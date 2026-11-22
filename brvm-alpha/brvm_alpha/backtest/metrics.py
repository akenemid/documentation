"""Mesures hebdomadaires de validation (spécification §8.2, revue 04 §2, §4, §7, §12, §13).

Toutes les métriques de portefeuille de la validation sont calculées sur des
rendements **hebdomadaires W-FRI**, **nets de coûts**, contre le BRVM
Composite Total Return (reconstruit avant le 02/01/2025). La fréquence
hebdomadaire atténue les prix périmés de la BRVM (autocorrélation des
rendements quotidiens) ; l'annualisation suit la convention de 52 semaines.

Contenu
-------
* :func:`weekly_returns` : composition des rendements quotidiens en semaines
  W-FRI, avec exclusion des fenêtres sans BOC (2021) ;
* :func:`sharpe_triplet` : trois Sharpe (naïf, Lo avec ``q = 4`` en
  hebdomadaire, GLM) et le signal de divergence de plus de 25 % ;
* :func:`glm_smoothing`, :func:`glm_sharpe` : modèle de lissage de
  Getmansky, Lo & Makarov (2004) ;
* :func:`psr`, :func:`dsr` : Sharpe probabiliste et dégonflé (Bailey & López
  de Prado, 2012, 2014), ``N`` = nombre d'essais du registre ;
* :func:`bootstrap_ci` : intervalle du bootstrap stationnaire (Politis &
  Romano, 1994), ``n_boot = 5 000``, blocs moyens de 8 semaines ;
* :func:`cvar`, :func:`cvar_bootstrap`, :func:`cvar_ratio` : CVaR 95 % à
  5 séances (une semaine) par bootstrap stationnaire, jamais sur des
  scénarios quotidiens (tronqués à ±7,5 %) ;
* :func:`annualized_active_return`, :func:`information_ratio`,
  :func:`max_drawdown`, :func:`relative_drawdown` ; :func:`family_pbo`
  (PBO par CSCV, 10 blocs hebdomadaires, critère = Sharpe de Lo des
  rendements actifs nets).

Ces mesures **estiment** des grandeurs incertaines à partir d'un historique
court : elles ne garantissent aucun gain futur.

Références
----------
* Bailey, D. H. & López de Prado, M. (2012, 2014), PSR / DSR.
* Bailey, D. H., Borwein, J., López de Prado, M. & Zhu, Q. J. (2017). The
  Probability of Backtest Overfitting. *Journal of Computational Finance*.
* Getmansky, M., Lo, A. W. & Makarov, I. (2004). An Econometric Model of
  Serial Correlation and Illiquidity in Hedge Fund Returns. *Journal of
  Financial Economics*, 74(3), 529-609.
* Lo, A. W. (2002). The Statistics of Sharpe Ratios. *Financial Analysts
  Journal*, 58(4), 36-52.
* Politis, D. N. & Romano, J. P. (1994). The Stationary Bootstrap. *JASA*.
* Rockafellar, R. T. & Uryasev, S. (2000). Optimization of Conditional
  Value-at-Risk. *Journal of Risk*, 2(3).
"""

from __future__ import annotations

import math
import warnings
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from brvm_alpha.quant import stats

__all__ = [
    "EXCLUDE_STATS_WINDOWS",
    "GLMSmoothing",
    "N_BOOT",
    "S0",
    "S1",
    "S1_SUBPERIODS",
    "S2_FROM",
    "WEEKLY_FREQ",
    "WEEKLY_MEAN_BLOCK",
    "WEEKS_PER_YEAR",
    "annualized_active_return",
    "annualized_return",
    "active_returns",
    "bootstrap_ci",
    "cvar",
    "cvar_bootstrap",
    "cvar_ratio",
    "dsr",
    "family_pbo",
    "glm_sharpe",
    "glm_smoothing",
    "information_ratio",
    "lo_sharpe",
    "max_drawdown",
    "naive_sharpe",
    "overlaps_s1",
    "psr",
    "relative_drawdown",
    "sharpe_triplet",
    "weekly_returns",
]

#: Fréquence d'évaluation (spéc. §8.2) et annualisation conventionnelle.
WEEKLY_FREQ = "W-FRI"
WEEKS_PER_YEAR = 52
#: Bootstrap stationnaire (spéc. §8.2) : 5 000 répliques (à passer
#: explicitement : le défaut de ``stats.stationary_bootstrap`` est 2 000),
#: blocs moyens de 8 semaines.
N_BOOT = 5000
WEEKLY_MEAN_BLOCK = 8
#: Fenêtres exclues des statistiques (trou de BOC de 2021, spéc. §3.1 et §8.1).
EXCLUDE_STATS_WINDOWS: tuple[tuple[str, str], ...] = (("2021-05-06", "2021-06-25"),)
#: Échantillons de la spécification §8.1.
S0 = ("2022-11-17", "2026-11-20")  # sélection, contaminé : diagnostic seulement
S1 = ("2017-01-02", "2022-11-16")  # validation pré-enregistrée : un seul test, fait plus tard
S1_SUBPERIODS: tuple[tuple[str, str], tuple[str, str]] = (("2017-01-02", "2019-12-31"), ("2020-01-01", "2022-11-16"))
S2_FROM = "2026-12-01"  # suivi réel


def overlaps_s1(start: Any, end: Any) -> bool:
    """Vrai si ``[start, end]`` recoupe l'échantillon vierge S1 (2017-01-02 → 2022-11-16).

    Garde-fou à appeler avant tout calcul de performance : S1 est réservé à
    **un seul** test de validation pré-enregistré (spéc. §8.1).
    """
    a = pd.Timestamp(start) if start is not None else pd.Timestamp.min
    b = pd.Timestamp(end) if end is not None else pd.Timestamp.max
    return bool(a <= pd.Timestamp(S1[1]) and b >= pd.Timestamp(S1[0]))


# ---------------------------------------------------------------------------
# Rendements hebdomadaires
# ---------------------------------------------------------------------------


def _as_series(x: Any, name: str = "returns") -> pd.Series:
    if isinstance(x, pd.DataFrame):
        if x.shape[1] != 1:
            raise ValueError(f"{name} : une seule colonne attendue")
        x = x.iloc[:, 0]
    if not isinstance(x, pd.Series):
        x = pd.Series(np.asarray(x, dtype=float))
    s = x.astype(float)
    if np.isinf(s.to_numpy()).any():
        raise ValueError(f"{name} : valeurs infinies")
    return s


def weekly_returns(
    daily: pd.Series | pd.DataFrame,
    *,
    freq: str = WEEKLY_FREQ,
    exclude_windows: Sequence[tuple[Any, Any]] | None = None,
    min_days: int = 1,
) -> pd.Series | pd.DataFrame:
    """Rendements hebdomadaires composés : ``R_w = Π_{t ∈ w} (1 + r_t) − 1``.

    Les semaines se terminent le vendredi (``W-FRI`` ; étiquette = vendredi
    de la semaine). Une semaine sans aucune observation est absente (jamais
    un rendement nul inventé). Les NaN quotidiens sont ignorés ; une semaine
    avec moins de ``min_days`` observations est retirée.

    Parameters
    ----------
    daily
        Rendements simples quotidiens (``Series`` ou ``DataFrame`` date ×
        colonnes), indexés par séance.
    exclude_windows
        Fenêtres ``(début, fin)`` dont les semaines qui les **recoupent** sont
        retirées (p. ex. :data:`EXCLUDE_STATS_WINDOWS`, trou de 2021).
    min_days
        Nombre minimal de séances observées dans la semaine.
    """
    frame = daily.to_frame() if isinstance(daily, pd.Series) else daily
    if not isinstance(frame.index, pd.DatetimeIndex):
        frame = frame.set_axis(pd.DatetimeIndex(pd.to_datetime(frame.index)), axis=0)
    frame = frame.sort_index().astype(float)
    if np.isinf(frame.to_numpy()).any():
        raise ValueError("rendements quotidiens infinis")
    periods = frame.index.to_period(freq)
    grp = frame.groupby(periods)
    growth = (1.0 + frame).where(frame.notna()).groupby(periods).prod(min_count=1) - 1.0
    counts = grp.count()
    growth = growth.where(counts >= int(min_days))
    out = growth.set_axis(pd.DatetimeIndex(growth.index.end_time.normalize()), axis=0)
    out.index.name = "week"
    if exclude_windows:
        week_start = pd.DatetimeIndex(growth.index.start_time.normalize())
        week_end = out.index
        drop = np.zeros(len(out), dtype=bool)
        for a, b in exclude_windows:
            a_ts, b_ts = pd.Timestamp(a), pd.Timestamp(b)
            drop |= (week_start <= b_ts) & (week_end >= a_ts)
        out = out.loc[~drop]
    if isinstance(daily, pd.Series):
        res = out.iloc[:, 0].dropna()
        res.name = daily.name
        return res
    return out.dropna(how="all")


def active_returns(strategy: pd.Series, benchmark: pd.Series) -> pd.Series:
    """Rendements actifs ``a_w = r_w − b_w`` sur les semaines communes (jointure interne)."""
    s, b = _as_series(strategy, "strategy"), _as_series(benchmark, "benchmark")
    both = pd.concat({"s": s, "b": b}, axis=1, join="inner").dropna()
    return (both["s"] - both["b"]).rename("active")


# ---------------------------------------------------------------------------
# Sharpe : naïf, Lo, GLM
# ---------------------------------------------------------------------------


def naive_sharpe(returns: Any, periods_per_year: int = WEEKS_PER_YEAR) -> float:
    """Sharpe naïf annualisé ``√P · moyenne / écart-type`` (``ddof = 1``)."""
    return float(stats.sharpe_ratio(_as_series(returns), rf=0.0, periods_per_year=periods_per_year))


def lo_sharpe(returns: Any, q: int = 4, periods_per_year: int = WEEKS_PER_YEAR) -> float:
    """Sharpe de Lo (2002) : autocorrélations tronquées à ``q`` (4 en hebdomadaire, spéc. §8.2)."""
    return float(stats.lo_adjusted_sharpe(_as_series(returns), q=q, periods_per_year=periods_per_year))


@dataclass(frozen=True)
class GLMSmoothing:
    """Estimation du lissage de Getmansky, Lo & Makarov (2004).

    ``R°_t = Σ_{j=0}^{k} θ_j R_{t−j}``, ``θ_j ∈ [0, 1]``, ``Σ θ_j = 1``, avec
    ``R`` les « vrais » rendements i.i.d. Alors ``Var(R°) = ξ·σ²`` avec
    ``ξ = Σ θ_j²`` et le Sharpe corrigé vaut ``√P · SR° · √ξ``.
    """

    theta: np.ndarray
    xi: float
    k: int
    method: str
    converged: bool
    n_obs: int

    @property
    def smoothing_index(self) -> float:
        """Indice de lissage ``ξ = Σ θ_j²`` (1 = aucun lissage)."""
        return self.xi


def _css_objective(z: np.ndarray, x: np.ndarray) -> float:
    """Somme des carrés conditionnelle d'un MA(k) ``x_t − μ = e_t + Σ ψ_j e_{t−j}``."""
    mu, psi = z[0], z[1:]
    k = psi.size
    e = np.zeros(x.size + k)
    for t in range(x.size):
        e[t + k] = (x[t] - mu) - float(psi @ e[t : t + k][::-1])
    return float(e[k:] @ e[k:])


def glm_smoothing(returns: Any, k: int = 2, method: str = "mle") -> GLMSmoothing:
    """Estime les coefficients de lissage ``θ_0..θ_k`` de GLM (2004).

    Méthode : maximum de vraisemblance gaussienne **exacte** d'un MA(k)
    ``x_t = μ + η_t + Σ ψ_j η_{t−j}`` (filtre de Kalman de ``statsmodels``),
    sous les bornes ``0 ≤ ψ_j ≤ 0,99`` (qui équivalent à ``θ_j ∈ [0, 1]`` et
    garantissent l'inversibilité pour ``k ≤ 2``), puis normalisation
    ``θ_0 = 1 / (1 + Σ ψ)``, ``θ_j = ψ_j θ_0``. ``method="css"`` (ou un échec
    de ``statsmodels``) utilise la somme des carrés conditionnelle.

    Parameters
    ----------
    returns
        Rendements (hebdomadaires de préférence) ; NaN ignorés.
    k
        Ordre du lissage (2 dans GLM).
    """
    from scipy.optimize import minimize

    if k < 1:
        raise ValueError("k doit être >= 1")
    if method not in ("mle", "css"):
        raise ValueError("method doit valoir 'mle' ou 'css'")
    x = _as_series(returns).dropna().to_numpy(dtype=float)
    n = int(x.size)
    if n < 4 * (k + 2):
        raise ValueError("historique trop court pour estimer le lissage GLM")
    bounds = [(None, None)] + [(0.0, 0.99)] * k
    z0 = np.r_[x.mean(), np.full(k, 0.05)]
    used = method
    psi = None
    converged = False
    if method == "mle":
        try:
            from statsmodels.tsa.arima.model import ARIMA

            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                model = ARIMA(x, order=(0, 0, k), trend="c", enforce_invertibility=False, enforce_stationarity=False)

                def nll(z: np.ndarray) -> float:
                    val = -float(model.loglike(np.r_[z[0], z[1 : k + 1], math.exp(z[-1])]))
                    return val if math.isfinite(val) else 1e300

                opt = minimize(
                    nll,
                    np.r_[z0, math.log(max(float(x.var()), 1e-12))],
                    method="L-BFGS-B",
                    bounds=bounds + [(None, None)],
                )
            psi = np.clip(opt.x[1 : k + 1], 0.0, 0.99)
            converged = bool(opt.success)
        except Exception:  # pragma: no cover - dépend de statsmodels
            psi = None
            used = "css"
    if psi is None:
        opt = minimize(_css_objective, z0, args=(x,), method="L-BFGS-B", bounds=bounds)
        psi = np.clip(opt.x[1:], 0.0, 0.99)
        converged = bool(opt.success)
    theta = np.r_[1.0, psi] / (1.0 + float(psi.sum()))
    return GLMSmoothing(theta=theta, xi=float(theta @ theta), k=int(k), method=used, converged=converged, n_obs=n)


def glm_sharpe(
    returns: Any,
    k: int = 2,
    periods_per_year: int = WEEKS_PER_YEAR,
    smoothing: GLMSmoothing | None = None,
) -> float:
    """Sharpe annualisé corrigé du lissage GLM : ``√P · (moyenne / écart-type) · √ξ``."""
    x = _as_series(returns).dropna()
    sm = glm_smoothing(x, k=k) if smoothing is None else smoothing
    sd = float(x.std(ddof=1))
    if not sd > 0:
        return math.nan
    return float(math.sqrt(periods_per_year) * float(x.mean()) / sd * math.sqrt(sm.xi))


def sharpe_triplet(
    returns: Any,
    *,
    periods_per_year: int = WEEKS_PER_YEAR,
    lo_q: int = 4,
    glm_k: int = 2,
    divergence_threshold: float = 0.25,
) -> dict[str, Any]:
    """Les trois Sharpe exigés par la spécification §8.2 (toujours rapportés ensemble).

    Returns
    -------
    dict
        ``naive``, ``lo`` (q = ``lo_q``), ``glm`` (k = ``glm_k``), ``glm_theta``,
        ``glm_xi``, ``lo_glm_gap`` = ``|SR_Lo − SR_GLM| / |SR_Lo|`` et
        ``divergence`` (vrai si l'écart dépasse 25 % : à signaler), ``n_obs``.
    """
    x = _as_series(returns).dropna()
    naive = naive_sharpe(x, periods_per_year)
    lo = lo_sharpe(x, q=lo_q, periods_per_year=periods_per_year)
    try:
        sm = glm_smoothing(x, k=glm_k)
        glm = glm_sharpe(x, k=glm_k, periods_per_year=periods_per_year, smoothing=sm)
        theta, xi = sm.theta, sm.xi
    except ValueError:
        glm, theta, xi = math.nan, np.full(glm_k + 1, np.nan), math.nan
    gap = abs(lo - glm) / abs(lo) if math.isfinite(lo) and math.isfinite(glm) and lo != 0 else math.nan
    return {
        "naive": naive,
        "lo": lo,
        "glm": glm,
        "glm_theta": theta,
        "glm_xi": xi,
        "lo_q": int(lo_q),
        "lo_glm_gap": gap,
        "divergence": bool(math.isfinite(gap) and gap > divergence_threshold),
        "n_obs": int(x.size),
    }


# ---------------------------------------------------------------------------
# PSR / DSR
# ---------------------------------------------------------------------------


def psr(returns: Any, sr_benchmark: float = 0.0) -> float:
    """Sharpe probabiliste ``PSR(SR*)`` (Sharpe par période ; ``SR* = 0`` par défaut)."""
    return float(stats.probabilistic_sharpe(_as_series(returns), sr_benchmark=sr_benchmark))


def dsr(returns: Any, n_trials: Any, sr_variance: float | None = None, sr_mean: float = 0.0) -> float:
    """Sharpe dégonflé avec ``N`` = nombre d'essais **du registre** (N brut, revue 04 §4.4).

    ``n_trials`` : entier, ou un ``TrialRegistry`` (``N = registre.n_trials()``
    et, si ``sr_variance`` est omis, ``registre.sharpe_variance()``).
    ``sr_variance`` est la variance, entre essais, des Sharpe **par période**
    (hebdomadaires ici). NaN si elle est inconnue : le DSR n'est alors pas
    évaluable (aucune valeur n'est inventée).
    """
    if hasattr(n_trials, "n_trials") and callable(n_trials.n_trials):
        registry = n_trials
        n_trials = int(registry.n_trials())
        if sr_variance is None:
            sr_variance = float(registry.sharpe_variance())
    if int(n_trials) < 1:
        raise ValueError("n_trials doit être >= 1")
    if not (sr_variance is not None and math.isfinite(sr_variance) and sr_variance >= 0):
        return math.nan
    return float(stats.deflated_sharpe(_as_series(returns), n_trials=int(n_trials), sr_variance=float(sr_variance),
                                       sr_mean=sr_mean))


# ---------------------------------------------------------------------------
# Rendement, drawdown, ratio d'information
# ---------------------------------------------------------------------------


def annualized_return(returns: Any, periods_per_year: int = WEEKS_PER_YEAR) -> float:
    """Rendement annualisé géométrique ``(Π(1 + r))^(P/n) − 1``."""
    x = _as_series(returns).dropna().to_numpy()
    if x.size == 0:
        return math.nan
    w = float(np.prod(1.0 + x))
    return w ** (periods_per_year / x.size) - 1.0 if w > 0 else -1.0


def annualized_active_return(strategy: Any, benchmark: Any, periods_per_year: int = WEEKS_PER_YEAR) -> float:
    """Rendement actif net annualisé : ``CAGR(stratégie) − CAGR(indice)`` sur les semaines communes."""
    s, b = _as_series(strategy, "strategy"), _as_series(benchmark, "benchmark")
    both = pd.concat({"s": s, "b": b}, axis=1, join="inner").dropna()
    if both.empty:
        return math.nan
    return annualized_return(both["s"], periods_per_year) - annualized_return(both["b"], periods_per_year)


def information_ratio(active: Any, periods_per_year: int = WEEKS_PER_YEAR) -> float:
    """Ratio d'information naïf annualisé ``√P · moyenne(a) / écart-type(a)``."""
    return naive_sharpe(active, periods_per_year)


def max_drawdown(returns: Any) -> float:
    """Drawdown maximal (≤ 0) de la richesse ``Π(1 + r)``, capital initial compris."""
    x = _as_series(returns).dropna().to_numpy()
    if x.size == 0:
        return math.nan
    wealth = np.cumprod(1.0 + x)
    peak = np.maximum.accumulate(np.concatenate(([1.0], wealth)))[1:]
    return float(np.min(wealth / peak - 1.0))


def relative_drawdown(strategy: Any, benchmark: Any) -> float:
    """Drawdown maximal de la richesse **relative** ``Π(1 + r_s) / Π(1 + r_b)`` (≤ 0)."""
    s, b = _as_series(strategy, "strategy"), _as_series(benchmark, "benchmark")
    both = pd.concat({"s": s, "b": b}, axis=1, join="inner").dropna()
    if both.empty:
        return math.nan
    rel = np.cumprod(1.0 + both["s"].to_numpy()) / np.cumprod(1.0 + both["b"].to_numpy())
    peak = np.maximum.accumulate(np.concatenate(([1.0], rel)))[1:]
    return float(np.min(rel / peak - 1.0))


# ---------------------------------------------------------------------------
# Bootstrap stationnaire et CVaR
# ---------------------------------------------------------------------------


def _ir_stat(periods_per_year: int) -> Callable[[np.ndarray], float]:
    def stat(x: np.ndarray) -> float:
        sd = float(np.std(x, ddof=1))
        return float(math.sqrt(periods_per_year) * np.mean(x) / sd) if sd > 0 else math.nan

    return stat


def bootstrap_ci(
    returns: Any,
    stat: str | Callable[[np.ndarray], float] = "ir",
    *,
    n_boot: int = N_BOOT,
    mean_block: float = WEEKLY_MEAN_BLOCK,
    alpha: float = 0.05,
    seed: int = 0,
    periods_per_year: int = WEEKS_PER_YEAR,
) -> dict[str, Any]:
    """Intervalle de confiance du bootstrap stationnaire (percentiles ``α/2`` et ``1 − α/2``).

    ``stat="ir"`` (ou ``"sharpe"``) : ratio annualisé ``√P · moyenne / écart-type`` ;
    ``"mean"`` : moyenne annualisée ; ou une fonction ``f(np.ndarray) -> float``.
    Défauts de la spécification : ``n_boot = 5 000``, blocs moyens de 8 semaines.

    Returns
    -------
    dict
        ``point``, ``lower``, ``upper``, ``n_boot``, ``mean_block``, ``alpha``,
        ``n_valid``.
    """
    x = _as_series(returns).dropna().to_numpy(dtype=float)
    if isinstance(stat, str):
        key = stat.lower()
        if key in ("ir", "sharpe"):
            fn = _ir_stat(periods_per_year)
        elif key == "mean":
            def fn(v: np.ndarray) -> float:
                return float(np.mean(v) * periods_per_year)
        else:
            raise ValueError(f"statistique inconnue : {stat!r}")
    else:
        fn = stat
    point = float(fn(x)) if x.size >= 2 else math.nan
    if x.size < 2:
        return {"point": point, "lower": math.nan, "upper": math.nan, "n_boot": int(n_boot),
                "mean_block": float(mean_block), "alpha": float(alpha), "n_valid": 0}
    draws = stats.stationary_bootstrap(x, fn, n_boot=int(n_boot), mean_block=float(mean_block), seed=seed)
    draws = np.asarray(draws, dtype=float).ravel()
    ok = draws[np.isfinite(draws)]
    lower = float(np.quantile(ok, alpha / 2.0)) if ok.size else math.nan
    upper = float(np.quantile(ok, 1.0 - alpha / 2.0)) if ok.size else math.nan
    return {"point": point, "lower": lower, "upper": upper, "n_boot": int(n_boot), "mean_block": float(mean_block),
            "alpha": float(alpha), "n_valid": int(ok.size)}


def cvar(returns: Any, alpha: float = 0.95) -> float:
    """CVaR (perte moyenne au-delà de la VaR) en **perte positive**.

    ``CVaR_α = −moyenne des k pires rendements``, ``k = ⌈n·(1 − α)⌉`` (au
    moins 1) : estimateur empirique de Rockafellar & Uryasev (2000) sur les
    scénarios fournis.
    """
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha doit être dans ]0, 1[")
    x = _as_series(returns).dropna().to_numpy(dtype=float)
    return _cvar_np(x, alpha)


def _cvar_np(x: np.ndarray, alpha: float) -> float:
    """CVaR empirique d'un tableau sans NaN (voir :func:`cvar`)."""
    if x.size == 0:
        return math.nan
    k = max(1, math.ceil(x.size * (1.0 - alpha) - 1e-12))
    return float(-np.mean(np.partition(x, k - 1)[:k])) if k < x.size else float(-np.mean(x))


def _cvar_rows(alpha: float) -> Callable[[np.ndarray], np.ndarray]:
    def fn(sample: np.ndarray) -> np.ndarray:
        if sample.ndim == 1:
            return np.array([_cvar_np(sample, alpha)])
        return np.array([_cvar_np(sample[:, i], alpha) for i in range(sample.shape[1])])

    return fn


def cvar_bootstrap(
    returns: Any,
    alpha: float = 0.95,
    *,
    n_boot: int = N_BOOT,
    mean_block: float = WEEKLY_MEAN_BLOCK,
    seed: int = 0,
) -> dict[str, float]:
    """CVaR 95 % **à 5 séances** par bootstrap stationnaire de rendements hebdomadaires.

    Un rendement hebdomadaire W-FRI couvre 5 séances : chaque réplique
    (blocs moyens de 8 semaines, 5 000 répliques) donne une CVaR empirique ;
    l'estimation est la **moyenne** des répliques (``cvar``), avec la valeur
    sur l'échantillon (``cvar_point``) et l'intervalle 2,5 %-97,5 %. Ne
    jamais l'appliquer à des rendements quotidiens (tronqués à ±7,5 %).
    """
    x = _as_series(returns).dropna().to_numpy(dtype=float)
    point = cvar(x, alpha)
    if x.size < 2:
        return {"cvar": point, "cvar_point": point, "lower": math.nan, "upper": math.nan, "n_boot": int(n_boot)}
    draws = stats.stationary_bootstrap(x, _cvar_rows(alpha), n_boot=int(n_boot), mean_block=float(mean_block),
                                       seed=seed)[:, 0]
    return {
        "cvar": float(np.mean(draws)),
        "cvar_point": point,
        "lower": float(np.quantile(draws, 0.025)),
        "upper": float(np.quantile(draws, 0.975)),
        "n_boot": int(n_boot),
    }


def cvar_ratio(
    strategy_weekly: Any,
    benchmark_weekly: Any,
    alpha: float = 0.95,
    *,
    n_boot: int = N_BOOT,
    mean_block: float = WEEKLY_MEAN_BLOCK,
    seed: int = 0,
) -> dict[str, float]:
    """Rapport ``CVaR(stratégie) / CVaR(indice)`` (critère candidat n° 7 : ≤ 1,25).

    Les semaines sont tirées **conjointement** (même bootstrap pour la
    stratégie et l'indice, ce qui préserve leur dépendance) ; ``ratio`` est
    le rapport des CVaR moyennes des répliques, ``ratio_median`` la médiane
    des rapports réplique par réplique.
    """
    s, b = _as_series(strategy_weekly, "strategy"), _as_series(benchmark_weekly, "benchmark")
    both = pd.concat({"s": s, "b": b}, axis=1, join="inner").dropna()
    data = both.to_numpy(dtype=float)
    if data.shape[0] < 2:
        raise ValueError("au moins deux semaines communes sont nécessaires")
    draws = stats.stationary_bootstrap(data, _cvar_rows(alpha), n_boot=int(n_boot), mean_block=float(mean_block),
                                       seed=seed)
    cs, cb = draws[:, 0], draws[:, 1]
    with np.errstate(divide="ignore", invalid="ignore"):
        per = cs / cb
    per = per[np.isfinite(per)]
    mean_b = float(np.mean(cb))
    return {
        "ratio": float(np.mean(cs) / mean_b) if mean_b > 0 else math.nan,
        "ratio_median": float(np.median(per)) if per.size else math.nan,
        "cvar_strategy": float(np.mean(cs)),
        "cvar_benchmark": mean_b,
        "cvar_strategy_point": cvar(data[:, 0], alpha),
        "cvar_benchmark_point": cvar(data[:, 1], alpha),
        "n_boot": int(n_boot),
    }


# ---------------------------------------------------------------------------
# PBO de la famille de variantes
# ---------------------------------------------------------------------------


def _lo_metric(q: int, periods_per_year: int) -> Callable[[np.ndarray], np.ndarray]:
    def metric(X: np.ndarray) -> np.ndarray:
        out = np.empty(X.shape[1])
        for i in range(X.shape[1]):
            col = X[:, i]
            col = col[np.isfinite(col)]
            try:
                out[i] = stats.lo_adjusted_sharpe(col, q=q, periods_per_year=periods_per_year)
            except ValueError:
                out[i] = math.nan
        return out

    metric.__name__ = f"sharpe_lo_q{q}"
    return metric


def family_pbo(
    weekly_active: pd.DataFrame,
    *,
    n_splits: int = 10,
    lo_q: int = 4,
    periods_per_year: int = WEEKS_PER_YEAR,
) -> dict[str, Any]:
    """PBO (CSCV) de la famille des variantes, critère = Sharpe de Lo des rendements actifs nets.

    ``weekly_active`` : matrice semaines × variantes (8 variantes du §3.4).
    ``n_splits = 10`` blocs en hebdomadaire (C(10, 5) = 252 combinaisons).
    Renvoie le dictionnaire de ``stats.pbo_cscv`` (``pbo``,
    ``degradation_slope``…).
    """
    frame = weekly_active.dropna(how="any")
    return stats.pbo_cscv(frame, n_splits=n_splits, metric=_lo_metric(lo_q, periods_per_year),
                          periods_per_year=periods_per_year)
