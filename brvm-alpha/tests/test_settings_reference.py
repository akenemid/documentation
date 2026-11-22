"""Tests des paramètres de la stratégie v1 (``configs/strategy_v1.yaml``, ``settings.py``)
et des données de référence (``reference.py``).

Aucun test ne calcule de performance : les contrôles sur le panel réel sont des contrôles
de forme (nombre de titres, capitalisation, secteurs, dates de publication).
"""

from __future__ import annotations

import copy
import re
from dataclasses import fields
from pathlib import Path

import pandas as pd
import pytest
import yaml

from brvm_alpha import reference as ref
from brvm_alpha.config import Constraints, CostModel, ExecutionModel, PlatformConfig, UniverseFilter
from brvm_alpha.settings import (
    COST_SCENARIOS,
    DEFAULT_STRATEGY_PATH,
    StrategyConfigError,
    apply_to_platform_config,
    config_fingerprint,
    cost_scenario,
    cost_scenarios,
    country_cap_params,
    get_param,
    half_spread_default,
    load_strategy_config,
    mdv_floor_params,
    n_holdings_params,
    one_way_cost_estimate,
    sector_cap_params,
    validate_strategy_config,
)

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "docs" / "SPECIFICATION_STRATEGIE.md"
REVIEW_01 = ROOT / "docs" / "research" / "01-structure-marche.md"
PANEL = ROOT / "data" / "panel"
needs_panel = pytest.mark.skipif(not (PANEL / "equities.parquet").exists(), reason="panel réel absent")


@pytest.fixture(scope="module")
def cfg() -> dict:
    return load_strategy_config()


def _spec_yaml_block() -> dict:
    text = SPEC.read_text(encoding="utf-8")
    m = re.search(r"### 12\.1 Fichier `brvm_alpha/config/strategy_v1\.yaml`\s*```yaml\n(.*?)```", text, re.S)
    assert m, "bloc YAML du §12.1 introuvable dans la spécification"
    return yaml.safe_load(m.group(1))


# ---------------------------------------------------------------------------
# Fichier YAML et validation
# ---------------------------------------------------------------------------


def test_yaml_file_location_and_identical_to_spec(cfg: dict) -> None:
    assert DEFAULT_STRATEGY_PATH == ROOT / "configs" / "strategy_v1.yaml"
    assert cfg == _spec_yaml_block()  # mêmes clés, mêmes valeurs que le §12.1
    assert cfg["version"] == "1.0"
    assert cfg["capital_fcfa_reference"] == 10_000_000
    assert cfg["capacity_variants_fcfa"] == [100_000_000, 1_000_000_000]
    header = DEFAULT_STRATEGY_PATH.read_text(encoding="utf-8").splitlines()[:4]
    assert any("configs/strategy_v1.yaml" in line for line in header)


def test_key_values_of_the_spec(cfg: dict) -> None:
    assert cfg["composite"]["A"] == {"ep": 0.15, "dy": 0.20, "mom6_1": 0.35, "lowvol": 0.20, "quality_proxy": 0.10}
    assert get_param(cfg, "universe.min_free_float") == 0.15
    assert get_param(cfg, "data.eps_override") == {"ETIT": 10.00, "ORGT": 264}
    assert get_param(cfg, "data.exclude_stats_windows") == [["2021-05-06", "2021-06-25"]]
    assert get_param(cfg, "validation.samples.S1_preregistered") == ["2017-01-02", "2022-11-16"]
    assert get_param(cfg, "validation.samples.S0_contaminated") == ["2022-11-17", "2026-11-20"]
    assert get_param(cfg, "validation.n_trials_start") == 63
    assert get_param(cfg, "macro_overlay.rf_local.confirm_sessions") == 5
    with pytest.raises(KeyError):
        get_param(cfg, "portfolio.inexistant")
    assert get_param(cfg, "portfolio.inexistant", 7) == 7


def test_formula_parsers(cfg: dict) -> None:
    assert n_holdings_params(cfg) == {"divisor": 3, "min": 12, "max": 20}
    assert sector_cap_params(cfg) == {"floor": 0.15, "cap": 0.45, "mult": 1.5}
    assert country_cap_params(cfg) == {"cap": 0.30, "floor": 0.10, "mult": 1.5}
    assert mdv_floor_params(cfg) == (500_000.0, 0.05)
    assert half_spread_default(cfg) == pytest.approx(0.0035)


def test_validation_rejects_bad_files(cfg: dict) -> None:
    validate_strategy_config(cfg)
    bad = copy.deepcopy(cfg)
    del bad["portfolio"]["max_weight"]
    with pytest.raises(StrategyConfigError, match="portfolio.max_weight"):
        validate_strategy_config(bad)
    bad = copy.deepcopy(cfg)
    bad["costs"]["brvm_fee"] = "1e-3"  # PyYAML lit « 1e-3 » comme une chaîne
    with pytest.raises(StrategyConfigError, match="costs.brvm_fee doit être un nombre"):
        validate_strategy_config(bad)
    bad = copy.deepcopy(cfg)
    bad["composite"]["A"]["ep"] = 0.25
    with pytest.raises(StrategyConfigError, match="composite.A"):
        validate_strategy_config(bad)
    bad = copy.deepcopy(cfg)
    bad["execution"]["max_volume_participation"] = 1.5
    with pytest.raises(StrategyConfigError, match="hors de l'intervalle"):
        validate_strategy_config(bad)
    bad = copy.deepcopy(cfg)
    bad["costs"]["scenarios"]["stress"]["sgi"] = None
    with pytest.raises(StrategyConfigError, match="costs.scenarios.stress.sgi"):
        validate_strategy_config(bad)
    bad = copy.deepcopy(cfg)
    bad["portfolio"]["n_holdings"] = "entre 12 et 20"
    with pytest.raises(StrategyConfigError, match="n_holdings"):
        validate_strategy_config(bad)
    bad = copy.deepcopy(cfg)
    bad["validation"]["samples"]["S1_preregistered"] = ["2017-01-02", "2023-06-30"]  # chevauche S0
    with pytest.raises(StrategyConfigError, match="S1 doit précéder S0"):
        validate_strategy_config(bad)
    with pytest.raises(StrategyConfigError):
        validate_strategy_config(["pas", "un", "dict"])  # type: ignore[arg-type]


def test_load_with_overrides_and_fingerprint(tmp_path: Path, cfg: dict) -> None:
    over = load_strategy_config(overrides={"portfolio": {"max_weight": 0.08}})
    assert over["portfolio"]["max_weight"] == 0.08
    assert over["portfolio"]["min_weight"] == 0.02  # fusion en profondeur
    assert cfg["portfolio"]["max_weight"] == 0.10  # l'original n'est pas modifié
    assert config_fingerprint(cfg) == config_fingerprint(load_strategy_config())
    assert config_fingerprint(over) != config_fingerprint(cfg)
    with pytest.raises(StrategyConfigError):
        load_strategy_config(overrides={"universe": {"min_free_float": "quinze"}})
    with pytest.raises(FileNotFoundError):
        load_strategy_config(tmp_path / "absent.yaml")
    p = tmp_path / "s.yaml"
    p.write_text("- 1\n- 2\n", encoding="utf-8")
    with pytest.raises(StrategyConfigError):
        load_strategy_config(p)


# ---------------------------------------------------------------------------
# Correspondance avec config.py
# ---------------------------------------------------------------------------


def test_apply_to_platform_config_gives_config_defaults(cfg: dict) -> None:
    pc = apply_to_platform_config(cfg)
    default = PlatformConfig()
    for name in ("costs", "taxes", "constraints", "execution", "universe"):
        assert getattr(pc, name) == getattr(default, name), name
    assert pc == default
    assert apply_to_platform_config() == default  # lecture du fichier livré


def test_apply_to_platform_config_keeps_base_fields_and_scenario(cfg: dict) -> None:
    base = PlatformConfig(trading_days=248, data_dir="ailleurs")
    base.taxes.dividend_withholding["TG"] = 0.0
    pc = apply_to_platform_config(cfg, base=base, scenario="stress")
    assert pc.trading_days == 248 and pc.data_dir == "ailleurs"
    assert pc.taxes.dividend_withholding["TG"] == 0.0
    assert pc.costs.sgi_commission == 0.010 and pc.costs.half_spread_mult == 1.5
    assert base.costs == CostModel()  # base intacte
    over = load_strategy_config(overrides={"portfolio": {"n_holdings": "clip(round(N_elig/3), 10, 25)"},
                                           "execution": {"carry_unfilled_max_sessions": 0}})
    pc = apply_to_platform_config(over)
    assert (pc.constraints.min_names, pc.constraints.max_names) == (10, 25)
    assert pc.execution.carry_unfilled is False and pc.execution.max_carry_sessions == 0


def test_config_dataclasses_are_spec_values() -> None:
    c, k, x, u = CostModel(), Constraints(), ExecutionModel(), UniverseFilter()
    assert (c.sgi_commission, c.brvm_fee, c.dcbr_fee, c.regulator_fee, c.vat_on_commission) == (0.008, 0.002, 0.001, 0.0, 0.18)
    assert (c.impact_coef, c.annual_custody, c.half_spread_default, c.account_fee_per_line_fcfa) == (0.016, 0.0025, 0.0035, 5000)
    assert c.half_spread_mult == 1.0  # champ ajouté pour les scénarios du §7.2
    assert (k.max_weight, k.min_weight, k.max_names, k.min_names, k.max_sector_weight) == (0.10, 0.02, 20, 12, 0.45)
    assert (k.max_country_weight, k.max_adv_participation) == (0.30, 0.10)
    assert (x.max_volume_participation, x.max_carry_sessions, x.settlement_switch_date) == (0.10, 10, "2025-12-04")
    assert u.mdv_floor(10_000_000) == 500_000 and u.mdv_floor(100_000_000) == 5_000_000
    assert u.mdv_floor(1_000_000_000) == 50_000_000


# ---------------------------------------------------------------------------
# Scénarios de coûts (§7.2)
# ---------------------------------------------------------------------------


def test_cost_scenarios_subtotals_match_spec(cfg: dict) -> None:
    sc = cost_scenarios(cfg)
    assert tuple(sc) == COST_SCENARIOS
    # Sous-totaux proportionnels aller du §7.2 : 0,85 / 1,244 / 1,48 / 2,07 %.
    expected = {"optimistic": 0.0085, "central": 0.01244, "stress": 0.0148, "severe": 0.0207}
    for name, rate in expected.items():
        assert sc[name].rate() == pytest.approx(rate, abs=1e-12), name
    assert [sc[n].half_spread_mult for n in COST_SCENARIOS] == [1.0, 1.0, 1.5, 2.0]
    assert [sc[n].impact_coef for n in COST_SCENARIOS] == [0.010, 0.016, 0.032, 0.050]
    assert [sc[n].annual_custody for n in COST_SCENARIOS] == [0.0, 0.0025, 0.005, 0.005]
    assert [sc[n].account_fee_per_line_fcfa for n in COST_SCENARIOS] == [0, 5000, 5000, 10000]
    assert sc["central"] == CostModel()


def test_cost_scenario_aliases_and_errors(cfg: dict) -> None:
    assert cost_scenario("optimiste", cfg) == cost_scenario("optimistic", cfg)
    assert cost_scenario("sévère", cfg) == cost_scenario("severe", cfg)
    assert cost_scenario("Central", cfg) == CostModel()
    assert cost_scenario("stress") == cost_scenario("stress", cfg)  # lecture du fichier par défaut
    with pytest.raises(KeyError):
        cost_scenario("catastrophe", cfg)


def test_one_way_cost_estimate_order_of_magnitude() -> None:
    central = cost_scenario("central")
    # §7.2 : titre médian (demi-spread 0,35 %, participation 1 %) : 1,244 + 0,35 + 0,16 ≈ 1,75 %.
    assert one_way_cost_estimate(central, participation=0.01) == pytest.approx(0.01754, abs=1e-6)
    # SNTS / SGBC (demi-spread ≈ 0,13 %) : « environ 1,4 % » au §7.2, soit 1,244 + 0,13 sans impact
    # (participation quasi nulle sur ces titres liquides) ; à 1 % de participation : ≈ 1,53 %.
    assert one_way_cost_estimate(central, half_spread=0.0013) == pytest.approx(0.014, abs=5e-4)
    assert one_way_cost_estimate(central, half_spread=0.0013, participation=0.01) == pytest.approx(0.01534, abs=1e-6)
    stress = cost_scenario("stress")
    assert one_way_cost_estimate(stress, half_spread=0.0035) == pytest.approx(0.0148 + 1.5 * 0.0035)


# ---------------------------------------------------------------------------
# Référentiel : nombre de titres, flottant
# ---------------------------------------------------------------------------


def _review01_table() -> dict[str, list[str]]:
    rows = {}
    for line in REVIEW_01.read_text(encoding="utf-8").splitlines():
        if line.startswith("| ") and line.count("|") >= 12:
            c = [x.strip() for x in line.strip("|").split("|")]
            if re.fullmatch(r"[A-Z]{3,6}", c[0]) and re.fullmatch(r"[\d  ]+", c[7]):
                rows[c[0]] = c
    return rows


def test_shares_outstanding_match_review_01_table() -> None:
    table = _review01_table()
    assert len(table) == 48
    parsed = {s: int(re.sub(r"\D", "", c[7])) for s, c in table.items()}
    assert parsed == ref.SHARES_OUTSTANDING_2026
    assert set(ref.SHARES_OUTSTANDING_2026) == set(ref.SYMBOLS_2026)


def test_free_float_matches_review_01_table() -> None:
    table = _review01_table()
    for sym, c in table.items():
        pct = float(re.match(r"[\d,]+", c[8]).group(0).replace(",", "."))
        assert ref.FREE_FLOAT_AVIS_303_2026[sym] * 100 == pytest.approx(pct, abs=0.051), sym
    exact = {"UNLC": 0.0022, "CFAC": 0.0415, "SEMC": 0.1029, "SICC": 0.1226, "BICC": 0.3251, "BOAN": 0.4094, "PRSC": 1.0}
    for sym, v in exact.items():
        assert ref.free_float(sym) == v


def test_free_float_point_in_time_and_u4() -> None:
    assert ref.free_float("UNLC", "2026-11-20") == 0.0022
    assert ref.free_float("UNLC", "2026-10-13") is None  # avis du 12/10/2026, utilisable 2 séances après
    assert ref.free_float("UNLC", "2026-10-14") == 0.0022
    assert ref.free_float("UNLC", "2020-06-30", allow_backfill=True) == 0.0022  # hypothèse déclarée
    assert ref.free_float("XXXX", "2026-11-20") is None
    t = ref.free_float_table("2026-11-20")
    below = set(t[t < ref.MIN_FREE_FLOAT_REGULATORY].index)
    assert below == {"UNLC", "CFAC", "SEMC", "SICC"}  # exclusions U4 au 20/11/2026 (spéc. §2)
    assert ref.free_float_table("2026-01-31").isna().all()


@needs_panel
def test_free_float_and_document_availability_dates_are_two_sessions_after() -> None:
    sess = pd.read_parquet(PANEL / "sessions.parquet")["date"].dropna().sort_values()

    def plus2(d: str) -> pd.Timestamp:
        return sess[sess > pd.Timestamp(d)].iloc[1]

    assert plus2(ref.AVIS_303_2026.document_date) == pd.Timestamp(ref.AVIS_303_2026.available_from)
    for rec in ref.EPS_OVERRIDES.values():
        assert plus2(rec.document_date) == pd.Timestamp(rec.available_from), rec.symbol
    for rec in ref.DIVIDEND_ABSENCES:
        if rec.fiscal_year is not None:
            assert plus2(rec.document_date) == pd.Timestamp(rec.available_from), rec.symbol


def test_shares_outstanding_safc_change() -> None:
    assert ref.shares_outstanding("SAFC") == 11_869_750
    assert ref.shares_outstanding("SAFC", "2026-08-10") == 8_119_750
    assert ref.shares_outstanding("SAFC", "2026-08-11") == 11_869_750
    assert ref.shares_outstanding("SNTS", "2017-01-02") == 1_000_000_000  # pas de remontée des divisions ici
    assert ref.shares_outstanding("SVOC") is None


@needs_panel
def test_reconstructed_cap_matches_boc_on_20261120() -> None:
    eq = pd.read_parquet(PANEL / "equities.parquet")
    last = eq[eq["date"] == pd.Timestamp("2026-11-20")].set_index("symbol")["close"]
    cap = sum(ref.SHARES_OUTSTANDING_2026[s] * last[s] for s in ref.SHARES_OUTSTANDING_2026)
    mk = pd.read_parquet(PANEL / "market.parquet").set_index("date")["market_cap"]
    assert cap / mk.loc["2026-11-20"] == pytest.approx(1.0, abs=0.001)  # 19 330 contre 19 328,8 Md
    w = ref.reference_country_weights(last)
    for c, v in ref.REFERENCE_COUNTRY_WEIGHTS_20261120.items():
        assert w.get(c, 0.0) == pytest.approx(v, abs=6e-4), c
    aes = sum(w[c] for c in ref.AES_COUNTRIES)
    assert 1.25 * aes == pytest.approx(0.106, abs=0.001)  # plafond AES par siège ≈ 10,6 % (§4.2)
    lam = ref.reference_country_weights(last, by="exposure")
    assert lam.sum() == pytest.approx(1.0)
    assert lam["ML"] == pytest.approx(0.057, abs=0.002)  # revue 05 §11.2, variante détention ≈ 5,7 %


# ---------------------------------------------------------------------------
# Pays, exposition, BPA, dividendes, comptes, secteurs
# ---------------------------------------------------------------------------


def test_country_multipliers() -> None:
    assert ref.COUNTRY_MULTIPLIER == {"CI": 1.0, "BJ": 1.0, "TG": 0.9, "SN": 0.85, "BF": 0.75, "ML": 0.7, "NE": 0.6}
    assert ref.country_multiplier("SNTS") == 0.85
    assert ref.country_multiplier("BOAN") == 0.6
    assert ref.country_multiplier("ETIT") == 0.9
    assert ref.country_multiplier("CI") == 1.0
    assert ref.country_multiplier("GW") == 0.6  # aucun titre : plus petit multiplicateur
    assert sum(ref.REFERENCE_COUNTRY_WEIGHTS_20261120.values()) == pytest.approx(1.0, abs=1e-9)


def test_economic_exposure() -> None:
    snts = ref.economic_exposure("SNTS")
    assert snts == {"SN": 0.401, "ML": 0.238, "GN": 0.274, "SL": 0.045, "GW": 0.042}
    assert sum(snts.values()) == pytest.approx(1.0)
    assert sum(ref.economic_exposure("SNTS", "clients").values()) == pytest.approx(1.0)
    assert ref.economic_exposure("ETIT") == {"PANAFRICAIN": 1.0}
    assert ref.economic_exposure("BOAM") == {"ML": 1.0}
    assert ref.economic_exposure("ORGT") == {"TG": 1.0}  # λ = 1 pour le siège (spéc. §4.1)
    m = ref.exposure_matrix(["SNTS", "ETIT", "SGBC"])
    assert m.sum(axis=1).tolist() == pytest.approx([1.0, 1.0, 1.0])
    with pytest.raises(ValueError):
        ref.economic_exposure("SNTS", "inconnue")


def test_eps_overrides_point_in_time() -> None:
    assert ref.eps_override("ETIT", "2026-11-20") == 10.00
    assert ref.eps_override("ETIT", "2026-04-14") is None  # comptes du 13/04/2026, + 2 séances
    assert ref.eps_override("ETIT", "2026-04-15") == 10.00
    assert ref.eps_override("ORGT", "2026-05-05") is None
    assert ref.eps_override("ORGT", "2026-05-06") == 264.0
    assert ref.eps_override("SNTS", "2026-11-20") is None
    assert ref.eps_override("ETIT") == 10.00
    assert ref.eps_override("ETIT", "2026-11-20") / 57 == pytest.approx(10 / 57)  # spéc. §12.3 n° 5 : ep(ETIT)


def test_announced_dividend_absences() -> None:
    boan = ref.announced_no_dividend("BOAN", "2026-11-20", last_payment_date="2025-06-03")
    assert boan is not None and boan.fiscal_year == 2025
    assert ref.announced_no_dividend("BOAN", "2026-04-30") is None  # communiqué du 29/04, + 2 séances
    assert ref.announced_no_dividend("BOAN", "2027-08-01", last_payment_date="2027-06-15") is None  # caduc
    assert ref.announced_no_dividend("ORGT", "2026-11-20", last_payment_date="2020-07-17") is not None
    safc = ref.announced_no_dividend("SAFC", "2018-06-29", last_payment_date="2011-07-29")
    assert safc is not None and safc.since == "2011-07-29"
    assert ref.announced_no_dividend("FTSC", "2026-03-31") is None  # AGO 2025 pas encore connue (revue 06b)
    assert ref.announced_no_dividend("FTSC", "2026-11-20", last_payment_date="2025-09-30") is not None
    assert ref.announced_no_dividend("SNTS", "2026-11-20") is None


def test_exceptional_dividend_ftsc() -> None:
    rec = ref.EXCEPTIONAL_DIVIDENDS[0]
    assert rec.gross_ordinary * (1 - 0.12) == pytest.approx(rec.net_ordinary)
    assert rec.gross_exceptional * (1 - 0.17) == pytest.approx(rec.net_exceptional, abs=0.01)
    assert rec.net_ordinary + rec.net_exceptional == pytest.approx(rec.net_total, abs=0.01)
    assert ref.ordinary_dividend_net("FTSC", "2025-09-30", 1726.56) == 1161.60
    assert ref.ordinary_dividend_net("FTSC", "2025-09-26", 1726.56) == 1161.60  # par la date ex
    assert ref.ordinary_dividend_net("FTSC", "2024-09-30", 143.10) == 143.10
    assert ref.ordinary_dividend_net("SNTS", "2025-09-30", 1726.56) == 1726.56


@needs_panel
def test_exceptional_dividend_matches_panel() -> None:
    dv = pd.read_parquet(PANEL / "dividends.parquet")
    row = dv[(dv["symbol"] == "FTSC") & (dv["payment_date"] == pd.Timestamp("2025-09-30"))].iloc[0]
    assert row["amount"] == pytest.approx(1726.56)
    assert ref.ordinary_dividend_net("FTSC", row["ex_date"], row["amount"]) == 1161.60


def test_stale_financials_u9() -> None:
    assert ref.stale_financials("UNLC", "2026-11-20") is True
    assert ref.stale_financials("SEMC", "2026-11-20") is True
    assert ref.stale_financials("UNLC", "2025-01-02") is False
    assert ref.stale_financials("UNLC", "2025-06-29") is False  # 546 jours exactement
    assert ref.stale_financials("UNLC", "2025-06-30") is True
    assert ref.stale_financials("UNLC", "2024-01-31") is None  # comptes 2023 pas encore publiés
    assert ref.stale_financials("SNTS", "2026-11-20") is None  # non relevé
    stale = [s for s in ref.SYMBOLS_2026 if ref.stale_financials(s, "2026-11-20")]
    assert stale == ["SEMC", "UNLC"]


def test_sectors_2025() -> None:
    assert set(ref.SYMBOLS_2026) <= set(ref.SECTOR_2025)
    assert set(ref.SECTOR_2025.values()) <= set(ref.SECTOR_LABELS)
    counts = pd.Series([ref.sector_of(s) for s in ref.SYMBOLS_2026]).value_counts().to_dict()
    assert counts == {"FIN": 17, "CB": 9, "CD": 7, "IND": 6, "ENE": 4, "TEL": 3, "SPU": 2}  # revue 01 §11
    assert ref.sector_of("snts") == "TEL" and ref.sector_of("XXXX") is None
    assert ref.sectors(["SGBC", "ORAC"]).to_dict() == {"SGBC": "FIN", "ORAC": "TEL"}


@needs_panel
def test_sectors_match_boc_20261120() -> None:
    eq = pd.read_parquet(PANEL / "equities.parquet")
    last = eq[eq["date"] == pd.Timestamp("2026-11-20")].set_index("symbol")["sector"]
    assert {s: ref.sector_of(s) for s in last.index} == last.to_dict()
    svoc = eq[eq["symbol"] == "SVOC"].sort_values("date").iloc[-1]
    assert svoc["sector"] == ref.sector_of("SVOC")
    assert str(svoc["date"].date()) == ref.DELISTED_SYMBOLS["SVOC"]


def test_existing_reference_api_unchanged() -> None:
    assert ref.country_of("CBIBF") == "BF" and ref.country_of("ETIT") == "TG" and ref.country_of("BOAN") == "NE"
    assert ref.exposure_of("ETIT") == "PANAFRICAIN"
    assert ref.countries(["SNTS", "SGBC"]).to_dict() == {"SNTS": "SN", "SGBC": "CI"}
    assert len(ref.SYMBOLS_2026) == 48


def test_costmodel_fields_cover_yaml_scenario_fields() -> None:
    names = {f.name for f in fields(CostModel)}
    assert {"sgi_commission", "vat_on_commission", "half_spread_mult", "impact_coef", "annual_custody",
            "account_fee_per_line_fcfa"} <= names
