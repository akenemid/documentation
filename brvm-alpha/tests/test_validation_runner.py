"""Tests de l'exécuteur de validation (additif v1.1 : D2, D6, D7, D12 ; spécification §8).

Toutes les données sont **synthétiques** (graines fixes) : aucun backtest, aucune performance,
aucun IC ni aucun signal n'est évalué sur les données réelles de l'échantillon vierge S1. Les
panels synthétiques datés de 2017-2018 ne servent qu'à exercer le chemin « S1 » du code (verrou,
plan, registre) ; ils ne contiennent aucune information sur le marché réel. Les modèles sont des
bouchons (momentum simple) : le contrat ``BrvmAlpha`` n'est pas requis. Aucune requête réseau.
"""

from __future__ import annotations

import json
import math
import subprocess
import types
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from brvm_alpha import cli
from brvm_alpha.backtest import metrics as mt
from brvm_alpha.backtest.engine import Backtester
from brvm_alpha.backtest.walkforward import (
    FAMILY_V11,
    N_TRIALS_START_V11,
    REFERENCE_TRIAL_ID,
    STATUT_DECLARE,
    STATUT_EXECUTE,
    STATUT_INDETERMINE,
    STATUT_PREENREGISTRE,
    TrialRegistry,
    evaluate_status,
    variant_promotion,
)
from brvm_alpha.config import CostModel
from brvm_alpha.validation import (
    RunSpec,
    ValidationFailed,
    ValidationRefused,
    run_plan,
    run_validation,
)
from brvm_alpha.validation import lock as lk

# ---------------------------------------------------------------------------
# Données synthétiques et bouchons
# ---------------------------------------------------------------------------

_K = {"A": 5, "B": 4, "C": 6, "D": 5, "E": 3, "F": 7, "G": 5, "H": 4, "I": 8, "REF": 9}
_LB = {"A": 60, "B": 40, "C": 90, "D": 70, "E": 60, "F": 80, "G": 50, "H": 60, "I": 60, "REF": 120}


def synth_panels(start: str, end: str, n: int = 10, seed: int = 0) -> dict:
    """Panel synthétique minimal (cours, volumes, TR par titre, Composite TR, numéros de séance)."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(start, end)
    syms = [f"X{i:02d}" for i in range(n)]
    r = rng.normal(0.0004, 0.012, (len(dates), n))
    close = pd.DataFrame(1000.0 * np.cumprod(1.0 + r, axis=0), dates, syms).round(0)
    vol = pd.DataFrame(rng.integers(3000, 9000, (len(dates), n)).astype(float), dates, syms)
    tr = close / close.iloc[0] * 100.0
    mtr = (100.0 * (1.0 + close.pct_change().mean(axis=1).fillna(0.0)).cumprod()).rename("TR")
    sess = pd.DataFrame(np.tile(np.arange(1, len(dates) + 1)[:, None], (1, n)), dates, syms)
    return {"close": close, "volume": vol, "value": close * vol, "tr_index": tr, "market_tr": mtr,
            "session_no": sess}


class StubModel:
    """Bouchon du contrat ``BrvmAlpha`` : momentum simple, une taille et une fenêtre par variante."""

    def __init__(self, spec: RunSpec, config, sample: str) -> None:
        self.spec = spec
        self.k = _K[spec.variant]
        self.lb = _LB[spec.variant]
        self.last_decision = None
        self.country_events = None

    def strategy_fn(self):
        def fn(t, view):
            c = view["close"]
            if len(c) <= self.lb:
                return None
            mom = c.iloc[-1] / c.iloc[-self.lb] - 1.0
            top = mom.nlargest(self.k).index
            self.last_decision = types.SimpleNamespace(
                asof=pd.Timestamp(t), universe=pd.DataFrame({"eligible": pd.Series(True, index=c.columns)}),
                signals={"composite": mom}, diagnostics={"mode": "selection"})
            return pd.Series(0.98 / self.k, index=top)

        return fn


class EventStubModel(StubModel):
    """Bouchon acceptant le mode événementiel : poids aux seules fins de mois, ``None`` sinon."""

    def strategy_fn(self, event_driven: bool = False, calendar=None):
        base = super().strategy_fn()
        if not event_driven:
            return base
        from brvm_alpha.backtest.engine import rebalance_dates

        ends = set(rebalance_dates(pd.DatetimeIndex(calendar), "M"))

        def fn(t, view):
            return base(t, view) if pd.Timestamp(t) in ends else None

        return fn


def event_factory(spec, config, sample):
    return EventStubModel(spec, config, sample)


def stub_factory(spec, config, sample):
    # Mode de décision par défaut « evenementiel » (pré-vol du 22/11/2026) : le bouchon l'accepte.
    return EventStubModel(spec, config, sample)


def monthly_only_factory(spec, config, sample):
    """Bouchon sans mode événementiel (``strategy_fn()`` seul) : repli vers le mode mensuel."""
    return StubModel(spec, config, sample)


def failing_factory(spec, config, sample):
    if spec.variant == "H":
        raise RuntimeError("bogue simulé dans la variante H")
    return EventStubModel(spec, config, sample)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), "-c", "user.email=test@example.invalid", "-c", "user.name=test",
                    *args], check=True, capture_output=True)


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """Dépôt git jetable avec des fichiers suivis sous brvm_alpha/ et configs/."""
    root = tmp_path / "depot"
    (root / "brvm_alpha").mkdir(parents=True)
    (root / "configs").mkdir()
    (root / "brvm_alpha" / "module.py").write_text("X = 1\n", encoding="utf-8")
    (root / "configs" / "strategie.yaml").write_text("version: '1.1'\n", encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")
    return root


@pytest.fixture(scope="module")
def s1_synth() -> dict:
    """Panel synthétique daté dans la fenêtre S1 (court : 15 mois, aucune donnée réelle)."""
    return synth_panels("2017-01-02", "2018-03-30", n=10, seed=1)


# ---------------------------------------------------------------------------
# Plan des runs
# ---------------------------------------------------------------------------


def test_run_plan_matches_addendum():
    plan = run_plan()
    ids = [s.run_id for s in plan]
    assert len(plan) == 30 and len(set(ids)) == 30
    for v in (*FAMILY_V11, "REF"):
        assert f"{v}_central_10M" in ids and f"{v}_stress_10M" in ids
    assert {s.run_id for s in plan if s.costs in ("optimistic", "severe")} == {
        "A_optimistic_10M", "A_severe_10M", "I_optimistic_10M", "I_severe_10M"}
    assert {s.run_id for s in plan if s.capital != 1e7} == {
        "A_central_100M", "A_central_1Md", "I_central_100M", "I_central_1Md", "REF_central_100M", "REF_central_1Md"}
    trials = [s for s in plan if s.is_trial]
    assert len(trials) == 10 and all(s.costs == "central" and s.capital == 1e7 for s in trials)
    assert [s.variant for s in plan if s.in_family] == list(FAMILY_V11)  # REF hors famille de la PBO
    assert RunSpec("REF").role.startswith("essai (référence") and RunSpec("A", "stress").role == "sensibilité"


# ---------------------------------------------------------------------------
# D6 : montant corrigé crédité, écart publié avec la ligne (d)
# ---------------------------------------------------------------------------


def test_engine_credits_corrected_dividend_and_publishes_gap():
    dates = pd.bdate_range("2030-01-01", periods=40)
    close = pd.DataFrame({"X": 1000.0, "Y": 1000.0}, index=dates)
    vol = pd.DataFrame(1e6, index=dates, columns=close.columns)
    div = pd.DataFrame(0.0, index=dates, columns=close.columns)
    boc = div.copy()
    div.loc[dates[20], "X"] = 30.0  # montant corrigé (meilleure estimation du versement)
    boc.loc[dates[20], "X"] = 27.0  # ligne (d) du BOC, vue par les signaux
    div.loc[dates[25], "Y"] = 10.0
    boc.loc[dates[25], "Y"] = 10.0
    zero = CostModel(sgi_commission=0.0, brvm_fee=0.0, dcbr_fee=0.0, impact_coef=0.0, annual_custody=0.0,
                     half_spread_mult=0.0, account_fee_per_line_fcfa=0.0)
    panels = {"close": close, "volume": vol, "value": close * vol, "dividend_net": div, "dividend_net_boc": boc}
    res = Backtester(panels, zero, capital=1e6).run(lambda t, v: pd.Series({"X": 0.45, "Y": 0.45}),
                                                     rebalance=[dates[2]])
    qx, qy = float(res.positions.iloc[-1]["X"]), float(res.positions.iloc[-1]["Y"])
    assert res.dividends.sum() == pytest.approx(30.0 * qx + 10.0 * qy)  # flux = montant corrigé
    assert res.dividends_boc.sum() == pytest.approx(27.0 * qx + 10.0 * qy)
    assert res.meta["dividend_gap_vs_boc"] == pytest.approx(3.0 * qx)
    assert res.meta["dividend_boc_line_available"] is True
    ev = res.dividend_events
    assert list(ev["symbol"]) == ["X", "Y"] and ev["gap"].tolist() == pytest.approx([3.0 * qx, 0.0])
    s = res.summary()
    assert s["dividend_gap_vs_boc"] == pytest.approx(3.0 * qx)
    # sans panel (d) : écart nul, montant crédité inchangé
    res0 = Backtester({k: v for k, v in panels.items() if k != "dividend_net_boc"}, zero, capital=1e6).run(
        lambda t, v: pd.Series({"X": 0.45, "Y": 0.45}), rebalance=[dates[2]])
    assert res0.dividends.sum() == pytest.approx(res.dividends.sum()) and res0.meta["dividend_gap_vs_boc"] == 0.0


def test_panels_from_equities_keeps_boc_line_amount():
    from brvm_alpha.backtest.engine import panels_from_equities

    dates = pd.bdate_range("2030-03-01", periods=10)
    eq = pd.DataFrame([{"date": d, "symbol": s, "close": 100.0, "volume": 10.0, "value": 1000.0}
                       for d in dates for s in ("X", "Y")])
    divs = pd.DataFrame({"symbol": ["X"], "ex_date": [dates[4]], "amount": [5.0], "amount_first": [4.5],
                         "payment_date": [dates[6]]})
    p = panels_from_equities(eq, close=eq.pivot(index="date", columns="symbol", values="close"), dividends=divs)
    assert p["dividend_net"].loc[dates[4], "X"] == 5.0 and p["dividend_net_boc"].loc[dates[4], "X"] == 4.5


# ---------------------------------------------------------------------------
# D2 : t0, rebasage, sous-périodes, exclusion de 2021
# ---------------------------------------------------------------------------


def test_t0_window_rebase_and_subperiods():
    days = pd.bdate_range("2030-01-01", periods=10)
    expo = pd.Series([0, 0, 0, 0.5, 0.98, 0.98, 0.98, 0.98, 0.98, 0.98], index=days, dtype=float)
    t0 = mt.first_investment_date(expo)
    assert t0 == days[3]
    level = pd.Series(np.linspace(100.0, 109.0, 10), index=days)
    rb = mt.rebase_at(level, t0)
    assert rb.iloc[:2].isna().all() and rb.loc[days[2]] == pytest.approx(100.0)  # base : veille de t0
    daily = level.pct_change()
    win = mt.evaluation_window(daily, t0)
    assert win.index[0] == t0  # le rendement de t0 (frais d'achat initiaux) est compté
    assert rb.iloc[-1] == pytest.approx(100.0 * float(np.prod(1.0 + win.to_numpy())))
    subs = mt.evaluation_subperiods("2017-07-03", mt.S1_SUBPERIODS, end="2022-11-18")
    assert subs == [(pd.Timestamp("2017-07-03"), pd.Timestamp("2019-12-31")),
                    (pd.Timestamp("2020-01-01"), pd.Timestamp("2022-11-18"))]
    assert mt.evaluation_subperiods("2020-03-02", mt.S1_SUBPERIODS) == [
        (pd.Timestamp("2020-03-02"), pd.Timestamp("2022-11-16"))]


def test_2021_window_excluded_by_default_in_weekly_returns_and_status():
    weeks = pd.date_range("2018-01-05", "2022-11-11", freq="W-FRI")
    rng = np.random.default_rng(3)
    b = pd.Series(rng.normal(0.001, 0.01, len(weeks)), index=weeks)
    a = pd.Series(rng.normal(0.0005, 0.004, len(weeks)), index=weeks)
    inside = (weeks >= "2021-05-07") & (weeks <= "2021-06-25")
    a[inside] = 0.5  # valeurs aberrantes dans la fenêtre exclue : ne doivent rien changer
    rep = evaluate_status(a, a, b, n_boot=100, turnover=0.1, pbo=0.2, cvar_ratio=1.0)
    clean = evaluate_status(a[~inside], a[~inside], b, n_boot=100, turnover=0.1, pbo=0.2, cvar_ratio=1.0)
    assert rep.mesures["n_semaines"] == clean.mesures["n_semaines"] == int((~inside).sum())
    assert rep.mesures["ir"] == pytest.approx(clean.mesures["ir"])
    assert any("06/05 → 25/06/2021" in x for x in rep.avertissements)
    days = pd.bdate_range("2021-04-26", "2021-07-09")
    w = mt.weekly_returns(pd.Series(0.001, index=days))
    assert not ((w.index >= "2021-05-07") & (w.index <= "2021-06-25")).any()


def test_coverage_explicit_expected_weeks_are_honoured():
    """``expected_weeks`` explicites priment sur ``expected_period``. Depuis la correction du 22/11/2026,
    l'exécuteur ne les dérive plus des semaines du TR (mêmes retraits : couverture de 100 % par
    construction) ; les semaines multi-séances sont gardées pour le chaînage (``dispersion_exclude``) et
    la couverture se mesure sur le calendrier W-FRI (tests/test_fix_all_s1.py)."""
    weeks = pd.date_range("2030-01-04", periods=290, freq="W-FRI")
    rng = np.random.default_rng(8)
    b = pd.Series(rng.normal(0.001, 0.01, 290), index=weeks)
    a = pd.Series(rng.normal(0.003, 0.004, 290), index=weeks)
    gap = weeks[100:116]  # 16 semaines retirées par la règle des séances (≈ 5,5 % de l'échantillon)
    a, b = a.drop(gap), b.drop(gap)
    subs = [(weeks[0], weeks[144]), (weeks[145], weeks[-1])]
    kw = {"turnover": 0.1, "pbo": 0.1, "cvar_ratio": 1.0, "n_boot": 100}
    naive = evaluate_status(a, a, b, subs, expected_period=(weeks[0], weeks[-1]), **kw)
    assert naive.mesures["couverture"] < 0.95 and naive.statut == STATUT_INDETERMINE
    ok = evaluate_status(a, a, b, subs, expected_period=(weeks[0], weeks[-1]), expected_weeks=b.index, **kw)
    assert ok.mesures["couverture"] == pytest.approx(1.0) and ok.statut == "CANDIDAT"


def test_short_sample_is_indetermine():
    weeks = pd.date_range("2030-01-04", periods=40, freq="W-FRI")
    rng = np.random.default_rng(4)
    a = pd.Series(rng.normal(0.004, 0.002, 40), index=weeks)  # actif très favorable mais 40 semaines
    b = pd.Series(rng.normal(0.001, 0.01, 40), index=weeks)
    subs = mt.evaluation_subperiods(weeks[0], [(weeks[0], weeks[19]), (weeks[20], weeks[-1])])
    rep = evaluate_status(a, a, b, subs, turnover=0.1, pbo=0.1, cvar_ratio=1.0, n_boot=100)
    assert rep.statut == STATUT_INDETERMINE and any("trop court" in x for x in rep.avertissements)
    assert rep.criteres["verifie"].isna().all()  # ni rejet, ni candidature (D7 : données insuffisantes)
    bad = evaluate_status(-a, -a, b, subs, turnover=0.1, pbo=0.1, cvar_ratio=1.0, n_boot=100)
    assert bad.statut == STATUT_INDETERMINE and bad.mesures["actif_net_central_an"] < 0  # mesure publiée


# ---------------------------------------------------------------------------
# PBO / DSR sur une famille synthétique de 9 variantes ; règle de promotion ; D7
# ---------------------------------------------------------------------------


def test_pbo_dsr_and_promotion_on_synthetic_family():
    rng = np.random.default_rng(11)
    idx = pd.date_range("2030-01-04", periods=290, freq="W-FRI")
    fam = pd.DataFrame({v: rng.normal(0.0003, 0.01, len(idx)) for v in FAMILY_V11}, index=idx)
    pb = mt.family_pbo(fam, n_splits=10)
    assert 0.0 <= pb["pbo"] <= 1.0 and "degradation_slope" in pb
    srs = fam.mean() / fam.std(ddof=1)
    var = float(np.var(srs, ddof=1))
    d9, d78 = mt.dsr(fam["A"], 9, var), mt.dsr(fam["A"], 78, var)
    assert 0.0 <= d78 < d9 <= 1.0  # plus d'essais : seuil SR0 plus haut, DSR plus bas
    fam["I"] = fam["A"] + 0.006 + rng.normal(0.0, 0.002, len(idx))  # nettement meilleure que A
    rep = variant_promotion(fam, pbo=0.10)
    assert rep.n_trials == 9  # N = taille de la famille de l'additif v1.1
    assert rep.criteres.loc["I", "bat_reference"] is True and rep.principal == "I"
    assert variant_promotion(fam, pbo=0.30).principal == "A"  # PBO > 0,25 : A reste le principal
    # famille de bruit pur : la PBO d'une famille sans signal est élevée en moyenne
    noise = pd.DataFrame({v: rng.normal(0.0, 0.01, len(idx)) for v in FAMILY_V11}, index=idx)
    assert mt.family_pbo(noise, n_splits=10)["pbo"] > 0.2


def test_d7_g7_on_s1_then_s2_ic():
    rng = np.random.default_rng(7)
    weeks = pd.date_range("2030-01-04", periods=312, freq="W-FRI")
    subs = [(weeks[0], weeks[155]), (weeks[156], weeks[-1])]
    b = pd.Series(rng.normal(0.002, 0.015, 312), index=weeks)
    a = pd.Series(rng.normal(0.004, 0.006, 312), index=weeks)
    ic_s1 = pd.Series(0.05 + 0.01 * np.sin(np.arange(30)), index=pd.date_range("2030-01-31", periods=30, freq="ME"))
    s2 = pd.Series(rng.normal(0.004, 0.006, 60), index=pd.date_range("2036-01-04", periods=60, freq="W-FRI"))
    ic_s2 = pd.Series(0.05 + 0.01 * np.cos(np.arange(10)), index=pd.date_range("2036-01-31", periods=10, freq="ME"))
    kw = {"turnover": 0.1, "pbo": 0.1, "pbo_slope": 0.1, "cvar_ratio": 1.0, "n_trials": 68, "sr_variance": 1e-4,
          "registry_complete": True, "ic_monthly": ic_s1, "n_boot": 100, "s2_active_weekly_returns": s2,
          "s2_ic_monthly": ic_s2, "s2_pbo": 0.1, "s2_pbo_slope": 0.1}
    rep = evaluate_status(a, a, b, subs, **kw)
    assert rep.critere("promotion_S1", "G7")["verifie"] is False  # 30 mois de S1 < 36
    assert rep.mesures["promotion_S2_ic_mois"] == 40 and rep.mesures["promotion_S2_ic_mois_s2_seul"] == 10
    assert rep.critere("promotion_S2", "G7")["verifie"] is True  # S1 puis S2 bout à bout : 40 mois
    v10 = evaluate_status(a, a, b, subs, rules="v1.0", **kw)
    assert v10.critere("promotion_S2", "G7")["verifie"] is False  # v1.0 : 10 mois de S2 seul
    no_s2_ic = evaluate_status(a, a, b, subs, **{**kw, "s2_ic_monthly": None})
    assert no_s2_ic.critere("promotion_S2", "G7")["verifie"] is None and no_s2_ic.statut != "PROMU"
    with pytest.raises(ValueError):
        evaluate_status(a, a, b, subs, rules="v2", **kw)


def test_monthly_ic_never_reads_beyond_sample_end():
    dates = pd.bdate_range("2030-01-01", periods=120)
    rng = np.random.default_rng(5)
    tr = pd.DataFrame(100.0 * np.cumprod(1.0 + rng.normal(0, 0.01, (120, 20)), axis=0), dates,
                      [f"S{i}" for i in range(20)])
    fwd = tr.shift(-22) / tr.shift(-1) - 1.0
    me = [dates[19], dates[40], dates[61], dates[90]]
    scores = {t: fwd.loc[t] for t in me}  # score parfait (contrôle de la formule)
    ic = mt.monthly_ic(scores, tr, end=dates[85])
    assert list(ic.index) == me[:3]  # la fenêtre de la 4e date dépasse la fin : omise
    assert ic.to_numpy() == pytest.approx(1.0)
    assert math.isnan(mt.monthly_ic(scores, tr, min_names=25).iloc[0])


# ---------------------------------------------------------------------------
# Registre : essais de l'additif v1.1 et relance motivée
# ---------------------------------------------------------------------------


def test_registry_addendum_v11_and_motivated_rerun(tmp_path):
    reg = TrialRegistry.initialize(tmp_path / "trials.parquet", addendum_v11=True)
    f = reg.frame
    assert reg.n_trials() >= N_TRIALS_START_V11 + 2  # 55 + 9 + 1 + au moins 2 essais de fumée de A
    for tid in ("S1-I", REFERENCE_TRIAL_ID):
        assert f.loc[f["id"] == tid, "statut"].iloc[0] == STATUT_PREENREGISTRE
    diag = f[f["famille"] == "S0 diagnostic (mise au point)"]
    assert len(diag[diag["id"].str.startswith("S0-DIAG-A-")]) >= 2 and (diag["statut"] == STATUT_DECLARE).all()
    assert TrialRegistry.initialize(tmp_path / "trials.parquet", addendum_v11=True).n_trials() == reg.n_trials()
    weeks = pd.date_range("2030-01-04", periods=60, freq="W-FRI")
    w = pd.Series(np.random.default_rng(0).normal(0.001, 0.01, 60), index=weeks)
    p_a = json.loads(f.loc[f["id"] == "S1-A", "parametres"].iloc[0])
    assert reg.record("A", p_a, "S1", w) == "S1-A"
    n = reg.n_trials()
    with pytest.raises(RuntimeError, match="UN test"):
        reg.record("A", p_a, "S1", w)
    with pytest.raises(ValueError, match="FIGÉS"):
        reg.record("A", {**p_a, "frequence": "hebdomadaire"}, "S1", w, rerun_reason="bogue de comptabilité")
    tid = reg.record("A", p_a, "S1", w, rerun_reason="bogue de comptabilité démontré")
    assert tid == "S1-A-R1" and reg.n_trials() == n + 1
    row = reg.frame[reg.frame["id"] == tid].iloc[0]
    assert row["statut"] == STATUT_EXECUTE and "bogue de comptabilité" in row["note"]
    p_ref = json.loads(f.loc[f["id"] == REFERENCE_TRIAL_ID, "parametres"].iloc[0])
    assert reg.record("REF", p_ref, "S1", w) == REFERENCE_TRIAL_ID
    reg.set_metrics("S1-A", {"statut": "INDÉTERMINÉ"})
    assert json.loads(reg.frame.loc[reg.frame["id"] == "S1-A", "metriques"].iloc[0]) == {"statut": "INDÉTERMINÉ"}


# ---------------------------------------------------------------------------
# Verrou et exécuteur sur panel synthétique
# ---------------------------------------------------------------------------


def test_git_tree_state_and_dirty_tree_refused(repo):
    st = lk.git_tree_state(repo)
    assert st["propre"] and st["commit"] and st["non_suivis"] == []
    (repo / "brvm_alpha" / "nouveau.py").write_text("Y = 2\n", encoding="utf-8")
    st = lk.git_tree_state(repo)
    # Pré-vol du 22/11/2026 : un fichier non suivi sous brvm_alpha/ serait importé sans figurer dans le
    # commit enregistré : l'arbre n'est plus « propre » et S1 est refusé (fichiers suivis inchangés).
    assert st["propre_suivis"] and not st["propre"] and st["non_suivis"] == ["brvm_alpha/nouveau.py"]
    with pytest.raises(ValidationRefused, match="non suivis"):
        lk.require_clean_tree(st)
    (repo / "brvm_alpha" / "nouveau.py").unlink()
    assert lk.git_tree_state(repo)["propre"]
    (repo / "configs" / "strategie.yaml").write_text("version: '1.2'\n", encoding="utf-8")
    st = lk.git_tree_state(repo)
    assert not st["propre"] and st["modifies"] == ["configs/strategie.yaml"]
    with pytest.raises(ValidationRefused, match="diffèrent de HEAD"):
        lk.require_clean_tree(st)


def test_runner_s1_lock_refuses_dirty_tree(repo, s1_synth, tmp_path):
    (repo / "brvm_alpha" / "module.py").write_text("X = 2\n", encoding="utf-8")
    out = tmp_path / "validation_S1"
    with pytest.raises(ValidationRefused):
        run_validation("S1", out_dir=out, panels=s1_synth, model_factory=stub_factory,
                       registry_path=tmp_path / "trials.parquet", repo_root=repo, workers=1, n_boot=100)
    assert not (out / "lock.json").exists() and not (tmp_path / "trials.parquet").exists()


def test_runner_s1_single_test_then_refusal_then_motivated_rerun(repo, s1_synth, tmp_path):
    out = tmp_path / "validation_S1"
    reg_path = tmp_path / "trials.parquet"
    kw = {"panels": s1_synth, "model_factory": stub_factory, "registry_path": reg_path, "repo_root": repo,
          "workers": 1, "n_boot": 100}
    res = run_validation("S1", out_dir=out, **kw)
    for name in ("resultats.md", "metrics.json", "weekly_returns.parquet", "nav.parquet", "trades.parquet",
                 "lock.json"):
        assert (out / name).exists(), name
    lock = json.loads((out / "lock.json").read_text(encoding="utf-8"))
    assert lock["statut"] == "terminé" and lock["commit"] == lk.git_tree_state(repo)["commit"]
    assert lock["empreinte_config"] and lock["version_yaml"] and lock["horodatage_utc"]
    assert len(lock["plan"]) == 30 and lock["plan_standard"] is True and lock["n_boot"] == 100
    assert set(lock["essais"].values()) == {f"S1-{v}" for v in FAMILY_V11} | {REFERENCE_TRIAL_ID}
    # D2 : t0 = première séance investie de A ; échantillon court : INDÉTERMINÉ partout
    m = res.metrics
    t0 = pd.Timestamp(m["t0"])
    assert t0 > pd.Timestamp("2017-03-01") and set(res.statuses.values()) == {STATUT_INDETERMINE}
    assert any("trop court" in x for x in m["variantes"]["A"]["avertissements"])
    wk = pd.read_parquet(out / "weekly_returns.parquet")
    assert wk.index.min() >= t0 and {"A_central_10M", "ETALON_TR", "ETALON_EW"} <= set(wk.columns)
    nav = pd.read_parquet(out / "nav.parquet")
    tr = nav[nav["serie"] == "ETALON_TR"].set_index("date")["base_t0"].dropna()
    assert tr.iloc[0] == pytest.approx(100.0) and tr.index[0] < t0  # base 100 la veille de t0
    reg = TrialRegistry.load(reg_path)
    assert len(reg.executed("S1")) == 10
    n_after_first = reg.n_trials()
    text = (out / "resultats.md").read_text(encoding="utf-8")
    assert "Performance passée ≠ garantie. Aucun gain n'est garanti." in text and "Prédiction" in text
    assert "t0 =" in text and "PROMU est impossible" in text
    # seconde exécution : refusée
    with pytest.raises(ValidationRefused, match="rerun-reason"):
        run_validation("S1", out_dir=out, **kw)
    assert TrialRegistry.load(reg_path).n_trials() == n_after_first
    # relance motivée : nouveaux essais, anciens résultats conservés et publiés
    res2 = run_validation("S1", out_dir=out, rerun_reason="bogue de comptabilité démontré (test)", **kw)
    prev = [d for d in out.iterdir() if d.name.startswith("precedent_")]
    assert len(prev) == 1 and (prev[0] / "metrics.json").exists() and (prev[0] / "lock.json").exists()
    assert set(res2.trial_ids.values()) == {f"S1-{v}-R1" for v in FAMILY_V11} | {f"{REFERENCE_TRIAL_ID}-R1"}
    reg2 = TrialRegistry.load(reg_path)
    assert reg2.n_trials() == n_after_first + 10 and len(reg2.executed("S1")) == 20
    lock2 = json.loads((out / "lock.json").read_text(encoding="utf-8"))
    assert lock2["relance"]["motif"].startswith("bogue de comptabilité")
    assert lock2["relance"]["verrou_precedent"]["statut"] == "terminé"
    text2 = (out / "resultats.md").read_text(encoding="utf-8")
    assert "Résultats de l'exécution précédente" in text2 and "Relance motivée" in text2


def test_runner_s1_failure_publishes_nothing(repo, s1_synth, tmp_path):
    out = tmp_path / "validation_S1"
    reg_path = tmp_path / "trials.parquet"
    plan = [RunSpec("A"), RunSpec("H")]
    with pytest.raises(ValidationRefused, match="non conforme"):
        run_validation("S1", out_dir=out, panels=s1_synth, model_factory=stub_factory, registry_path=reg_path,
                       repo_root=repo, plan=plan, workers=1, n_boot=100)
    with pytest.raises(ValidationFailed, match="aucune métrique"):
        run_validation("S1", out_dir=out, panels=s1_synth, model_factory=failing_factory, registry_path=reg_path,
                       repo_root=repo, plan=plan, allow_nonstandard_plan=True, workers=1, n_boot=100)
    lock = json.loads((out / "lock.json").read_text(encoding="utf-8"))
    assert lock["statut"] == "échec" and lock["erreurs"][0]["run_id"] == "H_central_10M"
    assert not (out / "metrics.json").exists() and not (out / "resultats.md").exists()
    assert not reg_path.exists()  # aucun essai marqué « exécuté »
    with pytest.raises(ValidationRefused, match="verrou existant"):  # tentative inachevée : motif exigé
        run_validation("S1", out_dir=out, panels=s1_synth, model_factory=stub_factory, registry_path=reg_path,
                       repo_root=repo, plan=plan, allow_nonstandard_plan=True, workers=1, n_boot=100)


def test_real_s1_requires_explicit_5000_bootstrap(tmp_path):
    """Sur le panel réel (fabrique par défaut), S1 refuse un bootstrap autre que 5 000 répliques, avant tout calcul."""
    out = tmp_path / "validation_S1"
    with pytest.raises(ValidationRefused, match="n_boot = 5000"):
        run_validation("S1", out_dir=out, registry_path=tmp_path / "trials.parquet", n_boot=200)
    assert not out.exists() and not (tmp_path / "trials.parquet").exists()


def test_runner_s0_parallel_is_deterministic_and_marked_contaminated(tmp_path):
    panels = synth_panels("2022-06-01", "2023-08-31", n=10, seed=2)
    plan = [RunSpec("A"), RunSpec("A", "stress"), RunSpec("B"), RunSpec("REF")]
    kw = {"panels": panels, "model_factory": stub_factory, "plan": plan, "n_boot": 100, "repo_root": tmp_path}
    seq = run_validation("S0", out_dir=tmp_path / "seq", registry_path=tmp_path / "r1.parquet", workers=1, **kw)
    par = run_validation("S0", out_dir=tmp_path / "par", registry_path=tmp_path / "r2.parquet", workers=2, **kw)
    pd.testing.assert_frame_equal(pd.read_parquet(tmp_path / "seq" / "weekly_returns.parquet"),
                                  pd.read_parquet(tmp_path / "par" / "weekly_returns.parquet"))
    pd.testing.assert_frame_equal(pd.read_parquet(tmp_path / "seq" / "trades.parquet"),
                                  pd.read_parquet(tmp_path / "par" / "trades.parquet"))
    assert seq.statuses == par.statuses
    for k in ("rendement_an", "actif_tr_an", "ir_tr"):
        assert seq.metrics["runs"]["A_central_10M"][k] == pytest.approx(par.metrics["runs"]["A_central_10M"][k])
    assert par.metrics["execution"]["workers"] == 2 and set(par.metrics["execution"]["durees_runs_s"]) == {
        s.run_id for s in plan}
    # S0 : pas de verrou, mention « contaminé », échantillon court : INDÉTERMINÉ
    assert not (tmp_path / "seq" / "lock.json").exists() and (tmp_path / "seq" / "contexte.json").exists()
    assert "aucune valeur de preuve" in (tmp_path / "seq" / "resultats.md").read_text(encoding="utf-8")
    assert seq.statuses["A"] == STATUT_INDETERMINE
    reg = TrialRegistry.load(tmp_path / "r1.parquet")
    ex = reg.executed("S0")
    assert len(ex) == 3 and ex["id"].str.startswith("S0-DIAG-").all()  # A, B, REF (essais centraux à 10 M)


def test_runner_event_driven_mode_is_recorded_and_falls_back(tmp_path):
    panels = synth_panels("2022-06-01", "2023-08-31", n=8, seed=6)
    plan = [RunSpec("A"), RunSpec("B")]
    kw = {"panels": panels, "plan": plan, "n_boot": 100, "repo_root": tmp_path, "workers": 1}
    monthly = run_validation("S0", out_dir=tmp_path / "m", registry_path=tmp_path / "r0.parquet",
                             model_factory=event_factory, decision_mode="mensuel", **kw)
    # défaut (pré-vol du 22/11/2026) : mode événementiel, conforme au §6 « Fréquence » et à D10
    event = run_validation("S0", out_dir=tmp_path / "e", registry_path=tmp_path / "r1.parquet",
                           model_factory=event_factory, **kw)
    assert monthly.metrics["execution"]["modes_effectifs"] == ["mensuel"]
    assert event.metrics["execution"]["mode_decision"] == "evenementiel"
    assert event.metrics["execution"]["modes_effectifs"] == ["evenementiel"]
    # décisions aux seules fins de mois : mêmes transactions qu'en mode mensuel
    pd.testing.assert_frame_equal(pd.read_parquet(tmp_path / "m" / "trades.parquet"),
                                  pd.read_parquet(tmp_path / "e" / "trades.parquet"))
    fallback = run_validation("S0", out_dir=tmp_path / "f", registry_path=tmp_path / "r2.parquet",
                              model_factory=monthly_only_factory, decision_mode="evenementiel", **kw)
    assert fallback.metrics["execution"]["modes_effectifs"][0].startswith("mensuel (repli")
    with pytest.raises(ValueError):
        run_validation("S0", out_dir=tmp_path / "x", decision_mode="quotidien", **kw)


def test_runner_s1_refuses_silent_decision_mode_fallback(repo, s1_synth, tmp_path):
    # Sur S1, un run qui ne peut pas suivre le mode consigné dans le verrou est un échec (rien n'est publié).
    out = tmp_path / "validation_S1"
    plan = [RunSpec("A"), RunSpec("B")]
    with pytest.raises(ValidationFailed, match="mode de décision effectif"):
        run_validation("S1", out_dir=out, panels=s1_synth, model_factory=monthly_only_factory,
                       registry_path=tmp_path / "trials.parquet", repo_root=repo, plan=plan,
                       allow_nonstandard_plan=True, workers=1, n_boot=100)
    lock = json.loads((out / "lock.json").read_text(encoding="utf-8"))
    assert lock["statut"] == "échec" and lock["mode_decision"] == "evenementiel"
    assert not (out / "metrics.json").exists()


def test_cli_validate_maps_refusal_to_exit_code_2(monkeypatch, capsys):
    import brvm_alpha.validation as validation

    def refuse(*a, **k):
        raise ValidationRefused("test unique S1 déjà tenté")

    monkeypatch.setattr(validation, "run_validation", refuse)
    assert cli.main(["validate", "--sample", "S1"]) == 2
    assert "refusé" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        cli.main(["validate", "--sample", "S2"])
