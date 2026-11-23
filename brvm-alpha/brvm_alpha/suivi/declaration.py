"""F9 — Déclaration du suivi sur papier (S2) : articles, chaîne d'empreintes, signature, registre des essais.

Cahier ``docs/RENDEMENT_NET.md``, §F9 et §8. Avant le début du suivi (mardi 01/12/2026), l'humain écrit, date et signe
ce qui sera suivi et comment on en jugera. Cette fonction est l'**outil** : elle ne décide rien à la place de
l'utilisateur et ne s'exécute que sur sa commande explicite.

* :func:`modele` : le projet de déclaration (articles 1 à 7 du §8 et le portefeuille ``PLAN``), non signé, avec pour
  chaque article la proposition par défaut et les réponses possibles ;
* :func:`signer` : écrit les articles répondus dans ``<dossier>/declaration.jsonl`` (ajout seul, une ligne JSON par
  article, chaîne d'empreintes) ; signature par **initiales ou pseudonyme** (lus dans ``<données>/profil/signature.json``
  ou donnés), jamais un nom complet ; refus hors du dépôt de développement (:class:`HorsDepot`, code 2) ;
* :func:`verifier` : contrôle de la chaîne (toute réécriture d'une ligne la rompt) ;
* :func:`en_vigueur` : règles en vigueur à une date (``remplace`` et ``retrait`` ne valent que pour l'avenir) ;
* :func:`inscrire_au_registre` : ajoute trois à cinq lignes au registre des essais **passé explicitement** (aucun
  chemin par défaut), sur confirmation écrite ; les lignes existantes ne sont ni modifiées ni réordonnées.

Le module n'écrit jamais de lui-même dans ``reports/suivi_S2/`` ni dans ``reports/trials.parquet`` : seul l'humain le
fait, par une commande explicite, dans le dépôt de développement, avant un commit daté.

Performance passée ≠ garantie. Aucun gain n'est garanti.
"""

from __future__ import annotations

import copy
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd

from brvm_alpha import paths as _paths
from brvm_alpha import suivi as _s
from brvm_alpha.rendement import reglages as _rg

__all__ = ["CONFIRMATION_REGISTRE", "CODE_REFUS", "FICHIER", "HorsDepot", "IDS", "MESSAGE_HORS_DEPOT", "SignatureInvalide",
           "TEXTE_8_3", "TEXTE_8_5", "TYPES", "depot_de_developpement", "empreinte_lignes", "empreintes", "en_vigueur",
           "inscrire_au_registre", "lignes", "lire_signature", "modele", "preparer", "signer", "valider_signature",
           "verifier"]

FICHIER = "declaration.jsonl"
TYPES = ("reference", "essai", "ecart_execution", "regle_papier", "decision_humaine", "derogation", "retrait", "remplace")
#: Identifiants des articles (§8, §F9). ``E-T`` : entrée en plusieurs fois (F15), écart de calendrier de même nature
#: que E-L, E-B, E-A (§8.3), ajouté par l'utilisateur s'il l'applique ; signé après le début, il ne vaut que pour
#: l'avenir.
IDS = ("REF-S2", "N", "E-C", "E-D", "PLAN", "E-A", "E-B", "E-L", "E-T")
#: Code de sortie d'un refus (ligne de commande).
CODE_REFUS = 2
MESSAGE_HORS_DEPOT = "La déclaration se signe dans le dépôt de développement, puis se livre par un commit."
#: Phrase exacte à recopier pour inscrire la déclaration au registre des essais.
CONFIRMATION_REGISTRE = "J'INSCRIS AU REGISTRE"
#: Texte cité de la spécification (§8.5, dernier paragraphe).
TEXTE_8_5 = ("Décisions humaines attendues (non tranchées ici, nouvel essai à juger sur S2 seulement) : (i) plancher D1 "
             "pour les filtres d'univers et âge des ordres compté en séances après un trou de BOC ; (ii) mise en œuvre du "
             "repli D8 (dividendes et produit des sorties forcées gardés en liquidités jusqu'au rebalancement annuel).")
#: Texte affiché avec les écarts d'exécution (§8.3).
TEXTE_8_3 = ("Ces écarts ne sont pas jugés sur leurs gains. Leur effet sur le rendement est celui d'être plus ou moins "
             "investi : il a le signe du marché. La décision se prend maintenant, par vous. Le suivi vérifie seulement que "
             "la règle fait ce qu'elle dit et ne coûte pas plus que prévu.")
MENTION_SANS_DECLARATION = ("Aucune déclaration signée : seul le panier de référence (témoin) est suivi ; sa définition est "
                            "celle du test et n'a pas besoin de signature.")


class HorsDepot(RuntimeError):
    """Signature refusée hors du dépôt de développement (installation) : code de sortie 2, rien n'est écrit."""

    code = CODE_REFUS


class SignatureInvalide(ValueError):
    """Initiales ou pseudonyme refusés (plus de 12 caractères, espace, « @ », caractère autre que lettre, chiffre ou
    tiret)."""


# ---------------------------------------------------------------------------
# Articles proposés (§8)
# ---------------------------------------------------------------------------

_OUI_NON = ["oui", "non"]
_OPTIONS = ["option 1", "option 2 : oui", "option 2 : non", "non déclaré"]


def _article(**kw: Any) -> dict[str, Any]:
    base = {"type": None, "id": None, "phrase": "", "regle": {}, "parametres": {}, "mesure": [], "duree_min": "",
            "decision_ecrite": "", "source_spec": "", "proposition": None, "choix": None, "reponse": None,
            "reponse_requise": True, "hypotheses_de_travail": [], "registre": None, "mention": ""}
    base.update(kw)
    return base


def modele(reglages: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    """Projet de déclaration (§8), **non signé** : une entrée par article, avec ``proposition`` (défaut du cahier),
    ``choix`` (réponses possibles) et ``reponse`` vide, à remplir par l'utilisateur (oui ou non pour chaque écart ;
    option 1 ou 2 pour E-C et E-D ; seuils marqués « Hypothèse de travail » à valider ou corriger)."""
    debut = str(_rg.lire(reglages, "dates.debut_suivi", "2026-12-01"))
    capital = int(_rg.lire(reglages, "suivi.capital_temoin_fcfa", 10_000_000))
    from brvm_alpha.suivi import temoin as _tm

    d0 = _tm.date_de_depart(reglages).date().isoformat()
    ref = _article(
        type="reference", id="REF-S2", reponse_requise=False, reponse="oui", proposition="oui",
        phrase=("Le panier de référence suit la règle testée : les 20 plus grosses sociétés éligibles, remises à niveau "
                "fin janvier, sans les notes."),
        regle={
            "selection_et_poids": "variante REF (D8) : 20 plus grosses capitalisations éligibles, poids proportionnels à "
                                  "la capitalisation, plafonds de D8, 98 % investi",
            "calendrier": "remise à niveau à la première décision de janvier ; mémoire des positions entre deux ; sorties "
                          "forcées de la règle (filtres de risque, inéligibilité)",
            "dividendes": "crédités nets à la date de paiement ; gardés en liquidités jusqu'à la remise à niveau",
            "arrondi": "vers le bas, ligne par ligne", "bande": "2 points par ligne",
            "execution": "cours moyen du jour suivant si le titre est échangé ; 10 % du volume du jour au plus ; report "
                         "10 séances",
            "notes": "aucune (D11 : aucun rôle dans le test)", "couts": "scénario central",
            "capital": f"{capital} FCFA",
            "depart": f"première décision le {d0} (dernière séance avant le {debut}, date figée) ; première exécution à "
                      f"la première séance à partir du {debut}",
            "code": "le moteur du test, plus un seul refus explicite (forfait de compte non nul) ; fabrique "
                    "brvm_alpha.suivi.temoin.temoin_model, sans modification de validation/runner.py"},
        parametres={"variante": "REF", "couts": "central", "capital_fcfa": capital, "notes": None,
                    "mode_decision": "evenementiel", "debut_suivi": debut, "date_premiere_decision": d0,
                    "fabrique": "brvm_alpha.suivi.temoin.temoin_model",
                    "budget_de_retard_points": {"premiere_annee": [3.3, 4.2], "par_an_ensuite": [1.7, 2.6]},
                    "points_d_etape": ["2026-12-01", "2027-01-29", "2027-06-01", "2027-12-01", "2028-01-31",
                                       "2029-12-01"]},
        mesure=["P1 identité comptable de chaque semaine (écart de 0 FCFA)",
                "P2 frais payés par poste contre frais prévus par le tarif",
                "P3 part investie moyenne", "P4 part des titres servis (test S1 : 80,9 % des ordres)",
                "P5 ordres déclenchés par un trou de bulletins (chaque cas documenté)",
                "P6 coût de la remise à niveau de janvier, comparé à la fourchette de F3",
                "P7 écart au marché en valeur de part, comparé au budget de retard",
                "P8 exécution sur papier en mode test, sans écart, contre le moteur"],
        duree_min="36 mois avant toute conclusion sur la référence",
        decision_ecrite=("Aucune conclusion sur la référence avant 36 mois. Budget de retard écrit d'avance [Estimation] : "
                         "3,3 à 4,2 points de moins que le marché la première année, puis 1,7 à 2,6 points par an. "
                         "L'alerte existante de la spécification (retard relatif de 10 %) reste le seul seuil."),
        source_spec="SPECIFICATION_STRATEGIE.md §6, §7.1, §7.2, §8.1, §8.4 (D8, D11) ; cahier §8.2",
        registre={"id": "S2-REF", "variante": "REF", "famille": "S2-temoin"},
        mention="Le témoin garde l'exécution du moteur du test (§7.1), sans test de limite.")
    e_l = _article(
        type="ecart_execution", id="E-L", proposition="oui", choix=list(_OUI_NON),
        phrase=("Sur papier, un ordre n'est servi que si le cours moyen du jour respecte sa limite : c'est ce que vous "
                "feriez avec votre courtier."),
        regle={"texte": "exécution sur papier en mode « limite » (F12), plus stricte que le §7.1 de la spécification : un "
                        "achat est servi si le titre a coté et si son cours moyen du jour est au plus à la limite (une "
                        "vente : au moins à la limite) ; 10 % du volume du jour ; report 10 séances ; annulation et "
                        "ressaisie le jour d'un détachement ou d'une division"},
        parametres={"mode": "limite", "participation_volume": 0.10, "validite_seances": 10},
        mesure=["part des titres servis à 1, 3 et 10 séances", "prix payé contre cours moyen du jour",
                "prix payé contre dernier cours"],
        duree_min="12 mois", decision_ecrite=("Aucune clause de retrait : c'est une mesure. Changer la règle des prix "
                                              "limites serait un nouvel article."),
        source_spec="cahier §8.3, §F12 (écart déclaré au §7.1 de la spécification)", mention=TEXTE_8_3)
    e_b = _article(
        type="ecart_execution", id="E-B", proposition="oui", choix=list(_OUI_NON),
        phrase=("Compléter un ordre servi en partie, et placer un apport d'argent frais sans attendre la remise à niveau "
                "de janvier."),
        regle={"texte": "options --completer et --apport (F13b) : achat du manque d'un ordre servi en partie, sans la "
                        "bande de 2 points, limite recalculée du jour, contrôle du pire cas ; apport : cibles sur la valeur "
                        "réelle (titres au cours plus liquidités réelles), aucune vente"},
        parametres={"completer": True, "apport": True},
        mesure=["part investie après les ordres", "ordres en plus", "frais en plus"],
        duree_min="12 mois",
        decision_ecrite=("Retiré si un complément coûte, en frais facturés par franc, plus de deux fois l'ordre d'origine "
                         "(cas d'un minimum par ordre)."),
        source_spec="cahier §8.3, §F13b", mention=TEXTE_8_3)
    e_a = _article(
        type="ecart_execution", id="E-A", proposition="au choix de l'utilisateur", choix=list(_OUI_NON),
        phrase="Arrondir certaines lignes au titre supérieur, en gardant une marge de deux trimestres de frais sur le compte.",
        regle={"texte": "option --arrondi restes (F13c) : un titre de plus au plus par ligne, par reste décroissant, sous "
                        "le contrôle du pire cas avec une marge de deux trimestres de frais fixes, des plafonds et des 10 "
                        "séances ; refusée sur un tarif supposé sauf emploi sur papier"},
        parametres={"arrondi": "restes", "marge_trimestres": 2},
        mesure=["francs placés en plus", "marge du pire cas à chaque ordre"], duree_min="12 mois",
        decision_ecrite=("Retiré si, une seule fois, la provision au prix limite dépasse les liquidités, ou si la grille "
                         "réelle rend la marge négative."),
        source_spec="cahier §8.3, §F13c", mention=TEXTE_8_3)
    n = _article(
        type="essai", id="N", proposition="oui", choix=["oui"],
        phrase=("Le panier de référence avec les notes de l'analyste : le seul essai sur papier qui cherche à faire mieux "
                "que le panier sans les notes."),
        regle={"texte": "REF-S2, plus les notes de l'analyste (veto, filtres de risque, inclinaisons), en règle stricte à "
                        "la date de décision ; tout le reste est identique",
               "pourquoi": "l'ordre par défaut applique les notes ; elles n'ont jamais été testées (D11)"},
        parametres={"base": "REF-S2", "notes": "journal des notes, règle stricte à la date de décision",
                    "mesure_principale": "d_t = rendement hebdomadaire net de N − celui de REF-S2",
                    "statistique": {"t": "Newey-West, 4 retards", "intervalle": "bootstrap stationnaire, blocs de 8 "
                                                                                "semaines, 5 000 tirages, graine 0"},
                    "seuils": {"t_retrait": -2.0, "retard_cumule_retrait_points": 3.0, "t_confirmation": 3.0,
                               "dsr_confirmation": 0.95, "p_unilaterale": "0,05 ÷ m"},
                    "comparaisons_multiples": {"m_option_1": "2 au départ (N et E-D), 3 dès que E-C s'écarte du témoin",
                                               "m_option_2": 1, "bonferroni": "0,05 ÷ m, en plus de t ≥ 3,0",
                                               "dsr": "tous les essais du registre, plus grande des deux variances"}},
        hypotheses_de_travail=["parametres.seuils.t_retrait", "parametres.seuils.retard_cumule_retrait_points"],
        mesure=["d_t hebdomadaire contre REF-S2",
                "mesure secondaire descriptive : rendement à 60 séances des titres bloqués par une note (lecture après 30 "
                "blocages sans chevauchement ; aucune décision n'en dépend)"],
        duree_min="aucune lecture de rendement avant 52 semaines ; aucune affirmation avant 156 semaines",
        decision_ecrite=("Notes retirées de l'ordre : à un point d'étape d'au moins 52 semaines, si t ≤ −2,0 ou si le "
                         "retard cumulé de N sur REF-S2 atteint 3 points [seuils : Hypothèse de travail, à valider]. Notes "
                         "confirmées : seulement à 156 semaines ou plus, si t ≥ 3,0 et p unilatérale ≤ 0,05 ÷ m et DSR ≥ "
                         "0,95. Sinon « indéterminé » : rien ne change. Prédiction écrite d'avance : « indéterminé » est le "
                         "résultat le plus probable, même si les notes sont utiles."),
        source_spec="cahier §8.4 (article 5), §8.5 ; SPECIFICATION_STRATEGIE.md §8.1, D11",
        registre={"id": "S2-N", "variante": "REF+notes", "famille": "S2-rendement"})
    e_c = _article(
        type="essai", id="E-C", proposition="option 1", choix=list(_OPTIONS),
        phrase=("Ne pas vendre un titre quand des bulletins de la bourse manquent : on garde la ligne et on attend des "
                "données complètes."),
        regle={"texte": "REF-S2 + option --continuite (F13e) : pas de vente pour une inéligibilité calculée sur une fenêtre "
                        "de 126 séances où des bulletins manquent ; âge des ordres compté en bulletins disponibles ; les "
                        "sorties pour cause réelle restent", "portefeuille": "REF-S2 plus cet écart seul, exécution sur "
                                                                           "papier en mode test, 10 M, tarif supposé"},
        parametres={"base": "REF-S2", "option": "--continuite", "execution": "papier, mode test"},
        mesure=["épisodes de bulletins manquants", "ventes évitées", "titres gardés et leur sort dans les 20 séances "
                                                                    "suivantes", "d_t contre REF-S2, publié"],
        duree_min="aucune prétention de rendement avant 156 semaines",
        decision_ecrite=("Retenue dans PLAN si aucun titre réellement suspendu ou radié n'a été gardé à tort plus de 20 "
                         "séances ; retirée sinon. À 156 semaines, mêmes conditions que N pour toute affirmation. Compte "
                         "dans m dès son premier écart au témoin (clone tant qu'il lui est identique)."),
        source_spec="cahier §8.4 (article 6) ; SPECIFICATION_STRATEGIE.md §8.5 (i)",
        registre={"id": "S2-EC", "variante": "REF+E-C", "famille": "S2-rendement"},
        mention="Option 1 (proposée) : essai déclaré, conforme au §8.5 de la spécification. Option 2 : dérogation signée.")
    e_d = _article(
        type="essai", id="E-D", proposition="option 1", choix=list(_OPTIONS),
        phrase=("Chaque fin de mois, remettre au travail l'argent qui dort sur une seule ligne, sans attendre la remise à "
                "niveau de janvier."),
        regle={"texte": "REF-S2 + option --reinvestir (F13d) : à la dernière séance du mois, une seule ligne (le plus "
                        "grand manque), montant permis min(D ; borne de la ligne), seuil max(100 000 ; minimum par ordre ÷ "
                        "courtage), aucune vente", "portefeuille": "REF-S2 plus cet écart seul, exécution sur papier en "
                                                                  "mode test, 10 M, tarif supposé"},
        parametres={"base": "REF-S2", "option": "--reinvestir", "execution": "papier, mode test",
                    "seuil_fcfa": 100_000},
        mesure=["argent qui dort moyen", "ordres par an", "frais par franc réinvesti", "d_t contre REF-S2",
                "effet d'exposition = (part investie de E-D − part investie de REF-S2) × variation du marché, publié"],
        duree_min="retrait possible au 31/01/2028 ; confirmation seulement à 156 semaines ou plus",
        decision_ecrite=("Retiré au 31/01/2028 si les frais par franc réinvesti dépassent 1,5 fois ceux de l'ordre d'entrée, "
                         "ou s'il y a plus de 6 ordres par an ; sinon « en cours ». Confirmé seulement à 156 semaines ou "
                         "plus, avec les conditions de N ; sinon « indéterminé »."),
        source_spec="cahier §8.4 (article 7) ; SPECIFICATION_STRATEGIE.md §8.5 (ii)",
        registre={"id": "S2-ED", "variante": "REF+E-D", "famille": "S2-rendement"},
        mention="Le déclarer, c'est choisir d'être plus exposé au marché de mai à janvier.")
    plan = _article(
        type="regle_papier", id="PLAN", proposition="avec les notes", choix=["avec les notes", "sans les notes"],
        phrase=("Le plan suivi sur papier : l'ordre par défaut, avec la mémoire de la remise à niveau de janvier et "
                "les écarts que vous acceptez."),
        regle={"texte": "ordre par défaut (recommend sans option) + mémoire annuelle (--suivi) + les écarts déclarés "
                        "« oui » ; ce n'est pas « ce que fait la commande par défaut », qui n'a pas de mémoire",
               "taille": f"{capital} FCFA, tarif supposé", "role": "vérification comptable ; jamais comparé au témoin "
                                                                   "sur le rendement"},
        parametres={"notes_dans_l_ordre": None, "memoire": True, "ecarts_oui": []},
        mesure=["identité comptable", "frais payés contre frais prévus", "argent qui dort contre la règle déclarée",
                "ordres servis"],
        duree_min="12 mois", decision_ecrite="Aucune décision sur le rendement : PLAN ne compte pas dans m.",
        source_spec="cahier §8.6 ; question 1 du §13 (les notes dans l'ordre)",
        registre={"id": "S2-PLAN", "variante": "PLAN", "famille": "S2-execution"},
        mention="Question : garder l'ordre par défaut « avec notes » pendant le suivi (proposé) ou revenir à la règle testée.")
    return [ref, e_l, e_b, e_a, n, e_c, e_d, plan]


def preparer(articles: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Articles répondus → lignes à signer (sans les champs de signature). ``ValueError`` si une réponse manque ou n'est
    pas dans ``choix``. E-C et E-D : ``option 1`` → essai ; ``option 2 : oui|non`` → dérogation signée (texte du §8.5
    cité) ; ``non déclaré`` → aucune ligne (ils restent éteints dans PLAN)."""
    fautes: list[str] = []
    out: list[dict[str, Any]] = []
    for a in articles:
        a = copy.deepcopy(dict(a))
        if a.get("type") not in TYPES:
            fautes.append(f"{a.get('id')} : type inconnu {a.get('type')!r}")
            continue
        if a.get("type") not in ("retrait", "remplace") and a.get("id") not in IDS:
            fautes.append(f"identifiant inconnu {a.get('id')!r} (attendus : {', '.join(IDS)})")
            continue
        rep = a.get("reponse")
        if a.get("reponse_requise", True) and a.get("choix") and rep not in a["choix"]:
            fautes.append(f"{a['id']} : réponse attendue parmi {a['choix']} (proposition : {a.get('proposition')})")
            continue
        out.append(a)
    opts = {a["id"]: str(a.get("reponse") or "") for a in out if a.get("id") in ("E-C", "E-D") and a.get("type") == "essai"}
    genres = {r.split(" :")[0] for r in opts.values() if r.startswith("option")}
    if len(genres) > 1:
        fautes.append("E-C et E-D : une seule option pour les deux (option 1 : essais déclarés ; option 2 : dérogation "
                      "signée), §8.4 et §8.5 ; réponses données : "
                      + ", ".join(f"{k} « {v} »" for k, v in sorted(opts.items())))
    if fautes:
        raise ValueError("déclaration incomplète : " + " ; ".join(fautes))
    lignes_: list[dict[str, Any]] = []
    for a in out:
        if a["id"] in ("E-C", "E-D") and a["type"] == "essai":
            rep = a["reponse"]
            if rep == "non déclaré":
                continue
            if rep.startswith("option 2"):
                a["type"] = "derogation"
                a["registre"] = None
                a["parametres"] = {**a.get("parametres", {}), "applique_dans_plan": rep.endswith("oui"),
                                   "texte_cite": TEXTE_8_5}
                a["decision_ecrite"] = ("Dérogation signée à la spécification §8.5 : cet écart devient une décision "
                                        "d'exécution du §8.3, n'est pas inscrit au registre et ne compte ni dans N ni dans "
                                        "m. " + TEXTE_8_3)
        lignes_.append(a)
    ecarts = [a["id"] for a in lignes_ if (a["type"] == "ecart_execution" and a.get("reponse") == "oui")
              or (a["id"] in ("E-C", "E-D") and (a["type"] == "essai" or a["parametres"].get("applique_dans_plan")))]
    for a in lignes_:
        if a["id"] == "PLAN" and a["type"] == "regle_papier":
            a["parametres"] = {**a.get("parametres", {}), "ecarts_oui": ecarts,
                               "notes_dans_l_ordre": a.get("reponse") == "avec les notes"}
    return lignes_


# ---------------------------------------------------------------------------
# Signature, dépôt de développement, empreintes
# ---------------------------------------------------------------------------


def valider_signature(signe_par: Any) -> str:
    """Initiales ou pseudonyme : 1 à 12 caractères, lettres, chiffres et tirets seulement (ni espace ni « @ »)."""
    s = "" if signe_par is None else str(signe_par)
    if not (1 <= len(s) <= 12) or not all(c.isalnum() or c == "-" for c in s):
        raise SignatureInvalide("signature refusée : initiales ou pseudonyme de 1 à 12 caractères (lettres, chiffres, "
                                "tirets), jamais un nom complet ni une adresse")
    return s


def lire_signature(profil: str | Path | None = None) -> dict[str, str]:
    """Signature choisie par l'humain, lue dans ``<profil>/signature.json`` (défaut : ``<données>/profil``), hors dépôt :
    ``{"signe_par": "AB"}`` (initiales ou pseudonyme) ou ``{"signe_par_empreinte": "<SHA-256 d'un texte secret>"}``.
    Fichier absent : ``{}``. Contenu invalide : ``SignatureInvalide``."""
    p = (Path(profil) if profil is not None else _paths.DATA_DIR / "profil") / "signature.json"
    if not p.exists():
        return {}
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SignatureInvalide(f"signature illisible : {p} ({exc})") from exc
    if not isinstance(d, Mapping):
        raise SignatureInvalide(f"signature illisible : {p} (un dictionnaire est attendu)")
    if d.get("signe_par_empreinte"):
        h = str(d["signe_par_empreinte"]).strip().lower()
        if not re.fullmatch(r"[0-9a-f]{64}", h):
            raise SignatureInvalide("signe_par_empreinte : 64 caractères hexadécimaux (SHA-256) attendus")
        return {"signe_par_empreinte": h}
    for k in ("signe_par", "initiales", "pseudonyme"):
        if d.get(k):
            return {"signe_par": valider_signature(d[k])}
    return {}


def depot_de_developpement(racine: str | Path | None = None) -> bool:
    """Vrai si ``racine`` (défaut : racine du code) est le dépôt de développement : un ``.git`` à la racine ou dans son
    dossier parent **et** ``reports/trials.parquet`` suivi par git (``git ls-files --error-unmatch``), c'est-à-dire
    ``reports/`` suivi par git. Une simple présence de ``.git`` (copie de l'installation par un clone) ne suffit pas :
    il faut aussi que le registre soit un fichier suivi de ce dépôt."""
    r = Path(racine) if racine is not None else _paths.REPO_ROOT
    if not ((r / ".git").exists() or (r.parent / ".git").exists()):
        return False
    try:
        res = subprocess.run(["git", "-C", str(r), "ls-files", "--error-unmatch", "reports/trials.parquet"],
                             capture_output=True, text=True, timeout=20, check=False)
    except (OSError, subprocess.SubprocessError):
        return False
    return res.returncode == 0


def _sha_fichier(p: Path) -> str | None:
    import hashlib

    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


def _version_code(racine: Path) -> str:
    try:
        r = subprocess.run(["git", "-C", str(racine), "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                           timeout=10, check=False)
        v = r.stdout.strip()
        return v if r.returncode == 0 and v else "inconnu"
    except (OSError, subprocess.SubprocessError):
        return "inconnu"


def empreintes(racine: str | Path | None = None, *, strategie: Mapping[str, Any] | None = None,
               reglages_chemin: str | Path | None = None, cahier_chemin: str | Path | None = None) -> dict[str, Any]:
    """Empreintes qui datent la déclaration : ``empreinte_config`` (``settings.config_fingerprint`` du YAML de stratégie),
    ``empreinte_reglages`` (SHA-256 de ``configs/rendement_net.yaml``), ``empreinte_cahier`` (SHA-256 de
    ``docs/RENDEMENT_NET.md``) : fichiers du code (``paths.REPO_ROOT``) ; ``version_code`` : commit git court du dépôt
    ``racine``. Lecture seule."""
    from brvm_alpha import settings

    r = Path(racine) if racine is not None else _paths.REPO_ROOT
    cfg = strategie if strategie is not None else settings.load_strategy_config()
    reg = Path(reglages_chemin) if reglages_chemin is not None else _paths.REPO_ROOT / "configs" / "rendement_net.yaml"
    cah = Path(cahier_chemin) if cahier_chemin is not None else _paths.REPO_ROOT / "docs" / "RENDEMENT_NET.md"
    return {"empreinte_config": settings.config_fingerprint(cfg), "empreinte_reglages": _sha_fichier(reg),
            "empreinte_cahier": _sha_fichier(cah), "version_code": _version_code(r)}


def _prochaine_seance(t: pd.Timestamp) -> pd.Timestamp:
    from brvm_alpha.portfolio import recommend as R

    return pd.Timestamp(R.future_sessions(t, 1)[0])


def _effet(maintenant: pd.Timestamp, reglages: Mapping[str, Any] | None) -> str:
    """Date d'effet : le début du suivi pour une ligne écrite avant ; sinon la prochaine séance (l'avenir seulement)."""
    debut = pd.Timestamp(str(_rg.lire(reglages, "dates.debut_suivi", "2026-12-01")))
    jour = maintenant.tz_convert(None).normalize() if maintenant.tzinfo is not None else maintenant.normalize()
    if jour < debut:
        return debut.date().isoformat()
    return _prochaine_seance(jour).date().isoformat()


# ---------------------------------------------------------------------------
# Lecture, vérification, signature
# ---------------------------------------------------------------------------


def lignes(dossier: str | Path) -> list[dict[str, Any]]:
    """Lignes de la déclaration (``<dossier>/declaration.jsonl``), dans l'ordre ; ``[]`` si le fichier n'existe pas."""
    return [o for _b, o in _s.lire_jsonl(Path(dossier) / FICHIER) if o is not None]


def _sceaux_du_registre(registre: str | Path) -> list[dict[str, Any]]:
    """Sceaux de la déclaration écrits dans le registre à l'inscription (lignes S2) : ``n`` et empreinte de la ligne
    citée, nombre de lignes et empreinte de la dernière ligne au moment de l'inscription."""
    p = Path(registre)
    if not p.exists():
        return []
    reg = pd.read_parquet(p)
    out = []
    for r in reg.to_dict("records"):
        if str(r.get("echantillon")) != "S2" or FICHIER not in str(r.get("source") or ""):
            continue
        try:
            par = json.loads(str(r.get("parametres") or "{}"))
        except (TypeError, ValueError):
            par = {}
        sc = par.get("declaration") if isinstance(par, Mapping) else None
        if isinstance(sc, Mapping):
            out.append({"id": str(r.get("id")), **sc})
    return out


def verifier(dossier: str | Path, registre: str | Path | None = None) -> dict[str, Any]:
    """Contrôle de la déclaration : chaque ligne se lit, ``n`` suit 1, 2, 3…, ``empreinte`` est celle de son contenu et
    ``precedente`` est le SHA-256 du texte exact de la ligne précédente. Toute réécriture rompt la chaîne
    (``chaine_ok`` faux : le feu « Données » passe au rouge). Fichier absent : ``existe`` faux, aucune anomalie.

    ``registre`` (chemin du registre des essais, lecture seule) : la suppression des **dernières** lignes ne rompt pas
    la chaîne à elle seule ; les sceaux écrits à l'inscription (ligne citée par ``source``, nombre de lignes et
    empreinte de la dernière ligne) la détectent."""
    p = Path(dossier) / FICHIER
    brut = _s.lire_jsonl(p)
    anomalies: list[str] = []
    prec = _s.ZERO
    for i, (txt, obj) in enumerate(brut, start=1):
        if obj is None:
            anomalies.append(f"ligne {i} illisible")
            prec = _s.empreinte_texte(txt)
            continue
        if obj.get("n") != i:
            anomalies.append(f"ligne {i} : numéro {obj.get('n')!r} au lieu de {i}")
        if obj.get("precedente") != prec:
            anomalies.append(f"ligne {i} : chaîne rompue (la ligne précédente a été modifiée, retirée ou déplacée)")
        contenu = {k: v for k, v in obj.items() if k != "empreinte"}
        if obj.get("empreinte") != _s.empreinte(contenu):
            anomalies.append(f"ligne {i} : contenu modifié après la signature")
        if obj.get("type") not in TYPES:
            anomalies.append(f"ligne {i} : type inconnu {obj.get('type')!r}")
        prec = _s.empreinte_texte(txt)
    if registre is not None:
        textes = [t for t, _o in brut]
        objets = [o for _t, o in brut]
        for sc in _sceaux_du_registre(registre):
            n, nl = int(sc.get("n") or 0), int(sc.get("n_lignes") or 0)
            if n < 1 or n > len(objets) or not isinstance(objets[n - 1], Mapping) or \
                    objets[n - 1].get("empreinte") != sc.get("empreinte_ligne"):
                anomalies.append(f"registre {sc['id']} : la ligne {n} de la déclaration manque ou a changé")
            if nl > len(textes):
                anomalies.append(f"registre {sc['id']} : {nl} lignes à l'inscription, {len(textes)} aujourd'hui "
                                 "(dernières lignes retirées)")
            elif nl >= 1 and _s.empreinte_texte(textes[nl - 1]) != sc.get("empreinte_derniere"):
                anomalies.append(f"registre {sc['id']} : la ligne {nl} (dernière à l'inscription) a changé")
    ok = not anomalies
    return {"fichier": str(p), "existe": p.exists(), "n_lignes": len(brut), "chaine_ok": ok, "ok": ok,
            "anomalies": anomalies, "derniere": prec if brut else None,
            "mention": None if p.exists() else MENTION_SANS_DECLARATION}


def signer(articles: Sequence[Mapping[str, Any]], signe_par: str | None = None, dossier: str | Path | None = None, *,
           profil: str | Path | None = None, racine: str | Path | None = None, maintenant: Any = None,
           reglages: Mapping[str, Any] | None = None, strategie: Mapping[str, Any] | None = None,
           reglages_chemin: str | Path | None = None, cahier_chemin: str | Path | None = None) -> Path:
    """Signe et écrit les articles répondus à la fin de ``<dossier>/declaration.jsonl`` (ajout seul) ; rend le chemin.

    ``dossier`` est **obligatoire** (en usage réel : ``reports/suivi_S2`` du dépôt de développement, sur commande
    explicite de l'humain ; dans les tests : un dossier temporaire). ``signe_par`` : initiales ou pseudonyme ; absent,
    il est lu dans ``<profil>/signature.json`` ; donné alors que le profil en contient d'autres : refus.

    Refus, sans rien écrire : hors du dépôt de développement (:class:`HorsDepot`, code 2, message
    :data:`MESSAGE_HORS_DEPOT`) ; signature invalide ; réponse manquante ; chaîne existante rompue (« aucune ligne ne
    peut être ajoutée avant une décision humaine écrite ») ; article identique à la dernière ligne signée pour le même
    identifiant (:class:`SignatureInvalide` : une deuxième signature du même texte, par les mêmes initiales ou par
    d'autres, ajouterait des lignes définitives en double). Une ligne écrite après le début du suivi ne vaut que pour
    l'avenir (``effet_a_partir_du`` = prochaine séance). Lecture de la chaîne et ajout sous le verrou d'écriture du
    dossier (code 4 s'il reste tenu par une autre opération)."""
    if dossier is None:
        raise ValueError("dossier de la déclaration obligatoire (aucun chemin par défaut)")
    r = Path(racine) if racine is not None else _paths.REPO_ROOT
    if not depot_de_developpement(r):
        raise HorsDepot(MESSAGE_HORS_DEPOT)
    prof = lire_signature(profil)
    if signe_par is not None:
        sig = {"signe_par": valider_signature(signe_par)}
        if prof.get("signe_par") and prof["signe_par"] != sig["signe_par"]:
            raise SignatureInvalide("les initiales données ne sont pas celles du profil (signature.json)")
        if prof.get("signe_par_empreinte"):
            raise SignatureInvalide("le profil signe par une empreinte : ne donnez pas d'initiales")
    else:
        sig = prof
    if not sig:
        raise SignatureInvalide("aucune signature : donnez vos initiales ou écrivez-les dans <données>/profil/signature.json")
    a_ecrire = preparer(articles)
    if not a_ecrire:
        raise ValueError("aucun article à signer")
    d = Path(dossier)
    with _s.verrou_ecriture(d, quoi="déclaration du suivi"):
        return _signer(a_ecrire, sig, d, r, maintenant=maintenant, reglages=reglages, strategie=strategie,
                       reglages_chemin=reglages_chemin, cahier_chemin=cahier_chemin)


def _contenu_signe(a: Mapping[str, Any]) -> str:
    """Contenu d'un article ou d'une ligne signée (hors date, effet, empreintes du code, signature et chaîne), avec les
    valeurs par défaut de la ligne écrite par :func:`signer`."""
    return _s.canonique({
        "type": a.get("type"), "id": a.get("id"), "phrase": a.get("phrase", ""), "regle": a.get("regle", {}),
        "parametres": a.get("parametres", {}), "mesure": a.get("mesure", []), "duree_min": a.get("duree_min", ""),
        "decision_ecrite": a.get("decision_ecrite", ""), "source_spec": a.get("source_spec", ""),
        "reponse": a.get("reponse"), "proposition": a.get("proposition"), "registre": a.get("registre"),
        "hypotheses_de_travail": a.get("hypotheses_de_travail", []), "remplace_n": a.get("remplace_n")})


def deja_signes(a_ecrire: Sequence[Mapping[str, Any]], existantes: Sequence[Mapping[str, Any]]) -> list[str]:
    """Identifiants des articles ``a_ecrire`` (sortie de :func:`preparer`) identiques à la dernière ligne signée du même
    identifiant dans ``existantes`` (lignes de la déclaration)."""
    dernieres: dict[str, str] = {}
    for l in existantes:
        dernieres[str(l.get("id"))] = _contenu_signe(l)
    return [str(a.get("id")) for a in a_ecrire if dernieres.get(str(a.get("id"))) == _contenu_signe(a)]


def _signer(a_ecrire: list[dict[str, Any]], sig: Mapping[str, str], d: Path, r: Path, *, maintenant: Any,
            reglages: Mapping[str, Any] | None, strategie: Mapping[str, Any] | None, reglages_chemin: Any,
            cahier_chemin: Any) -> Path:
    v = verifier(d)
    if not v["chaine_ok"]:
        raise ValueError("chaîne de la déclaration rompue : aucune ligne ne peut être ajoutée avant une décision humaine "
                         "écrite (" + " ; ".join(v["anomalies"][:3]) + ")")
    doubles = deja_signes(a_ecrire, lignes(d) if v["existe"] else [])
    if doubles:
        raise SignatureInvalide("déjà signés à l'identique : " + ", ".join(doubles) + " ; aucune ligne n'est ajoutée "
                                "(une ligne signée est définitive ; pour changer un article, signez une ligne « remplace » "
                                "ou « retrait »)")
    t = pd.Timestamp(maintenant) if maintenant is not None else pd.Timestamp.now(tz="UTC")
    if t.tzinfo is None:
        t = t.tz_localize("UTC")
    emp = empreintes(r, strategie=strategie, reglages_chemin=reglages_chemin, cahier_chemin=cahier_chemin)
    effet = _effet(t, reglages)
    n0 = v["n_lignes"]
    prec = v["derniere"] or _s.ZERO
    textes: list[dict[str, Any]] = []
    for i, a in enumerate(a_ecrire, start=1):
        ligne = {
            "n": n0 + i, "date_utc": t.isoformat(), "type": a["type"], "id": a["id"], "phrase": a.get("phrase", ""),
            "regle": a.get("regle", {}), "parametres": a.get("parametres", {}), "mesure": a.get("mesure", []),
            "duree_min": a.get("duree_min", ""), "decision_ecrite": a.get("decision_ecrite", ""),
            "source_spec": a.get("source_spec", ""), "effet_a_partir_du": effet,
            "declaree_apres_debut": effet != str(_rg.lire(reglages, "dates.debut_suivi", "2026-12-01")),
            "reponse": a.get("reponse"), "proposition": a.get("proposition"), "registre": a.get("registre"),
            "hypotheses_de_travail": a.get("hypotheses_de_travail", []), "remplace_n": a.get("remplace_n"),
            **emp, **sig, "precedente": prec}
        ligne["empreinte"] = _s.empreinte(ligne)
        prec = _s.empreinte_texte(_s.ligne_json(ligne))
        textes.append(ligne)
    _s.ajouter_jsonl(d / FICHIER, textes, hors_reports=False)
    return d / FICHIER


# ---------------------------------------------------------------------------
# Règles en vigueur
# ---------------------------------------------------------------------------


def en_vigueur(date: Any, dossier: str | Path | None = None) -> dict[str, Any]:
    """Règles en vigueur à ``date`` : pour chaque identifiant, la dernière ligne dont ``effet_a_partir_du`` ≤ date ; une
    ligne ``remplace`` remplace l'article pour l'avenir, une ligne ``retrait`` le retire. Sans déclaration : seul le
    témoin ``REF-S2`` (définition du test, sans signature)."""
    t = pd.Timestamp(date).normalize()
    ls = lignes(dossier) if dossier is not None else []
    v = verifier(dossier) if dossier is not None else {"chaine_ok": True}
    if not ls:
        ref = next(a for a in modele() if a["id"] == "REF-S2")
        return {"declaration": False, "chaine_ok": v["chaine_ok"], "articles": {"REF-S2": ref},
                "mention": MENTION_SANS_DECLARATION, "declaree_apres_debut": False}
    arts: dict[str, dict[str, Any]] = {}
    apres = False
    for l in ls:
        if pd.Timestamp(l.get("effet_a_partir_du") or "2100-01-01") > t:
            continue
        apres = apres or bool(l.get("declaree_apres_debut"))
        if l.get("type") == "retrait":
            arts.pop(str(l.get("id")), None)
            continue
        arts[str(l.get("id"))] = l
    return {"declaration": True, "chaine_ok": v["chaine_ok"], "articles": arts, "declaree_apres_debut": apres,
            "mention": "déclarée après le début du suivi" if apres else None}


# ---------------------------------------------------------------------------
# Registre des essais
# ---------------------------------------------------------------------------


def _valeur_canonique(x: Any) -> Any:
    if x is None:
        return None
    try:
        if pd.isna(x):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(x, pd.Timestamp):
        return x.isoformat()
    if hasattr(x, "isoformat"):
        return x.isoformat()
    return str(x)


def empreinte_lignes(frame: pd.DataFrame, n: int | None = None) -> str:
    """SHA-256 du contenu des ``n`` premières lignes d'un registre (toutes si ``n`` est vide), colonnes triées, valeurs
    en texte : sert à prouver que les lignes existantes ne changent pas."""
    f = frame if n is None else frame.iloc[: int(n)]
    recs = [{c: _valeur_canonique(row[c]) for c in sorted(f.columns)} for _i, row in f.iterrows()]
    return _s.empreinte(recs)


def _base_source(dossier: Path, source_base: str | None) -> str:
    """Chemin de la déclaration écrit dans ``source`` : relatif à la racine du code ; un dossier hors du dépôt est
    refusé (aucune provenance fabriquée), sauf ``source_base`` explicite (réservé aux tests sur des copies)."""
    if source_base is not None:
        return f"{str(source_base).rstrip('/')}/{FICHIER}"
    try:
        rel = Path(os.path.abspath(dossier / FICHIER)).relative_to(Path(os.path.abspath(_paths.REPO_ROOT)))
    except ValueError:
        raise ValueError(f"inscription refusée : la déclaration ({dossier}) n'est pas dans le dépôt "
                         f"({_paths.REPO_ROOT}) ; la provenance écrite au registre serait fausse") from None
    return rel.as_posix()


def inscrire_au_registre(dossier: str | Path, registre: str | Path, *, confirmer: str | None = None,
                         source_base: str | None = None) -> list[str]:
    """Ajoute au registre des essais les lignes ``S2-REF`` (famille ``S2-temoin``), ``S2-N`` (``S2-rendement``),
    ``S2-EC`` et ``S2-ED`` (``S2-rendement``, seulement s'ils sont déclarés comme essais) et ``S2-PLAN``
    (``S2-execution``) : ``echantillon`` = ``S2``, ``statut`` = ``pré-enregistré``, ``parametres`` = la règle déclarée,
    ``source`` = ``reports/suivi_S2/declaration.jsonl#<n>``. Rend les identifiants ajoutés.

    ``registre`` est le chemin **passé explicitement** (aucun défaut) : la fonction n'écrit nulle part ailleurs.
    ``confirmer`` doit valoir exactement :data:`CONFIRMATION_REGISTRE`. Refus si la chaîne de la déclaration est rompue,
    ou si le dossier n'est pas dans le dépôt (``source`` serait faux), sauf ``source_base`` explicite (tests). Chaque
    ligne porte dans ``parametres.declaration`` le sceau de la déclaration (ligne citée et son empreinte, nombre de
    lignes, empreinte de la dernière) : :func:`verifier` avec le registre détecte ensuite une troncature.
    Les lignes existantes ne sont ni modifiées ni réordonnées (empreinte vérifiée sur une copie avant de remplacer le
    fichier) ; une seconde inscription n'ajoute aucune ligne en double. C'est la seule écriture du module dans ce
    fichier. Lecture de la déclaration et du registre, puis remplacement du registre, sous le verrou d'écriture du
    dossier de la déclaration (code 4 s'il reste tenu par une autre opération)."""
    if registre is None or not str(registre).strip():
        raise ValueError("registre des essais : chemin obligatoire, passé explicitement")
    if confirmer != CONFIRMATION_REGISTRE:
        raise PermissionError(f"inscription refusée : recopiez exactement « {CONFIRMATION_REGISTRE} »")
    d = Path(dossier)
    base = _base_source(d, source_base)
    if not d.is_dir():
        raise ValueError("inscription refusée : déclaration absente (aucune ligne signée)")
    with _s.verrou_ecriture(d, quoi="déclaration du suivi et registre des essais"):
        return _inscrire(d, Path(registre), base)


def _inscrire(d: Path, p: Path, base: str) -> list[str]:
    from brvm_alpha import settings
    from brvm_alpha.backtest.walkforward import REGISTRY_COLUMNS, STATUT_PREENREGISTRE, TrialRegistry

    v = verifier(d)
    if not v["existe"] or not v["chaine_ok"]:
        raise ValueError("inscription refusée : déclaration absente ou chaîne rompue (" + " ; ".join(v["anomalies"][:3]) + ")")
    if not p.exists():
        raise FileNotFoundError(f"registre introuvable : {p} (il n'est jamais créé ici)")
    avant = pd.read_parquet(p)
    manq = [c for c in REGISTRY_COLUMNS if c not in avant.columns]
    if manq:
        raise ValueError(f"registre : colonnes manquantes {manq}")
    n_avant = len(avant)
    emp_avant = empreinte_lignes(avant)
    deja = set(avant["id"].astype(str))
    derniers: dict[str, dict[str, Any]] = {}
    for l in lignes(d):
        reg = l.get("registre")
        if isinstance(reg, Mapping) and reg.get("id") and l.get("type") in ("reference", "essai", "regle_papier",
                                                                             "remplace"):
            derniers[str(reg["id"])] = l
        if l.get("type") in ("derogation", "retrait"):
            for k in [k for k, x in derniers.items() if x.get("id") == l.get("id")]:
                derniers.pop(k)
    try:
        fp = settings.config_fingerprint(settings.load_strategy_config())
    except MemoryError:  # mémoire insuffisante : la commande s'arrête (code 6)
        raise
    except Exception:  # noqa: BLE001 - empreinte illisible : celle de la ligne signée fait foi
        fp = None
    rows = []
    for rid in ("S2-REF", "S2-N", "S2-EC", "S2-ED", "S2-PLAN"):
        l = derniers.get(rid)
        if l is None or rid in deja:
            continue
        reg = l["registre"]
        sceau = {"n": int(l["n"]), "empreinte_ligne": l.get("empreinte"), "n_lignes": int(v["n_lignes"]),
                 "empreinte_derniere": v["derniere"]}
        rows.append({"id": rid, "variante": str(reg.get("variante") or l.get("id")), "famille": str(reg["famille"]),
                     "parametres": _s.canonique({"regle": l.get("regle"), "parametres": l.get("parametres"),
                                                 "effet_a_partir_du": l.get("effet_a_partir_du"), "declaration": sceau}),
                     "echantillon": "S2", "statut": STATUT_PREENREGISTRE, "date_execution": pd.NaT,
                     "rendements_hebdo": None, "metriques": None,
                     "empreinte_config": str(l.get("empreinte_config") or fp or ""),
                     "source": f"{base}#{int(l['n'])}", "note": str(l.get("phrase") or "")})
    if not rows:
        return []
    neuf = pd.concat([avant.astype(object), pd.DataFrame(rows, columns=list(REGISTRY_COLUMNS)).astype(object)],
                     ignore_index=True)
    tmp = p.with_name(p.name + ".inscription.tmp")
    try:
        TrialRegistry(tmp, neuf).save(tmp)
        relu = pd.read_parquet(tmp)
        if len(relu) != n_avant + len(rows) or empreinte_lignes(relu, n_avant) != emp_avant:
            raise RuntimeError("inscription annulée : les lignes existantes du registre auraient changé")
        os.replace(tmp, p)
    finally:
        if tmp.exists():
            tmp.unlink()
    return [r["id"] for r in rows]
