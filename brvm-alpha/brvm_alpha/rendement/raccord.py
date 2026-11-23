"""Raccords du module « Rendement net et pertes » au moteur de l'ordre de bataille (cahier ``docs/RENDEMENT_NET.md``,
§4.3, §F13) : assistants appelés par ``portfolio.recommend`` seulement quand une option est demandée.

* :func:`options_execution` : options du plan (``_build_plan(options=…)``) et écarts à mentionner ;
* :func:`mention_ecart` : mention « Écart à la règle testée … » ou « Essai sur papier … » d'une sortie ;
* :func:`plan_arrondi_restes` : option ``arrondi="restes"`` (E-A) ;
* :func:`reinvestir_fin_de_mois` : option ``reinvestir`` (E-D) ;
* :func:`symboles_continuite` : option ``continuite`` (E-C) ;
* :func:`etat_journal_ref_s2` : état du journal du suivi sur papier REF-S2 dans les déclencheurs de revue.

Sans option, aucun de ces assistants ne change l'ordre : les quantités, les prix limites et les frais restent ceux de
la règle testée. Aucune écriture, aucun réseau ; S1 n'est jamais simulé.

Performance passée ≠ garantie. Aucun gain n'est garanti.
"""

from __future__ import annotations

import math
import warnings
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

from brvm_alpha import paths as _paths
from brvm_alpha import settings
from brvm_alpha.config import CostModel
from brvm_alpha.portfolio import recommend as R

__all__ = ["ECARTS_EXECUTION", "etat_journal_ref_s2", "mention_ecart", "options_execution", "plan_arrondi_restes",
           "reinvestir_fin_de_mois", "symboles_continuite"]


#: Options d'exécution du §F13 : identifiant de la déclaration du suivi (§8.3, §8.4), nom affiché, essai ou écart.
ECARTS_EXECUTION = {"arrondi": ("E-A", "arrondi « plus forts restes »", False),
                    "apport": ("E-B", "apport d'argent frais sans attendre la remise à niveau", False),
                    "completer": ("E-B", "compléter un ordre servi en partie", False),
                    "reinvestir": ("E-D", "réinvestissement de fin de mois", True),
                    "continuite": ("E-C", "continuité des données", True)}


def options_execution(*, memoire: Mapping[str, Any] | None, apport: Any, completer: bool, reinvestir: bool,
                      continuite: bool, arrondi: str, sessions: Any, pdir: Path | None
                      ) -> tuple[dict[str, Any], list[str]]:
    """Options du plan (``recommend._build_plan(options=…)``) et écarts à la règle testée à mentionner. Sans option :
    ``({}, [])``, le plan est celui de la règle testée à l'identique."""
    opts: dict[str, Any] = {}
    ecarts: list[str] = []
    if memoire and memoire.get("memoire_ref"):
        opts["memoire_ref"] = dict(memoire["memoire_ref"])  # §F13 a : la règle testée, sans écart
    if apport is not None:
        opts["sans_bande_achats"] = True
        ecarts.append("apport")
    if completer:
        opts["sans_bande_achats"] = True
        if memoire and memoire.get("non_servis"):
            opts["manque"] = dict(memoire["non_servis"])
        ecarts.append("completer")
    if reinvestir:
        opts["reinvestir"] = True
        ecarts.append("reinvestir")
    if continuite:
        sv = sessions if isinstance(sessions, pd.DataFrame) and "available" in sessions.columns else None
        if sv is None and pdir is not None and (pdir / "sessions.parquet").exists():
            try:
                sv = pd.read_parquet(pdir / "sessions.parquet", columns=["date", "available"])
            except Exception:  # noqa: BLE001 - table illisible : aucun trou détectable, rien ne change
                sv = None
        opts["continuite"] = {"sessions": sv, "fenetre": int(settings.get_param(
            settings.load_strategy_config(), "universe.min_history_sessions") or 126)}
        ecarts.append("continuite")
    if arrondi == "restes":
        ecarts.append("arrondi")
    return opts, ecarts


def mention_ecart(cle: str, jour: Any) -> str:
    """Mention portée par toute sortie produite avec une option du §F13 : écart déclaré (ou non) et jamais jugé ici."""
    ident, nom, essai = ECARTS_EXECUTION[cle]
    quand = None
    try:
        from brvm_alpha.suivi import declaration as _de

        j = pd.Timestamp(jour)
        j = j.tz_convert("UTC").tz_localize(None) if j.tzinfo is not None else j
        art = (_de.en_vigueur(j, _paths.REPO_ROOT / "reports" / "suivi_S2").get("articles") or {}).get(ident) or {}
        if art.get("date_utc") and "non" not in str(art.get("reponse") or "oui"):  # « non », « option 2 : non »
            quand = R._d(pd.Timestamp(str(art["date_utc"])[:10]))
    except Exception:  # noqa: BLE001 - déclaration illisible : « non déclaré »
        quand = None
    if essai:
        return (f"Essai sur papier : {nom} ({ident}). Déclaré le {quand} ; jugé sur le suivi seulement." if quand else
                f"Essai sur papier : {nom} ({ident}). Non déclaré à ce jour : il n'est jugé que sur le suivi, et "
                "seulement s'il est déclaré.")
    return (f"Écart à la règle testée : {nom} ({ident}). Décision d'exécution déclarée le {quand} ; non jugée." if quand
            else f"Écart à la règle testée : {nom} ({ident}). Décision d'exécution non déclarée ; non jugée.")


def plan_arrondi_restes(plan: Any, common: Mapping[str, Any], opts: dict[str, Any], *, variant: str, nav: float,
                        cash: float, costs: CostModel, cost_name: str, grille_sgi: Any, forcer: bool,
                        max_participation: float) -> Any:
    """Option ``arrondi="restes"`` (E-A, §F13 c) : ``rendement.liquidites.arrondi_restes`` sur le plan de la règle
    (quantités arrondies vers le bas), puis le même plan avec ces quantités (même décision du modèle). Refusée sur un
    tarif supposé sauf ``forcer`` (``ValueError``)."""
    from brvm_alpha.rendement import liquidites as _lq

    L = plan.lines
    o = {"valeur_portefeuille": nav, "liquidites_initiales": cash,
         "couts": R._cost_summary(L, nav, cash, costs, cost_name),
         "execution": {"participation_max_regle": float(max_participation), "reductions": dict(plan.reductions)},
         "lignes": L.to_dict("records") if len(L) else [],
         "explications": R._explanations(plan, common["t"], common["panels"])}
    ar = _lq.arrondi_restes(o, costs, grille_sgi, appliquer=True, forcer=forcer)
    plan.messages.append(f"arrondi « plus forts restes » (E-A) : {R._int(ar['titres_ajoutes'])} titre(s) ajouté(s), "
                         f"{R._fcfa(ar['francs_ajoutes'])} placés en plus, marge du pire cas {R._fcfa(ar['marge_pire_cas'])}"
                         + (f" ({ar['motif']})" if ar.get("motif") else ""))
    if not ar["lignes_ajoutees"]:
        return plan
    opts["cibles"] = {str(k): int(v) for k, v in ar["quantites"].items()}
    p2 = R._build_plan(variant=variant, **common, prebuilt=(plan.model, plan.decision), options=opts)
    p2.messages.append(plan.messages[-1])
    return p2


def _bulletins_manquants(sessions: Any, t: pd.Timestamp, fenetre: int) -> dict[str, Any] | None:
    """Séances sans bulletin (``available`` faux) parmi les ``fenetre`` dernières séances du calendrier jusqu'à ``t`` ;
    ``None`` sans table des séances (colonnes ``date`` et ``available``)."""
    if not isinstance(sessions, pd.DataFrame) or not {"date", "available"} <= set(sessions.columns):
        return None
    sv = sessions.assign(date=pd.to_datetime(sessions["date"])).sort_values("date")
    sv = sv[sv["date"] <= t].tail(int(fenetre))
    manq = sv[~sv["available"].astype(bool)]
    return {"n": int(len(manq)), "du": manq["date"].min() if len(manq) else None,
            "au": manq["date"].max() if len(manq) else None}


def symboles_continuite(cont: Mapping[str, Any], dec: Any, t: pd.Timestamp) -> dict[str, str]:
    """Option ``continuite`` (essai E-C, §F13 e) : titres dont la vente vient d'une inéligibilité calculée sur une
    fenêtre où des bulletins manquent ; ils sont gardés, sans achat. Les sorties pour cause réelle (suspension, veto,
    deux drapeaux R11, inéligibilité sur une fenêtre complète) restent : sans bulletin manquant, rien ne change."""
    fen = int(cont.get("fenetre") or 126)
    trou = _bulletins_manquants(cont.get("sessions"), t, fen)
    if not trou or not trou["n"]:
        return {}
    forced = dict(((dec.diagnostics.get("index") or {}).get("forced_exits") or {}))
    uni = dec.universe
    non_elig = (set(uni.index[~uni["eligible"].astype(bool)]) if isinstance(uni, pd.DataFrame)
                and "eligible" in uni.columns else set())
    out: dict[str, str] = {}
    for sym in sorted(set(forced) | non_elig):
        motif = str(forced.get(sym) or ("inéligible" if sym in non_elig else ""))
        if "inéligib" in motif:
            out[str(sym)] = (f"continuité des données (E-C) : {R._int(trou['n'])} bulletin(s) manquant(s) dans la "
                             f"fenêtre de {fen} séances ({motif}) ; position gardée, aucun achat")
    return out


def _a_la_borne_haute(panels: Mapping[str, Any], t: pd.Timestamp, sym: str, close: float) -> bool:
    """Le titre a clôturé à la borne haute de la séance ``t`` (référence du jour, ``ref_price``) : aucun achat."""
    ref = R._get(panels, "ref_price")
    if not isinstance(ref, pd.DataFrame) or t not in ref.index or sym not in ref.columns:
        return False
    rp = float(ref.loc[t, sym])
    if not (np.isfinite(rp) and rp > 0):
        return False
    return float(close) >= R.macro.price_band(rp)[1] - 1e-9


def reinvestir_fin_de_mois(lines: list[dict[str, Any]], opts: Mapping[str, Any], *, model: Any, variant: str,
                           t: pd.Timestamp, panels: Mapping[str, Any], nav: float, cash: float, costs: CostModel,
                           cfg: Mapping[str, Any], dec: Any, held_w: pd.Series, notes_arg: Any, notes_known_at: Any,
                           calendar_past: Any, max_participation: float, blocked: Mapping[str, Any],
                           status_t: Any) -> str:
    """Option ``reinvestir`` (essai E-D, §F13 d) : à la dernière séance du mois, ``D = liquidités − 2 % × V`` ; la ligne
    non bloquée la plus en retard sur son poids cible (``w × V − titres × cours``) ; montant permis
    ``M = min(D ; min(plafond ; w + 1 point) × V − valeur détenue)`` ; achat seulement si ``M ≥ S`` (``S = max(100 000 ;
    minimum par ordre ÷ taux de courtage)``), du plus grand nombre de titres dont le coût net tient dans M et dont le
    pire cas tient dans les liquidités. Une seule ligne ; aucune vente. Modifie ``lines`` ; rend le message du plan."""
    nom = "réinvestissement de fin de mois (E-D)"
    nxt = R.future_sessions(t, 1, calendar_past)[0]
    if (nxt.year, nxt.month) == (t.year, t.month):
        return f"{nom} : le {R._d(t)} n'est pas la dernière séance du mois ; aucun achat"
    if any(r["cibles"] > r["detenus"] for r in lines):
        return f"{nom} : la règle propose déjà des achats ce jour ; aucun achat de plus"
    m_ref, d_ref = model, dec
    if opts.get("memoire_ref"):
        # Entre deux remises à niveau, le modèle garde les positions : les poids cibles du jour viennent d'une
        # décision sans mémoire (comme l'ordre par défaut), lue seulement, jamais appliquée.
        from brvm_alpha.strategy import BrvmAlpha

        m_ref = BrvmAlpha(variant=variant, capital=nav, notes=notes_arg, notes_known_at=notes_known_at)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            d_ref = m_ref.decide(t, panels, held_w if len(held_w) else None)
    w_ref = d_ref.weights.astype(float).fillna(0.0)
    part = 1.0 - float((cfg.get("portfolio") or {}).get("gross_equity", 0.98))
    D = float(cash) - part * float(nav)
    risk = dec.risk

    def bloquee(r: Mapping[str, Any]) -> bool:
        sym = r["symbole"]
        if sym in blocked or (status_t is not None and str(status_t.get(sym, "")) == "suspended"):
            return True
        if isinstance(risk, pd.DataFrame) and sym in risk.index and "block_buys" in risk.columns \
                and bool(risk.loc[sym, "block_buys"]):
            return True
        return _a_la_borne_haute(panels, t, sym, r["cours_reference"])

    cand = [r for r in lines if float(w_ref.get(r["symbole"], 0.0)) > 0 and not bloquee(r)]
    if not cand:
        return f"{nom} : aucune ligne possible ; aucun achat"
    gap = {r["symbole"]: float(w_ref[r["symbole"]]) * nav - r["detenus"] * r["cours_reference"] for r in cand}
    r = max(cand, key=lambda x: (gap[x["symbole"]], x["symbole"]))
    sym, px = r["symbole"], float(r["cours_reference"])
    up = None
    try:
        up = (R._explain_one(m_ref, d_ref, t, panels, sym, held_w if len(held_w) else None).get("caps") or {}).get("upper")
    except Exception:  # noqa: BLE001 - plafond de ligne inconnu : seule la borne « w + 1 point » s'applique
        up = None
    cap = min(float(up) if up is not None else 1.0, float(w_ref[sym]) + 0.01)
    m_perm = min(D, cap * nav - r["detenus"] * px)
    seuil = max(100_000.0, float(costs.min_ticket_fcfa) / float(costs.sgi_commission)
                if costs.sgi_commission > 0 else 100_000.0)
    if m_perm < seuil:
        return (f"{nom} : montant permis sur {sym} {R._fcfa(max(m_perm, 0.0))}, sous le seuil de {R._fcfa(seuil)} ; aucun "
                "achat ce mois-ci")
    q = 0
    while True:
        q2 = q + 1
        tr = R.participation_schedule(q2, px, r["mdv63"], max_participation)
        oc = R.order_costs(q2, px, costs, side="achat", half_spread=r["demi_spread_pct"], mdv63=r["mdv63"], tranches=tr,
                         limit=r["limite_achat"])
        if not (q2 * px + oc["total"] <= m_perm and (r["detenus"] + q2) * px / nav <= cap + 1e-12
                and R._worst_case(tr, r["limite_achat"], costs, "achat") <= math.floor(cash)):
            break
        q = q2
    if q <= 0:
        return f"{nom} : aucun titre de {sym} ne tient dans le montant permis {R._fcfa(m_perm)} ; aucun achat"
    r["cibles"] = r["detenus"] + q
    r["note"] = (r["note"] + " ; " if r["note"] else "") + (f"réinvestissement de fin de mois (E-D) : +{R._int(q)} "
                                                            f"titre(s), montant permis {R._fcfa(m_perm)}")
    return f"{nom} : {sym} +{R._int(q)} titre(s) (montant permis {R._fcfa(m_perm)}, seuil {R._fcfa(seuil)})"


def etat_journal_ref_s2(dossier: str | Path | None = None) -> str | None:
    """État du journal du suivi sur papier REF-S2 (``<données>/suivi/REF-S2/semaines.csv``, lecture seule) : dernière
    semaine écrite et écart au marché en valeur de part. ``None`` tant que le journal n'existe pas ou est illisible."""
    try:
        from brvm_alpha.suivi import bulletin as _bu

        lignes = _bu.semaines_du_journal("REF-S2", dossier)
        if not lignes:
            return None
        der = lignes[-1]
        ec = der.get("ecart_au_marche")
        ec_txt = (f"écart au marché en valeur de part {R._pct(float(ec), 1, True)} depuis le début du suivi"
                  if isinstance(ec, (int, float)) and math.isfinite(float(ec)) else "écart au marché non calculé")
        return (f"Drawdown relatif contre le TR : aucun portefeuille réel suivi ; suivi sur papier du panier de "
                f"référence (REF-S2), semaine {R._int(der.get('semaine'))} au {R._d(der.get('vendredi'))} : {ec_txt} "
                "(sans argent réel : ce n'est pas une performance). Seuils à surveiller : −10 % alerte, −15 % "
                "exposition active ÷ 2, −20 % arrêt et indice discipliné")
    except Exception:  # noqa: BLE001 - journal absent ou illisible : mention d'origine
        return None
