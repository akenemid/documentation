"""Tâche de nuit (``deploiement/quotidien.sh``) : étape « suivi maj » du suivi sur papier (cahier
``docs/RENDEMENT_NET.md``, §4.3 et §9.1, exception X3).

L'étape se place entre « panel » et la collecte des notes ; un échec de « suivi maj » est écrit au journal et
**n'arrête jamais** la tâche : les notes et le rapport suivent, la tâche finit en code 1. Doublure de l'interpréteur
(celle de ``tests/test_deploiement_scripts.py``, avec une réponse pour « suivi »), dossiers temporaires, aucune
requête réseau. Performance passée ≠ garantie. Aucun gain n'est garanti.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from test_deploiement_scripts import STUB

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploiement"

pytestmark = pytest.mark.skipif(shutil.which("sh") is None, reason="shell POSIX absent")

#: La doublure répond aussi à « suivi » : code lu dans ``code_suivi`` (0 par défaut).
STUB_SUIVI = STUB.replace("    notes|report|serve)", '    suivi) echo "suivi : $*"; exit "$(lire code_suivi)" ;;\n'
                                                     "    notes|report|serve)")


@pytest.fixture()
def nuit(tmp_path):
    state = tmp_path / "doublure"
    state.mkdir()
    exe = tmp_path / "python-du-moteur"
    exe.write_text(STUB_SUIVI, encoding="utf-8")
    exe.chmod(0o755)
    for k, v in {"restant": 1, "pas": 1, "plancher": 0, "bloque": "false", "cache": 12, "pret": "true",
                 "lancements": 0, "code_update": 0, "code_suivi": 0}.items():
        (state / k).write_text(str(v), encoding="utf-8")
    (state / "appels").write_text("", encoding="utf-8")
    env = {"PATH": os.environ["PATH"], "BRVM_PYTHON": str(exe), "BRVM_CODE": str(ROOT), "STUB": str(state),
           "STUB_PYTHON": sys.executable, "BRVM_ALPHA_DONNEES": str(tmp_path / "donnees"),
           "BRVM_ALPHA_RAPPORTS": str(tmp_path / "rapports"), "BRVM_JOURNAL": str(tmp_path / "journaux")}

    def run(**etat):
        for k, v in etat.items():
            (state / k).write_text(str(v), encoding="utf-8")
        (state / "appels").write_text("", encoding="utf-8")
        r = subprocess.run(["sh", str(DEPLOY / "quotidien.sh")], env=env, cwd=tmp_path, capture_output=True,
                           text=True, timeout=120)
        appels = [c for c in (state / "appels").read_text(encoding="utf-8").splitlines() if not c.startswith("etat")]
        journal = (tmp_path / "journaux" / "quotidien.log").read_text(encoding="utf-8")
        return r, appels, journal

    return run


def test_suivi_maj_runs_between_panel_and_the_notes(nuit):
    r, appels, journal = nuit()
    assert r.returncode == 0, r.stdout + r.stderr
    assert appels == ["update --sans-panel", "panel", "suivi maj", "notes research --pdf 20",
                      "report --capital 10000000"]
    assert "fin : brvm_alpha suivi (code 0)" in journal and "tout s'est bien passé" in journal


@pytest.mark.parametrize("code", [1, 2, 7])
def test_a_failing_suivi_maj_never_stops_the_nightly_task(nuit, code):
    r, appels, journal = nuit(code_suivi=code)
    assert r.returncode == 1 and r.returncode != 3
    # Les étapes suivantes ont lieu : notes, puis le rapport.
    assert appels == ["update --sans-panel", "panel", "suivi maj", "notes research --pdf 20",
                      "report --capital 10000000"]
    assert f"fin : brvm_alpha suivi (code {code})" in journal
    assert "suivi maj en échec : la tâche continue vers le rapport." in journal
    assert "au moins une étape en échec" in journal


def test_suivi_maj_still_runs_after_a_refusal_of_the_site(nuit):
    r, appels, journal = nuit(refus_au_lancement=1)
    assert r.returncode == 5
    assert appels == ["update --sans-panel", "panel", "suivi maj", "report --capital 10000000"]  # calcul local
