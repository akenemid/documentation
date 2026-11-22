"""Tests de la construction de portefeuille v1 (spécification §4.2, §6, §9.1, §11).

Bande 30/50, nombre de lignes, plafonds (ligne, secteur, pays, AES, liquidité),
mode repli, déterminisme, faisabilité (somme ≤ 0,98, aucun plafond violé de plus de
1e-9), variantes G (HRP incliné) et H (moyenne-variance + Kelly actif).

Toutes les données sont **synthétiques** (générateurs à graine fixe), sauf un contrôle
de forme sur le panel réel à une date de S0 (aucune performance n'est calculée ; S1
reste vierge).
"""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from brvm_alpha import reference as ref
from brvm_alpha.config import Constraints, CostModel
from brvm_alpha.portfolio.construct import (
    PORTFOLIO_V1_DEFAULTS,
    SPEC_COUNTRY_MULTIPLIER,
    GroupCap,
    _lex_maxmin,
    _progressive_fill,
    aes_caps,
    audit_weights,
    build_group_caps,
    build_portfolio,
    central_one_way_cost,
    constraint_violations,
    country_caps,
    equal_weight_with_caps,
    fractional_kelly_scale,
    hrp_tilt_rates,
    is_fallback,
    line_caps,
    n_holdings,
    portfolio_params,
    reference_weights_pit,
    score_ranks,
    sector_caps,
    select_with_band,
    target_portfolio,
    weekly_covariance,
    weekly_returns,
)
from brvm_alpha.portfolio.risk import hrp_weights

ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "data" / "panel"
TOL = 1e-9
SYMS = list(ref.SYMBOLS_2026)


def _names(n: int, prefix: str = "T") -> list[str]:
    return [f"{prefix}{i:02d}" for i in range(n)]


def _scores(names, seed: int = 0) -> pd.Series:
    rng = np.random.default_rng(seed)
    return pd.Series(rng.normal(size=len(names)), index=names)


def _assert_invariants(w: pd.Series, diag: dict, budget: float = 0.98) -> None:
    """Invariants de la spécification : somme ≤ 0,98 et aucun plafond violé de plus de 1e-9."""
    assert np.all(np.isfinite(w.to_numpy()))
    assert (w >= -TOL).all()
    assert w.sum() <= budget + 1e-12
    for key, val in diag["violations"].items():
        assert val <= TOL, f"{key} violé de {val}"
    caps = diag["caps"]
    nz = w[w > 0]
    assert (nz <= caps["upper"].reindex(nz.index) + TOL).all()
    assert (nz >= PORTFOLIO_V1_DEFAULTS["min_weight"] - TOL).all()
    for gc in caps["groups"]:
        assert gc.load(w) <= gc.cap + TOL, gc.label
    assert len(nz) <= PORTFOLIO_V1_DEFAULTS["max_names"] or diag["mode"] == "repli"


# ---------------------------------------------------------------------------
# Paramètres
# ---------------------------------------------------------------------------


def test_defaults_match_specification():
    p = portfolio_params()
    assert p["gross_equity"] == 0.98
    assert (p["n_divisor"], p["min_names"], p["max_names"], p["min_eligible"]) == (3, 12, 20, 15)
    assert (p["entry_pct"], p["exit_pct"]) == (0.30, 0.50)
    assert (p["max_weight"], p["min_weight"]) == (0.10, 0.02)
    assert p["country_multiplier"] == {"CI": 1.0, "BJ": 1.0, "TG": 0.9, "SN": 0.85, "BF": 0.75, "ML": 0.7, "NE": 0.6}
    assert p["country_multiplier"] == ref.COUNTRY_MULTIPLIER
    assert (p["sector_cap_floor"], p["sector_cap_max"], p["sector_cap_mult"]) == (0.15, 0.45, 1.5)
    assert (p["country_cap_max"], p["country_cap_floor"], p["country_cap_mult"]) == (0.30, 0.10, 1.5)
    assert p["aes_cap_multiple"] == 1.25
    assert (p["max_participation"], p["days_to_liquidate"]) == (0.10, 20.0)
    assert (p["hrp_gamma"], p["hrp_linkage"], p["hrp_distance_of_distances"]) == (0.5, "single", True)
    assert (p["cov_freq"], p["cov_weeks"], p["cov_min_weeks"], p["cov_shrinkage_floor"]) == ("W-FRI", 104, 52, 0.5)
    assert (p["mv_ic"], p["mv_risk_aversion"]) == (0.02, 5.0)
    assert (p["kelly_fraction"], p["kelly_fraction_max"], p["kelly_max_gross"]) == (0.25, 0.5, 1.0)
    # config.py est calibré sur les mêmes valeurs
    c = Constraints()
    assert (c.max_weight, c.min_weight, c.max_names, c.min_names) == (0.10, 0.02, 20, 12)
    assert (c.max_sector_weight, c.max_country_weight, c.max_adv_participation, c.cash_buffer) == (0.45, 0.30, 0.10, 0.02)


def test_params_from_strategy_yaml_equal_defaults():
    settings = pytest.importorskip("brvm_alpha.settings")
    cfg = settings.load_strategy_config()
    p_yaml = portfolio_params(cfg)
    p_def = portfolio_params()
    for key in p_def:
        assert p_yaml[key] == p_def[key], key


def test_params_validation():
    with pytest.raises(ValueError, match="inconnus"):
        portfolio_params({"max_wieght": 0.1})
    with pytest.raises(ValueError, match="weighting"):
        portfolio_params({"weighting": "kelly"})
    with pytest.raises(ValueError, match="min_weight"):
        portfolio_params({"min_weight": 0.2})
    assert portfolio_params({"max_weight": 0.08})["max_weight"] == 0.08


# ---------------------------------------------------------------------------
# 1. Nombre de lignes et mode repli
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("n", "expected"),
    [(0, 0), (5, 5), (14, 14), (15, 12), (36, 12), (37, 12), (38, 13), (40, 13), (45, 15), (59, 20), (60, 20), (90, 20)],
)
def test_n_holdings(n, expected):
    assert n_holdings(n) == expected
    assert is_fallback(n) == (n < 15)


# ---------------------------------------------------------------------------
# 2. Sélection avec bande 30/50
# ---------------------------------------------------------------------------


def _ranked(n: int) -> pd.Series:
    """Scores strictement décroissants : T00 est le meilleur."""
    names = _names(n)
    return pd.Series(np.linspace(2.0, -2.0, n), index=names)


def test_band_from_cash_adds_top_30pct_only():
    sc = _ranked(40)
    sel = select_with_band(sc, None, sc.index, n_holdings(40))
    assert (sel.entry_rank, sel.exit_rank, sel.n_target) == (12, 20, 13)
    assert sel.selected == _names(12)  # 30 % de 40 = 12 titres, ≥ 12 : pas de complément
    assert all(sel.reasons[s].startswith("ajouté") for s in sel.selected)
    assert sel.reasons["T12"].startswith("non retenu")
    assert sel.reserve == [f"T{i:02d}" for i in range(12, 20)]


def test_band_keeps_held_inside_top_half_and_sells_outside():
    sc = _ranked(40)
    held = pd.Series({"T05": 0.08, "T19": 0.08, "T20": 0.08, "T35": 0.08, "OLD": 0.05})
    sel = select_with_band(sc, held, sc.index, 13)
    assert "T19" in sel.selected and sel.reasons["T19"].startswith("conservé")  # rang 20 ≤ 20
    assert "T20" not in sel.selected and sel.reasons["T20"].startswith("vendu")  # rang 21 > 20
    assert "T35" not in sel.selected
    assert sel.reasons["OLD"] == "vendu : titre non éligible à la date de décision"
    # ajouts jusqu'à n_cible = 13 : T05 et T19 conservés + 11 ajouts depuis les 30 % supérieurs
    assert len(sel.selected) == 13
    assert set(sel.selected) == {"T19"} | set(_names(12))
    assert set(sel.sold) == {"T20", "T35", "OLD"}


def test_band_completion_below_min_names():
    sc = _ranked(20)  # n_cible = 12, 30 % = 6, 50 % = 10
    sel = select_with_band(sc, None, sc.index, n_holdings(20))
    assert sel.selected == _names(12)
    assert sel.reasons["T07"].startswith("complément : moins de 12 lignes")
    assert sel.reasons["T11"].startswith("complément hors bande")
    strict = select_with_band(sc, None, sc.index, 12, fill_beyond_exit=False)
    assert strict.selected == _names(10)


def test_band_caps_at_max_names():
    sc = _ranked(60)  # 50 % = 30
    held = pd.Series(0.03, index=_names(30))
    sel = select_with_band(sc, held, sc.index, n_holdings(60))
    assert sel.selected == _names(20)
    assert all(sel.reasons[s].startswith("retiré : au-delà de 20 lignes") for s in _names(30)[20:])


def test_band_held_count_towards_target():
    sc = _ranked(60)  # 30 % = 18, n_cible = 20
    held = pd.Series(0.04, index=_names(5) + [f"T{i:02d}" for i in range(24, 29)])
    sel = select_with_band(sc, held, sc.index, 20)
    assert len(sel.selected) == 20
    assert sel.kept == _names(5) + [f"T{i:02d}" for i in range(24, 29)]
    assert sel.added == [f"T{i:02d}" for i in range(5, 15)]


def test_band_respects_holdable_and_no_buy():
    sc = _ranked(40)
    held = pd.Series({"T03": 0.05})
    sel = select_with_band(sc, held, sc.index, 13, holdable=[s for s in sc.index if s != "T01"], no_buy=["T02", "T03"])
    assert "T01" not in sel.selected and "plancher" in sel.reasons["T01"]
    assert "T02" not in sel.selected and "achat bloqué" in sel.reasons["T02"]
    assert "T03" in sel.selected  # détenu : conservé malgré le blocage des achats
    # 9 ajouts possibles dans les 30 % supérieurs (T01 et T02 écartés) + T03 = 10 < 12 : complément
    assert sel.completed == ["T12", "T13"]
    assert len(sel.selected) == 12


def test_band_is_deterministic_with_ties():
    names = _names(30)
    sc = pd.Series([1.0] * 10 + [0.0] * 10 + [-1.0] * 10, index=names)
    sel1 = select_with_band(sc, None, names, 12)
    perm = np.random.default_rng(3).permutation(30)
    sc2 = sc.iloc[perm]
    sel2 = select_with_band(sc2, None, list(sc2.index), 12)
    assert sel1.selected == sel2.selected
    assert sel1.reasons == sel2.reasons
    # égalités départagées par le symbole
    assert list(score_ranks(sc2, sc2.index).index[:10]) == _names(10)
    # score manquant : classé en dernier
    sc3 = sc.copy()
    sc3["T00"] = np.nan
    assert score_ranks(sc3, names).index[-1] == "T00"


# ---------------------------------------------------------------------------
# 3. Plafonds par ligne
# ---------------------------------------------------------------------------


def test_line_caps_multipliers_reductions_and_floor():
    syms = ["CI1", "SN1", "TG1", "NE1", "NE2", "BF1", "CI2", "CI3", "CI4", "GW1"]
    country = pd.Series(["CI", "SN", "TG", "NE", "NE", "BF", "CI", "CI", "CI", "GW"], index=syms)
    u6 = {"NE1": True, "NE2": True, "BF1": True, "CI2": True}
    u7 = ["NE2", "BF1", "CI2"]
    risk = pd.Series({"CI3": 1, "CI4": 2, "CI2": 1})
    caps = line_caps(syms, country, u6, u7, risk)
    assert caps["CI1"] == pytest.approx(0.10)
    assert caps["SN1"] == pytest.approx(0.085)
    assert caps["TG1"] == pytest.approx(0.09)
    assert caps["NE1"] == pytest.approx(0.03)  # 10 % × 0,6 × 0,5
    assert caps["NE2"] == 0.0  # 1,5 % < plancher 2 % : ligne supprimée
    assert caps["BF1"] == 0.0  # 10 % × 0,75 × 0,25 = 1,875 %
    assert caps["CI2"] == 0.0  # 10 % × 0,5³ = 1,25 % < 2 %
    assert caps["CI3"] == pytest.approx(0.05)  # un drapeau R11
    assert caps["CI4"] == 0.0  # deux drapeaux R11 : exclusion
    assert caps["GW1"] == pytest.approx(0.06)  # pays inconnu : plus petit multiplicateur
    det = line_caps(syms, country, u6, u7, risk, detail=True)
    assert "exclu" in det.loc["CI4", "cap_reason"]
    assert "plancher" in det.loc["NE2", "cap_reason"]


def test_line_caps_dataframe_flags_single_reduction():
    syms = ["A", "B", "C"]
    flags = pd.DataFrame({"R4": [True, False, True], "R11": [0, 1, 1], "R12": [False, False, True]}, index=syms)
    caps = line_caps(syms, {"A": "CI", "B": "CI", "C": "CI"}, None, None, flags)
    # R4, R11 (un drapeau) et R12 : une seule réduction × 0,5, non cumulative
    assert caps.tolist() == pytest.approx([0.05, 0.05, 0.05])


def test_line_caps_default_country_from_reference():
    caps = line_caps(["SNTS", "BOAN", "SGBC", "ONTBF"])
    assert caps.to_dict() == pytest.approx({"SNTS": 0.085, "BOAN": 0.06, "SGBC": 0.10, "ONTBF": 0.075})


# ---------------------------------------------------------------------------
# 4. Plafonds de groupe
# ---------------------------------------------------------------------------


def test_sector_caps_formula():
    lab = pd.Series(["FIN"] * 20 + ["TEL"] * 4 + ["CB"] * 8 + ["IND"] * 8, index=_names(40))
    caps = sector_caps(lab)
    assert caps["FIN"] == pytest.approx(0.45)  # 1,5 × 0,5 = 0,75 → 45 %
    assert caps["TEL"] == pytest.approx(0.15)  # 1,5 × 0,1 = 0,15
    assert caps["CB"] == pytest.approx(0.30)  # 1,5 × 0,2
    lab2 = pd.Series(["FIN"] * 39 + ["SPU"], index=_names(40))
    assert sector_caps(lab2)["SPU"] == pytest.approx(0.15)  # plancher 15 %


def test_country_caps_formula():
    lab = pd.Series(["CI"] * 28 + ["SN"] * 4 + ["BF"] * 3 + ["NE"] * 1 + ["BJ"] * 4, index=_names(40))
    b = pd.Series(ref.REFERENCE_COUNTRY_WEIGHTS_20261120)
    caps = country_caps(lab, b)
    assert "CI" not in caps.index  # aucun plafond propre
    assert caps["SN"] == pytest.approx(0.30)  # 1,5 × max(0,10 ; 0,2294) = 0,344 → 30 %
    assert caps["BF"] == pytest.approx(1.5 * 0.0750)  # max(u = 0,075 ; b = 0,0729)
    assert caps["NE"] == pytest.approx(0.10)  # plancher
    assert caps["BJ"] == pytest.approx(0.15)  # 1,5 × max(0,10 ; 0,0455)
    no_ref = country_caps(lab)
    assert no_ref["SN"] == pytest.approx(0.15)  # u_c seul (prudent)


def test_aes_caps_seat_and_lambda():
    syms = ["BOABF", "ONTBF", "BOAM", "BOAN", "SNTS", "SGBC"]
    lab = pd.Series([ref.country_of(s) for s in syms], index=syms)
    b = ref.REFERENCE_COUNTRY_WEIGHTS_20261120
    groups = aes_caps(lab, seat_reference=b, lambda_reference=0.144)
    seat, lam = groups
    assert seat.kind == "aes_seat" and lam.kind == "aes_lambda"
    assert seat.cap == pytest.approx(1.25 * (0.0729 + 0.0072 + 0.0048))  # ≈ 10,6 %
    assert seat.cap == pytest.approx(0.106125)
    assert seat.coefficients.to_dict() == {"BOABF": 1.0, "ONTBF": 1.0, "BOAM": 1.0, "BOAN": 1.0, "SNTS": 0.0, "SGBC": 0.0}
    assert lam.coefficients["SNTS"] == pytest.approx(0.238)  # SNTS exposé au Mali (variante détention)
    assert lam.cap == pytest.approx(0.18)


# ---------------------------------------------------------------------------
# 5. Équipondération projetée
# ---------------------------------------------------------------------------


def test_equal_weight_unconstrained():
    names = _names(15)
    w = equal_weight_with_caps(names, 0.10, [], 0.98)
    assert w.tolist() == pytest.approx([0.98 / 15] * 15, abs=1e-15)
    assert w.attrs["feasible_full_budget"] and w.attrs["solver"] == "remplissage"


def test_equal_weight_redistributes_line_excess_equally():
    names = _names(15)
    upper = pd.Series(0.10, index=names)
    upper[["T00", "T01"]] = 0.05
    w = equal_weight_with_caps(names, upper, [], 0.98)
    assert w[["T00", "T01"]].tolist() == pytest.approx([0.05, 0.05])
    assert w.drop(["T00", "T01"]).tolist() == pytest.approx([0.88 / 13] * 13)
    assert w.sum() == pytest.approx(0.98)
    assert "plafond de ligne T00 : 5.00%" in w.attrs["active_constraints"]


def test_equal_weight_group_cap():
    names = _names(15)
    coef = pd.Series([1.0] * 8 + [0.0] * 7, index=names)
    g = [GroupCap("secteur FIN", "sector", 0.30, coef)]
    w = equal_weight_with_caps(names, 0.10, g, 0.98)
    assert w.iloc[:8].tolist() == pytest.approx([0.0375] * 8)
    assert w.iloc[8:].tolist() == pytest.approx([0.68 / 7] * 7)
    assert g[0].load(w) == pytest.approx(0.30)


def test_equal_weight_infeasible_keeps_cash_and_signals():
    names = _names(12)
    w = equal_weight_with_caps(names, 0.05, [], 0.98)
    assert w.sum() == pytest.approx(0.60)
    assert not w.attrs["feasible_full_budget"]
    assert w.attrs["shortfall"] == pytest.approx(0.38)
    assert "non atteignable" in w.attrs["messages"][0]


def test_equal_weight_min_weight_prunes_worst_ranked():
    names = _names(15)
    coef = pd.Series([1.0] * 8 + [0.0] * 7, index=names)
    g = [GroupCap("secteur ENE", "sector", 0.15, coef)]  # 8 × 1,875 % < 2 %
    w = equal_weight_with_caps(names, 0.10, g, 0.98)
    assert w["T07"] == 0.0 and "plancher" in w.attrs["removed"]["T07"]
    assert w.iloc[:7].tolist() == pytest.approx([0.15 / 7] * 7)
    assert w.iloc[8:].tolist() == pytest.approx([0.10] * 7)  # 7 × 10 % = 70 %
    assert w.sum() == pytest.approx(0.85)
    assert audit_weights(w, 0.10, g, 0.98, 0.02)["min_weight"] == 0.0


def test_equal_weight_completes_min_names_and_capacity():
    names = _names(12)
    reserve = ["R00", "R01", "R02"]
    upper = pd.Series(0.10, index=names + reserve)
    coef = pd.Series([1.0] * 12 + [0.0] * 3, index=names + reserve)
    g = [GroupCap("pays X", "country", 0.80, coef)]
    # capacité : 12 titres plafonnés à 80 % ; deux titres de la réserve suffisent pour 98 %
    w = equal_weight_with_caps(names, upper, g, 0.98, capacity_reserve=reserve, max_names=20)
    assert w.attrs["capacity_added"] == ["R00", "R01"]
    assert w.sum() == pytest.approx(0.98)
    assert w[["R00", "R01"]].tolist() == pytest.approx([0.09, 0.09])
    no_fill = equal_weight_with_caps(names, upper, g, 0.98)
    assert no_fill.sum() == pytest.approx(0.80) and not no_fill.attrs["feasible_full_budget"]
    # complément sous min_names
    w2 = equal_weight_with_caps(names[:10], upper, [], 0.98, reserve=reserve, min_names=12)
    assert w2.attrs["added"] == ["R00", "R01"] and int((w2 > 0).sum()) == 12


def test_overlapping_caps_use_lexicographic_lp():
    """Plafonds croisés : le remplissage s'arrête à 15 %, la capacité vaut 20 %."""
    names = ["A", "B", "C"]
    g = [
        GroupCap("g1", "custom", 0.10, pd.Series({"A": 1.0, "B": 1.0})),
        GroupCap("g2", "custom", 0.10, pd.Series({"A": 1.0, "C": 1.0})),
    ]
    w = equal_weight_with_caps(names, 0.10, g, 0.98, min_weight=0.0)
    assert w.attrs["solver"] == "pl_lexicographique"
    assert w.sum() == pytest.approx(0.20, abs=1e-8)
    assert w.to_dict() == pytest.approx({"A": 0.0, "B": 0.10, "C": 0.10}, abs=1e-8)
    w2 = equal_weight_with_caps(names, 0.10, g, 0.98)  # plancher 2 % : A est supprimée
    assert w2["A"] == 0.0 and w2.sum() == pytest.approx(0.20, abs=1e-8)


@pytest.mark.parametrize("seed", range(25))
def test_allocation_invariants_random(seed):
    """Invariants sur des problèmes aléatoires (plafonds croisés, coefficients λ)."""
    rng = np.random.default_rng(seed)
    n = int(rng.integers(5, 21))
    names = _names(n)
    upper = pd.Series(rng.choice([0.0, 0.015, 0.03, 0.05, 0.075, 0.085, 0.10], n), index=names)
    groups = []
    for k in range(int(rng.integers(0, 5))):
        mem = rng.random(n) < 0.4
        coef = pd.Series(np.where(mem, rng.choice([1.0, 0.238, 0.5], n), 0.0), index=names)
        groups.append(GroupCap(f"g{k}", "custom", float(rng.uniform(0.05, 0.5)), coef))
    rates = None if seed % 2 else pd.Series(rng.uniform(0.2, 2.0, n), index=names)
    w = equal_weight_with_caps(names, upper, groups, 0.98, rates=rates)
    viol = audit_weights(w, upper, groups, 0.98, 0.02)
    assert max(viol.values()) <= TOL, viol
    assert w.sum() <= 0.98 + 1e-12
    # investissement = capacité maximale des lignes retenues (PL), à 1e-7 près
    from brvm_alpha.portfolio.construct import _group_arrays, _max_investable

    kept = list(w[w > 0].index)
    if kept:
        a, c = _group_arrays(groups, kept)
        cap = _max_investable(np.zeros(len(kept)), upper[kept].to_numpy(), a, c)
        assert w.sum() == pytest.approx(min(0.98, cap), abs=1e-6)


@pytest.mark.parametrize("seed", range(20))
def test_progressive_fill_is_lexicographic_maxmin(seed):
    """Le remplissage progressif donne l'allocation max-min lexicographique (vérifiée par PL)."""
    rng = np.random.default_rng(100 + seed)
    n = int(rng.integers(3, 15))
    u = rng.uniform(0.02, 0.12, n)
    k = int(rng.integers(0, 4))
    a = np.where(rng.random((k, n)) < 0.5, rng.choice([1.0, 0.3], (k, n)), 0.0)
    c = rng.uniform(0.05, 0.4, k)
    r = rng.uniform(0.5, 2.0, n) if seed % 2 else np.ones(n)
    w = _progressive_fill(r, u, a, c, 0.98)
    lex = _lex_maxmin(r, u, a, c, float(w.sum()))
    assert lex is not None
    assert np.allclose(w, lex, atol=1e-6)


# ---------------------------------------------------------------------------
# 6. Chaîne complète target_portfolio
# ---------------------------------------------------------------------------


def _universe(n_elig: int = 40, seed: int = 0) -> tuple[pd.Series, list[str]]:
    rng = np.random.default_rng(seed)
    elig = sorted(rng.choice(SYMS, n_elig, replace=False).tolist())
    return pd.Series(rng.normal(size=len(SYMS)), index=SYMS), elig


@pytest.mark.parametrize("seed", range(12))
def test_target_portfolio_invariants_realistic_universe(seed):
    scores, elig = _universe(int(15 + seed * 2.7), seed)
    rng = np.random.default_rng(seed)
    mdv = pd.Series(np.exp(rng.normal(np.log(5e6), 1.2, len(SYMS))), index=SYMS)
    spread = pd.Series(rng.uniform(0.002, 0.03, len(SYMS)), index=SYMS)
    ctx = {"mdv63": mdv, "spread": spread, "capital": 1e7}
    w, d = target_portfolio(scores, elig, None, ctx)
    _assert_invariants(w, d)
    assert d["mode"] == "selection"
    assert set(d["reasons"]) == set(w.index) and all(d["reasons"].values())
    # deuxième mois : la bande joue
    held = w[w > 0]
    w2, d2 = target_portfolio(scores + rng.normal(scale=0.3, size=len(SYMS)), elig, held, ctx)
    _assert_invariants(w2, d2)
    band = d2["band"]
    assert all(band.ranks[s] <= band.exit_rank for s in band.kept)


def test_target_portfolio_from_cash_reaches_98pct_and_12_to_20_lines():
    scores, elig = _universe(40, 7)
    w, d = target_portfolio(scores, elig)
    assert w.sum() == pytest.approx(0.98, abs=1e-12)
    assert 12 <= d["n_holdings"] <= 20
    assert d["feasible_full_budget"]
    assert d["n_target"] == 13 and (d["entry_rank"], d["exit_rank"]) == (12, 20)


def test_target_portfolio_is_deterministic():
    scores, elig = _universe(38, 11)
    held = pd.Series(0.05, index=elig[:9])
    w1, d1 = target_portfolio(scores, elig, held)
    perm = np.random.default_rng(0).permutation(len(scores))
    w2, d2 = target_portfolio(scores.iloc[perm], list(reversed(elig)), held.iloc[::-1])
    pd.testing.assert_series_equal(w1, w2)
    assert d1["reasons"] == d2["reasons"]
    pd.testing.assert_frame_equal(d1["table"], d2["table"])


def test_target_portfolio_aes_seat_cap_binds():
    aes_names = ["BOABF", "CBIBF", "ONTBF", "BOAM", "BOAN"]
    others = [s for s in SYMS if s not in aes_names][:35]
    elig = aes_names + others
    scores = pd.Series(0.0, index=elig)
    scores[aes_names] = [3.0, 2.9, 2.8, 2.7, 2.6]
    scores[others] = np.linspace(1.0, -1.0, len(others))
    w, d = target_portfolio(scores, elig, None, {"reference_weights": ref.REFERENCE_COUNTRY_WEIGHTS_20261120,
                                                  "asof": "2026-11-27"})
    _assert_invariants(w, d)
    seat_cap = d["caps"]["aes"]["bloc AES (siège)"]
    assert seat_cap == pytest.approx(1.25 * (0.0729 + 0.0072 + 0.0048))
    assert w[aes_names].sum() <= seat_cap + TOL
    assert w[aes_names].sum() == pytest.approx(seat_cap)  # plafond actif
    assert any("bloc AES (siège)" in x for x in d["active_constraints"])


def test_target_portfolio_aes_lambda_cap_with_pit_references():
    close = pd.Series(1000.0, index=SYMS)
    shares = pd.Series(ref.SHARES_OUTSTANDING_2026, dtype=float)
    pit = reference_weights_pit(close, shares)
    assert set(pit) == {"seat", "exposure"}
    assert pit["seat"].sum() == pytest.approx(1.0) and pit["exposure"].sum() == pytest.approx(1.0)
    elig = SYMS[:40]
    scores = pd.Series(np.linspace(1, -1, 40), index=elig)
    scores["SNTS"] = 5.0
    w, d = target_portfolio(scores, elig, None, {"close": close, "shares": shares})
    _assert_invariants(w, d)
    assert not any("λ non appliqué" in m for m in d["messages"])
    lam = next(g for g in d["caps"]["groups"] if g.kind == "aes_lambda")
    assert lam.coefficients["SNTS"] == pytest.approx(0.238)
    assert lam.load(w) <= lam.cap + TOL


def test_target_portfolio_liquidity_cap_and_u6_u7():
    scores, elig = _universe(30, 3)
    top = score_ranks(scores, elig).index[0]
    capital = 1e8
    mdv = pd.Series(5e7, index=SYMS)
    mdv[top] = 3e6  # 0,10 × 3 M × 20 / 100 M = 6 % ; U6 (< 2 M) non levé
    second = score_ranks(scores, elig).index[1]
    mdv[second] = 1.5e6  # U6 : poids max ÷ 2 ; liquidité : 3 %
    spread = pd.Series(0.005, index=SYMS)
    third = score_ranks(scores, elig).index[2]
    spread[third] = 0.03  # U7
    w, d = target_portfolio(scores, elig, None, {"mdv63": mdv, "spread": spread, "capital": capital})
    _assert_invariants(w, d)
    assert d["caps"]["liquidity"][top] == pytest.approx(0.06)
    assert w[top] <= 0.06 + TOL
    mult = SPEC_COUNTRY_MULTIPLIER.get(ref.country_of(second), 0.6)
    assert d["caps"]["line"][second] == pytest.approx(0.10 * mult * 0.5 if 0.10 * mult * 0.5 >= 0.02 else 0.0)
    assert w[second] <= min(0.03, d["caps"]["line"][second]) + TOL
    mult3 = SPEC_COUNTRY_MULTIPLIER.get(ref.country_of(third), 0.6)
    assert d["caps"]["line"][third] == pytest.approx(0.10 * mult3 * 0.5)


def test_target_portfolio_fallback_mode():
    elig = ["SGBC", "ORAC", "SNTS", "SIBC", "BOAC", "NTLC", "SOGC", "PALC", "CIEC", "SDCC"]
    scores = pd.Series(np.arange(10, 0, -1, dtype=float), index=elig)
    w, d = target_portfolio(scores, elig)
    assert d["mode"] == "repli" and d["n_target"] == 10
    _assert_invariants(w, d)
    assert (w[elig] > 0).all()
    # SNTS (SN) plafonné à 8,5 % ; TEL plafonné à max(15 % ; 1,5 × 2/10) = 30 % ; les autres égaux
    assert w["SNTS"] == pytest.approx(0.085)
    assert w[[s for s in elig if s != "SNTS"]].std() < 1e-12
    assert w.sum() == pytest.approx(0.98)
    assert any("repli" in m for m in d["messages"])


def test_target_portfolio_empty_universe():
    w, d = target_portfolio(pd.Series({"SGBC": 1.0}), [], pd.Series({"SGBC": 0.1}))
    assert w.sum() == 0.0 and d["mode"] == "vide"
    assert d["reasons"]["SGBC"].startswith("vendu")


def test_target_portfolio_no_buy_rules():
    scores, elig = _universe(40, 5)
    ranks = score_ranks(scores, elig)
    held_name, new_name = ranks.index[15], ranks.index[0]
    held = pd.Series({held_name: 0.04})
    w, d = target_portfolio(scores, elig, held, {"no_buy": [held_name, new_name]})
    _assert_invariants(w, d)
    assert w[new_name] == 0.0 and "achat bloqué" in d["reasons"][new_name]
    assert 0.0 < w[held_name] <= 0.04 + TOL  # conservé, sans renforcement


def test_target_portfolio_country_overrides():
    scores, elig = _universe(40, 9)
    sn = [s for s in elig if ref.country_of(s) == "SN"]
    scores[sn] = 5.0
    w, d = target_portfolio(scores, elig, None, {"country_cap_overrides": {"SN": 0.03}})
    _assert_invariants(w, d)
    assert w[sn].sum() <= 0.03 + TOL


@pytest.mark.skipif(not (PANEL / "equities.parquet").exists(), reason="panel réel absent")
def test_target_portfolio_real_panel_shape_s0():
    """Contrôle de forme sur le panel réel au 30/10/2026 (S0) : liquidité réelle, aucun calcul
    de performance. Univers simplifié (cotés, non suspendus, MDV63 ≥ 0,5 M)."""
    from brvm_alpha.data import store

    eq = store.load_equities(PANEL, start="2026-06-01", end="2026-10-30").reset_index()
    value = eq.pivot_table(index="date", columns="symbol", values="value", aggfunc="last").sort_index()
    mdv = value.iloc[-63:].fillna(0.0).median()
    last = eq[eq["date"] == eq["date"].max()].set_index("symbol")
    elig = sorted(s for s in mdv.index if mdv[s] >= 5e5 and last.get("status", pd.Series()).get(s) != "suspended")
    assert 15 <= len(elig) <= 48
    scores = pd.Series(np.random.default_rng(0).normal(size=len(elig)), index=elig)
    w, d = target_portfolio(scores, elig, None, {"mdv63": mdv, "capital": 1e7, "asof": "2026-10-30"})
    _assert_invariants(w, d)
    assert 12 <= d["n_holdings"] <= 20


# ---------------------------------------------------------------------------
# 7. Covariance hebdomadaire, variantes G et H
# ---------------------------------------------------------------------------


def _daily_returns(seed: int = 0, start: str = "2022-01-03", end: str = "2025-12-31", syms=None) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    syms = SYMS if syms is None else syms
    dates = pd.bdate_range(start, end)
    mkt = rng.normal(0, 0.008, (len(dates), 1))
    x = mkt * rng.uniform(0.5, 1.5, len(syms)) + rng.normal(0, 0.012, (len(dates), len(syms))) * rng.uniform(0.5, 2, len(syms))
    return pd.DataFrame(x, index=dates, columns=syms)


def test_weekly_returns_compounding_and_no_lookahead():
    idx = pd.bdate_range("2025-01-06", periods=12)  # lundi 06/01 → mardi 21/01
    r = pd.DataFrame({"A": 0.01, "B": np.nan}, index=idx)
    r.loc[idx[2], "B"] = 0.05
    wk = weekly_returns(r, asof=idx[-1])
    assert list(wk.index) == [pd.Timestamp("2025-01-10"), pd.Timestamp("2025-01-17")]  # semaine du 21/01 incomplète
    assert wk.loc["2025-01-10", "A"] == pytest.approx(1.01**5 - 1)
    assert wk.loc["2025-01-10", "B"] == pytest.approx(0.05)
    assert np.isnan(wk.loc["2025-01-17", "B"])
    r2 = r.copy()
    r2.loc[idx[-1], "A"] = 10.0  # après asof = idx[-2] : sans effet
    assert weekly_returns(r2, asof=idx[-2]).equals(weekly_returns(r, asof=idx[-2]))
    ex = weekly_returns(r, asof=idx[-1], exclude_windows=[("2025-01-06", "2025-01-08")])
    assert ex.loc["2025-01-10", "A"] == pytest.approx(1.01**2 - 1)


def test_weekly_covariance_window_min_weeks_and_shrinkage_floor():
    rets = _daily_returns(1, syms=_names(12))
    rets.iloc[:-200, -2:] = np.nan  # deux titres récents : < 52 semaines
    cov = weekly_covariance(rets, "2025-12-31")
    assert cov.attrs["n_weeks"] == 104
    assert set(cov.attrs["dropped"]) == {"T10", "T11"}
    assert cov.attrs["shrinkage"] >= 0.5 - 1e-12
    assert np.linalg.eigvalsh(cov.to_numpy()).min() > 0
    # plancher appliqué quand l'estimation est plus faible (beaucoup de semaines, peu de titres)
    long = _daily_returns(2, start="2000-01-03", syms=_names(3))
    cov2 = weekly_covariance(long, "2025-12-31", weeks=1000)
    assert cov2.attrs["shrinkage_estimated"] < 0.5
    assert cov2.attrs["shrinkage"] == pytest.approx(0.5)
    ann = weekly_covariance(rets, "2025-12-31", annualize=True)
    assert np.allclose(ann.to_numpy(), cov.to_numpy() * 52)
    later = rets.copy()
    later.loc["2025-12-01":] = 0.5  # données postérieures à asof : sans effet
    assert np.allclose(weekly_covariance(later, "2025-11-28").to_numpy(), weekly_covariance(rets, "2025-11-28").to_numpy())


def test_hrp_tilt_rates_gamma_zero_is_hrp():
    rets = _daily_returns(3, syms=_names(10))
    cov = weekly_covariance(rets, "2025-12-31")
    names = _names(10)
    rates, _ = hrp_tilt_rates(names, pd.Series(np.linspace(1, -1, 10), index=names), cov, gamma=0.0)
    hrp = hrp_weights(cov.loc[names, names], linkage_method="single", distance_of_distances=True)
    assert np.allclose(rates.to_numpy(), hrp.to_numpy())
    rates2, _ = hrp_tilt_rates(names, pd.Series(np.linspace(1, -1, 10), index=names), cov, gamma=0.5)
    assert rates2["T00"] / hrp["T00"] > rates2["T09"] / hrp["T09"]  # inclinaison vers les meilleurs scores


def test_variant_g_hrp_tilt_target_portfolio():
    rets = _daily_returns(4)
    scores, elig = _universe(40, 4)
    w, d = target_portfolio(scores, elig, None, {"returns": rets, "asof": "2025-12-31"}, {"weighting": "hrp_tilt"})
    _assert_invariants(w, d)
    assert d["weighting"] == "hrp_tilt" and d["cov_shrinkage"] >= 0.5 - 1e-12
    w_a, _ = target_portfolio(scores, elig, None, {"asof": "2025-12-31"})
    assert set(w[w > 0].index) <= set(w_a[w_a > 0].index) | set(d["band"].reserve) | set(d["band"].reserve_beyond)
    assert not np.allclose(w.to_numpy(), w_a.reindex(w.index).to_numpy())


def test_fractional_kelly_active_weights():
    alpha = pd.Series([0.02, 0.01, -0.01], index=list("abc"))
    cov = pd.DataFrame(np.diag([0.04, 0.05, 0.06]), index=list("abc"), columns=list("abc"))
    a = pd.Series([0.03, 0.0, -0.03], index=list("abc"))  # somme nulle
    num = float(a @ alpha)
    den = float(a @ cov @ a)
    s = fractional_kelly_scale(alpha, cov, fraction=0.25, max_gross=10.0, weights=a, normalize=False)
    assert s == pytest.approx(0.25 * num / den)
    assert fractional_kelly_scale(alpha, cov, weights=a) == 0.0  # normalisé : somme nulle → 0 (ancien comportement)
    assert fractional_kelly_scale(alpha, cov, weights=-a, normalize=False) == 0.0  # alpha actif < 0


def test_variant_h_mv_alpha_target_portfolio():
    rets = _daily_returns(5)
    scores, elig = _universe(40, 5)
    ctx = {"returns": rets, "asof": "2025-12-31"}
    w_a, _ = target_portfolio(scores, elig, None, ctx)
    w, d = target_portfolio(scores, elig, None, ctx, {"weighting": "mv_alpha"})
    _assert_invariants(w, d)
    assert 0.0 <= d["kelly_scale"] <= 1.0
    assert d["tcost"] == pytest.approx(central_one_way_cost())
    assert central_one_way_cost() == pytest.approx(CostModel().rate() + 0.0035 + 0.016 * 0.1)  # ≈ 1,75 %
    # λ faible : l'alpha domine, échelle de Kelly > 0 et portefeuille différent de A
    w2, d2 = target_portfolio(scores, elig, None, ctx, {"weighting": "mv_alpha", "mv_risk_aversion": 0.05})
    _assert_invariants(w2, d2)
    assert d2["kelly_scale"] > 0
    assert not np.allclose(w2.to_numpy(), w_a.reindex(w2.index).to_numpy())
    if d["kelly_scale"] == 0.0:
        assert np.allclose(w.to_numpy(), w_a.reindex(w.index).to_numpy())
        assert any("Kelly" in m for m in d["messages"])


def test_variants_require_covariance():
    scores, elig = _universe(40, 6)
    with pytest.raises(ValueError, match="covariance requise"):
        target_portfolio(scores, elig, None, {}, {"weighting": "hrp_tilt"})


# ---------------------------------------------------------------------------
# build_portfolio : plafonds linéaires supplémentaires (compatibilité)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("method", ["mv_alpha", "hrp_tilt", "equal"])
def test_build_portfolio_group_caps_with_fractional_coefficients(method):
    rng = np.random.default_rng(8)
    names = _names(20)
    rets = _daily_returns(8, syms=names)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        cov = weekly_covariance(rets, "2025-12-31", annualize=True)
    alpha = pd.Series(rng.normal(0.05, 0.05, 20), index=names)
    alpha.iloc[:5] += 0.3  # concentre l'alpha sur les 5 premiers
    coef = pd.Series([1.0, 0.5, 0.238, 1.0, 0.7] + [0.0] * 15, index=names)
    gc = [GroupCap("bloc", "custom", 0.12, coef)]
    cons = Constraints(max_weight=0.10, min_weight=0.02, max_names=20, min_names=12)
    w = build_portfolio(alpha, cov, cons, None, None, method=method, group_caps=gc, tcost=0.0)
    viol = constraint_violations(w, cons, group_caps=gc)
    assert viol["groups"] <= 1e-8 and max(viol.values()) <= 1e-8
    assert gc[0].load(w) <= 0.12 + 1e-8
    assert "groups" not in constraint_violations(w, cons)  # clé absente sans group_caps (compatibilité)


def test_build_group_caps_labels():
    syms = ["SNTS", "ORAC", "SGBC", "BOAN"]
    sec = pd.Series({"SNTS": "TEL", "ORAC": "TEL", "SGBC": "FIN", "BOAN": "FIN"})
    cty = pd.Series({s: ref.country_of(s) for s in syms})
    g = build_group_caps(syms, sec, cty, sector_caps(sec), country_caps(cty))
    labels = {x.label: x.cap for x in g}
    assert labels == pytest.approx({"secteur FIN": 0.45, "secteur TEL": 0.45, "pays NE": 0.30, "pays SN": 0.30})


def test_weekly_returns_usable_mask():
    idx = pd.bdate_range("2025-01-06", periods=10)
    r = pd.DataFrame({"A": 0.01, "B": 0.02}, index=idx)
    usable = pd.DataFrame(True, index=idx, columns=["A", "B"])
    usable.loc[idx[0], "A"] = False  # rendement multi-séances : exclu des statistiques
    wk = weekly_returns(r, asof=idx[-1], usable=usable)
    assert wk.loc["2025-01-10", "A"] == pytest.approx(1.01**4 - 1)
    assert wk.loc["2025-01-10", "B"] == pytest.approx(1.02**5 - 1)


@pytest.mark.parametrize("weighting", ["equal", "hrp_tilt", "mv_alpha"])
def test_every_zero_weight_selected_name_is_explained(weighting):
    rets = _daily_returns(9)
    scores, elig = _universe(40, 9)
    sec = pd.Series({s: ("ENE" if i < 9 else ref.sector_of(s)) for i, s in enumerate(score_ranks(scores, elig).index)})
    ctx = {"returns": rets, "asof": "2025-12-31", "sectors": sec}  # 9 titres ENE en tête : plafond 15 %
    w, d = target_portfolio(scores, elig, None, ctx, {"weighting": weighting, "mv_risk_aversion": 0.05})
    _assert_invariants(w, d)
    for s in d["band"].selected:
        if w[s] == 0:
            assert any(k in d["reasons"][s] for k in ("supprimée", "plancher", "poids final nul")), d["reasons"][s]


def test_capacity_completion_stays_in_top_half_unless_asked():
    """U6 sur tous les titres (plafond 5 %) : 12 lignes ne suffisent pas pour 98 %."""
    sc = _ranked(40)
    names = list(sc.index)
    ctx = {"countries": pd.Series("CI", index=names), "sectors": pd.Series([f"S{i % 8}" for i in range(40)], index=names),
           "low_liquidity": pd.Series(True, index=names)}
    w, d = target_portfolio(sc, names, None, ctx)
    _assert_invariants(w, d)
    assert d["n_holdings"] == 20  # 12 ajouts + 8 compléments de capacité (rangs 13 à 20)
    assert set(w[w > 0].index) == set(_names(20))
    assert w.sum() == pytest.approx(0.98)  # 20 × 5 % = 100 % ≥ 98 %
    assert all("50 % supérieurs" in d["reasons"][s] for s in _names(20)[12:])
    # rangs 13 à 20 : achat bloqué ; la réserve des 50 % supérieurs est vide → 12 × 5 % = 60 %
    ctx2 = dict(ctx, no_buy=_names(20)[12:])
    # lecture v1.0 (complément limité aux 50 % supérieurs) : explicite depuis l'additif v1.1
    w2, d2 = target_portfolio(sc, names, None, ctx2, {"capacity_beyond_exit": False})
    _assert_invariants(w2, d2)
    assert w2.sum() == pytest.approx(0.60) and not d2["feasible_full_budget"]
    assert any("non atteignable" in m for m in d2["messages"])
    w3, d3 = target_portfolio(sc, names, None, ctx2)  # additif v1.1, D4 (défaut) : au-delà des 50 %
    _assert_invariants(w3, d3)
    assert w3.sum() == pytest.approx(0.98) and d3["n_holdings"] == 20
    assert set(w3[w3 > 0].index) == set(_names(12)) | {f"T{i:02d}" for i in range(20, 28)}
    assert all("hors des 50 % supérieurs" in d3["reasons"][f"T{i:02d}"] for i in range(20, 28))
