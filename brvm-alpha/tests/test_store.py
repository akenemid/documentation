"""Tests du magasin de données : panel, cache incrémental, opérations sur titres, total return."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from brvm_alpha.data.store import (
    adjusted_prices,
    adjusted_table,
    build_panel,
    detect_corporate_actions,
    detect_dividends,
    load_corporate_actions,
    load_equities,
    load_indices,
    load_market,
    load_order_book,
    total_return_index,
)

FIX = Path(__file__).parent / "fixtures"
MAIN = ["20180601", "20200302", "20230601", "20240614", "20261120"]
N_ROWS = 45 + 46 + 46 + 46 + 48


def copy_fixtures(dst: Path, stamps: list[str], src: Path = FIX) -> Path:
    dst.mkdir(parents=True, exist_ok=True)
    for s in stamps:
        shutil.copy(src / f"boc_{s}.txt.gz", dst / f"boc_{s}.txt.gz")
    return dst


@pytest.fixture(scope="module")
def panel(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path, object]:
    root = tmp_path_factory.mktemp("panel")
    boc = copy_fixtures(root / "boc", MAIN)
    out = root / "out"
    summary = build_panel(boc, out, workers=2)
    return boc, out, summary


# ---------------------------------------------------------------------------
# build_panel / lecture
# ---------------------------------------------------------------------------


def test_build_panel_outputs(panel: tuple[Path, Path, object]) -> None:
    _, out, summary = panel
    for name in ("equities", "indices", "market", "order_book", "corporate_actions", "dividends",
                 "adjusted_prices"):
        assert (out / f"{name}.parquet").exists(), name
    assert summary.n_files == 5 and summary.n_parsed == 5 and summary.n_errors == 0
    assert summary.n_sessions == 5 and summary.n_rows == N_ROWS
    assert summary.first_date == pd.Timestamp("2018-06-01")
    assert summary.last_date == pd.Timestamp("2026-11-20")
    report = pd.read_csv(out / "parse_report.csv")
    assert list(report["file"]) == [f"boc_{s}.txt.gz" for s in MAIN]
    assert list(report["n_equities"]) == [45, 46, 46, 46, 48]
    for col in ("date", "n_warnings", "warning_codes", "warnings", "error", "excluded"):
        assert col in report.columns
    assert report.loc[4, "warning_codes"] == "wrapped_digits_joined=1"


def test_load_equities_index(panel: tuple[Path, Path, object]) -> None:
    _, out, _ = panel
    eq = load_equities(out)
    assert eq.index.names == ["date", "symbol"]
    assert eq.index.is_unique and eq.index.is_monotonic_increasing
    assert len(eq) == N_ROWS
    snts = eq.loc[(pd.Timestamp("2026-11-20"), "SNTS")]
    assert snts["close"] == 4040 and snts["value"] == 2988573270
    # Contrat du panel : volume et valeur à 0 quand le titre n'est pas échangé.
    sicc = eq.loc[(pd.Timestamp("2026-11-20"), "SICC")]
    assert sicc["status"] == "suspended" and sicc["volume"] == 0 and sicc["value"] == 0
    assert eq["close"].notna().all() and eq["volume"].notna().all()
    sub = load_equities(out, symbols=["SNTS", "ORAC"], start="2023-01-01")
    assert set(sub.index.get_level_values("symbol")) == {"SNTS", "ORAC"}
    assert sub.index.get_level_values("date").min() >= pd.Timestamp("2023-01-01")
    traded = load_equities(out, traded_only=True)
    assert (traded["status"] == "traded").all()


def test_load_indices_market_order_book(panel: tuple[Path, Path, object]) -> None:
    _, out, _ = panel
    ix = load_indices(out)
    assert ix.index.names == ["date", "index"] and ix.index.is_unique
    assert ix.loc[(pd.Timestamp("2026-11-20"), "BRVM COMPOSITE"), "level"] == 492.89
    wide = load_indices(out, wide=True)
    assert wide.loc["2018-06-01", "BRVM COMPOSITE"] == 217.72
    assert wide.loc["2026-11-20", "BRVM COMPOSITE TOTAL RETURN"] == 198.63
    assert np.isnan(wide.loc["2018-06-01", "BRVM PRESTIGE"])
    mk = load_market(out)
    assert mk.index.is_unique and len(mk) == 5
    assert mk.loc["2026-11-20", "market_cap"] == 19328818938929
    book = load_order_book(out)
    assert book.loc[(pd.Timestamp("2026-11-20"), "SNTS"), "bid"] == 4010
    assert isinstance(load_corporate_actions(out), pd.DataFrame)


def test_incremental_cache(tmp_path: Path) -> None:
    boc = copy_fixtures(tmp_path / "boc", MAIN[:2])
    out = tmp_path / "out"
    s1 = build_panel(boc, out, workers=1)
    assert (s1.n_parsed, s1.n_cached) == (2, 0)
    s2 = build_panel(boc, out, workers=1)
    assert (s2.n_parsed, s2.n_cached) == (0, 2)
    assert s2.n_rows == s1.n_rows
    # Nouveau fichier : seul lui est analysé.
    copy_fixtures(boc, [MAIN[2]])
    s3 = build_panel(boc, out, workers=1)
    assert (s3.n_parsed, s3.n_cached, s3.n_sessions) == (1, 2, 3)
    # Fichier modifié (date de modification) : réanalysé.
    f = boc / f"boc_{MAIN[0]}.txt.gz"
    os.utime(f, (f.stat().st_atime, f.stat().st_mtime + 100))
    s4 = build_panel(boc, out, workers=1)
    assert (s4.n_parsed, s4.n_cached) == (1, 2)
    assert s4.n_rows == 45 + 46 + 46  # pas de doublon après réanalyse
    # Fichier supprimé : ses lignes disparaissent du panel.
    f.unlink()
    s5 = build_panel(boc, out, workers=1)
    assert s5.n_sessions == 2 and s5.n_rows == 46 + 46
    # force=True : tout est réanalysé.
    s6 = build_panel(boc, out, workers=1, force=True)
    assert (s6.n_parsed, s6.n_cached) == (2, 0)


def test_duplicate_bulletin_is_excluded(tmp_path: Path) -> None:
    # BOC republié sous une autre date (contenu identique) : séance exclue du panel.
    boc = copy_fixtures(tmp_path / "boc", ["20240614"])
    shutil.copy(boc / "boc_20240614.txt.gz", boc / "boc_20240617.txt.gz")
    out = tmp_path / "out"
    summary = build_panel(boc, out, workers=1)
    assert summary.n_sessions == 1
    report = pd.read_csv(out / "parse_report.csv").set_index("file")
    assert report.loc["boc_20240617.txt.gz", "excluded"].startswith("duplicate_content")
    assert "date_mismatch" in report.loc["boc_20240617.txt.gz", "warning_codes"]


# ---------------------------------------------------------------------------
# Séquences réelles : division 1:10 de SONATEL (10/2026), dividende (05/2026)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def split_panel(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("split") / "out"
    build_panel(FIX / "seq_split_2026_10", out, workers=1)
    return out


def test_real_split_detected(split_panel: Path) -> None:
    ca = load_corporate_actions(split_panel)
    snts = ca[ca["symbol"] == "SNTS"]
    assert len(snts) == 1
    ev = snts.iloc[0]
    assert ev["date"] == pd.Timestamp("2026-10-26") and ev["prev_date"] == pd.Timestamp("2026-10-23")
    assert ev["kind"] == "split" and ev["ratio"] == 10 and ev["confidence"] == "high"
    assert ev["evidence"].startswith("prev_close_adjusted")  # 43 850 publié 4 385 le lendemain
    assert ev["close_before"] == 43850 and ev["close_after"] == 4700
    # Aucune autre valeur ne présente d'événement sur ces 4 séances consécutives.
    assert set(ca["symbol"]) == {"SNTS"}


def test_real_split_adjusted_prices(split_panel: Path) -> None:
    wide = adjusted_prices(panel_dir=split_panel)
    snts = wide["SNTS"]
    assert snts.loc["2026-10-22"] == pytest.approx(4200.0)  # 42 000 / 10
    assert snts.loc["2026-10-23"] == pytest.approx(4385.0)  # 43 850 / 10
    assert snts.loc["2026-10-26"] == pytest.approx(4700.0)  # inchangé après la division
    table = adjusted_prices(panel_dir=split_panel, wide=False).set_index(["symbol", "date"])
    r = table.loc[("SNTS", pd.Timestamp("2026-10-26"))]
    assert r["split_ratio"] == 10
    assert r["ret"] == pytest.approx(4700 * 10 / 43850 - 1)  # +7,18 % publié
    tr = total_return_index(panel_dir=split_panel)["SNTS"]
    assert tr.iloc[0] == 100.0
    assert tr.loc["2026-10-26"] / tr.loc["2026-10-23"] == pytest.approx(1.0718, abs=1e-4)
    # Le fichier écrit par build_panel est la même table longue.
    stored = pd.read_parquet(split_panel / "adjusted_prices.parquet")
    assert stored["adj_close"].notna().all() and len(stored) == len(table)


@pytest.fixture(scope="module")
def div_panel(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("div") / "out"
    build_panel(FIX / "seq_dividend_2026_05", out, workers=1)
    return out


def test_real_dividend_detected(div_panel: Path) -> None:
    dv = pd.read_parquet(div_panel / "dividends.parquet")
    snts = dv[dv["symbol"] == "SNTS"].iloc[0]
    # 21/05/2026 : marqueur (d), référence 27 160 = 28 900 - 1 740 -> détachement le 22/05.
    assert snts["amount"] == 1740 and snts["ex_date"] == pd.Timestamp("2026-05-22")
    assert snts["payment_date"] == pd.Timestamp("2026-05-26")
    assert snts["evidence"] == "ex_div_flag"
    table = adjusted_table(panel_dir=div_panel).set_index(["symbol", "date"])
    r = table.loc[("SNTS", pd.Timestamp("2026-05-22"))]
    assert r["dividend"] == 1740
    assert r["ret"] == pytest.approx(28500 / 28900 - 1)
    assert r["tr_ret"] == pytest.approx((28500 + 1740) / 28900 - 1)
    # Le détachement n'est pas une opération sur titres.
    ca = load_corporate_actions(div_panel)
    assert ca[ca["symbol"] == "SNTS"].empty


# ---------------------------------------------------------------------------
# Détections sur données synthétiques
# ---------------------------------------------------------------------------


def synth(symbol: str, closes: list[float], *, prev: list[float] | None = None, ref: list[float] | None = None,
          div: list[float] | None = None, div_date: list[str | None] | None = None,
          ex_div: list[bool] | None = None, start: str = "2024-01-01") -> pd.DataFrame:
    """Petit panel synthétique d'un titre (séances ouvrées consécutives)."""
    n = len(closes)
    dates = pd.bdate_range(start, periods=n)
    prev = prev if prev is not None else [np.nan, *closes[:-1]]
    return pd.DataFrame({
        "date": dates, "symbol": symbol, "close": closes, "prev_close": prev,
        "ref_price": ref if ref is not None else closes,
        "last_div_net": div if div is not None else [np.nan] * n,
        "last_div_date": pd.to_datetime(div_date if div_date is not None else [None] * n),
        "ex_div": ex_div if ex_div is not None else [False] * n,
        "flags": "", "status": "traded",
    })


def test_split_by_price_jump_and_reverse_split() -> None:
    a = synth("AAAA", [5000, 5050, 1010, 1000, 1020])  # 1:5 sans ajustement publié
    b = synth("BBBB", [40, 41, 405, 410])  # regroupement 10:1
    ca = detect_corporate_actions(pd.concat([a, b]))
    ra = ca[ca["symbol"] == "AAAA"].iloc[0]
    assert (ra["kind"], ra["ratio"], ra["confidence"]) == ("split", 5.0, "medium")
    assert ra["date"] == a["date"].iloc[2]
    rb = ca[ca["symbol"] == "BBBB"].iloc[0]
    assert rb["kind"] == "reverse_split" and rb["ratio"] == pytest.approx(0.1)


def test_published_adjustment_ratios() -> None:
    # Ajustement publié par la BRVM : « 3 pour 2 » (1,5) puis ajustement non simple (droits).
    a = synth("AAAA", [3000, 3020, 2030], prev=[np.nan, 3000, 2013.33])
    b = synth("BBBB", [5505, 4175, 4200], prev=[np.nan, 3890, 4175])
    ca = detect_corporate_actions(pd.concat([a, b])).set_index("symbol")
    assert ca.loc["AAAA", "kind"] == "split" and ca.loc["AAAA", "ratio"] == 1.5
    assert ca.loc["BBBB", "kind"] == "capital_adjustment"
    assert ca.loc["BBBB", "ratio"] == pytest.approx(5505 / 3890)


def test_dividend_drop_is_not_a_split() -> None:
    # Dividende exceptionnel de 30 % : la chute du cours est expliquée.
    e = synth("AAAA", [1000, 1000, 705, 700],
              ref=[1000, 700, 705, 700], prev=[np.nan, 1000, 700, 705],
              div=[50, 300, 300, 300], div_date=["2023-06-01", "2024-01-04", "2024-01-04", "2024-01-04"],
              ex_div=[False, True, False, False])
    dv = detect_dividends(e)
    assert len(dv) == 1 and dv.iloc[0]["amount"] == 300
    assert dv.iloc[0]["ex_date"] == e["date"].iloc[2] and dv.iloc[0]["evidence"] == "ex_div_flag"
    assert detect_corporate_actions(e, dv).empty


def test_data_error_and_missing_sessions() -> None:
    spike = synth("AAAA", [1000, 1005, 1500, 1010, 1000])  # pic isolé qui revient
    ca = detect_corporate_actions(spike)
    # Les deux temps du pic (montée puis retour) sont des erreurs, pas une division 1,5.
    assert list(ca["kind"]) == ["data_error", "data_error"]
    adj = adjusted_table(spike, ca)
    assert (adj["split_ratio"] == 1.0).all()
    # +15 % en deux séances (une séance manquante) : dans la bande élargie.
    gap = synth("BBBB", [1000, 1000, 1150, 1150])
    gap = gap.drop(index=2).reset_index(drop=True)
    gap.loc[2, "close"] = 1150
    gap.loc[2, "prev_close"] = 1075
    assert detect_corporate_actions(gap).empty


def test_detect_dividends_rules() -> None:
    d = synth(
        "AAAA", [100.0] * 8,
        div=[5, 5, 6, 6, 6, 0.6, 0.6, 7],
        div_date=["2023-05-01", "2023-05-01", "2024-01-03", "2024-01-05", "2023-05-01", "2024-01-05",
                  "2024-01-05", "2024-01-10"],
    )
    dv = detect_dividends(d)
    # 1re ligne : historique (non crédité) ; 2024-01-03 : nouveau (6) ; 2024-01-05 même
    # montant -> correction de date ; retour en arrière -> coquille ; 0,6 même date ->
    # retraitement (division) ; 2024-01-10 : nouveau (7).
    assert list(dv["amount"]) == [6.0, 7.0]
    assert dv.iloc[0]["payment_date"] == pd.Timestamp("2024-01-05")


def test_adjusted_table_synthetic() -> None:
    eq = synth("AAAA", [1000, 1050, 210, 220], prev=[np.nan, 1000, 210, 210])
    eq = pd.concat([eq, synth("BBBB", [100, 100, 90, 95],
                              div=[1, 10, 10, 10],
                              div_date=["2023-01-02", "2024-01-03", "2024-01-03", "2024-01-03"],
                              ref=[100, 90, 90, 95], ex_div=[False, True, False, False])])
    ca = detect_corporate_actions(eq, detect_dividends(eq))
    t = adjusted_table(eq, ca).set_index(["symbol", "date"])
    a = t.loc["AAAA"]
    assert list(a["split_factor"]) == [5.0, 5.0, 1.0, 1.0]
    assert list(a["adj_close"]) == [200.0, 210.0, 210.0, 220.0]
    assert a["ret"].iloc[2] == pytest.approx(0.0)
    b = t.loc["BBBB"]
    assert b["dividend"].iloc[2] == 10
    assert b["tr_ret"].iloc[2] == pytest.approx((90 + 10) / 100 - 1)
    assert b["tr_index"].iloc[-1] == pytest.approx(100 * 95 / 90)
    assert b["adj_close_tr"].iloc[-1] == 95
    wide = adjusted_prices(eq, ca)
    assert list(wide.columns) == ["AAAA", "BBBB"] and wide.index.is_monotonic_increasing
    tri = total_return_index(eq, ca)
    assert tri.iloc[0].tolist() == [100.0, 100.0]
