"""Exécuteur du test unique S1 et du diagnostic S0 (additif v1.1 : D2, D6, D7, D12 ; spéc. §8).

Point d'entrée : :func:`run_validation` (``python -m brvm_alpha validate --sample S1|S0``).

Plan des runs (:func:`run_plan`, 30 runs) :

* les 9 variantes A-I et la référence ``REF`` (« indice discipliné », D8) aux coûts
  **centraux** et de **stress**, à K = 10 M FCFA ;
* A et I aux coûts **optimistes** et **sévères** (10 M FCFA) ;
* A, I et REF à K = 100 M et 1 Md FCFA (coûts centraux).

Seuls les runs centraux à 10 M FCFA sont des **essais** (registre, PBO, DSR) ; les autres
mesurent le même essai sous d'autres hypothèses (analyses de sensibilité, §8.4).

Fenêtre d'évaluation (D2) : ``t0`` = première séance où A (centrale, 10 M) détient des
titres ; toutes les métriques, tous les critères du §8.3 et tous les étalons sur
``[t0 ; fin]``, rebasés à ``t0`` ; sous-période 1 = ``[t0 ; 2019-12-31]``, sous-période 2 =
``[2020-01-01 ; 2022-11-16]`` ; semaines du 06/05 au 25/06/2021 exclues (défaut de
``metrics.weekly_returns`` et de ``evaluate_status``). Les semaines dont l'observation couvre
plusieurs séances après un trou de BOC sont **gardées** pour les critères chaînés (rendement,
actif, drawdowns : §3.1.3, « gardé pour chaîner le TR ») et retirées des seules statistiques de
dispersion (IR, TE, volatilité, Sharpe, PSR/DSR, PBO, CVaR, bootstrap) ; la couverture se mesure
sur le calendrier W-FRI moins la fenêtre du §8.1 (correction du 22/11/2026, §8.5 de la
spécification). La fenêtre complète est publiée pour information.

S1 exige le verrou (:mod:`brvm_alpha.validation.lock`) ; S0 écrit dans
``reports/diagnostic_S0/`` sans verrou, avec la mention « contaminé, aucune valeur de
preuve ». Les runs indépendants sont parallélisés (``ProcessPoolExecutor``, au plus 3
processus, contexte ``spawn``) ; chaque run est déterministe et les résultats sont remis
dans l'ordre du plan, quel que soit l'ordre d'achèvement.

Toutes les sorties sont des **estimations** sous hypothèses (coûts, exécution, données) :
performance passée ≠ garantie, aucun gain n'est garanti.
"""

from __future__ import annotations

import concurrent.futures as cf
import hashlib
import json
import logging
import math
import multiprocessing as mp
import os
import time
import traceback
import warnings
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from brvm_alpha.backtest import metrics as mt
from brvm_alpha.backtest.walkforward import (
    DEFAULT_REGISTRY_PATH,
    FAMILY_V11,
    N_TRIALS_START_V11,
    REFERENCE_TRIAL_ID,
    REFERENCE_VARIANT,
    STATUT_PROMU,
    TrialRegistry,
    evaluate_status,
    variant_promotion,
)
from brvm_alpha.validation import lock as lk
from brvm_alpha.validation.benchmarks import BENCHMARKS, benchmark_levels, equal_weight_level
from brvm_alpha.validation.controls import CONTROL_TOLERANCE, accounting_controls

__all__ = [
    "BANNER",
    "CAPACITY_CAPITALS",
    "CAPITAL_REFERENCE",
    "DECISION_MODES",
    "DEFAULT_DECISION_MODE",
    "MAX_WORKERS",
    "PREDICTION_8_3",
    "S0_MENTION",
    "SAMPLES",
    "RunSpec",
    "SampleSpec",
    "ValidationFailed",
    "ValidationResult",
    "brvm_alpha_model",
    "capital_label",
    "execute_run",
    "run_plan",
    "run_validation",
]

logger = logging.getLogger("brvm_alpha.validation")

BANNER = "Performance passée ≠ garantie. Aucun gain n'est garanti."
S0_MENTION = "Diagnostic S0 : échantillon contaminé, aucune valeur de preuve."
CAPITAL_REFERENCE = 10_000_000.0
CAPACITY_CAPITALS = (100_000_000.0, 1_000_000_000.0)
CENTRAL, STRESS = "central", "stress"
SENSITIVITY_COSTS = ("optimistic", "severe")
#: Variantes soumises aux coûts optimistes / sévères et aux capacités de 100 M et 1 Md (§8.4).
SENSITIVITY_VARIANTS = ("A", "I")
CAPACITY_VARIANTS = ("A", "I", REFERENCE_VARIANT)
#: Processus au plus (consigne D12 : ≤ 3).
MAX_WORKERS = 3
#: Base de comptage des fenêtres tranchée par l'additif v1.1 (D1).
WINDOW_BASIS = "sessions"
#: Modes de décision : ``"evenementiel"`` (défaut depuis le pré-vol du 22/11/2026 :
#: ``strategy_fn(event_driven=True, calendar)`` + ``rebalance="D"`` : ordres aux fins de mois ET aux
#: événements du §6 « Fréquence » ; règles pays D10 dès la première séance qui suit l'annonce, ventes
#: reportées au jour ex §5.2, poche S1 de E) ou ``"mensuel"`` (``strategy_fn()`` + ``rebalance="M"`` :
#: aucun ordre entre deux fins de mois, donc règles pays appliquées à la fin du mois seulement, contraire à
#: D10). Le mode est consigné dans le verrou et dans ``metrics.json`` ; sur S1, un repli est un échec.
DECISION_MODES = ("evenementiel", "mensuel")
DEFAULT_DECISION_MODE = "evenementiel"
REPORTS_DIR = lk.PROJECT_ROOT / "reports"
#: Prédiction écrite d'avance (§8.3, maintenue par l'additif v1.1).
PREDICTION_8_3 = (
    "Prédiction écrite d'avance (§8.3, maintenue par l'additif v1.1) : avec un IR réel de 0,3, le z attendu sur "
    "S1 (5,9 ans) vaut 0,3 × √5,9 ≈ 0,73, soit un PSR ≈ 0,77 : G2 échouera probablement. Le statut le plus "
    "probable, même pour une bonne stratégie, est « candidat » ; le rejet de A est un résultat plausible (l'essai "
    "de fumée de S0 est défavorable). Un IR > 1 serait d'abord traité comme une ERREUR (anticipation, prix "
    "périmés, coûts oubliés).")


class ValidationFailed(RuntimeError):
    """Un ou plusieurs runs ont échoué (S1 : aucune métrique n'est calculée ni publiée)."""


# ---------------------------------------------------------------------------
# Échantillons et plan des runs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SampleSpec:
    """Échantillon évalué (§8.1)."""

    code: str
    period: tuple[str, str]
    subperiods: tuple[tuple[str, str], ...]
    out_name: str
    history_start: str | None
    validation_s1: bool
    contaminated: bool


SAMPLES: dict[str, SampleSpec] = {
    "S1": SampleSpec("S1", mt.S1, tuple(mt.S1_SUBPERIODS), "validation_S1", None, True, False),
    "S0": SampleSpec("S0", mt.S0, tuple(mt.S0_SUBPERIODS), "diagnostic_S0", mt.S0[0], False, True),
}


def capital_label(capital: float) -> str:
    """Étiquette courte d'un capital : ``10M``, ``100M``, ``1Md``."""
    c = float(capital)
    if c >= 1e9 and c % 1e9 == 0:
        return f"{int(c // 1e9)}Md"
    if c >= 1e6 and c % 1e6 == 0:
        return f"{int(c // 1e6)}M"
    return f"{int(round(c))}"


@dataclass(frozen=True)
class RunSpec:
    """Un run du plan : variante × scénario de coûts × capital."""

    variant: str
    costs: str = CENTRAL
    capital: float = CAPITAL_REFERENCE

    @property
    def run_id(self) -> str:
        return f"{self.variant}_{self.costs}_{capital_label(self.capital)}"

    @property
    def is_trial(self) -> bool:
        """Run central à 10 M FCFA : un essai du registre (les autres sont des sensibilités)."""
        return self.costs == CENTRAL and float(self.capital) == CAPITAL_REFERENCE

    @property
    def in_family(self) -> bool:
        """Essai de la famille de la PBO et du DSR (A-I, hors référence)."""
        return self.is_trial and self.variant in FAMILY_V11

    @property
    def role(self) -> str:
        if self.is_trial:
            return "essai (famille)" if self.in_family else "essai (référence, hors PBO)"
        return "sensibilité"


def run_plan(family: Sequence[str] = FAMILY_V11, reference: str = REFERENCE_VARIANT) -> list[RunSpec]:
    """Plan de l'additif v1.1 (§8.4, D12) : 30 runs dans un ordre fixe."""
    plan: list[RunSpec] = []
    for v in (*family, reference):
        plan.append(RunSpec(v, CENTRAL, CAPITAL_REFERENCE))
        plan.append(RunSpec(v, STRESS, CAPITAL_REFERENCE))
    for v in SENSITIVITY_VARIANTS:
        for c in SENSITIVITY_COSTS:
            plan.append(RunSpec(v, c, CAPITAL_REFERENCE))
    for v in CAPACITY_VARIANTS:
        for k in CAPACITY_CAPITALS:
            plan.append(RunSpec(v, CENTRAL, k))
    return plan


def _plan_is_standard(plan: Sequence[RunSpec]) -> bool:
    return [s.run_id for s in plan] == [s.run_id for s in run_plan()]


# ---------------------------------------------------------------------------
# Modèle par défaut (BrvmAlpha, import tardif)
# ---------------------------------------------------------------------------


class _IndexModeModel:
    """Adaptateur : référence « indice discipliné » via ``strategy_fn(mode="index")`` (repli)."""

    def __init__(self, model: Any) -> None:
        self._m = model
        self.repli = "variante 'REF' inconnue de BrvmAlpha : mode='index' de la variante A"

    def strategy_fn(self) -> Callable[..., Any]:
        return self._m.strategy_fn(mode="index")

    def __getattr__(self, name: str) -> Any:
        return getattr(self._m, name)


def brvm_alpha_model(spec: RunSpec, config: Any, sample: str) -> Any:
    """Modèle BrvmAlpha d'un run (contrat : ``BrvmAlpha(cfg, variant, capital, …).strategy_fn()``).

    ``window_basis="sessions"`` (D1), ``notes=None`` (D11), ``validation_s1`` seulement pour
    S1 ; ``history_start`` = début de S0 pour le diagnostic S0. La chronologie des événements
    pays (D10) est celle de la stratégie (``country_events`` par défaut).
    """
    from brvm_alpha.strategy import BrvmAlpha

    smp = SAMPLES[sample]
    kw: dict[str, Any] = {"capital": float(spec.capital), "notes": None, "window_basis": WINDOW_BASIS,
                          "validation_s1": smp.validation_s1, "history_start": smp.history_start}
    try:
        return BrvmAlpha(config, variant=spec.variant, **kw)
    except ValueError:
        if spec.variant != REFERENCE_VARIANT:
            raise
        return _IndexModeModel(BrvmAlpha(config, variant="A", **kw))


# ---------------------------------------------------------------------------
# Exécution d'un run (processus de travail)
# ---------------------------------------------------------------------------

_STATE: dict[str, Any] = {}


def _load_panels(source: tuple[Any, ...]) -> Mapping[str, Any]:
    kind = source[0]
    if kind == "obj":
        return source[1]
    if kind == "dir":
        from brvm_alpha.strategy import build_panels

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return build_panels(source[1], end=source[2])
    raise ValueError(f"source de panels inconnue : {kind!r}")


def _init_worker(source: tuple[Any, ...]) -> None:
    _STATE["panels"] = _load_panels(source)


def _run_in_worker(spec: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    return execute_run(RunSpec(**spec), _STATE["panels"], ctx)


class _DecisionLog:
    """Journal des décisions d'un run (univers éligible, score composite, mode)."""

    def __init__(self, model: Any, capture: bool) -> None:
        self.model = model
        self.capture = bool(capture)
        self.rows: list[dict[str, Any]] = []
        self.eligible: dict[pd.Timestamp, pd.Series] = {}
        self.scores: dict[pd.Timestamp, pd.Series] = {}
        self.errors: list[str] = []

    def wrap(self, fn: Callable[..., Any]) -> Callable[..., Any]:
        def wrapped(asof: Any, view: Any) -> Any:
            w = fn(asof, view)
            try:
                self._record(pd.Timestamp(asof).normalize(), w)
            except Exception as exc:  # noqa: BLE001 - le journal ne doit jamais interrompre un run
                self.errors.append(f"{pd.Timestamp(asof).date()} : {exc.__class__.__name__} : {exc}")
            return w

        return wrapped

    def _record(self, t: pd.Timestamp, w: Any) -> None:
        if w is None:
            return  # aucun ordre (mode événementiel hors événement)
        row: dict[str, Any] = {"date": t, "n_lignes": math.nan, "investi": math.nan, "n_eligibles": math.nan,
                               "mode": None}
        if w is not None:
            ws = pd.Series(w, dtype=float)
            row["n_lignes"] = int((ws > 1e-9).sum())
            row["investi"] = float(ws.clip(lower=0).sum())
        dec = getattr(self.model, "last_decision", None)
        if dec is not None and pd.Timestamp(getattr(dec, "asof", pd.NaT)).normalize() == t:
            uni = getattr(dec, "universe", None)
            if isinstance(uni, pd.DataFrame) and "eligible" in uni.columns:
                el = uni["eligible"].astype("boolean").fillna(False).astype(bool)
                el.index = el.index.astype(str)
                row["n_eligibles"] = int(el.sum())
                if self.capture:
                    self.eligible[t] = el
            diag = getattr(dec, "diagnostics", None) or {}
            row["mode"] = diag.get("mode") if isinstance(diag, Mapping) else None
            sig = getattr(dec, "signals", None) or {}
            comp = sig.get("composite") if isinstance(sig, Mapping) else None
            if self.capture and isinstance(comp, pd.Series):
                c = comp.astype(float)
                c.index = c.index.astype(str)
                self.scores[t] = c
        self.rows.append(row)


def _warning_summary(caught: Sequence[warnings.WarningMessage], limit: int = 15) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for w in caught:
        msg = str(w.message).strip().splitlines()[0][:220] if str(w.message).strip() else w.category.__name__
        counts[msg] = counts.get(msg, 0) + 1
    return [{"message": k, "n": v} for k, v in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]]


def execute_run(spec: RunSpec, panels: Mapping[str, Any], ctx: Mapping[str, Any]) -> dict[str, Any]:
    """Exécute un run (moteur ``Backtester``, rebalancement mensuel) et renvoie ses séries.

    ``ctx`` : ``sample``, ``start``, ``end``, ``factory`` (``f(spec, config, sample)`` → objet
    exposant ``strategy_fn()``, facultativement ``engine_country_shocks()`` et
    ``last_decision``), ``strategy_params`` (configuration YAML du moteur), ``capture``
    (identifiants des runs dont on garde l'univers et le score). Une exception est capturée
    et rapportée (``ok=False``).
    """
    t_start = time.perf_counter()
    out: dict[str, Any] = {"run_id": spec.run_id, "spec": asdict(spec), "ok": False, "error": None}
    try:
        from brvm_alpha import settings
        from brvm_alpha.backtest.engine import Backtester

        cfg = settings.apply_to_platform_config(scenario=spec.costs)
        factory = ctx.get("factory") or brvm_alpha_model
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            model = factory(spec, cfg, ctx["sample"])
            mode = ctx.get("decision_mode") or DEFAULT_DECISION_MODE
            rebalance = "M"
            if mode == "evenementiel":
                # §6 et D10 : ordres aux fins de mois ET aux événements (règles pays dès la séance qui
                # suit l'annonce, poche S1, ventes reportées) ; le moteur appelle la stratégie chaque séance.
                cal = pd.DatetimeIndex(panels["close"].index)
                try:
                    fn = model.strategy_fn(event_driven=True, calendar=cal)
                    rebalance = "D"
                except TypeError:
                    fn = model.strategy_fn()
                    mode = "mensuel (repli : strategy_fn sans mode événementiel)"
            else:
                fn = model.strategy_fn()
            shocks = None
            if callable(getattr(model, "engine_country_shocks", None)):
                shocks = model.engine_country_shocks()
            bt = Backtester(panels, cfg.costs, cfg.constraints, float(spec.capital), cfg.execution, cfg.taxes,
                            params=ctx.get("strategy_params"), country_shocks=shocks)
            journal = _DecisionLog(model, capture=spec.run_id in set(ctx.get("capture") or ()))
            res = bt.run(journal.wrap(fn), rebalance=rebalance, start=ctx["start"], end=ctx["end"])
        try:
            # Contrôles comptables et d'exécution (aucune performance) : cash ≥ 0, identités de la VL,
            # bornes de cotation, coût par aller (§6, §7.1, §7.2) ; publiés dans metrics.json.
            controles = accounting_controls(bt, res)
        except Exception as exc:  # noqa: BLE001 - un contrôle illisible est signalé, jamais masqué
            controles = {"ok": False, "anomalies": [f"contrôles impossibles ({exc.__class__.__name__} : {exc})"]}
        w = res.weights
        ev = getattr(model, "country_events", None)
        out.update(
            ok=True,
            returns=res.returns,
            equity=res.equity,
            exposure=w.sum(axis=1).rename("exposure"),
            n_lines=(w > 1e-9).sum(axis=1).rename("n_lines"),
            turnover_daily=res.turnover_daily,
            costs_daily=res.costs_daily,
            cost_breakdown=res.cost_breakdown,
            trades=res.trades,
            dividends=res.dividends,
            dividends_boc=getattr(res, "dividends_boc", res.dividends),
            dividend_events=getattr(res, "dividend_events", pd.DataFrame()),
            rebalance_dates=[pd.Timestamp(x) for x in res.rebalance_dates],
            fill_rate=float(res.fill_rate) if res.fill_rate == res.fill_rate else math.nan,
            decisions=pd.DataFrame(journal.rows),
            eligible=pd.DataFrame(journal.eligible).T if journal.eligible else None,
            scores=pd.DataFrame(journal.scores).T if journal.scores else None,
            journal_errors=journal.errors[:20],
            meta={
                "n_country_shock_cells": res.meta.get("n_country_shock_cells"),
                "dividend_gap_vs_boc": res.meta.get("dividend_gap_vs_boc"),
                "dividend_boc_line_available": res.meta.get("dividend_boc_line_available"),
                "n_vwap_fallback": res.meta.get("n_vwap_fallback"),
                "delisted_positions": len(res.meta.get("delisted_positions") or []),
                "nav_non_positive_from": res.meta.get("nav_non_positive_from"),
                "modele": repr(model),
                "repli": getattr(model, "repli", None),
                "n_evenements_pays": len(ev) if isinstance(ev, pd.DataFrame) else 0,
                "n_chocs_pays": len(shocks) if isinstance(shocks, pd.DataFrame) else 0,
                "mode_decision": mode,
            },
            warnings=_warning_summary(caught),
            controles=controles,
        )
    except Exception as exc:  # noqa: BLE001 - rapporté dans le résultat du run
        out["error"] = f"{exc.__class__.__name__} : {exc}"
        out["traceback"] = traceback.format_exc()
    out["duration_s"] = round(time.perf_counter() - t_start, 3)
    return out


def _execute_plan(
    plan: Sequence[RunSpec],
    source: tuple[Any, ...],
    panels: Mapping[str, Any],
    ctx: dict[str, Any],
    workers: int,
    log: Callable[[str], None],
) -> list[dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    n = len(plan)

    def done(r: dict[str, Any]) -> None:
        results[r["run_id"]] = r
        state = "ok" if r.get("ok") else f"ÉCHEC ({r.get('error')})"
        log(f"run {len(results)}/{n} {r['run_id']} : {state}, {r.get('duration_s', 0):.1f} s")

    if workers <= 1:
        for spec in plan:
            done(execute_run(spec, panels, ctx))
    else:
        mpctx = mp.get_context("spawn")
        with cf.ProcessPoolExecutor(max_workers=workers, mp_context=mpctx, initializer=_init_worker,
                                    initargs=(source,)) as ex:
            futs = [ex.submit(_run_in_worker, asdict(spec), ctx) for spec in plan]
            for f in cf.as_completed(futs):
                done(f.result())
    return [results[s.run_id] for s in plan]


# ---------------------------------------------------------------------------
# Métriques (§8.2)
# ---------------------------------------------------------------------------


def _f(x: Any) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return math.nan
    return v if math.isfinite(v) else math.nan


def _session_series(panels: Mapping[str, Any], calendar: pd.DatetimeIndex) -> pd.Series | None:
    sn = panels.get("session_no") if isinstance(panels, Mapping) else None
    if isinstance(sn, pd.DataFrame) and sn.shape[1]:
        s = sn.apply(pd.to_numeric, errors="coerce").max(axis=1)
    elif isinstance(sn, pd.Series):
        s = pd.to_numeric(sn, errors="coerce")
    else:
        return None
    s.index = pd.DatetimeIndex(pd.to_datetime(s.index))
    s = s.reindex(calendar)
    return s if s.notna().any() else None


def _weekly(daily: pd.Series, t0: Any, end: Any, sess: pd.Series | None) -> pd.Series:
    """Rendements hebdomadaires **chaînés** de ``[t0 ; fin]`` : seule la fenêtre du §8.1 est retirée ;
    les semaines multi-séances (trous de BOC) sont gardées (§3.1.3)."""
    d = mt.evaluation_window(pd.Series(daily, dtype=float), t0, end)
    w = mt.weekly_returns(d, session_no=sess, max_sessions=None)
    return pd.Series(w, dtype=float)


def _calendar_years(t0: Any, end: Any) -> float:
    """Années calendaires de la fenêtre ``[t0 ; fin]`` (jours / 365,25)."""
    a, b = pd.Timestamp(t0), pd.Timestamp(end)
    return max((b - a).days + 1, 1) / 365.25


def _cost_decomposition(trades: Any) -> dict[str, float]:
    """Coût par aller pondéré par les montants, décomposé (frais, demi-spread, impact) : la somme des
    trois composantes vaut le coût moyen pondéré par aller (``cost / value``)."""
    out = {"frais": math.nan, "demi_spread": math.nan, "impact": math.nan, "total": math.nan}
    if not isinstance(trades, pd.DataFrame) or not len(trades) or "value" not in trades.columns:
        return out
    val = trades["value"].astype(float).abs()
    tot = float(val.sum())
    if not tot > 0:
        return out
    for key, col in (("frais", "commission"), ("demi_spread", "spread_cost"), ("impact", "impact")):
        if col in trades.columns:
            out[key] = float(trades[col].astype(float).sum() / tot)
    if "cost" in trades.columns:
        out["total"] = float(trades["cost"].astype(float).sum() / tot)
    return out


def _slice_daily(s: pd.Series | pd.DataFrame, t0: Any, end: Any) -> Any:
    return mt.evaluation_window(s, t0, end)


def _sharpes(x: pd.Series) -> dict[str, Any]:
    if x.dropna().size < 3:
        return {"naive": math.nan, "lo": math.nan, "glm": math.nan, "lo_glm_gap": math.nan, "divergence": False,
                "n_obs": int(x.dropna().size)}
    t = mt.sharpe_triplet(x)
    return {k: t[k] for k in ("naive", "lo", "glm", "glm_xi", "lo_glm_gap", "divergence", "n_obs")}


def _series_metrics(w: pd.Series, bench: Mapping[str, pd.Series], *, n_boot: int, seed: int,
                    subperiods: Sequence[tuple[Any, Any]], full: bool = True,
                    multi_weeks: Sequence[Any] | pd.DatetimeIndex | None = None) -> dict[str, Any]:
    """Métriques hebdomadaires d'une série nette contre le TR (et le panier EW).

    ``w`` et les étalons sont **chaînés** (semaines multi-séances comprises) : rendement annualisé,
    actif, drawdowns. ``multi_weeks`` : semaines multi-séances retirées des seules statistiques de
    dispersion (volatilité, IR, TE, Sharpe, PSR, bootstrap, CVaR), §3.1.3."""
    tr = bench.get("TR")
    wd = mt.dispersion_sample(w, multi_weeks)
    out: dict[str, Any] = {"n_semaines": int(w.dropna().size),
                           "n_semaines_dispersion": int(wd.dropna().size),
                           "rendement_an": mt.annualized_return(w) if w.size else math.nan,
                           "volatilite_an": float(wd.std(ddof=1) * math.sqrt(mt.WEEKS_PER_YEAR)) if wd.size > 1
                           else math.nan,
                           "drawdown_absolu": mt.max_drawdown(w) if w.size else math.nan}
    if tr is not None and len(tr):
        both = pd.concat({"s": w, "b": tr}, axis=1, join="inner").dropna()
        both_d = mt.dispersion_sample(both, multi_weeks)
        a = (both["s"] - both["b"]).rename("actif")
        ad = (both_d["s"] - both_d["b"]).rename("actif")
        out.update(
            actif_tr_an=mt.annualized_active_return(both["s"], both["b"]) if len(both) else math.nan,
            ir_tr=mt.information_ratio(ad) if ad.size > 1 else math.nan,
            te_tr=float(ad.std(ddof=1) * math.sqrt(mt.WEEKS_PER_YEAR)) if ad.size > 1 else math.nan,
            drawdown_relatif_tr=mt.relative_drawdown(both["s"], both["b"]) if len(both) else math.nan,
            drawdown_tr=mt.max_drawdown(both["b"]) if len(both) else math.nan,
        )
        if full:
            out["sharpe"] = _sharpes(wd)
            out["sharpe_actif"] = _sharpes(ad)
            out["psr_actif"] = mt.psr(ad) if ad.size >= 3 else math.nan
            out["bootstrap_ir"] = mt.bootstrap_ci(ad, "ir", n_boot=n_boot, mean_block=mt.WEEKLY_MEAN_BLOCK, seed=seed)
            out["bootstrap_actif_moyen_an"] = mt.bootstrap_ci(ad, "mean", n_boot=n_boot,
                                                              mean_block=mt.WEEKLY_MEAN_BLOCK, seed=seed)
            try:
                out["cvar"] = mt.cvar_ratio(both_d["s"], both_d["b"], n_boot=n_boot,
                                            mean_block=mt.WEEKLY_MEAN_BLOCK, seed=seed)
            except ValueError as exc:
                out["cvar"] = {"ratio": math.nan, "note": str(exc)}
        subs = []
        for a0, b0 in subperiods:
            sa = a[(a.index >= pd.Timestamp(a0)) & (a.index <= pd.Timestamp(b0))]
            sd = ad[(ad.index >= pd.Timestamp(a0)) & (ad.index <= pd.Timestamp(b0))]
            sb = both["b"].reindex(sa.index)
            subs.append({"debut": pd.Timestamp(a0), "fin": pd.Timestamp(b0), "n_semaines": int(sa.size),
                         "n_semaines_dispersion": int(sd.size),
                         "actif_tr_an": mt.annualized_active_return(sa + sb, sb) if sa.size else math.nan,
                         "ir_tr": mt.information_ratio(sd) if sd.size > 1 else math.nan})
        out["sous_periodes"] = subs
    ew = bench.get("EW")
    if ew is not None and len(ew):
        both = pd.concat({"s": w, "b": ew}, axis=1, join="inner").dropna()
        both_d = mt.dispersion_sample(both, multi_weeks)
        ad = both_d["s"] - both_d["b"]
        out.update(actif_ew_an=mt.annualized_active_return(both["s"], both["b"]) if len(both) else math.nan,
                   ir_ew=mt.information_ratio(ad) if ad.size > 1 else math.nan,
                   te_ew=float(ad.std(ddof=1) * math.sqrt(mt.WEEKS_PER_YEAR)) if ad.size > 1 else math.nan)
    return out


def _run_metrics(r: Mapping[str, Any], w: pd.Series, bench: Mapping[str, pd.Series], t0: Any, end: Any, *,
                 n_boot: int, seed: int, subperiods: Sequence[tuple[Any, Any]],
                 multi_weeks: Sequence[Any] | pd.DatetimeIndex | None = None) -> dict[str, Any]:
    out = _series_metrics(w, bench, n_boot=n_boot, seed=seed, subperiods=subperiods, multi_weeks=multi_weeks)
    to = _slice_daily(r["turnover_daily"], t0, end)
    out["rotation_mensuelle_aller"] = mt.monthly_one_way_turnover(to)
    cd = _slice_daily(r["costs_daily"], t0, end)
    eq = _slice_daily(r["equity"], t0, end)
    n_days = len(eq)
    total = float(cd.sum())
    out["couts_payes_fcfa"] = total
    # Annualisation par les années CALENDAIRES de la fenêtre (correction du 22/11/2026) : la fenêtre de S1
    # compte environ 228 séances observées par an (BOC manquants), et non 252.
    years = _calendar_years(eq.index[0], eq.index[-1]) if n_days else math.nan
    out["couts_an_pct_nav_moyenne"] = (total / float(eq.mean()) / years) if n_days and eq.mean() > 0 \
        else math.nan
    out["couts_an_pct_nav_moyenne_252_seances"] = ((total / float(eq.mean()) * 252.0 / n_days)
                                                   if n_days and eq.mean() > 0 else math.nan)
    out["seances_observees_par_an"] = (n_days / years) if n_days else math.nan
    tr_w = r.get("trades")
    if isinstance(tr_w, pd.DataFrame) and len(tr_w) and "date" in tr_w.columns:
        dd = pd.DatetimeIndex(tr_w["date"])
        tr_w = tr_w[(dd >= pd.Timestamp(t0)) & (dd <= pd.Timestamp(end))]
    out["cout_aller_decomposition_ponderee"] = _cost_decomposition(tr_w)
    bd = _slice_daily(r["cost_breakdown"], t0, end)
    out["couts_detail_fcfa"] = {str(k): float(v) for k, v in bd.sum().items()} if isinstance(bd, pd.DataFrame) \
        else {}
    out["lignes_moyennes"] = float(_slice_daily(r["n_lines"], t0, end).mean()) if n_days else math.nan
    out["part_investie_moyenne"] = float(_slice_daily(r["exposure"], t0, end).mean()) if n_days else math.nan
    if n_days:
        nl = pd.Series(_slice_daily(r["n_lines"], t0, end), dtype=float)
        ex = pd.Series(_slice_daily(r["exposure"], t0, end), dtype=float)
        out["lignes_quantiles"] = {"min": _f(nl.min()), "p10": _f(nl.quantile(0.10)), "mediane": _f(nl.median()),
                                   "max": _f(nl.max())}
        out["part_investie_quantiles"] = {"min": _f(ex.min()), "p10": _f(ex.quantile(0.10)),
                                          "mediane": _f(ex.median()), "max": _f(ex.max())}
    dv = float(_slice_daily(r["dividends"], t0, end).sum())
    dvb = float(_slice_daily(r["dividends_boc"], t0, end).sum())
    out["dividendes"] = {"credites_fcfa": dv, "ligne_d_fcfa": dvb, "ecart_fcfa": dv - dvb,
                         "note": "flux = montant corrigé (meilleure estimation du versement réel, D6) ; signaux = "
                                 "ligne (d) du BOC"}
    out["valeur_finale_fcfa"] = float(eq.iloc[-1]) if n_days else math.nan
    out["n_transactions"] = len(r["trades"]) if isinstance(r.get("trades"), pd.DataFrame) else 0
    out["controles"] = r.get("controles") or {"ok": False, "anomalies": ["contrôles absents"]}
    return out


def _benchmark_metrics(w: pd.Series, tr: pd.Series | None,
                       multi_weeks: Sequence[Any] | pd.DatetimeIndex | None = None) -> dict[str, Any]:
    wd = mt.dispersion_sample(w, multi_weeks)
    out = {"n_semaines": int(w.dropna().size), "rendement_an": mt.annualized_return(w) if w.size else math.nan,
           "volatilite_an": float(wd.std(ddof=1) * math.sqrt(mt.WEEKS_PER_YEAR)) if wd.size > 1 else math.nan,
           "drawdown_absolu": mt.max_drawdown(w) if w.size else math.nan}
    if tr is not None and len(tr) and w.size:
        both = pd.concat({"s": w, "b": tr}, axis=1, join="inner").dropna()
        out["ecart_tr_an"] = mt.annualized_active_return(both["s"], both["b"]) if len(both) else math.nan
    return out


# ---------------------------------------------------------------------------
# Sérialisation
# ---------------------------------------------------------------------------


def _jsonable(obj: Any) -> Any:
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, (np.floating,)):
        return _jsonable(float(obj))
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (pd.Timestamp,)):
        return None if pd.isna(obj) else obj.isoformat()
    if obj is pd.NaT:
        return None
    if isinstance(obj, np.ndarray):
        return [_jsonable(x) for x in obj.tolist()]
    if isinstance(obj, pd.Series):
        return {(k.strftime("%Y-%m-%d") if isinstance(k, pd.Timestamp) else str(k)): _jsonable(v)
                for k, v in obj.items()}
    if isinstance(obj, pd.DataFrame):
        return [_jsonable(r) for r in obj.to_dict("records")]
    if isinstance(obj, Mapping):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_jsonable(x) for x in obj]
    if isinstance(obj, Path):
        return str(obj)
    return obj


def _write_json(path: Path, obj: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_jsonable(obj), ensure_ascii=False, indent=2, sort_keys=False, default=str) + "\n",
                    encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Résultat
# ---------------------------------------------------------------------------


@dataclass
class ValidationResult:
    """Résultat de :func:`run_validation` (dossier de sortie, métriques, statuts, durées)."""

    sample: str
    out_dir: Path
    metrics: dict[str, Any]
    statuses: dict[str, str]
    trial_ids: dict[str, str]
    duration_s: float
    files: dict[str, Path] = field(default_factory=dict)
    lock: dict[str, Any] | None = None

    @property
    def banner(self) -> str:
        return BANNER


# ---------------------------------------------------------------------------
# Exécuteur
# ---------------------------------------------------------------------------


def _default_workers() -> int:
    return max(1, min(MAX_WORKERS, os.cpu_count() or 1))


def run_validation(
    sample: str = "S1",
    out_dir: str | Path | None = None,
    rerun_reason: str | None = None,
    panel_dir: str | Path | None = None,
    workers: int | None = None,
    *,
    registry_path: str | Path | None = None,
    repo_root: str | Path | None = None,
    panels: Mapping[str, Any] | None = None,
    model_factory: Callable[[RunSpec, Any, str], Any] | None = None,
    plan: Sequence[RunSpec] | None = None,
    allow_nonstandard_plan: bool = False,
    n_boot: int = mt.N_BOOT,
    seed: int = 0,
    log: Callable[[str], None] | None = None,
    decision_mode: str = DEFAULT_DECISION_MODE,
) -> ValidationResult:
    """Exécute le test unique S1 (verrouillé) ou le diagnostic S0 et publie les résultats.

    Parameters
    ----------
    sample
        ``"S1"`` (test unique pré-enregistré, verrou D12) ou ``"S0"`` (diagnostic contaminé,
        sans verrou, sortie ``reports/diagnostic_S0/``).
    out_dir
        Dossier de sortie (défaut : ``reports/validation_S1`` ou ``reports/diagnostic_S0``).
    rerun_reason
        S1 seulement : motif d'une relance (bogue démontré). Sans lui, une seconde exécution
        est refusée (``lock.ValidationRefused``). Avec lui : nouveaux essais (``N``
        augmente), anciens résultats déplacés dans ``precedent_<horodatage>/``, les deux
        publiés.
    panel_dir
        Panel parquet (défaut : ``data/panel``), ignoré si ``panels`` est fourni.
    workers
        Processus parallèles (``≤ 3`` ; défaut ``min(3, nproc)``) ; ``1`` : exécution dans le
        processus courant. Résultats identiques quel que soit ``workers``.
    registry_path, repo_root
        Registre des essais (défaut ``reports/trials.parquet``) et dépôt git du verrou.
    panels, model_factory
        Panels en mémoire et fabrique de modèles (tests sur données synthétiques) ; défaut :
        :func:`brvm_alpha_model` (``BrvmAlpha``).
    plan, allow_nonstandard_plan
        Plan des runs (défaut :func:`run_plan`) ; un plan non standard est refusé sur S1
        sauf ``allow_nonstandard_plan=True`` (tests).
    n_boot, seed
        Bootstrap stationnaire (défaut **5 000** répliques explicites, blocs de 8 semaines) ;
        graine fixe.
    decision_mode
        ``"evenementiel"`` (défaut : ``strategy_fn(event_driven=True, calendar=…)`` et
        ``rebalance="D"`` : décisions de fin de mois, plus les ordres entre deux du §6 « Fréquence » :
        règles pays dès la première séance qui suit l'annonce (D10), poche S1, ventes reportées) ou
        ``"mensuel"`` (``strategy_fn()`` et ``rebalance="M"`` : aucun ordre entre deux fins de mois).
        Consigné dans le verrou et dans ``metrics.json`` ; sur S1, un repli d'un run vers un autre mode
        que celui demandé est un échec (aucune métrique publiée).
    """
    t_all = time.perf_counter()
    code = str(sample).strip().upper()
    if code not in SAMPLES:
        raise ValueError(f"échantillon inconnu {sample!r} : S1 ou S0")
    smp = SAMPLES[code]
    if decision_mode not in DECISION_MODES:
        raise ValueError(f"decision_mode doit valoir l'un de {DECISION_MODES}")
    journal: list[str] = []

    def say(msg: str) -> None:
        stamp = pd.Timestamp.now(tz="UTC").strftime("%H:%M:%S")
        journal.append(f"{stamp} {msg}")
        (log or logger.info)(msg)

    out = Path(out_dir) if out_dir is not None else REPORTS_DIR / smp.out_name
    reg_path = Path(registry_path) if registry_path is not None else DEFAULT_REGISTRY_PATH
    plan = list(plan) if plan is not None else run_plan()
    standard = _plan_is_standard(plan)
    if not plan:
        raise ValueError("plan de runs vide")
    if code == "S1" and not standard and not allow_nonstandard_plan:
        raise lk.ValidationRefused("plan de runs non conforme à l'additif v1.1 (30 runs) : refusé sur S1")
    if code == "S1" and model_factory is None and panels is None and int(n_boot) != mt.N_BOOT:
        raise lk.ValidationRefused(f"S1 exige n_boot = {mt.N_BOOT} (spéc. §8.2, explicite) : {n_boot} refusé")
    if not any(s.variant == "A" and s.is_trial for s in plan):
        raise ValueError("le plan doit contenir A aux coûts centraux à 10 M FCFA (définition de t0, D2)")
    n_workers = _default_workers() if workers is None else max(1, min(MAX_WORKERS, int(workers)))
    now = pd.Timestamp.now(tz="UTC")
    stamp = now.strftime("%Y%m%dT%H%M%SZ")

    # -- registre (amorcé avec l'additif v1.1) et contrôles ---------------------------------
    registry = TrialRegistry.initialize(reg_path, save=False, addendum_v11=True)
    git = lk.git_tree_state(repo_root)
    ident = lk.config_identity()
    # Empreinte du YAML : comparée à celle de l'état figé a2bfeb4 (premier test S1) ; la référence de
    # pré-enregistrement citée est le commit 751d1be (YAML v1.0, empreinte dcdf1fb7db530c44). Le registre
    # (S1-I, REF-ID) porte l'empreinte écrite dans le même commit que l'état figé : ce n'est pas une valeur
    # pré-enregistrée indépendante (revue du 22/11/2026). Un écart est consigné et publié (non bloquant).
    pre_fp = sorted({str(x) for x in registry.frame.loc[registry.frame["id"].isin(["S1-I", REFERENCE_TRIAL_ID]),
                                                        "empreinte_config"].dropna()})
    fp_check = lk.fingerprint_check(ident.get("empreinte_config"), pre_fp)
    rerun: dict[str, Any] = {"relance": False, "motif": None}
    lock_path = out / lk.LOCK_NAME
    if code == "S1":
        lk.require_clean_tree(git)
        rerun = lk.check_rerun(registry, out, rerun_reason, "S1")
    elif rerun_reason:
        say("--rerun-reason ignoré hors S1 (diagnostic S0 sans verrou)")
    previous_dir = None
    if rerun.get("relance"):
        previous_dir = lk.archive_previous(out, stamp)
        say(f"relance motivée : anciens résultats conservés dans {previous_dir}")
    out.mkdir(parents=True, exist_ok=True)

    if panels is not None:
        source: tuple[Any, ...] = ("obj", panels)
        panel_desc = "panels fournis en mémoire"
    else:
        from brvm_alpha.strategy.alpha import DEFAULT_PANEL_DIR

        pdir = Path(panel_dir) if panel_dir is not None else Path(DEFAULT_PANEL_DIR)
        source = ("dir", str(pdir), smp.period[1])
        panel_desc = str(pdir)
    panel_dir_eff = None if panels is not None else Path(source[1])

    from brvm_alpha import settings

    strategy_params = settings.load_strategy_config()
    lock_payload: dict[str, Any] = {
        "echantillon": code,
        "statut": "en cours",
        "horodatage_utc": now.isoformat(),
        "commit": git.get("commit"),
        "branche": git.get("branche"),
        "arbre_propre": git.get("propre"),
        "fichiers_modifies": git.get("modifies"),
        "fichiers_non_suivis": git.get("non_suivis"),
        "empreinte_config": ident.get("empreinte_config"),
        "empreinte_controle": fp_check,
        "version_yaml": ident.get("version_yaml"),
        "sha256_yaml": ident.get("sha256_yaml"),
        "periode": list(smp.period),
        "window_basis": WINDOW_BASIS,
        "mode_decision": decision_mode,
        "plan": [{"run_id": s.run_id, **asdict(s), "role": s.role} for s in plan],
        "plan_standard": standard,
        "n_boot": int(n_boot),
        "graine": int(seed),
        "workers": n_workers,
        "panel": panel_desc,
        "registre": str(reg_path),
        "n_essais_registre_avant": registry.n_trials(),
        "relance": {"motif": rerun.get("motif"), "precedent": str(previous_dir) if previous_dir else None,
                    "essais_deja_executes": rerun.get("essais_executes", []),
                    "verrou_precedent": rerun.get("verrou_precedent")} if rerun.get("relance") else None,
        "bandeau": BANNER,
    }
    if not fp_check["conforme"]:
        say(f"ATTENTION : empreinte de configuration {ident.get('empreinte_config')} différente de celle de l'état "
            f"figé {lk.FROZEN_STATE_COMMIT[:7]} ({lk.FROZEN_STATE_FINGERPRINT}) : paramètres modifiés depuis le premier "
            "test S1 ?")
    if code == "S1":
        lk.write_lock(lock_path, lock_payload)
        say(f"verrou S1 écrit : {lock_path} (commit {git.get('commit')}, empreinte {ident.get('empreinte_config')})")
    else:
        say(f"{S0_MENTION} Commit {git.get('commit')} (arbre {'propre' if git.get('propre') else 'modifié'})")

    def _rest() -> ValidationResult:
        # -- exécution des runs ----------------------------------------------------------------
        if panels is None:
            say(f"chargement du panel {panel_desc}")
            panels_main = _load_panels(source)
        else:
            panels_main = panels
        capture = [s.run_id for s in plan if s.is_trial or s.variant == "A"]
        ctx = {"sample": code, "start": smp.period[0], "end": smp.period[1], "factory": model_factory,
               "strategy_params": strategy_params, "capture": capture, "decision_mode": decision_mode}
        say(f"{len(plan)} runs, {n_workers} processus")
        t_runs = time.perf_counter()
        outputs = _execute_plan(plan, source, panels_main, ctx, n_workers, say)
        runs_s = time.perf_counter() - t_runs
        failed = [r for r in outputs if not r.get("ok")]
        if code == "S1":
            # Le mode de décision consigné dans le verrou doit être celui de CHAQUE run (aucun repli silencieux).
            for r in outputs:
                eff = (r.get("meta") or {}).get("mode_decision")
                if r.get("ok") and eff != decision_mode:
                    r.update(ok=False, error=f"mode de décision effectif {eff!r} différent du mode consigné "
                                             f"{decision_mode!r}")
            failed = [r for r in outputs if not r.get("ok")]
        if failed:
            msg = "; ".join(f"{r['run_id']} : {r.get('error')}" for r in failed)
            if code == "S1":
                lock_payload.update(statut="échec", erreurs=[{"run_id": r["run_id"], "erreur": r.get("error"),
                                                              "trace": r.get("traceback")} for r in failed],
                                    duree_runs_s=round(runs_s, 1))
                lk.write_lock(lock_path, lock_payload)
                raise ValidationFailed(f"{len(failed)} run(s) S1 en échec : aucune métrique calculée ni publiée ({msg}). "
                                       "Une relance exigera --rerun-reason (bogue démontré).")
            say(f"{len(failed)} run(s) en échec (diagnostic poursuivi) : {msg}")
        by_id = {r["run_id"]: r for r in outputs if r.get("ok")}
        a_id = RunSpec("A").run_id
        if a_id not in by_id:
            raise ValidationFailed(f"run {a_id} en échec : t0 (D2) indéfini, aucune métrique calculée")

        # -- fenêtre d'évaluation (D2) -----------------------------------------------------------
        a_run = by_id[a_id]
        calendar = pd.DatetimeIndex(a_run["returns"].index)
        t0 = mt.first_investment_date(a_run["exposure"])
        if t0 is None:
            raise ValidationFailed("la variante A ne s'investit jamais : t0 (D2) indéfini")
        end = min(pd.Timestamp(smp.period[1]), calendar[-1])
        sess = _session_series(panels_main, calendar)
        last_week = pd.Timestamp(pd.Period(end, freq=mt.WEEKLY_FREQ).end_time.normalize())
        subperiods = mt.evaluation_subperiods(t0, smp.subperiods, end=last_week)
        say(f"t0 = {t0.date()} (première séance investie de A) ; fenêtre [{t0.date()} ; {end.date()}]")

        # -- étalons ---------------------------------------------------------------------------
        def mask_of(run_id: str) -> pd.DataFrame | None:
            r = by_id.get(run_id)
            el = r.get("eligible") if r else None
            if isinstance(el, pd.DataFrame) and len(el):
                el = el.copy()
                el.index = pd.DatetimeIndex(el.index)
                return el.astype("boolean").fillna(False).astype(bool)
            return None

        levels, bnotes = benchmark_levels(panels_main, calendar, panel_dir=panel_dir_eff, eligible_mask=mask_of(a_id),
                                          end=end)
        ew_by_capital: dict[float, pd.Series] = {}
        if "EW" in levels:
            ew_by_capital[CAPITAL_REFERENCE] = levels["EW"]
        for k in CAPACITY_CAPITALS:
            m = mask_of(RunSpec("A", CENTRAL, k).run_id)
            if m is not None:
                s_ew, _, _ = equal_weight_level(panels_main, panel_dir=panel_dir_eff, eligible_mask=m)
                if s_ew is not None:
                    s_ew = pd.Series(s_ew, dtype=float)
                    s_ew.index = pd.DatetimeIndex(s_ew.index)
                    ew_by_capital[k] = s_ew.reindex(s_ew.index.union(calendar)).ffill(limit_area="inside").reindex(
                        calendar)
        if "TR" not in levels:
            raise ValidationFailed("Composite TR indisponible : étalon principal manquant, aucune métrique calculée")

        def bench_daily(level: pd.Series) -> pd.Series:
            return pd.Series(level, dtype=float).pct_change(fill_method=None)

        bench_w = {c: _weekly(bench_daily(levels[c]), t0, end, sess) for c in levels.columns}
        bench_w = {c: s for c, s in bench_w.items() if s.dropna().size}
        ew_w = {k: _weekly(bench_daily(s), t0, end, sess) for k, s in ew_by_capital.items()}
        # Semaines retirées du chaînage : la seule fenêtre du §8.1. Semaines multi-séances (trous de BOC) :
        # gardées pour les critères chaînés, retirées des statistiques de dispersion (§3.1.3).
        a_win = mt.weekly_returns(mt.evaluation_window(a_run["returns"], t0, end), session_no=sess, max_sessions=None)
        excluded = sorted({str(pd.Timestamp(x).date()) for x in getattr(a_win, "attrs", {}).get("weeks_dropped", [])})
        cal_win = calendar[(calendar >= t0) & (calendar <= end)]
        multi_weeks = mt.multi_session_weeks(cal_win, session_no=sess)
        multi_weeks = multi_weeks[multi_weeks.isin(pd.DatetimeIndex(a_win.index))]
        multi_full = mt.multi_session_weeks(calendar[calendar <= end], session_no=sess)
        say(f"semaines multi-séances gardées pour le chaînage, retirées de la dispersion : {len(multi_weeks)} "
            f"({', '.join(str(d.date()) for d in multi_weeks) or 'aucune'})")

        # -- séries hebdomadaires et métriques par run ---------------------------------------------
        weekly: dict[str, pd.Series] = {}
        run_metrics: dict[str, dict[str, Any]] = {}
        say(f"métriques par run (bootstrap stationnaire n_boot = {n_boot}, blocs de {mt.WEEKLY_MEAN_BLOCK} semaines)")
        for spec in plan:
            r = by_id.get(spec.run_id)
            if r is None:
                continue
            w = _weekly(r["returns"], t0, end, sess)
            weekly[spec.run_id] = w
            bench = {"TR": bench_w["TR"]}
            ew = ew_w.get(float(spec.capital))
            if ew is not None:
                bench["EW"] = ew
            m = _run_metrics(r, w, bench, t0, end, n_boot=n_boot, seed=seed, subperiods=subperiods,
                             multi_weeks=multi_weeks)
            full_w = mt.weekly_returns(pd.Series(r["returns"], dtype=float), session_no=sess, max_sessions=None)
            full_tr = mt.weekly_returns(bench_daily(levels["TR"]).loc[calendar[0]:end], session_no=sess,
                                        max_sessions=None)
            m["fenetre_complete"] = _series_metrics(pd.Series(full_w, dtype=float), {"TR": pd.Series(full_tr)},
                                                    n_boot=n_boot, seed=seed, subperiods=[], full=False,
                                                    multi_weeks=multi_full)
            m["fenetre_complete"]["debut"] = calendar[0]
            m.update(run_id=spec.run_id, variante=spec.variant, couts=spec.costs, capital=float(spec.capital),
                     role=spec.role, duree_s=r.get("duration_s"), avertissements_moteur=r.get("warnings", []),
                     meta=r.get("meta", {}), taux_execution=r.get("fill_rate"))
            dec = r.get("decisions")
            if isinstance(dec, pd.DataFrame) and len(dec):
                modes = dec["mode"].dropna().astype(str)
                m["decisions"] = {"n": len(dec), "modes": modes.value_counts().to_dict(),
                                  "eligibles_moyens": _f(dec["n_eligibles"].mean()),
                                  "premiere_decision": dec["date"].min(), "derniere_decision": dec["date"].max()}
                idx_mode = dec[dec["mode"].astype(str) == "indice_discipline"]
                if len(idx_mode):
                    m["decisions"]["passage_indice_discipline"] = idx_mode["date"].min()
            run_metrics[spec.run_id] = m

        # -- contrôles comptables et d'exécution (aucune performance) ---------------------------------
        ctl_keys = ("ok", "cash_min_fcfa", "exposition_max", "frais_dus_max_fcfa", "identite_vl_ecart_max",
                    "identite_flux_ecart_max", "ventes_a_la_borne_basse", "achats_a_la_borne_haute", "anomalies")
        controls_summary: dict[str, Any] = {}
        for rid, r in by_id.items():
            c = r.get("controles") or {"ok": False, "anomalies": ["contrôles absents"]}
            row = {k: c.get(k) for k in ctl_keys}
            row.update({k: (c.get("couts") or {}).get(k) for k in ("cout_aller_median", "cout_aller_moyen_pondere",
                                                                    "n_executions")})
            controls_summary[rid] = row
        bad = [rid for rid, c in controls_summary.items() if not c.get("ok")]
        controls_doc = {"tous_ok": not bad, "runs_en_anomalie": bad, "runs": controls_summary,
                        "tolerance_identites": CONTROL_TOLERANCE}
        say("contrôles comptables : " + ("tous verts" if not bad else f"ANOMALIES dans {', '.join(bad)}"))

        # -- famille : PBO, variance des Sharpe, IC --------------------------------------------------
        tr_w = bench_w["TR"]
        # Couverture (§8.3, seuil de 95 % documenté au §8.5) : semaines W-FRI de [t0 ; fin] moins la seule
        # fenêtre du §8.1, mesurée sur les séries chaînées (evaluate_status, expected_period). Les semaines
        # de l'étalon ne servent plus de semaines attendues : calculées avec les mêmes retraits, elles
        # donnaient une couverture de 100 % par construction (garde-fou tautologique, corrigé le 22/11/2026).
        active: dict[str, pd.Series] = {}
        for spec in plan:
            if spec.is_trial and spec.run_id in weekly:
                w = weekly[spec.run_id]
                both = pd.concat({"s": w, "b": tr_w}, axis=1, join="inner").dropna()
                active[spec.variant] = (both["s"] - both["b"]).rename(spec.variant)
        fam_cols = [v for v in FAMILY_V11 if v in active]
        fam_frame = pd.DataFrame({v: active[v] for v in fam_cols}).dropna(how="any")
        fam_disp = mt.dispersion_sample(fam_frame, multi_weeks)
        family: dict[str, Any] = {"variantes": fam_cols, "n_famille": len(FAMILY_V11), "complete": len(fam_cols) == len(
            FAMILY_V11), "n_semaines_communes": len(fam_frame), "n_semaines_dispersion": len(fam_disp),
            "pbo": math.nan, "pente_degradation": math.nan,
            "n_blocs": 10, "critere": "Sharpe de Lo (q = 4) des rendements actifs nets contre le TR (semaines "
                                      "multi-séances exclues)"}
        # Clones exacts dans la famille (p. ex. E = A faute d'avis de dividende daté à l'avance) : déclarés.
        clones: list[list[str]] = []
        for i, v in enumerate(fam_cols):
            for u in fam_cols[:i]:
                if np.allclose(fam_frame[v].to_numpy(), fam_frame[u].to_numpy(), rtol=0.0, atol=1e-12):
                    clones.append([v, u])
        family["clones_exacts"] = clones
        if len(fam_cols) >= 2 and len(fam_disp) >= 20:
            try:
                pb = mt.family_pbo(fam_disp, n_splits=10)
                family["pbo"] = _f(pb.get("pbo"))
                family["pente_degradation"] = _f(pb.get("degradation_slope"))
            except Exception as exc:  # noqa: BLE001 - échantillon trop court
                family["note_pbo"] = f"PBO non calculée ({exc.__class__.__name__} : {exc})"
            # Sensibilité de la PBO (publiée ; C6 reste évalué avec la convention figée ci-dessus).
            sens: dict[str, Any] = {"convention_figee": family["pbo"],
                                    "reference_nulle_n": mt.pbo_null_reference(len(fam_cols)),
                                    "reference_nulle_lambda0_demi": mt.pbo_null_reference(len(fam_cols), "half")}

            def _pbo_of(frame: pd.DataFrame, **kw: Any) -> float:
                try:
                    return _f(mt.family_pbo(frame, n_splits=10, **kw).get("pbo"))
                except Exception:  # noqa: BLE001 - publiée NaN
                    return math.nan

            sens["toutes_semaines_array_split"] = _pbo_of(fam_disp, split="array_split")
            sens["lambda0_compte_demi"] = _pbo_of(fam_disp, ties="half")
            no_clone = [v for v in fam_cols if not any(v == c[0] for c in clones)]
            if len(no_clone) < len(fam_cols) and len(no_clone) >= 2:
                sens["sans_clones"] = _pbo_of(fam_disp[no_clone])
                sens["sans_clones_variantes"] = no_clone
            if "A" in fam_disp.columns:
                rng = np.random.default_rng(seed)
                base = fam_disp["A"].to_numpy(dtype=float)
                clone_fam = pd.DataFrame({f"C{k}": base + rng.normal(0.0, 1e-4, base.size) for k in
                                          range(len(fam_cols))}, index=fam_disp.index)
                sens["famille_de_quasi_clones_simulee"] = _pbo_of(clone_fam)
            sens["note"] = ("Sensibilité publiée (correction du 22/11/2026) : la PBO dépend du découpage et de la "
                            "convention λ = 0 ; avec N impair, la PBO nulle vaut ⌊(N + 1)/2⌋/N (5/9 pour N = 9). Une "
                            "famille de quasi-clones donne une PBO élevée mécaniquement : la PBO n'a alors pas de "
                            "pouvoir discriminant. C6 reste évalué avec la convention figée avant S1.")
            family["pbo_sensibilite"] = sens
        else:
            family["note_pbo"] = "famille ou échantillon insuffisant pour la CSCV"
        srs = []
        for v in fam_cols:
            x = fam_disp[v].dropna() if v in fam_disp.columns else pd.Series(dtype=float)
            sd = float(x.std(ddof=1)) if len(x) > 1 else math.nan
            if sd and math.isfinite(sd) and sd > 0:
                srs.append(float(x.mean()) / sd)
        sr_var = float(np.var(srs, ddof=1)) if len(srs) >= 2 else math.nan
        family["variance_sharpe_hebdo"] = sr_var

        tr_index = panels_main.get("tr_index") if isinstance(panels_main, Mapping) else None
        ic: dict[str, pd.Series] = {}
        for spec in plan:
            r = by_id.get(spec.run_id)
            if not (spec.in_family and r is not None and isinstance(r.get("scores"), pd.DataFrame)):
                continue
            if not isinstance(tr_index, pd.DataFrame):
                continue
            sc = r["scores"]
            sc = sc[pd.DatetimeIndex(sc.index) >= pd.Timestamp(smp.period[0])]
            ic[spec.variant] = mt.monthly_ic(sc, tr_index, horizon=21, lag=1, min_names=15, end=end,
                                             eligible=r.get("eligible"))

        # -- registre : essais exécutés -----------------------------------------------------------
        fp = ident.get("empreinte_config")
        trial_ids: dict[str, str] = {}
        for spec in plan:
            if not (spec.is_trial and spec.run_id in weekly and weekly[spec.run_id].dropna().size):
                continue
            light = {k: run_metrics[spec.run_id].get(k) for k in ("rendement_an", "actif_tr_an", "ir_tr", "te_tr",
                                                                  "drawdown_relatif_tr", "psr_actif")}
            light.update(t0=t0, fin=end, echantillon=code, mode_decision=decision_mode)
            if code == "S1":
                row_id = REFERENCE_TRIAL_ID if spec.variant == REFERENCE_VARIANT else f"S1-{spec.variant}"
                f = registry.frame
                row = f[f["id"] == row_id]
                params = json.loads(str(row["parametres"].iloc[0])) if len(row) else {"variante": spec.variant}
                tid = registry.record(spec.variant, params, "S1", weekly[spec.run_id], light,
                                      config_fingerprint=fp, rerun_reason=rerun.get("motif") if rerun.get("relance")
                                      else None, family=str(row["famille"].iloc[0]) if len(row) else "",
                                      source="brvm_alpha.validation.runner (validate --sample S1)")
            else:
                params = {"variante": spec.variant, "couts": spec.costs, "capital": float(spec.capital),
                          "periode": list(smp.period), "window_basis": WINDOW_BASIS, "t0": str(t0.date()),
                          "mode_decision": decision_mode}
                tid = registry.record(spec.variant, params, "S0", weekly[spec.run_id], light,
                                      trial_id=f"S0-DIAG-{stamp}-{spec.variant}",
                                      family="S0 diagnostic (validate --sample S0)", config_fingerprint=fp,
                                      source="brvm_alpha.validation.runner (validate --sample S0)",
                                      note="diagnostic contaminé, aucune valeur de preuve ; compté dans N")
            trial_ids[spec.run_id] = tid
        n_reg = registry.n_trials()
        g1 = registry.is_complete(sample=code, variants=FAMILY_V11, min_trials=N_TRIALS_START_V11)
        family.update(n_registre=n_reg, registre_complet=g1)
        # Variance des Sharpe pour le DSR du registre : deux conventions publiées (§8.5) ; G3 reste évalué
        # avec la variance de la famille (convention du code figé avant S1).
        try:
            sr_var_reg = float(registry.sharpe_variance())
        except Exception:  # noqa: BLE001 - publiée NaN
            sr_var_reg = math.nan
        family["variance_sharpe_registre"] = sr_var_reg
        family["note_dsr"] = ("DSR « registre » : N = essais du registre ; variance des Sharpe hebdomadaires de la "
                              "famille (convention utilisée pour G3 sur S1) et, à côté, variance des Sharpe de tous "
                              "les essais exécutés du registre (rendements absolus de S0 et de S1 mélangés). La "
                              "première déflate peu (variantes presque identiques) ; la seconde est prudente.")
        say(f"registre : N = {n_reg} essais (G1 {'vert' if g1 else 'rouge'})")

        # -- DSR, haircut, statuts §8.3, promotion §3.4 -------------------------------------------
        from brvm_alpha.quant import stats

        statuses: dict[str, str] = {}
        variants_out: dict[str, Any] = {}
        stress_id = {s.variant: s.run_id for s in plan if s.costs == STRESS and float(s.capital) == CAPITAL_REFERENCE}
        for spec in plan:
            if not (spec.is_trial and spec.variant in active):
                continue
            v = spec.variant
            a_c = active[v]
            s_id = stress_id.get(v)
            a_s = None
            if s_id in weekly:
                both = pd.concat({"s": weekly[s_id], "b": tr_w}, axis=1, join="inner").dropna()
                a_s = both["s"] - both["b"]
            m = run_metrics[spec.run_id]
            cv = _f((m.get("cvar") or {}).get("ratio"))
            ir = _f(m.get("ir_tr"))
            n_obs = int(a_c.dropna().size)
            a_cd = mt.dispersion_sample(a_c, multi_weeks)
            n_obs = int(a_cd.dropna().size)
            dsr_reg = mt.dsr(a_cd, n_reg, sr_var) if n_obs >= 3 else math.nan
            dsr_reg_var_reg = mt.dsr(a_cd, n_reg, sr_var_reg) if n_obs >= 3 else math.nan
            dsr_fam = mt.dsr(a_cd, len(FAMILY_V11), sr_var) if n_obs >= 3 else math.nan
            hsr = math.nan
            if math.isfinite(ir) and n_obs >= 2:
                hsr = float(stats.haircut_sharpe(ir, n_obs=n_obs, n_tests=n_reg, method="bhy",
                                                 periods_per_year=mt.WEEKS_PER_YEAR))
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                rep = evaluate_status(a_c, a_s, tr_w, subperiods, turnover=m.get("rotation_mensuelle_aller"),
                                      pbo=family["pbo"] if math.isfinite(family["pbo"]) else None,
                                      cvar_ratio=cv if math.isfinite(cv) else None,
                                      pbo_slope=family["pente_degradation"] if math.isfinite(family["pente_degradation"])
                                      else None,
                                      n_trials=n_reg, sr_variance=sr_var if math.isfinite(sr_var) else None,
                                      registry_complete=g1, ic_monthly=ic.get(v), n_boot=n_boot, seed=seed, start=t0,
                                      expected_period=(t0, last_week), dispersion_exclude=multi_weeks)
            statut = rep.statut
            if statut == STATUT_PROMU:  # garde-fou : impossible sans suivi réel S2
                raise AssertionError("statut PROMU sans suivi réel S2 : incohérence")
            statuses[v] = statut
            crit = rep.criteres.copy()
            fails = crit[(crit["groupe"] == "rejet") & (crit["verifie"] == True)]
            miss = crit[(crit["groupe"] == "candidat") & (crit["verifie"] != True)]
            variants_out[v] = {
                "run_id": spec.run_id,
                "essai": trial_ids.get(spec.run_id),
                "role": spec.role,
                "statut": statut,
                "statut_informatif": v == REFERENCE_VARIANT,
                "rejets_declenches": fails["code"].tolist(),
                "criteres_candidat_non_verifies": miss["code"].tolist(),
                "criteres": crit.to_dict("records"),
                "mesures_statut": {k: rep.mesures.get(k) for k in ("actif_net_central_an", "actif_net_stress_an", "ir",
                                                                    "ir_sous_periodes", "actif_sous_periodes_an",
                                                                    "drawdown_relatif", "drawdown_absolu", "drawdown_tr",
                                                                    "rotation_mensuelle", "couverture",
                                                                    "couverture_dispersion", "semaines_attendues",
                                                                    "n_semaines", "n_semaines_dispersion",
                                                                    "semaines_sous_periodes")},
                "dsr_registre": dsr_reg,
                "dsr_registre_variance_registre": dsr_reg_var_reg,
                "dsr_famille_n9": dsr_fam,
                "hsr_bhy": hsr,
                "ic_mensuel": ic.get(v, pd.Series(dtype=float)),
                "ic_t_nw": rep.mesures.get("promotion_S1_ic_t_nw"),
                "avertissements": rep.avertissements,
            }
            clone_of = [c[1] for c in family.get("clones_exacts", []) if c[0] == v]
            if clone_of:
                variants_out[v]["testee"] = False
                variants_out[v]["note_test"] = (
                    f"{v} non testée sur S1 : rendements identiques à ceux de {clone_of[0]} (clone exact). Pour E, "
                    "aucun avis de dividende n'est daté à l'avance dans les données (première vue environ un jour "
                    "avant la date ex) : la poche S1 ne s'ouvre jamais. Statut publié pour information.")
                variants_out[v]["avertissements"] = [variants_out[v]["note_test"]] + list(rep.avertissements)
            else:
                variants_out[v]["testee"] = True
            run_metrics[spec.run_id].update(dsr_registre=dsr_reg, dsr_registre_variance_registre=dsr_reg_var_reg,
                                            dsr_famille_n9=dsr_fam, hsr_bhy=hsr, statut=statut)

        promotion: dict[str, Any] = {"principal": "A", "regle": "§3.4 : X remplace A seulement si X bat A en actif net "
                                     "ET DSR ≥ 0,95 avec N = 9 ET PBO ≤ 0,25"}
        if "A" in fam_frame.columns and len(fam_frame) >= 2:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    pr = variant_promotion(fam_frame, benchmark=tr_w.reindex(fam_frame.index),
                                           pbo=family["pbo"] if math.isfinite(family["pbo"]) else None, baseline="A",
                                           n_trials=len(FAMILY_V11), sr_variance=sr_var if math.isfinite(sr_var) else None,
                                           dispersion_exclude=multi_weeks)
                promotion.update(principal=pr.principal, criteres=pr.criteres.reset_index().to_dict("records"),
                                 avertissements=pr.avertissements, n_trials=pr.n_trials)
            except Exception as exc:  # noqa: BLE001
                promotion["note"] = f"règle non évaluable ({exc.__class__.__name__} : {exc})"

        for spec in plan:
            tid = trial_ids.get(spec.run_id)
            if tid:
                m = run_metrics[spec.run_id]
                vout = variants_out.get(spec.variant, {})
                sens = {s.run_id: {k: run_metrics[s.run_id].get(k) for k in ("actif_tr_an", "ir_tr", "rendement_an")}
                        for s in plan if s.variant == spec.variant and not s.is_trial and s.run_id in run_metrics}
                registry.set_metrics(tid, _jsonable({
                    "echantillon": code, "t0": t0, "fin": end, "rendement_an": m.get("rendement_an"),
                    "actif_tr_an": m.get("actif_tr_an"), "actif_ew_an": m.get("actif_ew_an"), "ir_tr": m.get("ir_tr"),
                    "te_tr": m.get("te_tr"), "psr_actif": m.get("psr_actif"), "dsr_registre": m.get("dsr_registre"),
                    "dsr_famille_n9": m.get("dsr_famille_n9"), "hsr_bhy": m.get("hsr_bhy"),
                    "dsr_registre_variance_registre": m.get("dsr_registre_variance_registre"),
                    "semaines_multi_seances": [str(d.date()) for d in multi_weeks],
                    "drawdown_relatif_tr": m.get("drawdown_relatif_tr"), "drawdown_absolu": m.get("drawdown_absolu"),
                    "rotation_mensuelle_aller": m.get("rotation_mensuelle_aller"), "statut": vout.get("statut"),
                    "pbo_famille": family.get("pbo"), "n_registre": n_reg, "sensibilites": sens,
                    "ic_mensuel": vout.get("ic_mensuel"),
                }))

        # -- sorties -------------------------------------------------------------------------------
        total_s = time.perf_counter() - t_all
        bench_metrics = {}
        for c, (lab, role) in BENCHMARKS.items():
            note = bnotes.get(c, {"disponible": False, "note": "non disponible"})
            entry = {"libelle": lab, "role": role, **note}
            if c in bench_w:
                entry["mesures"] = _benchmark_metrics(bench_w[c], tr_w if c != "TR" else None, multi_weeks)
            bench_metrics[c] = entry
        for k, s in ew_w.items():
            if float(k) != CAPITAL_REFERENCE and s.dropna().size:
                bench_metrics[f"EW_{capital_label(k)}"] = {"libelle": f"panier équipondéré TR des éligibles de A à "
                                                                      f"{capital_label(k)} FCFA", "role": "capacité",
                                                           "disponible": True,
                                                           "mesures": _benchmark_metrics(s, tr_w, multi_weeks)}
        previous = None
        if previous_dir is not None and (previous_dir / "metrics.json").exists():
            try:
                pm = json.loads((previous_dir / "metrics.json").read_text(encoding="utf-8"))
                previous = {"dossier": str(previous_dir), "execution": pm.get("execution"),
                            "statuts": {v: d.get("statut") for v, d in (pm.get("variantes") or {}).items()},
                            "tableau": {v: {k: (pm.get("runs", {}).get(d.get("run_id"), {}) or {}).get(k)
                                            for k in ("rendement_an", "actif_tr_an", "ir_tr", "drawdown_relatif_tr")}
                                        for v, d in (pm.get("variantes") or {}).items()},
                            "t0": pm.get("t0")}
            except (OSError, ValueError) as exc:
                previous = {"dossier": str(previous_dir), "erreur": str(exc)}

        metrics_doc: dict[str, Any] = {
            "bandeau": BANNER,
            "mention": S0_MENTION if smp.contaminated else "Test unique pré-enregistré S1 (additif v1.1, D12).",
            "echantillon": code,
            "periode": list(smp.period),
            "t0": t0,
            "fin": end,
            "sous_periodes": [[a, b] for a, b in subperiods],
            "fenetres_exclues": [list(x) for x in mt.EXCLUDE_STATS_WINDOWS],
            "semaines_exclues": excluded,
            "semaines_multi_seances": [str(d.date()) for d in multi_weeks],
            "regle_semaines": ("Critères chaînés (rendement annualisé, actif R1/R2/C1/C3, drawdowns R4/R5/C4) : toutes "
                               "les semaines sauf la fenêtre du §8.1 ; statistiques de dispersion (volatilité, IR R3/C2, "
                               "TE, Sharpe, PSR/DSR, PBO, CVaR, bootstrap) : sans les semaines multi-séances "
                               f"(observation de plus de {mt.MAX_WEEKLY_SESSIONS} séances, §3.1.3). Couverture : "
                               "calendrier W-FRI de [t0 ; fin] moins la fenêtre du §8.1 (seuil 95 %, §8.5). "
                               "Correction du 22/11/2026."),
            "frequence": mt.WEEKLY_FREQ,
            "n_boot": int(n_boot),
            "bloc_moyen_semaines": mt.WEEKLY_MEAN_BLOCK,
            "execution": {
                "commit": git.get("commit"), "branche": git.get("branche"), "arbre_propre": git.get("propre"),
                "fichiers_modifies": git.get("modifies"), "fichiers_non_suivis": git.get("non_suivis"),
                "empreinte_config": ident.get("empreinte_config"), "empreinte_controle": fp_check,
                "version_yaml": ident.get("version_yaml"),
                "horodatage_utc": now, "duree_totale_s": round(total_s, 1), "duree_runs_s": round(runs_s, 1),
                "workers": n_workers, "panel": panel_desc, "plan_standard": standard,
                "durees_runs_s": {r["run_id"]: r.get("duration_s") for r in outputs},
                "runs_en_echec": [{"run_id": r["run_id"], "erreur": r.get("error")} for r in failed],
                "relance": lock_payload.get("relance"),
                "n_evenements_pays": a_run.get("meta", {}).get("n_evenements_pays"),
                "mode_decision": decision_mode,
                "modes_effectifs": sorted({str((r.get("meta") or {}).get("mode_decision")) for r in outputs
                                           if r.get("ok")}),
            },
            "plan": [{"run_id": s.run_id, **asdict(s), "role": s.role} for s in plan],
            "etalons": bench_metrics,
            "runs": run_metrics,
            "famille": family,
            "variantes": variants_out,
            "promotion": promotion,
            "controles": controls_doc,
            "essais": trial_ids,
            "precedent": previous,
            "prediction_8_3": PREDICTION_8_3,
            "journal": journal,
        }
        files: dict[str, Path] = {}
        files["metrics.json"] = _write_json(out / "metrics.json", metrics_doc)
        wk = pd.DataFrame({**{rid: s for rid, s in weekly.items()},
                           **{f"ETALON_{c}": s for c, s in bench_w.items()},
                           **{f"ETALON_EW_{capital_label(k)}": s for k, s in ew_w.items()
                              if float(k) != CAPITAL_REFERENCE}}).sort_index()
        wk.index.name = "semaine"
        wk["SEMAINE_MULTI_SEANCES"] = pd.Series(wk.index.isin(multi_weeks), index=wk.index, dtype=bool)
        wk.to_parquet(out / "weekly_returns.parquet")
        files["weekly_returns.parquet"] = out / "weekly_returns.parquet"
        nav_rows = []
        for rid, r in by_id.items():
            eq = pd.Series(r["equity"], dtype=float)
            nav_rows.append(pd.DataFrame({"date": eq.index, "serie": rid, "type": "strategie", "valeur": eq.to_numpy(),
                                          "base_t0": mt.rebase_at(eq, t0).to_numpy()}))
        for c in levels.columns:
            lv = levels[c]
            nav_rows.append(pd.DataFrame({"date": lv.index, "serie": f"ETALON_{c}", "type": "etalon",
                                          "valeur": lv.to_numpy(), "base_t0": mt.rebase_at(lv, t0).to_numpy()}))
        nav = pd.concat(nav_rows, ignore_index=True) if nav_rows else pd.DataFrame()
        nav.to_parquet(out / "nav.parquet", index=False)
        files["nav.parquet"] = out / "nav.parquet"
        tr_rows = []
        for spec in plan:
            r = by_id.get(spec.run_id)
            if r is None or not isinstance(r.get("trades"), pd.DataFrame) or not len(r["trades"]):
                continue
            t = r["trades"].copy()
            t.insert(0, "run_id", spec.run_id)
            t.insert(1, "variante", spec.variant)
            t.insert(2, "couts", spec.costs)
            t.insert(3, "capital", float(spec.capital))
            for col in ("reason",):
                if col in t.columns:
                    t[col] = t[col].astype(str)
            tr_rows.append(t)
        trades = pd.concat(tr_rows, ignore_index=True) if tr_rows else pd.DataFrame(columns=["run_id"])
        trades.to_parquet(out / "trades.parquet", index=False)
        files["trades.parquet"] = out / "trades.parquet"
        from brvm_alpha.validation.report_md import build_report

        (out / "resultats.md").write_text(build_report(_jsonable(metrics_doc)), encoding="utf-8")
        files["resultats.md"] = out / "resultats.md"
        registry.save(reg_path)
        say(f"registre enregistré : {reg_path} (N = {registry.n_trials()})")
        digest = hashlib.sha256((out / "metrics.json").read_bytes()).hexdigest()
        if code == "S1":
            lock_payload.update(statut="terminé", fin_utc=pd.Timestamp.now(tz="UTC").isoformat(),
                                duree_totale_s=round(time.perf_counter() - t_all, 1), duree_runs_s=round(runs_s, 1),
                                durees_runs_s=metrics_doc["execution"]["durees_runs_s"], essais=trial_ids,
                                n_essais_registre_apres=registry.n_trials(), sha256_metrics=digest, t0=t0)
            lk.write_lock(lock_path, lock_payload)
            files["lock.json"] = lock_path
        else:
            ctxt = {k: v for k, v in lock_payload.items() if k != "statut"}
            ctxt.update(mention=S0_MENTION, verrou="aucun (diagnostic S0)", sha256_metrics=digest, essais=trial_ids,
                        n_essais_registre_apres=registry.n_trials(), duree_totale_s=round(time.perf_counter() - t_all, 1))
            files["contexte.json"] = _write_json(out / "contexte.json", ctxt)
        say(f"terminé en {time.perf_counter() - t_all:.1f} s : {out}")
        return ValidationResult(sample=code, out_dir=out, metrics=metrics_doc, statuses=statuses, trial_ids=trial_ids,
                                duration_s=round(time.perf_counter() - t_all, 1), files=files,
                                lock=lk.read_lock(lock_path) if code == "S1" else None)

    try:
        return _rest()
    except BaseException as exc:
        if code == "S1":
            cur = lk.read_lock(lock_path) or {}
            if cur.get("statut") == "en cours":
                lock_payload.update(statut="échec", erreurs=(lock_payload.get("erreurs") or [])
                                    + [{"etape": "exécution ou analyse", "erreur": f"{exc.__class__.__name__} : {exc}"}])
                lk.write_lock(lock_path, lock_payload)
        raise
