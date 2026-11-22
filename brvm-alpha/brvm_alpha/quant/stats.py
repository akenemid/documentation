"""Statistiques de performance et inférence robuste pour BRVM Alpha.

Ce module rassemble les mesures de performance d'une stratégie et, surtout,
les outils qui permettent de juger si une performance observée est
*statistiquement crédible* plutôt que le fruit du hasard ou du sur-ajustement
(« backtest overfitting »). Sur un marché étroit comme la BRVM (≈ 48 actions,
nombreuses séances sans échange, prix périmés, limites de variation de
±7,5 %), ces corrections ne sont pas un luxe : l'autocorrélation induite par
les prix périmés gonfle mécaniquement le ratio de Sharpe, et le nombre de
configurations testées gonfle le meilleur Sharpe observé.

Contenu
-------
Mesures descriptives
    :func:`perf_summary`, :func:`sharpe_ratio`, :func:`rolling_drawdown`,
    :func:`rolling_max_drawdown`, :func:`drawdown_episodes`, :func:`ic_summary`.
Inférence sur le ratio de Sharpe
    :func:`probabilistic_sharpe` (Bailey & López de Prado, 2012),
    :func:`deflated_sharpe` et :func:`expected_max_sharpe`
    (Bailey & López de Prado, 2014), :func:`min_track_record_length`
    (Bailey & López de Prado, 2012), :func:`lo_adjusted_sharpe` (Lo, 2002),
    :func:`haircut_sharpe` (Harvey, Liu & Zhu, 2016 ; Harvey & Liu, 2015).
Rééchantillonnage et sur-ajustement
    :func:`stationary_bootstrap` (Politis & Romano, 1994),
    :func:`pbo_cscv` (Bailey, Borwein, López de Prado & Zhu, 2017).
Économétrie
    :func:`dimson_beta` (Dimson, 1979), :func:`newey_west_tstat`
    (Newey & West, 1987, 1994), :func:`adjust_pvalues` (Holm, 1979 ;
    Benjamini & Hochberg, 1995 ; Benjamini & Yekutieli, 2001).

Conventions
-----------
* Rendements simples en décimal (0,01 = 1 %), une observation par séance.
* Annualisation par défaut : 252 séances (``periods_per_year``).
* Les ``NaN`` (titre ou portefeuille sans observation) sont **ignorés** par
  les fonctions statistiques ; les valeurs infinies sont refusées
  (``ValueError``) car elles signalent une donnée corrompue.
* Ratios de Sharpe « par période » (non annualisés) dans les formules de
  Bailey & López de Prado, comme dans les articles originaux. Les fonctions
  qui acceptent un Sharpe de référence proposent l'argument optionnel
  ``periods_per_year`` : s'il est fourni, la référence est lue en unités
  annualisées puis convertie (``SR_période = SR_annuel / sqrt(periods_per_year)``).
* Moments d'ordre 3 et 4 : estimateurs « population » (biaisés), c'est-à-dire
  ``scipy.stats.skew(x)`` et ``scipy.stats.kurtosis(x, fisher=False)``, comme
  dans le code de référence de López de Prado ; écart-type avec ``ddof=1``.
* Aucune fonction n'utilise d'information future : toutes opèrent sur la série
  passée en argument (les fonctions glissantes n'utilisent que le passé).

Références
----------
* Bailey, D. H. & López de Prado, M. (2012). The Sharpe Ratio Efficient
  Frontier. *Journal of Risk*, 15(2), 3-44.
* Bailey, D. H. & López de Prado, M. (2014). The Deflated Sharpe Ratio:
  Correcting for Selection Bias, Backtest Overfitting and Non-Normality.
  *Journal of Portfolio Management*, 40(5), 94-107.
* Bailey, D. H., Borwein, J., López de Prado, M. & Zhu, Q. J. (2017). The
  Probability of Backtest Overfitting. *Journal of Computational Finance*,
  20(4), 39-69.
* Benjamini, Y. & Yekutieli, D. (2001). The control of the false discovery
  rate in multiple testing under dependency. *Annals of Statistics*, 29(4).
* Dimson, E. (1979). Risk measurement when shares are subject to infrequent
  trading. *Journal of Financial Economics*, 7(2), 197-226.
* Harvey, C. R. & Liu, Y. (2015). Backtesting. *Journal of Portfolio
  Management*, 42(1), 13-28.
* Harvey, C. R., Liu, Y. & Zhu, H. (2016). ... and the Cross-Section of
  Expected Returns. *Review of Financial Studies*, 29(1), 5-68.
* Holm, S. (1979). A simple sequentially rejective multiple test procedure.
  *Scandinavian Journal of Statistics*, 6(2), 65-70.
* Lo, A. W. (2002). The Statistics of Sharpe Ratios. *Financial Analysts
  Journal*, 58(4), 36-52.
* Mertens, E. (2002). Comments on variance of the IID estimator in Lo (2002).
  Note de recherche, Université de Bâle.
* Newey, W. K. & West, K. D. (1987). A Simple, Positive Semi-Definite,
  Heteroskedasticity and Autocorrelation Consistent Covariance Matrix.
  *Econometrica*, 55(3), 703-708 ; (1994) Automatic Lag Selection in
  Covariance Matrix Estimation. *Review of Economic Studies*, 61(4).
* Politis, D. N. & Romano, J. P. (1994). The Stationary Bootstrap. *Journal of
  the American Statistical Association*, 89(428), 1303-1313.
* Sortino, F. A. & Price, L. N. (1994). Performance Measurement in a Downside
  Risk Framework. *Journal of Investing*, 3(3), 59-64.
* Young, T. W. (1991). Calmar Ratio: A Smoother Tool. *Futures*, 20(1).
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Callable, Sequence
from typing import Any, TypeAlias

import numpy as np
import numpy.typing as npt
import pandas as pd
from scipy import stats as sps

__all__ = [
    "EULER_MASCHERONI",
    "TRADING_DAYS",
    "adjust_pvalues",
    "deflated_sharpe",
    "dimson_beta",
    "dimson_betas",
    "drawdown_episodes",
    "expected_max_sharpe",
    "haircut_sharpe",
    "haircut_sharpe_details",
    "ic_summary",
    "lo_adjusted_sharpe",
    "long_run_variance",
    "min_track_record_length",
    "newey_west_lags",
    "newey_west_tstat",
    "pbo_cscv",
    "perf_summary",
    "probabilistic_sharpe",
    "rolling_drawdown",
    "rolling_max_drawdown",
    "sharpe_ratio",
    "sharpe_std_error",
    "stationary_bootstrap",
]

#: Constante d'Euler-Mascheroni γ (approximation de Gumbel du maximum).
EULER_MASCHERONI: float = 0.5772156649015329

#: Nombre de séances par an (convention de la plate-forme).
TRADING_DAYS: int = 252

#: Seuil sous lequel une variance est considérée comme nulle.
_TINY: float = 1e-14

#: Tolérance relative pour décider qu'un portefeuille est « sous l'eau ».
_DD_TOL: float = 1e-12

FloatArray: TypeAlias = npt.NDArray[np.float64]
ArrayLike: TypeAlias = pd.Series | np.ndarray | Sequence[float]


# ---------------------------------------------------------------------------
# Utilitaires internes
# ---------------------------------------------------------------------------


def _as_series(x: Any) -> pd.Series:
    """Convertit ``x`` en ``pd.Series`` de flottants (index conservé).

    Accepte une ``Series``, un ``DataFrame`` d'une seule colonne, un tableau
    NumPy 1-D ou une séquence. Refuse les valeurs infinies.
    """
    if isinstance(x, pd.DataFrame):
        if x.shape[1] != 1:
            raise ValueError("un DataFrame d'une seule colonne est attendu")
        x = x.iloc[:, 0]
    if isinstance(x, pd.Series):
        s = x.astype(float)
    else:
        arr = np.asarray(x, dtype=float)
        if arr.ndim != 1:
            raise ValueError("une série 1-D est attendue")
        s = pd.Series(arr)
    values = s.to_numpy(dtype=float)
    if np.isinf(values).any():
        raise ValueError("la série contient des valeurs infinies")
    return s


def _clean(x: Any) -> FloatArray:
    """Renvoie les valeurs finies de ``x`` sous forme de tableau NumPy 1-D."""
    arr = _as_series(x).to_numpy(dtype=float)
    return arr[~np.isnan(arr)]


def _to_period_sr(sr: float, periods_per_year: int | None) -> float:
    """Convertit un Sharpe annualisé en Sharpe par période si demandé."""
    if periods_per_year is None:
        return float(sr)
    if periods_per_year <= 0:
        raise ValueError("periods_per_year doit être > 0")
    return float(sr) / math.sqrt(periods_per_year)


def _sr_moments(x: FloatArray) -> tuple[float, float, float, int]:
    """Sharpe par période, asymétrie et kurtosis brute (biaisées), effectif.

    Renvoie ``(SR, γ3, γ4, n)`` avec ``SR = moyenne / écart-type (ddof=1)``,
    ``γ3 = E[(x-μ)^3]/σ^3`` et ``γ4 = E[(x-μ)^4]/σ^4`` (loi normale : 0 et 3).
    Si la série est constante, ``SR`` vaut NaN, ``γ3 = 0`` et ``γ4 = 3``.
    """
    n = int(x.size)
    if n < 2:
        return math.nan, math.nan, math.nan, n
    sd = float(np.std(x, ddof=1))
    if sd <= _TINY * max(1.0, float(np.abs(x).max())):
        return math.nan, 0.0, 3.0, n
    sr = float(np.mean(x)) / sd
    skew = float(sps.skew(x, bias=True))
    kurt = float(sps.kurtosis(x, fisher=False, bias=True))
    return sr, skew, kurt, n


def _sr_variance_factor(sr: float, skew: float, kurt: float) -> float:
    """Facteur ``1 - γ3·SR + (γ4 - 1)/4·SR²`` de la variance asymptotique du SR.

    Mertens (2002) ; Bailey & López de Prado (2012), éq. (4). L'inégalité de
    Pearson ``γ4 ≥ 1 + γ3²`` garantit que ce facteur est ``≥ (1 - γ3·SR/2)² ≥ 0``
    (y compris pour les moments empiriques) ; il est borné inférieurement par
    une petite constante pour éviter une division par zéro.
    """
    value = 1.0 - skew * sr + (kurt - 1.0) / 4.0 * sr * sr
    return max(value, 1e-12)


def _acf(x: FloatArray, nlags: int) -> FloatArray:
    """Autocorrélations empiriques ``ρ_1..ρ_nlags``.

    ``ρ_k = Σ_{t>k} (x_t - x̄)(x_{t-k} - x̄) / Σ_t (x_t - x̄)²`` (dénominateur
    commun, estimateur semi-défini positif de Box & Jenkins).
    """
    d = x - x.mean()
    denom = float(d @ d)
    n = x.size
    out = np.zeros(nlags, dtype=float)
    if denom <= 0.0:
        return out
    for k in range(1, min(nlags, n - 1) + 1):
        out[k - 1] = float(d[k:] @ d[:-k]) / denom
    return out


def _drawdown_array(r: FloatArray) -> FloatArray:
    """Drawdown ``DD_t = W_t / max(1, max_{s≤t} W_s) - 1`` avec ``W = Π(1+r)``.

    Le capital initial (1) compte comme premier plus haut : une perte dès la
    première séance est donc un drawdown.
    """
    wealth = np.cumprod(1.0 + r)
    peak = np.maximum.accumulate(np.concatenate(([1.0], wealth)))[1:]
    return wealth / peak - 1.0


def _episodes_from_dd(dd: FloatArray, labels: pd.Index) -> pd.DataFrame:
    """Découpe une série de drawdowns en épisodes « sous l'eau »."""
    under = dd < -_DD_TOL
    edges = np.flatnonzero(np.diff(np.concatenate(([0], under.astype(np.int8), [0]))))
    starts, ends = edges[::2], edges[1::2]  # ``ends`` exclusif
    n = dd.size
    rows: list[dict[str, Any]] = []
    for s, e in zip(starts, ends, strict=True):
        trough = int(s + np.argmin(dd[s:e]))
        recovered = bool(e < n)
        rows.append(
            {
                "peak": labels[s - 1] if s > 0 else None,
                "start": labels[s],
                "trough": labels[trough],
                "recovery": labels[e] if recovered else None,
                "depth": float(dd[trough]),
                "length": int(e - s),
                "to_trough": int(trough - s + 1),
                "recovered": recovered,
            }
        )
    cols = ["peak", "start", "trough", "recovery", "depth", "length", "to_trough", "recovered"]
    return pd.DataFrame(rows, columns=cols)


# ---------------------------------------------------------------------------
# Ratio de Sharpe et inférence
# ---------------------------------------------------------------------------


def sharpe_ratio(
    returns: ArrayLike,
    rf: float = 0.0,
    periods_per_year: int | None = TRADING_DAYS,
) -> float:
    """Ratio de Sharpe (Sharpe, 1966 ; 1994).

    ``SR = mean(r - rf_p) / std(r - rf_p)`` (écart-type ``ddof=1``), multiplié
    par ``sqrt(periods_per_year)`` si ``periods_per_year`` n'est pas ``None``.

    Parameters
    ----------
    returns
        Rendements simples par période ; les NaN sont ignorés.
    rf
        Taux sans risque. Annuel si ``periods_per_year`` est fourni (converti
        géométriquement : ``rf_p = (1 + rf)^(1/P) - 1``), par période sinon.
    periods_per_year
        Nombre de périodes par an ; ``None`` pour un Sharpe par période.

    Returns
    -------
    float
        NaN si moins de deux observations ou si la volatilité est nulle.
    """
    x = _clean(returns)
    if periods_per_year is None:
        rf_p = float(rf)
    else:
        rf_p = (1.0 + rf) ** (1.0 / periods_per_year) - 1.0
    sr, _, _, _ = _sr_moments(x - rf_p)
    if periods_per_year is None or math.isnan(sr):
        return sr
    return sr * math.sqrt(periods_per_year)


def sharpe_std_error(returns: ArrayLike) -> float:
    """Écart-type asymptotique du Sharpe par période, rendements non normaux.

    Mertens (2002) ; Bailey & López de Prado (2012) :

    ``σ(SR̂) = sqrt( (1 - γ3·SR + (γ4 - 1)/4 · SR²) / (n - 1) )``

    où ``γ3`` est l'asymétrie et ``γ4`` la kurtosis brute (normale = 3).
    """
    sr, skew, kurt, n = _sr_moments(_clean(returns))
    if n < 3 or math.isnan(sr):
        return math.nan
    return math.sqrt(_sr_variance_factor(sr, skew, kurt) / (n - 1))


def probabilistic_sharpe(
    returns: ArrayLike,
    sr_benchmark: float = 0.0,
    periods_per_year: int | None = None,
) -> float:
    """Probabilistic Sharpe Ratio (Bailey & López de Prado, 2012, éq. 11).

    Probabilité que le vrai Sharpe dépasse ``SR*`` compte tenu de la longueur
    de l'historique, de l'asymétrie et de l'épaisseur des queues :

    ``PSR(SR*) = Φ( (SR̂ - SR*)·sqrt(n - 1) / sqrt(1 - γ3·SR̂ + (γ4 - 1)/4·SR̂²) )``

    avec ``SR̂`` le Sharpe **par période**, ``γ3`` l'asymétrie, ``γ4`` la
    kurtosis brute et ``Φ`` la fonction de répartition normale.

    Parameters
    ----------
    returns
        Rendements (de préférence en excès du taux sans risque) ; NaN ignorés.
    sr_benchmark
        Sharpe de référence ``SR*``. Par période par défaut ; annualisé si
        ``periods_per_year`` est fourni.
    periods_per_year
        Si fourni, ``sr_benchmark`` est lu en unités annualisées.

    Returns
    -------
    float
        Probabilité dans [0, 1] ; NaN si moins de 3 observations ou si la
        volatilité est nulle.
    """
    sr_star = _to_period_sr(sr_benchmark, periods_per_year)
    sr, skew, kurt, n = _sr_moments(_clean(returns))
    if n < 3 or math.isnan(sr):
        return math.nan
    z = (sr - sr_star) * math.sqrt(n - 1) / math.sqrt(_sr_variance_factor(sr, skew, kurt))
    return float(sps.norm.cdf(z))


def expected_max_sharpe(n_trials: int, sr_variance: float, sr_mean: float = 0.0) -> float:
    """Espérance du maximum de ``N`` Sharpe estimés (approximation de Gumbel).

    Bailey & López de Prado (2014), éq. (2) ; théorème de Fisher-Tippett :

    ``E[max SR] ≈ μ_SR + σ_SR·[ (1 - γ)·Φ⁻¹(1 - 1/N) + γ·Φ⁻¹(1 - 1/(N·e)) ]``

    où ``γ ≈ 0,5772`` est la constante d'Euler-Mascheroni et
    ``σ_SR = sqrt(sr_variance)`` la dispersion des Sharpe entre essais. Le
    résultat est dans les mêmes unités que ``sr_mean`` et ``sqrt(sr_variance)``.

    Parameters
    ----------
    n_trials
        Nombre d'essais indépendants ``N ≥ 1`` (``N = 1`` → ``μ_SR``).
    sr_variance
        Variance des Sharpe entre essais (``≥ 0``).
    sr_mean
        Moyenne des Sharpe entre essais (0 sous l'hypothèse nulle).
    """
    if n_trials < 1:
        raise ValueError("n_trials doit être >= 1")
    if sr_variance < 0:
        raise ValueError("sr_variance doit être >= 0")
    if n_trials == 1:
        return float(sr_mean)
    g = EULER_MASCHERONI
    z = (1.0 - g) * sps.norm.ppf(1.0 - 1.0 / n_trials) + g * sps.norm.ppf(
        1.0 - 1.0 / (n_trials * math.e)
    )
    return float(sr_mean + math.sqrt(sr_variance) * z)


def deflated_sharpe(
    returns: ArrayLike,
    n_trials: int,
    sr_variance: float,
    sr_mean: float = 0.0,
    periods_per_year: int | None = None,
) -> float:
    """Deflated Sharpe Ratio (Bailey & López de Prado, 2014, éq. 3).

    PSR évalué au seuil ``SR₀`` égal au meilleur Sharpe attendu *par hasard*
    parmi ``N`` essais :

    ``DSR = PSR(SR₀)``, ``SR₀ = E[max_{n≤N} SR_n]`` (voir
    :func:`expected_max_sharpe`).

    Un DSR > 0,95 signifie que la stratégie retenue reste significative après
    prise en compte du biais de sélection (nombre de configurations testées),
    de la longueur de l'historique et de la non-normalité.

    Parameters
    ----------
    returns
        Rendements de la stratégie **retenue**.
    n_trials
        Nombre d'essais (configurations réellement testées, ou nombre effectif
        d'essais indépendants).
    sr_variance
        Variance des Sharpe des essais. Par période par défaut ; en unités
        annualisées si ``periods_per_year`` est fourni (``V_période = V_an / P``).
    sr_mean
        Moyenne des Sharpe des essais (0 par défaut, hypothèse nulle) ; même
        convention d'unités que ``sr_variance``.
    periods_per_year
        Voir ci-dessus.
    """
    if periods_per_year is not None:
        if periods_per_year <= 0:
            raise ValueError("periods_per_year doit être > 0")
        sr_variance = sr_variance / periods_per_year
        sr_mean = sr_mean / math.sqrt(periods_per_year)
    sr0 = expected_max_sharpe(n_trials, sr_variance, sr_mean)
    return probabilistic_sharpe(returns, sr_benchmark=sr0)


def min_track_record_length(
    returns: ArrayLike,
    sr_benchmark: float = 0.0,
    alpha: float = 0.05,
    periods_per_year: int | None = None,
) -> float:
    """Longueur minimale d'historique (Bailey & López de Prado, 2012, éq. 13).

    Nombre d'observations nécessaire pour que ``PSR(SR*) ≥ 1 - α`` :

    ``MinTRL = 1 + (1 - γ3·SR̂ + (γ4 - 1)/4·SR̂²) · ( z_{1-α} / (SR̂ - SR*) )²``

    Parameters
    ----------
    returns
        Rendements observés ; NaN ignorés.
    sr_benchmark
        Sharpe de référence ``SR*`` (par période, ou annualisé si
        ``periods_per_year`` est fourni).
    alpha
        Niveau de risque de première espèce (0,05 → confiance 95 %).
    periods_per_year
        Si fourni, ``sr_benchmark`` est lu en unités annualisées.

    Returns
    -------
    float
        Nombre d'**observations** (diviser par 252 pour des années) ; ``inf``
        si ``SR̂ ≤ SR*`` ; NaN si la série est trop courte ou constante.
    """
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha doit être dans ]0, 1[")
    sr_star = _to_period_sr(sr_benchmark, periods_per_year)
    sr, skew, kurt, n = _sr_moments(_clean(returns))
    if n < 3 or math.isnan(sr):
        return math.nan
    if sr <= sr_star:
        return math.inf
    z = float(sps.norm.ppf(1.0 - alpha))
    return 1.0 + _sr_variance_factor(sr, skew, kurt) * (z / (sr - sr_star)) ** 2


def lo_adjusted_sharpe(
    returns: ArrayLike,
    q: int = 5,
    periods_per_year: int = TRADING_DAYS,
) -> float:
    """Sharpe annualisé corrigé de l'autocorrélation (Lo, 2002, éq. 22).

    L'annualisation naïve ``SR·sqrt(T)`` suppose des rendements indépendants.
    Avec des autocorrélations ``ρ_k`` (typiques des prix périmés de la BRVM),
    Lo (2002) donne pour l'horizon ``T = periods_per_year`` :

    ``SR_T = η(T)·SR``,  ``η(T) = T / sqrt( T + 2·Σ_{k=1}^{T-1} (T - k)·ρ_k )``

    Les ``ρ_k`` sont estimés jusqu'au retard ``q`` et supposés nuls au-delà.
    Pour ``ρ_k = 0`` on retrouve ``η = sqrt(T)``. Une autocorrélation positive
    réduit le Sharpe annualisé ; une négative l'augmente.

    Parameters
    ----------
    returns
        Rendements par période ; NaN ignorés.
    q
        Retard maximal des autocorrélations (``q ≥ 1``).
    periods_per_year
        Horizon d'annualisation ``T``.

    Returns
    -------
    float
        Sharpe annualisé corrigé ; NaN si l'historique est trop court
        (``n ≤ q + 1``), si la volatilité est nulle, ou si la variance agrégée
        estimée est négative (autocorrélations négatives aberrantes).
    """
    if q < 1:
        raise ValueError("q doit être >= 1")
    x = _clean(returns)
    sr, _, _, n = _sr_moments(x)
    if n <= q + 1 or math.isnan(sr):
        return math.nan
    T = int(periods_per_year)
    rho = _acf(x, q)
    k = np.arange(1, min(q, T - 1) + 1)
    denom = T + 2.0 * float(np.sum((T - k) * rho[: k.size]))
    if denom <= 0.0:
        return math.nan
    return float(T / math.sqrt(denom) * sr)


def haircut_sharpe_details(
    sr_annual: float,
    n_obs: int,
    n_tests: int,
    method: str = "holm",
    other_pvalues: Sequence[float] | None = None,
    periods_per_year: int = TRADING_DAYS,
) -> dict[str, Any]:
    """Détail de la décote du Sharpe pour tests multiples.

    Méthode de Harvey & Liu (2015) et Harvey, Liu & Zhu (2016) :

    1. ``t = SR_an · sqrt(n_obs / P)`` (Sharpe annualisé → statistique t,
       ``P = periods_per_year``) ;
    2. p-valeur bilatérale ``p = 2·(1 - Φ(|t|))`` ;
    3. p-valeur ajustée ``p*`` pour ``M = n_tests`` tests (Bonferroni, Holm
       ou BHY, voir :func:`adjust_pvalues`) ;
    4. ``t* = Φ⁻¹(1 - p*/2)`` puis ``SR* = signe(SR)·t* / sqrt(n_obs / P)`` ;
       décote ``= 1 - SR*/SR``.

    Holm et BHY ont besoin des p-valeurs des ``M - 1`` autres tests. Si
    ``other_pvalues`` n'est pas fourni, on suppose que les autres tests sont
    nuls et on prend les espérances des statistiques d'ordre de ``M - 1``
    uniformes : ``p_(i) = i/M``. Dans ce cas Holm coïncide quasiment avec
    Bonferroni, et BHY (procédure conçue pour une dépendance arbitraire, donc
    divisée par ``c(M) = Σ 1/j``) est plus sévère. Fournir les p-valeurs
    réelles des configurations testées (grille du walk-forward) donne une
    décote plus juste ; Harvey & Liu simulent ces p-valeurs à partir d'un
    modèle calibré sur la littérature, non reproduit ici.

    Returns
    -------
    dict
        ``sr_annual``, ``sr_haircut``, ``haircut`` (fraction), ``t_stat``,
        ``t_stat_adjusted``, ``p_value``, ``p_value_adjusted``, ``method``,
        ``n_tests``.
    """
    if n_obs < 2:
        raise ValueError("n_obs doit être >= 2")
    if n_tests < 1:
        raise ValueError("n_tests doit être >= 1")
    years = n_obs / periods_per_year
    t = float(sr_annual) * math.sqrt(years)
    p = float(2.0 * sps.norm.sf(abs(t)))
    if n_tests == 1:
        p_adj = p
    else:
        if other_pvalues is None:
            others = np.arange(1, n_tests, dtype=float) / n_tests
        else:
            others = np.asarray(other_pvalues, dtype=float)
            if others.size != n_tests - 1:
                raise ValueError("other_pvalues doit contenir n_tests - 1 valeurs")
            if np.any((others < 0) | (others > 1)) or np.isnan(others).any():
                raise ValueError("other_pvalues doit être dans [0, 1]")
        p_adj = float(adjust_pvalues(np.concatenate(([p], others)), method=method)[0])
    if p_adj <= 0.0:
        # Signification au-delà de la précision machine : pas de décote mesurable.
        t_adj = abs(t)
    else:
        t_adj = float(sps.norm.isf(p_adj / 2.0))
    sr_adj = math.copysign(t_adj / math.sqrt(years), sr_annual) if sr_annual != 0 else 0.0
    haircut = 1.0 - sr_adj / sr_annual if sr_annual != 0 else 0.0
    return {
        "sr_annual": float(sr_annual),
        "sr_haircut": float(sr_adj),
        "haircut": float(haircut),
        "t_stat": t,
        "t_stat_adjusted": math.copysign(t_adj, t) if t != 0 else 0.0,
        "p_value": p,
        "p_value_adjusted": p_adj,
        "method": method,
        "n_tests": int(n_tests),
    }


def haircut_sharpe(
    sr_annual: float,
    n_obs: int,
    n_tests: int,
    method: str = "holm",
    other_pvalues: Sequence[float] | None = None,
    periods_per_year: int = TRADING_DAYS,
) -> float:
    """Sharpe annualisé après décote pour tests multiples (Harvey, Liu & Zhu, 2016).

    Raccourci de :func:`haircut_sharpe_details` qui ne renvoie que ``SR*``.
    ``method`` ∈ {``"bonferroni"``, ``"holm"``, ``"bhy"``} (et ``"bh"``).
    Exemple : SR annuel 1,0 sur 5 ans (1 260 séances) avec 100 essais,
    Bonferroni → p = 0,0253, p* = 1 → SR* = 0.
    """
    return float(
        haircut_sharpe_details(
            sr_annual,
            n_obs,
            n_tests,
            method=method,
            other_pvalues=other_pvalues,
            periods_per_year=periods_per_year,
        )["sr_haircut"]
    )


def adjust_pvalues(pvalues: ArrayLike, method: str = "holm") -> FloatArray:
    """P-valeurs ajustées pour tests multiples (ordre d'entrée conservé).

    Avec ``p_(1) ≤ … ≤ p_(M)`` les p-valeurs triées :

    * Bonferroni : ``p*_(i) = min(M·p_(i), 1)`` (contrôle du FWER) ;
    * Holm (1979), pas descendant :
      ``p*_(i) = max_{j≤i} min((M - j + 1)·p_(j), 1)`` (FWER) ;
    * BH (Benjamini & Hochberg, 1995), pas montant :
      ``p*_(i) = min_{j≥i} min(M·p_(j)/j, 1)`` (FDR, indépendance) ;
    * BHY (Benjamini & Yekutieli, 2001) :
      ``p*_(i) = min_{j≥i} min(M·c(M)·p_(j)/j, 1)``, ``c(M) = Σ_{j=1}^{M} 1/j``
      (FDR sous dépendance arbitraire ; méthode retenue par Harvey, Liu &
      Zhu, 2016).

    Parameters
    ----------
    pvalues
        P-valeurs dans [0, 1] (pas de NaN).
    method
        ``"bonferroni"``, ``"holm"``, ``"bh"`` ou ``"bhy"`` (alias ``"by"``,
        ``"fdr_by"``).
    """
    p = np.asarray(pvalues, dtype=float).ravel()
    if np.isnan(p).any() or np.any((p < 0) | (p > 1)):
        raise ValueError("les p-valeurs doivent être dans [0, 1] et sans NaN")
    m = p.size
    if m == 0:
        return p.copy()
    key = method.lower()
    order = np.argsort(p, kind="mergesort")
    ps = p[order]
    ranks = np.arange(1, m + 1, dtype=float)
    if key == "bonferroni":
        adj = np.minimum(ps * m, 1.0)
    elif key == "holm":
        adj = np.maximum.accumulate(np.minimum((m - ranks + 1.0) * ps, 1.0))
    elif key in ("bh", "fdr_bh"):
        adj = np.minimum.accumulate((m * ps / ranks)[::-1])[::-1]
        adj = np.minimum(adj, 1.0)
    elif key in ("bhy", "by", "fdr_by"):
        c_m = float(np.sum(1.0 / ranks))
        adj = np.minimum.accumulate((m * c_m * ps / ranks)[::-1])[::-1]
        adj = np.minimum(adj, 1.0)
    else:
        raise ValueError(f"méthode inconnue : {method!r}")
    out = np.empty_like(adj)
    out[order] = adj
    return out


# ---------------------------------------------------------------------------
# Économétrie : Newey-West, bêta de Dimson
# ---------------------------------------------------------------------------


def newey_west_lags(n: int) -> int:
    """Nombre de retards automatique de Newey & West (1994).

    ``L = floor(4·(n/100)^(2/9))`` (au moins 0, au plus ``n - 1``).
    """
    if n <= 1:
        return 0
    return int(min(n - 1, math.floor(4.0 * (n / 100.0) ** (2.0 / 9.0))))


def long_run_variance(series: ArrayLike, lags: int | None = None) -> float:
    """Variance de long terme HAC à noyau de Bartlett (Newey & West, 1987).

    ``Ω̂ = γ̂_0 + 2·Σ_{k=1}^{L} (1 - k/(L+1))·γ̂_k``,
    ``γ̂_k = (1/n)·Σ_{t=k+1}^{n} (x_t - x̄)(x_{t-k} - x̄)``.

    Les NaN sont retirés avant le calcul (la série est traitée comme
    contiguë). ``lags=None`` → :func:`newey_west_lags`.
    """
    x = _clean(series)
    n = x.size
    if n < 2:
        return math.nan
    L = newey_west_lags(n) if lags is None else int(lags)
    if L < 0:
        raise ValueError("lags doit être >= 0")
    L = min(L, n - 1)
    d = x - x.mean()
    omega = float(d @ d) / n
    for k in range(1, L + 1):
        omega += 2.0 * (1.0 - k / (L + 1.0)) * float(d[k:] @ d[:-k]) / n
    return omega


def newey_west_tstat(series: ArrayLike, lags: int | None = None, mu0: float = 0.0) -> float:
    """Statistique t de la moyenne, robuste à l'autocorrélation (Newey-West).

    ``t = (x̄ - μ₀) / sqrt(Ω̂ / n)`` avec ``Ω̂`` la variance de long terme de
    Bartlett (:func:`long_run_variance`). Identique à une régression MCO sur
    une constante avec covariance HAC sans correction de petit échantillon
    (``statsmodels``, ``cov_type="HAC", use_correction=False``).

    Parameters
    ----------
    series
        Série (rendements, IC, rendements longs-courts…) ; NaN ignorés.
    lags
        Retards du noyau ; ``None`` → règle de Newey & West (1994).
    mu0
        Moyenne sous l'hypothèse nulle.
    """
    x = _clean(series)
    n = x.size
    if n < 2:
        return math.nan
    omega = long_run_variance(x, lags)
    if not omega > _TINY * max(1.0, float(np.mean(x * x))):
        return math.nan
    return float((x.mean() - mu0) / math.sqrt(omega / n))


def dimson_betas(asset: ArrayLike, market: ArrayLike, lags: int = 2) -> pd.Series:
    """Coefficients de la régression de Dimson (1979), retard par retard.

    ``r_{i,t} = α + Σ_{k=-K}^{K} β_k · r_{m,t-k} + ε_t``

    L'index ``k > 0`` correspond au marché **passé** (le titre réagit avec
    retard : prix périmés, séances sans échange), ``k < 0`` au marché futur
    (indice lui-même en retard). Les décalages sont faits sur le calendrier
    commun des deux séries **avant** de retirer les NaN, si bien qu'une séance
    manquante ne décale pas les retards.

    Parameters
    ----------
    asset, market
        Rendements du titre et du marché. Deux ``Series`` sont alignées sur
        leur index (jointure interne) ; deux tableaux doivent avoir la même
        longueur.
    lags
        ``K ≥ 0`` ; ``K = 0`` donne le bêta MCO usuel.

    Returns
    -------
    pd.Series
        Coefficients ``β_k`` indexés par ``k = -K..K`` (NaN si moins de
        ``2K + 3`` observations complètes).
    """
    if lags < 0:
        raise ValueError("lags doit être >= 0")
    a = _as_series(asset)
    m = _as_series(market)
    if not isinstance(asset, pd.Series) and not isinstance(market, pd.Series) and len(a) != len(m):
        raise ValueError("asset et market doivent avoir la même longueur")
    df = pd.concat({"a": a, "m": m}, axis=1, join="inner")
    ks = list(range(-lags, lags + 1))
    design = pd.concat({k: df["m"].shift(k) for k in ks}, axis=1)
    ok = design.notna().all(axis=1) & df["a"].notna()
    y = df.loc[ok, "a"].to_numpy(dtype=float)
    X = design.loc[ok].to_numpy(dtype=float)
    index = pd.Index(ks, name="lag")
    if y.size < len(ks) + 2:
        return pd.Series(np.nan, index=index, dtype=float)
    X1 = np.column_stack([np.ones(y.size), X])
    coef, *_ = np.linalg.lstsq(X1, y, rcond=None)
    return pd.Series(coef[1:], index=index, dtype=float)


def dimson_beta(asset: ArrayLike, market: ArrayLike, lags: int = 2) -> float:
    """Bêta de Dimson (1979) : somme des bêtas aux retards ``-K..+K``.

    ``β_Dimson = Σ_{k=-K}^{K} β_k`` (voir :func:`dimson_betas`). Corrige le
    biais vers zéro du bêta MCO des titres peu échangés (Scholes & Williams,
    1977 ; Dimson, 1979), très marqué à la BRVM.
    """
    betas = dimson_betas(asset, market, lags=lags)
    if betas.isna().any():
        return math.nan
    return float(betas.sum())


# ---------------------------------------------------------------------------
# Bootstrap stationnaire
# ---------------------------------------------------------------------------


def stationary_bootstrap(
    returns: ArrayLike | pd.DataFrame,
    stat_fn: Callable[[np.ndarray], Any],
    n_boot: int = 2000,
    mean_block: float = 20,
    seed: int = 0,
) -> np.ndarray:
    """Bootstrap stationnaire (Politis & Romano, 1994).

    Rééchantillonne des blocs de longueur aléatoire géométrique de moyenne
    ``b = mean_block`` (probabilité ``p = 1/b`` d'ouvrir un nouveau bloc à
    chaque pas), avec raccord circulaire. Construction de l'indice :

    ``I_1 ~ U{0..n-1}`` ; ``I_{t+1} = U{0..n-1}`` avec proba ``p``, sinon
    ``(I_t + 1) mod n``.

    La série rééchantillonnée est stationnaire et conserve la dépendance
    sérielle jusqu'à l'ordre de ``b`` : c'est ce qui rend les intervalles de
    confiance du Sharpe ou du drawdown honnêtes en présence d'autocorrélation.
    ``mean_block = 1`` redonne le bootstrap i.i.d. d'Efron.

    Parameters
    ----------
    returns
        Série 1-D, ou ``DataFrame``/tableau 2-D (les lignes sont tirées
        ensemble, ce qui préserve la dépendance entre colonnes, p. ex.
        stratégie et indice). Les lignes contenant un NaN sont retirées.
    stat_fn
        Fonction appliquée à chaque échantillon ``np.ndarray`` (1-D ou 2-D) ;
        renvoie un scalaire ou un vecteur de taille fixe.
    n_boot
        Nombre de répliques.
    mean_block
        Longueur moyenne des blocs (``≥ 1``).
    seed
        Graine du générateur ``numpy.random.default_rng`` : résultats
        reproductibles ; les ``k`` premières répliques ne dépendent pas de
        ``n_boot``.

    Returns
    -------
    np.ndarray
        Forme ``(n_boot,)`` ou ``(n_boot, k)``.
    """
    if n_boot < 1:
        raise ValueError("n_boot doit être >= 1")
    if mean_block < 1:
        raise ValueError("mean_block doit être >= 1")
    if isinstance(returns, (pd.DataFrame, pd.Series)):
        data = returns.to_numpy(dtype=float)
    else:
        data = np.asarray(returns, dtype=float)
    if data.ndim not in (1, 2):
        raise ValueError("returns doit être 1-D ou 2-D")
    if np.isinf(data).any():
        raise ValueError("returns contient des valeurs infinies")
    keep = ~np.isnan(data) if data.ndim == 1 else ~np.isnan(data).any(axis=1)
    data = data[keep]
    n = data.shape[0]
    if n < 2:
        raise ValueError("au moins deux observations sont nécessaires")
    p = 1.0 / float(mean_block)
    rng = np.random.default_rng(seed)
    pos = np.arange(n)
    results: list[Any] = []
    for _ in range(n_boot):
        starts = rng.integers(0, n, size=n)
        new_block = rng.random(n) < p
        new_block[0] = True
        last = np.maximum.accumulate(np.where(new_block, pos, 0))
        idx = (starts[last] + (pos - last)) % n
        results.append(np.asarray(stat_fn(data[idx]), dtype=float))
    return np.asarray(results, dtype=float)


# ---------------------------------------------------------------------------
# Probabilité de sur-ajustement (CSCV)
# ---------------------------------------------------------------------------


def _cscv_combinations(n_splits: int, max_combinations: int | None, seed: int) -> np.ndarray:
    """Combinaisons de ``S/2`` blocs parmi ``S`` (toutes, ou un tirage)."""
    half = n_splits // 2
    total = math.comb(n_splits, half)
    if max_combinations is None or total <= max_combinations:
        if total > 1_000_000:
            raise ValueError(f"{total} combinaisons : réduire n_splits ou fixer max_combinations")
        return np.array(list(itertools.combinations(range(n_splits), half)), dtype=int)
    if max_combinations < 1:
        raise ValueError("max_combinations doit être >= 1")
    rng = np.random.default_rng(seed)
    chosen: set[tuple[int, ...]] = set()
    while len(chosen) < max_combinations:
        c = tuple(sorted(int(v) for v in rng.choice(n_splits, size=half, replace=False)))
        chosen.add(c)
    return np.array(sorted(chosen), dtype=int)


def _perf_from_sums(
    cnt: FloatArray,
    s1: FloatArray,
    s2: FloatArray,
    shift: FloatArray,
    metric: str,
    periods_per_year: int,
) -> FloatArray:
    """Moyenne ou Sharpe annualisés à partir de sommes centrées sur ``shift``."""
    with np.errstate(divide="ignore", invalid="ignore"):
        mean_c = s1 / cnt
        mean = mean_c + shift
        if metric == "mean":
            out = mean * periods_per_year
            return np.where(cnt >= 1, out, np.nan)
        var = (s2 - cnt * mean_c**2) / (cnt - 1.0)
        var = np.where(var > 0.0, var, 0.0)
        sd = np.sqrt(var)
        sr = mean / sd * math.sqrt(periods_per_year)
        valid = (cnt >= 2) & (sd > 1e-12 * np.maximum(1.0, np.abs(mean)))
        return np.where(valid, sr, np.nan)


def pbo_cscv(
    perf_matrix: pd.DataFrame,
    n_splits: int = 16,
    metric: str | Callable[[np.ndarray], np.ndarray] = "sharpe",
    periods_per_year: int = TRADING_DAYS,
    max_combinations: int | None = None,
    seed: int = 0,
) -> dict[str, Any]:
    """Probabilité de sur-ajustement du backtest par CSCV.

    Combinatorially Symmetric Cross-Validation de Bailey, Borwein, López de
    Prado & Zhu (2017). Soit ``M`` la matrice ``T × N`` des rendements de
    ``N`` configurations :

    1. ``M`` est découpée en ``S`` blocs chronologiques contigus de même
       taille ``T // S`` (les plus anciennes lignes en surnombre sont
       ignorées) ;
    2. pour chacune des ``C(S, S/2)`` combinaisons ``J`` de ``S/2`` blocs
       (échantillon d'apprentissage, IS) et son complément ``J̄`` (test, OOS),
       on calcule la performance ``R_n`` (IS) et ``R̄_n`` (OOS) de chaque
       configuration ;
    3. ``n* = argmax_n R_n`` est la configuration qu'aurait choisie le
       chercheur ; ``ω̄ = rang(R̄_{n*}) / (N + 1)`` est son rang relatif OOS
       (rang moyen en cas d'égalité, de 1 = pire à N = meilleur) et
       ``λ = ln(ω̄ / (1 - ω̄))`` son logit ;
    4. ``PBO = P(λ ≤ 0)`` = fréquence à laquelle la meilleure configuration
       IS finit sous la médiane OOS.

    La dégradation de performance est mesurée par la régression MCO
    ``R̄_{n*} = a + b·R_{n*}`` (pente ``b`` attendue négative en cas de
    sur-ajustement) et par ``P(R̄_{n*} < 0)``.

    Repères d'interprétation : PBO ≈ 0 pour une configuration réellement
    supérieure ; PBO ≈ 0,5 pour des configurations i.i.d. sans aucun signal ;
    PBO → 1 lorsque la sélection exploite du bruit qui se retourne (p. ex.
    configurations de même performance sur l'échantillon complet : la
    meilleure IS est alors mécaniquement la pire OOS).

    Parameters
    ----------
    perf_matrix
        ``DataFrame`` ``T × N`` de rendements par période (une colonne par
        configuration). Les NaN sont ignorés colonne par colonne.
    n_splits
        Nombre pair ``S`` de blocs (16 par défaut → 12 870 combinaisons).
    metric
        ``"sharpe"`` (Sharpe annualisé, défaut), ``"mean"`` (rendement moyen
        annualisé), ou une fonction ``f(X) -> np.ndarray`` de taille ``N``
        appliquée à un tableau ``(lignes × N)`` (plus lent).
    periods_per_year
        Annualisation des performances rapportées (n'affecte pas les rangs).
    max_combinations
        Si fourni et inférieur à ``C(S, S/2)``, tirage aléatoire (graine
        ``seed``) de ce nombre de combinaisons distinctes.
    seed
        Graine du tirage de combinaisons.

    Returns
    -------
    dict
        ``pbo``, ``logits`` (np.ndarray), ``oos_rank`` (``ω̄``), ``is_perf`` et
        ``oos_perf`` (performances de ``n*``), ``degradation_slope``,
        ``degradation_intercept``, ``degradation_r2``, ``prob_oos_loss``,
        ``selected`` (fréquence de sélection par configuration, ``Series``),
        ``n_combinations``, ``n_splits``, ``block_size``, ``n_configs``.
    """
    frame = perf_matrix if isinstance(perf_matrix, pd.DataFrame) else pd.DataFrame(perf_matrix)
    X = frame.to_numpy(dtype=float)
    if X.ndim != 2:
        raise ValueError("perf_matrix doit être 2-D")
    if np.isinf(X).any():
        raise ValueError("perf_matrix contient des valeurs infinies")
    T, N = X.shape
    if N < 2:
        raise ValueError("au moins deux configurations sont nécessaires")
    if n_splits < 2 or n_splits % 2:
        raise ValueError("n_splits doit être un entier pair >= 2")
    block = T // n_splits
    if block < 2:
        raise ValueError("trop peu d'observations pour n_splits blocs (>= 2 par bloc)")
    X = X[T - n_splits * block :]
    blocks = X.reshape(n_splits, block, N)
    combos = _cscv_combinations(n_splits, max_combinations, seed)
    C = combos.shape[0]
    member = np.zeros((C, n_splits), dtype=float)
    member[np.arange(C)[:, None], combos] = 1.0
    complement = 1.0 - member

    if isinstance(metric, str):
        key = metric.lower()
        if key not in ("sharpe", "mean"):
            raise ValueError(f"métrique inconnue : {metric!r}")
        mask = ~np.isnan(blocks)
        with np.errstate(invalid="ignore"):
            col_cnt = mask.reshape(-1, N).sum(axis=0)
            shift = np.where(col_cnt > 0, np.nansum(X, axis=0) / np.maximum(col_cnt, 1), 0.0)
        centred = np.where(mask, blocks - shift, 0.0)
        cnt = mask.sum(axis=1).astype(float)
        s1 = centred.sum(axis=1)
        s2 = (centred * centred).sum(axis=1)
        is_all = _perf_from_sums(
            member @ cnt, member @ s1, member @ s2, shift, key, periods_per_year
        )
        oos_all = _perf_from_sums(
            complement @ cnt, complement @ s1, complement @ s2, shift, key, periods_per_year
        )
        metric_name = key
    elif callable(metric):
        is_all = np.empty((C, N))
        oos_all = np.empty((C, N))
        all_blocks = np.arange(n_splits)
        for c in range(C):
            train = blocks[combos[c]].reshape(-1, N)
            test_ids = np.setdiff1d(all_blocks, combos[c], assume_unique=True)
            test = blocks[test_ids].reshape(-1, N)
            is_all[c] = np.asarray(metric(train), dtype=float)
            oos_all[c] = np.asarray(metric(test), dtype=float)
        metric_name = getattr(metric, "__name__", "callable")
    else:
        raise TypeError("metric doit être une chaîne ou une fonction")

    valid = np.isfinite(is_all).any(axis=1)
    train_score = np.where(np.isfinite(is_all), is_all, -np.inf)
    n_star = np.argmax(train_score, axis=1)
    rows = np.arange(C)
    oos_score = np.where(np.isfinite(oos_all), oos_all, -np.inf)
    chosen_oos = oos_score[rows, n_star]
    less = (oos_score < chosen_oos[:, None]).sum(axis=1)
    equal = (oos_score == chosen_oos[:, None]).sum(axis=1)
    rank = less + (equal + 1.0) / 2.0
    omega = rank / (N + 1.0)
    logits = np.log(omega / (1.0 - omega))
    logits = np.where(valid, logits, np.nan)

    is_perf = np.where(valid, is_all[rows, n_star], np.nan)
    oos_perf = np.where(valid, oos_all[rows, n_star], np.nan)
    finite_logits = logits[np.isfinite(logits)]
    pbo = float(np.mean(finite_logits <= 0.0)) if finite_logits.size else math.nan

    pair = np.isfinite(is_perf) & np.isfinite(oos_perf)
    slope = intercept = r2 = math.nan
    if pair.sum() >= 3 and np.ptp(is_perf[pair]) > 0:
        xs, ys = is_perf[pair], oos_perf[pair]
        slope, intercept = (float(v) for v in np.polyfit(xs, ys, 1))
        resid = ys - (intercept + slope * xs)
        sst = float(np.sum((ys - ys.mean()) ** 2))
        r2 = 1.0 - float(np.sum(resid**2)) / sst if sst > 0 else math.nan
    prob_loss = float(np.mean(oos_perf[pair] < 0.0)) if pair.any() else math.nan

    counts = np.bincount(n_star[valid], minlength=N).astype(float)
    selected = pd.Series(counts / max(valid.sum(), 1), index=frame.columns, name="selection_freq")
    selected = selected.sort_values(ascending=False)

    return {
        "pbo": pbo,
        "logits": logits,
        "oos_rank": np.where(valid, omega, np.nan),
        "is_perf": is_perf,
        "oos_perf": oos_perf,
        "degradation_slope": slope,
        "degradation_intercept": intercept,
        "degradation_r2": r2,
        "prob_oos_loss": prob_loss,
        "selected": selected,
        "n_combinations": int(C),
        "n_splits": int(n_splits),
        "block_size": int(block),
        "n_configs": int(N),
        "metric": metric_name,
    }


# ---------------------------------------------------------------------------
# Drawdowns
# ---------------------------------------------------------------------------


def rolling_drawdown(returns: ArrayLike, window: int | None = None) -> pd.Series:
    """Série des drawdowns (perte depuis le plus haut).

    ``W_t = Π_{s≤t} (1 + r_s)`` (capital initial 1) et
    ``DD_t = W_t / P_t - 1`` avec ``P_t`` le plus haut :

    * ``window=None`` : plus haut historique ``P_t = max(1, max_{s≤t} W_s)`` ;
    * ``window=w`` : plus haut des ``w`` dernières valeurs de ``W`` (séance
      courante incluse, capital initial inclus au début), utile pour suivre
      un drawdown « récent ».

    Les NaN sont traités comme un rendement nul (capital inchangé) et l'index
    d'origine est conservé. Valeurs ``≤ 0``.
    """
    s = _as_series(returns)
    r = s.fillna(0.0).to_numpy(dtype=float)
    if window is None:
        dd = _drawdown_array(r)
    else:
        if window < 1:
            raise ValueError("window doit être >= 1")
        wealth = np.concatenate(([1.0], np.cumprod(1.0 + r)))
        peak = pd.Series(wealth).rolling(int(window), min_periods=1).max().to_numpy()
        dd = wealth[1:] / peak[1:] - 1.0
    return pd.Series(dd, index=s.index, name="drawdown")


def rolling_max_drawdown(returns: ArrayLike, window: int = TRADING_DAYS) -> pd.Series:
    """Pire drawdown à l'intérieur de chaque fenêtre glissante de ``window`` séances.

    Pour la fenêtre se terminant en ``t`` (rendements ``r_{t-w+1..t}``, chemin
    de capital remis à 1 au début de la fenêtre) :
    ``MDD_t = min_{j} (W_j / max_{i≤j} W_i - 1)``. Les ``w - 1`` premières
    valeurs sont NaN. NaN de rendement traités comme 0.
    """
    if window < 1:
        raise ValueError("window doit être >= 1")
    s = _as_series(returns)
    r = s.fillna(0.0).to_numpy(dtype=float)
    n = r.size
    out = np.full(n, np.nan)
    if n >= window:
        wealth = np.concatenate(([1.0], np.cumprod(1.0 + r)))
        win = np.lib.stride_tricks.sliding_window_view(wealth, window + 1)
        peak = np.maximum.accumulate(win, axis=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            dd = np.where(peak > 0, win / peak - 1.0, -1.0)
        out[window - 1 :] = dd.min(axis=1)
    return pd.Series(out, index=s.index, name="max_drawdown")


def drawdown_episodes(returns: ArrayLike, top: int | None = None) -> pd.DataFrame:
    """Table des épisodes de drawdown, du plus profond au moins profond.

    Colonnes : ``peak`` (dernière date au plus haut ; manquant — ``NaT`` pour
    un index de dates — si l'épisode commence dès la première séance, le plus
    haut étant alors le capital initial), ``start`` (première séance sous
    l'eau), ``trough`` (creux), ``recovery`` (première séance revenue au plus
    haut ; manquant si non récupéré), ``depth`` (≤ 0), ``length`` (séances
    sous l'eau), ``to_trough`` (séances jusqu'au creux inclus),
    ``recovered``. NaN de rendement traités comme 0.
    """
    s = _as_series(returns)
    r = s.fillna(0.0).to_numpy(dtype=float)
    table = _episodes_from_dd(_drawdown_array(r), s.index)
    table = table.sort_values("depth", kind="mergesort").reset_index(drop=True)
    if top is not None:
        table = table.head(int(top))
    return table


# ---------------------------------------------------------------------------
# Coefficient d'information
# ---------------------------------------------------------------------------


def ic_summary(
    ic: ArrayLike,
    horizon: int = 1,
    lags: int | None = None,
) -> dict[str, float]:
    """Synthèse d'une série de coefficients d'information (IC).

    Pour une série ``IC_t`` (corrélation transversale signal / rendement futur,
    voir ``scoring.information_coefficient``) :

    * ``mean``, ``median``, ``std`` ; ``ir = mean / std`` (IR de l'IC,
      Grinold & Kahn, 2000) ;
    * ``t_stat_nw`` : t de Newey-West de la moyenne (:func:`newey_west_tstat`)
      et sa p-valeur bilatérale normale ``p_value_nw`` ;
    * ``t_stat_naive = mean / (std / sqrt(n))`` (à titre de comparaison) ;
    * ``hit_rate`` : part des dates où ``IC > 0``.

    Si les rendements futurs se chevauchent (horizon ``h > 1`` évalué chaque
    séance), les IC suivent un MA(h-1) ; par défaut
    ``lags = max(L_NW(n), 2h)`` lorsque ``h > 1`` (le noyau de Bartlett
    pondère alors à ≈ 83 % la variance de long terme d'un MA(h-1) à poids
    égaux, contre ≈ 67 % avec ``h - 1`` retards).

    Parameters
    ----------
    ic
        Série d'IC (NaN ignorés : dates sans assez de titres échangés).
    horizon
        Horizon ``h`` des rendements futurs, en séances.
    lags
        Retards de Newey-West imposés (prioritaires sur la règle ci-dessus).
    """
    if horizon < 1:
        raise ValueError("horizon doit être >= 1")
    x = _clean(ic)
    n = int(x.size)
    nan_out = {
        "n_obs": float(n),
        "mean": math.nan,
        "median": math.nan,
        "std": math.nan,
        "ir": math.nan,
        "t_stat_nw": math.nan,
        "p_value_nw": math.nan,
        "t_stat_naive": math.nan,
        "hit_rate": math.nan,
        "nw_lags": math.nan,
    }
    if n < 2:
        if n == 1:
            nan_out.update(mean=float(x[0]), median=float(x[0]), hit_rate=float(x[0] > 0))
        return nan_out
    if lags is None:
        L = newey_west_lags(n)
        if horizon > 1:
            L = max(L, 2 * horizon)
        L = min(L, n - 1)
    else:
        L = min(int(lags), n - 1)
    mean = float(x.mean())
    sd = float(x.std(ddof=1))
    t_nw = newey_west_tstat(x, lags=L)
    return {
        "n_obs": float(n),
        "mean": mean,
        "median": float(np.median(x)),
        "std": sd,
        "ir": mean / sd if sd > 0 else math.nan,
        "t_stat_nw": t_nw,
        "p_value_nw": float(2.0 * sps.norm.sf(abs(t_nw))) if math.isfinite(t_nw) else math.nan,
        "t_stat_naive": mean / (sd / math.sqrt(n)) if sd > 0 else math.nan,
        "hit_rate": float(np.mean(x > 0)),
        "nw_lags": float(L),
    }


# ---------------------------------------------------------------------------
# Synthèse de performance
# ---------------------------------------------------------------------------


def _summary_keys(var_tag: str, with_benchmark: bool) -> list[str]:
    keys = [
        "n_obs",
        "start",
        "end",
        "total_return",
        "cagr",
        "ann_return",
        "vol",
        "sharpe",
        "sortino",
        "max_drawdown",
        "max_drawdown_duration",
        "max_drawdown_peak",
        "max_drawdown_trough",
        "max_drawdown_recovery",
        "longest_drawdown_duration",
        "calmar",
        "hit_rate",
        "best",
        "worst",
        "avg_gain",
        "avg_loss",
        "profit_factor",
        "skew",
        "kurtosis",
        f"var_{var_tag}",
        f"cvar_{var_tag}",
        "psr",
        "sharpe_lo",
    ]
    if with_benchmark:
        keys += [
            "n_obs_common",
            "beta",
            "alpha",
            "beta_dimson",
            "correlation",
            "tracking_error",
            "information_ratio",
            "benchmark_cagr",
            "excess_cagr",
            "up_capture",
            "down_capture",
        ]
    return keys


def _cagr(r: FloatArray, periods_per_year: int) -> float:
    """``CAGR = (Π(1 + r))^(P/n) - 1`` ; -1 si le capital est anéanti."""
    if r.size == 0:
        return math.nan
    wealth = float(np.prod(1.0 + r))
    if wealth <= 0.0:
        return -1.0
    return wealth ** (periods_per_year / r.size) - 1.0


def perf_summary(
    returns: pd.Series,
    benchmark: pd.Series | None = None,
    rf: float = 0.0,
    periods_per_year: int = TRADING_DAYS,
    var_level: float = 0.95,
    dimson_lags: int = 2,
    lo_lags: int = 5,
) -> dict[str, Any]:
    """Tableau de bord de performance d'une série de rendements.

    Notations : ``r_t`` rendements simples, ``n`` observations non NaN,
    ``P = periods_per_year``, ``rf_p = (1 + rf)^(1/P) - 1`` le taux sans
    risque par période, ``e_t = r_t - rf_p``, ``W_t = Π(1 + r_s)``.

    Mesures absolues
        * ``total_return = W_n - 1`` ; ``cagr = W_n^(P/n) - 1`` ;
          ``ann_return = P·mean(r)`` (arithmétique) ;
        * ``vol = sqrt(P)·std(r)`` (``ddof=1``) ;
        * ``sharpe = sqrt(P)·mean(e)/std(e)`` (Sharpe, 1994) ;
        * ``sortino = P·mean(e) / (sqrt(P)·DD)`` avec la semi-déviation
          ``DD = sqrt(mean(min(e, 0)²))`` (Sortino & Price, 1994) ;
        * ``max_drawdown = min_t (W_t / max(1, max_{s≤t} W_s) - 1)`` (≤ 0),
          ``max_drawdown_duration`` = séances sous l'eau de l'épisode le plus
          profond (jusqu'à récupération ou fin de série), dates de plus haut,
          creux et récupération, ``longest_drawdown_duration`` = plus long
          épisode sous l'eau ;
        * ``calmar = cagr / |max_drawdown|`` (Young, 1991) ;
        * ``hit_rate = P(r > 0)`` ; ``best``, ``worst`` ; ``avg_gain`` et
          ``avg_loss`` (moyennes des rendements > 0 et < 0) ;
          ``profit_factor = Σ r⁺ / |Σ r⁻|`` ;
        * ``skew`` et ``kurtosis`` (kurtosis **en excès**, normale = 0 ;
          estimateurs biaisés) ;
        * ``var_95`` = quantile empirique à ``1 - var_level`` (VaR historique,
          exprimée comme un rendement, négatif en cas de perte) et
          ``cvar_95 = mean(r | r ≤ VaR)`` (expected shortfall) ; le suffixe
          suit ``var_level`` ;
        * ``psr`` = :func:`probabilistic_sharpe` de ``e`` contre 0 ;
          ``sharpe_lo`` = :func:`lo_adjusted_sharpe` de ``e`` (``q = lo_lags``).

    Mesures relatives (si ``benchmark`` est fourni, sur les dates communes)
        * ``beta = cov(r, b)/var(b)`` ; ``alpha = P·(mean(e) - β·mean(b - rf_p))``
          (alpha de Jensen, arithmétique annualisé) ; ``beta_dimson`` (retards
          ``±dimson_lags``, :func:`dimson_beta`) ; ``correlation`` ;
        * ``tracking_error = sqrt(P)·std(r - b)`` ;
          ``information_ratio = P·mean(r - b) / tracking_error`` ;
        * ``benchmark_cagr`` et ``excess_cagr = cagr_stratégie - cagr_indice``
          (période commune) ;
        * ``up_capture = mean(r | b > 0)/mean(b | b > 0)`` et
          ``down_capture = mean(r | b < 0)/mean(b | b < 0)``.

    Parameters
    ----------
    returns
        Rendements simples de la stratégie ; NaN ignorés.
    benchmark
        Rendements de l'indice de référence (p. ex. BRVM Composite), alignés
        sur l'index.
    rf
        Taux sans risque **annuel**.
    periods_per_year
        Nombre de périodes par an.
    var_level
        Niveau de confiance de la VaR/CVaR historiques.
    dimson_lags, lo_lags
        Paramètres de :func:`dimson_beta` et :func:`lo_adjusted_sharpe`.

    Returns
    -------
    dict
        Valeurs ``float`` (NaN si non calculable), entiers pour les durées,
        étiquettes d'index (dates) ou ``None`` pour les dates.
    """
    if not 0.0 < var_level < 1.0:
        raise ValueError("var_level doit être dans ]0, 1[")
    P = int(periods_per_year)
    var_tag = f"{var_level * 100:g}".replace(".", "_")
    s = _as_series(returns).dropna()
    out: dict[str, Any] = dict.fromkeys(_summary_keys(var_tag, benchmark is not None), math.nan)
    n = len(s)
    out["n_obs"] = n
    for key in (
        "start",
        "end",
        "max_drawdown_peak",
        "max_drawdown_trough",
        "max_drawdown_recovery",
    ):
        out[key] = None
    if n == 0:
        return out
    r = s.to_numpy(dtype=float)
    out["start"], out["end"] = s.index[0], s.index[-1]
    rf_p = (1.0 + rf) ** (1.0 / P) - 1.0
    e = r - rf_p

    out["total_return"] = float(np.prod(1.0 + r) - 1.0)
    out["cagr"] = _cagr(r, P)
    out["ann_return"] = float(np.mean(r) * P)
    out["best"] = float(r.max())
    out["worst"] = float(r.min())
    out["hit_rate"] = float(np.mean(r > 0))
    gains, losses = r[r > 0], r[r < 0]
    out["avg_gain"] = float(gains.mean()) if gains.size else math.nan
    out["avg_loss"] = float(losses.mean()) if losses.size else math.nan
    out["profit_factor"] = float(gains.sum() / -losses.sum()) if losses.size else math.nan

    dd = _drawdown_array(r)
    episodes = _episodes_from_dd(dd, s.index)
    out["max_drawdown"] = float(min(dd.min(), 0.0))
    if len(episodes):
        worst = episodes.loc[episodes["depth"].idxmin()]
        out["max_drawdown_duration"] = int(worst["length"])
        for key, col in (("peak", "peak"), ("trough", "trough"), ("recovery", "recovery")):
            value = worst[col]
            out[f"max_drawdown_{key}"] = None if pd.isna(value) else value
        out["longest_drawdown_duration"] = int(episodes["length"].max())
    else:
        out["max_drawdown_duration"] = 0
        out["longest_drawdown_duration"] = 0
    if out["max_drawdown"] < 0:
        out["calmar"] = out["cagr"] / abs(out["max_drawdown"])

    q = float(np.quantile(r, 1.0 - var_level))
    out[f"var_{var_tag}"] = q
    out[f"cvar_{var_tag}"] = float(r[r <= q].mean())

    if n >= 2:
        sd = float(np.std(r, ddof=1))
        out["vol"] = sd * math.sqrt(P)
        sr_p, skew, kurt, _ = _sr_moments(e)
        out["sharpe"] = sr_p * math.sqrt(P) if not math.isnan(sr_p) else math.nan
        downside = math.sqrt(float(np.mean(np.minimum(e, 0.0) ** 2)))
        if downside > 0:
            out["sortino"] = float(np.mean(e)) * P / (downside * math.sqrt(P))
        if sd > 0:
            out["skew"] = skew
            out["kurtosis"] = kurt - 3.0
        out["psr"] = probabilistic_sharpe(e, 0.0)
        out["sharpe_lo"] = lo_adjusted_sharpe(e, q=lo_lags, periods_per_year=P)

    if benchmark is not None:
        b_series = _as_series(benchmark)
        both_unindexed = not isinstance(benchmark, pd.Series) and not isinstance(returns, pd.Series)
        if both_unindexed and len(b_series) != len(_as_series(returns)):
            raise ValueError("returns et benchmark doivent avoir la même longueur")
        joint = pd.concat({"r": s, "b": b_series}, axis=1, join="inner").dropna()
        m = len(joint)
        out["n_obs_common"] = m
        if m >= 2:
            ra = joint["r"].to_numpy(dtype=float)
            ba = joint["b"].to_numpy(dtype=float)
            var_b = float(np.var(ba, ddof=1))
            if var_b > 0:
                beta = float(np.cov(ra, ba, ddof=1)[0, 1] / var_b)
                out["beta"] = beta
                out["alpha"] = float((np.mean(ra - rf_p) - beta * np.mean(ba - rf_p)) * P)
                sd_r = float(np.std(ra, ddof=1))
                if sd_r > 0:
                    out["correlation"] = float(np.corrcoef(ra, ba)[0, 1])
            active = ra - ba
            te = float(np.std(active, ddof=1)) * math.sqrt(P)
            out["tracking_error"] = te
            if te > 0:
                out["information_ratio"] = float(np.mean(active)) * P / te
            out["benchmark_cagr"] = _cagr(ba, P)
            out["excess_cagr"] = _cagr(ra, P) - out["benchmark_cagr"]
            up, down = ba > 0, ba < 0
            if up.any():
                out["up_capture"] = float(ra[up].mean() / ba[up].mean())
            if down.any():
                out["down_capture"] = float(ra[down].mean() / ba[down].mean())
            # Décalages sur le calendrier commun complet (NaN conservés) : une
            # séance manquante ne doit pas faire glisser les retards.
            out["beta_dimson"] = dimson_beta(_as_series(returns), b_series, lags=dimson_lags)
    return out
