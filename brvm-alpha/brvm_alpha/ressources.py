"""Ressources du processus : processeurs disponibles, fils de calcul, réservation de mémoire.

Le moteur embarqué tourne dans un sous-processus d'Odoo, qui borne la **mémoire virtuelle** de ses
travailleurs (``limit_memory_hard``) : le sous-processus en hérite. Or chaque fil de calcul réserve de
la mémoire virtuelle (pile, zone de ``malloc``), et l'allocateur par défaut d'Arrow (jemalloc) en
réserve beaucoup d'avance. Mesures (Python 3.11, jeu minimal, panel complet) : ``etat`` 1,9 Go de pic
de mémoire virtuelle par défaut, 0,55 Go avec un seul fil BLAS et le pool mémoire « system »
d'Arrow ; ``recommend`` 2,3 Go puis 0,9 Go. Le calcul est le même : seule la réservation change.

- :func:`processeurs_disponibles` : processeurs autorisés (``sched_getaffinity``) bornés par le quota
  du cgroup (``/sys/fs/cgroup/cpu.max`` en v2, ``cpu.cfs_quota_us`` / ``cpu.cfs_period_us`` en v1) ;
- :func:`workers_par_defaut` : processus de travail du panel, ``min(2, processeurs disponibles)`` ;
- :func:`limiter_fils` : ``OMP_NUM_THREADS``, ``OPENBLAS_NUM_THREADS``, ``MKL_NUM_THREADS``… à 1
  (à poser **avant** l'import de numpy, donc dans l'environnement d'un processus à lancer) ;
- :func:`regler_processus_embarque` : réglages du processus courant en mode embarqué (appelé par
  ``brvm_alpha/__init__.py`` avant tout import lourd) ;
- :func:`initialiser_travailleur` : réglages d'un processus de travail (pyarrow à 1 fil).

Une variable déjà posée par l'appelant n'est jamais écrasée.
"""

from __future__ import annotations

import os
import sys
from collections.abc import MutableMapping
from pathlib import Path

#: Variables qui bornent les fils des bibliothèques de calcul (lues à l'import de numpy).
VARIABLES_FILS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS",
                  "VECLIB_MAXIMUM_THREADS")
#: Pool mémoire d'Arrow (lu à la première allocation) : « system » (malloc) au lieu de jemalloc.
VARIABLE_POOL_ARROW = "ARROW_DEFAULT_MEMORY_POOL"
#: Nombre de processus de travail du panel au plus, par défaut.
WORKERS_MAX = 2
#: Arènes de malloc au plus en mode embarqué (chaque arène réserve 64 Mo de mémoire virtuelle).
ARENES_MALLOC = 2
_M_ARENA_MAX = -8  # constante de glibc (malloc.h)


def _cgroup_quota(root: Path = Path("/sys/fs/cgroup")) -> float | None:
    """Quota de processeurs du cgroup (``cpu.max`` v2 ou ``cfs_quota_us`` v1), ``None`` sans quota."""
    try:
        text = (root / "cpu.max").read_text().split()
        if text and text[0] != "max":
            quota, period = float(text[0]), float(text[1]) if len(text) > 1 else 100000.0
            if quota > 0 and period > 0:
                return quota / period
        elif text:
            return None
    except (OSError, ValueError, IndexError):
        pass
    for base in (root / "cpu", root / "cpu,cpuacct", root):
        try:
            quota = float((base / "cpu.cfs_quota_us").read_text().strip())
            period = float((base / "cpu.cfs_period_us").read_text().strip())
        except (OSError, ValueError):
            continue
        if quota > 0 and period > 0:
            return quota / period
        return None
    return None


def processeurs_disponibles(cgroup_root: str | Path = "/sys/fs/cgroup") -> int:
    """Processeurs réellement utilisables : affinité du processus bornée par le quota du cgroup (au moins 1)."""
    try:
        n = len(os.sched_getaffinity(0))
    except (AttributeError, OSError):  # pragma: no cover - système sans affinité
        n = os.cpu_count() or 1
    quota = _cgroup_quota(Path(cgroup_root))
    if quota is not None:
        n = min(n, max(1, int(quota)))  # quota 1,5 → 1 processeur entier
    return max(1, n)


def workers_par_defaut(plafond: int = WORKERS_MAX) -> int:
    """Processus de travail par défaut : ``min(plafond, processeurs disponibles)``."""
    return max(1, min(int(plafond), processeurs_disponibles()))


def limiter_fils(environ: MutableMapping[str, str] | None = None, n: int = 1) -> MutableMapping[str, str]:
    """Pose les variables de :data:`VARIABLES_FILS` à ``n`` (sans écraser une valeur déjà posée) ; rend l'environnement."""
    env = os.environ if environ is None else environ
    for name in VARIABLES_FILS:
        env.setdefault(name, str(int(n)))
    return env


def limiter_arenes(n: int = ARENES_MALLOC) -> bool:
    """Borne le nombre d'arènes de malloc (glibc, ``mallopt``) ; ``False`` si c'est impossible ici."""
    if not sys.platform.startswith("linux") or os.environ.get("MALLOC_ARENA_MAX"):
        return False
    try:
        import ctypes

        libc = ctypes.CDLL(None)
        return bool(libc.mallopt(_M_ARENA_MAX, int(n)))
    except Exception:  # pragma: no cover - libc sans mallopt (musl…)
        return False


def regler_arrow(n: int = 1) -> bool:
    """pyarrow (s'il est déjà importé) : ``n`` fils de calcul et d'entrée-sortie ; ``False`` sinon."""
    pa = sys.modules.get("pyarrow")
    if pa is None:
        return False
    try:
        pa.set_cpu_count(int(n))
        pa.set_io_thread_count(int(n))
    except Exception:  # pragma: no cover - version de pyarrow sans ces réglages
        return False
    return True


def regler_processus_embarque(environ: MutableMapping[str, str] | None = None) -> None:
    """Mode embarqué : un fil de calcul, pool mémoire « system » d'Arrow, deux arènes de malloc.

    À appeler avant l'import de numpy et de pyarrow (``brvm_alpha/__init__.py``) ; sans effet sur une
    variable déjà posée par le lanceur.
    """
    env = os.environ if environ is None else environ
    limiter_fils(env)
    env.setdefault(VARIABLE_POOL_ARROW, "system")
    if environ is None:
        limiter_arenes()
        regler_arrow(1)


def initialiser_travailleur() -> None:
    """Initialisation d'un processus de travail : pyarrow à un fil (les variables BLAS viennent du parent)."""
    regler_arrow(1)


__all__ = ["VARIABLES_FILS", "VARIABLE_POOL_ARROW", "WORKERS_MAX", "ARENES_MALLOC", "processeurs_disponibles",
           "workers_par_defaut", "limiter_fils", "limiter_arenes", "regler_arrow", "regler_processus_embarque",
           "initialiser_travailleur"]
