"""Rapport final HTML autonome de BRVM Alpha (spécification §4.5, §8, §9.3, §10 ; additif v1.1).

:func:`build_report` écrit **un seul fichier HTML** sans aucune ressource externe : styles et
script en ligne, graphiques en SVG inline générés ici (axes et libellés en HTML pour rester
lisibles à toute largeur), thème clair et sombre (variables CSS sur ``:root`` redéfinies sous
``@media (prefers-color-scheme: dark)``), mise en page lisible sur téléphone (gouttière de
16 px, aucun défilement horizontal de la page : les tableaux larges défilent dans leur propre
conteneur). Seuls les liens de la liste des sources pointent vers l'extérieur (``class="src"``).

Sections, dans l'ordre (:data:`SECTIONS`) : bandeau ; marché ; résultat du test S1 ; ordre de
bataille ; revenus ; distribution à 12 mois ; indices ; notes de l'analyste ; risques ; univers ;
méthode et limites.

Règles :

* **Aucun calcul de performance sur S1** : le résultat du test unique est **lu** dans
  ``validation_dir`` (``metrics.json``, ``nav.parquet``, ``weekly_returns.parquet``), jamais
  recalculé ; s'il n'existe pas, la section est remplacée par un encadré explicite. Le diagnostic
  S0 (``diagnostic_dir``) est affiché comme tel : contaminé, aucune valeur de preuve.
* **Robustesse** : chaque section est construite dans un ``try/except`` ; une erreur affiche un
  encadré lisible (type, message, trace repliée) au lieu de faire échouer le rapport.
* **Échappement** : tout texte issu des données, des notes ou des fichiers de résultats est
  échappé (:func:`esc`) ; l'adresse d'une note n'est un lien que si elle pointe vers
  ``https://www.brvm.org/`` (``class="src"``), sinon elle est affichée en texte.
* **Deux instants** : la date des données est celle du dernier BOC ; les notes suivent la règle
  stricte à cette date (mode historique, défaut de :func:`render_report`) ou, avec
  ``notes_known_at`` (mode direct, passé par la ligne de commande et l'interface à la dernière
  séance du panel), celles connues à cet instant sont appliquées à la séance suivante. Les
  sections indices, notes et ordre affichent la ligne « Notes connues au …, appliquées à la
  séance du … : N en vigueur (dont M manuelles), F filtre(s) de risque actif(s) ».
* **Honnêteté** : bannière « Performance passée ≠ garantie. Aucun gain n'est garanti. » en tête
  et en pied ; chaque bloc distingue faits, estimations et hypothèses.

Chemins relatifs : ``panel_dir``, ``notes_root``, ``validation_dir``, ``diagnostic_dir`` et
``registry_path`` s'entendent depuis la racine du dépôt (comme ``portfolio.recommend``) ;
``out_path`` depuis le répertoire courant.
"""

from __future__ import annotations

import html as _html
import inspect
import json
import math
import re
import time
import traceback
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any

import numpy as np
import pandas as pd

__all__ = [
    "BANNER",
    "SECTIONS",
    "SOURCES",
    "RapportHTML",
    "SectionResult",
    "Unavailable",
    "build_report",
    "ecrire_rapport",
    "esc",
    "fmt_date",
    "fmt_fcfa",
    "fmt_num",
    "fmt_pct",
    "read_validation",
    "render_report",
]

import brvm_alpha as _pkg
from brvm_alpha import erreurs as _erreurs
from brvm_alpha import fichiers as _fichiers
from brvm_alpha import paths as _paths

#: Racine du dépôt (dossier qui contient le paquet ``brvm_alpha``).
ROOT = Path(_pkg.__file__).resolve().parents[1]

#: Bannière permanente (§10).
BANNER = "Performance passée ≠ garantie. Aucun gain n'est garanti."

#: Échantillons (§8.1).
S1_START, S1_END = pd.Timestamp("2017-01-02"), pd.Timestamp("2022-11-16")
S0_START = pd.Timestamp("2022-11-17")
S2_START = pd.Timestamp("2026-12-01")

FAMILY = ("A", "B", "C", "D", "E", "F", "G", "H", "I")
REF = "REF"

#: Sections du rapport, dans l'ordre (identifiant d'ancre, titre).
SECTIONS: tuple[tuple[str, str], ...] = (
    ("bandeau", "Bandeau"),
    ("marche", "Marché au dernier BOC"),
    ("s1", "Résultat du test S1"),
    ("ordre", "Ordre de bataille"),
    ("revenus", "Revenus"),
    ("distribution", "Distribution à 12 mois"),
    ("indices", "Indices"),
    ("notes", "Notes de l'analyste"),
    ("risques", "Risques"),
    ("univers", "Univers"),
    ("methode", "Méthode et limites"),
)

#: Sources primaires (seuls liens externes du rapport).
SOURCES: tuple[tuple[str, str], ...] = (
    ("Bulletins officiels de la cote (BOC) de la BRVM", "https://www.brvm.org/fr/bulletins-officiels-de-la-cote"),
    ("Indices de la BRVM", "https://www.brvm.org/fr/indices"),
    ("Frais applicables (BRVM, DC/BR)", "https://www.brvm.org/fr/node/312"),
    ("Paiements de dividendes", "https://www.brvm.org/fr/esv/paiement-de-dividendes"),
    ("Avis 308-2025 : BRVM Composite Total Return",
     "https://www.brvm.org/sites/default/files/20251224_-_avis_ndeg308_brvmdg_-_affichage_de_lindice_brvm_composite_"
     "total_return_index.pdf"),
    ("Instruction 03-2025 : règlement-livraison J+2",
     "https://www.brvm.org/sites/default/files/instruction_03_2025_brvm_dg_reduction_delai_j3_j2_0.pdf"),
    ("Instruction 01-2025 : alerte sur résultats",
     "https://www.brvm.org/sites/default/files/instruction_ndeg01-2025-brvm-dg_-_profit_warning_1.pdf"),
    ("Règles de négociation, d'admission et de radiation",
     "https://www.brvm.org/sites/default/files/regles_negociation_admission_0.pdf"),
    ("Textes réglementaires", "https://www.brvm.org/fr/textes-reglementaires/reglement-general-instructions-circulaires-"
                              "et-autres-textes-publies-par-la"),
    ("Horaires de cotation", "https://www.brvm.org/fr/horaires-de-cotation"),
    ("robots.txt de brvm.org (Crawl-delay : 10 s, respecté par la collecte)", "https://www.brvm.org/robots.txt"),
)

MOIS = ("janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc.")
PAYS = {"CI": "Côte d'Ivoire", "SN": "Sénégal", "BJ": "Bénin", "BF": "Burkina Faso", "ML": "Mali", "NE": "Niger",
        "TG": "Togo", "GW": "Guinée-Bissau"}
SECTEURS = {"FIN": "Services financiers", "CB": "Consommation de base", "CD": "Consommation discrétionnaire",
            "IND": "Industriels", "ENE": "Énergie", "TEL": "Télécommunications", "SPU": "Services publics"}
AES = ("BF", "ML", "NE")
R_LABELS = {
    "R1": "suspension", "R2": "AG annulée ou reportée", "R3": "réserves ou doute sur la continuité",
    "R4": "dégradation de notation", "R5": "augmentation de capital en numéraire", "R6": "offre publique en cours",
    "R7": "rapport non publié à la date limite", "R8": "division ou regroupement", "R9": "alerte sur résultats",
    "R10": "baisse du RN ≥ 25 % sans alerte", "R11": "drapeaux des sociétés financières",
    "R12": "drapeaux des sociétés non financières",
}
COSTS_FR = {"central": "centraux", "stress": "de stress", "optimistic": "optimistes", "severe": "sévères"}

PREDICTION_8_3 = (
    "Prédiction écrite d'avance (§8.3, maintenue par l'additif v1.1) : avec un IR réel de 0,3, le z attendu sur S1 "
    "(5,9 ans) vaut 0,3 × √5,9 ≈ 0,73, soit un PSR ≈ 0,77 : G2 échouera probablement. Le statut le plus probable, "
    "même pour une bonne stratégie, est « candidat » ; le rejet de A est un résultat plausible (l'essai de fumée de "
    "S0 est défavorable). Un IR > 1 serait d'abord traité comme une ERREUR (anticipation, prix périmés, coûts "
    "oubliés).")
#: Module de l'ordre de bataille (point d'extension pour les tests).
_RECOMMEND_MODULE = "brvm_alpha.portfolio.recommend"

PHRASE_ETUDE = ("recommandation à titre d'étude ; suivi réel (paper trading) requis avant tout engagement d'argent "
                "réel")


# ---------------------------------------------------------------------------
# Échappement et mise en forme
# ---------------------------------------------------------------------------


class H(str):
    """Fragment HTML sûr (déjà échappé ou produit par ce module)."""

    __slots__ = ()


def esc(x: Any) -> H:
    """Texte échappé pour HTML (``<``, ``>``, ``&``, guillemets)."""
    return H(_html.escape("" if x is None else str(x), quote=True))


def _h(x: Any) -> H:
    return x if isinstance(x, H) else esc(x)


def _join(parts: Iterable[Any], sep: str = "") -> H:
    return H(sep.join(_h(p) for p in parts))


NBSP = " "
NNBSP = " "
MINUS = "−"


def _ok(x: Any) -> bool:
    try:
        return x is not None and not isinstance(x, bool) and math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def fmt_num(x: Any, decimals: int = 2, signed: bool = False) -> str:
    """Nombre à la française (``12 345,67``, signe moins typographique) ; ``n.d.`` si absent."""
    if not _ok(x):
        return "n.d."
    v = float(x)
    if abs(v) < 0.5 * 10 ** (-decimals):
        v = 0.0
    s = f"{v:+,.{decimals}f}" if signed else f"{v:,.{decimals}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", NNBSP).replace("-", MINUS)


def fmt_pct(x: Any, decimals: int = 1, signed: bool = False) -> str:
    """Fraction en pourcentage (``0,123`` → ``12,3 %``)."""
    if not _ok(x):
        return "n.d."
    return fmt_num(100.0 * float(x), decimals, signed) + NBSP + "%"


def fmt_fcfa(x: Any, signed: bool = False) -> str:
    if not _ok(x):
        return "n.d."
    return fmt_num(round(float(x)), 0, signed) + NBSP + "FCFA"


def fmt_int(x: Any) -> str:
    return fmt_num(x, 0) if _ok(x) else "n.d."


def fmt_date(x: Any) -> str:
    """Date ``JJ/MM/AAAA`` (``n.d.`` si absente)."""
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "n.d."
    try:
        t = pd.Timestamp(x)
    except (TypeError, ValueError):
        return str(x)
    if pd.isna(t):
        return "n.d."
    return t.strftime("%d/%m/%Y")


def fmt_capital(x: Any) -> str:
    if not _ok(x):
        return "n.d."
    c = float(x)
    if c >= 1e9:
        return f"{fmt_num(c / 1e9, 0 if c % 1e9 == 0 else 1)}{NBSP}Md FCFA"
    if c >= 1e6:
        return f"{fmt_num(c / 1e6, 0 if c % 1e6 == 0 else 1)}{NBSP}M FCFA"
    return fmt_fcfa(c)


def _utc_txt(x: Any) -> str:
    """Horodatage ISO → ``JJ/MM/AAAA HH:MM UTC`` (texte brut si illisible)."""
    try:
        t = pd.Timestamp(x)
    except (TypeError, ValueError):
        return str(x) if x else "n.d."
    if pd.isna(t):
        return "n.d."
    t = t.tz_convert("UTC") if t.tzinfo is not None else t
    return t.strftime("%d/%m/%Y %H:%M UTC")


def _cls(x: Any) -> str:
    return "" if not _ok(x) else ("neg" if float(x) < 0 else "pos" if float(x) > 0 else "")


def _norm_status(x: Any) -> str | None:
    if x is None:
        return None
    s = str(x).strip().upper()
    return {"REJETE": "REJETÉ", "INDETERMINE": "INDÉTERMINÉ"}.get(s, s or None)


def _get(d: Any, *keys: Any, default: Any = None) -> Any:
    cur = d
    for k in keys:
        if isinstance(cur, Mapping):
            cur = cur.get(k)
        elif isinstance(cur, (list, tuple)) and isinstance(k, int) and -len(cur) <= k < len(cur):
            cur = cur[k]
        else:
            return default
        if cur is None:
            return default
    return cur


def _fr_txt(texte: Any) -> str:
    """Typographie française d'un texte technique du modèle (``recommend.fr_texte``) ; texte inchangé si le
    module est illisible (le rapport reste autonome, chaque section isolée)."""
    try:
        from brvm_alpha.portfolio.recommend import fr_texte
    except Exception:  # noqa: BLE001 - affichage seulement
        return str(texte)
    return fr_texte(texte)


def _rel(path: Any) -> str:
    """Chemin affiché relativement à la racine du dépôt quand il s'y trouve."""
    if path is None:
        return "n.d."
    try:
        return str(Path(path).resolve().relative_to(ROOT))
    except (ValueError, OSError):
        return str(path)


def _resolve(path: str | Path | None) -> Path | None:
    if path is None:
        return None
    # ``data/…`` suit le dossier de données en vigueur (``BRVM_ALPHA_DONNEES``) ; le reste demeure au dépôt.
    return _paths.repo_path(path)


# ---------------------------------------------------------------------------
# Briques HTML
# ---------------------------------------------------------------------------


def _tag(kind: str) -> H:
    """Étiquette « fait » / « estimation » / « hypothèse »."""
    lab = {"fait": "fait", "estimation": "estimation", "hypothese": "hypothèse", "hypothèse": "hypothèse"}.get(kind, kind)
    k = {"hypothèse": "hypothese"}.get(lab, lab)
    return H(f'<span class="tag t-{esc(k)}">{esc(lab)}</span>')


def _chip(text: Any, kind: str = "") -> H:
    return H(f'<span class="chip{(" " + esc(kind)) if kind else ""}">{_h(text)}</span>')


def _status_chip(status: Any) -> H:
    s = _norm_status(status) or "n.d."
    kind = {"CANDIDAT": "ok", "PROMU": "ok", "REJETÉ": "no", "INDÉTERMINÉ": "warn"}.get(s, "")
    icon = {"ok": "✓ ", "no": "✕ ", "warn": "? "}.get(kind, "")
    return _chip(icon + s, kind)


def _stance_chip(stance: Any) -> H:
    s = str(stance or "n.d.")
    kind = "pos" if s.startswith("SUR") else "neg" if s.startswith("SOUS") else ""
    icon = "▲ " if kind == "pos" else "▼ " if kind == "neg" else "■ "
    return _chip(icon + s, kind)


def _box(kind: str, title: Any, body: Any = "") -> H:
    """Encadré : ``info``, ``warn`` (avertissement), ``err`` (erreur), ``empty`` (rien à afficher)."""
    icon = {"info": "ℹ", "warn": "⚠", "err": "✕", "empty": "○"}.get(kind, "ℹ")
    return H(f'<div class="box b-{esc(kind)}" role="note"><span class="bi" aria-hidden="true">{icon}</span>'
             f'<div><strong>{_h(title)}</strong>{(" " + _h(body)) if body else ""}</div></div>')


def _p(text: Any, cls: str = "") -> H:
    return H(f'<p{(" class=" + chr(34) + esc(cls) + chr(34)) if cls else ""}>{_h(text)}</p>')


def _ul(items: Iterable[Any], cls: str = "facts") -> H:
    lis = "".join(f"<li>{_h(x)}</li>" for x in items if x not in (None, ""))
    return H(f'<ul class="{esc(cls)}">{lis}</ul>') if lis else H("")


def _tiles(items: Sequence[tuple[Any, Any, Any, str | None]]) -> H:
    """Tuiles (libellé, valeur, sous-texte, nature ``fait``/``estimation``/``hypothese`` ou ``None``)."""
    out = []
    for k, v, s, nature in items:
        tag = (_tag(nature) + " ") if nature else ""
        vv = v if isinstance(v, H) else esc(str(v).replace(NBSP + "FCFA", " FCFA").replace(NBSP + "Md", " Md"))
        out.append(f'<div class="tile"><div class="k">{_h(k)}</div><div class="v">{vv}</div>'
                   f'<div class="s">{tag}{_h(s)}</div></div>')
    return H('<div class="tiles">' + "".join(out) + "</div>")


def _table(headers: Sequence[Any], rows: Sequence[Sequence[Any]], *, left: Iterable[int] = (0,),
           cls: str = "", foot: Sequence[Any] | None = None, caption: Any = None,
           foot_rows: Sequence[Sequence[Any]] | None = None) -> H:
    """Tableau dans un conteneur défilant ; ``left`` : colonnes alignées à gauche ; ``foot`` : une ligne de
    pied ; ``foot_rows`` : plusieurs lignes de pied (p. ex. total des achats, total des ventes, flux net)."""
    left = set(left)

    def cell(tag: str, j: int, x: Any) -> str:
        c = ' class="l"' if j in left else ""
        return f"<{tag}{c}>{_h(x)}</{tag}>"

    head = "".join(cell("th", j, h) for j, h in enumerate(headers))
    body = "".join("<tr>" + "".join(cell("td", j, x) for j, x in enumerate(r)) + "</tr>" for r in rows)
    frows = list(foot_rows or []) + ([foot] if foot else [])
    tfoot = ("<tfoot>" + "".join("<tr>" + "".join(cell("th", j, x) for j, x in enumerate(fr)) + "</tr>"
                                 for fr in frows) + "</tfoot>") if frows else ""
    cap = f"<caption>{_h(caption)}</caption>" if caption else ""
    return H(f'<div class="tablewrap"><table class="{esc(cls)}">{cap}<thead><tr>{head}</tr></thead>'
             f"<tbody>{body}</tbody>{tfoot}</table></div>")


def _num_cell(x: Any, kind: str = "pct", decimals: int = 1, signed: bool = False) -> H:
    txt = {"pct": fmt_pct, "num": fmt_num}[kind](x, decimals, signed) if kind in ("pct", "num") else fmt_fcfa(x)
    c = _cls(x) if signed else ""
    return H(f'<span class="{c}">{esc(txt)}</span>') if c else esc(txt)


def _details(summary: Any, body: Any, open_: bool = False) -> H:
    return H(f'<details{" open" if open_ else ""}><summary>{_h(summary)}</summary>'
             f'<div class="dbody">{_h(body)}</div></details>')


def _fiche(head: Any, fields: Sequence[tuple[str, Any]]) -> H:
    """Fiche d'un élément à champs longs (filtre, blocage) : en-tête puis lignes « libellé : texte ».

    Préférée à un tableau quand les cellules sont des phrases : rien n'est coupé ni caché derrière un
    défilement horizontal, à 390 px comme à 1 280 px.
    """
    rows = "".join(f"<li><b>{esc(k)} :</b> {_h(v)}</li>" for k, v in fields if v not in (None, ""))
    return H(f'<div class="note fiche"><div class="nh">{_h(head)}</div><ul class="facts small">{rows}</ul></div>')


def _card(*parts: Any, cls: str = "") -> H:
    return H(f'<div class="card{(" " + esc(cls)) if cls else ""}">' + "".join(_h(p) for p in parts) + "</div>")


# ---------------------------------------------------------------------------
# Graphiques : SVG inline (zone de tracé étirée, traits non mis à l'échelle), axes en HTML
# ---------------------------------------------------------------------------


def _nice_step(span: float, n: int) -> float:
    if span <= 0 or not math.isfinite(span):
        return 1.0
    raw = span / max(n, 1)
    mag = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 2.5, 5, 10):
        if raw <= m * mag:
            return m * mag
    return 10 * mag


def _nice_ticks(lo: float, hi: float, n: int = 5) -> list[float]:
    if not (math.isfinite(lo) and math.isfinite(hi)):
        return [0.0, 1.0]
    if hi <= lo:
        hi = lo + (abs(lo) * 0.1 or 1.0)
    step = _nice_step(hi - lo, n)
    a = math.floor(lo / step) * step
    b = math.ceil(hi / step) * step
    k = int(round((b - a) / step))
    return [round(a + i * step, 10) for i in range(k + 1)]


def _json_script(data: Any) -> H:
    txt = json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    # Aucun « < », « > » ni « & » brut dans le bloc de données (JSON.parse lit les échappements \\uXXXX).
    txt = txt.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
    return H(f'<script type="application/json" class="cdata">{txt}</script>')


def _clean_list(values: Iterable[Any], decimals: int = 3) -> list[float | None]:
    out: list[float | None] = []
    for v in values:
        out.append(round(float(v), decimals) if _ok(v) else None)
    return out


#: Classes des séries (couleurs de la palette validée ; références neutres en pointillés).
_SERIES_STYLE = {"1": "k1", "2": "k2", "3": "k3", "4": "k4", "5": "k5", "ink": "kink", "muted": "kmuted"}


def line_chart(cid: str, dates: Sequence[Any], series: Sequence[Mapping[str, Any]], *, height: int = 300,
               unit: str = "base100", label: str = "", caption: Any = "", baseline: float | None = 100.0) -> H:
    """Courbes (une seule échelle) : ``series`` = ``[{name, slot, values, dash}]``.

    Tracé dans un ``viewBox`` 1000 × 1000 étiré (``preserveAspectRatio="none"``) avec des traits
    non mis à l'échelle ; graduations et légende en HTML ; info-bulle et réticule en JavaScript
    (données dans un ``<script type="application/json">``).
    """
    ts = [pd.Timestamp(d) for d in dates]
    if len(ts) < 2:
        raise Unavailable("série trop courte pour un graphique")
    t0, t1 = ts[0].value, ts[-1].value
    span_t = max(t1 - t0, 1)
    vals = [np.asarray([float(v) if _ok(v) else np.nan for v in s["values"]], dtype=float) for s in series]
    allv = np.concatenate([v[np.isfinite(v)] for v in vals if np.isfinite(v).any()] or [np.array([0.0, 1.0])])
    lo, hi = float(np.min(allv)), float(np.max(allv))
    if baseline is not None:
        lo, hi = min(lo, baseline), max(hi, baseline)
    pad = (hi - lo) * 0.04 or 1.0
    ticks = _nice_ticks(lo - pad, hi + pad, 5)
    y0, y1 = ticks[0], ticks[-1]

    def X(t: int) -> float:
        return (t - t0) / span_t * 1000.0

    def Y(v: float) -> float:
        return (1.0 - (v - y0) / (y1 - y0)) * 1000.0

    grid = "".join(f'<line class="grid" x1="0" x2="1000" y1="{Y(v):.1f}" y2="{Y(v):.1f}" '
                   f'vector-effect="non-scaling-stroke"/>' for v in ticks)
    if baseline is not None and y0 < baseline < y1:
        grid += (f'<line class="base" x1="0" x2="1000" y1="{Y(baseline):.1f}" y2="{Y(baseline):.1f}" '
                 f'vector-effect="non-scaling-stroke"/>')
    xs = [X(t.value) for t in ts]
    paths = []
    for s, v in zip(series, vals):
        d, pen = [], False
        for x, y in zip(xs, v):
            if not math.isfinite(y):
                pen = False
                continue
            d.append(f"{'L' if pen else 'M'}{x:.1f} {Y(y):.1f}")
            pen = True
        cls = _SERIES_STYLE.get(str(s.get("slot", "1")), "k1") + (" dash" if s.get("dash") else "")
        paths.append(f'<path class="ln {cls}" d="{"".join(d)}" vector-effect="non-scaling-stroke"/>')
    ylab = "".join(f'<span style="top:{Y(v) / 10:.2f}%">{esc(fmt_num(v, 0 if abs(y1 - y0) >= 20 else 1))}</span>'
                   for v in ticks)
    # Graduations du temps : années (ou trimestres sur une période courte).
    years = sorted({t.year for t in ts})
    marks: list[tuple[pd.Timestamp, str]] = []
    if len(years) >= 3:
        marks = [(pd.Timestamp(year=y, month=1, day=1), str(y)) for y in years]
    else:
        q = pd.date_range(ts[0].normalize(), ts[-1], freq="QS")
        marks = [(d, f"{MOIS[d.month - 1]} {d.year}") for d in q]
    xl = []
    shown = [(d, lab) for d, lab in marks if 0.04 <= (d.value - t0) / span_t <= 0.93]
    for i, (d, lab) in enumerate(shown):
        odd = " odd" if (i % 2 == 1 and len(shown) > 5) else ""
        xl.append(f'<span class="xt{odd}" style="left:{X(d.value) / 10:.2f}%">{esc(lab)}</span>')
    legend = "".join(f'<span><i class="sw {_SERIES_STYLE.get(str(s.get("slot", "1")), "k1")}'
                     f'{" dash" if s.get("dash") else ""}"></i>{esc(s["name"])}</span>' for s in series)
    data = {"kind": "line", "t": [t.value // 10**6 for t in ts], "y0": y0, "y1": y1, "u": unit,
            "s": [{"n": str(s["name"]), "k": _SERIES_STYLE.get(str(s.get("slot", "1")), "k1"),
                   "v": _clean_list(v, 3)} for s, v in zip(series, vals)]}
    dots = "".join(f'<b class="dot {_SERIES_STYLE.get(str(s.get("slot", "1")), "k1")}"></b>' for s in series)
    return H(
        f'<figure class="chart" id="{esc(cid)}" data-kind="line">'
        f'<div class="legend">{legend}</div>'
        f'<div class="plot" style="height:{int(height)}px"><div class="yax" aria-hidden="true">{ylab}</div>'
        f'<div class="area"><svg viewBox="0 0 1000 1000" preserveAspectRatio="none" role="img" '
        f'aria-label="{esc(label)}" focusable="false">{grid}{"".join(paths)}</svg>'
        f'<div class="xax" aria-hidden="true">{"".join(xl)}</div><div class="xh"></div>'
        f'<div class="dots">{dots}</div><div class="tip" role="status"></div></div></div>'
        f'{_json_script(data)}'
        f'{("<figcaption>" + _h(caption) + "</figcaption>") if caption else ""}</figure>')


def bar_chart(cid: str, labels: Sequence[str], values: Sequence[float], *, tips: Sequence[str] | None = None,
              height: int = 220, label: str = "", caption: Any = "", unit: str = "fcfa",
              markers: Sequence[tuple[float, str, str]] = (), edges: Sequence[float] | None = None) -> H:
    """Barres verticales d'une seule série (histogramme si ``edges`` est fourni : ``len(values) + 1``
    bornes en fraction). ``markers`` : lignes verticales ``(position en fraction de x, libellé, classe)``
    pour un histogramme. Info-bulle par barre (``tips``)."""
    n = len(values)
    if n == 0:
        raise Unavailable("aucune valeur à représenter")
    v = np.asarray([float(x) if _ok(x) else 0.0 for x in values], dtype=float)
    top = float(v.max()) if v.max() > 0 else 1.0
    ticks = _nice_ticks(0.0, top, 4)
    y1 = ticks[-1]
    w = 1000.0 / n
    gap = min(w * 0.18, 14.0)
    bars = []
    for i, x in enumerate(v):
        hgt = x / y1 * 1000.0
        if hgt <= 0:
            continue
        bars.append(f'<rect class="bar" x="{i * w + gap / 2:.2f}" y="{1000 - hgt:.2f}" width="{max(w - gap, 0.5):.2f}" '
                    f'height="{hgt:.2f}"/>')
    grid = "".join(f'<line class="grid" x1="0" x2="1000" y1="{(1 - t / y1) * 1000:.1f}" y2="{(1 - t / y1) * 1000:.1f}" '
                   f'vector-effect="non-scaling-stroke"/>' for t in ticks)

    def yfmt(t: float) -> str:
        if unit == "share":
            return fmt_pct(t, 0 if y1 >= 0.05 else 1)
        if y1 >= 1e6:
            return fmt_num(t / 1e6, 1 if y1 < 1e7 else 0) + NBSP + "M"
        if y1 >= 1e3:
            return fmt_num(t / 1e3, 0) + NBSP + "k"
        return fmt_num(t, 0)

    ylab = "".join(f'<span style="top:{(1 - t / y1) * 100:.2f}%">{esc(yfmt(t))}</span>' for t in ticks)
    mk = ""
    xl = []
    if edges is not None:
        e0, e1 = float(edges[0]), float(edges[-1])

        def EX(x: float) -> float:
            return (x - e0) / (e1 - e0) * 1000.0 if e1 > e0 else 0.0

        for k, (pos, lab, cls) in enumerate(markers):
            if not _ok(pos) or not e0 <= pos <= e1:
                continue
            mk += (f'<line class="mk {esc(cls)}" x1="{EX(pos):.1f}" x2="{EX(pos):.1f}" y1="0" y2="1000" '
                   f'vector-effect="non-scaling-stroke"/>')
        xt = _nice_ticks(e0, e1, 6)
        for j, x in enumerate(t for t in xt if e0 <= t <= e1):
            p = EX(x) / 10
            if 3 <= p <= 95:
                xl.append(f'<span class="xt{" odd" if j % 2 else ""}" style="left:{p:.2f}%">'
                          f'{esc(fmt_pct(x, 0))}</span>')
        mlab = []
        # Étiquettes des repères : chacune sur la première ligne où elle ne touche aucune autre (largeur
        # estimée pour un graphique étroit, téléphone de 390 px). Avant, la ligne dépendait du rang du repère
        # (k % 3) : « P10 » et « TR médian » partageaient une ligne et se recouvraient.
        rows: list[list[tuple[float, float]]] = []
        shown = sorted(((EX(pos) / 10, lab, cls) for pos, lab, cls in markers if _ok(pos) and e0 <= pos <= e1
                        and cls != "zero"), key=lambda x: x[0])
        for p, lab, cls in shown:
            side = "r" if p > 70 else ""
            width = 2.4 * len(str(lab)) + 4.0  # % de la largeur du tracé, estimation prudente
            a, b = (p - width, p) if side else (p, p + width)
            row = next((i for i, used in enumerate(rows) if all(b <= u0 or a >= u1 for u0, u1 in used)), len(rows))
            if row == len(rows):
                rows.append([])
            rows[row].append((a, b))
            mlab.append(f'<span class="ml {esc(cls)} {side}" style="left:{p:.2f}%;top:{4 + 18 * row}px">'
                        f'{esc(lab)}</span>')
        mk_html = '<div class="mlab" aria-hidden="true">' + "".join(mlab) + "</div>"
    else:
        step = max(1, math.ceil(n / 12))
        for i, lab in enumerate(labels):
            if i % step == 0:
                xl.append(f'<span class="xt{" odd" if (i // step) % 2 else ""}" style="left:{(i + 0.5) * w / 10:.2f}%">'
                          f'{esc(lab)}</span>')
        mk_html = ""
    data = {"kind": "bars", "n": n, "tips": [str(x) for x in (tips or [f"{lab} : {yfmt(val)}" for lab, val in
                                                                      zip(labels, v)])]}
    return H(
        f'<figure class="chart" id="{esc(cid)}" data-kind="bars">'
        f'<div class="plot" style="height:{int(height)}px"><div class="yax" aria-hidden="true">{ylab}</div>'
        f'<div class="area"><svg viewBox="0 0 1000 1000" preserveAspectRatio="none" role="img" '
        f'aria-label="{esc(label)}" focusable="false">{grid}{"".join(bars)}{mk}'
        f'<line class="axis" x1="0" x2="1000" y1="1000" y2="1000" vector-effect="non-scaling-stroke"/></svg>'
        f'{mk_html}<div class="xax" aria-hidden="true">{"".join(xl)}</div><div class="hl"></div>'
        f'<div class="tip" role="status"></div></div></div>{_json_script(data)}'
        f'{("<figcaption>" + _h(caption) + "</figcaption>") if caption else ""}</figure>')


def histogram_chart(cid: str, values: np.ndarray, *, bins: int = 36, markers: Sequence[tuple[float, str, str]] = (),
                    height: int = 240, label: str = "", caption: Any = "") -> H:
    """Histogramme de rendements (fractions) : barres = part des tirages ; les queues au-delà des
    quantiles 0,5 % et 99,5 % sont regroupées dans les classes extrêmes (signalé dans l'info-bulle)."""
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) < 10:
        raise Unavailable("trop peu de tirages pour un histogramme")
    lo, hi = float(np.quantile(x, 0.005)), float(np.quantile(x, 0.995))
    for pos, _, _ in markers:
        if _ok(pos):
            lo, hi = min(lo, float(pos)), max(hi, float(pos))
    if hi <= lo:
        hi = lo + 0.01
    edges = np.linspace(lo, hi, bins + 1)
    counts, _ = np.histogram(np.clip(x, lo, hi), bins=edges)
    share = counts / len(x)
    tips = []
    for i in range(bins):
        a, b = edges[i], edges[i + 1]
        tail = (" (queue regroupée)" if (i == 0 and x.min() < lo) or (i == bins - 1 and x.max() > hi) else "")
        tips.append(f"De {fmt_pct(a)} à {fmt_pct(b)} : {fmt_int(counts[i])} tirages ({fmt_pct(share[i])}){tail}")
    return bar_chart(cid, [""] * bins, list(share), tips=tips, height=height, label=label, caption=caption,
                     unit="share", markers=markers, edges=list(edges))


# ---------------------------------------------------------------------------
# Lecture des résultats de validation (jamais recalculés)
# ---------------------------------------------------------------------------


def _read_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.exists():
        return None, None
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as exc:  # noqa: BLE001 - rapporté
        return None, f"{path.name} illisible ({exc.__class__.__name__} : {exc})"


def read_validation(validation_dir: str | Path | None, sample: str = "S1") -> dict[str, Any]:
    """État du test ``sample`` lu dans ``validation_dir`` (``metrics.json``, ``lock.json``).

    Renvoie ``execute`` (metrics.json lisible de l'échantillon attendu), ``etat`` (``exécuté``,
    ``non exécuté``, ``en cours``, ``échec``, ``illisible``, ``autre échantillon``), ``metrics``,
    ``statut_A``, ``principal`` (variante après la règle du §3.4), ``statut_principal``, ``lock``
    et ``avertissements``. Aucune performance n'est calculée ici.
    """
    vdir = _resolve(validation_dir)
    out: dict[str, Any] = {"dossier": str(vdir) if vdir else None, "execute": False, "etat": "non exécuté",
                           "metrics": None, "statut_A": None, "principal": None, "statut_principal": None,
                           "lock": None, "avertissements": []}
    if vdir is None:
        return out
    m, err = _read_json(vdir / "metrics.json")
    if err:
        out["etat"] = "illisible"
        out["avertissements"].append(err + f" : test {sample} réputé non exécuté")
    elif m is not None:
        if str(m.get("echantillon", "")).upper() != sample.upper():
            out["etat"] = "autre échantillon"
            out["avertissements"].append(f"metrics.json porte sur l'échantillon {m.get('echantillon')!r}, pas sur "
                                         f"{sample} : ignoré")
        else:
            V = m.get("variantes") or {}
            out.update(execute=True, etat="exécuté", metrics=m)
            out["statut_A"] = _norm_status(_get(V, "A", "statut")) or "INDÉTERMINÉ"
            principal = str(_get(m, "promotion", "principal", default="A"))
            out["principal"] = principal
            out["statut_principal"] = _norm_status(_get(V, principal, "statut")) or out["statut_A"]
    lock, lerr = _read_json(vdir / "lock.json")
    if lerr:
        out["avertissements"].append(lerr)
    if lock is not None:
        out["lock"] = lock
        if not out["execute"] and out["etat"] == "non exécuté":
            st = str(lock.get("statut", "")).strip().lower()
            out["etat"] = {"en cours": "en cours", "échec": "échec", "echec": "échec"}.get(st, out["etat"])
            if st == "terminé":
                out["avertissements"].append("lock.json indique « terminé » mais metrics.json est absent : "
                                             "incohérence à vérifier")
    return out


def _strategy_status(val: Mapping[str, Any]) -> dict[str, str]:
    """Statut affiché, phrase de statut (étude / paper trading / promu) et étiquette courte."""
    if not val.get("execute"):
        etat = val.get("etat")
        lab = {"en cours": "test S1 en cours", "échec": "test S1 en échec (aucune métrique publiée)"}.get(
            str(etat), "test S1 non exécuté")
        return {"code": "NON TESTÉ", "label": lab, "mode": "étude",
                "phrase": f"Étude : {PHRASE_ETUDE}. Aucune variante n'est validée ; l'ordre de bataille suit "
                          "l'« indice discipliné » (REF, D8) par défaut."}
    st = val.get("statut_A") or "INDÉTERMINÉ"
    principal = val.get("principal") or "A"
    stp = val.get("statut_principal") or st
    lab = f"A : {st}" + (f" ; {principal} promue (§3.4) : {stp}" if principal != "A" else "")
    if "PROMU" in (st, stp):
        return {"code": "PROMU", "label": lab, "mode": "promu",
                "phrase": "Promu : les critères du §8.3 sont verts sur S1 et sur au moins 12 mois de suivi réel ; "
                          "un engagement d'argent réel devient envisageable, sans aucune garantie de gain."}
    if "CANDIDAT" in (st, stp):
        return {"code": "CANDIDAT", "label": lab, "mode": "paper trading",
                "phrase": "Paper trading : le suivi réel (S2, à partir du 01/12/2026) est autorisé, sans argent réel ; "
                          f"{PHRASE_ETUDE}. Le statut PROMU exige au moins 12 mois de suivi réel (D7)."}
    if st == "REJETÉ":
        return {"code": "REJETÉ", "label": lab, "mode": "étude",
                "phrase": "Étude : A est rejeté sur S1 ; la plate-forme passe en mode « indice discipliné » (REF, D8), "
                          f"sans promesse d'alpha ; {PHRASE_ETUDE}."}
    return {"code": st, "label": lab, "mode": "étude",
            "phrase": f"Étude : statut {st} (données insuffisantes) : aucun suivi réel autorisé (D7) ; {PHRASE_ETUDE}."}


# ---------------------------------------------------------------------------
# Contexte : calculs partagés, paresseux, avec capture des erreurs
# ---------------------------------------------------------------------------


class Unavailable(RuntimeError):
    """Module, fichier ou donnée absent : la section affiche un encadré « indisponible »."""


class DependencyError(RuntimeError):
    """Un calcul partagé par plusieurs sections a échoué (exception d'origine dans ``original``)."""

    def __init__(self, label: str, original: BaseException, tb: str):
        super().__init__(f"{label} : {original.__class__.__name__} : {original}")
        self.label = label
        self.original = original
        self.tb = tb


class _Ctx:
    def __init__(self, asof: Any, capital: float, *, panels: Mapping[str, Any] | None, panel_dir: Any,
                 notes_root: Any, validation_dir: Any, diagnostic_dir: Any, holdings: Mapping[str, int] | None,
                 variant: str | None, cash: float | None, costs: Any, registry_path: Any, n_boot: int, seed: int,
                 recommend_kwargs: Mapping[str, Any] | None, now: pd.Timestamp, notes_known_at: Any = None,
                 historique: Mapping[str, Any] | None = None):
        self.asof_req = pd.Timestamp(asof).normalize()
        #: état de l'historique (ligne de commande : ``cli.history_state``) ; None : non relevé
        self.historique = dict(historique) if historique else None
        #: instant de connaissance des notes (mode direct) ; None : mode historique (règle stricte)
        self.notes_known_at = notes_known_at
        self.capital = float(capital)
        self.panels_given = panels
        self.panel_dir = _resolve(panel_dir)
        self.notes_root = _resolve(notes_root)
        self.validation_dir = _resolve(validation_dir)
        self.diagnostic_dir = _resolve(diagnostic_dir)
        self.holdings = {str(k).upper().strip(): int(v) for k, v in (holdings or {}).items()}
        self.variant = variant
        self.cash = cash
        self.costs = costs
        self.registry_path = _resolve(registry_path)
        self.n_boot = int(n_boot)
        self.seed = int(seed)
        self.recommend_kwargs = dict(recommend_kwargs or {})
        self.now = now
        self._cache: dict[str, tuple[str, Any, str]] = {}
        self.timings: dict[str, float] = {}

    # -- mécanique ----------------------------------------------------------------------------
    def lazy(self, key: str, label: str, fn: Callable[[], Any]) -> Any:
        if key not in self._cache:
            t = time.perf_counter()
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    self._cache[key] = ("ok", fn(), "")
            except (Unavailable, DependencyError) as exc:  # transmis tels quels (cause d'origine conservée)
                self._cache[key] = ("na", exc, "")
            except MemoryError:  # mémoire insuffisante : la commande s'arrête (code 6), pas un encadré
                raise
            except Exception as exc:  # noqa: BLE001 - restitué dans l'encadré d'erreur
                self._cache[key] = ("err", exc, traceback.format_exc())
            self.timings[key] = round(time.perf_counter() - t, 2)
        st, val, tb = self._cache[key]
        if st == "na":
            raise val
        if st == "err":
            raise DependencyError(label, val, tb)
        return val

    def try_get(self, key: str, label: str, fn: Callable[[], Any]) -> Any:
        try:
            return self.lazy(key, label, fn)
        except (Unavailable, DependencyError):
            return None

    # -- données ------------------------------------------------------------------------------
    def panels(self) -> Mapping[str, Any]:
        def load() -> Mapping[str, Any]:
            if self.panels_given is not None:
                return self.panels_given
            if self.panel_dir is None or not (self.panel_dir / "equities.parquet").exists():
                raise Unavailable(f"panel introuvable ({self.panel_dir})")
            from brvm_alpha.strategy import build_panels

            return build_panels(self.panel_dir)

        return self.lazy("panels", "panels du moteur", load)

    def long(self, name: str) -> pd.DataFrame | None:
        """Table longue du panel (``panel_dir/<name>.parquet``), ou table longue fournie dans ``panels``."""
        def load() -> pd.DataFrame | None:
            if self.panel_dir is not None and (self.panel_dir / f"{name}.parquet").exists():
                return pd.read_parquet(self.panel_dir / f"{name}.parquet")
            P = self.panels_given
            if isinstance(P, Mapping) and isinstance(P.get(name), pd.DataFrame) and "date" in P[name].columns:
                return P[name]
            return None

        return self.try_get(f"long:{name}", f"table {name}", load)

    def t(self) -> pd.Timestamp:
        """Date des données : dernière séance du panel au plus tard à la date demandée."""
        def find() -> pd.Timestamp:
            idx = None
            P = self.try_get("panels", "panels du moteur", self.panels)
            if P is not None:
                for k in ("close_raw", "close"):
                    df = P.get(k) if isinstance(P, Mapping) else None
                    if isinstance(df, pd.DataFrame) and len(df):
                        idx = pd.DatetimeIndex(df.index)
                        break
            if idx is None:
                mk = self.long("market")
                if mk is not None and len(mk):
                    idx = pd.DatetimeIndex(pd.to_datetime(mk["date"]))
            if idx is None:
                raise Unavailable("aucune donnée datée (panel absent)")
            idx = idx[idx <= self.asof_req]
            if not len(idx):
                raise Unavailable(f"aucune séance au plus tard le {fmt_date(self.asof_req)}")
            return pd.Timestamp(idx.max()).normalize()

        return self.lazy("t", "date des données", find)

    def validation(self) -> dict[str, Any]:
        return self.lazy("validation", "résultats du test S1", lambda: read_validation(self.validation_dir, "S1"))

    def diagnostic(self) -> dict[str, Any]:
        return self.lazy("diagnostic", "diagnostic S0", lambda: read_validation(self.diagnostic_dir, "S0"))

    def store(self) -> Any:
        """Journal des notes (``NoteStore``) s'il existe, sinon ``None``."""
        def load() -> Any:
            if self.notes_root is None:
                return None
            try:
                from brvm_alpha.notes.store import JOURNAL_NAME, NoteStore
            except Exception as exc:  # noqa: BLE001 - module absent : encadré « indisponible »
                raise Unavailable(f"module des notes indisponible ({exc.__class__.__name__} : {exc})") from exc
            if not (self.notes_root / JOURNAL_NAME).exists():
                return None
            return NoteStore(self.notes_root)

        return self.lazy("store", "journal des notes", load)

    def names(self) -> dict[str, str]:
        def load() -> dict[str, str]:
            eq = self.long("equities")
            if eq is not None and "name" in eq.columns:
                e = eq[pd.to_datetime(eq["date"]) <= self.asof_req] if "date" in eq.columns else eq
                return e.sort_values("date").groupby("symbol")["name"].last().astype(str).to_dict()
            return {}

        return self.try_get("names", "noms des titres", load) or {}

    # -- ordre de bataille --------------------------------------------------------------------
    def recommend_module(self) -> Any:
        def load() -> Any:
            try:
                import importlib

                mod = importlib.import_module(_RECOMMEND_MODULE)
            except Exception as exc:  # noqa: BLE001 - module absent : encadré « indisponible »
                raise Unavailable(f"module {_RECOMMEND_MODULE} indisponible ({exc.__class__.__name__} : "
                                  f"{exc})") from exc
            if not callable(getattr(mod, "recommend", None)):
                raise Unavailable("brvm_alpha.portfolio.recommend ne fournit pas de fonction recommend()")
            return mod

        return self.lazy("recommend_module", "module recommend", load)

    def order(self) -> Any:
        def compute() -> Any:
            mod = self.recommend_module()
            P = self.panels()
            st = self.store()
            kw: dict[str, Any] = dict(panels=P, holdings=self.holdings or None, cash=self.cash, variant=self.variant,
                                      costs=self.costs, notes_store=st if st is not None else False,
                                      validation_dir=self.validation_dir, n_boot=self.n_boot, seed=self.seed,
                                      registry_path=self.registry_path, index_evaluation=False,
                                      index_note="Évaluation des indices : voir la section « Indices » de ce rapport.",
                                      panel_dir=self.panel_dir if self.panel_dir is not None and self.panel_dir.exists()
                                      else None,
                                      # Contrôle de fraîcheur du panel (retard de BOC) à la date du rapport.
                                      today=self.now,
                                      # Mode direct des notes (None : mode historique, règle stricte).
                                      notes_known_at=self.notes_known_at)
            kw.update(self.recommend_kwargs)
            fn = mod.recommend
            try:
                params = inspect.signature(fn).parameters
                if not any(p.kind == p.VAR_KEYWORD for p in params.values()):
                    kw = {k: v for k, v in kw.items() if k in params}
            except (TypeError, ValueError):
                pass
            return fn(self.asof_req, self.capital, **kw)

        return self.lazy("order", "ordre de bataille (portfolio.recommend)", compute)

    def order_dict(self) -> dict[str, Any]:
        def conv() -> dict[str, Any]:
            o = self.order()
            return o.to_dict() if hasattr(o, "to_dict") else dict(o)

        return self.lazy("order_dict", "ordre de bataille (to_dict)", conv)

    def decision(self) -> Any:
        """Décision du modèle (univers, signaux, risque, score) pour la variante appliquée."""
        def compute() -> Any:
            from brvm_alpha.strategy import BrvmAlpha

            P = self.panels()
            t = self.t()
            od = self.try_get("order_dict", "ordre de bataille (to_dict)", self.order_dict)
            v = str((od or {}).get("variante") or self.variant or "A")
            nav = float((od or {}).get("valeur_portefeuille") or self.capital)
            st = self.store()
            close = P.get("close_raw") if isinstance(P.get("close_raw"), pd.DataFrame) else P.get("close")
            held = None
            if self.holdings and isinstance(close, pd.DataFrame):
                c = close.loc[:t].iloc[-1]
                held = pd.Series({s: q * float(c.get(s, np.nan)) / nav for s, q in self.holdings.items() if q > 0},
                                 dtype=float).dropna()
            model = BrvmAlpha(variant=v, capital=nav, notes=st if st is not None else None,
                              notes_known_at=self.notes_known_at)
            return model.decide(t, P, held if held is not None and len(held) else None)

        return self.lazy("decision", "décision du modèle (BrvmAlpha.decide)", compute)

    def indices_eval(self) -> pd.DataFrame:
        def compute() -> pd.DataFrame:
            try:
                from brvm_alpha.notes import index_eval
            except Exception as exc:
                raise Unavailable(f"module brvm_alpha.notes.index_eval indisponible ({exc.__class__.__name__})") from exc
            source: Any = None
            if self.panel_dir is not None and (self.panel_dir / "equities.parquet").exists() and \
                    (self.panel_dir / "indices.parquet").exists():
                source = str(self.panel_dir)
            elif isinstance(self.panels_given, Mapping) and all(
                    isinstance(self.panels_given.get(k), pd.DataFrame) and "date" in self.panels_given[k].columns
                    for k in ("equities", "indices")):
                source = self.panels_given
            if source is None:
                raise Unavailable("tables longues equities et indices introuvables (panel_dir)")
            return index_eval.evaluate_indices(source, self.store(), self.t(), notes_known_at=self.notes_known_at)

        return self.lazy("indices_eval", "évaluation des indices", compute)

    def notes_status(self) -> dict[str, Any] | None:
        """État daté des notes (``notes.signals.notes_in_force``) : ligne, notes en vigueur, filtres."""
        def compute() -> dict[str, Any] | None:
            st = self.store()
            if st is None:
                return None
            from brvm_alpha.notes import signals as sg

            cal: Any = self.long("sessions")
            if cal is None:
                P = self.try_get("panels", "panels du moteur", self.panels)
                close = None if P is None else (P.get("close_raw") if isinstance(P.get("close_raw"), pd.DataFrame)
                                                else P.get("close"))
                cal = list(pd.DatetimeIndex(close.index)) if isinstance(close, pd.DataFrame) else None
            eq = self.long("equities")
            return sg.notes_in_force(st, self.t(), known_at=self.notes_known_at, calendar=cal,
                                     equities=eq if eq is not None else None)

        return self.lazy("notes_status", "état des notes", compute)

    def notes_line(self) -> str | None:
        """Ligne datée des notes : celle de l'ordre de bataille si elle existe, sinon recalculée."""
        od = self.try_get("order_dict", "ordre de bataille", self.order_dict)
        line = _get(od, "declencheurs", "notes", "ligne")
        if line:
            return str(line)
        st = self.try_get("notes_status", "état des notes", self.notes_status)
        return None if not st else str(st.get("line"))

    def draws(self) -> dict[str, Any]:
        """Tirages du bootstrap de l'ordre de bataille, recalculés à l'identique (même fenêtre, mêmes
        poids, même graine) pour l'histogramme : ``net`` (rendement net à l'horizon) et ``tr``."""
        def compute() -> dict[str, Any]:
            od = self.order_dict()
            dist = od.get("distribution") or {}
            if not dist.get("disponible"):
                raise Unavailable(f"distribution indisponible ({dist.get('motif', 'motif non précisé')})")
            mod = self.recommend_module()
            P = self.panels()
            win = _get(od, "meta", "fenetre_estimation") or {}
            weights = {str(r["symbole"]): float(r["poids_realise"]) for r in od.get("lignes") or []
                       if (r.get("cibles") or 0) > 0 and _ok(r.get("poids_realise"))}
            weekly = mod.weekly_tr_returns(P["tr_index"], P.get("market_tr"), list(weights), win.get("debut"),
                                           win.get("fin"))
            # Même fonction que l'ordre de bataille (lignes pas encore cotées renormalisées, et non
            # comptées à 0 %) : l'histogramme reprend exactement la distribution publiée.
            again = mod.return_distribution(weekly, weights, horizon_weeks=int(dist["horizon_semaines"]),
                                            n_boot=int(dist["n_boot"]), mean_block=float(dist["bloc_moyen_semaines"]),
                                            seed=int(dist["graine"]), cost_drag=float(dist.get("frais_deduits") or 0.0),
                                            with_draws=True)
            if not again.get("disponible"):
                raise Unavailable(f"tirages non recalculables ({again.get('motif', 'motif non précisé')})")
            net, tr = np.asarray(again["tirages_net"], float), np.asarray(again["tirages_tr"], float)
            med = float(np.median(net))
            same = _ok(dist.get("mediane")) and abs(med - float(dist["mediane"])) < 1e-9
            return {"net": net, "tr": tr, "conforme": same, "mediane_recalculee": med}

        return self.lazy("draws", "tirages du bootstrap", compute)


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------


@dataclass
class SectionResult:
    """Résultat de la construction d'une section : ``statut`` ∈ ``ok`` / ``indisponible`` / ``erreur``."""

    id: str
    titre: str
    statut: str
    message: str = ""
    duree_s: float = 0.0
    #: code de sortie de l'erreur (:func:`brvm_alpha.erreurs.code_retour`) : 1 indisponible, 8 configuration…
    code: int | None = None


@dataclass
class RapportHTML:
    """Rapport rendu : ``html`` (document complet), ``sections`` (statut de chaque section), ``meta``."""

    html: str
    sections: list[SectionResult]
    asof: pd.Timestamp | None
    meta: dict[str, Any] = field(default_factory=dict)
    #: fichier écrit par :meth:`write` (``None`` tant que le rapport n'est qu'en mémoire)
    chemin: Path | None = None

    def statuts(self) -> dict[str, str]:
        return {s.id: s.statut for s in self.sections}

    def write(self, path: str | Path) -> Path:
        """Écrit le rapport de façon **atomique** (fichier temporaire voisin, ``fsync``, renommage) : un lecteur voit
        l'ancien rapport ou le nouveau, jamais un fichier à moitié écrit. Mode embarqué : jamais dans le code."""
        p = _fichiers.ecrire_atomique(Path(path), self.html)
        self.chemin = p
        return p


def _error_box(title: str, exc: BaseException) -> H:
    if isinstance(exc, DependencyError):
        orig, tb, what = exc.original, exc.tb, f"calcul « {exc.label} » en échec"
    else:
        orig, tb, what = exc, traceback.format_exc(), "erreur pendant la construction"
    msg = f"{orig.__class__.__name__} : {orig}"
    tail = "\n".join([ln for ln in (tb or "").strip().splitlines()][-12:])
    body = H(f"{esc(what)} : <code>{esc(msg[:600])}</code>. Les autres sections ne sont pas affectées."
             + (f'<details class="tb"><summary>Trace technique</summary><pre>{esc(tail)}</pre></details>' if tail
                else ""))
    return _box("err", f"Section « {title} » indisponible", body)


def _run_section(sid: str, title: str, lead: Any, fn: Callable[[], Any], results: list[SectionResult],
                 heading: bool = True) -> H:
    t = time.perf_counter()
    status, msg, code = "ok", "", None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            body = _h(fn())
    except Unavailable as exc:
        status, msg, code = "indisponible", str(exc), _erreurs.DONNEES_ABSENTES
        body = _box("info", f"{title} : données ou module indisponible", str(exc))
    except MemoryError:  # mémoire insuffisante : la commande s'arrête (code 6), pas un encadré
        raise
    except Exception as exc:  # noqa: BLE001 - encadré lisible, le rapport continue
        orig = exc.original if isinstance(exc, DependencyError) else exc
        if isinstance(orig, MemoryError):
            raise orig
        status, msg, code = "erreur", f"{exc.__class__.__name__} : {exc}", _erreurs.code_retour(orig)
        body = _error_box(title, exc)
    results.append(SectionResult(sid, title, status, msg, round(time.perf_counter() - t, 2), code))
    head = f'<h2>{esc(title)}</h2>' + (f'<p class="lead">{_h(lead)}</p>' if lead else "") if heading else ""
    return H(f'<section id="{esc(sid)}" data-statut="{esc(status)}">{head}{body}</section>')


# -- 1. Bandeau ------------------------------------------------------------------------------


def _sec_bandeau(ctx: _Ctx) -> H:
    val = ctx.try_get("validation", "résultats du test S1", ctx.validation) or {"execute": False, "etat": "illisible",
                                                                               "avertissements": []}
    st = _strategy_status(val)
    t = ctx.try_get("t", "date des données", ctx.t)
    od = ctx.try_get("order_dict", "ordre de bataille", ctx.order_dict)
    v = (od or {}).get("variante")
    vdesc = _get(od, "choix", "description", default="")
    when = ctx.now.tz_convert("UTC").strftime("%d/%m/%Y à %H:%M UTC")
    title = f"BRVM Alpha — rapport au {fmt_date(t) if t is not None else fmt_date(ctx.asof_req)}"
    sub = (f"Données : bulletin officiel de la cote du {fmt_date(t) if t is not None else 'n.d.'}"
           + (f" (date demandée : {fmt_date(ctx.asof_req)})" if t is not None and t != ctx.asof_req else "")
           + f" · capital {fmt_fcfa(ctx.capital)} · généré le {when}")
    chip = _status_chip(st["code"]) if val.get("execute") else _chip(st["label"], "warn")
    banner = H(f'<div class="banner" role="note"><span class="bi" aria-hidden="true">⚠</span><div>'
               f'<strong>{esc(BANNER)} Statut : {esc(st["code"])}.</strong>'
               f'<p>{esc(st["phrase"])}</p></div></div>')
    tiles = _tiles([
        ("Date des données", fmt_date(t) if t is not None else "n.d.", "dernière séance du panel ≤ date demandée",
         "fait"),
        ("Capital", fmt_fcfa(ctx.capital), "titres détenus compris" if ctx.holdings else "entièrement en liquidités",
         "fait"),
        ("Statut de la stratégie", chip, "lu dans metrics.json du test S1" if val.get("execute") else
         "reports/validation_S1/metrics.json absent", "fait"),
        ("Variante appliquée", v or "n.d.", vdesc or "ordre de bataille indisponible", None),
        ("Mode", st["mode"], "étude / paper trading / promu (§8.3)", None),
    ])
    warns = list(val.get("avertissements") or [])
    toc = "".join(f'<a href="#{esc(sid)}">{esc(lab)}</a>' for sid, lab in SECTIONS[1:])
    gaps = _gaps_summary(ctx)
    late = None
    try:  # même règle que l'ordre de bataille : la séance du jour compte après 15h00 UTC
        from brvm_alpha.portfolio.recommend import stale_panel_message

        if t is not None and t >= pd.Timestamp(ctx.asof_req).normalize():
            late = stale_panel_message(t, ctx.now, orders=True)
    except Exception:
        late = None
    if late:
        warns_late = [str(late).replace("`", "")]
    else:
        warns_late = []
    hist = ctx.historique or {}
    hist_box = ""
    if hist and not hist.get("complet", True):
        # Avertissement fort, en tête : sur un historique partiel, distribution et signaux peuvent être faux.
        hist_box = _box("err", "Historique incomplet : chiffres à ne pas utiliser tels quels",
                        str(hist.get("avertissement") or hist.get("raison") or "historique incomplet"))
    limits = H('<p class="sub limits" role="note"><strong>Limites à lire d\'abord.</strong> '
               + esc((f"Données : {gaps} ; " if gaps else "Données : pas de BOC avant 2017, trous en 2021 ; ")
                     + "le test S1 a été relancé une fois pour un défaut de mesure (D12) ; points ouverts : indice TR des "
                       "signaux non strictement daté, REF investi à 82 % en moyenne sur S1, plancher D1 et âge des "
                       "ordres pendant les trous de 2021. Détail : ")
               + '<a href="#methode">Méthode et limites</a>.</p>')
    return H(f'<header class="top"><div class="hrow"><h1>{esc(title)}</h1>'
             f'<button type="button" class="toggle" id="theme-toggle" aria-label="Changer de thème">Thème : auto</button>'
             f'</div><p class="sub">{esc(sub)}</p></header>{banner}{hist_box}'
             + "".join(_box("warn", "Données en retard", w) for w in warns_late) + f'{limits}{tiles}'
             + "".join(_box("warn", "Avertissement", w) for w in warns)
             + f'<nav class="toc" aria-label="Sommaire">{toc}</nav>')


def _gaps_summary(ctx: _Ctx) -> str | None:
    """« 129 séances sans BOC, dont 96 en 2021 » d'après ``sessions.parquet`` ; ``None`` sans calendrier."""
    try:
        sess = ctx.long("sessions")
        if sess is None or "available" not in sess.columns or not len(sess):
            return None
        miss = sess[~sess["available"].astype(bool)]
        years = (miss["year"] if "year" in miss.columns else pd.to_datetime(miss["date"], errors="coerce").dt.year)
        by_year = years.dropna().astype(int).value_counts()
        if not len(miss) or not len(by_year):
            return f"{fmt_int(len(miss))} séance(s) sans BOC"
        y, n = int(by_year.idxmax()), int(by_year.max())
        return f"{fmt_int(len(miss))} séances sans BOC, dont {fmt_int(n)} en {y}"
    except Exception:  # le bandeau ne tombe jamais pour un calendrier illisible
        return None


# -- 2. Marché -------------------------------------------------------------------------------


def _valuation_band(prime: float | None) -> str | None:
    if not _ok(prime):
        return None
    return "chère" if prime < 1.0 else "bon marché" if prime > 4.0 else "neutre"


#: Libellés affichés des bandes de valorisation (clé historique « chère » ; accord : marché « cher »).
_BAND_LABEL = {"chère": "cher"}


def _market_snapshot(ctx: _Ctx) -> dict[str, Any]:
    t = ctx.t()
    out: dict[str, Any] = {"t": t}
    ix = ctx.long("indices")
    if ix is not None and len(ix):
        ix = ix.copy()
        ix["date"] = pd.to_datetime(ix["date"])
        ix = ix[ix["date"] <= t]
        for name in ("BRVM COMPOSITE", "BRVM COMPOSITE TOTAL RETURN", "BRVM 30", "BRVM PRESTIGE", "BRVM PRINCIPAL"):
            s = ix[ix["index"] == name].sort_values("date")
            if len(s):
                r = s.iloc[-1]
                out[name] = {"level": r.get("level"), "date": r["date"], "chg": r.get("change_pct"),
                             "ytd": r.get("ytd_pct"), "stale": pd.Timestamp(r["date"]) < t}
    mk = ctx.long("market")
    if mk is None:
        P = ctx.try_get("panels", "panels", ctx.panels)
        mk = P.get("market") if isinstance(P, Mapping) and isinstance(P.get("market"), pd.DataFrame) else None
    if mk is not None and len(mk):
        m = mk.copy()
        if "date" in m.columns:
            m["date"] = pd.to_datetime(m["date"])
            m = m.set_index("date")
        m = m.sort_index()
        m = m[m.index <= t]
        if len(m):
            last = m.iloc[-1]
            out["market"] = {k: last.get(k) for k in ("market_cap", "avg_per", "risk_premium", "avg_yield_pct",
                                                       "n_up", "n_down", "n_unchanged", "value", "n_traded",
                                                       "n_listed")}
            out["market_date"] = m.index[-1]
            try:
                from brvm_alpha.quant import macro

                out["rf"] = float(macro.ref_govt_rate(m.reset_index(), asof=t))
            except Exception as exc:  # noqa: BLE001 - repli sans ref_govt_rate
                out["rf_err"] = f"{exc.__class__.__name__} : {exc}"
    if "BRVM COMPOSITE TOTAL RETURN" not in out:
        P = ctx.try_get("panels", "panels", ctx.panels)
        mtr = P.get("market_tr") if isinstance(P, Mapping) else None
        if mtr is not None:
            s = pd.Series(mtr, dtype=float).dropna()
            s = s[s.index <= t]
            if len(s):
                prev = s[s.index.year < t.year]
                out["TR_reconstruit"] = {"level": float(s.iloc[-1]), "date": s.index[-1],
                                         "ytd": float(s.iloc[-1] / prev.iloc[-1] - 1) * 100 if len(prev) else None}
    return out


def _sec_marche(ctx: _Ctx) -> H:
    snap = ctx.lazy("market", "instantané du marché", lambda: _market_snapshot(ctx))
    t = snap["t"]

    def idx_tile(name: str, label: str) -> tuple[Any, Any, Any, str | None]:
        r = snap.get(name)
        if not r:
            return (label, "n.d.", "absent du panel", None)
        s = []
        if _ok(r.get("chg")):
            s.append(f"séance {fmt_num(r['chg'], 2, True)}{NBSP}%")
        if _ok(r.get("ytd")):
            s.append(f"depuis le 31/12 {fmt_num(r['ytd'], 2, True)}{NBSP}%")
        if r.get("stale"):
            s.append(f"au {fmt_date(r['date'])}")
        return (label, fmt_num(r.get("level"), 2), " · ".join(s) or "BOC", "fait")

    tiles = [idx_tile("BRVM COMPOSITE", "BRVM Composite")]
    if snap.get("BRVM COMPOSITE TOTAL RETURN"):
        lab, v, s, _ = idx_tile("BRVM COMPOSITE TOTAL RETURN", "Composite TR")
        tiles.append((lab, v, s + " · officiel (avis 308-2025)", "fait"))
    elif snap.get("TR_reconstruit"):
        r = snap["TR_reconstruit"]
        tiles.append(("Composite TR", fmt_num(r["level"], 2),
                      (f"depuis le 31/12 {fmt_num(r['ytd'], 2, True)}{NBSP}% · " if _ok(r.get("ytd")) else "")
                      + "reconstruit (dividendes nets réinvestis)", "estimation"))
    else:
        tiles.append(("Composite TR", "n.d.", "absent du panel", None))
    tiles += [idx_tile("BRVM 30", "BRVM 30"), idx_tile("BRVM PRESTIGE", "BRVM Prestige")]
    m = snap.get("market") or {}
    prime = float(m["risk_premium"]) if _ok(m.get("risk_premium")) else None
    band = _valuation_band(prime)
    tiles += [
        ("Capitalisation", (fmt_num(float(m["market_cap"]) / 1e9, 0) + NBSP + "Md FCFA") if _ok(m.get("market_cap"))
         else "n.d.", "actions, au BOC", "fait" if _ok(m.get("market_cap")) else None),
        ("PER du marché", fmt_num(m.get("avg_per"), 2), "PER moyen publié au BOC", "fait" if _ok(m.get("avg_per"))
         else None),
        ("Prime de risque du BOC", H(esc(fmt_num(prime, 2)) + " " + (_chip(_BAND_LABEL.get(band, band),
                                                                            {"chère": "no", "bon marché": "ok"}
                                                                            .get(band, "")) if band else "")),
         "bandes : cher < 1 ; neutre 1-4 ; bon marché > 4 (§4.5)", "fait" if band else None),
        ("Taux de référence (rf)", fmt_pct(snap.get("rf"), 2) if _ok(snap.get("rf")) else "n.d.",
         "100/PER − prime, médiane 20 séances (§4.1)" if _ok(snap.get("rf")) else snap.get("rf_err", "non calculable"),
         "estimation" if _ok(snap.get("rf")) else None),
    ]
    parts = [_tiles(tiles)]
    facts = []
    if _ok(m.get("n_up")) and _ok(m.get("n_down")):
        facts.append(f"Séance du {fmt_date(snap.get('market_date', t))} : {fmt_int(m['n_up'])} hausses, "
                     f"{fmt_int(m['n_down'])} baisses" + (f", {fmt_int(m['n_unchanged'])} inchangés"
                                                          if _ok(m.get("n_unchanged")) else "")
                     + (f" ; valeur échangée {fmt_fcfa(m['value'])}" if _ok(m.get("value")) else "") + ".")
    if _ok(m.get("avg_yield_pct")):
        facts.append(f"Rendement moyen du marché publié au BOC : {fmt_num(m['avg_yield_pct'], 2)}{NBSP}% (dividendes "
                     "nets).")
    if facts:
        parts.append(_ul(facts))
    if band == "chère":
        parts.append(_box("warn", "Marché « cher » selon la prime du BOC (§4.5).",
                          "C'est une information, jamais un signal de timing : l'exposition ne change pas. Comme le "
                          "prévoit la spécification, les stress tests du §9.3 sont présentés en tête de la section "
                          "« Distribution à 12 mois »."))
    return _join(parts)


# -- 3. Résultat du test S1 ------------------------------------------------------------------


def _variant_desc() -> dict[str, str]:
    try:
        from brvm_alpha.strategy import VARIANT_SPECS

        return {k: str(v.description) for k, v in VARIANT_SPECS.items()}
    except Exception:  # noqa: BLE001 - descriptions facultatives
        return {}


def _nav_curves(vdir: Path, m: Mapping[str, Any]) -> tuple[list[pd.Timestamp], list[dict[str, Any]], str] | None:
    """Courbes rebasées à t0 (base 100 à la veille de t0) lues dans ``nav.parquet`` (ou reconstituées
    depuis ``weekly_returns.parquet``), à la fréquence hebdomadaire."""
    want = [("A_central_10M", "A (principal)", "1", False), ("I_central_10M", "I (cœur-satellite)", "2", False),
            ("REF_central_10M", "REF (indice discipliné)", "3", False),
            ("ETALON_TR", "Composite TR (étalon)", "ink", True), ("ETALON_EW", "Panier équipondéré EW", "muted", True)]
    frames: dict[str, pd.Series] = {}
    source = ""
    nav_p = vdir / "nav.parquet"
    if nav_p.exists():
        nav = pd.read_parquet(nav_p)
        if {"date", "serie", "base_t0"} <= set(nav.columns):
            for sid, *_ in want:
                s = nav.loc[nav["serie"] == sid, ["date", "base_t0"]].dropna()
                if len(s):
                    frames[sid] = pd.Series(s["base_t0"].to_numpy(float), index=pd.DatetimeIndex(s["date"]))
            source = "nav.parquet (valeurs liquidatives et niveaux rebasés à t0)"
    if not frames:
        wr_p = vdir / "weekly_returns.parquet"
        if wr_p.exists():
            wr = pd.read_parquet(wr_p)
            if "semaine" in wr.columns:
                wr = wr.set_index("semaine")
            wr.index = pd.DatetimeIndex(wr.index)
            for sid, *_ in want:
                if sid in wr.columns:
                    r = wr[sid].astype(float)
                    lvl = 100.0 * (1.0 + r.fillna(0.0)).cumprod()
                    frames[sid] = lvl
            source = "weekly_returns.parquet (rendements hebdomadaires nets cumulés, base 100 à t0)"
    if not frames:
        return None
    wk = {k: v.sort_index().resample("W-FRI").last() for k, v in frames.items()}
    idx = sorted(set().union(*[set(v.index) for v in wk.values()]))
    dates = [pd.Timestamp(d) for d in idx]
    series = []
    for sid, name, slot, dash in want:
        if sid in wk:
            s = wk[sid].reindex(idx)
            series.append({"name": name, "slot": slot, "dash": dash, "values": list(s.to_numpy(float))})
    return dates, series, source


def _window_note(m: Mapping[str, Any]) -> str:
    """Rappel sous le graphique des VL : les niveaux tracés comprennent la variation pendant la fenêtre du §8.1,
    exclue de toutes les mesures du tableau (le niveau final ne se lit pas comme le rendement annualisé)."""
    wins = [w for w in m.get("fenetres_exclues") or [] if isinstance(w, (list, tuple)) and len(w) == 2]
    if not wins:
        return ""
    txt = " ; ".join(f"{fmt_date(a)} → {fmt_date(b)}" for a, b in wins)
    return (f" Les niveaux tracés comprennent la variation pendant la fenêtre du §8.1 ({txt}), exclue de toutes les "
            "mesures du tableau : le niveau final ne se lit donc pas comme le rendement annualisé publié.")


def _criteria_text(vd: Mapping[str, Any], codes: Sequence[str]) -> list[str]:
    """Libellé, valeur et seuil des critères du §8.3 déclenchés (lus dans ``metrics.json``)."""
    crit = {str(c.get("code")): c for c in vd.get("criteres") or [] if isinstance(c, Mapping)}
    out = []
    for code in codes:
        c = crit.get(str(code))
        if c is None:
            out.append(str(code))
            continue
        lab = str(c.get("libelle", ""))
        is_ir = lab.startswith("IR") or " IR " in f" {lab} "

        def one(v: Any, is_ir: bool = is_ir) -> str:
            return fmt_num(v, 2, True) if is_ir else fmt_pct(v, 1, True)

        v = c.get("valeur")
        vtxt = " / ".join(one(x) for x in v) if isinstance(v, (list, tuple)) else one(v)
        out.append(f"{code} : {lab} = {vtxt} (seuil {_fr_txt(c.get('seuil', 'n.d.'))})")
    return out


def _interpretation(m: Mapping[str, Any]) -> list[str]:
    """Lecture honnête du résultat (jamais une promesse) à partir de ``metrics.json``."""
    V = m.get("variantes") or {}
    runs = m.get("runs") or {}
    fam = m.get("famille") or {}
    a = V.get("A") or {}
    st = _norm_status(a.get("statut")) or "INDÉTERMINÉ"
    ra = runs.get(a.get("run_id") or "A_central_10M") or {}
    P: list[str] = []
    if st == "REJETÉ":
        trig = list(a.get("rejets_declenches") or [])
        P.append(f"La variante principale A est REJETÉE sur S1 : {len(trig)} condition(s) de rejet du §8.3 sont vraies "
                 f"({' ; '.join(_criteria_text(a, trig)) or 'détail absent'}). Conformément au protocole écrit avant "
                 "l'exécution, la plate-forme passe en mode « indice discipliné » (REF, D8) : aucune promesse d'alpha, "
                 "la recherche continue.")
    elif st == "CANDIDAT":
        P.append("La variante principale A satisfait les sept critères « candidat » du §8.3 sur S1. Cela autorise le "
                 "suivi réel (paper trading, à partir du 01/12/2026), pas l'argent réel : le statut PROMU exige en plus "
                 "les filtres G1-G9 sur S1 et sur au moins 12 mois de suivi réel (D7).")
    elif st == "PROMU":
        P.append("Statut PROMU : à vérifier avec soin, car il exige au moins 12 mois de suivi réel S2 (D7), qui "
                 "commence le 01/12/2026.")
    else:
        miss = list(a.get("criteres_candidat_non_verifies") or [])
        P.append(f"Le statut de A est {st} : ni rejet ni candidature"
                 + (f" (critères candidat non vérifiés : {', '.join(map(str, miss))})" if miss else "")
                 + ". D7 : aucun suivi réel n'est autorisé ; l'ordre de bataille suit REF.")
    act, ir = ra.get("actif_tr_an"), ra.get("ir_tr")
    if _ok(act):
        P.append(f"Sur [t0 ; fin], A fait {fmt_pct(ra.get('rendement_an'))} par an, soit {fmt_pct(act, 1, True)} par "
                 f"an contre le Composite TR (IR {fmt_num(ir)}), net de tous les coûts (estimation).")
    bi = ra.get("bootstrap_ir") or {}
    lo, up = bi.get("lower"), bi.get("upper")
    if _ok(lo) and _ok(up):
        rng = f"[{fmt_num(lo)} ; {fmt_num(up)}]"
        if float(lo) <= 0 <= float(up):
            P.append(f"L'intervalle de confiance à 95 % de l'IR de A {rng} (bootstrap stationnaire) contient zéro : sur "
                     "environ six ans, le test ne permet pas de distinguer un alpha réel du hasard.")
        elif float(lo) > 0:
            P.append(f"L'intervalle de confiance à 95 % de l'IR de A {rng} est entièrement positif : c'est un indice "
                     "favorable, obtenu sur un seul échantillon ; il ne garantit rien pour la suite (§10).")
        else:
            P.append(f"L'intervalle de confiance à 95 % de l'IR de A {rng} est entièrement négatif : la "
                     "sous-performance contre le TR est nette sur S1.")
    if _ok(ir) and float(ir) > 1:
        P.append("IR > 1 : le §8.3 impose de traiter d'abord un tel chiffre comme une ERREUR à rechercher (biais "
                 "d'anticipation, prix périmés, coûts oubliés) avant toute conclusion.")
    subs = [s for s in ra.get("sous_periodes") or [] if isinstance(s, Mapping)]
    sg = [float(s["actif_tr_an"]) for s in subs if _ok(s.get("actif_tr_an"))]
    if len(sg) >= 2:
        if all(x > 0 for x in sg):
            P.append("Le rendement actif de A est positif dans les deux sous-périodes.")
        elif all(x < 0 for x in sg):
            P.append("Le rendement actif de A est négatif dans les deux sous-périodes.")
        else:
            P.append("Le signe du rendement actif de A change d'une sous-période à l'autre : le résultat n'est pas "
                     "stable.")
    pbo = fam.get("pbo")
    if _ok(pbo):
        q = ("élevée (> 0,5 : le critère candidat C6 échoue)" if float(pbo) > 0.5 else
             "modérée (≤ 0,5 mais > 0,25 : insuffisant pour G4)" if float(pbo) > 0.25 else "faible (≤ 0,25)")
        P.append(f"Probabilité de surapprentissage de la famille des 9 variantes (PBO, CSCV) : {fmt_num(pbo, 2)}, {q}.")
    pr = m.get("promotion") or {}
    if pr.get("principal") and str(pr.get("principal")) != "A":
        P.append(f"Règle de promotion du §3.4 : la variante {pr['principal']} remplace A (elle bat A en actif net, avec "
                 "DSR ≥ 0,95 et PBO ≤ 0,25).")
    ref = V.get(REF) or {}
    rr = runs.get(ref.get("run_id") or "REF_central_10M") or {}
    if _ok(rr.get("actif_tr_an")):
        inv = rr.get("part_investie_moyenne")
        txt = (f"La référence investissable REF (indice discipliné, hors famille) fait {fmt_pct(rr['actif_tr_an'], 1, True)} "
               "par an contre le TR. Cet écart ne vient pas seulement des frais, des plafonds et des règles de risque")
        if _ok(inv):
            txt += (f" : REF n'a été investi qu'à {fmt_pct(inv, 0)} en moyenne sur S1 (cible 98 %), et il est passé en "
                    "liquidités d'août à octobre 2021, pendant les trous de BOC, alors que le TR montait (plancher D1 "
                    "des filtres et âge des ordres : points ouverts, section « Méthode et limites »)")
        P.append(txt + ".")
    P.append(f"Comparaison avec la prédiction écrite d'avance : le statut le plus probable était « candidat », et le "
             f"rejet de A était jugé plausible ; le résultat observé est « {st} ».")
    once = ("un seul test (relancé une fois pour un défaut de mesure prouvé, D12 : voir l'encadré en tête de section)"
            if _rerun_info(m) is not None else "un seul test")
    P.append(f"Rappel : {once}, sur environ six ans d'un marché dont la liquidité a été multipliée par environ 30 "
             "depuis 2019-2020 (§10.9). Ces chiffres sont des estimations, pas des promesses.")
    return P


def _short(commit: Any) -> str:
    return str(commit or "n.d.")[:7]


def _sub_end(b: Any, fin: Any) -> str:
    """Fin d'une sous-période, bornée à la fin de la fenêtre : metrics.json porte l'étiquette de semaine
    (vendredi 18/11/2022) alors qu'aucune donnée n'est comptée après la fin (16/11/2022)."""
    try:
        tb, tf = pd.Timestamp(b), pd.Timestamp(fin)
        if tb > tf:
            return f"{fmt_date(tf)} (semaine du vendredi {fmt_date(tb)})"
    except (TypeError, ValueError):
        pass
    return fmt_date(b)


def _rerun_info(m: Mapping[str, Any]) -> dict[str, Any] | None:
    """Relance motivée (D12) lue dans ``metrics.json`` : ``None`` si le test n'a été exécuté qu'une fois."""
    ex = m.get("execution") or {}
    rel = ex.get("relance") if isinstance(ex.get("relance"), Mapping) else None
    prev = m.get("precedent") if isinstance(m.get("precedent"), Mapping) else None
    if not rel and not prev:
        return None
    pex = (prev or {}).get("execution") or (rel or {}).get("verrou_precedent") or {}
    V = m.get("variantes") or {}
    st_prev = {str(k): _norm_status(v) for k, v in ((prev or {}).get("statuts") or {}).items()}
    st_now = {str(k): _norm_status((d or {}).get("statut")) for k, d in V.items() if isinstance(d, Mapping)}
    same = bool(st_prev) and all(st_now.get(k) == v for k, v in st_prev.items())
    return {"motif": str((rel or {}).get("motif") or "").strip(), "commit_prev": pex.get("commit"),
            "quand_prev": pex.get("horodatage_utc"), "commit": ex.get("commit"), "quand": ex.get("horodatage_utc"),
            "dossier": (prev or {}).get("dossier") or (rel or {}).get("precedent"), "t0_prev": (prev or {}).get("t0"),
            "statuts_inchanges": same if st_prev else None}


def _rerun_box(m: Mapping[str, Any]) -> H | None:
    """Encadré de tête de la section S1 : le test a été relancé une fois, quand et pourquoi (D12)."""
    r = _rerun_info(m)
    if r is None:
        return None
    body = (f"Premier passage le {_utc_txt(r['quand_prev'])} (commit {_short(r['commit_prev'])}), relance le "
            f"{_utc_txt(r['quand'])} (commit {_short(r['commit'])}). ")
    body += (f"Motif enregistré dans metrics.json : {r['motif']} " if r["motif"] else
             "Motif : voir reports/validation_S1/tentatives.md. ")
    if r["statuts_inchanges"] is True:
        body += "Les statuts des variantes et de la référence sont les mêmes aux deux passages. "
    elif r["statuts_inchanges"] is False:
        body += "Des statuts diffèrent entre les deux passages : voir tentatives.md. "
    where = _rel(r["dossier"]) if r["dossier"] else "reports/validation_S1/precedent_…"
    tail = ((f" (t0 précédent {fmt_date(r['t0_prev'])})" if r["t0_prev"] else "")
            + ", et les deux passages sont décrits dans reports/validation_S1/tentatives.md.")
    # Chemin relatif dans <code> : il se replie au lieu de déborder de l'encadré.
    html_body = H(esc(body + "Les chiffres de cette section sont ceux de la relance ; le premier résultat est "
                      "conservé dans ") + f"<code>{esc(where)}</code>" + esc(tail))
    return _box("warn", "Test unique, relancé une fois pour un défaut de mesure prouvé (D12).", html_body)


def _fingerprint_note(ex: Mapping[str, Any]) -> str:
    """Ce que vaut l'empreinte de configuration : jamais « pré-enregistrée » si elle ne l'est pas."""
    c = ex.get("empreinte_controle") if isinstance(ex.get("empreinte_controle"), Mapping) else {}
    if not c or not c.get("conforme"):
        return ""
    if c.get("preenregistree_independante") is True:
        return " (identique au pré-enregistrement)"
    frozen = _get(c, "etat_fige", "commit")
    ref = _get(c, "reference_preenregistrement", "commit")
    if frozen or ref or c.get("preenregistree_independante") is False:
        return (" (identique à l'état figé" + (f" {_short(frozen)}" if frozen else "")
                + (f" ; référence de pré-enregistrement : commit {_short(ref)}" if ref else "")
                + " ; pas une valeur pré-enregistrée indépendante)")
    return " (identique à l'état figé avant l'exécution)"


def _s1_tables(m: Mapping[str, Any]) -> list[H]:
    V = m.get("variantes") or {}
    runs = m.get("runs") or {}
    fam = m.get("famille") or {}
    desc = _variant_desc()
    order = [v for v in FAMILY if v in V] + ([REF] if REF in V else []) + [v for v in V if v not in FAMILY and v != REF]
    rows = []
    for v in order:
        d = V.get(v) or {}
        r = runs.get(d.get("run_id") or f"{v}_central_10M") or {}
        bi = r.get("bootstrap_ir") or {}
        ic = (f"[{fmt_num(bi.get('lower'))} ; {fmt_num(bi.get('upper'))}]" if _ok(bi.get("lower")) else "n.d.")
        rows.append([H(f"<b>{esc(v)}</b>" + (' <span class="muted">(réf.)</span>' if d.get("statut_informatif") or
                                              v == REF else "")
                       + f'<div class="muted small desc">{esc(desc.get(v, ""))}</div>'),
                     _num_cell(r.get("rendement_an")), _num_cell(r.get("actif_tr_an"), signed=True),
                     _num_cell(r.get("ir_tr"), "num", 2, True), ic, fmt_num(d.get("dsr_famille_n9"), 2),
                     fmt_num(d.get("dsr_registre"), 2), _num_cell(r.get("drawdown_relatif_tr"), signed=True),
                     fmt_pct(r.get("rotation_mensuelle_aller")), _status_chip(d.get("statut"))])
    bench = m.get("etalons") or {}
    foot_rows = []
    for code in ("TR", "EW"):
        b = bench.get(code) or {}
        mm = b.get("mesures") or {}
        if b:
            foot_rows.append([H(f"<b>{esc(code)}</b> <span class='muted'>étalon</span><div class='muted small desc'>"
                                f"{esc(b.get('libelle', ''))}</div>"), _num_cell(mm.get("rendement_an")), "—", "—", "—",
                              "—", "—", "—", "—", esc("disponible" if b.get("disponible") else "non disponible")])
    t1 = _table(["Variante", "Rdt annualisé", "Actif vs TR", "IR", "IR [IC 95 %]", "DSR (N = 9)",
                 f"DSR (N = {fam.get('n_registre', 'registre')})", "Drawdown relatif", "Rotation /mois", "Statut"],
                rows + foot_rows, left=(0,), cls="s1")
    # Sous-périodes.
    srows = []
    for v in order:
        d = V.get(v) or {}
        r = runs.get(d.get("run_id") or f"{v}_central_10M") or {}
        cells = []
        for sp in (r.get("sous_periodes") or [])[:3]:
            cells.append(H(f'{_num_cell(sp.get("actif_tr_an"), signed=True)} <span class="muted">· IR '
                           f'{esc(fmt_num(sp.get("ir_tr")))} · {esc(sp.get("n_semaines", "n.d."))} sem.</span>'))
        srows.append([H(f"<b>{esc(v)}</b>")] + cells + [""] * max(0, 2 - len(cells)))
    subs = m.get("sous_periodes") or []
    sh = ["Variante"] + [f"Actif vs TR [{fmt_date(a)} ; {_sub_end(b, m.get('fin'))}]" for a, b in subs[:2]]
    while len(sh) < 3:
        sh.append(f"Sous-période {len(sh)}")
    t2 = _table(sh, srows)
    # Sensibilités.
    krows = []
    for rid, r in runs.items():
        if not isinstance(r, Mapping) or r.get("role") != "sensibilité":
            continue
        krows.append([H(f"<b>{esc(r.get('variante', rid))}</b> <span class='muted'>coûts "
                        f"{esc(COSTS_FR.get(str(r.get('couts')), r.get('couts')))}, {esc(fmt_capital(r.get('capital')))}"
                        "</span>"), _num_cell(r.get("rendement_an")), _num_cell(r.get("actif_tr_an"), signed=True),
                      _num_cell(r.get("ir_tr"), "num", 2, True), _num_cell(r.get("drawdown_relatif_tr"), signed=True),
                      fmt_pct(r.get("rotation_mensuelle_aller")), fmt_pct(r.get("couts_an_pct_nav_moyenne"), 2),
                      fmt_pct(r.get("part_investie_moyenne"))])
    t3 = (_table(["Run", "Rdt annualisé", "Actif vs TR", "IR", "Drawdown relatif", "Rotation /mois", "Coûts /an",
                  "Investi"], krows) if krows else _box("empty", "Aucune analyse de sensibilité dans metrics.json."))
    return [t1, t2, t3]


def _diag_block(ctx: _Ctx) -> H:
    dg = ctx.try_get("diagnostic", "diagnostic S0", ctx.diagnostic)
    if not dg or not dg.get("execute"):
        return H("")
    m = dg["metrics"]
    V = m.get("variantes") or {}
    runs = m.get("runs") or {}
    rows = []
    for v in [x for x in FAMILY if x in V] + ([REF] if REF in V else []):
        d = V[v]
        r = runs.get(d.get("run_id")) or {}
        rows.append([H(f"<b>{esc(v)}</b>"), _num_cell(r.get("rendement_an")), _num_cell(r.get("actif_tr_an"), signed=True),
                     _num_cell(r.get("ir_tr"), "num", 2, True), _num_cell(r.get("drawdown_relatif_tr"), signed=True),
                     esc(_norm_status(d.get("statut")) or "n.d.")])
    body = _join([
        _box("warn", "S0 (2022-11-17 → 2026-11-20) est contaminé : aucune valeur de preuve.",
             "Cet échantillon a été exploré par les revues et par la mise au point du moteur ; ces chiffres vérifient "
             "que la chaîne tourne, jamais la valeur de la stratégie. Ils sont inscrits au registre et comptent dans N."),
        _p(f"t0 = {fmt_date(m.get('t0'))} ; fin {fmt_date(m.get('fin'))} ; PBO de la famille "
           f"{fmt_num(_get(m, 'famille', 'pbo'), 2)} (diagnostic)."),
        _table(["Variante", "Rdt annualisé", "Actif vs TR", "IR", "Drawdown relatif", "Statut (diagnostic)"], rows),
    ])
    return _details("Diagnostic S0 (contaminé, pour information seulement)", body)


def _sec_s1(ctx: _Ctx) -> H:
    val = ctx.validation()
    if not val.get("execute"):
        etat = val.get("etat")
        lock = val.get("lock") or {}
        title = {"en cours": "Test S1 en cours d'exécution.",
                 "échec": "Test S1 en échec : aucune métrique calculée ni publiée."}.get(str(etat), "Test S1 non exécuté.")
        msg = ("Le test unique sur l'échantillon vierge S1 (02/01/2017 → 16/11/2022) n'a pas encore produit de "
               "résultats lisibles dans " + _rel(val.get("dossier")) + ". Aucune variante n'est validée : cette section "
               "affichera, après l'exécution de « python -m brvm_alpha validate --sample S1 », le statut des 9 variantes "
               "et de la référence, les courbes rebasées à t0, les sous-périodes, les sensibilités et la PBO.")
        if lock.get("horodatage_utc"):
            msg += f" Verrou du {_utc_txt(lock.get('horodatage_utc'))} (commit {str(lock.get('commit') or 'n.d.')[:12]})."
        parts = [_box("info" if etat != "échec" else "err", title, msg)]
        parts.append(_box("info", "Rappel.", PREDICTION_8_3))
        parts.append(_diag_block(ctx))
        return _join(parts)
    m = val["metrics"]
    vdir = ctx.validation_dir
    ex = m.get("execution") or {}
    fam = m.get("famille") or {}
    subs = m.get("sous_periodes") or []
    parts: list[Any] = []
    if m.get("bandeau") and BANNER not in str(m.get("bandeau")):
        parts.append(_box("warn", "Bandeau de metrics.json inattendu", str(m.get("bandeau"))))
    rerun = _rerun_box(m)
    if rerun is not None:  # en tête : le lecteur sait d'emblée que le test a connu deux passages, et pourquoi
        parts.append(rerun)
    parts.append(_tiles([
        ("t0 (D2)", fmt_date(m.get("t0")), "première séance investie de A (10 M FCFA, coûts centraux)", "fait"),
        ("Fin de la fenêtre", fmt_date(m.get("fin")), "sous-périodes " + (" et ".join(
            f"{fmt_date(a)} → {_sub_end(b, m.get('fin'))}" for a, b in subs[:2]) or "n.d."), "fait"),
        ("Statut de A", _status_chip(val.get("statut_A")), f"principal après §3.4 : {val.get('principal')}", "fait"),
        ("PBO (famille, N = 9)", fmt_num(fam.get("pbo"), 2), f"CSCV, {fam.get('n_blocs', 'n.d.')} blocs ; pente "
         f"{fmt_num(fam.get('pente_degradation'), 2)}", "estimation"),
        ("Essais au registre", fmt_int(fam.get("n_registre")), "N du DSR « registre » et du haircut BHY", "fait"),
        ("Contrôles comptables", "verts" if _get(m, "controles", "tous_ok") else "à examiner",
         f"{len(_get(m, 'controles', 'runs_en_anomalie', default=[]))} run(s) en anomalie", "fait"),
    ]))
    parts.append(_p(f"{'Relance motivée (D12)' if rerun is not None else 'Exécution unique'} : commit "
                    f"{str(ex.get('commit') or 'n.d.')[:12]}, empreinte de configuration "
                    f"{ex.get('empreinte_config', 'n.d.')}" + _fingerprint_note(ex)
                    + f", {_utc_txt(ex.get('horodatage_utc'))}, mode de décision {ex.get('mode_decision', 'n.d.')}, "
                    f"bootstrap n = {m.get('n_boot', 'n.d.')} (blocs de {m.get('bloc_moyen_semaines', 'n.d.')} "
                    "semaines). Métriques hebdomadaires nettes de tous les coûts, sur [t0 ; fin], rebasées à t0.",
                    "muted small"))
    t1, t2, t3 = _s1_tables(m)
    parts.append(_card(H("<h3>Les 9 variantes et la référence (coûts centraux, 10 M FCFA)</h3>"), t1,
                       _p("IR, PSR et DSR portent sur les rendements actifs nets contre le Composite TR. DSR : Sharpe "
                          "dégonflé (seuil 0,95). REF : référence investissable, hors famille de la PBO. Estimations.",
                          "muted small")))
    curves = _nav_curves(vdir, m) if vdir is not None else None
    if curves:
        dates, series, src = curves
        parts.append(_card(H("<h3>Valeur liquidative contre le Composite TR, base 100 à t0</h3>"),
                           line_chart("c-s1-nav", dates, series, label="VL des variantes A, I, REF et étalons TR, EW",
                                      caption=f"Source : {src}. Hebdomadaire (vendredi) ; les interruptions sont des semaines sans BOC "
                                              "disponible (surtout en 2021). Nets de coûts ; étalons sans coûts."
                                              + _window_note(m) + " Passez le doigt ou la souris sur le graphique.")))
    else:
        parts.append(_box("info", "Courbes indisponibles", "nav.parquet et weekly_returns.parquet absents ou illisibles."))
    parts.append(_card(H("<h3>Sous-périodes</h3>"), t2))
    parts.append(_card(H("<h3>Sensibilités : coûts et capacité</h3>"),
                       _p("Le même essai sous d'autres hypothèses de coûts ou de capital ; hors PBO et DSR.",
                          "muted small"), t3))
    pr = m.get("promotion") or {}
    if pr.get("criteres"):
        rows = [[H(f"<b>{esc(c.get('variante'))}</b>"), _num_cell(c.get("actif_net_an"), signed=True),
                 {True: "oui", False: "non"}.get(c.get("bat_reference"), "—"), fmt_num(c.get("dsr")),
                 {True: "oui", False: "non"}.get(c.get("dsr_ok"), "—"), {True: "oui", False: "non"}.get(c.get("pbo_ok"), "—"),
                 {True: "oui", False: "non"}.get(c.get("promue"), "—")] for c in pr["criteres"] if isinstance(c, Mapping)]
        parts.append(_card(H("<h3>Règle de promotion du §3.4</h3>"), _p(str(pr.get("regle", "")), "muted small"),
                           _table(["Variante", "Actif net an.", "Bat A", "DSR (N = 9)", "DSR ≥ 0,95", "PBO ≤ 0,25",
                                   "Remplace A"], rows)))
    parts.append(_box("info", "Rappel.", str(m.get("prediction_8_3") or PREDICTION_8_3)))
    parts.append(_card(H("<h3>Lecture du résultat</h3>"), _ul(_interpretation(m)),
                       _p("Les métriques sont des estimations sur environ six ans de données hebdomadaires ; seuls "
                          "les règles, les seuils et le plan des runs, figés avant l'exécution, sont des faits.",
                          "muted small")))
    parts.append(_diag_block(ctx))
    return _join(parts)


# -- 4. Ordre de bataille --------------------------------------------------------------------


def _aes_lambda_load(lines: Sequence[Mapping[str, Any]]) -> float | None:
    """Exposition économique λ du portefeuille cible au bloc AES : ``Σ poids_cible × λ_AES`` du titre
    (``reference.economic_exposure`` : 1 pour un siège BF, ML ou NE ; 0,238 pour SNTS, exposé au Mali)."""
    try:
        from brvm_alpha import reference as ref

        total = 0.0
        for r in lines:
            lam = ref.economic_exposure(str(r.get("symbole")))
            total += float(r.get("poids_cible") or 0.0) * sum(float(v) for c, v in lam.items() if c in AES)
        return total
    except Exception:  # table d'exposition indisponible : la ligne affiche « n.d. », jamais un chiffre faux
        return None


def _active_constraints(od: Mapping[str, Any]) -> list[list[Any]]:
    lines = [r for r in od.get("lignes") or [] if (r.get("cibles") or 0) > 0 or (r.get("poids_cible") or 0) > 0]
    expl = {str(e.get("symbole")): e for e in od.get("explications") or [] if e.get("statut") == "retenu"}
    rows: list[list[Any]] = []
    for r in lines:
        e = expl.get(str(r.get("symbole")))
        up = _get(e, "plafonds", "upper")
        w = r.get("poids_cible")
        if _ok(up) and _ok(w) and float(w) >= float(up) - 5e-4:
            rows.append([f"Plafond de ligne {r['symbole']}", fmt_pct(up, 2), fmt_pct(w, 2), _chip("active", "warn"),
                         _get(e, "plafonds", "line_detail", default="")])
    by_sec: dict[str, float] = {}
    by_cty: dict[str, float] = {}
    sec_cap: dict[str, float] = {}
    cty_cap: dict[str, float] = {}
    aes_caps: dict[str, float] = {}
    for r in lines:
        s, c, w = str(r.get("secteur")), str(r.get("pays")), float(r.get("poids_cible") or 0.0)
        by_sec[s] = by_sec.get(s, 0.0) + w
        by_cty[c] = by_cty.get(c, 0.0) + w
        e = expl.get(str(r.get("symbole")))
        if _ok(_get(e, "plafonds", "sector")):
            sec_cap[s] = float(e["plafonds"]["sector"])
        if _ok(_get(e, "plafonds", "country")):
            cty_cap[c] = float(e["plafonds"]["country"])
        for k, v in (_get(e, "plafonds", "aes", default={}) or {}).items():
            if _ok(v):
                aes_caps[str(k)] = float(v)
    for s, w in sorted(by_sec.items(), key=lambda x: -x[1]):
        cap = sec_cap.get(s)
        if cap is not None:
            act = w >= cap - 5e-4
            rows.append([f"Secteur {SECTEURS.get(s, s)}", fmt_pct(cap, 1), fmt_pct(w, 1),
                         _chip("active", "warn") if act else _chip("marge"), "§4.2, §6 (D8 pour REF)"])
    for c, w in sorted(by_cty.items(), key=lambda x: -x[1]):
        cap = cty_cap.get(c)
        if cap is not None and c != "CI":
            act = w >= cap - 5e-4
            rows.append([f"Pays {PAYS.get(c, c)}", fmt_pct(cap, 1), fmt_pct(w, 1),
                         _chip("active", "warn") if act else _chip("marge"), "§4.2"])
    # Deux plafonds, deux charges : « siège » = poids des titres dont le siège est au Burkina Faso, au Mali ou
    # au Niger ; « exposition λ » = Σ poids × part de l'activité du titre dans ces pays (SNTS : 23,8 % au Mali).
    # Jusqu'à la recette du 22/11/2026 la charge « siège » était affichée pour les deux (8,9 % au lieu de 14,9 %).
    w_seat = sum(w for c, w in by_cty.items() if c in AES)
    w_lam = _aes_lambda_load(lines)
    for k, cap in aes_caps.items():
        is_lam = "λ" in k or "lambda" in k.lower() or "exposition" in k.lower()
        load = w_lam if is_lam else w_seat
        if load is None:
            rows.append([k[:1].upper() + k[1:], fmt_pct(cap, 1), "n.d.", _chip("marge"), "§4.2 (exposition λ non calculable)"])
            continue
        act = load >= cap - 5e-4
        rows.append([k[:1].upper() + k[1:], fmt_pct(cap, 1), fmt_pct(load, 1),
                     _chip("active", "warn") if act else _chip("marge"),
                     "§4.2 (Σ poids × part de l'activité au BF, au ML et au NE)" if is_lam else "§4.2 (BF + ML + NE)"])
    ex = od.get("execution") or {}
    for s, why in (ex.get("reductions") or {}).items():
        rows.append([f"Quantité réduite {s}", "—", "—", _chip("active", "warn"), str(why)])
    for s in ex.get("participation_depassee") or []:
        rows.append([f"Participation {s}", "10 % de la MDV63", "dépassée", _chip("active", "warn"), "signalée (§7.1)"])
    k = od.get("couts") or {}
    if _ok(k.get("cible_pct")) and _ok(k.get("investi_pct")):
        rows.append(["Exposition cible", fmt_pct(k["cible_pct"], 1), fmt_pct(k["investi_pct"], 2),
                     _chip("arrondi"), f"reliquat d'arrondi {fmt_fcfa(k.get('reliquat_arrondi'))} (quotité 1, arrondi "
                                       "vers le bas)"])
    return rows


def _explicit_costs(k: Mapping[str, Any], lines: Sequence[Mapping[str, Any]]) -> float:
    """Frais explicites des deux sens (achats ET ventes) : clé ``explicites`` de l'ordre de bataille, sinon
    somme des ``frais_explicites`` des lignes (avant le 22/11/2026, la tuile ignorait les ventes)."""
    if _ok(k.get("explicites")):
        return float(k["explicites"])
    return float(sum(float(r.get("frais_explicites") or 0) for r in lines if str(r.get("sens")) in ("achat", "vente")))


def _sec_ordre(ctx: _Ctx) -> H:
    od = ctx.order_dict()
    o = ctx.order()
    k = od.get("couts") or {}
    ex = od.get("execution") or {}
    ch = od.get("choix") or {}
    lines_all = od.get("lignes") or []
    parts: list[Any] = [
        _box("warn", f"{od.get('bandeau') or BANNER} Statut : {od.get('statut', 'n.d.')}.",
             (od.get("phrase_etude") or "").capitalize() + ("." if od.get("phrase_etude") else "")),
        _tiles([
            ("Variante appliquée", str(od.get("variante", "n.d.")), ch.get("motif", ""), "fait"),
            ("Valeur du portefeuille", fmt_fcfa(od.get("valeur_portefeuille")),
             f"dont liquidités {fmt_fcfa(od.get('liquidites_initiales'))}", "fait"),
            ("Investi après ordres", fmt_fcfa(k.get("investi_apres")), f"{fmt_pct(k.get('investi_pct'), 2)} ; cible "
             f"atteignable {fmt_pct(k.get('cible_pct'), 2)} ; cible de la spécification "
             f"{fmt_pct(k.get('cible_specification', 0.98), 0)}", "estimation"),
            ("Coûts d'entrée", fmt_fcfa(k.get("total")), f"{fmt_pct(k.get('total_pct'), 2)} de la valeur ; explicites "
             f"{fmt_fcfa(_explicit_costs(k, lines_all))} (achats et ventes)", "estimation"),
            ("Frais fixes annuels", fmt_fcfa((k.get("garde_annuelle") or 0) + (k.get("tenue_compte_annuelle") or 0)),
             f"garde {fmt_pct(k.get('taux_garde'), 2)} + {fmt_fcfa(k.get('frais_par_ligne'))} par ligne", "hypothese"),
            ("Exécution", f"{fmt_int(ex.get('n_seances'))} séance(s)", f"du {fmt_date(ex.get('premiere_seance'))} au "
             f"{fmt_date(ex.get('derniere_seance'))} ; ≤ 10 % de la MDV63 par séance", "estimation"),
        ]),
    ]
    for w in od.get("avertissements") or []:
        parts.append(_box("warn", "Avertissement", w))
    nt = _get(od, "declencheurs", "notes") or {}
    if nt.get("ligne"):
        parts.append(_box("info", "Notes de l'analyste dans cette décision", nt["ligne"]))
    blocs = nt.get("blocages") or []
    eff = nt.get("effet") or {}
    if blocs or eff.get("lignes"):
        brow = [_fiche(H(f"<b>{esc(b.get('symbole'))}</b> {_chip('achats bloqués', 'no')} "
                         f"<span><b>{esc(b.get('code'))}</b> {esc(b.get('libelle') or '')}</span>"),
                       [("Note", _note_ref(b)), ("Blocage", _filter_span(b)),
                        ("Effet sur l'ordre", b.get("effet_poids") or "—"),
                        ("Pour lever le blocage", b.get("lever") or "")]) for b in blocs]
        erow = [[H(f"<b>{esc(x.get('symbole'))}</b>"), fmt_pct(x.get("poids_sans_notes"), 2),
                 fmt_pct(x.get("poids_avec_notes"), 2), _num_cell(x.get("ecart"), decimals=2, signed=True),
                 esc(x.get("motif") or "redistribution (construction)")] for x in eff.get("lignes") or []]
        parts.append(_card(
            H("<h3>Achats bloqués par les notes de l'analyste et effet sur les poids</h3>"),
            H('<div class="grid2">' + "".join(brow) + "</div>") if brow else "",
            _p(eff.get("texte", ""), "small") if eff.get("texte") else "",
            _details(f"Poids cibles sans et avec les notes ({len(erow)} ligne(s))",
                     _table(["Titre", "Sans les notes", "Avec les notes", "Écart", "Motif"], erow, left=(0, 4)),
                     open_=len(erow) <= 6) if erow else ""))
    mm = [str(m) for m in od.get("messages_modele") or [] if m]
    if mm:
        parts.append(_box("info", f"Messages du modèle ({len(mm)}, signalés)", _ul(mm)))
    lines = od.get("lignes") or []
    rows = []
    compact = []
    remarks: list[str] = []
    for r in sorted(lines, key=lambda r: (-(r.get("poids_cible") or 0.0), str(r.get("symbole")))):
        sens = str(r.get("sens", ""))
        tip = (f"courtage {fmt_fcfa(r.get('courtage'))} · TVA {fmt_fcfa(r.get('tva'))} · BRVM {fmt_fcfa(r.get('brvm'))}"
               f" · DC/BR {fmt_fcfa(r.get('dcbr'))} · demi-spread {fmt_fcfa(r.get('demi_spread'))} · impact "
               f"{fmt_fcfa(r.get('impact'))}")
        held = int(r.get("detenus") or 0)
        rows.append([
            H(f"<b>{esc(r.get('symbole'))}</b><div class='muted small name' title='{esc(r.get('nom', ''))}'>"
              f"{esc(r.get('nom', ''))}</div>"),
            _chip(sens.upper() if sens != "aucun" else "aucun", "ok" if sens == "achat" else "no" if sens == "vente" else ""),
            H(f"<b>{esc(fmt_int(r.get('quantite')))}</b>"
              + (f"<div class='muted small'>détenus {esc(fmt_int(held))} → {esc(fmt_int(r.get('cibles')))}</div>"
                 if held else "")),
            H(f"{esc(fmt_pct(r.get('poids_cible'), 2))}<div class='muted small'>réalisé "
              f"{esc(fmt_pct(r.get('poids_realise'), 2))}</div>"),
            fmt_num(r.get("cours_reference"), 0),
            H((f"<b>{esc(fmt_num(r.get('prix_limite'), 0))}</b>" if sens != "aucun" else "—")
              + f"<div class='muted small'>bornes {esc(fmt_num(r.get('borne_basse'), 0))} – "
                f"{esc(fmt_num(r.get('borne_haute'), 0))}</div>"),
            fmt_fcfa(r.get("montant_brut")), H(f"<span title='{esc(tip)}'>{esc(fmt_fcfa(r.get('couts_total')))}</span>"),
            fmt_fcfa(r.get("montant_net")), fmt_int(r.get("seances")),
        ])
        compact.append([H(f"<b>{esc(r.get('symbole'))}</b>"),
                        H(f"{esc(sens if sens != 'aucun' else '—')} <b>{esc(fmt_int(r.get('quantite')))}</b>"),
                        H(f"<b>{esc(fmt_num(r.get('prix_limite'), 0))}</b>") if sens != "aucun" else "—",
                        fmt_num(r.get("montant_net"), 0)])
        if r.get("note"):
            remarks.append(f"{r.get('symbole')} : {r.get('note')}")
    def _tot(side: str, col: str) -> float:
        return float(sum(float(r.get(col) or 0) for r in lines if str(r.get("sens")) == side))

    # Pied du tableau : achats et ventes séparés (avant : brut des deux sens additionné, au-delà de la valeur
    # du portefeuille) et flux net de liquidités (achats nets − ventes nettes).
    foot_rows = [
        ["Total achats", "", "", "", "", "", fmt_fcfa(_tot("achat", "montant_brut")), fmt_fcfa(_tot("achat", "couts_total")),
         fmt_fcfa(_tot("achat", "montant_net")), ""],
        ["Total ventes", "", "", "", "", "", fmt_fcfa(_tot("vente", "montant_brut")), fmt_fcfa(_tot("vente", "couts_total")),
         fmt_fcfa(_tot("vente", "montant_net")), ""],
        ["Flux net (achats − ventes)", "", "", "", "", "", "", fmt_fcfa(k.get("total")),
         fmt_fcfa(_tot("achat", "montant_net") - _tot("vente", "montant_net")), ""],
    ]
    parts.append(_card(H("<h3>Ordres (au titre et au franc près)</h3>"),
                       H('<div class="narrow-only">'), _table(["Titre", "Ordre", "Prix limite", "Net (FCFA)"], compact,
                                                             left=(0, 1)),
                       H('<p class="muted small">Résumé pour petit écran ; le détail (poids, bornes, coûts, séances) '
                         "suit et défile horizontalement.</p></div>"),
                       _table(["Titre", "Sens", "Quantité", "Poids cible", "Cours réf.", "Prix limite", "Brut",
                               "Coûts", "Net", "Séances"], rows, left=(0,), foot_rows=foot_rows),
                       _details(f"Remarques par ligne ({len(remarks)})", _ul(remarks)) if remarks else "",
                       _p("Prix limite d'achat : min(borne haute ; cours × 1,01) au pas inférieur ; de vente : "
                          "max(borne basse ; cours × 0,99) au pas supérieur. Coûts : BRVM 0,20 % et DC/BR 0,10 % "
                          "(faits, barèmes) ; courtage 0,80 % et taxe 18 % sur le courtage (hypothèses ; taxe [NON "
                          "VÉRIFIÉ] : TVA ou TAF) ; demi-spread et impact (estimations). Survolez un coût pour son détail.",
                          "muted small")))
    tr = od.get("tranches") or []
    if tr:
        trows = [[fmt_int(x.get("seance")), fmt_date(x.get("date")), x.get("symbole"), str(x.get("sens", "")),
                  fmt_int(x.get("titres")), fmt_num(x.get("prix_limite"), 0), fmt_fcfa(x.get("pire_cas")),
                  fmt_date(x.get("date_reglement")), x.get("financement", "")] for x in tr]
        parts.append(_details(f"Échéancier d'exécution ({len(tr)} tranche(s))",
                              _join([_table(["Séance", "Date", "Titre", "Sens", "Titres", "Limite", "Provision pire cas",
                                             "Règlement", "Financement"], trows, left=(2, 8)),
                                     _p(str(ex.get("calendrier", "")), "muted small")])))
    crow = _active_constraints(od)
    if crow:
        parts.append(_card(H("<h3>Contraintes actives</h3>"),
                           _table(["Contrainte", "Plafond", "Utilisé", "État", "Règle"], crow, left=(0, 4))))
    comp = od.get("comparaison")
    if comp:
        cd, cr = comp.get("distribution") or {}, comp.get("revenus") or {}
        d0, r0 = od.get("distribution") or {}, od.get("revenus") or {}
        k1 = comp.get("couts") or {}
        n0 = sum(1 for r in lines if (r.get("cibles") or 0) > 0)
        n1 = len(comp.get("lignes") or [])
        common = {str(r.get("symbole")) for r in lines if (r.get("cibles") or 0) > 0} & \
            {str(r.get("symbole")) for r in comp.get("lignes") or []}

        def row(lab: str, a: Any, b: Any) -> list[Any]:
            return [lab, a, b]

        crows = [
            row("Lignes", fmt_int(n0), fmt_int(n1)),
            row("Investi", fmt_pct(k.get("investi_pct"), 1), fmt_pct(k1.get("investi_pct"), 1)),
            row("Coûts d'entrée", f"{fmt_fcfa(k.get('total'))} ({fmt_pct(k.get('total_pct'), 2)})",
                f"{fmt_fcfa(k1.get('total'))} ({fmt_pct(k1.get('total_pct'), 2)})"),
            row("Revenu net à 12 mois", fmt_fcfa(r0.get("net")), fmt_fcfa(cr.get("net"))),
            row("Médiane à 12 mois (nette)", fmt_pct(d0.get("mediane")), fmt_pct(cd.get("mediane"))),
            row("P10 / P90", f"{fmt_pct(d0.get('p10'))} / {fmt_pct(d0.get('p90'))}",
                f"{fmt_pct(cd.get('p10'))} / {fmt_pct(cd.get('p90'))}"),
            row("P(battre le TR)", fmt_pct(d0.get("p_battre_tr"), 0), fmt_pct(cd.get("p_battre_tr"), 0)),
        ]
        top = sorted(comp.get("lignes") or [], key=lambda r: -(r.get("poids_cible") or 0))[:20]
        parts.append(_card(
            H(f"<h3>Comparaison : {esc(od.get('variante'))} (appliquée) contre {esc(comp.get('variante'))} "
              "(information)</h3>"),
            _p(comp.get("texte", ""), "muted small"),
            _table(["", str(od.get("variante")), str(comp.get("variante"))], crows),
            _p(f"Titres communs : {len(common)} ; lignes de {comp.get('variante')} : "
               + ", ".join(f"{r.get('symbole')} {fmt_pct(r.get('poids_cible'), 1)}" for r in top) + ".", "small"),
            _p("Distributions historiques (bootstrap), pas des prévisions.", "muted small")))
    else:
        parts.append(_box("info", "Aucune variante en comparaison.",
                          "A est rejeté, ou la variante est imposée par l'appelant (choose_variant)."))
    grid = H('<div class="grid3">'
             + _card(H("<h3>Faits</h3>"), _tag("fait"), _ul(od.get("faits") or []))
             + _card(H("<h3>Estimations</h3>"), _tag("estimation"), _ul(od.get("estimations") or []))
             + _card(H("<h3>Hypothèses</h3>"), _tag("hypothese"), _ul(od.get("hypotheses") or [])) + "</div>")
    parts.append(grid)
    try:
        frag = o.to_html_fragment() if hasattr(o, "to_html_fragment") else ""
    except Exception as exc:  # noqa: BLE001 - export facultatif
        frag = ""
        parts.append(_box("info", "Export HTML du module indisponible", f"{exc.__class__.__name__} : {exc}"))
    if frag:
        low = frag.lower()
        if "<script" in low or re.search(r"""(src|href)\s*=\s*["']?\s*(https?:|javascript:|//)""", low):
            parts.append(_box("warn", "Export HTML du module non inclus", "contenu actif ou ressource externe détecté"))
        else:
            parts.append(_details("Ordre de bataille complet (export du module recommend, to_html_fragment)",
                                  H(f'<div class="frag">{frag}</div>')))
    return _join(parts)


# -- 5. Revenus ------------------------------------------------------------------------------


def _sec_revenus(ctx: _Ctx) -> H:
    od = ctx.order_dict()
    rev = od.get("revenus") or {}
    div = [d for d in od.get("dividendes") or []]
    t = ctx.t()
    parts: list[Any] = [_tiles([
        (f"Revenu net à {rev.get('horizon_mois', 12)} mois", fmt_fcfa(rev.get("net")), "après IRVM du pays de l'émetteur",
         "estimation"),
        ("Brut", fmt_fcfa(rev.get("brut")), "avant retenue à la source", "estimation"),
        ("IRVM", fmt_fcfa(rev.get("irvm")), "retenue à la source (§7.3)", "hypothese"),
        ("Rendement net", fmt_pct(rev.get("rendement_net"), 2), f"sur la valeur ; {fmt_pct(rev.get('rendement_net_investi'), 2)} "
         "sur le montant investi", "estimation"),
        ("Paiements attendus", fmt_int(rev.get("n_paiements")), "dernier dividende reconduit à l'identique", "hypothese"),
    ])]
    paid = [d for d in div if (d.get("montant_net") or 0) > 0 and d.get("date_paiement_prevue")]
    if paid:
        start = pd.Timestamp(t).to_period("M") + 1
        months = pd.period_range(start, periods=int(rev.get("horizon_mois") or 12) + 1, freq="M")
        tot = {p: 0.0 for p in months}
        cnt = {p: [] for p in months}
        for d in paid:
            p = pd.Timestamp(d["date_paiement_prevue"]).to_period("M")
            if p in tot:
                tot[p] += float(d["montant_net"])
                cnt[p].append(str(d.get("symbole")))
        labels = [f"{MOIS[p.month - 1]} {str(p.year)[2:]}" for p in months]
        tips = [f"{MOIS[p.month - 1]} {p.year} : {fmt_fcfa(tot[p])} nets" + (f" ({', '.join(cnt[p])})" if cnt[p] else "")
                for p in months]
        parts.append(_card(H("<h3>Calendrier des dividendes nets attendus (par mois de paiement)</h3>"),
                           bar_chart("c-revenus", labels, [tot[p] for p in months], tips=tips, label="Dividendes nets "
                                     "attendus par mois", caption="Mois habituel de détachement tiré de l'historique ; "
                                     "montants en FCFA (estimation).")))
    rows = []
    for d in sorted(div, key=lambda d: (str(d.get("date_paiement_prevue") or "9999"), str(d.get("symbole")))):
        rows.append([H(f"<b>{esc(d.get('symbole'))}</b>"), fmt_int(d.get("titres")), fmt_date(d.get("date_ago_estimee")),
                     fmt_date(d.get("date_ex_prevue")), fmt_date(d.get("date_paiement_prevue")),
                     fmt_num(d.get("dividende_net_prevu_par_titre"), 2), fmt_fcfa(d.get("montant_brut")),
                     _irvm_cell(d),
                     H(f"<b>{esc(fmt_fcfa(d.get('montant_net')))}</b>"),
                     H(f"<span class='muted small wrap'>{esc(d.get('statut', ''))}</span>")])
    if rows:
        parts.append(_card(H("<h3>Détail par ligne</h3>"),
                           _table(["Titre", "Titres", "AGO estimée", "Date ex prévue", "Paiement prévu", "Net / titre",
                                   "Brut", "IRVM", "Net", "Statut"], rows, left=(0, 9),
                                  foot=["Total", "", "", "", "", "", fmt_fcfa(rev.get("brut")), fmt_fcfa(rev.get("irvm")),
                                        fmt_fcfa(rev.get("net")), ""]),
                           _p("Faits : derniers dividendes nets publiés au BOC, ajustés des divisions. Estimations : "
                              "dates projetées sur le mois habituel, AGO = date ex − 42 jours. Hypothèses : dividende "
                              "reconduit, taux d'IRVM marqués [NON VÉRIFIÉ].", "muted small")))
    else:
        parts.append(_box("empty", "Aucun dividende attendu sur l'horizon."))
    return _join(parts)


# -- 6. Distribution à 12 mois ---------------------------------------------------------------


def _irvm_cell(d: Mapping[str, Any]) -> H:
    """Montant de l'IRVM et son taux, affiché **une fois** : quand la remarque commence par le taux
    (« 12,5 % [NON VÉRIFIÉ] »), elle le remplace au lieu de le répéter."""
    rate = fmt_pct(d.get("taux_irvm_prevu"), 1)
    note = str(d.get("irvm_note") or "").strip()
    if note and note.replace("\u202f", " ").replace("\xa0", " ").startswith(rate.replace("\u202f", " ").replace("\xa0", " ")):
        return H(f"{esc(fmt_fcfa(d.get('irvm')))} <span class='muted small'>{esc(note)}</span>")
    return H(f"{esc(fmt_fcfa(d.get('irvm')))} <span class='muted small'>{esc(rate)}</span>"
             + (f"<div class='muted small desc'>{esc(note)}</div>" if note else ""))


def _stress_table(od: Mapping[str, Any]) -> H:
    rows = []
    for s in od.get("stress") or []:
        rows.append([H(f"<b>{esc(s.get('code'))}</b>"), H(f"<span class='cn'>{esc(s.get('variante') or '')}</span>"),
                     H(f"<span class='wrap w2'>{esc(s.get('scenario', ''))}</span>"),
                     H(f"<span class='{_cls(s.get('perte_fcfa'))}'>{esc(fmt_fcfa(s.get('perte_fcfa'), True))}</span>"),
                     _num_cell(s.get("perte_pct"), signed=True),
                     H(f"<span class='muted small wrap'>{esc(s.get('hypothese', ''))}</span>"),
                     H(f"<span class='cn small'>{esc(s.get('base', ''))}</span>"),
                     _tag("estimation" if s.get("nature") != "contrôle" else "fait")])
    if not rows:
        return _box("empty", "Aucun scénario de stress.")
    # Petit écran : résumé compact (code, variante, pertes) d'abord ; le détail suit (défilement horizontal),
    # pertes en 2e et 3e colonnes pour rester visibles (revue produit du 22/11/2026).
    compact = [[H(f"<b>{esc(s.get('code'))}</b>"
                  + (f"<div class='muted small cv'>{esc(s.get('variante'))}</div>" if s.get("variante") else "")),
                H(f"<span class='{_cls(s.get('perte_fcfa'))}'>"
                  f"{esc(fmt_num(round(float(s['perte_fcfa'])), 0, True) if _ok(s.get('perte_fcfa')) else 'n.d.')}</span>"),
                _num_cell(s.get("perte_pct"), signed=True)] for s in od.get("stress") or []]
    # Nature (estimation / contrôle) sous le code : le tableau complet tient dans la largeur d'un écran de bureau.
    full = [[H(f"{r[0]}<div>{r[7]}</div>"), r[3], r[4], r[1], r[2], r[5], r[6]] for r in rows]
    return _join([H('<div class="narrow-only">'), _table(["Code", "Variation (FCFA)", "Variation (%)"], compact),
                  H('<p class="muted small">Résumé pour petit écran ; scénario, hypothèse et base suivent.</p></div>'),
                  _table(["Code · nature", "Variation (FCFA)", "Variation (%)", "Variante", "Scénario", "Hypothèse",
                          "Base"], full, left=(0, 3, 4, 5, 6))])


def _sec_distribution(ctx: _Ctx) -> H:
    od = ctx.order_dict()
    d = od.get("distribution") or {}
    val = _get(od, "meta", "valorisation", "regime")
    stress = _card(H("<h3>Stress tests du §9.3</h3>"), _stress_table(od),
                   _p("Variation de valeur du portefeuille cible (négative = perte), sous hypothèse de linéarité (β "
                      "hebdomadaire borné) ou de choc direct par pays ; ST9 est un contrôle de données. Source : "
                      f"{_get(od, 'meta', 'stress_source', default='n.d.')}.", "muted small"))
    parts: list[Any] = []
    if val == "chère":
        parts.append(_box("warn", "Marché « cher » (prime du BOC < 1) : stress tests d'abord (§4.5).",
                          "Ils décrivent ce qui peut arriver ; ce ne sont pas des prévisions."))
        parts.append(stress)
    if not d.get("disponible"):
        parts.append(_box("info", "Distribution indisponible", d.get("motif", "motif non précisé")))
    else:
        parts.append(_tiles([
            ("Médiane à 12 mois", fmt_pct(d.get("mediane"), 1, True), f"nette des coûts d'entrée et frais fixes "
             f"({fmt_pct(d.get('frais_deduits'), 2)})", "estimation"),
            ("P10 / P90", f"{fmt_pct(d.get('p10'), 1, True)} / {fmt_pct(d.get('p90'), 1, True)}",
             "1 tirage sur 10 sous P10, 1 sur 10 au-dessus de P90", "estimation"),
            ("P(battre le TR)", fmt_pct(d.get("p_battre_tr"), 0),
             (f"fréquence historique aux poids actuels ; {(d.get('resultat_s1') or {}).get('court')}"
              if (d.get("resultat_s1") or {}).get("court") else f"médiane du TR {fmt_pct(d.get('tr_mediane'), 1, True)}"),
             "estimation"),
            ("P(perte)", fmt_pct(d.get("p_perte"), 1), "rendement net < 0 à 12 mois ; repère réalisé : 43 % des "
             "fenêtres de 12 mois du Composite prix sont négatives sur 2017-2026 (§10.3)", "estimation"),
            ("Volatilité annuelle", fmt_pct(d.get("vol_annuelle"), 1), f"TR {fmt_pct(d.get('tr_vol_annuelle'), 1)} ; β "
             f"{fmt_num(d.get('beta_hebdo'), 2)}", "estimation"),
        ]))
        parts.append(_p("P(perte) et le repère réalisé ne mesurent pas la même chose : la première rééchantillonne le "
                        "portefeuille d'aujourd'hui (dividendes compris) par blocs de quelques semaines, le second compte "
                        "les fenêtres de 12 mois réellement observées sur l'indice de prix. Un bootstrap par blocs "
                        "courts ne reproduit pas les baisses de plusieurs années : P(perte) est probablement trop basse.",
                        "muted small"))
        if d.get("biais_fenetre"):
            parts.append(_box("warn", "Fenêtre d'estimation optimiste", d["biais_fenetre"]))
        if d.get("biais_retrospectif"):
            span = (f"fenêtre du {fmt_date(d.get('debut'))} au {fmt_date(d.get('fin'))}" if d.get("fenetre_incomplete")
                    else "fenêtre 2017-2026")
            parts.append(_box("warn", f"Biais rétrospectif ({span}, poids actuels).",
                              re.sub(r"^Biais rétrospectif\s*:\s*", "", str(d["biais_retrospectif"]))))
        if (d.get("resultat_s1") or {}).get("texte"):
            parts.append(_box("warn", "Résultat du test S1 à lire avec P(battre le TR)", d["resultat_s1"]["texte"]))
        draws = ctx.try_get("draws", "tirages du bootstrap", ctx.draws)
        cap = (f"{fmt_int(d.get('n_boot'))} tirages du bootstrap stationnaire (blocs moyens de "
               f"{fmt_num(d.get('bloc_moyen_semaines'), 0)} semaines, graine {d.get('graine')}) sur "
               f"{fmt_int(d.get('n_semaines'))} semaines du {fmt_date(d.get('debut'))} au {fmt_date(d.get('fin'))} ; "
               f"{d.get('fenetre', '')}. Distribution historique, pas une prévision.")
        if draws is not None:
            markers = [(0.0, "0 %", "zero"), (d.get("p10"), f"P10 {fmt_pct(d.get('p10'), 0, True)}", "q"),
                       (d.get("mediane"), f"médiane {fmt_pct(d.get('mediane'), 0, True)}", "med"),
                       (d.get("p90"), f"P90 {fmt_pct(d.get('p90'), 0, True)}", "q"),
                       (d.get("tr_mediane"), f"TR médian {fmt_pct(d.get('tr_mediane'), 0, True)}", "tr")]
            note = "" if draws.get("conforme") else (" Histogramme recalculé : médiane "
                                                     f"{fmt_pct(draws.get('mediane_recalculee'), 2)} (écart avec l'ordre "
                                                     "de bataille, à examiner).")
            parts.append(_card(H("<h3>Rendement net à 12 mois : distribution historique</h3>"),
                               histogram_chart("c-dist", draws["net"], markers=markers,
                                               label="Histogramme des rendements nets à 12 mois", caption=cap + note)))
        else:
            parts.append(_box("info", "Histogramme indisponible", "tirages non recalculables ; " + cap))
    if val != "chère":
        parts.append(stress)
    return _join(parts)


# -- 7. Indices ------------------------------------------------------------------------------


MARKET_INDEX_CODES = ("IDX:BRVM-C", "IDX:BRVM-C-TR")


def _per_cell(code: Any, r: Any) -> H:
    """PER d'un indice, avec sa nature : publié (marché) ou médian des constituants (+ PER publié en petit)."""
    per = fmt_num(r.get("per"), 1)
    if str(code) in MARKET_INDEX_CODES:
        return H(f"{esc(per)}<div class='muted small'>publié (BOC)</div>")
    pub = r.get("per_index")
    return H(f"{esc(per)}<div class='muted small'>médian"
             + (f" ; publié {esc(fmt_num(pub, 1))}" if _ok(pub) else "") + "</div>")


def _sec_indices(ctx: _Ctx) -> H:
    ev = ctx.indices_eval()
    if ev is None or not len(ev):
        raise Unavailable("aucun indice évalué à la date")
    parts: list[Any] = [_box("info", "Portée : aide à la décision, pas un signal validé.",
                             "La position par indice combine tendance, valorisation, largeur, régime et notes avec des "
                             "poids non validés hors échantillon ; elle n'entre pas dans l'ordre de bataille. "
                             "Lecture factuelle, sans garantie.")]
    st = ctx.try_get("notes_status", "état des notes", ctx.notes_status)
    if st:
        parts.append(_box("info", "Notes de l'analyste dans l'évaluation des indices",
                          f"{st.get('line')} {st.get('scores_message') or ''}"))
    else:
        parts.append(_box("empty", "Notes de l'analyste : aucun journal.",
                          "La composante « notes » est exclue du score de chaque indice."))
    rows = []
    fragile = []
    for code, r in ev.iterrows():
        flip = _stance_flip(r)
        if flip:
            fragile.append(f"{r.get('label', code)} ({r.get('stance')} avec les notes, score "
                           f"{fmt_num(r.get('composite'), 2, True)} ; {flip} sans, score "
                           f"{fmt_num(r.get('composite_ex_notes'), 2, True)} ; z notes {fmt_num(r.get('z_notes'), 2, True)})")
        pos = _stance_chip(r.get("stance")) + (H(f"<div class='muted small'>sans notes : {esc(flip)}</div>")
                                                if flip else "")
        rows.append([H(f"<b class='cn'>{esc(r.get('label', code))}</b><div class='muted small'>{esc(code)}</div>"),
                     fmt_num(r.get("level"), 2), _num_cell(r.get("ret_1m"), signed=True),
                     _num_cell(r.get("ret_3m"), signed=True), _num_cell(r.get("ret_12m"), signed=True),
                     _num_cell(r.get("ytd"), signed=True), _per_cell(code, r), esc(r.get("regime") or "n.d."),
                     esc(_notes_z_txt(r)),
                     fmt_num(r.get("composite"), 2, True), H(pos),
                     fmt_pct(r.get("confidence"), 0)])
    if fragile:
        parts.append(_box("warn", STANCE_FLIP_TITLE, H(_ul(fragile) + esc(STANCE_FLIP_TEXT))))
    parts.append(_card(_table(["Indice", "Niveau", "1 mois", "3 mois", "12 mois", "Depuis le 31/12", "PER", "Régime",
                               "Notes (z)", "Score", "Position", "Confiance"], rows),
                       _p("Colonne PER : pour le marché (Composite, Composite TR), PER moyen publié au BOC ; pour les autres "
                          "indices, PER médian des constituants (0 < PER ≤ 100), utilisé par le score, avec en petit le "
                          "PER publié de l'indice au BOC. Les deux diffèrent fortement quand quelques titres ont un PER "
                          "très élevé.", "muted small")))
    det = []
    for code, r in ev.iterrows():
        reasons = list(r.get("reasons") or [])
        if reasons:
            det.append(_details(H(f"{esc(r.get('label', code))} — {_stance_chip(r.get('stance'))}"), _ul(reasons)))
    if det:
        parts.append(_card(H("<h3>Raisons</h3>"), _join(det)))
    return _join(parts)


# -- 8. Notes de l'analyste -------------------------------------------------------------------


def _ts_txt(x: Any) -> str:
    try:
        t = pd.Timestamp(x)
    except (TypeError, ValueError):
        return "n.d."
    if pd.isna(t):
        return "n.d."
    return t.strftime("%d/%m/%Y")


#: Lignes affichées au plus dans le tableau des notes automatiques en vigueur.
NOTES_TABLE_MAX = 60


#: Avertissement quand la position d'un indice diffère avec et sans les notes (mêmes textes que l'interface).
STANCE_FLIP_TITLE = "Position changée par les notes : sans elles, la position serait différente."
STANCE_FLIP_TEXT = ("Les notes s'ajoutent au score des autres composantes (+ 0,15 × z notes ; une note automatique pèse par "
                    "la confiance de son analyse) : une note positive ne peut que relever le score, une note négative que "
                    "l'abaisser. Ici elles font franchir un seuil : lire ces indices avec leur position « sans "
                    "notes ». Aide à la décision, pas un signal validé.")


def _note_targets_txt(n: Mapping[str, Any]) -> str:
    """Cible(s) saisie(s) dans la note ; pour une note propagée : « IDX:BRVM-C, propagée aux constituants × 0,25 »."""
    src = [str(x) for x in (n.get("source_targets") or n.get("targets") or [])]
    txt = ", ".join(src[:4]) + (" …" if len(src) > 4 else "")
    if _ok(n.get("propagation")) and str(n.get("relation") or "directe") != "directe":
        txt += f", propagée aux constituants × {fmt_num(n.get('propagation'), 2)}"
    return txt or "—"


def _note_date_txt(n: Mapping[str, Any]) -> str:
    """« saisie le … » (note de l'analyste) ou « publiée le … » (note collectée)."""
    manual = str(n.get("author") or "") == "analyste"
    for key, word in ((("created_at", "saisie"), ("published_at", "publiée")) if manual
                      else (("published_at", "publiée"), ("created_at", "collectée"))):
        v = n.get(key)
        if _ok(v):
            return f"{word} le {fmt_date(v)}"
    return "date n.d."


def _stance_flip(r: Any) -> str | None:
    """Position **sans** la composante « notes » quand elle diffère de la position affichée (sinon ``None``)."""
    ex = r.get("stance_ex_notes")
    if not isinstance(ex, str) or not ex or not _ok(r.get("z_notes")) or not _ok(r.get("composite_ex_notes")):
        return None
    return ex if ex != str(r.get("stance") or "") else None


def _filter_span(f: Mapping[str, Any]) -> str:
    """Durée d'un filtre : « depuis le …, jusqu'au … (encore N séance(s)) »."""
    return (f"depuis le {fmt_date(f.get('depuis'))}, {f.get('duree') or 'durée ouverte'}"
            + (f" (encore {fmt_int(f.get('seances_restantes'))} séance(s))"
               if f.get("seances_restantes") is not None else ""))


def _notes_z_txt(r: Any) -> str:
    """Composante « notes » d'un indice : z, ou la raison de son absence (jamais « n.d. » seul)."""
    z = r.get("z_notes")
    if _ok(z):
        return fmt_num(z, 2, True)
    n = r.get("notes_n")
    return "score nul" if _ok(n) and int(n) > 0 else "aucune note"


def _src_link(url: Any, text: Any = "document") -> H:
    """Adresse d'une note : lien (``class="src"``) vers www.brvm.org seulement, sinon texte non cliquable."""
    u = str(url or "").strip()
    if not u:
        return H("")
    if re.match(r"^https://www\.brvm\.org/[^\s\"'<>]*$", u):
        return H(f'<a class="src" href="{esc(u)}" rel="noopener noreferrer">{esc(text)}</a>')
    return H(f'<span class="muted small url">{esc(u)}</span>')


def _note_ref(b: Mapping[str, Any]) -> H:
    """Note qui porte un filtre : date, titre, source et lien."""
    link = _src_link(b.get("note_url"), "document")
    return H(f"note <code>{esc(str(b.get('note_id', ''))[:12])}</code> du {esc(_ts_txt(b.get('note_date')))} : "
             f"« {esc(b.get('note_titre') or '')} » <span class='muted small'>(source "
             f"{esc(b.get('note_source') or 'n.d.')})</span> {link}")


def _notes_rows(tab: pd.DataFrame, limit: int | None = None) -> list[list[Any]]:
    rows = []
    for r in (tab if limit is None else tab.head(limit)).to_dict("records"):
        src = H(f"{esc(r.get('source') or 'n.d.')} {_src_link(r.get('url'), 'document')}")
        avis = ""
        if isinstance(r.get("stance"), str) and r["stance"]:
            avis = f" · avis {r['stance']}" + (f" {int(r['conviction'])}/5" if _ok(r.get("conviction")) else "")
        rows.append([
            H(f"{esc(_ts_txt(r.get('published_at')))}<div class='muted small'>séance "
              f"{esc(_ts_txt(r.get('first_tradable_session')))}</div>"),
            esc(", ".join(map(str, r.get("targets") or [])) or "n.d."),
            _num_cell(r.get("score"), "num", 2, True),
            H(f"{esc(r.get('event_type') or 'n.d.')}<div class='muted small desc'>"
              f"{esc(str(r.get('title') or '')[:90])}{esc(avis)}</div>"),
            fmt_num(r.get("confidence"), 2),
            fmt_num(r.get("decay"), 2), src, esc(", ".join(map(str, r.get("filters") or [])) or "—"),
        ])
    return rows


#: En-têtes des tableaux de notes : le score suit la cible, pour rester visible sans défilement horizontal.
_NOTES_HEAD = ["Date (publication)", "Cible", "Score", "Type et titre", "Confiance", "Décroissance", "Source",
               "Filtre"]
_NOTES_LEFT = (0, 1, 3, 6, 7)


def _notes_in_force_block(ctx: _Ctx, st: Mapping[str, Any]) -> list[Any]:
    """Synthèse datée, filtres actifs, notes en vigueur (manuelles / automatiques), extrêmes, indices."""
    from brvm_alpha.notes.signals import top_notes

    parts: list[Any] = [_box("info", "Notes prises en compte dans la décision", st.get("line", ""))]
    tab = st.get("table")
    n_in = int(st.get("n_in_force") or 0)
    parts.append(_box("empty" if not st.get("n_scored") else "info",
                      "Scores des notes", st.get("scores_message", "")))
    # Filtres actifs.
    flt = st.get("filters") or []
    if flt:
        rows = [_fiche(H(f"<b>{esc(f.get('symbole'))}</b> "
                         f"{_chip('achats bloqués', 'no') if f.get('bloque_achats') else _chip('surveillance', 'warn')} "
                         f"<span><b>{esc(f.get('code'))}</b> {esc(f.get('libelle') or '')}</span>"),
                       [("Durée", _filter_span(f)), ("Note", _note_ref(f)),
                        ("Pour lever le filtre", f.get("lever") or "")]) for f in flt]
        parts.append(_card(H(f"<h3>Filtres de risque actifs issus des notes ({len(flt)})</h3>"),
                           H('<div class="grid2">' + "".join(rows) + "</div>")))
    else:
        parts.append(_box("empty", "Aucun filtre de risque actif issu des notes."))
    if not isinstance(tab, pd.DataFrame) or not n_in:
        return parts
    manual, auto = tab[tab["manual"]], tab[~tab["manual"]]
    parts.append(_card(
        H(f"<h3>Notes manuelles en vigueur ({len(manual)})</h3>"),
        _table(_NOTES_HEAD, _notes_rows(manual), left=_NOTES_LEFT) if len(manual) else
        _box("empty", "Aucune note manuelle en vigueur.",
             "Saisie : python -m brvm_alpha notes add, ou page Notes de l'interface.")))
    more = f" ; les {NOTES_TABLE_MAX} plus récentes sont affichées" if len(auto) > NOTES_TABLE_MAX else ""
    parts.append(_card(
        H(f"<h3>Notes automatiques en vigueur ({len(auto)})</h3>"),
        _p("Collectées sur www.brvm.org et dans les BOC ; âge compté depuis la publication (décroissance "
           f"exp(−Δ/10 séances)){more}.", "muted small"),
        _details(f"Tableau des notes automatiques ({min(len(auto), NOTES_TABLE_MAX)} ligne(s))",
                 _table(_NOTES_HEAD, _notes_rows(auto, NOTES_TABLE_MAX), left=_NOTES_LEFT)) if len(auto) else
        _box("empty", "Aucune note automatique en vigueur.")))
    pos, neg = top_notes(tab, 10)
    if len(pos) or len(neg):
        parts.append(_p("Classement des deux tableaux suivants : effet actuel de la note, soit score × décroissance "
                        "(à score égal, une note récente passe avant une note ancienne).", "muted small"))
        # Deux cartes l'une sous l'autre, en pleine largeur : côte à côte, les colonnes Décroissance, Source
        # et Filtre sortaient de l'écran à 1 280 px alors que le classement porte sur score × décroissance.
        parts.append(H('<div class="stack">'
                       + _card(H(f"<h3>Les {len(pos)} notes les plus positives</h3>"),
                               _table(_NOTES_HEAD, _notes_rows(pos), left=_NOTES_LEFT) if len(pos) else
                               _box("empty", "Aucune note de score positif."))
                       + _card(H(f"<h3>Les {len(neg)} notes les plus négatives</h3>"),
                               _table(_NOTES_HEAD, _notes_rows(neg), left=_NOTES_LEFT) if len(neg) else
                               _box("empty", "Aucune note de score négatif.")) + "</div>"))
    else:
        parts.append(_box("empty", "Aucune note positive ni négative à classer.", st.get("scores_message", "")))
    # Composante « notes » de chaque indice, avec les notes qui la portent.
    ev = ctx.try_get("indices_eval", "évaluation des indices", ctx.indices_eval)
    if ev is not None and len(ev):
        rows = []
        for code, r in ev.iterrows():
            det = list(r.get("notes_detail") or [])[:4]
            who = _ul([f"« {str(e.get('title') or '')[:80]} » ({_note_targets_txt(e)} ; {_note_date_txt(e)}) : "
                       f"score {fmt_num(e.get('note_score'), 2, True)}, part {fmt_num(e.get('part'), 3, True)}"
                       for e in det], "facts small") if det else esc(
                "aucune note en vigueur" if not (_ok(r.get("notes_n")) and int(r.get("notes_n")) > 0)
                else "notes en vigueur de score nul : composante exclue")
            flip = _stance_flip(r)
            rows.append([H(f"<b class='cn'>{esc(r.get('label', code))}</b><div class='muted small'>{esc(code)}</div>"),
                         esc(_notes_z_txt(r)), fmt_num(r.get("notes_score"), 3, True) if _ok(r.get("notes_score"))
                         else "—", fmt_int(r.get("notes_n")),
                         H(f"{esc(fmt_num(r.get('composite_ex_notes'), 2, True))} → "
                           f"<b>{esc(fmt_num(r.get('composite'), 2, True))}</b>"
                           + (f"<div class='muted small'>{esc(flip)} → {esc(r.get('stance'))}</div>" if flip else "")),
                         H(f"<div class='lst'>{who}</div>")])
        parts.append(_card(H("<h3>Composante « notes » de chaque indice</h3>"),
                           _p("z notes = score des notes (les notes automatiques pondérées par leur confiance) / 0,5, borné à ±3 ; les "
                              "notes s'ajoutent au score des autres composantes (+ 0,15 × z notes) : une note positive "
                              "ne peut que relever le score, une note négative que l'abaisser. « sans → avec » : score "
                              "composite sans puis avec les notes. Aide à la décision, pas un signal validé.",
                              "muted small"),
                           _table(["Indice", "z notes", "Score des notes", "Notes en vigueur", "Composite sans → avec",
                                   "Notes qui portent la composante"], rows, left=(0, 5))))
    return parts


def _sec_notes(ctx: _Ctx) -> H:
    store = ctx.store()
    if store is None:
        return _box("empty", "Aucune note dans le journal.",
                    f"Journal absent ({_rel(ctx.notes_root)}). Les notes se saisissent avec brvm_alpha.notes (NoteStore.add) ; "
                    "elles ne pilotent jamais seules le portefeuille (poids bornés, D11 : aucun rôle sur S1).")
    df = store.list(status="active")
    errs = list(getattr(store, "errors", []) or [])
    parts: list[Any] = []
    if errs:
        parts.append(_box("warn", f"{len(errs)} ligne(s) du journal ignorée(s) à la lecture", "; ".join(map(str, errs[:3]))))
    try:
        st = ctx.notes_status()
    except (Unavailable, DependencyError) as exc:
        st = None
        parts.append(_box("info", "État daté des notes non calculé", str(exc)))
    if st:
        parts.extend(_notes_in_force_block(ctx, st))
    if df is None or not len(df):
        parts.append(_box("empty", "Aucune note active dans le journal."))
        return _join(parts)
    t = ctx.t()
    t_end = (pd.Timestamp(t) + pd.Timedelta(hours=23, minutes=59)).tz_localize("UTC")
    df = df.sort_values("published_at", ascending=False).head(12)
    cards = []
    for r in df.itertuples(index=False):
        after = pd.notna(r.published_at) and pd.Timestamp(r.published_at) > t_end
        flags = ", ".join(map(str, r.risk_flags or [])) or "aucun"
        # pandas 3 : dans une colonne mêlant avis saisis et notes sans avis, l'absence vaut NaN (et non None).
        stance = (r.stance if isinstance(r.stance, str) and r.stance else "sans avis") + (
            f", conviction {int(r.conviction)}/5" if _ok(r.conviction) else "")
        cards.append(
            '<article class="note">'
            f'<div class="nh"><b>{esc(r.title or "(sans titre)")}</b>'
            + (' ' + _chip("postérieure aux données", "warn") if after else "")
            + f'</div><div class="muted small">publiée le {esc(_ts_txt(r.published_at))} · '
              f'{esc(r.author or "n.d.")} · source {esc(r.source or "n.d.")} · cibles '
              f'{esc(", ".join(map(str, r.all_targets or r.targets or [])) or "n.d.")} · type '
              f'{esc(r.event_type or "n.d.")} · avis {esc(stance)}</div>'
            + (f'<p class="ntext">{esc(str(r.text)[:600])}{"…" if len(str(r.text)) > 600 else ""}</p>' if r.text else "")
            + '<div class="nm">'
            + f'<span>score <b class="{_cls(r.score)}">{esc(fmt_num(r.score, 2, True))}</b></span>'
            + f'<span>matérialité <b>{esc(fmt_num(r.materiality, 2))}</b></span>'
            + f'<span>confiance <b>{esc(fmt_num(r.confidence, 2))}</b></span>'
            + f'<span>filtres R <b>{esc(flags)}</b></span></div>'
            + (f'<p class="small"><b>Lecture :</b> {esc(r.reading)}</p>' if r.reading else "")
            + (f'<p class="muted small">Adresse : {_src_link(r.url, "document sur www.brvm.org")}</p>' if r.url else "")
            + (f'<p class="muted small">Cibles non reconnues : {esc(", ".join(map(str, r.targets_unknown)))}</p>'
               if r.targets_unknown else "")
            + "</article>")
    parts.append(H("<h3>Dernières notes du journal</h3>"))
    parts.append(_p(f"{len(df)} dernière(s) note(s) active(s) du journal (par date de publication), qu'elles soient ou "
                    "non en vigueur à la séance d'application. Analyse automatique (score dans [−1 ; 1], matérialité et "
                    "confiance dans [0 ; 1]) : une lecture factuelle, pas une garantie.", "muted small"))
    parts.append(H('<div class="notes">' + "".join(cards) + "</div>"))
    od = ctx.try_get("order_dict", "ordre de bataille", ctx.order_dict)
    nd = _get(od, "declencheurs", "notes")
    if nd:
        veto = nd.get("veto") or {}
        tilt = nd.get("inclinaisons") or {}
        flags = nd.get("drapeaux") or {}
        rows = ([[H(f"<b>{esc(s)}</b>"), _chip("veto", "no"), "; ".join(map(str, v)) if isinstance(v, list) else str(v)]
                 for s, v in veto.items()]
                + [[H(f"<b>{esc(s)}</b>"), _chip("inclinaison"), f"{fmt_num(v, 2, True)} σ (borné à ±0,5)"]
                   for s, v in tilt.items()]
                + [[H(f"<b>{esc(s)}</b>"), _chip("filtre R", "warn"), ", ".join(map(str, v))] for s, v in flags.items()])
        parts.append(_card(H("<h3>Vetos et inclinaisons actifs à la date de décision</h3>"), _p(nd.get("texte", ""), "small"),
                           _table(["Titre", "Surcouche", "Détail"], rows, left=(0, 2)) if rows else
                           _box("empty", "Aucun veto ni inclinaison en vigueur.")))
    else:
        try:
            from brvm_alpha.notes.signals import manual_overlays

            ov = (st or {}).get("overlays") or manual_overlays(store, t, known_at=ctx.notes_known_at)
            reasons = list(ov.get("reasons") or [])
            parts.append(_card(H("<h3>Vetos et inclinaisons actifs</h3>"),
                               _ul(reasons) if reasons else _box("empty", "Aucun veto ni inclinaison en vigueur.")))
        except Exception as exc:  # noqa: BLE001 - surcouches facultatives
            parts.append(_box("info", "Surcouches de l'analyste non calculées", f"{exc.__class__.__name__} : {exc}"))
    return _join(parts)


# -- 9. Risques ------------------------------------------------------------------------------


def _as_list(x: Any) -> list[str]:
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return []
    if isinstance(x, (list, tuple, set, np.ndarray)):
        return [str(v) for v in x if v not in (None, "")]
    s = str(x)
    return [s] if s else []


def _sec_risques(ctx: _Ctx) -> H:
    parts: list[Any] = []
    od = ctx.try_get("order_dict", "ordre de bataille", ctx.order_dict)
    dec = ctx.try_get("decision", "décision du modèle", ctx.decision)
    target = {str(r.get("symbole")) for r in (od or {}).get("lignes") or [] if (r.get("cibles") or 0) > 0}
    # « en portefeuille » : titre déjà détenu ; « dans l'ordre » : titre que l'ordre propose d'acheter.
    owned = {str(r.get("symbole")) for r in (od or {}).get("lignes") or [] if (r.get("detenus") or 0) > 0}
    # Filtres R actifs.
    if dec is not None and isinstance(getattr(dec, "risk", None), pd.DataFrame) and "active" in dec.risk.columns:
        rk = dec.risk
        act = rk[rk["active"].astype(str).str.len() > 0]
        rows = []
        for s, r in act.iterrows():
            codes = str(r["active"])
            labs = ", ".join(sorted({R_LABELS.get(c, c) for c in re.findall(r"R\d+", codes)}))
            det = _as_list(r.get("detail_panel")) + _as_list(r.get("detail_notes"))
            rows.append([H(f"<b>{esc(s)}</b>" + (" " + _chip("en portefeuille" if s in owned else "dans l'ordre", "warn")
                                                 if s in target or s in owned else "")),
                         esc(codes), esc(labs), "oui" if bool(r.get("block_buys", False)) else "non",
                         H(f"<span class='small wrap'>{esc(_fr_txt(' ; '.join(det)))}</span>")])
        parts.append(_card(H("<h3>Filtres de risque R actifs (§5.6)</h3>"),
                           _table(["Titre", "Codes", "Nature", "Achats bloqués", "Détail"], rows, left=(0, 1, 2, 4))
                           if rows else _box("empty", "Aucun filtre R actif."),
                           _p("Les filtres R priment sur les signaux. R11 et R12 sont des approximations calculées sur "
                              "le panel (seuils non validés, §5.6).", "muted small")))
    elif od:
        fr = _get(od, "declencheurs", "filtres_r", default=[])
        rows = [[H(f"<b>{esc(x.get('symbole'))}</b>"), esc(x.get("filtres")), "oui" if x.get("achats_bloques") else "non"]
                for x in fr]
        parts.append(_card(H("<h3>Filtres de risque R actifs (lignes du portefeuille)</h3>"),
                           _table(["Titre", "Filtres", "Achats bloqués"], rows) if rows else
                           _box("empty", "Aucun filtre R actif sur les lignes.")))
    else:
        parts.append(_box("info", "Filtres R indisponibles", "décision du modèle et ordre de bataille indisponibles"))
    # Règles pays.
    trig = (od or {}).get("declencheurs") or {}
    ptxt = _get(trig, "pays", "texte")
    pays_rows = []
    try:
        from brvm_alpha import reference

        ce = getattr(reference, "COUNTRY_EVENTS", None)
        t = ctx.t()
        if isinstance(ce, pd.DataFrame) and len(ce):
            c2 = ce[(pd.to_datetime(ce["date"]) <= t) & (pd.to_datetime(ce["date"]) > t - pd.Timedelta(days=400))]
            for r in c2.sort_values("date", ascending=False).itertuples(index=False):
                pays_rows.append([fmt_date(r.date), PAYS.get(str(r.country), str(r.country)), str(r.rule),
                                  H(f"<span class='wrap w2'>{esc(getattr(r, 'label', ''))}</span>"),
                                  str(getattr(r, "confidence", "")),
                                  H(f"<span class='muted small wrap'>{esc(getattr(r, 'source', ''))}</span>")])
    except Exception as exc:  # noqa: BLE001 - tableau facultatif, motif affiché
        ptxt = (ptxt or "") + f" (chronologie des événements pays illisible : {exc.__class__.__name__})"
    parts.append(_card(H("<h3>Règles pays (§4.3)</h3>"), _p(ptxt or "Règles pays : ordre de bataille indisponible."),
                       _table(["Annonce", "Pays", "Règle", "Événement", "Confiance", "Source"], pays_rows, left=(1, 2, 3, 5))
                       if pays_rows else _p("Aucun événement pays annoncé dans les 400 derniers jours "
                                            "(reference.COUNTRY_EVENTS).", "muted small"),
                       _p("Les règles pays priment sur le score dans toutes les variantes. Dates de confiance « M » : "
                          "[NON VÉRIFIÉ] en source primaire.", "muted small")))
    # Drawdown et rebalancement.
    dd = _get(trig, "drawdown", "texte")
    rb = trig.get("rebalancement") or {}
    facts = [dd] if dd else []
    if rb:
        facts.append(f"Prochaine revue mensuelle : {fmt_date(rb.get('prochaine_revue'))}"
                     + (f" ; rebalancement annuel (D8) : {fmt_date(rb.get('rebalancement_annuel'))}"
                        if rb.get("rebalancement_annuel") else "") + ".")
    for x in _get(trig, "drawdown", "revues_lignes", default=[]) or []:
        facts.append(f"Revue obligatoire de {x.get('symbole')} : {fmt_pct(x.get('relatif_63'), 1, True)} contre le TR sur "
                     "63 séances (§9.1).")
    for x in _get(trig, "drawdown", "revues_avant_achat", default=[]) or []:
        rel_txt = (f"{fmt_pct(x.get('relatif_63'), 1, True)} contre le TR sur 63 séances" if _ok(x.get("relatif_63"))
                   else "sous-performance contre le TR sur 63 séances")
        facts.append(f"À revoir avant achat : {x.get('symbole')}, {rel_txt} (seuil de revue −25 %, §9.1) ; l'achat "
                     "reste proposé dans l'ordre.")
    if facts:
        parts.append(_card(H("<h3>Drawdown et revues</h3>"), _ul(facts)))
    # Événements à venir.
    ev = trig.get("evenements") or []
    if ev:
        rows = [[fmt_date(e.get("date")), str(e.get("type", "")), H(f"<b>{esc(e.get('cible', ''))}</b>"),
                 H(f"<span class='small wrap'>{esc(e.get('description', ''))}</span>"),
                 H(f"<span class='muted small'>{esc(e.get('nature', ''))}</span>")] for e in ev]
        first, rest = rows[:15], rows[15:]
        hdr = ["Date", "Type", "Cible", "Description", "Nature"]
        parts.append(_card(H(f"<h3>Événements à venir ({len(rows)} sur 12 mois)</h3>"), _table(hdr, first, left=(1, 2, 3, 4)),
                           _details(f"{len(rest)} événement(s) suivant(s)", _table(hdr, rest, left=(1, 2, 3, 4)))
                           if rest else ""))
    # Valorisation (§4.5).
    snap = ctx.try_get("market", "instantané du marché", lambda: _market_snapshot(ctx)) or {}
    prime = _get(snap, "market", "risk_premium")
    band = _valuation_band(float(prime)) if _ok(prime) else None
    parts.append(_card(H("<h3>Valorisation du marché (§4.5)</h3>"), _ul([
        (f"Prime de risque du BOC : {fmt_num(prime, 2)} → marché « {_BAND_LABEL.get(band, band)} » (cher < 1 ; "
         "neutre 1-4 ; bon marché > 4)."
         if band else "Prime de risque du BOC indisponible."),
        f"PER moyen du marché : {fmt_num(_get(snap, 'market', 'avg_per'), 2)} ; taux de référence estimé "
        f"{fmt_pct(snap.get('rf'), 2)}.",
        "Information, jamais un signal de timing : l'exposition ne change pas. Les PER aberrants du BOC (17/02/2021 ; "
        "17/07-26/08/2025) sont exclus des comparaisons historiques.",
        "Taux directeur de la BCEAO : décisions de septembre 2025 à novembre 2026 introuvables en source primaire "
        "[NON VÉRIFIÉ] ; poids nul.",
    ])))
    return _join(parts)


# -- 10. Univers -----------------------------------------------------------------------------


def _sec_univers(ctx: _Ctx) -> H:
    dec = ctx.decision()
    uni = dec.universe
    sc = dec.score if isinstance(dec.score, pd.DataFrame) else pd.DataFrame(index=uni.index)
    w = dec.weights if isinstance(dec.weights, pd.Series) else pd.Series(dtype=float)
    names = ctx.names()
    risk = dec.risk if isinstance(getattr(dec, "risk", None), pd.DataFrame) else pd.DataFrame()
    final = pd.to_numeric(sc.get("final", sc.get("score", pd.Series(dtype=float))), errors="coerce").reindex(uni.index)
    elig = uni["eligible"].astype("boolean").fillna(False).astype(bool)
    rank = final.where(elig & final.notna()).rank(ascending=False, method="first")
    order = sorted(uni.index, key=lambda s: (0 if elig.get(s) and _ok(rank.get(s)) else 1 if elig.get(s) else 2,
                                             rank.get(s) if _ok(rank.get(s)) else 0, str(s)))
    blocks = [("z_ep", "EP"), ("z_dy", "DY"), ("z_mom6_1", "MOM 6-1"), ("z_lowvol", "Faible vol."),
              ("z_quality_proxy", "Qualité")]
    rows = []
    for s in order:
        u = uni.loc[s]
        e = bool(elig.get(s))
        wt = float(w.get(s, 0.0)) if len(w) else 0.0
        motif = "" if e else str(u.get("reasons") or u.get("reason") or "")
        sym = H(f"<b>{esc(s)}</b>" + (" " + _chip("retenu", "ok") if wt > 0 else "")
                + f"<div class='muted small name' title='{esc(names.get(s, ''))}'>{esc(names.get(s, ''))}</div>")
        zc = []
        for col, _ in blocks:
            v = sc[col].get(s) if col in sc.columns else None
            zc.append(_num_cell(v, "num", 2, True) if _ok(v) else "—")
        ract = str(risk["active"].get(s, "")) if "active" in risk.columns and s in risk.index else ""
        rows.append([fmt_int(rank.get(s)) if _ok(rank.get(s)) else "—", sym,
                     f"{u.get('sector', '') or ''} · {u.get('country', '') or ''}",
                     _chip("oui", "ok") if e else H(_chip("non", "no") + f"<div class='muted small wrap motif'>{esc(motif)}</div>"),
                     fmt_fcfa(u.get("mdv63")) if _ok(u.get("mdv63")) else "n.d.",
                     H(f"<b>{_num_cell(final.get(s), 'num', 2, True)}</b>") if _ok(final.get(s)) else "—",
                     *zc, fmt_pct(wt, 2) if wt > 0 else "—", esc(ract or "—")])
    n_el = int(elig.sum())
    # Titres du panel absents du BOC de la date (anciens titres, radiés ou non encore cotés) : listés pour mémoire.
    absent = sum(1 for s in uni.index if "absent du BOC" in str(uni.loc[s].get("reasons") or uni.loc[s].get("reason") or ""))
    counted = (f"{len(uni) - absent} titres cotés à la date (plus {absent} ancien(s) titre(s) absent(s) du BOC, listé(s) "
               "pour mémoire)" if absent else f"{len(uni)} titres cotés à la date")
    lead = _p(f"{counted}, dont {n_el} éligibles (filtres U1-U10 du §2, capital "
              f"{fmt_fcfa(_get(ctx.try_get('order_dict', 'ordre', ctx.order_dict), 'valeur_portefeuille') or ctx.capital)}) ; "
              f"variante {dec.variant}. Score final : composite du §3.2 normalisé (rang gaussien), après malus et "
              "inclinaisons bornées. Blocs : scores normalisés par signal (z).", "muted small")
    return _join([lead, _card(_table(["Rang", "Titre", "Secteur · pays", "Éligible", "MDV63", "Score"]
                                     + [lab for _, lab in blocks] + ["Poids cible", "Filtres R"], rows,
                                     left=(1, 2, 3), cls="univ"))])


# -- 11. Méthode et limites ------------------------------------------------------------------


def _sec_methode(ctx: _Ctx) -> H:
    parts: list[Any] = []
    lim = [
        "Aucun gain garanti, ni absolu, ni relatif : avec un IR réel de 0,3, la probabilité de sous-performer l'indice "
        "une année donnée vaut environ 38 %, et 25 % sur 5 ans en cumul (§10.1).",
        "On ne prouve pas vite un alpha : il faut environ 30 ans de données hebdomadaires pour établir un IR de 0,3 à "
        "95 % (§10.2). Dix ans de BOC et 48 titres ne suffisent pas.",
        "Les marchés baissent, parfois longtemps : le Composite TR a perdu 46,7 % entre 2017 et 2020 ; 43 % des fenêtres "
        "de 12 mois du Composite prix sont négatives sur 2017-2026 (§10.3).",
        "Les professionnels n'y arrivent pas régulièrement : 28 à 30 % des années-fonds battent le TR (§10.4).",
        "Les effets s'affaiblissent quand ils sont exploités (fenêtre du dividende : de +5-6 % à environ +2,9 %) (§10.5).",
        "Les coûts mangent la marge : environ 3 à 3,5 % l'aller-retour pour un titre médian, et environ 1 % par an de "
        "frais fixes pour un petit portefeuille (§10.6).",
        "Le risque politique est brutal : −26 % en 9 séances au Niger (2023), aucun délai de sortie au Mali (2022) (§10.7).",
        "Les données ont des limites : pas de BOC avant 2017, trous en 2021, fondamentaux en partie scannés, taxes et "
        "IRVM en partie non vérifiés, études académiques citées non relues en ligne [NON VÉRIFIÉ] (§10.8).",
        "Le régime de liquidité a changé : environ 30 fois plus de valeur échangée en 2026 qu'en 2019-2020 ; 2017-2022 "
        "décrit un autre marché (§10.9).",
    ]
    parts.append(_card(H("<h3>Ce que la plate-forme ne peut pas promettre (§10)</h3>"), _ul(lim)))
    # Trous de données.
    gaps_txt = []
    sess = ctx.long("sessions")
    if sess is not None and "available" in sess.columns and len(sess):
        s = sess.copy()
        s["date"] = pd.to_datetime(s["date"], errors="coerce")
        avail = s["available"].astype(bool)
        miss = s[~avail]
        years = (miss["year"] if "year" in miss.columns else miss["date"].dt.year).dropna().astype(int)
        by_year = years.value_counts().sort_index()
        dates = s.loc[avail, "date"]
        gaps_txt.append(f"{fmt_int(len(miss))} séances réelles sans BOC téléchargeable sur {fmt_int(len(s))} numéros de "
                        f"bulletin ({fmt_date(dates.min())} → {fmt_date(dates.max())}) : "
                        + ", ".join(f"{y} : {n}" for y, n in by_year.items()) + " (fait : calendrier des numéros de BOC).")
        # Plus longue série de numéros consécutifs manquants (bornes : dernière et prochaine séances publiées).
        best: tuple[int, int] | None = None
        if "session_no" in s.columns and len(miss):
            no = miss["session_no"].astype(int).sort_values().to_numpy()
            start = prev = int(no[0])
            for x in list(no[1:]) + [None]:
                if x is not None and int(x) == prev + 1:
                    prev = int(x)
                    continue
                if best is None or prev - start > best[1] - best[0]:
                    best = (start, prev)
                if x is not None:
                    start = prev = int(x)
        if best is not None and best[1] > best[0]:
            g = miss[(miss["session_no"] >= best[0]) & (miss["session_no"] <= best[1])]
            iss = g["issue_no"] if "issue_no" in g.columns else None
            lo = g["gap_start"].min() if "gap_start" in g.columns else g["date"].min()
            hi = g["gap_end"].max() if "gap_end" in g.columns else g["date"].max()
            gaps_txt.append(f"Plus long trou : {len(g)} séances consécutives"
                            + (f" (N° {fmt_int(iss.min())} à {fmt_int(iss.max())})" if iss is not None else "")
                            + f", entre les BOC du {fmt_date(lo)} et du {fmt_date(hi)} ; les rendements qui couvrent "
                            "plusieurs séances et la fenêtre du 06/05 au 25/06/2021 sont exclus des statistiques "
                            "(§8.1, D1).")
    else:
        gaps_txt.append("129 séances réelles de 2017-2026 sans BOC téléchargeable, dont 96 en 2021 (N° 89-120 du 07/05 au "
                        "24/06/2021) (d'après docs/ARCHITECTURE.md ; calendrier sessions.parquet absent).")
    gaps_txt.append("Fenêtres des signaux comptées en séances avec seuils au prorata des BOC disponibles (additif v1.1, "
                    "D1) : un BOC manquant est une perte de nos données, pas une absence de cotation.")
    parts.append(_card(H("<h3>Trous de données</h3>"), _tag("fait"), _ul(gaps_txt)))
    val = ctx.try_get("validation", "résultats du test S1", ctx.validation) or {}
    inv = _get(val, "metrics", "runs", "REF_central_10M", "part_investie_moyenne")
    inv_txt = fmt_pct(inv, 0) if _ok(inv) else "82 %"
    open_pts = [
        "Indice TR des signaux non strictement daté : les signaux de momentum et de faible volatilité lisent un indice "
        "TR qui intègre le dividende corrigé dès le jour ex, avant la publication de la correction. Aucun effet n'a été "
        "trouvé sur S1 ; à corriger avant S2 (§8.5).",
        f"REF n'est investi qu'à {inv_txt} en moyenne sur S1, contre une cible de 98 % : les dividendes et le produit des "
        "sorties forcées restent en liquidités jusqu'au rebalancement annuel. L'écart de REF avec le TR ne mesure donc "
        "pas le seul coût de la réplication. Décision humaine, et un nouvel essai.",
        "Plancher D1 des filtres d'univers et âge des ordres après un trou de BOC : en 2021, REF est passé en liquidités "
        "d'août à octobre pendant que le TR montait. Décision humaine attendue.",
        "Le test S1 a été relancé une fois (D12) pour deux défauts de mesure prouvés par l'audit ; les deux passages "
        "sont décrits dans reports/validation_S1/tentatives.md, le premier résultat est conservé.",
    ]
    parts.append(_card(H("<h3>Points ouverts</h3>"), _tag("fait"),
                       _p("Limites connues, documentées au §8.5 de la spécification, dans le README et dans "
                          "tentatives.md ; aucune n'est corrigée dans les chiffres de ce rapport.", "muted small"),
                       _ul(open_pts)))
    od = ctx.try_get("order_dict", "ordre", ctx.order_dict)
    k = (od or {}).get("couts") or {}
    costs = [
        f"Courtage {fmt_pct(k.get('taux_courtage', 0.008), 2)} × (1 + taxe {fmt_pct(k.get('taux_tva', 0.18), 0)}) "
        "[taxe NON VÉRIFIÉ : TVA ou TAF] ; BRVM 0,20 % et DC/BR 0,10 % par côté (barèmes primaires).",
        f"Demi-spread : ½ × spread médian de clôture sur 120 séances (carnet du BOC) ; impact κ·√π avec κ = "
        f"{fmt_num(k.get('kappa', 0.016), 3)} (aucune étude d'impact publiée pour la BRVM : hypothèse).",
        f"Droits de garde {fmt_pct(k.get('taux_garde', 0.0025), 2)} par an et tenue de compte "
        f"{fmt_fcfa(k.get('frais_par_ligne', 5000))} par ligne et par an (SGI de type BICI ; 0 chez FGI).",
        "Exécution au plus tôt en t+1, participation ≤ 10 % de la valeur médiane échangée (MDV63), aucun achat à la "
        "borne haute ni vente à la borne basse ; règlement J+2 depuis le 04/12/2025.",
        "Scénarios du §7.2 : optimiste, central, stress, sévère ; les sensibilités du test S1 les publient.",
    ]
    parts.append(_card(H("<h3>Hypothèses de coûts (§7.2)</h3>"), _tag("hypothese"), _ul(costs)))
    proto = [
        "Échantillon vierge S1 (02/01/2017 → 16/11/2022) : test unique, paramètres et critères figés avant l'exécution "
        "(§8.3, additif v1.1 du 22/11/2026). Ce rapport ne calcule aucune performance sur S1 : il lit metrics.json.",
        "S0 (17/11/2022 → 20/11/2026) : contaminé, diagnostic seulement. S2 (suivi réel, à partir du 01/12/2026) : seul "
        "test réellement hors échantillon.",
        "Étalon : Composite Total Return (dividendes nets réinvestis), base 100 au 02/01/2025, publié au BOC depuis le "
        "02/01/2026 (avis 308-2025) et reconstruit avant cette date ; battre l'indice prix ne prouve rien.",
        "Distribution à 12 mois : bootstrap stationnaire des rendements hebdomadaires ; S0 seulement tant que S1 n'est "
        "pas exécuté (phase haussière : distribution probablement optimiste), toute l'histoire 2017-2026 ensuite, avec "
        "les poids actuels (biais rétrospectif signalé dans la section).",
        "Notes de l'analyste : poids bornés, aucun rôle sur S1 (D11) ; évaluation des indices : aide à la décision.",
    ]
    hist = ctx.historique or {}
    if hist and not hist.get("complet", True):
        proto.append("Ici, l'historique est incomplet (" + str(hist.get("raison") or "bulletins manquants") + ") : la "
                     "fenêtre réellement utilisée est plus courte que celle décrite ci-dessus (dates exactes dans la "
                     "section Distribution) ; les chiffres ne valent pas pour 2017-2026.")
    parts.append(_card(H("<h3>Protocole</h3>"), _ul(proto)))
    t = ctx.try_get("t", "date", ctx.t)
    src = [(lab, url) for lab, url in SOURCES]
    if t is not None:
        src.insert(1, (f"BOC du {fmt_date(t)} (PDF)", f"https://www.brvm.org/sites/default/files/boc_{t:%Y%m%d}_2.pdf"))
    links = "".join(f'<li><a class="src" href="{esc(u)}" rel="noopener noreferrer">{esc(lab)}</a>'
                    f'<span class="muted small url"> {esc(u)}</span></li>' for lab, u in src)
    parts.append(_card(H("<h3>Sources</h3>"), H(f'<ul class="facts sources">{links}</ul>'),
                       _p("Documents internes : docs/SPECIFICATION_STRATEGIE.md (§4.5, §8, §9.3, §10, additif v1.1), "
                          "docs/ARCHITECTURE.md, docs/research/01 à 08 (revues vérifiées). Données : data/panel "
                          "(BOC 2017-2026). Ce rapport est une aide à l'analyse, pas un conseil en investissement "
                          "personnalisé.", "muted small")))
    return _join(parts)


# ---------------------------------------------------------------------------
# Document
# ---------------------------------------------------------------------------

_CSS = """
:root {
  color-scheme: light;
  --surface-0: #f6f5f2; --surface-1: #fcfcfb; --border: #e3e2dd; --grid: #e1e0d9; --axis: #c3c2b7;
  --text-primary: #0b0b0b; --text-secondary: #52514e; --text-muted: #6f6e68;
  --series-1: #2a78d6; --series-2: #eb6834; --series-3: #1baf7a; --series-4: #eda100; --series-5: #e87ba4;
  --pos: #1f66c1; --neg: #c22f2f; --good: #006300; --critical: #c22f2f; --warning: #8a5a00;
  --warn-bg: #fff6e0; --warn-border: #fab219; --info-bg: #eef4fc; --info-border: #86b6ef;
  --err-bg: #fdecec; --err-border: #e34948; --chip: #efeee9; --shadow: rgba(0,0,0,.12);
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --surface-0: #121211; --surface-1: #1a1a19; --border: #2f2f2c; --grid: #2c2c2a; --axis: #383835;
    --text-primary: #f0efec; --text-secondary: #c3c2b7; --text-muted: #9a998f;
    --series-1: #3987e5; --series-2: #d95926; --series-3: #199e70; --series-4: #c98500; --series-5: #d55181;
    --pos: #5598e7; --neg: #e66767; --good: #0ca30c; --critical: #e66767; --warning: #fab219;
    --warn-bg: #2b2412; --warn-border: #b07d12; --info-bg: #14202e; --info-border: #1c5cab;
    --err-bg: #2e1616; --err-border: #a33a3a; --chip: #262624; --shadow: rgba(0,0,0,.5);
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --surface-0: #121211; --surface-1: #1a1a19; --border: #2f2f2c; --grid: #2c2c2a; --axis: #383835;
  --text-primary: #f0efec; --text-secondary: #c3c2b7; --text-muted: #9a998f;
  --series-1: #3987e5; --series-2: #d95926; --series-3: #199e70; --series-4: #c98500; --series-5: #d55181;
  --pos: #5598e7; --neg: #e66767; --good: #0ca30c; --critical: #e66767; --warning: #fab219;
  --warn-bg: #2b2412; --warn-border: #b07d12; --info-bg: #14202e; --info-border: #1c5cab;
  --err-bg: #2e1616; --err-border: #a33a3a; --chip: #262624; --shadow: rgba(0,0,0,.5);
}
* { box-sizing: border-box; }
html, body { margin: 0; }
body { background: var(--surface-0); color: var(--text-primary);
  font: 15px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; -webkit-font-smoothing: antialiased;
  overflow-wrap: break-word; }
.wrap { max-width: 1200px; margin: 0 auto; padding: 24px 16px 64px; }
.wrap > section, .card, .tile, .box, .banner, .grid3 > * { min-width: 0; }
header.top .hrow { display: flex; gap: 12px; align-items: flex-start; justify-content: space-between; }
header.top h1 { font-size: 24px; line-height: 1.25; margin: 0 0 4px; letter-spacing: -0.01em; }
header.top .sub { margin: 0; color: var(--text-secondary); }
p.limits { margin: 8px 0 4px; color: var(--text-secondary); font-size: 13.5px; max-width: 110ch; }
.toggle { flex: none; font: inherit; font-size: 12px; background: var(--chip); border: 1px solid var(--border);
  color: var(--text-secondary); border-radius: 6px; padding: 4px 8px; cursor: pointer; }
.banner { display: flex; gap: 12px; align-items: flex-start; margin: 16px 0 8px; padding: 12px 14px;
  background: var(--warn-bg); border: 1px solid var(--warn-border); border-radius: 10px; }
.banner p { margin: 2px 0 0; color: var(--text-secondary); }
.bi { flex: none; font-weight: 700; line-height: 1.4; }
h2 { font-size: 19px; margin: 40px 0 4px; letter-spacing: -0.005em; scroll-margin-top: 12px; }
h3 { font-size: 15px; margin: 0 0 8px; }
.lead { margin: 0 0 12px; color: var(--text-secondary); max-width: 75ch; }
p { margin: 8px 0; }
.small { font-size: 13px; }
.muted { color: var(--text-muted); }
.wrap .wrap { padding: 0; }
span.wrap { white-space: normal; display: inline-block; min-width: 180px; max-width: 420px; }
span.wrap.w2 { min-width: 260px; }
.card { background: var(--surface-1); border: 1px solid var(--border); border-radius: 12px; padding: 16px; margin-top: 12px; }
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; margin-top: 12px; }
.tile { background: var(--surface-1); border: 1px solid var(--border); border-radius: 12px; padding: 12px 14px; }
.tile .k { font-size: 13px; color: var(--text-secondary); }
.tile .v { font-size: 22px; font-weight: 650; font-variant-numeric: tabular-nums; margin-top: 2px; line-height: 1.3;
  overflow-wrap: normal; }
.tile .s { font-size: 12.5px; color: var(--text-muted); font-variant-numeric: tabular-nums; }
.tile .s .tag { margin-right: 2px; }
.tag { font-size: 11.5px; text-transform: uppercase; letter-spacing: .04em; padding: 0 5px; border-radius: 4px;
  border: 1px solid var(--border); color: var(--text-muted); white-space: nowrap; }
.t-fait { color: var(--good); border-color: currentColor; }
.t-estimation { color: var(--pos); border-color: currentColor; }
.t-hypothese { color: var(--warning); border-color: currentColor; }
.card > .tag { float: right; margin-left: 8px; }
.chip { display: inline-block; padding: 1px 8px; border-radius: 999px; background: var(--chip); font-size: 12.5px;
  color: var(--text-secondary); white-space: nowrap; font-weight: 600; }
.chip.ok, .chip.pos { color: var(--good); } .chip.no, .chip.neg { color: var(--critical); } .chip.warn { color: var(--warning); }
.tile .v .chip { font-size: 15px; }
.box { display: flex; gap: 10px; align-items: flex-start; padding: 10px 14px; border-radius: 10px; margin-top: 12px;
  border: 1px solid var(--info-border); background: var(--info-bg); }
.box.b-warn { border-color: var(--warn-border); background: var(--warn-bg); }
.box.b-err { border-color: var(--err-border); background: var(--err-bg); }
.box.b-empty { border-style: dashed; border-color: var(--border); background: var(--surface-1); color: var(--text-secondary); }
.box > div { min-width: 0; }
.box code { font-size: 12.5px; overflow-wrap: anywhere; }
.box pre { white-space: pre-wrap; overflow-wrap: anywhere; font-size: 12px; max-height: 260px; overflow: auto; }
.tablewrap { width: 100%; overflow-x: auto; -webkit-overflow-scrolling: touch; margin-top: 4px; }
table { border-collapse: collapse; width: 100%; font-size: 13.5px; font-variant-numeric: tabular-nums; }
caption { text-align: left; color: var(--text-secondary); padding: 4px 0; }
th, td { padding: 7px 8px; text-align: right; border-bottom: 1px solid var(--border); white-space: nowrap; vertical-align: top; }
th { font-weight: 600; color: var(--text-secondary); font-size: 12.5px; background: var(--surface-1); }
th.l, td.l { text-align: left; }
tfoot th { border-top: 1px solid var(--axis); }
td .name { max-width: 200px; overflow: hidden; text-overflow: ellipsis; }
td .motif { min-width: 220px; max-width: 320px; white-space: normal; }
td .cn { display: inline-block; white-space: normal; min-width: 110px; max-width: 200px; }
td .cv { white-space: normal; max-width: 120px; }
table.univ th, table.univ td { padding-left: 5px; padding-right: 5px; }
table.univ td .motif { min-width: 180px; }
table.univ td .name { max-width: 170px; }
td .desc { white-space: normal; min-width: 170px; max-width: 260px; }
td .lst { white-space: normal; min-width: 260px; }
td .lst ul.facts { margin: 0; } td .lst ul.facts li { margin: 2px 0; }
.fiche .nh { align-items: center; } .fiche ul.facts { margin: 6px 0 0; } .fiche ul.facts li { margin: 3px 0; }
.fiche code { font-size: 12.5px; overflow-wrap: anywhere; }
tbody tr:hover td { background: var(--chip); }
.neg { color: var(--neg); } .pos { color: var(--pos); }
ul.facts { margin: 6px 0 0; padding-left: 18px; } ul.facts li { margin: 6px 0; }
ul.sources .url { display: block; overflow-wrap: anywhere; }
details { margin-top: 10px; } details summary { cursor: pointer; font-weight: 600; padding: 4px 0; }
details .dbody { margin-top: 6px; }
.narrow-only { display: none; }
.grid3 { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 12px; }
.grid2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 12px; }
.grid2 > * { min-width: 0; }
span.url { overflow-wrap: anywhere; }
nav.toc { display: flex; flex-wrap: wrap; gap: 6px 14px; margin-top: 14px; font-size: 13.5px; }
a { color: var(--pos); }
.notes { display: grid; gap: 10px; }
.note { border: 1px solid var(--border); border-radius: 10px; padding: 10px 12px; background: var(--surface-1); }
.note .nh { display: flex; gap: 8px; flex-wrap: wrap; align-items: baseline; }
.note .ntext { white-space: pre-wrap; font-size: 13.5px; }
.note .nm { display: flex; flex-wrap: wrap; gap: 4px 16px; font-size: 13px; color: var(--text-secondary); }
.frag { overflow-x: auto; font-size: 13.5px; }
.frag td.t { white-space: normal; min-width: 200px; max-width: 460px; text-align: left; }
.frag td.t.long { min-width: 300px; max-width: 560px; }
.frag h1 { font-size: 17px; } .frag h2 { font-size: 15px; margin: 18px 0 6px; }
.frag table { display: block; overflow-x: auto; }
.chart { position: relative; margin: 8px 0 0; overflow: hidden; }
.chart figcaption { font-size: 12.5px; color: var(--text-muted); margin-top: 6px; }
.legend { display: flex; flex-wrap: wrap; gap: 6px 16px; font-size: 13px; color: var(--text-secondary); }
.legend .sw { display: inline-block; width: 16px; height: 0; border-top-width: 2px; border-top-style: solid; vertical-align: middle; margin-right: 6px; }
.legend .sw.dash { border-top-style: dashed; }
.plot { position: relative; margin-top: 8px; }
.plot .yax { position: absolute; left: 0; top: 8px; bottom: 28px; width: 50px; }
.plot .yax span { position: absolute; right: 8px; transform: translateY(-50%); font-size: 12px; color: var(--text-muted);
  font-variant-numeric: tabular-nums; white-space: nowrap; }
.plot .area { position: absolute; left: 54px; right: 8px; top: 8px; bottom: 28px; touch-action: pan-y; }
.plot svg { position: absolute; inset: 0; width: 100%; height: 100%; overflow: visible; display: block; }
.plot .xax { position: absolute; left: 0; right: 0; top: 100%; height: 26px; }
.plot .xax span { position: absolute; top: 6px; transform: translateX(-50%); font-size: 12px; color: var(--text-muted);
  white-space: nowrap; }
.grid { stroke: var(--grid); stroke-width: 1; }
.axis, .base { stroke: var(--axis); stroke-width: 1; }
.ln { fill: none; stroke-width: 2; stroke-linejoin: round; stroke-linecap: round; }
.k1 { stroke: var(--series-1); border-color: var(--series-1); } .k2 { stroke: var(--series-2); border-color: var(--series-2); }
.k3 { stroke: var(--series-3); border-color: var(--series-3); } .k4 { stroke: var(--series-4); border-color: var(--series-4); }
.k5 { stroke: var(--series-5); border-color: var(--series-5); }
.kink { stroke: var(--text-primary); border-color: var(--text-primary); }
.kmuted { stroke: var(--text-muted); border-color: var(--text-muted); }
.ln.dash { stroke-dasharray: 5 4; }
.bar { fill: var(--series-1); }
.mk { stroke: var(--text-secondary); stroke-width: 1.5; }
.mk.zero { stroke: var(--axis); } .mk.tr { stroke: var(--text-muted); stroke-dasharray: 4 3; }
.mk.med { stroke: var(--text-primary); stroke-width: 2; }
.mlab { position: absolute; inset: 0; pointer-events: none; }
.mlab .ml { position: absolute; transform: translateX(4px); font-size: 11.5px; white-space: nowrap; color: var(--text-secondary);
  background: color-mix(in srgb, var(--surface-1) 80%, transparent); padding: 0 3px; border-radius: 3px; }
.mlab .ml.r { transform: translateX(calc(-100% - 4px)); }
.mlab .ml.zero { display: none; }
.xh { position: absolute; top: 0; bottom: 0; width: 0; border-left: 1px solid var(--text-muted); display: none; pointer-events: none; }
.hl { position: absolute; top: 0; bottom: 0; background: var(--text-primary); opacity: .07; display: none; pointer-events: none; }
.dots .dot { position: absolute; width: 10px; height: 10px; border-radius: 50%; border: 2px solid var(--surface-1);
  transform: translate(-50%, -50%); display: none; pointer-events: none; }
.dot.k1 { background: var(--series-1); } .dot.k2 { background: var(--series-2); } .dot.k3 { background: var(--series-3); }
.dot.kink { background: var(--text-primary); } .dot.kmuted { background: var(--text-muted); }
.tip { position: absolute; z-index: 5; pointer-events: none; display: none; background: var(--surface-1);
  border: 1px solid var(--border); border-radius: 8px; padding: 7px 10px; font-size: 12.5px;
  box-shadow: 0 4px 14px var(--shadow); font-variant-numeric: tabular-nums; max-width: 280px; }
.tip b { display: block; margin-bottom: 2px; } .tip .row { display: flex; gap: 6px; align-items: center; white-space: nowrap; }
.tip .row i { display: inline-block; width: 12px; height: 0; border-top-width: 2px; border-top-style: solid; }
footer.foot { margin-top: 40px; color: var(--text-muted); font-size: 13px; border-top: 1px solid var(--border); padding-top: 12px; }
@media (max-width: 560px) {
  header.top h1 { font-size: 20px; }
  .tile .v { font-size: 19px; }
  .tiles { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
  .tile { padding: 10px; }
  .card { padding: 12px; }
  .plot .xax span.odd { display: none; }
  .plot .yax { width: 40px; } .plot .area { left: 44px; }
  span.wrap { min-width: 150px; max-width: 260px; }
  td .desc { min-width: 120px; max-width: 170px; }
  .narrow-only { display: block; }
  td .name { max-width: 140px; }
}
@media print { .toggle { display: none; } details { display: block; } }
"""

_JS = r"""
(function () {
  var root = document.documentElement, btn = document.getElementById('theme-toggle');
  var modes = ['auto', 'clair', 'sombre'], attr = {auto: null, clair: 'light', sombre: 'dark'};
  function apply(m) { if (attr[m]) root.setAttribute('data-theme', attr[m]); else root.removeAttribute('data-theme');
    if (btn) btn.textContent = 'Thème : ' + m; }
  var cur = 'auto';
  try { cur = localStorage.getItem('brvm-alpha-theme') || 'auto'; } catch (e) { cur = 'auto'; }
  if (modes.indexOf(cur) < 0) cur = 'auto';
  apply(cur);
  if (btn) btn.addEventListener('click', function () {
    cur = modes[(modes.indexOf(cur) + 1) % modes.length]; apply(cur);
    try { localStorage.setItem('brvm-alpha-theme', cur); } catch (e) { /* stockage indisponible */ }
  });
  var nf = function (v, d) { return v == null ? 'n.d.' : new Intl.NumberFormat('fr-FR',
    {minimumFractionDigits: d, maximumFractionDigits: d}).format(v); };
  var fd = function (ms) { var t = new Date(ms); var p = function (x) { return (x < 10 ? '0' : '') + x; };
    return p(t.getUTCDate()) + '/' + p(t.getUTCMonth() + 1) + '/' + t.getUTCFullYear(); };
  function el(tag, cls, txt) { var e = document.createElement(tag); if (cls) e.className = cls;
    if (txt != null) e.textContent = txt; return e; }
  function place(tip, area, px) { var w = area.clientWidth, tw = tip.offsetWidth, left = px + 12;
    if (left + tw > w) left = Math.max(0, px - 12 - tw); tip.style.left = left + 'px'; tip.style.top = '4px'; }
  document.querySelectorAll('figure.chart').forEach(function (fig) {
    var dEl = fig.querySelector('script.cdata'), area = fig.querySelector('.area'), tip = fig.querySelector('.tip');
    if (!dEl || !area || !tip) return;
    var D; try { D = JSON.parse(dEl.textContent); } catch (e) { return; }
    var hide = function () { tip.style.display = 'none'; fig.querySelectorAll('.xh,.hl,.dot').forEach(function (x) {
      x.style.display = 'none'; }); };
    var move = function (ev) {
      var r = area.getBoundingClientRect(), fx = (ev.clientX - r.left) / r.width;
      if (fx < 0 || fx > 1) { hide(); return; }
      while (tip.firstChild) tip.removeChild(tip.firstChild);
      if (D.kind === 'line') {
        var t0 = D.t[0], t1 = D.t[D.t.length - 1], tt = t0 + fx * (t1 - t0), i = 0, best = Infinity;
        for (var k = 0; k < D.t.length; k++) { var dd = Math.abs(D.t[k] - tt); if (dd < best) { best = dd; i = k; } }
        var x = (D.t[i] - t0) / (t1 - t0) * r.width, xh = fig.querySelector('.xh');
        xh.style.left = x + 'px'; xh.style.display = 'block';
        tip.appendChild(el('b', null, 'Semaine du ' + fd(D.t[i])));
        var dots = fig.querySelectorAll('.dot');
        D.s.forEach(function (s, j) {
          var v = s.v[i], row = el('div', 'row'), sw = el('i', s.k); row.appendChild(sw);
          row.appendChild(document.createTextNode(s.n + ' : ' + nf(v, 1))); tip.appendChild(row);
          if (dots[j]) { if (v == null) { dots[j].style.display = 'none'; } else {
            dots[j].style.left = x + 'px'; dots[j].style.top = ((1 - (v - D.y0) / (D.y1 - D.y0)) * r.height) + 'px';
            dots[j].style.display = 'block'; } }
        });
        tip.style.display = 'block'; place(tip, area, x);
      } else {
        var n = D.n, b = Math.min(n - 1, Math.max(0, Math.floor(fx * n))), hl = fig.querySelector('.hl');
        hl.style.left = (b / n * r.width) + 'px'; hl.style.width = (r.width / n) + 'px'; hl.style.display = 'block';
        tip.appendChild(el('div', null, D.tips[b])); tip.style.display = 'block'; place(tip, area, (b + 0.5) / n * r.width);
      }
    };
    area.addEventListener('pointermove', move); area.addEventListener('pointerdown', move);
    area.addEventListener('pointerleave', hide);
  });
})();
"""


def _rn_sous_bloc(ctx: _Ctx, section: str) -> H:
    """Sous-bloc du module « Rendement net et pertes » à la fin d'une section (§7.2) ; vide s'il échoue (la section
    garde son statut)."""
    try:
        from brvm_alpha.report import rendement_net as _rnr

        return H(_rnr.sous_bloc(ctx, section))
    except MemoryError:  # mémoire insuffisante : la commande s'arrête (code 6)
        raise
    except Exception:  # noqa: BLE001 - la section garde son statut « ok »
        return H("")


def render_report(asof: Any, capital: float, *, panels: Mapping[str, Any] | None = None,
                  panel_dir: str | Path | None = "data/panel", notes_root: str | Path | None = "data/notes",
                  validation_dir: str | Path | None = "reports/validation_S1",
                  diagnostic_dir: str | Path | None = "reports/diagnostic_S0", holdings: Mapping[str, int] | None = None,
                  variant: str | None = None, cash: float | None = None, costs: Any = "central",
                  registry_path: str | Path | None = None, n_boot: int = 5000, seed: int = 0,
                  recommend_kwargs: Mapping[str, Any] | None = None, now: Any = None,
                  notes_known_at: Any = None, historique: Mapping[str, Any] | None = None) -> RapportHTML:
    """Construit le rapport en mémoire (voir :func:`build_report`) et renvoie le HTML et le statut
    de chaque section (``ok``, ``indisponible``, ``erreur``).

    ``notes_known_at`` : ``None`` (défaut sûr : mode historique, notes en règle stricte à la date des
    données) ou instant de connaissance des notes (mode direct, passé par la ligne de commande et
    l'interface quand la date est la dernière séance du panel). ``historique`` : état de l'historique
    (``brvm_alpha.cli.history_state`` : ``complet``, ``raison``, ``avertissement``) ; incomplet, un
    avertissement fort est placé en tête du rapport."""
    if capital is None or not _ok(capital) or float(capital) <= 0:
        raise ValueError("capital doit être un nombre > 0 (FCFA)")
    now_ts = pd.Timestamp.now(tz="UTC") if now is None else pd.Timestamp(now)
    if now_ts.tzinfo is None:
        now_ts = now_ts.tz_localize("UTC")
    ctx = _Ctx(asof, capital, panels=panels, panel_dir=panel_dir, notes_root=notes_root,
               validation_dir=validation_dir, diagnostic_dir=diagnostic_dir, holdings=holdings, variant=variant,
               cash=cash, costs=costs, registry_path=registry_path, n_boot=n_boot, seed=seed,
               recommend_kwargs=recommend_kwargs, now=now_ts, notes_known_at=notes_known_at, historique=historique)
    results: list[SectionResult] = []
    leads = {
        "marche": "Faits du bulletin officiel de la cote à la date des données ; le taux de référence est une estimation.",
        "s1": "Test unique pré-enregistré sur l'échantillon vierge 02/01/2017 → 16/11/2022 (additif v1.1) : résultats lus "
              "dans metrics.json, jamais recalculés ici.",
        "ordre": "Du poids cible au carnet d'ordres, au titre et au franc près (portfolio.recommend).",
        "revenus": "Dividendes attendus sur 12 mois, nets de l'IRVM du pays de l'émetteur.",
        "distribution": "Bootstrap stationnaire des rendements hebdomadaires : une distribution historique, pas une "
                        "prévision ; puis les scénarios de stress du §9.3.",
        "indices": "Évaluation des indices (notes.index_eval) : SURPONDÉRER, NEUTRE ou SOUS-PONDÉRER, avec confiance et raisons.",
        "notes": "Journal des notes de l'analyste (data/notes) : notes en vigueur à la séance d'application, filtres "
                 "actifs, notes extrêmes, composante « notes » de chaque indice et surcouches.",
        "risques": "Filtres R, règles pays, événements à venir et valorisation du marché.",
        "univers": "Tous les titres du panel à la date : éligibilité (U1-U10), motif, score, rang et blocs de signaux.",
        "methode": "Ce que la plate-forme ne peut pas promettre, limites des données et hypothèses.",
    }
    fns: dict[str, Callable[[], Any]] = {
        "bandeau": lambda: H(_sec_bandeau(ctx) + _rn_sous_bloc(ctx, "bandeau")), "marche": lambda: _sec_marche(ctx),
        "s1": lambda: _sec_s1(ctx), "ordre": lambda: H(_sec_ordre(ctx) + _rn_sous_bloc(ctx, "ordre")),
        "revenus": lambda: H(_sec_revenus(ctx) + _rn_sous_bloc(ctx, "revenus")),
        "distribution": lambda: H(_sec_distribution(ctx) + _rn_sous_bloc(ctx, "distribution")),
        "indices": lambda: _sec_indices(ctx), "notes": lambda: _sec_notes(ctx),
        "risques": lambda: H(_sec_risques(ctx) + _rn_sous_bloc(ctx, "risques")), "univers": lambda: _sec_univers(ctx),
        "methode": lambda: H(_sec_methode(ctx) + _rn_sous_bloc(ctx, "methode")),
    }
    body = []
    for sid, title in SECTIONS:
        body.append(_run_section(sid, title, leads.get(sid), fns[sid], results, heading=(sid != "bandeau")))
    t = ctx.try_get("t", "date", ctx.t)
    val = ctx.try_get("validation", "validation", ctx.validation) or {}
    st = _strategy_status(val) if val else {"code": "NON TESTÉ"}
    summary = ", ".join(f"{r.id}={r.statut}" for r in results)
    foot = (f'<footer class="foot"><p><strong>{esc(BANNER)}</strong> Statut : {esc(st["code"])}.</p>'
            f'<p>Rapport généré par brvm_alpha.report le {esc(now_ts.strftime("%d/%m/%Y à %H:%M UTC"))} ; données au '
            f'{esc(fmt_date(t))}. Aide à l\'analyse, pas un conseil en investissement personnalisé. Sections : '
            f'{esc(summary)}.</p></footer>')
    title = f"BRVM Alpha — rapport au {fmt_date(t) if t is not None else fmt_date(ctx.asof_req)}"
    doc = ("<!doctype html>\n<html lang=\"fr\">\n<head>\n<meta charset=\"utf-8\">\n"
           "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
           f"<meta name=\"generator\" content=\"brvm_alpha.report\">\n<meta name=\"brvm-alpha-sections\" "
           f"content=\"{esc(summary)}\">\n<title>{esc(title)}</title>\n<style>{_CSS}</style>\n</head>\n<body>\n"
           f"<div class=\"wrap\">\n" + "\n".join(body) + "\n" + foot + "\n</div>\n<script>" + _JS + "</script>\n"
           "</body>\n</html>\n")
    meta = {"timings": dict(ctx.timings), "statut": st.get("code"), "taille_octets": len(doc.encode("utf-8"))}
    return RapportHTML(html=doc, sections=results, asof=t, meta=meta)


def build_report(asof: Any, capital: float, out_path: str | Path, *, panels: Mapping[str, Any] | None = None,
                 panel_dir: str | Path | None = "data/panel", notes_root: str | Path | None = "data/notes",
                 validation_dir: str | Path | None = "reports/validation_S1",
                 diagnostic_dir: str | Path | None = "reports/diagnostic_S0",
                 holdings: Mapping[str, int] | None = None, variant: str | None = None,
                 rendu: list[RapportHTML] | None = None, **kwargs: Any) -> Path:
    """Écrit le rapport HTML autonome à ``out_path`` (écriture atomique) et renvoie son chemin.

    Parameters
    ----------
    asof
        Date demandée ; les données sont celles de la dernière séance du panel au plus tard à cette date.
    capital
        Capital total en FCFA (titres détenus compris).
    out_path
        Fichier HTML à écrire (dossiers créés au besoin).
    panels
        Panels de :func:`brvm_alpha.strategy.build_panels` (défaut : construits depuis ``panel_dir``).
    panel_dir
        Panel du dépôt : tables longues (indices, marché, séances, actions) et panels du moteur.
    notes_root
        Journal des notes de l'analyste (``NoteStore``) ; absent : encadré « aucune note ».
    validation_dir, diagnostic_dir
        Résultats du test unique S1 (lus, jamais recalculés) et du diagnostic S0 (contaminé).
    holdings, variant
        Titres détenus (symbole → nombre) et variante imposée (défaut : choix de ``choose_variant``).
    **kwargs
        Options de :func:`render_report` : ``cash``, ``costs``, ``registry_path``, ``n_boot``, ``seed``,
        ``recommend_kwargs``, ``now``, ``notes_known_at`` (instant de connaissance des notes du mode
        direct ; défaut ``None`` : mode historique), ``historique`` (état de l'historique).
    rendu
        Liste qui reçoit le :class:`RapportHTML` rendu (statut de chaque section) : la ligne de commande
        en tire l'état des sections et son code de sortie.
    """
    rep = ecrire_rapport(asof, capital, out_path, panels=panels, panel_dir=panel_dir, notes_root=notes_root,
                         validation_dir=validation_dir, diagnostic_dir=diagnostic_dir, holdings=holdings,
                         variant=variant, **kwargs)
    if rendu is not None:
        rendu.append(rep)
    return rep.chemin if rep.chemin is not None else Path(out_path)


def ecrire_rapport(asof: Any, capital: float, out_path: str | Path, **kwargs: Any) -> RapportHTML:
    """Rend le rapport (:func:`render_report`) et l'écrit de façon atomique à ``out_path`` ; renvoie le rapport
    rendu (``chemin`` : fichier écrit ; ``sections`` : statut de chaque section)."""
    rep = render_report(asof, capital, **kwargs)
    rep.write(out_path)
    return rep
