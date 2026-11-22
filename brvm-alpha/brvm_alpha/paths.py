"""Emplacements des données et des rapports écrits ; mode embarqué.

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

Mode embarqué
-------------

Le moteur est **embarqué** (copié dans un module Odoo, par exemple) quand la variable
``BRVM_ALPHA_EMBARQUE`` vaut ``1`` ou quand un fichier ``VERSION`` (écrit par
``deploiement/exporter-moteur.sh``) se trouve à la racine du code, à côté du paquet ``brvm_alpha``
(:func:`est_embarque`, seule fonction de détection). Alors :

- ``BRVM_ALPHA_DONNEES`` et ``BRVM_ALPHA_RAPPORTS`` sont **obligatoires**, en chemins absolus, hors
  de l'arbre du code : sinon :func:`resolve_dirs` lève :class:`ConfigurationError` (code de sortie 8).
  Au démarrage, l'erreur est gardée dans :data:`ERREUR_CONFIGURATION` (l'import ne lève jamais) ;
  :func:`verifier_configuration` la relève ;
- aucune écriture dans l'arbre du code : :func:`verifier_ecriture` refuse tout chemin qui s'y trouve
  (fonctions d'écriture de :mod:`brvm_alpha.fichiers`, journal des notes, téléchargement, panel) ;
- un chemin relatif donné en option s'entend depuis ``BRVM_ALPHA_DONNEES``
  (:func:`resoudre_chemin_option`) ;
- la version du code est lue dans ``VERSION`` (:func:`version_livree`).
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from pathlib import Path

from brvm_alpha.erreurs import ConfigurationError, SaisieInvalide

#: Variable d'environnement du dossier de données (défaut : ``<dépôt>/data``).
ENV_DATA = "BRVM_ALPHA_DONNEES"
#: Variable d'environnement du dossier des rapports écrits (défaut : ``<dépôt>/reports``).
ENV_REPORTS = "BRVM_ALPHA_RAPPORTS"
#: Variable d'environnement du mode embarqué (``1`` : actif).
ENV_EMBARQUE = "BRVM_ALPHA_EMBARQUE"
#: Fichier de version écrit à l'export du moteur (sa présence active le mode embarqué).
VERSION_FILE = "VERSION"

#: Racine du dépôt ``brvm-alpha`` (dossier qui contient le paquet ``brvm_alpha``).
REPO_ROOT = Path(__file__).resolve().parents[1]

_VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+:-]{0,63}$")


def _env(environ: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if environ is None else environ


def est_embarque(environ: Mapping[str, str] | None = None, root: str | Path | None = None) -> bool:
    """Vrai si le moteur est embarqué : ``BRVM_ALPHA_EMBARQUE=1`` ou fichier ``VERSION`` à la racine du code."""
    if str(_env(environ).get(ENV_EMBARQUE, "") or "").strip() == "1":
        return True
    return (Path(root) if root is not None else REPO_ROOT).joinpath(VERSION_FILE).is_file()


def version_livree(root: str | Path | None = None) -> str | None:
    """Version écrite dans ``VERSION`` (première ligne non vide), ou ``None`` si le fichier manque ou est illisible."""
    try:
        text = (Path(root) if root is not None else REPO_ROOT).joinpath(VERSION_FILE).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    for line in text.splitlines():
        line = line.strip()
        if line:
            return line if _VERSION_RE.match(line) else None
    return None


def env_dir(name: str, environ: Mapping[str, str] | None = None) -> Path | None:
    """Dossier désigné par la variable ``name`` (chemin absolu), ou ``None`` si elle est vide.

    Un chemin relatif s'entend depuis le dossier courant au démarrage ; ``~`` est accepté.
    """
    raw = str(_env(environ).get(name, "") or "").strip()
    if not raw:
        return None
    return Path(os.path.abspath(os.path.expanduser(raw)))


def _inside(path: Path, folder: Path) -> bool:
    try:
        Path(os.path.abspath(path)).relative_to(Path(os.path.abspath(folder)))
    except ValueError:
        return False
    return True


def dans_le_code(path: str | Path, root: str | Path | None = None) -> bool:
    """Vrai si ``path`` est dans l'arbre du code (``REPO_ROOT`` ou ``root``), liens symboliques résolus."""
    base = Path(root) if root is not None else REPO_ROOT
    p = Path(path)
    if _inside(p, base):
        return True
    try:  # un lien symbolique placé hors du code peut y mener
        return _inside(p.resolve(), base.resolve())
    except OSError:  # pragma: no cover - chemin illisible
        return False


def resolve_dirs(environ: Mapping[str, str] | None = None, root: str | Path | None = None) -> tuple[Path, Path]:
    """``(dossier de données, dossier des rapports écrits)`` pour un environnement donné.

    Mode embarqué (:func:`est_embarque`) : les deux variables sont obligatoires, absolues et hors de
    l'arbre du code ; sinon :class:`ConfigurationError`.
    """
    env = _env(environ)
    code_root = Path(root) if root is not None else REPO_ROOT
    if not est_embarque(env, code_root):
        return (env_dir(ENV_DATA, env) or code_root / "data", env_dir(ENV_REPORTS, env) or code_root / "reports")
    out: list[Path] = []
    for name, what in ((ENV_DATA, "dossier des données"), (ENV_REPORTS, "dossier des rapports écrits")):
        raw = str(env.get(name, "") or "").strip()
        if not raw:
            raise ConfigurationError(
                f"mode embarqué : la variable {name} ({what}) est obligatoire ; donner un chemin absolu hors du "
                "dossier du code.")
        if not os.path.isabs(raw):
            raise ConfigurationError(f"mode embarqué : {name} doit être un chemin absolu (reçu : {raw!r}).")
        p = Path(os.path.normpath(raw))
        if dans_le_code(p, code_root):
            raise ConfigurationError(
                f"mode embarqué : {name} ({p}) est dans le dossier du code ({code_root}) ; aucune écriture n'y est "
                "permise.")
        out.append(p)
    return out[0], out[1]


def _initial_dirs() -> tuple[Path, Path, ConfigurationError | None]:
    try:
        data, reports = resolve_dirs()
    except ConfigurationError as exc:
        # L'import ne lève jamais : la ligne de commande relève l'erreur (verifier_configuration, code 8) ;
        # d'ici là, toute écriture est refusée (verifier_ecriture).
        return REPO_ROOT / "data", REPO_ROOT / "reports", exc
    return data, reports, None


#: Dossiers en vigueur, fixés au démarrage (voir le module).
DATA_DIR, REPORTS_DIR, ERREUR_CONFIGURATION = _initial_dirs()
PANEL_DIR = DATA_DIR / "panel"
BOC_DIR = DATA_DIR / "boc_text"
NOTES_DIR = DATA_DIR / "notes"

#: Résultats de la validation : toujours dans le dépôt, quelles que soient les variables.
VALIDATION_DIR = REPO_ROOT / "reports" / "validation_S1"
DIAGNOSTIC_DIR = REPO_ROOT / "reports" / "diagnostic_S0"


def verifier_configuration() -> None:
    """Lève l'erreur de configuration relevée au démarrage (mode embarqué sans dossiers valides)."""
    if ERREUR_CONFIGURATION is not None:
        raise ConfigurationError(str(ERREUR_CONFIGURATION))


def verifier_ecriture(path: str | Path) -> Path:
    """Contrôle avant toute écriture ; renvoie ``Path(path)``.

    Mode embarqué : refuse (:class:`ConfigurationError`) toute écriture tant que la configuration est
    invalide, et toute écriture dans l'arbre du code. Hors mode embarqué : aucun contrôle (usage
    inchangé, les données peuvent rester dans ``<dépôt>/data``).
    """
    p = Path(path)
    if not est_embarque():
        return p
    verifier_configuration()
    if dans_le_code(p):
        raise ConfigurationError(f"mode embarqué : écriture refusée dans le dossier du code ({p}).")
    return p


def resoudre_chemin_option(value: str | Path | None, *, base: str = "donnees",
                           environ: Mapping[str, str] | None = None) -> Path | None:
    """Chemin donné en option (``--panel-dir``, ``--boc-dir``, ``--racine``, ``--sortie``…).

    Absolu : rendu tel quel. Relatif : hors mode embarqué, depuis le dossier courant (comportement
    actuel) ; en mode embarqué, depuis ``BRVM_ALPHA_DONNEES`` (``base="donnees"``, un ``data/`` de tête
    est retiré : ``data/panel`` → ``<données>/panel``) ou ``BRVM_ALPHA_RAPPORTS`` (``base="rapports"``),
    sans « .. » (:class:`~brvm_alpha.erreurs.SaisieInvalide`). ``None`` ou vide : ``None``.
    """
    if value is None or str(value).strip() == "":
        return None
    p = Path(os.path.expanduser(str(value)))
    if p.is_absolute() or not est_embarque(environ):
        return p
    if base not in ("donnees", "rapports"):
        raise ValueError(f"base inconnue : {base!r} (donnees ou rapports)")
    parts = list(p.parts)
    if ".." in parts:
        raise SaisieInvalide(f"chemin relatif avec « .. » refusé en mode embarqué : {value!s}")
    if base == "donnees" and parts and parts[0] == "data":
        parts = parts[1:]
    return (DATA_DIR if base == "donnees" else REPORTS_DIR).joinpath(*parts)


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


__all__ = ["ENV_DATA", "ENV_REPORTS", "ENV_EMBARQUE", "VERSION_FILE", "REPO_ROOT", "DATA_DIR", "REPORTS_DIR",
           "PANEL_DIR", "BOC_DIR", "NOTES_DIR", "VALIDATION_DIR", "DIAGNOSTIC_DIR", "ERREUR_CONFIGURATION",
           "ConfigurationError", "est_embarque", "version_livree", "env_dir", "dans_le_code", "resolve_dirs",
           "verifier_configuration", "verifier_ecriture", "resoudre_chemin_option", "repo_path", "relocated"]
