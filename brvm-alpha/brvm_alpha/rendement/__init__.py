"""Module « Rendement net et pertes » (cahier des charges ``docs/RENDEMENT_NET.md``).

Ce module ne promet aucun gain et ne rend aucune perte impossible. Il ferme les fuites évitables (frais, impôts,
argent qui dort, arrondis, exécution), donne à l'utilisateur la maîtrise de ce qu'il accepte de risquer et ne
présente aucune règle nouvelle comme validée. Il ne change pas l'ordre de bataille par défaut : il **ajoute** des
blocs d'information et des options, toutes éteintes par défaut.

Point d'entrée : :func:`construire` ``(ordre, …) -> dict`` assemble la clé ``rendement_net`` de l'ordre de bataille
(§4.5). Chaque bloc est calculé à part ; un bloc en échec vaut ``{"erreur": "<message>"}`` et s'affiche « non
calculé », jamais comme un zéro. :func:`construire` **ne lève jamais** d'exception.

Performance passée ≠ garantie. Aucun gain n'est garanti.
"""

from __future__ import annotations

import contextvars
import datetime as _dt
import math
import time
from pathlib import Path
from typing import Any, Callable, Mapping

from brvm_alpha.rendement import alertes, bilan, grille, liquidites, perte, plan, reglages, rendu, risque
from brvm_alpha.rendement.reglages import BANNER

__all__ = ["VERSION", "alertes", "bilan", "construire", "grille", "liquidites", "perte", "plan", "pour_ordre_poche",
           "reglages", "rendu", "risque"]

#: Blocs gardés de l'ordre du capital total quand l'ordre affiché est celui de la poche (§F4, Intégration) : les
#: décisions de l'écran (table de choix, ligne retenue, réserve, plan) se prennent sur le capital total.
BLOCS_DU_CAPITAL_TOTAL = ("perte", "reserve", "plan")

VERSION = 1
_EN_COURS: contextvars.ContextVar[bool] = contextvars.ContextVar("rendement_en_cours", default=False)


def _bloc(fn: Callable[[], Any]) -> Any:
    try:
        return fn()
    except MemoryError:  # mémoire insuffisante : la commande s'arrête (code 6)
        raise
    except Exception as exc:  # noqa: BLE001 - un bloc en échec ne doit jamais faire tomber l'ordre de bataille
        return {"erreur": f"{exc.__class__.__name__} : {exc}"}


def _ok(b: Any) -> bool:
    return isinstance(b, Mapping) and not b.get("erreur")


def _montant(x: Any, K: float) -> float | None:
    """Montant en FCFA ou part du capital (« 10 % », « 10% », 0,1 si < 1)."""
    if x is None or x == "":
        return None
    if isinstance(x, str):
        s = x.strip().replace("\u202f", "").replace(" ", "").replace(",", ".")
        if s.endswith("%"):
            return float(s[:-1]) / 100.0 * K
        return float(s)
    v = float(x)
    return v * K if 0 < v < 1 else v


def _sans_objets(d: Any) -> Any:
    """Retire les objets non sérialisables (ordres complets) d'un résultat avant de le ranger dans le JSON."""
    if isinstance(d, Mapping):
        return {k: _sans_objets(v) for k, v in d.items() if k not in ("ordre", "_ordre")}
    if isinstance(d, (list, tuple)):
        return [_sans_objets(v) for v in d]
    if isinstance(d, float) and not math.isfinite(d):
        return None
    if hasattr(d, "item") and not isinstance(d, (str, bytes)):
        try:
            return d.item()
        except MemoryError:  # mémoire insuffisante : la commande s'arrête (code 6)
            raise
        except Exception:  # noqa: BLE001
            return d
    return d


def construire(ordre: Any, *, panels: Mapping[str, Any] | None = None, asof: Any = None, capital: float | None = None,
               costs: Any = None, grille_sgi: grille.GrilleSGI | None = None, perte_toleree: Any = None,
               taux_reserve: float | None = None, statut_taux: str | None = None,
               plan_enregistre: Mapping[str, Any] | None = None, suivi: Mapping[str, Any] | None = None,
               appel: Mapping[str, Any] | None = None, verifier: Callable[[float], Any] | None = None,
               choix_verifie: Mapping[str, Any] | None = None, validation_dir: str | Path | None = None,
               sessions: Any = None, carnet_cloture: Mapping[str, Mapping[str, float]] | None = None,
               holdings_fournis: bool | None = None, cash_fourni: bool | None = None,
               memoire: Mapping[str, Any] | None = None, completer: bool = False,
               forced_exits: Mapping[str, str] | None = None, grille_enregistree_non_employee: bool = False,
               aujourd_hui: Any = None, reglages_module: Mapping[str, Any] | None = None,
               graines: int | None = None, memo: dict | None = None, **_ignores: Any) -> dict[str, Any]:
    """Clé ``rendement_net`` de l'ordre de bataille (§4.5). **Ne lève jamais.**

    ``ordre`` : ``OrdreDeBataille`` **ou** son dictionnaire ``to_dict()`` (l'ordre du capital total, déjà calculé :
    coûts, dividendes, distribution, stress et avertissements). ``panels`` : panels de l'ordre (indices TR, cours
    ajustés, ``dividends_table``) ; sans eux, les lectures du risque valent « non calculé ». ``grille_sgi`` : grille
    employée pour l'ordre (``None`` : le tarif de l'ordre, supposé). ``perte_toleree`` : ce que l'utilisateur accepte
    de risquer sur 12 mois (FCFA, ou « 10 % » du capital) ; absent : table de choix. ``verifier(capital) -> ordre`` :
    vérification par l'ordre complet (§F4, étape 6), injectée par l'appelant (``recommend(..., rendement=False)``) ;
    jamais rappelée récursivement. ``memo`` : dictionnaire facultatif qui reçoit l'ordre de la poche vérifié
    (``memo["ordre_poche"]``), pour que l'appelant n'ait pas à le recalculer.

    Aucune écriture, aucun réseau. Les dates de S1 ne sont jamais simulées : seuls des résultats publiés et des
    statistiques descriptives du panier d'aujourd'hui sont lus."""
    if _EN_COURS.get():
        return {"version": VERSION, "bandeau": BANNER, "erreur": "appel récursif de rendement.construire refusé"}
    jeton = _EN_COURS.set(True)
    t0 = time.time()
    try:
        return _construire(ordre, panels=panels, asof=asof, capital=capital, costs=costs, g=grille_sgi,
                           perte_toleree=perte_toleree, taux_reserve=taux_reserve, statut_taux=statut_taux,
                           plan_enregistre=plan_enregistre, suivi=suivi, appel=appel, verifier=verifier,
                           choix_verifie=choix_verifie, validation_dir=validation_dir, sessions=sessions,
                           carnet_cloture=carnet_cloture, holdings_fournis=holdings_fournis, cash_fourni=cash_fourni,
                           memoire=memoire, completer=completer, forced_exits=forced_exits,
                           non_employee=grille_enregistree_non_employee, aujourd_hui=aujourd_hui, rg=reglages_module,
                           graines=graines, memo=memo, t0=t0)
    except MemoryError:  # mémoire insuffisante : la commande s'arrête (code 6)
        raise
    except Exception as exc:  # noqa: BLE001 - dernier filet : construire ne lève jamais
        return {"version": VERSION, "bandeau": BANNER, "erreur": f"{exc.__class__.__name__} : {exc}"}
    finally:
        _EN_COURS.reset(jeton)


def pour_ordre_poche(rn_capital: Mapping[str, Any], ordre_poche: Any, **kw: Any) -> dict[str, Any]:
    """Clé ``rendement_net`` de l'**ordre de la poche** (option ``--perte-toleree``, §F4, Intégration). **Ne lève
    jamais.**

    ``rn_capital`` : sortie de :func:`construire` sur l'ordre du capital total K, avec la perte acceptée (la ligne
    retenue y est vérifiée par l'ordre complet) ; ``ordre_poche`` : l'ordre O_A rendu dans ``memo["ordre_poche"]``.
    Les blocs qui décrivent l'ordre affiché sont recalculés sur O_A (``construire`` sans perte acceptée : frais,
    bilan, leviers, liquidités et provision, « passer l'ordre », alertes, avertissements, lectures du risque et
    concentration de l'ordre affiché) ; les décisions de l'écran restent celles du capital total (``perte``,
    ``reserve``, ``plan`` ; lectures du capital total sous ``risque_capital_total``). ``contexte`` porte le capital
    total, le montant en actions et la réserve (en-tête : :func:`brvm_alpha.rendement.rendu.ligne_entete_poche`).
    ``kw`` : mêmes paramètres que :func:`construire` (``perte_toleree``, ``verifier``, ``choix_verifie``, ``memo`` et
    ``capital`` sont ignorés : le capital de O_A est le montant en actions)."""
    try:
        sans = {k: v for k, v in kw.items() if k not in ("perte_toleree", "verifier", "choix_verifie", "memo", "capital")}
        rn_a = construire(ordre_poche, **sans)
        out = dict(rn_a)
        for cle in BLOCS_DU_CAPITAL_TOTAL:
            out[cle] = rn_capital.get(cle)
        out["risque_capital_total"] = rn_capital.get("risque")
        ctx_k = rn_capital.get("contexte") if isinstance(rn_capital.get("contexte"), Mapping) else {}
        K = float(ctx_k.get("capital") or 0)
        ch = (rn_capital.get("perte") or {}).get("choix") if isinstance(rn_capital.get("perte"), Mapping) else None
        A = float((ch or {}).get("en_actions") or (rn_a.get("contexte") or {}).get("capital") or 0)
        ctx = dict(rn_a.get("contexte") or {})
        ctx.update({"poche": True, "capital": K, "capital_ordre": float((rn_a.get("contexte") or {}).get("capital") or A),
                    "en_actions": A, "reserve": max(0.0, K - A)})
        out["contexte"] = ctx
        return out
    except MemoryError:  # mémoire insuffisante : la commande s'arrête (code 6)
        raise
    except Exception as exc:  # noqa: BLE001 - dernier filet : jamais d'exception vers l'ordre de bataille
        return {"version": VERSION, "bandeau": BANNER, "erreur": f"{exc.__class__.__name__} : {exc}"}


def _construire(ordre: Any, *, panels, asof, capital, costs, g, perte_toleree, taux_reserve, statut_taux, plan_enregistre,
                suivi, appel, verifier, choix_verifie, validation_dir, sessions, carnet_cloture, holdings_fournis,
                cash_fourni, memoire, completer, forced_exits, non_employee, aujourd_hui, rg, graines, memo,
                t0) -> dict[str, Any]:
    o = reglages.en_dict(ordre)
    R = rg if rg is not None else _bloc(reglages.charger)
    if not _ok(R) and isinstance(R, Mapping):
        R = None
    jour = aujourd_hui if aujourd_hui is not None else (appel or {}).get("today") or _dt.date.today()
    K = float(capital if capital is not None else (o.get("capital") or o.get("valeur_portefeuille") or 0))
    cm = _bloc(lambda: grille.cost_model_de(o, costs))
    cm = cm if not isinstance(cm, Mapping) else None
    g_eff = g if g is not None else _bloc(lambda: grille.depuis_cost_model(
        cm, "Tarif supposé (" + str((o.get("couts") or {}).get("scenario") or "central") + ")"))
    if isinstance(g_eff, Mapping):
        g_eff = grille.defaut()
    vdir = validation_dir if validation_dir is not None else (appel or {}).get("validation_dir")
    if vdir is not None and not Path(vdir).is_absolute():
        from brvm_alpha import paths as _paths

        vdir = _paths.repo_path(vdir)
    sess = sessions if sessions is not None else (appel or {}).get("sessions")
    rn: dict[str, Any] = {"version": VERSION, "bandeau": BANNER}
    avert = [str(a) for a in (o.get("avertissements") or [])]
    rn["contexte"] = {"capital": K, "asof": str(o.get("asof") or asof or "")[:10], "variante": o.get("variante"),
                      "statut": o.get("statut"), "panel_en_retard": next((a for a in avert if a.startswith("PANEL EN RETARD")), None),
                      "n_lignes_cibles": sum(1 for l in (o.get("lignes") or []) if float(l.get("poids_cible") or 0) > 0)}
    statut = str(o.get("statut") or "REJETÉ")
    rn["etude"] = _bloc(lambda: {
        "statut": statut, "phrases": [reglages.PH_ETUDE, reglages.phrase_seance(jour, R)],
        "debut_suivi": reglages.lire(R, "dates.debut_suivi"),
        "premiere_decision_argent_reel": reglages.lire(R, "dates.premiere_decision_argent_reel"),
        "argent_reel_recommande": False, "ne_pas_transmettre": reglages.PH_NE_PAS_TRANSMETTRE})

    def _grille_bloc() -> dict[str, Any]:
        d = g_eff.to_dict()
        d["employee"] = True
        if non_employee:
            d["non_employee"] = "Votre grille enregistrée n'est pas employée ici. Option --grille ma_sgi."
        d["texte"] = f"Tarif employé : {g_eff.nom} (statut : {grille.statut_global(g_eff)})."
        d["questions"] = grille.questions()
        return d

    rn["grille"] = _bloc(_grille_bloc)
    rn["bilan"] = _bloc(lambda: bilan.bilan_fuites(o, g_eff, reglages=R, costs=cm))
    # Lectures du risque (indices TR des panels)
    weekly = _bloc(lambda: risque.hebdo(o, panels or {}))
    wk = weekly if not isinstance(weekly, Mapping) else None

    def _risque_bloc() -> dict[str, Any]:
        if wk is None:
            raise ValueError("indices TR absents : lectures du risque non calculées" + (
                f" ({weekly.get('erreur')})" if isinstance(weekly, Mapping) else ""))
        lec = risque.lectures(o, weekly=wk, graines=graines, reglages=R)
        per = _bloc(lambda: risque.periodes_reelles(o, panels))
        out = {"lectures": lec["lectures"], "frais_deduits": lec["frais_deduits"], "n_semaines": lec["n_semaines"],
               "n_graines": len(lec["graines"]), "periodes_reelles": per, "synthese": risque.synthese(lec, per if _ok(per) else None),
               "phrases": [reglages.PH_PASSE, reglages.PH_DESCRIPTIF], "phrase_flatteuse": reglages.PH_FLATTE,
               "libelle_p_battre_tr": risque.LIBELLE_P_BATTRE_TR, "statut": reglages.ESTIMATION}
        return out

    rn["risque"] = _bloc(_risque_bloc)
    if _ok(rn["risque"]):
        conc = _bloc(lambda: risque.concentration(o, _montant(perte_toleree, K), reglages=R))
        rn["risque"]["concentration"] = conc
    else:
        rn["risque_concentration"] = _bloc(lambda: risque.concentration(o, _montant(perte_toleree, K), reglages=R))
    # Perte acceptée
    X = _bloc(lambda: _montant(perte_toleree, K))
    X = X if not isinstance(X, Mapping) else None
    if X is None and plan_enregistre and plan_enregistre.get("perte_toleree") is not None and perte_toleree is None:
        X = _bloc(lambda: _montant(plan_enregistre.get("perte_toleree"), K))
        X = X if not isinstance(X, Mapping) else None
    lecteur = _bloc(lambda: risque.LecteurPoche(wk)) if wk is not None else None
    lecteur = lecteur if not isinstance(lecteur, Mapping) else None

    def _perte_bloc() -> dict[str, Any]:
        cref = perte.choc_ref_publie(vdir, panels, reglages=R)
        ch = perte.chocs(o, cref)
        ch["ref_publie_detail"] = {k: cref.get(k) for k in ("vl_2018", "part_investie_2018", "frais_2018", "motif", "mention")
                                   if cref.get(k) is not None}
        table = perte.table_de_choix(o, cm, g if g is not None else None, ch, lecteur, reglages=R)
        # La table porte la lecture flatteuse (annee_ordinaire.flatteuse) : PH_FLATTE l'accompagne (règle 8, §F1-10).
        out: dict[str, Any] = {"chocs": ch, "table": table, "choix": None,
                               "phrases": [reglages.PH_PASSE, reglages.PH_DESCRIPTIF, reglages.PH_FLATTE,
                                           reglages.PH_RISQUE, reglages.PH_INTERETS]}
        if X is not None:
            choix = perte.ligne_choisie(o, X, cm, g if g is not None else None, ch, lecteur, verifier=verifier,
                                        reglages=R, choix_verifie=choix_verifie)
            out["choix"] = choix
        return out

    rn["perte"] = _bloc(_perte_bloc)
    A_star = 0.0
    if _ok(rn["perte"]) and rn["perte"].get("choix"):
        A_star = float(rn["perte"]["choix"].get("en_actions") or 0)
    tr = taux_reserve if taux_reserve is not None else (plan_enregistre or {}).get("taux_reserve")
    st_t = statut_taux if statut_taux is not None else (plan_enregistre or {}).get("statut_taux")
    rn["reserve"] = _bloc(lambda: {**perte.reserve(K, A_star, tr, st_t, reglages=R),
                                   "pendant_l_etude": {"montant": int(round(K)), "valeur_d_un_point": int(round(0.01 * K))}})
    # Liquidités
    arr = _bloc(lambda: liquidites.arrondi_restes(o, cm, g if g is not None else None, reglages=R))
    proj = _bloc(lambda: liquidites.projection(o, g if g is not None else None, costs=cm, reglages=R))
    proj_ed = _bloc(lambda: liquidites.projection(o, g if g is not None else None, reinvestir=True, costs=cm, reglages=R))
    rn["liquidites"] = {
        "decomposition": _bloc(lambda: liquidites.decomposition(o)),
        "reserve_fonctionnement": _bloc(lambda: liquidites.reserve_fonctionnement(o, g_eff, reglages=R)),
        "argent_qui_dort": _bloc(lambda: liquidites.argent_qui_dort(o, memoire=memoire, panels=panels, reglages=R)),
        "projection": proj,
        "provision": _bloc(lambda: liquidites.provision_entree(o, cm, reglages=R)),
        "arrondi_possible": arr,
    }
    lec_res = None
    if _ok(rn["risque"]):
        per = rn["risque"].get("periodes_reelles")
        lec_res = risque.resume_pour_leviers({"lectures": rn["risque"]["lectures"]}, per if _ok(per) else None)
    rn["leviers"] = _bloc(lambda: bilan.leviers(o, g_eff, lec_res, arrondi=arr if _ok(arr) else None,
                                               reinvestir=proj_ed if _ok(proj_ed) else None, reglages=R, costs=cm))
    rn["passer_l_ordre"] = _bloc(lambda: {"consignes": liquidites.consignes(o, panels, carnet=carnet_cloture),
                                          "carnet": liquidites.compte_carnet(o, carnet_cloture),
                                          "ne_pas_transmettre": reglages.PH_NE_PAS_TRANSMETTRE})
    al = _bloc(lambda: alertes.alertes_fuite(o, rn, g_eff if g is not None else None, panels, sessions=sess,
                                             holdings_fournis=holdings_fournis, cash_fourni=cash_fourni, memoire=memoire,
                                             completer=completer, forced_exits=forced_exits, reglages=R, costs=cm))
    rn["alertes"] = al if isinstance(al, list) else [{"code": "erreur", "niveau": "information", "prefixe": None,
                                                      "texte": f"alertes non calculées ({al.get('erreur')})", "cause": ""}]
    rn["avertissements_a_ajouter"] = _bloc(lambda: alertes.avertissements(rn["alertes"])) if isinstance(al, list) else []
    rn["suivi"] = None
    if suivi:
        rn["suivi"] = _bloc(lambda: {"feux": alertes.feux(suivi.get("semaine"), plan_enregistre or
                                                          ({"perte_toleree": X} if X else None), suivi.get("declaration"),
                                                          suivi.get("alertes_ouvertes"), reglages=R),
                                     "semaine": suivi.get("semaine")})
    # Ordre de la poche vérifié : rendu à part (non sérialisé)
    if _ok(rn["perte"]) and rn["perte"].get("choix"):
        ch = rn["perte"]["choix"]
        if memo is not None and ch.get("_ordre") is not None:
            memo["ordre_poche"] = ch.get("_ordre")
    rn = _sans_objets(rn)
    rn["plan"] = _bloc(lambda: plan.construire_plan(rn, plan_enregistre, rn.get("suivi"), jour))
    rn["duree_s"] = round(time.time() - t0, 2)
    return rn
