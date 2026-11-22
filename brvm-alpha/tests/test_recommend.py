"""Tests de l'ordre de bataille (``brvm_alpha.portfolio.recommend``), hors ligne.

Données synthétiques (dates de S0 seulement) ou panel réel S0 au 20/11/2026 ; aucune performance
n'est évaluée sur l'échantillon vierge S1 (2017-01-02 → 2022-11-16). Les cas d'arrondi et de coûts
sont calculés à la main dans les commentaires.
"""

from __future__ import annotations

import json
import math
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from brvm_alpha import reference, settings
from brvm_alpha.backtest.walkforward import REGISTRY_COLUMNS, TrialRegistry
from brvm_alpha.config import TaxModel
from brvm_alpha.portfolio import recommend as R
from brvm_alpha.quant import macro

ROOT = Path(__file__).resolve().parents[1]
PANEL_DIR = ROOT / "data" / "panel"
HAS_PANEL = (PANEL_DIR / "equities.parquet").exists() and (PANEL_DIR / "adjusted_prices.parquet").exists()
CENTRAL = settings.cost_scenario("central")


# ---------------------------------------------------------------------------
# Arrondis : prix et lots
# ---------------------------------------------------------------------------


def test_price_band_hand_cases():
    # 4385 × 0,925 = 4 056,125 → pas supérieur 4 060 ; 4385 × 1,075 = 4 713,875 → pas inférieur 4 710.
    assert macro.price_band(4385) == (4060.0, 4710.0)
    # §12.3 n° 3 : ETIT à 13 FCFA, borne haute = 14 (au moins un pas).
    assert macro.price_band(13)[1] == 14.0
    assert macro.tick_size(99) == 1 and macro.tick_size(100) == 5


def test_limit_prices_hand_cases():
    # 4385 : achat min(4710 ; 4428,85) → 4 425 ; vente max(4060 ; 4341,15) → 4 345.
    lp = R.limit_prices(4385)
    assert (lp["low"], lp["high"], lp["buy"], lp["sell"]) == (4060.0, 4710.0, 4425.0, 4345.0)
    # SNTS au 20/11/2026 (4 040) : bornes (3 740 ; 4 340), achat 4 080,4 → 4 080, vente 3 999,6 → 4 000.
    lp = R.limit_prices(4040)
    assert (lp["low"], lp["high"], lp["buy"], lp["sell"]) == (3740.0, 4340.0, 4080.0, 4000.0)
    # 950 : achat 959,5 → 955 ; vente 940,5 → 945.
    lp = R.limit_prices(950)
    assert (lp["buy"], lp["sell"]) == (955.0, 945.0)
    # Tolérance plus large que la bande : la borne s'impose (1 000 : bornes 925 ; 1 075).
    lp = R.limit_prices(1000, tolerance=0.10)
    assert (lp["buy"], lp["sell"]) == (1075.0, 925.0)
    # Frontière de 100 FCFA : achat 101 → 100 = dernier cours, porté à un pas au-dessus (105, pas de 5) ;
    # vente 99 (pas 1). Correction du 22/11/2026 : au moins un pas d'écart quand le pas dépasse la tolérance.
    lp = R.limit_prices(100)
    assert (lp["buy"], lp["sell"]) == (105.0, 99.0)
    # Pas de 1 FCFA : 57 × 1,01 = 57,57 → 57 et 57 × 0,99 = 56,43 → 57 (= dernier cours) : un pas d'écart.
    lp = R.limit_prices(57)
    assert (lp["buy"], lp["sell"]) == (58.0, 56.0)
    # Référence ex-dividende (4 200) : bornes (3 885 ; 4 515), limites autour du dernier cours.
    lp = R.limit_prices(4385, reference_price=4200)
    assert (lp["low"], lp["high"], lp["buy"], lp["sell"]) == (3885.0, 4515.0, 4425.0, 4345.0)


def test_tick_rounding_helpers():
    assert R.floor_to_tick(99.6) == 99.0
    assert R.ceil_to_tick(99.2) == 100.0
    assert R.ceil_to_tick(100.1) == 105.0
    assert R.floor_to_tick(104.9) == 100.0
    assert R.floor_to_tick(4428.85) == 4425.0
    assert R.ceil_to_tick(4341.15) == 4345.0
    assert R.round_fcfa(581.76) == 582 and R.round_fcfa(2.5) == 3 and R.round_fcfa(1292.8) == 1293
    assert R.round_fcfa(-2.5) == -3


# ---------------------------------------------------------------------------
# Coûts exacts d'un ordre (§7.2)
# ---------------------------------------------------------------------------


def test_order_costs_exact_hand_computed():
    """Achat de 100 SNTS à 4 040 FCFA, demi-spread 0,35 %, participation 4 % (MDV63 = 10,1 M).

    brut 404 000 ; courtage 0,8 % = 3 232 ; TVA 18 % × 3 232 = 581,76 → 582 ; BRVM 0,2 % = 808 ;
    DC/BR 0,1 % = 404 ; explicites 5 026 ; demi-spread 0,35 % = 1 414 ; impact 0,016 × √0,04 × 404 000
    = 1 292,8 → 1 293 ; implicites 2 707 ; total 7 733 ; net 411 733 (vente : 396 267).
    """
    oc = R.order_costs(100, 4040, CENTRAL, side="achat", half_spread=0.0035, mdv63=10_100_000)
    assert oc["brut"] == 404_000
    assert (oc["courtage"], oc["tva"], oc["brvm"], oc["dcbr"], oc["redevance"]) == (3232, 582, 808, 404, 0)
    assert oc["explicites"] == 5026
    assert (oc["demi_spread"], oc["impact"], oc["implicites"]) == (1414, 1293, 2707)
    assert oc["total"] == 7733 and oc["net"] == 411_733
    assert math.isclose(oc["participation_max"], 0.04)
    sell = R.order_costs(100, 4040, CENTRAL, side="vente", half_spread=0.0035, mdv63=10_100_000)
    assert sell["net"] == 404_000 - 7733
    # Deux tranches de 100 : chaque tranche a la même participation, donc deux fois les coûts.
    two = R.order_costs(200, 4040, CENTRAL, side="achat", half_spread=0.0035, mdv63=10_100_000, tranches=[100, 100])
    assert two["total"] == 2 * 7733 and two["brut"] == 808_000
    # Prix limite égal au cours : aucun coût implicite possible (plafonné), seulement les frais facturés.
    capped = R.order_costs(100, 4040, CENTRAL, side="achat", half_spread=0.0035, mdv63=10_100_000, limit=4040)
    assert capped["implicites"] == 0 and capped["implicites_plafonnes"] and capped["net"] == 404_000 + 5026
    assert R.fee_breakdown(0, CENTRAL)["explicites"] == 0
    with pytest.raises(ValueError):
        R.order_costs(3, 4040, CENTRAL, tranches=[1, 1])


def test_worst_case_provision_hand_computed():
    # 100 titres à la limite 4 080 : 408 000 + courtage 3 264 + TVA 587,52 → 588 + BRVM 816 + DC/BR 408.
    assert R._worst_case([100], 4080, CENTRAL, "achat") == 408_000 + 3264 + 588 + 816 + 408
    # Vente à la limite 4 000 : 400 000 − (3 200 + 576 + 800 + 400).
    assert R._worst_case([100], 4000, CENTRAL, "vente") == 400_000 - (3200 + 576 + 800 + 400)


# ---------------------------------------------------------------------------
# Échéancier de participation et règlement
# ---------------------------------------------------------------------------


def test_participation_schedule():
    # 10 % × 2 M = 200 000 FCFA par séance, soit 200 titres à 1 000 FCFA.
    assert R.participation_schedule(1000, 1000, 2_000_000) == [200] * 5
    assert R.participation_schedule(1001, 1000, 2_000_000) == [167] * 5 + [166]
    assert all(t * 1000 <= 200_000 for t in R.participation_schedule(1001, 1000, 2_000_000))
    assert R.participation_schedule(50, 1000, 2_000_000) == [50]
    assert R.participation_schedule(1001, 1000, None) == [1001]
    assert R.participation_schedule(3, 1000, 5000) == [1, 1, 1]  # un titre > 10 % : 1 par séance
    assert R.participation_schedule(0, 1000, 2_000_000) == []


def test_settlement_lag_regimes():
    cal = pd.bdate_range("2025-11-24", "2025-12-31")
    # J+3 avant le 04/12/2025 : jeudi 27/11 → mardi 02/12 ; J+2 ensuite : jeudi 04/12 → lundi 08/12.
    assert R.settlement_date("2025-11-27", cal) == pd.Timestamp("2025-12-02")
    assert R.settlement_date("2025-12-04", cal) == pd.Timestamp("2025-12-08")


def test_future_sessions_skip_fixed_holidays():
    fut = R.future_sessions("2026-12-23", 4, sessions=pd.DatetimeIndex(["2026-12-22", "2026-12-23"]))
    # 24/12 (jeudi), 25/12 férié, 28/12, 29/12, 30/12.
    assert fut == [pd.Timestamp(x) for x in ("2026-12-24", "2026-12-28", "2026-12-29", "2026-12-30")]


def test_plan_execution_sells_settle_before_financed_buys():
    """Ventes d'abord ; liquidités initiales utilisées d'abord ; produit de vente après règlement (J+2)."""
    cal = R.future_sessions("2026-11-20", 30, None)  # 23/11, 24/11, 25/11…
    orders = [
        {"symbol": "XXXC", "side": "vente", "qty": 100, "tranches": [100], "limit": 1000.0, "ref_price": 1000.0},
        {"symbol": "YYYC", "side": "achat", "qty": 50, "tranches": [50], "limit": 1000.0, "ref_price": 1000.0},
    ]
    tab, info = R.plan_execution(orders, 30_000, cal, CENTRAL)
    sell = tab[tab["sens"] == "vente"].iloc[0]
    assert sell["date"] == pd.Timestamp("2026-11-23") and sell["date_reglement"] == pd.Timestamp("2026-11-25")
    buys = tab[tab["sens"] == "achat"].reset_index(drop=True)
    # Séance 1 : 29 titres sur les liquidités initiales (29 000 + 232 + 42 + 58 + 29 = 29 361 ≤ 30 000).
    assert buys.loc[0, "date"] == pd.Timestamp("2026-11-23") and buys.loc[0, "titres"] == 29
    assert buys.loc[0, "financement"] == "liquidités initiales" and buys.loc[0, "produit_ventes_utilise"] == 0
    assert buys.loc[0, "pire_cas"] == 29_361
    # Le reste attend le règlement de la vente (25/11) : jamais avant.
    assert buys.loc[1, "date"] == pd.Timestamp("2026-11-25") and buys.loc[1, "titres"] == 21
    assert buys.loc[1, "produit_ventes_utilise"] > 0
    assert int(buys["titres"].sum()) == 50
    # La vente est listée avant l'achat de la même séance.
    first = tab[tab["seance"] == 1]
    assert list(first["sens"]) == ["vente", "achat"]
    # Pire cas : liquidités finales = 30 000 + 98 776 (vente) − 29 361 − achat de 21 titres.
    sale_min = 100_000 - (800 + 144 + 200 + 100)
    buy2 = 21_000 + (168 + 30 + 42 + 21)
    assert info["liquidites_finales_pire_cas"] == 30_000 + sale_min - 29_361 - buy2


def test_plan_execution_respects_participation_tranches():
    cal = R.future_sessions("2026-11-20", 30, None)
    orders = [{"symbol": "ZZZC", "side": "achat", "qty": 1001, "tranches": R.participation_schedule(1001, 1000, 2e6),
               "limit": 1010.0, "ref_price": 1000.0}]
    tab, _ = R.plan_execution(orders, 10_000_000, cal, CENTRAL)
    assert list(tab["seance"]) == [1, 2, 3, 4, 5, 6]
    assert list(tab["titres"]) == [167] * 5 + [166]


# ---------------------------------------------------------------------------
# Fiscalité (IRVM) et dividendes attendus
# ---------------------------------------------------------------------------


def test_irvm_rates():
    assert R.irvm_rate("SGBC") == 0.12  # CI
    assert R.irvm_rate("SNTS") == 0.10  # SN (2026)
    assert R.irvm_rate("CBIBF") == 0.125  # BF (NV)
    assert R.irvm_rate("BOAN") == 0.07  # NE
    assert R.irvm_rate("LNBB") == 0.05 and R.irvm_rate("BICB") == 0.05 and R.irvm_rate("BOAB") == 0.10  # émetteurs BJ
    # Taux de l'époque pour reconstituer le brut d'un dividende déjà payé.
    assert R.irvm_rate("SGBC", "2024-06-25") == 0.10
    assert R.irvm_rate("SGBC", "2025-08-05") == 0.12
    assert R.irvm_rate("SNTS", "2025-05-22") == 0.125
    assert R.irvm_rate("SNTS", "2026-05-26") == 0.10
    custom = TaxModel(dividend_withholding={**TaxModel().dividend_withholding, "CI": 0.15})
    assert R.irvm_rate("SGBC", taxes=custom) == 0.15


def _div_panels() -> dict:
    divs = pd.DataFrame([
        # CI : net 880 publié en 2025 (12 %) → brut 1 000.
        {"symbol": "SGBC", "ex_date": "2025-06-18", "payment_date": "2025-06-20", "amount": 880.0, "date": "2025-06-17"},
        {"symbol": "SGBC", "ex_date": "2024-06-19", "payment_date": "2024-06-21", "amount": 800.0, "date": "2024-06-18"},
        # SN : net 875 payé en 2025 (12,5 %), puis division par 10 le 27/10/2025.
        {"symbol": "SNTS", "ex_date": "2025-05-20", "payment_date": "2025-05-22", "amount": 875.0, "date": "2025-05-19"},
        # BF : net 875 (12,5 %).
        {"symbol": "CBIBF", "ex_date": "2025-07-03", "payment_date": "2025-07-07", "amount": 875.0, "date": "2025-07-02"},
        # Dernier paiement trop ancien (> 15 mois) : aucun dividende supposé.
        {"symbol": "SIVC", "ex_date": "2023-06-01", "payment_date": "2023-06-05", "amount": 100.0, "date": "2023-05-31"},
    ])
    ca = pd.DataFrame([{"symbol": "SNTS", "date": pd.Timestamp("2025-10-27"), "kind": "split", "ratio": 10.0}])
    return {"dividends_table": divs, "corporate_actions": ca}


def test_dividend_schedule_irvm_hand_computed():
    cal = pd.bdate_range("2023-01-02", "2026-03-02")
    out = R.dividend_schedule({"SGBC": 10, "SNTS": 100, "CBIBF": 10, "SIVC": 5}, "2026-03-02", _div_panels(),
                              calendar=cal).set_index("symbole")
    # CI : 10 × 880 = 8 800 nets ; brut 10 000 ; IRVM 1 200 (12 %).
    assert (out.loc["SGBC", "montant_brut"], out.loc["SGBC", "irvm"], out.loc["SGBC", "montant_net"]) == (10_000, 1_200, 8_800)
    assert out.loc["SGBC", "date_ex_prevue"] == pd.Timestamp("2026-06-18")
    assert out.loc["SGBC", "date_paiement_prevue"] == pd.Timestamp("2026-06-22")  # délai médian de 2 séances
    # SN : 875 / 10 (division) = 87,5 net à 12,5 % → brut 100 → 90 net à 10 % ; 100 titres.
    assert out.loc["SNTS", "facteur_division"] == 10.0
    assert math.isclose(out.loc["SNTS", "dividende_net_ajuste"], 87.5)
    assert (out.loc["SNTS", "montant_brut"], out.loc["SNTS", "irvm"], out.loc["SNTS", "montant_net"]) == (10_000, 1_000, 9_000)
    assert out.loc["SNTS", "taux_irvm_dernier"] == 0.125 and out.loc["SNTS", "taux_irvm_prevu"] == 0.10
    assert out.loc["SNTS", "date_ex_prevue"] == pd.Timestamp("2026-05-20")
    # BF : 10 × 875 = 8 750 nets (12,5 %).
    assert (out.loc["CBIBF", "montant_brut"], out.loc["CBIBF", "irvm"], out.loc["CBIBF", "montant_net"]) == (10_000, 1_250, 8_750)
    # Plus de 15 mois sans paiement : rien.
    assert out.loc["SIVC", "montant_net"] == 0 and "15 mois" in out.loc["SIVC", "statut"]


def test_dividend_schedule_announced_absence():
    """FTSC : absence de dividende de l'exercice 2025 connue le 12/06/2026 (reference.py)."""
    divs = pd.DataFrame([{"symbol": "FTSC", "ex_date": "2025-09-26", "payment_date": "2025-09-30",
                          "amount": 1726.56, "date": "2025-09-25"}])
    before = R.dividend_schedule({"FTSC": 10}, "2026-06-01", {"dividends_table": divs}).iloc[0]
    after = R.dividend_schedule({"FTSC": 10}, "2026-07-01", {"dividends_table": divs}).iloc[0]
    # Avant l'annonce : part ordinaire seulement (1 161,60 net, la part exceptionnelle est exclue).
    assert math.isclose(before["dividende_net_ajuste"], 1161.60)
    assert before["montant_net"] == R.round_fcfa(10 * 1161.60)
    assert after["montant_net"] == 0 and "absence annoncée" in after["statut"]
    assert reference.announced_no_dividend("FTSC", "2026-07-01") is not None


# ---------------------------------------------------------------------------
# Bootstrap et fenêtre d'estimation
# ---------------------------------------------------------------------------


def _weekly_frame(n: int = 200, seed: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2023-01-06", periods=n, freq="W-FRI")
    tr = rng.normal(0.003, 0.02, n)
    a = 0.8 * tr + rng.normal(0.0, 0.015, n)
    return pd.DataFrame({"AAAC": a, "BBBC": rng.normal(0.002, 0.03, n), R._BENCH: tr}, index=idx)


def test_bootstrap_deterministic_with_seed():
    i1 = R.stationary_bootstrap_indices(100, 52, 50, 8, seed=7)
    i2 = R.stationary_bootstrap_indices(100, 52, 50, 8, seed=7)
    assert np.array_equal(i1, i2)
    assert not np.array_equal(i1, R.stationary_bootstrap_indices(100, 52, 50, 8, seed=8))
    assert i1.min() >= 0 and i1.max() < 100
    # Blocs : la plupart des pas sont consécutifs (probabilité 7/8 de prolonger le bloc).
    cont = np.mean((i1[:, 1:] - i1[:, :-1]) % 100 == 1)
    assert 0.8 < cont < 0.95
    w = _weekly_frame()
    d1 = R.return_distribution(w, {"AAAC": 0.5, "BBBC": 0.48}, n_boot=2000, seed=11)
    d2 = R.return_distribution(w, {"AAAC": 0.5, "BBBC": 0.48}, n_boot=2000, seed=11)
    assert d1 == d2
    d3 = R.return_distribution(w, {"AAAC": 0.5, "BBBC": 0.48}, n_boot=2000, seed=12)
    assert d3["mediane"] != d1["mediane"]
    assert d1["p10"] <= d1["mediane"] <= d1["p90"]
    assert 0.0 <= d1["p_perte"] <= 1.0 and 0.0 <= d1["p_battre_tr"] <= 1.0
    assert d1["avertissement"] == "distribution historique, pas une prévision"


def test_bootstrap_joint_draws_and_cost_drag():
    w = _weekly_frame()
    w["CLONE"] = w[R._BENCH]
    same = R.return_distribution(w, {"CLONE": 1.0}, n_boot=500, seed=1)
    # Portefeuille identique au TR, tiré sur les mêmes semaines : jamais strictement meilleur.
    assert same["p_battre_tr"] == 0.0 and math.isclose(same["mediane"], same["tr_mediane"])
    drag = R.return_distribution(w, {"CLONE": 1.0}, n_boot=500, seed=1, cost_drag=0.02)
    assert drag["p_battre_tr"] == 0.0 and drag["mediane"] < same["mediane"]
    short = R.return_distribution(w.iloc[:10], {"CLONE": 1.0}, n_boot=10)
    assert short["disponible"] is False


def test_estimation_window_never_reads_s1_when_not_executed():
    """Cours empoisonnés sur S1 : rien ne doit en sortir quand le registre n'a pas exécuté S1."""
    idx = pd.bdate_range("2021-01-04", "2024-06-28")
    rng = np.random.default_rng(0)
    base = 100.0 * np.cumprod(1.0 + rng.normal(0.0005, 0.01, (len(idx), 2)), axis=0)
    tr = pd.DataFrame(base, index=idx, columns=["AAAC", "BBBC"])
    mtr = pd.Series(100.0 * np.cumprod(1.0 + rng.normal(0.0004, 0.008, len(idx))), index=idx)
    s1 = idx <= R.S1_END
    tr.loc[s1] = np.where(rng.random((int(s1.sum()), 2)) < 0.5, 1e9, np.nan)  # poison
    mtr.loc[s1] = 1e-9
    win = R.estimation_window("2024-06-28", s1_done=False)
    assert win["debut"] == pd.Timestamp("2022-11-17") and not win["s1_utilise"]
    weekly = R.weekly_tr_returns(tr, mtr, ["AAAC", "BBBC"], win["debut"], win["fin"])
    assert weekly.index.min() > R.S1_END
    assert weekly.attrs["debut_donnees"] >= R.S0_START
    assert weekly.abs().max().max() < 0.5  # aucun rendement issu des cours empoisonnés
    # Première semaine incomplète (jeudi 17/11/2022) retirée : la première semaine est celle du 25/11/2022.
    assert weekly.index.min() == pd.Timestamp("2022-11-25")
    full = R.estimation_window("2024-06-28", s1_done=True)
    assert full["debut"] == pd.Timestamp("2017-01-02") and full["s1_utilise"]


def _registry(path: Path, executed_s1: bool) -> Path:
    rows = [{c: None for c in REGISTRY_COLUMNS} for _ in range(2)]
    rows[0].update({"id": "S1-A", "variante": "A", "echantillon": "S1",
                    "statut": "exécuté" if executed_s1 else "pré-enregistré",
                    "date_execution": pd.Timestamp("2026-11-23", tz="UTC") if executed_s1 else pd.NaT})
    rows[1].update({"id": "S0-DIAG-A", "variante": "A", "echantillon": "S0", "statut": "exécuté",
                    "date_execution": pd.Timestamp("2026-11-22", tz="UTC")})
    frame = pd.DataFrame(rows)
    frame["date_execution"] = pd.to_datetime(frame["date_execution"], utc=True)
    TrialRegistry(path=path, frame=frame).save(path)
    return path


def test_s1_executed_reads_registry(tmp_path):
    assert R.s1_executed(_registry(tmp_path / "t1.parquet", False))[0] is False
    assert R.s1_executed(_registry(tmp_path / "t2.parquet", True))[0] is True
    assert R.s1_executed(tmp_path / "absent.parquet")[0] is False


# ---------------------------------------------------------------------------
# Choix de la variante (metrics.json factice)
# ---------------------------------------------------------------------------


def _metrics(tmp: Path, status_a: str, promo: list[dict] | None = None, others: dict | None = None,
             sample: str = "S1") -> Path:
    d = tmp / f"val_{status_a}_{len(promo or [])}_{sample}"
    d.mkdir(parents=True, exist_ok=True)
    variants = {"A": {"statut": status_a}, "REF": {"statut": "CANDIDAT"}, **(others or {})}
    m = {"echantillon": sample, "variantes": variants, "promotion": {"principal": "A", "criteres": promo or []}}
    (d / "metrics.json").write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
    return d


def test_choose_variant_absent(tmp_path):
    c = R.choose_variant(None, tmp_path / "rien", registry_path=_registry(tmp_path / "r.parquet", False))
    assert c["variante"] == "REF" and c["comparaison"] == "A" and c["statut"] == R.NOT_TESTED
    assert c["phrase_etude"] and any("pas encore été exécuté" in w for w in c["avertissements"])


def test_choose_variant_candidate(tmp_path):
    reg = _registry(tmp_path / "r.parquet", True)
    c = R.choose_variant(None, _metrics(tmp_path, "CANDIDAT"), registry_path=reg)
    assert c["variante"] == "A" and c["statut"] == "CANDIDAT" and c["comparaison"] == "REF"
    assert c["phrase_etude"] is True and not c["avertissements"]


def test_choose_variant_promoted_by_rule(tmp_path):
    reg = _registry(tmp_path / "r.parquet", True)
    promo = [{"variante": "A", "promue": None, "actif_net_an": 0.01},
             {"variante": "I", "promue": True, "actif_net_an": 0.02},
             {"variante": "G", "promue": True, "actif_net_an": 0.015}]
    c = R.choose_variant(None, _metrics(tmp_path, "CANDIDAT", promo, {"I": {"statut": "CANDIDAT"},
                                                                     "G": {"statut": "CANDIDAT"}}), registry_path=reg)
    assert c["variante"] == "I" and c["variante_promue"] == "I"


def test_choose_variant_rejected(tmp_path):
    reg = _registry(tmp_path / "r.parquet", True)
    c = R.choose_variant(None, _metrics(tmp_path, "REJETÉ"), registry_path=reg)
    assert c["variante"] == "REF" and c["comparaison"] is None and c["statut_A"] == "REJETÉ"
    assert c["phrase_etude"] is True


def test_choose_variant_indeterminate_and_promu(tmp_path):
    reg = _registry(tmp_path / "r.parquet", True)
    c = R.choose_variant(None, _metrics(tmp_path, "INDÉTERMINÉ"), registry_path=reg)
    assert c["variante"] == "REF" and c["comparaison"] == "A" and c["avertissements"]
    p = R.choose_variant(None, _metrics(tmp_path, "PROMU"), registry_path=reg)
    assert p["variante"] == "A" and p["promu"] and p["phrase_etude"] is False


def test_choose_variant_wrong_sample_and_inconsistent_registry(tmp_path):
    reg = _registry(tmp_path / "r.parquet", False)
    c = R.choose_variant(None, _metrics(tmp_path, "CANDIDAT", sample="S0"), registry_path=reg)
    assert c["variante"] == "REF" and any("S0" in w for w in c["avertissements"])
    c2 = R.choose_variant(None, _metrics(tmp_path, "CANDIDAT"), registry_path=reg)
    assert c2["variante"] == "A" and any("incohérence" in w for w in c2["avertissements"])
    forced = R.choose_variant("B", tmp_path / "rien", registry_path=reg)
    assert forced["variante"] == "B" and forced["impose"] and forced["comparaison"] is None


# ---------------------------------------------------------------------------
# Ordre de bataille complet : panel synthétique (S0)
# ---------------------------------------------------------------------------


def _synthetic_panels(n_days: int = 430, seed: int = 5) -> dict:
    """Panel synthétique au format de ``strategy.build_panels`` (dates de S0, sans divisions)."""
    rng = np.random.default_rng(seed)
    syms = [s for s in sorted(reference.SECTOR_2025) if s not in reference.DELISTED_SYMBOLS][:30]
    n = len(syms)
    dates = pd.bdate_range("2023-01-02", periods=n_days)
    r = rng.normal(rng.normal(0.0003, 0.0004, n), rng.uniform(0.006, 0.02, n), size=(n_days, n))
    traded = rng.random((n_days, n)) < rng.uniform(0.8, 1.0, n)
    r = np.where(traded, r, 0.0)
    close = 1000.0 * rng.uniform(0.5, 20.0, n) * np.cumprod(1.0 + r, axis=0)
    tick = np.where(close < 100, 1.0, 5.0)
    close = np.maximum(np.round(close / tick) * tick, 1.0)
    vol = np.where(traded, rng.integers(500, 6000, size=(n_days, n)), 0).astype(float)
    idx = pd.DatetimeIndex(dates, name="date")
    cols = pd.Index(syms, name="symbol")
    C = pd.DataFrame(close, idx, cols)
    status = pd.DataFrame(np.where(traded, "traded", "not_traded").astype(object), idx, cols)
    per = pd.DataFrame(np.tile(rng.uniform(4.0, 30.0, n), (n_days, 1)), idx, cols)
    div_amt = rng.uniform(0.02, 0.09, n) * close[0]
    pay = [dates[min(60 + 7 * j % 120, n_days - 1)] for j in range(n)]
    last_div_net = pd.DataFrame(np.tile(div_amt, (n_days, 1)), idx, cols)
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
    shares = pd.DataFrame(np.tile(rng.uniform(1e6, 5e7, n), (n_days, 1)), idx, cols)
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


@pytest.fixture(scope="module")
def synth() -> dict:
    return _synthetic_panels()


@pytest.fixture(scope="module")
def synth_order(synth, tmp_path_factory):
    tmp = tmp_path_factory.mktemp("rec")
    reg = _registry(tmp / "trials.parquet", False)
    t = synth["close"].index[-1]
    close = synth["close_raw"].loc[t]
    held_syms = list(close.sort_values().index[-6:-3])  # trois titres chers détenus
    holdings = {s: int(400_000 // close[s]) + 1 for s in held_syms}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return R.recommend(t, 20_000_000, panels=synth, holdings=holdings, validation_dir=tmp / "absent",
                           registry_path=reg, notes_store=False, n_boot=500, seed=3, index_evaluation=False)


def test_recommend_synthetic_contract(synth_order, synth):
    o = synth_order
    assert o.variante == "REF" and o.choix["comparaison"] == "A" and o.statut == R.NOT_TESTED
    assert o.phrase_etude == R.PHRASE_ETUDE and o.bandeau == R.BANNER
    L = o.lignes
    t = o.asof
    nav = o.valeur_portefeuille
    # Quotité 1, arrondi vers le bas : cible ≤ ⌊w × valeur / cours⌋ (égale sauf réduction pire cas ou bande).
    for r in L.itertuples(index=False):
        assert float(r.cibles).is_integer() and r.cibles >= 0
        floor_q = math.floor(r.poids_cible * nav / r.cours_reference + 1e-9)
        if r.sens != "aucun" or r.detenus == 0:
            assert r.cibles <= max(floor_q, r.detenus)
        assert math.isclose(r.poids_realise, r.cibles * r.cours_reference / nav)
        lp = R.limit_prices(r.cours_reference)
        assert (r.borne_basse, r.borne_haute) == (lp["low"], lp["high"])
        if r.sens == "achat":
            assert r.prix_limite == lp["buy"] and r.montant_net >= r.montant_brut
        elif r.sens == "vente":
            assert r.prix_limite == lp["sell"] and r.montant_net <= r.montant_brut
        # Coûts détaillés cohérents au franc près.
        assert r.frais_explicites == r.courtage + r.tva + r.brvm + r.dcbr + r.redevance
        assert r.couts_total == r.frais_explicites + r.demi_spread + r.impact
    # Le plan est finançable dans le pire cas (tout exécuté à la limite).
    assert o.execution["liquidites_finales_pire_cas"] >= 0 and not o.execution["non_finance"]
    k = o.couts
    assert k["achats_pire_cas"] <= o.liquidites_initiales + k["ventes_pire_cas"]
    assert k["total"] == int(L["couts_total"].sum())
    # Des titres détenus non retenus sont vendus ; les ventes précèdent les achats qu'elles financent.
    tab = o.tranches
    assert set(tab.loc[tab["sens"] == "vente", "symbole"]) == set(L.loc[L["sens"] == "vente", "symbole"])
    sells = tab[tab["sens"] == "vente"]
    for r in tab[(tab["sens"] == "achat") & (tab["produit_ventes_utilise"] > 0)].itertuples(index=False):
        assert r.date >= sells["date_reglement"].min()
    # Échéancier : la somme des tranches égale la quantité de chaque ordre.
    got = tab.groupby("symbole")["titres"].sum()
    for r in L[L["sens"] != "aucun"].itertuples(index=False):
        assert int(got[r.symbole]) == int(r.quantite)
    # Distribution : fenêtre S0 seulement, aucune donnée de S1.
    assert o.distribution["disponible"] and not o.distribution["s1_utilise"] and not o.meta["s1_lu"]
    assert pd.Timestamp(o.distribution["debut"]) > R.S1_END
    # Fenêtre S0 seulement : biais haussier signalé dans la distribution et dans les avertissements.
    assert "optimiste" in o.distribution["biais_fenetre"] and o.distribution["biais_fenetre"] in o.avertissements
    # Dividendes, déclencheurs, explications, comparaison.
    assert o.revenus["net"] == int(o.dividendes["montant_net"].sum())
    assert o.declencheurs["rebalancement"]["prochaine_revue"] > t
    assert {e["statut"] for e in o.explications} <= {"retenu", "écarté"}
    assert sum(e["statut"] == "écarté" for e in o.explications) == 5
    assert o.comparaison is not None and o.comparaison["variante"] == "A"
    assert {s["code"] for s in o.stress} >= {"ST1", "ST3", "ST4", "ST8"}


def test_recommend_exports(synth_order):
    o = synth_order
    d = o.to_dict()
    json.dumps(d, ensure_ascii=False)  # sérialisable
    assert d["bandeau"] == R.BANNER and d["statut"] == R.NOT_TESTED and d["phrase_etude"] == R.PHRASE_ETUDE
    md = o.to_markdown()
    assert R.BANNER in md and "paper trading" in md and "pas une prévision" in md
    assert "Faits (publiés ou réglementaires)" in md and "Hypothèses (supposées, non vérifiées)" in md
    h = o.to_html_fragment()
    assert h.startswith('<section class="brvm-ordre-de-bataille"') and h.rstrip().endswith("</section>")
    assert "<html" not in h and "<script" not in h and "Performance passée ≠ garantie." in h


def test_recommend_variant_from_candidate_metrics(synth, tmp_path):
    reg = _registry(tmp_path / "trials.parquet", True)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        o = R.recommend(synth["close"].index[-1], 10_000_000, panels=synth, validation_dir=_metrics(tmp_path, "CANDIDAT"),
                        registry_path=reg, notes_store=False, n_boot=200, index_evaluation=False, explanations=False,
                        comparison=False)
    assert o.variante == "A" and o.statut == "CANDIDAT" and o.phrase_etude == R.PHRASE_ETUDE
    # Le registre indique S1 exécuté : la fenêtre d'estimation couvre toute l'histoire disponible.
    assert o.meta["fenetre_estimation"]["s1_utilise"] is True
    assert o.lignes["cibles"].sum() > 0 and o.execution["n_seances"] >= 1


def test_recommend_rejects_bad_inputs(synth, tmp_path):
    t = synth["close"].index[-1]
    with pytest.raises(ValueError):
        R.recommend(t, 0, panels=synth, notes_store=False)
    with pytest.raises(ValueError):
        R.recommend(t, 1e7, panels=synth, holdings={"XXXX": 10}, notes_store=False)
    with pytest.raises(ValueError):
        R.recommend(t, 1e7, panels=synth, holdings={synth["close"].columns[0]: -5}, notes_store=False)


# ---------------------------------------------------------------------------
# Panel réel au 20/11/2026 (S0) : contrôles de forme
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def real_order(tmp_path_factory):
    if not HAS_PANEL:
        pytest.skip("panel réel absent (data/panel)")
    tmp = tmp_path_factory.mktemp("reel")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return R.recommend("2026-11-20", 10_000_000, validation_dir=tmp / "absent",
                           registry_path=_registry(tmp / "trials.parquet", False), notes_store=False,
                           n_boot=1000, index_evaluation=False)


def test_recommend_real_20261120(real_order):
    o = real_order
    assert o.asof == pd.Timestamp("2026-11-20") and o.variante == "REF" and o.choix["comparaison"] == "A"
    assert o.execution["premiere_seance"] == pd.Timestamp("2026-11-23")
    snts = o.lignes.set_index("symbole").loc["SNTS"]
    assert snts["cours_reference"] == 4040.0
    assert (snts["borne_basse"], snts["borne_haute"], snts["prix_limite"]) == (3740.0, 4340.0, 4080.0)
    assert snts["cibles"] == math.floor(snts["poids_cible"] * 10_000_000 / 4040.0 + 1e-9)
    assert int((o.lignes["cibles"] > 0).sum()) == 20  # D8 : 20 plus grosses capitalisations éligibles
    assert o.couts["investi_pct"] <= 0.98 + 1e-12
    assert o.execution["liquidites_finales_pire_cas"] >= 0
    assert not o.distribution["s1_utilise"] and pd.Timestamp(o.distribution["debut"]) > R.S1_END
    assert o.declencheurs["rebalancement"]["prochaine_revue"] == pd.Timestamp("2026-11-30")
    assert o.declencheurs["rebalancement"]["rebalancement_annuel"] == pd.Timestamp("2027-01-29")
    sn = o.dividendes.set_index("symbole").loc["SNTS"]
    assert sn["facteur_division"] == 10.0 and math.isclose(sn["dividende_net_ajuste"], 174.0)
    assert sn["taux_irvm_prevu"] == 0.10


def test_package_exports():
    import brvm_alpha.portfolio as P
    from brvm_alpha.portfolio import OrdreDeBataille, choose_variant, ordre_de_bataille, recommend

    assert callable(recommend) and recommend is R  # sous-module appelable comme sa fonction
    assert ordre_de_bataille is R.recommend and OrdreDeBataille is R.OrdreDeBataille
    assert choose_variant is R.choose_variant and "recommend" in P.__all__


def test_publication_events_from_notes_history():
    """Publications attendues = dernière publication connue (journal des notes) + 1 an ; une note
    inconnue à l'instant de connaissance n'est pas lue."""
    t = pd.Timestamp("2026-11-20")
    frame = pd.DataFrame([
        {"event_type": "RES_ANNUAL", "published_at": "2026-03-10T19:00:00Z", "targets": ["SNTS"], "all_targets": ["SNTS"]},
        {"event_type": "RES_S1", "published_at": "2025-09-15T19:00:00Z", "targets": ["SNTS"], "all_targets": ["SNTS"]},
        {"event_type": "RES_S1", "published_at": "2026-12-01T19:00:00Z", "targets": ["SNTS"], "all_targets": ["SNTS"]},
        {"event_type": "OTHER", "published_at": "2026-05-01T19:00:00Z", "targets": ["SNTS"], "all_targets": ["SNTS"]},
    ])
    rows = R._publication_events(frame, t, ["SNTS", "ORAC"], t + pd.DateOffset(months=12))
    got = {(r["date"], r["description"].split(" (")[0]) for r in rows}
    assert got == {(pd.Timestamp("2027-03-10"), "comptes annuels"), (pd.Timestamp("2027-09-15"), "comptes semestriels")}
    assert "+ 2 an(s)" in next(r["description"] for r in rows if "semestriels" in r["description"])


def test_own_stress_scenarios_hand_computed():
    """Chocs de repli du §9.3 (si ``portfolio/stress.py`` est absent) : β = 1 supposé."""
    values = {"SNTS": 1_000_000.0, "BOAM": 500_000.0, "SGBC": 1_000_000.0}
    rows = {r["code"]: r for r in R.stress_scenarios(values, 3_000_000.0, beta=None)}
    assert rows["ST1"]["perte_fcfa"] == -1_167_500  # −46,7 % × 2,5 M
    assert rows["ST3"]["perte_fcfa"] == -375_000
    # AES : BOAM (Mali, λ = 1) + part malienne de SNTS (λ_ML = 0,238) : −26 % × 738 000.
    assert rows["ST4"]["perte_fcfa"] == -191_880
    assert rows["ST5"]["perte_fcfa"] == -260_000  # titres sénégalais (SNTS) −26 %
    assert rows["ST8"]["perte_fcfa"] == -300_000  # plus grosse ligne −30 %
    assert math.isclose(rows["ST1"]["perte_pct"], -1_167_500 / 3_000_000)
