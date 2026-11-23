"""Données fixes de l'interface du module « Rendement net et pertes » (aucun accès au disque, aucune horloge).

Servent aux tests ``tests/test_ui_rendement.py`` et aux pages de référence ``tests/ui_reference_pages.py`` : un
``rendement_net`` réduit (table de choix à deux lignes, dont « tout »), un ordre d'une ligne (SNTS, 629 titres à
4 040 FCFA, comme l'ordre de 10 000 000 FCFA du 20/11/2026), le cache de l'écran et les états des cartes.
Performance passée ≠ garantie. Aucun gain n'est garanti.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

#: Jour d'affichage fixe (mardi) et dernier bulletin du panel des doublures.
JOUR = "2026-11-24"
ASOF = "2026-11-20"
CAPITAL = 10_000_000.0

RN_MINI: dict[str, Any] = {
    "version": 1, "bandeau": "Performance passée ≠ garantie. Aucun gain n'est garanti.",
    "contexte": {"capital": CAPITAL, "asof": ASOF, "variante": "REF", "statut": "REJETÉ", "panel_en_retard": None,
                 "n_lignes_cibles": 20},
    "perte": {"table": [
        {"perte_toleree": 1_000_000.0, "tout": False, "en_actions": 3_000_000, "reserve": 7_000_000,
         "annee_2018": [824_753.0, 974_805.0], "pire_moment_2018": 1_036_589.0, "baisse_2017_2020": 1_403_952.0,
         "depasse": {"pire_moment": True, "2017_2020": True},
         "annee_ordinaire": {"prudente": 118_000.0, "flatteuse": 263_349.0}, "mention": ""},
        {"perte_toleree": None, "tout": True, "en_actions": 10_000_000, "reserve": 0,
         "annee_2018": [2_600_000.0, 3_114_258.0], "pire_moment_2018": 3_330_000.0, "baisse_2017_2020": 4_590_000.0,
         "depasse": {}, "annee_ordinaire": {"prudente": 660_000.0, "flatteuse": 900_000.0}, "mention": ""}],
        "choix": None, "phrases": []},
    "suivi": None,
}

ORDRE_MINI: dict[str, Any] = {
    "bandeau": "Performance passée ≠ garantie. Aucun gain n'est garanti.", "statut": "REJETÉ", "asof": ASOF,
    "capital": CAPITAL, "valeur_portefeuille": CAPITAL, "liquidites_initiales": CAPITAL,
    "lignes": [{"symbole": "SNTS", "sens": "achat", "quantite": 629, "cours_reference": 4040.0, "prix_limite": 4080.0,
                "tranches": [629], "demi_spread_pct": 0.0010626992561105207, "mdv63": 852_282_472.5}],
    "couts": {"scenario": "central", "investi_apres": 2_541_160, "n_lignes": 1, "taux_courtage": 0.008,
              "taux_tva": 0.18, "taux_brvm": 0.002, "taux_dcbr": 0.001, "kappa": 0.016, "taux_garde": 0.0025,
              "frais_par_ligne": 5000.0, "forfait_compte_annuel": 0},
}


def plan_mini(jour: str = JOUR) -> dict[str, Any]:
    from brvm_alpha.rendement import plan as PL

    return PL.construire_plan(copy.deepcopy(RN_MINI), None, None, jour)


def cache_mini(asof: str = ASOF, calcule: str = "2026-11-23T05:00:00+00:00") -> dict[str, Any]:
    rn = copy.deepcopy(RN_MINI)
    rn["contexte"]["asof"] = asof
    return {"version": 1, "bandeau": rn["bandeau"], "calcule_utc": calcule, "asof": asof, "capital": CAPITAL,
            "capital_ordre": CAPITAL, "grille": "central", "perte_toleree": None, "empreinte_ordre": "0" * 64,
            "plan": plan_mini(), "rendement_net": rn, "ordre": {**copy.deepcopy(ORDRE_MINI), "asof": asof}}


def ecrire_cache(profil: Path, **kw: Any) -> Path:
    profil.mkdir(parents=True, exist_ok=True)
    p = profil / "plan_cache.json"
    p.write_text(json.dumps(cache_mini(**kw), ensure_ascii=False), encoding="utf-8")
    return p


def _grille_vue() -> dict[str, Any]:
    from brvm_alpha.rendement import grille as G
    from brvm_alpha.ui import rendement as RN

    return RN._grille_vue(G.defaut(), False)


def etat_carte_avec_plan() -> dict[str, Any]:
    """État de la carte « Mon plan » : calcul du 20/11/2026, à jour, sans suivi commencé."""
    from brvm_alpha.rendement import reglages as RG

    return {"cache": True, "erreur_cache": None, "plan": plan_mini(),
            "choix": [{"perte": 1_000_000.0, "tout": False, "en_actions": 3_000_000, "reserve": 7_000_000},
                      {"perte": None, "tout": True, "en_actions": 10_000_000, "reserve": 0}],
            "erreur_plan": None, "valeurs_plan": {}, "erreur_grille": None, "valeurs_grille": {}, "message": None,
            "job": None, "occupe": False, "comparaison": None, "notes": [], "bulletin": "REF-S2", "jour": JOUR,
            "phrases": [RG.PH_ETUDE, RG.phrase_seance(JOUR)], "plan_enregistre": {}, "grille": _grille_vue(),
            "dernier_bulletin": ASOF, "capital": CAPITAL, "asof": ASOF, "calcule": "2026-11-23",
            "capital_cache": CAPITAL, "perime": False, "feux_de": None}


def etat_carte_sans_plan() -> dict[str, Any]:
    """État de la carte quand aucun calcul n'est enregistré."""
    e = etat_carte_avec_plan()
    e.update({"cache": False, "plan": None, "choix": [], "asof": None, "calcule": None, "perime": False})
    return e


def etat_portefeuille() -> dict[str, Any]:
    from brvm_alpha.suivi import bulletin as BU

    b = BU.bulletin(None, nom="REF-S2", aujourd_hui=JOUR)
    return {"message": None, "erreur_revue": None, "valeurs_revue": {}, "erreur_saisie": None, "valeurs_saisie": {},
            "resultat_saisie": None, "grille_enregistree": False, "carnets": [],
            "bulletin": {"nom": "REF-S2", "presents": ["REF-S2"], "texte": BU.rendre(b, "texte"), "erreur": None,
                         "b": b}}


def etat_bulletin() -> dict[str, Any]:
    return etat_portefeuille()["bulletin"]


def etat_resultat() -> dict[str, Any]:
    from brvm_alpha.rendement import plan as PL

    p = plan_mini()
    return {"cache": True, "erreur_cache": None, "asof": ASOF, "calcule": "2026-11-23", "md": PL.rendre_plan(p, "md"),
            "texte": PL.rendre_plan(p, "texte"), "json": RN_MINI}


def etat_validation() -> dict[str, Any]:
    from brvm_alpha.suivi import declaration as DE

    lignes = []
    for a in DE.modele():
        etat = ("suivi : définition du test, sans signature" if a["id"] == "REF-S2"
                else f"non déclaré à ce jour (proposé : {a.get('proposition') or '—'})")
        lignes.append({"id": a["id"], "type": a["type"], "phrase": a.get("phrase") or "", "etat": etat,
                       "mesures": [str(m) for m in a.get("mesure") or []]})
    return {"jour": JOUR, "erreur": None, "lignes": lignes, "etat": DE.MENTION_SANS_DECLARATION, "chaine_ok": True,
            "mention": None, "prochain": ("2026-12-01", "début du suivi sur papier")}


class OrdreAvecRendement:
    """Ordre de bataille simulé (clé ``rendement_net`` calculée) pour le calcul de l'écran par l'interface."""

    def __init__(self, asof: str = ASOF):
        self.rendement_net = {**copy.deepcopy(RN_MINI), "plan": plan_mini()}
        self.rendement_net["contexte"]["asof"] = asof
        self._d = {**copy.deepcopy(ORDRE_MINI), "asof": asof}

    def to_dict(self) -> dict[str, Any]:
        return {**copy.deepcopy(self._d), "rendement_net": self.rendement_net}
