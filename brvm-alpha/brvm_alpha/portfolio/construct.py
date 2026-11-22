"""Construction de portefeuille sous contraintes pour la BRVM (long-only).

Fonctions principales :

* :func:`build_portfolio` — poids cibles selon trois méthodes :

  - ``"mv_alpha"`` : moyenne-variance avec coûts (Markowitz 1952 ; Grinold &
    Kahn 2000, *Active Portfolio Management*, ch. 14-16) ;
  - ``"hrp_tilt"`` : HRP (López de Prado 2016) incliné par ``exp(γ z_α)`` ;
  - ``"equal"`` : équipondération des meilleurs titres (DeMiguel, Garlappi &
    Uppal 2009 : la référence 1/N est difficile à battre hors échantillon).

  Toutes respectent : long-only, ``Σw = 1 − cash_buffer`` (si réalisable),
  ``w_i ≤ max_weight``, plafond de liquidité ``w_i ≤ liquidity_i``, plafonds
  secteur / pays, au plus ``max_names`` lignes, toute ligne non nulle
  ``≥ min_weight``. « Si réalisable » est vérifié exactement : lorsque les
  meilleurs scores sont trop peu liquides, la sélection est résolue par
  programmation linéaire en nombres entiers (cardinalité + poids
  semi-continus) plutôt que gloutonnement.
* :func:`liquidity_caps` — poids maximal par titre déduit de la valeur
  quotidienne moyenne échangée (ADV), du capital et du délai de sortie.
* :func:`average_daily_value` — ADV sans biais d'anticipation.
* :func:`fractional_kelly_scale` — exposition globale par Kelly fractionnel.
* :func:`apply_no_trade_band`, :func:`cap_turnover` — réduction du turnover.
* :func:`to_lots` — conversion en nombres entiers de titres.
* :func:`grinold_alpha` — conversion score → rendement espéré
  (« alpha = IC × volatilité × score », Grinold 1994).
* :func:`constraint_violations` — audit des contraintes d'un portefeuille.

Construction **v1** (``docs/SPECIFICATION_STRATEGIE.md`` §4.2, §6, §9.1, §11
« portfolio.* » ; paramètres par défaut identiques à la spécification, dict
optionnel accepté, voir :data:`PORTFOLIO_V1_DEFAULTS`) :

* :func:`n_holdings` — ``clip(round(N_élig/3), 12, 20)`` ; mode repli si N < 15 ;
* :func:`select_with_band` — bande 30/50 (entrée dans les 30 % supérieurs, sortie
  sous les 50 % supérieurs), déterministe ;
* :func:`line_caps` — plafond par ligne 10 % × pays × U6 × U7 × R4/R11/R12,
  plancher 2 % ;
* :func:`sector_caps`, :func:`country_caps`, :func:`aes_caps` (siège **et**
  exposition λ), :func:`liquidity_caps`, poche de liquidités 2 % ;
* :func:`equal_weight_with_caps` — équipondération projetée exactement sur toutes
  les contraintes (remplissage progressif, repli PL lexicographique) ;
* :func:`target_portfolio` — enchaîne le tout et renvoie ``(poids, diagnostics)`` ;
* variantes G (:func:`hrp_tilt_rates`, :func:`weekly_covariance`) et H
  (:func:`mv_alpha_weights`, Kelly fractionnel sur les poids **actifs**).

Unités : dans ``"mv_alpha"``, ``alpha``, ``cov`` et ``tcost`` doivent être
exprimés sur le **même horizon** (p. ex. rendement espéré annualisé, covariance
annualisée et coût aller simple amorti sur l'année, c.-à-d. coût × nombre de
rotations par an). ``risk_aversion = 5`` est calibré pour des grandeurs
annualisées.

Contexte BRVM : pas de vente à découvert, ±7,5 %/jour, liquidité très
hétérogène (quelques titres concentrent l'essentiel des volumes) ; le
plafond de liquidité est donc souvent la contrainte la plus active.
"""

from __future__ import annotations

import copy
import math
import warnings
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
import pandas as pd
from scipy import optimize

from brvm_alpha.config import Constraints, CostModel
from brvm_alpha.portfolio.risk import hrp_weights, ledoit_wolf_cov

__all__ = [  # noqa: RUF022 — regroupé par thème (historique, puis construction v1)
    "build_portfolio",
    "liquidity_caps",
    "average_daily_value",
    "fractional_kelly_scale",
    "apply_no_trade_band",
    "cap_turnover",
    "to_lots",
    "grinold_alpha",
    "constraint_violations",
    # construction v1 (spécification §4.2, §6, §9.1)
    "PORTFOLIO_V1_DEFAULTS",
    "SPEC_COUNTRY_MULTIPLIER",
    "SPEC_AES_COUNTRIES",
    "BandSelection",
    "GroupCap",
    "portfolio_params",
    "portfolio_params_from_config",
    "n_holdings",
    "is_fallback",
    "score_ranks",
    "select_with_band",
    "line_caps",
    "sector_caps",
    "country_caps",
    "aes_caps",
    "build_group_caps",
    "reference_weights_pit",
    "equal_weight_with_caps",
    "audit_weights",
    "weekly_returns",
    "weekly_covariance",
    "hrp_tilt_rates",
    "central_one_way_cost",
    "mv_alpha_weights",
    "target_portfolio",
]

Method = Literal["mv_alpha", "hrp_tilt", "equal"]

_FEAS_TOL = 1e-9  # tolérance de faisabilité interne
_NA_GROUP = "__NA__"


# ---------------------------------------------------------------------------
# Liquidité
# ---------------------------------------------------------------------------


def average_daily_value(
    value: pd.DataFrame,
    window: int = 60,
    asof: pd.Timestamp | None = None,
    stat: Literal["mean", "median"] = "mean",
    min_periods: int | None = None,
) -> pd.Series:
    """Valeur quotidienne échangée moyenne (ADV, FCFA) sur ``window`` séances.

    Les séances sans échange comptent pour 0 (NaN → 0) : à la BRVM, la
    liquidité réellement disponible est la moyenne **toutes séances
    confondues**, pas la moyenne des seules séances actives. Seules les
    séances ``≤ asof`` sont utilisées (pas de biais d'anticipation).

    Parameters
    ----------
    value
        Panel large (date × symbole) de valeurs échangées en FCFA.
    window
        Nombre de séances (60 ≈ 3 mois).
    asof
        Date d'évaluation (défaut : dernière date du panel).
    stat
        ``"mean"`` ou ``"median"`` (la médiane est plus prudente mais vaut 0
        pour un titre échangé moins d'une séance sur deux).
    min_periods
        Séances minimales disponibles (défaut : ``window // 2``) ; sinon NaN.
    """
    hist = value.sort_index()
    if asof is not None:
        hist = hist.loc[: pd.Timestamp(asof)]
    hist = hist.iloc[-window:].astype(float).fillna(0.0).clip(lower=0.0)
    need = window // 2 if min_periods is None else min_periods
    out = hist.mean() if stat == "mean" else hist.median()
    if len(hist) < need:
        out[:] = np.nan
    return out.rename("adv_value")


def liquidity_caps(
    adv_value: pd.Series,
    capital: float,
    max_adv_participation: float | None = None,
    max_days_to_liquidate: float | None = None,
) -> pd.Series:
    """Poids maximal par titre compatible avec la liquidité.

    Une position de valeur ``V_i`` doit pouvoir être soldée en
    ``D = max_days_to_liquidate`` séances sans dépasser une participation
    ``π = max_adv_participation`` du volume quotidien moyen :

    ``V_i ≤ π · ADV_i · D``  ⇒  ``w_i^max = min(1, π · ADV_i · D / capital)``.

    (Cadre de Almgren & Chriss 2000 et de la règle de « days-to-liquidate »
    usuelle en gestion de petites capitalisations.) ADV manquante ou ≤ 0 →
    poids maximal 0 (titre non détenable). Valeurs par défaut :
    :class:`~brvm_alpha.config.Constraints`.

    Parameters
    ----------
    adv_value
        ADV par titre en FCFA (voir :func:`average_daily_value`).
    capital
        Capital du portefeuille en FCFA.
    """
    if capital <= 0:
        raise ValueError("capital doit être > 0")
    defaults = Constraints()
    part = defaults.max_adv_participation if max_adv_participation is None else max_adv_participation
    days = defaults.max_days_to_liquidate if max_days_to_liquidate is None else max_days_to_liquidate
    if part < 0 or days < 0:
        raise ValueError("participation et délai doivent être >= 0")
    adv = pd.to_numeric(adv_value, errors="coerce").astype(float)
    adv = adv.where(np.isfinite(adv) & (adv > 0), 0.0)
    return (adv * part * days / capital).clip(0.0, 1.0).rename("liquidity_cap")


# ---------------------------------------------------------------------------
# Kelly, alpha, turnover
# ---------------------------------------------------------------------------


def grinold_alpha(scores: pd.Series, volatility: pd.Series, ic: float = 0.05) -> pd.Series:
    """Rendement résiduel espéré à partir d'un score : ``α_i = IC · σ_i · z_i``.

    Grinold (1994), *Alpha is Volatility Times IC Times Score*, J. Portfolio
    Management 20(4). ``scores`` doit être un z-score transversal (moyenne 0,
    écart-type 1), ``volatility`` la volatilité sur l'horizon de l'alpha, ``ic``
    la corrélation (Spearman) attendue entre score et rendement futur.
    """
    vol = volatility.reindex(scores.index).astype(float)
    return (ic * vol * scores.astype(float)).rename("alpha")


def fractional_kelly_scale(
    expected_excess: float | pd.Series | np.ndarray,
    cov: float | pd.DataFrame | np.ndarray,
    fraction: float = 0.25,
    max_gross: float = 1.0,
    weights: pd.Series | np.ndarray | None = None,
    *,
    normalize: bool = True,
) -> float:
    """Exposition globale selon le critère de Kelly fractionnel.

    Le critère de Kelly (Kelly 1956 ; Thorp 2006 ; MacLean, Thorp & Ziemba
    2011) maximise la croissance logarithmique espérée ; en temps continu,
    ``g(L) = L μ − ½ L² σ²`` d'où ``L* = μ / σ²`` (Merton 1969). Le rapport est
    invariant à l'horizon (μ et σ² doivent simplement être sur le même).

    * scalaires : ``L* = μ / σ²`` ;
    * vecteurs + ``weights`` (direction du portefeuille, normalisée à somme 1) :
      ``L* = wᵀμ / wᵀΣw`` ;
    * vecteurs sans ``weights`` : Kelly long-only
      ``x* = argmax_{x ≥ 0} μᵀx − ½ xᵀΣx`` (moindres carrés non négatifs sur
      la factorisation de Cholesky ``Σ = LLᵀ`` :
      ``min_{x≥0} ‖Lᵀx − L⁻¹μ‖²``), puis ``L* = 1ᵀx*``.

    Avec ``normalize=False`` (et ``weights`` fourni), la direction ``w`` n'est pas
    ramenée à une somme de 1 : c'est le cas des **poids actifs** ``w − w_EW`` de la
    variante H (spéc. §6), de somme ≈ 0. ``L* = wᵀμ / wᵀΣw`` est alors le
    multiple optimal du pari actif ``w`` lui-même.

    Résultat : ``clip(fraction · L*, 0, max_gross)``. Le Kelly fractionnel
    (``fraction = ¼`` par défaut) protège contre l'erreur d'estimation de μ,
    qui domine en pratique : à ½-Kelly, on conserve 75 % de la croissance pour
    la moitié de la volatilité. Long-only : exposition nulle si l'espérance est
    négative.
    """
    if fraction <= 0:
        raise ValueError("fraction doit être > 0")
    if max_gross < 0:
        raise ValueError("max_gross doit être >= 0")
    if np.isscalar(expected_excess) or np.ndim(expected_excess) == 0:
        mu = float(np.asarray(expected_excess, float))
        var = float(np.asarray(cov, float).reshape(-1)[0]) if np.ndim(cov) else float(cov)  # type: ignore[arg-type]
        if not np.isfinite(mu) or not np.isfinite(var) or var <= 0 or mu <= 0:
            return 0.0
        return float(np.clip(fraction * mu / var, 0.0, max_gross))

    if isinstance(expected_excess, pd.Series):
        names = expected_excess.index
        mu_v = expected_excess.astype(float).to_numpy()
        if isinstance(cov, pd.DataFrame):
            sig = cov.loc[names, names].to_numpy(dtype=float)
        else:
            sig = np.asarray(cov, float)
        if weights is not None:
            w_v = (
                weights.reindex(names).fillna(0.0).to_numpy(float)
                if isinstance(weights, pd.Series)
                else np.asarray(weights, float)
            )
        else:
            w_v = None
    else:
        mu_v = np.asarray(expected_excess, float).reshape(-1)
        sig = cov.to_numpy(dtype=float) if isinstance(cov, pd.DataFrame) else np.asarray(cov, float)
        w_v = None if weights is None else np.asarray(
            weights.to_numpy(float) if isinstance(weights, pd.Series) else weights, float
        )
    sig = 0.5 * (sig + sig.T)
    if not (np.all(np.isfinite(mu_v)) and np.all(np.isfinite(sig))):
        raise ValueError("fractional_kelly_scale : entrées non finies")

    if w_v is not None:
        if normalize:
            tot = w_v.sum()
            if tot <= 0:
                return 0.0
            w_v = w_v / tot
        mu_p = float(w_v @ mu_v)
        var_p = float(w_v @ sig @ w_v)
        if var_p <= 0 or mu_p <= 0:
            return 0.0
        return float(np.clip(fraction * mu_p / var_p, 0.0, max_gross))

    n = len(mu_v)
    jitter = 0.0
    scale = max(float(np.max(np.abs(np.diag(sig)))), 1e-300)
    for _ in range(8):
        try:
            chol = np.linalg.cholesky(sig + jitter * np.eye(n))
            break
        except np.linalg.LinAlgError:
            jitter = scale * 1e-10 if jitter == 0 else jitter * 100
    else:
        raise ValueError("fractional_kelly_scale : covariance non définie positive")
    b = np.linalg.solve(chol, mu_v)
    x, _ = optimize.nnls(chol.T, b)
    return float(np.clip(fraction * x.sum(), 0.0, max_gross))


def _union_index(first: pd.Index, second: pd.Index) -> pd.Index:
    """Union d'index conservant l'ordre de ``first`` puis les nouveaux de ``second``."""
    return first.append(second.difference(first, sort=False))


def apply_no_trade_band(
    target: pd.Series,
    prev: pd.Series | None,
    band: float | None = None,
    *,
    exit_zero_targets: bool = True,
) -> pd.Series:
    """Bande de non-transaction : on ne traite pas si ``|w_cible − w_préc| < band``.

    Règle de « no-trade region » (Davis & Norman 1990 ; Leland 2000) : avec
    des coûts proportionnels, il est optimal de ne rééquilibrer que lorsque
    l'écart à la cible dépasse un seuil. Ici :

    ``w_i = w_préc,i`` si ``|w_cible,i − w_préc,i| < band``, sinon ``w_cible,i``.

    Avec ``exit_zero_targets``, une ligne dont la cible est nulle est toujours
    soldée (sortie d'univers, signal annulé). Si les lignes conservées font
    dépasser le budget ``Σ w_cible``, l'excédent est retiré proportionnellement
    des lignes traitées (qui restent ≤ leur cible, donc sous leurs plafonds),
    puis, à défaut, de toutes les lignes. Les lignes conservées à leur poids
    précédent ne sont pas re-contrôlées vis-à-vis des plafonds de groupe :
    appliquer :func:`constraint_violations` si les contraintes ont changé.
    """
    band = Constraints().no_trade_band if band is None else float(band)
    if prev is None:
        return target.astype(float).fillna(0.0).copy()
    idx = _union_index(target.index, prev.index)
    t = target.reindex(idx).astype(float).fillna(0.0).clip(lower=0.0)
    p = prev.reindex(idx).astype(float).fillna(0.0).clip(lower=0.0)
    hold = (t - p).abs() < band
    if exit_zero_targets:
        hold &= ~((t <= 0.0) & (p > 0.0))
    w = p.where(hold, t)
    budget = float(t.sum())
    excess = float(w.sum()) - budget
    if excess > _FEAS_TOL:
        traded = (~hold) & (w > 0)
        tot = float(w[traded].sum())
        if tot > 0:
            cut = min(excess, tot)
            w[traded] = w[traded] * (1.0 - cut / tot)
            excess -= cut
        if excess > _FEAS_TOL:
            w = w * (budget / float(w.sum()))
    return w.rename(target.name)


def cap_turnover(target: pd.Series, prev: pd.Series | None, max_turnover: float | None = None) -> pd.Series:
    """Limite le turnover simple ``TO = ½ Σ|w_cible − w_préc|``.

    ``w = w_préc + θ (w_cible − w_préc)`` avec ``θ = min(1, TO_max / TO)``.
    Combinaison convexe de deux portefeuilles : toute contrainte linéaire
    satisfaite par les deux (budget, plafonds, secteurs) l'est aussi.
    """
    max_to = Constraints().max_turnover_per_rebalance if max_turnover is None else max_turnover
    if prev is None:
        prev = pd.Series(0.0, index=target.index)
    idx = _union_index(target.index, prev.index)
    t = target.reindex(idx).astype(float).fillna(0.0)
    p = prev.reindex(idx).astype(float).fillna(0.0)
    turnover = 0.5 * float((t - p).abs().sum())
    if turnover <= max_to or turnover <= 0:
        return t.rename(target.name)
    theta = max_to / turnover
    return (p + theta * (t - p)).rename(target.name)


# ---------------------------------------------------------------------------
# Arrondi en titres
# ---------------------------------------------------------------------------


def to_lots(
    weights: pd.Series,
    prices: pd.Series,
    capital: float,
    *,
    lot_size: int | pd.Series = 1,
    max_weight: float | pd.Series | None = None,
) -> pd.Series:
    """Convertit des poids en nombres entiers de titres (quotité 1 à la BRVM).

    1. ``q_i = ⌊ w_i · C / (P_i · lot_i) ⌋ · lot_i`` (jamais au-dessus de la
       cible) ;
    2. reliquat ``R = C · Σw − Σ q_i P_i`` réparti par la méthode des plus
       forts restes (Hamilton) : par fraction de lot manquante décroissante,
       chaque titre reçoit au plus un lot supplémentaire si ``P_i · lot_i ≤ R``
       et si ``max_weight`` (plafond, p. ex. ``min(max_weight, liquidité)``)
       n'est pas dépassé.

    Le montant investi ne dépasse jamais ``C · Σw`` (la poche de liquidité est
    préservée). Prix manquant ou ≤ 0 → 0 titre.

    Returns
    -------
    pandas.Series
        Nombres de titres (``int64``), même index que ``weights``.
    """
    if capital <= 0:
        raise ValueError("capital doit être > 0")
    w = weights.astype(float).fillna(0.0).clip(lower=0.0)
    px = prices.reindex(w.index).astype(float)
    lot = (
        lot_size.reindex(w.index).fillna(1).astype(float)
        if isinstance(lot_size, pd.Series)
        else pd.Series(float(lot_size), index=w.index)
    )
    if np.any(lot.to_numpy() < 1):
        raise ValueError("lot_size doit être >= 1")
    ok = np.isfinite(px) & (px > 0) & (w > 0)
    w = w.where(ok, 0.0)
    px_v = px.where(ok, 1.0).to_numpy()
    lot_v = lot.to_numpy()
    target_val = w.to_numpy() * capital
    lot_cost = px_v * lot_v
    n_lots = np.floor(target_val / lot_cost + 1e-9)
    n_lots = np.where(n_lots * lot_cost > target_val + 1e-6, n_lots - 1, n_lots)
    n_lots = np.maximum(n_lots, 0.0)
    shares = n_lots * lot_v

    if max_weight is None:
        cap_val = np.full(len(w), np.inf)
    elif isinstance(max_weight, pd.Series):
        cap_val = max_weight.reindex(w.index).astype(float).fillna(np.inf).to_numpy() * capital
    else:
        cap_val = np.full(len(w), float(max_weight) * capital)

    cash = float(target_val.sum() - (shares * px_v).sum())
    deficit = target_val - shares * px_v
    frac = np.where(ok.to_numpy(), deficit / lot_cost, -np.inf)
    names = np.asarray(w.index.astype(str))
    order = np.lexsort((names, -frac))
    for i in order:
        if not np.isfinite(frac[i]) or deficit[i] <= 1e-9:
            continue
        if lot_cost[i] <= cash + 1e-9 and (shares[i] * px_v[i] + lot_cost[i]) <= cap_val[i] + 1e-6:
            shares[i] += lot_v[i]
            cash -= lot_cost[i]
    return pd.Series(shares.astype(np.int64), index=w.index, name="shares")


# ---------------------------------------------------------------------------
# Outils internes : faisabilité, projection
# ---------------------------------------------------------------------------


def _group_matrix(
    names: pd.Index,
    labels: pd.Series | None,
    cap: float,
    budget: float,
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Matrice d'appartenance (groupes × titres) et plafonds associés.

    Les étiquettes manquantes sont regroupées dans un groupe « __NA__ »
    plafonné comme les autres (prudence). Un plafond ≥ budget n'est jamais
    contraignant et n'est pas ajouté.
    """
    if labels is None or cap >= budget - _FEAS_TOL:
        return np.zeros((0, len(names))), np.zeros(0), []
    lab = labels.reindex(names).astype(object)
    lab = lab.where(lab.notna(), _NA_GROUP).astype(str).to_numpy()
    uniq = sorted(set(lab))
    g = np.array([[1.0 if v == u else 0.0 for v in lab] for u in uniq])
    return g.reshape(len(uniq), len(names)), np.full(len(uniq), float(cap)), uniq


def _max_investable(
    lower: np.ndarray,
    upper: np.ndarray,
    g: np.ndarray,
    caps: np.ndarray,
) -> float | None:
    """Investissement maximal ``max 1ᵀw`` s.c. ``l ≤ w ≤ u``, ``Gw ≤ c`` (PL HiGHS).

    Renvoie ``None`` si l'ensemble est vide (bornes inférieures incompatibles).
    """
    n = len(upper)
    if n == 0:
        return 0.0
    if np.any(lower > upper + _FEAS_TOL):
        return None
    if g.shape[0] and np.any(g @ lower > caps + _FEAS_TOL):
        return None
    if g.shape[0] == 0:
        return float(upper.sum())
    res = optimize.linprog(
        c=-np.ones(n),
        A_ub=g,
        b_ub=caps,
        bounds=list(zip(lower, upper)),
        method="highs",
    )
    if res.status != 0:
        return None
    return float(-res.fun)


def _enforce_caps(w: np.ndarray, lower: np.ndarray, upper: np.ndarray, g: np.ndarray, caps: np.ndarray) -> np.ndarray:
    """Impose bornes et plafonds de groupe par réduction proportionnelle à ``w − l``.

    Les lignes de ``g`` peuvent porter des coefficients positifs quelconques (p. ex.
    l'exposition économique λ du bloc AES) : on impose alors ``g_k · w ≤ c_k``. Pour
    une ligne d'appartenance (coefficients 0/1), le calcul est inchangé.
    """
    w = np.clip(w, lower, upper)
    for k in range(g.shape[0]):
        idx = np.flatnonzero(g[k])
        coef = g[k, idx]
        binary = bool(np.all(coef == 1.0))
        s = w[idx].sum() if binary else float(coef @ w[idx])
        if s > caps[k]:
            lo = lower[idx]
            ex = w[idx] - lo
            tot = ex.sum() if binary else float(coef @ ex)
            room = max(caps[k] - (lo.sum() if binary else float(coef @ lo)), 0.0)
            w[idx] = lo + (ex * (room / tot) if tot > 0 else 0.0)
    return w


def _waterfill(
    w0: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
    budget: float,
    g: np.ndarray,
    caps: np.ndarray,
    max_iter: int = 500,
) -> np.ndarray:
    """Projection itérative (« water-filling ») sur les contraintes.

    Répète : (a) imposition des bornes ``l ≤ w ≤ u`` et des plafonds de groupe
    (réduction proportionnelle de l'excédent au-dessus du plancher) ;
    (b) si ``Σw > B`` : réduction proportionnelle de ``w − l`` ; si ``Σw < B`` :
    redistribution du déficit proportionnellement aux poids courants parmi les
    titres ayant de la marge (titre et groupes non saturés), chaque ajout étant
    borné par la marge du titre puis par la marge de chacun de ses groupes. À
    chaque tour, au moins un titre ou un groupe est saturé, d'où la
    convergence en au plus ``n + k + 1`` tours. Le résultat respecte toujours
    bornes et plafonds et ``Σw ≤ B``.
    """
    w = _enforce_caps(np.asarray(w0, float).copy(), lower, upper, g, caps)
    groups = [np.flatnonzero(g[k]) for k in range(g.shape[0])]
    for _ in range(max_iter):
        s = w.sum()
        gap = budget - s
        if gap < -_FEAS_TOL * 1e-3:
            ex = w - lower
            tot = ex.sum()
            if tot <= 0:
                break
            w = lower + ex * max(1.0 - (-gap) / tot, 0.0)
            break
        if gap <= _FEAS_TOL * 1e-3:
            break
        head = upper - w
        gslack = caps - g @ w if g.shape[0] else np.zeros(0)
        blocked = (g.T @ (gslack <= 1e-15).astype(float)) > 0 if g.shape[0] else np.zeros(len(w), bool)
        elig = (head > 1e-15) & ~blocked
        if not elig.any():
            break
        base = np.where(elig, w, 0.0)
        if base.sum() <= 1e-15:
            base = elig.astype(float)
        add = np.minimum(gap * base / base.sum(), np.where(elig, head, 0.0))
        for k, idx in enumerate(groups):
            coef = g[k, idx]
            sa = add[idx].sum() if bool(np.all(coef == 1.0)) else float(coef @ add[idx])
            if sa > gslack[k] and sa > 0:
                add[idx] *= max(gslack[k], 0.0) / sa
        if add.sum() <= 1e-16:
            break
        w = w + add
    w = _enforce_caps(w, lower, upper, g, caps)
    if w.sum() > budget:
        ex = w - lower
        tot = ex.sum()
        if tot > 0:
            w = lower + ex * max(1.0 - (w.sum() - budget) / tot, 0.0)
    return w


def _lp_project(
    v: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
    budget: float,
    g: np.ndarray,
    caps: np.ndarray,
) -> np.ndarray | None:
    """Projection L1 exacte (PL) : ``min ‖w − v‖₁`` s.c. contraintes et ``Σw = B``."""
    n = len(v)
    eye = np.eye(n)
    c = np.concatenate([np.zeros(n), np.ones(n)])
    a_ub = [np.hstack([eye, -eye]), np.hstack([-eye, -eye])]
    b_ub = [v, -v]
    if g.shape[0]:
        a_ub.append(np.hstack([g, np.zeros((g.shape[0], n))]))
        b_ub.append(caps)
    res = optimize.linprog(
        c,
        A_ub=np.vstack(a_ub),
        b_ub=np.concatenate(b_ub),
        A_eq=np.concatenate([np.ones(n), np.zeros(n)])[None, :],
        b_eq=[budget],
        bounds=list(zip(lower, upper)) + [(0.0, None)] * n,
        method="highs",
    )
    if res.status != 0:
        return None
    return np.clip(res.x[:n], lower, upper)


def _finalize(
    w0: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
    budget: float,
    g: np.ndarray,
    caps: np.ndarray,
) -> np.ndarray:
    """Projection garantissant les contraintes et le budget (si réalisable)."""
    w = _waterfill(w0, lower, upper, budget, g, caps)
    if abs(w.sum() - budget) > 1e-10:
        cap = _max_investable(lower, upper, g, caps)
        if cap is not None and cap >= budget - 1e-12:
            alt = _lp_project(w, lower, upper, budget, g, caps)
            if alt is not None:
                w = _waterfill(alt, lower, upper, budget, g, caps)
    return w


def _max_violation(
    w: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
    budget: float,
    g: np.ndarray,
    caps: np.ndarray,
) -> float:
    """Violation maximale des contraintes (bornes, groupes, budget)."""
    v = [float(np.max(lower - w, initial=0.0)), float(np.max(w - upper, initial=0.0)), abs(float(w.sum()) - budget)]
    if g.shape[0]:
        v.append(float(np.max(g @ w - caps, initial=0.0)))
    return max(v)


# ---------------------------------------------------------------------------
# Optimisation moyenne-variance avec coûts
# ---------------------------------------------------------------------------


@dataclass
class _MVProblem:
    """Données d'un problème moyenne-variance restreint à un ensemble de titres."""

    alpha: np.ndarray
    sigma: np.ndarray
    lower: np.ndarray
    upper: np.ndarray
    budget: float
    g: np.ndarray
    caps: np.ndarray
    prev: np.ndarray
    risk_aversion: float
    tcost: float

    def objective(self, w: np.ndarray) -> float:
        """``αᵀw − (λ/2) wᵀΣw − κ ‖w − w_préc‖₁``."""
        return float(
            self.alpha @ w
            - 0.5 * self.risk_aversion * w @ self.sigma @ w
            - self.tcost * np.abs(w - self.prev).sum()
        )


def _solve_mv(pb: _MVProblem, x0: np.ndarray) -> tuple[np.ndarray, str]:
    """Résout le QP moyenne-variance avec coûts L1 (SLSQP, puis trust-constr).

    Reformulation lisse du terme ``κ‖w − w_p‖₁`` (Lobo, Fazel & Boyd 2007) :
    pour les titres non détenus (``w_p,i = 0``), ``|w_i − 0| = w_i`` (long-only)
    est linéaire ; pour les titres détenus ``H``, variables auxiliaires
    ``t_i ≥ |w_i − w_p,i|`` : ``t_i − w_i ≥ −w_p,i`` et ``t_i + w_i ≥ w_p,i``.

    ``max αᵀw − (λ/2) wᵀΣw − κ (Σ_{i∉H} w_i + Σ_{i∈H} t_i)``
    s.c. ``Σw = B``, ``Gw ≤ c``, ``l ≤ w ≤ u``, ``t ≥ 0``.

    La meilleure solution réalisable parmi {SLSQP, trust-constr, point de
    départ heuristique} est retenue (repli robuste).
    """
    n = len(pb.alpha)
    held = np.flatnonzero(pb.prev > 0) if pb.tcost > 0 else np.zeros(0, int)
    h = len(held)
    lin = pb.alpha - (pb.tcost if pb.tcost > 0 else 0.0) * (pb.prev <= 0)
    scale = max(
        float(np.max(np.abs(pb.alpha), initial=0.0)),
        pb.risk_aversion * float(np.max(np.diag(pb.sigma), initial=0.0)),
        pb.tcost,
        1e-12,
    )
    lam_sig = pb.risk_aversion * pb.sigma

    def f(x: np.ndarray) -> float:
        w = x[:n]
        val = lin @ w - 0.5 * w @ lam_sig @ w - (pb.tcost * x[n:].sum() if h else 0.0)
        return -val / scale

    def grad(x: np.ndarray) -> np.ndarray:
        w = x[:n]
        gw = -(lin - lam_sig @ w) / scale
        if h:
            return np.concatenate([gw, np.full(h, pb.tcost / scale)])
        return gw

    def hess(x: np.ndarray) -> np.ndarray:
        hm = np.zeros((n + h, n + h))
        hm[:n, :n] = lam_sig / scale
        return hm

    # Matrice des contraintes linéaires A x (lb ≤ A x ≤ ub)
    rows, lbs, ubs = [], [], []
    rows.append(np.concatenate([np.ones(n), np.zeros(h)]))
    lbs.append(pb.budget)
    ubs.append(pb.budget)
    for k in range(pb.g.shape[0]):
        rows.append(np.concatenate([pb.g[k], np.zeros(h)]))
        lbs.append(-np.inf)
        ubs.append(pb.caps[k])
    for j, i in enumerate(held):
        r1 = np.zeros(n + h)
        r1[i], r1[n + j] = -1.0, 1.0
        rows.append(r1)
        lbs.append(-pb.prev[i])
        ubs.append(np.inf)
        r2 = np.zeros(n + h)
        r2[i], r2[n + j] = 1.0, 1.0
        rows.append(r2)
        lbs.append(pb.prev[i])
        ubs.append(np.inf)
    a_mat = np.vstack(rows)
    lb_v, ub_v = np.array(lbs), np.array(ubs)
    bounds_lo = np.concatenate([pb.lower, np.zeros(h)])
    bounds_hi = np.concatenate([pb.upper, np.full(h, np.inf)])
    xs0 = np.concatenate([x0, np.abs(x0[held] - pb.prev[held])]) if h else x0.copy()

    candidates: list[tuple[np.ndarray, str]] = [(x0.copy(), "heuristic")]

    eq_mask = np.isclose(lb_v, ub_v)
    lo_mask = np.isfinite(lb_v) & ~eq_mask
    up_mask = np.isfinite(ub_v) & ~eq_mask
    slsqp_cons = [
        {"type": "eq", "fun": lambda x: a_mat[eq_mask] @ x - lb_v[eq_mask], "jac": lambda x: a_mat[eq_mask]}
    ]
    if lo_mask.any():
        slsqp_cons.append(
            {"type": "ineq", "fun": lambda x: a_mat[lo_mask] @ x - lb_v[lo_mask], "jac": lambda x: a_mat[lo_mask]}
        )
    if up_mask.any():
        slsqp_cons.append(
            {"type": "ineq", "fun": lambda x: ub_v[up_mask] - a_mat[up_mask] @ x, "jac": lambda x: -a_mat[up_mask]}
        )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            res = optimize.minimize(
                f,
                xs0,
                jac=grad,
                bounds=optimize.Bounds(bounds_lo, bounds_hi),
                constraints=slsqp_cons,
                method="SLSQP",
                options={"ftol": 1e-14, "maxiter": 1000},
            )
            candidates.append((np.clip(res.x[:n], pb.lower, pb.upper), "slsqp" if res.success else "slsqp_partial"))
            slsqp_ok = res.success and _max_violation(res.x[:n], pb.lower, pb.upper, pb.budget, pb.g, pb.caps) < 1e-7
        except (ValueError, np.linalg.LinAlgError):
            slsqp_ok = False
        if not slsqp_ok:
            try:
                res2 = optimize.minimize(
                    f,
                    xs0,
                    jac=grad,
                    hess=hess,
                    bounds=optimize.Bounds(bounds_lo, bounds_hi),
                    constraints=[optimize.LinearConstraint(a_mat, lb_v, ub_v)],
                    method="trust-constr",
                    options={"gtol": 1e-10, "xtol": 1e-12, "maxiter": 3000},
                )
                candidates.append((np.clip(res2.x[:n], pb.lower, pb.upper), "trust-constr"))
            except (ValueError, np.linalg.LinAlgError):
                pass

    best_w, best_tag, best_obj = x0.copy(), "heuristic", -np.inf
    for w_c, tag in candidates:
        w_c = _finalize(w_c, pb.lower, pb.upper, pb.budget, pb.g, pb.caps)
        if _max_violation(w_c, pb.lower, pb.upper, pb.budget, pb.g, pb.caps) > 1e-7:
            continue
        obj = pb.objective(w_c)
        if obj > best_obj + 1e-15 or (tag != "heuristic" and obj >= best_obj - 1e-15):
            best_w, best_tag, best_obj = w_c, tag, obj
    return best_w, best_tag


# ---------------------------------------------------------------------------
# build_portfolio
# ---------------------------------------------------------------------------


def _validate_constraints(c: Constraints) -> None:
    if not c.long_only:
        raise ValueError("long_only=False non supporté : la vente à découvert est interdite à la BRVM")
    if not 0.0 <= c.cash_buffer < 1.0:
        raise ValueError("cash_buffer doit appartenir à [0, 1[")
    if not 0.0 < c.max_weight <= 1.0:
        raise ValueError("max_weight doit appartenir à ]0, 1]")
    if not 0.0 <= c.min_weight <= c.max_weight:
        raise ValueError("min_weight doit appartenir à [0, max_weight]")
    if c.max_names < 1:
        raise ValueError("max_names doit être >= 1")
    if c.max_sector_weight <= 0 or c.max_country_weight <= 0:
        raise ValueError("les plafonds secteur/pays doivent être > 0")


_MILP_CAP_TOL = 1e-7  # tolérance (absolue) sur la capacité visée dans les PLNE de sélection
_MILP_TIME_LIMIT = 10.0  # garde-fou (secondes) par résolution HiGHS ; jamais atteint en pratique


@dataclass
class _Selection:
    """Résultat de :func:`_select`.

    ``idx`` : titres retenus (ordre des scores) ; ``capacity`` : investissement
    maximal ``C*`` réalisable avec au plus ``k_max`` lignes (et au moins
    ``min_names`` si c'est réalisable ; PLNE), ``None`` s'il n'a pas été
    calculé (les ``k_max`` meilleurs scores suffisent) ;
    ``support`` : lignes d'une solution témoin atteignant ``C*`` (⊆ ``idx``) ;
    ``mode`` : ``"top"`` (meilleurs scores), ``"milp"`` ou ``"greedy"`` (repli).
    """

    idx: list[int]
    capacity: float | None
    support: list[int] | None
    mode: str = "top"


def _cardinality_milp(
    upper: np.ndarray,
    floor: float,
    g: np.ndarray,
    caps: np.ndarray,
    budget: float,
    k_max: int,
    *,
    forced_in: np.ndarray | None = None,
    forced_out: np.ndarray | None = None,
    target: float | None = None,
    n_min: int = 0,
) -> np.ndarray | None:
    """PLNE de capacité sous contrainte de cardinalité (HiGHS via ``scipy.optimize.milp``).

    Variables : poids ``w ∈ ℝⁿ`` et indicatrices de ligne ``y ∈ {0,1}ⁿ``.
    Chaque poids est **semi-continu** (Bienstock 1996 ; Chang, Meade, Beasley
    & Sharaiha 2000) : ``m·y_i ≤ w_i ≤ u_i·y_i`` (``m`` = ``floor`` =
    ``min_weight``), c.-à-d. ``w_i ∈ {0} ∪ [m, u_i]``. Contraintes :

    * cardinalité ``Σ_{j∉F} y_j ≤ k_max − |F|`` où ``F`` = ``forced_in`` (titres
      déjà retenus : ils occupent une place, qu'ils soient pondérés ou non) ;
    * ``y_j = 0`` pour ``j ∈ forced_out`` ;
    * au moins ``n_min`` lignes effectivement pondérées : ``Σ_j y_j ≥ n_min``
      (``min_names``) ;
    * plafonds de groupe ``Gw ≤ c`` et budget ``1ᵀw ≤ B`` ;
    * si ``target`` est fourni : ``1ᵀw ≥ target`` (problème de faisabilité,
      objectif nul) ; sinon on **maximise** ``1ᵀw`` (capacité ``C*``).

    Renvoie le vecteur ``(w, y)`` d'une solution réalisable (optimale pour la
    maximisation) ou ``None`` si le problème est infaisable ou non résolu.
    """
    n = len(upper)
    fin = np.zeros(n, bool) if forced_in is None else np.asarray(forced_in, bool)
    fout = np.zeros(n, bool) if forced_out is None else np.asarray(forced_out, bool)
    slots = k_max - int(fin.sum())
    if n == 0 or slots < 0:
        return None
    eye = np.eye(n)
    zero_n = np.zeros(n)
    rows = [np.hstack([eye, -np.diag(upper)])]  # w − u·y ≤ 0
    ub = [zero_n]
    lb = [np.full(n, -np.inf)]
    if floor > 0:
        rows.append(np.hstack([-eye, floor * eye]))  # m·y − w ≤ 0
        ub.append(zero_n)
        lb.append(np.full(n, -np.inf))
    rows.append(np.concatenate([zero_n, (~fin).astype(float)])[None, :])  # cardinalité
    ub.append(np.array([float(slots)]))
    lb.append(np.array([-np.inf]))
    if n_min > 0:
        rows.append(np.concatenate([zero_n, np.ones(n)])[None, :])  # lignes minimales
        ub.append(np.array([np.inf]))
        lb.append(np.array([float(n_min)]))
    if g.shape[0]:
        rows.append(np.hstack([g, np.zeros_like(g)]))
        ub.append(np.asarray(caps, float))
        lb.append(np.full(g.shape[0], -np.inf))
    rows.append(np.concatenate([np.ones(n), zero_n])[None, :])  # budget (et cible)
    ub.append(np.array([float(budget)]))
    lb.append(np.array([-np.inf if target is None else float(target)]))
    y_hi = np.where(fout, 0.0, 1.0)
    c = np.zeros(2 * n) if target is not None else np.concatenate([-np.ones(n), zero_n])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            res = optimize.milp(
                c,
                constraints=optimize.LinearConstraint(np.vstack(rows), np.concatenate(lb), np.concatenate(ub)),
                integrality=np.concatenate([zero_n, np.ones(n)]),
                bounds=optimize.Bounds(np.zeros(2 * n), np.concatenate([upper * y_hi, y_hi])),
                options={"mip_rel_gap": 1e-9, "time_limit": _MILP_TIME_LIMIT},
            )
        except (ValueError, np.linalg.LinAlgError):
            return None
    if res.x is None or res.status not in (0, 1):
        return None
    x = np.asarray(res.x, float)
    if target is not None and x[:n].sum() < target - 1e-9:
        return None
    return x


def _capacity_milp(
    upper: np.ndarray,
    floor: float,
    g: np.ndarray,
    caps: np.ndarray,
    budget: float,
    k_max: int,
    n_min: int,
) -> tuple[np.ndarray | None, int]:
    """Capacité maximale ``C*`` (:func:`_cardinality_milp`) avec au moins
    ``n_min`` lignes ; si ce plancher de cardinalité est irréalisable (planchers
    de poids incompatibles avec les plafonds de groupe), il est abandonné.
    Renvoie la solution et le ``n_min`` effectivement imposé."""
    n_min = max(0, min(int(n_min), int(k_max), len(upper)))
    x = _cardinality_milp(upper, floor, g, caps, budget, k_max, n_min=n_min)
    if x is None and n_min > 0:
        n_min = 0
        x = _cardinality_milp(upper, floor, g, caps, budget, k_max)
    return x, n_min


def _select_greedy(
    order: list[int],
    k_max: int,
    upper: np.ndarray,
    g: np.ndarray,
    caps: np.ndarray,
    budget: float,
) -> list[int]:
    """Repli glouton (si la PLNE échoue) : par score décroissant, on retient un
    titre s'il augmente la capacité investissable (PL), puis on complète avec
    les titres sautés. Sans garantie d'optimalité de la capacité."""

    def cap_of(sel: list[int]) -> float:
        if not sel:
            return 0.0
        v = _max_investable(np.zeros(len(sel)), upper[sel], g[:, sel], caps)
        return 0.0 if v is None else v

    selected: list[int] = []
    skipped: list[int] = []
    current = 0.0
    for i in order:
        if len(selected) >= k_max:
            break
        if current >= budget - 1e-12:
            selected.append(i)
            continue
        new = min(cap_of(selected + [i]), budget)
        if new > current + 1e-12:
            selected.append(i)
            current = new
        else:
            skipped.append(i)
    for i in skipped:
        if len(selected) >= k_max:
            break
        selected.append(i)
    rank = {v: r for r, v in enumerate(order)}
    return sorted(selected, key=rank.__getitem__)


def _select(
    order: np.ndarray,
    k_max: int,
    upper: np.ndarray,
    g: np.ndarray,
    caps: np.ndarray,
    budget: float,
    floor: float = 0.0,
    n_min: int = 0,
) -> _Selection:
    """Sélection d'au plus ``k_max`` titres, la meilleure par score parmi celles
    qui maximisent la capacité investissable.

    1. Si les ``k_max`` meilleurs scores permettent d'investir ``B`` même avec
       le plancher ``w_i ≥ m`` sur chacun (PL de capacité), ils sont retenus
       (cas usuel, aucun PLNE). S'il y a au plus ``k_max`` titres, tous sont
       retenus.
    2. Sinon, **phase 1** : capacité maximale ``C* = max 1ᵀw`` sur tous les
       portefeuilles de ``n_min`` à ``k_max`` lignes semi-continues
       ``w_i ∈ {0} ∪ [m, u_i]`` avec plafonds de groupe et ``1ᵀw ≤ B``
       (:func:`_capacity_milp` ; ``n_min = min_names`` est abandonné s'il est
       irréalisable). ``C* = B`` ssi le budget complet est réalisable.
    3. **Phase 2** : parmi les sélections atteignant ``C*``, on retient la
       meilleure pour l'ordre **lexicographique** des scores (Ehrgott 2005,
       *Multicriteria Optimization*, ch. 5) par fixation séquentielle : on
       parcourt les titres par score décroissant ; un titre est retenu s'il
       existe une complétion d'au plus ``k_max`` titres contenant les titres
       déjà retenus et lui-même qui atteint ``C*`` avec au moins ``n_min``
       lignes (PLNE de faisabilité), sinon
       il est écarté définitivement. Une solution témoin est conservée : si
       elle utilise déjà le titre, ou s'il reste une place libre, aucun PLNE
       n'est nécessaire. Le témoin final (``support``) atteint ``C*`` avec les
       seuls titres retenus.

    Comparé à un glouton qui retient tout titre augmentant (même de très peu)
    la capacité — et sature ainsi ``k_max`` avec des titres peu liquides — cette
    procédure garantit ``capacité(sélection) = C*`` tout en privilégiant les
    meilleurs scores. Repli glouton (:func:`_select_greedy`) si HiGHS échoue.
    """
    order = list(order)
    top = order[:k_max]
    if len(order) <= k_max:
        return _Selection(top, None, None)
    # PL avec planchers m sur tous les titres du « top » : borne inférieure de
    # la capacité semi-continue ; si elle atteint B, le top suffit.
    cap_top = _max_investable(np.full(len(top), floor), upper[top], g[:, top], caps)
    if cap_top is not None and cap_top >= budget - 1e-12:
        return _Selection(top, None, None)

    n = len(upper)
    x, n_min = _capacity_milp(upper, floor, g, caps, budget, k_max, n_min)
    if x is None:
        return _Selection(_select_greedy(order, k_max, upper, g, caps, budget), None, None, "greedy")
    cap_star = float(min(budget, x[:n].sum()))
    target = cap_star - _MILP_CAP_TOL
    witness = x[n:] > 0.5
    fin = np.zeros(n, bool)
    fout = np.zeros(n, bool)
    for i in order:
        n_in = int(fin.sum())
        if n_in >= k_max:
            break
        used_free = int((witness & ~fin).sum())
        fin[i] = True
        if witness[i] or used_free <= k_max - n_in - 1:
            continue  # le témoin reste réalisable avec i retenu
        x_i = _cardinality_milp(
            upper, floor, g, caps, budget, k_max, forced_in=fin, forced_out=fout, target=target, n_min=n_min
        )
        if x_i is None:
            fin[i] = False
            fout[i] = True
        else:
            witness = x_i[n:] > 0.5
    witness &= fin
    sel = [i for i in order if fin[i]]
    support = [i for i in order if witness[i]]
    return _Selection(sel, cap_star, support, "milp")


def _zscore(x: np.ndarray, clip: float = 3.0) -> np.ndarray:
    """z-score transversal écrêté à ``±clip`` (0 si dispersion nulle)."""
    sd = x.std()
    if not np.isfinite(sd) or sd <= 1e-15:
        return np.zeros_like(x)
    return np.clip((x - x.mean()) / sd, -clip, clip)


def build_portfolio(
    alpha: pd.Series,
    cov: pd.DataFrame | None,
    constraints: Constraints | None = None,
    liquidity: pd.Series | None = None,
    prev_weights: pd.Series | None = None,
    sectors: pd.Series | None = None,
    countries: pd.Series | None = None,
    method: Method = "mv_alpha",
    *,
    risk_aversion: float = 5.0,
    tcost: float | None = None,
    tilt_strength: float = 0.5,
    hrp_linkage: str = "single",
    hrp_distance_of_distances: bool = False,
    group_caps: Sequence[GroupCap] | None = None,
) -> pd.Series:
    """Poids cibles long-only sous contraintes.

    Étapes communes :

    1. **Univers éligible** : ``alpha`` fini, covariance disponible (sauf
       ``"equal"``), plafond ``u_i = min(max_weight, liquidity_i) ≥ min_weight``
       (un titre absent de ``liquidity`` a un plafond nul).
    2. **Sélection** des ``max_names`` meilleurs scores (``"mv_alpha"`` : score
       ``α_i + 2κ·1{détenu}``, la rotation d'un titre détenu coûtant un aller-
       retour), en garantissant que les plafonds permettent d'investir
       ``B = 1 − cash_buffer`` dès que c'est réalisable avec au plus
       ``max_names`` lignes (:func:`_select`) : si les meilleurs scores n'y
       suffisent pas, la capacité maximale ``C*`` est calculée par PLNE
       (cardinalité, poids semi-continus ``{0} ∪ [min_weight, u_i]``, plafonds
       secteur/pays ; Bienstock 1996 ; Chang et al. 2000) et la sélection est
       la meilleure, dans l'ordre lexicographique des scores, parmi celles qui
       atteignent ``C*``. Si ``C* < B``, ``B`` est réduit à ``C*`` et le reste
       demeure en liquidités.
    3. **Pondération** (selon ``method``) puis **élagage** : les lignes
       ``< min_weight`` sont supprimées (en conservant au moins ``min_names``
       lignes et la capacité d'investissement ; si l'élagage heuristique perd
       de la capacité, on repart de la solution témoin de la PLNE) et les poids
       sont recalculés sur les titres restants avec le plancher
       ``w_i ≥ min_weight`` — ce qui constitue la renormalisation.

    Méthodes :

    * ``"mv_alpha"`` : ``max αᵀw − (λ/2) wᵀΣw − κ‖w − w_préc‖₁`` s.c.
      ``Σw = B``, ``l ≤ w ≤ u``, plafonds secteur/pays (SLSQP, repli
      trust-constr puis heuristique ``w ∝ max(α,0)/σ²`` projetée).
    * ``"hrp_tilt"`` : ``w ∝ w_HRP · exp(γ z_α)`` (``z_α`` = z-score de l'alpha
      sur la sélection, écrêté à ±3), contraintes imposées par projection
      itérative (:func:`_waterfill`).
    * ``"equal"`` : ``w ∝ 1`` sur la sélection, même projection.

    Parameters
    ----------
    alpha
        Rendement espéré (ou score pour ``"hrp_tilt"``/``"equal"``) par titre.
    cov
        Covariance (même horizon que ``alpha`` pour ``"mv_alpha"``) ; peut être
        ``None`` pour ``"equal"``.
    constraints
        :class:`~brvm_alpha.config.Constraints` (défaut : valeurs par défaut).
    liquidity
        Poids maximal par titre (:func:`liquidity_caps`) ; ``None`` = pas de
        plafond de liquidité.
    prev_weights
        Poids actuels (coûts de rotation ; ``None`` = portefeuille en cash).
    sectors, countries
        Étiquettes secteur / pays par titre (étiquette manquante = groupe
        « __NA__ » plafonné).
    method
        ``"mv_alpha"``, ``"hrp_tilt"`` ou ``"equal"``.
    risk_aversion
        ``λ`` (pour des grandeurs annualisées).
    tcost
        ``κ`` coût proportionnel aller simple dans l'unité de ``alpha``
        (défaut : ``CostModel().rate()``).
    tilt_strength
        ``γ`` de l'inclinaison ``exp(γ z_α)``.
    hrp_linkage
        Méthode de classification pour HRP.
    hrp_distance_of_distances
        Transmis à :func:`~brvm_alpha.portfolio.risk.hrp_weights` (la spécification
        v1, §6, demande ``True`` explicitement ; défaut ``False`` pour compatibilité).
    group_caps
        Plafonds linéaires supplémentaires :class:`GroupCap` (``Σ_i a_i w_i ≤ c``,
        coefficients ``a_i ≥ 0`` quelconques : plafonds par secteur ou par pays
        différenciés, bloc AES par siège ou en exposition λ). Ils s'ajoutent aux
        plafonds uniformes ``max_sector_weight`` / ``max_country_weight``.

    Returns
    -------
    pandas.Series
        Poids sur l'union de ``alpha.index`` et ``prev_weights.index`` (0 pour
        les titres non retenus ; ``1 − Σw`` = liquidités). ``attrs`` :
        ``method``, ``solver``, ``budget`` (investissement visé), ``n_names``,
        ``max_investable`` (capacité maximale ``C*`` de **toutes** les
        sélections admissibles, PLNE, bornée par ``B``),
        ``feasible_full_budget`` (``C* ≥ B`` : le budget complet est réalisable
        sous les contraintes — calculé sur ``C*``, pas sur la sélection
        retenue) et ``selection`` (``"top"``, ``"milp"``, ``"greedy"``).
    """
    cons = Constraints() if constraints is None else constraints
    _validate_constraints(cons)
    if method not in ("mv_alpha", "hrp_tilt", "equal"):
        raise ValueError("method doit valoir 'mv_alpha', 'hrp_tilt' ou 'equal'")
    if method != "equal" and cov is None:
        raise ValueError(f"cov est requis pour method={method!r}")
    kappa = CostModel().rate() if tcost is None else float(tcost)
    if kappa < 0 or risk_aversion < 0:
        raise ValueError("tcost et risk_aversion doivent être >= 0")

    alpha = pd.Series(alpha, dtype=float)
    alpha = alpha.where(np.isfinite(alpha))
    prev = None if prev_weights is None else prev_weights.astype(float).fillna(0.0).clip(lower=0.0)
    out_index = alpha.index if prev is None else _union_index(alpha.index, prev.index)
    budget_target = 1.0 - cons.cash_buffer

    def _empty(reason: str) -> pd.Series:
        res = pd.Series(0.0, index=out_index, name="weight")
        res.attrs.update(
            {
                "method": method,
                "solver": reason,
                "budget": 0.0,
                "n_names": 0,
                "feasible_full_budget": False,
                "max_investable": 0.0,
                "selection": "none",
            }
        )
        return res

    # 1. Univers éligible ----------------------------------------------------
    cand = alpha.dropna()
    cand = cand[~cand.index.duplicated(keep="first")]
    if cov is not None:
        diag = pd.Series(np.diag(cov.to_numpy(dtype=float)), index=cov.index)
        ok_cov = diag[np.isfinite(diag) & (diag > 0)].index
        cand = cand[cand.index.isin(ok_cov) & cand.index.isin(cov.columns)]
        if len(cand):
            sub = cov.loc[cand.index, cand.index].to_numpy(dtype=float)
            row_ok = np.isfinite(sub).all(axis=1)
            cand = cand[row_ok]
    upper_s = pd.Series(cons.max_weight, index=cand.index, dtype=float)
    if liquidity is not None:
        liq = pd.to_numeric(liquidity, errors="coerce").reindex(cand.index).astype(float).fillna(0.0)
        upper_s = np.minimum(upper_s, liq.clip(lower=0.0))
    floor = max(cons.min_weight, 1e-12)
    cand = cand[upper_s >= floor - 1e-15]
    if cand.empty:
        warnings.warn("build_portfolio : aucun titre éligible, portefeuille 100 % liquidités", RuntimeWarning, stacklevel=2)
        return _empty("no_eligible")
    names = cand.index
    a_all = cand.to_numpy()
    u_all = np.minimum(upper_s.loc[names].to_numpy(), cons.max_weight)
    wp_all = prev.reindex(names).fillna(0.0).to_numpy() if prev is not None else np.zeros(len(names))
    g_sec, c_sec, _ = _group_matrix(names, sectors, cons.max_sector_weight, budget_target)
    g_cty, c_cty, _ = _group_matrix(names, countries, cons.max_country_weight, budget_target)
    g_extra, c_extra = _group_arrays(group_caps or (), list(names))
    g_all = np.vstack([g_sec, g_cty, g_extra]) if (g_sec.size or g_cty.size or g_extra.size) else np.zeros((0, len(names)))
    c_all = np.concatenate([c_sec, c_cty, c_extra])
    sig_all = cov.loc[names, names].to_numpy(dtype=float) if cov is not None else None
    if sig_all is not None:
        sig_all = 0.5 * (sig_all + sig_all.T)

    # 2. Sélection -----------------------------------------------------------
    score = a_all + (2.0 * kappa * (wp_all > 0) if method == "mv_alpha" else 0.0)
    order = np.lexsort((np.asarray(names.astype(str)), -score))
    selection = _select(
        order, cons.max_names, u_all, g_all, c_all, budget_target, floor=cons.min_weight, n_min=cons.min_names
    )
    sel = selection.idx

    def sub_groups(idx: list[int]) -> tuple[np.ndarray, np.ndarray]:
        g = g_all[:, idx]
        used = g.sum(axis=1) > 0
        return g[used], c_all[used]

    def capacity(idx: list[int], lower: np.ndarray) -> float | None:
        g, c = sub_groups(idx)
        return _max_investable(lower, u_all[idx], g, c)

    cap_sel = capacity(sel, np.zeros(len(sel))) or 0.0
    budget_s = min(budget_target, cap_sel)
    if budget_s <= 1e-12:
        return _empty("no_capacity")

    # 3. Pondération ---------------------------------------------------------
    def raw_weights(idx: list[int]) -> np.ndarray:
        if method == "equal":
            return np.ones(len(idx))
        if method == "hrp_tilt":
            names_i = names[idx]
            hrp = hrp_weights(
                pd.DataFrame(sig_all[np.ix_(idx, idx)], index=names_i, columns=names_i),
                linkage_method=hrp_linkage,
                distance_of_distances=hrp_distance_of_distances,
            ).to_numpy()
            return hrp * np.exp(tilt_strength * _zscore(a_all[idx]))
        # heuristique moyenne-variance diagonale : w ∝ max(α − coût, 0) / σ²
        var = np.diag(sig_all)[idx]
        edge = np.maximum(a_all[idx] - kappa * (wp_all[idx] <= 0), 0.0)
        raw = edge / var
        return raw if raw.sum() > 0 else 1.0 / var

    def weigh(idx: list[int], lower: np.ndarray, budget: float) -> tuple[np.ndarray, str]:
        g, c = sub_groups(idx)
        upper = u_all[idx]
        raw = raw_weights(idx)
        w0 = _finalize(raw / raw.sum() * budget, lower, upper, budget, g, c)
        if method != "mv_alpha":
            return w0, "projection"
        pb = _MVProblem(
            alpha=a_all[idx],
            sigma=sig_all[np.ix_(idx, idx)],
            lower=lower,
            upper=upper,
            budget=budget,
            g=g,
            caps=c,
            prev=wp_all[idx],
            risk_aversion=risk_aversion,
            tcost=kappa,
        )
        return _solve_mv(pb, w0)

    w1, tag1 = weigh(sel, np.zeros(len(sel)), budget_s)

    # 4. Élagage (min_weight, min_names) puis re-pondération avec plancher ----
    tol_keep = 1e-9
    keep = [sel[j] for j in range(len(sel)) if w1[j] >= cons.min_weight - tol_keep]
    rest_pos = sorted(
        (j for j in range(len(sel)) if w1[j] < cons.min_weight - tol_keep),
        key=lambda j: (-w1[j], -a_all[sel[j]]),
    )
    rest = [sel[j] for j in rest_pos]
    while len(keep) < min(cons.min_names, len(sel)) and rest:
        keep.append(rest.pop(0))
    floor_w = cons.min_weight

    def cap_floor(idx: list[int]) -> float | None:
        return capacity(idx, np.full(len(idx), floor_w))

    cap_k = cap_floor(keep)
    while (cap_k is None or cap_k < budget_s - 1e-12) and rest:
        keep.append(rest.pop(0))
        cap_k = cap_floor(keep)
    while cap_k is None and len(keep) > 1:
        # planchers incompatibles avec un plafond de groupe : on retire la plus petite ligne
        pos = {v: w1[sel.index(v)] for v in keep}
        keep.remove(min(keep, key=lambda v: (pos[v], a_all[v])))
        cap_k = cap_floor(keep)
    # Repli PLNE : l'élagage ci-dessus peut perdre de la capacité (planchers ×
    # plafonds de groupe) ; on repart alors d'un témoin semi-continu, complété
    # jusqu'à min_names lignes sans réduire la capacité.
    ref_cap = budget_s if selection.capacity is None else min(budget_s, selection.capacity)
    if cap_k is None or cap_k < ref_cap - _MILP_CAP_TOL:
        support = selection.support
        if support is None:
            g_s, c_s = sub_groups(sel)
            x_s, _ = _capacity_milp(u_all[sel], floor_w, g_s, c_s, budget_s, len(sel), cons.min_names)
            support = None if x_s is None else [sel[j] for j in range(len(sel)) if x_s[len(sel) + j] > 0.5]
        cap_t = cap_floor(support) if support else None
        if cap_t is not None and (cap_k is None or cap_t > cap_k + 1e-9):
            keep = list(support)
            need = min(cap_t, budget_s)
            extra = sorted((v for v in sel if v not in keep), key=lambda v: (-w1[sel.index(v)], -a_all[v]))
            for v in extra:
                if len(keep) >= min(cons.min_names, len(sel)):
                    break
                c2 = cap_floor(keep + [v])
                if c2 is not None and c2 >= need - 1e-12:
                    keep.append(v)
                    cap_t = c2
            cap_k = cap_t
    if cap_k is None:
        return _empty("infeasible")
    budget_k = min(budget_s, cap_k)
    keep = sorted(keep, key=sel.index)
    if floor_w > 0 or len(keep) != len(sel):
        w2, tag2 = weigh(keep, np.full(len(keep), floor_w), budget_k)
    else:
        w2, tag2 = w1, tag1

    # 5. Assemblage ----------------------------------------------------------
    res = pd.Series(0.0, index=out_index, name="weight")
    vals = np.where(w2 > 1e-15, w2, 0.0)
    res.loc[names[keep]] = vals
    # Capacité maximale admissible (≤ max_names lignes semi-continues, PLNE) :
    # c'est elle, et non la sélection retenue, qui dit si B est réalisable.
    full = budget_k >= budget_target - 1e-9
    if full:
        max_inv = budget_target
    elif selection.capacity is not None:
        max_inv = selection.capacity
    else:
        x_g, _ = _capacity_milp(u_all, floor_w, g_all, c_all, budget_target, cons.max_names, cons.min_names)
        max_inv = budget_k if x_g is None else float(min(budget_target, x_g[: len(names)].sum()))
    max_inv = max(float(max_inv), float(budget_k))
    res.attrs.update(
        {
            "method": method,
            "solver": tag2,
            "budget": float(budget_k),
            "n_names": int((vals > 0).sum()),
            "feasible_full_budget": bool(full or max_inv >= budget_target - _MILP_CAP_TOL),
            "max_investable": max_inv,
            "selection": selection.mode,
        }
    )
    return res


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------


def constraint_violations(
    weights: pd.Series,
    constraints: Constraints | None = None,
    liquidity: pd.Series | None = None,
    sectors: pd.Series | None = None,
    countries: pd.Series | None = None,
    group_caps: Sequence[GroupCap] | None = None,
) -> dict[str, float]:
    """Mesure des violations de contraintes (0 = respectée).

    Renvoie un dictionnaire : ``negative`` (poids < 0), ``budget`` (dépassement
    de ``1 − cash_buffer``), ``max_weight``, ``min_weight`` (plus grand écart
    sous le plancher parmi les lignes non nulles), ``liquidity``, ``sector``,
    ``country`` (dépassements maximaux) et ``max_names`` (lignes en trop). Avec
    ``group_caps``, la clé ``groups`` donne le plus grand dépassement des plafonds
    :class:`GroupCap`.
    """
    cons = Constraints() if constraints is None else constraints
    w = weights.astype(float).fillna(0.0)
    nz = w[w > 1e-12]
    out = {
        "negative": float(max(0.0, -float(w.min()))) if len(w) else 0.0,
        "budget": float(max(w.sum() - (1.0 - cons.cash_buffer), 0.0)),
        "max_weight": float(max((w - cons.max_weight).max(), 0.0)) if len(w) else 0.0,
        "min_weight": float(max((cons.min_weight - nz).max(), 0.0)) if len(nz) else 0.0,
        "max_names": float(max(len(nz) - cons.max_names, 0)),
        "liquidity": 0.0,
        "sector": 0.0,
        "country": 0.0,
    }
    if liquidity is not None:
        liq = liquidity.reindex(nz.index).astype(float).fillna(0.0)
        out["liquidity"] = float(max((nz - liq).max(), 0.0)) if len(nz) else 0.0
    for key, labels, cap in (
        ("sector", sectors, cons.max_sector_weight),
        ("country", countries, cons.max_country_weight),
    ):
        if labels is not None and len(nz):
            lab = labels.reindex(nz.index).astype(object)
            lab = lab.where(lab.notna(), _NA_GROUP).astype(str)
            out[key] = float(max(nz.groupby(lab).sum().max() - cap, 0.0))
    if group_caps is not None:
        out["groups"] = max(
            (max(float(gc.load(w)) - gc.cap, 0.0) for gc in group_caps), default=0.0
        )
    return out


# ===========================================================================
# Construction v1 (spécification §4.2, §6, §9.1 et §11 « portfolio.* »)
# ===========================================================================
#
# Toutes les entrées sont celles connues à la date de décision t (scores, univers
# éligible, MDV63, spreads, drapeaux de risque, poids de référence) ; l'exécution a
# lieu à partir de t+1 (moteur de backtest). Les plafonds (multiplicateurs pays,
# secteurs, AES) sont des choix de conception NON VALIDÉS (spéc. §11, confiance B) :
# ce sont des règles de risque, jamais une promesse de rendement.

#: Multiplicateur du poids maximal par ligne selon le pays du siège (spéc. §4.2.1 ;
#: jugement non validé de la revue 06a §9.4). Pays absent : plus petit multiplicateur.
SPEC_COUNTRY_MULTIPLIER: dict[str, float] = {
    "CI": 1.0, "BJ": 1.0, "TG": 0.9, "SN": 0.85, "BF": 0.75, "ML": 0.7, "NE": 0.6,
}

#: Pays du bloc AES (Burkina Faso, Mali, Niger ; spéc. §4.2.3).
SPEC_AES_COUNTRIES: tuple[str, ...] = ("BF", "ML", "NE")

#: Date de la table figée des poids de référence par pays (BOC du 20/11/2026).
_SNAPSHOT_DATE = pd.Timestamp("2026-11-20")

#: Paramètres de construction v1, identiques à la spécification (§6, §11, §12.1).
#: :func:`portfolio_params` accepte un dict plat de surcharges (clés ci-dessous) ou le
#: dict complet de ``configs/strategy_v1.yaml`` (:func:`portfolio_params_from_config`).
PORTFOLIO_V1_DEFAULTS: dict[str, Any] = {
    "capital": 10_000_000.0,  # capital de référence K du backtest (FCFA)
    "gross_equity": 0.98,  # exposition actions ; poche de liquidités de 2 %
    "n_divisor": 3,  # n_cible = clip(round(N_élig / 3), 12, 20)
    "min_names": 12,
    "max_names": 20,
    "min_eligible": 15,  # U10 : sous 15 éligibles, panier équipondéré (mode repli)
    "entry_pct": 0.30,  # entrée : rang dans les 30 % supérieurs
    "exit_pct": 0.50,  # sortie : rang hors des 50 % supérieurs
    "fill_beyond_exit": True,  # complément au-delà des 50 % si moins de 12 lignes (interprétation, voir select_with_band)
    "fill_for_capacity": True,  # complément depuis les 50 % si les plafonds empêchent d'investir 98 % (interprétation)
    "capacity_beyond_exit": False,  # ce complément de capacité peut-il aller au-delà des 50 % ? (non par défaut)
    "weighting": "equal",  # A : "equal" ; G : "hrp_tilt" ; H : "mv_alpha"
    "max_weight": 0.10,
    "min_weight": 0.02,  # plancher : en dessous, la ligne est supprimée
    "country_multiplier": dict(SPEC_COUNTRY_MULTIPLIER),
    "low_liquidity_mult": 0.5,  # U6
    "wide_spread_mult": 0.5,  # U7
    "risk_flag_mult": 0.5,  # R4, R11 (un drapeau), R12
    "risk_exclude_flags": 2,  # R11 : 2 drapeaux ou plus => exclusion
    "low_liquidity_tier_fcfa": 2_000_000.0,  # U6 : MDV63 < 2 M FCFA
    "max_spread_full_weight": 0.015,  # U7 : spread médian 120 séances > 1,5 %
    "sector_cap_floor": 0.15,  # w_s ≤ max(15 % ; min(45 % ; 1,5 × u_s))
    "sector_cap_max": 0.45,
    "sector_cap_mult": 1.5,
    "country_cap_max": 0.30,  # pays ≠ CI : min(30 % ; max(10 % ; 1,5 × max(u_c, b_c)))
    "country_cap_floor": 0.10,
    "country_cap_mult": 1.5,
    "uncapped_countries": ("CI",),  # CI : aucun plafond propre
    "aes_countries": SPEC_AES_COUNTRIES,
    "aes_cap_multiple": 1.25,  # AES ≤ 1,25 × référence (siège ET exposition λ)
    "max_participation": 0.10,  # liquidité : w·K ≤ 0,10 × MDV63 × 20
    "days_to_liquidate": 20.0,
    "hrp_gamma": 0.5,  # G : inclinaison exp(γ·z)
    "hrp_linkage": "single",
    "hrp_distance_of_distances": True,
    "cov_freq": "W-FRI",  # covariance : rendements hebdomadaires
    "cov_weeks": 104,
    "cov_min_weeks": 52,
    "cov_shrinkage_floor": 0.5,  # plancher d'intensité de Ledoit-Wolf
    "exclude_stats_windows": (("2021-05-06", "2021-06-25"),),  # trou de BOC de 2021 (§3.1.3)
    "mv_ic": 0.02,  # H : IC_post de l'alpha de Grinold
    "mv_risk_aversion": 5.0,  # H : λ (grandeurs annualisées)
    "mv_tcost": None,  # H : κ ; None = coût aller central (central_one_way_cost)
    "kelly_fraction": 0.25,  # H : Kelly fractionnel sur les poids actifs
    "kelly_fraction_max": 0.5,
    "kelly_max_gross": 1.0,
}

_WEIGHTINGS = ("equal", "hrp_tilt", "mv_alpha")
_CAP_TOL = 1e-12  # tolérance relative de saturation (remplissage)
_INVARIANT_TOL = 1e-9  # aucun plafond violé de plus de 1e-9


# ---------------------------------------------------------------------------
# Paramètres
# ---------------------------------------------------------------------------


def portfolio_params_from_config(cfg: Mapping[str, Any]) -> dict[str, Any]:
    """Paramètres de construction lus dans le dict de ``configs/strategy_v1.yaml``.

    ``cfg`` est le dictionnaire chargé par :func:`brvm_alpha.settings.load_strategy_config`
    (§12.1 de la spécification). Seules les clés présentes sont lues ; les formules
    textuelles (``n_holdings``, ``sector_cap``, ``country_cap_non_ci``) sont décodées par
    les fonctions de :mod:`brvm_alpha.settings`. Les paramètres absents du YAML (HRP,
    covariance, alpha de Grinold) gardent les valeurs de :data:`PORTFOLIO_V1_DEFAULTS`.
    """
    from brvm_alpha import settings as st  # import local : settings dépend de config.py

    def get(dotted: str) -> Any:
        return st.get_param(cfg, dotted, None)

    out: dict[str, Any] = {}
    simple = {
        "capital": "capital_fcfa_reference",
        "gross_equity": "portfolio.gross_equity",
        "max_weight": "portfolio.max_weight",
        "min_weight": "portfolio.min_weight",
        "aes_cap_multiple": "portfolio.aes_cap_multiple",
        "max_participation": "portfolio.liquidity.max_participation",
        "days_to_liquidate": "portfolio.liquidity.days_to_liquidate",
        "kelly_fraction": "portfolio.kelly.fraction",
        "kelly_fraction_max": "portfolio.kelly.fraction_max",
        "kelly_max_gross": "portfolio.kelly.max_gross",
        "low_liquidity_tier_fcfa": "universe.low_liquidity_tier_fcfa",
        "max_spread_full_weight": "universe.max_spread_full_weight",
        "risk_flag_mult": "events.risk_filters.R11_fin_flags.one_flag_weight_mult",
    }
    for key, dotted in simple.items():
        val = get(dotted)
        if val is not None:
            out[key] = float(val)
    if get("universe.min_names_for_selection") is not None:
        out["min_eligible"] = int(get("universe.min_names_for_selection"))
    if get("portfolio.weighting") is not None:
        out["weighting"] = str(get("portfolio.weighting"))
    if get("portfolio.n_holdings") is not None:
        nh = st.n_holdings_params(cfg)
        out.update(n_divisor=int(nh["divisor"]), min_names=int(nh["min"]), max_names=int(nh["max"]))
    band = get("portfolio.band")
    if isinstance(band, Mapping):
        out["entry_pct"] = float(band["enter_top_pct"]) / 100.0
        out["exit_pct"] = float(band["exit_below_top_pct"]) / 100.0
    mult = get("portfolio.country_multiplier")
    if isinstance(mult, Mapping):
        out["country_multiplier"] = {str(k): float(v) for k, v in mult.items()}
    if get("portfolio.sector_cap") is not None:
        sc = st.sector_cap_params(cfg)
        out.update(sector_cap_floor=sc["floor"], sector_cap_max=sc["cap"], sector_cap_mult=sc["mult"])
    if get("portfolio.country_cap_non_ci") is not None:
        cc = st.country_cap_params(cfg)
        out.update(country_cap_max=cc["cap"], country_cap_floor=cc["floor"], country_cap_mult=cc["mult"])
    two = get("events.risk_filters.R11_fin_flags.two_flags")
    if two is not None and str(two).lower() == "exclude":
        out["risk_exclude_flags"] = 2
    windows = get("data.exclude_stats_windows")
    if windows:
        out["exclude_stats_windows"] = tuple((str(a), str(b)) for a, b in windows)
    return out


def _validate_params(p: Mapping[str, Any]) -> None:
    problems = []
    if not 0.0 < float(p["gross_equity"]) <= 1.0:
        problems.append("gross_equity doit appartenir à ]0, 1]")
    if not 0.0 <= float(p["min_weight"]) <= float(p["max_weight"]) <= 1.0:
        problems.append("il faut 0 ≤ min_weight ≤ max_weight ≤ 1")
    if not 0.0 <= float(p["entry_pct"]) <= float(p["exit_pct"]) <= 1.0:
        problems.append("il faut 0 ≤ entry_pct ≤ exit_pct ≤ 1")
    if not 1 <= int(p["min_names"]) <= int(p["max_names"]):
        problems.append("il faut 1 ≤ min_names ≤ max_names")
    if int(p["n_divisor"]) < 1:
        problems.append("n_divisor doit être ≥ 1")
    if p["weighting"] not in _WEIGHTINGS:
        problems.append(f"weighting doit valoir {', '.join(_WEIGHTINGS)} (lu : {p['weighting']!r})")
    if float(p["capital"]) <= 0:
        problems.append("capital doit être > 0")
    for key in ("low_liquidity_mult", "wide_spread_mult", "risk_flag_mult"):
        if not 0.0 <= float(p[key]) <= 1.0:
            problems.append(f"{key} doit appartenir à [0, 1]")
    if not 0.0 <= float(p["kelly_fraction"]) <= 1.0 or not 0.0 < float(p["kelly_fraction_max"]) <= 1.0:
        problems.append("kelly_fraction ∈ [0, 1] et kelly_fraction_max ∈ ]0, 1] attendus")
    if int(p["cov_min_weeks"]) < 2 or int(p["cov_weeks"]) < int(p["cov_min_weeks"]):
        problems.append("il faut 2 ≤ cov_min_weeks ≤ cov_weeks")
    if problems:
        raise ValueError("paramètres de portefeuille invalides : " + " ; ".join(problems))


def portfolio_params(params: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Paramètres effectifs : :data:`PORTFOLIO_V1_DEFAULTS` + surcharges validées.

    ``params`` est soit un dict **plat** (clés de :data:`PORTFOLIO_V1_DEFAULTS`), soit le
    dict complet du YAML de stratégie (clé ``"portfolio"`` présente), converti par
    :func:`portfolio_params_from_config` ; dans ce second cas, les clés plates présentes
    au premier niveau priment. Une clé inconnue lève ``ValueError`` (les paramètres sont
    FIGÉS avant le test S1 : une faute de frappe ne doit pas passer inaperçue).
    """
    out = copy.deepcopy(PORTFOLIO_V1_DEFAULTS)
    if params:
        flat = dict(params)
        if isinstance(flat.get("portfolio"), Mapping):
            from_yaml = portfolio_params_from_config(flat)
            extra = {k: v for k, v in flat.items() if k in PORTFOLIO_V1_DEFAULTS}
            flat = {**from_yaml, **extra}
        unknown = sorted(set(flat) - set(out))
        if unknown:
            raise ValueError("paramètres de portefeuille inconnus : " + ", ".join(map(str, unknown)))
        out.update(copy.deepcopy(flat))
    _validate_params(out)
    return out


# ---------------------------------------------------------------------------
# Outils : symboles, étiquettes, drapeaux
# ---------------------------------------------------------------------------


def _symbols(x: Any) -> list[str]:
    """Liste triée et sans doublon de symboles (Series booléenne, index, itérable)."""
    if x is None:
        return []
    if isinstance(x, pd.Series):
        if x.dtype == bool or pd.api.types.is_bool_dtype(x):
            vals = x.index[x.fillna(False).astype(bool).to_numpy()]
        elif pd.api.types.is_numeric_dtype(x):
            vals = x.index[(x.fillna(0) != 0).to_numpy()]
        else:
            vals = x.dropna().astype(str).to_numpy()
        return sorted({str(v) for v in vals})
    if isinstance(x, Mapping):
        return sorted({str(k) for k, v in x.items() if v})
    if isinstance(x, str):
        return [x]
    return sorted({str(v) for v in x})


def _unique(seq: Iterable[Any]) -> list[str]:
    """Symboles uniques en conservant l'ordre."""
    return list(dict.fromkeys(str(s) for s in seq))


def _held_series(held: Any) -> pd.Series:
    """Poids détenus (> 0). Un itérable de symboles = détenus, poids inconnu (NaN)."""
    if held is None:
        return pd.Series(dtype=float, name="held")
    if isinstance(held, (pd.Series, Mapping)):
        s = pd.Series(held, dtype=float)
        s.index = s.index.astype(str)
        s = s.groupby(level=0).sum(min_count=1)
        s = s.where(np.isfinite(s), np.nan)
        return s[(s > 1e-12)].rename("held")
    return pd.Series(np.nan, index=_symbols(held), dtype=float, name="held")


def _flag_series(flags: Any, symbols: Sequence[str]) -> pd.Series:
    """Drapeau booléen par symbole (Series/Mapping booléen, ou itérable de symboles)."""
    idx = pd.Index(list(symbols), dtype=object)
    if flags is None:
        return pd.Series(False, index=idx, dtype=bool)
    if isinstance(flags, (pd.Series, Mapping)):
        s = pd.Series(flags)
        s.index = s.index.astype(str)
        s = s.reindex(idx)
        return pd.Series([bool(v) if pd.notna(v) else False for v in s.to_numpy()], index=idx, dtype=bool)
    if isinstance(flags, (bool, np.bool_)):
        return pd.Series(bool(flags), index=idx, dtype=bool)
    flagged = set(_symbols(flags))
    return pd.Series([s in flagged for s in idx], index=idx, dtype=bool)


def _labels_for(labels: Any, symbols: Sequence[str], kind: str) -> pd.Series:
    """Étiquettes pays / secteur par symbole ; défaut : :mod:`brvm_alpha.reference`."""
    idx = pd.Index(list(symbols), dtype=object)
    if labels is not None:
        s = pd.Series(labels, dtype=object)
        s.index = s.index.astype(str)
        s = s.reindex(idx)
    else:
        from brvm_alpha import reference as ref

        fn = ref.country_of if kind == "country" else ref.sector_of
        s = pd.Series([fn(x) for x in idx], index=idx, dtype=object)
    return pd.Series(
        [_NA_GROUP if (v is None or (not isinstance(v, str) and pd.isna(v))) else str(v) for v in s.to_numpy()],
        index=idx,
        dtype=object,
        name=kind,
    )


# ---------------------------------------------------------------------------
# 1. Nombre de lignes et 2. sélection avec bande
# ---------------------------------------------------------------------------


def is_fallback(n_eligible: int, min_eligible: int = 15) -> bool:
    """Mode repli (U10) : moins de ``min_eligible`` titres éligibles."""
    return int(n_eligible) < int(min_eligible)


def n_holdings(
    n_eligible: int,
    *,
    divisor: int = 3,
    min_names: int = 12,
    max_names: int = 20,
    min_eligible: int = 15,
) -> int:
    """Nombre de lignes visé : ``clip(round(N/3), 12, 20)`` (spéc. §6, ``portfolio.n_holdings``).

    Mode repli (U10, ``N < 15``) : le portefeuille est le panier équipondéré de **tous**
    les éligibles ; la fonction renvoie alors ``N`` (voir :func:`is_fallback`). ``round``
    est l'arrondi au plus proche (``N/3`` n'a jamais de partie fractionnaire 0,5).
    """
    n = int(n_eligible)
    if n <= 0:
        return 0
    if is_fallback(n, min_eligible):
        return n
    return int(min(max(math.floor(n / divisor + 0.5), min_names), max_names))


def score_ranks(scores: pd.Series | Mapping[str, float], eligible: Any) -> pd.Series:
    """Rang (1 = meilleur) des éligibles par score décroissant.

    Tri **stable et déterministe** : score décroissant, égalités départagées par le
    symbole (ordre alphabétique) ; un score manquant ou non fini est classé en dernier
    (puis par symbole). L'ordre d'entrée des données n'a aucune influence.
    """
    elig = _symbols(eligible)
    s = pd.Series(scores, dtype=float)
    s.index = s.index.astype(str)
    s = s[~s.index.duplicated(keep="first")].reindex(elig)

    def key(sym: str) -> tuple[int, float, str]:
        v = s.get(sym, np.nan)
        ok = v is not None and np.isfinite(v)
        return (0 if ok else 1, -float(v) if ok else 0.0, sym)

    order = sorted(elig, key=key)
    return pd.Series(np.arange(1, len(order) + 1, dtype=int), index=pd.Index(order, dtype=object), name="rank")


@dataclass
class BandSelection:
    """Résultat de :func:`select_with_band`.

    ``selected`` : titres retenus, dans l'ordre des rangs ; ``ranks`` : rang de chaque
    éligible ; ``reasons`` : motif (français) pour chaque titre considéré ;
    ``reserve`` : candidats non retenus des 50 % supérieurs (achetables), par rang ;
    ``reserve_beyond`` : candidats achetables au-delà des 50 % (par rang) ; ``kept`` /
    ``added`` / ``completed`` / ``dropped`` / ``sold`` : détail des mouvements.
    """

    selected: list[str]
    ranks: pd.Series
    reasons: dict[str, str]
    reserve: list[str]
    n_eligible: int
    n_target: int
    entry_rank: int
    exit_rank: int
    kept: list[str] = field(default_factory=list)
    added: list[str] = field(default_factory=list)
    completed: list[str] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)
    sold: list[str] = field(default_factory=list)
    reserve_beyond: list[str] = field(default_factory=list)


def select_with_band(
    scores: pd.Series | Mapping[str, float],
    held: Any,
    eligible: Any,
    n_target: int,
    entry_pct: float = 0.30,
    exit_pct: float = 0.50,
    *,
    min_names: int = 12,
    max_names: int = 20,
    holdable: Iterable[str] | None = None,
    no_buy: Iterable[str] | None = None,
    fill_beyond_exit: bool = True,
) -> BandSelection:
    """Sélection mensuelle avec bande de rotation 30/50 (spéc. §6 ; Novy-Marx & Velikov 2016).

    Rangs par score décroissant sur l'univers éligible (:func:`score_ranks`, N titres).
    Seuils : ``k_entrée = ⌊0,30·N⌋`` et ``k_sortie = ⌊0,50·N⌋`` (un titre est « dans les
    30 % supérieurs » si ``rang/N ≤ 0,30``).

    1. **Conservation** : un titre détenu reste tant que son rang est ``≤ k_sortie`` et
       qu'il est éligible (et détenable : plafond de ligne ≥ 2 %).
    2. **Ajouts** : titres non détenus de rang ``≤ k_entrée``, par score décroissant,
       jusqu'à ``n_target`` lignes (achat interdit pour ``no_buy`` : filtres R ou
       règles pays).
    3. **Complément** : si l'on a moins de ``min_names`` (12) lignes, meilleurs rangs
       restants des 50 % supérieurs. *Interprétation* (la spécification ne traite pas
       le cas) : si les 50 % supérieurs ne suffisent pas (N < 24), le complément se
       poursuit par rang au-delà (``fill_beyond_exit=True``, signalé dans ``reasons``),
       car la spécification ne réduit pas la diversification sous 12 lignes (§6).
    4. **Plafond** : au-delà de ``max_names`` (20) lignes, les moins bien classés sont
       retirés.

    Déterministe : tri stable, égalités départagées par le symbole.
    """
    elig = _symbols(eligible)
    held_s = _held_series(held)
    held_set = set(held_s.index)
    ranks = score_ranks(scores, elig)
    n = len(ranks)
    k_in = math.floor(float(entry_pct) * n + 1e-9)
    k_out = math.floor(float(exit_pct) * n + 1e-9)
    holdable_set = None if holdable is None else set(_symbols(holdable))

    def can_hold(sym: str) -> bool:
        return holdable_set is None or sym in holdable_set
    blocked = set(_symbols(no_buy)) if no_buy is not None else set()
    ordered = list(ranks.index)
    reasons: dict[str, str] = {}
    selected: list[str] = []
    kept: list[str] = []
    added: list[str] = []
    completed: list[str] = []
    dropped: list[str] = []
    sold: list[str] = []

    def rk(s: str) -> str:
        return f"rang {int(ranks[s])}/{n}"

    # 1. Conservation des titres détenus
    for s in ordered:
        if s not in held_set:
            continue
        if not can_hold(s):
            reasons[s] = f"vendu : plafond de ligne sous le plancher ({rk(s)})"
            sold.append(s)
        elif ranks[s] <= k_out:
            selected.append(s)
            kept.append(s)
            reasons[s] = f"conservé : détenu, {rk(s)} dans les 50 % supérieurs (seuil {k_out})"
        else:
            reasons[s] = f"vendu : {rk(s)} hors des 50 % supérieurs (seuil {k_out})"
            sold.append(s)
    for s in sorted(held_set - set(elig)):
        reasons[s] = "vendu : titre non éligible à la date de décision"
        sold.append(s)

    # 2. Ajouts depuis les 30 % supérieurs
    for s in ordered[:k_in]:
        if s in selected or s in held_set:
            continue
        if len(selected) >= n_target:
            reasons[s] = f"non retenu : {rk(s)} dans les 30 % supérieurs mais n_cible = {n_target} atteint"
            continue
        if not can_hold(s):
            reasons[s] = f"non retenu : plafond de ligne sous le plancher ({rk(s)})"
            continue
        if s in blocked:
            reasons[s] = f"non retenu : achat bloqué (filtre de risque ou règle pays), {rk(s)}"
            continue
        selected.append(s)
        added.append(s)
        reasons[s] = f"ajouté : {rk(s)} dans les 30 % supérieurs (seuil {k_in})"

    # 3. Complément jusqu'à min_names
    def candidates(pool: Sequence[str]) -> list[str]:
        return [s for s in pool if s not in selected and can_hold(s) and s not in blocked]

    pool_in = candidates([s for s in ordered[:k_out] if s not in held_set])
    pool_out = candidates(ordered[k_out:])
    for s in pool_in + (pool_out if fill_beyond_exit else []):
        if len(selected) >= min_names:
            break
        selected.append(s)
        completed.append(s)
        if ranks[s] <= k_out:
            reasons[s] = f"complément : moins de {min_names} lignes, {rk(s)} dans les 50 % supérieurs"
        else:
            reasons[s] = (
                f"complément hors bande : moins de {min_names} lignes et 50 % supérieurs épuisés, {rk(s)}"
            )
        if s in sold:
            sold.remove(s)
    reserve = [s for s in pool_in if s not in selected]
    reserve_beyond = [s for s in pool_out if s not in selected]

    # 4. Au plus max_names lignes
    selected.sort(key=lambda s: int(ranks[s]))
    while len(selected) > max_names:
        s = selected.pop()
        dropped.append(s)
        reasons[s] = f"retiré : au-delà de {max_names} lignes ({rk(s)})"
        if s in kept:
            sold.append(s)

    for s in ordered:
        if s not in reasons:
            if not can_hold(s):
                reasons[s] = f"non retenu : plafond de ligne sous le plancher ({rk(s)})"
            elif ranks[s] > k_in:
                reasons[s] = f"non retenu : {rk(s)} hors des 30 % supérieurs (seuil d'entrée {k_in})"
            else:
                reasons[s] = f"non retenu : {rk(s)}"
    return BandSelection(
        selected=selected,
        ranks=ranks,
        reasons=reasons,
        reserve=reserve,
        n_eligible=n,
        n_target=int(n_target),
        entry_rank=k_in,
        exit_rank=k_out,
        kept=kept,
        added=added,
        completed=completed,
        dropped=dropped,
        sold=sold,
        reserve_beyond=reserve_beyond,
    )


# ---------------------------------------------------------------------------
# 3. Plafonds par ligne
# ---------------------------------------------------------------------------


def _risk_components(risk_flags: Any, symbols: Sequence[str], exclude_n: int) -> tuple[pd.Series, pd.Series, pd.Series]:
    """(réduction ×0,5 ?, exclusion ?, description) par symbole.

    ``risk_flags`` : ``None`` ; Series/Mapping booléen (un drapeau R4, R11 ou R12) ;
    Series numérique = nombre de drapeaux R11 (1 : réduction, ≥ ``exclude_n`` :
    exclusion) ; DataFrame à colonnes ``R4``, ``R11`` (nombre), ``R12``… ; ou itérable
    de symboles (un drapeau chacun).
    """
    idx = pd.Index(list(symbols), dtype=object)
    reduce = pd.Series(False, index=idx, dtype=bool)
    exclude = pd.Series(False, index=idx, dtype=bool)
    desc = pd.Series("", index=idx, dtype=object)
    if risk_flags is None:
        return reduce, exclude, desc

    def numeric_part(col: pd.Series, name: str) -> None:
        vals = pd.to_numeric(col.reindex(idx), errors="coerce").fillna(0.0)
        if col.dtype == bool or pd.api.types.is_bool_dtype(col):
            vals = vals.astype(bool).astype(float)
        exc = vals >= exclude_n
        red = (vals >= 1) & ~exc
        exclude.loc[exc] = True
        reduce.loc[red] = True
        for s in idx[(vals >= 1).to_numpy()]:
            desc[s] = (desc[s] + " " if desc[s] else "") + f"{name}×{int(vals[s])}"

    if isinstance(risk_flags, pd.DataFrame):
        df = risk_flags.copy()
        df.index = df.index.astype(str)
        for col in df.columns:
            c = df[col]
            if str(col).upper().startswith("R11"):
                numeric_part(c, str(col))
            else:
                b = _flag_series(c, idx)
                reduce.loc[b] = True
                for s in idx[b.to_numpy()]:
                    desc[s] = (desc[s] + " " if desc[s] else "") + str(col)
        reduce &= ~exclude
        return reduce, exclude, desc
    if isinstance(risk_flags, (pd.Series, Mapping)):
        s = pd.Series(risk_flags)
        s.index = s.index.astype(str)
        if s.dtype == bool or pd.api.types.is_bool_dtype(s) or s.dtype == object:
            b = _flag_series(s, idx)
            reduce.loc[b] = True
            desc.loc[b] = "drapeau R"
        else:
            numeric_part(s, "R")
        return reduce, exclude, desc
    b = _flag_series(risk_flags, idx)
    reduce.loc[b] = True
    desc.loc[b] = "drapeau R"
    return reduce, exclude, desc


def line_caps(
    symbols: Iterable[str],
    country: pd.Series | Mapping[str, str] | None = None,
    liquidity_tier_flags: Any = None,
    spread_flags: Any = None,
    risk_flags: Any = None,
    base: float = 0.10,
    multipliers: Mapping[str, float] | None = None,
    *,
    floor: float = 0.02,
    low_liquidity_mult: float = 0.5,
    wide_spread_mult: float = 0.5,
    risk_flag_mult: float = 0.5,
    risk_exclude_flags: int = 2,
    detail: bool = False,
) -> pd.Series | pd.DataFrame:
    """Plafond de poids par ligne (spéc. §4.2.1 et §6).

    ``cap_i = base × m_pays × 0,5^[U6] × 0,5^[U7] × 0,5^[R]`` avec

    * ``m_pays`` : multiplicateur du pays du siège (:data:`SPEC_COUNTRY_MULTIPLIER` :
      CI 1,0 ; BJ 1,0 ; TG 0,9 ; SN 0,85 ; BF 0,75 ; ML 0,7 ; NE 0,6 ; pays inconnu :
      plus petit multiplicateur, par prudence) ;
    * U6 (``liquidity_tier_flags``) : MDV63 sous 2 M FCFA ;
    * U7 (``spread_flags``) : spread médian de clôture sur 120 séances > 1,5 % ;
    * R (``risk_flags``) : R4 (dégradation de notation), R11 avec **un** drapeau, R12 :
      une seule réduction ×0,5 même si plusieurs drapeaux de ce type sont levés ;
      R11 avec **deux drapeaux ou plus** : exclusion (plafond 0).

    **Plancher** : un plafond inférieur à ``floor`` (2 %) vaut 0 (ligne supprimée). Ex. :
    NE + U6 = 10 % × 0,6 × 0,5 = 3 % ; NE + U6 + U7 = 1,5 % → 0.

    ``country`` : Series/Mapping symbole → pays (défaut : :func:`brvm_alpha.reference.country_of`).
    Les drapeaux sont des Series/Mapping booléens ou des itérables de symboles.
    ``detail=True`` renvoie un DataFrame (composantes et motif) au lieu de la Series.
    """
    syms = _unique(symbols)
    idx = pd.Index(syms, dtype=object)
    mult = dict(SPEC_COUNTRY_MULTIPLIER if multipliers is None else multipliers)
    m_min = min(mult.values()) if mult else 1.0
    ctry = _labels_for(country, syms, "country")
    m_c = pd.Series([float(mult.get(c, m_min)) for c in ctry.to_numpy()], index=idx, dtype=float)
    u6 = _flag_series(liquidity_tier_flags, syms)
    u7 = _flag_series(spread_flags, syms)
    red, exc, rdesc = _risk_components(risk_flags, syms, int(risk_exclude_flags))
    raw = (
        float(base)
        * m_c
        * np.where(u6, low_liquidity_mult, 1.0)
        * np.where(u7, wide_spread_mult, 1.0)
        * np.where(red, risk_flag_mult, 1.0)
    )
    raw = pd.Series(np.where(exc, 0.0, raw), index=idx, dtype=float)
    cap = raw.where(raw >= float(floor) - _CAP_TOL, 0.0).rename("line_cap")
    if not detail:
        return cap
    reasons = []
    for s in syms:
        parts = [f"{base:.0%} × pays {ctry[s]} {m_c[s]:g}"]
        if u6[s]:
            parts.append(f"U6 ×{low_liquidity_mult:g}")
        if u7[s]:
            parts.append(f"U7 ×{wide_spread_mult:g}")
        if red[s]:
            parts.append(f"{rdesc[s] or 'drapeau R'} ×{risk_flag_mult:g}")
        if exc[s]:
            reasons.append(f"exclu : {rdesc[s]} (R11, {risk_exclude_flags} drapeaux ou plus)")
        elif cap[s] <= 0:
            reasons.append(" × ".join(parts) + f" = {raw[s]:.2%} < plancher {floor:.0%} : ligne supprimée")
        else:
            reasons.append(" × ".join(parts) + f" = {cap[s]:.2%}")
    return pd.DataFrame(
        {
            "country": ctry,
            "country_mult": m_c,
            "low_liquidity": u6,
            "wide_spread": u7,
            "risk_reduced": red,
            "risk_excluded": exc,
            "raw_cap": raw,
            "line_cap": cap,
            "cap_reason": pd.Series(reasons, index=idx, dtype=object),
        }
    )


# ---------------------------------------------------------------------------
# 4. Plafonds de groupe (secteur, pays, AES)
# ---------------------------------------------------------------------------


@dataclass(eq=False)
class GroupCap:
    """Plafond linéaire ``Σ_i a_i · w_i ≤ cap`` (coefficients ``a_i ≥ 0``).

    ``kind`` : ``"sector"``, ``"country"``, ``"aes_seat"``, ``"aes_lambda"`` ou
    ``"custom"`` ; ``coefficients`` : Series symbole → ``a_i`` (1 = appartenance ;
    exposition λ pour le bloc AES en exposition économique).
    """

    label: str
    kind: str
    cap: float
    coefficients: pd.Series

    def load(self, weights: pd.Series) -> float:
        """Charge ``Σ_i a_i w_i`` d'un portefeuille."""
        w = pd.Series(weights, dtype=float)
        w.index = w.index.astype(str)
        a = self.coefficients.reindex(w.index).fillna(0.0).astype(float)
        return float((a * w.fillna(0.0)).sum())


def _group_arrays(groups: Sequence[GroupCap], names: Sequence[str]) -> tuple[np.ndarray, np.ndarray]:
    """Matrice ``A`` (groupes × titres) et plafonds ``c`` restreints à ``names``.

    Les groupes sans membre parmi ``names`` ou de plafond infini sont ignorés.
    """
    rows, caps = [], []
    idx = pd.Index([str(s) for s in names], dtype=object)
    for gc in groups:
        if gc.cap is None or not np.isfinite(gc.cap):
            continue
        coef = pd.Series(gc.coefficients, dtype=float)
        coef.index = coef.index.astype(str)
        coef = coef[~coef.index.duplicated(keep="first")]
        a = coef.reindex(idx).fillna(0.0).clip(lower=0.0).to_numpy(dtype=float)
        if np.any(a > 0):
            rows.append(a)
            caps.append(max(float(gc.cap), 0.0))
    if not rows:
        return np.zeros((0, len(idx))), np.zeros(0)
    return np.vstack(rows), np.asarray(caps, float)


def sector_caps(
    sectors: pd.Series | Mapping[str, str],
    *,
    floor: float = 0.15,
    cap: float = 0.45,
    mult: float = 1.5,
) -> pd.Series:
    """Plafond par secteur ``w_s ≤ max(15 % ; min(45 % ; 1,5 × u_s))`` (spéc. §6).

    ``sectors`` : secteur de chaque titre de l'univers **éligible** à la date t ; ``u_s`` est
    la part (en nombre) du secteur dans cet univers. Étiquette manquante : groupe
    « __NA__ » plafonné de la même façon (prudence). Renvoie secteur → plafond.
    """
    lab = _labels_for(sectors, list(pd.Series(sectors).index.astype(str)), "sector")
    if lab.empty:
        return pd.Series(dtype=float, name="sector_cap")
    u = lab.value_counts(normalize=True)
    out = {s: max(float(floor), min(float(cap), float(mult) * float(u[s]))) for s in sorted(u.index)}
    return pd.Series(out, dtype=float, name="sector_cap")


def country_caps(
    countries: pd.Series | Mapping[str, str],
    reference: pd.Series | Mapping[str, float] | None = None,
    *,
    cap: float = 0.30,
    floor: float = 0.10,
    mult: float = 1.5,
    uncapped: Iterable[str] = ("CI",),
) -> pd.Series:
    """Plafond par pays du siège ``c ≠ CI`` : ``min(30 % ; max(10 % ; 1,5 × max(u_c, b_c)))``.

    ``countries`` : pays de chaque titre éligible en t (``u_c`` = part en nombre) ;
    ``reference`` : poids de référence ``b_c`` par capitalisation (point-in-time ; voir
    :func:`reference_weights_pit`). Sans ``reference``, ``b_c = 0`` : le plafond ne
    dépend que de ``u_c`` (plus prudent, sans anticipation). La CI (``uncapped``) n'a
    pas de plafond propre (spéc. §4.2.4). Renvoie pays → plafond.
    """
    lab = _labels_for(countries, list(pd.Series(countries).index.astype(str)), "country")
    if lab.empty:
        return pd.Series(dtype=float, name="country_cap")
    u = lab.value_counts(normalize=True)
    b = pd.Series(dtype=float) if reference is None else pd.Series(reference, dtype=float)
    skip = {str(c) for c in uncapped}
    out = {}
    for c in sorted(u.index):
        if c in skip:
            continue
        bc = float(b.get(c, 0.0)) if c in b.index and np.isfinite(b.get(c, np.nan)) else 0.0
        out[c] = min(float(cap), max(float(floor), float(mult) * max(float(u[c]), bc)))
    return pd.Series(out, dtype=float, name="country_cap")


def _lambda_aes(symbols: Sequence[str], aes: Sequence[str], exposure: pd.DataFrame | None = None) -> pd.Series:
    """Exposition économique λ de chaque titre au bloc AES (somme des pays AES)."""
    if exposure is None:
        from brvm_alpha import reference as ref

        exposure = ref.exposure_matrix(list(symbols))
    ex = exposure.copy()
    ex.index = ex.index.astype(str)
    cols = [c for c in ex.columns if str(c) in set(aes)]
    lam = ex[cols].sum(axis=1) if cols else pd.Series(0.0, index=ex.index)
    return lam.reindex(list(symbols)).fillna(0.0).astype(float).rename("lambda_aes")


def aes_caps(
    countries: pd.Series | Mapping[str, str],
    *,
    seat_reference: float | Mapping[str, float] | pd.Series | None,
    lambda_reference: float | Mapping[str, float] | pd.Series | None = None,
    lambda_aes: pd.Series | None = None,
    multiple: float = 1.25,
    aes_countries: Sequence[str] = SPEC_AES_COUNTRIES,
) -> list[GroupCap]:
    """Plafonds du bloc AES (BF + ML + NE), spéc. §4.2.3.

    * **siège** : ``Σ_{pays_i ∈ AES} w_i ≤ 1,25 × b_AES`` (``b_AES`` = part de
      capitalisation des sièges AES ; ≈ 8,5 % au 20/11/2026, soit un plafond ≈ 10,6 %) ;
    * **exposition λ** : ``Σ_i λ_i,AES · w_i ≤ 1,25 × λ_AES`` (``λ_AES`` = part de la
      capitalisation exposée aux pays AES, SNTS comprise via le Mali ; plafond ≈ 18 %).

    ``seat_reference`` / ``lambda_reference`` : nombre (part déjà sommée) ou table
    pays → poids (sommée sur les pays AES). ``lambda_aes`` : Series symbole → λ_AES
    (défaut : :func:`brvm_alpha.reference.exposure_matrix`). Une référence ``None``
    supprime le plafond correspondant.
    """
    lab = _labels_for(countries, list(pd.Series(countries).index.astype(str)), "country")
    aes = tuple(str(c) for c in aes_countries)

    def total(ref_: Any) -> float | None:
        if ref_ is None:
            return None
        if isinstance(ref_, (pd.Series, Mapping)):
            s = pd.Series(ref_, dtype=float)
            return float(s.reindex([c for c in s.index if str(c) in aes]).fillna(0.0).sum())
        return float(ref_)

    out: list[GroupCap] = []
    seat = total(seat_reference)
    if seat is not None:
        coef = pd.Series([1.0 if c in aes else 0.0 for c in lab.to_numpy()], index=lab.index, dtype=float)
        out.append(GroupCap("bloc AES (siège)", "aes_seat", float(multiple) * seat, coef))
    lam_ref = total(lambda_reference)
    if lam_ref is not None:
        lam = _lambda_aes(list(lab.index), aes) if lambda_aes is None else pd.Series(lambda_aes, dtype=float)
        lam.index = lam.index.astype(str)
        out.append(
            GroupCap("bloc AES (exposition λ)", "aes_lambda", float(multiple) * lam_ref, lam.reindex(lab.index).fillna(0.0))
        )
    return out


def build_group_caps(
    symbols: Iterable[str],
    sectors: pd.Series | Mapping[str, str] | None,
    countries: pd.Series | Mapping[str, str] | None,
    sector_cap: pd.Series | Mapping[str, float] | None = None,
    country_cap: pd.Series | Mapping[str, float] | None = None,
    extra: Iterable[GroupCap] = (),
) -> list[GroupCap]:
    """Liste des :class:`GroupCap` (un par secteur et par pays plafonné, plus ``extra``)."""
    syms = _unique(symbols)
    out: list[GroupCap] = []
    for kind, labels, caps in (("sector", sectors, sector_cap), ("country", countries, country_cap)):
        if caps is None:
            continue
        lab = _labels_for(labels, syms, kind)
        for g, c in pd.Series(caps, dtype=float).sort_index().items():
            coef = pd.Series((lab == str(g)).astype(float).to_numpy(), index=lab.index, dtype=float)
            name = "secteur" if kind == "sector" else "pays"
            out.append(GroupCap(f"{name} {g}", kind, float(c), coef))
    out.extend(extra)
    return out


def reference_weights_pit(
    close: pd.Series | Mapping[str, float],
    shares: pd.Series | Mapping[str, float],
) -> dict[str, pd.Series]:
    """Poids de référence **point-in-time** : ``{"seat": b_c, "exposure": b_λ}``.

    ``close`` : cours de clôture **non ajustés** à la date t ; ``shares`` : nombre de titres
    à la même date (``data.store.shares_outstanding_panel``). Capitalisation = cours ×
    titres, agrégée par pays du siège (``seat``) ou ventilée par exposition λ
    (``exposure``), via :func:`brvm_alpha.reference.reference_country_weights`. Le
    nombre de titres historique est une **reconstruction** (avis 303-2026 propagé avec
    les divisions) : hypothèse, pas une donnée publiée à chaque date.
    """
    from brvm_alpha import reference as ref

    px = pd.Series(close, dtype=float)
    px.index = px.index.astype(str)
    sh = pd.Series(shares, dtype=float)
    sh.index = sh.index.astype(str)
    common = [s for s in px.index if s in sh.index and np.isfinite(px[s]) and np.isfinite(sh[s]) and px[s] > 0 and sh[s] > 0]
    if not common:
        raise ValueError("reference_weights_pit : aucun titre avec cours et nombre de titres")
    return {
        "seat": ref.reference_country_weights(px[common], sh[common], by="country"),
        "exposure": ref.reference_country_weights(px[common], sh[common], by="exposure"),
    }


# ---------------------------------------------------------------------------
# 5. Équipondération projetée sur toutes les contraintes
# ---------------------------------------------------------------------------


def _feasible_clip(w: np.ndarray, upper: np.ndarray, a: np.ndarray, c: np.ndarray, budget: float) -> np.ndarray:
    """Rend ``w`` exactement réalisable en le **réduisant** (contraintes de couverture
    à coefficients ≥ 0 : réduire un poids ne viole jamais une autre contrainte)."""
    w = np.where(np.isfinite(w), w, 0.0)
    w = np.clip(w, 0.0, upper)
    for k in range(a.shape[0]):
        load = float(a[k] @ w)
        if load > c[k]:
            m = a[k] > 0
            w[m] = w[m] * (max(c[k], 0.0) / load)
    tot = float(w.sum())
    if tot > budget:
        w = w * (max(budget, 0.0) / tot)
    return w


def _progressive_fill(rates: np.ndarray, upper: np.ndarray, a: np.ndarray, c: np.ndarray, budget: float) -> np.ndarray:
    """Remplissage progressif (« water-filling ») pondéré.

    Tous les titres actifs montent ensemble au rythme ``rate_i`` (1 pour
    l'équipondération) ; un titre est gelé quand il atteint son plafond, tous les
    membres d'un groupe sont gelés quand le groupe est saturé, et l'on s'arrête quand
    le budget est investi. L'excédent d'un titre plafonné est ainsi redistribué aux
    autres **au prorata des rythmes** (à parts égales pour A). Le résultat est
    l'allocation max-min équitable (pondérée) de l'ensemble ``{0 ≤ w ≤ u, Aw ≤ c,
    1ᵀw ≤ B}`` (Bertsekas & Gallager, *Data Networks*, §6.5.2 ; Radunović & Le Boudec
    2007). Au plus ``n + k + 1`` étapes, chacune exacte (un minimum de rapports).
    """
    n = len(rates)
    w = np.zeros(n)
    if n == 0 or budget <= 0:
        return w
    k = a.shape[0]
    members = a > 0
    active = (rates > 0) & (upper > _CAP_TOL)
    for _ in range(2 * (n + k) + 4):
        if not active.any() or budget - w.sum() <= _CAP_TOL:
            break
        r = np.where(active, rates, 0.0)
        with np.errstate(divide="ignore", invalid="ignore"):
            t_name = np.where(active, (upper - w) / np.where(active, r, 1.0), np.inf)
        cand = [float(t_name.min())]
        if k:
            load_rate = a @ r
            slack = np.maximum(c - a @ w, 0.0)
            with np.errstate(divide="ignore", invalid="ignore"):
                t_grp = np.where(load_rate > 0, slack / np.where(load_rate > 0, load_rate, 1.0), np.inf)
            cand.append(float(t_grp.min()))
        else:
            t_grp = np.zeros(0)
        cand.append(max(budget - w.sum(), 0.0) / float(r.sum()))
        dt = max(min(cand), 0.0)
        w = w + dt * r
        full = active & (upper - w <= _CAP_TOL * np.maximum(1.0, upper))
        w = np.where(full, np.minimum(w, upper), w)
        frozen = full.copy()
        if k:
            sat = (c - a @ w) <= _CAP_TOL * np.maximum(1.0, np.abs(c))
            if sat.any():
                frozen |= members[sat].any(axis=0)
        if not frozen.any():
            # garde-fou numérique : on gèle l'élément qui a fixé le pas
            j = int(np.argmin(cand))
            if j == 0:
                frozen[int(np.argmin(t_name))] = True
            elif k and j == 1:
                frozen |= members[int(np.argmin(t_grp))]
            else:
                break
        active &= ~frozen
    return _feasible_clip(w, upper, a, c, budget)


def _lex_maxmin(rates: np.ndarray, upper: np.ndarray, a: np.ndarray, c: np.ndarray, total: float) -> np.ndarray | None:
    """Allocation max-min lexicographique (pondérée) avec ``Σw = total`` (PL HiGHS).

    Utilisée quand des plafonds **croisés** (secteur × pays × AES) empêchent le
    remplissage progressif d'investir autant que possible : on maximise d'abord
    l'investissement (``total`` = capacité maximale), puis l'égalité. Étape : ``max t``
    s.c. ``w_i ≥ t·rate_i`` (titres libres), ``w_j`` figés, ``Aw ≤ c``, ``Σw = total`` ;
    les titres dont la contrainte ``w_i ≥ t·rate_i`` a un multiplicateur dual > 0 sont
    figés à ``t*·rate_i`` (par complémentarité, ils valent ``t*`` dans **toute**
    solution optimale) ; au moins un par étape (somme des duaux = 1), donc au plus
    ``n`` PL.
    """
    n = len(rates)
    k = a.shape[0]
    fixed = np.full(n, np.nan)
    pos = rates > 0
    last: np.ndarray | None = None
    for _ in range(n + 1):
        free = np.isnan(fixed) & pos
        if not free.any():
            break
        idx = np.flatnonzero(free)
        rows = np.zeros((len(idx), n + 1))
        rows[np.arange(len(idx)), idx] = -1.0
        rows[:, n] = rates[idx]
        a_ub = np.vstack([rows, np.hstack([a, np.zeros((k, 1))])]) if k else rows
        b_ub = np.concatenate([np.zeros(len(idx)), c]) if k else np.zeros(len(idx))
        bounds = [
            (float(fixed[i]), float(fixed[i])) if np.isfinite(fixed[i]) else (0.0, float(upper[i])) for i in range(n)
        ] + [(0.0, None)]
        res = None
        for tot in (total, total * (1.0 - 1e-9)):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                res = optimize.linprog(
                    c=np.concatenate([np.zeros(n), [-1.0]]),
                    A_ub=a_ub,
                    b_ub=b_ub,
                    A_eq=np.concatenate([np.ones(n), [0.0]])[None, :],
                    b_eq=[tot],
                    bounds=bounds,
                    method="highs",
                )
            if res.status == 0:
                break
        if res is None or res.status != 0:
            break
        last = np.asarray(res.x[:n], float)
        t = float(res.x[n])
        marg = np.asarray(res.ineqlin.marginals[: len(idx)], float)
        blocked = marg < -1e-10
        if not blocked.any():
            blocked[int(np.argmin(marg))] = True
        for j in np.flatnonzero(blocked):
            i = idx[j]
            fixed[i] = min(max(t * rates[i], 0.0), upper[i])
    if last is None:
        return None
    w = np.where(np.isfinite(fixed), fixed, last)
    return _feasible_clip(w, upper, a, c, total)


def _allocate(
    names: Sequence[str],
    rates: pd.Series,
    upper: pd.Series,
    groups: Sequence[GroupCap],
    budget: float,
) -> tuple[pd.Series, dict[str, Any]]:
    """Allocation pondérée sous plafonds de ``names`` : remplissage progressif, puis
    repli PL lexicographique si l'investissement n'atteint pas la capacité maximale."""
    names = list(names)
    if not names:
        return pd.Series(dtype=float), {"solver": "vide", "max_investable": 0.0}
    u = upper.reindex(names).fillna(0.0).clip(lower=0.0).to_numpy(dtype=float)
    r = rates.reindex(names).fillna(0.0).clip(lower=0.0).to_numpy(dtype=float)
    a, c = _group_arrays(groups, names)
    w = _progressive_fill(r, u, a, c, budget)
    solver = "remplissage"
    cap_star = float(budget)
    if w.sum() < budget - _INVARIANT_TOL:
        cs = _max_investable(np.zeros(len(names)), u, a, c)
        cap_star = float(w.sum()) if cs is None else float(min(budget, cs))
        if cap_star > w.sum() + _INVARIANT_TOL:
            alt = _lex_maxmin(r, u, a, c, cap_star)
            if alt is not None and alt.sum() > w.sum() + 1e-10:
                w = alt
                solver = "pl_lexicographique"
    return pd.Series(w, index=pd.Index(names, dtype=object), dtype=float), {
        "solver": solver,
        "max_investable": max(cap_star, float(w.sum())),
    }


def _upper_series(upper: Any, names: Sequence[str], default: float) -> pd.Series:
    idx = pd.Index(list(names), dtype=object)
    if upper is None:
        return pd.Series(float(default), index=idx, dtype=float)
    if np.isscalar(upper):
        return pd.Series(float(upper), index=idx, dtype=float)  # type: ignore[arg-type]
    s = pd.Series(upper, dtype=float)
    s.index = s.index.astype(str)
    s = s[~s.index.duplicated(keep="first")]
    s = s.reindex(idx)
    return s.where(np.isfinite(s), 0.0).clip(lower=0.0).fillna(0.0)


def _rates_series(rates: Any, names: Sequence[str]) -> pd.Series:
    idx = pd.Index(list(names), dtype=object)
    if rates is None:
        return pd.Series(1.0, index=idx, dtype=float)
    s = pd.Series(rates, dtype=float)
    s.index = s.index.astype(str)
    s = s[~s.index.duplicated(keep="first")].reindex(idx)
    fill = float(s[np.isfinite(s) & (s > 0)].mean()) if (np.isfinite(s) & (s > 0)).any() else 1.0
    return s.where(np.isfinite(s) & (s > 0), fill)


def _active_constraints(w: pd.Series, upper: pd.Series, groups: Sequence[GroupCap], budget: float) -> list[str]:
    """Contraintes saturées (à 1e-9 près), en français."""
    out = []
    tol = 1e-9
    if abs(float(w.sum()) - budget) <= tol:
        out.append(f"exposition actions {budget:.0%} atteinte")
    for s, v in w.items():
        if v > 0 and v >= float(upper.get(s, np.inf)) - tol:
            out.append(f"plafond de ligne {s} : {float(upper[s]):.2%}")
    for gc in groups:
        load = gc.load(w)
        if load > 0 and load >= gc.cap - tol:
            out.append(f"{gc.label} : {load:.2%} = plafond {gc.cap:.2%}")
    return out


def audit_weights(
    weights: pd.Series,
    upper: pd.Series | float | None = None,
    groups: Sequence[GroupCap] = (),
    investable: float = 0.98,
    min_weight: float = 0.0,
) -> dict[str, float]:
    """Violations maximales (0 = respectée) : ``negative``, ``budget`` (au-delà de
    ``investable``), ``line`` (au-delà de ``upper``), ``groups``, ``min_weight``
    (lignes non nulles sous le plancher). Sert aux invariants (≤ 1e-9)."""
    w = pd.Series(weights, dtype=float).fillna(0.0)
    w.index = w.index.astype(str)
    nz = w[w > 1e-15]
    u = _upper_series(upper, list(w.index), np.inf) if upper is not None else pd.Series(np.inf, index=w.index)
    return {
        "negative": float(max(-float(w.min()), 0.0)) if len(w) else 0.0,
        "budget": float(max(float(w.sum()) - float(investable), 0.0)),
        "line": float(max((w - u).max(), 0.0)) if len(w) else 0.0,
        "groups": max((max(gc.load(w) - gc.cap, 0.0) for gc in groups), default=0.0),
        "min_weight": float(max((float(min_weight) - nz).max(), 0.0)) if len(nz) else 0.0,
    }


def equal_weight_with_caps(
    selected: Iterable[str],
    upper: pd.Series | Mapping[str, float] | float | None = None,
    groups: Sequence[GroupCap] = (),
    investable: float = 0.98,
    *,
    rates: pd.Series | Mapping[str, float] | None = None,
    min_weight: float = 0.02,
    reserve: Iterable[str] = (),
    min_names: int = 0,
    capacity_reserve: Iterable[str] = (),
    max_names: int | None = None,
    priority: pd.Series | Mapping[str, float] | None = None,
) -> pd.Series:
    """Équipondération de ``selected`` projetée **exactement** sur toutes les contraintes.

    1. Allocation (:func:`_progressive_fill`) : on part de ``B/n`` pour tous ; un titre
       qui atteint son plafond (``upper`` : ligne et liquidité) est gelé et son excédent
       est redistribué à parts égales aux autres ; un groupe saturé (secteur, pays, AES
       siège ou λ : :class:`GroupCap`) gèle ses membres ; arrêt à ``Σw = B``
       (``investable`` = 98 %). Si des plafonds croisés empêchent d'investir la capacité
       maximale (PL), repli : PL max-min lexicographique à ``Σw = capacité``.
    2. **Plancher** : une ligne sous ``min_weight`` (2 %) est supprimée (la moins bien
       classée d'abord, ``priority`` : plus petit = meilleur, défaut : ordre de
       ``selected``) et l'allocation est refaite.
    3. **Complément** : si l'on passe sous ``min_names`` lignes, les candidats de
       ``reserve`` sont essayés dans l'ordre ; un candidat est retenu si toutes les
       lignes restent ≥ ``min_weight``.
    4. **Complément de capacité** : si les plafonds empêchent d'investir ``investable``,
       les candidats de ``capacity_reserve`` (les 50 % supérieurs dans
       :func:`target_portfolio`) sont essayés par rang, sans dépasser ``max_names``
       lignes ; un candidat n'est retenu que s'il **augmente** l'investissement et que
       toutes les lignes restent ≥ ``min_weight``. *Interprétation* : la spécification
       demande à la fois 98 % d'exposition et des entrées depuis les 30 % supérieurs ;
       quand les deux sont incompatibles, l'exposition prime, dans la bande des 50 %.

    ``rates`` (optionnel) remplace l'équipondération par une pondération
    proportionnelle à ``rates`` (variante G : HRP incliné), avec la même projection.

    Invariants : ``Σw ≤ investable``, aucun plafond violé de plus de 1e-9, toute ligne
    non nulle ≥ ``min_weight``. Si le budget n'est pas atteignable, le reste demeure en
    liquidités et c'est **signalé** (``attrs["feasible_full_budget"] = False`` et
    ``attrs["messages"]``).

    Returns
    -------
    pandas.Series
        Poids (index : ``selected`` puis candidats essayés). ``attrs`` : ``invested``,
        ``cash`` (= 1 − investi), ``shortfall`` (= investable − investi),
        ``max_investable``, ``feasible_full_budget``, ``solver``, ``removed``
        (symbole → motif), ``added``, ``rejected``, ``active_constraints``,
        ``messages``.
    """
    budget = float(investable)
    if not 0.0 <= budget <= 1.0:
        raise ValueError("investable doit appartenir à [0, 1]")
    names = _unique(selected)
    pool = [s for s in _unique(reserve) if s not in names]
    cap_pool = [s for s in _unique(capacity_reserve) if s not in names]
    all_names = _unique(names + pool + cap_pool)
    upper_s = _upper_series(upper, all_names, budget)
    rates_s = _rates_series(rates, all_names)
    if priority is None:
        prio = {s: float(i) for i, s in enumerate(all_names)}
    else:
        ps = pd.Series(priority, dtype=float)
        ps.index = ps.index.astype(str)
        prio = {s: float(ps.get(s, np.inf)) if np.isfinite(ps.get(s, np.inf)) else 1e12 + i for i, s in enumerate(all_names)}
    floor = float(min_weight)
    removed: dict[str, str] = {}
    current = []
    for s in names:
        if upper_s[s] < floor - _CAP_TOL or upper_s[s] <= 0:
            removed[s] = f"plafond {upper_s[s]:.2%} sous le plancher {floor:.0%}"
        else:
            current.append(s)

    def run(cur: list[str]) -> tuple[pd.Series, dict[str, Any]]:
        return _allocate(cur, rates_s, upper_s, groups, budget)

    w, info = run(current)
    while True:
        small = [s for s in current if w[s] < floor - _CAP_TOL]
        if not small:
            break
        worst = max(small, key=lambda s: (prio[s], s))
        removed[worst] = f"poids {w[worst]:.2%} sous le plancher {floor:.0%} (plafonds de groupe) : ligne supprimée"
        current.remove(worst)
        w, info = run(current)
    added: list[str] = []
    rejected: list[str] = []
    for cand in sorted(pool, key=lambda s: (prio[s], s)):
        if len(current) >= int(min_names):
            break
        if upper_s[cand] < floor - _CAP_TOL:
            rejected.append(cand)
            continue
        trial = sorted(current + [cand], key=lambda s: (prio[s], s))
        w2, info2 = run(trial)
        if all(w2[s] >= floor - _CAP_TOL for s in trial) and w2.sum() >= w.sum() - 1e-12:
            current, w, info = trial, w2, info2
            added.append(cand)
        else:
            rejected.append(cand)
    capacity_added: list[str] = []
    limit = len(all_names) if max_names is None else int(max_names)
    for cand in sorted(cap_pool, key=lambda s: (prio[s], s)):
        if float(w.sum()) >= budget - _INVARIANT_TOL or len(current) >= limit:
            break
        if cand in current or cand in rejected or upper_s[cand] < floor - _CAP_TOL:
            continue
        trial = sorted(current + [cand], key=lambda s: (prio[s], s))
        w2, info2 = run(trial)
        if all(w2[s] >= floor - _CAP_TOL for s in trial) and w2.sum() > w.sum() + 1e-9:
            current, w, info = trial, w2, info2
            capacity_added.append(cand)
    tried = set(added) | set(rejected) | set(capacity_added)
    out_index = names + [s for s in all_names if s not in names and s in tried]
    out = pd.Series(0.0, index=pd.Index(out_index, dtype=object), dtype=float, name="weight")
    out.loc[w.index] = w.to_numpy()
    invested = float(out.sum())
    shortfall = max(budget - invested, 0.0)
    feasible = shortfall <= _INVARIANT_TOL
    messages = []
    if not feasible and current:
        messages.append(
            f"budget de {budget:.0%} non atteignable sous les plafonds : {invested:.2%} investis, "
            f"{shortfall:.2%} de plus restent en liquidités (signalé)"
        )
    if len(current) < int(min_names):
        messages.append(f"{len(current)} lignes seulement (minimum visé : {int(min_names)})")
    out.attrs.update(
        {
            "method": "equal" if rates is None else "weighted",
            "solver": info.get("solver", "vide"),
            "investable": budget,
            "invested": invested,
            "cash": 1.0 - invested,
            "shortfall": shortfall,
            "max_investable": float(info.get("max_investable", invested)),
            "feasible_full_budget": bool(feasible),
            "n_names": int((out > 0).sum()),
            "removed": dict(removed),
            "added": list(added),
            "capacity_added": list(capacity_added),
            "rejected": list(rejected),
            "active_constraints": _active_constraints(out[out > 0], upper_s, groups, budget),
            "messages": messages,
        }
    )
    return out


# ---------------------------------------------------------------------------
# 7. Covariance hebdomadaire, variantes G (HRP incliné) et H (moyenne-variance)
# ---------------------------------------------------------------------------


def weekly_returns(
    returns: pd.DataFrame,
    asof: Any = None,
    *,
    freq: str = "W-FRI",
    exclude_windows: Iterable[tuple[Any, Any]] | None = (("2021-05-06", "2021-06-25"),),
    drop_incomplete: bool = True,
    usable: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Rendements hebdomadaires (semaines civiles closes le vendredi) composés.

    ``R_sem = Π (1 + r_j) − 1`` sur les séances de la semaine où ``r_j`` est observé ;
    semaine sans aucune observation : NaN. Seules les séances ``≤ asof`` sont lues (pas
    de biais d'anticipation) ; la dernière semaine, incomplète si ``asof`` n'est pas un
    vendredi, est écartée (``drop_incomplete``). ``exclude_windows`` : séances mises à
    NaN avant agrégation (trou de BOC de 2021, spéc. §3.1.3). ``usable`` : masque
    booléen date × symbole (``data.store.stats_mask``) ; les rendements non utilisables
    (``multi_session``, suspendus, fenêtre exclue) sont passés à NaN avant agrégation.
    """
    if not isinstance(returns, pd.DataFrame):
        raise TypeError("returns doit être un DataFrame (date × symbole)")
    r = returns.sort_index().astype(float)
    r.index = pd.DatetimeIndex(r.index)
    if asof is not None:
        r = r.loc[: pd.Timestamp(asof)]
    r = r.where(np.isfinite(r))
    if usable is not None:
        m = usable.copy()
        m.index = pd.DatetimeIndex(m.index)
        m.columns = m.columns.astype(str)
        r.columns = r.columns.astype(str)
        m = m.reindex(index=r.index, columns=r.columns)
        r = r.where(m.fillna(False).astype(bool))
    for lo, hi in exclude_windows or ():
        r.loc[pd.Timestamp(lo) : pd.Timestamp(hi)] = np.nan
    if r.empty:
        return pd.DataFrame(columns=r.columns, dtype=float)
    weekly = (1.0 + r).resample(freq).prod(min_count=1) - 1.0
    if drop_incomplete and asof is not None and len(weekly) and weekly.index[-1] > pd.Timestamp(asof):
        weekly = weekly.iloc[:-1]
    return weekly.dropna(how="all")


def weekly_covariance(
    returns: pd.DataFrame,
    asof: Any = None,
    *,
    weeks: int = 104,
    min_weeks: int = 52,
    shrinkage_floor: float = 0.5,
    freq: str = "W-FRI",
    exclude_windows: Iterable[tuple[Any, Any]] | None = (("2021-05-06", "2021-06-25"),),
    annualize: bool = False,
    periods_per_year: int = 52,
    usable: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Covariance de Ledoit-Wolf (cible corrélation constante) des rendements hebdomadaires.

    Spéc. §6 : W-FRI, 104 dernières semaines, au moins 52 observations par titre (les
    autres sont exclus, ``attrs["dropped"]``), **plancher d'intensité** 0,5 : si
    l'intensité estimée δ* est plus faible, on impose δ = 0,5. Jamais une volatilité
    quotidienne × √252. Échelle hebdomadaire, ou annuelle (× 52) avec ``annualize``.
    ``attrs`` : ``shrinkage`` (appliquée), ``shrinkage_estimated``, ``n_weeks``,
    ``dropped``, ``freq``. ``usable`` : voir :func:`weekly_returns`.
    """
    wk = weekly_returns(returns, asof, freq=freq, exclude_windows=exclude_windows, usable=usable)
    wk = wk.iloc[-weeks:]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        cov = ledoit_wolf_cov(wk, target="constant_correlation", min_periods=int(min_weeks))
        est = float(cov.attrs.get("shrinkage", np.nan))
        if cov.shape[0] and (not np.isfinite(est) or est < float(shrinkage_floor)):
            cov = ledoit_wolf_cov(
                wk, target="constant_correlation", min_periods=int(min_weeks), shrinkage=float(shrinkage_floor)
            )
    attrs = dict(cov.attrs)
    if annualize:
        cov = cov * float(periods_per_year)
    cov.attrs.update(attrs)
    cov.attrs.update(
        {
            "shrinkage_estimated": est,
            "shrinkage": float(attrs.get("shrinkage", np.nan)),
            "n_weeks": len(wk),
            "freq": freq,
            "annualized": bool(annualize),
        }
    )
    return cov


def _cov_names(cov: pd.DataFrame | None, names: Sequence[str]) -> list[str]:
    """Titres de ``names`` dont la covariance est complète et la variance > 0."""
    if cov is None or cov.empty:
        return []
    ok = [s for s in names if s in cov.index and s in cov.columns]
    if not ok:
        return []
    sub = cov.loc[ok, ok].to_numpy(dtype=float)
    good = np.isfinite(sub).all(axis=1) & (np.diag(sub) > 0)
    return [s for s, g in zip(ok, good) if g]


def hrp_tilt_rates(
    names: Iterable[str],
    scores: pd.Series | Mapping[str, float],
    cov: pd.DataFrame | None,
    *,
    gamma: float = 0.5,
    linkage: str = "single",
    distance_of_distances: bool = True,
) -> tuple[pd.Series, dict[str, Any]]:
    """Rythmes de la variante G : ``w ∝ w_HRP · exp(γ·z)`` (spéc. §3.4, §6).

    HRP (López de Prado 2016, :func:`~brvm_alpha.portfolio.risk.hrp_weights`, lien
    ``single``, ``distance_of_distances=True``) sur la covariance hebdomadaire rétrécie
    (:func:`weekly_covariance`) ; ``z`` = z-score des scores **sur la sélection**,
    écrêté à ±3 (même convention que ``build_portfolio(method="hrp_tilt")``). Un titre
    sans covariance (moins de 52 semaines) reçoit le rythme moyen ``1/n`` (repli
    équipondéré, signalé). La projection sur les plafonds est celle de
    :func:`equal_weight_with_caps` (``rates=``).
    """
    syms = _unique(names)
    n = len(syms)
    sc = pd.Series(scores, dtype=float)
    sc.index = sc.index.astype(str)
    ok = _cov_names(cov, syms)
    rates = pd.Series(1.0 / n if n else 0.0, index=pd.Index(syms, dtype=object), dtype=float, name="rate")
    info: dict[str, Any] = {"hrp": pd.Series(dtype=float), "no_cov": [s for s in syms if s not in ok]}
    if ok:
        sub = cov.loc[ok, ok]  # type: ignore[union-attr]
        hrp = (
            hrp_weights(sub, linkage_method=linkage, distance_of_distances=distance_of_distances)
            if len(ok) > 1
            else pd.Series([1.0], index=ok)
        )
        z = _zscore(sc.reindex(ok).fillna(0.0).to_numpy(dtype=float))
        raw = hrp.to_numpy(dtype=float) * np.exp(float(gamma) * z)
        raw = raw / raw.sum() * (len(ok) / n)
        rates.loc[ok] = raw
        info["hrp"] = hrp.rename("hrp")
    return rates, info


def central_one_way_cost(costs: CostModel | None = None, *, half_spread: float | None = None, participation: float = 0.01) -> float:
    """**Estimation** du coût aller central d'un titre médian (spéc. §7.2).

    ``courtage × (1 + taxe) + BRVM + DC/BR + redevance + mult × demi-spread + κ·√π`` ;
    défauts : demi-spread 0,35 %, participation 1 % → ≈ 1,75 %. Les taux de courtage,
    de taxe et d'impact sont des **hypothèses** (en partie [NON VÉRIFIÉ]).
    """
    cm = CostModel() if costs is None else costs
    hs = cm.half_spread_default if half_spread is None else float(half_spread)
    mult = float(getattr(cm, "half_spread_mult", 1.0))
    return float(cm.rate() + mult * hs + cm.impact_coef * math.sqrt(max(float(participation), 0.0)))


def _prune_refill(
    w: pd.Series,
    upper: pd.Series,
    groups: Sequence[GroupCap],
    budget: float,
    min_weight: float,
    priority: Mapping[str, float],
) -> tuple[pd.Series, dict[str, str]]:
    """Supprime les lignes ``0 < w < min_weight`` (la moins bien classée d'abord) et
    redistribue au prorata des poids restants, sous les mêmes plafonds."""
    removed: dict[str, str] = {}
    w = w.copy()
    target = float(w.sum())
    while True:
        small = [s for s in w.index if 0 < w[s] < min_weight - _CAP_TOL]
        if not small:
            break
        worst = max(small, key=lambda s: (priority.get(s, np.inf), s))
        removed[worst] = f"poids {w[worst]:.2%} sous le plancher {min_weight:.0%} : ligne supprimée"
        w[worst] = 0.0
        keep = [s for s in w.index if w[s] > 0]
        if not keep:
            break
        alloc, _ = _allocate(keep, w[keep], upper, groups, min(target, budget))
        w.loc[:] = 0.0
        w.loc[alloc.index] = alloc.to_numpy()
    return w, removed


def mv_alpha_weights(
    names: Iterable[str],
    scores: pd.Series | Mapping[str, float],
    cov_annual: pd.DataFrame | None,
    upper: pd.Series,
    groups: Sequence[GroupCap],
    investable: float = 0.98,
    *,
    base_weights: pd.Series,
    held_weights: pd.Series | None = None,
    ic: float = 0.02,
    risk_aversion: float = 5.0,
    tcost: float | None = None,
    kelly_fraction: float = 0.25,
    kelly_fraction_max: float = 0.5,
    kelly_max_gross: float = 1.0,
    min_weight: float = 0.02,
    min_names: int = 12,
    priority: Mapping[str, float] | None = None,
) -> tuple[pd.Series, dict[str, Any]]:
    """Variante H : moyenne-variance rétrécie, puis Kelly fractionnel sur les poids actifs.

    1. Alpha de Grinold ``α_i = IC_post · σ_i · z_i`` (:func:`grinold_alpha`, IC 0,02 ;
       ``σ_i`` annualisée tirée de la covariance hebdomadaire × 52 ; ``z_i`` = score
       composite, déjà standardisé sur l'univers).
    2. :func:`build_portfolio` (``method="mv_alpha"``, λ = 5, κ = coût aller central
       :func:`central_one_way_cost`, plafonds de ligne et de groupe via ``liquidity`` et
       ``group_caps``) sur la **sélection** de A ; les titres sans covariance gardent
       leur poids de A.
    3. Kelly fractionnel sur les poids **actifs** ``a = w_MV − w_A`` (``w_A`` =
       ``base_weights``, l'équipondération plafonnée de A sur la même sélection —
       *interprétation* du « w_EW » du §6) : ``s = min(1 ; clip(f · aᵀα / aᵀΣa, 0,
       max_gross))`` avec ``f = min(0,25 ; 0,5)``. ``w_H = w_A + s·a`` : combinaison
       convexe de deux portefeuilles réalisables, donc réalisable.
    4. Lignes sous 2 % supprimées et redistribuées (:func:`_prune_refill`).

    Hypothèses (non vérifiées) : α annualisé, κ non amorti (le §6 dit « κ = coût aller
    central ») ; IC_post 0,02 est un a priori, pas une mesure.
    """
    syms = _unique(names)
    base = pd.Series(base_weights, dtype=float)
    base.index = base.index.astype(str)
    base = base.reindex(syms).fillna(0.0)
    prio = dict(priority or {s: float(i) for i, s in enumerate(syms)})
    kappa = central_one_way_cost() if tcost is None else float(tcost)
    info: dict[str, Any] = {"tcost": kappa, "kelly_scale": 0.0, "alpha": pd.Series(dtype=float), "no_cov": []}
    mv = [s for s in _cov_names(cov_annual, syms) if base.get(s, 0.0) > 0 or upper.get(s, 0.0) >= min_weight]
    info["no_cov"] = [s for s in syms if s not in mv]
    if len(mv) < 2 or base.sum() <= 0:
        info["message"] = "variante H : moins de 2 titres avec covariance, poids de A conservés"
        return base.rename("weight"), info
    fixed = [s for s in syms if s not in mv]
    fixed_w = base.reindex(fixed).fillna(0.0)
    budget_mv = float(investable) - float(fixed_w.sum())
    sig = cov_annual.loc[mv, mv]  # type: ignore[union-attr]
    vol = pd.Series(np.sqrt(np.diag(sig.to_numpy(dtype=float))), index=mv)
    sc = pd.Series(scores, dtype=float)
    sc.index = sc.index.astype(str)
    alpha = grinold_alpha(sc.reindex(mv).fillna(0.0), vol, ic=float(ic))
    info["alpha"] = alpha
    g_mv = []
    for gc in groups:
        load_fixed = gc.load(fixed_w) if len(fixed_w) else 0.0
        coef = pd.Series(gc.coefficients, dtype=float)
        coef.index = coef.index.astype(str)
        g_mv.append(GroupCap(gc.label, gc.kind, max(gc.cap - load_fixed, 0.0), coef.reindex(mv).fillna(0.0)))
    up_mv = upper.reindex(mv).fillna(0.0)
    if budget_mv <= 1e-12 or float(up_mv.max()) < min_weight:
        info["message"] = "variante H : aucun budget disponible pour l'optimisation, poids de A conservés"
        return base.rename("weight"), info
    cons = Constraints(
        long_only=True,
        max_weight=float(min(1.0, up_mv.max())),
        min_weight=float(min_weight),
        max_names=len(mv),
        min_names=min(int(min_names), len(mv)),
        max_sector_weight=1.0,
        max_country_weight=1.0,
        cash_buffer=float(min(max(1.0 - budget_mv, 0.0), 1.0 - 1e-12)),
    )
    prev = None if held_weights is None else pd.Series(held_weights, dtype=float).reindex(mv).fillna(0.0)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        w_mv = build_portfolio(
            alpha,
            sig,
            cons,
            liquidity=up_mv,
            prev_weights=prev,
            method="mv_alpha",
            risk_aversion=float(risk_aversion),
            tcost=kappa,
            group_caps=g_mv,
        )
    info["mv_solver"] = w_mv.attrs.get("solver")
    w_mv = w_mv.reindex(mv).fillna(0.0)
    if w_mv.sum() <= 1e-12:
        info["message"] = "variante H : optimisation sans solution, poids de A conservés"
        return base.rename("weight"), info
    active = w_mv - base.reindex(mv)
    s = fractional_kelly_scale(
        alpha,
        sig,
        fraction=float(min(kelly_fraction, kelly_fraction_max)),
        max_gross=float(kelly_max_gross),
        weights=active,
        normalize=False,
    )
    s = float(min(1.0, max(s, 0.0)))
    info["kelly_scale"] = s
    info["active_alpha"] = float(active.to_numpy() @ alpha.to_numpy())
    if s <= 0.0:
        info["message"] = (
            "variante H : alpha actif aᵀα ≤ 0 (l'écart MV − A réduit surtout le risque) : échelle de Kelly "
            "nulle, poids de A conservés (règle du §6 appliquée à la lettre)"
        )
    w = base.copy()
    w.loc[mv] = base.reindex(mv).to_numpy() + s * active.to_numpy()
    w = w.clip(lower=0.0)
    w, removed = _prune_refill(w, upper, groups, float(investable), float(min_weight), prio)
    w = pd.Series(
        _feasible_clip(
            w.to_numpy(dtype=float),
            upper.reindex(w.index).fillna(0.0).to_numpy(dtype=float),
            *_group_arrays(groups, list(w.index)),
            float(investable),
        ),
        index=w.index,
        dtype=float,
        name="weight",
    )
    info["removed"] = removed
    return w, info


# ---------------------------------------------------------------------------
# 6. Chaîne complète
# ---------------------------------------------------------------------------


def _resolve_references(
    ctx: Mapping[str, Any],
    elig: Sequence[str],
    countries: pd.Series,
    p: Mapping[str, Any],
    messages: list[str],
) -> tuple[pd.Series | None, float, float | None]:
    """(b_c par pays ou None, référence AES siège, référence AES λ ou None), sans anticipation.

    Sans poids de référence point-in-time, la référence AES par siège est la part en
    nombre des sièges AES parmi les éligibles, et le plafond en exposition λ n'est pas
    appliqué (une part en nombre sous-estimerait fortement le poids de SNTS et rendrait
    ce plafond artificiellement contraignant).
    """
    from brvm_alpha import reference as ref

    aes = tuple(p["aes_countries"])
    seat: pd.Series | None = None
    expo: pd.Series | None = None
    asof = ctx.get("asof")
    rw = ctx.get("reference_weights")
    if isinstance(rw, str):
        if rw != "snapshot_20261120":
            raise ValueError("reference_weights : seule la chaîne 'snapshot_20261120' est reconnue")
        seat = pd.Series(ref.REFERENCE_COUNTRY_WEIGHTS_20261120, dtype=float)
        if asof is None or pd.Timestamp(asof) < _SNAPSHOT_DATE:
            messages.append(
                "ATTENTION : poids de référence b_c figés au 20/11/2026 utilisés avant cette date "
                "(anticipation possible ; réservé aux contrôles de forme)"
            )
    elif isinstance(rw, Mapping) and ("seat" in rw or "exposure" in rw):
        seat = None if rw.get("seat") is None else pd.Series(rw["seat"], dtype=float)
        expo = None if rw.get("exposure") is None else pd.Series(rw["exposure"], dtype=float)
    elif rw is not None:
        seat = pd.Series(rw, dtype=float)
    elif ctx.get("close") is not None and ctx.get("shares") is not None:
        pit = reference_weights_pit(ctx["close"], ctx["shares"])
        seat, expo = pit["seat"], pit["exposure"]
    else:
        messages.append(
            "poids de référence b_c absents (ni close × shares ni reference_weights) : plafonds pays sur u_c seul "
            "et références AES en nombre de titres éligibles (approximation sans anticipation)"
        )
    lab = countries.reindex(list(elig))
    if seat is not None:
        seat.index = seat.index.astype(str)
        seat_aes = float(seat.reindex([c for c in seat.index if c in aes]).fillna(0.0).sum())
    else:
        seat_aes = float(lab.isin(aes).mean()) if len(lab) else 0.0
    lam_aes: float | None = None
    if ctx.get("lambda_reference") is not None:
        lam_aes = float(ctx["lambda_reference"])
    elif expo is not None:
        expo.index = expo.index.astype(str)
        lam_aes = float(expo.reindex([c for c in expo.index if c in aes]).fillna(0.0).sum())
    else:
        messages.append(
            "plafond AES en exposition λ non appliqué : référence λ point-in-time absente "
            "(fournir close et shares, ou reference_weights={'seat', 'exposure'})"
        )
    return seat, seat_aes, lam_aes


def _cov_from_context(ctx: Mapping[str, Any], p: Mapping[str, Any]) -> pd.DataFrame:
    """Covariance hebdomadaire (échelle hebdomadaire) depuis le contexte."""
    if ctx.get("weekly_cov") is not None:
        cov = ctx["weekly_cov"].copy()
        cov.index = cov.index.astype(str)
        cov.columns = cov.columns.astype(str)
        return cov
    rets = ctx.get("returns")
    if rets is None and ctx.get("tr_index") is not None:
        lv = ctx["tr_index"].sort_index().astype(float)
        rets = lv / lv.shift(1) - 1.0
    if rets is None:
        raise ValueError(
            "variantes G et H : covariance requise (context['weekly_cov'] ou context['returns'] quotidiens "
            "ou context['tr_index'])"
        )
    rets = rets.copy()
    rets.columns = rets.columns.astype(str)
    return weekly_covariance(
        rets,
        ctx.get("asof"),
        weeks=int(p["cov_weeks"]),
        min_weeks=int(p["cov_min_weeks"]),
        shrinkage_floor=float(p["cov_shrinkage_floor"]),
        freq=str(p["cov_freq"]),
        exclude_windows=p["exclude_stats_windows"],
        usable=ctx.get("stats_mask"),
    )


def target_portfolio(
    scores: pd.Series | Mapping[str, float],
    eligible: Any,
    held_weights: pd.Series | Mapping[str, float] | Iterable[str] | None = None,
    context: Mapping[str, Any] | None = None,
    params: Mapping[str, Any] | None = None,
) -> tuple[pd.Series, dict[str, Any]]:
    """Portefeuille cible v1 à la date de décision t (spéc. §6) : ``(poids, diagnostics)``.

    Enchaîne :func:`n_holdings` → :func:`select_with_band` → :func:`line_caps` (et
    :func:`liquidity_caps`) → :func:`sector_caps` / :func:`country_caps` /
    :func:`aes_caps` → :func:`equal_weight_with_caps` (A), ou HRP incliné (G,
    ``params["weighting"] = "hrp_tilt"``) ou moyenne-variance + Kelly actif (H,
    ``"mv_alpha"``).

    Parameters
    ----------
    scores
        Score composite ``S_i,t`` (déjà standardisé ; plus grand = mieux).
    eligible
        Univers éligible en t (U1-U10 appliqués par l'appelant) : Series booléenne ou
        itérable de symboles.
    held_weights
        Poids détenus avant le rebalancement (bande de rotation ; coût de rotation de H).
    context
        Données **connues en t** (toutes facultatives) :

        * ``capital`` (K, FCFA ; défaut ``params["capital"]``) ; ``asof`` (date t) ;
        * ``sectors``, ``countries`` (défaut : :mod:`brvm_alpha.reference`) ;
        * ``mdv63`` (valeur médiane échangée sur 63 séances, séances sans échange = 0) :
          plafond de liquidité ``0,10 × MDV63 × 20 / K`` et drapeau U6 (< 2 M FCFA) ;
          ``low_liquidity`` (drapeau U6 imposé) ;
        * ``spread`` (spread médian de clôture sur 120 séances) → U7 (> 1,5 %), ou
          ``wide_spread`` (drapeau U7 imposé) ;
        * ``risk_flags`` (R4, R11, R12 ; voir :func:`line_caps`) ; ``no_buy`` (titres à
          achat bloqué : R1, R2, R5, R9, règles pays — un titre détenu peut être
          conservé, sans renforcement) ;
        * ``close`` + ``shares`` (poids de référence ``b_c`` point-in-time,
          :func:`reference_weights_pit`) ou ``reference_weights`` (Series b_c, dict
          ``{"seat", "exposure"}``, ou ``"snapshot_20261120"``) ; ``lambda_aes`` ;
        * ``country_cap_mult`` (pays → multiplicateur, p. ex. 0,75) et
          ``country_cap_overrides`` (pays → plafond absolu) : règles d'événements pays ;
        * G et H : ``weekly_cov`` (covariance hebdomadaire) ou ``returns`` (rendements
          quotidiens, tronqués à t par :func:`weekly_returns`) ou ``tr_index`` ;
          ``stats_mask`` (``data.store.stats_mask`` : rendements multi-séances exclus).

        ``mdv63`` s'obtient par ``average_daily_value(value, window=63, asof=t,
        stat="median")`` (séances sans échange comptées à 0).
    params
        Surcharges de :data:`PORTFOLIO_V1_DEFAULTS` ou dict du YAML de stratégie.

    Returns
    -------
    (pandas.Series, dict)
        Poids cibles (index trié : scores ∪ éligibles ∪ détenus ; ``Σw ≤ 0,98``) et
        diagnostics : ``mode`` (``"selection"``, ``"repli"``, ``"vide"``), ``weighting``,
        ``n_eligible``, ``n_target``, ``n_holdings``, ``entry_rank`` / ``exit_rank``,
        ``invested``, ``cash``, ``max_investable``, ``feasible_full_budget``,
        ``active_constraints``, ``caps`` (ligne, liquidité, plafond effectif, secteur,
        pays, AES), ``reasons`` (motif de chaque inclusion ou exclusion), ``table``
        (DataFrame par titre), ``violations`` (audit, ≤ 1e-9), ``messages``
        (hypothèses et alertes), ``params``. La bande de non-transaction et le
        plafond de rotation (:func:`apply_no_trade_band`, :func:`cap_turnover`) sont
        appliqués ensuite par l'appelant (moteur d'exécution).

    Rien ici ne garantit un rendement : c'est une règle de construction, dont la valeur
    reste à **mesurer** (validation pré-enregistrée, spéc. §8).
    """
    p = portfolio_params(params)
    ctx = dict(context or {})
    messages: list[str] = []
    sc = pd.Series(scores, dtype=float)
    sc.index = sc.index.astype(str)
    sc = sc[~sc.index.duplicated(keep="first")]
    elig = _symbols(eligible)
    held = _held_series(held_weights)
    universe = sorted(set(sc.index) | set(elig) | set(held.index))
    budget = float(p["gross_equity"])
    capital = float(ctx.get("capital", p["capital"]))
    floor = float(p["min_weight"])
    countries = _labels_for(ctx.get("countries"), universe, "country")
    sectors = _labels_for(ctx.get("sectors"), universe, "sector")
    n_elig = len(elig)

    # 3. Plafonds par ligne et liquidité -------------------------------------
    mdv = ctx.get("mdv63")
    mdv_s = None
    if mdv is not None:
        mdv_s = pd.Series(mdv, dtype=float)
        mdv_s.index = mdv_s.index.astype(str)
        mdv_s = mdv_s.reindex(elig)
    if ctx.get("low_liquidity") is not None:
        u6: Any = ctx["low_liquidity"]
    elif mdv_s is not None:
        u6 = (mdv_s < float(p["low_liquidity_tier_fcfa"])).fillna(False)
    else:
        u6 = None
        messages.append("MDV63 absente : plafond de liquidité et niveau U6 non appliqués (hypothèse non vérifiée)")
    if ctx.get("wide_spread") is not None:
        u7: Any = ctx["wide_spread"]
    elif ctx.get("spread") is not None:
        sp = pd.Series(ctx["spread"], dtype=float)
        sp.index = sp.index.astype(str)
        u7 = (sp.reindex(elig) > float(p["max_spread_full_weight"])).fillna(False)
    else:
        u7 = None
        messages.append("spread médian absent : réduction U7 non appliquée")
    lc = line_caps(
        elig,
        countries.reindex(elig),
        u6,
        u7,
        ctx.get("risk_flags"),
        base=float(p["max_weight"]),
        multipliers=p["country_multiplier"],
        floor=floor,
        low_liquidity_mult=float(p["low_liquidity_mult"]),
        wide_spread_mult=float(p["wide_spread_mult"]),
        risk_flag_mult=float(p["risk_flag_mult"]),
        risk_exclude_flags=int(p["risk_exclude_flags"]),
        detail=True,
    )
    line = lc["line_cap"].astype(float)
    if mdv_s is not None:
        liq = liquidity_caps(
            mdv_s.fillna(0.0),
            capital,
            max_adv_participation=float(p["max_participation"]),
            max_days_to_liquidate=float(p["days_to_liquidate"]),
        ).reindex(elig).fillna(0.0)
    else:
        liq = pd.Series(np.inf, index=pd.Index(elig, dtype=object), dtype=float)
    upper = pd.Series(np.minimum(line.to_numpy(), liq.to_numpy()), index=pd.Index(elig, dtype=object), dtype=float)
    no_buy = set(_symbols(ctx.get("no_buy")))
    for s in elig:
        if s in no_buy and s in held.index and np.isfinite(held[s]):
            upper[s] = min(upper[s], float(held[s]))  # conservation sans renforcement
    holdable = [s for s in elig if upper[s] >= floor - _CAP_TOL and upper[s] > 0]

    # 4. Plafonds de groupe sur l'univers éligible ---------------------------
    seat_ref, seat_aes, lam_aes = _resolve_references(ctx, elig, countries, p, messages) if elig else (None, 0.0, 0.0)
    s_caps = sector_caps(
        sectors.reindex(elig), floor=p["sector_cap_floor"], cap=p["sector_cap_max"], mult=p["sector_cap_mult"]
    )
    c_caps = country_caps(
        countries.reindex(elig),
        seat_ref,
        cap=p["country_cap_max"],
        floor=p["country_cap_floor"],
        mult=p["country_cap_mult"],
        uncapped=p["uncapped_countries"],
    )
    for c, m in dict(ctx.get("country_cap_mult") or {}).items():
        if str(c) in c_caps.index:
            c_caps[str(c)] = c_caps[str(c)] * float(m)
        else:  # pays sans plafond propre (CI) : le multiplicateur s'applique à l'exposition visée
            c_caps[str(c)] = budget * float(m)
            messages.append(
                f"pays {c} sans plafond propre : multiplicateur {float(m):g} appliqué à l'exposition visée "
                f"({budget:.0%}) — interprétation"
            )
    for c, cap in dict(ctx.get("country_cap_overrides") or {}).items():
        c_caps[str(c)] = min(float(c_caps.get(str(c), np.inf)), float(cap))
    aes = aes_caps(
        countries.reindex(elig),
        seat_reference=seat_aes,
        lambda_reference=lam_aes,
        lambda_aes=None if ctx.get("lambda_aes") is None else pd.Series(ctx["lambda_aes"], dtype=float),
        multiple=float(p["aes_cap_multiple"]),
        aes_countries=p["aes_countries"],
    ) if elig else []
    groups = build_group_caps(elig, sectors.reindex(elig), countries.reindex(elig), s_caps, c_caps, aes)

    # 1-2. Nombre de lignes et sélection --------------------------------------
    ranks = score_ranks(sc, elig)
    mode = "vide" if n_elig == 0 else ("repli" if is_fallback(n_elig, int(p["min_eligible"])) else "selection")
    band: BandSelection | None = None
    if mode == "vide":
        selected: list[str] = []
        reserve: list[str] = []
        cap_reserve: list[str] = []
        n_target = 0
        reasons: dict[str, str] = {}
        messages.append("univers éligible vide : portefeuille 100 % liquidités")
    elif mode == "repli":
        n_target = n_holdings(n_elig, divisor=int(p["n_divisor"]), min_names=int(p["min_names"]),
                              max_names=int(p["max_names"]), min_eligible=int(p["min_eligible"]))
        reasons = {}
        selected = []
        for s in ranks.index:
            if s not in holdable:
                reasons[s] = "repli : plafond de ligne sous le plancher, titre écarté"
            elif s in no_buy and s not in held.index:
                reasons[s] = "repli : achat bloqué (filtre de risque ou règle pays)"
            else:
                selected.append(s)
                reasons[s] = f"repli (N_élig = {n_elig} < {int(p['min_eligible'])}) : panier équipondéré des éligibles"
        for s in held.index:
            if s not in elig:
                reasons[s] = "vendu : titre non éligible à la date de décision"
        reserve = []
        cap_reserve = []
        messages.append(
            f"mode repli : {n_elig} titres éligibles < {int(p['min_eligible'])}, panier équipondéré "
            "(aucune sélection par le score ; fait de marché, pas un défaut du modèle)"
        )
    else:
        n_target = n_holdings(n_elig, divisor=int(p["n_divisor"]), min_names=int(p["min_names"]),
                              max_names=int(p["max_names"]), min_eligible=int(p["min_eligible"]))
        band = select_with_band(
            sc,
            held,
            elig,
            n_target,
            float(p["entry_pct"]),
            float(p["exit_pct"]),
            min_names=int(p["min_names"]),
            max_names=int(p["max_names"]),
            holdable=holdable,
            no_buy=no_buy,
            fill_beyond_exit=bool(p["fill_beyond_exit"]),
        )
        selected, reasons = list(band.selected), dict(band.reasons)
        reserve = list(band.reserve) + (list(band.reserve_beyond) if bool(p["fill_beyond_exit"]) else [])
        cap_reserve = []
        if bool(p["fill_for_capacity"]):
            cap_reserve = list(band.reserve) + (list(band.reserve_beyond) if bool(p["capacity_beyond_exit"]) else [])
    for s in held.index:
        if s not in reasons and s not in elig:
            reasons[s] = "vendu : titre non éligible à la date de décision"
    for s in sc.index:
        if s not in reasons and s not in elig:
            reasons[s] = "non éligible à la date de décision"
    priority = {s: float(r) for s, r in ranks.items()}
    min_names_eff = 0 if mode != "selection" else int(p["min_names"])

    # 5. Pondération ----------------------------------------------------------
    weighting = str(p["weighting"])
    extra: dict[str, Any] = {}
    fill_kw: dict[str, Any] = {
        "min_weight": floor,
        "reserve": reserve,
        "min_names": min_names_eff,
        "capacity_reserve": cap_reserve,
        "max_names": int(p["max_names"]) if mode == "selection" else None,
        "priority": priority,
    }
    w_eq = equal_weight_with_caps(selected, upper, groups, budget, **fill_kw)
    if weighting == "equal" or not selected:
        w_sel = w_eq
    else:
        cov_w = _cov_from_context(ctx, p)
        extra["cov_shrinkage"] = cov_w.attrs.get("shrinkage")
        extra["cov_n_weeks"] = cov_w.attrs.get("n_weeks")
        names_w = [s for s in w_eq.index if w_eq[s] > 0]
        if weighting == "hrp_tilt":
            rates, info = hrp_tilt_rates(
                _unique(names_w + reserve + cap_reserve),
                sc,
                cov_w,
                gamma=float(p["hrp_gamma"]),
                linkage=str(p["hrp_linkage"]),
                distance_of_distances=bool(p["hrp_distance_of_distances"]),
            )
            w_sel = equal_weight_with_caps(names_w, upper, groups, budget, rates=rates, **fill_kw)
            extra["hrp"] = info["hrp"]
            if info["no_cov"]:
                messages.append("variante G : sans covariance (< 52 semaines), rythme équipondéré pour "
                                + ", ".join(info["no_cov"]))
        else:
            cov_a = cov_w * 52.0
            base = w_eq[w_eq > 0]
            w_h, info = mv_alpha_weights(
                list(base.index),
                sc,
                cov_a,
                upper,
                groups,
                budget,
                base_weights=base,
                held_weights=held.fillna(0.0) if len(held) else None,
                ic=float(p["mv_ic"]),
                risk_aversion=float(p["mv_risk_aversion"]),
                tcost=p["mv_tcost"],
                kelly_fraction=float(p["kelly_fraction"]),
                kelly_fraction_max=float(p["kelly_fraction_max"]),
                kelly_max_gross=float(p["kelly_max_gross"]),
                min_weight=floor,
                min_names=min_names_eff,
                priority=priority,
            )
            w_sel = w_h.reindex(w_eq.index).fillna(0.0)
            w_sel.attrs.update(w_eq.attrs)
            inv = float(w_sel.sum())
            w_sel.attrs.update(
                {
                    "invested": inv,
                    "cash": 1.0 - inv,
                    "shortfall": max(budget - inv, 0.0),
                    "feasible_full_budget": bool(budget - inv <= _INVARIANT_TOL),
                    "active_constraints": _active_constraints(w_sel[w_sel > 0], upper, groups, budget),
                    "removed": {**w_eq.attrs.get("removed", {}), **info.get("removed", {})},
                }
            )
            extra.update({k: info[k] for k in ("kelly_scale", "alpha", "tcost") if k in info})
            if info.get("no_cov"):
                messages.append("variante H : sans covariance (< 52 semaines), poids de A conservés pour "
                                + ", ".join(info["no_cov"]))
            if info.get("message"):
                messages.append(info["message"])
            messages.append(
                "variante H : alpha de Grinold (IC_post 0,02, a priori non mesuré), κ = coût aller central "
                f"estimé à {info.get('tcost', float('nan')):.2%} : hypothèses"
            )

    # Assemblage ---------------------------------------------------------------
    weights = pd.Series(0.0, index=pd.Index(universe, dtype=object), dtype=float, name="weight")
    pos = w_sel[w_sel > 0]
    weights.loc[pos.index] = pos.to_numpy()
    # A : un seul jeu d'attributs ; H : attributs de A déjà fusionnés ; G : ceux de A puis ceux de G
    sources = [w_sel.attrs] if (w_sel is w_eq or weighting == "mv_alpha") else [w_eq.attrs, w_sel.attrs]
    for src in sources:
        for s in src.get("added", []):
            reasons[s] = f"complément après l'élagage (moins de {int(p['min_names'])} lignes), rang {int(ranks[s])}/{n_elig}"
        for s in src.get("capacity_added", []):
            reasons[s] = (
                f"ajouté pour la capacité : plafonds saturés sous {budget:.0%} d'exposition, "
                f"rang {int(ranks[s])}/{n_elig}" + (" dans les 50 % supérieurs" if band and ranks[s] <= band.exit_rank
                                                   else " hors des 50 % supérieurs (capacity_beyond_exit)")
            )
        for s, why in src.get("removed", {}).items():
            if why not in reasons.get(s, ""):
                reasons[s] = (reasons.get(s, "") + " ; " if reasons.get(s) else "") + why
    touched = set(selected) | set(w_sel.index)
    for s in sorted(touched):
        if weights.get(s, 0.0) <= 0 and "supprimée" not in reasons.get(s, "") and "plancher" not in reasons.get(s, ""):
            reasons[s] = (reasons.get(s, "") + " ; " if reasons.get(s) else "") + f"poids final nul (pondération {weighting})"
    for s in selected:
        if s in weights.index and weights[s] > 0 and s in upper.index and weights[s] >= upper[s] - 1e-9:
            reasons[s] = reasons.get(s, "") + f" ; au plafond de ligne {upper[s]:.2%}"
    for s in held.index:
        if weights.get(s, 0.0) <= 0 and s not in reasons:
            reasons[s] = "vendu"
    messages.extend(w_sel.attrs.get("messages", []))
    invested = float(weights.sum())
    viol = audit_weights(weights[weights > 0], upper.reindex(weights[weights > 0].index).fillna(0.0), groups,
                         budget, floor)
    if max(viol.values()) > _INVARIANT_TOL:  # garde-fou : ne devrait jamais se produire
        messages.append("ALERTE : contrainte violée de plus de 1e-9 : " + repr(viol))
    in_elig = set(elig)
    table = pd.DataFrame(
        {
            "score": sc.reindex(universe),
            "rank": ranks.reindex(universe),
            "eligible": [s in in_elig for s in universe],
            "held_weight": held.reindex(universe),
            "country": countries.reindex(universe),
            "sector": sectors.reindex(universe),
            "line_cap": line.reindex(universe),
            "liquidity_cap": liq.reindex(universe),
            "upper": upper.reindex(universe),
            "selected": [s in set(selected) for s in universe],
            "weight": weights,
            "reason": [reasons.get(s, "") for s in universe],
        },
        index=pd.Index(universe, dtype=object),
    )
    table = table.sort_values(["rank", "score"], ascending=[True, False], na_position="last", kind="mergesort")
    diagnostics: dict[str, Any] = {
        "asof": ctx.get("asof"),
        "mode": mode,
        "weighting": weighting,
        "n_eligible": n_elig,
        "n_target": int(n_target),
        "n_selected": len(selected),
        "n_holdings": int((weights > 0).sum()),
        "entry_rank": band.entry_rank if band else None,
        "exit_rank": band.exit_rank if band else None,
        "invested": invested,
        "cash": 1.0 - invested,
        "budget": budget,
        "max_investable": float(w_sel.attrs.get("max_investable", invested)),
        "feasible_full_budget": bool(w_sel.attrs.get("feasible_full_budget", mode != "vide")),
        "solver": w_sel.attrs.get("solver"),
        "active_constraints": list(w_sel.attrs.get("active_constraints", [])),
        "caps": {
            "line": line,
            "liquidity": liq,
            "upper": upper,
            "line_detail": lc["cap_reason"],
            "sector": s_caps,
            "country": c_caps,
            "aes": {g.label: g.cap for g in aes},
            "groups": groups,
        },
        "band": band,
        "reasons": {s: reasons.get(s, "") for s in universe},
        "table": table,
        "violations": viol,
        "messages": _unique(messages),
        "params": p,
        **extra,
    }
    weights.attrs.update({"mode": mode, "weighting": weighting, "invested": invested})
    return weights, diagnostics
