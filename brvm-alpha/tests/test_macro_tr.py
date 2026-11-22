"""Tests du Composite Total Return reconstruit, des ajouts de ``store.py`` et de ``quant/macro.py``.

Tests de non-régression de la spéc. §12.3 : n° 1 (TR au 20/11/2026), n° 2 (taux de
référence), n° 3 (bandes de prix), n° 4 (dates ex de SNTS). Les contrôles sur le panel réel
sont des contrôles de **données** (capitalisation, dates, bandes) ; aucun calcul de
performance n'est fait sur l'échantillon vierge S1 (2017-01-02 → 2022-11-16).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from brvm_alpha import reference as ref
from brvm_alpha.data import store
from brvm_alpha.quant import macro

ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "data" / "panel"
needs_panel = pytest.mark.skipif(not (PANEL / "equities.parquet").exists(), reason="panel réel absent")
S0_START = pd.Timestamp("2022-11-17")


# ---------------------------------------------------------------------------
# Panel synthétique minimal
# ---------------------------------------------------------------------------

CA_COLS = store.CORPORATE_ACTION_COLUMNS


def _ca(rows: list[dict]) -> pd.DataFrame:
    base = {c: np.nan for c in CA_COLS}
    out = [dict(base, **r) for r in rows]
    df = pd.DataFrame(out, columns=CA_COLS)
    df["date"] = pd.to_datetime(df["date"])
    return df


def _write_panel(tmp: Path, *, equities: pd.DataFrame, indices: pd.DataFrame | None = None,
                 market: pd.DataFrame | None = None, dividends: pd.DataFrame | None = None,
                 corporate_actions: pd.DataFrame | None = None, adjusted: pd.DataFrame | None = None) -> Path:
    tmp.mkdir(parents=True, exist_ok=True)
    equities.to_parquet(tmp / "equities.parquet", index=False)
    if indices is not None:
        indices.to_parquet(tmp / "indices.parquet", index=False)
    if market is not None:
        market.to_parquet(tmp / "market.parquet", index=False)
    (dividends if dividends is not None else pd.DataFrame(columns=store.DIVIDEND_COLUMNS)).to_parquet(
        tmp / "dividends.parquet", index=False)
    (corporate_actions if corporate_actions is not None else _ca([])).to_parquet(
        tmp / "corporate_actions.parquet", index=False)
    if adjusted is not None:
        adjusted.to_parquet(tmp / "adjusted_prices.parquet", index=False)
    return tmp


def _equities(dates, symbols, status=None) -> pd.DataFrame:
    rows = []
    for d in dates:
        for s in symbols:
            st = (status or {}).get((str(pd.Timestamp(d).date()), s), "traded")
            rows.append({"date": pd.Timestamp(d), "symbol": s, "close": 1000.0, "status": st})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Nombre de titres
# ---------------------------------------------------------------------------


def test_shares_outstanding_panel_synthetic(tmp_path: Path) -> None:
    dates = pd.bdate_range("2025-03-03", periods=5)
    eq = _equities(dates, ["SNTS", "SGBC"])
    eq = eq[~((eq["symbol"] == "SGBC") & (eq["date"] == dates[0]))]  # SGBC « introduit » en d1
    ca = _ca([
        {"symbol": "SNTS", "date": dates[3], "kind": "split", "ratio": 10.0, "confidence": "high"},
        {"symbol": "SGBC", "date": dates[2], "kind": "split", "ratio": 5.0, "confidence": "low"},  # ignoré
        {"symbol": "SGBC", "date": dates[4], "kind": "unexplained_jump", "ratio": np.nan, "confidence": "low"},
    ])
    p = _write_panel(tmp_path / "p", equities=eq, corporate_actions=ca)
    n = store.shares_outstanding_panel(p)
    assert list(n.columns) == sorted(ref.SHARES_OUTSTANDING_2026)
    assert n.loc[dates[2], "SNTS"] == 1e8 and n.loc[dates[3], "SNTS"] == 1e9
    assert n.loc[dates[1]:, "SGBC"].eq(31_111_110).all()
    assert np.isnan(n.loc[dates[0], "SGBC"])  # pas encore coté
    assert n["ORAC"].isna().all()  # absent du panel synthétique
    full = store.shares_outstanding_panel(p, listed_only=False)
    assert full.loc[dates[0], "SGBC"] == 31_111_110


@needs_panel
def test_shares_outstanding_panel_real_safc_and_snts() -> None:
    n = store.shares_outstanding_panel(PANEL)
    assert n.loc["2026-11-20", "SNTS"] == 1e9 and n.loc["2026-10-23", "SNTS"] == 1e8
    assert n.loc["2026-04-23", "SAFC"] == 8_119_750  # le DPS du 24/04/2026 ne change pas le nombre
    assert n.loc["2026-08-10", "SAFC"] == 8_119_750 and n.loc["2026-08-11", "SAFC"] == 11_869_750
    assert n.loc["2017-01-03", "SAFC"] == pytest.approx(8_119_750 / 62.5)  # divisions 2,5 (2017) et 25 (2018)
    assert np.isnan(n.loc["2017-01-03", "ORAC"])  # introduit le 30/12/2022
    assert "SVOC" not in n.columns  # radié, nombre de titres inconnu


@needs_panel
def test_reconstructed_cap_within_tolerance_of_published() -> None:
    """Contrôle de données (spéc. §1.1 et ``data.cap_reconstruction_tolerance`` = 3 %)."""
    n = store.shares_outstanding_panel(PANEL)
    px = store.load_equities(PANEL)["close"].unstack().reindex(columns=n.columns)
    cap = (n * px).sum(axis=1, min_count=1)
    mk = store.load_market(PANEL)["market_cap"]
    ratio = (cap / mk).dropna()
    year_end = ratio.groupby(ratio.index.year).tail(1)
    assert ((year_end - 1).abs() < 0.03).all()
    assert ratio.loc["2026-11-20"] == pytest.approx(1.0001, abs=2e-4)
    assert ratio.loc["2022-12-30"] == pytest.approx(1.0, abs=2e-4)


# ---------------------------------------------------------------------------
# Composite Total Return
# ---------------------------------------------------------------------------


def _tr_panel(tmp: Path) -> tuple[Path, pd.DatetimeIndex]:
    dates = pd.bdate_range("2025-01-02", periods=6)
    eq = _equities(dates, ["SNTS", "SGBC"])
    comp = [100.0, 101.0, 100.5, 102.0, 103.0, 102.5]
    idx = [{"date": d, "index": "BRVM COMPOSITE", "level": v} for d, v in zip(dates, comp)]
    idx += [{"date": dates[3], "index": "BRVM COMPOSITE TOTAL RETURN", "level": 150.0},
            {"date": dates[4], "index": "BRVM COMPOSITE TOTAL RETURN", "level": 151.0}]
    market = pd.DataFrame({"date": dates, "market_cap": [1e13, 1.01e13, 1.0e13, 1.02e13, 1.03e13, 1.02e13]})
    divs = pd.DataFrame([
        {"symbol": "SGBC", "ex_date": dates[2], "amount": 1000.0, "payment_date": dates[3]},
        {"symbol": "SNTS", "ex_date": dates[4], "amount": 50.0, "payment_date": dates[5]},
        {"symbol": "SVOC", "ex_date": dates[4], "amount": 10.0, "payment_date": dates[5]},  # nombre inconnu
    ], columns=store.DIVIDEND_COLUMNS)
    ca = _ca([{"symbol": "SNTS", "date": dates[3], "kind": "split", "ratio": 10.0, "confidence": "high"}])
    return _write_panel(tmp, equities=eq, indices=pd.DataFrame(idx), market=market, dividends=divs,
                        corporate_actions=ca), dates


def test_composite_tr_formula_synthetic(tmp_path: Path) -> None:
    p, dates = _tr_panel(tmp_path / "p")
    det = store.composite_tr_reconstructed(p, detail=True)
    comp = det["composite"]
    r_div = pd.Series(0.0, index=dates)
    r_div[dates[2]] = 31_111_110 * 1000.0 / 1.01e13  # N_SGBC × D / Cap(t−1)
    r_div[dates[4]] = 1e9 * 50.0 / 1.02e13  # N_SNTS après la division
    expected = (1 + (comp.pct_change().fillna(0) + r_div)).cumprod() * 100.0
    assert det["tr_reconstructed"].to_numpy() == pytest.approx(expected.to_numpy(), rel=1e-12)
    assert det["tr_reconstructed"].iloc[0] == 100.0  # base 100 au 02/01/2025
    assert det.attrs["dividends_dropped"] == [("SVOC", str(dates[4].date()), "nombre de titres inconnu")]
    # Série raccordée : officielle à partir de son premier jour, reconstruite avant, chaînée après.
    tr = store.composite_tr_reconstructed(p)
    assert tr.name == "BRVM_COMPOSITE_TR" and tr.attrs["official_from"] == str(dates[3].date())
    assert tr.loc[dates[3]] == 150.0 and tr.loc[dates[4]] == 151.0
    rec = det["tr_reconstructed"]
    assert tr.loc[dates[1]] == pytest.approx(150.0 * rec.loc[dates[1]] / rec.loc[dates[3]])
    assert tr.loc[dates[5]] == pytest.approx(151.0 * (1 + det["r_tr"].loc[dates[5]]))
    pure = store.composite_tr_reconstructed(p, official=False)
    assert pure.to_numpy() == pytest.approx(rec.to_numpy())


@needs_panel
def test_composite_tr_reconstructed_regression_spec_12_3_1() -> None:
    """Spéc. §12.3 n° 1 : TR reconstruit au 20/11/2026 ∈ [198,2 ; 199,0] (officiel 198,63) ;
    écart quotidien médian sur 2026 < 0,5 pb."""
    det = store.composite_tr_reconstructed(PANEL, detail=True)
    rec = det["tr_reconstructed"]
    assert rec.loc["2025-01-02"] == pytest.approx(100.0)
    assert 198.2 <= rec.loc["2026-11-20"] <= 199.0
    assert rec.loc["2026-11-20"] == pytest.approx(198.45, abs=0.01)  # annexe C-SPEC n° 3
    both = det[["tr_reconstructed", "tr_official"]].dropna()
    assert len(both) == 220 and both.index[0] == pd.Timestamp("2026-01-02")
    diff_bp = (both["tr_reconstructed"].pct_change() - both["tr_official"].pct_change()).dropna().abs() * 1e4
    assert len(diff_bp) == 219
    assert diff_bp.median() < 0.5
    assert diff_bp.max() < 3.0
    tr = store.composite_tr_reconstructed(PANEL)
    assert tr.loc["2026-11-20"] == pytest.approx(198.63)
    assert (tr.loc["2026-01-02":] == det["tr_official"].loc["2026-01-02":].dropna()).all()
    assert tr.attrs["official_from"] == "2026-01-02"
    assert tr.attrs["dividends_used"] == 321 and tr.attrs["dividends_dropped"] == []
    assert tr.notna().all() and (tr > 0).all()


# ---------------------------------------------------------------------------
# Panier équipondéré et masque statistique
# ---------------------------------------------------------------------------


def _adj_panel(tmp: Path, dates, tr: dict[str, list[float]], status=None, missing=None) -> Path:
    rows = []
    for s, vals in tr.items():
        for i, (d, v) in enumerate(zip(dates, vals)):
            rows.append({"date": pd.Timestamp(d), "symbol": s, "ret": v, "tr_ret": v,
                         "missing_sessions": (missing or {}).get((i, s), 0)})
    adj = pd.DataFrame(rows)
    eq = _equities(dates, list(tr), status)
    return _write_panel(tmp, equities=eq, adjusted=adj)


def test_equal_weight_tr_daily_and_mask_lag(tmp_path: Path) -> None:
    dates = pd.bdate_range("2025-03-03", periods=5)
    tr = {"SNTS": [np.nan, 0.01, 0.02, -0.01, 0.0], "SGBC": [np.nan, 0.03, -0.01, 0.0, 0.02]}
    p = _adj_panel(tmp_path / "p", dates, tr)
    det = store.equal_weight_tr(p, detail=True)
    expected_r = [0.0, 0.02, 0.005, -0.005, 0.01]
    assert det["ret"].to_numpy() == pytest.approx(expected_r)
    assert det["level"].iloc[0] == 100.0
    assert det["level"].iloc[-1] == pytest.approx(100 * np.prod([1 + x for x in expected_r]))
    # Éligibilité connue à la clôture de t -> rendement de t+1 seulement.
    mask = pd.DataFrame(False, index=dates, columns=["SNTS", "SGBC"])
    mask.loc[dates[1], "SNTS"] = True
    mask.loc[dates[2]:, ["SNTS", "SGBC"]] = True
    det = store.equal_weight_tr(p, mask, detail=True)
    assert det["ret"].to_numpy() == pytest.approx([0.0, 0.0, 0.02, -0.005, 0.01])
    assert det["n_names"].tolist() == [0, 0, 1, 2, 2]


def test_equal_weight_tr_excludes_suspended_by_default(tmp_path: Path) -> None:
    dates = pd.bdate_range("2025-03-03", periods=4)
    tr = {"SNTS": [np.nan, 0.01, 0.01, 0.01], "SICC": [np.nan, 0.0, 0.0, 0.05]}
    status = {(str(dates[1].date()), "SICC"): "suspended", (str(dates[2].date()), "SICC"): "suspended"}
    p = _adj_panel(tmp_path / "p", dates, tr, status)
    det = store.equal_weight_tr(p, detail=True)
    # SICC suspendu à la clôture de d1 et d2 : hors du panier pour les rendements de d2 et d3.
    assert det["ret"].to_numpy() == pytest.approx([0.0, 0.005, 0.01, 0.01])


def test_equal_weight_tr_monthly_drift(tmp_path: Path) -> None:
    dates = pd.DatetimeIndex(["2025-01-29", "2025-01-30", "2025-01-31", "2025-02-03", "2025-02-04"])
    tr = {"SNTS": [np.nan, 0.10, 0.0, 0.10, 0.0], "SGBC": [np.nan, 0.0, 0.0, 0.0, 0.10]}
    p = _adj_panel(tmp_path / "p", dates, tr)
    det = store.equal_weight_tr(p, rebalance="monthly", detail=True)
    # d1 : poids égaux (fixés en d0) -> 5 % ; d2 : 0 ; rebalancement le 31/01 ;
    # d3 : 5 % ; d4 : SGBC pèse 1/2,1 du panier après la dérive -> 0,1 / 2,1.
    assert det["ret"].to_numpy() == pytest.approx([0.0, 0.05, 0.0, 0.05, 0.1 / 2.1])
    with pytest.raises(ValueError):
        store.equal_weight_tr(p, rebalance="weekly")


@needs_panel
def test_equal_weight_tr_real_panel_form_on_s0() -> None:
    # Éligibilité limitée à S0 : aucun rendement du panier n'est calculé sur l'échantillon vierge S1.
    eq = store.load_equities(PANEL)
    eq = eq.reset_index() if "symbol" not in eq.columns else eq
    status = eq.assign(date=pd.to_datetime(eq["date"])).pivot_table(index="date", columns="symbol", values="status",
                                                                    aggfunc="last")
    mask = status.notna() & status.ne("suspended")
    mask.loc[mask.index < pd.Timestamp(S0_START)] = False
    det = store.equal_weight_tr(PANEL, eligible_mask=mask, detail=True).loc[S0_START:]
    assert det["level"].notna().all() and (det["level"] > 0).all()
    assert det.loc["2026-01-01":, "n_names"].between(40, 48).all()


def test_stats_mask_synthetic(tmp_path: Path) -> None:
    dates = pd.DatetimeIndex(["2021-05-03", "2021-05-04", "2021-05-06", "2021-06-25", "2021-06-28",
                              "2021-07-05", "2021-07-06"])
    tr = {"SNTS": [np.nan, 0.01, 0.01, 0.2, 0.01, 0.01, 0.0], "SICC": [np.nan, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]}
    status = {("2021-07-06", "SICC"): "suspended", ("2021-05-04", "SICC"): "not_traded"}
    p = _adj_panel(tmp_path / "p", dates, tr, status, missing={(3, "SNTS"): 32, (3, "SICC"): 32})
    long = store.stats_mask(p, wide=False).set_index(["date", "symbol"])
    assert bool(long.loc[("2021-06-25", "SNTS"), "multi_session"])  # trou de 50 jours
    assert bool(long.loc[("2021-07-05", "SNTS"), "multi_session"])  # 7 jours calendaires
    assert not bool(long.loc[("2021-06-28", "SNTS"), "multi_session"])  # week-end normal
    assert bool(long.loc[("2021-05-06", "SNTS"), "excluded_window"])
    assert bool(long.loc[("2021-05-04", "SICC"), "stale"]) and bool(long.loc[("2021-05-04", "SICC"), "usable"])
    w = store.stats_mask(p)
    assert w.dtypes.eq(bool).all()
    assert not w.loc["2021-05-03"].any()  # pas de rendement
    assert w.loc["2021-05-04"].all() and not w.loc["2021-05-06"].any() and not w.loc["2021-06-25"].any()
    assert w.loc["2021-06-28"].all() and not w.loc["2021-07-05"].any()
    assert bool(w.loc["2021-07-06", "SNTS"]) and not bool(w.loc["2021-07-06", "SICC"])  # suspendu
    only_missing = store.stats_mask(p, gap_days=10, wide=False).set_index(["date", "symbol"])
    assert not bool(only_missing.loc[("2021-07-05", "SNTS"), "multi_session"])


@needs_panel
def test_stats_mask_real_panel() -> None:
    w = store.stats_mask(PANEL)
    assert not w.loc["2021-05-06":"2021-06-25"].any().any()
    assert not w.loc["2026-03-23"].any()  # après le BOC n° 54 manquant (2026)
    assert not w.loc["2026-10-05"].any()  # après le BOC n° 187 manquant (02/10/2026)
    assert not w.loc["2026-11-20", "SICC"] and w.loc["2026-11-20", "SNTS"]
    assert w.loc["2026-11-20"].sum() == 46  # 48 titres moins SICC et SEMC suspendus


# ---------------------------------------------------------------------------
# Taux de référence (rf local)
# ---------------------------------------------------------------------------


def _market(values: list[float], start: str = "2024-01-01") -> pd.DataFrame:
    """Marché synthétique dont le taux implicite vaut ``values`` (PER fixé à 10)."""
    dates = pd.bdate_range(start, periods=len(values))
    return pd.DataFrame({"avg_per": 10.0, "risk_premium": [10.0 - v for v in values]}, index=dates)


def test_ref_govt_rate_filters_synthetic() -> None:
    vals = [5.9] * 25 + [6.25] + [5.9] * 3 + [5.75] * 6 + [11.0] * 3 + [5.75] * 2
    m = _market(vals)
    det = macro.ref_govt_rate(m, detail=True, unit="pct")
    r = det["rate"]
    assert r.iloc[:4].isna().all() and r.iloc[4] == pytest.approx(5.9)  # 5 séances pour établir
    assert r.iloc[25] == pytest.approx(5.9) and det["status"].iloc[25] == "outlier"  # jour isolé ignoré
    assert r.iloc[29:33].tolist() == pytest.approx([5.9] * 4)  # 4 séances au nouveau niveau : pas encore
    assert r.iloc[33] == pytest.approx(5.75) and det["status"].iloc[33] == "regime_change"
    assert (det["status"].iloc[35:38] == "invalid").all() and r.iloc[35:38].tolist() == pytest.approx([5.75] * 3)
    assert macro.ref_govt_rate(m).iloc[-1] == pytest.approx(0.0575)  # décimal par défaut
    assert macro.ref_govt_rate(m, asof=m.index[30]) == pytest.approx(0.059)
    stale = macro.ref_govt_rate(_market([5.9] * 10 + [np.nan] * 25), unit="pct")
    assert stale.iloc[29] == pytest.approx(5.9) and np.isnan(stale.iloc[31])  # > 20 séances sans donnée
    with pytest.raises(ValueError):
        macro.ref_govt_rate(m, unit="bp")


def test_ref_govt_rate_is_point_in_time_synthetic() -> None:
    rng = np.random.default_rng(0)
    vals = list(5.9 + rng.normal(0, 0.003, 60)) + list(5.75 + rng.normal(0, 0.003, 60))
    vals[20] = 6.3
    m = _market(vals)
    full = macro.ref_govt_rate(m)
    for k in (10, 21, 64, 70, 119):
        assert macro.ref_govt_rate(m.iloc[: k + 1]).iloc[-1] == pytest.approx(full.iloc[k], nan_ok=True)


@needs_panel
def test_ref_govt_rate_regression_spec_12_3_2() -> None:
    m = store.load_market(PANEL)
    r = macro.ref_govt_rate(m, unit="pct")
    assert r.loc["2026-11-20"] == pytest.approx(5.75, abs=0.01)
    assert r.loc["2026-11-17"] == pytest.approx(5.75, abs=0.01)
    naive = macro.implied_govt_rate(m)
    assert naive.loc["2026-11-17"] == pytest.approx(6.25, abs=0.01)  # prime imprimée 0,01
    assert m.loc["2026-11-17", "risk_premium"] == 0.01
    assert r.loc["2023-12-29"] == pytest.approx(5.90, abs=0.01)
    assert r.loc["2024-01-11"] == pytest.approx(5.75, abs=0.01)  # 5e séance au nouveau niveau
    assert r.loc["2024-01-08"] == pytest.approx(5.90, abs=0.01)  # point-in-time : pas encore confirmé
    assert r.loc["2019-01-15"] == pytest.approx(6.00, abs=0.01)
    assert r.loc["2020-03-31"] == pytest.approx(6.50, abs=0.01)
    assert r.loc["2020-08-03":"2021-02-24"].isna().all()  # période incohérente (10,3-11,7 %) exclue
    assert r.loc["2024-01-11":"2026-11-20"].sub(5.75).abs().max() < 0.01
    assert macro.ref_govt_rate(PANEL, asof="2026-11-20") == pytest.approx(0.0575, abs=1e-4)
    full = macro.ref_govt_rate(m)
    cut = macro.ref_govt_rate(m.loc[:"2026-11-17"])
    assert cut.iloc[-1] == pytest.approx(full.loc["2026-11-17"])  # aucune information future


# ---------------------------------------------------------------------------
# Prime de risque pays
# ---------------------------------------------------------------------------


def test_country_crp_table_and_formula() -> None:
    table = {"CI": 0.0, "BJ": 0.009, "TG": 0.022, "SN": 0.0305, "ML": 0.041, "NE": 0.051, "BF": 0.053}
    for c, v in table.items():
        assert macro.country_crp(c) == pytest.approx(v)
        assert macro.country_crp(c, method="formula") == pytest.approx(v, abs=6e-4), c
    assert macro.country_crp("CI", method="formula") == 0.0
    assert macro.country_crp("GN") == macro.country_crp("PANAFRICAIN") == pytest.approx(0.04)
    assert macro.country_crp("SN", unit="pct") == pytest.approx(3.05)
    s = macro.country_crp()
    assert s["HORS_UEMOA"] == pytest.approx(0.04) and s["CI"] == 0.0
    base = macro.country_crp("BF", method="formula")
    higher = macro.country_crp("BF", method="formula", jump_prob={"BF": (0.20, 0.30)})
    lower = macro.country_crp("BF", method="formula", jump_prob={"BF": (0.05, 0.30)})
    assert lower < base < higher
    assert lower == pytest.approx(0.038, abs=6e-4)  # revue 05 §12.4 : p_sév 5 % -> 3,8 %
    with pytest.raises(KeyError):
        macro.country_crp("FR")
    with pytest.raises(ValueError):
        macro.country_crp("SN", method="autre")


def test_cost_of_equity_snts_example() -> None:
    # Revue 05 §12.2 : CRP SNTS ≈ 3,7 % (détention) / 3,8 % (clients) ; k ≈ 5,75 + 4,0 + 3,75 ≈ 13,5 %.
    k_det = macro.cost_of_equity("SNTS")
    k_cli = macro.cost_of_equity("SNTS", variant="clients")
    assert k_det - 0.0575 - 0.04 == pytest.approx(0.0372, abs=5e-4)
    assert k_cli - 0.0575 - 0.04 == pytest.approx(0.0378, abs=5e-4)
    assert 0.133 <= k_det <= 0.137
    assert macro.cost_of_equity("SGBC", beta=0.8) == pytest.approx(0.0575 + 0.8 * 0.04)


# ---------------------------------------------------------------------------
# Pas de cotation et bandes (§7.1)
# ---------------------------------------------------------------------------


def test_price_band_regression_spec_12_3_3() -> None:
    assert macro.price_band(4385) == (4060, 4710)
    low, high = macro.price_band(13, "ETIT")
    assert high == 14 and low == 13
    assert macro.price_band(57) == (53, 61)
    assert macro.price_band(1000) == (925, 1075)
    assert macro.tick_size(99.0) == 1 and macro.tick_size(100) == 5 and macro.tick_size(4385) == 5
    assert macro.tick_size([13, 150]).tolist() == [1, 5]


def test_price_band_frame_matches_scalar() -> None:
    refs = pd.Series([13, 57, 99, 100, 101, 4385, 38795, np.nan])
    lo, hi = macro.price_band_frame(refs)
    for r, a, b in zip(refs, lo, hi):
        if np.isnan(r):
            assert np.isnan(a) and np.isnan(b)
        else:
            assert (a, b) == macro.price_band(r)
    df = pd.DataFrame({"A": [4385.0, 13.0]})
    lo, hi = macro.price_band_frame(df)
    assert lo["A"].tolist() == [4060, 13] and hi["A"].tolist() == [4710, 14]


@needs_panel
def test_price_bands_contain_closes_2026() -> None:
    """Contrôle de données sur S0 (2026) : la clôture reste dans les bornes de la référence de la veille."""
    eq = pd.read_parquet(PANEL / "equities.parquet").sort_values(["symbol", "date"])
    eq["ref_prev"] = eq.groupby("symbol")["ref_price"].shift(1)
    flags = store.stats_mask(PANEL, wide=False)[["date", "symbol", "multi_session"]]
    x = eq.merge(flags, on=["date", "symbol"], how="left")
    x = x[(x["date"] >= "2026-01-01") & (x["status"] == "traded") & x["ref_prev"].notna() & ~x["ex_div"]
          & ~x["multi_session"].fillna(False).astype(bool)]
    lo, hi = macro.price_band_frame(x["ref_prev"])
    inside = (x["close"] >= lo - 1e-9) & (x["close"] <= hi + 1e-9)
    assert len(x) > 10_000 and inside.mean() > 0.999


# ---------------------------------------------------------------------------
# Règlement et date de détachement (§5.2, §7.1.5)
# ---------------------------------------------------------------------------


def test_settlement_lag() -> None:
    assert macro.settlement_lag("2025-12-03") == 3
    assert macro.settlement_lag("2025-12-04") == 2
    assert macro.settlement_lag(pd.Timestamp("2017-01-02")) == 3
    assert macro.settlement_lag(["2025-12-03", "2025-12-04", "2026-11-20"]).tolist() == [3, 2, 2]


def test_shift_sessions_and_calendar_fallback() -> None:
    cal = pd.DatetimeIndex(["2026-05-21", "2026-05-22", "2026-05-26", "2026-05-27"])  # 25/05 férié
    assert macro.shift_sessions("2026-05-26", -1, cal) == pd.Timestamp("2026-05-22")
    assert macro.shift_sessions("2026-05-22", 1, cal) == pd.Timestamp("2026-05-26")
    assert macro.shift_sessions("2026-05-27", 2, cal) == pd.Timestamp("2026-05-29")  # au-delà : jours ouvrés
    assert macro.shift_sessions("2026-05-26", 0, cal) == pd.Timestamp("2026-05-26")
    assert macro.shift_sessions("2026-05-26", -1) == pd.Timestamp("2026-05-25")  # sans calendrier
    assert len(macro.session_index(pd.DataFrame({"date": cal}))) == 4


def test_ex_date_rule_boundaries_synthetic() -> None:
    cal = pd.bdate_range("2025-11-24", "2025-12-19")
    # Registres le 05/12/2025 : dernier jour avec droit réglé en J+3 -> ex le 03/12.
    assert macro.ex_date_rule("2025-12-05", cal) == pd.Timestamp("2025-12-03")
    # Registres le 08/12/2025 : dernier jour avec droit le 04/12 (J+2) -> ex le 05/12.
    assert macro.ex_date_rule("2025-12-08", cal) == pd.Timestamp("2025-12-05")
    assert macro.ex_date_rule("2025-12-01", cal) == pd.Timestamp("2025-11-27")


@needs_panel
def test_ex_date_rule_regression_spec_12_3_4() -> None:
    sess = store.load_sessions(PANEL).reset_index()
    assert macro.ex_date_rule("2026-05-26", sess) == pd.Timestamp("2026-05-22")  # lundi 25/05/2026 férié
    assert macro.ex_date_rule("2025-05-22", sess) == pd.Timestamp("2025-05-20")
    assert macro.ex_date_rule("2026-05-26", PANEL) == pd.Timestamp("2026-05-22")  # chemin du panel accepté
    # Sans calendrier, le férié est inconnu : la règle donnerait le 25/05/2026 (d'où ``sessions``).
    assert macro.ex_date_rule("2026-05-26") == pd.Timestamp("2026-05-25")
    dv = pd.read_parquet(PANEL / "dividends.parquet")
    snts = dv[dv["symbol"] == "SNTS"].set_index("payment_date")["ex_date"]
    assert snts.loc["2026-05-26"] == pd.Timestamp("2026-05-22") and snts.loc["2025-05-22"] == pd.Timestamp("2025-05-20")
    # Contrôle global (données 2022-2026, hors détections faites après un trou de BOC).
    chk = macro.ex_date_check(dv, sess)
    recent = chk[(chk["ex_date"] >= "2022-01-01") & ~chk["evidence"].fillna("").str.contains("data_gap")]
    assert recent["match"].mean() > 0.9
    assert recent.loc[recent["ex_date"] >= "2025-12-04", "match"].all()  # régime J+2 : 35 sur 35
