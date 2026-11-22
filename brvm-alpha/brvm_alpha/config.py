"""Paramètres de la plate-forme (frais, fiscalité, contraintes, univers).

Les valeurs par défaut marquées ``# À CALIBRER`` sont provisoires : elles sont
remplacées par les valeurs sourcées de ``docs/SPECIFICATION_STRATEGIE.md``.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CostModel:
    """Coûts d'une transaction sur actions BRVM, en fraction du montant négocié."""

    sgi_commission: float = 0.006  # À CALIBRER : commission de la SGI (courtier)
    brvm_fee: float = 0.0015  # À CALIBRER : commission de la bourse
    dcbr_fee: float = 0.001  # À CALIBRER : dépositaire central / banque de règlement
    regulator_fee: float = 0.0005  # À CALIBRER : AMF-UMOA
    vat_on_commission: float = 0.18  # À CALIBRER : TVA appliquée à la commission SGI
    min_ticket_fcfa: float = 0.0  # frais fixes minimum par ordre
    impact_coef: float = 0.10  # impact de marché : coef × sqrt(participation)
    annual_custody: float = 0.0  # droits de garde annuels (fraction de l'encours)

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
        default_factory=lambda: {  # À CALIBRER
            "CI": 0.10,
            "SN": 0.10,
            "BF": 0.125,
            "ML": 0.10,
            "NE": 0.10,
            "BJ": 0.10,
            "TG": 0.13,
            "GW": 0.10,
        }
    )
    dividends_reported_net: bool = True  # le BOC publie des dividendes NETS
    capital_gains_tax: float = 0.0  # À CALIBRER


@dataclass
class Constraints:
    """Contraintes de construction de portefeuille."""

    long_only: bool = True  # pas de vente à découvert à la BRVM
    max_weight: float = 0.15
    min_weight: float = 0.02  # en dessous : ligne supprimée
    max_names: int = 15
    min_names: int = 6
    max_sector_weight: float = 0.40
    max_country_weight: float = 0.60
    max_adv_participation: float = 0.20  # part max du volume quotidien moyen par séance
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
    max_volume_participation: float = 0.20  # part max du volume du jour exécutable
    carry_unfilled: bool = True  # les ordres non exécutés sont reportés
    cash_rate_annual: float = 0.0  # rémunération du cash (prudence : 0)


@dataclass
class UniverseFilter:
    """Filtres d'éligibilité (liquidité, historique)."""

    min_history_days: int = 120
    min_traded_fraction: float = 0.50  # part des séances avec échanges (fenêtre 120 j)
    min_median_value_fcfa: float = 2_000_000.0  # valeur médiane échangée par séance
    exclude_suspended: bool = True


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
