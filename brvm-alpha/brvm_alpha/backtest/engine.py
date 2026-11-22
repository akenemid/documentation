"""Moteur de backtest quotidien réaliste pour la BRVM (long-only, peu liquide).

Ce module simule, séance par séance, la vie d'un portefeuille d'actions BRVM
piloté par une stratégie ``strategy(asof, view) -> poids cibles``. Il vise à
reproduire les frictions qui, sur un marché étroit, séparent une performance
« papier » d'une performance réellement capturable :

* **pas d'anticipation** : la stratégie ne reçoit qu'une :class:`PanelView`,
  vue des données *tronquée* à la date de décision ``asof`` incluse, quel que
  soit le format (panel large, table longue à colonne ``date``, ``MultiIndex``
  (date, symbol), ``PeriodIndex``, dates en chaînes ; objet daté non
  tronquable ⇒ ``TypeError``), sans accès aux panels complets, et dont les
  cours ajustés sont ramenés aux unités du jour ``asof`` (un ajustement « à
  rebours » trahirait les divisions futures) ; les ordres sont exécutés au
  plus tôt à la séance suivante (t+1) ;
* **titres non échangés** : aucun ordre ne s'exécute un jour sans transaction
  (volume nul, titre non coté ou suspendu) ; la valorisation utilise alors le
  dernier cours connu (prix périmés, cf. Scholes & Williams, 1977 ; Lo &
  MacKinlay, 1990) ;
* **prix d'exécution** : prix moyen pondéré de la séance
  ``VWAP_t = valeur_t / volume_t`` (option ``ExecutionModel.price``) ;
* **plafond de participation** : quantité exécutable
  ``q_t ≤ ⌊π_max · volume_t⌋`` (``π_max = max_volume_participation``) ; le
  reliquat est reporté aux séances suivantes si ``carry_unfilled`` ;
* **limites de variation** (±7,5 % à la BRVM, Instruction I-A) : un titre qui
  clôture à la limite haute signale une file d'acheteurs non servie ⇒ **pas
  d'achat** ; à la limite basse, file de vendeurs ⇒ **pas de vente** (Kim &
  Rhee, 1997, sur l'effet des limites de prix) ;
* **coûts** (cf. :func:`trade_cost`) : frais proportionnels
  ``CostModel.rate()`` (SGI + TVA, BRVM, DC/BR, AMF-UMOA) et impact de marché
  en racine carrée de la participation (Almgren, Thum, Hauptmann & Li, 2005 ;
  Tóth et al., 2011 ; Bouchaud, Bonart, Donier & Gould, 2018) ;
* **quantités entières** (quotité ``lot_size``, 1 par défaut), **cash non
  négatif** (pas d'effet de levier, pas de découvert ; les ventes passent
  avant les achats, qui sont réduits au prorata si nécessaire) ;
* **dividendes** nets crédités en cash à la date de détachement aux titres
  détenus à l'ouverture de cette séance (rendement total), convertis en
  unités ajustées par ``adj_factor`` (``D · f``) ; retenue à la source par
  pays si les montants fournis sont bruts (``TaxModel``). Depuis le panel
  long, la date de détachement vient de ``store.detect_dividends``
  (:func:`panels_from_equities`), pas de la mise à jour tardive de la colonne
  « dernier dividende » du BOC.

Déroulé d'une séance ``t`` (dans cet ordre)
-------------------------------------------
1. rémunération du cash : ``cash ← cash · (1 + r_a)^(1/252)`` ;
2. dividendes : ``cash += Σ_i q_i(t⁻) · D_i(t)`` (``q(t⁻)`` = positions
   d'ouverture, donc un achat du jour de détachement n'y a pas droit) ;
3. droits de garde : ``garde_t = g_a / 252 · Σ_i q_i P_i(t-1)`` (à payer) ;
4. exécution des ordres en attente : **ventes d'abord**, puis achats limités
   par le cash disponible ;
5. valorisation à la clôture : ``NAV_t = cash_t + Σ_i q_i(t) · P̃_i(t)`` où
   ``P̃`` est le dernier cours de clôture connu ;
6. si ``t`` est une date de rebalancement : appel de la stratégie sur la vue
   tronquée à ``t`` et création des ordres (exécutables à partir de t+1).

Dimensionnement des ordres
--------------------------
À la décision (clôture de ``t``), la cible en titres est
``q*_i = ⌊ w_i · NAV_t / (P̃_i(t) · lot) ⌋ · lot`` et l'ordre vaut
``q*_i − q_i(t)``. La quantité est figée à la décision (comme un ordre réel
transmis à la SGI avant l'ouverture) ; un nouveau rebalancement annule et
remplace les ordres encore en attente.

Mesures produites (:class:`BacktestResult`)
-------------------------------------------
* ``equity`` (NAV), ``returns`` ``r_t = NAV_t / NAV_{t-1} − 1`` ;
* ``weights`` quotidiens ``w_{i,t} = q_i(t) P̃_i(t) / NAV_t`` ;
* ``trades`` (``date, symbol, qty, price, value, cost, reason``) ;
* ``costs`` cumulés (FCFA), ``turnover`` annualisé (aller simple)
  ``TO = 252 · moyenne_t[ Σ_i |V_{i,t}| / (2 · NAV_{t-1}) ]`` ;
* ``fill_rate`` = part (en valeur au cours de décision) des ordres exécutés.

Limites connues (choix de prudence documentés)
----------------------------------------------
* Règlement-livraison supposé immédiat (le produit des ventes finance les
  achats du jour) alors qu'il est à J+3 à la BRVM : effet de second ordre
  pour des rebalancements hebdomadaires ou plus lents.
* Le carnet d'ordres n'est pas observé : la file d'attente à la limite est
  approchée par le statut de clôture (à la limite ⇒ non servi).
* Les dates de fin de période (``'M'``, ``'Q'``, ``'W-FRI'``) supposent le
  calendrier des séances connu à l'avance (jours fériés publiés), hypothèse
  standard ; ``anchor="first"`` l'évite.
* Les quantités sont arrondies en titres **ajustés** : avant une division
  future 1:k, une position peut correspondre à une fraction de titre réel
  (écart < 1 titre réel par ligne, négligeable en valeur).
* Seuls ``close`` et ``adj_factor`` sont remis aux unités du jour de décision
  dans la vue ; un autre panel fourni en unités ajustées à rebours resterait
  dépendant des divisions futures.

Références
----------
* Almgren, R., Thum, C., Hauptmann, E. & Li, H. (2005). Direct Estimation of
  Equity Market Impact. *Risk*, 18(7), 58-62.
* Bouchaud, J.-P., Bonart, J., Donier, J. & Gould, M. (2018). *Trades,
  Quotes and Prices*. Cambridge University Press (loi en racine carrée).
* Kim, K. A. & Rhee, S. G. (1997). Price Limit Performance: Evidence from
  the Tokyo Stock Exchange. *Journal of Finance*, 52(2), 885-901.
* Lo, A. W. & MacKinlay, A. C. (1990). An Econometric Analysis of
  Nonsynchronous Trading. *Journal of Econometrics*, 45(1-2), 181-211.
* Perold, A. F. (1988). The Implementation Shortfall: Paper versus Reality.
  *Journal of Portfolio Management*, 14(3), 4-9.
* Scholes, M. & Williams, J. (1977). Estimating Betas from Nonsynchronous
  Data. *Journal of Financial Economics*, 5(3), 309-327.
* Tóth, B., Lempérière, Y., Deremble, C., de Lataillade, J., Kockelkoren, J.
  & Bouchaud, J.-P. (2011). Anomalous Price Impact and the Critical Nature
  of Liquidity in Financial Markets. *Physical Review X*, 1(2), 021006.
* López de Prado, M. (2018). *Advances in Financial Machine Learning*.
  Wiley, ch. 11-12 (dangers du backtest, biais d'anticipation).
"""

from __future__ import annotations

import math
import numbers
import warnings
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from brvm_alpha.config import Constraints, CostModel, ExecutionModel, PlatformConfig, TaxModel

__all__ = [
    "BacktestResult",
    "Backtester",
    "PanelView",
    "Strategy",
    "limit_flags",
    "panels_from_equities",
    "rebalance_dates",
    "trade_cost",
    "truncate_asof",
]

TRADING_DAYS = 252

#: Signature d'une stratégie : ``(asof, vue tronquée) -> poids cibles``.
#: ``None`` signifie « ne rien changer » (les ordres en attente sont conservés).
Strategy = Callable[[pd.Timestamp, Mapping[str, Any]], "pd.Series | Mapping[str, float] | None"]

_BLOCKING_STATUS = frozenset({"suspended", "not_traded"})

# Alias de fréquences « fin de période » (offsets pandas) -> fréquence de période.
_PERIOD_ALIASES = {
    "M": "M",
    "ME": "M",
    "BM": "M",
    "BME": "M",
    "MS": "M",
    "BMS": "M",
    "Q": "Q",
    "QE": "Q",
    "BQ": "Q",
    "BQE": "Q",
    "QS": "Q",
    "BQS": "Q",
    "Y": "Y",
    "YE": "Y",
    "A": "Y",
    "BA": "Y",
    "BY": "Y",
    "YS": "Y",
    "AS": "Y",
    "W": "W",
}
_DAILY_RULES = frozenset({"D", "B", "1D", "1B", "C"})


# ---------------------------------------------------------------------------
# Vue tronquée (garantie d'absence d'anticipation)
# ---------------------------------------------------------------------------


#: Noms (insensibles à la casse) d'une colonne ou d'un niveau d'index de dates
#: dans une table longue (schéma ``indices.parquet``, ``corporate_actions.parquet``).
_DATE_LABELS = frozenset({"date"})

#: Scalaires sans dimension temporelle, transmis tels quels à la stratégie.
_STATIC_SCALARS = (str, bytes, bool, numbers.Number, np.bool_, np.str_, np.bytes_)


def _is_date_label(name: Any) -> bool:
    return isinstance(name, str) and name.strip().lower() in _DATE_LABELS


def _parse_date_index(values: pd.Index) -> pd.DatetimeIndex | None:
    """Interprète un index de chaînes (ou d'objets ``date``) comme des dates.

    Renvoie ``None`` si ``values`` n'est pas un index de dates : type numérique,
    booléen ou catégoriel, élément sans chiffre (un code BRVM comme ``SNTS``
    n'est jamais une date) ou élément non convertible. Les ``DatetimeIndex``
    sont renvoyés tels quels ; ``PeriodIndex`` et ``MultiIndex`` sont traités
    à part (``None``).

    Formats : ISO 8601 (``AAAA-MM-JJ[ hh:mm…]``) et ``AAAAMMJJ`` sans
    ambiguïté ; tout autre format est lu dans les deux ordres (jour/mois et
    mois/jour) : une divergence (``01/12/2021`` = 1er décembre en français,
    12 janvier en anglais) pourrait avancer une date et faire fuiter le
    futur, elle lève donc ``TypeError``.

    Raises
    ------
    TypeError
        Dates en chaînes ambiguës (ordre jour/mois indéterminé).
    """
    if isinstance(values, pd.DatetimeIndex):
        return values
    if isinstance(values, (pd.PeriodIndex, pd.MultiIndex, pd.CategoricalIndex)):
        return None
    if not (values.dtype == object or pd.api.types.is_string_dtype(values.dtype)):
        return None
    present = np.asarray(values.notna(), dtype=bool)
    if len(values) == 0 or not present.any():
        return None
    as_text = pd.Index(values[present]).astype(str).str.strip()
    if not bool(as_text.str.contains(r"\d", regex=True).all()):
        return None

    def attempt(**kw: Any) -> pd.DatetimeIndex | None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                cand = pd.DatetimeIndex(pd.to_datetime(values, errors="coerce", **kw))
            except (TypeError, ValueError, OverflowError):
                return None
        return None if bool(np.asarray(cand.isna())[present].any()) else cand

    if bool(as_text.str.fullmatch(r"\d{4}-\d{2}-\d{2}([ T].*)?").all()):
        return attempt(format="ISO8601")
    if bool(as_text.str.fullmatch(r"\d{8}").all()):
        return attempt(format="%Y%m%d")
    month_first = attempt(format="mixed")
    day_first = attempt(format="mixed", dayfirst=True)
    if month_first is not None and day_first is not None and not month_first.equals(day_first):
        raise TypeError("dates en chaînes ambiguës (ordre jour/mois indéterminé) : convertir en DatetimeIndex")
    return month_first if month_first is not None else day_first


def _cutoff_for(asof: pd.Timestamp, tz: Any) -> pd.Timestamp:
    """``asof`` exprimé dans le fuseau d'un index (comparaison sans erreur)."""
    if tz is None:
        return asof.tz_localize(None) if asof.tz is not None else asof
    return asof.tz_localize(tz) if asof.tz is None else asof.tz_convert(tz)


def _datetime_selector(values: pd.DatetimeIndex, asof: pd.Timestamp) -> slice | np.ndarray:
    """Sélection des positions ``≤ asof`` (tranche si trié, masque sinon ; NaT exclu)."""
    cut = _cutoff_for(asof, values.tz)
    if values.is_monotonic_increasing and not values.hasnans:
        return slice(0, int(values.searchsorted(cut, side="right")))
    return np.asarray(values <= cut, dtype=bool)


def _period_selector(values: pd.PeriodIndex, asof: pd.Timestamp) -> np.ndarray:
    """Périodes **terminées** au plus tard le jour de ``asof``.

    Une période (mois, trimestre…) n'est connue qu'à sa fin : la donnée de
    janvier n'est visible qu'à partir du 31 janvier (``end_time`` ramené au
    jour). Les périodes quotidiennes du jour ``asof`` sont visibles.
    """
    ends = pd.DatetimeIndex(values.end_time).normalize()
    return np.asarray(ends <= _cutoff_for(asof, None).normalize(), dtype=bool)


def _date_level(idx: pd.MultiIndex) -> int | None:
    """Niveau de dates d'un ``MultiIndex`` : nommé ``date``, sinon le premier niveau daté."""
    for i, name in enumerate(idx.names):
        if _is_date_label(name):
            return i
    for i in range(idx.nlevels):
        lv = idx.levels[i]
        if isinstance(lv, (pd.DatetimeIndex, pd.PeriodIndex)):
            return i
    return None


def _index_selector(idx: pd.Index, asof: pd.Timestamp) -> slice | np.ndarray | None:
    """Sélection des lignes ``≤ asof`` selon l'index, ou ``None`` si l'index n'est pas daté."""
    if isinstance(idx, pd.MultiIndex):
        lev = _date_level(idx)
        if lev is None:
            return None
        values = idx.get_level_values(lev)
        if isinstance(values, pd.PeriodIndex):
            return _period_selector(values, asof)
        parsed = _parse_date_index(values)
        if parsed is None:
            if _is_date_label(idx.names[lev]):
                raise TypeError(f"niveau d'index {idx.names[lev]!r} non convertible en dates")
            return None
        return _datetime_selector(parsed, asof)
    if isinstance(idx, pd.PeriodIndex):
        return _period_selector(idx, asof)
    parsed = _parse_date_index(idx)
    if parsed is None:
        return None
    return _datetime_selector(parsed, asof)


def _as_date_column(col: pd.Series, name: Any) -> pd.DatetimeIndex:
    """Colonne ``date`` d'une table longue convertie en ``DatetimeIndex`` (erreur sinon)."""
    if isinstance(col.dtype, pd.PeriodDtype):
        return pd.DatetimeIndex(pd.PeriodIndex(col).end_time).normalize()
    if pd.api.types.is_datetime64_any_dtype(col.dtype):
        return pd.DatetimeIndex(col)
    parsed = _parse_date_index(pd.Index(col))
    if parsed is None:
        raise TypeError(f"colonne {name!r} non convertible en dates")
    return parsed


def _has_dated_values(obj: pd.Series | pd.DataFrame) -> bool:
    """Vrai si un objet pandas *non indexé par des dates* contient des dates."""
    if isinstance(obj, pd.Series):
        dtypes = [obj.dtype]
    else:
        dtypes = list(obj.dtypes)
        cols = obj.columns
        if isinstance(cols, (pd.DatetimeIndex, pd.PeriodIndex)) or (
            not isinstance(cols, pd.MultiIndex) and _parse_date_index(cols) is not None
        ):
            return True  # panel transposé : dates en colonnes
    return any(pd.api.types.is_datetime64_any_dtype(d) or isinstance(d, pd.PeriodDtype) for d in dtypes)


def _truncate_pandas(obj: pd.Series | pd.DataFrame, asof: pd.Timestamp) -> pd.Series | pd.DataFrame:
    sel = _index_selector(obj.index, asof)
    if sel is not None:
        return obj.iloc[sel]
    if isinstance(obj, pd.DataFrame):
        date_cols = [c for c in obj.columns if _is_date_label(c)]
        if date_cols:
            name = date_cols[0]
            col = obj.loc[:, name]
            if isinstance(col, pd.DataFrame):
                raise TypeError(f"colonne de dates {name!r} en double")
            return obj.iloc[_datetime_selector(_as_date_column(col, name), asof)]
    if _has_dated_values(obj):
        raise TypeError(
            "objet pandas daté mais non indexé par des dates (valeurs datetime ou dates en colonnes) : "
            "impossible de le tronquer sans risque d'anticipation ; l'indexer par la date de publication "
            "ou ajouter une colonne 'date'"
        )
    return obj.copy(deep=False)


def truncate_asof(obj: Any, asof: Any) -> Any:
    """Restreint un objet daté aux observations ``≤ asof`` (aucune anticipation).

    Règles, dans cet ordre :

    * ``DataFrame`` / ``Series`` dont l'index est un ``DatetimeIndex``, un
      index de **chaînes de dates** (CSV lu sans ``parse_dates``) : lignes de
      date ``≤ asof`` (``iloc[: searchsorted(asof, "right")]`` si l'index est
      trié, masque booléen sinon ; ``NaT`` exclu) ;
    * ``PeriodIndex`` : périodes **terminées** au plus tard le jour ``asof``
      (``end_time`` ramené au jour ``≤ asof`` : le mois de janvier n'est
      visible qu'au 31 janvier) ;
    * ``MultiIndex`` : troncature sur le niveau nommé ``date`` (à défaut, le
      premier niveau de type date ou période), p. ex. ``(date, symbol)`` ;
    * table longue avec une colonne ``date`` (schéma ``indices.parquet``,
      ``corporate_actions.parquet``) : lignes de date ``≤ asof`` ;
    * autre objet pandas **sans date** (p. ex. ``Series`` symbole → pays) :
      copie superficielle (*copy-on-write* : une modification par la
      stratégie ne remonte jamais aux données du moteur) ; s'il contient des
      dates (valeurs ``datetime``, dates en colonnes) : ``TypeError`` ;
    * ``pd.Index`` : dates ``≤ asof`` s'il est daté, inchangé sinon ;
    * ``Mapping`` (dict), ``list``, ``tuple``, ``set`` : troncature récursive
      de chaque élément ;
    * scalaires sans date (``str``, nombres, booléens, ``None``) : inchangés ;
    * tout autre objet (tableau ``numpy``, date isolée, objet arbitraire),
      dont l'alignement temporel est inconnu : ``TypeError`` plutôt qu'une
      transmission silencieuse du futur.

    Raises
    ------
    TypeError
        Objet daté que la fonction ne sait pas tronquer.
    """
    asof = pd.Timestamp(asof)
    if isinstance(obj, (pd.DataFrame, pd.Series)):
        return _truncate_pandas(obj, asof)
    if isinstance(obj, pd.Index):
        sel = _index_selector(obj, asof)
        return obj if sel is None else obj[sel]
    if isinstance(obj, Mapping):
        return {k: truncate_asof(v, asof) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set, frozenset)):
        items = [truncate_asof(x, asof) for x in obj]
        if isinstance(obj, tuple) and hasattr(obj, "_fields"):
            return type(obj)(*items)
        return type(obj)(items)
    if obj is None or (isinstance(obj, _STATIC_SCALARS) and not isinstance(obj, (np.datetime64, np.timedelta64))):
        return obj
    raise TypeError(
        f"objet de type {type(obj).__name__} non tronquable à la date de décision (risque d'anticipation) : "
        "fournir un DataFrame/Series indexé par date, une table longue avec colonne 'date' ou un objet statique"
    )


class PanelView(Mapping[str, Any]):
    """Vue en lecture seule des panels, tronquée à la date de décision ``asof``.

    Chaque accès ``view[clé]`` renvoie l'objet source restreint aux dates
    ``≤ asof`` (:func:`truncate_asof`, calcul paresseux mis en cache pour la
    durée de l'appel de la stratégie). Aucune ligne postérieure à ``asof``
    n'est donc accessible par la vue : ``view["close"].index.max() ≤ asof``,
    quel que soit le format (panel large, table longue à colonne ``date``,
    ``MultiIndex`` (date, symbol), ``PeriodIndex``, index de dates en
    chaînes) ; un objet daté non reconnu lève ``TypeError``. Avec le
    *copy-on-write* de pandas ≥ 3, une écriture de la stratégie sur un objet
    renvoyé ne modifie jamais les données du moteur.

    Les panels source ne sont **pas** exposés : ils ne sont accessibles qu'à
    travers une fermeture privée qui applique la troncature (pas d'attribut
    ``_source`` ; Python n'offre pas d'encapsulation absolue, mais aucun
    accès accidentel au futur n'est possible).

    Parameters
    ----------
    panels
        Dictionnaire des données (non tronquées).
    asof
        Date de décision.
    nav, cash, positions, weights, pending
        État du portefeuille à la clôture de ``asof`` (attributs informatifs).
    rescale
        ``{clé: Series symbole → facteur}`` : facteurs multiplicatifs par
        colonne appliqués après troncature. Le moteur l'utilise pour exprimer
        ``close`` et ``adj_factor`` en **unités du jour de décision**
        (``P_t · f_t / f_asof``) : un cours ajusté « à rebours » dépend des
        divisions *postérieures* à ``asof`` (Π des ratios futurs), ce qui
        révélerait une division à venir ; après remise à l'échelle,
        ``view["close"].iloc[-1]`` est le cours publié le jour ``asof``.

    Attributs : ``asof``, ``nav``, ``cash``, ``positions`` (titres détenus),
    ``weights`` (poids courants), ``pending`` (ordres en attente, en titres).
    Quand le moteur remet la vue à l'échelle (``adj_factor`` ≠ 1), ``positions``
    et ``pending`` sont aussi exprimés en titres du jour ``asof``
    (``q · f_asof``, ``float``) ; sinon ce sont des entiers.
    """

    __slots__ = ("__fetch", "__keys", "_asof", "_cache", "cash", "nav", "pending", "positions", "weights")

    def __init__(
        self,
        panels: Mapping[str, Any],
        asof: pd.Timestamp,
        *,
        nav: float | None = None,
        cash: float | None = None,
        positions: pd.Series | None = None,
        weights: pd.Series | None = None,
        pending: pd.Series | None = None,
        rescale: Mapping[str, pd.Series] | None = None,
    ) -> None:
        stamp = pd.Timestamp(asof)
        scales = dict(rescale or {})
        source = panels

        def fetch(key: str) -> Any:
            out = truncate_asof(source[key], stamp)
            factor = scales.get(key)
            if factor is not None and isinstance(out, pd.DataFrame):
                out = out * factor.reindex(out.columns).fillna(1.0)
            return out

        self.__fetch = fetch
        self.__keys = tuple(panels)
        self._asof = stamp
        self._cache: dict[str, Any] = {}
        self.nav = nav
        self.cash = cash
        self.positions = positions
        self.weights = weights
        self.pending = pending

    @property
    def asof(self) -> pd.Timestamp:
        """Date de décision (dernière date visible)."""
        return self._asof

    def __getitem__(self, key: str) -> Any:
        if key not in self._cache:
            if key not in self.__keys:
                raise KeyError(key)
            self._cache[key] = self.__fetch(key)
        return self._cache[key]

    def __contains__(self, key: object) -> bool:
        return key in self.__keys

    def __iter__(self) -> Iterator[str]:
        return iter(self.__keys)

    def __len__(self) -> int:
        return len(self.__keys)

    def __repr__(self) -> str:
        return f"PanelView(asof={self._asof.date()}, keys={list(self.__keys)})"


# ---------------------------------------------------------------------------
# Calendrier de rebalancement
# ---------------------------------------------------------------------------


def rebalance_dates(
    calendar: Sequence[Any] | pd.DatetimeIndex,
    rule: str | int | Sequence[Any] | pd.DatetimeIndex | None,
    *,
    start: Any = None,
    end: Any = None,
    anchor: str = "last",
) -> pd.DatetimeIndex:
    """Dates de décision (séances) d'un calendrier de rebalancement.

    Parameters
    ----------
    calendar
        Séances disponibles (triées ou non, doublons tolérés).
    rule
        * ``'W-FRI'`` (ou ``'W'``), ``'M'``/``'ME'``, ``'Q'``/``'QE'``,
          ``'Y'``/``'YE'`` (suffixes d'ancrage acceptés, p. ex. ``'Q-DEC'``) :
          une décision par période, à la **dernière** séance de la période
          (``anchor="last"``) ou à la première (``anchor="first"``) ;
        * ``'D'`` / ``'B'`` : chaque séance ;
        * entier ``n`` : une séance sur ``n`` à partir de la première ;
        * liste de dates : chaque date est ramenée à la dernière séance
          ``≤ date`` (information disponible), doublons supprimés ;
        * ``None`` : la première séance uniquement (achat-conservation).
    start, end
        Bornes (incluses) appliquées au calendrier.
    anchor
        ``"last"`` (défaut) ou ``"first"``.

    Returns
    -------
    pandas.DatetimeIndex
        Dates triées, sans doublon, toutes présentes dans ``calendar``.
    """
    if anchor not in ("last", "first"):
        raise ValueError("anchor doit valoir 'last' ou 'first'")
    cal = pd.DatetimeIndex(pd.to_datetime(pd.Index(calendar))).dropna().unique().sort_values()
    if start is not None:
        cal = cal[cal >= pd.Timestamp(start)]
    if end is not None:
        cal = cal[cal <= pd.Timestamp(end)]
    if len(cal) == 0:
        return pd.DatetimeIndex([])
    if rule is None:
        return cal[:1]
    if isinstance(rule, (bool, np.bool_)):
        raise TypeError("rule booléen non supporté")
    if isinstance(rule, (int, np.integer)):
        if rule < 1:
            raise ValueError("un pas entier de rebalancement doit être >= 1")
        return cal[:: int(rule)]
    if isinstance(rule, str):
        head, sep, tail = rule.strip().upper().partition("-")
        if head in _DAILY_RULES and not sep:
            return cal
        if head not in _PERIOD_ALIASES:
            raise ValueError(f"règle de rebalancement inconnue : {rule!r}")
        base = _PERIOD_ALIASES[head]
        if base == "W" and not sep:
            tail, sep = "FRI", "-"
        freq = base + (sep + tail if sep else "")
        periods = cal.to_period(freq)
        s = pd.Series(cal, index=cal)
        grouped = s.groupby(np.asarray(periods.asi8), sort=True)
        picked = grouped.max() if anchor == "last" else grouped.min()
        return pd.DatetimeIndex(picked.to_numpy()).sort_values()
    # liste de dates
    wanted = pd.DatetimeIndex(pd.to_datetime(pd.Index(rule))).dropna()
    pos = cal.searchsorted(wanted, side="right") - 1
    pos = pos[pos >= 0]
    return pd.DatetimeIndex(cal[np.unique(pos)])


# ---------------------------------------------------------------------------
# Coûts et limites
# ---------------------------------------------------------------------------


def trade_cost(
    amount: np.ndarray | float,
    participation: np.ndarray | float,
    costs: CostModel,
) -> np.ndarray:
    """Coût total (FCFA) d'une exécution de montant ``A`` à la participation ``π``.

    ``coût = max(τ · A, m) + κ · sqrt(π) · A`` pour ``A > 0`` (0 sinon), avec
    ``τ = CostModel.rate()`` (frais proportionnels d'un aller simple, TVA sur
    la commission SGI incluse), ``m = min_ticket_fcfa`` (minimum de frais par
    ordre) et ``κ = impact_coef``. ``π = q / volume_jour`` ∈ [0, 1].

    Le terme ``κ sqrt(π)`` est la « loi en racine carrée » de l'impact de
    marché (Almgren et al., 2005 ; Tóth et al., 2011), exprimée ici en
    fraction du montant et calibrée par ``impact_coef`` ; elle est comptée
    comme un coût (équivalent d'un prix d'exécution dégradé).
    """
    a = np.asarray(amount, dtype=float)
    p = np.clip(np.asarray(participation, dtype=float), 0.0, None)
    positive = a > 0
    prop = np.where(positive, np.maximum(costs.rate() * a, float(costs.min_ticket_fcfa)), 0.0)
    impact = np.where(positive, float(costs.impact_coef) * np.sqrt(p) * a, 0.0)
    return prop + impact


def limit_flags(
    move: pd.DataFrame | np.ndarray,
    price_limit: float = 0.075,
    tolerance: float = 0.002,
    max_plausible_move: float = 0.20,
) -> tuple[np.ndarray, np.ndarray]:
    """Indicateurs « clôture à la limite haute / basse ».

    Avec ``m_t = P_t / R_t − 1`` la variation de la séance par rapport au
    cours de référence ``R_t`` et ``L = price_limit − tolerance`` :

    * limite haute : ``m_t ≥ L`` ; limite basse : ``m_t ≤ −L`` ;
    * une variation ``|m_t| > max_plausible_move`` (impossible sous la bande
      de ±7,5 %) signale un cours de référence non ajusté (division du
      nominal, détachement) : elle n'est **pas** interprétée comme une limite.
    NaN ⇒ pas de limite.

    Returns
    -------
    (limit_up, limit_down)
        Tableaux booléens de même forme que ``move``.
    """
    m = np.asarray(move, dtype=float)
    thr = float(price_limit) - float(tolerance)
    with np.errstate(invalid="ignore"):
        plausible = np.isfinite(m) & (np.abs(m) <= float(max_plausible_move))
        up = plausible & (m >= thr)
        down = plausible & (m <= -thr)
    return up, down


# ---------------------------------------------------------------------------
# Résultat
# ---------------------------------------------------------------------------


def _minimal_summary(returns: pd.Series, benchmark: pd.Series | None, rf: float, periods: int) -> dict[str, Any]:
    """Métriques minimales (repli si ``brvm_alpha.quant.stats`` est absent)."""
    r = returns.dropna().to_numpy(dtype=float)
    out: dict[str, Any] = {"n_obs": int(r.size)}
    if r.size == 0:
        return out
    wealth = np.cumprod(1.0 + r)
    total = float(wealth[-1] - 1.0)
    cagr = float(wealth[-1] ** (periods / r.size) - 1.0) if wealth[-1] > 0 else -1.0
    rf_p = (1.0 + rf) ** (1.0 / periods) - 1.0
    sd = float(np.std(r, ddof=1)) if r.size > 1 else math.nan
    excess = r - rf_p
    sharpe = float(math.sqrt(periods) * excess.mean() / sd) if sd and sd > 0 else math.nan
    peak = np.maximum.accumulate(np.maximum(wealth, 1.0))
    out.update(
        total_return=total,
        cagr=cagr,
        vol=float(sd * math.sqrt(periods)) if np.isfinite(sd) else math.nan,
        sharpe=sharpe,
        max_drawdown=float(np.min(wealth / peak - 1.0)),
        hit_rate=float(np.mean(r > 0)),
    )
    if benchmark is not None:
        b = benchmark.reindex(returns.index).dropna()
        common = returns.reindex(b.index).dropna()
        b = b.reindex(common.index)
        if len(common) > 1:
            bw = float(np.prod(1.0 + b.to_numpy()))
            b_cagr = bw ** (periods / len(b)) - 1.0 if bw > 0 else -1.0
            sw = float(np.prod(1.0 + common.to_numpy()))
            s_cagr = sw ** (periods / len(common)) - 1.0 if sw > 0 else -1.0
            active = common - b
            te = float(active.std(ddof=1) * math.sqrt(periods))
            out.update(
                benchmark_cagr=b_cagr,
                excess_cagr=s_cagr - b_cagr,
                tracking_error=te,
                information_ratio=float(active.mean() * periods / te) if te > 0 else math.nan,
            )
    return out


#: Rendement quotidien d'indice au-delà duquel une série est jugée mal interprétée
#: (un indice d'actions ne varie pas de 50 % en une séance ; à la BRVM, chaque
#: titre est limité à ±7,5 %).
_MAX_ABS_BENCH_RETURN = 0.5


def _benchmark_returns(
    benchmark: pd.Series | pd.DataFrame, index: pd.DatetimeIndex, is_level: bool | None
) -> pd.Series:
    """Convertit un indice de référence (niveaux ou rendements) en rendements alignés.

    Niveaux ``I_t`` : ``r_t = I_t / I_{t-1} − 1`` sur les séances du backtest
    (dernier niveau connu reporté, jamais de remplissage arrière).

    Détection automatique (``is_level=None``) : une série de rendements
    quotidiens n'est jamais **entièrement** positive (elle contient des
    baisses), alors qu'un niveau d'indice l'est toujours, qu'il soit en points
    (≈ 200) ou normalisé à 1 (``tr / tr.iloc[0]``, valeurs ≈ 0,9-1,3) : toutes
    les valeurs ``> 0`` ⇒ niveaux, sinon rendements. Contrôle de cohérence :
    si les rendements obtenus dépassent ``|r| > 0,5`` à une séance (impossible
    pour un indice d'actions), la série est ambiguë (niveaux comportant des
    valeurs ≤ 0, rendements tous positifs sur une série très courte,
    rendements en %) ⇒ ``ValueError`` invitant à préciser ``benchmark_is_level``.
    Avec ``is_level`` explicite, un tel dépassement donne un avertissement.
    """
    if isinstance(benchmark, pd.DataFrame):
        if benchmark.shape[1] != 1:
            raise ValueError("benchmark : une seule colonne attendue")
        benchmark = benchmark.iloc[:, 0]
    b = benchmark.astype(float)
    if not isinstance(b.index, pd.DatetimeIndex):
        parsed = _parse_date_index(b.index)
        if parsed is None:
            raise TypeError("benchmark : index de dates attendu")
        b = b.set_axis(parsed)
    b = b.sort_index()
    b = b[~b.index.duplicated(keep="last")]
    vals = b.dropna()
    auto = is_level is None
    if auto:
        is_level = bool(len(vals) > 0 and (vals > 0).all())
    if is_level:
        lvl = b.reindex(b.index.union(index)).ffill()
        out = lvl.reindex(index).pct_change().iloc[1:].reindex(index)
    else:
        out = b.reindex(index)
    worst = float(out.abs().max()) if out.notna().any() else 0.0
    if worst > _MAX_ABS_BENCH_RETURN:
        kind = "niveaux" if is_level else "rendements"
        msg = (
            f"benchmark interprété comme des {kind} : rendement quotidien de {worst:.0%} invraisemblable "
            "pour un indice"
        )
        if auto:
            raise ValueError(msg + " ; préciser benchmark_is_level=True (niveaux) ou False (rendements décimaux)")
        warnings.warn(msg, stacklevel=3)
    return out


@dataclass
class BacktestResult:
    """Résultat d'un backtest (toutes les séries sont indexées par séance).

    Attributes
    ----------
    equity
        Valeur liquidative ``NAV_t`` (FCFA), clôture de chaque séance.
    returns
        Rendements simples ``NAV_t / NAV_{t-1} − 1`` (``NAV_{-1}`` = capital).
    weights
        Poids quotidiens ``q_i P̃_i / NAV`` (date × symbole) ; le complément à 1
        est la poche de liquidités (``cash / equity``).
    trades
        Exécutions : ``date, symbol, qty`` (signée : > 0 achat, < 0 vente),
        ``price`` (prix d'exécution), ``value`` (``|qty| × price`` ≥ 0),
        ``cost`` (frais + impact), ``reason`` (``"rebalance"`` si exécuté à la
        première séance suivant la décision, ``"carry"`` pour un reliquat
        reporté), ``decision_date``, ``participation``, ``impact``.
    costs
        Coûts cumulés (frais de transaction + impact + droits de garde, FCFA).
    turnover
        Rotation annualisée aller simple ``252 · mean(Σ|V| / (2 NAV_{t-1}))``.
    fill_rate
        ``Σ |exécuté| · P_déc / Σ |ordonné| · P_déc`` (valeur au cours de
        décision ``P_déc``) ; NaN sans ordre.
    cash, positions
        Liquidités et nombres de titres détenus en fin de séance.
    dividends, taxes
        Dividendes crédités et impôts payés (retenue appliquée par le moteur,
        impôt sur plus-values) par séance.
    costs_daily, turnover_daily
        Coûts et rotation de chaque séance.
    orders
        Journal des ordres (décision, symbole, quantité, exécuté, statut).
    blocked
        Événements de non-exécution (``date, symbol, side, qty, reason`` avec
        ``reason`` ∈ ``not_traded``, ``limit_up``, ``limit_down``,
        ``volume_cap``, ``cash``).
    rebalance_dates
        Dates de décision effectivement utilisées.
    """

    equity: pd.Series
    returns: pd.Series
    weights: pd.DataFrame
    trades: pd.DataFrame
    costs: pd.Series
    turnover: float
    fill_rate: float
    cash: pd.Series
    positions: pd.DataFrame
    dividends: pd.Series
    taxes: pd.Series
    costs_daily: pd.Series
    turnover_daily: pd.Series
    orders: pd.DataFrame
    blocked: pd.DataFrame
    rebalance_dates: pd.DatetimeIndex
    capital: float
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def total_costs(self) -> float:
        """Coûts totaux (FCFA)."""
        return float(self.costs.iloc[-1]) if len(self.costs) else 0.0

    def summary(
        self,
        benchmark: pd.Series | pd.DataFrame | None = None,
        rf: float = 0.0,
        *,
        benchmark_is_level: bool | None = None,
        periods_per_year: int = TRADING_DAYS,
    ) -> dict[str, Any]:
        """Synthèse de performance, nette de tous les frais.

        Appelle ``brvm_alpha.quant.stats.perf_summary`` (import paresseux) si
        le module est disponible, sinon calcule des métriques minimales (CAGR,
        volatilité, Sharpe, drawdown maximal, et si un indice est fourni :
        CAGR de l'indice, excès de CAGR, tracking error, ratio
        d'information). Ajoute les mesures propres au backtest : coûts totaux,
        ``cost_drag`` (coûts annualisés / NAV moyenne), rotation, taux
        d'exécution, nombre d'exécutions, dividendes, valeur finale.

        Parameters
        ----------
        benchmark
            Indice de référence (idéalement le **BRVM Composite Total
            Return** : l'indice de prix omet ≈ 7 %/an de dividendes), en
            niveaux ou en rendements simples.
        rf
            Taux sans risque annuel.
        benchmark_is_level
            ``True`` niveaux, ``False`` rendements, ``None`` détection
            automatique : valeurs toutes > 0 ⇒ niveaux (y compris un indice
            normalisé à 1), sinon rendements ; ``ValueError`` si le résultat
            est invraisemblable (``|r| > 0,5`` à une séance), cf.
            :func:`_benchmark_returns`.
        """
        bench = None
        if benchmark is not None:
            bench = _benchmark_returns(benchmark, pd.DatetimeIndex(self.returns.index), benchmark_is_level)
        try:
            from brvm_alpha.quant.stats import perf_summary
        except ImportError:  # pragma: no cover - dépend des modules installés
            out = _minimal_summary(self.returns, bench, rf, periods_per_year)
        else:
            out = dict(perf_summary(self.returns, bench, rf=rf, periods_per_year=periods_per_year))
        n = len(self.equity)
        mean_nav = float(self.equity.mean()) if n else math.nan
        out.update(
            final_equity=float(self.equity.iloc[-1]) if n else math.nan,
            total_costs=self.total_costs,
            cost_drag=(self.total_costs / mean_nav * periods_per_year / n) if n and mean_nav > 0 else math.nan,
            turnover=self.turnover,
            fill_rate=self.fill_rate,
            n_trades=len(self.trades),
            dividends=float(self.dividends.sum()),
            taxes=float(self.taxes.sum()),
        )
        return out


# ---------------------------------------------------------------------------
# Préparation des données
# ---------------------------------------------------------------------------


def _as_wide(obj: Any, name: str) -> pd.DataFrame:
    """Contrôle et normalise un panel large (index de dates trié, sans doublon)."""
    if not isinstance(obj, pd.DataFrame):
        raise TypeError(f"le panel {name!r} doit être un DataFrame date × symbole")
    df = obj
    if not isinstance(df.index, pd.DatetimeIndex):
        try:
            parsed = _parse_date_index(df.index)
        except TypeError as exc:
            raise TypeError(f"le panel {name!r} : {exc}") from exc
        if parsed is None:
            raise TypeError(f"le panel {name!r} doit être indexé par des dates")
        df = df.set_axis(parsed, axis=0)
    if df.index.has_duplicates:
        df = df[~df.index.duplicated(keep="last")]
    if not df.index.is_monotonic_increasing:
        df = df.sort_index()
    if df.columns.has_duplicates:
        raise ValueError(f"le panel {name!r} a des symboles en double")
    return df


#: Panels larges lus par le moteur lui-même (normalisés par :func:`_as_wide`).
_ENGINE_PANELS = (
    "close",
    "volume",
    "value",
    "status",
    "prev_close",
    "ref_price",
    "change_pct",
    "dividend_net",
    "open",
    "adj_factor",
)


def _stable_order(values: pd.Index) -> np.ndarray:
    return np.argsort(np.asarray(values.asi8 if hasattr(values, "asi8") else values), kind="stable")


def _normalize_panel(obj: Any, name: str) -> Any:
    """Copie d'un panel pour le moteur et la vue, avec des dates exploitables.

    * panels du moteur (:data:`_ENGINE_PANELS`, ``DataFrame``) : :func:`_as_wide`
      (index converti en ``DatetimeIndex``, trié, doublons « dernier gagne ») ;
    * autre objet pandas indexé par des dates (y compris en chaînes) : index
      converti en ``DatetimeIndex`` et tri stable (doublons conservés : une
      table longue indexée par date en comporte légitimement) ;
    * ``MultiIndex`` à niveau ``date`` et table longue à colonne ``date`` :
      dates converties si besoin, tri stable par date (troncature par
      ``searchsorted``) ;
    * autre objet : inchangé (sa troncature est vérifiée à l'initialisation).
    """
    if not isinstance(obj, (pd.DataFrame, pd.Series)):
        return obj
    out = obj.copy()
    if name in _ENGINE_PANELS and isinstance(out, pd.DataFrame):
        return _as_wide(out, name)
    idx = out.index
    if isinstance(idx, pd.MultiIndex):
        lev = _date_level(idx)
        if lev is not None and not isinstance(idx.levels[lev], pd.PeriodIndex):
            values = idx.get_level_values(lev)
            parsed = _parse_date_index(values)
            if parsed is None:
                raise TypeError(f"panel {name!r} : niveau {idx.names[lev]!r} non convertible en dates")
            if not isinstance(values, pd.DatetimeIndex):
                arrays = [parsed if i == lev else idx.get_level_values(i) for i in range(idx.nlevels)]
                out.index = pd.MultiIndex.from_arrays(arrays, names=idx.names)
            if not parsed.is_monotonic_increasing:
                out = out.iloc[_stable_order(parsed)]
        return out
    if isinstance(idx, pd.PeriodIndex):
        return out if idx.is_monotonic_increasing else out.iloc[_stable_order(idx)]
    parsed = _parse_date_index(idx)
    if parsed is not None:
        out = out.set_axis(parsed, axis=0)
        return out if parsed.is_monotonic_increasing else out.iloc[_stable_order(parsed)]
    if isinstance(out, pd.DataFrame):
        date_cols = [c for c in out.columns if _is_date_label(c)]
        if date_cols:
            col = out.loc[:, date_cols[0]]
            if isinstance(col, pd.DataFrame):
                raise TypeError(f"panel {name!r} : colonne de dates en double")
            d = _as_date_column(col, date_cols[0])
            if not (pd.api.types.is_datetime64_any_dtype(col.dtype) or isinstance(col.dtype, pd.PeriodDtype)):
                out[date_cols[0]] = d.to_numpy()
            if not d.is_monotonic_increasing:
                out = out.iloc[_stable_order(d)]
    return out


def _with_key(key: str, exc: Exception) -> str:
    """Message d'erreur préfixé du nom du panel (s'il n'y figure pas déjà)."""
    msg = str(exc)
    return msg if repr(key) in msg else f"panel {key!r} : {msg}"


def _snap_to_calendar(df: pd.DataFrame, dates: pd.DatetimeIndex) -> pd.DataFrame:
    """Ramène des montants datés hors calendrier sur la séance suivante (somme).

    Un détachement daté d'une séance absente du panel (BOC manquant, jour non
    ouvré) est crédité à la première séance ``≥ date`` : aucune transaction
    n'ayant lieu entre les deux, les positions d'ouverture de cette séance
    sont celles qui avaient droit au dividende (``searchsorted(date, "left")``).
    Les dates antérieures à la première séance ou postérieures à la dernière
    sont ignorées (aucune position n'est concernée).
    """
    if len(dates) == 0 or len(df) == 0:
        return df.reindex(dates)
    idx = pd.DatetimeIndex(df.index)
    if idx.isin(dates).all():
        return df.reindex(dates)
    keep = (idx >= dates[0]) & (idx <= dates[-1])
    sub = df.loc[keep]
    pos = dates.searchsorted(pd.DatetimeIndex(sub.index), side="left")
    snapped = sub.set_axis(dates[pos], axis=0)
    num = snapped.apply(pd.to_numeric, errors="coerce")
    return num.groupby(level=0, sort=True).sum(min_count=1).reindex(dates)


def _dispatch_models(*slots: Any) -> dict[str, Any]:
    """Reconnaît par leur type les modèles passés en position (ordre libre)."""
    kinds: dict[str, Any] = {}
    names = {
        CostModel: "costs",
        Constraints: "constraints",
        ExecutionModel: "execution",
        TaxModel: "taxes",
    }
    for value in slots:
        if value is None:
            continue
        key = None
        for cls, nm in names.items():
            if isinstance(value, cls):
                key = nm
                break
        if key is None and isinstance(value, (int, float, np.integer, np.floating)) and not isinstance(value, bool):
            key = "capital"
        if key is None:
            raise TypeError(f"argument non reconnu pour Backtester : {type(value).__name__}")
        if key in kinds:
            raise TypeError(f"argument {key!r} fourni deux fois")
        kinds[key] = value
    return kinds


# ---------------------------------------------------------------------------
# Moteur
# ---------------------------------------------------------------------------


@dataclass
class _Order:
    """Ordre en attente (quantité signée restante)."""

    oid: int
    j: int
    decision_pos: int
    qty: int  # quantité initiale signée
    remaining: int  # reliquat signé
    ref_price: float
    status: str = "pending"
    first_fill: pd.Timestamp | None = None
    last_fill: pd.Timestamp | None = None


class Backtester:
    """Backtest quotidien réaliste d'une stratégie long-only sur la BRVM.

    Parameters
    ----------
    panels
        Dictionnaire de panels larges (date × symbole) :

        * ``close`` (obligatoire) : cours de clôture **ajusté des divisions
          de nominal** (renseigné même sans échange ; NaN avant cotation) ;
        * ``volume`` (obligatoire) : titres échangés (0 ou NaN sans échange) ;
        * ``value`` : capitaux échangés (FCFA) pour le VWAP ;
        * ``status`` : ``traded`` / ``not_traded`` / ``suspended`` ;
        * ``change_pct`` (variation publiée, en %), ``prev_close`` ou
          ``ref_price`` : référence des limites de variation (par ordre de
          préférence : ``change_pct`` publié, calculé par la BRVM sur la
          référence ajustée ; ``prev_close − dividende`` ; ``ref_price`` de la
          séance précédente, qui s'applique à la séance suivante ; à défaut
          la clôture précédente) ;
        * ``dividend_net`` : dividende net par action crédité à la date de
          détachement (0 sinon) ; une date absente du calendrier (BOC
          manquant) est reportée à la séance suivante (:func:`_snap_to_calendar`) ;
        * ``open`` : pour ``ExecutionModel.price == "open"`` ;
        * ``adj_factor`` : facteur ``f = cours ajusté / cours brut``,
          **indispensable** si ``close`` est ajusté mais ``volume``,
          ``value``, ``prev_close`` et ``dividend_net`` sont bruts (sortie de
          :func:`panels_from_equities`) : volume ``V / f``, VWAP
          ``(valeur / V) · f``, dividende ``D · f`` en unités ajustées. Sans
          lui (``f = 1``), avant une division 1:k le dividende crédité serait
          k fois trop élevé et le plafond de participation faux d'un facteur
          k. Reporté vers l'avant uniquement, 1 avant la première valeur ;
        * ``country`` (optionnel) : ``Series`` symbole → pays (retenue à la
          source si les dividendes fournis sont bruts) ;
        * toute autre entrée est transmise **tronquée** à la stratégie
          (:func:`truncate_asof` : panel large, table longue à colonne
          ``date``, ``MultiIndex`` (date, symbol), ``PeriodIndex``, index de
          dates en chaînes, objets statiques) ; un objet daté non tronquable
          (tableau ``numpy``, objet indexé par symbole contenant des dates…)
          lève ``TypeError`` dès la construction.
    costs, constraints, capital, execution, taxes
        Modèles de ``brvm_alpha.config``. Ils peuvent être passés en position
        dans n'importe quel ordre — contrat ``(panels, costs, constraints,
        capital)`` d'``ARCHITECTURE.md`` comme ``(panels, costs, execution,
        taxes, capital)`` — ils sont reconnus par leur type.
        ``constraints`` (facultatif) active : poids négatifs mis à 0
        (toujours appliqué : pas de vente à découvert), exposition brute
        plafonnée à ``1 − cash_buffer`` et bande de non-transaction
        ``no_trade_band`` (|Δw| < bande ⇒ pas d'ordre, sauf sortie totale).
    lot_size
        Quotité de négociation (1 à la BRVM).
    max_order_age
        Nombre maximal de séances de vie d'un ordre reporté (``None`` :
        jusqu'au rebalancement suivant).
    vwap_tolerance
        Si ``|VWAP / clôture − 1|`` dépasse ce seuil (incohérence
        d'ajustement), le prix d'exécution retenu est la clôture du jour.
    max_plausible_move
        Seuil d'invraisemblance des variations pour les limites
        (:func:`limit_flags`).
    periods_per_year
        Séances par an (annualisation du cash, des droits de garde et de la
        rotation).
    jump_warning
        Contrôle des cours non ajustés : une variation de clôture d'une
        séance à l'autre hors de ``[1 − s, 1 / (1 − s)]`` (``s = 0,40`` :
        −40 % / +67 %), avec comme sans réintégration du dividende du jour
        (``(P_t + D_t) / P_{t-1}`` et ``P_t / P_{t-1}``), impossible sous la
        bande de ±7,5 %, signale le plus souvent une division non ajustée ;
        elle est listée dans ``price_jumps`` et un avertissement est émis.
        ``None`` désactive le contrôle.

    Attributes
    ----------
    dates, symbols
        Calendrier des séances et univers (colonnes de ``close``).
    price_jumps
        ``DataFrame`` (``date, symbol, ratio``) des variations invraisemblables.
    n_vwap_fallback
        Nombre de (séance, titre) où le VWAP incohérent a été remplacé par la
        clôture (un nombre élevé signale des unités mal ajustées).
    n_dividend_dates_off_calendar
        Lignes de ``dividend_net`` datées hors calendrier (reportées à la
        séance suivante, ou ignorées hors de la période).
    """

    def __init__(
        self,
        panels: Mapping[str, Any],
        costs: Any = None,
        constraints: Any = None,
        capital: Any = None,
        execution: Any = None,
        taxes: Any = None,
        *,
        lot_size: int = 1,
        max_order_age: int | None = None,
        vwap_tolerance: float = 0.20,
        max_plausible_move: float = 0.20,
        periods_per_year: int = TRADING_DAYS,
        jump_warning: float | None = 0.40,
    ) -> None:
        models = _dispatch_models(costs, constraints, capital, execution, taxes)
        self.costs: CostModel = models.get("costs", CostModel())
        self.constraints: Constraints | None = models.get("constraints")
        self.execution: ExecutionModel = models.get("execution", ExecutionModel())
        self.taxes: TaxModel = models.get("taxes", TaxModel())
        self.capital = float(models.get("capital", PlatformConfig().capital_fcfa))
        if not (math.isfinite(self.capital) and self.capital > 0):
            raise ValueError("capital doit être > 0")
        if int(lot_size) < 1:
            raise ValueError("lot_size doit être >= 1")
        if max_order_age is not None and int(max_order_age) < 1:
            raise ValueError("max_order_age doit être >= 1")
        if not 0.0 < self.execution.max_volume_participation <= 1.0:
            raise ValueError("max_volume_participation doit être dans ]0, 1]")
        if self.execution.price not in ("vwap", "close", "open"):
            raise ValueError("ExecutionModel.price doit valoir 'vwap', 'close' ou 'open'")
        self.lot_size = int(lot_size)
        self.max_order_age = None if max_order_age is None else int(max_order_age)
        self.vwap_tolerance = float(vwap_tolerance)
        self.max_plausible_move = float(max_plausible_move)
        self.periods_per_year = int(periods_per_year)
        if jump_warning is not None and not 0.0 < float(jump_warning) < 1.0:
            raise ValueError("jump_warning doit être dans ]0, 1[ ou None")
        self.jump_warning = None if jump_warning is None else float(jump_warning)

        if "close" not in panels or "volume" not in panels:
            raise KeyError("les panels 'close' et 'volume' sont obligatoires")
        # Copie normalisée (dates converties et triées), indépendante des
        # modifications ultérieures des objets de l'appelant.
        self._panels: dict[str, Any] = {}
        for key, obj in panels.items():
            try:
                self._panels[key] = _normalize_panel(obj, key)
            except TypeError as exc:
                raise TypeError(_with_key(key, exc)) from exc
        close = _as_wide(self._panels["close"], "close").astype(float)
        self._panels["close"] = close
        self.dates = pd.DatetimeIndex(close.index)
        self.symbols = pd.Index(close.columns)
        if len(self.dates):
            # Échec immédiat (plutôt qu'au premier rebalancement) si un objet
            # daté ne peut pas être tronqué sans anticipation.
            for key, obj in self._panels.items():
                try:
                    truncate_asof(obj, self.dates[0])
                except TypeError as exc:
                    raise TypeError(_with_key(key, exc)) from exc
        self._prepare_arrays()

    @classmethod
    def from_config(cls, panels: Mapping[str, Any], config: PlatformConfig, **kwargs: Any) -> Backtester:
        """Construit un moteur à partir d'une :class:`PlatformConfig`."""
        return cls(
            panels,
            costs=config.costs,
            constraints=config.constraints,
            capital=config.capital_fcfa,
            execution=config.execution,
            taxes=config.taxes,
            periods_per_year=config.trading_days,
            **kwargs,
        )

    # -- préparation ----------------------------------------------------------

    def _wide(self, name: str, fill: float | None = None) -> np.ndarray | None:
        """Panel ``name`` aligné sur (séances, symboles) en ``float`` ou ``None``."""
        if name not in self._panels or self._panels[name] is None:
            return None
        df = _as_wide(self._panels[name], name).reindex(index=self.dates, columns=self.symbols)
        arr = df.apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
        if fill is not None:
            arr = np.where(np.isfinite(arr), arr, fill)
        return arr

    def _prepare_arrays(self) -> None:
        """Pré-calcule prix d'exécution, exécutabilité, limites et dividendes."""
        ex = self.execution
        close = self._panels["close"]
        c = close.to_numpy(dtype=float)
        c = np.where(c > 0, c, np.nan)
        self._close = c

        af = self._wide("adj_factor")
        self._has_adj_factor = af is not None
        if af is None:
            af = np.ones_like(c)
        else:
            # report du dernier facteur connu ; jamais de remplissage arrière
            # (il utiliserait une information future), 1 avant le premier.
            af = pd.DataFrame(np.where(af > 0, af, np.nan)).ffill().to_numpy(dtype=float)
            af = np.where(np.isfinite(af), af, 1.0)
        self._af = af
        # La vue n'est remise à l'échelle que si un facteur diffère de 1.
        self._rescale_view = bool(np.any(np.abs(af - 1.0) > 1e-12))

        vol_in = self._wide("volume", fill=0.0)
        assert vol_in is not None  # panel obligatoire (contrôlé à l'initialisation)
        vol_raw = np.clip(vol_in, 0.0, None)
        self._volume = vol_raw / af  # volume en titres « ajustés »
        value = self._wide("value")

        self.n_vwap_fallback = 0
        with np.errstate(divide="ignore", invalid="ignore"):
            if ex.price == "vwap" and value is not None:
                px = np.where(vol_raw > 0, value / vol_raw, np.nan) * af
                bad = ~np.isfinite(px) | (px <= 0)
                incoherent = np.isfinite(c) & ~bad & (np.abs(px / c - 1.0) > self.vwap_tolerance)
                self.n_vwap_fallback = int(incoherent.sum())
                px = np.where(bad | incoherent, c, px)
            elif ex.price == "open" and (o := self._wide("open")) is not None:
                o = o * af
                px = np.where(np.isfinite(o) & (o > 0), o, c)
            else:
                px = c.copy()
        self._px_exec = px

        tradeable = (self._volume > 0) & np.isfinite(px) & (px > 0)
        if "status" in self._panels and self._panels["status"] is not None:
            st = _as_wide(self._panels["status"], "status").reindex(index=self.dates, columns=self.symbols)
            st_low = st.astype(object).where(st.notna(), "").astype(str)
            st_low = st_low.apply(lambda col: col.str.strip().str.lower())
            tradeable &= ~st_low.isin(_BLOCKING_STATUS).to_numpy(dtype=bool)
        self._tradeable = tradeable

        # Valorisation : dernier cours de clôture connu (à défaut, dernier prix
        # d'exécution observé si la clôture manque un jour d'échange).
        val_src = np.where(np.isfinite(c), c, np.where(tradeable, px, np.nan))
        self._px_val = pd.DataFrame(val_src).ffill().to_numpy(dtype=float)

        # Dividendes (montant par titre ajusté) et retenue éventuelle ; une date
        # de détachement hors calendrier est reportée à la séance suivante.
        div = self._dividend_array()
        div = np.zeros_like(c) if div is None else np.clip(div, 0.0, None)
        div_adj = div * af
        if not self.taxes.dividends_reported_net:
            rates = self._withholding_rates()
            self._div = div_adj * (1.0 - rates)[None, :]
            self._div_tax = div_adj * rates[None, :]
        else:
            self._div = div_adj
            self._div_tax = np.zeros_like(div_adj)

        # Variation de la séance pour les limites de prix.
        move = np.full_like(c, np.nan)
        chg = self._wide("change_pct")
        if chg is not None:
            move = chg / 100.0
        prev = self._wide("prev_close")
        with np.errstate(divide="ignore", invalid="ignore"):
            if prev is not None:
                ref = (prev - div) * af
                m = np.where(ref > 0, c / ref - 1.0, np.nan)
                move = np.where(np.isfinite(move), move, m)
            refp = self._wide("ref_price")
            if refp is not None:
                ref = np.vstack([np.full((1, c.shape[1]), np.nan), refp[:-1]]) * af
                m = np.where(ref > 0, c / ref - 1.0, np.nan)
                move = np.where(np.isfinite(move), move, m)
            prev_c = np.vstack([np.full((1, c.shape[1]), np.nan), self._px_val[:-1]]) - div_adj
            m = np.where(prev_c > 0, c / prev_c - 1.0, np.nan)
            move = np.where(np.isfinite(move), move, m)
        self._move = move
        self._lim_up, self._lim_down = limit_flags(move, ex.price_limit, ex.limit_tolerance, self.max_plausible_move)
        self._check_price_jumps(c, div_adj)

    def _dividend_array(self) -> np.ndarray | None:
        """``dividend_net`` aligné sur (séances, symboles), dates hors calendrier reportées."""
        self.n_dividend_dates_off_calendar = 0
        raw = self._panels.get("dividend_net")
        if raw is None:
            return None
        df = _as_wide(raw, "dividend_net")
        n_off = int((~pd.DatetimeIndex(df.index).isin(self.dates)).sum())
        df = _snap_to_calendar(df, self.dates).reindex(columns=self.symbols)
        self.n_dividend_dates_off_calendar = n_off
        arr = df.apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
        return np.where(np.isfinite(arr), arr, 0.0)

    def _check_price_jumps(self, c: np.ndarray, div_adj: np.ndarray) -> None:
        """Repère les variations de clôture invraisemblables (division non ajustée ?)."""
        self.price_jumps = pd.DataFrame(columns=["date", "symbol", "ratio"])
        if self.jump_warning is None or c.shape[0] < 2:
            return
        s = self.jump_warning
        lo, hi = 1.0 - s, 1.0 / (1.0 - s)
        prev = np.vstack([np.full((1, c.shape[1]), np.nan), self._px_val[:-1]])
        with np.errstate(divide="ignore", invalid="ignore"):
            ratio = (c + div_adj) / prev
            price_only = c / prev
            # invraisemblable avec ET sans réintégration du dividende du jour
            # (un dividende dont la baisse de cours n'apparaît pas n'est pas
            # une division)
            bad = (
                np.isfinite(ratio)
                & ((ratio < lo) | (ratio > hi))
                & ((price_only < lo) | (price_only > hi))
            )
        if not bad.any():
            return
        ti, ji = np.nonzero(bad)
        self.price_jumps = pd.DataFrame(
            {"date": self.dates[ti], "symbol": self.symbols[ji], "ratio": ratio[ti, ji]}
        )
        first = self.price_jumps.iloc[0]
        warnings.warn(
            f"{len(self.price_jumps)} variation(s) de clôture invraisemblable(s) d'une séance à l'autre "
            f"(p. ex. {first['symbol']} le {pd.Timestamp(first['date']).date()} : {first['ratio'] - 1.0:+.0%}) : "
            "cours non ajustés des divisions ? fournir un 'close' ajusté et 'adj_factor' "
            "(panels_from_equities) ; détail dans Backtester.price_jumps",
            stacklevel=4,
        )

    def _withholding_rates(self) -> np.ndarray:
        """Taux de retenue à la source par symbole (``TaxModel``, pays d'émission)."""
        country = self._panels.get("country")
        if isinstance(country, pd.Series):
            ctry = country.reindex(self.symbols)
        else:
            ctry = pd.Series(np.nan, index=self.symbols, dtype=object)
        missing = ctry.isna()
        if missing.any():
            from brvm_alpha.reference import country_of

            ctry = ctry.astype(object)
            ctry[missing] = [country_of(str(s)) for s in self.symbols[missing.to_numpy()]]
        table = self.taxes.dividend_withholding
        return np.array([float(table.get(str(x), 0.0)) for x in ctry], dtype=float)

    # -- exécution ------------------------------------------------------------

    def _round_lot(self, q: np.ndarray) -> np.ndarray:
        lot = self.lot_size
        return (np.floor(np.asarray(q, dtype=float) / lot + 1e-9) * lot).astype(np.int64)

    def _buy_totals(self, q: np.ndarray, px: np.ndarray, vol: np.ndarray) -> np.ndarray:
        amount = q * px
        part = np.where(vol > 0, q / np.where(vol > 0, vol, 1.0), 0.0)
        return amount + trade_cost(amount, part, self.costs)

    def _affordable(self, desired: np.ndarray, px: np.ndarray, vol: np.ndarray, cash: float) -> np.ndarray:
        """Réduction au prorata des achats pour respecter ``Σ coût total ≤ cash``.

        Cherche par dichotomie le plus grand ``f ∈ [0, 1]`` tel que
        ``Σ_i T_i(⌊f · q_i⌋) ≤ cash`` où ``T_i(q) = q P_i + coût_i(q)`` est
        croissante en ``q`` ; ``f = 0`` est toujours admissible (cash ≥ 0).
        """
        if desired.size == 0:
            return desired
        if self._buy_totals(desired, px, vol).sum() <= cash:
            return desired
        lo, hi = 0.0, 1.0
        for _ in range(64):
            mid = 0.5 * (lo + hi)
            if self._buy_totals(self._round_lot(desired * mid), px, vol).sum() <= cash:
                lo = mid
            else:
                hi = mid
        return self._round_lot(desired * lo)

    # -- boucle principale ----------------------------------------------------

    def run(
        self,
        strategy: Strategy | Any,
        rebalance: str | int | Sequence[Any] | pd.DatetimeIndex | None = "M",
        *,
        start: Any = None,
        end: Any = None,
        anchor: str = "last",
    ) -> BacktestResult:
        """Simule la stratégie de ``start`` à ``end`` (inclus).

        Parameters
        ----------
        strategy
            ``strategy(asof, view) -> poids`` (``Series`` ou dict symbole →
            poids en fraction de la NAV ; symboles absents = 0 ; ``None`` =
            pas de changement) ou objet exposant ``target_weights(asof,
            panels)`` (p. ex. ``BrvmAlpha``). ``view`` est une
            :class:`PanelView` tronquée à ``asof``.
        rebalance
            Calendrier des décisions (:func:`rebalance_dates`) : ``'W-FRI'``,
            ``'M'``, ``'Q'``, ``'D'``, entier, liste de dates ou ``None``.
            Aucune décision n'est prise à la dernière séance (pas de t+1).
        start, end
            Période simulée ; la vue contient tout l'historique antérieur à
            ``asof`` (y compris avant ``start``) pour les calculs de signaux.
        anchor
            ``"last"`` ou ``"first"`` séance de chaque période.

        Returns
        -------
        BacktestResult
        """
        fn = self._strategy_callable(strategy)
        ex = self.execution
        costs = self.costs
        dates = self.dates
        T, N = len(dates), len(self.symbols)
        i0 = 0 if start is None else int(dates.searchsorted(pd.Timestamp(start), side="left"))
        i1 = T - 1 if end is None else int(dates.searchsorted(pd.Timestamp(end), side="right")) - 1
        if T == 0 or i0 > i1 or i0 >= T:
            raise ValueError("période de backtest vide")
        sim_dates = dates[i0 : i1 + 1]
        reb = rebalance_dates(sim_dates, rebalance, anchor=anchor)
        reb_pos = {int(p) for p in dates.get_indexer(reb) if 0 <= p < i1}

        n_sim = i1 - i0 + 1
        equity = np.empty(n_sim)
        cash_hist = np.empty(n_sim)
        pos_hist = np.zeros((n_sim, N), dtype=np.int64)
        costs_daily = np.zeros(n_sim)
        div_daily = np.zeros(n_sim)
        tax_daily = np.zeros(n_sim)
        traded_value = np.zeros(n_sim)

        q = np.zeros(N, dtype=np.int64)
        avg_cost = np.zeros(N)
        cash = self.capital
        payable = 0.0  # droits de garde dus non encore payés
        orders: list[_Order] = []
        pending: dict[int, _Order] = {}
        trades: list[tuple[Any, ...]] = []
        blocked: list[tuple[Any, ...]] = []
        used_reb: list[pd.Timestamp] = []
        warned: set[str] = set()

        daily_cash_rate = (1.0 + ex.cash_rate_annual) ** (1.0 / self.periods_per_year) - 1.0
        custody_daily = float(costs.annual_custody) / self.periods_per_year
        cgt = float(self.taxes.capital_gains_tax)
        part_max = float(ex.max_volume_participation)
        prev_nav = self.capital

        for k, t in enumerate(range(i0, i1 + 1)):
            day = dates[t]
            cost_today = 0.0
            tax_today = 0.0
            value_today = 0.0
            # 1. rémunération du cash
            if k > 0 and daily_cash_rate != 0.0:
                cash *= 1.0 + daily_cash_rate
            # 2. dividendes (positions d'ouverture)
            if q.any():
                d = float(q @ self._div[t])
                if d > 0:
                    cash += d
                    div_daily[k] = d
                tax_today += float(q @ self._div_tax[t])
            # 3. droits de garde sur la valeur de la veille
            if custody_daily > 0 and k > 0 and q.any():
                fee = custody_daily * float(np.nansum(q * self._px_val[t - 1]))
                payable += fee
                cost_today += fee
            if payable > 0:
                paid = min(cash, payable)
                cash -= paid
                payable -= paid

            # 4. exécution des ordres en attente
            if pending:
                px = self._px_exec[t]
                vol = self._volume[t]
                trad = self._tradeable[t]
                cap = self._round_lot(np.floor(part_max * vol + 1e-9))
                # 4a. ventes
                for j, od in list(pending.items()):
                    if od.remaining >= 0:
                        continue
                    want = min(-od.remaining, int(q[j]))
                    if want <= 0:
                        od.remaining = 0
                        continue
                    if not trad[j]:
                        blocked.append((day, self.symbols[j], "sell", want, "not_traded"))
                        continue
                    if self._lim_down[t, j]:
                        blocked.append((day, self.symbols[j], "sell", want, "limit_down"))
                        continue
                    n = int(min(want, cap[j]))
                    if n < want:
                        blocked.append((day, self.symbols[j], "sell", want - n, "volume_cap"))
                    if n <= 0:
                        continue
                    amount = n * float(px[j])
                    part = n / float(vol[j])
                    c_tot = float(trade_cost(amount, part, costs))
                    impact = float(costs.impact_coef) * math.sqrt(part) * amount
                    proceeds = amount - c_tot
                    if cash + proceeds < 0.0:
                        # vente « de poussière » dont les frais minimaux excèdent
                        # le produit et que le cash ne peut couvrir : reportée
                        blocked.append((day, self.symbols[j], "sell", n, "cash"))
                        continue
                    gain = proceeds - avg_cost[j] * n
                    tax = cgt * max(gain, 0.0)
                    cash += proceeds - tax
                    tax_today += tax
                    cost_today += c_tot
                    value_today += amount
                    q[j] -= n
                    if q[j] == 0:
                        avg_cost[j] = 0.0
                    od.remaining += n
                    reason = "rebalance" if t == od.decision_pos + 1 else "carry"
                    trades.append(
                        (
                            day,
                            self.symbols[j],
                            -n,
                            float(px[j]),
                            amount,
                            c_tot,
                            reason,
                            dates[od.decision_pos],
                            part,
                            impact,
                        )
                    )
                    if od.first_fill is None:
                        od.first_fill = day
                    od.last_fill = day
                if payable > 0:
                    paid = min(cash, payable)
                    cash -= paid
                    payable -= paid
                # 4b. achats
                buy_js: list[int] = []
                desired: list[int] = []
                for j, od in pending.items():
                    if od.remaining <= 0:
                        continue
                    want = od.remaining
                    if not trad[j]:
                        blocked.append((day, self.symbols[j], "buy", want, "not_traded"))
                        continue
                    if self._lim_up[t, j]:
                        blocked.append((day, self.symbols[j], "buy", want, "limit_up"))
                        continue
                    n = int(min(want, cap[j]))
                    if n < want:
                        blocked.append((day, self.symbols[j], "buy", want - n, "volume_cap"))
                    if n > 0:
                        buy_js.append(j)
                        desired.append(n)
                if buy_js:
                    js = np.asarray(buy_js, dtype=np.int64)
                    want_q = np.asarray(desired, dtype=np.int64)
                    got = self._affordable(want_q, px[js], vol[js], max(cash, 0.0))
                    for j_raw, w_n, n_raw in zip(js, want_q, got, strict=True):
                        j = int(j_raw)
                        n = int(n_raw)
                        if n < w_n:
                            blocked.append((day, self.symbols[j], "buy", int(w_n - n), "cash"))
                        if n <= 0:
                            continue
                        amount = n * float(px[j])
                        part = n / float(vol[j])
                        c_tot = float(trade_cost(amount, part, costs))
                        impact = float(costs.impact_coef) * math.sqrt(part) * amount
                        cash -= amount + c_tot
                        cost_today += c_tot
                        value_today += amount
                        avg_cost[j] = (avg_cost[j] * q[j] + amount + c_tot) / (q[j] + n)
                        q[j] += n
                        od = pending[j]
                        od.remaining -= n
                        reason = "rebalance" if t == od.decision_pos + 1 else "carry"
                        trades.append(
                            (
                                day,
                                self.symbols[j],
                                n,
                                float(px[j]),
                                amount,
                                c_tot,
                                reason,
                                dates[od.decision_pos],
                                part,
                                impact,
                            )
                        )
                        if od.first_fill is None:
                            od.first_fill = day
                        od.last_fill = day
                    if cash < 0.0:
                        # garde-fou numérique : la dichotomie garantit Σ coûts ≤ cash
                        if cash < -1e-6 * max(1.0, self.capital):
                            raise AssertionError(f"cash négatif au {day.date()} : {cash}")
                        cash = 0.0
                # 4c. ordres terminés / expirés
                for j in list(pending):
                    od = pending[j]
                    if od.remaining == 0:
                        od.status = "filled"
                        del pending[j]
                    elif not ex.carry_unfilled or (
                        self.max_order_age is not None and t - od.decision_pos >= self.max_order_age
                    ):
                        od.status = "expired"
                        del pending[j]

            # 5. valorisation à la clôture
            px_val = self._px_val[t]
            held = q != 0
            stock_value = float(np.sum(q[held] * np.nan_to_num(px_val[held]))) if held.any() else 0.0
            nav = cash - payable + stock_value
            equity[k] = nav
            cash_hist[k] = cash
            pos_hist[k] = q
            costs_daily[k] = cost_today
            tax_daily[k] = tax_today
            traded_value[k] = value_today / (2.0 * prev_nav) if prev_nav > 0 else 0.0

            # 6. décision
            if t in reb_pos:
                used_reb.append(day)
                self._decide(fn, t, nav, cash, q, pending, orders, warned)
            prev_nav = nav

        for od in pending.values():
            od.status = "end_of_backtest"
        return self._build_result(
            sim_dates,
            equity,
            cash_hist,
            pos_hist,
            costs_daily,
            div_daily,
            tax_daily,
            traded_value,
            trades,
            blocked,
            orders,
            pd.DatetimeIndex(used_reb),
            i0,
        )

    @staticmethod
    def _strategy_callable(strategy: Any) -> Callable[[pd.Timestamp, Mapping[str, Any]], Any]:
        if hasattr(strategy, "target_weights") and callable(strategy.target_weights):
            return strategy.target_weights
        if callable(strategy):
            return strategy
        raise TypeError("strategy doit être appelable ou exposer target_weights(asof, panels)")

    def _parse_weights(self, raw: Any, warned: set[str]) -> np.ndarray | None:
        """Convertit la sortie de la stratégie en vecteur de poids aligné ≥ 0."""
        if raw is None:
            return None
        if isinstance(raw, pd.DataFrame):
            if raw.shape[1] != 1:
                raise TypeError("la stratégie doit renvoyer une Series de poids")
            raw = raw.iloc[:, 0]
        s = pd.Series(raw, dtype=float) if not isinstance(raw, pd.Series) else raw.astype(float)
        if s.index.has_duplicates:
            raise ValueError("poids : symboles en double")
        unknown = s.index.difference(self.symbols)
        has_unknown = len(unknown) > 0 and float(s.reindex(unknown).fillna(0.0).abs().sum()) > 0
        if has_unknown and "unknown" not in warned:
            warnings.warn(f"poids ignorés pour des symboles inconnus : {list(unknown)[:5]}", stacklevel=3)
            warned.add("unknown")
        w = s.reindex(self.symbols).to_numpy(dtype=float)
        if np.any(np.isinf(w)):
            raise ValueError("poids infinis renvoyés par la stratégie")
        w = np.nan_to_num(w, nan=0.0)
        if np.any(w < 0):
            if "short" not in warned:
                warnings.warn("poids négatifs mis à 0 (pas de vente à découvert à la BRVM)", stacklevel=3)
                warned.add("short")
            w = np.clip(w, 0.0, None)
        max_gross = 1.0 - (self.constraints.cash_buffer if self.constraints is not None else 0.0)
        gross = float(w.sum())
        if gross > max_gross + 1e-12:
            if gross > 1.0 + 1e-9 and "lever" not in warned:
                warnings.warn(
                    f"exposition brute {gross:.4f} > 1 ramenée à {max_gross:.4f} (pas de levier)", stacklevel=3
                )
                warned.add("lever")
            w = w * (max_gross / gross)
        return w

    def _decide(
        self,
        fn: Callable[[pd.Timestamp, Mapping[str, Any]], Any],
        t: int,
        nav: float,
        cash: float,
        q: np.ndarray,
        pending: dict[int, _Order],
        orders: list[_Order],
        warned: set[str],
    ) -> None:
        """Appelle la stratégie sur la vue tronquée et remplace les ordres."""
        asof = self.dates[t]
        px = self._px_val[t]
        val = np.where(np.isfinite(px), q * np.nan_to_num(px), 0.0)
        cur_w = val / nav if nav > 0 else np.zeros_like(val)
        pend = pd.Series({self.symbols[j]: od.remaining for j, od in pending.items()}, dtype="int64", name="pending")
        positions = pd.Series(q.copy(), index=self.symbols, name="positions")
        rescale = None
        if self._rescale_view:
            # Vue « point-in-time » : cours, facteurs et quantités exprimés en
            # unités du jour de décision (f_s / f_asof ne dépend que des
            # divisions intervenues dans ]s, asof]) ; sans cela, le cours
            # ajusté à rebours révélerait les divisions futures.
            f_now = pd.Series(self._af[t], index=self.symbols)
            rescale = {"close": 1.0 / f_now, "adj_factor": 1.0 / f_now}
            positions = (positions * f_now).rename("positions")
            pend = (pend.astype(float) * f_now.reindex(pend.index)).rename("pending")
        view = PanelView(
            self._panels,
            asof,
            nav=nav,
            cash=cash,
            positions=positions,
            weights=pd.Series(cur_w, index=self.symbols, name="weights"),
            pending=pend,
            rescale=rescale,
        )
        w = self._parse_weights(fn(asof, view), warned)
        if w is None:
            return
        ok = np.isfinite(px) & (px > 0)
        target = np.zeros(len(w), dtype=np.int64)
        if nav > 0:
            raw = np.where(ok, w * nav / np.where(ok, px, 1.0), 0.0)
            target = self._round_lot(raw)
        delta = target - q
        if self.constraints is not None and self.constraints.no_trade_band > 0:
            band = float(self.constraints.no_trade_band)
            small = (np.abs(w - cur_w) < band) & ~((w == 0) & (q > 0))
            delta = np.where(small, 0, delta)
        for od in pending.values():
            od.status = "replaced"
        pending.clear()
        for j in np.flatnonzero(delta):
            od = _Order(
                oid=len(orders),
                j=int(j),
                decision_pos=t,
                qty=int(delta[j]),
                remaining=int(delta[j]),
                ref_price=float(px[j]) if np.isfinite(px[j]) else math.nan,
            )
            orders.append(od)
            pending[int(j)] = od

    def _build_result(
        self,
        sim_dates: pd.DatetimeIndex,
        equity: np.ndarray,
        cash: np.ndarray,
        pos: np.ndarray,
        costs_daily: np.ndarray,
        div_daily: np.ndarray,
        tax_daily: np.ndarray,
        turnover_daily: np.ndarray,
        trades: list[tuple[Any, ...]],
        blocked: list[tuple[Any, ...]],
        orders: list[_Order],
        used_reb: pd.DatetimeIndex,
        i0: int,
    ) -> BacktestResult:
        idx = pd.DatetimeIndex(sim_dates, name="date")
        eq = pd.Series(equity, index=idx, name="equity")
        prev = np.concatenate([[self.capital], equity[:-1]])
        rets = pd.Series(
            np.where(prev > 0, equity / np.where(prev > 0, prev, 1.0) - 1.0, np.nan), index=idx, name="returns"
        )
        positions = pd.DataFrame(pos, index=idx, columns=self.symbols)
        px_val = np.nan_to_num(self._px_val[i0 : i0 + len(idx)])
        with np.errstate(divide="ignore", invalid="ignore"):
            w = np.where(equity[:, None] > 0, pos * px_val / equity[:, None], 0.0)
        weights = pd.DataFrame(w, index=idx, columns=self.symbols)
        trade_cols = [
            "date",
            "symbol",
            "qty",
            "price",
            "value",
            "cost",
            "reason",
            "decision_date",
            "participation",
            "impact",
        ]
        tr = pd.DataFrame(trades, columns=trade_cols)
        if len(tr):
            tr["qty"] = tr["qty"].astype(np.int64)
        bl = pd.DataFrame(blocked, columns=["date", "symbol", "side", "qty", "reason"])
        od = pd.DataFrame(
            [
                {
                    "decision_date": self.dates[o.decision_pos],
                    "symbol": self.symbols[o.j],
                    "qty": o.qty,
                    "filled": o.qty - o.remaining,
                    "ref_price": o.ref_price,
                    "status": o.status,
                    "first_fill": o.first_fill,
                    "last_fill": o.last_fill,
                }
                for o in orders
            ],
            columns=["decision_date", "symbol", "qty", "filled", "ref_price", "status", "first_fill", "last_fill"],
        )
        if len(od):
            ref = od["ref_price"].fillna(0.0)
            asked = float((od["qty"].abs() * ref).sum())
            done = float((od["filled"].abs() * ref).sum())
            fill_rate = done / asked if asked > 0 else math.nan
        else:
            fill_rate = math.nan
        to_daily = pd.Series(turnover_daily, index=idx, name="turnover")
        return BacktestResult(
            equity=eq,
            returns=rets,
            weights=weights,
            trades=tr,
            costs=pd.Series(np.cumsum(costs_daily), index=idx, name="costs"),
            turnover=float(to_daily.mean() * self.periods_per_year) if len(idx) else math.nan,
            fill_rate=fill_rate,
            cash=pd.Series(cash, index=idx, name="cash"),
            positions=positions,
            dividends=pd.Series(div_daily, index=idx, name="dividends"),
            taxes=pd.Series(tax_daily, index=idx, name="taxes"),
            costs_daily=pd.Series(costs_daily, index=idx, name="costs_daily"),
            turnover_daily=to_daily,
            orders=od,
            blocked=bl,
            rebalance_dates=used_reb,
            capital=self.capital,
            meta={
                "costs": self.costs,
                "execution": self.execution,
                "taxes": self.taxes,
                "constraints": self.constraints,
                "lot_size": self.lot_size,
                "n_vwap_fallback": self.n_vwap_fallback,
                "adj_factor": self._has_adj_factor,
                "n_dividend_dates_off_calendar": self.n_dividend_dates_off_calendar,
                "n_price_jumps": len(self.price_jumps),
            },
        )


# ---------------------------------------------------------------------------
# Conversion depuis le panel long (equities.parquet)
# ---------------------------------------------------------------------------


#: Fenêtre (jours) de fusion d'une correction de date à montant identique,
#: alignée sur ``store.detect_dividends``.
_DIV_CORRECTION_DAYS = 60

_DIVIDEND_METHODS = ("detect", "last_div")


def _dividends_from_last_div(
    last_net: pd.DataFrame, last_date: pd.DataFrame, *, merge_days: int = _DIV_CORRECTION_DAYS
) -> pd.DataFrame:
    """Repli **explicite** : dividendes à la date de mise à jour de la colonne BOC.

    Un nouveau dividende est détecté à la première séance où la date de
    paiement publiée (``last_div_date``) est strictement postérieure à toutes
    celles observées auparavant pour ce titre ; il est crédité **à cette
    séance d'observation**. La première observation de chaque titre (état
    initial de l'historique) n'est pas créditée. Une correction de date à
    montant identique moins de ``merge_days`` jours après un dividende
    détecté est le même dividende (fusion, comme ``store.detect_dividends``) :
    sans cette fusion il serait crédité deux fois.

    Biais connu (raison pour laquelle ce n'est pas le défaut) : la BRVM met
    parfois à jour cette colonne plusieurs semaines **après** le détachement.
    Une position achetée entre le détachement et la mise à jour, donc au cours
    déjà ex-dividende, recevrait un dividende auquel elle n'a pas droit, et
    une position vendue entre les deux le perdrait. Préférer
    ``store.detect_dividends`` (date de détachement estimée), chemin par
    défaut de :func:`panels_from_equities`.
    """
    net = last_net.apply(pd.to_numeric, errors="coerce")
    dt = last_date.apply(pd.to_datetime, errors="coerce").reindex(index=net.index, columns=net.columns)
    out = pd.DataFrame(0.0, index=net.index, columns=net.columns)
    for col in net.columns:
        a = net[col]
        b = dt[col]
        obs = a.notna() & b.notna()
        if not obs.any():
            continue
        a_o, b_o = a[obs], b[obs]
        # nouveau dividende : date de paiement strictement plus récente que
        # toutes celles déjà observées (robuste aux allers-retours de saisie)
        prev_max = b_o.cummax().shift(1)
        new = (b_o > prev_max).fillna(False) & (a_o > 0)
        last_amount: float | None = None
        last_seen: pd.Timestamp | None = None
        for day, amount in a_o[new].items():
            day = pd.Timestamp(day)
            amount = float(amount)
            if (
                last_amount is not None
                and last_seen is not None
                and abs(amount - last_amount) < 1e-6
                and (day - last_seen).days <= merge_days
            ):
                continue  # simple correction de la date de paiement
            out.loc[day, col] = amount
            last_amount, last_seen = amount, day
    return out


def _dividend_panel(table: pd.DataFrame | None, dates: pd.DatetimeIndex, symbols: pd.Index) -> pd.DataFrame:
    """Panel large ``D_{t,i}`` à partir d'une table d'événements (``symbol, ex_date, amount``).

    Chaque montant (dividende net par action, en unités **brutes** du jour de
    détachement, comme le publie le BOC) est placé à la séance de
    détachement, ramenée au calendrier par ``searchsorted(ex_date, "left")``
    (première séance ``≥ ex_date`` si la séance manque) ; montants d'un même
    jour additionnés ; événements hors de ``[dates[0], dates[-1]]`` ignorés.
    """
    out = pd.DataFrame(0.0, index=dates, columns=symbols)
    if table is None or not len(table) or not len(dates):
        return out
    need = {"symbol", "ex_date", "amount"}
    if not need.issubset(table.columns):
        raise KeyError(f"table de dividendes : colonnes manquantes {sorted(need - set(table.columns))}")
    ev = table.loc[:, ["symbol", "ex_date", "amount"]].copy()
    ev["ex_date"] = pd.to_datetime(ev["ex_date"], errors="coerce")
    ev["amount"] = pd.to_numeric(ev["amount"], errors="coerce")
    ok = ev["symbol"].isin(symbols) & ev["ex_date"].notna() & np.isfinite(ev["amount"]) & (ev["amount"] > 0)
    ev = ev[ok & (ev["ex_date"] >= dates[0]) & (ev["ex_date"] <= dates[-1])]
    if not len(ev):
        return out
    rows = dates.searchsorted(pd.DatetimeIndex(ev["ex_date"]), side="left")
    cols = symbols.get_indexer(ev["symbol"])
    arr = out.to_numpy(dtype=float, copy=True)
    np.add.at(arr, (rows, cols), ev["amount"].to_numpy(dtype=float))
    return pd.DataFrame(arr, index=dates, columns=symbols)


def _complete_dividend_table(table: pd.DataFrame) -> pd.DataFrame:
    """Table d'événements au format de ``store.detect_dividends`` (``first_seen`` = ``ex_date`` si absent)."""
    need = {"symbol", "ex_date", "amount"}
    if not need.issubset(table.columns):
        raise KeyError(f"table de dividendes : colonnes manquantes {sorted(need - set(table.columns))}")
    out = table.copy()
    out["ex_date"] = pd.to_datetime(out["ex_date"], errors="coerce")
    if "first_seen" not in out.columns:
        out["first_seen"] = out["ex_date"]
    else:
        out["first_seen"] = pd.to_datetime(out["first_seen"], errors="coerce").fillna(out["ex_date"])
    return out


def _store_ready(df: pd.DataFrame) -> pd.DataFrame:
    """Complète les colonnes facultatives attendues par ``brvm_alpha.data.store``.

    ``ex_div`` (marqueur ``(d)``) faux, ``flags`` vide, ``prev_close`` /
    ``ref_price`` / ``last_div_net`` NaN et ``last_div_date`` NaT si absents :
    la détection se replie alors sur les indices restants.
    """
    out = df.copy()
    for col in ("prev_close", "ref_price", "last_div_net"):
        if col not in out.columns:
            out[col] = np.nan
    out["last_div_date"] = (
        pd.to_datetime(out["last_div_date"], errors="coerce") if "last_div_date" in out.columns else pd.NaT
    )
    if "ex_div" in out.columns:
        out["ex_div"] = out["ex_div"].astype(object).where(out["ex_div"].notna(), False).astype(bool)
    else:
        out["ex_div"] = False
    out["flags"] = out["flags"].astype(object).where(out["flags"].notna(), "").astype(str) if "flags" in out else ""
    return out.sort_values(["date", "symbol"], kind="stable").reset_index(drop=True)


def _adjustment_factor(adjusted: pd.DataFrame, raw: pd.DataFrame) -> pd.DataFrame:
    """Facteur ``f_t = P̃_t / P_t`` (cours ajusté / cours brut), reporté vers l'avant.

    Avec ``adjusted_prices`` (convention de la colonne ``cfacpr`` de CRSP),
    ``P̃_t = P_t / Π_{s>t} k_s`` : ``f`` est constant par morceaux et vaut
    ``1 / Π`` des ratios des divisions postérieures à ``t``. Valeurs non
    finies ou ≤ 0 (titre non coté) : dernier facteur connu (jamais de
    remplissage arrière), 1 avant la première observation (convention du
    moteur). Écarts à 1 inférieurs à 1e-9 (arrondis) ramenés à 1.
    """
    raw = raw.reindex(index=adjusted.index, columns=adjusted.columns).astype(float)
    adj = adjusted.astype(float)
    with np.errstate(divide="ignore", invalid="ignore"):
        f = adj / raw
    f = f.where(np.isfinite(f) & (f > 0)).ffill()
    return f.mask((f - 1.0).abs() < 1e-9, 1.0)


def panels_from_equities(
    equities: pd.DataFrame,
    *,
    close: pd.DataFrame | None = None,
    dividend_net: pd.DataFrame | None = None,
    infer_dividends: bool = True,
    dividends: pd.DataFrame | None = None,
    corporate_actions: pd.DataFrame | None = None,
    adjust: bool = True,
    dividend_method: str = "detect",
) -> dict[str, Any]:
    """Construit les panels larges du moteur à partir de ``equities.parquet``.

    Unités. Le moteur raisonne en titres **ajustés des divisions** : le cours
    ``close`` est ajusté (``P̃ = P · f``) et ``adj_factor`` (``f = P̃ / P``)
    convertit les grandeurs brutes du BOC : volume ``V / f``, VWAP
    ``(valeur / V) · f``, dividende ``D · f``. Sans ce facteur, avant une
    division 1:k, un dividende brut serait crédité k fois sur des titres
    « ajustés » (biais optimiste énorme), le VWAP brut serait rejeté comme
    incohérent et le plafond de participation serait faux d'un facteur k.

    Dividendes. Par défaut (``dividend_method="detect"``), les montants
    proviennent de ``store.detect_dividends`` : un nouveau dividende apparaît
    quand la date du « dernier dividende payé » change, mais il est daté du
    **détachement** (marqueur ``(d)``, baisse de la référence d'environ le
    montant, à défaut estimation par la date de paiement), et une correction
    de date à montant identique (≤ 60 jours) est fusionnée. Le dividende
    revient aux titres détenus à l'ouverture de la séance de détachement,
    celle où le cours baisse d'environ le montant (Elton & Gruber, 1970) :
    c'est la date d'ayant droit, même si le BOC ne met à jour la colonne que
    plus tard. ``dividend_method="last_div"`` est un repli explicite
    (:func:`_dividends_from_last_div`, avec avertissement) qui crédite à la
    date de mise à jour de la colonne.

    Parameters
    ----------
    equities
        Table longue (schéma ``ARCHITECTURE.md`` : une ligne par (date,
        symbole)), ou indexée par ``(date, symbol)`` (``store.load_equities``).
    close
        Cours ajustés des divisions (``store.adjusted_prices``). ``adj_factor``
        en est déduit (``close / close brut``). Ne pas fournir de cours
        ajustés **des dividendes** (ils seraient comptés deux fois).
    dividend_net
        Dividendes nets par action (unités brutes) par date de détachement
        (panel large) ; prioritaire sur ``dividends``.
    infer_dividends
        Si ni ``dividend_net`` ni ``dividends`` n'est fourni : déduire les
        dividendes (``dividend_method``) ; ``False`` ⇒ aucun dividende.
    dividends
        Table d'événements (``dividends.parquet`` : ``symbol, ex_date,
        amount``) ; à défaut calculée par ``store.detect_dividends``.
    corporate_actions
        Opérations sur titres (``corporate_actions.parquet``) pour
        l'ajustement ; à défaut ``store.detect_corporate_actions``.
    adjust
        Si ``close`` n'est pas fourni : ``True`` (défaut) calcule les cours
        ajustés par ``store.adjusted_prices`` ; ``False`` garde les cours
        bruts **avec un avertissement** (une division 1:k y apparaît comme une
        chute de ``1 − 1/k``, p. ex. −83 % pour 1:6).
    dividend_method
        ``"detect"`` (défaut, date de détachement) ou ``"last_div"`` (repli).

    Returns
    -------
    dict
        ``close`` (ajusté), ``adj_factor`` (si ajusté), ``volume, value,
        status, prev_close, ref_price, change_pct, open, net_yield_pct, per,
        last_div_net, last_div_date`` (bruts, si présents), ``dividend_net``,
        ``country`` (``Series``) et ``sector`` (``Series``).

    References
    ----------
    * Elton, E. J. & Gruber, M. J. (1970). Marginal Stockholder Tax Rates and
      the Clientele Effect. *Review of Economics and Statistics*, 52(1), 68-74.
    * CRSP (2001). *CRSP Data Description Guide* (facteurs d'ajustement des
      cours ``cfacpr`` et des quantités ``cfacshr``).
    """
    if dividend_method not in _DIVIDEND_METHODS:
        raise ValueError(f"dividend_method doit valoir l'un de {_DIVIDEND_METHODS}")
    if "date" not in equities.columns or "symbol" not in equities.columns:
        names = [n for n in equities.index.names if n is not None]
        if {"date", "symbol"} & set(names):
            equities = equities.reset_index()
    need = {"date", "symbol", "close", "volume"}
    if not need.issubset(equities.columns):
        raise KeyError(f"colonnes manquantes : {sorted(need - set(equities.columns))}")
    df = equities.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.drop_duplicates(["date", "symbol"], keep="last")
    cols = [
        "close",
        "volume",
        "value",
        "status",
        "prev_close",
        "ref_price",
        "change_pct",
        "open",
        "net_yield_pct",
        "per",
        "last_div_net",
        "last_div_date",
    ]
    panels: dict[str, Any] = {}
    for c in cols:
        if c in df.columns:
            panels[c] = df.pivot(index="date", columns="symbol", values=c).sort_index()
    panels["volume"] = panels["volume"].astype(float).fillna(0.0)
    raw_close = panels["close"].astype(float)
    has_last_div = "last_div_net" in df.columns and "last_div_date" in df.columns

    use_detect = dividend_net is None and dividends is None and infer_dividends and dividend_method == "detect"
    need_store = use_detect or (close is None and adjust)
    ready = _store_ready(df) if need_store else None
    div_table = _complete_dividend_table(dividends) if dividends is not None else None
    if div_table is None and need_store and has_last_div:
        from brvm_alpha.data import store

        div_table = store.detect_dividends(ready)

    if close is None and adjust:
        from brvm_alpha.data import store

        ca = corporate_actions if corporate_actions is not None else store.detect_corporate_actions(ready, div_table)
        close = store.adjusted_prices(ready, ca, div_table)
    if close is not None:
        adj = _as_wide(close, "close").astype(float)
        panels["close"] = adj
        panels["adj_factor"] = _adjustment_factor(adj, raw_close)
    else:
        warnings.warn(
            "panels_from_equities(adjust=False) : cours BRUTS non ajustés des divisions ; une division 1:k "
            "apparaîtra comme une chute de 1 - 1/k du portefeuille (fournir close=store.adjusted_prices(...))",
            stacklevel=2,
        )

    dates = pd.DatetimeIndex(panels["close"].index)
    symbols = pd.Index(panels["close"].columns)
    if dividend_net is not None:
        panels["dividend_net"] = dividend_net.sort_index()
    elif div_table is not None and (dividends is not None or (infer_dividends and dividend_method == "detect")):
        panels["dividend_net"] = _dividend_panel(div_table, dates, symbols)
    elif infer_dividends and has_last_div and dividend_method == "last_div":
        warnings.warn(
            "dividend_method='last_div' : dividendes crédités à la date de mise à jour de la colonne "
            "« dernier dividende » du BOC, parfois plusieurs semaines après le détachement (droit mal attribué)",
            stacklevel=2,
        )
        last_net = panels["last_div_net"].reindex(index=dates, columns=symbols)
        last_date = panels["last_div_date"].reindex(index=dates, columns=symbols)
        panels["dividend_net"] = _dividends_from_last_div(last_net, last_date)
    else:
        panels["dividend_net"] = pd.DataFrame(0.0, index=dates, columns=symbols)
    from brvm_alpha.reference import countries

    panels["country"] = countries(list(symbols))
    if "sector" in df.columns:
        panels["sector"] = df.sort_values("date").groupby("symbol")["sector"].last().reindex(list(symbols))
    return panels
