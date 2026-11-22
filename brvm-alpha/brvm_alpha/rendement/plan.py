"""F1 — Écran « Mon plan » (cahier ``docs/RENDEMENT_NET.md``, §F1).

Un écran pour un particulier pressé : que faire à la prochaine séance (rien acheter), ce que chaque choix change en
FCFA, quoi regarder chaque semaine. L'écran ne calcule rien : il assemble les blocs de ``rendement_net`` (F2 à F7,
F10-F11).

* :func:`construire_plan` rend ``{"lignes": [...], "une_chose": str, "feux": {...}}`` ; chaque ligne porte son
  texte « écran » (montants arrondis par ``reglages.arrondi_ecran``, règle 10) et son texte « détail » (au franc) ;
* :func:`rendre_plan` écrit la forme ``texte`` (écran : 45 lignes au plus, 100 colonnes au plus), ``md`` (détail) ou
  ``html`` (écran, sans aucune ressource externe).

Ordre des blocs : ``BANNER`` ; ``PH_ETUDE`` ; ``PH_SEANCE`` ; décision 1 (courtier) ; décision 2 (ce que j'accepte de
risquer), suivie de ``PH_PASSE``, ``PH_DESCRIPTIF`` et de la phrase de synthèse de F6 ; décision 3 (réserve, avec
``PH_INTERETS``) ; « si vous ne faites qu'une chose cette semaine » (jamais un achat) ; « ce que vous recevriez et ce
qui partirait » ; ``PH_COURS`` ; les trois feux. La lecture flatteuse (passé rejoué) n'apparaît que dans le détail,
toujours suivie de ``PH_FLATTE``.
"""

from __future__ import annotations

import datetime as _dt
import html as _html
import math
import re
import textwrap
from typing import Any, Mapping, Sequence

from brvm_alpha.rendement import reglages as _rg
from brvm_alpha.rendement.reglages import ESTIMATION, FAIT, HYPOTHESE, arrondi_ecran, fcfa

__all__ = ["UNE_CHOSE", "construire_plan", "rendre_plan"]

LARGEUR = 100
UNE_CHOSE = {
    "questions": "envoyez les 8 questions à votre courtier.",
    "risque": "choisissez ce que vous acceptez de risquer sur 12 mois (table de la décision 2).",
    "taux": "saisissez le taux net de votre réserve (question 7 au courtier).",
    "bulletin": "lisez le bulletin de la semaine.",
}
_MOTS = {FAIT: "compté", ESTIMATION: "estimé", HYPOTHESE: "supposé"}


def _ok(b: Any) -> bool:
    return isinstance(b, Mapping) and not b.get("erreur")


def _ecr(x: Any, **kw: Any) -> str:
    return arrondi_ecran(x, **kw) if x is not None else "non calculé"


def _env(x: Any, **kw: Any) -> str:
    t = _ecr(x, **kw)
    return t if t in ("non calculé",) or t.startswith("entre") else "environ " + t


def _sans_signe(x: Any) -> str:
    """Valeur arrondie de l'écran, écrite sans signe (après « de frais », « de moins »…)."""
    if x is None:
        return "non calculé"
    return _ecr(x).lstrip("+−")


def _L(lignes: list, bloc: str, texte: str, detail: str | None = None, *, montant: Any = None, ecran: str | None = None,
       statut: str | None = None, type_: str = "texte", cellules: Sequence[str] | None = None,
       cellules_detail: Sequence[str] | None = None) -> None:
    lignes.append({"bloc": bloc, "type": type_, "texte": texte, "texte_detail": detail if detail is not None else texte,
                   "montant": montant, "montant_ecran": ecran, "statut": statut,
                   "cellules": list(cellules) if cellules is not None else None,
                   "cellules_detail": list(cellules_detail) if cellules_detail is not None else None})


def _paragraphe(lignes: list, bloc: str, texte: str, detail: str | None = None, *, retrait: str = "",
                largeur: int = LARGEUR, **kw: Any) -> None:
    _L(lignes, bloc, texte, detail, type_="paragraphe", **kw)
    lignes[-1]["retrait"] = retrait
    lignes[-1]["largeur"] = largeur


def _titre(lignes: list, bloc: str, gauche: str, droite: str = "") -> None:
    if droite:
        pad = max(1, LARGEUR - 4 - len(gauche) - len(droite))
        txt = f"{gauche}{' ' * pad}[ {droite} ]"
    else:
        txt = gauche
    _L(lignes, bloc, txt, type_="titre")
    lignes[-1]["titre"] = gauche
    lignes[-1]["etiquette"] = droite


def _blanc(lignes: list, bloc: str) -> None:
    _L(lignes, bloc, "", type_="blanc")


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def _une_chose(rn: Mapping[str, Any], plan_enregistre: Mapping[str, Any] | None) -> tuple[str, str]:
    pe = plan_enregistre or {}
    gr = rn.get("grille") if _ok(rn.get("grille")) else {}
    if str(gr.get("statut_global") or "supposé") == "supposé" and not pe.get("questions_envoyees"):
        return "questions", UNE_CHOSE["questions"]
    if pe.get("perte_toleree") is None and not (_ok(rn.get("perte")) and rn["perte"].get("choix")):
        return "risque", UNE_CHOSE["risque"]
    if pe.get("taux_reserve") is None and not (_ok(rn.get("reserve")) and rn["reserve"].get("taux_connu")):
        return "taux", UNE_CHOSE["taux"]
    return "bulletin", UNE_CHOSE["bulletin"]


def _bloc_courtier(L: list, rn: Mapping[str, Any]) -> None:
    b = rn.get("bilan")
    gr = rn.get("grille") if _ok(rn.get("grille")) else {}
    st = str(gr.get("statut_global") or "supposé")
    etiq = "tarif supposé, non vérifié" if st == "supposé" else f"tarif : {st}"
    _titre(L, "courtier", "1. CE QUE PREND MON COURTIER (SGI)", etiq)
    if not _ok(b):
        _L(L, "courtier", "   Frais de la 1re année : non calculé.", statut=None)
        return
    t = b["totaux"]
    mot = _rg.mot_statut(HYPOTHESE if st == "supposé" else FAIT)
    f1, an = int(t["frais_an1"]), int(t["annuels"])
    _paragraphe(L, "courtier",
                f"Si vous achetiez tout : {_env(-f1, suffixe='de frais')} la 1re année, puis {_sans_signe(-an)} par an.",
                f"Si vous achetiez tout : {fcfa(f1)} de frais la 1re année, puis {fcfa(an)} par an.",
                retrait="   ", montant=f1, ecran=_ecr(-f1, suffixe="de frais"), statut=mot)
    tenue = next((x for x in b["lignes"] if x["code"] == "A2"), None)
    part = t.get("part_supposee_frais")
    pct_txt = f"{int(math.floor(100 * part + 0.5))} %" if part is not None else "non calculé"
    if tenue and tenue["montant"] > 0:
        _paragraphe(L, "courtier",
                    f"Dont {_sans_signe(-tenue['montant'])} FCFA par an de tenue de compte [{tenue['mot_statut']}]. "
                    f"{pct_txt} de ces frais : supposés ou estimés.",
                    f"Dont {fcfa(tenue['montant'])} par an de tenue de compte [{tenue['mot_statut']}]. "
                    f"{_rg.pct(part)} de ces frais ({fcfa(t['supposee_frais_fcfa'])}) sont supposés ou estimés.",
                    retrait="   ", montant=tenue["montant"], ecran=_sans_signe(-tenue["montant"]), statut=tenue["mot_statut"])
    else:
        _paragraphe(L, "courtier", f"{pct_txt} de ces frais : supposés ou estimés.",
                    f"{_rg.pct(part)} de ces frais ({fcfa(t['supposee_frais_fcfa'])}) sont supposés ou estimés.",
                    retrait="   ", montant=t["supposee_frais_fcfa"], ecran=pct_txt, statut="estimé")
    lv = rn.get("leviers")
    ens = None
    if _ok(lv):
        ens = next((x for x in lv.get("frais_evites") or [] if str(x.get("geste", "")).startswith("Ensemble")), None)
    if st == "supposé":
        if ens and ens.get("premiere_annee") is not None and ens["premiere_annee"] > 0:
            _paragraphe(L, "courtier",
                        f"-> Envoyez les 8 questions à votre courtier. Avec la seule grille connue sans frais par ligne : "
                        f"environ {_sans_signe(ens['premiere_annee'])} FCFA de moins la 1re année, puis {_sans_signe(ens['par_an'])} de moins "
                        f"par an [supposé]. 0 si votre courtier ne facture pas ce poste.",
                        f"-> Envoyez les 8 questions à votre courtier. Avec la seule grille connue sans frais par ligne : "
                        f"{fcfa(ens['premiere_annee'])} de moins la 1re année, puis {fcfa(ens['par_an'])} de moins par an "
                        f"[supposé]. {_rg.PH_ECONOMIE}",
                        retrait="   ", montant=ens["premiere_annee"], ecran=_ecr(ens["premiere_annee"]), statut="supposé")
        else:
            _paragraphe(L, "courtier", "-> Envoyez les 8 questions à votre courtier.", retrait="   ")
    if gr.get("non_employee"):
        _paragraphe(L, "courtier", gr["non_employee"], retrait="   ")


def _cellules_ligne(r: Mapping[str, Any], *, detail: bool) -> tuple[list[str], str]:
    f = (lambda x: fcfa(x, unite=False)) if detail else (lambda x: _ecr(x).lstrip("+"))
    fs = (lambda x: fcfa(x, unite=False, signe=True)) if detail else _ecr
    if r.get("tout"):
        risque = "tout"
    else:
        risque = f(r["perte_toleree"])
    bas, haut = (r.get("annee_2018") or [None, None])[:2]
    annee = f"{fs(-bas) if bas is not None else 'non calculé'} à {fs(-haut)}" if haut is not None else "non calculé"
    ordi = (r.get("annee_ordinaire") or {}).get("prudente")
    o_txt = fs(ordi) if ordi is not None else "non calculé"
    if r.get("mention") == "frais > dividendes":
        o_txt += " ; frais > dividendes"
    cells = [risque, f(r["en_actions"]), f(r["reserve"]), annee, o_txt]
    pm, lg = r.get("pire_moment_2018"), r.get("baisse_2017_2020")
    dep = r.get("depasse") or {}
    sous = (f"pire moment de 2018 : {fs(-pm) if pm is not None else 'non calculé'} ; si 2017-2020 revenait : "
            f"{fs(-lg) if lg is not None else 'non calculé'}")
    if dep.get("pire_moment") and dep.get("2017_2020"):
        sous += " (les deux dépassent)"
    elif dep.get("pire_moment") or dep.get("2017_2020"):
        sous += " (dépasse)"
    return cells, sous


def _bloc_risque(L: list, rn: Mapping[str, Any]) -> None:
    p = rn.get("perte")
    rq = rn.get("risque") if _ok(rn.get("risque")) else {}
    synth = (rq.get("synthese") or {}).get("phrase") if isinstance(rq, Mapping) else None
    choix = p.get("choix") if _ok(p) else None
    _titre(L, "risque", "2. CE QUE J'ACCEPTE DE RISQUER SUR 12 MOIS",
           "montants estimés" if choix else "à choisir ; montants estimés")
    if not _ok(p):
        _L(L, "risque", "   Table de choix : non calculé.")
        return
    if choix and choix.get("en_actions", 0) > 0:
        X = choix["perte_toleree"]
        bas, haut = choix["annee_2018"]
        _paragraphe(L, "risque", f"Vous acceptez de risquer {fcfa(X)} sur 12 mois. Ce n'est pas une limite.",
                    retrait="   ", montant=X, ecran=fcfa(X), statut="compté")
        _paragraphe(L, "risque", f"En actions : {fcfa(choix['en_actions'])}. En réserve : {fcfa(choix['reserve'])}.",
                    retrait="   ", montant=choix["en_actions"], ecran=fcfa(choix["en_actions"]), statut="compté")
        dep_pm = (choix.get("depasse") or {}).get("pire_moment")
        dep_lg = (choix.get("depasse") or {}).get("2017_2020")
        _paragraphe(L, "risque",
                    f"Une année comme 2018 : {_env(-bas) if bas is not None else 'non calculé'} à {_ecr(-haut)} FCFA, frais "
                    f"compris [estimé]. Au pire moment de l'année : {_env(-choix['pire_moment_2018'])} FCFA."
                    + (" Cela dépasse ce que vous acceptez." if dep_pm else ""),
                    f"Une année comme 2018 : {fcfa(-bas, signe=True) if bas is not None else 'non calculé'} à "
                    f"{fcfa(-haut, signe=True)}, frais compris [estimé]. Au pire moment de l'année : "
                    f"{fcfa(-choix['pire_moment_2018'], signe=True)}." + (" Cela dépasse ce que vous acceptez." if dep_pm else ""),
                    retrait="   ", montant=-haut, ecran=_ecr(-haut), statut="estimé")
        _paragraphe(L, "risque",
                    f"Si la baisse de 2017-2020 revenait : {_env(-choix['baisse_2017_2020'])} FCFA, sur plusieurs années."
                    + (" Cela dépasse ce que vous acceptez." if dep_lg else ""),
                    f"Si la baisse de 2017-2020 revenait : {fcfa(-choix['baisse_2017_2020'], signe=True)}, sur plusieurs "
                    "années." + (" Cela dépasse ce que vous acceptez." if dep_lg else ""),
                    retrait="   ", montant=-choix["baisse_2017_2020"], ecran=_ecr(-choix["baisse_2017_2020"]), statut="estimé")
        ordi = (choix.get("annee_ordinaire") or {}).get("prudente")
        tout = ((choix.get("ordre_tout") or {}).get("annee_ordinaire") or {}).get("prudente")
        if ordi is not None and tout is not None:
            prix = float(tout) - float(ordi)
            moins = _sans_signe(-prix)
            _paragraphe(L, "risque",
                        f"Prix de cette prudence : dans une année ordinaire du passé, lecture prudente, {_env(ordi)} FCFA au "
                        f"lieu de {_ecr(tout)} (environ {moins} FCFA de moins).",
                        f"Prix de cette prudence : dans une année ordinaire du passé, lecture prudente, {fcfa(ordi, signe=True)} "
                        f"au lieu de {fcfa(tout, signe=True)} ({fcfa(prix)} de moins).",
                        retrait="   ", montant=-prix, ecran=_ecr(-prix), statut="estimé")
        r1 = choix.get("reste_an1")
        if r1 is not None and r1 < 0 <= int(choix.get("reste_suivant") or 0):
            _paragraphe(L, "risque", f"Au tarif supposé, la 1re année, les frais dépassent les dividendes attendus "
                                     f"d'environ {_sans_signe(r1)} FCFA. Voir « ce que prend mon courtier ».",
                        f"Au tarif supposé, la 1re année, les frais dépassent les dividendes attendus de {fcfa(-r1)}. "
                        "Voir « ce que prend mon courtier ».",
                        retrait="   ", montant=r1, ecran=_ecr(r1), statut="supposé")
            L[-1]["detail_seul"] = True  # l'écran le montre déjà dans « ce que vous recevriez » (45 lignes au plus)
        elif int(choix.get("reste_suivant") or 0) < 0:
            _paragraphe(L, "risque", f"Au tarif supposé, les frais annuels dépassent les dividendes attendus d'environ "
                                     f"{_sans_signe(choix['reste_suivant'])} FCFA par an.",
                        retrait="   ", montant=choix["reste_suivant"], ecran=_ecr(choix["reste_suivant"]), statut="supposé")
        _paragraphe(L, "risque", "Un tarif plus bas permet plus d'actions pour le même risque accepté : la somme exposée au "
                                 "marché augmente aussi. Ce que vous acceptez de risquer ne se recharge pas chaque année. "
                                 "Après une perte, relisez ce choix.", retrait="   ")
        if choix.get("message"):
            _paragraphe(L, "risque", choix["message"], retrait="   ")
        fixes = [_rg.PH_PASSE, _rg.PH_DESCRIPTIF] + ([synth] if synth else []) + [_rg.PH_RISQUE]
        _paragraphe(L, "risque", " ".join(fixes), retrait="   ")
        return
    if choix and choix.get("message"):
        _paragraphe(L, "risque", choix["message"], retrait="   ")
    entete = ["Je risque", "En actions", "En réserve", "Année comme 2018", "Année ordinaire (prudente)"]
    _L(L, "risque", "", type_="entete_table", cellules=entete, cellules_detail=entete + ["Année ordinaire (flatteuse)"])
    for r in p.get("table") or []:
        if not r.get("en_actions") and not r.get("tout"):
            _L(L, "risque", "", type_="ligne_table",
               cellules=[_ecr(r["perte_toleree"]).lstrip("+"), "0", _ecr(r["reserve"]).lstrip("+"), "—", "—"],
               cellules_detail=[fcfa(r["perte_toleree"], unite=False), "0", fcfa(r["reserve"], unite=False), "—", "—", "—"],
               montant=0, ecran="0", statut="estimé")
            _L(L, "risque", "      " + str(r.get("message") or ""), type_="sous_ligne")
            continue
        cells, sous = _cellules_ligne(r, detail=False)
        cd, sous_d = _cellules_ligne(r, detail=True)
        fl = (r.get("annee_ordinaire") or {}).get("flatteuse")
        cd = cd + [fcfa(fl, unite=False, signe=True) if fl is not None else "non calculé"]
        _L(L, "risque", "", type_="ligne_table", cellules=cells, cellules_detail=cd, montant=r["en_actions"],
           ecran=cells[1], statut="estimé")
        rap = r.get("rapport_2017_2020_sur_2018")
        rap_txt = f" ; rapport 2017-2020 ÷ 2018 : {rap:.2f}".replace(".", ",") if rap is not None else ""
        _L(L, "risque", "      " + sous, sous_d + rap_txt, type_="sous_ligne", montant=-(r.get("pire_moment_2018") or 0),
           ecran=_ecr(-(r.get("pire_moment_2018") or 0)), statut="estimé")
    fixes = ["« tout » : tout en actions. Ce ne sont pas des limites.", _rg.PH_PASSE, _rg.PH_DESCRIPTIF]
    if synth:
        fixes.append(synth)
    _paragraphe(L, "risque", " ".join(fixes), retrait="   ")


def _bloc_reserve(L: list, rn: Mapping[str, Any]) -> None:
    r = rn.get("reserve")
    ctx = rn.get("contexte") or {}
    K = float(ctx.get("capital") or 0)
    connu = _ok(r) and r.get("taux_connu")
    etiq = f"taux saisi : {_rg.pct(r['taux'], 2)} [{r['mot_statut']}]" if connu else "taux inconnu : compté à 0 %"
    _titre(L, "reserve", "3. OÙ DORT LE RESTE, ET À QUEL TAUX", etiq)
    if not _ok(r):
        _L(L, "reserve", "   Réserve : non calculé.")
        return
    pt_K = int(round(0.01 * K))
    if r.get("montant", 0) < K - 0.5:
        txt = (f"Avec {fcfa(K - r['montant'])} en actions, la réserve est de {fcfa(r['montant'])} : chaque point d'intérêt "
               f"vaut {fcfa(r['valeur_d_un_point'])} par an.")
    else:
        txt = f"Pendant l'étude, vos {fcfa(K)} attendent : un point d'intérêt vaut {fcfa(pt_K)} par an."
    _paragraphe(L, "reserve", txt, retrait="   ", montant=r["valeur_d_un_point"], ecran=fcfa(r["valeur_d_un_point"]),
                statut="compté")
    if connu:
        _paragraphe(L, "reserve", f"Intérêts attendus : {_env(r['interets'])} FCFA par an [{r['mot_statut']}], montrés à part. "
                                  + " ".join(r.get("phrases") or [_rg.PH_INTERETS]),
                    f"Intérêts attendus : {fcfa(r['interets'])} par an [{r['mot_statut']}], montrés à part. "
                    + " ".join(r.get("phrases") or [_rg.PH_INTERETS]),
                    retrait="   ", montant=r["interets"], ecran=_ecr(r["interets"]), statut=r["mot_statut"])
    else:
        _paragraphe(L, "reserve", _rg.PH_INTERETS + " -> Question 7.", retrait="   ")


def _bloc_recevoir(L: list, rn: Mapping[str, Any]) -> None:
    b = rn.get("bilan")
    p = rn.get("perte") if _ok(rn.get("perte")) else {}
    ch = p.get("choix") if isinstance(p, Mapping) else None
    gr = rn.get("grille") if _ok(rn.get("grille")) else {}
    sup = str(gr.get("statut_global") or "supposé") == "supposé"
    mf = "supposé" if sup else "compté"
    if ch and ch.get("en_actions", 0) > 0:
        d, e, a = ch["dividendes"], ch["frais_achat"], ch["frais_annuels"]
        I = float(ch["investi"])
        A = float(ch["en_actions"])
        chute = round(float(d) * 0.8)
        r20 = chute - e - a
        aller = e / I if I else 0.0
        bas = 2 * 12 * 0.0087 * A * aller
        haut = 0.0123 * A
        quoi = f"{fcfa(ch['en_actions'], unite=False)} en actions"
    elif _ok(b):
        t = b["totaux"]
        d, e, a = t["dividendes_nets"], t["entree"], t["annuels"]
        r20 = next((x["reste_an1"] for x in b.get("dividendes_en_baisse") or [] if abs(x["chute"] - 0.20) < 1e-9), None)
        bas, haut = b["remise_a_niveau"]["bas"], b["remise_a_niveau"]["haut"]
        quoi = "tout en actions"
    else:
        _titre(L, "recevoir", "CE QUE VOUS RECEVRIEZ ET CE QUI PARTIRAIT (FCFA) : non calculé")
        return
    _titre(L, "recevoir", f"CE QUE VOUS RECEVRIEZ ET CE QUI PARTIRAIT (FCFA) — 1re année, cours inchangés, {quoi}")
    rows = [
        ("Dividendes attendus, impôt déduit", d, "estimé", "estimé : dernier dividende reconduit", ""),
        ("Frais d'achat", -e, "supposé" if sup else "estimé", "supposé et estimé" if sup else "compté et estimé", ""),
        ("Frais annuels du courtier", -a, mf, mf, ""),
        ("Dividendes moins frais", d - e - a, "estimé", "estimé",
         f"{_ecr(r20)} si dividendes −20 %" if r20 is not None else ""),
        ("Années suivantes, sans transaction", d - a, "estimé", "estimé",
         f"remise à niveau {_ecr(-bas)} à {_ecr(-haut)}"),
    ]
    for lib, x, st, etiq, extra in rows:
        ecran = f"   {lib:<35} {('environ ' + _ecr(x)):>16}  [{etiq}]" + (f" {extra}" if extra else "")
        det_extra = ""
        if extra and "−20 %" in extra:
            det_extra = f" {fcfa(r20, signe=True)} si dividendes −20 %"
        elif extra:
            det_extra = f" remise à niveau {fcfa(-bas, signe=True)} à {fcfa(-haut, signe=True)}"
        _L(L, "recevoir", ecran, f"   {lib} : {fcfa(x, signe=True)} [{etiq}]{det_extra}", montant=int(x), ecran=_ecr(x),
           statut=st, type_="ligne_montant")
    _paragraphe(L, "recevoir", "Montants arrondis. " + _rg.PH_COURS, "Montants au franc. " + _rg.PH_COURS, retrait="   ")


def _bloc_feux(L: list, rn: Mapping[str, Any], suivi: Mapping[str, Any] | None) -> dict[str, Any]:
    fx = None
    if isinstance(suivi, Mapping):
        fx = suivi.get("feux")
    if fx is None and isinstance(rn.get("suivi"), Mapping):
        fx = rn["suivi"].get("feux")
    if not fx or not fx.get("suivi_commence"):
        txt = "TROIS FEUX CHAQUE SEMAINE    Perte : —    Fuites : —    Données : —    (le suivi n'a pas commencé)"
        _L(L, "feux", txt, type_="feux")
        return fx or {"suivi_commence": False}
    txt = (f"TROIS FEUX CHAQUE SEMAINE    Perte : {fx['perte']['affichage']}    Fuites : {fx['fuites']['affichage']}    "
           f"Données : {fx['donnees']['affichage']}")
    _L(L, "feux", txt, type_="feux")
    _paragraphe(L, "feux", _rg.PH_REVUE, retrait="   ")
    return fx


def construire_plan(rendement_net: Mapping[str, Any], plan_enregistre: Mapping[str, Any] | None = None,
                    suivi: Mapping[str, Any] | None = None, aujourd_hui: Any = None) -> dict[str, Any]:
    """Écran « Mon plan » (§F1) assemblé à partir de ``rendement_net`` : ``{"lignes": [{"bloc", "texte", "montant",
    "montant_ecran", "statut", …}], "une_chose": str, "feux": {...}}``. ``montant`` est au franc ; ``montant_ecran``
    est le texte arrondi (règle 10). Un bloc en échec s'écrit « non calculé », jamais 0."""
    rn = rendement_net
    ctx = rn.get("contexte") or {}
    L: list[dict[str, Any]] = []
    K = ctx.get("capital")
    if ctx.get("panel_en_retard"):
        _paragraphe(L, "entete", str(ctx["panel_en_retard"]))
    b = rn.get("bilan")
    if _ok(b):
        t = b["totaux"]
        if t["annuels"] > t["dividendes_nets"]:
            _paragraphe(L, "entete", f"À ce tarif, {ctx.get('n_lignes_cibles') or 20} lignes coûtent plus qu'elles ne rapportent : "
                                     f"{fcfa(t['annuels'])} de frais par an pour {fcfa(t['dividendes_nets'])} de dividendes "
                                     "attendus.", montant=t["annuels"], ecran=fcfa(t["annuels"]), statut="supposé")
    jour = ""
    if ctx.get("asof"):
        try:
            d = _rg._date(ctx["asof"])
            noms = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
            jour = f" — cours du {noms[d.weekday()]} {d:%d/%m/%Y}"
        except (TypeError, ValueError):
            jour = ""
    _L(L, "entete", f"MON PLAN — {fcfa(K) if K else 'capital non calculé'}{jour}", type_="titre")
    _L(L, "entete", _rg.BANNER, type_="texte")
    et = rn.get("etude") if _ok(rn.get("etude")) else {}
    ph = list(et.get("phrases") or [_rg.PH_ETUDE, _rg.phrase_seance(aujourd_hui)])
    _paragraphe(L, "etude", " ".join(ph))
    _blanc(L, "etude")
    _bloc_courtier(L, rn)
    _blanc(L, "courtier")
    _bloc_risque(L, rn)
    _blanc(L, "risque")
    _bloc_reserve(L, rn)
    _blanc(L, "reserve")
    code, une = _une_chose(rn, plan_enregistre)
    _L(L, "une_chose", f"SI VOUS NE FAITES QU'UNE CHOSE CETTE SEMAINE : {une}", type_="titre")
    _blanc(L, "une_chose")
    _bloc_recevoir(L, rn)
    _blanc(L, "recevoir")
    fx = _bloc_feux(L, rn, suivi)
    return {"lignes": L, "une_chose": une, "une_chose_code": code, "feux": fx, "aujourd_hui":
            (_rg._date(aujourd_hui).isoformat() if aujourd_hui is not None else _dt.date.today().isoformat())}


# ---------------------------------------------------------------------------
# Rendus
# ---------------------------------------------------------------------------


_INSECABLE = re.compile(r"(\d) (%|FCFA\b)")


def _table_texte(entete: Sequence[str], cell: Sequence[str]) -> str:
    return (f"   {cell[0]:>9}  {cell[1]:>10}  {cell[2]:>10}   {cell[3]:<24}  {cell[4]}").rstrip()


def _texte(plan: Mapping[str, Any]) -> str:
    out: list[str] = []
    entete = None
    for l0 in plan["lignes"]:
        if l0.get("detail_seul"):
            continue
        l = dict(l0)
        l["texte"] = _INSECABLE.sub("\\1\u00a0\\2", str(l["texte"]))
        t = l["type"]
        if t == "paragraphe":
            r = l.get("retrait") or ""
            r2 = r + "   " if l["texte"].startswith("->") else r
            out.extend(textwrap.wrap(l["texte"], width=int(l.get("largeur") or LARGEUR), initial_indent=r,
                                     subsequent_indent=r2, break_on_hyphens=False) or [r])
        elif t == "entete_table":
            entete = l["cellules"]
            out.append(f"   {entete[0]:>9}  {entete[1]:>10}  {entete[2]:>10}   {entete[3]:<24}  {entete[4]}")
        elif t == "ligne_table":
            out.append(_table_texte(entete or [], l["cellules"]))
        elif t == "blanc":
            out.append("")
        else:
            out.extend(textwrap.wrap(l["texte"], width=LARGEUR, break_on_hyphens=False, subsequent_indent="   ")
                       if len(l["texte"]) > LARGEUR else [l["texte"]])
    while out and out[-1] == "":
        out.pop()
    lmax = 45
    i = len(out) - 1
    while len(out) > lmax and i >= 0:
        if out[i] == "":
            del out[i]
        i -= 1
    return "\n".join(out) + "\n"


def _md(plan: Mapping[str, Any]) -> str:
    out: list[str] = []
    rows: list[list[str]] = []
    head: list[str] | None = None
    flatteuse = False

    def vider() -> None:
        nonlocal rows, head
        if head is not None:
            out.append("| " + " | ".join(head) + " |")
            out.append("|" + "|".join("---" for _ in head) + "|")
            out.extend("| " + " | ".join(r) + " |" for r in rows)
            out.append("")
            if flatteuse:
                out.append(_rg.PH_FLATTE)
                out.append("")
        rows, head = [], None

    for l in plan["lignes"]:
        t = l["type"]
        if t == "entete_table":
            head = list(l["cellules_detail"]) + ["Pire moment de 2018 ; si 2017-2020 revenait"]
            flatteuse = any("flatteuse" in h for h in head)
            continue
        if t == "ligne_table":
            rows.append(list(l["cellules_detail"]))
            continue
        if t == "sous_ligne":
            if rows and head is not None:
                rows[-1] = (rows[-1] + [""] * len(head))[: len(head) - 1] + [l["texte_detail"].strip()]
            continue
        vider()
        if t == "titre":
            out.append(("## " if l["bloc"] == "entete" else "### ") + str(l.get("titre") or l["texte_detail"]).strip()
                       + (f" — {l.get('etiquette')}" if l.get("etiquette") else ""))
            out.append("")
        elif t == "blanc":
            continue
        elif t in ("ligne_montant",):
            out.append("- " + l["texte_detail"].strip())
        elif t == "feux":
            out.append("")
            out.append(f"**{l['texte_detail'].strip()}**")
        else:
            out.append(l["texte_detail"].strip())
            out.append("")
    vider()
    txt = "\n".join(out)
    while "\n\n\n" in txt:
        txt = txt.replace("\n\n\n", "\n\n")
    return txt.strip() + "\n\n> **" + _rg.BANNER + "**\n"


_CSS = ("<style>.mon-plan{font-family:system-ui,-apple-system,'Segoe UI',sans-serif;max-width:60rem;line-height:1.45;"
        "color:#1d2733;background:#ffffff;padding:12px}.mon-plan h3{font-size:1rem;margin:1rem 0 .3rem}"
        ".mon-plan .etiquette{font-weight:normal;color:#55606e;font-size:.9rem}.mon-plan table{border-collapse:collapse;"
        "width:100%}.mon-plan td,.mon-plan th{padding:3px 6px;border-bottom:1px solid #e3e6ea;text-align:right;"
        "vertical-align:top}.mon-plan td.t,.mon-plan th.t{text-align:left}.mon-plan .sous{color:#55606e;font-size:.9rem;"
        "text-align:left}.mon-plan .bandeau{font-weight:bold}.mon-plan .feux{font-weight:bold;margin-top:1rem}"
        "@media (prefers-color-scheme: dark){.mon-plan{color:#e6e9ee;background:#161b22}.mon-plan td,.mon-plan th"
        "{border-color:#30363d}.mon-plan .sous,.mon-plan .etiquette{color:#a3abb6}}</style>")


def _html_plan(plan: Mapping[str, Any]) -> str:
    e = _html.escape
    out = [_CSS, '<section class="mon-plan" lang="fr">']
    table_ouverte = False
    for l in plan["lignes"]:
        if l.get("detail_seul"):
            continue
        t = l["type"]
        if t not in ("ligne_table", "sous_ligne") and table_ouverte:
            out.append("</tbody></table>")
            table_ouverte = False
        if t == "titre":
            if l.get("etiquette"):
                out.append(f"<h3>{e(l.get('titre') or l['texte'])} <span class=\"etiquette\">[ {e(l['etiquette'])} ]</span></h3>")
            elif l["bloc"] == "entete":
                out.append(f"<h2>{e(l['texte'])}</h2>")
            else:
                out.append(f"<h3>{e(l['texte'])}</h3>")
        elif t == "entete_table":
            c = l["cellules"]
            out.append("<table><thead><tr>" + "".join(
                f"<th scope=\"col\" class=\"{'t' if i >= 3 else ''}\">{e(x)}</th>" for i, x in enumerate(c)) + "</tr></thead><tbody>")
            table_ouverte = True
        elif t == "ligne_table":
            c = l["cellules"]
            out.append("<tr>" + "".join(f"<td class=\"{'t' if i >= 3 else ''}\">{e(x)}</td>" for i, x in enumerate(c)) + "</tr>")
        elif t == "sous_ligne":
            out.append(f"<tr><td></td><td class=\"sous\" colspan=\"4\">{e(l['texte'].strip())}</td></tr>")
        elif t == "blanc":
            continue
        elif t == "feux":
            out.append(f"<p class=\"feux\">{e(l['texte'])}</p>")
        elif t == "texte" and l["texte"] == _rg.BANNER:
            out.append(f"<p class=\"bandeau\">{e(l['texte'])}</p>")
        else:
            out.append(f"<p>{e(l['texte'].strip())}</p>")
    if table_ouverte:
        out.append("</tbody></table>")
    out.append(f"<p class=\"bandeau\">{e(_rg.BANNER)}</p>")
    out.append("</section>")
    return "\n".join(out) + "\n"


def rendre_plan(plan: Mapping[str, Any], fmt: str = "texte") -> str:
    """Rendu de l'écran : ``texte`` et ``html`` (formes écran, montants arrondis) ; ``md`` (forme détail, au franc,
    avec la lecture flatteuse suivie de ``PH_FLATTE``)."""
    f = str(fmt).lower()
    if f in ("texte", "text", "txt"):
        return _texte(plan)
    if f in ("md", "markdown"):
        return _md(plan)
    if f == "html":
        return _html_plan(plan)
    raise ValueError(f"format inconnu : {fmt!r} (texte, md ou html)")
