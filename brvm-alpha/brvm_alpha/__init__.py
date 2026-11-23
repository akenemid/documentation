"""BRVM Alpha - plate-forme d'analyse quantitative de la BRVM."""

import os as _os
import sys as _sys

__version__ = "0.1.0"


def _embarque_sans_import() -> bool:
    """Même règle que :func:`brvm_alpha.paths.est_embarque` (``BRVM_ALPHA_EMBARQUE=1`` ou fichier ``VERSION`` à la
    racine du code, liens symboliques résolus), sans rien importer du paquet : elle sert à couper l'écriture des
    fichiers ``.pyc`` **avant** le premier import (un test vérifie que les deux réponses concordent)."""
    if str(_os.environ.get("BRVM_ALPHA_EMBARQUE", "") or "").strip() == "1":
        return True
    racine = _os.path.dirname(_os.path.dirname(_os.path.realpath(__file__)))
    return _os.path.isfile(_os.path.join(racine, "VERSION"))


# Mode embarqué (module Odoo) : aucune écriture dans l'arbre du code, donc pas de fichiers .pyc à côté des
# modules. Le lanceur passe aussi « -B » : avec « -I », la variable PYTHONDONTWRITEBYTECODE est ignorée.
if _embarque_sans_import():
    _sys.dont_write_bytecode = True

from brvm_alpha import paths as _paths  # noqa: E402 - module léger (os, pathlib)
from brvm_alpha import ressources as _ressources  # noqa: E402 - module léger (os, sys)

# Une bibliothèque compilée impossible à charger faute de mémoire lève MemoryError (code 6), pas ImportError.
_ressources.installer_garde_chargement()

# Mode embarqué : un fil de calcul et le pool mémoire « system » d'Arrow, posés avant l'import de numpy et de
# pyarrow (pic de mémoire virtuelle divisé par 2 à 3 ; voir brvm_alpha.ressources).
if _paths.est_embarque():
    _ressources.regler_processus_embarque()
