"""Tests de non-régression des corrections de la vérification finale du moteur v1 (22/11/2026).

Données **synthétiques** (``test_strategy_alpha.make_panels``, séances de 2023-2024) : aucun
backtest, aucune performance ni aucun IC sur l'échantillon vierge S1.
"""

from __future__ import annotations

import pandas as pd

from brvm_alpha import cli
from test_strategy_alpha import make_panels


def test_cli_universe_line_keeps_comma_and_formats_floor(monkeypatch, capsys):
    """La ligne d'en-tête de ``universe`` garde sa virgule ; seul le plancher U5 a un séparateur de milliers.

    Avant la correction, ``.replace(",", " ")`` s'appliquait à toute la ligne : « 30 titres
    éligibles  mode selection » (virgule perdue).
    """
    synth = make_panels()
    import brvm_alpha.strategy as strategy

    monkeypatch.setattr(strategy, "build_panels", lambda *a, **k: synth)
    t = synth["close"].index[400]
    assert cli.main(["universe", "--date", str(t.date()), "--capital", "100000000"]) == 0
    out = capsys.readouterr().out
    first = out.splitlines()[0]
    # Recette du 22/11/2026 : date au format français, titres cotés puis éligibles, mode en français, bannière.
    assert f"Univers au {pd.Timestamp(t):%d/%m/%Y} : " in first
    assert " titres cotés, dont " in first and " éligibles ; mode sélection " in first  # ponctuation conservée
    assert "(plancher U5 5 000 000 FCFA)" in first  # max(0,5 M ; 0,05 × 100 M), séparateur de milliers
    assert out.rstrip().endswith(cli.BANNER)


def test_relative_drawdown_diagnostic_after_stop_reports_no_halving():
    """Après l'arrêt (−20 %, §9.1), le mode « indice discipliné » est définitif : le diagnostic ne
    doit plus annoncer la division par 2 (``halve``) même si le drawdown remonte entre −20 % et −15 %.

    Avant la correction, ``diagnostics["relative_drawdown"]["halve"]`` valait ``True`` en mode
    indice alors qu'aucune division par 2 n'était appliquée (diagnostic trompeur).
    """
    from brvm_alpha.strategy import BrvmAlpha

    synth = make_panels()
    idx = synth["close"].index
    mt = synth["market_tr"]
    m = BrvmAlpha(notes=None)
    t0, t1, t2 = idx[300], idx[330], idx[390]
    m.record_nav(t0, 1e7)
    m.record_nav(t1, 1e7 * mt[t1] / mt[t0] * 0.79)  # −21 % contre le TR : arrêt
    assert m.decide(t1, synth).diagnostics["relative_drawdown"].get("stop")
    m.record_nav(t2, 1e7 * mt[t2] / mt[t0] * 0.84)  # −16 % : seuil de division franchi, mais arrêt définitif
    dec = m.decide(t2, synth)
    rel = dec.diagnostics["relative_drawdown"]
    assert dec.diagnostics["mode"] == "indice_discipline"
    assert abs(rel["dd"] + 0.16) < 1e-9  # drawdown toujours suivi
    assert not rel.get("halve") and not rel.get("stop") and rel.get("tracking_only")
