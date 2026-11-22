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
* **bandes de prix exactes** (±7,5 % à la BRVM, Instruction I-A ; spéc.
  §7.1.3) : autour de la référence ajustée ``R`` (cours de référence publié
  la veille), ``basse = ceil(R·0,925 / pas)·pas`` et
  ``haute = max(floor(R·1,075 / pas)·pas ; R + pas)``, pas de cotation de
  1 FCFA sous 100 FCFA, 5 FCFA au-delà (:func:`price_band_limits`). Un titre
  qui clôture à la borne haute signale une file d'acheteurs non servie ⇒
  **pas d'achat** ; à la borne basse, file de vendeurs ⇒ **pas de vente**
  (Kim & Rhee, 1997). Par défaut (``band_rule="exact_or_tolerance"``), la
  clôture est « à la borne » si elle l'atteint exactement **ou** si
  ``|clôture/R − 1| ≥ 7,5 % − 0,2 %`` (tolérance de la spécification) ;
* **coûts par côté** (cf. :func:`trade_cost`, spéc. §7.2) : frais
  proportionnels ``CostModel.rate()`` (SGI × (1 + taxe), BRVM, DC/BR,
  AMF-UMOA), **demi-spread propre au titre** (½ spread médian de clôture sur
  120 séances quand les deux côtés du carnet sont présents, plancher
  ``pas / (2·cours)``, défaut ``CostModel.half_spread_default``, multiplié
  par ``CostModel.half_spread_mult`` ; :func:`quoted_half_spread`) et impact
  de marché ``κ·√π`` en racine carrée de la participation (Almgren, Thum,
  Hauptmann & Li, 2005 ; Tóth et al., 2011 ; Bouchaud, Bonart, Donier &
  Gould, 2018). Ce sont des **hypothèses** de coûts (plusieurs taux sont
  [NON VÉRIFIÉ] dans la spécification), pas des coûts observés ;
* **frais fixes** : droits de garde (``annual_custody`` sur l'encours) et
  **tenue de compte par ligne détenue** (``account_fee_per_line_fcfa`` par
  an), au prorata des séances écoulées ;
* **quantités entières** (quotité ``lot_size``, 1 par défaut), **cash non
  négatif** (pas d'effet de levier, pas de découvert ; les ventes passent
  avant les achats, qui sont réduits au prorata si nécessaire) ;
* **règlement-livraison** (spéc. §7.1.5) : J+3 pour une négociation
  antérieure au ``ExecutionModel.settlement_switch_date`` (04/12/2025), J+2
  ensuite ; le produit d'une vente ne finance un achat qu'**après**
  règlement (il reste une créance dans la NAV entre-temps). Les achats
  mobilisent le cash dès la négociation (provision exigée par la SGI) ;
* **report des ordres** (spéc. §7.1.1) : un ordre non servi en t+1 est
  reporté pendant au plus ``ExecutionModel.max_carry_sessions`` séances
  (t+2 … t+11 par défaut), puis annulé (réévaluation au rebalancement
  suivant) ;
* **jour ex et jour de division** (spéc. §7.1.4, §5.2.4) : la BRVM annule
  les ordres en attente ; le moteur annule les ordres résiduels saisis avant
  la séance et les **ressaisit le jour même** (journal ``orders`` et
  ``events``) ;
* **dividendes** nets reconnus à la date de détachement aux titres détenus à
  l'ouverture de cette séance (créance dans la NAV), **crédités en cash à la
  date de paiement** (``dividend_payment_date`` si connue, sinon date ex +
  2 séances) et laissés en cash jusqu'au rebalancement suivant ; montants
  convertis en unités ajustées par ``adj_factor`` (``D · f``) ; retenue à
  la source par pays si les montants fournis sont bruts (``TaxModel``).
  Depuis le panel long, la date de détachement vient de
  ``store.detect_dividends`` (:func:`panels_from_equities`). **Montant crédité
  (additif v1.1, D6)** : le montant **corrigé** (meilleure estimation du
  versement réel, ``dividend_net``) ; le montant de la ligne « (d) » du BOC
  (``dividend_net_boc``, celui que voient les signaux) sert à publier l'écart
  total (``BacktestResult.dividends_boc``, ``dividend_events``,
  ``meta["dividend_gap_vs_boc"]``) ;
* **suspension** : position bloquée (aucun ordre exécuté) ; sa valeur est
  suivie à part (``suspended_value``) pour une décote de risque de 10 % ;
* **choc pays sévère** (option ``country_shocks``, spéc. §4.3 et §7.1.8) :
  la première séance qui suit l'annonce est supposée au plancher, sans
  vendeur servi (hypothèse de stress, pas une observation).

Déroulé d'une séance ``t`` (dans cet ordre)
-------------------------------------------
1. rémunération du cash : ``cash ← cash · (1 + r_a)^(n_t/252)`` (``n_t`` =
   séances écoulées depuis la ligne précédente, BOC manquants compris) ;
2. règlements : produits de ventes arrivés à échéance et dividendes dont la
   date de paiement est atteinte versés en cash ;
3. dividendes : créance ``Σ_i q_i(t⁻) · D_i(t)`` (``q(t⁻)`` = positions
   d'ouverture, donc un achat du jour de détachement n'y a pas droit) ;
4. frais fixes : ``garde_t = g_a·n_t / 252 · Σ_i q_i P_i(t-1)`` et
   ``tenue_t = F·n_t / 252 · #{i : q_i > 0}`` (à payer) ;
5. jour ex / jour de division : annulation et ressaisie des ordres en
   attente concernés ;
6. exécution des ordres en attente : **ventes d'abord**, puis achats limités
   par le cash **réglé** disponible ;
7. valorisation à la clôture :
   ``NAV_t = cash_t − dû_t + créances_t + Σ_i q_i(t) · P̃_i(t)`` où ``P̃``
   est le dernier cours de clôture connu ;
8. si ``t`` est une date de rebalancement : appel de la stratégie sur la vue
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
* ``trades`` (``date, symbol, qty, price, value, cost, reason`` ; détail
  ``commission, half_spread, spread_cost, impact``) ;
* ``costs`` cumulés (FCFA) et ``cost_breakdown`` quotidien (commission,
  demi-spread, impact, garde, tenue de compte), ``turnover`` annualisé
  (aller simple) ``TO = 252 · moyenne_t[ Σ_i |V_{i,t}| / (2 · NAV_{t-1}) ]`` ;
* ``fill_rate`` = part (en valeur au cours de décision) des ordres exécutés ;
* ``cash`` réglé, ``receivables`` (ventes non réglées, dividendes à
  recevoir), ``payables`` (frais dus), ``dividends`` (reconnus au jour ex)
  et ``dividends_paid`` (versés), ``dividends_boc`` (les mêmes dividendes
  valorisés au montant de la ligne « (d) », D6) et ``dividend_events`` (un
  détachement par ligne : crédité, ligne (d), écart), ``orders`` / ``events``
  (annulations et ressaisies), ``suspended_value``.

Toutes ces grandeurs sont des **simulations** sous hypothèses (coûts,
exécution au VWAP, file d'attente aux bornes) : elles ne garantissent aucun
résultat réel.

Limites connues (choix de prudence documentés)
----------------------------------------------
* Les ordres du moteur sont « au mieux » (exécutés au VWAP) : la ressaisie
  du jour ex ne change donc ni leur prix ni leur quantité (en titres
  ajustés) ; elle est journalisée pour la traçabilité.
* Le carnet d'ordres n'est pas observé en séance : la file d'attente à la
  limite est approchée par le cours de clôture (à la borne ⇒ non servi).
* Le VWAP se situe déjà à l'intérieur de la fourchette : y ajouter le
  demi-spread est prudent (coût probablement surestimé), conforme à la
  spécification §7.2.
* Les dates de fin de période (``'M'``, ``'Q'``, ``'W-FRI'``) supposent le
  calendrier des séances connu à l'avance (jours fériés publiés), hypothèse
  standard ; ``anchor="first"`` l'évite.
* Les quantités sont arrondies en titres **réels du jour d'exécution**
  (``q_brut = ⌊w · NAV / (P̃ / f_t) / lot⌋ · lot``, puis ``q_ajusté = q_brut / f_t``) :
  la granularité ne dépend d'aucune division future. Une attribution non entière
  (3:2 sur un nombre impair de titres) laisse un « rompu », crédité en cash au
  dernier cours le jour de l'attribution (hypothèse simple).
* ``close``, ``adj_factor``, ``close_adj`` et ``split_factor`` sont remis aux unités du
  jour de décision dans la vue ; un autre panel fourni en unités ajustées à rebours
  resterait dépendant des divisions futures.
* Choc pays sévère de plusieurs séances : planchers cumulés séance après séance ;
  après le choc, le niveau choqué persiste (option ``country_shock_recovery``).
* Titre radié (plus aucune ligne au BOC) : position bloquée (motif ``delisted``),
  suivie dans ``suspended_value`` ; valorisation au dernier cours sauf
  ``delisted_writedown`` (hypothèse, scénario ST8).
* Valeur liquidative ≤ 0 : avertissement, rendements arrêtés (``meta``).

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
    "BAND_RULES",
    "ENGINE_DEFAULTS",
    "BacktestResult",
    "Backtester",
    "PanelView",
    "Strategy",
    "band_flags",
    "limit_flags",
    "panels_from_equities",
    "price_band_limits",
    "quoted_half_spread",
    "rebalance_dates",
    "settlement_lag_sessions",
    "tick_size",
    "trade_cost",
    "truncate_asof",
]

TRADING_DAYS = 252

#: Règles de détection de la clôture « à la borne » (spéc. §7.1.3) :
#: ``"exact"`` (clôture égale à la borne calculée au pas), ``"tolerance"``
#: (``|clôture/réf − 1| ≥ limite − tolérance``, comportement historique du
#: moteur) ou l'union des deux (défaut, prudent dans les deux sens).
BAND_RULES = ("exact_or_tolerance", "exact", "tolerance")

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

    Attributs : ``asof``, ``nav``, ``cash`` (cash **réglé** disponible),
    ``receivables`` (ventes non réglées et dividendes à recevoir, FCFA),
    ``positions`` (titres détenus), ``weights`` (poids courants), ``pending``
    (ordres en attente, en titres).
    ``positions`` est exprimé en titres **réels** du jour ``asof`` (``q · f_asof``,
    entiers) ; ``pending`` aussi (entiers, ou ``float`` si une attribution non
    entière laisse une fraction).
    """

    __slots__ = (
        "__fetch",
        "__keys",
        "_asof",
        "_cache",
        "cash",
        "nav",
        "pending",
        "positions",
        "receivables",
        "weights",
    )

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
        receivables: float | None = None,
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
        self.receivables = receivables

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
    half_spread: np.ndarray | float | None = None,
) -> np.ndarray:
    """Coût total (FCFA) d'une exécution de montant ``A`` à la participation ``π``.

    ``coût = max(τ · A, m) + s · A + κ · sqrt(π) · A`` pour ``A > 0`` (0
    sinon), avec ``τ = CostModel.rate()`` (frais proportionnels d'un aller
    simple, taxe sur la commission SGI incluse), ``m = min_ticket_fcfa``
    (minimum de frais par ordre), ``s`` le **demi-spread** de la ligne
    (fraction, déjà multiplié par ``half_spread_mult`` et plancher compris ;
    ``None`` ⇒ 0, comportement historique) et ``κ = impact_coef``.
    ``π = q / volume_jour`` ∈ [0, 1]. Formule par côté de la spécification
    §7.2 : ``courtage × (1 + taxe) + 0,0020 + 0,0010 + demi_spread_i + κ·√π``.

    Le terme ``κ sqrt(π)`` est la « loi en racine carrée » de l'impact de
    marché (Almgren et al., 2005 ; Tóth et al., 2011), exprimée ici en
    fraction du montant et calibrée par ``impact_coef`` ; elle est comptée
    comme un coût (équivalent d'un prix d'exécution dégradé). Le κ central
    (0,016) est une **hypothèse** : aucune étude d'impact publiée sur la BRVM.
    """
    prop, spread, impact = _cost_parts(amount, participation, costs, half_spread)
    return prop + spread + impact


def _cost_parts(
    amount: np.ndarray | float,
    participation: np.ndarray | float,
    costs: CostModel,
    half_spread: np.ndarray | float | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Décomposition ``(frais proportionnels, demi-spread, impact)`` de :func:`trade_cost`."""
    a = np.asarray(amount, dtype=float)
    p = np.clip(np.asarray(participation, dtype=float), 0.0, None)
    positive = a > 0
    prop = np.where(positive, np.maximum(costs.rate() * a, float(costs.min_ticket_fcfa)), 0.0)
    hs = 0.0 if half_spread is None else np.clip(np.nan_to_num(np.asarray(half_spread, dtype=float)), 0.0, None)
    spread = np.where(positive, hs * a, 0.0)
    impact = np.where(positive, float(costs.impact_coef) * np.sqrt(p) * a, 0.0)
    return prop, spread, impact


def tick_size(price: Any) -> Any:
    """Pas de cotation (FCFA) : 1 sous 100 FCFA, 5 au-delà (BOC 2017-2026, spéc. §6 et §11).

    Scalaire ⇒ ``float`` ; tableau ⇒ ``np.ndarray`` (NaN conservés).
    """
    if np.ndim(price) == 0:
        p = float(price)
        return math.nan if not math.isfinite(p) else (1.0 if p < 100.0 else 5.0)
    arr = np.asarray(price, dtype=float)
    return np.where(np.isfinite(arr), np.where(arr < 100.0, 1.0, 5.0), np.nan)


#: Marge numérique des arrondis au pas (évite ``ceil(812.0000000001)``).
_BAND_EPS = 1e-9


def price_band_limits(ref: Any, pct: float = 0.075, tick: Any = None) -> tuple[Any, Any]:
    """Bornes de cotation autour de la référence **ajustée** ``R`` (spéc. §7.1.3, §11).

    ``basse = ceil(R·(1 − pct) / pas)·pas`` et
    ``haute = max(floor(R·(1 + pct) / pas)·pas ; R + pas)``, avec le pas de
    :func:`tick_size` (calculé sur ``R``) sauf si ``tick`` est fourni.
    Exemples de non-régression (§12.3 n° 3) : ``R = 4385`` ⇒ (4060, 4710) ;
    ``R = 13`` (ETIT) ⇒ haute = 14. Vectorisé (NaN ⇒ NaN).

    Returns
    -------
    (basse, haute)
        Scalaires ``float`` ou tableaux de la forme de ``ref``.
    """
    scalar = np.ndim(ref) == 0
    r = np.asarray(ref, dtype=float)
    step = tick_size(r) if tick is None else np.broadcast_to(np.asarray(tick, dtype=float), r.shape)
    with np.errstate(invalid="ignore"):
        low = np.ceil(r * (1.0 - pct) / step - _BAND_EPS) * step
        high = np.maximum(np.floor(r * (1.0 + pct) / step + _BAND_EPS) * step, r + step)
    ok = np.isfinite(r) & (r > 0)
    low = np.where(ok, low, np.nan)
    high = np.where(ok, high, np.nan)
    if scalar:
        return float(low), float(high)
    return low, high


def band_flags(
    close: np.ndarray,
    ref: np.ndarray,
    pct: float = 0.075,
    max_plausible_move: float = 0.20,
) -> tuple[np.ndarray, np.ndarray]:
    """Clôture **exactement** à la borne haute / basse (bornes au pas, :func:`price_band_limits`).

    ``haut = clôture ≥ haute(R)`` ; ``bas = clôture ≤ basse(R)``, en unités
    **brutes** du jour (le pas dépend du cours publié). Une référence
    invraisemblable (``|clôture/R − 1| > max_plausible_move``) ou manquante
    ne donne aucun drapeau.
    """
    c = np.asarray(close, dtype=float)
    r = np.asarray(ref, dtype=float)
    low, high = price_band_limits(r, pct)
    with np.errstate(divide="ignore", invalid="ignore"):
        plausible = np.isfinite(c) & np.isfinite(r) & (r > 0) & (np.abs(c / r - 1.0) <= float(max_plausible_move))
        up = plausible & (c >= high - _BAND_EPS)
        # Bande dégénérée vers le bas (référence ≤ 13 FCFA : ceil(0,925·R) = R) : une clôture
        # inchangée n'est pas « au plancher » (sinon toute séance inchangée bloquerait les
        # ventes, ETIT 2019-2021). La règle de tolérance reste active pour une vraie baisse.
        down = plausible & (c <= low + _BAND_EPS) & (low < r - _BAND_EPS)
    return up, down


def settlement_lag_sessions(date: Any, switch_date: Any = "2025-12-04", before: int = 3, after: int = 2) -> int:
    """Délai de règlement (séances) d'une négociation à ``date`` (spéc. §7.1.5, instruction 03-2025).

    J+3 pour une négociation antérieure au ``switch_date`` (04/12/2025), J+2
    à partir de cette date.
    """
    return int(before) if pd.Timestamp(date).normalize() < pd.Timestamp(switch_date) else int(after)


def quoted_half_spread(
    bid: pd.DataFrame,
    ask: pd.DataFrame,
    *,
    window: int = 120,
    min_obs: int = 20,
    lag: int = 1,
) -> pd.DataFrame:
    """Demi-spread relatif médian du carnet de clôture (spéc. §7.2, revue 01 §5.2).

    Pour chaque séance où **les deux côtés** sont présents (``bid > 0``,
    ``ask > 0``, ``ask ≥ bid``) : ``s_t = (ask − bid) / ((ask + bid)/2)``.
    Le demi-spread retenu en ``t`` est ``½ · médiane(s)`` sur les ``window``
    dernières séances **jusqu'à t − lag** inclus (``lag = 1`` : seule
    l'information publiée avant la séance d'exécution est utilisée), avec au
    moins ``min_obs`` observations, sinon NaN (le moteur prend alors
    ``CostModel.half_spread_default``). Le plancher ``pas / (2·cours)`` est
    appliqué par le moteur au cours d'exécution.

    Parameters
    ----------
    bid, ask
        Panels larges (date × symbole) des meilleures limites de clôture
        (``order_book.parquet`` : colonnes ``bid`` et ``ask``) ; une limite
        « au prix du marché » doit être NaN.
    """
    if window < 1 or min_obs < 1 or lag < 0:
        raise ValueError("window et min_obs doivent être >= 1, lag >= 0")
    b = _as_wide(bid, "bid").apply(pd.to_numeric, errors="coerce")
    a = _as_wide(ask, "ask").apply(pd.to_numeric, errors="coerce")
    idx = b.index.union(a.index)
    cols = b.columns.union(a.columns)
    b = b.reindex(index=idx, columns=cols)
    a = a.reindex(index=idx, columns=cols)
    with np.errstate(divide="ignore", invalid="ignore"):
        mid = 0.5 * (a + b)
        rel = (a - b) / mid
    ok = (b > 0) & (a > 0) & (a >= b) & np.isfinite(rel)
    rel = rel.where(ok)
    med = rel.rolling(int(window), min_periods=int(min_obs)).median()
    return 0.5 * med.shift(int(lag))


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


#: Colonnes de :attr:`BacktestResult.dividend_events` (additif v1.1, D6).
DIVIDEND_EVENT_COLUMNS = ("date", "symbol", "qty", "per_share", "per_share_boc", "credited", "boc", "gap")


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
        reporté), ``decision_date``, ``participation``, ``impact``, ``raw_qty``
        (titres réels du jour, entier ; ``qty`` est en titres ajustés).
    costs
        Coûts cumulés (frais de transaction + impact + droits de garde, FCFA).
    turnover
        Rotation **annualisée** aller simple ``252 · mean(Σ|V| / (2 NAV_{t-1}))`` ; la
        rotation mensuelle aller du critère C5 (§8.3) est
        ``metrics.monthly_one_way_turnover(result)``.
    fill_rate
        ``Σ |exécuté| · P_déc / Σ |ordonné| · P_déc`` (valeur au cours de
        décision ``P_déc``) ; NaN sans ordre.
    cash, positions
        Liquidités **réglées** disponibles et nombres de titres détenus en fin
        de séance.
    dividends, taxes
        Dividendes nets **reconnus** à la date de détachement (créance) et
        impôts payés (retenue appliquée par le moteur, impôt sur plus-values)
        par séance.
    costs_daily, turnover_daily
        Coûts (transactions, garde, tenue de compte) et rotation de chaque
        séance.
    orders
        Journal des ordres (décision, symbole, quantité, exécuté, statut ;
        ``oid``, ``parent`` (ordre annulé puis ressaisi), ``entered``).
        Statuts : ``filled``, ``expired`` (report maximal atteint),
        ``replaced`` (nouveau rebalancement), ``cancelled_ex`` /
        ``cancelled_split`` (annulé le jour ex ou de division, puis
        ressaisi), ``end_of_backtest``.
    blocked
        Événements de non-exécution (``date, symbol, side, qty, reason`` avec
        ``reason`` ∈ ``delisted``, ``not_traded``, ``suspended``, ``limit_up``,
        ``limit_down``, ``country_shock``, ``volume_cap``, ``cash``).
    rebalance_dates
        Dates de décision effectivement utilisées.
    dividends_paid
        Dividendes nets versés en cash à la date de paiement.
    receivables
        Créances en fin de séance : produits de ventes non encore réglés et
        dividendes détachés non encore payés (comptés dans la NAV).
    cost_breakdown
        Coûts quotidiens par nature (``commission, spread, impact, custody,
        account_fees``, FCFA).
    events
        Journal des événements du moteur (annulations / ressaisies d'ordres,
        chocs pays) : ``date, symbol, event, oid, new_oid, qty``.
    suspended_value
        Valeur des positions suspendues (cours au dernier cours connu) ; la
        spécification (§7.1.7) prévoit une décote de risque de 10 %
        (``meta["suspended_risk_haircut"]``).
    payables
        Frais fixes dus et non encore payés faute de cash réglé (déduits de
        la NAV) : ``equity = cash − payables + receivables + Σ q·P``.
    dividends_boc
        Les dividendes reconnus de ``dividends``, valorisés au montant de la
        ligne « (d) » du BOC (``dividend_net_boc`` ; à défaut, égal au montant
        crédité). Additif v1.1, D6 : le moteur crédite le montant **corrigé**
        (meilleure estimation du versement réel) ; l'écart total
        ``Σ dividends − Σ dividends_boc`` est publié dans
        ``meta["dividend_gap_vs_boc"]`` et dans :meth:`summary`.
    dividend_events
        Un détachement crédité par ligne : ``date, symbol, qty`` (titres
        ajustés détenus à l'ouverture), ``per_share`` et ``per_share_boc``
        (montants nets par titre ajusté), ``credited``, ``boc`` et ``gap``
        (FCFA).
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
    dividends_paid: pd.Series = field(default_factory=lambda: pd.Series(dtype=float, name="dividends_paid"))
    receivables: pd.Series = field(default_factory=lambda: pd.Series(dtype=float, name="receivables"))
    cost_breakdown: pd.DataFrame = field(default_factory=pd.DataFrame)
    events: pd.DataFrame = field(
        default_factory=lambda: pd.DataFrame(columns=["date", "symbol", "event", "oid", "new_oid", "qty"])
    )
    suspended_value: pd.Series = field(default_factory=lambda: pd.Series(dtype=float, name="suspended_value"))
    payables: pd.Series = field(default_factory=lambda: pd.Series(dtype=float, name="payables"))
    dividends_boc: pd.Series = field(default_factory=lambda: pd.Series(dtype=float, name="dividends_boc"))
    dividend_events: pd.DataFrame = field(
        default_factory=lambda: pd.DataFrame(columns=list(DIVIDEND_EVENT_COLUMNS))
    )

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
        n_finite = int(np.isfinite(self.returns.to_numpy(dtype=float)).sum())
        if n_finite < len(self.returns):
            warnings.warn(
                f"summary : {len(self.returns) - n_finite} rendement(s) non fini(s) exclu(s) des statistiques "
                f"({n_finite} observations sur {len(self.returns)})"
                + (f" ; valeur liquidative ≤ 0 depuis le {pd.Timestamp(self.meta['nav_non_positive_from']).date()}"
                   if self.meta.get("nav_non_positive_from") is not None else ""),
                stacklevel=2,
            )
        mean_nav = float(self.equity.mean()) if n else math.nan
        out.update(
            n_obs_total=int(len(self.returns)),
            n_obs_excluded=int(len(self.returns) - n_finite),
            nav_non_positive_from=self.meta.get("nav_non_positive_from"),
            final_equity=float(self.equity.iloc[-1]) if n else math.nan,
            total_costs=self.total_costs,
            cost_drag=(self.total_costs / mean_nav * periods_per_year / n) if n and mean_nav > 0 else math.nan,
            turnover=self.turnover,
            fill_rate=self.fill_rate,
            n_trades=len(self.trades),
            dividends=float(self.dividends.sum()),
            dividends_boc=float(self.dividends_boc.sum()) if len(self.dividends_boc) else float(self.dividends.sum()),
            dividend_gap_vs_boc=(float(self.dividends.sum()) - float(self.dividends_boc.sum()))
            if len(self.dividends_boc) else 0.0,
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
    "dividend_net_boc",
    "open",
    "adj_factor",
    "bid",
    "ask",
    "half_spread",
    "session_no",
    "dividend_payment_date",
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
    """Ordre en attente (quantité signée restante, en titres **ajustés**).

    Les quantités sont exprimées en titres ajustés des divisions (``float``) ; à
    chaque exécution, la quantité négociée correspond à un nombre **entier** de
    titres réels du jour (``q_brut = q · f_t``, quotité ``lot_size``).
    """

    oid: int
    j: int
    decision_pos: int
    qty: float  # quantité initiale signée (titres ajustés)
    remaining: float  # reliquat signé (titres ajustés)
    ref_price: float
    status: str = "pending"
    first_fill: pd.Timestamp | None = None
    last_fill: pd.Timestamp | None = None
    entered_pos: int = -1  # séance de saisie dans le carnet (décision + 1, ou jour de ressaisie)
    parent: int | None = None  # ordre annulé (jour ex / division) dont celui-ci est la ressaisie
    root: int = -1  # premier ordre de la chaîne (taux d'exécution)


#: Paramètres du moteur (spéc. §7.1) et leurs valeurs par défaut, modifiables
#: par mot-clé ou par le dictionnaire ``params`` de :class:`Backtester`.
ENGINE_DEFAULTS: dict[str, Any] = {
    "settlement": "brvm",  # J+3 jusqu'au 03/12/2025, J+2 ensuite ; entier = délai fixe ; 0 = immédiat
    "dividend_payment_lag": 2,  # séances entre détachement et paiement si la date de paiement est inconnue
    "cancel_on_corporate_events": True,  # annulation / ressaisie des ordres le jour ex et de division
    "band_rule": "exact_or_tolerance",  # cf. BAND_RULES
    "spread_window": 120,  # séances du spread médian de clôture
    "spread_min_obs": 20,  # observations minimales (deux côtés présents)
    "suspended_risk_haircut": 0.10,  # décote de risque d'une position suspendue (§7.1.7)
    "country_shock_block_buys": True,  # aucun achat à la séance de choc (règle pays, §4.3)
    # Après un choc pays : "persistent" (le niveau choqué persiste, rendements réels ensuite ;
    # aucun rebond artificiel) ou "shock_only" (plancher sur les seules séances de choc).
    "country_shock_recovery": "persistent",
    # Radiation (plus aucune ligne au BOC) : décote de VALORISATION appliquée à partir de la
    # séance qui suit la dernière cotation (0 = dernier cours ; 0,30 = scénario ST8). Hypothèse.
    "delisted_writedown": 0.0,
    # Séances minimales sans cotation jusqu'à la fin du panel pour conclure à une radiation
    # (sauf symbole listé dans ``reference.DELISTED_SYMBOLS``).
    "delisting_min_sessions": 5,
}

#: Modes de valorisation après un choc pays sévère (option ``country_shock_recovery``).
SHOCK_RECOVERY_MODES = ("persistent", "shock_only")

#: Correspondance avec les clés ``execution.*`` du fichier ``configs/strategy_v1.yaml``.
_YAML_EXECUTION_KEYS = {
    "carry_unfilled_max_sessions": "max_carry_sessions",
    "cancel_orders_on_ex_and_split_days": "cancel_on_corporate_events",
}

#: Clés de la section ``execution`` du YAML : celles qui ne sont pas des paramètres du
#: moteur sont lues ailleurs (``ExecutionModel`` via ``settings.apply_to_platform_config``).
#: Toute autre clé (faute de frappe) est refusée.
_YAML_EXECUTION_KNOWN = frozenset(
    {
        "price",
        "carry_unfilled_max_sessions",
        "max_volume_participation",
        "price_limit",
        "limit_tolerance",
        "block_buy_at_upper_limit",
        "block_sell_at_lower_limit",
        "cancel_orders_on_ex_and_split_days",
        "settlement",
        "dividends",
    }
)


def _engine_params(params: Mapping[str, Any] | None, explicit: Mapping[str, Any]) -> dict[str, Any]:
    """Fusionne défauts, dictionnaire ``params`` (plat ou au format du YAML) et mots-clés explicites.

    Ordre de priorité croissante : :data:`ENGINE_DEFAULTS`, section
    ``execution`` d'un dictionnaire de configuration (``load_strategy_config``),
    clés plates de ``params``, puis mots-clés passés explicitement au
    constructeur (différents de ``None``).
    """
    out = dict(ENGINE_DEFAULTS)
    extra: dict[str, Any] = {}
    if params:
        exe = params.get("execution")
        if isinstance(exe, Mapping):
            # configuration complète (format du YAML) : seule la section
            # ``execution`` concerne le moteur ; une section ``engine``
            # facultative porte les clés plates. Une clé inconnue de la section
            # ``execution`` (faute de frappe) est refusée : elle serait sinon
            # ignorée en silence alors que l'empreinte de configuration change.
            bad = sorted(set(map(str, exe)) - _YAML_EXECUTION_KNOWN)
            if bad:
                raise KeyError(f"clés inconnues dans la section execution : {bad}")
            for k, v in exe.items():
                if k in _YAML_EXECUTION_KEYS:
                    extra[_YAML_EXECUTION_KEYS[k]] = v
                elif k == "settlement" and isinstance(v, Sequence) and not isinstance(v, str):
                    extra["settlement"] = "brvm"  # règle J+3 / J+2 de la spécification
            eng = params.get("engine")
            if isinstance(eng, Mapping):
                extra.update(eng)
        else:
            extra.update(params)
    unknown = set(extra) - set(out) - {"max_carry_sessions"}
    if unknown:
        raise KeyError(f"paramètres du moteur inconnus : {sorted(unknown)}")
    out.update(extra)
    out.update({k: v for k, v in explicit.items() if v is not None})
    if out["band_rule"] not in BAND_RULES:
        raise ValueError(f"band_rule doit valoir l'un de {BAND_RULES}")
    if out["country_shock_recovery"] not in SHOCK_RECOVERY_MODES:
        raise ValueError(f"country_shock_recovery doit valoir l'un de {SHOCK_RECOVERY_MODES}")
    if not 0.0 <= float(out["delisted_writedown"]) < 1.0:
        raise ValueError("delisted_writedown doit appartenir à [0, 1[")
    if int(out["delisting_min_sessions"]) < 1:
        raise ValueError("delisting_min_sessions doit être >= 1")
    return out


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
        * ``dividend_net`` : dividende net par action, placé à la date de
          détachement (0 sinon) : droit reconnu ce jour-là (créance), cash
          versé à la date de paiement ; une date absente du calendrier (BOC
          manquant) est reportée à la séance suivante (:func:`_snap_to_calendar`) ;
        * ``change_pct``, ``prev_close``, ``ref_price`` : voir aussi les bornes
          exactes (:meth:`_reference_raw` : ``ref_price`` de la veille en
          priorité, puis variation publiée, puis ``prev_close − dividende``) ;
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
          source si les dividendes fournis sont bruts, chocs pays) ;
        * ``dividend_payment_date`` (optionnel) : panel large aligné sur
          ``dividend_net`` (ligne de la date ex) donnant la date de paiement ;
          à défaut, paiement ``dividend_payment_lag`` séances après la date ex ;
        * ``bid`` / ``ask`` (optionnels, unités brutes) : meilleures limites
          de clôture du carnet (``order_book.parquet``), pour le demi-spread
          propre au titre (:func:`quoted_half_spread`) ; ou ``half_spread``
          (fraction, déjà calculée) ; à défaut ``half_spread_default`` ;
        * ``session_no`` (optionnel) : numéro global de séance (panel large ou
          ``Series`` par date) ; il compte les séances sans BOC (2021) pour
          le report des ordres, le règlement, le paiement des dividendes et
          le prorata des frais ; à défaut, une ligne = une séance ;
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
        ``no_trade_band`` (|Δw| < bande ⇒ pas d'ordre, sauf entrée sur un titre
        non détenu ou sortie totale, §6).
    lot_size
        Quotité de négociation (1 à la BRVM).
    max_order_age
        Nombre maximal de séances de vie d'un ordre depuis sa décision.
        ``"auto"`` (défaut) : ``1 + ExecutionModel.max_carry_sessions``
        (première tentative en t+1, puis au plus 10 reports, spéc. §7.1.1) ;
        ``None`` : jusqu'au rebalancement suivant (comportement historique) ;
        entier : valeur explicite. Les séances sont comptées sur
        ``session_no`` (BOC manquants compris).
    settlement
        ``"brvm"`` (défaut) : J+3 pour une négociation antérieure au
        ``ExecutionModel.settlement_switch_date``, J+2 ensuite ; entier
        ``n`` : délai fixe de ``n`` séances ; ``0`` : règlement immédiat (le
        produit d'une vente finance les achats du jour, comportement
        historique).
    dividend_payment_lag
        Séances entre la date ex et le paiement quand la date de paiement
        est inconnue (2 par défaut, médiane observée, spéc. §5.2.3) ; ``0`` :
        cash crédité dès le détachement (comportement historique).
    cancel_on_corporate_events
        Annuler puis ressaisir le jour même les ordres en attente le jour ex
        et le jour de division (spéc. §7.1.4).
    band_rule
        Détection de la clôture à la borne : voir :data:`BAND_RULES`.
    spread_window, spread_min_obs
        Fenêtre (séances) et observations minimales du spread médian.
    country_shocks
        Chocs pays sévères (spéc. §4.3, §7.1.8) : ``DataFrame`` à colonnes
        ``country, date`` (+ ``sessions`` facultatif, 1 par défaut) ou liste
        de tuples ``(pays, date[, séances])``. Les ``sessions`` premières
        séances **strictement postérieures** à la date d'annonce sont
        supposées au plancher pour les titres du pays (pays du siège) :
        valorisation au plus à la borne basse, aucun vendeur servi, et aucun
        achat si ``country_shock_block_buys``. Hypothèse de stress.
    order_book
        Table longue ``order_book.parquet`` (``date, symbol, bid, ask``) si
        les panels ``bid`` / ``ask`` ne sont pas fournis.
    params
        Dictionnaire optionnel de paramètres du moteur : clés de
        :data:`ENGINE_DEFAULTS`, ou configuration complète
        (``settings.load_strategy_config()``, section ``execution``). Les
        mots-clés explicites l'emportent.
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
        max_order_age: int | str | None = "auto",
        vwap_tolerance: float = 0.20,
        max_plausible_move: float = 0.20,
        periods_per_year: int = TRADING_DAYS,
        jump_warning: float | None = 0.40,
        settlement: str | int | None = None,
        dividend_payment_lag: int | None = None,
        cancel_on_corporate_events: bool | None = None,
        band_rule: str | None = None,
        spread_window: int | None = None,
        spread_min_obs: int | None = None,
        country_shocks: Any = None,
        order_book: pd.DataFrame | None = None,
        params: Mapping[str, Any] | None = None,
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
        if not 0.0 < self.execution.max_volume_participation <= 1.0:
            raise ValueError("max_volume_participation doit être dans ]0, 1]")
        if self.execution.price not in ("vwap", "close", "open"):
            raise ValueError("ExecutionModel.price doit valoir 'vwap', 'close' ou 'open'")
        opts = _engine_params(
            params,
            {
                "settlement": settlement,
                "dividend_payment_lag": dividend_payment_lag,
                "cancel_on_corporate_events": cancel_on_corporate_events,
                "band_rule": band_rule,
                "spread_window": spread_window,
                "spread_min_obs": spread_min_obs,
            },
        )
        carry_max = int(opts.pop("max_carry_sessions", self.execution.max_carry_sessions))
        if isinstance(max_order_age, str):
            if max_order_age != "auto":
                raise ValueError("max_order_age doit valoir 'auto', None ou un entier >= 1")
            max_order_age = 1 + max(0, carry_max)
        if max_order_age is not None and int(max_order_age) < 1:
            raise ValueError("max_order_age doit être >= 1")
        self.options: dict[str, Any] = opts
        sett = opts["settlement"]
        if not (sett == "brvm" or (isinstance(sett, (int, np.integer)) and not isinstance(sett, bool) and sett >= 0)):
            raise ValueError("settlement doit valoir 'brvm' ou un entier >= 0")
        if int(opts["dividend_payment_lag"]) < 0:
            raise ValueError("dividend_payment_lag doit être >= 0")
        self.settlement = sett
        self.dividend_payment_lag = int(opts["dividend_payment_lag"])
        self.cancel_on_corporate_events = bool(opts["cancel_on_corporate_events"])
        self.band_rule = str(opts["band_rule"])
        self.spread_window = int(opts["spread_window"])
        self.spread_min_obs = int(opts["spread_min_obs"])
        self.suspended_risk_haircut = float(opts["suspended_risk_haircut"])
        self.country_shock_block_buys = bool(opts["country_shock_block_buys"])
        self.country_shock_recovery = str(opts["country_shock_recovery"])
        self.delisted_writedown = float(opts["delisted_writedown"])
        self.delisting_min_sessions = int(opts["delisting_min_sessions"])
        self._order_book = order_book
        self._country_shocks_raw = country_shocks
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
        """Pré-calcule prix d'exécution, exécutabilité, bandes, spreads, dividendes et calendrier."""
        ex = self.execution
        close = self._panels["close"]
        c = close.to_numpy(dtype=float)
        c = np.where(c > 0, c, np.nan)
        self._close = c
        T = c.shape[0]

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
        # Jour de division / d'ajustement du nombre de titres : le facteur change.
        split_day = np.zeros(c.shape, dtype=bool)
        if T > 1:
            split_day[1:] = np.abs(af[1:] / af[:-1] - 1.0) > 1e-9
        self._split_day = split_day

        # Calendrier des séances (BOC manquants compris) et délai de règlement.
        self._sess = self._session_numbers()
        steps = np.ones(T, dtype=float)
        if T > 1:
            steps[1:] = np.maximum(np.diff(self._sess), 1)
        self._steps = steps
        if self.settlement == "brvm":
            switch = pd.Timestamp(ex.settlement_switch_date)
            self._lag_rows = np.where(self.dates < switch, 3, 2).astype(np.int64)
        else:
            self._lag_rows = np.full(T, int(self.settlement), dtype=np.int64)

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
        suspended = np.zeros(c.shape, dtype=bool)
        if "status" in self._panels and self._panels["status"] is not None:
            st = _as_wide(self._panels["status"], "status").reindex(index=self.dates, columns=self.symbols)
            st_low = st.astype(object).where(st.notna(), "").astype(str)
            st_low = st_low.apply(lambda col: col.str.strip().str.lower())
            tradeable &= ~st_low.isin(_BLOCKING_STATUS).to_numpy(dtype=bool)
            suspended = (st_low == "suspended").to_numpy(dtype=bool)
        self._tradeable = tradeable
        self._suspended = suspended

        # Valorisation : dernier cours de clôture connu (à défaut, dernier prix
        # d'exécution observé si la clôture manque un jour d'échange).
        val_src = np.where(np.isfinite(c), c, np.where(tradeable, px, np.nan))
        px_val0 = pd.DataFrame(val_src).ffill().to_numpy(dtype=float)

        # Dividendes (montant par titre ajusté) et retenue éventuelle ; une date
        # de détachement hors calendrier est reportée à la séance suivante.
        div = self._dividend_array()
        div = np.zeros_like(c) if div is None else np.clip(div, 0.0, None)
        self._ex_day = div > 0
        div_adj = div * af
        # Additif v1.1, D6 : montant de la ligne « (d) » du BOC, pour publier l'écart avec le
        # montant corrigé effectivement crédité ; à défaut, identique (écart nul).
        div_boc = self._dividend_array("dividend_net_boc")
        self.has_dividend_boc = div_boc is not None
        div_boc_adj = (np.clip(div_boc, 0.0, None) * af) if div_boc is not None else div_adj
        if not self.taxes.dividends_reported_net:
            rates = self._withholding_rates()
            self._div = div_adj * (1.0 - rates)[None, :]
            self._div_tax = div_adj * rates[None, :]
            self._div_boc = div_boc_adj * (1.0 - rates)[None, :]
        else:
            self._div = div_adj
            self._div_tax = np.zeros_like(div_adj)
            self._div_boc = div_boc_adj
        self._div_pay_pos = self._payment_positions(self._ex_day)

        chg = self._wide("change_pct")
        prev = self._wide("prev_close")
        refp = self._wide("ref_price")

        # Bornes exactes au pas autour de la référence ajustée (unités brutes du jour).
        raw_close = c / af
        ref_raw = self._reference_raw(raw_close, div, af, px_val0, chg, prev, refp)
        self._ref_raw = ref_raw
        ex_up, ex_down = band_flags(raw_close, ref_raw, ex.price_limit, self.max_plausible_move)

        # Règle de tolérance (|clôture / R − 1| ≥ 7,5 % − 0,2 %) calculée sur la MÊME référence
        # ajustée R que la règle exacte. La variation publiée ``change_pct`` est parfois calculée
        # par la BRVM sur la clôture NON ajustée du dividende (jours ex de 2017-2019 : SOGC le
        # 19/07/2018 publie −7,89 % pour +3,86 % contre la référence ajustée) : elle ne sert plus
        # que de repli quand aucune référence n'est disponible.
        with np.errstate(divide="ignore", invalid="ignore"):
            move = np.where(np.isfinite(ref_raw) & (ref_raw > 0), raw_close / ref_raw - 1.0, np.nan)
            if chg is not None:
                move = np.where(np.isfinite(move), move, chg / 100.0)
        self._move = move
        tol_up, tol_down = limit_flags(move, ex.price_limit, ex.limit_tolerance, self.max_plausible_move)
        if self.band_rule == "exact":
            self._lim_up, self._lim_down = ex_up, ex_down
        elif self.band_rule == "tolerance":
            self._lim_up, self._lim_down = tol_up, tol_down
        else:
            self._lim_up, self._lim_down = ex_up | tol_up, ex_down | tol_down

        # Chocs pays sévères (§4.3, §7.1.8) : planchers CUMULÉS séance après séance, sans
        # vendeur servi ; le multiplicateur s'applique à la valorisation ET au prix d'exécution
        # (chemin de stress cohérent). La valorisation réelle est d'abord reportée vers l'avant
        # (cours NaN), puis le multiplicateur est appliqué (aucun report du plancher par ffill).
        self._shock_events: list[tuple[Any, ...]] = []
        shock = self._shock_mask()
        self._shock = shock
        mult = self._shock_multipliers(shock, px_val0, ref_raw, af)
        self._shock_mult = mult
        self._px_exec = np.where(np.isfinite(px), px * mult, px)

        # Radiation : plus aucune cotation jusqu'à la fin du panel (spéc. §5.5).
        self._delisted = self._delisting_mask(c)
        val = px_val0 * mult
        if self.delisted_writedown > 0 and self._delisted.any():
            val = np.where(self._delisted, val * (1.0 - self.delisted_writedown), val)
        self._px_val = val

        # Demi-spread propre à chaque titre (fraction du montant, par côté).
        self._hs = self._half_spreads(px, af)
        self._check_price_jumps(c, div_adj, px_val0)

    def _session_numbers(self) -> np.ndarray:
        """Numéro global de séance par ligne (``session_no``), sinon ``0..T-1``.

        Les séances sans BOC (2021) sont comptées : entre deux lignes, l'écart
        de numéro mesure les séances réellement écoulées (report des ordres,
        règlement, paiement des dividendes, prorata des frais).
        """
        T = len(self.dates)
        raw = self._panels.get("session_no")
        s: pd.Series | None = None
        if isinstance(raw, pd.DataFrame):
            df = _as_wide(raw, "session_no").reindex(self.dates)
            s = df.apply(pd.to_numeric, errors="coerce").max(axis=1)
        elif isinstance(raw, pd.Series):
            ser = raw.copy()
            if not isinstance(ser.index, pd.DatetimeIndex):
                parsed = _parse_date_index(ser.index)
                if parsed is None:
                    raise TypeError("session_no : index de dates attendu")
                ser = ser.set_axis(parsed)
            ser = ser[~ser.index.duplicated(keep="last")]
            s = pd.to_numeric(ser, errors="coerce").reindex(self.dates)
        if s is None or not s.notna().any():
            return np.arange(T, dtype=np.int64)
        vals = s.to_numpy(dtype=float)
        # numéros manquants : séance précédente + 1 (jamais de remplissage arrière)
        out = np.empty(T, dtype=float)
        last = math.nan
        for i, v in enumerate(vals):
            if math.isfinite(v):
                last = v
            else:
                last = (last + 1.0) if math.isfinite(last) else float(i)
            out[i] = last
        if np.any(np.diff(out) <= 0):
            warnings.warn("session_no non strictement croissant : une ligne = une séance", stacklevel=4)
            return np.arange(T, dtype=np.int64)
        return out.astype(np.int64)

    def _payment_positions(self, ex_mask: np.ndarray) -> np.ndarray:
        """Ligne de paiement de chaque dividende (``T`` si au-delà du panel ; −1 sans dividende).

        Date de paiement lue dans ``dividend_payment_date`` (ligne de la date
        ex, reportée comme ``dividend_net`` sur la séance suivante si elle est
        hors calendrier) ; à défaut, première ligne dont la séance est
        ``≥ séance_ex + dividend_payment_lag``. Un paiement daté avant la date
        ex (donnée incohérente) est ramené à la date ex.
        """
        T, N = ex_mask.shape
        pos = np.full((T, N), -1, dtype=np.int64)
        ti, ji = np.nonzero(ex_mask)
        if ti.size == 0:
            return pos
        known: dict[tuple[int, int], pd.Timestamp] = {}
        raw = self._panels.get("dividend_payment_date")
        if isinstance(raw, pd.DataFrame) and len(self.dates):
            df = _as_wide(raw, "dividend_payment_date")
            for col in df.columns:
                if col not in self.symbols:
                    continue
                ser = pd.to_datetime(df[col], errors="coerce").dropna()
                if ser.empty:
                    continue
                jj = int(self.symbols.get_loc(col))
                rows = self.dates.searchsorted(pd.DatetimeIndex(ser.index), side="left")
                for r, pay in zip(rows, ser.to_numpy(), strict=True):
                    if 0 <= r < T:
                        cur = known.get((int(r), jj))
                        pay_ts = pd.Timestamp(pay)
                        known[(int(r), jj)] = pay_ts if cur is None else max(cur, pay_ts)
        for t, j in zip(ti, ji, strict=True):
            pay = known.get((int(t), int(j)))
            if pay is not None:
                p = int(self.dates.searchsorted(pay.normalize(), side="left"))
            elif self.dividend_payment_lag == 0:
                p = int(t)
            else:
                target = self._sess[t] + self.dividend_payment_lag
                p = int(np.searchsorted(self._sess, target, side="left"))
            pos[t, j] = max(int(t), p)
        return pos

    def _reference_raw(
        self,
        raw_close: np.ndarray,
        div_raw: np.ndarray,
        af: np.ndarray,
        px_val0: np.ndarray,
        chg: np.ndarray | None,
        prev: np.ndarray | None,
        refp: np.ndarray | None,
    ) -> np.ndarray:
        """Référence ajustée de la séance ``t`` en unités **brutes** du jour (bornes exactes).

        Par ordre de préférence :

        1. ``ref_price`` publié la veille (BOC de t − 1, déjà ajusté du
           détachement ou de la division du jour), si t − 1 est la séance
           immédiatement précédente (pas de BOC manquant) ;
        2. ``clôture / (1 + change_pct)`` arrondi au pas (variation publiée,
           calculée par la BRVM sur la référence ajustée) ;
        3. ``prev_close − dividende`` du jour (avant le n° 2 un jour ex : la
           variation publiée y a parfois été calculée sur la clôture non ajustée) ;
        4. dernier cours connu, ramené aux unités du jour, moins le dividende.
        """
        T, N = raw_close.shape
        ref = np.full((T, N), np.nan)
        with np.errstate(divide="ignore", invalid="ignore"):
            if refp is not None and T > 1:
                prior = np.vstack([np.full((1, N), np.nan), refp[:-1]])
                contiguous = np.concatenate([[False], np.diff(self._sess) == 1])[:, None]
                ref = np.where(contiguous & np.isfinite(prior) & (prior > 0), prior, np.nan)
            implied = np.full((T, N), np.nan)
            if chg is not None:
                implied = raw_close / (1.0 + chg / 100.0)
                step = tick_size(implied)
                implied = np.round(implied / step) * step
            implied = np.where(np.isfinite(implied) & (implied > 0), implied, np.nan)
            cand = np.full((T, N), np.nan) if prev is None else prev - div_raw
            cand = np.where(np.isfinite(cand) & (cand > 0), cand, np.nan)
            # Jour ex : la variation publiée a parfois été calculée sur la clôture NON ajustée du
            # dividende (2017-2019) ; ``prev_close − dividende`` passe alors avant elle.
            ex_rows = div_raw > 0
            first = np.where(ex_rows, cand, implied)
            second = np.where(ex_rows, implied, cand)
            ref = np.where(np.isfinite(ref), ref, first)
            ref = np.where(np.isfinite(ref), ref, second)
            last = np.vstack([np.full((1, N), np.nan), px_val0[:-1]]) / af - div_raw
            ref = np.where(np.isfinite(ref), ref, np.where(last > 0, last, np.nan))
        return ref

    def _symbol_countries(self) -> np.ndarray:
        """Pays du siège de chaque symbole (panel ``country``, sinon ``reference.country_of``)."""
        country = self._panels.get("country")
        if isinstance(country, pd.Series):
            ctry = country.reindex(self.symbols).astype(object)
        else:
            ctry = pd.Series(np.nan, index=self.symbols, dtype=object)
        missing = ctry.isna()
        if missing.any():
            from brvm_alpha.reference import country_of

            ctry[missing] = [country_of(str(s)) for s in self.symbols[missing.to_numpy()]]
        return np.array([str(x).upper() for x in ctry], dtype=object)

    def _shock_mask(self) -> np.ndarray:
        """Séances de choc pays sévère (spéc. §4.3, §7.1.8) par (séance, titre)."""
        T, N = len(self.dates), len(self.symbols)
        mask = np.zeros((T, N), dtype=bool)
        spec = self._country_shocks_raw
        if spec is None or T == 0:
            return mask
        rows: list[tuple[str, pd.Timestamp, int]] = []
        if isinstance(spec, pd.DataFrame):
            if not {"country", "date"}.issubset(spec.columns):
                raise KeyError("country_shocks : colonnes 'country' et 'date' attendues")
            for rec in spec.to_dict("records"):
                n = rec.get("sessions", 1)
                n = 1 if n is None or (isinstance(n, float) and math.isnan(n)) else int(n)
                rows.append((str(rec["country"]).upper(), pd.Timestamp(rec["date"]), n))
        else:
            for item in spec:
                if len(item) not in (2, 3):
                    raise ValueError("country_shocks : tuples (pays, date[, séances]) attendus")
                n = int(item[2]) if len(item) == 3 else 1
                rows.append((str(item[0]).upper(), pd.Timestamp(item[1]), n))
        ctry = self._symbol_countries()
        for country, when, n in rows:
            if n < 1:
                raise ValueError("country_shocks : au moins une séance de choc")
            cols = ctry == country
            start = int(self.dates.searchsorted(when, side="right"))  # séance suivant l'annonce
            stop = min(T, start + n)
            if start >= T or not cols.any():
                continue
            mask[start:stop, cols] = True
            for t in range(start, stop):
                for j in np.flatnonzero(cols):
                    self._shock_events.append((self.dates[t], self.symbols[j], "choc_pays_plancher", -1, -1, 0))
        return mask

    def _shock_multipliers(
        self, shock: np.ndarray, real_val: np.ndarray, ref_raw: np.ndarray, af: np.ndarray
    ) -> np.ndarray:
        """Multiplicateur ``m_{t,i}`` du chemin de stress d'un choc pays sévère (§4.3, §7.1.8, ST4).

        Pendant les séances de choc, les planchers se **cumulent** : la référence de la
        séance ``k`` est le niveau choqué de la séance ``k − 1`` et
        ``plancher_k = ceil(réf_k · 0,925 / pas) · pas`` (unités brutes du jour) ; le niveau
        choqué vaut ``min(cours réel · m, plancher_k)``. Trois séances sur un cours plat de
        1 000 donnent 925, 860 puis 800 (arrondi au pas à chaque séance), et non −7,5 %.

        Après le choc (option ``country_shock_recovery``) :

        * ``"persistent"`` (défaut) : ``m`` reste constant, la valorisation et l'exécution
          suivent les rendements **réels** à partir du niveau choqué (aucun rebond
          artificiel vers la clôture réelle). Si le cours réel a lui-même atteint le
          plancher, ``m = 1`` : aucun double comptage d'une baisse observée ;
        * ``"shock_only"`` : le plancher ne s'applique qu'aux séances de choc ; la
          valorisation revient à la clôture réelle ensuite (rebond possible, documenté).

        Hypothèse de stress, pas une observation.
        """
        T, N = shock.shape
        m = np.ones((T, N))
        if not shock.any():
            return m
        pct = float(self.execution.price_limit)
        persistent = self.country_shock_recovery == "persistent"
        for j in np.flatnonzero(shock.any(axis=0)):
            cur = 1.0
            prev_level = math.nan  # niveau choqué de la séance précédente (unités brutes de cette séance)
            in_shock = False
            for t in range(T):
                f = af[t, j]
                real_raw = real_val[t, j] / f if f > 0 else math.nan
                if not shock[t, j]:
                    in_shock = False
                    if not persistent:
                        cur = 1.0
                    m[t, j] = cur
                    continue
                if in_shock and math.isfinite(prev_level):
                    ref = prev_level * af[t - 1, j] / f
                else:
                    r = ref_raw[t, j]
                    if not (math.isfinite(r) and r > 0) and t > 0:
                        r = real_val[t - 1, j] / f
                    ref = r * cur
                if not (math.isfinite(ref) and ref > 0 and math.isfinite(real_raw) and real_raw > 0):
                    m[t, j] = cur
                    in_shock = False
                    continue
                floor = float(price_band_limits(ref, pct)[0])
                level = min(real_raw * cur, floor)
                cur = level / real_raw
                m[t, j] = cur
                prev_level = level
                in_shock = True
        return m

    def _delisting_mask(self, c: np.ndarray) -> np.ndarray:
        """Séances postérieures à la **dernière cotation** d'un titre radié (spéc. §5.5).

        Un titre est jugé radié s'il n'a plus aucune clôture jusqu'à la fin du panel
        pendant au moins ``delisting_min_sessions`` séances, ou s'il figure dans
        ``reference.DELISTED_SYMBOLS`` (SVOC/MOVIS le 26/06/2025, TTRC…). La position
        reste bloquée (motif ``delisted``), est suivie dans ``suspended_value`` (décote de
        risque) et, si ``delisted_writedown > 0``, sa valorisation est réduite.
        """
        T, N = c.shape
        out = np.zeros((T, N), dtype=bool)
        if T == 0:
            return out
        try:
            from brvm_alpha.reference import DELISTED_SYMBOLS

            known = {str(s) for s in DELISTED_SYMBOLS}
        except ImportError:  # pragma: no cover - module de référence absent
            known = set()
        finite = np.isfinite(c)
        for j in range(N):
            rows = np.flatnonzero(finite[:, j])
            if rows.size == 0:
                continue
            last = int(rows[-1])
            if last >= T - 1:
                continue
            if (T - 1 - last) >= self.delisting_min_sessions or str(self.symbols[j]) in known:
                out[last + 1 :, j] = True
        return out

    def _quote_panels(self) -> tuple[pd.DataFrame | None, pd.DataFrame | None]:
        """Panels larges ``bid`` / ``ask`` (panels, sinon table longue ``order_book``)."""
        bid, ask = self._panels.get("bid"), self._panels.get("ask")
        if isinstance(bid, pd.DataFrame) and isinstance(ask, pd.DataFrame):
            return bid, ask
        book = self._order_book if self._order_book is not None else self._panels.get("order_book")
        if isinstance(book, pd.DataFrame) and {"date", "symbol", "bid", "ask"}.issubset(book.columns):
            b = book.loc[:, ["date", "symbol", "bid", "ask"]].copy()
            b["date"] = pd.to_datetime(b["date"])
            b = b.drop_duplicates(["date", "symbol"], keep="last")
            return (
                b.pivot(index="date", columns="symbol", values="bid").sort_index(),
                b.pivot(index="date", columns="symbol", values="ask").sort_index(),
            )
        return None, None

    def _half_spreads(self, px_exec: np.ndarray, af: np.ndarray) -> np.ndarray:
        """Demi-spread par (séance, titre) : ``mult × max(mesure ou défaut ; pas / (2·cours))``.

        La mesure (:func:`quoted_half_spread`, ou le panel ``half_spread``)
        n'utilise que le carnet publié jusqu'à la veille ; le plancher est
        calculé au cours d'exécution brut du jour (un pas de cotation est le
        plus petit spread possible).
        """
        T, N = px_exec.shape
        self.half_spread_measured_share = 0.0
        mult = float(self.costs.half_spread_mult)
        if mult <= 0.0:
            return np.zeros((T, N))
        base = self._wide("half_spread")
        if base is None:
            bid, ask = self._quote_panels()
            if bid is not None and ask is not None:
                hs = quoted_half_spread(
                    bid, ask, window=self.spread_window, min_obs=self.spread_min_obs, lag=1
                ).reindex(index=self.dates, columns=self.symbols)
                base = hs.to_numpy(dtype=float)
        measured = np.zeros((T, N), dtype=bool) if base is None else (np.isfinite(base) & (base >= 0))
        if measured.size:
            self.half_spread_measured_share = float(measured.mean())
        b = np.full((T, N), float(self.costs.half_spread_default))
        if base is not None:
            b = np.where(measured, base, b)
        with np.errstate(divide="ignore", invalid="ignore"):
            raw_px = px_exec / af
            floor = np.where(np.isfinite(raw_px) & (raw_px > 0), tick_size(raw_px) / (2.0 * raw_px), 0.0)
        return mult * np.maximum(b, np.nan_to_num(floor))

    def _dividend_array(self, key: str = "dividend_net") -> np.ndarray | None:
        """``dividend_net`` (ou ``key``) aligné sur (séances, symboles), dates hors calendrier reportées."""
        if key == "dividend_net":
            self.n_dividend_dates_off_calendar = 0
        raw = self._panels.get(key)
        if raw is None:
            return None
        df = _as_wide(raw, key)
        n_off = int((~pd.DatetimeIndex(df.index).isin(self.dates)).sum())
        df = _snap_to_calendar(df, self.dates).reindex(columns=self.symbols)
        if key == "dividend_net":
            self.n_dividend_dates_off_calendar = n_off
        arr = df.apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
        return np.where(np.isfinite(arr), arr, 0.0)

    def _check_price_jumps(self, c: np.ndarray, div_adj: np.ndarray, real_val: np.ndarray | None = None) -> None:
        """Repère les variations de clôture invraisemblables (division non ajustée ?).

        ``real_val`` : valorisation **réelle** reportée (sans choc pays ni décote de
        radiation) ; à défaut, la valorisation du moteur.
        """
        self.price_jumps = pd.DataFrame(columns=["date", "symbol", "ratio"])
        if self.jump_warning is None or c.shape[0] < 2:
            return
        s = self.jump_warning
        lo, hi = 1.0 - s, 1.0 / (1.0 - s)
        base = self._px_val if real_val is None else real_val
        prev = np.vstack([np.full((1, c.shape[1]), np.nan), base[:-1]])
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
        issuer = getattr(self.taxes, "issuer_withholding", {}) or {}
        return np.array(
            [float(issuer.get(str(s), table.get(str(x), 0.0))) for s, x in zip(self.symbols, ctry, strict=True)],
            dtype=float,
        )

    # -- exécution ------------------------------------------------------------

    def _round_lot(self, q: np.ndarray) -> np.ndarray:
        """Arrondi vers le bas à la quotité, en titres **réels** (``q`` en titres bruts du jour)."""
        lot = self.lot_size
        return (np.floor(np.asarray(q, dtype=float) / lot + 1e-9) * lot).astype(np.int64)

    @staticmethod
    def _raw_count(q_adj: float, f: float) -> int:
        """Nombre entier de titres réels du jour correspondant à ``q_adj`` titres ajustés (≥ 0)."""
        x = abs(float(q_adj)) * float(f)
        return int(math.floor(x + 1e-6))

    def _buy_totals(self, q: np.ndarray, px: np.ndarray, vol: np.ndarray, hs: np.ndarray | None = None) -> np.ndarray:
        amount = q * px
        part = np.where(vol > 0, q / np.where(vol > 0, vol, 1.0), 0.0)
        return amount + trade_cost(amount, part, self.costs, hs)

    def _affordable(
        self,
        desired: np.ndarray,
        px: np.ndarray,
        vol: np.ndarray,
        cash: float,
        hs: np.ndarray | None = None,
    ) -> np.ndarray:
        """Réduction au prorata des achats pour respecter ``Σ coût total ≤ cash``.

        Quantités, prix et volumes en unités **brutes du jour** (titres réels) : l'arrondi
        à la quotité donne un nombre entier de titres réels. Cherche par dichotomie le
        plus grand ``f ∈ [0, 1]`` tel que ``Σ_i T_i(⌊f · q_i⌋) ≤ cash`` où
        ``T_i(q) = q P_i + coût_i(q)`` est croissante en ``q`` ; ``f = 0`` est toujours
        admissible (cash ≥ 0).
        """
        if desired.size == 0:
            return desired
        if self._buy_totals(desired, px, vol, hs).sum() <= cash:
            return desired
        lo, hi = 0.0, 1.0
        for _ in range(64):
            mid = 0.5 * (lo + hi)
            if self._buy_totals(self._round_lot(desired * mid), px, vol, hs).sum() <= cash:
                lo = mid
            else:
                hi = mid
        return self._round_lot(desired * lo)

    def _block_reason(self, t: int, j: int, side: str) -> str | None:
        """Motif de non-exécution d'un ordre (``None`` si exécutable), par ordre de priorité."""
        if self._delisted[t, j]:
            return "delisted"
        if self._suspended[t, j]:
            return "suspended"
        if self._shock[t, j] and (side == "sell" or self.country_shock_block_buys):
            return "country_shock"
        if not self._tradeable[t, j]:
            return "not_traded"
        if side == "sell" and self._lim_down[t, j]:
            return "limit_down"
        if side == "buy" and self._lim_up[t, j]:
            return "limit_up"
        return None

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
        recv_hist = np.zeros(n_sim)
        pay_hist = np.zeros(n_sim)
        susp_hist = np.zeros(n_sim)
        pos_hist = np.zeros((n_sim, N), dtype=float)
        costs_daily = np.zeros(n_sim)
        breakdown = np.zeros((n_sim, 5))  # commission, spread, impact, garde, tenue de compte
        div_daily = np.zeros(n_sim)
        div_boc_daily = np.zeros(n_sim)
        div_events: list[tuple[Any, ...]] = []
        paid_daily = np.zeros(n_sim)
        tax_daily = np.zeros(n_sim)
        traded_value = np.zeros(n_sim)

        # Positions en titres AJUSTÉS des divisions (``float``) ; q · f_t est un nombre entier
        # de titres réels à chaque séance (arrondis en titres bruts, rompus des attributions).
        q = np.zeros(N, dtype=float)
        avg_cost = np.zeros(N)
        delisted_log: list[dict[str, Any]] = []
        delisted_seen: set[int] = set()
        cash = self.capital
        payable = 0.0  # frais dus non encore payés (garde, tenue de compte)
        sale_recv: list[tuple[int, float]] = []  # (séance de règlement, produit net)
        div_recv: list[tuple[int, float]] = []  # (ligne de paiement, montant net)
        orders: list[_Order] = []
        pending: dict[int, _Order] = {}
        trades: list[tuple[Any, ...]] = []
        blocked: list[tuple[Any, ...]] = []
        events: list[tuple[Any, ...]] = [e for e in self._shock_events if sim_dates[0] <= e[0] <= sim_dates[-1]]
        used_reb: list[pd.Timestamp] = []
        warned: set[str] = set()

        daily_cash_rate = (1.0 + ex.cash_rate_annual) ** (1.0 / self.periods_per_year) - 1.0
        custody_daily = float(costs.annual_custody) / self.periods_per_year
        line_fee_daily = float(getattr(costs, "account_fee_per_line_fcfa", 0.0)) / self.periods_per_year
        cgt = float(self.taxes.capital_gains_tax)
        part_max = float(ex.max_volume_participation)
        sess = self._sess
        prev_nav = self.capital

        def pay_fees() -> None:
            nonlocal cash, payable
            if payable > 0:
                paid = min(cash, payable)
                cash -= paid
                payable -= paid

        for k, t in enumerate(range(i0, i1 + 1)):
            day = dates[t]
            steps = float(self._steps[t]) if k > 0 else 1.0
            cost_today = 0.0
            tax_today = 0.0
            value_today = 0.0
            # 1. rémunération du cash
            if k > 0 and daily_cash_rate != 0.0:
                cash *= (1.0 + daily_cash_rate) ** steps
            # 2. règlements : ventes réglées, dividendes payés
            if sale_recv:
                due = [a for s, a in sale_recv if s <= sess[t]]
                if due:
                    cash += float(sum(due))
                    sale_recv = [(s, a) for s, a in sale_recv if s > sess[t]]
            if div_recv:
                due = [a for p, a in div_recv if p <= t]
                if due:
                    amt = float(sum(due))
                    cash += amt
                    paid_daily[k] += amt
                    div_recv = [(p, a) for p, a in div_recv if p > t]
            # 3. dividendes reconnus (positions d'ouverture du jour ex)
            if q.any():
                d_row = self._div[t]
                d = float(q @ d_row)
                if d > 0:
                    div_daily[k] = d
                    b_row = self._div_boc[t]
                    div_boc_daily[k] = float(q @ b_row)
                    for jd in np.flatnonzero((q != 0) & (d_row > 0)):
                        amt = float(q[jd] * d_row[jd])
                        amt_boc = float(q[jd] * b_row[jd])
                        div_events.append((day, self.symbols[jd], float(q[jd]), float(d_row[jd]), float(b_row[jd]),
                                           amt, amt_boc, amt - amt_boc))
                        p = int(self._div_pay_pos[t, jd])
                        if p <= t:
                            cash += amt
                            paid_daily[k] += amt
                        else:
                            div_recv.append((p, amt))
                tax_today += float(q @ self._div_tax[t])
            # 4. frais fixes sur les positions d'ouverture (prorata des séances)
            if k > 0 and q.any():
                if custody_daily > 0:
                    fee = custody_daily * steps * float(np.nansum(q * self._px_val[t - 1]))
                    payable += fee
                    cost_today += fee
                    breakdown[k, 3] += fee
                if line_fee_daily > 0:
                    fee = line_fee_daily * steps * int(np.count_nonzero(q > 0))
                    payable += fee
                    cost_today += fee
                    breakdown[k, 4] += fee
            pay_fees()

            # 4b. jour de division ou d'attribution : la position doit rester un nombre entier
            # de titres réels ; une fraction (attribution 3:2 sur un nombre impair…) est un
            # « rompu », vendu au dernier cours connu et crédité en cash (hypothèse simple).
            if k > 0 and q.any():
                f_row = self._af[t]
                for jr in np.flatnonzero((q > 0) & self._split_day[t]):
                    raw_units = float(q[jr] * f_row[jr])
                    whole = math.floor(raw_units + 1e-6)
                    frac = raw_units - whole
                    if frac > 1e-6:
                        px_prev = float(self._px_val[t - 1, jr])
                        value = frac / float(f_row[jr]) * px_prev if math.isfinite(px_prev) else 0.0
                        q[jr] = whole / float(f_row[jr])
                        cash += value
                        events.append((day, self.symbols[jr], "rompus_credites", -1, -1, frac))

            # 4c. report maximal (§7.1.1) contrôlé AVANT toute tentative : après un trou de BOC,
            # un ordre plus vieux que ``max_order_age`` séances n'est jamais exécuté.
            if pending and self.max_order_age is not None:
                for j in list(pending):
                    od = pending[j]
                    if sess[t] - sess[od.decision_pos] > self.max_order_age:
                        od.status = "expired"
                        events.append((day, self.symbols[j], "expiration_report_maximal", od.oid, -1, od.remaining))
                        del pending[j]

            # 5. jour ex / jour de division : annulation et ressaisie le jour même
            if pending and self.cancel_on_corporate_events:
                for j, od in list(pending.items()):
                    if od.entered_pos >= t:
                        continue  # ordre saisi le jour même : non concerné
                    is_ex = bool(self._ex_day[t, j])
                    if not (is_ex or self._split_day[t, j]):
                        continue
                    od.status = "cancelled_ex" if is_ex else "cancelled_split"
                    new = _Order(
                        oid=len(orders),
                        j=j,
                        decision_pos=od.decision_pos,
                        qty=od.remaining,
                        remaining=od.remaining,
                        ref_price=od.ref_price,
                        entered_pos=t,
                        parent=od.oid,
                        root=od.root,
                    )
                    orders.append(new)
                    pending[j] = new
                    label = "annulation_ressaisie_jour_ex" if is_ex else "annulation_ressaisie_division"
                    events.append((day, self.symbols[j], label, od.oid, new.oid, float(od.remaining)))

            # 6. exécution des ordres en attente
            if pending:
                px = self._px_exec[t]
                vol = self._volume[t]
                hs = self._hs[t]
                f_t = self._af[t]
                lag = int(self._lag_rows[t])
                # Unités brutes du jour : titres réels entiers (quotité ``lot_size``).
                with np.errstate(divide="ignore", invalid="ignore"):
                    px_raw = px / f_t
                vol_raw = vol * f_t
                cap = self._round_lot(np.floor(part_max * vol_raw + 1e-9))
                # 6a. ventes
                for j, od in list(pending.items()):
                    if od.remaining >= 0:
                        continue
                    fj = float(f_t[j])
                    want = min(self._raw_count(od.remaining, fj), self._raw_count(q[j], fj))
                    if want <= 0:
                        od.remaining = 0.0
                        continue
                    why = self._block_reason(t, j, "sell")
                    if why is not None:
                        blocked.append((day, self.symbols[j], "sell", want / fj, why))
                        continue
                    n_raw = int(min(want, cap[j]))
                    if n_raw < want:
                        blocked.append((day, self.symbols[j], "sell", (want - n_raw) / fj, "volume_cap"))
                    if n_raw <= 0:
                        continue
                    n = n_raw / fj  # titres ajustés
                    amount = n_raw * float(px_raw[j])
                    part = n_raw / float(vol_raw[j])
                    comm, spr, imp = (float(x) for x in _cost_parts(amount, part, costs, hs[j]))
                    c_tot = comm + spr + imp
                    proceeds = amount - c_tot
                    gain = proceeds - avg_cost[j] * n
                    tax = cgt * max(gain, 0.0)
                    net = proceeds - tax
                    if lag == 0 or net <= 0.0:
                        if cash + net < 0.0:
                            # vente « de poussière » dont les frais minimaux excèdent
                            # le produit et que le cash ne peut couvrir : reportée
                            blocked.append((day, self.symbols[j], "sell", n, "cash"))
                            continue
                        cash += net
                    else:
                        sale_recv.append((int(sess[t]) + lag, net))
                    tax_today += tax
                    cost_today += c_tot
                    breakdown[k, 0] += comm
                    breakdown[k, 1] += spr
                    breakdown[k, 2] += imp
                    value_today += amount
                    q[j] -= n
                    if abs(q[j] * fj) < 1e-6:
                        q[j] = 0.0
                        avg_cost[j] = 0.0
                    od.remaining += n
                    if abs(od.remaining * fj) < 1e-6:
                        od.remaining = 0.0
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
                            imp,
                            float(hs[j]),
                            spr,
                            comm,
                            -n_raw,
                        )
                    )
                    if od.first_fill is None:
                        od.first_fill = day
                    od.last_fill = day
                pay_fees()
                # 6b. achats (cash réglé uniquement)
                buy_js: list[int] = []
                desired: list[int] = []
                for j, od in pending.items():
                    if od.remaining <= 0:
                        continue
                    fj = float(f_t[j])
                    want = self._raw_count(od.remaining, fj)
                    want = int(self._round_lot(np.array([float(want)]))[0])
                    if want <= 0:
                        od.remaining = 0.0  # reliquat inférieur à un titre réel (rompu)
                        continue
                    why = self._block_reason(t, j, "buy")
                    if why is not None:
                        blocked.append((day, self.symbols[j], "buy", want / fj, why))
                        continue
                    n_raw = int(min(want, cap[j]))
                    if n_raw < want:
                        blocked.append((day, self.symbols[j], "buy", (want - n_raw) / fj, "volume_cap"))
                    if n_raw > 0:
                        buy_js.append(j)
                        desired.append(n_raw)
                if buy_js:
                    js = np.asarray(buy_js, dtype=np.int64)
                    want_q = np.asarray(desired, dtype=np.int64)
                    got = self._affordable(want_q, px_raw[js], vol_raw[js], max(cash, 0.0), hs[js])
                    for j_raw, w_n, n_got in zip(js, want_q, got, strict=True):
                        j = int(j_raw)
                        fj = float(f_t[j])
                        n_raw = int(n_got)
                        if n_raw < w_n:
                            blocked.append((day, self.symbols[j], "buy", (int(w_n) - n_raw) / fj, "cash"))
                        if n_raw <= 0:
                            continue
                        n = n_raw / fj  # titres ajustés
                        amount = n_raw * float(px_raw[j])
                        part = n_raw / float(vol_raw[j])
                        comm, spr, imp = (float(x) for x in _cost_parts(amount, part, costs, hs[j]))
                        c_tot = comm + spr + imp
                        cash -= amount + c_tot
                        cost_today += c_tot
                        breakdown[k, 0] += comm
                        breakdown[k, 1] += spr
                        breakdown[k, 2] += imp
                        value_today += amount
                        avg_cost[j] = (avg_cost[j] * q[j] + amount + c_tot) / (q[j] + n)
                        q[j] += n
                        od = pending[j]
                        od.remaining -= n
                        if abs(od.remaining * fj) < 1e-6:
                            od.remaining = 0.0
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
                                imp,
                                float(hs[j]),
                                spr,
                                comm,
                                n_raw,
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
                # 6c. ordres terminés / expirés (report maximal en séances)
                for j in list(pending):
                    od = pending[j]
                    if od.remaining == 0:
                        od.status = "filled"
                        del pending[j]
                    elif not ex.carry_unfilled or (
                        self.max_order_age is not None and sess[t] - sess[od.decision_pos] >= self.max_order_age
                    ):
                        od.status = "expired"
                        del pending[j]

            # 7. valorisation à la clôture
            px_val = self._px_val[t]
            held = q != 0
            stock_value = float(np.sum(q[held] * np.nan_to_num(px_val[held]))) if held.any() else 0.0
            recv = float(sum(a for _, a in sale_recv)) + float(sum(a for _, a in div_recv))
            nav = cash - payable + recv + stock_value
            equity[k] = nav
            cash_hist[k] = cash
            recv_hist[k] = recv
            pay_hist[k] = payable
            pos_hist[k] = q
            costs_daily[k] = cost_today
            tax_daily[k] = tax_today
            traded_value[k] = value_today / (2.0 * prev_nav) if prev_nav > 0 else 0.0
            # Positions bloquées pour le risque (§7.1.7) : suspensions ET titres radiés (plus
            # aucune ligne au BOC), suivies pour la décote de 10 %.
            susp = held & (self._suspended[t] | self._delisted[t])
            if susp.any():
                susp_hist[k] = float(np.sum(q[susp] * np.nan_to_num(px_val[susp])))
            for jd in np.flatnonzero(held & self._delisted[t]):
                if int(jd) not in delisted_seen:
                    delisted_seen.add(int(jd))
                    delisted_log.append({"symbol": str(self.symbols[jd]), "date": day, "qty": float(q[jd]),
                                         "value": float(q[jd] * np.nan_to_num(px_val[jd]))})
                    events.append((day, self.symbols[jd], "radiation_position_bloquee", -1, -1, float(q[jd])))

            # 8. décision
            if t in reb_pos:
                used_reb.append(day)
                self._decide(fn, t, nav, cash, q, pending, orders, warned, receivables=recv)
            prev_nav = nav

        for od in pending.values():
            od.status = "end_of_backtest"
        if delisted_log:
            warnings.warn(
                f"{len(delisted_log)} position(s) détenue(s) au moment d'une radiation (plus aucune cotation) : "
                f"p. ex. {delisted_log[0]['symbol']} le {pd.Timestamp(delisted_log[0]['date']).date()} ; "
                "position bloquée, suivie dans suspended_value"
                + (f", valorisation décotée de {self.delisted_writedown:.0%}" if self.delisted_writedown > 0 else
                   ", valorisée au dernier cours (hypothèse ; delisted_writedown pour un stress)"),
                stacklevel=2,
            )
        self._delisted_log = delisted_log
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
            paid=paid_daily,
            receivables=recv_hist,
            breakdown=breakdown,
            events=events,
            suspended=susp_hist,
            payables=pay_hist,
            dividends_boc=div_boc_daily,
            dividend_events=div_events,
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
        *,
        receivables: float = 0.0,
    ) -> None:
        """Appelle la stratégie sur la vue tronquée et remplace les ordres."""
        asof = self.dates[t]
        px = self._px_val[t]
        val = np.where(np.isfinite(px), q * np.nan_to_num(px), 0.0)
        cur_w = val / nav if nav > 0 else np.zeros_like(val)
        f_view = pd.Series(self._af[t], index=self.symbols)
        # Titres réels du jour ``asof`` (entiers) ; identiques aux titres ajustés sans division.
        positions = pd.Series(np.round(q * self._af[t]).astype(np.int64), index=self.symbols, name="positions")
        pend_raw = {self.symbols[j]: float(od.remaining) * float(self._af[t, j]) for j, od in pending.items()}
        pend = pd.Series(pend_raw, dtype=float, name="pending")
        if len(pend) and np.allclose(pend.to_numpy(), np.round(pend.to_numpy()), atol=1e-6):
            pend = pend.round().astype("int64")
        elif not len(pend):
            pend = pend.astype("int64")
        rescale = None
        if self._rescale_view:
            # Vue « point-in-time » : cours, facteurs et quantités exprimés en
            # unités du jour de décision (f_s / f_asof ne dépend que des
            # divisions intervenues dans ]s, asof]) ; sans cela, le cours
            # ajusté à rebours révélerait les divisions futures. ``close_adj`` et
            # ``split_factor`` (panels de la stratégie, ``strategy.build_panels``)
            # sont remis à l'échelle de la même façon : ``split_factor`` vaut 1 en
            # ``asof`` et ``close_adj`` y égale le cours publié.
            rescale = {"close": 1.0 / f_view, "adj_factor": 1.0 / f_view, "close_adj": 1.0 / f_view,
                       "split_factor": f_view}
        view = PanelView(
            self._panels,
            asof,
            nav=nav,
            cash=cash,
            positions=positions,
            weights=pd.Series(cur_w, index=self.symbols, name="weights"),
            pending=pend,
            rescale=rescale,
            receivables=receivables,
        )
        w = self._parse_weights(fn(asof, view), warned)
        if w is None:
            return
        f_now = self._af[t]
        ok = np.isfinite(px) & (px > 0)
        # Cible en titres RÉELS du jour (quotité ``lot_size``), puis en titres ajustés :
        # q*_brut = ⌊w · NAV / (P̃ / f_t) / lot⌋ · lot et q*_ajusté = q*_brut / f_t. La
        # granularité ne dépend donc d'aucune division postérieure à la décision.
        target_raw = np.zeros(len(w), dtype=np.int64)
        if nav > 0:
            raw = np.where(ok, w * nav / np.where(ok, px / f_now, 1.0), 0.0)
            target_raw = self._round_lot(raw)
        held_raw = np.round(q * f_now).astype(np.int64)
        delta_raw = target_raw - held_raw
        if self.constraints is not None and self.constraints.no_trade_band > 0:
            band = float(self.constraints.no_trade_band)
            # §6 : pas d'ordre si |w_cible − w_actuel| < bande, SAUF pour une entrée
            # (titre non détenu) ou une sortie complète.
            full_exit = (w == 0) & (held_raw > 0)
            entry = (w > 0) & (held_raw == 0)
            small = (np.abs(w - cur_w) < band) & ~full_exit & ~entry
            delta_raw = np.where(small, 0, delta_raw)
        for od in pending.values():
            od.status = "replaced"
        pending.clear()
        for j in np.flatnonzero(delta_raw):
            oid = len(orders)
            d_adj = float(delta_raw[j]) / float(f_now[j])
            od = _Order(
                oid=oid,
                j=int(j),
                decision_pos=t,
                qty=d_adj,
                remaining=d_adj,
                ref_price=float(px[j]) if np.isfinite(px[j]) else math.nan,
                entered_pos=t + 1,
                root=oid,
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
        *,
        paid: np.ndarray | None = None,
        receivables: np.ndarray | None = None,
        breakdown: np.ndarray | None = None,
        events: list[tuple[Any, ...]] | None = None,
        suspended: np.ndarray | None = None,
        payables: np.ndarray | None = None,
        dividends_boc: np.ndarray | None = None,
        dividend_events: list[tuple[Any, ...]] | None = None,
    ) -> BacktestResult:
        idx = pd.DatetimeIndex(sim_dates, name="date")
        n = len(idx)
        eq = pd.Series(equity, index=idx, name="equity")
        prev = np.concatenate([[self.capital], equity[:-1]])
        r_arr = np.where(prev > 0, equity / np.where(prev > 0, prev, 1.0) - 1.0, np.nan)
        nav_meta: dict[str, Any] = {"nav_non_positive_from": None, "n_returns_excluded": 0}
        bad_nav = np.flatnonzero(equity <= 0)
        if bad_nav.size:
            # Valeur liquidative ≤ 0 (frais fixes supérieurs au capital…) : la série de
            # rendements s'arrête (perte totale de −100 % à la séance de franchissement,
            # NaN ensuite) au lieu de rendements absurdes (−1 295 %, puis signes inversés).
            k0 = int(bad_nav[0])
            r_arr[k0] = -1.0
            r_arr[k0 + 1 :] = np.nan
            nav_meta = {"nav_non_positive_from": idx[k0], "n_returns_excluded": int(n - k0 - 1)}
            warnings.warn(
                f"valeur liquidative ≤ 0 à partir du {idx[k0].date()} ({equity[k0]:,.0f} FCFA) : rendements "
                f"arrêtés (−100 % ce jour-là, {n - k0 - 1} séance(s) exclue(s)) ; capital trop faible pour les "
                "frais fixes ?",
                stacklevel=3,
            )
        rets = pd.Series(r_arr, index=idx, name="returns")
        if np.allclose(pos, np.round(pos), atol=1e-9):
            pos = np.round(pos).astype(np.int64)
        positions = pd.DataFrame(pos, index=idx, columns=self.symbols)
        px_val = np.nan_to_num(self._px_val[i0 : i0 + n])
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
            "half_spread",
            "spread_cost",
            "commission",
            "raw_qty",
        ]
        tr = pd.DataFrame(trades, columns=trade_cols)
        if len(tr):
            # ``qty`` en titres ajustés ; ``raw_qty`` en titres réels du jour (entier).
            tr["raw_qty"] = tr["raw_qty"].astype(np.int64)
            qv = tr["qty"].to_numpy(dtype=float)
            if np.allclose(qv, np.round(qv), atol=1e-9):
                tr["qty"] = np.round(qv).astype(np.int64)
        bl = pd.DataFrame(blocked, columns=["date", "symbol", "side", "qty", "reason"])
        if len(bl):
            bq = bl["qty"].to_numpy(dtype=float)
            if np.allclose(bq, np.round(bq), atol=1e-9):
                bl["qty"] = np.round(bq).astype(np.int64)
        od_cols = [
            "decision_date",
            "symbol",
            "qty",
            "filled",
            "ref_price",
            "status",
            "first_fill",
            "last_fill",
            "oid",
            "parent",
            "entered",
        ]
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
                    "oid": o.oid,
                    "parent": o.parent,
                    "entered": self.dates[o.entered_pos] if 0 <= o.entered_pos < len(self.dates) else pd.NaT,
                }
                for o in orders
            ],
            columns=od_cols,
        )
        for col in ("qty", "filled"):
            if len(od):
                v = od[col].to_numpy(dtype=float)
                if np.allclose(v, np.round(v), atol=1e-9):
                    od[col] = np.round(v).astype(np.int64)
        if len(od):
            # taux d'exécution : quantité demandée par l'ordre racine, exécutions
            # cumulées sur toute la chaîne (ressaisies du jour ex comprises)
            roots = [o for o in orders if o.parent is None]
            asked = float(sum(abs(o.qty) * (o.ref_price if math.isfinite(o.ref_price) else 0.0) for o in roots))
            done = float(
                sum(abs(o.qty - o.remaining) * (o.ref_price if math.isfinite(o.ref_price) else 0.0) for o in orders)
            )
            fill_rate = done / asked if asked > 0 else math.nan
        else:
            fill_rate = math.nan
        to_daily = pd.Series(turnover_daily, index=idx, name="turnover")
        bd = np.zeros((n, 5)) if breakdown is None else breakdown
        cost_breakdown = pd.DataFrame(
            bd, index=idx, columns=["commission", "spread", "impact", "custody", "account_fees"]
        )
        ev = pd.DataFrame(events or [], columns=["date", "symbol", "event", "oid", "new_oid", "qty"])
        div_boc = np.asarray(div_daily, dtype=float) if dividends_boc is None else np.asarray(dividends_boc, dtype=float)
        div_ev = pd.DataFrame(dividend_events or [], columns=list(DIVIDEND_EVENT_COLUMNS))
        gap_total = float(np.sum(div_daily) - np.sum(div_boc))
        return BacktestResult(
            equity=eq,
            returns=rets,
            weights=weights,
            trades=tr,
            costs=pd.Series(np.cumsum(costs_daily), index=idx, name="costs"),
            turnover=float(to_daily.mean() * self.periods_per_year) if n else math.nan,
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
                "settlement": self.settlement,
                "max_order_age_sessions": self.max_order_age,
                "dividend_payment_lag": self.dividend_payment_lag,
                "band_rule": self.band_rule,
                "half_spread_measured_share": self.half_spread_measured_share,
                "suspended_risk_haircut": self.suspended_risk_haircut,
                "n_country_shock_cells": int(self._shock.sum()),
                "country_shock_recovery": self.country_shock_recovery,
                "delisted_positions": list(getattr(self, "_delisted_log", [])),
                "delisted_writedown": self.delisted_writedown,
                "nav_non_positive_from": nav_meta["nav_non_positive_from"],
                "n_returns_excluded": nav_meta["n_returns_excluded"],
                "quantity_units": "qty et positions en titres ajustés ; raw_qty en titres réels du jour (entiers)",
                "dividend_amount_credited": "montant corrigé (meilleure estimation du versement réel, additif v1.1 D6)",
                "dividend_boc_line_available": bool(getattr(self, "has_dividend_boc", False)),
                "dividend_gap_vs_boc": gap_total,
                "n_dividend_events_gap": int((div_ev["gap"].abs() > 1e-9).sum()) if len(div_ev) else 0,
                "avertissement": "Performance simulée (hypothèses de coûts et d'exécution) : aucun gain n'est garanti.",
            },
            dividends_paid=pd.Series(np.zeros(n) if paid is None else paid, index=idx, name="dividends_paid"),
            receivables=pd.Series(np.zeros(n) if receivables is None else receivables, index=idx, name="receivables"),
            cost_breakdown=cost_breakdown,
            events=ev,
            suspended_value=pd.Series(
                np.zeros(n) if suspended is None else suspended, index=idx, name="suspended_value"
            ),
            payables=pd.Series(np.zeros(n) if payables is None else payables, index=idx, name="payables"),
            dividends_boc=pd.Series(div_boc, index=idx, name="dividends_boc"),
            dividend_events=div_ev,
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


def _payment_date_panel(table: pd.DataFrame, dates: pd.DatetimeIndex, symbols: pd.Index) -> pd.DataFrame:
    """Panel large des dates de paiement, à la ligne de la date ex (même placement que :func:`_dividend_panel`).

    Plusieurs événements le même jour : date de paiement la plus tardive.
    Une date de paiement manquante reste ``NaT`` (le moteur applique alors
    le délai par défaut).
    """
    out = pd.DataFrame(pd.NaT, index=dates, columns=symbols, dtype="datetime64[ns]")
    if not len(table) or not len(dates):
        return out
    ev = table.loc[:, ["symbol", "ex_date", "amount", "payment_date"]].copy()
    ev["ex_date"] = pd.to_datetime(ev["ex_date"], errors="coerce")
    ev["payment_date"] = pd.to_datetime(ev["payment_date"], errors="coerce")
    ev["amount"] = pd.to_numeric(ev["amount"], errors="coerce")
    ok = ev["symbol"].isin(symbols) & ev["ex_date"].notna() & ev["payment_date"].notna() & (ev["amount"] > 0)
    ev = ev[ok & (ev["ex_date"] >= dates[0]) & (ev["ex_date"] <= dates[-1])]
    for rec in ev.itertuples(index=False):
        row = dates[int(dates.searchsorted(pd.Timestamp(rec.ex_date), side="left"))]
        cur = out.at[row, rec.symbol]
        pay = pd.Timestamp(rec.payment_date)
        out.at[row, rec.symbol] = pay if pd.isna(cur) else max(pd.Timestamp(cur), pay)
    return out


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
    order_book: pd.DataFrame | None = None,
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
    order_book
        Table ``order_book.parquet`` (``date, symbol, bid, ask``) : panels
        ``bid`` et ``ask`` (unités brutes) pour le demi-spread propre au
        titre (:func:`quoted_half_spread`).

    Returns
    -------
    dict
        ``close`` (ajusté), ``adj_factor`` (si ajusté), ``volume, value,
        status, prev_close, ref_price, change_pct, open, net_yield_pct, per,
        last_div_net, last_div_date, session_no`` (bruts, si présents),
        ``dividend_net``, ``dividend_payment_date`` (si la table de
        dividendes porte ``payment_date``), ``bid`` / ``ask`` (si
        ``order_book``), ``country`` (``Series``) et ``sector`` (``Series``).

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
        "session_no",
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
        if "amount_first" in div_table.columns:
            # Additif v1.1, D6 : flux = montant corrigé (``amount``) ; ligne « (d) » du BOC
            # (``amount_first``, montant connu des signaux) gardée pour publier l'écart.
            first = pd.to_numeric(div_table["amount_first"], errors="coerce")
            boc_table = div_table.assign(amount=first.fillna(pd.to_numeric(div_table["amount"], errors="coerce")))
            panels["dividend_net_boc"] = _dividend_panel(boc_table, dates, symbols)
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
    if (
        dividend_net is None
        and div_table is not None
        and "payment_date" in div_table.columns
        and (dividends is not None or (infer_dividends and dividend_method == "detect"))
    ):
        panels["dividend_payment_date"] = _payment_date_panel(div_table, dates, symbols)
    if order_book is not None:
        need_ob = {"date", "symbol", "bid", "ask"}
        if not need_ob.issubset(order_book.columns):
            raise KeyError(f"order_book : colonnes manquantes {sorted(need_ob - set(order_book.columns))}")
        ob = order_book.loc[:, ["date", "symbol", "bid", "ask"]].copy()
        ob["date"] = pd.to_datetime(ob["date"])
        ob = ob.drop_duplicates(["date", "symbol"], keep="last")
        for side in ("bid", "ask"):
            panels[side] = (
                ob.pivot(index="date", columns="symbol", values=side)
                .reindex(index=dates, columns=symbols)
                .astype(float)
            )
    from brvm_alpha.reference import countries

    panels["country"] = countries(list(symbols))
    if "sector" in df.columns:
        panels["sector"] = df.sort_values("date").groupby("symbol")["sector"].last().reindex(list(symbols))
    return panels
