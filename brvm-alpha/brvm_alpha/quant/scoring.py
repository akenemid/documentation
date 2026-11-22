"""Normalisation transversale, neutralisation, composites et évaluation des signaux.

Toutes les opérations « transversales » travaillent **date par date** (une
ligne du panel = une coupe transversale) : la valeur en ``t`` ne dépend que
de la ligne ``t``. Elles n'introduisent donc aucun biais d'anticipation. Les
seules fonctions tournées vers le futur sont :func:`forward_returns` (cible
d'évaluation, jamais une caractéristique) et, par construction, l'IC et les
rendements par quantile qui l'utilisent ; :func:`shrunk_ic_weights` et
:func:`rolling_ic_weights` appliquent un embargo pour que les poids en ``t``
ne reposent que sur des IC **déjà observables** en ``t``.

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
* Qian, E., Hua, R. & Sorensen, E. (2007). *Quantitative Equity Portfolio
  Management*. Chapman & Hall/CRC (pondération des facteurs par ``IC/σ(IC)``).
* Spearman, C. (1904). The Proof and Measurement of Association between Two
  Things. *American Journal of Psychology*, 15(1), 72-101.
"""

from __future__ import annotations

import warnings
from collections.abc import Mapping
from typing import Literal, TypeAlias, overload

import numpy as np
import pandas as pd
from scipy.special import ndtri

__all__ = [
    "combine",
    "cross_sectional_zscore",
    "forward_returns",
    "information_coefficient",
    "neutralize",
    "quantile_returns",
    "rolling_ic_weights",
    "shrunk_ic_weights",
]

Frame: TypeAlias = pd.DataFrame
ZMethod: TypeAlias = Literal["rank_gauss", "zscore", "robust"]

_POOL = "__autres__"
_NA_GROUP = "__sans_groupe__"
_EPS = 1e-14


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


@overload
def cross_sectional_zscore(
    df: pd.DataFrame, winsor: float | None = ..., method: ZMethod = ..., min_obs: int = ...
) -> pd.DataFrame: ...
@overload
def cross_sectional_zscore(
    df: pd.Series, winsor: float | None = ..., method: ZMethod = ..., min_obs: int = ...
) -> pd.Series: ...


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
      et ``μ, σ`` sont recalculés (au plus 50 passes) ; puis
      ``z = (x_w - mean(x_w)) / sd(x_w)`` (ddof = 1), d'où une moyenne nulle et
      un écart-type unitaire exacts.
    * ``"robust"`` : ``z = (x - médiane) / (1,4826 · MAD)``, puis borné à ``±w``.

    ``winsor`` borne aussi le résultat final de ``"rank_gauss"`` et
    ``"robust"`` (``None`` : pas de borne). Une ligne de moins de ``min_obs``
    valeurs observées donne NaN ; une ligne sans dispersion donne 0. Les NaN
    restent NaN.

    Parameters
    ----------
    df
        Panel large date × symbole, ou ``Series`` (une seule coupe).
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
            for _ in range(50):
                mu, sd, _n = _row_mean_sd(x)
                lo = (mu - winsor * sd)[:, None]
                hi = (mu + winsor * sd)[:, None]
                with np.errstate(invalid="ignore"):
                    out_of = ok & np.isfinite(lo) & ((x < lo - _EPS) | (x > hi + _EPS))
                if not out_of.any():
                    break
                x = np.where(out_of, np.clip(x, lo, hi), x)
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

    Les symboles sans groupe forment le groupe ``"__sans_groupe__"``. Avec
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
    tr_index: pd.DataFrame | pd.Series, horizon: int = 21, lag: int = 1
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


def shrunk_ic_weights(
    ic_history: pd.DataFrame,
    prior: Mapping[str, float],
    shrinkage: float = 0.5,
    min_periods: int = 12,
    lookback: int | None = None,
    asof: pd.Timestamp | str | None = None,
    embargo: int = 0,
) -> pd.Series:
    """Poids de combinaison ∝ IR d'IC, rétrécis vers un a priori.

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
    ``d + lag + h``. Pour décider en ``asof``, ne garder que les IC datés
    ``<= asof`` puis retirer les ``embargo >= lag + h`` dernières lignes.

    Parameters
    ----------
    ic_history
        IC par date (lignes) et par signal (colonnes).
    prior
        Poids a priori par signal.
    shrinkage
        ``s ∈ [0, 1]`` (1 : a priori seul ; 0 : IC seuls).
    lookback
        Si fourni, seules les ``lookback`` dernières lignes (après embargo).
    """
    if not 0.0 <= shrinkage <= 1.0:
        raise ValueError("shrinkage doit être dans [0, 1]")
    if embargo < 0:
        raise ValueError("embargo doit être >= 0")
    ic = _finite(ic_history)
    if asof is not None:
        ic = ic.loc[: pd.Timestamp(asof)]
    if embargo:
        ic = ic.iloc[: max(len(ic) - embargo, 0)]
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
    embargo: int = 0,
) -> pd.DataFrame:
    """Poids :func:`shrunk_ic_weights` recalculés à chaque date, sans anticipation.

    La ligne ``t`` n'utilise que les IC des lignes ``<= t - embargo``
    (fenêtre glissante de ``lookback`` lignes, ou expansive). Avant que
    ``min_periods`` IC soient disponibles, les poids valent l'a priori.
    """
    if not 0.0 <= shrinkage <= 1.0:
        raise ValueError("shrinkage doit être dans [0, 1]")
    ic = _finite(ic_history)
    names = list(dict.fromkeys([*prior.keys(), *ic.columns]))
    p = _normalized_prior(prior, names)
    ic = ic.reindex(columns=names)
    roll = ic.rolling(lookback, min_periods=1) if lookback else ic.expanding(min_periods=1)
    mean = roll.mean().shift(embargo)
    sd = roll.std(ddof=1).shift(embargo)
    cnt = roll.count().shift(embargo).fillna(0.0)
    ir = (mean / sd).where((cnt >= min_periods) & (sd > _EPS), 0.0).fillna(0.0).clip(lower=0.0)
    IR = ir.to_numpy(dtype=float)
    tot = IR.sum(axis=1, keepdims=True)
    prior_row = p.to_numpy(dtype=float)[None, :]
    with np.errstate(invalid="ignore", divide="ignore"):
        w_ic = np.where(tot > 0, IR / tot, prior_row)
    w = np.clip((1.0 - shrinkage) * w_ic + shrinkage * prior_row, 0.0, None)
    w = w / w.sum(axis=1, keepdims=True)
    return pd.DataFrame(w, index=ic.index, columns=names)
