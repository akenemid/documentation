"""Tests de régression des constats de l'audit du test S1 (agent fix:all, 22/11/2026).

Chaque test échoue avant la correction correspondante. Données **synthétiques** uniquement (graines
fixes, dates 2023-2025 et 2030+) : aucun backtest, aucune performance, aucun IC ni aucun signal n'est
évalué sur les données réelles de l'échantillon vierge S1. Aucune requête réseau.

Constats couverts :

* semaines « multi-séances » (trou de BOC) retirées du chaînage (rendement, actif, drawdowns) alors que
  le §3.1.3 les garde pour chaîner le TR ;
* garde-fou de couverture tautologique (semaines attendues = semaines du TR calculées avec les mêmes
  retraits) ;
* coûts annuels annualisés à 252 séances au lieu des années calendaires ; décomposition du coût par aller ;
* DSR « registre » publié sous une seule convention de variance ;
* PBO : sensibilité au découpage, convention λ = 0 (N impair), clone exact E = A ;
* IC « mensuels » de G7 : plusieurs décisions par mois en mode événementiel ;
* contrôle d'empreinte autoréférentiel ; empreinte du pré-enregistrement écrasée au registre.
"""

from __future__ import annotations

import json
import math
import types
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from brvm_alpha.backtest import metrics as mt
from brvm_alpha.backtest.walkforward import STATUT_INDETERMINE, TrialRegistry, evaluate_status, variant_promotion
from brvm_alpha.quant import stats
from brvm_alpha.validation import RunSpec, run_validation
from brvm_alpha.validation import lock as lk

# ---------------------------------------------------------------------------
# Panel synthétique avec un trou de BOC (numéros de séance qui sautent)
# ---------------------------------------------------------------------------

GAP = ("2024-01-08", "2024-01-26")  # 3 semaines sans BOC (15 séances)
JUMP_DAY = pd.Timestamp("2024-01-29")  # première séance après le trou : +20 % sur tous les titres


def gap_panels(seed: int = 3, n: int = 10) -> dict:
    rng = np.random.default_rng(seed)
    full = pd.bdate_range("2023-01-02", "2025-06-27")
    sess_all = pd.Series(np.arange(1, len(full) + 1), index=full)
    dates = full[(full < GAP[0]) | (full > GAP[1])]
    syms = [f"X{i:02d}" for i in range(n)]
    r = rng.normal(0.0003, 0.011, (len(dates), n))
    r[dates.get_loc(JUMP_DAY)] = 0.20
    close = pd.DataFrame(1000.0 * np.cumprod(1.0 + r, axis=0), dates, syms).round(0)
    vol = pd.DataFrame(rng.integers(3000, 9000, (len(dates), n)).astype(float), dates, syms)
    tr = close / close.iloc[0] * 100.0
    mtr = (100.0 * (1.0 + close.pct_change().mean(axis=1).fillna(0.0)).cumprod()).rename("TR")
    sess = pd.DataFrame(np.tile(sess_all.reindex(dates).to_numpy()[:, None], (1, n)), dates, syms)
    return {"close": close, "volume": vol, "value": close * vol, "tr_index": tr, "market_tr": mtr,
            "session_no": sess}


_K = {"A": 5, "B": 4, "E": 5, "REF": 9}
_LB = {"A": 60, "B": 40, "E": 60, "REF": 120}


class _Stub:
    """Bouchon du contrat ``BrvmAlpha`` : momentum simple ; E est un clone exact de A."""

    def __init__(self, spec, config, sample) -> None:
        self.k, self.lb = _K[spec.variant], _LB[spec.variant]
        self.last_decision = None
        self.country_events = None

    def strategy_fn(self, event_driven: bool = False, calendar=None):
        from brvm_alpha.backtest.engine import rebalance_dates

        ends = set(rebalance_dates(pd.DatetimeIndex(calendar), "M")) if event_driven else None

        def fn(t, view):
            if ends is not None and pd.Timestamp(t) not in ends:
                return None
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


def _factory(spec, config, sample):
    return _Stub(spec, config, sample)


@pytest.fixture(scope="module")
def gap_run(tmp_path_factory) -> tuple[Path, object]:
    tmp = tmp_path_factory.mktemp("fix_all_s1")
    plan = [RunSpec("A"), RunSpec("A", "stress"), RunSpec("B"), RunSpec("E"), RunSpec("REF")]
    res = run_validation("S0", out_dir=tmp / "out", panels=gap_panels(), model_factory=_factory, plan=plan,
                         registry_path=tmp / "trials.parquet", repo_root=tmp, workers=1, n_boot=100)
    return tmp / "out", res


# ---------------------------------------------------------------------------
# Constat majeur 1 : chaînage des semaines multi-séances
# ---------------------------------------------------------------------------


def test_runner_chains_multi_session_week_into_returns_and_drawdowns(gap_run):
    out, res = gap_run
    m = res.metrics
    multi = m["semaines_multi_seances"]
    assert multi == ["2024-02-02"]  # la semaine qui suit le trou couvre 19 séances
    assert m["semaines_exclues"] == []  # rien d'autre que la fenêtre du §8.1 (hors période ici)
    wk = pd.read_parquet(out / "weekly_returns.parquet")
    assert pd.Timestamp("2024-02-02") in wk.index and bool(wk.loc["2024-02-02", "SEMAINE_MULTI_SEANCES"])
    assert wk.loc["2024-02-02", "ETALON_TR"] > 0.15  # le saut de +20 % est chaîné
    # Rendement annualisé du TR = croissance du niveau rebasé à t0 (aucune semaine perdue)
    nav = pd.read_parquet(out / "nav.parquet")
    tr = nav[nav["serie"] == "ETALON_TR"].set_index("date")["base_t0"]
    t0, end = pd.Timestamp(m["t0"]), pd.Timestamp(m["fin"])
    growth = float(tr.loc[:end].iloc[-1]) / 100.0
    b = m["etalons"]["TR"]["mesures"]
    assert (1.0 + b["rendement_an"]) ** (b["n_semaines"] / 52.0) == pytest.approx(growth, rel=1e-9)
    # même chose pour la stratégie A : l'actif chaîné contient la semaine multi-séances
    ra = m["runs"]["A_central_10M"]
    w_a = wk["A_central_10M"].dropna()
    assert ra["n_semaines"] == len(w_a) and ra["n_semaines_dispersion"] == len(w_a) - 1
    assert ra["rendement_an"] == pytest.approx(mt.annualized_return(w_a))
    # dispersion : sans la semaine multi-séances
    w_tr = wk["ETALON_TR"].dropna()
    a_disp = (w_a - w_tr).drop(pd.Timestamp("2024-02-02"))
    assert ra["ir_tr"] == pytest.approx(mt.information_ratio(a_disp))
    assert ra["drawdown_relatif_tr"] == pytest.approx(mt.relative_drawdown(w_a, w_tr.reindex(w_a.index)))
    assert t0 <= pd.Timestamp("2024-02-02") <= end


def test_evaluate_status_chained_criteria_keep_multi_session_weeks_dispersion_does_not():
    weeks = pd.date_range("2030-01-04", periods=300, freq="W-FRI")
    rng = np.random.default_rng(11)
    b = pd.Series(rng.normal(0.001, 0.01, 300), index=weeks)
    a = pd.Series(rng.normal(0.0002, 0.003, 300), index=weeks)
    gap_week = weeks[150]
    b.iloc[150] = 0.30  # trou de BOC : le TR gagne 30 % sur l'observation multi-séances
    a.iloc[150] = -0.30  # la stratégie en liquidités : actif −30 % sur cette semaine
    subs = [(weeks[0], weeks[149]), (weeks[150], weeks[-1])]
    kw = {"turnover": 0.1, "pbo": 0.1, "cvar_ratio": 1.0, "n_boot": 100, "expected_period": (weeks[0], weeks[-1])}
    rep = evaluate_status(a, a, b, subs, dispersion_exclude=[gap_week], **kw)
    clean = a.drop(gap_week)
    # chaîné : identique au calcul sur toutes les semaines
    assert rep.mesures["actif_net_central_an"] == pytest.approx(mt.annualized_active_return(a + b, b))
    assert rep.mesures["drawdown_relatif"] == pytest.approx(mt.relative_drawdown(a + b, b))
    assert rep.mesures["drawdown_relatif"] < -0.2  # 1 / 1,30 − 1 ≈ −23 % sur la seule semaine multi-séances
    # dispersion : sans la semaine multi-séances
    assert rep.mesures["ir"] == pytest.approx(mt.information_ratio(clean))
    assert rep.mesures["n_semaines"] == 300 and rep.mesures["n_semaines_dispersion"] == 299
    assert rep.mesures["couverture"] == pytest.approx(1.0)
    assert rep.mesures["couverture_dispersion"] == pytest.approx(299 / 300)
    assert rep.critere("rejet", "R4")["verifie"] is True  # drawdown relatif chaîné < −20 %


def test_variant_promotion_active_is_chained_dsr_is_dispersion():
    weeks = pd.date_range("2030-01-04", periods=260, freq="W-FRI")
    rng = np.random.default_rng(12)
    b = pd.Series(rng.normal(0.001, 0.01, 260), index=weeks)
    fam = pd.DataFrame({v: rng.normal(0.0, 0.003, 260) for v in "AB"}, index=weeks)
    fam.loc[weeks[100], "B"] = 0.25  # gain de B sur une semaine multi-séances
    pr = variant_promotion(fam, benchmark=b, pbo=0.1, n_trials=2, dispersion_exclude=[weeks[100]])
    act_b = pr.criteres.loc["B", "actif_net_an"]
    assert act_b == pytest.approx(mt.annualized_active_return(fam["B"] + b, b))  # chaîné
    d_b = mt.dsr(fam["B"].drop(weeks[100]), 2, pr.sr_variance)
    assert pr.criteres.loc["B", "dsr"] == pytest.approx(d_b)  # dispersion


# ---------------------------------------------------------------------------
# Constat majeur 2 : couverture mesurée sur le calendrier W-FRI (plus d'autoréférence)
# ---------------------------------------------------------------------------


def test_runner_coverage_is_measured_on_w_fri_calendar_not_on_tr_weeks(gap_run):
    _, res = gap_run
    ms = res.metrics["variantes"]["A"]["mesures_statut"]
    t0 = pd.Timestamp(res.metrics["t0"])
    end = pd.Timestamp(res.metrics["fin"])
    last_week = pd.Timestamp(pd.Period(end, freq="W-FRI").end_time.normalize())
    expected = pd.date_range(t0, last_week, freq="W-FRI")
    assert ms["semaines_attendues"] == len(expected)
    # trois semaines sans aucun BOC : comptées comme manquantes (avant : 100 % par construction)
    assert ms["couverture"] == pytest.approx(ms["n_semaines"] / len(expected))
    assert ms["couverture"] < 1.0 and ms["n_semaines"] == len(expected) - 3
    assert ms["couverture_dispersion"] == pytest.approx((ms["n_semaines"] - 1) / len(expected))


def test_coverage_never_uses_series_with_same_drops_as_expected_weeks():
    """Avant la correction, le runner passait ``expected_weeks`` = semaines du TR (mêmes retraits) : la
    couverture valait 100 % même avec 5,5 % de semaines retirées. Calendrier W-FRI : 94,5 % < 95 %."""
    weeks = pd.date_range("2030-01-04", periods=290, freq="W-FRI")
    rng = np.random.default_rng(8)
    b = pd.Series(rng.normal(0.001, 0.01, 290), index=weeks)
    a = pd.Series(rng.normal(0.003, 0.004, 290), index=weeks)
    gap = weeks[100:116]
    subs = [(weeks[0], weeks[144]), (weeks[145], weeks[-1])]
    kw = {"turnover": 0.1, "pbo": 0.1, "cvar_ratio": 1.0, "n_boot": 100}
    dropped = evaluate_status(a.drop(gap), a.drop(gap), b.drop(gap), subs, expected_period=(weeks[0], weeks[-1]), **kw)
    assert dropped.mesures["couverture"] < 0.95 and dropped.statut == STATUT_INDETERMINE
    # Les semaines gardées pour le chaînage (multi-séances) ne manquent pas : couverture complète.
    kept = evaluate_status(a, a, b, subs, expected_period=(weeks[0], weeks[-1]), dispersion_exclude=gap, **kw)
    assert kept.mesures["couverture"] == pytest.approx(1.0) and kept.statut == "CANDIDAT"
    assert kept.mesures["couverture_dispersion"] == pytest.approx(274 / 290)


# ---------------------------------------------------------------------------
# Coûts : annualisation calendaire et décomposition pondérée
# ---------------------------------------------------------------------------


def test_costs_annualized_by_calendar_years_and_decomposition_sums(gap_run):
    out, res = gap_run
    r = res.metrics["runs"]["A_central_10M"]
    nav = pd.read_parquet(out / "nav.parquet")
    eq = nav[nav["serie"] == "A_central_10M"].set_index("date")["valeur"]
    t0, end = pd.Timestamp(res.metrics["t0"]), pd.Timestamp(res.metrics["fin"])
    eq = eq[(eq.index >= t0) & (eq.index <= end)]
    years = ((eq.index[-1] - eq.index[0]).days + 1) / 365.25
    assert r["couts_an_pct_nav_moyenne"] == pytest.approx(r["couts_payes_fcfa"] / eq.mean() / years)
    assert r["couts_an_pct_nav_moyenne_252_seances"] == pytest.approx(r["couts_payes_fcfa"] / eq.mean() * 252 / len(eq))
    assert r["seances_observees_par_an"] == pytest.approx(len(eq) / years)  # S1 : environ 228 (BOC manquants)
    dc = r["cout_aller_decomposition_ponderee"]
    assert dc["frais"] + dc["demi_spread"] + dc["impact"] == pytest.approx(dc["total"], rel=1e-9)
    text = (out / "resultats.md").read_text(encoding="utf-8")
    assert "Décomposition **pondérée** du coût par aller" in text


# ---------------------------------------------------------------------------
# DSR sous deux conventions ; PBO : sensibilité, λ = 0, clone exact
# ---------------------------------------------------------------------------


def test_dsr_published_under_both_variance_conventions(gap_run):
    _, res = gap_run
    fam = res.metrics["famille"]
    a = res.metrics["variantes"]["A"]
    assert math.isfinite(fam["variance_sharpe_hebdo"]) and math.isfinite(fam["variance_sharpe_registre"])
    assert "dsr_registre_variance_registre" in a and "note_dsr" in fam


def test_pbo_null_reference_and_tie_convention():
    assert mt.pbo_null_reference(9) == pytest.approx(5 / 9)
    assert mt.pbo_null_reference(10) == pytest.approx(0.5)
    assert mt.pbo_null_reference(9, "half") == 0.5
    rng = np.random.default_rng(0)
    vals = []
    for k in range(30):
        x = pd.DataFrame(rng.normal(0, 0.01, (200, 9)))
        vals.append((stats.pbo_cscv(x, n_splits=10, metric="sharpe")["pbo"],
                     stats.pbo_cscv(x, n_splits=10, metric="sharpe", ties="half")["pbo"]))
    le, half = np.mean(vals, axis=0)
    assert le > half  # λ = 0 compté comme sur-ajustement : biais vers 5/9
    assert half == pytest.approx(0.5, abs=0.05) and le == pytest.approx(5 / 9, abs=0.05)


def test_pbo_array_split_keeps_all_rows():
    rng = np.random.default_rng(1)
    x = pd.DataFrame(rng.normal(0, 0.01, (255, 4)))
    trim = stats.pbo_cscv(x, n_splits=10, metric="sharpe")
    full = stats.pbo_cscv(x, n_splits=10, metric="sharpe", split="array_split")
    assert trim["block_size"] == 25 and full["block_size"] == 26  # 255 = 5 × 26 + 5 × 25
    assert math.isfinite(full["pbo"])
    exact = pd.DataFrame(rng.normal(0, 0.01, (250, 4)))  # divisible : les deux conventions coïncident
    assert stats.pbo_cscv(exact, n_splits=10)["pbo"] == stats.pbo_cscv(exact, n_splits=10, split="array_split")["pbo"]
    with pytest.raises(ValueError):
        stats.pbo_cscv(x, n_splits=10, split="autre")


def test_family_clone_is_declared_untested_and_pbo_sensitivity_published(gap_run):
    out, res = gap_run
    fam = res.metrics["famille"]
    assert ["E", "A"] in fam["clones_exacts"]
    e = res.metrics["variantes"]["E"]
    assert e["testee"] is False and "non testée sur S1" in e["note_test"]
    assert res.metrics["variantes"]["A"]["testee"] is True
    sens = fam["pbo_sensibilite"]
    assert sens["sans_clones_variantes"] == ["A", "B"]
    assert sens["reference_nulle_n"] == pytest.approx(mt.pbo_null_reference(3))
    for k in ("convention_figee", "toutes_semaines_array_split", "lambda0_compte_demi",
              "famille_de_quasi_clones_simulee"):
        assert k in sens
    text = (out / "resultats.md").read_text(encoding="utf-8")
    assert "Sensibilité de la PBO" in text and "Non testée(s) sur S1" in text


# ---------------------------------------------------------------------------
# IC « mensuels » : une décision par mois civil
# ---------------------------------------------------------------------------


def test_monthly_ic_keeps_one_decision_per_calendar_month():
    dates = pd.bdate_range("2030-01-01", periods=160)
    rng = np.random.default_rng(5)
    tr = pd.DataFrame(100.0 * np.cumprod(1.0 + rng.normal(0, 0.01, (160, 20)), axis=0), dates,
                      [f"S{i}" for i in range(20)])
    fwd = tr.shift(-22) / tr.shift(-1) - 1.0
    month_end = [d for d in dates[:-30] if d == dates[dates.to_period("M") == d.to_period("M")][-1]]
    event = [pd.Timestamp("2030-02-11"), pd.Timestamp("2030-03-06")]  # décisions d'événement en cours de mois
    scores = {t: fwd.loc[t] for t in sorted(month_end + event)}
    ic = mt.monthly_ic(scores, tr)
    assert len(ic) == len(month_end) and not ic.index.to_period("M").duplicated().any()
    assert set(ic.index) == set(month_end)
    assert len(mt.monthly_ic(scores, tr, one_per_month=False)) == len(month_end) + len(event)


# ---------------------------------------------------------------------------
# Empreinte : référence de pré-enregistrement 751d1be, pas d'autoréférence
# ---------------------------------------------------------------------------


def test_fingerprint_check_cites_preregistration_commit_and_is_not_self_referential():
    fc = lk.fingerprint_check("f1582ed8e9fa1c85", ["f1582ed8e9fa1c85"])
    assert fc["conforme_etat_fige"] is True and fc["preenregistree_independante"] is False
    ref = fc["reference_preenregistrement"]
    assert ref["commit"].startswith("751d1be") and ref["empreinte_v1_0"] == "dcdf1fb7db530c44"
    assert fc["etat_fige"]["commit"].startswith("a2bfeb4")
    assert lk.fingerprint_check("0000000000000000", ["f1582ed8e9fa1c85"])["conforme"] is False


def test_registry_keeps_trace_of_preregistered_fingerprint(tmp_path):
    reg = TrialRegistry.initialize(tmp_path / "trials.parquet", addendum_v11=True)
    f = reg.frame
    i = int(np.flatnonzero((f["id"] == "S1-A").to_numpy())[0])
    reg._frame.at[i, "empreinte_config"] = "dcdf1fb7db530c44"  # état du registre au commit 751d1be
    p_a = json.loads(f.loc[f["id"] == "S1-A", "parametres"].iloc[0])
    w = pd.Series(np.random.default_rng(0).normal(0.001, 0.01, 60),
                  index=pd.date_range("2030-01-04", periods=60, freq="W-FRI"))
    reg.record("A", p_a, "S1", w, config_fingerprint="f1582ed8e9fa1c85")
    row = reg.frame[reg.frame["id"] == "S1-A"].iloc[0]
    assert row["empreinte_config"] == "f1582ed8e9fa1c85"
    assert "empreinte au pré-enregistrement : dcdf1fb7db530c44" in row["note"]
