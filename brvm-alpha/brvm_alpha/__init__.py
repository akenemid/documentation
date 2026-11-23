"""BRVM Alpha - plate-forme d'analyse quantitative de la BRVM."""

import os as _os
import sys as _sys

__version__ = "0.1.0"

# Mode embarqué (module Odoo) : aucune écriture dans l'arbre du code, donc pas de fichiers .pyc à côté des
# modules. Réglé avant tout autre import du paquet (même test que brvm_alpha.paths.est_embarque : variable
# BRVM_ALPHA_EMBARQUE=1 ou fichier VERSION à la racine du code). Le lanceur passe aussi « -B » : avec « -I »,
# la variable PYTHONDONTWRITEBYTECODE est ignorée.
if (str(_os.environ.get("BRVM_ALPHA_EMBARQUE", "") or "").strip() == "1"
        or _os.path.isfile(_os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "VERSION"))):
    _sys.dont_write_bytecode = True

# Mode embarqué : un fil de calcul et le pool mémoire « system » d'Arrow, posés avant l'import de numpy et de
# pyarrow (pic de mémoire virtuelle divisé par 2 à 3 ; voir brvm_alpha.ressources).
from brvm_alpha import paths as _paths  # noqa: E402 - module léger (os, pathlib)

if _paths.est_embarque():
    from brvm_alpha import ressources as _ressources

    _ressources.regler_processus_embarque()
