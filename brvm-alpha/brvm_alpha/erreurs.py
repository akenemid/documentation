"""Erreurs du moteur et codes de retour des commandes.

Chaque erreur prévue porte son code de sortie (attribut ``code_sortie``). La ligne de commande
traduit toute exception par :func:`code_retour` et :func:`type_erreur` ; :func:`erreur_json` donne
l'objet JSON d'une erreur (``--format json``).

Codes (toutes les commandes, en mode normal comme embarqué) :

== =====================================================================================
0  succès
1  données absentes ou historique non prêt
2  saisie invalide (erreurs d'argparse comprises)
4  verrou occupé (une autre opération tient le même fichier)
5  accès refusé ou réseau (HTTP 403 ou 429, refus de la liste blanche, délai dépassé…)
6  mémoire insuffisante (``MemoryError``)
7  erreur interne (exception non prévue)
8  configuration manquante ou invalide (mode embarqué sans dossiers, extracteur PDF absent…)
130 interruption (Ctrl+C)
== =====================================================================================

Le code 3 n'est **jamais** rendu : dans le conteneur Odoo, le processus 1 (le maître Odoo) s'arrête
s'il récolte un enfant sorti avec ce code.

Ce module n'importe rien de lourd : il est lu au démarrage, avant pandas.
"""

from __future__ import annotations

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


class VerrouOccupe(ErreurMoteur):
    """Un verrou est tenu par une autre opération au-delà du délai d'attente (code 4)."""

    code_sortie = VERROU_OCCUPE


class AccesRefuse(ErreurMoteur):
    """Accès refusé ou réseau : refus du site, de la liste blanche, réponse trop grosse, délai (code 5)."""

    code_sortie = ACCES_REFUSE


class ConfigurationError(ErreurMoteur):
    """Configuration manquante ou invalide : mode embarqué sans dossiers, extracteur PDF absent (code 8)."""

    code_sortie = CONFIGURATION


def code_retour(exc: BaseException) -> int:
    """Code de sortie d'une commande arrêtée par ``exc`` ; jamais 3."""
    if isinstance(exc, KeyboardInterrupt):
        code = INTERRUPTION
    elif isinstance(exc, MemoryError):
        code = MEMOIRE
    elif isinstance(exc, SystemExit):  # argparse : 2 pour une saisie invalide, 0 pour --help
        raw = exc.code
        code = OK if raw in (None, 0) else (raw if isinstance(raw, int) else SAISIE_INVALIDE)
    elif isinstance(exc, ErreurMoteur):
        code = int(getattr(exc, "code_sortie", INTERNE))
    elif isinstance(exc, (ValueError, KeyError)):
        code = SAISIE_INVALIDE
    elif isinstance(exc, FileNotFoundError):
        code = DONNEES_ABSENTES
    else:
        code = INTERNE
    return INTERNE if code == CODE_INTERDIT else code


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
    if isinstance(exc, KeyboardInterrupt):
        return "commande interrompue."
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
           "HistoriqueIncomplet", "SaisieInvalide", "VerrouOccupe", "AccesRefuse", "ConfigurationError", "code_retour",
           "type_erreur", "message_erreur", "erreur_json"]
