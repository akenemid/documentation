"""Interface du module « Rendement net et pertes » (cahier ``docs/RENDEMENT_NET.md``, §7.1).

* **Tableau de bord** : carte « Mon plan » en tête de page. Elle lit ``<données>/profil/plan_cache.json`` et ne lance
  jamais ``recommend`` ; elle écrit la date du bulletin du calcul et propose de recalculer (fil de travail existant,
  une opération à la fois). Trois décisions : la grille du courtier (``POST /plan/grille``, recalcul des frais sur les
  lignes du cache, en moins d'une seconde), ce que j'accepte de risquer et le taux de la réserve (``POST
  /plan/enregistrer``, puis calcul de l'écran). Liens : ``GET /plan/questions``, ``GET /plan/resultat``, ``GET
  /suivi/bulletin``.
* **Portefeuille** : champs « Ce que j'accepte de risquer », « Taux net de ma réserve », « Tarif » et trois cases non
  cochées (arrondi « plus forts restes », apport d'argent frais, compléter un ordre servi en partie), passés à
  ``recommend`` seulement s'ils sont remplis ; bulletin de la semaine ; revue guidée (``POST /suivi/revue``) ; saisie
  d'un apport, d'un retrait ou d'un avis d'opéré (``POST /suivi/saisir``).
* **Validation** : tableau « Suivi sur papier : ce qui est déclaré » et ``PH_ESSAI`` ; aucun classement par rendement.

Les fonctions ``carte_*``, ``champs_*``, ``section_*``, ``tableau_*`` et ``page_*`` sont **pures** (dictionnaire en
entrée, fragment HTML échappé en sortie : les pages de référence des tests s'en servent) ; les fonctions ``etat_*``
lisent le disque, sans rien écrire ; seules les actions ``POST`` écrivent, sous ``<données>/profil`` et
``<données>/suivi`` seulement, par écriture atomique (refusée dans l'arbre du code en mode embarqué).

Dossier de données de l'interface : ``Services.data_dir`` s'il est donné ; sinon le dossier qui contient le journal
des notes quand il est donné (``<données>/notes``) ; sinon celui de l'installation (``paths.DATA_DIR``). Ainsi une copie
du journal et du profil se sert sans toucher aux données réelles. Aucun formulaire ``GET`` n'est ajouté : les pages
nouvelles sont atteintes par des liens.

Performance passée ≠ garantie. Aucun gain n'est garanti.
"""

from __future__ import annotations

import json
import warnings
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pandas as pd

from brvm_alpha import paths
from brvm_alpha.erreurs import ErreurMoteur, VerrouOccupe
from brvm_alpha.ui import pages as P
from brvm_alpha.ui.pages import Safe, box, csrf_field, esc, join, link, table

BANNER = P.BANNER
#: Genre des travaux de calcul de l'écran « Mon plan » (fil de travail de l'interface).
JOB_PLAN = "plan"
#: Portefeuilles tenus par un carnet (revue, saisie) ; ``MOI`` d'abord : c'est le portefeuille de l'utilisateur.
CARNETS = ("MOI", "PLAN", "E-C", "E-D")
#: Portefeuilles dont le bulletin peut s'afficher.
PORTEFEUILLES = ("REF-S2", "N", "PLAN", "MOI", "E-C", "E-D")
#: Libellés des portefeuilles (lexique du cahier, §1.1 : jamais « REF » ni « S2 » seuls à l'écran).
LIBELLES = {"REF-S2": "le panier de référence (témoin)", "N": "l'essai « avec notes »", "PLAN": "mon plan sur papier",
            "MOI": "mon portefeuille", "E-C": "l'essai « données manquantes »", "E-D": "l'essai « fin de mois »"}
DECISIONS = (("garder", "garder"), ("ne-plus-acheter", "ne plus acheter"),
             ("reduire", "réduire par ordres à cours limité sur plusieurs séances"))
#: Champs de la page Portefeuille ajoutés par le module (vides ou non cochés par défaut).
CHAMPS_PORTEFEUILLE = ("perte", "taux", "tarif", "arrondi", "apport", "apport_montant", "completer")
#: Champs du formulaire « Ce que j'accepte de risquer ; où dort le reste ».
CHAMPS_PLAN = ("perte", "perte_libre", "capital", "taux", "placement", "besoin", "questions_envoyees", "recalculer")
#: Champs du formulaire « Ce que prend mon courtier » : (nom du champ du formulaire, champ de la grille, unité).
CHAMPS_GRILLE = (("courtage", "courtage", "%"), ("taxe", "taxe_courtage", "%"), ("garde", "garde", "%"),
                 ("par_ligne", "tenue_par_ligne", "FCFA"), ("forfait", "forfait_compte", "FCFA"),
                 ("min_ordre", "courtage_min_par_ordre", "FCFA"), ("taxe_frais", "taxe_frais_annuels", "%"),
                 ("garde_min", "garde_minimum", "FCFA"), ("encaissement", "encaissement_taux", "%"),
                 ("encaissement_fixe", "encaissement_fixe", "FCFA"), ("transfert", "transfert_par_ligne", "FCFA"))
#: Libellés des champs de la grille sur la carte (unité comprise).
LIBELLES_GRILLE = {"courtage": "Courtage (% du montant)", "taxe": "Taxe sur le courtage (% du courtage)",
                   "garde": "Droits de garde (% de la valeur, par an)", "par_ligne": "Tenue de compte par ligne (FCFA par an)",
                   "forfait": "Forfait de compte (FCFA par an)", "min_ordre": "Minimum de courtage par ordre (FCFA)",
                   "taxe_frais": "Taxe sur les frais annuels (%)", "garde_min": "Minimum de droits de garde (FCFA par an)",
                   "encaissement": "Encaissement des dividendes (% du dividende net)",
                   "encaissement_fixe": "Encaissement par paiement (FCFA)",
                   "transfert": "Transfert de titres par ligne (FCFA)"}
STATUTS_GRILLE = (("supposé", "supposé (non vérifié)"), ("grille écrite", "grille écrite de mon courtier"),
                  ("avis d'opéré", "avis d'opéré"))
#: Champs du formulaire de saisie du suivi (apport, retrait, avis d'opéré).
CHAMPS_SAISIE = ("nom", "quoi", "montant", "avis", "confirmer_grille")
CHAMPS_REVUE = ("nom", "alerte", "decision", "texte")
#: En-tête attendu d'un avis d'opéré collé dans la page (séparateur « ; » ou « , »).
EN_TETE_AVIS = "date;symbole;sens;titres;prix;courtage;taxe;commissions;autres_frais;total"
#: Cahier §8.1, « à écrire tel quel sur la page Validation » (sources des chiffres ramenées à leur statut).
CE_QUE_LE_SUIVI_PEUT_MONTRER = (
    "Le suivi ne peut pas prouver la référence par ses gains avant plusieurs années. Dans son test, l'écart de suivi "
    "de la règle de référence face au marché était de 4,31 % par an [Fait publié]. Neuf fois sur dix, le hasard seul "
    "déplace donc son retard cumulé de moins de 5 points à 6 mois, 7 points à 12 mois et 12 points à 36 mois "
    "(1,645 × 4,31 % × √durée en années) ; le retard attendu est de 1,7 à 2,6 points par an, plus 1,6 point la "
    "première année [Estimation sous hypothèse normale].",
    "Le suivi vérifie la plomberie : frais, exécution, argent qui dort, données.",
    "Aucun essai ne sera prouvé par ses gains en un an. Le plus petit avantage visible après un an est de 1,6 à 3,3 "
    "points par an pour un seul essai [Estimation : 1,645 × écart de suivi, seuil unilatéral de 5 %, hypothèse "
    "normale, avec un écart de suivi de l'essai face au témoin supposé de 1 % à 2 % par an].",
    "On ne classe jamais des essais par leur rendement. Avec trois essais sans avantage réel, la chance qu'au moins un "
    "dépasse la référence par hasard est d'au plus 87,5 % ; avec cinq, d'au plus 96,9 % (bornes hautes, essais "
    "supposés indépendants ; environ 72 % et 80 % s'ils sont corrélés à 0,6) [Estimation].",
)
#: Prix de chaque décision de la revue (cahier §F11), affiché avant la réponse.
PRIX_DES_DECISIONS = (
    ("Garder", "0 FCFA de frais ; on reste exposé."),
    ("Ne plus acheter", "0 FCFA ; la ligne s'écarte de son poids."),
    ("Réduire ou vendre", "frais de sortie, perte réalisée sur le prix de revient et dividende attendu abandonné ; si "
                          "l'on rachète plus tard : un aller-retour (3,33 % du montant à 10 000 000 FCFA) [estimé]."),
)
QUESTIONS_REVUE = (
    "La baisse vient-elle du marché ou du titre ?",
    "Une note, un filtre de risque ou une publication l'explique-t-il ?",
    "Le dividende attendu est-il menacé ?",
    "Votre besoin d'argent ou votre durée ont-ils changé ?",
    "Décision : garder ; ne plus acheter ; réduire par ordres à cours limité sur plusieurs séances.",
)


# ---------------------------------------------------------------------------
# Petits outils
# ---------------------------------------------------------------------------


def _rg() -> Any:
    from brvm_alpha.rendement import reglages

    return reglages


def _cr() -> Any:
    from brvm_alpha import cli_rendement

    return cli_rendement


def _ok(b: Any) -> bool:
    return isinstance(b, Mapping) and not b.get("erreur")


def fcfa(x: Any, signe: bool = False) -> str:
    """Montant au franc, à la française (espace fine des milliers)."""
    return _rg().fcfa(x, signe=signe)


def date_fr(x: Any) -> str:
    try:
        return pd.Timestamp(x).strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return str(x or "—")


def _jour(services: Any) -> pd.Timestamp:
    """Date du jour (UTC, sans heure) à l'horloge de l'interface."""
    try:
        t = pd.Timestamp(services.clock())
    except Exception:  # noqa: BLE001 - une doublure sans horloge : l'heure de la machine
        t = pd.Timestamp.now(tz="UTC")
    if t.tzinfo is not None:
        t = t.tz_convert("UTC").tz_localize(None)
    return t.normalize()


def _taux_txt(x: Any) -> str:
    """Taux (part) écrit en pourcentage pour un champ de formulaire : 0,008 → « 0,8 »."""
    try:
        v = float(x) * 100.0
    except (TypeError, ValueError):
        return ""
    return f"{v:.4f}".rstrip("0").rstrip(".").replace(".", ",")


def _montant_txt(x: Any) -> str:
    try:
        return f"{float(x):.0f}"
    except (TypeError, ValueError):
        return ""


def _perte_txt(x: Any) -> str:
    if x is None or x == "":
        return ""
    if isinstance(x, str):
        return x.replace(".", ",").replace("%", " %")
    return _montant_txt(x)


def _first(form: Mapping[str, list[str]], name: str) -> str:
    v = form.get(name)
    return v[0] if v else ""


def _valeurs(form: Mapping[str, list[str]], noms: Sequence[str], n: int = 500) -> dict[str, str]:
    return {k: _first(form, k).strip()[:n] for k in noms}


def _select(name: str, options: Sequence[tuple[str, str]], selected: Any = "", id_: str | None = None) -> Safe:
    return P._select(name, options, selected, id_)


def _champ(id_: str, nom: str, libelle: str, valeur: Any, *, hint: Any = None, mode: str = "text",
           classe: str = "", exemple: Any = None) -> Safe:
    """Champ de formulaire : étiquette, saisie, aide (texte échappé) ; ``exemple`` : texte grisé d'un champ vide."""
    im = {"decimal": ' inputmode="decimal"', "numeric": ' inputmode="numeric"'}.get(mode, "")
    typ = "number" if mode == "number" else "text"
    h = f'<div class="hint">{esc(hint) if not isinstance(hint, Safe) else hint}</div>' if hint else ""
    c = f' class="{esc(classe)}"' if classe else ""
    ex = f' placeholder="{esc(exemple)}"' if exemple not in (None, "") else ""
    return Safe(f'<div{c}><label for="{esc(id_)}">{esc(libelle)}</label><input type="{typ}" id="{esc(id_)}" '
                f'name="{esc(nom)}"{im} value="{esc(valeur)}"{ex}>{h}</div>')


def _case(id_: str, nom: str, libelle: str, coche: bool, hint: Any = None, classe: str = "") -> Safe:
    h = f'<div class="hint">{esc(hint)}</div>' if hint else ""
    c = f' class="{esc(classe)}"' if classe else ""
    return Safe(f'<div{c}><input type="checkbox" id="{esc(id_)}" name="{esc(nom)}" value="oui"'
                + (" checked" if coche else "") + f'> <label class="inline" for="{esc(id_)}">{esc(libelle)}</label>'
                + h + "</div>")


def _pre(texte: str) -> Safe:
    return Safe(f'<pre class="bulletin">{esc(texte)}</pre>')


# ---------------------------------------------------------------------------
# Dossiers (lecture seule)
# ---------------------------------------------------------------------------


def dossier_donnees(services: Any) -> Path:
    """Dossier de données de l'interface (voir le module)."""
    d = getattr(services, "data_dir", None)
    if d:
        return Path(d)
    n = getattr(services, "notes_root", None)
    if n:
        return Path(n).parent
    return paths.DATA_DIR


def dossier_profil(services: Any) -> Path:
    return dossier_donnees(services) / "profil"


def dossier_suivi(services: Any) -> Path:
    return dossier_donnees(services) / "suivi"


def dossier_declaration() -> Path:
    """``reports/suivi_S2`` du dépôt (déclaration signée, suivie par git) : lu, jamais écrit par l'interface."""
    return paths.REPO_ROOT / "reports" / "suivi_S2"


def _registre() -> Path | None:
    r = paths.REPO_ROOT / "reports" / "trials.parquet"
    return r if r.exists() else None


def lire_cache(profil: Path) -> tuple[dict[str, Any] | None, str | None]:
    """``plan_cache.json`` : (contenu, ``None``) ; (``None``, ``None``) s'il n'existe pas ; (``None``, motif) s'il est
    illisible (aucun montant n'est alors affiché)."""
    p = Path(profil) / "plan_cache.json"
    if not p.exists():
        return None, None
    try:
        c = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, f"calcul enregistré illisible ({type(exc).__name__})"
    if not isinstance(c, dict) or not isinstance(c.get("rendement_net"), Mapping):
        return None, "calcul enregistré illisible (contenu inattendu)"
    return c, None


def lire_plan(profil: Path) -> tuple[dict[str, Any], str | None]:
    try:
        return _cr().lire_plan(profil), None
    except ValueError as exc:
        return {}, str(exc)


def lire_grille(profil: Path) -> tuple[Any, bool, str | None]:
    """(grille, enregistrée, erreur) ; grille par défaut (tarif supposé) si aucune n'est enregistrée ou si elle est
    illisible (l'erreur est alors rendue, jamais tue)."""
    from brvm_alpha.rendement import grille as G

    enr = (Path(profil) / "grille_sgi.yaml").exists()
    if not enr:
        return G.defaut(), False, None
    try:
        return G.charger(profil), True, None
    except ValueError as exc:
        return G.defaut(), True, str(exc)


def _grille_vue(g: Any, enregistree: bool) -> dict[str, Any]:
    from brvm_alpha.rendement import grille as G

    champs = {}
    for nom, champ, unite in CHAMPS_GRILLE:
        ch = g.champs.get(champ)
        v = g.valeur(champ)
        champs[nom] = {"valeur": _taux_txt(v) if unite == "%" else _montant_txt(v),
                       "statut": ch.statut if ch is not None else G.SUPPOSE}
    return {"nom": g.nom, "statut": G.statut_global(g), "enregistree": enregistree, "champs": champs,
            "investisseur": "morale" if g.investisseur == G.INVESTISSEURS[1] else "physique",
            "pays": g.pays_residence}


def _feux_du_suivi(profil: Path, D: Path, jour: pd.Timestamp) -> tuple[dict[str, Any] | None, str | None]:
    """Feux de la semaine du portefeuille de l'utilisateur (``MOI``, ``PLAN`` à défaut ; §F11), lus dans son journal ;
    ``(None, None)`` sans carnet."""
    for nom in ("MOI", "PLAN"):
        if (D / nom / "carnet.jsonl").is_file():
            b = _cr().bulletin_portefeuille(nom, D, profil=profil, panels=None, jour=jour)
            return {"feux": b.get("feux") or {}}, nom
    return None, None


def nom_du_bulletin(D: Path, demande: str = "") -> str:
    """Portefeuille du bulletin : celui demandé s'il est connu ; sinon ``MOI``, puis ``PLAN``, puis le témoin."""
    if demande in PORTEFEUILLES:
        return demande
    for nom in ("MOI", "PLAN"):
        if (D / nom / "carnet.jsonl").is_file():
            return nom
    return "REF-S2"


def portefeuilles_presents(D: Path) -> list[str]:
    out = ["REF-S2"]
    for nom in PORTEFEUILLES[1:]:
        d = D / nom
        if (d / "carnet.jsonl").is_file() or (d / "semaines.csv").is_file():
            out.append(nom)
    return out


# ---------------------------------------------------------------------------
# Carte « Mon plan » : état (lecture du disque) et rendu (pur)
# ---------------------------------------------------------------------------


def _plan_affiche(cache: Mapping[str, Any], pe: Mapping[str, Any], suivi: Mapping[str, Any] | None,
                  jour: pd.Timestamp) -> dict[str, Any]:
    """Écran « Mon plan » du cache, tel que la commande ``plan`` l'a calculé : seules la phrase de la séance, la ligne
    « une chose » et les feux sont refaits au jour de l'affichage (règle 2 du cahier : dates et temps du verbe calculés
    à l'affichage). Les montants ne sont jamais rebâtis depuis ``rendement_net`` : avec une perte acceptée, ce bloc
    porte la facture de l'ordre du montant en actions, pas celle du capital total que montre l'écran."""
    from brvm_alpha.rendement import plan as PL

    rn = cache["rendement_net"]
    p = cache.get("plan")
    if _ok(p) and isinstance(p.get("lignes"), list):
        return PL.rafraichir_plan(p, rn, dict(pe) or None, suivi, jour.date())
    if (rn.get("contexte") or {}).get("poche"):
        raise ValueError("écran « Mon plan » absent du calcul enregistré : recalculer")
    rg = _rg()
    rn = dict(rn)
    et = rn.get("etude")
    if _ok(et):
        rn["etude"] = {**et, "phrases": [rg.PH_ETUDE, rg.phrase_seance(jour.date())]}
    return PL.construire_plan(rn, dict(pe) or None, suivi, jour.date())


def _choix(cache: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    """Lignes de la table de choix de la décision 2 (montants au franc, estimés)."""
    if not cache:
        return []
    p = (cache.get("rendement_net") or {}).get("perte")
    if not _ok(p):
        return []
    out = []
    for r in p.get("table") or []:
        if not isinstance(r, Mapping):
            continue
        out.append({"perte": r.get("perte_toleree"), "tout": bool(r.get("tout")), "en_actions": r.get("en_actions"),
                    "reserve": r.get("reserve")})
    return out


def etat_carte(services: Any, jobs: Any = None, *, qs: Mapping[str, list[str]] | None = None,
               erreur_plan: Any = None, valeurs_plan: Mapping[str, Any] | None = None, erreur_grille: Any = None,
               valeurs_grille: Mapping[str, Any] | None = None, message: Any = None) -> dict[str, Any]:
    """Tout ce que la carte affiche, lu sur le disque (lecture seule, aucun calcul de l'ordre). Ne lève jamais : une
    erreur est rendue dans la carte."""
    e: dict[str, Any] = {"cache": False, "erreur_cache": None, "plan": None, "choix": [], "erreur_plan": erreur_plan,
                         "valeurs_plan": dict(valeurs_plan or {}), "erreur_grille": erreur_grille,
                         "valeurs_grille": dict(valeurs_grille or {}), "message": message, "job": None, "occupe": False,
                         "comparaison": None, "notes": [], "bulletin": "REF-S2"}
    try:
        _etat_carte(e, services, jobs, qs or {})
    except Exception as exc:  # noqa: BLE001 - la page ne tombe jamais pour la carte
        e["erreur_interne"] = f"{type(exc).__name__} : {exc}"
    return e


def _etat_carte(e: dict[str, Any], services: Any, jobs: Any, qs: Mapping[str, list[str]]) -> None:
    from brvm_alpha.rendement import grille as G

    rg = _rg()
    profil, D = dossier_profil(services), dossier_suivi(services)
    jour = _jour(services)
    e["jour"] = jour.date().isoformat()
    e["phrases"] = [rg.PH_ETUDE, rg.phrase_seance(jour.date())]
    if jobs is not None:
        cur = jobs.current()
        e["occupe"] = bool(cur is not None and cur.status in ("en cours", "en attente"))
        if cur is not None and cur.kind == JOB_PLAN:
            e["job"] = cur.snapshot()
    pe, err_pe = lire_plan(profil)
    if err_pe:
        e["notes"].append(("error", err_pe))
    e["plan_enregistre"] = {k: pe.get(k) for k in ("capital", "perte_toleree", "taux_reserve", "placement",
                                                   "besoin_dans_mois", "questions_envoyees", "risque")}
    g, enr, err_g = lire_grille(profil)
    if err_g:
        e["notes"].append(("error", err_g + " : la carte emploie le tarif supposé."))
    e["grille"] = _grille_vue(g, enr)
    e["bulletin"] = nom_du_bulletin(D)
    cache, err_c = lire_cache(profil)
    e["erreur_cache"] = err_c
    try:
        last = services.last_session()
    except Exception:  # noqa: BLE001
        last = None
    e["dernier_bulletin"] = pd.Timestamp(last).date().isoformat() if last is not None else None
    e["capital"] = float(pe.get("capital") or (cache or {}).get("capital") or _cr().CAPITAL_DEFAUT)
    if cache is None:
        return
    e["cache"] = True
    e["asof"] = str(cache.get("asof") or "")[:10]
    e["calcule"] = str(cache.get("calcule_utc") or "")[:10]
    e["capital_cache"] = float(cache.get("capital") or 0)
    e["perime"] = bool(e["dernier_bulletin"] and e["asof"] and e["asof"] < e["dernier_bulletin"])
    try:
        calc = pd.Timestamp(cache.get("calcule_utc"))
        calc = calc.tz_convert("UTC") if calc.tzinfo is not None else calc.tz_localize("UTC")
        for nom, quoi in (("grille_sgi.yaml", "votre grille"), ("plan.json", "vos choix")):
            p = profil / nom
            if p.exists() and pd.Timestamp(p.stat().st_mtime, unit="s", tz="UTC") > calc:
                e["notes"].append(("warn", f"{quoi[0].upper() + quoi[1:]} a changé depuis ce calcul : recalculer pour "
                                           "l'employer dans toute la carte."))
    except (TypeError, ValueError):
        pass
    if abs(e["capital_cache"] - e["capital"]) >= 0.5:
        e["notes"].append(("warn", f"Ce calcul porte sur {fcfa(e['capital_cache'])} ; votre plan enregistré, sur "
                                   f"{fcfa(e['capital'])} : recalculer."))
    suivi, nom_feux = None, None
    try:
        suivi, nom_feux = _feux_du_suivi(profil, D, jour)
    except Exception:  # noqa: BLE001 - feux « — » si le journal ne se lit pas
        suivi = None
    e["feux_de"] = nom_feux
    e["plan"] = _plan_affiche(cache, pe, suivi, jour)
    e["choix"] = _choix(cache)
    if _first(qs, "grille") and isinstance(cache.get("ordre"), Mapping):
        grilles = {"central": G.defaut()}
        if enr and not err_g:
            grilles["ma_sgi"] = g
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            rows = G.comparer(cache["ordre"], grilles, reference=G.defaut())
        e["comparaison"] = [{k: x.get(k) for k in ("nom", "statut", "frais_achat", "frais_annuels", "premiere_annee",
                                                   "ecart_premiere_annee", "ecart_annuel", "sens_ecart", "mention")}
                            for x in rows]
        e["capital_ordre"] = float(cache.get("capital_ordre") or e["capital_cache"])


def _form_recalculer(ctx: Any, occupe: bool, libelle: str = "Recalculer mon plan") -> Safe:
    return Safe('<form method="post" action="/plan/enregistrer" class="grid">' + csrf_field(ctx.token)
                + '<input type="hidden" name="recalculer" value="oui">'
                + f'<div><button type="submit" class="secondary"{" disabled" if occupe else ""}>{esc(libelle)}</button>'
                  '<div class="hint">Calcul de l\'écran dans le fil de travail (une opération à la fois, environ 20 s).'
                  "</div></div></form>")


def _tableau_comparaison(e: Mapping[str, Any]) -> Safe:
    rg = _rg()
    rows = []
    for x in e.get("comparaison") or []:
        ec = int(x.get("ecart_premiere_annee") or 0)
        sens = "égal" if ec == 0 else ("frais évités par rapport au tarif supposé" if ec < 0 else "surcoût")
        rows.append([x.get("nom") or "", x.get("statut") or "", fcfa(x.get("frais_achat")), fcfa(x.get("frais_annuels")),
                     fcfa(x.get("premiere_annee")), f"{fcfa(ec, signe=True)} ({sens})", x.get("mention") or ""])
    corps = join([
        Safe(f"<p>Frais recalculés sur les lignes de l'ordre de {esc(fcfa(e.get('capital_ordre')))} du calcul "
             "enregistré, sans relancer l'ordre :</p>"),
        table(["Grille", "Statut", "Frais d'achat", "Frais annuels", "1re année", "Écart (1re année)", "Mention"], rows),
        Safe(f'<p class="hint">{esc(rg.PH_FRAIS)} {esc(rg.PH_ECONOMIE)}</p>')])
    return box("info", corps, "Ce que prend mon courtier :")


def _form_grille(ctx: Any, e: Mapping[str, Any]) -> Safe:
    gv = e.get("grille") or {}
    saisie = e.get("valeurs_grille") or {}

    def actuelle(nom: str) -> str:
        return str(((gv.get("champs") or {}).get(nom) or {}).get("valeur") or "")

    def statut(nom: str) -> str:
        return str(((gv.get("champs") or {}).get(nom) or {}).get("statut") or "supposé")

    def champ(n: str) -> str:
        # Champ vide (la valeur actuelle en exemple grisé) : seul un champ rempli reçoit le statut et la source choisis.
        a = actuelle(n)
        return str(_champ(f"g-{n}", n, LIBELLES_GRILLE[n], saisie.get(n, ""), mode="decimal", exemple=a,
                          hint=f"actuel : {a or '—'} ({statut(n)})"))

    principaux = "".join(champ(n) for n, _c, _u in CHAMPS_GRILLE[:5])
    autres = "".join(champ(n) for n, _c, _u in CHAMPS_GRILLE[5:])
    inv = saisie.get("investisseur", gv.get("investisseur") or "physique")
    autres += (f'<div><label for="g-investisseur">Investisseur</label>'
               f'{_select("investisseur", (("physique", "personne physique résidente"), ("morale", "personne morale")), inv, "g-investisseur")}'
               "</div>")
    autres += str(_champ("g-pays", "pays", "Pays de résidence", saisie.get("pays", gv.get("pays") or "")))
    err = box("error", e["erreur_grille"], "Saisie refusée :") if e.get("erreur_grille") else Safe("")
    ouvert = " open" if (e.get("erreur_grille") or saisie) else ""
    return Safe(
        f'<details class="decision"{ouvert}><summary>1. Ce que prend mon courtier (SGI) — {esc(gv.get("nom") or "")} '
        f'(statut : {esc(gv.get("statut") or "supposé")})</summary>'
        '<form method="post" action="/plan/grille" class="grid" autocomplete="off">' + csrf_field(ctx.token) + err
        + '<div class="wide"><p class="hint">Les cinq chiffres de la grille écrite de votre courtier. Taux en pourcentage '
          "(« 0,8 » pour 0,8 %), montants en FCFA. Un champ vide garde sa valeur et son statut ; seuls les "
          "champs remplis reçoivent le statut et la source ci-dessous.</p></div>"
        + principaux
        + '<div class="wide"><details><summary>Plus de champs</summary>' + autres + "</details></div>"
        + str(_champ("g-source", "source", "Source (grille écrite, avis d'opéré)", saisie.get("source", ""),
                     hint="obligatoire pour le statut « grille écrite » ou « avis d'opéré »"))
        + f'<div><label for="g-statut">Statut des valeurs saisies</label>'
          f'{_select("statut", STATUTS_GRILLE, saisie.get("statut", "supposé"), "g-statut")}</div>'
        + '<div class="wide"><button type="submit">Enregistrer ma grille</button> '
        + str(link("/plan/questions", "Voir les 8 questions", "btn secondary"))
        + '<div class="hint">Les frais sont recalculés sur les lignes du calcul enregistré, en moins d\'une seconde ; '
          "rien n'est acheté.</div></div></form></details>")


def _form_plan(ctx: Any, e: Mapping[str, Any]) -> Safe:
    rg = _rg()
    pe = e.get("plan_enregistre") or {}
    v = e.get("valeurs_plan") or {}
    K = float(e.get("capital") or _cr().CAPITAL_DEFAUT)
    perte_pe = pe.get("perte_toleree")
    coche = v.get("perte") if "perte" in v else (
        "tout" if pe.get("risque") == "tout" else ("" if perte_pe is None else _perte_txt(perte_pe)))
    radios = []
    vus = set()
    for i, r in enumerate(e.get("choix") or []):
        if r["tout"]:
            val = "tout"
            lib = (f"tout : tout en actions ({fcfa(r['en_actions'])} ; en réserve {fcfa(r['reserve'])} ; capital total "
                   f"{fcfa(K)}) [estimé]")
        else:
            val = _montant_txt(r["perte"])
            lib = (f"je risque {fcfa(r['perte'])} : en actions {fcfa(r['en_actions'])} ; en réserve "
                   f"{fcfa(r['reserve'])} ; capital total {fcfa(K)} [estimé]")
        vus.add(val)
        radios.append(f'<label class="inline"><input type="radio" id="pl-perte-{i}" name="perte" value="{esc(val)}"'
                      + (" checked" if str(coche) == val else "") + f"> {esc(lib)}</label><br>")
    libre = str(v.get("perte_libre", "")) or ("" if str(coche) in vus or coche in ("", "tout", "libre") else str(coche))
    radios.append('<label class="inline"><input type="radio" id="pl-perte-libre" name="perte" value="libre"'
                  + (" checked" if libre else "") + "> autre montant (FCFA, ou « 10 % » du capital) :</label>"
                  f'<input type="text" id="pl-perte-montant" name="perte_libre" aria-label="Autre montant" '
                  f'inputmode="numeric" value="{esc(libre)}"><br>')
    radios.append('<label class="inline"><input type="radio" id="pl-perte-aucun" name="perte" value=""'
                  + (" checked" if not libre and str(coche) in ("", "None") else "") + "> pas encore choisi</label>")
    err = box("error", e["erreur_plan"], "Saisie refusée :") if e.get("erreur_plan") else Safe("")
    ouvert = " open" if (e.get("erreur_plan") or v or not e.get("cache")) else ""
    taux = v.get("taux", _taux_txt(pe.get("taux_reserve")) if pe.get("taux_reserve") is not None else "")
    besoin = v.get("besoin", "" if pe.get("besoin_dans_mois") is None else str(pe.get("besoin_dans_mois")))
    envoyees = (v.get("questions_envoyees") == "oui") if "questions_envoyees" in v else bool(pe.get("questions_envoyees"))
    tableau = ("" if e.get("choix") else
               '<p class="hint">La table de choix à quatre lignes s\'affiche une fois le plan calculé.</p>')
    return Safe(
        f'<details class="decision"{ouvert}><summary>2 et 3. Ce que j\'accepte de risquer ; où dort le reste</summary>'
        '<form method="post" action="/plan/enregistrer" class="grid" autocomplete="off">' + csrf_field(ctx.token) + err
        + '<div class="wide"><fieldset><legend>Ce que j\'accepte de risquer sur 12 mois</legend>' + tableau
        + "".join(radios)
        + f'<div class="hint">{esc(rg.PH_RISQUE)}</div></fieldset></div>'
        + str(_champ("pl-capital", "capital", "Capital total (FCFA)", v.get("capital", P.fr_num(K, 0)),
                     hint="exemples : 10 000 000, 10M", mode="numeric"))
        + str(_champ("pl-taux", "taux", "Taux net de ma réserve (% par an)", taux,
                     hint="vide : inconnu, compté à 0 %. " + rg.PH_RESERVE, mode="decimal"))
        + str(_champ("pl-placement", "placement", "Où dort le reste (compte, placement)",
                     v.get("placement", pe.get("placement") or ""), hint="texte libre, gardé dans votre plan"))
        + str(_champ("pl-besoin", "besoin", "Besoin de cet argent dans (mois, facultatif)", besoin, mode="numeric",
                     hint="la durée n'est pas encore calculée : votre réponse est gardée dans le plan"))
        + str(_case("pl-questions", "questions_envoyees", "J'ai envoyé les 8 questions à mon courtier", envoyees,
                    classe="wide"))
        + f'<div class="wide"><button type="submit"{" disabled" if e.get("occupe") else ""}>Enregistrer et recalculer'
          '</button><div class="hint">Enregistré dans votre profil, puis calcul de l\'écran dans le fil de travail. '
          "Rien n'est acheté.</div></div></form></details>")


def carte_mon_plan(ctx: Any, e: Mapping[str, Any]) -> Safe:
    """Carte « Mon plan » du Tableau de bord (forme écran : montants arrondis, aucune lecture flatteuse)."""
    from brvm_alpha.rendement import plan as PL

    rg = _rg()
    parts: list[Any] = [Safe('<section class="card" id="mon-plan"><h2>Mon plan</h2>')]
    if e.get("message"):
        kind, msg = e["message"] if isinstance(e["message"], tuple) else ("ok", e["message"])
        parts.append(box(kind, msg))
    if e.get("erreur_interne"):
        parts.append(box("error", f"carte « Mon plan » non calculée ({e['erreur_interne']})."))
    for kind, msg in e.get("notes") or []:
        parts.append(box(kind, msg))
    if e.get("job"):
        parts.append(P.job_panel(e["job"], result_link=link("/#mon-plan", "Afficher mon plan"), done_anchor="mon-plan"))
    if e.get("comparaison"):
        parts.append(_tableau_comparaison(e))
    plan = e.get("plan")
    if e.get("cache") and plan:
        when = f"Calculé le {date_fr(e.get('calcule'))} sur le bulletin du {date_fr(e.get('asof'))}."
        if e.get("perime"):
            parts.append(box("warn", join([
                Safe(f"<p>Ce plan est calculé sur le bulletin du {esc(date_fr(e.get('asof')))} ; le dernier bulletin est "
                     f"celui du {esc(date_fr(e.get('dernier_bulletin')))}. Les montants ci-dessous datent du "
                     f"{esc(date_fr(e.get('asof')))}.</p>"), _form_recalculer(ctx, bool(e.get("occupe")))]),
                "Calcul à refaire :"))
        else:
            parts.append(Safe(f'<p class="muted">{esc(when)}</p>'))
        parts.append(Safe(PL.rendre_plan(plan, "fragment")))
        if not e.get("feux_de"):
            parts.append(Safe('<p class="hint">Feux : le suivi sur papier de votre portefeuille n\'a pas commencé '
                              "(page Portefeuille).</p>"))
    else:
        parts.append(Safe(f'<p class="banner">{esc(BANNER)}</p>'))
        parts.append(Safe("<p>" + " ".join(esc(p) for p in (e.get("phrases") or [rg.PH_ETUDE])) + "</p>"))
        motif = e.get("erreur_cache") or "aucun calcul enregistré"
        parts.append(box("info", join([
            Safe(f"<p>Mon plan n'est pas encore calculé ({esc(motif)}). Le calcul reprend l'ordre du capital total "
                 "et le décompose en trois décisions ; il ne passe aucun ordre.</p>"),
            _form_recalculer(ctx, bool(e.get("occupe")), "Calculer mon plan")])))
    if e.get("cache") and plan and not e.get("perime"):
        parts.append(_form_recalculer(ctx, bool(e.get("occupe"))))
    parts.append(Safe("<p>" + " · ".join(str(x) for x in (
        link("/plan/resultat", "Détail au franc"), link("/suivi/bulletin", "Bulletin de la semaine"),
        link("/plan/questions", "Les 8 questions à votre courtier"))) + "</p>"))
    parts.append(Safe("<h3>Mes trois décisions</h3>"))
    parts.append(_form_grille(ctx, e))
    parts.append(_form_plan(ctx, e))
    parts.append(Safe("</section>"))
    return join(parts)


def carte_ou_erreur(ctx: Any, e: Mapping[str, Any]) -> Safe:
    """Carte, ou encadré d'erreur si son rendu échoue : le Tableau de bord ne tombe jamais pour elle."""
    try:
        return carte_mon_plan(ctx, e)
    except Exception as exc:  # noqa: BLE001
        return Safe('<section class="card" id="mon-plan"><h2>Mon plan</h2>'
                    + box("error", f"carte « Mon plan » non affichée ({type(exc).__name__} : {exc}).") + "</section>")


# ---------------------------------------------------------------------------
# Actions du Tableau de bord : grille, plan, calcul de l'écran
# ---------------------------------------------------------------------------


def _taux_saisi(texte: str, quoi: str) -> float:
    try:
        return _cr().parse_taux(texte)
    except ValueError as exc:
        raise ValueError(f"{quoi} : {exc}") from None


def _taux_reserve_saisi(texte: str) -> float:
    """Taux net de la réserve saisi dans l'interface : même contrôle que ``--taux-reserve`` (de 0 à 15 %)."""
    try:
        return _cr().parse_taux_reserve(texte)
    except ValueError as exc:
        msg = str(exc)
        raise ValueError(msg if msg.startswith("taux de la réserve") else f"taux net de la réserve : {msg}") from None


def grille_depuis_formulaire(v: Mapping[str, str], avant: Any, jour: str) -> Any:
    """Grille enregistrée après la saisie : seuls les champs remplis reçoivent la valeur, le statut et la source
    choisis (comme ``plan grille --courtage … --statut …``) ; un champ vide garde sa valeur et son statut. Le
    formulaire ne préremplit aucun champ : la valeur actuelle y est un exemple grisé."""
    import copy

    from brvm_alpha.rendement import grille as G

    statut = v.get("statut") or G.SUPPOSE
    if statut not in G.STATUTS:
        raise ValueError(f"statut inconnu : {statut[:20]!r} (supposé, grille écrite ou avis d'opéré)")
    source = str(v.get("source") or "").strip()[:200]
    g = copy.deepcopy(avant)
    for nom, champ, unite in CHAMPS_GRILLE:
        brut = str(v.get(nom) or "").strip()
        if not brut:
            continue
        lib = LIBELLES_GRILLE[nom]
        if unite == "%":
            x = _taux_saisi(brut, lib)
        else:
            try:
                x = _cr().parse_montant(brut)
            except ValueError as exc:
                raise ValueError(f"{lib} : {exc}") from None
        g = g.avec(**{champ: x})
        g.champs[champ].statut = statut
        g.champs[champ].source = source
        g.champs[champ].date = jour
    inv = v.get("investisseur") or ""
    if inv:
        if inv not in ("physique", "morale"):
            raise ValueError("investisseur : personne physique ou morale")
        g.investisseur = G.INVESTISSEURS[0] if inv == "physique" else G.INVESTISSEURS[1]
    if "pays" in v:
        g.pays_residence = str(v.get("pays") or "").strip()[:60]
    if g.nom.startswith("Tarif supposé"):
        g.nom = "Ma grille"
    c = G.controler(g)
    if c["erreurs"]:
        raise ValueError(" ; ".join(c["erreurs"]) + " (rien n'est enregistré)")
    return g


def plan_depuis_formulaire(v: Mapping[str, str], avant: Mapping[str, Any], maintenant: Any) -> dict[str, Any]:
    """Plan enregistré (``plan.json``) d'après le formulaire des décisions 2 et 3 (mêmes clés que ``plan
    --enregistrer``)."""
    from brvm_alpha import cli

    CR = _cr()
    pe = dict(avant)
    try:
        pe["capital"] = float(cli.parse_capital(v.get("capital") or pe.get("capital") or CR.CAPITAL_DEFAUT))
    except ValueError as exc:
        raise ValueError(f"capital : {exc}") from None
    choix = str(v.get("perte") or "")
    libre = str(v.get("perte_libre") or "").strip()
    pe.pop("risque", None)
    if choix == "libre" or (choix == "" and libre):
        if not libre:
            raise ValueError("ce que j'accepte de risquer : saisir un montant (FCFA) ou une part (« 10 % »)")
        try:
            pe["perte_toleree"] = CR.parse_perte(libre)
        except ValueError as exc:
            raise ValueError(f"ce que j'accepte de risquer : {exc}") from None
    elif choix == "tout":
        pe["perte_toleree"] = None
        pe["risque"] = "tout"
    elif choix == "":
        pe["perte_toleree"] = None
    else:
        try:
            pe["perte_toleree"] = CR.parse_perte(choix)
        except ValueError as exc:
            raise ValueError(f"ce que j'accepte de risquer : {exc}") from None
    if isinstance(pe.get("perte_toleree"), float) and pe["perte_toleree"] > pe["capital"]:
        raise ValueError("ce que j'accepte de risquer : plus que le capital total (choisir « tout » pour tout en actions)")
    t = pd.Timestamp(maintenant)
    taux = str(v.get("taux") or "").strip()
    if taux:
        pe.update({"taux_reserve": _taux_reserve_saisi(taux), "statut_taux": "supposé",
                   "date_taux": t.date().isoformat()})
    else:
        for k in ("taux_reserve", "statut_taux", "date_taux"):
            pe.pop(k, None)
    pe["placement"] = str(v.get("placement") or "").strip()[:120]
    besoin = str(v.get("besoin") or "").strip()
    if besoin:
        try:
            pe["besoin_dans_mois"] = int(CR._mois(besoin))
        except ValueError as exc:
            raise ValueError(f"besoin de cet argent : {exc}") from None
    else:
        pe.pop("besoin_dans_mois", None)
    pe["questions_envoyees"] = v.get("questions_envoyees") == "oui"
    pe.update({"version": 1, "enregistre_utc": t.isoformat(), "bandeau": BANNER})
    return pe


def calculer_plan(services: Any, profil: Path, log: Any) -> dict[str, Any]:
    """Calcul de l'écran « Mon plan » (fil de travail) : ``recommend`` du capital du plan enregistré, avec la grille du
    profil, ce que j'accepte de risquer et le taux de la réserve, puis écriture de ``plan_cache.json``. Même calcul que
    ``python -m brvm_alpha plan`` ; rien n'est acheté."""
    from brvm_alpha import cli
    from brvm_alpha.portfolio import recommend as rec
    from brvm_alpha.rendement import grille as G

    CR = _cr()
    t = services.last_session()
    if t is None:
        raise ValueError("panel introuvable : " + cli.PANEL_HINT)
    if cli.in_s1(t):
        raise ValueError(cli.s1_refusal(t, "l'écran « Mon plan »"))
    pe = CR.lire_plan(profil)
    capital = float(pe.get("capital") or CR.CAPITAL_DEFAUT)
    g: Any = "central"
    nom_g = "central"
    if pe.get("grille") != "central" and (Path(profil) / "grille_sgi.yaml").exists():
        g, nom_g = G.charger(profil), "ma_sgi"
    kw: dict[str, Any] = {"grille": g, "plan_enregistre": pe or None}
    if pe.get("perte_toleree") is not None:
        kw["perte_toleree"] = pe["perte_toleree"]
    if pe.get("taux_reserve") is not None:
        kw["taux_reserve"] = pe["taux_reserve"]
    known = services.notes_instant(t)
    log(f"écran « Mon plan » au {cli.fr_date(t)} pour {cli.fr_num(capital, 0)} FCFA (tarif : {nom_g})…")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        o = rec.recommend(t, capital, notes_store=services.notes_store() if services.notes_root else None,
                          panel_dir=services.panel_dir, validation_dir=services.validation_dir, notes_known_at=known,
                          index_evaluation=False, today=services.clock(), **kw)
    rn = getattr(o, "rendement_net", None) or {}
    if not _ok(rn) or not _ok(rn.get("plan")):
        raise RuntimeError("écran « Mon plan » non calculé (module « Rendement net et pertes » en échec)")
    cache = CR.cache_du_plan(o, t=t, capital=capital, grille=nom_g, perte_toleree=pe.get("perte_toleree"),
                             maintenant=services.clock())
    chemin = CR.ecrire_json(Path(profil) / "plan_cache.json", cache)
    log(f"écrit {chemin.name} (bulletin du {cli.fr_date(t)})")
    return {"asof": str(t.date()), "capital": capital}


def lancer_calcul(h: Any) -> Any:
    """Lance le calcul de l'écran dans le fil de travail (``JobBusy`` si une opération est en cours)."""
    s = h.server.services
    profil = dossier_profil(s)
    return h.server.jobs.start(JOB_PLAN, "calcul de l'écran « Mon plan »",
                               lambda job: calculer_plan(s, profil, job.log))


def _dashboard(h: Any, status: int, **carte: Any) -> None:
    from brvm_alpha.ui import server as S

    S._render_dashboard(h, status, {}, **carte)


def post_plan_grille(h: Any, form: Mapping[str, list[str]]) -> None:
    from brvm_alpha.rendement import grille as G

    v = _valeurs(form, [n for n, _c, _u in CHAMPS_GRILLE] + ["source", "statut", "investisseur", "pays"], 200)
    profil = dossier_profil(h.server.services)
    jour = _jour(h.server.services).date().isoformat()
    try:
        avant, _enr, err = lire_grille(profil)
        if err:
            raise ValueError(err)
        grille_depuis_formulaire(v, avant, jour)  # saisie contrôlée d'abord : un refus ne crée rien
        paths.verifier_ecriture(profil / "grille_sgi.yaml")
        with _cr().verrou_profil(profil, quoi="saisie de la grille (grille_sgi.yaml)"):  # lecture, fusion, écriture
            avant, _enr, err = lire_grille(profil)
            if err:
                raise ValueError(err)
            g = grille_depuis_formulaire(v, avant, jour)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                G.enregistrer(g, profil)
    except (ValueError, ErreurMoteur, OSError) as exc:
        _dashboard(h, 400, erreur_grille=str(exc), valeurs_grille=v)
        return
    h._redirect("/?grille=1#mon-plan")


def post_plan_enregistrer(h: Any, form: Mapping[str, list[str]]) -> None:
    from brvm_alpha.ui.server import JobBusy

    s = h.server.services
    v = _valeurs(form, CHAMPS_PLAN, 200)
    profil = dossier_profil(s)
    message = None
    if v.get("recalculer") != "oui":
        v.pop("recalculer", None)
        try:
            avant, err = lire_plan(profil)
            if err:
                raise ValueError(err)
            plan_depuis_formulaire(v, avant, s.clock())  # saisie contrôlée d'abord : un refus ne crée rien
            with _cr().verrou_profil(profil, quoi="enregistrement du plan (plan.json)"):  # lecture, fusion, écriture
                avant, err = lire_plan(profil)
                if err:
                    raise ValueError(err)
                pe = plan_depuis_formulaire(v, avant, s.clock())
                _cr().ecrire_json(profil / "plan.json", pe)
        except (ValueError, ErreurMoteur, OSError) as exc:
            _dashboard(h, 400, erreur_plan=str(exc), valeurs_plan=v)
            return
        message = ("ok", "Vos choix sont enregistrés dans votre profil.")
    try:
        lancer_calcul(h)
    except JobBusy as exc:
        _dashboard(h, 409, erreur_plan=f"calcul non lancé : {exc}", message=message)
        return
    h._redirect("/?plan=1#mon-plan")


def stale_plan_form(h: Any, form: Mapping[str, list[str]]) -> None:
    """Jeton périmé sur un formulaire de la carte : rien n'est enregistré ; la saisie revient (403)."""
    from brvm_alpha.ui.server import STALE_TOKEN_MSG

    if "courtage" in form or "statut" in form:
        _dashboard(h, 403, erreur_grille=STALE_TOKEN_MSG,
                   valeurs_grille=_valeurs(form, [n for n, _c, _u in CHAMPS_GRILLE] + ["source", "statut",
                                                                                         "investisseur", "pays"], 200))
    else:
        _dashboard(h, 403, erreur_plan=STALE_TOKEN_MSG, valeurs_plan={k: x for k, x in _valeurs(form, CHAMPS_PLAN, 200)
                                                                      .items() if k != "recalculer"})


# ---------------------------------------------------------------------------
# Pages atteintes par des liens : questions, détail du plan, bulletin
# ---------------------------------------------------------------------------


def page_questions(ctx: Any, questions: Sequence[str]) -> str:
    items = "".join(f"<li>{esc(str(q).split('. ', 1)[-1])}</li>" for q in questions)
    texte = "Les 8 questions à mon courtier (SGI) :\n" + "\n".join(questions)
    body = join([
        Safe('<section class="card"><h2>À envoyer à votre courtier (SGI)</h2>'
             '<p>Demandez une réponse écrite : elle permet de remplacer le tarif supposé par des faits.</p>'),
        Safe(f"<ol>{items}</ol>"),
        Safe('<label for="q-texte">Texte à copier</label>'
             f'<textarea id="q-texte" readonly>{esc(texte)}</textarea>'),
        Safe(f'<p>{link("/#mon-plan", "Saisir les réponses dans « Ce que prend mon courtier »")}</p></section>')])
    return P.layout(ctx, "Les 8 questions à votre courtier", body, active="accueil")


def etat_resultat(services: Any) -> dict[str, Any]:
    profil = dossier_profil(services)
    cache, err = lire_cache(profil)
    e: dict[str, Any] = {"cache": cache is not None, "erreur_cache": err}
    if cache is None:
        return e
    from brvm_alpha.rendement import plan as PL

    pe, _err = lire_plan(profil)
    jour = _jour(services)
    plan = _plan_affiche(cache, pe, None, jour)
    e.update({"asof": str(cache.get("asof") or "")[:10], "calcule": str(cache.get("calcule_utc") or "")[:10],
              "md": PL.rendre_plan(plan, "md"), "texte": PL.rendre_plan(plan, "texte"),
              "json": cache.get("rendement_net")})
    return e


def page_resultat(ctx: Any, e: Mapping[str, Any]) -> str:
    if not e.get("cache"):
        body = join([Safe('<section class="card">'),
                     box("info", f"Mon plan n'est pas encore calculé ({e.get('erreur_cache') or 'aucun calcul enregistré'}).",
                         "Mon plan :"),
                     Safe(f'<p>{link("/#mon-plan", "Calculer mon plan depuis le Tableau de bord")}</p></section>')])
        return P.layout(ctx, "Mon plan — détail au franc", body, active="accueil")
    body = join([
        Safe(f'<section class="card"><p class="muted">Calculé le {esc(date_fr(e.get("calcule")))} sur le bulletin du '
             f'{esc(date_fr(e.get("asof")))}. Forme « détail » : montants au franc.</p>'),
        P.md_to_html(str(e.get("md") or "")),
        Safe(f'<p>Exports : {link("/plan/resultat?format=texte", "écran (texte)")} · '
             f'{link("/plan/resultat?format=json", "JSON")} · {link("/#mon-plan", "Retour à la carte")}</p></section>')])
    return P.layout(ctx, "Mon plan — détail au franc", body, active="accueil")


def get_plan_questions(h: Any, qs: Mapping[str, list[str]]) -> None:
    from brvm_alpha.rendement import grille as G

    q = G.questions()
    h._page(200, lambda ctx: page_questions(ctx, q))


def get_plan_resultat(h: Any, qs: Mapping[str, list[str]]) -> None:
    from brvm_alpha.ui.server import HTTPError

    e = etat_resultat(h.server.services)
    fmt = _first(qs, "format").strip()
    if fmt and not e.get("cache"):
        raise HTTPError(404, "Mon plan introuvable", "aucun calcul de l'écran « Mon plan » n'est enregistré")
    if fmt == "json":
        h._send(200, json.dumps({"bandeau": BANNER, "asof": e.get("asof"), "rendement_net": e.get("json")},
                                ensure_ascii=False, indent=1), "application/json; charset=utf-8")
    elif fmt == "texte":
        h._send(200, str(e.get("texte") or ""), "text/plain; charset=utf-8")
    elif fmt:
        raise HTTPError(400, "Format inconnu", "format texte ou json")
    else:
        h._page(200, lambda ctx: page_resultat(ctx, e))


def etat_bulletin(services: Any, demande: str = "", *, avec_panels: bool = True) -> dict[str, Any]:
    """Bulletin de la semaine d'un portefeuille (lecture seule) ; ne lève jamais."""
    D = dossier_suivi(services)
    nom = nom_du_bulletin(D, demande)
    e: dict[str, Any] = {"nom": nom, "presents": portefeuilles_presents(D), "texte": None, "erreur": None, "b": None}
    try:
        panels = None
        if avec_panels:
            try:
                panels = services.strategy_panels()
            except Exception:  # noqa: BLE001 - sans panel : bulletin sans les prochains rendez-vous
                panels = None
        b = _cr().bulletin_portefeuille(nom, D, profil=dossier_profil(services), panels=panels, jour=_jour(services))
        from brvm_alpha.suivi import bulletin as BU

        e["b"] = b
        e["texte"] = BU.rendre(b, "texte")
    except Exception as exc:  # noqa: BLE001
        e["erreur"] = str(exc)
    return e


def _liens_portefeuilles(e: Mapping[str, Any]) -> Safe:
    out = []
    for nom in e.get("presents") or ["REF-S2"]:
        lib = LIBELLES.get(nom, nom)
        out.append(Safe(f"<strong>{esc(lib)}</strong>") if nom == e.get("nom")
                   else link(f"/suivi/bulletin?nom={P.q(nom)}", lib))
    return join(out, " · ")


def page_bulletin(ctx: Any, e: Mapping[str, Any]) -> str:
    corps: list[Any] = [Safe('<section class="card">'),
                        Safe(f"<p>Portefeuilles suivis : {_liens_portefeuilles(e)}</p>")]
    if e.get("erreur"):
        corps.append(box("error", f"bulletin non calculé ({e['erreur']})."))
    if e.get("texte"):
        corps.append(_pre(str(e["texte"])))
        corps.append(Safe(f'<p>Exports : {link("/suivi/bulletin?nom=" + P.q(e.get("nom")) + "&format=texte", "texte")} · '
                          f'{link("/suivi/bulletin?nom=" + P.q(e.get("nom")) + "&format=json", "JSON")}</p>'))
    corps.append(Safe(f'<p>{link("/portefeuille#suivi", "Revue guidée et saisies (page Portefeuille)")}</p></section>'))
    return P.layout(ctx, f"Bulletin de la semaine — {LIBELLES.get(str(e.get('nom')), e.get('nom'))}", join(corps),
                    active="portefeuille")


def get_suivi_bulletin(h: Any, qs: Mapping[str, list[str]]) -> None:
    from brvm_alpha.ui.server import HTTPError

    demande = _first(qs, "nom").strip().upper()
    if demande and demande not in PORTEFEUILLES:
        raise HTTPError(400, "Portefeuille inconnu", "portefeuille attendu : " + ", ".join(PORTEFEUILLES))
    e = etat_bulletin(h.server.services, demande)
    fmt = _first(qs, "format").strip()
    if fmt in ("texte", "json"):
        if e.get("b") is None:
            raise HTTPError(400, "Bulletin non calculé", str(e.get("erreur") or "bulletin non calculé"))
        from brvm_alpha.suivi import bulletin as BU

        if fmt == "json":
            h._send(200, BU.rendre(e["b"], "json"), "application/json; charset=utf-8")
        else:
            texte = str(e["texte"])
            h._send(200, texte if BANNER in texte else texte + BANNER + "\n", "text/plain; charset=utf-8")
        return
    if fmt:
        raise HTTPError(400, "Format inconnu", "format texte ou json")
    h._page(200, lambda ctx: page_bulletin(ctx, e))


# ---------------------------------------------------------------------------
# Page Portefeuille : champs de l'ordre, bulletin, revue, saisie
# ---------------------------------------------------------------------------


def etat_portefeuille(services: Any, *, valeurs: Mapping[str, Any] | None = None, message: Any = None,
                      erreur_revue: Any = None, valeurs_revue: Mapping[str, Any] | None = None,
                      erreur_saisie: Any = None, valeurs_saisie: Mapping[str, Any] | None = None,
                      resultat_saisie: Any = None) -> dict[str, Any]:
    """État des ajouts de la page Portefeuille ; ne lève jamais."""
    e: dict[str, Any] = {"message": message, "erreur_revue": erreur_revue, "valeurs_revue": dict(valeurs_revue or {}),
                         "erreur_saisie": erreur_saisie, "valeurs_saisie": dict(valeurs_saisie or {}),
                         "resultat_saisie": resultat_saisie, "grille_enregistree": False, "bulletin": {}}
    try:
        profil = dossier_profil(services)
        e["grille_enregistree"] = (profil / "grille_sgi.yaml").exists()
        D = dossier_suivi(services)
        e["carnets"] = [n for n in CARNETS if (D / n / "carnet.jsonl").is_file()]
        e["bulletin"] = etat_bulletin(services)
    except Exception as exc:  # noqa: BLE001
        e["bulletin"] = {"erreur": str(exc), "nom": "REF-S2"}
    return e


def champs_portefeuille(values: Mapping[str, Any], e: Mapping[str, Any] | None = None) -> Safe:
    """Champs du module dans le formulaire de l'ordre de bataille : vides ou non cochés par défaut (ordre inchangé)."""
    rg = _rg()
    v = {k: ("" if values.get(k) is None else str(values.get(k))) for k in CHAMPS_PORTEFEUILLE}
    tarifs = (("", "tarif supposé (central)"), ("ma_sgi", "ma grille enregistrée"))
    enr = bool((e or {}).get("grille_enregistree"))
    return Safe(
        '<div class="wide"><strong>Rendement net et pertes</strong> <span class="hint">options éteintes par défaut : '
        "sans saisie, l'ordre est celui d'aujourd'hui ; chaque option porte sa mention dans l'ordre.</span></div>"
        + str(_champ("p-perte", "perte", "Ce que j'accepte de risquer sur 12 mois (FCFA)", v["perte"], mode="numeric",
                     hint="vide : aucun choix. Exemples : 1 000 000, 1M, 10 %. " + rg.PH_RISQUE))
        + str(_champ("p-taux", "taux", "Taux net de ma réserve (% par an)", v["taux"], mode="decimal",
                     hint="vide : inconnu, compté à 0 %. Jamais déduit de la perte estimée."))
        + f'<div><label for="p-tarif">Tarif</label>{_select("tarif", tarifs, v["tarif"], "p-tarif")}'
        + ('<div class="hint">grille saisie sur la carte « Mon plan »</div>' if enr else
           '<div class="hint">aucune grille enregistrée : saisir la vôtre sur la carte « Mon plan »</div>') + "</div>"
        + str(_case("p-arrondi", "arrondi", "Arrondi « plus forts restes »", v["arrondi"] == "oui",
                    hint="écart d'exécution (E-A) : demande votre grille écrite"))
        + str(_case("p-apport", "apport", "J'apporte de l'argent frais", v["apport"] == "oui",
                    hint="écart d'exécution (E-B) : achats sans vente ; demande le champ « Liquidités »"))
        + str(_champ("p-apport-montant", "apport_montant", "Montant apporté (FCFA, facultatif)", v["apport_montant"],
                     mode="numeric", hint="vide : les liquidités saisies"))
        + str(_case("p-completer", "completer", "Compléter un ordre servi en partie", v["completer"] == "oui",
                    hint="écart d'exécution (E-B)"))
        + f'<div class="wide hint">{esc(rg.PH_PLACE)}</div>')


def options_portefeuille(v: Mapping[str, str], services: Any, cash: float | None) -> dict[str, Any]:
    """Paramètres nommés de ``recommend`` d'après les champs du module ; ``{}`` s'ils sont vides (appel inchangé).
    ``ValueError`` pour une saisie refusée (rien n'est lancé)."""
    from brvm_alpha import cli
    from brvm_alpha.rendement import grille as G

    CR = _cr()
    kw: dict[str, Any] = {}
    if str(v.get("perte") or "").strip():
        try:
            kw["perte_toleree"] = CR.parse_perte(v["perte"])
        except ValueError as exc:
            raise ValueError(f"ce que j'accepte de risquer : {exc}") from None
    if str(v.get("taux") or "").strip():
        kw["taux_reserve"] = _taux_reserve_saisi(v["taux"])
    tarif = str(v.get("tarif") or "").strip()
    g = None
    if tarif == "ma_sgi":
        profil = dossier_profil(services)
        g, enr, err = lire_grille(profil)
        if not enr:
            raise ValueError("tarif « ma grille » : aucune grille enregistrée (la saisir sur la carte « Mon plan »)")
        if err:
            raise ValueError(err)
        kw["grille"] = g
    elif tarif not in ("", "central"):
        raise ValueError("tarif : supposé ou ma grille")
    if v.get("arrondi") == "oui":
        if g is None or G.statut_global(g) == G.SUPPOSE:
            raise ValueError("arrondi « plus forts restes » refusé : il demande la grille écrite de votre courtier "
                             "(statut « grille écrite » ou « avis d'opéré », tarif « ma grille »)")
        kw["arrondi"] = "restes"
    if v.get("apport") == "oui":
        if cash is None:
            raise ValueError("apport : liquidités réelles nécessaires (champ « Liquidités », qui comprend l'apport)")
        brut = str(v.get("apport_montant") or "").strip()
        try:
            montant = float(cli.parse_capital(brut)) if brut else float(cash)
        except ValueError as exc:
            raise ValueError(f"montant apporté : {exc}") from None
        if montant <= 0:
            raise ValueError("apport : un montant positif est attendu")
        if float(cash) + 1.0 < montant:
            raise ValueError("apport supérieur aux liquidités : le champ « Liquidités » doit comprendre l'apport")
        kw["apport"] = montant
    elif str(v.get("apport_montant") or "").strip():
        raise ValueError("montant apporté : cocher « J'apporte de l'argent frais »")
    if v.get("completer") == "oui":
        kw["completer"] = True
    return kw


def _form_revue(ctx: Any, e: Mapping[str, Any]) -> Safe:
    rg = _rg()
    v = e.get("valeurs_revue") or {}
    noms = [(n, f"{LIBELLES.get(n, n)} ({n})") for n in CARNETS]
    err = box("error", e["erreur_revue"], "Saisie refusée :") if e.get("erreur_revue") else Safe("")
    prix = table(["Décision", "Coût"], [[a, b] for a, b in PRIX_DES_DECISIONS])
    ouvert = " open" if (e.get("erreur_revue") or v) else ""
    return Safe(
        f'<details id="revue"{ouvert}><summary>Revue guidée : un feu ouvre une revue, jamais une vente</summary>'
        + "<ol>" + "".join(f"<li>{esc(q)}</li>" for q in QUESTIONS_REVUE) + "</ol>"
        + "<p>Le prix de chaque décision, avant de répondre :</p>" + prix
        + f'<p class="hint">{esc(rg.PH_REVUE)}</p>'
        + '<form method="post" action="/suivi/revue" class="grid" autocomplete="off">' + csrf_field(ctx.token) + err
        + f'<div><label for="r-nom">Portefeuille</label>{_select("nom", noms, v.get("nom", "MOI"), "r-nom")}</div>'
        + str(_champ("r-alerte", "alerte", "Alerte (identifiant ou ligne)", v.get("alerte", ""),
                     hint="par exemple « perte » ou le symbole de la ligne à revoir"))
        + f'<div><label for="r-decision">Décision</label>{_select("decision", DECISIONS, v.get("decision", "garder"), "r-decision")}</div>'
        + f'<div class="wide"><label for="r-texte">Vos réponses aux cinq questions</label>'
          f'<textarea id="r-texte" name="texte">{esc(v.get("texte", ""))}</textarea></div>'
        + '<div class="wide"><button type="submit">Consigner la revue au carnet</button>'
          '<div class="hint">Aucun ordre n\'est créé.</div></div></form></details>')


def _form_saisie(ctx: Any, e: Mapping[str, Any]) -> Safe:
    v = e.get("valeurs_saisie") or {}
    noms = [(n, f"{LIBELLES.get(n, n)} ({n})") for n in CARNETS]
    quoi = v.get("quoi", "apport")
    radios = "".join(
        f'<label class="inline"><input type="radio" id="s-quoi-{k}" name="quoi" value="{k}"'
        + (" checked" if quoi == k else "") + f"> {esc(lib)}</label><br>"
        for k, lib in (("apport", "un apport d'argent"), ("retrait", "un retrait d'argent"),
                       ("avis", "un avis d'opéré (portefeuille réel seulement)")))
    err = box("error", e["erreur_saisie"], "Saisie refusée :") if e.get("erreur_saisie") else Safe("")
    res = e.get("resultat_saisie")
    ok = box("ok", res, "Consigné :") if res else Safe("")
    ouvert = " open" if (e.get("erreur_saisie") or v or res) else ""
    return Safe(
        f'<details id="saisie"{ouvert}><summary>Saisir un apport, un retrait ou un avis d\'opéré</summary>'
        + '<form method="post" action="/suivi/saisir" class="grid" autocomplete="off">' + csrf_field(ctx.token) + err + ok
        + f'<div><label for="s-nom">Portefeuille</label>{_select("nom", noms, v.get("nom", "MOI"), "s-nom")}</div>'
        + f'<div><fieldset><legend>Je saisis</legend>{radios}</fieldset></div>'
        + str(_champ("s-montant", "montant", "Montant de l'apport ou du retrait (FCFA)", v.get("montant", ""),
                     mode="numeric"))
        + f'<div class="wide"><label for="s-avis">Avis d\'opéré (une ligne par exécution)</label>'
          f'<textarea id="s-avis" name="avis" placeholder="{esc(EN_TETE_AVIS)}">{esc(v.get("avis", ""))}</textarea>'
          f'<div class="hint">Première ligne : {esc(EN_TETE_AVIS)} (séparateur « ; » ou « , », virgule décimale '
          "acceptée). Les frais lus sont comparés à votre grille, à 1 FCFA près par ligne.</div></div>"
        + str(_case("s-confirmer", "confirmer_grille", "Enregistrer la grille corrigée proposée, si l'avis ne concorde pas",
                    v.get("confirmer_grille") == "oui", classe="wide"))
        + '<div class="wide"><button type="submit">Consigner au carnet</button>'
          '<div class="hint">Ajout seul : une saisie en double est refusée. Démarrer un portefeuille : '
          "« python -m brvm_alpha suivi demarrer --nom MOI ».</div></div></form></details>")


def section_suivi(ctx: Any, e: Mapping[str, Any]) -> Safe:
    """Section « Suivi sur papier » de la page Portefeuille : bulletin de la semaine, revue, saisie."""
    b = e.get("bulletin") or {}
    nom = str(b.get("nom") or "REF-S2")
    parts: list[Any] = [Safe('<section class="card" id="suivi"><h2>Suivi sur papier</h2>')]
    if e.get("message"):
        kind, msg = e["message"] if isinstance(e["message"], tuple) else ("ok", e["message"])
        parts.append(box(kind, msg))
    parts.append(Safe(f"<h3>Bulletin de la semaine : {esc(LIBELLES.get(nom, nom))}</h3>"))
    if b.get("erreur"):
        parts.append(box("error", f"bulletin non calculé ({b['erreur']})."))
    if b.get("texte"):
        parts.append(_pre(str(b["texte"])))
    parts.append(Safe(f'<p>{link("/suivi/bulletin", "Bulletin complet et autres portefeuilles")}</p>'))
    if not e.get("carnets"):
        parts.append(Safe('<p class="hint">Aucun carnet sur papier pour l\'instant : la revue et les saisies demandent '
                          "un portefeuille démarré (« suivi demarrer »).</p>"))
    parts.append(_form_revue(ctx, e))
    parts.append(_form_saisie(ctx, e))
    parts.append(Safe("</section>"))
    return join(parts)


def section_ou_erreur(ctx: Any, e: Mapping[str, Any]) -> Safe:
    try:
        return section_suivi(ctx, e)
    except Exception as exc:  # noqa: BLE001
        return Safe('<section class="card" id="suivi"><h2>Suivi sur papier</h2>'
                    + box("error", f"section non affichée ({type(exc).__name__} : {exc}).") + "</section>")


def _portefeuille(h: Any, status: int, **suivi: Any) -> None:
    from brvm_alpha.ui import server as S

    S._render_portfolio(h, status, suivi=suivi)


def _carnet(services: Any, nom: str) -> Any:
    from brvm_alpha.suivi import carnet as cn

    if nom not in CARNETS:
        raise ValueError("portefeuille : " + ", ".join(CARNETS) + " (le témoin et l'essai « avec notes » sont tenus "
                                                                   "par le moteur, sans carnet)")
    D = dossier_suivi(services)
    c = cn.ouvrir(nom, D, creer=False)
    if not c.fichier.exists():
        raise ValueError(f"portefeuille « {nom} » non démarré : python -m brvm_alpha suivi demarrer --nom {nom}")
    paths.verifier_ecriture(c.fichier)
    return c


def post_suivi_revue(h: Any, form: Mapping[str, list[str]]) -> None:
    s = h.server.services
    v = _valeurs(form, CHAMPS_REVUE, 4000)
    v["nom"] = v["nom"].upper()
    jour = _jour(s).date().isoformat()
    try:
        if not v["alerte"]:
            raise ValueError("alerte : préciser l'alerte ou la ligne revue")
        if v["decision"] not in {k for k, _l in DECISIONS}:
            raise ValueError("décision : garder, ne plus acheter ou réduire")
        c = _carnet(s, v["nom"])
        c.ajouter({"type": "revue", "date": jour, "alerte": v["alerte"][:200], "decision": v["decision"],
                   "texte": v["texte"]})
    except (ValueError, ErreurMoteur, OSError) as exc:  # journal tenu par une autre écriture : 409, pas une saisie fausse
        _portefeuille(h, 409 if isinstance(exc, VerrouOccupe) else 400, erreur_revue=str(exc), valeurs_revue=v)
        return
    _portefeuille(h, 200, message=("ok", f"Revue consignée au carnet « {v['nom']} » le {date_fr(jour)} : décision "
                                         f"« {dict(DECISIONS)[v['decision']]} ». Aucun ordre n'est créé. "
                                         + _rg().PH_REVUE))


def post_suivi_saisir(h: Any, form: Mapping[str, list[str]]) -> None:
    from brvm_alpha import cli

    s = h.server.services
    v = _valeurs(form, CHAMPS_SAISIE, 100_000)
    v["nom"] = v["nom"].upper()
    jour = _jour(s).date().isoformat()
    try:
        c = _carnet(s, v["nom"])
        if v["quoi"] in ("apport", "retrait"):
            try:
                montant = float(cli.parse_capital(v["montant"]))
            except ValueError as exc:
                raise ValueError(f"montant : {exc}") from None
            c.ajouter({"type": v["quoi"], "date": jour, "montant": montant})
            res = f"{'Apport' if v['quoi'] == 'apport' else 'Retrait'} de {fcfa(montant)} au carnet « {c.nom} » le " \
                  f"{date_fr(jour)}."
        elif v["quoi"] == "avis":
            if (c.mandat() or {}).get("mode") != "reel":
                raise ValueError("un avis d'opéré ne se saisit que dans un portefeuille réel ; un portefeuille sur papier "
                                 "est exécuté chaque nuit par « suivi maj »")
            lignes = _cr().lire_avis_texte(v["avis"], "avis d'opéré saisi")
            r = _cr().saisir_avis_au_carnet(c, lignes, confirmer_grille=v.get("confirmer_grille") == "oui", jour=jour,
                                            profil=dossier_profil(s))
            res = join([Safe(f"<p>{esc(len(lignes))} exécution(s) consignée(s) au carnet « {esc(c.nom)} ». "
                             f"{esc(r['texte'])}</p>")]
                       + [Safe(f"<p>{esc(x['symbole'])} ({esc(x['date'])}) : écarts en FCFA {esc(x['ecarts_fcfa'])}</p>")
                          for x in r["lignes"] if not x["concorde"]]
                       + ([Safe("<p>Grille enregistrée au statut « avis d'opéré ».</p>")] if r["grille_enregistree"] else [])
                       + ([Safe("<p>Grille corrigée proposée, non enregistrée : cocher la case et renvoyer pour "
                                "l'enregistrer.</p>")] if r.get("grille_proposee") and not r["grille_enregistree"] else []))
        else:
            raise ValueError("je saisis : un apport, un retrait ou un avis d'opéré")
    except (ValueError, ErreurMoteur, OSError) as exc:  # journal tenu par une autre écriture : 409, pas une saisie fausse
        _portefeuille(h, 409 if isinstance(exc, VerrouOccupe) else 400, erreur_saisie=str(exc), valeurs_saisie=v)
        return
    _portefeuille(h, 200, resultat_saisie=res, valeurs_saisie={"nom": v["nom"], "quoi": v["quoi"]})


def stale_suivi_form(h: Any, form: Mapping[str, list[str]]) -> None:
    """Jeton périmé sur la revue ou la saisie : rien n'est consigné ; la saisie revient (403)."""
    from brvm_alpha.ui.server import STALE_TOKEN_MSG

    if "decision" in form or "alerte" in form:
        _portefeuille(h, 403, erreur_revue=STALE_TOKEN_MSG, valeurs_revue=_valeurs(form, CHAMPS_REVUE, 4000))
    else:
        _portefeuille(h, 403, erreur_saisie=STALE_TOKEN_MSG, valeurs_saisie=_valeurs(form, CHAMPS_SAISIE, 100_000))


# ---------------------------------------------------------------------------
# Page Validation : ce qui est déclaré
# ---------------------------------------------------------------------------


def points_d_etape(reglages: Mapping[str, Any] | None = None) -> list[tuple[str, str]]:
    """Points d'étape du suivi (cahier §8.8), dates tirées des réglages et du calendrier de la remise à niveau."""
    from brvm_alpha.suivi import bulletin as BU

    rg = _rg()
    debut = pd.Timestamp(str(rg.lire(reglages, "dates.debut_suivi", "2026-12-01")))
    argent = pd.Timestamp(str(rg.lire(reglages, "dates.premiere_decision_argent_reel", "2027-06-01")))
    affirm = pd.Timestamp(str(rg.lire(reglages, "dates.affirmation_performance", "2029-12-01")))
    un_an = debut + pd.DateOffset(years=1)
    return sorted([
        (debut.date().isoformat(), "début du suivi sur papier"),
        (BU.remise_a_niveau_suivante(debut).date().isoformat(), "remise à niveau du panier de référence : coût mesuré"),
        (argent.date().isoformat(), "comptabilité seulement ; première date possible pour une décision humaine écrite "
                                    "sur l'argent réel"),
        (un_an.date().isoformat(), "première lecture de l'écart de l'essai « avec notes » (52 semaines)"),
        (BU.remise_a_niveau_suivante(un_an).date().isoformat(), "essai « fin de mois » après une saison de dividendes et une "
                                                               "remise à niveau"),
        (affirm.date().isoformat(), "156 semaines : première affirmation possible"),
    ])


def etat_validation(services: Any) -> dict[str, Any]:
    """Déclaration du suivi en vigueur (lecture seule) ; ne lève jamais."""
    from brvm_alpha.suivi import declaration as DE

    jour = _jour(services)
    e: dict[str, Any] = {"jour": jour.date().isoformat(), "erreur": None, "lignes": [], "etat": ""}
    try:
        d = dossier_declaration()
        v = DE.verifier(d, registre=_registre())
        ev = DE.en_vigueur(jour, d)
        e["etat"] = (f"{v['n_lignes']} ligne(s) signée(s), chaîne {'intacte' if v['chaine_ok'] else 'rompue'}"
                     if v["existe"] else str(v.get("mention") or "aucune déclaration signée"))
        e["chaine_ok"] = bool(v["chaine_ok"])
        e["mention"] = ev.get("mention")
        arts = ev.get("articles") or {}
        for a in DE.modele():
            k = str(a["id"])
            en = arts.get(k)
            if k == "REF-S2" and not ev.get("declaration"):
                etat = "suivi : définition du test, sans signature"
            elif isinstance(en, Mapping) and ev.get("declaration"):
                etat = (f"déclaré (réponse : {en.get('reponse') or '—'}), en vigueur à partir du "
                        f"{date_fr(en.get('effet_a_partir_du'))}")
            else:
                etat = f"non déclaré à ce jour (proposé : {a.get('proposition') or '—'})"
            e["lignes"].append({"id": k, "type": str(a.get("type") or ""), "phrase": str(a.get("phrase") or ""),
                                "etat": etat, "mesures": [str(m) for m in (a.get("mesure") or [])]})
    except Exception as exc:  # noqa: BLE001
        e["erreur"] = f"{type(exc).__name__} : {exc}"
    try:
        futurs = [p for p in points_d_etape() if p[0] >= e["jour"]]
        e["prochain"] = futurs[0] if futurs else None
    except Exception:  # noqa: BLE001
        e["prochain"] = None
    return e


ROLES = {"reference": "témoin", "ecart_execution": "écart d'exécution", "essai": "essai sur papier",
         "regle_papier": "vérification comptable"}


def tableau_validation(e: Mapping[str, Any]) -> Safe:
    """Section « Suivi sur papier : ce qui est déclaré » de la page Validation (aucun classement par rendement)."""
    rg = _rg()
    parts: list[Any] = [Safe('<section class="card" id="suivi-declare"><h2>Suivi sur papier : ce qui est déclaré</h2>')]
    if e.get("erreur"):
        parts.append(box("error", f"déclaration non lue ({e['erreur']})."))
    etat = str(e.get("etat") or "—").rstrip(".")
    mention = str(e.get("mention") or "").rstrip(".")
    if mention and mention != etat:
        etat = f"{etat} ; {mention}"
    parts.append(Safe(f"<p>Déclaration (reports/suivi_S2) : {esc(etat)}.</p>"))
    rows = []
    for x in e.get("lignes") or []:
        mes = Safe("<ul>" + "".join(f"<li>{esc(m)}</li>" for m in x["mesures"]) + "</ul>") if x["mesures"] else "—"
        rows.append([x["id"], ROLES.get(x["type"], x["type"]), Safe(f"{esc(x['phrase'])}"), x["etat"], mes])
    parts.append(table(["Code", "Rôle", "Règle", f"État au {date_fr(e.get('jour'))}", "Mesures comptées"], rows,
                       empty="Aucun article."))
    pr = e.get("prochain")
    if pr:
        parts.append(Safe(f"<p><strong>Prochain point d'étape : le {esc(date_fr(pr[0]))}</strong> — {esc(pr[1])}. Entre "
                          "deux points d'étape : aucune décision sur une règle.</p>"))
    parts.append(box("info", Safe("<ul>" + "".join(f"<li>{esc(t)}</li>" for t in CE_QUE_LE_SUIVI_PEUT_MONTRER)
                                  + "</ul>"), "Ce que le suivi peut montrer, et ce qu'il ne peut pas :"))
    parts.append(box("hypothesis", f"{rg.PH_ESSAI} Aucun classement par rendement avant le point d'étape."))
    parts.append(Safe("</section>"))
    return join(parts)


def tableau_ou_erreur(e: Mapping[str, Any]) -> Safe:
    try:
        return tableau_validation(e)
    except Exception as exc:  # noqa: BLE001
        return Safe('<section class="card" id="suivi-declare"><h2>Suivi sur papier : ce qui est déclaré</h2>'
                    + box("error", f"tableau non affiché ({type(exc).__name__} : {exc}).") + "</section>")


__all__ = ["CARNETS", "CHAMPS_PORTEFEUILLE", "JOB_PLAN", "PORTEFEUILLES", "calculer_plan", "carte_mon_plan",
           "carte_ou_erreur", "champs_portefeuille", "dossier_donnees", "etat_bulletin", "etat_carte",
           "etat_portefeuille", "etat_resultat", "etat_validation", "get_plan_questions", "get_plan_resultat",
           "get_suivi_bulletin", "grille_depuis_formulaire", "options_portefeuille", "page_bulletin", "page_questions",
           "page_resultat", "plan_depuis_formulaire", "post_plan_enregistrer", "post_plan_grille", "post_suivi_revue",
           "post_suivi_saisir", "section_ou_erreur", "section_suivi", "stale_plan_form", "stale_suivi_form",
           "tableau_ou_erreur", "tableau_validation"]
