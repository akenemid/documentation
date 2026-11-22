"""Pré-vol avant le test unique S1 (22/11/2026) : intégration stratégie × exécuteur de validation.

Données **synthétiques** uniquement (graines fixes). Les panels datés de 2017-2018 ne contiennent
aucune information sur le marché réel : ils servent à exercer le chemin « S1 » du code (début
d'échantillon sans historique, trou de BOC qui vide l'univers, verrou), sans aucun backtest ni
aucune performance sur les données réelles de l'échantillon vierge. Aucune requête réseau.

Corrections couvertes :

* variante I sur un univers vide (``construct.core_satellite_weights`` : diagnostic complet) ;
* décisions intra-mois du mode événementiel sans effet sur l'état annuel de REF et de I ;
* contrôles comptables publiés par run (``validation.controls``) ;
* exécuteur + vrai modèle ``BrvmAlpha`` (A, I, REF) sur un panel synthétique daté de S1.
"""

from __future__ import annotations

import json
import subprocess
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from test_strategy_alpha import SYMS, make_panels

from brvm_alpha import reference, settings
from brvm_alpha.backtest import engine
from brvm_alpha.backtest.engine import Backtester
from brvm_alpha.portfolio import construct
from brvm_alpha.strategy import BrvmAlpha
from brvm_alpha.validation import RunSpec, run_validation
from brvm_alpha.validation.controls import accounting_controls
from brvm_alpha.validation.runner import DEFAULT_DECISION_MODE


def s1_like_panels(n_days: int = 320, gap: tuple[int, int] = (200, 246), n_syms: int = 20) -> dict:
    """Panel synthétique daté de 2017 (aucune donnée réelle) : début sans historique et trou de BOC.

    Les numéros de séance (``session_no``) sont contigus ; les lignes ``gap`` sont retirées (BOC
    manquants) : après le trou, la fenêtre de 63 séances contient moins de 20 BOC et l'univers est
    vide (D1, plancher des filtres), comme au 30/07/2021 sur le panel réel.
    """
    P = make_panels(n_days=n_days, symbols=SYMS[:n_syms])
    idx = P["close"].index
    new = pd.bdate_range("2017-01-02", periods=len(idx), name="date")
    mp = dict(zip(idx, new, strict=True))
    out: dict = {}
    for k, v in P.items():
        if isinstance(v, (pd.DataFrame, pd.Series)) and v.index.equals(idx):
            v = v.copy()
            v.index = new
        out[k] = v
    m = out["market"].copy()
    m["date"] = new
    dt = out["dividends_table"].copy()
    for c in ("ex_date", "payment_date", "date"):
        dt[c] = dt[c].map(mp)
    out["dividends_table"] = dt
    out["last_div_date"] = out["last_div_date"].apply(lambda s: s.map(lambda x: mp.get(x, x - pd.DateOffset(years=6))))
    out["session_no"] = pd.DataFrame(np.tile(np.arange(1, len(new) + 1)[:, None], (1, out["close"].shape[1])), new,
                                     out["close"].columns)
    keep = np.ones(len(new), dtype=bool)
    keep[gap[0]:gap[1]] = False
    for k, v in list(out.items()):
        if isinstance(v, (pd.DataFrame, pd.Series)) and v.index.equals(new):
            out[k] = v[keep]
    out["market"] = m[keep].reset_index(drop=True)
    return out


@pytest.fixture(scope="module")
def s1_like() -> dict:
    return s1_like_panels()


# ---------------------------------------------------------------------------
# Variante I sur un univers vide (début de S1, trou de BOC de 2021)
# ---------------------------------------------------------------------------


def test_core_satellite_weights_empty_universe_has_full_diagnostics():
    w, diag = construct.core_satellite_weights(pd.Series(dtype=float), pd.Series(dtype=float), pd.Series(dtype=float),
                                               [], core_share=0.5, budget=0.98)
    assert w.empty and diag["invested"] == 0.0 and not diag["projected"]
    for key in ("upper", "violations", "active_constraints", "core_share", "solver", "raw"):
        assert key in diag, key
    assert diag["violations"]["budget"] == 0.0 and diag["active_constraints"] == []


def test_variant_i_decides_on_empty_universe(s1_like):
    idx = s1_like["close"].index
    m = BrvmAlpha(variant="I", notes=None, validation_s1=True)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        first = m.decide(idx[25], s1_like)  # janvier-février 2017 : aucun historique, univers vide
        after_gap = m.decide(idx[205], s1_like)  # juste après le trou de BOC : univers vide (D1)
    for dec in (first, after_gap):
        assert int(dec.universe["eligible"].sum()) == 0
        assert dec.diagnostics["mode"] == "coeur_satellite" and float(dec.weights.sum()) == 0.0


# ---------------------------------------------------------------------------
# Mode événementiel : une décision intra-mois ne consomme pas le rebalancement annuel
# ---------------------------------------------------------------------------


def test_intramonth_country_rule_keeps_annual_rebalance_of_ref():
    P = make_panels()  # 2023-01-02 → 2024-08 (séances synthétiques)
    idx = P["close"].index
    dec_end = idx[idx.searchsorted(pd.Timestamp("2023-12-29"))]
    probe = BrvmAlpha(variant="REF", notes=None, country_events=False)
    w0 = probe.decide(dec_end, P).weights
    top = w0.idxmax()
    country = reference.country_of(top)
    events = pd.DataFrame([{"date": "2024-01-05", "country": country, "rule": "severe"}])
    m = BrvmAlpha(variant="REF", notes=None, country_events=events)
    fn = m.strategy_fn(event_driven=True, calendar=idx)
    jan = [d for d in idx if d.year == 2024 and d.month == 1]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        first = fn(dec_end, engine.PanelView(P, dec_end))
        assert first is not None and float(first.sum()) == pytest.approx(0.98)
        assert m._sleeves["ref"]["year"] == 2023
        out = {d: fn(d, engine.PanelView(P, d)) for d in jan}
    t_event = pd.Timestamp("2024-01-05")
    w_ev = out[t_event]
    assert w_ev is not None, "la règle pays doit déclencher des ordres dès la séance qui suit l'annonce (D10)"
    members = [s for s in w_ev.index if reference.country_of(s) == country]
    assert float(w_ev[members].sum()) < float(first[members].sum())
    # l'état annuel n'est pas consommé par la décision intra-mois : la fin de janvier rebalance (D8)
    assert m._sleeves["ref"]["year"] == 2024
    assert m.last_decision.diagnostics["index"]["action"] == "rebalancement"
    assert out[jan[-1]] is not None


# ---------------------------------------------------------------------------
# Contrôles comptables
# ---------------------------------------------------------------------------


def test_accounting_controls_green_then_detect_tampering():
    P = make_panels(n_days=330)
    cfg = settings.apply_to_platform_config(scenario="central")
    m = BrvmAlpha(cfg, variant="A", notes=None)
    bt = Backtester(P, cfg.costs, cfg.constraints, 10e6, cfg.execution, cfg.taxes,
                    params=settings.load_strategy_config())
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = bt.run(m.strategy_fn(), rebalance="M", start=P["close"].index[0])
    c = accounting_controls(bt, res)
    assert c["ok"], c["anomalies"]
    assert c["cash_min_fcfa"] >= 0.0
    assert c["identite_vl_ecart_max"] < 1e-9 and c["identite_flux_ecart_max"] < 1e-9
    assert c["ventes_a_la_borne_basse"] == 0 and c["achats_a_la_borne_haute"] == 0
    co = c["couts"]
    # coût proportionnel minimal par aller : courtage 0,8 % × 1,18 + BRVM 0,2 % + DC/BR 0,1 % = 1,244 %
    assert co["n_executions"] > 0 and co["cout_aller_p10"] >= 0.01244 - 1e-9
    # falsification : 1 000 FCFA « apparus » dans le cash à mi-parcours -> identités rompues
    k = len(res.cash) // 2
    res.cash.iloc[k] += 1000.0
    bad = accounting_controls(bt, res)
    assert not bad["ok"] and any("identité de la VL" in a for a in bad["anomalies"])
    res.cash.iloc[k] -= 1000.0
    res.equity.iloc[k:] += 1000.0
    bad = accounting_controls(bt, res)
    assert not bad["ok"] and any("identité de flux" in a for a in bad["anomalies"])


# ---------------------------------------------------------------------------
# Exécuteur + vrai modèle BrvmAlpha sur un panel synthétique daté de S1
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), "-c", "user.email=test@example.invalid", "-c", "user.name=test",
                    *args], check=True, capture_output=True)


@pytest.fixture()
def clean_repo(tmp_path: Path) -> Path:
    root = tmp_path / "depot"
    (root / "brvm_alpha").mkdir(parents=True)
    (root / "configs").mkdir()
    (root / "brvm_alpha" / "module.py").write_text("X = 1\n", encoding="utf-8")
    (root / "configs" / "strategie.yaml").write_text("version: '1.1'\n", encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")
    return root


def test_runner_with_real_model_on_synthetic_s1_like_panel(s1_like, clean_repo, tmp_path):
    out = tmp_path / "validation_S1"
    plan = [RunSpec("A"), RunSpec("I"), RunSpec("REF")]
    assert DEFAULT_DECISION_MODE == "evenementiel"
    res = run_validation("S1", out_dir=out, panels=s1_like, plan=plan, allow_nonstandard_plan=True, workers=1,
                         n_boot=50, registry_path=tmp_path / "trials.parquet", repo_root=clean_repo)
    m = res.metrics
    assert set(res.statuses) == {"A", "I", "REF"}
    assert m["execution"]["mode_decision"] == "evenementiel" and m["execution"]["modes_effectifs"] == [
        "evenementiel"]
    assert m["controles"]["tous_ok"], m["controles"]["runs_en_anomalie"]
    modes = {v: set((m["runs"][f"{v}_central_10M"].get("decisions") or {}).get("modes", {})) for v in plan_ids(plan)}
    assert "coeur_satellite" in modes["I"] and "indice_discipline" in modes["REF"]
    assert {"vide", "selection"} <= modes["A"] or {"vide", "repli"} <= modes["A"] or "vide" in modes["A"]
    lock = json.loads((out / "lock.json").read_text(encoding="utf-8"))
    assert lock["statut"] == "terminé" and lock["mode_decision"] == "evenementiel"
    assert "empreinte_controle" in lock and lock["arbre_propre"] is True
    text = (out / "resultats.md").read_text(encoding="utf-8")
    assert "Contrôles comptables" in text and "Performance passée ≠ garantie" in text


def plan_ids(plan: list[RunSpec]) -> list[str]:
    return [s.variant for s in plan]
