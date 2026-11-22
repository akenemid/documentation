"""Écritures atomiques et verrous entre processus.

Écriture atomique (:func:`fichier_atomique`, :func:`ecrire_atomique`, :func:`ecrire_atomique_avec`) :
le contenu est écrit dans un fichier temporaire **du même dossier** (``.<nom>.<pid>.<jeton>.part``),
vidé sur disque (``fsync``), puis renommé sous son nom final (``os.replace``, atomique) ; le dossier
est lui aussi vidé sur disque. Un lecteur voit l'ancien fichier ou le nouveau, jamais un fichier à
moitié écrit ; une écriture interrompue ne laisse qu'un ``.part`` (purgé par :func:`purger_temporaires`).

Verrous (:func:`verrou`) : ``fcntl.flock`` sur un fichier de verrou qui n'est **jamais supprimé**. Le
système libère le verrou à la mort du processus : aucun verrou « périmé » à deviner (numéro de
processus réutilisé, horloge). Un verrou tenu par une autre opération au-delà du délai d'attente lève
:class:`~brvm_alpha.erreurs.VerrouOccupe` (code de sortie 4). Délai par défaut : :data:`DELAI_VERROU_S`,
ou la variable ``BRVM_ALPHA_ATTENTE_VERROU`` (secondes).

En mode embarqué, chaque écriture passe par :func:`brvm_alpha.paths.verifier_ecriture` (rien dans
l'arbre du code).
"""

from __future__ import annotations

import errno
import fcntl
import os
import secrets
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import IO, Any

from brvm_alpha import paths
from brvm_alpha.erreurs import VerrouOccupe

#: Délai d'attente par défaut d'un verrou (s).
DELAI_VERROU_S = 10.0
#: Variable d'environnement qui remplace :data:`DELAI_VERROU_S`.
ENV_ATTENTE = "BRVM_ALPHA_ATTENTE_VERROU"
#: Intervalle entre deux essais de prise du verrou (s).
_PAS_S = 0.05
_SUFFIXE_TEMP = ".part"


def delai_verrou(attente: float | None = None) -> float:
    """Délai d'attente effectif : ``attente`` s'il est donné, sinon ``BRVM_ALPHA_ATTENTE_VERROU``, sinon 10 s."""
    if attente is not None:
        return max(0.0, float(attente))
    raw = str(os.environ.get(ENV_ATTENTE, "") or "").strip()
    try:
        return max(0.0, float(raw)) if raw else DELAI_VERROU_S
    except ValueError:
        return DELAI_VERROU_S


# ---------------------------------------------------------------------------
# Écriture atomique
# ---------------------------------------------------------------------------


def _fsync_dir(folder: Path) -> None:
    try:
        fd = os.open(folder, os.O_RDONLY)
    except OSError:  # pragma: no cover - système sans ouverture de dossier
        return
    try:
        os.fsync(fd)
    except OSError:  # pragma: no cover - système de fichiers sans fsync de dossier
        pass
    finally:
        os.close(fd)


def chemin_temporaire(path: str | Path) -> Path:
    """Fichier temporaire voisin de ``path`` (même dossier, donc même système de fichiers)."""
    p = Path(path)
    return p.with_name(f".{p.name}.{os.getpid()}.{secrets.token_hex(4)}{_SUFFIXE_TEMP}")


@contextmanager
def fichier_atomique(path: str | Path, mode: str = "wb", *, encoding: str | None = None) -> Iterator[IO[Any]]:
    """Fichier ouvert en écriture, publié sous ``path`` seulement si le bloc se termine sans erreur."""
    if "w" not in mode or "+" in mode or "a" in mode:
        raise ValueError("fichier_atomique : mode d'écriture « w » ou « wb » attendu")
    p = paths.verifier_ecriture(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = chemin_temporaire(p)
    fh = open(tmp, mode, encoding=encoding if "b" not in mode else None)  # noqa: SIM115 - fermé ci-dessous
    try:
        yield fh
        fh.flush()
        os.fsync(fh.fileno())
        fh.close()
        os.replace(tmp, p)
        _fsync_dir(p.parent)
    except BaseException:
        fh.close()
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


def ecrire_atomique(path: str | Path, data: bytes | str, *, encoding: str = "utf-8") -> Path:
    """Écrit ``data`` (octets ou texte) sous ``path`` de façon atomique ; renvoie ``Path(path)``."""
    raw = data.encode(encoding) if isinstance(data, str) else bytes(data)
    with fichier_atomique(path, "wb") as fh:
        fh.write(raw)
    return Path(path)


def ecrire_atomique_avec(path: str | Path, ecrire: Callable[[Path], Any]) -> Path:
    """Publie atomiquement le fichier qu'``ecrire(chemin_temporaire)`` produit (parquet, CSV, gzip…).

    ``ecrire`` reçoit un chemin temporaire du même dossier et doit y écrire le fichier complet.
    """
    p = paths.verifier_ecriture(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = chemin_temporaire(p)
    try:
        ecrire(tmp)
        fd = os.open(tmp, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(tmp, p)
        _fsync_dir(p.parent)
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise
    return p


def purger_temporaires(folder: str | Path, age_min_s: float = 3600.0) -> int:
    """Supprime les ``.part`` laissés par une écriture interrompue (plus vieux que ``age_min_s``) ; renvoie leur nombre."""
    n = 0
    now = time.time()
    try:
        entries = list(os.scandir(folder))
    except OSError:
        return 0
    for entry in entries:
        if not (entry.name.startswith(".") and entry.name.endswith(_SUFFIXE_TEMP)):
            continue
        try:
            if entry.is_file(follow_symlinks=False) and now - entry.stat(follow_symlinks=False).st_mtime >= age_min_s:
                os.unlink(entry.path)
                n += 1
        except OSError:
            continue
    return n


_AT_FDCWD = -100
_RENAME_EXCHANGE = 2


def echanger_dossiers(a: str | Path, b: str | Path) -> bool:
    """Échange atomiquement deux chemins existants (``renameat2(RENAME_EXCHANGE)``, Linux).

    Renvoie ``False`` si le système ou le système de fichiers ne le permet pas (rien n'est changé).
    """
    try:
        import ctypes

        libc = ctypes.CDLL(None, use_errno=True)
        fn = libc.renameat2
    except (OSError, AttributeError):
        return False
    fn.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    fn.restype = ctypes.c_int
    if fn(_AT_FDCWD, os.fsencode(str(a)), _AT_FDCWD, os.fsencode(str(b)), _RENAME_EXCHANGE) == 0:
        return True
    err = ctypes.get_errno()
    if err in (errno.EINVAL, errno.ENOSYS, errno.EOPNOTSUPP, errno.EPERM, errno.EXDEV):
        return False
    raise OSError(err, os.strerror(err), str(a))


def remplacer_dossier(nouveau: str | Path, cible: str | Path) -> Path | None:
    """Met le dossier ``nouveau`` à la place de ``cible`` ; rend l'ancien dossier (à supprimer) ou ``None``.

    Échange atomique si possible ; sinon deux renommages (l'ancien est mis de côté sous
    ``.<nom>.ancien-…``, puis le nouveau prend sa place : une coupure entre les deux laisse l'ancien
    intact, récupérable par :func:`recuperer_dossier`). ``nouveau`` doit être dans le même dossier parent.
    """
    new, target = Path(nouveau), paths.verifier_ecriture(cible)
    if not target.exists():
        os.rename(new, target)
        _fsync_dir(target.parent)
        return None
    if echanger_dossiers(new, target):
        _fsync_dir(target.parent)
        return new  # contient maintenant l'ancien
    aside = target.with_name(f".{target.name}.ancien-{os.getpid()}-{secrets.token_hex(4)}")
    os.rename(target, aside)
    try:
        os.rename(new, target)
    except BaseException:
        os.rename(aside, target)
        raise
    _fsync_dir(target.parent)
    return aside


def recuperer_dossier(cible: str | Path) -> bool:
    """Après une bascule interrompue (cible absente, ancien mis de côté) : remet l'ancien ; ``True`` si fait."""
    target = Path(cible)
    if target.exists():
        return False
    try:
        asides = sorted((p for p in target.parent.glob(f".{target.name}.ancien-*") if p.is_dir()),
                        key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError:
        return False
    if not asides:
        return False
    os.rename(asides[0], paths.verifier_ecriture(target))
    return True


# ---------------------------------------------------------------------------
# Verrous (fcntl.flock)
# ---------------------------------------------------------------------------

_tenus = threading.local()


def _registre() -> dict[str, list[Any]]:
    reg = getattr(_tenus, "reg", None)
    if reg is None:
        reg = _tenus.reg = {}
    return reg


def detenteur(path: str | Path) -> str:
    """Description du détenteur inscrite dans le fichier de verrou (« processus 123, depuis … »), ou ``""``."""
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace").strip()[:200]
    except OSError:
        return ""


@contextmanager
def verrou(path: str | Path, *, attente: float | None = None, partage: bool = False, quoi: str | None = None,
           creer: bool = True) -> Iterator[bool]:
    """Verrou ``fcntl.flock`` sur ``path`` (exclusif, ou partagé si ``partage``) ; rend ``True`` s'il est tenu.

    - le fichier de verrou est créé au besoin (sauf ``creer=False`` : s'il n'existe pas, aucun verrou
      n'est pris et le bloc reçoit ``False``, pour un lecteur qui ne doit rien écrire) ; il n'est jamais
      supprimé ;
    - verrou libéré à la sortie du bloc, ou par le système à la mort du processus ;
    - réentrant dans un même fil d'exécution (un exclusif couvre un partagé) ; deux fils d'un même
      processus s'excluent comme deux processus ;
    - au-delà de ``attente`` secondes (:func:`delai_verrou`), :class:`VerrouOccupe` (code 4).
    """
    p = Path(path)
    key = os.path.abspath(p)
    reg = _registre()
    held = reg.get(key)
    if held is not None:
        if held[0] or partage:  # déjà tenu par ce fil : un exclusif couvre tout, un partagé couvre un partagé
            held[1] += 1
            try:
                yield True
            finally:
                held[1] -= 1
            return
        raise VerrouOccupe(f"verrou {quoi or p} : ce fil tient déjà un verrou partagé (passage à l'exclusif impossible).")
    if creer:
        paths.verifier_ecriture(p)
        p.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(p, os.O_RDWR | os.O_CREAT, 0o644)
    else:
        try:
            fd = os.open(p, os.O_RDONLY)
        except FileNotFoundError:
            yield False
            return
    try:
        deadline = time.monotonic() + delai_verrou(attente)
        op = (fcntl.LOCK_SH if partage else fcntl.LOCK_EX) | fcntl.LOCK_NB
        while True:
            try:
                fcntl.flock(fd, op)
                break
            except OSError as exc:
                if exc.errno not in (errno.EAGAIN, errno.EACCES, errno.EWOULDBLOCK):
                    raise
                if time.monotonic() >= deadline:
                    who = detenteur(p)
                    raise VerrouOccupe(
                        f"verrou occupé : {quoi or p} ({who or 'autre opération en cours'}) ; réessayer plus tard."
                    ) from None
                time.sleep(_PAS_S)
        if not partage and creer:
            try:  # pour le diagnostic seulement : la vérité est le verrou du système
                os.ftruncate(fd, 0)
                os.pwrite(fd, f"processus {os.getpid()}, depuis {time.strftime('%Y-%m-%d %H:%M:%S')}"
                              f"{', ' + quoi if quoi else ''}\n".encode("utf-8"), 0)
            except OSError:  # pragma: no cover
                pass
        reg[key] = [not partage, 1]
        try:
            yield True
        finally:
            reg.pop(key, None)
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError:  # pragma: no cover
                pass
    finally:
        os.close(fd)


__all__ = ["DELAI_VERROU_S", "ENV_ATTENTE", "VerrouOccupe", "delai_verrou", "chemin_temporaire", "fichier_atomique",
           "ecrire_atomique", "ecrire_atomique_avec", "purger_temporaires", "echanger_dossiers", "remplacer_dossier",
           "recuperer_dossier", "detenteur", "verrou"]
