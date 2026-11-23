"""Suivi sur papier (S2) du module « Rendement net et pertes » (cahier ``docs/RENDEMENT_NET.md``, §8, F9, F10, F12).

Le suivi commence le mardi 01/12/2026. Il ne promet rien : il compte, chaque semaine, les frais payés, l'argent qui
dort, les ordres servis et l'écart au marché, et il dit d'où vient chaque franc gagné ou perdu. Aucune fonction de ce
paquet ne vend, ne passe d'ordre réel ni n'envoie de requête réseau.

Modules (importés à la demande) :

* :mod:`~brvm_alpha.suivi.declaration` (F9) : articles de la déclaration du suivi, chaîne d'empreintes, signature par
  initiales, inscription au registre des essais (sur commande explicite de l'humain seulement) ;
* :mod:`~brvm_alpha.suivi.temoin` (F10) : fabrique ``temoin_model`` et portefeuilles ``REF-S2`` et ``N`` produits par
  le moteur existant, sans le modifier ;
* :mod:`~brvm_alpha.suivi.carnet` (F12) : journal en ajout seul, prix de revient, avis d'opéré ;
* :mod:`~brvm_alpha.suivi.papier` (F12) : exécution sur papier (modes ``limite`` et ``test``) ;
* :mod:`~brvm_alpha.suivi.etat` (F12) : valeur et pont « fuites / pertes latentes », une seule base ;
* :mod:`~brvm_alpha.suivi.bulletin` (F10) : ligne de la semaine, journal hebdomadaire chaîné, bulletin texte,
  Markdown et JSON.

Ce module définit les règles communes : refus des dates de l'échantillon S1 (≤ 16/11/2022), dossiers du suivi
(toujours un paramètre ``dossier`` ; jamais sous ``reports/``), fichiers en ajout seul et chaînes d'empreintes.

Performance passée ≠ garantie. Aucun gain n'est garanti.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import math
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd

from brvm_alpha import paths as _paths

__all__ = ["BANNER", "S1_FIN", "SOUS_MODULES", "ZERO", "DossierInterdit", "DateDeS1", "ajouter_jsonl", "canonique",
           "dossier_portefeuille", "dossier_suivi", "empreinte", "empreinte_texte", "ligne_json", "lire_jsonl", "refuser_s1",
           "sous_reports", "verifier_hors_reports"]

#: Bandeau permanent (identique à ``recommend.BANNER`` et à ``rendement.reglages.BANNER``).
BANNER = "Performance passée ≠ garantie. Aucun gain n'est garanti."
#: Dernière date de l'échantillon vierge S1 (test unique, déjà consommé) : aucune règle n'est simulée jusqu'à elle.
S1_FIN = pd.Timestamp("2022-11-16")
#: Empreinte de départ d'une chaîne (aucune ligne précédente).
ZERO = "0" * 64
SOUS_MODULES = ("bulletin", "carnet", "declaration", "etat", "papier", "temoin")


class DateDeS1(ValueError):
    """Date de l'échantillon S1 (≤ 16/11/2022) : refusée par le suivi, le carnet et l'exécution sur papier."""


class DossierInterdit(ValueError):
    """Écriture refusée : le suivi n'écrit jamais sous ``reports/`` (résultats publiés, registre des essais)."""


def refuser_s1(date: Any, quoi: str = "cette date") -> pd.Timestamp:
    """Date normalisée ; ``DateDeS1`` si elle tombe dans l'échantillon S1 (≤ 16/11/2022)."""
    t = pd.Timestamp(date).normalize()
    if t <= S1_FIN:
        raise DateDeS1(f"refusé : {quoi} au {t:%d/%m/%Y} tombe dans l'échantillon S1 (jusqu'au 16/11/2022), "
                       "fermé : aucune règle n'y est simulée")
    return t


def dossier_suivi(dossier: str | Path | None = None) -> Path:
    """Dossier des journaux du suivi : ``dossier`` s'il est donné, sinon ``<données>/suivi``."""
    return Path(dossier) if dossier is not None else _paths.DATA_DIR / "suivi"


def sous_reports(chemin: str | Path) -> bool:
    """Vrai si ``chemin`` est sous le dossier ``reports/`` du dépôt (résultats publiés, registre)."""
    p = Path(os.path.abspath(chemin))
    r = Path(os.path.abspath(_paths.REPO_ROOT / "reports"))
    return p == r or r in p.parents


def verifier_hors_reports(chemin: str | Path) -> Path:
    """``chemin`` ; ``DossierInterdit`` s'il est sous ``reports/`` du dépôt."""
    if sous_reports(chemin):
        raise DossierInterdit(f"refusé : le suivi n'écrit jamais sous reports/ ({chemin})")
    return Path(chemin)


def dossier_portefeuille(nom: str, dossier: str | Path | None = None, *, creer: bool = False) -> Path:
    """Dossier d'un portefeuille suivi (``<dossier>/<nom>``) ; jamais sous ``reports/``."""
    n = str(nom).strip()
    if not n or any(c in n for c in "/\\") or n.startswith("."):
        raise ValueError(f"nom de portefeuille invalide : {nom!r}")
    p = verifier_hors_reports(dossier_suivi(dossier) / n)
    if creer:
        p.mkdir(parents=True, exist_ok=True)
    return p


def verrou_ecriture(dossier: str | Path, quoi: str = "journal du suivi") -> Any:
    """Verrou exclusif d'écriture d'un dossier du suivi, à tenir autour de la lecture de la chaîne et de l'ajout : deux
    écritures simultanées (une saisie pendant « suivi maj », deux commandes lancées au même instant) ne rompent jamais
    la chaîne. Le verrou porte sur le dossier lui-même (``flock``) : aucun fichier n'est ajouté au dossier (créé au
    besoin, puisqu'une écriture suit). Réentrant dans un même fil d'exécution ; tenu par une autre opération au-delà du
    délai d'attente (``BRVM_ALPHA_ATTENTE_VERROU``, 10 s par défaut) : ``VerrouOccupe``, code de sortie 4."""
    from brvm_alpha import fichiers

    d = _paths.verifier_ecriture(Path(dossier))
    d.mkdir(parents=True, exist_ok=True)
    return fichiers.verrou(d, quoi=quoi, creer=False)


# ---------------------------------------------------------------------------
# Empreintes et fichiers en ajout seul
# ---------------------------------------------------------------------------


def _jsonable(x: Any) -> Any:
    if isinstance(x, Mapping):
        return {str(k): _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple, set)):
        return [_jsonable(v) for v in (sorted(x) if isinstance(x, set) else x)]
    if isinstance(x, pd.Timestamp):
        return None if pd.isna(x) else x.isoformat()
    if isinstance(x, float):
        return x if math.isfinite(x) else None
    if hasattr(x, "item") and not isinstance(x, (str, bytes)):
        try:
            return _jsonable(x.item())
        except Exception:  # noqa: BLE001
            return str(x)
    if hasattr(x, "isoformat"):
        return x.isoformat()
    if x is None or isinstance(x, (str, int, bool)):
        return x
    return str(x)


def canonique(obj: Any) -> str:
    """Texte JSON canonique (clés triées, sans espace superflu, accents gardés) : base des empreintes."""
    return json.dumps(_jsonable(obj), sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def empreinte_texte(texte: str) -> str:
    """SHA-256 (hexadécimal) d'un texte UTF-8."""
    return hashlib.sha256(str(texte).encode("utf-8")).hexdigest()


def empreinte(obj: Any) -> str:
    """SHA-256 du texte canonique d'un objet."""
    return empreinte_texte(canonique(obj))


def ligne_json(obj: Mapping[str, Any]) -> str:
    """Texte exact d'une ligne JSONL écrite par le suivi (accents gardés) : base de la chaîne ``precedente``."""
    return json.dumps(_jsonable(obj), ensure_ascii=False, separators=(", ", ": "))


def lire_jsonl(chemin: str | Path) -> list[tuple[str, dict[str, Any] | None]]:
    """Lignes d'un fichier JSONL : ``(texte brut, objet)`` ; objet ``None`` si la ligne est illisible."""
    p = Path(chemin)
    if not p.exists():
        return []
    out: list[tuple[str, dict[str, Any] | None]] = []
    for brut in p.read_text(encoding="utf-8").splitlines():
        if not brut.strip():
            continue
        try:
            obj = json.loads(brut)
            out.append((brut, obj if isinstance(obj, dict) else None))
        except json.JSONDecodeError:
            out.append((brut, None))
    return out


def ajouter_jsonl(chemin: str | Path, objets: Iterable[Mapping[str, Any]], *, hors_reports: bool = True) -> list[str]:
    """Ajoute des lignes JSON à la fin du fichier (jamais de réécriture) ; rend les lignes écrites.

    ``hors_reports`` (défaut) : refus sous ``reports/``. Seule la déclaration signée par l'humain
    (``reports/suivi_S2/declaration.jsonl``, commande explicite) passe ``hors_reports=False``."""
    p = verifier_hors_reports(chemin) if hors_reports else Path(chemin)
    p.parent.mkdir(parents=True, exist_ok=True)
    lignes = [ligne_json(o) for o in objets]
    if not lignes:
        return []
    with p.open("a", encoding="utf-8") as fh:
        for ligne in lignes:
            fh.write(ligne + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    return lignes


def __getattr__(nom: str) -> Any:
    """Sous-modules importés à la demande (``brvm_alpha.suivi.carnet``…)."""
    if nom in SOUS_MODULES:
        return importlib.import_module(f"{__name__}.{nom}")
    raise AttributeError(f"module {__name__!r} has no attribute {nom!r}")
