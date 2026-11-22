"""Validation walk-forward et grilles de paramètres (entrée de la CSCV / PBO).

Deux outils complémentaires contre le sur-ajustement (« backtest
overfitting ») :

* :func:`walk_forward` — analyse *walk-forward* (Pardo, 2008) : on estime /
  calibre sur une fenêtre d'apprentissage, on applique sur la fenêtre de test
  qui suit, puis on avance. Seules les performances **hors échantillon**
  (concaténation des fenêtres de test) sont évaluées. Fenêtres
  **expansives** (l'apprentissage démarre toujours à la première date) ou
  **glissantes** (longueur fixe ``train_years``).

  *Embargo* : les ``h = embargo_days`` dernières séances précédant chaque
  fenêtre de test sont retirées de l'apprentissage. Si une étiquette
  d'apprentissage à la date ``s`` dépend des rendements de ``]s, s + h]``
  (rendement à terme sur ``h`` séances), alors pour toute date d'apprentissage
  conservée ``s ≤ τ − h − 1`` (``τ`` = première séance de test) l'étiquette ne
  dépend que de séances ``< τ`` : **aucun recouvrement d'information** entre
  apprentissage et test (« purging » et « embargo », López de Prado, 2018,
  ch. 7). Choisir ``embargo_days ≥`` horizon des étiquettes.

* :func:`run_param_grid` — exécute un backtest par configuration d'une grille
  et renvoie la matrice ``T × N`` des rendements quotidiens, entrée de
  ``brvm_alpha.quant.stats.pbo_cscv`` (Bailey, Borwein, López de Prado & Zhu,
  2017) et du Sharpe déflaté (Bailey & López de Prado, 2014) qui corrige du
  nombre ``N`` d'essais.

Références
----------
* Bailey, D. H. & López de Prado, M. (2014). The Deflated Sharpe Ratio.
  *Journal of Portfolio Management*, 40(5), 94-107.
* Bailey, D. H., Borwein, J., López de Prado, M. & Zhu, Q. J. (2017). The
  Probability of Backtest Overfitting. *Journal of Computational Finance*,
  20(4), 39-69.
* López de Prado, M. (2018). *Advances in Financial Machine Learning*.
  Wiley, ch. 7 (validation croisée purgée, embargo) et ch. 12.
* Pardo, R. (2008). *The Evaluation and Optimization of Trading
  Strategies*, 2ᵉ éd. Wiley, ch. 11 (walk-forward analysis).
* White, H. (2000). A Reality Check for Data Snooping. *Econometrica*,
  68(5), 1097-1126.
"""

from __future__ import annotations

import itertools
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

__all__ = [
    "WalkForwardFold",
    "WalkForwardResult",
    "WalkForwardWindow",
    "param_grid",
    "run_param_grid",
    "walk_forward",
    "walk_forward_windows",
]


# ---------------------------------------------------------------------------
# Fenêtres
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WalkForwardWindow:
    """Une fenêtre walk-forward : apprentissage, embargo, test (séances)."""

    fold: int
    train: pd.DatetimeIndex
    embargo: pd.DatetimeIndex
    test: pd.DatetimeIndex

    @property
    def train_start(self) -> pd.Timestamp:
        return self.train[0]

    @property
    def train_end(self) -> pd.Timestamp:
        return self.train[-1]

    @property
    def test_start(self) -> pd.Timestamp:
        return self.test[0]

    @property
    def test_end(self) -> pd.Timestamp:
        return self.test[-1]


def _as_calendar(dates: Any) -> pd.DatetimeIndex:
    if isinstance(dates, (pd.Series, pd.DataFrame)):
        dates = dates.index
    cal = pd.DatetimeIndex(pd.to_datetime(pd.Index(dates))).dropna().unique().sort_values()
    if len(cal) == 0:
        raise ValueError("calendrier vide")
    return cal


def walk_forward_windows(
    dates: Any,
    train_years: float,
    test_months: int,
    embargo_days: int = 0,
    *,
    expanding: bool = True,
    min_train_days: int = 1,
    allow_partial: bool = True,
) -> list[WalkForwardWindow]:
    """Découpe un calendrier en fenêtres walk-forward sans recouvrement.

    Ancrages calendaires (pas de dérive) : ``a_0 = d_0 + train_years`` puis
    ``a_{k+1} = a_k + test_months`` mois. La fenêtre de test ``k`` contient
    les séances de ``[a_k, a_{k+1}[`` ; les fenêtres de test sont donc
    disjointes et contiguës. Avec ``τ_k`` la première séance de test :

    * apprentissage expansif : séances de ``[d_0, τ_k[`` ;
    * apprentissage glissant : séances de ``[a_k − train_years, τ_k[`` ;

    privées de leurs ``embargo_days`` dernières séances (embargo).

    Parameters
    ----------
    dates
        Séances (``DatetimeIndex``, liste, ou objet pandas dont l'index est
        utilisé).
    train_years
        Longueur (années, éventuellement fractionnaire : arrondi au mois) de
        l'apprentissage initial, et de chaque apprentissage si glissant.
    test_months
        Longueur (mois) de chaque fenêtre de test (≥ 1).
    embargo_days
        Séances retirées entre apprentissage et test (≥ 0).
    expanding
        ``True`` : fenêtres expansives ; ``False`` : glissantes.
    min_train_days
        Fenêtres dont l'apprentissage compte moins de séances ignorées.
    allow_partial
        Conserver la dernière fenêtre de test si les données s'arrêtent avant
        sa fin calendaire.

    Returns
    -------
    list[WalkForwardWindow]
    """
    cal = _as_calendar(dates)
    train_m = round(float(train_years) * 12)
    if train_m < 1:
        raise ValueError("train_years doit couvrir au moins un mois")
    if int(test_months) < 1:
        raise ValueError("test_months doit être >= 1")
    if int(embargo_days) < 0:
        raise ValueError("embargo_days doit être >= 0")
    if int(min_train_days) < 1:
        raise ValueError("min_train_days doit être >= 1")
    emb = int(embargo_days)
    train_off = pd.DateOffset(months=train_m)
    test_off = pd.DateOffset(months=int(test_months))

    out: list[WalkForwardWindow] = []
    d0 = cal[0]
    anchor = d0 + train_off
    fold = 0
    while anchor <= cal[-1]:
        nxt = anchor + test_off
        lo = int(cal.searchsorted(anchor, side="left"))
        hi = int(cal.searchsorted(nxt, side="left"))
        complete = hi < len(cal)
        if hi > lo and (complete or allow_partial):
            train_lo = 0 if expanding else int(cal.searchsorted(anchor - train_off, side="left"))
            train_hi = max(train_lo, lo - emb)
            train = cal[train_lo:train_hi]
            if len(train) >= int(min_train_days):
                out.append(
                    WalkForwardWindow(
                        fold=fold,
                        train=train,
                        embargo=cal[train_hi:lo],
                        test=cal[lo:hi],
                    )
                )
                fold += 1
        anchor = nxt
    return out


# ---------------------------------------------------------------------------
# Walk-forward
# ---------------------------------------------------------------------------


@dataclass
class WalkForwardFold:
    """Fenêtre, modèle estimé sur l'apprentissage et sortie sur le test."""

    window: WalkForwardWindow
    model: Any
    output: Any


@dataclass
class WalkForwardResult:
    """Résultat d'une analyse walk-forward."""

    folds: list[WalkForwardFold] = field(default_factory=list)

    @property
    def windows(self) -> list[WalkForwardWindow]:
        return [f.window for f in self.folds]

    @property
    def models(self) -> list[Any]:
        return [f.model for f in self.folds]

    @property
    def oos(self) -> pd.Series | pd.DataFrame | list[Any]:
        """Sorties hors échantillon concaténées (``Series``/``DataFrame``), sinon liste."""
        outs = [f.output for f in self.folds]
        if outs and all(isinstance(o, (pd.Series, pd.DataFrame)) for o in outs):
            res = pd.concat(outs)
            return res.sort_index()
        return outs

    def summary(self) -> pd.DataFrame:
        """Tableau des fenêtres (dates, tailles, embargo)."""
        rows = [
            {
                "fold": w.fold,
                "train_start": w.train_start,
                "train_end": w.train_end,
                "n_train": len(w.train),
                "n_embargo": len(w.embargo),
                "test_start": w.test_start,
                "test_end": w.test_end,
                "n_test": len(w.test),
            }
            for w in self.windows
        ]
        return pd.DataFrame(
            rows,
            columns=["fold", "train_start", "train_end", "n_train", "n_embargo", "test_start", "test_end", "n_test"],
        )


def walk_forward(
    fit_fn: Callable[[pd.DatetimeIndex], Any],
    apply_fn: Callable[[Any, pd.DatetimeIndex], Any],
    dates: Any,
    train_years: float,
    test_months: int,
    embargo_days: int = 0,
    *,
    expanding: bool = True,
    min_train_days: int = 1,
    allow_partial: bool = True,
    clip_output: bool = True,
) -> WalkForwardResult:
    """Analyse walk-forward : ``fit`` sur l'apprentissage, ``apply`` sur le test.

    Pour chaque fenêtre ``k`` (:func:`walk_forward_windows`) :
    ``model_k = fit_fn(train_k)`` puis ``out_k = apply_fn(model_k, test_k)``.
    ``fit_fn`` ne reçoit que des séances strictement antérieures à
    ``τ_k − embargo`` ; c'est à lui de ne lire les données que sur ces dates.

    Parameters
    ----------
    fit_fn
        ``fit_fn(train_dates) -> modèle`` (p. ex. paramètres choisis par
        maximisation d'un Sharpe sur l'apprentissage).
    apply_fn
        ``apply_fn(modèle, test_dates) -> sortie`` (p. ex. ``Series`` des
        rendements quotidiens du backtest sur ``test_dates``).
    dates, train_years, test_months, embargo_days, expanding, min_train_days, allow_partial
        Voir :func:`walk_forward_windows`.
    clip_output
        Si la sortie est un objet pandas indexé par des dates, la restreindre
        à ``[test_start, test_end]`` (les sorties concaténées ne se
        recouvrent alors jamais).

    Returns
    -------
    WalkForwardResult
        ``folds`` (fenêtre, modèle, sortie), ``oos`` (sorties concaténées),
        ``summary()``.

    Examples
    --------
    Choix du paramètre sur l'apprentissage, application hors échantillon ::

        bt = Backtester(panels, costs, execution, taxes, capital)

        def fit(train):
            perf = run_param_grid(
                lambda lookback: bt.run(make_strategy(lookback), "M", start=train[0], end=train[-1]),
                {"lookback": [60, 120, 250]},
            )
            sharpe = perf.mean() / perf.std()
            return perf.attrs["params"][sharpe.idxmax()]

        def apply(params, test):
            return bt.run(make_strategy(**params), "M", start=test[0], end=test[-1]).returns

        wf = walk_forward(fit, apply, bt.dates, train_years=3, test_months=6, embargo_days=20)
        oos_returns = wf.oos  # à comparer au BRVM Composite Total Return
    """
    windows = walk_forward_windows(
        dates,
        train_years,
        test_months,
        embargo_days,
        expanding=expanding,
        min_train_days=min_train_days,
        allow_partial=allow_partial,
    )
    result = WalkForwardResult()
    for w in windows:
        model = fit_fn(w.train)
        out = apply_fn(model, w.test)
        if clip_output and isinstance(out, (pd.Series, pd.DataFrame)) and isinstance(out.index, pd.DatetimeIndex):
            out = out.loc[(out.index >= w.test_start) & (out.index <= w.test_end)]
        result.folds.append(WalkForwardFold(window=w, model=model, output=out))
    return result


# ---------------------------------------------------------------------------
# Grilles de paramètres
# ---------------------------------------------------------------------------


def param_grid(grid: Mapping[str, Sequence[Any]] | Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Développe une grille en liste de configurations.

    * ``dict`` nom → liste de valeurs : produit cartésien, dans l'ordre des
      clés (la dernière varie le plus vite) ;
    * liste de ``dict`` : configurations explicites, renvoyées telles quelles.
    """
    if isinstance(grid, Mapping):
        keys = list(grid)
        values = []
        for k in keys:
            v = grid[k]
            if isinstance(v, (str, bytes)) or not isinstance(v, Iterable):
                v = [v]
            values.append(list(v))
        return [dict(zip(keys, combo, strict=True)) for combo in itertools.product(*values)]
    configs = [dict(c) for c in grid]
    if not all(isinstance(c, dict) for c in configs):
        raise TypeError("grid : dict de listes ou liste de dict attendu")
    return configs


def _format_value(v: Any) -> str:
    if isinstance(v, float):
        return f"{v:g}"
    if callable(v) and hasattr(v, "__name__"):
        return str(v.__name__)
    return str(v)


def _label(params: Mapping[str, Any]) -> str:
    return "|".join(f"{k}={_format_value(v)}" for k, v in params.items()) or "default"


def _extract_returns(out: Any) -> pd.Series:
    """Rendements quotidiens d'un résultat de backtest (``BacktestResult`` ou ``Series``)."""
    if isinstance(out, pd.Series):
        return out.astype(float)
    if isinstance(out, pd.DataFrame):
        if out.shape[1] != 1:
            raise TypeError("backtest_fn : DataFrame à une seule colonne attendu")
        return out.iloc[:, 0].astype(float)
    rets = getattr(out, "returns", None)
    if isinstance(rets, pd.Series):
        return rets.astype(float)
    raise TypeError("backtest_fn doit renvoyer un BacktestResult ou une Series de rendements")


def run_param_grid(
    backtest_fn: Callable[..., Any],
    grid: Mapping[str, Sequence[Any]] | Sequence[Mapping[str, Any]],
    *,
    labels: Sequence[str] | None = None,
    how: str = "outer",
) -> pd.DataFrame:
    """Rendements quotidiens ``T × N`` de ``N`` configurations (entrée de ``pbo_cscv``).

    Chaque configuration ``θ`` de :func:`param_grid` est évaluée par
    ``backtest_fn(**θ)`` (exécution séquentielle, donc déterministe) ; la
    sortie doit être un ``BacktestResult`` (ou tout objet exposant
    ``.returns``) ou une ``Series`` de rendements.

    Parameters
    ----------
    backtest_fn
        Fonction de backtest paramétrée.
    grid
        ``dict`` nom → valeurs (produit cartésien) ou liste de ``dict``.
    labels
        Noms des colonnes (défaut ``"k1=v1|k2=v2"`` ; doublons suffixés).
    how
        ``"outer"`` (union des dates, NaN si absent) ou ``"inner"`` (dates
        communes à toutes les configurations, recommandé pour la CSCV).

    Returns
    -------
    pandas.DataFrame
        Index = séances triées, une colonne par configuration ;
        ``df.attrs["params"]`` associe chaque colonne à ses paramètres et
        ``df.attrs["n_trials"]`` vaut ``N`` (à reporter dans le Sharpe
        déflaté).
    """
    if how not in ("outer", "inner"):
        raise ValueError("how doit valoir 'outer' ou 'inner'")
    configs = param_grid(grid)
    if not configs:
        raise ValueError("grille vide")
    if labels is not None and len(labels) != len(configs):
        raise ValueError("labels : une étiquette par configuration")
    names: list[str] = []
    seen: dict[str, int] = {}
    for i, cfg in enumerate(configs):
        base = str(labels[i]) if labels is not None else _label(cfg)
        n = seen.get(base, 0)
        seen[base] = n + 1
        names.append(base if n == 0 else f"{base}#{n}")
    series: dict[str, pd.Series] = {}
    for name, cfg in zip(names, configs, strict=True):
        r = _extract_returns(backtest_fn(**cfg))
        if r.index.has_duplicates:
            raise ValueError(f"rendements avec dates en double pour {name}")
        series[name] = r
    frame = pd.concat(series, axis=1, join=how).sort_index()
    frame = frame[names]
    frame.attrs["params"] = dict(zip(names, configs, strict=True))
    frame.attrs["n_trials"] = len(names)
    if np.isinf(frame.to_numpy(dtype=float)).any():
        raise ValueError("rendements infinis dans la grille")
    return frame
