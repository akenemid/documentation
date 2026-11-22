"""Bibliothèque de caractéristiques (« features ») date × symbole pour BRVM Alpha.

Chaque fonction publique prend un dictionnaire de panels **larges** (une
colonne par symbole, index ``DatetimeIndex`` trié par séance) et renvoie un
``DataFrame`` date × symbole. Les clés reconnues sont celles du contrat
(``docs/ARCHITECTURE.md``) :

``close_adj``      cours de clôture ajusté des splits (renseigné même sans échange) ;
``tr_index``       indice de rendement total par titre (dividendes nets réinvestis) ;
``volume``         titres échangés (0 si non échangé) ;
``value``          valeur échangée en FCFA ;
``status``         ``traded`` / ``not_traded`` / ``suspended`` ;
``net_yield_pct``  rendement net publié par le BOC, en % ;
``per``            PER publié par le BOC ;
``last_div_net``   dernier dividende net payé (FCFA) ;
``last_div_date``  date de paiement du dernier dividende ;
``ref_price``      cours de référence (brut, non ajusté des splits) ;
``change_pct``     (facultatif) variation du jour publiée par le BOC, en %.
``split_factor``   (facultatif) facteur de division cumulé **dans la convention de
                   ``data/store.py``** : ``close_adj = close / split_factor``
                   (pivot large de la colonne ``split_factor`` de
                   ``store.adjusted_table``) ;
``close``          (facultatif) cours de clôture **brut** ; avec ``close_adj``, il
                   donne le facteur exact ``split_factor = close / close_adj``.

Principes
---------
* **Aucun biais d'anticipation** : la valeur en ``t`` n'utilise que des lignes
  d'index ``<= t``. Toutes les fenêtres sont des fenêtres glissantes « vers le
  passé » exprimées en **séances** (lignes du panel), jamais centrées. Les
  quelques calculs qui ont besoin d'une valeur future (avances du bêta de
  Dimson) sont décalés d'autant de séances pour rester causaux.
* **Titres non échangés** : à la BRVM une large part des séances-titres n'a pas
  d'échange ; le cours publié est alors un cours périmé. On distingue donc les
  rendements « calendrier » (séance à séance, nuls quand le cours est périmé)
  et les rendements « d'échange à échange » (*trade-to-trade*, Maynes &
  Rumsey, 1993), définis uniquement les séances échangées.
* **NaN** : un titre non coté (cours absent) ou sans historique suffisant
  reçoit ``NaN`` ; les statistiques glissantes exigent un nombre minimal
  d'observations valides (``min_obs``).
* Les ratios de cours ajustés « vers l'arrière » (splits) sont invariants aux
  ajustements futurs : un momentum ou une distance au plus haut calculés sur
  ``close_adj`` n'introduisent donc pas d'information future.
* **Splits et grandeurs par action** : le ``volume`` (nombre de titres) et
  ``last_div_net`` (FCFA par action) du BOC sont **bruts**. Après une division
  k:1, ils sont multipliés (resp. divisés) par ``k`` sans changement
  économique. Les caractéristiques qui les comparent dans le temps
  (:func:`turnover_proxy`, :func:`turnover`, :func:`dividend_growth`) les
  ramènent à la base de titres de ``close_adj`` à l'aide de ``split_factor``
  (convention du store : ``brut / split_factor`` pour un prix ou un dividende,
  ``brut × split_factor`` pour un nombre de titres). Le facteur « vers
  l'arrière » dépend des splits futurs, mais seulement par une constante
  multiplicative commune à toutes les dates antérieures, qui s'annule dans
  les ratios calculés : aucune anticipation.
* Annualisation : 252 séances.

Signaux de la stratégie v1
--------------------------
La dernière section du module implémente les signaux de
``docs/SPECIFICATION_STRATEGIE.md`` (§3.1-§3.3, §11) : :func:`ep_signal` (surcharges
de BPA point-in-time), :func:`dy_signal` (repli v1 : garde-fou de 15 mois, plafond
de 15 % avec drapeau, dividendes exceptionnels exclus, absences annoncées),
:func:`mom6_1` en séances, :func:`lowvol`, :func:`quality_proxy`, les modulateurs du
momentum (:func:`vol_scaling`, :func:`crash_filter`) et les signaux de recherche
(:data:`RESEARCH_SIGNALS_V1`, poids nul). Ce sont des caractéristiques, pas des
résultats : aucune performance n'y est mesurée et rien n'y garantit un gain.

Références
----------
* Amihud, Y. (2002). Illiquidity and stock returns: cross-section and
  time-series effects. *Journal of Financial Markets*, 5(1), 31-56.
* Asness, C., Moskowitz, T. & Pedersen, L. (2013). Value and Momentum
  Everywhere. *Journal of Finance*, 68(3), 929-985.
* Barroso, P. & Santa-Clara, P. (2015). Momentum has its moments. *Journal of
  Financial Economics*, 116(1), 111-120.
* Blitz, D., Pang, J. & van Vliet, P. (2013). The volatility effect in emerging
  markets. *Emerging Markets Review*, 16, 31-45.
* Daniel, K. & Moskowitz, T. (2016). Momentum crashes. *Journal of Financial
  Economics*, 122(2), 221-247.
* Ang, A., Hodrick, R., Xing, Y. & Zhang, X. (2006). The Cross-Section of
  Volatility and Expected Returns. *Journal of Finance*, 61(1), 259-299.
* Basu, S. (1977). Investment Performance of Common Stocks in Relation to
  Their Price-Earnings Ratios. *Journal of Finance*, 32(3), 663-682.
* Bekaert, G., Harvey, C. & Lundblad, C. (2007). Liquidity and Expected
  Returns: Lessons from Emerging Markets. *Review of Financial Studies*,
  20(6), 1783-1831.
* Blitz, D. & van Vliet, P. (2007). The Volatility Effect. *Journal of
  Portfolio Management*, 34(1), 102-113.
* Datar, V., Naik, N. & Radcliffe, R. (1998). Liquidity and stock returns:
  An alternative test. *Journal of Financial Markets*, 1(2), 203-219.
* Dimson, E. (1979). Risk measurement when shares are subject to infrequent
  trading. *Journal of Financial Economics*, 7(2), 197-226.
* Estrada, J. (2007). Mean-semivariance behavior: Downside risk and capital
  asset pricing. *International Review of Economics & Finance*, 16(2), 169-185.
* George, T. & Hwang, C.-Y. (2004). The 52-Week High and Momentum Investing.
  *Journal of Finance*, 59(5), 2145-2176.
* Gervais, S., Kaniel, R. & Mingelgrin, D. (2001). The High-Volume Return
  Premium. *Journal of Finance*, 56(3), 877-919.
* Hartzmark, S. & Solomon, D. (2013). The dividend month premium. *Journal of
  Financial Economics*, 109(3), 640-660.
* Heston, S. & Sadka, R. (2008). Seasonality in the cross-section of stock
  returns. *Journal of Financial Economics*, 87(2), 418-445.
* Jegadeesh, N. (1990). Evidence of Predictable Behavior of Security Returns.
  *Journal of Finance*, 45(3), 881-898.
* Jegadeesh, N. & Titman, S. (1993). Returns to Buying Winners and Selling
  Losers. *Journal of Finance*, 48(1), 65-91.
* Lehmann, B. (1990). Fads, Martingales, and Market Efficiency. *Quarterly
  Journal of Economics*, 105(1), 1-28.
* Lesmond, D., Ogden, J. & Trzcinka, C. (1999). A New Estimate of Transaction
  Costs. *Review of Financial Studies*, 12(5), 1113-1141.
* Lintner, J. (1956). Distribution of Incomes of Corporations Among Dividends,
  Retained Earnings, and Taxes. *American Economic Review*, 46(2), 97-113.
* Litzenberger, R. & Ramaswamy, K. (1979). The effect of personal taxes and
  dividends on capital asset prices. *Journal of Financial Economics*, 7(2),
  163-195.
* Maynes, E. & Rumsey, J. (1993). Conducting event studies with thinly traded
  stocks. *Journal of Banking & Finance*, 17(1), 145-157.
* Michaely, R., Thaler, R. & Womack, K. (1995). Price Reactions to Dividend
  Initiations and Omissions: Overreaction or Drift? *Journal of Finance*,
  50(2), 573-608.
* Scholes, M. & Williams, J. (1977). Estimating betas from nonsynchronous
  data. *Journal of Financial Economics*, 5(3), 309-327.
* Sortino, F. & Price, L. (1994). Performance Measurement in a Downside Risk
  Framework. *Journal of Investing*, 3(3), 59-64.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal, TypeAlias

import numpy as np
import pandas as pd

from brvm_alpha.config import ExecutionModel

__all__ = [
    "ANNOUNCED_NO_DIVIDEND_V1",
    "EPS_OVERRIDES_V1",
    "EXCEPTIONAL_DIVIDENDS_V1",
    "EXCLUDED_STAT_WINDOWS",
    "MOMENTUM_PRESETS",
    "RESEARCH_SIGNALS_V1",
    "SIGNAL_PARAMS_V1",
    "TRADING_DAYS",
    "V1_SIGNALS",
    "DividendAbsence",
    "EpsOverride",
    "ExceptionalDividend",
    "Panels",
    "adjusted_volume",
    "amihud_illiquidity",
    "amihud_signal",
    "average_daily_value",
    "beta_dimson",
    "compute_features",
    "crash_filter",
    "days_since_dividend",
    "distance_to_high",
    "dividend_growth",
    "dividend_stability",
    "dividend_years",
    "dividend_yield",
    "downside_vol",
    "dy_signal",
    "dy_signal_details",
    "earnings_yield",
    "ep_signal",
    "limit_hits",
    "listed_mask",
    "lowvol",
    "median_value_traded",
    "mom3_1",
    "mom6_0",
    "mom6_1",
    "mom12_1",
    "mom12_7",
    "mom_sessions",
    "momentum",
    "momentum_multiplier",
    "momentum_preset",
    "momentum_spread_returns",
    "multi_session_mask",
    "panels_for_signals",
    "past_return",
    "per_v1",
    "quality_proxy",
    "returns",
    "seasonality",
    "short_term_reversal",
    "signal_blocks_v1",
    "split_factor_panel",
    "traded_mask",
    "turnover",
    "turnover_proxy",
    "WINDOW_BASES",
    "DEFAULT_WINDOW_BASIS_V11",
    "FILTER_MIN_OBS_FLOOR",
    "MAX_BOUND_STALE_SESSIONS",
    "SIGNAL_MIN_OBS_FLOOR",
    "min_obs_thresholds",
    "missing_sessions_in_window",
    "on_session_grid",
    "prorata_min_obs",
    "session_numbers",
    "valid_return_mask",
    "vol_scaling",
    "volatility",
    "zero_return_fraction",
    "zero_volume_fraction",
]

#: Dictionnaire de panels larges (clé -> DataFrame date × symbole).
Panels: TypeAlias = Mapping[str, pd.DataFrame]

#: Nombre de séances par an (convention de la plate-forme).
TRADING_DAYS: int = 252

#: Paramétrages usuels du momentum, en séances : ``nom -> (lookback, skip)``.
#: « 12-1 » = rendement des 12 derniers mois en omettant le dernier mois
#: (Jegadeesh & Titman, 1993 ; Asness, Moskowitz & Pedersen, 2013).
MOMENTUM_PRESETS: dict[str, tuple[int, int]] = {
    "12-1": (252, 21),
    "6-1": (126, 21),
    "3-0": (63, 0),
    "1-0": (21, 0),
}

ReturnKind: TypeAlias = Literal["simple", "log"]
ReturnBasis: TypeAlias = Literal["calendar", "traded"]

_TINY = 1e-300


# ---------------------------------------------------------------------------
# Accès aux panels et masques
# ---------------------------------------------------------------------------


def _check_index(df: pd.DataFrame, key: str) -> None:
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"le panel {key!r} doit être un DataFrame large (date × symbole)")
    if not isinstance(df.index, pd.DatetimeIndex):
        raise TypeError(f"le panel {key!r} doit être indexé par un DatetimeIndex")
    if not df.index.is_monotonic_increasing:
        raise ValueError(f"l'index du panel {key!r} doit être trié par date croissante")
    if df.index.has_duplicates:
        raise ValueError(f"l'index du panel {key!r} contient des dates dupliquées")


def _raw(panels: Panels, key: str) -> pd.DataFrame:
    """Renvoie le panel ``key`` (validé) ou lève ``KeyError`` explicite."""
    if key not in panels or panels[key] is None:
        raise KeyError(f"panel {key!r} requis (clés disponibles : {sorted(panels)})")
    df = panels[key]
    _check_index(df, key)
    return df


def _numeric(panels: Panels, key: str, like: pd.DataFrame | None = None) -> pd.DataFrame:
    """Panel numérique (float), ±inf remplacés par NaN, aligné sur ``like``."""
    df = _raw(panels, key)
    if like is not None:
        df = df.reindex(index=like.index, columns=like.columns)
    out = df.apply(pd.to_numeric, errors="coerce").astype(float)
    return out.where(np.isfinite(out))


def _price(panels: Panels, key: str) -> pd.DataFrame:
    """Panel de prix strictement positifs (les valeurs ``<= 0`` deviennent NaN)."""
    p = _numeric(panels, key)
    return p.where(p > 0)


def _reference(panels: Panels, *keys: str) -> pd.DataFrame:
    """Premier panel disponible parmi ``keys`` (sert de grille date × symbole)."""
    for k in keys:
        if k in panels and panels[k] is not None:
            df = panels[k]
            _check_index(df, k)
            return df
    raise KeyError(f"aucun des panels {keys} n'est disponible (clés : {sorted(panels)})")


def traded_mask(panels: Panels, like: pd.DataFrame | None = None) -> pd.DataFrame:
    """Masque booléen des séances effectivement échangées.

    Règle : ``status == "traded"`` lorsque le statut est renseigné ; à défaut
    (statut manquant ou panel ``status`` absent), ``volume > 0``. Une séance
    suspendue ou sans statut ni volume est considérée comme non échangée.

    Parameters
    ----------
    panels
        Panels larges ; ``status`` et/ou ``volume`` requis.
    like
        Grille cible (index et colonnes) ; par défaut celle du panel source.
    """
    mask: pd.DataFrame | None = None
    if "status" in panels and panels["status"] is not None:
        st = _raw(panels, "status")
        if like is not None:
            st = st.reindex(index=like.index, columns=like.columns)
        known = st.notna()
        mask = st.eq("traded") & known
        if "volume" in panels and panels["volume"] is not None:
            vol = _numeric(panels, "volume", like=st)
            mask = mask.where(known, vol > 0)
    elif "volume" in panels and panels["volume"] is not None:
        vol = _numeric(panels, "volume", like=like)
        mask = vol > 0
    if mask is None:
        raise KeyError("traded_mask : panel 'status' ou 'volume' requis")
    if like is not None:
        mask = mask.reindex(index=like.index, columns=like.columns)
    return mask.fillna(False).astype(bool)


def listed_mask(panels: Panels, like: pd.DataFrame | None = None) -> pd.DataFrame:
    """Masque des séances où le titre est coté (cours ``close_adj`` ou ``tr_index`` connu).

    Si aucun panel de prix n'est disponible, toutes les cellules de ``like``
    sont considérées comme cotées.
    """
    for key in ("close_adj", "tr_index"):
        if key in panels and panels[key] is not None:
            p = _price(panels, key)
            if like is not None:
                p = p.reindex(index=like.index, columns=like.columns)
            return p.notna()
    if like is None:
        raise KeyError("listed_mask : panel 'close_adj' ou 'tr_index' requis (ou argument like)")
    return pd.DataFrame(True, index=like.index, columns=like.columns)


def _row_positions(df: pd.DataFrame) -> pd.DataFrame:
    """Numéro de séance (0..T-1) diffusé sur la grille de ``df``."""
    pos = np.broadcast_to(np.arange(len(df), dtype=float)[:, None], df.shape)
    return pd.DataFrame(pos, index=df.index, columns=df.columns)


def _annualize(x: pd.DataFrame, annualize: bool) -> pd.DataFrame:
    return x * math.sqrt(TRADING_DAYS) if annualize else x


def _check_window(window: int, min_obs: int | None = None) -> None:
    if window < 1:
        raise ValueError("window doit être >= 1")
    if min_obs is not None and not 1 <= min_obs <= window:
        raise ValueError("min_obs doit être compris entre 1 et window")


# ---------------------------------------------------------------------------
# Rendements
# ---------------------------------------------------------------------------


def returns(
    panels: Panels,
    kind: ReturnKind = "simple",
    basis: ReturnBasis = "calendar",
    price: str = "tr_index",
    gap_adjust: bool = False,
    max_gap: int | None = None,
) -> pd.DataFrame:
    """Rendements séance par séance ou d'échange à échange.

    * ``basis="calendar"`` : ``r_t = P_t / P_{t-1} - 1`` sur chaque séance du
      panel ; un cours périmé (pas d'échange) donne un rendement nul.
    * ``basis="traded"`` (*trade-to-trade*, Maynes & Rumsey, 1993) : défini
      seulement les séances échangées, ``r_t = P_t / P_{τ(t)} - 1`` où
      ``τ(t) < t`` est la dernière séance échangée précédente ; ``NaN`` sinon.
      Avec ``gap_adjust=True`` le rendement est divisé par ``sqrt(t - τ(t))``,
      ce qui ramène sa variance à celle d'une séance sous l'hypothèse de
      marche aléatoire.

    ``kind="log"`` renvoie ``ln(P_t / P_prev)``.

    Parameters
    ----------
    panels
        Panels larges ; ``price`` et (pour ``basis="traded"``) ``status`` ou
        ``volume``.
    kind
        ``"simple"`` (décimal) ou ``"log"``.
    basis
        ``"calendar"`` ou ``"traded"``.
    price
        Clé du panel de prix (``tr_index`` par défaut : dividendes inclus).
    gap_adjust
        Normalisation par la racine de l'écart en séances (``basis="traded"``).
    max_gap
        Si fourni, rendements d'échange à échange couvrant plus de ``max_gap``
        séances mis à ``NaN``.
    """
    if kind not in ("simple", "log"):
        raise ValueError("kind doit valoir 'simple' ou 'log'")
    p = _price(panels, price)
    if basis == "calendar":
        ratio = p / p.shift(1)
        gap = None
    elif basis == "traded":
        tr = traded_mask(panels, like=p)
        pt = p.where(tr)
        prev = pt.ffill().shift(1)
        ratio = pt / prev
        last_pos = _row_positions(p).where(tr).ffill().shift(1)
        gap = _row_positions(p) - last_pos
        if max_gap is not None:
            ratio = ratio.where(gap <= max_gap)
    else:
        raise ValueError("basis doit valoir 'calendar' ou 'traded'")
    r = np.log(ratio) if kind == "log" else ratio - 1.0
    if gap_adjust and gap is not None:
        r = r / np.sqrt(gap)
    return r.astype(float)


def past_return(panels: Panels, window: int = 21, price: str = "tr_index") -> pd.DataFrame:
    """Rendement cumulé sur les ``window`` dernières séances : ``P_t / P_{t-window} - 1``."""
    _check_window(window)
    p = _price(panels, price)
    return p / p.shift(window) - 1.0


def momentum(
    panels: Panels,
    lookback: int = 252,
    skip: int = 21,
    price: str = "tr_index",
    min_traded_fraction: float | None = None,
) -> pd.DataFrame:
    """Momentum « lookback-skip » (Jegadeesh & Titman, 1993).

    ``MOM_t = P_{t-skip} / P_{t-lookback} - 1``

    calculé sur l'indice de rendement total (dividendes réinvestis). Le saut
    ``skip`` (21 séances ≈ 1 mois pour le 12-1) écarte le retournement de
    court terme (Jegadeesh, 1990). Les décalages sont en séances.

    Parameters
    ----------
    lookback, skip
        ``0 <= skip < lookback`` (voir :data:`MOMENTUM_PRESETS`).
    min_traded_fraction
        Si fourni, ``NaN`` lorsque la part des séances échangées dans la
        fenêtre ``(t-lookback, t-skip]`` est inférieure à ce seuil : un
        momentum construit sur deux échanges dans l'année n'est pas un signal.
    """
    if not 0 <= skip < lookback:
        raise ValueError("il faut 0 <= skip < lookback")
    p = _price(panels, price)
    mom = p.shift(skip) / p.shift(lookback) - 1.0
    if min_traded_fraction is not None:
        tr = traded_mask(panels, like=p).astype(float).where(p.notna())
        frac = tr.rolling(lookback - skip, min_periods=1).mean().shift(skip)
        mom = mom.where(frac >= min_traded_fraction)
    return mom


def momentum_preset(panels: Panels, name: str = "12-1", **kwargs: object) -> pd.DataFrame:
    """Momentum selon un paramétrage nommé de :data:`MOMENTUM_PRESETS` (``"12-1"``, ``"6-1"``…)."""
    if name not in MOMENTUM_PRESETS:
        raise KeyError(f"préréglage inconnu {name!r} ; choix : {sorted(MOMENTUM_PRESETS)}")
    lookback, skip = MOMENTUM_PRESETS[name]
    return momentum(panels, lookback=lookback, skip=skip, **kwargs)  # type: ignore[arg-type]


def short_term_reversal(panels: Panels, window: int = 5, price: str = "tr_index") -> pd.DataFrame:
    """Signal de retournement de court terme (Jegadeesh, 1990 ; Lehmann, 1990).

    ``REV_t = -(P_t / P_{t-window} - 1)``

    Orientation : une valeur **élevée** désigne un titre qui a **baissé** sur
    la fenêtre (candidat au rebond). ``window=5`` ≈ 1 semaine, ``21`` ≈ 1 mois.
    L'indice de rendement total est utilisé par défaut pour qu'un détachement
    de dividende ne crée pas de faux « plongeon ».
    """
    return -past_return(panels, window=window, price=price)


# ---------------------------------------------------------------------------
# Risque
# ---------------------------------------------------------------------------


def volatility(
    panels: Panels,
    window: int = 63,
    min_obs: int = 20,
    annualize: bool = True,
    basis: ReturnBasis = "traded",
    gap_adjust: bool = True,
    kind: ReturnKind = "log",
    price: str = "tr_index",
    max_gap: int | None = None,
) -> pd.DataFrame:
    """Volatilité glissante (écart-type des rendements), annualisée.

    ``σ_t = sqrt(252) · sd({r_s : s ∈ (t-window, t], r_s observé})`` (ddof = 1)

    Par défaut, rendements logarithmiques d'échange à échange normalisés par
    ``sqrt(écart)`` (voir :func:`returns`) : l'estimateur est alors sans biais
    pour la variance quotidienne d'une marche aléatoire même si le titre n'est
    échangé qu'une séance sur trois, alors que les rendements calendaires
    (zéros des séances sans échange) sous-estiment la volatilité. ``NaN`` s'il
    y a moins de ``min_obs`` rendements observés dans la fenêtre. Facteur
    « faible volatilité » : Ang et al. (2006), Blitz & van Vliet (2007).
    """
    _check_window(window, min_obs)
    r = returns(panels, kind=kind, basis=basis, price=price, gap_adjust=gap_adjust, max_gap=max_gap)
    vol = r.rolling(window, min_periods=min_obs).std(ddof=1)
    return _annualize(vol, annualize)


def downside_vol(
    panels: Panels,
    window: int = 63,
    min_obs: int = 20,
    target: float = 0.0,
    annualize: bool = True,
    basis: ReturnBasis = "traded",
    gap_adjust: bool = True,
    kind: ReturnKind = "log",
    price: str = "tr_index",
) -> pd.DataFrame:
    """Semi-écart-type sous un seuil (Sortino & Price, 1994 ; Estrada, 2007).

    ``σ⁻_t = sqrt(252) · sqrt( (1/n) Σ_s min(r_s - τ, 0)² )``

    sur les ``n >= min_obs`` rendements observés de la fenêtre ``(t-window, t]``
    (même construction des rendements que :func:`volatility`), ``τ = target``.
    """
    _check_window(window, min_obs)
    r = returns(panels, kind=kind, basis=basis, price=price, gap_adjust=gap_adjust)
    d2 = np.minimum(r - target, 0.0) ** 2
    semi = d2.rolling(window, min_periods=min_obs).mean()
    return _annualize(np.sqrt(semi), annualize)


def beta_dimson(
    panels: Panels,
    market: pd.Series,
    window: int = 252,
    lags: int = 2,
    min_obs: int = 60,
    price: str = "tr_index",
    market_is_returns: bool = False,
) -> pd.DataFrame:
    """Bêta de Dimson (1979) glissant, sans anticipation.

    Régression sur la fenêtre, par titre :

    ``r_{i,s} = α + Σ_{k=-K}^{K} β_k · r_{m,s-k} + ε_s``,  ``β_Dimson = Σ_k β_k``

    avec des rendements **calendaires** (un cours périmé donne 0, et ce sont
    précisément les retards ``k > 0`` qui captent la réaction différée des
    titres peu échangés ; les avances ``k < 0`` captent le retard de l'indice
    lui-même, Scholes & Williams, 1977).

    Absence d'anticipation : l'avance ``k = -K`` à la ligne ``s`` utilise
    ``r_{m,s+K}``. La valeur publiée en ``t`` est donc la régression dont la
    fenêtre se termine en ``s = t - K`` ; elle n'utilise que des rendements de
    marché ``<= t`` et des rendements du titre ``<= t - K``. Résultat
    identique à :func:`brvm_alpha.quant.stats.dimson_beta` appliquée à cette
    fenêtre.

    Parameters
    ----------
    market
        Niveau de l'indice de marché (``market_is_returns=False``) ou ses
        rendements simples, sur le même calendrier que le panel (réindexé sans
        remplissage).
    window
        Longueur de la fenêtre en séances.
    lags
        ``K >= 0`` (``K = 0`` : bêta MCO).
    min_obs
        Nombre minimal d'observations complètes (titre et ``2K+1`` termes de
        marché) dans la fenêtre ; au moins ``2K + 3``.
    """
    if lags < 0:
        raise ValueError("lags doit être >= 0")
    if not isinstance(market, pd.Series):
        raise TypeError("market doit être une pd.Series (niveau ou rendements de l'indice)")
    p = _price(panels, price)
    r = (p / p.shift(1) - 1.0).to_numpy(dtype=float)
    m_raw = pd.to_numeric(market, errors="coerce").astype(float).reindex(p.index)
    if market_is_returns:
        m = m_raw
    else:
        lvl = m_raw.where(m_raw > 0)
        m = lvl / lvl.shift(1) - 1.0
    ks = list(range(-lags, lags + 1))
    design = np.column_stack([m.shift(k).to_numpy(dtype=float) for k in ks])
    T, N = r.shape
    n_par = len(ks) + 1
    min_obs = max(min_obs, n_par + 1)
    if min_obs > window:
        raise ValueError(f"window ({window}) doit être >= min_obs effectif ({min_obs})")
    Z = np.column_stack([np.ones(T), design])  # (T, p)
    z_ok = np.isfinite(Z).all(axis=1)
    Zc = np.where(z_ok[:, None], Z, 0.0)
    ZZ = (Zc[:, :, None] * Zc[:, None, :]).reshape(T, -1)  # (T, p²)
    out = np.full((T, N), np.nan)

    def _window_sum(a: np.ndarray) -> np.ndarray:
        c = np.cumsum(a, axis=0)
        c[window:] = c[window:] - c[:-window]
        return c

    for j in range(N):
        y = r[:, j]
        w = (z_ok & np.isfinite(y)).astype(float)
        if w.sum() < min_obs:
            continue
        yc = np.where(w > 0, y, 0.0)
        cnt = _window_sum(w)
        xtx = _window_sum(ZZ * w[:, None]).reshape(T, n_par, n_par)
        xty = _window_sum(Zc * (w * yc)[:, None])
        ok = np.flatnonzero(cnt >= min_obs - 1e-9)
        if ok.size == 0:
            continue
        coef = np.einsum("tij,tj->ti", np.linalg.pinv(xtx[ok]), xty[ok])
        out[ok, j] = coef[:, 1:].sum(axis=1)
    beta = pd.DataFrame(out, index=p.index, columns=p.columns)
    return beta.shift(lags) if lags > 0 else beta


# ---------------------------------------------------------------------------
# Liquidité
# ---------------------------------------------------------------------------


def amihud_illiquidity(
    panels: Panels,
    window: int = 63,
    min_obs: int = 10,
    unit: float = 1e6,
    price: str = "tr_index",
) -> pd.DataFrame:
    """Illiquidité d'Amihud (2002).

    ``ILLIQ_t = (1/n) Σ_{s ∈ (t-window, t], échangé} |r_s| / (V_s / unit)``

    où ``r_s`` est le rendement d'échange à échange et ``V_s`` la valeur
    échangée en FCFA (``unit = 10⁶`` : variation de prix par million de FCFA
    échangé). Seules les séances échangées à valeur ``> 0`` comptent ; ``NaN``
    s'il y en a moins de ``min_obs`` dans la fenêtre.
    """
    _check_window(window, min_obs)
    r = returns(panels, kind="simple", basis="traded", price=price)
    v = _numeric(panels, "value", like=r)
    ratio = r.abs() / (v.where(v > 0) / unit)
    return ratio.rolling(window, min_periods=min_obs).mean()


def zero_volume_fraction(panels: Panels, window: int = 63, min_obs: int = 20) -> pd.DataFrame:
    """Part des séances sans échange sur la fenêtre (Lesmond et al., 1999 ; Bekaert et al., 2007).

    ``ZV_t = (1/n) Σ_{s ∈ (t-window, t], coté} 1[s non échangée]``

    Les séances suspendues comptent comme non échangées ; les séances où le
    titre n'est pas coté sont exclues du dénominateur.
    """
    _check_window(window, min_obs)
    like = _reference(panels, "close_adj", "tr_index", "status", "volume")
    listed = listed_mask(panels, like=like)
    z = (~traded_mask(panels, like=like)).astype(float).where(listed)
    return z.rolling(window, min_periods=min_obs).mean()


def zero_return_fraction(
    panels: Panels, window: int = 63, min_obs: int = 20, price: str = "close_adj"
) -> pd.DataFrame:
    """Part des rendements calendaires exactement nuls (Lesmond, Ogden & Trzcinka, 1999).

    Mesure de coût de transaction implicite : un titre dont le cours ne bouge
    pas est un titre que personne n'a intérêt à traiter à son coût effectif.
    """
    _check_window(window, min_obs)
    r = returns(panels, kind="simple", basis="calendar", price=price)
    z = (r == 0.0).astype(float).where(r.notna())
    return z.rolling(window, min_periods=min_obs).mean()


def _value_on_listed(panels: Panels) -> tuple[pd.DataFrame, pd.DataFrame]:
    v = _numeric(panels, "value")
    listed = listed_mask(panels, like=v) if any(
        k in panels for k in ("close_adj", "tr_index")
    ) else v.notna()
    return v.fillna(0.0).where(listed), listed


def median_value_traded(
    panels: Panels, window: int = 63, min_obs: int = 20, include_zero: bool = True
) -> pd.DataFrame:
    """Valeur échangée médiane par séance (FCFA) sur la fenêtre.

    ``include_zero=True`` (défaut, cohérent avec ``UniverseFilter``) : les
    séances sans échange comptent pour 0, ce qui pénalise les titres rarement
    échangés ; ``False`` : médiane sur les seules séances échangées.
    """
    _check_window(window, min_obs)
    v, _ = _value_on_listed(panels)
    if not include_zero:
        tr = traded_mask(panels, like=v)
        v = v.where(tr & (v > 0))
    return v.rolling(window, min_periods=min_obs).median()


def average_daily_value(panels: Panels, window: int = 63, min_obs: int = 20) -> pd.DataFrame:
    """Valeur moyenne échangée par séance (ADV, FCFA), séances sans échange à 0."""
    _check_window(window, min_obs)
    v, _ = _value_on_listed(panels)
    return v.rolling(window, min_periods=min_obs).mean()


def _listed_or_observed(panels: Panels, like: pd.DataFrame) -> pd.DataFrame:
    """Masque « coté » si un panel de prix existe, sinon cellules renseignées de ``like``."""
    if any(panels.get(k) is not None for k in ("close_adj", "tr_index")):
        return listed_mask(panels, like=like)
    return like.notna()


def split_factor_panel(
    panels: Panels,
    split_factor: pd.DataFrame | None = None,
    like: pd.DataFrame | None = None,
) -> pd.DataFrame | None:
    """Facteur de division cumulé, **convention de** ``data/store.py``.

    ``close_adj_t = close_t / f_t`` : ``f_t`` est le produit des ratios ``k``
    des divisions k:1 postérieures à ``t`` (``f = 1`` après la dernière
    division, ``f = k`` avant une division k:1). Un montant par action brut se
    ramène à la base de ``close_adj`` par ``montant / f`` ; un nombre de titres
    brut par ``titres × f``.

    Sources, par ordre de priorité :

    1. l'argument ``split_factor`` ;
    2. le panel ``panels["split_factor"]`` (pivot large de la colonne
       ``split_factor`` de :func:`brvm_alpha.data.store.adjusted_table`) ;
    3. le facteur exact ``f = close / close_adj`` si le cours **brut**
       ``close`` et ``close_adj`` sont fournis.

    Renvoie ``None`` si aucune source n'est disponible. Les facteurs ``<= 0``
    deviennent NaN ; les trous sont comblés par report vers l'avant (le
    facteur est constant par morceaux). Seuls les **ratios** ``f_s / f_u``
    (``s, u <= t``) sont utilisés par les caractéristiques : ils ne dépendent
    que des divisions survenues entre ``s`` et ``u``, donc pas du futur.

    Parameters
    ----------
    like
        Grille cible (index et colonnes) ; par défaut celle de la source.
    """
    if split_factor is not None:
        _check_index(split_factor, "split_factor")
        src = split_factor
    elif panels.get("split_factor") is not None:
        src = _raw(panels, "split_factor")
    elif panels.get("close") is not None and panels.get("close_adj") is not None:
        adj = _price(panels, "close_adj")
        src = _price(panels, "close").reindex(index=adj.index, columns=adj.columns) / adj
    else:
        return None
    f = src.apply(pd.to_numeric, errors="coerce").astype(float)
    f = f.where(np.isfinite(f) & (f > 0))
    if like is not None:
        f = f.reindex(columns=like.columns)
        f = f.reindex(f.index.union(like.index)).ffill().reindex(like.index)
    return f.ffill()


def adjusted_volume(
    panels: Panels,
    split_factor: pd.DataFrame | None = None,
    split_adjust: bool = True,
) -> pd.DataFrame:
    """Volume en titres ramené à la base de titres de ``close_adj`` (ajusté des splits).

    * Facteur connu (voir :func:`split_factor_panel`) : ``V^adj_t = V_t · f_t``
      (exact ; une séance sans échange reste à 0 même si ``f_t`` est inconnu,
      une séance échangée dont le facteur est inconnu devient NaN).
    * Sinon, volume implicite ``V^adj_t ≈ value_t / close_adj_t`` (valeur
      échangée en FCFA, invariante aux splits, divisée par le cours ajusté) :
      exact au rapport ``VWAP_t / close_t`` près, borné par la limite de
      variation journalière.
    * ``split_adjust=False`` : volume brut ``V_t`` (à réserver aux titres dont
      on sait qu'ils n'ont connu aucune division).

    Les séances sans échange valent 0, les séances non cotées NaN.

    Raises
    ------
    KeyError
        si ``split_adjust=True`` et qu'aucune des combinaisons ``volume`` +
        facteur, ou ``value`` + ``close_adj``, n'est disponible.
    """
    has_vol = panels.get("volume") is not None
    if split_adjust:
        f = None
        if has_vol:
            vol = _numeric(panels, "volume")
            f = split_factor_panel(panels, split_factor, like=vol)
        if f is not None:
            listed = _listed_or_observed(panels, vol)
            v = vol.fillna(0.0)
            adj = (v * f).mask(f.isna() & (v == 0.0), 0.0)
            return adj.where(listed)
        if panels.get("value") is not None and panels.get("close_adj") is not None:
            val = _numeric(panels, "value")
            px = _price(panels, "close_adj").reindex(index=val.index, columns=val.columns)
            listed = _listed_or_observed(panels, val)
            v = val.fillna(0.0)
            adj = (v / px).mask(v == 0.0, 0.0)
            return adj.where(listed)
        raise KeyError(
            "volume ajusté des splits : fournir 'volume' + 'split_factor' (ou 'close' brut "
            "+ 'close_adj'), ou bien 'value' + 'close_adj' ; split_adjust=False pour "
            f"utiliser le volume brut (clés disponibles : {sorted(panels)})"
        )
    vol = _numeric(panels, "volume")
    listed = _listed_or_observed(panels, vol)
    return vol.fillna(0.0).where(listed)


def turnover_proxy(
    panels: Panels,
    window: int = 21,
    base_window: int = 252,
    min_obs: int | None = None,
    split_factor: pd.DataFrame | None = None,
    split_adjust: bool = True,
) -> pd.DataFrame:
    """Rotation relative (volume anormal), sans nombre de titres en circulation.

    ``TO_t = mean(V^adj sur window) / mean(V^adj sur base_window)``

    où ``V^adj`` est le volume ajusté des splits (:func:`adjusted_volume`),
    séances sans échange à 0, fenêtres se terminant en ``t``. Sans capital
    flottant fiable, on mesure la rotation d'un titre **par rapport à sa
    propre norme** ; un volume anormalement élevé précède des rendements
    supérieurs (Gervais, Kaniel & Mingelgrin, 2001). Sur le volume brut, une
    division k:1 multiplierait ``TO`` par jusqu'à ``k`` pendant
    ``base_window`` séances sans aucun changement de liquidité. Les deux
    moyennes étant exprimées dans la même base de titres, un split postérieur
    à ``t`` ne modifie pas ``TO_t``. ``NaN`` si la base est nulle ou trop
    courte (``min_obs``, défaut ``base_window // 2``).
    """
    if not 1 <= window <= base_window:
        raise ValueError("il faut 1 <= window <= base_window")
    min_obs = base_window // 2 if min_obs is None else min_obs
    _check_window(base_window, min_obs)
    vol = adjusted_volume(panels, split_factor=split_factor, split_adjust=split_adjust)
    short = vol.rolling(window, min_periods=min(window, min_obs)).mean()
    base = vol.rolling(base_window, min_periods=min_obs).mean()
    return short / base.where(base > 0)


def turnover(
    panels: Panels,
    shares_outstanding: pd.Series | pd.DataFrame,
    window: int = 63,
    min_obs: int = 20,
    split_factor: pd.DataFrame | None = None,
    split_adjust: bool = True,
) -> pd.DataFrame:
    """Taux de rotation classique (Datar, Naik & Radcliffe, 1998).

    ``TURN_t = mean(V^adj_s, s ∈ (t-window, t]) / N^adj_t``

    ``V^adj`` : volume ajusté des splits (:func:`adjusted_volume`).
    ``shares_outstanding`` (``N^adj``) doit être exprimé dans la **même base
    de titres que** ``close_adj`` (nombre de titres après les divisions,
    comme le nombre actuel) : ``Series`` (symbole -> nombre, constant) ou
    panel large connu à chaque date (sans anticipation de l'appelant). Un
    panel de nombres **bruts** ``N_t`` se convertit par ``N_t · split_factor``,
    ou s'utilise tel quel avec ``split_adjust=False`` (ratio brut / brut).
    """
    _check_window(window, min_obs)
    vol = adjusted_volume(panels, split_factor=split_factor, split_adjust=split_adjust)
    adv = vol.rolling(window, min_periods=min_obs).mean()
    if isinstance(shares_outstanding, pd.DataFrame):
        sh = shares_outstanding.reindex(index=adv.index, columns=adv.columns).astype(float)
        return adv / sh.where(sh > 0)
    sh_s = pd.to_numeric(shares_outstanding, errors="coerce").astype(float).reindex(adv.columns)
    return adv.div(sh_s.where(sh_s > 0), axis=1)


# ---------------------------------------------------------------------------
# Microstructure : limites de variation, plus haut 52 semaines
# ---------------------------------------------------------------------------


def limit_hits(
    panels: Panels,
    window: int = 21,
    side: Literal["up", "down", "both", "net"] = "net",
    threshold: float | None = None,
    min_obs: int = 1,
    change: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Nombre de séances à la limite de variation (±7,5 %) sur la fenêtre.

    ``UP_t = Σ_{s ∈ (t-window, t]} 1[Δ_s >= θ]``, ``DOWN_t = Σ 1[Δ_s <= -θ]``

    ``side`` : ``"up"``, ``"down"``, ``"both"`` (``UP + DOWN``) ou ``"net"``
    (``UP - DOWN``, signe = sens de la pression). ``θ`` vaut par défaut
    ``ExecutionModel.price_limit - ExecutionModel.limit_tolerance`` (7,3 %).

    Variation ``Δ`` : panel ``change`` fourni (décimal), sinon ``change_pct``
    du BOC / 100 (variation officielle par rapport au cours de référence),
    sinon rendement calendaire de ``close_adj``. Le BOC peut afficher un cours
    indicatif à la limite sans échange : ces séances comptent (excès d'offre
    ou de demande non servi). Voir la revue 02, section 7, pour l'asymétrie
    plafond haut / plafond bas observée à la BRVM.
    """
    _check_window(window, min_obs)
    if side not in ("up", "down", "both", "net"):
        raise ValueError("side doit valoir 'up', 'down', 'both' ou 'net'")
    if threshold is None:
        ex = ExecutionModel()
        threshold = ex.price_limit - ex.limit_tolerance
    if change is not None:
        _check_index(change, "change")
        ch = change.astype(float)
    elif "change_pct" in panels and panels["change_pct"] is not None:
        ch = _numeric(panels, "change_pct") / 100.0
    else:
        ch = returns(panels, kind="simple", basis="calendar", price="close_adj")
    obs = ch.notna()
    up = (ch >= threshold).astype(float).where(obs)
    down = (ch <= -threshold).astype(float).where(obs)
    n_up = up.rolling(window, min_periods=min_obs).sum()
    n_down = down.rolling(window, min_periods=min_obs).sum()
    if side == "up":
        return n_up
    if side == "down":
        return n_down
    if side == "both":
        return n_up + n_down
    return n_up - n_down


def distance_to_high(
    panels: Panels, window: int = 252, min_obs: int = 126, price: str = "close_adj"
) -> pd.DataFrame:
    """Distance au plus haut sur ``window`` séances (George & Hwang, 2004).

    ``D_t = P_t / max_{s ∈ (t-window, t]} P_s - 1``  (``<= 0``, nul au plus haut)

    Transformation monotone du ratio ``P/H`` de George & Hwang : les rangs sont
    identiques. Calcul sur le cours ajusté des splits (``close_adj``), le prix
    que voient les investisseurs (hypothèse d'ancrage).
    """
    _check_window(window, min_obs)
    p = _price(panels, price)
    hi = p.rolling(window, min_periods=min_obs).max()
    return p / hi - 1.0


# ---------------------------------------------------------------------------
# Valorisation et dividendes
# ---------------------------------------------------------------------------


def _datetime_array(df: pd.DataFrame) -> np.ndarray:
    """Panel de dates -> tableau ``datetime64[ns]`` (NaT si manquant)."""
    conv = df.apply(lambda s: pd.to_datetime(s, errors="coerce"))
    return conv.to_numpy(dtype="datetime64[ns]")


def _day_numbers(arr: np.ndarray) -> np.ndarray:
    """``datetime64`` -> nombre de jours depuis 1970 (float, NaN pour NaT)."""
    days = arr.astype("datetime64[D]").astype(np.int64).astype(float)
    days[np.isnat(arr)] = np.nan
    return days


def _index_days(index: pd.DatetimeIndex) -> np.ndarray:
    return index.to_numpy(dtype="datetime64[ns]").astype("datetime64[D]").astype(np.int64).astype(float)


def _days_since_dividend_raw(panels: Panels) -> tuple[pd.DataFrame, np.ndarray]:
    d = _raw(panels, "last_div_date")
    d_days = _day_numbers(_datetime_array(d))
    elapsed = _index_days(d.index)[:, None] - d_days
    return pd.DataFrame(elapsed, index=d.index, columns=d.columns), d_days


def dividend_yield(panels: Panels, max_dividend_age_days: float | None = None) -> pd.DataFrame:
    """Rendement du dividende net : ``DY_t = net_yield_pct_t / 100``.

    Rendement **net** de la retenue à la source tel que publié par le BOC
    (Litzenberger & Ramaswamy, 1979 pour l'effet des dividendes et de la
    fiscalité). Valeurs négatives -> NaN. Si ``max_dividend_age_days`` est
    fourni et que le dernier dividende (``last_div_date``) est plus ancien,
    le rendement est mis à 0 : le BOC peut continuer d'afficher le rendement
    d'un dividende qui n'a pas été reconduit.
    """
    dy = _numeric(panels, "net_yield_pct") / 100.0
    dy = dy.where(dy >= 0)
    if max_dividend_age_days is not None:
        elapsed, _ = _days_since_dividend_raw(panels)
        elapsed = elapsed.reindex(index=dy.index, columns=dy.columns)
        stale = elapsed > max_dividend_age_days
        dy = dy.mask(stale & dy.notna(), 0.0)
    return dy


def earnings_yield(panels: Panels) -> pd.DataFrame:
    """Rendement bénéficiaire ``EY_t = 1 / PER_t`` si ``PER_t > 0``, NaN sinon (Basu, 1977).

    Un PER négatif ou nul (pertes) n'a pas d'interprétation de valorisation
    monotone ; il est mis à NaN (le titre sort de ce signal sans être
    pénalisé artificiellement).
    """
    per = _numeric(panels, "per")
    return (1.0 / per).where(per > 0)


def _dividend_state(
    panels: Panels,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, np.ndarray]:
    """Montants bruts, validité, événements et apparitions de dividende.

    Un **événement** est une ligne où ``last_div_date`` (renseignée) diffère
    de la dernière valeur renseignée précédente ; la première observation
    renseignée est aussi un événement (dividende connu à l'entrée dans
    l'échantillon). La date de l'événement est la **ligne** où le changement
    apparaît dans le BOC (information publiée en ``t``), pas la date de
    paiement elle-même. Une **apparition** est un événement ou une
    correction (montant modifié, date inchangée) : la ligne où le couple
    (date, montant) affiché apparaît pour la première fois.
    """
    d = _raw(panels, "last_div_date")
    a = _numeric(panels, "last_div_net", like=d)
    d_arr = _datetime_array(d)
    d_days = pd.DataFrame(_day_numbers(d_arr), index=d.index, columns=d.columns)
    valid = d_days.notna() & a.notna()
    dv = d_days.where(valid)
    av = a.where(valid)
    new = valid & (dv != dv.ffill().shift(1))
    appear = new | (valid & (av != av.ffill().shift(1)))
    return av, valid, new, appear, d_arr


def _take_rows(values: np.ndarray, pos: np.ndarray) -> np.ndarray:
    """``out[t, j] = values[pos[t, j], j]`` ; NaN là où ``pos < 0``."""
    out = np.take_along_axis(values, np.clip(pos, 0, None), axis=0)
    return np.where(pos >= 0, out, np.nan)


def _last_true_row(mask: np.ndarray) -> np.ndarray:
    """Numéro de la dernière ligne ``<= t`` où ``mask`` est vrai (-1 sinon)."""
    rows = np.arange(mask.shape[0])[:, None]
    return np.maximum.accumulate(np.where(mask, rows, -1), axis=0)


def dividend_growth(
    panels: Panels,
    split_factor: pd.DataFrame | None = None,
    split_adjust: bool = True,
    split_tolerance: float = 0.25,
) -> pd.DataFrame:
    """Croissance du dividende net entre les deux derniers dividendes connus, ajustée des splits.

    ``g_t = D̃_k / D̃_{k-1} - 1``,  ``D̃ = D / f_a``

    où ``D_k`` est le dernier dividende connu en ``t`` (dernière valeur
    publiée, corrections comprises), ``D_{k-1}`` le dernier montant affiché
    avant l'événement ``k`` ; un nouveau dividende est détecté par un
    changement de ``last_div_date``. ``f_a`` est le facteur de division
    (convention du store, ``close_adj = close / f``) de la ligne ``a`` où le
    montant affiché est **apparu** : le BOC conserve parfois le montant
    d'avant split jusqu'au dividende suivant (BOAB, 2024) et le recalcule
    parfois le jour du split sans changer la date (PRSC 2019, SNTS 2026) ;
    dans les deux cas le montant est rapporté à la base de titres en vigueur
    à son apparition. ``g`` ne dépend que de ``f_a / f_b`` (lignes ``<= t``),
    donc des seules divisions survenues entre les deux apparitions : aucune
    anticipation. ``NaN`` tant que deux dividendes n'ont pas été observés, si
    ``D̃_{k-1} <= 0`` ou si le facteur est inconnu.

    Lintner (1956) : les dirigeants ne relèvent le dividende que s'ils jugent
    la hausse des bénéfices durable — la croissance du dividende est un
    signal de qualité. Sans ajustement, une division k:1 ressemblerait à une
    baisse de ``1 - 1/k`` (−90 % pour un 10:1).

    Parameters
    ----------
    split_factor
        Facteurs de division cumulés, **convention de** ``data/store.py``
        (``split_factor`` de :func:`brvm_alpha.data.store.adjusted_table`,
        pivoté en large). À défaut : ``panels["split_factor"]``, puis
        ``close / close_adj`` (voir :func:`split_factor_panel`).
    split_adjust
        ``True`` (défaut) : sans facteur exact, une division est **détectée**
        par le facteur implicite ``f̂ = ref_price / close_adj`` (cours de
        référence brut / cours ajusté) et ``g`` vaut NaN lorsque ``f̂`` varie
        de plus de ``split_tolerance`` (en relatif) entre les apparitions de
        ``D_{k-1}`` et de ``D_k`` ; sans ``ref_price`` ni facteur :
        ``KeyError``. Avec les deux, ``f̂`` sert de **contrôle de cohérence** :
        un facteur du store qui s'écarte de ``f̂`` de plus de
        ``split_tolerance`` à l'apparition d'un montant (split daté quelques
        séances trop tard, par ex. SEMC en décembre 2018) n'est pas utilisé et
        l'on se rabat sur la règle de détection. ``ref_price`` étant la
        référence de la séance suivante (``close - D`` la veille d'un
        détachement), ``f̂`` est évalué avec ``ref`` et avec ``ref + D`` et
        l'écart le plus faible est retenu. ``False`` : montants bruts (titres
        sans division).
    split_tolerance
        Seuil de détection (défaut 25 % : au-dessus du bruit de la limite de
        variation ±7,5 %, en dessous des plus petits ajustements observés,
        1,3 à 1,5).
    """
    if split_tolerance <= 0:
        raise ValueError("split_tolerance doit être > 0")
    a, valid, new, appear, _ = _dividend_state(panels)
    raw = a.to_numpy(dtype=float)
    app_pos = _last_true_row(appear.to_numpy(dtype=bool))
    tol = math.log1p(split_tolerance)
    f_app: np.ndarray | None = None  # facteur du store à l'apparition du montant
    implied: np.ndarray | None = None  # facteurs implicites (ref, ref + D) / close_adj, idem
    if split_adjust:
        f = split_factor_panel(panels, split_factor, like=a)
        if f is not None:
            f_app = _take_rows(f.to_numpy(dtype=float), app_pos)
        if panels.get("ref_price") is not None and panels.get("close_adj") is not None:
            # ref_price est la référence de la séance suivante : la veille d'un
            # détachement, ref = close - D ; on retient aussi le candidat (ref + D).
            ref = _price(panels, "ref_price").reindex(index=a.index, columns=a.columns).ffill()
            adj = _price(panels, "close_adj").reindex(index=a.index, columns=a.columns).ffill()
            lo = _take_rows((ref / adj).to_numpy(dtype=float), app_pos)
            hi = _take_rows(((ref + a.fillna(0.0)) / adj).to_numpy(dtype=float), app_pos)
            implied = np.stack([lo, hi])
        if f_app is None and implied is None:
            raise KeyError(
                "dividend_growth : information de split requise ('split_factor', 'close' brut "
                "+ 'close_adj', ou 'ref_price' + 'close_adj') ; split_adjust=False pour "
                f"comparer les montants bruts (clés disponibles : {sorted(panels)})"
            )
    new_arr = new.to_numpy(dtype=bool)
    cur_pos = _last_true_row(valid.to_numpy(dtype=bool))
    before = np.vstack([np.full((1, cur_pos.shape[1]), -1), cur_pos[:-1]])
    ev_pos = _last_true_row(new_arr)
    prev_pos = np.where(ev_pos >= 0, np.take_along_axis(before, np.clip(ev_pos, 0, None), axis=0), -1)
    prev_pos = np.where(np.cumsum(new_arr, axis=0) >= 2, prev_pos, -1)

    def _growth(amounts: np.ndarray) -> np.ndarray:
        cur, prev = _take_rows(amounts, cur_pos), _take_rows(amounts, prev_pos)
        with np.errstate(invalid="ignore", divide="ignore"):
            return np.where(prev > 0, cur / prev - 1.0, np.nan)

    g_raw = _growth(raw)
    if f_app is None and implied is None:
        return pd.DataFrame(g_raw, index=a.index, columns=a.columns, dtype=float)
    with np.errstate(invalid="ignore", divide="ignore"):
        if implied is not None:
            # Même base de titres (selon le BOC) aux deux apparitions : ratio brut valable.
            cur_c = [_take_rows(c, cur_pos) for c in implied]
            prev_c = [_take_rows(c, prev_pos) for c in implied]
            jump = np.fmin.reduce([np.abs(np.log(x / y)) for x in cur_c for y in prev_c])
            g_same_base = np.where(jump <= tol, g_raw, np.nan)
        if f_app is None:
            return pd.DataFrame(g_same_base, index=a.index, columns=a.columns, dtype=float)
        g = _growth(raw / f_app)
        if implied is not None:
            # Contrôle de cohérence : un facteur du store contredit par le cours de
            # référence brut du BOC (split mal daté) n'est pas utilisé ; on se replie
            # alors sur le ratio brut si le BOC n'indique aucun split entre les deux.
            gap = np.fmin(np.abs(np.log(implied[0] / f_app)), np.abs(np.log(implied[1] / f_app)))
            coherent = (gap <= tol) | ~np.isfinite(implied[0])
            pair_ok = _take_rows(coherent.astype(float), cur_pos) * _take_rows(
                coherent.astype(float), prev_pos
            )
            g = np.where(pair_ok == 1.0, g, g_same_base)
    return pd.DataFrame(g, index=a.index, columns=a.columns, dtype=float)


def dividend_stability(
    panels: Panels, grace_days: float = 550.0, split_factor: pd.DataFrame | None = None
) -> pd.DataFrame:
    """Nombre d'années civiles consécutives avec dividende (série en cours).

    À la date ``t`` : soit ``Y_t`` l'ensemble des années de paiement des
    dividendes ``> 0`` observés jusqu'à ``t`` et ``y* = max Y_t`` ;
    ``S_t = max{k : y*, y*-1, …, y*-k+1 ∈ Y_t}``. La série est **rompue**
    (``S_t = 0``) si le dernier paiement date de plus de ``grace_days`` jours
    (≈ 18 mois par défaut : un dividende annuel non reconduit). Titre coté sans
    dividende connu : 0 ; titre non coté : NaN. L'historique est borné par le
    début de l'échantillon. Une omission de dividende est suivie d'une dérive
    négative (Michaely, Thaler & Womack, 1995).

    Seuls le signe des montants et les dates comptent : la mesure est
    invariante aux divisions. ``split_factor`` est accepté pour la symétrie
    avec :func:`dividend_growth` mais n'a aucun effet.
    """
    del split_factor  # invariance aux splits : seul le signe du montant compte
    a, _valid, new, _appear, d_arr = _dividend_state(panels)
    idx_days = _index_days(a.index)
    years = d_arr.astype("datetime64[Y]").astype(np.int64) + 1970
    pay_days = _day_numbers(d_arr)
    amounts = a.to_numpy(dtype=float)
    new_arr = new.to_numpy(dtype=bool)
    T, N = a.shape
    streak = np.zeros((T, N))
    last_pay = np.full((T, N), np.nan)
    has_event = np.zeros((T, N), dtype=bool)
    for j in range(N):
        rows = np.flatnonzero(new_arr[:, j]).tolist()
        seen: set[int] = set()
        cur_streak = 0.0
        cur_pay = np.nan
        start = 0
        for r in rows:
            # Remplissage de la plage précédente avec l'état courant.
            streak[start:r, j] = cur_streak
            last_pay[start:r, j] = cur_pay
            if np.isfinite(amounts[r, j]) and amounts[r, j] > 0:
                seen.add(int(years[r, j]))
                y = max(seen)
                k = 0
                while (y - k) in seen:
                    k += 1
                cur_streak = float(k)
                cur_pay = pay_days[r, j]
            has_event[r:, j] = True
            start = r
        streak[start:, j] = cur_streak
        last_pay[start:, j] = cur_pay
    elapsed = idx_days[:, None] - last_pay
    alive = np.isfinite(elapsed) & (elapsed <= grace_days)
    out = np.where(alive, streak, 0.0)
    res = pd.DataFrame(out, index=a.index, columns=a.columns)
    if any(k in panels for k in ("close_adj", "tr_index")):
        listed = listed_mask(panels, like=res)
        res = res.where(listed | pd.DataFrame(has_event, index=a.index, columns=a.columns))
    return res


def days_since_dividend(panels: Panels) -> pd.DataFrame:
    """Jours calendaires écoulés depuis le dernier paiement : ``t - last_div_date``.

    NaN si aucune date n'est connue ; une valeur négative signale une date de
    paiement annoncée et encore à venir. Sert à capter la prime du mois de
    dividende (Hartzmark & Solomon, 2013) et les effets de détachement.
    """
    elapsed, _ = _days_since_dividend_raw(panels)
    return elapsed


# ---------------------------------------------------------------------------
# Saisonnalité
# ---------------------------------------------------------------------------


def seasonality(
    panels: Panels,
    min_years: int = 2,
    max_years: int | None = 10,
    month_offset: int = 0,
    price: str = "tr_index",
) -> pd.DataFrame:
    """Rendement moyen du même mois calendaire les années passées (Heston & Sadka, 2008).

    Soit ``R_{i,y,m}`` le rendement du mois ``m`` de l'année ``y`` (dernier
    cours du mois / dernier cours du mois précédent - 1). Pour la date ``t``
    du mois courant ``p`` et le mois cible ``m* = mois(p + month_offset)`` :

    ``SEAS_t = moyenne(R_{i,y,m*})`` sur les ``max_years`` derniers mois ``m*``
    **entièrement révolus avant le début du mois courant** (au moins
    ``min_years`` ; ``max_years=None`` : toute l'histoire).

    ``month_offset=0`` : mois en cours (vue « tenue intra-mois ») ;
    ``month_offset=1`` : mois suivant (rebalancement en fin de mois).
    """
    if not 0 <= month_offset <= 11:
        raise ValueError("month_offset doit être compris entre 0 et 11")
    if min_years < 1 or (max_years is not None and max_years < min_years):
        raise ValueError("il faut 1 <= min_years <= max_years")
    p = _price(panels, price)
    periods = p.index.to_period("M")
    month_end = p.groupby(periods).last()
    full = pd.period_range(month_end.index.min(), month_end.index.max(), freq="M")
    month_end = month_end.reindex(full)
    mret = month_end / month_end.shift(1) - 1.0
    stats = []
    for m in range(1, 13):
        sub = mret[mret.index.month == m]
        if max_years is None:
            stats.append(sub.expanding(min_periods=min_years).mean())
        else:
            stats.append(sub.rolling(max_years, min_periods=min_years).mean())
    table = pd.concat(stats).sort_index()
    k = month_offset // 12 + 1
    target = periods + (month_offset - 12 * k)
    out = table.reindex(target)
    out.index = p.index
    return out.astype(float)


# ---------------------------------------------------------------------------
# Bibliothèque par défaut
# ---------------------------------------------------------------------------

_FeatureFn: TypeAlias = Callable[[Panels], pd.DataFrame]

#: Panels permettant un volume ajusté des splits (voir :func:`adjusted_volume`).
_SPLIT_INVARIANT_VOLUME = "volume+split_factor|volume+close+close_adj|value+close_adj"
#: Panels permettant d'ajuster ou de détecter les splits (voir :func:`dividend_growth`).
_SPLIT_INFO = "split_factor|close+close_adj|ref_price+close_adj"


def _default_specs(market: pd.Series | None) -> list[tuple[str, tuple[str, ...], _FeatureFn]]:
    specs: list[tuple[str, tuple[str, ...], _FeatureFn]] = [
        ("mom_12_1", ("tr_index",), lambda P: momentum(P, 252, 21)),
        ("mom_6_1", ("tr_index",), lambda P: momentum(P, 126, 21)),
        ("mom_3_0", ("tr_index",), lambda P: momentum(P, 63, 0)),
        ("rev_1w", ("tr_index",), lambda P: short_term_reversal(P, 5)),
        ("rev_1m", ("tr_index",), lambda P: short_term_reversal(P, 21)),
        ("vol_63", ("tr_index", "status|volume"), lambda P: volatility(P, 63, 20)),
        ("downside_vol_63", ("tr_index", "status|volume"), lambda P: downside_vol(P, 63, 20)),
        ("amihud_63", ("tr_index", "value", "status|volume"), lambda P: amihud_illiquidity(P, 63)),
        ("zero_volume_63", ("status|volume",), lambda P: zero_volume_fraction(P, 63)),
        ("median_value_63", ("value",), lambda P: median_value_traded(P, 63)),
        ("adv_63", ("value",), lambda P: average_daily_value(P, 63)),
        (
            "turnover_rel_21_252",
            (_SPLIT_INVARIANT_VOLUME,),
            lambda P: turnover_proxy(P, 21, 252),
        ),
        ("limit_net_21", ("change_pct|close_adj",), lambda P: limit_hits(P, 21, "net")),
        ("limit_up_21", ("change_pct|close_adj",), lambda P: limit_hits(P, 21, "up")),
        ("limit_down_21", ("change_pct|close_adj",), lambda P: limit_hits(P, 21, "down")),
        ("dist_high_252", ("close_adj",), lambda P: distance_to_high(P, 252)),
        ("dividend_yield", ("net_yield_pct",), dividend_yield),
        ("earnings_yield", ("per",), earnings_yield),
        ("dividend_growth", ("last_div_date", "last_div_net", _SPLIT_INFO), dividend_growth),
        ("dividend_stability", ("last_div_date", "last_div_net"), dividend_stability),
        ("days_since_dividend", ("last_div_date",), days_since_dividend),
        ("seasonality", ("tr_index",), lambda P: seasonality(P)),
    ]
    if market is not None:
        specs.append(("beta_dimson_252", ("tr_index",), lambda P: beta_dimson(P, market, 252)))
    return specs


def _requirement_met(need: str, available: set[str]) -> bool:
    """``"a+b|c"`` : (``a`` et ``b``) ou ``c``."""
    return any(all(k in available for k in alt.split("+")) for alt in need.split("|"))


def compute_features(
    panels: Panels,
    market: pd.Series | None = None,
    include: list[str] | None = None,
    split_factor: pd.DataFrame | None = None,
) -> dict[str, pd.DataFrame]:
    """Calcule la bibliothèque de caractéristiques par défaut.

    Les caractéristiques dont les panels requis sont absents sont omises
    (``"a|b"`` signifie « ``a`` ou ``b`` », ``"a+b"`` « ``a`` et ``b`` »).
    ``market`` (niveau de l'indice, par ex. BRVM Composite) active le bêta de
    Dimson. ``include`` restreint le calcul à une liste de noms.

    ``split_factor`` (convention de ``data/store.py`` : ``close_adj = close /
    split_factor``), équivalent à la clé ``panels["split_factor"]``, ajuste
    des divisions les grandeurs par action brutes : ``turnover_rel_21_252``
    (volume) et ``dividend_growth`` (dividende). Sans facteur,
    ``turnover_rel_21_252`` utilise le volume implicite ``value / close_adj``
    et ``dividend_growth`` neutralise (NaN) les comparaisons de part et
    d'autre d'une division détectée par ``ref_price / close_adj`` ; sans
    aucune de ces informations, ces caractéristiques sont **omises** plutôt
    que biaisées.

    Les **sens** économiques (valeur élevée = attractive ?) ne sont pas
    imposés ici : c'est au modèle (``strategy/alpha.py``) d'orienter chaque
    caractéristique avant normalisation et combinaison.
    """
    if split_factor is not None:
        panels = {**panels, "split_factor": split_factor}
    available = {k for k, v in panels.items() if v is not None}
    out: dict[str, pd.DataFrame] = {}
    for name, needs, fn in _default_specs(market):
        if include is not None and name not in include:
            continue
        if all(_requirement_met(need, available) for need in needs):
            out[name] = fn(panels)
    return out


# ===========================================================================
# Signaux de la stratégie v1 (SPECIFICATION_STRATEGIE.md §3.1-§3.3, §5.2, §11)
# ===========================================================================
#
# Les fonctions ci-dessous suivent la spécification v1.0 du 22/11/2026. Leurs
# valeurs par défaut sont celles de la spécification (§11 ``signals.*`` et
# ``composite.momentum_*``, §12.1). Chacune accepte un dictionnaire ``params``
# (la section correspondante de ``configs/strategy_v1.yaml``) : ses clés
# **remplacent** les arguments de même nom ; les clés descriptives inconnues
# (``def``, ``per_basis``…) sont ignorées. Les signaux sont orientés « valeur
# élevée = attractive » sauf mention contraire (signaux de recherche).
#
# Rien ici ne mesure une performance : ce sont des caractéristiques datées,
# sans biais d'anticipation (la valeur en t n'utilise que des lignes <= t).

#: Fenêtres exclues des statistiques (§3.1.3 : trou de 50 jours de BOC en 2021).
EXCLUDED_STAT_WINDOWS: tuple[tuple[str, str], ...] = (("2021-05-06", "2021-06-25"),)

#: Écart calendaire (jours) au-delà duquel un rendement est « multi-séances » (§3.1.3).
MULTI_SESSION_GAP_DAYS: int = 4

#: Délai de disponibilité d'un document sans en-tête ``Last-Modified`` (§3.1.4) : 2 séances
#: après la date du nom de fichier.
FUNDAMENTALS_LAG_SESSIONS: int = 2

#: Blocs du score composite v1 (variante A) et signaux de recherche (§3.3, poids nul).
V1_SIGNALS: tuple[str, ...] = ("ep", "dy", "mom6_1", "lowvol", "quality_proxy")
RESEARCH_SIGNALS_V1: tuple[str, ...] = ("mom3_1", "mom6_0", "mom12_1", "mom12_7", "amihud")


@dataclass(frozen=True)
class EpsOverride:
    """Surcharge point-in-time du BPA (spécification §3.2, signal EP).

    ``PER = cours brut / eps`` à partir de la ``publication_lag_sessions``-ième
    séance qui suit ``known_from`` (date du document source ; ``None`` : toutes
    les dates), jusqu'à ``valid_until`` inclus (``None`` : sans fin).
    """

    eps: float
    known_from: str | None = None
    valid_until: str | None = None
    source: str = ""


@dataclass(frozen=True)
class DividendAbsence:
    """Absence de dividende annoncée pour l'exercice ``fiscal_year``.

    À partir de la date effective de ``known_from`` (``None`` : toutes les
    dates), DY = 0 tant que le dernier dividende connu a été payé au plus tard
    pendant l'année civile ``fiscal_year`` (c'est-à-dire au titre d'un exercice
    antérieur). Un paiement ultérieur (exercice suivant) lève la règle.
    """

    symbol: str
    fiscal_year: int
    known_from: str | None
    source: str = ""


@dataclass(frozen=True)
class ExceptionalDividend:
    """Dividende comprenant une part exceptionnelle, exclue de DY (§3.2)."""

    symbol: str
    payment_date: str
    total_net: float
    exceptional_net: float
    source: str = ""


#: Surcharges de BPA de la spécification (§3.2, §12.1 ``data.eps_override``). Dates =
#: préfixe du nom de fichier des états financiers sur brvm.org (revue 06a, §8 n° 10-11).
EPS_OVERRIDES_V1: dict[str, EpsOverride] = {
    "ETIT": EpsOverride(
        10.00,
        "2026-04-13",
        source="ETI, états financiers IFRS 2025 : BPA part du groupe 1,68 cent US = 10,00 FCFA "
        "(brvm.org, 20260413) ; le PER du BOC (2,98) porte sur le RN total",
    ),
    "ORGT": EpsOverride(
        264.0,
        "2026-05-04",
        source="Oragroup, états financiers 2025 : BPA de base 264 FCFA (dilué 241) (brvm.org, 20260504)",
    ),
}

#: Absences de dividende annoncées (repli v1 de DY, §3.2) : BOAN 2025, ORGT, SAFC
#: (spécification) et FTSC 2025 (test §12.3 n° 5 ; revue 06b §7.6). ORGT et SAFC sont de
#: toute façon couverts par le garde-fou de 15 mois (derniers paiements : 17/07/2020 et
#: 29/07/2011) ; pour SAFC, l'absence de distribution depuis 2011 est déjà lisible dans
#: tous les BOC de l'échantillon, d'où ``known_from=None``.
ANNOUNCED_NO_DIVIDEND_V1: tuple[DividendAbsence, ...] = (
    DividendAbsence("BOAN", 2025, "2026-04-29",
                    "communiqué de presse BOA Niger du 27/04/2026 (mis en ligne le 29/04/2026)"),
    DividendAbsence("FTSC", 2025, "2026-06-10",
                    "Filtisac, états financiers 2025 : projet d'affectation sans dividende"),
    DividendAbsence("ORGT", 2025, "2026-05-04",
                    "Oragroup, états financiers 2025 ; aucun dividende depuis 2020"),
    DividendAbsence("SAFC", 2025, None, "aucun dividende depuis 2011 (BOC : dernier paiement 29/07/2011)"),
)

#: Dividendes exceptionnels connus (§3.2 : « dividendes exceptionnels exclus (FTSC) »).
#: FTSC, exercice 2024 : 1 320 ordinaire (IRVM 12 %) + 680,67 exceptionnel (IRVM 17 %)
#: brut, soit 1 161,60 + 564,96 = 1 726,56 net payé le 30/09/2025 (revue 06b §8 n° 12).
EXCEPTIONAL_DIVIDENDS_V1: tuple[ExceptionalDividend, ...] = (
    ExceptionalDividend("FTSC", "2025-09-30", 1726.56, 564.96,
                        "calendrier des dividendes, exercice 2024 ; 680,67 × 0,83 = 564,96 net"),
)

#: Paramètres par défaut des signaux v1 (miroir de la spécification §11-§12.1).
SIGNAL_PARAMS_V1: dict[str, dict[str, Any]] = {
    "ep": {"publication_lag_sessions": FUNDAMENTALS_LAG_SESSIONS, "missing_per_as_loss": False},
    "dy": {"max_age_months": 15, "cap": 0.15, "exclude_exceptional": True,
           "zero_if_no_dividend_voted": True, "source": "auto"},
    "mom6_1": {"lookback_sessions": 126, "skip_sessions": 21, "min_obs": 100},
    "mom3_1": {"lookback_sessions": 63, "skip_sessions": 21, "min_obs": 50},
    "mom6_0": {"lookback_sessions": 126, "skip_sessions": 0, "min_obs": 100},
    "mom12_1": {"lookback_sessions": 252, "skip_sessions": 21, "min_obs": 200},
    "mom12_7": {"lookback_sessions": 252, "skip_sessions": 147, "min_obs": 200},
    "lowvol": {"window_sessions": 250, "min_obs": 200, "fallback_window": 126,
               "fallback_min_obs": 100, "sign": -1.0},
    "quality_proxy": {"dividend_years_weight": 0.5, "per_sane_range": (3.0, 40.0),
                      "per_sane_weight": 0.5, "window_years": 5},
    "amihud": {"window": 63, "min_obs": 10},
    "momentum_vol_scaling": {"window_sessions": 126, "min_obs": 100, "min_history_months": 24,
                             "floor": 0.5, "cap": 1.0},
    "momentum_crash_filter": {"bear_lookback_months": 24, "vol_window_sessions": 63,
                              "vol_min_obs": 50, "vol_percentile": 80.0, "multiplier": 0.5,
                              "duration_months": 3, "min_history_sessions": 252},
}


def _merge(params: Mapping[str, Any] | None, aliases: Mapping[str, str] | None = None,
           **current: Any) -> dict[str, Any]:
    """Arguments courants, remplacés par les clés connues de ``params`` (alias acceptés)."""
    out = dict(current)
    if params:
        for key, value in params.items():
            name = (aliases or {}).get(key, key)
            if name in out:
                out[name] = value
    return out


def _grid(panels: Panels) -> pd.DataFrame:
    """Grille date × symbole de référence (prix ajusté, TR ou cours brut)."""
    return _reference(panels, "close_adj", "tr_index", "close")


def _ts(x: Any) -> pd.Timestamp | None:
    """Date ou ``None`` (``None``, NaN et NaT donnent ``None``)."""
    if x is None:
        return None
    try:
        if pd.isna(x):
            return None
    except (TypeError, ValueError):
        pass
    return pd.Timestamp(x)


def _effective_row(index: pd.DatetimeIndex, known_from: Any, lag_sessions: int) -> int:
    """Première ligne où un document daté ``known_from`` est utilisable.

    Règle §3.1.4 (sans en-tête ``Last-Modified``) : ``lag_sessions`` séances après la
    date du document, soit la ligne ``p(d) + lag`` où ``p(d)`` est la dernière séance
    ``<= d`` (``lag = 0`` : le jour même s'il s'agit d'une séance). ``None`` -> 0.
    """
    d = _ts(known_from)
    if d is None:
        return 0
    pos = int(index.searchsorted(d, side="right")) - 1 + int(lag_sessions)
    if lag_sessions == 0 and (pos < 0 or index[pos] != d):
        pos += 1  # le jour même seulement si c'est une séance, sinon la suivante
    return max(pos, 0)


def _end_row(index: pd.DatetimeIndex, valid_until: Any) -> int:
    d = _ts(valid_until)
    return len(index) if d is None else int(index.searchsorted(d, side="right"))


def _raw_close(panels: Panels, like: pd.DataFrame, split_factor: pd.DataFrame | None = None) -> pd.DataFrame:
    """Cours brut (non ajusté) : ``close`` s'il est fourni, sinon ``close_adj × f``.

    À défaut de facteur de division, ``close_adj`` est utilisé tel quel (exact après la
    dernière division seulement).
    """
    if panels.get("close") is not None:
        return _price(panels, "close").reindex(index=like.index, columns=like.columns)
    adj = _price(panels, "close_adj").reindex(index=like.index, columns=like.columns)
    f = split_factor_panel(panels, split_factor, like=like)
    return adj if f is None else adj * f


def _bool_panel(df: pd.DataFrame, like: pd.DataFrame) -> pd.DataFrame:
    return df.reindex(index=like.index, columns=like.columns).eq(True)


def multi_session_mask(panels: Panels, like: pd.DataFrame | None = None,
                       gap_days: int = MULTI_SESSION_GAP_DAYS) -> pd.DataFrame:
    """Rendements « multi-séances » (§3.1.3), exclus des estimations de risque.

    Panel booléen ``multi_session`` s'il est fourni ; sinon, comme
    ``store.stats_mask`` : écart calendaire entre deux séances du panel ``> gap_days``
    **ou** ``missing_sessions > 0`` (``store.adjusted_table`` : BOC manquants entre deux
    lignes) lorsque ce panel existe. Ces rendements restent utilisés pour chaîner le TR
    (momentum).
    """
    ref = like if like is not None else _grid(panels)
    if panels.get("multi_session") is not None:
        return _bool_panel(_raw(panels, "multi_session"), ref)
    days = _index_days(pd.DatetimeIndex(ref.index))
    gap = np.concatenate([[False], np.diff(days) > gap_days]) if len(days) else np.zeros(0, bool)
    out = pd.DataFrame(np.broadcast_to(gap[:, None], ref.shape), index=ref.index, columns=ref.columns)
    if panels.get("missing_sessions") is not None:
        out = out | _numeric(panels, "missing_sessions", like=ref).gt(0)
    return out


def valid_return_mask(
    panels: Panels,
    like: pd.DataFrame | None = None,
    price: str = "tr_index",
    gap_days: int = MULTI_SESSION_GAP_DAYS,
    exclude_windows: Iterable[tuple[str, str]] = EXCLUDED_STAT_WINDOWS,
) -> pd.DataFrame:
    """Rendements quotidiens « valides » pour les statistiques (§3.1.3, §3.2).

    Valide : rendement calendaire défini (cours en ``t`` et ``t-1``), non
    multi-séances (:func:`multi_session_mask`), titre non suspendu (``SP``) en ``t``
    ni en ``t-1``, date hors des fenêtres exclues (2021). Un cours non échangé
    (``NC``) donne un rendement nul **valide** : c'est la convention de la
    spécification (§3.1.3, rendement 0 marqué périmé).

    Le rendement du jour de reprise après une suspension couvre toute la suspension :
    il est exclu ici (différence avec ``store.stats_mask``, qui le garde). Pour
    reproduire exactement le masque du store, fournir ``panels["stats_usable"]``
    (``store.stats_mask(panel_dir)``) : il remplace alors les règles ci-dessus (le cours
    doit toujours être défini en ``t`` et ``t-1``).
    """
    p = _price(panels, price)
    if like is not None:
        p = p.reindex(index=like.index, columns=like.columns)
    ok = p.notna() & p.shift(1).notna()
    if panels.get("stats_usable") is not None:
        return (ok & _bool_panel(_raw(panels, "stats_usable"), p)).astype(bool)
    ok &= ~multi_session_mask(panels, like=p, gap_days=gap_days)
    if panels.get("status") is not None:
        susp = _raw(panels, "status").reindex(index=p.index, columns=p.columns).eq("suspended")
        ok &= ~susp & ~susp.shift(1, fill_value=False)
    for lo, hi in exclude_windows:
        rows = (p.index >= pd.Timestamp(lo)) & (p.index <= pd.Timestamp(hi))
        ok.loc[rows] = False
    return ok.astype(bool)


#: Bases de comptage des fenêtres glissantes (§3.1.3, §3.2, U2-U7). ``"boc"`` : lignes du
#: panel, c'est-à-dire BOC **disponibles** (convention des calculs de l'annexe
#: ``docs/annexes-spec/univ_breadth.py``, qui a produit les tableaux du §2) ; ``"sessions"`` :
#: séances du calendrier contigu des numéros de BOC (``session_no``), BOC manquants compris
#: (lecture littérale de « en séances » et de « un BOC absent n'est pas un jour férié »).
#: Les deux lectures ne diffèrent que là où des BOC manquent (96 en 2021, 33 ailleurs) ; le
#: choix pour le test S1 doit être tranché par un addendum pré-enregistré.
WINDOW_BASES: tuple[str, ...] = ("boc", "sessions")


def _check_basis(window_basis: str) -> str:
    b = str(window_basis)
    if b not in WINDOW_BASES:
        raise ValueError(f"window_basis doit valoir l'un de {WINDOW_BASES} (lu : {window_basis!r})")
    return b


#: Additif v1.1 (§8.4, D1) : base de comptage par défaut des fenêtres (séances, numéros de BOC).
DEFAULT_WINDOW_BASIS_V11: str = "sessions"

#: D1 : plancher absolu des seuils minimaux d'observations **au prorata** des BOC disponibles,
#: pour les signaux (MOM, LOWVOL et son repli, dosage du momentum, filtre de crash…) …
SIGNAL_MIN_OBS_FLOOR: int = 40
#: … et pour les filtres d'univers (U2, U3, MDV63 et tout seuil « m observations sur L séances »).
FILTER_MIN_OBS_FLOOR: int = 20
#: D1 : une borne de fenêtre de rendement prend le dernier cours disponible à la séance de
#: borne ou avant, à **5 séances au plus** ; au-delà, NaN.
MAX_BOUND_STALE_SESSIONS: int = 5


def missing_sessions_in_window(sess: np.ndarray | Sequence[int], window: int) -> np.ndarray:
    """Séances **sans BOC** parmi les ``window`` dernières séances de chaque ligne (D1).

    ``sess`` : numéro de séance de chaque ligne (strictement croissant, :func:`session_numbers`).
    Seules les séances postérieures ou égales à la première séance du panel comptent : une
    fenêtre qui déborde avant le début des données n'est pas « amputée de BOC manquants »,
    elle est simplement incomplète (le seuil reste ``m``).
    """
    s = np.asarray(sess, dtype=np.int64)
    if not len(s):
        return np.zeros(0, dtype=np.int64)
    lo = np.maximum(s - int(window) + 1, s[0])
    span = s - lo + 1
    start = np.searchsorted(s, lo, side="left")
    rows = np.arange(len(s)) - start + 1
    return np.maximum(span - rows, 0).astype(np.int64)


def prorata_min_obs(min_obs: int, window: int, n_missing: np.ndarray | int, floor: int) -> np.ndarray:
    """Seuil effectif ``m_eff = max(⌈m × n_dispo / L⌉ ; min(m, plancher))`` (additif v1.1, D1).

    ``n_dispo = L − n_manquants`` : BOC disponibles dans la fenêtre de ``L`` séances. Le
    plancher (40 pour un signal, 20 pour un filtre d'univers) ne relève jamais le seuil
    au-dessus de ``m`` (un seuil déjà inférieur au plancher est gardé tel quel). Sans BOC
    manquant, ``m_eff = m``. Arithmétique entière (aucun arrondi flottant).
    """
    m, L = int(min_obs), int(window)
    miss = np.asarray(n_missing, dtype=np.int64)
    n_avail = np.clip(L - miss, 0, L)
    m_eff = -((-m * n_avail) // L)
    return np.maximum(m_eff, min(m, int(floor))).astype(np.int64)


def min_obs_thresholds(sess: np.ndarray | None, window: int, min_obs: int, floor: int,
                       index: pd.Index | None = None) -> pd.Series | int:
    """Seuil minimal d'observations par ligne (D1) : constant (``m``) sans numéros de séance."""
    if sess is None:
        return int(min_obs)
    thr = prorata_min_obs(min_obs, window, missing_sessions_in_window(sess, window), floor)
    return pd.Series(thr, index=index) if index is not None else thr  # type: ignore[return-value]


def session_numbers(panels: Panels, like: pd.DataFrame | None = None) -> np.ndarray | None:
    """Numéro global de séance de chaque ligne (calendrier des BOC, séances manquantes comprises).

    Sources, par ordre de préférence : panel ``session_no`` (large : maximum par ligne,
    le numéro est commun à tous les titres d'une date ; ou ``Series`` par date) ; à défaut
    ``missing_sessions`` (BOC manquants avant chaque ligne : ``n_t = n_{t-1} + 1 + manque``).
    ``None`` si aucune source n'est disponible ou si les numéros ne sont pas strictement
    croissants (une ligne = une séance, signalé par l'appelant).
    """
    ref = like if like is not None else _grid(panels)
    idx = pd.DatetimeIndex(ref.index)
    if not len(idx):
        return None
    raw = panels.get("session_no") if hasattr(panels, "get") else None
    s: pd.Series | None = None
    if isinstance(raw, pd.DataFrame):
        s = raw.reindex(idx).apply(pd.to_numeric, errors="coerce").max(axis=1)
    elif isinstance(raw, pd.Series):
        s = pd.to_numeric(raw, errors="coerce")
        s = s[~s.index.duplicated(keep="last")].reindex(idx)
    if s is not None and s.notna().any():
        vals = s.to_numpy(dtype=float)
        out = np.empty(len(vals))
        last = math.nan
        for i, v in enumerate(vals):
            last = v if math.isfinite(v) else (last + 1.0 if math.isfinite(last) else float(i))
            out[i] = last
    else:
        ms = panels.get("missing_sessions") if hasattr(panels, "get") else None
        if not isinstance(ms, pd.DataFrame):
            return None
        gap = ms.reindex(idx).apply(pd.to_numeric, errors="coerce").max(axis=1).fillna(0.0).clip(lower=0.0)
        out = np.cumsum(1.0 + gap.to_numpy(dtype=float))
    if len(out) > 1 and np.any(np.diff(out) <= 0):
        return None
    return out.astype(np.int64)


def on_session_grid(
    df: pd.DataFrame,
    sess: np.ndarray | None,
    fn: Callable[[pd.DataFrame], pd.DataFrame],
    *,
    ffill: bool | int = False,
) -> pd.DataFrame:
    """Applique ``fn`` (fenêtre glissante, décalage) sur le calendrier **contigu** des séances.

    Les séances sans BOC deviennent des lignes NaN (``ffill=True`` : dernier niveau
    connu reporté, pour un niveau comme le TR ; ``ffill=k`` entier : report limité à
    ``k`` séances, règle des bornes de l'additif v1.1, D1) ; le résultat est ramené aux
    lignes de ``df``. ``sess=None`` : ``fn(df)`` sur les lignes (base ``"boc"``). Exemple :
    ``on_session_grid(valid, sess, lambda x: x.rolling(63, min_periods=1).sum())``
    compte les rendements valides des 63 dernières **séances**.
    """
    if sess is None:
        return fn(df)
    s = np.asarray(sess, dtype=np.int64)
    if len(s) != len(df):
        raise ValueError("on_session_grid : un numéro de séance par ligne est attendu")
    if not len(s):
        return fn(df)
    work = df.astype(float) if any(dt == bool or dt == object for dt in df.dtypes) else df
    full = work.set_axis(pd.Index(s), axis=0).reindex(pd.RangeIndex(int(s.min()), int(s.max()) + 1))
    if ffill is True:
        full = full.ffill()
    elif ffill is not False and ffill is not None and int(ffill) > 0:
        full = full.ffill(limit=int(ffill))
    out = fn(full)
    return out.reindex(pd.Index(s)).set_axis(df.index, axis=0)


def mom_sessions(
    panels: Panels,
    lookback_sessions: int = 126,
    skip_sessions: int = 21,
    min_obs: int = 100,
    price: str = "tr_index",
    gap_days: int = MULTI_SESSION_GAP_DAYS,
    exclude_windows: Iterable[tuple[str, str]] = EXCLUDED_STAT_WINDOWS,
    params: Mapping[str, Any] | None = None,
    window_basis: str = "boc",
    prorata: bool | None = None,
    obs_floor: int = SIGNAL_MIN_OBS_FLOOR,
    max_stale_sessions: int | None = MAX_BOUND_STALE_SESSIONS,
) -> pd.DataFrame:
    """Momentum en **séances** : ``TR(t - skip) / TR(t - lookback) - 1`` (§3.2).

    Le TR (``tr_index``) chaîne tous les rendements, multi-séances compris. Le
    signal vaut NaN si le titre n'est pas coté en ``t`` ou si la fenêtre des
    ``lookback`` derniers rendements ``(t - lookback, t]`` compte moins de
    ``min_obs`` rendements valides (:func:`valid_return_mask`, multi-séances,
    suspensions et fenêtre 2021 exclus du comptage). Choix documenté : le comptage
    porte sur toute la fenêtre de ``lookback`` séances (126, au moins 100), comme
    pour LOWVOL (250, au moins 200).

    ``window_basis`` (:data:`WINDOW_BASES`) : ``"boc"`` compte les lignes du panel (BOC
    disponibles) ; ``"sessions"`` (défaut de l'additif v1.1, D1) compte les séances du
    calendrier des numéros de BOC (:func:`session_numbers`). En base ``"sessions"`` :

    * **bornes** : le niveau aux séances ``t - skip`` et ``t - lookback`` est le dernier
      TR disponible à cette séance ou avant, à ``max_stale_sessions`` (5) séances au
      plus ; sinon NaN (``None`` : report illimité, comportement antérieur) ;
    * **seuil au prorata** (``prorata=None`` ⇒ actif) : ``m_eff = max(⌈m × n_dispo / L⌉ ;
      min(m, 40))`` avec ``n_dispo`` les BOC disponibles dans la fenêtre de ``L`` séances
      (:func:`prorata_min_obs`) ; sous le seuil, NaN (bloc manquant, z = 0).

    En base ``"boc"``, aucune séance ne manque dans la fenêtre : ``m_eff = m``.
    """
    a = _merge(params, lookback_sessions=lookback_sessions, skip_sessions=skip_sessions, min_obs=min_obs)
    lb, sk, mo = int(a["lookback_sessions"]), int(a["skip_sessions"]), int(a["min_obs"])
    if not 0 <= sk < lb:
        raise ValueError("il faut 0 <= skip_sessions < lookback_sessions")
    _check_window(lb, mo)
    basis = _check_basis(window_basis)
    p = _price(panels, price)
    sess = session_numbers(panels, like=p) if basis == "sessions" else None
    ff: bool | int = True if max_stale_sessions is None else int(max_stale_sessions)
    mom = on_session_grid(p, sess, lambda x: x.shift(sk) / x.shift(lb) - 1.0, ffill=ff)
    valid = valid_return_mask(panels, like=p, price=price, gap_days=gap_days, exclude_windows=exclude_windows)
    cnt = on_session_grid(valid.astype(float), sess, lambda x: x.rolling(lb, min_periods=1).sum())
    use_prorata = (basis == "sessions") if prorata is None else bool(prorata)
    thr = min_obs_thresholds(sess if use_prorata else None, lb, mo, obs_floor, index=p.index)
    ok = cnt.ge(thr, axis=0) if isinstance(thr, pd.Series) else cnt >= thr
    return mom.where(ok & p.notna())


def _mom_preset(name: str) -> Callable[..., pd.DataFrame]:
    def fn(panels: Panels, params: Mapping[str, Any] | None = None, **kwargs: Any) -> pd.DataFrame:
        args = {**SIGNAL_PARAMS_V1[name], **kwargs}
        return mom_sessions(panels, params=params, **args)

    fn.__name__ = name
    lb, sk = SIGNAL_PARAMS_V1[name]["lookback_sessions"], SIGNAL_PARAMS_V1[name]["skip_sessions"]
    fn.__doc__ = (
        f"Momentum ``{name}`` : ``TR(t-{sk}) / TR(t-{lb}) - 1`` en séances, au moins "
        f"{SIGNAL_PARAMS_V1[name]['min_obs']} rendements valides sur {lb} (voir :func:`mom_sessions`)."
    )
    return fn


mom6_1 = _mom_preset("mom6_1")
mom3_1 = _mom_preset("mom3_1")
mom6_0 = _mom_preset("mom6_0")
mom12_1 = _mom_preset("mom12_1")
mom12_7 = _mom_preset("mom12_7")


def lowvol(
    panels: Panels,
    window_sessions: int = 250,
    min_obs: int = 200,
    fallback_window: int = 126,
    fallback_min_obs: int = 100,
    sign: float = -1.0,
    annualize: bool = False,
    price: str = "tr_index",
    gap_days: int = MULTI_SESSION_GAP_DAYS,
    exclude_windows: Iterable[tuple[str, str]] = EXCLUDED_STAT_WINDOWS,
    params: Mapping[str, Any] | None = None,
    window_basis: str = "boc",
    prorata: bool | None = None,
    obs_floor: int = SIGNAL_MIN_OBS_FLOOR,
) -> pd.DataFrame:
    """Faible volatilité : ``lv = -σ`` (§3.2, Blitz, Pang & van Vliet 2013).

    ``σ`` est l'écart-type (ddof = 1) des rendements quotidiens valides du TR sur
    ``window_sessions`` séances (au moins ``min_obs``), à défaut sur
    ``fallback_window`` séances (au moins ``fallback_min_obs``), NaN sinon.
    Rendements calendaires : un cours périmé compte pour 0 (convention §3.1.3) ;
    un titre très peu échangé paraît donc peu volatil (le filtre U3 de l'univers
    limite ce biais). ``annualize=True`` multiplie par ``sqrt(252)`` (rangs inchangés).
    ``window_basis`` : fenêtres comptées en BOC disponibles (``"boc"``) ou en séances du
    calendrier des numéros de BOC (``"sessions"``, voir :data:`WINDOW_BASES`). En base
    ``"sessions"`` (additif v1.1, D1), les seuils 200/250 et 100/126 sont ramenés au prorata
    des BOC disponibles dans chaque fenêtre, avec un plancher de 40 observations
    (:func:`prorata_min_obs`) ; ``prorata=False`` garde les seuils bruts.
    """
    a = _merge(params, window_sessions=window_sessions, min_obs=min_obs, fallback_window=fallback_window,
               fallback_min_obs=fallback_min_obs, sign=sign)
    _check_window(int(a["window_sessions"]), int(a["min_obs"]))
    _check_window(int(a["fallback_window"]), int(a["fallback_min_obs"]))
    basis = _check_basis(window_basis)
    p = _price(panels, price)
    sess = session_numbers(panels, like=p) if basis == "sessions" else None
    r = (p / p.shift(1) - 1.0).where(
        valid_return_mask(panels, like=p, price=price, gap_days=gap_days, exclude_windows=exclude_windows))
    use_prorata = (basis == "sessions") if prorata is None else bool(prorata)

    def sigma_on(window: int, m: int) -> pd.DataFrame:
        sd = on_session_grid(r, sess, lambda x: x.rolling(window, min_periods=min(2, m)).std(ddof=1))
        n = on_session_grid(r, sess, lambda x: x.rolling(window, min_periods=1).count())
        thr = min_obs_thresholds(sess if use_prorata else None, window, m, obs_floor, index=r.index)
        ok = n.ge(thr, axis=0) if isinstance(thr, pd.Series) else n >= thr
        return sd.where(ok)

    s_long = sigma_on(int(a["window_sessions"]), int(a["min_obs"]))
    s_short = sigma_on(int(a["fallback_window"]), int(a["fallback_min_obs"]))
    sigma = _annualize(s_long.where(s_long.notna(), s_short), annualize)
    return (float(a["sign"]) * sigma).where(p.notna())


def amihud_signal(panels: Panels, window: int = 63, min_obs: int = 10,
                  params: Mapping[str, Any] | None = None) -> pd.DataFrame:
    """Illiquidité d'Amihud en log (signal de recherche §3.3, poids nul).

    ``log(ILLIQ_63)`` avec :func:`amihud_illiquidity` (|r| d'échange à échange par
    million de FCFA échangé). Orientation : valeur élevée = titre **illiquide**.
    """
    a = _merge(params, window=window, min_obs=min_obs)
    illiq = amihud_illiquidity(panels, window=int(a["window"]), min_obs=int(a["min_obs"]))
    return np.log(illiq.where(illiq > 0))


# ---------------------------------------------------------------------------
# Value : EP et DY
# ---------------------------------------------------------------------------


def _resolve_eps_overrides(eps_override: Mapping[str, Any] | None) -> dict[str, EpsOverride]:
    """Normalise les surcharges : ``EpsOverride``, nombre, ``(eps, known_from[, valid_until])``
    ou ``{"eps": …, "known_from": …}``. Un nombre seul reprend la date du tableau par
    défaut (:data:`EPS_OVERRIDES_V1`) si le symbole y figure, sinon s'applique à toutes
    les dates (à réserver à une coupe courante)."""
    if eps_override is None:
        return dict(EPS_OVERRIDES_V1)
    out: dict[str, EpsOverride] = {}
    for sym, v in eps_override.items():
        default = EPS_OVERRIDES_V1.get(sym)
        if isinstance(v, EpsOverride):
            out[sym] = v
        elif isinstance(v, Mapping):
            out[sym] = EpsOverride(float(v["eps"]), v.get("known_from", default.known_from if default else None),
                                   v.get("valid_until"), str(v.get("source", "")))
        elif isinstance(v, (tuple, list)):
            out[sym] = EpsOverride(float(v[0]), v[1] if len(v) > 1 else None, v[2] if len(v) > 2 else None)
        else:
            out[sym] = EpsOverride(float(v), default.known_from if default else None,
                                   default.valid_until if default else None, default.source if default else "")
    return out


def per_v1(
    panels: Panels,
    eps_override: Mapping[str, Any] | None = None,
    publication_lag_sessions: int = FUNDAMENTALS_LAG_SESSIONS,
    per_pit: pd.DataFrame | None = None,
    split_factor: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """PER utilisé par la stratégie v1 : PER du BOC avec surcharges point-in-time.

    * ``per_pit`` (facultatif) : PER recalculé ``capitalisation / RN part du groupe``
      (table des fondamentaux, §3.2), prioritaire là où il est renseigné ;
    * surcharges de BPA (:data:`EPS_OVERRIDES_V1` par défaut : ETIT 10,00 ; ORGT 264) :
      ``PER = cours brut / BPA`` à partir de la date effective du document.
    """
    per = _numeric(panels, "per")
    if per_pit is not None:
        _check_index(per_pit, "per_pit")
        pit = per_pit.reindex(index=per.index, columns=per.columns).astype(float)
        per = pit.where(pit.notna(), per)
    overrides = {s: o for s, o in _resolve_eps_overrides(eps_override).items() if s in per.columns}
    if not overrides:
        return per
    if not any(panels.get(k) is not None for k in ("close", "close_adj")):
        raise KeyError("per_v1 : un cours ('close' brut ou 'close_adj') est requis pour les surcharges de BPA")
    price = _raw_close(panels, like=per, split_factor=split_factor)
    per = per.copy()
    for sym, ov in overrides.items():
        if sym not in per.columns or not np.isfinite(ov.eps) or ov.eps == 0:
            continue
        lo = _effective_row(per.index, ov.known_from, publication_lag_sessions)
        hi = _end_row(per.index, ov.valid_until)
        if lo >= hi:
            continue
        j = per.columns.get_loc(sym)
        px = price.iloc[lo:hi, j]
        per.iloc[lo:hi, j] = (px / ov.eps).where(px.notna()).to_numpy(dtype=float)
    return per


def ep_signal(
    panels: Panels,
    eps_override: Mapping[str, Any] | None = None,
    publication_lag_sessions: int = FUNDAMENTALS_LAG_SESSIONS,
    missing_per_as_loss: bool = False,
    per_pit: pd.DataFrame | None = None,
    split_factor: pd.DataFrame | None = None,
    params: Mapping[str, Any] | None = None,
) -> pd.DataFrame:
    """Rendement bénéficiaire EP (§3.2, poids 0,15 dans A).

    ``ep = 1 / PER`` si ``PER > 0`` ; si ``PER <= 0``, ``ep = 0`` : valeur inférieure à
    tous les ``1/PER`` positifs, donc **rang minimal** dans la coupe (ex aequo entre
    eux). PER = :func:`per_v1` (PER du BOC et surcharges de BPA point-in-time,
    ETIT 10,00 FCFA soit ``ep = 10/57`` au 20/11/2026 ; ORGT 264).

    PER manquant : NaN (z = 0, neutre, §3.1.6). Le BOC laisse le PER vide pour les
    sociétés en perte ; ``missing_per_as_loss=True`` les place au rang minimal
    (variante non pré-enregistrée, désactivée par défaut).

    ``params`` : clés ``eps_override``, ``publication_lag_sessions`` (alias
    ``fundamentals_fallback_lag_sessions``), ``missing_per_as_loss``.
    """
    a = _merge(params, {"fundamentals_fallback_lag_sessions": "publication_lag_sessions"},
               eps_override=eps_override, publication_lag_sessions=publication_lag_sessions,
               missing_per_as_loss=missing_per_as_loss)
    per = per_v1(panels, a["eps_override"], int(a["publication_lag_sessions"]), per_pit, split_factor)
    ep = (1.0 / per).where(per > 0)
    ep = ep.mask(per <= 0, 0.0)
    if any(panels.get(k) is not None for k in ("close_adj", "tr_index", "close")):
        listed = _grid(panels).reindex(index=ep.index, columns=ep.columns).notna()
        if a["missing_per_as_loss"]:
            ep = ep.mask(per.isna() & listed, 0.0)
        ep = ep.where(listed)
    return ep


def _add_months_days(days: np.ndarray, months: int) -> np.ndarray:
    """Jours (depuis 1970, NaN possible) + ``months`` mois calendaires (``pd.DateOffset``)."""
    out = np.full(days.shape, np.nan)
    ok = np.isfinite(days)
    if ok.any():
        uniq, inv = np.unique(days[ok], return_inverse=True)
        base = pd.DatetimeIndex(pd.to_datetime(uniq.astype(np.int64), unit="D"))
        shifted = base + pd.DateOffset(months=int(months))
        out[ok] = shifted.to_numpy(dtype="datetime64[D]").astype(np.int64).astype(float)[inv]
    return out


def _dividend_frames(panels: Panels, grid: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Dernier dividende connu (montant brut BOC, date de paiement en jours) et apparitions.

    Lignes valides : date et montant ``> 0`` renseignés ; le dernier couple valide est
    reporté vers l'avant (information déjà publiée). Une **apparition** est la ligne où
    le couple (date, montant) affiché apparaît pour la première fois.
    """
    d = _raw(panels, "last_div_date")
    d_days = pd.DataFrame(_day_numbers(_datetime_array(d)), index=d.index, columns=d.columns)
    d_days = d_days.reindex(index=grid.index, columns=grid.columns)
    amount = _numeric(panels, "last_div_net", like=grid)
    valid = d_days.notna() & amount.gt(0)
    dv, av = d_days.where(valid).ffill(), amount.where(valid).ffill()
    appear = dv.notna() & ((dv != dv.shift(1)) | (av != av.shift(1)))
    return av, dv, appear


def _split_ratio_since(f: pd.DataFrame | None, appear: pd.DataFrame) -> np.ndarray:
    """``f_t / f_a`` (convention du store) entre la ligne d'apparition ``a`` et ``t``."""
    if f is None:
        return np.ones(appear.shape)
    pos = _last_true_row(appear.to_numpy(dtype=bool))
    fa = _take_rows(f.to_numpy(dtype=float), pos)
    with np.errstate(invalid="ignore", divide="ignore"):
        ratio = f.to_numpy(dtype=float) / fa
    return np.where(np.isfinite(ratio) & (ratio > 0), ratio, 1.0)


def dy_signal_details(
    panels: Panels,
    max_age_months: int = 15,
    cap: float = 0.15,
    exclude_exceptional: bool = True,
    zero_if_no_dividend_voted: bool = True,
    source: Literal["auto", "computed", "boc"] = "auto",
    announced_absences: Iterable[DividendAbsence] | None = None,
    exceptional_dividends: Iterable[ExceptionalDividend] | None = None,
    publication_lag_sessions: int = FUNDAMENTALS_LAG_SESSIONS,
    agm_dividends: pd.DataFrame | None = None,
    split_factor: pd.DataFrame | None = None,
    params: Mapping[str, Any] | None = None,
) -> dict[str, pd.DataFrame]:
    """Rendement net du dividende DY (§3.2, poids 0,20 dans A), avec son diagnostic.

    **Repli v1** (les AGO ne sont pas encore collectées), cellule par cellule :

    1. dernier dividende net connu en ``t`` (``last_div_net``, ``last_div_date`` du
       BOC) ; aucun dividende connu pour un titre coté : DY = 0 ;
    2. rendement brut ``y`` : ``source="computed"`` : ``D × (f_t / f_a) / C_t`` (C brut,
       montant ramené à la base de titres de ``t`` si une division est survenue depuis
       l'apparition ``a`` du montant : SLBC 2024 affichait 36,9 %) ; ``"boc"`` :
       ``net_yield_pct / 100`` tel que publié ; ``"auto"`` (défaut) : calculé si possible,
       sinon BOC ;
    3. part exceptionnelle exclue (:data:`EXCEPTIONAL_DIVIDENDS_V1`, FTSC 2025) ;
    4. garde-fou : DY = 0 si le dernier paiement a plus de ``max_age_months`` mois ;
    5. absences annoncées (:data:`ANNOUNCED_NO_DIVIDEND_V1`) : DY = 0 dès la date
       effective (``publication_lag_sessions`` séances après le document) ;
    6. plafond ``cap`` (15 %) avec un drapeau au-delà.

    **Définition principale** (si ``agm_dividends`` est fourni : colonnes ``symbol,
    fiscal_year, known_from, dps_net_ordinary`` et facultativement ``payment_date``) :
    pour chaque titre de la table, DY = DPS net ordinaire du dernier exercice dont
    l'AGO est connue en ``t`` / cours (0 si l'AGO n'a voté aucun dividende), garde-fou
    et plafond inchangés ; les cellules antérieures à la première AGO connue
    retombent sur le repli v1.

    Returns
    -------
    dict
        ``dy`` (signal), ``dy_raw`` (avant plafond), ``flag_cap`` (DY brut > ``cap``),
        ``reason`` (``""``, ``aucun_dividende``, ``perime``, ``absence_annoncee``,
        ``ago_sans_dividende``, ``plafonne``).
    """
    a = _merge(params, max_age_months=max_age_months, cap=cap, exclude_exceptional=exclude_exceptional,
               zero_if_no_dividend_voted=zero_if_no_dividend_voted, source=source,
               publication_lag_sessions=publication_lag_sessions)
    if a["source"] not in ("auto", "computed", "boc"):
        raise ValueError("source doit valoir 'auto', 'computed' ou 'boc'")
    grid = _grid(panels)
    listed = _price(panels, "close_adj" if panels.get("close_adj") is not None else
                    ("tr_index" if panels.get("tr_index") is not None else "close")).reindex_like(grid).notna()
    av, dv, appear = _dividend_frames(panels, grid)
    T, N = grid.shape
    idx_days = _index_days(pd.DatetimeIndex(grid.index))
    f = split_factor_panel(panels, split_factor, like=grid)
    ratio = _split_ratio_since(f, appear)
    has_price = panels.get("close") is not None or panels.get("close_adj") is not None
    y_comp = np.full((T, N), np.nan)
    if has_price:
        px = _raw_close(panels, like=grid, split_factor=split_factor).to_numpy(dtype=float)
        with np.errstate(invalid="ignore", divide="ignore"):
            y_comp = av.to_numpy(dtype=float) * ratio / px
    y_boc = np.full((T, N), np.nan)
    if panels.get("net_yield_pct") is not None:
        y_boc = (_numeric(panels, "net_yield_pct", like=grid) / 100.0).to_numpy(dtype=float)
        y_boc = np.where(y_boc >= 0, y_boc, np.nan)
    if a["source"] == "computed":
        y = y_comp
    elif a["source"] == "boc":
        y = y_boc
    else:
        y = np.where(np.isfinite(y_comp), y_comp, y_boc)
    y = np.array(y, dtype=float)
    pay = dv.to_numpy(dtype=float)
    amt = av.to_numpy(dtype=float)
    has_div = np.isfinite(pay)
    reason = np.full((T, N), "", dtype=object)
    cols = {s: j for j, s in enumerate(grid.columns)}

    if a["exclude_exceptional"]:
        for ex in EXCEPTIONAL_DIVIDENDS_V1 if exceptional_dividends is None else exceptional_dividends:
            j = cols.get(ex.symbol)
            if j is None or ex.total_net <= 0:
                continue
            pday = float(_index_days(pd.DatetimeIndex([pd.Timestamp(ex.payment_date)]))[0])
            hit = (pay[:, j] == pday) & (np.abs(amt[:, j] - ex.total_net) <= max(0.5, 0.01 * ex.total_net))
            y[hit, j] *= max(0.0, 1.0 - ex.exceptional_net / ex.total_net)

    lst = listed.to_numpy(dtype=bool)
    none_known = lst & ~has_div
    y[none_known] = 0.0
    reason[none_known] = "aucun_dividende"
    stale = has_div & (idx_days[:, None] > _add_months_days(pay, int(a["max_age_months"])))
    y[stale] = 0.0
    reason[stale] = "perime"
    if a["zero_if_no_dividend_voted"]:
        years = (np.where(has_div, pay, 0.0).astype(np.int64).astype("datetime64[D]")
                 .astype("datetime64[Y]").astype(np.int64) + 1970)
        for ab in ANNOUNCED_NO_DIVIDEND_V1 if announced_absences is None else announced_absences:
            j = cols.get(ab.symbol)
            if j is None:
                continue
            lo = _effective_row(pd.DatetimeIndex(grid.index), ab.known_from, int(a["publication_lag_sessions"]))
            hit = np.zeros(T, dtype=bool)
            hit[lo:] = True
            hit &= has_div[:, j] & (years[:, j] <= int(ab.fiscal_year))
            y[hit, j] = 0.0
            reason[hit, j] = "absence_annoncee"

    if agm_dividends is not None and len(agm_dividends):
        _apply_agm_dividends(panels, grid, agm_dividends, y, reason, f, int(a["max_age_months"]),
                             int(a["publication_lag_sessions"]), split_factor)

    y = np.where(lst, y, np.nan)
    dy_raw = pd.DataFrame(y, index=grid.index, columns=grid.columns)
    flag = dy_raw.gt(float(a["cap"]))
    reason[flag.to_numpy()] = "plafonne"
    dy = dy_raw.clip(upper=float(a["cap"]))
    return {"dy": dy, "dy_raw": dy_raw, "flag_cap": flag,
            "reason": pd.DataFrame(reason, index=grid.index, columns=grid.columns)}


def _apply_agm_dividends(panels: Panels, grid: pd.DataFrame, table: pd.DataFrame, y: np.ndarray,
                         reason: np.ndarray, f: pd.DataFrame | None, max_age_months: int,
                         lag: int, split_factor: pd.DataFrame | None) -> None:
    """Définition principale de DY (AGO connues) : écrit en place dans ``y`` et ``reason``."""
    need = {"symbol", "fiscal_year", "known_from", "dps_net_ordinary"}
    if not need <= set(table.columns):
        raise KeyError(f"agm_dividends : colonnes requises {sorted(need)}")
    index = pd.DatetimeIndex(grid.index)
    idx_days = _index_days(index)
    px = _raw_close(panels, like=grid, split_factor=split_factor).to_numpy(dtype=float)
    fv = None if f is None else f.to_numpy(dtype=float)
    cols = {s: j for j, s in enumerate(grid.columns)}
    for sym, g in table.groupby("symbol", sort=False):
        j = cols.get(sym)
        if j is None:
            continue
        g = g.assign(_start=[_effective_row(index, k, lag) for k in g["known_from"]])
        g = g.sort_values(["_start", "fiscal_year"])
        starts = g["_start"].to_numpy(dtype=int)
        for k, row in enumerate(g.itertuples(index=False)):
            lo = int(starts[k])
            hi = int(starts[k + 1]) if k + 1 < len(starts) else len(index)
            if lo >= hi or lo >= len(index):
                continue
            dps = float(row.dps_net_ordinary)
            rows = np.arange(lo, hi)
            if dps <= 0:
                y[rows, j] = 0.0
                reason[rows, j] = "ago_sans_dividende"
                continue
            scale = np.ones(len(rows)) if fv is None else fv[rows, j] / fv[lo, j]
            with np.errstate(invalid="ignore", divide="ignore"):
                y[rows, j] = dps * scale / px[rows, j]
            reason[rows, j] = ""
            pdate = _ts(getattr(row, "payment_date", None))
            if pdate is not None:
                pday = float(_index_days(pd.DatetimeIndex([pdate]))[0])
                limit = _add_months_days(np.array([pday]), max_age_months)[0]
                old = rows[idx_days[rows] > limit]
                y[old, j] = 0.0
                reason[old, j] = "perime"


def dy_signal(panels: Panels, params: Mapping[str, Any] | None = None, **kwargs: Any) -> pd.DataFrame:
    """Signal DY (§3.2) : ``dy_signal_details(...)["dy"]`` (voir :func:`dy_signal_details`).

    Valeurs de non-régression (§12.3 n° 5) : DY(FTSC, 20/11/2026) = 0 (exercice 2025
    sans dividende) ; DY(FTSC, 31/03/2026) > 0, plafonné à 15 % avec drapeau.
    """
    return dy_signal_details(panels, params=params, **kwargs)["dy"]


# ---------------------------------------------------------------------------
# Qualité (proxy v1)
# ---------------------------------------------------------------------------


def dividend_years(panels: Panels, window_years: int = 5) -> pd.DataFrame:
    """Nombre d'années de paiement d'un dividende sur les ``window_years`` dernières années.

    À la date ``t`` : années civiles distinctes des paiements ``> 0`` connus en ``t``
    (un nouveau paiement est détecté quand ``last_div_date`` dépasse toutes les dates
    déjà vues : une date qui recule est une coquille) dont la date de paiement est
    ``> t - window_years ans`` ; plafonné à ``window_years``. Un dividende d'un exercice
    est payé l'année suivante : la fenêtre glissante couvre les ``window_years``
    derniers exercices. Titre coté sans dividende : 0 ; non coté : NaN.
    L'historique commence avec l'échantillon (2017).
    """
    if window_years < 1:
        raise ValueError("window_years doit être >= 1")
    grid = _grid(panels)
    d = _raw(panels, "last_div_date")
    d_days = pd.DataFrame(_day_numbers(_datetime_array(d)), index=d.index, columns=d.columns)
    d_days = d_days.reindex(index=grid.index, columns=grid.columns).to_numpy(dtype=float)
    amount = _numeric(panels, "last_div_net", like=grid).to_numpy(dtype=float)
    idx_days = _index_days(pd.DatetimeIndex(grid.index))
    T, N = grid.shape
    out = np.zeros((T, N))
    for j in range(N):
        seen = -np.inf
        by_year: dict[int, np.ndarray] = {}
        for r in np.flatnonzero(np.isfinite(d_days[:, j]) & (amount[:, j] > 0)):
            pay = d_days[r, j]
            if pay <= seen:
                continue
            seen = pay
            end_day = _add_months_days(np.array([pay]), 12 * window_years)[0]
            end = int(np.searchsorted(idx_days, end_day, side="left"))
            year = int(np.datetime64(int(pay), "D").astype("datetime64[Y]").astype(np.int64)) + 1970
            act = by_year.setdefault(year, np.zeros(T, dtype=bool))
            act[r:max(end, r)] = True
        for act in by_year.values():
            out[:, j] += act
    res = pd.DataFrame(np.minimum(out, window_years), index=grid.index, columns=grid.columns)
    return res.where(grid.notna())


def quality_proxy(
    panels: Panels,
    dividend_years_weight: float = 0.5,
    per_sane_range: tuple[float, float] = (3.0, 40.0),
    per_sane_weight: float = 0.5,
    window_years: int = 5,
    universe: pd.DataFrame | None = None,
    eps_override: Mapping[str, Any] | None = None,
    publication_lag_sessions: int = FUNDAMENTALS_LAG_SESSIONS,
    per_pit: pd.DataFrame | None = None,
    split_factor: pd.DataFrame | None = None,
    params: Mapping[str, Any] | None = None,
) -> pd.DataFrame:
    """Qualité v1 (proxy, §3.2, poids 0,10 dans A, niveau de preuve P3).

    ``q = ½ · rang(années avec dividende sur 5 exercices) + ½ · 1[3 <= PER <= 40]``

    ``rang`` = rang transversal normalisé ``(r - 1) / (N - 1)`` dans ``[0, 1]`` (ex
    aequo : rang moyen ; ``N = 1`` : 0,5) parmi les titres de ``universe`` (masque
    booléen date × symbole ; défaut : titres cotés). PER = :func:`per_v1` (surcharges
    de BPA comprises) ; PER manquant : indicatrice nulle. ``params`` : clés
    ``dividend_years_of_5`` (alias du poids), ``per_sane_range``, ``per_sane_weight``.
    """
    a = _merge(params, {"dividend_years_of_5": "dividend_years_weight"},
               dividend_years_weight=dividend_years_weight, per_sane_range=per_sane_range,
               per_sane_weight=per_sane_weight, window_years=window_years)
    years = dividend_years(panels, int(a["window_years"]))
    per = per_v1(panels, eps_override, publication_lag_sessions, per_pit, split_factor)
    per = per.reindex(index=years.index, columns=years.columns)
    member = years.notna()
    if universe is not None:
        member &= _bool_panel(universe, years)
    yv = years.where(member)
    rk = yv.rank(axis=1, method="average")
    n = yv.notna().sum(axis=1)
    pct = rk.sub(1.0).div((n - 1).where(n > 1), axis=0)
    single = np.broadcast_to((n == 1).to_numpy()[:, None], member.shape)
    pct = pct.mask(member & pd.DataFrame(single, index=member.index, columns=member.columns), 0.5)
    lo, hi = float(a["per_sane_range"][0]), float(a["per_sane_range"][1])
    sane = ((per >= lo) & (per <= hi)).astype(float)
    q = float(a["dividend_years_weight"]) * pct + float(a["per_sane_weight"]) * sane
    return q.where(member)


# ---------------------------------------------------------------------------
# Modulateurs du bloc momentum (§3.2, pré-enregistrés dans A)
# ---------------------------------------------------------------------------


def _month_end_rows(index: pd.DatetimeIndex) -> np.ndarray:
    """Positions de la dernière séance de chaque mois civil présent dans l'index."""
    if not len(index):
        return np.zeros(0, dtype=int)
    per = index.to_period("M")
    last = np.r_[per[1:] != per[:-1], True]
    return np.flatnonzero(last)


def momentum_spread_returns(
    panels: Panels,
    mom: pd.DataFrame | None = None,
    universe: pd.DataFrame | None = None,
    formation: Literal["monthly", "daily"] = "monthly",
    lag_sessions: int = 1,
    n_groups: int = 3,
    price: str = "tr_index",
    gap_days: int = MULTI_SESSION_GAP_DAYS,
    exclude_windows: Iterable[tuple[str, str]] = EXCLUDED_STAT_WINDOWS,
) -> pd.Series:
    """Rendement quotidien ``spread_mom`` : tiers supérieur de MOM6_1 − panier de l'univers.

    À chaque date de formation ``s`` (dernière séance du mois, ou chaque séance) :
    univers = titres de ``universe`` (défaut : tous) dont le momentum est défini ;
    tiers supérieur = titres dont ``ceil(n · rang / N) = n``. Les deux paniers,
    équipondérés (moyenne des rendements du jour), sont détenus de la clôture de
    ``s + lag_sessions`` à la formation suivante : le rendement du jour ``d`` utilise
    la formation ``s <= d - lag_sessions - 1``. Rendements TR calendaires valides
    seulement (:func:`valid_return_mask`).

    **Attention (échantillon vierge)** : cette série est la performance d'un facteur.
    Ne l'évaluer que sur des données de l'échantillon autorisé (fournir des panels
    déjà tronqués à S0 ou des données synthétiques).
    """
    if n_groups < 2 or lag_sessions < 0:
        raise ValueError("il faut n_groups >= 2 et lag_sessions >= 0")
    p = _price(panels, price)
    m = mom6_1(panels) if mom is None else mom.reindex(index=p.index, columns=p.columns).astype(float)
    r = (p / p.shift(1) - 1.0).where(
        valid_return_mask(panels, like=p, price=price, gap_days=gap_days, exclude_windows=exclude_windows))
    member = m.notna()
    if universe is not None:
        member &= _bool_panel(universe, p)
    pct = m.where(member).rank(axis=1, method="average", pct=True)
    top = np.ceil(pct * n_groups).eq(n_groups) & member
    if formation == "monthly":
        rows = _month_end_rows(pd.DatetimeIndex(p.index))
    elif formation == "daily":
        rows = np.arange(len(p))
    else:
        raise ValueError("formation doit valoir 'monthly' ou 'daily'")

    def held(mask: pd.DataFrame) -> pd.DataFrame:
        f = pd.DataFrame(np.nan, index=p.index, columns=p.columns)
        f.iloc[rows] = mask.iloc[rows].astype(float).to_numpy()
        return f.ffill().shift(lag_sessions + 1).eq(1.0)

    ret_top = r.where(held(top)).mean(axis=1)
    ret_all = r.where(held(member)).mean(axis=1)
    return (ret_top - ret_all).rename("spread_mom")


def _session_array(sess: np.ndarray | pd.Series | None, index: pd.Index) -> np.ndarray | None:
    """Numéros de séance alignés sur ``index`` (``None`` si absents, incomplets ou non croissants)."""
    if sess is None:
        return None
    if isinstance(sess, pd.Series):
        v = pd.to_numeric(sess[~sess.index.duplicated(keep="last")], errors="coerce").reindex(index)
        if v.isna().any():
            return None
        arr = v.to_numpy(dtype=float)
    else:
        arr = np.asarray(sess, dtype=float)
        if len(arr) != len(index):
            return None
    if not len(arr) or not np.isfinite(arr).all() or (len(arr) > 1 and np.any(np.diff(arr) <= 0)):
        return None
    return arr.astype(np.int64)


def vol_scaling(
    spread: pd.Series,
    window_sessions: int = 126,
    min_obs: int = 100,
    min_history_months: int = 24,
    floor: float = 0.5,
    cap: float = 1.0,
    history_start: Any = None,
    params: Mapping[str, Any] | None = None,
    sess: np.ndarray | pd.Series | None = None,
    obs_floor: int = SIGNAL_MIN_OBS_FLOOR,
) -> pd.Series:
    """Dosage du momentum par sa volatilité (Barroso & Santa-Clara 2015, adapté ; §3.2).

    ``m_t = clip(σ_cible,t / σ̂_126,t, floor, cap)`` où ``σ̂_126`` est l'écart-type
    (ddof = 1) de ``spread`` (:func:`momentum_spread_returns`) sur 126 séances (au
    moins ``min_obs`` valeurs) et ``σ_cible,t`` la médiane **expansive** des ``σ̂``
    jusqu'à ``t``. ``m_t = 1`` tant que ``σ̂`` n'a pas ``min_history_months`` mois
    d'historique (comptés depuis sa première valeur), ou si ``σ̂`` est indéfini.
    Le poids du momentum devient ``0,35 × m_t`` ; le poids libéré est réparti au
    prorata sur les autres blocs (``scoring.modulate_weights``).

    ``history_start`` : les valeurs de ``spread`` antérieures sont ignorées (permet de
    n'utiliser que l'échantillon autorisé). Clés de ``params`` : ``window_sessions``,
    ``min_obs``, ``min_history_months``, ``floor``, ``cap`` (``target`` ignorée : la
    seule cible prévue est la médiane expansive).

    ``sess`` (additif v1.1, D1) : numéros de séance des dates de ``spread`` (tableau aligné ou
    ``Series`` indexée par date). La fenêtre de 126 est alors comptée en **séances** et le
    seuil ``min_obs`` ramené au prorata des BOC disponibles, plancher ``obs_floor`` (40).
    """
    a = _merge(params, window_sessions=window_sessions, min_obs=min_obs,
               min_history_months=min_history_months, floor=floor, cap=cap)
    if not 0 < float(a["floor"]) <= float(a["cap"]):
        raise ValueError("il faut 0 < floor <= cap")
    s = pd.to_numeric(spread, errors="coerce").astype(float)
    if not isinstance(s.index, pd.DatetimeIndex) or not s.index.is_monotonic_increasing:
        raise ValueError("spread doit être indexé par un DatetimeIndex trié")
    if history_start is not None:
        s = s.where(s.index >= pd.Timestamp(history_start))
    _check_window(int(a["window_sessions"]), int(a["min_obs"]))
    L, m = int(a["window_sessions"]), int(a["min_obs"])
    grid = _session_array(sess, s.index)
    if grid is None:
        sig = s.rolling(L, min_periods=m).std(ddof=1)
    else:
        frame = s.to_frame("x")
        sd = on_session_grid(frame, grid, lambda x: x.rolling(L, min_periods=min(2, m)).std(ddof=1))["x"]
        n = on_session_grid(frame, grid, lambda x: x.rolling(L, min_periods=1).count())["x"]
        thr = pd.Series(prorata_min_obs(m, L, missing_sessions_in_window(grid, L), obs_floor), index=s.index)
        sig = sd.where(n >= thr)
    target = sig.expanding(min_periods=1).median()
    first = sig.first_valid_index()
    out = pd.Series(1.0, index=s.index, name="vol_scaling")
    if first is None:
        return out
    ready = s.index >= first + pd.DateOffset(months=int(a["min_history_months"]))
    ok = ready & sig.gt(0).to_numpy() & np.isfinite(sig.to_numpy())
    m = (target / sig).clip(lower=float(a["floor"]), upper=float(a["cap"]))
    out[ok] = m[ok]
    return out


def crash_filter(
    market_tr: pd.Series,
    bear_lookback_months: int = 24,
    vol_window_sessions: int = 63,
    vol_min_obs: int = 50,
    vol_percentile: float = 80.0,
    multiplier: float = 0.5,
    duration_months: int = 3,
    min_history_sessions: int = 252,
    gap_days: int = MULTI_SESSION_GAP_DAYS,
    exclude_windows: Iterable[tuple[str, str]] = EXCLUDED_STAT_WINDOWS,
    history_start: Any = None,
    params: Mapping[str, Any] | None = None,
    sess: np.ndarray | pd.Series | None = None,
    obs_floor: int = SIGNAL_MIN_OBS_FLOOR,
) -> pd.Series:
    """Filtre de crash du momentum (inspiré de Daniel & Moskowitz 2016 ; §3.2).

    Déclenchement en ``t`` si **(i)** le TR de marché (Composite TR, reconstruit avant
    le 02/01/2025) est en baisse sur ``bear_lookback_months`` mois :
    ``TR_t / TR_{t-24 mois} - 1 < 0`` (niveau à la dernière séance ``<= t - 24 mois`` ;
    faux tant que l'historique est plus court) **et (ii)** sa volatilité quotidienne
    sur ``vol_window_sessions`` séances (au moins ``vol_min_obs`` rendements ;
    rendements sur un trou > ``gap_days`` jours et fenêtre 2021 exclus) dépasse le
    ``vol_percentile``-ième centile de son historique expansif (valeurs ``<= t``, au
    moins ``min_history_sessions`` valeurs). Le multiplicateur vaut alors
    ``multiplier`` (0,5) pour les dates ``d`` telles que ``t <= d < t + 3 mois`` (un
    nouveau déclenchement prolonge la durée), 1 sinon. Choix du projet, non validé
    (niveau B) ; aucune mesure de performance ici.

    ``sess`` (additif v1.1, D1) : numéros de séance des dates de ``market_tr`` (``Series``
    indexée par date ou tableau aligné) : la fenêtre de 63 est comptée en séances et le
    seuil de 50 ramené au prorata des BOC disponibles, plancher ``obs_floor`` (40). Sans
    numéro pour une date, la fenêtre reste comptée en lignes (signalé par l'appelant).
    """
    a = _merge(params, bear_lookback_months=bear_lookback_months, vol_window_sessions=vol_window_sessions,
               vol_min_obs=vol_min_obs, vol_percentile=vol_percentile, multiplier=multiplier,
               duration_months=duration_months, min_history_sessions=min_history_sessions)
    lvl = pd.to_numeric(market_tr, errors="coerce").astype(float)
    if not isinstance(lvl.index, pd.DatetimeIndex) or not lvl.index.is_monotonic_increasing:
        raise ValueError("market_tr doit être indexé par un DatetimeIndex trié")
    if history_start is not None:
        lvl = lvl.where(lvl.index >= pd.Timestamp(history_start))
    lvl = lvl.where(lvl > 0)
    idx = pd.DatetimeIndex(lvl.index)
    obs = lvl.dropna()
    out = pd.Series(1.0, index=idx, name="crash_filter")
    if len(obs) < 2:
        return out
    # (i) marché baissier sur 24 mois
    back = idx - pd.DateOffset(months=int(a["bear_lookback_months"]))
    pos = obs.index.searchsorted(back, side="right") - 1
    past = np.where(pos >= 0, obs.to_numpy()[np.clip(pos, 0, None)], np.nan)
    bear = (lvl.to_numpy() / past - 1.0) < 0
    # (ii) volatilité sur 63 séances au-dessus du 80e centile expansif
    r = obs / obs.shift(1) - 1.0
    days = _index_days(pd.DatetimeIndex(obs.index))
    r[np.r_[False, np.diff(days) > gap_days]] = np.nan
    for lo, hi in exclude_windows:
        r[(r.index >= pd.Timestamp(lo)) & (r.index <= pd.Timestamp(hi))] = np.nan
    Lv, mv = int(a["vol_window_sessions"]), int(a["vol_min_obs"])
    grid = _session_array(sess, obs.index)
    if grid is None:
        vol = r.rolling(Lv, min_periods=mv).std(ddof=1)
    else:
        frame = r.to_frame("x")
        sd = on_session_grid(frame, grid, lambda x: x.rolling(Lv, min_periods=min(2, mv)).std(ddof=1))["x"]
        n = on_session_grid(frame, grid, lambda x: x.rolling(Lv, min_periods=1).count())["x"]
        thr = pd.Series(prorata_min_obs(mv, Lv, missing_sessions_in_window(grid, Lv), obs_floor), index=r.index)
        vol = sd.where(n >= thr)
    thr = vol.expanding(min_periods=int(a["min_history_sessions"])).quantile(float(a["vol_percentile"]) / 100.0)
    high = (vol > thr).reindex(idx, fill_value=False).to_numpy(dtype=bool)
    trig = bear & high
    if not trig.any():
        return out
    stamps = idx.to_numpy(dtype="datetime64[ns]")
    last = pd.Series(np.where(trig, stamps, np.datetime64("NaT", "ns")), index=idx).ffill()
    known = last.notna().to_numpy()
    end_days = _add_months_days(
        np.where(known, _day_numbers(last.to_numpy(dtype="datetime64[ns]")), np.nan), int(a["duration_months"]))
    active = known & (_index_days(idx) < end_days)
    out[active] = float(a["multiplier"])
    return out


def momentum_multiplier(*factors: pd.Series | float | None, index: pd.DatetimeIndex | None = None) -> pd.Series:
    """Produit des modulateurs du momentum (:func:`vol_scaling` × :func:`crash_filter`).

    Les séries sont alignées sur ``index`` (défaut : union des index) avec report vers
    l'avant ; une valeur manquante vaut 1 (aucune modulation).
    """
    series = [f for f in factors if isinstance(f, pd.Series)]
    if index is None:
        if not series:
            raise ValueError("fournir index ou au moins une série")
        index = series[0].index
        for s in series[1:]:
            index = index.union(s.index)
    out = pd.Series(1.0, index=index, name="momentum_multiplier")
    for f in factors:
        if f is None:
            continue
        if isinstance(f, pd.Series):
            s = pd.to_numeric(f, errors="coerce").astype(float)
            s = s.reindex(s.index.union(index)).ffill().reindex(index)
            out = out * s.fillna(1.0)
        else:
            out = out * float(f)
    return out


# ---------------------------------------------------------------------------
# Assemblage
# ---------------------------------------------------------------------------


def signal_blocks_v1(
    panels: Panels,
    universe: pd.DataFrame | None = None,
    include_research: bool = True,
    eps_override: Mapping[str, Any] | None = None,
    params: Mapping[str, Any] | None = None,
    split_factor: pd.DataFrame | None = None,
) -> dict[str, pd.DataFrame]:
    """Blocs bruts de la stratégie v1 : ``ep, dy, mom6_1, lowvol, quality_proxy`` (+ recherche).

    ``params`` : section ``signals`` du YAML (sous-dictionnaires ``ep``, ``dy``,
    ``mom6_1``, ``lowvol``, ``quality_proxy`` ; facultativement ``mom12_1``…) ;
    ``eps_override`` : ``data.eps_override``. Les signaux de recherche
    (:data:`RESEARCH_SIGNALS_V1`, poids nul sauf ``mom12_1`` dans la variante C) sont
    inclus si ``include_research``. Les blocs ne sont **pas** normalisés : voir
    ``scoring.composite_score``.
    """
    p = params or {}
    sub = lambda k: p.get(k) if isinstance(p.get(k), Mapping) else None
    eps = eps_override if eps_override is not None else (sub("ep") or {}).get("eps_override")
    out: dict[str, pd.DataFrame] = {
        "ep": ep_signal(panels, eps_override=eps, split_factor=split_factor, params=sub("ep")),
        "dy": dy_signal(panels, split_factor=split_factor, params=sub("dy")),
        "mom6_1": mom6_1(panels, params=sub("mom6_1")),
        "lowvol": lowvol(panels, params=sub("lowvol")),
        "quality_proxy": quality_proxy(panels, universe=universe, eps_override=eps,
                                       split_factor=split_factor, params=sub("quality_proxy")),
    }
    if include_research:
        out["mom3_1"] = mom3_1(panels, params=sub("mom3_1"))
        out["mom6_0"] = mom6_0(panels, params=sub("mom6_0"))
        out["mom12_1"] = mom12_1(panels, params=sub("mom12_1"))
        out["mom12_7"] = mom12_7(panels, params=sub("mom12_7"))
        if panels.get("value") is not None and any(panels.get(k) is not None for k in ("status", "volume")):
            out["amihud"] = amihud_signal(panels, params=sub("amihud"))
    return out


def panels_for_signals(equities: pd.DataFrame, adjusted: pd.DataFrame | None = None) -> dict[str, pd.DataFrame]:
    """Panels larges (convention de ce module) à partir de ``equities`` et ``adjusted_table``.

    ``close`` = clôture **brute** du BOC ; avec ``adjusted`` (``store.adjusted_table`` ou
    ``adjusted_prices.parquet``) : ``close_adj`` (= ``adj_close``), ``tr_index``,
    ``split_factor``, ``missing_sessions`` et ``multi_session`` s'il existe ; sans lui,
    ``close_adj = tr_index = close`` (aucun ajustement : à réserver aux tests).
    Également : ``volume, value, status, per, net_yield_pct, last_div_net,
    last_div_date, ref_price, change_pct, sector`` (si présents).
    """
    eq = equities.reset_index() if "symbol" not in equities.columns else equities.copy()
    eq["date"] = pd.to_datetime(eq["date"])
    eq = eq.drop_duplicates(["date", "symbol"], keep="last")
    out: dict[str, pd.DataFrame] = {}
    for c in ("close", "volume", "value", "status", "per", "net_yield_pct", "last_div_net",
              "last_div_date", "ref_price", "change_pct", "sector"):
        if c in eq.columns:
            out[c] = eq.pivot(index="date", columns="symbol", values=c).sort_index()
    grid = out["close"]
    if adjusted is not None:
        adj = adjusted.reset_index() if "symbol" not in adjusted.columns else adjusted.copy()
        adj["date"] = pd.to_datetime(adj["date"])
        adj = adj.drop_duplicates(["date", "symbol"], keep="last")
        for src, dst in (("adj_close", "close_adj"), ("tr_index", "tr_index"), ("split_factor", "split_factor"),
                         ("missing_sessions", "missing_sessions"), ("multi_session", "multi_session")):
            if src in adj.columns:
                out[dst] = adj.pivot(index="date", columns="symbol", values=src).reindex_like(grid)
    out.setdefault("close_adj", grid.astype(float))
    out.setdefault("tr_index", grid.astype(float))
    return out
