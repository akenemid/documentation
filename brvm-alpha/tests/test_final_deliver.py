"""Tests de non-régression des corrections de la livraison finale (22/11/2026).

Données **synthétiques** (panel de S0 de ``test_report_html``, résultats S1 **factices**) : aucun
backtest, aucune performance, aucun IC ni aucun signal évalué sur l'échantillon vierge S1, aucune
requête réseau.

Constats corrigés (captures du rapport réel à 390 et 1280 px) :

- histogramme de la distribution recalculé avec l'ancienne convention (lignes pas encore cotées
  comptées à 0 %) : médiane différente de celle de l'ordre de bataille (« écart à examiner ») ;
- chemin absolu du dossier de la relance qui débordait de l'écran à 390 px (encadré flexible) ;
- niveaux du graphique des VL lus sans rappeler que la fenêtre du §8.1 est exclue des mesures ;
- seuils, messages du modèle et détails des filtres R au format anglais (« 0.0 », « 98.00% ») ;
- tableau des stress tronqué à 1280 px (colonne « Nature » fusionnée sous le code).
"""

from __future__ import annotations

import copy
import json
import warnings

import numpy as np
import pandas as pd
from test_report_html import (  # noqa: F401 - fixture importée
    _fake_metrics,
    _render,
    _section,
    synth,
)

from brvm_alpha.portfolio import recommend as R
from brvm_alpha.report import html as RH


def test_fr_texte_typographie_francaise():
    """Décimales à virgule, signe moins, espace avant % ; sections, versions et dates intactes."""
    f = R.fr_texte
    assert f("indice discipliné (additif v1.1, D8) : 98.00% investis") == \
        "indice discipliné (additif v1.1, D8) : 98,00 % investis"
    assert f("R11 : payout brut estimé 1.31 > 1") == "R11 : payout brut estimé 1,31 > 1"
    assert f("seuil < -0.01 ⇒ rejet") == "seuil < −0,01 ⇒ rejet"
    assert f("§4.2 ; 17.11.2022 ; MOM6_1") == "§4.2 ; 17.11.2022 ; MOM6_1"
    assert f("notes désactivées (notes=None)") == "notes désactivées (aucun journal de notes transmis)"
    assert RH._fr_txt("≤ 0.0 ⇒ rejet") == "≤ 0,0 ⇒ rejet"


def _weekly_with_late_listing(n: int = 160, seed: int = 4) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2023-01-06", periods=n, freq="W-FRI")
    w = pd.DataFrame({"AAA": rng.normal(0.003, 0.03, n), "BBB": rng.normal(-0.002, 0.03, n),
                      R._BENCH: rng.normal(0.001, 0.02, n)}, index=idx)
    w.iloc[:80, 1] = np.nan  # BBB coté seulement à partir de la 81e semaine
    return w


def test_return_distribution_with_draws_matches_published_quantiles():
    """``with_draws=True`` rend les tirages mêmes de la distribution publiée (médiane identique)."""
    weekly = _weekly_with_late_listing()
    kw = {"horizon_weeks": 52, "n_boot": 400, "mean_block": 8.0, "seed": 2, "cost_drag": 0.01}
    pub = R.return_distribution(weekly, {"AAA": 0.5, "BBB": 0.4}, **kw)
    again = R.return_distribution(weekly, {"AAA": 0.5, "BBB": 0.4}, with_draws=True, **kw)
    assert "tirages_net" not in pub and len(again["tirages_net"]) == 400
    assert abs(float(np.median(again["tirages_net"])) - pub["mediane"]) < 1e-12
    assert abs(float(np.median(again["tirages_tr"])) - pub["tr_mediane"]) < 1e-12
    # L'ancienne reconstruction du rapport (semaines avant cotation comptées à 0 %) donnait une autre médiane.
    sub = weekly[["AAA", "BBB"]].fillna(0.0).to_numpy() @ np.array([0.5, 0.4])
    idx = R.stationary_bootstrap_indices(len(sub), 52, 400, 8.0, 2)
    old = (1.0 + (np.prod(1.0 + sub[idx], axis=1) - 1.0)) * 0.99 - 1.0
    assert abs(float(np.median(old)) - pub["mediane"]) > 1e-6


def test_report_histogram_conforme_with_late_listed_line(synth):  # noqa: F811
    """Ligne cible pas encore cotée au début de la fenêtre : l'histogramme du rapport reprend la
    distribution de l'ordre de bataille (plus de « Histogramme recalculé … à examiner »)."""
    panels = copy.copy(synth["panels"])
    tr = panels["tr_index"].copy()
    tr.iloc[:120, ::2] = np.nan  # un titre sur deux « coté » après 120 séances (S0 synthétique)
    panels["tr_index"] = tr
    # Registre « S1 exécuté » : fenêtre de toute l'histoire du panel, avertissement de biais rétrospectif publié.
    rep = _render(synth, panels=panels, registry_path=synth["reg_yes"], recommend_kwargs={"explanations": False})
    dist = _section(rep.html, "distribution")
    assert "distribution historique" in dist
    assert "Histogramme recalculé" not in dist
    assert "valeur(s) antérieure(s) à la cotation" in rep.html  # le cas « pas encore coté » est bien exercé


def test_report_s1_rerun_box_window_note_and_french_thresholds(synth):  # noqa: F811
    """Encadré de relance : chemin relatif dans ``<code>`` (repliable) ; graphique des VL : rappel de la
    fenêtre du §8.1 ; seuils des critères au format français ; stress : pas de colonne « Nature »."""
    vdir = _fake_metrics(synth["tmp"] / "val_relance", "REJETÉ")
    m = json.loads((vdir / "metrics.json").read_text(encoding="utf-8"))
    m["precedent"] = {"dossier": str(RH.ROOT / "reports" / "validation_S1" / "precedent_20261122T121328Z"),
                      "t0": "2017-08-01"}
    m["fenetres_exclues"] = [["2021-05-06", "2021-06-25"]]
    (vdir / "metrics.json").write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        rep = _render(synth, validation_dir=vdir, registry_path=synth["reg_yes"],
                      recommend_kwargs={"explanations": False})
    h = rep.html
    s1 = _section(h, "s1")
    assert "<code>reports/validation_S1/precedent_20261122T121328Z</code>" in s1
    assert str(RH.ROOT) not in s1
    assert ".box > div { min-width: 0; }" in h  # le texte d'un encadré se replie au lieu de déborder
    assert "fenêtre du §8.1 (06/05/2021 → 25/06/2021)" in s1
    assert "seuil ≤ 0,0 ⇒ rejet" in s1 and "seuil &lt; −0,5 sur l&#x27;une ⇒ rejet" in s1
    dist = _section(h, "distribution")
    assert "Code · nature" in dist and ">Nature</th>" not in dist
    assert "class='muted small cv'" in dist or 'class="muted small cv"' in dist or "Stress" not in dist
