"""F12 — État d'un portefeuille suivi et pont « fuites / pertes latentes », avec une seule base.

Cahier ``docs/RENDEMENT_NET.md``, §F10 (ligne de la semaine) et §F12 (état et pont). Les calculs partent des
**opérations** (format ``operations.csv`` : achats, ventes, dividendes, frais fixes, apports, retraits, divisions), qu'elles
viennent du carnet (papier, avis d'opéré) ou du moteur (témoin), et des cours du panel (lecture seule).

Pont, une seule base : le cours de référence avant l'ordre. Pour chaque exécution j (n titres, prix x, cours de
référence r = dernière clôture connue à la décision) :

* ``cout_prix_j = n × (x − r)`` pour un achat, ``n × (r − x)`` pour une vente (peut être négatif) ;
* ``effet_cours = T_t − T_0 − Σ_achats n × r + Σ_ventes n × r`` (aucun frais n'y entre) ;
* ``frais_transaction = Σ frais facturés + Σ cout_prix`` ;
* identité **E = effet_cours + dividendes_recus − frais_transaction − frais_fixes + interets**, au franc près, avec
  ``E = V − K``, ``V = T + L`` (titres au cours plus liquidités) et ``K`` l'argent engagé (apports − retraits, titres
  apportés comptés à leur clôture du jour d'apport, ``T_0``).

Entre un détachement et le paiement, l'effet de cours contient la baisse du détachement ; le dividende à recevoir est
donné à part (« à recevoir »), hors identité. Valeur de part (rendement pondéré par le temps) : ``u = 1`` au départ ; à
chaque apport ou retrait, des parts sont créées ou détruites à la valeur de part de la veille ; l'écart au marché est
``(u_t ÷ u_0) ÷ (indice_t ÷ indice_0) − 1``.

Cours employés : clôture réelle du jour (``close_raw``, sinon ``close``) ; titre sans cours ce jour : dernier cours connu ;
titre hors bulletin (absent du bulletin du jour : suspendu de longue date, radié) : dernier cours − 10 % (règle existante
de l'ordre de bataille). Aucune écriture.

Performance passée ≠ garantie. Aucun gain n'est garanti.
"""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from brvm_alpha.suivi import carnet as _cn

__all__ = ["DECOTE_HORS_BULLETIN", "COMPOSANTES", "a_recevoir", "etat", "indice_marche", "pont", "prix_reels",
           "prix_valorisation", "serie"]

#: Décote d'un titre hors bulletin (suspendu ou radié) : dernier cours − 10 % (règle existante).
DECOTE_HORS_BULLETIN = 0.10
COMPOSANTES = ("effet_cours", "dividendes_recus", "frais_transaction", "frais_fixes", "interets")


def _f(x: Any, defaut: float = 0.0) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return defaut
    return v if math.isfinite(v) else defaut


def _wide(panels: Mapping[str, Any] | None, cle: str) -> pd.DataFrame | None:
    if not isinstance(panels, Mapping):
        return None
    x = panels.get(cle)
    if not isinstance(x, pd.DataFrame) or not len(x):
        return None
    out = x.copy()
    out.index = pd.DatetimeIndex(pd.to_datetime(out.index)).normalize()
    out.columns = out.columns.astype(str)
    return out.sort_index()


def _brut(panels: Mapping[str, Any]) -> pd.DataFrame:
    p = _wide(panels, "close_raw")
    if p is None:
        p = _wide(panels, "close")
    if p is None:
        raise ValueError("panel sans cours de clôture (close_raw ou close)")
    return p.astype(float)


def prix_reels(panels: Mapping[str, Any]) -> pd.DataFrame:
    """Clôtures réelles (unités du jour : ``close_raw``, à défaut ``close``), dernier cours connu reporté (titre sans
    cours ce jour : dernier cours connu)."""
    return _brut(panels).ffill()


def prix_valorisation(panels: Mapping[str, Any]) -> pd.DataFrame:
    """Cours de valorisation : clôture réelle reportée ; titre **hors bulletin** (absent du bulletin d'une séance
    publiée alors qu'il avait déjà coté : suspendu de longue date, radié) : dernier cours − 10 %, arrondi au pas
    inférieur (règle existante de l'ordre de bataille, §7.1.7 de la spécification)."""
    from brvm_alpha.portfolio import recommend as R

    brut = _brut(panels)
    p = brut.ffill()
    hors = brut.isna() & p.notna()
    if bool(hors.to_numpy().any()):
        dec = p.where(~hors).copy()
        for c in p.columns[hors.any(axis=0)]:
            m = hors[c]
            dec.loc[m, c] = [R.floor_to_tick(float(x) * (1.0 - DECOTE_HORS_BULLETIN)) or float(x) for x in p.loc[m, c]]
        p = dec
    return p


def indice_marche(panels: Mapping[str, Any]) -> pd.Series | None:
    """Composite TR du panel (``market_tr``), ``None`` s'il manque."""
    if not isinstance(panels, Mapping):
        return None
    x = panels.get("market_tr")
    if isinstance(x, pd.DataFrame):
        x = x.iloc[:, 0]
    if not isinstance(x, pd.Series) or not len(x):
        return None
    s = x.astype(float).copy()
    s.index = pd.DatetimeIndex(pd.to_datetime(s.index)).normalize()
    return s.sort_index().ffill()


def _frais(df: pd.DataFrame) -> pd.Series:
    return df[["courtage", "taxe", "brvm", "dcbr", "autres_frais"]].astype(float).sum(axis=1)


def serie(ops: pd.DataFrame, panels: Mapping[str, Any], *, debut: Any = None, fin: Any = None,
          prix: pd.DataFrame | None = None) -> pd.DataFrame:
    """Série quotidienne (une ligne par séance du panel, de ``debut`` à ``fin``) : ``T`` (titres au cours), ``L``
    (liquidités), ``V``, ``K`` (argent engagé), ``E`` = V − K, composantes cumulées du pont, ``ecart_identite`` (0 au franc
    près), ``part_investie``, valeur de part ``u`` et parts, indice de marché, flux d'apports du jour.

    Une opération datée un jour sans séance compte à la séance suivante."""
    px = prix if prix is not None else prix_valorisation(panels)
    dates = pd.DatetimeIndex(px.index)
    ops = ops.copy() if ops is not None else pd.DataFrame(columns=list(_cn.COLONNES_OPERATIONS))
    if len(ops):
        ops["date"] = pd.to_datetime(ops["date"]).dt.normalize()
    d0 = pd.Timestamp(debut).normalize() if debut is not None else (ops["date"].min() if len(ops) else dates[0])
    d1 = pd.Timestamp(fin).normalize() if fin is not None else dates[-1]
    dates = dates[(dates >= d0) & (dates <= d1)]
    if not len(dates):
        raise ValueError("aucune séance dans la période demandée")
    if len(ops):
        pos = dates.searchsorted(ops["date"].to_numpy(), side="left")
        ops = ops.assign(_i=pos)
        ops = ops[ops["_i"] < len(dates)]
    else:
        ops = ops.assign(_i=pd.Series(dtype=int))
    n = len(dates)

    def cum(masque: pd.Series, valeurs: pd.Series) -> np.ndarray:
        a = np.zeros(n)
        if len(ops):
            sel = ops[masque]
            np.add.at(a, sel["_i"].to_numpy(dtype=int), valeurs[masque].to_numpy(dtype=float))
        return np.cumsum(a)

    ty = ops["type"].astype(str) if len(ops) else pd.Series(dtype=str)
    titres = ops["titres"].astype(float) if len(ops) else pd.Series(dtype=float)
    prixo = ops["prix"].astype(float) if len(ops) else pd.Series(dtype=float)
    brut = titres * prixo
    cp = ops["cout_prix"].astype(float) if len(ops) else pd.Series(dtype=float)
    mnet = ops["montant_net"].astype(float) if len(ops) else pd.Series(dtype=float)
    fr = _frais(ops) if len(ops) else pd.Series(dtype=float)
    ach, ven = ty == "achat", ty == "vente"
    apt = (ty == "apport") & (titres > 0)
    apc = (ty == "apport") & ~(titres > 0)
    ret = ty == "retrait"
    L = cum(ty.notna() if len(ops) else ty, mnet)
    T0 = cum(apt, brut)
    Kf = np.zeros(n)
    if len(ops):
        flux = mnet.where(apc | ret, 0.0) + brut.where(apt, 0.0)
        np.add.at(Kf, ops["_i"].to_numpy(dtype=int), flux.to_numpy(dtype=float))
    K = np.cumsum(Kf)
    ref_ach = cum(ach, brut - cp)
    ref_ven = cum(ven, brut + cp)
    ffact = cum(ach | ven, fr)
    cprix = cum(ach | ven, cp)
    div = cum(ty == "dividende", mnet)
    fixes = cum(ty == "frais_fixes", -mnet)
    inter = cum(ty == "interets", mnet)
    # titres détenus par séance
    syms = sorted({str(s) for s in ops["symbole"]} - {""}) if len(ops) else []
    signe = pd.Series(0.0, index=ops.index)
    if len(ops):
        signe = titres.where(ach | apt | (ty == "division"), 0.0) - titres.where(ven, 0.0)
    T = np.zeros(n)
    positions = pd.DataFrame(0.0, index=dates, columns=syms)
    if syms:
        dq = np.zeros((n, len(syms)))
        col = {s: j for j, s in enumerate(syms)}
        m = signe != 0
        np.add.at(dq, (ops.loc[m, "_i"].to_numpy(dtype=int), ops.loc[m, "symbole"].map(col).to_numpy(dtype=int)),
                  signe[m].to_numpy(dtype=float))
        q = np.cumsum(dq, axis=0)
        positions = pd.DataFrame(q, index=dates, columns=syms)
        pr = px.reindex(index=dates, columns=syms).copy()
        dernier = ops[ach | ven | apt].groupby("symbole")["prix"].last() if (ach | ven | apt).any() else pd.Series(dtype=float)
        for s in syms:
            if pr[s].isna().any():
                pr[s] = pr[s].ffill().fillna(_f(dernier.get(s), 0.0))
        T = np.nansum(q * pr.to_numpy(dtype=float), axis=1)
    V = T + L
    E = V - K
    effet = T - T0 - ref_ach + ref_ven
    ftr = ffact + cprix
    ecart = E - (effet + div - ftr - fixes + inter)
    # valeur de part
    u = np.ones(n)
    parts = np.zeros(n)
    prev_u, prev_p = 1.0, 0.0
    for i in range(n):
        nouv = Kf[i] / prev_u if prev_u > 0 else 0.0
        p_i = prev_p + nouv
        u_i = V[i] / p_i if p_i > 1e-9 else prev_u
        u[i], parts[i] = u_i, p_i
        prev_u, prev_p = u_i, p_i
    ind = indice_marche(panels)
    out = pd.DataFrame({"T": T, "L": L, "V": V, "K": K, "T0": T0, "E": E, "effet_cours": effet, "dividendes_recus": div,
                        "frais_factures": ffact, "cout_prix": cprix, "frais_transaction": ftr, "frais_fixes": fixes,
                        "interets": inter, "ecart_identite": ecart, "u": u, "parts": parts, "flux_apports": Kf,
                        "part_investie": np.where(V > 0, T / np.where(V > 0, V, 1.0), 0.0)}, index=dates)
    out["indice"] = ind.reindex(dates).ffill().to_numpy() if ind is not None else np.nan
    out.attrs["positions"] = positions
    return out


def pont(ops: pd.DataFrame, panels: Mapping[str, Any], date: Any, *, debut: Any = None,
         prix: pd.DataFrame | None = None) -> dict[str, Any]:
    """Pont au jour ``date`` (dernière séance ≤ date) : valeur, argent engagé, écart et ses cinq composantes ;
    ``identite_ok`` vrai si l'écart est nul au franc près."""
    s = serie(ops, panels, debut=debut, fin=date, prix=prix)
    r = s.iloc[-1]
    out = {k: float(r[k]) for k in ("T", "L", "V", "K", "T0", "E", *COMPOSANTES, "frais_factures", "cout_prix",
                                    "ecart_identite", "part_investie", "u")}
    out["date"] = s.index[-1].date().isoformat()
    out["identite_ok"] = abs(out["ecart_identite"]) < 0.5
    return out


def a_recevoir(ops: pd.DataFrame, detaches: pd.DataFrame | None, date: Any) -> dict[str, Any]:
    """Dividendes détachés et pas encore crédités à ``date`` (hors identité) : ``detaches`` a les colonnes ``symbole``,
    ``date_detachement``, ``date_paiement``, ``montant`` (net, pour les titres détenus la veille)."""
    t = pd.Timestamp(date).normalize()
    if detaches is None or not len(detaches):
        return {"total": 0.0, "lignes": []}
    d = detaches.copy()
    d["date_detachement"] = pd.to_datetime(d["date_detachement"]).dt.normalize()
    d["date_paiement"] = pd.to_datetime(d["date_paiement"]).dt.normalize()
    m = (d["date_detachement"] <= t) & (d["date_paiement"] > t)
    sel = d[m]
    return {"total": float(sel["montant"].astype(float).sum()),
            "lignes": [{"symbole": str(r.symbole), "date_detachement": r.date_detachement.date().isoformat(),
                        "date_paiement": r.date_paiement.date().isoformat(), "montant": float(r.montant)}
                       for r in sel.itertuples(index=False)]}


def _dividende_attendu(panels: Mapping[str, Any], sym: str, t: pd.Timestamp) -> float:
    tab = panels.get("dividends_table") if isinstance(panels, Mapping) else None
    if not isinstance(tab, pd.DataFrame) or not len(tab) or "symbol" not in tab.columns:
        return 0.0
    x = tab[tab["symbol"].astype(str) == sym]
    if "date" in x.columns:
        x = x[pd.to_datetime(x["date"]) <= t]
    if not len(x):
        return 0.0
    x = x.sort_values("ex_date" if "ex_date" in x.columns else "date")
    col = "amount_cashflow" if "amount_cashflow" in x.columns else "amount"
    return _f(x[col].iloc[-1])


def _plus_bas(prix: pd.Series, ops: pd.DataFrame, detaches: pd.DataFrame | None, sym: str, depuis: pd.Timestamp,
              t: pd.Timestamp, n: int, pr: float) -> float:
    """Plus bas de ``(cours + dividendes par titre reçus ou à recevoir depuis l'achat) ÷ PR − 1`` sur les séances depuis
    le premier achat : un détachement (baisse du cours compensée par le dividende à recevoir) n'abaisse rien."""
    h = prix.loc[depuis:t].dropna()
    if not len(h) or n <= 0:
        return 0.0
    dv = pd.Series(0.0, index=h.index)
    if detaches is not None and len(detaches):
        d = detaches[detaches["symbole"].astype(str) == sym]
        for r in d.itertuples(index=False):
            ex = pd.Timestamp(r.date_detachement).normalize()
            if ex > depuis:
                dv.loc[dv.index >= ex] += float(r.montant) / n
    elif ops is not None and len(ops):
        d = ops[(ops["type"] == "dividende") & (ops["symbole"].astype(str) == sym)]
        for r in d.itertuples(index=False):
            dt = pd.Timestamp(r.date).normalize()
            if dt > depuis:
                dv.loc[dv.index >= dt] += float(r.montant_net) / n
    return float(((h + dv) / pr - 1.0).min())


def etat(source: Any, panels: Mapping[str, Any], date: Any, *, costs: Any = None, grille: Any = None,
         detaches: pd.DataFrame | None = None, debut: Any = None) -> dict[str, Any]:
    """État du portefeuille à ``date`` (§F12). ``source`` : un :class:`~brvm_alpha.suivi.carnet.Carnet` ou un tableau
    d'opérations. Par ligne : titres, cours, valeur, coût (titres × PR), prix de revient, dividendes reçus, résultat non
    réalisé, résultat réalisé, effet de cours (contre le cours de référence), baisse depuis l'achat et plus bas depuis
    l'achat (dividendes compris, à recevoir inclus : un détachement n'allume rien), frais annuels contre dividende
    attendu, et « si l'on vendait aujourd'hui » (frais de sortie, résultat réalisé, dividende attendu abandonné).
    Portefeuille : le pont de :func:`pont`. Aucune écriture."""
    from brvm_alpha.config import CostModel
    from brvm_alpha.portfolio import recommend as R

    ops = source.operations(date) if isinstance(source, _cn.Carnet) else source
    t = pd.Timestamp(date).normalize()
    px = prix_valorisation(panels)
    s = serie(ops, panels, debut=debut, fin=t, prix=px)
    tt = s.index[-1]
    cm = costs if isinstance(costs, CostModel) else CostModel()
    tenue = _f(getattr(cm, "account_fee_per_line_fcfa", 0.0))
    garde = _f(getattr(cm, "annual_custody", 0.0))
    if grille is not None:
        tenue, garde = grille.valeur("tenue_par_ligne"), grille.valeur("garde")
    pos = _cn.positions_depuis_operations(ops, tt)
    recv = a_recevoir(ops, detaches, tt)
    recv_l: dict[str, float] = {}
    for l in recv["lignes"]:
        recv_l[l["symbole"]] = recv_l.get(l["symbole"], 0.0) + l["montant"]
    lignes = []
    for sym, p in sorted(pos.items()):
        if p["titres"] <= 0:
            continue
        n = int(p["titres"])
        c = _f(px[sym].loc[:tt].dropna().iloc[-1]) if sym in px.columns and px[sym].loc[:tt].notna().any() else 0.0
        val = n * c
        pr = _f(p["prix_de_revient"])
        cout = n * pr
        div_l = _f(p["dividendes_recus"]) + recv_l.get(sym, 0.0)
        ratio = ((c + div_l / n) / pr - 1.0) if pr > 0 else 0.0
        bas = ratio
        if sym in px.columns and p["premier_achat"] is not None and pr > 0:
            bas = min(ratio, _plus_bas(px[sym], ops, detaches, sym, pd.Timestamp(p["premier_achat"]), tt, n, pr))
        da = _dividende_attendu(panels, sym, tt) * n
        sortie = R.order_costs(n, c, cm, side="vente")["total"] if c > 0 else 0
        lignes.append({"symbole": sym, "titres": n, "cours": c, "valeur": val, "prix_de_revient": pr, "cout": cout,
                       "dividendes_recus": _f(p["dividendes_recus"]), "a_recevoir": recv_l.get(sym, 0.0),
                       "resultat_non_realise": val - cout, "resultat_realise": _f(p["resultat_realise"]),
                       "effet_cours": val - n * _f(p["cours_reference_moyen"]),
                       "baisse_depuis_achat": max(0.0, -ratio), "plus_bas_depuis_achat": min(bas, ratio),
                       "frais_annuels": R.round_fcfa(garde * val) + tenue, "dividende_attendu": da,
                       "premier_achat": pd.Timestamp(p["premier_achat"]).date().isoformat() if p["premier_achat"] is not None
                       else None,
                       "si_l_on_vendait": {"frais_sortie": int(sortie), "resultat_realise": val - cout - sortie,
                                           "dividende_abandonne": da}})
    r = s.iloc[-1]
    pertes_nr = sum(min(0.0, l["effet_cours"]) for l in lignes)
    realise_neg = sum(min(0.0, _f(p["resultat_realise"])) for p in pos.values())
    out = {"date": tt.date().isoformat(), "lignes": lignes, "valeur_titres": float(r["T"]), "liquidites": float(r["L"]),
           "valeur": float(r["V"]), "argent_engage": float(r["K"]), "ecart": float(r["E"]),
           "pont": {k: float(r[k]) for k in COMPOSANTES}, "frais_factures": float(r["frais_factures"]),
           "cout_prix": float(r["cout_prix"]), "ecart_identite": float(r["ecart_identite"]),
           "identite_ok": abs(float(r["ecart_identite"])) < 0.5,
           "fuites_definitives": float(r["frais_transaction"] + r["frais_fixes"]),
           "pertes_non_realisees": float(pertes_nr), "pertes_realisees": float(realise_neg),
           "part_investie": float(r["part_investie"]), "a_recevoir": recv, "valeur_de_part": float(r["u"])}
    return out


def ligne_vide(date: Any) -> dict[str, Any]:
    """État avant tout achat (semaine 0) : aucun titre, aucune opération."""
    return {"date": pd.Timestamp(date).date().isoformat(), "lignes": [], "valeur_titres": 0.0, "liquidites": 0.0,
            "valeur": 0.0, "argent_engage": 0.0, "ecart": 0.0, "pont": {k: 0.0 for k in COMPOSANTES}}


def _positions_jour(s: pd.DataFrame, t: Any) -> Mapping[str, float]:
    pos = s.attrs.get("positions")
    if not isinstance(pos, pd.DataFrame) or not len(pos):
        return {}
    r = pos.loc[: pd.Timestamp(t)].iloc[-1]
    return {k: float(v) for k, v in r.items() if abs(v) > 1e-9}


def positions_par_seance(s: pd.DataFrame, prix: pd.DataFrame, seances: Sequence[pd.Timestamp] | None = None) -> pd.DataFrame:
    """Lignes de ``positions.csv`` (``date, symbole, titres, cours, valeur``) pour les séances demandées."""
    pos = s.attrs.get("positions")
    rows = []
    if not isinstance(pos, pd.DataFrame) or not len(pos):
        return pd.DataFrame(columns=["date", "symbole", "titres", "cours", "valeur"])
    jours = pd.DatetimeIndex(seances) if seances is not None else pos.index
    for d in jours:
        if d not in pos.index:
            continue
        r = pos.loc[d]
        for sym, q in r.items():
            if abs(q) < 1e-9:
                continue
            c = _f(prix[sym].loc[:d].dropna().iloc[-1]) if sym in prix.columns and prix[sym].loc[:d].notna().any() else 0.0
            rows.append({"date": d.date().isoformat(), "symbole": sym, "titres": int(round(q)), "cours": c,
                         "valeur": float(round(q) * c)})
    return pd.DataFrame(rows, columns=["date", "symbole", "titres", "cours", "valeur"])
