"""``notes add --titre-fichier`` et ``notes archive --motif-fichier`` (demande de l'intégrateur Odoo).

Le module Odoo ne doit pas passer un texte libre (titre, motif) en argument de la ligne de commande : il l'écrit dans
un fichier et passe son chemin. Règles essayées ici, en mode normal et en mode embarqué :

- lecture UTF-8 stricte (octets invalides : code 2) ; bords retirés ; contenu vide ou blanc : 2 ;
- même borne de longueur que ``--titre`` (500 caractères, blancs ramenés à une espace) ; pour le motif, 200
  caractères (borne du formulaire de l'interface ; ``--motif`` n'en a pas) ; taille du fichier bornée à 8 Kio avant
  toute lecture ;
- chemin vide ou blanc : 2 ; lien symbolique, dossier, tube : 2 ; en mode embarqué, mêmes dossiers permis que
  ``--fichier`` (données, rapports, fichiers temporaires), chemin relatif résolu depuis les données, chemin réel
  compris ;
- ``--titre`` et ``--titre-fichier`` ensemble (de même ``--motif`` et ``--motif-fichier``) : 2 ; ni l'un ni l'autre
  n'est obligatoire, comme avant ;
- la valeur lue suit exactement le chemin de ``--titre`` ou ``--motif`` ; l'objet JSON de sortie ne change pas.

Tous les journaux sont dans des dossiers temporaires (jamais data/notes). Le code 3 n'est jamais attendu.
Performance passée ≠ garantie. Aucun gain n'est garanti.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from brvm_alpha import cli, paths

ROOT = Path(__file__).resolve().parents[1]
CODES_ADMIS = {0, 1, 2, 4, 5, 6, 7, 8, 130}


def run_cli(capsys, *argv: str) -> tuple[int, str, str]:
    try:
        code = cli.main(list(argv))
    except SystemExit as exc:
        code = exc.code
    cap = capsys.readouterr()
    assert code in CODES_ADMIS
    return code, cap.out, cap.err


def one_json(out: str) -> dict:
    d = json.loads(out)
    assert isinstance(d, dict) and d["bandeau"] == cli.BANNER
    return d


def _ajout(capsys, journal: Path, *extra: str) -> tuple[int, dict]:
    code, out, _ = run_cli(capsys, "notes", "add", "--racine", str(journal), "--cible", "SNTS", "--texte",
                           "Résultats annuels en hausse", "--publie-le", "2026-11-20", *extra, "--format", "json")
    return code, one_json(out)


def _lignes(journal: Path) -> list[dict]:
    f = journal / "notes.jsonl"
    return [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines()] if f.exists() else []


# ---------------------------------------------------------------------------
# Mode normal
# ---------------------------------------------------------------------------


def test_title_file_gives_the_same_note_as_the_title_option(tmp_path, capsys):
    titre = tmp_path / "titre.txt"
    titre.write_bytes("﻿  Résultats du T3 :\n  hausse de 12 %  \r\n\n".encode("utf-8"))  # marque d'ordre, bords
    j1, j2 = tmp_path / "j1", tmp_path / "j2"
    code, d1 = _ajout(capsys, j1, "--titre-fichier", str(titre))
    assert code == 0 and d1["cree"] is True and d1["note"]["title"] == "Résultats du T3 : hausse de 12 %"
    code, d2 = _ajout(capsys, j2, "--titre", "Résultats du T3 :\n  hausse de 12 %")
    assert code == 0 and d2["note"]["title"] == d1["note"]["title"]
    assert set(d1) == set(d2) and d1["note_id"] == d2["note_id"]  # JSON de sortie inchangé, même note
    # même journal : la même saisie par fichier est reconnue comme doublon de la saisie par --titre
    code, d3 = _ajout(capsys, j2, "--titre-fichier", str(titre))
    assert code == 0 and d3["cree"] is False and d3["deja_enregistree"] is True and len(_lignes(j2)) == 1


def test_relative_title_file_is_read_from_the_current_folder_in_normal_mode(tmp_path, capsys, monkeypatch):
    (tmp_path / "t.txt").write_text("Titre relatif", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    code, d = _ajout(capsys, tmp_path / "j", "--titre-fichier", "t.txt")
    assert code == 0 and d["note"]["title"] == "Titre relatif"


def _fichiers_refuses(tmp_path: Path) -> dict[str, tuple[str, str]]:
    """Fichiers refusés (code 2) et un mot du message attendu."""
    d = tmp_path / "refus"
    d.mkdir()
    (d / "latin1.txt").write_bytes("Résultat".encode("latin-1"))
    (d / "coupe.txt").write_bytes("é".encode("utf-8")[:1])  # UTF-8 coupé au milieu d'un caractère
    (d / "vide.txt").write_bytes(b"")
    (d / "blanc.txt").write_text(" \t\n\r\n   　\n", encoding="utf-8")
    (d / "nul.txt").write_bytes(b"titre\x00cache")
    (d / "gros.txt").write_bytes(b"a" * (cli.VALEUR_FICHIER_MAX_OCTETS + 1))
    (d / "dossier").mkdir()
    (d / "vrai.txt").write_text("Titre visé par le lien", encoding="utf-8")
    (d / "lien.txt").symlink_to(d / "vrai.txt")
    os.mkfifo(d / "tube")
    return {"latin1.txt": ("UTF-8", "latin-1"), "coupe.txt": ("UTF-8", "coupé"), "vide.txt": ("vide", "vide"),
            "blanc.txt": ("blancs", "blancs"), "nul.txt": ("nul", "nul"), "gros.txt": ("volumineux", "8 Kio"),
            "dossier": ("fichier ordinaire", "dossier"), "lien.txt": ("lien symbolique", "lien"),
            "tube": ("fichier ordinaire", "tube"), "absent.txt": ("introuvable", "absent")}


def test_each_title_file_rule_exits_2_and_writes_nothing(tmp_path, capsys):
    journal = tmp_path / "j"
    for nom, (mot, cas) in _fichiers_refuses(tmp_path).items():
        code, d = _ajout(capsys, journal, "--titre-fichier", str(tmp_path / "refus" / nom))
        assert code == 2 and d["erreur"] == "saisie_invalide" and mot in d["message"], (cas, d)
        assert "--titre-fichier" in d["message"], (cas, d)
    for vide in ("", " ", "\t"):
        code, d = _ajout(capsys, journal, "--titre-fichier", vide)
        assert code == 2 and "vide ou fait seulement d'espaces" in d["message"], (vide, d)
    assert not journal.exists() or _lignes(journal) == []  # rien n'est écrit


def test_title_file_keeps_the_title_length_limit(tmp_path, capsys):
    ok, trop, blancs = tmp_path / "ok.txt", tmp_path / "trop.txt", tmp_path / "blancs.txt"
    ok.write_text("é" * cli.TITRE_MAX_CARACTERES + "\n", encoding="utf-8")  # 1 000 octets, 500 caractères
    trop.write_text("é" * (cli.TITRE_MAX_CARACTERES + 1), encoding="utf-8")
    blancs.write_text("a    " * cli.TITRE_MAX_CARACTERES, encoding="utf-8")  # 999 caractères une fois ramenés
    code, d = _ajout(capsys, tmp_path / "j", "--titre-fichier", str(ok))
    assert code == 0 and d["note"]["title"] == "é" * cli.TITRE_MAX_CARACTERES
    for f in (trop, blancs):
        code, d = _ajout(capsys, tmp_path / "j", "--titre-fichier", str(f))
        assert code == 2 and "titre trop long (500 caractères au plus)" in d["message"], d
        code, d2 = _ajout(capsys, tmp_path / "j", "--titre", f.read_text(encoding="utf-8"))
        assert code == 2 and d2["message"] == d["message"]  # même contrôle que --titre


def test_title_and_title_file_together_exit_2_and_neither_is_required(tmp_path, capsys):
    t = tmp_path / "t.txt"
    t.write_text("Titre", encoding="utf-8")
    for avec in (["--titre", "autre"], ["--titre", ""]):
        code, d = _ajout(capsys, tmp_path / "j", *avec, "--titre-fichier", str(t))
        assert code == 2 and "incompatible" in d["message"] and "--titre" in d["message"], d
        code, d = _ajout(capsys, tmp_path / "j", "--titre-fichier", str(t), *avec)
        assert code == 2 and "incompatible" in d["message"], d
    assert _lignes(tmp_path / "j") == []
    code, d = _ajout(capsys, tmp_path / "j")  # ni --titre ni --titre-fichier : le texte suffit, comme avant
    assert code == 0 and d["cree"] is True and d["note"]["title"] == ""


def _note_archivable(capsys, journal: Path) -> str:
    code, d = _ajout(capsys, journal, "--titre", "À archiver")
    assert code == 0
    return d["note_id"]


def _archiver(capsys, journal: Path, nid: str, *extra: str) -> tuple[int, dict]:
    code, out, _ = run_cli(capsys, "notes", "archive", nid[:12], "--racine", str(journal), *extra, "--format", "json")
    return code, one_json(out)


def test_reason_file_gives_the_same_archive_as_the_reason_option(tmp_path, capsys):
    m = tmp_path / "motif.txt"
    m.write_text("\n  Information démentie par l'émetteur  \n", encoding="utf-8")
    j1, j2 = tmp_path / "j1", tmp_path / "j2"
    n1, n2 = _note_archivable(capsys, j1), _note_archivable(capsys, j2)
    code, d1 = _archiver(capsys, j1, n1, "--motif-fichier", str(m))
    code2, d2 = _archiver(capsys, j2, n2, "--motif", "Information démentie par l'émetteur")
    assert code == code2 == 0 and set(d1) == set(d2) and d1["archivee"] is True and d1["version"] == d2["version"]
    t1, t2 = _lignes(j1)[-1]["tags"], _lignes(j2)[-1]["tags"]
    assert t1 == t2 and "archive:Information démentie par l'émetteur" in t1


def test_each_reason_file_rule_exits_2_and_writes_nothing(tmp_path, capsys):
    journal = tmp_path / "j"
    nid = _note_archivable(capsys, journal)
    avant = (journal / "notes.jsonl").read_bytes()
    refus = _fichiers_refuses(tmp_path)
    (tmp_path / "refus" / "long.txt").write_text("m" * (cli.MOTIF_MAX_CARACTERES + 1), encoding="utf-8")
    refus["long.txt"] = ("200 au plus", "201 caractères")
    for nom, (mot, cas) in refus.items():
        code, d = _archiver(capsys, journal, nid, "--motif-fichier", str(tmp_path / "refus" / nom))
        assert code == 2 and d["erreur"] == "saisie_invalide" and mot in d["message"], (cas, d)
    for vide in ("", " "):
        code, d = _archiver(capsys, journal, nid, "--motif-fichier", vide)
        assert code == 2 and "vide ou fait seulement d'espaces" in d["message"], d
    m = tmp_path / "m.txt"
    m.write_text("motif", encoding="utf-8")
    for avec in (["--motif", "autre"], ["--motif", ""]):
        code, d = _archiver(capsys, journal, nid, *avec, "--motif-fichier", str(m))
        assert code == 2 and "incompatible" in d["message"], d
    assert (journal / "notes.jsonl").read_bytes() == avant  # rien n'est écrit
    (tmp_path / "juste.txt").write_text("m" * cli.MOTIF_MAX_CARACTERES, encoding="utf-8")
    code, d = _archiver(capsys, journal, nid, "--motif-fichier", str(tmp_path / "juste.txt"))
    assert code == 0 and d["archivee"] is True


def test_archive_without_any_reason_still_works(tmp_path, capsys):
    journal = tmp_path / "j"
    nid = _note_archivable(capsys, journal)
    code, d = _archiver(capsys, journal, nid)
    assert code == 0 and d["archivee"] is True
    assert not any(str(t).startswith("archive:") for t in _lignes(journal)[-1]["tags"])


def test_help_documents_the_new_options(capsys):
    for argv, opt in ((["notes", "add", "--help"], "--titre-fichier"), (["notes", "archive", "--help"],
                                                                         "--motif-fichier")):
        code, out, _ = run_cli(capsys, *argv)
        plat = " ".join(out.split())
        assert code == 0 and opt in plat and "UTF-8 strict" in plat and "8 Kio" in plat, out


# ---------------------------------------------------------------------------
# Mode embarqué (en processus : chemins et dossiers permis)
# ---------------------------------------------------------------------------


@pytest.fixture()
def embarque(tmp_path, monkeypatch):
    data, reports, tmp = tmp_path / "donnees", tmp_path / "rapports", tmp_path / "tmp"
    for d in (data / "notes", reports, tmp):
        d.mkdir(parents=True)
    monkeypatch.setattr(paths, "est_embarque", lambda environ=None, root=None: True)
    monkeypatch.setattr(paths, "ERREUR_CONFIGURATION", None)
    monkeypatch.setattr(paths, "DATA_DIR", data)
    monkeypatch.setattr(paths, "REPORTS_DIR", reports)
    monkeypatch.setenv("TMPDIR", str(tmp))
    import tempfile

    monkeypatch.setattr(tempfile, "tempdir", str(tmp))
    return data, reports, tmp


def test_embedded_title_file_follows_the_path_rules_of_the_file_option(embarque, tmp_path, capsys, monkeypatch):
    data, reports, tmp = embarque
    dehors = tmp_path / "dehors"
    dehors.mkdir()
    (dehors / "secret.txt").write_text("contenu d'un fichier du serveur", encoding="utf-8")
    (data / "titre.txt").write_text("Titre des données\n", encoding="utf-8")
    (tmp / "titre_odoo.txt").write_text("Titre écrit par Odoo dans son TMPDIR\n", encoding="utf-8")
    (reports / "titre_r.txt").write_text("Titre des rapports", encoding="utf-8")
    (data / "lien_dedans.txt").symlink_to(data / "titre.txt")  # lien, même vers un fichier permis : refusé
    (data / "lien_dehors.txt").symlink_to(dehors / "secret.txt")
    (data / "dossier_lien").symlink_to(dehors, target_is_directory=True)  # lien plus haut dans le chemin
    courant = tmp_path / "courant"
    courant.mkdir()
    (courant / "titre.txt").write_text("Titre du dossier courant d'Odoo", encoding="utf-8")
    monkeypatch.chdir(courant)
    journal = data / "notes"
    acceptes = {"titre.txt": "Titre des données",  # relatif : résolu depuis les données, pas le dossier courant
                str(data / "titre.txt"): "Titre des données",
                str(tmp / "titre_odoo.txt"): "Titre écrit par Odoo dans son TMPDIR",
                str(reports / "titre_r.txt"): "Titre des rapports"}
    for chemin, titre in acceptes.items():
        code, d = _ajout(capsys, journal, "--titre-fichier", chemin, "--forcer")
        assert code == 0 and d["note"]["title"] == titre, (chemin, d)
    refuses = {str(dehors / "secret.txt"): "hors des dossiers permis",
               str(data / "dossier_lien" / "secret.txt"): "mène hors des dossiers permis",
               str(data) + "/../dehors/secret.txt": "hors des dossiers permis",
               str(data / "lien_dehors.txt"): "mène hors des dossiers permis",  # chemin réel contrôlé d'abord
               str(data / "lien_dedans.txt"): "lien symbolique",
               str(data / "notes"): "fichier ordinaire",
               "": "vide ou fait seulement d'espaces", " ": "vide ou fait seulement d'espaces"}
    n = len(_lignes(journal))
    for chemin, mot in refuses.items():
        code, d = _ajout(capsys, journal, "--titre-fichier", chemin)
        assert code == 2 and d["erreur"] == "saisie_invalide" and mot in d["message"], (chemin, d)
        assert "--titre-fichier" in d["message"] and "contenu d'un fichier du serveur" not in json.dumps(d)
    assert len(_lignes(journal)) == n
    assert not any("serveur" in str(x.get("title")) for x in _lignes(journal))


def test_embedded_reason_file_follows_the_same_path_rules(embarque, tmp_path, capsys):
    data, _reports, tmp = embarque
    dehors = tmp_path / "dehors"
    dehors.mkdir()
    (dehors / "m.txt").write_text("motif du serveur", encoding="utf-8")
    (tmp / "m.txt").write_text("motif écrit par Odoo", encoding="utf-8")
    (data / "lien.txt").symlink_to(tmp / "m.txt")
    (data / "invalide.txt").write_bytes(b"\xc3\x28")
    journal = data / "notes"
    nid = _note_archivable(capsys, journal)
    avant = (journal / "notes.jsonl").read_bytes()
    for chemin, mot in ((str(dehors / "m.txt"), "hors des dossiers permis"), (str(data / "lien.txt"), "lien"),
                        ("invalide.txt", "UTF-8"), (" ", "vide")):
        code, d = _archiver(capsys, journal, nid, "--motif-fichier", chemin)
        assert code == 2 and mot in d["message"] and "--motif-fichier" in d["message"], (chemin, d)
    assert (journal / "notes.jsonl").read_bytes() == avant
    code, d = _archiver(capsys, journal, nid, "--motif-fichier", str(tmp / "m.txt"))
    assert code == 0 and d["archivee"] is True and "archive:motif écrit par Odoo" in _lignes(journal)[-1]["tags"]


# ---------------------------------------------------------------------------
# Mode embarqué, vrai processus, environnement du lanceur (§ A.6 : env -i et ses variables)
# ---------------------------------------------------------------------------


def _lancer(args: list[str], d: Path, r: Path, t: Path) -> tuple[int, dict, str]:
    env = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "HOME": str(d), "TMPDIR": str(t),
           "BRVM_ALPHA_DONNEES": str(d), "BRVM_ALPHA_RAPPORTS": str(r),
           # pas d'export ici (pas de fichier VERSION) : le mode embarqué est demandé par la variable, et le code est
           # trouvé par PYTHONPATH (le lanceur réel passe par -I et le .pth de l'installation, § A.5)
           "BRVM_ALPHA_EMBARQUE": "1", "PYTHONPATH": str(ROOT), "PYTHONDONTWRITEBYTECODE": "1"}
    with open(t / "sortie.json", "wb") as out, open(t / "erreurs.txt", "wb") as err:
        p = subprocess.run([sys.executable, "-B", "-m", "brvm_alpha", *args, "--format", "json"], env=env,
                           stdin=subprocess.DEVNULL, stdout=out, stderr=err, cwd=str(t), timeout=180,
                           start_new_session=True)
    texte = (t / "sortie.json").read_text(encoding="utf-8")
    return p.returncode, json.loads(texte), (t / "erreurs.txt").read_text(encoding="utf-8", errors="replace")


def test_embedded_launcher_reads_title_and_reason_from_files_in_its_temporary_folder(tmp_path):
    d, r, t = tmp_path / "donnees", tmp_path / "rapports", tmp_path / "tmp"
    for x in (d, r, t):
        x.mkdir()
    (t / "titre.txt").write_text("Avis : « dividende » de 1 500 FCFA ; $(rm -rf /) `id`\n", encoding="utf-8")
    (t / "motif.txt").write_text("Saisie en double --forcer ; « motif » libre\n", encoding="utf-8")
    code, j, err = _lancer(["notes", "add", "--cible", "SNTS", "--titre-fichier", str(t / "titre.txt"), "--texte",
                            "Dividende annoncé"], d, r, t)
    assert code == 0 and j["ok"] is True and j["cree"] is True, (j, err)
    assert j["note"]["title"] == "Avis : « dividende » de 1 500 FCFA ; $(rm -rf /) `id`"
    code, j2, err = _lancer(["notes", "archive", j["note_id"][:12], "--motif-fichier", str(t / "motif.txt")], d, r, t)
    assert code == 0 and j2["archivee"] is True, (j2, err)
    lignes = [json.loads(x) for x in (d / "notes" / "notes.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(lignes) == 2 and "archive:Saisie en double --forcer ; « motif » libre" in lignes[-1]["tags"]
    # refus, même environnement : lien symbolique placé dans les données, octets invalides
    (d / "lien.txt").symlink_to(t / "titre.txt")
    (t / "invalide.txt").write_bytes(b"titre \xff")
    for f in (d / "lien.txt", t / "invalide.txt"):
        code, j3, _ = _lancer(["notes", "add", "--cible", "SNTS", "--titre-fichier", str(f), "--texte", "x"], d, r, t)
        assert code == 2 and j3["erreur"] == "saisie_invalide", j3
    assert len((d / "notes" / "notes.jsonl").read_text(encoding="utf-8").splitlines()) == 2


def test_deployment_doc_describes_the_value_file_options():
    doc = (ROOT / "docs" / "DEPLOIEMENT.md").read_text(encoding="utf-8")
    plat = " ".join(doc.split())
    a9 = plat.split("### A.9", 1)[1].split("### A.10", 1)[0]
    for mot in ("--titre-fichier", "--motif-fichier", "UTF-8 strict", "8 Kio", "500 caractères", "200 caractères",
                "lien symbolique", "Objets JSON inchangés"):
        assert mot in a9.replace("**", ""), mot
    a15 = plat.split("### A.15", 1)[1].split("### A.16", 1)[0]
    assert "--titre-fichier" in a15 and "--motif-fichier" in a15
    a2 = plat.split("### A.2", 1)[1].split("### A.3", 1)[0]
    assert "`--titre-fichier`, `--motif-fichier`, `--sortie`) vide ou faite seulement d'espaces" in a2.replace("**", "")
