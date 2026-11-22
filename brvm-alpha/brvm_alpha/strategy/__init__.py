"""Modèle BRVM Alpha v1 (``docs/SPECIFICATION_STRATEGIE.md``, contrat ``docs/ARCHITECTURE.md``).

- :class:`BrvmAlpha` : univers U1-U10, signaux et variantes A-I (famille v1.1,
  :data:`FAMILY_V11`) et référence ``REF`` (« indice discipliné », D8), filtres de risque
  R1-R12, règles pays datées (``reference.COUNTRY_EVENTS``, D10), construction de
  portefeuille, explication d'une ligne ;
- :func:`build_panels` : panels du moteur et de la stratégie à partir de ``data/panel`` ;
- :func:`dividend_amount_gap` : écart entre montants de dividende des signaux et des flux (D6).

Rien ici ne garantit un gain : ce sont des règles pré-enregistrées dont la valeur reste à
mesurer (validation §8).
"""

from brvm_alpha.strategy.alpha import (
    COUNTRY_RULES,
    FAMILY_V1,
    FAMILY_V11,
    REFERENCE_VARIANT,
    SIGNAL_LABELS,
    VARIANT_SPECS,
    VARIANTS,
    AlphaDecision,
    BrvmAlpha,
    VariantSpec,
    build_panels,
    dividend_amount_gap,
    notes_available,
)

__all__ = [
    "COUNTRY_RULES",
    "FAMILY_V1",
    "FAMILY_V11",
    "REFERENCE_VARIANT",
    "SIGNAL_LABELS",
    "VARIANTS",
    "VARIANT_SPECS",
    "AlphaDecision",
    "BrvmAlpha",
    "VariantSpec",
    "build_panels",
    "dividend_amount_gap",
    "notes_available",
]
