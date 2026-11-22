"""Verrou du test unique S1 (additif v1.1, D12 ; spécification §8.4).

S1 (2017-01-02 → 2022-11-16) est exécuté **une seule fois**. Avant l'exécution :

* les fichiers **suivis** sous ``brvm_alpha/`` et ``configs/`` doivent être identiques à
  ``HEAD`` (``git diff --quiet HEAD -- brvm_alpha configs``) **et** aucun fichier non suivi (non
  ignoré) ne doit s'y trouver : un module non commité serait importé sans figurer dans le commit
  enregistré (pré-vol du 22/11/2026 ; ``__pycache__`` et ``*.pyc`` sont ignorés par ``.gitignore``) ;
* le registre ne doit contenir aucun essai S1 « exécuté » et aucun verrou antérieur ne doit
  exister, sauf relance motivée par un **bogue démontré** (``rerun_reason``) : de nouveaux
  essais sont alors créés et l'ancien résultat est conservé dans un sous-dossier daté.

Le verrou (``reports/validation_S1/lock.json``) enregistre le commit, l'empreinte de
configuration (``settings.config_fingerprint``), la version du YAML, l'horodatage UTC et la
liste des runs. Ce module ne calcule aucune performance.
"""

from __future__ import annotations

import hashlib
import json
import math
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pandas as pd

__all__ = [
    "LOCKED_PATHS",
    "LOCK_NAME",
    "PROJECT_ROOT",
    "ValidationRefused",
    "archive_previous",
    "check_rerun",
    "config_identity",
    "fingerprint_check",
    "git_tree_state",
    "read_lock",
    "require_clean_tree",
    "write_lock",
]

#: Nom du fichier de verrou dans le dossier de sortie de S1.
LOCK_NAME = "lock.json"
#: Arborescences dont les fichiers suivis doivent être identiques à ``HEAD`` avant S1.
LOCKED_PATHS: tuple[str, ...] = ("brvm_alpha", "configs")
#: Racine du dépôt (dossier qui contient ``brvm_alpha/``).
PROJECT_ROOT = Path(__file__).resolve().parents[2]
#: Référence de pré-enregistrement de l'additif v1.1 (spécification §8.4) : commit où les décisions
#: D1-D12 ont été figées, AVANT l'état figé du test S1. À ce commit, le YAML était en version 1.0 et
#: les essais S1-A à S1-H portaient l'empreinte ``dcdf1fb7db530c44`` (registre de ce commit).
PREREGISTRATION_COMMIT = "751d1be729ac1501fe672eb47be084c794dac7a9"
PREREGISTERED_FINGERPRINT_V10 = "dcdf1fb7db530c44"
#: État figé exécuté au premier test S1 (commit a2bfeb4, 09:56:15 UTC) : l'empreinte ``f1582ed8e9fa1c85``
#: y apparaît pour la première fois dans le registre (essais S1-I et REF-ID), 11 s avant le run. Ce n'est
#: donc PAS une valeur pré-enregistrée indépendante, mais l'empreinte de l'état figé lui-même.
FROZEN_STATE_COMMIT = "a2bfeb4c9b09c6a97f1208dfd7d585146455b651"
FROZEN_STATE_FINGERPRINT = "f1582ed8e9fa1c85"


def fingerprint_check(current: str | None, registry_fingerprints: Sequence[str] = ()) -> dict[str, Any]:
    """Contrôle de l'empreinte de configuration, sans autoréférence (revue du 22/11/2026).

    ``conforme_etat_fige`` compare l'empreinte courante à celle de l'état figé ``a2bfeb4`` (même
    YAML que le premier test S1, donc mêmes paramètres pour une relance). La référence de
    pré-enregistrement citée est le commit ``751d1be`` (spécification, YAML v1.0, empreinte
    ``dcdf1fb7db530c44``) : le YAML a changé entre les deux commits (clés v1.1 reprenant D1-D12),
    si bien qu'aucune empreinte v1.1 n'a été enregistrée dans un commit antérieur à l'état figé.
    ``conforme`` (clé historique) vaut ``conforme_etat_fige`` ; ``preenregistree_independante``
    vaut toujours faux pour cette empreinte. À l'avenir (S2) : enregistrer l'empreinte dans un
    commit antérieur à l'état figé.
    """
    reg = sorted({str(x) for x in registry_fingerprints if x})
    same = current == FROZEN_STATE_FINGERPRINT
    return {
        "actuelle": current,
        "etat_fige": {"commit": FROZEN_STATE_COMMIT, "empreinte": FROZEN_STATE_FINGERPRINT},
        "conforme_etat_fige": bool(same),
        "conforme": bool(same),
        "registre_s1_i_ref": reg,
        "preenregistree_v11": reg,
        "preenregistree_independante": False,
        "reference_preenregistrement": {
            "commit": PREREGISTRATION_COMMIT, "version_yaml": "1.0", "empreinte_v1_0": PREREGISTERED_FINGERPRINT_V10,
            "note": "spécification inchangée depuis 751d1be ; YAML passé de 1.0 à 1.1 entre 751d1be et a2bfeb4 "
                    "(clés v1.1 = valeurs D1-D12 du §8.4) ; l'empreinte f1582ed8e9fa1c85 est celle de l'état figé "
                    "a2bfeb4, écrite dans le même commit que le run (11 s avant), pas une valeur pré-enregistrée "
                    "indépendante"},
    }


class ValidationRefused(RuntimeError):
    """Exécution refusée (verrou S1, arbre modifié, plan non conforme) : code de sortie 2."""

    exit_code = 2


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=False)


def git_tree_state(repo_root: str | Path | None = None, paths: Sequence[str] = LOCKED_PATHS) -> dict[str, Any]:
    """État git des arborescences verrouillées.

    Renvoie ``commit`` (``HEAD``), ``propre_suivis`` (``git diff --quiet HEAD -- <paths>``
    réussi), ``propre`` (``propre_suivis`` **et** aucun fichier non suivi sous ``paths``),
    ``modifies`` (fichiers suivis différents de ``HEAD``, index compris), ``non_suivis``
    (fichiers non suivis et non ignorés : ils rendent l'arbre non propre) et ``erreur``
    (texte, ou ``None``). Aucune modification du dépôt.
    """
    repo = Path(repo_root) if repo_root is not None else PROJECT_ROOT
    out: dict[str, Any] = {"depot": str(repo), "chemins": list(paths), "commit": None, "propre": False,
                           "propre_suivis": False, "modifies": [], "non_suivis": [], "erreur": None}
    try:
        head = _git(repo, "rev-parse", "HEAD")
    except FileNotFoundError:  # pragma: no cover - git absent
        out["erreur"] = "git introuvable"
        return out
    if head.returncode != 0:
        out["erreur"] = (head.stderr or head.stdout).strip() or "dépôt git introuvable"
        return out
    out["commit"] = head.stdout.strip()
    diff = _git(repo, "diff", "--quiet", "HEAD", "--", *paths)
    if diff.returncode not in (0, 1):
        out["erreur"] = (diff.stderr or "git diff en échec").strip()
        return out
    out["propre_suivis"] = diff.returncode == 0
    names = _git(repo, "diff", "--name-only", "--relative", "HEAD", "--", *paths)
    out["modifies"] = [x for x in names.stdout.splitlines() if x.strip()]
    others = _git(repo, "ls-files", "--others", "--exclude-standard", "--", *paths)
    out["non_suivis"] = [x for x in others.stdout.splitlines() if x.strip()]
    out["propre"] = bool(out["propre_suivis"] and not out["non_suivis"])
    branch = _git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    out["branche"] = branch.stdout.strip() if branch.returncode == 0 else None
    return out


def require_clean_tree(state: Mapping[str, Any]) -> None:
    """Refuse (``ValidationRefused``) si les fichiers suivis verrouillés diffèrent de ``HEAD`` ou si
    un fichier non suivi (non ignoré) se trouve sous les arborescences verrouillées."""
    if state.get("erreur"):
        raise ValidationRefused(f"verrou S1 : état git illisible ({state['erreur']}) : exécution refusée")
    where = " et ".join(f"{p}/" for p in state.get("chemins", LOCKED_PATHS))
    mods = list(state.get("modifies") or [])
    untracked = list(state.get("non_suivis") or [])
    if mods or not state.get("propre_suivis", state.get("propre")):
        raise ValidationRefused(
            f"verrou S1 : les fichiers suivis sous {where} diffèrent de HEAD ({', '.join(mods) or '?'}) : commiter ou "
            "annuler les modifications avant le test unique (git diff --quiet HEAD -- brvm_alpha configs)")
    if untracked:
        raise ValidationRefused(
            f"verrou S1 : fichiers non suivis sous {where} ({', '.join(untracked[:12])}"
            + ("…" if len(untracked) > 12 else "") + ") : ils seraient importés sans figurer dans le commit "
            "enregistré ; les commiter ou les retirer avant le test unique")
    if not state.get("propre"):
        raise ValidationRefused(f"verrou S1 : arbre {where} non propre : exécution refusée")


def config_identity(path: str | Path | None = None) -> dict[str, Any]:
    """Empreinte de configuration (``settings.config_fingerprint``), version et SHA-256 du YAML."""
    from brvm_alpha import settings

    p = Path(path) if path is not None else Path(settings.DEFAULT_STRATEGY_PATH)
    out: dict[str, Any] = {"yaml": str(p), "empreinte_config": None, "version_yaml": None, "sha256_yaml": None,
                           "erreur": None}
    try:
        cfg = settings.load_strategy_config(p)
        out["empreinte_config"] = settings.config_fingerprint(cfg)
        out["version_yaml"] = str(cfg.get("version")) if cfg.get("version") is not None else None
        out["sha256_yaml"] = hashlib.sha256(p.read_bytes()).hexdigest()
    except Exception as exc:  # noqa: BLE001 - rapporté dans le verrou
        out["erreur"] = f"{exc.__class__.__name__} : {exc}"
    return out


def _clean(obj: Any) -> Any:
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, Mapping):
        return {str(k): _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    if isinstance(obj, Path):
        return str(obj)
    return obj


def write_lock(path: str | Path, payload: Mapping[str, Any]) -> Path:
    """Écrit le verrou (JSON UTF-8, clés triées)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(_clean(dict(payload)), ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n",
                 encoding="utf-8")
    return p


def read_lock(path: str | Path) -> dict[str, Any] | None:
    """Verrou existant (``None`` s'il est absent ; ``{"illisible": ...}`` s'il est corrompu)."""
    p = Path(path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {"illisible": f"{exc.__class__.__name__} : {exc}"}


def check_rerun(registry: Any, out_dir: str | Path, rerun_reason: str | None, sample: str = "S1") -> dict[str, Any]:
    """Contrôle du test unique (D12) : renvoie ``{"relance": bool, "motif", "essais_executes", "verrou_precedent"}``.

    Refus (``ValidationRefused``) si le registre contient déjà des essais ``sample``
    « exécuté » **ou** si un verrou antérieur existe (tentative précédente, même inachevée),
    sauf ``rerun_reason`` non vide (bogue démontré : anticipation, comptabilité, données).
    """
    reason = (rerun_reason or "").strip() or None
    done = registry.executed(sample) if hasattr(registry, "executed") else pd.DataFrame()
    ids = sorted(str(x) for x in done["id"]) if len(done) else []
    previous = read_lock(Path(out_dir) / LOCK_NAME)
    if (ids or previous is not None) and reason is None:
        what = []
        if ids:
            what.append(f"{len(ids)} essai(s) {sample} déjà « exécuté » au registre ({', '.join(ids[:12])}"
                        + ("…" if len(ids) > 12 else "") + ")")
        if previous is not None:
            what.append(f"verrou existant ({Path(out_dir) / LOCK_NAME}, statut "
                        f"{previous.get('statut', previous.get('illisible', '?'))})")
        raise ValidationRefused(
            f"test unique {sample} déjà tenté : " + " ; ".join(what)
            + ". Une relance n'est permise que pour un bogue démontré, avec --rerun-reason TEXTE "
            "(nouveaux essais, N augmente, les deux résultats sont publiés).")
    return {"relance": reason is not None and (bool(ids) or previous is not None), "motif": reason,
            "essais_executes": ids, "verrou_precedent": previous}


def archive_previous(out_dir: str | Path, stamp: str) -> Path | None:
    """Déplace les sorties existantes de ``out_dir`` dans ``out_dir/precedent_<stamp>/`` (aucune suppression)."""
    d = Path(out_dir)
    if not d.exists():
        return None
    items = [x for x in d.iterdir() if not x.name.startswith("precedent_")]
    if not items:
        return None
    dest = d / f"precedent_{stamp}"
    k = 1
    while dest.exists():
        k += 1
        dest = d / f"precedent_{stamp}_{k}"
    dest.mkdir(parents=True)
    for x in items:
        shutil.move(str(x), str(dest / x.name))
    return dest
