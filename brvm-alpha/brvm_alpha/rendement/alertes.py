"""F8 — Avertissements de fuite dans l'ordre ; F11 — trois feux, vie d'une alerte, prix des décisions.

Cahier ``docs/RENDEMENT_NET.md``, §F8 et §F11. L'outil parle quand une fuite devient lourde. Un feu ouvre une
**revue**, jamais une vente : aucune fonction de ce module ne produit d'ordre. Les seuils (``configs/rendement_net.yaml``)
ont été choisis après lecture de la période 2022-2026, sans base statistique ; leur utilité est inconnue.

* :func:`alertes_fuite` : W1 à W9 (toutes dans ``rendement_net.alertes``) ;
* :func:`avertissements` : trois au plus, avec leur préfixe (« FUITE : » ou « À VÉRIFIER : »), à placer **à la fin**
  de la liste ``avertissements`` de l'ordre (les informations n'y entrent jamais) ;
* :func:`feux` : feux « Perte », « Fuites », « Données » d'une semaine du journal ;
* :func:`ouvrir`, :func:`marquer_revue`, :func:`clore` : vie d'une alerte (ouverte → revue faite → close ; elle ne
  se rouvre qu'au palier suivant) ;
* :func:`lignes_a_revoir`, :func:`prix_des_decisions` : « à revoir, pas à vendre » et le prix de chaque décision.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd

from brvm_alpha.rendement import grille as _gr
from brvm_alpha.rendement import reglages as _rg
from brvm_alpha.rendement.reglages import R

__all__ = ["AVERTISSEMENT_SEUILS", "PRIORITE", "QUESTIONS_REVUE", "alertes_fuite", "avertissements", "clore", "feux",
           "lignes_a_revoir", "marquer_revue", "ouvrir", "prix_des_decisions", "ventes_ineligibles"]

FUITE, VERIFIER = "FUITE", "À VÉRIFIER"
AVERTISSEMENT_SEUILS = ("Seuils choisis après lecture de la période 2022-2026, sans base statistique. Leur utilité est "
                        "inconnue. Ils sonneraient plus souvent en marché baissier.")
#: Ordre de priorité des alertes du module dans la liste ``avertissements`` (§F8, placement).
PRIORITE = ("W7", "W9", "W1_fort", "W4_fuite", "W5", "W6", "W1_orange")
QUESTIONS_REVUE = [
    "1. La baisse vient-elle du marché ou du titre ?",
    "2. Une note, un filtre de risque ou une publication l'explique-t-il ?",
    "3. Le dividende attendu est-il menacé ?",
    "4. Votre besoin d'argent ou votre durée ont-ils changé ?",
    "5. Décision : garder ; ne plus acheter ; réduire par ordres à cours limité sur plusieurs séances.",
]
QUESTION_PERTE_ROUGE = "Ce que vous acceptez de risquer est-il toujours le bon montant ?"


def _a(code: str, niveau: str, prefixe: str | None, texte: str, cause: str = "", **valeurs: Any) -> dict[str, Any]:
    return {"code": code, "niveau": niveau, "prefixe": prefixe, "texte": texte, "cause": cause, "valeurs": valeurs}


# ---------------------------------------------------------------------------
# F8 — alertes de l'ordre
# ---------------------------------------------------------------------------


def ventes_ineligibles(ordre: Any, forced_exits: Mapping[str, str] | None = None) -> list[str]:
    """Ventes proposées pour inéligibilité : ``forced_exits`` du modèle (motif « inéligible »), motif de la ligne, ou
    message du modèle « SYM (inéligible … »."""
    o = _rg.en_dict(ordre)
    msgs = " ".join(str(m) for m in (o.get("messages_modele") or []))
    expl = {str(e.get("symbole")): str(e.get("texte") or "") + " " + str(e.get("statut") or "")
            for e in (o.get("explications") or [])}
    out = []
    for l in o.get("lignes") or []:
        if l.get("sens") != "vente" or int(l.get("quantite") or 0) <= 0:
            continue
        s = str(l["symbole"])
        motif = str((forced_exits or {}).get(s, ""))
        if ("inéligib" in motif or "ineligib" in motif or "inéligib" in str(l.get("note") or "")
                or f"{s} (inéligib" in msgs or "inéligib" in expl.get(s, "")):
            out.append(s)
    return out


def _trou_de_bulletins(sessions: Any, t: pd.Timestamp, fenetre: int) -> dict[str, Any] | None:
    if sessions is None:
        return None
    s = sessions if isinstance(sessions, pd.DataFrame) else None
    if s is None or "available" not in s.columns or "date" not in s.columns:
        return None
    s = s.assign(date=pd.to_datetime(s["date"])).sort_values("date")
    s = s[s["date"] <= t].tail(int(fenetre))
    manq = s[~s["available"].astype(bool)]
    return {"n": int(len(manq)), "du": manq["date"].min() if len(manq) else None,
            "au": manq["date"].max() if len(manq) else None}


def alertes_fuite(ordre: Any, rendement_net: Mapping[str, Any] | None = None, grille: _gr.GrilleSGI | None = None,
                  panels: Mapping[str, Any] | None = None, *, sessions: Any = None, holdings_fournis: bool | None = None,
                  cash_fourni: bool | None = None, memoire: Mapping[str, Any] | None = None, completer: bool = False,
                  forced_exits: Mapping[str, str] | None = None, reglages: Mapping[str, Any] | None = None,
                  costs: Any = None) -> list[dict[str, Any]]:
    """Alertes W1 à W9 (§F8). ``rendement_net`` : blocs déjà calculés (bilan, liquidités) ; à défaut ils sont
    recalculés. ``sessions`` : table ``sessions`` du panel (``date``, ``available``) pour W7 ; ``holdings_fournis`` et
    ``cash_fourni`` : ce que l'appelant a passé à ``recommend`` (W8, W9)."""
    from brvm_alpha.rendement import bilan as _bi
    from brvm_alpha.rendement import liquidites as _lq

    o = _rg.en_dict(ordre)
    rn = dict(rendement_net or {})
    out: list[dict[str, Any]] = []
    seuils = [float(x) for x in _rg.lire(reglages, "frais.seuils_frais_annuels_sur_dividendes", [0.15, 0.5, 1.0])]
    b = rn.get("bilan") if isinstance(rn.get("bilan"), Mapping) and "totaux" in rn.get("bilan", {}) else None
    if b is None:
        b = _bi.bilan_fuites(o, grille, reglages=reglages, costs=costs)
    t = b["totaux"]
    ann, N = int(t["annuels"]), int(t["dividendes_nets"])
    supp = _gr.statut_global(grille) == _gr.SUPPOSE
    mot = " [supposé]" if supp else ""
    # W1
    if N > 0:
        r = ann / N
        if r >= seuils[2]:
            out.append(_a("W1", "critique", FUITE,
                          f"Les frais annuels ({_rg.fcfa(ann)}) dépassent les dividendes nets attendus ({_rg.fcfa(N)}). À "
                          f"cours inchangés, ce portefeuille perd {_rg.fcfa(ann - N, unite=False)} FCFA par an.",
                          "frais annuels", ratio=r, frais_annuels=ann, dividendes_nets=N))
        elif r >= seuils[1]:
            out.append(_a("W1", "rouge", FUITE, f"Les frais annuels du courtier ({_rg.fcfa(ann)}) prennent "
                          f"{_rg.pct(r, 0)} des dividendes nets attendus ({_rg.fcfa(N)}){mot}.", "frais annuels",
                          ratio=r, frais_annuels=ann, dividendes_nets=N))
        elif r >= seuils[0]:
            out.append(_a("W1", "orange", FUITE, f"Les frais annuels du courtier ({_rg.fcfa(ann)}) prennent "
                          f"{_rg.pct(r, 0)} des dividendes nets attendus ({_rg.fcfa(N)}){mot}.", "frais annuels",
                          ratio=r, frais_annuels=ann, dividendes_nets=N))
    else:
        K = float(o.get("capital") or 0)
        s_cap = float(_rg.lire(reglages, "frais.seuil_frais_annuels_sur_capital", 0.01))
        if K > 0 and ann / K > s_cap:
            out.append(_a("W1", "critique", FUITE, f"Les frais annuels ({_rg.fcfa(ann)}) dépassent {_rg.pct(s_cap, 0)} du "
                          "capital, sans dividende attendu.", "frais annuels", ratio=ann / K, frais_annuels=ann,
                          dividendes_nets=0))
    # W2
    if supp:
        fr = int(t["frais_an1"])
        sf = int(t["supposee_frais_fcfa"])
        out.append(_a("W2", "information", None,
                      f"Tarif non vérifié : {_rg.pct(sf / fr if fr else 0, 0)} des frais de la 1re année sont supposés ou "
                      f"estimés ({_rg.fcfa(sf, unite=False)} sur {_rg.fcfa(fr)}). Envoyez les 8 questions à votre courtier.",
                      "tarif supposé", supposes=sf, frais_an1=fr))
    # W3
    rouges = [x for x in b.get("lignes_petites") or [] if x.get("niveau") == "rouge"]
    if rouges:
        lst = ", ".join(f"{x['symbole']} ({_rg.fcfa(x['frais_annuels'], unite=False)} de frais pour "
                        f"{_rg.fcfa(x['dividende_net'], unite=False)} de dividende)" for x in rouges[:6])
        plus = f" et {len(rouges) - 6} autres" if len(rouges) > 6 else ""
        out.append(_a("W3", "orange", FUITE, f"{len(rouges)} ligne(s) coûtent plus qu'elles ne versent en dividendes, "
                      f"en FCFA par an{mot} : {lst}{plus}.", "frais par ligne", lignes=[x["symbole"] for x in rouges]))
    # W4
    aqd = rn.get("liquidites", {}).get("argent_qui_dort") if isinstance(rn.get("liquidites"), Mapping) else None
    if not isinstance(aqd, Mapping) or "D" not in aqd:
        aqd = _lq.argent_qui_dort(o, memoire=memoire, panels=panels, reglages=reglages)
    seuil = float(_rg.lire(reglages, "liquidites.seuil_argent_qui_dort_fcfa", 100_000))
    if float(aqd.get("D_hors_regle") or 0) >= seuil:
        causes = [c for c in aqd.get("causes") or [] if not c.get("prevu")]
        cause = max(causes, key=lambda c: c["montant"])["cause"] if causes else "inconnue"
        out.append(_a("W4", "orange", FUITE, f"Argent qui dort hors de la règle testée : {_rg.fcfa(aqd['D_hors_regle'])} "
                      f"(cause : {cause}).", cause, D=aqd["D"], D_hors_regle=aqd["D_hors_regle"]))
    elif float(aqd.get("D") or 0) >= seuil:
        prev = [c for c in aqd.get("causes") or [] if c.get("prevu")]
        cause = max(prev, key=lambda c: c["montant"])["cause"] if prev else "règle testée"
        out.append(_a("W4", "information", None, f"Argent qui dort : {_rg.fcfa(aqd['D'])}, prévu par la règle testée "
                      f"({cause}).", cause, D=aqd["D"], D_hors_regle=aqd.get("D_hors_regle")))
    # W5
    prov = (rn.get("liquidites") or {}).get("provision") if isinstance(rn.get("liquidites"), Mapping) else None
    if not isinstance(prov, Mapping) or "marge_courtage_plus_cher" not in prov:
        prov = _lq.provision_entree(o, costs, reglages=reglages)
    if int(prov["marge_courtage_plus_cher"]) < 0:
        out.append(_a("W5", "orange", VERIFIER, f"Marge du pire cas trop mince : avec un courtage plus cher de "
                      f"{_rg.pct(prov['surcout_courtage_test'], 1)[:-2]} point, il manquerait "
                      f"{_rg.fcfa(-int(prov['marge_courtage_plus_cher']))} pour payer l'ordre au prix limite. Gardez plus de "
                      "liquidités ou vérifiez votre tarif.", "marge du pire cas", marge=prov["marge_courtage_plus_cher"]))
    # W6
    if grille is not None and grille.valeur("courtage_min_par_ordre") > 0 and grille.valeur("courtage") > 0:
        F = grille.valeur("courtage_min_par_ordre")
        seuil_t = F / grille.valeur("courtage")
        cm, _f = _gr.vers_cost_model(grille, _gr.cost_model_de(o, costs))
        cm0 = R.replace_costs(cm, min_ticket_fcfa=0.0)
        sur = 0
        n_tr = 0
        for l in o.get("lignes") or []:
            if l.get("sens") not in ("achat", "vente"):
                continue
            for q in l.get("tranches") or []:
                a = int(q) * float(l["cours_reference"])
                if 0 < a < seuil_t:
                    n_tr += 1
                    sur += R.fee_breakdown(a, cm)["explicites"] - R.fee_breakdown(a, cm0)["explicites"]
        if n_tr:
            out.append(_a("W6", "orange", FUITE, f"{n_tr} tranche(s) d'ordre sous le minimum du courtier "
                          f"({_rg.fcfa(F)} par ordre) : surcoût de {_rg.fcfa(sur)}.", "minimum par ordre", surcout=int(sur),
                          tranches=n_tr))
    # W7
    vi = ventes_ineligibles(o, forced_exits)
    if vi:
        fen = int(_rg.lire(reglages, "feux.fenetre_trou_seances", 126))
        tdec = pd.Timestamp(o.get("asof")).normalize() if o.get("asof") else None
        sess = sessions if sessions is not None else (panels.get("sessions") if isinstance(panels, Mapping) else None)
        trou = _trou_de_bulletins(sess, tdec, fen) if tdec is not None else None
        if trou is None:
            out.append(_a("W7", "rouge", VERIFIER, "Vente proposée pour inéligibilité ("
                          + ", ".join(vi) + ") : bulletins manquants non vérifiables (table des séances absente).",
                          "bulletins manquants non vérifiables", ventes=vi))
        elif trou["n"] > 0:
            out.append(_a("W7", "rouge", VERIFIER, f"Ne vendez pas à cause d'un trou de données : {trou['n']} bulletins "
                          f"manquent entre le {trou['du']:%d/%m} et le {trou['au']:%d/%m}. Ventes concernées : "
                          + ", ".join(vi) + ".", "bulletins manquants", ventes=vi, n=trou["n"]))
    # W8, W9
    holds = holdings_fournis if holdings_fournis is not None else any(int(l.get("detenus") or 0) > 0 for l in (o.get("lignes") or []))
    if holds and not memoire and not completer:
        out.append(_a("W8", "information", None, "Hors remise à niveau de janvier, la règle testée ne propose aucun ordre. "
                      "Cet ordre est recalculé : écart à la règle testée. Option --suivi.", "portefeuille sans mémoire"))
    if holds and cash_fourni is False:
        out.append(_a("W9", "orange", VERIFIER, "Liquidités prises égales à capital − titres : les frais déjà payés sont "
                      "comptés comme disponibles. Donnez vos liquidités réelles (option --cash).", "liquidités non données"))
    return out


def _cle_priorite(a: Mapping[str, Any]) -> str | None:
    c, n, p = a.get("code"), a.get("niveau"), a.get("prefixe")
    if c == "W1":
        return "W1_fort" if n in ("rouge", "critique") else ("W1_orange" if n == "orange" else None)
    if c == "W4":
        return "W4_fuite" if p == FUITE else None
    if c in ("W5", "W6", "W7", "W9"):
        return c
    return None


def avertissements(alertes: Iterable[Mapping[str, Any]], n_max: int = 3) -> list[str]:
    """Avertissements à ajouter **à la fin** de la liste existante de l'ordre : trois au plus, avec leur préfixe,
    dans l'ordre W7, W9, W1 rouge ou critique, W4 « FUITE », W5, W6, W1 orange. Les informations (W2, W4 sans préfixe,
    W8) n'y entrent jamais."""
    cand = []
    for a in alertes:
        k = _cle_priorite(a)
        if k is not None and a.get("prefixe"):
            cand.append((PRIORITE.index(k), f"{a['prefixe']} : {a['texte']}"))
    cand.sort(key=lambda x: x[0])
    return [t for _i, t in cand[: int(n_max)]]


# ---------------------------------------------------------------------------
# F11 — vie d'une alerte
# ---------------------------------------------------------------------------


def _jour(x: Any) -> _dt.date:
    return _rg._date(x)


def ouvrir(alertes: list[dict[str, Any]], cle: str, palier: int, date: Any, *, feu: str = "", niveau: str = "orange",
           texte: str = "") -> dict[str, Any] | None:
    """Ouvre une alerte (``ouverte``) pour ``cle`` au ``palier`` donné, ou rend l'alerte déjà ouverte. Une alerte
    revue ou close ne se rouvre qu'au **palier suivant** : ``None`` si le palier n'est pas plus haut. La liste
    ``alertes`` est complétée sur place (le carnet du suivi la rend durable)."""
    mem = [a for a in alertes if a.get("cle") == cle]
    if mem:
        der = mem[-1]
        if der["etat"] == "ouverte":
            if int(palier) > int(der["palier"]):
                der.update({"palier": int(palier), "niveau": niveau})
            return der
        if int(palier) <= int(der["palier"]):
            return None
    d = _jour(date)
    ident = hashlib.sha256(f"{cle}|{palier}|{d.isoformat()}".encode()).hexdigest()[:12]
    a = {"id": ident, "cle": cle, "feu": feu, "palier": int(palier), "niveau": niveau, "etat": "ouverte",
         "ouverte_le": d.isoformat(), "revue_le": None, "close_le": None, "decision": None, "texte": texte}
    alertes.append(a)
    return a


def marquer_revue(alerte: dict[str, Any], date: Any, decision: str, reponses: Sequence[str] | None = None) -> dict[str, Any]:
    """``ouverte`` → ``revue faite le jj/mm`` (décision écrite). Aucune décision ne crée d'ordre."""
    if decision not in ("garder", "ne-plus-acheter", "ne plus acheter", "reduire", "réduire"):
        raise ValueError("décision : garder, ne plus acheter ou réduire")
    alerte.update({"etat": "revue faite", "revue_le": _jour(date).isoformat(), "decision": decision,
                   "reponses": list(reponses or [])})
    return alerte


def clore(alerte: dict[str, Any], date: Any) -> dict[str, Any]:
    """Alerte close ; elle ne se rouvre qu'au palier suivant (:func:`ouvrir`)."""
    alerte.update({"etat": "close", "close_le": _jour(date).isoformat()})
    return alerte


# ---------------------------------------------------------------------------
# F11 — trois feux
# ---------------------------------------------------------------------------


def _palier(p: float, bornes: Sequence[float]) -> int:
    k = 0
    for i, b in enumerate(bornes, start=1):
        if p >= b - 1e-9:
            k = i
    return k


def _affichage(etat: str, alertes: Sequence[Mapping[str, Any]] | None, feu: str, jour: _dt.date | None,
               rappel_jours: int) -> tuple[str, str | None]:
    if etat in ("vert", "—"):
        return etat.upper() if etat == "vert" else "—", None
    lib = etat.upper()
    rappel = None
    for a in reversed(list(alertes or [])):
        if a.get("feu") != feu:
            continue
        if a.get("etat") == "revue faite" and a.get("revue_le"):
            return f"{lib} — revue faite le {_jour(a['revue_le']):%d/%m}", None
        if a.get("etat") == "ouverte" and etat == "rouge" and jour is not None and a.get("ouverte_le"):
            if (jour - _jour(a["ouverte_le"])).days >= rappel_jours:
                rappel = f"Rappel : alerte rouge sans revue depuis le {_jour(a['ouverte_le']):%d/%m}."
        break
    return lib, rappel


def feux(semaine: Mapping[str, Any] | None, plan: Mapping[str, Any] | None = None,
         declaration: Mapping[str, Any] | None = None, alertes_ouvertes: Sequence[Mapping[str, Any]] | None = None, *,
         reglages: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Trois feux d'une semaine du journal (§F11) : « Perte », « Fuites », « Données ». Vert : rien à faire ; orange :
    une revue ; rouge : une décision écrite. Aucun feu ne vend.

    ``semaine`` (ligne du journal, clés lues si présentes) : ``valeur``, ``argent_engage``, ``argent_engage_actions``,
    ``papier``, ``avis`` (liste de ``{frais_lus, frais_prevus}``), ``argent_qui_dort``, ``argent_qui_dort_prevu``,
    ``seances_argent_qui_dort_au_dela``, ``ordres_expires``, ``dividendes_non_credites``, ``liquidites``,
    ``prochain_prelevement``, ``w1_critique``, ``bulletins_manquants``, ``retard_journal_jours``, ``chaine_rompue``,
    ``passe_a_change``, ``ordre_contredit_decision``, ``date``. ``plan`` : ``perte_toleree`` (X).
    ``declaration`` : ``chaine_ok``. Sans journal : feux « — », « le suivi n'a pas commencé »."""
    base = {"avertissement": AVERTISSEMENT_SEUILS, "phrase": _rg.PH_REVUE}
    if not semaine:
        vide = {"etat": "—", "affichage": "—", "phrase": "le suivi n'a pas commencé", "conditions": []}
        return {**base, "perte": dict(vide), "fuites": dict(vide), "donnees": dict(vide), "suivi_commence": False}
    s = semaine
    jour = _jour(s["date"]) if s.get("date") else None
    rappel_j = int(_rg.lire(reglages, "feux.rappel_rouge_jours", 14))
    # Perte
    V, K = float(s.get("valeur") or 0), float(s.get("argent_engage") or 0)
    p = max(0.0, K - V)
    X = (plan or {}).get("perte_toleree")
    if X:
        X = float(X)
        bornes = [float(b) * X for b in _rg.lire(reglages, "feux.perte_paliers", [0.5, 1.0, 1.5, 2.0])]
        pal = _palier(p, bornes)
        etat_p = "vert" if pal == 0 else ("orange" if pal == 1 else "rouge")
        ph = (f"{_rg.fcfa(p)} sous l'argent engagé. Vous avez accepté de risquer {_rg.fcfa(X)}. Une année comme 2018 "
              "dépasse ce montant en cours d'année.")
    else:
        Ka = float(s.get("argent_engage_actions") or K)
        bornes = [float(b) * Ka for b in _rg.lire(reglages, "feux.perte_sans_choix", [0.10, 0.20])]
        pal = _palier(p, bornes)
        etat_p = "vert" if pal == 0 else ("orange" if pal == 1 else "rouge")
        ph = f"{_rg.fcfa(p)} sous l'argent engagé. Aucun montant accepté n'est choisi : paliers à 10 % et 20 % de l'argent en actions."
    aff, rap = _affichage(etat_p, alertes_ouvertes, "perte", jour, rappel_j)
    perte = {"etat": etat_p, "affichage": aff, "phrase": ph, "palier": pal, "perte_en_cours": int(R.round_fcfa(p)),
             "rappel": rap, "questions": QUESTIONS_REVUE + ([QUESTION_PERTE_ROUGE] if etat_p == "rouge" else [])}
    # Fuites
    cond: list[str] = []
    rouge: list[str] = []
    e_f, e_p = float(_rg.lire(reglages, "feux.frais_ecart_fcfa", 1000)), float(_rg.lire(reglages, "feux.frais_ecart_part", 0.05))
    if s.get("papier"):
        cond.append("(a) frais lus sur avis d'opéré : sans objet (papier)")
    else:
        for av in s.get("avis") or []:
            lu, prevu = float(av.get("frais_lus") or 0), float(av.get("frais_prevus") or 0)
            if lu - prevu > e_f and (prevu <= 0 or (lu - prevu) / prevu > e_p):
                cond.append(f"(a) frais lus {_rg.fcfa(lu)} pour {_rg.fcfa(prevu)} prévus par la grille")
                break
    ecart = float(s.get("argent_qui_dort") or 0) - float(s.get("argent_qui_dort_prevu") or 0)
    if ecart > float(_rg.lire(reglages, "feux.argent_qui_dort_ecart_fcfa", 100_000)) and \
            int(s.get("seances_argent_qui_dort_au_dela") or 0) > int(_rg.lire(reglages, "liquidites.delai_argent_qui_dort_seances", 20)):
        cond.append(f"(b) argent qui dort {_rg.fcfa(ecart)} au-delà de ce que la règle déclarée prévoit")
    if int(s.get("ordres_expires") or 0) > 0:
        cond.append(f"(c) {int(s['ordres_expires'])} ordre(s) non servi(s) expiré(s) après 10 séances")
    ndc = s.get("dividendes_non_credites")
    if ndc:
        cond.append(f"(d) dividende non crédité 30 jours après son avis de paiement : {ndc if isinstance(ndc, str) else len(ndc) if isinstance(ndc, (list, tuple)) else ndc}")
    if s.get("prochain_prelevement") is not None and s.get("liquidites") is not None and \
            float(s["liquidites"]) < float(s["prochain_prelevement"]):
        rouge.append("les liquidités ne couvrent pas le prochain prélèvement de frais fixes")
    if s.get("w1_critique"):
        rouge.append("frais annuels supérieurs aux dividendes attendus")
    reel = [c for c in cond if "sans objet" not in c]
    etat_f = "rouge" if rouge else ("orange" if reel else "vert")
    aff, rap = _affichage(etat_f, alertes_ouvertes, "fuites", jour, rappel_j)
    fuites = {"etat": etat_f, "affichage": aff, "conditions": cond + rouge, "rappel": rap,
              "phrase": "; ".join(rouge + reel) if (rouge or reel) else "aucune fuite au-delà de ce que la règle prévoit"}
    # Données
    bm = int(s.get("bulletins_manquants") or 0)
    o_b = int((_rg.lire(reglages, "feux.bulletins_manquants", {}) or {}).get("orange", 1))
    r_b = int((_rg.lire(reglages, "feux.bulletins_manquants", {}) or {}).get("rouge", 3))
    dr: list[str] = []
    do: list[str] = []
    if bm >= r_b:
        dr.append(f"{bm} bulletins manquants : aucun ordre de vente ne doit partir")
    elif bm >= o_b:
        do.append(f"{bm} bulletin(s) manquant(s) dans la semaine")
    if int(s.get("retard_journal_jours") or 0) > int(_rg.lire(reglages, "feux.retard_journal_jours", 9)):
        do.append(f"journal en retard de {int(s['retard_journal_jours'])} jours")
    if s.get("chaine_rompue") or (declaration is not None and declaration.get("chaine_ok") is False):
        dr.append("chaîne du journal ou de la déclaration rompue")
    if s.get("passe_a_change"):
        dr.append("le passé a changé")
    if s.get("ordre_contredit_decision"):
        dr.append("un ordre proposé contredit une décision déclarée")
    etat_d = "rouge" if dr else ("orange" if do else "vert")
    aff, rap = _affichage(etat_d, alertes_ouvertes, "donnees", jour, rappel_j)
    donnees = {"etat": etat_d, "affichage": aff, "conditions": dr + do, "rappel": rap,
               "phrase": "; ".join(dr + do) if (dr or do) else "données à jour"}
    return {**base, "perte": perte, "fuites": fuites, "donnees": donnees, "suivi_commence": True}


# ---------------------------------------------------------------------------
# F11 — lignes à revoir, prix des décisions
# ---------------------------------------------------------------------------


def lignes_a_revoir(etat: Mapping[str, Any], plan: Mapping[str, Any] | None = None, *,
                    reglages: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    """« À revoir, pas à vendre » (§F11). ``etat["lignes"]`` : ``symbole``, ``baisse_depuis_achat`` (part,
    dividendes compris : un détachement n'allume rien), ``perte_ligne`` (FCFA), ``ecart_marche_63`` (rendement contre le
    marché sur 63 séances), ``frais_annuels``, ``dividende_attendu`` ; ``etat["valeur"]``. L1 : baisse ≥ 25 % (paliers
    35 %, 45 %) ; L2 : perte de la ligne ≥ 10 % de X (sans choix : ≥ 1 % de V) ; L3 : −25 % contre le marché en
    63 séances ; L4 : la ligne coûte plus qu'elle ne rapporte en dividendes."""
    pal = [float(x) for x in _rg.lire(reglages, "feux.ligne_baisse_paliers", [0.25, 0.35, 0.45])]
    X = (plan or {}).get("perte_toleree")
    V = float(etat.get("valeur") or 0)
    seuil_l2 = float(_rg.lire(reglages, "feux.ligne_part_perte", 0.10)) * float(X) if X else \
        float(_rg.lire(reglages, "feux.ligne_part_perte_sans_choix", 0.01)) * V
    out = []
    for l in etat.get("lignes") or []:
        motifs = []
        b = float(l.get("baisse_depuis_achat") or 0)
        k = _palier(b, pal)
        if k:
            motifs.append(f"L1 : baisse de {_rg.pct(b, 0)} depuis l'achat, dividendes compris (palier {k})")
        pl = float(l.get("perte_ligne") or 0)
        if seuil_l2 > 0 and pl >= seuil_l2:
            motifs.append(f"L2 : perte de la ligne {_rg.fcfa(pl)}")
        if l.get("ecart_marche_63") is not None and float(l["ecart_marche_63"]) <= -0.25:
            motifs.append("L3 : −25 % contre le marché en 63 séances")
        if l.get("frais_annuels") is not None and l.get("dividende_attendu") is not None and \
                float(l["frais_annuels"]) >= float(l["dividende_attendu"]):
            motifs.append("L4 : la ligne coûte plus qu'elle ne verse en dividendes")
        if motifs:
            out.append({"symbole": l["symbole"], "motifs": motifs, "palier_baisse": k, "a_vendre": False})
    return out


def prix_des_decisions(etat: Mapping[str, Any], symbole: str, costs: Any = None) -> dict[str, Any]:
    """Prix de chaque décision, affiché avant la réponse (§F11). ``etat["lignes"]`` : ``symbole``, ``titres``,
    ``cours``, ``prix_de_revient``, ``dividende_attendu``, ``demi_spread_pct``, ``mdv63``.

    Garder : 0 FCFA de frais, on reste exposé ; ne plus acheter : 0 FCFA ; réduire ou vendre : frais de sortie +
    perte réalisée + dividende attendu abandonné ; racheter plus tard : un aller-retour (deux fois les frais d'achat)."""
    from brvm_alpha.config import CostModel

    cm = costs if isinstance(costs, CostModel) else CostModel()
    l = next((x for x in etat.get("lignes") or [] if str(x.get("symbole")) == str(symbole)), None)
    if l is None:
        raise ValueError(f"{symbole} : ligne absente de l'état du portefeuille")
    q, px = int(l.get("titres") or 0), float(l.get("cours") or 0)
    hs = float(l.get("demi_spread_pct") or 0.0)
    mdv = l.get("mdv63")
    sortie = R.order_costs(q, px, cm, side="vente", half_spread=hs, mdv63=mdv)["total"] if q > 0 else 0
    achat = R.order_costs(q, px, cm, side="achat", half_spread=hs, mdv63=mdv)["total"] if q > 0 else 0
    pr = l.get("prix_de_revient")
    realise = int(R.round_fcfa(q * (px - float(pr)))) if pr is not None else None
    div = int(l.get("dividende_attendu") or 0)
    return {"symbole": symbole, "phrase": _rg.PH_REVUE,
            "garder": {"frais": 0, "texte": "0 FCFA de frais ; on reste exposé"},
            "ne_plus_acheter": {"frais": 0, "texte": "0 FCFA ; la ligne s'écarte de son poids"},
            "reduire_ou_vendre": {"frais_sortie": int(sortie), "resultat_realise": realise, "dividende_abandonne": div,
                                  "aller_retour": int(2 * achat), "frais_achat_equivalent": int(achat),
                                  "texte": f"frais de sortie {_rg.fcfa(sortie)} ; résultat réalisé "
                                           f"{_rg.fcfa(realise, signe=True) if realise is not None else 'non calculé'} ; "
                                           f"dividende attendu abandonné {_rg.fcfa(div)} ; si l'on rachète plus tard : un "
                                           f"aller-retour de {_rg.fcfa(2 * achat)}"}}
