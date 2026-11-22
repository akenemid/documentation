"""Tests du modèle BRVM Alpha v1 (``brvm_alpha/strategy/alpha.py``).

Données synthétiques pour les invariants, et panel réel (``data/panel``) pour les contrôles
de forme du §12.3 (n° 5 et n° 6) et un essai de fumée **sur S0 seulement**. Aucun backtest,
aucune performance ni aucun IC n'est calculé sur l'échantillon vierge S1
(2017-01-02 → 2022-11-16) : le seul contrôle qui touche 2020 porte sur la taille de
l'univers (contrôle de forme autorisé).
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from brvm_alpha import reference
from brvm_alpha.backtest import engine
from brvm_alpha.backtest.engine import Backtester
from brvm_alpha.config import Constraints, CostModel, ExecutionModel
from brvm_alpha.strategy import VARIANTS, BrvmAlpha, build_panels, notes_available
from brvm_alpha.strategy.alpha import COUNTRY_RULES

ROOT = Path(__file__).resolve().parents[1]
PANEL_DIR = ROOT / "data" / "panel"
HAS_PANEL = (PANEL_DIR / "equities.parquet").exists() and (PANEL_DIR / "adjusted_prices.parquet").exists()
S0_START = "2022-11-17"
S1_END = pd.Timestamp("2022-11-16")

SYMS = [s for s in sorted(reference.SECTOR_2025) if s not in reference.DELISTED_SYMBOLS][:32]


def make_panels(n_days: int = 430, seed: int = 0, symbols: list[str] | None = None) -> dict:
    """Panel synthétique au format de :func:`build_panels` (sans divisions)."""
    rng = np.random.default_rng(seed)
    syms = list(symbols or SYMS)
    n = len(syms)
    dates = pd.bdate_range("2023-01-02", periods=n_days)
    mu = rng.normal(0.0003, 0.0004, n)
    sig = rng.uniform(0.006, 0.02, n)
    r = rng.normal(mu, sig, size=(n_days, n))
    p_trade = rng.uniform(0.75, 1.0, n)
    p_trade[:2] = 0.30  # deux titres peu échangés (U3)
    traded = rng.random((n_days, n)) < p_trade
    r = np.where(traded, r, 0.0)
    close = 1000.0 * rng.uniform(0.5, 20.0, n) * np.cumprod(1.0 + r, axis=0)
    tick = np.where(close < 100, 1.0, 5.0)
    close = np.maximum(np.round(close / tick) * tick, 1.0)
    vol = np.where(traded, rng.integers(200, 5000, size=(n_days, n)), 0).astype(float)
    vol[:, 2] = np.where(traded[:, 2], 3.0, 0.0)  # titre illiquide (U5)
    value = vol * close
    status = np.where(traded, "traded", "not_traded").astype(object)
    status[300:320, 3] = "suspended"  # suspension (U1, R1)
    vol[300:320, 3] = 0.0
    value[300:320, 3] = 0.0
    idx = pd.DatetimeIndex(dates, name="date")
    cols = pd.Index(syms, name="symbol")
    C = pd.DataFrame(close, idx, cols)
    per = pd.DataFrame(np.tile(rng.uniform(4.0, 30.0, n), (n_days, 1)), idx, cols)
    per.iloc[:, 5] = -3.0  # titre en perte
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
    bid = C * (1.0 - half)
    ask = C * (1.0 + half)
    divt = pd.DataFrame(div_rows)
    dividend_net = pd.DataFrame(0.0, idx, cols)
    for rec in div_rows:
        dividend_net.loc[rec["ex_date"], rec["symbol"]] = rec["amount"]
    return {
        "close": C.copy(), "adj_factor": pd.DataFrame(1.0, idx, cols), "close_raw": C, "close_adj": C.copy(),
        "tr_index": tr_index, "volume": pd.DataFrame(vol, idx, cols), "value": pd.DataFrame(value, idx, cols),
        "status": pd.DataFrame(status, idx, cols), "per": per, "net_yield_pct": net_yield,
        "last_div_net": last_div_net, "last_div_date": last_div_date, "ref_price": C.shift(1),
        "flags": flags, "bid": bid, "ask": ask, "shares": shares, "market": market, "market_tr": market_tr,
        "dividends_table": divt, "dividend_net": dividend_net,
    }


@pytest.fixture(scope="module")
def synth() -> dict:
    return make_panels()


@pytest.fixture(scope="module")
def month_ends(synth) -> list[pd.Timestamp]:
    idx = synth["close"].index
    me = engine.rebalance_dates(idx, "M")
    return [d for d in me if d >= idx[300]]


def model(**kw) -> BrvmAlpha:
    kw.setdefault("notes", None)
    return BrvmAlpha(**kw)


# ---------------------------------------------------------------------------
# Paramètres et variantes
# ---------------------------------------------------------------------------


def test_variants_and_defaults():
    assert VARIANTS == ("A", "B", "C", "D", "E", "F", "G", "H")
    m = model()
    assert m.capital == 10_000_000
    assert m.mdv_floor() == 500_000
    assert model(capital=1e9).mdv_floor() == 50_000_000
    assert m.portfolio_params["weighting"] == "equal"
    assert model(variant="g").portfolio_params["weighting"] == "hrp_tilt"
    assert model(variant="H").portfolio_params["weighting"] == "mv_alpha"
    assert model(variant="D").spec.sector_neutral == ("ep", "dy")
    with pytest.raises(ValueError):
        BrvmAlpha(variant="Z", notes=None)
    # Surcharges du YAML : fusion profonde et validation par settings.
    m2 = model(params={"portfolio": {"max_weight": 0.08}})
    assert m2.portfolio_params["max_weight"] == pytest.approx(0.08)
    assert m.fingerprint != m2.fingerprint


# ---------------------------------------------------------------------------
# Univers
# ---------------------------------------------------------------------------


def test_universe_synthetic(synth):
    t = synth["close"].index[310]
    u = model().universe(t, synth)
    assert {"eligible", "reason", "codes", "mdv63", "traded_fraction_120", "free_float", "low_liquidity",
            "spread_120", "wide_spread", "liquidity_level"} <= set(u.columns)
    s_illiq, s_susp, s_stale = SYMS[2], SYMS[3], SYMS[0]
    assert not u.loc[s_illiq, "eligible"] and "U5" in u.loc[s_illiq, "codes"]
    assert not u.loc[s_susp, "eligible"] and u.loc[s_susp, "codes"].startswith("U1")
    assert "U3" in u.loc[s_stale, "codes"]
    assert u.attrs["mode"] == "selection" and u.attrs["n_eligible"] >= 15
    assert (u.loc[u["eligible"], "reason"] == "").all()
    # Reprise de cotation : exclu pendant 5 séances après la reprise (R1), puis réadmis.
    idx = synth["close"].index
    assert not model().universe(idx[322], synth).loc[s_susp, "eligible"]
    assert model().universe(idx[326], synth).loc[s_susp, "eligible"]


def test_universe_depends_on_capital(synth):
    t = synth["close"].index[400]
    small = model().universe(t, synth)
    big = model(capital=5e10).universe(t, synth)
    assert big.attrs["n_eligible"] < small.attrs["n_eligible"]
    assert big.attrs["mdv_floor"] == pytest.approx(0.05 * 5e10)
    assert big.attrs["mode"] in ("repli", "vide")


# ---------------------------------------------------------------------------
# Poids : invariants, point-in-time, déterminisme
# ---------------------------------------------------------------------------


def _check_weights(w: pd.Series, dec) -> None:
    assert (w >= 0).all()
    assert w.sum() <= 0.98 + 1e-9
    caps = (dec.diagnostics.get("portfolio") or {}).get("caps", {})
    upper = caps.get("upper")
    if upper is not None:
        pos = w[w > 0]
        assert (pos <= upper.reindex(pos.index).fillna(0.0) + 1e-9).all()
    viol = (dec.diagnostics.get("portfolio") or {}).get("violations", {})
    assert all(v <= 1e-9 for v in viol.values())


def test_target_weights_invariants(synth, month_ends):
    m = model()
    held = None
    for t in month_ends:
        w = m.target_weights(t, synth, held=held)
        dec = m.last_decision
        _check_weights(w, dec)
        assert dec.diagnostics["mode"] == "selection"
        n = int((w > 0).sum())
        assert 12 <= n <= 20
        held = w[w > 0]


def test_point_in_time_truncated_panel(synth):
    t = synth["close"].index[350]
    full = model().target_weights(t, synth)
    trunc = model().target_weights(t, engine.truncate_asof(synth, t))
    pd.testing.assert_series_equal(full, trunc)
    sig_full = model().signals(t, synth)["composite"]
    sig_trunc = model().signals(t, engine.truncate_asof(synth, t))["composite"]
    pd.testing.assert_series_equal(sig_full, sig_trunc)


def test_point_in_time_future_changes_ignored(synth):
    """Modifier tout ce qui suit t (cours, dividendes, statuts, TR de marché) ne change rien en t."""
    idx = synth["close"].index
    t = idx[340]
    alt = {k: (v.copy() if hasattr(v, "copy") else v) for k, v in synth.items()}
    fut = alt["close"].index > t
    for k in ("close", "close_raw", "close_adj", "tr_index", "value"):
        alt[k].loc[fut] = alt[k].loc[fut] * 3.0
    alt["status"].loc[fut] = "suspended"
    alt["market_tr"] = alt["market_tr"].where(alt["market_tr"].index <= t, 1.0)
    extra = pd.DataFrame([{"symbol": SYMS[10], "ex_date": idx[345], "amount": 9999.0, "date": idx[344]}])
    alt["dividends_table"] = pd.concat([alt["dividends_table"], extra], ignore_index=True)
    pd.testing.assert_series_equal(model().target_weights(t, synth), model().target_weights(t, alt))


def test_determinism(synth):
    t = synth["close"].index[380]
    a = model().decide(t, synth)
    b = model().decide(t, synth)
    pd.testing.assert_series_equal(a.weights, b.weights)
    pd.testing.assert_frame_equal(a.score, b.score)
    assert model().decide(t, synth) is not None


def test_fallback_mode_equal_weights(synth):
    t = synth["close"].index[400]
    u = model().universe(t, synth)
    mdv = u.loc[u["eligible"], "mdv63"].sort_values(ascending=False)
    m = model(capital=float(mdv.iloc[7]) / 0.05)  # plancher U5 = 8e MDV63 : environ 8 éligibles
    dec = m.decide(t, synth)
    n_el = int(dec.universe["eligible"].sum())
    assert 0 < n_el < 15
    assert dec.diagnostics["mode"] == "repli"
    w = dec.weights[dec.weights > 0]
    _check_weights(dec.weights, dec)
    assert set(w.index) <= set(dec.universe.index[dec.universe["eligible"]])
    assert any("repli" in msg for msg in dec.messages)


# ---------------------------------------------------------------------------
# Signaux, score, S2, explication
# ---------------------------------------------------------------------------


def test_signals_keys(synth):
    t = synth["close"].index[380]
    s = model().signals(t, synth)
    for k in ("EP", "DY", "MOM6_1", "LOWVOL", "QUAL", "composite", "S2", "MOM3_1", "MOM6_0", "MOM12_1",
              "MOM12_7", "AMIHUD", "composite_raw", "tilt", "z_EP"):
        assert k in s, k
        assert isinstance(s[k], pd.Series)
    loss = SYMS[5]
    assert s["EP"][loss] == 0.0  # PER négatif : rang minimal
    comp = s["composite"].dropna()
    assert len(comp) >= 15
    assert comp.abs().max() <= 3.0 + 1e-12


def test_s2_malus_only_for_new_buys(synth):
    idx = synth["close"].index
    t = idx[390]
    sym = SYMS[12]
    p = dict(synth)
    extra = pd.DataFrame([{"symbol": sym, "ex_date": idx[386], "amount": 1.0, "date": idx[385]}])
    p["dividends_table"] = pd.concat([synth["dividends_table"], extra], ignore_index=True)
    m = model()
    dec = m.decide(t, p)
    assert dec.signals["S2"][sym] == pytest.approx(-0.5)
    assert dec.diagnostics["s2"][sym]["sessions_since_ex"] == 4
    assert dec.score.loc[sym, "malus"] == pytest.approx(-0.5)
    held = pd.Series({sym: 0.05})
    dec_h = model().decide(t, p, held=held)
    assert dec_h.score.loc[sym, "malus"] == 0.0
    assert dec_h.score.loc[sym, "with_malus"] >= dec.score.loc[sym, "with_malus"]
    # 20 séances après le détachement, le malus a disparu.
    assert model().decide(idx[386 + 20], p).signals["S2"][sym] == 0.0


def test_explain_complete(synth):
    t = synth["close"].index[380]
    m = model()
    w = m.target_weights(t, synth)
    sym = w.idxmax()
    ex = m.explain(t, synth, sym)
    for k in ("symbol", "asof", "variant", "eligible", "universe", "blocks", "score", "weight", "caps",
              "risk_flags", "notes", "valuation", "momentum", "text", "banner", "construction_reason"):
        assert k in ex, k
    assert ex["weight"] == pytest.approx(w[sym])
    contrib = sum(b["contribution"] for b in ex["blocks"].values() if not b["research_only"])
    assert contrib == pytest.approx(ex["score"]["raw"], abs=1e-9)
    assert set(ex["blocks"]) >= {"EP", "DY", "MOM6_1", "LOWVOL", "QUAL"}
    assert ex["score"]["rank"] >= 1 and ex["score"]["n_ranked"] >= 15
    v = ex["valuation"]
    assert v["used_in_score"] is False and 0.0 < v["cost_of_equity"] < 0.5
    assert "n'entre pas dans le score" in v["note"]
    assert ex["caps"]["upper"] >= ex["weight"] - 1e-9
    assert "variante A" in ex["text"] and "Aucun gain n'est garanti" in ex["text"]
    # Titre non éligible : motif en français.
    ex2 = m.explain(t, synth, SYMS[2])
    assert ex2["eligible"] is False and "U5" in ex2["text"]
    with pytest.raises(KeyError):
        m.explain(t, synth, "XXXX")


# ---------------------------------------------------------------------------
# Filtres de risque et règles pays
# ---------------------------------------------------------------------------


def test_panel_risk_flags(synth):
    idx = synth["close"].index
    t = idx[380]
    p = dict(synth)
    flags = synth["flags"].copy()
    flags.loc[t, SYMS[7]] = "VAL-T"
    flags.loc[t, SYMS[8]] = "(EX-D)"
    p["flags"] = flags
    p["corporate_actions"] = pd.DataFrame([{"date": idx[378], "symbol": SYMS[9], "kind": "unexplained_jump",
                                            "ratio": np.nan, "confidence": "low"}])
    risk = model().risk_flags(t, p, notes=None)
    assert risk.loc[SYMS[7], "R8"] and not risk.loc[SYMS[7], "R8_fail"]
    assert risk.loc[SYMS[8], "R5"] and risk.loc[SYMS[8], "block_buys"]
    assert risk.loc[SYMS[9], "R8_fail"] and risk.loc[SYMS[9], "block_buys"]
    r1 = model().risk_flags(idx[310], synth, notes=None)
    assert r1.loc[SYMS[3], "R1"] and r1.loc[SYMS[3], "block_buys"]
    dec = model().decide(t, p)
    assert dec.weights[SYMS[9]] == 0.0  # contrôle de facteur échoué : signaux bloqués
    assert dec.weights[SYMS[8]] == 0.0  # R5 : pas d'achat


def test_country_rule_severe(synth):
    idx = synth["close"].index
    t = idx[380]
    sn = [s for s in SYMS if reference.country_of(s) == "SN"]
    ci = [s for s in SYMS if reference.country_of(s) == "CI"]
    assert sn and ci
    base = model().decide(t, synth)
    held = base.weights[base.weights > 0]
    ev = [{"date": idx[378], "country": "SN", "rule": "severe", "label": "test"}]
    m = model(country_events=ev)
    dec = m.decide(t, synth, held=held)
    st = dec.diagnostics["country_rules"]["SN"]
    assert st["rule"] == "severe" and st["no_buy"]
    _check_weights(dec.weights, dec)
    elig = [s for s in dec.universe.index if dec.universe.loc[s, "eligible"]]
    u_c = sum(1 for s in elig if reference.country_of(s) == "SN") / len(elig)
    w_sn = float(dec.weights.reindex(sn).sum())
    assert w_sn <= 0.25 * u_c + 1e-9
    for s in sn:  # aucun achat : un titre SN non détenu reste à 0
        if s not in held.index:
            assert dec.weights[s] == 0.0
    assert all(dec.risk.loc[s, "block_buys"] for s in sn)
    # Moteur : premier jour au plancher (choc sévère, §7.1.8).
    shocks = m.engine_country_shocks()
    assert list(shocks.columns) == ["country", "date", "sessions"]
    # Après 60 séances : retour progressif sur 20 séances (achats de nouveau permis), puis fin de la règle.
    ev2 = [{"date": idx[320], "country": "SN", "rule": "severe"}]
    ramp = model(country_events=ev2).decide(idx[320 + 70], synth).diagnostics["country_rules"]["SN"]
    assert ramp["ramp"] is not None and not ramp["no_buy"]
    assert "SN" not in model(country_events=ev2).decide(idx[320 + 81], synth).diagnostics["country_rules"]
    with pytest.raises(ValueError):
        model(country_events=[{"date": t, "country": "SN", "rule": "inconnue"}])
    assert set(COUNTRY_RULES) >= {"severe", "coup", "relief", "election", "downgrade", "bond_discount"}


def test_country_rule_downgrade_multiplier(synth):
    idx = synth["close"].index
    t = idx[380]
    ev = [{"date": idx[370], "country": "SN", "rule": "downgrade"}]
    dec = model(country_events=ev).decide(t, synth)
    assert dec.diagnostics["country_rules"]["SN"]["rule"] == "downgrade"
    caps = dec.diagnostics["portfolio"]["caps"]["country"]
    base_caps = model().decide(t, synth).diagnostics["portfolio"]["caps"]["country"]
    assert caps["SN"] == pytest.approx(0.75 * base_caps["SN"])


# ---------------------------------------------------------------------------
# Notes de l'analyste
# ---------------------------------------------------------------------------


def test_without_notes_module(monkeypatch, synth):
    t = synth["close"].index[380]
    ref_w = model().target_weights(t, synth)
    monkeypatch.setitem(sys.modules, "brvm_alpha.notes.signals", None)
    ok, why = notes_available()
    assert not ok and "indisponible" in why
    m = BrvmAlpha(notes="auto")
    w = m.target_weights(t, synth)
    pd.testing.assert_series_equal(w, ref_w)
    assert any("indisponible" in msg for msg in m.last_decision.messages)
    ex = m.explain(t, synth, w.idxmax())
    assert ex["notes"]["available"] is False
    assert "indisponible" in ex["notes"]["message"]
    risk = m.risk_flags(t, synth)
    assert not risk["veto"].any() and (risk["tilt"] == 0).all()


def test_notes_veto_and_tilt(tmp_path, synth):
    pytest.importorskip("brvm_alpha.notes.signals")
    from brvm_alpha.notes.model import Note
    from brvm_alpha.notes.store import NoteStore

    idx = synth["close"].index
    t = idx[380]
    base = model().decide(t, synth)
    ranked = base.score["final"].dropna().sort_values(ascending=False)
    top, other = ranked.index[0], ranked.index[-1]
    store = NoteStore(root=tmp_path / "notes", calendar=list(idx))
    when = idx[375] - pd.Timedelta(days=1)
    stamp = pd.Timestamp(when.date()).tz_localize("UTC") + pd.Timedelta(hours=20)
    store.add(Note(title=f"Veto {top}", text="exclusion manuelle", targets=[top], tags=["veto"],
                   author="analyste", created_at=stamp, published_at=stamp, horizon_days=40), now=stamp)
    store.add(Note(title=f"Avis positif {other}", text="conviction forte", targets=[other], stance="haussier",
                   conviction=5, author="analyste", created_at=stamp, published_at=stamp, horizon_days=40),
              now=stamp)
    m = BrvmAlpha(notes=store)
    dec = m.decide(t, synth)
    assert dec.risk.loc[top, "veto"]
    assert dec.weights[top] == 0.0
    tilt = float(dec.risk.loc[other, "tilt"])
    assert 0.0 < tilt <= 0.5 + 1e-12
    assert dec.score.loc[other, "final"] == pytest.approx(dec.score.loc[other, "score"] + tilt)
    ex = m.explain(t, synth, other)
    assert ex["notes"]["available"] and ex["notes"]["tilt"] == pytest.approx(tilt)
    # Point-in-time : avant la publication de la note, rien ne change.
    early = BrvmAlpha(notes=store).decide(idx[370], synth)
    assert not early.risk["veto"].any()


def test_notes_r9_blocks_buys_without_forced_sale(monkeypatch, synth):
    """R9 (alerte sur résultats) : aucun achat, qualité −1, mais pas de vente forcée."""
    ns = pytest.importorskip("brvm_alpha.notes.signals")
    idx = synth["close"].index
    t = idx[380]
    base = model().decide(t, synth)
    held_sym = base.weights.idxmax()
    new_sym = base.score["final"].dropna().sort_values(ascending=False).index[0]
    fake = {
        "veto": {held_sym: ["R9 actif"], new_sym: ["R9 actif"]},
        "tilt": pd.Series(dtype=float),
        "flags": {s: [{"code": "R9", "note_id": "n" * 12, "action": "aucun achat"}] for s in (held_sym, new_sym)},
        "block_buys": [held_sym, new_sym], "max_weight_mult": {}, "freeze_auto": [],
        "quality_penalty": {held_sym: -1.0, new_sym: -1.0}, "governance_penalty": {},
        "disabled_signals": {held_sym: ["S1", "S4"]}, "reasons": [],
        "table": pd.DataFrame([{"symbol": held_sym, "code": "R9"}, {"symbol": new_sym, "code": "R9"}]),
    }
    monkeypatch.setattr(ns, "manual_overlays", lambda *a, **k: fake)
    monkeypatch.setattr(ns, "note_scores", lambda *a, **k: pd.DataFrame())
    monkeypatch.setattr(ns, "notes_asof", lambda *a, **k: pd.DataFrame())
    held = pd.Series({held_sym: 0.08})
    dec = BrvmAlpha(notes=pd.DataFrame()).decide(t, synth, held=held)
    assert dec.risk.loc[held_sym, "R9"] and dec.risk.loc[held_sym, "block_buys"]
    assert not dec.risk.loc[held_sym, "veto"]
    assert dec.risk.loc[held_sym, "quality_penalty"] == -1.0
    assert dec.score.loc[held_sym, "quality_delta"] < 0
    assert dec.weights[held_sym] <= 0.08 + 1e-12  # conservé sans renforcement (ou vendu par la bande)
    if new_sym != held_sym:
        assert dec.weights[new_sym] == 0.0  # pas de nouvel achat


# ---------------------------------------------------------------------------
# Variantes, indice discipliné, risque de portefeuille
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("variant", list(VARIANTS))
def test_all_variants_valid(synth, variant):
    t = synth["close"].index[400]
    kw = {}
    if variant == "E":
        idx = synth["close"].index
        kw["dividend_calendar"] = pd.DataFrame([{"date": idx[398], "symbol": SYMS[15], "ex_date": idx[410],
                                                 "amount": 0.06 * float(synth["close_raw"][SYMS[15]].iloc[398])}])
    m = model(variant=variant, **kw)
    dec = m.decide(t, synth)
    _check_weights(dec.weights, dec)
    assert dec.weights.sum() > 0.3
    if variant == "D":
        assert dec.diagnostics["score"]["sector_neutral"] == ["ep", "dy"]
    if variant == "E":
        s1 = dec.diagnostics["s1"]
        assert SYMS[15] in s1["positions"] and 0 < s1["total"] <= 0.20 + 1e-12
        assert dec.weights[SYMS[15]] >= s1["positions"][SYMS[15]]["weight"] - 1e-12
    if variant == "F":
        assert "regime" in dec.diagnostics
    if variant in ("G", "H"):
        assert dec.diagnostics["portfolio"]["weighting"] == m.spec.weighting


def test_variant_weights_differ(synth):
    t = synth["close"].index[400]
    wa = model(variant="A").decide(t, synth).diagnostics["score"]["weights_prior"]
    wb = model(variant="B").decide(t, synth).diagnostics["score"]["weights_prior"]
    wc = model(variant="C").decide(t, synth).diagnostics["score"]["weights_prior"]
    assert wa == {"ep": 0.15, "dy": 0.20, "mom6_1": 0.35, "lowvol": 0.20, "quality_proxy": 0.10}
    assert wb == {"ep": 0.25, "dy": 0.25, "mom6_1": 0.50}
    assert "mom12_1" in wc


def test_disciplined_index(synth):
    t = synth["close"].index[400]
    m = model()
    w = m.disciplined_index_weights(t, synth)
    assert w.attrs["mode"] == "indice_discipline"
    assert (w >= 0).all() and w.sum() <= 0.98 + 1e-9
    n = int((w > 0).sum())
    elig = m.universe(t, synth)
    n_el = int(elig["eligible"].sum())
    assert n <= 20 and n >= min(15, n_el) - 3  # quelques lignes peuvent tomber sous le plancher de 2 %
    cap = (synth["close_raw"].loc[t] * synth["shares"].loc[t])[elig.index[elig["eligible"]]]
    top = cap.sort_values(ascending=False).index[: min(20, n_el)]
    assert set(w[w > 0].index) <= set(top)


def test_relative_drawdown_overlay(synth):
    idx = synth["close"].index
    mt = synth["market_tr"]
    m = model()
    t0, t1, t2, t3 = idx[300], idx[330], idx[360], idx[390]
    m.record_nav(t0, 1e7)
    m.record_nav(t1, 1e7 * mt[t1] / mt[t0] * 0.84)  # −16 % contre le TR
    dec = m.decide(t1, synth)
    assert dec.diagnostics["relative_drawdown"]["dd"] == pytest.approx(-0.16, abs=1e-9)
    assert dec.diagnostics["relative_drawdown"].get("halve")
    assert (dec.weights >= 0).all() and dec.weights.sum() <= 0.98 + 1e-9
    m.record_nav(t2, 1e7 * mt[t2] / mt[t0] * 0.79)  # −21 % : arrêt
    dec2 = m.decide(t2, synth)
    assert dec2.diagnostics["relative_drawdown"].get("stop")
    assert dec2.diagnostics["mode"] == "indice_discipline"
    dec3 = m.decide(t3, synth)
    assert dec3.diagnostics["mode"] == "indice_discipline"
    m.reset_state()
    assert m.decide(t3, synth).diagnostics["mode"] == "selection"


def test_cap_guard_freezes(synth):
    t = synth["close"].index[380]
    p = dict(synth)
    mk = synth["market"].copy()
    mk.loc[mk["date"] == t, "market_cap"] *= 1.10
    p["market"] = mk
    held = pd.Series({SYMS[10]: 0.3, SYMS[11]: 0.2})
    dec = model().decide(t, p, held=held)
    assert dec.diagnostics["mode"] == "gel_donnees"
    assert dec.weights[SYMS[10]] == pytest.approx(0.3) and dec.weights.sum() == pytest.approx(0.5)
    assert any("contrôle des données" in msg for msg in dec.messages)


# ---------------------------------------------------------------------------
# Moteur de backtest (données synthétiques)
# ---------------------------------------------------------------------------


ZERO_COSTS = CostModel(sgi_commission=0.0, brvm_fee=0.0, dcbr_fee=0.0, vat_on_commission=0.0, impact_coef=0.0,
                       annual_custody=0.0, half_spread_default=0.0, account_fee_per_line_fcfa=0.0)


def test_strategy_fn_with_backtester(synth):
    idx = synth["close"].index
    m = model()
    fn = m.strategy_fn()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = Backtester(synth, ZERO_COSTS, Constraints(), 10e6, ExecutionModel()).run(
            fn, rebalance="M", start=idx[300], end=idx[-1])
    assert np.isfinite(res.equity).all() and res.equity.iloc[-1] > 0
    assert (res.weights.sum(axis=1) <= 1.0 + 1e-9).all()
    assert len(m._nav) >= 3  # valeur liquidative mémorisée à chaque décision
    # La bande 30/50 utilise les positions détenues : la rotation reste modérée.
    tr = res.trades.assign(m=res.trades["date"].dt.to_period("M"))
    monthly = tr.groupby("m")["value"].apply(lambda x: x.abs().sum()) / 1e7
    assert (monthly.iloc[1:] < 1.2).all()
    # Objet BrvmAlpha passé directement au moteur (target_weights(asof, view)).
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res2 = Backtester(synth, ZERO_COSTS, Constraints(), 10e6, ExecutionModel()).run(
            model(), rebalance="M", start=idx[300], end=idx[360])
    assert np.isfinite(res2.equity).all()


def test_event_driven_mode(synth):
    idx = synth["close"].index
    m = model(country_events=[{"date": idx[350], "country": "SN", "rule": "severe"}])
    calls = {"n": 0, "orders": 0}
    fn = m.strategy_fn(event_driven=True, calendar=idx)

    def wrapped(asof, view):
        calls["n"] += 1
        out = fn(asof, view)
        if out is not None:
            calls["orders"] += 1
        return out

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        Backtester(synth, ZERO_COSTS, Constraints(), 10e6, ExecutionModel()).run(
            wrapped, rebalance="D", start=idx[330], end=idx[375])
    me = [d for d in engine.rebalance_dates(idx, "M") if idx[330] <= d < idx[375]]
    assert calls["n"] > 30
    assert calls["orders"] == len(me) + 1  # fins de mois + la règle pays du jour de l'annonce
    with pytest.raises(ValueError):
        m.strategy_fn(event_driven=True)


# ---------------------------------------------------------------------------
# Panel réel : contrôles de forme du §12.3 et essai de fumée sur S0
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def real():
    if not HAS_PANEL:
        pytest.skip("panel réel absent (data/panel)")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return build_panels(PANEL_DIR)


def test_spec_12_3_n6_universe_2020(real):
    """§12.3 n° 6 (contrôle de forme : taille de l'univers, aucune performance)."""
    u10 = BrvmAlpha(notes=None, capital=10e6).universe("2020-06-30", real)
    assert 15 <= u10.attrs["n_eligible"] <= 26
    assert u10.attrs["mode"] == "selection"
    u1md = BrvmAlpha(notes=None, capital=1e9).universe("2020-06-30", real)
    assert u1md.attrs["mode"] in ("repli", "vide") and u1md.attrs["n_eligible"] < 15


def test_spec_12_3_n5_signals(real):
    """§12.3 n° 5 : DY(FTSC, 20/11/2026) = 0 ; EP(ETIT) = 10/57."""
    s = BrvmAlpha(notes=None).signals("2026-11-20", real)
    assert s["DY"]["FTSC"] == 0.0
    assert float(real["close_raw"].loc["2026-11-20", "ETIT"]) == 57.0
    assert s["EP"]["ETIT"] == pytest.approx(10.0 / 57.0)


def test_point_in_time_real_panel_s0(real):
    t = pd.Timestamp("2025-06-30")
    assert t > S1_END
    a = BrvmAlpha(notes=None, history_start=S0_START).target_weights(t, real)
    b = BrvmAlpha(notes=None, history_start=S0_START).target_weights(t, engine.truncate_asof(real, t))
    pd.testing.assert_series_equal(a, b)
    assert 0.5 < a.sum() <= 0.98 + 1e-9 and 12 <= int((a > 0).sum()) <= 20


def test_universe_real_20261120(real):
    u = BrvmAlpha(notes=None).universe("2026-11-20", real)
    # U4 : UNLC et CFAC exclus par le flottant (avis 303-2026) ; SEMC et SICC suspendus.
    assert "U4" in u.loc["UNLC", "codes"] and "U4" in u.loc["CFAC", "codes"]
    assert not u.loc["SEMC", "eligible"] and not u.loc["SICC", "eligible"]
    assert "U9" in u.loc["UNLC", "codes"]
    assert u.attrs["n_eligible"] >= 35


def test_smoke_backtest_s0_short(real):
    """Essai de fumée court, **S0 seulement** : tout tourne, coûts et rotation plausibles."""
    from brvm_alpha import settings

    start, end = pd.Timestamp("2024-01-02"), pd.Timestamp("2024-06-28")
    assert start > S1_END
    m = BrvmAlpha(notes=None, history_start=S0_START)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        bt = Backtester(real, settings.cost_scenario("central"), Constraints(), 10e6, ExecutionModel())
        res = bt.run(m.strategy_fn(), rebalance="M", start=start, end=end)
    assert np.isfinite(res.equity).all()
    w = res.weights
    assert (w.sum(axis=1) <= 1.0 + 1e-6).all()
    n_lines = (w > 1e-6).sum(axis=1)
    assert n_lines.iloc[-1] >= 10
    tr = res.trades.assign(m=res.trades["date"].dt.to_period("M"))
    monthly = tr.groupby("m")["value"].apply(lambda x: x.abs().sum()) / res.equity.mean() / 2.0
    assert monthly.iloc[1:].mean() < 0.35  # rotation aller mensuelle après la constitution
    cost_rate = float(res.cost_breakdown[["commission", "spread", "impact"]].sum().sum()) / float(
        res.trades["value"].abs().sum())
    assert 0.012 < cost_rate < 0.04  # coût aller estimé (hypothèses du §7.2)


# ---------------------------------------------------------------------------
# Compléments : cohérence du score, rotation, report des ventes, mode indice
# ---------------------------------------------------------------------------


def test_score_matches_scoring_composite(synth):
    """Sans pénalité ni inclinaison, le score final est celui de ``scoring.composite_score``."""
    from brvm_alpha.quant import scoring

    t = synth["close"].index[390]
    m = model()
    dec = m.decide(t, synth)
    elig = dec.universe["eligible"]
    blocks = {k: dec.signals[lab] for k, lab in (("ep", "EP"), ("dy", "DY"), ("mom6_1", "MOM6_1"),
                                                ("lowvol", "LOWVOL"), ("quality_proxy", "QUAL"))}
    ref = scoring.composite_score(blocks, "A", s2_malus=dec.signals["S2"].where(elig, 0.0), universe=elig,
                                  momentum_multiplier=dec.diagnostics["momentum"]["multiplier"])
    pd.testing.assert_series_equal(dec.score["score"].where(elig), ref.reindex(dec.score.index).where(elig),
                                   check_names=False)


def test_turnover_capped(synth):
    t = synth["close"].index[400]
    base = model().decide(t, synth).weights
    others = [s for s in base.index if base[s] == 0 and s not in (SYMS[2], SYMS[3])][:10]
    held = pd.Series(0.098, index=others)
    dec = model().decide(t, synth, held=held)
    w = dec.weights
    to = 0.5 * float((w - held.reindex(w.index).fillna(0.0)).abs().sum())
    assert to <= 0.50 + 1e-9
    assert dec.diagnostics["turnover_capped"]["before"] > 0.5
    assert any("cap_turnover" in msg for msg in dec.messages)


def test_sell_deferral_before_ex_date(synth):
    idx = synth["close"].index
    t = idx[400]
    base = model().decide(t, synth).weights
    sold = [s for s in base.index if base[s] == 0 and s not in (SYMS[2], SYMS[3], SYMS[5])][0]
    held = base[base > 0].copy() * 0.9
    held[sold] = 0.05
    px = float(synth["close_raw"][sold].iloc[400])
    cal = pd.DataFrame([{"date": idx[398], "symbol": sold, "ex_date": idx[405], "amount": 0.06 * px}])
    on = model(dividend_calendar=cal, defer_sales=True).decide(t, synth, held=held)
    assert sold in on.diagnostics["deferred_sales"]
    assert on.weights[sold] == pytest.approx(0.05)
    assert on.weights.sum() <= 0.98 + 1e-9
    off = model(dividend_calendar=cal).decide(t, synth, held=held)  # hors mode événementiel : signalé seulement
    assert off.weights[sold] == 0.0
    assert any("non appliqué hors mode événementiel" in msg for msg in off.messages)
    low = pd.DataFrame([{"date": idx[398], "symbol": sold, "ex_date": idx[405], "amount": 0.01 * px}])
    assert sold not in model(dividend_calendar=low, defer_sales=True).decide(t, synth, held=held).diagnostics[
        "deferred_sales"]


def test_index_mode_annual_after_stop(synth):
    idx = synth["close"].index
    mt = synth["market_tr"]
    m = model()
    t0, t1 = idx[300], idx[360]
    m.record_nav(t0, 1e7)
    m.record_nav(t1, 1e7 * mt[t1] / mt[t0] * 0.75)
    w1 = m.decide(t1, synth).weights
    assert m._risk_state["stopped"] and m._risk_state["index_year"] == t1.year
    later = [d for d in idx if d > t1 and d.year == t1.year][-1]
    dec = m.decide(later, synth, held=w1[w1 > 0])
    assert dec.diagnostics["mode"] == "indice_discipline"
    pd.testing.assert_series_equal(dec.weights[dec.weights > 0], w1[w1 > 0], check_names=False)
    fn = model().strategy_fn(mode="index")
    first = fn(idx[350], engine.PanelView(synth, idx[350]))
    assert first is not None and first.sum() <= 0.98 + 1e-9
    assert fn(idx[351], engine.PanelView(synth, idx[351])) is None  # même année : pas de rebalancement


def test_payout_proxies_optional(synth):
    t = synth["close"].index[400]
    on = model().risk_flags(t, synth, notes=None)
    off = model(payout_proxies=False).risk_flags(t, synth, notes=None)
    assert (off["R11"] <= on["R11"]).all()
    assert not any("payout" in x for lst in off["detail_panel"] for x in lst)
