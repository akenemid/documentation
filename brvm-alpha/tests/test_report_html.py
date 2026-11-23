"""Tests du rapport HTML autonome (``brvm_alpha.report``), hors ligne.

Panel synthétique (dates de S0 seulement, aucun cours réel) écrit dans un dossier temporaire,
fichiers de résultats S1 **factices** (statut absent, CANDIDAT, REJETÉ ; nombres inventés), journal
de notes temporaire. Aucune performance n'est évaluée sur l'échantillon vierge S1 et aucune requête
réseau n'est faite.
"""

from __future__ import annotations

import json
import re
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from brvm_alpha import reference
from brvm_alpha.backtest.walkforward import REGISTRY_COLUMNS, TrialRegistry
from brvm_alpha.portfolio import recommend as R
from brvm_alpha.report import BANNER, SECTIONS, build_report, render_report
from brvm_alpha.report import html as RH

N_BOOT = 300
#: Bannière telle qu'écrite dans le HTML (apostrophe échappée).
BANNER_H = RH.esc(BANNER)
FAMILY = ("A", "B", "C", "D", "E", "F", "G", "H", "I")


# ---------------------------------------------------------------------------
# Données synthétiques
# ---------------------------------------------------------------------------


def _synthetic(n_days: int = 430, seed: int = 11) -> tuple[dict, dict[str, pd.DataFrame]]:
    """Panels larges (format ``strategy.build_panels``) et tables longues cohérentes (S0)."""
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
    per_v = rng.uniform(4.0, 30.0, n)
    per = pd.DataFrame(np.tile(per_v, (n_days, 1)), idx, cols)
    div_amt = rng.uniform(0.02, 0.09, n) * close[0]
    pay = [dates[min(60 + 7 * j % 120, n_days - 1)] for j in range(n)]
    last_div_net = pd.DataFrame(np.tile(div_amt, (n_days, 1)), idx, cols)
    last_div_date = pd.DataFrame({s: pd.Series(pd.Timestamp("2022-12-15"), index=idx) for s in syms})
    tr = C.pct_change().fillna(0.0)
    div_rows = []
    for j, s in enumerate(syms):
        last_div_date.loc[last_div_date.index >= pay[j], s] = pay[j]
        ex = dates[dates.get_loc(pay[j]) - 2]
        tr.loc[ex, s] += div_amt[j] / C[s].shift(1).loc[ex]
        div_rows.append({"symbol": s, "ex_date": ex, "amount": float(div_amt[j]), "payment_date": pay[j],
                         "date": dates[dates.get_loc(ex) - 1], "first_seen": dates[dates.get_loc(ex) - 1]})
    tr_index = 100.0 * (1.0 + tr).cumprod()
    shares = pd.DataFrame(np.tile(rng.uniform(1e6, 5e7, n), (n_days, 1)), idx, cols)
    cap = (C * shares).sum(axis=1)
    market = pd.DataFrame({"date": idx, "avg_per": 15.0, "risk_premium": 0.8, "market_cap": cap.to_numpy(),
                           "avg_yield_pct": 6.5, "n_up": 12.0, "n_down": 10.0, "n_unchanged": 8.0,
                           "value": (C * pd.DataFrame(vol, idx, cols)).sum(axis=1).to_numpy()})
    mret = tr_index.pct_change().mean(axis=1).fillna(0.0)
    market_tr = (100.0 * (1.0 + mret).cumprod()).rename("TR")
    dividend_net = pd.DataFrame(0.0, idx, cols)
    for rec in div_rows:
        dividend_net.loc[rec["ex_date"], rec["symbol"]] = rec["amount"]
    panels = {"close": C.copy(), "adj_factor": pd.DataFrame(1.0, idx, cols), "close_raw": C, "close_adj": C.copy(),
              "tr_index": tr_index, "volume": pd.DataFrame(vol, idx, cols), "value": pd.DataFrame(vol, idx, cols) * C,
              "status": status, "per": per, "net_yield_pct": pd.DataFrame(100.0 * div_amt / close, idx, cols),
              "last_div_net": last_div_net, "last_div_date": last_div_date, "ref_price": C.shift(1),
              "flags": pd.DataFrame("", index=idx, columns=cols, dtype=object), "bid": C * 0.996, "ask": C * 1.004,
              "shares": shares, "market": market, "market_tr": market_tr,
              "dividends_table": pd.DataFrame(div_rows).drop(columns=["first_seen"]), "dividend_net": dividend_net}
    # Tables longues (marché, indices, actions, dividendes, séances).
    eq_rows = []
    for j, s in enumerate(syms):
        sec = reference.sector_of(s) or "FIN"
        for i, d in enumerate(dates):
            eq_rows.append({"date": d, "symbol": s, "name": f"SOCIETE <{s}> & CIE", "sector": sec,
                            "compartment": "PRESTIGE" if j % 3 == 0 else "PRINCIPAL", "close": close[i, j],
                            "volume": vol[i, j], "value": vol[i, j] * close[i, j], "status": status.iat[i, j],
                            "per": per_v[j], "net_yield_pct": 100.0 * div_amt[j] / close[i, j], "change_pct": np.nan})
    equities = pd.DataFrame(eq_rows)

    def level(series: pd.Series, base: float) -> pd.Series:
        return base * (1.0 + series).cumprod()

    comp = level(C.pct_change().fillna(0.0).mean(axis=1), 200.0)
    lv = {"BRVM COMPOSITE": comp, "BRVM COMPOSITE TOTAL RETURN": market_tr,
          "BRVM 30": level(C.iloc[:, :20].pct_change().fillna(0.0).mean(axis=1), 100.0),
          "BRVM PRESTIGE": level(C.iloc[:, ::3].pct_change().fillna(0.0).mean(axis=1), 100.0)}
    ix_rows = []
    for name, s in lv.items():
        prev = s.groupby(s.index.year).transform("first")
        for d, v in s.items():
            ix_rows.append({"date": d, "index": name, "level": float(v), "change_pct": 0.1,
                            "ytd_pct": float(100.0 * (v / prev[d] - 1.0)), "per": np.nan})
    indices = pd.DataFrame(ix_rows)
    sessions = pd.DataFrame({"session_no": np.arange(1, n_days + 1), "year": dates.year,
                             "issue_no": np.arange(1, n_days + 1), "date": dates, "available": True})
    sessions.loc[100:102, "available"] = False
    long = {"equities": equities, "indices": indices, "market": market, "dividends": pd.DataFrame(div_rows),
            "sessions": sessions}
    return panels, long


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


def _fake_metrics(d: Path, status_a: str, *, sample: str = "S1", prediction: str | None = None) -> Path:
    """metrics.json, nav.parquet et lock.json FACTICES (nombres inventés, aucune exécution)."""
    d.mkdir(parents=True, exist_ok=True)
    t0, end = "2017-08-01", "2022-11-16"
    runs, variants = {}, {}
    for k, v in enumerate(list(FAMILY) + ["REF"]):
        act = 0.01 * (k - 4) if status_a != "REJETÉ" else -0.02 - 0.001 * k
        runs[f"{v}_central_10M"] = {
            "run_id": f"{v}_central_10M", "variante": v, "couts": "central", "capital": 1e7,
            "role": "essai (famille)" if v != "REF" else "essai (référence, hors PBO)",
            "rendement_an": 0.05 + act, "actif_tr_an": act, "ir_tr": 3.0 * act, "drawdown_relatif_tr": -0.1,
            "rotation_mensuelle_aller": 0.07, "bootstrap_ir": {"point": 3 * act, "lower": 3 * act - 0.6,
                                                               "upper": 3 * act + 0.6},
            "sous_periodes": [{"debut": t0, "fin": "2019-12-31", "actif_tr_an": act, "ir_tr": 3 * act, "n_semaines": 125},
                              {"debut": "2020-01-01", "fin": end, "actif_tr_an": act / 2, "ir_tr": 1.5 * act,
                               "n_semaines": 130}]}
        st = status_a if v == "A" else ("CANDIDAT" if status_a == "CANDIDAT" else "REJETÉ")
        variants[v] = {"run_id": f"{v}_central_10M", "statut": st, "statut_informatif": v == "REF",
                       "rejets_declenches": ["R1", "R3"] if st == "REJETÉ" else [],
                       "criteres_candidat_non_verifies": [],
                       "criteres": [{"code": "R1", "libelle": "rendement actif net annualisé contre le TR (coûts centraux)",
                                     "valeur": act, "seuil": "≤ 0.0 ⇒ rejet", "verifie": act <= 0},
                                    {"code": "R3", "libelle": "IR de chaque sous-période", "valeur": [3 * act, 1.5 * act],
                                     "seuil": "< -0.5 sur l'une ⇒ rejet", "verifie": True}],
                       "dsr_famille_n9": 0.4, "dsr_registre": 0.2}
    runs["A_stress_10M"] = dict(runs["A_central_10M"], run_id="A_stress_10M", couts="stress", role="sensibilité")
    runs["A_central_100M"] = dict(runs["A_central_10M"], run_id="A_central_100M", capital=1e8, role="sensibilité")
    m = {"bandeau": BANNER, "echantillon": sample, "t0": t0, "fin": end,
         "sous_periodes": [[t0, "2019-12-31"], ["2020-01-01", end]], "n_boot": 5000, "bloc_moyen_semaines": 8,
         "execution": {"commit": "0123456789abcdef", "empreinte_config": "f00", "horodatage_utc": "2026-11-22T09:56:27+00:00",
                       "mode_decision": "evenementiel", "empreinte_controle": {"conforme": True}},
         "famille": {"pbo": 0.3, "pente_degradation": -0.2, "n_blocs": 10, "n_registre": 88},
         "variantes": variants, "runs": runs,
         "etalons": {"TR": {"libelle": "Composite TR", "disponible": True, "mesures": {"rendement_an": 0.04}},
                     "EW": {"libelle": "panier EW", "disponible": True, "mesures": {"rendement_an": 0.045}}},
         "promotion": {"principal": "A", "regle": "§3.4", "criteres": [{"variante": "A", "actif_net_an": 0.0}]},
         "prediction_8_3": prediction or "Prédiction écrite d'avance (§8.3) : statut le plus probable « candidat ».",
         "controles": {"tous_ok": True, "runs_en_anomalie": []}}
    (d / "metrics.json").write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
    days = pd.bdate_range(t0, end)
    rows = []
    rng = np.random.default_rng(3)
    for sid in ("A_central_10M", "I_central_10M", "REF_central_10M", "ETALON_TR", "ETALON_EW"):
        lvl = 100.0 * np.cumprod(1.0 + rng.normal(0.0002, 0.006, len(days)))
        rows.append(pd.DataFrame({"date": days, "serie": sid, "type": "strategie", "valeur": lvl * 1e5, "base_t0": lvl}))
    pd.concat(rows).to_parquet(d / "nav.parquet")
    (d / "lock.json").write_text(json.dumps({"statut": "terminé", "commit": "0123456789abcdef"}), encoding="utf-8")
    return d


@pytest.fixture(scope="module")
def synth(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("rapport")
    panels, long = _synthetic()
    pdir = tmp / "panel"
    pdir.mkdir()
    for name, df in long.items():
        df.to_parquet(pdir / f"{name}.parquet")
    return {"tmp": tmp, "panels": panels, "panel_dir": pdir, "t": panels["close"].index[-1],
            "reg_no": _registry(tmp / "trials_no.parquet", False), "reg_yes": _registry(tmp / "trials_yes.parquet", True)}


def _render(synth, **kw):
    base = dict(panels=synth["panels"], panel_dir=synth["panel_dir"], notes_root=synth["tmp"] / "pas_de_notes",
                validation_dir=synth["tmp"] / "absent", diagnostic_dir=synth["tmp"] / "absent_s0",
                registry_path=synth["reg_no"], n_boot=N_BOOT, seed=1, now="2026-11-22T10:00:00Z")
    base.update(kw)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return render_report(synth["t"], 10_000_000, **base)


@pytest.fixture(scope="module")
def rep_absent(synth):
    return _render(synth)


def _section(html: str, sid: str) -> str:
    a = html.index(f'<section id="{sid}"')
    b = html.find("<section id=", a + 10)
    return html[a:b if b > 0 else len(html)]


# ---------------------------------------------------------------------------
# Mise en forme et graphiques
# ---------------------------------------------------------------------------


def test_formatting_helpers():
    assert RH.fmt_pct(0.1234) == "12,3 %"
    assert RH.fmt_pct(-0.05, 1, True) == "−5,0 %"
    assert RH.fmt_num(-1234.5, 1) == "−1 234,5"
    assert RH.fmt_fcfa(10_000_000) == "10 000 000 FCFA"
    assert RH.fmt_pct(None) == "n.d." and RH.fmt_num(float("nan")) == "n.d."
    assert RH.fmt_date("2026-11-20") == "20/11/2026" and RH.fmt_date(None) == "n.d."
    assert RH.esc('<a href="x">&</a>') == "&lt;a href=&quot;x&quot;&gt;&amp;&lt;/a&gt;"
    assert RH.fmt_capital(1e9) == "1 Md FCFA" and RH.fmt_capital(1e8) == "100 M FCFA"


def test_line_chart_and_histogram_are_inline_svg():
    dates = pd.date_range("2023-01-06", periods=60, freq="W-FRI")
    vals = list(100 + np.arange(60) * 0.5)
    vals[10] = float("nan")  # trou de données : chemin interrompu
    h = RH.line_chart("c-test", dates, [{"name": "A <x>", "slot": "1", "values": vals},
                                        {"name": "TR", "slot": "ink", "values": list(100 + np.arange(60) * 0.3),
                                         "dash": True}])
    assert "<svg" in h and 'preserveAspectRatio="none"' in h and "nan" not in h.lower().replace("nanos", "")
    assert "A &lt;x&gt;" in h and "<x>" not in h
    assert h.count("<path") == 2 and h.count("M") >= 3  # le trou crée un second segment
    data = json.loads(re.search(r'<script type="application/json" class="cdata">(.*?)</script>', h).group(1))
    assert data["kind"] == "line" and len(data["t"]) == 60 and data["s"][0]["v"][10] is None
    draws = np.random.default_rng(0).normal(0.1, 0.15, 2000)
    hh = RH.histogram_chart("c-h", draws, bins=30, markers=[(0.0, "0 %", "zero"), (0.1, "médiane", "med")])
    d2 = json.loads(re.search(r'class="cdata">(.*?)</script>', hh).group(1))
    assert d2["n"] == 30 and len(d2["tips"]) == 30
    tot = sum(int(re.search(r": (\d[\d ]*) tirages", t).group(1).replace(" ", "")) for t in d2["tips"])
    assert tot == 2000
    with pytest.raises(RH.Unavailable):
        RH.line_chart("c-vide", dates[:1], [{"name": "x", "values": [1.0]}])


def test_read_validation_states(tmp_path):
    assert RH.read_validation(tmp_path / "rien")["etat"] == "non exécuté"
    bad = tmp_path / "bad"
    bad.mkdir()
    (bad / "metrics.json").write_text("{pas du json", encoding="utf-8")
    v = RH.read_validation(bad)
    assert v["etat"] == "illisible" and not v["execute"] and v["avertissements"]
    s0 = _fake_metrics(tmp_path / "s0", "CANDIDAT", sample="S0")
    assert RH.read_validation(s0)["etat"] == "autre échantillon"
    running = tmp_path / "run"
    running.mkdir()
    (running / "lock.json").write_text(json.dumps({"statut": "en cours"}), encoding="utf-8")
    assert RH.read_validation(running)["etat"] == "en cours"
    ok = RH.read_validation(_fake_metrics(tmp_path / "ok", "CANDIDAT"))
    assert ok["execute"] and ok["statut_A"] == "CANDIDAT" and ok["principal"] == "A"


# ---------------------------------------------------------------------------
# Rapport complet : test S1 absent
# ---------------------------------------------------------------------------


def test_report_structure_banner_and_sections(rep_absent):
    h = rep_absent.html
    assert h.startswith("<!doctype html>") and '<html lang="fr">' in h
    assert '<meta name="viewport" content="width=device-width, initial-scale=1">' in h
    # Sections dans l'ordre demandé.
    pos = [h.index(f'<section id="{sid}"') for sid, _ in SECTIONS]
    assert pos == sorted(pos) and len(pos) == 11
    assert [s.id for s in rep_absent.sections] == [sid for sid, _ in SECTIONS]
    st = rep_absent.statuts()
    for sid in ("bandeau", "marche", "s1", "ordre", "revenus", "distribution", "risques", "univers", "methode"):
        assert st[sid] == "ok", (sid, st[sid], [s.message for s in rep_absent.sections if s.id == sid])
    assert st["indices"] in ("ok", "erreur", "indisponible")
    # Bannière en tête et en pied, statut « test S1 non exécuté », phrase d'étude.
    assert h.count(BANNER_H) >= 3
    band = _section(h, "bandeau")
    assert "test S1 non exécuté" in band and "Statut : NON TESTÉ" in band and "Étude" in band
    s1 = _section(h, "s1")
    assert "Test S1 non exécuté." in s1 and "§8.3" in s1 and "<table" not in s1
    # Marché : prime < 1 ⇒ « chère » et stress tests d'abord dans la distribution (§4.5).
    assert "cher" in _section(h, "marche") and "« chère »" not in h  # accord : marché « cher » (22/11/2026)
    dist = _section(h, "distribution")
    assert dist.index("Stress tests du §9.3") < dist.index("Rendement net à 12 mois")
    # Ordre de bataille : REF par défaut, A en comparaison, faits / estimations / hypothèses.
    ordre = _section(h, "ordre")
    assert "REF" in ordre and "Comparaison" in ordre and "Faits" in ordre and "Hypothèses" in ordre
    assert "Prix limite" in ordre and "Contraintes actives" in ordre
    # Univers : tableau complet des titres du panel.
    univ = _section(h, "univers")
    assert univ.count("<tr>") >= 30 and "Éligible" in univ
    # Méthode : trous de données comptés sur le calendrier, sources en lien.
    meth = _section(h, "methode")
    assert "3 séances réelles sans BOC" in meth and "https://www.brvm.org/fr/bulletins-officiels-de-la-cote" in meth


def test_report_is_self_contained_and_themed(rep_absent):
    h = rep_absent.html
    # Aucune ressource externe : pas de src= distant, pas de feuille de style ni de police externes.
    assert not re.search(r"""\ssrc\s*=\s*["']?(https?:)?//""", h, re.IGNORECASE)
    assert "<link" not in h.lower() and "@import" not in h and "url(" not in h
    for m in re.finditer(r"""<a\s[^>]*href\s*=\s*["']([^"']+)["'][^>]*>""", h):
        url, tag = m.group(1), m.group(0)
        if url.startswith("#"):
            continue
        assert url.startswith("https://www.brvm.org/") and 'class="src"' in tag, tag
    assert "http" not in re.sub(r'<a class="src" href="[^"]+"', "", re.sub(r'<span class="muted small url">[^<]*</span>', "", h))
    # Thème clair et sombre : variables sur :root, redéfinies sous prefers-color-scheme: dark ; fond explicite.
    assert ":root {" in h and "@media (prefers-color-scheme: dark)" in h and ':root[data-theme="dark"]' in h
    assert re.search(r"body \{[^}]*background: var\(--surface-0\)", h)
    assert "--surface-0: #121211" in h
    # Mobile : gouttière de 16 px, tableaux dans un conteneur défilant.
    assert "padding: 24px 16px 64px" in h and ".tablewrap { width: 100%; overflow-x: auto;" in h
    own = re.sub(r'<section class="brvm-ordre-de-bataille".*?</section>', "", h, flags=re.DOTALL)  # export du module
    assert "<table" in own and own.count('<div class="tablewrap"><table') == own.count("<table")
    assert ".frag { overflow-x: auto;" in h
    # Graphiques SVG inline générés en Python, info-bulles en JavaScript sans dépendance.
    assert "<svg" in h and "c-dist" in h and "c-revenus" in h and "<script src" not in h


def test_build_report_writes_file(synth, tmp_path):
    out = tmp_path / "sous" / "rapport.html"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        p = build_report(synth["t"], 10_000_000, out, panels=synth["panels"], panel_dir=synth["panel_dir"],
                         notes_root=synth["tmp"] / "pas_de_notes", validation_dir=synth["tmp"] / "absent",
                         diagnostic_dir=None, registry_path=synth["reg_no"], n_boot=200,
                         recommend_kwargs={"explanations": False, "comparison": False})
    assert p == out and out.exists() and out.stat().st_size > 20_000
    txt = out.read_text(encoding="utf-8")
    assert BANNER_H in txt and 'name="brvm-alpha-sections"' in txt
    with pytest.raises(ValueError):
        render_report(synth["t"], 0)


# ---------------------------------------------------------------------------
# Statuts du test S1 (fichiers factices)
# ---------------------------------------------------------------------------


def test_report_candidat(synth):
    vdir = _fake_metrics(synth["tmp"] / "val_candidat", "CANDIDAT")
    rep = _render(synth, validation_dir=vdir, registry_path=synth["reg_yes"],
                  recommend_kwargs={"explanations": False})
    h = rep.html
    assert rep.statuts()["s1"] == "ok" and rep.statuts()["ordre"] == "ok"
    band = _section(h, "bandeau")
    assert "Statut : CANDIDAT" in band and "Paper trading" in band
    s1 = _section(h, "s1")
    for v in list(FAMILY) + ["REF"]:
        assert f"<b>{v}</b>" in s1
    assert "c-s1-nav" in s1 and "Sous-périodes" in s1 and "Sensibilités" in s1 and "PBO" in s1
    assert "coûts de stress" in s1 and "100 M FCFA" in s1
    assert "Lecture du résultat" in s1 and "paper trading" in s1 and "Rappel." in s1
    # A CANDIDAT : l'ordre suit A, REF en comparaison.
    assert ">A<" in _section(h, "ordre")


def test_report_rejete(synth):
    vdir = _fake_metrics(synth["tmp"] / "val_rejete", "REJETÉ")
    rep = _render(synth, validation_dir=vdir, registry_path=synth["reg_yes"],
                  recommend_kwargs={"explanations": False})
    h = rep.html
    band = _section(h, "bandeau")
    assert "Statut : REJETÉ" in band and "indice discipliné" in band
    s1 = _section(h, "s1")
    assert "REJETÉE sur S1" in s1 and "R1 : rendement actif net annualisé" in s1
    assert "IR de chaque sous-période" in s1  # valeur en liste (une par sous-période)
    assert "Aucune variante en comparaison" in _section(h, "ordre")


# ---------------------------------------------------------------------------
# Notes, échappement, robustesse
# ---------------------------------------------------------------------------


def test_notes_present_escaped_and_absent(synth, rep_absent):
    from brvm_alpha.notes.model import Note
    from brvm_alpha.notes.store import NoteStore

    assert "Aucune note dans le journal." in _section(rep_absent.html, "notes")
    root = synth["tmp"] / "notes"
    st = NoteStore(root)
    sym = synth["panels"]["close"].columns[0]
    st.add(Note(title="<script>alert('x')</script> Résultats & dividende", targets=[sym],
                text="Résultat net en baisse de 40 % ; <img src=x onerror=alert(1)>", author="analyste",
                source="manual", url="javascript:alert(1)", published_at="2024-08-20T10:00:00Z",
                created_at="2024-08-20T10:00:00Z", stance="baissier", conviction=3), analyze=True,
           now="2024-08-20T10:05:00Z")
    vdir = _fake_metrics(synth["tmp"] / "val_xss", "CANDIDAT", prediction="<b onmouseover=alert(2)>piège</b>")
    rep = _render(synth, notes_root=root, validation_dir=vdir, registry_path=synth["reg_yes"],
                  recommend_kwargs={"explanations": False, "comparison": False})
    h = rep.html
    notes = _section(h, "notes")
    assert rep.statuts()["notes"] == "ok"
    assert "&lt;script&gt;alert(&#x27;x&#x27;)&lt;/script&gt; Résultats &amp; dividende" in notes
    assert "&lt;img src=x onerror=alert(1)&gt;" in notes and "score" in notes and "matérialité" in notes
    assert "javascript:alert(1)" in notes and 'href="javascript' not in h  # adresse en texte, jamais en lien
    assert "<script>alert" not in h and "<img src=x" not in h
    assert "&lt;b onmouseover=alert(2)&gt;piège&lt;/b&gt;" in _section(h, "s1") and "<b onmouseover" not in h
    # Noms des titres issus des données : échappés dans l'univers.
    assert "SOCIETE &lt;" in _section(h, "univers") and "SOCIETE <" not in h


def test_section_errors_are_isolated(synth, monkeypatch):
    bad = synth["tmp"] / "val_corrompu"
    bad.mkdir(exist_ok=True)
    (bad / "metrics.json").write_text("{tronqué", encoding="utf-8")

    def boom(*a, **k):
        raise RuntimeError("panne simulée de l'ordre de bataille <b>")

    monkeypatch.setattr(R, "recommend", boom)
    rep = _render(synth, validation_dir=bad)
    st = rep.statuts()
    assert st["ordre"] == st["revenus"] == st["distribution"] == "erreur"
    for sid in ("bandeau", "marche", "s1", "notes", "risques", "univers", "methode"):
        assert st[sid] == "ok", (sid, st[sid])
    h = rep.html
    ordre = _section(h, "ordre")
    assert "Section « Ordre de bataille » indisponible" in ordre and "RuntimeError" in ordre
    assert "panne simulée de l&#x27;ordre de bataille &lt;b&gt;" in ordre and "Trace technique" in ordre
    assert "metrics.json illisible" in _section(h, "bandeau")
    assert "Test S1 non exécuté." in _section(h, "s1")
    assert BANNER_H in h and "</html>" in h


def test_recommend_module_unavailable(synth, monkeypatch):
    monkeypatch.setattr(RH, "_RECOMMEND_MODULE", "brvm_alpha.portfolio.module_inexistant")
    rep = _render(synth)
    st = rep.statuts()
    assert st["ordre"] == st["revenus"] == st["distribution"] == "indisponible"
    assert "module brvm_alpha.portfolio.module_inexistant indisponible" in _section(rep.html, "ordre")
    assert st["univers"] == "ok" and st["s1"] == "ok"


def test_missing_panel_gives_readable_boxes(tmp_path):
    rep = render_report("2026-11-20", 10_000_000, panel_dir=tmp_path / "vide", notes_root=tmp_path / "n",
                        validation_dir=tmp_path / "v", diagnostic_dir=None, registry_path=tmp_path / "r.parquet",
                        now="2026-11-22T10:00:00Z")
    st = rep.statuts()
    assert st["bandeau"] == "ok" and st["methode"] == "ok" and st["s1"] == "ok"
    assert st["ordre"] == "indisponible" and st["marche"] == "indisponible"
    assert "panel introuvable" in _section(rep.html, "ordre") and BANNER_H in rep.html


def test_paths_of_the_delivered_validation_results_never_show_another_machine():
    """Contrôle de a58b4c8, constat 20 : hors du dépôt de développement (export Odoo), le rapport affichait le chemin
    absolu de la machine de développement gardé par metrics.json (« /home/…/reports/validation_S1/precedent_… ») ; il
    est affiché depuis ``reports/``, quelle que soit la racine."""
    from brvm_alpha.report import html as H

    for racine in ("/home/user/documentation/brvm-alpha", "/var/lib/odoo/addons/rz_brvm_alpha/moteur", "/ailleurs"):
        p = f"{racine}/reports/validation_S1/precedent_20261122T121328Z"
        assert H._rel(p) == "reports/validation_S1/precedent_20261122T121328Z", racine
    assert H._rel(None) == "n.d." and H._rel("/var/lib/odoo/x/notes") == "/var/lib/odoo/x/notes"
    assert H._rel(H.ROOT / "reports" / "trials.parquet") == "reports/trials.parquet"


def test_the_filters_card_counts_filters_like_the_order_line():
    """Contrôle de a58b4c8, constat 23 : deux notes portant le même filtre comptaient deux filtres dans la carte (9) et un
    seul dans la ligne de l'ordre (8). Même compte partout ; le nombre de notes est donné en plus s'il diffère."""
    from brvm_alpha.ui import pages

    flt = [{"symbole": "FTSC", "code": "R10", "libelle": "x", "bloque_achats": False, "note_id": "a" * 40},
           {"symbole": "FTSC", "code": "R10", "libelle": "x", "bloque_achats": False, "note_id": "b" * 40},
           {"symbole": "ETIT", "code": "R2", "libelle": "y", "bloque_achats": True, "note_id": "c" * 40}]
    bloc = str(pages.notes_status_block({"line": "…", "filters": flt}))
    assert "Filtres de risque actifs issus des notes (2, venus de 3 notes)" in bloc
    assert "(1)</summary>" in str(pages.notes_status_block({"line": "…", "filters": flt[2:]}))
