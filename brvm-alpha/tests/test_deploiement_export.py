"""Export du moteur embarqué (``deploiement/exporter-moteur.sh``) : contenu, ``VERSION``, lecture seule.

L'export est lancé pour de bon dans un dossier temporaire, rendu non inscriptible (``chmod -R a-w`` ; en
plus, quand le test tourne en root, un montage en lecture seule dans un espace de noms à part, car root
passe outre les droits). Les commandes utiles à Odoo y sont lancées comme Odoo le fera : ``python -I -B``
(``PYTHONPATH`` ignoré, dossier courant hors du chemin), le code rendu importable par un fichier ``.pth``,
un environnement explicite (``env -i``) et des dossiers de données temporaires (sept BOC des fixtures).
Puis : aucun fichier n'apparaît ni ne change dans l'export, le dossier personnel ou le dossier courant.

Aucune requête réseau (mandataire invalide), aucune écriture dans ``data/`` ni ``reports/`` du dépôt.
Performance passée ≠ garantie. Aucun gain n'est garanti.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploiement"
BOC_FIX = ROOT / "tests" / "fixtures" / "notes" / "boc"

pytestmark = pytest.mark.skipif(shutil.which("sh") is None or shutil.which("git") is None,
                                reason="shell POSIX ou git absent")


def snapshot(root: Path) -> dict[str, tuple[int, int, int]]:
    out = {}
    for dirpath, dirnames, filenames in os.walk(root):
        for name in filenames + dirnames:
            st = os.lstat(os.path.join(dirpath, name))
            out[os.path.relpath(os.path.join(dirpath, name), root)] = (st.st_size, st.st_mtime_ns, st.st_mode)
    return out


def _ro_wrapper(paths: list[Path]) -> list[str]:
    """Préfixe qui monte ``paths`` en lecture seule (root seulement, espace de noms à part), sinon rien."""
    if os.geteuid() != 0 or shutil.which("unshare") is None:
        return []
    probe = subprocess.run(["unshare", "-m", "--propagation", "private", "true"], capture_output=True)
    if probe.returncode != 0:
        return []
    mounts = " && ".join(f'mount --bind "{p}" "{p}" && mount -o remount,ro,bind "{p}"' for p in paths)
    return ["unshare", "-m", "--propagation", "private", "sh", "-c", mounts + ' && exec "$@"', "sh"]


@pytest.fixture(scope="module")
def exported(tmp_path_factory):
    base = tmp_path_factory.mktemp("export_moteur")
    dest = base / "moteur"
    r = subprocess.run(["sh", str(DEPLOY / "exporter-moteur.sh"), str(dest)], capture_output=True, text=True,
                       timeout=300)
    assert r.returncode == 0, r.stdout + r.stderr
    return base, dest, r


def test_export_contains_only_what_the_engine_reads_and_a_version_file(exported):
    _base, dest, r = exported
    top = sorted(p.name for p in dest.iterdir())
    assert top == ["VERSION", "brvm_alpha", "configs", "deploiement", "reports"]
    assert sorted(p.name for p in (dest / "deploiement").iterdir()) == ["requirements-moteur-py311.txt"]
    reports = sorted(p.name for p in (dest / "reports").iterdir())
    assert "validation_S1" in reports and "trials.parquet" in reports
    assert all(n in ("validation_S1", "trials.parquet", "suivi_S2") or n.startswith("diagnostic_S0")
               for n in reports), reports
    files = [p for p in dest.rglob("*") if p.is_file()]
    assert not [p for p in files if "__pycache__" in p.parts or p.suffix == ".pyc" or p.name.startswith(".")]
    assert not (dest / "tests").exists() and not (dest / "docs").exists() and not (dest / "data").exists()
    assert (dest / "configs" / "strategy_v1.yaml").is_file() and (dest / "brvm_alpha" / "cli.py").is_file()
    lines = (dest / "VERSION").read_text(encoding="utf-8").splitlines()
    assert re.fullmatch(r"[0-9a-f]{7}(\+modifie)?", lines[0]), lines[0]
    assert any(line.startswith("# date (UTC) : ") for line in lines) and any("# commit : " in x for x in lines)
    sums = [x for x in lines if re.match(r"^[0-9a-f]{64}  ", x)]
    assert len(sums) == len(files) - 1  # chaque fichier, sauf VERSION lui-même
    check = subprocess.run(["sha256sum", "-c", "--quiet"], input="\n".join(sums) + "\n", text=True, cwd=dest,
                           capture_output=True)
    assert check.returncode == 0, check.stdout + check.stderr
    from brvm_alpha import etat, paths

    assert paths.est_embarque({}, dest) and paths.version_livree(dest) == lines[0]
    assert etat.code_version(dest, {}) == lines[0]


def test_export_refuses_a_destination_in_the_code_or_not_empty(exported, tmp_path):
    r = subprocess.run(["sh", str(DEPLOY / "exporter-moteur.sh"), str(ROOT / "export_interdit")], capture_output=True,
                       text=True)
    assert r.returncode == 2 and "dans le dossier du code" in r.stderr and not (ROOT / "export_interdit").exists()
    (tmp_path / "plein").mkdir()
    (tmp_path / "plein" / "x").write_text("x", encoding="utf-8")
    r = subprocess.run(["sh", str(DEPLOY / "exporter-moteur.sh"), str(tmp_path / "plein")], capture_output=True,
                       text=True)
    assert r.returncode == 2 and "n'est pas vide" in r.stderr
    assert subprocess.run(["sh", str(DEPLOY / "exporter-moteur.sh")], capture_output=True).returncode == 2


#: Commandes utiles à Odoo, et codes de sortie attendus sur un historique de sept BOC (incomplet).
COMMANDS = [
    (["etat"], 0),
    (["panel", "--workers", "1"], 0),
    (["notes", "add", "--cible", "SNTS", "--titre", "Sonatel : essai embarqué", "--avis", "haussier"], 0),
    (["notes", "list"], 0),
    (["indices"], 0),
    (["explain", "SNTS"], 0),
    (["recommend", "--capital", "10M", "--sans-indices", "--tirages", "200"], 1),  # historique incomplet : refus
    (["recommend", "--capital", "10M", "--sans-indices", "--tirages", "200", "--accepter-historique-incomplet"], 0),
    (["report", "--capital", "10M", "--tirages", "200", "--accepter-historique-incomplet"], 0),
    (["update", "--simulation"], 0),
    (["notes", "research", "--hors-ligne", "--pdf", "0"], 0),
    (["notes", "lire", "--hors-ligne", "--max", "2"], 0),
]


def test_exported_engine_runs_read_only_like_odoo_and_writes_only_in_its_data_folders(exported):
    base, dest, _r = exported
    work = base / "essai"
    data, reports, home, cwd, tmpdir, site = (work / n for n in ("donnees", "rapports", "home", "courant", "tmp",
                                                                   "site"))
    for d in (data / "boc_text", reports, home, cwd, tmpdir, site):
        d.mkdir(parents=True)
    for f in BOC_FIX.glob("boc_*.txt.gz"):
        shutil.copy(f, data / "boc_text" / f.name)
    # Fichier .pth : comme dans le site-packages de l'interpréteur autonome (installer-python-et-roues.sh).
    (site / "rz_brvm_alpha.pth").write_text(f"{dest}\n", encoding="utf-8")
    launcher = ("import runpy, site, sys; site.addsitedir(sys.argv[1]); sys.argv = ['brvm_alpha'] + sys.argv[2:]; "
                "runpy.run_module('brvm_alpha', run_name='__main__', alter_sys=True)")
    subprocess.run(["chmod", "-R", "a-w", str(dest)], check=True)
    try:
        env = {"PATH": os.environ["PATH"], "HOME": str(home), "TMPDIR": str(tmpdir), "LANG": "C.UTF-8",
               "BRVM_ALPHA_DONNEES": str(data), "BRVM_ALPHA_RAPPORTS": str(reports),
               "HTTPS_PROXY": "http://127.0.0.1:9", "HTTP_PROXY": "http://127.0.0.1:9"}
        watched = {"export": dest, "home": home, "courant": cwd, "site": site}
        before = {k: snapshot(v) for k, v in watched.items()}
        wrapper = _ro_wrapper([dest])
        for argv, expected in COMMANDS:
            r = subprocess.run([*wrapper, sys.executable, "-I", "-B", "-c", launcher, str(site), *argv, "--format",
                                "json"], env=env, cwd=cwd, capture_output=True, text=True, timeout=600)
            d = json.loads(r.stdout)  # exactement un objet JSON sur la sortie standard
            assert r.returncode == expected and d["bandeau"] and d["ok"] is (expected == 0), (argv, r.stderr[-1500:])
            if argv[0] == "recommend" and expected == 1:
                assert d["erreur"] == "historique_incomplet"
            if argv[0] == "etat":
                assert d["embarque"] is True and d["version"] == (dest / "VERSION").read_text().splitlines()[0]
        after = {k: snapshot(v) for k, v in watched.items()}
        assert after == before  # rien d'écrit dans l'export, le dossier personnel ni le dossier courant
    finally:
        subprocess.run(["chmod", "-R", "u+w", str(dest)], check=True)
    assert (data / "panel" / "equities.parquet").is_file() and (data / "notes" / "notes.jsonl").is_file()
    assert [p.name for p in reports.iterdir()] == ["rapport_2026-10-29.html"]
    assert not list(tmpdir.iterdir())  # fichiers temporaires rendus


def test_embedded_export_without_data_folders_refuses_with_code_8(exported, tmp_path):
    _base, dest, _r = exported
    (tmp_path / "site").mkdir()
    (tmp_path / "site" / "x.pth").write_text(f"{dest}\n", encoding="utf-8")
    launcher = ("import runpy, site, sys; site.addsitedir(sys.argv[1]); sys.argv = ['brvm_alpha'] + sys.argv[2:]; "
                "runpy.run_module('brvm_alpha', run_name='__main__', alter_sys=True)")
    r = subprocess.run([sys.executable, "-I", "-B", "-c", launcher, str(tmp_path / "site"), "notes", "add", "--titre",
                        "x", "--format", "json"], env={"PATH": os.environ["PATH"], "HOME": str(tmp_path)},
                       cwd=tmp_path, capture_output=True, text=True, timeout=120)
    d = json.loads(r.stdout)
    assert r.returncode == 8 and d["erreur"] == "configuration" and "BRVM_ALPHA_DONNEES" in d["message"]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["site"]
