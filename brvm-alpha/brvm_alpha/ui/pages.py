"""Pages HTML de l'interface locale (fonctions pures : données en entrée, document HTML en sortie).

Règles de rendu :

- **tout texte** issu des données, des notes, des fichiers ou de la saisie passe par :func:`esc`
  (``html.escape`` avec guillemets) ; seuls les fragments construits ici ou par
  ``OrdreDeBataille.to_html_fragment`` (texte déjà échappé par ``portfolio.recommend``) sont
  insérés tels quels, enveloppés dans :class:`Safe` ;
- aucune ressource externe : styles et script en ligne (script autorisé par un *nonce* de la
  politique CSP), aucun gestionnaire d'événement dans les attributs ;
- couleurs en variables CSS sur ``:root``, redéfinies pour le thème sombre (préférence du système
  ou bouton « Thème ») ; gouttière de 16 px ; tableaux larges dans ``.tablewrap`` (aucun défilement
  horizontal de la page) : utilisable sur téléphone ;
- chaque page porte la bannière « Performance passée ≠ garantie. Aucun gain n'est garanti. » et
  distingue faits, estimations et hypothèses ;
- les pages Tableau de bord, Notes, Indices et Portefeuille affichent la ligne datée des notes
  (« Notes connues au …, appliquées à la séance du … : N en vigueur (dont M manuelles), F filtre(s)
  de risque actif(s) ») : :func:`notes_status_block`.
"""

from __future__ import annotations

import html as _html
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import pandas as pd

from brvm_alpha.cli import BANNER, RULES_POLITENESS, fr_date, fr_num, fr_pct

# ---------------------------------------------------------------------------
# Échappement et petits composants
# ---------------------------------------------------------------------------


class Safe(str):
    """Fragment HTML sûr (déjà échappé ou construit par ce module)."""

    __slots__ = ()


def esc(x: Any) -> Safe:
    """Texte échappé pour HTML (``<``, ``>``, ``&``, guillemets simples et doubles)."""
    if isinstance(x, Safe):
        return x
    return Safe(_html.escape("" if x is None else str(x), quote=True))


def _c(x: Any) -> Safe:
    return x if isinstance(x, Safe) else esc(x)


def join(parts: Iterable[Any], sep: str = "") -> Safe:
    return Safe(sep.join(_c(p) for p in parts))


def q(value: Any) -> str:
    """Valeur encodée pour une URL (paramètre de requête)."""
    return quote(str(value or ""), safe="")


def link(href: str, text: Any, cls: str = "") -> Safe:
    """Lien interne (``href`` construit par le serveur, jamais tiré d'une saisie brute)."""
    c = f' class="{esc(cls)}"' if cls else ""
    return Safe(f'<a href="{esc(href)}"{c}>{_c(text)}</a>')


def ext_link(url: Any, text: Any = None) -> Safe:
    """Lien externe : http(s) seulement (sinon texte simple), sans référent."""
    u = str(url or "").strip()
    if not re.match(r"^https?://", u, re.I):
        return esc(u)
    return Safe(f'<a href="{esc(u)}" rel="noopener noreferrer nofollow" target="_blank">{_c(text or u)}</a>')


def table(headers: Sequence[Any], rows: Iterable[Sequence[Any]], cls: str = "", empty: str = "Aucune ligne.") -> Safe:
    rows = list(rows)
    if not rows:
        return Safe(f'<p class="muted">{esc(empty)}</p>')
    head = "".join(f'<th scope="col">{_c(h)}</th>' for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{_c(c)}</td>" for c in r) + "</tr>" for r in rows)
    c = f' class="{esc(cls)}"' if cls else ""
    return Safe(f'<div class="tablewrap"><table{c}><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>')


def dl(items: Iterable[tuple[Any, Any]]) -> Safe:
    return Safe('<dl class="kv">' + "".join(f"<dt>{_c(k)}</dt><dd>{_c(v)}</dd>" for k, v in items) + "</dl>")


def box(kind: str, content: Any, title: str | None = None) -> Safe:
    """Encadré : ``info``, ``warn``, ``error``, ``ok``, ``fact``, ``estimate``, ``hypothesis``."""
    t = f"<strong>{esc(title)}</strong> " if title else ""
    return Safe(f'<div class="box {esc(kind)}" role="note">{t}{_c(content)}</div>')


def csrf_field(token: str) -> Safe:
    return Safe(f'<input type="hidden" name="_jeton" value="{esc(token)}">')


def stance_badge(stance: Any) -> Safe:
    s = str(stance or "")
    cls = {"SURPONDÉRER": "up", "SOUS-PONDÉRER": "down", "NEUTRE": "flat",
           "haussier": "up", "baissier": "down", "neutre": "flat"}.get(s, "flat")
    return Safe(f'<span class="badge {cls}">{esc(s or "—")}</span>')


def _fmt_value(v: Any) -> str:
    """Valeur extraite lisible (nombres au format français, listes et dictionnaires en texte)."""
    if isinstance(v, bool):
        return "oui" if v else "non"
    if isinstance(v, int):
        return fr_num(v, 0)
    if isinstance(v, float):
        return fr_num(v, 4 if abs(v) < 10 else 2).rstrip("0").rstrip(",") if v == v else "n.d."
    if isinstance(v, (dict, list, tuple)):
        return str(v)
    return str(v)


def _val(x: Any) -> Any:
    if isinstance(x, (list, dict, tuple)):
        return x
    try:
        return None if pd.isna(x) else x
    except (TypeError, ValueError):
        return x


# ---------------------------------------------------------------------------
# Markdown sûr (résultats de la validation)
# ---------------------------------------------------------------------------


def _md_inline(text: str) -> str:
    parts = re.split(r"(`[^`]*`)", text)
    out = []
    for p in parts:
        if len(p) >= 2 and p.startswith("`") and p.endswith("`"):
            out.append(f"<code>{_html.escape(p[1:-1], quote=True)}</code>")
            continue
        e = _html.escape(p, quote=True)
        e = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", e)
        e = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", e)
        e = re.sub(r"(?<![\w])_(?!\s)([^_]+?)(?<!\s)_(?![\w])", r"<em>\1</em>", e)
        e = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)",
                   r'<a href="\2" rel="noopener noreferrer nofollow" target="_blank">\1</a>', e)
        out.append(e)
    return "".join(out)


def _md_cells(line: str) -> list[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def md_to_html(text: str) -> Safe:
    """Markdown → HTML **sûr** (titres, tableaux, listes, citations, code, gras) : tout est échappé."""
    lines = str(text or "").splitlines()
    out: list[str] = []
    para: list[str] = []

    def flush() -> None:
        if para:
            out.append("<p>" + " ".join(_md_inline(x.strip()) for x in para) + "</p>")
            para.clear()

    i = 0
    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if not s:
            flush()
            i += 1
            continue
        if s.startswith("```"):
            flush()
            j = i + 1
            code: list[str] = []
            while j < len(lines) and not lines[j].strip().startswith("```"):
                code.append(lines[j])
                j += 1
            out.append("<pre><code>" + _html.escape("\n".join(code), quote=True) + "</code></pre>")
            i = j + 1
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", s)
        if m:
            flush()
            lvl = min(len(m.group(1)) + 1, 6)
            out.append(f"<h{lvl}>{_md_inline(m.group(2))}</h{lvl}>")
            i += 1
            continue
        if re.fullmatch(r"(-{3,}|\*{3,}|_{3,})", s):
            flush()
            out.append("<hr>")
            i += 1
            continue
        if s.startswith("|"):
            flush()
            block = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                block.append(lines[i])
                i += 1
            rows = [_md_cells(b) for b in block if not re.fullmatch(r"\|?[\s:|-]+\|?", b.strip())]
            if rows:
                head = "".join(f'<th scope="col">{_md_inline(c)}</th>' for c in rows[0])
                body = "".join("<tr>" + "".join(f"<td>{_md_inline(c)}</td>" for c in r) + "</tr>" for r in rows[1:])
                out.append(f'<div class="tablewrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>')
            continue
        if s.startswith(">"):
            flush()
            quote_lines = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote_lines.append(lines[i].strip()[1:].strip())
                i += 1
            out.append("<blockquote><p>" + "<br>".join(_md_inline(x) for x in quote_lines) + "</p></blockquote>")
            continue
        if re.match(r"^\s*([-*+]|\d+[.)])\s+", line):
            flush()
            ordered = bool(re.match(r"^\s*\d+[.)]\s+", line))
            items = []
            while i < len(lines) and re.match(r"^\s*([-*+]|\d+[.)])\s+", lines[i]):
                items.append(re.sub(r"^\s*([-*+]|\d+[.)])\s+", "", lines[i]))
                i += 1
                while i < len(lines) and lines[i].startswith("  ") and lines[i].strip() and not re.match(
                        r"^\s*([-*+]|\d+[.)])\s+", lines[i]):
                    items[-1] += " " + lines[i].strip()
                    i += 1
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>" + "".join(f"<li>{_md_inline(x)}</li>" for x in items) + f"</{tag}>")
            continue
        para.append(line)
        i += 1
    flush()
    return Safe("\n".join(out))


# ---------------------------------------------------------------------------
# Gabarit
# ---------------------------------------------------------------------------

CSS = """
:root{--bg:#f6f6f3;--surface:#ffffff;--fg:#1b1f23;--muted:#5d6770;--line:#d9dde1;--accent:#1c5b8c;
--accent-fg:#ffffff;--ok:#1d7238;--warn:#9a5b00;--bad:#b3261e;--code:#eef0f2;--up:#1d7238;--down:#b3261e;
--flat:#5d6770;--focus:#2f7fc1}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#121518;--surface:#1a1f24;--fg:#e5e8eb;
--muted:#9ba6b0;--line:#2f3740;--accent:#7db3df;--accent-fg:#0d1114;--ok:#6cc58a;--warn:#e2a64b;--bad:#f08a80;
--code:#232a31;--up:#6cc58a;--down:#f08a80;--flat:#9ba6b0;--focus:#7db3df}}
:root[data-theme="dark"]{--bg:#121518;--surface:#1a1f24;--fg:#e5e8eb;--muted:#9ba6b0;--line:#2f3740;--accent:#7db3df;
--accent-fg:#0d1114;--ok:#6cc58a;--warn:#e2a64b;--bad:#f08a80;--code:#232a31;--up:#6cc58a;--down:#f08a80;
--flat:#9ba6b0;--focus:#7db3df}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
overflow-wrap:anywhere}
a{color:var(--accent)}
a:focus-visible,button:focus-visible,input:focus-visible,select:focus-visible,textarea:focus-visible,summary:focus-visible{
outline:2px solid var(--focus);outline-offset:2px}
header.top{background:var(--surface);border-bottom:1px solid var(--line)}
.top .in{max-width:1180px;margin:0 auto;padding:10px 16px;display:flex;flex-wrap:wrap;gap:8px 16px;align-items:center}
.brand{font-weight:700;font-size:17px;color:var(--fg);text-decoration:none;margin-right:auto}
nav.main{display:flex;flex-wrap:wrap;gap:4px}
nav.main a{padding:6px 10px;border-radius:6px;text-decoration:none;color:var(--fg)}
nav.main a[aria-current="page"]{background:var(--accent);color:var(--accent-fg)}
button,.btn{font:inherit;padding:7px 14px;border-radius:6px;border:1px solid var(--accent);background:var(--accent);
color:var(--accent-fg);cursor:pointer;text-decoration:none;display:inline-block;min-height:36px}
button.secondary,.btn.secondary{background:transparent;color:var(--accent)}
button.danger{background:var(--bad);border-color:var(--bad);color:#fff}
main{max-width:1180px;margin:0 auto;padding:16px}
.banner{border-left:4px solid var(--warn);background:var(--surface);padding:8px 12px;margin:0 0 12px;font-weight:600}
h1{font-size:22px;margin:4px 0 12px}h2{font-size:18px;margin:22px 0 8px}h3{font-size:16px;margin:16px 0 6px}
h4,h5,h6{font-size:15px;margin:12px 0 4px}
section.card{background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:12px 16px;margin:0 0 16px}
.muted{color:var(--muted)}
.tablewrap{overflow-x:auto;max-width:100%;margin:6px 0 10px}
table{border-collapse:collapse;font-size:13.5px;min-width:100%}
th,td{border-bottom:1px solid var(--line);padding:5px 7px;text-align:left;vertical-align:top}
th{font-weight:600;white-space:nowrap}
td.num,th.num{text-align:right;white-space:nowrap}
td:first-child{white-space:nowrap}
.box{border:1px solid var(--line);border-left-width:4px;border-radius:6px;padding:8px 12px;margin:8px 0;background:var(--surface)}
.box.info{border-left-color:var(--accent)}.box.warn{border-left-color:var(--warn)}.box.error{border-left-color:var(--bad)}
.box.ok{border-left-color:var(--ok)}.box.fact{border-left-color:var(--ok)}.box.estimate{border-left-color:var(--warn)}
.box.hypothesis{border-left-color:var(--muted)}
.badge{display:inline-block;padding:1px 8px;border-radius:10px;font-size:12.5px;font-weight:600;border:1px solid currentColor;
white-space:nowrap}
.badge.up{color:var(--up)}.badge.down{color:var(--down)}.badge.flat{color:var(--flat)}
form.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px 16px;align-items:end}
form.grid .wide{grid-column:1/-1}
label{display:block;font-weight:600;font-size:13.5px;margin-bottom:3px}
label.inline{display:inline;font-weight:400}
input[type=text],input[type=url],input[type=number],input[type=date],input[type=time],input[type=search],select,textarea{
width:100%;font:inherit;padding:7px 9px;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--fg)}
textarea{min-height:140px;resize:vertical}
.hint{font-size:12.5px;color:var(--muted);margin-top:2px;font-weight:400}
.row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.row>input{flex:1 1 160px;width:auto}
dl.kv{display:grid;grid-template-columns:minmax(120px,max-content) 1fr;gap:4px 14px;margin:6px 0}
dl.kv dt{font-weight:600;color:var(--muted)}dl.kv dd{margin:0}
pre,code{background:var(--code);border-radius:4px}
code{padding:0 3px;font-size:13px}
pre{padding:10px;overflow-x:auto;white-space:pre-wrap;font-size:13px}
pre.log{max-height:320px;overflow-y:auto}
blockquote{margin:8px 0;padding:6px 12px;border-left:3px solid var(--line);color:var(--muted)}
details{margin:6px 0}summary{cursor:pointer;font-weight:600}
iframe.report{width:100%;height:75vh;border:1px solid var(--line);border-radius:6px;background:var(--surface)}
footer.foot{max-width:1180px;margin:0 auto;padding:16px;color:var(--muted);font-size:13px}
.legend span{margin-right:12px}
.brvm-ordre-de-bataille .bandeau{border-left:4px solid var(--warn);padding:6px 10px}
.brvm-ordre-de-bataille .avertissement{border-left:4px solid var(--warn);padding:4px 10px}
.brvm-ordre-de-bataille table{display:block;overflow-x:auto;max-width:100%}
@media (max-width:640px){body{font-size:14.5px}h1{font-size:20px}nav.main a{padding:6px 8px}th,td{padding:4px 5px}}
"""

HEAD_JS = """(function(){try{var t=localStorage.getItem('brvm-theme');if(t==='light'||t==='dark'){
document.documentElement.setAttribute('data-theme',t);}}catch(e){}})();"""

BODY_JS = r"""(function(){
var root=document.documentElement;
function getT(){try{return localStorage.getItem('brvm-theme');}catch(e){return null;}}
function setT(v){try{if(v){localStorage.setItem('brvm-theme',v);}else{localStorage.removeItem('brvm-theme');}}catch(e){}}
function apply(v){if(v==='light'||v==='dark'){root.setAttribute('data-theme',v);}else{root.removeAttribute('data-theme');}
var b=document.getElementById('theme');if(b){b.textContent='Thème : '+(v==='light'?'clair':(v==='dark'?'sombre':'auto'));}}
apply(getT());
var tb=document.getElementById('theme');
if(tb){tb.addEventListener('click',function(){var c=getT();var n=(c===null)?'light':(c==='light'?'dark':null);setT(n);apply(n);});}
Array.prototype.forEach.call(document.querySelectorAll('form[data-confirm]'),function(f){
f.addEventListener('submit',function(ev){if(!window.confirm(f.getAttribute('data-confirm'))){ev.preventDefault();}});});
Array.prototype.forEach.call(document.querySelectorAll('[data-add-target]'),function(btn){
btn.addEventListener('click',function(){var src=document.getElementById(btn.getAttribute('data-src'));
var dst=document.getElementById(btn.getAttribute('data-dst'));if(!src||!dst){return;}
var v=(src.value||'').trim();if(!v){return;}
var cur=dst.value.split(',').map(function(s){return s.trim();}).filter(function(s){return s.length>0;});
if(cur.indexOf(v)<0){cur.push(v);}dst.value=cur.join(', ');src.value='';src.focus();});});
var jp=document.querySelector('[data-job-id]');
if(jp){var st0=jp.getAttribute('data-job-state');
if(st0==='en cours'||st0==='en attente'){var id=jp.getAttribute('data-job-id');
var timer=setInterval(function(){fetch('/api/travail?id='+encodeURIComponent(id),{credentials:'same-origin',cache:'no-store'})
.then(function(r){return r.json();}).then(function(s){
var st=jp.querySelector('[data-job-status]');if(st){st.textContent=s.statut;}
var pr=jp.querySelector('[data-job-progress]');if(pr){pr.textContent=s.progression||'';}
var lg=jp.querySelector('[data-job-log]');if(lg){lg.textContent=(s.journal||[]).join('\n');lg.scrollTop=lg.scrollHeight;}
if(s.termine){clearInterval(timer);window.location.reload();}}).catch(function(){});},2000);}}
})();"""

NAV: tuple[tuple[str, str, str], ...] = (
    ("/", "Tableau de bord", "accueil"),
    ("/notes", "Notes", "notes"),
    ("/recherche", "Recherche", "recherche"),
    ("/indices", "Indices", "indices"),
    ("/portefeuille", "Portefeuille", "portefeuille"),
    ("/expliquer", "Expliquer", "expliquer"),
    ("/validation", "Validation", "validation"),
)

LEGEND = Safe('<p class="legend muted"><span><strong>Fait</strong> : publié (BOC, brvm.org, registre)</span>'
              '<span><strong>Estimation</strong> : calcul sous hypothèses (coûts, exécution, distribution)</span>'
              '<span><strong>Hypothèse</strong> : choix de modélisation non vérifiable</span></p>')


@dataclass
class PageContext:
    """Contexte d'une page : jeton anti-CSRF (formulaires POST) et nonce CSP (scripts)."""

    token: str
    nonce: str


def layout(ctx: PageContext, title: str, body: Any, *, active: str = "", flash: Any = None) -> str:
    """Document HTML complet (navigation, bannière, contenu, pied de page).

    ``body`` est un fragment **construit par ce module** (inséré tel quel) ; ``title`` et ``flash``
    sont échappés.
    """
    nav = "".join(
        f'<a href="{esc(href)}"' + (' aria-current="page"' if key == active else "") + f">{esc(label)}</a>"
        for href, label, key in NAV
    )
    fl = ""
    if flash:
        kind, msg = flash if isinstance(flash, tuple) else ("ok", flash)
        fl = box(kind, msg)
    n = esc(ctx.nonce)
    return (
        "<!doctype html>\n<html lang=\"fr\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        "<meta name=\"color-scheme\" content=\"light dark\">\n<meta name=\"referrer\" content=\"no-referrer\">\n"
        f"<title>{esc(title)} — BRVM Alpha</title>\n<style nonce=\"{n}\">{CSS}</style>\n"
        f"<script nonce=\"{n}\">{HEAD_JS}</script>\n</head>\n<body>\n"
        f"<header class=\"top\"><div class=\"in\"><a class=\"brand\" href=\"/\">BRVM Alpha</a>"
        f"<nav class=\"main\" aria-label=\"Navigation principale\">{nav}</nav>"
        "<button type=\"button\" id=\"theme\" class=\"secondary\">Thème : auto</button></div></header>\n"
        f"<main>\n<p class=\"banner\" role=\"note\">{esc(BANNER)}</p>\n{fl}<h1>{esc(title)}</h1>\n{body}\n</main>\n"
        f"<footer class=\"foot\">{LEGEND}<p>Interface locale de BRVM Alpha (127.0.0.1) : aide à l'analyse, pas un "
        "conseil en investissement personnalisé. Aucune ressource externe n'est chargée. "
        f"{esc(BANNER)}</p></footer>\n<script nonce=\"{n}\">{BODY_JS}</script>\n</body>\n</html>\n"
    )


def error_page(ctx: PageContext, status: int, title: str, message: Any) -> str:
    body = box("error", message) + Safe(f'<p>{link("/", "Retour au tableau de bord")}</p>')
    return layout(ctx, f"{title} (erreur {int(status)})", body)


# ---------------------------------------------------------------------------
# Travaux (opérations longues)
# ---------------------------------------------------------------------------


def job_panel(job: Mapping[str, Any] | None, *, result_link: Any = None) -> Safe:
    """État d'un travail (statut, progression, journal) ; actualisé par le script de la page."""
    if not job:
        return Safe("")
    state = str(job.get("statut") or "")
    log_txt = "\n".join(job.get("journal") or [])
    err = box("error", job.get("erreur"), "Échec :") if job.get("erreur") else Safe("")
    extra = Safe(f"<p>{_c(result_link)}</p>") if result_link and state == "terminé" else Safe("")
    noscript = Safe('<noscript><p class="muted">Sans JavaScript : recharger la page pour suivre la progression.'
                    "</p></noscript>")
    return Safe(
        f'<section class="card" data-job-id="{esc(job.get("id"))}" data-job-state="{esc(state)}">'
        f'<h2>Travail : {esc(job.get("libelle"))}</h2>'
        + dl([("Statut", Safe(f'<span data-job-status>{esc(state)}</span>')),
              ("Progression", Safe(f'<span data-job-progress>{esc(job.get("progression") or "")}</span>')),
              ("Lancé le", esc(job.get("debut") or "—")), ("Terminé le", esc(job.get("fin") or "—"))])
        + err + extra + noscript
        + f'<details{" open" if state in ("en cours", "en attente") else ""}><summary>Journal</summary>'
          f'<pre class="log" data-job-log>{esc(log_txt)}</pre></details></section>'
    )


# ---------------------------------------------------------------------------
# Cibles : aide à la saisie
# ---------------------------------------------------------------------------


def target_options(symbol_names: Mapping[str, str] | None = None) -> list[tuple[str, str]]:
    """Codes de cibles proposés (code, libellé) : symboles, indices, pays, secteurs, thèmes, marché."""
    from brvm_alpha.notes import model as m
    from brvm_alpha.reference import COUNTRY_NAMES

    names = dict(symbol_names or {})
    out: list[tuple[str, str]] = []
    for s in sorted(set(m.KNOWN_SYMBOLS) | set(names)):
        out.append((s, names.get(s, "action BRVM")))
    for code, (label, _n) in m.INDEX_TARGETS.items():
        out.append((code, "indice " + label))
    for sec, label in m.SECTOR_LABELS.items():
        if sec in m.SECTOR_INDEX_NAMES:
            out.append((f"IDX:SECT:{sec}", "indice sectoriel " + label))
    for c, label in COUNTRY_NAMES.items():
        out.append((f"PAYS:{c}", label))
    for sec, label in m.SECTOR_LABELS.items():
        out.append((f"SECT:{sec}", "secteur " + label))
    for th, label in m.THEMES.items():
        out.append((f"THEME:{th}", "thème " + label))
    out.append(("MARCHE", "marché (BRVM)"))
    return out


def datalist(dl_id: str, options: Iterable[tuple[str, str]]) -> Safe:
    return Safe(f'<datalist id="{esc(dl_id)}">'
                + "".join(f'<option value="{esc(v)}">{esc(lab)}</option>' for v, lab in options) + "</datalist>")


TARGET_HELP = Safe(
    "<details><summary>Aide à la saisie des codes de cibles</summary>"
    + table(["Type", "Code", "Exemples"], [
        ["Action", "SYMBOLE", "SNTS (Sonatel), ORAC, SGBC ; un nom est accepté : « Sonatel »"],
        ["Indice", "IDX:…", "IDX:BRVM-C, IDX:BRVM-30, IDX:PRESTIGE, IDX:PRINCIPAL, IDX:BRVM-C-TR"],
        ["Indice sectoriel", "IDX:SECT:…", "IDX:SECT:FIN, IDX:SECT:TEL"],
        ["Pays", "PAYS:…", "PAYS:CI, PAYS:SN, PAYS:BF, PAYS:ML (ou « Côte d'Ivoire »)"],
        ["Secteur", "SECT:…", "SECT:FIN, SECT:TEL, SECT:CB, SECT:CD, SECT:ENE, SECT:IND, SECT:SPU"],
        ["Thème", "THEME:…", "THEME:TAUX_BCEAO, THEME:CACAO, THEME:PETROLE, THEME:ELECTIONS, THEME:SECURITE"],
        ["Marché", "MARCHE", "ensemble de la cote"],
    ])
    + "<p class=\"hint\">Plusieurs cibles : séparer par des virgules. Une cible non reconnue est conservée à part "
      "(« cibles non reconnues ») et n'agit sur aucun titre : elle n'est jamais remplacée en silence.</p></details>"
)


# ---------------------------------------------------------------------------
# Notes en vigueur : ligne datée, filtres actifs, tableaux
# ---------------------------------------------------------------------------

NOTES_HEAD = ["Publiée", "Séance", "Cible", "Type", "Titre", "Score", "Confiance", "Décroissance", "Source", "Filtre"]
#: Lignes affichées au plus dans le tableau des notes automatiques en vigueur.
NOTES_AUTO_MAX = 80


def _src_cell(n: Mapping[str, Any]) -> Safe:
    """Source d'une note avec son lien (http ou https seulement)."""
    src = esc(n.get("source") or "n.d.")
    url = str(n.get("url") or "").strip()
    return Safe(f"{src} · {ext_link(url, 'document')}") if url else src


def _in_force_rows(tab: Any, limit: int | None = None) -> list[list[Any]]:
    if not isinstance(tab, pd.DataFrame) or not len(tab):
        return []
    rows = []
    for n in (tab if limit is None else tab.head(limit)).to_dict(orient="records"):
        avis = ""
        if isinstance(n.get("stance"), str) and n["stance"]:
            c = n.get("conviction")
            avis = f" ({n['stance']}" + (f" {int(c)}/5" if c is not None and c == c else "") + ")"
        rows.append([fr_date(n.get("published_at")), fr_date(n.get("first_tradable_session")),
                     ", ".join(map(str, n.get("targets") or [])) or "—", (n.get("event_type") or "n.d.") + avis,
                     link(f"/notes/fiche?id={q(n.get('note_id'))}", str(n.get("title") or "(sans titre)")[:90]),
                     fr_num(n.get("score"), 2, True), fr_num(n.get("confidence"), 2), fr_num(n.get("decay"), 2),
                     _src_cell(n), ", ".join(map(str, n.get("filters") or [])) or "—"])
    return rows


def _filters_table(status: Mapping[str, Any]) -> Safe:
    rows = []
    for f in status.get("filters") or []:
        rem = f.get("seances_restantes")
        fin = str(f.get("duree") or "durée ouverte") + (f" (encore {int(rem)} séance(s))" if rem is not None else "")
        note = Safe(f"{link('/notes/fiche?id=' + q(f.get('note_id')), str(f.get('note_titre') or '(sans titre)')[:90])}"
                    f"<br><span class=\"muted\">{esc(fr_date(f.get('note_date')))} · "
                    f"{_src_cell({'source': f.get('note_source'), 'url': f.get('note_url')})}</span>")
        rows.append([f.get("symbole"), Safe(f"<strong>{esc(f.get('code'))}</strong> {esc(f.get('libelle') or '')}"),
                     "achats bloqués" if f.get("bloque_achats") else "surveillance",
                     f"depuis le {fr_date(f.get('depuis'))}, {fin}", note, f.get("lever") or ""])
    return table(["Titre", "Filtre", "Effet", "Durée", "Note", "Pour lever le filtre"], rows,
                 empty="Aucun filtre de risque actif issu des notes.")


def notes_status_block(status: Mapping[str, Any] | None, *, detail: bool = False, title: str | None = None) -> Safe:
    """Ligne datée des notes (toujours), message sur les scores et filtres actifs (``detail``)."""
    if not status:
        return box("info", "Notes de l'analyste : aucun journal (ou panel introuvable) ; aucune note n'entre dans "
                           "les calculs.", title)
    parts: list[Any] = [box("fact", status.get("line") or "", title or "Notes dans la décision :")]
    if status.get("erreur"):
        return join(parts)
    if status.get("scores_message"):
        parts.append(Safe(f'<p class="muted">{esc(status["scores_message"])}</p>'))
    if detail or status.get("filters"):
        parts.append(Safe("<h3>Filtres de risque actifs issus des notes</h3>"))
        parts.append(_filters_table(status))
    return join(parts)


def notes_in_force_section(status: Mapping[str, Any] | None, indices: Any = None) -> Safe:
    """Section « Notes en vigueur » de la page Notes : synthèse, filtres, notes manuelles et
    automatiques, 10 plus positives et 10 plus négatives, composante « notes » de chaque indice."""
    if not status or status.get("erreur"):
        return Safe('<section class="card"><h2>Notes en vigueur</h2>') + notes_status_block(status) + Safe("</section>")
    from brvm_alpha.notes.signals import top_notes

    tab = status.get("table")
    has = isinstance(tab, pd.DataFrame) and len(tab) > 0
    manual = tab[tab["manual"]] if has else None
    auto = tab[~tab["manual"]] if has else None
    pos, neg = top_notes(tab, 10) if has else (None, None)
    parts: list[Any] = [Safe('<section class="card"><h2>Notes en vigueur à la séance d\'application</h2>'),
                        notes_status_block(status, detail=True),
                        Safe('<p class="muted">Une note est en vigueur si elle est connue, non archivée, négociable au '
                             "plus tard à la séance d'application et agit encore (décroissance exp(−Δ/10 séances), "
                             "filtre de risque ou avis de l'analyste dans son horizon). Âge compté depuis la "
                             "publication pour une note automatique, depuis la saisie pour une note manuelle.</p>"),
                        Safe(f"<h3>Notes manuelles en vigueur ({0 if manual is None else len(manual)})</h3>"),
                        table(NOTES_HEAD, _in_force_rows(manual), empty="Aucune note manuelle en vigueur."),
                        Safe(f"<h3>Notes automatiques en vigueur ({0 if auto is None else len(auto)})</h3>")]
    arows = _in_force_rows(auto, NOTES_AUTO_MAX)
    if arows:
        more = (f" (les {NOTES_AUTO_MAX} plus récentes sur {len(auto)})" if auto is not None and len(auto) > NOTES_AUTO_MAX
                else "")
        parts.append(Safe(f"<details><summary>Afficher le tableau{esc(more)}</summary>") + table(NOTES_HEAD, arows)
                     + Safe("</details>"))
    else:
        parts.append(Safe('<p class="muted">Aucune note automatique en vigueur.</p>'))
    parts += [Safe("<h3>Les 10 notes les plus positives</h3>"),
              table(NOTES_HEAD, _in_force_rows(pos), empty="Aucune note de score positif en vigueur."),
              Safe("<h3>Les 10 notes les plus négatives</h3>"),
              table(NOTES_HEAD, _in_force_rows(neg), empty="Aucune note de score négatif en vigueur.")]
    if isinstance(indices, pd.DataFrame) and len(indices):
        rows = []
        for code, r in indices.iterrows():
            det = list(_val(r.get("notes_detail")) or [])[:4]
            if det:
                who: Any = Safe("<ul>" + "".join(
                    f"<li>{link('/notes/fiche?id=' + q(e.get('note_id')), str(e.get('title') or '(sans titre)')[:80])} "
                    f"({esc(', '.join(map(str, (e.get('targets') or [])[:3])))}) : score "
                    f"{esc(fr_num(e.get('note_score'), 2, True))}, part {esc(fr_num(e.get('part'), 3, True))}</li>"
                    for e in det) + "</ul>")
            else:
                n = _val(r.get("notes_n"))
                who = "notes en vigueur de score nul : composante exclue" if n is not None and int(n) > 0 else \
                    "aucune note en vigueur : composante exclue"
            rows.append([link(f"/indices/dossier?code={q(code)}", r.get("label")), notes_z_text(r),
                         fr_num(r.get("notes_score"), 3, True) if _val(r.get("notes_score")) is not None else "—",
                         fr_num(r.get("composite_ex_notes"), 2, True) + " → " + fr_num(r.get("composite"), 2, True),
                         who])
        parts += [Safe("<h3>Composante « notes » de chaque indice</h3>"
                       '<p class="muted">z notes = score des notes / 0,5, borné à ±3, poids 0,15 du score composite ; '
                       "« sans → avec » : score composite sans puis avec cette composante. Aide à la décision, pas "
                       "un signal validé.</p>"),
                  table(["Indice", "z notes", "Score des notes", "Composite sans → avec",
                         "Notes qui portent la composante"], rows)]
    parts.append(Safe("</section>"))
    return join(parts)


def notes_z_text(r: Any) -> str:
    """Composante « notes » d'un indice : z, ou la raison de son absence (jamais « n.d. » seul)."""
    z = _val(r.get("z_notes"))
    if z is not None:
        return fr_num(z, 2, True)
    n = _val(r.get("notes_n"))
    return "score nul" if n is not None and int(n) > 0 else "aucune note"


# ---------------------------------------------------------------------------
# Tableau de bord
# ---------------------------------------------------------------------------


def page_dashboard(ctx: PageContext, *, last_session: Any, validation: Mapping[str, Any] | None,
                   choice: Mapping[str, Any] | None, reports: Sequence[Mapping[str, Any]],
                   job: Mapping[str, Any] | None, recent_notes: Sequence[Mapping[str, Any]],
                   default_capital: float = 10_000_000, flash: Any = None,
                   notes_status: Mapping[str, Any] | None = None) -> str:
    facts = [("Données au", fr_date(last_session) if last_session is not None else "panel introuvable")]
    if validation:
        facts.append(("Test S1", f"{validation.get('etat')} ; statut de A : {validation.get('statut_A') or 'n.d.'}"))
        if validation.get("principal"):
            facts.append(("Variante principale (§3.4)", f"{validation.get('principal')} "
                                                       f"({validation.get('statut_principal') or 'n.d.'})"))
    if choice:
        facts.append(("Variante de l'ordre de bataille", f"{choice.get('variante')} — {choice.get('motif') or ''}"))
    state = dl(facts)
    if reports:
        latest = reports[0]
        others = [[link(f"/rapport/voir?nom={q(r['nom'])}", r["nom"]), r["modifie"], r["taille"]] for r in reports[:8]]
        rep = Safe(
            f"<p>Dernier rapport : <strong>{esc(latest['nom'])}</strong> (modifié le {esc(latest['modifie'])}) — "
            f"{link('/rapport/voir?nom=' + q(latest['nom']), 'ouvrir en plein écran')}</p>"
            f'<iframe class="report" title="Dernier rapport" sandbox="allow-scripts allow-popups '
            f'allow-popups-to-escape-sandbox" loading="lazy" src="/rapport/voir?nom={esc(q(latest["nom"]))}"></iframe>'
            + "<details><summary>Rapports disponibles</summary>" + table(["Fichier", "Modifié le", "Taille"], others)
            + "</details>")
    else:
        rep = box("info", "Aucun rapport généré pour l'instant : utiliser « Régénérer le rapport ».")
    busy = bool(job and job.get("statut") in ("en cours", "en attente"))
    form = Safe(
        '<form method="post" action="/rapport/regenerer" class="grid">' + csrf_field(ctx.token)
        + f'<div><label for="capital">Capital (FCFA)</label><input type="text" id="capital" name="capital" '
          f'inputmode="numeric" value="{esc(fr_num(default_capital, 0))}" required>'
          '<div class="hint">exemples : 10 000 000, 10M, 1,5Md</div></div>'
        + f'<div><button type="submit"{" disabled" if busy else ""}>Régénérer le rapport</button>'
          '<div class="hint">Une seule opération longue à la fois ; le rapport est écrit dans reports/.</div></div>'
          "</form>")
    notes_rows = [[fr_date(n.get("published_at")), link(f"/notes/fiche?id={q(n.get('note_id'))}", n.get("title") or "(sans titre)"),
                   ", ".join(n.get("all_targets") or []) or "—", fr_num(n.get("score"), 2, True)] for n in recent_notes]
    body = join([
        Safe('<section class="card"><h2>État (faits)</h2>'), state,
        box("hypothesis", "Tant que rien n'est PROMU, toute recommandation est à titre d'étude : suivi réel (paper "
                          "trading) requis avant tout engagement d'argent réel."),
        Safe("</section>"),
        Safe('<section class="card"><h2>Notes prises en compte (mode direct)</h2>'),
        notes_status_block(notes_status),
        Safe('<p class="muted">Date des cours : dernier BOC du panel ; instant de connaissance des notes : maintenant. '
             "Les notes saisies ou collectées jusqu'à cet instant comptent dans l'évaluation des indices, l'ordre de "
             f"bataille et le rapport régénéré. {link('/notes', 'Détail des notes en vigueur')}</p></section>"),
        Safe('<section class="card"><h2>Rapport</h2>'), rep, form, Safe("</section>"),
        job_panel(job, result_link=link("/", "Afficher le nouveau rapport")),
        Safe('<section class="card"><h2>Dernières notes</h2>'),
        table(["Publiée", "Titre", "Cibles", "Score"], notes_rows, empty="Aucune note dans le journal."),
        Safe(f'<p>{link("/notes", "Toutes les notes et saisie")}</p></section>'),
    ])
    return layout(ctx, "Tableau de bord", body, active="accueil", flash=flash)


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------

STANCE_CHOICES = (("", "— (aucun avis)"), ("haussier", "haussier"), ("baissier", "baissier"), ("neutre", "neutre"))


def _select(name: str, options: Iterable[tuple[str, str]], selected: Any = "", id_: str | None = None) -> Safe:
    sel = str(selected or "")
    opts = "".join(f'<option value="{esc(v)}"' + (" selected" if str(v) == sel else "") + f">{esc(lab)}</option>"
                   for v, lab in options)
    return Safe(f'<select name="{esc(name)}" id="{esc(id_ or name)}">{opts}</select>')


def note_form(ctx: PageContext, values: Mapping[str, Any] | None = None, error: Any = None) -> Safe:
    """Formulaire de saisie manuelle d'une note (POST /notes/ajouter)."""
    from brvm_alpha.notes.model import EVENT_TYPES

    v = {k: ("" if x is None else x) for k, x in dict(values or {}).items()}
    ev_opts = [("", "détecté automatiquement")] + [(k, f"{k} — {lab}") for k, lab in EVENT_TYPES.items()]
    conv = [("", "—")] + [(str(i), str(i)) for i in range(1, 6)]
    err = box("error", error, "Saisie refusée :") if error else Safe("")
    return Safe(
        '<form method="post" action="/notes/ajouter" class="grid" autocomplete="off">' + csrf_field(ctx.token) + err
        + '<div class="wide"><label for="cibles">Cible(s)</label>'
          f'<input type="text" id="cibles" name="cibles" list="codes-cibles" value="{esc(v.get("cibles", ""))}" '
          'placeholder="SNTS, IDX:BRVM-30, PAYS:CI">'
          '<div class="row"><input type="text" id="cible-choix" list="codes-cibles" aria-label="Choisir une cible" '
          'placeholder="chercher un code ou un nom">'
          '<button type="button" class="secondary" data-add-target data-src="cible-choix" data-dst="cibles">Ajouter'
          '</button></div><div class="hint">Codes : SYMBOLE, IDX:…, PAYS:…, SECT:…, THEME:…, MARCHE (aide ci-dessous) ; '
          "vide : cibles détectées dans le texte.</div></div>"
        + f'<div class="wide"><label for="titre">Titre</label><input type="text" id="titre" name="titre" maxlength="500" '
          f'value="{esc(v.get("titre", ""))}"></div>'
        + f'<div class="wide"><label for="texte">Texte</label><textarea id="texte" name="texte">{esc(v.get("texte", ""))}'
          "</textarea></div>"
        + f'<div><label for="avis">Avis</label>{_select("avis", STANCE_CHOICES, v.get("avis"))}</div>'
        + f'<div><label for="conviction">Conviction (1-5)</label>{_select("conviction", conv, v.get("conviction"))}</div>'
        + f'<div><label for="horizon">Horizon (séances)</label><input type="number" id="horizon" name="horizon" min="1" '
          f'max="2000" value="{esc(v.get("horizon", "20"))}"></div>'
        + f'<div><label for="type">Type d\'événement</label>{_select("type", ev_opts, v.get("type"))}</div>'
        + f'<div><label for="source">Source</label><input type="text" id="source" name="source" maxlength="120" '
          f'value="{esc(v.get("source", ""))}" placeholder="rapport annuel, presse, BOC…"></div>'
        + f'<div><label for="url">Adresse (URL)</label><input type="url" id="url" name="url" maxlength="2000" '
          f'value="{esc(v.get("url", ""))}" placeholder="https://…"></div>'
        + f'<div><label for="publie_le">Date de publication</label><input type="date" id="publie_le" name="publie_le" '
          f'value="{esc(v.get("publie_le", ""))}"><div class="hint">vide : maintenant</div></div>'
        + f'<div><label for="heure">Heure (UTC, facultative)</label><input type="time" id="heure" name="heure" '
          f'value="{esc(v.get("heure", ""))}"><div class="hint">sans heure : réputée publiée en fin de journée '
          "(agit à la séance suivante)</div></div>"
        + f'<div><label for="etiquettes">Étiquettes</label><input type="text" id="etiquettes" name="etiquettes" '
          f'value="{esc(v.get("etiquettes", ""))}" placeholder="mots séparés par des virgules"></div>'
        + '<div class="wide"><button type="submit">Enregistrer et analyser la note</button></div></form>'
        + TARGET_HELP
    )


def _note_row(n: Mapping[str, Any]) -> list[Any]:
    return [fr_date(n.get("published_at")),
            link(f"/notes/fiche?id={q(n.get('note_id'))}", n.get("title") or "(sans titre)"),
            ", ".join(n.get("all_targets") or []) or "—",
            stance_badge(n.get("stance")) if n.get("stance") else "—",
            fr_num(n.get("score"), 2, True), fr_num(n.get("materiality"), 2), fr_num(n.get("confidence"), 2),
            n.get("source") or "", n.get("status") or ""]


def page_notes(ctx: PageContext, *, notes: Sequence[Mapping[str, Any]], filters: Mapping[str, Any],
               options: Sequence[tuple[str, str]], form_values: Mapping[str, Any] | None = None,
               form_error: Any = None, store_errors: Sequence[str] = (), total: int = 0, flash: Any = None,
               notes_status: Mapping[str, Any] | None = None, indices: Any = None) -> str:
    f = {k: ("" if x is None else x) for k, x in dict(filters).items()}
    statut = [("actives", "actives"), ("archivees", "archivées"), ("toutes", "toutes")]
    filt = Safe(
        '<form method="get" action="/notes" class="grid">'
        f'<div><label for="f-cible">Cible</label><input type="text" id="f-cible" name="cible" list="codes-cibles" '
        f'value="{esc(f.get("cible", ""))}"></div>'
        f'<div><label for="f-depuis">Publiées depuis</label><input type="date" id="f-depuis" name="depuis" '
        f'value="{esc(f.get("depuis", ""))}"></div>'
        f'<div><label for="f-texte">Texte contenu</label><input type="search" id="f-texte" name="texte" '
        f'value="{esc(f.get("texte", ""))}"></div>'
        f'<div><label for="f-statut">Statut</label>{_select("statut", statut, f.get("statut") or "actives", "f-statut")}</div>'
        '<div><button type="submit">Filtrer</button></div></form>')
    warn = box("warn", f"{len(store_errors)} ligne(s) illisible(s) du journal ignorée(s) : {store_errors[0]}") \
        if store_errors else Safe("")
    lst = table(["Publiée", "Titre", "Cibles", "Avis", "Score", "Matérialité", "Confiance", "Source", "Statut"],
                [_note_row(n) for n in notes], empty="Aucune note ne correspond aux filtres.")
    body = join([
        datalist("codes-cibles", options),
        Safe('<section class="card"><h2>Nouvelle note (saisie manuelle)</h2>'),
        Safe('<p class="muted">La note est analysée (type d\'événement, ton, chiffres, matérialité, filtres de risque, '
             "lecture) puis enregistrée dans le journal append-only. Les notes ne pilotent jamais seules le "
             "portefeuille : leur poids est borné (inclinaison ±0,5 écart-type, veto).</p>"),
        note_form(ctx, form_values, form_error), Safe("</section>"),
        notes_in_force_section(notes_status, indices),
        Safe('<section class="card"><h2>Journal des notes</h2>'), filt, warn,
        Safe(f'<p class="muted">{len(notes)} note(s) affichée(s) sur {int(total)} dans le journal.</p>'), lst,
        Safe("</section>"),
    ])
    return layout(ctx, "Notes de l'analyste", body, active="notes", flash=flash)


def page_note(ctx: PageContext, *, note: Mapping[str, Any], versions: Sequence[Mapping[str, Any]],
              risk_labels: Mapping[str, str], event_labels: Mapping[str, str], flash: Any = None) -> str:
    n = note
    an = n.get("analysis") or {}
    meta = [
        ("Identifiant", Safe(f"<code>{esc(n.get('note_id'))}</code>")),
        ("Version", f"{n.get('version')} ({n.get('status')})"),
        ("Publiée le", f"{fr_date(n.get('published_at'))}"
                       + (" (date seule : réputée connue en fin de journée)" if n.get("published_precision") == "date"
                          else f" à {pd.Timestamp(n['published_at']):%H:%M} UTC" if n.get("published_at") else "")),
        ("Négociable à partir du", fr_date(n.get("first_tradable_session"))),
        ("Auteur", n.get("author")), ("Source", n.get("source")),
        ("Adresse", ext_link(n.get("url")) if n.get("url") else "—"),
        ("Cibles saisies", ", ".join(n.get("targets") or []) or "—"),
    ]
    if n.get("targets_unknown"):
        meta.append(("Cibles non reconnues", Safe(f'<span class="badge down">{esc(", ".join(n["targets_unknown"]))}'
                                                  "</span> conservées, sans effet sur un titre")))
    if n.get("stance"):
        meta.append(("Avis de l'analyste", join([stance_badge(n.get("stance")),
                                                 f" conviction {n.get('conviction') or '—'}/5, horizon "
                                                 f"{n.get('horizon_days')} séances"])))
    if n.get("tags"):
        meta.append(("Étiquettes", ", ".join(n["tags"])))
    analysis: list[Any] = []
    if an:
        analysis.append(dl([
            ("Type d'événement", f"{an.get('event_type')} — {event_labels.get(str(an.get('event_type')), '')}"),
            ("Score [−1 ; 1]", fr_num(an.get("score"), 2, True)),
            ("Ton lexical", fr_num(an.get("tone"), 2, True)),
            ("Chiffres (s_num)", fr_num(an.get("s_num"), 2, True)),
            ("Matérialité [0 ; 1]", fr_num(an.get("materiality"), 2)),
            ("Confiance [0 ; 1]", fr_num(an.get("confidence"), 2)),
            ("Cibles retenues", ", ".join(an.get("targets") or []) or "—"),
            ("Cible principale", an.get("primary_target") or "—"),
        ]))
        if an.get("reading"):
            analysis.append(box("estimate", an["reading"], "Lecture :"))
        flags = an.get("risk_flags") or []
        if flags:
            analysis.append(table(["Filtre", "Effet"], [[f, risk_labels.get(f, "")] for f in flags]))
        ext = an.get("extracted") or {}
        if ext:
            analysis.append(Safe("<h3>Chiffres et dates extraits (faits lus dans le texte)</h3>"))
            analysis.append(table(["Champ", "Valeur"], [[k, _fmt_value(v)] for k, v in ext.items()
                                                        if _val(v) is not None and v != ""]))
        terms = an.get("matched_terms") or []
        if terms:
            analysis.append(Safe("<details><summary>Termes reconnus</summary>"))
            analysis.append(table(["Terme", "Polarité", "Catégorie"],
                                  [[t.get("term") or t.get("text") or "", t.get("polarity", ""), t.get("category", "")]
                                   for t in terms[:60] if isinstance(t, Mapping)]))
            analysis.append(Safe("</details>"))
        for w in an.get("warnings") or []:
            analysis.append(box("warn", w))
        if an.get("contradiction"):
            analysis.append(box("warn", "L'avis de l'analyste contredit le ton ou les chiffres du texte."))
    else:
        analysis.append(box("info", "Aucune analyse enregistrée pour cette version."))
    vrows = [[v.get("version"), v.get("recorded_at") or "—", v.get("op") or "", v.get("status") or "",
              v.get("title") or "", fr_num(v.get("score"), 2, True)] for v in versions]
    archive = Safe("")
    if n.get("status") == "active":
        archive = Safe(
            '<form method="post" action="/notes/archiver" class="grid" data-confirm="Archiver cette note ? '
            "Une nouvelle version « archivée » est écrite ; l'historique est conservé.\">" + csrf_field(ctx.token)
            + f'<input type="hidden" name="id" value="{esc(n.get("note_id"))}">'
            + '<div><label for="motif">Motif (facultatif)</label><input type="text" id="motif" name="motif" maxlength="200">'
              '</div><div><button type="submit" class="danger">Archiver</button></div></form>')
    body = join([
        Safe('<section class="card"><h2>Note</h2>'), dl(meta),
        Safe(f'<h3>Texte</h3><pre class="texte">{esc(n.get("text") or "(aucun texte)")}</pre></section>'),
        Safe('<section class="card"><h2>Analyse</h2><p class="muted">Lecture factuelle et chiffrée, avec son degré '
             "de confiance : pas une prévision.</p>"), *analysis, Safe("</section>"),
        Safe('<section class="card"><h2>Versions</h2>'),
        table(["Version", "Écrite le (UTC)", "Opération", "Statut", "Titre", "Score"], vrows), Safe("</section>"),
        Safe('<section class="card"><h2>Archivage</h2>'),
        archive if n.get("status") == "active" else box("info", "Note archivée."), Safe("</section>"),
        Safe(f'<p>{link("/notes", "Retour aux notes")}</p>'),
    ])
    return layout(ctx, n.get("title") or "Note", body, active="notes", flash=flash)


# ---------------------------------------------------------------------------
# Recherche
# ---------------------------------------------------------------------------


def page_research(ctx: PageContext, *, job: Mapping[str, Any] | None, blocked: Mapping[str, Any],
                  defaults: Mapping[str, Any] | None = None, error: Any = None, new_notes: Sequence[Mapping[str, Any]] = (),
                  flash: Any = None, options: Sequence[tuple[str, str]] = (),
                  documents: Sequence[str] | None = None) -> str:
    d = {"mode": "hors_ligne", "max_requetes": 30, "cibles": "", "depuis": "", "lire_documents": "",
         "max_documents": 20} | dict(defaults or {})
    busy = bool(job and job.get("statut") in ("en cours", "en attente"))
    blk = Safe("")
    if blocked:
        blk = box("error", "; ".join(f"{h} bloqué depuis le {e.get('ts')} (HTTP {e.get('status')})" for h, e in blocked.items())
                  + ". Aucune requête ne lui sera envoyée ; le blocage ne se lève qu'explicitement, avec l'accord du site.",
                  "Site bloqué :")
    checked_off = " checked" if d.get("mode") != "en_ligne" else ""
    checked_on = " checked" if d.get("mode") == "en_ligne" else ""
    form = Safe(
        '<form method="post" action="/recherche/lancer" class="grid" data-confirm="Lancer la recherche ? En ligne, '
        'des requêtes réelles sont envoyées à www.brvm.org (au moins 10 s entre deux).">' + csrf_field(ctx.token)
        + (box("error", error, "Saisie refusée :") if error else "")
        + '<div class="wide"><fieldset><legend>Mode</legend>'
          f'<label class="inline"><input type="radio" name="mode" value="hors_ligne"{checked_off}> hors ligne : cache '
          "disque et BOC locaux, aucune requête réseau</label><br>"
          f'<label class="inline"><input type="radio" name="mode" value="en_ligne"{checked_on}> en ligne : listes '
          "publiques de www.brvm.org (poliment)</label></fieldset></div>"
        + f'<div><label for="max_requetes">Quota de requêtes</label><input type="number" id="max_requetes" '
          f'name="max_requetes" min="1" max="150" value="{esc(d.get("max_requetes"))}">'
          '<div class="hint">au plus 150 ; durée maximale ≈ quota × 10 s</div></div>'
        + f'<div><label for="r-cibles">Périmètre (facultatif)</label><input type="text" id="r-cibles" name="cibles" '
          f'list="codes-cibles" value="{esc(d.get("cibles"))}" placeholder="vide : tout le marché"></div>'
        + f'<div><label for="r-depuis">Remonter jusqu\'au (facultatif)</label><input type="date" id="r-depuis" '
          f'name="depuis" value="{esc(d.get("depuis"))}"></div>'
        + '<div class="wide"><label class="inline"><input type="checkbox" name="lire_documents" value="oui"'
          f'{" checked" if d.get("lire_documents") else ""}> lire le contenu des documents récents (PDF de '
          "www.brvm.org : alertes sur résultats, résultats, rapports d'activité, notations, communiqués)</label>"
          '<div class="hint">Après la collecte : une requête par document en ligne (au moins 10 s entre deux), ou le '
          "cache seul hors ligne ; chaque note lue reçoit une nouvelle version analysée avec le texte ; un PDF "
          "scanné (image) est signalé « à lire à la main ».</div></div>"
        + f'<div><label for="max_documents">Nombre maximal de documents</label><input type="number" '
          f'id="max_documents" name="max_documents" min="1" max="60" value="{esc(d.get("max_documents"))}">'
          '<div class="hint">au plus 60 ; les plus utiles et les plus récents d\'abord</div></div>'
        + '<div class="wide"><label class="inline"><input type="checkbox" name="confirmer" value="oui" required> '
          "Je confirme le lancement et j'ai pris connaissance des règles de politesse.</label></div>"
        + f'<div><button type="submit"{" disabled" if busy else ""}>Lancer la recherche</button></div></form>')
    rows = [_note_row(n) for n in new_notes]
    body = join([
        datalist("codes-cibles", options),
        Safe('<section class="card"><h2>Règles de politesse</h2>'), box("info", RULES_POLITENESS),
        Safe("<ul><li>Seules des pages publiques sont lues ; jamais d'API non documentée ni de contournement d'une "
             "protection anti-robot.</li><li>Un refus (HTTP 403 ou 429) inscrit le site comme bloqué d'une session à "
             "l'autre.</li><li>Les notes collectées sont datées (publication, première séance négociable) : aucune "
             "information n'agit avant d'être publique.</li></ul>"),
        blk, Safe("</section>"),
        Safe('<section class="card"><h2>Lancer une recherche</h2>'), form, Safe("</section>"),
        job_panel(job, result_link=link("/notes", "Voir les notes")),
        (Safe('<section class="card"><h2>Lecture du contenu des documents (dernière recherche)</h2><pre class="log">')
         + esc("\n".join(map(str, documents))) + Safe("</pre></section>")) if documents else Safe(""),
        Safe('<section class="card"><h2>Nouvelles notes de la dernière recherche</h2>') if rows else Safe(""),
        table(["Publiée", "Titre", "Cibles", "Avis", "Score", "Matérialité", "Confiance", "Source", "Statut"], rows)
        if rows else Safe(""), Safe("</section>") if rows else Safe(""),
    ])
    return layout(ctx, "Recherche automatique", body, active="recherche", flash=flash)


# ---------------------------------------------------------------------------
# Indices
# ---------------------------------------------------------------------------


def page_indices(ctx: PageContext, *, evaluation: pd.DataFrame | None, asof: Any, notes_included: bool,
                 error: Any = None, notes_status: Mapping[str, Any] | None = None) -> str:
    form = Safe('<form method="get" action="/indices" class="grid"><div><label for="i-date">Date d\'évaluation</label>'
                f'<input type="date" id="i-date" name="date" value="{esc("" if asof is None else pd.Timestamp(asof).strftime("%Y-%m-%d"))}">'
                '<div class="hint">à partir du 17/11/2022 (S0) ; vide : dernière séance</div></div>'
                '<div><button type="submit">Évaluer</button></div></form>')
    parts: list[Any] = [Safe('<section class="card">'), form]
    if error:
        parts.append(box("error", error))
    if evaluation is not None and len(evaluation):
        when = fr_date(evaluation["date"].max()) if "date" in evaluation else fr_date(asof)
        parts.append(Safe(f"<p>Évaluation au <strong>{esc(when)}</strong> ; composante « notes » : "
                          f"{'incluse' if notes_included else 'aucune note'}.</p>"))
        if notes_included:
            parts.append(notes_status_block(notes_status))
        parts.append(box("hypothesis", "Aide à la décision, pas un signal validé : poids et seuils sont des choix de "
                                       "conception non validés hors échantillon (score composite de z-scores bornés)."))
        rows = []
        for code, r in evaluation.iterrows():
            rows.append([link(f"/indices/dossier?code={q(code)}" + (f"&date={q(pd.Timestamp(asof).strftime('%Y-%m-%d'))}"
                                                                     if asof is not None else ""), r.get("label")),
                         fr_num(r.get("level"), 2), fr_pct(r.get("ret_1m")), fr_pct(r.get("ret_3m")),
                         fr_pct(r.get("ret_12m")), fr_pct(r.get("ytd")), fr_num(r.get("per"), 1),
                         fr_num(r.get("yield_pct"), 2), stance_badge(r.get("stance")), fr_num(r.get("confidence"), 2),
                         fr_num(r.get("composite"), 2, True), notes_z_text(r)])
        parts.append(table(["Indice", "Niveau", "1 mois", "3 mois", "12 mois", "Depuis 31/12", "PER", "Rdt %",
                            "Position", "Confiance", "Score", "Notes (z)"], rows))
        parts.append(Safe("</section>"))
        for code, r in evaluation.iterrows():
            reasons = list(_val(r.get("reasons")) or [])
            parts.append(Safe(f'<section class="card"><h2>{esc(r.get("label"))} <span class="muted">({esc(code)})</span> '
                              f'{stance_badge(r.get("stance"))}</h2>'))
            parts.append(Safe("<ul>" + "".join(f"<li>{esc(s)}</li>" for s in reasons) + "</ul>"))
            parts.append(Safe(f'<p>{link("/indices/dossier?code=" + q(code), "Dossier détaillé")}</p></section>'))
    else:
        parts.append(Safe("</section>"))
    return layout(ctx, "Évaluation des indices", join(parts), active="indices")


def page_dossier(ctx: PageContext, *, dossier: Mapping[str, Any] | None, code: str, error: Any = None) -> str:
    if dossier is None:
        return layout(ctx, f"Dossier {code}", box("error", error or "dossier indisponible")
                      + Safe(f'<p>{link("/indices", "Retour aux indices")}</p>'), active="indices")
    d = dossier
    ev = d.get("evaluation") or {}
    head = dl([("Position", stance_badge(ev.get("stance"))), ("Confiance", fr_num(ev.get("confidence"), 2)),
               ("Score composite", fr_num(ev.get("composite"), 2, True)), ("Date", fr_date(ev.get("date"))),
               ("Niveau", fr_num(ev.get("level"), 2)), ("Composition", d.get("composition") or "—")])
    nline = Safe(f'<p class="muted">{esc(d.get("notes_line"))}.</p>') if d.get("notes_line") else Safe("")
    parts: list[Any] = [Safe('<section class="card"><h2>Synthèse</h2>'), head, nline,
                        Safe("<h3>Raisons</h3><ul>" + "".join(f"<li>{esc(s)}</li>" for s in d.get("reasons") or [])
                             + "</ul></section>")]
    notes = d.get("recent_notes") or []
    nrows = [[fr_date(n.get("first_tradable_session")), link(f"/notes/fiche?id={q(n.get('note_id'))}", n.get("title") or "—"),
              ", ".join(n.get("targets") or []), n.get("event_type") or "", n.get("author") or "",
              fr_num(n.get("score"), 2, True), fr_num(n.get("decay"), 2), ", ".join(n.get("risk_flags") or [])]
             for n in notes]
    parts += [Safe('<section class="card"><h2>Notes qui l\'influencent</h2><p class="muted">Notes sur l\'indice, ses '
                   "alias (MARCHE, secteur) et ses constituants, depuis 90 jours ; décroissance exp(−Δ/10 séances).</p>"),
              table(["Négociable dès", "Titre", "Cibles", "Type", "Auteur", "Score", "Décroissance", "Filtres"], nrows,
                    empty="Aucune note récente."), Safe("</section>")]
    cons = d.get("constituents")
    if isinstance(cons, pd.DataFrame) and len(cons):
        crow = []
        for sym, r in cons.iterrows():
            crow.append([link(f"/expliquer?symbole={q(sym)}", sym), r.get("name") or "", r.get("country") or "",
                         fr_pct(r.get("weight"), 2, False), fr_num(r.get("close"), 0), fr_pct(r.get("ret_3m")),
                         fr_pct(r.get("ret_12m")), fr_pct(r.get("contribution_12m"), 2), fr_num(r.get("per"), 1),
                         fr_num(r.get("net_yield_pct"), 2), fr_num(r.get("note_score"), 2, True),
                         ", ".join(_val(r.get("flags")) or []) + (" veto" if bool(r.get("veto")) else "")])
        parts += [Safe(f'<section class="card"><h2>Constituants ({len(cons)})</h2>'),
                  table(["Titre", "Nom", "Pays", "Poids", "Cours", "3 mois", "12 mois", "Contrib. 12 m", "PER", "Rdt %",
                         "Notes", "Filtres"], crow), Safe("</section>")]
    cmm = d.get("change_my_mind") or []
    if cmm:
        parts += [Safe('<section class="card"><h2>Ce qui ferait changer d\'avis</h2><ul>'
                       + "".join(f"<li>{esc(s)}</li>" for s in cmm) + "</ul></section>")]
    cal = d.get("calendar")
    if isinstance(cal, pd.DataFrame) and len(cal):
        cols = list(cal.columns)
        rows = [[fr_date(v) if isinstance(v, pd.Timestamp) else ("" if _val(v) is None else v) for v in r]
                for r in cal.head(40).itertuples(index=False)]
        parts += [Safe('<section class="card"><h2>Calendrier (120 prochains jours, estimations)</h2>'),
                  table(cols, rows), Safe("</section>")]
    parts.append(Safe(f'<p>{link("/indices", "Retour aux indices")}</p>'))
    return layout(ctx, f"Dossier {d.get('label') or code}", join(parts), active="indices")


# ---------------------------------------------------------------------------
# Portefeuille
# ---------------------------------------------------------------------------


VARIANT_CHOICES = (("", "automatique (d'après le test S1)"),) + tuple(
    (v, v) for v in ("A", "B", "C", "D", "E", "F", "G", "H", "I", "REF"))


def page_portfolio(ctx: PageContext, *, values: Mapping[str, Any] | None, job: Mapping[str, Any] | None,
                   fragment: str | None, error: Any = None, job_id: str | None = None,
                   notes_status: Mapping[str, Any] | None = None) -> str:
    v = {"capital": "10 000 000", "portefeuille": "", "cash": "", "variante": "", "date": "", "tirages": "5000"} \
        | {k: ("" if x is None else x) for k, x in dict(values or {}).items()}
    busy = bool(job and job.get("statut") in ("en cours", "en attente"))
    tir = [("1000", "1 000 (rapide)"), ("2000", "2 000"), ("5000", "5 000 (défaut)")]
    form = Safe(
        '<form method="post" action="/portefeuille/calculer" class="grid">' + csrf_field(ctx.token)
        + (box("error", error, "Saisie refusée :") if error else "")
        + f'<div><label for="p-capital">Capital total (FCFA)</label><input type="text" id="p-capital" name="capital" '
          f'inputmode="numeric" value="{esc(v["capital"])}" required><div class="hint">titres détenus compris ; '
          "exemples : 10 000 000, 10M, 1,5Md</div></div>"
        + f'<div><label for="p-cash">Liquidités (facultatif)</label><input type="text" id="p-cash" name="cash" '
          f'inputmode="numeric" value="{esc(v["cash"])}"><div class="hint">défaut : capital − titres détenus</div></div>'
        + f'<div><label for="p-variante">Variante</label>{_select("variante", VARIANT_CHOICES, v["variante"], "p-variante")}</div>'
        + f'<div><label for="p-date">Date de décision</label><input type="date" id="p-date" name="date" '
          f'value="{esc(v["date"])}"><div class="hint">vide : dernière séance (mode direct : les notes connues '
          "maintenant comptent, appliquées à la séance suivante) ; date passée : notes en règle stricte à cette "
          'date ; S1 refusé</div></div>'
        + f'<div><label for="p-tirages">Tirages du bootstrap</label>{_select("tirages", tir, v["tirages"], "p-tirages")}</div>'
        + f'<div class="wide"><label for="p-portefeuille">Portefeuille actuel (une ligne « symbole,titres »)</label>'
          f'<textarea id="p-portefeuille" name="portefeuille" placeholder="SNTS,120&#10;ORAC,15">{esc(v["portefeuille"])}'
          "</textarea></div>"
        + f'<div class="wide"><button type="submit"{" disabled" if busy else ""}>Calculer l\'ordre de bataille</button>'
          '<div class="hint">Calcul long (bootstrap, stress) : exécuté dans un fil de travail, une opération à la fois.'
          "</div></div></form>")
    links = Safe("")
    if fragment and job_id:
        links = Safe(f'<p>Exports : {link("/portefeuille/resultat?travail=" + q(job_id) + "&format=md", "Markdown")} · '
                     f'{link("/portefeuille/resultat?travail=" + q(job_id) + "&format=json", "JSON")}</p>')
    body = join([
        Safe('<section class="card"><h2>Paramètres</h2>'), form, Safe("</section>"),
        Safe('<section class="card"><h2>Notes prises en compte à la dernière séance (mode direct)</h2>'),
        notes_status_block(notes_status),
        Safe('<p class="muted">Un achat bloqué par une note est écrit en clair dans l\'ordre de bataille (règle, '
             "note, fin du blocage) ; pour le lever, archiver la note depuis sa fiche. "
             f'{link("/notes", "Notes en vigueur")}</p></section>'),
        job_panel(job),
        Safe('<section class="card"><h2>Ordre de bataille</h2>') if fragment else Safe(""),
        links, Safe(fragment) if fragment else Safe(""), Safe("</section>") if fragment else Safe(""),
    ])
    return layout(ctx, "Portefeuille — ordre de bataille", body, active="portefeuille")


# ---------------------------------------------------------------------------
# Expliquer
# ---------------------------------------------------------------------------


def page_explain(ctx: PageContext, *, values: Mapping[str, Any], explanation: Mapping[str, Any] | None,
                 options: Sequence[tuple[str, str]], error: Any = None) -> str:
    v = {k: ("" if x is None else x) for k, x in dict(values).items()}
    form = Safe(
        datalist("codes-symboles", options)
        + '<form method="get" action="/expliquer" class="grid">'
          f'<div><label for="e-symbole">Symbole</label><input type="text" id="e-symbole" name="symbole" '
          f'list="codes-symboles" value="{esc(v.get("symbole", ""))}" required placeholder="SNTS"></div>'
          f'<div><label for="e-date">Date</label><input type="date" id="e-date" name="date" value="{esc(v.get("date", ""))}">'
          '<div class="hint">vide : dernière séance ; S1 refusé</div></div>'
          f'<div><label for="e-variante">Variante</label>{_select("variante", VARIANT_CHOICES, v.get("variante"), "e-variante")}</div>'
          '<div><button type="submit">Expliquer</button></div></form>')
    parts: list[Any] = [Safe('<section class="card">'), form]
    if error:
        parts.append(box("error", error))
    parts.append(Safe("</section>"))
    e = explanation
    if e:
        ch = e.get("choix_variante") or {}
        parts.append(Safe(f'<section class="card"><h2>{esc(e.get("symbol"))} au {esc(fr_date(e.get("asof")))}, variante '
                          f'{esc(e.get("variant"))}</h2>'))
        if ch.get("motif"):
            parts.append(Safe(f'<p class="muted">Variante choisie : {esc(ch.get("motif"))}</p>'))
        if e.get("text"):
            parts.append(Safe("<pre>" + esc(e.get("text")) + "</pre>"))
        sc = e.get("score") or {}
        parts.append(dl([("Éligible", "oui" if e.get("eligible") else "non"),
                         ("Score final", fr_num(sc.get("final"), 3, True)),
                         ("Rang", f"{sc.get('rank') or 'n.d.'} / {sc.get('n_ranked') or 'n.d.'}"),
                         ("Poids cible", fr_pct(e.get("weight"), 2, False)),
                         ("Motif de construction", e.get("construction_reason") or "—")]))
        blocks = e.get("blocks") or {}
        parts.append(Safe("<h3>Blocs de signaux</h3>"))
        parts.append(table(["Bloc", "Valeur brute", "z", "Poids a priori", "Poids effectif", "Contribution", ""],
                           [[lab, fr_num(b.get("raw"), 4), fr_num(b.get("z"), 2, True), fr_num(b.get("weight_prior"), 2),
                             fr_num(b.get("weight"), 2), fr_num(b.get("contribution"), 3, True),
                             "recherche (poids nul)" if b.get("research_only") else ""] for lab, b in blocks.items()]))
        rf = e.get("risk_flags") or {}
        parts.append(Safe("<h3>Filtres de risque</h3>"))
        parts.append(dl([("Actifs", ", ".join(rf.get("active") or []) or "aucun"),
                         ("Achats bloqués", "oui" if rf.get("block_buys") else "non"),
                         ("Règle pays", rf.get("country_rule") or "—")]))
        for dtl in rf.get("detail") or []:
            parts.append(box("warn", dtl if not isinstance(dtl, Mapping) else ", ".join(f"{k} : {x}" for k, x in dtl.items())))
        caps = e.get("caps") or {}
        if caps:
            parts.append(Safe("<h3>Plafonds</h3>"))
            parts.append(dl([(k, fr_pct(x, 2, False) if not isinstance(x, (dict, list)) else str(x))
                             for k, x in caps.items() if k != "line_detail"]))
        nt = e.get("notes") or {}
        parts.append(Safe("<h3>Notes de l'analyste</h3>"))
        parts.append(dl([("Module", "disponible" if nt.get("available") else "indisponible"),
                         ("Message", nt.get("message") or "—"), ("Inclinaison", fr_num(nt.get("tilt"), 3, True)),
                         ("Veto", ", ".join(map(str, nt.get("veto") or [])) or "aucun"),
                         ("Usage", nt.get("used_in_score") or "—")]))
        val = e.get("valuation") or {}
        if val:
            parts.append(Safe("<details><summary>Valorisation (information, n'entre pas dans le score)</summary>"))
            parts.append(dl([(k, fr_num(x, 4) if isinstance(x, (int, float)) and not isinstance(x, bool) else str(x))
                             for k, x in val.items()]))
            parts.append(Safe("</details>"))
        for msg in e.get("messages") or []:
            parts.append(box("info", msg))
        parts.append(Safe("</section>"))
    return layout(ctx, "Expliquer une ligne", join(parts), active="expliquer")


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def page_validation(ctx: PageContext, *, s1: Mapping[str, Any] | None, s1_md: str | None,
                    attempts_md: str | None, s0_md: str | None) -> str:
    parts: list[Any] = [Safe('<section class="card"><h2>Test unique S1 (faits lus, jamais recalculés)</h2>')]
    if s1:
        parts.append(dl([("État", s1.get("etat")), ("Statut de A", s1.get("statut_A") or "n.d."),
                         ("Variante principale (§3.4)", f"{s1.get('principal') or 'n.d.'} "
                                                       f"({s1.get('statut_principal') or 'n.d.'})"),
                         ("Dossier", s1.get("dossier") or "—")]))
        for w in s1.get("avertissements") or []:
            parts.append(box("warn", w))
    parts.append(box("info", "Échantillon vierge S1 (2017-01-02 → 2022-11-16) : test exécuté une seule fois, "
                             "paramètres figés avant l'exécution (additif v1.1). Cette page lit les résultats ; elle ne "
                             "relance aucun calcul."))
    parts.append(Safe("</section>"))
    if s1_md:
        parts += [Safe('<section class="card"><h2>Résultats S1 (resultats.md)</h2>'), md_to_html(s1_md), Safe("</section>")]
    else:
        parts.append(box("warn", "resultats.md du test S1 introuvable."))
    if attempts_md:
        parts += [Safe('<section class="card"><details><summary>Tentatives (tentatives.md)</summary>'),
                  md_to_html(attempts_md), Safe("</details></section>")]
    if s0_md:
        parts += [Safe('<section class="card"><details><summary>Diagnostic S0 — échantillon contaminé, aucune valeur de '
                       "preuve</summary>"), md_to_html(s0_md), Safe("</details></section>")]
    return layout(ctx, "Validation", join(parts), active="validation")


__all__ = [
    "Safe", "esc", "md_to_html", "layout", "error_page", "PageContext", "job_panel", "target_options",
    "page_dashboard", "page_notes", "page_note", "page_research", "page_indices", "page_dossier",
    "page_portfolio", "page_explain", "page_validation", "note_form",
]
