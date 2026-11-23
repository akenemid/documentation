"""Sous-blocs du module « Rendement net et pertes » dans le rapport HTML (cahier ``docs/RENDEMENT_NET.md``, §7.2,
§F1-11) : à la fin de six sections existantes, ``SECTIONS`` garde ses 11 entrées, tableaux dans ``tablewrap``,
bandeau dans chaque sous-bloc, section ``bandeau`` au statut ``ok`` même si la carte « Mon plan » échoue.

Panel synthétique (dates de S0 seulement) de ``tests/test_report_html.py`` ; dossiers temporaires ; aucune requête.
Performance passée ≠ garantie. Aucun gain n'est garanti.
"""

from __future__ import annotations

import re
import warnings

import pytest

from brvm_alpha.report import BANNER, SECTIONS, render_report
from brvm_alpha.report import html as RH
from brvm_alpha.report import rendement_net as RNR
from test_report_html import _registry, _synthetic

N_BOOT = 300
SOUS_BLOCS = ("bandeau", "ordre", "revenus", "distribution", "risques", "methode")


@pytest.fixture(scope="module")
def synth(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("rapport_rn")
    panels, long = _synthetic()
    pdir = tmp / "panel"
    pdir.mkdir()
    for name, df in long.items():
        df.to_parquet(pdir / f"{name}.parquet")
    return {"tmp": tmp, "panels": panels, "panel_dir": pdir, "t": panels["close"].index[-1],
            "reg": _registry(tmp / "trials_no.parquet", False)}


def _render(synth, **kw):
    base = dict(panels=synth["panels"], panel_dir=synth["panel_dir"], notes_root=synth["tmp"] / "pas_de_notes",
                validation_dir=synth["tmp"] / "absent", diagnostic_dir=synth["tmp"] / "absent_s0",
                registry_path=synth["reg"], n_boot=N_BOOT, seed=1,
                now=f"{synth['t']:%Y-%m-%d}T16:00:00Z")  # panel à jour : ordre non périmé, projection calculée
    base.update(kw)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return render_report(synth["t"], 10_000_000, **base)


@pytest.fixture(scope="module")
def rep(synth, tmp_path_factory):
    import brvm_alpha.paths as P

    # Lecture seule des journaux du suivi : un dossier de données vide (le bulletin dit « semaine 0 »).
    old = P.DATA_DIR
    P.DATA_DIR = tmp_path_factory.mktemp("donnees_vides")
    try:
        return _render(synth)
    finally:
        P.DATA_DIR = old


def _section(html: str, sid: str) -> str:
    a = html.index(f'<section id="{sid}"')
    b = html.find("<section id=", a + 10)
    return html[a:b if b > 0 else len(html)]


def _sous_bloc(html: str, sid: str) -> str:
    s = _section(html, sid)
    i = s.index(f'id="rn-{sid}"')
    return s[i:]


def test_sections_unchanged_all_ok_and_six_sub_blocks_at_the_end(rep):
    assert len(SECTIONS) == 11 and [r.id for r in rep.sections] == [s for s, _ in SECTIONS]
    assert all(r.statut == "ok" for r in rep.sections), [(r.id, r.statut, r.message) for r in rep.sections]
    h = rep.html
    assert re.findall(r'id="rn-(\w+)"', h) == list(SOUS_BLOCS)
    for sid in SOUS_BLOCS:
        s = _section(h, sid)
        i = s.index(f'id="rn-{sid}"')
        # À la fin de la section : rien de la section existante après le sous-bloc.
        assert s[i:].count("<h2") == 0 and RH.esc(BANNER) in s[i:], sid
    for sid in ("marche", "s1", "indices", "notes", "univers"):
        assert "rn-sous-bloc" not in _section(h, sid)


def test_sub_block_contents_and_tables_in_tablewrap(rep):
    h = rep.html
    own = re.sub(r'<section class="brvm-ordre-de-bataille".*?</section>', "", h, flags=re.DOTALL)
    assert own.count('<div class="tablewrap"><table') == own.count("<table")
    for sid in SOUS_BLOCS:
        b = _sous_bloc(h, sid)
        assert b.count('<div class="tablewrap"><table') == b.count("<table"), sid
    assert "Mon plan" in _sous_bloc(h, "bandeau") and "TROIS FEUX" in _sous_bloc(h, "bandeau").upper()
    o = _sous_bloc(h, "ordre")
    assert "Argent qui dort et provision" in o and "Passer l" in o and "c-rn-liquidites" in o
    r = _sous_bloc(h, "revenus")
    assert "Du brut au net" in r and "Frais évités par rapport au tarif supposé" in r and "Inconnues à lever" in r
    assert "gain ou perte selon le marché" in r
    assert "Lectures du risque" in _sous_bloc(h, "distribution")
    k = _sous_bloc(h, "risques")
    assert "Ce que j" in k and "BULLETIN DE LA SEMAINE" in k and "semaine 0" in k
    m = _sous_bloc(h, "methode")
    assert "Suivi sur papier : ce qui est déclaré" in m and "REF-S2" in m and "Un essai sur papier n" in m
    # Forme écran : la lecture flatteuse n'apparaît pas dans la carte du bandeau.
    assert "flatteuse" not in _sous_bloc(h, "bandeau").lower()


def test_bandeau_stays_ok_when_the_plan_card_fails(synth, monkeypatch):
    from brvm_alpha.rendement import plan as PL

    def panne(*a, **k):
        raise RuntimeError("carte en panne")

    monkeypatch.setattr(PL, "construire_plan", panne)
    r = _render(synth)
    st = {x.id: x.statut for x in r.sections}
    assert st["bandeau"] == "ok" and all(v == "ok" for v in st.values()), st
    assert "Carte « Mon plan » : non calculé" in _sous_bloc(r.html, "bandeau")


def test_a_module_failure_leaves_every_section_ok_without_sub_blocks(synth, monkeypatch):
    def panne(*a, **k):
        raise RuntimeError("module en panne")

    monkeypatch.setattr(RNR, "sous_bloc", panne)
    r = _render(synth)
    assert all(x.statut == "ok" for x in r.sections) and "rn-sous-bloc" not in r.html
    r2 = _render(synth, recommend_kwargs={"rendement": False})  # --sans-rendement : aucun sous-bloc
    assert all(x.statut == "ok" for x in r2.sections) and "rn-sous-bloc" not in r2.html
