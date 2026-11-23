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
- :func:`initialiser_travailleur` : réglages d'un processus de travail (pyarrow à 1 fil) ;
- :func:`preparer_lien_parent` : lien au parent d'un outil lancé par ``subprocess`` (outils de poppler).

Une variable déjà posée par l'appelant n'est jamais écrasée.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable, MutableMapping
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
    except MemoryError:  # mémoire insuffisante : la commande s'arrête (code 6)
        raise
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
    except MemoryError:  # mémoire insuffisante : la commande s'arrête (code 6)
        raise
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


_GARDE_CHARGEMENT = False


def _motif_memoire(exc: BaseException) -> bool:
    from brvm_alpha import erreurs

    return erreurs.est_memoire(exc)


def installer_garde_chargement() -> bool:
    """Une bibliothèque compilée (``.so``) impossible à charger **faute de mémoire** lève ``MemoryError``.

    Sous une limite de mémoire virtuelle, ``dlopen`` échoue avec « failed to map segment from shared object » :
    Python en fait une ``ImportError``, que le code prend pour un module absent (repli silencieux, résultat
    dégradé). Le chargeur des extensions est remplacé par une sous-classe qui transforme cette erreur, et elle
    seule, en ``MemoryError`` (code 6). Idempotent ; ``False`` si l'interpréteur ne s'y prête pas.
    """
    try:
        import importlib._bootstrap_external as ext  # chargeurs standard (stables depuis Python 3.4)
        import importlib.machinery as machinery
    except ImportError:  # pragma: no cover
        return False
    global _GARDE_CHARGEMENT
    if _GARDE_CHARGEMENT:
        return True

    class ChargeurExtension(machinery.ExtensionFileLoader):
        def create_module(self, spec):  # noqa: D401 - surcharge
            try:
                return super().create_module(spec)
            except ImportError as exc:
                if _motif_memoire(exc):
                    raise MemoryError(f"mémoire insuffisante pour charger {spec.origin} : {exc}") from exc
                raise

    try:
        loaders = [(ChargeurExtension if cls is machinery.ExtensionFileLoader else cls, suffixes)
                   for cls, suffixes in ext._get_supported_file_loaders()]
        for i, hook in enumerate(sys.path_hooks):
            if getattr(hook, "__name__", "") == "path_hook_for_FileFinder":
                sys.path_hooks[i] = machinery.FileFinder.path_hook(*loaders)
                break
        else:  # pragma: no cover - interpréteur sans FileFinder
            return False
        sys.path_importer_cache.clear()
    except MemoryError:  # mémoire insuffisante : la commande s'arrête (code 6)
        raise
    except Exception:  # pragma: no cover - interpréteur inattendu : chargement standard  # noqa: BLE001
        return False
    _GARDE_CHARGEMENT = True
    return True


def _pdeathsig(sig: int) -> bool:
    """Linux : le noyau envoie ``sig`` à ce processus quand son parent meurt (``PR_SET_PDEATHSIG``)."""
    if not sys.platform.startswith("linux"):
        return False
    try:
        import ctypes

        libc = ctypes.CDLL(None, use_errno=True)
        return libc.prctl(1, int(sig), 0, 0, 0) == 0  # 1 = PR_SET_PDEATHSIG
    except MemoryError:  # mémoire insuffisante : la commande s'arrête (code 6)
        raise
    except Exception:  # pragma: no cover - libc sans prctl  # noqa: BLE001
        return False


def lier_au_parent(parent: int | None = None) -> bool:
    """Processus de travail : il meurt avec son parent (``PR_SET_PDEATHSIG`` = ``SIGKILL``).

    Sans cela, si seul le processus principal est tué (tueur de mémoire du noyau, ``KILL`` au seul PID), le
    serveur de processus et les travailleurs du panel restent vivants, rattachés au processus 1 (le maître Odoo
    dans le conteneur). ``parent`` : PID attendu du parent ; s'il est déjà mort (course au démarrage), le
    processus s'arrête aussitôt.
    """
    import signal

    ok = _pdeathsig(signal.SIGKILL)
    if ok and parent is not None and os.getppid() != parent:
        os._exit(1)  # parent mort avant la pose : rien à faire pour personne
    return ok


def preparer_lien_parent() -> Callable[[], None] | None:
    """Sous-processus lancé par ``subprocess`` (outils de poppler) : fonction à appeler **dans l'enfant**, avant
    ``exec`` (``preexec_fn``), qui le lie au processus courant (``PR_SET_PDEATHSIG`` = ``SIGKILL``, gardé par
    ``exec``). Si le moteur meurt seul (``KILL`` au seul PID, tueur de mémoire du noyau), l'outil meurt avec lui au
    lieu d'être récolté par le processus 1 (le maître Odoo) avec son propre code de sortie (poppler documente le
    code 3).

    Tout est préparé ici, dans le parent : l'enfant ne charge aucune bibliothèque après ``fork``. Le lien vaut pour
    le fil qui lance l'outil (le fil principal dans le moteur). ``None`` hors Linux ou sans ``prctl``.
    """
    if not sys.platform.startswith("linux"):
        return None
    import signal

    try:
        import ctypes

        prctl = ctypes.CDLL(None, use_errno=True).prctl
        prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong]
        prctl.restype = ctypes.c_int
    except MemoryError:  # mémoire insuffisante : la commande s'arrête (code 6)
        raise
    except Exception:  # pragma: no cover - libc sans prctl  # noqa: BLE001
        return None
    parent, sig = os.getpid(), int(signal.SIGKILL)

    def lier() -> None:  # dans l'enfant, avant exec : un appel système, rien d'autre
        prctl(1, sig, 0, 0, 0)  # 1 = PR_SET_PDEATHSIG
        if os.getppid() != parent:
            os._exit(1)  # parent mort avant la pose : l'outil ne démarre pas

    return lier


def initialiser_travailleur(parent: int | None = None) -> None:
    """Initialisation d'un processus de travail du panel : lié à son parent (:func:`lier_au_parent`), pyarrow à
    un fil (les variables BLAS viennent du parent)."""
    lier_au_parent(parent)
    regler_arrow(1)


__all__ = ["VARIABLES_FILS", "VARIABLE_POOL_ARROW", "WORKERS_MAX", "ARENES_MALLOC", "processeurs_disponibles",
           "workers_par_defaut", "limiter_fils", "limiter_arenes", "regler_arrow", "regler_processus_embarque",
           "installer_garde_chargement", "lier_au_parent", "preparer_lien_parent", "initialiser_travailleur"]
