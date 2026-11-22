"""Normalisation transversale, neutralisation, composites et évaluation des signaux.

Toutes les opérations « transversales » travaillent **date par date** (une
ligne du panel = une coupe transversale) : la valeur en ``t`` ne dépend que
de la ligne ``t``. Elles n'introduisent donc aucun biais d'anticipation. Les
seules fonctions tournées vers le futur sont :func:`forward_returns` (cible
d'évaluation, jamais une caractéristique) et, par construction, l'IC et les
rendements par quantile qui l'utilisent.

L'IC daté ``d`` dépend des cours jusqu'à ``d + lag + h`` : il n'est observable
qu'en ``d + lag + h``. :func:`shrunk_ic_weights` et :func:`rolling_ic_weights`
appliquent donc **par défaut** un embargo ``E = lag + horizon`` (22 séances
avec les conventions par défaut de :func:`forward_returns`, ``h = 21``,
``lag = 1``) : les poids décidés en ``t`` ne reposent que sur des IC datés
``<= t - E``, déjà observables en ``t``. Un embargo explicite plus court que
``lag + horizon`` (quand l'un des deux est précisé) lève ``ValueError`` ;
``embargo=0`` n'est légitime que pour un historique d'IC déjà daté de sa date
d'observation. Lopez de Prado (2018, ch. 7) pour la purge et l'embargo.

Score composite v1 (``docs/SPECIFICATION_STRATEGIE.md`` §3.1.6, §3.2, §3.4, §5.2) :
:func:`rank_gauss_z` (winsorisation 1-99, ``Φ⁻¹((rang - 0,5)/N)``, ±3, manquant -> 0),
:func:`composite_score` (règle des 3 blocs, malus S2 pour les nouveaux achats,
re-standardisation en rang, variante D par secteur), :func:`modulate_weights`
(redistribution du poids libéré par les modulateurs du momentum),
:func:`s2_penalty_panel` et :data:`VARIANT_WEIGHTS` (variantes A à D).

Convention d'orientation : un signal doit être orienté de sorte qu'une valeur
élevée soit attractive (par ex. ``-volatilité`` pour l'anomalie de faible
volatilité) **avant** normalisation, combinaison et calcul des poids par IC.

Références
----------
* Blom, G. (1958). *Statistical Estimates and Transformed Beta-Variables*.
  Wiley (scores normaux ``Φ⁻¹((r - 3/8)/(n + 1/4))``).
* DeMiguel, V., Garlappi, L. & Uppal, R. (2009). Optimal Versus Naive
  Diversification: How Inefficient is the 1/N Portfolio Strategy? *Review of
  Financial Studies*, 22(5), 1915-1953.
* Fama, E. & MacBeth, J. (1973). Risk, Return, and Equilibrium: Empirical
  Tests. *Journal of Political Economy*, 81(3), 607-636.
* Grinold, R. & Kahn, R. (2000). *Active Portfolio Management*, 2e éd.
  McGraw-Hill (IC, loi fondamentale, scores).
* James, W. & Stein, C. (1961). Estimation with Quadratic Loss. *Proc. 4th
  Berkeley Symposium on Mathematical Statistics and Probability*, 1, 361-379.
* Lopez de Prado, M. (2018). *Advances in Financial Machine Learning*. Wiley
  (ch. 7 : validation croisée purgée, embargo).
* Qian, E., Hua, R. & Sorensen, E. (2007). *Quantitative Equity Portfolio
  Management*. Chapman & Hall/CRC (pondération des facteurs par ``IC/σ(IC)``).
* Spearman, C. (1904). The Proof and Measurement of Association between Two
  Things. *American Journal of Psychology*, 15(1), 72-101.
"""

from __future__ import annotations

import warnings
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, TypeAlias

import numpy as np
import pandas as pd
from scipy.special import ndtri

__all__ = [
    "MOMENTUM_BLOCKS",
    "VARIANT_SECTOR_NEUTRAL",
    "VARIANT_WEIGHTS",
    "CompositeResult",
    "combine",
    "composite_score",
    "cross_sectional_zscore",
    "forward_returns",
    "information_coefficient",
    "modulate_weights",
    "neutralize",
    "quantile_returns",
    "rank_gauss_z",
    "rolling_ic_weights",
    "s2_penalty_panel",
    "shrunk_ic_weights",
    "variant_weights",
]

Frame: TypeAlias = pd.DataFrame
ZMethod: TypeAlias = Literal["rank_gauss", "zscore", "robust"]

_POOL = "__autres__"
_NA_GROUP = "__sans_groupe__"
_EPS = 1e-14
_WINSOR_MAX_ITER = 500
_WINSOR_RTOL = 1e-9

#: Horizon et délai d'exécution par défaut des rendements futurs (séances).
DEFAULT_HORIZON: int = 21
DEFAULT_LAG: int = 1


# ---------------------------------------------------------------------------
# Utilitaires
# ---------------------------------------------------------------------------


def _as_frame(x: pd.DataFrame | pd.Series) -> tuple[pd.DataFrame, bool]:
    """Une ``Series`` (coupe transversale unique) devient un DataFrame à une ligne."""
    if isinstance(x, pd.Series):
        name = x.name if x.name is not None else 0
        return x.to_frame(name=name).T, True
    if isinstance(x, pd.DataFrame):
        return x, False
    raise TypeError("attendu : pd.DataFrame (date × symbole) ou pd.Series (symboles)")


def _finite(df: pd.DataFrame) -> pd.DataFrame:
    out = df.apply(pd.to_numeric, errors="coerce").astype(float)
    return out.where(np.isfinite(out))


def _row_mean_sd(x: np.ndarray, ddof: int = 1) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Moyenne, écart-type et effectif par ligne en ignorant les NaN (sans avertissement)."""
    ok = np.isfinite(x)
    n = ok.sum(axis=1).astype(float)
    xs = np.where(ok, x, 0.0)
    with np.errstate(invalid="ignore", divide="ignore"):
        mu = xs.sum(axis=1) / n
        dev = np.where(ok, x - mu[:, None], 0.0)
        var = (dev**2).sum(axis=1) / (n - ddof)
    sd = np.sqrt(np.where(n > ddof, var, np.nan))
    return mu, sd, n


# ---------------------------------------------------------------------------
# Normalisation transversale
# ---------------------------------------------------------------------------


def cross_sectional_zscore(
    df: pd.DataFrame | pd.Series,
    winsor: float | None = 3.0,
    method: ZMethod = "rank_gauss",
    min_obs: int = 3,
) -> pd.DataFrame | pd.Series:
    """Score transversal par date.

    * ``"rank_gauss"`` (défaut) : rangs moyens ``r`` (ex aequo partagés) des
      ``n`` valeurs observées, transformés en quantiles normaux (Blom, 1958) :
      ``z = Φ⁻¹((r - 3/8) / (n + 1/4))``. Insensible aux valeurs extrêmes et à
      l'échelle, adapté à 48 titres aux distributions très asymétriques
      (illiquidité, PER…).
    * ``"zscore"`` : z-score classique après **winsorisation itérative** :
      tant qu'une valeur dépasse ``μ ± w·σ``, elle est ramenée à cette borne
      et ``μ, σ`` sont recalculés (point fixe, au plus 500 passes, tolérance
      relative 10⁻⁹·σ) ; puis ``z = (x_w - mean(x_w)) / sd(x_w)`` (ddof = 1),
      d'où une moyenne nulle, un écart-type unitaire et ``|z| <= w`` à la
      convergence.
    * ``"robust"`` : ``z = (x - médiane) / (1,4826 · MAD)``, puis borné à ``±w``.

    ``winsor`` borne aussi le résultat final de ``"rank_gauss"`` et
    ``"robust"`` (``None`` : pas de borne). Une ligne de moins de ``min_obs``
    valeurs observées donne NaN ; une ligne sans dispersion donne 0. Les NaN
    restent NaN.

    Parameters
    ----------
    df
        Panel large date × symbole, ou ``Series`` (une seule coupe) : le type
        de sortie suit celui de l'entrée.
    """
    if winsor is not None and winsor <= 0:
        raise ValueError("winsor doit être > 0 ou None")
    frame, is_series = _as_frame(df)
    x_df = _finite(frame)
    x = x_df.to_numpy(dtype=float, copy=True)
    ok = np.isfinite(x)
    n = ok.sum(axis=1).astype(float)
    if method == "rank_gauss":
        ranks = x_df.rank(axis=1, method="average").to_numpy(dtype=float)
        with np.errstate(invalid="ignore", divide="ignore"):
            u = (ranks - 3.0 / 8.0) / (n[:, None] + 0.25)
        z = ndtri(u)
        if winsor is not None:
            z = np.clip(z, -winsor, winsor)
    elif method == "zscore":
        if winsor is not None:
            active = np.arange(x.shape[0])
            for _ in range(_WINSOR_MAX_ITER):
                xa = x[active]
                mu, sd, _n = _row_mean_sd(xa)
                lo = (mu - winsor * sd)[:, None]
                hi = (mu + winsor * sd)[:, None]
                tol = (_WINSOR_RTOL * sd)[:, None]
                with np.errstate(invalid="ignore"):
                    out_of = ok[active] & np.isfinite(lo) & ((xa < lo - tol) | (xa > hi + tol))
                rows = out_of.any(axis=1)
                if not rows.any():
                    break
                x[active] = np.where(out_of, np.clip(xa, lo, hi), xa)
                active = active[rows]
        mu, sd, _n = _row_mean_sd(x)
        with np.errstate(invalid="ignore", divide="ignore"):
            z = (x - mu[:, None]) / sd[:, None]
        flat = np.isfinite(sd) & (sd <= _EPS)
        z[flat, :] = 0.0
    elif method == "robust":
        with warnings.catch_warnings(), np.errstate(invalid="ignore"):
            warnings.simplefilter("ignore", RuntimeWarning)
            med = np.nanmedian(np.where(ok, x, np.nan), axis=1)
            mad = np.nanmedian(np.abs(x - med[:, None]), axis=1)
        scale = 1.4826 * mad
        with np.errstate(invalid="ignore", divide="ignore"):
            z = (x - med[:, None]) / scale[:, None]
        z[np.isfinite(scale) & (scale <= _EPS), :] = 0.0
        if winsor is not None:
            z = np.clip(z, -winsor, winsor)
    else:
        raise ValueError("method doit valoir 'rank_gauss', 'zscore' ou 'robust'")
    z = np.where(ok, z, np.nan)
    z[n < max(min_obs, 1), :] = np.nan
    out = pd.DataFrame(z, index=frame.index, columns=frame.columns)
    return out.iloc[0] if is_series else out


# ---------------------------------------------------------------------------
# Neutralisation
# ---------------------------------------------------------------------------


def _group_labels(groups: pd.Series | pd.DataFrame, like: pd.DataFrame) -> pd.DataFrame:
    if isinstance(groups, pd.DataFrame):
        g = groups.reindex(index=like.index, columns=like.columns)
    elif isinstance(groups, pd.Series):
        g_s = groups.reindex(like.columns)
        g = pd.DataFrame(
            np.broadcast_to(g_s.to_numpy(dtype=object)[None, :], like.shape),
            index=like.index,
            columns=like.columns,
        )
    else:
        raise TypeError("groups doit être une Series (symbole -> groupe) ou un DataFrame")
    g = g.astype(object)
    return g.where(g.notna(), _NA_GROUP).astype(str)


def neutralize(
    df: pd.DataFrame | pd.Series,
    groups: pd.Series | pd.DataFrame,
    method: Literal["demean", "regress"] = "demean",
    min_group_size: int = 1,
    exposures: Mapping[str, pd.DataFrame | pd.Series] | None = None,
) -> pd.DataFrame | pd.Series:
    """Neutralisation par groupes (secteur, pays) date par date.

    * ``"demean"`` : ``x̃_{i,t} = x_{i,t} - mean_{j ∈ g(i), t}(x_{j,t})`` — la
      moyenne de chaque groupe devient nulle.
    * ``"regress"`` : résidus de la régression transversale (Fama & MacBeth,
      1973) ``x_{i,t} = Σ_g γ_{g,t} 1[i ∈ g] + Σ_k δ_{k,t} E_{k,i,t} + ε_{i,t}``.
      Avec les seules indicatrices de groupe, identique à ``"demean"`` ;
      ``exposures`` (par ex. log-taille, bêta) ajoute des expositions
      continues à neutraliser : les résidus sont orthogonaux aux indicatrices
      et aux expositions.

    Fournir ``exposures`` implique la méthode par régression. Les symboles
    sans groupe forment le groupe ``"__sans_groupe__"``. Avec
    ``min_group_size > 1``, les groupes ayant moins de ``min_group_size``
    titres observés à la date ``t`` sont regroupés dans ``"__autres__"``
    (évite d'annuler le signal d'un secteur à un seul titre).

    Parameters
    ----------
    df
        Panel large date × symbole, ou ``Series`` (une coupe).
    groups
        ``Series`` symbole -> groupe (statique) ou panel large de groupes
        (variable dans le temps).
    """
    if method not in ("demean", "regress"):
        raise ValueError("method doit valoir 'demean' ou 'regress'")
    frame, is_series = _as_frame(df)
    x = _finite(frame)
    g = _group_labels(groups, x)
    obs = x.notna()
    if min_group_size > 1:
        g = g.copy()
        for label in pd.unique(g.to_numpy().ravel()):
            in_g = g.eq(label)
            cnt = (in_g & obs).sum(axis=1).to_numpy()
            small = in_g & np.broadcast_to((cnt < min_group_size)[:, None], in_g.shape)
            g = g.mask(small, _POOL)
    if method == "demean" and not exposures:
        out = x.copy()
        for label in pd.unique(g.to_numpy().ravel()):
            in_g = g.eq(label)
            mean_g = x.where(in_g).mean(axis=1)
            out = out.mask(in_g, x.sub(mean_g, axis=0))
        out = out.where(obs)
    else:
        out = _neutralize_regress(x, g, exposures or {})
    return out.iloc[0] if is_series else out


def _neutralize_regress(
    x: pd.DataFrame, g: pd.DataFrame, exposures: Mapping[str, pd.DataFrame | pd.Series]
) -> pd.DataFrame:
    expo: list[np.ndarray] = []
    for name, e in exposures.items():
        if isinstance(e, pd.Series):
            # Exposition statique par symbole, diffusée sur toutes les dates.
            vals = pd.to_numeric(e.reindex(x.columns), errors="coerce").to_numpy(dtype=float)
            e = pd.DataFrame(
                np.broadcast_to(vals[None, :], x.shape), index=x.index, columns=x.columns
            )
        if not isinstance(e, pd.DataFrame):
            raise TypeError(f"exposition {name!r} : DataFrame ou Series attendu")
        expo.append(_finite(e.reindex(index=x.index, columns=x.columns)).to_numpy(dtype=float))
    X = x.to_numpy(dtype=float)
    G = g.to_numpy()
    out = np.full(X.shape, np.nan)
    for t in range(X.shape[0]):
        ok = np.isfinite(X[t])
        for e in expo:
            ok &= np.isfinite(e[t])
        if not ok.any():
            continue
        labels, inv = np.unique(G[t, ok], return_inverse=True)
        D = np.zeros((int(ok.sum()), len(labels)))
        D[np.arange(D.shape[0]), inv] = 1.0
        if expo:
            D = np.column_stack([D] + [e[t, ok] for e in expo])
        y = X[t, ok]
        coef, *_ = np.linalg.lstsq(D, y, rcond=None)
        out[t, ok] = y - D @ coef
    return pd.DataFrame(out, index=x.index, columns=x.columns)


# ---------------------------------------------------------------------------
# Composite
# ---------------------------------------------------------------------------


def combine(
    signals: Mapping[str, pd.DataFrame | pd.Series],
    weights: Mapping[str, float],
    min_coverage: float = 0.0,
) -> pd.DataFrame | pd.Series:
    """Moyenne pondérée de scores avec renormalisation des poids disponibles.

    ``S_{i,t} = Σ_k w_k z_{k,i,t} / Σ_{k : z_{k,i,t} observé} |w_k|``

    Un titre auquel il manque un signal (NaN) est noté sur les signaux
    disponibles, poids renormalisés. Si la part des poids disponibles
    ``Σ_dispo |w_k| / Σ_k |w_k|`` est inférieure à ``min_coverage``, le
    score est NaN. Les signaux absents de ``weights`` sont ignorés ; un poids
    référencant un signal absent lève ``KeyError``. Entrées : z-scores
    orientés (voir :func:`cross_sectional_zscore`), panels ou ``Series``.
    """
    if not 0.0 <= min_coverage <= 1.0:
        raise ValueError("min_coverage doit être dans [0, 1]")
    missing = [k for k in weights if k not in signals]
    if missing:
        raise KeyError(f"poids sans signal correspondant : {missing}")
    keys = [k for k in weights if weights[k] != 0 and np.isfinite(weights[k])]
    if not keys:
        raise ValueError("aucun poids non nul")
    all_series = all(isinstance(signals[k], pd.Series) for k in keys)
    if all_series:
        frames = {k: signals[k].to_frame(name=0).T for k in keys}
    else:
        frames = {k: _as_frame(signals[k])[0] for k in keys}
    index = frames[keys[0]].index
    columns = frames[keys[0]].columns
    for k in keys[1:]:
        index = index.union(frames[k].index)
        columns = columns.union(frames[k].columns)
    total = float(sum(abs(weights[k]) for k in keys))
    num = np.zeros((len(index), len(columns)))
    den = np.zeros_like(num)
    for k in keys:
        z = _finite(frames[k].reindex(index=index, columns=columns)).to_numpy(dtype=float)
        ok = np.isfinite(z)
        num += np.where(ok, weights[k] * z, 0.0)
        den += np.where(ok, abs(weights[k]), 0.0)
    with np.errstate(invalid="ignore", divide="ignore"):
        score = num / den
    score[(den <= 0) | (den < min_coverage * total - 1e-12)] = np.nan
    out = pd.DataFrame(score, index=index, columns=columns)
    return out.iloc[0] if all_series and len(out) == 1 else out


# ---------------------------------------------------------------------------
# Évaluation : rendements futurs, IC, quantiles
# ---------------------------------------------------------------------------


def forward_returns(
    tr_index: pd.DataFrame | pd.Series, horizon: int = DEFAULT_HORIZON, lag: int = DEFAULT_LAG
) -> pd.DataFrame | pd.Series:
    """Rendement futur sur ``horizon`` séances, **pour l'évaluation seulement**.

    ``F_t = P_{t+lag+h} / P_{t+lag} - 1``

    La valeur placée en ``t`` est le rendement qu'aurait obtenu un ordre
    passé à la vue du signal de ``t`` et exécuté au plus tôt en ``t + lag``
    (``lag = 1`` : convention d'exécution en t+1 de la plate-forme ;
    ``lag = 0`` donne ``P_{t+h}/P_t - 1``). Les dernières lignes sont NaN.
    C'est une **cible** : ne jamais l'utiliser comme caractéristique.
    """
    if horizon < 1 or lag < 0:
        raise ValueError("il faut horizon >= 1 et lag >= 0")
    if isinstance(tr_index, pd.DataFrame):
        p = tr_index.apply(pd.to_numeric, errors="coerce").astype(float)
    else:
        p = pd.to_numeric(tr_index, errors="coerce").astype(float)
    p = p.where(p > 0)
    return p.shift(-(lag + horizon)) / p.shift(-lag) - 1.0


def _aligned_pair(
    signal: pd.DataFrame | pd.Series, fwd: pd.DataFrame | pd.Series
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    s, _ = _as_frame(signal)
    f, _ = _as_frame(fwd)
    if isinstance(signal, pd.Series) and isinstance(fwd, pd.Series):
        f.index = s.index
    s, f = _finite(s).align(_finite(f), join="inner")
    mask = s.notna() & f.notna()
    return s.where(mask), f.where(mask), mask


def information_coefficient(
    signal: pd.DataFrame | pd.Series,
    fwd_returns: pd.DataFrame | pd.Series,
    method: Literal["spearman", "pearson"] = "spearman",
    min_obs: int = 10,
) -> pd.Series:
    """Coefficient d'information transversal par date (Grinold & Kahn, 2000).

    ``IC_t = corr_i(rang(s_{i,t}), rang(F_{i,t}))`` (Spearman, 1904) sur les
    titres où signal et rendement futur sont tous deux observés ; ``"pearson"``
    utilise les valeurs brutes. NaN si moins de ``min_obs`` paires ou si l'une
    des deux coupes est sans dispersion.
    """
    if method not in ("spearman", "pearson"):
        raise ValueError("method doit valoir 'spearman' ou 'pearson'")
    s, f, mask = _aligned_pair(signal, fwd_returns)
    if method == "spearman":
        s = s.rank(axis=1, method="average")
        f = f.rank(axis=1, method="average")
    m = mask.to_numpy(dtype=bool)
    n = m.sum(axis=1).astype(float)
    S = np.where(m, s.to_numpy(dtype=float), 0.0)
    F = np.where(m, f.to_numpy(dtype=float), 0.0)
    with np.errstate(invalid="ignore", divide="ignore"):
        sm = np.where(m, S - (S.sum(axis=1) / n)[:, None], 0.0)
        fm = np.where(m, F - (F.sum(axis=1) / n)[:, None], 0.0)
    cov = (sm * fm).sum(axis=1)
    vs = (sm**2).sum(axis=1)
    vf = (fm**2).sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        ic = cov / np.sqrt(vs * vf)
    ic[(n < max(min_obs, 2)) | (vs <= _EPS) | (vf <= _EPS)] = np.nan
    return pd.Series(np.clip(ic, -1.0, 1.0), index=s.index, name="ic", dtype=float)


def quantile_returns(
    signal: pd.DataFrame | pd.Series,
    fwd_returns: pd.DataFrame | pd.Series,
    n: int = 5,
    min_obs: int | None = None,
    add_spread: bool = False,
) -> pd.DataFrame:
    """Rendement futur moyen (équipondéré) par quantile de signal, date par date.

    Les titres observés (signal et rendement) sont classés par rang moyen
    ``r`` ; quantile ``q = ceil(n · r / N_t)`` (1 = signal le plus faible,
    ``n`` = le plus fort), ex aequo dans le même quantile. Colonnes ``1..n`` ;
    ``add_spread=True`` ajoute ``"spread"`` = ``Q_n - Q_1`` (jambe longue
    moins jambe courte, indicatif : pas de vente à découvert à la BRVM). NaN
    si moins de ``min_obs`` titres (défaut ``2n``). Avec 48 titres, préférer
    ``n = 3`` (tertiles, au moins 8 titres par jambe).
    """
    if n < 2:
        raise ValueError("n doit être >= 2")
    min_obs = 2 * n if min_obs is None else min_obs
    s, f, mask = _aligned_pair(signal, fwd_returns)
    cnt = mask.sum(axis=1)
    pct = s.rank(axis=1, method="average", pct=True)
    q = np.ceil(pct * n).clip(lower=1, upper=n)
    out = pd.DataFrame(
        {k: f.where(q == k).mean(axis=1) for k in range(1, n + 1)}, index=s.index, dtype=float
    )
    out.loc[cnt < min_obs, :] = np.nan
    if add_spread:
        out["spread"] = out[n] - out[1]
    out.columns.name = "quantile"
    return out


# ---------------------------------------------------------------------------
# Pondération des signaux par IC, rétrécie vers un a priori
# ---------------------------------------------------------------------------


def _normalized_prior(prior: Mapping[str, float], names: list[str]) -> pd.Series:
    p = pd.Series({k: float(v) for k, v in prior.items()}, dtype=float).reindex(names).fillna(0.0)
    p = p.clip(lower=0.0)
    if p.sum() <= 0:
        return pd.Series(1.0 / len(names), index=names)
    return p / p.sum()


def _shrink(ir: pd.Series, prior: pd.Series, shrinkage: float) -> pd.Series:
    ir = ir.reindex(prior.index).fillna(0.0).clip(lower=0.0)
    w_ic = ir / ir.sum() if ir.sum() > 0 else prior
    w = ((1.0 - shrinkage) * w_ic + shrinkage * prior).clip(lower=0.0)
    return w / w.sum()


def _resolve_embargo(embargo: int | None, horizon: int | None, lag: int | None) -> int:
    """Embargo effectif en séances : ``lag + horizon`` par défaut.

    Un ``embargo`` explicite est accepté tel quel (par ex. ``0`` pour un
    historique d'IC déjà daté de sa date d'observation), sauf s'il est plus
    court que ``lag + horizon`` alors que ``horizon`` ou ``lag`` est précisé
    (paramétrage contradictoire, donc anticipation).
    """
    h = DEFAULT_HORIZON if horizon is None else int(horizon)
    lg = DEFAULT_LAG if lag is None else int(lag)
    if h < 1 or lg < 0:
        raise ValueError("il faut horizon >= 1 et lag >= 0")
    required = h + lg
    if embargo is None:
        return required
    if embargo < 0:
        raise ValueError("embargo doit être >= 0")
    if (horizon is not None or lag is not None) and embargo < required:
        raise ValueError(
            f"embargo={embargo} < lag + horizon = {required} : les poids utiliseraient des IC "
            "qui dépendent de rendements postérieurs à la date de décision"
        )
    return int(embargo)


def _last_usable_rows(
    ic_index: pd.Index,
    decision: pd.Index,
    embargo: int,
    calendar: pd.DatetimeIndex | None,
) -> np.ndarray:
    """Dernière ligne d'IC utilisable pour chaque date de décision (-1 : aucune).

    Sans ``calendar``, l'embargo est compté en **lignes** de l'historique :
    exact pour un IC quotidien aligné sur les séances, prudent (plus long)
    si l'historique est sous-échantillonné. Avec ``calendar`` (séances), il
    est compté en séances : seuls les IC datés ``<= calendar[p(t) - E]``, où
    ``p(t)`` est la dernière séance ``<= t``, sont utilisables.
    """
    pos_t = ic_index.searchsorted(decision, side="right") - 1
    if calendar is None:
        return np.asarray(pos_t - embargo, dtype=int)
    if not isinstance(ic_index, pd.DatetimeIndex):
        raise TypeError("calendar exige un historique d'IC indexé par un DatetimeIndex")
    cal = pd.DatetimeIndex(calendar).unique().sort_values()
    if not len(cal):
        return np.full(len(decision), -1, dtype=int)
    p = cal.searchsorted(decision, side="right") - 1 - embargo
    last = ic_index.searchsorted(cal[np.clip(p, 0, None)], side="right") - 1
    return np.where(p >= 0, last, -1).astype(int)


def _check_ic_args(shrinkage: float, lookback: int | None) -> None:
    if not 0.0 <= shrinkage <= 1.0:
        raise ValueError("shrinkage doit être dans [0, 1]")
    if lookback is not None and lookback < 1:
        raise ValueError("lookback doit être >= 1 ou None")


def _sorted_ic(ic_history: pd.DataFrame) -> pd.DataFrame:
    ic = _finite(ic_history)
    if not ic.index.is_monotonic_increasing:
        raise ValueError("l'index de ic_history doit être trié par date croissante")
    return ic


def shrunk_ic_weights(
    ic_history: pd.DataFrame,
    prior: Mapping[str, float],
    shrinkage: float = 0.5,
    min_periods: int = 12,
    lookback: int | None = None,
    asof: pd.Timestamp | str | None = None,
    embargo: int | None = None,
    horizon: int | None = None,
    lag: int | None = None,
    calendar: pd.DatetimeIndex | None = None,
) -> pd.Series:
    """Poids de combinaison ∝ IR d'IC, rétrécis vers un a priori, sans anticipation.

    ``IR_k = mean(IC_k) / sd(IC_k)`` (Qian, Hua & Sorensen, 2007) ;
    ``w_IC,k = max(IR_k, 0) / Σ_j max(IR_j, 0)`` ;
    ``w = (1 - s) · w_IC + s · w_prior``, poids négatifs tronqués à 0 puis
    renormalisés à une somme de 1.

    Le rétrécissement vers l'a priori (James & Stein, 1961 ; DeMiguel et al.,
    2009 pour la robustesse des pondérations naïves) limite le sur-ajustement
    à un historique d'IC court et bruité, typique d'un marché de 48 titres.
    Un signal avec moins de ``min_periods`` IC observés a ``IR = 0`` ; si
    aucun IR n'est positif, ``w = w_prior``. L'a priori est tronqué à 0 et
    normalisé (équipondération s'il est nul).

    Absence d'anticipation : l'IC daté ``d`` dépend des rendements jusqu'à
    ``d + lag + h``. Pour décider en ``asof`` (par défaut : dernière date de
    l'historique), seuls les IC datés au plus tard ``E`` séances avant
    ``asof`` sont utilisés, avec ``E = embargo`` ou, par défaut,
    ``E = lag + horizon`` (22 séances pour ``h = 21``, ``lag = 1``).

    Parameters
    ----------
    ic_history
        IC par date (lignes, triées) et par signal (colonnes), daté comme
        :func:`information_coefficient` (date du signal).
    prior
        Poids a priori par signal.
    shrinkage
        ``s ∈ [0, 1]`` (1 : a priori seul ; 0 : IC seuls).
    lookback
        Si fourni, seules les ``lookback`` dernières lignes utilisables.
    asof
        Date de décision ; ``None`` : dernière ligne de ``ic_history``.
    embargo
        Embargo en séances ; ``None`` (défaut) : ``lag + horizon``.
    horizon, lag
        Paramètres de :func:`forward_returns` ayant servi aux IC (défauts
        ``21`` et ``1``). Les préciser interdit un ``embargo`` plus court.
    calendar
        Calendrier des séances, pour compter l'embargo en séances lorsque
        l'historique d'IC est sous-échantillonné (par ex. IC mensuels) ;
        sinon l'embargo est compté en lignes (prudent dans ce cas).
    """
    _check_ic_args(shrinkage, lookback)
    emb = _resolve_embargo(embargo, horizon, lag)
    ic = _sorted_ic(ic_history)
    if len(ic):
        decision = pd.Index([ic.index[-1] if asof is None else pd.Timestamp(asof)])
        last = int(_last_usable_rows(ic.index, decision, emb, calendar)[0])
        ic = ic.iloc[: max(last + 1, 0)]
    if lookback is not None:
        ic = ic.iloc[-lookback:]
    names = list(dict.fromkeys([*prior.keys(), *ic.columns]))
    if not names:
        raise ValueError("aucun signal (prior et ic_history vides)")
    p = _normalized_prior(prior, names)
    mean = ic.mean()
    sd = ic.std(ddof=1)
    cnt = ic.count()
    ir = (mean / sd).where((cnt >= min_periods) & (sd > _EPS), 0.0)
    return _shrink(ir, p, shrinkage).rename("weight")


def rolling_ic_weights(
    ic_history: pd.DataFrame,
    prior: Mapping[str, float],
    shrinkage: float = 0.5,
    min_periods: int = 12,
    lookback: int | None = None,
    embargo: int | None = None,
    horizon: int | None = None,
    lag: int | None = None,
    calendar: pd.DatetimeIndex | None = None,
) -> pd.DataFrame:
    """Poids :func:`shrunk_ic_weights` recalculés à chaque date, sans anticipation.

    La ligne ``t`` n'utilise que les IC des lignes ``<= t - E`` (fenêtre
    glissante de ``lookback`` lignes, ou expansive), ``E = embargo`` ou, par
    défaut, ``E = lag + horizon`` ; avec ``calendar``, ``E`` est compté en
    séances (voir :func:`shrunk_ic_weights`). La ligne ``t`` est identique à
    ``shrunk_ic_weights(..., asof=t)``. Avant que ``min_periods`` IC soient
    utilisables, les poids valent l'a priori.
    """
    _check_ic_args(shrinkage, lookback)
    emb = _resolve_embargo(embargo, horizon, lag)
    ic = _sorted_ic(ic_history)
    names = list(dict.fromkeys([*prior.keys(), *ic.columns]))
    p = _normalized_prior(prior, names)
    ic = ic.reindex(columns=names)
    roll = ic.rolling(lookback, min_periods=1) if lookback is not None else ic.expanding(min_periods=1)
    last = _last_usable_rows(ic.index, ic.index, emb, calendar)[:, None]
    last = np.broadcast_to(last, ic.shape)

    def _at_cutoff(stat: pd.DataFrame) -> np.ndarray:
        arr = stat.to_numpy(dtype=float)
        return np.where(last >= 0, np.take_along_axis(arr, np.clip(last, 0, None), axis=0), np.nan)

    mean = _at_cutoff(roll.mean())
    sd = _at_cutoff(roll.std(ddof=1))
    cnt = np.nan_to_num(_at_cutoff(roll.count()), nan=0.0)
    with np.errstate(invalid="ignore", divide="ignore"):
        ir = np.where((cnt >= min_periods) & (sd > _EPS), mean / sd, 0.0)
    IR = np.clip(np.nan_to_num(ir, nan=0.0), 0.0, None)
    tot = IR.sum(axis=1, keepdims=True)
    prior_row = p.to_numpy(dtype=float)[None, :]
    with np.errstate(invalid="ignore", divide="ignore"):
        w_ic = np.where(tot > 0, IR / tot, prior_row)
    w = np.clip((1.0 - shrinkage) * w_ic + shrinkage * prior_row, 0.0, None)
    w = w / w.sum(axis=1, keepdims=True)
    return pd.DataFrame(w, index=ic.index, columns=names)


# ===========================================================================
# Score composite de la stratégie v1 (SPECIFICATION_STRATEGIE.md §3.1.6, §3.2, §3.4, §5.2)
# ===========================================================================

#: Poids pré-enregistrés des variantes (§3.4, §11 ``weights.*``, §12.1 ``composite``).
#: D = poids de A, avec EP et DY classés à l'intérieur des secteurs (voir
#: :data:`VARIANT_SECTOR_NEUTRAL`). E, F, G et H réutilisent le score de A (surcouches de
#: portefeuille) : ils ne figurent pas ici.
VARIANT_WEIGHTS: dict[str, dict[str, float]] = {
    "A": {"ep": 0.15, "dy": 0.20, "mom6_1": 0.35, "lowvol": 0.20, "quality_proxy": 0.10},
    "B": {"ep": 0.25, "dy": 0.25, "mom6_1": 0.50},
    "C": {"ep": 0.15, "dy": 0.20, "mom6_1": 0.20, "mom12_1": 0.15, "lowvol": 0.20, "quality_proxy": 0.10},
    "D": {"ep": 0.15, "dy": 0.20, "mom6_1": 0.35, "lowvol": 0.20, "quality_proxy": 0.10},
}

#: Blocs classés à l'intérieur des secteurs (variante D : value neutralisée par secteur).
VARIANT_SECTOR_NEUTRAL: dict[str, tuple[str, ...]] = {"D": ("ep", "dy")}

#: Blocs du « bloc momentum » soumis aux modulateurs (dosage par la volatilité, filtre
#: de crash). Dans C, le bloc momentum (0,35) est formé de MOM6_1 (0,20) et MOM12_1 (0,15) :
#: les deux sont modulés (choix documenté, la spécification ne décrit les modulateurs
#: que pour A).
MOMENTUM_BLOCKS: tuple[str, ...] = ("mom6_1", "mom12_1")

#: Taille minimale d'un secteur pour être classé à part (variante D) ; les autres sont regroupés.
MIN_SECTOR_SIZE: int = 4
_POOLED_SECTOR = "__autres__"


def variant_weights(code: str) -> dict[str, float]:
    """Poids d'une variante pré-enregistrée (copie) ; ``KeyError`` si le code est inconnu."""
    key = str(code).upper()
    if key not in VARIANT_WEIGHTS:
        raise KeyError(f"variante inconnue {code!r} ; choix : {sorted(VARIANT_WEIGHTS)}")
    return dict(VARIANT_WEIGHTS[key])


def _truthy(x: pd.DataFrame | pd.Series) -> pd.DataFrame | pd.Series:
    """Booléens tels quels ; nombres (par ex. poids détenus) : ``> 0`` ; autres : ``== True``."""
    dtypes = [x.dtype] if isinstance(x, pd.Series) else list(x.dtypes)
    if dtypes and all(pd.api.types.is_numeric_dtype(d) and not pd.api.types.is_bool_dtype(d) for d in dtypes):
        return x.gt(0)
    return x.eq(True)


def _bool_like(mask: pd.DataFrame | pd.Series | None, like: pd.DataFrame) -> pd.DataFrame | None:
    """Masque booléen aligné sur ``like`` (``Series`` : même masque à toutes les dates)."""
    if mask is None:
        return None
    if isinstance(mask, pd.Series):
        vals = _truthy(mask.reindex(like.columns)).to_numpy(dtype=bool)
        return pd.DataFrame(np.broadcast_to(vals[None, :], like.shape), index=like.index, columns=like.columns)
    return _truthy(mask.reindex(index=like.index, columns=like.columns)).astype(bool)


def _sector_groups(sectors: pd.Series | pd.DataFrame, member: pd.DataFrame, min_size: int) -> pd.DataFrame:
    """Libellés de groupe date × symbole : secteurs d'au moins ``min_size`` membres, sinon regroupés."""
    g = _group_labels(sectors, member)
    g = g.where(member, _NA_GROUP)
    out = g.copy()
    for label in pd.unique(g.to_numpy().ravel()):
        if label == _NA_GROUP:
            continue
        in_g = g.eq(label) & member
        cnt = in_g.sum(axis=1).to_numpy()
        small = in_g & np.broadcast_to((cnt < min_size)[:, None], in_g.shape)
        out = out.mask(small, _POOLED_SECTOR)
    # Sans secteur connu : groupe regroupé.
    return out.mask(member & g.eq(_NA_GROUP), _POOLED_SECTOR)


def rank_gauss_z(
    df: pd.DataFrame,
    universe: pd.DataFrame | pd.Series | None = None,
    winsor_pct: tuple[float, float] | None = (1.0, 99.0),
    clip: float | None = 3.0,
    missing: float | None = 0.0,
    groups: pd.Series | pd.DataFrame | None = None,
    min_group_size: int = MIN_SECTOR_SIZE,
) -> pd.DataFrame:
    """Transformation transversale de la spécification (§3.1.6), date par date.

    Sur l'univers éligible ``U_t`` (masque booléen ; défaut : titres observés) :

    (a) winsorisation des valeurs brutes aux centiles ``winsor_pct`` (1 et 99,
        interpolation linéaire) ;
    (b) ``z = Φ⁻¹((rang - 0,5) / N)`` (rang moyen des ex aequo, ``N`` titres observés),
        écrêté à ``±clip`` (3) ;
    (c) valeur manquante d'un titre de l'univers -> ``z = missing`` (0) ; hors univers :
        NaN.

    Avec ``groups`` (secteurs : ``Series`` statique ou panel point-in-time), les rangs
    sont calculés **à l'intérieur** de chaque groupe ; les groupes de moins de
    ``min_group_size`` membres de l'univers à la date ``t`` sont regroupés (variante
    D). Note : la formule diffère de ``cross_sectional_zscore(method="rank_gauss")``
    (positions de Blom) ; c'est celle de la spécification.
    """
    x = _finite(df)
    member = _bool_like(universe, x)
    member = x.notna() if member is None else member
    xv = x.where(member)
    if winsor_pct is not None:
        lo_p, hi_p = winsor_pct
        if not 0.0 <= lo_p < hi_p <= 100.0:
            raise ValueError("winsor_pct doit vérifier 0 <= bas < haut <= 100")
        arr = xv.to_numpy(dtype=float)
        has = np.isfinite(arr).any(axis=1)
        lo = np.full(len(arr), np.nan)
        hi = np.full(len(arr), np.nan)
        if has.any():
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                lo[has] = np.nanpercentile(arr[has], lo_p, axis=1)
                hi[has] = np.nanpercentile(arr[has], hi_p, axis=1)
        xv = xv.clip(lower=pd.Series(lo, index=xv.index), upper=pd.Series(hi, index=xv.index), axis=0)
    if groups is None:
        labels = None
    else:
        labels = _sector_groups(groups, member, int(min_group_size))
    z = np.full(x.shape, np.nan)
    blocks = [None] if labels is None else [g for g in pd.unique(labels.to_numpy().ravel()) if g != _NA_GROUP]
    for label in blocks:
        sub = xv if label is None or labels is None else xv.where(labels.eq(label))
        ranks = sub.rank(axis=1, method="average").to_numpy(dtype=float)
        n = sub.notna().sum(axis=1).to_numpy(dtype=float)
        with np.errstate(invalid="ignore", divide="ignore"):
            zz = ndtri((ranks - 0.5) / n[:, None])
        ok = np.isfinite(ranks)
        z[ok] = zz[ok]
    if clip is not None:
        z = np.clip(z, -clip, clip)
    out = pd.DataFrame(z, index=x.index, columns=x.columns)
    if missing is not None:
        out = out.mask(member & out.isna(), float(missing))
    return out.where(member)


def s2_penalty_panel(
    ex_dates: pd.DataFrame,
    calendar: pd.DatetimeIndex | pd.Index,
    sessions: int = 20,
    penalty: float = -0.5,
    symbols: Sequence[str] | None = None,
    start_offset: int = 0,
) -> pd.DataFrame:
    """Malus S2 après détachement (§5.2 n° 5), en écarts-types du score.

    Pour chaque date ex ``e`` (première séance ``>= e`` du calendrier, position
    ``p``), les séances ``p + start_offset, …, p + start_offset + sessions - 1``
    reçoivent ``penalty`` (-0,5), 0 ailleurs ; les fenêtres qui se chevauchent ne se
    cumulent pas. Avec ``start_offset = 0`` (défaut), un signal daté du jour ex à
    ``e + 19`` séances, exécuté en ``t + 1``, couvre les achats de ``e + 1`` à
    ``e + 20`` : la fenêtre ``CAR[+1, +20]`` mesurée (−2,54 %, revue 07). La date ex
    est connue en ``t >= e`` (ligne (d) publiée la veille) : aucune anticipation.

    Le malus ne vise que les **nouveaux achats** : ``composite_score(..., held=…)``
    l'ignore pour les titres détenus (aucune vente forcée).

    Parameters
    ----------
    ex_dates
        Table longue (colonnes ``symbol`` et ``ex_date``, par ex. ``dividends.parquet``)
        ou panel large booléen (``True`` le jour ex).
    calendar
        Séances (index du panel de signaux).
    """
    if sessions < 1:
        raise ValueError("sessions doit être >= 1")
    cal = pd.DatetimeIndex(calendar).unique().sort_values()
    if {"symbol", "ex_date"} <= set(ex_dates.columns):
        ev = ex_dates[["symbol", "ex_date"]].dropna()
        ev = ev.assign(ex_date=pd.to_datetime(ev["ex_date"]))
    else:
        if not isinstance(ex_dates.index, pd.DatetimeIndex):
            raise TypeError("ex_dates : table (symbol, ex_date) ou panel booléen indexé par date")
        rows, cols_ = np.nonzero(ex_dates.eq(True).to_numpy())
        ev = pd.DataFrame({"symbol": ex_dates.columns[cols_].astype(str), "ex_date": ex_dates.index[rows]})
    cols = list(symbols) if symbols is not None else sorted(pd.unique(ev["symbol"].astype(str)))
    out = np.zeros((len(cal), len(cols)))
    pos_of = {s: j for j, s in enumerate(cols)}
    for sym, e in zip(ev["symbol"].astype(str), ev["ex_date"], strict=False):
        j = pos_of.get(sym)
        if j is None:
            continue
        p = int(cal.searchsorted(pd.Timestamp(e), side="left")) + int(start_offset)
        lo, hi = max(p, 0), min(p + sessions, len(cal))
        if lo < hi:
            out[lo:hi, j] = np.minimum(out[lo:hi, j], penalty) if penalty < 0 else np.maximum(out[lo:hi, j], penalty)
    return pd.DataFrame(out, index=cal, columns=pd.Index(cols, name="symbol"))


def modulate_weights(
    weights: Mapping[str, float],
    multiplier: pd.Series | float | None,
    momentum_blocks: Sequence[str] = MOMENTUM_BLOCKS,
) -> pd.DataFrame | dict[str, float]:
    """Poids modulés du momentum, poids libéré redistribué au prorata (§3.2).

    ``w_mom,t = w_mom · m_t`` pour chaque bloc momentum présent ; le poids libéré
    ``Σ w_mom · (1 - m_t)`` est réparti sur les autres blocs au prorata de leurs poids :
    ``w_b,t = w_b · (1 + libéré_t / Σ_autres w)``. La somme des poids est conservée.
    ``multiplier`` : nombre (renvoie un dict) ou série datée (renvoie un DataFrame date
    × bloc) ; ``None`` : poids inchangés. ``m_t`` doit être dans ``[0, 1]``.
    """
    w = {k: float(v) for k, v in weights.items()}
    mom = [k for k in w if k in momentum_blocks and w[k] != 0]
    other = [k for k in w if k not in mom]
    other_sum = sum(w[k] for k in other)
    if multiplier is None or not mom:
        if isinstance(multiplier, pd.Series):
            return pd.DataFrame({k: np.full(len(multiplier), v) for k, v in w.items()}, index=multiplier.index)
        return dict(w)
    if other and other_sum <= 0:
        raise ValueError("impossible de redistribuer : somme des poids hors momentum <= 0")
    m = pd.to_numeric(multiplier, errors="coerce") if isinstance(multiplier, pd.Series) else float(multiplier)
    if isinstance(m, pd.Series):
        m = m.astype(float).fillna(1.0)
        if ((m < 0) | (m > 1)).any():
            raise ValueError("le multiplicateur du momentum doit être dans [0, 1]")
    elif not 0.0 <= m <= 1.0:
        raise ValueError("le multiplicateur du momentum doit être dans [0, 1]")
    freed = sum(w[k] for k in mom) * (1.0 - m)
    res: dict[str, Any] = {}
    for k, wk in w.items():
        if k in mom:
            res[k] = wk * m
        elif other:
            res[k] = wk * (1.0 + freed / other_sum)
        else:
            res[k] = wk
    if not other:  # aucun bloc pour recevoir le poids libéré : il est perdu (documenté)
        warnings.warn("modulate_weights : aucun bloc hors momentum, le poids libéré n'est pas redistribué",
                      stacklevel=2)
    if isinstance(m, pd.Series):
        return pd.DataFrame({k: (v if isinstance(v, pd.Series) else pd.Series(v, index=m.index))
                             for k, v in res.items()}, index=m.index)
    return {k: float(v) for k, v in res.items()}


@dataclass
class CompositeResult:
    """Détail du score composite (voir :func:`composite_score`)."""

    score: pd.DataFrame  # score final, re-standardisé en rang (z de rang gaussien)
    raw: pd.DataFrame  # S = Σ w_b z_b (0 si moins de min_blocks blocs valides)
    with_malus: pd.DataFrame  # S + malus S2 (en écarts-types de S), avant re-standardisation
    z: dict[str, pd.DataFrame] = field(default_factory=dict)  # z par bloc (manquant = 0)
    n_valid: pd.DataFrame | None = None  # nombre de blocs valides par titre
    weights: pd.DataFrame | None = None  # poids effectifs date × bloc
    malus: pd.DataFrame | None = None  # malus appliqué (écarts-types), 0 pour les titres détenus


def composite_score(
    blocks: Mapping[str, pd.DataFrame],
    weights: Mapping[str, float] | pd.DataFrame | str = "A",
    min_blocks: int = 3,
    s2_malus: pd.DataFrame | None = None,
    *,
    universe: pd.DataFrame | pd.Series | None = None,
    held: pd.DataFrame | pd.Series | None = None,
    momentum_multiplier: pd.Series | float | None = None,
    momentum_blocks: Sequence[str] = MOMENTUM_BLOCKS,
    sector_neutral: Sequence[str] | None = None,
    sectors: pd.Series | pd.DataFrame | None = None,
    min_sector_size: int = MIN_SECTOR_SIZE,
    winsor_pct: tuple[float, float] | None = (1.0, 99.0),
    clip: float | None = 3.0,
    missing: float = 0.0,
    s2_units: Literal["sd", "raw"] = "sd",
    params: Mapping[str, Any] | None = None,
    return_details: bool = False,
) -> pd.DataFrame | CompositeResult:
    """Score composite v1 (§3.2) : ``S = Σ_b w_b z_b``, malus S2, re-standardisation en rang.

    1. Chaque bloc brut (orienté « élevé = attractif ») est transformé par
       :func:`rank_gauss_z` sur l'univers éligible ``universe`` (winsorisation 1-99,
       ``Φ⁻¹((rang - 0,5)/N)``, écrêtage ±3, manquant -> 0). Blocs de
       ``sector_neutral`` (variante D : ``ep``, ``dy``) : rangs à l'intérieur des
       secteurs d'au moins ``min_sector_size`` (4) titres, les autres regroupés.
    2. ``S_i,t = Σ_b w_b,t z_b,i,t`` ; ``S = 0`` (neutre) si moins de ``min_blocks``
       (3) blocs de poids non nul sont valides (valeur brute observée) pour le titre.
    3. Poids : dict, code de variante (``"A"``…``"D"``, :data:`VARIANT_WEIGHTS`) ou
       DataFrame date × bloc. ``momentum_multiplier`` (``features.vol_scaling`` ×
       ``features.crash_filter``) module les blocs momentum ; le poids libéré est
       redistribué au prorata (:func:`modulate_weights`).
    4. Malus S2 (``s2_malus``, par ex. :func:`s2_penalty_panel`, en écarts-types) :
       ``S' = S + malus · sd_t(S)`` (``s2_units="sd"`` : écart-type transversal de S sur
       l'univers ; ``"raw"`` : ajout tel quel), **sauf** pour les titres détenus
       (``held`` : masque booléen, ou poids détenus ``> 0``, panel ou ``Series``). Sans
       ``held``, le malus s'applique à tous les titres : à n'utiliser que pour des
       décisions d'achat.
    5. ``S'`` est re-standardisé en rang (:func:`rank_gauss_z`, sans winsorisation).

    Entrées : panels date × symbole, ou ``Series`` (une seule coupe transversale : le
    score est alors une ``Series`` et ``momentum_multiplier`` un nombre). Hors univers :
    NaN. ``params`` : clés ``winsor_pct``, ``clip``, ``missing``,
    ``min_valid_blocks`` (alias de ``min_blocks``), ``min_sector_size``. Aucune
    information postérieure à ``t`` n'est utilisée (opérations date par date).
    """
    a: dict[str, Any] = {"winsor_pct": winsor_pct, "clip": clip, "missing": missing, "min_blocks": min_blocks,
                         "min_sector_size": min_sector_size}
    for k, v in (params or {}).items():
        k = {"min_valid_blocks": "min_blocks"}.get(k, k)
        if k in a:
            a[k] = v
    if a["winsor_pct"] is not None:
        a["winsor_pct"] = (float(a["winsor_pct"][0]), float(a["winsor_pct"][1]))
    w_static: Mapping[str, float] | None
    if isinstance(weights, str):
        w_static = variant_weights(weights)
        if sector_neutral is None:
            sector_neutral = VARIANT_SECTOR_NEUTRAL.get(weights.upper(), ())
    elif isinstance(weights, pd.DataFrame):
        w_static = None
    else:
        w_static = {k: float(v) for k, v in weights.items()}
    sector_neutral = tuple(sector_neutral or ())
    if sector_neutral and sectors is None:
        raise ValueError("sector_neutral exige sectors (Series symbole -> secteur ou panel daté)")
    names = list(weights.columns) if isinstance(weights, pd.DataFrame) else list(w_static or {})
    active = [k for k in names if (w_static is None or w_static[k] != 0)]
    missing_blocks = [k for k in active if k not in blocks]
    if missing_blocks:
        raise KeyError(f"blocs absents pour des poids non nuls : {missing_blocks}")
    if not active:
        raise ValueError("aucun poids non nul")

    single = all(isinstance(blocks[k], pd.Series) for k in active)
    if single:
        if isinstance(momentum_multiplier, pd.Series):
            raise ValueError("coupe unique (Series) : momentum_multiplier doit être un nombre")
        key = pd.Index([0])
        frames = {k: _finite(pd.DataFrame([blocks[k].to_numpy()], index=key, columns=blocks[k].index))
                  for k in active}
        if isinstance(s2_malus, pd.Series):
            s2_malus = pd.DataFrame([s2_malus.to_numpy()], index=key, columns=s2_malus.index)
    else:
        frames = {k: _finite(_as_frame(blocks[k])[0]) for k in active}
    index, columns = frames[active[0]].index, frames[active[0]].columns
    for k in active[1:]:
        index, columns = index.union(frames[k].index), columns.union(frames[k].columns)
    if isinstance(universe, pd.DataFrame):
        index, columns = index.union(universe.index), columns.union(universe.columns)
    frames = {k: f.reindex(index=index, columns=columns) for k, f in frames.items()}
    like = pd.DataFrame(index=index, columns=columns, dtype=float)
    member = _bool_like(universe, like)
    if member is None:
        member = pd.DataFrame(False, index=index, columns=columns)
        for f in frames.values():
            member |= f.notna()

    if isinstance(weights, pd.DataFrame):
        W = weights.reindex(index=index).ffill()[active].astype(float)
        if momentum_multiplier is not None:
            raise ValueError("momentum_multiplier ne se combine pas avec des poids datés (DataFrame)")
    else:
        mult = momentum_multiplier
        if isinstance(mult, pd.Series):
            mult = pd.to_numeric(mult, errors="coerce").astype(float)
            mult = mult.reindex(mult.index.union(index)).ffill().reindex(index).fillna(1.0)
        mod = modulate_weights(w_static or {}, mult, momentum_blocks)
        if isinstance(mod, pd.DataFrame):
            W = mod[active]
        else:
            W = pd.DataFrame({k: np.full(len(index), mod[k]) for k in active}, index=index)

    z: dict[str, pd.DataFrame] = {}
    n_valid = np.zeros((len(index), len(columns)))
    S = np.zeros((len(index), len(columns)))
    for k in active:
        grp = sectors if k in sector_neutral else None
        zk = rank_gauss_z(frames[k], universe=member, winsor_pct=a["winsor_pct"], clip=a["clip"],
                          missing=a["missing"], groups=grp, min_group_size=int(a["min_sector_size"]))
        z[k] = zk
        wk = W[k].to_numpy(dtype=float)[:, None]
        n_valid += ((frames[k].notna() & member).to_numpy()) * (wk != 0)
        S += np.nan_to_num(zk.to_numpy(dtype=float), nan=0.0) * wk
    mem = member.to_numpy(dtype=bool)
    S = np.where(n_valid >= int(a["min_blocks"]), S, 0.0)
    S = np.where(mem, S, np.nan)
    raw = pd.DataFrame(S, index=index, columns=columns)

    malus_df = None
    S2 = raw.copy()
    if s2_malus is not None:
        mal = _finite(s2_malus).reindex(index=index, columns=columns).fillna(0.0)
        hmask = _bool_like(held, like)
        if hmask is not None:
            mal = mal.mask(hmask, 0.0)
        mal = mal.where(member, 0.0)
        if s2_units == "sd":
            sd = raw.std(axis=1, ddof=1).fillna(0.0)
            S2 = raw + mal.mul(sd, axis=0)
        elif s2_units == "raw":
            S2 = raw + mal
        else:
            raise ValueError("s2_units doit valoir 'sd' ou 'raw'")
        malus_df = mal
    score = rank_gauss_z(S2, universe=member, winsor_pct=None, clip=a["clip"], missing=a["missing"])
    if not return_details:
        return score.iloc[0] if single else score
    return CompositeResult(
        score=score, raw=raw, with_malus=S2, z=z,
        n_valid=pd.DataFrame(n_valid, index=index, columns=columns).where(member),
        weights=W, malus=malus_df,
    )
