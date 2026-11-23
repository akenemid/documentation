"""Mode direct des notes : deux instants (date des cours, instant de connaissance des notes).

Hors ligne, journal temporaire (``tmp_path``), horloge simulée : les instants d'écriture sont fixés
par ``NoteStore.add(now=…)`` (mode ``BRVM_ALPHA_SIMULATED_CLOCK`` de ``conftest.py``) et l'instant
de connaissance par le paramètre ``known_at`` / ``notes_known_at`` ou l'option ``--notes-au``. Les
panels sont synthétiques (dates de S0 seulement) : aucune performance n'est évaluée sur
l'échantillon vierge S1 et le journal réel ``data/notes`` n'est jamais touché.

Scénario des indices : dernier BOC le vendredi 20/11/2026, note saisie le dimanche 22/11/2026 au
soir, séance d'application le lundi 23/11/2026. Scénario de l'ordre de bataille : dernier BOC du
panel synthétique le vendredi 23/08/2024, note saisie le samedi 24/08/2024, séance d'application le
lundi 26/08/2024.
"""

from __future__ import annotations

import json
import re
import warnings
from pathlib import Path

import pandas as pd
import pytest

from test_index_eval import synthetic_panel
from test_report_html import _registry, _render, _section, synth  # noqa: F401 - fixture importée
from test_ui import FakeServices, call, token, wait_job

from brvm_alpha import cli
from brvm_alpha.notes import index_eval as ie
from brvm_alpha.notes import signals as sg
from brvm_alpha.notes.model import SIMULATED_CLOCK_ENV, Note
from brvm_alpha.notes.store import NoteStore
from brvm_alpha.portfolio import recommend as R
from brvm_alpha.strategy import BrvmAlpha

T_BOC = pd.Timestamp("2026-11-20")  # vendredi : dernier BOC du panel synthétique des indices
SUNDAY = "2026-11-22T20:00:00Z"  # saisie du dimanche soir
KNOWN = "2026-11-22T20:30:00Z"  # instant de connaissance (« maintenant »)
MONDAY = pd.Timestamp("2026-11-23")
LINE_RE = re.compile(r"Notes connues au (\d{2}/\d{2}/\d{4} \d{2}:\d{2}) UTC, appliquées à la séance du "
                     r"(\d{2}/\d{2}/\d{4}) : (\d+) en vigueur \(dont (\d+) manuelles?\), (\d+) filtre\(s\) de risque "
                     r"actif\(s\)")


# ---------------------------------------------------------------------------
# Outils
# ---------------------------------------------------------------------------


def bearish_index_note(when: str = SUNDAY, **kw) -> Note:
    """Note manuelle baissière de forte conviction sur le Composite (analyse fournie : score −0,8)."""
    base = dict(title="Composite : je réduis l'exposition", text="Valorisations tendues, largeur en baisse.",
                targets=["IDX:BRVM-C"], stance="baissier", conviction=5, author="analyste", created_at=when,
                analysis={"targets": ["IDX:BRVM-C"], "event_type": "MANUAL", "score": -0.8, "confidence": 0.8,
                          "risk_flags": []})
    base.update(kw)
    return Note(**base)


def ag_cancel_note(symbol: str, when: str, *, author: str = "analyste", published: str | None = None,
                   url: str = "") -> Note:
    """Annulation d'assemblée générale (R2 : aucun achat pendant 60 séances), analyse fournie."""
    return Note(title=f"{symbol} : annulation de l'Assemblée Générale Ordinaire",
                text="L'assemblée générale ordinaire convoquée est annulée sur instruction du régulateur.",
                targets=[symbol], author=author, source="manual" if author == "analyste" else "brvm_list", url=url,
                created_at=when, published_at=published, event_type="AG_CANCEL",
                analysis={"targets": [symbol], "event_type": "AG_CANCEL", "score": -0.5, "confidence": 0.7,
                          "risk_flags": ["R2"]})


def line_fields(text: str) -> tuple[str, str, int, int, int]:
    m = LINE_RE.search(text)
    assert m, text[:600]
    return m.group(1), m.group(2), int(m.group(3)), int(m.group(4)), int(m.group(5))


@pytest.fixture(scope="module")
def panel() -> dict[str, pd.DataFrame]:
    return synthetic_panel()


@pytest.fixture(scope="module")
def panel_dir(tmp_path_factory, panel) -> Path:
    """Panel synthétique des indices écrit sur disque (pour la ligne de commande)."""
    root = tmp_path_factory.mktemp("panel_direct")
    for name, df in panel.items():
        df = df.assign(available=True) if name == "sessions" else df
        df.to_parquet(root / f"{'adjusted_prices' if name == 'adjusted' else name}.parquet")
    return root


# ---------------------------------------------------------------------------
# Deux instants : séance d'application et coupure de 09h00 UTC
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("known, session", [
    ("2026-11-20T18:00:00Z", "2026-11-23"),  # vendredi soir, après la clôture
    ("2026-11-22T20:30:00Z", "2026-11-23"),  # dimanche soir
    ("2026-11-23T08:59:00Z", "2026-11-23"),  # lundi avant la coupure
    ("2026-11-23T09:00:00Z", "2026-11-24"),  # coupure passée : séance suivante
    ("2026-11-23T15:00:00Z", "2026-11-24"),
    ("2026-11-25T10:00:00Z", "2026-11-26"),  # panel en retard de trois séances
    ("2026-11-19T10:00:00Z", "2026-11-23"),  # instant antérieur au BOC : jamais avant la séance suivante
])
def test_application_session_is_next_session_or_the_following_after_cutoff(panel, known, session):
    cal = panel["sessions"]
    m = sg.notes_moment(T_BOC, known, cal)
    assert m.mode == "direct" and m.prices_date == T_BOC and m.session == pd.Timestamp(session)
    assert sg.application_session(T_BOC, known, cal) == pd.Timestamp(session)


def test_application_session_skips_weekend_and_fixed_holiday():
    cal = pd.bdate_range("2026-11-02", "2026-12-24")  # dernier BOC : jeudi 24/12/2026
    m = sg.notes_moment("2026-12-24", "2026-12-24T20:00:00Z", cal)
    assert m.session == pd.Timestamp("2026-12-28")  # vendredi 25/12 férié, puis week-end


def test_historical_moment_is_the_default_and_keeps_the_date():
    m = sg.notes_moment(T_BOC)
    assert m.mode == "historique" and m.known_at is None and m.session == T_BOC and not m.direct
    assert "mode historique" in m.describe() and "20/11/2026" in m.describe()
    # Une date seule comme instant de connaissance désigne la fin de la journée.
    d = sg.notes_moment(T_BOC, "2026-11-22")
    assert d.known_at == pd.Timestamp("2026-11-22 23:59:59.999999", tz="UTC") and d.session == MONDAY


# ---------------------------------------------------------------------------
# Sélection des notes : direct contre historique
# ---------------------------------------------------------------------------


def test_note_entered_now_is_in_force_in_direct_mode_only(tmp_path):
    st = NoteStore(tmp_path)
    nid = st.add(bearish_index_note(), now=SUNDAY)
    # Mode historique (défaut) à la date du BOC : rien, la note est postérieure.
    assert len(sg.notes_asof(st, T_BOC)) == 0
    assert len(sg.note_scores(st, T_BOC)) == 0
    hist = sg.notes_in_force(st, T_BOC)
    assert hist["mode"] == "historique" and hist["n_in_force"] == 0
    assert "mode historique" in hist["line"] and "0 en vigueur" in hist["line"]
    assert "n'agit pas" in hist["scores_message"]
    # Mode direct : connue maintenant, appliquée à la séance du lundi.
    df = sg.notes_asof(st, T_BOC, known_at=KNOWN)
    assert list(df["note_id"]) == [nid] and df["first_tradable_session"].iloc[0] == MONDAY
    sc = sg.note_scores(st, T_BOC, known_at=KNOWN, equities=None)
    assert sc.loc["IDX:BRVM-C", "score"] == pytest.approx(-0.8)  # décroissance exp(0) = 1 à la séance d'application
    d = sg.notes_in_force(st, T_BOC, known_at=KNOWN, equities=None)
    assert line_fields(d["line"]) == ("22/11/2026 20:30", "23/11/2026", 1, 1, 0)
    assert d["n_scored"] == 1 and bool(d["table"]["manual"].iloc[0]) and bool(d["table"]["tilt"].iloc[0])
    assert d["table"]["weight"].iloc[0] == pytest.approx(-0.8)
    # Un instant antérieur à la saisie ne voit pas la note.
    assert len(sg.notes_asof(st, T_BOC, known_at="2026-11-22T19:59:00Z")) == 0


def test_note_published_tomorrow_does_not_act(tmp_path):
    st = NoteStore(tmp_path)
    # Publication datée du lundi 08h00 (avant la coupure : séance du lundi), saisie le dimanche soir.
    a = st.add(bearish_index_note(title="Communiqué attendu demain matin", published_at="2026-11-23T08:00:00Z"),
               now=SUNDAY)
    # Publication datée « lundi » sans heure : réputée connue en fin de journée, séance du mardi.
    b = st.add(bearish_index_note(title="Publication datée de demain", published_at="2026-11-23"), now=SUNDAY)
    assert st.get(a).first_tradable_session == MONDAY and st.get(b).first_tradable_session == pd.Timestamp("2026-11-24")
    assert len(sg.notes_asof(st, T_BOC, known_at=KNOWN)) == 0  # dimanche soir : aucune n'est encore publiée
    d = sg.notes_in_force(st, T_BOC, known_at=KNOWN, equities=None)
    assert d["n_in_force"] == 0 and "Aucune note en vigueur" in d["scores_message"]
    # Lundi 08h30 : la première est publiée et négociable à la séance du jour ; pas la seconde.
    mon = sg.notes_asof(st, T_BOC, known_at="2026-11-23T08:30:00Z")
    assert list(mon["note_id"]) == [a]
    # Lundi après la coupure : séance d'application du mardi, les deux sont en vigueur.
    tue = sg.notes_asof(st, T_BOC, known_at="2026-11-23T10:00:00Z")
    assert set(tue["note_id"]) == {a, b}


def test_cutoff_moves_the_application_session_and_the_decay(tmp_path, panel):
    st = NoteStore(tmp_path)
    st.add(bearish_index_note(), now=SUNDAY)
    cal = panel["sessions"]
    before = sg.notes_in_force(st, T_BOC, known_at="2026-11-23T08:59:00Z", calendar=cal, equities=None)
    after = sg.notes_in_force(st, T_BOC, known_at="2026-11-23T09:00:00Z", calendar=cal, equities=None)
    assert before["session"] == MONDAY and after["session"] == pd.Timestamp("2026-11-24")
    assert line_fields(before["line"])[1] == "23/11/2026" and line_fields(after["line"])[1] == "24/11/2026"
    assert int(before["table"]["sessions_elapsed"].iloc[0]) == 0
    assert int(after["table"]["sessions_elapsed"].iloc[0]) == 1  # une séance écoulée : exp(−1/10)
    assert after["table"]["decay"].iloc[0] == pytest.approx(float(sg.decay_factor(1)))


def test_auto_note_ages_from_publication_manual_note_from_entry(tmp_path, panel):
    """Une note collectée aujourd'hui sur une publication ancienne a l'âge de sa publication ; un avis
    de l'analyste vaut à partir de sa saisie, même s'il cite une publication ancienne."""
    st = NoteStore(tmp_path)
    cal = panel["sessions"]
    auto = st.add(ag_cancel_note("ETIT", SUNDAY, author="auto", published="2026-10-23",
                                 url="https://www.brvm.org/sites/default/files/annulation_ago.pdf"), now=SUNDAY)
    manual = st.add(Note(title="SNTS : avis sur les comptes de septembre", text="Je reste vendeur.", targets=["SNTS"],
                         stance="baissier", conviction=4, published_at="2026-10-23", created_at=SUNDAY,
                         analysis={"targets": ["SNTS"], "event_type": "MANUAL", "score": -0.6, "confidence": 0.7}),
                    now=SUNDAY)
    df = sg.notes_asof(st, T_BOC, known_at=KNOWN, calendar=cal).set_index("note_id")
    assert df.loc[auto, "first_tradable_session"] == pd.Timestamp("2026-10-26")  # séance de la publication
    assert df.loc[manual, "first_tradable_session"] == MONDAY  # séance de la saisie
    assert df.loc[manual, "first_tradable_session_published"] == pd.Timestamp("2026-10-26")
    ov = sg.manual_overlays(st, T_BOC, known_at=KNOWN, calendar=cal, equities=panel["equities"])
    assert ov["mode"] == "direct" and ov["session"] == MONDAY and ov["asof"] == T_BOC
    flag = ov["flags"]["ETIT"][0]
    # R2 : 60 séances à partir du 26/10/2026 ; 21 séances écoulées au 23/11/2026 (aucun férié sur la période).
    assert flag["code"] == "R2" and flag["since"] == pd.Timestamp("2026-10-26") and flag["remaining_sessions"] == 39
    assert flag["until"] == pd.Timestamp("2027-01-19") and "ETIT" in ov["block_buys"]
    assert flag["url"].startswith("https://www.brvm.org/") and flag["source"] == "brvm_list"
    # L'avis de l'analyste (horizon 20 séances) n'a pas expiré : inclinaison −4/5 × 0,5 = −0,4 σ.
    assert ov["tilt"]["SNTS"] == pytest.approx(-0.4) and manual in ov["tilt_notes"]
    # Mode historique plus tard : âge compté depuis la connaissance (règle stricte inchangée).
    strict = sg.notes_asof(st, "2026-11-23", calendar=cal).set_index("note_id")
    assert strict.loc[auto, "first_tradable_session"] == MONDAY


def test_archive_and_new_version_take_effect_at_their_writing_instant(tmp_path, panel):
    st = NoteStore(tmp_path)
    nid = st.add(ag_cancel_note("ETIT", SUNDAY), now=SUNDAY)
    kw = dict(calendar=panel["sessions"], equities=panel["equities"])
    assert sg.notes_in_force(st, T_BOC, known_at=KNOWN, **kw)["block_buys"] == ["ETIT"]
    # Nouvelle version (analyse enrichie) écrite à 20h40 : en vigueur seulement à partir de cet instant.
    st.update(nid, now="2026-11-22T20:40:00Z", reanalyze=False,
              analysis={"targets": ["ETIT"], "event_type": "AG_CANCEL", "score": -0.9, "confidence": 0.9,
                        "risk_flags": ["R2"]})
    assert sg.notes_in_force(st, T_BOC, known_at=KNOWN, **kw)["table"]["score"].iloc[0] == pytest.approx(-0.5)
    later = sg.notes_in_force(st, T_BOC, known_at="2026-11-22T20:45:00Z", **kw)
    assert later["table"]["score"].iloc[0] == pytest.approx(-0.9) and int(later["table"]["version"].iloc[0]) == 2
    # Archivage à 21h00 : le filtre est levé pour tout instant postérieur, pas pour un instant antérieur.
    st.archive(nid, reason="AG reconvoquée", now="2026-11-22T21:00:00Z")
    assert sg.notes_in_force(st, T_BOC, known_at="2026-11-22T20:45:00Z", **kw)["block_buys"] == ["ETIT"]
    lifted = sg.notes_in_force(st, T_BOC, known_at="2026-11-22T21:30:00Z", **kw)
    assert lifted["block_buys"] == [] and lifted["n_in_force"] == 0 and lifted["n_filters"] == 0


def test_backdated_version_counts_only_when_the_instant_is_the_present(tmp_path, monkeypatch):
    monkeypatch.delenv(SIMULATED_CLOCK_ENV, raising=False)  # horloge réelle : un « now » passé est antidaté
    now = pd.Timestamp.now(tz="UTC")
    st = NoteStore(tmp_path)
    old = (now - pd.Timedelta(days=20)).isoformat()
    nid = st.add(ag_cancel_note("ETIT", old, author="auto", published=(now - pd.Timedelta(days=21)).isoformat(),
                                url="https://www.brvm.org/x.pdf"), now=old)
    assert "reconstitue" in st.get(nid).tags
    prices = (now - pd.Timedelta(days=3)).normalize().tz_localize(None)
    assert len(sg.notes_asof(st, prices)) == 0  # règle stricte : version reconstituée ignorée
    assert list(sg.notes_asof(st, prices, known_at=now)["note_id"]) == [nid]  # connue au moment où l'outil tourne
    assert len(sg.notes_asof(st, prices, known_at=now - pd.Timedelta(days=2))) == 0  # instant passé : non prouvé


def test_summary_says_clearly_when_no_note_carries_a_score(tmp_path):
    st = NoteStore(tmp_path)
    st.add(Note(title="SIBC : rapport d'activités du 3e trimestre 2026", text="", targets=["SIBC"], author="auto",
                source="brvm_issuer", url="https://www.brvm.org/rapport.pdf", published_at="2026-11-18",
                created_at=SUNDAY, analysis={"targets": ["SIBC"], "event_type": "ACT_Q3", "score": 0.0,
                                             "confidence": 0.6}), now=SUNDAY)
    d = sg.notes_in_force(st, T_BOC, known_at=KNOWN, equities=None)
    assert line_fields(d["line"])[2:] == (1, 0, 0) and d["n_scored"] == 0
    assert "ne porte de score directionnel" in d["scores_message"] and "notes lire" in d["scores_message"]
    pos, neg = sg.top_notes(d["table"])
    assert len(pos) == 0 and len(neg) == 0


# ---------------------------------------------------------------------------
# Évaluation des indices
# ---------------------------------------------------------------------------


def test_manual_bearish_note_changes_the_index_score_in_direct_mode_only(tmp_path, panel):
    st = NoteStore(tmp_path)
    nid = st.add(bearish_index_note(), now=SUNDAY)
    codes = ["IDX:BRVM-C", "IDX:PRESTIGE"]
    base = ie.evaluate_indices(panel, asof=T_BOC, indices=codes)  # sans journal
    hist = ie.evaluate_indices(panel, store=st, asof=T_BOC, indices=codes)  # journal, mode historique
    direct = ie.evaluate_indices(panel, store=st, asof=T_BOC, indices=codes, notes_known_at=KNOWN)
    b, h, d = base.loc["IDX:BRVM-C"], hist.loc["IDX:BRVM-C"], direct.loc["IDX:BRVM-C"]
    # Mode historique à la date du BOC : rien ne change (la note est postérieure).
    assert h["composite"] == pytest.approx(b["composite"]) and h["stance"] == b["stance"] and h["notes_n"] == 0
    assert h["z_notes"] is None or not pd.notna(h["z_notes"])
    assert hist.attrs["notes_moment"].mode == "historique"
    assert any("mode historique" in r and "aucune note en vigueur" in r for r in h["reasons"])
    assert any("notes n.d. : aucune note en vigueur" in r for r in h["reasons"])  # jamais « n.d. » seul
    # Mode direct : la composante « notes » existe et le score baisse ; les cours ne bougent pas.
    assert d["notes_score"] == pytest.approx(-0.8) and d["notes_n"] == 1
    assert d["z_notes"] == pytest.approx(-0.8 / ie.NOTES_SCALE)
    assert d["composite"] < b["composite"] - 0.1
    assert d["composite_ex_notes"] == pytest.approx(b["composite"]) and d["stance_ex_notes"] == b["stance"]
    for col in ("level", "ret_1m", "ret_12m", "z_trend", "z_valuation", "z_breadth", "date"):
        assert d[col] == b[col] or d[col] == pytest.approx(b[col])
    w = ie.COMPONENT_WEIGHTS
    avail = {k: b[f"z_{c}"] for k, c in (("tendance", "trend"), ("valorisation", "valuation"), ("largeur", "breadth"),
                                           ("regime", "regime")) if pd.notna(b[f"z_{c}"])}
    # Surcouche additive (recette du 22/11/2026) : score sans notes + 0,15 × z notes, sans diluer les autres.
    expected = sum(w[k] * v for k, v in avail.items()) / sum(w[k] for k in avail) + w["notes"] * d["z_notes"]
    assert d["composite"] == pytest.approx(expected)
    det = d["notes_detail"]
    assert [e["note_id"] for e in det] == [nid] and det[0]["part"] == pytest.approx(-0.8)
    assert direct.attrs["notes_moment"].session == MONDAY
    assert direct.attrs["notes_line"].startswith("Notes connues au 22/11/2026 20:30 UTC, appliquées à la séance du 23/11/2026")
    txt = " ".join(d["reasons"])
    assert "Notes (connues au 22/11/2026 20:30 UTC, appliquées à la séance du 23/11/2026) : score −0,800" in txt
    assert "Notes qui portent la composante" in txt and "Effet des notes" in txt
    # La note du Composite se propage (0,25) aux constituants du Prestige.
    assert direct.loc["IDX:PRESTIGE", "notes_score"] == pytest.approx(0.25 * -0.8)
    assert hist.loc["IDX:PRESTIGE", "composite"] == pytest.approx(base.loc["IDX:PRESTIGE", "composite"])


def test_index_dossier_uses_the_same_direct_notes(tmp_path, panel):
    st = NoteStore(tmp_path)
    st.add(bearish_index_note(), now=SUNDAY)
    st.add(ag_cancel_note("ETIT", SUNDAY), now=SUNDAY)
    hist = ie.index_dossier("IDX:BRVM-C", panel, store=st, asof=T_BOC)
    direct = ie.index_dossier("IDX:BRVM-C", panel, store=st, asof=T_BOC, notes_known_at=KNOWN)
    assert hist["recent_notes"] == [] and not hist["constituents"]["flags"].map(bool).any()
    assert "mode historique" in hist["notes_line"]
    assert len(direct["recent_notes"]) == 2 and direct["notes_moment"].session == MONDAY
    assert direct["constituents"].loc["ETIT", "flags"] == ["R2"]
    assert direct["overlays"]["mode"] == "direct" and "ETIT" in direct["overlays"]["block_buys"]
    assert any(r.startswith("Filtres actifs sur les constituants") and "ETIT (R2)" in r for r in direct["reasons"])


# ---------------------------------------------------------------------------
# Ordre de bataille : achat bloqué par une note, levée par archivage
# ---------------------------------------------------------------------------

SAT = "2024-08-24T10:00:00Z"  # samedi qui suit le dernier BOC du panel synthétique (vendredi 23/08/2024)
SAT_KNOWN = "2024-08-24T12:00:00Z"


def _order(synth, tmp: Path, **kw):  # noqa: F811
    base = dict(panels=synth["panels"], panel_dir=synth["panel_dir"], validation_dir=tmp / "absent",
                registry_path=synth["reg_no"], n_boot=200, seed=2, index_evaluation=False, comparison=False,
                explanations=False, variant="REF", today=synth["t"])
    base.update(kw)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return R.recommend(synth["t"], 10_000_000, **base)


def _targets(o) -> dict[str, int]:
    return {r.symbole: int(r.cibles) for r in o.lignes.itertuples(index=False) if r.cibles > 0}


@pytest.fixture(scope="module")
def blocked(synth, tmp_path_factory):  # noqa: F811
    """Ordre REF sans notes, puis avec une annulation d'AG sur une ligne retenue (direct et historique)."""
    tmp = tmp_path_factory.mktemp("blocage")
    assert synth["t"] == pd.Timestamp("2024-08-23")
    base = _order(synth, tmp, notes_store=False)
    sym = str(base.lignes.sort_values("poids_cible", ascending=False).iloc[2]["symbole"])
    st = NoteStore(tmp / "notes")
    # Analyse réelle de la note (aucune analyse fournie) : type AG_CANCEL, filtre R2.
    nid = st.add(Note(title=f"{sym} : annulation de l'Assemblée Générale Ordinaire",
                      text="L'assemblée générale ordinaire convoquée est annulée sur instruction de la Commission "
                           "Bancaire.", targets=[sym], author="analyste", url="https://exemple.test/communique.pdf",
                      created_at=SAT), analyze=True, now=SAT)
    assert "R2" in (st.get(nid).analysis or {}).get("risk_flags", [])
    direct = _order(synth, tmp, notes_store=st, notes_known_at=SAT_KNOWN)
    hist = _order(synth, tmp, notes_store=st)
    return {"tmp": tmp, "base": base, "sym": sym, "store": st, "nid": nid, "direct": direct, "hist": hist}


def test_ag_cancel_note_blocks_the_purchase_in_direct_mode(blocked):
    base, o, sym, nid = blocked["base"], blocked["direct"], blocked["sym"], blocked["nid"]
    assert sym in _targets(base) and sym not in _targets(o)  # l'achat n'a pas lieu
    nt = o.declencheurs["notes"]
    assert nt["mode"] == "direct" and nt["seance_application"] == pd.Timestamp("2024-08-26")
    assert line_fields(nt["ligne"]) == ("24/08/2024 12:00", "26/08/2024", 1, 1, 1)
    b = nt["blocages"][0]
    assert (b["symbole"], b["code"], b["note_id"], b["bloque_achats"]) == (sym, "R2", nid, True)
    assert b["depuis"] == pd.Timestamp("2024-08-26") and b["seances_restantes"] == 59
    # 60 séances à partir du 26/08/2024 : jours ouvrés hors fériés fixes (01/11 et 15/11) → 19/11/2024.
    assert b["jusqu_au"] == pd.Timestamp("2024-11-19")
    assert b["note_url"] == "https://exemple.test/communique.pdf" and b["note_source"] == "manual"
    assert f"notes archive {nid[:12]}" in b["lever"] and "sans les notes, 0 % avec" in b["effet_poids"]
    # Effet sur les poids : même total investi, le poids du titre bloqué est réparti (règles existantes).
    eff = nt["effet"]
    w0 = float(base.lignes.set_index("symbole").loc[sym, "poids_cible"])
    row = next(x for x in eff["lignes"] if x["symbole"] == sym)
    assert row["poids_sans_notes"] == pytest.approx(w0) and row["poids_avec_notes"] == 0.0 and "R2" in row["motif"]
    assert eff["total_avec_notes"] == pytest.approx(eff["total_sans_notes"]) == pytest.approx(0.98)
    assert sum(x["ecart"] for x in eff["lignes"]) == pytest.approx(0.0, abs=1e-9)
    # Les totaux de l'ordre restent exacts, au franc près.
    L, k = o.lignes, o.couts
    assert len(_targets(o)) == 20 and float(L["poids_cible"].sum()) == pytest.approx(0.98)
    assert k["investi_apres"] == pytest.approx(float((L["cibles"] * L["cours_reference"]).sum()))
    assert k["achats_brut"] == int(L.loc[L["sens"] == "achat", "montant_brut"].sum())
    assert k["liquidites_apres"] == pytest.approx(o.liquidites_initiales - k["achats_net"] + k["ventes_net"])
    assert k["investi_pct"] <= 0.98 + 1e-12 and o.execution["liquidites_finales_pire_cas"] >= 0


def test_blocked_purchase_is_written_in_plain_words(blocked):
    o, sym, nid = blocked["direct"], blocked["sym"], blocked["nid"]
    md = o.to_markdown()
    assert LINE_RE.search(md)
    assert "Achats bloqués par les notes de l'analyste et effet sur les poids" in md
    warn = next(w for w in o.avertissements if w.startswith("ACHAT BLOQUÉ par une note"))
    for piece in (sym, "R2", nid[:12], "du 24/08/2024", "annulation de l'Assemblée Générale Ordinaire",
                  "jusqu'au 19/11/2024", "Pour lever le blocage : archiver la note"):
        assert piece in warn, piece
    row = next(line for line in md.splitlines() if line.startswith(f"| {sym} | R2"))
    assert "https://exemple.test/communique.pdf" in row and "source manual" in row and "encore 59 séance(s)" in row
    assert "Poids cible sans les notes" in md and R.BANNER in md
    html = o.to_html_fragment()
    assert "ACHAT BLOQUÉ par une note" in html and "<a " not in html  # adresse en texte dans le fragment
    payload = json.loads(json.dumps(o.to_dict()))
    assert payload["declencheurs"]["notes"]["blocages"][0]["symbole"] == sym
    assert payload["declencheurs"]["notes"]["connues_au"].startswith("2024-08-24T12:00")


def test_historical_call_ignores_the_later_note(blocked):
    base, hist = blocked["base"], blocked["hist"]
    assert _targets(hist) == _targets(base)
    pd.testing.assert_series_equal(hist.lignes.set_index("symbole")["poids_cible"],
                                   base.lignes.set_index("symbole")["poids_cible"])
    nt = hist.declencheurs["notes"]
    assert nt["mode"] == "historique" and nt["n_en_vigueur"] == 0 and nt["blocages"] == [] and nt["effet"] is None
    assert "mode historique" in nt["ligne"] and "0 filtre(s) de risque actif(s)" in nt["ligne"]
    assert not any("ACHAT BLOQUÉ" in w for w in hist.avertissements)


def test_archiving_the_note_lifts_the_block(blocked, synth):  # noqa: F811
    st, nid, base = blocked["store"], blocked["nid"], blocked["base"]
    # Les ordres de la fixture sont déjà calculés : l'archivage (journal en ajout seul) ne les modifie pas.
    st.archive(nid, reason="assemblée reconvoquée", now="2024-08-24T14:00:00Z")
    after = _order(synth, blocked["tmp"], notes_store=st, notes_known_at="2024-08-24T15:00:00Z")
    assert _targets(after) == _targets(base)
    nt = after.declencheurs["notes"]
    assert nt["blocages"] == [] and nt["n_filtres"] == 0 and line_fields(nt["ligne"])[2:] == (0, 0, 0)
    assert not any("ACHAT BLOQUÉ" in w for w in after.avertissements)
    # À un instant antérieur à l'archivage, le blocage vaut encore (version en vigueur à cet instant).
    still = sg.notes_in_force(st, synth["t"], known_at=SAT_KNOWN, equities=None,
                              calendar=list(synth["panels"]["close"].index))
    assert still["block_buys"] == [blocked["sym"]]


# ---------------------------------------------------------------------------
# Non-régression : les appels programmatiques restent stricts (aucune anticipation)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("variant", ["REF", "A"])
def test_programmatic_decision_is_identical_with_a_later_journal(synth, tmp_path, variant):  # noqa: F811
    """Décision S0 à une date passée, journal non vide mais postérieur : poids identiques avec et sans."""
    panels, t = synth["panels"], synth["t"]
    assert t > pd.Timestamp("2022-11-16")  # S0 seulement
    st = NoteStore(tmp_path)
    syms = list(panels["close"].columns)
    for i, s in enumerate(syms[:6]):
        st.add(ag_cancel_note(s, SAT), now=SAT)  # filtres R2 postérieurs à la décision
        st.add(Note(title=f"{s} : veto", text="exclusion", targets=[s], stance="baissier", conviction=5, tags=["veto"],
                    created_at=SAT, analysis={"targets": [s], "event_type": "MANUAL", "score": -0.8}), now=SAT)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        without = BrvmAlpha(variant=variant, capital=1e7, notes=None).decide(t, panels)
        with_j = BrvmAlpha(variant=variant, capital=1e7, notes=st).decide(t, panels)
        # Un instant de connaissance antérieur à la décision est ignoré (mode historique).
        early = BrvmAlpha(variant=variant, capital=1e7, notes=st,
                          notes_known_at="2024-08-20T12:00:00Z").decide(t, panels)
        # Validation S1 : aucune note, quel que soit l'instant (D11).
        assert BrvmAlpha(variant=variant, notes=st, notes_known_at=SAT_KNOWN, validation_s1=True,
                         window_basis="sessions").notes_known_at is None
    pd.testing.assert_series_equal(with_j.weights, without.weights)
    pd.testing.assert_series_equal(early.weights, without.weights)
    nd = with_j.diagnostics["notes"]
    assert nd["available"] and nd["mode"] == "historique" and nd["veto"] == {} and nd["flags"] == {}
    assert early.diagnostics["notes"]["mode"] == "historique"
    # Le même journal, en mode direct, agit (veto et filtres) : la différence vient bien du seul instant.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        direct = BrvmAlpha(variant=variant, capital=1e7, notes=st, notes_known_at=SAT_KNOWN).decide(t, panels)
    nd = direct.diagnostics["notes"]
    assert nd["mode"] == "direct" and nd["session"] == pd.Timestamp("2024-08-26") and len(nd["veto"]) == 6
    assert float(direct.weights.reindex(syms[:6]).fillna(0.0).sum()) == 0.0


def test_default_arguments_are_historical_everywhere():
    import inspect

    from brvm_alpha.report import html as RH

    for fn, name in ((sg.notes_asof, "known_at"), (sg.note_scores, "known_at"), (sg.note_contributions, "known_at"),
                     (sg.manual_overlays, "known_at"), (sg.notes_in_force, "known_at"),
                     (ie.evaluate_indices, "notes_known_at"), (ie.index_dossier, "notes_known_at"),
                     (R.recommend, "notes_known_at"), (RH.render_report, "notes_known_at"),
                     (BrvmAlpha.__init__, "notes_known_at"), (cli.explain_symbol, "notes_known_at")):
        assert inspect.signature(fn).parameters[name].default is None, fn


# ---------------------------------------------------------------------------
# Ligne de commande : --notes-au, mode direct par défaut à la dernière séance
# ---------------------------------------------------------------------------


def test_parse_instant_and_notes_instant_rules():
    assert cli.parse_instant("2026-11-22T21:00") == pd.Timestamp("2026-11-22 21:00", tz="UTC")
    assert cli.parse_instant("2026-11-22 07:05") == pd.Timestamp("2026-11-22 07:05", tz="UTC")
    assert cli.parse_instant("2026-11-22") == pd.Timestamp("2026-11-22 23:59:59.999999", tz="UTC")
    assert cli.parse_instant("22/11/2026 08:59") == pd.Timestamp("2026-11-22 08:59", tz="UTC")
    assert cli.parse_instant("2026-11-23T00:00") == pd.Timestamp("2026-11-23 00:00", tz="UTC")  # minuit explicite
    for bad in ("hier", "2026-13-40", "2026-11-22T25:00", ""):
        with pytest.raises(ValueError):
            cli.parse_instant(bad)
    now = pd.Timestamp("2026-11-22 20:30", tz="UTC")
    kw = dict(last=T_BOC, now=now)
    assert cli.notes_instant(None, None, **kw) == now  # aucune date : mode direct
    assert cli.notes_instant(T_BOC, None, **kw) == now  # dernière séance demandée : mode direct
    assert cli.notes_instant(pd.Timestamp("2026-11-22"), None, **kw) == now  # date postérieure au dernier BOC
    assert cli.notes_instant(pd.Timestamp("2026-11-13"), None, **kw) is None  # date passée : mode historique
    fixed = cli.notes_instant(pd.Timestamp("2026-11-13"), "2026-11-15T10:00", **kw)
    assert fixed == pd.Timestamp("2026-11-15 10:00", tz="UTC")  # --notes-au fixe l'instant


@pytest.fixture()
def cli_clock(monkeypatch):
    monkeypatch.setattr(cli, "last_session", lambda panel_dir=None: T_BOC)
    monkeypatch.setattr(cli, "now_utc", lambda: pd.Timestamp("2026-11-22 20:30", tz="UTC"))
    return pd.Timestamp("2026-11-22 20:30", tz="UTC")


def test_cli_passes_the_knowledge_instant_to_every_command(tmp_path, capsys, monkeypatch, cli_clock):
    import brvm_alpha.report as report

    NoteStore(tmp_path).add(bearish_index_note(), now=SUNDAY)
    seen: dict[str, object] = {}

    def fake_eval(*a, **k):
        seen["indices"] = k.get("notes_known_at", "absent")
        return pd.DataFrame({"label": ["BRVM Composite"], "date": [T_BOC], "level": [492.89], "ret_1m": [-0.06],
                             "ret_12m": [0.43], "ytd": [0.42], "stance": ["NEUTRE"], "confidence": [0.5],
                             "composite": [-0.4], "reasons": [["raison"]]},
                            index=pd.Index(["IDX:BRVM-C"], name="index"))

    class FakeOrder:
        asof = T_BOC

        def to_markdown(self):
            return "# Ordre\n"

    def fake_rec(asof, capital, **k):
        seen["recommend"] = k.get("notes_known_at", "absent")
        return FakeOrder()

    def fake_report(asof, capital, out, **k):
        seen["report"] = k.get("notes_known_at", "absent")
        Path(out).write_text("<html></html>", encoding="utf-8")
        return Path(out)

    def fake_explain(symbol, asof, **k):
        seen["explain"] = k.get("notes_known_at", "absent")
        return {"symbol": symbol, "asof": asof, "variant": "REF", "text": "", "blocks": {}, "score": {}, "weight": 0.0,
                "risk_flags": {}, "choix_variante": None}

    def fake_dossier(code, **k):
        seen["dossier"] = k.get("notes_known_at", "absent")
        return {"index": code, "label": "BRVM Composite", "asof": T_BOC, "composition": "officielle",
                "evaluation": {"date": T_BOC, "stance": "NEUTRE", "confidence": 0.4, "composite": 0.1},
                "constituents": pd.DataFrame(), "recent_notes": [], "change_my_mind": [], "calendar": pd.DataFrame(),
                "reasons": ["raison"], "overlays": None}

    monkeypatch.setattr(ie, "evaluate_indices", fake_eval)
    monkeypatch.setattr(ie, "index_dossier", fake_dossier)
    monkeypatch.setattr(R, "recommend", fake_rec)
    monkeypatch.setattr(report, "build_report", fake_report)
    monkeypatch.setattr(cli, "explain_symbol", fake_explain)
    root = ["--racine", str(tmp_path)]
    # Mode direct : aucune date, ou la dernière séance du panel.
    for argv in (["indices"] + root, ["indices", "--date", "2026-11-20"] + root):
        assert cli.main(argv) == 0
        assert seen["indices"] == cli_clock
    out = capsys.readouterr().out
    assert line_fields(out) == ("22/11/2026 20:30", "23/11/2026", 1, 1, 0)
    assert cli.main(["recommend", "--capital", "10M"] + root) == 0 and seen["recommend"] == cli_clock
    assert cli.main(["report", "--capital", "10M", "--sortie", str(tmp_path / "r.html")] + root) == 0
    assert seen["report"] == cli_clock and "mode direct" in capsys.readouterr().out
    assert cli.main(["explain", "SNTS"] + root) == 0 and seen["explain"] == cli_clock
    # Mode historique : date passée demandée.
    assert cli.main(["indices", "--date", "2026-11-13"] + root) == 0 and seen["indices"] is None
    assert "mode historique" in capsys.readouterr().out
    assert cli.main(["recommend", "--capital", "10M", "--date", "2026-11-13"] + root) == 0 and seen["recommend"] is None
    assert cli.main(["report", "--capital", "10M", "--date", "2026-11-13", "--sortie", str(tmp_path / "r.html")]
                    + root) == 0 and seen["report"] is None
    assert cli.main(["explain", "SNTS", "--date", "2026-11-13"] + root) == 0 and seen["explain"] is None
    # --notes-au fixe l'instant, y compris avec une date passée ; une date seule : fin de journée.
    fixed = pd.Timestamp("2026-11-21 10:15", tz="UTC")
    assert cli.main(["indices", "--notes-au", "2026-11-21T10:15"] + root) == 0 and seen["indices"] == fixed
    assert cli.main(["indices", "dossier", "IDX:BRVM-C", "--notes-au", "2026-11-21T10:15"] + root) == 0
    assert seen["dossier"] == fixed
    assert cli.main(["indices", "dossier", "IDX:BRVM-C"] + root) == 0 and seen["dossier"] == cli_clock
    assert cli.main(["indices", "dossier", "IDX:BRVM-C", "--date", "2026-11-13"] + root) == 0 and seen["dossier"] is None
    assert cli.main(["indices", "dossier", "IDX:BRVM-C", "--sans-notes"]) == 0 and seen["dossier"] is None
    assert cli.main(["recommend", "--capital", "10M", "--date", "2026-11-13", "--notes-au", "2026-11-21"] + root) == 0
    assert seen["recommend"] == pd.Timestamp("2026-11-21 23:59:59.999999", tz="UTC")
    # Date seule d'aujourd'hui : la fin de la journée n'est pas encore arrivée, l'instant vaut « maintenant ».
    assert cli.main(["recommend", "--capital", "10M", "--date", "2026-11-13", "--notes-au", "2026-11-22"] + root) == 0
    assert seen["recommend"] == cli_clock
    assert cli.main(["report", "--capital", "10M", "--notes-au", "2026-11-21T10:15", "--sortie",
                     str(tmp_path / "r.html")] + root) == 0 and seen["report"] == fixed
    assert cli.main(["explain", "SNTS", "--notes-au", "2026-11-21T10:15"] + root) == 0 and seen["explain"] == fixed
    # --sans-notes : aucun instant transmis.
    assert cli.main(["recommend", "--capital", "10M", "--sans-notes"]) == 0 and seen["recommend"] is None
    capsys.readouterr()
    with pytest.raises(SystemExit) as exc:
        cli.main(["indices", "--notes-au", "hier"])
    assert exc.value.code == 2 and "instant invalide" in capsys.readouterr().err


def test_cli_indices_end_to_end_direct_historical_and_fixed_instant(tmp_path, capsys, monkeypatch, panel_dir):
    """Commande réelle (aucune doublure de calcul) sur le panel synthétique écrit sur disque."""
    st = NoteStore(tmp_path)
    st.add(bearish_index_note(), now=SUNDAY)
    st.add(ag_cancel_note("ETIT", SUNDAY, author="auto", published="2026-10-23",
                          url="https://www.brvm.org/sites/default/files/annulation_ago.pdf"), now=SUNDAY)
    monkeypatch.setattr(cli, "now_utc", lambda: pd.Timestamp("2026-11-22 20:30", tz="UTC"))
    base = ["indices", "--panel-dir", str(panel_dir), "--racine", str(tmp_path)]
    assert cli.main(base + ["--format", "json"]) == 0
    direct = json.loads(capsys.readouterr().out)
    comp = next(r for r in direct["indices"] if r["index"] == "IDX:BRVM-C")
    assert direct["notes"]["mode"] == "direct" and direct["notes"]["seance_application"].startswith("2026-11-23")
    assert line_fields(direct["notes"]["ligne"]) == ("22/11/2026 20:30", "23/11/2026", 2, 1, 1)
    assert direct["notes"]["filtres"][0]["symbole"] == "ETIT" and comp["z_notes"] < -1.0
    # Date passée : mode historique, la note du dimanche n'agit pas.
    assert cli.main(base + ["--date", "2026-11-13", "--format", "json"]) == 0
    hist = json.loads(capsys.readouterr().out)
    assert hist["notes"]["mode"] == "historique" and hist["notes"]["n_en_vigueur"] == 0
    assert next(r for r in hist["indices"] if r["index"] == "IDX:BRVM-C")["z_notes"] is None
    # --notes-au avant la saisie : aucune note ; après la coupure du lundi : séance du mardi.
    assert cli.main(base + ["--notes-au", "2026-11-22T19:00", "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out)["notes"]["n_en_vigueur"] == 0
    # Un instant futur est refusé (recette du 22/11/2026) : il est 20:30 le dimanche.
    assert cli.main(base + ["--notes-au", "2026-11-23T09:30"]) == 2
    assert "dans le futur" in capsys.readouterr().err
    monkeypatch.setattr(cli, "now_utc", lambda: pd.Timestamp("2026-11-23 10:00", tz="UTC"))
    assert cli.main(base + ["--notes-au", "2026-11-23T09:30"]) == 0
    out = capsys.readouterr().out
    assert line_fields(out)[:2] == ("23/11/2026 09:30", "24/11/2026")
    assert "Filtre actif — ETIT : R2" in out and "ACHATS BLOQUÉS" in out and "pour lever : archiver la note" in out
    assert "Notes (connues au 23/11/2026 09:30 UTC, appliquées à la séance du 24/11/2026)" in out
    assert cli.BANNER in out
    # Dossier d'indice : même ligne, filtre du constituant.
    assert cli.main(["indices", "dossier", "IDX:BRVM-C", "--panel-dir", str(panel_dir), "--racine", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert LINE_RE.search(out) and "Filtre actif sur un constituant — ETIT : R2" in out


def test_notes_add_tells_when_the_note_will_count(tmp_path, capsys, monkeypatch, cli_clock):
    assert cli.main(["notes", "add", "--racine", str(tmp_path), "--cible", "IDX:BRVM-C", "--titre", "Prudence",
                     "--avis", "baissier", "--conviction", "5"]) == 0
    out = capsys.readouterr().out
    assert "Prise en compte :" in out and "mode direct" in out or "première séance négociable" in out


# ---------------------------------------------------------------------------
# Lecture du contenu des documents : câblage (fonction simulée, jamais le réseau)
# ---------------------------------------------------------------------------

FAKE_REPORT = {
    "n_candidates": 5, "n_read": 3, "n_enriched": 2, "n_scanned": 1, "n_failed": 0, "n_requests": 3, "stopped": None,
    "details": [
        {"note_id": "a" * 40, "symbol": "SIVC", "title": "ERIUM CI : Profit Warning", "url": "https://www.brvm.org/a.pdf",
         "status": "enrichie", "score_before": 0.0, "score_after": -0.72, "extracted": {"rn_growth": -0.45}},
        {"note_id": "b" * 40, "symbol": "SNTS", "title": "SONATEL : rapport du 1er semestre",
         "url": "https://www.brvm.org/b.pdf", "status": "enrichie", "score_before": 0.0, "score_after": 0.31,
         "extracted": {}},
        {"note_id": "c" * 40, "symbol": "BOAC", "title": "BOA CI : états financiers", "url": "https://www.brvm.org/c.pdf",
         "status": "scan", "score_before": 0.0, "score_after": 0.0, "extracted": {}},
    ],
}


@pytest.fixture()
def fake_enrich(monkeypatch):
    from brvm_alpha.notes import research as rs

    def no_network(*a, **k):
        raise AssertionError("aucune requête réseau dans les tests")

    monkeypatch.setattr(rs, "_requests_transport", no_network)
    calls: list[dict] = []

    def enrich(store, **kw):
        calls.append({"store": store, **kw})
        return dict(FAKE_REPORT)

    monkeypatch.setattr(rs, "enrich_documents", enrich, raising=False)
    return calls


def test_cli_notes_lire_calls_enrich_documents_and_prints_the_report(tmp_path, capsys, fake_enrich):
    assert cli.main(["notes", "lire", "--racine", str(tmp_path), "--max", "7", "--hors-ligne", "--cibles",
                     "SIVC, SNTS"]) == 0
    out = capsys.readouterr().out
    call_ = fake_enrich[-1]
    assert call_["max_docs"] == 7 and call_["offline"] is True and call_["targets"] == ["SIVC", "SNTS"]
    assert call_["dry_run"] is False and isinstance(call_["store"], NoteStore)
    assert Path(call_["store"].root) == tmp_path
    assert "5 candidat(s), 3 lu(s), 2 note(s) enrichie(s), 1 document(s) scanné(s) à lire à la main, 0 erreur(s)" in out
    assert "score 0,00 → −0,72" in out and "à lire à la main" in out and "https://www.brvm.org/c.pdf" in out
    assert "Règles de politesse" in out and cli.BANNER in out
    # Défauts : 20 documents, en ligne, tout le journal ; --simulation : dry_run.
    assert cli.main(["notes", "lire", "--racine", str(tmp_path), "--simulation"]) == 0
    call_ = fake_enrich[-1]
    assert call_["max_docs"] == 20 and call_["offline"] is False and call_["targets"] is None and call_["dry_run"] is True
    capsys.readouterr()


def test_cli_notes_lire_reports_a_stop_and_a_missing_function(tmp_path, capsys, monkeypatch, fake_enrich):
    from brvm_alpha.notes import research as rs

    monkeypatch.setattr(rs, "enrich_documents", lambda store, **kw: {**FAKE_REPORT, "stopped": "HTTP 429 : arrêt"},
                        raising=False)
    assert cli.main(["notes", "lire", "--racine", str(tmp_path)]) == 5  # refus du site : code 5 (accès refusé)
    assert "Arrêt de la lecture : HTTP 429" in capsys.readouterr().out

    def boom(store, **kw):
        raise RuntimeError("PDF illisible")

    monkeypatch.setattr(rs, "enrich_documents", boom, raising=False)
    assert cli.main(["notes", "lire", "--racine", str(tmp_path)]) == 1
    assert "lecture du contenu des documents interrompue (RuntimeError : PDF illisible)" in capsys.readouterr().out
    monkeypatch.delattr(rs, "enrich_documents", raising=False)
    assert cli.main(["notes", "lire", "--racine", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "enrich_documents n'est pas installée" in out and "journal inchangé" in out


def test_cli_notes_research_pdf_option(tmp_path, capsys, monkeypatch, fake_enrich):
    from brvm_alpha.notes import research as rs

    stopped: list[str | None] = [None]

    def fake_run(store, **kw):
        res = rs.ResearchResult()
        res.report = rs.ResearchReport(n_items=0)
        res.report.stopped = stopped[0]
        return res

    monkeypatch.setattr(rs, "run_research", fake_run)
    base = ["notes", "research", "--racine", str(tmp_path), "--hors-ligne"]
    assert cli.main(base) == 0  # défaut : 20 documents après la collecte
    assert len(fake_enrich) == 1 and fake_enrich[-1]["max_docs"] == 20 and fake_enrich[-1]["offline"] is True
    assert "3 lu(s)" in capsys.readouterr().out
    assert cli.main(base + ["--pdf", "5", "--cibles", "SIVC"]) == 0
    assert fake_enrich[-1]["max_docs"] == 5 and fake_enrich[-1]["targets"] == ["SIVC"]
    assert cli.main(base + ["--pdf", "0"]) == 0  # 0 : aucun document lu
    assert len(fake_enrich) == 2 and "non demandée (--pdf 0)" in capsys.readouterr().out
    # Collecte en ligne arrêtée (403 / 429) : aucune lecture, aucune autre requête.
    stopped[0] = "HTTP 403"
    assert cli.main(["notes", "research", "--racine", str(tmp_path), "--pdf", "5"]) == 5  # refus : code 5
    assert len(fake_enrich) == 2 and "non lancée" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        cli.main(base + ["--pdf", "-1"])


# ---------------------------------------------------------------------------
# Interface : instant de connaissance des services, pages, case « lire les documents »
# ---------------------------------------------------------------------------

UI_NOW = pd.Timestamp("2026-11-22 20:30", tz="UTC")


@pytest.fixture()
def ui_direct(tmp_path, monkeypatch):
    import threading

    from brvm_alpha.notes import research as rs
    from brvm_alpha.ui import server as S

    def no_network(*a, **k):
        raise AssertionError("aucune requête réseau dans les tests")

    monkeypatch.setattr(rs, "_requests_transport", no_network)

    class Services(FakeServices):
        def evaluate_indices(self, asof):
            ev = pd.DataFrame({
                "label": ["BRVM Composite"], "date": [T_BOC], "level": [492.89], "ret_1m": [-0.06], "ret_3m": [-0.05],
                "ret_12m": [0.43], "ytd": [0.42], "per": [15.8], "yield_pct": [7.1], "stance": ["SOUS-PONDÉRER"],
                "confidence": [0.6], "composite": [-0.7], "composite_ex_notes": [-0.5], "z_notes": [-1.6],
                "notes_n": [1], "notes_score": [-0.8], "reasons": [["Notes : score −0,800"]],
                "notes_detail": [[{"note_id": "ab" * 20, "title": "Composite <b>prudence</b>", "targets": ["IDX:BRVM-C"],
                                   "note_score": -0.8, "part": -0.8}]],
            }, index=pd.Index(["IDX:BRVM-C"], name="index"))
            return ev, True

    services = Services(tmp_path)
    services.clock = lambda: UI_NOW
    srv = S.make_server("127.0.0.1", 0, services=services)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    try:
        yield srv
    finally:
        srv.shutdown()
        srv.shutdown_jobs()
        srv.server_close()


def test_ui_pages_show_the_dated_line_tables_and_filters(ui_direct):
    st = NoteStore(ui_direct.services.notes_root)
    st.add(bearish_index_note(), now=SUNDAY)
    st.add(ag_cancel_note("ETIT", SUNDAY, author="auto", published="2026-10-23",
                          url="https://www.brvm.org/sites/default/files/annulation_ago.pdf"), now=SUNDAY)
    for path in ("/", "/notes", "/indices", "/portefeuille"):
        status, _, body = call(ui_direct, "GET", path)
        assert status == 200, body[:400]
        assert line_fields(body) == ("22/11/2026 20:30", "23/11/2026", 2, 1, 1), path
    status, _, body = call(ui_direct, "GET", "/notes")
    for piece in ("Notes en vigueur à la séance d'application", "Notes manuelles en vigueur (1)",
                  "Notes automatiques en vigueur (1)", "Les 10 notes les plus positives",
                  "Les 10 notes les plus négatives", "Filtres de risque actifs issus des notes",
                  "achats bloqués", "Composante « notes » de chaque indice", "Journal des notes",
                  "Composite &lt;b&gt;prudence&lt;/b&gt;", "notes archive "):
        assert piece in body, piece
    assert "<b>prudence</b>" not in body
    assert "nan" not in re.sub(r"<[^>]+>", " ", body).split()  # aucune valeur manquante affichée « nan »
    # Lien vers la source : http(s) seulement, sans référent.
    assert ('<a href="https://www.brvm.org/sites/default/files/annulation_ago.pdf" rel="noopener noreferrer nofollow" '
            'target="_blank">document</a>') in body
    assert "Aucune note de score positif en vigueur." in body
    status, _, body = call(ui_direct, "GET", "/indices")
    assert "Notes (z)" in body and "−1,60" in body
    # Sans journal : texte clair, pas d'erreur.
    for f in Path(ui_direct.services.notes_root).glob("*.jsonl"):
        f.unlink()
    ui_direct.services._store = None
    status, _, body = call(ui_direct, "GET", "/")
    assert status == 200 and "aucun journal" in body


def test_ui_services_pass_now_in_direct_mode_and_nothing_for_a_past_date(tmp_path, monkeypatch):
    import brvm_alpha.report as report
    from brvm_alpha.ui import server as S

    seen: dict[str, object] = {}
    svc = S.Services(notes_root=tmp_path / "notes", panel_dir=tmp_path / "panel", reports_dir=tmp_path / "reports",
                     clock=lambda: UI_NOW)
    monkeypatch.setattr(svc, "last_session", lambda: T_BOC)
    NoteStore(tmp_path / "notes").add(bearish_index_note(), now=SUNDAY)
    monkeypatch.setattr(ie, "load_panels", lambda *a, **k: {})
    monkeypatch.setattr(ie, "evaluate_indices", lambda **k: seen.__setitem__("indices", k["notes_known_at"]) or
                        pd.DataFrame())
    monkeypatch.setattr(ie, "index_dossier", lambda code, **k: seen.__setitem__("dossier", k["notes_known_at"]) or {})
    monkeypatch.setattr(R, "recommend", lambda asof, capital, **k: seen.__setitem__("recommend", k["notes_known_at"]))
    monkeypatch.setattr(report, "build_report",
                        lambda asof, capital, out, **k: seen.__setitem__("report", k["notes_known_at"]) or Path(out))
    monkeypatch.setattr(cli, "explain_symbol",
                        lambda symbol, asof, **k: seen.__setitem__("explain", k["notes_known_at"]) or {})
    monkeypatch.setattr(svc, "strategy_panels", lambda: {})
    log: list[str] = []
    past = pd.Timestamp("2026-11-13")
    for asof, expected in ((T_BOC, UI_NOW), (past, None)):
        seen.clear()
        svc.evaluate_indices(asof)
        svc.index_dossier("IDX:BRVM-C", asof)
        svc.explain("SNTS", asof, None)
        svc.recommend(asof=asof, capital=1e7, holdings=None, cash=None, variant=None, n_boot=1000, log=log.append)
        svc.build_report(asof=asof, capital=1e7, log=log.append)
        assert seen == {k: expected for k in ("indices", "dossier", "explain", "recommend", "report")}, asof
    assert any("mode direct" in x for x in log) and any("mode historique" in x for x in log)
    assert svc.notes_instant(None) == UI_NOW and svc.notes_instant(past) is None
    # État des notes : mode direct par défaut, historique pour une date passée.
    assert line_fields(svc.notes_status()["line"]) == ("22/11/2026 20:30", "23/11/2026", 1, 1, 0)
    assert svc.notes_status(past)["mode"] == "historique"


def test_ui_research_checkbox_reads_documents_with_a_fake_function(ui_direct, fake_enrich):
    status, _, body = call(ui_direct, "GET", "/recherche")
    assert status == 200 and 'name="lire_documents"' in body and 'name="max_documents"' in body
    assert "lire le contenu des documents récents" in body
    form = {"_jeton": token(ui_direct), "mode": "hors_ligne", "max_requetes": "10", "confirmer": "oui"}
    # Case cochée, nombre invalide : refus avant tout lancement.
    status, _, body = call(ui_direct, "POST", "/recherche/lancer", {**form, "lire_documents": "oui",
                                                                    "max_documents": "999"})
    assert status == 400 and "nombre maximal de documents" in body and not fake_enrich
    status, h, _ = call(ui_direct, "POST", "/recherche/lancer", {**form, "lire_documents": "oui", "max_documents": "7"})
    assert status == 303 and h["location"] == "/recherche"
    job = wait_job(ui_direct, "recherche")
    assert job.status == "terminé", job.snapshot()
    assert len(fake_enrich) == 1 and fake_enrich[0]["max_docs"] == 7 and fake_enrich[0]["offline"] is True
    assert job.result["documents"]["bilan"]["n_read"] == 3
    log = "\n".join(job.snapshot()["journal"])
    assert "lecture du contenu d'au plus 7 document(s)" in log and "3 lu(s)" in log and "à lire à la main" in log
    status, _, body = call(ui_direct, "GET", "/recherche")
    assert "Lecture du contenu des documents (dernière recherche)" in body and "2 note(s) enrichie(s)" in body
    # Case non cochée : la fonction n'est pas appelée.
    status, _, _ = call(ui_direct, "POST", "/recherche/lancer", form)
    assert status == 303
    job2 = wait_job_after(ui_direct, job.id)
    assert job2.status == "terminé" and job2.result["documents"] is None and len(fake_enrich) == 1


def wait_job_after(srv, previous_id: str, timeout: float = 120.0):
    import time

    deadline = time.time() + timeout
    while time.time() < deadline:
        job = srv.jobs.latest("recherche")
        if job is not None and job.id != previous_id and job.done.is_set():
            return job
        time.sleep(0.05)
    raise AssertionError("seconde recherche non terminée")


# ---------------------------------------------------------------------------
# Rapport HTML : sections ordre, indices et notes
# ---------------------------------------------------------------------------


def test_report_sections_in_direct_and_historical_modes(synth, tmp_path):  # noqa: F811
    root = tmp_path / "notes"
    st = NoteStore(root)
    base = _render(synth, recommend_kwargs={"explanations": False, "comparison": False, "variant": "REF"})
    od = None
    for sym in synth["panels"]["close"].columns:
        if f"<b>{sym}</b>" in _section(base.html, "ordre"):
            od = sym
            break
    assert od is not None
    auto = st.add(ag_cancel_note(od, SAT, author="auto", published="2024-08-20",
                                 url="https://www.brvm.org/sites/default/files/annulation.pdf"), now=SAT)
    st.add(Note(title="<script>alert(1)</script> avis", text="prudence", targets=[synth["panels"]["close"].columns[5]],
                stance="baissier", conviction=4, url="https://exemple.test/x", created_at=SAT,
                analysis={"targets": [synth["panels"]["close"].columns[5]], "event_type": "MANUAL", "score": -0.6,
                          "confidence": 0.7}), now=SAT)
    kw = dict(notes_root=root, recommend_kwargs={"explanations": False, "comparison": False, "variant": "REF"})
    direct = _render(synth, notes_known_at=SAT_KNOWN, **kw)
    assert direct.statuts()["notes"] == "ok" and direct.statuts()["ordre"] == "ok"
    notes, ordre = _section(direct.html, "notes"), _section(direct.html, "ordre")
    assert line_fields(notes) == ("24/08/2024 12:00", "26/08/2024", 2, 1, 1)
    assert line_fields(ordre) == ("24/08/2024 12:00", "26/08/2024", 2, 1, 1)
    for piece in ("Filtres de risque actifs issus des notes (1)", "Notes manuelles en vigueur (1)",
                  "Notes automatiques en vigueur (1)", "notes les plus négatives", "Aucune note de score positif",
                  "achats bloqués", f"notes archive {auto[:12]}", "Dernières notes du journal"):
        assert piece in notes, piece
    # Lien vers www.brvm.org seulement ; autre adresse en texte ; contenu échappé.
    assert '<a class="src" href="https://www.brvm.org/sites/default/files/annulation.pdf" rel="noopener noreferrer">' in notes
    assert '<span class="muted small url">https://exemple.test/x</span>' in notes and 'href="https://exemple' not in notes
    assert "&lt;script&gt;alert(1)&lt;/script&gt; avis" in notes and "<script>alert(1)" not in direct.html
    # Journal mêlant notes avec et sans avis : jamais de « nan » affiché (colonnes de textes de pandas 3).
    words = re.sub(r"<[^>]+>", " ", notes).split()
    assert "nan" not in words and "avis baissier 4/5" in notes and "sans avis" in notes
    assert "Achats bloqués par les notes de l&#x27;analyste et effet sur les poids" in ordre
    assert "ACHAT BLOQUÉ par une note" in ordre and f"<b>{od}</b>" in ordre
    for m in re.finditer(r"""<a\s[^>]*href\s*=\s*["']([^"']+)["'][^>]*>""", direct.html):
        url, tag = m.group(1), m.group(0)
        assert url.startswith("#") or (url.startswith("https://www.brvm.org/") and 'class="src"' in tag), tag
    # Mode historique (défaut de render_report) : même journal, aucune note en vigueur à la date des données.
    hist = _render(synth, **kw)
    hnotes = _section(hist.html, "notes")
    assert "mode historique" in hnotes and "0 en vigueur" in hnotes and "Aucune note en vigueur" in hnotes
    assert "ACHAT BLOQUÉ par une note" not in hist.html
    assert "Dernières notes du journal" in hnotes  # le journal reste listé
