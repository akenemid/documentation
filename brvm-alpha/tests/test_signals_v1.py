"""Tests des signaux de la stratégie v1 (spécification §3.1-§3.4, §5.2 S2, §11, §12.3 n° 5).

Trois familles de tests :

1. **Valeurs exactes** sur des données synthétiques (calculs refaits à la main) :
   momentum en séances, faible volatilité, EP avec surcharges de BPA, DY (garde-fou de
   15 mois, plafond, exclusion des dividendes exceptionnels, absences annoncées,
   divisions), qualité, modulateurs du momentum, z de rang gaussien, score composite,
   malus S2.
2. **Absence d'anticipation** : modifier les données à partir de ``t0`` ne change
   aucune valeur avant ``t0``.
3. **Panel réel** : valeurs ponctuelles du §12.3 n° 5 (permises à toute date) et
   contrôles de forme ; tout ce qui ressemble à une performance (spread du momentum,
   scores composites) est restreint à **S0** (2022-11-17 → 2026-11-20). Aucun
   calcul de performance ni d'IC n'est fait sur S1 (échantillon vierge).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy.stats import norm

from brvm_alpha.quant import features as ft
from brvm_alpha.quant import scoring as sc

ROOT = Path(__file__).resolve().parents[1]
PANEL_DIR = ROOT / "data" / "panel"
YAML = ROOT / "configs" / "strategy_v1.yaml"
S0_START = pd.Timestamp("2022-11-17")
S0_END = pd.Timestamp("2026-11-20")


# ---------------------------------------------------------------------------
# Utilitaires synthétiques
# ---------------------------------------------------------------------------


def _frame(values: np.ndarray, dates: pd.DatetimeIndex, cols: list[str]) -> pd.DataFrame:
    return pd.DataFrame(values, index=dates, columns=cols)


def _geometric(T: int = 300, g: float = 1.001) -> dict[str, pd.DataFrame]:
    dates = pd.bdate_range("2030-01-01", periods=T)
    p = 100.0 * g ** np.arange(T)
    df = pd.DataFrame({"A": p, "B": 3 * p}, index=dates)
    return {"tr_index": df, "close_adj": df.copy()}


def synth_panels(T: int = 640, N: int = 12, seed: int = 1) -> dict[str, pd.DataFrame]:
    """Panel « type BRVM » (échanges rares, dividendes annuels, BOC manquants, suspension)."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2030-01-02", periods=T)
    syms = [f"S{i:02d}" for i in range(N)]
    traded = rng.random((T, N)) < rng.uniform(0.4, 0.95, N)[None, :]
    traded[0] = True
    r = np.where(traded, np.clip(rng.normal(0.0005, 0.018, (T, N)), -0.075, 0.075), 0.0)
    close = 1000.0 * np.cumprod(1.0 + r, axis=0)
    amount = np.full((T, N), np.nan)
    pay = np.full((T, N), np.datetime64("NaT", "ns"), dtype="datetime64[ns]")
    for j in range(0, N, 2):
        for year in sorted({d.year for d in dates}):
            k = np.flatnonzero(dates >= pd.Timestamp(year=year, month=6, day=10))
            if k.size:
                amount[k[0]:, j] = 20.0 + 3 * j + year % 7
                pay[k[0]:, j] = np.datetime64(pd.Timestamp(year=year, month=6, day=12), "ns")
    status = np.where(traded, "traded", "not_traded").astype(object)
    status[200:230, 3] = "suspended"
    volume = np.where(traded, rng.integers(10, 3000, (T, N)), 0).astype(float)
    volume[200:230, 3] = 0.0
    close[:120, N - 1] = np.nan  # introduction en cours de période
    status[:120, N - 1] = None
    missing = np.zeros((T, N))
    missing[rng.choice(np.arange(1, T), 6, replace=False)] = 1.0  # BOC manquants (toute la cote)
    per = np.where(rng.random((T, N)) < 0.08, np.nan, rng.uniform(-3, 60, (T, N)))
    net_yield = np.where(np.isnan(amount), np.nan, amount / close * 100)
    f = lambda a: _frame(a, dates, syms)
    return {
        "close": f(close),
        "close_adj": f(close),
        "tr_index": f(close),
        "volume": f(volume),
        "value": f(volume * np.nan_to_num(close)),
        "status": f(status),
        "per": f(per),
        "net_yield_pct": f(net_yield),
        "last_div_net": f(amount),
        "last_div_date": f(pay),
        "missing_sessions": f(missing),
        "split_factor": f(np.ones((T, N))),
    }


def perturb_future(panels: dict[str, pd.DataFrame], t0: int, seed: int = 7) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    out = {}
    for key, df in panels.items():
        new = df.copy()
        rows = new.index[t0:]
        shape = new.loc[rows].shape
        if key in ("close", "close_adj", "tr_index"):
            new.loc[rows] = df.loc[rows].to_numpy() * rng.uniform(0.3, 2.0, shape)
        elif key in ("volume", "value"):
            new.loc[rows] = rng.uniform(0, 1e7, shape)
        elif key == "status":
            new.loc[rows] = rng.choice(["traded", "not_traded", "suspended"], shape)
        elif key == "last_div_date":
            new.loc[rows] = np.datetime64("2045-01-01", "ns")
        elif key == "missing_sessions":
            new.loc[rows] = rng.integers(0, 2, shape).astype(float)
        elif key == "split_factor":
            new.loc[rows] = 1.0
        else:
            new.loc[rows] = rng.normal(0, 40, shape)
        out[key] = new
    return out


def _same_before(a: pd.DataFrame | pd.Series, b: pd.DataFrame | pd.Series, t0: pd.Timestamp) -> None:
    pd.testing.assert_frame_equal(
        pd.DataFrame(a).loc[: t0 - pd.Timedelta(days=1)], pd.DataFrame(b).loc[: t0 - pd.Timedelta(days=1)]
    )


# ---------------------------------------------------------------------------
# 1. Momentum en séances (§3.2 MOM6_1, §3.3)
# ---------------------------------------------------------------------------


def test_mom6_1_geometric_exact() -> None:
    g = 1.001
    P = _geometric(300, g)
    m = ft.mom6_1(P)
    assert m.iloc[:126].isna().all().all()
    assert m.iloc[126]["A"] == pytest.approx(g**105 - 1.0, rel=1e-12)
    assert m.iloc[-1]["B"] == pytest.approx(g**105 - 1.0, rel=1e-12)
    # Préréglages de recherche (§3.3) : 3-1, 6-0, 12-1, 12-7.
    assert ft.mom3_1(P).iloc[-1]["A"] == pytest.approx(g**42 - 1.0, rel=1e-12)
    assert ft.mom6_0(P).iloc[-1]["A"] == pytest.approx(g**126 - 1.0, rel=1e-12)
    assert ft.mom12_1(P).iloc[-1]["A"] == pytest.approx(g**231 - 1.0, rel=1e-12)
    assert ft.mom12_7(P).iloc[-1]["A"] == pytest.approx(g**105 - 1.0, rel=1e-12)
    assert ft.mom12_1(P).iloc[251].isna().all() and ft.mom12_1(P).iloc[252].notna().all()
    # Paramètres du YAML : leurs clés remplacent les défauts.
    alt = ft.mom6_1(P, params={"lookback_sessions": 63, "skip_sessions": 0, "min_obs": 50, "def": "ignoré"})
    assert alt.iloc[-1]["A"] == pytest.approx(g**63 - 1.0, rel=1e-12)


def test_mom6_1_requires_100_valid_returns_excluding_multi_session() -> None:
    P = _geometric(300)
    miss = pd.DataFrame(0.0, index=P["tr_index"].index, columns=["A", "B"])
    miss.iloc[100:127, 0] = 1.0  # 27 rendements multi-séances dans (0, 126] pour A
    miss.iloc[100:126, 1] = 1.0  # 26 pour B
    m = ft.mom6_1({**P, "missing_sessions": miss})
    assert np.isnan(m.iloc[126]["A"])  # 126 - 27 = 99 < 100
    assert m.iloc[126]["B"] == pytest.approx(1.001**105 - 1.0)  # 100 rendements valides
    # Dès que la fenêtre n'en contient plus que 26 (ligne 226), le signal revient ; les
    # rendements multi-séances restent chaînés dans le TR (valeur inchangée).
    assert np.isnan(m.iloc[225]["A"])
    assert m.iloc[226]["A"] == pytest.approx(1.001**105 - 1.0)
    # Suspension : la séance suspendue et la reprise ne comptent pas.
    st = pd.DataFrame("traded", index=miss.index, columns=["A", "B"])
    st.iloc[50:75, 1] = "suspended"  # 25 séances + la reprise = 26 rendements exclus
    m2 = ft.mom6_1({**P, "status": st})
    assert np.isfinite(m2.iloc[126]["B"])  # 126 - 26 = 100
    st.iloc[50:76, 1] = "suspended"
    assert np.isnan(ft.mom6_1({**P, "status": st}).iloc[126]["B"])  # 99
    # Sans cours en t : NaN.
    tr = P["tr_index"].copy()
    tr.iloc[200, 0] = np.nan
    assert np.isnan(ft.mom6_1({"tr_index": tr}).iloc[200]["A"])


def test_multi_session_from_calendar_gap() -> None:
    dates = pd.DatetimeIndex(["2030-01-07", "2030-01-08", "2030-01-14", "2030-01-15"])  # trou de 6 jours
    P = {"tr_index": pd.DataFrame({"A": [1.0, 2.0, 3.0, 4.0]}, index=dates)}
    m = ft.multi_session_mask(P)
    assert m["A"].tolist() == [False, False, True, False]
    v = ft.valid_return_mask(P)
    assert v["A"].tolist() == [False, True, False, True]


# ---------------------------------------------------------------------------
# 2. Faible volatilité (§3.2 LOWVOL)
# ---------------------------------------------------------------------------


def test_lowvol_exact_and_fallback() -> None:
    rng = np.random.default_rng(3)
    T = 320
    dates = pd.bdate_range("2030-01-01", periods=T)
    r = rng.normal(0, 0.02, (T, 2))
    tr = 100 * np.cumprod(1 + r, axis=0)
    tr[: T - 150, 1] = np.nan  # B coté sur les 150 dernières séances seulement
    P = {"tr_index": pd.DataFrame(tr, index=dates, columns=["A", "B"])}
    lv = ft.lowvol(P)
    ret = P["tr_index"].pct_change(fill_method=None)
    # A : 250 séances, 250 rendements (>= 200).
    assert lv.iloc[-1]["A"] == pytest.approx(-ret["A"].iloc[-250:].std(ddof=1), rel=1e-10)
    # Ligne 199 : 199 rendements < 200 -> repli sur les 126 derniers ; ligne 200 : fenêtre longue.
    assert lv.iloc[199]["A"] == pytest.approx(-ret["A"].iloc[74:200].std(ddof=1), rel=1e-10)
    assert lv.iloc[200]["A"] == pytest.approx(-ret["A"].iloc[1:201].std(ddof=1), rel=1e-10)
    assert np.isnan(lv.iloc[99]["A"]) and np.isfinite(lv.iloc[100]["A"])  # repli : au moins 100
    # B : 149 rendements < 200 -> repli sur 126 séances (>= 100).
    assert lv.iloc[-1]["B"] == pytest.approx(-ret["B"].iloc[-126:].std(ddof=1), rel=1e-10)
    first_b = T - 150
    assert np.isnan(lv.iloc[first_b + 99]["B"]) and np.isfinite(lv.iloc[first_b + 100]["B"])
    # Multi-séances exclus de l'estimation.
    miss = pd.DataFrame(0.0, index=dates, columns=["A", "B"])
    miss.iloc[-10:, 0] = 1.0
    lv2 = ft.lowvol({**P, "missing_sessions": miss})
    keep = ret["A"].iloc[-250:].iloc[:-10]
    assert lv2.iloc[-1]["A"] == pytest.approx(-keep.std(ddof=1), rel=1e-10)
    assert ft.lowvol(P, annualize=True).iloc[-1]["A"] == pytest.approx(lv.iloc[-1]["A"] * np.sqrt(252))


def test_lowvol_excludes_2021_window() -> None:
    dates = pd.bdate_range("2020-06-01", "2021-12-31")
    rng = np.random.default_rng(5)
    r = rng.normal(0, 0.01, len(dates))
    P = {"tr_index": pd.DataFrame({"A": 100 * np.cumprod(1 + r)}, index=dates)}
    t = pd.Timestamp("2021-08-31")
    ret = P["tr_index"]["A"].pct_change(fill_method=None)
    win = ret.loc[:t].iloc[-250:]
    win = win[(win.index < "2021-05-06") | (win.index > "2021-06-25")]
    assert ft.lowvol(P).loc[t, "A"] == pytest.approx(-win.std(ddof=1), rel=1e-10)


# ---------------------------------------------------------------------------
# 3. EP avec surcharges de BPA (§3.2 EP)
# ---------------------------------------------------------------------------


def test_ep_values_and_minimum_rank() -> None:
    dates = pd.bdate_range("2030-01-01", periods=3)
    per = pd.DataFrame([[10.0, 20.0, -5.0, np.nan, 0.0]] * 3, index=dates, columns=list("ABCDE"))
    close = pd.DataFrame(100.0, index=dates, columns=list("ABCDE"))
    ep = ft.ep_signal({"per": per, "close": close, "close_adj": close}, eps_override={})
    assert ep.iloc[0].tolist()[:3] == [0.1, 0.05, 0.0]
    assert np.isnan(ep.iloc[0]["D"]) and ep.iloc[0]["E"] == 0.0
    z = sc.rank_gauss_z(ep)
    assert z.iloc[0]["C"] == z.iloc[0]["E"] == z.iloc[0].min()  # rang minimal (ex aequo)
    loss = ft.ep_signal({"per": per, "close": close}, eps_override={}, missing_per_as_loss=True)
    assert loss.iloc[0]["D"] == 0.0


def test_ep_eps_override_point_in_time() -> None:
    dates = pd.bdate_range("2026-04-06", "2026-04-24")
    cols = ["ETIT", "ORGT", "XXXX"]
    close = pd.DataFrame({"ETIT": 50.0, "ORGT": 2640.0, "XXXX": 100.0}, index=dates)
    per = pd.DataFrame({"ETIT": 2.5, "ORGT": 8.0, "XXXX": 10.0}, index=dates)[cols]
    P = {"per": per, "close": close, "close_adj": close}
    ep = ft.ep_signal(P)
    # ETIT : document du 13/04/2026 (lundi), disponible 2 séances après : 15/04/2026.
    assert ep.loc["2026-04-14", "ETIT"] == pytest.approx(1 / 2.5)
    assert ep.loc["2026-04-15", "ETIT"] == pytest.approx(10.0 / 50.0)
    # ORGT : 04/05/2026, hors de la fenêtre : PER du BOC.
    assert ep["ORGT"].eq(1 / 8.0).all()
    assert ep["XXXX"].eq(0.1).all()
    # Nombre seul (forme du YAML ``data.eps_override``) : la date du tableau par défaut est reprise.
    ep_yaml = ft.ep_signal(P, params={"eps_override": {"ETIT": 10.0, "ORGT": 264}})
    pd.testing.assert_frame_equal(ep_yaml, ep)
    # Symbole hors du tableau : la surcharge s'applique à toutes les dates.
    ep_all = ft.ep_signal(P, eps_override={"XXXX": 20.0})
    assert ep_all["XXXX"].eq(20.0 / 100.0).all() and ep_all.loc["2026-04-24", "ETIT"] == pytest.approx(0.4)
    # Tuple (bpa, date) explicite et délai de publication nul.
    ep0 = ft.ep_signal(P, eps_override={"ETIT": (10.0, "2026-04-13")}, publication_lag_sessions=0)
    assert ep0.loc["2026-04-10", "ETIT"] == pytest.approx(0.4) and ep0.loc["2026-04-13", "ETIT"] == 0.2


# ---------------------------------------------------------------------------
# 4. DY : repli v1 (§3.2 DY)
# ---------------------------------------------------------------------------


def _dy_panels() -> dict[str, pd.DataFrame]:
    dates = pd.bdate_range("2024-01-01", "2026-12-31")
    cols = ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF", "GGG"]
    close = pd.DataFrame(1000.0, index=dates, columns=cols)
    split = pd.DataFrame(1.0, index=dates, columns=cols)
    pre = dates < "2024-10-01"
    close.loc[~pre, "CCC"] = 100.0  # division 10:1 le 01/10/2024
    split.loc[pre, "CCC"] = 10.0
    close.loc["2025-02-01":, "GGG"] = np.nan  # radiation
    amount = pd.DataFrame(np.nan, index=dates, columns=cols)
    pay = pd.DataFrame(pd.NaT, index=dates, columns=cols, dtype="datetime64[ns]")
    seen = dates >= "2024-06-12"  # ligne (d) : la colonne est mise à jour avant le paiement
    for c, a in {"AAA": 100.0, "BBB": 300.0, "CCC": 100.0, "EEE": 200.0, "FFF": 80.0, "GGG": 100.0}.items():
        amount.loc[seen, c] = a
        pay.loc[seen, c] = pd.Timestamp("2024-06-14")
    later = dates >= "2025-06-13"
    amount.loc[later, "FFF"] = 90.0
    pay.loc[later, "FFF"] = pd.Timestamp("2025-06-16")
    close_adj = close / split
    return {
        "close": close, "close_adj": close_adj, "tr_index": close_adj, "split_factor": split,
        "last_div_net": amount, "last_div_date": pay, "net_yield_pct": amount / close * 100,
    }


def test_dy_fallback_rules_exact() -> None:
    P = _dy_panels()
    d = ft.dy_signal_details(
        P,
        announced_absences=[ft.DividendAbsence("FFF", 2024, "2025-03-03")],
        exceptional_dividends=[ft.ExceptionalDividend("EEE", "2024-06-14", 200.0, 100.0)],
    )
    dy, raw, flag, why = d["dy"], d["dy_raw"], d["flag_cap"], d["reason"]
    # Aucun dividende connu (avant la ligne (d), ou jamais) : 0.
    assert dy.loc["2024-06-11", "AAA"] == 0.0 and why.loc["2024-06-11", "AAA"] == "aucun_dividende"
    assert dy["DDD"].eq(0.0).all()
    # Rendement net 100 / 1 000 dès la ligne (d).
    assert dy.loc["2024-06-12", "AAA"] == pytest.approx(0.10)
    # Garde-fou : paiement du 14/06/2024 + 15 mois = 14/09/2025 (dimanche).
    assert dy.loc["2025-09-12", "AAA"] == pytest.approx(0.10)
    assert dy.loc["2025-09-15", "AAA"] == 0.0 and why.loc["2025-09-15", "AAA"] == "perime"
    # Plafond de 15 % avec drapeau.
    assert raw.loc["2025-01-02", "BBB"] == pytest.approx(0.30)
    assert dy.loc["2025-01-02", "BBB"] == 0.15 and bool(flag.loc["2025-01-02", "BBB"])
    assert not flag.loc["2025-01-02", "AAA"]
    # Division 10:1 après l'apparition du montant : le BOC afficherait 100 %.
    assert P["net_yield_pct"].loc["2024-10-01", "CCC"] == pytest.approx(100.0)
    assert dy.loc["2024-09-30", "CCC"] == pytest.approx(0.10)
    assert dy.loc["2024-10-01", "CCC"] == pytest.approx(0.10)
    boc = ft.dy_signal_details(P, source="boc")
    assert boc["dy"].loc["2024-10-01", "CCC"] == 0.15 and bool(boc["flag_cap"].loc["2024-10-01", "CCC"])
    # Dividende exceptionnel : seule la part ordinaire (100 sur 200) compte.
    assert dy.loc["2025-01-02", "EEE"] == pytest.approx(0.10)
    assert ft.dy_signal(P, exclude_exceptional=False).loc["2025-01-02", "EEE"] == 0.15
    # Absence annoncée le 03/03/2025 (lundi) : effective 2 séances après, le 05/03/2025.
    assert dy.loc["2025-03-04", "FFF"] == pytest.approx(0.08)
    assert dy.loc["2025-03-05", "FFF"] == 0.0 and why.loc["2025-03-05", "FFF"] == "absence_annoncee"
    # Un dividende de l'exercice suivant (payé en 2025) lève la règle.
    assert dy.loc["2025-06-13", "FFF"] == pytest.approx(0.09)
    assert ft.dy_signal(P, announced_absences=[ft.DividendAbsence("FFF", 2024, "2025-03-03")],
                        zero_if_no_dividend_voted=False).loc["2025-03-05", "FFF"] == pytest.approx(0.08)
    # Titre radié : NaN.
    assert np.isnan(dy.loc["2025-02-03", "GGG"]) and dy.loc["2025-01-31", "GGG"] == pytest.approx(0.10)
    # Paramètres du YAML (``signals.dy``).
    alt = ft.dy_signal(P, params={"max_age_months": 3, "cap": 0.5, "def": "ignoré"})
    assert alt.loc["2024-09-13", "AAA"] == pytest.approx(0.10) and alt.loc["2024-09-16", "AAA"] == 0.0
    assert alt.loc["2024-07-01", "BBB"] == pytest.approx(0.30)


def test_dy_agm_definition_overrides_fallback() -> None:
    P = _dy_panels()
    agm = pd.DataFrame({
        "symbol": ["AAA", "AAA"],
        "fiscal_year": [2024, 2025],
        "known_from": ["2025-04-01", "2026-04-01"],
        "dps_net_ordinary": [50.0, 0.0],
    })
    d = ft.dy_signal_details(P, agm_dividends=agm)
    dy, why = d["dy"], d["reason"]
    assert dy.loc["2025-04-02", "AAA"] == pytest.approx(0.10)  # repli v1 avant l'AGO connue
    assert dy.loc["2025-04-03", "AAA"] == pytest.approx(0.05)  # 01/04 + 2 séances
    assert dy.loc["2025-12-01", "AAA"] == pytest.approx(0.05)  # pas de date de paiement : pas de garde-fou
    assert dy.loc["2026-04-03", "AAA"] == 0.0 and why.loc["2026-04-03", "AAA"] == "ago_sans_dividende"
    assert dy.loc["2025-04-03", "BBB"] == 0.15  # titres hors table : repli v1


# ---------------------------------------------------------------------------
# 5. Qualité (proxy v1)
# ---------------------------------------------------------------------------


def test_dividend_years_and_quality_proxy_exact() -> None:
    dates = pd.bdate_range("2018-01-01", "2024-12-31")
    cols = ["A", "B", "C"]
    pay = pd.DataFrame(pd.NaT, index=dates, columns=cols, dtype="datetime64[ns]")
    amount = pd.DataFrame(np.nan, index=dates, columns=cols)
    for year in range(2018, 2025):
        d = pd.Timestamp(year=year, month=6, day=15)
        rows = dates >= d
        pay.loc[rows, "A"] = d
        amount.loc[rows, "A"] = 10.0
        if year in (2018, 2019, 2021):
            pay.loc[rows, "B"] = d
            amount.loc[rows, "B"] = 5.0
    close = pd.DataFrame(100.0, index=dates, columns=cols)
    per = pd.DataFrame({"A": 10.0, "B": 50.0, "C": np.nan}, index=dates)
    P = {"close": close, "close_adj": close, "last_div_date": pay, "last_div_net": amount, "per": per}
    yrs = ft.dividend_years(P)
    assert yrs.loc["2021-03-01"].tolist() == [3.0, 2.0, 0.0]  # A : 2018-2020 ; B : 2018-2019
    assert yrs.loc["2024-11-20"].tolist() == [5.0, 1.0, 0.0]  # fenêtre (20/11/2019, 20/11/2024]
    q = ft.quality_proxy(P, eps_override={})
    # Rangs (r - 1)/(N - 1) : A = 1, B = 0,5, C = 0 ; PER sain : A seulement.
    assert q.loc["2024-11-20"].tolist() == pytest.approx([1.0, 0.25, 0.0])
    q_yaml = ft.quality_proxy(P, eps_override={}, params={"dividend_years_of_5": 1.0, "per_sane_weight": 0.0})
    assert q_yaml.loc["2024-11-20"].tolist() == pytest.approx([1.0, 0.5, 0.0])
    univ = pd.DataFrame(True, index=dates, columns=cols)
    univ["C"] = False
    q_u = ft.quality_proxy(P, eps_override={}, universe=univ)
    assert q_u.loc["2024-11-20", "B"] == pytest.approx(0.0) and np.isnan(q_u.loc["2024-11-20", "C"])


# ---------------------------------------------------------------------------
# 6. Modulateurs du momentum
# ---------------------------------------------------------------------------


def test_momentum_spread_returns_exact() -> None:
    dates = pd.bdate_range("2030-01-01", "2030-03-29")
    cols = [f"S{j}" for j in range(6)]
    daily = np.array([0.01 * j for j in range(6)])
    tr = pd.DataFrame(100 * np.cumprod(np.broadcast_to(1 + daily, (len(dates), 6)), axis=0),
                      index=dates, columns=cols)
    mom = pd.DataFrame(np.broadcast_to(np.arange(6.0), (len(dates), 6)), index=dates, columns=cols)
    s = ft.momentum_spread_returns({"tr_index": tr}, mom=mom)
    jan_end = dates[dates.month == 1][-1]
    first = dates.get_loc(jan_end) + 2  # formation fin janvier, détention dès la clôture de t+1
    assert s.iloc[:first].isna().all()
    # Tiers supérieur = S4, S5 : 0,045 - 0,025 (panier de l'univers) = 0,02.
    assert np.allclose(s.iloc[first:].to_numpy(), 0.02)
    univ = pd.DataFrame(True, index=dates, columns=cols)
    univ["S5"] = False  # S5 hors univers : tiers supérieur = S3, S4 parmi 5 titres
    s2 = ft.momentum_spread_returns({"tr_index": tr}, mom=mom, universe=univ)
    assert np.allclose(s2.iloc[first:].to_numpy(), 0.035 - 0.02)


def test_vol_scaling_rules() -> None:
    dates = pd.bdate_range("2030-01-01", periods=1300)
    sign = np.where(np.arange(len(dates)) % 2 == 0, 1.0, -1.0)
    amp = np.where(dates < "2033-01-01", 0.01, 0.03)
    amp = np.where(dates >= "2034-01-01", 0.005, amp)
    spread = pd.Series(sign * amp, index=dates)
    m = ft.vol_scaling(spread)
    sig = spread.rolling(126, min_periods=100).std(ddof=1)
    first = sig.first_valid_index()
    ready = dates >= first + pd.DateOffset(months=24)
    assert m[~ready].eq(1.0).all()
    for t in (dates[ready][0], pd.Timestamp("2033-06-30"), pd.Timestamp("2034-08-31")):
        t = dates[dates <= t][-1]
        expected = float(np.clip(np.median(sig.loc[:t].dropna()) / sig.loc[t], 0.5, 1.0))
        assert m.loc[t] == pytest.approx(expected, rel=1e-12)
    assert m.loc["2033-06-30"] == pytest.approx(0.5)  # σ̂ triplée : plancher 0,5
    assert m.loc["2034-08-29"] == 1.0  # σ̂ faible : plafond 1
    assert m.between(0.5, 1.0).all()
    # Moins de 24 mois d'historique après history_start : multiplicateur 1.
    assert ft.vol_scaling(spread, history_start="2032-06-01").loc[:"2034-06-01"].eq(1.0).all()
    assert ft.vol_scaling(spread, params={"min_history_months": 6, "floor": 0.8}).min() == pytest.approx(0.8)


def _crash_expected(level: pd.Series, months: int = 24, win: int = 63, q: float = 0.8,
                    min_hist: int = 252, dur: int = 3) -> pd.Series:
    """Implémentation indépendante (boucles) du filtre de crash."""
    r = level.pct_change(fill_method=None)
    vol = r.rolling(win, min_periods=50).std(ddof=1)
    trig = []
    for i, t in enumerate(level.index):
        past = level.loc[: t - pd.DateOffset(months=months)]
        bear = len(past) > 0 and level.iloc[i] / past.iloc[-1] - 1 < 0
        hist = vol.iloc[: i + 1].dropna()
        high = len(hist) >= min_hist and vol.iloc[i] > np.percentile(hist, 100 * q)
        trig.append(bool(bear and high))
    out = pd.Series(1.0, index=level.index)
    for t in level.index[np.array(trig)]:
        out[(level.index >= t) & (level.index < t + pd.DateOffset(months=dur))] = 0.5
    return out


def test_crash_filter_matches_independent_loop() -> None:
    dates = pd.bdate_range("2030-01-01", periods=1100)
    i = np.arange(len(dates))
    alt = np.where(i % 2 == 0, 1.0, -1.0)
    r = 0.0008 + 0.002 * alt  # marché haussier calme
    crash = (i >= 760) & (i < 800)
    r = np.where(crash, -0.012 + 0.03 * alt, r)  # krach : environ -40 % en 40 séances
    r = np.where(i >= 800, 0.0002 + 0.002 * alt, r)
    level = pd.Series(100 * np.cumprod(1 + r), index=dates)
    m = ft.crash_filter(level, exclude_windows=())
    pd.testing.assert_series_equal(m, _crash_expected(level), check_names=False)
    assert m.iloc[:760].eq(1.0).all() and m.iloc[799] == 0.5 and m.iloc[-1] == 1.0
    # Même krach dans un marché encore au-dessus de son niveau d'il y a 24 mois : aucun déclenchement.
    mild = np.where(crash, -0.002 + 0.03 * alt, r)
    lvl2 = pd.Series(100 * np.cumprod(1 + np.where(i < 760, 0.0008 + 0.002 * alt, mild)), index=dates)
    assert ft.crash_filter(lvl2, exclude_windows=()).eq(1.0).all()
    # Combinaison des modulateurs.
    mm = ft.momentum_multiplier(m, pd.Series(0.8, index=dates))
    assert mm.loc[dates[799]] == pytest.approx(0.4) and mm.iloc[0] == pytest.approx(0.8)


# ---------------------------------------------------------------------------
# 7. Score composite (§3.1.6, §3.2, §3.4) et malus S2 (§5.2)
# ---------------------------------------------------------------------------


def test_variant_weights_match_specification() -> None:
    assert sc.VARIANT_WEIGHTS["A"] == {"ep": 0.15, "dy": 0.20, "mom6_1": 0.35, "lowvol": 0.20, "quality_proxy": 0.10}
    assert sc.VARIANT_WEIGHTS["B"] == {"ep": 0.25, "dy": 0.25, "mom6_1": 0.50}
    assert sc.VARIANT_WEIGHTS["C"] == {"ep": 0.15, "dy": 0.20, "mom6_1": 0.20, "mom12_1": 0.15,
                                       "lowvol": 0.20, "quality_proxy": 0.10}
    assert sc.VARIANT_WEIGHTS["D"] == sc.VARIANT_WEIGHTS["A"] and sc.VARIANT_SECTOR_NEUTRAL["D"] == ("ep", "dy")
    for w in sc.VARIANT_WEIGHTS.values():
        assert sum(w.values()) == pytest.approx(1.0)
    with pytest.raises(KeyError):
        sc.variant_weights("Z")


@pytest.mark.skipif(not YAML.exists(), reason="configs/strategy_v1.yaml absent")
def test_defaults_match_strategy_yaml() -> None:
    yaml = pytest.importorskip("yaml")
    cfg = yaml.safe_load(YAML.read_text(encoding="utf-8"))
    for code in ("A", "B", "C"):
        assert sc.VARIANT_WEIGHTS[code] == pytest.approx(cfg["composite"][code])
    sig = cfg["signals"]
    for key in ("mom6_1", "lowvol"):
        for k, v in sig[key].items():
            assert ft.SIGNAL_PARAMS_V1[key][k] == pytest.approx(v), (key, k)
    for k in ("max_age_months", "cap", "exclude_exceptional", "zero_if_no_dividend_voted"):
        assert ft.SIGNAL_PARAMS_V1["dy"][k] == sig["dy"][k]
    qp = sig["quality_proxy"]
    assert ft.SIGNAL_PARAMS_V1["quality_proxy"]["dividend_years_weight"] == qp["dividend_years_of_5"]
    assert list(ft.SIGNAL_PARAMS_V1["quality_proxy"]["per_sane_range"]) == qp["per_sane_range"]
    tr = sig["transform"]
    assert tr["winsor_pct"] == [1, 99] and tr["clip"] == 3.0 and tr["min_valid_blocks"] == 3
    vs, cf = cfg["composite"]["momentum_vol_scaling"], cfg["composite"]["momentum_crash_filter"]
    assert ft.SIGNAL_PARAMS_V1["momentum_vol_scaling"]["window_sessions"] == vs["window_sessions"]
    assert ft.SIGNAL_PARAMS_V1["momentum_vol_scaling"]["min_history_months"] == vs["min_history_months"]
    assert ft.SIGNAL_PARAMS_V1["momentum_vol_scaling"]["floor"] == vs["floor"]
    for k, v in cf.items():
        assert ft.SIGNAL_PARAMS_V1["momentum_crash_filter"][k] == v, k
    assert cfg["composite"]["s2_post_ex_penalty_sd"] == -0.5 and cfg["composite"]["s2_sessions"] == 20
    eps = cfg["data"]["eps_override"]
    assert {k: o.eps for k, o in ft.EPS_OVERRIDES_V1.items()} == pytest.approx(eps)


def test_modulate_weights_prorata() -> None:
    w = sc.modulate_weights(sc.VARIANT_WEIGHTS["A"], 0.5)
    freed = 0.175
    assert w["mom6_1"] == pytest.approx(0.175)
    for k in ("ep", "dy", "lowvol", "quality_proxy"):
        assert w[k] == pytest.approx(sc.VARIANT_WEIGHTS["A"][k] * (1 + freed / 0.65))
    assert sum(w.values()) == pytest.approx(1.0)
    m = pd.Series([1.0, 0.5, 0.25], index=pd.bdate_range("2030-01-01", periods=3))
    W = sc.modulate_weights(sc.VARIANT_WEIGHTS["C"], m)
    assert W.sum(axis=1).to_numpy() == pytest.approx(np.ones(3))
    assert W.loc[m.index[2], "mom12_1"] == pytest.approx(0.15 * 0.25)
    assert W.loc[m.index[0]].to_dict() == pytest.approx(sc.VARIANT_WEIGHTS["C"])
    with pytest.raises(ValueError):
        sc.modulate_weights(sc.VARIANT_WEIGHTS["A"], 1.5)


def test_rank_gauss_z_formula_universe_and_missing() -> None:
    dates = pd.bdate_range("2030-01-01", periods=1)
    x = pd.DataFrame([[3.0, 1.0, 2.0, np.nan, 7.0]], index=dates, columns=list("ABCDE"))
    univ = pd.DataFrame([[True, True, True, True, False]], index=dates, columns=list("ABCDE"))
    z = sc.rank_gauss_z(x, universe=univ)
    assert z.iloc[0]["A"] == pytest.approx(norm.ppf(2.5 / 3))
    assert z.iloc[0]["B"] == pytest.approx(norm.ppf(0.5 / 3))
    assert z.iloc[0]["C"] == pytest.approx(0.0, abs=1e-15)
    assert z.iloc[0]["D"] == 0.0 and np.isnan(z.iloc[0]["E"])  # manquant -> 0 ; hors univers -> NaN
    # Ex aequo : rang moyen.
    t = sc.rank_gauss_z(pd.DataFrame([[1.0, 1.0, 2.0]], index=dates, columns=list("abc")))
    assert t.iloc[0]["a"] == t.iloc[0]["b"] == pytest.approx(norm.ppf(1.0 / 3))
    # Winsorisation 1-99 : avec 201 valeurs, les deux extrêmes rejoignent le 3e.
    big = pd.DataFrame([np.arange(201.0)], index=dates)
    zb = sc.rank_gauss_z(big)
    assert zb.iloc[0, 0] == zb.iloc[0, 2] == pytest.approx(norm.ppf(1.5 / 201))
    assert zb.iloc[0, 200] == pytest.approx(norm.ppf(199.5 / 201))
    assert sc.rank_gauss_z(big, winsor_pct=None).iloc[0, 0] == pytest.approx(norm.ppf(0.5 / 201))
    assert sc.rank_gauss_z(big, winsor_pct=None, clip=2.0).iloc[0, 0] == -2.0


def test_rank_gauss_z_within_sectors_variant_d() -> None:
    dates = pd.bdate_range("2030-01-01", periods=1)
    cols = [f"F{i}" for i in range(4)] + [f"C{i}" for i in range(4)] + ["X0", "X1", "Y0"]
    sectors = pd.Series(["FIN"] * 4 + ["CB"] * 4 + ["XX"] * 2 + ["YY"], index=cols)
    vals = np.array([4, 3, 2, 1, 40, 30, 20, 10, 5, 6, 7], dtype=float)
    x = pd.DataFrame([vals], index=dates, columns=cols)
    z = sc.rank_gauss_z(x, groups=sectors)
    assert z.iloc[0]["F0"] == pytest.approx(norm.ppf(3.5 / 4)) == pytest.approx(z.iloc[0]["C0"])
    assert z.iloc[0]["F3"] == pytest.approx(norm.ppf(0.5 / 4))
    # XX (2) et YY (1) ont moins de 4 titres : regroupés (3 titres).
    assert z.iloc[0][["X0", "X1", "Y0"]].tolist() == pytest.approx(norm.ppf(np.array([0.5, 1.5, 2.5]) / 3))
    # Si CB perd un titre de l'univers, il rejoint le groupe regroupé.
    univ = pd.DataFrame([[True] * 11], index=dates, columns=cols)
    univ["C3"] = False
    z2 = sc.rank_gauss_z(x, universe=univ, groups=sectors)
    pooled = ["C0", "C1", "C2", "X0", "X1", "Y0"]  # valeurs 40, 30, 20, 5, 6, 7
    assert z2.iloc[0]["C0"] == pytest.approx(norm.ppf(5.5 / 6)) and z2.iloc[0]["X0"] == pytest.approx(norm.ppf(0.5 / 6))
    assert z2.iloc[0][pooled].notna().all() and np.isnan(z2.iloc[0]["C3"])


def test_s2_penalty_panel() -> None:
    cal = pd.bdate_range("2030-01-01", periods=40)
    ev = pd.DataFrame({"symbol": ["A", "B"], "ex_date": [cal[3], pd.Timestamp("2030-01-12")]})  # B : samedi
    pen = sc.s2_penalty_panel(ev, cal, symbols=["A", "B", "C"])
    assert pen["A"].iloc[3:23].eq(-0.5).all() and pen["A"].drop(pen.index[3:23]).eq(0.0).all()
    b0 = cal.searchsorted(pd.Timestamp("2030-01-14"))
    assert pen["B"].iloc[b0] == -0.5 and pen["B"].iloc[b0 - 1] == 0.0 and pen["C"].eq(0.0).all()
    wide = pd.DataFrame(False, index=cal, columns=["A", "B", "C"])
    wide.iloc[3, 0] = True
    wide.iloc[b0, 1] = True
    pd.testing.assert_frame_equal(sc.s2_penalty_panel(wide, cal, symbols=["A", "B", "C"]), pen)
    shifted = sc.s2_penalty_panel(ev, cal, symbols=["A"], start_offset=1, sessions=5)
    assert shifted["A"].iloc[4:9].eq(-0.5).all() and shifted["A"].sum() == pytest.approx(-2.5)
    # Deux détachements qui se chevauchent ne se cumulent pas.
    ev2 = pd.DataFrame({"symbol": ["A", "A"], "ex_date": [cal[3], cal[10]]})
    assert sc.s2_penalty_panel(ev2, cal)["A"].min() == -0.5


def _blocks_example() -> tuple[dict[str, pd.DataFrame], pd.DatetimeIndex]:
    dates = pd.bdate_range("2030-01-01", periods=2)
    cols = list("ABCDE")
    ep = pd.DataFrame([[0.10, 0.05, 0.02, 0.08, np.nan]] * 2, index=dates, columns=cols)
    dy = pd.DataFrame([[0.03, 0.07, 0.01, np.nan, np.nan]] * 2, index=dates, columns=cols)
    mom = pd.DataFrame([[0.20, -0.10, 0.40, 0.00, 0.30]] * 2, index=dates, columns=cols)
    return {"ep": ep, "dy": dy, "mom6_1": mom}, dates


def test_composite_score_by_hand() -> None:
    blocks, dates = _blocks_example()
    res = sc.composite_score(blocks, "B", return_details=True)
    assert isinstance(res, sc.CompositeResult)
    zf = lambda r, n: norm.ppf((r - 0.5) / n)
    z_ep = {"A": zf(4, 4), "B": zf(2, 4), "C": zf(1, 4), "D": zf(3, 4), "E": 0.0}
    z_dy = {"A": zf(2, 3), "B": zf(3, 3), "C": zf(1, 3), "D": 0.0, "E": 0.0}
    z_mo = {"A": zf(3, 5), "B": zf(1, 5), "C": zf(5, 5), "D": zf(2, 5), "E": zf(4, 5)}
    S = {k: 0.25 * z_ep[k] + 0.25 * z_dy[k] + 0.5 * z_mo[k] for k in "ABC"}
    S.update({"D": 0.0, "E": 0.0})  # moins de 3 blocs valides : score neutre
    assert res.raw.iloc[0].to_dict() == pytest.approx(S)
    assert res.n_valid.iloc[0].tolist() == [3, 3, 3, 2, 1]
    ranks = pd.Series(S).rank()
    assert res.score.iloc[0].to_dict() == pytest.approx({k: zf(ranks[k], 5) for k in S})
    # min_valid_blocks depuis le YAML.
    loose = sc.composite_score(blocks, "B", params={"min_valid_blocks": 2}, return_details=True)
    assert loose.raw.iloc[0]["D"] == pytest.approx(0.25 * z_ep["D"] + 0.5 * z_mo["D"])
    # Univers : E exclu -> NaN, rangs recalculés sur 4 titres.
    univ = pd.DataFrame(True, index=dates, columns=list("ABCDE"))
    univ["E"] = False
    u = sc.composite_score(blocks, "B", universe=univ, return_details=True)
    assert np.isnan(u.score.iloc[0]["E"]) and u.z["mom6_1"].iloc[0]["C"] == pytest.approx(zf(4, 4))
    with pytest.raises(KeyError):
        sc.composite_score(blocks, "A")  # blocs lowvol et quality_proxy absents


def test_composite_s2_malus_new_buys_only_and_momentum_modulation() -> None:
    blocks, dates = _blocks_example()
    base = sc.composite_score(blocks, "B", return_details=True)
    malus = pd.DataFrame(0.0, index=dates, columns=list("ABCDE"))
    malus["C"] = -0.5
    res = sc.composite_score(blocks, "B", s2_malus=malus, return_details=True)
    sd = base.raw.iloc[0].std(ddof=1)
    assert res.with_malus.iloc[0]["C"] == pytest.approx(base.raw.iloc[0]["C"] - 0.5 * sd)
    assert res.with_malus.iloc[0]["A"] == pytest.approx(base.raw.iloc[0]["A"])
    assert res.score.iloc[0]["C"] < base.score.iloc[0]["C"]
    held = pd.Series({"C": True})  # titre détenu : aucun malus, aucune vente forcée
    kept = sc.composite_score(blocks, "B", s2_malus=malus, held=held)
    pd.testing.assert_frame_equal(kept, base.score)
    raw = sc.composite_score(blocks, "B", s2_malus=malus, s2_units="raw", return_details=True)
    assert raw.with_malus.iloc[0]["C"] == pytest.approx(base.raw.iloc[0]["C"] - 0.5)
    # Modulateur du momentum : poids libéré redistribué au prorata.
    m = pd.Series([1.0, 0.5], index=dates)
    mod = sc.composite_score(blocks, "B", momentum_multiplier=m, return_details=True)
    assert mod.weights.iloc[0].to_dict() == pytest.approx({"ep": 0.25, "dy": 0.25, "mom6_1": 0.5})
    assert mod.weights.iloc[1].to_dict() == pytest.approx({"ep": 0.375, "dy": 0.375, "mom6_1": 0.25})
    z = base.z
    expect = 0.375 * z["ep"].iloc[1]["A"] + 0.375 * z["dy"].iloc[1]["A"] + 0.25 * z["mom6_1"].iloc[1]["A"]
    assert mod.raw.iloc[1]["A"] == pytest.approx(expect)
    assert mod.raw.iloc[0].to_dict() == pytest.approx(base.raw.iloc[0].to_dict())


def test_composite_variant_d_uses_sectors() -> None:
    rng = np.random.default_rng(11)
    dates = pd.bdate_range("2030-01-01", periods=3)
    cols = [f"S{i}" for i in range(10)]
    blocks = {k: pd.DataFrame(rng.normal(size=(3, 10)), index=dates, columns=cols) for k in sc.VARIANT_WEIGHTS["A"]}
    sectors = pd.Series(["FIN"] * 5 + ["CB"] * 4 + ["TEL"], index=cols)
    with pytest.raises(ValueError):
        sc.composite_score(blocks, "D")
    d = sc.composite_score(blocks, "D", sectors=sectors, return_details=True)
    a = sc.composite_score(blocks, "A", return_details=True)
    pd.testing.assert_frame_equal(d.z["ep"], sc.rank_gauss_z(blocks["ep"], groups=sectors))
    pd.testing.assert_frame_equal(d.z["mom6_1"], a.z["mom6_1"])
    assert not np.allclose(d.z["dy"].to_numpy(), a.z["dy"].to_numpy())


# ---------------------------------------------------------------------------
# 8. Absence d'anticipation
# ---------------------------------------------------------------------------

LOOKAHEAD_CASES = {
    "mom6_1": lambda P: ft.mom6_1(P),
    "mom12_7": lambda P: ft.mom12_7(P),
    "mom3_1": lambda P: ft.mom3_1(P),
    "lowvol": lambda P: ft.lowvol(P),
    "ep": lambda P: ft.ep_signal(P),
    "dy": lambda P: ft.dy_signal(P),
    "dy_reason": lambda P: ft.dy_signal_details(P)["reason"],
    "dividend_years": lambda P: ft.dividend_years(P),
    "quality": lambda P: ft.quality_proxy(P),
    "amihud": lambda P: ft.amihud_signal(P),
    "spread": lambda P: ft.momentum_spread_returns(P).to_frame(),
    "vol_scaling": lambda P: ft.vol_scaling(ft.momentum_spread_returns(P), min_history_months=6,
                                            min_obs=60).to_frame(),
}


@pytest.mark.parametrize("name", sorted(LOOKAHEAD_CASES))
def test_signals_have_no_lookahead(name: str) -> None:
    P = synth_panels()
    t0 = 420
    a = LOOKAHEAD_CASES[name](P)
    b = LOOKAHEAD_CASES[name](perturb_future(P, t0))
    _same_before(a, b, P["close"].index[t0])


def test_crash_filter_and_composite_have_no_lookahead() -> None:
    P = synth_panels()
    t0 = 420
    cut = P["close"].index[t0]
    level = P["tr_index"].pct_change(fill_method=None).mean(axis=1).fillna(0.0).add(1).cumprod()
    lvl2 = level.copy()
    lvl2.iloc[t0:] *= np.random.default_rng(0).uniform(0.2, 3.0, len(lvl2) - t0)
    kw = {"bear_lookback_months": 6, "min_history_sessions": 60}
    _same_before(ft.crash_filter(level, **kw), ft.crash_filter(lvl2, **kw), cut)

    def score(Q: dict[str, pd.DataFrame]) -> pd.DataFrame:
        blocks = ft.signal_blocks_v1(Q, include_research=False)
        univ = blocks["mom6_1"].notna() & Q["status"].ne("suspended")
        pen = sc.s2_penalty_panel(pd.DataFrame({"symbol": ["S00", "S02"], "ex_date": ["2030-06-12", "2031-06-12"]}),
                                  Q["close"].index)
        return sc.composite_score(blocks, "A", s2_malus=pen, universe=univ, momentum_multiplier=0.7)

    _same_before(score(P), score(perturb_future(P, t0)), cut)


# ---------------------------------------------------------------------------
# 9. Panel réel : valeurs du §12.3 n° 5 et contrôles de forme (performance : S0 seulement)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def real_panels() -> dict[str, pd.DataFrame]:
    eq_path, adj_path = PANEL_DIR / "equities.parquet", PANEL_DIR / "adjusted_prices.parquet"
    if not (eq_path.exists() and adj_path.exists()):
        pytest.skip("panel réel absent (data/panel)")
    return ft.panels_for_signals(pd.read_parquet(eq_path), pd.read_parquet(adj_path))


def test_real_panel_regression_values_12_3_n5(real_panels: dict[str, pd.DataFrame]) -> None:
    P = real_panels
    t = "2026-11-20"
    d = ft.dy_signal_details(P)
    # §12.3 n° 5 : dy_used(FTSC, 2026-11-20) = 0 ; ep(ETIT) = 10/57.
    assert d["dy"].loc[t, "FTSC"] == 0.0
    assert ft.ep_signal(P).loc[t, "ETIT"] == pytest.approx(10.0 / 57.0, rel=1e-12)
    assert P["per"].loc[t, "ETIT"] == pytest.approx(2.98)  # PER du BOC (RN total), remplacé
    # Revue 06b §7.6 : avant l'AGO 2025, DY(FTSC) > 0, plafonné avec drapeau (part ordinaire seule).
    assert d["dy"].loc["2026-03-31", "FTSC"] == pytest.approx(0.15)
    assert bool(d["flag_cap"].loc["2026-03-31", "FTSC"])
    assert d["dy_raw"].loc["2026-03-31", "FTSC"] == pytest.approx(1161.60 / P["close"].loc["2026-03-31", "FTSC"])
    # Absences annoncées (BOAN 2025, ORGT, SAFC) : rendement BOC trompeur mis à 0.
    for sym in ("BOAN", "ORGT", "SAFC"):
        assert d["dy"].loc[t, sym] == 0.0, sym
    assert P["net_yield_pct"].loc[t, "BOAN"] == pytest.approx(4.73)
    # Division SNTS 10:1 (26/10/2026) : DPS 174 et non le rendement BOC de 37 %.
    assert d["dy"].loc["2026-10-26", "SNTS"] == pytest.approx(174.0 / P["close"].loc["2026-10-26", "SNTS"])
    # Rendement ordinaire inchangé : ABJC 201,52 / 3 000.
    assert d["dy"].loc[t, "ABJC"] == pytest.approx(201.52 / 3000.0)


def test_real_panel_shapes(real_panels: dict[str, pd.DataFrame]) -> None:
    """Contrôles de forme sur tout l'historique (aucune performance calculée)."""
    blocks = ft.signal_blocks_v1(real_panels)
    assert set(ft.V1_SIGNALS) | set(ft.RESEARCH_SIGNALS_V1) <= set(blocks)
    grid = real_panels["close"]
    t = pd.Timestamp("2026-10-30")
    for name, df in blocks.items():
        assert df.shape == grid.shape, name
        assert not np.isinf(df.to_numpy(dtype=float)).any(), name
    for name in ft.V1_SIGNALS:
        assert blocks[name].loc[t].notna().sum() >= 40, name
    assert blocks["dy"].max().max() <= 0.15 and blocks["dy"].min().min() >= 0.0
    assert blocks["quality_proxy"].stack().dropna().between(0.0, 1.0).all()
    assert (blocks["lowvol"].stack().dropna() <= 0).all()


def test_real_panel_composite_and_vol_scaling_s0_only(real_panels: dict[str, pd.DataFrame]) -> None:
    """Score composite et dosage du momentum sur **S0** uniquement (données tronquées)."""
    s0 = {k: v.loc[S0_START:S0_END] for k, v in real_panels.items()}
    # Signaux calculés sur l'historique complet (aucune performance), scores sur S0.
    blocks = {k: v.loc[S0_START:S0_END] for k, v in ft.signal_blocks_v1(real_panels, include_research=False).items()}
    me = pd.DatetimeIndex(s0["close"].index.to_series().groupby(s0["close"].index.to_period("M")).max())
    univ = (blocks["mom6_1"].notna() & s0["status"].ne("suspended")).loc[me]
    res = sc.composite_score({k: v.loc[me] for k, v in blocks.items()}, "A", universe=univ, return_details=True)
    sc_ = res.score
    assert ((sc_.notna()) == univ).all().all()
    assert sc_.abs().max().max() <= 3.0
    assert sc_.mean(axis=1).abs().max() < 1e-9  # rangs symétriques
    assert (univ.sum(axis=1) >= 15).all()
    # Spread du momentum et dosage par la volatilité : données S0 seulement.
    spread = ft.momentum_spread_returns(s0, mom=ft.mom6_1(s0))
    m = ft.vol_scaling(spread)
    assert m.between(0.5, 1.0).all()
    first = spread.rolling(126, min_periods=100).std().first_valid_index()
    assert m.loc[: first + pd.DateOffset(months=24) - pd.Timedelta(days=1)].eq(1.0).all()


def test_composite_single_cross_section_and_held_weights() -> None:
    blocks, _dates = _blocks_example()
    full = sc.composite_score(blocks, "B")
    row = sc.composite_score({k: v.iloc[0] for k, v in blocks.items()}, "B")
    assert isinstance(row, pd.Series)
    pd.testing.assert_series_equal(row, full.iloc[0], check_names=False)
    malus = pd.Series({"A": 0.0, "B": 0.0, "C": -0.5, "D": 0.0, "E": 0.0})
    held_w = pd.Series({"A": 0.10, "C": 0.08, "B": 0.0})  # poids détenus : C ne reçoit pas de malus
    kept = sc.composite_score({k: v.iloc[0] for k, v in blocks.items()}, "B", s2_malus=malus, held=held_w)
    pd.testing.assert_series_equal(kept, row)
    hit = sc.composite_score({k: v.iloc[0] for k, v in blocks.items()}, "B", s2_malus=malus)
    assert hit["C"] < row["C"]


def test_valid_mask_accepts_store_stats_mask_and_or_rule() -> None:
    dates = pd.DatetimeIndex(["2030-01-07", "2030-01-08", "2030-01-09", "2030-01-16", "2030-01-17"])
    tr = pd.DataFrame({"A": [1.0, 1.1, 1.2, 1.3, 1.4]}, index=dates)
    miss = pd.DataFrame({"A": [0.0, 0.0, 1.0, 0.0, 0.0]}, index=dates)
    m = ft.multi_session_mask({"tr_index": tr, "missing_sessions": miss})
    assert m["A"].tolist() == [False, False, True, True, False]  # BOC manquant OU trou de 7 jours
    usable = pd.DataFrame({"A": [True, True, True, True, False]}, index=dates)
    v = ft.valid_return_mask({"tr_index": tr, "missing_sessions": miss, "stats_usable": usable})
    assert v["A"].tolist() == [False, True, True, True, False]  # masque du store, cours requis en t-1
