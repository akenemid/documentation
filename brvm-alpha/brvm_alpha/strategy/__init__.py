"""Modèle BRVM Alpha v1 (``docs/SPECIFICATION_STRATEGIE.md``, contrat ``docs/ARCHITECTURE.md``).

- :class:`BrvmAlpha` : univers U1-U10, signaux et variantes A-H, filtres de risque R1-R12,
  règles pays, construction de portefeuille, explication d'une ligne, mode « indice
  discipliné » ;
- :func:`build_panels` : panels du moteur et de la stratégie à partir de ``data/panel``.

Rien ici ne garantit un gain : ce sont des règles pré-enregistrées dont la valeur reste à
mesurer (validation §8).
"""

from brvm_alpha.strategy.alpha import (
    COUNTRY_RULES,
    SIGNAL_LABELS,
    VARIANT_SPECS,
    VARIANTS,
    AlphaDecision,
    BrvmAlpha,
    VariantSpec,
    build_panels,
    notes_available,
)

__all__ = [
    "COUNTRY_RULES",
    "SIGNAL_LABELS",
    "VARIANTS",
    "VARIANT_SPECS",
    "AlphaDecision",
    "BrvmAlpha",
    "VariantSpec",
    "build_panels",
    "notes_available",
]
