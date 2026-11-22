"""Estimation du risque pour un marché peu liquide (BRVM).

Ce module fournit :

* :func:`ledoit_wolf_cov` — covariance rétrécie de Ledoit & Wolf (2004), cible
  « corrélation constante » (Ledoit & Wolf, 2004, *Honey, I Shrunk the Sample
  Covariance Matrix*, J. Portfolio Management 30(4)) ou cible « identité »
  (Ledoit & Wolf, 2004, *A well-conditioned estimator for large-dimensional
  covariance matrices*, J. Multivariate Analysis 88(2)). Les valeurs
  manquantes (titres non cotés, suspendus) sont traitées par paires, puis la
  matrice est projetée sur le cône des matrices semi-définies positives (SDP)
  par l'algorithme de Higham (2002).
* :func:`aggregate_returns` — rendements multi-séances (p. ex. hebdomadaires)
  sur blocs disjoints, pour atténuer le biais des prix périmés.
* :func:`nearest_correlation` — matrice de corrélation la plus proche au sens
  de Frobenius (Higham, 2002, *Computing the nearest correlation matrix — a
  problem from finance*, IMA J. Numerical Analysis 22(3)).
* :func:`hrp_weights` — Hierarchical Risk Parity (López de Prado, 2016,
  *Building Diversified Portfolios that Outperform Out of Sample*, J. Portfolio
  Management 42(4)).
* :func:`inverse_vol_weights`, :func:`risk_contributions`,
  :func:`portfolio_volatility`, :func:`cov_to_corr`.

Prix périmés (« stale prices ») et rendements multi-séances
-----------------------------------------------------------
À la BRVM, beaucoup de titres ne s'échangent pas chaque séance : le cours de
clôture publié est alors le dernier cours connu, le rendement quotidien vaut 0
puis « rattrape » d'un coup lors de la séance suivante avec échanges. Les
rendements quotidiens observés sont donc des moyennes mobiles retardées des
rendements latents, ce qui :

1. biaise les corrélations vers zéro (effet Epps, Epps 1979 ; Scholes &
   Williams 1977 ; Dimson 1979 pour les bêtas) ;
2. introduit de l'autocorrélation (Lo & MacKinlay, 1990, « non-synchronous
   trading »).

En agrégeant les rendements sur des blocs disjoints de ``h`` séances
(``horizon=h``), le décalage moyen entre deux titres (au plus quelques séances)
devient petit devant la longueur du bloc : la covariance mesurée
``Cov(R_i^{(h)}, R_j^{(h)})`` capture l'essentiel des covariances croisées
retardées, et ``Σ_quotidienne ≈ Σ^{(h)} / h``. Le prix à payer est une division
par ``h`` du nombre d'observations, compensée en partie par le rétrécissement
de Ledoit-Wolf (dont l'intensité augmente automatiquement quand ``T``
diminue).

Ordre de grandeur (simulation reproduite dans ``tests/test_portfolio.py``) :
deux titres de corrélation latente ρ = 0,6, échangés chacun avec une
probabilité de 30 % par séance (cas fréquent à la BRVM), 2 500 séances. La
corrélation mesurée vaut ≈ 0,10 en quotidien, ≈ 0,35 sur 5 séances, ≈ 0,48 sur
10 séances et ≈ 0,58 sur 20 séances. En pratique : ``horizon=5`` pour les
titres liquides (SNTS, ORAC, SGBC…), ``horizon=10`` à ``20`` dès que l'univers
contient des titres échangés moins d'une séance sur deux, avec au moins 2 à 3
ans d'historique pour garder ``T/h`` raisonnable.

Aucune fonction de ce module ne regarde le futur : la covariance estimée à la
date ``t`` ne doit recevoir que les rendements connus en ``t`` (c'est à
l'appelant de tronquer le panel).
"""

from __future__ import annotations

import warnings
from typing import Literal

import numpy as np
import pandas as pd
from scipy.cluster import hierarchy as sch
from scipy.spatial.distance import squareform

__all__ = [
    "aggregate_returns",
    "cov_to_corr",
    "nearest_correlation",
    "nearest_psd_cov",
    "ledoit_wolf_cov",
    "hrp_weights",
    "inverse_vol_weights",
    "risk_contributions",
    "portfolio_volatility",
]

Target = Literal["constant_correlation", "identity"]

_TINY = 1e-14


# ---------------------------------------------------------------------------
# Utilitaires
# ---------------------------------------------------------------------------


def _symmetrize(a: np.ndarray) -> np.ndarray:
    """Renvoie ``(A + Aᵀ) / 2``."""
    return 0.5 * (a + a.T)


def _validate_square(cov: pd.DataFrame, what: str = "cov") -> np.ndarray:
    """Vérifie qu'un DataFrame est une matrice carrée, finie, aux index alignés."""
    if not isinstance(cov, pd.DataFrame):
        raise TypeError(f"{what} doit être un pandas.DataFrame")
    if cov.shape[0] != cov.shape[1]:
        raise ValueError(f"{what} doit être carrée, forme reçue {cov.shape}")
    if not cov.index.equals(cov.columns):
        raise ValueError(f"{what} : l'index et les colonnes doivent être identiques")
    a = cov.to_numpy(dtype=float)
    if not np.all(np.isfinite(a)):
        raise ValueError(f"{what} contient des valeurs non finies (NaN/inf)")
    return _symmetrize(a)


def cov_to_corr(cov: pd.DataFrame | np.ndarray) -> pd.DataFrame | np.ndarray:
    """Matrice de corrélation ``ρ_ij = Σ_ij / (σ_i σ_j)``.

    Les variances nulles donnent des corrélations nulles (et 1 sur la
    diagonale). Le type de sortie suit celui de l'entrée.
    """
    a = cov.to_numpy(dtype=float) if isinstance(cov, pd.DataFrame) else np.asarray(cov, float)
    sd = np.sqrt(np.clip(np.diag(a), 0.0, None))
    denom = np.outer(sd, sd)
    with np.errstate(invalid="ignore", divide="ignore"):
        corr = np.where(denom > _TINY, a / np.where(denom > _TINY, denom, 1.0), 0.0)
    corr = np.clip(_symmetrize(corr), -1.0, 1.0)
    np.fill_diagonal(corr, 1.0)
    if isinstance(cov, pd.DataFrame):
        return pd.DataFrame(corr, index=cov.index, columns=cov.columns)
    return corr


def aggregate_returns(
    returns: pd.DataFrame,
    horizon: int,
    min_valid_fraction: float = 0.5,
) -> pd.DataFrame:
    """Rendements simples composés sur blocs disjoints de ``horizon`` séances.

    Pour un bloc ``b`` de séances ``t ∈ b`` :

    ``R_b = Π_{t ∈ b, r_t observé} (1 + r_t) − 1``

    Les blocs sont alignés sur la **fin** de l'échantillon (la dernière séance
    clôt le dernier bloc, l'éventuel premier bloc incomplet est écarté) : la
    covariance estimée à la date ``t`` exploite ainsi les données les plus
    récentes. Un NaN à l'intérieur d'un bloc est traité comme un rendement nul
    (cours inchangé) ; le bloc est NaN si moins de
    ``ceil(min_valid_fraction · horizon)`` rendements y sont observés (titre pas
    encore coté, suspendu…).

    Parameters
    ----------
    returns
        Panel large (date × symbole) de rendements simples décimaux.
    horizon
        Nombre de séances par bloc (1 = pas d'agrégation, 5 ≈ hebdomadaire).
    min_valid_fraction
        Part minimale de rendements observés dans un bloc.

    Returns
    -------
    pandas.DataFrame
        Rendements par bloc, indexés par la date de fin de bloc.
    """
    if horizon < 1:
        raise ValueError("horizon doit être >= 1")
    if not 0.0 < min_valid_fraction <= 1.0:
        raise ValueError("min_valid_fraction doit appartenir à ]0, 1]")
    if horizon == 1:
        return returns.astype(float).copy()
    t_obs, p = returns.shape
    n_blocks = t_obs // horizon
    start = t_obs - n_blocks * horizon
    arr = returns.to_numpy(dtype=float)[start:]
    arr = np.where(np.isfinite(arr), arr, np.nan).reshape(n_blocks, horizon, p)
    valid = np.isfinite(arr)
    growth = np.prod(np.where(valid, 1.0 + arr, 1.0), axis=1) - 1.0
    need = int(np.ceil(min_valid_fraction * horizon))
    out = np.where(valid.sum(axis=1) >= need, growth, np.nan)
    index = returns.index[start + horizon - 1 :: horizon]
    return pd.DataFrame(out, index=index, columns=returns.columns)


# ---------------------------------------------------------------------------
# Higham (2002) : matrice de corrélation la plus proche
# ---------------------------------------------------------------------------


def _proj_psd(a: np.ndarray, min_eig: float = 0.0) -> np.ndarray:
    """Projection de Frobenius sur ``{X symétrique : λ_min(X) ≥ min_eig}``."""
    vals, vecs = np.linalg.eigh(_symmetrize(a))
    vals = np.maximum(vals, min_eig)
    return _symmetrize((vecs * vals) @ vecs.T)


def nearest_correlation(
    corr: np.ndarray | pd.DataFrame,
    *,
    tol: float = 1e-10,
    max_iter: int = 2000,
    min_eig: float = 0.0,
) -> np.ndarray | pd.DataFrame:
    """Matrice de corrélation la plus proche (norme de Frobenius), Higham (2002).

    Résout ``min ‖A − X‖_F`` sur l'intersection des ensembles convexes
    ``S = {X ⪰ 0}`` et ``U = {X : diag(X) = 1}`` par projections alternées avec
    correction de Dykstra (Higham 2002, algorithme 3.3, poids ``W = I``) :

    ``R_k = Y_{k−1} − ΔS_{k−1}``, ``X_k = P_S(R_k)``, ``ΔS_k = X_k − R_k``,
    ``Y_k = P_U(X_k)``.

    ``P_S`` annule (ou plancher à ``min_eig``) les valeurs propres négatives,
    ``P_U`` remet la diagonale à 1. À l'issue des itérations, la sortie est
    ``D^{-1/2} P_S(Y) D^{-1/2}`` (``D = diag(P_S(Y))``), ce qui garantit
    exactement une diagonale unité **et** le caractère SDP.

    Parameters
    ----------
    corr
        Matrice symétrique « pseudo-corrélation » (p. ex. corrélations par
        paires, possiblement indéfinie).
    tol
        Tolérance relative d'arrêt (critères de Higham sur ``X``, ``Y`` et
        ``X − Y``).
    max_iter
        Nombre maximal d'itérations.
    min_eig
        Plancher des valeurs propres (0 = SDP ; > 0 = définie positive).

    Returns
    -------
    numpy.ndarray ou pandas.DataFrame
        Même type que l'entrée.
    """
    a = corr.to_numpy(dtype=float) if isinstance(corr, pd.DataFrame) else np.asarray(corr, float)
    if a.ndim != 2 or a.shape[0] != a.shape[1]:
        raise ValueError("corr doit être une matrice carrée")
    if not np.all(np.isfinite(a)):
        raise ValueError("corr contient des valeurs non finies")
    a = _symmetrize(a)
    y = a.copy()
    np.fill_diagonal(y, 1.0)
    d_s = np.zeros_like(a)
    x_prev = y.copy()
    for _ in range(max_iter):
        r = y - d_s
        x = _proj_psd(r, min_eig)
        d_s = x - r
        y_new = x.copy()
        np.fill_diagonal(y_new, 1.0)
        ny = max(np.linalg.norm(y_new), 1.0)
        crit = max(
            np.linalg.norm(x - x_prev) / max(np.linalg.norm(x), 1.0),
            np.linalg.norm(y_new - y) / ny,
            np.linalg.norm(y_new - x) / ny,
        )
        y, x_prev = y_new, x
        if crit < tol:
            break
    x = _proj_psd(y, min_eig)
    d = np.sqrt(np.clip(np.diag(x), _TINY, None))
    out = _symmetrize(x / np.outer(d, d))
    np.fill_diagonal(out, 1.0)
    if isinstance(corr, pd.DataFrame):
        return pd.DataFrame(out, index=corr.index, columns=corr.columns)
    return out


def nearest_psd_cov(cov: pd.DataFrame, *, min_eig: float = 0.0) -> pd.DataFrame:
    """Projette une covariance (p. ex. estimée par paires) sur le cône SDP.

    La corrélation implicite est projetée par :func:`nearest_correlation`
    (Higham 2002) puis remise à l'échelle des écarts-types d'origine :
    ``Σ̃ = D^{1/2} C̃ D^{1/2}`` — les variances sont donc conservées.
    """
    a = _validate_square(cov)
    sd = np.sqrt(np.clip(np.diag(a), 0.0, None))
    corr = cov_to_corr(a)
    c_psd = nearest_correlation(corr, min_eig=min_eig)
    out = _symmetrize(c_psd * np.outer(sd, sd))
    return pd.DataFrame(out, index=cov.index, columns=cov.columns)


# ---------------------------------------------------------------------------
# Ledoit-Wolf par paires
# ---------------------------------------------------------------------------


def _lw_core(
    x: np.ndarray,
    target: Target,
    min_overlap: int,
    shrinkage: float | None,
) -> tuple[np.ndarray, float, dict]:
    """Cœur numérique de Ledoit-Wolf sur un tableau ``T × p`` avec NaN.

    Notations (``y_ti`` = rendement centré par la moyenne du titre ``i`` sur ses
    observations, ``J_ij`` = séances où ``i`` et ``j`` sont observés,
    ``N_ij = |J_ij|``, ``n_i = N_ii``) :

    * ``s_ij = (1/N_ij) Σ_{t∈J_ij} y_ti y_tj`` (normalisation en ``1/N`` comme
      dans Ledoit-Wolf et scikit-learn) ;
    * ``π_ij = (1/N_ij) Σ_{t∈J_ij} (y_ti y_tj − s_ij)²`` ;
    * ``θ_ii,ij = (1/N_ij) Σ_{t∈J_ij} (y_ti² − s_ii)(y_ti y_tj − s_ij)``.

    Intensité optimale ``δ* = Σ_ij [Var(s_ij) − Cov(f_ij, s_ij)] / Σ_ij (f_ij − s_ij)²``
    avec, par paires, ``Var(s_ij) ≈ π_ij / N_ij`` et
    ``Cov(s_ii, s_ij) ≈ θ_ii,ij / n_i``. Sans valeur manquante, on retrouve
    exactement ``δ* = κ̂ / T`` de Ledoit & Wolf (2004).
    """
    t_obs, p = x.shape
    m = np.isfinite(x)
    mf = m.astype(float)
    n_i = mf.sum(axis=0)
    mean = np.where(m, x, 0.0).sum(axis=0) / n_i
    y = np.where(m, x - mean, 0.0)

    n_ij = mf.T @ mf
    c = y.T @ y
    n_safe = np.where(n_ij > 0, n_ij, 1.0)
    s0 = c / n_safe  # moments bruts (aussi pour les paires invalides)
    valid = n_ij >= min_overlap
    np.fill_diagonal(valid, True)
    var = np.diag(s0).copy()
    sd = np.sqrt(var)

    corr = s0 / np.outer(sd, sd)
    np.fill_diagonal(corr, 1.0)
    offdiag = ~np.eye(p, dtype=bool)
    iu = np.triu_indices(p, 1)
    if target == "constant_correlation":
        vals = corr[iu][valid[iu]]
        fill = float(vals.mean()) if vals.size else 0.0
    else:
        fill = 0.0
    corr = np.clip(np.where(valid, corr, fill), -1.0, 1.0)
    corr = _symmetrize(corr)
    np.fill_diagonal(corr, 1.0)

    projected = False
    if p > 1 and np.linalg.eigvalsh(corr)[0] < -1e-10:
        corr = nearest_correlation(corr)
        projected = True
    s_psd = _symmetrize(corr * np.outer(sd, sd))

    if target == "constant_correlation":
        rbar = float(corr[iu].mean()) if p > 1 else 0.0
        f = rbar * np.outer(sd, sd)
        np.fill_diagonal(f, var)
    else:
        rbar = float("nan")
        mu = float(var.mean())
        f = mu * np.eye(p)

    gamma = float(np.sum((f - s_psd) ** 2))

    if shrinkage is not None:
        delta = float(shrinkage)
    elif gamma <= _TINY * max(float(np.sum(s_psd**2)), _TINY):
        delta = 0.0
    else:
        y2 = y * y
        pi = (y2.T @ y2) / n_safe - s0**2
        pi_scaled = np.where(valid, pi / n_safe, 0.0)
        pi_sum = float(pi_scaled.sum())
        if target == "identity":
            # Ledoit & Wolf (2004a), lemme 3.4 : b̄² = min(b̄², d²) ; δ = b̄²/d².
            delta = min(pi_sum, gamma) / gamma
        else:
            y3 = y2 * y
            a3 = y3.T @ y  # Σ y_i³ y_j
            b2 = y2.T @ mf  # Σ y_i² 1{j observé}
            theta = (a3 - s0 * b2 - var[:, None] * c + var[:, None] * s0 * n_ij) / n_safe
            ratio = sd[None, :] / sd[:, None]  # sqrt(s_jj / s_ii)
            rho_diag = float(np.sum(np.diag(pi) / n_i))
            rho_off = float(
                np.sum(np.where(valid & offdiag, rbar * ratio * theta / n_i[:, None], 0.0))
            )
            delta = (pi_sum - rho_diag - rho_off) / gamma
    delta = float(np.clip(delta, 0.0, 1.0))
    sigma = _symmetrize(delta * f + (1.0 - delta) * s_psd)
    info = {
        "projected": projected,
        "mean_correlation": rbar,
        "n_obs": n_i,
        "n_invalid_pairs": int((~valid[iu]).sum()),
    }
    return sigma, delta, info


def ledoit_wolf_cov(
    returns: pd.DataFrame,
    target: Target = "constant_correlation",
    *,
    horizon: int = 1,
    min_periods: int = 20,
    min_overlap: int | None = None,
    shrinkage: float | None = None,
    min_valid_fraction: float = 0.5,
    annualize: bool = False,
    trading_days: int = 252,
) -> pd.DataFrame:
    """Covariance rétrécie de Ledoit-Wolf, robuste aux NaN et aux prix périmés.

    ``Σ̂ = δ* F + (1 − δ*) S``

    où ``S`` est la covariance empirique (normalisation ``1/T``), ``F`` la cible
    et ``δ* ∈ [0, 1]`` l'intensité optimale (asymptotiquement) au sens de la
    perte quadratique de Frobenius :

    * ``target="constant_correlation"`` (Ledoit & Wolf, 2004, JPM) :
      ``F_ii = s_ii``, ``F_ij = r̄ √(s_ii s_jj)``, ``r̄`` = corrélation moyenne ;
      ``δ* = max(0, min(1, (π̂ − ρ̂) / (γ̂ T)))`` avec ``π̂ = Σ π_ij``,
      ``ρ̂ = Σ_i π_ii + Σ_{i≠j} r̄ √(s_jj/s_ii) θ_ii,ij``,
      ``γ̂ = ‖F − S‖²_F`` (transcription du code ``covCor.m`` des auteurs).
    * ``target="identity"`` (Ledoit & Wolf, 2004, JMVA) : ``F = μ I`` avec
      ``μ = tr(S)/p`` et ``δ* = min(b̄², d²)/d²``, ``d² = ‖S − μI‖²_F``,
      ``b̄² = Σ_ij π_ij / T`` — identique à ``sklearn.covariance.LedoitWolf``
      sur données complètes.

    Valeurs manquantes : moyennes, covariances et moments d'ordre 4 sont
    calculés **par paires** sur les séances communes (``N_ij`` observations) ;
    les variances d'estimation deviennent ``π_ij / N_ij`` (voir
    :func:`_lw_core`). Les paires avec moins de ``min_overlap`` observations
    communes sont entièrement rétrécies vers la cible. La matrice par paires,
    éventuellement indéfinie, est projetée sur la matrice de corrélation SDP la
    plus proche (Higham, 2002) avant le rétrécissement : le résultat est
    toujours symétrique semi-défini positif (défini positif dès que ``δ* > 0``
    et ``F ≻ 0``).

    Prix périmés : ``horizon=h > 1`` estime la covariance sur des rendements
    composés de ``h`` séances (blocs disjoints, cf. :func:`aggregate_returns`)
    puis la ramène à l'échelle quotidienne par ``Σ^{(h)} / h`` ; cela corrige
    l'essentiel du biais vers zéro des corrélations dû aux titres non échangés
    (effet Epps ; Scholes & Williams 1977 ; Lo & MacKinlay 1990).

    Parameters
    ----------
    returns
        Panel large (date × symbole) de rendements simples quotidiens ; NaN =
        rendement indisponible (titre non coté, suspendu). Un titre non échangé
        dont le cours est reporté doit avoir un rendement 0 (et non NaN).
    target
        ``"constant_correlation"`` (défaut, adapté aux actions) ou
        ``"identity"``.
    horizon
        Longueur des blocs de rendements (1 = quotidien ; 5 ≈ hebdomadaire).
    min_periods
        Nombre minimal d'observations (après agrégation) pour conserver un
        titre ; les titres exclus (historique trop court ou variance nulle,
        p. ex. jamais échangés) sont retirés de la sortie avec un
        avertissement.
    min_overlap
        Nombre minimal d'observations communes pour estimer une covariance
        croisée (défaut : ``min_periods``).
    shrinkage
        Si fourni, intensité imposée ``δ ∈ [0, 1]`` (pas d'estimation).
    min_valid_fraction
        Voir :func:`aggregate_returns`.
    annualize
        Si vrai, multiplie la covariance quotidienne par ``trading_days``.
    trading_days
        Séances par an (252).

    Returns
    -------
    pandas.DataFrame
        Covariance (symbole × symbole), à l'échelle quotidienne (ou annuelle).
        ``attrs`` contient ``shrinkage``, ``target``, ``horizon``,
        ``projected`` (projection de Higham appliquée), ``mean_correlation``,
        ``n_obs`` (dict symbole → observations) et ``dropped`` (titres exclus).
    """
    if not isinstance(returns, pd.DataFrame):
        raise TypeError("returns doit être un pandas.DataFrame (date × symbole)")
    if target not in ("constant_correlation", "identity"):
        raise ValueError("target doit valoir 'constant_correlation' ou 'identity'")
    if shrinkage is not None and not 0.0 <= shrinkage <= 1.0:
        raise ValueError("shrinkage doit appartenir à [0, 1]")
    if min_periods < 2:
        raise ValueError("min_periods doit être >= 2")
    overlap = min_periods if min_overlap is None else int(min_overlap)
    if overlap < 2:
        raise ValueError("min_overlap doit être >= 2")

    rets = returns.astype(float)
    if horizon > 1:
        rets = aggregate_returns(rets, horizon, min_valid_fraction)
    x = rets.to_numpy(dtype=float)
    x = np.where(np.isfinite(x), x, np.nan)

    counts = np.isfinite(x).sum(axis=0)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        variances = np.nanvar(x, axis=0) if x.shape[0] else np.zeros(x.shape[1])
    enough = (counts >= min_periods) & np.isfinite(variances)
    # variance « nulle » = titre jamais échangé sur la fenêtre (rendements tous à 0)
    var_floor = max(1e-12 * float(variances[enough].max()), 1e-20) if enough.any() else 1e-20
    keep = enough & (variances > var_floor)
    cols = rets.columns
    dropped = [str(c) for c in cols[~keep]]
    if dropped:
        warnings.warn(
            "ledoit_wolf_cov : titres exclus (historique < min_periods ou variance nulle) : "
            + ", ".join(dropped),
            RuntimeWarning,
            stacklevel=2,
        )
    kept_cols = cols[keep]
    xk = x[:, keep]
    p = xk.shape[1]
    if p == 0:
        out = pd.DataFrame(np.zeros((0, 0)), index=kept_cols, columns=kept_cols)
        delta, info = 0.0, {"projected": False, "mean_correlation": float("nan"), "n_obs": np.zeros(0)}
    else:
        sigma, delta, info = _lw_core(xk, target, overlap, shrinkage)
        sigma = sigma / horizon
        if annualize:
            sigma = sigma * trading_days
        out = pd.DataFrame(sigma, index=kept_cols, columns=kept_cols)
    out.attrs.update(
        {
            "shrinkage": delta,
            "target": target,
            "horizon": horizon,
            "projected": bool(info["projected"]),
            "mean_correlation": info["mean_correlation"],
            "n_obs": {str(k): int(v) for k, v in zip(kept_cols, info["n_obs"])},
            "dropped": dropped,
        }
    )
    return out


# ---------------------------------------------------------------------------
# Hierarchical Risk Parity (López de Prado, 2016)
# ---------------------------------------------------------------------------


def _quasi_diag(link: np.ndarray) -> list[int]:
    """Ordre des feuilles du dendrogramme (quasi-diagonalisation).

    Parcours préfixe gauche → droite, identique à ``getQuasiDiag`` de López de
    Prado (2016) : chaque grappe est remplacée récursivement par ses deux
    sous-grappes ``link[k, 0]`` puis ``link[k, 1]``.
    """
    n = link.shape[0] + 1
    order: list[int] = []
    stack = [2 * n - 2]
    while stack:
        node = stack.pop()
        if node < n:
            order.append(node)
        else:
            row = link[node - n]
            stack.append(int(row[1]))
            stack.append(int(row[0]))
    return order


def _ivp_cluster_var(cov: np.ndarray, items: list[int]) -> float:
    """Variance d'une grappe pondérée par l'inverse des variances.

    ``w = diag(V)^{-1} / 1ᵀ diag(V)^{-1}``, ``σ²_grappe = wᵀ V w``.
    """
    sub = cov[np.ix_(items, items)]
    ivp = 1.0 / np.diag(sub)
    ivp /= ivp.sum()
    return float(ivp @ sub @ ivp)


def _bisect_halves(cov: np.ndarray, order: list[int]) -> np.ndarray:
    """Bissection récursive par moitiés de la liste ordonnée (López de Prado)."""
    w = np.ones(cov.shape[0])
    clusters = [order]
    while clusters:
        nxt: list[list[int]] = []
        for c in clusters:
            if len(c) <= 1:
                continue
            half = len(c) // 2
            c0, c1 = c[:half], c[half:]
            v0, v1 = _ivp_cluster_var(cov, c0), _ivp_cluster_var(cov, c1)
            a = 1.0 - v0 / (v0 + v1)
            w[c0] *= a
            w[c1] *= 1.0 - a
            nxt.extend([c0, c1])
        clusters = nxt
    return w


def _bisect_tree(cov: np.ndarray, link: np.ndarray) -> np.ndarray:
    """Bissection en suivant les nœuds du dendrogramme (variante « arbre »)."""
    w = np.ones(cov.shape[0])
    root = sch.to_tree(link)
    stack = [root]
    while stack:
        node = stack.pop()
        if node.is_leaf():
            continue
        c0 = node.get_left().pre_order()
        c1 = node.get_right().pre_order()
        v0, v1 = _ivp_cluster_var(cov, c0), _ivp_cluster_var(cov, c1)
        a = 1.0 - v0 / (v0 + v1)
        w[c0] *= a
        w[c1] *= 1.0 - a
        stack.extend([node.get_left(), node.get_right()])
    return w


def hrp_weights(
    cov: pd.DataFrame,
    *,
    linkage_method: str = "single",
    distance_of_distances: bool = False,
    split: Literal["halves", "tree"] = "halves",
) -> pd.Series:
    """Poids Hierarchical Risk Parity (López de Prado, 2016).

    1. **Distance** : ``d_ij = √(½ (1 − ρ_ij))`` (métrique sur les corrélations).
    2. **Classification hiérarchique** (single-linkage par défaut) sur ``d``.
       Avec ``distance_of_distances=True``, on reproduit le code original de
       l'article, qui classe les colonnes de ``d`` par la distance euclidienne
       ``d̃_ij = ‖d_·i − d_·j‖₂``.
    3. **Quasi-diagonalisation** : réordonnancement selon les feuilles du
       dendrogramme (titres similaires adjacents).
    4. **Bissection récursive** : chaque grappe ``L`` est coupée en ``L₀, L₁``
       (moitiés de la liste ordonnée — ``split="halves"``, comme l'article — ou
       sous-arbres du dendrogramme — ``split="tree"``) ; avec
       ``V_k = w̃_kᵀ Σ_k w̃_k`` (``w̃_k`` = inverse-variance dans ``L_k``),
       ``α = 1 − V₀ / (V₀ + V₁)`` ; ``w[L₀] ×= α`` et ``w[L₁] ×= 1 − α``.

    HRP n'inverse pas Σ : il reste stable avec des covariances mal
    conditionnées, fréquentes à la BRVM (peu d'observations, prix périmés).

    Parameters
    ----------
    cov
        Covariance complète (sans NaN), variances strictement positives.
    linkage_method
        Méthode de ``scipy.cluster.hierarchy.linkage`` (``"single"`` par défaut).
    distance_of_distances
        Reproduire la variante du code de l'article (voir ci-dessus).
    split
        ``"halves"`` (article) ou ``"tree"``.

    Returns
    -------
    pandas.Series
        Poids positifs de somme 1, dans l'ordre de ``cov.index``.
    """
    a = _validate_square(cov)
    p = a.shape[0]
    if p == 0:
        return pd.Series(dtype=float, name="hrp")
    if np.any(np.diag(a) <= 0):
        raise ValueError("hrp_weights : variances nulles ou négatives")
    if p == 1:
        return pd.Series([1.0], index=cov.index, name="hrp")
    corr = cov_to_corr(a)
    dist = np.sqrt(np.clip(0.5 * (1.0 - corr), 0.0, 1.0))
    dist = _symmetrize(dist)
    np.fill_diagonal(dist, 0.0)
    if distance_of_distances:
        with warnings.catch_warnings():
            # scipy signale qu'une matrice carrée ressemble à une matrice de
            # distances : ici c'est voulu (observations = colonnes de d).
            warnings.simplefilter("ignore", sch.ClusterWarning)
            link = sch.linkage(dist, method=linkage_method, metric="euclidean")
    else:
        link = sch.linkage(squareform(dist, checks=False), method=linkage_method)
    if split == "halves":
        w = _bisect_halves(a, _quasi_diag(link))
    elif split == "tree":
        w = _bisect_tree(a, link)
    else:
        raise ValueError("split doit valoir 'halves' ou 'tree'")
    w = w / w.sum()
    return pd.Series(w, index=cov.index, name="hrp")


# ---------------------------------------------------------------------------
# Pondérations simples et décomposition du risque
# ---------------------------------------------------------------------------


def inverse_vol_weights(cov: pd.DataFrame, power: float = 1.0) -> pd.Series:
    """Poids inversement proportionnels à la volatilité : ``w_i ∝ σ_i^{−power}``.

    ``power=1`` : inverse-volatilité (contributions au risque égales si les
    corrélations sont uniformes, Maillard, Roncalli & Teïletche 2010) ;
    ``power=2`` : inverse-variance (portefeuille de variance minimale si les
    corrélations sont nulles).
    """
    a = _validate_square(cov)
    var = np.diag(a)
    if np.any(var <= 0):
        raise ValueError("inverse_vol_weights : variances nulles ou négatives")
    w = np.sqrt(var) ** (-power)
    return pd.Series(w / w.sum(), index=cov.index, name="inverse_vol")


def _aligned(weights: pd.Series, cov: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Aligne poids et covariance ; un poids sans covariance lève une erreur."""
    w = weights.astype(float).fillna(0.0)
    missing = w.index.difference(cov.index)
    if len(missing) and np.any(w.loc[missing].to_numpy() != 0):
        raise KeyError(f"covariance absente pour : {list(missing)}")
    w = w.loc[w.index.intersection(cov.index, sort=False)]
    v = _validate_square(cov.loc[w.index, w.index])
    return w.to_numpy(), v


def portfolio_volatility(weights: pd.Series, cov: pd.DataFrame) -> float:
    """Volatilité du portefeuille ``σ_p = √(wᵀ Σ w)`` (unité de ``cov``)."""
    w, v = _aligned(weights, cov)
    return float(np.sqrt(max(w @ v @ w, 0.0)))


def risk_contributions(
    weights: pd.Series,
    cov: pd.DataFrame,
    relative: bool = True,
) -> pd.Series:
    """Contributions au risque (décomposition d'Euler).

    ``RC_i = w_i (Σw)_i / σ_p`` avec ``Σ_i RC_i = σ_p`` ; si ``relative``,
    ``RC_i / σ_p`` (somme 1). Référence : Maillard, Roncalli & Teïletche
    (2010), *The Properties of Equally Weighted Risk Contribution Portfolios*,
    J. Portfolio Management 36(4).
    """
    w, v = _aligned(weights, cov)
    idx = weights.index.intersection(cov.index, sort=False)
    marginal = v @ w
    var = float(w @ marginal)
    if var <= _TINY:
        return pd.Series(np.zeros(len(w)), index=idx, name="risk_contribution")
    sig = np.sqrt(var)
    rc = w * marginal / sig
    if relative:
        rc = rc / sig
    return pd.Series(rc, index=idx, name="risk_contribution")
