"""Non-régression : BOC manquants (trous du calendrier) et datation des dividendes.

Anomalies relevées par les vérificateurs :

* des séances **réelles** manquent au panel (le téléchargeur a noté leur BOC
  ``.missing`` comme un jour férié) : les numéros des bulletins (« N° 186 ») ne se
  suivent pas (2021 : 156 fichiers pour 252 numéros). Le panel porte désormais un
  calendrier contigu (``sessions.parquet``), le numéro global de séance
  (``session_no``) et, pour chaque rendement, le nombre de séances manquantes
  (``missing_sessions``) ;
* un dividende dont la date de détachement estimée (paiement - 2 jours ouvrés) tombait
  dans un trou était crédité à la dernière séance **avant** le trou, alors que le titre
  y était encore cum-dividende (ONTBF 06/05/2021 : ancien dividende 387,17 du
  10-juin-20, référence = clôture 3 415), soit 50 jours avant sa publication ;
* SLBC 2024 : dividende daté pendant la suspension (12/08) alors que la BOC n'ajuste le
  cours qu'à la reprise (12/09 : précédent publié 80 550 = 83 250 - 2 700).

Fixtures : BOC réels de ``tests/fixtures/seq_gap_2021`` et ``seq_gap_2026_10``
(``boc_20261002.missing`` = témoin du téléchargeur).
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from brvm_alpha.data.boc_parser import _issue_number, parse_boc_file
from brvm_alpha.data.store import (
    adjusted_table,
    build_panel,
    detect_dividends,
    load_equities,
    load_sessions,
    session_calendar,
)

FIX = Path(__file__).parent / "fixtures"
PANEL = Path(__file__).resolve().parents[1] / "data" / "panel"
T, N, S = "traded", "not_traded", "suspended"


def seq(symbol: str, rows: list[tuple], session_no: list[int] | None = None) -> pd.DataFrame:
    """Séquence d'un titre : (date, prev, close, ref, div, div_date, status, flags)."""
    recs = []
    for date, prev, close, ref, div, ddate, status, flags in rows:
        recs.append({"date": pd.Timestamp(date), "symbol": symbol, "prev_close": prev, "close": close,
                     "ref_price": ref, "last_div_net": div,
                     "last_div_date": pd.Timestamp(ddate) if ddate else pd.NaT, "status": status,
                     "flags": flags, "ex_div": "(D)" in flags, "volume": 1.0 if status == "traded" else 0.0})
    df = pd.DataFrame(recs)
    if session_no is not None:
        df["session_no"] = session_no
    return df


# ---------------------------------------------------------------------------
# Parseur : numéro du bulletin
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path, issue", [
    ("boc_20180601.txt.gz", 105),
    ("boc_20230601.txt.gz", 103),
    ("boc_20261120.txt.gz", 222),
    ("regressions/boc_20241209.txt.gz", 234),  # bulletin qui commence par la page OPCVM
    ("edge_cases/boc_20250102.txt.gz", 1),  # bulletin en anglais, numéro sans date sur la ligne
    ("seq_gap_2021/boc_20210506.txt.gz", 88),
    ("seq_gap_2021/boc_20210625.txt.gz", 121),
    ("seq_gap_2026_10/boc_20261001.txt.gz", 186),
    ("seq_gap_2026_10/boc_20261005.txt.gz", 188),
])
def test_issue_number_read_from_bulletin(path: str, issue: int) -> None:
    assert parse_boc_file(FIX / path).meta["issue_no"] == issue


def test_issue_number_ignores_notice_references() -> None:
    # Références d'avis du calendrier (20/12/2017, 02/01/2018, 25/07/2019) : jamais le numéro du BOC.
    lines = [
        "BRVM   AVIS N°263 - 2017 / BRVM / Paiement Intérêts CRRH-UEMOA",
        "BRVM   N°001-2018/BRVM/DG Nouvelle composition de l'indice BRVM 10",
        "DC/BR  N°001/2018/DC/BR/DG Paiement Intérêts",
        "CREPMF N°58/CREPMF/2019 Instruction",
    ]
    assert _issue_number(lines) is None
    header = "Variation annuelle      -21,84 % N° 241       mercredi 20 décembre 2017     Site : www.brvm.org"
    assert _issue_number([*lines, header]) == 241
    assert _issue_number(["Variation annuelle   -4,62 %     N° 115    ", "vendredi 19 juin 2018"]) == 115


# ---------------------------------------------------------------------------
# Calendrier des séances
# ---------------------------------------------------------------------------


def test_missing_bulletin_is_a_real_session(tmp_path: Path) -> None:
    # BOC N° 186 (01/10/2026) puis N° 188 (05/10/2026) : le N° 187 du 02/10 manque (noté
    # .missing par le téléchargeur, comme un jour férié). SGBC : clôture 39 000 le 01/10,
    # précédent publié 39 995 le 05/10 (= clôture de la séance manquante du 02/10).
    out = tmp_path / "out"
    summary = build_panel(FIX / "seq_gap_2026_10", out, workers=1)
    assert (summary.n_sessions, summary.n_missing_sessions, summary.n_gaps) == (2, 1, 1)
    cal = load_sessions(out)
    assert list(cal.index) == [186, 187, 188] and list(cal["issue_no"]) == [186, 187, 188]
    gap = cal.loc[187]
    assert not gap["available"] and gap["date"] == pd.Timestamp("2026-10-02") and gap["marker"] == "missing"
    assert (gap["gap_start"], gap["gap_end"]) == (pd.Timestamp("2026-10-01"), pd.Timestamp("2026-10-05"))
    assert cal.loc[188, "missing_before"] == 1 and cal.loc[186, "missing_before"] == 0
    assert list(load_sessions(out, available_only=True).index) == [186, 188]
    eq = load_equities(out)
    d1, d2 = pd.Timestamp("2026-10-01"), pd.Timestamp("2026-10-05")
    assert eq.loc[(d1, "SGBC"), "close"] == 39000 and eq.loc[(d2, "SGBC"), "prev_close"] == 39995
    assert eq.loc[(d2, "SGBC"), "session_no"] - eq.loc[(d1, "SGBC"), "session_no"] == 2
    ap = adjusted_table(panel_dir=out).set_index(["symbol", "date"])
    assert ap.loc[("SGBC", d2), "missing_sessions"] == 1 and ap.loc[("SGBC", d1), "missing_sessions"] == 0
    report = pd.read_csv(out / "parse_report.csv").set_index("file")
    assert report.loc["boc_20261005.txt.gz", "issue_no"] == 188
    assert report.loc["boc_20261005.txt.gz", "missing_before"] == 1


def test_session_calendar_rules() -> None:
    avail = pd.DataFrame({
        "date": pd.to_datetime(["2020-12-30", "2020-12-31", "2021-01-04", "2021-01-07", "2021-01-12"]),
        "source_file": ["a", "b", "c", "d", "e"],
        "issue_no": [251, 252, 1, 3, np.nan],  # N° 2 manquant ; dernier numéro illisible
    })
    cal = session_calendar(avail).set_index("session_no")
    # Numérotation globale contiguë à travers le changement d'année (2020 : 252 séances).
    assert list(cal.index) == list(range(251, 251 + len(cal)))
    assert cal.loc[253, "issue_no"] == 1 and cal.loc[253, "missing_before"] == 0
    # N° 2 : seul numéro manquant entre le 04/01 et le 07/01, mais deux jours ouvrés
    # (05 et 06/01) : date inconnue.
    two = cal.loc[254]
    assert not two["available"] and pd.isna(two["date"]) and two["issue_no"] == 2 and not two["estimated"]
    assert cal.loc[255, "missing_before"] == 1
    # Numéro illisible : estimé (précédent + 1 + jours ouvrés intercalaires = N° 6).
    last = cal[cal["source_file"] == "e"].iloc[0]
    assert last["issue_no"] == 6 and last["estimated"]
    assert session_calendar(avail.iloc[:0]).empty


# ---------------------------------------------------------------------------
# Dividendes : date de détachement estimée dans un trou de BOC
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def gap_2021(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("gap_2021") / "out"
    build_panel(FIX / "seq_gap_2021", out, workers=1)
    return out


GAP_DIVIDENDS = [
    # (symbole, montant, paiement, détachement = première séance après le trou)
    ("ONTBF", 399.56, "2021-06-01", "2021-06-25"),
    ("BOAB", 436.00, "2021-05-20", "2021-06-25"),
    ("BOAC", 315.00, "2021-05-12", "2021-06-25"),
    ("BOAS", 161.01, "2021-06-01", "2021-06-25"),
    ("SNTS", 1225.00, "2021-05-17", "2021-06-25"),
    ("PALC", 102.51, "2021-08-27", "2021-09-08"),
    ("SPHC", 132.30, "2021-08-24", "2021-09-08"),
    ("SCRC", 40.50, "2021-08-20", "2021-09-08"),
]


def test_dividend_estimated_inside_boc_gap_is_credited_after_the_gap(gap_2021: Path) -> None:
    # BOC N° 89 à 120 (07/05 -> 24/06/2021) et N° 156 à 172 (16/08 -> 07/09/2021) introuvables.
    # Le 06/05 (N° 88), ONTBF publie encore 387,17 (10-juin-20) et une référence égale à
    # la clôture (3 415) : titre cum-dividende. Le dividende 399,56 (1-juin-21) paraît le
    # 25/06 (N° 121) ; sa date estimée (28/05) tombe dans le trou.
    raw = parse_boc_file(FIX / "seq_gap_2021" / "boc_20210506.txt.gz").equities.set_index("symbol")
    assert raw.loc["ONTBF", "last_div_net"] == pytest.approx(387.17)
    assert raw.loc["ONTBF", "ref_price"] == raw.loc["ONTBF", "close"] == 3415
    dv = pd.read_parquet(gap_2021 / "dividends.parquet").set_index(["symbol", "payment_date"])
    for sym, amount, paid, ex in GAP_DIVIDENDS:
        ev = dv.loc[(sym, pd.Timestamp(paid))]
        assert ev["amount"] == pytest.approx(amount), sym
        assert ev["ex_date"] == pd.Timestamp(ex), (sym, ev["ex_date"])
        assert ev["ex_date"] >= ev["first_seen"], sym  # jamais crédité avant sa publication
        assert ev["evidence"] == "payment_date_estimate+data_gap", (sym, ev["evidence"])
    ap = pd.read_parquet(gap_2021 / "adjusted_prices.parquet").set_index(["symbol", "date"])
    # Dernière séance avant le trou : rendement total = rendement de prix.
    for sym, ret in [("ONTBF", 3415 / 3450 - 1), ("BOAB", 0.025), ("BOAC", 0.0), ("BOAS", 0.0),
                     ("SNTS", 14195 / 14000 - 1)]:
        r = ap.loc[(sym, pd.Timestamp("2021-05-06"))]
        assert r["dividend"] == 0 and r["tr_ret"] == pytest.approx(ret) and r["ret"] == pytest.approx(ret), sym
    r = ap.loc[("PALC", pd.Timestamp("2021-08-13"))]
    assert r["dividend"] == 0 and r["tr_ret"] == pytest.approx(4350 / 4100 - 1)
    # Première séance après le trou : dividende crédité, rendement sur 33 (resp. 18) séances.
    r = ap.loc[("ONTBF", pd.Timestamp("2021-06-25"))]
    assert r["dividend"] == pytest.approx(399.56) and r["missing_sessions"] == 32
    assert r["tr_ret"] == pytest.approx((3280 + 399.56) / 3415 - 1)
    r = ap.loc[("PALC", pd.Timestamp("2021-09-08"))]
    assert r["dividend"] == pytest.approx(102.51) and r["missing_sessions"] == 17
    assert r["tr_ret"] == pytest.approx((4360 + 102.51) / 4350 - 1)
    # Calendrier : trous identifiés par les numéros ; août-septembre daté (17 numéros
    # manquants pour 17 jours ouvrés), mai-juin non daté (32 numéros, 35 jours ouvrés).
    cal = load_sessions(gap_2021)
    may = cal[(cal["year"] == 2021) & cal["issue_no"].between(89, 120)]
    assert len(may) == 32 and not may["available"].any() and may["date"].isna().all()
    assert (may["gap_start"] == pd.Timestamp("2021-05-06")).all() and (may["gap_end"] == pd.Timestamp("2021-06-25")).all()
    aug = cal[(cal["year"] == 2021) & cal["issue_no"].between(156, 172)]
    assert not aug["available"].any()
    assert list(aug["date"]) == list(pd.bdate_range("2021-08-16", "2021-09-07"))


def test_payment_date_estimate_holiday_vs_boc_gap() -> None:
    # Dividende paru plus de 7 jours après son paiement (03/05/2024), sans marqueur ni
    # ajustement publié : détachement estimé au 01/05 (paiement - 2 jours ouvrés), férié.
    rows = [
        ("2024-04-29", 1000, 1000, 1000, 50, "2023-05-02", T, ""),
        ("2024-04-30", 1000, 1000, 1000, 50, "2023-05-02", T, ""),
        ("2024-05-02", 1000, 1000, 1000, 50, "2023-05-02", T, ""),
        ("2024-05-03", 1000, 1000, 1000, 50, "2023-05-02", T, ""),
        ("2024-05-20", 1000, 1000, 1000, 60, "2024-05-03", T, ""),
        ("2024-05-21", 1000, 1000, 1000, 60, "2024-05-03", T, ""),
    ]
    # Numéros de BOC consécutifs autour du 01/05 : jour férié -> séance précédente (30/04).
    holiday = detect_dividends(seq("AAAA", rows, session_no=[80, 81, 82, 83, 93, 94]))
    assert holiday.iloc[0]["ex_date"] == pd.Timestamp("2024-04-30")
    assert holiday.iloc[0]["evidence"] == "payment_date_estimate"
    # Un numéro saute (BOC du 01/05 manquant) : première séance après le trou (02/05).
    gap = detect_dividends(seq("AAAA", rows, session_no=[80, 81, 83, 84, 94, 95]))
    assert gap.iloc[0]["ex_date"] == pd.Timestamp("2024-05-02")


# ---------------------------------------------------------------------------
# Dividendes : cours précédent publié ajusté du montant
# ---------------------------------------------------------------------------


def test_dividend_of_suspended_stock_dated_at_published_previous_adjustment() -> None:
    # SLBC 2024 : suspendu jusqu'au 11/09 à 83 250 (référence non ajustée) ; reprise le
    # 12/09 avec un précédent publié de 80 550 = 83 250 - 2 700 et (V) ; le dividende
    # 2 700 (14-août-24) ne paraît que le 16/10. Daté auparavant du 12/08 (paiement - 2
    # jours, en pleine suspension), avec un faux +3,2 % ce jour-là.
    rows = [
        ("2024-08-09", 83250, 83250, 83250, 4050, "2022-08-12", S, ""),
        ("2024-08-12", 83250, 83250, 83250, 4050, "2022-08-12", S, ""),
        ("2024-08-13", 83250, 83250, 83250, 4050, "2022-08-12", S, ""),
        ("2024-09-11", 83250, 83250, 83250, 4050, "2022-08-12", S, ""),
        ("2024-09-12", 80550, 86590, 86590, 4050, "2022-08-12", T, "(V)"),
        ("2024-09-13", 86590, 86590, 86590, 4050, "2022-08-12", T, ""),
        ("2024-10-15", 17000, 15725, 15725, 4050, "2022-08-12", T, ""),
        ("2024-10-16", 15725, 14995, 14995, 2700, "2024-08-14", T, ""),
    ]
    for sessions in (None, [150, 151, 152, 172, 173, 174, 196, 197]):  # jours ouvrés / numéros de BOC
        e = seq("SLBC", rows, session_no=sessions)
        dv = detect_dividends(e)
        assert len(dv) == 1
        ev = dv.iloc[0]
        assert (ev["ex_date"], ev["amount"], ev["evidence"]) == (pd.Timestamp("2024-09-12"), 2700.0,
                                                                  "prev_close_adjusted")
        t = adjusted_table(e).set_index("date")
        assert t.loc["2024-08-12", "tr_ret"] == pytest.approx(0.0)
        assert t.loc["2024-09-12", "tr_ret"] == pytest.approx((86590 + 2700) / 83250 - 1)


def test_dividend_dated_by_adjusted_previous_close() -> None:
    # NSBC 2020 : 77,69 (27-juil.-20) paraît le 22/07 avec une référence égale à la clôture
    # (3 200, cum) ; le 23/07 la BOC publie un précédent de 3 125 (≈ 3 200 - 77,69) et
    # une variation de +4,00 % calculée sur lui : détachement le 23/07, non le 22/07.
    e = seq("NSBC", [
        ("2020-07-20", 3655, 3385, 3385, 194.20, "2019-07-09", T, ""),
        ("2020-07-21", 3385, 3385, 3385, 194.20, "2019-07-09", T, ""),
        ("2020-07-22", 3385, 3200, 3200, 77.69, "2020-07-27", T, ""),
        ("2020-07-23", 3125, 3250, 3250, 77.69, "2020-07-27", T, ""),
        ("2020-07-24", 3250, 3250, 3250, 77.69, "2020-07-27", T, ""),
    ])
    ev = detect_dividends(e).iloc[0]
    assert (ev["ex_date"], ev["evidence"]) == (pd.Timestamp("2020-07-23"), "prev_close_adjusted")
    t = adjusted_table(e).set_index("date")
    assert t.loc["2020-07-22", "tr_ret"] == pytest.approx(3200 / 3385 - 1)
    assert t.loc["2020-07-23", "tr_ret"] == pytest.approx((3250 + 77.69) / 3200 - 1)
    # Précédent publié après des séances manquantes : clôture d'une autre séance, pas une preuve.
    gap = seq("NSBC", [
        ("2020-07-20", 3655, 3385, 3385, 194.20, "2019-07-09", T, ""),
        ("2020-07-21", 3385, 3200, 3200, 77.69, "2020-07-27", T, ""),
        ("2020-07-29", 3125, 3250, 3250, 77.69, "2020-07-27", T, ""),
    ], session_no=[140, 141, 146])
    assert detect_dividends(gap).iloc[0]["evidence"] != "prev_close_adjusted"


# ---------------------------------------------------------------------------
# Panel réel (si construit)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not (PANEL / "sessions.parquet").exists(), reason="data/panel absent")
def test_real_panel_session_calendar_and_gap_dividends() -> None:
    cal = pd.read_parquet(PANEL / "sessions.parquet")
    assert cal["session_no"].diff().dropna().eq(1).all()  # calendrier contigu
    for _, g in cal.groupby("year"):  # numéros 1..N sans trou ni doublon chaque année
        assert list(g["issue_no"]) == list(range(g["issue_no"].iloc[0], g["issue_no"].iloc[0] + len(g)))
    missing = cal[~cal["available"]]
    gap21 = missing[(missing["year"] == 2021) & missing["issue_no"].between(89, 120)]
    assert len(gap21) == 32 and (gap21["gap_end"] == pd.Timestamp("2021-06-25")).all()
    assert len(missing[missing["year"] == 2021]) == 96
    oct26 = cal[(cal["year"] == 2026) & (cal["issue_no"] == 187)].iloc[0]
    assert not oct26["available"] and oct26["date"] == pd.Timestamp("2026-10-02") and oct26["marker"] == "missing"
    # 07/07/2020 : témoin .bad (PDF tronqué boc_20200707.pdf) mais BOC lu via boc_20200707_0.pdf (N° 129).
    jul = cal[cal["date"] == pd.Timestamp("2020-07-07")].iloc[0]
    assert jul["available"] and jul["issue_no"] == 129
    eq = pd.read_parquet(PANEL / "equities.parquet")
    assert eq["session_no"].notna().all()
    dv = pd.read_parquet(PANEL / "dividends.parquet").set_index(["symbol", "payment_date"])
    for sym, amount, paid, ex in GAP_DIVIDENDS:
        ev = dv.loc[(sym, pd.Timestamp(paid))]
        assert ev["amount"] == pytest.approx(amount) and ev["ex_date"] == pd.Timestamp(ex), sym
    assert dv.loc[("SLBC", pd.Timestamp("2024-08-14")), "ex_date"] == pd.Timestamp("2024-09-12")
    assert dv.loc[("NSBC", pd.Timestamp("2020-07-27")), "ex_date"] == pd.Timestamp("2020-07-23")
    ap = pd.read_parquet(PANEL / "adjusted_prices.parquet").set_index(["symbol", "date"])
    for sym in ("ONTBF", "BOAB", "BOAC", "BOAS", "SNTS"):
        r = ap.loc[(sym, pd.Timestamp("2021-05-06"))]
        assert r["dividend"] == 0 and r["tr_ret"] == pytest.approx(r["ret"]), sym
    assert ap.loc[("ONTBF", pd.Timestamp("2021-06-25")), "missing_sessions"] == 32
    assert ap.loc[("SGBC", pd.Timestamp("2026-10-05")), "missing_sessions"] == 1
    assert ap.loc[("SNTS", pd.Timestamp("2026-10-01")), "missing_sessions"] == 0
    assert np.isfinite(ap["missing_sessions"]).all()
    report = pd.read_csv(PANEL / "parse_report.csv")
    assert report["issue_no"].notna().all()
    assert dt.date(2021, 6, 25) in set(pd.to_datetime(report.loc[report["missing_before"] == 32, "date"]).dt.date)
