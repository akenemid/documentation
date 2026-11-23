"""F10 — Le témoin REF-S2 : fabrique ``temoin_model``, run du moteur existant, journal (cahier ``docs/RENDEMENT_NET.md``,
§F10 et §8.2).

Panel de synthèse daté de S0 (2023-2024) : aucun test ne touche l'échantillon S1, ne lit les données réelles ni n'écrit
sous ``reports/``. Le test de non-régression prouve que REF-S2 est bien la règle testée : la fabrique du témoin redonne,
au franc, les mêmes valeurs et les mêmes ordres que ``brvm_alpha_model`` (celle du test) sur la même fenêtre.
"""

from __future__ import annotations

import functools
import re
from pathlib import Path

import pandas as pd
import pytest

import suivi_jeux as J
from brvm_alpha import settings
from brvm_alpha import suivi as S
from brvm_alpha.suivi import bulletin as BU
from brvm_alpha.suivi import temoin as TM
from brvm_alpha.validation import runner

DEBUT, FIN = "2024-01-31", "2024-06-28"
PAQUET = Path(S.__file__).resolve().parent


@pytest.fixture(scope="module")
def panels():
    return J.panel_moteur()


def _ctx(factory, sample):
    return {"sample": sample, "start": DEBUT, "end": FIN, "decision_mode": "evenementiel",
            "strategy_params": settings.load_strategy_config(), "factory": factory, "capture": ()}


@pytest.fixture(scope="module")
def deux_runs(panels):
    spec = runner.RunSpec("REF", costs="central", capital=10_000_000)
    test = runner.execute_run(spec, panels, _ctx(runner.brvm_alpha_model, "S0"))
    tem = runner.execute_run(spec, panels, _ctx(functools.partial(TM.temoin_model, notes=None,
                                                                  history_start=runner.SAMPLES["S0"].history_start), "S0"))
    return test, tem


def test_fabrique_du_temoin_redonne_la_regle_testee(deux_runs):
    test, tem = deux_runs
    assert test["ok"] and tem["ok"], (test.get("error"), tem.get("error"))
    pd.testing.assert_series_equal(test["equity"], tem["equity"])
    pd.testing.assert_frame_equal(test["trades"], tem["trades"])
    pd.testing.assert_frame_equal(test["cost_breakdown"], tem["cost_breakdown"])
    assert len(test["trades"]) > 0 and test["meta"]["mode_decision"] == tem["meta"]["mode_decision"] == "evenementiel"
    assert "variant='REF'" in tem["meta"]["modele"]


def test_echantillon_S2_sans_toucher_runner(panels):
    assert set(runner.SAMPLES) == {"S1", "S0"}  # runner.py n'est pas modifié
    r = TM.lancer(panels, debut=DEBUT, fin="2024-03-29")
    assert r["ok"], r.get("error")
    ctx = TM.contexte("2024-03-29", debut=DEBUT)
    assert ctx["sample"] == "S2" and ctx["decision_mode"] == "evenementiel" and ctx["capture"] == ()
    assert ctx["factory"].func is TM.temoin_model and ctx["factory"].keywords["notes"] is None
    assert ctx["strategy_params"] == settings.load_strategy_config()
    sp = TM.spec()
    assert (sp.variant, sp.costs, float(sp.capital)) == ("REF", "central", 10_000_000.0)


def test_refus_des_dates_de_S1_et_de_reports(panels, tmp_path):
    with pytest.raises(S.DateDeS1):
        TM.contexte("2023-03-01", debut="2022-11-16")
    with pytest.raises(S.DateDeS1):
        TM.maj("REF-S2", panels, tmp_path, debut="2021-06-30")
    interdit = J.RACINE / "reports" / "suivi_essai_temoin"
    with pytest.raises(S.DossierInterdit):
        TM.maj("REF-S2", panels, interdit, debut=DEBUT, fin="2024-02-29")
    assert not interdit.exists()
    with pytest.raises(ValueError, match="notes"):
        TM.maj("N", panels, tmp_path, debut=DEBUT)


def test_debut_par_defaut_derniere_seance_avant_le_suivi():
    idx = pd.bdate_range("2026-11-20", "2026-12-08")
    p = {"close": pd.DataFrame({"X": 1.0}, index=idx)}
    assert TM.debut_par_defaut(p) == pd.Timestamp("2026-11-30")
    p2 = {"close": pd.DataFrame({"X": 1.0}, index=idx.drop(pd.Timestamp("2026-11-30")))}
    assert TM.debut_par_defaut(p2) == pd.Timestamp("2026-11-27")


def test_semaine_zero_rien_n_est_ecrit(panels, tmp_path):
    court = {k: (v.loc[:"2024-01-31"] if isinstance(v, pd.DataFrame) and isinstance(v.index, pd.DatetimeIndex) else
                 v.loc[:"2024-01-31"] if isinstance(v, pd.Series) else v) for k, v in panels.items()}
    r = TM.maj("REF-S2", court, tmp_path, debut=DEBUT)
    assert r["semaine_0"] and not r["ecrit"]
    assert not (tmp_path / "REF-S2").exists()


@pytest.fixture(scope="module")
def journal(panels, tmp_path_factory):
    d = tmp_path_factory.mktemp("suivi")
    r = TM.maj("REF-S2", panels, d, debut="2023-06-30", fin="2023-11-30")
    return d, r


def test_journal_du_temoin_identite_et_valeur_du_moteur(journal):
    d, r = journal
    assert r["ok"] and r["ecrit"] and len(r["lignes"]) >= 20
    c = r["controles"]
    assert c["identite_max_fcfa"] < 0.5  # P1 : identité de chaque semaine au franc
    assert c["ecart_moteur_max_fcfa"] < 1.0  # valeur du journal + à recevoir = valeur liquidative du moteur
    assert any(l["dividendes_recus"] > 0 for l in r["lignes"]) and any(l["a_recevoir"] > 0 for l in r["lignes"])
    assert r["lignes"][0]["semaine"] == 1 and r["lignes"][0]["argent_engage"] == 10_000_000
    for f in ("operations.csv", "positions.csv", "semaines.csv", "empreintes.jsonl", "controles.json"):
        assert (d / "REF-S2" / f).exists(), f
    ops = pd.read_csv(d / "REF-S2" / "operations.csv")
    assert set(ops["source"]) == {"moteur"} and {"apport", "achat", "dividende", "frais_fixes"} <= set(ops["type"])
    assert BU.verifier_semaines("REF-S2", d)["ok"]


def test_relance_idempotente_puis_passe_a_change(journal, panels):
    d, r = journal
    avant = (d / "REF-S2" / "semaines.csv").read_bytes()
    r2 = TM.maj("REF-S2", panels, d, debut="2023-06-30", fin="2023-11-30")
    assert r2["semaines"]["ajoutees"] == 0 and r2["semaines"]["identiques"] == len(r["lignes"])
    assert not r2["passe_a_change"] and (d / "REF-S2" / "semaines.csv").read_bytes() == avant
    # une donnée corrigée dans le passé : la ligne n'est pas réécrite, une anomalie est consignée
    p2 = dict(panels)
    sym = r["conversion"]["operations"].query("type == 'achat'")["symbole"].iloc[0]
    for k in ("close", "close_raw", "close_adj"):
        x = panels[k].copy()
        x.loc["2023-08-01":"2023-08-10", sym] *= 1.05
        p2[k] = x
    r3 = TM.maj("REF-S2", p2, d, debut="2023-06-30", fin="2023-11-30")
    assert r3["passe_a_change"] and r3["semaines"]["anomalies"]
    assert (d / "REF-S2" / "semaines.csv").read_bytes() == avant
    assert "le passé a changé" in (d / "REF-S2" / "anomalies.jsonl").read_text(encoding="utf-8")
    b = BU.depuis_journal("REF-S2", d, aujourd_hui="2023-12-04")
    assert b["feux"]["donnees"]["etat"] == "rouge" and "le passé a changé" in b["feux"]["donnees"]["phrase"]


def test_semaines_suivantes_ajoutees_sans_reecrire(panels, tmp_path):
    r1 = TM.maj("REF-S2", panels, tmp_path, debut=DEBUT, fin="2024-03-29")
    r2 = TM.maj("REF-S2", panels, tmp_path, debut=DEBUT, fin="2024-04-26")
    assert r2["semaines"]["identiques"] == len(r1["lignes"]) and r2["semaines"]["ajoutees"] == 4
    assert not r2["passe_a_change"] and BU.verifier_semaines("REF-S2", tmp_path)["ok"]


def test_le_paquet_n_appelle_ni_validate_ni_backtest_ni_le_reseau():
    for p in PAQUET.glob("*.py"):
        src = p.read_text(encoding="utf-8")
        assert not re.search(r"\brun_validation\s*\(", src), p.name
        assert not re.search(r"^\s*(import|from)\s+(urllib|requests|socket|http)\b", src, re.M), p.name
        assert "cli.main" not in src and "\"validate\"" not in src and "\"backtest\"" not in src, p.name
        assert "trials.parquet" not in src or p.name == "declaration.py", p.name
