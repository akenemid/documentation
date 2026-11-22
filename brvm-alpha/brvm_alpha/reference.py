"""Métadonnées de référence des sociétés cotées à la BRVM.

Le pays d'un émetteur se lit dans le suffixe de son symbole BRVM :
``C`` Côte d'Ivoire, ``S`` Sénégal, ``B`` Bénin, ``BF`` Burkina Faso,
``M`` Mali, ``N`` Niger, ``T`` Togo. Le tableau ``OVERRIDES`` corrige les
exceptions et ajoute l'exposition économique réelle (ex. ETIT est une holding
panafricaine domiciliée au Togo).
"""

from __future__ import annotations

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
