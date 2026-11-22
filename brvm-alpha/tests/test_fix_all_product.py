"""Tests de régression des constats des revues « produit » et « quant » (agent fix:all, 22/11/2026).

Chaque test échoue avant la correction correspondante. Données **synthétiques** (dates de S0 ou
postérieures, graines fixes) : aucun backtest, aucune performance, aucun IC ni aucun signal n'est évalué
sur l'échantillon vierge S1. Aucune requête réseau (le serveur de l'interface écoute sur 127.0.0.1).
"""

from __future__ import annotations

import json
import re
import socket
import threading
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from test_recommend import _registry, _synthetic_panels

from brvm_alpha import cli, reference
from brvm_alpha.notes.store import NoteStore
from brvm_alpha.portfolio import recommend as R
from brvm_alpha.portfolio import stress as S
from brvm_alpha.strategy import BrvmAlpha


@pytest.fixture(scope="module")
def synth() -> dict:
    return _synthetic_panels()


def _rec(synth, tmp: Path, capital: float = 10_000_000, **kw):
    kw.setdefault("validation_dir", tmp / "absent")
    kw.setdefault("registry_path", _registry(tmp / "trials.parquet", False))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return R.recommend(kw.pop("asof", synth["close"].index[-1]), capital, panels=synth, notes_store=False,
                           n_boot=kw.pop("n_boot", 300), index_evaluation=False, explanations=False,
                           comparison=False, **kw)


# ---------------------------------------------------------------------------
# Majeur : distribution à 12 mois (cotation, biais rétrospectif, résultat de S1)
# ---------------------------------------------------------------------------


def test_distribution_renormalizes_weeks_before_listing_instead_of_counting_zero():
    weeks = pd.date_range("2030-01-04", periods=120, freq="W-FRI")
    rng = np.random.default_rng(0)
    old = pd.Series(rng.normal(-0.004, 0.02, 120), index=weeks)
    new = pd.Series(rng.normal(0.004, 0.02, 120), index=weeks)
    new.iloc[:60] = np.nan  # introduction en bourse à la semaine 60
    weekly = pd.DataFrame({"OLD": old, "NEW": new, R._BENCH: old})
    d = R.return_distribution(weekly, {"OLD": 0.49, "NEW": 0.49}, n_boot=200, horizon_weeks=26)
    part = d["lignes_sans_historique_complet"]
    assert [x["symbole"] for x in part] == ["NEW"] and part[0]["semaines_avant_cotation"] == 60
    assert d["poids_sans_historique_complet"] == pytest.approx(0.49)
    assert d["valeurs_avant_cotation_renormalisees"] == 60 and d["valeurs_manquantes_apres_cotation"] == 0
    # avant la cotation : 98 % sur OLD (poids renormalisés), et non 49 % OLD + 49 % de liquidités
    rp = np.where(weekly["NEW"].notna(), 0.49 * old + 0.49 * new.fillna(0.0), 0.98 * old)
    assert d["rendement_annualise_fenetre"] == pytest.approx(float(np.prod(1 + rp) ** (52 / 120) - 1))


def _metrics_with_runs(tmp: Path) -> Path:
    d = tmp / "val_s1"
    d.mkdir(parents=True, exist_ok=True)
    m = {"echantillon": "S1",
         "variantes": {"A": {"statut": "REJETÉ", "run_id": "A_central_10M"},
                       "REF": {"statut": "REJETÉ", "run_id": "REF_central_10M"}},
         "runs": {"A_central_10M": {"actif_tr_an": -0.072}, "REF_central_10M": {"actif_tr_an": -0.036}},
         "promotion": {"principal": "A", "criteres": []}}
    (d / "metrics.json").write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
    return d


def test_full_history_distribution_warns_retrospective_bias_and_shows_s1_result(synth, tmp_path):
    o = _rec(synth, tmp_path, validation_dir=_metrics_with_runs(tmp_path),
             registry_path=_registry(tmp_path / "reg.parquet", True))
    D = o.distribution
    assert D["s1_utilise"] is True and "biais_fenetre" not in D
    assert "Biais rétrospectif" in D["biais_retrospectif"] and D["biais_retrospectif"] in o.avertissements
    rs = D["resultat_s1"]
    assert rs["variante"] == "REF" and rs["actif_tr_an"] == pytest.approx(-0.036) and rs["statut"] == "REJETÉ"
    assert rs["texte"] in o.avertissements
    md = o.to_markdown()
    assert re.search(r"test S1 : REF [−-]3,6 %/an contre le TR \(REJETÉ\)", md)
    assert "fréquence historique aux poids actuels" in md


# ---------------------------------------------------------------------------
# Majeur : panel en retard (dernier BOC absent)
# ---------------------------------------------------------------------------


def test_expected_missing_sessions_counts_business_days_before_today():
    assert R.expected_missing_sessions("2026-11-19", "2026-11-22") == [pd.Timestamp("2026-11-20")]
    assert R.expected_missing_sessions("2026-11-20", "2026-11-22") == []
    assert R.expected_missing_sessions("2026-11-20", "2026-11-23") == []  # le BOC du jour n'est pas attendu
    assert R.expected_missing_sessions("2026-12-24", "2026-12-28") == []  # 25/12 férié fixe


def test_stale_panel_warns_marks_orders_and_never_dates_execution_in_the_past(synth, tmp_path):
    last = synth["close"].index[-1]
    today = last + pd.offsets.BDay(3)  # deux BOC manquent (J+1, J+2)
    o = _rec(synth, tmp_path, today=today)
    assert o.avertissements[0].startswith("PANEL EN RETARD de 2 séance(s)")
    assert "update" in o.avertissements[0] and o.execution["perime"] is True
    assert len(o.execution["seances_manquantes"]) == 2
    assert o.execution["premiere_seance"] >= pd.Timestamp(today).normalize()
    if len(o.tranches):
        assert pd.DatetimeIndex(o.tranches["date"]).min() >= pd.Timestamp(today).normalize()
    assert "ORDRES PÉRIMÉS" in o.to_markdown()
    fresh = _rec(synth, tmp_path, today=last + pd.offsets.BDay(1))
    assert fresh.execution["perime"] is False and not any("RETARD" in w for w in fresh.avertissements)
    # Décision historique explicite (antérieure au dernier BOC) : aucun contrôle de fraîcheur.
    past = _rec(synth, tmp_path, today=today, asof=synth["close"].index[-30])
    assert past.execution["perime"] is False


# ---------------------------------------------------------------------------
# Mineurs du module recommend
# ---------------------------------------------------------------------------


def test_small_capital_warns_lines_investment_and_fixed_fees(synth, tmp_path):
    o = _rec(synth, tmp_path, capital=100_000)
    w = [x for x in o.avertissements if x.startswith("Capital insuffisant")]
    assert w and "Capital minimal indicatif" in w[0] and "SGI sans frais par ligne" in w[0]
    big = _rec(synth, tmp_path, capital=20_000_000)
    assert not any(x.startswith("Capital insuffisant") for x in big.avertissements)


def test_model_messages_and_spec_target_are_rendered(synth, tmp_path):
    o = _rec(synth, tmp_path)
    o.messages_modele = ["budget de 98% non atteignable sous les plafonds : 90.74% investis (signalé)"]
    md = o.to_markdown()
    assert "Messages du modèle (signalés)" in md and "non atteignable" in md
    assert "cible de la spécification : 98,00 %" in md
    assert "non atteignable" in o.to_html_fragment()


def test_cost_summary_has_explicit_costs_of_both_sides():
    from brvm_alpha.report.html import _explicit_costs

    L = pd.DataFrame([
        {"sens": "achat", "montant_brut": 1000, "couts_total": 30, "frais_explicites": 20, "couts_implicites": 10,
         "montant_net": 1030, "pire_cas": 1050, "courtage": 15, "tva": 2, "brvm": 2, "dcbr": 1, "demi_spread": 6,
         "impact": 4, "valeur_apres": 1000, "poids_cible": 0.5, "cibles": 1},
        {"sens": "vente", "montant_brut": 2000, "couts_total": 50, "frais_explicites": 35, "couts_implicites": 15,
         "montant_net": 1950, "pire_cas": 1900, "courtage": 25, "tva": 4, "brvm": 4, "dcbr": 2, "demi_spread": 10,
         "impact": 5, "valeur_apres": 0, "poids_cible": 0.0, "cibles": 0}])
    k = R._cost_summary(L, 10_000.0, 5_000.0, R.settings.cost_scenario("central"), "central")
    assert k["ventes_explicites"] == 35 and k["ventes_implicites"] == 15 and k["explicites"] == 55
    assert k["flux_net"] == 1030 - 1950
    assert _explicit_costs(k, []) == 55
    assert _explicit_costs({"achats_explicites": 20}, L.to_dict("records")) == 55  # ancien ordre : lignes


def test_line_sessions_and_worst_case_match_the_execution_schedule(synth, tmp_path):
    close = synth["close_raw"].iloc[-1]
    held = list(close.sort_values().index[-8:-2])
    holdings = {s: int(1_500_000 // close[s]) for s in held}  # titres à vendre, peu de liquidités
    o = _rec(synth, tmp_path, capital=10_000_000, holdings=holdings, cash=150_000)
    tab = o.tranches
    for r in o.lignes[o.lignes["sens"] != "aucun"].itertuples(index=False):
        sel = tab[(tab["symbole"] == r.symbole) & (tab["sens"] == r.sens)]
        assert int(r.seances) == len(sel), r.symbole
        assert int(r.pire_cas) == int(sel["pire_cas"].sum()), r.symbole


def test_held_symbol_absent_from_boc_is_blocked_not_fatal(synth, tmp_path):
    panels = dict(synth)
    sym = synth["close_raw"].columns[3]
    for k in ("close_raw", "close", "close_adj"):
        f = panels[k].copy()
        f.loc[f.index[-40]:, sym] = np.nan  # suspendu de longue date, absent du BOC
        panels[k] = f
    o = _rec(panels, tmp_path, holdings={sym: 100, synth["close_raw"].columns[0]: 10})
    row = o.lignes.set_index("symbole").loc[sym]
    assert row["sens"] == "aucun" and int(row["cibles"]) == 100 and "hors BOC" in row["note"]
    last_px = float(synth["close_raw"][sym].iloc[-41])
    assert row["cours_reference"] == pytest.approx(R.floor_to_tick(last_px * 0.9))
    assert any(f"{sym} : absent du BOC" in w for w in o.avertissements)
    with pytest.raises(ValueError, match="titre inconnu"):
        _rec(synth, tmp_path, holdings={"XXXX": 10})


def test_limit_prices_move_at_least_one_tick_below_the_tolerance():
    lp = R.limit_prices(57.0)  # ETIT : pas de 1 FCFA = 1,75 % > tolérance de 1 %
    assert (lp["buy"], lp["sell"], lp["un_pas"]) == (58.0, 56.0, True)
    lp = R.limit_prices(300.0)  # pas de 5 FCFA = 1,67 %
    assert (lp["buy"], lp["sell"]) == (305.0, 295.0)
    lp = R.limit_prices(4040.0)  # cas courant inchangé
    assert (lp["buy"], lp["sell"], lp["un_pas"]) == (4080.0, 4000.0, False)
    lp = R.limit_prices(57.0, reference_price=53.0)  # borne haute 56 < dernier cours : aucune limite au-dessus
    assert lp["buy"] <= lp["high"]


def test_stress_texts_use_french_number_format_and_valuation_label(synth, tmp_path):
    assert S._pct(0.1409) == "14,09 %" and S._pct(-0.893, 1) == "−89,3 %" and S._num(0.238, 3) == "0,238"
    o = _rec(synth, tmp_path)
    for s in o.stress:
        txt = str(s.get("hypothese", ""))
        assert not re.search(r"(?<![§\d])\d+\.\d+ ?%", txt), txt
        assert not re.search(r"\d\.\d{2}\b(?! ?FCFA)", txt.replace("§9.3", "")), txt
    mk = pd.DataFrame({"date": synth["close"].index, "risk_premium": 0.5})
    v = R._valuation_regime({"market": mk}, synth["close"].index[-1])
    assert "« cher »" in v["texte"] and "chère »" not in v["texte"]


# ---------------------------------------------------------------------------
# CLI, interface, journal des notes
# ---------------------------------------------------------------------------


def test_cli_recommend_accepts_racine_and_report_accepts_costs_and_seed():
    p = cli.build_parser()
    a = p.parse_args(["recommend", "--capital", "10M", "--racine", "/tmp/journal"])
    assert a.racine == "/tmp/journal"
    b = p.parse_args(["report", "--capital", "10M", "--couts", "stress", "--graine", "7"])
    assert b.couts == "stress" and b.graine == 7


def test_ui_server_times_out_unsent_body_and_bounds_connections(tmp_path):
    from brvm_alpha.ui import server as srv

    assert srv.Handler.timeout and srv.Handler.timeout <= 30 and srv.UIServer.max_connections <= 64
    services = srv.Services(notes_root=tmp_path / "notes", panel_dir=tmp_path / "panel", reports_dir=tmp_path / "r",
                            validation_dir=tmp_path / "v", diagnostic_dir=tmp_path / "d", boc_dir=tmp_path / "b")
    old_timeout = srv.Handler.timeout
    srv.Handler.timeout = 1.0
    s = srv.make_server("127.0.0.1", 0, services=services)
    th = threading.Thread(target=s.serve_forever, daemon=True)
    th.start()
    try:
        c = socket.create_connection(("127.0.0.1", s.port), timeout=10)
        c.sendall(f"POST /notes/ajouter HTTP/1.0\r\nHost: 127.0.0.1:{s.port}\r\nContent-Type: "
                  "application/x-www-form-urlencoded\r\nContent-Length: 200000\r\n\r\n".encode())
        t0 = time.time()
        data = b""
        while True:
            chunk = c.recv(65536)
            if not chunk:
                break
            data += chunk
        assert time.time() - t0 < 8  # la connexion est fermée après le délai, sans attendre le corps
        c.close()
    finally:
        srv.Handler.timeout = old_timeout
        s.shutdown()
        s.server_close()


def test_note_store_rejects_record_reduced_to_its_id(tmp_path):
    root = tmp_path / "notes"
    root.mkdir()
    st = NoteStore(root)
    (root / "notes.jsonl").write_text('{"note_id":"deadbeef"}\n', encoding="utf-8")
    assert len(st.frame()) == 0  # avant : « deadbeef | (titre vide) | active | NaT »
    assert any("ni titre ni texte" in e for e in st.errors)


# ---------------------------------------------------------------------------
# Règles pays hors S1 (revue quantitative) : élection J−30, durée depuis la première séance
# ---------------------------------------------------------------------------


def test_post_s1_election_known_thirty_business_days_ahead_s1_chronology_frozen():
    ev = reference.country_events_table()
    sn = ev[(ev["country"] == "SN") & (ev["rule"] == "election") & (ev["event_date"] == pd.Timestamp("2024-03-24"))]
    assert sn["date"].iloc[0] == pd.Timestamp("2024-03-24") - pd.offsets.BDay(30)
    s1 = ev[(ev["rule"] == "election") & (ev["event_date"] <= pd.Timestamp("2022-11-16"))]
    assert (s1["date"] == s1["event_date"]).all()  # D10 figé : élection connue la veille du scrutin sur S1
    cal = pd.bdate_range("2023-11-01", "2024-04-30")
    rng = np.random.default_rng(2)
    close = pd.DataFrame(1000.0 * np.cumprod(1 + rng.normal(0, 0.01, (len(cal), 2)), axis=0),
                         index=cal, columns=["SNTS", "SGBC"]).round()
    m = BrvmAlpha(notes=None)
    d = m._prepare({"close_raw": close}, "2024-02-20")  # J − 24 jours ouvrés
    st = m._country_rule_state(d, d.country_events)
    assert "SN" in st and st["SN"]["rule"] == "election"


def test_post_s1_country_rule_duration_counts_sessions_from_announcement_through_boc_gap():
    full = pd.bdate_range("2030-01-01", periods=140)
    sess_all = pd.Series(np.arange(1, len(full) + 1), index=full)
    gap = full[40:73]  # 33 BOC manquants (séances 41 à 73)
    days = full.difference(gap)
    rng = np.random.default_rng(3)
    close = pd.DataFrame(1000.0 * np.cumprod(1 + rng.normal(0, 0.01, (len(days), 2)), axis=0),
                         index=days, columns=["BOAM", "SNTS"]).round()
    sess = pd.DataFrame({c: sess_all.reindex(days).to_numpy() for c in close.columns}, index=days)
    ann = full[52]  # annonce pendant le trou (séance 53) : règle attendue sur les séances 54 à 73
    m = BrvmAlpha(notes=None, country_events=[{"date": ann, "country": "ML", "rule": "coup"}],
                  window_basis="sessions")
    panels = {"close_raw": close, "session_no": sess}
    d = m._prepare(panels, full[73])  # première séance après le trou (séance 74)
    st = m._country_rule_state(d, d.country_events)
    assert "ML" not in st  # 20 séances écoulées (54 → 73) : règle terminée (avant : active jusqu'à 93)
    d = m._prepare(panels, full[45]) if full[45] in days else None
    assert d is None  # aucune séance pendant le trou
