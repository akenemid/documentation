"""Jeux d'essai du paquet ``brvm_alpha.suivi`` (tests seulement).

* Panels de synthèse, toujours datés après l'échantillon S1 (S0 : 2023-2024 ; ou dates de suivi fabriquées) : aucun test
  ne lit les données réelles de l'installation ni ne fige un exemple tiré d'une date réelle choisie après coup.
* Registre des essais : **copie** de ``reports/trials.parquet`` dans un dossier temporaire (le fichier du dépôt est lu,
  jamais écrit).
* Dépôt de développement factice : un dossier temporaire avec un dossier ``.git`` vide.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

from brvm_alpha import reference

RACINE = Path(__file__).resolve().parents[1]
REGISTRE_DU_DEPOT = RACINE / "reports" / "trials.parquet"
S0_DEBUT = "2022-11-17"
SYMS = [s for s in sorted(reference.SECTOR_2025) if s not in reference.DELISTED_SYMBOLS][:32]


def sha(p: Path) -> str | None:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


def depot(tmp: Path) -> Path:
    """Dépôt de développement factice (un dossier ``.git``)."""
    d = tmp / "depot"
    (d / ".git").mkdir(parents=True, exist_ok=True)
    return d


def registre(tmp: Path) -> Path:
    """Copie du registre des essais du dépôt (98 lignes) dans le dossier temporaire."""
    p = tmp / "trials.parquet"
    shutil.copyfile(REGISTRE_DU_DEPOT, p)
    return p


def reponses_proposees(articles: list[dict], **choix: str) -> list[dict]:
    """Répond à chaque article par la proposition du cahier (ou par ``choix[id]``)."""
    for a in articles:
        cle = a["id"].replace("-", "_")
        if cle in choix:
            a["reponse"] = choix[cle]
        elif a.get("reponse_requise"):
            a["reponse"] = a["proposition"] if a["proposition"] in (a.get("choix") or []) else a["choix"][0]
    return articles


def panel_simple(dates, prix: dict, *, volume: float = 10_000.0, raw: dict | None = None, indice=None,
                 dividendes: list[dict] | None = None, sessions: pd.DataFrame | None = None,
                 actions: list[dict] | None = None) -> dict:
    """Panel minimal : clôtures (``close`` ; ``close_raw`` si ``raw``), volumes et valeurs (cours moyen = clôture),
    Composite TR (plat par défaut), table des dividendes et des opérations sur titres."""
    idx = pd.DatetimeIndex(pd.to_datetime(dates), name="date")
    close = pd.DataFrame({k: list(map(float, v)) for k, v in prix.items()}, index=idx)
    vol = pd.DataFrame(float(volume), index=idx, columns=close.columns)
    p = {"close": close, "volume": vol, "value": close * vol,
         "market_tr": pd.Series(100.0 if indice is None else indice, index=idx, name="TR")}
    if raw is not None:
        p["close_raw"] = pd.DataFrame({k: list(map(float, v)) for k, v in raw.items()}, index=idx)
        p["value"] = p["close_raw"] * vol
    if dividendes:
        p["dividends_table"] = pd.DataFrame(dividendes)
    if sessions is not None:
        p["sessions"] = sessions
    if actions:
        p["corporate_actions"] = pd.DataFrame(actions)
    return p


def panel_moteur(n_days: int = 430, seed: int = 0, symbols: list[str] | None = None) -> dict:
    """Panel synthétique au format de ``build_panels`` (S0 : à partir du 02/01/2023), assez riche pour ``BrvmAlpha``
    (même construction que les tests de la stratégie)."""
    rng = np.random.default_rng(seed)
    syms = list(symbols or SYMS)
    n = len(syms)
    dates = pd.bdate_range("2023-01-02", periods=n_days)
    mu = rng.normal(0.0003, 0.0004, n)
    sig = rng.uniform(0.006, 0.02, n)
    r = rng.normal(mu, sig, size=(n_days, n))
    p_trade = rng.uniform(0.75, 1.0, n)
    p_trade[:2] = 0.30
    traded = rng.random((n_days, n)) < p_trade
    r = np.where(traded, r, 0.0)
    close = 1000.0 * rng.uniform(0.5, 20.0, n) * np.cumprod(1.0 + r, axis=0)
    tick = np.where(close < 100, 1.0, 5.0)
    close = np.maximum(np.round(close / tick) * tick, 1.0)
    vol = np.where(traded, rng.integers(200, 5000, size=(n_days, n)), 0).astype(float)
    vol[:, 2] = np.where(traded[:, 2], 3.0, 0.0)
    value = vol * close
    status = np.where(traded, "traded", "not_traded").astype(object)
    status[300:320, 3] = "suspended"
    vol[300:320, 3] = 0.0
    value[300:320, 3] = 0.0
    idx = pd.DatetimeIndex(dates, name="date")
    cols = pd.Index(syms, name="symbol")
    C = pd.DataFrame(close, idx, cols)
    per = pd.DataFrame(np.tile(rng.uniform(4.0, 30.0, n), (n_days, 1)), idx, cols)
    per.iloc[:, 5] = -3.0
    yld = rng.uniform(0.02, 0.09, n)
    div_amt = yld * close[0]
    pay_day = [dates[min(60 + 7 * j % 120, n_days - 1)] for j in range(n)]
    last_div_net = pd.DataFrame(np.tile(div_amt, (n_days, 1)), idx, cols)
    last_div_date = pd.DataFrame({s: pd.Series(pd.Timestamp("2022-06-15"), index=idx) for s in syms})
    for j, s in enumerate(syms):
        last_div_date.loc[last_div_date.index >= pay_day[j], s] = pay_day[j]
    net_yield = pd.DataFrame(100.0 * div_amt[None, :] / close, idx, cols)
    tr = C.pct_change().fillna(0.0)
    div_rows = []
    for j, s in enumerate(syms):
        ex = dates[max(dates.get_loc(pay_day[j]) - 2, 1)]
        tr.loc[ex, s] += div_amt[j] / C[s].shift(1).loc[ex]
        div_rows.append({"symbol": s, "ex_date": ex, "amount": float(div_amt[j]), "payment_date": pay_day[j],
                         "date": dates[dates.get_loc(ex) - 1]})
    tr_index = 100.0 * (1.0 + tr).cumprod()
    shares = pd.DataFrame(np.tile(rng.uniform(1e6, 5e7, n), (n_days, 1)), idx, cols)
    mcap = (C * shares).sum(axis=1)
    market = pd.DataFrame({"date": idx, "avg_per": 15.0, "risk_premium": 100.0 / 15.0 - 5.75,
                           "market_cap": mcap.to_numpy()})
    mret = tr_index.pct_change().mean(axis=1).fillna(0.0)
    market_tr = (100.0 * (1.0 + mret).cumprod()).rename("BRVM_COMPOSITE_TR")
    flags = pd.DataFrame("", index=idx, columns=cols, dtype=object)
    half = 0.004
    divt = pd.DataFrame(div_rows)
    dividend_net = pd.DataFrame(0.0, idx, cols)
    for rec in div_rows:
        dividend_net.loc[rec["ex_date"], rec["symbol"]] = rec["amount"]
    return {
        "close": C.copy(), "adj_factor": pd.DataFrame(1.0, idx, cols), "close_raw": C, "close_adj": C.copy(),
        "tr_index": tr_index, "volume": pd.DataFrame(vol, idx, cols), "value": pd.DataFrame(value, idx, cols),
        "status": pd.DataFrame(status, idx, cols), "per": per, "net_yield_pct": net_yield,
        "last_div_net": last_div_net, "last_div_date": last_div_date, "ref_price": C.shift(1),
        "flags": flags, "bid": C * (1.0 - half), "ask": C * (1.0 + half), "shares": shares, "market": market,
        "market_tr": market_tr, "dividends_table": divt, "dividend_net": dividend_net,
    }
