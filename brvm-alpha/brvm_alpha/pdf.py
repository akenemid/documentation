"""Extraction du texte des PDF : ``pdftotext`` (poppler), repli ``pdfplumber`` hors mode embarqué.

- ``pdftotext`` tourne en sous-processus **borné** (:func:`lancer_outil`) : délai (:data:`DELAI_PDFTOTEXT_S`),
  mémoire virtuelle (:data:`MEMOIRE_OUTIL`) et taille de la sortie (:data:`SORTIE_MAX`) ;
- ``pdfplumber`` (repli pur Python, plus lent) tourne lui aussi dans un **sous-processus** borné en
  durée (:data:`DELAI_PDFPLUMBER_S`) : un PDF pathologique ne fige ni ne gonfle le processus du moteur ;
- en **mode embarqué** (:func:`brvm_alpha.paths.est_embarque`), ``pdftotext`` est obligatoire :
  :class:`~brvm_alpha.erreurs.ConfigurationError` s'il manque, aucun repli silencieux (tout
  l'historique serait sinon converti autrement, et gardé tel quel) ;
- sans ``pdftotext`` ni ``pdfplumber`` : :class:`~brvm_alpha.erreurs.ConfigurationError` (aucune
  conversion, aucun jour marqué sans bulletin à tort) ;
- fichier de plus de :data:`TAILLE_MAX` octets refusé (:class:`ExtractionRatee`).

Aucune exécution de JavaScript : ni poppler ni pdfminer n'en exécutent.
"""

from __future__ import annotations

import functools
import os
import shutil
import subprocess
import sys
from pathlib import Path

from brvm_alpha import paths
from brvm_alpha.erreurs import ConfigurationError

#: Délai d'une extraction par pdftotext (s) : un BOC se convertit en moins de 2 s.
DELAI_PDFTOTEXT_S = 60.0
#: Mémoire virtuelle d'un outil de poppler (pdftotext, pdfinfo, pdffonts, pdfimages) : ``RLIMIT_AS`` de l'enfant.
MEMOIRE_OUTIL = 512 * 2 ** 20
#: Sortie maximale d'un outil (octets) : écrite dans un fichier temporaire borné (``RLIMIT_FSIZE``), jamais gardée
#: entière en mémoire.
SORTIE_MAX = 32 * 2 ** 20
#: Délai d'une extraction par pdfplumber (s), dans un sous-processus.
DELAI_PDFPLUMBER_S = 180.0
#: Taille maximale d'un PDF à convertir (octets).
TAILLE_MAX = 64 * 2 ** 20

_PLUMBER_CODE = (
    "import sys\n"
    "import pdfplumber\n"
    "layout = sys.argv[2] == '1'\n"
    "with pdfplumber.open(sys.argv[1]) as pdf:\n"
    "    pages = [(p.extract_text(layout=True) if layout else p.extract_text()) or '' for p in pdf.pages]\n"
    "sys.stdout.buffer.write('\\n\\f'.join(pages).encode('utf-8', 'replace'))\n"
)


class ExtractionRatee(RuntimeError):
    """Le texte d'un PDF n'a pas pu être extrait (fichier illisible, trop gros, délai dépassé)."""


def _limites_outil(memoire: int, sortie: int):
    def poser() -> None:  # dans l'enfant, avant exec : rien d'autre que des appels système
        import resource

        for lim, val in ((resource.RLIMIT_AS, memoire), (resource.RLIMIT_FSIZE, sortie), (resource.RLIMIT_CORE, 0)):
            try:
                _soft, hard = resource.getrlimit(lim)
                v = val if hard == resource.RLIM_INFINITY else min(val, hard)
                resource.setrlimit(lim, (v, hard))
            except (ValueError, OSError):
                pass
    return poser


def lancer_outil(cmd: list[str], *, delai: float, memoire: int = MEMOIRE_OUTIL,
                 sortie: int = SORTIE_MAX) -> tuple[int, bytes, bytes]:
    """``(code, sortie, erreurs)`` d'un outil de poppler, **borné** : durée (``delai``), mémoire virtuelle
    (``memoire``, ``RLIMIT_AS``) et taille de la sortie (``sortie`` : fichier temporaire limité par
    ``RLIMIT_FSIZE``, l'outil est arrêté au-delà). Un PDF piégé ne peut ni figer le moteur, ni lui faire garder des
    dizaines de mégaoctets en mémoire, ni monter à plus de ``memoire`` octets. :class:`ExtractionRatee` si l'outil
    est arrêté (délai, mémoire, sortie trop grosse) ; ``OSError`` s'il ne peut pas être lancé.
    """
    import signal
    import tempfile

    name = Path(cmd[0]).name
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                preexec_fn=_limites_outil(int(memoire), int(sortie)), close_fds=True)
        try:
            code = proc.wait(timeout=delai)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            raise ExtractionRatee(f"{name} : délai de {delai:.0f} s dépassé.") from None
        except BaseException:
            proc.kill()
            proc.wait()
            raise
        if code == -signal.SIGXFSZ:
            raise ExtractionRatee(f"{name} : sortie de plus de {sortie // 2 ** 20} Mo, outil arrêté.")
        if code in (-signal.SIGSEGV, -signal.SIGABRT, -signal.SIGKILL, -signal.SIGBUS):
            raise ExtractionRatee(f"{name} : arrêté par le signal {-code} (mémoire de {memoire // 2 ** 20} Mo "
                                  "dépassée ou PDF piégé).")
        out.seek(0)
        data = out.read(int(sortie) + 1)
        err.seek(0)
        errors = err.read(64 * 1024)
    if len(data) > sortie:  # pragma: no cover - RLIMIT_FSIZE l'aurait arrêté
        raise ExtractionRatee(f"{name} : sortie de plus de {sortie // 2 ** 20} Mo.")
    return code, data, errors


def pdftotext_disponible() -> bool:
    return shutil.which("pdftotext") is not None


@functools.lru_cache(maxsize=1)
def _pdfplumber_present() -> bool:
    import importlib.util

    try:
        return importlib.util.find_spec("pdfplumber") is not None
    except (ImportError, ValueError):  # pragma: no cover
        return False


@functools.lru_cache(maxsize=1)
def version_pdftotext() -> str | None:
    """Version de pdftotext (« 24.02.0 »), ou ``None``."""
    exe = shutil.which("pdftotext")
    if not exe:
        return None
    try:
        out = subprocess.run([exe, "-v"], capture_output=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    text = (out.stderr or out.stdout or b"").decode("utf-8", "replace")
    for line in text.splitlines():
        if "version" in line.lower():
            return line.split()[-1].strip()
    return None


@functools.lru_cache(maxsize=1)
def version_pdfplumber() -> str | None:
    """Version de pdfplumber (sans l'importer dans ce processus), ou ``None``."""
    try:
        from importlib.metadata import version

        return version("pdfplumber")
    except MemoryError:  # mémoire insuffisante : la commande s'arrête (code 6)
        raise
    except Exception:  # noqa: BLE001 - paquet absent
        return None


def extracteur(embarque: bool | None = None) -> str:
    """Extracteur disponible (``"pdftotext"`` ou ``"pdfplumber"``) ; :class:`ConfigurationError` sinon."""
    emb = paths.est_embarque() if embarque is None else bool(embarque)
    if pdftotext_disponible():
        return "pdftotext"
    if emb:
        raise ConfigurationError("pdftotext absent : installer poppler-utils (mode embarqué : pdftotext est "
                                 "obligatoire pour convertir les PDF, aucun repli n'est permis).")
    if _pdfplumber_present():
        return "pdfplumber"
    raise ConfigurationError("pdftotext absent : installer poppler-utils (aucun extracteur PDF : ni pdftotext ni "
                             "pdfplumber).")


def _verifier_taille(path: Path) -> None:
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise ExtractionRatee(f"PDF introuvable : {path} ({exc})") from exc
    if size > TAILLE_MAX:
        raise ExtractionRatee(f"PDF de {size} octets, au-delà du plafond de {TAILLE_MAX} octets : non converti.")


def par_pdftotext(path: str | Path, *, layout: bool = True, delai: float = DELAI_PDFTOTEXT_S) -> str:
    """Texte par ``pdftotext`` (sortie gardée même si le code de retour signale un PDF un peu abîmé)."""
    p = Path(path)
    _verifier_taille(p)
    exe = shutil.which("pdftotext")
    if not exe:
        raise ConfigurationError("pdftotext absent : installer poppler-utils.")
    cmd = [exe, *(["-layout"] if layout else []), str(p), "-"]
    try:
        _code, out, _err = lancer_outil(cmd, delai=delai)
    except ExtractionRatee as exc:
        raise ExtractionRatee(f"{exc} ({p.name})") from exc
    except OSError as exc:
        raise ExtractionRatee(f"pdftotext : {exc}") from exc
    return out.decode("utf-8", errors="replace")


def par_pdfplumber(path: str | Path, *, layout: bool = True, delai: float = DELAI_PDFPLUMBER_S) -> str:
    """Texte par ``pdfplumber``, dans un sous-processus tué au-delà de ``delai`` secondes."""
    p = Path(path)
    _verifier_taille(p)
    if paths.est_embarque():
        raise ConfigurationError("mode embarqué : pdfplumber n'est pas utilisé (pdftotext obligatoire).")
    if not _pdfplumber_present():
        raise ConfigurationError("pdfplumber n'est pas installé.")
    # « -I » : ni PYTHONPATH ni dossier courant dans sys.path ; dossier courant : le dossier temporaire du système
    # (pas celui du PDF, où un fichier pdfplumber.py posé à côté serait importé) ; environnement réduit.
    import tempfile

    cmd = [sys.executable, "-I", "-c", _PLUMBER_CODE, str(p.resolve()), "1" if layout else "0"]
    env = {k: os.environ[k] for k in ("PATH", "LANG", "LC_ALL", "HOME", "TMPDIR", "SYSTEMROOT") if k in os.environ}
    env.update({"OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "PYTHONIOENCODING": "utf-8"})
    try:
        out = subprocess.run(cmd, capture_output=True, timeout=delai, cwd=tempfile.gettempdir(), env=env)
    except subprocess.TimeoutExpired as exc:
        raise ExtractionRatee(f"pdfplumber : délai de {delai:.0f} s dépassé ({p.name}).") from exc
    except OSError as exc:
        raise ExtractionRatee(f"pdfplumber : {exc}") from exc
    if out.returncode != 0:
        err = (out.stderr or b"").decode("utf-8", "replace").strip().splitlines()
        raise ExtractionRatee(f"pdfplumber : {err[-1] if err else 'échec'} ({p.name}).")
    return out.stdout.decode("utf-8", errors="replace")


def extraire_texte(path: str | Path, *, layout: bool = True, embarque: bool | None = None) -> tuple[str, str, str | None]:
    """``(texte, extracteur, version)`` d'un PDF : pdftotext, sinon (hors mode embarqué) pdfplumber.

    pdftotext d'abord ; texte vide et repli permis : pdfplumber. Lève :class:`ConfigurationError` si
    aucun extracteur n'est utilisable, :class:`ExtractionRatee` si le texte n'a pas pu être lu.
    """
    emb = paths.est_embarque() if embarque is None else bool(embarque)
    first = extracteur(emb)
    if first == "pdftotext":
        text = par_pdftotext(path, layout=layout)
        if text.strip() or emb or not _pdfplumber_present():
            return text, "pdftotext", version_pdftotext()
    text = par_pdfplumber(path, layout=layout)
    return text, "pdfplumber", version_pdfplumber()


__all__ = ["DELAI_PDFTOTEXT_S", "DELAI_PDFPLUMBER_S", "TAILLE_MAX", "MEMOIRE_OUTIL", "SORTIE_MAX", "ExtractionRatee",
           "lancer_outil", "pdftotext_disponible",
           "version_pdftotext", "version_pdfplumber", "extracteur", "par_pdftotext", "par_pdfplumber",
           "extraire_texte"]
