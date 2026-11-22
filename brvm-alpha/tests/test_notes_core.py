"""Tests du noyau « Notes de l'analyste » : modèle, journal, entités, lexique, analyse.

Hors ligne : fixtures dans ``tests/fixtures/notes/core_*`` (titres réels des listes
brvm.org relevés dans ``docs/research/annexes-07/data``, communiqué réel d'ETI, et
reconstitutions signalées comme telles). Le journal réel ``data/notes`` n'est jamais
touché : chaque test utilise ``tmp_path``.
"""

from __future__ import annotations

import csv
import json
import re
import threading
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from brvm_alpha.notes import analyze as an
from brvm_alpha.notes import entities as en
from brvm_alpha.notes import lexicon as lx
from brvm_alpha.notes import model as md
from brvm_alpha.notes.model import Note, NoteAnalysis, SessionCalendar, first_tradable_session, normalize_target
from brvm_alpha.notes.store import NoteStore

FIX = Path(__file__).parent / "fixtures" / "notes"
REAL_SESSIONS = Path(__file__).resolve().parents[1] / "data" / "panel" / "sessions.parquet"


def load_fixture(name: str) -> str:
    """Texte d'une fixture, sans les lignes de commentaire (« # … »)."""
    lines = (FIX / name).read_text(encoding="utf-8").splitlines()
    return "\n".join(ln for ln in lines if not ln.startswith("#"))


def real_titles() -> list[dict[str, str]]:
    with (FIX / "core_titres_reels.csv").open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def biz_calendar(start: str = "2026-09-01", end: str = "2026-12-31") -> pd.DatetimeIndex:
    """Calendrier synthétique : jours ouvrés hors 01/11, 15/11 et 25/12."""
    days = pd.bdate_range(start, end)
    return days[~days.strftime("%m-%d").isin(["11-01", "11-15", "12-25"])]


# ---------------------------------------------------------------------------
# Modèle : codes de cibles
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, code",
    [
        ("snts", "SNTS"), ("  Snts ", "SNTS"), ("Sonatel", "SNTS"), ("Orange CI", "ORAC"),
        ("BRVM 30", "IDX:BRVM-30"), ("brvm-30", "IDX:BRVM-30"), ("brvm30", "IDX:BRVM-30"),
        ("IDX:brvm-30", "IDX:BRVM-30"), ("BRVM Composite", "IDX:BRVM-C"), ("BRVM-C", "IDX:BRVM-C"),
        ("Prestige", "IDX:PRESTIGE"), ("BRVM Principal", "IDX:PRINCIPAL"),
        ("Composite Total Return", "IDX:BRVM-C-TR"), ("BRVM - TELECOMMUNICATIONS (base 2025)", "IDX:SECT:TEL"),
        ("BRVM - FINANCES (base 1999)", "IDX:SECT:FIN"), ("idx:sect:fin", "IDX:SECT:FIN"),
        ("Côte d'Ivoire", "PAYS:CI"), ("cote divoire", "PAYS:CI"), ("CI", "PAYS:CI"), ("pays:sn", "PAYS:SN"),
        ("Sénégal", "PAYS:SN"), ("Burkina", "PAYS:BF"), ("Abidjan", "PAYS:CI"), ("GW", "PAYS:GW"),
        ("SECT:fin", "SECT:FIN"), ("secteur:Télécommunications", "SECT:TEL"),
        ("theme:taux BCEAO", "THEME:TAUX_BCEAO"), ("cacao", "THEME:CACAO"), ("THEME:Pétrole", "THEME:PETROLE"),
        ("marché", "MARCHE"), ("BRVM", "MARCHE"),
    ],
)
def test_normalize_target_canonical_codes(raw, code):
    assert normalize_target(raw) == code


def test_normalize_target_unknown_and_strict():
    assert normalize_target("xyz123") is None
    assert normalize_target("") is None
    with pytest.raises(ValueError):
        normalize_target("xyz123", strict=True)
    # thème libre accepté avec un préfixe explicite (slug)
    assert normalize_target("theme:cours du fer") == "THEME:COURS_DU_FER"


def test_normalize_targets_list_and_string_dedup():
    assert md.normalize_targets("snts; BRVM 30, sonatel | pays:ci") == ["SNTS", "IDX:BRVM-30", "PAYS:CI"]
    assert md.normalize_targets(["Prestige", "IDX:PRESTIGE", None, "inconnu!"]) == ["IDX:PRESTIGE"]


def test_target_helpers_kind_label_index_names():
    assert md.target_kind("IDX:SECT:FIN") == "index"
    assert md.target_kind("PAYS:ML") == "country"
    assert md.index_names("IDX:SECT:FIN")[0] == "BRVM - SERVICES FINANCIERS (base 2025)"
    assert md.index_names("IDX:BRVM-C") == ("BRVM COMPOSITE",)
    assert md.target_label("PAYS:NE") == "Niger"
    assert md.target_symbols("PAYS:BF") == ["BOABF", "CBIBF", "ONTBF"]


# ---------------------------------------------------------------------------
# Modèle : Note, sérialisation, identifiant
# ---------------------------------------------------------------------------


def _note(**kw) -> Note:
    base = dict(
        title="SONATEL SN : Communiqué de presse", text="Résultat net en hausse.", author="auto",
        source="brvm_list", url="https://www.brvm.org/sites/default/files/x.pdf",
        created_at="2026-11-17T19:00:00Z", published_at="2026-11-17T18:18:00Z",
    )
    base.update(kw)
    return Note(**base)


def test_note_defaults_and_validation():
    n = Note(title="Note libre", text="Rien", created_at="2026-11-18T10:00:00Z")
    assert n.author == "analyste" and n.source == "manual" and n.status == "active"
    assert n.published_at == n.created_at and n.horizon_days == 20 and n.version == 1
    assert len(n.note_id) == 40 and all(c in "0123456789abcdef" for c in n.note_id)
    with pytest.raises(ValueError):
        Note(title="x", author="robot")
    with pytest.raises(ValueError):
        Note(title="x", source="twitter")
    with pytest.raises(ValueError):
        Note(title="x", conviction=7)
    with pytest.raises(ValueError):
        Note(title="x", stance="peut-être")
    with pytest.raises(ValueError):
        Note(title="", text="  ")


def test_note_stance_normalization():
    assert Note(title="x", stance="Achat").stance == "haussier"
    assert Note(title="x", stance="bearish").stance == "baissier"
    assert Note(title="x", stance="Neutre").stance == "neutre"
    assert Note(title="x", stance=None).stance is None


def test_note_roundtrip_json():
    n = _note(targets=["sonatel", "brvm 30"], tags=["résultats"], stance="haussier", conviction=4)
    d = n.to_dict()
    assert d["created_at"] == "2026-11-17T19:00:00+00:00"
    assert d["first_tradable_session"] == "2026-11-18"
    line = n.to_json()
    back = Note.from_json(line)
    assert back == n and back.note_id == n.note_id
    assert json.loads(line)["targets"] == ["SNTS", "IDX:BRVM-30"]


def test_note_analysis_roundtrip():
    a = an.analyze_text("Résultat net : 245,3 milliards FCFA contre 210,1 milliards en 2024, soit +16,8 %")
    d = a.to_dict()
    json.dumps(d)  # sérialisable
    b = NoteAnalysis.from_dict(d)
    assert b.to_dict() == d
    assert NoteAnalysis.from_dict({"score": 0.5, "inconnu": 1}).score == 0.5


def test_note_id_is_stable():
    a, b = _note(), _note(text="Texte corrigé", created_at="2026-11-19T08:00:00Z")
    assert a.note_id == b.note_id  # même source, même URL, même titre : même pièce
    c = _note(url="https://www.brvm.org/sites/default/files/y.pdf")
    assert c.note_id != a.note_id
    m1 = Note(title="Avis", text="Haussier sur SNTS", created_at="2026-11-18T10:00:00Z")
    m2 = Note(title="Avis", text="Haussier sur SNTS", created_at="2026-11-18T10:00:00Z")
    m3 = Note(title="Avis", text="Haussier sur SNTS", created_at="2026-11-18T11:00:00Z")
    assert m1.note_id == m2.note_id != m3.note_id
    assert md.make_note_id("manual", title="Été", text="x") == md.make_note_id("manual", title="ete ", text="x")


def test_published_precision_date_only():
    n = _note(published_at="2026-11-16")
    assert n.published_precision == "date"
    assert n.known_at == pd.Timestamp("2026-11-17T19:00:00Z")  # created_at après la fin de journée
    n2 = _note(published_at="2026-11-16T00:00:00+00:00", created_at="2026-11-16T05:00:00Z")
    assert n2.published_precision == "date"
    assert n2.known_at == pd.Timestamp("2026-11-16T23:59:59.999999Z")


def test_french_date_parsing_is_day_first():
    assert md.to_utc("02/09/2026") == pd.Timestamp("2026-09-02", tz="UTC")
    assert md.to_utc("17/11/2026 18h18") == pd.Timestamp("2026-11-17T18:18", tz="UTC")


# ---------------------------------------------------------------------------
# Modèle : première séance négociable
# ---------------------------------------------------------------------------


def test_first_tradable_cutoff_0900_utc():
    cal = biz_calendar()
    assert first_tradable_session("2026-11-17T08:59:00Z", cal) == pd.Timestamp("2026-11-17")
    assert first_tradable_session("2026-11-17T09:00:00Z", cal) == pd.Timestamp("2026-11-18")
    assert first_tradable_session("2026-11-17T18:18:00Z", cal) == pd.Timestamp("2026-11-18")
    # Heure locale d'Abidjan = UTC ; un horodatage avec fuseau est converti.
    assert first_tradable_session("2026-11-17T10:30:00+02:00", cal) == pd.Timestamp("2026-11-17")


def test_first_tradable_weekend_holiday_and_date_only():
    cal = biz_calendar()
    assert first_tradable_session("2026-11-20T18:00:00Z", cal) == pd.Timestamp("2026-11-23")  # vendredi soir
    assert first_tradable_session("2026-11-21T07:00:00Z", cal) == pd.Timestamp("2026-11-23")  # samedi
    assert first_tradable_session("2026-12-24T16:00:00Z", cal) == pd.Timestamp("2026-12-28")  # 25/12 férié
    assert first_tradable_session("2026-11-16", cal) == pd.Timestamp("2026-11-17")  # date seule : après séance
    assert first_tradable_session("2026-11-16T07:00:00Z", cal) == pd.Timestamp("2026-11-16")
    assert first_tradable_session(None, cal) is None


def test_first_tradable_with_session_gaps_and_beyond_calendar():
    df = pd.DataFrame({
        "date": pd.to_datetime(["2021-05-05", "2021-05-06", None, None, "2021-06-25", "2021-06-28"]),
        "gap_start": pd.to_datetime([None, None, "2021-05-06", "2021-05-06", None, None]),
        "gap_end": pd.to_datetime([None, None, "2021-06-25", "2021-06-25", None, None]),
    })
    cal = SessionCalendar(df)
    # Dans une lacune de BOC, les jours ouvrés font foi (lundi 10/05/2021).
    assert first_tradable_session("2021-05-07T18:00:00Z", cal) == pd.Timestamp("2021-05-10")
    # Au-delà de la dernière séance connue : jours ouvrés (le 29/06/2021 est un mardi).
    assert first_tradable_session("2021-06-28T12:00:00Z", cal) == pd.Timestamp("2021-06-29")
    assert cal.sessions_between("2021-06-24", "2021-06-28") == 2


@pytest.mark.skipif(not REAL_SESSIONS.exists(), reason="panel absent")
def test_first_tradable_real_calendar():
    from brvm_alpha.data.store import load_sessions

    sessions = load_sessions(REAL_SESSIONS.parent)
    # Avis LNBB (D) : la BRVM était fermée le vendredi 07/08/2026 (fête nationale ivoirienne).
    assert first_tradable_session("2026-08-06T18:00:00Z", sessions) == pd.Timestamp("2026-08-10")
    assert first_tradable_session("2026-11-17T18:18:00Z", sessions) == pd.Timestamp("2026-11-18")
    # Après la fin du panel (20/11/2026) : jours ouvrés.
    assert first_tradable_session("2026-11-20T18:00:00Z", sessions) == pd.Timestamp("2026-11-23")


# ---------------------------------------------------------------------------
# Journal append-only
# ---------------------------------------------------------------------------


def test_store_add_get_idempotent(tmp_path):
    st = NoteStore(tmp_path / "notes", calendar=biz_calendar())
    n = _note()
    nid = st.add(n, now="2026-11-17T19:00:00Z")
    assert st.add(n, now="2026-11-17T20:00:00Z") == nid  # doublon : rien n'est écrit
    assert len(st) == 1 and nid in st
    assert (tmp_path / "notes" / "notes.jsonl").read_text(encoding="utf-8").count("\n") == 1
    got = st.get(nid)
    assert got.title == n.title and got.recorded_at == pd.Timestamp("2026-11-17T19:00:00Z")
    with pytest.raises(KeyError):
        st.get("0" * 40)


def test_store_is_append_only_and_versions(tmp_path):
    st = NoteStore(tmp_path, calendar=biz_calendar())
    nid = st.add(_note(), analyze=True, now="2026-11-17T19:00:00Z")
    before = st.path.read_bytes()
    v2 = st.update(nid, title="SONATEL SN : Résultats annuels 2025", now="2026-11-18T10:00:00Z")
    after = st.path.read_bytes()
    assert after.startswith(before)  # la première ligne n'est jamais réécrite
    assert after.count(b"\n") == 2 and v2.version == 2
    assert [v.version for v in st.versions(nid)] == [1, 2]
    assert st.get(nid, version=1).title == "SONATEL SN : Communiqué de presse"
    assert st.get(nid).analysis["event_type"] == "RES_ANNUAL"  # analyse relancée (titre modifié)
    with pytest.raises(ValueError):
        st.update(nid, note_id="x")
    with pytest.raises(ValueError):
        st.update(nid, created_at="2020-01-01")
    # Sans changement effectif : aucune écriture.
    st.update(nid, title="SONATEL SN : Résultats annuels 2025", now="2026-11-18T11:00:00Z")
    assert st.path.read_bytes().count(b"\n") == 2


def test_store_update_published_at_recomputes_session(tmp_path):
    st = NoteStore(tmp_path, calendar=biz_calendar())
    nid = st.add(_note(), now="2026-11-17T19:00:00Z")
    assert st.get(nid).first_tradable_session == pd.Timestamp("2026-11-18")
    st.update(nid, published_at="2026-11-17T07:30:00Z", now="2026-11-18T09:30:00Z")
    assert st.get(nid).first_tradable_session == pd.Timestamp("2026-11-17")


def test_store_asof_no_lookahead(tmp_path):
    st = NoteStore(tmp_path, calendar=biz_calendar())
    # Note rétro-collectée : publiée le 10/11, saisie le 17/11.
    late = _note(title="BOA MALI : Communiqué", url="https://www.brvm.org/a.pdf",
                 published_at="2026-11-10T18:00:00Z", created_at="2026-11-17T08:00:00Z")
    st.add(late, now="2026-11-17T08:00:00Z")
    # Note publiée le 17/11 à 18h18, saisie à 19h.
    nid = st.add(_note(), now="2026-11-17T19:00:00Z")
    assert st.asof("2026-11-12").empty  # créée après : invisible (pas d'anticipation)
    assert len(st.asof("2026-11-12", strict=False)) == 1  # reconstitution d'historique
    assert list(st.asof("2026-11-17T18:30:00Z")["title"]) == ["BOA MALI : Communiqué"]
    assert len(st.asof("2026-11-17")) == 2  # date seule = fin de journée
    st.update(nid, title="Titre corrigé", now="2026-11-19T10:00:00Z")
    assert set(st.asof("2026-11-18")["title"]) == {"BOA MALI : Communiqué", "SONATEL SN : Communiqué de presse"}
    assert "Titre corrigé" in set(st.asof("2026-11-19T12:00:00Z")["title"])


def test_store_asof_date_only_publication_is_end_of_day(tmp_path):
    st = NoteStore(tmp_path, calendar=biz_calendar())
    st.add(_note(published_at="2026-11-16", created_at="2026-11-16T06:00:00Z"), now="2026-11-16T06:00:00Z")
    assert st.asof("2026-11-16T12:00:00Z").empty
    assert len(st.asof("2026-11-16")) == 1
    assert st.list()["first_tradable_session"].iloc[0] == pd.Timestamp("2026-11-17")


def test_store_archive_list_filters(tmp_path):
    st = NoteStore(tmp_path, calendar=biz_calendar())
    a = st.add(_note(), analyze=True, now="2026-11-17T19:00:00Z")
    b = st.add(Note(title="Vue BRVM 30", text="Indice BRVM 30 cher", targets=["BRVM 30"], stance="baissier",
                    conviction=2, created_at="2026-11-18T07:00:00Z"), analyze=True, now="2026-11-18T07:00:00Z")
    assert set(st.list(target="Sonatel")["note_id"]) == {a}
    assert set(st.list(target="IDX:BRVM-30")["note_id"]) == {b}
    assert set(st.list(source="manual")["note_id"]) == {b}
    assert set(st.list(since="2026-11-18")["note_id"]) == {b}
    assert set(st.list(until="2026-11-17")["note_id"]) == {a}
    st.archive(a, reason="doublon", now="2026-11-20T10:00:00Z")
    assert set(st.list()["note_id"]) == {b}
    allv = st.list(status=None)
    assert set(allv["note_id"]) == {a, b}
    assert "archive:doublon" in st.get(a).tags
    assert a not in set(st.asof("2026-11-21")["note_id"])
    assert a in set(st.asof("2026-11-19")["note_id"])  # encore active à cette date
    assert a in set(st.asof("2026-11-21", include_archived=True)["note_id"])
    assert st.frame(all_versions=True).shape[0] == 3


def test_store_tolerates_corrupted_line_and_export(tmp_path):
    st = NoteStore(tmp_path, calendar=biz_calendar())
    st.add(_note(), analyze=True, now="2026-11-17T19:00:00Z")
    with st.path.open("ab") as fh:
        fh.write(b'{"note_id": "abc", "title": "coup')  # écriture interrompue
    st2 = NoteStore(tmp_path)
    assert len(st2) == 1 and st2.errors
    st2.add(Note(title="Après incident", text="x", created_at="2026-11-18T07:00:00Z"), now="2026-11-18T07:00:00Z")
    lines = st2.path.read_text(encoding="utf-8").splitlines()
    assert lines[1].startswith('{"note_id": "abc"')  # la ligne partielle reste, intacte
    assert len(NoteStore(tmp_path)) == 2
    out = st2.export_markdown(tmp_path / "export" / "notes.md")
    md_text = out.read_text(encoding="utf-8")
    assert "# Notes de l'analyste" in md_text and "SONATEL SN" in md_text
    assert not re.search(r"\b(?:nan|None|NaT)\b", md_text)
    assert not st2.lock_path.exists()


def test_store_concurrent_writers(tmp_path):
    st = NoteStore(tmp_path)
    errors: list[Exception] = []

    def worker(i: int) -> None:
        try:
            s = NoteStore(tmp_path)
            for j in range(5):
                s.add(Note(title=f"note {i}-{j}", text="x", created_at="2026-11-18T07:00:00Z"),
                      now="2026-11-18T07:00:00Z")
        except Exception as exc:  # pragma: no cover
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    lines = st.path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 20 and all(json.loads(ln)["note_id"] for ln in lines)


# ---------------------------------------------------------------------------
# Entités
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("row", real_titles(), ids=lambda r: r["titre"][:40])
def test_real_titles_event_type_and_target(row):
    a = an.analyze_text("", row["titre"])
    assert a.event_type == row["type_attendu"]
    assert (a.primary_target or "") == row["cible_attendue"]


@pytest.mark.parametrize(
    "text, expected",
    [
        ("SONATEL SN : Communiqué", ["SNTS"]),
        ("Orange Côte d'Ivoire publie ses résultats", ["ORAC"]),
        ("Société Générale CI et SGBCI", ["SGBC"]),
        ("Ecobank Transnational Incorporated TOGO : Communiqué de presse", ["ETIT"]),
        ("Ecobank Côte d'Ivoire", ["ECOC"]),
        ("TotalEnergies Marketing Sénégal et Total CI", ["TTLS", "TTLC"]),
        ("La SIB et Coris Bank", ["SIBC", "CBIBF"]),
        ("NSIA Banque, BOA Niger, Bank of Africa Bénin", ["NSBC", "BOAN", "BOAB"]),
        ("AFRICA GLOBAL LOGISTICS CÔTE D'IVOIRE (symbole : SDSC)", ["SDSC"]),
        ("ERIUM CI (Ex AIR LIQUIDE CI)", ["SIVC"]),
    ],
)
def test_entity_linking_companies(text, expected):
    assert en.link_entities(text).by_kind("symbol") == expected


def test_entity_linking_false_positives():
    links = en.link_entities(
        "Le bateau (boat) est possible ; le total des actifs ; Orange Money ; le Nigeria ; "
        "le principal actionnaire ; matériaux composites ; Or, la marge brute ; Dupont et Cie."
    )
    assert links.targets == []
    assert "Orange Money" in links.ambiguous
    # « BOA » seul reste ambigu, « BOA Mali » est lié sans lier le pays séparément.
    l2 = en.link_entities("BOA Mali progresse, BOA aussi.")
    assert l2.targets == ["BOAM"] and "BOA" in l2.ambiguous
    assert en.link_entities("La CIE CI et la CIE").targets == ["CIEC"]
    assert en.link_entities("TotalEnergies seul").targets == []


def test_entity_linking_indices_countries_sectors_themes():
    links = en.link_entities(
        "Le BRVM Composite et la BRVM 30 montent ; l'indice des télécommunications recule. "
        "Les banques ivoiriennes et sénégalaises profitent de la baisse des taux directeurs de la BCEAO ; "
        "à Dakar, le cours du cacao et le prix de l'or inquiètent, ainsi que la situation sécuritaire au Burkina."
    )
    assert links.by_kind("index") == ["IDX:BRVM-C", "IDX:BRVM-30", "IDX:SECT:TEL"]
    assert set(links.by_kind("country")) == {"PAYS:CI", "PAYS:SN", "PAYS:BF"}
    assert links.by_kind("sector") == ["SECT:FIN"]
    assert {"THEME:TAUX_BCEAO", "THEME:CACAO", "THEME:OR", "THEME:SECURITE"} <= set(links.by_kind("theme"))
    assert links.terms["PAYS:CI"] == ["ivoiriennes"]


def test_entity_linking_returns_surface_forms_and_signature_place():
    links = en.link_entities("La SOCIÉTÉ GÉNÉRALE CÔTE D'IVOIRE annonce.", title="SGBC : avis")
    assert links.terms["SGBC"] == ["SGBC", "SOCIÉTÉ GÉNÉRALE CÔTE D'IVOIRE"]
    assert links.in_title("SGBC")
    sig = en.link_entities("ETI informe ses actionnaires.\nLomé, le 23 octobre 2026")
    assert sig.targets == ["ETIT"]  # lieu de signature ignoré
    assert en.link_entities("Les affaires reprennent à Lomé.").targets == ["PAYS:TG"]


def test_entity_fuzzy_issuer_prefix():
    assert en.link_entities("", "VIVO ENERY CÔTE D'IVOIRE : Rapport d'activités").targets == ["SHEC"]
    assert en.link_entities("", "BENABE CI : Avis de convocation").targets == ["BNBC"]
    assert en.link_entities("", "Avis : Transactions sur dossier").targets == []


def test_alias_table_built_from_real_panel_names():
    table = en.alias_table()
    names = en.panel_names()
    for sym, labels in names.items():
        linked = set()
        for lab in labels:
            linked |= set(en.link_entities(lab).by_kind("symbol"))
        assert sym in linked, (sym, labels)
    assert "bankofafrica" in table.collisions  # libellé partagé par six filiales : ambigu


def test_every_usual_alias_is_verified():
    rep = en.verify_aliases()
    assert rep["symbol_in_panel"].all()
    unverified = rep[~rep["in_panel_name"] & (rep["evidence"] == "")]
    assert unverified.empty, unverified[["alias", "symbol"]].to_dict("records")


# ---------------------------------------------------------------------------
# Lexique et types d'événements
# ---------------------------------------------------------------------------


def test_lexicon_contrast_example_from_doc07():
    # Doc 07 §3.4 : « +2 − 0,5 = +1,5 ».
    hits = lx.scan("Oragroup accroît son bénéfice de 14 %, malgré le recul des crédits")
    t = lx.tone_from_hits(hits)
    assert t["P"] - t["N"] == pytest.approx(1.5)
    assert t["tone"] == pytest.approx(1.5 / 3.5)
    assert "concession ×0,5" in hits[-1].modifiers


def test_lexicon_negation_rules():
    assert lx.tone_from_hits(lx.scan("Pas de dividende au titre de 2025"))["tone"] == pytest.approx(-2 / 3)
    neg = lx.scan("La société n'a pas constaté de baisse du résultat net")
    assert neg[0].weight == 2 and "négation" in neg[0].modifiers
    assert lx.tone_from_hits(lx.scan("Sans impact sur le résultat net"))["tone"] == 0
    both = lx.scan("Non seulement le résultat net progresse, mais le dividende est relevé")
    assert [h.weight for h in both] == [2, 2]  # « non seulement … mais » n'est ni négation ni concession


def test_lexicon_intensity_and_attenuation():
    assert lx.scan("Résultat net en forte hausse")[0].weight == pytest.approx(3.0)
    assert lx.scan("Résultat net en légère hausse")[0].weight == pytest.approx(1.0)
    assert lx.scan("Le bénéfice de la BIIC bondit de 64 %")[0].weight == pytest.approx(3.0)
    assert lx.scan("Bénéfice record")[0].weight == pytest.approx(2.0)  # « record » non compté deux fois


def test_lexicon_neutral_traps():
    for txt in (
        "Le déficit budgétaire de l'État se creuse",
        "Les commissaires aux comptes certifient sans réserve les comptes",
        "Comptes établis selon le principe de continuité d'exploitation",
        "Dotation aux provisions pour risques et charges",
    ):
        assert lx.tone_from_hits(lx.scan(txt))["tone"] == 0, txt


def test_lexicon_risk_terms_r3():
    for txt in (
        "Les commissaires aux comptes émettent des réserves",
        "Refus de certifier les comptes de l'exercice",
        "Une incertitude significative sur la continuité d'exploitation",
        "Les capitaux propres sont inférieurs à la moitié du capital social",
    ):
        a = an.analyze_text(txt, "SITAB CI : Communiqué")
        assert "R3" in a.risk_flags, txt
        assert a.score < 0


@pytest.mark.parametrize(
    "title, etype",
    [
        ("Communiqué – Alerte sur résultats - BOA NIGER", "PROFIT_WARNING"),
        ("AGL CI : Paiement de dividendes - Exercice 2025", "DIV_NOTICE"),
        ("SONATEL SN : Avis de convocation - Assemblée Générale Extraordinaire", "AG_CONVOCATION"),
        ("SAPH CI : Projet de résolutions - AGO 2026", "AG_RESOLUTIONS"),
        ("CIE CI : Notation financière", "RATING"),
        ("Moody's abaisse la note souveraine du Sénégal", "NOTATION_SOUVERAINE"),
        ("Coup d'État au Niger : la CEDEAO annonce des sanctions", "POLITIQUE"),
        ("Attaques jihadistes dans le nord du Burkina", "SECURITE"),
        ("Le cours du cacao au plus haut", "MATIERES_PREMIERES"),
        ("La BCEAO baisse ses taux directeurs de 25 points de base", "MACRO"),
    ],
)
def test_event_type_rules(title, etype):
    assert lx.detect_event_type(title)[0] == etype


def test_event_type_from_text_when_title_generic():
    et, origin = lx.detect_event_type("BOA NG : Communiqué de presse", "Profit warning : le résultat net 2025 baisse.")
    assert (et, origin) == ("PROFIT_WARNING", "text")


# ---------------------------------------------------------------------------
# Analyse : chiffres
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, value",
    [("1 234 567", 1234567.0), ("12,5", 12.5), ("245.3", 245.3), ("+16,8", 16.8), ("−3,4", -3.4),
     ("1.234.567", 1234567.0), ("2 910", 2910.0), ("1 834,5", 1834.5)],
)
def test_parse_fr_number(raw, value):
    assert an.parse_fr_number(raw) == pytest.approx(value)


def test_extract_rn_example_from_mission():
    a = an.analyze_text("Résultat net : 245,3 milliards FCFA contre 210,1 milliards en 2024, soit +16,8 %")
    ex = a.extracted
    assert ex["rn"] == pytest.approx(245.3e9) and ex["rn_prev"] == pytest.approx(210.1e9)
    assert ex["rn_growth"] == pytest.approx(0.168)
    assert ex["s_rn"] == pytest.approx(0.168 * 100 / 25)
    assert a.s_num == pytest.approx(0.168 * 100 / 25 / 2)
    assert a.score == pytest.approx(0.7 * a.s_num + 0.3 * a.tone)
    figs = an.extract_figures("Résultat net : 245,3 milliards FCFA contre 210,1 milliards en 2024, soit +16,8 %")
    assert figs["rn"]["consistent"] is True  # 245,3 / 210,1 − 1 = 16,75 %


@pytest.mark.parametrize(
    "text, ind, value, prev, growth",
    [
        ("Le chiffre d'affaires atteint 12,5 milliards FCFA, en hausse de 18,2 %.", "ca", 12.5e9, None, 0.182),
        ("Le résultat net s'établit à 1 234 567 FCFA, en baisse de 5 %.", "rn", 1234567.0, None, -0.05),
        ("Le PNB passe de 80 à 92 milliards FCFA.", "pnb", 92e9, 80e9, 0.15),
        ("Perte nette de 3,2 milliards FCFA contre un bénéfice de 1,6 milliard en 2024.", "rn", -3.2e9, 1.6e9, -3.0),
        ("Le bénéfice de la BIIC bondit de 64 %.", "rn", None, None, 0.64),
        ("Oragroup accroît son bénéfice de 14 %.", "rn", None, None, 0.14),
    ],
)
def test_extract_french_formats(text, ind, value, prev, growth):
    ex = an.analyze_text(text).extracted
    if value is not None:
        assert ex[ind] == pytest.approx(value)
    if prev is not None:
        assert ex[f"{ind}_prev"] == pytest.approx(prev)
    assert ex[f"{ind}_growth"] == pytest.approx(growth)


def test_ratio_percent_is_not_a_growth():
    ex = an.analyze_text("Le résultat net représente une marge nette de 12 % du chiffre d'affaires.").extracted
    assert ex.get("rn_growth") is None


def test_numeric_sentiment_replaces_lexicon_and_coverage_weighting():
    a = an.analyze_text("Le résultat net est en hausse de 30 %.")
    assert a.tone == 0  # le terme « en hausse » est remplacé par le chiffre
    assert a.extracted["s_rn"] == 1.2 and a.s_num == pytest.approx(0.6)
    # Ventes chiffrées, résultat décrit en mots : le chiffre ne doit pas dominer (doc 07 §2.2).
    b = an.analyze_text("Filtisac : les ventes bondissent de 40 %, mais le résultat courant reste déficitaire")
    assert b.s_num > 0 and b.score < 0
    assert b.components["lexical_only_indicators"] == ["rn"]


# ---------------------------------------------------------------------------
# Analyse : avis réels et reconstitués
# ---------------------------------------------------------------------------


def _agl_panels() -> dict:
    dates = pd.bdate_range("2026-07-01", "2026-10-30")
    close = pd.DataFrame({"SDSC": 2860.0}, index=dates)
    close.loc["2026-10-12":, "SDSC"] = 5000.0  # information FUTURE : ne doit pas servir
    last = pd.DataFrame({"SDSC": 92.0}, index=dates)
    last_date = pd.DataFrame({"SDSC": pd.Timestamp("2025-08-29")}, index=dates)
    value = pd.DataFrame({"SDSC": 40e6}, index=dates)
    return {"close": close, "last_div_net": last, "last_div_date": last_date, "value": value}


def test_dividend_notice_agl_reconstructed():
    txt = load_fixture("core_avis_dividende_agl.txt")
    n = Note(title="AGL CI : Paiement de dividendes - Exercice 2025", text=txt, author="auto", source="brvm_list",
             url="https://www.brvm.org/fr/esv/paiement-de-dividendes#agl", published_at="2026-10-09",
             created_at="2026-10-10T06:00:00Z")
    a = an.analyze_note(n, panels=_agl_panels(), sessions=biz_calendar())
    ex = a.extracted
    assert a.event_type == "DIV_NOTICE" and a.primary_target == "SDSC" and a.targets == ["SDSC"]
    assert n.first_tradable_session == pd.Timestamp("2026-10-12")  # date seule du vendredi -> lundi
    assert ex["div_net"] == 92.0 and ex["ex_date"] == pd.Timestamp("2026-10-26")
    assert ex["pay_date"] == pd.Timestamp("2026-10-27") and ex["record_date"] == pd.Timestamp("2026-10-27")
    assert ex["ag_date"] == pd.Timestamp("2026-09-02") and ex["ag_type"] == "AGM"
    assert ex["fiscal_period"] == "2025A"
    assert any("mardi" in w for w in a.warnings)  # coquille de l'avis (02/09/2026 = mercredi)
    # Rendement calculé au cours connu AVANT la séance négociable (2 860), pas au cours futur.
    assert ex["close_at_notice"] == 2860.0 and ex["yield_at_notice"] == pytest.approx(92 / 2860)
    assert ex["div_prev"] == 92.0 and ex["div_growth"] == 0.0 and ex["div_prev_source"] == "panel"
    assert ex["sessions_to_ex"] == 10
    assert "en dessous du seuil S1 de 4 %" in a.reading and "12/10/2026" in a.reading


def test_eti_real_communique_ag_cancel():
    a = an.analyze_text(load_fixture("core_communique_eti_annulation_ago.txt"))
    assert a.event_type == "AG_CANCEL" and a.targets == ["ETIT"]
    assert a.risk_flags == ["R2"] and a.score < -0.5
    assert a.extracted["ag_date"] == pd.Timestamp("2026-10-26")


def test_profit_warning_boan():
    a = an.analyze_text(load_fixture("core_alerte_resultats_boan.txt"))
    assert a.event_type == "PROFIT_WARNING" and a.primary_target == "BOAN" and a.targets == ["BOAN"]
    assert "R9" in a.risk_flags and a.extracted["rn_growth"] == pytest.approx(-0.62)
    assert a.score < -0.8 and a.materiality >= 0.9


def test_results_communique_full():
    txt = load_fixture("core_communique_resultats.txt")
    title, body = txt.split("\n", 1)
    a = an.analyze_text(body, title)
    ex = a.extracted
    assert a.event_type == "RES_ANNUAL" and a.targets == ["SNTS"]
    assert ex["rn_growth"] == pytest.approx(0.168) and ex["ca_growth"] == pytest.approx(0.082)
    assert ex["div_net"] == 1740 and ex["div_prev"] == 1655
    assert ex["fiscal_period"] == "2025A" and a.score > 0


@pytest.mark.parametrize(
    "title, text, flag, present",
    [
        ("SUCRIVOIRE S.A : Suspension de la cotation", "", "R1", True),
        ("Avis : Suspension de l’emprunt obligataire - TPCI.O77", "", "R1", False),  # obligation : pas R1
        ("ALIOS FINANCE (SAFCA CI) : Augmentation de capital par apport en numéraire avec DPS", "", "R5", True),
        ("BICI CÔTE D'IVOIRE : Communiqué - Augmentation de capital par incorporation de réserves", "", "R5", False),
        ("SONATEL SN : Fractionnement d'actions & Valeur théorique", "", "R8", True),
        ("CIE CI : Notation financière", "Abaissement de la notation, perspective négative.", "R4", True),
        ("CIE CI : Notation financière", "Note confirmée, perspective stable.", "R4", False),
        ("Résultats de première cotation - BRIDGE BANK GROUP COTE D'IVOIRE (BBGC)", "", "R6", True),
        ("Avis : Respect de diffusion d'information financière", "BIIC publie avec retard.", "R7", True),
    ],
)
def test_risk_flags_from_text(title, text, flag, present):
    assert (flag in an.analyze_text(text, title).risk_flags) is present


def test_r10_candidate_and_history_check():
    txt = "Le résultat net de l'exercice 2025 est en baisse de 40 %."
    n = Note(title="SAPH CI : États financiers - Exercice 2025", text=txt, author="auto", source="brvm_issuer",
             url="https://www.brvm.org/r.pdf", published_at="2026-04-28T18:00:00Z")
    a = an.analyze_note(n)
    assert a.extracted.get("r10_candidate") is True and "R10" not in a.risk_flags
    hist_without = pd.DataFrame({"published_at": [pd.Timestamp("2026-01-10", tz="UTC")],
                                 "event_type": ["RES_ANNUAL"], "all_targets": [["SPHC"]]})
    assert "R10" in an.analyze_note(n, history=hist_without).risk_flags
    hist_with = pd.DataFrame({"published_at": [pd.Timestamp("2026-03-10", tz="UTC")],
                              "event_type": ["PROFIT_WARNING"], "all_targets": [["SPHC"]]})
    assert "R10" not in an.analyze_note(n, history=hist_with).risk_flags
    old = n.copy(published_at="2025-04-28T18:00:00Z")  # avant l'instruction 01-2025 : pas de R10
    assert an.analyze_note(old, history=hist_without).risk_flags == []


# ---------------------------------------------------------------------------
# Analyse : notes de l'analyste, matérialité, confiance, lecture
# ---------------------------------------------------------------------------


def test_manual_note_bounded_and_contradiction():
    pure = Note(title="Vue SNTS", text="Conviction personnelle.", targets=["SNTS"], stance="haussier", conviction=5)
    a = an.analyze_note(pure)
    assert a.score == pytest.approx(0.8)  # jugement seul, borné à ±0,8
    assert a.event_type == "MANUAL" and not a.contradiction
    contra = Note(title="Vue BOAN", text="Alerte sur résultats : résultat net en baisse de 62 %, pas de dividende.",
                  targets=["BOAN"], stance="haussier", conviction=4)
    b = an.analyze_note(contra)
    assert b.contradiction is True
    assert "contradiction" in b.reading.lower()
    assert b.score < 0.4 and b.confidence < an.analyze_text(contra.text).confidence + 0.2
    agree = an.analyze_note(contra.copy(stance="baissier"))
    assert not agree.contradiction and agree.score < b.score


def test_materiality_company_vs_market_and_size():
    small = an.analyze_text("Le résultat net est en hausse de 5 %.", "SGBC : Communiqué")
    big = an.analyze_text("Le résultat net est en hausse de 60 %.", "SGBC : Communiqué")
    market = an.analyze_text("Le résultat net cumulé des sociétés cotées est en hausse de 60 %.", "Le marché boursier")
    assert big.materiality > small.materiality
    assert big.materiality > market.materiality
    assert 0 <= market.materiality <= 1


def test_confidence_structured_beats_regex_beats_ocr():
    txt = "Le conseil propose un dividende net de 500 FCFA contre 400 FCFA."
    title = "SGBC : Communiqué"
    base = dict(title=title, text=txt, author="auto", source="brvm_list", url="https://www.brvm.org/d")
    regex = an.analyze_note(Note(**base))
    ocr = an.analyze_note(Note(**base, tags=["ocr"]))
    struct = an.analyze_note(Note(**base), structured={"div_net": 500.0, "div_prev": 400.0})
    assert struct.confidence > regex.confidence > ocr.confidence
    assert struct.extracted["extract_conf"] == 1.0 and ocr.extracted["extract_conf"] == 0.3
    assert struct.extracted["div_growth"] == pytest.approx(0.25)


def test_absence_of_dividend_after_paying_last_year():
    a = an.analyze_text("Le conseil ne proposera pas de dividende, contre 120 FCFA l'an dernier.",
                        "BOAN : Communiqué")
    assert a.extracted.get("s_div") == -2.0 or a.score < -0.5


def test_reading_is_two_to_five_french_sentences():
    cases = [
        an.analyze_note(Note(title="SONATEL SN : Résultats annuels 2025", author="auto", source="url",
                             url="https://www.brvm.org/s.pdf", published_at="2026-11-17T18:18:00Z",
                             text=load_fixture("core_communique_resultats.txt"))),
        an.analyze_text(load_fixture("core_alerte_resultats_boan.txt")),
        an.analyze_text("", "Avis : Transactions sur dossier"),
        an.analyze_note(Note(title="Vue", text="Alerte sur résultats", targets=["BOAN"], stance="haussier",
                             conviction=3, published_at="2026-11-18T07:00:00Z")),
    ]
    for a in cases:
        n_sent = len([s for s in a.reading.split(". ") if s.strip()])
        assert 2 <= n_sent <= 5, a.reading
        assert a.reading.endswith(".")
    assert "négociable à partir de la séance du 18/11/2026" in cases[0].reading
    assert "après la coupure de 09h00" in cases[0].reading
    assert "Score" in cases[2].reading and "ton neutre" in cases[2].reading


def test_scores_are_bounded():
    for txt in ("Résultat net en hausse de 900 %", "Perte nette, liquidation, alerte sur résultats, suspension",
                "Rien à signaler"):
        a = an.analyze_text(txt, "SNTS")
        assert -1 <= a.score <= 1 and -1 <= a.tone <= 1 and -1 <= a.s_num <= 1
        assert 0 <= a.materiality <= 1 and 0.05 <= a.confidence <= 0.95


def test_store_add_with_analysis_sets_columns(tmp_path):
    st = NoteStore(tmp_path, calendar=biz_calendar())
    st.add(Note(title="Communiqué – Alerte sur résultats - BOA NIGER", text=load_fixture("core_alerte_resultats_boan.txt"),
                author="auto", source="brvm_list", url="https://www.brvm.org/pw.pdf",
                published_at="2026-11-17T18:00:00Z"), analyze=True)
    df = st.list(target="BOAN")
    assert len(df) == 1
    row = df.iloc[0]
    assert row["event_type"] == "PROFIT_WARNING" and row["risk_flags"] == ["R9"]
    assert row["score"] < 0 and isinstance(row["reading"], str) and row["reading"]
    assert np.isfinite(row["confidence"])


def test_target_symbols_point_in_time():
    eq = pd.DataFrame({
        "date": pd.to_datetime(["2026-01-05", "2026-01-05", "2026-06-01", "2026-06-01"]),
        "symbol": ["SNTS", "SGBC", "SNTS", "SGBC"],
        "sector": ["SPU", "FIN", "TEL", "FIN"],
        "compartment": ["PRESTIGE", "PRINCIPAL", "PRESTIGE", "PRESTIGE"],
    })
    assert md.target_symbols("SECT:TEL", eq, "2026-03-01") == []  # reclassement non encore connu
    assert md.target_symbols("SECT:TEL", eq, "2026-06-01") == ["SNTS"]
    assert md.target_symbols("IDX:PRESTIGE", eq, "2026-03-01") == ["SNTS"]
    assert md.target_symbols("IDX:PRESTIGE", eq, "2026-06-30") == ["SGBC", "SNTS"]
    assert md.target_symbols("IDX:BRVM-30", eq) is None  # composition absente du panel
    assert md.target_symbols("PAYS:SN", eq) == ["SNTS"]


def test_default_store_path_and_no_write_on_init(tmp_path):
    st = NoteStore()
    assert st.path == Path(__file__).resolve().parents[1] / "data" / "notes" / "notes.jsonl"
    fresh = NoteStore(tmp_path / "jamais_cree")
    assert len(fresh) == 0 and fresh.list().empty and fresh.asof("2026-11-20").empty
    assert not (tmp_path / "jamais_cree").exists()


def test_analyze_note_warns_when_asof_precedes_knowledge():
    n = _note(published_at="2026-11-17T18:18:00Z", created_at="2026-11-17T19:00:00Z")
    a = an.analyze_note(n, asof="2026-11-17T12:00:00Z")
    assert any("rétrospectif" in w for w in a.warnings)
    assert not an.analyze_note(n, asof="2026-11-18").warnings


# ---------------------------------------------------------------------------
# Régressions de l'essai réel du 22/11/2026 (brvm.org + BOC 2025-2026, notes d'analyste)
# ---------------------------------------------------------------------------


def _analyst(title: str, text: str, **kw) -> NoteAnalysis:
    n = Note(title=title, text=text, author="analyste", source="manual", created_at="2026-11-20T15:30:00Z", **kw)
    return an.analyze_note(n)


def test_regression_analyst_text_event_is_context_not_type():
    # « le fractionnement récent » dans un commentaire ne fait pas de la note un SPLIT (ni R8).
    a = _analyst("Dividende SNTS attendu en hausse",
                 "Nous anticipons un dividende Sonatel en hausse de 8 % au titre de l'exercice 2026, porté par "
                 "la croissance du chiffre d'affaires et le fractionnement récent.", stance="haussier", conviction=4)
    assert a.event_type == "MANUAL" and a.components["event_candidate"] == "SPLIT"
    assert "R8" not in a.risk_flags and a.targets == ["SNTS"]
    assert a.extracted.get("div_growth") == pytest.approx(0.08) and a.score > 0
    assert "contexte" in a.reading
    # « états financiers … publiés avec retard » : rumeur, pas une publication de comptes annuels.
    r = _analyst("Rumeur de retard des comptes de SOGB",
                 "Selon une source de marché non confirmée, les états financiers 2026 de SOGB CI pourraient être "
                 "publiés avec retard.", stance="baissier", conviction=2)
    assert r.event_type == "MANUAL" and "R7" in r.risk_flags and r.score < 0
    assert r.components["uncertainty_terms"] >= 2  # « non confirmée », « selon une source »
    # Une publication de résultats chiffrée garde son type, même lue dans le texte.
    q = _analyst("BOA Côte d'Ivoire : point d'activité",
                 "Au 30 septembre 2026, le produit net bancaire progresse de 12 % et le résultat net de 18 %.")
    assert q.event_type == "ACT_Q3"
    # Note automatique : le type lu dans le texte reste retenu.
    auto = an.analyze_text("Le conseil a décidé le fractionnement des actions.", title="SONATEL : Communiqué")
    assert auto.event_type == "SPLIT"


def test_regression_suspension_rule_ignores_payment_suspension():
    assert lx.detect_event_type("Coup d'État au Niger", "la suspension des paiements de la banque")[0] == "POLITIQUE"
    assert lx.detect_event_type("La BCEAO a suspendu ses opérations bancaires")[0] == "MACRO"
    for t in ("Suspension de cotation - SOGB CI", "AVIS DE SUSPENSION DES TITRES SOGB", "Titre suspendu",
              "Suspension de la cotation des actions SOGB CI"):
        assert lx.detect_event_type(t)[0] == "SUSPENSION", t
    a = _analyst("Coup d'État au Niger : risque pour BOA Niger",
                 "Une tentative de coup d'État a eu lieu à Niamey. Les sanctions de la CEDEAO de 2023 avaient "
                 "entraîné la suspension des paiements.", stance="baissier", conviction=4)
    assert a.event_type == "POLITIQUE" and "R1" not in a.risk_flags
    assert a.primary_target == "BOAN" and {"PAYS:NE", "THEME:COUP_ETAT"} <= set(a.targets)
    assert a.tone < 0 and a.score < 0


@pytest.mark.parametrize(
    "text, sign",
    [
        ("La BCEAO a décidé de baisser ses taux directeurs de 25 points de base.", 1),
        ("Baisse de 25 pb des taux directeurs de la BCEAO", 1),
        ("Cet assouplissement monétaire réduit le coût des ressources.", 1),
        ("La BCEAO relève ses taux directeurs.", -1),
        ("Le resserrement monétaire se poursuit.", -1),
        ("Impact négatif attendu sur la marge de Sonatel.", -1),
        ("Les marges des distributeurs sous pression.", -1),
        ("Le risque de tensions politiques pèse sur les titres togolais.", -1),
        ("Une tentative de coup d'État a eu lieu.", -1),
        ("La loi de finances prévoit une nouvelle taxe.", -1),
        ("Le coût du risque est en baisse.", 1),
        ("Les valeurs bancaires profitent de la baisse des taux.", 1),
        ("Une mesure favorable à la consommation.", 1),
        ("Dividende SNTS attendu en hausse", 1),
        ("Le dividende Sonatel attendu en baisse.", -1),
        ("Pas d'impact négatif sur les comptes.", 0),
        ("Aucun impact significatif sur le résultat.", 0),
        ("La société profite de cette occasion pour remercier ses clients.", 0),
    ],
)
def test_regression_lexicon_v02_terms(text, sign):
    tone = lx.score_text(text)["tone"]
    assert (tone > 0, tone < 0, tone == 0)[{1: 0, -1: 1, 0: 2}[sign]], (text, tone)


def test_regression_rumour_is_uncertainty_not_direction():
    r = lx.score_text("Rumeur non confirmée, selon des sources de marché : à vérifier.")
    assert r["tone"] == 0 and r["uncertainty"] >= 3


def test_regression_primary_target_follows_title():
    a = _analyst("Élections au Togo en 2027 : risque",
                 "Le risque de tensions politiques pèse sur les titres togolais cotés (Ecobank Transnational, Oragroup).",
                 stance="baissier", conviction=2)
    assert a.primary_target == "PAYS:TG" and {"ETIT", "ORGT", "THEME:ELECTIONS"} <= set(a.targets)
    assert a.event_type == "POLITIQUE" and a.tone < 0
    b = _analyst("La BCEAO baisse son taux directeur de 25 pb",
                 "Cet assouplissement monétaire devrait réduire le coût des ressources des banques.")
    assert b.primary_target == "THEME:TAUX_BCEAO" and "SECT:FIN" in b.targets and b.score > 0
    # brvm.org : l'émetteur du titre reste la cible principale.
    c = an.analyze_text("", title="BANK OF AFRICA NIGER : Communiqué - Alerte sur résultats")
    assert c.primary_target == "BOAN"


def test_regression_theme_exposure_propagation():
    from brvm_alpha.notes.model import KNOWN_SYMBOLS, THEMES

    for theme, items in en.THEME_EXPOSURES.items():
        assert theme in THEMES
        for tgt, sign, channel, source in items:
            assert (tgt in KNOWN_SYMBOLS or tgt.startswith("SECT:")) and sign in (-1, 0, 1) and channel and source
    cacao = {e["target"]: e["sign"] for e in en.theme_exposure("THEME:CACAO")}
    assert cacao == {"FTSC": 1, "SDSC": 1, "NTLC": 0}
    assert en.theme_exposure("INFLATION") == [] and en.theme_exposure("ELECTIONS") == []
    a = _analyst("Hausse du prix du pétrole : marges des distributeurs sous pression",
                 "Les marges de TotalEnergies Marketing CI et de Vivo Energy CI risquent de se dégrader.",
                 stance="baissier", conviction=3)
    assert a.primary_target == "THEME:PETROLE" and {"TTLC", "SHEC"} <= set(a.targets)
    expo = {e["target"] for e in a.components["theme_exposure"]["THEME:PETROLE"]}
    assert {"SMBC", "TTLS"} <= expo and "SMBC (+)" in a.reading and a.tone < 0
