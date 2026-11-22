"""Tests du parseur de BOC sur des bulletins réels (2018, 2020, 2023, 2024, 2025, 2026).

Les valeurs attendues ont été relevées à la main dans les fichiers texte des
fixtures (``zcat tests/fixtures/boc_AAAAMMJJ.txt.gz``).
"""

from __future__ import annotations

import datetime as dt
import math
from pathlib import Path

import pandas as pd
import pytest

from brvm_alpha.data.boc_parser import (
    EQUITY_COLUMNS,
    INDEX_COLUMNS,
    ORDER_BOOK_COLUMNS,
    BocDay,
    parse_boc_file,
    parse_boc_text,
    parse_french_date,
    parse_number,
    read_boc_text,
    tokenize,
    warning_code,
)

FIX = Path(__file__).parent / "fixtures"
MAIN_FIXTURES = ["20180601", "20200302", "20230601", "20240614", "20261120"]


@pytest.fixture(scope="module")
def days() -> dict[str, BocDay]:
    """Les cinq BOC de référence, analysés une seule fois."""
    return {d: parse_boc_file(FIX / f"boc_{d}.txt.gz") for d in MAIN_FIXTURES}


def row(day: BocDay, symbol: str) -> pd.Series:
    """Ligne action d'un symbole (exactement une)."""
    sel = day.equities[day.equities["symbol"] == symbol]
    assert len(sel) == 1, f"{symbol}: {len(sel)} lignes"
    return sel.iloc[0]


def idx(day: BocDay, name: str) -> pd.Series:
    sel = day.indices[day.indices["index"] == name]
    assert len(sel) == 1, f"{name}: {len(sel)} lignes ({sorted(day.indices['index'])})"
    return sel.iloc[0]


def ob(day: BocDay, symbol: str) -> pd.Series:
    sel = day.order_book[day.order_book["symbol"] == symbol]
    assert len(sel) == 1
    return sel.iloc[0]


def assert_row(r: pd.Series, **expected: object) -> None:
    """Compare les champs d'une ligne (NaN attendu = None)."""
    for k, v in expected.items():
        got = r[k]
        if v is None:
            assert got is None or (isinstance(got, float) and math.isnan(got)) or got is pd.NaT, f"{k}: {got!r}"
        elif isinstance(v, float):
            assert got == pytest.approx(v, abs=1e-9), f"{k}: {got!r} != {v!r}"
        elif isinstance(v, dt.date):
            assert pd.Timestamp(got) == pd.Timestamp(v), f"{k}: {got!r} != {v!r}"
        else:
            assert got == v, f"{k}: {got!r} != {v!r}"


# ---------------------------------------------------------------------------
# Tokenisation et conversions
# ---------------------------------------------------------------------------


def kinds(s: str, lang: str = "fr") -> list[tuple[str, object]]:
    return [(t.kind, t.value) for t in tokenize(s, lang=lang)]


def test_tokenize_date_glued_to_number() -> None:
    # Colonnes séparées par une seule espace : dividende puis date.
    assert kinds("704 18-sept.-26") == [("num", 704.0), ("date", dt.date(2026, 9, 18))]
    assert kinds("1919 25-sept.-00") == [("num", 1919.0), ("date", dt.date(2000, 9, 25))]
    assert kinds("201,52 30-sept.-26") == [("num", 201.52), ("date", dt.date(2026, 9, 30))]


def test_tokenize_percent_before_number() -> None:
    assert kinds("8,57 % 519,40") == [("pct", 8.57), ("num", 519.4)]
    assert kinds("-0,78 %") == [("pct", -0.78)]
    assert kinds("2 200,00 %") == [("pct", 2200.0)]
    assert kinds("79.94 %   37%") == [("pct", 79.94), ("pct", 37.0)]


def test_tokenize_never_merges_columns() -> None:
    # Deux colonnes séparées par 2+ espaces ne sont jamais fusionnées.
    assert kinds("738 457      2 988 573") == [("num", 738457.0), ("num", 2988573.0)]
    assert kinds("12 900     12 900     12 800") == [("num", 12900.0)] * 2 + [("num", 12800.0)]
    # Une espace simple suivie d'un groupe non conforme ne fusionne pas non plus.
    assert kinds("1 645 1 640") == [("num", 1645.0), ("num", 1640.0)]
    assert kinds("8 400          SP           SP") == [("num", 8400.0), ("mark", "SP"), ("mark", "SP")]


def test_parse_number() -> None:
    assert parse_number("12 737 890") == 12737890
    assert parse_number("1 500,00") == 1500
    assert parse_number("369,6") == pytest.approx(369.6)
    assert parse_number(",92") == pytest.approx(0.92)
    assert parse_number("1 041,") == 1041
    assert parse_number("-") is None
    assert parse_number("NC") is None
    assert parse_number("10,082,387,479,022", "en") == 10082387479022
    assert parse_number("276.13", "en") == pytest.approx(276.13)
    assert parse_number("114,56", "en") == pytest.approx(114.56)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("7-sept.-26", dt.date(2026, 9, 7)),
        ("23-mai-18", dt.date(2018, 5, 23)),
        ("9-janv.-18", dt.date(2018, 1, 9)),
        ("29-juin-26", dt.date(2026, 6, 29)),
        ("16-juil.-23", dt.date(2023, 7, 16)),
        ("12-août-11", dt.date(2011, 8, 12)),
        ("14-févr.-27", dt.date(2027, 2, 14)),
        ("28-déc.-21", dt.date(2021, 12, 28)),
        ("5-juil.-99", dt.date(1999, 7, 5)),
        ("12 Sep 24", dt.date(2024, 9, 12)),
        ("02 janvier 2023", dt.date(2023, 1, 2)),
        ("1er juin 2020", dt.date(2020, 6, 1)),
        ("june 14, 1999", dt.date(1999, 6, 14)),
        ("pas une date", None),
    ],
)
def test_parse_french_date(text: str, expected: dt.date | None) -> None:
    assert parse_french_date(text) == expected


def test_warning_code() -> None:
    assert warning_code("change_mismatch: SNTS: 1 vs 2") == "change_mismatch"


# ---------------------------------------------------------------------------
# Contrôles génériques sur les cinq années
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("stamp", MAIN_FIXTURES)
def test_generic_invariants(days: dict[str, BocDay], stamp: str) -> None:
    day = days[stamp]
    eq = day.equities
    assert day.date == dt.datetime.strptime(stamp, "%Y%m%d").date()
    assert list(eq.columns) == EQUITY_COLUMNS
    assert list(day.indices.columns) == INDEX_COLUMNS
    assert list(day.order_book.columns) == ORDER_BOOK_COLUMNS
    # Une ligne par société cotée (45-48 selon les années), sans doublon.
    assert 45 <= len(eq) <= 48
    assert len(eq) == day.market["n_listed"]
    assert not eq["symbol"].duplicated().any()
    assert eq["symbol"].str.fullmatch(r"[A-Z]{4,5}").all()
    # Les sommes recoupent la ligne « TOTAL - Marché des actions ».
    assert eq["volume"].sum() == day.market["equity_total_volume"]
    assert eq["value"].sum() == day.market["equity_total_value"]
    # Statuts et règle du cours de clôture.
    assert set(eq["status"]) <= {"traded", "not_traded", "suspended"}
    assert (eq["close"] > 0).all()
    untraded = eq[eq["status"] != "traded"]
    moved = (untraded["change_pct"] != 0) & (untraded["close"] == untraded["ref_price"])
    assert ((untraded["close"] == untraded["prev_close"]) | moved).all()
    assert untraded["volume"].isna().all() and untraded["open"].isna().all()
    traded = eq[eq["status"] == "traded"]
    implied = (traded["close"] / traded["prev_close"] - 1) * 100
    assert ((implied - traded["change_pct"]).abs() < 0.02).all()
    # Valeur ≈ volume × cours (ordre de grandeur).
    ratio = traded["value"] / (traded["volume"] * traded["close"])
    assert ratio.between(0.85, 1.15).all()
    # Rendement ≈ dividende / cours quand les deux sont publiés.
    both = eq.dropna(subset=["last_div_net", "net_yield_pct"])
    yld = both["last_div_net"] / both["close"] * 100
    assert ((yld - both["net_yield_pct"]).abs() < 0.15 + 0.05 * both["net_yield_pct"]).all()
    assert eq["sector"].notna().all()
    # Pas d'anomalie (seules des réparations informatives sont tolérées).
    assert {warning_code(w) for w in day.warnings} <= {"wrapped_digits_joined"}
    # Le carnet d'ordres couvre les mêmes titres.
    assert set(day.order_book["symbol"]) == set(eq["symbol"])
    assert day.indices["level"].notna().all()


# ---------------------------------------------------------------------------
# 2026-11-20 (format « Code Sect. » sous le symbole, compartiments, Total Return)
# ---------------------------------------------------------------------------


def test_2026_snts(days: dict[str, BocDay]) -> None:
    r = row(days["20261120"], "SNTS")
    # NB : la valeur transigée est imprimée « 2 988 573 » avec « 270 » renvoyé sur la
    # ligne suivante (sous la colonne) : 2 988 573 270 FCFA. Vérifications : somme du
    # compartiment PRESTIGE = TOTAL publié (3 322 470 470) et 738 457 × ~4 047 FCFA.
    assert_row(
        r, prev_close=4090.0, open=4080.0, close=4040.0, change_pct=-1.22, volume=738457.0,
        value=2988573270.0, ref_price=4040.0, ytd_pct=54.67, last_div_net=174.0,
        last_div_date=dt.date(2026, 5, 26), net_yield_pct=4.31, per=9.77,
        sector="TEL", compartment="PRESTIGE", status="traded", name="SONATEL SN",
    )
    assert r["value"] / r["volume"] == pytest.approx(4047, abs=10)
    assert "wrapped_digits_joined" in r["warnings"]


def test_2026_suspended_and_two_line_names(days: dict[str, BocDay]) -> None:
    d = days["20261120"]
    assert_row(row(d, "SICC"), status="suspended", prev_close=8400.0, close=8400.0, open=None,
               volume=None, value=None, ref_price=8400.0, ytd_pct=154.55, last_div_net=1919.0,
               last_div_date=dt.date(2000, 9, 25), net_yield_pct=None, per=None, sector="CB")
    assert_row(row(d, "SEMC"), status="suspended", name="SONOCO METAL PACKAGING SIEM S.",
               close=1495.0, net_yield_pct=0.94, per=37.21, sector="IND")
    assert_row(row(d, "TTLC"), name="TOTALENERGIES MARKETING CI", sector="ENE", close=2990.0)
    assert_row(row(d, "SGBC"), name="SOCIETE GENERALE COTE D'IVOIRE", last_div_net=2298.75)
    assert_row(row(d, "ECOC"), name="ECOBANK COTE D'IVOIRE")  # « D''IVOIRE » normalisé
    assert_row(row(d, "SIVC"), name="ERIUM CI (Ex AIR LIQUIDE CI)", net_yield_pct=None, per=77.94)


def test_2026_tricky_columns(days: dict[str, BocDay]) -> None:
    d = days["20261120"]
    # « 704 18-sept.-26 » : dividende et date collés par une seule espace.
    assert_row(row(d, "SMBC"), last_div_net=704.0, last_div_date=dt.date(2026, 9, 18), per=10.73)
    # « 8,57 % 519,40 » : rendement et PER collés.
    assert_row(row(d, "BNBC"), net_yield_pct=8.57, per=519.40)
    # Ni variation annuelle, ni dividende, ni rendement : le nombre isolé est le PER.
    assert_row(row(d, "BBGC"), ytd_pct=None, last_div_net=None, net_yield_pct=None, per=14.97,
               volume=9592.0, value=79798610.0, ref_price=8145.0)
    # Dividende sans rendement : le nombre après la date est le PER.
    assert_row(row(d, "UNLC"), last_div_net=1233.0, last_div_date=dt.date(2012, 7, 9),
               net_yield_pct=None, per=631.03, volume=2.0, value=87950.0)
    # Dividende « ,92 ».
    assert_row(row(d, "ETIT"), last_div_net=0.92, prev_close=57.0, open=56.0, close=57.0,
               volume=950024.0, value=52268184.0, name="ECOBANK TRANS. INCORP. TG")
    # PER absent en fin de ligne.
    assert_row(row(d, "SCRC"), net_yield_pct=3.29, per=None)
    assert_row(row(d, "FTSC"), net_yield_pct=107.91, per=48.43)


def test_2026_indices(days: dict[str, BocDay]) -> None:
    d = days["20261120"]
    assert_row(idx(d, "BRVM COMPOSITE"), level=492.89, change_pct=-0.21, ytd_pct=42.56, family="headline")
    assert_row(idx(d, "BRVM 30"), level=238.73, change_pct=-0.29, ytd_pct=43.61)
    assert_row(idx(d, "BRVM PRESTIGE"), level=186.61, change_pct=-0.03, ytd_pct=29.37,
               n_companies=12.0, volume=758339.0, value=3322470470.0, per=13.21)
    assert_row(idx(d, "BRVM PRINCIPAL"), level=337.96, change_pct=-0.35, ytd_pct=55.28, n_companies=36.0)
    assert_row(idx(d, "BRVM COMPOSITE TOTAL RETURN"), level=198.63, change_pct=-0.22, ytd_pct=49.19,
               family="total_return", base_date=dt.date(2025, 1, 2))
    assert_row(idx(d, "BRVM - TELECOMMUNICATIONS (base 2025)"), level=137.33, change_pct=-0.17,
               ytd_pct=44.71, n_companies=3.0, per=12.91, family="sector")
    assert_row(idx(d, "BRVM - SERVICES PUBLICS (base 2025)"), level=199.96, ytd_pct=88.82)
    assert len(d.indices) == 12


def test_2026_market_and_order_book(days: dict[str, BocDay]) -> None:
    d = days["20261120"]
    m = d.market
    assert m["market_cap"] == 19328818938929
    assert m["market_cap_chg_pct"] == -0.21
    assert m["bond_market_cap"] == 13424990989851
    assert m["volume"] == 1811601 and m["value"] == 3892842384
    assert m["n_traded"] == 46 and m["n_up"] == 19 and m["n_down"] == 19 and m["n_unchanged"] == 8
    assert m["avg_per"] == 15.79 and m["avg_yield_pct"] == 7.12 and m["avg_return_pct"] == 7.14
    assert m["n_listed"] == 48 and m["n_bond_lines"] == 210 and m["n_sgi"] == 36
    assert m["avg_session_value_ytd"] == pytest.approx(3092021750.78)
    assert m["risk_premium"] == 0.58
    # Meilleures limites : « SNTS  SONATEL SN  30  4,010 / 4,040  3 985  4 040 ».
    assert_row(ob(d, "SNTS"), bid_qty=30.0, bid=4010.0, ask=4040.0, ask_qty=3985.0, ref_price=4040.0)
    assert_row(ob(d, "ETIT"), bid_qty=6930.0, bid=56.0, ask=57.0, ask_qty=788369.0, ref_price=57.0)
    assert_row(ob(d, "SAFC"), bid_qty=None, bid=None, ask=3030.0, ask_qty=93.0)
    assert_row(ob(d, "UNLC"), bid_qty=5.0, bid=43950.0, ask=None, ask_qty=None, ref_price=44000.0)
    assert_row(ob(d, "SICC"), bid=None, ask=None, ref_price=8400.0)


# ---------------------------------------------------------------------------
# 2018-06-01 (format par secteur, NC, ex-dividende)
# ---------------------------------------------------------------------------


def test_2018_snts(days: dict[str, BocDay]) -> None:
    assert_row(
        row(days["20180601"], "SNTS"), prev_close=22300.0, open=22500.0, close=22400.0,
        change_pct=0.45, volume=4004.0, value=89364840.0, ref_price=22400.0, ytd_pct=-4.68,
        last_div_net=1500.0, last_div_date=dt.date(2018, 5, 23), net_yield_pct=6.70, per=11.08,
        sector="SPU", compartment="SERVICES PUBLICS", status="traded",
    )


def test_2018_not_traded_and_special_rows(days: dict[str, BocDay]) -> None:
    d = days["20180601"]
    assert_row(row(d, "SEMC"), status="not_traded", prev_close=13750.0, open=None, close=13750.0,
               volume=None, value=None, ref_price=13750.0, ytd_pct=-0.90, last_div_net=676.80,
               last_div_date=dt.date(2017, 9, 29), net_yield_pct=4.92, per=18.26, sector="IND")
    assert_row(row(d, "TTRC"), status="suspended", name="TRITURAF CI-Ste en Liquidation",
               last_div_net=1440.0, last_div_date=dt.date(2002, 7, 19), per=None)
    # (d) : ex-dividende, référence ajustée pour la séance suivante (8 895 - 727,91).
    assert_row(row(d, "ONTBF"), ex_div=True, flags="(D)", close=8895.0, ref_price=8170.0,
               last_div_net=727.91, last_div_date=dt.date(2018, 6, 6), net_yield_pct=8.18)
    # Nombre isolé après la variation annuelle : PER (pas de dividende).
    assert_row(row(d, "ECOC"), last_div_net=None, per=10.37, net_yield_pct=None)
    # « 0,00 » sans date puis PER.
    assert_row(row(d, "NSBC"), last_div_net=0.0, last_div_date=None, per=10.55)
    assert_row(row(d, "FTSC"), last_div_date=dt.date(2018, 1, 9), net_yield_pct=14.39, per=22.07)
    assert_row(row(d, "SLBC"), status="not_traded", last_div_net=4101.0, ytd_pct=-39.12)
    assert_row(row(d, "STAC"), sector="AUT", last_div_net=0.0, per=3.56)
    assert_row(row(d, "SDSC"), sector="TRP", name="BOLLORE")


def test_2018_indices_market_order_book(days: dict[str, BocDay]) -> None:
    d = days["20180601"]
    assert_row(idx(d, "BRVM 10"), level=204.65, change_pct=0.0, ytd_pct=-6.83)
    assert_row(idx(d, "BRVM COMPOSITE"), level=217.72, change_pct=-0.31, ytd_pct=-10.43)
    assert_row(idx(d, "BRVM - INDUSTRIE (base 1999)"), level=83.29, change_pct=-0.39, ytd_pct=-19.14,
               n_companies=12.0, volume=386.0, value=984445.0, per=23.78, base_date=dt.date(1999, 6, 14))
    assert "BRVM - PETITES CAPITALISATIONS (base 1999)" not in set(d.indices["index"])  # que des tirets
    assert d.market["market_cap"] == 6123566289400
    assert d.market["avg_per"] == 13.91 and d.market["n_listed"] == 45
    assert d.market["avg_session_value_ytd"] == pytest.approx(12220019.67)
    assert_row(ob(d, "CABC"), ask_at_market=True, ask=None, ask_qty=10.0, ref_price=1650.0, bid=None)
    assert_row(ob(d, "PRSC"), ask=183000.0, ask_qty=1.0, ref_price=183990.0)
    assert_row(ob(d, "ETIT"), bid_qty=22238.0, bid=20.0, ask=21.0, ask_qty=31481.0, ref_price=21.0)


# ---------------------------------------------------------------------------
# 2020-03-02
# ---------------------------------------------------------------------------


def test_2020_rows(days: dict[str, BocDay]) -> None:
    d = days["20200302"]
    assert_row(row(d, "SNTS"), prev_close=14995.0, open=14800.0, close=15500.0, change_pct=3.37,
               volume=771.0, value=11487975.0, ref_price=15500.0, ytd_pct=-8.80, last_div_net=1500.0,
               last_div_date=dt.date(2019, 5, 14), net_yield_pct=9.68, per=7.88, sector="SPU")
    assert_row(row(d, "NTLC"), status="not_traded", close=280.0, ytd_pct=-29.11, last_div_net=31.50,
               last_div_date=dt.date(2011, 8, 12), net_yield_pct=None, per=7.54)
    assert_row(row(d, "UNLC"), status="suspended", close=2500.0, last_div_net=1233.0, per=None)
    assert_row(row(d, "SEMC"), status="not_traded", net_yield_pct=14.10, per=None)
    assert_row(row(d, "SGBC"), name="SOCIETE GENERALE COTE D'IVOIRE", volume=1611.0, value=13935705.0)
    assert_row(row(d, "ECOC"), name="ECOBANK COTE D'IVOIRE")
    # Ligne TOTAL du secteur TRANSPORT imprimée sur la page suivante.
    assert_row(row(d, "SDSC"), sector="TRP", volume=6310.0, value=12049700.0, per=9.99)
    assert_row(row(d, "PRSC"), sector="DIS", last_div_date=dt.date(2019, 9, 18), net_yield_pct=4.83)


def test_2020_indices_market_order_book(days: dict[str, BocDay]) -> None:
    d = days["20200302"]
    assert_row(idx(d, "BRVM COMPOSITE"), level=148.61, change_pct=1.78, ytd_pct=-6.68)
    assert_row(idx(d, "BRVM 10"), level=139.15, change_pct=2.44, ytd_pct=-6.68)
    assert_row(idx(d, "BRVM - SERVICES PUBLICS (base 1999)"), level=461.14, change_pct=3.71, n_companies=4.0)
    assert d.market["market_cap"] == 4424073285276 and d.market["avg_trend_ratio"] == 2396.53
    assert d.market["bond_volume"] == 800 and d.market["bond_value"] == 8000000
    assert_row(ob(d, "ETIT"), ask_at_market=True, ask_qty=1609365.0, ref_price=13.0, bid=None)
    assert_row(ob(d, "SDSC"), bid_qty=1365.0, bid=1900.0, ask=1920.0, ask_qty=1515.0, ref_price=1910.0)


# ---------------------------------------------------------------------------
# 2023-06-01 (code secteur en tête de ligne, compartiments)
# ---------------------------------------------------------------------------


def test_2023_rows(days: dict[str, BocDay]) -> None:
    d = days["20230601"]
    assert_row(row(d, "SNTS"), prev_close=15000.0, open=14995.0, close=14990.0, change_pct=-0.07,
               volume=855.0, value=12820470.0, ytd_pct=-1.38, last_div_net=1500.0,
               last_div_date=dt.date(2023, 5, 30), net_yield_pct=10.01, per=5.37,
               sector="SPU", compartment="PRESTIGE")
    assert_row(row(d, "ETIT"), name="ECOBANK TRANS. INCORP. TG", sector="FIN", volume=368864.0,
               value=6380503.0, last_div_net=0.90, last_div_date=dt.date(2022, 6, 20), per=1.34)
    assert_row(row(d, "SICC"), status="not_traded", close=6315.0, net_yield_pct=None, per=3.83,
               compartment="PRINCIPAL", sector="AGR")
    assert_row(row(d, "SVOC"), status="suspended", sector="TRP", last_div_date=dt.date(1999, 7, 5))
    # « ORANGE COTE D''''IVOIRE », sans dividende : seul le PER suit la variation annuelle.
    assert_row(row(d, "ORAC"), name="ORANGE COTE D'IVOIRE", last_div_net=None, per=9.40, ytd_pct=-6.22)
    assert_row(row(d, "SLBC"), open=73075.0, close=73075.0, change_pct=-7.50, per=98.82)
    assert_row(row(d, "FTSC"), net_yield_pct=20.09, per=107.51)  # « 20,09 % 107,51 »
    assert_row(row(d, "STAC"), sector="AUT", per=None, net_yield_pct=6.04)
    assert_row(row(d, "SIVC"), last_div_date=dt.date(2017, 9, 29), net_yield_pct=None, per=12.79)


def test_2023_indices_market(days: dict[str, BocDay]) -> None:
    d = days["20230601"]
    assert_row(idx(d, "BRVM COMPOSITE"), level=195.04, change_pct=-0.24, ytd_pct=-4.03)
    assert_row(idx(d, "BRVM 30"), level=97.75, change_pct=-0.09, ytd_pct=-2.25)
    assert_row(idx(d, "BRVM PRESTIGE"), level=99.27, change_pct=-0.17, n_companies=10.0, per=6.06)
    assert_row(idx(d, "BRVM PRINCIPAL"), level=93.77, change_pct=-0.31, ytd_pct=-6.23, value=121444175.0)
    assert_row(idx(d, "BRVM - AUTRES SECTEURS (base 1999)"), level=1351.10, per=None, volume=32.0)
    assert d.market["market_cap"] == 7256073749714
    assert d.market["bond_volume"] == 52946 and d.market["bond_volume_chg_pct"] == 2200.0
    assert d.market["avg_per"] == 9.05 and d.market["avg_coverage_ratio"] == 171.13
    assert_row(ob(d, "ETIT"), bid_qty=3286185.0, bid=16.0, ask=17.0, ask_qty=179446.0)


# ---------------------------------------------------------------------------
# 2024-06-14
# ---------------------------------------------------------------------------


def test_2024_rows(days: dict[str, BocDay]) -> None:
    d = days["20240614"]
    assert_row(row(d, "SNTS"), prev_close=19250.0, open=19250.0, close=19330.0, change_pct=0.42,
               volume=1694.0, value=32470150.0, ref_price=19330.0, ytd_pct=7.51, last_div_net=1575.0,
               last_div_date=dt.date(2024, 5, 17), net_yield_pct=8.15, per=5.83)
    assert_row(row(d, "BICC"), prev_close=10300.0, open=10650.0, close=10410.0, change_pct=1.07)
    assert_row(row(d, "SLBC"), status="suspended", close=83250.0, ytd_pct=-4.31, last_div_net=4050.0,
               last_div_date=dt.date(2022, 8, 12), net_yield_pct=4.86, per=9.09)
    assert_row(row(d, "SEMC"), name="EVIOSYS PACKAGING SIEM CI", status="suspended")
    assert_row(row(d, "SDSC"), name="AFRICA GLOBAL LOGISTICS CI", last_div_net=92.0,
               last_div_date=dt.date(2023, 11, 20), net_yield_pct=6.81, per=4.29, sector="TRP")
    assert_row(row(d, "BNBC"), net_yield_pct=15.87, per=173.88)
    assert_row(row(d, "UNLC"), status="not_traded", close=6500.0, ytd_pct=30.0)
    assert_row(row(d, "SPHC"), last_div_net=294.30, last_div_date=dt.date(2023, 9, 29), net_yield_pct=11.80)
    assert_row(row(d, "CABC"), volume=3.0, value=2970.0, change_pct=-5.71)


def test_2024_indices_market_order_book(days: dict[str, BocDay]) -> None:
    d = days["20240614"]
    assert_row(idx(d, "BRVM COMPOSITE"), level=228.88, change_pct=0.57, ytd_pct=6.88)
    assert_row(idx(d, "BRVM 30"), level=114.25, change_pct=0.60, ytd_pct=5.93)
    assert_row(idx(d, "BRVM PRESTIGE"), level=107.72, change_pct=-0.13, ytd_pct=6.16)
    assert_row(idx(d, "BRVM PRINCIPAL"), level=110.30, change_pct=0.94, ytd_pct=6.10)
    assert d.market["market_cap"] == 8515055597424 and d.market["avg_per"] == 7.92
    assert_row(ob(d, "SNTS"), bid_qty=18.0, bid=19110.0, ask=19330.0, ask_qty=25.0, ref_price=19330.0)
    assert_row(ob(d, "SICC"), ask_at_market=True, ask_qty=10.0, ref_price=3400.0)


# ---------------------------------------------------------------------------
# Cas limites réels (tests/fixtures/edge_cases)
# ---------------------------------------------------------------------------


def edge(stamp: str) -> BocDay:
    return parse_boc_file(FIX / "edge_cases" / f"boc_{stamp}.txt.gz")


def test_split_thousands_group_across_lines() -> None:
    # « 25 316 630 27 » + « 5 » sur la ligne suivante (ORGT, 24/08/2022).
    d = edge("20220824")
    assert_row(row(d, "ORGT"), volume=6100481.0, value=25316630275.0, close=4150.0, per=14.55)
    assert not [w for w in d.warnings if "total_mismatch" in w or "unparsed" in w]


def test_decimals_wrapped_to_next_line() -> None:
    # PER « 1 041, » + « 59 » (BNBC, 13/05/2025) ; le code secteur suit sur la même ligne.
    d = edge("20250513")
    assert_row(row(d, "BNBC"), per=1041.59, sector="CD", net_yield_pct=13.04)


def test_marker_split_across_lines_and_rights_adjustment() -> None:
    # « SAFCA CI  (Ex- » / « d) » : marqueur ex-droit coupé, référence ajustée (3 890).
    d = edge("20260423")
    assert_row(row(d, "SAFC"), name="SAFCA CI", flags="(EX-D)", sector="FIN", close=5505.0,
               ref_price=3890.0, per=63.76)


def test_first_listing_row() -> None:
    # LNBB, première cotation le 13/12/2024 : ni cours précédent ni variation.
    d = edge("20241213")
    assert_row(row(d, "LNBB"), prev_close=None, change_pct=None, open=5025.0, close=5160.0,
               volume=17049.0, value=84893375.0, ref_price=5160.0, status="traded",
               name="LOTERIE NATIONALE DU BENIN", sector="AUT")
    assert "first_listing" in row(d, "LNBB")["warnings"]
    assert not [w for w in d.warnings if "total_mismatch" in w]


def test_english_bulletin() -> None:
    # BOC du 02/01/2025 publié en anglais (virgule des milliers, « 12 Sep 24 », rendement en fraction).
    d = edge("20250102")
    assert d.meta["lang"] == "en" and d.date == dt.date(2025, 1, 2)
    assert len(d.equities) == 47 == d.market["n_listed"]
    assert_row(row(d, "TTLC"), prev_close=2500.0, open=2500.0, close=2480.0, change_pct=-0.80,
               volume=2039.0, value=4973040.0, last_div_net=199.54, last_div_date=dt.date(2024, 9, 12),
               net_yield_pct=8.05, per=17.93, name="TOTALENERGIES MARKETING CI", sector="ENE")
    assert_row(row(d, "SICC"), last_div_net=1919.0, last_div_date=dt.date(2000, 9, 25),
               net_yield_pct=None, per=124.71)
    assert_row(row(d, "BICC"), status="not_traded", close=14000.0)
    assert_row(idx(d, "BRVM COMPOSITE"), level=276.13, change_pct=0.04, ytd_pct=0.04)
    assert_row(idx(d, "BRVM 30"), level=138.71, change_pct=-0.02)
    assert_row(idx(d, "BRVM PRESTIGE"), level=114.56, change_pct=-0.24, n_companies=10.0)
    assert_row(idx(d, "BRVM - CONSOMMATION DISCRETIONNAIRE (base 2025)"), level=100.46, change_pct=None,
               ytd_pct=0.0)
    assert d.market["market_cap"] == 10082387479022 and d.market["avg_per"] == 11.26
    assert d.market["n_listed"] == 47 and d.market["avg_session_value_ytd"] == 1730101361


# ---------------------------------------------------------------------------
# Robustesse
# ---------------------------------------------------------------------------


def test_date_from_argument_and_mismatch() -> None:
    text = read_boc_text(FIX / "boc_20240614.txt.gz")
    d = parse_boc_text(text, date="2024-06-13")
    assert d.date == dt.date(2024, 6, 13)
    assert d.meta["header_date"] == dt.date(2024, 6, 14)
    assert any(warning_code(w) == "date_mismatch" for w in d.warnings)
    assert parse_boc_text(text).date == dt.date(2024, 6, 14)


def test_plain_text_file(tmp_path: Path) -> None:
    p = tmp_path / "boc_20180601.txt"
    p.write_text(read_boc_text(FIX / "boc_20180601.txt.gz"), encoding="utf-8")
    d = parse_boc_file(p)
    assert len(d.equities) == 45 and d.meta["file"] == "boc_20180601.txt"


def test_garbage_does_not_raise() -> None:
    d = parse_boc_text("rien d'utile ici\n\fpage 2\n", date=dt.date(2020, 1, 2))
    assert d.date == dt.date(2020, 1, 2)
    assert d.equities.empty and list(d.equities.columns) == EQUITY_COLUMNS
    assert any(warning_code(w) == "no_equity_table" for w in d.warnings)


def test_english_bulletin_2022_sector_groups() -> None:
    # BOC anglais de 2022 : groupes « INDUSTRY - SECTOR », indices « MARKET INDICES BY SECTOR ».
    d = edge("20220112")
    assert d.meta["lang"] == "en" and len(d.equities) == 46
    assert_row(row(d, "SNTS"), sector="SPU", compartment="SERVICES PUBLICS", close=13900.0)
    assert_row(row(d, "STAC"), sector="AUT", compartment="AUTRES SECTEURS")
    assert_row(row(d, "SHEC"), last_div_net=63.90, last_div_date=dt.date(2020, 11, 26), per=None,
               net_yield_pct=pytest.approx(63.90 / 890 * 100, abs=0.01))
    assert_row(idx(d, "BRVM - INDUSTRIE (base 1999)"), level=109.39, change_pct=0.60, ytd_pct=-0.65)
    assert_row(idx(d, "BRVM - AUTRES SECTEURS (base 1999)"), level=931.58, n_companies=1.0)
    assert_row(idx(d, "BRVM 10"), level=158.46, change_pct=-0.01, ytd_pct=3.22)
    assert_row(ob(d, "ABJC"), bid_qty=142.0, bid=1505.0, ask=1515.0, ask_qty=190.0, ref_price=1515.0)
    assert {warning_code(w) for w in d.warnings} == {"lang_en"}


def test_ex_dividend_day_and_unflagged_ex_date() -> None:
    # Veille de détachement (marqueur « (v) ») : référence ajustée dans la cote, non
    # ajustée dans le carnet d'ordres -> pas d'avertissement de carnet.
    d0 = edge("20210503")
    assert_row(row(d0, "BOAN"), close=3960.0, ref_price=3535.0, last_div_net=429.66)
    assert_row(ob(d0, "BOAN"), ref_price=3960.0)
    assert not [w for w in d0.warnings if warning_code(w) == "order_book_ref_mismatch"]
    # Jour de détachement : précédent publié 3 960 (non ajusté), variation +7,21 % calculée
    # sur la référence 3 535 -> réconcilié, pas de « change_mismatch ».
    d1 = edge("20210504")
    r = row(d1, "BOAN")
    assert_row(r, prev_close=3960.0, close=3790.0, change_pct=7.21)
    assert "change_vs_adjusted_ref" in r["warnings"]
    assert not [w for w in d1.warnings if warning_code(w) == "change_mismatch"]


def test_untraded_reference_moved_by_exchange() -> None:
    # SAFC 09/01/2019 : NC, mais référence 215 -> 210 et variation -2,33 % publiée.
    d = edge("20190109")
    r = row(d, "SAFC")
    assert_row(r, status="not_traded", prev_close=215.0, close=210.0, ref_price=210.0, change_pct=-2.33)
    assert "untraded_ref_change" in r["warnings"]


# ---------------------------------------------------------------------------
# BOC historiques (jusqu'à novembre 2017)
# ---------------------------------------------------------------------------


def test_legacy_2017_layout() -> None:
    # Colonnes : volume, valeur, préc., ouv., clôt., moyen, var., var. an., réf., seuils
    # bas/haut, dividende, date, compartiment (« 1er »/« 2eme »), rendement, PER.
    d = edge("20170124")
    assert d.meta["legacy_layout"] is True
    assert len(d.equities) == 43 == d.market["n_listed"]
    assert d.equities["volume"].sum() == d.market["equity_total_volume"] == 2192005
    assert d.equities["value"].sum() == d.market["equity_total_value"] == 388706501
    assert_row(row(d, "SNTS"), volume=1223.0, value=29382820.0, prev_close=24300.0, open=24200.0,
               close=24000.0, change_pct=-1.23, ytd_pct=-4.0, ref_price=24000.0, last_div_net=1500.0,
               last_div_date=dt.date(2016, 5, 10), net_yield_pct=6.25, per=10.86, sector="SPU")
    # Non coté : variation du jour vide, variation annuelle lue à sa place.
    assert_row(row(d, "CABC"), status="not_traded", close=79100.0, change_pct=None, ytd_pct=-9.60,
               last_div_net=1200.0, last_div_date=dt.date(2016, 7, 28), net_yield_pct=1.52, per=16.70)
    assert_row(row(d, "FTSC"), name="FILTISAC CI", flags="(*)", net_yield_pct=12.41, per=18.40)
    assert_row(row(d, "ETIT"), volume=2179424.0, value=52306176.0, close=24.0, last_div_net=2.0, per=6.78)
    assert_row(row(d, "TTRC"), status="suspended", close=490.0)
    assert_row(idx(d, "BRVM 10"), level=248.24, change_pct=-0.49, ytd_pct=-5.23)
    assert_row(idx(d, "BRVM COMPOSITE"), level=277.59, change_pct=-0.49, ytd_pct=-4.99)
    # Indices sectoriels lus dans les en-têtes de groupe (« SECTEUR - INDUSTRIE 146,08 points -1,10% »).
    assert_row(idx(d, "BRVM - INDUSTRIE (base 1999)"), level=146.08, change_pct=-1.10, ytd_pct=None)
    assert_row(idx(d, "BRVM - TRANSPORT (base 1999)"), level=1301.03, change_pct=0.0)
    m = d.market
    assert m["market_cap"] == 7332030000000 and m["bond_market_cap"] == 2489500000000  # milliards
    assert m["avg_per"] == 23.05 and m["n_sgi"] == 23 and m["avg_liquidity_ratio"] == 69.94
    assert (m["n_traded"], m["n_up"], m["n_unchanged"], m["n_down"]) == (33, 10, 10, 13)
    # Carnet d'ordres historique : prix sans séparateur, « - » pour les cases vides.
    assert_row(ob(d, "CABC"), bid_qty=1.0, bid=79150.0, ask=85000.0, ask_qty=14.0, ref_price=79100.0)
    assert_row(ob(d, "NEIC"), bid_qty=2.0, bid=3200.0, ask=None, ask_qty=None, ref_price=3000.0)
    assert_row(ob(d, "SEMC"), name="CROWN SIEM CI", bid=None, ask=44990.0, ask_qty=5.0)
    assert_row(ob(d, "STAC"), ask_at_market=True, ask_qty=7.0, ref_price=33000.0)
    assert {warning_code(w) for w in d.warnings} <= {"yield_mismatch"}


def test_legacy_order_book_before_price_table() -> None:
    # 30/11/2017 : le carnet d'ordres précède la cote (pages permutées).
    d = edge("20171130")
    # 44 lignes de carnet, dont 2 sans aucun ordre (« TTRC ... -  -  -  490 », sans « / »).
    assert len(d.equities) == 44 == d.market["n_listed"] and len(d.order_book) == 44
    assert_row(row(d, "SNTS"), volume=32356.0, value=740743790.0, prev_close=22505.0, close=22900.0,
               change_pct=1.76, ytd_pct=-8.40, last_div_date=dt.date(2017, 5, 15), net_yield_pct=6.55, per=10.61)
    assert_row(row(d, "NTLC"), net_yield_pct=None, per=42.84, last_div_net=31.5)
    assert_row(ob(d, "CABC"), bid_qty=37.0, bid=950.0, ask=970.0, ask_qty=62.0, ref_price=950.0)
    assert_row(ob(d, "NEIC"), name="NEI-CEDA CI", ask_at_market=True, ask_qty=75.0, ref_price=40.0)
    assert not d.warnings


def test_number_split_by_stray_space() -> None:
    # 22/12/2017 : cours précédent imprimé « 4 30 » (430) -> recollé.
    d = edge("20171222")
    r = row(d, "SIVC")
    assert_row(r, prev_close=430.0, open=430.0, close=430.0, change_pct=0.0, volume=77.0, value=33110.0, per=54.35)
    assert "split_number_joined" in r["warnings"]
