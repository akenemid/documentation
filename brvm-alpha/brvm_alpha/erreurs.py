"""Erreurs du moteur et codes de retour des commandes.

Chaque erreur prévue porte son code de sortie (attribut ``code_sortie``). La ligne de commande
traduit toute exception par :func:`code_retour` et :func:`type_erreur` ; :func:`erreur_json` donne
l'objet JSON d'une erreur (``--format json``).

Codes (toutes les commandes, en mode normal comme embarqué) :

== =====================================================================================
0  succès
1  données absentes, historique non prêt, panel ou journal des notes illisible
2  saisie invalide : :class:`SaisieInvalide` et erreurs d'argparse **seulement**
4  verrou occupé (une autre opération tient le même fichier)
5  accès refusé ou réseau (HTTP 403 ou 429, refus de la liste blanche, délai dépassé…)
6  mémoire insuffisante (``MemoryError``, bibliothèque impossible à charger faute de mémoire, processus de
   travail tué par ``SIGKILL`` sous une limite de mémoire virtuelle)
7  erreur interne : toute exception non prévue (``ValueError`` et ``KeyError`` d'une bibliothèque comprises,
   processus de travail tué par ``SIGSEGV`` ou un autre signal)
8  configuration manquante ou invalide (mode embarqué sans dossiers, extracteur PDF absent, paquet
   manquant, dossier de données non inscriptible, limite de temps de calcul trop basse ou atteinte…)
130 interruption (Ctrl+C, signal TERM)
== =====================================================================================

Le code 3 n'est **jamais** rendu : dans le conteneur Odoo, le processus 1 (le maître Odoo) s'arrête
s'il récolte un enfant sorti avec ce code. Tout code hors de la table est ramené à 7 (:func:`code_sur`).

Ce module n'importe rien de lourd : il est lu au démarrage, avant pandas.
"""

from __future__ import annotations

import errno
from typing import Any

OK = 0
DONNEES_ABSENTES = 1
SAISIE_INVALIDE = 2
VERROU_OCCUPE = 4
ACCES_REFUSE = 5
MEMOIRE = 6
INTERNE = 7
CONFIGURATION = 8
INTERRUPTION = 130
#: Code interdit (arrête le maître Odoo) : jamais rendu, remplacé par :data:`INTERNE`.
CODE_INTERDIT = 3

#: Type d'erreur (clé ``erreur`` du JSON) selon le code.
TYPES = {
    DONNEES_ABSENTES: "donnees_absentes",
    SAISIE_INVALIDE: "saisie_invalide",
    VERROU_OCCUPE: "verrou_occupe",
    ACCES_REFUSE: "acces_refuse",
    MEMOIRE: "memoire",
    INTERNE: "interne",
    CONFIGURATION: "configuration",
    INTERRUPTION: "interruption",
}


class ErreurMoteur(Exception):
    """Erreur prévue du moteur ; ``code_sortie`` : code de retour de la commande."""

    code_sortie: int = INTERNE


class DonneesAbsentes(ErreurMoteur):
    """Données absentes ou historique non prêt (code 1)."""

    code_sortie = DONNEES_ABSENTES


class HistoriqueIncomplet(DonneesAbsentes):
    """Historique des bulletins incomplet : ordre de bataille ou rapport refusé en mode embarqué (code 1).

    Clé ``erreur`` du JSON : ``historique_incomplet`` (au lieu de ``donnees_absentes``).
    """

    type_erreur = "historique_incomplet"


class SaisieInvalide(ErreurMoteur, ValueError):
    """Saisie invalide (code 2)."""

    code_sortie = SAISIE_INVALIDE


class CleInconnue(SaisieInvalide, KeyError):
    """Identifiant, symbole ou indice inconnu donné par l'utilisateur (code 2 ; aussi une ``KeyError``)."""


class JournalIllisible(DonneesAbsentes):
    """Le journal des notes existe mais ne se lit pas (dossier à sa place, droits…) : code 1.

    Un journal **absent** n'est pas une erreur (aucune note) ; un journal illisible l'est : sans lui, un veto
    ou un achat bloqué par une note serait ignoré sans alerte.
    """


class VerrouOccupe(ErreurMoteur):
    """Un verrou est tenu par une autre opération au-delà du délai d'attente (code 4)."""

    code_sortie = VERROU_OCCUPE


class AccesRefuse(ErreurMoteur):
    """Accès refusé ou réseau : refus du site, de la liste blanche, réponse trop grosse, délai (code 5)."""

    code_sortie = ACCES_REFUSE


class ConfigurationError(ErreurMoteur):
    """Configuration manquante ou invalide : mode embarqué sans dossiers, extracteur PDF absent (code 8)."""

    code_sortie = CONFIGURATION


#: Codes de la table : tout autre code (3, 259, -253, 515…) est ramené à :data:`INTERNE` (le statut d'un
#: processus est le code modulo 256 : 259 sortirait en 3).
CODES = frozenset({OK, DONNEES_ABSENTES, SAISIE_INVALIDE, VERROU_OCCUPE, ACCES_REFUSE, MEMOIRE, INTERNE,
                   CONFIGURATION, INTERRUPTION})

#: Motifs d'une erreur de chargement ou d'allocation due à la mémoire (``dlopen``, ``mmap``, OpenBLAS…).
_MOTIFS_MEMOIRE = ("failed to map segment", "cannot allocate memory", "out of memory", "unable to allocate",
                   "memory allocation failed", "cannot map zero-fill pages")
#: Erreurs d'écriture d'un dossier configuré qui relèvent de la configuration (volume en lecture seule, droits,
#: disque plein) : code 8.
_ERRNO_CONFIGURATION = frozenset({errno.EROFS, errno.EACCES, errno.EPERM, errno.ENOSPC,
                                  getattr(errno, "EDQUOT", errno.ENOSPC)})
#: Disque plein, quota atteint, volume en lecture seule : toujours la configuration (code 8), même quand l'erreur ne
#: porte pas de nom de fichier (écriture refusée au ``flush`` ou au ``close`` d'un fichier atomique ; avant : code 7
#: « erreur interne »). Le moteur n'écrit que dans ses dossiers configurés et dans son dossier temporaire.
_ERRNO_VOLUME = frozenset({errno.EROFS, errno.ENOSPC, getattr(errno, "EDQUOT", errno.ENOSPC)})


class ArretDemande(KeyboardInterrupt):
    """Signal TERM reçu (Odoo, superviseur, script) : la commande s'arrête comme sur Ctrl+C (code 130)."""


class TempsCalculDepasse(KeyboardInterrupt):
    """Signal ``SIGXCPU`` reçu : la limite souple de temps de calcul (``RLIMIT_CPU``) est atteinte (code 8).

    Comme :class:`ArretDemande`, elle dérive de ``KeyboardInterrupt`` : aucun ``except Exception`` ne l'avale, la
    commande s'arrête proprement (verrous rendus, fichiers temporaires retirés) et rend un objet JSON. Le code est 8
    (configuration) : c'est au lanceur de relever ``RLIMIT_CPU``.
    """


def code_sur(code: Any) -> int:
    """Code de sortie admis : un code de la table (:data:`CODES`), sinon :data:`INTERNE` ; jamais 3."""
    if isinstance(code, bool):
        code = int(code)
    if not isinstance(code, int):
        try:
            code = int(code)
        except (TypeError, ValueError, OverflowError):
            return INTERNE
    return code if code in CODES else INTERNE


def limite_memoire() -> int | None:
    """Limite douce de mémoire virtuelle du processus (``RLIMIT_AS``, octets), ou ``None`` sans limite."""
    try:
        import resource

        soft, _hard = resource.getrlimit(resource.RLIMIT_AS)
    except (ImportError, OSError, ValueError, AttributeError):  # pragma: no cover - plate-forme sans RLIMIT_AS
        return None
    return None if soft == resource.RLIM_INFINITY or soft < 0 else int(soft)


def limite_cpu() -> float | None:
    """Limite souple de temps de calcul du processus (``RLIMIT_CPU``, secondes), ou ``None`` sans limite."""
    try:
        import resource

        soft, _hard = resource.getrlimit(resource.RLIMIT_CPU)
    except (ImportError, OSError, ValueError, AttributeError):  # pragma: no cover - plate-forme sans RLIMIT_CPU
        return None
    return None if soft == resource.RLIM_INFINITY or soft < 0 else float(soft)


#: Attribut posé par le moteur sur une ``BrokenProcessPool`` (:func:`brvm_alpha.data.store._parse_all`) : codes de
#: sortie des processus de travail, relevés une fois le pool fermé (négatif : tué par ce signal).
ATTR_CODES_TRAVAILLEURS = "codes_sortie_travailleurs"


def _nom_signal(n: int) -> str:
    try:
        import signal

        return f"{signal.Signals(n).name} ({n})"
    except (ImportError, ValueError):  # pragma: no cover - numéro inconnu
        return f"n° {n}"


def _cause_pool(e: BaseException) -> tuple[int, str]:
    """``(code, message)`` d'un processus de travail mort (``BrokenProcessPool`` ``e``), d'après les codes de sortie.

    - tué par ``SIGXCPU`` : limite de temps de calcul atteinte → 8 ;
    - tué par ``SIGKILL`` sous une limite de mémoire virtuelle : manque de mémoire → 6 ;
    - tué par un autre signal (``SIGSEGV``, ``SIGABRT``, ``SIGBUS``…) → 7 ;
    - cause inconnue (codes absents, code positif, ou seulement ``SIGTERM``, que le pool envoie lui-même aux autres
      processus) : classement d'avant (6 sous une limite de mémoire virtuelle, 7 sinon), dit dans le message.
    """
    import signal

    codes = [int(c) for c in (getattr(e, ATTR_CODES_TRAVAILLEURS, None) or ()) if isinstance(c, int)]
    sigs = sorted({-c for c in codes if c < 0 and -c != int(signal.SIGTERM)})
    sous_as = limite_memoire() is not None
    xcpu = int(getattr(signal, "SIGXCPU", 24))
    if xcpu in sigs:
        return CONFIGURATION, ("arrêt : temps de calcul épuisé : un processus de travail du panel a été arrêté par le "
                               "signal SIGXCPU (limite de temps de calcul RLIMIT_CPU atteinte). Le lanceur doit relever "
                               "RLIMIT_CPU (limite souple = limite dure, docs/DEPLOIEMENT.md § A.6).")
    if int(signal.SIGKILL) in sigs and sous_as:
        return MEMOIRE, ("mémoire insuffisante : un processus de travail du panel a été tué par le signal SIGKILL sous "
                         "une limite de mémoire virtuelle (tueur de mémoire du noyau, le plus souvent). Relever la limite "
                         "de mémoire virtuelle (3 Go conseillés).")
    autres = [s for s in sigs if s != int(signal.SIGKILL)]
    if autres:
        return INTERNE, ("erreur interne : un processus de travail du panel a été arrêté par le signal "
                         + ", ".join(_nom_signal(s) for s in autres)
                         + " (défaut d'une bibliothèque compilée, le plus souvent) ; ce n'est pas un manque de mémoire.")
    vus = ", ".join(str(c) for c in sorted(set(codes))) or "non relevés"
    if sous_as:
        return MEMOIRE, ("mémoire insuffisante (cause inconnue) : un processus de travail du panel est mort (codes de "
                         f"sortie des processus de travail : {vus}) ; classé « mémoire » parce qu'une limite de mémoire "
                         "virtuelle est posée. Relever la limite de mémoire virtuelle (3 Go conseillés) et vérifier la "
                         "limite de temps de calcul (RLIMIT_CPU).")
    return INTERNE, ("erreur interne : un processus de travail du panel est mort, cause inconnue (codes de sortie des "
                     f"processus de travail : {vus}).")


def cause_travailleur(exc: BaseException | None) -> tuple[int, str] | None:
    """Processus de travail mort (``BrokenProcessPool`` dans la chaîne de ``exc``) : ``(code, message)``, sinon
    ``None``. Voir :func:`_cause_pool`."""
    for e in _chaine(exc):
        if type(e).__name__ == "BrokenProcessPool":
            return _cause_pool(e)
    return None


def _chaine(exc: BaseException | None):
    seen: set[int] = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        yield exc
        exc = exc.__cause__ if exc.__cause__ is not None else exc.__context__


def est_memoire(exc: BaseException | None) -> bool:
    """Vrai si ``exc`` (ou sa cause) vient d'un manque de mémoire.

    ``MemoryError`` ; ``ImportError`` ou ``OSError`` dont le message dit « failed to map segment », « cannot
    allocate memory »… (bibliothèque partagée impossible à charger sous une limite de mémoire virtuelle) ou de
    code ``ENOMEM`` ; ``BrokenProcessPool`` (processus de travail mort) quand :func:`cause_travailleur` y voit un manque
    de mémoire (tué par ``SIGKILL`` sous une limite de mémoire virtuelle, ou cause inconnue sous cette limite) : un
    processus tué par ``SIGXCPU`` ou ``SIGSEGV`` n'est pas un manque de mémoire. Un manque de place pour les
    variables de fil (« static TLS ») n'est pas un manque de mémoire.
    """
    for e in _chaine(exc):
        if isinstance(e, MemoryError):
            return True
        if isinstance(e, (ImportError, OSError)):
            if getattr(e, "errno", None) == errno.ENOMEM:
                return True
            msg = str(e).lower()
            if "static tls" not in msg and any(m in msg for m in _MOTIFS_MEMOIRE):
                return True
        if type(e).__name__ == "BrokenProcessPool" and _cause_pool(e)[0] == MEMOIRE:
            return True
    return False


def est_panel_illisible(exc: BaseException | None) -> bool:
    """Vrai si ``exc`` vient de la lecture d'un fichier ``.parquet`` abîmé (``ArrowInvalid``, ``OSError``…)."""
    for e in _chaine(exc):
        if isinstance(e, FileNotFoundError):
            return False
        if (type(e).__module__ or "").startswith("pyarrow") or isinstance(e, OSError):
            if "parquet" in f"{e} {getattr(e, 'filename', '') or ''}".lower():
                return True
    return False


def _dossier_configure(chemin: Any) -> bool:
    if not chemin:
        return False
    try:
        import os

        from brvm_alpha import paths

        p = os.path.abspath(os.fspath(chemin))
        for base in (paths.DATA_DIR, paths.REPORTS_DIR):
            b = os.path.abspath(base)
            if p == b or p.startswith(b.rstrip(os.sep) + os.sep):
                return True
    except Exception:  # pragma: no cover - chemin illisible : pas une erreur de configuration  # noqa: BLE001
        return False
    return False


def est_configuration(exc: BaseException | None) -> bool:
    """Vrai si ``exc`` relève de la configuration (code 8) sans être une :class:`ConfigurationError` :

    paquet tiers manquant (``ModuleNotFoundError`` hors de ``brvm_alpha``) ; écriture refusée dans un dossier
    configuré (``BRVM_ALPHA_DONNEES``, ``BRVM_ALPHA_RAPPORTS``) : volume en lecture seule, droits, disque plein.
    """
    if isinstance(exc, ModuleNotFoundError):
        name = str(getattr(exc, "name", "") or "")
        return bool(name) and not name.split(".")[0] == "brvm_alpha"
    if isinstance(exc, OSError) and getattr(exc, "errno", None) in _ERRNO_CONFIGURATION:
        if getattr(exc, "errno", None) in _ERRNO_VOLUME and not getattr(exc, "filename", None):
            return True
        return _dossier_configure(getattr(exc, "filename", None)) or _dossier_configure(getattr(exc, "filename2", None))
    return False


def code_retour(exc: BaseException) -> int:
    """Code de sortie d'une commande arrêtée par ``exc`` ; toujours un code de la table, jamais 3.

    Seules les saisies (:class:`SaisieInvalide`, erreurs d'argparse) donnent 2 : une ``ValueError`` ou une
    ``KeyError`` venue d'ailleurs (bibliothèque, défaut du moteur) est une erreur interne (7). Un panel illisible
    (``.parquet`` abîmé) donne 1, un manque de mémoire 6 (:func:`est_memoire`), un processus de travail mort le code de
    sa cause (:func:`cause_travailleur`), un paquet manquant ou un dossier configuré non inscriptible 8
    (:func:`est_configuration`), le signal ``SIGXCPU`` 8 (:class:`TempsCalculDepasse`).
    """
    if isinstance(exc, TempsCalculDepasse):
        code = CONFIGURATION
    elif isinstance(exc, KeyboardInterrupt):
        code = INTERRUPTION
    elif isinstance(exc, SystemExit):  # argparse : 2 pour une saisie invalide, 0 pour --help
        raw = exc.code
        code = OK if raw is None else (raw if isinstance(raw, int) else SAISIE_INVALIDE)
    elif isinstance(exc, ErreurMoteur):
        code = int(getattr(exc, "code_sortie", INTERNE))
    elif est_memoire(exc):
        code = MEMOIRE
    elif (cause := cause_travailleur(exc)) is not None:
        code = cause[0]
    elif est_configuration(exc):
        code = CONFIGURATION
    elif isinstance(exc, FileNotFoundError) or est_panel_illisible(exc):
        code = DONNEES_ABSENTES
    else:
        code = INTERNE
    return code_sur(code)


def type_erreur(exc: BaseException) -> str:
    """Type stable de l'erreur (clé ``erreur`` du JSON) : ``acces_refuse``, ``verrou_occupe``…

    Une erreur du moteur peut préciser son type (attribut de classe ``type_erreur``, par exemple
    ``historique_incomplet``) ; sinon le type suit le code de sortie.
    """
    own = getattr(type(exc), "type_erreur", None) if isinstance(exc, ErreurMoteur) else None
    if isinstance(own, str) and own:
        return own
    return TYPES.get(code_retour(exc), "interne")


def message_erreur(exc: BaseException) -> str:
    """Texte français de l'erreur, sans trace d'appel."""
    if isinstance(exc, MemoryError):
        return "mémoire insuffisante : la commande a été arrêtée (aucun résultat partiel n'est donné)."
    if isinstance(exc, TempsCalculDepasse):
        return str(exc.args[0]) if exc.args else "arrêt : limite de temps de calcul atteinte (signal SIGXCPU)."
    if isinstance(exc, KeyboardInterrupt):
        return str(exc.args[0]) if isinstance(exc, ArretDemande) and exc.args else "commande interrompue."
    if not isinstance(exc, ErreurMoteur):
        cause = cause_travailleur(exc)
        if cause is not None and not any(isinstance(e, MemoryError) for e in _chaine(exc)):
            return cause[1]
        if est_memoire(exc):
            return ("mémoire insuffisante : une bibliothèque n'a pas pu être chargée ou un processus de travail est "
                    f"mort ({type(exc).__name__} : {str(exc)[:200]}). Relever la limite de mémoire virtuelle "
                    "(3 Go conseillés).")
        if isinstance(exc, ModuleNotFoundError) and est_configuration(exc):
            return (f"paquet Python manquant : {exc.name} (installer le jeu de paquets du moteur, "
                    "deploiement/requirements-moteur-py311.txt).")
        if isinstance(exc, OSError) and est_configuration(exc):
            ou = f" ({exc.filename})" if exc.filename else ""
            return (f"dossier configuré inutilisable : {exc.strerror or exc}{ou}. Vérifier que BRVM_ALPHA_DONNEES, "
                    "BRVM_ALPHA_RAPPORTS et le dossier temporaire sont inscriptibles et que le disque n'est pas plein.")
        if est_panel_illisible(exc):
            return (f"panel illisible ({type(exc).__name__} : {str(exc)[:200]}) : reconstruire le panel "
                    "(python -m brvm_alpha panel --force).")
    text = str(exc).strip()
    if isinstance(exc, KeyError) and text.startswith(("'", '"')) and text.endswith(("'", '"')):
        text = text[1:-1]
    return text or type(exc).__name__


def erreur_json(exc: BaseException, bandeau: str) -> dict[str, Any]:
    """Objet JSON d'une erreur : ``{"ok": false, "code", "erreur", "message", "bandeau"}``."""
    return {"ok": False, "code": code_retour(exc), "erreur": type_erreur(exc), "message": message_erreur(exc),
            "bandeau": bandeau}


__all__ = ["OK", "DONNEES_ABSENTES", "SAISIE_INVALIDE", "VERROU_OCCUPE", "ACCES_REFUSE", "MEMOIRE", "INTERNE",
           "CONFIGURATION", "INTERRUPTION", "CODE_INTERDIT", "TYPES", "ErreurMoteur", "DonneesAbsentes",
           "HistoriqueIncomplet", "SaisieInvalide", "CleInconnue", "JournalIllisible", "VerrouOccupe", "AccesRefuse",
           "ConfigurationError", "ArretDemande", "TempsCalculDepasse", "CODES", "code_sur", "limite_memoire",
           "limite_cpu", "ATTR_CODES_TRAVAILLEURS", "cause_travailleur", "est_memoire",
           "est_panel_illisible", "est_configuration", "code_retour", "type_erreur", "message_erreur", "erreur_json"]
