"""Mesures hebdomadaires de validation (spécification §8.2, revue 04 §2, §4, §7, §12, §13).

Toutes les métriques de portefeuille de la validation sont calculées sur des
rendements **hebdomadaires W-FRI**, **nets de coûts**, contre le BRVM
Composite Total Return (reconstruit avant le 02/01/2025). La fréquence
hebdomadaire atténue les prix périmés de la BRVM (autocorrélation des
rendements quotidiens) ; l'annualisation suit la convention de 52 semaines.

Contenu
-------
* :func:`weekly_returns` : composition des rendements quotidiens en semaines
  W-FRI, avec exclusion de la seule fenêtre du §8.1 (06/05 → 25/06/2021) ; les semaines
  dont l'observation couvre plusieurs séances (trou de BOC) sont **gardées** pour chaîner
  les rendements (§3.1.3) et listées par :func:`multi_session_weeks` ;
  :func:`dispersion_sample` les retire des statistiques de dispersion (IR, TE, Sharpe,
  PSR/DSR, PBO, CVaR, bootstrap) ;
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
  rendements actifs nets) ;
* fenêtre d'évaluation de l'additif v1.1 (D2, spéc. §8.4) :
  :func:`first_investment_date` (``t0`` = première séance où la variante A
  détient des titres), :func:`evaluation_window` (rendements quotidiens de
  ``[t0 ; fin]``), :func:`rebase_at` (niveaux rebasés à ``t0``) et
  :func:`evaluation_subperiods` (sous-période 1 = ``[t0 ; 2019-12-31]``,
  sous-période 2 = ``[2020-01-01 ; 2022-11-16]``) ; la fenêtre du 06/05 au
  25/06/2021 est exclue **par défaut** de :func:`weekly_returns` (et de
  ``walkforward.evaluate_status``) ;
* :func:`monthly_ic` : IC mensuel de Spearman d'un score (horizon de 21
  séances, délai d'une séance, au moins 15 titres), entrée du filtre G7.

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
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from brvm_alpha.quant import stats

__all__ = [
    "EXCLUDE_STATS_WINDOWS",
    "GLMSmoothing",
    "MAX_WEEKLY_SESSIONS",
    "N_BOOT",
    "S0",
    "S1",
    "S1_SUBPERIODS",
    "S0_SUBPERIODS",
    "S2_FROM",
    "FAMILY_SIZE_V11",
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
    "dispersion_sample",
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
    "evaluation_subperiods",
    "evaluation_window",
    "first_investment_date",
    "monthly_ic",
    "monthly_one_way_turnover",
    "multi_session_weeks",
    "pbo_null_reference",
    "rebase_at",
    "weekly_observation_mask",
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
#: Sous-périodes de **diagnostic** de S0 (aucune valeur de preuve) : avant / après le premier
#: niveau officiel du Composite TR (02/01/2025). Choix descriptif, pas un critère de la spécification.
S0_SUBPERIODS: tuple[tuple[str, str], tuple[str, str]] = (("2022-11-17", "2024-12-31"), ("2025-01-01", "2026-11-20"))
#: Taille de la famille de la PBO et du DSR depuis l'additif v1.1 (D9 : variantes A à I).
FAMILY_SIZE_V11 = 9


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


#: Séances au plus couvertes par une observation « hebdomadaire » (5 + une séance de marge
#: pour un vendredi férié) : au-delà, l'observation couvre un trou de BOC (2021 : 7 à 49 jours).
MAX_WEEKLY_SESSIONS = 6


def weekly_observation_mask(
    daily_index: pd.DatetimeIndex | Sequence[Any],
    week_index: pd.DatetimeIndex | Sequence[Any],
    *,
    freq: str = WEEKLY_FREQ,
    exclude_windows: Sequence[tuple[Any, Any]] | None = EXCLUDE_STATS_WINDOWS,
    max_sessions: int | None = MAX_WEEKLY_SESSIONS,
    session_no: pd.Series | None = None,
) -> np.ndarray:
    """Observations hebdomadaires utilisables pour les statistiques (§3.1.3, §8.1).

    Une observation de la semaine ``w`` couvre les séances comprises entre la dernière
    séance observée de la semaine précédente (exclue) et la dernière séance observée de
    ``w`` (incluse). Elle est **retirée** si elle couvre plus de ``max_sessions`` séances
    (trou de BOC : un BOC manquant n'est pas un jour férié ; comptage par ``session_no``
    s'il est fourni, sinon en jours ouvrés) ou si la semaine recoupe une fenêtre de
    ``exclude_windows`` (06/05 → 25/06/2021). Renvoie un masque booléen aligné sur
    ``week_index`` (vrai = conservée).
    """
    days = pd.DatetimeIndex(pd.to_datetime(list(daily_index))).sort_values().unique()
    weeks = pd.DatetimeIndex(pd.to_datetime(list(week_index)))
    keep = np.ones(len(weeks), dtype=bool)
    if not len(weeks):
        return keep
    if exclude_windows:
        w_per = weeks.to_period(freq)
        w_start = pd.DatetimeIndex(w_per.start_time.normalize())
        w_end = pd.DatetimeIndex(w_per.end_time.normalize())
        for a, b in exclude_windows:
            keep &= ~((w_start <= pd.Timestamp(b)) & (w_end >= pd.Timestamp(a)))
    if max_sessions is not None and len(days):
        last = pd.Series(days, index=days).groupby(days.to_period(freq)).max()
        labels = pd.DatetimeIndex(last.index.end_time.normalize())
        last_d = pd.DatetimeIndex(last.to_numpy())
        prev_d = last_d[:-1]
        cur_d = last_d[1:]
        if session_no is not None:
            sn = pd.to_numeric(pd.Series(session_no), errors="coerce")
            sn.index = pd.DatetimeIndex(pd.to_datetime(sn.index))
            a = sn.reindex(prev_d).to_numpy(dtype=float)
            b = sn.reindex(cur_d).to_numpy(dtype=float)
            span = b - a
            fallback = ~np.isfinite(span)
            if fallback.any():
                bd = np.busday_count(prev_d.to_numpy(dtype="datetime64[D]"), cur_d.to_numpy(dtype="datetime64[D]"))
                span = np.where(fallback, bd, span)
        else:
            span = np.busday_count(prev_d.to_numpy(dtype="datetime64[D]"), cur_d.to_numpy(dtype="datetime64[D]"))
        too_long = pd.Series(np.r_[False, np.asarray(span, dtype=float) > int(max_sessions)], index=labels)
        keep &= ~too_long.reindex(weeks, fill_value=False).to_numpy(dtype=bool)
    return keep


def multi_session_weeks(
    daily_index: pd.DatetimeIndex | Sequence[Any],
    week_index: pd.DatetimeIndex | Sequence[Any] | None = None,
    *,
    freq: str = WEEKLY_FREQ,
    max_sessions: int = MAX_WEEKLY_SESSIONS,
    session_no: pd.Series | None = None,
) -> pd.DatetimeIndex:
    """Semaines dont l'observation couvre **plus** de ``max_sessions`` séances (trou de BOC, §3.1.3).

    ``daily_index`` : séances observées (calendrier des BOC) ; ``week_index`` : semaines à
    examiner (défaut : toutes les semaines W-FRI observées). Comptage par ``session_no`` s'il est
    fourni, sinon en jours ouvrés (:func:`weekly_observation_mask`). Ces semaines sont
    **gardées** pour chaîner les rendements (rendement annualisé, actif, drawdowns) et retirées
    des seules statistiques de dispersion (:func:`dispersion_sample`).
    """
    days = pd.DatetimeIndex(pd.to_datetime(list(daily_index))).sort_values().unique()
    if week_index is None:
        week_index = pd.DatetimeIndex(days.to_period(freq).unique().end_time.normalize()) if len(days) \
            else pd.DatetimeIndex([])
    weeks = pd.DatetimeIndex(pd.to_datetime(list(week_index)))
    if not len(weeks) or not len(days):
        return pd.DatetimeIndex([], name="week")
    keep = weekly_observation_mask(days, weeks, freq=freq, exclude_windows=None, max_sessions=int(max_sessions),
                                   session_no=session_no)
    return pd.DatetimeIndex(weeks[~keep], name="week")


def dispersion_sample(x: Any, multi_weeks: Sequence[Any] | pd.DatetimeIndex | None) -> Any:
    """``x`` (``Series`` ou ``DataFrame`` hebdomadaire) sans les semaines multi-séances ``multi_weeks``.

    À utiliser pour les statistiques de **dispersion** seulement (IR, TE, volatilité, Sharpe,
    PSR/DSR, PBO, CVaR, bootstrap) : une observation qui couvre 7 à 49 séances n'a pas la
    variance d'une semaine. Les critères **chaînés** (rendement annualisé, actif, drawdowns)
    gardent toutes les semaines (§3.1.3 : « gardé pour chaîner le TR »).
    """
    if multi_weeks is None or not len(multi_weeks) or x is None or not len(x):
        return x
    drop = pd.DatetimeIndex(pd.to_datetime(list(multi_weeks)))
    idx = pd.DatetimeIndex(x.index)
    return x.loc[~idx.isin(drop)]


def weekly_returns(
    daily: pd.Series | pd.DataFrame,
    *,
    freq: str = WEEKLY_FREQ,
    exclude_windows: Sequence[tuple[Any, Any]] | None = EXCLUDE_STATS_WINDOWS,
    min_days: int = 1,
    max_sessions: int | None = None,
    session_no: pd.Series | None = None,
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
        retirées. **Défaut** : :data:`EXCLUDE_STATS_WINDOWS` (06/05 → 25/06/2021,
        §8.1 : rendements exclus des statistiques) ; ``None`` : aucune exclusion.
    min_days
        Nombre minimal de séances observées dans la semaine.
    max_sessions
        **Défaut ``None``** : toutes les semaines sont gardées, y compris celles dont
        l'observation couvre plusieurs séances après un trou de BOC (7 à 18 séances de
        juillet à novembre 2021) : la spécification §3.1.3 les exclut des estimations de
        volatilité, de bêta et de covariance « mais [les garde] pour chaîner le TR ».
        Un entier retire ces semaines (échantillon de **dispersion** seulement,
        :func:`weekly_observation_mask`). Avant la correction du 22/11/2026, le défaut
        valait 6 : 7 semaines de 2018-2021 étaient retirées du chaînage (TR, actif,
        drawdowns faussés).
    session_no
        Numéro global de séance par date (calendrier des BOC) pour un comptage
        exact ; à défaut, jours ouvrés.

    Les semaines retirées sont listées dans ``attrs["weeks_dropped"]`` ; les semaines
    multi-séances (plus de :data:`MAX_WEEKLY_SESSIONS` séances), gardées ou non, dans
    ``attrs["multi_session_weeks"]``.
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
    observed = frame.index[frame.notna().any(axis=1).to_numpy()]
    keep = weekly_observation_mask(observed, out.index, freq=freq, exclude_windows=exclude_windows,
                                   max_sessions=max_sessions, session_no=session_no)
    dropped = [d for d, k, has in zip(out.index, keep, out.notna().any(axis=1).to_numpy(), strict=True)
               if not k and has]
    multi = list(multi_session_weeks(observed, out.index[out.notna().any(axis=1).to_numpy()], freq=freq,
                                     session_no=session_no)) if len(observed) else []
    out = out.loc[keep]
    if isinstance(daily, pd.Series):
        res = out.iloc[:, 0].dropna()
        res.name = daily.name
        res.attrs["weeks_dropped"] = dropped
        res.attrs["multi_session_weeks"] = multi
        return res
    res_df = out.dropna(how="all")
    res_df.attrs["weeks_dropped"] = dropped
    res_df.attrs["multi_session_weeks"] = multi
    return res_df


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


def require_statsmodels() -> Any:
    """Classe ``ARIMA`` de statsmodels ; :class:`~brvm_alpha.erreurs.ConfigurationError` (code de sortie 8)
    si le paquet manque. Aucun repli silencieux : le lissage GLM du test S1 (pré-enregistré) se calcule par
    maximum de vraisemblance, jamais par une autre méthode faute de paquet (commandes ``validate``, ``backtest``)."""
    try:
        from statsmodels.tsa.arima.model import ARIMA
    except ImportError as exc:
        from brvm_alpha.erreurs import ConfigurationError

        raise ConfigurationError(
            "statsmodels n'est pas installé : validate et le lissage GLM du test S1 en ont besoin (aucun repli "
            "silencieux). Installer statsmodels, ou ne pas lancer cette commande.") from exc
    return ARIMA


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
        ARIMA = require_statsmodels()
        try:
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
    if x.size < max(2, 2.0 * float(mean_block)):
        # Moins de deux blocs moyens : un bootstrap par blocs rééchantillonne quasiment la même
        # série (intervalle de largeur nulle trompeur) ; aucun intervalle n'est rendu.
        return {"point": point, "lower": math.nan, "upper": math.nan, "n_boot": int(n_boot),
                "mean_block": float(mean_block), "alpha": float(alpha), "n_valid": 0,
                "note": f"{x.size} observation(s) < 2 × bloc moyen ({2.0 * float(mean_block):g}) : non évaluable"}
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
    split: str = "trim_oldest",
    ties: str = "le",
) -> dict[str, Any]:
    """PBO (CSCV) de la famille des variantes, critère = Sharpe de Lo des rendements actifs nets.

    ``weekly_active`` : matrice semaines × variantes (9 variantes A-I depuis l'additif v1.1, §3.4).
    ``n_splits = 10`` blocs en hebdomadaire (C(10, 5) = 252 combinaisons).
    ``split`` et ``ties`` : conventions de ``stats.pbo_cscv`` (défauts = convention figée avant
    S1 : blocs égaux, plus anciennes semaines en surnombre ignorées ; ``λ = 0`` compté comme
    sur-ajustement). Renvoie le dictionnaire de ``stats.pbo_cscv`` (``pbo``,
    ``degradation_slope``…).
    """
    frame = weekly_active.dropna(how="any")
    return stats.pbo_cscv(frame, n_splits=n_splits, metric=_lo_metric(lo_q, periods_per_year),
                          periods_per_year=periods_per_year, split=split, ties=ties)


def pbo_null_reference(n_configs: int, ties: str = "le") -> float:
    """PBO attendue sous l'hypothèse nulle (configurations i.i.d., aucun signal) pour ``N`` configurations.

    Le rang OOS de la configuration choisie est uniforme sur ``1..N`` ; ``ω = rang/(N + 1)``.
    Avec ``ties="le"`` (``λ ≤ 0`` compté comme sur-ajustement), la PBO nulle vaut
    ``⌊(N + 1)/2⌋ / N`` : **5/9 ≈ 0,556** pour N = 9 (et non 0,5) ; avec ``ties="half"``
    (``λ = 0`` compté pour ½), elle vaut 0,5 pour tout N.
    """
    n = int(n_configs)
    if n < 2:
        raise ValueError("au moins deux configurations")
    if ties == "half":
        return 0.5
    if ties != "le":
        raise ValueError("ties doit valoir 'le' ou 'half'")
    return float(((n + 1) // 2) / n)


# ---------------------------------------------------------------------------
# Rotation mensuelle et début d'investissement (entrées de ``evaluate_status``)
# ---------------------------------------------------------------------------


def monthly_one_way_turnover(result: Any, *, skip_first_month: bool = True) -> float:
    """Rotation moyenne **mensuelle aller** (critère C5 : ≤ 20 %/mois).

    ``result`` : ``BacktestResult`` (``turnover_daily`` = ``Σ|V| / (2 · NAV_{t−1})`` par
    séance) ou ``Series`` de rotation quotidienne aller. Rotation d'un mois = somme des
    rotations quotidiennes du mois civil ; on renvoie la moyenne sur les mois.
    ``skip_first_month`` : le premier mois avec des transactions (constitution initiale
    du portefeuille depuis les liquidités, ≈ 49 % aller) est exclu. Attention :
    ``BacktestResult.turnover`` est, lui, **annualisé** (``252 × moyenne quotidienne``).
    """
    daily = getattr(result, "turnover_daily", result)
    s = pd.Series(daily, dtype=float).dropna()
    if not len(s):
        return math.nan
    if not isinstance(s.index, pd.DatetimeIndex):
        s.index = pd.DatetimeIndex(pd.to_datetime(s.index))
    monthly = s.groupby(s.index.to_period("M")).sum()
    if skip_first_month:
        active = monthly[monthly > 0]
        if len(active):
            monthly = monthly[monthly.index > active.index[0]]
    return float(monthly.mean()) if len(monthly) else math.nan


def first_investment_date(result: Any, min_exposure: float = 0.0) -> pd.Timestamp | None:
    """Première séance où l'exposition actions dépasse ``min_exposure``.

    ``result`` : ``BacktestResult`` (exposition = ``weights.sum(axis=1)``) ou ``Series``
    d'exposition (fraction de la NAV investie). ``None`` si la stratégie ne s'investit
    jamais. Sert à faire commencer la fenêtre d'évaluation (stratégie ET indice) à la
    première décision investissable (période de démarrage en liquidités, §8.3).
    """
    w = getattr(result, "weights", None)
    expo = w.sum(axis=1) if isinstance(w, pd.DataFrame) else pd.Series(result, dtype=float)
    expo = expo.astype(float)
    hit = expo[expo > float(min_exposure)]
    return pd.Timestamp(hit.index[0]) if len(hit) else None


# ---------------------------------------------------------------------------
# Fenêtre d'évaluation commune (additif v1.1, D2)
# ---------------------------------------------------------------------------


def evaluation_window(daily: pd.Series | pd.DataFrame, t0: Any, end: Any = None) -> pd.Series | pd.DataFrame:
    """Rendements quotidiens de la fenêtre d'évaluation ``[t0 ; end]`` (bornes incluses).

    Additif v1.1, D2 : ``t0`` est la première séance où la variante A détient des titres
    (:func:`first_investment_date`), **commune** à toutes les variantes et à tous les étalons.
    Le rendement de la séance ``t0`` (celle des premiers achats, qui porte les frais d'achat
    initiaux) est **compté** : choix prudent, les niveaux sont donc rebasés à la clôture de la
    veille de ``t0`` (:func:`rebase_at`).
    """
    obj = daily.copy()
    if not isinstance(obj.index, pd.DatetimeIndex):
        obj.index = pd.DatetimeIndex(pd.to_datetime(obj.index))
    obj = obj.sort_index()
    keep = obj.index >= pd.Timestamp(t0)
    if end is not None:
        keep &= obj.index <= pd.Timestamp(end)
    return obj.loc[keep]


def rebase_at(level: pd.Series | pd.DataFrame, t0: Any, base: float = 100.0) -> pd.Series | pd.DataFrame:
    """Niveaux rebasés à ``base`` à la clôture de la **veille** de ``t0`` (NaN avant).

    Cohérent avec :func:`evaluation_window` : ``rebase_at(L, t0)`` composé des rendements
    quotidiens de ``[t0 ; fin]`` redonne le niveau. Sans séance antérieure à ``t0``, la base
    est la clôture de ``t0``. Une série sans valeur finie à la date de base est rebasée sur sa
    première valeur finie ultérieure.
    """
    obj = level.copy()
    if not isinstance(obj.index, pd.DatetimeIndex):
        obj.index = pd.DatetimeIndex(pd.to_datetime(obj.index))
    obj = obj.sort_index().astype(float)
    t0 = pd.Timestamp(t0)
    before = obj.index[obj.index < t0]
    anchor = before[-1] if len(before) else (obj.index[obj.index >= t0][0] if (obj.index >= t0).any() else None)
    if anchor is None:
        return obj * np.nan
    sub = obj.loc[obj.index >= anchor]
    first = sub.ffill().bfill().iloc[0] if isinstance(sub, pd.Series) else sub.bfill().iloc[0]
    out = obj * np.nan
    out.loc[obj.index >= anchor] = (sub / first * float(base))
    return out


def evaluation_subperiods(
    t0: Any,
    subperiods: Sequence[tuple[Any, Any]] = S1_SUBPERIODS,
    end: Any = None,
) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Sous-périodes de la fenêtre d'évaluation (additif v1.1, D2).

    La première commence à ``max(t0, début)`` (S1 : ``[t0 ; 2019-12-31]``), la seconde reste
    ``[2020-01-01 ; 2022-11-16]``. ``end`` (étiquette de la dernière semaine W-FRI, p. ex. le
    vendredi 18/11/2022 qui porte les séances des 14-16/11/2022) prolonge la dernière borne
    pour que la dernière semaine partielle soit comptée dans la sous-période 2.
    """
    t0 = pd.Timestamp(t0)
    out: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    periods = [(pd.Timestamp(a), pd.Timestamp(b)) for a, b in subperiods]
    for i, (a, b) in enumerate(periods):
        if i == len(periods) - 1 and end is not None:
            b = max(b, pd.Timestamp(end))
        a = max(a, t0)
        if a <= b:
            out.append((a, b))
    return out


def monthly_ic(
    scores: Mapping[Any, pd.Series] | pd.DataFrame,
    tr_index: pd.DataFrame,
    *,
    horizon: int = 21,
    lag: int = 1,
    min_names: int = 15,
    end: Any = None,
    eligible: Mapping[Any, pd.Series] | pd.DataFrame | None = None,
    one_per_month: bool = True,
) -> pd.Series:
    """IC mensuel de Spearman d'un score (spéc. §3.5, entrée du filtre G7 du §8.3).

    Pour chaque date de décision ``t`` : rendement total à terme de ``t + lag`` à
    ``t + lag + horizon`` séances (lignes de ``tr_index``), corrélation de rang avec le score
    connu en ``t`` sur les titres où les deux sont finis (et éligibles si ``eligible`` est
    fourni) ; NaN sous ``min_names`` titres. Une date dont la fenêtre à terme dépasse ``end``
    (fin de l'échantillon) ou la dernière séance est **omise** : aucun rendement hors de
    l'échantillon évalué n'est lu. Index = dates de décision.

    ``one_per_month`` (défaut, correction du 22/11/2026) : une seule date par mois civil, la
    **dernière** décision du mois (fin de mois, §3.1.5). En mode « evenementiel », les
    décisions d'événement (règle pays, poche S1…) donnaient plusieurs IC par mois, à horizons
    de 21 séances qui se chevauchent (67 IC sur 64 mois au test S1) ; le seuil de G7
    (« au moins 36 mois ») compte alors des mois distincts.
    """
    frame = pd.DataFrame(scores).T if isinstance(scores, Mapping) else pd.DataFrame(scores)
    out: dict[pd.Timestamp, float] = {}
    if frame.empty or tr_index is None or not len(tr_index):
        return pd.Series(out, dtype=float, name="ic")
    frame.index = pd.DatetimeIndex(pd.to_datetime(frame.index))
    if one_per_month and len(frame):
        frame = frame.sort_index()
        frame = frame[~frame.index.to_period("M").duplicated(keep="last")]
    tr = tr_index.sort_index().astype(float)
    tr.index = pd.DatetimeIndex(pd.to_datetime(tr.index))
    frame.index = pd.DatetimeIndex(pd.to_datetime(frame.index))
    el = None
    if eligible is not None:
        el = pd.DataFrame(eligible).T if isinstance(eligible, Mapping) else pd.DataFrame(eligible)
        el.index = pd.DatetimeIndex(pd.to_datetime(el.index))
    last = pd.Timestamp(end) if end is not None else tr.index[-1]
    for t, row in frame.sort_index().iterrows():
        pos = int(tr.index.searchsorted(t, side="right")) - 1
        a, b = pos + int(lag), pos + int(lag) + int(horizon)
        if pos < 0 or b >= len(tr.index) or tr.index[b] > last:
            continue
        fwd = tr.iloc[b] / tr.iloc[a] - 1.0
        sc = pd.to_numeric(row, errors="coerce").astype(float)
        df = pd.concat({"s": sc, "f": fwd}, axis=1, join="inner")
        if el is not None and t in el.index:
            m = el.loc[t].reindex(df.index).astype("boolean").fillna(False).astype(bool)
            df = df[m.to_numpy()]
        df = df.replace([np.inf, -np.inf], np.nan).dropna()
        if len(df) < int(min_names) or df["s"].nunique() < 2 or df["f"].nunique() < 2:
            out[pd.Timestamp(t)] = math.nan
            continue
        out[pd.Timestamp(t)] = float(df["s"].rank().corr(df["f"].rank()))
    return pd.Series(out, dtype=float, name="ic").sort_index()
