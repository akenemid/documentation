"""Emplacements des données et des rapports écrits.

Par défaut, tout reste dans l'arbre du code, comme avant : ``<dépôt>/data`` (bulletins en texte,
panel, journal des notes et son cache) et ``<dépôt>/reports`` (rapports écrits). Deux variables
d'environnement permettent de les placer ailleurs, par exemple sur un volume de données :

- ``BRVM_ALPHA_DONNEES=/chemin`` : remplace ``<dépôt>/data`` (``boc_text/``, ``panel/``, ``notes/``) ;
- ``BRVM_ALPHA_RAPPORTS=/chemin`` : remplace ``<dépôt>/reports`` pour les rapports **écrits**
  (``rapport_AAAA-MM-JJ.html``, export des notes).

Les variables sont lues **une fois, au démarrage** du programme. Les options de la ligne de
commande (``--panel-dir``, ``--boc-dir``, ``--racine``, ``--sortie``) l'emportent toujours.

Ce qui ne bouge jamais : les résultats de la validation (``reports/validation_S1``,
``reports/diagnostic_S0``, ``reports/trials.parquet``) et ``configs/strategy_v1.yaml`` restent lus
dans le dépôt. Ils font partie du code livré, pas des données de l'installation.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

#: Variable d'environnement du dossier de données (défaut : ``<dépôt>/data``).
ENV_DATA = "BRVM_ALPHA_DONNEES"
#: Variable d'environnement du dossier des rapports écrits (défaut : ``<dépôt>/reports``).
ENV_REPORTS = "BRVM_ALPHA_RAPPORTS"

#: Racine du dépôt ``brvm-alpha`` (dossier qui contient le paquet ``brvm_alpha``).
REPO_ROOT = Path(__file__).resolve().parents[1]


def env_dir(name: str, environ: Mapping[str, str] | None = None) -> Path | None:
    """Dossier désigné par la variable ``name`` (chemin absolu), ou ``None`` si elle est vide.

    Un chemin relatif s'entend depuis le dossier courant au démarrage ; ``~`` est accepté.
    """
    raw = str((os.environ if environ is None else environ).get(name, "") or "").strip()
    if not raw:
        return None
    return Path(os.path.abspath(os.path.expanduser(raw)))


def resolve_dirs(environ: Mapping[str, str] | None = None) -> tuple[Path, Path]:
    """``(dossier de données, dossier des rapports écrits)`` pour un environnement donné."""
    return (env_dir(ENV_DATA, environ) or REPO_ROOT / "data",
            env_dir(ENV_REPORTS, environ) or REPO_ROOT / "reports")


#: Dossiers en vigueur, fixés au démarrage (voir le module).
DATA_DIR, REPORTS_DIR = resolve_dirs()
PANEL_DIR = DATA_DIR / "panel"
BOC_DIR = DATA_DIR / "boc_text"
NOTES_DIR = DATA_DIR / "notes"

#: Résultats de la validation : toujours dans le dépôt, quelles que soient les variables.
VALIDATION_DIR = REPO_ROOT / "reports" / "validation_S1"
DIAGNOSTIC_DIR = REPO_ROOT / "reports" / "diagnostic_S0"


def repo_path(path: str | Path) -> Path:
    """Chemin absolu d'un chemin donné relativement au dépôt.

    Un chemin relatif qui commence par ``data/`` désigne le dossier de données en vigueur
    (``data/panel`` → ``<données>/panel``) ; tout autre chemin relatif reste dans le dépôt
    (``reports/validation_S1`` n'est jamais déplacé) ; un chemin absolu est rendu tel quel.
    """
    p = Path(path)
    if p.is_absolute():
        return p
    if p.parts and p.parts[0] == "data":
        return DATA_DIR.joinpath(*p.parts[1:])
    return REPO_ROOT / p


def relocated() -> bool:
    """Vrai si les données ou les rapports écrits sont placés hors de l'arbre du code."""
    return DATA_DIR != REPO_ROOT / "data" or REPORTS_DIR != REPO_ROOT / "reports"


__all__ = ["ENV_DATA", "ENV_REPORTS", "REPO_ROOT", "DATA_DIR", "REPORTS_DIR", "PANEL_DIR", "BOC_DIR", "NOTES_DIR",
           "VALIDATION_DIR", "DIAGNOSTIC_DIR", "env_dir", "resolve_dirs", "repo_path", "relocated"]
