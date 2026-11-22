"""Interface en ligne de commande minimale : ``python -m brvm_alpha <commande>``.

Commandes disponibles (v1) :

* ``universe --date AAAA-MM-JJ [--capital K]`` : univers éligible U1-U10 à une date
  (contrôle de forme : nombre de titres, mode ``selection`` / ``repli`` / ``vide``) ;
* ``backtest --start --end [--variant A] [--capital K] [--costs central]`` : backtest
  quotidien du modèle BRVM Alpha (moteur ``backtest.engine``), résumé **net de coûts** ;
  toute période qui recoupe l'échantillon vierge S1 (2017-01-02 → 2022-11-16) est
  **refusée** sauf drapeau explicite ``--validation-s1`` (réservé au test unique et
  pré-enregistré, qui exige aussi ``--window-basis``).

Les commandes ``update``, ``panel``, ``live``, ``news``, ``analyze`` et ``report`` du contrat
(``docs/ARCHITECTURE.md``) sont **à venir**. Toutes les sorties sont des estimations sous
hypothèses (coûts, exécution) : aucun gain n'est garanti.
"""

from __future__ import annotations

import argparse
import sys
import warnings
from collections.abc import Sequence

import pandas as pd

BANNER = "Performance passée ≠ garantie. Aucun gain n'est garanti."
S1 = ("2017-01-02", "2022-11-16")


def _overlaps_s1(start: str | None, end: str | None) -> bool:
    a = pd.Timestamp(start) if start else pd.Timestamp.min
    b = pd.Timestamp(end) if end else pd.Timestamp.max
    return bool(a <= pd.Timestamp(S1[1]) and b >= pd.Timestamp(S1[0]))


def build_parser() -> argparse.ArgumentParser:
    """Analyseur des arguments (en français)."""
    parser = argparse.ArgumentParser(prog="python -m brvm_alpha", description="BRVM Alpha : outils en ligne de commande")
    sub = parser.add_subparsers(dest="command", required=True)

    u = sub.add_parser("universe", help="univers éligible à une date (contrôle de forme)")
    u.add_argument("--date", required=True, help="date de décision (AAAA-MM-JJ)")
    u.add_argument("--capital", type=float, default=None, help="capital K en FCFA (défaut : 10 M)")
    u.add_argument("--panel-dir", default=None, help="répertoire du panel (défaut : data/panel)")

    b = sub.add_parser("backtest", help="backtest net de coûts (S1 refusé sans --validation-s1)")
    b.add_argument("--start", required=True, help="première séance simulée (AAAA-MM-JJ)")
    b.add_argument("--end", required=True, help="dernière séance simulée (AAAA-MM-JJ)")
    b.add_argument("--variant", default="A", help="variante pré-enregistrée (A … H)")
    b.add_argument("--capital", type=float, default=None, help="capital K en FCFA (défaut : 10 M)")
    b.add_argument("--costs", default="central", help="scénario de coûts : optimistic, central, stress, severe")
    b.add_argument("--window-basis", default=None, choices=("boc", "sessions"),
                   help="comptage des fenêtres (obligatoire avec --validation-s1)")
    b.add_argument("--validation-s1", action="store_true",
                   help="autorise S1 : réservé au test UNIQUE pré-enregistré (§8.1)")
    b.add_argument("--panel-dir", default=None, help="répertoire du panel (défaut : data/panel)")
    return parser


def _cmd_universe(args: argparse.Namespace) -> int:
    from brvm_alpha.strategy import BrvmAlpha, build_panels

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        panels = build_panels(args.panel_dir, end=args.date)
    u = BrvmAlpha(notes=None, capital=args.capital).universe(args.date, panels)
    # séparateur de milliers appliqué au seul montant (et non à toute la ligne, dont la virgule)
    floor = f"{u.attrs['mdv_floor']:,.0f}".replace(",", " ")
    print(f"Univers au {pd.Timestamp(args.date).date()} : {u.attrs['n_eligible']} titres éligibles, "
          f"mode {u.attrs['mode']} (plancher U5 {floor} FCFA)")
    for sym, row in u.iterrows():
        print(f"  {sym:6s} {'oui' if row['eligible'] else 'non'}  {row['reason']}")
    return 0


def _cmd_backtest(args: argparse.Namespace) -> int:
    if _overlaps_s1(args.start, args.end) and not args.validation_s1:
        print(f"refusé : la période {args.start} → {args.end} recoupe l'échantillon vierge S1 "
              f"({S1[0]} → {S1[1]}), réservé à un test unique pré-enregistré (--validation-s1).", file=sys.stderr)
        return 2
    if args.validation_s1 and args.window_basis is None:
        print("refusé : --validation-s1 exige --window-basis (boc ou sessions), à trancher par un addendum "
              "pré-enregistré.", file=sys.stderr)
        return 2
    from brvm_alpha import settings
    from brvm_alpha.backtest.engine import Backtester
    from brvm_alpha.strategy import BrvmAlpha, build_panels

    cfg = settings.apply_to_platform_config(scenario=args.costs)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        panels = build_panels(args.panel_dir, end=args.end)
    history = None if args.validation_s1 else "2022-11-17"
    model = BrvmAlpha(cfg, variant=args.variant, capital=args.capital, notes=None, history_start=history,
                      window_basis=args.window_basis, validation_s1=bool(args.validation_s1))
    bt = Backtester(panels, cfg.costs, cfg.constraints, model.capital, cfg.execution, cfg.taxes,
                    params=settings.load_strategy_config())
    res = bt.run(model.strategy_fn(), rebalance="M", start=args.start, end=args.end)
    s = res.summary(panels.get("market_tr"), benchmark_is_level=True) if "market_tr" in panels else res.summary()
    print(f"Backtest {args.variant} du {args.start} au {args.end} (coûts {args.costs}, estimation sous hypothèses)")
    for key in ("total_return", "cagr", "vol", "max_drawdown", "excess_cagr", "information_ratio", "turnover",
                "total_costs", "n_trades"):
        if key in s:
            print(f"  {key} : {s[key]}")
    print(BANNER)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Point d'entrée : renvoie le code de sortie (0 : succès ; 2 : refus)."""
    args = build_parser().parse_args(argv)
    if args.command == "universe":
        return _cmd_universe(args)
    if args.command == "backtest":
        return _cmd_backtest(args)
    return 2  # pragma: no cover - argparse impose une commande


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
