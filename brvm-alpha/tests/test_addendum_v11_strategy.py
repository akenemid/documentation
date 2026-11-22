"""Tests de non-régression de l'additif v1.1 (§8.4) côté stratégie : D1, D3, D4, D5, D6, D8-D11.

Données **synthétiques** (``test_strategy_alpha.make_panels``, séances 2023-2024, ou panels
construits ici) et simples calculs de dates. Aucun backtest, aucune performance, aucun IC ni
aucun signal n'est évalué sur l'échantillon vierge S1 (2017-01-02 → 2022-11-16) : le test
« Mali 09/01/2022 » porte sur des cours aléatoires et ne mesure qu'une date d'action. Le seul
contrôle sur données réelles porte sur la décision du 20/11/2026 (S0).
"""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from test_strategy_alpha import SYMS, make_panels

from brvm_alpha import reference, settings
from brvm_alpha.backtest import engine
from brvm_alpha.backtest.engine import Backtester
from brvm_alpha.config import Constraints, CostModel, ExecutionModel
from brvm_alpha.portfolio import construct
from brvm_alpha.quant import features as F
from brvm_alpha.strategy import (
    FAMILY_V11,
    REFERENCE_VARIANT,
    VARIANT_SPECS,
    BrvmAlpha,
    dividend_amount_gap,
)

ROOT = Path(__file__).resolve().parents[1]
HAS_PANEL = (ROOT / "data" / "panel" / "equities.parquet").exists()
S1_END = pd.Timestamp("2022-11-16")

ZERO_COSTS = CostModel(sgi_commission=0.0, brvm_fee=0.0, dcbr_fee=0.0, vat_on_commission=0.0, impact_coef=0.0,
                       annual_custody=0.0, half_spread_default=0.0, account_fee_per_line_fcfa=0.0)


@pytest.fixture(scope="module")
def synth() -> dict:
    return make_panels()


def model(**kw) -> BrvmAlpha:
    kw.setdefault("notes", None)
    return BrvmAlpha(**kw)


# ---------------------------------------------------------------------------
# Contrat et paramètres (YAML 1.1, settings)
# ---------------------------------------------------------------------------


def test_contract_variants_and_exports():
    assert FAMILY_V11 == ("A", "B", "C", "D", "E", "F", "G", "H", "I")
    assert REFERENCE_VARIANT == "REF"
    assert set(VARIANT_SPECS) == set(FAMILY_V11) | {"REF"}
    assert VARIANT_SPECS["I"].kind == "core_satellite" and VARIANT_SPECS["I"].core_share == 0.5
    assert VARIANT_SPECS["REF"].kind == "reference"
    for v in VARIANT_SPECS:
        m = BrvmAlpha(cfg=None, variant=v, capital=10e6, validation_s1=False, window_basis=None,
                      history_start=None, notes=None, country_events=None)
        assert m.variant == v and m.window_basis == "sessions"
    with pytest.raises(TypeError):
        BrvmAlpha(cfg=3.0, notes=None)  # type: ignore[arg-type]
    m = BrvmAlpha(cfg=settings.load_strategy_config(), notes=None)  # dictionnaire = surcharges validées
    assert m.cfg["version"] == "1.1"


def test_yaml_v11_keys_validated():
    cfg = settings.load_strategy_config()
    assert cfg["version"] == "1.1"
    assert settings.window_basis_default(cfg) == "sessions"
    assert settings.min_obs_prorata_params(cfg) == {"signal_floor": 40, "filter_floor": 20, "max_stale": 5}
    assert cfg["validation"]["variants"] == list(FAMILY_V11) and cfg["validation"]["reference_variant"] == "REF"
    assert cfg["data"]["cap_guard_blocking"] is False and cfg["data"]["return_guard_blocking"] is True
    with pytest.raises(settings.StrategyConfigError, match="window_basis"):
        settings.load_strategy_config(overrides={"data": {"window_basis": "lignes"}})
    with pytest.raises(settings.StrategyConfigError, match="inconnue"):
        settings.load_strategy_config(overrides={"portfolio": {"capacity_fil": {"max_names": 20}}})
    bad = dict(cfg, version="1.0")
    with pytest.raises(settings.StrategyConfigError, match="version"):
        settings.validate_strategy_config(bad)
    pp = construct.portfolio_params(cfg)
    assert pp["capacity_beyond_exit"] is True and pp["capacity_cap_per_name"] == "budget/n_target"
    assert model().fingerprint != model(window_basis="boc").fingerprint
    assert model().fingerprint != model(country_events=False).fingerprint


# ---------------------------------------------------------------------------
# D1 : séances, bornes à 5 séances, seuils au prorata
# ---------------------------------------------------------------------------


def test_d1_prorata_arithmetic():
    assert int(F.prorata_min_obs(100, 126, 0, 40)) == 100  # aucun BOC manquant : m_eff = m
    assert int(F.prorata_min_obs(100, 126, 40, 40)) == 69  # ⌈100 × 86 / 126⌉
    assert int(F.prorata_min_obs(200, 250, 100, 40)) == 120  # ⌈200 × 150 / 250⌉
    assert int(F.prorata_min_obs(40, 63, 46, 20)) == 20  # ⌈40 × 17 / 63⌉ = 11 < plancher 20
    assert int(F.prorata_min_obs(100, 126, 120, 40)) == 40  # plancher des signaux
    assert int(F.prorata_min_obs(10, 63, 30, 20)) == 10  # le plancher ne relève jamais un seuil < plancher
    sess = np.r_[np.arange(1, 151), np.arange(191, 241)]
    assert int(F.missing_sessions_in_window(sess, 63)[-1]) == 13
    assert int(F.missing_sessions_in_window(np.arange(10, 30), 63)[-1]) == 0  # début de panel : pas d'amputation


def _bound_panel(stale: int) -> tuple[dict, pd.Timestamp]:
    """TR sur 300 séances ; la borne t − 126 tombe ``stale`` séances après le dernier BOC disponible."""
    last = 300
    bound = last - 126
    sess = np.r_[np.arange(1, bound - stale + 1), np.arange(bound + 1, last + 1)]
    dates = pd.bdate_range("2024-01-01", periods=len(sess))
    tr = pd.DataFrame({"X": 100.0 * 1.001 ** np.arange(len(sess))}, index=dates)
    return {"tr_index": tr, "session_no": pd.Series(sess, index=dates)}, dates[-1]


@pytest.mark.parametrize(("stale", "defined"), [(1, True), (5, True), (6, False), (12, False)])
def test_d1_window_bounds_at_most_five_sessions(stale, defined):
    panels, t = _bound_panel(stale)
    mom = F.mom_sessions(panels, window_basis="sessions")
    assert bool(np.isfinite(mom.loc[t, "X"])) is defined
    # report illimité (lecture antérieure) : toujours défini ; base « boc » : décalage en lignes
    assert np.isfinite(F.mom_sessions(panels, window_basis="sessions", max_stale_sessions=None).loc[t, "X"])


def test_d1_lowvol_prorata_and_floor():
    n = 300
    sess = np.r_[np.arange(1, 201), np.arange(261, 261 + n - 200)]  # 60 BOC manquants dans les 250 dernières
    dates = pd.bdate_range("2024-01-01", periods=n)
    rng = np.random.default_rng(1)
    tr = pd.DataFrame({"X": 100.0 * np.cumprod(1.0 + rng.normal(0, 0.01, n))}, index=dates)
    panels = {"tr_index": tr, "session_no": pd.Series(sess, index=dates)}
    t = dates[-1]
    raw = F.lowvol(panels, window_basis="sessions", prorata=False, fallback_window=250, fallback_min_obs=200)
    pro = F.lowvol(panels, window_basis="sessions", fallback_window=250, fallback_min_obs=200)
    assert np.isnan(raw.loc[t, "X"])  # 190 rendements < 200
    assert np.isfinite(pro.loc[t, "X"])  # seuil ⌈200 × 190 / 250⌉ = 152
    assert pro.loc[t, "X"] == pytest.approx(-tr["X"].pct_change().iloc[-190:].std(ddof=1), rel=1e-9)


def test_d1_vol_scaling_counts_sessions():
    n = 400
    dates = pd.bdate_range("2024-01-01", periods=n)
    rng = np.random.default_rng(2)
    spread = pd.Series(rng.normal(0, 0.01, n), index=dates)
    sess = np.r_[np.arange(1, 351), np.arange(401, 451)]  # 50 BOC manquants avant les 50 dernières lignes
    plain = F.vol_scaling(spread, min_history_months=1)
    by_sess = F.vol_scaling(spread, min_history_months=1, sess=sess)
    assert len(by_sess) == n and by_sess.between(0.5, 1.0).all()
    assert not plain.equals(by_sess)  # fenêtre de 126 séances : moins de valeurs qu'en lignes
    assert F.vol_scaling(spread, min_history_months=1, sess=pd.Series(sess, index=dates)).equals(by_sess)


def test_d1_defaults_and_universe_floor(synth):
    assert model().window_basis == "sessions"
    assert model(validation_s1=True).window_basis == "sessions"  # plus d'erreur : D1 tranche la base
    assert model(window_basis="boc").window_basis == "boc"
    idx = synth["close"].index
    t = idx[400]
    for gap, nonempty in ((40, True), (50, False)):
        p = dict(synth)
        sess = np.arange(1, len(idx) + 1)
        sess[390:] += gap
        p["session_no"] = pd.Series(sess, index=idx)
        u = model().universe(t, p)
        # gap 40 : 23 BOC dans les 63 dernières séances ≥ plancher 20 ; gap 50 : 13 < 20 : exclusion (D1)
        assert (u.attrs["n_eligible"] > 0) is nonempty
        if not nonempty:
            assert u["codes"].str.contains("U2").all()


# ---------------------------------------------------------------------------
# D3 : garde de capitalisation non bloquante ; |rendement| > 50 % bloquant
# ---------------------------------------------------------------------------


def test_d3_return_guard_still_blocks(synth):
    idx = synth["close"].index
    sym = SYMS[12]
    p = dict(synth)
    tr = synth["tr_index"].copy()
    tr.loc[idx[398]:, sym] *= 1.8  # rendement de +80 % le 398
    p["tr_index"] = tr
    dec = model().decide(idx[400], p)
    assert bool(dec.risk.loc[sym, "data_guard"]) and dec.weights[sym] == 0.0
    assert np.isnan(dec.signals["composite"][sym])
    mk = synth["market"].copy()
    mk.loc[mk["date"] == idx[400], "market_cap"] *= 1.2
    p["market"] = mk
    dec2 = model().decide(idx[400], p)
    assert dec2.diagnostics["cap_guard"]["alert"] and not dec2.diagnostics["cap_guard"].get("blocked")
    assert dec2.diagnostics["mode"] == "selection" and dec2.weights.sum() > 0.9


# ---------------------------------------------------------------------------
# D4 : remplissage de capacité
# ---------------------------------------------------------------------------


def _capacity_case(no_buy: list[str] | None = None, cap: object = "budget/n_target"):
    names = [f"T{i:02d}" for i in range(40)]
    sc = pd.Series(np.linspace(2.0, -2.0, 40), index=names)
    countries = pd.Series(["SN"] * 12 + ["CI"] * 28, index=names)  # bande (rangs 1-12) : un pays plafonné à 30 %
    ctx = {"countries": countries, "sectors": pd.Series([f"S{i % 8}" for i in range(40)], index=names),
           "reference_weights": {"seat": {"SN": 0.0, "CI": 1.0}}}
    if no_buy:
        ctx["no_buy"] = no_buy
    return construct.target_portfolio(sc, names, None, ctx, {"capacity_cap_per_name": cap})


def test_d4_capacity_added_names_capped_at_band_line_weight():
    w, d = _capacity_case()
    n_target = d["n_target"]
    cap = 0.98 / n_target
    cf = d["capacity_fill"]
    assert n_target == 13 and cf["cap_per_added"] == pytest.approx(cap)
    added = cf["added"]
    assert added and len(w[w > 0]) <= 20
    assert all(w[s] <= cap + 1e-12 for s in added)
    # Bande entièrement contrainte par son plafond pays (SN ≤ 30 % : 2,5 % par ligne) : la règle D4 borne
    # un titre ajouté au poids NOMINAL d'une ligne de la bande (98 % / n_cible), pas au poids réalisé
    # d'une ligne de la bande plafonnée par son groupe (lecture littérale de l'additif, signalée).
    band = [s for s in d["band"].selected if w.get(s, 0) > 0]
    assert sum(w[s] for s in band) == pytest.approx(0.30)
    assert cf["residual_cash"] == pytest.approx(0.98 - float(w.sum()))
    assert cf["residual_cash"] > 0.05 and not cf["feasible_full_budget"]  # reliquat en liquidités, publié
    assert all("D4" in d["reasons"][s] for s in added)
    # sans le plafond D4 (lecture v1.0) : un titre ajouté pèse plus qu'une ligne de la bande
    w0, d0 = _capacity_case(cap=None)
    assert max(w0[s] for s in d0["capacity_fill"]["added"]) > cap + 1e-6


def test_d4_capacity_goes_beyond_top_half_by_score():
    names = [f"T{i:02d}" for i in range(40)]
    _, d = _capacity_case(no_buy=names[12:20])
    added = d["capacity_fill"]["added"]
    assert added and all(int(s[1:]) >= 20 for s in added)  # rangs > 50 % (seuil 20)
    assert added == sorted(added)  # par ordre de score
    assert all("hors des 50 % supérieurs" in d["reasons"][s] for s in added)


@pytest.mark.skipif(not HAS_PANEL, reason="panel réel absent")
def test_d4_decision_20261120_variant_a():
    """Décision du 20/11/2026 (S0) : aucun titre ajouté au-delà de 98 % / n_cible ni de la plus lourde ligne de la bande."""
    from brvm_alpha.strategy import build_panels

    dec = BrvmAlpha(variant="A", notes=None).decide("2026-11-20", build_panels())
    pdg = dec.diagnostics["portfolio"]
    cf = pdg["capacity_fill"]
    w = dec.weights
    cap = 0.98 / pdg["n_target"]
    band = [s for s in pdg["band"].selected if w.get(s, 0) > 0]
    assert all(w[s] <= cap + 1e-12 for s in cf["added"])
    if cf["added"]:
        assert max(w[s] for s in cf["added"]) <= max(w[s] for s in band) + 1e-12
    assert w.sum() <= 0.98 + 1e-9 and cf["residual_cash"] == pytest.approx(0.98 - float(w.sum()), abs=1e-9)


# ---------------------------------------------------------------------------
# D5 : drawdown relatif depuis t0, panier w_EW, bande de non-transaction
# ---------------------------------------------------------------------------


def test_d5_relative_drawdown_measured_from_first_investment(synth):
    idx = synth["close"].index
    mt = synth["market_tr"]
    ta, t0, t1 = idx[300], idx[340], idx[380]
    k = 1e7
    nav0 = k  # liquidités jusqu'à t0, puis exactement le TR
    nav1 = k * float(mt[t1] / mt[t0])
    m = model()
    m.record_nav(ta, k, invested=False)
    m.record_nav(t0, nav0, invested=True)
    m.record_nav(t1, nav1, invested=True)
    rel = m.decide(t1, synth).diagnostics["relative_drawdown"]
    assert m.relative_dd_start == t0 and rel["t0"] == t0
    assert rel["dd"] == pytest.approx(0.0, abs=1e-12)  # aucun pari mécanique sur la période en liquidités
    old = model()  # lecture v1.0 : depuis la première VL (période en liquidités comprise)
    old.record_nav(ta, k)
    old.record_nav(t0, nav0)
    old.record_nav(t1, nav1)
    exp = (nav1 / k) / float(mt[t1] / mt[ta]) / max(1.0, (nav0 / k) / float(mt[t0] / mt[ta])) - 1.0
    assert old.decide(t1, synth).diagnostics["relative_drawdown"]["dd"] == pytest.approx(exp)


def test_d5_ew_basket_is_top20_ranked(synth):
    idx = synth["close"].index
    mt = synth["market_tr"]
    t0, t1 = idx[300], idx[390]
    m = model()
    m.record_nav(t0, 1e7, invested=True)
    m.record_nav(t1, 1e7 * float(mt[t1] / mt[t0]) * 0.84, invested=True)  # −16 % : division par 2
    dec = m.decide(t1, synth)
    assert dec.diagnostics["relative_drawdown"].get("halve")
    basket = dec.diagnostics["ew_basket"]["names"]
    elig = [s for s in dec.universe.index if dec.universe.loc[s, "eligible"]]
    assert len(elig) > 20 and len(basket) == 20
    ranks = construct.score_ranks(dec.score["final"].reindex(elig), elig)
    assert set(basket) == set(list(ranks.index)[:20])


def test_d5_engine_executes_small_entries_and_exits_despite_band(synth):
    """Bande de 2 points : une entrée ou une sortie complète de 1,5 point est exécutée (exemption)."""
    idx = synth["close"].index
    x, y, z = SYMS[10], SYMS[11], SYMS[12]
    d1, d2, d3 = idx[340], idx[350], idx[360]
    plan = {d1: {x: 0.49, y: 0.49}, d2: {x: 0.48, y: 0.485, z: 0.015}, d3: {x: 0.49, y: 0.49}}

    def fn(asof, view):
        return pd.Series(plan[pd.Timestamp(asof)]) if pd.Timestamp(asof) in plan else None

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = Backtester(synth, ZERO_COSTS, Constraints(), 10e6, ExecutionModel()).run(
            fn, rebalance=[d1, d2, d3], start=idx[335], end=idx[370])
    tz = res.trades[res.trades["symbol"] == z]
    assert (tz["qty"] > 0).any() and (tz["date"][tz["qty"] > 0] > d2).all()  # entrée < bande : exécutée
    assert (tz["qty"] < 0).any() and (tz["date"][tz["qty"] < 0] > d3).all()  # sortie complète : exécutée
    tx = res.trades[(res.trades["symbol"] == x) & (res.trades["date"] > d2) & (res.trades["date"] <= d3)]
    assert tx.empty  # 0,49 → 0,48 : sous la bande, aucun ordre


# ---------------------------------------------------------------------------
# D6 : montants de dividende (signaux = connu en t ; flux = corrigé)
# ---------------------------------------------------------------------------


def test_d6_signals_use_amount_known_at_t(synth):
    idx = synth["close"].index
    p = dict(synth)
    tab = synth["dividends_table"].copy()
    tab["amount_cashflow"] = tab["amount"] * 1.05  # correction ultérieure (flux)
    p["dividends_table"] = tab
    gap = dividend_amount_gap(p)
    assert gap["gap"].to_numpy() == pytest.approx((tab["amount"] * 0.05).to_numpy())
    assert gap.attrs["n_differences"] == len(tab) and gap.attrs["total_gap_per_share"] > 0
    t = idx[400]
    a = model().signals(t, synth)
    b = model().signals(t, p)
    for key in ("DY", "S2", "composite"):
        pd.testing.assert_series_equal(a[key], b[key])  # le montant corrigé ne change aucun signal
    assert dividend_amount_gap({}).attrs["n_differences"] == 0


@pytest.mark.skipif(not HAS_PANEL, reason="panel réel absent")
def test_d6_build_panels_interface():
    from brvm_alpha.strategy import build_panels

    p = build_panels(end="2026-11-20")
    tab = p["dividends_table"]
    assert {"amount", "amount_cashflow", "amount_revised", "revised_seen"} <= set(tab.columns)
    gap = dividend_amount_gap(p)
    assert len(gap) == len(tab) and np.isfinite(gap.attrs["total_gap_per_share"])


# ---------------------------------------------------------------------------
# D8 : indice discipliné (REF)
# ---------------------------------------------------------------------------


def test_d8_disciplined_index_rules():
    names = [f"N{i:02d}" for i in range(25)]
    cap = pd.Series([800.0, 100.0] + [60.0] * 20 + [0.2, 0.1, 0.05], index=names)
    sectors = pd.Series(["TEL", "TEL"] + ["FIN"] * 10 + ["IND"] * 13, index=names)
    ctx = {"countries": pd.Series("CI", index=names), "sectors": sectors}
    w, d = construct.disciplined_index_portfolio(cap, names[:22] + names[22:], ctx)
    assert d["selected"] == names[:20]  # 20 plus grosses capitalisations éligibles
    b = cap / cap.sum()
    lc = d["caps"]["line"]
    assert lc["N00"] == pytest.approx(max(0.10, min(0.30, 1.25 * b["N00"])))  # = 30 %
    assert lc["N05"] == pytest.approx(max(0.10, min(0.30, 1.25 * b["N05"])))  # = 10 %
    assert d["caps"]["sector"]["TEL"] == pytest.approx(max(0.15, 1.25 * (b["N00"] + b["N01"])))
    assert d["caps"]["sector"]["FIN"] == pytest.approx(max(0.15, 1.25 * b[names[2:12]].sum()))
    assert w.sum() == pytest.approx(0.98) and w["N00"] == pytest.approx(0.30)
    rest = w.drop(["N00"])  # N00 au plafond de 30 % ; l'excédent est réparti au prorata des capitalisations
    assert np.allclose(rest / cap[rest.index], (rest / cap[rest.index]).iloc[0])  # ∝ capitalisation
    tiny = pd.Series([400.0] + [60.0] * 18 + [0.01], index=names[:20])
    w2, d2 = construct.disciplined_index_portfolio(tiny, list(tiny.index), ctx)
    assert "N19" not in w2.index and "N19" in d2["removed"]  # plancher de 0,5 %
    assert (w2 >= 0.005 - 1e-12).all()


def test_d8_ref_variant_and_annual_rebalancing(synth):
    idx = synth["close"].index
    t = idx[400]
    dec = model(variant="REF").decide(t, synth)
    w = dec.weights
    assert dec.diagnostics["mode"] == "indice_discipline" and w.sum() == pytest.approx(0.98)
    elig = dec.universe.index[dec.universe["eligible"]]
    caps = (synth["close_raw"].loc[t] * synth["shares"].loc[t])[elig].sort_values(ascending=False)
    assert set(w[w > 0].index) <= set(caps.index[:20])
    ref = model().disciplined_index_weights(t, synth)
    pd.testing.assert_series_equal(ref, w, check_names=False, check_exact=False, atol=1e-12)
    # rebalancement annuel : première décision de l'année, rien entre deux (sauf sorties forcées)
    fn = model(variant="REF").strategy_fn()
    first = fn(idx[240], engine.PanelView(synth, idx[240]))
    assert first is not None and first.sum() == pytest.approx(0.98)
    assert idx[240].year == idx[250].year
    assert fn(idx[250], engine.PanelView(synth, idx[250])) is None
    jan = next(d for d in idx if d.year == idx[240].year + 1)
    assert fn(jan, engine.PanelView(synth, jan)) is not None


def test_d8_forced_exit_between_rebalances(synth):
    idx = synth["close"].index
    m = model(variant="REF")
    w0 = m.decide(idx[290], synth).weights
    held = w0[w0 > 0].copy() * 0.95
    held[SYMS[3]] = 0.03  # suspendu du 300 au 319 : inéligible (U1)
    dec = m.decide(idx[305], synth, held=held)
    ix = dec.diagnostics["index"]
    assert ix["action"] == "conservation" and ix["changed"] and SYMS[3] in ix["forced_exits"]
    assert dec.weights[SYMS[3]] == 0.0
    others = held.drop(SYMS[3])
    assert dec.weights.reindex(others.index).to_numpy() == pytest.approx(others.to_numpy())


# ---------------------------------------------------------------------------
# D9 : variante I cœur-satellite
# ---------------------------------------------------------------------------


def test_d9_core_satellite_sum_and_projection():
    core = pd.Series({"A": 0.50, "B": 0.30, "C": 0.18})
    sat = pd.Series({"A": 0.10, "D": 0.44, "E": 0.44})
    up = pd.Series(1.0, index=list("ABCDE"))
    w, d = construct.core_satellite_weights(core, sat, up, [], budget=0.98)
    assert not d["projected"]
    assert w.to_dict() == pytest.approx({"A": 0.30, "B": 0.15, "C": 0.09, "D": 0.22, "E": 0.22})
    g = [construct.GroupCap("secteur X", "sector", 0.20, pd.Series({"D": 1.0, "E": 1.0}))]
    w2, d2 = construct.core_satellite_weights(core, sat, up, g, budget=0.98)
    assert d2["projected"] and g[0].load(w2) == pytest.approx(0.20) and w2.sum() == pytest.approx(0.98)
    free = w2[["A", "B", "C"]]
    assert np.allclose(free / w[["A", "B", "C"]], (free / w[["A", "B", "C"]]).iloc[0])  # excédent au prorata


def test_d9_variant_i_decision_and_annual_core(synth):
    idx = synth["close"].index
    t1, t2 = idx[290], idx[330]
    assert t1.year == t2.year
    m = model(variant="I")
    dec = m.decide(t1, synth)
    w = dec.weights
    assert dec.diagnostics["mode"] == "coeur_satellite" and w.sum() <= 0.98 + 1e-9
    w_ref = model(variant="REF").decide(t1, synth).weights
    w_a = dec.diagnostics["satellite"]["weights"].reindex(w.index).fillna(0.0)
    raw = 0.5 * w_ref + 0.5 * w_a
    if not dec.diagnostics["core_satellite"]["projected"]:
        assert w.to_numpy() == pytest.approx(raw.reindex(w.index).to_numpy())
    for g in dec.diagnostics["portfolio"]["caps"]["groups"]:
        assert g.load(w) <= g.cap + 1e-9
    assert set(w[w > 0].index) == set(raw[raw > 0].index)
    later = m.decide(t2, synth)
    core = later.diagnostics["core"]
    assert core["core_action"] == "derive" and core["index"]["t0"] == t1  # cœur rebalancé une fois par an
    assert m._sleeves["a"]["t"] == t2  # côté A : chaque mois


def test_variants_i_and_ref_run_with_backtester(synth):
    idx = synth["close"].index
    for v in ("I", "REF"):
        m = model(variant=v)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            res = Backtester(synth, ZERO_COSTS, Constraints(), 10e6, ExecutionModel()).run(
                m.strategy_fn(), rebalance="M", start=idx[300], end=idx[-1])
        assert np.isfinite(res.equity).all() and (res.cash >= -1e-6).all()
        assert res.weights.sum(axis=1).iloc[-1] > 0.9


# ---------------------------------------------------------------------------
# D10 : événements pays datés
# ---------------------------------------------------------------------------

_S1_CHRONOLOGY = [
    ("2018-07-29", "ML", "election"), ("2019-02-24", "SN", "election"), ("2020-02-22", "TG", "election"),
    ("2020-08-18", "ML", "coup"), ("2020-10-31", "CI", "election"), ("2020-11-22", "BF", "election"),
    ("2020-12-27", "NE", "election"), ("2021-04-11", "BJ", "election"), ("2021-05-24", "ML", "coup"),
    ("2022-01-09", "ML", "severe"), ("2022-01-24", "BF", "coup"), ("2022-07-03", "ML", "relief"),
    ("2022-09-30", "BF", "coup"),
]
_LATER = [
    ("2023-07-26", "NE", "coup"), ("2023-07-30", "NE", "severe"), ("2024-02-24", "NE", "relief"),
    ("2024-03-24", "SN", "election"), ("2025-10-25", "CI", "election"), ("2026-04-12", "BJ", "election"),
]


def test_d10_reference_chronology_exact():
    ev = reference.COUNTRY_EVENTS
    got = [(str(r.date.date()), r.country, r.rule) for r in ev.itertuples()]
    assert got == _S1_CHRONOLOGY + _LATER
    assert list(ev.loc[ev["sample"] == "S1", "date"].dt.strftime("%Y-%m-%d")) == [x[0] for x in _S1_CHRONOLOGY]
    assert {"date", "country", "rule", "source", "confidence", "action_date"} <= set(ev.columns)
    assert ev.loc[ev["rule"] == "election", "event_date"].notna().all()
    assert (ev["confidence"] == "M").all()  # dates [NON VÉRIFIÉ] en source primaire


def test_d10_mali_announced_sunday_acts_monday():
    assert reference.country_event_action_date("2022-01-09") == pd.Timestamp("2022-01-10")
    cal = pd.bdate_range("2021-12-01", "2022-02-28")
    assert reference.country_event_action_date("2022-01-09", cal) == pd.Timestamp("2022-01-10")
    assert reference.country_event_action_date("2022-01-24", cal) == pd.Timestamp("2022-01-25")
    # Décision à la clôture du vendredi 07/01 : exécution le lundi 10/01, l'annonce du dimanche est connue.
    rng = np.random.default_rng(5)
    close = pd.DataFrame(1000.0 * np.cumprod(1 + rng.normal(0, 0.01, (len(cal), 2)), axis=0),
                         index=cal, columns=["BOAM", "SNTS"]).round()
    panels = {"close_raw": close}
    m = model()
    for t, known in (("2022-01-06", False), ("2022-01-07", True), ("2022-01-10", True)):
        d = m._prepare(panels, t)
        st = m._country_rule_state(d, d.country_events)
        assert ("ML" in st and st["ML"]["rule"] == "severe") is known, t
        if known:
            assert st["ML"]["no_buy"]
            assert st["ML"]["elapsed"] == (0 if t == "2022-01-07" else 1)  # 10/01 : première séance de la règle
    m._calendar = cal  # calendrier publié des séances : même résultat
    assert m._next_session("2022-01-07") == pd.Timestamp("2022-01-10")
    shocks = m.engine_country_shocks()
    ml = shocks[shocks["country"] == "ML"]
    assert list(ml["date"]) == [pd.Timestamp("2022-01-09")]  # moteur : séances strictement postérieures
    assert model(country_events=False).country_events is None
    d = model(country_events=False)._prepare(panels, "2022-01-10")
    assert d.country_events is None


def test_d10_default_events_apply_on_synthetic_s0_dates(synth):
    # NE : coup 26/07/2023 puis sanctions 30/07/2023 (dates de S0) : règle sévère active, achats bloqués.
    idx = synth["close"].index
    t = idx[idx.searchsorted(pd.Timestamp("2023-08-04"))]
    dec = model().decide(t, synth, portfolio=False)
    ne = [s for s in dec.risk.index if reference.country_of(s) == "NE"]
    if ne:
        assert dec.diagnostics["country_rules"]["NE"]["rule"] == "severe"
        assert dec.risk.loc[ne, "block_buys"].all()


# ---------------------------------------------------------------------------
# D11 : aucune note de l'analyste en validation S1
# ---------------------------------------------------------------------------


def test_d11_notes_forced_off_in_validation_s1(synth):
    m = BrvmAlpha(notes="auto", validation_s1=True)
    assert m.notes_source is None
    t = synth["close"].index[400]
    dec = m.decide(t, synth)
    assert any("D11" in x for x in dec.messages)
    assert (dec.risk["tilt"] == 0).all() and not dec.risk["veto"].any()
    notes = pd.DataFrame([{"symbol": SYMS[10], "note": "veto"}])
    assert not m.risk_flags(t, synth, notes=notes)["veto"].any()
    assert m.cfg["events"]["S5_news_score"]["weight"] == 0.0
