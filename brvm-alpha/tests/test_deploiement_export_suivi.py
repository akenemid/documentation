"""Livraison de la déclaration signée du suivi sur papier sur l'installation (``deploiement/exporter-moteur.sh``,
``Dockerfile.moteur`` ; cahier ``docs/RENDEMENT_NET.md``, §F9 ; fiche de raccordement R17, exception X4).

Sur une **copie** de dépôt (dossier temporaire, ``git init``) : une déclaration signée dans ``reports/suivi_S2`` et
suivie par git part avec l'export ; sur l'export, ``declaration.verifier`` la lit (``existe``, chaîne intacte) et
``depot_de_developpement`` est faux (aucun ``.git`` : on ne signe jamais sur l'installation). Sans git (mode
``find``), le dossier part s'il existe et son absence ne fait pas échouer l'export. Le vrai dépôt n'est jamais touché.
Performance passée ≠ garantie. Aucun gain n'est garanti.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pandas as pd
import pytest

import suivi_jeux as SJ
from brvm_alpha.suivi import declaration as DE

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploiement"

pytestmark = pytest.mark.skipif(shutil.which("sh") is None or shutil.which("git") is None,
                                reason="shell POSIX ou git absent")

GIT = ["git", "-c", "user.name=essai", "-c", "user.email=essai@exemple.invalid", "-c", "commit.gpgsign=false"]


def _arbre(base: Path) -> Path:
    """Arbre de code minimal : ce que l'export copie (le paquet réduit à son ``__init__``)."""
    code = base / "code"
    (code / "brvm_alpha").mkdir(parents=True)
    shutil.copyfile(ROOT / "brvm_alpha" / "__init__.py", code / "brvm_alpha" / "__init__.py")
    shutil.copytree(ROOT / "configs", code / "configs")
    (code / "reports" / "validation_S1").mkdir(parents=True)
    shutil.copyfile(ROOT / "reports" / "validation_S1" / "metrics.json", code / "reports" / "validation_S1" / "metrics.json")
    shutil.copyfile(SJ.REGISTRE_DU_DEPOT, code / "reports" / "trials.parquet")
    (code / "reports" / "diagnostic_S0").mkdir()
    (code / "reports" / "diagnostic_S0" / "LISEZMOI.txt").write_text("diagnostic S0 (essai)\n", encoding="utf-8")
    (code / "deploiement").mkdir()
    for f in ("exporter-moteur.sh", "requirements-moteur-py311.txt"):
        shutil.copyfile(DEPLOY / f, code / "deploiement" / f)
    return code


def _signer(code: Path, tmp: Path) -> Path:
    arts = SJ.reponses_proposees(DE.modele())
    return DE.signer(arts, "AB", code / "reports" / "suivi_S2", racine=code, profil=tmp / "profil",
                     maintenant=pd.Timestamp("2026-11-24 10:00", tz="UTC"))


def _exporter(code: Path, dest: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["sh", str(code / "deploiement" / "exporter-moteur.sh"), str(dest)], capture_output=True,
                          text=True, timeout=120)


def test_signed_declaration_tracked_by_git_is_delivered_and_readable_on_the_installation(tmp_path):
    code = _arbre(tmp_path)
    subprocess.run(GIT + ["init", "-q", str(code)], check=True)
    subprocess.run(GIT + ["-C", str(code), "add", "-A"], check=True)
    subprocess.run(GIT + ["-C", str(code), "commit", "-q", "-m", "essai"], check=True)
    assert DE.depot_de_developpement(code)  # la copie est un dépôt de développement : on peut y signer
    f = _signer(code, tmp_path)
    subprocess.run(GIT + ["-C", str(code), "add", "reports/suivi_S2/declaration.jsonl"], check=True)
    subprocess.run(GIT + ["-C", str(code), "commit", "-q", "-m", "déclaration signée"], check=True)
    dest = tmp_path / "moteur"
    r = _exporter(code, dest)
    assert r.returncode == 0, r.stdout + r.stderr
    livre = dest / "reports" / "suivi_S2" / "declaration.jsonl"
    assert livre.read_bytes() == f.read_bytes()
    assert sorted(p.name for p in (dest / "reports").iterdir()) == ["diagnostic_S0", "suivi_S2", "trials.parquet",
                                                                     "validation_S1"]
    v = DE.verifier(dest / "reports" / "suivi_S2", registre=dest / "reports" / "trials.parquet")
    assert v["existe"] and v["chaine_ok"] and v["n_lignes"] == len(DE.lignes(code / "reports" / "suivi_S2"))
    assert not DE.depot_de_developpement(dest)  # aucun .git sur l'installation : jamais de signature là
    lignes = (dest / "VERSION").read_text(encoding="utf-8").splitlines()
    assert re.fullmatch(r"[0-9a-f]{7}", lignes[0]) and any(x.endswith("  reports/suivi_S2/declaration.jsonl")
                                                          for x in lignes)


def test_without_git_the_folder_goes_if_it_exists_and_its_absence_is_not_an_error(tmp_path):
    code = _arbre(tmp_path)
    r = _exporter(code, tmp_path / "sans_declaration")
    assert r.returncode == 0, r.stdout + r.stderr
    assert not (tmp_path / "sans_declaration" / "reports" / "suivi_S2").exists()
    (code / "reports" / "suivi_S2").mkdir(parents=True)
    (code / "reports" / "suivi_S2" / "declaration.jsonl").write_text("{}\n", encoding="utf-8")
    r = _exporter(code, tmp_path / "avec_declaration")
    assert r.returncode == 0, r.stdout + r.stderr
    assert (tmp_path / "avec_declaration" / "reports" / "suivi_S2" / "declaration.jsonl").is_file()


def test_image_copies_the_declaration_only_if_it_exists():
    text = (DEPLOY / "Dockerfile.moteur").read_text(encoding="utf-8")
    assert re.search(r"^COPY reports/suivi_S\[2\] reports/suivi_S2/$", text, re.M)
    assert "!reports/suivi_S2" in (DEPLOY / "Dockerfile.moteur.dockerignore").read_text(encoding="utf-8")
