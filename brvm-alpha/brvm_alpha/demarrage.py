"""Démarrage de ``python -m brvm_alpha`` : garde posée **avant** tout import lourd (pandas, numpy, pyarrow).

Ce module n'utilise que la bibliothèque standard et :mod:`brvm_alpha.erreurs` : il tourne avant l'import
de la ligne de commande (:mod:`brvm_alpha.cli`), qui charge pandas. Il tient le contrat même quand ce
chargement échoue :

- **signal TERM** : traité comme une interruption dès le démarrage (code 130, objet JSON
  ``"erreur": "interruption"``), y compris pendant le chargement de pandas ;
- **mémoire** : sous une limite de mémoire virtuelle (``RLIMIT_AS``) inférieure à
  :data:`SEUIL_MEMOIRE_MO` Mo (réglable par ``BRVM_ALPHA_MEMOIRE_MIN``, en Mo ; ``0`` : aucun contrôle),
  rien n'est chargé et la commande sort en 6. Sous ce seuil, numpy, OpenBLAS ou Arrow échouent au
  chargement sans objet JSON (codes 1, 127, −11), ou se figent sans répondre au signal TERM ;
- **échec au chargement du paquet** : ``MemoryError`` ou bibliothèque impossible à charger faute de
  mémoire → 6 ; paquet manquant ou installation abîmée (``ImportError``) → 8 ; interruption → 130 ;
  autre → 7, avec la trace sur la sortie d'erreur ;
- avec ``--format json``, la sortie standard porte **exactement un objet JSON** dans tous ces cas ;
- le code de sortie est toujours un code de la table (:data:`brvm_alpha.erreurs.CODES`), **jamais 3**.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from collections.abc import Mapping, Sequence
from typing import Any

from brvm_alpha import erreurs

BANDEAU = "Performance passée ≠ garantie. Aucun gain n'est garanti."
#: Limite de mémoire virtuelle minimale (Mo). Mesures du mode embarqué : 0,8 Go au plus (``recommend``,
#: ``panel --force``) ; sous 1 Go, le chargement de numpy et de pyarrow devient aléatoire.
SEUIL_MEMOIRE_MO = 1024
#: Variable d'environnement du seuil (Mo) ; ``0`` désactive le contrôle.
ENV_MEMOIRE_MIN = "BRVM_ALPHA_MEMOIRE_MIN"

_ETAT = {"json_emis": False}


def json_demande(argv: Sequence[str]) -> bool:
    """``--format json`` (ou ``--format=json``, abréviation comprise) figure-t-il dans ``argv`` ?"""
    toks = [str(a) for a in argv]
    for i, tok in enumerate(toks):
        name, eq, val = tok.partition("=")
        if not (len(name) >= 4 and "--format".startswith(name)):
            continue
        if (eq and val == "json") or (not eq and i + 1 < len(toks) and toks[i + 1] == "json"):
            return True
    return False


def marquer_json_emis() -> None:
    """Appelé quand l'objet JSON de la commande a été écrit sur la sortie standard (jamais deux objets)."""
    _ETAT["json_emis"] = True


def json_emis() -> bool:
    return bool(_ETAT["json_emis"])


def reinitialiser() -> None:
    """Nouvelle commande : aucun objet JSON écrit pour l'instant."""
    _ETAT["json_emis"] = False


def seuil_memoire(environ: Mapping[str, str] | None = None) -> int:
    """Seuil de mémoire virtuelle en Mo (:data:`ENV_MEMOIRE_MIN`, défaut :data:`SEUIL_MEMOIRE_MO`)."""
    raw = str((os.environ if environ is None else environ).get(ENV_MEMOIRE_MIN, "") or "").strip()
    if not raw:
        return SEUIL_MEMOIRE_MO
    try:
        return max(0, int(raw))
    except ValueError:
        return SEUIL_MEMOIRE_MO


def controle_memoire(environ: Mapping[str, str] | None = None, limite: int | None = None) -> str | None:
    """Message de refus si la limite de mémoire virtuelle est sous le seuil, sinon ``None``.

    ``limite`` : limite en octets (défaut : ``RLIMIT_AS`` du processus ; ``None`` sans limite).
    """
    lim = erreurs.limite_memoire() if limite is None else limite
    if lim is None:
        return None
    seuil = seuil_memoire(environ)
    if seuil <= 0 or lim >= seuil * 1024 ** 2:
        return None
    return (f"mémoire insuffisante : limite de mémoire virtuelle trop basse ({lim // 1024 ** 2} Mo, RLIMIT_AS) ; le "
            f"moteur en demande au moins {seuil} Mo (3 Go conseillés, docs/DEPLOIEMENT.md § A.6). Aucune commande "
            "n'a été lancée.")


def _on_term(signum: int, frame: Any) -> None:  # noqa: ARG001 - signature imposée par signal
    raise erreurs.ArretDemande("arrêt demandé (signal TERM) : la commande a été arrêtée proprement.")


def _poser_term() -> None:
    import signal
    import threading

    if threading.current_thread() is threading.main_thread():
        try:
            signal.signal(signal.SIGTERM, _on_term)
        except (ValueError, OSError):  # pragma: no cover - plate-forme sans SIGTERM
            pass


def _rendre_term() -> None:
    import signal
    import threading

    if threading.current_thread() is threading.main_thread():
        try:
            signal.signal(signal.SIGTERM, signal.SIG_DFL)
        except (ValueError, OSError):  # pragma: no cover
            pass


def _ecrire(flux: Any, texte: str) -> None:
    try:
        flux.write(texte)
        flux.flush()
    except (OSError, ValueError, AttributeError):  # sortie fermée : le code de sortie suffit
        pass


def echec(code: int, erreur: str, message: str, en_json: bool) -> int:
    """Message sur la sortie d'erreur et, avec ``--format json``, l'objet d'erreur (s'il n'a pas déjà été écrit)."""
    code = erreurs.code_sur(code)
    _ecrire(sys.stderr, message + "\n")
    if en_json and not json_emis():
        obj = {"ok": False, "code": code, "erreur": erreur, "message": message, "bandeau": BANDEAU}
        _ecrire(sys.stdout, json.dumps(obj, ensure_ascii=False, indent=1) + "\n")
        marquer_json_emis()
    return code


def _classer(exc: BaseException) -> tuple[int, str, str]:
    """``(code, type, message)`` d'une erreur survenue au chargement de la ligne de commande."""
    if isinstance(exc, KeyboardInterrupt):
        return erreurs.INTERRUPTION, "interruption", "interruption : " + erreurs.message_erreur(exc)
    if erreurs.est_memoire(exc):
        return erreurs.MEMOIRE, "memoire", "échec : " + erreurs.message_erreur(exc)
    if isinstance(exc, ImportError):
        name = getattr(exc, "name", None) or ""
        return (erreurs.CONFIGURATION, "configuration",
                f"configuration invalide : chargement impossible du moteur ({type(exc).__name__} : {str(exc)[:300]})"
                + (f" ; paquet en cause : {name}" if name else "")
                + ". Vérifier l'installation des paquets (deploiement/requirements-moteur-py311.txt).")
    code = erreurs.code_retour(exc)
    return code, erreurs.TYPES.get(code, "interne"), (
        f"erreur interne : {type(exc).__name__} : {erreurs.message_erreur(exc)}" if code == erreurs.INTERNE
        else erreurs.message_erreur(exc))


def lancer(argv: Sequence[str] | None = None) -> int:
    """Point d'entrée de ``python -m brvm_alpha`` : garde de démarrage, puis :func:`brvm_alpha.cli.main`."""
    raw = list(sys.argv[1:] if argv is None else argv)
    en_json = json_demande(raw)
    reinitialiser()
    try:
        _poser_term()
        refus = controle_memoire()
        if refus is not None:
            return echec(erreurs.MEMOIRE, "memoire", refus, en_json)
        from brvm_alpha import cli

        return erreurs.code_sur(cli.main(raw))
    except SystemExit as exc:  # erreur d'arguments (objet JSON déjà écrit) ou --help
        return erreurs.code_retour(exc)
    except BaseException as exc:  # noqa: BLE001 - contrat : un code de la table et un objet JSON, toujours
        code, kind, message = _classer(exc)
        if code == erreurs.INTERNE:
            try:
                traceback.print_exception(type(exc), exc, exc.__traceback__, file=sys.stderr)
            except (OSError, ValueError):
                pass
        return echec(code, kind, message, en_json)
    finally:
        _rendre_term()


__all__ = ["BANDEAU", "SEUIL_MEMOIRE_MO", "ENV_MEMOIRE_MIN", "json_demande", "marquer_json_emis", "json_emis",
           "seuil_memoire", "controle_memoire", "echec", "lancer"]
