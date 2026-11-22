"""Tests de non-régression des corrections du modèle BRVM Alpha (revue du moteur v1, 22/11/2026).

Données **synthétiques** (``test_strategy_alpha.make_panels``, séances de 2023-2024) : aucun
backtest, aucune performance ni aucun IC sur l'échantillon vierge S1.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from brvm_alpha.backtest import metrics as mt
from brvm_alpha.quant import features as F
from brvm_alpha.strategy import BrvmAlpha
from test_strategy_alpha import SYMS, make_panels


@pytest.fixture(scope="module")
def synth() -> dict:
    return make_panels()


def model(**kw) -> BrvmAlpha:
    kw.setdefault("notes", None)
    return BrvmAlpha(**kw)


def _cal(synth: dict, sym: str, notice: int, ex: int, yld: float = 0.06) -> pd.DataFrame:
    idx = synth["close"].index
    amount = yld * float(synth["close_raw"][sym].iloc[notice])
    return pd.DataFrame([{"date": idx[notice], "symbol": sym, "ex_date": idx[ex], "amount": amount}])


# ---------------------------------------------------------------------------
# §5.2.7 : poche S1 — exécution au plus tard en ex − 3 séances, R7, coupe-circuit
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("ex_offset", "expected"), [(2, False), (3, False), (4, True)])
def test_s1_pocket_entry_at_most_three_sessions_before_ex(synth, ex_offset, expected):
    """t + 1 ≤ ex − 3 séances : ex = t + 2 ou t + 3 refusés ; ex = t + 4 accepté (achat en ex − 3)."""
    t = 400
    sym = SYMS[15]
    dec = model(variant="E", dividend_calendar=_cal(synth, sym, 390, t + ex_offset)).decide(synth["close"].index[t],
                                                                                           synth)
    assert (sym in dec.diagnostics["s1"]["positions"]) is expected


def test_s1_open_position_is_kept_until_the_day_before_ex(synth):
    idx = synth["close"].index
    sym = SYMS[15]
    m = model(variant="E", dividend_calendar=_cal(synth, sym, 390, 406))
    m._recording = True
    dec = m.decide(idx[400], synth)  # ouverture (6 séances avant le jour ex)
    assert sym in dec.diagnostics["s1"]["positions"]
    held = dec.weights[dec.weights > 0]
    later = m.decide(idx[404], synth, held=held)  # ex = t + 2 : plus d'entrée, mais position conservée
    assert later.diagnostics["s1"]["positions"][sym]["renewal"]
    last = m.decide(idx[405], synth, held=held)  # ex = t + 1 : vente exécutée le jour ex
    assert sym not in last.diagnostics["s1"]["positions"]


class _R7Model(BrvmAlpha):
    """Modèle dont les notes signalent R7 (rapport non publié) sur un titre."""

    flagged: str = ""

    def _notes_overlay(self, d):  # type: ignore[override]
        out = super()._notes_overlay(d)
        out["flags"] = {self.flagged: [{"code": "R7", "note_id": "test", "action": "alerte orange"}]}
        return out


def test_s1_pocket_respects_r7(synth):
    sym = SYMS[15]
    t = synth["close"].index[400]
    cal = _cal(synth, sym, 390, 410)
    assert sym in model(variant="E", dividend_calendar=cal).decide(t, synth).diagnostics["s1"]["positions"]
    m = _R7Model(variant="E", notes=None, dividend_calendar=cal)
    m.flagged = sym
    dec = m.decide(t, synth)
    assert dec.risk.loc[sym, "R7"] and sym not in dec.diagnostics["s1"]["positions"]


def test_s1_journal_records_operations_point_in_time(synth):
    idx = synth["close"].index
    sym = SYMS[15]
    m = model(variant="E", dividend_calendar=_cal(synth, sym, 390, 406))
    m._recording = True
    m.decide(idx[400], synth)
    assert (sym, idx[406]) in m._s1_open and m.s1_journal().empty  # opération ouverte, non clôturée
    m.decide(idx[410], synth)  # après le jour ex : clôture avec les seules données publiées
    j = m.s1_journal()
    assert len(j) == 1 and bool(j.iloc[0]["executed"])
    op = j.iloc[0]
    vwap = float(synth["value"][sym].iloc[401]) / float(synth["volume"][sym].iloc[401])
    if float(synth["volume"][sym].iloc[401]) > 0:
        assert op["entry_price"] == pytest.approx(vwap)
    assert op["exit_price"] == pytest.approx(float(synth["close_raw"][sym].iloc[406]))
    assert op["net"] == pytest.approx(op["gross"] - op["round_trip_cost"])


def test_s1_kill_switch_suspends_pocket(synth):
    idx = synth["close"].index
    sym = SYMS[15]
    m = model(variant="E", dividend_calendar=_cal(synth, sym, 390, 410))
    m._s1_journal = [{"symbol": "X", "executed": True, "net": -0.004, "win": False} for _ in range(30)]
    m._recording = True
    dec = m.decide(idx[400], synth)
    ks = dec.diagnostics["s1"]["kill_switch"]
    assert ks["suspended"] and ks["mean_net"] < 0 and ks["n"] == 30
    assert not dec.diagnostics["s1"]["positions"]
    assert any("coupe-circuit" in x for x in dec.messages)
    assert m._s1_suspended is not None  # suspension durable pendant le backtest
    # 29 opérations seulement : pas encore évaluable
    m2 = model(variant="E", dividend_calendar=_cal(synth, sym, 390, 410))
    m2._s1_journal = [{"symbol": "X", "executed": True, "net": -0.004, "win": False} for _ in range(29)]
    assert sym in m2.decide(idx[400], synth).diagnostics["s1"]["positions"]
    m2.reset_state()
    assert m2.s1_journal().empty


# ---------------------------------------------------------------------------
# R5 : de l'annonce de l'augmentation en numéraire à la veille du détachement
# ---------------------------------------------------------------------------


def test_r5_dated_from_announcement_and_not_from_boc_exd_flag(synth):
    idx = synth["close"].index
    sym = SYMS[8]
    p = dict(synth)
    flags = synth["flags"].copy()
    flags.loc[idx[399], sym] = "(EX-D)"  # veille du détachement du 400
    p["flags"] = flags
    ci = pd.DataFrame([{"date": idx[390], "symbol": sym, "detachment_date": idx[400], "kind": "cash"}])
    m = model(capital_increases=ci)
    assert m.risk_flags(idx[395], p, notes=None).loc[sym, "R5"]  # annonce connue : achats bloqués
    r = m.risk_flags(idx[399], p, notes=None)
    assert r.loc[sym, "R5"] and r.loc[sym, "EX-D_boc"]  # veille : l'ordre s'exécuterait avec droits attachés
    assert not m.risk_flags(idx[400], p, notes=None).loc[sym, "R5"]  # droits détachés : R5 levé
    assert not model().risk_flags(idx[399], p, notes=None).loc[sym, "block_buys"]  # BOC seul : information
    bonus = ci.assign(kind="bonus")
    assert not model(capital_increases=bonus).risk_flags(idx[395], p, notes=None).loc[sym, "R5"]


# ---------------------------------------------------------------------------
# Échantillon vierge : aucune série de performance sur S1 sans validation_s1
# ---------------------------------------------------------------------------


def _early_panels() -> dict:
    """Panel minimal couvrant la fin de S1 et le début de S0 (formes seulement)."""
    rng = np.random.default_rng(3)
    dates = pd.bdate_range("2022-01-03", "2023-06-30")
    syms = SYMS[:20]
    r = rng.normal(0.0004, 0.01, (len(dates), len(syms)))
    close = pd.DataFrame(1000.0 * np.cumprod(1.0 + r, axis=0), index=dates, columns=syms).round()
    vol = pd.DataFrame(rng.integers(500, 3000, close.shape).astype(float), index=dates, columns=syms)
    return {"close_raw": close, "tr_index": close / close.iloc[0] * 100.0, "volume": vol, "value": vol * close,
            "status": pd.DataFrame("traded", index=dates, columns=syms),
            "per": pd.DataFrame(12.0, index=dates, columns=syms),
            "net_yield_pct": pd.DataFrame(6.0, index=dates, columns=syms),
            "last_div_net": pd.DataFrame(60.0, index=dates, columns=syms),
            "last_div_date": pd.DataFrame(pd.Timestamp("2021-06-15"), index=dates, columns=syms)}


def test_momentum_spread_never_computed_on_s1_by_default(monkeypatch):
    panels = _early_panels()
    seen: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    orig = F.momentum_spread_returns

    def probe(fp, *a, **kw):
        idx = fp["tr_index"].index
        seen.append((idx.min(), idx.max()))
        return orig(fp, *a, **kw)

    monkeypatch.setattr(F, "momentum_spread_returns", probe)
    dec = model().decide("2023-06-30", panels, portfolio=False)
    assert seen and seen[-1][0] >= pd.Timestamp("2022-11-17")
    assert any("échantillon vierge S1 protégé" in x for x in dec.messages)
    seen.clear()
    model().decide("2022-10-31", panels, portfolio=False)  # décision datée de S1 : aucun calcul
    assert not seen
    # Additif v1.1 (D1) : base « sessions » par défaut, y compris pour le test unique de S1.
    assert BrvmAlpha(notes=None, validation_s1=True).window_basis == "sessions"
    seen.clear()
    model(validation_s1=True, window_basis="boc").decide("2023-06-30", panels, portfolio=False)
    assert seen[-1][0] == pd.Timestamp("2022-01-03")  # réservé au test pré-enregistré


# ---------------------------------------------------------------------------
# Fenêtres en séances (session_no) : trou de BOC synthétique
# ---------------------------------------------------------------------------


def test_session_window_basis_on_synthetic_gap():
    dates = pd.bdate_range("2024-01-01", periods=200)
    sess = np.arange(1, 201)
    sess[150:] += 40  # 40 BOC manquants entre la ligne 149 et la ligne 150
    tr = pd.DataFrame({"A": 100.0 * 1.001 ** np.arange(200)}, index=dates)
    panels = {"tr_index": tr, "session_no": pd.Series(sess, index=dates)}
    assert F.session_numbers(panels, like=tr).tolist() == sess.tolist()
    boc = F.mom_sessions(panels, window_basis="boc")
    ses = F.mom_sessions(panels, window_basis="sessions", prorata=False)
    t = dates[-1]
    assert np.isfinite(boc.loc[t, "A"])  # 126 lignes : défini
    assert np.isnan(ses.loc[t, "A"])  # 126 séances dont 40 sans BOC : < 100 rendements valides (sans prorata)
    # Additif v1.1, D1 : seuil au prorata ⌈100 × 86 / 126⌉ = 69 ≤ 86 rendements valides : défini.
    assert np.isfinite(F.mom_sessions(panels, window_basis="sessions").loc[t, "A"])
    # 63 dernières séances (178 à 240) : seules 50 lignes ont un BOC (séances 191 à 240)
    valid = F.valid_return_mask(panels, like=tr)
    cnt = F.on_session_grid(valid.astype(float), sess, lambda x: x.rolling(63, min_periods=1).sum())
    assert int(cnt.loc[t, "A"]) == 50
    assert int(valid.astype(float).rolling(63, min_periods=1).sum().loc[t, "A"]) == 63  # base « boc »
    with pytest.raises(ValueError):
        F.mom_sessions(panels, window_basis="lignes")


def test_universe_u2_counts_sessions_when_requested(synth):
    p = dict(synth)
    idx = synth["close"].index
    sess = np.arange(1, len(idx) + 1)
    sess[390:] += 40  # trou de 40 BOC avant la ligne 390
    p["session_no"] = pd.Series(sess, index=idx)
    t = idx[400]
    u_boc = model(window_basis="boc").universe(t, p)
    u_ses = model(window_basis="sessions").universe(t, p)
    assert u_boc.attrs["n_eligible"] > 0
    assert (u_ses["n_returns_63"] <= 23).all()  # au plus 22 rendements sur les 63 dernières séances
    # Additif v1.1, D1 : seuil U2 au prorata des 23 BOC disponibles, plancher 20 (au lieu de 40) : l'univers
    # n'est plus vidé par la perte de nos BOC ; un titre sous 20 rendements reste exclu.
    assert u_ses.attrs["n_eligible"] > 0
    assert ((u_ses["n_returns_63"] >= 20) | ~u_ses["eligible"]).all()
    dec = model(window_basis="boc").decide(t, p, portfolio=False)
    assert any("window_basis='sessions'" in x for x in dec.messages)
    assert dec.diagnostics["window_basis"]["basis"] == "boc"
    assert model().window_basis == "sessions"  # défaut v1.1
    assert model(window_basis="boc").fingerprint != model(window_basis="sessions").fingerprint


# ---------------------------------------------------------------------------
# Point-in-time : facteur de division et montants de dividendes
# ---------------------------------------------------------------------------


def test_prepare_split_factor_and_close_adj_point_in_time(synth):
    p = dict(synth)
    idx = synth["close"].index
    sf = pd.DataFrame(1.0, index=idx, columns=synth["close"].columns)
    sf.iloc[:420, 0] = 10.0  # division 10:1 FUTURE (ligne 420) pour le premier titre
    p["split_factor"] = sf
    p["close_adj"] = synth["close_raw"] / sf
    d = model()._prepare(p, idx[400])
    col = synth["close"].columns[0]
    assert d.wide["split_factor"][col].iloc[-1] == 1.0
    assert d.wide["close_adj"][col].iloc[-1] == pytest.approx(float(synth["close_raw"][col].iloc[400]))


def test_dividend_revision_visible_only_from_its_publication(synth):
    idx = synth["close"].index
    p = dict(synth)
    tab = pd.DataFrame([{"date": idx[380], "symbol": SYMS[4], "ex_date": idx[381], "amount": 226.45,
                         "amount_revised": 266.45, "revised_seen": idx[382]}])
    p["dividends_table"] = tab
    m = model()
    before = m._prepare(p, idx[380]).dividends
    after = m._prepare(p, idx[383]).dividends
    assert float(before["amount"].iloc[0]) == 226.45 and float(after["amount"].iloc[0]) == 266.45


# ---------------------------------------------------------------------------
# §4.4 variante F : observations « hebdomadaires » multi-semaines retirées
# ---------------------------------------------------------------------------


def test_weekly_observation_mask_drops_multi_week_and_2021_window():
    days = pd.bdate_range("2021-04-01", "2021-08-31")
    gap = (days > "2021-05-06") & (days < "2021-06-25")
    gap |= (days >= "2021-07-01") & (days <= "2021-07-07")
    days = days[~gap]
    lvl = pd.Series(np.linspace(100, 110, len(days)), index=days)
    r = lvl.resample("W-FRI").last().dropna().pct_change().dropna()
    keep = mt.weekly_observation_mask(days, r.index)
    dropped = set(r.index[~keep].strftime("%Y-%m-%d"))
    assert "2021-06-25" in dropped and "2021-07-09" in dropped
    assert "2021-08-27" not in dropped


def test_regime_variant_f_ignores_multi_week_observations(synth):
    p = dict(synth)
    mtr = synth["market_tr"].copy()
    idx = mtr.index
    mtr = mtr[(idx < idx[200]) | (idx > idx[230])]  # trou de 30 séances dans le TR de marché
    p["market_tr"] = mtr
    m = model(variant="F")
    d = m._prepare(p, idx[420])
    rg = m._regime(d)
    assert rg.get("weeks_dropped")
