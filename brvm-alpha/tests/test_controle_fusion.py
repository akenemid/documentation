"""Contrôle adverse de l'état fusionné ``a58b4c8`` : saisies du module « Rendement net et pertes » et contrat de la ligne
de commande (constats 5 à 15, 22 et 25).

- deux saisies lancées au même instant ne perdent rien et n'inscrivent rien deux fois (verrous du profil et du
  portefeuille) ;
- toute faute de saisie sort en code 2, jamais en 7 ni en 1, avec un seul objet JSON, et rien n'est écrit ;
- en mode embarqué, les liens symboliques ne mènent jamais hors des dossiers permis, en lecture comme en écriture ;
- une valeur vide n'est jamais remplacée sans le dire par un défaut.

Dossiers temporaires seulement ; aucune requête réseau ; aucune date de S1. Performance passée ≠ garantie. Aucun gain
n'est garanti.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path

import pytest

from brvm_alpha import cli, cli_rendement, fichiers
from brvm_alpha.suivi import carnet as CN
from test_cli_rendement import (_Ordre, donnees, embarque, fausse_reco, gardes_du_depot, horloge,  # noqa: F401
                                one_json, panel_suivi, rn10, run_cli)


def _lignes(data: Path, nom: str) -> list[dict]:
    c = CN.ouvrir(nom, data / "suivi", creer=False)
    return c.mouvements(actifs=False) if c.fichier.exists() else []


# ---------------------------------------------------------------------------
# Constat 5 : deux « suivi demarrer » au même instant
# ---------------------------------------------------------------------------


def test_two_simultaneous_starts_write_one_mandate_only(donnees, horloge, capsys, monkeypatch):
    """Avant : le contrôle « déjà démarré » se faisait hors du verrou ; deux lancements simultanés inscrivaient deux
    mandats et deux apports (liquidités cumulées). Le second démarrage arrive ici pendant le premier, entre son
    contrôle de départ et son ajout : il est refusé (2) et le carnet garde un seul mandat."""
    data, _ = donnees
    vrai = cli_rendement.lire_plan
    vu: list[int] = []

    def autre_demarrage(*a, **k):
        if not vu:
            vu.append(1)
            code, _out, _err = run_cli(capsys, "suivi", "demarrer", "--nom", "E-X", "--capital", "2M", "--format",
                                       "json")
            assert code == 0
        return vrai(*a, **k)

    monkeypatch.setattr(cli_rendement, "lire_plan", autre_demarrage)
    code, out, _ = run_cli(capsys, "suivi", "demarrer", "--nom", "E-X", "--capital", "1M", "--format", "json")
    assert code == 2 and "déjà démarré" in one_json(out)["message"]
    assert [(m["type"], m.get("capital", m.get("montant"))) for m in _lignes(data, "E-X")] == [
        ("mandat", 2_000_000.0), ("apport", 2_000_000.0)]


# ---------------------------------------------------------------------------
# Constat 6 : plan grille et plan --enregistrer sous le verrou du profil
# ---------------------------------------------------------------------------


@pytest.fixture()
def profil_tenu(donnees, monkeypatch):
    """Le verrou du profil tenu par un autre fil (une saisie lente en cours) ; attente courte."""
    monkeypatch.setenv(fichiers.ENV_ATTENTE, "0.3")
    pret, fin = threading.Event(), threading.Event()

    def tenir():
        with cli_rendement.verrou_profil(quoi="essai"):
            pret.set()
            fin.wait(10)

    t = threading.Thread(target=tenir)
    t.start()
    assert pret.wait(5)
    yield donnees
    fin.set()
    t.join(5)


def test_grid_and_plan_saves_wait_for_the_profile_lock(profil_tenu, fausse_reco, capsys):
    """Avant : aucun verrou ; deux saisies simultanées sortaient en 0 et la dernière écriture effaçait la valeur de
    l'autre. Pendant une autre saisie, la lecture, la fusion et l'écriture attendent le verrou : au-delà du délai, code
    4 et rien n'est écrit."""
    data, _ = profil_tenu
    code, out, _ = run_cli(capsys, "plan", "grille", "--garde", "0,4", "--format", "json")
    assert code == 4 and one_json(out)["erreur"] == "verrou_occupe"
    code, out, _ = run_cli(capsys, "plan", "--enregistrer", "--capital", "6M", "--besoin-dans", "24", "--sans-notes",
                           "--format", "json")
    assert code == 4 and one_json(out)["erreur"] == "verrou_occupe" and fausse_reco == []
    assert sorted(p.name for p in (data / "profil").iterdir()) == []  # rien d'écrit, aucun fichier de verrou


def test_grid_and_plan_saves_merge_with_the_last_saved_values(donnees, fausse_reco, capsys):
    data, _ = donnees
    assert run_cli(capsys, "plan", "grille", "--courtage", "0,95", "--format", "json")[0] == 0
    assert run_cli(capsys, "plan", "grille", "--garde", "0,4", "--format", "json")[0] == 0
    from brvm_alpha.rendement import grille as G

    g = G.charger(data / "profil")
    assert g.valeur("courtage") == pytest.approx(0.0095) and g.valeur("garde") == pytest.approx(0.004)
    assert run_cli(capsys, "plan", "--enregistrer", "--capital", "6M", "--perte-toleree", "1M", "--sans-notes")[0] == 0
    assert run_cli(capsys, "plan", "--enregistrer", "--capital", "6M", "--besoin-dans", "24", "--sans-notes")[0] == 0
    pe = cli_rendement.lire_plan(data / "profil")
    assert pe["perte_toleree"] == 1_000_000 and pe["besoin_dans_mois"] == 24
    # une saisie refusée ne crée rien, pas même le dossier du profil
    (data / "profil" / "grille_sgi.yaml").unlink()
    (data / "profil" / "plan.json").unlink()
    (data / "profil" / "plan_cache.json").unlink()
    (data / "profil").rmdir()
    assert run_cli(capsys, "plan", "grille", "--courtage", "9", "--format", "json")[0] == 2
    assert not (data / "profil").exists()


# ---------------------------------------------------------------------------
# Constats 7, 13 et 14 : fichiers de saisie illisibles, grille vide ou énorme
# ---------------------------------------------------------------------------


@pytest.fixture()
def reel(donnees, horloge, capsys):
    data, _ = donnees
    assert run_cli(capsys, "suivi", "demarrer", "--nom", "E-C", "--mode", "reel", "--format", "json")[0] == 0
    fx = data / "fx"
    fx.mkdir()
    (fx / "invalide.csv").write_bytes(b"date,symbole,sens,titres,prix\n2026-09-01,SNTS,achat,100,25000\xff\xfe\n")
    (fx / "dossier").mkdir()
    os.mkfifo(fx / "tube")
    return data


@pytest.mark.parametrize("fichier,mot", [("invalide.csv", "UTF-8"), ("dossier", "fichier ordinaire"),
                                         ("tube", "fichier ordinaire")])
def test_unreadable_trade_note_is_an_input_error(reel, capsys, fichier, mot):
    """Avant : texte non UTF-8 en 7 (erreur interne, avec une trace) ; dossier ou tube en 1 « introuvable »."""
    avant = _lignes(reel, "E-C")
    code, out, err = run_cli(capsys, "suivi", "saisir", "--nom", "E-C", "--fichier", str(reel / "fx" / fichier),
                             "--format", "json")
    assert code == 2 and mot in one_json(out)["message"] and "Traceback" not in err
    assert _lignes(reel, "E-C") == avant


@pytest.mark.parametrize("contenu,mot", [("", "grille vide"), ("# rien\n", "grille vide"), ("{}\n", "grille vide"),
                                         ("#" + "a" * 70_000 + "\n", "trop volumineux")])
def test_empty_or_huge_grid_file_is_refused_before_any_calculation(donnees, fausse_reco, capsys, tmp_path, contenu,
                                                                   mot):
    """Avant : fichier vide ou fait de commentaires accepté (tarif par défaut sous le nom « Ma grille ») ; aucune borne
    de taille (un YAML de 300 Mo occupait recommend 5 minutes)."""
    f = tmp_path / "grille.yaml"
    f.write_text(contenu, encoding="utf-8")
    for argv in (["plan", "--sans-notes"], ["recommend", "--capital", "10M", "--sans-notes"]):
        code, out, _ = run_cli(capsys, *argv, "--grille", str(f), "--format", "json")
        assert code == 2 and mot in one_json(out)["message"], argv
    assert fausse_reco == []


def test_grid_file_that_is_a_folder_or_a_pipe_is_an_input_error(reel, fausse_reco, capsys):
    for f in ("dossier", "tube"):
        code, out, _ = run_cli(capsys, "plan", "--sans-notes", "--grille", str(reel / "fx" / f), "--format", "json")
        assert code == 2 and "fichier ordinaire" in one_json(out)["message"], f
    assert fausse_reco == []


# ---------------------------------------------------------------------------
# Constats 8 et 9 : suivi exporter vers <R>, <T> ou un lien
# ---------------------------------------------------------------------------


@pytest.fixture()
def journaux(donnees, horloge, capsys):
    data, reports = donnees
    assert run_cli(capsys, "suivi", "demarrer", "--nom", "PLAN", "--format", "json")[0] == 0
    return data, reports


def test_export_never_replaces_the_reports_temporary_or_data_folder(journaux, capsys, monkeypatch, tmp_path):
    """Avant : « --sortie <R> » (ou « . ») sur un dossier vide remplaçait le dossier des rapports lui-même, et la copie
    temporaire était créée dans son parent, hors des dossiers permis."""
    data, reports = journaux
    tmpdir = tmp_path / "tmp_systeme"
    tmpdir.mkdir()
    monkeypatch.setattr("tempfile.tempdir", str(tmpdir))
    ino = reports.stat().st_ino
    parent_avant = sorted(p.name for p in reports.parent.iterdir())
    for sortie in (str(reports), str(tmpdir), str(data)):
        code, out, _ = run_cli(capsys, "suivi", "exporter", "--sortie", sortie, "--format", "json")
        assert code == 2 and "lui-même" in one_json(out)["message"], sortie
    assert reports.stat().st_ino == ino and not any(reports.iterdir()) and not any(tmpdir.iterdir())
    assert sorted(p.name for p in reports.parent.iterdir()) == parent_avant  # rien dans le parent


def test_embedded_export_to_dot_is_the_reports_folder_itself_and_is_refused(embarque, horloge, capsys):
    data, reports = embarque
    assert run_cli(capsys, "suivi", "demarrer", "--nom", "PLAN", "--format", "json")[0] == 0
    ino = reports.stat().st_ino
    code, out, _ = run_cli(capsys, "suivi", "exporter", "--sortie", ".", "--format", "json")
    assert code == 2 and "lui-même" in one_json(out)["message"]
    assert reports.stat().st_ino == ino and not any(reports.iterdir())
    assert not [p for p in reports.parent.iterdir() if p.name.endswith(".part")]


def test_export_to_a_symbolic_link_is_an_input_error(journaux, capsys, tmp_path):
    """Avant : lien vers un dossier vide extérieur, code 7 (NotADirectoryError, avec une trace)."""
    _data, reports = journaux
    dehors = tmp_path / "dehors_vide"
    dehors.mkdir()
    (reports / "lien").symlink_to(dehors)
    code, out, err = run_cli(capsys, "suivi", "exporter", "--sortie", str(reports / "lien"), "--format", "json")
    assert code == 2 and "lien symbolique" in one_json(out)["message"] and "Traceback" not in err
    assert not any(dehors.iterdir())


# ---------------------------------------------------------------------------
# Constats 10, 11 et 25 : liens symboliques en mode embarqué
# ---------------------------------------------------------------------------


@pytest.fixture()
def liens(embarque, tmp_path, monkeypatch):
    data, reports = embarque
    monkeypatch.setattr("tempfile.tempdir", str(tmp_path / "tmp_systeme"))
    (tmp_path / "tmp_systeme").mkdir()
    ext = tmp_path / "ext"
    (ext / "dir").mkdir(parents=True)
    (ext / "avis.csv").write_text("date,symbole,sens,titres,prix\n2026-09-02,SNTS,achat,7,25000\n", encoding="utf-8")
    (ext / "grille.yaml").write_text("nom: grille dehors\n", encoding="utf-8")
    (ext / "hors.txt").write_text("secret hors des dossiers\n", encoding="utf-8")
    (reports / "lien_dir").symlink_to(ext / "dir")
    (reports / "lien_absent.json").symlink_to(ext / "absent.json")
    (data / "fx").mkdir()
    (data / "fx" / "lien_avis.csv").symlink_to(ext / "avis.csv")
    (data / "fx" / "lien_grille.yaml").symlink_to(ext / "grille.yaml")
    (data / "fx" / "lien_texte.txt").symlink_to(ext / "hors.txt")
    (data / "fx" / "vrai.txt").write_text("texte dedans\n", encoding="utf-8")
    (data / "fx" / "lien_dedans.txt").symlink_to(data / "fx" / "vrai.txt")
    return data, reports, ext


def test_embedded_output_through_a_link_in_the_reports_folder_is_refused(liens, fausse_reco, horloge, panel_suivi,
                                                                         capsys):
    """Avant : plan, suivi bulletin, suivi exporter (et déjà recommend, report) écrivaient au bout d'un lien placé dans
    <R>, hors des dossiers permis."""
    data, reports, ext = liens
    assert run_cli(capsys, "suivi", "demarrer", "--nom", "MOI", "--format", "json")[0] == 0
    cas = [["plan", "--sans-notes", "--sortie", str(reports / "lien_dir" / "plan.json")],
           ["plan", "--sans-notes", "--sortie", str(reports / "lien_absent.json")],
           ["recommend", "--capital", "10M", "--sans-notes", "--sortie", str(reports / "lien_dir" / "ordre.json")],
           ["suivi", "bulletin", "--nom", "MOI", "--sortie", str(reports / "lien_dir" / "bulletin.json")],
           ["suivi", "exporter", "--sortie", str(reports / "lien_dir" / "exp_dehors")]]
    for argv in cas:
        code, out, _ = run_cli(capsys, *argv, "--format", "json")
        assert code == 2 and "hors des dossiers permis" in one_json(out)["message"], argv
    assert sorted(p.name for p in ext.iterdir()) == ["avis.csv", "dir", "grille.yaml", "hors.txt"]
    assert not any((ext / "dir").iterdir())
    # un fichier ordinaire de <R> reste permis
    code, out, _ = run_cli(capsys, "plan", "--sans-notes", "--sortie", str(reports / "plan.json"), "--format", "json")
    assert code == 0 and (reports / "plan.json").is_file()


def test_embedded_input_through_a_link_is_refused_and_nothing_is_written(liens, fausse_reco, horloge, capsys):
    """Avant : suivi saisir --fichier inscrivait pour toujours l'avis lu au bout d'un lien de <D> ; --grille et notes
    add --fichier lisaient un fichier extérieur (--titre-fichier était déjà refusé)."""
    data, _reports, _ext = liens
    assert run_cli(capsys, "suivi", "demarrer", "--nom", "E-C", "--mode", "reel", "--format", "json")[0] == 0
    avant = _lignes(data, "E-C")
    code, out, _ = run_cli(capsys, "suivi", "saisir", "--nom", "E-C", "--fichier", "fx/lien_avis.csv", "--format",
                           "json")
    assert code == 2 and "mène hors des dossiers permis" in one_json(out)["message"]
    assert _lignes(data, "E-C") == avant
    for argv in (["recommend", "--capital", "10M", "--sans-notes"], ["plan", "--sans-notes"]):
        code, out, _ = run_cli(capsys, *argv, "--grille", "fx/lien_grille.yaml", "--format", "json")
        assert code == 2 and "mène hors des dossiers permis" in one_json(out)["message"], argv
    assert fausse_reco == []
    journal = data / "notes" / "notes.jsonl"
    code, out, _ = run_cli(capsys, "notes", "add", "--cible", "SNTS", "--titre", "cas fichier", "--fichier",
                           "fx/lien_texte.txt", "--format", "json")
    assert code == 2 and "mène hors des dossiers permis" in one_json(out)["message"] and not journal.exists()
    # lien qui reste dans <D> : refusé aussi (le fichier lui-même est attendu), comme pour --titre-fichier
    code, out, _ = run_cli(capsys, "notes", "add", "--cible", "SNTS", "--titre", "cas fichier", "--fichier",
                           "fx/lien_dedans.txt", "--format", "json")
    assert code == 2 and "lien symbolique" in one_json(out)["message"] and not journal.exists()


# ---------------------------------------------------------------------------
# Constats 12 et 15 : valeurs vides
# ---------------------------------------------------------------------------


def test_empty_portfolio_name_is_refused_never_replaced_by_a_default(donnees, fausse_reco, horloge, panel_suivi,
                                                                    capsys):
    """Avant : « suivi maj --nom '' » mettait à jour tous les portefeuilles, « suivi bulletin --nom '' » donnait REF-S2
    et « recommend --suivi '' » ignorait l'option (code 0 ; « ' ' » donnait déjà 2)."""
    for argv in (["suivi", "maj", "--nom", ""], ["suivi", "bulletin", "--nom", ""], ["suivi", "bulletin", "--nom", " "],
                 ["recommend", "--capital", "10M", "--sans-notes", "--suivi", ""]):
        code, out, _ = run_cli(capsys, *argv, "--format", "json")
        assert code == 2 and "vide" in one_json(out)["message"], argv
    assert fausse_reco == [] and not (donnees[0] / "suivi").exists()


@pytest.mark.parametrize("texte", ["", " ", "\t"])
def test_a_review_without_text_is_refused(donnees, horloge, capsys, texte):
    data, _ = donnees
    assert run_cli(capsys, "suivi", "demarrer", "--nom", "MOI", "--format", "json")[0] == 0
    avant = _lignes(data, "MOI")
    code, out, _ = run_cli(capsys, "suivi", "revue", "--nom", "MOI", "--alerte", "W1", "--decision", "garder", "--texte",
                           texte, "--format", "json")
    assert code == 2 and "texte vide" in one_json(out)["message"]
    assert _lignes(data, "MOI") == avant


# ---------------------------------------------------------------------------
# Constat 22 : écriture d'un taux
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("valeur", ["-0", "1e-1", "0_7", "1_8", "+1", "nan", "inf", "0x1", "1,2,3", "٣", ""])
def test_rate_accepts_only_digits_one_separator_and_percent(valeur):
    """Avant : la syntaxe des nombres de Python passait (« 1e-1 » = 0,1 %, « 0_7 » = 7 %, « -0 » écrit -0.0)."""
    with pytest.raises(ValueError, match="taux invalide"):
        cli_rendement.parse_taux(valeur)


@pytest.mark.parametrize("valeur,attendu", [("0,7", 0.007), ("0.7 %", 0.007), ("12", 0.12), (",5", 0.005),
                                            ("5.", 0.05), ("0", 0.0), ("0,8 %", 0.008)])
def test_rate_usual_spellings(valeur, attendu):
    assert cli_rendement.parse_taux(valeur) == attendu


def test_a_signed_or_exponent_rate_writes_nothing(donnees, capsys):
    for v in ("-0", "1e-1", "0_7"):
        code, out, _ = run_cli(capsys, "plan", "grille", f"--courtage={v}", "--format", "json")
        assert code == 2 and "taux invalide" in one_json(out)["message"], v
    assert not (donnees[0] / "profil").exists()
