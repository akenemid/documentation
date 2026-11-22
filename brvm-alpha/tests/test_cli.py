"""Tests de la ligne de commande (``python -m brvm_alpha``), **hors ligne**.

Aucune requête réseau : les téléchargements utilisent des clients simulés, les calculs lourds
(indices, ordre de bataille, explication) sont remplacés par des doublures ; les notes sont écrites
dans un journal temporaire. Aucun backtest, aucune performance ni aucun signal n'est évalué sur S1 :
on vérifie au contraire que les dates de S1 sont refusées avant tout calcul.
"""

from __future__ import annotations

import datetime as dt
import gzip
import json
from pathlib import Path

import pandas as pd
import pytest

from brvm_alpha import cli
from brvm_alpha.data import boc_download

FIX = Path(__file__).parent / "fixtures"
ROBOTS = (FIX / "notes" / "robots_brvm.txt").read_bytes()


# ---------------------------------------------------------------------------
# Analyse des arguments
# ---------------------------------------------------------------------------


def parse(*argv: str):
    return cli.build_parser().parse_args(list(argv))


def test_parser_update_panel_live():
    a = parse("update", "--from", "2026-11-01", "--simulation", "--max-requetes", "5")
    assert a.command == "update" and a.start == pd.Timestamp("2026-11-01") and a.simulation and a.max_requetes == 5
    assert a.delai == 10.0 and a.end is None and not a.sans_panel
    a = parse("update", "--from", "01/11/2026")
    assert a.start == pd.Timestamp("2026-11-01")
    a = parse("panel", "--force", "--workers", "2")
    assert a.command == "panel" and a.force and a.workers == 2
    a = parse("live", "--format", "json", "--symbole", "SNTS", "--hors-ligne")
    assert a.format == "json" and a.symbole == ["SNTS"] and a.hors_ligne


def test_parser_notes_subcommands():
    a = parse("notes", "add", "--cible", "SNTS", "--cible", "PAYS:SN", "--titre", "T", "--texte", "x", "--avis",
              "haussier", "--conviction", "4", "--horizon", "30", "--source", "presse", "--url", "https://ex.org/a",
              "--publie-le", "2026-11-20")
    assert (a.notes_cmd, a.cible, a.avis, a.conviction, a.horizon, a.publie_le) == (
        "add", ["SNTS", "PAYS:SN"], "haussier", 4, 30, "2026-11-20")
    a = parse("notes", "list", "--cible", "SNTS", "--depuis", "2026-01-01", "--statut", "toutes")
    assert a.notes_cmd == "list" and a.depuis == pd.Timestamp("2026-01-01") and a.statut == "toutes"
    assert parse("notes", "show", "abcd1234").id == "abcd1234"
    a = parse("notes", "archive", "abcd1234", "--motif", "doublon")
    assert a.notes_cmd == "archive" and a.motif == "doublon"
    assert parse("notes", "export", "--sortie", "-").sortie == "-"
    a = parse("notes", "research", "--cibles", "SNTS,BOAC", "--hors-ligne", "--max-requetes", "20")
    assert a.cibles == ["SNTS,BOAC"] and a.hors_ligne and a.max_requetes == 20
    a = parse("notes", "analyze", "--texte", "Le résultat net progresse de 20 %")
    assert a.notes_cmd == "analyze" and a.texte.startswith("Le résultat")


def test_parser_analysis_commands():
    a = parse("indices", "--date", "2026-11-20", "--detail")
    assert a.command == "indices" and a.indices_cmd is None and a.detail
    a = parse("indices", "dossier", "IDX:BRVM-30", "--date", "2026-11-20")
    assert a.indices_cmd == "dossier" and a.code == "IDX:BRVM-30" and a.date == pd.Timestamp("2026-11-20")
    a = parse("indices", "--date", "2026-11-19", "dossier", "IDX:BRVM-C")
    assert a.date == pd.Timestamp("2026-11-19") and a.format == "texte" and a.racine is None
    a = parse("universe")
    assert a.date is None
    a = parse("explain", "SNTS", "--variante", "A", "--date", "2026-11-20")
    assert a.symbole == "SNTS" and a.variante == "A"
    a = parse("backtest", "--start", "2023-01-02", "--end", "2023-06-30")
    assert a.variant == "A" and not a.validation_s1
    assert parse("validate", "--sample", "S0").sample == "S0"
    a = parse("recommend", "--capital", "10M", "--portefeuille", "p.csv", "--cash", "2 000 000", "--format", "json")
    assert a.capital == 10_000_000 and a.cash == 2_000_000 and a.format == "json" and a.portefeuille == "p.csv"
    a = parse("report", "--capital", "1,5Md", "--sortie", "r.html")
    assert a.capital == 1.5e9 and a.sortie == "r.html"
    a = parse("serve")
    assert a.port == 8765 and a.hote is None


def test_parser_errors_are_french(capsys):
    with pytest.raises(SystemExit) as e:
        parse("recommend")
    assert e.value.code == 2
    err = capsys.readouterr().err
    assert "utilisation :" in err and "erreur : arguments obligatoires manquants : --capital" in err
    with pytest.raises(SystemExit):
        parse("notes", "add", "--conviction", "7")
    assert "conviction : entier de 1 à 5" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        parse("commande-inconnue")
    assert "choix invalide" in capsys.readouterr().err


def test_help_is_french(capsys):
    with pytest.raises(SystemExit) as e:
        parse("-h")
    assert e.value.code == 0
    out = capsys.readouterr().out
    assert "commandes" in out and "affiche cette aide et quitte" in out and cli.BANNER in out
    for name in ("update", "panel", "live", "notes", "indices", "universe", "explain", "backtest", "validate",
                 "recommend", "report", "serve"):
        assert name in out


def test_input_parsers():
    assert cli.parse_capital("10 000 000") == 10_000_000
    assert cli.parse_capital("10M") == 10_000_000 and cli.parse_capital("250k") == 250_000
    assert cli.parse_capital("1,5 Md") == 1.5e9
    for bad in ("", "abc", "-5", "0"):
        with pytest.raises(ValueError):
            cli.parse_capital(bad)
    assert cli.parse_date("20/11/2026") == pd.Timestamp("2026-11-20")
    with pytest.raises(ValueError):
        cli.parse_date("2026-13-45")
    h = cli.parse_holdings("symbole,titres\nSNTS,120\n# commentaire\norac;15\nSNTS, 5\n\nBOAC\t0\n")
    assert h == {"SNTS": 125, "ORAC": 15}
    with pytest.raises(ValueError, match="ligne 1"):
        cli.parse_holdings("SNTS")
    with pytest.raises(ValueError, match="nombre de titres"):
        cli.parse_holdings("SNTS,1.5")
    with pytest.raises(ValueError, match="symbole invalide"):
        cli.parse_holdings("S<N>TS,3")
    assert cli.in_s1("2022-11-16") and not cli.in_s1("2022-11-17")
    assert cli.is_loopback("127.0.0.1") and cli.is_loopback("localhost") and cli.is_loopback("::1")
    assert not cli.is_loopback("0.0.0.0") and not cli.is_loopback("192.168.1.10")


# ---------------------------------------------------------------------------
# Notes : add / list / show / archive / export / analyze sur un journal temporaire
# ---------------------------------------------------------------------------


def test_notes_add_list_show_archive_export(tmp_path, capsys):
    root = str(tmp_path / "notes")
    code = cli.main(["notes", "add", "--racine", root, "--cible", "SNTS", "--titre", "Sonatel : résultat annuel",
                     "--texte", "Le résultat net atteint 450 milliards FCFA contre 390 milliards, en hausse de 15,4 %.",
                     "--avis", "haussier", "--conviction", "3", "--source", "rapport annuel",
                     "--publie-le", "2026-11-18"])
    out = capsys.readouterr().out
    assert code == 0 and "Note enregistrée" in out and "Analyse : type" in out and cli.BANNER in out
    from brvm_alpha.notes.store import NoteStore

    store = NoteStore(root)
    nid = store.ids()[0]
    note = store.get(nid)
    assert note.targets == ["SNTS"] and note.stance == "haussier" and note.analysis is not None
    assert "source:rapport annuel" in note.tags and note.author == "analyste"

    assert cli.main(["notes", "list", "--racine", root, "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["bandeau"] == cli.BANNER and payload["notes"][0]["note_id"] == nid

    assert cli.main(["notes", "list", "--racine", root, "--cible", "Sonatel"]) == 0
    assert nid[:12] in capsys.readouterr().out
    assert cli.main(["notes", "list", "--racine", root, "--cible", "ORAC"]) == 0
    assert "Aucune note" in capsys.readouterr().out

    assert cli.main(["notes", "show", "--racine", root, nid[:8]]) == 0
    out = capsys.readouterr().out
    assert "Sonatel : résultat annuel" in out and "Versions :" in out and "v1" in out

    assert cli.main(["notes", "archive", "--racine", root, nid[:8], "--motif", "test"]) == 0
    assert "archivée" in capsys.readouterr().out
    assert store.get(nid).status == "archived" and len(store.versions(nid)) == 2
    assert cli.main(["notes", "list", "--racine", root]) == 0
    assert "Aucune note" in capsys.readouterr().out
    assert cli.main(["notes", "list", "--racine", root, "--statut", "toutes"]) == 0
    assert "archivée" in capsys.readouterr().out  # statut affiché en français

    md = tmp_path / "export.md"
    assert cli.main(["notes", "export", "--racine", root, "--statut", "toutes", "--sortie", str(md)]) == 0
    assert "Sonatel : résultat annuel" in md.read_text(encoding="utf-8")


def test_notes_add_rejects_bad_input(tmp_path, capsys):
    root = str(tmp_path / "notes")
    assert cli.main(["notes", "add", "--racine", root, "--titre", "x", "--url", "javascript:alert(1)"]) == 2
    assert "adresse invalide" in capsys.readouterr().err
    assert cli.main(["notes", "add", "--racine", root]) == 2
    assert "titre ou un texte" in capsys.readouterr().err
    assert cli.main(["notes", "add", "--racine", root, "--titre", "x", "--publie-le", "2099-01-01"]) == 2
    assert "futur" in capsys.readouterr().err
    assert cli.main(["notes", "show", "--racine", root, "zzzz"]) == 2
    assert "identifiant invalide" in capsys.readouterr().err


def test_notes_unknown_target_is_kept_apart(tmp_path, capsys):
    root = str(tmp_path / "notes")
    assert cli.main(["notes", "add", "--racine", root, "--cible", "XXXXQ", "--titre", "Cible inconnue"]) == 0
    assert "Cibles non reconnues" in capsys.readouterr().out


def test_notes_analyze_does_not_write(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert cli.main(["notes", "analyze", "--texte", "Sonatel annonce un dividende net de 1 800 FCFA contre 1 655 FCFA",
                     "--titre", "Avis de paiement", "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["enregistree"] is False and "score" in payload["analyse"]
    assert not any(tmp_path.rglob("*.jsonl"))


def test_notes_research_offline_uses_no_network(tmp_path, capsys, monkeypatch):
    from brvm_alpha.notes import research as rs

    def no_network(*a, **k):
        raise AssertionError("aucune requête réseau attendue en mode hors ligne")

    monkeypatch.setattr(rs, "_requests_transport", no_network)
    seen = {}

    def fake_run(store, **kw):
        seen.update(kw)
        res = rs.ResearchResult()
        res.report = rs.ResearchReport(n_items=0)
        return res

    monkeypatch.setattr(rs, "run_research", fake_run)
    assert cli.main(["notes", "research", "--racine", str(tmp_path), "--hors-ligne", "--cibles", "SNTS, BOAC",
                     "--max-requetes", "7"]) == 0
    out = capsys.readouterr().out
    assert "Règles de politesse" in out and "hors ligne" in out
    assert seen["offline"] is True and seen["max_requests"] == 7 and seen["targets"] == ["SNTS", "BOAC"]


# ---------------------------------------------------------------------------
# Refus de S1 : aucune évaluation de signal avant le 17/11/2022
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("argv", [
    ["indices", "--date", "2020-03-02"],
    ["indices", "dossier", "IDX:BRVM-C", "--date", "2021-06-30"],
    ["explain", "SNTS", "--date", "2019-05-02"],
    ["recommend", "--capital", "10M", "--date", "2022-11-16"],
    ["report", "--capital", "10M", "--date", "2018-01-03"],
])
def test_s1_dates_are_refused_before_any_computation(argv, capsys, monkeypatch):
    from brvm_alpha.notes import index_eval
    from brvm_alpha.portfolio import recommend as rec

    def boom(*a, **k):
        raise AssertionError("aucun calcul ne doit être lancé sur S1")

    monkeypatch.setattr(index_eval, "evaluate_indices", boom)
    monkeypatch.setattr(index_eval, "index_dossier", boom)
    monkeypatch.setattr(rec, "recommend", boom)
    monkeypatch.setattr(cli, "explain_symbol", boom)
    assert cli.main(argv) == 2
    assert "échantillon vierge S1" in capsys.readouterr().err


def test_backtest_s1_still_refused(capsys):
    assert cli.main(["backtest", "--start", "2020-01-02", "--end", "2023-06-30"]) == 2
    assert "recoupe l'échantillon vierge S1" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# Indices, explication, ordre de bataille, rapport (doublures)
# ---------------------------------------------------------------------------


def _fake_eval(*a, **k):
    return pd.DataFrame({
        "label": ["BRVM Composite"], "date": [pd.Timestamp("2026-11-20")], "level": [492.89], "ret_1m": [-0.06],
        "ret_12m": [0.431], "ytd": [0.4256], "stance": ["SOUS-PONDÉRER"], "confidence": [0.59],
        "composite": [-0.53], "reasons": [["raison un", "raison deux", "raison trois", "raison quatre"]],
    }, index=pd.Index(["IDX:BRVM-C"], name="index"))


def test_indices_text_and_json(tmp_path, capsys, monkeypatch):
    from brvm_alpha.notes import index_eval

    calls = {}

    def fake(*a, **k):
        calls.update(k)
        return _fake_eval()

    monkeypatch.setattr(index_eval, "evaluate_indices", fake)
    assert cli.main(["indices", "--date", "2026-11-20", "--racine", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "SOUS-PONDÉRER" in out and "raison trois" in out and "raison quatre" not in out and "--detail" in out
    assert calls["asof"] == pd.Timestamp("2026-11-20") and calls["store"] is None
    assert cli.main(["indices", "--date", "2026-11-20", "--racine", str(tmp_path), "--detail"]) == 0
    assert "raison quatre" in capsys.readouterr().out
    assert cli.main(["indices", "--date", "2026-11-20", "--racine", str(tmp_path), "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["indices"][0]["stance"] == "SOUS-PONDÉRER" and payload["bandeau"] == cli.BANNER


def test_indices_dossier(tmp_path, capsys, monkeypatch):
    from brvm_alpha.notes import index_eval

    def fake(code, **k):
        assert code == "IDX:BRVM-30"
        return {"index": code, "label": "BRVM 30", "asof": pd.Timestamp("2026-11-20"), "composition": "officielle",
                "evaluation": {"date": pd.Timestamp("2026-11-20"), "stance": "NEUTRE", "confidence": 0.4,
                               "composite": 0.1},
                "constituents": pd.DataFrame({"name": ["Sonatel"], "weight": [0.3], "close": [4040.0]},
                                             index=pd.Index(["SNTS"], name="symbol")),
                "recent_notes": [{"note_id": "a" * 40, "first_tradable_session": pd.Timestamp("2026-11-19"),
                                  "title": "Note", "score": 0.4, "targets": ["SNTS"]}],
                "change_my_mind": ["seuil"], "calendar": pd.DataFrame(), "reasons": ["r1"], "overlays": None}

    monkeypatch.setattr(index_eval, "index_dossier", fake)
    assert cli.main(["indices", "dossier", "IDX:BRVM-30", "--date", "2026-11-20", "--racine", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "Dossier BRVM 30" in out and "Sonatel" in out and "Notes récentes qui l'influencent (1 note(s)" in out


def test_explain_text(capsys, monkeypatch):
    def fake(symbol, asof, **k):
        assert symbol == "SNTS" and asof == pd.Timestamp("2026-11-20") and k["variant"] == "A"
        return {"symbol": "SNTS", "asof": asof, "variant": "A", "text": "Résumé en français.",
                "blocks": {"Valeur": {"raw": 0.1, "z": 1.2, "weight": 0.25, "contribution": 0.3}},
                "score": {"final": 0.8, "rank": 3, "n_ranked": 30}, "weight": 0.05,
                "risk_flags": {"active": ["R4"]}, "banner": cli.BANNER, "choix_variante": None}

    monkeypatch.setattr(cli, "explain_symbol", fake)
    assert cli.main(["explain", "SNTS", "--date", "2026-11-20", "--variante", "A"]) == 0
    out = capsys.readouterr().out
    assert "Résumé en français." in out and "Valeur" in out and "R4" in out and cli.BANNER in out


class _FakeOrder:
    asof = pd.Timestamp("2026-11-20")

    def to_markdown(self):
        return "# Ordre de bataille\n\n> **" + cli.BANNER + "**\n"

    def to_dict(self):
        return {"bandeau": cli.BANNER, "lignes": []}

    def to_html_fragment(self):
        return '<section class="brvm-ordre-de-bataille"><p>fragment &lt;échappé&gt;</p></section>'


def test_recommend_formats_and_holdings(tmp_path, capsys, monkeypatch):
    from brvm_alpha.portfolio import recommend as rec

    seen = {}

    def fake(asof, capital, **k):
        seen.update(k, asof=asof, capital=capital)
        return _FakeOrder()

    monkeypatch.setattr(rec, "recommend", fake)
    csv = tmp_path / "pf.csv"
    csv.write_text("symbole,titres\nSNTS,10\nORAC,3\n", encoding="utf-8")
    assert cli.main(["recommend", "--capital", "10000000", "--date", "2026-11-20", "--portefeuille", str(csv),
                     "--format", "md", "--tirages", "100"]) == 0
    assert "# Ordre de bataille" in capsys.readouterr().out
    assert seen["holdings"] == {"SNTS": 10, "ORAC": 3} and seen["capital"] == 10_000_000 and seen["n_boot"] == 100
    assert cli.main(["recommend", "--capital", "10M", "--date", "2026-11-20", "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out)["bandeau"] == cli.BANNER
    out = tmp_path / "o.html"
    assert cli.main(["recommend", "--capital", "10M", "--date", "2026-11-20", "--format", "html", "--sortie",
                     str(out)]) == 0
    html = out.read_text(encoding="utf-8")
    import html as html_lib

    assert html.startswith("<!doctype html>") and html_lib.escape(cli.BANNER) in html
    assert "fragment &lt;échappé&gt;" in html
    assert "http" not in html.split("<main>")[0].replace("http-equiv", "")  # aucune ressource externe


def test_report_command(tmp_path, capsys, monkeypatch):
    import brvm_alpha.report as report

    seen = {}

    def fake(asof, capital, out, **k):
        seen.update(k, asof=asof, capital=capital, out=out)
        Path(out).write_text("<html></html>", encoding="utf-8")
        return Path(out)

    monkeypatch.setattr(report, "build_report", fake)
    target = tmp_path / "r.html"
    assert cli.main(["report", "--capital", "10M", "--date", "2026-11-20", "--sortie", str(target)]) == 0
    assert target.exists() and seen["capital"] == 10_000_000 and "Rapport écrit" in capsys.readouterr().out


def test_serve_binds_loopback_and_warns_for_other_host(monkeypatch, capsys):
    from brvm_alpha.ui import server

    calls = []

    class FakeSrv:
        server_address = ("127.0.0.1", 8765)

        def serve_forever(self):
            raise KeyboardInterrupt

        def shutdown_jobs(self):
            pass

        def server_close(self):
            pass

    def fake_make(host, port, *, allow_remote=False, services=None):
        calls.append((host, port, allow_remote))
        return FakeSrv()

    monkeypatch.setattr(server, "make_server", fake_make)
    assert cli.main(["serve", "--port", "0"]) == 0
    assert calls[-1] == ("127.0.0.1", 0, False)
    assert cli.main(["serve", "--hote", "0.0.0.0"]) == 0
    assert calls[-1] == ("0.0.0.0", 8765, True)
    assert "AVERTISSEMENT" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# update : politesse du téléchargement (aucune requête réelle)
# ---------------------------------------------------------------------------


class FakeClock:
    def __init__(self):
        self.t = 1000.0
        self.sleeps: list[float] = []

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.sleeps.append(s)
        self.t += s


class FakeResp:
    def __init__(self, status, content=b""):
        self.status_code, self.content = status, content


class FakeHTTP:
    """Session ``requests`` simulée : URL -> statut ; enregistre l'heure de chaque requête."""

    def __init__(self, clock, pages):
        self.clock, self.pages, self.calls = clock, pages, []

    def get(self, url, **kw):
        self.calls.append((url, self.clock.t))
        self.clock.t += 0.2
        st = self.pages.get(url, 404)
        return FakeResp(st, ROBOTS if url.endswith("robots.txt") else b"")


def test_boc_download_default_delay_is_ten_seconds():
    import inspect

    assert boc_download.DEFAULT_PAUSE_S == 10.0
    assert inspect.signature(boc_download.download_range).parameters["pause"].default == 10.0
    assert boc_download.PoliteFetcher(pause=0.4).delay == 10.0  # plancher, quel que soit le réglage


def test_polite_fetcher_spacing_robots_and_stop_on_403(tmp_path):
    clock = FakeClock()
    http = FakeHTTP(clock, {boc_download.ROBOTS_URL: 200})
    f = boc_download.PoliteFetcher(http, pause=0.4, sleep=clock.sleep, clock=clock)
    day = dt.date(2026, 11, 18)
    assert boc_download.fetch_one(f, day, tmp_path, mark_missing=True) is None
    times = [t for _, t in http.calls]
    assert http.calls[0][0] == boc_download.ROBOTS_URL and len(http.calls) == 1 + len(boc_download.RECENT_SUFFIXES)
    assert min(b - a for a, b in zip(times, times[1:])) >= 10.0 - 1e-9
    assert (tmp_path / "boc_20261118.missing").exists()

    clock2 = FakeClock()
    url = boc_download.BASE_URL.format(date="20261119", suffix="_2")
    http2 = FakeHTTP(clock2, {boc_download.ROBOTS_URL: 200, url: 403})
    f2 = boc_download.PoliteFetcher(http2, sleep=clock2.sleep, clock=clock2)
    with pytest.raises(boc_download.DownloadStopped, match="403"):
        boc_download.download_range(dt.date(2026, 11, 17), dt.date(2026, 11, 20), tmp_path, fetcher=f2,
                                    today=dt.date(2026, 11, 22))
    n_calls = len(http2.calls)
    assert not (tmp_path / "boc_20261119.missing").exists()  # un refus n'est pas un jour sans bulletin
    with pytest.raises(boc_download.DownloadStopped):
        f2(boc_download.BASE_URL.format(date="20261117", suffix=""))
    assert len(http2.calls) == n_calls  # plus aucune requête après l'arrêt


def test_polite_fetcher_honours_robots_disallow(tmp_path):
    clock = FakeClock()

    class DenyAll(FakeHTTP):
        def get(self, url, **kw):
            self.calls.append((url, self.clock.t))
            body = b"User-agent: *\nDisallow: /sites/\n" if url.endswith("robots.txt") else b""
            return FakeResp(200, body)

    http = DenyAll(clock, {})
    f = boc_download.PoliteFetcher(http, sleep=clock.sleep, clock=clock)
    with pytest.raises(boc_download.DownloadStopped, match="robots.txt"):
        boc_download.fetch_one(f, dt.date(2026, 11, 18), tmp_path)
    assert len(http.calls) == 1  # seul robots.txt a été lu


def test_recent_days_are_not_marked_missing(tmp_path):
    calls = []

    def fetch(url):
        calls.append(url)
        return 404, b""

    n = boc_download.download_range(dt.date(2026, 11, 16), dt.date(2026, 11, 20), tmp_path, fetcher=fetch,
                                    today=dt.date(2026, 11, 20))
    assert n == 0 and calls
    assert (tmp_path / "boc_20261116.missing").exists()
    assert not (tmp_path / "boc_20261118.missing").exists() and not (tmp_path / "boc_20261120.missing").exists()


def test_update_simulation_sends_nothing(tmp_path, capsys, monkeypatch):
    boc = tmp_path / "boc"
    boc.mkdir()
    with gzip.open(boc / "boc_20261117.txt.gz", "wt", encoding="utf-8") as fh:
        fh.write("x")
    monkeypatch.setattr(boc_download, "download_range", lambda *a, **k: (_ for _ in ()).throw(AssertionError("réseau")))
    assert cli.main(["update", "--boc-dir", str(boc), "--jusqu-au", "2026-11-20", "--simulation"]) == 0
    out = capsys.readouterr().out
    assert "du 18/11/2026 au 20/11/2026 : 3 jour(s)" in out and "2026-11-19" in out and "aucune requête" in out
    assert "10 s au moins" in out


def test_update_stops_at_first_403_and_keeps_panel(tmp_path, capsys, monkeypatch):
    from brvm_alpha.data import store
    from brvm_alpha.notes import research as rs

    boc = tmp_path / "boc"
    boc.mkdir()
    monkeypatch.setattr(rs, "DEFAULT_NOTES_DIR", tmp_path / "notes")
    calls = []

    def fake_fetcher(**kw):
        def fetch(url):
            calls.append(url)
            raise boc_download.DownloadStopped("www.brvm.org a répondu HTTP 403 : téléchargement arrêté")

        fetch.session = type("S", (), {"n_requests": 1})()
        return fetch

    monkeypatch.setattr(cli, "brvm_fetcher", fake_fetcher)
    monkeypatch.setattr(store, "build_panel", lambda *a, **k: (_ for _ in ()).throw(AssertionError("panel")))
    code = cli.main(["update", "--boc-dir", str(boc), "--from", "2026-11-19", "--jusqu-au", "2026-11-20"])
    assert code == 1 and len(calls) == 1
    assert "arrêt" in capsys.readouterr().err
    assert not list(boc.glob("*.missing"))


def test_update_refuses_when_brvm_is_blocked(tmp_path, capsys, monkeypatch):
    from brvm_alpha.notes import research as rs

    monkeypatch.setattr(rs, "DEFAULT_NOTES_DIR", tmp_path / "notes")
    monkeypatch.setattr(rs, "blocked_hosts", lambda cache_dir=None: {"www.brvm.org": {"ts": "x", "status": 429}})
    monkeypatch.setattr(cli, "brvm_fetcher", lambda **k: (_ for _ in ()).throw(AssertionError("réseau")))
    boc = tmp_path / "boc"
    boc.mkdir()
    assert cli.main(["update", "--boc-dir", str(boc), "--from", "2026-11-19", "--jusqu-au", "2026-11-20"]) == 2
    assert "refusé" in capsys.readouterr().err


def test_brvm_fetcher_wraps_polite_session(tmp_path, monkeypatch):
    """Le client de ``update`` passe par ``PoliteSession`` : robots.txt, délai de 10 s, arrêt au 403."""
    from brvm_alpha.notes import research as rs

    clock = FakeClock()
    pages = {"https://www.brvm.org/robots.txt": (200, ROBOTS)}
    url_ok = boc_download.BASE_URL.format(date="20261118", suffix="_2")
    url_403 = boc_download.BASE_URL.format(date="20261119", suffix="_2")
    pages[url_ok] = (200, b"%PDF-1.4 ...")
    pages[url_403] = (403, b"")
    seen = []

    def transport(url, headers, timeout):
        seen.append((url, clock.t))
        clock.t += 0.1
        st, body = pages.get(url, (404, b""))
        return FakeResp(st, body)

    real_init = rs.PoliteSession.__init__

    def init(self, **kw):
        kw.update(transport=transport, clock=clock, sleep=clock.sleep, now=lambda: dt.datetime(2026, 11, 22,
                                                                                               tzinfo=dt.timezone.utc))
        real_init(self, **kw)

    monkeypatch.setattr(rs.PoliteSession, "__init__", init)
    fetch = cli.brvm_fetcher(max_requests=10, cache_dir=tmp_path / "cache")
    assert fetch(url_ok) == (200, b"%PDF-1.4 ...")
    with pytest.raises(boc_download.DownloadStopped):
        fetch(url_403)
    assert [u for u, _ in seen][0].endswith("robots.txt")
    gaps = [b - a for (_, a), (_, b) in zip(seen, seen[1:])]
    assert gaps and min(gaps) >= 10.0 - 1e-9
    assert rs.blocked_hosts(tmp_path / "cache").get("www.brvm.org")  # blocage persistant après le 403
    assert not list((tmp_path / "cache").rglob("*.body.gz"))  # aucun PDF conservé dans le cache HTTP


def test_live_offline_reads_cached_page(tmp_path, capsys, monkeypatch):
    from brvm_alpha.data import live
    from brvm_alpha.notes import research as rs

    monkeypatch.setattr(rs, "DEFAULT_NOTES_DIR", tmp_path / "notes")
    sess = rs.PoliteSession(offline=True, cache_dir=tmp_path / "notes" / "cache", log_path=tmp_path / "log.jsonl")
    sess.cache_put(live.LIVE_URL, (FIX / "brvm_cours_actions.html").read_bytes(), 200,
                   {"Content-Type": "text/html; charset=utf-8"})
    assert cli.main(["live", "--hors-ligne", "--symbole", "BBGC"]) == 0
    out = capsys.readouterr().out
    assert "BBGC" in out and "8 145" in out and "BRVM-C" in out and cli.BANNER in out
