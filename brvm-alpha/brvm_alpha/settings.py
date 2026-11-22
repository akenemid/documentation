"""Paramètres de la stratégie v1 : lecture et validation de ``configs/strategy_v1.yaml``.

Le fichier YAML reprend le §12.1 de ``docs/SPECIFICATION_STRATEGIE.md`` (v1.0 du 22/11/2026)
et les clés de l'additif v1.1 (§8.4, D1-D12, ``version: "1.1"``), validées ici (valeurs
numériques bornées, valeurs énumérées, version). La spécification le nomme ``brvm_alpha/config/strategy_v1.yaml`` ;
un dossier ``brvm_alpha/config/`` masquerait le module ``brvm_alpha/config.py``, il est
donc rangé dans ``configs/strategy_v1.yaml`` à la racine du dépôt.

Fonctions principales
---------------------
* :func:`load_strategy_config` : lit le YAML, applique d'éventuelles surcharges et
  **valide** les clés obligatoires et les valeurs numériques (:class:`StrategyConfigError`).
* :func:`apply_to_platform_config` : remplit ``CostModel``, ``TaxModel``, ``Constraints``,
  ``ExecutionModel`` et ``UniverseFilter`` de ``config.py`` à partir du YAML. Sur le
  fichier livré, le résultat est **égal** aux défauts de ``config.py`` (test de cohérence).
* :func:`cost_scenario` : ``CostModel`` d'un scénario de coûts du §7.2 (optimiste, central,
  stress, sévère).
* :func:`config_fingerprint` : empreinte SHA-256 des paramètres (à journaliser avec chaque
  essai : les paramètres sont FIGÉS avant le test S1).

Les coûts, les taxes et l'impact restent des **hypothèses** (plusieurs taux sont
[NON VÉRIFIÉ] dans la spécification) : rien ici ne garantit un résultat.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping

import pandas as pd
import yaml

from .config import Constraints, CostModel, ExecutionModel, PlatformConfig, TaxModel, UniverseFilter

__all__ = [
    "COST_SCENARIOS",
    "DEFAULT_STRATEGY_PATH",
    "SHIPPED_FILES",
    "missing_shipped_files",
    "check_shipped_files",
    "StrategyConfigError",
    "apply_to_platform_config",
    "config_fingerprint",
    "cost_scenario",
    "cost_scenarios",
    "country_cap_params",
    "get_param",
    "half_spread_default",
    "load_strategy_config",
    "mdv_floor_params",
    "n_holdings_params",
    "one_way_cost_estimate",
    "ENUM_KEYS",
    "OPEN_OVERRIDE_SECTIONS",
    "SUPPORTED_VERSIONS",
    "min_obs_prorata_params",
    "window_basis_default",
    "sector_cap_params",
    "unknown_override_keys",
    "validate_strategy_config",
]

#: Emplacement du fichier de paramètres livré avec le dépôt.
DEFAULT_STRATEGY_PATH = Path(__file__).resolve().parent.parent / "configs" / "strategy_v1.yaml"

#: Fichiers livrés avec le code, frères du paquet ``brvm_alpha`` (lus par ``__file__``) : configuration
#: figée, résultats du test S1 (variante de l'ordre de bataille, rapport) et registre des essais.
SHIPPED_FILES = ("configs/strategy_v1.yaml", "reports/validation_S1/metrics.json", "reports/trials.parquet")


def missing_shipped_files(root: str | Path | None = None, validation_dir: str | Path | None = None,
                          registry_path: str | Path | None = None) -> list[str]:
    """Fichiers livrés absents (chemins), parmi :data:`SHIPPED_FILES` ; ``validation_dir`` et
    ``registry_path`` remplacent ``reports/validation_S1`` et ``reports/trials.parquet``."""
    base = Path(root) if root is not None else Path(__file__).resolve().parent.parent
    wanted = [base / SHIPPED_FILES[0],
              (Path(validation_dir) / "metrics.json") if validation_dir is not None else base / SHIPPED_FILES[1],
              Path(registry_path) if registry_path is not None else base / SHIPPED_FILES[2]]
    return [str(p) for p in wanted if not p.is_file()]


def check_shipped_files(root: str | Path | None = None, validation_dir: str | Path | None = None,
                        registry_path: str | Path | None = None) -> None:
    """Erreur claire (:class:`~brvm_alpha.erreurs.ConfigurationError`, code de sortie 8) si un fichier livré
    manque, au lieu d'un repli silencieux (ordre de bataille rendu en « test S1 non exécuté » faute de
    ``metrics.json``). À appeler en mode embarqué, où ces fichiers sont copiés avec le code."""
    missing = missing_shipped_files(root, validation_dir, registry_path)
    if missing:
        from brvm_alpha.erreurs import ConfigurationError

        raise ConfigurationError(
            "fichier(s) livré(s) avec le code introuvable(s) : " + ", ".join(missing) + ". Copier configs/, "
            "reports/validation_S1/ et reports/trials.parquet à côté du paquet brvm_alpha (vrais fichiers).")

#: Noms canoniques des scénarios de coûts (§7.2) et alias acceptés.
COST_SCENARIOS = ("optimistic", "central", "stress", "severe")
_SCENARIO_ALIASES = {
    "optimistic": "optimistic", "optimiste": "optimistic",
    "central": "central", "centrale": "central",
    "stress": "stress",
    "severe": "severe", "sévère": "severe", "severe_stress": "severe",
}

_MISSING = object()


class StrategyConfigError(ValueError):
    """Fichier de paramètres invalide (clé manquante, valeur non numérique, incohérence)."""


# ---------------------------------------------------------------------------
# Clés obligatoires et contrôles numériques
# ---------------------------------------------------------------------------

#: Clés (chemins pointés) qui doivent exister.
REQUIRED_KEYS: tuple[str, ...] = (
    "version", "capital_fcfa_reference", "capacity_variants_fcfa",
    "data.multi_session_gap_days", "data.exclude_stats_windows", "data.eps_override",
    "data.max_abs_daily_return_guard", "data.cap_reconstruction_tolerance",
    "benchmark.primary", "benchmark.official_from",
    "universe.exclude_status", "universe.resume_buffer_sessions", "universe.min_history_sessions",
    "universe.min_obs_63", "universe.min_traded_fraction_120", "universe.min_free_float",
    "universe.mdv63_floor_fcfa", "universe.low_liquidity_tier_fcfa", "universe.max_spread_full_weight",
    "universe.stale_financials_days", "universe.min_names_for_selection",
    "signals.transform", "signals.mom6_1", "signals.lowvol", "signals.dy", "signals.quality_proxy",
    "composite.A", "composite.B", "composite.C", "composite.s2_post_ex_penalty_sd", "composite.s2_sessions",
    "learning.walk_forward",
    "portfolio.long_only", "portfolio.gross_equity", "portfolio.n_holdings", "portfolio.band",
    "portfolio.max_weight", "portfolio.min_weight", "portfolio.country_multiplier", "portfolio.sector_cap",
    "portfolio.country_cap_non_ci", "portfolio.aes_cap_multiple", "portfolio.liquidity",
    "portfolio.no_trade_band", "portfolio.max_turnover_per_rebalance", "portfolio.kelly",
    "execution.price", "execution.carry_unfilled_max_sessions", "execution.max_volume_participation",
    "execution.price_limit", "execution.limit_tolerance", "execution.settlement",
    "costs.scenarios", "costs.brvm_fee", "costs.dcbr_fee", "costs.regulator_fee", "costs.half_spread",
    "costs.capital_gains_tax",
    "events.ex_date_rule", "events.sell_deferral_to_ex", "events.S1", "events.risk_filters",
    "macro_overlay.rf_local", "macro_overlay.country_event_rules",
    "risk.relative_dd", "risk.cvar",
    "validation.samples", "validation.subperiods_S1", "validation.variants", "validation.n_trials_start",
    "validation.reject_if", "validation.candidate_if",
    # additif v1.1 (§8.4, D1-D12)
    "data.window_basis", "data.window_bound_max_stale_sessions", "data.min_obs_prorata",
    "data.cap_guard_blocking", "data.return_guard_blocking",
    "portfolio.capacity_fill", "portfolio.disciplined_index", "portfolio.core_satellite",
    "risk.relative_dd.start", "risk.relative_dd.ew_basket_top_n",
    "macro_overlay.country_events", "validation.reference_variant",
)

#: Versions du fichier de paramètres reconnues (v1.1 : additif du §8.4).
SUPPORTED_VERSIONS: tuple[str, ...] = ("1.1",)

#: Clés à valeurs énumérées (additif v1.1) : chemin -> valeurs admises.
ENUM_KEYS: dict[str, tuple[Any, ...]] = {
    "data.window_basis": ("sessions", "boc"),
    "data.cap_guard_blocking": (False, True),
    "data.return_guard_blocking": (False, True),
    "risk.relative_dd.start": ("first_investment",),
    "validation.reference_variant": ("REF",),
    "portfolio.capacity_fill.beyond_exit": (False, True),
}

#: Valeurs numériques obligatoires et bornes admises (incluses).
NUMERIC_KEYS: dict[str, tuple[float, float]] = {
    "capital_fcfa_reference": (1.0, 1e15),
    "data.multi_session_gap_days": (1, 30),
    "data.max_abs_daily_return_guard": (0.0, 10.0),
    "data.cap_reconstruction_tolerance": (0.0, 1.0),
    "data.fundamentals_fallback_lag_sessions": (0, 30),
    "universe.resume_buffer_sessions": (0, 250),
    "universe.min_history_sessions": (1, 2_000),
    "universe.min_obs_63": (1, 63),
    "universe.min_traded_fraction_120": (0.0, 1.0),
    "universe.min_free_float": (0.0, 1.0),
    "universe.low_liquidity_tier_fcfa": (0.0, 1e13),
    "universe.max_spread_full_weight": (0.0, 1.0),
    "universe.stale_financials_days": (1, 5_000),
    "universe.min_names_for_selection": (1, 200),
    "signals.transform.clip": (0.0, 10.0),
    "signals.transform.missing": (-10.0, 10.0),
    "signals.transform.min_valid_blocks": (1, 10),
    "signals.dy.max_age_months": (1, 120),
    "signals.dy.cap": (0.0, 1.0),
    "signals.mom6_1.lookback_sessions": (1, 2_000),
    "signals.mom6_1.skip_sessions": (0, 500),
    "signals.mom6_1.min_obs": (1, 2_000),
    "signals.lowvol.window_sessions": (1, 2_000),
    "signals.lowvol.min_obs": (1, 2_000),
    "signals.lowvol.fallback_window": (1, 2_000),
    "signals.lowvol.fallback_min_obs": (1, 2_000),
    "composite.s2_post_ex_penalty_sd": (-5.0, 0.0),
    "composite.s2_sessions": (0, 250),
    "learning.ic_horizon_sessions": (1, 250),
    "learning.ic_min_names": (1, 200),
    "learning.ic_cap": (0.0, 1.0),
    "learning.shrink_to_equal": (0.0, 1.0),
    "portfolio.gross_equity": (0.0, 1.0),
    "portfolio.max_weight": (0.0, 1.0),
    "portfolio.min_weight": (0.0, 1.0),
    "portfolio.aes_cap_multiple": (0.0, 10.0),
    "portfolio.liquidity.max_participation": (0.0, 1.0),
    "portfolio.liquidity.days_to_liquidate": (1, 1_000),
    "portfolio.no_trade_band": (0.0, 1.0),
    "portfolio.max_turnover_per_rebalance": (0.0, 2.0),
    "portfolio.band.enter_top_pct": (0, 100),
    "portfolio.band.exit_below_top_pct": (0, 100),
    "portfolio.kelly.fraction": (0.0, 1.0),
    "portfolio.kelly.fraction_max": (0.0, 1.0),
    "portfolio.kelly.max_gross": (0.0, 2.0),
    "execution.carry_unfilled_max_sessions": (0, 250),
    "execution.max_volume_participation": (0.0, 1.0),
    "execution.price_limit": (0.0, 1.0),
    "execution.limit_tolerance": (0.0, 0.1),
    "costs.brvm_fee": (0.0, 0.1),
    "costs.dcbr_fee": (0.0, 0.1),
    "costs.regulator_fee": (0.0, 0.1),
    "costs.capital_gains_tax": (0.0, 1.0),
    "events.sell_deferral_to_ex.max_sessions_to_ex": (0, 250),
    "events.sell_deferral_to_ex.min_net_yield": (0.0, 1.0),
    "macro_overlay.rf_local.outlier_pp": (0.0, 10.0),
    "macro_overlay.rf_local.confirm_sessions": (1, 250),
    "risk.cvar.alpha": (0.5, 1.0),
    "risk.cvar.horizon_sessions": (1, 250),
    "risk.cvar.scenarios": (1, 1e7),
    "validation.psr_min": (0.0, 1.0),
    "validation.dsr_min": (0.0, 1.0),
    "validation.n_trials_start": (1, 1e6),
    "validation.bootstrap.n_boot": (1, 1e7),
    # additif v1.1 (§8.4)
    "data.window_bound_max_stale_sessions": (0, 250),
    "data.min_obs_prorata.signal_floor": (1, 2_000),
    "data.min_obs_prorata.filter_floor": (1, 2_000),
    "portfolio.capacity_fill.max_names": (1, 200),
    "portfolio.disciplined_index.n_names": (1, 200),
    "portfolio.disciplined_index.line_base": (0.0, 1.0),
    "portfolio.disciplined_index.line_bench_cap": (0.0, 1.0),
    "portfolio.disciplined_index.bench_mult": (0.0, 10.0),
    "portfolio.disciplined_index.min_weight": (0.0, 1.0),
    "portfolio.disciplined_index.sector_floor": (0.0, 1.0),
    "portfolio.disciplined_index.sector_bench_mult": (0.0, 10.0),
    "portfolio.core_satellite.core_share": (0.0, 1.0),
    "risk.relative_dd.ew_basket_top_n": (1, 200),
}

#: Champs numériques obligatoires de chaque scénario de coûts (§7.2).
_SCENARIO_FIELDS = ("sgi", "tax", "half_spread_mult", "impact_coef", "custody", "line_fee")


def _is_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


def get_param(cfg: Mapping[str, Any], dotted: str, default: Any = _MISSING) -> Any:
    """Valeur d'un chemin pointé (``"portfolio.liquidity.max_participation"``)."""
    node: Any = cfg
    for part in dotted.split("."):
        if isinstance(node, Mapping) and part in node:
            node = node[part]
        else:
            if default is _MISSING:
                raise KeyError(dotted)
            return default
    return node


#: Sections où une surcharge peut AJOUTER des clés absentes du YAML de référence (dictionnaires
#: ouverts) : nouveaux symboles, pays, scénarios de coûts ; section ``engine`` (clés plates du
#: moteur, contrôlées par ``backtest.engine``).
OPEN_OVERRIDE_SECTIONS: tuple[str, ...] = (
    "data.eps_override",
    "portfolio.country_multiplier",
    "costs.scenarios",
    "engine",
)

#: Signaux admis comme nouvelles clés des pondérations ``composite.<variante>``.
KNOWN_SIGNALS: frozenset[str] = frozenset(
    {"ep", "dy", "mom6_1", "lowvol", "quality_proxy", "mom12_1", "mom3_1", "mom6_0", "mom12_7", "amihud"})


def unknown_override_keys(base: Mapping[str, Any], extra: Mapping[str, Any], prefix: str = "") -> list[str]:
    """Chemins pointés de ``extra`` absents de ``base`` (fautes de frappe dans une surcharge).

    Les sections de :data:`OPEN_OVERRIDE_SECTIONS` acceptent de nouvelles clés ; les poids
    ``composite.<variante>`` acceptent les signaux de :data:`KNOWN_SIGNALS`.
    """
    out: list[str] = []
    for k, v in extra.items():
        path = f"{prefix}{k}"
        if any(path == o or path.startswith(o + ".") for o in OPEN_OVERRIDE_SECTIONS):
            continue
        if not isinstance(base, Mapping) or k not in base:
            if prefix.startswith("composite.") and prefix.count(".") == 2 and str(k) in KNOWN_SIGNALS:
                continue
            out.append(path)
            continue
        if isinstance(v, Mapping) and isinstance(base[k], Mapping):
            out += unknown_override_keys(base[k], v, path + ".")
    return out


def _deep_merge(base: dict, extra: Mapping) -> dict:
    out = copy.deepcopy(base)
    for k, v in extra.items():
        if isinstance(v, Mapping) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


# ---------------------------------------------------------------------------
# Formules écrites en texte dans le YAML (le §12.1 les donne sous cette forme)
# ---------------------------------------------------------------------------

_NUM = r"([0-9][0-9_]*(?:\.[0-9]+)?)"


def _num(s: str) -> float:
    return float(s.replace("_", ""))


def mdv_floor_params(cfg: Mapping[str, Any]) -> tuple[float, float]:
    """``universe.mdv63_floor_fcfa`` = ``"max(P, f * capital)"`` -> ``(P, f)`` (U5)."""
    raw = get_param(cfg, "universe.mdv63_floor_fcfa")
    if _is_number(raw):
        return float(raw), 0.0
    m = re.fullmatch(rf"\s*max\(\s*{_NUM}\s*,\s*{_NUM}\s*\*\s*capital\s*\)\s*", str(raw))
    if not m:
        raise StrategyConfigError(f"universe.mdv63_floor_fcfa illisible : {raw!r} (attendu « max(P, f * capital) »)")
    return _num(m.group(1)), _num(m.group(2))


def window_basis_default(cfg: Mapping[str, Any]) -> str:
    """Base de comptage des fenêtres (additif v1.1, D1) : ``data.window_basis`` (``"sessions"``)."""
    return str(get_param(cfg, "data.window_basis", "sessions"))


def min_obs_prorata_params(cfg: Mapping[str, Any]) -> dict[str, int]:
    """Planchers des seuils au prorata (D1) et ancienneté maximale des bornes : ``{signal_floor,
    filter_floor, max_stale}`` (défauts 40, 20, 5)."""
    pr = get_param(cfg, "data.min_obs_prorata", {}) or {}
    return {"signal_floor": int(pr.get("signal_floor", 40)), "filter_floor": int(pr.get("filter_floor", 20)),
            "max_stale": int(get_param(cfg, "data.window_bound_max_stale_sessions", 5))}


def n_holdings_params(cfg: Mapping[str, Any]) -> dict[str, int]:
    """``portfolio.n_holdings`` = ``"clip(round(N_elig/d), lo, hi)"`` -> ``{divisor, min, max}``."""
    raw = str(get_param(cfg, "portfolio.n_holdings"))
    m = re.fullmatch(r"\s*clip\(\s*round\(\s*N_elig\s*/\s*(\d+)\s*\)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)\s*", raw)
    if not m:
        raise StrategyConfigError(f"portfolio.n_holdings illisible : {raw!r}")
    d, lo, hi = (int(g) for g in m.groups())
    if not 0 < lo <= hi:
        raise StrategyConfigError(f"portfolio.n_holdings : bornes incohérentes ({lo}, {hi})")
    return {"divisor": d, "min": lo, "max": hi}


def sector_cap_params(cfg: Mapping[str, Any]) -> dict[str, float]:
    """``portfolio.sector_cap`` = ``"max(a, min(b, m*u_s))"`` -> ``{floor, cap, mult}``."""
    raw = str(get_param(cfg, "portfolio.sector_cap"))
    m = re.fullmatch(rf"\s*max\(\s*{_NUM}\s*,\s*min\(\s*{_NUM}\s*,\s*{_NUM}\s*\*\s*u_s\s*\)\s*\)\s*", raw)
    if not m:
        raise StrategyConfigError(f"portfolio.sector_cap illisible : {raw!r}")
    floor, cap, mult = (_num(g) for g in m.groups())
    return {"floor": floor, "cap": cap, "mult": mult}


def country_cap_params(cfg: Mapping[str, Any]) -> dict[str, float]:
    """``portfolio.country_cap_non_ci`` = ``"min(a, max(b, m*max(u_c, b_c)))"`` -> ``{cap, floor, mult}``."""
    raw = str(get_param(cfg, "portfolio.country_cap_non_ci"))
    m = re.fullmatch(
        rf"\s*min\(\s*{_NUM}\s*,\s*max\(\s*{_NUM}\s*,\s*{_NUM}\s*\*\s*max\(\s*u_c\s*,\s*b_c\s*\)\s*\)\s*\)\s*", raw)
    if not m:
        raise StrategyConfigError(f"portfolio.country_cap_non_ci illisible : {raw!r}")
    cap, floor, mult = (_num(g) for g in m.groups())
    return {"cap": cap, "floor": floor, "mult": mult}


def half_spread_default(cfg: Mapping[str, Any]) -> float:
    """Demi-spread par défaut lu dans ``costs.half_spread`` (« … ; default 0.0035 »)."""
    raw = get_param(cfg, "costs.half_spread")
    if _is_number(raw):
        return float(raw)
    m = re.search(r"default\s+([0-9]*\.?[0-9]+)", str(raw))
    if not m:
        raise StrategyConfigError(f"costs.half_spread : valeur par défaut introuvable dans {raw!r}")
    return float(m.group(1))


def _settlement_switch(cfg: Mapping[str, Any]) -> str:
    """Date de passage de J+3 à J+2 (entrée ``from`` de ``execution.settlement``)."""
    for item in get_param(cfg, "execution.settlement"):
        if isinstance(item, Mapping) and "from" in item:
            return str(pd.Timestamp(item["from"]).date())
    raise StrategyConfigError("execution.settlement : aucune entrée « from » (date de passage J+3 -> J+2)")


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_strategy_config(cfg: Mapping[str, Any]) -> dict:
    """Contrôle les clés obligatoires, les valeurs numériques et quelques cohérences.

    Lève :class:`StrategyConfigError` avec la liste complète des problèmes trouvés.
    """
    if not isinstance(cfg, Mapping):
        raise StrategyConfigError("la configuration doit être un dictionnaire")
    problems: list[str] = []
    version = cfg.get("version")
    if str(version) not in SUPPORTED_VERSIONS:
        problems.append(f"version {version!r} non reconnue (attendu : {', '.join(SUPPORTED_VERSIONS)} ; additif v1.1)")
    for key, allowed in ENUM_KEYS.items():
        val = get_param(cfg, key, _MISSING)
        if val is not _MISSING and val not in allowed:
            problems.append(f"{key} = {val!r} (valeurs admises : {', '.join(map(repr, allowed))})")
    vfam = get_param(cfg, "validation.variants", None)
    if isinstance(vfam, list) and vfam and "REF" in [str(v) for v in vfam]:
        problems.append("validation.variants : REF est la référence (validation.reference_variant), hors famille")
    for key in REQUIRED_KEYS:
        if get_param(cfg, key, None) is None:
            problems.append(f"clé obligatoire absente : {key}")
    absent = object()
    for key, (lo, hi) in NUMERIC_KEYS.items():
        val = get_param(cfg, key, absent)
        if val is absent:
            if key in REQUIRED_KEYS:
                continue  # déjà signalée
            problems.append(f"valeur numérique absente : {key}")
            continue
        if not _is_number(val):
            problems.append(f"{key} doit être un nombre (lu : {val!r} ; écrire 0.001 et non 1e-3)")
        elif not lo <= float(val) <= hi:
            problems.append(f"{key} = {val} hors de l'intervalle admis [{lo}, {hi}]")
    # Pondérations des composites (somme = 1, poids >= 0).
    for name in ("A", "B", "C"):
        w = get_param(cfg, f"composite.{name}", None)
        if isinstance(w, Mapping):
            if not all(_is_number(v) and v >= 0 for v in w.values()):
                problems.append(f"composite.{name} : poids non numériques ou négatifs")
            elif abs(sum(float(v) for v in w.values()) - 1.0) > 1e-9:
                problems.append(f"composite.{name} : la somme des poids vaut {sum(w.values()):.6f} (attendu 1)")
    # Multiplicateurs pays.
    mult = get_param(cfg, "portfolio.country_multiplier", None)
    if isinstance(mult, Mapping):
        for c, v in mult.items():
            if not _is_number(v) or not 0 < float(v) <= 1.0:
                problems.append(f"portfolio.country_multiplier.{c} = {v!r} (attendu dans ]0, 1])")
    # Scénarios de coûts.
    scen = get_param(cfg, "costs.scenarios", None)
    if isinstance(scen, Mapping):
        for name in COST_SCENARIOS:
            sc = scen.get(name)
            if not isinstance(sc, Mapping):
                problems.append(f"costs.scenarios.{name} absent")
                continue
            for f in _SCENARIO_FIELDS:
                v = sc.get(f)
                if not _is_number(v) or float(v) < 0:  # type: ignore[arg-type]
                    problems.append(f"costs.scenarios.{name}.{f} = {v!r} (nombre >= 0 attendu)")
    # Échantillons : S0 et S1 disjoints, S1 avant S0.
    samples = get_param(cfg, "validation.samples", None)
    if isinstance(samples, Mapping):
        try:
            s0 = [pd.Timestamp(x) for x in samples["S0_contaminated"]]
            s1 = [pd.Timestamp(x) for x in samples["S1_preregistered"]]
            if not (s1[0] <= s1[1] < s0[0] <= s0[1]):
                problems.append("validation.samples : S1 doit précéder S0 sans chevauchement")
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            problems.append(f"validation.samples illisible ({exc})")
    for w in get_param(cfg, "data.exclude_stats_windows", []) or []:
        try:
            a, b = (pd.Timestamp(x) for x in w)
            if a > b:
                problems.append(f"data.exclude_stats_windows : fenêtre inversée {w}")
        except (TypeError, ValueError):
            problems.append(f"data.exclude_stats_windows : fenêtre illisible {w!r}")
    eps = get_param(cfg, "data.eps_override", None)
    if isinstance(eps, Mapping):
        for s, v in eps.items():
            if not _is_number(v) or float(v) <= 0:
                problems.append(f"data.eps_override.{s} = {v!r} (BPA > 0 attendu)")
    # Formules textuelles (doivent être lisibles).
    for fn in (mdv_floor_params, n_holdings_params, sector_cap_params, country_cap_params,
               half_spread_default, _settlement_switch):
        try:
            fn(cfg)
        except (StrategyConfigError, KeyError, TypeError, ValueError) as exc:
            problems.append(str(exc))
    if problems:
        raise StrategyConfigError("configuration de stratégie invalide :\n- " + "\n- ".join(problems))
    return dict(cfg)


def load_strategy_config(path: str | Path | None = None, overrides: Mapping[str, Any] | None = None) -> dict:
    """Lit ``configs/strategy_v1.yaml`` (ou ``path``), applique ``overrides`` puis valide.

    ``overrides`` est un dictionnaire imbriqué fusionné en profondeur (ex.
    ``{"portfolio": {"max_weight": 0.08}}``) : toute modification d'un paramètre FIGÉ
    doit être comptée comme un essai de plus dans le registre (spéc. §8.2).

    Une clé de surcharge **absente** du YAML de référence (faute de frappe :
    ``max_wieght``, ``portfolo``, ``carry_unfilled_max_session``…) lève
    :class:`StrategyConfigError` : elle serait sinon ignorée en silence tout en changeant
    l'empreinte de configuration (un essai fantôme gonflerait N et fausserait le DSR).
    Sections ouvertes : :data:`OPEN_OVERRIDE_SECTIONS`.
    """
    p = Path(path) if path is not None else DEFAULT_STRATEGY_PATH
    if not p.exists():
        raise FileNotFoundError(f"fichier de paramètres introuvable : {p}")
    with p.open(encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    if not isinstance(cfg, dict):
        raise StrategyConfigError(f"{p} ne contient pas un dictionnaire YAML")
    if overrides:
        if not isinstance(overrides, Mapping):
            raise StrategyConfigError("overrides doit être un dictionnaire imbriqué")
        bad = unknown_override_keys(cfg, overrides)
        if bad:
            raise StrategyConfigError(
                "clé(s) de surcharge inconnue(s) (absentes de configs/strategy_v1.yaml) : " + ", ".join(bad))
        cfg = _deep_merge(cfg, overrides)
    return validate_strategy_config(cfg)


def config_fingerprint(cfg: Mapping[str, Any]) -> str:
    """Empreinte SHA-256 (16 premiers caractères hexadécimaux) des paramètres."""
    blob = json.dumps(cfg, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Correspondance YAML -> config.py
# ---------------------------------------------------------------------------


def _scenario_name(name: str) -> str:
    key = str(name).strip().lower()
    if key not in _SCENARIO_ALIASES:
        raise KeyError(f"scénario de coûts inconnu : {name!r} (choix : {', '.join(COST_SCENARIOS)})")
    return _SCENARIO_ALIASES[key]


def cost_scenario(name: str = "central", cfg: Mapping[str, Any] | None = None) -> CostModel:
    """``CostModel`` d'un scénario du §7.2 : ``optimistic`` / ``central`` / ``stress`` / ``severe``.

    Alias français acceptés : « optimiste », « sévère ». Le demi-spread effectif d'un titre
    vaut ``half_spread_mult`` × son demi-spread mesuré (à défaut ``half_spread_default``) ;
    le multiplicateur n'est **pas** déjà appliqué à ``half_spread_default``.
    Les taux de courtage, la taxe (TVA ou TAF) et l'impact sont des **hypothèses**.
    """
    cfg = load_strategy_config() if cfg is None else cfg
    sc = get_param(cfg, f"costs.scenarios.{_scenario_name(name)}")
    costs = get_param(cfg, "costs")
    return CostModel(
        sgi_commission=float(sc["sgi"]),
        brvm_fee=float(costs["brvm_fee"]),
        dcbr_fee=float(costs["dcbr_fee"]),
        regulator_fee=float(costs["regulator_fee"]),
        vat_on_commission=float(sc["tax"]),
        impact_coef=float(sc["impact_coef"]),
        annual_custody=float(sc["custody"]),
        half_spread_default=half_spread_default(cfg),
        half_spread_mult=float(sc["half_spread_mult"]),
        account_fee_per_line_fcfa=float(sc["line_fee"]),
    )


def cost_scenarios(cfg: Mapping[str, Any] | None = None) -> dict[str, CostModel]:
    """Les quatre scénarios du §7.2, dans l'ordre optimiste, central, stress, sévère."""
    cfg = load_strategy_config() if cfg is None else cfg
    return {name: cost_scenario(name, cfg) for name in COST_SCENARIOS}


def one_way_cost_estimate(costs: CostModel, half_spread: float | None = None, participation: float = 0.0) -> float:
    """**Estimation** du coût d'un aller simple (fraction du montant), §7.2.

    ``courtage × (1 + taxe) + BRVM + DC/BR + redevance + mult × demi-spread + κ·√π``.
    Exemple central, titre médian (demi-spread 0,35 %, participation 1 %) : ≈ 1,75 %.
    """
    hs = costs.half_spread_default if half_spread is None else float(half_spread)
    pi = max(0.0, float(participation))
    return costs.rate() + costs.half_spread_mult * hs + costs.impact_coef * math.sqrt(pi)


_EXEC_PRICE = {"vwap_t_plus_1": "vwap", "close_t_plus_1": "close", "open_t_plus_1": "open",
               "vwap": "vwap", "close": "close", "open": "open"}


def apply_to_platform_config(
    cfg: Mapping[str, Any] | None = None,
    *,
    scenario: str = "central",
    base: PlatformConfig | None = None,
) -> PlatformConfig:
    """``PlatformConfig`` rempli à partir du YAML (coûts du scénario ``scenario``).

    Les champs absents du YAML (taux d'IRVM par pays, ``min_ticket_fcfa``,
    ``cash_rate_annual``, ``trading_days``…) gardent la valeur de ``base`` (par défaut
    ``PlatformConfig()``). Sur le fichier livré et le scénario central, le résultat est
    égal à ``PlatformConfig()`` : ``config.py`` et le YAML disent la même chose.
    """
    cfg = load_strategy_config() if cfg is None else validate_strategy_config(cfg)
    base = PlatformConfig() if base is None else copy.deepcopy(base)

    sc_costs = cost_scenario(scenario, cfg)
    costs = replace(sc_costs, min_ticket_fcfa=base.costs.min_ticket_fcfa)

    taxes: TaxModel = replace(base.taxes, capital_gains_tax=float(get_param(cfg, "costs.capital_gains_tax")))

    nh = n_holdings_params(cfg)
    liq = get_param(cfg, "portfolio.liquidity")
    constraints = replace(
        base.constraints,
        long_only=bool(get_param(cfg, "portfolio.long_only")),
        max_weight=float(get_param(cfg, "portfolio.max_weight")),
        min_weight=float(get_param(cfg, "portfolio.min_weight")),
        max_names=nh["max"],
        min_names=nh["min"],
        max_sector_weight=sector_cap_params(cfg)["cap"],
        max_country_weight=country_cap_params(cfg)["cap"],
        max_adv_participation=float(liq["max_participation"]),
        max_days_to_liquidate=float(liq["days_to_liquidate"]),
        cash_buffer=round(1.0 - float(get_param(cfg, "portfolio.gross_equity")), 12),
        no_trade_band=float(get_param(cfg, "portfolio.no_trade_band")),
        max_turnover_per_rebalance=float(get_param(cfg, "portfolio.max_turnover_per_rebalance")),
    )

    price = str(get_param(cfg, "execution.price"))
    if price not in _EXEC_PRICE:
        raise StrategyConfigError(f"execution.price inconnu : {price!r}")
    carry = int(get_param(cfg, "execution.carry_unfilled_max_sessions"))
    execution: ExecutionModel = replace(
        base.execution,
        price=_EXEC_PRICE[price],
        price_limit=float(get_param(cfg, "execution.price_limit")),
        limit_tolerance=float(get_param(cfg, "execution.limit_tolerance")),
        max_volume_participation=float(get_param(cfg, "execution.max_volume_participation")),
        carry_unfilled=carry > 0,
        max_carry_sessions=carry,
        settlement_switch_date=_settlement_switch(cfg),
    )

    floor, frac = mdv_floor_params(cfg)
    universe: UniverseFilter = replace(
        base.universe,
        min_history_days=int(get_param(cfg, "universe.min_history_sessions")),
        min_returns_63=int(get_param(cfg, "universe.min_obs_63")),
        min_traded_fraction=float(get_param(cfg, "universe.min_traded_fraction_120")),
        min_median_value_fcfa=floor,
        mdv_capital_fraction=frac,
        low_liquidity_tier_fcfa=float(get_param(cfg, "universe.low_liquidity_tier_fcfa")),
        max_spread_full_weight=float(get_param(cfg, "universe.max_spread_full_weight")),
        min_float=float(get_param(cfg, "universe.min_free_float")),
        min_names_for_selection=int(get_param(cfg, "universe.min_names_for_selection")),
        stale_financials_days=int(get_param(cfg, "universe.stale_financials_days")),
        exclude_suspended="suspended" in list(get_param(cfg, "universe.exclude_status")),
    )

    return replace(
        base,
        costs=costs,
        taxes=taxes,
        constraints=constraints,
        execution=execution,
        universe=universe,
        capital_fcfa=float(get_param(cfg, "capital_fcfa_reference")),
    )
