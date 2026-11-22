"""Tests du lecteur de cours en direct (page brvm.org enregistrée le 2026-11-21)."""

from pathlib import Path

from brvm_alpha.data.live import parse_live_html, parse_number

FIXTURE = Path(__file__).parent / "fixtures" / "brvm_cours_actions.html"


def test_parse_number():
    assert parse_number("12 737 890") == 12737890
    assert parse_number("-0,21% ") == -0.21
    assert parse_number("19 328 818 938 929 FCFA") == 19328818938929
    assert parse_number("NC") is None


def test_parse_live_page():
    snap = parse_live_html(FIXTURE.read_text(encoding="utf-8"))
    q = snap.quotes.set_index("symbol")
    assert len(q) >= 45
    assert q.loc["BBGC", "close"] == 8145
    assert q.loc["BBGC", "prev_close"] == 8150
    assert q.loc["BBGC", "volume"] == 9592
    assert q.loc["BBGC", "change_pct"] == -4.18
    assert snap.indices["BRVM-C"]["level"] == 492.89
    assert snap.indices["BRVM-C"]["change_pct"] == -0.21
    assert snap.activity["Capitalisation Actions"] == 19328818938929
