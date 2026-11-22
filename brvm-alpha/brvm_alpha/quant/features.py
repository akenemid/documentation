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

Références
----------
* Amihud, Y. (2002). Illiquidity and stock returns: cross-section and
  time-series effects. *Journal of Financial Markets*, 5(1), 31-56.
* Asness, C., Moskowitz, T. & Pedersen, L. (2013). Value and Momentum
  Everywhere. *Journal of Finance*, 68(3), 929-985.
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
from collections.abc import Callable, Mapping
from typing import Literal, TypeAlias

import numpy as np
import pandas as pd

from brvm_alpha.config import ExecutionModel

__all__ = [
    "MOMENTUM_PRESETS",
    "TRADING_DAYS",
    "Panels",
    "adjusted_volume",
    "amihud_illiquidity",
    "average_daily_value",
    "beta_dimson",
    "compute_features",
    "days_since_dividend",
    "distance_to_high",
    "dividend_growth",
    "dividend_stability",
    "dividend_yield",
    "downside_vol",
    "earnings_yield",
    "limit_hits",
    "listed_mask",
    "median_value_traded",
    "momentum",
    "momentum_preset",
    "past_return",
    "returns",
    "seasonality",
    "short_term_reversal",
    "split_factor_panel",
    "traded_mask",
    "turnover",
    "turnover_proxy",
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
