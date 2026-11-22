"""Grandeurs macro, pays et microstructure de la BRVM (spéc. §4.1, §5.2, §7.1 et §12.2).

* :func:`ref_govt_rate` : taux de référence des emprunts d'État déduit du BOC,
  ``100/PER_moyen − prime_BOC`` (légende du BOC du 22/02/2021), filtré et lissé
  **point-in-time** (médiane glissante sur 20 séances) ;
* :func:`country_crp` : prime de risque pays relative à la Côte d'Ivoire (table §4.1 ou
  formule ``1,5 × LS_c + (p_sév × 21 % + p_mod × 8 %)_c − (idem)_CI``) ; :func:`cost_of_equity` ;
* :func:`tick_size`, :func:`price_band`, :func:`price_band_frame` : pas de cotation et bornes
  de ±7,5 % (§7.1) ;
* :func:`ex_date_rule`, :func:`settlement_lag`, :func:`shift_sessions` : date de détachement
  et délai de règlement (J+3 jusqu'au 03/12/2025, J+2 ensuite, instruction 03-2025).

Les primes pays reposent sur des probabilités de choc **à dire d'expert** (hypothèses non
vérifiables, revue 05 §12) : ce ne sont pas des faits, et elles n'entrent pas dans le score A.
"""

from __future__ import annotations

import math
from collections import deque
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

from .. import reference

__all__ = [
    "CRP_TABLE_PCT",
    "JUMP_PROBABILITIES",
    "LOCAL_SPREAD_VS_CI_PP",
    "SETTLEMENT_SWITCH_DATE",
    "cost_of_equity",
    "country_crp",
    "ex_date_check",
    "ex_date_rule",
    "implied_govt_rate",
    "price_band",
    "price_band_frame",
    "ref_govt_rate",
    "session_index",
    "settlement_lag",
    "shift_sessions",
    "tick_size",
]

# ---------------------------------------------------------------------------
# Taux de référence des emprunts d'État (rf local)
# ---------------------------------------------------------------------------


def _market_frame(market: pd.DataFrame | str | Path) -> pd.DataFrame:
    if isinstance(market, (str, Path)):
        from ..data import store  # import tardif : évite une dépendance circulaire

        market = store.load_market(market)
    df = market
    if "date" in df.columns:
        df = df.set_index("date")
    df = df.sort_index()
    return df[~df.index.duplicated(keep="last")]


def implied_govt_rate(market: pd.DataFrame | str | Path) -> pd.Series:
    """Taux implicite **brut** du BOC, en points de % : ``100 / avg_per − risk_premium``."""
    df = _market_frame(market)
    per = pd.to_numeric(df["avg_per"], errors="coerce")
    prime = pd.to_numeric(df["risk_premium"], errors="coerce")
    raw = 100.0 / per.where(per > 0) - prime
    raw.name = "implied_rate_pct"
    return raw


def ref_govt_rate(
    market: pd.DataFrame | str | Path,
    *,
    window: int = 20,
    outlier_pp: float = 0.10,
    confirm_sessions: int = 5,
    plausible_pct: tuple[float, float] = (3.0, 9.0),
    max_stale_sessions: int = 20,
    unit: str = "decimal",
    detail: bool = False,
    asof: Any = None,
) -> pd.Series | pd.DataFrame | float:
    """Taux de référence des emprunts d'État (rf local), règle de la spéc. §4.1 et revue 05 §1.2.

    Calcul séquentiel, sans biais d'anticipation (la valeur en t n'utilise que les BOC
    publiés jusqu'à t) :

    1. taux brut ``100/PER − prime`` (:func:`implied_govt_rate`) ; une valeur hors de
       ``plausible_pct`` est **invalide** (filtre de plausibilité, choix de conception : il
       écarte la période incohérente du 29/04/2020 au 19/02/2021, 10,3-11,7 %, et les primes
       figées de fin 2017 et fin 2018) ;
    2. une valeur qui s'écarte de plus de ``outlier_pp`` point de la médiane en cours est
       ignorée (prime imprimée 0,00 ou 0,01 : 19/10, 23/10, 17/11/2026 ; 5,27 % le 13/07/2026) ;
    3. un changement de niveau n'est retenu qu'après ``confirm_sessions`` séances valides
       consécutives au nouveau niveau (à ``outlier_pp`` près) ; l'historique repart alors du
       nouveau niveau ;
    4. valeur publiée = médiane des ``window`` dernières valeurs retenues ; ``NaN`` avant le
       premier niveau confirmé, et quand la dernière valeur retenue a plus de
       ``max_stale_sessions`` séances (aucune donnée exploitable : ``ffill`` seulement si
       l'on accepte cette hypothèse).

    Conséquence de la règle : un changement est vu au plus tôt à la 5e séance au nouveau
    niveau. Le passage de 5,90 % à 5,75 % (05/01/2024) est confirmé le 11/01/2024 ; la valeur
    « 5,75 % le 08/01/2024 » citée par la revue 05 (§14.3 n° 7) exigerait de connaître le futur.

    ``unit="decimal"`` (défaut, 0,0575) ou ``"pct"`` (5,75). ``detail=True`` : DataFrame
    (``raw_pct``, ``status``, ``rate``). ``asof`` : valeur à cette date (dernière séance ≤ asof).
    """
    if unit not in ("decimal", "pct"):
        raise ValueError("unit doit valoir 'decimal' ou 'pct'")
    raw = implied_govt_rate(market)
    lo, hi = plausible_pct
    accepted: deque[float] = deque(maxlen=int(window))
    candidate: list[float] = []
    since_accept = math.inf
    out = np.full(len(raw), np.nan)
    status: list[str] = []
    for i, x in enumerate(raw.to_numpy(dtype=float)):
        since_accept += 1
        if not np.isfinite(x) or not lo <= x <= hi:
            st = "invalid"
        elif not accepted:
            if candidate and abs(x - float(np.median(candidate))) <= outlier_pp:
                candidate.append(x)
            else:
                candidate = [x]
            st = "pending"
            if len(candidate) >= confirm_sessions:
                accepted.extend(candidate[-window:])
                candidate = []
                since_accept = 0
                st = "established"
        else:
            med = float(np.median(accepted))
            if abs(x - med) <= outlier_pp:
                accepted.append(x)
                candidate = []
                since_accept = 0
                st = "accepted"
            else:
                if candidate and abs(x - float(np.median(candidate))) <= outlier_pp:
                    candidate.append(x)
                else:
                    candidate = [x]
                st = "outlier"
                if len(candidate) >= confirm_sessions:
                    accepted.clear()
                    accepted.extend(candidate[-window:])
                    candidate = []
                    since_accept = 0
                    st = "regime_change"
        if accepted and since_accept <= max_stale_sessions:
            out[i] = float(np.median(accepted))
        status.append(st)
    scale = 0.01 if unit == "decimal" else 1.0
    rate = pd.Series(out * scale, index=raw.index, name="ref_govt_rate")
    if asof is not None:
        r = rate.loc[: pd.Timestamp(asof)]
        return float(r.iloc[-1]) if len(r) else float("nan")
    if detail:
        return pd.DataFrame({"raw_pct": raw, "status": status, "rate": rate})
    return rate


# ---------------------------------------------------------------------------
# Prime de risque pays et coût des fonds propres
# ---------------------------------------------------------------------------

#: Spread local contre la courbe ivoirienne, en points de % (spéc. §4.1, revue 05 §6.2 ;
#: BJ et NE : émissions 2025). GW : aucune émission, 1,0 supposé (revue 05 §12.2).
LOCAL_SPREAD_VS_CI_PP: dict[str, float] = {
    "CI": 0.0, "BJ": 0.05, "ML": 0.57, "TG": 0.92, "NE": 0.95, "SN": 0.97, "BF": 1.07, "GW": 1.0,
}
#: Probabilités annuelles (p_sév, p_mod) de choc politique, **dire d'expert** (revue 05 §12.2).
JUMP_PROBABILITIES: dict[str, tuple[float, float]] = {
    "CI": (0.02, 0.10), "BJ": (0.04, 0.15), "TG": (0.04, 0.15), "SN": (0.02, 0.30),
    "ML": (0.10, 0.30), "NE": (0.12, 0.30), "BF": (0.12, 0.30), "GW": (0.15, 0.30),
}
#: Table de la spéc. §4.1 (CRP relative à la CI, en %) ; GW d'après la revue 05 §12.2 ;
#: hors UEMOA (Guinée, Sierra Leone, ETIT) : 4,0 % forfaitaire, risque de change compris.
CRP_TABLE_PCT: dict[str, float] = {
    "CI": 0.0, "BJ": 0.9, "TG": 2.2, "SN": 3.05, "ML": 4.1, "NE": 5.1, "BF": 5.3, "GW": 5.8,
    "HORS_UEMOA": 4.0,
}
#: Pertes en cas de choc (revue 05 §12.1) : sévère 21 % (stress 26 %), modéré 8 %.
LOSS_SEVERE = 0.21
LOSS_MODERATE = 0.08
#: Multiplicateur obligations -> actions (convention de Damodaran, valeur actuelle NON VÉRIFIÉE).
EQUITY_BOND_MULTIPLIER = 1.5
#: Prime de risque actions du marché (moyenne 2021-2025 de la prime BOC ≈ 4,1 %).
ERP_BRVM = 0.04


def _crp_key(country: str) -> str:
    c = country.upper().strip()
    if c in reference.NON_UEMOA_ZONES or c in ("HORS_UEMOA", "HORS-UEMOA"):
        return "HORS_UEMOA"
    if c not in CRP_TABLE_PCT:
        raise KeyError(f"pays inconnu pour la prime de risque : {country!r}")
    return c


def country_crp(
    country: str | None = None,
    *,
    method: str = "table",
    multiplier: float = EQUITY_BOND_MULTIPLIER,
    loss_severe: float = LOSS_SEVERE,
    loss_moderate: float = LOSS_MODERATE,
    local_spread_pp: Mapping[str, float] | None = None,
    jump_prob: Mapping[str, tuple[float, float]] | None = None,
    unit: str = "decimal",
) -> float | pd.Series:
    """Prime de risque pays relative à la Côte d'Ivoire (spéc. §4.1).

    * ``method="table"`` : valeurs arrondies du §4.1 (CI 0 ; BJ 0,9 ; TG 2,2 ; SN 3,05 ;
      ML 4,1 ; NE 5,1 ; BF 5,3 ; hors UEMOA 4,0 %) ;
    * ``method="formula"`` : ``m × LS_c + 100 × [(p_sév·L_sév + p_mod·L_mod)_c − (idem)_CI]``,
      avec les tables :data:`LOCAL_SPREAD_VS_CI_PP` et :data:`JUMP_PROBABILITIES`
      (remplaçables pour des tests de sensibilité). Hors UEMOA : 4,0 % dans les deux cas.

    ``country=None`` : série pour tous les pays. ``unit`` : ``"decimal"`` (0,0305) ou ``"pct"``.
    """
    if unit not in ("decimal", "pct"):
        raise ValueError("unit doit valoir 'decimal' ou 'pct'")
    scale = 0.01 if unit == "decimal" else 1.0
    if country is None:
        keys = list(CRP_TABLE_PCT)
        return pd.Series({k: country_crp(k, method=method, multiplier=multiplier, loss_severe=loss_severe,
                                         loss_moderate=loss_moderate, local_spread_pp=local_spread_pp,
                                         jump_prob=jump_prob, unit=unit) for k in keys}, name="crp")
    key = _crp_key(country)
    if key == "HORS_UEMOA" or method == "table":
        return CRP_TABLE_PCT[key] * scale
    if method != "formula":
        raise ValueError("method doit valoir 'table' ou 'formula'")
    ls = dict(LOCAL_SPREAD_VS_CI_PP, **(local_spread_pp or {}))
    jp = dict(JUMP_PROBABILITIES, **(jump_prob or {}))

    def jump(c: str) -> float:
        ps, pm = jp[c]
        return 100.0 * (ps * loss_severe + pm * loss_moderate)

    crp_pct = multiplier * (ls[key] - ls["CI"]) + jump(key) - jump("CI")
    return crp_pct * scale


def cost_of_equity(
    symbol: str,
    *,
    beta: float = 1.0,
    rf: float = 0.0575,
    erp: float = ERP_BRVM,
    variant: str = "detention",
    method: str = "table",
) -> float:
    """Coût des fonds propres ``k_i = rf + β_i × ERP + Σ_c λ_ic × CRP_c`` (décimal, spéc. §4.1).

    Sert aux lignes de base de valorisation affichées par ``explain()`` ; **n'entre pas** dans
    le score A. Exemple SNTS (variante détention, β = 1) : 5,75 + 4,0 + ≈ 3,7 ≈ 13,5 %.
    """
    lam = reference.economic_exposure(symbol, variant)
    crp = sum(w * float(country_crp(c, method=method)) for c, w in lam.items())
    return float(rf) + float(beta) * float(erp) + crp


# ---------------------------------------------------------------------------
# Pas de cotation et bandes de prix (§7.1)
# ---------------------------------------------------------------------------

PRICE_LIMIT = 0.075
_EPS = 1e-9


def tick_size(price):
    """Pas de cotation : 1 FCFA si le cours est < 100 FCFA, sinon 5 (BOC 2017-2026, revue 01 §2.3)."""
    if np.ndim(price) == 0:
        return 1 if float(price) < 100 else 5
    p = np.asarray(price, dtype=float)
    return np.where(p < 100, 1, 5)


def price_band(ref: float, symbol: str | None = None, *, pct: float = PRICE_LIMIT,
               tick: float | None = None) -> tuple[float, float]:
    """Bornes de cotation autour de la référence **ajustée** (spéc. §7.1, revue 01 §3.2).

    ``basse = ceil(réf × (1 − pct) / pas) × pas`` ; ``haute = max(floor(réf × (1 + pct) / pas) × pas ; réf + pas)``.
    Pas de pas minimal vers le bas : à 13 FCFA, ETIT n'a jamais clôturé sous 13 en 363
    séances (BOC 2017-2026), conforme à ``ceil(12,025) = 13``. ``symbol`` est accepté pour
    la lisibilité des appels ; le pas ne dépend que du cours.
    """
    ref = float(ref)
    step = float(tick if tick is not None else tick_size(ref))
    low = math.ceil(ref * (1.0 - pct) / step - _EPS) * step
    high = max(math.floor(ref * (1.0 + pct) / step + _EPS) * step, ref + step)
    return float(low), float(high)


def price_band_frame(ref, *, pct: float = PRICE_LIMIT):
    """Version vectorisée de :func:`price_band` : renvoie ``(basse, haute)`` de même forme que ``ref``
    (DataFrame, Series ou tableau). Les références manquantes donnent ``NaN``."""
    arr = np.asarray(ref, dtype=float)
    step = np.where(arr < 100, 1.0, 5.0)
    low = np.ceil(arr * (1.0 - pct) / step - _EPS) * step
    high = np.maximum(np.floor(arr * (1.0 + pct) / step + _EPS) * step, arr + step)
    low = np.where(np.isfinite(arr), low, np.nan)
    high = np.where(np.isfinite(arr), high, np.nan)
    if isinstance(ref, pd.DataFrame):
        return (pd.DataFrame(low, index=ref.index, columns=ref.columns),
                pd.DataFrame(high, index=ref.index, columns=ref.columns))
    if isinstance(ref, pd.Series):
        return pd.Series(low, index=ref.index, name="low"), pd.Series(high, index=ref.index, name="high")
    return low, high


# ---------------------------------------------------------------------------
# Calendrier, règlement et date de détachement (§5.2, §7.1.5)
# ---------------------------------------------------------------------------

#: Passage de J+3 à J+2 (instruction 03-2025/BRVM/DG) : première séance réglée à J+2.
SETTLEMENT_SWITCH_DATE = "2025-12-04"


def session_index(sessions: Any = None) -> pd.DatetimeIndex:
    """Calendrier des séances sous forme de ``DatetimeIndex`` trié.

    Accepte un ``DatetimeIndex``, une liste de dates, une ``Series`` de dates, un DataFrame
    avec une colonne ``date`` (``sessions.parquet`` : séances réelles, BOC disponible ou non)
    ou un chemin de panel (lecture de ``sessions.parquet``). ``None`` : index vide (jours
    ouvrés du lundi au vendredi, jours fériés inconnus).
    """
    if sessions is None:
        return pd.DatetimeIndex([])
    if isinstance(sessions, (str, Path)):
        sessions = pd.read_parquet(Path(sessions) / "sessions.parquet")
    if isinstance(sessions, pd.DataFrame):
        sessions = sessions["date"] if "date" in sessions.columns else sessions.index
    idx = pd.DatetimeIndex(pd.to_datetime(pd.Series(list(sessions)).dropna())).normalize()
    return idx.unique().sort_values()


def _extended_calendar(cal: pd.DatetimeIndex, lo: pd.Timestamp, hi: pd.Timestamp) -> pd.DatetimeIndex:
    """Calendrier connu, complété par des jours ouvrés hors de sa plage."""
    if len(cal) == 0:
        return pd.bdate_range(lo, hi)
    parts = [cal]
    if lo < cal[0]:
        parts.append(pd.bdate_range(lo, cal[0] - pd.Timedelta(days=1)))
    if hi > cal[-1]:
        parts.append(pd.bdate_range(cal[-1] + pd.Timedelta(days=1), hi))
    return parts[0].append(parts[1:]).unique().sort_values() if len(parts) > 1 else cal


def shift_sessions(date: Any, n: int, sessions: Any = None) -> pd.Timestamp:
    """Séance située ``n`` séances après (``n > 0``) ou avant (``n < 0``) ``date``.

    ``n = −1`` : dernière séance strictement antérieure ; ``n = +1`` : première séance
    strictement postérieure. Hors du calendrier fourni : jours ouvrés (fériés inconnus).
    """
    d = pd.Timestamp(date).normalize()
    if n == 0:
        return d
    span = pd.Timedelta(days=7 * abs(n) + 30)
    cal = _extended_calendar(session_index(sessions), d - span, d + span)
    if n < 0:
        before = cal[cal < d]
        if len(before) < -n:
            raise ValueError("calendrier trop court")
        return before[n]
    after = cal[cal > d]
    if len(after) < n:
        raise ValueError("calendrier trop court")
    return after[n - 1]


def settlement_lag(date: Any, switch_date: str = SETTLEMENT_SWITCH_DATE):
    """Délai de règlement-livraison (séances) d'une négociation à ``date`` : 3 avant le
    04/12/2025, 2 ensuite. Accepte un scalaire ou un vecteur de dates."""
    sw = pd.Timestamp(switch_date)
    if np.ndim(date) == 0:
        return 3 if pd.Timestamp(date).normalize() < sw else 2
    d = pd.to_datetime(pd.Series(list(date))).dt.normalize()
    return np.where(d < sw, 3, 2)


def ex_date_rule(payment_or_register_date: Any, sessions: Any = None, *,
                 switch_date: str = SETTLEMENT_SWITCH_DATE) -> pd.Timestamp:
    """Date de détachement (ex) d'après la date de paiement ou de fermeture des registres (§5.2).

    Règle : jusqu'au 03/12/2025 (J+3), 2 séances avant la date des registres ; depuis le
    04/12/2025 (J+2), 1 séance avant (« 2 si ce jour est férié » : c'est la séance
    précédente du calendrier). Le régime est celui du **dernier jour avec droit** (veille du
    jour ex) : son règlement doit tomber le jour des registres.

    Vérification (BOC et ``dividends.parquet``) : en appliquant la règle à la **date de
    paiement** publiée au BOC, prise comme date des registres, avec le calendrier réel des
    séances, on retrouve SNTS 2026 (paiement 26/05/2026, lundi 25/05 férié -> ex 22/05/2026)
    et SNTS 2025 (paiement 22/05/2025 -> ex 20/05/2025), lignes (d)/(V) des BOC des 19-20/05/2025
    et 21-22/05/2026. Sans calendrier (jours ouvrés), le férié du 25/05/2026 n'est pas connu
    et la règle donnerait le 25/05/2026 : fournir ``sessions``.
    """
    reg = pd.Timestamp(payment_or_register_date).normalize()
    last_cum_t2 = shift_sessions(reg, -2, sessions)
    if last_cum_t2 >= pd.Timestamp(switch_date):
        return shift_sessions(reg, -1, sessions)
    return shift_sessions(reg, -2, sessions)


def ex_date_check(dividends: pd.DataFrame, sessions: Any = None,
                  switch_date: str = SETTLEMENT_SWITCH_DATE) -> pd.DataFrame:
    """Compare la date ex détectée (``dividends.parquet``) à :func:`ex_date_rule` appliquée à la
    date de paiement. Colonnes ajoutées : ``ex_rule``, ``match``, ``lag_sessions`` (séances
    entre la date ex détectée et le paiement)."""
    cal = session_index(sessions)
    rows = []
    for d in dividends.itertuples(index=False):
        if pd.isna(d.payment_date) or pd.isna(d.ex_date):
            continue
        rule = ex_date_rule(d.payment_date, cal, switch_date=switch_date)
        ex = pd.Timestamp(d.ex_date).normalize()
        pay = pd.Timestamp(d.payment_date).normalize()
        lag = int(((cal > ex) & (cal <= pay)).sum()) if len(cal) else int(np.busday_count(ex.date(), pay.date()))
        rows.append({"symbol": d.symbol, "ex_date": ex, "payment_date": pay, "ex_rule": rule,
                     "match": rule == ex, "lag_sessions": lag,
                     "evidence": getattr(d, "evidence", None)})
    return pd.DataFrame(rows)
