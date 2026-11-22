"""Paramètres de la plate-forme (frais, fiscalité, contraintes, univers).

Valeurs calibrées d'après ``docs/SPECIFICATION_STRATEGIE.md`` (v1.0 du
22/11/2026), §2, §6, §7 et §11. Les valeurs marquées ``NV`` restent
[NON VÉRIFIÉ] dans la spécification : elles sont prudentes, pas certaines.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CostModel:
    """Coûts d'une transaction sur actions BRVM, en fraction du montant négocié."""

    sgi_commission: float = 0.008  # courtage SGI central (0,005 / 0,010 / 0,015) — spéc. §7.2
    brvm_fee: float = 0.002  # commission BRVM par côté (barème primaire)
    dcbr_fee: float = 0.001  # DC/BR par côté (barème primaire)
    regulator_fee: float = 0.0  # redevance AMF-UMOA : introuvable (spéc. §7.2)
    vat_on_commission: float = 0.18  # taxe sur le courtage, NV (0,10 en variante)
    min_ticket_fcfa: float = 0.0  # frais fixes minimum par ordre
    impact_coef: float = 0.016  # impact κ·√participation (0,010 / 0,032 / 0,050), hypothèse
    annual_custody: float = 0.0025  # droits de garde annuels sur l'encours
    half_spread_default: float = 0.0035  # demi-spread par défaut (spread médian 0,69 % en 2026)
    account_fee_per_line_fcfa: float = 5_000.0  # tenue de compte par ligne et par an (0 chez FGI)

    def rate(self) -> float:
        """Coût proportionnel total d'un aller simple (hors impact)."""
        return (
            self.sgi_commission * (1.0 + self.vat_on_commission)
            + self.brvm_fee
            + self.dcbr_fee
            + self.regulator_fee
        )


@dataclass
class TaxModel:
    """Retenue à la source sur dividendes (IRVM) par pays d'émetteur."""

    dividend_withholding: dict[str, float] = field(
        default_factory=lambda: {  # IRVM personne physique, spéc. §7.3
            "CI": 0.12,  # 10 % jusqu'en 2024 (inférence)
            "SN": 0.10,
            "BF": 0.125,  # NV
            "ML": 0.07,
            "NE": 0.07,
            "BJ": 0.10,  # selon l'émetteur, voir issuer_withholding
            "TG": 0.13,  # inconnu : utiliser le net du BOC
            "GW": 0.10,  # NV
        }
    )
    issuer_withholding: dict[str, float] = field(
        default_factory=lambda: {"LNBB": 0.05, "BICB": 0.05, "BOAB": 0.10}  # inférences, spéc. §7.3
    )
    dividends_reported_net: bool = True  # le BOC publie des dividendes NETS (règle prioritaire)
    capital_gains_tax: float = 0.0  # personne physique résidente, NV


@dataclass
class Constraints:
    """Contraintes de construction de portefeuille."""

    long_only: bool = True  # pas de vente à découvert à la BRVM
    max_weight: float = 0.10  # × multiplicateur pays × réductions U6/U7/R4/R11 (spéc. §6)
    min_weight: float = 0.02  # en dessous : ligne supprimée
    max_names: int = 20
    min_names: int = 12
    max_sector_weight: float = 0.45  # plafond : max(15 % ; min(45 % ; 1,5 × part de l'univers))
    max_country_weight: float = 0.30  # pays ≠ CI : min(30 % ; max(10 % ; 1,5 × max(u_c, b_c)))
    max_adv_participation: float = 0.10  # part max du volume quotidien par séance
    max_days_to_liquidate: float = 20.0  # séances pour sortir d'une ligne à cette participation
    cash_buffer: float = 0.02
    no_trade_band: float = 0.02  # pas de transaction si |Δpoids| < bande
    max_turnover_per_rebalance: float = 0.50


@dataclass
class ExecutionModel:
    """Hypothèses d'exécution du backtest."""

    price: str = "vwap"  # "vwap" (value/volume), "close" ou "open" de t+1
    price_limit: float = 0.075  # bande de variation journalière des actions
    limit_tolerance: float = 0.002  # marge pour considérer un titre « à la limite »
    max_volume_participation: float = 0.10  # part max du volume du jour exécutable
    carry_unfilled: bool = True  # les ordres non exécutés sont reportés
    max_carry_sessions: int = 10  # report au plus 10 séances, puis annulation (spéc. §7.1)
    settlement_switch_date: str = "2025-12-04"  # J+3 avant, J+2 à partir de cette date
    cash_rate_annual: float = 0.0  # rémunération du cash (prudence : 0)


@dataclass
class UniverseFilter:
    """Filtres d'éligibilité (liquidité, historique)."""

    min_history_days: int = 126  # U2 (et ≥ 40 rendements sur 63 séances)
    min_returns_63: int = 40
    min_traded_fraction: float = 0.50  # U3 : part des séances avec échanges (fenêtre 120)
    min_median_value_fcfa: float = 500_000.0  # U5 : plancher de MDV63 (séances sans échange = 0)
    mdv_capital_fraction: float = 0.05  # U5 : MDV63 ≥ max(plancher ; 0,05 × capital)
    low_liquidity_tier_fcfa: float = 2_000_000.0  # U6 : sous ce seuil, poids max ÷ 2
    max_spread_full_weight: float = 0.015  # U7 : spread médian au-delà : poids max ÷ 2
    min_float: float = 0.15  # U4 : flottant minimal
    min_names_for_selection: int = 15  # U10 : sinon panier équipondéré (mode repli)
    stale_financials_days: int = 546  # U9 : comptes annuels périmés
    exclude_suspended: bool = True

    def mdv_floor(self, capital_fcfa: float) -> float:
        """Seuil de capacité U5 : ``max(plancher ; fraction × capital)`` en FCFA."""
        return max(self.min_median_value_fcfa, self.mdv_capital_fraction * float(capital_fcfa))


@dataclass
class PlatformConfig:
    costs: CostModel = field(default_factory=CostModel)
    taxes: TaxModel = field(default_factory=TaxModel)
    constraints: Constraints = field(default_factory=Constraints)
    execution: ExecutionModel = field(default_factory=ExecutionModel)
    universe: UniverseFilter = field(default_factory=UniverseFilter)
    capital_fcfa: float = 10_000_000.0
    trading_days: int = 252
    data_dir: str = "data"
    reports_dir: str = "reports"
