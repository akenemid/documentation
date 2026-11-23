"""Interface derrière un relais authentifié : préfixe d'adresse, origine du relais, cadre, ``/etat.json``.

Hors ligne : serveur local sur un port libre, journal temporaire, calculs lourds remplacés par les
doublures de ``test_ui``. Aucune requête vers l'extérieur, aucun calcul sur S1, ``data/notes`` jamais
touché. Le « relais de référence » de ce fichier suit le contrat de ``docs/DEPLOIEMENT.md`` : c'est
un modèle exécutable de ce que le contrôleur Odoo doit faire.
Performance passée ≠ garantie. Aucun gain n'est garanti.
"""

from __future__ import annotations

import http.client
import json
import re
import threading
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlencode, urlsplit

import pandas as pd
import pytest

import ui_reference_pages as R
from test_ui import BOC_FIX, PAGES, FakeServices, call, token, wait_job

from brvm_alpha.notes.store import NoteStore
from brvm_alpha.ui import pages
from brvm_alpha.ui import server as S

PREFIX = "/rz_brvm_alpha/ui"
RELAY = "https://erp.exemple.com"

#: Empreintes SHA-256 des pages de référence (``tests/ui_reference_pages.py``), relevées sur le commit
#: 3683f3a, dernier commit **sans** préfixe d'adresse. Sans préfixe, les pages doivent sortir à
#: l'octet près comme avant. Après un changement voulu d'une page : ``python tests/ui_reference_pages.py``.
GOLDEN = {
    "tableau_de_bord": "bafea888e1b61fc76587bec6668e8ff3ccf3a0e10f20f883ccc5741e37baabcc",
    "tableau_de_bord_vide": "0ec3e942265bd10244666bdd2b5ba1c51e3ba7b9a2dbabda7ac3e8518da56edc",
    "notes": "e406bace4c7a5abb003b31f9ca1564ced990f574a320dd71a934d87b6810fd78",
    "notes_en_vigueur": "4519ed04ed494135889f92cdbe29a83e678380decacdbe7886633b4e211d427a",
    "tableau_de_bord_notes": "8480f029a7210d1011efc5c0d7dbd9ecf07d82bda894d087acec5f72032533c5",
    "fiche_note": "62ccc8bad34ead456aa14828b43079a6f96aec2831e2ddfe2a874c4e9c1054d8",
    "recherche": "59f83d1487440e08afab046714745a85322a194b915f8619c0c75d90f3555107",
    "indices": "0d7b725cc867121a4d708c2efcec1b5b376fb70ccf3fa46d9df6ab45eb3210b5",
    "dossier": "96eb02850658702221441af2d3f8c2f0b5d3e84d6702d887c25625561613a437",
    "dossier_erreur": "c78b184d47aaf53e5294cbc6d22988c1563a3f073493f0ddbb1b873531553594",
    "portefeuille": "1651a5345042f60849897aaa3f96aa7c69370566abec8360892a2b10be28aaf7",
    "portefeuille_en_cours": "81f61af90904c4f3ae3d349eb110e924c5dcd849dcca4ba8fedbb738da73504b",
    "expliquer": "115db9092e540f1f57514acecdc043e917a5fb85bfc50bc710025d436dc6a372",
    "validation": "36dfe69a982df7e7fc2231e2d05a41ca9da883aa3781c974bd02f9a6c7040890",
    "erreur_404": "e0c891cdc09c2e33be74d6eba0099a9aa90fb12d3659b31b5c53a6b8fef210f0",
}

#: Attributs HTML qui portent une adresse.
URL_ATTRS = frozenset({"href", "src", "action", "formaction", "poster", "data", "cite", "background", "manifest",
                       "ping", "srcset"})
#: Attributs de texte libre (une saisie peut y commencer par « / » sans être une adresse).
TEXT_ATTRS = frozenset({"value", "placeholder", "content", "title", "aria-label", "data-confirm", "alt"})


class Links(HTMLParser):
    """Relève les adresses internes d'un document : attributs d'adresse, formulaires, appels du script."""

    def __init__(self, document: str):
        super().__init__(convert_charrefs=True)
        self.urls: list[tuple[str, str, str]] = []
        self.forms: list[tuple[str, str]] = []
        self.stray: list[tuple[str, str, str]] = []
        self._in_script = False
        self.script = ""
        self.feed(document)

    def handle_starttag(self, tag, attrs):
        self._in_script = tag == "script"
        d = dict(attrs)
        if tag == "form":
            self.forms.append(((d.get("method") or "get").lower(), d.get("action") or ""))
        for name, value in attrs:
            if value is None or not value.startswith("/") or value.startswith("//"):
                continue
            if name in URL_ATTRS:
                self.urls.append((tag, name, value))
            elif name not in TEXT_ATTRS:
                self.stray.append((tag, name, value))

    def handle_endtag(self, tag):
        if tag == "script":
            self._in_script = False

    def handle_data(self, data):
        if self._in_script:
            self.script += data

    @property
    def script_paths(self) -> list[str]:
        """Chaînes du script qui ressemblent à un chemin interne (« '/api/…' »)."""
        return re.findall(r"""['"](/[A-Za-z_][^'"]*)['"]""", self.script)


def assert_all_prefixed(document: str, prefix: str = PREFIX) -> Links:
    links = Links(document)
    bad = [u for u in links.urls if not u[2].startswith(prefix + "/")]
    assert not bad, f"adresses sans préfixe : {bad[:5]}"
    assert not links.stray, f"adresse interne dans un attribut inattendu : {links.stray[:5]}"
    assert all(p.startswith(prefix + "/") for p in links.script_paths), links.script_paths
    return links


@pytest.fixture()
def serve(tmp_path, monkeypatch):
    """Fabrique de serveurs (doublures de ``test_ui``) : ``serve(prefix=…, relay_origins=…, …)``."""
    from brvm_alpha.notes import research as rs

    def no_network(*a, **k):
        raise AssertionError("aucune requête réseau dans les tests")

    monkeypatch.setattr(rs, "_requests_transport", no_network)
    started = []

    def make(name: str = "a", services=None, **kw):
        folder = tmp_path / name
        folder.mkdir(exist_ok=True)
        srv = S.make_server("127.0.0.1", 0, services=services or FakeServices(folder), **kw)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        started.append(srv)
        return srv

    yield make
    for srv in started:
        srv.shutdown()
        srv.shutdown_jobs()
        srv.server_close()


def post(srv, path, form, origin=None, site="same-origin", **kw):
    headers = {} if origin is None else {"Origin": origin, "Sec-Fetch-Site": site}
    return call(srv, "POST", path, {"_jeton": token(srv), **form}, headers=headers, **kw)


# ---------------------------------------------------------------------------
# Sans option : sortie inchangée
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(GOLDEN))
def test_without_prefix_each_reference_page_is_byte_identical_to_the_previous_release(name):
    import hashlib

    doc = R.reference_pages()[name]
    assert hashlib.sha256(doc.encode("utf-8")).hexdigest() == GOLDEN[name], (
        f"la page « {name} » a changé sans préfixe ; si le changement est voulu, relever les empreintes avec "
        "python tests/ui_reference_pages.py")


def test_reference_pages_cover_every_route_of_the_interface():
    assert set(R.reference_pages()) == set(GOLDEN)
    seen = set()
    for doc in R.reference_pages().values():
        links = Links(doc)
        seen |= {urlsplit(u).path for _, _, u in links.urls} | {urlsplit(p).path for p in links.script_paths}
    routes = (set(S.GET_ROUTES) | set(S.POST_ROUTES)) - {"/etat.json"}  # adresse de service, sans lien dans les pages
    assert routes <= seen, routes - seen


def test_page_context_and_layout_default_to_no_prefix():
    ctx = pages.PageContext(token="t", nonce="n")
    assert ctx.prefix == "" and pages.with_prefix("<a href=\"/notes\">", "") == "<a href=\"/notes\">"
    assert pages.body_script() is pages.BODY_JS and pages.body_script("") is pages.BODY_JS
    doc = "<p>texte</p>"
    assert pages.with_prefix(doc, "") is doc  # même objet : rien n'est recopié ni réécrit


def test_default_server_has_no_prefix_no_relay_origin_and_forbids_framing(serve):
    srv = serve()
    assert srv.prefix == "" and srv.relay_origins == frozenset() and srv.frame_same_origin is False
    status, h, body = call(srv, "GET", "/notes")
    assert status == 200 and 'action="/notes/ajouter"' in body and "fetch('/api/travail?id='" in body
    assert h["x-frame-options"] == "DENY" and "frame-ancestors 'none'" in h["content-security-policy"]
    # l'origine d'un relais n'est acceptée que si elle est déclarée : par défaut, refus
    assert post(srv, "/notes/ajouter", {"titre": "x", "cibles": "SNTS"}, origin=RELAY)[0] == 403
    assert len(NoteStore(srv.services.notes_root)) == 0
    status, h, _ = post(srv, "/notes/ajouter", {"titre": "x", "cibles": "SNTS"})
    assert status == 303 and h["location"].startswith("/notes/fiche?id=")


def test_server_pages_differ_from_default_only_by_the_prefix(serve):
    plain, prefixed = serve("a"), serve("b", prefix=PREFIX)

    def norm(srv, body):
        body = re.sub(r'nonce="[^"]+"', 'nonce="N"', body).replace(token(srv), "JETON")
        return re.sub(r"val(?=</dd>)", "val", body)

    for path in PAGES:
        s1, _, b1 = call(plain, "GET", path)
        s2, _, b2 = call(prefixed, "GET", PREFIX + path)
        assert (s1, s2) == (200, 200), path
        assert norm(prefixed, b2).replace(PREFIX + "/", "/") == norm(plain, b1), path
        assert b2.count(PREFIX + "/") >= 9  # navigation, marque, formulaire ou appel du script


# ---------------------------------------------------------------------------
# Préfixe : pages, liens, formulaires, script
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(GOLDEN))
def test_with_prefix_every_link_form_file_and_script_call_carries_it(name):
    plain, prefixed = R.reference_pages()[name], R.reference_pages(PREFIX)[name]
    links = assert_all_prefixed(prefixed)
    assert links.urls and f"fetch('{PREFIX}/api/travail?id='" in prefixed and "fetch('/api" not in prefixed
    # le préfixe est le seul ajout, et il n'apparaît que dans des adresses
    assert prefixed.replace(PREFIX + "/", "/") == plain
    assert prefixed.count(PREFIX) == len(links.urls) + len(links.script_paths)


def test_prefix_never_rewrites_text_typed_by_the_user():
    doc = R.reference_pages(PREFIX)["fiche_note"]
    # titre et texte de la note contiennent href="/piege", action="/piege", src="/piege" : échappés, intacts
    assert "href=&quot;/piege&quot;" in doc and "action=&quot;/piege&quot; src=&quot;/piege&quot;" in doc
    assert PREFIX + "/piege" not in doc
    form = R.reference_pages(PREFIX)["notes"]
    assert 'value="Titre &quot;gardé&quot;"' in form and PREFIX + "/piege" not in form
    md = R.reference_pages(PREFIX)["validation"]
    assert 'href="https://www.brvm.org/fr"' in md and "<code>href=&quot;/piege&quot;</code>" in md


@pytest.mark.parametrize("path", PAGES)
def test_pages_are_served_only_under_the_prefix(serve, path):
    srv = serve(prefix=PREFIX)
    status, _, body = call(srv, "GET", PREFIX + path)
    assert status == 200, body[:300]
    assert_all_prefixed(body)
    status, _, body = call(srv, "GET", path)  # même page sans le préfixe : introuvable
    assert status == 404 and "Page introuvable" in body
    assert_all_prefixed(body)  # la page d'erreur renvoie vers le tableau de bord sous préfixe


@pytest.mark.parametrize("path", ["/", "/notes", "/etat.json", "/api/travail?id=0123456789abcdef", PREFIX + "x/notes",
                                  PREFIX.upper() + "/notes", "/x" + PREFIX + "/notes", PREFIX + "/../notes",
                                  "/%72z_brvm_alpha/ui/notes", PREFIX + "//notes", PREFIX + "/inconnue"])
def test_any_path_outside_the_prefix_is_404(serve, path):
    srv = serve(prefix=PREFIX)
    assert call(srv, "GET", path)[0] == 404
    status, _, _ = post(srv, path.split("?")[0], {"titre": "x", "cibles": "SNTS"})
    assert status == 404
    assert len(NoteStore(srv.services.notes_root)) == 0


def test_prefix_root_with_or_without_trailing_slash_is_the_dashboard(serve):
    srv = serve(prefix=PREFIX)
    for path in (PREFIX, PREFIX + "/", PREFIX + "/?lance=1"):
        status, _, body = call(srv, "GET", path)
        assert status == 200 and "<h1>Tableau de bord</h1>" in body
    assert f'<a class="brand" href="{PREFIX}/">' in body
    assert call(srv, "HEAD", PREFIX + "/notes")[0] == 200


def test_forms_post_under_the_prefix_and_redirect_under_the_prefix(serve):
    srv = serve(prefix=PREFIX)
    locations = []

    def follow(status, headers):
        assert status == 303, status
        loc = headers["location"]
        u = urlsplit(loc)
        assert u.scheme == "" and u.netloc == "" and loc.startswith(PREFIX + "/"), loc  # jamais une adresse complète
        locations.append(loc)
        s, _, body = call(srv, "GET", loc.split("#")[0])
        assert s == 200, loc
        assert_all_prefixed(body)
        return body

    # note : ajout, doublon (lien « Ouvrir la note »), archivage
    note = {"cibles": "SNTS", "titre": "Sonatel : dividende", "texte": "Dividende net de 1 800 FCFA.", "avis": "haussier"}
    status, h, _ = post(srv, PREFIX + "/notes/ajouter", note)
    assert "Note enregistrée et analysée" in follow(status, h)
    nid = re.search(r"id=([0-9a-f]+)", h["location"]).group(1)
    status, _, body = post(srv, PREFIX + "/notes/ajouter", note)
    assert status == 409 and f'href="{PREFIX}/notes/fiche?id={nid}"' in body
    assert_all_prefixed(body)
    status, h, _ = post(srv, PREFIX + "/notes/archiver", {"id": nid, "motif": "essai"})
    assert "Note archivée" in follow(status, h)
    # recherche hors ligne
    status, h, _ = post(srv, PREFIX + "/recherche/lancer", {"mode": "hors_ligne", "max_requetes": "5", "confirmer": "oui"})
    follow(status, h)
    assert wait_job(srv, "recherche").status == "terminé"
    # rapport : régénération, cadre du tableau de bord, fichier servi sous préfixe
    status, h, _ = post(srv, PREFIX + "/rapport/regenerer", {"capital": "10M"})
    assert h["location"] == PREFIX + "/?lance=1"
    follow(status, h)
    assert wait_job(srv, "rapport").status == "terminé"
    body = call(srv, "GET", PREFIX + "/")[2]
    src = f"{PREFIX}/rapport/voir?nom=rapport_2026-11-20.html"
    assert f'loading="lazy" src="{src}"' in body and f'<a href="{src}">ouvrir en plein écran</a>' in body
    status, hh, report = call(srv, "GET", src)
    assert status == 200 and "rapport simulé" in report and "sandbox" in hh["content-security-policy"]
    assert call(srv, "GET", "/rapport/voir?nom=rapport_2026-11-20.html")[0] == 404
    # portefeuille : calcul, ancre, exports
    status, h, _ = post(srv, PREFIX + "/portefeuille/calculer", {"capital": "10M", "tirages": "1000"})
    assert re.fullmatch(re.escape(PREFIX) + r"/portefeuille\?travail=[0-9a-f]{16}#travail", h["location"])
    follow(status, h)
    job = wait_job(srv, "portefeuille")
    body = call(srv, "GET", h["location"].split("#")[0])[2]
    for fmt in ("md", "json"):
        link = f"{PREFIX}/portefeuille/resultat?travail={job.id}&amp;format={fmt}"
        assert f'href="{link}"' in body
        assert call(srv, "GET", link.replace("&amp;", "&"))[0] == 200
    # suivi des travaux par le script : même préfixe
    status, _, js = call(srv, "GET", f"{PREFIX}/api/travail?id={job.id}")
    assert status == 200 and json.loads(js)["termine"] is True
    assert call(srv, "GET", f"/api/travail?id={job.id}")[0] == 404
    assert len(locations) == 5


def test_every_form_of_every_page_targets_a_prefixed_route(serve):
    srv = serve(prefix=PREFIX)
    _, h, _ = post(srv, PREFIX + "/notes/ajouter", {"cibles": "SNTS", "titre": "Note pour la fiche"})
    forms: set[tuple[str, str]] = set()
    for path in [*PAGES, h["location"][len(PREFIX):]]:
        forms |= set(Links(call(srv, "GET", PREFIX + path)[2]).forms)
    assert {a for m, a in forms if m == "post"} == {PREFIX + r for r in S.POST_ROUTES}
    assert {a for m, a in forms if m == "get"} == {PREFIX + r for r in ("/notes", "/indices", "/expliquer")}


def test_stale_token_form_is_shown_again_under_the_prefix(serve):
    srv = serve(prefix=PREFIX)
    status, _, body = call(srv, "POST", PREFIX + "/notes/ajouter", {"_jeton": "perime", "titre": "Saisie gardée"})
    assert status == 403 and 'value="Saisie gardée"' in body and f'action="{PREFIX}/notes/ajouter"' in body
    assert len(NoteStore(srv.services.notes_root)) == 0


def test_crawl_every_internal_link_answers_under_the_prefix(serve):
    """Aucun lien mort sous préfixe : chaque adresse interne trouvée dans les pages répond (jamais 404)."""
    srv = serve(prefix=PREFIX)
    post(srv, PREFIX + "/notes/ajouter", {"cibles": "SNTS", "titre": "Note du parcours"})
    post(srv, PREFIX + "/rapport/regenerer", {"capital": "10M"})
    wait_job(srv, "rapport")
    todo, seen = [PREFIX + p for p in PAGES], set()
    while todo:
        url = todo.pop()
        if url in seen:
            continue
        seen.add(url)
        status, h, body = call(srv, "GET", url)
        # 400 : saisie refusée ; 404 « Note introuvable » : note fictive des doublures. Jamais « Page introuvable ».
        assert status in (200, 400, 404) and "Page introuvable" not in body, (url, status)
        assert status != 404 or "Note introuvable" in body, (url, status)
        if h["content-type"].startswith("text/html") and "sandbox" not in h["content-security-policy"]:
            for _, attr, target in assert_all_prefixed(body).urls:
                if attr in ("href", "src"):
                    todo.append(target.split("#")[0])
    assert len(seen) >= 15 and any("/rapport/voir" in u for u in seen) and any("/notes/fiche" in u for u in seen)
    assert any("/indices/dossier" in u for u in seen) and any("/expliquer?symbole=" in u for u in seen)


@pytest.mark.parametrize("bad", ["rz", "/rz/", "/", "//rz", "/rz//ui", "/rz/../ui", "/rz/./ui", "/rz?x=1", "/rz#a",
                                 "/rz ui", "/rz<script>", "/é", "/rz\\ui", "/rz'ui", "/" + "a" * 201, "https://x/rz"])
def test_malformed_prefix_is_refused_before_the_port_opens(bad):
    from brvm_alpha import cli

    with pytest.raises(ValueError, match="préfixe d'adresse invalide"):
        cli.parse_prefix(bad)
    with pytest.raises(ValueError, match="préfixe d'adresse invalide"):
        S.make_server("127.0.0.1", 0, prefix=bad)


def test_well_formed_prefixes_are_kept_as_given():
    from brvm_alpha import cli

    for good in ("/rz_brvm_alpha/ui", "/a", "/a-b/c.d/e~f", "/Odoo/BRVM_1"):
        assert cli.parse_prefix(good) == good == cli.parse_prefix(f"  {good} ")
    assert cli.parse_prefix("") == "" == cli.parse_prefix(None) == cli.parse_prefix("  ")


# ---------------------------------------------------------------------------
# Relais : origine acceptée ou refusée, hôte, jeton
# ---------------------------------------------------------------------------


def test_relay_origin_is_accepted_for_forms_only_when_declared(serve):
    srv = serve(prefix=PREFIX, relay_origins=[RELAY])
    assert srv.relay_origins == frozenset({RELAY})
    form = {"cibles": "SNTS", "titre": "Depuis le relais"}
    status, h, _ = post(srv, PREFIX + "/notes/ajouter", form, origin=RELAY)
    assert status == 303 and h["location"].startswith(PREFIX + "/notes/fiche?id=")
    store = NoteStore(srv.services.notes_root)
    assert len(store) == 1
    refused = ["https://evil.exemple.com", "http://erp.exemple.com", "https://erp.exemple.com:8443",
               "https://erp.exemple.com.evil.test", "https://sous.erp.exemple.com", "https://erp.exemple.com@evil.test",
               "https://evil.test/https://erp.exemple.com", "erp.exemple.com", "ftp://erp.exemple.com", "*", ""]
    for origin in refused:
        status, _, _ = post(srv, PREFIX + "/notes/ajouter", {"cibles": "ORAC", "titre": f"Refus {origin}"}, origin=origin)
        assert status == 403, origin
    assert len(store) == 1
    # écritures équivalentes de la même origine : acceptées
    for i, origin in enumerate(("https://ERP.Exemple.com", "https://erp.exemple.com:443")):
        assert post(srv, PREFIX + "/notes/ajouter", {"cibles": "ORAC", "titre": f"Même origine {i}"}, origin=origin)[0] == 303
    # l'accès direct local reste possible (tunnel d'administration)
    local = f"http://127.0.0.1:{srv.port}"
    assert post(srv, PREFIX + "/notes/ajouter", {"cibles": "ORAC", "titre": "Local"}, origin=local)[0] == 303


def test_relay_origin_does_not_weaken_the_other_checks(serve):
    srv = serve(prefix=PREFIX, relay_origins=[RELAY])
    form = {"cibles": "SNTS", "titre": "x"}
    # Sec-Fetch-Site d'un autre site : refusé même avec la bonne origine et le bon jeton
    for site in ("cross-site", "same-site"):
        assert post(srv, PREFIX + "/notes/ajouter", form, origin=RELAY, site=site)[0] == 403
    # jeton absent ou faux : refusé même avec la bonne origine
    hdr = {"Origin": RELAY, "Sec-Fetch-Site": "same-origin"}
    assert call(srv, "POST", PREFIX + "/notes/archiver", {"id": "ab" * 20}, headers=hdr)[0] == 403
    assert call(srv, "POST", PREFIX + "/notes/archiver", {"id": "ab" * 20, "_jeton": "faux"}, headers=hdr)[0] == 403
    # « Origin: null » : accepté seulement si le navigateur atteste la même origine (règle inchangée)
    assert post(srv, PREFIX + "/notes/ajouter", form, origin="null", site="cross-site")[0] == 403
    assert call(srv, "POST", PREFIX + "/notes/ajouter", {"_jeton": token(srv), **form}, headers={"Origin": "null"})[0] == 403
    # l'en-tête Host reste celui de l'adresse locale : le nom public du relais est refusé
    for host in ("erp.exemple.com", "erp.exemple.com:443", f"erp.exemple.com:{srv.port}"):
        status, _, body = call(srv, "GET", PREFIX + "/", host=host)
        assert status == 400 and "Hôte refusé" in body
        assert post(srv, PREFIX + "/notes/ajouter", form, origin=RELAY, host=host)[0] == 400
    assert len(NoteStore(srv.services.notes_root)) == 0
    # corps : mêmes limites qu'avant (type, taille)
    big = b"_jeton=" + token(srv).encode() + b"&texte=" + b"a" * (S.MAX_BODY_BYTES + 10)
    assert call(srv, "POST", PREFIX + "/notes/ajouter", raw=big, headers=hdr)[0] == 413


@pytest.mark.parametrize("bad", ["erp.exemple.com", "https://", "https://erp.exemple.com/chemin", "https://*.exemple.com",
                                 "https://erp.exemple.com?x=1", "https://u:p@erp.exemple.com", "javascript:alert(1)",
                                 "null", "https://erp.exemple.com:99999", "https://erp exemple.com", ""])
def test_malformed_relay_origin_is_refused(bad):
    from brvm_alpha import cli

    with pytest.raises(ValueError, match="origine invalide"):
        cli.parse_origin(bad)
    with pytest.raises(ValueError, match="origine invalide"):
        S.make_server("127.0.0.1", 0, relay_origins=[bad])


def test_relay_origin_normalisation():
    from brvm_alpha import cli

    assert cli.parse_origin("https://ERP.Exemple.com:443/") == "https://erp.exemple.com"
    assert cli.parse_origin("http://preprod.local:8069") == "http://preprod.local:8069"
    assert cli.parse_origin("http://preprod.local:80") == "http://preprod.local"
    assert cli.parse_origin("https://[::1]:8443") == "https://[::1]:8443"
    assert cli.split_origins(" https://a.test, https://b.test\thttps://c.test ,, ") == [
        "https://a.test", "https://b.test", "https://c.test"]


# ---------------------------------------------------------------------------
# Cadre de même origine et en-têtes de sécurité
# ---------------------------------------------------------------------------


def test_same_origin_frame_is_an_explicit_option(serve):
    default, framed = serve("a", prefix=PREFIX), serve("b", prefix=PREFIX, frame_same_origin=True)
    _, h, _ = call(default, "GET", PREFIX + "/notes")
    assert h["x-frame-options"] == "DENY" and "frame-ancestors 'none'" in h["content-security-policy"]
    for path in ("/notes", "/etat.json", "/inconnue"):
        _, h, _ = call(framed, "GET", PREFIX + path)
        csp = h["content-security-policy"]
        assert h["x-frame-options"] == "SAMEORIGIN" and "frame-ancestors 'self'" in csp, path
        assert "frame-ancestors 'none'" not in csp and "*" not in csp and "ALLOW-FROM" not in h["x-frame-options"]
        # le reste de la politique ne change pas
        assert "default-src 'none'" in csp and "form-action 'self'" in csp and "base-uri 'none'" in csp
        assert "script-src 'nonce-" in csp and "'unsafe-inline'" not in csp
        assert h["referrer-policy"] == "same-origin" and h["cache-control"] == "no-store"
        assert h["x-content-type-options"] == "nosniff" and "set-cookie" not in h


def test_report_is_framed_by_the_same_origin_and_sandboxed_with_or_without_the_option(serve):
    for name, kw in (("a", {}), ("b", {"frame_same_origin": True})):
        srv = serve(name, prefix=PREFIX, **kw)
        post(srv, PREFIX + "/rapport/regenerer", {"capital": "10M"})
        wait_job(srv, "rapport")
        _, h, _ = call(srv, "GET", f"{PREFIX}/rapport/voir?nom=rapport_2026-11-20.html")
        csp = h["content-security-policy"]
        assert h["x-frame-options"] == "SAMEORIGIN" and "frame-ancestors 'self'" in csp
        # bac à sable sans « allow-same-origin » : le script du rapport n'a jamais l'origine du relais
        assert "sandbox allow-scripts" in csp and "allow-same-origin" not in csp and "form-action 'none'" in csp
        assert h["cache-control"] == "no-store"


# ---------------------------------------------------------------------------
# /etat.json
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def tiny_panel(tmp_path_factory):
    """Panel minuscule construit depuis sept extraits de BOC (aucun réseau, aucun calcul sur S1)."""
    from brvm_alpha.data import store

    out = tmp_path_factory.mktemp("panel_minuscule")
    store.build_panel(BOC_FIX, out, workers=1)
    return out


def test_state_json_is_read_only_and_follows_the_prefix(serve, tmp_path, tiny_panel):
    clock = lambda: pd.Timestamp("2026-10-30 12:00", tz="UTC")  # noqa: E731 - horloge fixe
    data = tmp_path / "donnees"
    (data / "sous").mkdir(parents=True)
    (data / "sous" / "fichier.bin").write_bytes(b"x" * 2048)
    reports = tmp_path / "rapports"
    reports.mkdir()
    (reports / "rapport_2026-10-29.html").write_text("<p>r</p>", encoding="utf-8")
    (reports / "brouillon.html").write_text("ignoré", encoding="utf-8")
    services = S.Services(notes_root=tmp_path / "notes", panel_dir=tiny_panel, reports_dir=reports, boc_dir=BOC_FIX,
                          clock=clock, data_dir=data)
    srv = serve(services=services, prefix=PREFIX)
    before = sorted(str(p) for p in tmp_path.rglob("*"))
    status, h, body = call(srv, "GET", PREFIX + "/etat.json")
    assert status == 200 and h["content-type"].startswith("application/json") and h["cache-control"] == "no-store"
    state = json.loads(body)
    assert list(state) == ["bandeau", "pret", "raison", "historique_complet", "version", "releve_le", "panel",
                           "bulletins", "site", "notes", "rapport", "donnees", "extracteur_pdf", "embarque"]
    # sept BOC des fixtures : panel lisible, historique incomplet depuis 2017, donc pas « prêt »
    assert state["bandeau"] == pages.BANNER and state["pret"] is False and state["releve_le"] == "2026-10-30T12:00:00Z"
    assert state["raison"].startswith("historique incomplet") and state["historique_complet"] is False
    assert state["panel"]["derniere_seance"] == "2026-10-29" and state["panel"]["seances_presentes"] == 7
    assert state["panel"]["seances_en_retard"] == 0 and state["panel"]["retard"] is None
    assert state["bulletins"]["en_cache"] == 7 and state["bulletins"]["dernier"] == "2026-10-29"
    # « update » comble l'historique depuis le 02/01/2017 : le 30/10/2026 (pas encore paru) et tous les jours sans
    # bulletin depuis 2017 (sept BOC seulement ici)
    assert state["bulletins"]["jours_a_telecharger"] == state["bulletins"]["jours_a_telecharger_depuis_2017"] > 2000
    assert state["site"] == {"bloque": False, "depuis": None, "code_http": None}
    assert state["notes"]["au_journal"] == 0 and state["notes"]["journal_present"] is False
    assert state["rapport"]["nom"] == "rapport_2026-10-29.html" and state["rapport"]["date"].endswith("Z")
    assert state["donnees"] == {"dossier": str(data), "taille_octets": 2048, "taille": "2 Ko"}
    assert re.fullmatch(r"[0-9a-f]{7}|inconnue|[A-Za-z0-9._-]{1,40}", state["version"])
    # lecture seule : rien n'est créé, et l'adresse n'existe que sous le préfixe, en GET
    assert sorted(str(p) for p in tmp_path.rglob("*")) == before
    assert call(srv, "GET", "/etat.json")[0] == 404
    assert call(srv, "POST", PREFIX + "/etat.json", {"_jeton": token(srv)})[0] == 404
    assert call(srv, "HEAD", PREFIX + "/etat.json")[0] == 200


def test_state_json_counts_notes_and_is_cached_for_a_few_seconds(serve, tmp_path, tiny_panel, monkeypatch):
    # Horloge réelle : la note saisie maintenant est connue du relevé (mode direct), donc en vigueur.
    services = S.Services(notes_root=tmp_path / "notes", panel_dir=tiny_panel, reports_dir=tmp_path / "rapports",
                          boc_dir=BOC_FIX, data_dir=tmp_path)
    srv = serve(services=services)
    first = json.loads(call(srv, "GET", "/etat.json")[2])
    assert first["pret"] is False and first["notes"]["au_journal"] == 0 and first["rapport"]["nom"] is None
    post(srv, "/notes/ajouter", {"cibles": "SNTS", "titre": "Sonatel : avis", "avis": "haussier", "conviction": "3"})
    assert json.loads(call(srv, "GET", "/etat.json")[2])["notes"]["au_journal"] == 0  # relevé gardé quelques secondes
    monkeypatch.setattr(S, "STATE_TTL_S", 0.0)
    again = json.loads(call(srv, "GET", "/etat.json")[2])
    assert again["notes"] == {"dossier": str(tmp_path / "notes"), "journal_present": True, "au_journal": 1,
                              "en_vigueur": 1}


def test_state_json_reports_not_ready_without_panel(serve):
    srv = serve()  # doublures : aucun panel sur le disque
    state = json.loads(call(srv, "GET", "/etat.json")[2])
    assert state["pret"] is False and state["panel"]["derniere_seance"] is None
    assert state["panel"]["seances_presentes"] == 0 and state["bandeau"] == pages.BANNER


# ---------------------------------------------------------------------------
# Relais de référence : le contrat de docs/DEPLOIEMENT.md, exécuté de bout en bout
# ---------------------------------------------------------------------------


class ReferenceRelay(ThreadingHTTPServer):
    """Relais minimal placé devant le moteur (modèle du contrôleur Odoo).

    Il relaie ``<préfixe>/…`` vers ``http://127.0.0.1:<port du moteur>`` en gardant le chemin complet,
    après avoir vérifié sa propre authentification (ici un témoin de session fixe).
    """

    daemon_threads = True

    def __init__(self, prefix: str):
        super().__init__(("127.0.0.1", 0), RelayHandler)
        self.prefix = prefix
        self.engine_port = 0
        self.port = int(self.server_address[1])
        self.sent: list[dict[str, str]] = []  # en-têtes envoyés au moteur, pour les contrôles


class RelayHandler(BaseHTTPRequestHandler):
    #: Seuls en-têtes de la requête du navigateur transmis au moteur.
    FORWARD = ("Origin", "Sec-Fetch-Site", "Content-Type")
    #: En-têtes de la réponse du moteur que le relais ne recopie pas (il pose les siens).
    DROP = frozenset({"connection", "keep-alive", "transfer-encoding", "content-length", "server", "date"})
    server: ReferenceRelay

    def log_message(self, format, *args):  # noqa: A002
        return

    def _relay(self):
        srv = self.server
        path = urlsplit(self.path).path
        if path != srv.prefix and not path.startswith(srv.prefix + "/"):
            self.send_error(404)
            return
        if "session=valide" not in (self.headers.get("Cookie") or ""):  # authentification du relais
            self.send_error(401)
            return
        headers = {k: self.headers[k] for k in self.FORWARD if self.headers.get(k)}  # ni Cookie, ni Host, ni Referer
        body = None
        if self.command == "POST":
            body = self.rfile.read(int(self.headers.get("Content-Length") or 0))  # corps transmis tel quel
        conn = http.client.HTTPConnection("127.0.0.1", srv.engine_port, timeout=60)
        conn.request(self.command, self.path, body=body, headers=headers)  # Host = 127.0.0.1:<port du moteur>
        srv.sent.append(headers)
        resp = conn.getresponse()  # aucune redirection suivie : le 303 repart tel quel au navigateur
        data = resp.read()
        self.send_response(resp.status)
        for k, v in resp.getheaders():
            if k.lower() not in self.DROP:
                self.send_header(k, v)  # Location, Content-Type, CSP, X-Frame-Options, Cache-Control… tels quels
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)
        conn.close()

    do_GET = do_POST = do_HEAD = _relay  # noqa: N815


def browser(relay, method, path, form=None, cookie="session=valide", origin=None, site="same-origin"):
    """Requête d'un navigateur vers l'adresse publique du relais."""
    conn = http.client.HTTPConnection("127.0.0.1", relay.port, timeout=60)
    headers = {"Cookie": cookie, "Referer": f"http://127.0.0.1:{relay.port}{PREFIX}/notes",
               "Authorization": "Basic c2VjcmV0"}
    data = None
    if form is not None:
        data = urlencode(form).encode("utf-8")
        headers |= {"Content-Type": "application/x-www-form-urlencoded", "Origin": origin, "Sec-Fetch-Site": site}
    conn.request(method, path, body=data, headers=headers)
    r = conn.getresponse()
    out = (r.status, {k.lower(): v for k, v in r.getheaders()}, r.read().decode("utf-8", "replace"))
    conn.close()
    return out


def test_reference_relay_end_to_end(serve):
    relay = ReferenceRelay(PREFIX)
    public = f"http://127.0.0.1:{relay.port}"  # origine que voit le navigateur
    engine = serve(prefix=PREFIX, relay_origins=[public], frame_same_origin=True)
    relay.engine_port = engine.port
    threading.Thread(target=relay.serve_forever, daemon=True).start()
    try:
        # sans session du relais : le moteur n'est même pas contacté
        assert browser(relay, "GET", PREFIX + "/notes", cookie="")[0] == 401 and relay.sent == []
        # hors du sous-chemin du relais : rien n'est relayé
        assert browser(relay, "GET", "/notes")[0] == 404 and relay.sent == []
        # page : en-têtes de sécurité du moteur intacts, liens sous préfixe
        status, h, body = browser(relay, "GET", PREFIX + "/notes")
        assert status == 200 and h["x-frame-options"] == "SAMEORIGIN" and h["cache-control"] == "no-store"
        assert "frame-ancestors 'self'" in h["content-security-policy"] and h["referrer-policy"] == "same-origin"
        assert_all_prefixed(body)
        jeton = re.search(r'name="_jeton" value="([^"]+)"', body).group(1)
        # formulaire : origine publique du relais, jeton du moteur dans le corps, redirection relative
        form = {"_jeton": jeton, "cibles": "SNTS", "titre": "Saisie à travers le relais", "avis": "haussier"}
        status, h, _ = browser(relay, "POST", PREFIX + "/notes/ajouter", form, origin=public)
        assert status == 303 and h["location"].startswith(PREFIX + "/notes/fiche?id=")
        status, _, body = browser(relay, "GET", h["location"])
        assert status == 200 and "Note enregistrée et analysée" in body and "Saisie à travers le relais" in body
        store = NoteStore(engine.services.notes_root)
        assert len(store) == 1
        # attaque d'un autre site à travers le relais : l'origine transmise telle quelle fait refuser l'envoi
        for origin, site in (("https://evil.test", "cross-site"), ("https://evil.test", "same-origin"), (public, "cross-site")):
            status, _, _ = browser(relay, "POST", PREFIX + "/notes/ajouter", form | {"titre": "Attaque"}, origin=origin,
                                   site=site)
            assert status == 403
        assert len(store) == 1
        # état du moteur à travers le relais
        status, _, js = browser(relay, "GET", PREFIX + "/etat.json")
        assert status == 200 and json.loads(js)["notes"]["au_journal"] in (0, 1)
        # le moteur n'a jamais reçu les témoins, l'autorisation, le référent ni l'hôte du navigateur
        assert relay.sent and all(set(sent) <= {"Origin", "Sec-Fetch-Site", "Content-Type"} for sent in relay.sent)
    finally:
        relay.shutdown()
        relay.server_close()
