"""F10 — Le témoin du suivi : portefeuilles ``REF-S2`` (règle testée) et ``N`` (avec les notes), produits par le moteur
existant, sans le modifier.

Cahier ``docs/RENDEMENT_NET.md``, §F10 et §8.2. ``REF-S2`` est la règle telle qu'elle a été testée : variante REF,
coûts « central », 10 000 000 FCFA, aucune note, mode de décision « evenementiel » ; première décision à la dernière
séance au plus tard le 30/11/2026, première exécution à la première séance à partir du 01/12/2026.

``validation.runner.SAMPLES`` ne connaît que « S1 » et « S0 », et la fabrique par défaut ``brvm_alpha_model`` lit
``SAMPLES[sample]`` : ce module **ne l'emploie pas et ne modifie pas** ``runner.py``. Il fournit sa propre fabrique,
:func:`temoin_model`, passée par ``ctx["factory"]`` à ``runner.execute_run`` (le moteur du test, tel quel). Le module
n'appelle ni ``run_validation`` ni la commande ``validate`` ; il n'écrit rien sous ``reports/`` ; il refuse toute date de
l'échantillon S1 (≤ 16/11/2022).

* :func:`temoin_model`, :func:`contexte`, :func:`lancer` : le run du moteur ;
* :func:`operations_du_moteur` : exécutions, dividendes (à la date de paiement), frais fixes et apport, au format
  ``operations.csv`` (titres réels du jour, montants en FCFA : invariants aux divisions futures) ;
* :func:`maj` : met à jour ``<dossier>/<nom>/`` (``operations.csv``, ``positions.csv``, ``semaines.csv``,
  ``empreintes.jsonl``, ``anomalies.jsonl``, ``controles.json``) ; chaque relance doit retrouver à l'identique les
  semaines déjà écrites, sinon « le passé a changé » est consigné et la ligne n'est pas réécrite.

Performance passée ≠ garantie. Aucun gain n'est garanti.
"""

from __future__ import annotations

import csv
import functools
import io
import json
import math
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

from brvm_alpha import suivi as _s
from brvm_alpha.rendement import reglages as _rg
from brvm_alpha.suivi import bulletin as _bu
from brvm_alpha.suivi import carnet as _cn
from brvm_alpha.suivi import etat as _et

__all__ = ["CAPITAL", "COUTS", "NOMS", "contexte", "debut_par_defaut", "lancer", "maj", "operations_du_moteur", "spec",
           "temoin_model"]

NOMS = ("REF-S2", "N")
CAPITAL = 10_000_000
COUTS = "central"


def temoin_model(spec: Any, cfg: Any, sample: str, *, notes: Any = None, history_start: Any = None) -> Any:
    """Fabrique du témoin (contrat de ``runner.execute_run`` : ``factory(spec, cfg, sample)``).

    ``REF-S2`` : ``notes=None``. ``N`` : journal des notes (``NoteStore``), règle stricte à la date de décision.
    ``sample`` n'est pas lu (``runner.SAMPLES`` n'est pas consulté) ; ``validation_s1`` est toujours faux.
    ``history_start`` : ``None`` pour le suivi (le modèle part alors du début de S0, jamais de S1) ; le test de
    non-régression passe le début de S0, la valeur que ``brvm_alpha_model`` emploie pour le diagnostic S0."""
    from brvm_alpha.strategy import BrvmAlpha
    from brvm_alpha.validation import runner

    kw = dict(capital=float(spec.capital), notes=notes, window_basis="sessions", validation_s1=False,
              history_start=history_start)
    try:
        return BrvmAlpha(cfg, variant="REF", **kw)
    except ValueError:  # même repli que runner.brvm_alpha_model
        return runner._IndexModeModel(BrvmAlpha(cfg, variant="A", **kw))


def spec(capital: float = CAPITAL) -> Any:
    """``RunSpec("REF", costs="central", capital=10 000 000)``."""
    from brvm_alpha.validation import runner

    return runner.RunSpec("REF", costs=COUTS, capital=float(capital))


def debut_par_defaut(panels: Mapping[str, Any], reglages: Mapping[str, Any] | None = None) -> pd.Timestamp:
    """Dernière séance du panel au plus tard la veille du début du suivi (30/11/2026 si c'est une séance)."""
    veille = pd.Timestamp(str(_rg.lire(reglages, "dates.debut_suivi", "2026-12-01"))) - pd.Timedelta(days=1)
    idx = pd.DatetimeIndex(panels["close"].index)
    avant = idx[idx <= veille]
    if not len(avant):
        raise ValueError(f"panel sans séance au plus tard le {veille:%d/%m/%Y}")
    return pd.Timestamp(avant[-1]).normalize()


def contexte(fin: Any, *, debut: Any, notes: Any = None, history_start: Any = None, sample: str = "S2",
             strategy_params: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """``ctx`` de ``runner.execute_run``, écrit en entier : ``sample`` (lu par la seule fabrique, qui ne consulte pas
    ``SAMPLES``), ``start``, ``end``, ``decision_mode`` « evenementiel », ``strategy_params`` (YAML de stratégie, comme
    ``run_validation``), ``factory`` = :func:`temoin_model` (notes, ``history_start``), ``capture`` vide."""
    from brvm_alpha import settings

    d0 = _s.refuser_s1(debut, "le début du témoin")
    d1 = _s.refuser_s1(fin, "la fin du témoin")
    if d1 < d0:
        raise ValueError("fin du témoin avant son début")
    return {"sample": sample, "start": d0.date().isoformat(), "end": d1.date().isoformat(),
            "decision_mode": "evenementiel",
            "strategy_params": dict(strategy_params) if strategy_params is not None else settings.load_strategy_config(),
            "factory": functools.partial(temoin_model, notes=notes, history_start=history_start), "capture": ()}


def lancer(panels: Mapping[str, Any], *, debut: Any = None, fin: Any = None, notes: Any = None,
           history_start: Any = None, capital: float = CAPITAL, sample: str = "S2",
           reglages: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Run du moteur du test pour le témoin (``runner.execute_run``) : rend son résultat (``ok``, séries, ordres)."""
    from brvm_alpha.validation import runner

    d0 = pd.Timestamp(debut).normalize() if debut is not None else debut_par_defaut(panels, reglages)
    d1 = pd.Timestamp(fin).normalize() if fin is not None else pd.Timestamp(panels["close"].index[-1]).normalize()
    ctx = contexte(d1, debut=d0, notes=notes, history_start=history_start, sample=sample)
    return runner.execute_run(spec(capital), panels, ctx)


# ---------------------------------------------------------------------------
# Du run du moteur aux opérations du journal
# ---------------------------------------------------------------------------


def _wide(panels: Mapping[str, Any], cle: str) -> pd.DataFrame | None:
    return _et._wide(panels, cle)


def _paiements(panels: Mapping[str, Any], ev: pd.DataFrame, lag: int) -> list[pd.Timestamp]:
    """Date de paiement de chaque détachement, comme le moteur : ``dividend_payment_date`` du panel (ligne du jour ex),
    sinon ``lag`` séances après la date ex."""
    dates = pd.DatetimeIndex(pd.to_datetime(panels["close"].index)).normalize()
    pay = _wide(panels, "dividend_payment_date")
    out = []
    for r in ev.itertuples(index=False):
        ex = pd.Timestamp(r.date).normalize()
        p = None
        if pay is not None and str(r.symbol) in pay.columns:
            col = pd.to_datetime(pay[str(r.symbol)], errors="coerce")
            sel = col[col.index >= ex].dropna()
            if len(sel) and sel.index[0] == ex:
                p = pd.Timestamp(sel.iloc[0]).normalize()
        if p is None:
            i = int(dates.searchsorted(ex, side="left"))
            p = dates[min(i + int(lag), len(dates) - 1)] if i + int(lag) < len(dates) else ex + pd.offsets.BDay(int(lag))
        out.append(max(ex, pd.Timestamp(p)))
    return out


def operations_du_moteur(run: Mapping[str, Any], panels: Mapping[str, Any], *, debut: Any, capital: float = CAPITAL,
                         fin: Any = None, costs: Any = None, lag_paiement: int = 2) -> dict[str, Any]:
    """Opérations du témoin (format ``operations.csv``, ``source`` = ``moteur``) depuis un run de ``execute_run`` :

    * apport du capital à la date de début ;
    * achats et ventes : titres réels du jour (``raw_qty``), prix = montant ÷ titres, frais facturés (courtage, taxe,
      BRVM, DC/BR : la commission du moteur), ``autres_frais`` = écart et impact estimés que le moteur paie en
      liquidités ; cours de référence = clôture à la décision (``cout_prix`` = montant − titres ajustés × clôture
      ajustée de la décision, invariant aux divisions) ;
    * dividendes nets crédités à la date de paiement (comme le moteur) ; ceux qui ne sont pas encore payés à la fin
      sont « à recevoir » (tableau ``detaches``) ;
    * frais fixes (garde, tenue de compte) du moteur, regroupés par semaine et prélevés à sa dernière séance.

    Rend ``{"operations", "detaches", "ordres", "fin"}``."""
    from brvm_alpha.config import CostModel

    if not run.get("ok"):
        raise ValueError(f"run du moteur en échec : {run.get('error')}")
    cm = costs if isinstance(costs, CostModel) else _cout_central()
    d0 = _s.refuser_s1(debut, "le début du témoin")
    eq = run["equity"]
    d1 = pd.Timestamp(fin).normalize() if fin is not None else pd.Timestamp(eq.index[-1]).normalize()
    close_adj = _wide(panels, "close")
    rows: list[dict[str, Any]] = []
    base = {c: 0.0 for c in _cn.COLONNES_OPERATIONS}
    rows.append({**base, "date": d0, "type": "apport", "symbole": "", "titres": 0, "prix": 0.0,
                 "montant_net": float(capital), "source": "moteur", "cours_reference": None, "ordre": None})
    tr = run.get("trades")
    ordres: dict[tuple[str, str], dict[str, Any]] = {}
    if isinstance(tr, pd.DataFrame) and len(tr):
        tr = tr.sort_values(["date", "symbol"], kind="stable")
        for r in tr.itertuples(index=False):
            d = pd.Timestamp(r.date).normalize()
            if d > d1:
                continue
            q_adj, val = float(r.qty), float(r.value)
            raw = int(round(abs(float(getattr(r, "raw_qty", abs(q_adj)) or abs(q_adj)))))
            if raw <= 0 or val <= 0:
                continue
            sens = "achat" if q_adj > 0 else "vente"
            dec = pd.Timestamp(r.decision_date).normalize() if pd.notna(r.decision_date) else d
            ref_adj = float(close_adj[str(r.symbol)].loc[:dec].dropna().iloc[-1]) if close_adj is not None and \
                str(r.symbol) in close_adj.columns and close_adj[str(r.symbol)].loc[:dec].notna().any() else val / abs(q_adj)
            ref_val = abs(q_adj) * ref_adj
            comm = float(r.commission)
            courtage = val * cm.sgi_commission
            taxe = courtage * cm.vat_on_commission
            brvm = val * cm.brvm_fee
            dcbr = comm - courtage - taxe - brvm
            autres = float(r.cost) - comm
            cp = val - ref_val if sens == "achat" else ref_val - val
            rows.append({**base, "date": d, "type": sens, "symbole": str(r.symbol), "titres": raw, "prix": val / raw,
                         "courtage": courtage, "taxe": taxe, "brvm": brvm, "dcbr": dcbr, "autres_frais": autres,
                         "cout_prix": cp, "montant_net": -(val + float(r.cost)) if sens == "achat" else val - float(r.cost),
                         "source": "moteur", "cours_reference": ref_val / raw, "ordre": None})
            # Le moteur ne publie pas ses ordres : un ordre est compté à sa première exécution (date stable d'un
            # lancement à l'autre), sans titres demandés (taux de service global du moteur seulement).
            o = ordres.setdefault((dec.date().isoformat(), str(r.symbol)),
                                  {"date": d.date().isoformat(), "date_decision": dec.date().isoformat(),
                                   "symbole": str(r.symbol), "sens": sens, "titres": None, "executions": [],
                                   "etat": "servi", "expire_le": None})
            o["executions"].append({"date": d.date().isoformat(), "titres": raw, "prix": val / raw})
    detaches = pd.DataFrame(columns=["symbole", "date_detachement", "date_paiement", "montant", "titres"])
    ev = run.get("dividend_events")
    if isinstance(ev, pd.DataFrame) and len(ev):
        ev = ev[pd.to_datetime(ev["date"]).dt.normalize() <= d1].reset_index(drop=True)
        pays = _paiements(panels, ev, lag_paiement)
        af = _wide(panels, "adj_factor")
        recs = []
        for r, p in zip(ev.itertuples(index=False), pays, strict=True):
            ex = pd.Timestamp(r.date).normalize()
            f = float(af[str(r.symbol)].loc[:ex].dropna().iloc[-1]) if af is not None and str(r.symbol) in af.columns \
                and af[str(r.symbol)].loc[:ex].notna().any() else 1.0
            titres = int(round(float(r.qty) * f))
            recs.append({"symbole": str(r.symbol), "date_detachement": ex, "date_paiement": p,
                         "montant": float(r.credited), "titres": titres})
            if p <= d1:
                rows.append({**base, "date": p, "type": "dividende", "symbole": str(r.symbol), "titres": titres,
                             "prix": float(r.credited) / titres if titres else 0.0, "montant_net": float(r.credited),
                             "source": "moteur", "cours_reference": None, "ordre": None})
        detaches = pd.DataFrame(recs, columns=list(detaches.columns))
    cb = run.get("cost_breakdown")
    if isinstance(cb, pd.DataFrame) and len(cb):
        fixes = cb[[c for c in ("custody", "account_fees") if c in cb.columns]].sum(axis=1)
        fixes.index = pd.DatetimeIndex(pd.to_datetime(fixes.index)).normalize()
        fixes = fixes[(fixes.index >= d0) & (fixes.index <= d1) & (fixes > 0)]
        if len(fixes):
            vend = fixes.index + pd.to_timedelta((4 - fixes.index.day_of_week) % 7, unit="D")
            g = fixes.groupby(vend)
            for v, x in g:
                jour = x.index.max()
                rows.append({**base, "date": jour, "type": "frais_fixes", "symbole": "garde et tenue de compte",
                             "titres": 0, "prix": 0.0, "autres_frais": float(x.sum()), "montant_net": -float(x.sum()),
                             "source": "moteur", "cours_reference": None, "ordre": None})
    ops = pd.DataFrame(rows, columns=list(_cn.COLONNES_OPERATIONS))
    ops["date"] = pd.to_datetime(ops["date"]).dt.normalize()
    ordre_type = {"apport": 0, "achat": 2, "vente": 1, "dividende": 3, "frais_fixes": 4}
    ops = ops.assign(_o=ops["type"].map(ordre_type)).sort_values(["date", "_o", "symbole"], kind="stable")
    ops = ops.drop(columns="_o").reset_index(drop=True)
    return {"operations": ops, "detaches": detaches, "ordres": [ordres[k] for k in sorted(ordres)], "fin": d1}


def _cout_central() -> Any:
    from brvm_alpha import settings

    return settings.apply_to_platform_config(scenario=COUTS).costs


# ---------------------------------------------------------------------------
# Mise à jour des journaux
# ---------------------------------------------------------------------------


def _texte_csv(valeurs: list[str]) -> str:
    buf = io.StringIO()
    csv.writer(buf, lineterminator="").writerow(valeurs)
    return buf.getvalue()


def _fmt_csv(v: Any) -> str:
    if v is None or (isinstance(v, float) and not math.isfinite(v)):
        return ""
    if isinstance(v, (float, np.floating)):
        return f"{float(v):.2f}"
    if isinstance(v, pd.Timestamp):
        return v.date().isoformat()
    return str(v)


def _ecrire_csv_ajout(p: Path, df: pd.DataFrame, cle_date: str, jusqu_a: pd.Timestamp) -> dict[str, Any]:
    """Ajoute à ``p`` les lignes datées après la dernière date écrite (jusqu'à ``jusqu_a``) ; compare les lignes déjà
    écrites (« le passé a changé » si elles diffèrent). Jamais de réécriture."""
    df = df[pd.to_datetime(df[cle_date]) <= jusqu_a].copy()
    df[cle_date] = pd.to_datetime(df[cle_date]).dt.strftime("%Y-%m-%d")
    j = list(df.columns).index(cle_date)
    textes = [(str(rec[j]), _texte_csv([_fmt_csv(v) for v in rec])) for rec in df.itertuples(index=False)]
    if not p.exists():
        p.write_text(",".join(df.columns) + "\n", encoding="utf-8")
    deja = p.read_text(encoding="utf-8").splitlines()[1:]
    derniere = max((next(csv.reader([x]))[j] for x in deja), default="")
    anciens = sorted(t for d, t in textes if d <= derniere)
    nouveaux = [t for d, t in textes if d > derniere]
    if nouveaux:
        with p.open("a", encoding="utf-8") as fh:
            for t in nouveaux:
                fh.write(t + "\n")
    return {"ajoutees": len(nouveaux), "passe_a_change": anciens != sorted(deja)}


def maj(nom: str, panels: Mapping[str, Any], dossier: str | Path | None = None, *, debut: Any = None, fin: Any = None,
        jusqu_au: Any = None, notes: Any = None, capital: float = CAPITAL, maintenant: Any = None,
        history_start: Any = None, reglages: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Met à jour le journal d'un portefeuille du moteur (``REF-S2`` ou ``N``) dans ``<dossier>/<nom>/``.

    Relance le moteur de la première décision (``debut`` ; défaut : dernière séance ≤ 30/11/2026) jusqu'au dernier
    bulletin (``fin``), convertit le run en opérations, calcule les semaines finies et les écrit en ajout seul
    (:func:`brvm_alpha.suivi.bulletin.ecrire_semaines`). Avant toute séance après le début : « semaine 0 », rien n'est
    écrit. Refuse les dates de S1 et tout dossier sous ``reports/``. ``N`` exige ``notes`` (journal des notes)."""
    if nom not in NOMS:
        raise ValueError(f"portefeuille du moteur : {', '.join(NOMS)} (les autres passent par le carnet)")
    if nom == "N" and notes is None:
        raise ValueError("N : journal des notes obligatoire (règle stricte à la date de décision)")
    d = _s.dossier_portefeuille(nom, dossier)
    d0 = pd.Timestamp(debut).normalize() if debut is not None else debut_par_defaut(panels, reglages)
    _s.refuser_s1(d0, "le début du témoin")
    idx = pd.DatetimeIndex(pd.to_datetime(panels["close"].index)).normalize()
    d1 = pd.Timestamp(fin).normalize() if fin is not None else idx[-1]
    if len(idx[idx > d0]) == 0 or d1 <= d0:
        return {"nom": nom, "semaine_0": True, "debut": d0.date().isoformat(), "ecrit": False,
                "mention": "semaine 0 : état avant achat, aucune séance après la première décision"}
    run = lancer(panels, debut=d0, fin=d1, notes=notes, history_start=history_start, capital=capital, reglages=reglages)
    if not run.get("ok"):
        return {"nom": nom, "ok": False, "erreur": run.get("error"), "ecrit": False}
    conv = operations_du_moteur(run, panels, debut=d0, capital=capital, fin=d1)
    ops = conv["operations"]
    lignes = _bu.lignes_semaines(ops, panels, debut=d0, fin=d1, jusqu_au=jusqu_au, ordres=conv["ordres"],
                                 detaches=conv["detaches"], reglages=reglages)
    d.mkdir(parents=True, exist_ok=True)
    res = _bu.ecrire_semaines(nom, lignes, dossier, maintenant=maintenant)
    der = pd.Timestamp(lignes[-1]["date"]) if lignes else d0
    px = _et.prix_valorisation(panels)
    s = _et.serie(ops, panels, debut=d0, fin=der, prix=px)
    o_res = _ecrire_csv_ajout(d / "operations.csv", ops, "date", der)
    pos = _et.positions_par_seance(s, px)
    p_res = _ecrire_csv_ajout(d / "positions.csv", pos, "date", der) if len(pos) else {"ajoutees": 0,
                                                                                     "passe_a_change": False}
    if o_res["passe_a_change"] or p_res["passe_a_change"]:
        _s.ajouter_jsonl(d / "anomalies.jsonl", [{"date_utc": pd.Timestamp.now(tz="UTC").isoformat(),
                                                  "cause": "le passé a changé (opérations ou positions)",
                                                  "cause_probable": "donnée corrigée"}])
    eq = run["equity"]
    ecarts = []
    for l in lignes:
        t = pd.Timestamp(l["date"])
        if t in eq.index:
            ecarts.append(float(eq.loc[t]) - (float(l["valeur"]) + float(l["a_recevoir"])))
    controles = {"nom": nom, "debut": d0.date().isoformat(), "fin": d1.date().isoformat(),
                 "derniere_semaine": lignes[-1]["vendredi"] if lignes else None,
                 "identite_max_fcfa": max((abs(float(l["ecart_identite"])) for l in lignes), default=0.0),
                 "ecart_moteur_max_fcfa": max((abs(x) for x in ecarts), default=0.0),
                 "taux_de_service_moteur": run.get("fill_rate"), "controles_moteur": run.get("controles"),
                 "mode_decision": (run.get("meta") or {}).get("mode_decision"), "bandeau": _s.BANNER,
                 "mention": ("Valeur du journal + dividendes à recevoir comparée à la valeur liquidative du moteur ; "
                             "titres demandés non publiés par le moteur (taux de service global seulement).")}
    (d / "controles.json").write_text(json.dumps(_s._jsonable(controles), ensure_ascii=False, indent=1) + "\n",
                                      encoding="utf-8")
    return {"nom": nom, "ok": True, "ecrit": True, "lignes": lignes, "semaines": res, "operations": o_res,
            "positions": p_res, "controles": controles, "run": run, "conversion": conv,
            "passe_a_change": bool(res["passe_a_change"] or o_res["passe_a_change"] or p_res["passe_a_change"])}
