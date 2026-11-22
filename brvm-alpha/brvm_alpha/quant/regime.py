"""Régime de marché : tendance, volatilité, drawdown et chaîne de Markov cachée.

:func:`market_regime` décrit l'état de l'indice de marché (BRVM Composite de
préférence en rendement total) à chaque séance, **sans anticipation** : toutes
les statistiques sont glissantes vers le passé, et le modèle de Markov caché
facultatif est ré-estimé périodiquement sur le seul passé puis appliqué en
*filtrage* (probabilité de l'état en ``t`` sachant les rendements jusqu'à
``t``), jamais en *lissage*.

Usage visé : filtre d'exposition (actions / liquidités) et non signal de
sélection. La revue 02 (section 7.1) observe une persistance des rendements de
l'indice sur plusieurs semaines en 2024-2026 (VR(10) ≈ 1,40) qui dépend du
régime ; elle doit être suivie, pas extrapolée.

Règles de l'état discret (dans cet ordre de priorité)
-----------------------------------------------------
Avec ``trend = niveau / MM - 1`` (MM : moyenne mobile ``ma_window`` séances),
``slope = MM_t / MM_{t-slope_window} - 1``, ``vol_pct`` le percentile
glissant de la volatilité réalisée et ``dd_recent`` le drawdown depuis le plus
haut des ``crash_window`` dernières séances :

1. ``"stress"`` si ``trend < 0`` **et** (volatilité élevée **ou** krach
   ``dd_recent <= -stress_drawdown``), où « volatilité élevée » signifie
   ``vol_pct >= stress_vol_pct`` ou, si le HMM est activé et discriminant,
   ``p_turbulent >= hmm_stress_prob``. Le stress est une **turbulence** (ou
   une chute rapide), pas un marché baissier lent : une baisse prolongée et
   calme, même profonde, relève de ``"baissier"`` ;
2. ``"haussier"`` si ``trend > band`` et ``slope > 0`` ;
3. ``"baissier"`` si ``trend < -band`` et ``slope < 0`` ;
4. ``"neutre"`` sinon.

NaN tant que la moyenne mobile et sa pente ne sont pas calculables. Un filtre
de confirmation facultatif (``confirm_days``) n'adopte un nouvel état
qu'après ``confirm_days`` séances consécutives dans cet état (hystérésis
causale).

Références
----------
* Ang, A. & Bekaert, G. (2002). International Asset Allocation with Regime
  Shifts. *Review of Financial Studies*, 15(4), 1137-1187.
* Baum, L., Petrie, T., Soules, G. & Weiss, N. (1970). A Maximization
  Technique Occurring in the Statistical Analysis of Probabilistic Functions
  of Markov Chains. *Annals of Mathematical Statistics*, 41(1), 164-171.
* Brock, W., Lakonishok, J. & LeBaron, B. (1992). Simple Technical Trading
  Rules and the Stochastic Properties of Stock Returns. *Journal of Finance*,
  47(5), 1731-1764.
* Faber, M. (2007). A Quantitative Approach to Tactical Asset Allocation.
  *Journal of Wealth Management*, 9(4), 69-79.
* Hamilton, J. (1989). A New Approach to the Economic Analysis of
  Nonstationary Time Series and the Business Cycle. *Econometrica*, 57(2),
  357-384.
* Hillis, W. D. & Steele, G. L. (1986). Data Parallel Algorithms.
  *Communications of the ACM*, 29(12), 1170-1183.
* Kritzman, M., Page, S. & Turkington, D. (2012). Regime Shifts: Implications
  for Dynamic Strategies. *Financial Analysts Journal*, 68(3), 22-39.
* Moreira, A. & Muir, T. (2017). Volatility-Managed Portfolios. *Journal of
  Finance*, 72(4), 1611-1644.
* Rabiner, L. (1989). A Tutorial on Hidden Markov Models and Selected
  Applications in Speech Recognition. *Proceedings of the IEEE*, 77(2),
  257-286.
* Schwarz, G. (1978). Estimating the Dimension of a Model. *Annals of
  Statistics*, 6(2), 461-464.
* Särkkä, S. & García-Fernández, Á. (2021). Temporal Parallelization of
  Bayesian Smoothers. *IEEE Transactions on Automatic Control*, 66(1), 299-306.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import numpy.typing as npt
import pandas as pd

__all__ = [
    "REGIME_STATES",
    "GaussianHMM",
    "hmm_filtered_probabilities",
    "market_regime",
]

#: États discrets possibles, du plus favorable au plus défavorable.
REGIME_STATES: tuple[str, ...] = ("haussier", "neutre", "baissier", "stress")

TRADING_DAYS = 252
FloatArray = npt.NDArray[np.float64]


# ---------------------------------------------------------------------------
# Modèle de Markov caché gaussien
# ---------------------------------------------------------------------------


def _scan(M: FloatArray, reverse: bool = False) -> tuple[FloatArray, FloatArray]:
    """Produits matriciels cumulés par balayage parallèle (Hillis & Steele, 1986).

    ``reverse=False`` : ``P[t] ∝ M[0] @ M[1] @ … @ M[t]`` ;
    ``reverse=True``  : ``P[t] ∝ M[t] @ M[t+1] @ … @ M[T-1]``.

    Chaque produit (à coefficients positifs) est renormalisé par la somme de
    ses coefficients et ``log_scale[t]`` accumule les logarithmes des
    facteurs : produit exact ``= P[t] · exp(log_scale[t])``. Coût ``O(T log T)`` entièrement vectorisé
    (le même principe que la parallélisation temporelle des lisseurs
    bayésiens de Särkkä & García-Fernández, 2021).
    """
    P = M.astype(float, copy=True)
    T, K = P.shape[0], P.shape[1]
    ones = np.ones(K * K)

    def _norm(Q: FloatArray) -> FloatArray:
        # Somme des coefficients par produit matrice-vecteur (BLAS) : bien plus
        # rapide qu'une réduction sur de petits axes.
        tot = Q.reshape(Q.shape[0], K * K) @ ones
        tot[~(tot > 0)] = 1.0
        Q /= tot[:, None, None]
        return np.log(tot)

    logc = _norm(P)
    d = 1
    while d < T:
        prod = P[:-d] @ P[d:]
        lc = logc[:-d] + logc[d:]
        log_s = _norm(prod)
        if reverse:
            P[:-d] = prod
            logc[:-d] = lc + log_s
        else:
            P[d:] = prod
            logc[d:] = lc + log_s
        d *= 2
    return P, logc


@dataclass
class GaussianHMM:
    """Chaîne de Markov cachée à émissions gaussiennes univariées (Hamilton, 1989).

    ``s_t ∈ {0..K-1}``, ``P(s_t = j | s_{t-1} = i) = A_ij``,
    ``x_t | s_t = j ~ N(μ_j, σ²_j)``, ``P(s_0 = j) = π_j``.

    Estimation par Baum-Welch (EM ; Baum et al., 1970 ; Rabiner, 1989).
    L'étape E calcule ``α`` (filtrage) et ``β`` par produits matriciels
    cumulés (:func:`_scan`) :

    ``α_t ∝ π' diag(b_0) A diag(b_1) … A diag(b_t)``,
    ``β_t ∝ A diag(b_{t+1}) … A diag(b_{T-1}) 1``,

    puis ``γ_t ∝ α_t ⊙ β_t`` et ``ξ_t(i,j) ∝ α_{t-1}(i) A_ij b_t(j) β_t(j)``.
    Étape M : ``π = γ_0`` ; ``A_ij = Σ_t ξ_t(i,j) / Σ_t γ_{t-1}(i)`` ;
    ``μ_j = Σ γ_t(j) x_t / Σ γ_t(j)`` ; ``σ²_j = Σ γ_t(j)(x_t - μ_j)² / Σ γ_t(j)``
    avec un plancher ``min_variance_ratio · Var(x)`` contre la dégénérescence.
    Arrêt quand le gain de log-vraisemblance d'une itération est inférieur à
    ``tol × n`` (``tol`` par observation) ou après ``max_iter`` itérations.

    Après estimation, les états sont **triés par variance croissante** :
    l'état 0 est le plus calme, l'état ``K-1`` le plus turbulent.
    """

    n_states: int = 2
    max_iter: int = 200
    tol: float = 1e-8
    min_variance_ratio: float = 1e-3
    startprob_: FloatArray | None = field(default=None, repr=False)
    transmat_: FloatArray | None = field(default=None, repr=False)
    means_: FloatArray | None = field(default=None, repr=False)
    variances_: FloatArray | None = field(default=None, repr=False)
    loglik_: float = math.nan
    n_iter_: int = 0

    # -- utilitaires -------------------------------------------------------

    @staticmethod
    def _clean(x: npt.ArrayLike) -> FloatArray:
        arr = np.asarray(x, dtype=float).ravel()
        if arr.size == 0 or not np.isfinite(arr).all():
            raise ValueError("la série doit être non vide et sans NaN/inf")
        return arr

    def _check_fitted(self) -> None:
        if self.transmat_ is None:
            raise RuntimeError("modèle non estimé : appeler fit() d'abord")

    def _emissions(self, x: FloatArray) -> tuple[FloatArray, FloatArray]:
        assert self.means_ is not None and self.variances_ is not None
        var = self.variances_[None, :]
        logb = -0.5 * (np.log(2.0 * np.pi * var) + (x[:, None] - self.means_[None, :]) ** 2 / var)
        off = logb.max(axis=1)
        return np.exp(logb - off[:, None]), off

    def _forward(self, x: FloatArray) -> tuple[FloatArray, FloatArray, FloatArray, float]:
        """Filtrage : ``α̂_t = P(s_t | x_0..x_t)``, émissions normalisées, log-vraisemblance."""
        assert self.transmat_ is not None and self.startprob_ is not None
        b, off = self._emissions(x)
        M = self.transmat_[None, :, :] * b[:, None, :]
        M[0] = np.diag(b[0])
        P, logc = _scan(M)
        alpha = np.einsum("i,tij->tj", self.startprob_, P)
        tot = alpha.sum(axis=1)
        tot = np.where(tot > 0, tot, np.finfo(float).tiny)
        filt = alpha / tot[:, None]
        loglik = float(np.log(tot[-1]) + logc[-1] + off.sum())
        return filt, b, M, loglik

    def _backward(self, M: FloatArray) -> FloatArray:
        T, K = M.shape[0], M.shape[1]
        beta = np.ones((T, K))
        if T > 1:
            S, _ = _scan(M[1:], reverse=True)
            beta[:-1] = S.sum(axis=2)
        beta /= beta.sum(axis=1, keepdims=True)
        return beta

    def _init_params(self, x: FloatArray) -> None:
        """Initialisation déterministe par quantiles des écarts au carré.

        Les observations sont réparties en ``K`` groupes de taille égale selon
        ``(x - médiane)²`` ; ``σ²_k`` est la moyenne de ce carré dans le groupe
        ``k`` et ``μ_k`` la moyenne de ``x`` dans le groupe : états distincts
        dès le départ (pas de point selle symétrique pour l'EM).
        """
        K = self.n_states
        self.startprob_ = np.full(K, 1.0 / K)
        stay = 0.95 if K > 1 else 1.0
        A = np.full((K, K), (1.0 - stay) / max(K - 1, 1))
        np.fill_diagonal(A, stay)
        self.transmat_ = A
        d2 = (x - np.median(x)) ** 2
        groups = np.array_split(np.argsort(d2, kind="stable"), K)
        floor = max(float(x.var()) * self.min_variance_ratio, 1e-14)
        self.means_ = np.array([float(x[g].mean()) for g in groups])
        self.variances_ = np.maximum(np.array([float(d2[g].mean()) for g in groups]), floor)

    def _get_params(self) -> tuple[FloatArray, FloatArray, FloatArray, FloatArray]:
        assert self.startprob_ is not None and self.transmat_ is not None
        assert self.means_ is not None and self.variances_ is not None
        return self.startprob_.copy(), self.transmat_.copy(), self.means_.copy(), self.variances_.copy()

    def _set_params(self, params: tuple[FloatArray, FloatArray, FloatArray, FloatArray]) -> None:
        self.startprob_, self.transmat_, self.means_, self.variances_ = (a.copy() for a in params)

    def _sort_states(self) -> None:
        assert self.variances_ is not None and self.transmat_ is not None
        assert self.means_ is not None and self.startprob_ is not None
        order = np.argsort(self.variances_)
        self.variances_ = self.variances_[order]
        self.means_ = self.means_[order]
        self.startprob_ = self.startprob_[order]
        self.transmat_ = self.transmat_[np.ix_(order, order)]

    # -- API -----------------------------------------------------------------

    def fit(self, x: npt.ArrayLike, warm_start: bool = False) -> GaussianHMM:
        """Estime les paramètres par Baum-Welch.

        Départ « à froid » déterministe (:meth:`_init_params` : ``π``
        uniforme, ``A_ii = 0,95``, variances par quantiles). Avec
        ``warm_start=True`` et un modèle déjà estimé, l'EM est aussi lancé
        depuis les paramètres courants et l'on garde la solution de plus
        grande vraisemblance (l'EM ne garantit qu'un optimum local).
        """
        xs = self._clean(x)
        if self.n_states < 1:
            raise ValueError("n_states doit être >= 1")
        if xs.size < 2 * self.n_states + 2:
            raise ValueError("série trop courte pour estimer le modèle")
        starts = []
        if warm_start and self.transmat_ is not None:
            _, A, mu, var = self._get_params()
            starts.append((np.full(self.n_states, 1.0 / self.n_states), A, mu, var))
        self._init_params(xs)
        starts.append(self._get_params())
        best: tuple[float, tuple[FloatArray, FloatArray, FloatArray, FloatArray], int] | None = None
        for start in starts:
            self._set_params(start)
            n_iter = self._em(xs)
            ll = self.score(xs)
            if best is None or ll > best[0]:
                best = (ll, self._get_params(), n_iter)
        assert best is not None
        self._set_params(best[1])
        self.n_iter_ = best[2]
        self._sort_states()
        self.loglik_ = best[0]
        return self

    def _em(self, xs: FloatArray) -> int:
        """Itérations EM depuis les paramètres courants ; renvoie le nombre d'itérations."""
        var_floor = max(float(xs.var()) * self.min_variance_ratio, 1e-14)
        prev = -np.inf
        it = 0
        for it in range(1, self.max_iter + 1):
            filt, b, M, ll = self._forward(xs)
            beta = self._backward(M)
            gamma = filt * beta
            gamma /= gamma.sum(axis=1, keepdims=True)
            assert self.transmat_ is not None
            xi = filt[:-1, :, None] * self.transmat_[None, :, :] * (b[1:] * beta[1:])[:, None, :]
            xi_sum = xi / xi.sum(axis=(1, 2), keepdims=True)
            # Étape M
            w = gamma.sum(axis=0)
            used = w > 1e-10
            self.startprob_ = gamma[0]
            A_num = xi_sum.sum(axis=0)
            A_new = A_num / np.maximum(A_num.sum(axis=1, keepdims=True), 1e-300)
            self.transmat_ = np.where(used[:, None], A_new, self.transmat_)
            mu = (gamma * xs[:, None]).sum(axis=0) / np.maximum(w, 1e-300)
            var = (gamma * (xs[:, None] - mu[None, :]) ** 2).sum(axis=0) / np.maximum(w, 1e-300)
            assert self.means_ is not None and self.variances_ is not None
            self.means_ = np.where(used, mu, self.means_)
            self.variances_ = np.maximum(np.where(used, var, self.variances_), var_floor)
            if abs(ll - prev) <= self.tol * xs.size:
                break
            prev = ll
        return it

    def n_parameters(self) -> int:
        """Nombre de paramètres libres : ``(K-1) + K(K-1) + 2K``."""
        K = self.n_states
        return (K - 1) + K * (K - 1) + 2 * K

    def bic_gain(self, x: npt.ArrayLike) -> float:
        """Écart de BIC (Schwarz, 1978) entre une loi normale unique et ce modèle.

        ``ΔBIC = [-2 ln L_1 + 2 ln n] - [-2 ln L_K + p_K ln n]`` ; ``> 0`` : le
        modèle à ``K`` états est préféré (les régimes sont réellement
        distincts sur cet échantillon).
        """
        xs = self._clean(x)
        n = xs.size
        ll1 = -0.5 * n * (math.log(2.0 * math.pi * max(float(xs.var()), 1e-300)) + 1.0)
        llk = self.score(xs)
        return (-2.0 * ll1 + 2.0 * math.log(n)) - (-2.0 * llk + self.n_parameters() * math.log(n))

    def score(self, x: npt.ArrayLike) -> float:
        """Log-vraisemblance ``ln p(x_0..x_{T-1})``."""
        self._check_fitted()
        return self._forward(self._clean(x))[3]

    def filter(self, x: npt.ArrayLike) -> FloatArray:
        """Probabilités filtrées ``P(s_t | x_0..x_t)`` (``T × K``), causales."""
        self._check_fitted()
        return self._forward(self._clean(x))[0]

    def smooth(self, x: npt.ArrayLike) -> FloatArray:
        """Probabilités lissées ``P(s_t | x_0..x_{T-1})`` — **utilisent le futur**, analyse seulement."""
        self._check_fitted()
        filt, _, M, _ = self._forward(self._clean(x))
        gamma = filt * self._backward(M)
        return gamma / gamma.sum(axis=1, keepdims=True)


def hmm_filtered_probabilities(
    returns: pd.Series,
    n_states: int = 2,
    refit_every: int = 63,
    train_window: int | None = 1000,
    min_train: int = 252,
    max_iter: int = 50,
    tol: float = 1e-6,
    warm_start: bool = True,
    min_sigma_ratio: float | None = None,
    bic_check: bool = False,
) -> pd.DataFrame:
    """Probabilités d'état d'un HMM gaussien ré-estimé périodiquement sur le passé.

    Dates de ré-estimation (positions parmi les rendements observés) :
    ``τ_k = min_train - 1 + k · refit_every``, ancrées sur le **début** de la
    série (ajouter des données futures ne les déplace pas). En ``τ_k`` le
    modèle est estimé sur ``x[τ_k - W + 1 .. τ_k]`` (``W = train_window`` ou
    tout l'historique) ; pour ``t ∈ [τ_k, τ_{k+1})`` on publie la probabilité
    **filtrée** ``P(s_t | x_{τ_k-W+1..t}; θ_k)``. Avant ``τ_0`` : NaN.

    Identifiabilité : les états sont définis **relativement** à la fenêtre
    d'estimation ; une fenêtre entièrement calme est découpée en deux
    sous-états calmes et ``p_{K-1}`` n'y signifie pas « turbulent ». Avec
    ``min_sigma_ratio`` (par ex. 1,5), un bloc dont le modèle a
    ``σ_{K-1} / σ_0 < min_sigma_ratio`` reçoit des probabilités NaN
    (régimes non discriminés) ; avec ``bic_check=True``, de même si le
    critère BIC (Schwarz, 1978) préfère une loi normale unique sur la fenêtre
    d'estimation (:meth:`GaussianHMM.bic_gain` ``<= 0``).

    À chaque ré-estimation, l'EM part à la fois des paramètres précédents
    (``warm_start``) et d'une initialisation à froid ; la meilleure
    vraisemblance est retenue. ``max_iter = 50`` suffit : sur des données à
    régimes l'EM converge en une dizaine d'itérations, et sans régime il
    rampe sans changer le verdict du BIC.

    Returns
    -------
    pd.DataFrame
        Colonnes ``p_0..p_{K-1}`` (état 0 = le plus calme), ``state`` (état le
        plus probable), ``sigma_0..sigma_{K-1}`` (volatilités annualisées des
        états du modèle en vigueur). Index de ``returns`` ; les dates à
        rendement manquant reprennent la dernière valeur connue.
    """
    if refit_every < 1 or min_train < 2 * n_states + 2:
        raise ValueError("refit_every >= 1 et min_train >= 2K + 2 requis")
    if train_window is not None and train_window < min_train:
        raise ValueError("train_window doit être >= min_train")
    s = pd.to_numeric(returns, errors="coerce").astype(float)
    x_s = s[np.isfinite(s)]
    x = x_s.to_numpy(dtype=float)
    T, K = x.size, n_states
    probs = np.full((T, K), np.nan)
    sigmas = np.full((T, K), np.nan)
    model = GaussianHMM(n_states=K, max_iter=max_iter, tol=tol)
    fitted = False
    for tau in range(min_train - 1, T, refit_every):
        start = 0 if train_window is None else max(0, tau - train_window + 1)
        model.fit(x[start : tau + 1], warm_start=warm_start and fitted)
        fitted = True
        end = min(T, tau + refit_every)
        assert model.variances_ is not None
        sigmas[tau:end] = np.sqrt(model.variances_ * TRADING_DAYS)[None, :]
        ratio = math.sqrt(model.variances_[-1] / model.variances_[0])
        if min_sigma_ratio is not None and ratio < min_sigma_ratio:
            continue
        if bic_check and model.bic_gain(x[start : tau + 1]) <= 0:
            continue
        filt = model.filter(x[start:end])
        probs[tau:end] = filt[tau - start :]
    cols = {f"p_{k}": probs[:, k] for k in range(K)}
    out = pd.DataFrame(cols, index=x_s.index)
    valid = np.isfinite(probs).all(axis=1)
    state = np.full(T, np.nan)
    state[valid] = probs[valid].argmax(axis=1)
    out["state"] = state
    for k in range(K):
        out[f"sigma_{k}"] = sigmas[:, k]
    return _reindex_carry(out, s.index)


def _reindex_carry(df: pd.DataFrame, index: pd.Index) -> pd.DataFrame:
    """Réindexe ``df`` sur ``index`` ; seules les dates **absentes** de ``df``
    reprennent la dernière valeur connue (aucune information nouvelle ce jour-là)."""
    full = df.reindex(index)
    missing = ~index.isin(df.index)
    if missing.any():
        full.loc[missing] = full.ffill().loc[missing]
    return full


# ---------------------------------------------------------------------------
# Régime de marché
# ---------------------------------------------------------------------------


def _apply_confirmation(raw: pd.Series, confirm_days: int) -> pd.Series:
    """Hystérésis : un nouvel état n'est adopté qu'après ``confirm_days`` séances consécutives."""
    if confirm_days <= 1:
        return raw
    vals = raw.to_numpy(dtype=object)
    out = np.empty(len(vals), dtype=object)
    current: object = None
    cand: object = None
    run = 0
    for i, v in enumerate(vals):
        if v is None or (isinstance(v, float) and math.isnan(v)):
            out[i] = current
            continue
        if current is None:
            current = v
        elif v == current:
            cand, run = None, 0
        else:
            if v == cand:
                run += 1
            else:
                cand, run = v, 1
            if run >= confirm_days:
                current, cand, run = v, None, 0
        out[i] = current
    return pd.Series(out, index=raw.index, dtype=object)


def market_regime(
    index_level: pd.Series,
    ma_window: int = 200,
    slope_window: int = 20,
    vol_window: int = 21,
    vol_rank_window: int = 756,
    vol_rank_min_periods: int = 126,
    band: float = 0.0,
    stress_vol_pct: float = 0.90,
    stress_drawdown: float = 0.15,
    crash_window: int = 63,
    confirm_days: int = 1,
    hmm: bool = False,
    hmm_refit_every: int = 63,
    hmm_train_window: int | None = 1000,
    hmm_min_train: int = 252,
    hmm_stress_prob: float = 0.80,
    hmm_min_sigma_ratio: float | None = 1.5,
    hmm_bic_check: bool = True,
    hmm_max_iter: int = 50,
) -> pd.DataFrame:
    """Régime de l'indice de marché, séance par séance, sans anticipation.

    Colonnes :

    ``level``           niveau de l'indice ;
    ``ma``              moyenne mobile simple sur ``ma_window`` séances
                        (200 : Brock, Lakonishok & LeBaron, 1992 ; Faber, 2007) ;
    ``trend``           ``level / ma - 1`` ;
    ``ma_slope``        ``ma_t / ma_{t-slope_window} - 1`` ;
    ``realized_vol``    écart-type des rendements logarithmiques sur
                        ``vol_window`` séances × ``sqrt(252)`` ;
    ``vol_percentile``  rang centile de ``realized_vol`` parmi ses
                        ``vol_rank_window`` dernières valeurs (incluse) ;
    ``drawdown``        ``level / max_{s<=t} level_s - 1`` (depuis l'origine) ;
    ``recent_drawdown`` ``level / max_{t-crash_window<s<=t} level_s - 1`` ;
    ``state``           ``"haussier" | "neutre" | "baissier" | "stress"`` (règles
                        du docstring du module) ;
    ``p_turbulent``, ``hmm_state``, ``hmm_sigma_calm``, ``hmm_sigma_turbulent``
                        si ``hmm=True`` (HMM gaussien à 2 états ré-estimé tous
                        les ``hmm_refit_every`` jours sur le passé, voir
                        :func:`hmm_filtered_probabilities` ; Kritzman, Page &
                        Turkington, 2012). ``p_turbulent`` est NaN quand le
                        modèle en vigueur ne discrimine pas deux régimes
                        (``σ_turb / σ_calme < hmm_min_sigma_ratio`` ou BIC
                        défavorable si ``hmm_bic_check``) : la règle de
                        stress se rabat alors sur ``vol_percentile``.

    Les séances où l'indice est manquant reprennent l'état de la veille (pas
    d'information nouvelle) ; ``level`` y reste NaN.

    Parameters
    ----------
    index_level
        Niveau de l'indice (``pd.Series`` indexée par date, croissante).
    band
        Zone neutre autour de la moyenne mobile (``0,01`` = ±1 %).
    stress_vol_pct, stress_drawdown, crash_window
        Seuils de l'état ``"stress"`` : percentile de volatilité, chute depuis
        le plus haut des ``crash_window`` dernières séances.
    confirm_days
        Séances consécutives nécessaires pour changer d'état (1 : aucun filtre).
    """
    if not isinstance(index_level, pd.Series):
        raise TypeError("index_level doit être une pd.Series de niveaux")
    if not isinstance(index_level.index, pd.DatetimeIndex):
        raise TypeError("index_level doit être indexée par un DatetimeIndex")
    if not index_level.index.is_monotonic_increasing:
        raise ValueError("index_level doit être triée par date croissante")
    if min(ma_window, slope_window, vol_window, vol_rank_window, crash_window) < 1:
        raise ValueError("les fenêtres doivent être >= 1")
    raw = pd.to_numeric(index_level, errors="coerce").astype(float)
    lvl = raw[np.isfinite(raw) & (raw > 0)]

    ma = lvl.rolling(ma_window, min_periods=ma_window).mean()
    trend = lvl / ma - 1.0
    slope = ma / ma.shift(slope_window) - 1.0
    logret = np.log(lvl / lvl.shift(1))
    rv = logret.rolling(vol_window, min_periods=vol_window).std(ddof=1) * math.sqrt(TRADING_DAYS)
    vol_pct = rv.rolling(vol_rank_window, min_periods=min(vol_rank_min_periods, vol_rank_window)).rank(
        pct=True
    )
    dd = lvl / lvl.cummax() - 1.0
    dd_recent = lvl / lvl.rolling(crash_window, min_periods=1).max() - 1.0

    out = pd.DataFrame(
        {
            "level": lvl,
            "ma": ma,
            "trend": trend,
            "ma_slope": slope,
            "realized_vol": rv,
            "vol_percentile": vol_pct,
            "drawdown": dd,
            "recent_drawdown": dd_recent,
        }
    )
    high_vol = vol_pct.ge(stress_vol_pct).fillna(False)
    if hmm:
        hm = hmm_filtered_probabilities(
            logret,
            n_states=2,
            refit_every=hmm_refit_every,
            train_window=hmm_train_window,
            min_train=hmm_min_train,
            min_sigma_ratio=hmm_min_sigma_ratio,
            bic_check=hmm_bic_check,
            max_iter=hmm_max_iter,
        )
        out["p_turbulent"] = hm["p_1"]
        out["hmm_state"] = hm["state"]
        out["hmm_sigma_calm"] = hm["sigma_0"]
        out["hmm_sigma_turbulent"] = hm["sigma_1"]
        high_vol = high_vol | hm["p_1"].ge(hmm_stress_prob).fillna(False)

    defined = trend.notna() & slope.notna()
    stress = (trend < 0) & (high_vol | (dd_recent <= -stress_drawdown))
    bull = (trend > band) & (slope > 0)
    bear = (trend < -band) & (slope < 0)
    state = pd.Series(
        np.select([stress, bull, bear], ["stress", "haussier", "baissier"], default="neutre"),
        index=lvl.index,
        dtype=object,
    ).where(defined, None)
    out["state"] = _apply_confirmation(state, confirm_days)

    full = _reindex_carry(out, raw.index)
    full["level"] = raw.where(raw > 0)
    return full
