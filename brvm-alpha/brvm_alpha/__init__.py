"""BRVM Alpha - plate-forme d'analyse quantitative de la BRVM."""

__version__ = "0.1.0"

# Mode embarqué (module Odoo) : un fil de calcul et le pool mémoire « system » d'Arrow, posés avant
# l'import de numpy et de pyarrow (pic de mémoire virtuelle divisé par 2 à 3 ; voir brvm_alpha.ressources).
from brvm_alpha import paths as _paths  # noqa: E402 - module léger (os, pathlib)

if _paths.est_embarque():
    from brvm_alpha import ressources as _ressources

    _ressources.regler_processus_embarque()
