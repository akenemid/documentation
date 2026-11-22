"""Tests de ``brvm_alpha.notes.signals`` : scores datés, propagation, surcouches, filtres R1-R10.

Hors ligne. Le journal réel ``data/notes`` n'est jamais touché (``tmp_path``). La plupart
des notes portent une analyse fixée (score, filtres) pour que les tests ne dépendent pas
du lexique ; quelques tests passent par la vraie analyse (fixtures ``core_*``).
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from brvm_alpha.notes import signals as sg
from brvm_alpha.notes.model import Note, SessionCalendar
from brvm_alpha.notes.store import NoteStore

FIX = Path(__file__).parent / "fixtures" / "notes"
REAL_PANEL = Path(__file__).resolve().parents[1] / "data" / "panel"


def biz_days(start: str = "2026-01-05", end: str = "2026-12-31") -> pd.DatetimeIndex:
    days = pd.bdate_range(start, end)
    return days[~days.strftime("%m-%d").isin(["01-01", "05-01", "08-07", "08-15", "11-01", "11-15", "12-25"])]


CAL = biz_days()

#: Univers synthétique : symbole -> (secteur, compartiment). Pays : reference.country_of.
UNIVERSE = {
    "SNTS": ("TEL", "PRESTIGE"), "ORAC": ("TEL", "PRESTIGE"), "SGBC": ("FIN", "PRESTIGE"),
    "BOAN": ("FIN", "PRINCIPAL"), "ETIT": ("FIN", "PRINCIPAL"), "SPHC": ("CB", "PRESTIGE"),
    "SOGC": ("CB", "PRINCIPAL"), "TTLC": ("ENE", "PRESTIGE"), "BOAS": ("FIN", "PRINCIPAL"),
}


def equities(dates=("2026-01-05",)) -> pd.DataFrame:
    rows = []
    for d in dates:
        for s, (sec, comp) in UNIVERSE.items():
            rows.append({"date": pd.Timestamp(d), "symbol": s, "name": s, "sector": sec, "compartment": comp,
                         "value": 1e6 * (1 + len(s)), "volume": 100.0, "status": "traded", "close": 1000.0})
    return pd.DataFrame(rows)


EQ = equities()


def analysis(score: float, flags=(), event_type="OTHER", targets=(), extracted=None, confidence=0.6) -> dict:
    return {"targets": list(targets), "event_type": event_type, "tone": 0.0, "s_num": 0.0, "score": score,
            "materiality": 0.5, "confidence": confidence, "risk_flags": list(flags), "extracted": dict(extracted or {}),
            "reading": "", "matched_terms": []}


def note(title: str, published: str, targets=("SNTS",), score: float = 0.5, flags=(), event_type=None,
         author="auto", created: str | None = None, extracted=None, **kw) -> Note:
    src = "url" if author == "auto" else "manual"
    return Note(title=title, text=title, targets=list(targets), published_at=published,
                created_at=created or published, author=author, source=src,
                url=f"http://exemple/{abs(hash((title, published))) % 10**8}" if author == "auto" else "",
                event_type=event_type, analysis=analysis(score, flags, event_type or "OTHER", targets, extracted), **kw)


def make_store(tmp_path, notes) -> NoteStore:
    st = NoteStore(tmp_path / "notes", calendar=list(CAL))
    for n in notes:
        st.add(n, now=n.created_at)
    return st


def scores(store, asof, **kw) -> pd.DataFrame:
    kw.setdefault("calendar", list(CAL))
    kw.setdefault("equities", EQ)
    return sg.note_scores(store, asof, **kw)


# ---------------------------------------------------------------------------
# Compteur de séances et décroissance
# ---------------------------------------------------------------------------


def test_session_clock_matches_session_calendar():
    cal = SessionCalendar(list(CAL))
    clk = sg.SessionClock(cal)
    pairs = [("2026-03-02", "2026-03-09"), ("2026-11-13", "2026-11-17"), ("2026-12-24", "2027-01-08"),
             ("2026-02-27", "2026-02-28"), ("2026-05-01", "2026-05-04")]
    for a, b in pairs:
        assert clk.between(a, b) == cal.sessions_between(a, b)
    # nth_session : 5 séances après le vendredi 13/11/2026 (16/11 lundi = 1re, 15/11 férié dimanche).
    assert clk.nth_session("2026-11-13", 1) == pd.Timestamp("2026-11-16")
    assert clk.nth_session("2026-11-13", 5) == pd.Timestamp("2026-11-20")
    assert clk.nth_session("2026-11-14", 0) == pd.Timestamp("2026-11-16")
    assert clk.nth_session("2026-11-16", 0) == pd.Timestamp("2026-11-16")


@pytest.mark.skipif(not (REAL_PANEL / "sessions.parquet").exists(), reason="panel réel absent")
def test_session_clock_on_real_calendar_with_gaps():
    sessions = pd.read_parquet(REAL_PANEL / "sessions.parquet")
    cal = SessionCalendar(sessions)
    clk = sg.SessionClock(sessions)
    for a, b in [("2021-05-03", "2021-07-05"), ("2020-12-28", "2021-01-08"), ("2026-11-02", "2026-11-20")]:
        assert clk.between(a, b) == cal.sessions_between(a, b)


def test_decay_half_life_and_tau():
    assert sg.decay_factor(0, 10)[()] == 1.0
    assert sg.decay_factor(10, 10)[()] == pytest.approx(0.5)
    assert sg.decay_factor(20, 10)[()] == pytest.approx(0.25)
    # Formule du document 07 : exp(−Δ/τ), τ = 10.
    assert sg.decay_factor(10, tau=10)[()] == pytest.approx(math.exp(-1))
    with pytest.raises(ValueError):
        sg.decay_factor(1, half_life=0)


# ---------------------------------------------------------------------------
# note_scores : point-in-time
# ---------------------------------------------------------------------------


def test_note_after_cutoff_counts_from_next_session(tmp_path):
    st = make_store(tmp_path, [note("SNTS soir", "2026-11-17 16:00", score=0.6)])
    assert "SNTS" not in scores(st, "2026-11-17").index  # publiée après la séance du 17
    s18 = scores(st, "2026-11-18")
    assert s18.loc["SNTS", "score"] == pytest.approx(0.6)  # 1re séance négociable : Δ = 0
    s = scores(st, "2026-12-02")  # 10 séances plus tard : exp(−10/τ), τ = 10 (document 07 §3.4)
    assert s.loc["SNTS", "score"] == pytest.approx(0.6 * math.exp(-1))
    assert s.loc["SNTS", "last_session"] == pd.Timestamp("2026-11-18")


def test_note_before_cutoff_counts_same_session(tmp_path):
    st = make_store(tmp_path, [note("SNTS matin", "2026-11-17 08:30", score=-0.4)])
    assert scores(st, "2026-11-17").loc["SNTS", "score"] == pytest.approx(-0.4)
    assert "SNTS" not in scores(st, "2026-11-16").index


def test_date_only_publication_acts_next_session(tmp_path):
    st = make_store(tmp_path, [note("SNTS date seule", "2026-11-17", score=0.5, created="2026-11-17 07:00")])
    assert "SNTS" not in scores(st, "2026-11-17").index
    assert scores(st, "2026-11-18").loc["SNTS", "score"] == pytest.approx(0.5)


def test_retro_collected_note_invisible_in_strict_mode(tmp_path):
    n = note("ancienne", "2026-06-01 08:00", score=0.8, created="2026-11-20 10:00")
    st = make_store(tmp_path, [n])
    assert "SNTS" not in scores(st, "2026-06-10").index
    loose = scores(st, "2026-06-10", strict=False)
    assert loose.loc["SNTS", "score"] == pytest.approx(0.8 * math.exp(-7 / 10))


def test_version_in_force_and_archive(tmp_path):
    n = note("v1", "2026-10-01 08:00", score=0.5)
    st = make_store(tmp_path, [n])
    st.update(n.note_id, analysis=analysis(-0.5, targets=["SNTS"]), now="2026-10-08 12:00", reanalyze=False)
    st.archive(n.note_id, now="2026-10-15 12:00")
    assert scores(st, "2026-10-07").loc["SNTS", "score"] > 0  # version 1 en vigueur
    # Version 2 écrite le 08/10 à 12h00, après la coupure : elle n'est en vigueur qu'à la
    # séance du 09/10 (une décision prise à la séance du 08/10 ne la connaissait pas).
    assert scores(st, "2026-10-08").loc["SNTS", "score"] > 0
    assert scores(st, "2026-10-09").loc["SNTS", "score"] < 0
    assert scores(st, "2026-10-15").loc["SNTS", "score"] < 0  # archivage écrit à 12h00 : effet le 16/10
    assert "SNTS" not in scores(st, "2026-10-16").index  # archivée


def test_sum_of_notes_and_columns(tmp_path):
    st = make_store(tmp_path, [
        note("a", "2026-11-02 08:00", score=0.4),
        note("b", "2026-11-09 08:00", score=-0.2),
        note("c", "2026-11-09 08:00", targets=["SNTS"], score=0.3, author="analyste", stance="haussier", conviction=4),
    ])
    s = scores(st, "2026-11-16")
    exp = 0.4 * math.exp(-10 / 10) - 0.2 * math.exp(-5 / 10) + 0.3 * math.exp(-5 / 10)
    assert s.loc["SNTS", "score"] == pytest.approx(exp)
    assert s.loc["SNTS", "n_notes"] == 3 and s.loc["SNTS", "n_manual"] == 1 and s.loc["SNTS", "n_auto"] == 2
    assert s.loc["SNTS", "score_manual"] == pytest.approx(0.3 * math.exp(-0.5))
    assert s.loc["SNTS", "score_manual"] + s.loc["SNTS", "score_auto"] == pytest.approx(exp)
    for c in sg.SCORE_COLUMNS:
        assert c in s.columns


def test_old_notes_fade_out(tmp_path):
    st = make_store(tmp_path, [note("a", "2026-01-06 08:00", score=0.9)])
    assert "SNTS" not in scores(st, "2026-11-20").index  # > 100 séances : facteur < 0,001


# ---------------------------------------------------------------------------
# Propagation
# ---------------------------------------------------------------------------


def test_propagation_country_sector_market_index(tmp_path):
    st = make_store(tmp_path, [
        note("pays SN", "2026-11-16 08:00", targets=["PAYS:SN"], score=0.4, author="analyste"),
        note("secteur TEL", "2026-11-16 08:00", targets=["SECT:TEL"], score=-0.6, author="analyste"),
        note("marché", "2026-11-16 08:00", targets=["MARCHE"], score=0.8, author="analyste"),
        note("prestige", "2026-11-16 08:00", targets=["IDX:PRESTIGE"], score=-0.4, author="analyste"),
    ])
    s = scores(st, "2026-11-16")
    # SNTS : SN (0,5 × 0,4) + TEL (0,5 × −0,6) + marché (0,25 × 0,8) + Prestige (0,25 × −0,4)
    assert s.loc["SNTS", "score"] == pytest.approx(0.2 - 0.3 + 0.2 - 0.1)
    assert s.loc["SNTS", "score_direct"] == 0.0
    # BOAS (SN, FIN, Principal) : SN + marché
    assert s.loc["BOAS", "score"] == pytest.approx(0.2 + 0.2)
    # ORAC (CI, TEL, Prestige) : TEL + marché + Prestige
    assert s.loc["ORAC", "score"] == pytest.approx(-0.3 + 0.2 - 0.1)
    # Les cibles larges ont leur propre ligne (poids 1).
    assert s.loc["PAYS:SN", "score"] == pytest.approx(0.4)
    assert s.loc["IDX:PRESTIGE", "score"] == pytest.approx(-0.4)
    assert s.loc["MARCHE", "score"] == pytest.approx(0.8)


def test_propagation_parameters_are_explicit(tmp_path):
    st = make_store(tmp_path, [note("pays SN", "2026-11-16 08:00", targets=["PAYS:SN"], score=0.4, author="analyste")])
    s = scores(st, "2026-11-16", propagation={"country": 0.1})
    assert s.loc["SNTS", "score"] == pytest.approx(0.04)
    assert "SNTS" not in scores(st, "2026-11-16", propagate=False).index


def test_no_double_count_within_a_note(tmp_path):
    st = make_store(tmp_path, [note("SNTS et SN", "2026-11-16 08:00", targets=["SNTS", "PAYS:SN"], score=0.5,
                                    author="analyste")])
    s = scores(st, "2026-11-16")
    assert s.loc["SNTS", "score"] == pytest.approx(0.5)  # poids max = 1 (cible directe)
    assert s.loc["BOAS", "score"] == pytest.approx(0.25)


def test_theme_exposure_propagation(tmp_path):
    st = make_store(tmp_path, [note("caoutchouc", "2026-11-16 08:00", targets=["THEME:CAOUTCHOUC"], score=0.4,
                                    author="analyste")])
    s = scores(st, "2026-11-16")
    assert s.loc["SPHC", "score"] == pytest.approx(0.1) and s.loc["SOGC", "score"] == pytest.approx(0.1)
    assert "SNTS" not in s.index


def test_theme_sign_negative_and_ambiguous(tmp_path):
    st = make_store(tmp_path, [
        note("hausse des taux", "2026-11-16 08:00", targets=["THEME:TAUX_BCEAO"], score=0.4, author="analyste"),
        note("pétrole", "2026-11-16 08:00", targets=["THEME:PETROLE"], score=0.8, author="analyste"),
    ])
    s = scores(st, "2026-11-16")
    # Hausse des taux (facteur +) : effet −1 sur les banques (secteur FIN), × 0,25.
    for b in ("SGBC", "BOAN", "ETIT", "BOAS"):
        assert s.loc[b, "score"] == pytest.approx(-0.1)
    # Pétrole : TTLC a un signe ambigu (0) -> pas de propagation.
    assert "TTLC" not in s.index
    assert dict(sg.theme_exposures("THEME:PETROLE"))["TTLC"] == 0


def test_detected_broad_targets_are_context_when_a_symbol_is_detected(tmp_path):
    n = Note(title="x", text="x", published_at="2026-11-16 08:00", created_at="2026-11-16 08:00", author="auto",
             source="url", url="http://e/1", analysis=analysis(0.5, targets=["SNTS", "PAYS:SN", "MARCHE"]))
    st = make_store(tmp_path, [n])
    s = scores(st, "2026-11-16")
    assert list(s.index) == ["SNTS"]


def test_manual_targets_override_detected(tmp_path):
    n = Note(title="BRVM 30", text="Sonatel tire l'indice", targets=["IDX:PRESTIGE"], published_at="2026-11-16 08:00",
             created_at="2026-11-16 08:00", analysis=analysis(0.4, targets=["IDX:PRESTIGE", "SNTS"]))
    st = make_store(tmp_path, [n])
    s = scores(st, "2026-11-16")
    assert s.loc["SNTS", "score"] == pytest.approx(0.1)  # propagation 0,25, pas de poids direct
    assert s.loc["SNTS", "score_direct"] == 0.0


def test_brvm30_note_reaches_official_constituents(tmp_path):
    eq = equities(("2026-11-16",))
    st = make_store(tmp_path, [note("BRVM 30", "2026-11-16 08:00", targets=["IDX:BRVM-30"], score=-0.8,
                                    author="analyste")])
    s = sg.note_scores(st, "2026-11-16", calendar=list(CAL), equities=eq)
    assert s.loc["SNTS", "score"] == pytest.approx(-0.2)  # SNTS dans la composition T4-2026
    assert "BOAN" in s.index and "TTLC" in s.index
    assert "BOAS" in s.index
    assert "SPHC" in s.index


# ---------------------------------------------------------------------------
# notes_panel
# ---------------------------------------------------------------------------


def test_notes_panel_equals_note_scores_at_each_date(tmp_path):
    n1 = note("a", "2026-10-01 08:00", score=0.5)
    notes = [
        n1,
        note("b", "2026-10-05 16:00", targets=["PAYS:SN"], score=-0.4, author="analyste"),
        note("c", "2026-10-20 08:00", targets=["IDX:PRESTIGE"], score=0.6, author="analyste"),
        note("d", "2026-10-21", targets=["BOAN"], score=-0.7, created="2026-10-21 07:00"),
        note("e retro", "2026-09-01 08:00", targets=["SGBC"], score=0.9, created="2026-10-12 11:00"),
    ]
    st = make_store(tmp_path, notes)
    st.update(n1.note_id, analysis=analysis(-0.2, targets=["SNTS"]), now="2026-10-09 15:00", reanalyze=False)
    dates = CAL[(CAL >= "2026-09-25") & (CAL <= "2026-11-30")]
    pn = sg.notes_panel(st, list(dates), ["SNTS", "BOAN", "BOAS", "SGBC", "ORAC"], equities=EQ,
                        targets=["PAYS:SN", "IDX:PRESTIGE"])
    assert list(pn.index) == list(dates)
    for t in dates[::3]:
        s = sg.note_scores(st, t, calendar=list(dates), equities=EQ)
        for c in pn.columns:
            exp = float(s["score"].get(c, 0.0))
            assert pn.at[t, c] == pytest.approx(exp, abs=1e-12), (t, c)
    # Rien avant la première note ; la note rétro-collectée n'agit qu'à partir de sa saisie
    # (12/10 à 11h00, après la coupure de 09h00 : séance du 13/10).
    assert (pn.loc[:"2026-09-30"] == 0).all().all()
    assert pn.at[pd.Timestamp("2026-10-09"), "SGBC"] == 0.0
    assert pn.at[pd.Timestamp("2026-10-12"), "SGBC"] == 0.0
    assert pn.at[pd.Timestamp("2026-10-13"), "SGBC"] == pytest.approx(0.9)


def test_notes_panel_with_sessions_frame(tmp_path):
    st = make_store(tmp_path, [note("a", "2026-11-02 08:00", score=0.4)])
    sessions = pd.DataFrame({"date": list(CAL[(CAL >= "2026-11-02") & (CAL <= "2026-11-30")])})
    pn = sg.notes_panel(st, sessions, ["SNTS"], equities=EQ)
    assert pn.at[pd.Timestamp("2026-11-02"), "SNTS"] == pytest.approx(0.4)
    assert pn.at[pd.Timestamp("2026-11-16"), "SNTS"] == pytest.approx(0.4 * math.exp(-1))  # 10 séances après


# ---------------------------------------------------------------------------
# manual_overlays : veto, tilt, filtres
# ---------------------------------------------------------------------------


def overlays(store, asof, **kw):
    kw.setdefault("calendar", list(CAL))
    kw.setdefault("equities", EQ)
    return sg.manual_overlays(store, asof, **kw)


def test_tilt_bounds_and_expiry(tmp_path):
    st = make_store(tmp_path, [
        note("SNTS +", "2026-11-02 08:00", score=0.4, author="analyste", stance="haussier", conviction=5),
        note("SNTS ++", "2026-11-03 08:00", score=0.4, author="analyste", stance="haussier", conviction=3),
        note("SGBC -", "2026-11-02 08:00", targets=["SGBC"], score=-0.4, author="analyste", stance="baissier",
             conviction=2, horizon_days=5),
        note("SN +", "2026-11-02 08:00", targets=["PAYS:SN"], score=0.2, author="analyste", stance="haussier",
             conviction=4),
        note("auto ignoré", "2026-11-02 08:00", targets=["ORAC"], score=0.9, stance="haussier", conviction=5),
    ])
    ov = overlays(st, "2026-11-04")
    assert ov["tilt"]["SNTS"] == pytest.approx(0.5)  # 0,5 + 0,3 + 0,2 (SN) -> borné à 0,5
    assert ov["tilt"]["SGBC"] == pytest.approx(-0.2)  # −1 × 2/5 × 0,5
    assert ov["tilt"]["BOAS"] == pytest.approx(0.2)  # 4/5 × 0,5 × 0,5 (propagation pays)
    assert "ORAC" not in ov["tilt"].index  # note automatique : pas de surcouche manuelle
    assert ov["tilt_targets"]["PAYS:SN"] == pytest.approx(0.4)
    assert (ov["tilt"].abs() <= sg.TILT_MAX_SD + 1e-12).all()
    # Horizon de 5 séances : active les 02, 03, 04, 05 et 06/11, expirée le 09/11.
    assert overlays(st, "2026-11-06")["tilt"].get("SGBC", 0.0) == pytest.approx(-0.2)
    assert overlays(st, "2026-11-09")["tilt"].get("SGBC", 0.0) == 0.0
    # Horizon par défaut (20 séances) : la note SNTS du 02/11 expire après le 27/11.
    assert overlays(st, "2026-11-27")["tilt"].get("SNTS", 0.0) > 0
    assert overlays(st, "2026-12-02")["tilt"].get("SNTS", 0.0) == 0.0


def test_manual_veto_tag_with_expiry_and_broad_target(tmp_path):
    st = make_store(tmp_path, [
        note("veto ETIT", "2026-11-02 08:00", targets=["ETIT"], score=-0.5, author="analyste", tags=["veto"],
             horizon_days=10),
        note("veto Niger", "2026-11-02 08:00", targets=["PAYS:NE"], score=-0.5, author="analyste", tags=["Veto"]),
        note("tag auto", "2026-11-02 08:00", targets=["SNTS"], score=-0.5, tags=["veto"]),
    ])
    ov = overlays(st, "2026-11-13")
    assert set(ov["veto"]) == {"ETIT", "BOAN"}
    assert "ETIT" in ov["block_buys"] and "BOAN" in ov["block_buys"]
    assert "SNTS" not in ov["veto"]  # seule une note de l'analyste porte un veto
    assert any("veto manuel" in r for r in ov["reasons"])
    assert "ETIT" not in overlays(st, "2026-11-16")["veto"]  # 10 séances écoulées


def test_r2_duration_60_sessions(tmp_path):
    st = make_store(tmp_path, [note("AG annulée ETIT", "2026-10-23 16:00", targets=["ETIT"], score=-0.6,
                                    flags=["R2"], event_type="AG_CANCEL")])
    clk = sg.SessionClock(list(CAL))
    first = pd.Timestamp("2026-10-26")
    last = clk.nth_session(first, 59)
    ov = overlays(st, last)
    f = ov["flags"]["ETIT"][0]
    assert f["code"] == "R2" and f["until"] == last and f["remaining_sessions"] == 0
    assert ov["governance_penalty"]["ETIT"] == -1.0 and "ETIT" in ov["block_buys"]
    assert "ETIT" not in overlays(st, clk.nth_session(first, 60))["flags"]
    assert "ETIT" not in overlays(st, "2026-10-23")["flags"]  # pas encore négociable


def test_r8_r4_durations(tmp_path):
    st = make_store(tmp_path, [
        note("split", "2026-10-01 08:00", targets=["SNTS"], score=0.0, flags=["R8"], event_type="SPLIT"),
        note("dégradation", "2026-10-01 08:00", targets=["SGBC"], score=-0.3, flags=["R4"], event_type="RATING"),
    ])
    clk = sg.SessionClock(list(CAL))
    d0 = pd.Timestamp("2026-10-01")
    assert "SNTS" in overlays(st, clk.nth_session(d0, 4))["flags"]
    assert "SNTS" not in overlays(st, clk.nth_session(d0, 5))["flags"]
    ov = overlays(st, clk.nth_session(d0, 50))
    assert ov["max_weight_mult"]["SGBC"] == 0.5
    assert "SGBC" in overlays(st, clk.nth_session(d0, 119))["flags"]
    assert "SGBC" not in overlays(st, clk.nth_session(d0, 120))["flags"]


def test_r9_is_veto_and_ends_with_next_accounts(tmp_path):
    st = make_store(tmp_path, [
        note("alerte", "2026-09-01 08:00", targets=["BOAN"], score=-0.8, flags=["R9"], event_type="PROFIT_WARNING"),
        note("comptes S1", "2026-10-20 08:00", targets=["BOAN"], score=-0.2, event_type="RES_S1"),
    ])
    ov = overlays(st, "2026-10-19")
    assert "BOAN" in ov["veto"] and ov["quality_penalty"]["BOAN"] == -1.0
    assert ov["disabled_signals"]["BOAN"] == ["S1", "S4"]
    assert "BOAN" not in overlays(st, "2026-10-20")["veto"]


def test_r3_until_next_accounts(tmp_path):
    st = make_store(tmp_path, [
        note("réserves", "2026-04-01 08:00", targets=["SGBC"], score=-0.7, flags=["R3"], event_type="RES_ANNUAL"),
        note("activité T1", "2026-05-04 08:00", targets=["SGBC"], score=0.2, event_type="ACT_Q1"),
        note("comptes S1", "2026-09-30 08:00", targets=["SGBC"], score=0.3, event_type="RES_S1"),
    ])
    assert "SGBC" in overlays(st, "2026-09-29")["veto"]  # un rapport T1 n'est pas « les comptes »
    assert "SGBC" not in overlays(st, "2026-09-30")["veto"]


def test_r1_until_resumption_plus_5_sessions(tmp_path):
    st = make_store(tmp_path, [
        note("suspension", "2026-06-01 08:00", targets=["SOGC"], score=-0.5, flags=["R1"], event_type="SUSPENSION"),
        note("reprise", "2026-06-10 08:00", targets=["SOGC"], score=0.1, event_type="RESUMPTION"),
    ])
    assert "SOGC" in overlays(st, "2026-06-09", use_panel_status=False)["block_buys"]
    clk = sg.SessionClock(list(CAL))
    end = clk.nth_session("2026-06-10", 5)
    assert "SOGC" in overlays(st, end, use_panel_status=False)["flags"]
    assert "SOGC" not in overlays(st, clk.nth_session("2026-06-10", 6), use_panel_status=False)["flags"]


def test_r1_resumption_from_panel_status(tmp_path):
    days = CAL[(CAL >= "2026-06-01") & (CAL <= "2026-07-15")]
    eq = equities(days)
    eq.loc[(eq["symbol"] == "SOGC") & (eq["date"] <= "2026-06-12"), "status"] = "suspended"
    st = make_store(tmp_path, [note("suspension", "2026-06-01 08:00", targets=["SOGC"], score=-0.5, flags=["R1"],
                                    event_type="SUSPENSION")])
    ov = overlays(st, "2026-06-30", equities=eq)
    assert "SOGC" not in ov["flags"]  # reprise le 15/06 (statut du panel) + 5 séances = 22/06
    ov2 = overlays(st, "2026-06-19", equities=eq)
    assert ov2["flags"]["SOGC"][0]["resumption"] == pd.Timestamp("2026-06-15")


def test_r5_until_rights_detachment(tmp_path):
    st = make_store(tmp_path, [note("DPS", "2026-04-01 08:00", targets=["SGBC"], score=-0.1, flags=["R5"],
                                    event_type="CAP_INC", extracted={"ex_date": "2026-04-24"})])
    assert "SGBC" in overlays(st, "2026-04-23")["block_buys"]
    assert "SGBC" not in overlays(st, "2026-04-24")["block_buys"]


def test_r10_candidate_confirmed_by_journal(tmp_path):
    st = make_store(tmp_path, [note("comptes", "2026-10-15 08:00", targets=["ETIT"], score=-0.6,
                                    event_type="RES_S1", extracted={"r10_candidate": True, "rn_growth": -0.4})])
    ov = overlays(st, "2026-10-20")
    f = ov["flags"]["ETIT"][0]
    assert f["code"] == "R10" and f["confirmed"] is False
    assert ov["quality_penalty"]["ETIT"] == -0.5
    st2 = make_store(tmp_path / "b", [
        note("alerte", "2026-09-01 08:00", targets=["ETIT"], score=-0.6, event_type="PROFIT_WARNING"),
        note("comptes", "2026-10-15 08:00", targets=["ETIT"], score=-0.6, event_type="RES_S1",
             extracted={"r10_candidate": True}),
    ])
    assert "R10" not in [x["code"] for x in overlays(st2, "2026-10-20")["flags"].get("ETIT", [])]


def test_overlays_reasons_are_french_and_dated(tmp_path):
    st = make_store(tmp_path, [note("AG annulée", "2026-10-23 16:00", targets=["ETIT"], score=-0.6, flags=["R2"],
                                    event_type="AG_CANCEL")])
    ov = overlays(st, "2026-11-20")
    assert any(r.startswith("ETIT : R2 depuis le 26/10/2026") and "séance" in r for r in ov["reasons"])
    assert isinstance(ov["table"], pd.DataFrame) and len(ov["table"]) == 1


# ---------------------------------------------------------------------------
# Intégration avec la vraie analyse
# ---------------------------------------------------------------------------


def load_fixture(name: str) -> str:
    lines = (FIX / name).read_text(encoding="utf-8").splitlines()
    return "\n".join(ln for ln in lines if not ln.startswith("#"))


def test_real_analysis_on_the_fly_profit_warning_is_r9(tmp_path):
    n = Note(title="Communiqué – Alerte sur résultats - BOA NIGER", text=load_fixture("core_alerte_resultats_boan.txt"),
             targets=["BOAN"], published_at="2026-11-13 16:00", created_at="2026-11-13 16:00", author="auto",
             source="brvm_list", url="http://exemple/boan")
    st = make_store(tmp_path, [n])  # ajoutée sans analyse : calculée à la volée
    s = scores(st, "2026-11-16")
    assert s.loc["BOAN", "score"] < 0
    ov = overlays(st, "2026-11-16")
    assert "R9" in [f["code"] for f in ov["flags"]["BOAN"]] and "BOAN" in ov["veto"]


def test_frame_and_note_list_inputs(tmp_path):
    notes = [note("a", "2026-11-02 08:00", score=0.4), note("b", "2026-11-02 16:00", targets=["SGBC"], score=0.2)]
    st = make_store(tmp_path, notes)
    a = scores(st, "2026-11-03")
    b = scores(st.frame(all_versions=True), "2026-11-03")
    c = scores(notes, "2026-11-03")
    pd.testing.assert_series_equal(a["score"], b["score"])
    pd.testing.assert_series_equal(a["score"].sort_index(), c["score"].sort_index())
    assert len(scores([], "2026-11-03")) == 0


# ---------------------------------------------------------------------------
# Régressions de la revue du 22/11/2026 (chaque test échouait avant la correction)
# ---------------------------------------------------------------------------


def test_regression_strict_session_follows_knowledge_time(tmp_path):
    """Une note publiée à 08h00 mais saisie à 20h00 n'agit qu'à la séance suivante (mode strict)."""
    a = note("SONATEL : bénéfice record", "2026-11-17 08:00", score=0.8, author="analyste",
             created="2026-11-17 20:00")
    b = note("SONATEL : bénéfice record (bis)", "2026-11-17 20:00", score=0.8, author="analyste",
             created="2026-11-17 20:00")
    st = make_store(tmp_path, [a, b])
    assert scores(st, "2026-11-17").empty  # rien n'était connu avant la coupure du 17/11
    s18 = scores(st, "2026-11-18")
    assert s18.loc["SNTS", "score"] == pytest.approx(1.6)  # Δ = 0 pour les deux notes
    assert (s18.loc["SNTS", "last_session"]) == pd.Timestamp("2026-11-18")
    con = sg.note_contributions(st, "2026-11-18", calendar=list(CAL), equities=EQ)
    assert set(con["first_tradable_session"]) == {pd.Timestamp("2026-11-18")}
    df = sg.notes_asof(st, "2026-11-18", calendar=list(CAL))
    assert set(df["first_tradable_session_published"]) == {pd.Timestamp("2026-11-17"), pd.Timestamp("2026-11-18")}
    pn = sg.notes_panel(st, list(CAL[(CAL >= "2026-11-16") & (CAL <= "2026-11-30")]), ["SNTS"], equities=EQ)
    assert pn.at[pd.Timestamp("2026-11-17"), "SNTS"] == 0.0
    assert pn.at[pd.Timestamp("2026-11-18"), "SNTS"] == pytest.approx(1.6)
    # Reconstitution (strict=False) : seule la publication compte.
    assert scores(st, "2026-11-17", strict=False).loc["SNTS", "score"] == pytest.approx(0.8)
    # Les surcouches suivent la même règle (pas de tilt le 17/11).
    a2 = note("SGBC : vue", "2026-11-17 08:00", targets=["SGBC"], score=0.1, author="analyste",
              created="2026-11-17 20:00", stance="haussier", conviction=5)
    st2 = make_store(tmp_path / "b", [a2])
    assert "SGBC" not in overlays(st2, "2026-11-17")["tilt"].index
    assert overlays(st2, "2026-11-18")["tilt"]["SGBC"] == pytest.approx(0.5)


def test_regression_record_time_bounds_knowledge(tmp_path):
    """``add(now=20h00)`` d'une note dont ``created_at`` vaut 08h00 : connue à 20h00, effet à J+1."""
    st = NoteStore(tmp_path / "notes", calendar=list(CAL))
    st.add(note("SNTS", "2026-11-17 08:00", score=0.5, created="2026-11-17 08:00"), now="2026-11-17 20:00")
    assert scores(st, "2026-11-17").empty
    assert scores(st, "2026-11-18").loc["SNTS", "score"] == pytest.approx(0.5)


def test_regression_vectorized_first_tradable_matches_model():
    from brvm_alpha.notes.model import first_tradable_session

    cal = list(CAL)
    rng = np.random.default_rng(7)
    base = pd.Timestamp("2026-10-01", tz="UTC")
    instants = [base + pd.Timedelta(minutes=int(m)) for m in rng.integers(0, 60 * 24 * 70, size=300)]
    instants += [pd.Timestamp("2026-11-17 08:59:59", tz="UTC"), pd.Timestamp("2026-11-17 09:00", tz="UTC"),
                 pd.Timestamp("2026-11-14 07:00", tz="UTC"), pd.Timestamp("2026-12-24 23:59:59.999999", tz="UTC")]
    got = sg.SessionClock(SessionCalendar(cal)).first_tradable(instants)
    exp = [first_tradable_session(t, cal, date_only=False) for t in instants]
    assert [pd.Timestamp(g) for g in got] == exp


def test_regression_default_decay_is_doc07_tau_10(tmp_path):
    """Document 07 (§3.4 règle 6, §6.5 S5) : exp(−Δ/τ) avec τ = 10 séances, par défaut."""
    assert sg.DEFAULT_TAU == 10.0 and sg.DEFAULT_HALF_LIFE == pytest.approx(10 * math.log(2))
    for d in (5, 10, 20):
        assert sg.decay_factor(d)[()] == pytest.approx(math.exp(-d / 10))
    st = make_store(tmp_path, [note("SNTS", "2026-11-02 08:00", score=0.8)])
    assert scores(st, "2026-11-16").loc["SNTS", "score"] == pytest.approx(0.8 * math.exp(-1))
    # La demi-vie reste disponible explicitement.
    assert scores(st, "2026-11-16", half_life=10).loc["SNTS", "score"] == pytest.approx(0.4)


def test_regression_backdated_notes_never_count_in_strict_views(tmp_path, monkeypatch):
    from brvm_alpha.notes.model import SIMULATED_CLOCK_ENV

    monkeypatch.delenv(SIMULATED_CLOCK_ENV, raising=False)
    st = make_store(tmp_path, [note("SNTS rétro", "2026-06-01 08:00", score=0.8)])  # now= antidaté
    assert scores(st, "2026-06-02").empty
    assert sg.notes_panel(st, list(CAL[(CAL >= "2026-06-01") & (CAL <= "2026-06-10")]), ["SNTS"],
                          equities=EQ)["SNTS"].eq(0).all()
    assert scores(st, "2026-06-02", strict=False).loc["SNTS", "score"] == pytest.approx(0.8 * math.exp(-1 / 10))


def test_regression_unknown_manual_target_does_not_fall_back_to_detected(tmp_path):
    n = Note(title="x", text="BOA CI déçoit ; SONATEL reste ma conviction.", targets=["SNTSS"], author="analyste",
             source="manual", published_at="2026-11-16 07:00", created_at="2026-11-16 07:00", stance="haussier",
             conviction=5, analysis=analysis(0.7, targets=["BOAC", "SNTS"]))
    st = make_store(tmp_path, [n])
    assert scores(st, "2026-11-17").empty
    assert sg.effective_targets(st.frame().iloc[0].to_dict()) == []
