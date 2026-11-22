"""Tests de l'interface web locale (``brvm_alpha.ui``), **hors ligne**.

Le serveur est lancé sur un port libre dans un fil ; les calculs lourds (indices, explication,
ordre de bataille, rapport) sont remplacés par des doublures ; les notes sont écrites dans un
journal temporaire ; la recherche est exécutée en mode hors ligne (aucune requête réseau : le
transport HTTP est remplacé par une fonction qui échoue si elle est appelée). Aucun calcul sur S1.
"""

from __future__ import annotations

import http.client
import json
import re
import threading
import time
from pathlib import Path
from urllib.parse import urlencode

import pandas as pd
import pytest

from brvm_alpha.notes.store import NoteStore
from brvm_alpha.ui import pages
from brvm_alpha.ui import server as S

FIX = Path(__file__).parent / "fixtures"
BOC_FIX = FIX / "notes" / "boc"


class FakeOrder:
    asof = pd.Timestamp("2026-11-20")

    def to_html_fragment(self):
        return '<section class="brvm-ordre-de-bataille"><h1>Ordre de bataille</h1><p>SNTS &lt;achat&gt;</p></section>'

    def to_markdown(self):
        return "# Ordre de bataille\n"

    def to_dict(self):
        return {"bandeau": pages.BANNER, "lignes": [{"titre": "SNTS"}]}


def fake_evaluation() -> pd.DataFrame:
    return pd.DataFrame({
        "label": ["BRVM Composite", "BRVM 30"], "date": [pd.Timestamp("2026-11-20")] * 2, "level": [492.89, 238.73],
        "ret_1m": [-0.06, -0.06], "ret_3m": [-0.05, -0.045], "ret_12m": [0.43, 0.44], "ytd": [0.42, 0.43],
        "per": [15.8, 13.1], "yield_pct": [7.1, 4.7], "stance": ["SOUS-PONDÉRER", "NEUTRE"], "confidence": [0.59, 0.4],
        "composite": [-0.53, -0.2], "reasons": [["Tendance <forte>", "Valorisation"], ["Largeur"]],
    }, index=pd.Index(["IDX:BRVM-C", "IDX:BRVM-30"], name="index"))


class FakeServices(S.Services):
    def __init__(self, tmp: Path, **kw):
        super().__init__(notes_root=tmp / "notes", panel_dir=tmp / "panel", reports_dir=tmp / "reports",
                         validation_dir=tmp / "val", diagnostic_dir=tmp / "diag", boc_dir=BOC_FIX,
                         research_kwargs={"panel_dir": None, "boc_last_n": 3, **kw})
        self.calls: list[tuple[str, object]] = []
        (tmp / "val").mkdir()
        (tmp / "val" / "resultats.md").write_text(
            "# Validation S1\n\n> **Performance passée ≠ garantie.**\n\n| Var. | Statut |\n|---|---|\n| A | REJETÉ |\n\n"
            "Texte <script>alert('md')</script> et `code`.\n", encoding="utf-8")
        (tmp / "diag").mkdir()
        (tmp / "diag" / "resultats.md").write_text("# Diagnostic S0\n\n- contaminé\n", encoding="utf-8")

    def last_session(self):
        return pd.Timestamp("2026-11-20")

    #: Contrôle « panel en retard » : coupé par défaut (il dépend de l'heure réelle) ; les tests de la
    #: recette l'activent avec une horloge fixe (``services.clock``).
    panel_late_check = False

    def panel_warning(self):
        return super().panel_warning() if self.panel_late_check else None

    def symbol_names(self):
        return {"SNTS": "SONATEL"}

    def evaluate_indices(self, asof):
        self.calls.append(("indices", asof))
        return fake_evaluation(), False

    def index_dossier(self, code, asof):
        self.calls.append(("dossier", code))
        return {"index": code, "label": "BRVM 30", "asof": asof, "composition": "officielle",
                "evaluation": {"date": asof, "stance": "NEUTRE", "confidence": 0.4, "composite": -0.2, "level": 238.7},
                "constituents": pd.DataFrame({"name": ["SONATEL"], "weight": [0.3], "close": [4040.0],
                                              "flags": [["R4"]], "veto": [False]},
                                             index=pd.Index(["SNTS"], name="symbol")),
                "recent_notes": [{"note_id": "ab" * 20, "first_tradable_session": asof, "title": "Note <b>",
                                  "targets": ["SNTS"], "score": 0.4, "decay": 0.9, "risk_flags": []}],
                "change_my_mind": ["seuil chiffré"], "calendar": pd.DataFrame(), "reasons": ["raison"]}

    def explain(self, symbol, asof, variant):
        self.calls.append(("explain", symbol))
        return {"symbol": symbol, "asof": asof, "variant": variant or "REF", "eligible": True,
                "text": "Explication <en> français.", "blocks": {"Valeur": {"raw": 0.1, "z": 1.0, "weight": 0.25,
                                                                           "contribution": 0.25}},
                "score": {"final": 0.5, "rank": 2, "n_ranked": 30}, "weight": 0.05,
                "risk_flags": {"active": [], "block_buys": False}, "notes": {"available": False}, "caps": {}}

    def recommend(self, **kw):
        self.calls.append(("recommend", kw))
        kw["log"]("calcul simulé")
        return FakeOrder()

    def build_report(self, *, asof, capital, log):
        out = self.report_target(asof)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("<!doctype html><html><head><title>Rapport</title></head><body><p>rapport simulé</p>"
                       "</body></html>", encoding="utf-8")
        log(f"écrit {out.name}")
        return out

    def read_validation(self):
        return {"etat": "exécuté", "statut_A": "REJETÉ", "principal": "A", "statut_principal": "REJETÉ",
                "avertissements": [], "dossier": "val"}

    def choose_variant(self):
        return {"variante": "REF", "motif": "A est REJETÉ sur S1"}


@pytest.fixture()
def ui(tmp_path, monkeypatch):
    from brvm_alpha.notes import research as rs

    def no_network(*a, **k):
        raise AssertionError("aucune requête réseau dans les tests")

    monkeypatch.setattr(rs, "_requests_transport", no_network)
    services = FakeServices(tmp_path)
    srv = S.make_server("127.0.0.1", 0, services=services)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    try:
        yield srv
    finally:
        srv.shutdown()
        srv.shutdown_jobs()
        srv.server_close()


def call(srv, method: str, path: str, form=None, *, host: str | None = None, headers=None, raw: bytes | None = None):
    conn = http.client.HTTPConnection("127.0.0.1", srv.port, timeout=60)
    h = {"Host": host if host is not None else f"127.0.0.1:{srv.port}"}
    data = None
    if form is not None or raw is not None:
        data = raw if raw is not None else urlencode(form, doseq=True).encode("utf-8")
        h["Content-Type"] = "application/x-www-form-urlencoded"
        h["Content-Length"] = str(len(data))
    h.update(headers or {})
    conn.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
    for k, v in h.items():
        conn.putheader(k, v)
    conn.endheaders(data)
    r = conn.getresponse()
    out = (r.status, {k.lower(): v for k, v in r.getheaders()}, r.read().decode("utf-8", "replace"))
    conn.close()
    return out


def token(srv) -> str:
    return srv.csrf_token


def wait_job(srv, kind: str, timeout: float = 120.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = srv.jobs.latest(kind)
        if job is not None and job.done.is_set():
            return job
        time.sleep(0.05)
    raise AssertionError(f"travail {kind} non terminé")


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

PAGES = ["/", "/notes", "/recherche", "/indices", "/indices/dossier?code=IDX:BRVM-30", "/portefeuille", "/expliquer",
         "/expliquer?symbole=SNTS", "/validation"]


@pytest.mark.parametrize("path", PAGES)
def test_every_page_answers_200_in_french_with_banner(ui, path):
    status, headers, body = call(ui, "GET", path)
    assert status == 200, body[:500]
    assert '<html lang="fr">' in body and pages.esc(pages.BANNER) in body
    assert headers["content-type"].startswith("text/html")
    assert re.search(r"(src|href)=\"https?://", body.split("</head>")[0]) is None  # aucune ressource externe


def test_security_headers_and_nonce(ui):
    status, h, body = call(ui, "GET", "/")
    csp = h["content-security-policy"]
    nonce = re.search(r"script-src 'nonce-([^']+)'", csp).group(1)
    assert f'<script nonce="{nonce}">' in body and "default-src 'none'" in csp and "frame-ancestors 'none'" in csp
    assert h["x-frame-options"] == "DENY" and h["x-content-type-options"] == "nosniff"
    assert h["referrer-policy"] == "same-origin" and h["cache-control"] == "no-store"
    assert "Python" not in h.get("server", "")
    # thème clair/sombre, gouttière et tableau défilant pour téléphone
    assert "prefers-color-scheme: dark" in body and ':root[data-theme="dark"]' in body and ".tablewrap" in body
    assert 'name="viewport"' in body


def test_unknown_page_404_and_method_not_allowed(ui):
    assert call(ui, "GET", "/inconnue")[0] == 404
    status, h, _ = call(ui, "PUT", "/notes")
    assert status == 405 and "POST" in h["allow"]
    assert call(ui, "HEAD", "/")[0] == 200


# ---------------------------------------------------------------------------
# Sécurité : Host, CSRF, Origin, corps
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("host", ["evil.example", "evil.example:{port}", "127.0.0.1:1", "", "localhost.evil:{port}"])
def test_foreign_host_is_refused(ui, host):
    status, _, body = call(ui, "GET", "/", host=host.format(port=ui.port))
    assert status in (400, 403) and "Hôte refusé" in body
    status, _, _ = call(ui, "POST", "/notes/ajouter", {"_jeton": token(ui), "titre": "x"},
                        host=host.format(port=ui.port))
    assert status in (400, 403)
    assert len(NoteStore(ui.services.notes_root)) == 0


def test_localhost_host_accepted(ui):
    assert call(ui, "GET", "/", host=f"localhost:{ui.port}")[0] == 200


def test_post_note_without_token_is_403_then_with_token_creates_analysed_note(ui):
    form = {"cibles": "SNTS", "titre": "Sonatel : dividende en hausse",
            "texte": "Sonatel annonce un dividende net de 1 800 FCFA contre 1 655 FCFA l'an dernier.",
            "avis": "haussier", "conviction": "4", "horizon": "20", "source": "avis de paiement",
            "publie_le": "2026-11-18", "heure": "08:30"}
    status, _, body = call(ui, "POST", "/notes/ajouter", form)
    assert status == 403 and "jeton anti-CSRF" in body
    status, _, _ = call(ui, "POST", "/notes/ajouter", form | {"_jeton": "faux-jeton"})
    assert status == 403
    store = NoteStore(ui.services.notes_root)
    assert len(store) == 0

    status, h, _ = call(ui, "POST", "/notes/ajouter", form | {"_jeton": token(ui)})
    assert status == 303 and h["location"].startswith("/notes/fiche?id=")
    assert len(store) == 1
    note = next(iter(store))
    assert note.targets == ["SNTS"] and note.stance == "haussier" and note.conviction == 4
    assert note.analysis is not None and "score" in note.analysis
    assert note.published_at == pd.Timestamp("2026-11-18 08:30", tz="UTC")
    status, _, body = call(ui, "GET", h["location"])
    assert status == 200 and "Note enregistrée et analysée" in body and "Analyse" in body
    assert "Versions" in body and "Archiver" in body and "Lecture" in body
    status, _, body = call(ui, "GET", "/notes?cible=SNTS")
    assert status == 200 and "Sonatel : dividende en hausse" in body


def test_foreign_origin_is_refused_even_with_token(ui):
    status, _, body = call(ui, "POST", "/notes/ajouter", {"_jeton": token(ui), "titre": "x"},
                           headers={"Origin": "http://evil.example"})
    assert status == 403
    status, _, _ = call(ui, "POST", "/notes/ajouter", {"_jeton": token(ui), "titre": "x"},
                        headers={"Sec-Fetch-Site": "cross-site"})
    assert status == 403
    assert len(NoteStore(ui.services.notes_root)) == 0
    status, _, _ = call(ui, "POST", "/notes/ajouter", {"_jeton": token(ui), "titre": "même origine"},
                        headers={"Origin": f"http://127.0.0.1:{ui.port}", "Sec-Fetch-Site": "same-origin"})
    assert status == 303


def test_body_size_and_content_type_limits(ui):
    big = b"_jeton=" + token(ui).encode() + b"&texte=" + b"a" * (S.MAX_BODY_BYTES + 10)
    status, _, body = call(ui, "POST", "/notes/ajouter", raw=big)
    assert status == 413
    conn = http.client.HTTPConnection("127.0.0.1", ui.port, timeout=30)
    data = json.dumps({"_jeton": token(ui)}).encode()
    conn.request("POST", "/notes/ajouter", body=data, headers={"Host": f"127.0.0.1:{ui.port}",
                                                                "Content-Type": "application/json"})
    assert conn.getresponse().status == 415
    conn.close()


def test_title_with_script_is_escaped_everywhere(ui):
    evil = '<script>alert("x")</script><img src=x onerror=alert(1)>'
    status, h, _ = call(ui, "POST", "/notes/ajouter", {"_jeton": token(ui), "titre": evil, "texte": evil,
                                                       "cibles": "SNTS"})
    assert status == 303
    for path in (h["location"], "/notes", "/"):
        status, _, body = call(ui, "GET", path)
        assert status == 200
        assert '<script>alert("x")' not in body and "<img src=x" not in body
        assert "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;" in body


def test_invalid_note_input_rerenders_form_with_values(ui):
    status, _, body = call(ui, "POST", "/notes/ajouter", {"_jeton": token(ui), "titre": "Titre <gardé>",
                                                          "url": "javascript:alert(1)"})
    assert status == 400 and "adresse invalide" in body and 'value="Titre &lt;gardé&gt;"' in body
    assert len(NoteStore(ui.services.notes_root)) == 0


def test_archive_note(ui):
    _, h, _ = call(ui, "POST", "/notes/ajouter", {"_jeton": token(ui), "titre": "À archiver", "cibles": "ORAC"})
    nid = h["location"].split("id=")[1].split("&")[0]
    assert call(ui, "POST", "/notes/archiver", {"id": nid})[0] == 403
    status, h2, _ = call(ui, "POST", "/notes/archiver", {"_jeton": token(ui), "id": nid, "motif": "doublon"})
    assert status == 303
    store = NoteStore(ui.services.notes_root)
    assert store.get(nid).status == "archived" and len(store.versions(nid)) == 2
    body = call(ui, "GET", h2["location"])[2]
    assert "Note archivée" in body
    assert "À archiver" not in call(ui, "GET", "/notes")[2]
    assert "À archiver" in call(ui, "GET", "/notes?statut=toutes")[2]


# ---------------------------------------------------------------------------
# Recherche (hors ligne simulée), travaux
# ---------------------------------------------------------------------------


def test_research_offline_requires_confirmation_then_runs_without_network(ui):
    status, _, body = call(ui, "GET", "/recherche")
    assert "Règles de politesse" in body and "10 s" in body and "403" in body
    status, _, body = call(ui, "POST", "/recherche/lancer", {"_jeton": token(ui), "mode": "hors_ligne",
                                                             "max_requetes": "10"})
    assert status == 400 and "confirmation" in body
    status, _, body = call(ui, "POST", "/recherche/lancer", {"_jeton": token(ui), "mode": "en_ligne",
                                                             "max_requetes": "999", "confirmer": "oui"})
    assert status == 400 and "quota" in body
    status, h, _ = call(ui, "POST", "/recherche/lancer", {"_jeton": token(ui), "mode": "hors_ligne",
                                                          "max_requetes": "10", "confirmer": "oui"})
    assert status == 303 and h["location"] == "/recherche"
    job = wait_job(ui, "recherche")
    assert job.status == "terminé", job.snapshot()
    assert job.result["requetes"] == 0
    log = "\n".join(job.snapshot()["journal"])
    assert "hors ligne" in log and "aucune requête" in log
    status, _, body = call(ui, "GET", "/recherche")
    assert status == 200 and job.id in body
    store = NoteStore(ui.services.notes_root)
    assert len(store) == len(job.result["notes"])
    if job.result["notes"]:
        assert "Nouvelles notes de la dernière recherche" in body
    status, _, js = call(ui, "GET", f"/api/travail?id={job.id}")
    snap = json.loads(js)
    assert status == 200 and snap["termine"] and snap["statut"] == "terminé"
    assert call(ui, "GET", "/api/travail?id=0123456789abcdef")[0] == 404


def test_one_long_operation_at_a_time(ui):
    gate = threading.Event()
    job = ui.jobs.start("rapport", "travail bloquant", lambda j: gate.wait(30))
    try:
        status, _, body = call(ui, "POST", "/rapport/regenerer", {"_jeton": token(ui), "capital": "10 000 000"})
        assert status == 409 and "déjà en cours" in body
        status, _, body = call(ui, "POST", "/recherche/lancer", {"_jeton": token(ui), "mode": "hors_ligne",
                                                                 "max_requetes": "5", "confirmer": "oui"})
        assert status == 409
        status, _, body = call(ui, "GET", "/")
        assert f'data-job-id="{job.id}"' in body and 'data-job-state="en cours"' in body
    finally:
        gate.set()
    ui.jobs.wait(job.id, 10)
    assert job.status == "terminé"


def test_report_regeneration_and_whitelisted_serving(ui):
    status, h, _ = call(ui, "POST", "/rapport/regenerer", {"_jeton": token(ui), "capital": "10M"})
    assert status == 303
    job = wait_job(ui, "rapport")
    assert job.status == "terminé"
    path = ui.services.reports_dir / "rapport_2026-11-20.html"
    assert path.exists()
    status, _, body = call(ui, "GET", "/")
    assert "rapport_2026-11-20.html" in body and "<iframe" in body and 'sandbox="allow-scripts' in body
    status, hh, body = call(ui, "GET", "/rapport/voir?nom=rapport_2026-11-20.html")
    assert status == 200 and "rapport simulé" in body and "sandbox" in hh["content-security-policy"]
    assert hh["x-frame-options"] == "SAMEORIGIN"
    for bad in ("../../etc/passwd", "..%2F..%2Fpyproject.toml", "/etc/passwd", "inconnu.html"):
        assert call(ui, "GET", f"/rapport/voir?nom={bad}")[0] == 404
    status, _, body = call(ui, "POST", "/rapport/regenerer", {"_jeton": token(ui), "capital": "abc"})
    assert status == 400 and "montant invalide" in body


def test_portfolio_job_result_and_exports(ui):
    status, _, body = call(ui, "POST", "/portefeuille/calculer", {"_jeton": token(ui), "capital": "10 000 000",
                                                                  "portefeuille": "SNTS,abc"})
    assert status == 400 and "nombre de titres invalide" in body
    status, _, body = call(ui, "POST", "/portefeuille/calculer", {"_jeton": token(ui), "capital": "10M",
                                                                  "date": "2021-03-01"})
    assert status == 400 and "échantillon vierge S1" in body
    assert not [c for c in ui.services.calls if c[0] == "recommend"]
    status, h, _ = call(ui, "POST", "/portefeuille/calculer", {"_jeton": token(ui), "capital": "10M",
                                                               "portefeuille": "SNTS,120\nORAC,15", "cash": "",
                                                               "variante": "", "tirages": "1000"})
    assert status == 303 and h["location"].startswith("/portefeuille?travail=")
    job = wait_job(ui, "portefeuille")
    assert job.status == "terminé"
    kw = [c for c in ui.services.calls if c[0] == "recommend"][-1][1]
    assert kw["holdings"] == {"SNTS": 120, "ORAC": 15} and kw["capital"] == 10_000_000 and kw["n_boot"] == 1000
    status, _, body = call(ui, "GET", h["location"])
    assert status == 200 and "SNTS &lt;achat&gt;" in body and "Exports" in body
    status, hh, md = call(ui, "GET", f"/portefeuille/resultat?travail={job.id}&format=md")
    assert status == 200 and md.startswith("# Ordre de bataille") and hh["content-type"].startswith("text/plain")
    status, _, js = call(ui, "GET", f"/portefeuille/resultat?travail={job.id}&format=json")
    assert status == 200 and json.loads(js)["bandeau"] == pages.BANNER


def test_indices_dossier_explain_and_s1_refusal(ui):
    status, _, body = call(ui, "GET", "/indices")
    assert status == 200 and "SOUS-PONDÉRER" in body and "Tendance &lt;forte&gt;" in body
    assert "/indices/dossier?code=IDX%3ABRVM-C" in body
    n = len(ui.services.calls)
    status, _, body = call(ui, "GET", "/indices?date=2020-01-02")
    assert status == 400 and "échantillon vierge S1" in body and len(ui.services.calls) == n
    status, _, body = call(ui, "GET", "/indices/dossier?code=IDX:BRVM-30")
    assert status == 200 and "Notes récentes qui l" in body and "Note &lt;b&gt;" in body and "seuil chiffré" in body
    status, _, body = call(ui, "GET", "/indices/dossier?code=%3Cscript%3E")
    assert status == 400 and "<script>" not in body.split("<main>")[1]
    status, _, body = call(ui, "GET", "/expliquer?symbole=snts")
    assert status == 200 and "Explication &lt;en&gt; français." in body
    status, _, body = call(ui, "GET", "/expliquer?symbole=SNTS&date=2019-01-02")
    assert status == 400 and "échantillon vierge S1" in body
    status, _, body = call(ui, "GET", "/expliquer?symbole=%3Cb%3E")
    assert status == 400 and "symbole invalide" in body


def test_validation_page_renders_markdown_safely(ui):
    status, _, body = call(ui, "GET", "/validation")
    assert status == 200 and "REJETÉ" in body and "<table>" in body
    assert "<script>alert('md')" not in body and "&lt;script&gt;alert(&#x27;md&#x27;)" in body
    assert "Diagnostic S0" in body and "contaminé" in body


def test_server_refuses_non_loopback_address():
    with pytest.raises(ValueError, match="127.0.0.1"):
        S.make_server("0.0.0.0", 0)


def test_job_manager_reports_failures():
    jm = S.JobManager()

    def fail(job):
        job.log("étape 1")
        raise RuntimeError("panne simulée")

    job = jm.start("x", "échec attendu", fail)
    jm.wait(job.id, 10)
    snap = job.snapshot()
    assert snap["statut"] == "échec" and "panne simulée" in snap["erreur"] and snap["termine"]
    assert any("étape 1" in line for line in snap["journal"])
