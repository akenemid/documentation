"""Compatibilité avec Python 3.11, l'interpréteur de l'image de production d'Odoo 17 (odoo:17.0, Debian bookworm).

Le banc de développement tourne en Python 3.13, qui accepte des f-strings que Python 3.11 refuse
(PEP 701 : barre oblique inverse ou même guillemet dans la partie expression). ``ast.parse(...,
feature_version=(3, 11))`` ne les détecte pas : d'où deux gardes.

1. Analyse lexicale (toujours active, Python 3.12 ou plus) : dans la partie expression d'une f-string,
   aucune chaîne ne doit contenir de barre oblique inverse ni réutiliser le guillemet de la f-string
   qui l'entoure.
2. Compilation réelle par ``python3.11`` quand il est installé (sinon le test est sauté).
"""

from __future__ import annotations

import io
import shutil
import subprocess
import sys
import tokenize
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1]
DOSSIERS = ("brvm_alpha", "tests")


def _fichiers() -> list[Path]:
    out: list[Path] = []
    for d in DOSSIERS:
        out.extend(sorted((RACINE / d).rglob("*.py")))
    return out


def _quote(tok: str) -> str:
    """Guillemet d'ouverture d'une chaîne ou d'une f-string (préfixes retirés)."""
    s = tok.lstrip("rRbBuUfF")
    return s[:3] if s[:3] in ('"""', "'''") else s[:1]


def violations_311(src: str) -> list[tuple[int, str]]:
    """Constructions de f-strings acceptées par Python 3.12+ mais refusées par Python 3.11."""
    if not hasattr(tokenize, "FSTRING_START"):  # Python 3.11 : la compilation suffit
        return []
    pile: list[str] = []  # guillemets des f-strings ouvertes
    out: list[tuple[int, str]] = []
    for t in tokenize.generate_tokens(io.StringIO(src).readline):
        if t.type == tokenize.FSTRING_START:
            q = _quote(t.string)
            if pile and q == pile[-1]:
                out.append((t.start[0], "f-string imbriquée avec le même guillemet"))
            pile.append(q)
        elif t.type == tokenize.FSTRING_END:
            if pile:
                pile.pop()
        elif pile and t.type == tokenize.STRING:
            if "\\" in t.string:
                out.append((t.start[0], "barre oblique inverse dans la partie expression d'une f-string"))
            elif _quote(t.string) == pile[-1]:
                out.append((t.start[0], "chaîne avec le même guillemet que la f-string qui l'entoure"))
        elif pile and t.type == tokenize.COMMENT:
            out.append((t.start[0], "commentaire dans la partie expression d'une f-string"))
    return out


def test_detecteur_reconnait_les_cas_refuses_par_311():
    if not hasattr(tokenize, "FSTRING_START"):
        pytest.skip("analyse lexicale des f-strings : Python 3.12 ou plus")
    assert violations_311('x = f"a {\'jusqu\\\'à\' if c else \'b\'} z"\n')
    assert violations_311("x = f\"a {', '.join(y)} z\"\n") == []
    assert violations_311('x = f"a {"b"} z"\n')


def test_aucune_fstring_reservee_a_python_312():
    fautes = []
    for p in _fichiers():
        for ligne, motif in violations_311(p.read_text(encoding="utf-8")):
            fautes.append(f"{p.relative_to(RACINE)}:{ligne} : {motif}")
    assert not fautes, "Refusé par Python 3.11 (image Odoo 17) :\n" + "\n".join(fautes)


def test_compilation_par_python311():
    py311 = shutil.which("python3.11")
    if not py311 or sys.version_info[:2] == (3, 11):
        pytest.skip("python3.11 absent (ou déjà l'interpréteur courant)")
    code = (
        "import sys, pathlib\n"
        "bad = []\n"
        "for a in sys.argv[1:]:\n"
        "    p = pathlib.Path(a)\n"
        "    try:\n"
        "        compile(p.read_text(encoding='utf-8'), a, 'exec')\n"
        "    except SyntaxError as e:\n"
        "        bad.append(f'{a}:{e.lineno} : {e.msg}')\n"
        "print('\\n'.join(bad))\n"
        "sys.exit(1 if bad else 0)\n"
    )
    r = subprocess.run([py311, "-I", "-c", code, *map(str, _fichiers())],
                       capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, "Erreurs de syntaxe sous Python 3.11 :\n" + r.stdout + r.stderr
