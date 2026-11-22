"""Tests de non-régression des corrections de la validation, des paramètres et des utilitaires.

Revue du moteur v1 (22/11/2026). Données **synthétiques** datées hors S1 (2030 et après) ; le
seul calendrier de 2021 sert à des comptages de séances (aucun rendement de S1).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from brvm_alpha import settings
from brvm_alpha.backtest import metrics as mt
from brvm_alpha.backtest.engine import Backtester
from brvm_alpha.backtest.walkforward import (
    STATUT_INDETERMINE,
    cpcv,
    evaluate_status,
    purged_kfold,
    variant_promotion,
)
from brvm_alpha.config import CostModel
from brvm_alpha.portfolio import construct
from brvm_alpha.quant import scoring
from brvm_alpha.strategy import BrvmAlpha

ROOT = Path(__file__).resolve().parents[1]
WEEKS = pd.date_range("2030-01-04", periods=312, freq="W-FRI")
SUBS = [(WEEKS[0], WEEKS[155]), (WEEKS[156], WEEKS[-1])]


def _bench(n: int = 312, seed: int = 1) -> pd.Series:
    rng = np.random.default_rng(seed)
    return pd.Series(rng.normal(0.002, 0.02, n), index=WEEKS[:n])


def _good(n: int = 312, seed: int = 2) -> pd.Series:
    rng = np.random.default_rng(seed)
    return pd.Series(rng.normal(0.002, 0.006, n), index=WEEKS[:n])


# ---------------------------------------------------------------------------
# §8.1 : fenêtre 2021 exclue par défaut, observations multi-semaines retirées
# ---------------------------------------------------------------------------


def test_weekly_returns_excludes_2021_window_by_default():
    days = pd.bdate_range("2021-06-01", "2021-07-16")
    days = days[(days < "2021-06-10") | (days > "2021-06-24")]  # trou de BOC
    daily = pd.Series(0.001, index=days)
    w = mt.weekly_returns(daily)
    assert pd.Timestamp("2021-06-25") not in w.index  # semaine du rendement multi-séances du 25/06/2021
    assert pd.Timestamp("2021-06-25") in mt.weekly_returns(daily, exclude_windows=None, max_sessions=None).index
    assert pd.Timestamp("2021-07-16") in w.index


def test_weekly_returns_keeps_multi_session_weeks_for_chaining_and_flags_them():
    """§3.1.3 : un rendement sur plusieurs séances est exclu des statistiques de dispersion « mais gardé pour
    chaîner le TR » (correction du 22/11/2026 : il était retiré de tout, chaînage compris)."""
    days = pd.bdate_range("2030-08-05", "2030-10-04")
    days = days[(days < "2030-08-28") | (days > "2030-09-12")]  # 11 séances sans BOC
    daily = pd.Series(0.001, index=days)
    w = mt.weekly_returns(daily)
    assert pd.Timestamp("2030-09-13") in w.index  # gardée pour le chaînage
    assert "2030-09-13" in {str(d.date()) for d in w.attrs["multi_session_weeks"]}
    assert w.attrs["weeks_dropped"] == []
    disp = mt.weekly_returns(daily, max_sessions=mt.MAX_WEEKLY_SESSIONS)  # échantillon de dispersion
    assert pd.Timestamp("2030-09-13") not in disp.index
    assert "2030-09-13" in {str(d.date()) for d in disp.attrs["weeks_dropped"]}
    assert list(mt.dispersion_sample(w, w.attrs["multi_session_weeks"]).index) == list(disp.index)
    sess = pd.Series(np.arange(len(days)), index=days)  # numéros contigus : aucun trou réel
    assert len(mt.multi_session_weeks(days, session_no=sess)) == 0
    assert list(mt.multi_session_weeks(days)) == [pd.Timestamp("2030-09-13")]


def test_bootstrap_ci_needs_two_mean_blocks():
    out = mt.bootstrap_ci(pd.Series([0.01, 0.02], index=WEEKS[:2]), "ir", n_boot=200)
    assert np.isnan(out["lower"]) and np.isnan(out["upper"]) and out["n_valid"] == 0


# ---------------------------------------------------------------------------
# §8.3 : longueur et couverture de l'échantillon, entrées propres à S2, démarrage, rotation
# ---------------------------------------------------------------------------


def test_status_short_sample_is_never_candidate():
    b = _bench()
    a = pd.Series(0.004 + np.random.default_rng(5).normal(0, 0.002, 312), index=WEEKS)  # actif très favorable
    for n in (4, 10, 51):
        subs = [(WEEKS[0], WEEKS[n // 2]), (WEEKS[n // 2 + 1], WEEKS[n - 1])]
        rep = evaluate_status(a.iloc[:n], a.iloc[:n], b, subs, turnover=0.1, pbo=0.2, cvar_ratio=1.0, n_boot=200)
        assert rep.statut == STATUT_INDETERMINE
        assert rep.groupe("candidat")["verifie"].isna().all()
        assert any("trop court" in x for x in rep.avertissements)


def test_status_coverage_and_nan_are_reported():
    b = _bench()
    a = _good()
    trunc = a.copy()
    trunc.iloc[200:] = np.nan
    rep = evaluate_status(trunc, trunc, b, SUBS, turnover=0.1, pbo=0.2, cvar_ratio=1.0, n_boot=200,
                          expected_period=(WEEKS[0], WEEKS[-1]))
    assert any("NaN" in x for x in rep.avertissements)
    assert rep.mesures["couverture"] < 0.95 and rep.statut != "CANDIDAT"


def test_status_s2_never_reuses_s1_ic():
    b = _bench()
    a = _good()
    ic = pd.Series(0.05 + 0.01 * np.sin(np.arange(70)), index=pd.date_range("2030-01-31", periods=70, freq="ME"))
    s2 = pd.Series(np.random.default_rng(9).normal(0.003, 0.006, 52),
                   index=pd.date_range("2037-01-02", periods=52, freq="W-FRI"))
    rep = evaluate_status(a, a, b, SUBS, turnover=0.1, pbo=0.1, pbo_slope=0.1, cvar_ratio=1.0, n_trials=63,
                          sr_variance=1e-4, registry_complete=True, ic_monthly=ic, s2_active_weekly_returns=s2,
                          n_boot=200)
    g7 = rep.critere("promotion_S2", "G7")
    assert g7["verifie"] is None  # avant : True avec les 70 IC de S1
    assert rep.mesures["promotion_S2_ic_mois"] == 0
    assert rep.statut != "PROMU"


def test_status_warmup_window_and_turnover_units():
    b = _bench()
    a = _good()
    expo = pd.Series(np.r_[np.zeros(20), np.full(292, 0.98)], index=WEEKS)
    rep = evaluate_status(a, a, b, SUBS, turnover=0.1, pbo=0.2, cvar_ratio=1.0, n_boot=200, exposure=expo)
    assert any("démarrage en liquidités" in x for x in rep.avertissements)
    rep2 = evaluate_status(a, a, b, SUBS, turnover=0.1, pbo=0.2, cvar_ratio=1.0, n_boot=200, exposure=expo,
                           start="first_investment")
    assert rep2.mesures["debut_evaluation"] == WEEKS[20] and rep2.mesures["n_semaines"] == 292
    rep3 = evaluate_status(a, a, b, SUBS, turnover=4.78, pbo=0.2, cvar_ratio=1.0, n_boot=200)
    assert any("annualisé" in x for x in rep3.avertissements)


def test_monthly_one_way_turnover_and_first_investment_from_result():
    dates = pd.bdate_range("2030-01-01", periods=90)
    close = pd.DataFrame({"X": 1000.0, "Y": 1000.0}, index=dates)
    vol = pd.DataFrame(1e6, index=dates, columns=close.columns)
    panels = {"close": close, "volume": vol, "value": close * vol}
    zero = CostModel(sgi_commission=0.0, brvm_fee=0.0, dcbr_fee=0.0, impact_coef=0.0, annual_custody=0.0,
                     half_spread_mult=0.0, account_fee_per_line_fcfa=0.0)
    plan = {dates[10]: {"X": 0.9}, dates[40]: {"Y": 0.9}, dates[70]: {"X": 0.9}}
    res = Backtester(panels, zero, capital=1e7).run(lambda t, v: None if t not in plan else pd.Series(plan[t]),
                                                    rebalance=list(plan))
    m = mt.monthly_one_way_turnover(res)
    assert 0.2 < m < 1.0 and res.turnover > 1.0  # annualisé ≠ mensuel
    assert mt.first_investment_date(res) == dates[11]


# ---------------------------------------------------------------------------
# §3.4 : règle de promotion d'une variante (N = 8)
# ---------------------------------------------------------------------------


def test_variant_promotion_rule():
    rng = np.random.default_rng(11)
    idx = pd.date_range("2030-01-04", periods=300, freq="W-FRI")
    fam = pd.DataFrame({v: rng.normal(0.0005, 0.01, 300) for v in "ABCDEFGH"}, index=idx)
    fam["E"] = fam["A"] + 0.004 + rng.normal(0, 0.002, 300)  # nettement meilleure que A
    rep = variant_promotion(fam, pbo=0.10)
    assert rep.n_trials == 8 and rep.criteres.loc["E", "bat_reference"] is True
    assert rep.criteres.loc["E", "promue"] is True and rep.principal == "E"
    assert variant_promotion(fam, pbo=0.40).principal == "A"  # PBO > 0,25 : A reste le principal
    weak = fam.copy()
    weak["E"] = fam["A"] - 0.001
    assert variant_promotion(weak, pbo=0.10).principal == "A"
    with pytest.raises(KeyError):
        variant_promotion(fam.drop(columns="A"), pbo=0.1)


# ---------------------------------------------------------------------------
# CPCV / k-fold purgé sur un calendrier trop court
# ---------------------------------------------------------------------------


def test_cpcv_rejects_empty_training_sets():
    with pytest.raises(ValueError, match="apprentissage"):
        cpcv(pd.bdate_range("2030-01-01", periods=15))
    with pytest.raises(ValueError, match="apprentissage"):
        cpcv(pd.bdate_range("2030-01-01", periods=60))
    with pytest.raises(ValueError):
        purged_kfold(pd.bdate_range("2030-01-01", periods=30), n_splits=2, purge=21, embargo=21, min_train=5)
    assert cpcv(pd.bdate_range("2030-01-01", periods=1200)).n_splits == 45


# ---------------------------------------------------------------------------
# Paramètres : une clé inconnue est refusée
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("over", [{"portfolio": {"max_wieght": 0.08}}, {"portfolo": {"max_weight": 0.08}},
                                  {"execution": {"max_carry_session": 3}},
                                  {"execution": {"carry_unfilled_max_session": 3}}])
def test_unknown_override_keys_are_rejected(over):
    with pytest.raises(settings.StrategyConfigError, match="inconnue"):
        settings.load_strategy_config(overrides=over)
    with pytest.raises(settings.StrategyConfigError):
        BrvmAlpha(notes=None, params=over)


def test_known_and_open_override_keys_still_accepted():
    cfg = settings.load_strategy_config(overrides={"portfolio": {"max_weight": 0.08},
                                                   "data": {"eps_override": {"SNTS": 1500.0}},
                                                   "execution": {"carry_unfilled_max_sessions": 3}})
    assert cfg["portfolio"]["max_weight"] == 0.08 and cfg["data"]["eps_override"]["SNTS"] == 1500.0
    with pytest.raises(ValueError, match="portfolio"):
        construct.portfolio_params({**cfg, "portfolio": {**cfg["portfolio"], "max_wieght": 0.1}})


# ---------------------------------------------------------------------------
# Messages d'erreur sur des entrées dégénérées
# ---------------------------------------------------------------------------


def test_degenerate_inputs_have_french_messages():
    with pytest.raises(ValueError, match="entier fini"):
        construct.n_holdings(float("nan"))
    z = scoring.rank_gauss_z(pd.Series({"A": 1.0, "B": 2.0, "C": 3.0}))
    assert isinstance(z, pd.Series) and z["B"] == 0.0
    with pytest.raises(TypeError, match="DataFrame"):
        scoring.rank_gauss_z([1.0, 2.0])  # type: ignore[arg-type]


def test_target_portfolio_without_finite_scores_is_equal_weight_fallback():
    syms = [f"S{i:02d}C" for i in range(20)]
    scores = pd.Series(np.nan, index=syms)
    ctx = {"capital": 1e7, "mdv63": pd.Series(1e8, index=syms), "sectors": {s: "FIN" for s in syms},
           "countries": {s: "CI" for s in syms}}
    w, diag = construct.target_portfolio(scores, syms, None, ctx, construct.portfolio_params())
    assert diag["mode"] == "repli"
    assert any("aucun score fini" in x for x in diag["messages"])
    assert int((w > 0).sum()) == 20  # panier équipondéré, et non 12 titres par ordre alphabétique


# ---------------------------------------------------------------------------
# Ligne de commande et conftest sans module des notes
# ---------------------------------------------------------------------------


def test_cli_refuses_s1_without_flag():
    out = subprocess.run([sys.executable, "-m", "brvm_alpha", "backtest", "--start", "2021-01-04", "--end",
                          "2021-03-31"], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert out.returncode == 2 and "S1" in out.stderr
    out = subprocess.run([sys.executable, "-m", "brvm_alpha", "backtest", "--start", "2021-01-04", "--end",
                          "2021-03-31", "--validation-s1"], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert out.returncode == 2 and "window-basis" in out.stderr


def test_conftest_survives_broken_notes_module(tmp_path):
    plug = tmp_path / "sans_notes.py"
    plug.write_text("import sys\nsys.modules['brvm_alpha.notes.model'] = None\n", encoding="utf-8")
    env_path = f"{tmp_path}:{ROOT}"
    out = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-p", "sans_notes",
                          "--rootdir", str(ROOT), "-c", "/dev/null", str(ROOT / "tests" / "test_review_engine_fixes.py"),
                          "-k", "unknown_execution"], cwd=ROOT, capture_output=True, text=True, timeout=300,
                         env={"PYTHONPATH": env_path, "PATH": "/usr/bin:/bin"})
    assert "ImportError while loading conftest" not in out.stdout + out.stderr
    assert out.returncode == 0, out.stdout[-2000:] + out.stderr[-2000:]
