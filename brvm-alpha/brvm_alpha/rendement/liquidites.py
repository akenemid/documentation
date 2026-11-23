"""F7 — Argent qui dort, provision d'entrée, « passer l'ordre » ; F13c — arrondi « plus forts restes ».

Cahier ``docs/RENDEMENT_NET.md``, §F7 et §F13c. Le module dit combien d'argent ne travaille pas, pourquoi et
jusqu'à quand ; la provision à avoir sur le compte avant l'ordre ; comment passer un ordre à cours limité.

* :func:`decomposition` : ``liquidités après = liquidités initiales − achats nets + ventes nettes`` (identité au
  franc) ;
* :func:`argent_qui_dort` : ``D = liquidités après les ordres proposés − 2 % × V``, chaque franc rangé dans une cause
  « prévue par la règle testée » ou « non prévue » ;
* :func:`projection` : compte des francs à cours constants (ne prévoit rien) ; elle suit la règle testée et sert de
  référence au feu « Fuites » ;
* :func:`provision_entree` : provision du pire cas, part investie maximale ``1 ÷ (ρ × (1 + τ))`` ;
* :func:`arrondi_restes` : algorithme de F13c. Information par défaut (« sans l'appliquer ») ; l'appliquer est un
  **écart à la règle testée** (option ``--arrondi restes``, éteinte par défaut, déclarée E-A).

Des francs placés ne sont pas des francs gagnés : gain ou perte selon le marché.
"""

from __future__ import annotations

import datetime as _dt
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd

from brvm_alpha.rendement import grille as _gr
from brvm_alpha.rendement import reglages as _rg
from brvm_alpha.rendement.reglages import ESTIMATION, FAIT, HYPOTHESE, R

__all__ = ["CONSIGNES", "argent_qui_dort", "arrondi_restes", "carnet_de_cloture", "compte_carnet", "consignes",
           "decomposition", "dividendes_depuis_janvier", "projection", "projection_detenus", "provision_entree",
           "reserve_fonctionnement"]

AES = ("BF", "ML", "NE")
CONSIGNES = [
    "Vos ordres sont à cours limité. Certaines lignes peuvent ne pas être servies le jour même, ou seulement en partie.",
    "Horaires (heure d'Abidjan) : saisie avant l'ouverture de 9 h 00 à 9 h 45 ; cotation en continu jusqu'à 14 h 00 ; "
    "fixing de clôture à 14 h 30 ; négociation au dernier cours jusqu'à 15 h 00.",
    "Demandez une validité de plusieurs séances (10 au plus). La plate-forme réévalue ensuite.",
    "Le jour d'un détachement de dividende ou d'une division, la BRVM annule les ordres en attente : il faut les ressaisir.",
    "Le produit d'une vente n'est disponible que deux jours de bourse plus tard.",
    "Après quelques séances, relancez la commande avec ce que vous détenez vraiment.",
]


def _ts(x: Any) -> pd.Timestamp | None:
    try:
        return None if x is None else pd.Timestamp(x).normalize()
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# (a) Décomposition
# ---------------------------------------------------------------------------


def decomposition(ordre: Any) -> dict[str, Any]:
    """``liquidités après = liquidités initiales − achats nets + ventes nettes`` ; pour un premier achat :
    ``(V − cible investie) + reliquat d'arrondi − frais d'achat`` (à 10 M : 200 000 + 149 440 − 160 588 =
    188 852 FCFA). Écart d'identité rendu au franc."""
    o = _rg.en_dict(ordre)
    c = o.get("couts") or {}
    L0 = float(o.get("liquidites_initiales") or 0)
    V = float(o.get("valeur_portefeuille") or 0)
    an, vn = int(c.get("achats_net") or 0), int(c.get("ventes_net") or 0)
    apres = int(c.get("liquidites_apres") or 0)
    calc = R.round_fcfa(L0 - an + vn)
    premier = not any(int(l.get("detenus") or 0) > 0 for l in (o.get("lignes") or []))
    out = {"liquidites_initiales": int(R.round_fcfa(L0)), "achats_nets": an, "ventes_nettes": vn, "liquidites_apres": apres,
           "ecart_identite": int(apres - calc), "premier_achat": premier, "statut": ESTIMATION,
           "pct_valeur": apres / V if V > 0 else None}
    if premier:
        hors = R.round_fcfa(V - float(c.get("cible_investie") or 0))
        rel = int(c.get("reliquat_arrondi") or 0)
        fr = int(c.get("achats_couts") or 0)
        out.update({"hors_cible": int(hors), "reliquat_arrondi": rel, "frais_achat": fr,
                    "ecart_identite_premier_achat": int(apres - (hors + rel - fr)),
                    "texte": f"{_rg.fcfa(hors, unite=False)} + {_rg.fcfa(rel, unite=False)} − {_rg.fcfa(fr, unite=False)} = "
                             f"{_rg.fcfa(apres)}"})
    return out


# ---------------------------------------------------------------------------
# (b) Argent qui dort, et ses causes
# ---------------------------------------------------------------------------


def _derniere_remise_a_niveau(t: pd.Timestamp) -> pd.Timestamp:
    y = t.year if t.month > 1 else t.year - 1
    d = pd.Timestamp(_dt.date(y, 1, 31))
    while d.weekday() >= 5:
        d -= pd.Timedelta(days=1)
    return d


def dividendes_depuis_janvier(ordre: Any, panels: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Estimation des dividendes reçus depuis la dernière remise à niveau de fin janvier : paiements de la table
    ``dividends_table`` entre cette date et la date de l'ordre, pour les titres détenus aujourd'hui (montant net
    publié ramené aux divisions postérieures). Statut : estimé."""
    if panels is None:
        return None
    dt = panels.get("dividends_table") if isinstance(panels, Mapping) else None
    if not isinstance(dt, pd.DataFrame) or not len(dt):
        return None
    o = _rg.en_dict(ordre)
    t = _ts(o.get("asof"))
    if t is None:
        return None
    t0 = _derniere_remise_a_niveau(t)
    det = {str(l["symbole"]): int(l.get("detenus") or 0) for l in (o.get("lignes") or []) if int(l.get("detenus") or 0) > 0}
    if not det:
        return {"montant": 0, "depuis": t0.strftime("%Y-%m-%d"), "statut": ESTIMATION, "lignes": []}
    if not isinstance(panels.get("corporate_actions"), pd.DataFrame) and "facteur_division" not in dt.columns:
        # Sans la table des opérations sur titres, un dividende détaché avant une division serait compté sur la base
        # de titres d'aujourd'hui (facteur 1) : le montant serait faux. Il n'est pas calculé.
        return {"montant": None, "depuis": t0.strftime("%Y-%m-%d"), "statut": ESTIMATION, "lignes": [],
                "non_calcule": "dividendes depuis janvier : non calculés (divisions d'actions inconnues : table "
                               "corporate_actions absente du panel)"}
    d = dt.copy()
    pay = pd.to_datetime(d["payment_date"].where(d["payment_date"].notna(), d["ex_date"]))
    d = d.assign(paiement_=pay)
    d = d[(d["paiement_"] > t0) & (d["paiement_"] <= t) & d["symbol"].astype(str).isin(det)]
    col = "amount_cashflow" if "amount_cashflow" in d.columns else "amount"
    tot = 0
    rows = []
    for r in d.itertuples(index=False):
        sym = str(r.symbol)
        f = getattr(r, "facteur_division", None)
        if f is None or not pd.notna(f):
            try:
                f = float(R._split_factor_after(panels, sym, pd.Timestamp(r.ex_date), t))
            except MemoryError:  # mémoire insuffisante : la commande s'arrête (code 6)
                raise
            except Exception as exc:  # noqa: BLE001 - facteur illisible : le montant n'est pas calculé (jamais 1)
                return {"montant": None, "depuis": t0.strftime("%Y-%m-%d"), "statut": ESTIMATION, "lignes": [],
                        "non_calcule": f"dividendes depuis janvier : non calculés (facteur de division de {sym} "
                                       f"illisible : {exc.__class__.__name__})"}
        net = float(getattr(r, col) if pd.notna(getattr(r, col)) else r.amount) / (f or 1.0)
        m = int(R.round_fcfa(det[sym] * net))
        tot += m
        rows.append({"symbole": sym, "paiement": pd.Timestamp(r.paiement_).strftime("%Y-%m-%d"), "montant": m})
    return {"montant": int(tot), "depuis": t0.strftime("%Y-%m-%d"), "statut": ESTIMATION, "lignes": rows}


def argent_qui_dort(ordre: Any, carnet: Mapping[str, Any] | None = None, *, memoire: Mapping[str, Any] | None = None,
                    panels: Mapping[str, Any] | None = None, arrondi_declare: bool = False,
                    reglages: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Argent qui dort au-delà de la réserve de la règle (§F7 b) : ``D = liquidités après les ordres proposés −
    2 % × V`` (V = titres au cours + liquidités réelles).

    Chaque franc de D est rangé dans une cause, en FCFA :

    * **non prévu** : ordres non servis ou servis en partie (titres de l'ordre d'origine non détenus après les ordres
      proposés : ``carnet["quantites_origine"]`` ou ``memoire["quantites_origine"]``) ; reliquat d'arrondi au-delà de
      la marge de F13c (seulement si l'arrondi « plus forts restes » est déclaré) ; cause inconnue ;
    * **prévu par la règle testée** : dividendes gardés jusqu'à la remise à niveau de fin janvier (carnet, ou
      estimation sur ``dividends_table``) ; produit des sorties forcées (carnet) ; argent laissé par la dernière remise à
      niveau s'il est mesuré (carnet ou mémoire) ; reliquat d'arrondi vers le bas et des plafonds de l'ordre en cours
      (lignes que l'ordre traite). La bande de 2 points gèle une ligne, elle ne crée pas d'argent : l'écart d'une ligne
      gelée n'est jamais rangé dans « prévu » sans mesure.

    ``D_hors_regle = D − D_prevu``."""
    o = _rg.en_dict(ordre)
    c = o.get("couts") or {}
    V = float(o.get("valeur_portefeuille") or 0)
    part = float(_rg.lire(reglages, "liquidites.part_reserve_regle", 0.02))
    apres = float(c.get("liquidites_apres") or 0)
    D = apres - part * V
    src = dict(carnet or {})
    for k, v in (memoire or {}).items():
        src.setdefault(k, v)
    lignes = o.get("lignes") or []
    orig = src.get("quantites_origine") or src.get("ordre_origine") or {}
    non_servis = 0.0
    detail_ns = []
    for l in lignes:
        s = str(l["symbole"])
        if s in orig:
            manque = max(0, int(orig[s]) - int(l.get("cibles") or 0))
            if manque > 0:
                non_servis += manque * float(l["cours_reference"])
                detail_ns.append({"symbole": s, "titres": manque, "montant": int(R.round_fcfa(manque * float(l["cours_reference"])))})
    achats = [l for l in lignes if l.get("sens") == "achat" and int(l.get("quantite") or 0) > 0]
    ventes = [l for l in lignes if l.get("sens") == "vente" and int(l.get("quantite") or 0) > 0]
    out: dict[str, Any] = {"D": int(R.round_fcfa(D)), "liquidites_apres": int(apres), "reserve_regle": int(R.round_fcfa(part * V)),
                           "part_reserve": part, "valeur": int(R.round_fcfa(V)), "aucun_ordre": not achats and not ventes,
                           "causes": [], "D_prevu": 0, "D_hors_regle": 0, "statut": ESTIMATION}
    if D <= 0:
        out["texte"] = (f"Liquidités après les ordres : {_rg.fcfa(apres)} ({_rg.pct(apres / V if V else 0)}), sous la réserve "
                        f"de {_rg.pct(part, 0)} de la règle : aucun argent ne dort au-delà.")
        return out
    reste = D
    causes: list[dict[str, Any]] = []

    def ajoute(code: str, libelle: str, montant: float, prevu: bool, statut: str = FAIT, **kw: Any) -> None:
        nonlocal reste
        m = max(0.0, min(reste, float(montant)))
        if m < 0.5:  # moins d'un franc : aucune cause écrite (jamais une ligne « 0 FCFA »)
            return
        reste -= m
        causes.append({"code": code, "cause": libelle, "montant": int(R.round_fcfa(m)), "prevu": prevu, "statut": statut, **kw})

    # 1. Non prévu, d'abord ce qui est un fait du carnet.
    ajoute("ordres_non_servis", "ordres non servis", non_servis, False, FAIT, detail=detail_ns)
    # 2. Prévu par la règle testée.
    div = src.get("dividendes_depuis_remise_a_niveau")
    div_st = FAIT
    div_nc = None
    if div is None:
        est = dividendes_depuis_janvier(o, panels)
        if est is not None:
            div, div_st = est["montant"], ESTIMATION
            div_nc = est.get("non_calcule")
    if div:
        ajoute("dividendes_gardes", "dividendes gardés jusqu'à la remise à niveau de fin janvier", float(div), True, div_st)
    if src.get("produit_sorties_forcees"):
        ajoute("sorties_forcees", "produit des sorties forcées, gardé jusqu'à la remise à niveau", float(src["produit_sorties_forcees"]), True)
    # Ce que la règle produit elle-même (§F7 b) : le reliquat d'arrondi vers le bas de l'ordre en cours, recalculé sur
    # les lignes que cet ordre traite (Σ w × V − q × p : lignes achetées ou vendues, lignes non encore détenues), le
    # reliquat des plafonds, moins les frais de l'ordre. L'écart d'une ligne gelée par la bande de 2 points dit pourquoi
    # l'argent n'est pas placé, pas d'où il vient : il n'est compté que s'il est mesuré (argent laissé par la dernière
    # remise à niveau, carnet ou mémoire : « reliquat_remise_a_niveau »). Le reste n'a pas de cause connue : « inconnue ».
    reliq_mesure = src.get("reliquat_remise_a_niveau")
    if reliq_mesure is not None:
        ajoute("bande_mesuree", "argent laissé par la dernière remise à niveau (arrondi et bande de 2 points, mesuré)",
               float(reliq_mesure), True, FAIT)
    regle = _reliquat_ordre_en_cours(o, V) + max(0.0, float(c.get("reliquat_plafonds") or 0)) * V \
        - float(c.get("achats_couts") or 0) - float(c.get("ventes_couts") or 0)
    if arrondi_declare:
        try:
            ar = arrondi_restes(o, reglages=reglages)
            place = float(ar.get("francs_ajoutes") or 0)
        except MemoryError:  # mémoire insuffisante : la commande s'arrête (code 6)
            raise
        except Exception:  # noqa: BLE001
            place = 0.0
        ajoute("arrondi_au_dela_marge", "arrondi au-delà de la marge", place, False, FAIT)
        regle -= place
    ajoute("regle", "argent laissé par l'arrondi vers le bas de l'ordre en cours", max(0.0, regle), True, FAIT)
    ajoute("inconnue", "inconnue", reste, False, HYPOTHESE)
    if div_nc:
        out["dividendes_non_calcules"] = div_nc
    prevu = sum(x["montant"] for x in causes if x["prevu"])
    hors = sum(x["montant"] for x in causes if not x["prevu"])
    out.update({"causes": causes, "D_prevu": int(prevu), "D_hors_regle": int(out["D"] - prevu), "D_non_prevu_detail": int(hors)})
    pct_l = _rg.pct(apres / V if V else 0)
    suffixe = f" {div_nc[0].upper()}{div_nc[1:]}." if div_nc else ""
    if out["aucun_ordre"] and out["D_hors_regle"] < float(_rg.lire(reglages, "liquidites.seuil_argent_qui_dort_fcfa", 100_000)):
        cause = "dividendes gardés jusqu'à fin janvier" if div else "arrondi et bande de la règle"
        out["texte"] = (f"Liquidités {_rg.fcfa(apres)} ({pct_l}). Aucun ordre proposé : la règle n'achète pas hors de la "
                        "remise à niveau de janvier, et la bande de 2 points gèle chaque ligne. Cet argent est prévu par la "
                        f"règle testée ({cause}).")
    else:
        hors_c = [x for x in causes if not x["prevu"]]
        principale = max(hors_c or causes, key=lambda x: x["montant"])["cause"] if causes else "inconnue"
        out["texte"] = (f"Argent qui dort : {_rg.fcfa(out['D'])} au-delà de la réserve de {_rg.pct(part, 0)} ; dont hors de la "
                        f"règle testée {_rg.fcfa(out['D_hors_regle'])} (cause : {principale}).")
    out["texte"] += suffixe
    return out


def _reliquat_ordre_en_cours(o: Mapping[str, Any], V: float) -> float:
    """Reliquat d'arrondi vers le bas de l'ordre en cours : Σ (w × V − q × p) sur les lignes cibles que l'ordre traite
    (achat ou vente proposés, ou ligne non encore détenue). Les lignes détenues sans ordre (gelées par la bande de 2
    points) n'y entrent pas : leur écart ne dit pas d'où vient l'argent."""
    tot = 0.0
    for l in o.get("lignes") or []:
        w, p = float(l.get("poids_cible") or 0), float(l.get("cours_reference") or 0)
        if w <= 0 or p <= 0:
            continue
        traitee = (l.get("sens") in ("achat", "vente") and int(l.get("quantite") or 0) > 0) or int(l.get("detenus") or 0) == 0
        if traitee:
            tot += w * V - int(l.get("cibles") or 0) * p
    return tot


# ---------------------------------------------------------------------------
# (c) Réserve de fonctionnement (information, pas une règle)
# ---------------------------------------------------------------------------


def _annuels(o: Mapping[str, Any], grille: _gr.GrilleSGI | None = None) -> float:
    c = o.get("couts") or {}
    a = float(c.get("garde_annuelle") or 0) + float(c.get("tenue_compte_annuelle") or 0)
    if c.get("forfait_compte_annuel") is not None:
        a += float(c["forfait_compte_annuel"])
    elif grille is not None:
        a += float(grille.valeur("forfait_compte"))
    return a


def reserve_fonctionnement(ordre: Any, grille: _gr.GrilleSGI | None = None, n: int | Sequence[int] | None = None, *,
                           reglages: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """``R_n = round_fcfa(n × frais annuels ÷ 4)`` pour n = 2 et 3 (demi vers le haut) : à 10 M, 62 063 et 93 095 FCFA.
    Information, pas une règle : la réserve de 2 % de la spécification ne change pas."""
    o = _rg.en_dict(ordre)
    ns = [int(n)] if isinstance(n, int) else [int(x) for x in (n if n is not None else
                                                               _rg.lire(reglages, "liquidites.trimestres_reserve", [2, 3]))]
    a = _annuels(o, grille)
    return {"frais_annuels": int(R.round_fcfa(a)), "trimestres": {str(k): int(R.round_fcfa(k * a / 4.0)) for k in ns},
            "statut": HYPOTHESE if _gr.statut_global(grille) == _gr.SUPPOSE else FAIT,
            "texte": "Réserve de fonctionnement (information) : de quoi payer les frais fixes de "
                     + " ou ".join(f"{k} trimestres ({_rg.fcfa(R.round_fcfa(k * a / 4.0))})" for k in ns) + "."}


# ---------------------------------------------------------------------------
# (d) Projection à cours constants
# ---------------------------------------------------------------------------


def _dernier_ouvre(y: int, m: int) -> _dt.date:
    d = _dt.date(y + (m == 12), (m % 12) + 1, 1) - _dt.timedelta(days=1)
    while d.weekday() >= 5:
        d -= _dt.timedelta(days=1)
    return d


def _fins_trimestre(a: _dt.date, b: _dt.date) -> set[_dt.date]:
    out = set()
    for y in range(a.year, b.year + 1):
        for m, j in ((3, 31), (6, 30), (9, 30), (12, 31)):
            d = _dt.date(y, m, j)
            if a <= d <= b:
                out.add(d)
    return out


def _plafonds(o: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(e["symbole"]): (e.get("plafonds") or {}) for e in (o.get("explications") or []) if e.get("symbole")}


def projection(ordre: Any, grille: _gr.GrilleSGI | None = None, *, reinvestir: bool = False, costs: Any = None,
               reglages: Mapping[str, Any] | None = None, serie: bool = False) -> dict[str, Any]:
    """Projection jour par jour à cours constants (§F7 d), du premier jour d'exécution au dernier jour ouvré de
    janvier de l'année N+2 : départ = liquidités après l'ordre ; + ``round_fcfa(titres × dividende net prévu)`` à
    chaque date de paiement prévue ; − ``(garde × investi + tenue × lignes + forfait) × jours ÷ 365`` à chaque fin de
    trimestre civil (prélèvement supposé en fin de trimestre). Elle suit la règle testée (dividendes gardés jusqu'à
    janvier). Compte des francs ; ne prévoit rien.

    ``reinvestir=True`` : simulation **d'information** de l'essai E-D (F13d, règle corrigée), qui n'est pas la règle
    testée : à la dernière séance de chaque mois, une seule ligne, la plus en retard sur son poids, montant permis
    ``min(D ; min(plafond ; w + 1 point) × V − valeur détenue)``, seulement s'il atteint le seuil S."""
    o = _rg.en_dict(ordre)
    c = o.get("couts") or {}
    cm = _gr.cost_model_de(o, costs)
    if grille is not None:
        cm, _f = _gr.vers_cost_model(grille, cm)
    forfait = float(c.get("forfait_compte_annuel") or (grille.valeur("forfait_compte") if grille is not None else 0.0))
    ex = o.get("execution") or {}
    start = _ts(ex.get("premiere_seance")) or _ts(o.get("asof"))
    if start is None:
        raise ValueError("date de la première séance absente")
    d0 = start.date()
    reb = _ts(((o.get("declencheurs") or {}).get("rebalancement") or {}).get("rebalancement_annuel"))
    reb1 = reb.date() if reb is not None else _dernier_ouvre(d0.year + 1, 1)
    fin = _dernier_ouvre(reb1.year + 1, 1)
    lignes = {str(l["symbole"]): l for l in (o.get("lignes") or []) if int(l.get("cibles") or 0) > 0}
    titres = {s: int(l["cibles"]) for s, l in lignes.items()}
    pay: dict[_dt.date, list[tuple[str, float]]] = {}
    for d in o.get("dividendes") or []:
        dp = _ts(d.get("date_paiement_prevue"))
        nps = d.get("dividende_net_prevu_par_titre")
        if dp is None or nps is None or int(d.get("montant_net") or 0) <= 0 or str(d["symbole"]) not in titres:
            continue
        pay.setdefault(dp.date(), []).append((str(d["symbole"]), float(nps)))
    trims = _fins_trimestre(d0, fin)
    caps = _plafonds(o)
    seuil = float(_rg.lire(reglages, "liquidites.seuil_reinvestissement_fcfa", 100_000))
    S = max(seuil, (cm.min_ticket_fcfa / cm.sgi_commission) if cm.sgi_commission > 0 else seuil)
    part = float(_rg.lire(reglages, "liquidites.part_reserve_regle", 0.02))
    part_max = float(ex.get("participation_max_regle") or 0.10)
    cash = float(c.get("liquidites_apres") or 0)
    dernier = d0
    serie_j: dict[_dt.date, float] = {}
    achats: list[dict[str, Any]] = []
    frais_achats = 0
    paiements: list[dict[str, Any]] = []
    j = d0
    while j <= fin:
        for s, nps in pay.get(j, []):
            m = int(R.round_fcfa(titres[s] * nps))
            cash += m
            paiements.append({"date": j.isoformat(), "symbole": s, "montant": m})
        if j in trims:
            inv = sum(titres[s] * float(lignes[s]["cours_reference"]) for s in titres)
            n = sum(1 for s in titres if titres[s] > 0)
            cash -= (cm.annual_custody * inv + cm.account_fee_per_line_fcfa * n + forfait) * (j - dernier).days / 365.0
            dernier = j
        if reinvestir and j > d0 and j == _dernier_ouvre(j.year, j.month):
            inv = sum(titres[s] * float(lignes[s]["cours_reference"]) for s in titres)
            V = inv + cash
            Dd = cash - part * V
            manque = {s: float(lignes[s]["poids_cible"]) * V - titres[s] * float(lignes[s]["cours_reference"]) for s in titres}
            s = max(manque, key=lambda k: (manque[k], k))
            l = lignes[s]
            p = float(l["cours_reference"])
            cap = min(float((caps.get(s) or {}).get("upper") or 1.0), float(l["poids_cible"]) + 0.01)
            Mi = min(Dd, cap * V - titres[s] * p)
            if Mi >= S:
                q = 0
                while True:
                    q2 = q + 1
                    tr = R.participation_schedule(q2, p, l.get("mdv63"), part_max)
                    oc = R.order_costs(q2, p, cm, side="achat", half_spread=float(l.get("demi_spread_pct") or 0.0),
                                       mdv63=l.get("mdv63"), tranches=tr, limit=float(l["limite_achat"]))
                    ok = (q2 * p + oc["total"] <= Mi and (titres[s] + q2) * p / V <= cap + 1e-12
                          and R._worst_case(tr, float(l["limite_achat"]), cm, "achat") <= cash)
                    if not ok:
                        break
                    q = q2
                if q > 0:
                    tr = R.participation_schedule(q, p, l.get("mdv63"), part_max)
                    oc = R.order_costs(q, p, cm, side="achat", half_spread=float(l.get("demi_spread_pct") or 0.0),
                                       mdv63=l.get("mdv63"), tranches=tr, limit=float(l["limite_achat"]))
                    cash -= q * p + oc["total"]
                    titres[s] += q
                    frais_achats += int(oc["total"])
                    achats.append({"date": j.isoformat(), "symbole": s, "titres": q, "montant": int(R.round_fcfa(q * p)),
                                   "frais": int(oc["total"])})
        serie_j[j] = cash
        j += _dt.timedelta(days=1)

    def moy(a: _dt.date, b: _dt.date) -> float | None:
        v = [x for d, x in serie_j.items() if a <= d <= b]
        return sum(v) / len(v) if v else None

    fdm: dict[str, int] = {}
    for d, v in serie_j.items():
        fdm[f"{d.year}-{d.month:02d}"] = int(R.round_fcfa(v))
    par_mois: dict[str, int] = {}
    for p_ in paiements:
        k = p_["date"][:7]
        par_mois[k] = par_mois.get(k, 0) + p_["montant"]
    deb_p = _dt.date(reb1.year, 2, 1)
    m1 = moy(d0, reb1 - _dt.timedelta(days=1))
    m2 = moy(deb_p, fin - _dt.timedelta(days=1))
    pic_d = max(serie_j, key=lambda k: serie_j[k]) if serie_j else None
    out = {"debut": d0.isoformat(), "fin": fin.isoformat(), "remise_a_niveau": reb1.isoformat(),
           "dividendes_total": int(sum(p_["montant"] for p_ in paiements)), "n_paiements": len(paiements),
           "premier_paiement": paiements[0]["date"] if paiements else None,
           "dernier_paiement": paiements[-1]["date"] if paiements else None, "dividendes_par_mois": par_mois,
           "fins_de_mois": fdm, "moyenne_avant_remise_a_niveau": m1, "moyenne_annee_suivante": m2,
           "periode_moyenne": [deb_p.isoformat(), (fin - _dt.timedelta(days=1)).isoformat()],
           "pointe": serie_j[pic_d] if pic_d else None, "date_pointe": pic_d.isoformat() if pic_d else None,
           "a_la_remise_a_niveau": serie_j.get(fin), "statut": ESTIMATION, "reinvestir": bool(reinvestir),
           "hypotheses": ["cours constants au cours de référence", "dernier dividende reconduit, payé à la date prévue",
                          "frais fixes prélevés en fin de trimestre civil (date réelle inconnue)"],
           "regle": "règle testée : dividendes gardés jusqu'à la remise à niveau de fin janvier" if not reinvestir else
           "essai E-D (F13d), écart à la règle testée : information seulement"}
    if serie:
        # Liquidités jour par jour (référence du feu « Fuites », §F11 b) ; hors du JSON de l'ordre par défaut.
        out["serie"] = {d.isoformat(): float(v) for d, v in serie_j.items()}
    if reinvestir:
        base = projection(o, grille, reinvestir=False, costs=costs, reglages=reglages)
        out.update({"achats": achats, "frais_achats": frais_achats, "achete": int(sum(a["montant"] for a in achats)),
                    "seuil_S": S,
                    "remis_au_travail_moyen": (base["moyenne_annee_suivante"] - m2) if (m2 is not None and base["moyenne_annee_suivante"] is not None) else None})
    return out


def projection_detenus(titres: Mapping[str, int], panels: Mapping[str, Any], asof: Any, liquidites: float, *,
                       costs: Any = None, grille: _gr.GrilleSGI | None = None, calendrier: Any = None,
                       reglages: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Projection de F7 (d) pour un portefeuille détenu (règle déclarée : dividendes gardés jusqu'à la remise à niveau
    de fin janvier), sans ordre de bataille : titres au dernier cours connu en ``asof``, dividendes attendus
    (``recommend.dividend_schedule``, avec le calendrier des séances), frais fixes de ``costs`` ou de la grille.
    Rend la projection avec sa série journalière (``serie=True``). Lecture seule."""
    from brvm_alpha.config import CostModel

    t = pd.Timestamp(asof).normalize()
    q = {str(k): int(v) for k, v in (titres or {}).items() if int(v) > 0}
    close = panels.get("close_raw") if isinstance(panels.get("close_raw"), pd.DataFrame) else panels.get("close")
    cal = calendrier
    if cal is None:
        ses = panels.get("sessions")
        cal = (pd.DatetimeIndex(pd.to_datetime(ses["date"])) if isinstance(ses, pd.DataFrame) and "date" in ses.columns
               else pd.DatetimeIndex(close.index))
    lignes = []
    for s_, n in q.items():
        col = close[s_].loc[:t].dropna() if isinstance(close, pd.DataFrame) and s_ in close.columns else pd.Series(dtype=float)
        if not len(col):
            continue
        lignes.append({"symbole": s_, "cibles": n, "detenus": n, "cours_reference": float(col.iloc[-1]), "poids_cible": 0.0,
                       "limite_achat": float(col.iloc[-1]), "sens": "garder", "quantite": 0})
    div = []
    if q:
        sch = R.dividend_schedule(q, t, panels, calendar=cal)
        for r in sch.to_dict("records"):
            if r.get("date_paiement_prevue") is None or not pd.notna(r.get("date_paiement_prevue")):
                continue
            n = int(r.get("titres") or 0)
            div.append({"symbole": str(r["symbole"]), "date_paiement_prevue": pd.Timestamp(r["date_paiement_prevue"]),
                        "montant_net": int(r.get("montant_net") or 0),
                        "dividende_net_prevu_par_titre": (float(r.get("montant_net") or 0) / n) if n else 0.0})
    cm = costs if isinstance(costs, CostModel) else CostModel()
    forfait = float(grille.valeur("forfait_compte")) if grille is not None else float(getattr(cm, "account_fee_fixed_fcfa", 0.0) or 0.0)
    o = {"asof": t.date().isoformat(), "lignes": lignes, "dividendes": div,
         "couts": {"liquidites_apres": float(liquidites), "forfait_compte_annuel": forfait},
         "execution": {"premiere_seance": t.date().isoformat()}}
    return projection(o, grille, costs=cm, reglages=reglages, serie=True)


# ---------------------------------------------------------------------------
# (e) Provision d'entrée et part investie maximale
# ---------------------------------------------------------------------------


def _pire_achats(o: Mapping[str, Any], cm: Any) -> int:
    tot = 0
    for l in o.get("lignes") or []:
        if l.get("sens") != "achat" or int(l.get("quantite") or 0) <= 0:
            continue
        tr = [int(x) for x in (l.get("tranches") or [int(l["quantite"])])]
        tot += int(R._worst_case(tr, float(l["prix_limite"]), cm, "achat"))
    return tot


def provision_entree(ordre: Any, costs: Any = None, *, reglages: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Provision d'entrée (§F7 e) : ``ρ = Σ q × L ÷ Σ q × p`` ; ``τ = costs.rate()`` ; **part investie maximale =
    1 ÷ (ρ × (1 + τ))** (97,81 % au tarif supposé : la cible de 98 % n'est pas atteignable avec la règle du pire
    cas). Provision du pire cas, marge = liquidités − provision, et la même marge avec un courtage plus cher de
    0,2 point. Montants calculés sur un tarif supposé tant que la grille n'est pas saisie."""
    o = _rg.en_dict(ordre)
    c = o.get("couts") or {}
    cm = _gr.cost_model_de(o, costs)
    L = [l for l in (o.get("lignes") or []) if int(l.get("cibles") or 0) > 0]
    num = sum(int(l["cibles"]) * float(l["limite_achat"]) for l in L)
    den = sum(int(l["cibles"]) * float(l["cours_reference"]) for l in L)
    rho = num / den if den > 0 else None
    tau = float(cm.rate())
    liq = float(o.get("liquidites_initiales") or 0)
    provision = int(c.get("achats_pire_cas") or _pire_achats(o, cm))
    sur = float(_rg.lire(reglages, "liquidites.surcout_courtage_test", 0.002))
    cm2 = R.replace_costs(cm, sgi_commission=cm.sgi_commission + sur)
    p2 = _pire_achats(o, cm2)
    ventes_min = int(c.get("ventes_pire_cas") or 0)
    marge = int(math.floor(liq)) + ventes_min - provision
    marge2 = int(math.floor(liq)) + ventes_min - p2
    from brvm_alpha import settings

    parts = {}
    for nom in ("optimistic", "central", "stress", "severe"):
        try:
            t2 = float(settings.cost_scenario(nom).rate())
            parts[nom] = 1.0 / (rho * (1.0 + t2)) if rho else None
        except MemoryError:  # mémoire insuffisante : la commande s'arrête (code 6)
            raise
        except Exception:  # noqa: BLE001
            parts[nom] = None
    pmax = 1.0 / (rho * (1.0 + tau)) if rho else None
    cible = float(c.get("cible_specification") or 0.98)
    txt = (f"Provision à avoir avant l'ordre : {_rg.fcfa(provision)}. Part investie maximale à ce tarif : "
           f"{_rg.pct(pmax, 2)}" + (f" (la cible de {_rg.pct(cible, 0)} n'est pas atteignable)." if pmax is not None and pmax < cible else "."))
    return {"rho": rho, "tau": tau, "part_investie_max": pmax, "parts_par_scenario": parts, "provision_pire_cas": provision,
            "liquidites": int(R.round_fcfa(liq)), "marge": marge, "surcout_courtage_test": sur,
            "provision_courtage_plus_cher": int(p2), "marge_courtage_plus_cher": marge2,
            "statut": HYPOTHESE, "mention": "provision calculée sur un tarif supposé", "texte": txt}


# ---------------------------------------------------------------------------
# F13c — arrondi « plus forts restes »
# ---------------------------------------------------------------------------


def arrondi_restes(ordre: Any, costs: Any = None, grille: _gr.GrilleSGI | None = None, *, appliquer: bool = False,
                   forcer: bool = False, reglages: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Arrondi « plus forts restes » avec marge (§F13c). Éteint par défaut : sans ``appliquer``, c'est
    l'information de F7 f (« sans l'appliquer »). L'appliquer est un écart à la règle testée (E-A) ; il est refusé si
    la grille est ``supposé``, sauf ``forcer`` (emploi sur papier).

    1. ``q0 = ⌊x + 1e-9⌋``, ``x = w × V ÷ p`` ; reste ``f = x − q0`` ;
    2. marge ``M = n × (garde × cible investie + tenue × lignes cibles + forfait) ÷ 4``, n = 2 ;
    3. lignes par reste décroissant puis par code ; ``q0 + 1`` gardé si (C1) provisions du pire cas ≤ ⌊liquidités⌋ +
       encaissement minimal des ventes − M, (C2) Σ titres × cours ≤ cible investie, (C3) plafonds de ligne, de
       secteur, de pays et du bloc AES respectés (ligne sans plafond connu : rien), (C4) au plus 10 séances,
       (C5) un seul titre de plus par ligne ;
    4. M non tenue au départ : rien n'est ajouté, motif écrit.

    Seulement les lignes en achat, non gelées, non bloquées, et si le contrôle du pire cas n'a réduit aucune
    quantité."""
    o = _rg.en_dict(ordre)
    if appliquer and _gr.statut_global(grille) == _gr.SUPPOSE and not forcer:
        from brvm_alpha.erreurs import SaisieInvalide  # refus d'une saisie (code 2), classe fille de ValueError

        raise SaisieInvalide("arrondi « plus forts restes » refusé : la grille du courtier est supposée (option --forcer pour "
                         "un emploi sur papier)")
    cm = _gr.cost_model_de(o, costs)
    forfait = float((o.get("couts") or {}).get("forfait_compte_annuel") or 0.0)
    if grille is not None:
        cm, forfait = _gr.vers_cost_model(grille, cm)
    c = o.get("couts") or {}
    ex = o.get("execution") or {}
    V = float(o.get("valeur_portefeuille") or 0)
    liq = float(o.get("liquidites_initiales") or 0)
    part_max = float(ex.get("participation_max_regle") or 0.10)
    max_sean = int(_rg.lire(reglages, "suivi.validite_ordre_seances", 10))
    n_trim = float(_rg.lire(reglages, "liquidites.marge_arrondi_trimestres", 2))
    caps = _plafonds(o)
    L = [l for l in (o.get("lignes") or []) if float(l.get("poids_cible") or 0) > 0]
    cible = float(c.get("cible_pct") or 0.98) * V
    M = n_trim * (cm.annual_custody * cible + cm.account_fee_per_line_fcfa * len(L) + forfait) / 4.0
    by = {str(l["symbole"]): l for l in L}
    x = {s: float(l["poids_cible"]) * V / float(l["cours_reference"]) for s, l in by.items()}
    q0 = {s: int(l["cibles"]) for s, l in by.items()}
    ventes_min = int(c.get("ventes_pire_cas") or 0)

    def pire(s: str, q: int, mod: Any = cm) -> int:
        l = by[s]
        if l.get("sens") != "achat" and q <= int(l.get("detenus") or 0):
            return 0
        qa = q - int(l.get("detenus") or 0)
        if qa <= 0:
            return 0
        tr = R.participation_schedule(qa, float(l["cours_reference"]), l.get("mdv63"), part_max)
        return int(R._worst_case(tr, float(l["limite_achat"]), mod, "achat"))

    def couts_achat(q: dict[str, int]) -> int:
        tot = 0
        for s, qi in q.items():
            l = by[s]
            qa = qi - int(l.get("detenus") or 0)
            if qa <= 0:
                continue
            tr = R.participation_schedule(qa, float(l["cours_reference"]), l.get("mdv63"), part_max)
            tot += int(R.order_costs(qa, float(l["cours_reference"]), cm, side="achat",
                                     half_spread=float(l.get("demi_spread_pct") or 0.0), mdv63=l.get("mdv63"), tranches=tr,
                                     limit=float(l["limite_achat"]))["total"])
        return tot

    def ecarts(q: dict[str, int]) -> float:
        return sum(abs(float(by[s]["poids_cible"]) - q[s] * float(by[s]["cours_reference"]) / V) for s in q) if V else 0.0

    budget = int(math.floor(liq)) + ventes_min - M
    pc0 = sum(pire(s, q0[s]) for s in q0)
    inv0 = sum(q0[s] * float(by[s]["cours_reference"]) for s in q0)
    q = dict(q0)
    ajout: list[str] = []
    motif = ""
    elig = {s for s, l in by.items() if l.get("sens") == "achat" and "bande" not in str(l.get("note") or "")
            and "bloquée" not in str(l.get("note") or "") and "suspendu" not in str(l.get("note") or "")}
    if ex.get("reductions"):
        motif = "le contrôle du pire cas a déjà réduit des quantités : aucun titre ajouté"
    elif pc0 > budget:
        motif = (f"marge de {_rg.fcfa(M)} non tenue avec les quantités de départ (pire cas {_rg.fcfa(pc0)}, liquidités "
                 f"{_rg.fcfa(liq)}) : aucun titre ajouté")
    else:
        ordre_l = sorted((s for s in q if s in elig and x[s] - q0[s] > 1e-9), key=lambda s: (-(x[s] - q0[s]), s))
        for s in ordre_l:
            l = by[s]
            q2 = dict(q)
            q2[s] = q0[s] + 1
            c1 = sum(pire(k, q2[k]) for k in q2) <= budget
            c2 = sum(q2[k] * float(by[k]["cours_reference"]) for k in q2) <= cible + 1e-6
            wl = {k: q2[k] * float(by[k]["cours_reference"]) / V for k in q2}
            cp = caps.get(s) or {}
            c3 = cp.get("upper") is not None and wl[s] <= float(cp["upper"]) + 1e-12
            if c3 and cp.get("sector") is not None:
                c3 = sum(wl[k] for k in wl if by[k].get("secteur") == l.get("secteur")) <= float(cp["sector"]) + 1e-12
            if c3 and l.get("pays") != "CI" and cp.get("country") is not None:
                c3 = sum(wl[k] for k in wl if by[k].get("pays") == l.get("pays")) <= float(cp["country"]) + 1e-12
            if c3 and l.get("pays") in AES and isinstance(cp.get("aes"), Mapping):
                c3 = sum(wl[k] for k in wl if by[k].get("pays") in AES) <= float(cp["aes"].get("bloc AES (siège)", 1.0)) + 1e-12
            qa = q2[s] - int(l.get("detenus") or 0)
            c4 = len(R.participation_schedule(qa, float(l["cours_reference"]), l.get("mdv63"), part_max)) <= max_sean
            if c1 and c2 and c3 and c4:
                q = q2
                ajout.append(s)
    pc = sum(pire(s, q[s]) for s in q)
    inv = sum(q[s] * float(by[s]["cours_reference"]) for s in q)
    plus = inv - inv0
    marge = int(math.floor(liq)) + ventes_min - pc
    cm15 = R.replace_costs(cm, sgi_commission=0.015)
    out = {"applique": bool(appliquer), "marge_M": M, "titres_ajoutes": len(ajout), "lignes_ajoutees": ajout,
           "francs_ajoutes": int(R.round_fcfa(plus)), "investi": int(R.round_fcfa(inv)), "part_investie": inv / V if V else None,
           "investi_depart": int(R.round_fcfa(inv0)), "part_investie_depart": inv0 / V if V else None,
           "marge_pire_cas": int(marge), "marge_pire_cas_depart": int(math.floor(liq)) + ventes_min - pc0,
           "frais_achat_en_plus": couts_achat(q) - couts_achat(q0),
           "marge_courtage_1_5pct": int(math.floor(liq)) + ventes_min - sum(pire(s, q[s], cm15) for s in q),
           "somme_ecarts": ecarts(q), "somme_ecarts_depart": ecarts(q0), "quantites": q, "motif": motif,
           "statut": FAIT, "ecart_a_la_regle": "E-A (arrondi « plus forts restes »), éteint par défaut",
           "phrase": _rg.PH_PLACE}
    if not appliquer:
        out["texte"] = (f"Avec l'arrondi « plus forts restes » : {_rg.fcfa(plus, signe=True)} placés ({_rg.pct(out['part_investie'], 2)} "
                        f"au lieu de {_rg.pct(out['part_investie_depart'], 2)}), marge du pire cas {_rg.fcfa(marge)}. Option "
                        "--arrondi restes, écart à la règle testée. Gain ou perte selon le marché." if plus > 0 else
                        "Arrondi « plus forts restes » : aucun titre ne peut être ajouté sous les contraintes"
                        + (f" ({motif})." if motif else "."))
    return out


# ---------------------------------------------------------------------------
# (g) « Passer l'ordre »
# ---------------------------------------------------------------------------


def carnet_de_cloture(panel_dir: str | Path, asof: Any) -> dict[str, dict[str, float]] | None:
    """Carnet de clôture (``order_book.parquet``, lecture seule) à la date ``asof`` : symbole → ``ask``,
    ``ask_qty``. ``None`` si le fichier ou les colonnes manquent."""
    p = Path(panel_dir) / "order_book.parquet"
    if not p.exists():
        return None
    ob = pd.read_parquet(p, columns=["date", "symbol", "ask", "ask_qty"])
    t = pd.Timestamp(asof).normalize()
    ob = ob[pd.to_datetime(ob["date"]) == t]
    return {str(r.symbol): {"ask": float(r.ask), "ask_qty": float(r.ask_qty)} for r in ob.itertuples(index=False)
            if pd.notna(r.ask)}


def compte_carnet(ordre: Any, carnet: Mapping[str, Mapping[str, float]] | None) -> dict[str, Any] | None:
    """Consigne 7 (§F7 g, §4.5 ``passer_l_ordre.carnet``) : ``{"n1", "n2", "date"}`` ; n1 = lignes d'achat dont le prix
    demandé au dernier carnet dépasse la limite ; n2 = lignes au prix demandé sous la limite mais sans assez de titres
    au meilleur prix. ``None`` sans carnet."""
    if not carnet:
        return None
    o = _rg.en_dict(ordre)
    n1 = n2 = 0
    for l in o.get("lignes") or []:
        if l.get("sens") != "achat" or int(l.get("quantite") or 0) <= 0:
            continue
        b = carnet.get(str(l["symbole"]))
        if not b or b.get("ask") is None:
            continue
        if float(b["ask"]) > float(l["prix_limite"]) + 1e-9:
            n1 += 1
        elif float(b.get("ask_qty") or 0) < int(l["quantite"]):
            n2 += 1  # parmi les lignes dont le prix demandé est sous la limite (04_limites.py)
    return {"n1": n1, "n2": n2, "date": str(o.get("asof") or "")[:10] or None}


def consignes(ordre: Any, panels: Mapping[str, Any] | None = None, *,
              carnet: Mapping[str, Mapping[str, float]] | None = None) -> list[str]:
    """Consignes fixes pour passer l'ordre (§F7 g) ; la 7e seulement si le carnet de clôture est connu : « Au dernier
    carnet, {n1} lignes ont un prix demandé au-dessus de votre limite et {n2} n'offrent pas assez de titres au
    meilleur prix. »"""
    out = list(CONSIGNES)
    cb = carnet
    if cb is None and isinstance(panels, Mapping) and isinstance(panels.get("carnet_cloture"), Mapping):
        cb = panels["carnet_cloture"]
    k = compte_carnet(ordre, cb)
    if k is not None:
        out.append(f"Au dernier carnet, {k['n1']} lignes ont un prix demandé au-dessus de votre limite et {k['n2']} "
                   "n'offrent pas assez de titres au meilleur prix.")
    return out
