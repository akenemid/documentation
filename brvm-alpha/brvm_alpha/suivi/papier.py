"""F12 — Exécution sur papier des ordres d'un carnet, avec test de limite.

Cahier ``docs/RENDEMENT_NET.md``, §F12 et §8.3 (article E-L). Sur papier, l'outil applique la règle que l'utilisateur
pourrait vraiment suivre. Deux modes :

* ``limite`` (défaut) : règle **plus stricte que le §7.1 de la spécification** (elle ajoute un test de limite), déclarée
  comme telle (article E-L) ; elle sert ``PLAN`` et ``MOI``. À la séance d, un achat est servi si le titre a coté et si
  son cours moyen du jour (valeur ÷ volume) est au plus à la limite ; une vente, s'il est au moins à la limite.
  Frais facturés : ceux de la grille (``fee_breakdown``) ; le coût dans le prix se lit dans le prix payé ;
* ``test`` : exécution du §7.1 sans test de limite (cours moyen du jour suivant si le titre est échangé), pour les
  essais ``E-C`` et ``E-D``, afin qu'ils ne diffèrent du témoin que par leur écart ; écart et impact estimés payés en
  liquidités, comme dans le moteur (contrôle P8 : les différences restantes avec le moteur sont publiées).

Règles communes : un ordre décidé à la clôture de t est saisi pour la séance suivante ; titres servis =
min(reste ; ⌊10 % × volume du jour⌋) ; le reste est reporté, puis ``expiration`` après 10 séances ; le jour d'un
détachement ou d'une division du titre, l'ordre est annulé et ressaisi le jour même, avec une limite recalculée sur la
référence ajustée ; un achat financé par une vente n'est possible qu'à partir du règlement de la vente (deux séances) ;
dividendes crédités nets à la date de paiement publiée ; frais fixes prélevés en fin de trimestre civil [Hypothèse].

Le témoin ``REF-S2`` garde l'exécution du moteur (:mod:`~brvm_alpha.suivi.temoin`). Aucune écriture hors du dossier du
portefeuille ; aucune date de S1. Performance passée ≠ garantie. Aucun gain n'est garanti.
"""

from __future__ import annotations

import json
import math
from typing import Any, Mapping

import pandas as pd

from brvm_alpha import suivi as _s
from brvm_alpha.rendement import reglages as _rg
from brvm_alpha.suivi import carnet as _cn
from brvm_alpha.suivi import etat as _et

__all__ = ["MODES", "controle_p8", "dividendes_detaches", "divisions", "executer", "mesures"]

MODES = ("limite", "test")
_ETAT = "papier.json"


def _f(x: Any, defaut: float = 0.0) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return defaut
    return v if math.isfinite(v) else defaut


def _wide(panels: Mapping[str, Any], cle: str) -> pd.DataFrame | None:
    return _et._wide(panels, cle)


def dividendes_detaches(panels: Mapping[str, Any], lag: int = 2) -> pd.DataFrame:
    """Dividendes du panel : ``symbole, date_detachement, date_paiement, net_par_titre`` (montant corrigé si connu ;
    paiement publié, sinon détachement + ``lag`` séances)."""
    tab = panels.get("dividends_table") if isinstance(panels, Mapping) else None
    cols = ["symbole", "date_detachement", "date_paiement", "net_par_titre"]
    if not isinstance(tab, pd.DataFrame) or not len(tab) or "ex_date" not in tab.columns:
        return pd.DataFrame(columns=cols)
    dates = pd.DatetimeIndex(pd.to_datetime(panels["close"].index)).normalize()
    col = "amount_cashflow" if "amount_cashflow" in tab.columns else "amount"
    rows = []
    for r in tab.itertuples(index=False):
        ex = pd.Timestamp(getattr(r, "ex_date")).normalize()
        if pd.isna(ex):
            continue
        pay = getattr(r, "payment_date", None)
        pay = pd.Timestamp(pay).normalize() if pay is not None and pd.notna(pay) else None
        if pay is None:
            i = int(dates.searchsorted(ex, side="left"))
            pay = dates[i + lag] if i + lag < len(dates) else ex + pd.offsets.BDay(lag)
        rows.append({"symbole": str(getattr(r, "symbol")), "date_detachement": ex, "date_paiement": max(pay, ex),
                     "net_par_titre": _f(getattr(r, col))})
    return pd.DataFrame(rows, columns=cols).drop_duplicates(["symbole", "date_detachement"], keep="last")


def divisions(panels: Mapping[str, Any]) -> pd.DataFrame:
    """Divisions et regroupements : ``corporate_actions`` du panel (``kind`` contenant « split » ou « division »,
    ``ratio`` = titres nouveaux par titre ancien) ; à défaut, sauts du facteur d'ajustement ``adj_factor``."""
    ca = panels.get("corporate_actions") if isinstance(panels, Mapping) else None
    cols = ["symbole", "date", "rapport"]
    if isinstance(ca, pd.DataFrame) and len(ca) and {"date", "symbol", "ratio"} <= set(ca.columns):
        k = ca["kind"].astype(str).str.lower() if "kind" in ca.columns else pd.Series("split", index=ca.index)
        m = k.str.contains("split|division|regroup")
        out = pd.DataFrame({"symbole": ca.loc[m, "symbol"].astype(str), "date": pd.to_datetime(ca.loc[m, "date"]).dt.normalize(),
                            "rapport": ca.loc[m, "ratio"].astype(float)})
        return out[out["rapport"] > 0].reset_index(drop=True)
    af = _wide(panels, "adj_factor")
    rows = []
    if af is not None:
        r = af / af.shift(1)
        for c in af.columns:
            x = r[c].dropna()
            for d, v in x[(x - 1.0).abs() > 1e-6].items():
                rows.append({"symbole": c, "date": pd.Timestamp(d).normalize(), "rapport": float(v)})
    return pd.DataFrame(rows, columns=cols)


def _cm(grille: Any, costs: Any) -> Any:
    from brvm_alpha.config import CostModel
    from brvm_alpha.rendement import grille as _gr

    base = costs if isinstance(costs, CostModel) else CostModel()
    if grille is not None:
        cm, _forfait = _gr.vers_cost_model(grille, base)
        return cm
    return base


def _limite_ajustee(limite: float, facteur: float, sens: str) -> float:
    from brvm_alpha.portfolio import recommend as R

    x = float(limite) * float(facteur)
    return R.floor_to_tick(x) if sens == "achat" else R.ceil_to_tick(x)


def executer(carnet: _cn.Carnet, panels: Mapping[str, Any], jusqu_a: Any, *, mode: str = "limite", grille: Any = None,
             costs: Any = None, maintenant: Any = None, reglages: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Exécute sur papier les ordres en attente du carnet, séance par séance, jusqu'à ``jusqu_a`` ; ajoute au carnet les
    mouvements ``execution``, ``expiration``, ``ordre`` (ressaisie), ``dividende``, ``division`` et ``frais``. Idempotent :
    les séances déjà traitées (``papier.json`` du portefeuille) ne sont jamais rejouées. Rend les mouvements ajoutés et
    les mesures (:func:`mesures`). Aucune vente n'est créée : seuls les ordres du carnet sont exécutés. Tout le passage
    (état lu, séances rejouées, mouvements et état écrits) se fait sous le verrou d'écriture du portefeuille : deux
    exécutions simultanées ne rejouent jamais deux fois la même séance (code 4 si le verrou reste tenu)."""
    if mode not in MODES:
        raise ValueError(f"mode : {', '.join(MODES)}")
    _s.refuser_s1(jusqu_a, "l'exécution sur papier")
    if not carnet.fichier.exists():  # aucun carnet : rien à exécuter ni à écrire (aucun dossier créé)
        return _executer(carnet, panels, jusqu_a, mode=mode, grille=grille, costs=costs, maintenant=maintenant,
                         reglages=reglages)
    with _s.verrou_ecriture(carnet.dossier, quoi=f"exécution sur papier de {carnet.nom}"):
        return _executer(carnet, panels, jusqu_a, mode=mode, grille=grille, costs=costs, maintenant=maintenant,
                         reglages=reglages)


def _executer(carnet: _cn.Carnet, panels: Mapping[str, Any], jusqu_a: Any, *, mode: str, grille: Any, costs: Any,
              maintenant: Any, reglages: Mapping[str, Any] | None) -> dict[str, Any]:
    from brvm_alpha import fichiers
    from brvm_alpha.portfolio import recommend as R
    from brvm_alpha.quant import macro

    fin = _s.refuser_s1(jusqu_a, "l'exécution sur papier")
    part = float(_rg.lire(reglages, "suivi.participation_volume", 0.10))
    validite = int(_rg.lire(reglages, "suivi.validite_ordre_seances", 10))
    cm = _cm(grille, costs)
    forfait = float(grille.valeur("forfait_compte")) if grille is not None else 0.0
    etat_p = carnet.dossier / _ETAT
    st = json.loads(etat_p.read_text(encoding="utf-8")) if etat_p.exists() else {}
    deja = pd.Timestamp(st["jusqu_au"]).normalize() if st.get("jusqu_au") else None
    mouv = carnet.mouvements()
    if not mouv:
        return {"ajoutes": [], "mesures": mesures(carnet), "jusqu_au": None}
    d_min = min(pd.Timestamp(m["date"]).normalize() for m in mouv)
    seances = pd.DatetimeIndex(pd.to_datetime(panels["close"].index)).normalize()
    seances = seances[(seances > (deja if deja is not None else d_min - pd.Timedelta(days=1))) & (seances <= fin)]
    vol, val = _wide(panels, "volume"), _wide(panels, "value")
    px = _et.prix_reels(panels)
    detach = dividendes_detaches(panels)
    divs = divisions(panels)
    ajoutes: list[dict[str, Any]] = []
    tout = pd.DatetimeIndex(pd.to_datetime(panels["close"].index)).normalize()

    def ecrire(ms: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not ms:
            return []
        out = carnet.ajouter_plusieurs(ms, maintenant=maintenant, autoriser_double=True)
        ajoutes.extend(out)
        return out

    for d in seances:
        mouv = carnet.mouvements()
        ops = _cn.operations_depuis_mouvements(mouv)
        pos = _cn.positions_depuis_operations(ops, d - pd.Timedelta(days=1))
        held = {k: int(v["titres"]) for k, v in pos.items() if v["titres"] > 0}
        # 1. divisions du jour (titres × rapport ; ordres annulés et ressaisis)
        jour_div = divs[divs["date"] == d] if len(divs) else divs
        nouveaux: list[dict[str, Any]] = []
        rapports: dict[str, float] = {}
        for r in jour_div.itertuples(index=False):
            if held.get(r.symbole, 0) > 0:
                nouveaux.append({"type": "division", "date": d.date().isoformat(), "symbole": r.symbole,
                                 "rapport": float(r.rapport), "source": "papier"})
            rapports[r.symbole] = float(r.rapport)
        ecrire(nouveaux)
        # 2. dividendes payés ce jour (titres détenus la veille du détachement)
        nouveaux = []
        if len(detach):
            paie = detach[(detach["date_paiement"] == d)]
            for r in paie.itertuples(index=False):
                p_ex = _cn.positions_depuis_operations(ops, r.date_detachement - pd.Timedelta(days=1)).get(r.symbole)
                n = int(p_ex["titres"]) if p_ex else 0
                if n > 0 and r.net_par_titre > 0:
                    nouveaux.append({"type": "dividende", "date": d.date().isoformat(), "symbole": r.symbole,
                                     "titres": n, "net_par_titre": float(r.net_par_titre),
                                     "montant": float(R.round_fcfa(n * r.net_par_titre)),
                                     "date_detachement": r.date_detachement.date().isoformat(), "source": "papier"})
        ecrire(nouveaux)
        # 3. ordres en attente : annulation et ressaisie (détachement, division), exécution, expiration
        mouv = carnet.mouvements()
        ords = [o for o in _cn.etat_des_ordres(mouv) if o["etat"] == "en cours" and o["reste"] > 0
                and pd.Timestamp(o["date"]).normalize() < d]
        ex_jour = set(detach.loc[detach["date_detachement"] == d, "symbole"]) if len(detach) else set()
        ressaisies = []
        for o in ords:
            s = o["symbole"]
            if s in rapports or s in ex_jour:
                if s in rapports:
                    fac, titres = 1.0 / rapports[s], int(math.floor(o["reste"] * rapports[s] + 1e-9))
                else:
                    prev = px[s].loc[: d - pd.Timedelta(days=1)].dropna() if s in px.columns else pd.Series(dtype=float)
                    dv = float(detach.loc[(detach["symbole"] == s) & (detach["date_detachement"] == d), "net_par_titre"].sum())
                    ref = float(prev.iloc[-1]) if len(prev) else float(o.get("cours_reference") or 0)
                    fac, titres = ((ref - dv) / ref if ref > dv > 0 else 1.0), int(o["reste"])
                ressaisies.append({"type": "ordre", "date": d.date().isoformat(), "symbole": s, "sens": o["sens"],
                                   "titres": titres, "limite": _limite_ajustee(o["limite"], fac, o["sens"]),
                                   "cours_reference": _f(o.get("cours_reference")) * fac, "validite": o.get("validite", validite),
                                   "motif": o.get("motif"), "ressaisie_de": int(o["n"]),
                                   "date_decision": o.get("date_decision") or o["date"],
                                   "seances_ecoulees": _seances_ecoulees(o, tout, d),
                                   "raison": "division" if s in rapports else "détachement", "source": "papier"})
        ecrire(ressaisies)
        mouv = carnet.mouvements()
        ops = _cn.operations_depuis_mouvements(mouv)
        L = float(ops["montant_net"].sum()) if len(ops) else 0.0
        # produits de ventes non réglés : indisponibles avant le règlement (deux séances)
        bloque = 0.0
        for r in ops[ops["type"] == "vente"].itertuples(index=False):
            try:
                regle = R.settlement_date(r.date, tout)
            except ValueError:
                regle = pd.Timestamp(r.date) + pd.offsets.BDay(int(macro.settlement_lag(r.date)))
            if regle > d:
                bloque += float(r.montant_net)
        dispo = L - bloque
        ords = [o for o in _cn.etat_des_ordres(mouv) if o["etat"] == "en cours" and o["reste"] > 0
                and pd.Timestamp(o["date"]).normalize() < d]
        ords = [o for o in ords if o.get("ressaisie_de") is None or pd.Timestamp(o["date"]).normalize() <= d]
        ords.sort(key=lambda o: (0 if o["sens"] == "vente" else 1, int(o["n"])))
        nouveaux = []
        for o in ords + [o2 for o2 in _cn.etat_des_ordres(mouv) if o2.get("ressaisie_de") is not None
                         and pd.Timestamp(o2["date"]).normalize() == d and o2["etat"] == "en cours"]:
            s = o["symbole"]
            v_j = _f(vol[s].get(d)) if vol is not None and s in vol.columns and d in vol.index else 0.0
            a_j = _f(val[s].get(d)) if val is not None and s in val.columns and d in val.index else 0.0
            cap = int(math.floor(part * v_j + 1e-9))
            if v_j > 0 and a_j > 0 and cap > 0:
                vwap = a_j / v_j
                ok = True if mode == "test" else (vwap <= float(o["limite"]) + 1e-9 if o["sens"] == "achat"
                                                    else vwap >= float(o["limite"]) - 1e-9)
                q = min(int(o["reste"]), cap) if ok else 0
                if q > 0 and o["sens"] == "achat":
                    while q > 0:
                        fr = _frais_execution(q, vwap, cm, mode, panels, s, d)
                        if q * vwap + sum(fr.values()) <= dispo + 1e-6:
                            break
                        q -= 1
                if q > 0:
                    fr = _frais_execution(q, vwap, cm, mode, panels, s, d)
                    nouveaux.append({"type": "execution", "date": d.date().isoformat(), "symbole": s, "sens": o["sens"],
                                     "titres": int(q), "prix": float(vwap), "frais": fr, "ordre": int(o["n"]),
                                     "cours_reference": _f(o.get("cours_reference"), vwap), "source": "papier",
                                     "mode": mode})
                    if o["sens"] == "achat":
                        dispo -= q * vwap + sum(fr.values())
                    o["reste"] -= q
            if o["reste"] > 0 and _seances_ecoulees(o, tout, d) >= int(o.get("validite") or validite):
                nouveaux.append({"type": "expiration", "date": d.date().isoformat(), "symbole": s,
                                 "titres": int(o["reste"]), "ordre": int(o["n"]), "source": "papier"})
        ecrire(nouveaux)
        # 4. frais fixes en fin de trimestre civil (dernière séance du trimestre)
        fin_trim = (d + pd.offsets.QuarterEnd(0)).normalize()
        suiv = tout[tout > d]
        prochaine = suiv[0] if len(suiv) else pd.Timestamp(R.future_sessions(d, 1)[0])
        if prochaine > fin_trim:
            mouv = carnet.mouvements()
            ops = _cn.operations_depuis_mouvements(mouv)
            pos = _cn.positions_depuis_operations(ops, d)
            lignes = {k: v for k, v in pos.items() if v["titres"] > 0}
            if lignes:
                prec = [pd.Timestamp(m["date"]) for m in mouv if m.get("type") == "frais"]
                achats = [pd.Timestamp(m["date"]) for m in mouv if m.get("type") == "execution"]
                depuis = max(prec) if prec else (min(achats) if achats else d)
                jours = max(0, (d - depuis).days)
                T = sum(int(v["titres"]) * _f(px[k].loc[:d].dropna().iloc[-1]) for k, v in lignes.items()
                        if k in px.columns and px[k].loc[:d].notna().any())
                montant = R.round_fcfa((cm.annual_custody * T + cm.account_fee_per_line_fcfa * len(lignes) + forfait)
                                       * jours / 365.0)
                if montant > 0:
                    ecrire([{"type": "frais", "date": d.date().isoformat(), "nature": "garde et tenue de compte",
                             "montant": float(montant), "jours": int(jours), "source": "papier",
                             "hypothese": "prélèvement en fin de trimestre civil (date réelle inconnue)"}])
        st = {"jusqu_au": d.date().isoformat(), "mode": mode}
        fichiers.ecrire_atomique(etat_p, json.dumps(st, ensure_ascii=False) + "\n")
    return {"ajoutes": ajoutes, "mesures": mesures(carnet), "jusqu_au": st.get("jusqu_au"), "mode": mode}


def _seances_ecoulees(o: Mapping[str, Any], seances: pd.DatetimeIndex, d: pd.Timestamp) -> int:
    """Séances de bourse écoulées depuis la saisie de l'ordre d'origine, séance d comprise (ressaisies : le compteur
    continue)."""
    base = int(o.get("seances_ecoulees") or 0) if o.get("ressaisie_de") is not None else 0
    t0 = pd.Timestamp(o["date"]).normalize()
    n = int(((seances > t0) & (seances <= d)).sum())
    if o.get("ressaisie_de") is not None:
        n = int(((seances >= t0) & (seances <= d)).sum()) - 1
    return base + n


def _frais_execution(q: int, prix: float, cm: Any, mode: str, panels: Mapping[str, Any], s: str, d: pd.Timestamp) -> dict[str, float]:
    from brvm_alpha.portfolio import recommend as R

    a = q * prix
    f = R.fee_breakdown(a, cm)
    out = {"courtage": float(f["courtage"]), "taxe": float(f["tva"]), "brvm": float(f["brvm"]), "dcbr": float(f["dcbr"]),
           "autres": float(f["redevance"])}
    if mode == "test":
        mdv = None
        vv = _wide(panels, "value")
        if vv is not None and s in vv.columns:
            h = vv[s].loc[:d].tail(63)
            mdv = float(h.median()) if len(h) else None
        c = R.order_costs(q, prix, cm, side="achat", half_spread=float(cm.half_spread_default), mdv63=mdv)
        out["autres"] += float(c["implicites"])
    return out


def mesures(carnet: _cn.Carnet) -> dict[str, Any]:
    """Mesures de l'exécution sur papier (article E-L) : part des titres servis à 1, 3 et 10 séances ; prix payé contre
    dernier cours (cours de référence) et contre cours moyen du jour ; séances pour finir un ordre."""
    ords = [o for o in _cn.etat_des_ordres(carnet.mouvements()) if o.get("ressaisie_de") is None]
    if not ords:
        return {"n_ordres": 0}
    tout = carnet.mouvements()
    enfants: dict[int, list[dict[str, Any]]] = {}
    for o in _cn.etat_des_ordres(tout):
        if o.get("ressaisie_de") is not None:
            enfants.setdefault(int(o["ressaisie_de"]), []).append(o)
    demandes, servis = 0, {1: 0, 3: 0, 10: 0}
    ecart_ref, montant = 0.0, 0.0
    finir = []
    for o in ords:
        execs = list(o["executions"])
        file = [int(o["n"])]
        while file:
            for e in enfants.get(file.pop(), []):
                execs.extend(e["executions"])
                file.append(int(e["n"]))
        demandes += int(o["titres"])
        t0 = pd.Timestamp(o["date"]).normalize()
        jours = sorted({pd.Timestamp(e["date"]).normalize() for e in execs})
        rang = {j: i + 1 for i, j in enumerate(pd.bdate_range(t0 + pd.Timedelta(days=1), t0 + pd.Timedelta(days=30)))}
        for e in execs:
            k = rang.get(pd.Timestamp(e["date"]).normalize(), 99)
            for h in servis:
                if k <= h:
                    servis[h] += int(e["titres"])
            ref = _f(o.get("cours_reference"), e["prix"])
            ecart_ref += int(e["titres"]) * (e["prix"] - ref) * (1 if o["sens"] == "achat" else -1)
            montant += int(e["titres"]) * e["prix"]
        if sum(int(e["titres"]) for e in execs) >= int(o["titres"]) and jours:
            finir.append(rang.get(jours[-1], None))
    return {"n_ordres": len(ords), "titres_demandes": demandes,
            "part_servie": {f"{h}_seances": (servis[h] / demandes if demandes else None) for h in servis},
            "cout_contre_dernier_cours_fcfa": ecart_ref, "cout_contre_dernier_cours_part": ecart_ref / montant if montant else None,
            "prix_contre_cours_moyen": "égal par construction (exécution au cours moyen du jour)",
            "seances_pour_finir": [x for x in finir if x is not None]}


def controle_p8(lignes_test: list[Mapping[str, Any]], lignes_temoin: list[Mapping[str, Any]], *,
                tolerance_fcfa: float = 1.0) -> dict[str, Any]:
    """Contrôle P8 (§8.2) : l'exécution sur papier en mode ``test``, sans écart, contre le moteur (témoin REF-S2),
    semaine par semaine. Rend les semaines comparées et les écarts de valeur et d'ordres, **publiés** tels quels : si
    elles diffèrent, E-C et E-D sont lus avec cette réserve. Aucune décision n'en découle ici."""
    tem = {str(l["vendredi"]): l for l in lignes_temoin}
    ecarts = []
    n = 0
    for l in lignes_test:
        v = str(l["vendredi"])
        if v not in tem:
            continue
        n += 1
        dv = float(l["valeur"]) - float(tem[v]["valeur"])
        do = int(_f(l.get("titres_servis"))) - int(_f(tem[v].get("titres_servis")))
        if abs(dv) > tolerance_fcfa or do != 0:
            ecarts.append({"vendredi": v, "ecart_valeur_fcfa": dv, "ecart_titres_servis": do})
    return {"semaines_comparees": n, "conforme": n > 0 and not ecarts, "ecarts": ecarts,
            "mention": ("Mêmes valeurs et mêmes titres servis que le moteur." if n and not ecarts else
                        "Écarts publiés : E-C et E-D sont lus avec cette réserve (contrôle P8).")}
