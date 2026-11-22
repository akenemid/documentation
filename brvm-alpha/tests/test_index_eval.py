"""Tests de ``brvm_alpha.notes.index_eval`` : évaluation des indices et dossier.

Panel synthétique (symboles réels, nombre de titres de ``reference.SHARES_OUTSTANDING_2026``,
Composite pondéré par la capitalisation totale) pour des vérifications exactes ; tests sur le
panel réel ``data/panel`` (ignorés s'il est absent) pour la cohérence avec les BOC. Aucun
réseau ; le journal des notes est créé sous ``tmp_path``.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from brvm_alpha.notes import index_eval as ie
from brvm_alpha.notes import signals as sg
from brvm_alpha.notes.model import Note
from brvm_alpha.notes.store import NoteStore
from brvm_alpha.quant.regime import market_regime
from brvm_alpha.reference import SHARES_OUTSTANDING_2026

REAL_PANEL = Path(__file__).resolve().parents[1] / "data" / "panel"
HAS_REAL = (REAL_PANEL / "equities.parquet").exists() and (REAL_PANEL / "indices.parquet").exists()

SYMS = {
    "SNTS": ("TEL", "PRESTIGE", "AUT"), "ORAC": ("TEL", "PRESTIGE", "AUT"), "SGBC": ("FIN", "PRESTIGE", "FIN"),
    "SPHC": ("CB", "PRESTIGE", "AGR"), "BOAN": ("FIN", "PRINCIPAL", "FIN"), "ETIT": ("FIN", "PRINCIPAL", "FIN"),
    "SOGC": ("CB", "PRINCIPAL", "AGR"), "BOAS": ("FIN", "PRINCIPAL", "FIN"),
}


def bdays(start: str, end: str) -> pd.DatetimeIndex:
    d = pd.bdate_range(start, end)
    return d[~d.strftime("%m-%d").isin(["01-01", "05-01", "08-07", "08-15", "11-01", "11-15", "12-25"])]


DATES = bdays("2022-01-03", "2026-11-20")


def _cap_index(prices: pd.DataFrame, members: list[str], base_date: str, base: float) -> pd.Series:
    n = pd.Series({s: float(SHARES_OUTSTANDING_2026[s]) for s in members})
    cap = (prices[members] * n).sum(axis=1)
    return cap / cap.loc[pd.Timestamp(base_date):].iloc[0] * base


def _ytd(level: pd.Series) -> pd.Series:
    out = pd.Series(np.nan, index=level.index)
    for y, g in level.groupby(level.index.year):
        prev = level[level.index.year < y]
        ref = prev.iloc[-1] if len(prev) else g.iloc[0]
        out.loc[g.index] = 100 * (g / ref - 1)
    return out.round(2)


def synthetic_panel(dates: pd.DatetimeIndex = DATES) -> dict[str, pd.DataFrame]:
    k = np.arange(len(dates), dtype=float)
    prices = {}
    for i, s in enumerate(SYMS):
        mu = 0.0004 * (i + 1) - 0.0010
        prices[s] = (1000.0 * (i + 1)) * np.exp(mu * k + 0.03 * np.sin(k / 9.0 + i))
    px = pd.DataFrame(prices, index=dates).round(4)
    rows = []
    for d_i, d in enumerate(dates):
        for i, s in enumerate(SYMS):
            sec25, comp, sec99 = SYMS[s]
            sector = sec25 if d.year >= 2025 else sec99
            compartment = comp if d.year >= 2023 else {"FIN": "FINANCES", "AUT": "AUTRES SECTEURS", "AGR": "AGRICULTURE"}[sec99]
            vol = 1000.0 + 300.0 * i + 50.0 * math.sin(d_i / 5.0)
            rows.append({"date": d, "symbol": s, "name": f"SOCIETE {s}", "sector": sector, "compartment": compartment,
                         "close": px.at[d, s], "volume": vol, "value": vol * px.at[d, s],
                         "per": 8.0 + 0.004 * d_i + i, "net_yield_pct": 7.0 - 0.001 * d_i + 0.1 * i,
                         "status": "traded", "change_pct": np.nan})
    eq = pd.DataFrame(rows)
    comp = _cap_index(px, list(SYMS), "2022-01-03", 200.0)
    prest = [s for s in SYMS if SYMS[s][1] == "PRESTIGE"]
    princ = [s for s in SYMS if SYMS[s][1] == "PRINCIPAL"]
    fin = [s for s in SYMS if SYMS[s][0] == "FIN"]
    agr = [s for s in SYMS if SYMS[s][2] == "AGR"]
    series = {
        "BRVM COMPOSITE": comp,
        "BRVM 30": _cap_index(px, list(SYMS), "2023-01-02", 100.0).loc["2023-01-02":],
        "BRVM PRESTIGE": _cap_index(px, prest, "2023-01-02", 100.0).loc["2023-01-02":],
        "BRVM PRINCIPAL": _cap_index(px, princ, "2023-01-02", 100.0).loc["2023-01-02":],
        "BRVM - FINANCES (base 1999)": _cap_index(px, fin, "2022-01-03", 80.0).loc[:"2025-12-31"],
        "BRVM - SERVICES FINANCIERS (base 2025)": _cap_index(px, fin, "2025-01-02", 100.0).loc["2025-01-02":],
        "BRVM - AGRICULTURE (base 1999)": _cap_index(px, agr, "2022-01-03", 150.0).loc[:"2025-12-31"],
    }
    ix_rows = []
    for name, s in series.items():
        s = s.round(2)
        y = _ytd(s)
        for d, v in s.items():
            ix_rows.append({"date": d, "index": name, "level": float(v), "change_pct": np.nan, "ytd_pct": float(y[d]),
                            "per": 10.0 if "PRESTIGE" in name else np.nan})
    ix = pd.DataFrame(ix_rows)
    rets = px.pct_change()
    n = pd.Series({s: float(SHARES_OUTSTANDING_2026[s]) for s in SYMS})
    mk = pd.DataFrame({
        "date": dates, "avg_per": 8.0 + 0.005 * k, "avg_yield_pct": 8.0 - 0.001 * k,
        "n_up": (rets > 0).sum(axis=1).to_numpy(dtype=float), "n_down": (rets < 0).sum(axis=1).to_numpy(dtype=float),
        "market_cap": (px * n).sum(axis=1).to_numpy(),
    })
    dv_rows = []
    for i, s in enumerate(SYMS):
        for y in range(2022, 2027):
            exd = dates[dates >= pd.Timestamp(f"{y}-05-12") + pd.Timedelta(days=3 * i)][0]
            prev = dates[dates < exd][-1]
            dv_rows.append({"symbol": s, "ex_date": exd, "amount": round(0.05 * px.at[prev, s], 2),
                            "payment_date": exd + pd.Timedelta(days=2), "first_seen": exd, "evidence": "test",
                            "close_before": px.at[prev, s], "yield_pct": 5.0})
    dv = pd.DataFrame(dv_rows)
    adj = eq[["date", "symbol", "close"]].copy()
    adj["adj_close"] = adj["close"]
    adj = adj.sort_values(["symbol", "date"])
    adj["ret"] = adj.groupby("symbol")["adj_close"].pct_change()
    adj["tr_index"] = adj["adj_close"]
    ca = pd.DataFrame(columns=["symbol", "date", "kind", "ratio", "confidence"])
    return {"equities": eq, "indices": ix, "market": mk, "dividends": dv, "adjusted": adj.reset_index(drop=True),
            "corporate_actions": ca, "sessions": pd.DataFrame({"date": dates})}


@pytest.fixture(scope="module")
def panel() -> dict[str, pd.DataFrame]:
    return synthetic_panel()


@pytest.fixture(scope="module")
def ev(panel) -> pd.DataFrame:
    return ie.evaluate_indices(panel, asof="2026-11-20")


def level(panel, name: str) -> pd.Series:
    ix = panel["indices"]
    return ix[ix["index"] == name].set_index("date")["level"].sort_index()


# ---------------------------------------------------------------------------
# Statistiques de base
# ---------------------------------------------------------------------------


def test_returns_ytd_vol_drawdown(panel, ev):
    s = level(panel, "BRVM COMPOSITE")
    t = s.index[-1]
    row = ev.loc["IDX:BRVM-C"]
    for m, col in ((1, "ret_1m"), (3, "ret_3m"), (6, "ret_6m"), (12, "ret_12m")):
        ref = s.loc[:t - pd.DateOffset(months=m)].iloc[-1]
        assert row[col] == pytest.approx(s.iloc[-1] / ref - 1)
    ytd_official = panel["indices"].query("index == 'BRVM COMPOSITE'").set_index("date")["ytd_pct"].iloc[-1]
    assert row["ytd"] == pytest.approx(ytd_official / 100)
    lr = np.log(s / s.shift(1)).dropna()
    assert row["vol_63"] == pytest.approx(lr.iloc[-63:].std(ddof=1) * math.sqrt(252))
    w = s[s.index > t - pd.DateOffset(months=12)]
    assert row["drawdown"] == pytest.approx(s.iloc[-1] / w.max() - 1)
    assert row["max_drawdown_12m"] == pytest.approx((w / w.cummax() - 1).min())
    assert row["level"] == pytest.approx(s.iloc[-1])
    assert row["date"] == t


def test_regime_is_market_regime(panel, ev):
    s = level(panel, "BRVM COMPOSITE")
    st = market_regime(s).iloc[-1]
    row = ev.loc["IDX:BRVM-C"]
    assert row["regime"] == st["state"]
    assert row["trend_200"] == pytest.approx(st["trend"])
    assert row["z_regime"] == ie.REGIME_SCORE[st["state"]]


def test_robust_z_and_percentile():
    h = np.arange(100, dtype=float)
    assert ie.percentile_rank(99.0, h) == 1.0
    assert ie.percentile_rank(-1.0, h) == 0.0
    z = ie.robust_z(49.5, h)
    assert z == pytest.approx(0.0)
    assert ie.robust_z(1e9, h) == ie.Z_CLIP
    assert ie.robust_z(5.0, h[:10]) is None  # historique trop court


def test_market_valuation_percentile_and_sign(ev):
    row = ev.loc["IDX:BRVM-C"]
    # PER du marché au plus haut de son historique, rendement au plus bas : cher.
    assert row["per_pct"] == pytest.approx(1.0)
    assert row["per_z"] > 0 and row["yield_z"] < 0 and row["z_valuation"] < 0
    assert row["per"] == pytest.approx(8.0 + 0.005 * (len(DATES) - 1))


def test_constituent_valuation_uses_medians(panel, ev):
    row = ev.loc["IDX:PRESTIGE"]
    eq = panel["equities"]
    last = eq[(eq["date"] == eq["date"].max()) & (eq["compartment"] == "PRESTIGE")]
    assert row["per"] == pytest.approx(last["per"].median())
    assert row["yield_pct"] == pytest.approx(last["net_yield_pct"].median())
    assert row["per_index"] == pytest.approx(10.0)  # PER publié de l'indice (information)


def test_breadth_definitions(panel, ev):
    eq = panel["equities"]
    px = eq.pivot(index="date", columns="symbol", values="close")
    ma50 = px.rolling(50, min_periods=40).mean().iloc[-1]
    ma200 = px.rolling(200, min_periods=150).mean().iloc[-1]
    row = ev.loc["IDX:BRVM-C"]
    assert row["breadth_50"] == pytest.approx(float((px.iloc[-1] > ma50).mean()))
    assert row["breadth_200"] == pytest.approx(float((px.iloc[-1] > ma200).mean()))
    mk = panel["market"].set_index("date")
    ud = mk["n_up"].iloc[-20:].sum() / max(mk["n_down"].iloc[-20:].sum(), 1.0)
    assert row["up_down_20"] == pytest.approx(ud)


# ---------------------------------------------------------------------------
# Score composite, position, confiance
# ---------------------------------------------------------------------------


def test_composite_is_weighted_mean_of_available_components(ev):
    w = ie.COMPONENT_WEIGHTS
    cols = {"tendance": "z_trend", "valorisation": "z_valuation", "largeur": "z_breadth", "regime": "z_regime",
            "notes": "z_notes"}
    for code, row in ev.iterrows():
        avail = {k: row[c] for k, c in cols.items() if row[c] is not None and np.isfinite(row[c])}
        exp = sum(w[k] * v for k, v in avail.items()) / sum(w[k] for k in avail)
        assert row["composite"] == pytest.approx(exp), code
        if row["composite"] > 0.5:
            assert row["stance"] == "SURPONDÉRER"
        elif row["composite"] < -0.5:
            assert row["stance"] == "SOUS-PONDÉRER"
        else:
            assert row["stance"] == "NEUTRE"
        assert 0.05 <= row["confidence"] <= 0.95
        for c in cols.values():
            v = row[c]
            assert v is None or not np.isfinite(v) or abs(v) <= ie.Z_CLIP + 1e-12


def test_custom_weights(panel):
    df = ie.evaluate_indices(panel, asof="2026-11-20", indices=["IDX:BRVM-C"],
                             weights={"tendance": 1.0, "valorisation": 0.0, "largeur": 0.0, "regime": 0.0, "notes": 0.0})
    assert df.loc["IDX:BRVM-C", "composite"] == pytest.approx(df.loc["IDX:BRVM-C", "z_trend"])
    with pytest.raises(ValueError):
        ie.evaluate_indices(panel, asof="2026-11-20", weights={"momentum": 1.0})


def test_stance_support_confidence_logic():
    w = ie.COMPONENT_WEIGHTS
    # Toutes les composantes négatives mais score NEUTRE (−0,45) : neutralité fragile.
    agree, margin = ie._stance_support("NEUTRE", -0.45, {"tendance": -0.4, "valorisation": -0.5}, w)
    assert agree == pytest.approx(0.0) and margin == pytest.approx(0.05)
    agree, margin = ie._stance_support("SURPONDÉRER", 1.2, {"tendance": 2.0, "valorisation": -0.4}, w)
    assert agree == pytest.approx(0.6 / 0.7) and margin == pytest.approx(0.7)


def test_reasons_are_french_numbers_and_not_guarantees(ev):
    r = ev.loc["IDX:BRVM-C", "reasons"]
    assert r[0].startswith("BRVM Composite : ") and "," in r[0] and "%" in r[0]
    assert any(x.startswith("Valorisation : PER moyen du marché") for x in r)
    assert any(x.startswith("Largeur : ") for x in r)
    assert any(x.startswith("Score composite ") and "→" in x for x in r)
    assert r[-1] == "Lecture factuelle et datée : ce score n'est pas une garantie de rendement."
    txt = " ".join(r).lower()
    assert "garanti " not in txt and "certain" not in txt


# ---------------------------------------------------------------------------
# Point-in-time
# ---------------------------------------------------------------------------


def test_point_in_time_truncated_and_modified_future(panel):
    t = "2025-09-30"
    full = ie.evaluate_indices(panel, asof=t)
    trunc = ie.evaluate_indices(ie.truncate_panels(panel, t), asof=t)
    pd.testing.assert_frame_equal(full, trunc)
    # Données postérieures à t bouleversées : l'évaluation à t ne bouge pas.
    p2 = {k: v.copy() for k, v in panel.items()}
    after = p2["equities"]["date"] > t
    p2["equities"].loc[after, ["close", "value", "per"]] *= 0.3
    p2["adjusted"].loc[p2["adjusted"]["date"] > t, "adj_close"] *= 0.3
    p2["indices"].loc[p2["indices"]["date"] > t, "level"] *= 0.3
    p2["market"].loc[p2["market"]["date"] > t, ["avg_per", "n_down"]] *= 5
    p2["dividends"] = pd.concat([p2["dividends"], pd.DataFrame([{
        "symbol": "SNTS", "ex_date": pd.Timestamp("2025-10-15"), "amount": 9999.0}])], ignore_index=True)
    mod = ie.evaluate_indices(p2, asof=t)
    pd.testing.assert_frame_equal(full, mod)
    assert full.attrs["asof"] == pd.Timestamp(t)


def test_asof_on_weekend_uses_last_session(panel):
    a = ie.evaluate_indices(panel, asof="2026-11-14", indices=["IDX:BRVM-C"])  # samedi
    b = ie.evaluate_indices(panel, asof="2026-11-13", indices=["IDX:BRVM-C"])
    assert a.loc["IDX:BRVM-C", "date"] == pd.Timestamp("2026-11-13")
    assert a.loc["IDX:BRVM-C", "composite"] == pytest.approx(b.loc["IDX:BRVM-C", "composite"])


def test_stale_and_not_yet_created_indices(panel):
    late = ie.evaluate_indices(panel, asof="2026-11-20")
    assert "IDX:SECT:AGR" not in late.index  # base 1999 arrêtée au 31/12/2025
    mid = ie.evaluate_indices(panel, asof="2025-06-30")
    assert "IDX:SECT:AGR" in mid.index
    early = ie.evaluate_indices(panel, asof="2022-06-30")
    assert "IDX:PRESTIGE" not in early.index and "IDX:BRVM-C" in early.index


# ---------------------------------------------------------------------------
# Composition
# ---------------------------------------------------------------------------


def test_compartment_and_sector_members(panel):
    eq = panel["equities"]
    m, how = ie.index_constituents("IDX:PRESTIGE", "2026-11-20", equities=eq)
    assert m == sorted(s for s in SYMS if SYMS[s][1] == "PRESTIGE") and "compartiment" in how
    m, how = ie.index_constituents("IDX:SECT:TEL", "2026-11-20", equities=eq)
    assert m == ["ORAC", "SNTS"]
    # Indice base 1999 après le passage à la classification 2025.
    m, how = ie.index_constituents("IDX:SECT:AGR", "2025-06-30", equities=eq)
    assert m == ["SOGC", "SPHC"] and "dernier BOC" in how
    assert ie.index_constituents("IDX:PRINCIPAL", "2022-06-30", equities=eq)[0] == []


def _all_symbols_equities(day: str) -> pd.DataFrame:
    syms = sorted(set(SHARES_OUTSTANDING_2026))
    return pd.DataFrame({"date": pd.Timestamp(day), "symbol": syms, "sector": "FIN", "compartment": "PRINCIPAL",
                         "value": 1.0, "volume": 1.0, "status": "traded", "close": 1.0})


def test_brvm30_official_and_reconstructed_compositions():
    t4, how4 = ie.index_constituents("IDX:BRVM-30", "2026-11-20", equities=_all_symbols_equities("2026-11-20"))
    assert t4 == sorted(ie.BRVM30_T4_2026) and len(t4) == 30 and "289-2026" in how4
    t3, how3 = ie.index_constituents("IDX:BRVM-30", "2026-08-14", equities=_all_symbols_equities("2026-08-14"))
    assert len(t3) == 30 and "T3-2026 reconstituée" in how3
    assert set(t4) - set(t3) == {"LNBB", "ONTBF", "SHEC", "SLBC"}
    assert set(t3) - set(t4) == {"NEIC", "SCRC", "SEMC", "STAC"}
    # Au-delà du T4-2026 (janvier 2027) : la composition officielle n'est plus en vigueur.
    _, how = ie.index_constituents("IDX:BRVM-30", "2027-01-15", equities=_all_symbols_equities("2027-01-15"))
    assert how.startswith("approximation")


def test_brvm30_approximation_rank_and_reason(panel):
    eq = panel["equities"]
    listed = sorted(SYMS)
    top3 = ie._liquidity_rank(eq, listed, pd.Timestamp("2025-01-01"), pd.Timestamp("2025-03-31"), 3)
    w = eq[(eq["date"] >= "2025-01-01") & (eq["date"] <= "2025-03-31")].groupby("symbol")
    score = w["value"].sum().rank(ascending=False) + w["volume"].sum().rank(ascending=False)
    assert set(top3) == set(score.sort_values().index[:3])
    m, how = ie.index_constituents("IDX:BRVM-30", "2025-06-30", equities=eq)
    assert how.startswith("approximation") and "01/01/2025 au 31/03/2025" in how
    m2, how2 = ie.index_constituents("IDX:BRVM-30", "2025-06-30", equities=eq, brvm30_method="valeur_6m")
    assert "6 mois" in how2
    row = ie.evaluate_indices(panel, asof="2025-06-30", indices=["BRVM 30"]).loc["IDX:BRVM-30"]
    assert row["approx_composition"] and any("approximation" in r for r in row["reasons"])


def test_brvm30_composition_from_index_change_note(tmp_path, panel):
    st = NoteStore(tmp_path / "notes")
    n = Note(title="Avis : composition de l'indice BRVM 30", text="composition", targets=["IDX:BRVM-30"],
             event_type="INDEX_CHANGE", published_at="2025-04-01 07:00", created_at="2025-04-01 07:00",
             author="auto", source="brvm_list", url="http://exemple/avis",
             analysis={"targets": ["IDX:BRVM-30"], "event_type": "INDEX_CHANGE", "score": 0.0,
                       "extracted": {"constituents": ["SNTS", "ORAC", "SGBC"]}})
    st.add(n, now="2025-04-01 07:00")
    m, how = ie.index_constituents("IDX:BRVM-30", "2025-06-30", equities=panel["equities"], store=st)
    assert m == ["ORAC", "SGBC", "SNTS"] and "INDEX_CHANGE" in how
    m0, how0 = ie.index_constituents("IDX:BRVM-30", "2025-03-31", equities=panel["equities"], store=st)
    assert how0.startswith("approximation")  # la note n'était pas encore connue


# ---------------------------------------------------------------------------
# Séries : chaînage et Total Return
# ---------------------------------------------------------------------------


def test_sector_series_chained_across_bases(panel):
    ctx = ie._Ctx(panel, "2025-06-30")
    s, info = ie.level_series("IDX:SECT:FIN", ctx)
    assert info["chained"] and info["name"] == "BRVM - SERVICES FINANCIERS (base 2025)"
    new = level(panel, "BRVM - SERVICES FINANCIERS (base 2025)").loc[:"2025-06-30"]
    old = level(panel, "BRVM - FINANCES (base 1999)")
    assert s.loc["2025-01-02":].equals(new)
    ratio = new.iloc[0] / old.loc["2025-01-02"]
    assert s.loc["2024-06-28"] == pytest.approx(old.loc["2024-06-28"] * ratio)
    row = ie.evaluate_indices(panel, asof="2025-06-30", indices=["IDX:SECT:FIN"]).loc["IDX:SECT:FIN"]
    assert np.isfinite(row["ret_12m"]) and any("chaînée" in r for r in row["reasons"])


def test_total_return_backward_chaining(panel):
    p = {k: v.copy() for k, v in panel.items()}
    comp = level(p, "BRVM COMPOSITE")
    tr = (comp.loc["2026-01-02":] / comp.loc["2026-01-02"] * 140.0).round(4)
    p["indices"] = pd.concat([p["indices"], pd.DataFrame({"date": tr.index, "index": ie.TR_NAME, "level": tr.values,
                                                          "ytd_pct": np.nan, "per": np.nan})], ignore_index=True)
    ctx = ie._Ctx(p, "2026-11-20")
    s, info = ie.level_series("IDX:BRVM-C-TR", ctx)
    assert info["reconstructed"] and s.index[0] < pd.Timestamp("2026-01-02")
    assert s.loc["2026-01-02":].equals(tr)
    # Un jour de détachement de 2025 : r_TR = r_Composite + N·D / Cap(t−1).
    dv = p["dividends"]
    row = dv[(dv["symbol"] == "SNTS") & (dv["ex_date"].dt.year == 2025)].iloc[0]
    d = pd.Timestamp(row["ex_date"])
    others = dv[(dv["ex_date"] == d) & (dv["symbol"] != "SNTS")]
    assert others.empty
    prev = comp.index[comp.index.get_loc(d) - 1]
    mc = p["market"].set_index("date")["market_cap"]
    exp = comp[d] / comp[prev] - 1 + SHARES_OUTSTANDING_2026["SNTS"] * row["amount"] / mc[prev]
    assert s[d] / s[prev] - 1 == pytest.approx(exp, rel=1e-9)
    ev = ie.evaluate_indices(p, asof="2026-11-20", indices=["IDX:BRVM-C-TR"])
    assert "IDX:BRVM-C-TR" in ev.index and np.isfinite(ev.loc["IDX:BRVM-C-TR", "ret_12m"])


# ---------------------------------------------------------------------------
# Saison des dividendes
# ---------------------------------------------------------------------------


def test_dividend_season_expected_and_mechanical_drop(panel):
    row = ie.evaluate_indices(panel, asof="2026-04-30", indices=["IDX:BRVM-C"]).loc["IDX:BRVM-C"]
    assert row["div_payers"] == len(SYMS) and row["div_expected_60d"] == len(SYMS)
    assert row["div_season_share"] == pytest.approx(1.0)
    ctx = ie._Ctx(panel, "2026-04-30")
    w = ctx.cap_weights(sorted(SYMS))
    dv = panel["dividends"]
    last = dv[dv["ex_date"].dt.year == 2025].set_index("symbol")["amount"]
    close = ctx.close.iloc[-1]
    exp = float(sum(w[s] * last[s] / close[s] for s in SYMS))
    assert row["div_yield_60d"] == pytest.approx(exp)
    assert any("baisse mécanique" in r for r in row["reasons"])
    late = ie.evaluate_indices(panel, asof="2026-11-20", indices=["IDX:BRVM-C"]).loc["IDX:BRVM-C"]
    assert late["div_expected_60d"] == 0 and late["div_yield_60d"] == 0.0


def test_dividend_amount_adjusted_for_later_split(panel):
    p = {k: v.copy() for k, v in panel.items()}
    p["corporate_actions"] = pd.DataFrame([{"symbol": "SNTS", "date": pd.Timestamp("2025-10-27"), "kind": "split",
                                            "ratio": 10.0, "confidence": "high"}])
    ctx = ie._Ctx(p, "2026-04-30")
    tab = ie.expected_detachments(ctx, ["SNTS"], ctx.asof).set_index("symbol")
    raw = p["dividends"].query("symbol == 'SNTS' and ex_date.dt.year == 2025")["amount"].iloc[0]
    assert tab.at["SNTS", "div_net"] == pytest.approx(raw / 10.0)
    assert tab.at["SNTS", "expected_ex"].month == 5 and tab.at["SNTS", "in_window"]


def test_announced_dividend_from_note(tmp_path, panel):
    st = NoteStore(tmp_path / "notes")
    n = Note(title="Paiement de dividendes SGBC", text="avis", targets=["SGBC"], event_type="DIV_NOTICE",
             published_at="2026-11-02 18:00", created_at="2026-11-02 18:00", author="auto", source="brvm_list",
             url="http://exemple/div",
             analysis={"targets": ["SGBC"], "event_type": "DIV_NOTICE", "score": 0.3, "confidence": 0.8,
                       "extracted": {"ex_date": "2026-12-10", "div_net": 1500.0, "pay_date": "2026-12-14"}})
    st.add(n, now="2026-11-02 18:00")
    row = ie.evaluate_indices(panel, store=st, asof="2026-11-20", indices=["IDX:BRVM-C"]).loc["IDX:BRVM-C"]
    assert row["div_expected_60d"] == 1
    d = ie.index_dossier("IDX:BRVM-C", panel, store=st, asof="2026-11-20")
    ev = [e for e in d["calendar"] if e["symbol"] == "SGBC"]
    assert {e["type"] for e in ev} >= {"détachement", "paiement du dividende"}
    assert any(e["source"] == "annoncé (note)" for e in ev)


# ---------------------------------------------------------------------------
# Composante « notes »
# ---------------------------------------------------------------------------


def test_notes_component_index_plus_value_weighted_constituents(tmp_path, panel):
    st = NoteStore(tmp_path / "notes")

    def add(title, targets, score, author="analyste"):
        n = Note(title=title, text=title, targets=targets, published_at="2026-11-20 07:00",
                 created_at="2026-11-20 07:00", author=author, source="manual" if author == "analyste" else "url",
                 url="" if author == "analyste" else f"http://exemple/{title}",
                 analysis={"targets": targets, "event_type": "MANUAL", "score": score, "confidence": 0.7})
        st.add(n, now="2026-11-20 07:00")

    add("composite", ["IDX:BRVM-C"], 0.4)
    add("sonatel", ["SNTS"], -0.6, author="auto")
    row = ie.evaluate_indices(panel, store=st, asof="2026-11-20", indices=["IDX:BRVM-C", "IDX:PRESTIGE"])
    eq = panel["equities"]
    v6 = eq[eq["date"] > pd.Timestamp("2026-11-20") - pd.DateOffset(months=6)].groupby("symbol")["value"].sum()
    c = row.loc["IDX:BRVM-C"]
    # Note automatique : pondérée par la confiance de son analyse (0,7) ; note de l'analyste : en entier.
    exp_const = -0.6 * 0.7 * v6["SNTS"] / v6.sum()
    assert c["notes_n"] == 2
    assert c["notes_score"] == pytest.approx(0.4 + exp_const)
    assert c["z_notes"] == pytest.approx(np.clip((0.4 + exp_const) / ie.NOTES_SCALE, -3, 3))
    # Prestige : la note du Composite se propage (0,25) aux constituants, la note SNTS compte en direct.
    p = row.loc["IDX:PRESTIGE"]
    prest = [s for s in SYMS if SYMS[s][1] == "PRESTIGE"]
    s_i = pd.Series({s: 0.25 * 0.4 for s in prest})
    s_i["SNTS"] += -0.6 * 0.7
    exp_p = float((v6[prest] * s_i).sum() / v6[prest].sum())
    assert p["notes_score"] == pytest.approx(exp_p)
    no = ie.evaluate_indices(panel, asof="2026-11-20", indices=["IDX:BRVM-C"]).loc["IDX:BRVM-C"]
    assert no["z_notes"] is None or not np.isfinite(no["z_notes"])
    assert any("aucune note" in r for r in no["reasons"])


def test_regression_zero_score_notes_do_not_dilute_the_composite(tmp_path, panel):
    """Vérification finale : des notes de score nul (avis administratifs propagés au marché)
    rendaient la composante « notes » disponible avec z = 0 ; la renormalisation des poids
    rapprochait le composite de 0 et pouvait faire passer l'indice à NEUTRE sans aucune
    information directionnelle."""
    base = ie.evaluate_indices(panel, asof="2026-11-20", indices=["IDX:BRVM-C"]).loc["IDX:BRVM-C"]
    st = NoteStore(tmp_path / "notes")
    for i, tg in enumerate((["MARCHE"], ["SNTS"], ["IDX:BRVM-C"])):
        st.add(Note(title=f"Avis administratif {i}", text="Homologation des tarifs d'une SGO.", targets=tg,
                    published_at="2026-11-19 07:00", created_at="2026-11-19 07:00", author="auto", source="url",
                    url=f"http://exemple/avis{i}", analysis={"targets": tg, "event_type": "REGULATOR", "score": 0.0,
                                                             "confidence": 0.5}), now="2026-11-19 07:00")
    row = ie.evaluate_indices(panel, store=st, asof="2026-11-20", indices=["IDX:BRVM-C"]).loc["IDX:BRVM-C"]
    assert row["notes_n"] == 3
    for k in ("z_notes", "notes_score"):
        assert row[k] is None or not np.isfinite(row[k])
    assert row["composite"] == pytest.approx(base["composite"]) and row["stance"] == base["stance"]
    assert any("score nul" in r for r in row["reasons"])


# ---------------------------------------------------------------------------
# Dossier
# ---------------------------------------------------------------------------


def test_dossier_contributions_reconcile_cap_weighted_composite(panel):
    d = ie.index_dossier("BRVM Composite", panel, asof="2026-11-20")
    for k in ("1m", "3m", "12m", "ytd"):
        c = d["contributions"][k]
        assert c["index_return"] == pytest.approx(c["sum_contributions"], abs=2e-4), k  # niveaux arrondis à 0,01
    cons = d["constituents"]
    assert set(cons.index) == set(SYMS) and cons["weight"].sum() == pytest.approx(1.0)
    assert {"close", "ret_12m", "per", "net_yield_pct", "value_6m", "flags", "veto", "country"} <= set(cons.columns)
    assert d["top_contributors"]["contribution"].is_monotonic_decreasing


def test_dossier_prestige_weights_are_capped(panel):
    d = ie.index_dossier("IDX:PRESTIGE", panel, asof="2026-11-20")
    assert d["constituents"]["weight"].max() <= ie.WEIGHT_CAPS["IDX:PRESTIGE"] + 1e-9 or len(d["constituents"]) * 0.2 < 1


def test_dossier_keys_calendar_and_change_my_mind(panel, tmp_path):
    st = NoteStore(tmp_path / "notes")
    n = Note(title="Alerte", text="alerte", targets=["BOAN"], event_type="PROFIT_WARNING",
             published_at="2026-11-16 07:00", created_at="2026-11-16 07:00", author="auto", source="url",
             url="http://exemple/pw", analysis={"targets": ["BOAN"], "event_type": "PROFIT_WARNING", "score": -0.7,
                                                "risk_flags": ["R9"], "confidence": 0.8})
    st.add(n, now="2026-11-16 07:00")
    d = ie.index_dossier("IDX:PRINCIPAL", panel, store=st, asof="2026-04-15")
    assert d["asof"] == pd.Timestamp("2026-04-15")
    for k in ("index", "label", "evaluation", "constituents", "contributions", "recent_notes", "calendar",
              "change_my_mind", "overlays", "reasons", "composition"):
        assert k in d
    dates = [e["date"] for e in d["calendar"]]
    assert dates == sorted(dates)
    assert any(e["type"] == "date limite" and e["date"] == pd.Timestamp("2026-04-30") for e in d["calendar"])
    assert any(e["type"] == "détachement" for e in d["calendar"])
    cmm = d["change_my_mind"]
    assert any(x.startswith("Passage à ") for x in cmm) and any("moyenne 200 séances" in x for x in cmm)
    assert d["recent_notes"] == []  # la note du 16/11/2026 est postérieure à asof
    d2 = ie.index_dossier("IDX:PRINCIPAL", panel, store=st, asof="2026-11-20")
    assert d2["recent_notes"] and d2["recent_notes"][0]["note_id"] == n.note_id
    assert d2["constituents"].loc["BOAN", "flags"] == ["R9"] and d2["constituents"].loc["BOAN", "veto"]
    assert any(r.startswith("Filtres actifs sur les constituants") for r in d2["reasons"])
    with pytest.raises(ValueError):
        ie.index_dossier("SNTS", panel)


# ---------------------------------------------------------------------------
# Panel réel (cohérence avec les BOC)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def real():
    if not HAS_REAL:
        pytest.skip("panel réel absent")
    return ie.load_panels(REAL_PANEL)


def test_real_panel_matches_boc_20261120(real):
    df = ie.evaluate_indices(real, asof="2026-11-20")
    c = df.loc["IDX:BRVM-C"]
    assert c["level"] == pytest.approx(492.89) and c["ytd"] == pytest.approx(0.4256)
    assert c["per"] == pytest.approx(15.79) and c["yield_pct"] == pytest.approx(7.12)
    assert c["n_constituents"] == 48
    assert df.loc["IDX:BRVM-30", "level"] == pytest.approx(238.73)
    assert df.loc["IDX:BRVM-30", "ytd"] == pytest.approx(0.4361)
    assert df.loc["IDX:BRVM-C-TR", "level"] == pytest.approx(198.63)
    assert df.loc["IDX:PRESTIGE", "n_constituents"] == 12 and df.loc["IDX:PRINCIPAL", "n_constituents"] == 36
    assert "289-2026" in df.loc["IDX:BRVM-30", "composition"]
    assert "IDX:SECT:AGR" not in df.index
    assert set(df["stance"]) <= set(ie.STANCES)


def test_real_panel_past_dates_match_boc(real):
    a = ie.evaluate_indices(real, asof="2025-06-30", indices=["IDX:BRVM-C", "IDX:BRVM-30", "IDX:PRESTIGE"])
    assert a.loc["IDX:BRVM-C", "level"] == pytest.approx(312.04)
    assert a.loc["IDX:BRVM-C", "per"] == pytest.approx(14.12) and a.loc["IDX:BRVM-C", "yield_pct"] == pytest.approx(6.99)
    assert a.loc["IDX:BRVM-30", "level"] == pytest.approx(155.83) and a.loc["IDX:PRESTIGE", "level"] == pytest.approx(132.51)
    b = ie.evaluate_indices(real, asof="2022-12-30", indices=["IDX:BRVM-C", "IDX:BRVM-10"])
    assert b.loc["IDX:BRVM-C", "level"] == pytest.approx(203.22) and b.loc["IDX:BRVM-10", "level"] == pytest.approx(165.58)
    assert b.loc["IDX:BRVM-C", "per"] == pytest.approx(7.96) and b.loc["IDX:BRVM-C", "yield_pct"] == pytest.approx(7.51)


def test_real_panel_point_in_time(real):
    t = "2026-03-31"
    full = ie.evaluate_indices(real, asof=t)
    trunc = ie.evaluate_indices(ie.truncate_panels(real, t), asof=t)
    pd.testing.assert_frame_equal(full, trunc)


def test_real_prestige_cap_rule_reconciles(real):
    d = ie.index_dossier("IDX:PRESTIGE", real, asof="2026-11-20")
    assert abs(d["contributions"]["ytd"]["gap"]) < 0.005
    d30 = ie.index_dossier("IDX:BRVM-30", real, asof="2026-11-20")
    assert abs(d30["contributions"]["1m"]["gap"]) < 0.002  # composition T4-2026 en vigueur sur le mois
