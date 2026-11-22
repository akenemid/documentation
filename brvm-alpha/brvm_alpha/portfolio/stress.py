"""Scénarios de stress du §9.3 (ST1-ST10) appliqués à un portefeuille cible.

Point d'entrée : :func:`stress_tests` (``weights``, ``panels``, ``asof``, ``capital``) →
``DataFrame`` d'une ligne par scénario (et par variante d'un scénario), avec la **variation de
valeur** estimée en FCFA et en % du capital (négative = perte).

Méthodes (toutes des **estimations** sous hypothèses, jamais des prévisions) :

* **Marché** (ST1, ST2, ST3) : ``perte = β_p × choc × valeur investie``. ``β_p`` est le bêta
  hebdomadaire (W-FRI) du panier de titres détenus contre le Composite TR, sur 104 semaines au
  plus (52 au moins) **jusqu'à ``asof``**, sans jamais lire l'échantillon vierge S1
  (``history_start`` = début de S0 par défaut), borné à [0,5 ; 1,5] ; β = 1 à défaut
  (hypothèse de linéarité). Les chocs sont des faits mesurés de la spécification (TR −46,7 %
  du 01/03/2017 au 26/10/2020, prix −59,8 % depuis fin 2015, 2018 : TR −25,1 %, baisse
  intra-annuelle −33,0 %, −15 % en 8 semaines) : **aucun rejeu des titres sur S1**.
* **Pays** (ST4, ST5, ST10) : choc sur l'exposition économique λ (``reference.economic_exposure`` :
  pays du siège, filiales pour SNTS) ; paramètres du §4.3 et du §11 (``macro.jump_loss``) :
  sévère 21 %, stress 26 %, modéré 8 % ; Mali 2022 : −16,9 % en 3 séances ; Sénégal : −9 %
  relatif en 60 séances, stress −26 % sur BOAS et SNTS.
* **Liquidité** (ST6) : liquidation de chaque ligne en 20 séances à 5 % de la valeur médiane
  échangée (MDV63, séances sans échange = 0), demi-spread × 2 ; coût par aller du §7.2
  (courtage, taxe, BRVM, DC/BR, demi-spread, impact ``κ·√π``), part non liquidable publiée.
* **Coûts** (ST7) : scénario « sévère » du §7.2 sur 12 mois, avec la rotation objectif du §6
  (15 %/mois aller, hypothèse), garde et tenue de compte comprises.
* **Suspension** (ST8) : la plus grosse ligne valorisée −10 % (risque) puis −30 % (stress).
* **Erreur de données** (ST9) : division non ajustée (SNTS, faux −89,3 %) injectée dans une copie
  du panel à ``asof`` ; le contrôle ``|rendement| > 50 %`` de la stratégie doit **bloquer** les
  signaux du titre (perte évitée = 0 si bloqué).

Performance passée ≠ garantie. Aucun gain n'est garanti.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd

from brvm_alpha import reference

__all__ = ["BANNER", "STRESS_DEFAULTS", "portfolio_beta", "stress_tests"]

BANNER = "Performance passée ≠ garantie. Aucun gain n'est garanti."

#: Paramètres par défaut (spécification §4.3, §7.2, §9.3, §11) ; ``params`` les surcharge.
STRESS_DEFAULTS: dict[str, Any] = {
    # ST1-ST3 (faits mesurés, [C-SPEC] ; [R08] ; [R04] §12.4)
    "tr_bear_2017_2020": 0.467,
    "price_bear_from_2015": 0.598,
    "tr_2018": 0.251,
    "composite_2018_intra": 0.330,
    "drop_8_weeks": 0.15,
    # chocs pays (§4.3 ; §11 macro.jump_loss ; [R05] §9)
    "severe_loss": 0.21,
    "severe_stress_loss": 0.26,
    "moderate_loss": 0.08,
    "mali_2022_3_sessions": 0.169,
    "sn_relative_60": 0.09,
    "sn_stress_loss": 0.26,
    "sn_stress_names": ("BOAS", "SNTS"),
    # ST6 liquidité (hypothèse de conception) et coûts du §7.2
    "liquidity_participation": 0.05,
    "liquidity_spread_mult": 2.0,
    "liquidity_sessions": 20,
    "mdv_window": 63,
    "spread_window": 120,
    "half_spread_default": 0.0035,
    "costs_central": {"sgi": 0.008, "tax": 0.18, "brvm": 0.002, "dcbr": 0.001, "impact_coef": 0.016,
                      "custody": 0.0025, "line_fee": 5000.0, "half_spread_mult": 1.0},
    "costs_severe": {"sgi": 0.015, "tax": 0.18, "brvm": 0.002, "dcbr": 0.001, "impact_coef": 0.050,
                     "custody": 0.005, "line_fee": 10000.0, "half_spread_mult": 2.0},
    # ST7 : rotation objectif du §6 (hypothèse) ; participation plafonnée à 10 % (§7.1)
    "turnover_month": 0.15,
    "max_participation": 0.10,
    # ST8 ([R07] §4.7)
    "suspension_haircut": 0.10,
    "suspension_haircut_stress": 0.30,
    # ST9 ([R08] §1)
    "split_error_return": -0.893,
    "split_error_symbol": "SNTS",
    # bêta
    "beta_window_weeks": 104,
    "beta_min_weeks": 52,
    "beta_bounds": (0.5, 1.5),
    #: jamais de lecture de l'échantillon vierge S1 (2017-01-02 → 2022-11-16)
    "history_start": "2022-11-17",
}


def _fcfa(x: float) -> str:
    """Montant en FCFA, espace comme séparateur de milliers (format français)."""
    return f"{float(x):,.0f}".replace(",", "\u202f") + " FCFA"


def _num(x: float, decimals: int = 2) -> str:
    """Nombre au format français (virgule décimale, signe −)."""
    return f"{float(x):.{decimals}f}".replace(".", ",").replace("-", "−")


def _pct(x: float, decimals: int = 2) -> str:
    """Pourcentage au format français : « 14,09 % », « −89,3 % »."""
    return f"{100.0 * float(x):.{decimals}f}".replace(".", ",").replace("-", "−") + " %"


def _d(x: Any) -> str:
    return pd.Timestamp(x).strftime("%d/%m/%Y")


def _params(params: Mapping[str, Any] | None) -> dict[str, Any]:
    p = {k: (dict(v) if isinstance(v, dict) else v) for k, v in STRESS_DEFAULTS.items()}
    for k, v in dict(params or {}).items():
        if k not in p:
            raise KeyError(f"paramètre de stress inconnu : {k!r} (choix : {', '.join(sorted(p))})")
        if isinstance(p[k], dict) and isinstance(v, Mapping):
            p[k] = {**p[k], **dict(v)}
        else:
            p[k] = v
    return p


def _wide(panels: Mapping[str, Any], key: str, asof: pd.Timestamp) -> pd.DataFrame | None:
    obj = panels.get(key) if isinstance(panels, Mapping) else None
    if not isinstance(obj, pd.DataFrame) or not len(obj):
        return None
    df = obj.copy()
    df.index = pd.DatetimeIndex(pd.to_datetime(df.index))
    df.columns = df.columns.astype(str)
    return df.loc[df.index <= asof].sort_index()


def _lambda(symbol: str, zones: tuple[str, ...]) -> float:
    lam = reference.economic_exposure(symbol)
    return float(sum(v for k, v in lam.items() if k in zones))


def portfolio_beta(weights: pd.Series, panels: Mapping[str, Any], asof: Any,
                   params: Mapping[str, Any] | None = None) -> tuple[float, str, int]:
    """β hebdomadaire du panier détenu (poids normalisés) contre le Composite TR, à ``asof``.

    Fenêtre : 104 semaines au plus, 52 au moins, jamais avant ``history_start`` (S1 exclu).
    Renvoie ``(β borné, note, n_semaines)`` ; β = 1 (hypothèse) si l'estimation est impossible.
    """
    p = _params(params)
    t = pd.Timestamp(asof)
    w = pd.Series(weights, dtype=float)
    w = w[w > 0]
    tr = _wide(panels, "tr_index", t)
    mk = panels.get("market_tr") if isinstance(panels, Mapping) else None
    if tr is None or mk is None or not len(w):
        return 1.0, "β = 1 supposé (indices TR absents)", 0
    mk = pd.Series(mk, dtype=float)
    mk.index = pd.DatetimeIndex(pd.to_datetime(mk.index))
    start = max(pd.Timestamp(p["history_start"]), t - pd.Timedelta(weeks=int(p["beta_window_weeks"]) + 1))
    cols = [s for s in w.index if s in tr.columns]
    if not cols:
        return 1.0, "β = 1 supposé (titres absents des indices TR)", 0
    sub = tr.loc[(tr.index >= start) & (tr.index <= t), cols]
    m = mk.loc[(mk.index >= start) & (mk.index <= t)]
    wk = sub.resample("W-FRI").last().pct_change(fill_method=None)
    wm = m.resample("W-FRI").last().pct_change(fill_method=None)
    ww = w.reindex(cols) / float(w.reindex(cols).sum())
    rp = (wk.fillna(0.0) * ww).sum(axis=1).where(wk.notna().any(axis=1))
    both = pd.concat({"p": rp, "m": wm}, axis=1).dropna()
    both = both.iloc[-int(p["beta_window_weeks"]):]
    n = len(both)
    if n < int(p["beta_min_weeks"]) or float(both["m"].var(ddof=1)) <= 0:
        return 1.0, f"β = 1 supposé ({n} semaines < {int(p['beta_min_weeks'])} depuis le {_d(start)})", n
    beta = float(both["p"].cov(both["m"]) / both["m"].var(ddof=1))
    lo, hi = p["beta_bounds"]
    b = float(np.clip(beta, lo, hi))
    return b, (f"β {n} semaines (hebdomadaire) {_num(beta)}, borné à {_num(b)}, jusqu'au {_d(t)}, "
               f"depuis le {_d(both.index[0])} (aucune donnée de S1)"), n


def _half_spreads(panels: Mapping[str, Any], syms: list[str], asof: pd.Timestamp, p: Mapping[str, Any],
                  price: pd.Series) -> pd.Series:
    """½ × spread relatif médian de clôture sur 120 séances (deux côtés), plancher pas/(2·cours)."""
    out = pd.Series(float(p["half_spread_default"]), index=syms, dtype=float)
    bid, ask = _wide(panels, "bid", asof), _wide(panels, "ask", asof)
    if bid is not None and ask is not None:
        b = bid.reindex(columns=syms).iloc[-int(p["spread_window"]):]
        a = ask.reindex(index=b.index, columns=syms)
        mid = 0.5 * (a + b)
        rel = ((a - b) / mid).where((a > 0) & (b > 0) & (a >= b))
        med = 0.5 * rel.median()
        out = med.where(med.notna(), out)
    tick = np.where(price < 100, 1.0, 5.0)
    floor = pd.Series(np.where(price > 0, tick / (2.0 * price), 0.0), index=syms)
    return np.maximum(out, floor.reindex(syms).fillna(0.0))


def _mdv(panels: Mapping[str, Any], syms: list[str], asof: pd.Timestamp, window: int) -> pd.Series:
    val = _wide(panels, "value", asof)
    if val is None:
        return pd.Series(np.nan, index=syms, dtype=float)
    return val.reindex(columns=syms).iloc[-int(window):].fillna(0.0).median()


def _one_way(c: Mapping[str, Any], hs: pd.Series, part: pd.Series) -> pd.Series:
    """Coût par aller du §7.2 : courtage × (1 + taxe) + BRVM + DC/BR + demi-spread + κ·√π."""
    prop = float(c["sgi"]) * (1.0 + float(c["tax"])) + float(c["brvm"]) + float(c["dcbr"])
    return prop + float(c["half_spread_mult"]) * hs + float(c["impact_coef"]) * np.sqrt(part.clip(lower=0.0))


def _split_guard(panels: Mapping[str, Any], asof: pd.Timestamp, symbol: str, ret: float) -> tuple[bool | None, str]:
    """Injecte une division non ajustée dans une copie du panel et lit le contrôle de la stratégie."""
    try:
        from brvm_alpha.backtest import engine
        from brvm_alpha.strategy import BrvmAlpha
    except Exception as exc:  # noqa: BLE001 - stratégie indisponible : contrôle non vérifiable
        return None, f"stratégie indisponible ({exc.__class__.__name__})"
    view = engine.truncate_asof(dict(panels), asof)
    mod: dict[str, Any] = dict(view)
    hit = False
    for key in ("tr_index", "close", "close_adj", "close_raw"):
        df = mod.get(key)
        if isinstance(df, pd.DataFrame) and symbol in df.columns and len(df):
            df = df.copy()
            df.iloc[-1, df.columns.get_loc(symbol)] = df[symbol].iloc[-1] * (1.0 + ret)
            mod[key] = df
            hit = True
    if not hit:
        return None, f"{symbol} absent du panel"
    try:
        rf = BrvmAlpha(notes=None, country_events=False).risk_flags(asof, mod, notes=None)
    except Exception as exc:  # noqa: BLE001
        return None, f"contrôle non évaluable ({exc.__class__.__name__} : {exc})"
    if "data_guard" not in rf.columns or symbol not in rf.index:
        return None, "colonne data_guard absente"
    return bool(rf.loc[symbol, "data_guard"]), "BrvmAlpha.risk_flags : data_guard (|rendement| > 50 %)"


def stress_tests(weights: pd.Series | Mapping[str, float], panels: Mapping[str, Any], asof: Any, capital: float,
                 params: Mapping[str, Any] | None = None) -> pd.DataFrame:
    """Scénarios ST1-ST10 du §9.3 appliqués aux poids cibles ``weights`` (fractions de la VL).

    Parameters
    ----------
    weights
        Poids par symbole (fraction de la valeur du portefeuille ; le reste est en liquidités).
    panels
        Panels larges du moteur (``tr_index``, ``market_tr``, ``value``, ``bid``, ``ask``,
        ``close_raw`` ou ``close``) ; seules les données datées ``≤ asof`` sont lues, jamais
        celles de l'échantillon vierge S1 pour le bêta.
    asof
        Date du portefeuille (par ex. décision du 20/11/2026).
    capital
        Valeur du portefeuille K en FCFA.
    params
        Surcharges de :data:`STRESS_DEFAULTS` (clé inconnue refusée).

    Returns
    -------
    DataFrame
        Colonnes ``code`` (ST1…ST10), ``variante``, ``scenario``, ``perte_fcfa`` (variation de
        valeur, **négative = perte**, arrondie au franc), ``perte_pct`` (fraction de ``capital``),
        ``hypothese``, ``base`` (source), ``nature`` (``estimation`` / ``contrôle``).
        ``attrs`` : ``beta``, ``beta_note``, ``investi_fcfa``, ``bandeau``. Ce sont des
        estimations sous hypothèses, pas des prévisions.
    """
    p = _params(params)
    t = pd.Timestamp(asof)
    K = float(capital)
    if not K > 0:
        raise ValueError("capital doit être > 0")
    w = pd.Series(weights, dtype=float).fillna(0.0)
    w.index = w.index.astype(str)
    w = w[w > 1e-12]
    syms = list(w.index)
    val = w * K
    inv = float(val.sum())
    rows: list[dict[str, Any]] = []

    def add(code: str, variante: str, scenario: str, loss: float, hyp: str, base: str,
            nature: str = "estimation") -> None:
        loss_f = 0.0 if not math.isfinite(loss) else float(loss)
        rows.append({"code": code, "variante": variante, "scenario": scenario, "perte_fcfa": int(round(loss_f)),
                     "perte_pct": loss_f / K, "hypothese": hyp, "base": base, "nature": nature})

    beta, b_note, _ = portfolio_beta(w, panels, t, p)

    # ST1-ST3 : marché (β × choc × valeur investie)
    add("ST1", "TR", "marché baissier long : chemin du TR du 01/03/2017 au 26/10/2020 (−46,7 %)",
        -beta * float(p["tr_bear_2017_2020"]) * inv, b_note, "[C-SPEC] §1.1 (fait mesuré)")
    add("ST1", "prix", "marché baissier long : Composite prix depuis fin 2015 (−59,8 % en 58 mois)",
        -beta * float(p["price_bear_from_2015"]) * inv, b_note + " ; dividendes non comptés", "[R08] §4.3")
    add("ST2", "TR", "pire année (2018 : TR reconstruit −25,1 %)", -beta * float(p["tr_2018"]) * inv, b_note,
        "[C-SPEC] ; [R08]")
    add("ST2", "intra-annuel", "pire année (2018 : baisse intra-annuelle maximale du Composite −33,0 %)",
        -beta * float(p["composite_2018_intra"]) * inv, b_note, "[R08]")
    add("ST3", "", "correction rapide (−15 % en 8 semaines ; pire 8 semaines observé −14,3 %)",
        -beta * float(p["drop_8_weeks"]) * inv, b_note, "[R04] §12.4")

    # ST4 : choc pays sévère AES (exposition λ : siège, filiales pour SNTS)
    aes = tuple(reference.AES_COUNTRIES)
    v_aes = float(sum(val[s] * _lambda(s, aes) for s in syms))
    lam_note = (f"exposition λ AES {_pct(v_aes / K)} du capital (siège ; filiales pour SNTS : "
                f"ML {_num(reference.economic_exposure('SNTS').get('ML', 0.0), 3)})")
    add("ST4", "sévère 21 %", "choc pays sévère AES (sanctions, gel BCEAO) : −21 % sur BF, ML, NE",
        -float(p["severe_loss"]) * v_aes, lam_note, "§4.3 ; §11 macro.jump_loss ; [R05] §12")
    add("ST4", "stress 26 % (Niger 2023)", "choc pays sévère AES : −26 % en 9 séances, dont 3 au plancher sans "
        "vendeur servi (rejeu Niger 2023)", -float(p["severe_stress_loss"]) * v_aes,
        lam_note + " ; aucune vente possible avant la 4ᵉ séance", "[R05] §9")
    v_ml = float(sum(val[s] * _lambda(s, ("ML",)) for s in syms))
    add("ST4", "Mali 2022", "variante Mali 2022 : plancher dès t+1, −16,9 % en 3 séances sur ML",
        -float(p["mali_2022_3_sessions"]) * v_ml, f"exposition λ ML {_pct(v_ml / K)} du capital", "[R05] §9")
    add("ST4", "modéré 8 %", "coup d'État sans sanctions UEMOA : −8 % sur BF, ML, NE",
        -float(p["moderate_loss"]) * v_aes, lam_note, "§4.3 ; [R05] §12")

    # ST5 : stress souverain Sénégal
    sn = [s for s in syms if reference.country_of(s) == "SN"]
    v_sn = float(val[sn].sum()) if sn else 0.0
    add("ST5", "relatif −9 %", "stress souverain Sénégal : −9 % relatif en 60 séances (audit 2024) sur les titres "
        "sénégalais", -float(p["sn_relative_60"]) * v_sn,
        f"titres SN détenus : {', '.join(sn) or 'aucun'} ({_pct(v_sn / K)}) ; marché supposé stable", "[R05] §9")
    names = [s for s in p["sn_stress_names"] if s in val.index]
    v_st = float(val[names].sum()) if names else 0.0
    add("ST5", "stress −26 %", "stress souverain Sénégal : −26 % sur BOAS et SNTS",
        -float(p["sn_stress_loss"]) * v_st, f"BOAS + SNTS : {_pct(v_st / K)} du capital (hypothèse de stress)",
        "[R05] §9, §12")

    # ST6 : liquidité (participation 5 %, demi-spread × 2, 20 séances)
    close = _wide(panels, "close_raw", t)
    if close is None:
        close = _wide(panels, "close", t)
    price = (close.reindex(columns=syms).ffill().iloc[-1] if close is not None and len(close)
             else pd.Series(np.nan, index=syms)).astype(float)
    hs = _half_spreads(panels, syms, t, p, price.fillna(0.0))
    mdv = _mdv(panels, syms, t, int(p["mdv_window"]))
    part = float(p["liquidity_participation"])
    n_sess = int(p["liquidity_sessions"])
    per_day = part * mdv
    sellable = np.minimum(val, (n_sess * per_day).fillna(0.0))
    unsold = (val - sellable).clip(lower=0.0)
    c_liq = dict(p["costs_central"], half_spread_mult=float(p["liquidity_spread_mult"]))
    liq_rate = _one_way(c_liq, hs, pd.Series(part, index=syms))
    liq_cost = float((sellable * liq_rate).sum())
    normal_rate = _one_way(p["costs_central"], hs, pd.Series(float(p["max_participation"]), index=syms))
    normal_cost = float((val * normal_rate).sum())
    with np.errstate(divide="ignore", invalid="ignore"):
        days = (val / per_day).replace([np.inf, -np.inf], np.nan)
    worst = days.idxmax() if days.notna().any() else None
    add("ST6", "", "liquidité : participation divisée par 2 (5 %) et demi-spread × 2 pendant 20 séances "
        "(liquidation complète)", -liq_cost,
        f"coût de sortie {_pct(liq_cost / max(inv, 1.0))} de la valeur investie (normal, 10 % de participation : "
        f"{_pct(normal_cost / max(inv, 1.0))}) ; non liquidable en {n_sess} séances : {_fcfa(float(unsold.sum()))}"
        + (f" ; ligne la plus lente : {worst} ({_num(float(days[worst]), 1)} séances à 5 %)" if worst is not None else ""),
        "hypothèse de conception ; §7.2")

    # ST7 : coûts sévères du §7.2 sur 12 mois (rotation objectif 15 %/mois aller)
    to = float(p["turnover_month"])
    with np.errstate(divide="ignore", invalid="ignore"):
        pi = ((to * val) / mdv).replace([np.inf, -np.inf], np.nan).fillna(float(p["max_participation"]))
    pi = pi.clip(upper=float(p["max_participation"]))
    traded = 12.0 * 2.0 * to * val

    def annual(c: Mapping[str, Any]) -> float:
        return float((traded * _one_way(c, hs, pi)).sum() + float(c["custody"]) * inv
                     + float(c["line_fee"]) * len(syms))

    sev, cen = annual(p["costs_severe"]), annual(p["costs_central"])
    add("ST7", "", "coûts : scénario sévère du §7.2 sur 12 mois (courtage 1,5 %, demi-spread × 2, κ = 0,05, "
        "garde 0,5 %, 10 000 FCFA par ligne)", -sev,
        f"rotation {_pct(to, 0)}/mois aller (objectif du §6, hypothèse) ; coûts centraux sur 12 mois : {_fcfa(cen)} ; "
        f"surcoût du scénario sévère : {_fcfa(sev - cen)}", "§7.2")

    # ST8 : suspension de la plus grosse ligne
    if len(val):
        top = str(val.idxmax())
        add("ST8", "−10 %", f"suspension de la plus grosse ligne ({top}, {_pct(w[top])}) pendant 60 séances, valorisée "
            "−10 %", -float(p["suspension_haircut"]) * float(val[top]), "valorisation de risque (§7.1.7)", "[R07] §4.7")
        add("ST8", "−30 %", f"suspension de la plus grosse ligne ({top}) : valorisée −30 % (stress)",
            -float(p["suspension_haircut_stress"]) * float(val[top]), "hypothèse de stress", "[R07] §4.7")

    # ST9 : erreur de données (division non ajustée) : le contrôle doit bloquer
    sym9 = str(p["split_error_symbol"])
    r9 = float(p["split_error_return"])
    blocked, how = _split_guard(panels, t, sym9, r9)
    apparent = r9 * float(val.get(sym9, 0.0))
    if blocked:
        hyp9 = (f"contrôle BLOQUANT vérifié ({how}) : signaux de {sym9} bloqués ; perte apparente évitée "
                f"{_fcfa(-apparent)}")
        loss9 = 0.0
    elif blocked is False:
        hyp9 = f"ÉCHEC du contrôle ({how}) : la fausse baisse passerait dans les signaux"
        loss9 = apparent
    else:
        hyp9 = f"contrôle non vérifiable : {how}"
        loss9 = 0.0
    add("ST9", "", f"erreur de données : division non ajustée sur {sym9} (faux {_pct(r9, 1)})", loss9, hyp9, "[R08] §1",
        nature="contrôle")

    # ST10 : rupture de parité ou sortie de l'UEMOA
    zones10 = aes + ("GN", "SL", "GW")
    v10 = float(sum(val[s] * (_lambda(s, zones10) if s == "SNTS" else _lambda(s, aes)) for s in syms))
    for lab, key in (("sévère 21 %", "severe_loss"), ("stress 26 %", "severe_stress_loss")):
        add("ST10", lab, "rupture de parité ou sortie de l'UEMOA : règle « sévère » sur les titres AES et les "
            "filiales de SNTS", -float(p[key]) * v10,
            f"exposition {_pct(v10 / K)} du capital (AES ; SNTS : ML, GN, SL, GW) ; perte de change NON chiffrée "
            "(aucune source)", "[R05] §7")

    out = pd.DataFrame(rows, columns=["code", "variante", "scenario", "perte_fcfa", "perte_pct", "hypothese", "base",
                                      "nature"])
    out.attrs.update(beta=beta, beta_note=b_note, investi_fcfa=inv, capital=K, asof=t, bandeau=BANNER,
                     controle_split_bloquant=blocked)
    return out
