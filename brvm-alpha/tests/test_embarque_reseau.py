"""Couches internes du moteur embarqué : réseau commun, politesse, recherche des notes, cours du jour.

Aucune requête vers l'extérieur : serveurs HTTP locaux factices (127.0.0.1) et doublures. Les cas
couverts : liste blanche (requête et chaque redirection), redirection vers un autre hôte, https → http,
adresse locale ou privée après résolution DNS, réponse trop grosse (annoncée, en flux, compressée),
réponse lente (délai total, délai par opération), ``MemoryError`` jamais prise pour une erreur réseau,
robots.txt redirigé ou illisible, état de politesse daté dans le futur, verrou de l'état entre deux
processus, recherche écrite au fil de l'eau et bilan structuré, cours du jour poli.

Performance passée ≠ garantie. Aucun gain n'est garanti.
"""

from __future__ import annotations

import datetime as dt
import gzip
import http.server
import json
import os
import shutil
import socket
import ssl
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from brvm_alpha import erreurs, net
from brvm_alpha.notes import research as rs

ROOT = Path(__file__).resolve().parents[1]
UTC = dt.timezone.utc
NOW = dt.datetime(2026, 11, 22, 3, 40, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Serveur HTTP local factice
# ---------------------------------------------------------------------------


class _Handler(http.server.BaseHTTPRequestHandler):
    routes: dict[str, Any] = {}

    def log_message(self, *args: Any) -> None:  # silence
        return

    def do_GET(self) -> None:  # noqa: N802 - nom imposé par http.server
        self.server.hits.append(self.path)  # type: ignore[attr-defined]
        route = self.server.routes.get(self.path.split("?")[0])  # type: ignore[attr-defined]
        if route is None:
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        route(self)


class LocalServer:
    """Serveur HTTP (ou HTTPS) sur 127.0.0.1, dans un fil d'exécution."""

    def __init__(self, routes: dict[str, Any], context: ssl.SSLContext | None = None) -> None:
        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self.httpd.routes = routes  # type: ignore[attr-defined]
        self.httpd.hits = []  # type: ignore[attr-defined]
        self.httpd.daemon_threads = True
        if context is not None:
            self.httpd.socket = context.wrap_socket(self.httpd.socket, server_side=True)
        self.port = self.httpd.server_address[1]
        self.scheme = "https" if context is not None else "http"
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    @property
    def base(self) -> str:
        return f"{self.scheme}://127.0.0.1:{self.port}"

    @property
    def hits(self) -> list[str]:
        return self.httpd.hits  # type: ignore[attr-defined]

    def close(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


def reply(status: int, body: bytes = b"", headers: dict[str, str] | None = None, *, length: bool = True):
    def handler(h: http.server.BaseHTTPRequestHandler) -> None:
        h.send_response(status)
        for k, v in (headers or {}).items():
            h.send_header(k, v)
        if length:
            h.send_header("Content-Length", str(len(body)))
        h.end_headers()
        h.wfile.write(body)
    return handler


def drip(n_bytes: int, every_s: float):
    """Réponse qui arrive goutte à goutte (un octet toutes les ``every_s`` secondes)."""
    def handler(h: http.server.BaseHTTPRequestHandler) -> None:
        h.send_response(200)
        h.send_header("Content-Length", str(n_bytes))
        h.end_headers()
        try:
            for _ in range(n_bytes):
                h.wfile.write(b"x")
                h.wfile.flush()
                time.sleep(every_s)
        except OSError:  # le client a coupé
            pass
    return handler


def silent(delay_s: float):
    """Réponse qui ne commence qu'après ``delay_s`` secondes."""
    def handler(h: http.server.BaseHTTPRequestHandler) -> None:
        time.sleep(delay_s)
        try:
            reply(200, b"tard")(h)
        except OSError:
            pass
    return handler


@pytest.fixture()
def server():
    servers: list[LocalServer] = []

    def make(routes: dict[str, Any], context: ssl.SSLContext | None = None) -> LocalServer:
        s = LocalServer(routes, context)
        servers.append(s)
        return s

    yield make
    for s in servers:
        s.close()


def local_client(*servers: LocalServer, **policy: Any) -> net.ClientHttp:
    """Client limité aux serveurs locaux donnés (boucle locale permise pour l'essai), sans mandataire."""
    import requests

    hosts = frozenset(f"127.0.0.1:{s.port}" for s in servers)
    pol = net.Politique(hotes=hosts, schemas=frozenset({"http", "https"}), adresses_locales=True, **policy)
    sess = requests.Session()
    sess.trust_env = False
    return net.ClientHttp(pol, session=sess)


# ---------------------------------------------------------------------------
# Liste blanche et politique
# ---------------------------------------------------------------------------


def test_default_whitelist_is_brvm_only_and_optional_sources_need_explicit_activation():
    pol = net.politique_par_defaut()
    assert pol.refus("https://www.brvm.org/fr/cours-actions/0") is None and pol.refus("https://brvm.org/") is None
    for url in ("https://evil.example/", "http://www.brvm.org/", "https://www.brvm.org:8443/", "https://user@www.brvm.org/",
                "https://www.brvm.org.evil.example/", "https://127.0.0.1/", "ftp://www.brvm.org/", "https:///x",
                "https://www.sikafinance.com/marches"):
        assert pol.refus(url), url
    with pytest.raises(net.HoteNonAutorise):
        pol.controler("https://evil.example/")
    with_sika = net.politique_par_defaut(sources=["sikafinance"])
    assert with_sika.refus("https://www.sikafinance.com/marches") is None
    assert with_sika.refus("https://www.richbourse.com/") is not None  # seule la source activée
    assert net.politique_par_defaut(sources=True).refus("https://www.financialafrik.com/x") is None
    with pytest.raises(ValueError):
        net.politique_par_defaut(sources=["inconnue"])
    with pytest.raises(net.RedirectionRefusee, match="https vers http"):
        pol.controler("http://www.brvm.org/x", depuis="https://www.brvm.org/y")
    assert erreurs.code_retour(net.HoteNonAutorise("x")) == 5 and erreurs.code_retour(net.DelaiDepasse("x")) == 5


@pytest.mark.parametrize("ip,bad", [("127.0.0.1", True), ("10.1.2.3", True), ("192.168.1.1", True), ("172.16.0.1", True),
                                    ("169.254.169.254", True), ("100.64.0.1", True), ("0.0.0.0", True), ("::1", True),
                                    ("fe80::1", True), ("fc00::1", True), ("::ffff:127.0.0.1", True), ("224.0.0.1", True),
                                    ("196.200.80.10", False), ("2001:4860:4860::8888", False)])
def test_forbidden_addresses(ip, bad):
    assert net.adresse_interdite(ip) is bad


def test_private_address_after_dns_resolution_is_refused_before_any_request():
    import requests

    class NoNetwork(requests.Session):
        def get(self, *a: Any, **k: Any) -> Any:
            raise AssertionError("aucune requête ne doit partir")

    sess = NoNetwork()
    sess.trust_env = False  # pas de mandataire : le nom est résolu ici
    for answer in ("10.0.0.7", "127.0.0.1", "169.254.169.254"):
        def resolver(host, port, *a, _ip=answer):
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (_ip, port))]

        cli = net.ClientHttp(session=sess, resolveur=resolver)
        with pytest.raises(net.AdresseInterdite, match="adresse interdite"):
            cli.get("https://www.brvm.org/fr/cours-actions/0")


def test_loopback_server_is_refused_without_explicit_permission(server):
    srv = server({"/ok": reply(200, b"ok")})
    import requests

    sess = requests.Session()
    sess.trust_env = False
    pol = net.Politique(hotes=frozenset({f"localhost:{srv.port}"}), schemas=frozenset({"http"}))
    with pytest.raises(net.AdresseInterdite):
        net.ClientHttp(pol, session=sess).get(f"http://localhost:{srv.port}/ok")
    assert srv.hits == []


def test_session_trusts_environment_only_outside_embedded_mode(monkeypatch):
    monkeypatch.delenv("BRVM_ALPHA_EMBARQUE", raising=False)
    monkeypatch.delenv(net.ENV_PROXY, raising=False)
    assert net.creer_session().trust_env is True  # développement : mandataire de l'environnement conservé
    env = {"BRVM_ALPHA_EMBARQUE": "1"}
    s = net.creer_session(environ=env)
    assert s.trust_env is False and not s.proxies
    s = net.creer_session(environ={"BRVM_ALPHA_EMBARQUE": "1", net.ENV_PROXY: "http://mandataire.local:3128"})
    assert s.trust_env is False and s.proxies == {"http": "http://mandataire.local:3128",
                                                  "https": "http://mandataire.local:3128"}


# ---------------------------------------------------------------------------
# Serveurs locaux : redirections, taille, lenteur
# ---------------------------------------------------------------------------


def test_redirect_to_another_host_is_refused_on_every_hop(server):
    other = server({"/ok": reply(200, b"ailleurs")})
    srv = server({"/vers-ailleurs": reply(302, b"", {"Location": f"http://localhost:{other.port}/ok"}),
                  "/vers-ici": reply(302, b"", {"Location": "/ok"}), "/ok": reply(200, b"ici"),
                  "/boucle": reply(302, b"", {"Location": "/boucle"})})
    cli = local_client(srv)
    res = cli.get(f"{srv.base}/vers-ici", suivre=3)
    assert res.status_code == 200 and res.content == b"ici"
    with pytest.raises(net.RedirectionRefusee, match="liste blanche"):
        cli.get(f"{srv.base}/vers-ailleurs", suivre=3)
    assert other.hits == []  # le second hôte n'a reçu aucune requête
    with pytest.raises(net.TropDeRedirections):
        cli.get(f"{srv.base}/boucle", suivre=3)
    assert srv.hits.count("/boucle") == 4
    assert cli.get(f"{srv.base}/vers-ici").status_code == 302  # suivre=0 : la redirection est rendue telle quelle


@pytest.fixture(scope="module")
def tls_context(tmp_path_factory):
    if not shutil.which("openssl"):
        pytest.skip("openssl absent : certificat d'essai impossible")
    d = tmp_path_factory.mktemp("tls")
    cert, key = d / "cert.pem", d / "key.pem"
    r = subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", str(key), "-out", str(cert),
                        "-days", "1", "-subj", "/CN=127.0.0.1", "-addext", "subjectAltName=IP:127.0.0.1"],
                       capture_output=True)
    if r.returncode != 0:
        pytest.skip("openssl ne sait pas fabriquer le certificat d'essai")
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(cert, key)
    return ctx, cert


def test_https_to_http_redirect_is_refused(server, tls_context):
    ctx, cert = tls_context
    plain = server({"/ok": reply(200, b"en clair")})
    secure = server({"/descente": reply(302, b"", {"Location": f"http://127.0.0.1:{plain.port}/ok"}),
                     "/ok": reply(200, b"chiffre")}, context=ctx)
    cli = local_client(secure, plain)
    cli._session.verify = str(cert)
    assert cli.get(f"{secure.base}/ok").content == b"chiffre"  # le serveur https d'essai répond
    with pytest.raises(net.RedirectionRefusee, match="https vers http"):
        cli.get(f"{secure.base}/descente", suivre=3)
    assert plain.hits == []
    # Même règle dans la session polie (redirections suivies à la main).
    with pytest.raises(rs.PolicyRefused, match="https vers http"):
        sess = rs.PoliteSession(transport=lambda u, h, t: _resp(302, b"", {"Location": "http://www.brvm.org/x"}, u),
                                clock=time.monotonic, sleep=lambda s: None, now=lambda: NOW, delay_s=0.0,
                                cache_dir=cert.parent / "cache", log_path=cert.parent / "log.jsonl")
        sess._robots["https://www.brvm.org"] = None
        sess.get("https://www.brvm.org/y")


def test_size_cap_announced_streamed_and_compressed(server):
    big = b"a" * 5000
    bomb = gzip.compress(b"\0" * 2_000_000)
    srv = server({"/annonce": reply(200, big), "/flux": reply(200, big, length=False),
                  "/bombe": reply(200, bomb, {"Content-Encoding": "gzip"}),
                  "/petit": reply(200, gzip.compress(b"petit"), {"Content-Encoding": "gzip"}),
                  "/inconnu": reply(200, b"x", {"Content-Encoding": "br"})})
    cli = local_client(srv, plafonds={"page": 1000, "pdf": 4000})
    with pytest.raises(net.ReponseTropGrosse, match="annoncés"):
        cli.get(f"{srv.base}/annonce")
    with pytest.raises(net.ReponseTropGrosse, match="lecture arrêtée"):
        cli.get(f"{srv.base}/flux")
    assert len(bomb) < 1000 * 3  # la bombe est petite une fois compressée…
    with pytest.raises(net.ReponseTropGrosse, match="décompressée"):
        cli.get(f"{srv.base}/bombe", nature="pdf")  # … et arrêtée dès le plafond franchi
    assert cli.get(f"{srv.base}/petit").content == b"petit"
    with pytest.raises(net.EncodageRefuse):
        cli.get(f"{srv.base}/inconnu")


def test_slow_responses_hit_the_total_and_per_operation_deadlines(server):
    srv = server({"/goutte": drip(200, 0.05), "/muet": silent(3.0)})
    cli = local_client(srv, delais={"page": 1.0}, delai_lecture=5.0)
    t0 = time.monotonic()
    with pytest.raises(net.DelaiDepasse, match="délai total"):
        cli.get(f"{srv.base}/goutte")  # 10 s de goutte-à-goutte, délai total d'une seconde
    assert time.monotonic() - t0 < 4.0
    cli2 = local_client(srv, delais={"page": 10.0}, delai_lecture=0.5)
    t0 = time.monotonic()
    with pytest.raises(net.DelaiDepasse):
        cli2.get(f"{srv.base}/muet")  # rien pendant 3 s : délai par opération de 0,5 s
    assert time.monotonic() - t0 < 2.5


# ---------------------------------------------------------------------------
# Session polie : MemoryError, tailles, robots.txt, état partagé
# ---------------------------------------------------------------------------


class _R:
    def __init__(self, status: int, content: bytes, headers: dict[str, str] | None, url: str) -> None:
        self.status_code, self.content, self.headers, self.url = status, content, headers or {}, url


def _resp(status: int, content: bytes = b"", headers: dict[str, str] | None = None, url: str = "") -> _R:
    return _R(status, content, headers, url)


def polite(tmp_path: Path, transport: Any, **kw: Any) -> rs.PoliteSession:
    kw.setdefault("delay_s", 10.0)
    return rs.PoliteSession(transport=transport, clock=_Clock(), sleep=lambda s: None, now=lambda: NOW,
                            cache_dir=tmp_path / "cache", log_path=tmp_path / "fetch_log.jsonl", **kw)


class _Clock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


def test_memory_error_is_never_a_network_error(tmp_path):
    calls = []

    def transport(url, headers, timeout):
        calls.append(url)
        if url.endswith("robots.txt"):
            return _resp(404, b"", None, url)
        raise MemoryError()

    sess = polite(tmp_path, transport)
    with pytest.raises(MemoryError):
        sess.get("https://www.brvm.org/fr/cours-actions/0")
    assert calls.count("https://www.brvm.org/fr/cours-actions/0") == 1  # aucun nouvel essai
    assert erreurs.code_retour(MemoryError()) == 6


def test_oversized_response_is_refused_without_retry(tmp_path):
    calls = []

    def transport(url, headers, timeout):
        calls.append(url)
        if url.endswith("robots.txt"):
            return _resp(404, b"", None, url)
        return _resp(200, b"x" * (net.PLAFONDS["page"] + 1), {"Content-Type": "text/html"}, url)

    sess = polite(tmp_path, transport)
    with pytest.raises(rs.PolicyRefused, match="plafond"):
        sess.get("https://www.brvm.org/fr/emetteurs/type-annonces/communiques")
    assert len(calls) == 2 and not sess.stopped  # une seule requête vers la page ; la session continue


@pytest.mark.parametrize("robots", [
    _resp(302, b"", {"Location": "https://evil.example/robots.txt"}),  # redirection hors liste blanche
    _resp(302, b"", {"Location": "http://www.brvm.org/robots.txt"}),  # https vers http
    _resp(200, b"<!DOCTYPE html><html><body>maintenance</body></html>", {"Content-Type": "text/html"}),  # illisible
    _resp(200, b"\x00\x01\x02binaire", {}),
])
def test_robots_redirected_or_unreadable_means_everything_forbidden(tmp_path, robots):
    calls = []

    def transport(url, headers, timeout):
        calls.append(url)
        if url == "https://www.brvm.org/robots.txt":
            return robots
        return _resp(200, b"<html>page</html>", {"Content-Type": "text/html"}, url)

    sess = polite(tmp_path, transport)
    with pytest.raises(rs.RobotsDisallowed):
        sess.get("https://www.brvm.org/fr/cours-actions/0")
    assert "https://www.brvm.org/fr/cours-actions/0" not in calls
    assert not any("evil.example" in u for u in calls) and not any(u.startswith("http://") for u in calls)


def test_polite_fetcher_robots_redirect_or_html_stops_the_download():
    from brvm_alpha.data import boc_download as bd

    class Http:
        def __init__(self, robots):
            self.robots, self.calls = robots, []

        def get(self, url, **kw):
            self.calls.append(url)
            return self.robots if url.endswith("robots.txt") else _resp(404, b"", None, url)

    for robots in (_resp(301, b"", {"Location": "/ailleurs"}), _resp(200, b"<html>maintenance</html>")):
        http_ = Http(robots)
        f = bd.PoliteFetcher(http_, sleep=lambda s: None, clock=_Clock())
        with pytest.raises(bd.DownloadStopped, match="robots.txt") as exc:
            f(bd.BASE_URL.format(date="20261118", suffix="_2"))
        assert exc.value.raison == "robots" and http_.calls == [bd.ROBOTS_URL]


def _write_state(cache: Path, entry: dict[str, Any]) -> None:
    cache.mkdir(parents=True, exist_ok=True)
    (cache / rs.POLITENESS_STATE).write_text(json.dumps({"hosts": {"www.brvm.org": entry}}), encoding="utf-8")


@pytest.mark.parametrize("entry", [
    # horloge recalée : réservation faite « dans le futur » (une heure après maintenant)
    {"last": (NOW + dt.timedelta(hours=1)).isoformat(), "session": "autre",
     "reserved_at": (NOW + dt.timedelta(minutes=59)).isoformat()},
    # ancien format sans date de réservation, dernière requête une heure dans le futur
    {"last": (NOW + dt.timedelta(hours=1)).isoformat(), "session": "autre"},
    # date absurde (année 2099)
    {"last": "2099-01-01T00:00:00+00:00", "session": "autre"},
])
def test_last_request_in_the_future_is_ignored_and_wait_is_capped(tmp_path, entry):
    _write_state(tmp_path / "cache", entry)
    sleeps: list[float] = []

    def transport(url, headers, timeout):
        return _resp(404 if url.endswith("robots.txt") else 200, b"<html>ok</html>", {"Content-Type": "text/html"}, url)

    sess = rs.PoliteSession(transport=transport, clock=_Clock(), sleep=sleeps.append, now=lambda: NOW, delay_s=10.0,
                            cache_dir=tmp_path / "cache", log_path=tmp_path / "log.jsonl")
    sess.get("https://www.brvm.org/fr/cours-actions/0")
    assert sleeps and max(sleeps) <= 2 * 10.0 + 1e-9 and max(sleeps) == pytest.approx(10.0)


def test_chained_reservations_of_other_sessions_are_still_honoured(tmp_path):
    # Deux sessions déjà en file (réservations faites maintenant, la dernière à +10 s) : la troisième part à +20 s.
    _write_state(tmp_path / "cache", {"last": (NOW + dt.timedelta(seconds=10)).isoformat(), "session": "autre",
                                      "reserved_at": NOW.isoformat()})
    sleeps: list[float] = []
    sess = rs.PoliteSession(transport=lambda u, h, t: _resp(404, b"", None, u), clock=_Clock(), sleep=sleeps.append,
                            now=lambda: NOW, delay_s=10.0, cache_dir=tmp_path / "cache", log_path=tmp_path / "l.jsonl")
    sess._robots["https://www.brvm.org"] = None
    sess.get("https://www.brvm.org/fr/x")
    assert sleeps == [pytest.approx(20.0)]


_HOLD_STATE = r"""
import sys, time
from brvm_alpha.notes import research as rs
with rs._state_locked(sys.argv[1]):
    print("PRET", flush=True)
    time.sleep(float(sys.argv[2]))
"""


def _holder(code: str, *args: str) -> subprocess.Popen:
    p = subprocess.Popen([sys.executable, "-c", code, *args], cwd=str(ROOT), stdout=subprocess.PIPE, text=True,
                         env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    assert p.stdout is not None and p.stdout.readline().strip() == "PRET"
    return p


def test_politeness_state_lock_between_two_processes_and_released_at_death(tmp_path):
    cache = tmp_path / "cache"
    p = _holder(_HOLD_STATE, str(cache), "30")
    try:
        t0 = time.monotonic()
        with pytest.raises(erreurs.VerrouOccupe, match="état de politesse"):
            with rs._state_locked(cache, timeout_s=0.3):
                pass
        assert time.monotonic() - t0 < 3.0
        assert erreurs.code_retour(erreurs.VerrouOccupe("x")) == 4
        p.kill()  # mort du détenteur : le système rend le verrou, aucun verrou « périmé » à deviner
        p.wait(timeout=10)
        with rs._state_locked(cache, timeout_s=2.0):
            pass
    finally:
        if p.poll() is None:
            p.kill()


def test_blocked_403_is_kept_when_the_state_lock_is_contended(tmp_path):
    cache = tmp_path / "cache"
    p = _holder(_HOLD_STATE, str(cache), "1.5")
    try:
        sess = polite(tmp_path, lambda u, h, t: _resp(403, b"", None, u))
        sess._robots["https://www.brvm.org"] = None
        sess._wait_turn = lambda url: None  # le créneau n'est pas l'objet de l'essai
        sess._record_done = lambda host: None
        with pytest.raises(rs.AccessBlocked):
            sess._network_get("https://www.brvm.org/fr/x", {})
        assert rs.blocked_hosts(cache).get("www.brvm.org", {}).get("status") == 403  # attendu, pas perdu
    finally:
        p.kill()
        p.wait(timeout=10)


# ---------------------------------------------------------------------------
# Recherche : écriture au fil de l'eau, bilan structuré, cache des BOC
# ---------------------------------------------------------------------------


class _Store:
    """Journal minimal : enregistre l'ordre des écritures."""

    def __init__(self, root: Path, events: list[str]) -> None:
        self.root, self.events, self.notes, self.updates = root, events, {}, []

    def add(self, note: Any) -> str:
        self.events.append(f"add:{note.note_id[:8]}")
        self.notes[note.note_id] = note
        return note.note_id

    def get(self, note_id: str) -> Any:
        if note_id not in self.notes:
            raise KeyError(note_id)
        return self.notes[note_id]

    def update(self, note_id: str, **changes: Any) -> Any:
        changes.pop("now", None)
        changes.pop("reanalyze", None)
        self.updates.append((note_id, changes))
        self.notes[note_id] = self.notes[note_id].copy(**changes, version=self.notes[note_id].version + 1)
        return self.notes[note_id]


def _item(list_key: str, title: str, url: str, doc_date: dt.date, **extra: Any) -> dict[str, Any]:
    return {"list_type": list_key, "source": "brvm_list", "title": title, "doc_url": url, "page_url": url,
            "doc_date": doc_date.isoformat(), "symbol": "SNTS", "issuer": "SONATEL", "country": "SN",
            "extra": dict(extra), "seen_at": NOW.isoformat()}


class _Sess:
    def __init__(self, max_requests: int = 10) -> None:
        self.n_requests, self.max_requests, self.stopped, self.stop_kind, self.blocked = 0, max_requests, None, None, None
        self.offline, self.cache_dir = False, Path("/nonexistent")

    @property
    def remaining(self) -> int:
        return max(0, self.max_requests - self.n_requests)


def test_research_writes_each_note_as_soon_as_its_list_is_collected(tmp_path, monkeypatch):
    events: list[str] = []
    store = _Store(tmp_path, events)
    pdf = "https://www.brvm.org/sites/default/files/20261105_-_avis_paiement_dividende_-_snts.pdf"
    items = {
        "dividendes": [_item("dividendes", "SONATEL : paiement de dividende", pdf, dt.date(2026, 11, 5))],
        "communiques": [_item("communiques", "SONATEL : communiqué résultats", "https://www.brvm.org/sites/default/files"
                              "/20261110_-_communique_-_snts.pdf", dt.date(2026, 11, 10))],
    }
    sess = _Sess()

    def collect(session, key, **kw):
        events.append(f"collecte:{key}")
        session.n_requests += 2
        return [dict(it, extra=dict(it["extra"])) for it in items.get(key, [])]

    monkeypatch.setattr(rs, "collect_list", collect)
    res = rs.run_research(store, lists=["dividendes", "communiques"], session=sess, issuer_reports=False, boc=False,
                          panel_dir=None, now=NOW, analyze=False)
    adds = [i for i, e in enumerate(events) if e.startswith("add:")]
    assert events[0] == "collecte:dividendes" and adds and adds[0] < events.index("collecte:communiques")
    bilan = res.report.to_dict()
    assert bilan["notes_ajoutees"] == [n.note_id for n in res] and len(bilan["notes_ajoutees"]) == 2
    assert bilan["requetes"] == 4 and bilan["quota"] == 10 and bilan["quota_restant"] == 6
    assert bilan["arret"] is False and bilan["raison_arret"] is None and bilan["blocage"] is None
    json.dumps(bilan)  # sérialisable


def test_research_report_gives_the_403_block_and_keeps_notes_written_before(tmp_path, monkeypatch):
    events: list[str] = []
    store = _Store(tmp_path, events)
    sess = _Sess()

    def collect(session, key, **kw):
        if key == "dividendes":
            session.n_requests += 1
            return [_item("dividendes", "SONATEL : paiement de dividende",
                          "https://www.brvm.org/sites/default/files/20261105_-_avis_-_snts.pdf", dt.date(2026, 11, 5))]
        session.n_requests += 1
        session.stopped, session.stop_kind = "HTTP 403 sur https://www.brvm.org/x", "bloque"
        session.blocked = {"host": "www.brvm.org", "status": 403, "url": "https://www.brvm.org/x", "since": "t"}
        return []

    monkeypatch.setattr(rs, "collect_list", collect)
    res = rs.run_research(store, lists=["dividendes", "communiques", "avis"], session=sess, issuer_reports=False,
                          boc=False, panel_dir=None, now=NOW, analyze=False)
    bilan = res.report.to_dict()
    assert len(store.notes) == 1 and bilan["notes_ajoutees"] == list(store.notes)
    assert bilan["arret"] is True and bilan["raison_arret"] == "bloque" and bilan["blocage"]["status"] == 403


def test_research_rewrites_a_written_note_when_a_later_source_gives_an_earlier_publication(tmp_path, monkeypatch):
    events: list[str] = []
    store = _Store(tmp_path, events)
    pdf = "https://www.brvm.org/sites/default/files/20261105_-_avis_paiement_dividende_-_snts.pdf"
    late = _item("dividendes", "SONATEL : paiement de dividende", pdf, dt.date(2026, 11, 5))
    early = dict(_item("avis", "SONATEL : paiement de dividende", pdf, dt.date(2026, 11, 5)),
                 published_at="2026-11-05T08:00:00+00:00", published_precision="datetime")
    sess = _Sess()
    monkeypatch.setattr(rs, "collect_list", lambda session, key, **kw: [dict(late)] if key == "dividendes"
                        else [dict(early)] if key == "avis" else [])
    res = rs.run_research(store, lists=["dividendes", "avis"], session=sess, issuer_reports=False, boc=False,
                          panel_dir=None, now=NOW, analyze=False)
    assert len(res) == 1 and len(store.notes) == 1 and res.report.n_duplicates == 1
    kept = next(iter(store.notes.values()))
    # Écrite dès la première liste, puis récrite (nouvelle version) quand la liste des avis donne l'heure exacte.
    assert res.report.updated_ids == [kept.note_id] and res.report.added_ids == [kept.note_id]
    assert store.updates[0][1]["published_at"] == dt.datetime(2026, 11, 5, 8, 0, tzinfo=UTC)
    assert kept.version == 2 and res[0].version == 2 and events.count(f"add:{kept.note_id[:8]}") == 1


def test_research_clears_the_boc_text_cache(tmp_path, monkeypatch):
    assert rs._read_boc.cache_info().maxsize == rs.BOC_TEXT_CACHE_SIZE == 128
    rs._read_boc.cache_clear()
    boc = ROOT / "tests" / "fixtures" / "notes" / "boc"
    monkeypatch.setattr(rs, "collect_list", lambda *a, **k: [])
    rs.run_research(_Store(tmp_path, []), lists=[], session=_Sess(), issuer_reports=False, boc=True, boc_dir=boc,
                    panel_dir=None, now=NOW, analyze=False, dry_run=True)
    assert rs._read_boc.cache_info().currsize == 0


def test_fetch_url_note_refuses_hosts_outside_the_whitelist_before_any_request(tmp_path):
    calls = []
    sess = polite(tmp_path, lambda u, h, t: calls.append(u) or _resp(200, b"<html><h1>x</h1></html>", None, u))
    with pytest.raises(rs.PolicyRefused, match="liste blanche"):
        rs.fetch_url_note("https://journal.example/article", _Store(tmp_path, []), session=sess)
    assert calls == []
    assert erreurs.code_retour(rs.PolicyRefused("x")) == 5 and erreurs.code_retour(rs.SourceDisabled("x")) == 5
    assert erreurs.code_retour(rs.QuotaExceeded("x")) == 1


# ---------------------------------------------------------------------------
# Cours du jour : même session polie
# ---------------------------------------------------------------------------


def test_fetch_live_goes_through_the_polite_session_and_its_cache(tmp_path):
    from brvm_alpha.data import live

    page = (ROOT / "tests" / "fixtures" / "brvm_cours_actions.html").read_bytes()
    calls = []

    def transport(url, headers, timeout):
        calls.append(url)
        if url.endswith("robots.txt"):
            return _resp(200, b"User-agent: *\nCrawl-delay: 10\n", {"Content-Type": "text/plain"}, url)
        return _resp(200, page, {"Content-Type": "text/html; charset=utf-8"}, url)

    sess = polite(tmp_path, transport, max_requests=3)
    snap = live.fetch_live(session=sess)
    assert calls == ["https://www.brvm.org/robots.txt", live.LIVE_URL] and len(snap.quotes) > 10
    live.fetch_live(session=sess)  # moins de 60 s : cache, aucune requête
    assert len(calls) == 2
    bad = polite(tmp_path / "b", lambda u, h, t: _resp(200, page, None, u))
    with pytest.raises(rs.PolicyRefused):
        bad.get("https://evil.example/fr/cours-actions/0")
    # page sans <tbody> : les lignes du tableau sont lues quand même
    html = ("<table><tr><th>Symbole</th><th>Nom</th></tr><tr><td>SNTS</td><td>SONATEL</td><td>1 000</td><td>20 000</td>"
            "<td>20 100</td><td>20 200</td><td>1,00 %</td></tr></table>")
    assert list(live.parse_live_html(html).quotes["symbol"]) == ["SNTS"]
