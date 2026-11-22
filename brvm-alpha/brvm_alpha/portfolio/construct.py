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
  ``≥ min_weight``.
* :func:`liquidity_caps` — poids maximal par titre déduit de la valeur
  quotidienne moyenne échangée (ADV), du capital et du délai de sortie.
* :func:`average_daily_value` — ADV sans biais d'anticipation.
* :func:`fractional_kelly_scale` — exposition globale par Kelly fractionnel.
* :func:`apply_no_trade_band`, :func:`cap_turnover` — réduction du turnover.
* :func:`to_lots` — conversion en nombres entiers de titres.
* :func:`grinold_alpha` — conversion score → rendement espéré
  (« alpha = IC × volatilité × score », Grinold 1994).
* :func:`constraint_violations` — audit des contraintes d'un portefeuille.

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

import warnings
from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd
from scipy import optimize

from brvm_alpha.config import Constraints, CostModel
from brvm_alpha.portfolio.risk import hrp_weights

__all__ = [
    "build_portfolio",
    "liquidity_caps",
    "average_daily_value",
    "fractional_kelly_scale",
    "apply_no_trade_band",
    "cap_turnover",
    "to_lots",
    "grinold_alpha",
    "constraint_violations",
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
    """Impose bornes et plafonds de groupe par réduction proportionnelle à ``w − l``."""
    w = np.clip(w, lower, upper)
    for k in range(g.shape[0]):
        idx = np.flatnonzero(g[k])
        s = w[idx].sum()
        if s > caps[k]:
            lo = lower[idx]
            ex = w[idx] - lo
            tot = ex.sum()
            room = max(caps[k] - lo.sum(), 0.0)
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
            sa = add[idx].sum()
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


def _select(
    order: np.ndarray,
    k_max: int,
    upper: np.ndarray,
    g: np.ndarray,
    caps: np.ndarray,
    budget: float,
) -> list[int]:
    """Sélection des ``max_names`` meilleurs titres, consciente de la capacité.

    On prend d'abord les ``k_max`` meilleurs scores. Si leurs plafonds
    (liquidité, secteur, pays) ne permettent pas d'investir le budget, on
    construit la sélection gloutonnement par score décroissant en sautant les
    titres qui n'augmentent pas la capacité investissable tant que le budget
    n'est pas atteignable, puis on complète avec les titres sautés.
    """
    order = list(order)
    top = order[:k_max]

    def cap_of(sel: list[int]) -> float:
        if not sel:
            return 0.0
        v = _max_investable(np.zeros(len(sel)), upper[sel], g[:, sel], caps)
        return 0.0 if v is None else v

    if len(order) <= k_max or cap_of(top) >= budget - 1e-12:
        return top
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
) -> pd.Series:
    """Poids cibles long-only sous contraintes.

    Étapes communes :

    1. **Univers éligible** : ``alpha`` fini, covariance disponible (sauf
       ``"equal"``), plafond ``u_i = min(max_weight, liquidity_i) ≥ min_weight``
       (un titre absent de ``liquidity`` a un plafond nul).
    2. **Sélection** des ``max_names`` meilleurs scores (``"mv_alpha"`` : score
       ``α_i + 2κ·1{détenu}``, la rotation d'un titre détenu coûtant un aller-
       retour), en garantissant si possible que les plafonds permettent
       d'investir ``B = 1 − cash_buffer`` (:func:`_select`). Si ce n'est pas
       réalisable, ``B`` est réduit à l'investissement maximal (PL) et le reste
       demeure en liquidités.
    3. **Pondération** (selon ``method``) puis **élagage** : les lignes
       ``< min_weight`` sont supprimées (en conservant au moins ``min_names``
       lignes et la capacité d'investissement) et les poids sont recalculés sur
       les titres restants avec le plancher ``w_i ≥ min_weight`` — ce qui
       constitue la renormalisation.

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

    Returns
    -------
    pandas.Series
        Poids sur l'union de ``alpha.index`` et ``prev_weights.index`` (0 pour
        les titres non retenus ; ``1 − Σw`` = liquidités). ``attrs`` :
        ``method``, ``solver``, ``budget`` (investissement visé), ``n_names``,
        ``feasible_full_budget``.
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
            {"method": method, "solver": reason, "budget": 0.0, "n_names": 0, "feasible_full_budget": False}
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
    g_all = np.vstack([g_sec, g_cty]) if (g_sec.size or g_cty.size) else np.zeros((0, len(names)))
    c_all = np.concatenate([c_sec, c_cty])
    sig_all = cov.loc[names, names].to_numpy(dtype=float) if cov is not None else None
    if sig_all is not None:
        sig_all = 0.5 * (sig_all + sig_all.T)

    # 2. Sélection -----------------------------------------------------------
    score = a_all + (2.0 * kappa * (wp_all > 0) if method == "mv_alpha" else 0.0)
    order = np.lexsort((np.asarray(names.astype(str)), -score))
    sel = _select(order, cons.max_names, u_all, g_all, c_all, budget_target)

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
    res.attrs.update(
        {
            "method": method,
            "solver": tag2,
            "budget": float(budget_k),
            "n_names": int((vals > 0).sum()),
            "feasible_full_budget": bool(budget_k >= budget_target - 1e-9),
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
) -> dict[str, float]:
    """Mesure des violations de contraintes (0 = respectée).

    Renvoie un dictionnaire : ``negative`` (poids < 0), ``budget`` (dépassement
    de ``1 − cash_buffer``), ``max_weight``, ``min_weight`` (plus grand écart
    sous le plancher parmi les lignes non nulles), ``liquidity``, ``sector``,
    ``country`` (dépassements maximaux) et ``max_names`` (lignes en trop).
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
    return out
