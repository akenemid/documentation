"""Contrôles comptables et d'exécution d'un run (pré-vol S0 et test unique S1).

Ces contrôles ne mesurent **aucune** performance : ils vérifient que la simulation respecte
les règles du moteur (spécification §6, §7.1, §7.2) et que sa comptabilité est cohérente.
Ils sont calculés pour chaque run par l'exécuteur (``runner.execute_run``) et publiés dans
``metrics.json`` (clé ``controles`` de chaque run) :

* **liquidités** : cash réglé ≥ 0 à chaque séance (aucun levier, §6) ;
* **identité de la VL** : ``VL = cash − frais dus + créances + Σ q·P`` à chaque séance ;
* **identité de flux** : ``ΔVL = Σ q(t−1)·ΔP + Σ q_ordre·(P − prix d'exécution) + dividendes −
  coûts (+ rémunération du cash)`` à chaque séance (écart résiduel publié, rompus de
  division compris) ;
* **bornes de cotation** (§7.1.3) : aucune vente une séance à la borne basse, aucun achat une
  séance à la borne haute ;
* **coût par aller** (§7.2) : coût proportionnel (courtage, taxe, BRVM, DC/BR, demi-spread,
  impact) rapporté au montant de chaque exécution, médiane et moyenne pondérée ;
* **ordres bloqués** : nombre par motif (borne, volume, cash, titre non échangé, choc pays…).

Performance passée ≠ garantie. Aucun gain n'est garanti.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

__all__ = ["CONTROL_TOLERANCE", "accounting_controls"]

#: Écart relatif toléré (fraction de la VL) pour les identités comptables.
CONTROL_TOLERANCE = 1e-6


def _f(x: Any) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return math.nan
    return v if math.isfinite(v) else math.nan


def _cost_stats(trades: pd.DataFrame) -> dict[str, Any]:
    """Coût proportionnel par exécution (fraction du montant), par côté et au total."""
    out: dict[str, Any] = {"n_executions": int(len(trades))}
    if not len(trades) or not {"value", "cost", "qty"} <= set(trades.columns):
        return out
    val = trades["value"].astype(float).abs()
    cost = trades["cost"].astype(float)
    ok = val > 0
    rate = (cost[ok] / val[ok]).astype(float)
    out.update(
        cout_aller_median=_f(rate.median()),
        cout_aller_moyen_pondere=_f(cost[ok].sum() / val[ok].sum()) if bool(ok.any()) else math.nan,
        cout_aller_p10=_f(rate.quantile(0.10)),
        cout_aller_p90=_f(rate.quantile(0.90)),
    )
    side = np.sign(trades["qty"].astype(float))
    for lab, sgn in (("achats", 1.0), ("ventes", -1.0)):
        m = ok & (side == sgn)
        out[f"cout_aller_moyen_pondere_{lab}"] = (_f(cost[m].sum() / val[m].sum()) if bool(m.any()) else math.nan)
        out[f"n_{lab}"] = int((side == sgn).sum())
    if "half_spread" in trades.columns:
        out["demi_spread_median"] = _f(trades.loc[ok, "half_spread"].astype(float).median())
    if "participation" in trades.columns:
        out["participation_mediane"] = _f(trades.loc[ok, "participation"].astype(float).median())
    return out


def accounting_controls(bt: Any, res: Any) -> dict[str, Any]:
    """Contrôles d'un run : ``bt`` (``Backtester`` après ``run``) et ``res`` (``BacktestResult``).

    Renvoie un dictionnaire sérialisable : ``cash_min_fcfa``, ``exposition_max``,
    ``identite_vl_ecart_max`` et ``identite_flux_ecart_max`` (fractions de la VL),
    ``ventes_a_la_borne_basse``, ``achats_a_la_borne_haute``, statistiques de coût par aller,
    ``ordres_bloques`` (par motif), ``ok`` (tous les contrôles bloquants verts) et
    ``anomalies`` (liste de phrases). Aucune performance n'est calculée.
    """
    eq = pd.Series(res.equity, dtype=float)
    idx = pd.DatetimeIndex(eq.index)
    rows = np.asarray(pd.DatetimeIndex(bt.dates).get_indexer(idx))
    out: dict[str, Any] = {"n_seances": int(len(idx))}
    anomalies: list[str] = []
    if not len(idx) or (rows < 0).any():
        out.update(ok=False, anomalies=["calendrier du résultat absent du moteur : contrôles impossibles"])
        return out
    cash = pd.Series(res.cash, dtype=float).reindex(idx).to_numpy()
    pay = pd.Series(getattr(res, "payables", 0.0), dtype=float).reindex(idx).fillna(0.0).to_numpy()
    recv = pd.Series(getattr(res, "receivables", 0.0), dtype=float).reindex(idx).fillna(0.0).to_numpy()
    pos = pd.DataFrame(res.positions).reindex(index=idx, columns=list(bt.symbols)).fillna(0.0).to_numpy(dtype=float)
    pv = np.nan_to_num(np.asarray(bt._px_val, dtype=float)[rows])
    nav = eq.to_numpy()
    scale = np.maximum(np.abs(nav), 1.0)

    # 1. liquidités réglées ≥ 0 (aucun levier)
    out["cash_min_fcfa"] = _f(np.min(cash))
    out["frais_dus_max_fcfa"] = _f(np.max(pay)) if len(pay) else 0.0
    w_sum = pd.DataFrame(res.weights).sum(axis=1)
    out["exposition_max"] = _f(w_sum.max())
    if out["cash_min_fcfa"] < -1e-6 * max(1.0, float(getattr(bt, "capital", 1.0))):
        anomalies.append(f"cash réglé négatif ({out['cash_min_fcfa']:.0f} FCFA)")

    # 2. identité de la VL (stock)
    stock = (pos * pv).sum(axis=1)
    gap_stock = (cash - pay + recv + stock) - nav
    out["identite_vl_ecart_max"] = _f(np.max(np.abs(gap_stock) / scale))

    # 3. identité de flux (ΔVL expliquée par les cours, les exécutions, les dividendes et les coûts)
    trades = res.trades if isinstance(res.trades, pd.DataFrame) else pd.DataFrame()
    t_pnl = np.zeros(len(idx))
    if len(trades):
        sym_pos = {s: i for i, s in enumerate(bt.symbols)}
        k = idx.get_indexer(pd.DatetimeIndex(trades["date"]))
        j = np.array([sym_pos.get(str(s), -1) for s in trades["symbol"]])
        good = (k >= 0) & (j >= 0)
        q = trades["qty"].to_numpy(dtype=float)
        p = trades["price"].to_numpy(dtype=float)
        contrib = np.where(good, q * (pv[np.clip(k, 0, None), np.clip(j, 0, None)] - p), 0.0)
        np.add.at(t_pnl, np.clip(k, 0, None), contrib)
    div = pd.Series(res.dividends, dtype=float).reindex(idx).fillna(0.0).to_numpy()
    costs = pd.Series(res.costs_daily, dtype=float).reindex(idx).fillna(0.0).to_numpy()
    rate = float(getattr(getattr(bt, "execution", None), "cash_rate_annual", 0.0) or 0.0)
    interest = np.zeros(len(idx))
    if rate != 0.0 and len(idx) > 1:
        daily = (1.0 + rate) ** (1.0 / float(getattr(bt, "periods_per_year", 252))) - 1.0
        steps = np.asarray(getattr(bt, "_steps", np.ones(len(bt.dates))), dtype=float)[rows]
        interest[1:] = cash[:-1] * ((1.0 + daily) ** steps[1:] - 1.0)
    # Rompus d'une attribution (fraction de titre réel) : vendus au dernier cours connu (moteur), donc
    # non exposés à la variation du jour de la division : correction du terme de valorisation.
    rompus = np.zeros(len(idx))
    ev = getattr(res, "events", None)
    if isinstance(ev, pd.DataFrame) and len(ev) and "event" in ev.columns and len(idx) > 1:
        rp = ev[ev["event"] == "rompus_credites"]
        if len(rp):
            sym_pos = {s: i for i, s in enumerate(bt.symbols)}
            af = np.asarray(getattr(bt, "_af", np.ones((len(bt.dates), len(bt.symbols)))), dtype=float)
            for rec in rp.to_dict("records"):
                kk = int(idx.get_indexer([pd.Timestamp(rec["date"])])[0])
                jj = sym_pos.get(str(rec["symbol"]), -1)
                if kk >= 1 and jj >= 0:
                    f = float(af[rows[kk], jj]) or 1.0
                    rompus[kk] += float(rec["qty"]) / f * (pv[kk, jj] - pv[kk - 1, jj])
    out["n_rompus"] = int((rompus != 0).sum())
    gap_flow = np.zeros(len(idx))
    if len(idx) > 1:
        mark = (pos[:-1] * (pv[1:] - pv[:-1])).sum(axis=1)
        expected = mark - rompus[1:] + t_pnl[1:] + div[1:] - costs[1:] + interest[1:]
        gap_flow[1:] = np.diff(nav) - expected
    gap_flow[0] = (nav[0] - float(getattr(bt, "capital", nav[0]))) - (t_pnl[0] + div[0] - costs[0])
    out["identite_flux_ecart_max"] = _f(np.max(np.abs(gap_flow) / scale))
    out["identite_flux_ecart_cumule_fcfa"] = _f(np.sum(gap_flow))
    for key, lab in (("identite_vl_ecart_max", "identité de la VL"), ("identite_flux_ecart_max", "identité de flux")):
        if not out[key] <= CONTROL_TOLERANCE:
            anomalies.append(f"{lab} : écart maximal {out[key]:.2e} de la VL > {CONTROL_TOLERANCE:.0e}")

    # 4. bornes de cotation (§7.1.3)
    n_sell_low = n_buy_up = 0
    if len(trades):
        sym_pos = {s: i for i, s in enumerate(bt.symbols)}
        t_rows = np.asarray(pd.DatetimeIndex(bt.dates).get_indexer(pd.DatetimeIndex(trades["date"])))
        j = np.array([sym_pos.get(str(s), -1) for s in trades["symbol"]])
        good = (t_rows >= 0) & (j >= 0)
        lim_down = np.asarray(bt._lim_down, dtype=bool)
        lim_up = np.asarray(bt._lim_up, dtype=bool)
        q = trades["qty"].to_numpy(dtype=float)
        tr_, jr_ = np.clip(t_rows, 0, None), np.clip(j, 0, None)
        n_sell_low = int((good & (q < 0) & lim_down[tr_, jr_]).sum())
        n_buy_up = int((good & (q > 0) & lim_up[tr_, jr_]).sum())
    out["ventes_a_la_borne_basse"] = n_sell_low
    out["achats_a_la_borne_haute"] = n_buy_up
    if n_sell_low or n_buy_up:
        anomalies.append(f"exécutions aux bornes : {n_sell_low} vente(s) à la borne basse, {n_buy_up} achat(s) à "
                         "la borne haute")

    # 5. coût par aller (§7.2) et ordres bloqués
    out["couts"] = _cost_stats(trades)
    bl = getattr(res, "blocked", None)
    out["ordres_bloques"] = ({str(k): int(v) for k, v in bl["reason"].value_counts().items()}
                             if isinstance(bl, pd.DataFrame) and len(bl) and "reason" in bl.columns else {})
    out["anomalies"] = anomalies
    out["ok"] = not anomalies
    return out
