"""Jeux d'essai du module « Rendement net et pertes » (tests seulement).

* Ordres de bataille réels du 20/11/2026, **figés** dans ``tests/donnees_rendement/`` (produits par
  ``python -m brvm_alpha recommend --capital K --format json --sortie …`` au commit d256e26, puis réduits aux clés
  que le module lit) : les tests ne lisent jamais les données réelles de l'installation.
* Extraits du panel du 20/11/2026 figés : indices TR quotidiens des 20 lignes et du Composite TR (fenêtre de l'ordre),
  cours ajustés de 2018 des titres du test S1 publié, carnet de clôture, dividendes payés en 2026.
* Panel de synthèse (dates de S0 seulement) pour les tests unitaires.

Aucune écriture hors des dossiers temporaires des tests.
"""

from __future__ import annotations

import functools
import gzip
import json
from pathlib import Path

import numpy as np
import pandas as pd

RACINE = Path(__file__).resolve().parents[1]
DONNEES = Path(__file__).resolve().parent / "donnees_rendement"
#: Résultats S1 publiés, suivis par git (lecture seule permise, jamais d'écriture).
VALIDATION_S1 = RACINE / "reports" / "validation_S1"
AUJOURD_HUI = "2026-11-22"


@functools.lru_cache(maxsize=None)
def _json(nom: str) -> str:
    p = DONNEES / nom
    if nom.endswith(".gz"):
        return gzip.decompress(p.read_bytes()).decode("utf-8")
    return p.read_text(encoding="utf-8")


def ordre(nom: str) -> dict:
    """Ordre figé : ``10M``, ``1M``, ``50M``, ``1400000``, ``3000000``, ``6300000``, ``detenu_624840``, ``partiel``."""
    return json.loads(_json(f"ordre_20261120_{nom}.json"))


def resume_poches() -> dict:
    return json.loads(_json("ordres_20261120_poches_resume.json"))["ordres"]


@functools.lru_cache(maxsize=None)
def _tr() -> tuple[pd.DataFrame, pd.Series]:
    d = json.loads(_json("tr_20261120.json.gz"))
    idx = pd.DatetimeIndex(pd.to_datetime(d["dates"]), name="date")
    tr = pd.DataFrame({s: pd.Series(v, index=idx, dtype=float) for s, v in d["tr_index"].items()})
    tr.columns.name = "symbol"
    mtr = pd.Series(d["market_tr"], index=idx, dtype=float, name="TR").dropna()
    return tr, mtr


def panels_tr() -> dict:
    """Panels réduits (``tr_index``, ``market_tr``) du 20/11/2026 pour les lectures du risque."""
    tr, mtr = _tr()
    return {"tr_index": tr.copy(), "market_tr": mtr.copy()}


@functools.lru_cache(maxsize=None)
def _s1() -> tuple[pd.DataFrame, pd.DataFrame]:
    d = json.loads(_json("s1_2018_cours.json.gz"))
    idx = pd.DatetimeIndex(pd.to_datetime(d["dates"]), name="date")
    ca = pd.DataFrame({s: pd.Series(v, index=idx, dtype=float) for s, v in d["close_adj"].items()})
    ti = pd.DataFrame({s: pd.Series(v, index=idx, dtype=float) for s, v in d["tr_index"].items()})
    return ca, ti


def panels_s1_2018() -> dict:
    """Cours ajustés et indices TR de 2018 des titres détenus par la référence dans le test S1 publié."""
    ca, ti = _s1()
    return {"close_adj": ca.copy(), "tr_index": ti.copy()}


def carnet() -> dict:
    return json.loads(_json("carnet_cloture_20261120.json"))["carnet"]


def dividendes_2026() -> pd.DataFrame:
    d = pd.DataFrame(json.loads(_json("dividendes_2026.json"))["lignes"])
    for c in ("ex_date", "payment_date"):
        d[c] = pd.to_datetime(d[c])
    return d


def panels_reels() -> dict:
    """Tous les extraits figés réunis (comme les panels de ``recommend``)."""
    p = panels_tr()
    s = panels_s1_2018()
    # Une seule table d'indices TR, comme dans les panels réels : les 20 lignes sur la fenêtre de l'ordre, plus les
    # titres du test S1 publié en 2017-2018 (mêmes valeurs là où les deux extraits se recouvrent).
    p["tr_index"] = p["tr_index"].combine_first(s["tr_index"])
    p["close_adj"] = s["close_adj"]
    p["dividends_table"] = dividendes_2026()
    return p


# ---------------------------------------------------------------------------
# Panel de synthèse (dates de S0 seulement : aucune date ≤ 16/11/2022)
# ---------------------------------------------------------------------------


def panel_synthese(n_jours: int = 430, graine: int = 5, n_titres: int = 24) -> dict:
    """Panel au format de ``strategy.build_panels`` (copie du panel de ``tests/test_recommend.py``), dates de S0."""
    from brvm_alpha import reference

    rng = np.random.default_rng(graine)
    syms = [s for s in sorted(reference.SECTOR_2025) if s not in reference.DELISTED_SYMBOLS][:n_titres]
    n = len(syms)
    dates = pd.bdate_range("2023-01-02", periods=n_jours)
    r = rng.normal(rng.normal(0.0003, 0.0004, n), rng.uniform(0.006, 0.02, n), size=(n_jours, n))
    traded = rng.random((n_jours, n)) < rng.uniform(0.8, 1.0, n)
    r = np.where(traded, r, 0.0)
    close = 1000.0 * rng.uniform(0.5, 20.0, n) * np.cumprod(1.0 + r, axis=0)
    tick = np.where(close < 100, 1.0, 5.0)
    close = np.maximum(np.round(close / tick) * tick, 1.0)
    vol = np.where(traded, rng.integers(500, 6000, size=(n_jours, n)), 0).astype(float)
    idx = pd.DatetimeIndex(dates, name="date")
    cols = pd.Index(syms, name="symbol")
    C = pd.DataFrame(close, idx, cols)
    status = pd.DataFrame(np.where(traded, "traded", "not_traded").astype(object), idx, cols)
    per = pd.DataFrame(np.tile(rng.uniform(4.0, 30.0, n), (n_jours, 1)), idx, cols)
    div_amt = rng.uniform(0.02, 0.09, n) * close[0]
    pay = [dates[min(60 + 7 * j % 120, n_jours - 1)] for j in range(n)]
    last_div_net = pd.DataFrame(np.tile(div_amt, (n_jours, 1)), idx, cols)
    last_div_date = pd.DataFrame({s: pd.Series(pd.Timestamp("2022-12-15"), index=idx) for s in syms})
    tr = C.pct_change().fillna(0.0)
    rows = []
    for j, s in enumerate(syms):
        last_div_date.loc[last_div_date.index >= pay[j], s] = pay[j]
        ex = dates[dates.get_loc(pay[j]) - 2]
        tr.loc[ex, s] += div_amt[j] / C[s].shift(1).loc[ex]
        rows.append({"symbol": s, "ex_date": ex, "amount": float(div_amt[j]), "payment_date": pay[j],
                     "date": dates[dates.get_loc(ex) - 1]})
    tr_index = 100.0 * (1.0 + tr).cumprod()
    shares = pd.DataFrame(np.tile(rng.uniform(1e6, 5e7, n), (n_jours, 1)), idx, cols)
    market = pd.DataFrame({"date": idx, "avg_per": 15.0, "risk_premium": 2.0,
                           "market_cap": (C * shares).sum(axis=1).to_numpy()})
    market_tr = (100.0 * (1.0 + tr_index.pct_change().mean(axis=1).fillna(0.0)).cumprod()).rename("TR")
    dividend_net = pd.DataFrame(0.0, idx, cols)
    for rec in rows:
        dividend_net.loc[rec["ex_date"], rec["symbol"]] = rec["amount"]
    return {"close": C.copy(), "adj_factor": pd.DataFrame(1.0, idx, cols), "close_raw": C, "close_adj": C.copy(),
            "tr_index": tr_index, "volume": pd.DataFrame(vol, idx, cols), "value": pd.DataFrame(vol, idx, cols) * C,
            "status": status, "per": per, "net_yield_pct": pd.DataFrame(100.0 * div_amt / close, idx, cols),
            "last_div_net": last_div_net, "last_div_date": last_div_date, "ref_price": C.shift(1),
            "flags": pd.DataFrame("", index=idx, columns=cols, dtype=object), "bid": C * 0.996, "ask": C * 1.004,
            "shares": shares, "market": market, "market_tr": market_tr, "dividends_table": pd.DataFrame(rows),
            "dividend_net": dividend_net}


def registre_vide(chemin: Path) -> Path:
    """Registre des essais sans S1 exécuté (copie de ``tests/test_recommend.py``), dans un dossier temporaire."""
    from brvm_alpha.backtest.walkforward import REGISTRY_COLUMNS

    pd.DataFrame(columns=list(REGISTRY_COLUMNS)).to_parquet(chemin)
    return chemin


def ordre_synthese(panels: dict, capital: float, tmp: Path, **kw) -> object:
    """Ordre de bataille complet sur le panel de synthèse (``recommend`` existant, sans notes, sans indices)."""
    import warnings

    from brvm_alpha.portfolio import recommend as R

    reg = tmp / "trials.parquet"
    if not reg.exists():
        registre_vide(reg)
    t = panels["close"].index[-1]
    args = dict(panels=panels, validation_dir=tmp / "absent", registry_path=reg, notes_store=False, n_boot=300, seed=0,
                index_evaluation=False, comparison=False, explanations=True)
    args.update(kw)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return R.recommend(t, capital, **args)
