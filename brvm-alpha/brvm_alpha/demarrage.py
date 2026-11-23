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
- **temps de calcul** : un travailleur Odoo pose sur lui-même une limite souple de temps de calcul
  (``RLIMIT_CPU``), dont ses sous-processus héritent. Si la marge restante (limite souple moins le temps déjà
  consommé par le processus) est sous :data:`SEUIL_CPU_S` secondes (réglable par ``BRVM_ALPHA_CPU_MIN`` ;
  ``0`` : aucun contrôle), rien n'est chargé et la commande sort en 8. Le moteur ne relève **pas** la limite
  lui-même : c'est au lanceur de le faire. Le signal ``SIGXCPU`` (limite atteinte en cours de commande)
  arrête la commande proprement, en 8 avec un objet JSON, au lieu d'une sortie en −24 sans objet ;
- **échec au chargement du paquet** : ``MemoryError`` ou bibliothèque impossible à charger faute de
  mémoire → 6 ; paquet manquant ou installation abîmée (``ImportError``) → 8 ; interruption → 130 ;
  autre → 7, avec la trace sur la sortie d'erreur ;
- avec ``--format json``, la sortie standard porte **exactement un objet JSON** dans tous ces cas : TERM et
  ``SIGXCPU`` sont reportés pendant son écriture (:func:`ecrire_objet`), et une fois l'objet écrit ils ne changent
  plus le code de sortie (c'est celui de l'objet) ;
- **écriture finale** : pour une commande dont l'écriture durable est la dernière étape (``notes add``, ``notes
  archive``, ``recommend --sortie``, ``report``, ``notes export``), TERM et ``SIGXCPU`` sont reportés dès le point de
  non-retour de cette écriture jusqu'à la fin de la commande (:func:`reporter_apres_ecriture`,
  :func:`point_de_non_retour`) : une note enregistrée n'est jamais annoncée perdue ;
- le code de sortie est toujours un code de la table (:data:`brvm_alpha.erreurs.CODES`), **jamais 3**.
"""

from __future__ import annotations

import contextlib
import json
import math
import os
import sys
import traceback
from collections.abc import Iterator, Mapping, Sequence
from typing import Any

from brvm_alpha import erreurs

BANDEAU = "Performance passée ≠ garantie. Aucun gain n'est garanti."
#: Limite de mémoire virtuelle minimale (Mo). Mesures du mode embarqué : 0,8 Go au plus (``recommend``,
#: ``panel --force``) ; sous 1 Go, le chargement de numpy et de pyarrow devient aléatoire.
SEUIL_MEMOIRE_MO = 1024
#: Variable d'environnement du seuil (Mo) ; ``0`` désactive le contrôle.
ENV_MEMOIRE_MIN = "BRVM_ALPHA_MEMOIRE_MIN"
#: Marge minimale de temps de calcul (s) sous ``RLIMIT_CPU``. Mesures du mode embarqué : ``recommend`` 14 s,
#: ``report`` 16 s, ``panel --force`` 40 s par processus de travail ; un processeur lent compte 2 à 3 fois plus.
SEUIL_CPU_S = 900
#: Variable d'environnement de la marge minimale (s) ; ``0`` désactive le contrôle.
ENV_CPU_MIN = "BRVM_ALPHA_CPU_MIN"

#: Message de l'arrêt sur TERM.
MESSAGE_TERM = "arrêt demandé (signal TERM) : la commande a été arrêtée proprement."

#: État du processus : objet JSON écrit (et son code), gestionnaire de ``SIGXCPU`` d'avant, signaux reportés
#: (``report`` : profondeur des blocs ; ``recus`` : signaux reçus pendant ces blocs), écriture finale (``arme`` :
#: commande dont l'écriture durable est la dernière étape ; ``arme_actif`` : point de non-retour franchi).
_ETAT: dict[str, Any] = {"json_emis": False, "code_emis": None, "xcpu_avant": None, "report": 0, "recus": [],
                         "arme": 0, "arme_actif": False}


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


def marquer_json_emis(code: int | None = None) -> None:
    """Appelé quand l'objet JSON de la commande a été écrit sur la sortie standard (jamais deux objets) ; ``code`` :
    code de sortie que dit l'objet (0 pour ``"ok": true``).

    Le résultat est alors donné : un ``SIGXCPU`` plus tardif est ignoré, et un TERM ne change plus le code de sortie
    (sinon un objet ``"ok": true`` pourrait sortir en 8 ou en 130)."""
    _ETAT["json_emis"] = True
    _ETAT["code_emis"] = None if code is None else erreurs.code_sur(code)
    if _ETAT.get("xcpu_avant") is not None:  # gestionnaire posé par lancer() : ce processus est le moteur
        _ignorer_xcpu()


def json_emis() -> bool:
    return bool(_ETAT["json_emis"])


def code_emis() -> int | None:
    """Code de sortie que dit l'objet JSON déjà écrit (``None`` : aucun objet, ou code non relevé)."""
    return _ETAT["code_emis"] if _ETAT["json_emis"] else None


def reinitialiser() -> None:
    """Nouvelle commande : aucun objet JSON écrit pour l'instant, aucun signal reporté."""
    _ETAT.update({"json_emis": False, "code_emis": None, "report": 0, "recus": [], "arme": 0, "arme_actif": False})


def _fil_principal() -> bool:
    import threading

    return threading.current_thread() is threading.main_thread()


def _signal_reporte(nom: str) -> bool:
    """Signal reçu dans un bloc où TERM et ``SIGXCPU`` sont reportés : noté, sans effet immédiat."""
    if _ETAT["report"] > 0:
        _ETAT["recus"].append(nom)
        return True
    return False


def _lever(nom: str) -> None:
    if nom == "SIGXCPU":
        _ignorer_xcpu()
        raise erreurs.TempsCalculDepasse(message_xcpu())
    raise erreurs.ArretDemande(MESSAGE_TERM)


def _fin_report(traiter: bool) -> None:
    """Fin du bloc le plus extérieur : signaux reçus oubliés, ou le premier traité (``traiter``)."""
    recus, _ETAT["recus"] = list(_ETAT["recus"]), []
    if not recus:
        return
    if traiter:
        _lever(recus[0])
    _ecrire(sys.stderr, f"signal {recus[0]} reçu pendant l'écriture du résultat : sans effet, la commande rend son "
                        "propre résultat.\n")


@contextlib.contextmanager
def signaux_reportes() -> Iterator[None]:
    """Bloc où TERM et ``SIGXCPU`` sont **reportés** (écriture de l'unique objet JSON) : l'objet n'est jamais coupé en
    deux par un signal, et jamais suivi d'un second objet.

    À la fin du bloc le plus extérieur : objet JSON écrit, ou bloc sorti par une erreur : les signaux reçus sont
    oubliés (l'objet, ou l'erreur, est la réponse) ; sinon le premier est traité comme d'habitude (130, 8)."""
    _ETAT["report"] += 1
    fini = False
    try:
        yield
        fini = True
    finally:
        _ETAT["report"] -= 1
        if _ETAT["report"] <= 0:
            _ETAT["report"] = 0
            _fin_report(fini and not json_emis())


@contextlib.contextmanager
def reporter_apres_ecriture() -> Iterator[None]:
    """Commande dont l'écriture durable est la **dernière étape** (``notes add``, ``notes archive``, ``recommend
    --sortie``, ``report``, ``notes export``) : dès le point de non-retour de l'écriture (:func:`point_de_non_retour`),
    TERM et ``SIGXCPU`` sont reportés jusqu'à la fin du bloc, puis oubliés. La note ou le fichier est enregistré, la
    commande finit et rend son vrai résultat (avant : ``notes add`` pouvait sortir en 8 « sans résultat partiel » alors
    que la note était au journal). Avant ce point, rien ne change : un TERM pendant l'attente d'un verrou ou pendant le
    calcul arrête la commande comme avant."""
    _ETAT["arme"] += 1
    try:
        yield
    finally:
        _ETAT["arme"] -= 1
        if _ETAT["arme"] <= 0:
            _ETAT["arme"] = 0
            if _ETAT["arme_actif"]:
                _ETAT["arme_actif"] = False
                _ETAT["report"] = max(0, _ETAT["report"] - 1)
                if _ETAT["report"] == 0:
                    _fin_report(False)


def point_de_non_retour() -> None:
    """Appelé juste avant une écriture qui ne se défait pas (ligne ajoutée au journal des notes, renommage d'un fichier
    écrit de façon atomique). Dans un bloc :func:`reporter_apres_ecriture` (fil principal), TERM et ``SIGXCPU`` sont
    reportés à partir d'ici ; ailleurs, sans effet."""
    if _ETAT["arme"] > 0 and not _ETAT["arme_actif"] and _fil_principal():
        _ETAT["arme_actif"] = True
        _ETAT["report"] += 1


def ecrire_objet(flux: Any, texte: str, code: int) -> None:
    """Écrit l'unique objet JSON de la commande (``texte``) sur ``flux``, TERM et ``SIGXCPU`` reportés pendant
    l'écriture, puis le marque comme écrit (:func:`marquer_json_emis`, ``code`` : celui que dit l'objet).

    Avant, un signal reçu pendant l'écriture d'un gros objet vers un tube coupait l'objet, puis un second objet (celui de
    l'erreur) suivait. ``OSError`` si l'écriture échoue (l'objet n'est pas marqué comme écrit)."""
    with signaux_reportes():
        flux.write(texte)
        flux.flush()
        marquer_json_emis(code)


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


def _lire_seuil_cpu(environ: Mapping[str, str] | None = None) -> tuple[float, str | None]:
    """``(seuil, valeur illisible ou None)`` : :data:`ENV_CPU_MIN` lu ; vide : défaut ; ``0`` : aucun contrôle.

    Une valeur illisible (« abc », « nan », « inf ») ou **négative** prend le défaut :data:`SEUIL_CPU_S` : une faute de
    frappe ne coupe jamais le contrôle (seul ``0`` le coupe)."""
    raw = str((os.environ if environ is None else environ).get(ENV_CPU_MIN, "") or "").strip()
    if not raw:
        return float(SEUIL_CPU_S), None
    try:
        val = float(raw)
    except ValueError:
        return float(SEUIL_CPU_S), raw
    if not math.isfinite(val) or val < 0:
        return float(SEUIL_CPU_S), raw
    return val, None


def seuil_cpu(environ: Mapping[str, str] | None = None) -> float:
    """Marge minimale de temps de calcul en secondes (:data:`ENV_CPU_MIN`, défaut :data:`SEUIL_CPU_S` ; valeur
    illisible ou négative : défaut ; ``0`` : aucun contrôle)."""
    return _lire_seuil_cpu(environ)[0]


def temps_consomme() -> float:
    """Temps de calcul déjà consommé par ce processus (utilisateur et système, tous les fils), en secondes."""
    try:
        import resource

        ru = resource.getrusage(resource.RUSAGE_SELF)
    except (ImportError, OSError, ValueError, AttributeError):  # pragma: no cover
        return 0.0
    return float(ru.ru_utime + ru.ru_stime)


def _fr(x: float) -> str:
    return f"{x:.1f}".replace(".", ",")


def controle_cpu(environ: Mapping[str, str] | None = None, limite: float | None = None,
                 consomme: float | None = None) -> str | None:
    """Message de refus si la marge de temps de calcul est sous le seuil, sinon ``None``.

    ``limite`` : limite souple en secondes (défaut : ``RLIMIT_CPU`` du processus ; ``None`` sans limite) ;
    ``consomme`` : temps déjà consommé (défaut : :func:`temps_consomme`). La limite n'est jamais modifiée ici.
    """
    lim = erreurs.limite_cpu() if limite is None else float(limite)
    if lim is None:
        return None
    seuil, illisible = _lire_seuil_cpu(environ)
    used = temps_consomme() if consomme is None else float(consomme)
    marge = lim - used
    if seuil <= 0 or marge >= seuil:
        return None
    # Arrondis vers le bas pour la marge et vers le haut pour le reste : le message ne se contredit jamais (avant :
    # « 900,0 s de marge ; le moteur en demande au moins 900 s »).
    marge_txt = _fr(max(math.floor(marge * 10) / 10, 0.0))
    note = (f" ; {ENV_CPU_MIN} illisible ou négative (« {illisible[:40]} ») : défaut de {SEUIL_CPU_S} s pris"
            if illisible is not None else "")
    return (f"configuration invalide : limite de temps de calcul trop basse (RLIMIT_CPU souple de {lim:.0f} s, dont "
            f"{_fr(math.ceil(used * 10) / 10)} s déjà consommées : {marge_txt} s de marge ; le moteur en demande au "
            f"moins {math.ceil(seuil)} s{note}) : le lanceur doit relever RLIMIT_CPU (limite souple = limite dure, "
            "docs/DEPLOIEMENT.md § A.6). Aucune commande n'a été lancée.")


def message_xcpu() -> str:
    """Message de l'arrêt sur ``SIGXCPU`` (limite souple de temps de calcul atteinte en cours de commande)."""
    return (f"arrêt : limite de temps de calcul atteinte après {_fr(temps_consomme())} s de calcul (signal SIGXCPU, "
            "limite souple RLIMIT_CPU) : la commande a été arrêtée proprement (verrous rendus, fichiers temporaires "
            "retirés) ; ce qui était déjà enregistré avant l'arrêt est gardé, rien n'est laissé à moitié. Le lanceur "
            "doit relever RLIMIT_CPU (limite souple = limite dure, docs/DEPLOIEMENT.md § A.6).")


def _ignorer_xcpu() -> None:
    import signal
    import threading

    if hasattr(signal, "SIGXCPU") and threading.current_thread() is threading.main_thread():
        try:
            signal.signal(signal.SIGXCPU, signal.SIG_IGN)
        except (ValueError, OSError):  # pragma: no cover
            pass


def _on_xcpu(signum: int, frame: Any) -> None:  # signature imposée par signal
    # Le noyau renvoie SIGXCPU chaque seconde tant que le calcul continue : les suivants sont ignorés, pour que la
    # sortie propre (verrous, fichiers temporaires, objet JSON) aille à son terme. La limite n'est pas modifiée.
    if _signal_reporte("SIGXCPU"):  # écriture du résultat en cours : traité (ou oublié) à la fin du bloc
        return
    _ignorer_xcpu()
    raise erreurs.TempsCalculDepasse(message_xcpu())


def _on_term(signum: int, frame: Any) -> None:  # noqa: ARG001 - signature imposée par signal
    if _signal_reporte("TERM"):  # écriture du résultat en cours : traité (ou oublié) à la fin du bloc
        return
    raise erreurs.ArretDemande(MESSAGE_TERM)


def _poser_term() -> None:
    import signal
    import threading

    if threading.current_thread() is threading.main_thread():
        try:
            signal.signal(signal.SIGTERM, _on_term)
        except (ValueError, OSError):  # pragma: no cover - plate-forme sans SIGTERM
            pass
        if hasattr(signal, "SIGXCPU"):
            try:
                _ETAT["xcpu_avant"] = signal.signal(signal.SIGXCPU, _on_xcpu)
            except (ValueError, OSError):  # pragma: no cover
                pass


def _rendre_term(processus: bool = False) -> None:
    """Fin de commande : TERM rendu à son action par défaut, ou ignoré si ``processus`` et que l'objet JSON est écrit (le
    code de sortie est celui de l'objet : la fermeture de l'interpréteur ne doit pas finir en −15). ``SIGXCPU`` : ignoré
    si ``processus`` (le code de sortie est décidé ; la fermeture de l'interpréteur ne doit pas finir en −24), sinon
    gestionnaire d'avant rétabli (appel dans un processus qui continue, par exemple les essais)."""
    import signal
    import threading

    if threading.current_thread() is threading.main_thread():
        try:
            signal.signal(signal.SIGTERM, signal.SIG_IGN if processus and json_emis() else signal.SIG_DFL)
        except (ValueError, OSError):  # pragma: no cover
            pass
        if hasattr(signal, "SIGXCPU"):
            avant, _ETAT["xcpu_avant"] = _ETAT.get("xcpu_avant"), None
            try:
                signal.signal(signal.SIGXCPU, signal.SIG_IGN if processus or avant is None else avant)
            except (ValueError, OSError, TypeError):  # pragma: no cover
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
        try:
            ecrire_objet(sys.stdout, json.dumps(obj, ensure_ascii=False, indent=1) + "\n", code)
        except (OSError, ValueError, AttributeError):  # sortie fermée : le code de sortie suffit
            pass
    return code


def _classer(exc: BaseException) -> tuple[int, str, str]:
    """``(code, type, message)`` d'une erreur survenue au chargement de la ligne de commande."""
    if isinstance(exc, erreurs.TempsCalculDepasse):
        return erreurs.CONFIGURATION, "configuration", erreurs.message_erreur(exc)
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
    """Point d'entrée de ``python -m brvm_alpha`` : garde de démarrage, puis :func:`brvm_alpha.cli.main`.

    ``argv`` absent : arguments du processus (``python -m brvm_alpha``), qui s'arrête ensuite ; donné : appel dans un
    processus qui continue (les gestionnaires de signaux d'avant sont rétablis à la fin)."""
    raw = list(sys.argv[1:] if argv is None else argv)
    en_json = json_demande(raw)
    reinitialiser()
    try:
        _poser_term()
        refus = controle_memoire()
        if refus is not None:
            return echec(erreurs.MEMOIRE, "memoire", refus, en_json)
        refus = controle_cpu()
        if refus is not None:
            return echec(erreurs.CONFIGURATION, "configuration", refus, en_json)
        from brvm_alpha import cli

        return erreurs.code_sur(cli.main(raw))
    except SystemExit as exc:  # erreur d'arguments (objet JSON déjà écrit) ou --help
        return erreurs.code_retour(exc)
    except BaseException as exc:  # noqa: BLE001 - contrat : un code de la table et un objet JSON, toujours
        if isinstance(exc, KeyboardInterrupt) and code_emis() is not None:
            # TERM ou SIGXCPU après l'objet JSON : le résultat est donné, le code de sortie est celui de l'objet.
            _ecrire(sys.stderr, f"{erreurs.message_erreur(exc)} (reçu après l'écriture du résultat : sans effet)\n")
            return int(code_emis())
        code, kind, message = _classer(exc)
        if code == erreurs.INTERNE:
            try:
                traceback.print_exception(type(exc), exc, exc.__traceback__, file=sys.stderr)
            except (OSError, ValueError):
                pass
        return echec(code, kind, message, en_json)
    finally:
        _rendre_term(processus=argv is None)


__all__ = ["BANDEAU", "SEUIL_MEMOIRE_MO", "ENV_MEMOIRE_MIN", "SEUIL_CPU_S", "ENV_CPU_MIN", "MESSAGE_TERM",
           "json_demande", "marquer_json_emis", "json_emis", "code_emis", "signaux_reportes", "reporter_apres_ecriture",
           "point_de_non_retour", "ecrire_objet", "seuil_memoire", "controle_memoire", "seuil_cpu", "temps_consomme",
           "controle_cpu", "message_xcpu", "echec", "lancer"]
