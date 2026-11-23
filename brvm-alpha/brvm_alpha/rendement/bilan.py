"""F3 — Du brut au net : la facture, ce qui est supposé, les leviers (cahier ``docs/RENDEMENT_NET.md``, §F3).

Un tableau répond à : « sur ce que mon portefeuille verserait, combien m'arriverait, et qui prend le reste ? ».
Chaque ligne dit combien, une fois ou chaque année, son statut (Fait, Estimation, Hypothèse) et ce qu'on peut y
faire. Les totaux de l'ordre de bataille sont retrouvés à 0 FCFA d'écart (contrôle d'identité affiché).

Deux tableaux de leviers, jamais mélangés : « frais évités par rapport au tarif supposé » (tableau A) et « argent
placé en plus : gain ou perte selon le marché » (tableau B). Chaque ligne du tableau A est **recalculée** par
:func:`brvm_alpha.rendement.grille.comparer` ; rien n'est additionné à la main.

Une économie de frais n'est pas un gain. Des francs placés ne sont pas des francs gagnés.
"""

from __future__ import annotations

import math
from typing import Any, Mapping

from brvm_alpha.rendement import grille as _gr
from brvm_alpha.rendement import reglages as _rg
from brvm_alpha.rendement.reglages import ESTIMATION, FAIT, HYPOTHESE, R, plus_faible

__all__ = ["aller_retour", "amortissement", "bilan_fuites", "leviers", "lignes_petites"]

#: Catégories « par action possible » (§F3).
ACTIONS = ("aucune", "négociable", "selon le courtier", "à vérifier", "exécution")


def _ratio(a: float, b: float) -> float | None:
    return float(a) / float(b) if b else None


def _grille_de(o: Mapping[str, Any], grille: _gr.GrilleSGI | None, costs: Any = None) -> _gr.GrilleSGI:
    if grille is not None:
        return grille
    cm = _gr.cost_model_de(o, costs)
    nom = "Tarif supposé (" + str((o.get("couts") or {}).get("scenario") or "central") + ")"
    return _gr.depuis_cost_model(cm, nom)


def _forfait(o: Mapping[str, Any], g: _gr.GrilleSGI) -> int:
    c = o.get("couts") or {}
    if c.get("forfait_compte_annuel") is not None:
        return int(c["forfait_compte_annuel"])
    return int(R.round_fcfa(g.valeur("forfait_compte")))


def _irvm_par_pays(o: Mapping[str, Any]) -> dict[str, int]:
    out: dict[str, int] = {}
    for d in o.get("dividendes") or []:
        p = str(d.get("pays") or "")
        out[p] = out.get(p, 0) + int(d.get("irvm") or 0)
    return out


def bilan_fuites(ordre: Any, grille: _gr.GrilleSGI | None = None, horizon_ans: int | None = None, *,
                 reglages: Mapping[str, Any] | None = None, costs: Any = None) -> dict[str, Any]:
    """Tableau du brut au net (§F3) : lignes B, T, E1 à E6, A1 à A5 ; totaux ; part supposée ou estimée (règle du
    statut le plus faible) et ce qui la lèverait ; dividendes en baisse ; remise à niveau de janvier ; aller-retour ;
    détail ligne par ligne.

    ``grille`` : la grille employée pour l'ordre (``None`` : le tarif de l'ordre, tous les champs supposés)."""
    o = _rg.en_dict(ordre)
    g = _grille_de(o, grille, costs)
    c = dict(o.get("couts") or {})
    if grille is not None:
        # Grille donnée : les postes de coûts sont recalculés avec elle sur les lignes de l'ordre (aucune relance de
        # recommend) ; avec la grille par défaut, ils sont égaux au franc à ceux de l'ordre.
        c.update(_gr.couts_recalcules(o, grille, _gr.cost_model_de(o, costs)))
    rv = o.get("revenus") or {}
    H = int(horizon_ans if horizon_ans is not None else _rg.lire(reglages, "frais.horizon_ans", 3))
    K = float(o.get("capital") or o.get("valeur_portefeuille") or 0)
    V = float(o.get("valeur_portefeuille") or K)
    verifies = set(_rg.lire(reglages, "frais.irvm_verifies", ["CI", "SN"]) or [])
    forfait = _forfait(o, g)
    hm = _gr.frais_hors_modele(g, c, rv, o.get("dividendes"), forfait)

    B = int(rv.get("brut") or 0)
    T = int(rv.get("irvm") or 0)
    par_pays = _irvm_par_pays(o)
    T_v = int(sum(v for k, v in par_pays.items() if k in verifies))
    T_nv = T - T_v
    st_T = (HYPOTHESE if T_nv > 0 else ESTIMATION) if T > 0 else ESTIMATION
    s_court = _gr.statut_champ(g, "courtage")
    if g.valeur("courtage_min_par_ordre") > 0:
        s_court = plus_faible(s_court, _gr.statut_champ(g, "courtage_min_par_ordre"))
    s_taxe = plus_faible(s_court, _gr.statut_champ(g, "taxe_courtage"))
    s_garde = _gr.statut_champ(g, "garde")
    if g.valeur("garde_minimum") > 0:
        s_garde = plus_faible(s_garde, _gr.statut_champ(g, "garde_minimum"))
    s_enc = plus_faible(_gr.statut_champ(g, "encaissement_taux"), _gr.statut_champ(g, "encaissement_fixe"))

    def L(code: str, lib: str, montant: int, freq: str, statut: str, action: str, levee: str | None,
          detail: str = "") -> dict[str, Any]:
        return {"code": code, "libelle": lib, "montant": int(montant), "frequence": freq, "statut": statut,
                "mot_statut": _rg.mot_statut(statut), "action": action, "levee_par": levee if statut != FAIT else None,
                "pct_capital": _ratio(montant, K), "pct_brut": _ratio(montant, B), "detail": detail}

    lignes = [
        L("B", "Dividendes bruts attendus", B, "par an", ESTIMATION, "—", None, "dernier dividende reconduit"),
        L("T", "Impôt sur les dividendes", T, "par an", st_T, "aucune (retenu à la source)",
          "taux_impot_non_verifie" if T_nv else "dividendes_estimes",
          f"pays au taux vérifié {_rg.fcfa(T_v)} ; autres pays {_rg.fcfa(T_nv)}"),
        L("E1", "Courtage", int(c.get("courtage") or 0), "une fois", s_court, "négociable", "grille"),
        L("E2", "Taxe sur le courtage", int(c.get("tva") or 0), "une fois", s_taxe,
          "à vérifier (une taxe ne se négocie pas)", "grille"),
        L("E3", "Commission de la BRVM", int(c.get("brvm") or 0), "une fois", FAIT, "aucune", None),
        L("E4", "Commission du dépositaire (DC/BR)", int(c.get("dcbr") or 0), "une fois", FAIT, "aucune", None),
        L("E5", "Écart entre acheteurs et vendeurs", int(c.get("demi_spread") or 0), "une fois", ESTIMATION,
          "exécution", "execution"),
        L("E6", "Effet de l'ordre sur le prix", int(c.get("impact") or 0), "une fois", ESTIMATION, "exécution",
          "execution"),
        L("A1", "Droits de garde", int(c.get("garde_annuelle") or 0) + hm["garde_complement"], "par an", s_garde,
          "négociable", "grille"),
        L("A2", "Tenue de compte par ligne", int(c.get("tenue_compte_annuelle") or 0), "par an",
          _gr.statut_champ(g, "tenue_par_ligne"), "selon le courtier", "grille"),
        L("A3", "Forfait de compte", forfait, "par an", _gr.statut_champ(g, "forfait_compte"), "selon le courtier",
          "grille"),
        L("A4", "Taxe sur les frais annuels", hm["taxe_annuelle"], "par an", _gr.statut_champ(g, "taxe_frais_annuels"),
          "à vérifier", "grille"),
        L("A5", "Encaissement des dividendes", hm["encaissement"], "par an", s_enc, "selon le courtier", "grille"),
    ]
    red = int(c.get("redevance") or 0) if "redevance" in c else 0
    if red:
        lignes.insert(8, L("E7", "Redevance du régulateur", red, "une fois", HYPOTHESE, "aucune", "grille"))
    entree_l = [x for x in lignes if x["code"].startswith("E")]
    annuels_l = [x for x in lignes if x["code"].startswith("A")]
    entree = sum(x["montant"] for x in entree_l)
    annuels = sum(x["montant"] for x in annuels_l)
    N = B - T
    fuites1 = T + entree + annuels
    fuites2 = T + annuels
    reste1 = N - entree - annuels
    reste2 = N - annuels
    facture = [x for x in lignes if x["code"] != "B"]
    sup = sum(x["montant"] for x in facture if x["statut"] != FAIT)
    frais_l = entree_l + annuels_l
    sup_frais = sum(x["montant"] for x in frais_l if x["statut"] != FAIT)
    levee = {"grille": 0, "execution": 0, "taux_impot_non_verifie": 0, "dividendes_estimes": 0}
    for x in frais_l:
        if x["statut"] != FAIT and x["levee_par"] in levee:
            levee[x["levee_par"]] += x["montant"]
    levee["taux_impot_non_verifie"] = T_nv
    levee["dividendes_estimes"] = T_v
    par_action = {a: 0 for a in ACTIONS}
    for x in facture:
        a = x["action"]
        if a.startswith("aucune"):
            par_action["aucune"] += x["montant"]
        elif a.startswith("à vérifier"):
            par_action["à vérifier"] += x["montant"]
        elif a in par_action:
            par_action[a] += x["montant"]
    chutes = [float(x) for x in (_rg.lire(reglages, "frais.chutes_dividendes", [0.075, 0.20]) or [])]
    baisse = []
    for ch in chutes:
        Nc = R.round_fcfa(N * (1.0 - ch))
        baisse.append({"chute": ch, "net": int(Nc), "reste_an1": int(Nc - entree - annuels),
                       "reste_suivant": int(Nc - annuels)})
    investi = float(c.get("investi_apres") or 0)
    a_taux = entree / investi if investi > 0 else 0.0
    bas = 2 * 12 * float(_rg.lire(reglages, "frais.rotation_basse_mensuelle", 0.0087)) * V * a_taux
    haut = float(_rg.lire(reglages, "frais.remise_a_niveau_haute", 0.0123)) * V
    controle = B - fuites1 - reste1
    totaux = {
        "dividendes_bruts": B, "impot": T, "dividendes_nets": N, "entree": entree, "annuels": annuels,
        "fuites_an1": fuites1, "fuites_suivantes": fuites2, "reste_an1": reste1, "reste_suivant": reste2,
        "frais_an1": entree + annuels,
        "part_supposee": _ratio(sup, fuites1), "supposee_fcfa": int(sup),
        "part_supposee_frais": _ratio(sup_frais, entree + annuels), "supposee_frais_fcfa": int(sup_frais),
        "levee_par": levee, "par_action": par_action, "controle_ecart": int(controle),
        "controle_couts_total": int(entree - int(c.get("total") or 0)),
        "pct_capital_an1": _ratio(fuites1, K), "pct_brut_an1": _ratio(fuites1, B),
        "ratio_annuels_dividendes": _ratio(annuels, N),
    }
    return {
        "grille": g.nom, "statut_grille": _gr.statut_global(g), "lignes": lignes, "totaux": totaux,
        "dividendes_en_baisse": baisse,
        "remise_a_niveau": {"bas": int(R.round_fcfa(bas)), "haut": int(R.round_fcfa(haut)), "bas_exact": bas,
                            "haut_exact": haut, "statut": ESTIMATION,
                            "libelle": "Remise à niveau de janvier et sorties forcées (hors totaux) : Estimation ; à "
                                       "mesurer pendant le suivi sur papier"},
        "aller_retour": aller_retour({**o, "couts": c}, H, costs=costs),
        "lignes_petites": lignes_petites(o, g),
        "lignes_fixes": ["Variations de cours : non comptées. " + _rg.PH_COURS,
                         "Impôt sur les plus-values : non compté (0 supposé, non vérifié).", _rg.PH_FRAIS],
        "horizon_ans": H,
    }


def aller_retour(ordre: Any, horizon_ans: int = 3, *, costs: Any = None) -> dict[str, Any]:
    """Coût d'un aller-retour (2 × frais d'entrée), en % de l'investi, réparti sur 1, 3 et 5 ans ; pour chaque
    vente proposée : « Cette vente coûterait X FCFA. Racheter plus tard le même montant coûterait Y FCFA. »"""
    o = _rg.en_dict(ordre)
    c = o.get("couts") or {}
    entree = int(c.get("total") or 0)
    investi = float(c.get("investi_apres") or 0)
    cout = 2 * entree
    cm = _gr.cost_model_de(o, costs)
    ventes = []
    for l in o.get("lignes") or []:
        if l.get("sens") != "vente" or int(l.get("quantite") or 0) <= 0:
            continue
        q = int(l["quantite"])
        tr = [int(x) for x in (l.get("tranches") or [q])]
        lim = l.get("limite_achat")
        rach = R.order_costs(q, float(l["cours_reference"]), cm, side="achat",
                             half_spread=float(l.get("demi_spread_pct") or 0.0),
                             mdv63=float(l["mdv63"]) if l.get("mdv63") is not None else None, tranches=tr,
                             limit=float(lim) if lim is not None else None)
        x, y = int(l.get("couts_total") or 0), int(rach["total"])
        ventes.append({"symbole": l["symbole"], "cout_vente": x, "cout_rachat": y,
                       "texte": f"Cette vente coûterait {_rg.fcfa(x)}. Racheter plus tard le même montant coûterait "
                                f"{_rg.fcfa(y)}."})
    return {"cout": cout, "pct_investi": _ratio(cout, investi), "horizon_ans": int(horizon_ans),
            "par_an": {str(h): int(R.round_fcfa(cout / h)) for h in (1, 3, 5)}, "statut": ESTIMATION,
            "ventes": ventes}


def lignes_petites(ordre: Any, grille: _gr.GrilleSGI | None = None, *, costs: Any = None) -> list[dict[str, Any]]:
    """Ligne par ligne : frais annuels de la ligne (``round_fcfa(garde × v_i)`` + tenue par ligne), dividende net
    attendu, rapport ; rouge si le rapport ≥ 100 %, orange si ≥ 50 %. Triées du rapport le plus lourd au plus
    léger."""
    o = _rg.en_dict(ordre)
    g = _grille_de(o, grille, costs)
    div: dict[str, int] = {}
    for d in o.get("dividendes") or []:
        div[str(d["symbole"])] = div.get(str(d["symbole"]), 0) + int(d.get("montant_net") or 0)
    out = []
    for l in o.get("lignes") or []:
        if int(l.get("cibles") or 0) <= 0:
            continue
        v = float(l.get("valeur_apres") or 0)
        fr = int(R.round_fcfa(g.valeur("garde") * v) + R.round_fcfa(g.valeur("tenue_par_ligne")))
        dv = int(div.get(str(l["symbole"]), 0))
        r = fr / dv if dv > 0 else (math.inf if fr > 0 else 0.0)
        niveau = "rouge" if r >= 1.0 else ("orange" if r >= 0.5 else None)
        out.append({"symbole": l["symbole"], "frais_annuels": fr, "dividende_net": dv,
                    "rapport": None if math.isinf(r) else r, "sans_dividende": dv <= 0, "niveau": niveau})
    out.sort(key=lambda x: (-(x["rapport"] if x["rapport"] is not None else 1e9), x["symbole"]))
    return out


def _avec_grille(o: Mapping[str, Any], g: _gr.GrilleSGI, nouvelles: dict[str, _gr.GrilleSGI], costs: Any) -> dict[str, dict[str, Any]]:
    cm = _gr.cost_model_de(o, costs)
    res = _gr.comparer(o, nouvelles, base=cm, reference=g)
    return {r["cle"]: r for r in res}


def leviers(ordre: Any, grille: _gr.GrilleSGI | None = None, lectures: Mapping[str, Any] | None = None, *,
            arrondi: Mapping[str, Any] | None = None, reinvestir: Mapping[str, Any] | None = None,
            reglages: Mapping[str, Any] | None = None, costs: Any = None) -> dict[str, Any]:
    """Leviers (§F3) : tableau A « frais évités par rapport au tarif supposé ; 0 si votre courtier ne facture pas
    ce poste » (recalculé par ``grille.comparer``), inconnues à lever (ni gestes, ni gains), tableau B « argent
    placé en plus : gain ou perte selon le marché » (``PH_PLACE``).

    ``lectures`` : résumé des lectures du risque (``risque.resume_pour_leviers``) ; ``arrondi`` : sortie de
    ``liquidites.arrondi_restes`` ; ``reinvestir`` : sortie de ``liquidites.projection(..., reinvestir=True)``."""
    o = _rg.en_dict(ordre)
    g = _grille_de(o, grille, costs)
    H = int(_rg.lire(reglages, "frais.horizon_ans", 3))
    ex = _gr.exemples(reglages)
    cand = {"sans_tenue": g.avec(tenue_par_ligne=0), "garde_010": g.avec(garde=0.001),
            "courtage_050": g.avec(courtage=0.005)}
    for cle in ("sans_frais_par_ligne", "borne_non_attestee"):
        if cle in ex:
            cand[cle] = ex[cle]
    res = _avec_grille(o, g, cand, costs)

    def evite(r: Mapping[str, Any]) -> tuple[int, int, int]:
        return -int(r["ecart_achat"]), -int(r["ecart_annuel"]), -int(r["ecart_premiere_annee"])

    A: list[dict[str, Any]] = []
    tenue = g.valeur("tenue_par_ligne")
    u, a_, _p = evite(res["sans_tenue"])
    A.append({"geste": "Courtier sans tenue de compte par ligne", "une_fois": u, "par_an": a_,
              "condition": (f"si votre courtier facture {_rg.fcfa(tenue)} par ligne" if tenue > 0 else
                            "sans objet : votre courtier ne facture pas ce poste"),
              "contrepartie": "changer de courtier ; courtage peut-être plus élevé ; transfert de 5 000 à 34 375 FCFA "
                              "par ligne si des titres sont déjà détenus",
              "sans_objet": tenue <= 0, "statut": HYPOTHESE})
    garde = g.valeur("garde")
    u, a_, _p = evite(res["garde_010"])
    A.append({"geste": f"Droits de garde à 0,10 % au lieu de {_rg.pct(garde, 2)}", "une_fois": u, "par_an": a_,
              "condition": "si le taux est obtenu par écrit" if garde > 0.001 else
              "sans objet : votre taux est déjà à 0,10 % ou moins", "contrepartie": "aucune connue",
              "sans_objet": garde <= 0.001, "statut": HYPOTHESE})
    court = g.valeur("courtage")
    u, a_, _p = evite(res["courtage_050"])
    A.append({"geste": f"Courtage à 0,50 % au lieu de {_rg.pct(court, 2)}", "une_fois": u, "par_an": 0,
              "par_an_texte": "sur chaque ordre futur",
              "equivalent_annuel": int(R.round_fcfa(u / H)) if H else None,
              "condition": "si le taux est obtenu par écrit" if court > 0.005 else
              "sans objet : votre courtage est déjà à 0,50 % ou moins",
              "contrepartie": "aucune connue ; le taux réel de départ est inconnu", "sans_objet": court <= 0.005,
              "statut": HYPOTHESE})
    if "sans_frais_par_ligne" in res:
        r = res["sans_frais_par_ligne"]
        u, a_, p1 = evite(r)
        A.append({"geste": "Ensemble, avec la grille connue sans frais par ligne (courtage 1,00 %, forfait 4 000)",
                  "une_fois": u, "par_an": a_, "premiere_annee": p1,
                  "texte": _texte_evite(p1, a_),
                  "condition": "grille homologuée lue ; non confirmée pour vous",
                  "contrepartie": f"courtage plus élevé à l'entrée ({_rg.fcfa(-u, signe=True)})" if u < 0 else "—",
                  "sans_objet": False, "statut": HYPOTHESE})
    if "borne_non_attestee" in res:
        r = res["borne_non_attestee"]
        u, a_, p1 = evite(r)
        A.append({"geste": "Borne non attestée (0,50 % et aucun frais par ligne)", "une_fois": u, "par_an": a_,
                  "premiere_annee": p1, "texte": _texte_evite(p1, a_),
                  "condition": "aucune grille lue ne cumule ces avantages", "contrepartie": "—", "sans_objet": False,
                  "borne_non_attestee": True, "statut": HYPOTHESE})
    for x in A:
        if x.get("equivalent_annuel") is None:
            x["equivalent_annuel"] = int(x["par_an"] + (R.round_fcfa(x["une_fois"] / H) if H else 0))

    # Inconnues à lever (ni gestes, ni gains). Les postes de l'ordre sont recalculés avec la grille employée (comme la
    # ligne E2 du tableau du brut au net) : la borne haute de la taxe est celle de cette grille, pas du tarif central.
    inc: list[dict[str, Any]] = []
    c = dict(o.get("couts") or {})
    if grille is not None:
        c.update(_gr.couts_recalcules(o, grille, _gr.cost_model_de(o, costs)))
    if _gr.statut_champ(g, "taxe_courtage") != FAIT:
        r10 = _avec_grille(o, g, {"t10": g.avec(taxe_courtage=0.10)}, costs)["t10"]
        inc.append({"inconnue": "Taxe sur le courtage", "de": 0, "a": int(c.get("tva") or 0),
                    "si_10pct": int(r10["ecart_premiere_annee"]),
                    "texte": f"de 0 à {_rg.fcfa(c.get('tva') or 0)} ({_rg.fcfa(-r10['ecart_premiere_annee'], unite=False)} "
                             "de moins si elle est de 10 %)"})
    if _gr.statut_champ(g, "courtage_min_par_ordre") != FAIT:
        rm = _avec_grille(o, g, {"m": g.avec(courtage_min_par_ordre=2500.0)}, costs)["m"]
        inc.append({"inconnue": "Minimum par ordre", "minimum": 2500, "surcout": int(rm["ecart_achat"]),
                    "texte": f"{_rg.fcfa(rm['ecart_achat'], signe=True)} s'il est de 2 500 FCFA"})
    if _gr.statut_champ(g, "taxe_frais_annuels") != FAIT:
        rt = _avec_grille(o, g, {"t": g.avec(taxe_frais_annuels=0.18)}, costs)["t"]
        inc.append({"inconnue": "Taxe sur les frais annuels", "surcout_annuel": int(rt["ecart_annuel"]),
                    "texte": f"{_rg.fcfa(rt['ecart_annuel'], signe=True)} par an si elle est de 18 %"})
    inc.append({"inconnue": "Impôt sur les plus-values", "texte": "non compté"})

    # Tableau B : argent placé en plus (gain ou perte selon le marché)
    B: list[dict[str, Any]] = []
    rv = o.get("revenus") or {}
    rend = float(rv.get("rendement_net_investi") or 0.0)
    lec = lectures or {}

    def ligne_b(nom: str, francs: float, nature: str, moyenne: bool = False) -> dict[str, Any]:
        f = float(francs)
        out = {"changement": nom, "francs": int(R.round_fcfa(f)), "en_moyenne": moyenne,
               "dividendes": int(R.round_fcfa(f * rend)), "nature": nature, "statut": ESTIMATION,
               "phrase": _rg.PH_PLACE}
        for cle in ("ordinaire_prudente", "ordinaire_flatteuse", "une_sur_dix_flatteuse", "une_sur_dix_prudente",
                    "une_sur_dix_periodes"):
            if lec.get(cle) is not None:
                out[cle] = int(R.round_fcfa(f * float(lec[cle])))
        return out

    if arrondi and not arrondi.get("erreur"):
        B.append(ligne_b("Arrondi « plus forts restes » (F13c)", float(arrondi.get("francs_ajoutes") or 0),
                         "option, écart déclaré"))
    if reinvestir and not reinvestir.get("erreur") and reinvestir.get("remis_au_travail_moyen") is not None:
        B.append(ligne_b("Réinvestissement mensuel (F13d, règle corrigée)", float(reinvestir["remis_au_travail_moyen"]),
                         "option, essai E-D", moyenne=True))
    # Le tableau B porte une année ordinaire du passé et « une année sur dix », dont la lecture flatteuse : PH_PASSE,
    # PH_DESCRIPTIF et PH_FLATTE l'accompagnent (règle 8 du §1, §F1-10).
    return {"frais_evites": A, "phrase_frais_evites": _rg.PH_ECONOMIE, "inconnues": inc, "argent_place": B,
            "phrase_argent_place": _rg.PH_PLACE, "horizon_ans": H,
            "phrases": [_rg.PH_PASSE, _rg.PH_DESCRIPTIF, _rg.PH_FLATTE],
            "note": "Les lignes du tableau B se recoupent : elles ne s'additionnent pas."}


def _texte_evite(premiere_annee: int, par_an: int) -> str:
    """« 73 224 de moins la 1re année, puis 96 000 de moins par an » ; une valeur négative s'écrit « surcoût » (§F2)."""
    def un(x: int, quand: str) -> str:
        if x >= 0:
            return f"{_rg.fcfa(x, unite=False)} de moins {quand}"
        return f"surcoût de {_rg.fcfa(-x, unite=False)} {quand}"
    return un(int(premiere_annee), "la 1re année") + ", puis " + un(int(par_an), "par an")


def amortissement(poche: Mapping[str, Any]) -> dict[str, Any]:
    """Durée pour couvrir les frais d'achat (12 × e ÷ (d − a)) et un achat suivi d'une revente (24 × e ÷ (d − a)) ;
    « jamais » si d ≤ a (§F14, information)."""
    d = float(poche.get("dividendes") or 0)
    a = float(poche.get("frais_annuels") or 0)
    e = float(poche.get("frais_achat") or 0)
    rev = d - a
    if rev <= 0:
        return {"revenu_net_annuel": int(R.round_fcfa(rev)), "mois_frais_achat": None, "mois_achat_revente": None,
                "jamais": True}
    return {"revenu_net_annuel": int(R.round_fcfa(rev)), "mois_frais_achat": 12 * e / rev,
            "mois_achat_revente": 24 * e / rev, "jamais": False}
