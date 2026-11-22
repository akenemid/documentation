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

Validation de la stratégie v1 (spécification §8)
------------------------------------------------

* :func:`purged_kfold` et :func:`cpcv` — validation croisée purgée avec
  embargo et validation croisée combinatoire purgée (10 groupes, ``k = 2``,
  45 découpages, 9 chemins ; purge et embargo de 21 séances) ;
* :class:`TrialRegistry` — registre persistant des essais
  (``reports/trials.parquet``) : 55 essais S0 « déclarés » et 8 variantes
  S1 « pré-enregistrées » au départ (``N = 63``) ; l'additif v1.1 (§8.4) y
  ajoute la variante I (``S1-I``), la référence « indice discipliné »
  (``REF-ID``, hors famille de la PBO) et les essais de diagnostic S0 déjà
  exécutés pendant la mise au point (essais de fumée de A, décision du
  20/11/2026), soit ``N ≥ 65 + diagnostics`` ; puis chaque essai exécuté avec
  ses rendements hebdomadaires nets (une relance motivée crée de **nouveaux**
  essais, D12) ;
* :func:`evaluate_status` — statut REJETÉ / CANDIDAT / INDÉTERMINÉ / PROMU
  selon les critères exacts du §8.3 et les filtres G1-G9, avec le détail
  critère par critère ; règle D7 de l'additif v1.1 pour le suivi réel S2 ;
* :func:`variant_promotion` — règle de promotion du §3.4 (N = 9 depuis
  l'additif v1.1).

L'échantillon S1 (2017-01-02 → 2022-11-16) est réservé à **un seul** test
pré-enregistré : aucun de ces outils ne l'exécute de lui-même.

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
import json
import math
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

__all__ = [
    "CPCVResult",
    "DEFAULT_REGISTRY_PATH",
    "FAMILY_V11",
    "N_TRIALS_START",
    "N_TRIALS_START_V11",
    "REFERENCE_TRIAL_ID",
    "REFERENCE_VARIANT",
    "RULES_VERSIONS",
    "PromotionReport",
    "PurgedSplit",
    "REGISTRY_COLUMNS",
    "STATUS_THRESHOLDS",
    "STATUT_CANDIDAT",
    "STATUT_DECLARE",
    "STATUT_EXECUTE",
    "STATUT_INDETERMINE",
    "STATUT_PREENREGISTRE",
    "STATUT_PROMU",
    "STATUT_REJETE",
    "S1_VARIANTS",
    "StatusReport",
    "TrialRegistry",
    "WalkForwardFold",
    "WalkForwardResult",
    "WalkForwardWindow",
    "cpcv",
    "declared_s0_diagnostic_trials",
    "declared_s0_trials",
    "evaluate_status",
    "param_grid",
    "preregistered_addendum_v11",
    "preregistered_s1_variants",
    "purged_kfold",
    "run_param_grid",
    "status_thresholds",
    "variant_promotion",
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


# ---------------------------------------------------------------------------
# Validation croisée purgée et CPCV (revue 04 §6 ; López de Prado, 2018)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PurgedSplit:
    """Un découpage apprentissage / test purgé et sous embargo.

    ``purged`` : séances d'apprentissage retirées **avant** chaque bloc de
    test (leur étiquette à ``h = purge`` séances chevauche le test) ;
    ``embargoed`` : séances retirées **après** chaque bloc de test (mémoire
    sérielle, ``embargo`` séances).
    """

    split: int
    test_groups: tuple[int, ...]
    train: pd.DatetimeIndex
    test: pd.DatetimeIndex
    purged: pd.DatetimeIndex
    embargoed: pd.DatetimeIndex


def _contiguous_runs(pos: np.ndarray) -> list[tuple[int, int]]:
    """Blocs contigus ``[début, fin]`` (inclus) d'un tableau de positions triées."""
    if pos.size == 0:
        return []
    breaks = np.flatnonzero(np.diff(pos) > 1)
    starts = np.r_[pos[0], pos[breaks + 1]]
    ends = np.r_[pos[breaks], pos[-1]]
    return [(int(a), int(b)) for a, b in zip(starts, ends, strict=True)]


def _purged_positions(n: int, test_pos: np.ndarray, purge: int, embargo: int) -> tuple[np.ndarray, ...]:
    """Positions (apprentissage, purgées, sous embargo) pour un ensemble de test."""
    is_test = np.zeros(n, dtype=bool)
    is_test[test_pos] = True
    purged = np.zeros(n, dtype=bool)
    embargoed = np.zeros(n, dtype=bool)
    for a, b in _contiguous_runs(np.sort(test_pos)):
        purged[max(0, a - purge) : a] = True
        embargoed[b + 1 : min(n, b + 1 + embargo)] = True
    purged &= ~is_test
    embargoed &= ~is_test & ~purged
    train = ~is_test & ~purged & ~embargoed
    return np.flatnonzero(train), np.flatnonzero(purged), np.flatnonzero(embargoed)


def _check_cv_args(n: int, n_groups: int, purge: int, embargo: int) -> None:
    if n_groups < 2:
        raise ValueError("au moins deux groupes sont nécessaires")
    if n < n_groups:
        raise ValueError("moins de séances que de groupes")
    if purge < 0 or embargo < 0:
        raise ValueError("purge et embargo doivent être >= 0")


def _split_groups(cal: pd.DatetimeIndex, n_groups: int) -> list[np.ndarray]:
    """``n_groups`` blocs chronologiques contigus de tailles quasi égales (``np.array_split``)."""
    return [np.asarray(g, dtype=np.int64) for g in np.array_split(np.arange(len(cal)), n_groups)]


def _check_train(splits: Sequence[PurgedSplit], min_train: int, what: str) -> None:
    """Refuse un découpage dont le jeu d'apprentissage est vide ou trop court."""
    if min_train < 1:
        raise ValueError("min_train doit être >= 1")
    short = [sp.split for sp in splits if len(sp.train) < int(min_train)]
    if short:
        sizes = sorted({len(sp.train) for sp in splits if sp.split in short})
        raise ValueError(
            f"{what} : {len(short)} découpage(s) avec moins de {int(min_train)} séance(s) d'apprentissage "
            f"(tailles {sizes[:5]}) ; calendrier trop court pour la purge et l'embargo")


def purged_kfold(
    dates: Any, n_splits: int = 10, purge: int = 21, embargo: int = 21, *, min_train: int = 1
) -> list[PurgedSplit]:
    """K-fold chronologique **purgé** avec **embargo** (López de Prado, 2018, ch. 7).

    Le calendrier est découpé en ``n_splits`` blocs contigus ; chaque bloc
    sert une fois de test. Sont retirées de l'apprentissage les ``purge``
    séances qui précèdent le test (étiquette à ``h = purge`` séances : 21
    pour un signal mensuel) et les ``embargo`` séances qui le suivent (21,
    mémoire mesurée de la BRVM, revue 04 §6.3). ``ValueError`` si un découpage a moins
    de ``min_train`` séances d'apprentissage.
    """
    cal = _as_calendar(dates)
    _check_cv_args(len(cal), n_splits, purge, embargo)
    out: list[PurgedSplit] = []
    for i, g in enumerate(_split_groups(cal, n_splits)):
        tr, pu, em = _purged_positions(len(cal), g, int(purge), int(embargo))
        out.append(
            PurgedSplit(split=i, test_groups=(i,), train=cal[tr], test=cal[g], purged=cal[pu], embargoed=cal[em])
        )
    _check_train(out, min_train, "purged_kfold")
    return out


@dataclass
class CPCVResult:
    """Validation croisée combinatoire purgée : découpages et chemins de backtest.

    ``paths[p]`` associe à chaque groupe ``g`` le découpage dont le test
    fournit ce groupe dans le chemin ``p`` ; il y a
    ``φ = C(N − 1, k − 1) = k/N · C(N, k)`` chemins (9 pour N = 10, k = 2).
    """

    splits: list[PurgedSplit]
    groups: list[pd.DatetimeIndex]
    n_groups: int
    k_test: int
    purge: int
    embargo: int
    paths: list[dict[int, int]]

    @property
    def n_splits(self) -> int:
        return len(self.splits)

    @property
    def n_paths(self) -> int:
        return len(self.paths)

    def path_returns(self, outputs: Mapping[int, pd.Series]) -> pd.DataFrame:
        """Assemble les chemins hors échantillon à partir des sorties de chaque découpage.

        ``outputs[s]`` : ``Series`` (dates × rendements) produite par le
        modèle entraîné sur ``splits[s].train`` et appliqué à
        ``splits[s].test``. Renvoie un ``DataFrame`` dates × chemins.
        """
        cols: dict[str, pd.Series] = {}
        for p, mapping in enumerate(self.paths):
            parts = []
            for g, s in sorted(mapping.items()):
                out = outputs[s]
                parts.append(out.loc[out.index.isin(self.groups[g])])
            cols[f"chemin_{p + 1}"] = pd.concat(parts).sort_index()
        return pd.concat(cols, axis=1)


def cpcv(
    dates: Any, n_groups: int = 10, k_test: int = 2, purge: int = 21, embargo: int = 21, *, min_train: int = 1
) -> CPCVResult:
    """CPCV (López de Prado, 2018, ch. 12) : ``C(N, k)`` découpages, ``C(N − 1, k − 1)`` chemins.

    Paramètres de la spécification §8.2 : 10 groupes, ``k = 2`` (45
    découpages, 9 chemins), purge 21 séances, embargo 21 séances. Deux
    groupes de test adjacents forment un seul bloc (purge avant, embargo
    après). ``ValueError`` si un découpage a moins de ``min_train`` séances
    d'apprentissage (calendrier trop court pour la purge et l'embargo).
    """
    cal = _as_calendar(dates)
    _check_cv_args(len(cal), n_groups, purge, embargo)
    if not 1 <= k_test < n_groups:
        raise ValueError("k_test doit être dans [1, n_groups[")
    groups = _split_groups(cal, n_groups)
    splits: list[PurgedSplit] = []
    for i, combo in enumerate(itertools.combinations(range(n_groups), k_test)):
        test_pos = np.concatenate([groups[g] for g in combo])
        tr, pu, em = _purged_positions(len(cal), test_pos, int(purge), int(embargo))
        splits.append(
            PurgedSplit(
                split=i,
                test_groups=tuple(combo),
                train=cal[tr],
                test=cal[np.sort(test_pos)],
                purged=cal[pu],
                embargoed=cal[em],
            )
        )
    _check_train(splits, min_train, "cpcv")
    n_paths = math.comb(n_groups - 1, k_test - 1)
    by_group = {g: [s.split for s in splits if g in s.test_groups] for g in range(n_groups)}
    paths = [{g: by_group[g][p] for g in range(n_groups)} for p in range(n_paths)]
    return CPCVResult(
        splits=splits,
        groups=[cal[g] for g in groups],
        n_groups=int(n_groups),
        k_test=int(k_test),
        purge=int(purge),
        embargo=int(embargo),
        paths=paths,
    )


# ---------------------------------------------------------------------------
# Registre des essais (reports/trials.parquet)
# ---------------------------------------------------------------------------

#: Emplacement du registre dans le dépôt (``reports/`` est le seul dossier
#: d'écriture autorisé hors ``data/``, ARCHITECTURE.md).
DEFAULT_REGISTRY_PATH = Path(__file__).resolve().parents[2] / "reports" / "trials.parquet"

#: Colonnes du registre (une ligne par essai).
REGISTRY_COLUMNS = (
    "id",
    "variante",
    "famille",
    "parametres",
    "echantillon",
    "statut",
    "date_execution",
    "rendements_hebdo",
    "metriques",
    "empreinte_config",
    "source",
    "note",
)

STATUT_DECLARE = "déclaré"  # essai déjà fait par les revues (S0), sans rendements journalisés
STATUT_PREENREGISTRE = "pré-enregistré"  # variante déclarée AVANT toute exécution (S1)
STATUT_EXECUTE = "exécuté"  # rendements hebdomadaires nets journalisés

#: Nombre d'essais de départ (spéc. §8.2 et §11 : 55 essais S0 + 8 variantes S1).
N_TRIALS_START = 63
S1_VARIANTS = ("A", "B", "C", "D", "E", "F", "G", "H")
#: Famille de la PBO et du DSR depuis l'additif v1.1 (D9 : variante I « cœur-satellite »).
FAMILY_V11 = ("A", "B", "C", "D", "E", "F", "G", "H", "I")
#: Référence « indice discipliné » (D8) : essai ``REF-ID``, hors famille de la PBO.
REFERENCE_VARIANT = "REF"
REFERENCE_TRIAL_ID = "REF-ID"
#: N de départ de l'additif v1.1 (§8.2) : 55 (S0) + 9 variantes + 1 référence, **avant** les
#: essais de diagnostic S0 réellement exécutés (ajoutés au registre, ils comptent aussi dans N).
N_TRIALS_START_V11 = 65

_A_WEIGHTS = {"ep": 0.15, "dy": 0.20, "mom6_1": 0.35, "lowvol": 0.20, "quality_proxy": 0.10}


def declared_s0_trials() -> list[dict[str, Any]]:
    """Les 55 essais déjà faits sur S0 (2022-11-17 → 2026-11-20), déclarés par la spécification §8.1-8.2.

    * 13 configurations acheteuses comparées formellement par [R03] §7.2-7.3
      (7 facteurs seuls et 6 composites ; **reconstitution** d'après les
      tableaux de la revue : la liste exacte des 13 n'y est pas énumérée,
      correspondance [NON VÉRIFIÉ]) ;
    * 6 fenêtres de momentum de [R03] §7.2 (3-1, 6-0, 6-1, 9-1, 12-1, 12-7) ;
    * la grille de 36 stratégies momentum de [R04] §3.4 (L × saut × top-k).

    Ces essais n'ont pas de rendements journalisés (statut « déclaré ») :
    ils comptent dans ``N`` (DSR, haircut BHY) mais pas dans la PBO.
    """
    out: list[dict[str, Any]] = []
    singles = ["mom12_1", "mom6_1", "str1", "ep", "dy", "lowvol", "illiq"]
    composites = [
        {"ep": 0.5, "dy": 0.5},
        {"ep": 0.25, "dy": 0.25, "mom6_1": 0.5},
        {"ep": 1 / 6, "dy": 1 / 6, "mom6_1": 1 / 3, "lowvol": 1 / 3},
        {"ep": 0.4 / 3, "dy": 0.4 / 3, "mom6_1": 0.8 / 3, "lowvol": 0.8 / 3, "str1_continuation": 0.20},
        {"ep": 0.25, "dy": 0.25, "mom12_1": 0.5},
        {"ep": 0.15, "dy": 0.20, "mom6_1": 0.20, "mom12_1": 0.15, "lowvol": 0.20},
    ]
    configs: list[dict[str, Any]] = [{"facteur": f} for f in singles] + [{"composite": c} for c in composites]
    for i, p in enumerate(configs, start=1):
        p.update({"portefeuille": "tertile supérieur équipondéré", "rebalancement": "mensuel", "execution": "t+1"})
        out.append(
            {
                "id": f"S0-R03-C{i:02d}",
                "variante": f"R03-C{i:02d}",
                "famille": "R03 configurations acheteuses",
                "parametres": p,
                "source": "[R03] §7.2-7.3",
                "note": "reconstitution de la liste des 13 configurations [NON VÉRIFIÉ]",
            }
        )
    for i, (look, skip) in enumerate([(3, 1), (6, 0), (6, 1), (9, 1), (12, 1), (12, 7)], start=1):
        out.append(
            {
                "id": f"S0-R03-M{i:02d}",
                "variante": f"MOM{look}-{skip}",
                "famille": "R03 fenêtres de momentum",
                "parametres": {"formation_mois": look, "saut_mois": skip, "mesure": "L/S tertiles"},
                "source": "[R03] §7.2",
                "note": "",
            }
        )
    k = 0
    for look in (21, 63, 126, 252):
        for skip in (0, 5, 21):
            for top in (5, 10, 15):
                k += 1
                out.append(
                    {
                        "id": f"S0-R04-G{k:02d}",
                        "variante": f"MOM-L{look}-S{skip}-K{top}",
                        "famille": "R04 grille momentum 36",
                        "parametres": {
                            "lookback": look,
                            "skip": skip,
                            "top_k": top,
                            "rebalance_sessions": 21,
                            "execution": "t+1",
                            "rendements": "bruts actifs contre le panier EW",
                            "periode": ["2023-03-17", "2026-11-20"],
                        },
                        "source": "[R04] §3.4",
                        "note": "",
                    }
                )
    for row in out:
        row.update({"echantillon": "S0", "statut": STATUT_DECLARE})
    assert len(out) == 55
    return out


def preregistered_s1_variants() -> list[dict[str, Any]]:
    """Les 8 variantes A-H pré-enregistrées pour S1 (spéc. §3.4), paramètres FIGÉS."""
    a = dict(_A_WEIGHTS)
    base = {"poids": a, "ponderation": "equal", "frequence": "mensuel", "bande": [30, 50]}
    specs: dict[str, tuple[dict[str, Any], str]] = {
        "A": (dict(base), "principal (pré-enregistré par [R03])"),
        "B": ({**base, "poids": {"ep": 0.25, "dy": 0.25, "mom6_1": 0.50}}, "challenger choisi après coup (DSR 0,65)"),
        "C": (
            {**base, "poids": {"ep": 0.15, "dy": 0.20, "mom6_1": 0.20, "mom12_1": 0.15, "lowvol": 0.20,
                               "quality_proxy": 0.10}},
            "horizon long « standard »",
        ),
        "D": ({**base, "neutralisation": "value dans les secteurs >= 4 titres (FIN, CB, CD, IND, ENE)"},
              "neutralisation sectorielle de la value"),
        "E": ({**base, "poche_S1": {"max_total": 0.20, "max_par_titre": 0.05}}, "surcouche S1 (dividende)"),
        "F": ({**base, "regime": {"p_agite": 0.8, "drawdown_tr": -0.08, "exposition": 0.75}}, "dosage par le régime"),
        "G": ({**base, "ponderation": "hrp_tilt", "gamma": 0.5}, "pondération par le risque (HRP)"),
        "H": ({**base, "ponderation": "mv_alpha", "ic_post": 0.02, "lambda": 5.0, "kappa": "coût aller central"},
              "moyenne-variance rétrécie"),
    }
    out = []
    for code in S1_VARIANTS:
        params, role = specs[code]
        out.append(
            {
                "id": f"S1-{code}",
                "variante": code,
                "famille": "S1 variantes pré-enregistrées",
                "parametres": params,
                "echantillon": "S1",
                "statut": STATUT_PREENREGISTRE,
                "source": "SPECIFICATION_STRATEGIE.md §3.4",
                "note": role,
            }
        )
    return out


def preregistered_addendum_v11() -> list[dict[str, Any]]:
    """Essais ajoutés par l'additif v1.1 (§8.4, D8-D9) **avant** toute exécution sur S1.

    * ``S1-I`` : variante I « cœur-satellite » ``w_I = 0,5·w_D8 + 0,5·w_A`` (famille N = 9) ;
    * ``REF-ID`` : référence « indice discipliné » D8, évaluée sur S1 comme étalon
      investissable, **hors famille** de la PBO (mais comptée dans ``N``).
    """
    core = {
        "n_titres": 20,
        "ponderation": "capitalisation point-in-time",
        "investi": 0.98,
        "plafond_ligne": "max(10 % × multiplicateur pays ; min(30 % ; 1,25 × b_i))",
        "plancher_ligne": 0.005,
        "plafond_secteur": "max(15 % ; 1,25 × b_s)",
        "plafonds": "pays, AES et liquidité de A",
        "filtres": "R et règles pays actifs",
        "rebalancement": "annuel (première décision de janvier) + sorties forcées",
    }
    return [
        {
            "id": "S1-I",
            "variante": "I",
            "famille": "S1 variantes pré-enregistrées",
            "parametres": {"coeur": core, "poids_coeur": 0.5, "poids_A": 0.5,
                           "rebalancement": {"A": "mensuel", "coeur": "annuel"},
                           "projection": "plafonds de groupe de D8", "chevauchements": "additionnés"},
            "echantillon": "S1",
            "statut": STATUT_PREENREGISTRE,
            "source": "SPECIFICATION_STRATEGIE.md §8.4 (D9)",
            "note": "cœur-satellite 50/50 fixé a priori (aucun paramètre libre)",
        },
        {
            "id": REFERENCE_TRIAL_ID,
            "variante": REFERENCE_VARIANT,
            "famille": "S1 référence indice discipliné (hors PBO)",
            "parametres": core,
            "echantillon": "S1",
            "statut": STATUT_PREENREGISTRE,
            "source": "SPECIFICATION_STRATEGIE.md §8.4 (D8)",
            "note": "référence investissable et repli du §8.3 ; hors famille de la PBO, compté dans N",
        },
    ]


def declared_s0_diagnostic_trials() -> list[dict[str, Any]]:
    """Essais de diagnostic S0 **déjà exécutés** pendant la mise au point (additif v1.1, §8.4).

    Ils ont été vus (informations contaminées déclarées par l'additif) mais leurs rendements
    n'ont pas été journalisés : statut « déclaré », comptés dans ``N`` (DSR, haircut BHY),
    hors PBO.

    * ``S0-DIAG-A-01`` : essai de fumée de A sur S0 (10 M FCFA, coûts centraux) : ≈ 28 %/an
      contre 34,6 %/an pour le TR, drawdown relatif −15 % au 30/09/2024 puis −20 % au
      29/11/2024 (arrêt, « indice discipliné ») ;
    * ``S0-DIAG-A-02`` : essai de fumée court de A (02/01/2024 → 28/06/2024, test
      ``test_smoke_backtest_s0_short``), exécuté à chaque passage de la suite de tests ;
    * ``S0-DIAG-DEC-20261120`` : décision du 20/11/2026 (remplissage de capacité, CIEC rang 19
      à 8,58 % contre BOAC rang 1 à 5,98 %), motif des décisions D4.
    """
    base = {"variante_moteur": "A", "capital": 10_000_000, "couts": "central"}
    rows = [
        {"id": "S0-DIAG-A-01", "variante": "A", "famille": "S0 diagnostic (mise au point)",
         "parametres": {**base, "periode": ["2022-11-17", "2026-11-20"], "mesure": "fumée"},
         "source": "SPECIFICATION_STRATEGIE.md §8.4 (« Ce qui a été vu »)",
         "note": "≈ 28 %/an contre 34,6 %/an pour le TR ; DD relatif −15 % (30/09/2024), −20 % (29/11/2024)"},
        {"id": "S0-DIAG-A-02", "variante": "A", "famille": "S0 diagnostic (mise au point)",
         "parametres": {**base, "periode": ["2024-01-02", "2024-06-28"], "mesure": "fumée courte (tests)"},
         "source": "tests/test_strategy_alpha.py::test_smoke_backtest_s0_short",
         "note": "contrôle de forme (NAV finie, coûts et rotation plausibles)"},
        {"id": "S0-DIAG-DEC-20261120", "variante": "A", "famille": "S0 diagnostic (mise au point)",
         "parametres": {**base, "date": "2026-11-20", "mesure": "décision (poids)"},
         "source": "SPECIFICATION_STRATEGIE.md §8.4 (« Décision du 20/11/2026 »)",
         "note": "CIEC (rang 19) 8,58 % contre BOAC (rang 1) 5,98 % : motif de D4"},
    ]
    for row in rows:
        row.update({"echantillon": "S0", "statut": STATUT_DECLARE})
    return rows


def _json_default(x: Any) -> Any:
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating,)):
        v = float(x)
        return v if math.isfinite(v) else None
    if isinstance(x, np.ndarray):
        return [_json_default(v) for v in x.tolist()]
    if isinstance(x, (pd.Timestamp,)):
        return x.isoformat()
    return str(x)


def _clean_json(obj: Any) -> Any:
    """Remplace NaN / inf par ``None`` (JSON strict)."""
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, Mapping):
        return {str(k): _clean_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean_json(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return [_clean_json(v) for v in obj.tolist()]
    if isinstance(obj, (np.floating, np.integer)):
        return _clean_json(obj.item())
    return obj


def _dumps(obj: Any) -> str:
    return json.dumps(_clean_json(obj), sort_keys=True, ensure_ascii=False, default=_json_default)


def _series_to_json(s: pd.Series | None) -> str | None:
    if s is None:
        return None
    s = pd.Series(s, dtype=float).dropna()
    idx = pd.DatetimeIndex(pd.to_datetime(s.index))
    return _dumps({d.strftime("%Y-%m-%d"): float(v) for d, v in zip(idx, s.to_numpy(), strict=True)})


class TrialRegistry:
    """Registre persistant des essais (``reports/trials.parquet``, spéc. §8.2, revue 04 §17.1 G1).

    Chaque essai (variante × échantillon) est journalisé avec ses paramètres
    (JSON), son échantillon, sa date d'exécution, ses **rendements
    hebdomadaires nets** (JSON ``{date: rendement}``) et ses métriques. Le
    registre alimente ``N`` du Sharpe dégonflé et ``M`` du haircut BHY
    (:meth:`n_trials`, N **brut**), la matrice de la PBO
    (:meth:`returns_matrix`) et la variance des Sharpe entre essais
    (:meth:`sharpe_variance`).

    Garde-fous :

    * S1 est un **test unique** : une variante déjà « exécutée » sur S1 ne
      peut pas être enregistrée une seconde fois ;
    * les paramètres d'une variante pré-enregistrée sont **figés** : une
      exécution avec d'autres paramètres est refusée (créer un nouvel essai
      sous un autre nom, compté dans ``N``).
    """

    def __init__(self, path: str | Path | None = DEFAULT_REGISTRY_PATH, frame: pd.DataFrame | None = None) -> None:
        self.path = None if path is None else Path(path)
        if frame is None:
            frame = pd.DataFrame({c: pd.Series(dtype=object) for c in REGISTRY_COLUMNS})
            frame["date_execution"] = pd.Series(dtype="datetime64[ns, UTC]")
        missing = [c for c in REGISTRY_COLUMNS if c not in frame.columns]
        if missing:
            raise ValueError(f"registre : colonnes manquantes {missing}")
        self._frame = frame.loc[:, list(REGISTRY_COLUMNS)].reset_index(drop=True)

    # -- persistance ------------------------------------------------------

    @classmethod
    def load(cls, path: str | Path = DEFAULT_REGISTRY_PATH) -> TrialRegistry:
        """Lit le registre (registre vide si le fichier n'existe pas)."""
        p = Path(path)
        if not p.exists():
            return cls(p)
        return cls(p, pd.read_parquet(p))

    @classmethod
    def initialize(
        cls,
        path: str | Path | None = DEFAULT_REGISTRY_PATH,
        *,
        save: bool = True,
        overwrite: bool = False,
        addendum_v11: bool = False,
    ) -> TrialRegistry:
        """Registre amorcé avec les 55 essais S0 « déclarés » et les 8 variantes S1 « pré-enregistrées ».

        ``addendum_v11=True`` ajoute les essais de l'additif v1.1 (§8.4) : ``S1-I``,
        ``REF-ID`` (:func:`preregistered_addendum_v11`) et les essais de diagnostic S0 déjà
        exécutés (:func:`declared_s0_diagnostic_trials`), soit ``N = 68`` au départ.

        Idempotent : un registre existant est relu et seuls les essais
        d'amorçage absents (par ``id``) sont ajoutés ; ``overwrite=True``
        repart d'un registre vide (à éviter : l'historique des essais fait
        partie de la preuve).
        """
        reg = cls(path) if (overwrite or path is None or not Path(path).exists()) else cls.load(path)
        have = set(reg._frame["id"])
        fingerprint = None
        try:
            from brvm_alpha import settings

            fingerprint = settings.config_fingerprint(settings.load_strategy_config())
        except Exception:  # pragma: no cover - fichier de paramètres absent ou invalide
            fingerprint = None
        rows = []
        seed_rows = declared_s0_trials() + preregistered_s1_variants()
        if addendum_v11:
            seed_rows += preregistered_addendum_v11() + declared_s0_diagnostic_trials()
        for row in seed_rows:
            if row["id"] in have:
                continue
            rows.append(
                {
                    "id": row["id"],
                    "variante": row["variante"],
                    "famille": row["famille"],
                    "parametres": _dumps(row["parametres"]),
                    "echantillon": row["echantillon"],
                    "statut": row["statut"],
                    "date_execution": pd.NaT,
                    "rendements_hebdo": None,
                    "metriques": None,
                    "empreinte_config": fingerprint if row["echantillon"] == "S1" else None,
                    "source": row["source"],
                    "note": row["note"],
                }
            )
        if rows:
            reg._append(rows)
        if save and reg.path is not None:
            reg.save()
        return reg

    def save(self, path: str | Path | None = None) -> Path:
        """Écrit le registre en parquet (dossier créé si besoin)."""
        p = Path(path) if path is not None else self.path
        if p is None:
            raise ValueError("aucun chemin de registre")
        p.parent.mkdir(parents=True, exist_ok=True)
        out = self._frame.copy()
        out["date_execution"] = pd.to_datetime(out["date_execution"], utc=True)
        for c in REGISTRY_COLUMNS:
            if c != "date_execution":
                out[c] = out[c].astype(object).where(out[c].notna(), None)
        out.to_parquet(p, index=False)
        return p

    # -- accès ----------------------------------------------------------------

    @property
    def frame(self) -> pd.DataFrame:
        """Copie du registre (une ligne par essai)."""
        return self._frame.copy()

    def __len__(self) -> int:
        return len(self._frame)

    def n_trials(self, sample: str | None = None, *, include_declared: bool = True) -> int:
        """Nombre **brut** d'essais (``N`` du DSR, ``M`` du haircut BHY ; revue 04 §4.4).

        ``sample`` restreint à un échantillon ; ``include_declared=False``
        ne compte que les essais exécutés.
        """
        f = self._frame
        if sample is not None:
            f = f[f["echantillon"] == sample]
        if not include_declared:
            f = f[f["statut"] == STATUT_EXECUTE]
        return int(len(f))

    def executed(self, sample: str | None = None) -> pd.DataFrame:
        """Essais au statut « exécuté » (restreints à ``sample`` si fourni)."""
        f = self._frame[self._frame["statut"] == STATUT_EXECUTE]
        if sample is not None:
            f = f[f["echantillon"] == sample]
        return f.copy()

    def set_metrics(self, trial_id: str, metrics: Mapping[str, Any], *, save: bool = False) -> None:
        """Remplace les métriques (JSON) d'un essai exécuté (statut §8.3 calculé après coup)."""
        hit = np.flatnonzero((self._frame["id"] == trial_id).to_numpy())
        if not hit.size:
            raise KeyError(trial_id)
        i = int(hit[0])
        if self._frame.at[i, "statut"] != STATUT_EXECUTE:
            raise ValueError(f"essai {trial_id} non exécuté : aucune métrique à enregistrer")
        self._frame = self._frame.astype(object)
        self._frame.at[i, "metriques"] = _dumps(dict(metrics))
        if save:
            self.save()

    def _append(self, rows: list[dict[str, Any]]) -> None:
        new = pd.DataFrame(rows, columns=list(REGISTRY_COLUMNS))
        base = self._frame
        if len(base) == 0:
            self._frame = new.reset_index(drop=True)
        else:
            self._frame = pd.concat([base.astype(object), new.astype(object)], ignore_index=True)

    def record(
        self,
        variant: str,
        params: Mapping[str, Any],
        sample: str,
        weekly_returns: pd.Series,
        metrics: Mapping[str, Any] | None = None,
        *,
        family: str = "",
        trial_id: str | None = None,
        run_date: Any = None,
        config_fingerprint: str | None = None,
        source: str = "",
        note: str = "",
        save: bool = False,
        rerun_reason: str | None = None,
    ) -> str:
        """Journalise un essai exécuté (rendements hebdomadaires **nets**) et renvoie son ``id``.

        Une variante pré-enregistrée sur ``sample`` est complétée sur place
        (paramètres identiques exigés) ; sinon une nouvelle ligne est créée
        (``N`` augmente d'une unité).

        S1 est un test unique : une variante déjà exécutée sur S1 est refusée, **sauf**
        relance motivée par un bogue démontré (``rerun_reason``, additif v1.1 D12) : un
        **nouvel** essai est alors créé (``S1-<variante>-R<k>``, ``N`` augmente), l'ancien
        résultat reste au registre et les paramètres figés sont toujours exigés.
        """
        if weekly_returns is None or len(pd.Series(weekly_returns).dropna()) == 0:
            raise ValueError("rendements hebdomadaires nets obligatoires pour un essai exécuté")
        f = self._frame
        same = (f["variante"] == variant) & (f["echantillon"] == sample)
        rerun = False
        if sample == "S1" and bool((same & (f["statut"] == STATUT_EXECUTE)).any()):
            if not (rerun_reason and str(rerun_reason).strip()):
                raise RuntimeError(
                    f"la variante {variant} a déjà été exécutée sur S1 : l'échantillon vierge ne sert qu'à UN test "
                    "(relance seulement pour un bogue démontré, avec rerun_reason)"
                )
            rerun = True
            frozen_rows = f[same & f["parametres"].notna()]
            frozen_params = json.loads(str(frozen_rows["parametres"].iloc[0])) if len(frozen_rows) else None
            if frozen_params is not None and json.loads(_dumps(dict(params))) != frozen_params:
                raise ValueError(
                    f"paramètres de la variante {variant} modifiés : ils sont FIGÉS ; une relance motivée "
                    "rejoue les mêmes paramètres"
                )
        stamp = pd.Timestamp.now(tz="UTC") if run_date is None else pd.Timestamp(run_date)
        if stamp.tzinfo is None:
            stamp = stamp.tz_localize("UTC")
        payload = {
            "parametres": _dumps(dict(params)),
            "statut": STATUT_EXECUTE,
            "date_execution": stamp,
            "rendements_hebdo": _series_to_json(pd.Series(weekly_returns)),
            "metriques": _dumps(dict(metrics or {})),
            "empreinte_config": config_fingerprint,
        }
        pre = same & (f["statut"] == STATUT_PREENREGISTRE)
        if rerun:
            k = 1
            existing = set(f["id"])
            base_id = str(f.loc[same, "id"].iloc[0]) if bool(same.any()) else f"{sample}-{variant}"
            while f"{base_id}-R{k}" in existing:
                k += 1
            tid = trial_id or f"{base_id}-R{k}"
            if tid in existing:
                raise ValueError(f"identifiant d'essai déjà utilisé : {tid}")
            reason = f"relance motivée (D12) : {str(rerun_reason).strip()}"
            self._append(
                [
                    {
                        "id": tid,
                        "variante": variant,
                        "famille": family or str(f.loc[same, "famille"].iloc[0]),
                        "echantillon": sample,
                        "source": source or str(f.loc[same, "source"].iloc[0]),
                        "note": (note + " ; " if note else "") + reason,
                        **payload,
                    }
                ]
            )
        elif bool(pre.any()):
            i = int(np.flatnonzero(pre.to_numpy())[0])
            frozen = json.loads(str(f.at[i, "parametres"]))
            if json.loads(payload["parametres"]) != frozen:
                raise ValueError(
                    f"paramètres de la variante pré-enregistrée {variant} modifiés : ils sont FIGÉS avant le test ; "
                    "enregistrer un nouvel essai sous un autre nom"
                )
            self._frame = f.astype(object)
            # L'empreinte du pré-enregistrement n'est jamais effacée sans trace (revue du 22/11/2026 : celle des
            # essais S1-A à S1-H, dcdf1fb7db530c44, avait été remplacée par celle de l'exécution).
            old_fp = f.at[i, "empreinte_config"]
            new_fp = payload.get("empreinte_config")
            if isinstance(old_fp, str) and old_fp and new_fp is not None and str(new_fp) != old_fp:
                prev_note = f.at[i, "note"]
                prev_note = prev_note if isinstance(prev_note, str) else ""
                payload = {**payload, "note": (prev_note + " ; " if prev_note else "")
                           + f"empreinte au pré-enregistrement : {old_fp} ; empreinte à l'exécution : {new_fp}"}
            for k, v in payload.items():
                if k == "empreinte_config" and v is None:
                    continue
                self._frame.at[i, k] = v
            tid = str(self._frame.at[i, "id"])
        else:
            tid = trial_id or f"{sample}-{variant}-{int(same.sum()) + 1:03d}"
            if tid in set(f["id"]):
                raise ValueError(f"identifiant d'essai déjà utilisé : {tid}")
            self._append(
                [
                    {
                        "id": tid,
                        "variante": variant,
                        "famille": family,
                        "echantillon": sample,
                        "source": source,
                        "note": note,
                        **payload,
                    }
                ]
            )
        if save:
            self.save()
        return tid

    def weekly_returns(self, trial_id: str) -> pd.Series:
        """Rendements hebdomadaires nets journalisés d'un essai (``Series`` vide si déclaré)."""
        row = self._frame[self._frame["id"] == trial_id]
        if row.empty:
            raise KeyError(trial_id)
        raw = row["rendements_hebdo"].iloc[0]
        if raw is None or (isinstance(raw, float) and math.isnan(raw)):
            return pd.Series(dtype=float, name=trial_id)
        d = json.loads(str(raw))
        s = pd.Series({pd.Timestamp(k): (np.nan if v is None else float(v)) for k, v in d.items()}, dtype=float)
        return s.sort_index().rename(trial_id)

    def returns_matrix(self, sample: str | None = None, variants: Sequence[str] | None = None) -> pd.DataFrame:
        """Matrice semaines × essais exécutés (entrée de la PBO, :func:`metrics.family_pbo`)."""
        f = self._frame[self._frame["statut"] == STATUT_EXECUTE]
        if sample is not None:
            f = f[f["echantillon"] == sample]
        if variants is not None:
            f = f[f["variante"].isin(list(variants))]
        cols = {str(r["variante"]) if variants is not None else str(r["id"]): self.weekly_returns(str(r["id"]))
                for _, r in f.iterrows()}
        if not cols:
            return pd.DataFrame()
        return pd.concat(cols, axis=1).sort_index()

    def sharpe_variance(self, sample: str | None = None) -> float:
        """Variance (``ddof = 1``) des Sharpe **hebdomadaires par période** des essais exécutés.

        NaN s'il y a moins de deux essais exécutés : le DSR n'est alors pas
        évaluable sans hypothèse externe sur cette variance.
        """
        mat = self.returns_matrix(sample)
        if mat.shape[1] < 2:
            return math.nan
        srs = []
        for c in mat.columns:
            x = mat[c].dropna()
            sd = float(x.std(ddof=1)) if len(x) > 1 else math.nan
            if sd and math.isfinite(sd) and sd > 0:
                srs.append(float(x.mean()) / sd)
        return float(np.var(srs, ddof=1)) if len(srs) >= 2 else math.nan

    def is_complete(
        self,
        sample: str = "S1",
        variants: Sequence[str] = S1_VARIANTS,
        min_trials: int = N_TRIALS_START,
    ) -> bool:
        """G1 : registre complet (``N ≥ 63`` et chaque variante de la famille exécutée avec ses rendements)."""
        if self.n_trials() < int(min_trials):
            return False
        f = self._frame
        for v in variants:
            row = f[(f["variante"] == v) & (f["echantillon"] == sample) & (f["statut"] == STATUT_EXECUTE)]
            if row.empty or row["rendements_hebdo"].isna().all():
                return False
        return True


# ---------------------------------------------------------------------------
# Statut de la stratégie (spéc. §8.3, revue 04 §17.1)
# ---------------------------------------------------------------------------

STATUT_REJETE = "REJETÉ"
STATUT_CANDIDAT = "CANDIDAT"
STATUT_PROMU = "PROMU"
#: Cas non prévu par le §8.3 (ni rejeté, ni candidat) : aucun suivi réel autorisé.
STATUT_INDETERMINE = "INDÉTERMINÉ"
#: Versions des règles de :func:`evaluate_status` : ``"v1.1"`` (défaut, additif §8.4, D7) ou
#: ``"v1.0"`` (lecture prudente antérieure, conservée pour la traçabilité).
RULES_VERSIONS = ("v1.1", "v1.0")

#: Seuils du §8.3 (et du §12.1 ``validation``), FIGÉS avant toute exécution sur S1.
STATUS_THRESHOLDS: dict[str, float] = {
    "reject_active_net_central_le": 0.0,
    "reject_active_net_stress_lt": -0.01,
    "reject_subperiod_ir_lt": -0.5,
    "reject_rel_dd_lt": -0.20,
    "reject_abs_dd_worse_than_tr_by": 0.10,
    "candidate_active_net_central_gt": 0.0,
    "candidate_active_net_stress_ge": -0.005,
    "candidate_ir_ge": 0.20,
    "candidate_rel_dd_ge": -0.20,
    "candidate_turnover_month_le": 0.20,
    "candidate_pbo_le": 0.5,
    "candidate_cvar_ratio_le": 1.25,
    "psr_min": 0.95,
    "dsr_min": 0.95,
    "pbo_max_promoted": 0.25,
    "pbo_min_slope": -0.5,
    "hsr_min": 0.3,
    "ic_min_t_documented": 2.0,
    "ic_min_t_new": 3.0,
    "ic_min_months": 36,
    "lo_naive_ratio_min": 0.6,
    "s2_min_weeks": 52,
    # G7 sur S2, règles v1.0 seulement (``rules="v1.0"``) : IC mensuels PROPRES au suivi réel,
    # lecture prudente (36 mois d'IC de S2). Depuis l'additif v1.1 (D7, défaut ``rules="v1.1"``),
    # G7 s'évalue sur la série d'IC S1 puis S2 mise bout à bout (``ic_min_months`` = 36 mois) et les
    # autres filtres de S2 sur S2 seul (``s2_min_weeks`` = 52 semaines, soit 12 mois).
    "s2_ic_min_months": 36,
    # Longueur minimale d'un échantillon évalué (critères C1-C7 et G1-G9) : 52 semaines par sous-période.
    "min_weeks_per_subperiod": 52,
    "min_coverage": 0.95,
    "n_trials_start": N_TRIALS_START,
}

_YAML_REJECT = {
    "active_net_central_le": "reject_active_net_central_le",
    "active_net_stress_lt": "reject_active_net_stress_lt",
    "subperiod_ir_lt": "reject_subperiod_ir_lt",
    "rel_dd_lt": "reject_rel_dd_lt",
    "abs_dd_worse_than_tr_by": "reject_abs_dd_worse_than_tr_by",
}
_YAML_CANDIDATE = {
    "active_net_central_gt": "candidate_active_net_central_gt",
    "active_net_stress_ge": "candidate_active_net_stress_ge",
    "ir_ge": "candidate_ir_ge",
    "rel_dd_ge": "candidate_rel_dd_ge",
    "turnover_month_le": "candidate_turnover_month_le",
    "pbo_le": "candidate_pbo_le",
    "cvar_ratio_le": "candidate_cvar_ratio_le",
}


def status_thresholds(params: Mapping[str, Any] | None = None) -> dict[str, float]:
    """Seuils de décision : défauts de la spécification, surchargés par ``params``.

    ``params`` : clés plates de :data:`STATUS_THRESHOLDS`, ou configuration
    complète (``settings.load_strategy_config()``, section ``validation``).
    """
    out = dict(STATUS_THRESHOLDS)
    if not params:
        return out
    val = params.get("validation") if isinstance(params.get("validation"), Mapping) else None
    if val is None:
        unknown = set(params) - set(out)
        if unknown:
            raise KeyError(f"seuils inconnus : {sorted(unknown)}")
        out.update({k: float(v) for k, v in params.items()})
        return out
    for k, v in (val.get("reject_if") or {}).items():
        if k in _YAML_REJECT:
            out[_YAML_REJECT[k]] = float(v)
    for k, v in (val.get("candidate_if") or {}).items():
        if k in _YAML_CANDIDATE:
            out[_YAML_CANDIDATE[k]] = float(v)
    for k in ("psr_min", "dsr_min", "n_trials_start"):
        if k in val:
            out[k] = float(val[k])
    pbo = val.get("pbo") or {}
    if "max_promoted" in pbo:
        out["pbo_max_promoted"] = float(pbo["max_promoted"])
    if "min_slope" in pbo:
        out["pbo_min_slope"] = float(pbo["min_slope"])
    hc = val.get("haircut") or {}
    if "min_hsr" in hc:
        out["hsr_min"] = float(hc["min_hsr"])
    mt = val.get("min_t") or {}
    if "documented" in mt:
        out["ic_min_t_documented"] = float(mt["documented"])
    if "new" in mt:
        out["ic_min_t_new"] = float(mt["new"])
    return out


@dataclass
class StatusReport:
    """Résultat de :func:`evaluate_status` : statut et détail critère par critère.

    ``criteres`` : une ligne par critère (``groupe`` ∈ ``rejet``,
    ``candidat``, ``promotion_S1``, ``promotion_S2`` ; ``code``,
    ``libelle``, ``valeur``, ``seuil``, ``verifie`` (``True`` / ``False`` /
    ``None`` = non évaluable, donnée manquante), ``note``).
    """

    statut: str
    criteres: pd.DataFrame
    mesures: dict[str, Any]
    avertissements: list[str]

    @property
    def bandeau(self) -> str:
        """Bandeau permanent de la spécification §10."""
        return f"Performance passée ≠ garantie. Aucun gain n'est garanti. Statut : {self.statut}"

    def groupe(self, name: str) -> pd.DataFrame:
        """Critères d'un groupe (``rejet``, ``candidat``, ``promotion_S1``, ``promotion_S2``)."""
        return self.criteres[self.criteres["groupe"] == name].reset_index(drop=True)

    def critere(self, groupe: str, code: str) -> dict[str, Any]:
        """Un critère (dictionnaire)."""
        row = self.criteres[(self.criteres["groupe"] == groupe) & (self.criteres["code"] == code)]
        if row.empty:
            raise KeyError(f"{groupe}/{code}")
        return row.iloc[0].to_dict()

    def to_dict(self) -> dict[str, Any]:
        return {
            "statut": self.statut,
            "bandeau": self.bandeau,
            "criteres": self.criteres.to_dict("records"),
            "mesures": self.mesures,
            "avertissements": list(self.avertissements),
        }


def _finite(x: Any) -> bool:
    try:
        return x is not None and math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def _check(value: Any, test: Callable[[float], bool]) -> bool | None:
    """``True`` / ``False`` si la valeur est évaluable, ``None`` sinon."""
    return bool(test(float(value))) if _finite(value) else None


def _slice(s: pd.Series, a: Any, b: Any) -> pd.Series:
    return s.loc[(s.index >= pd.Timestamp(a)) & (s.index <= pd.Timestamp(b))]


def _g_filters(
    group: str,
    active: pd.Series,
    subperiods: Sequence[tuple[Any, Any]],
    th: Mapping[str, float],
    *,
    n_trials: int | None,
    sr_variance: float | None,
    g1: bool | None,
    pbo: float,
    pbo_slope: float | None,
    ic_monthly: pd.Series | None,
    new_signal: bool,
    n_boot: int,
    mean_block: float,
    seed: int,
    lo_q: int,
    mesures: dict[str, Any],
    ic_min_months: float | None = None,
) -> list[dict[str, Any]]:
    """Filtres G1-G9 de la revue 04 §17.1 sur une série de rendements actifs hebdomadaires.

    Toutes les entrées (IC mensuels, PBO et pente) doivent être PROPRES à l'échantillon
    évalué : pour le suivi réel S2, celles de S1 ne sont jamais réutilisées.
    """
    from brvm_alpha.backtest import metrics as mt
    from brvm_alpha.quant import stats

    rows: list[dict[str, Any]] = []
    n_obs = int(active.dropna().size)
    psr_v = mt.psr(active) if n_obs >= 3 else math.nan
    dsr_v = math.nan
    if n_trials is not None and n_obs >= 3:
        dsr_v = mt.dsr(active, n_trials, sr_variance if sr_variance is not None else math.nan)
    ir = mt.information_ratio(active) if n_obs >= 2 else math.nan
    hsr = math.nan
    if n_trials is not None and _finite(ir) and n_obs >= 2:
        hsr = float(stats.haircut_sharpe(ir, n_obs=n_obs, n_tests=int(n_trials), method="bhy",
                                         periods_per_year=mt.WEEKS_PER_YEAR))
    boot = mt.bootstrap_ci(active, "ir", n_boot=n_boot, mean_block=mean_block, seed=seed)
    naive = mt.naive_sharpe(active) if n_obs >= 2 else math.nan
    lo = mt.lo_sharpe(active, q=lo_q) if n_obs > lo_q + 1 else math.nan
    ic_t, ic_n = math.nan, 0
    if ic_monthly is not None:
        ic = pd.Series(ic_monthly, dtype=float).dropna()
        ic_n = int(ic.size)
        ic_t = float(stats.newey_west_tstat(ic)) if ic_n >= 2 else math.nan
    min_t = th["ic_min_t_new"] if new_signal else th["ic_min_t_documented"]
    signs = []
    for a, b in subperiods:
        sub = _slice(active, a, b).dropna()
        signs.append(float(sub.mean()) if len(sub) else math.nan)
    mesures.update(
        {
            f"{group}_psr": psr_v,
            f"{group}_dsr": dsr_v,
            f"{group}_n_trials": n_trials,
            f"{group}_sr_variance": sr_variance,
            f"{group}_hsr_bhy": hsr,
            f"{group}_ir_bootstrap": boot,
            f"{group}_sharpe_naif": naive,
            f"{group}_sharpe_lo": lo,
            f"{group}_ic_t_nw": ic_t,
            f"{group}_ic_mois": ic_n,
            f"{group}_moyennes_sous_periodes": signs,
        }
    )
    g4 = None
    if _finite(pbo) and pbo_slope is not None and _finite(pbo_slope):
        g4 = bool(float(pbo) <= th["pbo_max_promoted"] and float(pbo_slope) > th["pbo_min_slope"])
    elif _finite(pbo) and float(pbo) > th["pbo_max_promoted"]:
        g4 = False
    g7 = None
    min_months = th["ic_min_months"] if ic_min_months is None else float(ic_min_months)
    if ic_monthly is not None:
        g7 = bool(ic_n >= min_months and _finite(ic_t) and ic_t >= min_t)
    g8 = None if (not signs or not all(_finite(x) for x in signs)) else bool(all(x > 0 for x in signs))
    g9 = None if not (_finite(lo) and _finite(naive)) else bool(lo >= th["lo_naive_ratio_min"] * naive)
    rows += [
        {"code": "G1", "libelle": "registre d'essais complet (chaque variante journalisée avec ses rendements)",
         "valeur": n_trials, "seuil": f"N ≥ {int(th['n_trials_start'])} et famille exécutée", "verifie": g1,
         "note": ""},
        {"code": "G2", "libelle": "PSR(SR* = 0) des rendements actifs hebdomadaires", "valeur": psr_v,
         "seuil": f"≥ {th['psr_min']}", "verifie": _check(psr_v, lambda v: v >= th["psr_min"]), "note": ""},
        {"code": "G3", "libelle": "DSR avec N = nombre d'essais du registre", "valeur": dsr_v,
         "seuil": f"≥ {th['dsr_min']}", "verifie": _check(dsr_v, lambda v: v >= th["dsr_min"]),
         "note": "" if _finite(dsr_v) else "variance des Sharpe entre essais inconnue ou N absent"},
        {"code": "G4", "libelle": "PBO de la famille et pente de dégradation", "valeur": pbo,
         "seuil": f"PBO ≤ {th['pbo_max_promoted']} et pente > {th['pbo_min_slope']}", "verifie": g4,
         "note": "" if pbo_slope is not None else "pente de dégradation non fournie"},
        {"code": "G5", "libelle": "haircut BHY (M = registre)", "valeur": hsr, "seuil": f"HSR > {th['hsr_min']}",
         "verifie": _check(hsr, lambda v: v > th["hsr_min"]), "note": ""},
        {"code": "G6", "libelle": "borne basse à 95 % du bootstrap stationnaire de l'IR",
         "valeur": boot["lower"], "seuil": "> 0", "verifie": _check(boot["lower"], lambda v: v > 0),
         "note": f"n_boot = {boot['n_boot']}, blocs de {boot['mean_block']:g} semaines"},
        {"code": "G7", "libelle": "t de Newey-West de l'IC mensuel sur au moins 36 mois", "valeur": ic_t,
         "seuil": f"t ≥ {min_t} et ≥ {int(min_months)} mois", "verifie": g7,
         "note": (f"{ic_n} mois d'IC" if ic_monthly is not None else "série d'IC non fournie")},
        {"code": "G8", "libelle": "stabilité du signe de l'alpha (chaque sous-période)", "valeur": signs,
         "seuil": "moyenne active > 0 partout", "verifie": g8, "note": ""},
        {"code": "G9", "libelle": "Sharpe de Lo (q = 4) ≥ 0,6 × Sharpe naïf", "valeur": lo,
         "seuil": f"≥ {th['lo_naive_ratio_min']} × {naive:.3f}" if _finite(naive) else "—", "verifie": g9,
         "note": "Sharpe naïf ≤ 0 : critère peu informatif" if _finite(naive) and naive <= 0 else ""},
    ]
    for r in rows:
        r["groupe"] = group
    return rows


def _prep_weekly(x: Any, name: str, windows: Sequence[tuple[Any, Any]] | None, avert: list[str]) -> pd.Series:
    """Série hebdomadaire triée : NaN retirés (signalés), semaines des fenêtres exclues retirées (signalées)."""
    from brvm_alpha.backtest import metrics as mt

    raw = pd.Series(x, dtype=float).sort_index()
    if not isinstance(raw.index, pd.DatetimeIndex):
        raw.index = pd.DatetimeIndex(pd.to_datetime(raw.index))
    n_nan = int(raw.isna().sum())
    if n_nan:
        avert.append(f"{name} : {n_nan} semaine(s) NaN retirée(s) (série tronquée ? à vérifier avant toute "
                     "conclusion)")
    out = raw.dropna()
    if windows and len(out):
        keep = mt.weekly_observation_mask(out.index, out.index, exclude_windows=windows, max_sessions=None)
        if (~keep).any():
            avert.append(f"{name} : {int((~keep).sum())} semaine(s) dans une fenêtre exclue des statistiques "
                         "(§8.1, 06/05 → 25/06/2021) retirée(s)")
            out = out[keep]
    return out


def evaluate_status(
    active_weekly_returns_central: pd.Series,
    active_weekly_returns_stress: pd.Series | None,
    benchmark: pd.Series,
    subperiods: Sequence[tuple[Any, Any]] | None = None,
    turnover: float | None = None,
    pbo: float | None = None,
    cvar_ratio: float | None = None,
    *,
    pbo_slope: float | None = None,
    registry: TrialRegistry | None = None,
    n_trials: int | None = None,
    sr_variance: float | None = None,
    registry_complete: bool | None = None,
    ic_monthly: pd.Series | None = None,
    new_signal: bool = False,
    s2_active_weekly_returns: pd.Series | None = None,
    s2_ic_monthly: pd.Series | None = None,
    s2_pbo: float | None = None,
    s2_pbo_slope: float | None = None,
    params: Mapping[str, Any] | None = None,
    n_boot: int = 5000,
    mean_block: float = 8,
    seed: int = 0,
    lo_q: int = 4,
    start: Any = None,
    result: Any = None,
    exposure: pd.Series | None = None,
    expected_period: tuple[Any, Any] | None = None,
    exclude_windows: Sequence[tuple[Any, Any]] | None = None,
    rules: str = "v1.1",
    expected_weeks: Sequence[Any] | pd.DatetimeIndex | None = None,
    dispersion_exclude: Sequence[Any] | pd.DatetimeIndex | None = None,
) -> StatusReport:
    """Statut REJETÉ / CANDIDAT / PROMU selon les critères **exacts** du §8.3.

    Entrées (hebdomadaires W-FRI, nettes de coûts) :

    * ``active_weekly_returns_central`` / ``..._stress`` : rendements actifs
      ``a_w = r_w − b_w`` contre le Composite TR, aux coûts central et stress ;
    * ``benchmark`` : rendements hebdomadaires du TR (la stratégie vaut
      ``r_w = a_w + b_w``) ;
    * ``subperiods`` : les deux sous-périodes (défaut : celles de S1) ;
    * ``turnover`` : rotation moyenne **mensuelle aller** (fraction) ; à défaut,
      calculée depuis ``result`` (``metrics.monthly_one_way_turnover``). Attention :
      ``BacktestResult.turnover`` est **annualisé** ; une valeur > 1 est signalée ;
    * ``pbo`` : PBO de la famille des variantes (9 depuis l'additif v1.1 ; :func:`metrics.family_pbo`),
      ``pbo_slope`` sa pente de dégradation ;
    * ``cvar_ratio`` : CVaR 95 % à 5 séances stratégie / TR
      (:func:`metrics.cvar_ratio`) ;
    * ``s2_active_weekly_returns``, ``s2_ic_monthly``, ``s2_pbo``, ``s2_pbo_slope`` :
      entrées PROPRES au suivi réel S2 (jamais celles de S1 seules). **Règle D7** de
      l'additif v1.1 (``rules="v1.1"``, défaut) : le G7 de S2 s'évalue sur la série d'IC
      **S1 puis S2 mise bout à bout** (``ic_monthly`` suivi de ``s2_ic_monthly``, au moins
      ``ic_min_months`` = 36 mois) ; les autres filtres de S2 (G2-G6, G8, G9, et G4 avec
      ``s2_pbo``) s'évaluent sur S2 seul, avec au moins 12 mois (52 semaines). Sans IC de
      S2, le G7 de S2 n'est pas évaluable et le statut PROMU est impossible. ``rules="v1.0"``
      : lecture prudente antérieure (G7 de S2 sur ``s2_ic_monthly`` seul, au moins
      ``s2_ic_min_months`` mois) ;
    * ``start`` : début COMMUN de la fenêtre d'évaluation (stratégie ET indice) ;
      ``"first_investment"`` : première séance investie de ``result`` / ``exposure``
      (:func:`metrics.first_investment_date`). Sans ``start``, une période de démarrage
      en liquidités de plus de 4 semaines (``result`` ou ``exposure`` fournis) est
      signalée : elle crée un rendement actif mécanique sans lien avec l'alpha. Le choix
      de l'option (fenêtre commune, ou détention du TR pendant le démarrage) doit être
      pré-enregistré avant le test S1 ;
    * ``expected_period`` : période attendue (S1 en validation) ; semaines attendues =
      calendrier **W-FRI** de la période, moins la seule fenêtre du §8.1. Si la couverture
      des semaines (série chaînée, semaines multi-séances comprises) est inférieure à
      ``min_coverage`` (95 %, seuil de mise en œuvre documenté au §8.5 de la
      spécification), l'échantillon est **incomplet** ; la couverture de l'échantillon de
      dispersion (sans les semaines multi-séances) est publiée à côté
      (``couverture_dispersion``) ;
    * ``expected_weeks`` : semaines attendues explicites (prioritaires sur ``expected_period``).
      **Ne jamais** les dériver d'une série calculée avec les mêmes retraits que les
      entrées (p. ex. les semaines de l'étalon) : la couverture vaudrait 100 % par
      construction (garde-fou tautologique corrigé le 22/11/2026) ;
    * ``dispersion_exclude`` : semaines dont l'observation couvre plusieurs séances (trou
      de BOC, :func:`metrics.multi_session_weeks`). Elles restent dans les critères
      **chaînés** (actif net R1, R2, C1, C3 ; drawdowns R4, R5, C4) et sont retirées des
      statistiques de **dispersion** (IR R3, C2 ; Sharpe ; G2-G9) : §3.1.3, « exclu des
      estimations de volatilité […] mais gardé pour chaîner le TR » ;
    * ``exclude_windows`` : semaines exclues des statistiques (défaut :
      ``metrics.EXCLUDE_STATS_WINDOWS``, §8.1) retirées de toutes les entrées.

    Longueur minimale : une sous-période de moins de ``min_weeks_per_subperiod`` semaines
    (52), ou une couverture insuffisante, rend **tous** les critères non évaluables
    (``None``, valeurs mesurées publiées) et le statut vaut ``INDÉTERMINÉ`` (additif v1.1,
    D7 : « données insuffisantes », aucun suivi réel autorisé) : 4 semaines ne suffisent ni à
    un statut CANDIDAT, ni à un rejet.

    Définitions : rendement actif net annualisé = ``CAGR(r) − CAGR(b)`` ; IR
    = ``√52 · moyenne(a) / écart-type(a)`` ; drawdown relatif = drawdown de
    ``Π(1 + r) / Π(1 + b)`` ; drawdown absolu = drawdown de ``Π(1 + r)``.

    Règles (§8.3) :

    * **REJETÉ** si l'une est vraie : (R1) actif central ≤ 0 ; (R2) actif
      stress < −1 %/an ; (R3) IR < −0,5 sur une sous-période ; (R4) drawdown
      relatif < −20 % ; (R5) drawdown absolu pire que celui du TR de plus de
      10 points ;
    * **CANDIDAT** si toutes sont vraies : (C1) actif central > 0 et stress
      ≥ −0,5 %/an ; (C2) IR ≥ 0,20 ; (C3) actif > 0 dans les deux
      sous-périodes ; (C4) drawdown relatif ≥ −20 % ; (C5) rotation ≤ 20 %
      par mois ; (C6) PBO ≤ 0,5 ; (C7) CVaR ≤ 1,25 × celle du TR ;
    * **PROMU** si, en plus, G1-G9 (revue 04 §17.1) sont tous verts sur S1
      **et** sur au moins 12 mois (52 semaines) de suivi réel S2
      (``s2_active_weekly_returns``), avec les entrées propres à S2.

    Un critère non évaluable (donnée manquante) vaut ``None`` : il ne
    déclenche pas de rejet mais empêche le statut candidat ou promu. Le cas
    « ni rejeté, ni candidat », non prévu par le §8.3, renvoie
    ``INDÉTERMINÉ`` (aucun suivi réel autorisé). Ces statuts reposent sur
    des **estimations** : même un statut PROMU ne garantit aucun gain.
    """
    from brvm_alpha.backtest import metrics as mt

    if rules not in RULES_VERSIONS:
        raise ValueError(f"rules doit valoir l'un de {RULES_VERSIONS}")
    th = status_thresholds(params)
    avert: list[str] = []
    windows = mt.EXCLUDE_STATS_WINDOWS if exclude_windows is None else exclude_windows
    expo = exposure
    if expo is None and result is not None and isinstance(getattr(result, "weights", None), pd.DataFrame):
        expo = result.weights.sum(axis=1)
    start_ts: pd.Timestamp | None = None
    if isinstance(start, str) and start == "first_investment":
        start_ts = mt.first_investment_date(expo) if expo is not None else None
        if start_ts is None:
            avert.append("start='first_investment' : exposition inconnue ou nulle, fenêtre non modifiée")
    elif start is not None:
        start_ts = pd.Timestamp(start)
    b = _prep_weekly(benchmark, "indice", windows, avert)
    a_c = _prep_weekly(active_weekly_returns_central, "rendements actifs (central)", windows, avert)
    if start_ts is not None:
        # fenêtre COMMUNE : la stratégie et le TR commencent à la même date
        b = b[b.index >= start_ts]
        a_c = a_c[a_c.index >= start_ts]
    elif expo is not None:
        first = mt.first_investment_date(expo)
        e_start = pd.Series(expo, dtype=float).index.min() if len(pd.Series(expo, dtype=float)) else None
        if first is not None and e_start is not None and (first - pd.Timestamp(e_start)).days > 28:
            avert.append(f"période de démarrage en liquidités du {pd.Timestamp(e_start).date()} au {first.date()} : "
                         "rendement actif mécanique contre le TR, sans lien avec l'alpha ; fixer start= "
                         "(première décision investissable) ou une règle de démarrage pré-enregistrée")
    a_c = a_c.loc[a_c.index.isin(b.index)]
    b_c = b.reindex(a_c.index)
    r_c = a_c + b_c
    # Échantillon de dispersion : sans les semaines multi-séances (§3.1.3).
    multi = (pd.DatetimeIndex(pd.to_datetime(list(dispersion_exclude))) if dispersion_exclude is not None
             else pd.DatetimeIndex([]))
    a_d = a_c.loc[~a_c.index.isin(multi)] if len(multi) else a_c
    periods: Sequence[tuple[Any, Any]] = list(mt.S1_SUBPERIODS) if subperiods is None else subperiods
    subperiods = [(pd.Timestamp(x), pd.Timestamp(y)) for x, y in periods]
    mesures: dict[str, Any] = {"n_semaines": int(a_c.size), "n_semaines_dispersion": int(a_d.size),
                               "semaines_multi_seances": [d for d in a_c.index if d in set(multi)],
                               "debut_evaluation": start_ts}
    # Longueur et couverture de l'échantillon : en dessous, aucun statut favorable.
    min_w = int(th["min_weeks_per_subperiod"])
    sub_n = [int(_slice(a_c, x, y).size) for x, y in subperiods]
    mesures["semaines_sous_periodes"] = sub_n
    too_short = (not subperiods and a_c.size < min_w) or any(n < min_w for n in sub_n)
    if too_short:
        avert.append(f"échantillon trop court ({sub_n or [a_c.size]} semaines ; minimum {min_w} par sous-période) : "
                     "critères R1-R5, C1-C7 et G1-G9 non évaluables (statut INDÉTERMINÉ, D7)")
    if expected_period is not None or expected_weeks is not None:
        if expected_weeks is not None:
            exp_weeks = pd.DatetimeIndex(pd.to_datetime(list(expected_weeks)))
            if start_ts is not None:
                exp_weeks = exp_weeks[exp_weeks >= start_ts]
        else:
            lo, hi = (pd.Timestamp(x) for x in expected_period)  # type: ignore[union-attr]
            exp_weeks = pd.date_range(lo, hi, freq="W-FRI")
        if windows and len(exp_weeks):
            exp_weeks = exp_weeks[mt.weekly_observation_mask(exp_weeks, exp_weeks, exclude_windows=windows,
                                                             max_sessions=None)]
        cov = float(a_c.index.isin(exp_weeks).sum() / len(exp_weeks)) if len(exp_weeks) else math.nan
        mesures["couverture"] = cov
        mesures["couverture_dispersion"] = (float(a_d.index.isin(exp_weeks).sum() / len(exp_weeks))
                                            if len(exp_weeks) else math.nan)
        mesures["semaines_attendues"] = int(len(exp_weeks))
        if not (_finite(cov) and cov >= float(th["min_coverage"])):
            too_short = True
            avert.append(f"couverture de la période attendue {cov:.1%} < {float(th['min_coverage']):.0%} : critères "
                         "R, C et G non évaluables (statut INDÉTERMINÉ, D7)")
    if turnover is None and result is not None:
        turnover = mt.monthly_one_way_turnover(result)
        mesures["rotation_source"] = "metrics.monthly_one_way_turnover(result)"
    if _finite(turnover) and float(turnover) > 1.0:
        avert.append(f"rotation mensuelle {float(turnover):.2f} > 1 (plus de 100 %/mois) invraisemblable : "
                     "BacktestResult.turnover est annualisé ; utiliser metrics.monthly_one_way_turnover(result)")

    act_central = mt.annualized_active_return(r_c, b_c) if a_c.size else math.nan
    act_stress = math.nan
    if active_weekly_returns_stress is not None:
        a_s = _prep_weekly(active_weekly_returns_stress, "rendements actifs (stress)", windows, [])
        if start_ts is not None:
            a_s = a_s[a_s.index >= start_ts]
        a_s = a_s.loc[a_s.index.isin(b.index)]
        if a_s.size:
            act_stress = mt.annualized_active_return(a_s + b.reindex(a_s.index), b.reindex(a_s.index))
    ir = mt.information_ratio(a_d) if a_d.size >= 2 else math.nan
    sub_ir, sub_act = [], []
    for x, y in subperiods:
        sa = _slice(a_c, x, y)
        sd = _slice(a_d, x, y)
        sb = b_c.reindex(sa.index)
        sub_ir.append(mt.information_ratio(sd) if sd.size >= 2 else math.nan)
        sub_act.append(mt.annualized_active_return(sa + sb, sb) if sa.size else math.nan)
    rel_dd = mt.relative_drawdown(r_c, b_c) if a_c.size else math.nan
    abs_dd = mt.max_drawdown(r_c) if a_c.size else math.nan
    tr_dd = mt.max_drawdown(b_c) if a_c.size else math.nan
    gap_dd = abs_dd - tr_dd if _finite(abs_dd) and _finite(tr_dd) else math.nan
    mesures.update(
        {
            "actif_net_central_an": act_central,
            "actif_net_stress_an": act_stress,
            "ir": ir,
            "ir_sous_periodes": sub_ir,
            "actif_sous_periodes_an": sub_act,
            "drawdown_relatif": rel_dd,
            "drawdown_absolu": abs_dd,
            "drawdown_tr": tr_dd,
            "rotation_mensuelle": turnover,
            "pbo": pbo,
            "pbo_pente": pbo_slope,
            "cvar_ratio": cvar_ratio,
            "sharpe_actif": mt.sharpe_triplet(a_d, lo_q=lo_q) if a_d.size > 2 * (lo_q + 2) else None,
        }
    )
    sub_ir_ok = [v for v in sub_ir if _finite(v)]
    r3 = None
    if len(sub_ir_ok) == len(sub_ir) and sub_ir:
        r3 = bool(any(v < th["reject_subperiod_ir_lt"] for v in sub_ir))
    elif any(v < th["reject_subperiod_ir_lt"] for v in sub_ir_ok):
        r3 = True
    rows: list[dict[str, Any]] = [
        {"groupe": "rejet", "code": "R1", "libelle": "rendement actif net annualisé contre le TR (coûts centraux)",
         "valeur": act_central, "seuil": f"≤ {th['reject_active_net_central_le']} ⇒ rejet",
         "verifie": _check(act_central, lambda v: v <= th["reject_active_net_central_le"]), "note": ""},
        {"groupe": "rejet", "code": "R2", "libelle": "rendement actif net annualisé (coûts de stress)",
         "valeur": act_stress, "seuil": f"< {th['reject_active_net_stress_lt']} ⇒ rejet",
         "verifie": _check(act_stress, lambda v: v < th["reject_active_net_stress_lt"]),
         "note": "" if _finite(act_stress) else "rendements au coût de stress non fournis"},
        {"groupe": "rejet", "code": "R3", "libelle": "IR de chaque sous-période", "valeur": sub_ir,
         "seuil": f"< {th['reject_subperiod_ir_lt']} sur l'une ⇒ rejet", "verifie": r3, "note": ""},
        {"groupe": "rejet", "code": "R4", "libelle": "drawdown relatif contre le TR", "valeur": rel_dd,
         "seuil": f"< {th['reject_rel_dd_lt']} ⇒ rejet",
         "verifie": _check(rel_dd, lambda v: v < th["reject_rel_dd_lt"]), "note": ""},
        {"groupe": "rejet", "code": "R5", "libelle": "drawdown absolu moins celui du TR", "valeur": gap_dd,
         "seuil": f"< −{th['reject_abs_dd_worse_than_tr_by']} ⇒ rejet",
         "verifie": _check(gap_dd, lambda v: v < -th["reject_abs_dd_worse_than_tr_by"]),
         "note": f"stratégie {abs_dd:.1%}, TR {tr_dd:.1%}" if _finite(gap_dd) else ""},
    ]
    c1: bool | None
    if not _finite(act_central):
        c1 = None
    elif act_central <= th["candidate_active_net_central_gt"]:
        c1 = False
    else:
        c1 = _check(act_stress, lambda v: v >= th["candidate_active_net_stress_ge"])
    c3 = None if not sub_act or not all(_finite(v) for v in sub_act) else bool(all(v > 0 for v in sub_act))
    rows += [
        {"groupe": "candidat", "code": "C1", "libelle": "actif net > 0 (central) et ≥ −0,5 %/an (stress)",
         "valeur": [act_central, act_stress],
         "seuil": f"> {th['candidate_active_net_central_gt']} et ≥ {th['candidate_active_net_stress_ge']}",
         "verifie": c1, "note": ""},
        {"groupe": "candidat", "code": "C2", "libelle": "IR net", "valeur": ir, "seuil": f"≥ {th['candidate_ir_ge']}",
         "verifie": _check(ir, lambda v: v >= th["candidate_ir_ge"]), "note": ""},
        {"groupe": "candidat", "code": "C3", "libelle": "rendement actif positif dans les deux sous-périodes",
         "valeur": sub_act, "seuil": "> 0 dans chacune", "verifie": c3, "note": ""},
        {"groupe": "candidat", "code": "C4", "libelle": "drawdown relatif contre le TR", "valeur": rel_dd,
         "seuil": f"≥ {th['candidate_rel_dd_ge']}", "verifie": _check(rel_dd, lambda v: v >= th["candidate_rel_dd_ge"]),
         "note": ""},
        {"groupe": "candidat", "code": "C5", "libelle": "rotation moyenne mensuelle aller", "valeur": turnover,
         "seuil": f"≤ {th['candidate_turnover_month_le']}",
         "verifie": _check(turnover, lambda v: v <= th["candidate_turnover_month_le"]),
         "note": "" if _finite(turnover) else "rotation non fournie"},
        {"groupe": "candidat", "code": "C6", "libelle": "PBO de la famille des variantes (N = 9, additif v1.1)", "valeur": pbo,
         "seuil": f"≤ {th['candidate_pbo_le']}", "verifie": _check(pbo, lambda v: v <= th["candidate_pbo_le"]),
         "note": "" if _finite(pbo) else "PBO non fournie"},
        {"groupe": "candidat", "code": "C7", "libelle": "CVaR 95 % à 5 séances / CVaR du TR", "valeur": cvar_ratio,
         "seuil": f"≤ {th['candidate_cvar_ratio_le']}",
         "verifie": _check(cvar_ratio, lambda v: v <= th["candidate_cvar_ratio_le"]),
         "note": "" if _finite(cvar_ratio) else "rapport de CVaR non fourni"},
    ]

    # Filtres G1-G9 (S1 puis S2).
    n_tr = n_trials if n_trials is not None else (registry.n_trials() if registry is not None else None)
    sr_var = sr_variance
    if sr_var is None and registry is not None:
        sr_var = registry.sharpe_variance()
        if not _finite(sr_var):
            sr_var = None
    g1 = registry_complete
    if g1 is None and registry is not None:
        g1 = registry.is_complete(min_trials=int(th["n_trials_start"]))
    common: dict[str, Any] = {
        "n_trials": n_tr,
        "sr_variance": sr_var,
        "g1": g1,
        "new_signal": new_signal,
        "n_boot": n_boot,
        "mean_block": mean_block,
        "seed": seed,
        "lo_q": lo_q,
        "mesures": mesures,
    }
    rows += _g_filters("promotion_S1", a_d, subperiods, th, pbo=pbo if pbo is not None else math.nan,
                       pbo_slope=pbo_slope, ic_monthly=ic_monthly, **common)
    s2_ok = False
    if s2_active_weekly_returns is not None:
        a2 = _prep_weekly(s2_active_weekly_returns, "suivi réel S2", windows, avert)
        mesures["s2_semaines"] = int(a2.size)
        if a2.size >= th["s2_min_weeks"]:
            s2_ok = True
            # Entrées PROPRES à S2 : jamais la PBO ni la pente de S1 (§8.3 : G1-G9 verts « sur S1 ET sur
            # le suivi réel S2 »). Sans IC de S2, G7 vaut None : PROMU impossible.
            s2_ic = None if s2_ic_monthly is None else pd.Series(s2_ic_monthly, dtype=float).dropna()
            if rules == "v1.1":
                # Additif v1.1, D7 : G7 sur la série d'IC S1 puis S2 mise bout à bout (≥ 36 mois).
                g7_ic = None
                if s2_ic is not None:
                    parts = [pd.Series(ic_monthly, dtype=float).dropna()] if ic_monthly is not None else []
                    g7_ic = pd.concat(parts + [s2_ic]).sort_index()
                    g7_ic = g7_ic[~g7_ic.index.duplicated(keep="last")]
                    mesures["promotion_S2_ic_mois_s2_seul"] = int(s2_ic.size)
                g7_min = th["ic_min_months"]
            else:
                g7_ic, g7_min = s2_ic, th["s2_ic_min_months"]
            rows += _g_filters("promotion_S2", a2, [(a2.index[0], a2.index[-1])], th,
                               pbo=s2_pbo if s2_pbo is not None else math.nan, pbo_slope=s2_pbo_slope,
                               ic_monthly=g7_ic, ic_min_months=g7_min, **common)
            if rules == "v1.1":
                for r in rows:
                    if r["groupe"] == "promotion_S2" and r["code"] == "G7":
                        r["libelle"] = "t de Newey-West de l'IC mensuel, séries S1 puis S2 bout à bout (D7)"
            if s2_ic is None:
                avert.append("suivi réel S2 : IC mensuels propres à S2 non fournis (G7 non évaluable) : PROMU "
                             "impossible")
            elif rules == "v1.0" and int(s2_ic.size) < th["s2_ic_min_months"]:
                avert.append(f"suivi réel S2 : moins de {int(th['s2_ic_min_months'])} mois d'IC propres à S2 "
                             "(G7, lecture prudente v1.0 du §8.3)")
        else:
            avert.append(f"suivi réel S2 de {a2.size} semaines < {int(th['s2_min_weeks'])} : promotion impossible")
    else:
        avert.append("aucun suivi réel S2 : le statut PROMU est impossible (au moins 12 mois exigés)")
    if too_short:
        # Échantillon trop court ou incomplet (D7 : « données insuffisantes ») : aucun critère n'est
        # évaluable, ni de rejet ni de candidature ; les valeurs mesurées restent publiées.
        for r in rows:
            r["verifie"] = None
            r["note"] = (r["note"] + " ; " if r["note"] else "") + "échantillon trop court ou incomplet"

    crit = pd.DataFrame(rows, columns=["groupe", "code", "libelle", "valeur", "seuil", "verifie", "note"])
    rejected = bool((crit.loc[crit["groupe"] == "rejet", "verifie"] == True).any())  # noqa: E712
    candidate = bool((crit.loc[crit["groupe"] == "candidat", "verifie"] == True).all())  # noqa: E712
    g_s1 = crit.loc[crit["groupe"] == "promotion_S1", "verifie"]
    g_s2 = crit.loc[crit["groupe"] == "promotion_S2", "verifie"]
    promoted = candidate and s2_ok and bool((g_s1 == True).all()) and len(g_s2) > 0 and bool((g_s2 == True).all())  # noqa: E712
    if rejected:
        statut = STATUT_REJETE
        avert.append("REJETÉ : passage en mode « indice discipliné » (aucune promesse d'alpha), la recherche continue")
    elif promoted:
        statut = STATUT_PROMU
    elif candidate:
        statut = STATUT_CANDIDAT
    else:
        statut = STATUT_INDETERMINE
        if too_short:
            avert.append("INDÉTERMINÉ : données insuffisantes (additif v1.1, D7) : aucun suivi réel autorisé")
        else:
            avert.append("ni rejeté ni candidat (cas non prévu par le §8.3) : aucun suivi réel autorisé")
    if _finite(ir) and ir > 1.0:
        avert.append("IR > 1 : à traiter d'abord comme une ERREUR (anticipation, prix périmés, coûts oubliés), §8.3")
    if mesures.get("sharpe_actif") and mesures["sharpe_actif"].get("divergence"):
        avert.append("écart entre Sharpe de Lo et Sharpe GLM > 25 % : prix périmés à examiner (§8.2)")
    mesures["regles"] = rules
    avert.append("Performance passée ≠ garantie. Aucun gain n'est garanti.")
    return StatusReport(statut=statut, criteres=crit, mesures=mesures, avertissements=avert)


# ---------------------------------------------------------------------------
# Règle de promotion d'une variante (spéc. §3.4)
# ---------------------------------------------------------------------------


@dataclass
class PromotionReport:
    """Résultat de :func:`variant_promotion` : variante principale et détail par variante."""

    principal: str
    criteres: pd.DataFrame
    pbo: float
    n_trials: int
    sr_variance: float
    avertissements: list[str] = field(default_factory=list)


def variant_promotion(
    weekly_active: pd.DataFrame | Mapping[str, pd.Series],
    *,
    benchmark: pd.Series | None = None,
    pbo: float | None = None,
    baseline: str = "A",
    n_trials: int | None = None,
    sr_variance: float | None = None,
    params: Mapping[str, Any] | None = None,
    exclude_windows: Sequence[tuple[Any, Any]] | None = None,
    dispersion_exclude: Sequence[Any] | pd.DatetimeIndex | None = None,
) -> PromotionReport:
    """Règle de promotion pré-enregistrée du §3.4 (« A reste le principal »).

    Une variante X ne remplace A que si, sur l'échantillon de validation, **les trois**
    conditions sont vraies :

    1. X bat A en rendement actif net annualisé (``CAGR(a + b) − CAGR(b)`` si
       ``benchmark`` est fourni, sinon ``52 × moyenne(a)``) ;
    2. DSR(X) ≥ 0,95 avec **N = taille de la famille** (``n_trials`` ; défaut : nombre de
       colonnes de ``weekly_active``, soit **9** pour la famille A-I de l'additif v1.1) ; la
       variance des Sharpe hebdomadaires entre variantes est estimée sur la famille si
       ``sr_variance`` n'est pas fourni ;
    3. PBO de la famille ≤ 0,25 (:func:`metrics.family_pbo` si ``pbo`` n'est pas fourni).

    ``weekly_active`` : rendements actifs hebdomadaires nets (semaines × variantes, ``A``
    compris), sur les semaines communes. ``dispersion_exclude`` : semaines multi-séances
    gardées pour l'actif net (chaîné) et retirées du DSR, de la variance des Sharpe et de la
    PBO (dispersion, §3.1.3). Si plusieurs variantes satisfont la règle, la
    principale devient celle dont le rendement actif net est le plus élevé (choix
    documenté). Un critère non évaluable (NaN) empêche la promotion. Estimations
    seulement : aucune promesse de gain.
    """
    from brvm_alpha.backtest import metrics as mt

    th = status_thresholds(params)
    frame = pd.DataFrame(dict(weekly_active)) if not isinstance(weekly_active, pd.DataFrame) else weekly_active
    frame = frame.astype(float).sort_index()
    if baseline not in frame.columns:
        raise KeyError(f"variante de référence {baseline!r} absente ({list(frame.columns)})")
    avert: list[str] = []
    windows = mt.EXCLUDE_STATS_WINDOWS if exclude_windows is None else exclude_windows
    if windows and len(frame):
        keep = mt.weekly_observation_mask(frame.index, frame.index, exclude_windows=windows, max_sessions=None)
        frame = frame[keep]
    n_all = len(frame)
    frame = frame.dropna(how="any")
    if len(frame) < n_all:
        avert.append(f"{n_all - len(frame)} semaine(s) sans rendement pour toutes les variantes retirée(s)")
    if len(frame) < 2:
        raise ValueError("au moins deux semaines communes à toutes les variantes sont nécessaires")
    if n_trials is None:
        n_trials = int(frame.shape[1])
    b = None
    if benchmark is not None:
        b = pd.Series(benchmark, dtype=float).reindex(frame.index)
        if b.isna().any():
            raise ValueError("benchmark : semaines manquantes sur l'échantillon commun")
    act: dict[str, float] = {}
    sr: dict[str, float] = {}
    disp = mt.dispersion_sample(frame, dispersion_exclude)
    for v in frame.columns:
        a = frame[v]
        act[v] = (mt.annualized_active_return(a + b, b) if b is not None
                  else float(a.mean() * mt.WEEKS_PER_YEAR))
        ad = disp[v]
        sd = float(ad.std(ddof=1))
        sr[v] = float(ad.mean() / sd) if sd > 0 else math.nan
    sr_vals = np.array([x for x in sr.values() if _finite(x)])
    sr_var = float(sr_variance) if sr_variance is not None else (
        float(np.var(sr_vals, ddof=1)) if sr_vals.size > 1 else math.nan)
    pbo_v = math.nan if pbo is None else float(pbo)
    if pbo is None:
        try:
            pbo_v = float(mt.family_pbo(disp)["pbo"])
        except Exception as exc:  # pragma: no cover - historique trop court
            avert.append(f"PBO non calculée ({exc.__class__.__name__} : {exc})")
    rows = []
    for v in frame.columns:
        d = mt.dsr(disp[v], int(n_trials), sr_var) if disp[v].size >= 3 else math.nan
        beats = None if v == baseline else (bool(act[v] > act[baseline]) if _finite(act[v]) else None)
        dsr_ok = _check(d, lambda x: x >= th["dsr_min"])
        pbo_ok = _check(pbo_v, lambda x: x <= th["pbo_max_promoted"])
        promoted = None if v == baseline else (
            None if any(x is None for x in (beats, dsr_ok, pbo_ok)) else bool(beats and dsr_ok and pbo_ok))
        rows.append({"variante": v, "actif_net_an": act[v], "bat_reference": beats, "dsr": d,
                     "dsr_ok": dsr_ok, "pbo": pbo_v, "pbo_ok": pbo_ok, "promue": promoted})
    tab = pd.DataFrame(rows).set_index("variante")
    winners = [v for v in tab.index if tab.loc[v, "promue"] is True]
    principal = baseline
    if winners:
        principal = max(winners, key=lambda v: float(tab.loc[v, "actif_net_an"]))
        if len(winners) > 1:
            avert.append(f"plusieurs variantes satisfont la règle ({', '.join(winners)}) : la plus forte en actif "
                         f"net est retenue ({principal})")
    avert.append(f"règle du §3.4 : DSR avec N = {int(n_trials)}, PBO ≤ {th['pbo_max_promoted']} ; estimations, "
                 "aucune promesse de gain")
    return PromotionReport(principal=principal, criteres=tab, pbo=pbo_v, n_trials=int(n_trials), sr_variance=sr_var,
                           avertissements=avert)
