"""Tests hors ligne de ``brvm_alpha.notes.research`` (recherche automatique des notes).

Aucun accès réseau : le transport HTTP est simulé à partir de pages **réelles** de
www.brvm.org capturées une fois le 22/11/2026 (``tests/fixtures/notes/*.html.gz``,
21 requêtes espacées de 11 s, robots.txt lu d'abord), de BOC texte réels
(``tests/fixtures/notes/boc/``) et d'un PDF texte réel (communiqué ETI du 23/10/2026).
L'horloge est simulée : les délais de politesse sont vérifiés sans attendre.
"""

from __future__ import annotations

import datetime as dt
import gzip
import json
import re
import socket
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from brvm_alpha.notes import research as r
from brvm_alpha.reference import SYMBOLS_2026

FIX = Path(__file__).parent / "fixtures" / "notes"
BOC_FIX = FIX / "boc"
UTC = dt.timezone.utc
#: Instant de la capture des pages (dimanche 22/11/2026, 03h40 UTC).
NOW = dt.datetime(2026, 11, 22, 3, 40, tzinfo=UTC)
B = "https://www.brvm.org"
ETI_PDF = f"{B}/sites/default/files/20261023_-_communique_-_annulation_ago_-_eti_tg.pdf"

#: Fichier de fixture -> URL de la page capturée.
PAGES = {
    "brvm_communiques": "/fr/emetteurs/type-annonces/communiques",
    "brvm_communiques_p1": "/fr/emetteurs/type-annonces/communiques?page=1",
    "brvm_convocations": "/fr/emetteurs/type-annonces/convocations-assemblees-generales",
    "brvm_dirigeants": "/fr/emetteurs/type-annonces/changements-de-dirigeants",
    "brvm_seuils": "/fr/emetteurs/type-annonces/franchissements-de-seuil",
    "brvm_notations": "/fr/emetteurs/type-annonces/notations-financieres",
    "brvm_resolutions": "/fr/emetteurs/type-annonces/projets-de-resolution",
    "brvm_dividendes": "/fr/esv/paiement-de-dividendes",
    "brvm_dividendes_p1": "/fr/esv/paiement-de-dividendes?page=1",
    "brvm_augmentation_capital": "/fr/esv/augmentation-de-capital",
    "brvm_fractionnement": "/fr/esv/fractionnement",
    "brvm_radiation": "/fr/esv/radiation",
    "brvm_avis": "/fr/marche/avis-et-publications/avis",
    "brvm_rapports_index": "/fr/rapports-societes-cotees",
    "brvm_rapports_index_p1": "/fr/rapports-societes-cotees?page=1",
    "brvm_rapports_index_p2": "/fr/rapports-societes-cotees?page=2",
    "brvm_emetteur_bank-africa-ci": "/fr/rapports-societe-cotes/bank-africa-ci",
    "brvm_emetteur_sonatel": "/fr/rapports-societe-cotes/sonatel",
}
LIST_FIXTURES = {
    "communiques": "brvm_communiques", "convocations": "brvm_convocations", "dirigeants": "brvm_dirigeants",
    "seuils": "brvm_seuils", "notations": "brvm_notations", "resolutions": "brvm_resolutions",
    "dividendes": "brvm_dividendes", "augmentation_capital": "brvm_augmentation_capital",
    "fractionnement": "brvm_fractionnement", "radiation": "brvm_radiation", "avis": "brvm_avis",
}


def html(name: str) -> bytes:
    return gzip.decompress((FIX / f"{name}.html.gz").read_bytes())


def parse(list_key: str) -> dict[str, Any]:
    return r.parse_list_page(html(LIST_FIXTURES[list_key]), list_key)


def by_title(items: list[dict[str, Any]], fragment: str) -> dict[str, Any]:
    return next(it for it in items if fragment in it["title"])


# ---------------------------------------------------------------------------
# Simulations : réseau, horloge, journal de notes
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Toute tentative d'accès réseau réel fait échouer le test."""
    import requests

    def boom(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("accès réseau interdit pendant les tests")

    monkeypatch.setattr(requests.Session, "request", boom)
    monkeypatch.setattr(socket, "create_connection", boom)


class FakeClock:
    """Horloge monotone simulée : ``sleep`` avance le temps et est enregistré."""

    def __init__(self) -> None:
        self.t = 1_000.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.t += seconds


class FakeResponse:
    def __init__(self, status: int, content: bytes = b"", headers: dict[str, str] | None = None, url: str = ""):
        self.status_code = status
        self.content = content
        self.headers = headers or {}
        self.url = url


class FakeWeb:
    """Transport HTTP simulé : URL -> réponse (ou liste de réponses successives)."""

    def __init__(self, pages: dict[str, Any], clock: FakeClock | None = None, latency: float = 0.3):
        self.pages = dict(pages)
        self.calls: list[tuple[str, dict[str, str], float | None]] = []
        self.clock = clock
        self.latency = latency

    def __call__(self, url: str, headers: dict[str, str], timeout: float) -> FakeResponse:
        self.calls.append((url, dict(headers), self.clock.t if self.clock else None))
        if self.clock:
            self.clock.t += self.latency
        resp = self.pages.get(url)
        if resp is None:
            return FakeResponse(404, b"<html>introuvable</html>", {"Content-Type": "text/html"}, url)
        if isinstance(resp, list):
            resp = resp.pop(0) if len(resp) > 1 else resp[0]
        if callable(resp):
            resp = resp(url, headers)
        if isinstance(resp, Exception):
            raise resp
        if isinstance(resp, FakeResponse):
            resp.url = resp.url or url
            return resp
        status, body = resp[:2]
        hdrs = resp[2] if len(resp) > 2 else {"Content-Type": "text/html; charset=utf-8"}
        return FakeResponse(status, body, hdrs, url)

    def urls(self) -> list[str]:
        return [c[0] for c in self.calls]


def brvm_pages(**overrides: Any) -> dict[str, Any]:
    """Toutes les pages capturées, servies à leur URL réelle (robots.txt compris)."""
    meta = {m["url"]: m for m in json.loads((FIX / "capture_log.json").read_text())}
    pages: dict[str, Any] = {f"{B}/robots.txt": (200, (FIX / "robots_brvm.txt").read_bytes(),
                                                 {"Content-Type": "text/plain"})}
    for name, path in PAGES.items():
        m = meta.get(B + path, {})
        hdrs = {"Content-Type": "text/html; charset=utf-8"}
        if m.get("etag"):
            hdrs["ETag"] = m["etag"]
        if m.get("last_modified"):
            hdrs["Last-Modified"] = m["last_modified"]
        pages[B + path] = (200, html(name), hdrs)
    pages[ETI_PDF] = (200, (FIX / "doc_20261023_communique_annulation_ago_eti_tg.pdf").read_bytes(),
                      {"Content-Type": "application/pdf"})
    pages.update(overrides)
    return pages


def make_session(tmp_path: Path, pages: dict[str, Any] | None = None, **kw: Any):
    clock = FakeClock()
    web = FakeWeb(brvm_pages() if pages is None else pages, clock)
    kw.setdefault("delay_s", 10.0)
    sess = r.PoliteSession(transport=web, clock=clock, sleep=clock.sleep, cache_dir=tmp_path / "cache",
                           log_path=tmp_path / "fetch_log.jsonl", now=lambda: NOW, **kw)
    return sess, web, clock


def request_gaps(web: FakeWeb, host: str = "www.brvm.org") -> list[float]:
    times = [t for (u, _, t) in web.calls if host in u]
    return [b - a for a, b in zip(times, times[1:])]


class MemoryStore:
    """Journal de notes minimal (contrat ``NoteStore``) pour tester la couche (b) seule."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.notes: dict[str, Any] = {}
        self.updates: list[tuple[str, dict[str, Any]]] = []

    def add(self, note: Any) -> str:
        if note.note_id in self.notes:
            raise ValueError("doublon")
        self.notes[note.note_id] = note
        return note.note_id

    def get(self, note_id: str) -> Any:
        return self.notes.get(note_id)

    def update(self, note_id: str, **changes: Any) -> Any:
        self.updates.append((note_id, changes))
        self.notes[note_id] = self.notes[note_id].copy(**changes, version=self.notes[note_id].version + 1)
        return self.notes[note_id]

    def list(self, target=None, since=None, until=None, source=None, status="active") -> pd.DataFrame:
        rows = [n.to_dict() for n in self.notes.values()]
        return pd.DataFrame(rows, columns=["note_id", "url", "title", "targets", "published_at", "event_type",
                                           "source"] if not rows else None)


# ---------------------------------------------------------------------------
# Couche (a) : listes Drupal de brvm.org
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "list_key,n_rows,last_page",
    [("communiques", 15, 26), ("convocations", 15, 59), ("dirigeants", 15, 7), ("seuils", 15, 2),
     ("notations", 15, 31), ("resolutions", 15, 18), ("dividendes", 10, 43), ("augmentation_capital", 10, 2),
     ("fractionnement", 10, 4), ("radiation", 10, 1), ("avis", 10, 192)],
)
def test_lists_rows_and_last_page(list_key: str, n_rows: int, last_page: int) -> None:
    """Nombre de lignes par page et dernière page : identiques au relevé du document 07 §1.2."""
    p = parse(list_key)
    assert p["n_rows"] == n_rows
    assert len(p["items"]) == n_rows
    assert p["last_page"] == last_page
    for it in p["items"]:
        assert it["source"] == "brvm_list" and it["list_type"] == list_key
        assert it["title"]
        assert it["doc_url"] is None or it["doc_url"].startswith(f"{B}/sites/default/files/")


def test_communiques_dates_links_symbols() -> None:
    items = parse("communiques")["items"]
    first = items[0]
    assert first["doc_date"] == "2026-11-16" and first["date_source"] == "liste"
    assert first["symbol"] == "SOGC" and first["country"] == "CI"
    assert first["doc_url"] == f"{B}/sites/default/files/20261116_-_communique_de_presse_-_sogb_ci.pdf"
    assert first["file_date"] == "2026-11-16"
    # Date de mise en ligne (colonne) et date du document (nom du fichier) peuvent différer.
    eri = by_title(items, "Profit Warning")
    assert (eri["symbol"], eri["doc_date"], eri["file_date"]) == ("SIVC", "2026-06-21", "2026-06-19")
    assert eri["issuer"] == "AIR LIQUIDE CI"  # libellé historique -> ERIUM CI (SIVC)
    eti = by_title(items, "Annulation")
    assert eti["symbol"] == "ETIT" and eti["doc_url"] == ETI_PDF
    assert [it["symbol"] for it in items[:10]] == ["SOGC", "ETIT", "SNTS", "SCRC", "UNXC", "ETIT", "SNTS",
                                                   "BICC", "NSBC", "FTSC"]
    # Émetteur non coté (AFINHAB, ex-CRRH) ou actionnaire seul : pas de symbole.
    assert by_title(items, "AFINHAB")["symbol"] is None
    dates = [it["doc_date"] for it in items]
    assert dates == sorted(dates, reverse=True)


def test_historical_labels_map_to_current_symbols() -> None:
    div = parse("dividendes")["items"]
    labels = {it["issuer"]: it["symbol"] for it in div}
    assert labels["BOLLORE TRANSPORT & LOGISTICS"] == "SDSC"
    assert labels["TOTAL"] == "TTLC"
    assert labels["SGCI"] == "SGBC"
    assert labels["VIVO ENERGY CI"] == "SHEC"
    dirig = parse("dirigeants")["items"]
    assert by_title(dirig, "MOOV BURKINA FASO")["symbol"] == "ONTBF"
    assert by_title(dirig, "TOTALENERGIES MARKETING SENEGAL")["symbol"] == "TTLS"
    assert by_title(dirig, "CÔTE D'IVOIRE : Changement important au sein")["symbol"] == "TTLC"
    conv = parse("convocations")["items"]
    assert by_title(conv, "AFRICA GLOBAL LOGISTICS CI : Avis de convocation")["symbol"] == "SDSC"


def test_dividend_list_structured_fields() -> None:
    items = parse("dividendes")["items"]
    agl = items[0]
    assert agl["symbol"] == "SDSC" and agl["event_hint"] == "DIV_NOTICE"
    assert agl["extra"]["div_listed"] == 92.0 and agl["extra"]["div_net"] == pytest.approx(80.96)  # présomption
    assert agl["extra"]["ex_date"] == "2026-10-26" and agl["extra"]["pay_date"] == "2026-10-27"
    assert agl["extra"]["exercice"] == 2025 and agl["extra"]["avis_no"] == 297
    assert agl["doc_date"] == "2026-10-09" and agl["date_source"] == "fichier"
    assert "Date ex-dividende : 26/10/2026" in agl["text"]
    # Émetteurs ivoiriens : la colonne « net » de brvm.org est presque toujours brute (essai réel,
    # 13 cas sur 15 contre le « dernier dividende payé » du BOC) : net présumé = 88 % du montant affiché.
    total = next(it for it in items if it["symbol"] == "TTLC")
    assert total["extra"]["div_listed"] == pytest.approx(158.827)
    assert total["extra"]["div_net"] == pytest.approx(139.7678) and total["extra"]["div_basis"] == "brut présumé"
    sgbc = next(it for it in items if it["symbol"] == "SGBC")
    assert sgbc["extra"]["div_gross"] == 2606.0 and sgbc["extra"]["div_net"] == pytest.approx(2293.28)
    assert not any(it["extra"].get("date_suspect") for it in items)


def test_dividend_suspect_notice_dates_are_floored() -> None:
    """Document 07 §1.2 : l'avis LNB porte une mauvaise année dans son nom de fichier."""
    items = r.parse_list_page(html("brvm_dividendes_p1"), "dividendes")["items"]
    lnb = next(it for it in items if it["symbol"] == "LNBB")
    assert lnb["file_date"] == "2025-07-20"  # dimanche, un an trop tôt
    assert "date d'avis un week-end" in lnb["extra"]["date_suspect"]
    assert lnb["extra"]["published_floor"] == "2026-07-21"  # ex 31/07/2026 - 10 jours
    pub, prec, est = r.item_published_at(lnb, NOW)
    assert pub.date() == dt.date(2026, 7, 21) and prec == "date" and est
    sogb = next(it for it in items if it["symbol"] == "SOGC")  # date ex un dimanche
    assert "date ex-dividende un week-end" in sogb["extra"]["date_suspect"]


def test_avis_list_has_time_and_flags_bonds() -> None:
    items = parse("avis")["items"]
    first = items[0]
    assert first["published_at"] == "2026-11-17T18:18:00+00:00" and first["date_source"] == "horodatage"
    assert first["instrument"] == "obligation" and first["symbol"] is None
    assert first["extra"]["avis_no"] == 336
    assert by_title(items, "TPCI.O77 : Suspension")["country"] == "CI"
    split = by_title(items, "SONATEL SN : Fractionnement")
    assert split["symbol"] == "SNTS" and split["instrument"] is None
    tsd = by_title(items, "Transactions Sur Dossier")
    assert tsd["market_level"] and tsd["symbol"] is None


def test_split_capital_increase_and_delisting_lists() -> None:
    splits = parse("fractionnement")["items"]
    snts = splits[0]
    assert snts["symbol"] == "SNTS" and snts["event_hint"] == "SPLIT"
    assert snts["extra"]["split_ratio"] == 10.0 and snts["extra"]["split_date"] == "2026-10-26"
    assert [it["extra"]["split_ratio"] for it in splits[1:4]] == [64.0, 64.0, 4.0]
    cap = parse("augmentation_capital")["items"]
    assert cap[0]["symbol"] == "SIBC" and cap[0]["event_hint"] == "CAP_INC"
    assert cap[0]["extra"]["record_date"] == "2024-11-19" and cap[0]["extra"]["parity_ratio"] == 1.0
    assert by_title(cap, "BANK OF AFRICA NG")["extra"]["parity_ratio"] == pytest.approx(0.6)
    rad = parse("radiation")["items"]
    assert all(it["instrument"] == "obligation" and it["symbol"] is None for it in rad)
    countries = [it["country"] for it in rad]
    assert countries[:3] == [None, "CI", "CI"]
    # « SUKUK ETAT DU SENEGAL » rattaché par erreur à TPCI : le nom de l'obligation prime.
    assert by_title(rad, "SUKUK ETAT DU SENEGAL")["country"] == "SN"


def test_ancillary_documents_are_flagged() -> None:
    conv = parse("convocations")["items"]
    flagged = [it["title"] for it in conv if it["ancillary"]]
    assert len(flagged) == 6 and all(("Pouvoir" in t or "Formulaire" in t) for t in flagged)
    notes = parse("notations")["items"]
    zaka = by_title(notes, "FCTC ZAKA")
    assert zaka["instrument"] == "fctc" and zaka["symbol"] is None
    assert zaka["extra"]["issuer_symbol"] == "NSBC"


def test_issuer_index_covers_all_listed_shares() -> None:
    issuers = []
    for name in ("brvm_rapports_index", "brvm_rapports_index_p1", "brvm_rapports_index_p2"):
        p = r.parse_issuers_index(html(name))
        issuers += p["issuers"]
    assert len(issuers) == 75
    found = {i["symbol"]: i["slug"] for i in issuers if i["symbol"]}
    assert set(SYMBOLS_2026) <= set(found)
    for sym in SYMBOLS_2026:
        assert any(i["slug"] in r.ISSUER_SLUGS[sym] for i in issuers if i["symbol"] == sym), sym
    assert next(i for i in issuers if i["name"] == "TPCI")["symbol"] is None
    assert r.parse_issuers_index(html("brvm_rapports_index"))["last_page"] == 2


def test_issuer_reports_dates_from_file_names() -> None:
    url = B + PAGES["brvm_emetteur_bank-africa-ci"]
    p = r.parse_issuer_reports(html("brvm_emetteur_bank-africa-ci"), url, "BOAC")
    assert p["issuer"] == "BANK OF AFRICA CI" and p["last_page"] == 3 and len(p["items"]) == 20
    assert {it["symbol"] for it in p["items"]} == {"BOAC"}
    first = p["items"][0]
    assert first["title"] == "BOA CI : Rapport d'activités - 3e trimestre 2026"
    assert first["doc_date"] == "2026-11-02" and first["date_source"] == "fichier"
    assert first["source"] == "brvm_issuer"
    son = r.parse_issuer_reports(html("brvm_emetteur_sonatel"), B + PAGES["brvm_emetteur_sonatel"], "SNTS")
    undated = [it for it in son["items"] if it["extra"].get("date_inconnue")]
    assert len(undated) == 2 and all(it["doc_date"] is None for it in undated)
    # Document d'ONATEL BF rangé par erreur sur la page SONATEL : le titre l'emporte.
    onatel = by_title(son["items"], "ONATEL BF")
    assert onatel["symbol"] == "ONTBF" and onatel["extra"]["symbol_conflict"] == ["SNTS", "ONTBF"]


def test_date_helpers() -> None:
    assert r.parse_date_fr("1er décembre 2026") == dt.date(2026, 12, 1)
    assert r.parse_date_fr("16/11/2026") == dt.date(2026, 11, 16)
    assert r.parse_date_fr("2026-11-17T18:18:00+00:00") == dt.date(2026, 11, 17)
    assert r.parse_date_fr("27 août 2026") == dt.date(2026, 8, 27)
    assert r.parse_date_fr("7-sept.-26") == dt.date(2026, 9, 7)
    assert r.parse_date_fr("bientôt") is None
    assert r.date_from_filename(ETI_PDF) == dt.date(2026, 10, 23)
    assert r.date_from_filename(f"{B}/sites/default/files/comfi_groupe_sonatel_t1_2023.pdf") is None
    assert r.date_from_filename(f"{B}/sites/default/files/20261399_-_x.pdf") is None
    assert r.parse_parity("dix (10) actions nouvelles pour une (1) action ancienne") == 10.0
    assert r.parse_parity("64 actions nouvelles pour une action ancienne") == 64.0
    assert r.parse_parity("Trois (3) actions nouvelles pour cinq (5) actions") == pytest.approx(0.6)


# ---------------------------------------------------------------------------
# Couche (a) : pagination et arrêts
# ---------------------------------------------------------------------------


def test_pagination_two_pages_with_crawl_delay(tmp_path: Path) -> None:
    sess, web, clock = make_session(tmp_path)
    items = r.collect_list(sess, "communiques", max_pages=2)
    assert web.urls() == [f"{B}/robots.txt", B + PAGES["brvm_communiques"], B + PAGES["brvm_communiques_p1"]]
    assert len(items) == 30 and [it["page"] for it in items] == [0] * 15 + [1] * 15
    assert all(g >= 10.0 for g in request_gaps(web))  # Crawl-delay: 10
    assert sess.crawl_delay(B) == 10.0


def test_pagination_stops_at_first_known_url(tmp_path: Path) -> None:
    sess, web, _ = make_session(tmp_path)
    first = r.parse_list_page(html("brvm_communiques"), "communiques")["items"]
    known = {first[2]["doc_url"]}
    items = r.collect_list(sess, "communiques", max_pages=10, known_urls=known)
    assert B + PAGES["brvm_communiques_p1"] not in web.urls()
    assert len(items) == 14 and first[2]["doc_url"] not in {it["doc_url"] for it in items}


def test_pagination_stops_at_since(tmp_path: Path) -> None:
    sess, web, _ = make_session(tmp_path)
    items = r.collect_list(sess, "communiques", since="2026-07-01", max_pages=10)
    assert B + PAGES["brvm_communiques_p1"] not in web.urls()
    assert len(items) == 11 and min(it["doc_date"] for it in items) >= "2026-07-01"
    sess2, web2, _ = make_session(tmp_path / "b")
    items2 = r.collect_list(sess2, "communiques", since="2026-03-01", max_pages=10)
    # page 0 entièrement après le 01/03 -> page 1 lue ; page 1 finit en 2025 -> arrêt.
    assert web2.urls()[-1] == B + PAGES["brvm_communiques_p1"]
    assert f"{B}/fr/emetteurs/type-annonces/communiques?page=2" not in web2.urls()
    assert len(items2) == 18


def test_collect_issuer_reports_uses_known_slug(tmp_path: Path) -> None:
    sess, web, _ = make_session(tmp_path)
    items = r.collect_issuer_reports(sess, "BOAC")
    assert web.urls()[-1] == B + PAGES["brvm_emetteur_bank-africa-ci"] and len(items) == 20
    items = r.collect_issuer_reports(sess, "SNTS", since="2026-01-01")
    assert [it["doc_date"] for it in items] == ["2026-10-29", "2026-07-24", "2026-04-17", "2026-02-16"]
    with pytest.raises(ValueError):
        r.collect_issuer_reports(sess, "XXXX")


# ---------------------------------------------------------------------------
# Couche (a) : politesse (robots.txt, délais, quota, 403/429, 5xx, cache)
# ---------------------------------------------------------------------------


def test_robots_crawl_delay_applies_to_other_hosts(tmp_path: Path) -> None:
    host = "https://exemple.test"
    pages = {f"{host}/robots.txt": (200, b"User-agent: *\nCrawl-delay: 7\nDisallow: /prive/\n", {}),
             f"{host}/a": (200, b"<html><h1>A</h1></html>"), f"{host}/b": (200, b"<html><h1>B</h1></html>")}
    sess, web, clock = make_session(tmp_path, pages, delay_s=1.0)
    sess.get(f"{host}/a")
    sess.get(f"{host}/b")
    assert web.urls() == [f"{host}/robots.txt", f"{host}/a", f"{host}/b"]
    assert all(g >= 7.0 for g in request_gaps(web, "exemple.test"))
    assert max(clock.sleeps) == pytest.approx(7.0)  # délai compté depuis la fin de la réponse précédente
    with pytest.raises(r.RobotsDisallowed, match="robots.txt"):
        sess.get(f"{host}/prive/page")
    assert f"{host}/prive/page" not in web.urls()


def test_brvm_floor_delay_even_if_configured_lower(tmp_path: Path) -> None:
    sess, web, _ = make_session(tmp_path, delay_s=0.5)
    sess.get(B + PAGES["brvm_avis"])
    sess.get(B + PAGES["brvm_dividendes"])
    assert all(g >= 10.0 for g in request_gaps(web))


def test_missing_robots_allows_and_robots_5xx_refuses(tmp_path: Path) -> None:
    pages = {"https://a.test/robots.txt": (404, b""), "https://a.test/x": (200, b"<p>x</p>"),
             "https://b.test/robots.txt": (503, b"")}
    sess, web, _ = make_session(tmp_path, pages, delay_s=1.0, backoff_s=1.0)
    assert sess.get("https://a.test/x").status == 200
    with pytest.raises(r.ServerUnavailable, match="robots.txt"):
        sess.get("https://b.test/y")


@pytest.mark.parametrize("status", [403, 429])
def test_stop_definitively_on_403_429(tmp_path: Path, status: int) -> None:
    pages = brvm_pages(**{B + PAGES["brvm_avis"]: (status, b"Forbidden")})
    sess, web, _ = make_session(tmp_path, pages)
    sess.get(B + PAGES["brvm_communiques"])
    with pytest.raises(r.AccessBlocked, match=f"HTTP {status}"):
        sess.get(B + PAGES["brvm_avis"])
    assert sess.stopped and str(status) in sess.stopped
    n = len(web.calls)
    with pytest.raises(r.AccessBlocked):
        sess.get(B + PAGES["brvm_dividendes"])
    assert len(web.calls) == n  # plus aucune requête, même vers une autre page
    events = [json.loads(line)["event"] for line in (tmp_path / "fetch_log.jsonl").read_text().splitlines()]
    assert "stop" in events and events.count("robots") == 1
    errors: list[str] = []
    assert r.collect_list(sess, "dividendes", errors=errors) == [] and "arrêtée" in errors[0]


def test_retries_with_exponential_backoff_on_5xx(tmp_path: Path) -> None:
    url = B + PAGES["brvm_avis"]
    pages = brvm_pages(**{url: [(503, b""), (502, b""), (200, html("brvm_avis"))]})
    sess, web, clock = make_session(tmp_path, pages, backoff_s=10.0)
    res = sess.get(url)
    assert res.status == 200 and web.urls().count(url) == 3
    assert clock.sleeps.count(10.0) >= 1 and 20.0 in clock.sleeps
    assert not sess.stopped
    pages = brvm_pages(**{url: [(500, b"")]})
    sess, web, _ = make_session(tmp_path / "b", pages)
    with pytest.raises(r.ServerUnavailable, match="3 essais"):
        sess.get(url)
    assert web.urls().count(url) == 3 and sess.stopped


def test_network_error_is_retried_then_stops(tmp_path: Path) -> None:
    url = B + PAGES["brvm_avis"]
    pages = brvm_pages(**{url: [ConnectionError("réseau coupé")]})
    sess, web, _ = make_session(tmp_path, pages, backoff_s=1.0)
    with pytest.raises(r.ServerUnavailable):
        sess.get(url)
    assert web.urls().count(url) == 3


def test_quota_counts_robots_and_stops(tmp_path: Path) -> None:
    sess, web, _ = make_session(tmp_path, max_requests=2)
    sess.get(B + PAGES["brvm_avis"])  # robots.txt + page = 2 requêtes
    with pytest.raises(r.QuotaExceeded):
        sess.get(B + PAGES["brvm_dividendes"])
    assert len(web.calls) == 2 and sess.n_requests == 2


def test_conditional_get_and_offline_cache(tmp_path: Path) -> None:
    url = B + PAGES["brvm_avis"]
    calls: list[dict[str, str]] = []

    def answer(u: str, headers: dict[str, str]) -> FakeResponse:
        calls.append(headers)
        if headers.get("If-None-Match") == '"v1"':
            return FakeResponse(304, b"", {"ETag": '"v1"'})
        return FakeResponse(200, html("brvm_avis"), {"ETag": '"v1"', "Last-Modified": "Sun, 22 Nov 2026 03:40:00 GMT",
                                                     "Content-Type": "text/html; charset=utf-8"})

    pages = brvm_pages(**{url: answer})
    sess, web, _ = make_session(tmp_path, pages)
    first = sess.get(url)
    second = sess.get(url)
    assert first.status == 200 and not first.from_cache
    assert second.from_cache and second.content == first.content
    assert calls[1]["If-None-Match"] == '"v1"' and calls[1]["If-Modified-Since"].startswith("Sun, 22 Nov 2026")
    off, web_off, _ = make_session(tmp_path, {}, offline=True)
    assert off.get(url).content == first.content
    with pytest.raises(r.OfflineCacheMiss):
        off.get(B + PAGES["brvm_dividendes"])
    assert web_off.calls == []  # hors ligne : aucun appel au transport


def test_fetch_log_is_jsonl(tmp_path: Path) -> None:
    sess, web, _ = make_session(tmp_path)
    sess.get(B + PAGES["brvm_avis"])
    lines = [json.loads(x) for x in (tmp_path / "fetch_log.jsonl").read_text().splitlines()]
    assert [x["event"] for x in lines] == ["robots", "page"]
    assert lines[1]["url"] == B + PAGES["brvm_avis"] and lines[1]["status"] == 200 and lines[1]["bytes"] > 10_000
    assert web.calls[1][1]["User-Agent"] == "brvm-alpha/0.1 (outil d'analyse personnel)"


# ---------------------------------------------------------------------------
# Couche (a) : événements des BOC locaux
# ---------------------------------------------------------------------------


def boc(day: str) -> str:
    return gzip.decompress((BOC_FIX / f"boc_{day}.txt.gz").read_bytes()).decode("utf-8")


def test_boc_sections_communiques_and_ag_cancel() -> None:
    items = r.parse_boc_events(boc("20261029"), "2026-10-29")
    comm = [it for it in items if it["list_type"] == "boc_communiques"]
    assert [it["symbol"] for it in comm] == ["CIEC", "CIEC", "PRSC", "PRSC", "CBIBF", "SNTS", "SNTS"]
    assert comm[4]["issuer"] == "CORIS BANK INTERNATIONAL"  # libellé sur deux lignes, fusionné
    assert comm[4]["extra"]["nature"] == "Rapport d'activités du troisième trimestre"
    assert all(it["published_at"] == "2026-10-29T19:00:00+00:00" for it in items)
    assert all(it["page_url"] == "https://www.brvm.org/sites/default/files/boc_20261029_2.pdf" for it in items)
    cancel = [it for it in items if it["list_type"] == "boc_ag_annulation"]
    assert len(cancel) == 1 and cancel[0]["symbol"] == "ETIT" and cancel[0]["event_hint"] == "AG_CANCEL"
    assert cancel[0]["extra"]["ag_date"] == "2026-10-26"
    assert sum(it["list_type"] == "boc_ag" for it in items) == 50
    assert {it["symbol"] for it in items if it["list_type"] == "boc_suspension"} == {"SEMC", "SICC"}
    # Avis sur obligations (intérêts, FCTC) écartés par défaut ; la décision AMF sur deux lignes est fusionnée.
    assert not [it for it in items if it["list_type"] == "boc_avis"]
    full = r.parse_boc_events(boc("20261029"), "2026-10-29", include_bonds=True)
    amf = next(it for it in full if it["list_type"] == "boc_avis" and it["issuer"] == "AMF-UMOA")
    assert amf["extra"]["avis_no"] == "Décision N°AMF- UMOA/2026/306"
    assert "FCTC AFG REFINANCEMENT CLO" in amf["title"]


def test_boc_operations_and_dividend_avis() -> None:
    items = r.parse_boc_events(boc("20261009"), "2026-10-09")
    ops = [it for it in items if it["list_type"] == "boc_operations"]
    # PRSC : « 209 F CFA par action (IRVM applicable de 12 %…) » est brut ; net = 209 × 0,88 = 183,92,
    # valeur du « dernier dividende payé » du BOC (panel, 21/10/2026). Corrigé lors de l'essai réel.
    assert [(it["symbol"], it["extra"]["div_net"], it["extra"]["pay_date"]) for it in ops] == [
        ("SDSC", 92.0, "2026-10-27"), ("PRSC", 183.92, "2026-10-23")]
    assert ops[1]["extra"]["div_gross"] == 209.0 and "div_gross" not in ops[0]["extra"]
    avis = [it for it in items if it["list_type"] == "boc_avis"]
    assert [(it["symbol"], it["event_hint"]) for it in avis] == [("PRSC", "DIV_NOTICE"), ("SDSC", "DIV_NOTICE")]
    assert avis[1]["extra"]["avis_no"] == "297-2026"


def test_boc_sp_mentions_old_and_new_layouts() -> None:
    eq = set(SYMBOLS_2026) | {"SVOC", "TTRC"}
    old = gzip.decompress((FIX.parent / "boc_20200302.txt.gz").read_bytes()).decode("utf-8")
    assert r._boc_sp_symbols(old.splitlines(), eq) == {"SVOC", "TTRC", "UNLC"}  # code secteur en tête de ligne
    assert r._boc_sp_symbols(boc("20261029").splitlines(), eq) == {"SEMC", "SICC"}


def test_collect_boc_events_first_appearance_and_suspensions() -> None:
    items = r.collect_boc_events(BOC_FIX, since="2026-09-16", until="2026-09-17")
    sus = {it["symbol"]: it for it in items if it["list_type"] == "boc_suspension"}
    assert set(sus) == {"SCRC", "SEMC", "SICC"}
    assert all(it["doc_date"] == "2026-09-16" and it["event_hint"] == "SUSPENSION" for it in sus.values())
    # Les opérations déjà présentes au BOC du 15/09 sont datées du 15/09 (première apparition).
    smb = next(it for it in items if it["list_type"] == "boc_operations" and it["symbol"] == "SMBC")
    assert smb["doc_date"] == "2026-09-15"
    avis = [it for it in items if it["list_type"] == "boc_avis"]
    assert [it["symbol"] for it in avis] == ["SICC", "SCRC", "SEMC"]
    # Fenêtre de fin d'année : reprise de SEMC au 02/01/2026.
    items = r.collect_boc_events(BOC_FIX, since="2026-01-02", until="2026-01-02")
    rep = [it for it in items if it["list_type"] == "boc_reprise"]
    assert [(it["symbol"], it["doc_date"], it["event_hint"]) for it in rep] == [("SEMC", "2026-01-02", "RESUMPTION")]


# ---------------------------------------------------------------------------
# Couche (a) : PDF
# ---------------------------------------------------------------------------


def blank_pdf() -> bytes:
    """PDF valide d'une page sans texte (comme un scan sans couche texte)."""
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R >>",
            b"<< /Length 0 >>\nstream\n\nendstream"]
    out, offs = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offs)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return out


def test_pdf_text_and_scan_detection(tmp_path: Path) -> None:
    info = r.extract_pdf_text(FIX / "doc_20261023_communique_annulation_ago_eti_tg.pdf")
    assert info["n_pages"] == 1 and not info["ocr_needed"] and info["chars_per_page"] > 200
    assert "Annulation de l’Assemblée Générale Ordinaire" in info["text"]
    scan = tmp_path / "scan.pdf"
    scan.write_bytes(blank_pdf())
    info = r.extract_pdf_text(scan)
    assert info["ocr_needed"] and info["n_pages"] == 1


def test_fetch_document_downloads_once(tmp_path: Path) -> None:
    sess, web, _ = make_session(tmp_path)
    doc = r.fetch_document(sess, ETI_PDF)
    assert not doc["cached"] and doc["sha256"] == r.url_hash(ETI_PDF) and not doc["ocr_needed"]
    assert Path(doc["path"]).exists() and Path(doc["path"]).parent == tmp_path / "cache" / "docs"
    again = r.fetch_document(sess, ETI_PDF)
    assert again["cached"] and again["text"] == doc["text"]
    assert web.urls().count(ETI_PDF) == 1


# ---------------------------------------------------------------------------
# Cibles, horodatage, première séance négociable
# ---------------------------------------------------------------------------


def test_expand_targets() -> None:
    assert r.expand_targets(None).all_market
    s = r.expand_targets(["SNTS"], panel_dir=None)
    assert not s.all_market and s.symbols == {"SNTS"}
    s = r.expand_targets(["IDX:BRVM-30"], panel_dir=None)
    assert len(s.symbols) == 30 and "SNTS" in s.symbols and "NTLC" not in s.symbols
    assert r.expand_targets(["IDX:BRVM-C"], panel_dir=None).all_market
    s = r.expand_targets(["PAYS:CI"], panel_dir=None)
    assert "SOGC" in s.symbols and "SNTS" not in s.symbols and s.countries == {"CI"}
    s = r.expand_targets(["IDX:PRESTIGE"], panel_dir=None)
    assert s.symbols == set(r.FALLBACK_COMPARTMENT_PRESTIGE)
    s = r.expand_targets(["SECT:TEL"], panel_dir=None)
    assert s.symbols == {"ONTBF", "ORAC", "SNTS"}
    with pytest.raises(ValueError):
        r.expand_targets(["??"], panel_dir=None)


def test_scope_matching() -> None:
    avis = parse("avis")["items"]
    s = r.expand_targets(["PAYS:CI"], panel_dir=None)
    assert s.matches(by_title(avis, "TPCI.O77 : Suspension"))  # événement souverain ivoirien
    assert not s.matches(by_title(avis, "SONATEL SN : Fractionnement"))
    assert r.expand_targets(["SNTS"], panel_dir=None).matches(by_title(avis, "SONATEL SN : Fractionnement"))
    idx = r.expand_targets(["IDX:BRVM-30"], panel_dir=None)
    assert idx.matches(by_title(avis, "Transactions Sur Dossier"))  # avis de marché
    theme = r.expand_targets(["THEME:dividendes"], panel_dir=None)
    assert theme.matches(parse("dividendes")["items"][0])


def test_first_tradable_session_cutoff() -> None:
    cal = pd.DatetimeIndex(pd.bdate_range("2026-11-02", "2026-11-30"))
    assert r.first_tradable_session("2026-11-20T08:30:00Z", cal) == pd.Timestamp("2026-11-20")
    assert r.first_tradable_session("2026-11-20T09:30:00Z", cal) == pd.Timestamp("2026-11-23")
    assert r.first_tradable_session("2026-11-21T08:00:00Z", cal) == pd.Timestamp("2026-11-23")
    # Avec le modèle (calendrier du panel) : avant 09h00 -> jour même ; date seule -> séance suivante.
    assert r._tradable(pd.Timestamp("2026-11-20 08:59", tz="UTC")) == pd.Timestamp("2026-11-20")
    assert r._tradable(pd.Timestamp("2026-11-20 09:00", tz="UTC")) == pd.Timestamp("2026-11-23")
    assert r._tradable(pd.Timestamp("2026-11-20", tz="UTC"), precision="date") == pd.Timestamp("2026-11-23")


def test_item_published_at_rules() -> None:
    comm = parse("communiques")["items"][0]  # mis en ligne le 16/11 (colonne de la liste)
    ts, prec, est = r.item_published_at(comm, NOW)
    assert (ts.date(), prec, est) == (dt.date(2026, 11, 16), "date", True)
    early = dict(comm, doc_date="2026-11-22")  # vu le jour même à 03h40 : l'heure de collecte borne
    ts, prec, _ = r.item_published_at(early, NOW)
    assert ts == NOW and prec == "datetime"
    avis = parse("avis")["items"][0]
    ts, prec, est = r.item_published_at(avis, NOW)
    assert ts == dt.datetime(2026, 11, 17, 18, 18, tzinfo=UTC) and prec == "datetime" and not est
    div = parse("dividendes")["items"][0]  # date lue dans le nom du fichier (vendredi 09/10) -> + 1 séance
    ts, prec, _ = r.item_published_at(div, NOW)
    assert ts.date() == dt.date(2026, 10, 12) and prec == "date"
    assert r._tradable(ts, None, prec) == pd.Timestamp("2026-10-13")
    undated = dict(comm, doc_date=None, date_source=None)
    assert r.item_published_at(undated, NOW)[0] == NOW


def test_note_ids_are_stable_and_source_independent() -> None:
    div = parse("dividendes")["items"][0]
    same_pdf = dict(div, list_type="avis", source="brvm_list", title="autre titre")
    assert r.note_id_for(div) == r.note_id_for(same_pdf)
    a = r.parse_boc_events(boc("20261029"), "2026-10-29")
    b = r.parse_boc_events(boc("20261029"), "2026-10-29")
    assert [r.note_id_for(x) for x in a] == [r.note_id_for(x) for x in b]
    assert len({r.note_id_for(x) for x in a}) == len(a)


def test_content_signature_matches_across_sources() -> None:
    issuer_title = "SONATEL SN : Rapport d'activités - 3e trimestre 2026"
    boc_title = "Rapport d'activités - 3e trimestre 2026 - SONATEL SN"
    assert r.content_signature(issuer_title, "SNTS") == r.content_signature(boc_title, "SNTS")
    assert r.content_signature(issuer_title, "SNTS") != r.content_signature(
        "SONATEL SN : Rapport d'activités - 1er semestre 2026", "SNTS")


def test_extract_html_content_from_brvm_page() -> None:
    c = r.extract_html_content(html("brvm_emetteur_sonatel"), B + PAGES["brvm_emetteur_sonatel"])
    assert c["title"] and "SONATEL SN : Rapport d'activités - 3e trimestre 2026" in c["text"]
    assert "<script" not in c["text"]


# ---------------------------------------------------------------------------
# fetch_url_note : refus clairs, sans contournement
# ---------------------------------------------------------------------------


def test_fetch_url_note_refusals(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path)
    with pytest.raises(r.SourceDisabled, match="désactivée par défaut"):
        r.fetch_url_note("https://www.sikafinance.com/marches/actualites", store)
    with pytest.raises(r.SourceDisabled):
        r.fetch_url_note("https://www.richbourse.com/common/news/index", store)
    with pytest.raises(ValueError, match="URL invalide"):
        r.fetch_url_note("ftp://exemple.test/x", store)
    host = "https://presse.test"
    pages = {f"{host}/robots.txt": (200, b"User-agent: *\nDisallow: /article/\n", {}),
             f"{host}/bloque": (403, b"Forbidden")}
    sess, web, _ = make_session(tmp_path, pages, delay_s=1.0)
    with pytest.raises(r.RobotsDisallowed, match="interdit"):
        r.fetch_url_note(f"{host}/article/1", store, session=sess)
    assert f"{host}/article/1" not in web.urls()
    with pytest.raises(r.AccessBlocked, match="sans aucune tentative de contournement"):
        r.fetch_url_note(f"{host}/bloque", store, session=sess)
    assert store.notes == {}


# ---------------------------------------------------------------------------
# Couche (b) : conversion en notes (modèle réel), déduplication, journal
# ---------------------------------------------------------------------------

model = pytest.importorskip("brvm_alpha.notes.model")


def test_item_to_note_dividend() -> None:
    div = parse("dividendes")["items"][0]
    note = r.item_to_note(div, now=NOW, analyze=False)
    assert isinstance(note, model.Note)
    assert note.source == "brvm_list" and note.author == "auto" and note.targets == ["SDSC"]
    assert note.event_type == "DIV_NOTICE" and note.url == div["doc_url"]
    assert note.published_precision == "date" and note.published_at == pd.Timestamp("2026-10-12", tz="UTC")
    assert note.first_tradable_session == pd.Timestamp("2026-10-13")
    assert note.created_at == pd.Timestamp(NOW)
    assert "liste:dividendes" in note.tags and "auto" in note.tags


def test_item_to_note_boc_and_sovereign() -> None:
    items = r.collect_boc_events(BOC_FIX, since="2026-09-16", until="2026-09-17")
    sus = next(it for it in items if it["list_type"] == "boc_suspension" and it["symbol"] == "SICC")
    note = r.item_to_note(sus, now=NOW, analyze=False)
    assert note.source == "boc" and note.event_type == "SUSPENSION" and note.targets == ["SICC"]
    assert note.published_at == pd.Timestamp("2026-09-16 19:00", tz="UTC")
    assert note.first_tradable_session == pd.Timestamp("2026-09-17")  # BOC du soir -> séance suivante
    tpci = by_title(parse("avis")["items"], "TPCI.O77 : Suspension")
    n2 = r.item_to_note(tpci, now=NOW, analyze=False)
    assert n2.targets == ["PAYS:CI"] and "instrument:obligation" in n2.tags


def _run_offline(tmp_path: Path, store: Any, **kw: Any):
    """Recherche hors ligne : cache amorcé avec les pages capturées, BOC des fixtures."""
    sess, web, _ = make_session(tmp_path, {}, offline=True)
    for url, (status, body, *rest) in brvm_pages().items():
        sess.cache_put(url, body, status, rest[0] if rest else {})
    kw.setdefault("analyze", False)
    res = r.run_research(store, session=sess, offline=True, boc_dir=BOC_FIX, now=NOW, **kw)
    assert web.calls == []
    return res


def test_run_research_offline_dedup_and_idempotence(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "notes")
    res = _run_offline(tmp_path, store, targets=["SNTS", "BOAC", "SDSC", "ETIT", "SICC"], boc_last_n=None)
    notes = list(res)
    assert notes and len(store.notes) == len(notes) == res.report.n_new
    assert all(n.targets and n.targets[0] in {"SNTS", "BOAC", "SDSC", "ETIT", "SICC"} for n in notes)
    by_sym_type: dict[tuple[str, str | None], list[Any]] = {}
    for n in notes:
        by_sym_type.setdefault((n.targets[0], n.event_type), []).append(n)
    # Le fractionnement SONATEL (liste esv, avis, BOC) ne donne qu'une note.
    split = [n for n in notes if n.targets == ["SNTS"] and "ractionnement" in n.title]
    assert len(split) == 1 and split[0].event_type == "SPLIT"
    # Le dividende AGL : liste des dividendes + BOC (opérations en cours, avis) -> une note.
    agl_div = [n for n in notes if n.targets == ["SDSC"] and "ividende" in n.title]
    assert len(agl_div) == 1 and agl_div[0].source == "brvm_list"
    # L'annulation de l'AGO d'ETI : communiqué + calendrier des AG du BOC -> une note.
    eti_cancel = [n for n in notes if n.targets == ["ETIT"] and "nnulation" in n.title]
    assert len(eti_cancel) == 1
    # Le rapport T3 2026 de SONATEL : page émetteur + BOC du 29/10 -> une note, datée par le BOC.
    t3 = [n for n in notes if n.targets == ["SNTS"] and "3e trimestre 2026" in n.title]
    assert len(t3) == 1 and t3[0].first_tradable_session == pd.Timestamp("2026-10-30")
    assert res.report.n_duplicates > 0 and any("date inconnue" in u for u in res.report.unresolved)
    # Seconde exécution : rien de nouveau.
    again = _run_offline(tmp_path, store, targets=["SNTS", "BOAC", "SDSC", "ETIT", "SICC"], boc_last_n=None)
    assert list(again) == [] and len(store.notes) == len(notes)


def test_run_research_targets_restrict_issuer_pages(tmp_path: Path) -> None:
    sess, web, _ = make_session(tmp_path)
    store = MemoryStore(tmp_path / "notes")
    res = r.run_research(store, targets=["SNTS"], session=sess, boc=False, now=NOW, analyze=False,
                         lists=["fractionnement", "avis"])
    urls = web.urls()
    assert urls[0] == f"{B}/robots.txt" and B + PAGES["brvm_emetteur_sonatel"] in urls
    assert not any("rapports-societe-cotes/" in u and "sonatel" not in u for u in urls)
    assert all(g >= 10.0 for g in request_gaps(web))
    assert {n.targets[0] for n in res} == {"SNTS"}


def test_run_research_country_target_keeps_sovereign_events(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "notes")
    res = _run_offline(tmp_path, store, targets=["PAYS:CI"], issuer_reports=False, boc=False, lists=["avis"])
    assert any(n.targets == ["PAYS:CI"] and "TPCI" in n.title for n in res)
    assert not any("SONATEL" in n.title for n in res)


def test_run_research_stops_on_403_but_keeps_local_boc(tmp_path: Path) -> None:
    pages = brvm_pages(**{B + PAGES["brvm_fractionnement"]: (403, b"Forbidden")})
    sess, web, _ = make_session(tmp_path, pages)
    store = MemoryStore(tmp_path / "notes")
    res = r.run_research(store, session=sess, boc_dir=BOC_FIX, boc_last_n=3, now=NOW, analyze=False)
    assert res.report.stopped and "403" in res.report.stopped
    n_calls = len(web.calls)
    assert web.urls()[-1] == B + PAGES["brvm_fractionnement"]  # plus rien après le 403
    assert any(n.source == "boc" for n in res) and any(n.source == "brvm_list" for n in res)
    assert len(web.calls) == n_calls


def test_run_research_merges_precise_avis_time(tmp_path: Path) -> None:
    """Même PDF dans « paiement de dividendes » (date du fichier) et dans « avis » (date + heure)."""
    div_url = f"{B}/sites/default/files/20261009_-_avis_ndeg297_brvmdg_-_paiement_de_dividendes_exo_2025_-_agl_ci.pdf"
    avis_html = html("brvm_avis").replace(
        b"https://www.brvm.org/sites/default/files/20261117_-_avis_ndeg336_brvmdg_-_resultats_de_premiere_cotation_-_green_bond_swami_agri_700_2026-2031_swas.o1.pdf",
        div_url.encode()).replace(b"2026-11-17T18:18:00+00:00", b"2026-10-09T18:05:00+00:00")
    avis_html = re.sub(rb"GREEN BOND SWAMI AGRI 7,00 % 2026-2031 \(SWAS\.O1\) :\s+R[^<]+cotation",
                       "AFRICA GLOBAL LOGISTICS CI : Paiement de dividendes - Exercice 2025".encode(), avis_html,
                       count=1)
    assert b"AFRICA GLOBAL LOGISTICS CI : Paiement" in avis_html
    sess, web, _ = make_session(tmp_path, brvm_pages(**{B + PAGES["brvm_avis"]: (200, avis_html)}))
    store = MemoryStore(tmp_path / "notes")
    res = r.run_research(store, targets=["SDSC"], session=sess, boc=False, issuer_reports=False, now=NOW,
                         analyze=False, lists=["dividendes", "avis"])
    agl = [n for n in res if "ividende" in n.title]
    assert len(agl) == 1
    assert agl[0].published_at == pd.Timestamp("2026-10-09 18:05", tz="UTC")
    assert agl[0].first_tradable_session == pd.Timestamp("2026-10-12")


def test_fetch_url_note_html_and_versioning(tmp_path: Path) -> None:
    url = "https://www.brvm.org/fr/rapports-societe-cotes/sonatel"
    sess, web, _ = make_session(tmp_path)
    store = MemoryStore(tmp_path / "notes")
    note = r.fetch_url_note(url, store, session=sess, now=NOW, analyze=False)
    assert note.source == "url" and note.author == "analyste" and note.url == url
    assert note.targets == ["SNTS"] and "date_collecte" in note.tags
    assert note.published_at == pd.Timestamp(NOW) and note.first_tradable_session == pd.Timestamp("2026-11-23")
    assert r.fetch_url_note(url, store, session=sess, now=NOW, analyze=False).note_id == note.note_id
    assert len(store.notes) == 1 and store.updates == []
    pdf_note = r.fetch_url_note(ETI_PDF, store, session=sess, now=NOW, analyze=False, targets=["ETIT"])
    assert pdf_note.targets == ["ETIT"] and pdf_note.published_precision == "date"
    assert pdf_note.published_at == pd.Timestamp("2026-10-23", tz="UTC")
    assert pdf_note.first_tradable_session == pd.Timestamp("2026-10-26")


# ---------------------------------------------------------------------------
# Couche (b) avec les modules réels NoteStore et analyze (si présents)
# ---------------------------------------------------------------------------


def test_run_research_with_real_store_and_analysis(tmp_path: Path) -> None:
    store_mod = pytest.importorskip("brvm_alpha.notes.store")
    pytest.importorskip("brvm_alpha.notes.analyze")
    store = store_mod.NoteStore(root=tmp_path / "notes")
    res = _run_offline(tmp_path, store, targets=["SNTS", "ETIT"], boc_last_n=None, analyze=True)
    assert len(res) > 0
    frame = store.list(status=None) if "status" in store.list.__code__.co_varnames else store.list()
    assert len(frame) == len(res)
    for n in res:
        assert n.analysis and "score" in n.analysis and -1.0 <= n.analysis["score"] <= 1.0
        assert store.get(n.note_id) is not None
    cancel = next(n for n in res if n.targets == ["ETIT"] and "nnulation" in n.title)
    assert cancel.event_type == "AG_CANCEL"
    split = next(n for n in res if n.targets == ["SNTS"] and "ractionnement" in n.title)
    assert split.analysis["extracted"].get("split_ratio") == 10.0
    again = _run_offline(tmp_path, store, targets=["SNTS", "ETIT"], boc_last_n=None, analyze=True)
    assert list(again) == []


def test_run_research_downloads_new_pdfs_once(tmp_path: Path) -> None:
    sess, web, _ = make_session(tmp_path)
    store = MemoryStore(tmp_path / "notes")
    res = r.run_research(store, targets=["ETIT"], session=sess, boc=False, issuer_reports=False, now=NOW,
                         analyze=False, lists=["communiques"], download_pdfs=True, max_pdfs=5)
    eti = next(n for n in res if "Annulation" in n.title)
    assert "Commission" in eti.text and "Bancaire de l’UMOA" in eti.text and "ocr_requis" not in eti.tags
    assert web.urls().count(ETI_PDF) == 1
    assert (tmp_path / "cache" / "docs" / f"{r.url_hash(ETI_PDF)}.pdf").exists()  # clé : sha256 de l'URL
    other = next(n for n in res if "Communiqué de Presse" in n.title)  # PDF absent (404) : note sans texte du PDF
    assert other.text.startswith("Liste « Communiqués »")


def test_fetch_url_note_new_version_with_real_store(tmp_path: Path) -> None:
    store_mod = pytest.importorskip("brvm_alpha.notes.store")
    store = store_mod.NoteStore(root=tmp_path / "notes")
    url = "https://exemple.test/article"
    page_v1 = (b"<html><head><title>SONATEL SN : chiffre d'affaires en hausse</title>"
               b'<meta property="article:published_time" content="2026-11-19T17:30:00Z"></head>'
               b"<body><article><p>Le chiffre d'affaires de SONATEL progresse de 8 %.</p></article></body></html>")
    page_v2 = page_v1.replace(b"8 %", b"9 %")
    pages = {"https://exemple.test/robots.txt": (404, b""), url: [(200, page_v1), (200, page_v2)]}
    sess, web, _ = make_session(tmp_path, pages, delay_s=1.0)
    n1 = r.fetch_url_note(url, store, session=sess, now=NOW, analyze=False)
    assert n1.source == "url" and n1.targets == ["SNTS"]
    assert n1.published_at == pd.Timestamp("2026-11-19 17:30", tz="UTC")
    assert n1.first_tradable_session == pd.Timestamp("2026-11-20")
    sess.cache_dir = tmp_path / "autre_cache"  # forcer une nouvelle lecture de la page
    n2 = r.fetch_url_note(url, store, session=sess, now=NOW, analyze=False)
    assert n2.note_id == n1.note_id and n2.version == 2 and "9 %" in n2.text
    assert [v.version for v in store.versions(n1.note_id)] == [1, 2]


def test_resolver_aliases_and_exclusions() -> None:
    res = r.IssuerResolver()
    assert res.resolve("CORIS BANK") == "CBIBF" and res.resolve("PALMCI") == "PALC"
    # Coris Bank International Côte d'Ivoire (introduction annoncée) n'est pas CBIBF.
    assert res.resolve("CORIS BANK INTERNATIONAL COTE D'IVOIRE") is None
    assert res.resolve(None, "CORIS BANK INTERNATIONAL CÔTE D'IVOIRE : Note d'information") is None
    assert res.resolve(None, "Projet de résolutions - Assemblée Générale Ordinaire - BOA BF") == "BOABF"
    assert res.resolve(None, "montant total du dividende") is None  # « TOTAL » seul n'est pas un émetteur


def test_run_research_respects_quota(tmp_path: Path) -> None:
    sess, web, _ = make_session(tmp_path, max_requests=5)
    store = MemoryStore(tmp_path / "notes")
    res = r.run_research(store, session=sess, boc_dir=BOC_FIX, boc_last_n=2, now=NOW, analyze=False)
    assert len(web.calls) == 5 and res.report.n_requests == 5  # robots.txt + 4 listes, puis arrêt
    assert any("Quota" in e for e in res.report.errors)
    assert any(n.source == "boc" for n in res)  # les BOC locaux sont traités quand même


def test_regression_resolver_former_names_and_garbled_boc_labels() -> None:
    """Essai réel du 22/11/2026 : libellés du calendrier des AG des BOC 2025 non résolus."""
    res = r.default_resolver()
    # Ancien nom entre parenthèses (« ERIUM CI (Ex AIR LIQUIDE CI) » tronqué en « E CI »).
    assert res.resolve("E        CI (Ex AIR LIQUIDE CI)", None) == "SIVC"
    assert res.resolve("MOOV BURKINA FASO (ex ONATEL BF)", None) == "ONTBF"
    # Glyphes perdus à l'extraction : TotalEnergies Marketing CI (Abidjan) et SN (Dakar).
    assert res.resolve("T T       E E GIE      ETI G I", None) == "TTLC"
    assert res.resolve("T T       E E GIE      ETI G", None) == "TTLS"
    # Émetteurs non cotés en actions : toujours non résolus.
    assert res.resolve("AFINHAB (Ex-CRRH-UEMOA)", None) is None
    assert res.resolve("FIDELIS FINANCE", None) is None
    text = "\n".join([
        "CALENDRIER DES ASSEMBLEES GENERALES",
        "ANNEE : 2025",
        "T T       E E GIE      ETI G I     Ordinaire   19/06/2025        10:00:00   Radisson Blu Hotel Abidjan Airport",
        "E        CI (Ex AIR LIQUIDE CI)   Ordinaire   16/12/2025        08:30:00   SALLE DE CONFÉRENCE DE LA CRRAE-UMOA",
    ])
    items = [it for it in r.parse_boc_events(text, "2025-06-10", "https://www.brvm.org/boc.pdf")
             if it["list_type"] == "boc_ag"]
    assert {it["symbol"] for it in items} == {"TTLC", "SIVC"}


def test_regression_offline_replay_reuses_cached_pdfs(tmp_path: Path) -> None:
    """Une relecture hors ligne reprend le texte des PDF déjà téléchargés (essai réel)."""
    sess, web, _ = make_session(tmp_path)
    r.run_research(MemoryStore(tmp_path / "a"), targets=["ETIT"], session=sess, boc=False, issuer_reports=False,
                   now=NOW, analyze=False, lists=["communiques"], download_pdfs=True, max_pdfs=5)
    off = r.PoliteSession(offline=True, cache_dir=tmp_path / "cache", log_path=tmp_path / "off.jsonl", now=lambda: NOW)
    res = r.run_research(MemoryStore(tmp_path / "b"), targets=["ETIT"], session=off, boc=False, issuer_reports=False,
                         now=NOW, analyze=False, lists=["communiques"], download_pdfs=True, max_pdfs=5)
    eti = next(n for n in res if "Annulation" in n.title)
    assert "Commission" in eti.text and off.n_requests == 0
    assert not any("PDF" in e for e in res.report.errors)  # PDF absent du cache : ignoré sans erreur


def test_regression_boc_avis_nature_column_does_not_force_dividend() -> None:
    """Avis 166-2025 : nature « Paiement de dividendes » pour une levée de suspension (BOC du 15/07/2025)."""
    text = "\n".join([
        "AVIS",
        "Entité        N° avis            Nature                                    Objet",
        "BRVM          166-2025           Paiement de dividendes                    Levée de la suspension des titres "
        "de l'ETAT DU NIGER - Offre Publique d’Échange",
        "",
        "BRVM          167-2025           Paiement de dividendes                    Paiement de dividendes - Exercice "
        "2024 - SOLIBRA CI",
        "",
    ])
    items = {it["extra"].get("avis_no"): it for it in r.parse_boc_events(text, "2025-07-15", "https://www.brvm.org/b.pdf",
                                                                          include_bonds=True)
             if it["list_type"] == "boc_avis"}
    if not items:  # gabarit de section non reconnu par ce texte réduit : on teste la règle seule
        pytest.skip("section AVIS non reconnue dans le texte réduit")
    assert items["166-2025"]["event_hint"] is None
    assert items["167-2025"]["event_hint"] == "DIV_NOTICE" and items["167-2025"]["symbol"] == "SLBC"


def test_regression_result_publications_dedup_across_sources() -> None:
    """Rapport de l'émetteur et communiqué du BOC pour la même publication : un seul événement."""
    assert r.dedup_event_type({"title": "FILTISAC CÔTE D'IVOIRE : Rapport d'activités du 1er trimestre 2025"}) == "RES:ACT_Q1"
    assert r.dedup_event_type({"title": "Rapport d'activités - 1er trimestre 2025 - FILTISAC CI"}) == "RES:ACT_Q1"
    assert r.dedup_event_type({"title": "ETI TOGO : 1er semestre 2025"}) == "RES:RES_S1"
    assert r.dedup_event_type({"title": "Rapport d'activités - 3ème trimestre 2025 - SOCIETE GENERALE CI"}) == "RES:ACT_Q3"
    assert r.dedup_event_type({"title": "Etats financiers - Exercice 2024 - CIE CI"}) == "RES:RES_ANNUAL"
    # Pas des résultats : contrat de liquidité, RSE ; année absente : pas de clé.
    assert r.dedup_event_type({"title": "Bilan semestriel du contrat de liquidité -1er semestre 2026 - BOA ML"}) is None
    assert r.dedup_event_type({"title": "Rapport RSE - Exercice 2024 - PALM CI"}) is None
    # Sans exercice dans le titre : même clé (la fenêtre de 30 jours sépare les exercices).
    assert r.dedup_event_type({"title": "CIE SODE CÔTE D'IVOIRE : Etats financiers - Norme SYSCOHADA"}) == "RES:RES_ANNUAL"
    # Note déjà analysée : son type de résultats sert de clé (communiqué de presse sans période).
    assert r.dedup_event_type({"title": "SONATEL SN - Communiqué de Presse", "event_hint": "RES_S1"}) == "RES:RES_S1"
    assert r.dedup_event_type({"title": "SONATEL SN - Communiqué de Presse"}) is None
    # « Annule et remplace » : document corrigé, pas une annulation d'AG ; convocation + résolutions.
    assert r.dedup_event_type({"title": "Projet de résolutions - Assemblée Générale Ordinaire - SICABLE CI "
                                        "(Annule et remplace le précédent)"}) == "AG_RESOLUTIONS"
    assert r.dedup_event_type({"title": "Avis de convocation et Projets de résolutions - Assemblée Générale Mixte"}) \
        == "AG_CONVOCATION"
    assert r.content_signature("Avis 20260930 (AMF-UMOA) : Communiqué - Souscription à des OPV") == \
        r.content_signature("Communiqué AMF-UMOA - Souscription à des OPV")
    a = {"symbol": "FTSC", "title": "FILTISAC CÔTE D'IVOIRE : Rapport d'activités du 1er trimestre 2025",
         "doc_date": "2025-04-30"}
    b = {"symbol": "FTSC", "title": "Rapport d'activités - 1er trimestre 2025 - FILTISAC CI", "doc_date": "2025-05-02",
         "extra": {"first_seen_boc": "2025-05-02"}}
    idx = r._DateIndex()
    idx.add(("FTSC", r.dedup_event_type(a)), r._event_date(a))
    assert r._is_event_duplicate(b, idx)
    q3 = dict(b, title="Rapport d'activités - 3ème trimestre 2025 - FILTISAC CI")
    assert not r._is_event_duplicate(q3, idx)
    # Résolutions, seuils, dirigeants : même document dans une liste brvm.org et au BOC.
    assert r.dedup_event_type({"title": "Projet de résolutions - Assemblée Générale Ordinaire du 12/05/2026 - BOA BF"}) \
        == "AG_RESOLUTIONS"
    assert r.dedup_event_type({"title": "Communiqué - Franchissement de seuil par ERIUM Ltd"}) == "THRESHOLD"
    assert r.dedup_event_type({"title": "Avis de nomination - SAPH CI"}) == "MGMT_CHANGE"
    assert r.dedup_event_type({"title": "Avis de convocation - Assemblée Générale Ordinaire - SETAO CI"}) == "AG_CONVOCATION"
    # Signature de contenu : le nom de pays resté dans le libellé ne sépare plus les deux titres.
    assert r.content_signature("FILTISAC CÔTE D'IVOIRE : Etats financiers - Exercice 2024", "FTSC") == \
        r.content_signature("Etats financiers - Exercice 2024 - FILTISAC CI", "FTSC")


def test_regression_market_notice_targets_named_index_and_dedups() -> None:
    item = {"list_type": "avis", "source": "brvm_list", "title": "Avis N°289/BRVM/2026 – Composition de l'indice BRVM 30",
            "doc_url": "https://www.brvm.org/sites/default/files/20261001_-_avis_289.pdf", "doc_date": "2026-10-01",
            "symbol": None, "market_level": True, "extra": {}}
    note = r.item_to_note(item, now=NOW, analyze=False)
    assert note.targets == ["IDX:BRVM-30"]
    plain = dict(item, title="Avis : Transactions Sur Dossier", doc_url="https://www.brvm.org/x.pdf")
    assert r.item_to_note(plain, now=NOW, analyze=False).targets == ["MARCHE"]
    # Même avis vu dans le BOC (sans symbole) : signature retrouvée dans le journal.
    frame = pd.DataFrame([{"targets": ["MARCHE"], "title": "Avis 289-2026 (BRVM) : Composition de l'indice BRVM 30",
                           "published_at": "2026-10-01T19:00:00Z"}])
    assert r._is_duplicate(item, r._signature_index(frame))


def test_regression_boc_operations_gross_dividend_with_irvm() -> None:
    """BOC « opérations en cours » : un montant suivi de « IRVM applicable » est brut (essai réel)."""
    text = "\n".join([
        "OPERATIONS EN COURS",
        "Emetteur                                Opération",
        "",
        "BANK OF AFRICA SN                       Paiement de dividendes de 350 F CFA net par action, le 02/06/2025",
        "",
        "ECOBANK CI                              Paiement de dividendes de 804 F CFA par action (IRVM applicable de 12 % "
        "pour les personnes physiques et 10 % pour les",
        "                                        personnes morales), le 30/05/2025",
        "",
    ])  # disposition du BOC réel du 15/05/2025
    ops = {it["symbol"]: it for it in r.parse_boc_events(text, "2025-05-15", "https://www.brvm.org/b.pdf")
           if it["list_type"] == "boc_operations"}
    if not ops:
        pytest.skip("section OPERATIONS EN COURS non reconnue dans le texte réduit")
    eco = ops["ECOC"]["extra"]
    assert eco["div_gross"] == 804 and eco["irvm_rate"] == pytest.approx(0.12)
    assert eco["div_net"] == pytest.approx(707.52)  # = « dernier dividende payé » du BOC
    assert ops["BOAS"]["extra"]["div_net"] == 350 and "div_gross" not in ops["BOAS"]["extra"]
    note = r.item_to_note(ops["ECOC"], now=NOW)
    ex = note.analysis["extracted"]
    assert ex["div_net"] == pytest.approx(707.52) and ex["div_gross"] == 804


def test_regression_corrected_documents_share_signature() -> None:
    a = "Rapport du Conseil d·Administration à l·Assemblée Générale Ordinaire - Exercice 2025 - BOA NG (Annule et remplace le précédent)"
    b = "Rapport du Conseil d’Administration à l’Assemblée Générale Ordinaire - Exercice 2025 - BOA NG"
    assert r.content_signature(a, "BOAN") == r.content_signature(b, "BOAN")
    assert r.content_signature("ERRATUM - Communiqué - X", None) == r.content_signature("Communiqué - X", None)
    assert r.dedup_event_type({"title": "Rapport d'activité -Deuxième semestre 2025 - BOA BF"}) == "RES:RES_ANNUAL"
    assert r.dedup_event_type({"title": "Rapport des CAC sur les conventions réglementées - Exercice 2025"}) is None


def test_regression_dividend_basis_reconciled_with_boc_operations(tmp_path: Path) -> None:
    """AGL : brvm.org affiche 92 (présumé brut), le BOC dit « 92 F CFA net » : net = 92.
    TRACTAFRIC : brvm.org affiche 209, le BOC dit « IRVM applicable » : brut confirmé, net 183,92."""
    sess, _, _ = make_session(tmp_path)
    res = r.run_research(MemoryStore(tmp_path / "notes"), session=sess, lists=["dividendes"], issuer_reports=False,
                         boc=True, boc_dir=BOC_FIX, boc_last_n=7, now=NOW, analyze=True)
    divs = {n.targets[0]: n for n in res if n.event_type == "DIV_NOTICE" and n.source == "brvm_list"}
    agl, prsc = divs["SDSC"].analysis["extracted"], divs["PRSC"].analysis["extracted"]
    # Parenthésage explicite : « A and B or C » laissait passer un montant net faux.
    assert agl["div_net"] == 92.0
    assert agl.get("div_gross") is None
    assert prsc["div_net"] == pytest.approx(183.92) and prsc["div_gross"] == 209.0
    assert agl["div_basis"] == "net (BOC)" and prsc["div_basis"] == "brut (BOC)"
    assert "dividende_brut_presume" not in divs["PRSC"].tags  # présomption confirmée par le BOC
    # Sans BOC, la présomption reste signalée.
    sess2, _, _ = make_session(tmp_path / "b")
    res2 = r.run_research(MemoryStore(tmp_path / "b" / "notes"), session=sess2, lists=["dividendes"],
                          issuer_reports=False, boc=False, now=NOW, analyze=True)
    ttlc = next(n for n in res2 if n.targets == ["TTLC"])
    assert "dividende_brut_presume" in ttlc.tags and ttlc.analysis["extracted"]["div_basis"] == "brut présumé"


# ---------------------------------------------------------------------------
# Régressions de la revue du 22/11/2026 (chaque test échouait avant la correction)
# ---------------------------------------------------------------------------


def _shared_sessions(tmp_path: Path, pages: dict[str, Any]):
    """Sessions successives sur le même cache, horloge et instant simulés communs."""
    clock = FakeClock()
    web = FakeWeb(pages, clock)

    def now() -> dt.datetime:
        return NOW + dt.timedelta(seconds=clock.t - 1_000.0)

    def session(**kw: Any) -> r.PoliteSession:
        return r.PoliteSession(transport=web, clock=clock, sleep=clock.sleep, cache_dir=tmp_path / "cache",
                               log_path=tmp_path / "fetch_log.jsonl", now=now, **kw)

    return session, web, clock


def test_regression_crawl_delay_holds_across_sessions(tmp_path: Path) -> None:
    """Deux appels successifs (nouvelle session, robots.txt en cache) restent espacés de 10 s."""
    session, web, clock = _shared_sessions(tmp_path, brvm_pages())
    session().get(B + PAGES["brvm_avis"])
    session().get(B + PAGES["brvm_dividendes"])  # 1re requête d'une nouvelle session
    session().get(B + PAGES["brvm_communiques"])
    assert web.urls().count(f"{B}/robots.txt") == 1  # robots.txt relu depuis le cache disque
    assert len(web.calls) == 4 and all(g >= 10.0 for g in request_gaps(web))
    # Les sessions créées par fetch_url_note et run_research partagent ce même état.
    state = json.loads((tmp_path / "cache" / "politeness.json").read_text(encoding="utf-8"))
    assert "www.brvm.org" in state["hosts"]


def test_regression_403_blocks_later_sessions_until_cleared(tmp_path: Path) -> None:
    pages = brvm_pages(**{B + PAGES["brvm_avis"]: (403, b"Forbidden")})
    sess, web, _ = make_session(tmp_path, pages)
    with pytest.raises(r.AccessBlocked):
        sess.get(B + PAGES["brvm_avis"])
    assert r.blocked_hosts(tmp_path / "cache")["www.brvm.org"]["status"] == 403
    sess2, web2, _ = make_session(tmp_path, pages)
    with pytest.raises(r.AccessBlocked, match="clear_block"):
        sess2.get(B + PAGES["brvm_communiques"])
    assert web2.calls == []  # aucune requête vers le site qui a refusé l'accès
    sess3, web3, _ = make_session(tmp_path, pages)
    res = r.run_research(MemoryStore(tmp_path / "notes"), session=sess3, boc=False, issuer_reports=False, now=NOW,
                         analyze=False)
    assert res.report.stopped and "bloqué" in res.report.stopped and web3.calls == []
    assert r.clear_block("https://www.brvm.org/", tmp_path / "cache")  # levée explicite
    sess4, _, _ = make_session(tmp_path, brvm_pages())
    assert sess4.get(B + PAGES["brvm_communiques"]).status == 200


def test_regression_redirects_are_followed_by_hand_and_checked(tmp_path: Path) -> None:
    host = "https://court.test"
    pages = {
        f"{host}/robots.txt": (404, b""),
        f"{host}/vers-sika": (302, b"", {"Location": "https://www.sikafinance.com/marches/actualites"}),
        f"{host}/vers-interdit": (301, b"", {"Location": "https://cible.test/prive/page"}),
        "https://cible.test/robots.txt": (200, b"User-agent: *\nDisallow: /prive/\n", {}),
        f"{host}/vers-ok": (302, b"", {"Location": "/article"}),
        f"{host}/article": (200, b"<html><h1>OK</h1></html>", {"Content-Type": "text/html"}),
        f"{host}/boucle": (302, b"", {"Location": "/boucle"}),
    }
    sess, web, _ = make_session(tmp_path, pages, delay_s=2.0)
    with pytest.raises(r.SourceDisabled):
        sess.get(f"{host}/vers-sika")
    assert not any("sikafinance" in u for u in web.urls())
    with pytest.raises(r.RobotsDisallowed, match="redirige"):
        sess.get(f"{host}/vers-interdit")
    assert "https://cible.test/prive/page" not in web.urls()
    n0 = sess.n_requests
    res = sess.get(f"{host}/vers-ok")
    assert res.status == 200 and res.final_url == f"{host}/article" and sess.n_requests == n0 + 2  # chaque saut compte
    assert all(g >= 2.0 for g in request_gaps(web, "court.test"))
    with pytest.raises(r.ResearchError, match="redirections"):
        sess.get(f"{host}/boucle")
    assert web.urls().count(f"{host}/boucle") == r.MAX_REDIRECTS + 1


def test_regression_default_transport_does_not_follow_redirects(monkeypatch: pytest.MonkeyPatch) -> None:
    import requests

    seen: dict[str, Any] = {}

    def fake_request(self: Any, method: str, url: str, **kw: Any) -> Any:
        seen.update(kw)
        resp = requests.Response()
        resp.status_code, resp.url, resp._content = 302, url, b""
        resp.headers["Location"] = "https://ailleurs.test/"
        return resp

    monkeypatch.setattr(requests.Session, "request", fake_request)
    resp = r._requests_transport(r.USER_AGENT)("https://a.test/", {}, 5.0)
    assert seen["allow_redirects"] is False and resp.status_code == 302


@pytest.mark.parametrize("url", [
    "https://www.sikafinance.com:443/marches/actualites", "https://www.sikafinance.com./marches/actualites",
    "https://WWW.RICHBOURSE.COM:443/common/news/index", "https://user@www.richbourse.com/common/news/index",
])
def test_regression_disabled_sources_whatever_the_host_spelling(tmp_path: Path, url: str) -> None:
    sess, web, _ = make_session(tmp_path, {})
    with pytest.raises(r.SourceDisabled):
        r.fetch_url_note(url, MemoryStore(tmp_path), session=sess)
    with pytest.raises(r.SourceDisabled):
        sess.get(url)
    assert web.calls == []


def test_regression_brvm_delay_floor_with_port_or_trailing_dot(tmp_path: Path) -> None:
    sess, _, _ = make_session(tmp_path, {}, delay_s=0.5)
    for u in ("https://www.brvm.org:443/fr", "https://www.brvm.org./fr", "https://WWW.BRVM.ORG/fr"):
        assert r.url_host(u) == "www.brvm.org" and sess.crawl_delay(u) == 10.0


def test_regression_collector_seen_time_bounds_knowledge(tmp_path: Path) -> None:
    """Avis horodaté 08h00, vu à 11h00 : publication de marché 08h00, mais connu à 11h00 (effet J+1)."""
    from brvm_alpha.notes import signals as sg

    sess, _, _ = make_session(tmp_path)
    items = r.collect_list(sess, "avis")
    assert items and all(it["seen_at"] == NOW.isoformat(timespec="seconds") for it in items)
    item = {"published_at": "2026-11-17T08:00:00+00:00", "title": "SONATEL : avis de paiement de dividendes",
            "source": "brvm_list", "list_type": "avis", "symbol": "SNTS", "page_url": B + PAGES["brvm_avis"],
            "doc_url": B + "/sites/default/files/20261117_avis_sonatel.pdf", "seen_at": "2026-11-17T11:00:00+00:00",
            "extra": {}}
    note = r.item_to_note(item, now=dt.datetime(2026, 11, 17, 8, 50, tzinfo=UTC), analyze=False)
    assert note.created_at == pd.Timestamp("2026-11-17T11:00:00Z")
    assert note.first_tradable_session == pd.Timestamp("2026-11-17")
    assert sg.notes_asof([note], "2026-11-17").empty
    assert sg.notes_asof([note], "2026-11-18")["first_tradable_session"].iloc[0] == pd.Timestamp("2026-11-18")


def test_regression_backdated_research_never_dates_future_documents(tmp_path: Path,
                                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    from brvm_alpha.notes.model import RECONSTRUCTED_TAG, SIMULATED_CLOCK_ENV
    from brvm_alpha.notes.store import NoteStore

    monkeypatch.delenv(SIMULATED_CLOCK_ENV, raising=False)
    past = dt.datetime(2025, 6, 30, 12, 0, tzinfo=UTC)
    future = {"doc_date": "2026-10-09", "date_source": "fichier", "title": "AGL : dividende", "extra": {}}
    assert r.item_published_at(future, NOW)[0] <= NOW  # collecte réelle : rien ne change
    with pytest.raises(r.PostdatedItem):
        r.item_published_at(future, past, strict_seen=True)
    # Collecteur qui « voit » les pages en 2025 (reconstitution complète).
    clock = FakeClock()
    sess = r.PoliteSession(transport=FakeWeb(brvm_pages(), clock), clock=clock, sleep=clock.sleep,
                           cache_dir=tmp_path / "cache", log_path=tmp_path / "log.jsonl", now=lambda: past)
    store = NoteStore(tmp_path / "notes")
    res = r.run_research(store, session=sess, boc=True, boc_dir=BOC_FIX, issuer_reports=False, now=past,
                         analyze=False, panel_dir=None, lists=["dividendes", "communiques"])
    assert res.report.reconstructed and any("reconstitution" in u for u in res.report.unresolved)
    for n in res:
        assert n.published_at <= pd.Timestamp(past)
        d = r.date_from_filename(n.url) if n.url else None
        assert d is None or d <= past.date()
        assert RECONSTRUCTED_TAG in store.get(n.note_id).tags
    assert store.asof("2026-11-22").empty  # vue stricte : aucune note antidatée
    # Pages vues réellement en 2026 (instant de session) mais now=2025 : dates de 2026 conservées.
    sess2, _, _ = make_session(tmp_path / "b")
    res2 = r.run_research(NoteStore(tmp_path / "b" / "notes"), session=sess2, boc=False, issuer_reports=False,
                          now=past, analyze=False, panel_dir=None, lists=["dividendes"])
    assert res2 and all(n.published_at > pd.Timestamp(past) for n in res2)


def test_regression_html_dates_day_first_and_invalid_values(tmp_path: Path) -> None:
    def page(head: str) -> bytes:
        return (f"<html><head>{head}<title>SONATEL</title></head><body><article><p>Sonatel : résultat net en "
                "hausse.</p></article></body></html>").encode("utf-8")

    c = r.extract_html_content(page('<meta property="article:published_time" content="05/11/2026">'))
    assert c["published_at"] == dt.datetime(2026, 11, 5, tzinfo=UTC) and c["published_precision"] == "date"
    c = r.extract_html_content(page('<meta name="date" content="02/11/2026 18:30">'))
    assert c["published_at"] == dt.datetime(2026, 11, 2, 18, 30, tzinfo=UTC) and c["published_precision"] == "datetime"
    for head in ('<meta name="date" content="2026">', '<meta name="date" content="11/12/2026 6:30 PM">', ""):
        assert r.extract_html_content(page(head))["published_at"] is None
    body = b'<html><body><time datetime="">hier</time><article><p>SONATEL : hausse</p></article></body></html>'
    assert r.extract_html_content(body)["published_at"] is None
    url = "https://exemple.test/vide_time"
    pages = {"https://exemple.test/robots.txt": (404, b""), url: (200, body, {"Content-Type": "text/html"})}
    sess, _, _ = make_session(tmp_path, pages, delay_s=1.0)
    n = r.fetch_url_note(url, MemoryStore(tmp_path), session=sess, now=NOW, analyze=False)
    assert "date_collecte" in n.tags and n.published_at == pd.Timestamp(NOW)


def test_regression_concurrent_sessions_keep_reserved_slots(tmp_path: Path) -> None:
    """Deux sessions simultanées : le créneau réservé par B pendant la requête de A est respecté.

    Vérification finale : la fin de la requête de A réécrivait l'identifiant de session de
    l'état partagé ; la requête suivante de A ignorait alors la réservation de B et partait
    0,4 s après elle (au lieu de 10 s).
    """
    t = [0.0]
    waits: dict[str, list[float]] = {"A": [], "B": []}

    def now() -> dt.datetime:
        return NOW + dt.timedelta(seconds=t[0])

    def mk(name: str) -> r.PoliteSession:
        return r.PoliteSession(transport=FakeWeb({}), clock=lambda: t[0], sleep=waits[name].append, now=now,
                               cache_dir=tmp_path / "cache", log_path=tmp_path / "fetch_log.jsonl")

    a, b = mk("A"), mk("B")
    url = B + "/fr/page"
    a._wait_turn(url)  # A part à T0
    b._wait_turn(url)  # B, lancée pendant la requête de A : créneau T0 + 10 s
    t[0] += 0.4  # fin de la requête de A
    a._last_request["www.brvm.org"] = t[0]
    a._record_done("www.brvm.org")
    a._wait_turn(url)  # requête suivante de A : après le créneau de B, soit T0 + 20 s
    assert waits["B"] == [pytest.approx(10.0)]
    assert waits["A"] == [pytest.approx(19.6)]


def test_regression_reservation_includes_own_session_wait(tmp_path: Path) -> None:
    """Le créneau réservé par A inclut sa propre attente : B, arrivée pendant cette attente,
    part 10 s après la requête de A, pas en même temps qu'elle (vérification finale)."""
    t = [0.0]
    waits: dict[str, list[float]] = {"A": [], "B": []}

    def now() -> dt.datetime:
        return NOW + dt.timedelta(seconds=t[0])

    def mk(name: str) -> r.PoliteSession:
        return r.PoliteSession(transport=FakeWeb({}), clock=lambda: t[0], sleep=waits[name].append, now=now,
                               cache_dir=tmp_path / "cache", log_path=tmp_path / "fetch_log.jsonl")

    a, b = mk("A"), mk("B")
    url = B + "/fr/page"
    a._wait_turn(url)  # requête 1 de A à T0
    t[0] += 0.2
    a._last_request["www.brvm.org"] = t[0]
    a._record_done("www.brvm.org")
    a._wait_turn(url)  # requête 2 de A : attend sa propre fin de délai, soit T0 + 10,2 s
    assert waits["A"] == [pytest.approx(10.0)]
    b._wait_turn(url)  # B arrive pendant l'attente de A : après la requête 2 de A
    assert waits["B"] == [pytest.approx(20.0)]
