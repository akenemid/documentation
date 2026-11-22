"""Rapport ``resultats.md`` de la validation (en français), à partir de ``metrics.json``.

Le rapport distingue les **faits** (données et règles appliquées), les **estimations**
(métriques calculées sur un historique court, avec leur incertitude) et les **hypothèses**
(coûts, exécution, reconstruction de l'étalon). Il porte la bannière « Performance passée ≠
garantie. Aucun gain n'est garanti. » en tête et en pied, et rappelle la prédiction écrite
d'avance du §8.3.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

__all__ = ["build_report", "fmt_num", "fmt_pct"]

BANNER = "Performance passée ≠ garantie. Aucun gain n'est garanti."

_COSTS = {"central": "centraux", "stress": "de stress", "optimistic": "optimistes", "severe": "sévères"}
_BENCH_ORDER = ("TR", "EW", "PRIX", "BRVM10", "BRVM30", "PRESTIGE", "FONDS")


def _ok(x: Any) -> bool:
    try:
        return x is not None and math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def fmt_pct(x: Any, decimals: int = 1, signed: bool = False) -> str:
    """Pourcentage à la française (``12,3 %``) ; ``n.d.`` si non évaluable."""
    if not _ok(x):
        return "n.d."
    v = 100.0 * float(x)
    s = f"{v:+.{decimals}f}" if signed else f"{v:.{decimals}f}"
    return s.replace(".", ",").replace("-", "−") + " %"


def fmt_num(x: Any, decimals: int = 2, signed: bool = False) -> str:
    """Nombre à la française (``0,25``) ; ``n.d.`` si non évaluable."""
    if not _ok(x):
        return "n.d."
    s = f"{float(x):+.{decimals}f}" if signed else f"{float(x):.{decimals}f}"
    return s.replace(".", ",").replace("-", "−")


def _fcfa(x: Any) -> str:
    if not _ok(x):
        return "n.d."
    return f"{float(x):,.0f}".replace(",", " ") + " FCFA"


def _date(x: Any) -> str:
    if not x:
        return "n.d."
    s = str(x)[:10]
    if len(s) == 10 and s[4] == "-":
        return f"{s[8:10]}/{s[5:7]}/{s[0:4]}"
    return s


def _get(d: Mapping[str, Any] | None, *keys: str) -> Any:
    cur: Any = d
    for k in keys:
        if not isinstance(cur, Mapping):
            return None
        cur = cur.get(k)
    return cur


def _table(header: Sequence[str], rows: Sequence[Sequence[str]]) -> list[str]:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return out


def _capital(x: Any) -> str:
    if not _ok(x):
        return "n.d."
    c = float(x)
    if c >= 1e9:
        return f"{fmt_num(c / 1e9, 0 if c % 1e9 == 0 else 1)} Md FCFA"
    if c >= 1e6:
        return f"{fmt_num(c / 1e6, 0 if c % 1e6 == 0 else 1)} M FCFA"
    return _fcfa(c)


def _pbo_sens_text(sens: Mapping[str, Any], fam: Mapping[str, Any]) -> str:
    parts = [f"convention figée (blocs égaux, semaines anciennes en surnombre ignorées) "
             f"{fmt_num(sens.get('convention_figee'), 3)}",
             f"toutes les semaines (`array_split`) {fmt_num(sens.get('toutes_semaines_array_split'), 3)}",
             f"λ = 0 compté pour ½ {fmt_num(sens.get('lambda0_compte_demi'), 3)}"]
    if "sans_clones" in sens:
        parts.append(f"famille sans clone ({', '.join(sens.get('sans_clones_variantes') or [])}) "
                     f"{fmt_num(sens.get('sans_clones'), 3)}")
    if "famille_de_quasi_clones_simulee" in sens:
        parts.append(f"famille simulée de quasi-clones de A {fmt_num(sens.get('famille_de_quasi_clones_simulee'), 3)}")
    parts.append(f"PBO nulle de référence pour N = {len(fam.get('variantes') or [])} : "
                 f"{fmt_num(sens.get('reference_nulle_n'), 3)} (0,5 si λ = 0 compte pour ½)")
    return " ; ".join(parts) + "."


def _fp_text(fc: Mapping[str, Any] | None) -> str:
    """Contrôle d'empreinte sans autoréférence : état figé a2bfeb4 et référence 751d1be (v1.0)."""
    if not fc:
        return ""
    ref = fc.get("reference_preenregistrement") or {}
    fixed = fc.get("etat_fige") or {}
    if not ref:  # verrou antérieur à la correction du 22/11/2026
        return (" (identique à l'empreinte du registre S1-I / REF-ID, écrite dans le même commit que l'état figé : "
                "contrôle autoréférentiel)" if fc.get("conforme") else " (**différente** de l'empreinte du registre)")
    same = fc.get("conforme_etat_fige", fc.get("conforme"))
    return ((f" (identique à l'empreinte de l'état figé `{str(fixed.get('commit'))[:7]}`" if same else
             f" (**différente** de l'empreinte de l'état figé `{str(fixed.get('commit'))[:7]}` "
             f"`{fixed.get('empreinte')}`")
            + f" ; référence de pré-enregistrement : commit `{str(ref.get('commit'))[:7]}`, YAML "
              f"{ref.get('version_yaml')}, empreinte `{ref.get('empreinte_v1_0')}` ; l'empreinte de l'état figé n'est "
              "pas une valeur pré-enregistrée indépendante)")


def _run_label(rid: str, runs: Mapping[str, Any]) -> str:
    r = runs.get(rid) or {}
    costs = _COSTS.get(str(r.get("couts")), r.get("couts"))
    return f"{r.get('variante', rid)} (coûts {costs}, {_capital(r.get('capital'))})"


def build_report(m: Mapping[str, Any]) -> str:
    """Texte Markdown complet du rapport (``m`` : contenu de ``metrics.json``)."""
    sample = m.get("echantillon")
    runs: Mapping[str, Any] = m.get("runs") or {}
    variants: Mapping[str, Any] = m.get("variantes") or {}
    fam: Mapping[str, Any] = m.get("famille") or {}
    ex: Mapping[str, Any] = m.get("execution") or {}
    L: list[str] = []
    title = ("Validation S1 — test unique pré-enregistré (additif v1.1)" if sample == "S1"
             else "Diagnostic S0 — échantillon contaminé")
    L += [f"# BRVM Alpha — {title}", "", f"> **{BANNER}**", ""]
    if sample != "S1":
        L += ["> **Contaminé, aucune valeur de preuve.** S0 (2022-11-17 → 2026-11-20) a déjà été exploré par les "
              "revues et par la mise au point du moteur : ces chiffres servent à vérifier que la chaîne tourne, "
              "jamais à conclure. Les essais exécutés ici sont inscrits au registre et comptent dans N.", ""]
    else:
        L += ["> Test **unique** sur l'échantillon vierge S1 (2017-01-02 → 2022-11-16), paramètres figés avant "
              "l'exécution (§3.4, §8.3, additif v1.1 §8.4). Toute relance exige un bogue démontré "
              "(`--rerun-reason`) et crée de nouveaux essais.", ""]

    # 1. Contexte
    L += ["## 1. Contexte d'exécution (faits)", ""]
    L += _table(["Élément", "Valeur"], [
        ["Commit", f"`{ex.get('commit')}`" + (f" (branche {ex.get('branche')})" if ex.get("branche") else "")],
        ["Arbre `brvm_alpha/` et `configs/` identique à HEAD, sans fichier non suivi",
         "oui" if ex.get("arbre_propre") else "non"],
        ["Fichiers non suivis (refusés sur S1, listés)", ", ".join(ex.get("fichiers_non_suivis") or []) or "aucun"],
        ["Empreinte de configuration", f"`{ex.get('empreinte_config')}`" + _fp_text(ex.get("empreinte_controle"))],
        ["Version du YAML", str(ex.get("version_yaml"))],
        ["Horodatage (UTC)", str(ex.get("horodatage_utc"))],
        ["Durée totale / des runs", f"{fmt_num(ex.get('duree_totale_s'), 1)} s / {fmt_num(ex.get('duree_runs_s'), 1)} s"
                                    f" ({ex.get('workers')} processus)"],
        ["Panel", str(ex.get("panel"))],
        ["Plan des runs", f"{len(m.get('plan') or [])} runs" + ("" if ex.get("plan_standard") else
                                                                 " (**non standard**)")],
        ["Événements pays chargés (D10)", str(ex.get("n_evenements_pays"))],
        ["Mode de décision", f"{ex.get('mode_decision')} (effectif : {', '.join(ex.get('modes_effectifs') or [])})"],
        ["Bootstrap stationnaire", f"n_boot = {m.get('n_boot')} (explicite), blocs moyens de "
                                   f"{m.get('bloc_moyen_semaines')} semaines"],
    ])
    if ex.get("runs_en_echec"):
        L += ["", "**Runs en échec** : " + " ; ".join(f"{x['run_id']} ({x['erreur']})" for x in ex["runs_en_echec"])]
    if ex.get("relance"):
        rl = ex["relance"]
        L += ["", f"**Relance motivée (D12)** : {rl.get('motif')}. Anciens résultats : `{rl.get('precedent')}`."]
    L += [""]

    # 2. Fenêtre
    subs = m.get("sous_periodes") or []
    L += ["## 2. Fenêtre d'évaluation (additif v1.1, D2)", ""]
    L += [f"- **t0 = {_date(m.get('t0'))}** : première séance où la variante A (coûts centraux, 10 M FCFA) détient "
          "des titres. Toutes les variantes et tous les étalons sont évalués sur la **même** fenêtre "
          f"[{_date(m.get('t0'))} ; {_date(m.get('fin'))}], rebasés à t0 (base 100 à la clôture de la veille de t0 : "
          "le rendement de t0, qui porte les frais d'achat initiaux, est compté).",
          "- Sous-périodes : " + " ; ".join(f"[{_date(a)} ; {_date(b)}]" for a, b in subs) + ".",
          f"- Fréquence : hebdomadaire ({m.get('frequence')}), nette de tous les coûts ; annualisation à 52 semaines.",
          "- Semaines retirées de toutes les mesures : fenêtre(s) du §8.1 " + ", ".join(
              f"{_date(a)} → {_date(b)}" for a, b in m.get("fenetres_exclues") or [])
          + " (" + (", ".join(_date(x) for x in m.get("semaines_exclues") or []) or "aucune") + ").",
          ("- Semaines multi-séances (observation de plus de 6 séances après un trou de BOC) : "
           + (", ".join(_date(x) for x in m.get("semaines_multi_seances") or []) or "aucune")
           + ". Elles sont **gardées** pour les critères chaînés (rendement annualisé, actif R1/R2/C1/C3, drawdowns "
             "R4/R5/C4) et **retirées** des seules statistiques de dispersion (volatilité, IR, TE, Sharpe, PSR, DSR, "
             "PBO, CVaR, bootstrap) : §3.1.3, « exclu des estimations de volatilité […] mais gardé pour chaîner le "
             "TR »." if "semaines_multi_seances" in m else
           "- Semaines couvrant plus de 6 séances (trous de BOC) : retirées de toutes les mesures (lecture antérieure "
           "à la correction du 22/11/2026)."),
          "- La fenêtre complète (depuis la première séance simulée, liquidités de démarrage comprises) est "
          "publiée en section 10 **pour information seulement**.", ""]

    # 3. Étalons
    L += ["## 3. Étalons (sur [t0 ; fin], sans coûts)", ""]
    rows = []
    bench = m.get("etalons") or {}
    for c in list(_BENCH_ORDER) + [k for k in bench if k not in _BENCH_ORDER]:
        b = bench.get(c)
        if not b:
            continue
        mm = b.get("mesures") or {}
        rows.append([c, b.get("libelle", ""), "oui" if b.get("disponible") else "**non disponible**",
                     fmt_pct(mm.get("rendement_an")), fmt_pct(mm.get("volatilite_an")),
                     fmt_pct(mm.get("drawdown_absolu")), str(mm.get("n_semaines", "")),
                     " ; ".join(x for x in (b.get("note") or "", f"source : {b.get('source')}" if b.get("source")
                                            else "") if x)])
    L += _table(["Code", "Étalon", "Disponible", "Rendement an.", "Vol. an.", "Drawdown", "Semaines", "Note"], rows)
    L += [""]

    # 4. Tableau par variante
    L += ["## 4. Variantes aux coûts centraux, 10 M FCFA (estimations)", ""]
    rows = []
    for v, d in variants.items():
        r = runs.get(d.get("run_id")) or {}
        sh = r.get("sharpe") or {}
        cv = r.get("cvar") or {}
        rows.append([f"**{v}**" + (" (réf.)" if d.get("statut_informatif") else ""), fmt_pct(r.get("rendement_an")),
                     fmt_pct(r.get("volatilite_an")), fmt_pct(r.get("actif_tr_an"), signed=True),
                     fmt_pct(r.get("actif_ew_an"), signed=True), fmt_num(r.get("ir_tr")), fmt_pct(r.get("te_tr")),
                     f"{fmt_num(sh.get('naive'))} / {fmt_num(sh.get('lo'))} / {fmt_num(sh.get('glm'))}"
                     + (" ⚠" if sh.get("divergence") else ""),
                     fmt_num(r.get("psr_actif")), fmt_num(d.get("dsr_registre")), fmt_num(d.get("dsr_famille_n9")),
                     fmt_pct(r.get("drawdown_absolu")), fmt_pct(r.get("drawdown_relatif_tr")),
                     fmt_num(cv.get("ratio")), fmt_pct(r.get("rotation_mensuelle_aller")),
                     fmt_pct(r.get("couts_an_pct_nav_moyenne"), 2), fmt_num(r.get("lignes_moyennes"), 1),
                     fmt_pct(r.get("part_investie_moyenne"))])
    L += _table(["Var.", "Rdt an.", "Vol.", "Actif / TR", "Actif / EW", "IR", "TE", "Sharpe naïf / Lo / GLM", "PSR(0)",
                 f"DSR (N = {fam.get('n_registre')})", "DSR (N = 9)", "DD abs.", "DD rel. TR", "CVaR / TR",
                 "Rotation /mois", "Coûts /an", "Lignes", "Investi"], rows)
    L += ["", "⚠ : écart entre Sharpe de Lo et Sharpe GLM supérieur à 25 % (prix périmés à examiner, §8.2). "
          "PSR, DSR, IR et Sharpe portent sur les rendements **actifs** nets contre le TR (sauf la colonne Sharpe, "
          "rendements absolus). Coûts /an : coûts payés rapportés à la NAV moyenne, annualisés par les années "
          "calendaires de la fenêtre.", ""]
    if any(_ok(d.get("dsr_registre_variance_registre")) for d in variants.values()):
        rows = [[v, fmt_num(d.get("dsr_registre"), 4), fmt_num(d.get("dsr_registre_variance_registre"), 4),
                 fmt_num(d.get("dsr_famille_n9"), 4)] for v, d in variants.items()]
        L += [f"**DSR sous deux conventions de variance** (N = {fam.get('n_registre')} ; §8.5) : variance des Sharpe "
              f"hebdomadaires de la famille ({fmt_num(fam.get('variance_sharpe_hebdo'), 6)}, utilisée pour G3) ou de "
              f"tous les essais exécutés du registre ({fmt_num(fam.get('variance_sharpe_registre'), 4)}, prudente).", ""]
        L += _table(["Var.", "DSR (variance famille)", "DSR (variance registre)", "DSR (N = 9)"], rows) + [""]

    # 5. Statuts
    L += ["## 5. Statuts du §8.3 (règles exactes, estimations)", ""]
    rows = []
    for v, d in variants.items():
        ms = d.get("mesures_statut") or {}
        rows.append([f"**{v}**", f"**{d.get('statut')}**" + (" (informatif)" if d.get("statut_informatif") else ""),
                     ", ".join(d.get("rejets_declenches") or []) or "aucun",
                     ", ".join(d.get("criteres_candidat_non_verifies") or []) or "aucun",
                     fmt_pct(ms.get("actif_net_central_an"), signed=True),
                     fmt_pct(ms.get("actif_net_stress_an"), signed=True),
                     " / ".join(fmt_num(x) for x in ms.get("ir_sous_periodes") or []),
                     fmt_num(d.get("ic_t_nw")), fmt_num(d.get("hsr_bhy"))])
    L += _table(["Var.", "Statut", "Rejets déclenchés (R1-R5)", "Critères candidat non vérifiés (C1-C7)",
                 "Actif central", "Actif stress", "IR sous-périodes", "t NW de l'IC", "HSR (BHY)"], rows)
    cov = [(v, (d.get("mesures_statut") or {})) for v, d in variants.items()]
    if any(_ok(ms.get("couverture_dispersion")) for _, ms in cov):
        ms_a = dict(cov).get("A") or (cov[0][1] if cov else {})
        L += ["", f"Couverture de la période attendue (calendrier W-FRI de [t0 ; fin] moins la fenêtre du §8.1, "
                  f"{ms_a.get('semaines_attendues')} semaines ; seuil 95 %, §8.5) : "
                  f"**{fmt_pct(ms_a.get('couverture'))}** sur les séries chaînées (critère) ; "
                  f"{fmt_pct(ms_a.get('couverture_dispersion'))} sans les semaines multi-séances (lecture antérieure à "
                  "la correction du 22/11/2026, sous le seuil : elle aurait rendu le statut INDÉTERMINÉ)."]
    untested = [v for v, d in variants.items() if d.get("testee") is False]
    if untested:
        L += ["", "**Non testée(s) sur S1** : " + " ; ".join(str(variants[v].get("note_test")) for v in untested)]
    L += ["", "REJETÉ : l'une des conditions R1-R5 est vraie. CANDIDAT : C1-C7 toutes vraies (paper trading "
          "autorisé). INDÉTERMINÉ : ni l'un ni l'autre, ou données insuffisantes (aucun suivi réel autorisé). "
          "**PROMU est impossible sans suivi réel S2** (au moins 12 mois ; G7 sur les IC S1 puis S2 bout à bout, "
          "au moins 36 mois, D7). La référence REF (« indice discipliné », D8) est évaluée pour information, hors "
          "famille de la PBO.", ""]

    # 6. Famille, PBO, promotion
    pr = m.get("promotion") or {}
    L += ["## 6. Famille (N = 9), PBO et règle de promotion du §3.4", ""]
    L += [f"- Variantes de la famille exécutées : {', '.join(fam.get('variantes') or [])} "
          f"({'complète' if fam.get('complete') else '**incomplète**'}) ; semaines communes : "
          f"{fam.get('n_semaines_communes')}.",
          f"- **PBO (CSCV, S = {fam.get('n_blocs')} blocs hebdomadaires, {fam.get('critere')})** : "
          f"{fmt_num(fam.get('pbo'), 3)} ; pente de dégradation : {fmt_num(fam.get('pente_degradation'), 3)}"
          + (f" ({fam.get('note_pbo')})" if fam.get("note_pbo") else "") + ".",
          *(["- **Sensibilité de la PBO** (publiée ; C6 reste évalué avec la convention figée) : "
             + _pbo_sens_text(fam.get("pbo_sensibilite") or {}, fam)] if fam.get("pbo_sensibilite") else []),
          *([f"- Clones exacts dans la famille : {', '.join(f'{a} = {b}' for a, b in fam.get('clones_exacts'))} "
             "(variantes identiques : la PBO perd son pouvoir discriminant)."] if fam.get("clones_exacts") else []),
          f"- Registre : N = {fam.get('n_registre')} essais (DSR « registre » et haircut BHY) ; G1 (registre "
          f"complet) : {'vert' if fam.get('registre_complet') else 'rouge'} ; variance des Sharpe hebdomadaires "
          f"entre variantes : {fmt_num(fam.get('variance_sharpe_hebdo'), 6)}.",
          f"- Règle : {pr.get('regle')}. **Variante principale après la règle : {pr.get('principal')}**"
          + (f" ({pr.get('note')})" if pr.get("note") else "") + ".", ""]
    if pr.get("criteres"):
        rows = [[str(c.get("variante")), fmt_pct(c.get("actif_net_an"), signed=True),
                 {True: "oui", False: "non"}.get(c.get("bat_reference"), "—"), fmt_num(c.get("dsr")),
                 {True: "oui", False: "non"}.get(c.get("promue"), "—")] for c in pr["criteres"]]
        L += _table(["Variante", "Actif net an.", "Bat A", "DSR (N = 9)", "Remplace A"], rows) + [""]

    # 7. Bootstrap
    L += ["## 7. Intervalles du bootstrap stationnaire (95 %, rendements actifs contre le TR)", ""]
    rows = []
    for v, d in variants.items():
        r = runs.get(d.get("run_id")) or {}
        bi, ba = r.get("bootstrap_ir") or {}, r.get("bootstrap_actif_moyen_an") or {}
        rows.append([v, f"{fmt_num(bi.get('point'))} [{fmt_num(bi.get('lower'))} ; {fmt_num(bi.get('upper'))}]",
                     f"{fmt_pct(ba.get('point'), signed=True)} [{fmt_pct(ba.get('lower'), signed=True)} ; "
                     f"{fmt_pct(ba.get('upper'), signed=True)}]"])
    L += _table(["Var.", "IR [IC 95 %]", "Actif moyen annualisé [IC 95 %]"], rows) + [""]

    # 8. Sous-périodes
    L += ["## 8. Sous-périodes (coûts centraux, 10 M FCFA)", ""]
    rows = []
    for v, d in variants.items():
        r = runs.get(d.get("run_id")) or {}
        cells = []
        for sp in r.get("sous_periodes") or []:
            cells.append(f"[{_date(sp.get('debut'))} ; {_date(sp.get('fin'))}] : actif "
                         f"{fmt_pct(sp.get('actif_tr_an'), signed=True)}, IR {fmt_num(sp.get('ir_tr'))}, "
                         f"{sp.get('n_semaines')} sem.")
        rows.append([v] + (cells or ["n.d."]))
    width = max((len(r) for r in rows), default=2)
    rows = [r + [""] * (width - len(r)) for r in rows]
    L += _table(["Var."] + [f"Sous-période {i}" for i in range(1, width)], rows) + [""]

    # 9. Sensibilités
    L += ["## 9. Analyses de sensibilité (le même essai sous d'autres hypothèses ; hors PBO et DSR)", ""]
    rows = []
    for rid, r in runs.items():
        if r.get("role") != "sensibilité":
            continue
        rows.append([_run_label(rid, runs), fmt_pct(r.get("rendement_an")), fmt_pct(r.get("actif_tr_an"), signed=True),
                     fmt_pct(r.get("actif_ew_an"), signed=True), fmt_num(r.get("ir_tr")),
                     fmt_pct(r.get("drawdown_relatif_tr")), fmt_pct(r.get("rotation_mensuelle_aller")),
                     fmt_pct(r.get("couts_an_pct_nav_moyenne"), 2), fmt_num(r.get("lignes_moyennes"), 1),
                     fmt_pct(r.get("part_investie_moyenne"))])
    L += _table(["Run", "Rdt an.", "Actif / TR", "Actif / EW", "IR", "DD rel. TR", "Rotation /mois", "Coûts /an",
                 "Lignes", "Investi"], rows)
    L += ["", "Aux capacités de 100 M et 1 Md FCFA, le panier EW est celui des éligibles de A **au même capital** "
          "(plancher de liquidité U5 dépendant du capital).", ""]

    # 9 bis. Contrôles comptables et d'exécution
    ctl = m.get("controles") or {}
    if ctl.get("runs"):
        L += ["## 9 bis. Contrôles comptables et d'exécution (faits de simulation, aucune performance)", ""]
        rows = []
        for rid, c in ctl["runs"].items():
            rows.append([_run_label(rid, runs), "oui" if c.get("ok") else "**NON**", _fcfa(c.get("cash_min_fcfa")),
                         fmt_pct(c.get("exposition_max"), 2), f"{c.get('identite_vl_ecart_max') or 0:.1e}",
                         f"{c.get('identite_flux_ecart_max') or 0:.1e}",
                         f"{c.get('ventes_a_la_borne_basse')} / {c.get('achats_a_la_borne_haute')}",
                         fmt_pct(c.get("cout_aller_median"), 2), fmt_pct(c.get("cout_aller_moyen_pondere"), 2),
                         str(c.get("n_executions"))])
        L += _table(["Run", "Contrôles verts", "Cash min.", "Exposition max.", "Identité VL", "Identité de flux",
                     "Ventes borne basse / achats borne haute", "Coût par aller (médiane)",
                     "Coût par aller (moyenne pondérée)", "Exécutions"], rows)
        drows = []
        for rid, r in runs.items():
            dc = r.get("cout_aller_decomposition_ponderee") or {}
            if _ok(dc.get("total")):
                drows.append([_run_label(rid, runs), fmt_pct(dc.get("frais"), 3), fmt_pct(dc.get("demi_spread"), 3),
                              fmt_pct(dc.get("impact"), 3), fmt_pct(dc.get("total"), 3)])
        if drows:
            L += ["", "Décomposition **pondérée** du coût par aller sur [t0 ; fin] (somme des composantes = coût moyen "
                      "pondéré ; le demi-spread médian mesuré n'entre pas dans cette somme) :", ""]
            L += _table(["Run", "Frais (courtage, taxe, BRVM, DC/BR)", "Demi-spread", "Impact", "Total"], drows)
        L += ["", "Cash réglé ≥ 0 à chaque séance (aucun levier) ; identités `VL = cash − frais dus + créances + "
              "Σ q·P` et `ΔVL = Σ q·ΔP + exécutions + dividendes − coûts` (écart maximal en fraction de la VL, "
              f"tolérance {ctl.get('tolerance_identites')}) ; aucune vente à la borne basse ni achat à la borne "
              "haute (§7.1.3). Une exposition légèrement supérieure à 100 % vient des frais de garde et de tenue de "
              "compte dus mais non encore payés (cash réglé nul en attendant un règlement J+3/J+2) : ce n'est pas "
              "un levier. Coût par aller : courtage, taxe, BRVM, DC/BR, demi-spread et impact rapportés au montant "
              "exécuté (§7.2 : environ 1,75 % pour un titre médian aux coûts centraux).", ""]
        if ctl.get("runs_en_anomalie"):
            L += ["**Anomalies** : " + " ; ".join(f"{rid} : {', '.join(ctl['runs'][rid].get('anomalies') or [])}"
                                                   for rid in ctl["runs_en_anomalie"]), ""]

    # 10. Dividendes et fenêtre complète
    L += ["## 10. Dividendes (D6) et fenêtre complète (information)", ""]
    rows = []
    for v, d in variants.items():
        r = runs.get(d.get("run_id")) or {}
        dv = r.get("dividendes") or {}
        fc = r.get("fenetre_complete") or {}
        rows.append([v, _fcfa(dv.get("credites_fcfa")), _fcfa(dv.get("ligne_d_fcfa")), _fcfa(dv.get("ecart_fcfa")),
                     fmt_pct(fc.get("rendement_an")), fmt_pct(fc.get("actif_tr_an"), signed=True),
                     fmt_num(fc.get("ir_tr")), fmt_pct(fc.get("drawdown_relatif_tr"))])
    L += _table(["Var.", "Dividendes crédités", "Ligne (d) du BOC", "Écart", "Rdt an. (complet)",
                 "Actif / TR (complet)", "IR (complet)", "DD rel. (complet)"], rows)
    L += ["", "Flux de trésorerie : montant **corrigé** (meilleure estimation du versement réel) ; signaux (DY, S1, "
          "S2) : montant connu en t, ligne (d) du BOC (D6). La fenêtre complète inclut les mois de liquidités de "
          "démarrage : elle crée un rendement actif mécanique et n'entre dans **aucun** critère (D2).", ""]

    # 11. Hypothèses et limites
    L += ["## 11. Faits, estimations, hypothèses et limites", "",
          "**Faits** : cours, volumes, dividendes et numéros de BOC lus dans les bulletins officiels ; règles et "
          "seuils du §8.3 et de l'additif v1.1, figés avant l'exécution ; plan des runs et paramètres consignés "
          "dans `lock.json` (S1) et dans le registre `reports/trials.parquet`.", "",
          "**Estimations** : toutes les métriques (rendements, IR, Sharpe, PSR, DSR, PBO, CVaR, intervalles du "
          "bootstrap) sont des estimations sur environ cinq ans de données hebdomadaires : leur incertitude est "
          "large (voir les intervalles de la section 7).", "",
          "**Hypothèses** : barèmes de coûts du §7.2 (courtage, taxe [NON VÉRIFIÉ], demi-spread mesuré, impact "
          "κ·√π sans étude publiée) ; exécution au VWAP de t+1 avec participation ≤ 10 % ; Composite TR "
          "reconstruit avant le premier niveau officiel ; secteurs de 2025 appliqués à tout l'historique ; "
          "chronologie des événements pays [NON VÉRIFIÉ] en partie (D10) ; étalon « fonds actions » non "
          "disponible.", "",
          "**Limites** : 129 séances sans BOC (dont 96 en 2021) ; semaines multi-séances gardées pour le chaînage et "
          "exclues des seules statistiques de dispersion ; annualisation conventionnelle (52 semaines observées) ; "
          "aucun suivi réel (S2) : le statut PROMU est impossible.",
          ""]

    # 12. Prédiction
    L += ["## 12. Prédiction du §8.3 (rappel, écrite avant l'exécution)", "", str(m.get("prediction_8_3") or ""), ""]

    # 13. Précédent
    prev = m.get("precedent")
    if prev:
        L += ["## 13. Résultats de l'exécution précédente (conservés, publiés avec la relance)", "",
              f"Dossier : `{prev.get('dossier')}` ; t0 précédent : {_date(prev.get('t0'))}.", ""]
        if prev.get("statuts"):
            rows = []
            for v, st in prev["statuts"].items():
                t = (prev.get("tableau") or {}).get(v) or {}
                rows.append([v, str(st), fmt_pct(t.get("rendement_an")), fmt_pct(t.get("actif_tr_an"), signed=True),
                             fmt_num(t.get("ir_tr")), fmt_pct(t.get("drawdown_relatif_tr"))])
            L += _table(["Var.", "Statut précédent", "Rdt an.", "Actif / TR", "IR", "DD rel. TR"], rows) + [""]
        elif prev.get("erreur"):
            L += [f"Lecture impossible : {prev['erreur']}", ""]

    L += ["## Fichiers", "", "`metrics.json` (toutes les mesures), `weekly_returns.parquet` (rendements hebdomadaires "
          "nets des stratégies et des étalons sur la fenêtre d'évaluation), `nav.parquet` (valeurs liquidatives et "
          "niveaux, rebasés à t0), `trades.parquet` (exécutions de tous les runs)"
          + (", `lock.json` (verrou du test unique)." if sample == "S1" else ", `contexte.json` (sans verrou)."), "",
          f"> **{BANNER}**", ""]
    return "\n".join(L)
