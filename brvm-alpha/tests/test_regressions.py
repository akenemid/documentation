"""Tests de non-régression des anomalies relevées par les vérificateurs (parseur et magasin).

Parseur : BOC réels copiés dans ``tests/fixtures/regressions`` (valeurs attendues
relevées à la main dans le texte, ``zcat tests/fixtures/regressions/boc_AAAAMMJJ.txt.gz``).

Magasin : séquences synthétiques reprenant les chiffres exacts des BOC concernés
(dates, cours, références, marqueurs), puis contrôles sur le panel réel
``data/panel`` s'il existe.
"""

from __future__ import annotations

import datetime as dt
import math
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from brvm_alpha.data.boc_parser import BocDay, parse_boc_file, parse_boc_text, read_boc_text, warning_code
from brvm_alpha.data.store import adjusted_table, detect_corporate_actions, detect_dividends

REG = Path(__file__).parent / "fixtures" / "regressions"
PANEL = Path(__file__).resolve().parents[1] / "data" / "panel"


def day(stamp: str) -> BocDay:
    return parse_boc_file(REG / f"boc_{stamp}.txt.gz")


def row(d: BocDay, symbol: str) -> pd.Series:
    sel = d.equities[d.equities["symbol"] == symbol]
    assert len(sel) == 1, f"{symbol}: {len(sel)} lignes"
    return sel.iloc[0]


def idx(d: BocDay, name: str) -> pd.Series:
    sel = d.indices[d.indices["index"] == name]
    assert len(sel) == 1, f"{name}: {sorted(d.indices['index'])}"
    return sel.iloc[0]


def ob(d: BocDay, symbol: str) -> pd.Series:
    sel = d.order_book[d.order_book["symbol"] == symbol]
    assert len(sel) == 1, f"{symbol}: {len(sel)} lignes"
    return sel.iloc[0]


def check(r: pd.Series, **expected: object) -> None:
    for k, v in expected.items():
        got = r[k]
        if v is None:
            assert got is None or got is pd.NaT or (isinstance(got, float) and math.isnan(got)), f"{k}: {got!r}"
        elif isinstance(v, float):
            assert got == pytest.approx(v, abs=1e-9), f"{k}: {got!r} != {v!r}"
        elif isinstance(v, dt.date):
            assert pd.Timestamp(got) == pd.Timestamp(v), f"{k}: {got!r} != {v!r}"
        else:
            assert got == v, f"{k}: {got!r} != {v!r}"


def codes(d: BocDay) -> set[str]:
    return {warning_code(w) for w in d.warnings}


# ---------------------------------------------------------------------------
# Page 1 : indicateurs de marché
# ---------------------------------------------------------------------------


def test_market_columns_assigned_by_position_when_bond_column_is_shifted() -> None:
    # 27/05/2019 : la colonne Obligations est imprimée une ligne AU-DESSUS de la colonne
    # Actions ; l'ordre sur la ligne donnait les chiffres obligataires aux actions.
    m = day("20190527").market
    assert (m["volume"], m["value"]) == (36061, 221922320)  # = TOTAL - MARCHE DES ACTIONS
    assert (m["n_traded"], m["n_up"], m["n_down"], m["n_unchanged"]) == (39, 11, 15, 13)
    assert (m["bond_volume"], m["bond_value"]) == (151137, 1466369300)
    assert (m["bond_n_traded"], m["bond_n_up"], m["bond_n_down"], m["bond_n_unchanged"]) == (2, 0, 2, 0)
    assert m["market_cap"] == 4884208110796 and m["bond_market_cap"] == 3639981584698
    assert m["volume"] == m["equity_total_volume"] and m["value"] == m["equity_total_value"]


def test_market_bond_cap_alone_on_its_line_and_rights_cap() -> None:
    # 24/05/2019 : capitalisation obligataire seule sur sa ligne ; ligne « - Droits » distincte.
    m = day("20190524").market
    assert m["market_cap"] == 4880545688659 and m["bond_market_cap"] == 3649429189648
    assert m["rights_market_cap"] == 12534375
    assert (m["volume"], m["bond_volume"]) == (223842, 1118)


def test_market_volume_includes_rights_and_wrapped_rights_total() -> None:
    # 12/05/2026 : « Volume échangé (Actions & Droits) » = actions + droits ; le TOTAL des
    # droits a son dernier groupe de milliers renvoyé à la ligne (« 355 678 » / « 925 »).
    d = day("20260512")
    m = d.market
    assert (m["rights_total_volume"], m["rights_total_value"]) == (300388, 355678925)
    assert m["volume"] == m["equity_total_volume"] + m["rights_total_volume"] == 865336
    assert m["value"] == m["equity_total_value"] + m["rights_total_value"] == 1825517775
    assert "market_total_mismatch" not in codes(d)


def test_market_total_mismatch_is_reported() -> None:
    text = read_boc_text(REG / "boc_20190527.txt.gz")
    bad = text.replace("221 922 320", "221 922 330", 1)  # page 1 seulement
    assert "market_total_mismatch" in {warning_code(w) for w in parse_boc_text(bad, "2019-05-27").warnings}


# ---------------------------------------------------------------------------
# Tableaux d'indices
# ---------------------------------------------------------------------------


def test_total_return_index_with_control_characters() -> None:
    # Libellé brut « BRVM ²\x03COMPOSITE TOTAL RETURN » (23/03/2026).
    check(idx(day("20260323"), "BRVM COMPOSITE TOTAL RETURN"), level=155.18, change_pct=-1.38,
          ytd_pct=16.55, n_companies=47.0, per=13.98, family="total_return")


def test_index_rows_with_truncated_footnote_and_lost_letter() -> None:
    d = day("20251209")  # « BRVM-PRINCIPAL   (   37  220,56 ... »
    check(idx(d, "BRVM PRINCIPAL"), level=220.56, change_pct=-0.84, ytd_pct=59.70, n_companies=37.0, per=14.23)
    check(idx(d, "BRVM - INDUSTRIE (base 1999)"), level=269.47, change_pct=0.08, per=None)
    check(idx(d, "BRVM - CONSOMMATION DE BASE (base 2025)"), level=224.69, change_pct=-0.09)
    # 15/07/2026 : « RVM - CONSOMMATION DE BASE » (B perdu par pdftotext).
    check(idx(day("20260715"), "BRVM - CONSOMMATION DE BASE (base 2025)"), level=283.07, change_pct=-0.23,
          ytd_pct=31.0, per=10.41)


def test_garbled_index_per_is_left_empty() -> None:
    # 02/06/2025 : colonne PER moyen brouillée (« 1 , », « 7, », « , 8 », « 1 , 2 ») -> vide.
    d = day("20250602")
    for name in ("BRVM PRINCIPAL", "BRVM - FINANCES (base 1999)", "BRVM - INDUSTRIELS (base 2025)",
                 "BRVM - TRANSPORT (base 1999)"):
        assert math.isnan(idx(d, name)["per"]), name
    check(idx(d, "BRVM PRESTIGE"), per=9.73)  # cellule lisible conservée
    assert sum(warning_code(w) == "garbled_index_per" for w in d.warnings) == 14
    # Même brouillage sur une action : LNBB « 1 , » n'est pas un PER de 1.
    r = row(d, "LNBB")
    check(r, per=None, close=4800.0, ytd_pct=1.48)
    assert "garbled_cell" in r["warnings"]


@pytest.mark.parametrize("stamp, index, chg, ytd", [
    ("20170102", "BRVM 10", -2.79, -2.79),         # « Variation: » / « Variation / 31 » / valeur / « Déc. 2016: »
    ("20170102", "BRVM COMPOSITE", -2.39, -2.39),
    ("20171116", "BRVM 10", 0.05, -20.25),
    ("20171116", "BRVM COMPOSITE", 0.49, -22.64),  # « Variation / 30 » / valeur / « Déc. 2016: »
    ("20171123", "BRVM 10", -1.83, -21.90),        # « Variation / 30 Déc. 2016: -21,90% » sur une ligne
    ("20171123", "BRVM COMPOSITE", -1.46, -23.85),
    ("20171128", "BRVM 10", 0.98, -22.10),         # « Variation / 30 Déc. » / « 2016:  -22,10% »
    ("20171128", "BRVM COMPOSITE", 0.72, -24.27),
])
def test_legacy_headline_variations(stamp: str, index: str, chg: float, ytd: float) -> None:
    check(idx(day(stamp), index), change_pct=chg, ytd_pct=ytd)


# ---------------------------------------------------------------------------
# Lignes actions
# ---------------------------------------------------------------------------


def test_per_thousands_group_wrapped_with_sector_code() -> None:
    # « ... 10,99 %   1 » puis « CD ... 236,32 » : PER 1 236,32 et code secteur CD.
    check(row(day("20260102"), "BNBC"), per=1236.32, sector="CD", net_yield_pct=10.99, close=1365.0)
    d = day("20260213")
    check(row(d, "UNLC"), per=1147.32, sector="CB", last_div_net=1233.0, close=80000.0)
    check(row(d, "BNBC"), per=1426.52, sector="CD")
    assert "missing_sector" not in codes(d)


def test_truncated_sector_code_keeps_name_continuation() -> None:
    # 10/02/2025 : code secteur imprimé « C » sous LNBB (suivi de « BENIN ») et sous UNLC.
    d = day("20250210")
    r = row(d, "LNBB")
    check(r, name="LOTERIE NATIONALE DU BENIN", sector=None, close=4995.0, per=25.52)
    assert "truncated_sector" in r["warnings"]
    check(row(d, "UNLC"), name="UNILEVER CI", sector=None)


@pytest.mark.parametrize("stamp, symbol, name, flags, ex_div", [
    ("20241209", "SDSC", "AFRICA GLOBAL LOGISTICS CI", "(D)", True),  # « (d) » collé, nom sur 2 lignes
    ("20190916", "PRSC", "TRACTAFRIC MOTORS CI", "(D)", True),        # « (ex- » / « div) »
    ("20181226", "ECOC", "ECOBANK COTE D'IVOIRE", "(#)", False),      # « D'IVOIRE(#) », jour de division
    ("20171213", "CFAC", "CFAO MOTORS CI", "(#) VAL-T", False),       # « CI (#) » une espace
])
def test_markers_glued_to_name(stamp: str, symbol: str, name: str, flags: str, ex_div: bool) -> None:
    check(row(day(stamp), symbol), name=name, flags=flags, ex_div=ex_div)


def test_legacy_high_limit_not_read_as_dividend() -> None:
    # STAC 25/10/2017 : « 180 NC NC NC -48,57% 180 Val-T 170 180 ... 2eme - 2,17 » : le
    # seuil haut est imprimé 180 (au lieu de 190) ; la colonne dividende est vide.
    check(row(day("20171025"), "STAC"), last_div_net=None, last_div_date=None, per=2.17, ref_price=180.0,
          close=180.0, status="not_traded")


def test_legacy_first_listing_without_previous_close() -> None:
    # ECOC 12/12/2017 (introduction) : « 7 183  154 426 185  [vide]  21 500  21 500  21 499 ... ».
    r = row(day("20171212"), "ECOC")
    check(r, prev_close=None, open=21500.0, close=21500.0, volume=7183.0, value=154426185.0,
          ref_price=21500.0, status="traded")
    assert "first_listing" in r["warnings"]


# ---------------------------------------------------------------------------
# Lignes TOTAL de groupe
# ---------------------------------------------------------------------------


def test_group_total_wrapped_thousands_group() -> None:
    # 28/10/2026 : TOTAL PRESTIGE « 13 174 088 » / « 055 » = 13 174 088 055 (= somme des lignes).
    d = day("20261028")
    assert "group_total_mismatch" not in codes(d)
    text = read_boc_text(REG / "boc_20261028.txt.gz")
    lines = text.split("\n")
    k = next(i for i, ln in enumerate(lines) if "13 174 088" in ln and "TOTAL" in ln)
    lines[k + 1] = lines[k + 1].replace("055", "056")
    bad = parse_boc_text("\n".join(lines), "2026-10-28")
    assert any("13174088056" in w for w in bad.warnings if warning_code(w) == "group_total_mismatch")


def test_group_total_with_only_group_per_is_not_a_volume() -> None:
    # 12/02/2020 (anglais) : « TOTAL   10.66 » (PER du groupe) n'est pas un volume de 11.
    assert codes(day("20200212")) == {"lang_en"}


def test_group_total_values_on_next_line_are_checked() -> None:
    # 02/01/2019 : « TOTAL » seul, valeurs « 6 505  24 132 660  8,55 » sur la ligne suivante.
    d = day("20190102")
    assert "group_total_mismatch" not in codes(d)
    bad = parse_boc_text(read_boc_text(REG / "boc_20190102.txt.gz").replace("24 132 660", "24 132 661"),
                         "2019-01-02")
    assert any("AGRICULTURE" in w for w in bad.warnings if warning_code(w) == "group_total_mismatch")


# ---------------------------------------------------------------------------
# Carnet d'ordres historique (2017)
# ---------------------------------------------------------------------------


def test_legacy_order_book_marker_after_reference_and_empty_rows() -> None:
    d = day("20170720")
    # « SPHC  SAPH CI  95  15400 /  -  3 080 Val- T » : pas de vente, référence 3 080.
    check(ob(d, "SPHC"), bid_qty=95.0, bid=15400.0, ask=None, ask_qty=None, ref_price=3080.0)
    check(ob(d, "TTLS"), bid_qty=25.0, bid=17510.0, ask=18400.0, ask_qty=322.0, ref_price=17950.0)  # « Ex-c »
    check(ob(d, "SAFC"), bid_qty=5.0, bid=17600.0, ask=None, ref_price=17500.0)
    # Lignes sans aucun ordre (pas de « / ») : « TTRC ... -  -  -  490 ».
    check(ob(d, "TTRC"), bid=None, ask=None, bid_qty=None, ask_qty=None, ref_price=490.0)
    check(ob(d, "PRSC"), ref_price=288000.0)
    assert "order_book_crossed" not in codes(d)


def ob_with_orders(d: BocDay) -> pd.DataFrame:
    """Lignes de carnet portant au moins un ordre (hors lignes « -  -  - »)."""
    o = d.order_book
    has = o[["bid_qty", "bid", "ask", "ask_qty"]].notna().any(axis=1) | o["bid_at_market"] | o["ask_at_market"]
    return o[has]


def test_english_order_book_with_singular_equity_market_heading() -> None:
    # 09/03/2017 (et 11/10, 13/10/2017) : page carnet en anglais titrée « EQUITY MARKET »
    # (singulier), suivie de « RIGHTS MARKET » et « BOND MARKET ». Seul « EQUITIES MARKET »
    # était reconnu : le carnet était perdu en entier, sans avertissement.
    d = day("20170309")
    assert len(d.equities) == 43 and len(d.order_book) == 43
    assert len(ob_with_orders(d)) == 42  # + TTRC (« -  -  -  490 »)
    check(ob(d, "CABC"), bid_qty=148.0, bid=73390.0, ask=78000.0, ask_qty=544.0, ref_price=75000.0)
    check(ob(d, "SIVC"), bid=None, ask=None, ask_at_market=True, ask_qty=309.0, ref_price=9500.0)
    check(ob(d, "STAC"), bid=None, ask=27000.0, ask_qty=21.0, ref_price=27000.0)  # dernière ligne
    check(ob(d, "TTRC"), bid=None, ask=None, bid_qty=None, ask_qty=None, ref_price=490.0)
    assert not {"order_book_missing", "order_book_crossed", "order_book_ref_mismatch"} & codes(d)
    # Un titre de section inconnu ne fait plus perdre le carnet en silence.
    text = read_boc_text(REG / "boc_20170309.txt.gz")
    bad = parse_boc_text(text.replace("EQUITY MARKET", "STOCK MARKET"), "2017-03-09")
    assert bad.order_book.empty and "order_book_missing" in codes(bad)
    # Section présente mais vide : signalée (information).
    a, b = text.index("EQUITY MARKET"), text.index("RIGHTS MARKET")
    rows = re.compile(r"^\s+[A-Z][A-Z0-9]{2,6}\s{2,}")
    emptied = text[:a] + "\n".join(ln for ln in text[a:b].split("\n") if not rows.match(ln)) + text[b:]
    e = parse_boc_text(emptied, "2017-03-09")
    assert e.order_book.empty and "order_book_empty" in codes(e)


def test_stale_order_book_page_of_previous_session_is_dropped() -> None:
    # 16/10/2017 : la page carnet (anglaise, « EQUITY MARKET ») est celle de la séance du
    # 13/10 (« Trading session of October 13, 2017 ») : ordres identiques au carnet du
    # 13/10, référence SNTS 23 300 (clôture du 13/10) contre 23 010 à la cote du 16/10.
    # Ignorée avec un avertissement plutôt que datée du 16/10.
    d = day("20171016")
    assert len(d.equities) == 43 and d.order_book.empty
    assert "order_book_stale" in codes(d)
    check(row(d, "SNTS"), close=23010.0)
    # La même page annoncée pour la bonne séance est lue : 41 lignes avec ordres + TTRC et
    # SAFC (« -  -  -  9 000 Ex-d »).
    text = read_boc_text(REG / "boc_20171016.txt.gz").replace("October 13, 2017", "October 16, 2017")
    f = parse_boc_text(text, "2017-10-16")
    assert len(f.order_book) == 43 and len(ob_with_orders(f)) == 41
    assert "order_book_stale" not in codes(f)
    check(ob(f, "SNTS"), bid=23300.0, ask=23350.0, ref_price=23300.0)
    check(ob(f, "SAFC"), bid=None, ask=None, ref_price=9000.0)


def test_bulletin_without_order_book_page_is_reported() -> None:
    # 28/04/2017 : BOC de 3 pages, sans page carnet (le « MARCHE DES ACTIONS » est la cote).
    d = day("20170428")
    assert len(d.equities) == 43 and d.order_book.empty
    assert "order_book_absent" in codes(d) and "order_book_missing" not in codes(d)


# ---------------------------------------------------------------------------
# Magasin : dividendes
# ---------------------------------------------------------------------------


def seq(symbol: str, rows: list[tuple]) -> pd.DataFrame:
    """Séquence d'un titre : (date, prev, close, ref, div, div_date, status, flags)."""
    recs = []
    for date, prev, close, ref, div, ddate, status, flags in rows:
        recs.append({"date": pd.Timestamp(date), "symbol": symbol, "prev_close": prev, "close": close,
                     "ref_price": ref, "last_div_net": div,
                     "last_div_date": pd.Timestamp(ddate) if ddate else pd.NaT, "status": status,
                     "flags": flags, "ex_div": "(D)" in flags, "volume": 1.0 if status == "traded" else 0.0})
    return pd.DataFrame(recs)


T, N, S = "traded", "not_traded", "suspended"


def test_dividend_republished_after_reversal_is_not_a_second_dividend() -> None:
    # CIEC 2017 : 3 465 (12-juil.-17) apparaît le 07/07 (Ex-c, référence 67 000 -> 63 535),
    # disparaît le 13/07 (retour à 2 641 / 15-sept.-16) puis revient daté du 20-sept.-17.
    e = seq("CIEC", [
        ("2017-07-05", 68000, 70000, 70000, 2641, "2016-09-15", T, ""),
        ("2017-07-07", 70000, 67000, 63535, 3465, "2017-07-12", T, "EX-C"),
        ("2017-07-10", 67000, 67000, 63535, 3465, "2017-07-12", N, "EX-C"),
        ("2017-07-11", 67000, 68000, 68000, 3465, "2017-07-12", T, ""),
        ("2017-07-13", 62900, 63000, 63000, 2641, "2016-09-15", T, ""),
        ("2017-09-19", 59900, 57000, 57000, 2641, "2016-09-15", T, ""),
        ("2017-09-20", 57000, 58500, 58500, 3465, "2017-09-20", T, ""),
        ("2017-09-21", 58500, 58000, 58000, 3465, "2017-09-20", T, ""),
    ])
    dv = detect_dividends(e)
    assert len(dv) == 1
    check(dv.iloc[0], amount=3465.0, ex_date=dt.date(2017, 7, 10), evidence="ref_adjusted")
    t = adjusted_table(e).set_index("date")
    assert t.loc["2017-09-20", "tr_ret"] == pytest.approx(58500 / 57000 - 1)


def test_first_dividend_after_listing_is_new() -> None:
    # ORAC, cotée le 30/12/2022 : colonne dividende vide jusqu'au 12/06/2023, où paraît
    # 752,76 (15-juin-23) avec (d) et une référence 8 850 pour une clôture de 9 600. Ce
    # premier dividende était pris pour un dividende « connu au début de l'historique » :
    # perdu, et la baisse ex-dividende comptée comme une perte (tr_ret -4,06 %).
    e = seq("ORAC", [
        ("2022-12-30", None, 10210, 10210, None, None, T, ""),
        ("2023-01-02", 10210, 10925, 10925, None, None, T, ""),
        ("2023-06-08", 9605, 9550, 9550, None, None, T, ""),
        ("2023-06-09", 9550, 9950, 9950, None, None, T, ""),
        ("2023-06-12", 9950, 9600, 8850, 752.76, "2023-06-15", T, "(D)"),
        ("2023-06-13", 8850, 9210, 9210, 752.76, "2023-06-15", T, "(V)"),
        ("2023-06-14", 9210, 9450, 9450, 752.76, "2023-06-15", T, ""),
    ])
    dv = detect_dividends(e)
    assert len(dv) == 1
    check(dv.iloc[0], amount=752.76, ex_date=dt.date(2023, 6, 13), evidence="ex_div_flag")
    t = adjusted_table(e).set_index("date")
    check(t.loc["2023-06-13"], dividend=752.76)
    assert t.loc["2023-06-13", "tr_ret"] == pytest.approx((9210 + 752.76) / 9600 - 1)
    # NSBC 2018 : colonne « 0,00 » sans date avant le 20/06/2018 (466,10, 25-juin-18, (d),
    # référence 9 035 pour 9 500) : même règle.
    e = seq("NSBC", [
        ("2018-06-18", 9200, 9200, 9200, 0.0, None, T, ""),
        ("2018-06-19", 9200, 9300, 9300, 0.0, None, T, ""),
        ("2018-06-20", 9300, 9500, 9035, 466.10, "2018-06-25", T, "(D)"),
        ("2018-06-21", 9500, 8800, 8800, 466.10, "2018-06-25", T, ""),
    ])
    check(detect_dividends(e).iloc[0], amount=466.10, ex_date=dt.date(2018, 6, 21))
    # BOAM 2017 : colonne vide en début d'historique, 2 790 (2-mai-17) le 26/04 avec « Ex-c »
    # et référence 46 510 pour 49 300 (sans marqueur (d) : preuve = référence abaissée).
    e = seq("BOAM", [
        ("2017-01-02", 49000, 49000, 49000, None, None, T, ""),
        ("2017-04-25", 49000, 49000, 49000, None, None, T, ""),
        ("2017-04-26", 49000, 49300, 46510, 2790, "2017-05-02", T, "EX-C"),
        ("2017-04-27", 49300, 48950, 48950, 2790, "2017-05-02", T, ""),
    ])
    check(detect_dividends(e).iloc[0], amount=2790.0, ex_date=dt.date(2017, 4, 27), evidence="ref_adjusted")


def test_dividend_known_before_history_start_is_not_new() -> None:
    # Dividende publié dès la première séance du titre, ou payé avant elle (colonne vide
    # sur les premières séances) : état initial, pas un détachement de l'historique.
    e = seq("SNTS", [
        ("2017-01-02", 25000, 25000, 25000, 1500, "2016-05-17", T, ""),
        ("2017-01-03", 25000, 25100, 25100, 1500, "2016-05-17", T, ""),
    ])
    assert detect_dividends(e).empty
    e = seq("SNTS", [
        ("2017-01-02", 25000, 25000, 25000, None, None, T, ""),
        ("2017-01-03", 25000, 25100, 25100, 1500, "2016-05-17", T, ""),
        ("2017-01-04", 25100, 25100, 25100, 1500, "2016-05-17", T, ""),
    ])
    assert detect_dividends(e).empty


def test_dividend_restated_on_split_day_is_not_new() -> None:
    # FTSC 31/01/2018 : division par 4 (précédent publié 4 125 pour 16 500) ; le dividende
    # 1 045 (31-juil.-17) devient 261 daté du 9-janv.-18 : simple retraitement.
    e = seq("FTSC", [
        ("2017-12-29", 18425, 19700, 19700, 1045, "2017-07-31", T, ""),
        ("2018-01-03", 19500, 19295, 19295, 1045, "2017-07-31", T, ""),
        ("2018-01-05", 19295, 18500, 18500, 1045, "2017-07-31", T, ""),
        ("2018-01-29", 17000, 16500, 16500, 1045, "2017-07-31", T, ""),
        ("2018-01-30", 16500, 16500, 4125, 1045, "2017-07-31", T, ""),
        ("2018-01-31", 4125, 4400, 4400, 261, "2018-01-09", T, ""),
        ("2018-02-01", 4400, 4400, 4400, 261, "2018-01-09", T, ""),
    ])
    assert detect_dividends(e).empty
    ca = detect_corporate_actions(e)
    check(ca.iloc[0], kind="split", ratio=4.0)
    t = adjusted_table(e).set_index("date")
    assert t.loc["2018-01-05", "tr_ret"] == pytest.approx(18500 / 19295 - 1)


def test_dividend_amount_corrected_by_boc() -> None:
    # ONTBF : 226,45 publié le 26/07/2024 ((d), référence 2 995 -> 2 730), corrigé en 266,45
    # (même date 31-juil.-24) le 30/07 ; la baisse de la référence (265) confirme 266,45.
    e = seq("ONTBF", [
        ("2024-07-25", 2995, 2995, 2995, 287.88, "2023-06-26", T, ""),
        ("2024-07-26", 2995, 2995, 2730, 226.45, "2024-07-31", T, "(D)"),
        ("2024-07-29", 2730, 2800, 2800, 226.45, "2024-07-31", T, "(V)"),
        ("2024-07-30", 2800, 2700, 2700, 266.45, "2024-07-31", T, ""),
        ("2024-07-31", 2700, 2700, 2700, 266.45, "2024-07-31", T, ""),
    ])
    dv = detect_dividends(e)
    assert len(dv) == 1
    check(dv.iloc[0], amount=266.45, ex_date=dt.date(2024, 7, 29))
    assert dv.iloc[0]["evidence"].endswith("+amount_corrected")


def test_untraded_ex_date_valued_at_ex_reference() -> None:
    # SDCC : (d) le 24/10/2019 (référence 2 625), non coté le 25/10 (clôture publiée = 2 895,
    # cours cum), prochaine cotation 2 820 le 28/10.
    e = seq("SDCC", [
        ("2019-10-23", 2900, 2900, 2900, 270, "2018-08-29", N, ""),
        ("2019-10-24", 2900, 2895, 2625, 270, "2019-10-29", T, "(D)"),
        ("2019-10-25", 2895, 2895, 2625, 270, "2019-10-29", N, ""),
        ("2019-10-28", 2895, 2820, 2820, 270, "2019-10-29", T, ""),
    ])
    dv = detect_dividends(e)
    check(dv.iloc[0], ex_date=dt.date(2019, 10, 25), amount=270.0)
    t = adjusted_table(e).set_index("date")
    check(t.loc["2019-10-25"], close=2625.0, dividend=270.0)
    assert t.loc["2019-10-25", "tr_ret"] == pytest.approx((2625 + 270) / 2895 - 1)
    assert t.loc["2019-10-28", "tr_ret"] == pytest.approx(2820 / 2625 - 1)
    # Dividende réinvesti au cours ex (2 625) : 2 895 / 2 625 titres-équivalents valorisés 2 820.
    growth = (1 + t["tr_ret"].fillna(0)).prod()
    assert growth == pytest.approx(2895 / 2900 * (2895 / 2625) * (2820 / 2895), rel=1e-12)


# ---------------------------------------------------------------------------
# Magasin : opérations sur titres
# ---------------------------------------------------------------------------


def test_capital_adjustment_published_before_reference_reset() -> None:
    # SAFC 2017 : référence 9 000 (Val-T) le 11/10, Ex-d les 12-13/10, remise à 22 500 le
    # 16/10, première cotation 9 675 (= 9 000 x 1,075) le 17/10 ; dividende 1 440 retraité
    # en 576 (/2,5) le 19/12/2017.
    e = seq("SAFC", [
        ("2017-10-10", 22500, 22000, 22000, 1440, "2011-07-29", T, ""),
        ("2017-10-11", 22000, 22500, 9000, 1440, "2011-07-29", T, "VAL-T"),
        ("2017-10-12", 22500, 22500, 9000, 1440, "2011-07-29", N, "EX-D"),
        ("2017-10-13", 22500, 22500, 9000, 1440, "2011-07-29", N, "EX-D"),
        ("2017-10-16", 22500, 22500, 22500, 1440, "2011-07-29", N, ""),
        ("2017-10-17", 22500, 9675, 9675, 1440, "2011-07-29", T, "(*)"),
        ("2017-12-18", 10900, 10900, 10900, 1440, "2011-07-29", N, ""),
        ("2017-12-19", 10900, 10900, 10900, 576, "2011-07-29", N, ""),
    ])
    ca = detect_corporate_actions(e)
    assert len(ca) == 1
    ev = ca.iloc[0]
    check(ev, kind="split", ratio=2.5, date=dt.date(2017, 10, 17), confidence="high")
    assert "ref_adjusted_earlier" in ev["evidence"] and "div_restated" in ev["evidence"]
    t = adjusted_table(e, ca).set_index("date")
    assert t.loc["2017-10-17", "ret"] == pytest.approx(0.075)


def test_split_with_alternating_stale_previous_close() -> None:
    # SAFC 21/12/2018 - 08/01/2019 : division 1:25 ; la BOC alterne précédent 5 300 / 215 sur
    # les séances non cotées ; dividende 576 retraité en 23,04 (k = 25).
    rows = [("2018-12-20", 5300, 5300, 5300, 576, "2011-07-29", N, ""),
            ("2018-12-21", 5300, 5300, 215, 576, "2011-07-29", N, "(#)")]
    for date, c in [("2018-12-24", 215), ("2018-12-26", 5300), ("2018-12-27", 5300), ("2018-12-28", 5300),
                    ("2018-12-31", 5300), ("2019-01-02", 215), ("2019-01-03", 215), ("2019-01-04", 5300),
                    ("2019-01-07", 215)]:
        rows.append((date, c, c, 215 if date < "2018-12-31" else c, 23.04, "2011-07-29", N, ""))
    rows.append(("2019-01-08", 215, 210, 210, 23.04, "2011-07-29", T, ""))
    e = seq("SAFC", rows)
    ca = detect_corporate_actions(e)
    adj = ca[ca["kind"].isin(["split", "reverse_split", "price_reset"])]
    assert math.prod(adj["ratio"]) == pytest.approx(25.0)
    lead = ca[ca["kind"] == "split"]
    assert len(lead) == 1 and lead.iloc[0]["date"] == pd.Timestamp("2018-12-24")
    assert lead.iloc[0]["ratio"] == pytest.approx(25.0) and lead.iloc[0]["confidence"] == "high"
    t = adjusted_table(e, ca).set_index("date")
    # Rendement économique : 5 300 (cum) -> 210 x 25 (première cotation ex-division).
    assert (1 + t["ret"].fillna(0)).prod() == pytest.approx(210 * 25 / 5300)
    assert (t["split_factor"].iloc[0]) == pytest.approx(25.0)


def test_suspension_reference_resets_are_not_returns() -> None:
    # UNLC : suspendu le 24/07/2019 à 3 500 ; la BOC remet le précédent à 2 500 le
    # 02/01/2020 ; reprise le 17/03/2020 (admission d'actions nouvelles) à 4 775 sans
    # précédent publié.
    e = seq("UNLC", [
        ("2019-07-23", 3780, 3500, 3500, 1233, "2012-07-09", T, ""),
        ("2019-07-24", 3500, 3500, 3500, 1233, "2012-07-09", S, ""),
        ("2019-08-21", 3500, 3500, 2500, 1233, "2012-07-09", S, ""),
        ("2019-12-31", 3500, 3500, 2500, 1233, "2012-07-09", S, ""),
        ("2020-01-02", 2500, 2500, 2500, 1233, "2012-07-09", S, ""),
        ("2020-03-16", 2500, 2500, 2500, 1233, "2012-07-09", S, ""),
        ("2020-03-17", np.nan, 4775, 4775, 1233, "2012-07-09", N, ""),
        ("2020-06-02", 4775, 4775, 4775, 1233, "2012-07-09", T, ""),
    ])
    ca = detect_corporate_actions(e)
    assert list(ca["kind"]) == ["suspension_reset"]
    check(ca.iloc[0], date=dt.date(2020, 3, 17), ratio=3500 / 4775)
    t = adjusted_table(e, ca)
    assert np.allclose(t["ret"].fillna(0), 0.0)


# ---------------------------------------------------------------------------
# Panel réel (si construit)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not (PANEL / "equities.parquet").exists(), reason="data/panel absent")
def test_real_panel_regressions() -> None:
    mk = pd.read_parquet(PANEL / "market.parquet").set_index("date")
    june = mk.loc["2019-05-27":"2019-06-26"]
    # Page 1 = actions + droits (droits SVOC.DS1 les 06 et 12/06/2019).
    assert (june["volume"] == june["equity_total_volume"] + june["rights_total_volume"].fillna(0)).all()
    assert (mk["volume"] - mk["equity_total_volume"] - mk["rights_total_volume"].fillna(0)).abs().max() < 0.5
    assert june["bond_volume"].notna().all()
    eq = pd.read_parquet(PANEL / "equities.parquet").set_index(["date", "symbol"])
    assert eq.loc[(pd.Timestamp("2026-01-02"), "BNBC"), "per"] == pytest.approx(1236.32)
    assert not eq["name"].str.contains(r"\((?:d|v|V|#|-|ex-)\)?", regex=True).any()
    dv = pd.read_parquet(PANEL / "dividends.parquet")
    assert len(dv[(dv["symbol"] == "CIEC") & (dv["amount"] == 3465)]) == 1
    assert dv[(dv["symbol"] == "FTSC") & (dv["ex_date"].dt.year == 2018) & (dv["ex_date"].dt.month == 1)].empty
    assert dv[(dv["symbol"] == "ONTBF") & (dv["ex_date"] == "2024-07-29")]["amount"].iloc[0] == pytest.approx(266.45)
    # Premier dividende d'un titre après des séances à colonne dividende vide.
    first_divs = {("ECOC", "2018-06-20"): 1844, ("NSBC", "2018-06-21"): 466.10, ("ORGT", "2019-06-27"): 56.73,
                  ("ORAC", "2023-06-13"): 752.76, ("LNBB", "2025-07-29"): 275.50, ("BICB", "2025-09-11"): 254.60,
                  ("BOAM", "2017-04-27"): 2790, ("CBIBF", "2017-06-07"): 1120, ("SIBC", "2017-06-07"): 855,
                  ("SCRC", "2017-09-27"): 549}
    for (sym, ex), amount in first_divs.items():
        sel = dv[(dv["symbol"] == sym) & (dv["ex_date"] == ex)]
        assert len(sel) == 1 and sel["amount"].iloc[0] == pytest.approx(amount), (sym, ex)
    # STAC 2021 : 66,15 (16-juil.-21) paru le 19/07 après un trou de BOC (07/07 -> 19/07).
    stac = dv[(dv["symbol"] == "STAC") & ((dv["amount"] - 66.15).abs() < 1e-6) & (dv["ex_date"].dt.year == 2021)]
    assert len(stac) == 1 and stac["ex_date"].iloc[0].strftime("%Y-%m") == "2021-07"
    # Carnets des pages anglaises « EQUITY MARKET » ; celui du 16/10/2017 (page du 13/10) ignoré.
    obk = pd.read_parquet(PANEL / "order_book.parquet")
    n_ob = obk.groupby("date").size()
    for stamp in ("2017-03-09", "2017-10-11", "2017-10-13"):
        assert n_ob.get(pd.Timestamp(stamp), 0) == 43, stamp
    assert pd.Timestamp("2017-10-16") not in n_ob.index
    ca = pd.read_parquet(PANEL / "corporate_actions.parquet").set_index(["symbol", "date"])
    assert ca.loc[("SAFC", pd.Timestamp("2017-10-17")), "ratio"] == pytest.approx(2.5)
    for sym, k in (("SAFC", 25.0), ("SEMC", 40.0)):
        sel = ca.loc[sym].loc["2018-12-20":"2019-01-10"]
        assert math.prod(sel["ratio"]) == pytest.approx(k)
    ap = pd.read_parquet(PANEL / "adjusted_prices.parquet").set_index(["symbol", "date"])
    assert ap.loc[("SAFC", pd.Timestamp("2017-10-17")), "tr_ret"] == pytest.approx(0.075)
    assert ap.loc[("SDCC", pd.Timestamp("2019-10-25")), "close"] == 2625.0
    assert ap.loc[("ORAC", pd.Timestamp("2023-06-13")), "tr_ret"] == pytest.approx((9210 + 752.76) / 9600 - 1)
    assert ap.loc[("ECOC", pd.Timestamp("2018-06-20")), "tr_ret"] == pytest.approx((24485 + 1844) / 26000 - 1)
    unlc = ap.loc["UNLC"].loc["2019-07-24":"2020-03-17", "ret"]
    assert np.allclose(unlc.fillna(0), 0.0)
