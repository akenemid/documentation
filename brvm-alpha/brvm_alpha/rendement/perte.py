"""F4 — Ce que j'accepte de risquer → montant en actions ; F5 — Où dort le reste, et à quel taux.

Cahier ``docs/RENDEMENT_NET.md``, §F4 et §F5. Ce que l'utilisateur accepte de risquer sur 12 mois **n'est pas une
limite** : c'est une taille de montant en actions calculée pour une année comme 2018. Une baisse plus forte a
existé ; les dépassements sont écrits sur la même ligne, en FCFA.

* :func:`choc_ref_publie` lit le test S1 **publié** (``reports/validation_S1/trades.parquet`` et ``nav.parquet``,
  série ``REF_central_10M``) et les cours ajustés : rendement TR de 2018 de la partie investie, poids de la veille.
  Lecture d'un résultat publié, pas un test : aucune règle n'est simulée, aucun fichier n'est écrit ;
* :func:`poche` refait l'arithmétique de l'ordre pour un montant en actions A (quantités, frais, pire cas,
  dividendes), sans relancer ``recommend`` ;
* :func:`montant_actions` donne le plus grand A (au pas de 100 000 FCFA) dont la perte estimée d'une année comme
  2018, frais compris, ne dépasse pas X ; :func:`verifier_par_ordre` le confirme par l'ordre complet, au moyen
  d'une fonction **injectée** ``verifier(capital) -> ordre`` (10 appels au plus, jamais de récursion) ;
* :func:`reserve` (F5) : les intérêts de la réserve ne sont **jamais** déduits de la perte estimée.

Performance passée ≠ garantie. Aucun gain n'est garanti.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import numpy as np
import pandas as pd

from brvm_alpha import paths as _paths
from brvm_alpha.rendement import grille as _gr
from brvm_alpha.rendement import reglages as _rg
from brvm_alpha.rendement.reglages import ESTIMATION, FAIT, HYPOTHESE, R

__all__ = ["choc_ref_publie", "chocs", "montant_actions", "poche", "reserve", "table_de_choix", "verifier_par_ordre",
           "MESSAGE_ARRET", "MESSAGE_AUCUNE", "MESSAGE_DETENU", "MESSAGE_VENTES"]

MESSAGE_ARRET = "vérification arrêtée après {n} ordres : montant en actions à confirmer"
MESSAGE_VENTES = ("l'ordre de vérification propose des ventes ({ventes}) : aucune vente n'est proposée ; il sert seulement "
                  "à vérifier la perte estimée")
MESSAGE_DETENU = ("Titres déjà détenus pour {detenu} FCFA, soit {ecart} FCFA de plus que le montant en actions : aucune "
                  "vente n'est proposée.")
MESSAGE_AUCUNE = ("À ce tarif, le plus petit montant en actions à {n} lignes risque plus que ce que vous acceptez.")
RUN_REF = "REF_central_10M"


# ---------------------------------------------------------------------------
# Chocs par franc investi
# ---------------------------------------------------------------------------


def _large(panels: Mapping[str, Any] | None, cles: Sequence[str]) -> pd.DataFrame | None:
    if panels is None:
        return None
    for k in cles:
        v = panels.get(k) if isinstance(panels, Mapping) else None
        if isinstance(v, pd.DataFrame) and len(v):
            return v
    return None


def choc_ref_publie(validation_dir: str | Path | None = None, panels: Mapping[str, Any] | None = None, *,
                    run: str = RUN_REF, repli: float | None = None,
                    reglages: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Choc de 2018 subi par la règle de référence dans son test publié, par franc investi, hors frais (§F4,
    étape 2).

    Lecture seule de ``trades.parquet`` et ``nav.parquet`` (série ``run``) et des cours ajustés des panels
    (``close_adj`` et ``tr_index``) : positions = cumul par titre de ``qty`` ; pour chaque séance de 2018 (de la
    dernière séance de 2017 à la dernière de 2018), poids de la veille ``titres × cours ajusté ÷ valeur des titres`` ;
    ``r_d = Σ w × r_TR`` ; ``s_ref = |Π(1 + r_d) − 1|``, arrondi à 4 décimales comme dans le cahier (la mesure brute
    est rendue sous ``valeur_mesuree``). Contrôles rendus : VL de 2018, part investie moyenne, frais de transaction de
    2018. Fichiers illisibles : valeur de repli des réglages, ``source = "repli"``."""
    val_repli = float(repli if repli is not None else _rg.lire(reglages, "perte.choc_2018_ref_publie", 0.2932))
    base = {"valeur": val_repli, "source": "repli", "vl_2018": None, "part_investie_2018": None, "frais_2018": None,
            "statut": ESTIMATION, "run": run,
            "libelle": "lecture d'un résultat publié, pas un test"}
    d = Path(validation_dir) if validation_dir is not None else _paths.VALIDATION_DIR
    try:
        nav = pd.read_parquet(d / "nav.parquet")
        tr = pd.read_parquet(d / "trades.parquet")
        adj = _large(panels, ("close_adj", "close"))
        tri = _large(panels, ("tr_index",))
        if adj is None or tri is None:
            raise ValueError("cours ajustés ou indices TR absents des panels")
        nav = nav.assign(date=pd.to_datetime(nav["date"]))
        tr = tr.assign(date=pd.to_datetime(tr["date"]))
        v = nav[nav["serie"] == run].set_index("date")["valeur"].astype(float).sort_index()
        t = tr[tr["run_id"] == run]
        if not len(v) or not len(t):
            raise ValueError(f"série {run} absente des fichiers publiés")
        q = t.pivot_table(index="date", columns="symbol", values="qty", aggfunc="sum").fillna(0.0).cumsum()
        avant = v.index[v.index <= pd.Timestamp("2017-12-31")]
        if not len(avant):
            raise ValueError("aucune valeur publiée fin 2017")
        d0 = avant[-1]
        days = v.index[(v.index >= d0) & (v.index <= pd.Timestamp("2018-12-31"))]
        qd = q.reindex(q.index.union(days)).ffill().reindex(days).fillna(0.0)
        cols = [c for c in qd.columns if c in adj.columns and c in tri.columns]
        manquants = [c for c in qd.columns if c not in cols and float(qd[c].abs().sum()) > 0]
        if manquants:
            raise ValueError("cours absents pour " + ", ".join(sorted(manquants)))
        A = adj.sort_index().ffill()
        T = tri.sort_index().ffill()
        px = A.reindex(A.index.union(days)).ffill().reindex(days)[cols].astype(float)
        val = qd[cols] * px
        inv_val = val.sum(axis=1)
        w_prev = val.div(inv_val.where(inv_val > 0), axis=0).shift(1)
        ri = T.reindex(T.index.union(days)).ffill().reindex(days)[cols].astype(float).pct_change(fill_method=None)
        rb = (w_prev * ri.fillna(0.0)).sum(axis=1).iloc[1:]
        Rr = float(np.prod(1.0 + rb.to_numpy()) - 1.0)
        if not math.isfinite(Rr):
            raise ValueError("rendement non fini")
        part = (inv_val / v.reindex(days)).iloc[1:]
        t18 = t[(t["date"] > d0) & (t["date"] <= days[-1])]
        # Valeur retenue : la mesure arrondie à 4 décimales, comme le cahier (0,2932) ; la mesure brute reste rendue
        # (« valeur_mesuree »). Les tables du cahier (bornes « haut », P_vérifiée) sont ainsi retrouvées au franc.
        return {**base, "valeur": round(abs(Rr), 4), "valeur_mesuree": abs(Rr), "source": "mesuré", "rendement_2018": Rr,
                "vl_2018": float(v.loc[days[-1]] / v.loc[days[0]] - 1.0),
                "part_investie_2018": float(part.mean()), "frais_2018": float(t18["cost"].sum()) if "cost" in t18 else None,
                "debut": days[0].strftime("%Y-%m-%d"), "fin": days[-1].strftime("%Y-%m-%d"), "n_seances": int(len(days))}
    except Exception as exc:  # noqa: BLE001 - fichiers illisibles : valeur de repli, écrite comme telle
        return {**base, "motif": f"{exc.__class__.__name__} : {exc}",
                "mention": "choc de repli (fichiers publiés illisibles)"}


def _stress(o: Mapping[str, Any], code: str, variante: str) -> float | None:
    for s in o.get("stress") or []:
        if s.get("code") == code and str(s.get("variante") or "") == variante and s.get("perte_fcfa") is not None:
            return abs(float(s["perte_fcfa"]))
    return None


def chocs(ordre: Any, choc_ref: Mapping[str, Any] | float | None = None) -> dict[str, Any]:
    """Chocs par franc investi, lus dans l'ordre du capital total (``stress``) : ``beta`` (ST2 TR ÷ investi :
    marché de 2018 × sensibilité du panier), ``ref_publie`` (:func:`choc_ref_publie`), ``retenu`` = max des deux
    (le choc qui dimensionne), ``en_cours_d_annee`` (ST2 intra-annuel : pire moment de 2018), ``2017_2020``
    (ST1 TR : baisse de mars 2017 à octobre 2020). Stress absent : « non calculé » (``None``)."""
    o = _rg.en_dict(ordre)
    inv = float((o.get("couts") or {}).get("investi_apres") or 0)
    if isinstance(choc_ref, Mapping):
        s_ref, src = float(choc_ref.get("valeur")), str(choc_ref.get("source") or "mesuré")
    elif choc_ref is not None:
        s_ref, src = float(choc_ref), "fourni"
    else:
        s_ref, src = float(_rg.lire(None, "perte.choc_2018_ref_publie", 0.2932)), "repli"

    def par_franc(code: str, var: str) -> float | None:
        x = _stress(o, code, var)
        return x / inv if (x is not None and inv > 0) else None

    s_beta = par_franc("ST2", "TR")
    out = {"beta": s_beta, "ref_publie": s_ref, "ref_publie_source": src,
           "retenu": max(s_ref, s_beta) if s_beta is not None else s_ref,
           "en_cours_d_annee": par_franc("ST2", "intra-annuel"), "2017_2020": par_franc("ST1", "TR"),
           "investi_ordre": int(inv), "statut": ESTIMATION}
    if src == "repli":
        out["mention"] = "choc de repli"
    return out


# ---------------------------------------------------------------------------
# Arithmétique d'un montant en actions
# ---------------------------------------------------------------------------


def _net_par_titre(o: Mapping[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    for d in o.get("dividendes") or []:
        v = d.get("dividende_net_prevu_par_titre")
        if v is None or (isinstance(v, float) and not math.isfinite(v)):
            v = 0.0
        out[str(d["symbole"])] = out.get(str(d["symbole"]), 0.0) + float(v)
    return out


def _cibles(o: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [l for l in (o.get("lignes") or []) if float(l.get("poids_cible") or 0) > 0]


def poche(ordre: Any, A: float, costs: Any = None, grille: _gr.GrilleSGI | None = None, *,
          _cache: dict | None = None) -> dict[str, Any]:
    """Montant en actions ``A`` (§F4, étape 3) : ``q_i = ⌊w_i × A ÷ p_i + 1e-9⌋`` ; tranches à 10 % de la MDV63 ;
    coûts ``order_costs`` (côté achat, demi-écart et MDV63 de la ligne, limite d'achat).

    Rend investi ``I``, frais d'achat ``e``, frais annuels ``a`` (garde + tenue par ligne + forfait + frais hors
    modèle), lignes ``n``, provision du pire cas ``pc``, dividendes nets attendus ``d``, quantités et poids."""
    o = _rg.en_dict(ordre)
    base = _gr.cost_model_de(o, costs)
    if grille is not None:
        cm, forfait = _gr.vers_cost_model(grille, base)
    else:
        cm, forfait = base, float((o.get("couts") or {}).get("forfait_compte_annuel") or 0.0)
    part_max = float((o.get("execution") or {}).get("participation_max_regle") or 0.10)
    nps = _net_par_titre(o)
    A = float(A)
    inv = e = pc = d = n = 0
    q: dict[str, int] = {}
    big = 0.0
    big_sym = None
    for l in _cibles(o):
        p = float(l["cours_reference"])
        qi = int(math.floor(float(l["poids_cible"]) * A / p + 1e-9))
        q[str(l["symbole"])] = qi
        if qi <= 0:
            continue
        mdv = l.get("mdv63")
        mdv = float(mdv) if mdv is not None else None
        tr = R.participation_schedule(qi, p, mdv, part_max)
        lim = float(l["limite_achat"])
        oc = R.order_costs(qi, p, cm, side="achat", half_spread=float(l.get("demi_spread_pct") or 0.0), mdv63=mdv,
                           tranches=tr, limit=lim)
        inv += int(oc["brut"])
        e += int(oc["total"])
        pc += int(R._worst_case(tr, lim, cm, "achat"))
        n += 1
        d += int(R.round_fcfa(qi * nps.get(str(l["symbole"]), 0.0)))
        if qi * p > big:
            big, big_sym = qi * p, str(l["symbole"])
    garde = int(R.round_fcfa(cm.annual_custody * inv))
    tenue = int(R.round_fcfa(cm.account_fee_per_line_fcfa * n))
    hm = _gr.frais_hors_modele(grille, {"garde_annuelle": garde, "tenue_compte_annuelle": tenue},
                               {"net": d, "n_paiements": sum(1 for s, x in q.items() if x > 0 and nps.get(s, 0) > 0)},
                               None, forfait)["total"] if grille is not None else 0
    a = garde + tenue + int(R.round_fcfa(forfait)) + int(hm)
    prix = {str(l["symbole"]): float(l["cours_reference"]) for l in _cibles(o)}
    w = {s: qi * prix[s] / A for s, qi in q.items() if qi > 0} if A > 0 else {}
    return {"A": int(round(A)), "investi": int(inv), "frais_achat": int(e), "frais_annuels": int(a), "garde": garde,
            "tenue": tenue, "forfait": int(R.round_fcfa(forfait)), "hors_modele": int(hm), "lignes": int(n),
            "lignes_cibles": len(_cibles(o)), "pire_cas": int(pc), "dividendes": int(d), "quantites": q, "poids": w,
            "plus_grosse_ligne": big_sym, "un_titre_en_moins": int(R.round_fcfa(0.30 * big)),
            "frais_an1": int(e + a)}


def _P(pp: Mapping[str, Any], s: float) -> float:
    return float(s) * float(pp["investi"]) + float(pp["frais_achat"]) + float(pp["frais_annuels"])


def _grille_pas(K: float, pas: int) -> list[int]:
    out = list(range(int(pas), int(math.floor(K)) + 1, int(pas)))
    if not out or out[-1] != int(math.floor(K)):
        out.append(int(math.floor(K)))
    return out


def montant_actions(ordre: Any, X: float, costs: Any = None, grille: _gr.GrilleSGI | None = None,
                    choc: Mapping[str, Any] | None = None, *, pas: int | None = None, K: float | None = None,
                    reglages: Mapping[str, Any] | None = None, _cache: dict | None = None) -> dict[str, Any]:
    """Montant en actions (§F4, étape 5) : A* = le plus grand A de {pas, 2 × pas, …, K} tel que
    ``P(A) = s_dim × I(A) + e(A) + a(A) ≤ X``, toutes les lignes cibles présentes et ``pire cas ≤ A``. Les
    intérêts de la réserve n'entrent jamais dans P(A). Aucun A : A* = 0."""
    o = _rg.en_dict(ordre)
    costs = _gr.cost_model_de(o, costs)
    ch = dict(choc) if choc is not None else chocs(o)
    s = float(ch["retenu"])
    p = int(pas if pas is not None else _rg.lire(reglages, "perte.pas_fcfa", 100_000))
    KK = float(K if K is not None else (o.get("capital") or o.get("valeur_portefeuille")))
    cache = _cache if _cache is not None else {}
    n_cibles = len(_cibles(o))
    best = 0
    for A in _grille_pas(KK, p):
        pp = cache.get(A)
        if pp is None:
            pp = cache[A] = poche(o, A, costs, grille)
        if pp["lignes"] == n_cibles and pp["pire_cas"] <= A and _P(pp, s) <= float(X):
            best = A
    out: dict[str, Any] = {"X": float(X), "A": int(best), "pas": p, "choc_retenu": s}
    if best > 0:
        pp = cache[best]
        out.update({"poche": pp, "P": _P(pp, s)})
        nxt = best + p
        if nxt <= KK:
            pn = cache.get(nxt) or poche(o, nxt, costs, grille)
            out["P_pas_suivant"] = _P(pn, s)
    else:
        out["message"] = MESSAGE_AUCUNE.format(n=n_cibles)
    return out


def _vue_verification(O: Mapping[str, Any], s_ref: float) -> dict[str, Any]:
    c = O.get("couts") or {}
    inv = float(c.get("investi_apres") or 0)
    e = int(c.get("total") or 0)
    a = int(c.get("garde_annuelle") or 0) + int(c.get("tenue_compte_annuelle") or 0) + int(c.get("forfait_compte_annuel") or 0)
    st2 = _stress(O, "ST2", "TR")
    intra = _stress(O, "ST2", "intra-annuel")
    st1 = _stress(O, "ST1", "TR")
    pv = max(s_ref * inv, st2 if st2 is not None else 0.0) + e + a
    div = int((O.get("revenus") or {}).get("net") or 0)
    return {"investi": int(inv), "frais_achat": e, "frais_annuels": a, "frais_an1": e + a,
            "stress_2018_plus_frais": (st2 + e + a) if st2 is not None else None, "P_verifiee": pv,
            "pire_moment_2018_plus_frais": (intra + e + a) if intra is not None else None,
            "baisse_2017_2020_plus_frais": (st1 + e + a) if st1 is not None else None, "dividendes": div,
            "pire_cas": int(c.get("achats_pire_cas") or 0),
            "reductions": dict((O.get("execution") or {}).get("reductions") or {})}


def verifier_par_ordre(A: int, X: float, choc: Mapping[str, Any], verifier: Callable[[float], Any], *,
                       pas: int = 100_000, max_appels: int | None = None,
                       reglages: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Vérification par l'ordre complet (§F4, étape 6), seulement quand X est choisi.

    ``verifier(capital) -> ordre`` est **injecté** (la phase de raccord y branchera
    ``recommend(..., rendement=False)``) : ``P_vérifiée = max(s_ref × investi ; |ST2 TR|) + frais d'achat + frais
    annuels`` de l'ordre O_A. Tant que ``P_vérifiée > X`` et ``A > 0`` : A ← A − pas et nouvel ordre, 10 appels au
    plus. Plafond atteint sans valeur vérifiée : A = 0 et le message « vérification arrêtée après 10 ordres :
    montant en actions à confirmer ». Rend le dernier ordre vérifié (``ordre``) et le nombre d'appels."""
    n_max = int(max_appels if max_appels is not None else _rg.lire(reglages, "perte.verification_appels_max", 10))
    s_ref = float(choc.get("ref_publie") if isinstance(choc, Mapping) else choc)
    a_cur = int(A)
    appels = 0
    essais: list[dict[str, Any]] = []
    while a_cur > 0 and appels < n_max:
        O = verifier(float(a_cur))
        appels += 1
        od = _rg.en_dict(O)
        vue = _vue_verification(od, s_ref)
        essais.append({"A": a_cur, "P_verifiee": vue["P_verifiee"]})
        if vue["P_verifiee"] <= float(X):
            ventes = [str(l.get("symbole")) for l in (od.get("lignes") or [])
                      if l.get("sens") == "vente" and int(l.get("quantite") or 0) > 0]
            out_ok = {"A": a_cur, "verifie_par_ordre": True, "appels": appels, "ordre": O, "vue": vue, "essais": essais,
                      "quantites_reduites": bool(vue["reductions"]),
                      "mention": "quantités réduites par la provision" if vue["reductions"] else ""}
            if ventes:
                # §F4, cas limite 4 : aucune vente n'est proposée. L'ordre sert à la vérification, il n'est pas rendu
                # comme ordre de la poche (l'appelant garde l'ordre du capital total).
                out_ok.update({"ordre": None, "ventes_refusees": ventes,
                               "mention_ventes": MESSAGE_VENTES.format(ventes=", ".join(sorted(ventes)))})
            return out_ok
        a_cur -= int(pas)
    out = {"A": 0, "verifie_par_ordre": False, "appels": appels, "ordre": None, "vue": None, "essais": essais}
    if appels >= n_max:
        out["message"] = MESSAGE_ARRET.format(n=n_max)
    return out


# ---------------------------------------------------------------------------
# Table de choix (quand X n'est pas saisi) et ligne retenue
# ---------------------------------------------------------------------------


def _ligne(o: Mapping[str, Any], X: float | None, pp: Mapping[str, Any], ch: Mapping[str, Any], K: float,
           lecteur: Any, tout: Mapping[str, Any] | None, s_beta_poche: float | None = None) -> dict[str, Any]:
    I, e, a, d = float(pp["investi"]), float(pp["frais_achat"]), float(pp["frais_annuels"]), float(pp["dividendes"])
    an1 = e + a
    s_ref = float(ch["ref_publie"])
    sb = s_beta_poche if s_beta_poche is not None else ch.get("beta")
    bas = sb * I + an1 if sb is not None else None
    haut = s_ref * I + an1
    pm = ch["en_cours_d_annee"] * I + an1 if ch.get("en_cours_d_annee") is not None else None
    lg = ch["2017_2020"] * I + an1 if ch.get("2017_2020") is not None else None
    dep_pm = bool(X is not None and pm is not None and pm > float(X))
    dep_lg = bool(X is not None and lg is not None and lg > float(X))
    r1, r2 = d - e - a, d - a
    mention = ""
    if r2 < 0:
        mention = "frais > dividendes"
    elif r1 < 0:
        mention = "la 1re année, les frais dépassent les dividendes"
    ordi: dict[str, Any] = {"prudente": None, "flatteuse": None}
    freq: dict[str, Any] = {"prudente": None, "flatteuse": None}
    if lecteur is not None and pp["A"] > 0:
        try:
            lu = lecteur.poche(pp)
            ordi = {"prudente": lu["mediane_prudente_fcfa"], "flatteuse": lu["mediane_flatteuse_fcfa"]}
            freq = {"prudente": lu["p_perte_prudente"], "flatteuse": lu["p_perte_flatteuse"]}
        except Exception as exc:  # noqa: BLE001 - lecture du passé indisponible : « non calculé »
            ordi = {"prudente": None, "flatteuse": None, "erreur": str(exc)}
    prix = prix_fl = None
    if tout is not None and ordi.get("prudente") is not None and (tout.get("annee_ordinaire") or {}).get("prudente") is not None:
        prix = float(tout["annee_ordinaire"]["prudente"]) - float(ordi["prudente"])
    if tout is not None and ordi.get("flatteuse") is not None and (tout.get("annee_ordinaire") or {}).get("flatteuse") is not None:
        prix_fl = float(tout["annee_ordinaire"]["flatteuse"]) - float(ordi["flatteuse"])  # détail seulement (PH_FLATTE)
    return {"perte_toleree": None if X is None else float(X), "tout": X is None, "en_actions": int(pp["A"]),
            "reserve": int(round(K - pp["A"])), "investi": int(I), "frais_an1": int(an1), "frais_achat": int(e),
            "frais_annuels": int(a), "dividendes": int(d), "annee_2018": [bas, haut],
            "pire_moment_2018": pm, "baisse_2017_2020": lg, "depasse": {"pire_moment": dep_pm, "2017_2020": dep_lg},
            "rapport_2017_2020_sur_2018": (lg / haut) if (lg is not None and haut) else None,
            "reste_an1": int(r1), "reste_suivant": int(r2), "annee_ordinaire": ordi, "frequence_perte": freq,
            "prix_prudence": prix, "prix_prudence_flatteuse": prix_fl, "mention": mention,
            "un_titre_en_moins": int(pp["un_titre_en_moins"]),
            "plus_grosse_ligne": pp.get("plus_grosse_ligne"), "lignes": int(pp["lignes"]), "pire_cas": int(pp["pire_cas"]),
            "statut": ESTIMATION}


def table_de_choix(ordre: Any, costs: Any = None, grille: _gr.GrilleSGI | None = None,
                   choc: Mapping[str, Any] | None = None, lecteur: Any = None, *, parts: Sequence[float] | None = None,
                   reglages: Mapping[str, Any] | None = None, _cache: dict | None = None) -> list[dict[str, Any]]:
    """Table de choix (§F4, étape 8) : une ligne par part de ``perte.choix_parts`` (X = part × K), plus la ligne
    « tout » (tout en actions, sans X). Rien n'est choisi à la place de l'utilisateur.

    ``lecteur`` : lecteur du passé (``risque.LecteurPoche``) pour l'« année ordinaire » (prudente et flatteuse)."""
    o = _rg.en_dict(ordre)
    costs = _gr.cost_model_de(o, costs)
    ch = dict(choc) if choc is not None else chocs(o)
    K = float(o.get("capital") or o.get("valeur_portefeuille"))
    ps = [float(x) for x in (parts if parts is not None else _rg.lire(reglages, "perte.choix_parts", [0.05, 0.10, 0.20]))]
    cache = _cache if _cache is not None else {}
    pk = cache.get(int(math.floor(K))) or poche(o, K, costs, grille)
    tout = _ligne(o, None, pk, ch, K, lecteur, None)
    rows = []
    for part in ps:
        X = part * K
        m = montant_actions(o, X, costs, grille, ch, K=K, reglages=reglages, _cache=cache)
        if m["A"] > 0:
            r = _ligne(o, X, m["poche"], ch, K, lecteur, tout)
            r["P"] = m["P"]
            r["P_pas_suivant"] = m.get("P_pas_suivant")
        else:
            r = {"perte_toleree": X, "tout": False, "en_actions": 0, "reserve": int(round(K)), "investi": 0,
                 "message": m.get("message"), "statut": ESTIMATION, "depasse": {"pire_moment": False, "2017_2020": False},
                 "annee_ordinaire": {"prudente": None, "flatteuse": None}}
        r["part"] = part
        rows.append(r)
    tout["prix_prudence"] = 0.0 if (tout.get("annee_ordinaire") or {}).get("prudente") is not None else None
    tout["prix_prudence_flatteuse"] = 0.0 if (tout.get("annee_ordinaire") or {}).get("flatteuse") is not None else None
    tout["P"] = _P(pk, float(ch["retenu"]))
    rows.append(tout)
    return rows


def ligne_choisie(ordre: Any, X: float, costs: Any = None, grille: _gr.GrilleSGI | None = None,
                  choc: Mapping[str, Any] | None = None, lecteur: Any = None, *,
                  verifier: Callable[[float], Any] | None = None, reglages: Mapping[str, Any] | None = None,
                  choix_verifie: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Ligne retenue quand X est choisi : arithmétique de l'étape 5, puis, si ``verifier`` est donné (ou
    ``choix_verifie``, résultat déjà calculé), valeurs de l'ordre exact de la poche (étape 6) qui remplacent celles
    de la formule."""
    o = _rg.en_dict(ordre)
    costs = _gr.cost_model_de(o, costs)
    ch = dict(choc) if choc is not None else chocs(o)
    K = float(o.get("capital") or o.get("valeur_portefeuille"))
    if float(X) <= 0:
        raise ValueError("ce que j'accepte de risquer doit être un montant positif")
    cache: dict = {}
    m = montant_actions(o, X, costs, grille, ch, K=K, reglages=reglages, _cache=cache)
    pk = poche(o, K, costs, grille)
    tout = _ligne(o, None, pk, ch, K, lecteur, None)
    if m["A"] <= 0:
        return _avec_detenu(o, {"perte_toleree": float(X), "en_actions": 0, "reserve": int(round(K)),
                                "message": m.get("message"), "verifie_par_ordre": False, "appels": 0, "statut": ESTIMATION})
    r = _ligne(o, X, m["poche"], ch, K, lecteur, tout)
    r.update({"P": m["P"], "P_pas_suivant": m.get("P_pas_suivant"), "verifie_par_ordre": False, "appels": 0,
              "arithmetique": {"A": m["A"], "P": m["P"]}})
    if r["en_actions"] >= int(math.floor(K)):
        r["rappel"] = _rg.PH_RISQUE
    v = choix_verifie
    if v is None and verifier is not None:
        v = verifier_par_ordre(m["A"], X, ch, verifier, pas=m["pas"], reglages=reglages)
    if v is not None and not v.get("verifie_par_ordre"):
        # §F4, étape 6 : aucune valeur vérifiée sous X → A* = 0, tout en réserve ; les montants de la formule ne
        # s'affichent pas (« non calculé ») ; le message d'arrêt et le nombre d'appels restent.
        return _avec_detenu(o, {"perte_toleree": float(X), "en_actions": 0, "reserve": int(round(K)), "investi": None,
                "annee_2018": [None, None], "pire_moment_2018": None, "baisse_2017_2020": None,
                "annee_ordinaire": {"prudente": None, "flatteuse": None}, "prix_prudence": None,
                "depasse": {"pire_moment": False, "2017_2020": False},
                "message": v.get("message") or MESSAGE_ARRET.format(n=int(v.get("appels") or 0)),
                "verifie_par_ordre": False, "appels": int(v.get("appels") or 0), "essais": v.get("essais") or [],
                "a_confirmer": True, "arithmetique": {"A": m["A"], "P": m["P"]}, "statut": ESTIMATION,
                "ordre_tout": {"annee_ordinaire": tout["annee_ordinaire"]}})
    if v is not None:
        r["verifie_par_ordre"] = bool(v.get("verifie_par_ordre"))
        r["appels"] = int(v.get("appels") or 0)
        if v.get("message"):
            r["message"] = v["message"]
        if v.get("verifie_par_ordre") and v.get("vue"):
            vue = v["vue"]
            A = int(v["A"])
            O = _rg.en_dict(v["ordre"]) if v.get("ordre") is not None else None
            pa = poche(O, A, costs, grille) if O is not None else m["poche"]
            ch_a = chocs(O, ch["ref_publie"]) if O is not None else ch
            exact = {"investi": vue["investi"], "frais_achat": vue["frais_achat"], "frais_annuels": vue["frais_annuels"],
                     "dividendes": vue["dividendes"], "pire_cas": vue["pire_cas"], "A": A,
                     "lignes": pa["lignes"], "un_titre_en_moins": pa["un_titre_en_moins"],
                     "plus_grosse_ligne": pa["plus_grosse_ligne"], "poids": pa["poids"], "quantites": pa["quantites"]}
            r2 = _ligne(o, X, exact, ch, K, lecteur, tout, s_beta_poche=ch_a.get("beta"))
            r2.update({"P_verifiee": vue["P_verifiee"], "stress_2018_plus_frais": vue["stress_2018_plus_frais"],
                       "pire_moment_2018_ordre": vue["pire_moment_2018_plus_frais"],
                       "baisse_2017_2020_ordre": vue["baisse_2017_2020_plus_frais"],
                       "verifie_par_ordre": True, "appels": r["appels"], "arithmetique": r["arithmetique"],
                       "mention_ordre": v.get("mention") or ""})
            if vue["pire_moment_2018_plus_frais"] is not None:
                r2["pire_moment_2018"] = vue["pire_moment_2018_plus_frais"]
                r2["depasse"]["pire_moment"] = bool(vue["pire_moment_2018_plus_frais"] > float(X))
            if vue["baisse_2017_2020_plus_frais"] is not None:
                r2["baisse_2017_2020"] = vue["baisse_2017_2020_plus_frais"]
                r2["depasse"]["2017_2020"] = bool(vue["baisse_2017_2020_plus_frais"] > float(X))
                r2["rapport_2017_2020_sur_2018"] = r2["baisse_2017_2020"] / max(vue["P_verifiee"], 1.0)
            if "rappel" in r:
                r2["rappel"] = r["rappel"]
            if v.get("mention_ventes"):
                r2["mention_ventes"] = v["mention_ventes"]
                r2["ventes_refusees"] = list(v.get("ventes_refusees") or [])
            r2["_ordre"] = v.get("ordre")
            r = r2
    r["ordre_tout"] = {"annee_ordinaire": tout["annee_ordinaire"]}
    return _avec_detenu(o, r)


def _avec_detenu(o: Mapping[str, Any], r: dict[str, Any]) -> dict[str, Any]:
    """§F4, cas limite 4 : titres déjà détenus pour plus que A* : l'écart est affiché ; aucune vente n'est proposée."""
    detenu = sum(int(l.get("detenus") or 0) * float(l.get("cours_reference") or 0) for l in (o.get("lignes") or []))
    if detenu > float(r.get("en_actions") or 0) + 0.5:
        ecart = int(R.round_fcfa(detenu - float(r.get("en_actions") or 0)))
        r["detenu"] = {"valeur": int(R.round_fcfa(detenu)), "ecart": ecart,
                       "texte": MESSAGE_DETENU.format(detenu=_rg.fcfa(detenu, unite=False), ecart=_rg.fcfa(ecart, unite=False))}
    return r


# ---------------------------------------------------------------------------
# F5 — la réserve
# ---------------------------------------------------------------------------


def reserve(K: float, A: float, r: float | None = None, statut: str | None = None, *,
            reglages: Mapping[str, Any] | None = None, support: str = "") -> dict[str, Any]:
    """Réserve = K − A (§F5). Valeur d'un point de taux = réserve × 0,01 par an ; intérêts attendus = r × réserve.

    ``r`` n'entre **jamais** dans la perte estimée ni dans A* (``deduit_de_la_perte`` vaut toujours ``False``).
    ``r`` vide : compté à 0, « taux inconnu ». Tout chiffre qui dépend de r > 0 est « supposé » tant que le statut
    du taux n'est pas ``relevé`` (``PH_RESERVE``). Taux au-delà de 15 % ou négatif : refusé (``ValueError``)."""
    tmax = float(_rg.lire(reglages, "reserve.taux_max", 0.15))
    if r is not None and (not math.isfinite(float(r)) or float(r) < 0 or float(r) > tmax + 1e-12):
        raise ValueError(f"taux de la réserve : {_rg.pct(r, 2)} est hors de la plage acceptée (0 à {_rg.pct(tmax, 0)})")
    res = max(0.0, float(K) - float(A))
    rr = 0.0 if r is None else float(r)
    releve = str(statut or "").lower() in ("relevé", "releve")
    st_int = (ESTIMATION if releve else HYPOTHESE) if rr > 0 else HYPOTHESE
    phrases = [_rg.PH_INTERETS]
    if rr > 0 and not releve:
        phrases.insert(0, _rg.PH_RESERVE)
    return {"montant": int(round(res)), "taux": None if r is None else rr, "taux_connu": r is not None,
            "statut": st_int, "mot_statut": _rg.mot_statut(st_int), "statut_valeur_d_un_point": FAIT,
            "statut_taux": statut or ("supposé" if r is not None else "inconnu"),
            "support": support, "interets": int(R.round_fcfa(rr * res)), "valeur_d_un_point": int(R.round_fcfa(0.01 * res)),
            "deduit_de_la_perte": False, "masque": res <= 0, "phrases": phrases,
            "mention": "taux inconnu : compté à 0 %" if r is None else ""}
