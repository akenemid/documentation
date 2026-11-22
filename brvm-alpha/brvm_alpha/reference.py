"""Métadonnées de référence des sociétés cotées à la BRVM.

Le pays d'un émetteur se lit dans le suffixe de son symbole BRVM :
``C`` Côte d'Ivoire, ``S`` Sénégal, ``B`` Bénin, ``BF`` Burkina Faso,
``M`` Mali, ``N`` Niger, ``T`` Togo. Le tableau ``OVERRIDES`` corrige les
exceptions et ajoute l'exposition économique réelle (ex. ETIT est une holding
panafricaine domiciliée au Togo).

Données ajoutées pour la stratégie v1 (``docs/SPECIFICATION_STRATEGIE.md``) ; chaque
valeur porte sa source en commentaire. Les données **datées** sont point-in-time :
une fonction ``f(symbole, asof)`` ne renvoie une information qu'à partir du jour où elle
était publique (règle §3.1.4 : à défaut d'en-tête ``Last-Modified``, un document est
utilisable **2 séances** après la date de son nom de fichier ; dates précalculées sur
``data/panel/sessions.parquet`` et vérifiées par les tests).

* nombre de titres actuel (avis 303-2026, revue 01 §11) : :data:`SHARES_OUTSTANDING_2026`,
  :func:`shares_outstanding` (la propagation vers le passé avec les divisions est faite
  par ``data.store.shares_outstanding_panel``) ;
* flottant BRVM (avis 303-2026, U4) : :func:`free_float`, :func:`free_float_table` ;
* multiplicateurs pays du §4.2 : :func:`country_multiplier` ;
* poids de référence par pays du siège b_c : :data:`REFERENCE_COUNTRY_WEIGHTS_20261120`,
  :func:`reference_country_weights` ;
* exposition économique λ (SNTS, ETIT) : :func:`economic_exposure`, :func:`exposure_matrix` ;
* surcharges de BPA (ETIT 10,00 ; ORGT 264) : :func:`eps_override` ;
* absences de dividende annoncées et dividendes exceptionnels :
  :func:`announced_no_dividend`, :func:`ordinary_dividend_net` ;
* comptes périmés (U9) : :func:`stale_financials` ;
* secteur courant (classification BRVM 2025) : :func:`sector_of`, :func:`sectors`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

import pandas as pd

COUNTRY_NAMES = {
    "CI": "Côte d'Ivoire",
    "SN": "Sénégal",
    "BJ": "Bénin",
    "BF": "Burkina Faso",
    "ML": "Mali",
    "NE": "Niger",
    "TG": "Togo",
    "GW": "Guinée-Bissau",
}

#: Pays de l'Alliance des États du Sahel (bloc AES, plafonds §4.2.3).
AES_COUNTRIES = ("BF", "ML", "NE")

# Exposition économique principale quand elle diffère du pays de cotation.
OVERRIDES: dict[str, dict[str, str]] = {
    "ETIT": {"country": "TG", "exposure": "PANAFRICAIN"},
    "ORGT": {"country": "TG", "exposure": "UEMOA+CEMAC"},
    "SNTS": {"country": "SN", "exposure": "SN+ML+GN+BF+GW"},
}

# Liste au BOC du 2026-11-20 (48 actions).
SYMBOLS_2026 = (
    "ABJC BBGC BICB BICC BNBC BOAB BOABF BOAC BOAM BOAN BOAS CABC CBIBF CFAC CIEC "
    "ECOC ETIT FTSC LNBB NEIC NSBC NTLC ONTBF ORAC ORGT PALC PRSC SAFC SCRC SDCC "
    "SDSC SEMC SGBC SHEC SIBC SICC SIVC SLBC SMBC SNTS SOGC SPHC STAC STBC TTLC "
    "TTLS UNLC UNXC"
).split()

#: Titres radiés présents dans les BOC 2017-2026 (univers point-in-time, sans biais du survivant).
DELISTED_SYMBOLS: dict[str, str] = {
    "SVOC": "2025-06-26",  # MOVIS CI : dernière ligne au BOC le 26/06/2025 (spéc. §5.5)
    "TTRC": "2022-10-05",  # TRITURAF CI (société en liquidation) : dernière ligne au BOC le 05/10/2022
}


def country_of(symbol: str) -> str:
    """Pays d'émission (code ISO-2) d'un symbole BRVM."""
    symbol = symbol.upper().strip()
    if symbol in OVERRIDES:
        return OVERRIDES[symbol]["country"]
    if symbol.endswith("BF"):
        return "BF"
    suffix_map = {"C": "CI", "S": "SN", "B": "BJ", "M": "ML", "N": "NE", "T": "TG", "G": "GW"}
    return suffix_map.get(symbol[-1], "CI")


def exposure_of(symbol: str) -> str:
    """Exposition économique principale (pays ou zone)."""
    symbol = symbol.upper().strip()
    return OVERRIDES.get(symbol, {}).get("exposure", country_of(symbol))


def countries(symbols) -> pd.Series:
    """Série symbole -> pays."""
    return pd.Series({s: country_of(s) for s in symbols}, name="country")


def _ts(x) -> pd.Timestamp:
    return pd.Timestamp(x).normalize()


# ---------------------------------------------------------------------------
# Nombre de titres (avis 303-2026, revue 01 §11)
# ---------------------------------------------------------------------------

#: Source du nombre de titres et du flottant.
AVIS_303_2026_URL = (
    "https://www.brvm.org/sites/default/files/"
    "20261012_-_avis_ndeg303_brvmdg_-_flottant_des_societes_cotees_a_la_brvm.pdf"
)

#: Nombre de titres au 20/11/2026 : avis 303-2026 (données au 31/12/2025), repris dans le
#: tableau de ``docs/research/01-structure-marche.md`` §11, **après** la division SNTS ×10
#: (26/10/2026, avis 309-2026) et l'admission des actions nouvelles SAFC (11/08/2026).
#: Contrôle [C-SPEC] : Σ N × cours = 19 330 Md contre 19 328,8 Md publiés au BOC du 20/11/2026.
SHARES_OUTSTANDING_2026: dict[str, int] = {
    "NTLC": 22_070_400,
    "PALC": 15_459_316,
    "SPHC": 25_558_005,
    "SMBC": 7_794_850,
    "TTLC": 62_961_600,
    "TTLS": 32_577_700,
    "ECOC": 55_050_600,
    "SGBC": 31_111_110,
    "SIBC": 100_000_000,
    "ONTBF": 68_000_000,
    "ORAC": 150_655_350,
    "SNTS": 1_000_000_000,  # 100 000 000 × 10 (division du 26/10/2026)
    "SCRC": 19_600_000,
    "SICC": 600_000,
    "SLBC": 16_460_840,
    "SOGC": 21_601_840,
    "STBC": 17_955_000,
    "UNLC": 9_183_400,
    "ABJC": 10_912_000,
    "BNBC": 6_624_000,
    "CFAC": 181_371_900,  # confirmé par OCR de l'avis 303 (revue 01, vérification n° 27)
    "LNBB": 20_000_000,
    "NEIC": 12_765_825,
    "PRSC": 10_240_000,
    "UNXC": 20_750_000,
    "SHEC": 63_000_000,
    "BBGC": 50_000_000,
    "BICB": 57_759_800,
    "BICC": 16_666_670,
    "BOAB": 40_561_048,
    "BOABF": 44_000_000,
    "BOAC": 40_000_000,
    "BOAM": 27_450_000,
    "BOAN": 20_800_000,
    "BOAS": 36_000_000,
    "CBIBF": 32_000_000,
    "ETIT": 18_084_106_722,  # nombre retenu par la BRVM ; le BPA IFRS implique ≈ 23,7 Md (revue 06a §8)
    "NSBC": 24_734_572,
    "ORGT": 69_986_131,
    "SAFC": 11_869_750,  # 8 119 750 + 3 750 000 actions nouvelles admises le 11/08/2026
    "CABC": 5_920_000,
    "FTSC": 14_103_740,
    "SDSC": 54_435_300,
    "SEMC": 25_189_600,
    "SIVC": 8_734_000,
    "STAC": 13_440_000,
    "CIEC": 56_000_000,
    "SDCC": 9_000_000,
}


@dataclass(frozen=True)
class ShareCountChange:
    """Changement du nombre de titres **sans** facteur d'ajustement de cours."""

    symbol: str
    effective: str  # première séance avec le nouveau nombre
    shares_before: int
    shares_after: int
    source: str


#: Augmentation de capital SAFC avec DPS : 3 750 000 actions nouvelles à 400 FCFA (visa
#: 047/AMF-UMOA/2026), admises le 11/08/2026 (revue 06a §5.8). Le facteur de cours du DPS
#: (0,7066, détachement le 24/04/2026) n'est PAS un changement du nombre de titres.
SHARE_COUNT_CHANGES: tuple[ShareCountChange, ...] = (
    ShareCountChange("SAFC", "2026-08-11", 8_119_750, 11_869_750,
                     "revue 06a §5.8 ; avis 303-2026 (8 119 750 titres) ; spéc. annexe C-SPEC n° 3"),
)


#: Ajustements de cours détectés (``corporate_actions``, kind ``capital_adjustment``) qui ne
#: changent PAS le nombre de titres à leur date : (symbole, date). SAFC : détachement du DPS
#: le 24/04/2026 (facteur de cours 0,7066 = 3 890 / 5 505, avis 108-2026) ; les actions
#: nouvelles ne sont admises que le 11/08/2026 (voir :data:`SHARE_COUNT_CHANGES`).
PRICE_ONLY_ADJUSTMENTS: tuple[tuple[str, str], ...] = (("SAFC", "2026-04-24"),)


def shares_outstanding(symbol: str, date=None) -> int | None:
    """Nombre de titres « actuel » (avis 303-2026), corrigé des changements sans facteur de cours.

    Ne remonte **pas** les divisions : pour une date ancienne, utiliser
    ``data.store.shares_outstanding_panel`` (propagation avec ``corporate_actions``).
    """
    symbol = symbol.upper().strip()
    n = SHARES_OUTSTANDING_2026.get(symbol)
    if n is None or date is None:
        return n
    d = _ts(date)
    for ch in SHARE_COUNT_CHANGES:
        if ch.symbol == symbol and d < _ts(ch.effective):
            n = int(round(n * ch.shares_before / ch.shares_after))
    return n


# ---------------------------------------------------------------------------
# Flottant (U4)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FreeFloatSource:
    """Un avis de flottant de la BRVM (point-in-time)."""

    name: str
    data_as_of: str  # date des données de l'avis
    document_date: str  # date du nom de fichier
    available_from: str  # document_date + 2 séances (règle §3.1.4)
    url: str


AVIS_303_2026 = FreeFloatSource("avis 303-2026", "2025-12-31", "2026-10-12", "2026-10-14", AVIS_303_2026_URL)

#: Flottant BRVM au 31/12/2025, en fraction, d'après l'avis 303-2026. Valeurs du tableau de
#: la revue 01 §11 (arrondies à 0,1 point), remplacées par la valeur exacte de l'avis quand
#: une revue l'a relue : UNLC 0,22 %, CFAC 4,15 %, SEMC 10,29 %, SICC 12,26 % (revue 01 §0,
#: revue 06b §1.2), BICC 32,51 % (revue 06a §5), BOAN 40,94 % (revue 06a §5.14), PRSC 100 %
#: (déclaré, incohérent avec la fiche émetteur : revue 06b §3).
FREE_FLOAT_AVIS_303_2026: dict[str, float] = {
    "NTLC": 0.200, "PALC": 0.329, "SPHC": 0.595, "SMBC": 0.518, "TTLC": 0.270, "TTLS": 0.309,
    "ECOC": 0.238, "SGBC": 0.434, "SIBC": 0.200, "ONTBF": 0.230, "ORAC": 0.202, "SNTS": 0.239,
    "SCRC": 0.230, "SICC": 0.1226, "SLBC": 0.186, "SOGC": 0.268, "STBC": 0.264, "UNLC": 0.0022,
    "ABJC": 0.200, "BNBC": 0.349, "CFAC": 0.0415, "LNBB": 0.450, "NEIC": 0.200, "PRSC": 1.000,
    "UNXC": 0.277, "SHEC": 0.283, "BBGC": 0.200, "BICB": 0.331, "BICC": 0.3251, "BOAB": 0.459,
    "BOABF": 0.435, "BOAC": 0.303, "BOAM": 0.358, "BOAN": 0.4094, "BOAS": 0.383, "CBIBF": 0.304,
    "ETIT": 0.335, "NSBC": 0.200, "ORGT": 0.198, "SAFC": 0.292, "CABC": 0.487, "FTSC": 0.337,
    "SDSC": 0.250, "SEMC": 0.1029, "SIVC": 0.279, "STAC": 0.208, "CIEC": 0.459, "SDCC": 0.495,
}

#: Avis de flottant connus, du plus ancien au plus récent : (source, valeurs).
FREE_FLOAT_HISTORY: tuple[tuple[FreeFloatSource, Mapping[str, float]], ...] = (
    (AVIS_303_2026, FREE_FLOAT_AVIS_303_2026),
)

#: Seuil réglementaire de diffusion (colonne « Diffusion de 15 % du capital dans le public »).
MIN_FREE_FLOAT_REGULATORY = 0.15


def free_float(symbol: str, asof=None, *, allow_backfill: bool = False) -> float | None:
    """Flottant (fraction) d'après le dernier avis **utilisable** à la date ``asof``.

    ``asof=None`` : dernier avis connu. Avant le premier avis de la base (14/10/2026),
    renvoie ``None`` (information inconnue à cette date), sauf ``allow_backfill=True`` qui
    applique le premier avis connu au passé : c'est une **hypothèse d'anticipation**
    (biais possible), à n'utiliser qu'en la déclarant.
    """
    symbol = symbol.upper().strip()
    if asof is None:
        return FREE_FLOAT_HISTORY[-1][1].get(symbol)
    d = _ts(asof)
    known = [vals for src, vals in FREE_FLOAT_HISTORY if _ts(src.available_from) <= d]
    if known:
        return known[-1].get(symbol)
    if allow_backfill:
        return FREE_FLOAT_HISTORY[0][1].get(symbol)
    return None


def free_float_table(asof=None, symbols: Iterable[str] | None = None, *, allow_backfill: bool = False) -> pd.Series:
    """Série symbole -> flottant (fraction) à la date ``asof`` (NaN si inconnu)."""
    syms = list(symbols) if symbols is not None else sorted(FREE_FLOAT_HISTORY[-1][1])
    vals = {s: free_float(s, asof, allow_backfill=allow_backfill) for s in syms}
    return pd.Series({s: (float("nan") if v is None else v) for s, v in vals.items()}, name="free_float", dtype=float)


# ---------------------------------------------------------------------------
# Pays : multiplicateurs, poids de référence, exposition économique
# ---------------------------------------------------------------------------

#: Multiplicateur du poids maximal par ligne selon le pays du siège (spéc. §4.2.1 ;
#: jugement non validé de la revue 06a §9.4).
COUNTRY_MULTIPLIER: dict[str, float] = {
    "CI": 1.0, "BJ": 1.0, "TG": 0.9, "SN": 0.85, "BF": 0.75, "ML": 0.7, "NE": 0.6,
}


def country_multiplier(symbol_or_country: str, table: Mapping[str, float] | None = None) -> float:
    """Multiplicateur du §4.2 pour un symbole ou un code pays.

    Pays absent de la table (GW, aucun titre coté) : plus petit multiplicateur (prudence).
    """
    tab = COUNTRY_MULTIPLIER if table is None else table
    key = symbol_or_country.upper().strip()
    c = key if key in COUNTRY_NAMES else country_of(key)
    return float(tab.get(c, min(tab.values())))


#: Poids de référence b_c par pays du siège au 20/11/2026 (cours BOC × nombre de titres),
#: en fraction ; spéc. §4.1 et revue 05 §11.1 (total recalculé 19 331 Md FCFA).
REFERENCE_COUNTRY_WEIGHTS_20261120: dict[str, float] = {
    "CI": 0.5778, "SN": 0.2294, "BF": 0.0729, "TG": 0.0624, "BJ": 0.0455, "ML": 0.0072, "NE": 0.0048, "GW": 0.0,
}


def reference_country_weights(prices: pd.Series | None = None, shares: Mapping[str, float] | pd.Series | None = None,
                              by: str = "country") -> pd.Series:
    """Poids de référence par pays du siège (``by="country"``) ou par zone d'exposition λ.

    Sans argument : table figée au 20/11/2026. Avec ``prices`` (cours par symbole à une date)
    et ``shares`` (nombre de titres à la même date, défaut :data:`SHARES_OUTSTANDING_2026`) :
    capitalisations agrégées, calcul point-in-time si les deux entrées le sont.
    ``by="exposure"`` ventile chaque capitalisation avec :func:`economic_exposure`.
    """
    if prices is None:
        if by != "country":
            raise ValueError("by='exposure' exige des cours")
        return pd.Series(REFERENCE_COUNTRY_WEIGHTS_20261120, name="b_c", dtype=float)
    sh = pd.Series(SHARES_OUTSTANDING_2026 if shares is None else shares, dtype=float)
    px = pd.Series(prices, dtype=float)
    cap = (px * sh.reindex(px.index)).dropna()
    cap = cap[cap > 0]
    if by == "country":
        out = cap.groupby([country_of(s) for s in cap.index]).sum()
    elif by == "exposure":
        out = exposure_matrix(cap.index).mul(cap, axis=0).sum()
    else:
        raise ValueError("by doit valoir 'country' ou 'exposure'")
    return (out / out.sum()).rename("b_c")


#: Exposition économique λ (part de l'activité par pays ou zone), spéc. §4.1, revue 05 §11.2.
#: Par défaut λ = 1 pour le pays du siège. SNTS : variante « détention » retenue par la
#: spécification (clients mobiles 2025 × taux de détention des filiales, confiance M) et
#: variante « clients » (clients mobiles 2025 seuls). ETIT : holding panafricaine, surtout
#: hors UEMOA (zone « PANAFRICAIN », prime pays hors UEMOA de 4 %).
ECONOMIC_EXPOSURE: dict[str, dict[str, dict[str, float]]] = {
    "detention": {
        "SNTS": {"SN": 0.401, "ML": 0.238, "GN": 0.274, "SL": 0.045, "GW": 0.042},
        "ETIT": {"PANAFRICAIN": 1.0},
    },
    "clients": {
        "SNTS": {"SN": 0.337, "ML": 0.289, "GN": 0.259, "SL": 0.075, "GW": 0.040},
        "ETIT": {"PANAFRICAIN": 1.0},
    },
}

#: Zones hors UEMOA (prime pays forfaitaire de 4 %, risque de change compris, spéc. §4.1).
NON_UEMOA_ZONES = ("GN", "SL", "PANAFRICAIN")


def economic_exposure(symbol: str, variant: str = "detention") -> dict[str, float]:
    """Vecteur λ d'un titre (somme = 1)."""
    if variant not in ECONOMIC_EXPOSURE:
        raise ValueError(f"variante inconnue : {variant!r} ({', '.join(ECONOMIC_EXPOSURE)})")
    symbol = symbol.upper().strip()
    lam = ECONOMIC_EXPOSURE[variant].get(symbol)
    return dict(lam) if lam is not None else {country_of(symbol): 1.0}


def exposure_matrix(symbols: Iterable[str], variant: str = "detention") -> pd.DataFrame:
    """Matrice λ (symbole × pays/zone), lignes de somme 1."""
    rows = {s: economic_exposure(s, variant) for s in symbols}
    return pd.DataFrame(rows).T.fillna(0.0).sort_index(axis=1)


# ---------------------------------------------------------------------------
# Surcharges de BPA (§3.2)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EpsOverride:
    """BPA à utiliser à la place du PER du BOC (calculé sur le RN total, minoritaires compris)."""

    symbol: str
    eps: float  # FCFA par action
    fiscal_year: int
    basis: str
    document_date: str
    available_from: str  # document_date + 2 séances (règle §3.1.4)
    source: str


#: ETIT : BPA de base = dilué = 1,68 cent US = 10,00 FCFA (états financiers IFRS 2025), soit un
#: PER ≈ 5,7 à 57 FCFA contre 2,98 au BOC (revue 06a §5.16 et vérification n° 10).
#: ORGT : BPA de base 2025 = 264 FCFA (dilué 241), RN part du groupe 18 355 M (revue 06a §5.17,
#: vérification n° 11). Convention unique : BPA **de base** (revue 06a §8, n° 1).
EPS_OVERRIDES: dict[str, EpsOverride] = {
    "ETIT": EpsOverride(
        "ETIT", 10.00, 2025, "BPA part du groupe IFRS (de base = dilué)", "2026-04-13", "2026-04-15",
        "https://www.brvm.org/sites/default/files/20260413_-_etats_financiers_ifrs_-_exercice_2025_-_eti_tg.pdf"),
    "ORGT": EpsOverride(
        "ORGT", 264.0, 2025, "BPA de base part du groupe IFRS (dilué 241)", "2026-05-04", "2026-05-06",
        "https://www.brvm.org/sites/default/files/20260504_-_etats_financiers_-_exercice_2025_-_oragroup_tg.pdf"),
}


def eps_override(symbol: str, asof=None) -> float | None:
    """BPA de surcharge utilisable à ``asof`` (``None`` avant sa disponibilité ou sans surcharge).

    ``asof=None`` : dernière surcharge connue. La surcharge vaut jusqu'aux comptes de
    l'exercice suivant (date inconnue aujourd'hui : à mettre à jour à leur publication).
    """
    rec = EPS_OVERRIDES.get(symbol.upper().strip())
    if rec is None:
        return None
    if asof is not None and _ts(asof) < _ts(rec.available_from):
        return None
    return rec.eps


# ---------------------------------------------------------------------------
# Dividendes : absences annoncées, parts exceptionnelles
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DividendAbsence:
    """Exercice sans dividende, connu à partir de ``available_from``."""

    symbol: str
    fiscal_year: int | None  # None : absence durable (aucun dividende depuis ``since``)
    document_date: str
    available_from: str
    source: str
    since: str | None = None  # date du dernier paiement connu


#: Absences de dividende (spéc. §3.2, repli v1 de DY ; revue 06a §0 n° 10 et §8 n° 3).
DIVIDEND_ABSENCES: tuple[DividendAbsence, ...] = (
    # BOAN : aucun dividende au titre de 2025 (RN −92 %), communiqué de presse du 29/04/2026.
    DividendAbsence("BOAN", 2025, "2026-04-29", "2026-05-04",
                    "https://www.brvm.org/sites/default/files/20260429_-_communique_de_presse_-_boa_ng.pdf ; revue 06a §5.14"),
    # ORGT : aucun dividende depuis 2020 (dernier paiement 59,52 net le 17/07/2020, BOC) ;
    # exercice 2025 : états financiers du 04/05/2026 (rapport annuel du 30/04/2026).
    DividendAbsence("ORGT", 2025, "2026-05-04", "2026-05-06",
                    "https://www.brvm.org/sites/default/files/20260504_-_etats_financiers_-_exercice_2025_-_oragroup_tg.pdf ;"
                    " revue 06a §5.17", since="2020-07-17"),
    # SAFC : aucun dividende depuis 2011 (dernier : 23,04 net le 29/07/2011, colonne « dernier
    # dividende » du BOC dès le 02/01/2017, premier BOC de la base). Absence durable.
    DividendAbsence("SAFC", None, "2017-01-02", "2017-01-02", "BOC 2017-2026 ; revue 06a §5.8", since="2011-07-29"),
    # FTSC : projet d'affectation de l'exercice 2025 sans dividende (états financiers du 10/06/2026) ;
    # spéc. §12.3 n° 5 : dy_used(FTSC, 2026-11-20) = 0 ; revue 06b A2 : dy_used(FTSC, 2026-03-31) > 0.
    DividendAbsence("FTSC", 2025, "2026-06-10", "2026-06-12",
                    "https://www.brvm.org/sites/default/files/20260610_-_etats_financiers_-_exercice_2025_-_filtisac_ci.pdf ;"
                    " revue 06b §6 A2"),
)


def announced_no_dividend(symbol: str, asof, last_payment_date=None) -> DividendAbsence | None:
    """Absence de dividende connue à ``asof`` et non démentie par un paiement postérieur.

    ``last_payment_date`` : date du dernier dividende payé connue à ``asof`` (colonne
    ``last_div_date`` du BOC) ; un paiement **après** l'annonce rend l'absence caduque
    (nouvel exercice). Renvoie l'enregistrement le plus récent, sinon ``None``.
    """
    symbol = symbol.upper().strip()
    d = _ts(asof)
    best: DividendAbsence | None = None
    for rec in DIVIDEND_ABSENCES:
        if rec.symbol != symbol or _ts(rec.available_from) > d:
            continue
        if last_payment_date is not None and not pd.isna(last_payment_date):
            lp = _ts(last_payment_date)
            if lp > _ts(rec.available_from) or (rec.since is not None and lp > _ts(rec.since)):
                continue
        if best is None or _ts(rec.available_from) > _ts(best.available_from):
            best = rec
    return best


@dataclass(frozen=True)
class ExceptionalDividend:
    """Dividende comprenant une part exceptionnelle (exclue du signal DY, gardée dans le TR)."""

    symbol: str
    payment_date: str
    ex_date: str
    gross_ordinary: float
    gross_exceptional: float
    net_total: float  # montant net publié au BOC
    net_ordinary: float
    net_exceptional: float
    source: str


#: FTSC : 2 000,67 brut = 1 320 ordinaire (IRVM 12 %) + 680,67 exceptionnel (IRVM 17 %), net
#: 1 726,56 = 1 161,60 + 564,96, payé le 30/09/2025 (calendrier exercice 2024 ; revue 06b,
#: vérification n° 12). Le rendement BOC de 107,91 % au 20/11/2026 vient de ce versement.
EXCEPTIONAL_DIVIDENDS: tuple[ExceptionalDividend, ...] = (
    ExceptionalDividend("FTSC", "2025-09-30", "2025-09-26", 1320.0, 680.67, 1726.56, 1161.60, 564.96,
                        "calendrier de paiement des dividendes, exercice 2024 (24/12/2025) ; revue 06b §6 A2"),
)


def ordinary_dividend_net(symbol: str, date, amount_net: float, tolerance_days: int = 7) -> float:
    """Part **ordinaire** d'un dividende net (retire une part exceptionnelle connue).

    ``date`` : date de paiement ou de détachement ; la correspondance se fait à
    ``tolerance_days`` près et sur le montant net publié (à 1 % près).
    """
    symbol = symbol.upper().strip()
    d = _ts(date)
    for rec in EXCEPTIONAL_DIVIDENDS:
        if rec.symbol != symbol:
            continue
        near = min(abs((d - _ts(rec.payment_date)).days), abs((d - _ts(rec.ex_date)).days)) <= tolerance_days
        if near and abs(float(amount_net) - rec.net_total) <= 0.01 * rec.net_total:
            return rec.net_ordinary
    return float(amount_net)


# ---------------------------------------------------------------------------
# Comptes périmés (U9)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LastAnnualAccounts:
    """Derniers comptes annuels publiés connus (relevé fait à ``checked_on``)."""

    symbol: str
    fiscal_year_end: str
    published: str
    checked_on: str
    source: str


#: U9 : UNLC et SEMC n'ont publié aucun état financier après l'exercice 2023 (pages émetteurs
#: relues le 20-22/11/2026 ; revue 06b §1.2 et vérification n° 24). Autres titres : non relevés.
LAST_ANNUAL_ACCOUNTS: dict[str, LastAnnualAccounts] = {
    "UNLC": LastAnnualAccounts(
        "UNLC", "2023-12-31", "2024-09-04", "2026-11-20",
        "https://www.brvm.org/sites/default/files/20240904_-_etats_financiers_-_exercice_2023_-_unilever_ci.pdf"),
    "SEMC": LastAnnualAccounts(
        "SEMC", "2023-12-31", "2024-12-16", "2026-11-20",
        "https://www.brvm.org/sites/default/files/"
        "20241216_-_etats_financiers_de_synthese_-exercice_2023_-_eviosys_packaging_siem_ci.pdf"),
}


def stale_financials(symbol: str, asof, max_age_days: int = 546) -> bool | None:
    """U9 : ``True`` si les derniers comptes connus portent sur un exercice clos depuis plus
    de ``max_age_days`` jours ; ``None`` si l'information n'est pas relevée pour ce titre
    ou n'était pas encore publiée à ``asof``.

    Après ``checked_on``, le résultat suppose qu'aucun compte plus récent n'a été publié :
    à revérifier sur la page de l'émetteur.
    """
    rec = LAST_ANNUAL_ACCOUNTS.get(symbol.upper().strip())
    if rec is None:
        return None
    d = _ts(asof)
    if d < _ts(rec.published):
        return None
    return (d - _ts(rec.fiscal_year_end)).days > int(max_age_days)


# ---------------------------------------------------------------------------
# Secteurs (classification BRVM 2025)
# ---------------------------------------------------------------------------

SECTOR_LABELS: dict[str, str] = {
    "FIN": "Services financiers",
    "CB": "Consommation de base",
    "CD": "Consommation discrétionnaire",
    "IND": "Industriels",
    "ENE": "Énergie",
    "TEL": "Télécommunications",
    "SPU": "Services publics",
}

#: Secteur courant (classification BRVM 2025, colonne « secteur » du BOC du 20/11/2026 ;
#: revue 01 §11). La classification des BOC 2017-2024 (DIS, AGR, TRP, AUT…) n'est pas
#: comparable : ce tableau la remplace pour tout l'historique.
SECTOR_2025: dict[str, str] = {
    "ABJC": "CD", "BBGC": "FIN", "BICB": "FIN", "BICC": "FIN", "BNBC": "CD", "BOAB": "FIN",
    "BOABF": "FIN", "BOAC": "FIN", "BOAM": "FIN", "BOAN": "FIN", "BOAS": "FIN", "CABC": "IND",
    "CBIBF": "FIN", "CFAC": "CD", "CIEC": "SPU", "ECOC": "FIN", "ETIT": "FIN", "FTSC": "IND",
    "LNBB": "CD", "NEIC": "CD", "NSBC": "FIN", "NTLC": "CB", "ONTBF": "TEL", "ORAC": "TEL",
    "ORGT": "FIN", "PALC": "CB", "PRSC": "CD", "SAFC": "FIN", "SCRC": "CB", "SDCC": "SPU",
    "SDSC": "IND", "SEMC": "IND", "SGBC": "FIN", "SHEC": "ENE", "SIBC": "FIN", "SICC": "CB",
    "SIVC": "IND", "SLBC": "CB", "SMBC": "ENE", "SNTS": "TEL", "SOGC": "CB", "SPHC": "CB",
    "STAC": "IND", "STBC": "CB", "TTLC": "ENE", "TTLS": "ENE", "UNLC": "CB", "UNXC": "CD",
    # Titres radiés :
    "SVOC": "IND",  # MOVIS CI : secteur IND au BOC du 26/06/2025 (classification 2025)
    "TTRC": "IND",  # TRITURAF CI : radiée en 2022, avant la classification 2025 ; ancien code « IND » (hypothèse)
}


def sector_of(symbol: str) -> str | None:
    """Secteur BRVM 2025 d'un symbole (``None`` si inconnu)."""
    return SECTOR_2025.get(symbol.upper().strip())


def sectors(symbols) -> pd.Series:
    """Série symbole -> secteur BRVM 2025."""
    return pd.Series({s: sector_of(s) for s in symbols}, name="sector", dtype=object)
