"""Blocs Markdown et HTML communs du module « Rendement net et pertes » (cahier ``docs/RENDEMENT_NET.md``, §7.2, §7.3).

Les blocs ont la forme de ceux de l'ordre de bataille (``[(genre, valeur), …]`` avec ``h2``, ``h3``, ``p``, ``ul``,
``table``, ``warn``, ``banner``) : la phase de raccord les insère telle quelle dans ``OrdreDeBataille._blocks`` et les
rend avec le moteur de rendu de l'ordre (même typographie, même échappement HTML). Formes « détail » : montants au
franc.

* :func:`bloc_essentiel` : bloc « L'essentiel » (titre de niveau 3, 14 lignes au plus), après les avertissements ;
* :func:`blocs_section` : section « Rendement net et pertes » (titre de niveau 2), après « Revenus attendus » ;
* :func:`blocs_distribution` : lignes des lectures du risque, sous la table de la distribution ;
* :func:`ligne_execution` : la ligne ajoutée à la section « Exécution » ;
* :func:`sous_blocs_rapport` : sous-blocs du rapport HTML, à la fin des sections existantes ;
* :func:`fragment` : rendu Markdown ou HTML d'une liste de blocs (sans ressource externe).

Performance passée ≠ garantie. Aucun gain n'est garanti.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from brvm_alpha.rendement import reglages as _rg
from brvm_alpha.rendement.reglages import BANNER, R, fcfa, pct

__all__ = ["SOUS_PARTIES", "bloc_essentiel", "blocs_distribution", "blocs_section", "fragment", "ligne_execution",
           "ligne_ne_pas_transmettre", "sous_blocs_rapport"]

Bloc = tuple[str, Any]
SOUS_PARTIES = ("Du brut au net", "Frais évités par rapport au tarif supposé", "Inconnues à lever",
                "Ce que j'accepte de risquer", "Où dort le reste", "Argent qui dort et provision",
                "Argent placé en plus : gain ou perte selon le marché", "Passer l'ordre", "Points à vérifier")
NON_CALCULE = "non calculé"


def _ok(b: Any) -> bool:
    return isinstance(b, Mapping) and not b.get("erreur")


def _err(b: Any) -> str:
    return f"{NON_CALCULE} ({b.get('erreur')})" if isinstance(b, Mapping) and b.get("erreur") else NON_CALCULE


def _s(x: Any) -> str:
    return fcfa(x, signe=True) if x is not None else NON_CALCULE


def _ligne_choix(r: Mapping[str, Any]) -> str:
    if not r.get("en_actions") and not r.get("tout"):
        return f"{fcfa(r.get('perte_toleree'))} acceptés : {r.get('message') or 'aucun montant en actions possible'}"
    qui = "Tout en actions" if r.get("tout") else f"{fcfa(r['perte_toleree'])} acceptés"
    bas, haut = (r.get("annee_2018") or [None, None])[:2]
    dep = r.get("depasse") or {}
    d1 = " (dépasse)" if dep.get("pire_moment") else ""
    d2 = " (dépasse)" if dep.get("2017_2020") else ""
    ordi = (r.get("annee_ordinaire") or {}).get("prudente")
    return (f"{qui} : {fcfa(r['en_actions'])} en actions, {fcfa(r['reserve'])} en réserve ; une année comme 2018 "
            f"{_s(-bas) if bas is not None else NON_CALCULE} à {_s(-haut) if haut is not None else NON_CALCULE} ; pire moment "
            f"de 2018 {_s(-(r.get('pire_moment_2018') or 0)) if r.get('pire_moment_2018') is not None else NON_CALCULE}{d1} ; "
            f"si 2017-2020 revenait {_s(-(r.get('baisse_2017_2020') or 0)) if r.get('baisse_2017_2020') is not None else NON_CALCULE}{d2} ; "
            f"année ordinaire (prudente) {_s(ordi)} [estimé]")


def bloc_essentiel(rn: Mapping[str, Any]) -> list[Bloc]:
    """Bloc « L'essentiel » (§7.3) : 14 lignes au plus, montants au franc. ``PH_SEANCE`` ; frais de la 1re année et
    part supposée ou estimée des frais ; le premier geste ; les lignes de la table de choix (ou la ligne retenue),
    chacune avec ses deux dépassements en FCFA ; ``PH_PASSE`` et ``PH_DESCRIPTIF`` ; la valeur d'un point de taux sur
    la réserve et ``PH_INTERETS`` ; les trois feux."""
    items: list[str] = []
    et = rn.get("etude") if _ok(rn.get("etude")) else {}
    ph = et.get("phrases") or []
    if len(ph) > 1:
        items.append(ph[1])
    b = rn.get("bilan")
    if _ok(b):
        t = b["totaux"]
        items.append(f"Frais de la 1re année si vous achetiez tout : {fcfa(t['frais_an1'])}, dont {pct(t['part_supposee_frais'])} "
                     f"supposés ou estimés ({fcfa(t['supposee_frais_fcfa'])}). {_rg.PH_FRAIS}")
    else:
        items.append(f"Frais de la 1re année : {_err(b)}.")
    pl = rn.get("plan") if _ok(rn.get("plan")) else {}
    if pl.get("une_chose"):
        items.append(f"Si vous ne faites qu'une chose cette semaine : {pl['une_chose']}")
    p = rn.get("perte")
    if _ok(p):
        lignes = [p["choix"]] if p.get("choix") else list(p.get("table") or [])
        for r in lignes[:4]:
            items.append(_ligne_choix(r))
    else:
        items.append(f"Ce que j'accepte de risquer : {_err(p)}.")
    items.append(f"{_rg.PH_PASSE} {_rg.PH_DESCRIPTIF}")
    r = rn.get("reserve")
    if _ok(r):
        items.append(f"Réserve {fcfa(r['montant'])} : un point d'intérêt vaut {fcfa(r['valeur_d_un_point'])} par an. "
                     f"{_rg.PH_INTERETS}")
    fx = ((rn.get("suivi") or {}).get("feux") if isinstance(rn.get("suivi"), Mapping) else None) or {}
    if fx.get("suivi_commence"):
        items.append(f"Trois feux : perte {fx['perte']['affichage']} ; fuites {fx['fuites']['affichage']} ; données "
                     f"{fx['donnees']['affichage']}. {_rg.PH_REVUE}")
    else:
        items.append("Trois feux : perte — ; fuites — ; données — (le suivi n'a pas commencé).")
    return [("h3", "L'essentiel"), ("ul", items[:13])]


def ligne_ne_pas_transmettre() -> Bloc:
    """Ligne placée juste au-dessus de la table des ordres tant que le statut est REJETÉ (le titre de la table ne
    change pas)."""
    return ("strong", _rg.PH_NE_PAS_TRANSMETTRE)


def ligne_execution(rn: Mapping[str, Any]) -> str | None:
    """Ligne ajoutée à la section « Exécution » : provision à avoir avant l'ordre, part investie maximale."""
    pv = ((rn.get("liquidites") or {}).get("provision")) if isinstance(rn.get("liquidites"), Mapping) else None
    return pv.get("texte") if _ok(pv) else None


def _bilan_table(b: Mapping[str, Any]) -> list[Bloc]:
    rows = []
    for x in b["lignes"]:
        rows.append([x["libelle"], fcfa(x["montant"]), x["frequence"], x["mot_statut"], x["action"],
                     pct(x["pct_capital"], 2) if x["pct_capital"] is not None else "—",
                     pct(x["pct_brut"], 1) if x["pct_brut"] is not None else "sans objet"])
    t = b["totaux"]
    lv = t["levee_par"]
    B: list[Bloc] = [("table", (["Poste", "Montant", "Fréquence", "Statut", "Action possible", "% du capital",
                                 "% des dividendes bruts"], rows))]
    B.append(("ul", [
        f"Frais et impôt de la 1re année : {fcfa(t['fuites_an1'])} ({pct(t['pct_capital_an1'], 2)} du capital) ; années "
        f"suivantes, sans transaction : {fcfa(t['fuites_suivantes'])}",
        f"Dividendes moins frais : 1re année {_s(t['reste_an1'])} ; années suivantes, sans transaction "
        f"{_s(t['reste_suivant'])} [estimé]",
        f"Part supposée ou estimée (statut le plus faible) : {pct(t['part_supposee'])} de la facture "
        f"({fcfa(t['supposee_fcfa'])}) ; {pct(t['part_supposee_frais'])} des seuls frais ({fcfa(t['supposee_frais_fcfa'])})",
        f"Ce qui la lèverait : la grille écrite {fcfa(lv['grille'])} ; l'avis d'opéré (exécution) {fcfa(lv['execution'])} ; "
        f"le taux d'impôt non vérifié {fcfa(lv['taux_impot_non_verifie'])} ; le paiement des dividendes estimés "
        f"{fcfa(lv['dividendes_estimes'])}",
        "Par action possible : " + " ; ".join(f"{k} {fcfa(v)}" for k, v in t["par_action"].items()),
        f"Contrôle : dividendes bruts − (frais et impôt) = dividendes moins frais, écart {fcfa(t['controle_ecart'])}",
    ] + [f"Si les dividendes baissent de {pct(x['chute'], 1)} : 1re année {_s(x['reste_an1'])} ; ensuite {_s(x['reste_suivant'])}"
         for x in b.get("dividendes_en_baisse") or []]
        + [f"{b['remise_a_niveau']['libelle']} : {fcfa(b['remise_a_niveau']['bas'])} à {fcfa(b['remise_a_niveau']['haut'])} par an",
           f"Aller-retour : {fcfa(b['aller_retour']['cout'])} ({pct(b['aller_retour']['pct_investi'], 2)} de l'investi)"]
        + [v["texte"] for v in b["aller_retour"].get("ventes") or []] + list(b.get("lignes_fixes") or [])))
    return B


def blocs_section(rn: Mapping[str, Any]) -> list[Bloc]:
    """Section « Rendement net et pertes » de l'ordre de bataille (§7.3), sous-parties dans l'ordre du cahier ; détail
    ligne par ligne et projection par mois en fin de section."""
    B: list[Bloc] = [("h2", "Rendement net et pertes"), ("banner", BANNER)]
    et = rn.get("etude") if _ok(rn.get("etude")) else {}
    for ph in et.get("phrases") or []:
        B.append(("strong", ph))
    gr = rn.get("grille")
    if _ok(gr):
        B.append(("p", gr.get("texte") or ""))
        if gr.get("non_employee"):
            B.append(("warn", gr["non_employee"]))
    # 1. Du brut au net
    B.append(("h3", SOUS_PARTIES[0]))
    b = rn.get("bilan")
    B.extend(_bilan_table(b) if _ok(b) else [("p", f"Du brut au net : {_err(b)}.")])
    # 2. Frais évités
    lv = rn.get("leviers")
    B.append(("h3", SOUS_PARTIES[1]))
    if _ok(lv):
        B.append(("p", lv["phrase_frais_evites"]))
        rows = [[x["geste"], fcfa(x["une_fois"]), x.get("par_an_texte") or fcfa(x["par_an"]),
                 fcfa(x.get("premiere_annee")) if x.get("premiere_annee") is not None else "—", x["condition"],
                 x["contrepartie"]] for x in lv["frais_evites"]]
        B.append(("table", (["Geste", "Une fois", "Par an", "1re année", "Condition", "Contrepartie"], rows)))
        B.append(("h3", SOUS_PARTIES[2]))
        B.append(("ul", [f"{x['inconnue']} : {x['texte']}" for x in lv["inconnues"]]))
    else:
        B.append(("p", f"Leviers : {_err(lv)}."))
        B.append(("h3", SOUS_PARTIES[2]))
        B.append(("p", NON_CALCULE + "."))
    # 4. Ce que j'accepte de risquer
    B.append(("h3", SOUS_PARTIES[3]))
    p = rn.get("perte")
    if _ok(p):
        ch = p["chocs"]
        B.append(("p", f"Chocs par franc investi [estimé] : marché de 2018 × sensibilité du panier "
                       f"{_rg.pct(ch.get('beta'), 2) if ch.get('beta') is not None else NON_CALCULE} ; choc subi par la règle "
                       f"de référence dans son test publié {_rg.pct(ch['ref_publie'], 2)} ({ch['ref_publie_source']}, lecture "
                       f"d'un résultat publié, pas un test) ; retenu {_rg.pct(ch['retenu'], 2)} ; pire moment de 2018 "
                       f"{_rg.pct(ch.get('en_cours_d_annee'), 2) if ch.get('en_cours_d_annee') is not None else NON_CALCULE} ; "
                       f"baisse de 2017-2020 {_rg.pct(ch.get('2017_2020'), 2) if ch.get('2017_2020') is not None else NON_CALCULE}."))
        lignes = [p["choix"]] if p.get("choix") else list(p.get("table") or [])
        rows = []
        for r in lignes:
            if not r.get("en_actions") and not r.get("tout"):
                rows.append([fcfa(r.get("perte_toleree")), "0", fcfa(r.get("reserve")), r.get("message") or "", "", "", "", "", ""])
                continue
            bas, haut = (r.get("annee_2018") or [None, None])[:2]
            ao = r.get("annee_ordinaire") or {}
            rows.append(["tout" if r.get("tout") else fcfa(r["perte_toleree"]), fcfa(r["en_actions"]), fcfa(r["reserve"]),
                         f"{_s(-bas) if bas is not None else NON_CALCULE} à {_s(-haut)}",
                         _s(-r["pire_moment_2018"]) + (" (dépasse)" if (r.get("depasse") or {}).get("pire_moment") else "")
                         if r.get("pire_moment_2018") is not None else NON_CALCULE,
                         _s(-r["baisse_2017_2020"]) + (" (dépasse)" if (r.get("depasse") or {}).get("2017_2020") else "")
                         if r.get("baisse_2017_2020") is not None else NON_CALCULE,
                         f"{_s(r['reste_an1'])} ; {_s(r['reste_suivant'])}",
                         _s(ao.get("prudente")), _s(ao.get("flatteuse"))])
        B.append(("table", (["Je risque", "En actions", "En réserve", "Année comme 2018", "Pire moment de 2018",
                             "Si 2017-2020 revenait", "Dividendes moins frais (1re année ; ensuite)",
                             "Année ordinaire (prudente)", "Année ordinaire (flatteuse)"], rows)))
        B.append(("p", _rg.PH_FLATTE))
        notes = [" ".join(p.get("phrases") or [])]
        if p.get("choix") and p["choix"].get("verifie_par_ordre"):
            notes.append(f"Montant en actions vérifié par l'ordre complet ({p['choix'].get('appels')} appel(s)) : "
                         f"{fcfa(p['choix'].get('P_verifiee'))} pour une année comme 2018, frais compris.")
        if p.get("choix") and p["choix"].get("message"):
            notes.append(p["choix"]["message"])
        B.append(("ul", notes))
        rq = rn.get("risque") if _ok(rn.get("risque")) else {}
        conc = rq.get("concentration") if isinstance(rq, Mapping) else None
        if _ok(conc):
            B.append(("ul", [f"Un titre en moins (choc de {pct(conc['choc'], 0)}) : {x['nom']} {fcfa(x['perte_choc'])} "
                             f"({pct(x['pct_capital'], 1)} du capital)" for x in conc["lignes"][:4]]
                      + [f"Poids des deux premières lignes : {pct(conc['poids_deux_premieres'], 1)} ; lignes effectives "
                         f"{(conc['lignes_effectives'] or 0):.1f}".replace(".", ",")]))
    else:
        B.append(("p", f"Ce que j'accepte de risquer : {_err(p)}."))
    # 5. Où dort le reste
    B.append(("h3", SOUS_PARTIES[4]))
    r = rn.get("reserve")
    if _ok(r):
        B.append(("ul", [f"Réserve {fcfa(r['montant'])} ; taux {pct(r['taux'], 2) if r.get('taux') is not None else 'inconnu : compté à 0 %'} ; "
                         f"un point d'intérêt vaut {fcfa(r['valeur_d_un_point'])} par an ; intérêts attendus "
                         f"{fcfa(r['interets'])} [{r['mot_statut']}], montrés à part"] + list(r.get("phrases") or [])))
    else:
        B.append(("p", f"Réserve : {_err(r)}."))
    # 6. Argent qui dort et provision
    B.append(("h3", SOUS_PARTIES[5]))
    lq = rn.get("liquidites") or {}
    items = []
    for cle in ("decomposition", "argent_qui_dort", "reserve_fonctionnement", "provision", "arrondi_possible"):
        x = lq.get(cle)
        if _ok(x) and x.get("texte"):
            items.append(x["texte"])
        elif not _ok(x):
            items.append(f"{cle.replace('_', ' ')} : {_err(x)}")
    pr = lq.get("projection")
    if _ok(pr):
        items.append(f"Projection à cours constants (compte des francs, ne prévoit rien) : dividendes {fcfa(pr['dividendes_total'])} "
                     f"en {pr['n_paiements']} paiements ; liquidités moyennes {fcfa(pr['moyenne_annee_suivante'])} de février à "
                     f"janvier ; pointe {fcfa(pr['pointe'])} ; à la remise à niveau {fcfa(pr['a_la_remise_a_niveau'])} [estimé].")
    B.append(("ul", items))
    # 7. Argent placé en plus
    B.append(("h3", SOUS_PARTIES[6]))
    if _ok(lv) and lv.get("argent_place"):
        B.append(("p", lv["phrase_argent_place"]))
        rows = [[x["changement"], fcfa(x["francs"]) + (" en moyenne" if x.get("en_moyenne") else ""),
                 _s(x["dividendes"]) + " par an",
                 f"{_s(x.get('ordinaire_prudente'))} à {_s(x.get('ordinaire_flatteuse'))}",
                 f"{_s(x.get('une_sur_dix_flatteuse'))} ; {_s(x.get('une_sur_dix_prudente'))} ; {_s(x.get('une_sur_dix_periodes'))}",
                 x["nature"]] for x in lv["argent_place"]]
        B.append(("table", (["Changement", "Francs placés en plus", "Dividendes attendus [estimé]",
                             "Année ordinaire du passé (prudente à flatteuse)",
                             "Une année sur dix (flatteuse ; prudente ; périodes réelles)", "Nature"], rows)))
        B.append(("p", lv["note"] + " " + _rg.PH_FLATTE))
    else:
        B.append(("p", NON_CALCULE + "."))
    # 8. Passer l'ordre
    B.append(("h3", SOUS_PARTIES[7]))
    po = rn.get("passer_l_ordre")
    B.append(("ul", list(po["consignes"])) if _ok(po) else ("p", _err(po)))
    # 9. Points à vérifier
    B.append(("h3", SOUS_PARTIES[8]))
    al = rn.get("alertes") or []
    B.append(("ul", [(f"{a['prefixe']} : " if a.get("prefixe") else "") + str(a.get("texte")) for a in al]
              or ["Aucun point à vérifier."]))
    # Détail ligne par ligne et projection par mois
    if _ok(b) and b.get("lignes_petites"):
        B.append(("h3", "Détail ligne par ligne : frais annuels contre dividende attendu"))
        rows = [[x["symbole"], fcfa(x["frais_annuels"]), fcfa(x["dividende_net"]),
                 pct(x["rapport"], 0) if x["rapport"] is not None else "sans dividende", x["niveau"] or "—"]
                for x in b["lignes_petites"]]
        B.append(("table", (["Titre", "Frais annuels", "Dividende net attendu", "Rapport", "Niveau"], rows)))
    if _ok(pr) and pr.get("fins_de_mois"):
        B.append(("h3", "Projection des liquidités par mois (cours constants, estimation)"))
        B.append(("table", (["Mois", "Liquidités en fin de mois", "Dividendes du mois"],
                            [[k, fcfa(v), fcfa(pr["dividendes_par_mois"].get(k, 0))] for k, v in pr["fins_de_mois"].items()])))
    B.append(("banner", BANNER))
    return B


def blocs_distribution(rn: Mapping[str, Any]) -> list[Bloc]:
    """Lignes des lectures du risque (§F6) à placer sous la table de la distribution : chaque lecture (graine 0 ;
    médiane des 20 graines), périodes réelles, ``PH_PASSE``, ``PH_DESCRIPTIF``, phrase de synthèse ; la lecture
    flatteuse est suivie de ``PH_FLATTE``."""
    rq = rn.get("risque")
    if not _ok(rq):
        return [("p", f"Lectures du risque : {_err(rq)}.")]
    rows = []
    for l in rq["lectures"]:
        g0, m = l.get("graine_0") or {}, l["mediane_graines"]
        rows.append([l["nom"], f"{pct(g0.get('p_perte'))} ; {pct(m['p_perte'])}",
                     f"{pct(g0.get('mediane'), 1, signe=True)} ; {pct(m['mediane'], 1, signe=True)}",
                     f"{pct(g0.get('p10'), 1, signe=True)} ; {pct(m['p10'], 1, signe=True)}",
                     f"{pct(g0.get('p5'), 1, signe=True)} ; {pct(m['p5'], 1, signe=True)}",
                     pct(g0.get("pire"), 1, signe=True) if l["flatteuse"] else "—"])
    per = rq.get("periodes_reelles")
    if _ok(per) and per.get("disponible"):
        h = per["horizons"].get("12") or {}
        rows.append(["Périodes réellement observées", f"{h.get('n_perte')} sur {h.get('n')} ({pct(h.get('part_perte'))})", "—",
                     pct(h.get("p10"), 2, signe=True), "—", f"{pct(h.get('pire'), 1, signe=True)} (départ {h.get('pire_depart')})"])
    B: list[Bloc] = [("h3", "Lectures du risque : plusieurs lectures d'un seul passé"),
                     ("table", (["Lecture", "Périodes en perte (graine 0 ; médiane des graines)", "Année ordinaire",
                                 "Une année sur dix", "Une année sur vingt", "Pire tirage"], rows)),
                     ("p", f"{_rg.PH_PASSE} {_rg.PH_DESCRIPTIF} " + str((rq.get("synthese") or {}).get("phrase") or "")),
                     ("p", _rg.PH_FLATTE),
                     ("p", f"Libellé : « {rq.get('libelle_p_battre_tr')} »." if rq.get("libelle_p_battre_tr") else "")]
    return [x for x in B if x[1]]


def sous_blocs_rapport(rn: Mapping[str, Any]) -> dict[str, list[Bloc]]:
    """Sous-blocs du rapport HTML (§7.2), à ajouter **à la fin** des sections existantes : ``bandeau`` (carte « Mon
    plan »), ``ordre``, ``revenus``, ``distribution``, ``risques``, ``methode``. Chaque sous-bloc porte ``BANNER``."""
    sec = blocs_section(rn)

    def part(titre: str, suivant: str | None) -> list[Bloc]:
        try:
            i = sec.index(("h3", titre))
        except ValueError:
            return []
        j = sec.index(("h3", suivant)) if suivant and ("h3", suivant) in sec else len(sec) - 1
        return sec[i:j]

    banner: list[Bloc] = [("banner", BANNER)]
    out = {
        "bandeau": [("h3", "Mon plan")] + [("p", "Carte « Mon plan » : voir plan.rendre_plan (forme écran).")] + banner,
        "ordre": part(SOUS_PARTIES[5], SOUS_PARTIES[6]) + part(SOUS_PARTIES[7], SOUS_PARTIES[8]) + banner,
        "revenus": part(SOUS_PARTIES[0], SOUS_PARTIES[1]) + part(SOUS_PARTIES[1], SOUS_PARTIES[2])
                   + part(SOUS_PARTIES[2], SOUS_PARTIES[3]) + part(SOUS_PARTIES[6], SOUS_PARTIES[7]) + banner,
        "distribution": blocs_distribution(rn) + banner,
        "risques": part(SOUS_PARTIES[3], SOUS_PARTIES[4]) + banner,
        "methode": [("h3", "Rendement net et pertes : statut des chiffres et limites"),
                    ("ul", ["Chaque montant porte son statut : compté (Fait), estimé (Estimation), supposé (Hypothèse).",
                            _rg.PH_DESCRIPTIF, _rg.PH_PASSE, _rg.PH_INTERETS, _rg.PH_ESSAI])] + banner,
    }
    return out


def fragment(blocs: Sequence[Bloc], fmt: str = "md") -> str:
    """Rendu d'une liste de blocs avec le moteur de rendu de l'ordre de bataille (``md`` ou ``html``) ; le HTML est un
    fragment ``<section>`` sans ressource externe."""
    return R._render(list(blocs), "md" if fmt == "md" else "html")
