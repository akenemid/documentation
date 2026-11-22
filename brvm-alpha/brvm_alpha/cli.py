"""Ligne de commande de BRVM Alpha : ``python -m brvm_alpha <commande>`` (aide : ``-h``).

Données
  ``update [--from AAAA-MM-JJ]`` : télécharge **poliment** les BOC manquants depuis www.brvm.org
  (robots.txt respecté, au moins 10 s entre deux requêtes, arrêt définitif au premier HTTP 403/429)
  puis reconstruit le panel ; ``panel`` : reconstruit ``data/panel`` depuis les BOC locaux ;
  ``live`` : cours du jour (page publique, instantané sans historique).

Notes de l'analyste (journal ``data/notes/notes.jsonl``)
  ``notes add|list|show|archive|export|research|analyze`` : saisie manuelle analysée, liste filtrée,
  fiche (analyse, lecture, versions), archivage, export Markdown, recherche polie sur brvm.org (ou
  hors ligne, cache seul), analyse d'un texte sans l'enregistrer.

Analyse et décision
  ``indices [--date]`` et ``indices dossier CODE`` : évaluation des indices (position, confiance,
  raisons) ; ``universe`` : univers éligible U1-U10 ; ``explain SYMBOLE`` : décomposition du score ;
  ``recommend --capital K`` : ordre de bataille complet (Markdown, JSON ou HTML) ; ``report --capital
  K`` : rapport HTML autonome ; ``serve`` : interface web locale (127.0.0.1 uniquement par défaut).

Validation
  ``backtest`` (toute période qui recoupe l'échantillon vierge S1, 2017-01-02 → 2022-11-16, est
  **refusée** sans ``--validation-s1``) ; ``validate --sample S1|S0`` (test unique verrouillé ou
  diagnostic S0 contaminé).

Aucune commande n'évalue un signal sur S1 : ``indices``, ``explain``, ``recommend`` et ``report``
refusent une date de décision antérieure au 17/11/2022 (code 2). Toutes les sorties chiffrées sont
des estimations sous hypothèses (coûts, exécution) : **Performance passée ≠ garantie. Aucun gain
n'est garanti.**

Codes de sortie : 0 succès ; 1 échec (données absentes, arrêt de la collecte) ; 2 refus ou erreur de
saisie.
"""

from __future__ import annotations

import argparse
import datetime as dt
import ipaddress
import json
import math
import re
import sys
import warnings
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import pandas as pd

BANNER = "Performance passée ≠ garantie. Aucun gain n'est garanti."
S1 = ("2017-01-02", "2022-11-16")
S1_END = pd.Timestamp(S1[1])
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PANEL_DIR = ROOT / "data" / "panel"
DEFAULT_BOC_DIR = ROOT / "data" / "boc_text"
DEFAULT_REPORTS_DIR = ROOT / "reports"
DEFAULT_CAPITAL = 10_000_000.0
#: Hôtes de bouclage acceptés par ``serve`` sans option explicite.
LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "::1")
DEFAULT_PORT = 8765

RULES_POLITENESS = (
    "Règles de politesse : seul www.brvm.org est interrogé (Sika Finance, Richbourse et la presse sont "
    "désactivés) ; robots.txt lu et respecté ; au moins 10 s entre deux requêtes (Crawl-delay), d'une session "
    "à l'autre ; arrêt définitif au premier HTTP 403 ou 429, sans contournement ; quota de requêtes ; aucune "
    "API non documentée ; journal dans data/notes/fetch_log.jsonl."
)


# ---------------------------------------------------------------------------
# Analyseur d'arguments en français
# ---------------------------------------------------------------------------

_ERRORS_FR: tuple[tuple[str, str], ...] = (
    (r"^the following arguments are required: (.*)$", r"arguments obligatoires manquants : \1"),
    (r"^unrecognized arguments: (.*)$", r"arguments non reconnus : \1"),
    (r"^argument (.*?): invalid choice: (.*?) \(choose from (.*)\)$", r"argument \1 : choix invalide : \2 (choix possibles : \3)"),
    (r"^argument (.*?): invalid (\w+) value: (.*)$", r"argument \1 : valeur invalide : \3"),
    (r"^argument (.*?): expected one argument$", r"argument \1 : une valeur est attendue"),
    (r"^argument (.*?): not allowed with argument (.*)$", r"argument \1 : incompatible avec \2"),
    (r"^one of the arguments (.*) is required$", r"l'un des arguments \1 est obligatoire"),
    (r"^ambiguous option: (.*?) could match (.*)$", r"option ambiguë : \1 (possibilités : \2)"),
    (r"^argument (.*?): (.*)$", r"argument \1 : \2"),
)


def _fr_error(message: str) -> str:
    for pat, rep in _ERRORS_FR:
        if re.match(pat, message):
            return re.sub(pat, rep, message)
    return message


class _FrHelpFormatter(argparse.RawDescriptionHelpFormatter):
    def add_usage(self, usage, actions, groups, prefix=None):  # noqa: D401 - surcharge argparse
        return super().add_usage(usage, actions, groups, prefix="utilisation : " if prefix is None else prefix)


class FrArgumentParser(argparse.ArgumentParser):
    """``ArgumentParser`` aux libellés et messages d'erreur en français."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("formatter_class", _FrHelpFormatter)
        kwargs["add_help"] = False
        super().__init__(*args, **kwargs)
        self._positionals.title = "arguments"
        self._optionals.title = "options"
        self.add_argument("-h", "--help", action="help", default=argparse.SUPPRESS,
                          help="affiche cette aide et quitte")

    def error(self, message: str):  # type: ignore[override]
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog} : erreur : {_fr_error(message)}\n")


# ---------------------------------------------------------------------------
# Saisies (partagées avec l'interface web)
# ---------------------------------------------------------------------------


def parse_date(value: Any) -> pd.Timestamp:
    """Date « AAAA-MM-JJ » ou « JJ/MM/AAAA » (``ValueError`` sinon)."""
    s = str(value or "").strip()
    m = re.fullmatch(r"(\d{1,2})[/.](\d{1,2})[/.](\d{4})", s)
    try:
        if m:
            return pd.Timestamp(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
            return pd.Timestamp(s)
    except ValueError as exc:
        raise ValueError(f"date invalide : {s!r}") from exc
    raise ValueError(f"date invalide : {s!r} (attendu AAAA-MM-JJ ou JJ/MM/AAAA)")


def parse_capital(value: Any) -> float:
    """Montant en FCFA : « 10000000 », « 10 000 000 », « 10M », « 1,5 Md », « 250k » (``ValueError`` sinon)."""
    s = str(value or "").strip().lower().replace("\u202f", "").replace("\xa0", "").replace(" ", "").replace("_", "")
    s = s.replace("fcfa", "").replace("xof", "")
    m = re.fullmatch(r"(\d+(?:[.,]\d+)?)(k|m|md|mds|mrd|g)?", s)
    if not m:
        raise ValueError(f"montant invalide : {value!r} (exemples : 10000000, 10M, 1,5Md)")
    x = float(m.group(1).replace(",", "."))
    mult = {None: 1.0, "k": 1e3, "m": 1e6, "md": 1e9, "mds": 1e9, "mrd": 1e9, "g": 1e9}[m.group(2)]
    x *= mult
    if not math.isfinite(x) or x <= 0:
        raise ValueError("le montant doit être strictement positif")
    if x > 1e13:
        raise ValueError("montant hors de portée (plus de 10 000 milliards de FCFA)")
    return x


_HOLDINGS_HEADER = frozenset({"symbole", "symboles", "symbol", "titre", "code", "valeur", "ticker"})


def parse_holdings(text: str) -> dict[str, int]:
    """Portefeuille « symbole,titres » (une ligne par titre ; séparateur ``,`` ``;`` ou tabulation).

    Les lignes vides et les commentaires (``#``) sont ignorés ; une première ligne d'en-tête
    (« symbole,titres ») est acceptée. Lève ``ValueError`` (message en français) sinon.
    """
    out: dict[str, int] = {}
    seen_data = False
    for i, line in enumerate(str(text or "").splitlines(), start=1):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        parts = [p.strip() for p in re.split(r"[;,\t]", s) if p.strip()]
        if len(parts) < 2:
            raise ValueError(f"ligne {i} : « symbole,titres » attendu, lu {s[:40]!r}")
        sym = parts[0].upper()
        qty_s = re.sub(r"[\s\u202f\xa0]", "", parts[1])
        if not seen_data and parts[0].strip().lower() in _HOLDINGS_HEADER:
            seen_data = True
            continue  # en-tête « symbole,titres »
        seen_data = True
        if not re.fullmatch(r"[A-Z0-9]{2,8}", sym):
            raise ValueError(f"ligne {i} : symbole invalide {parts[0][:20]!r}")
        if not re.fullmatch(r"\d+", qty_s):
            raise ValueError(f"ligne {i} : nombre de titres invalide {parts[1][:20]!r} (entier positif attendu)")
        out[sym] = out.get(sym, 0) + int(qty_s)
    return {k: v for k, v in out.items() if v > 0}


def read_holdings(path: str | Path) -> dict[str, int]:
    """Lit un fichier CSV « symbole,titres » (voir :func:`parse_holdings`)."""
    return parse_holdings(Path(path).read_text(encoding="utf-8-sig"))


def _date_arg(value: str) -> pd.Timestamp:
    try:
        return parse_date(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _capital_arg(value: str) -> float:
    try:
        return parse_capital(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _conviction_arg(value: str) -> int:
    try:
        c = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("conviction : entier de 1 à 5") from exc
    if not 1 <= c <= 5:
        raise argparse.ArgumentTypeError("conviction : entier de 1 à 5")
    return c


def _positive_int(value: str) -> int:
    try:
        n = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"entier attendu : {value!r}") from exc
    if n <= 0:
        raise argparse.ArgumentTypeError("entier strictement positif attendu")
    return n


def in_s1(date: Any) -> bool:
    """La date de décision tombe-t-elle dans l'échantillon vierge S1 (ou avant) ?"""
    return pd.Timestamp(date).normalize() <= S1_END


def s1_refusal(date: Any, what: str) -> str:
    """Message de refus d'une évaluation sur S1."""
    return (f"refusé : {what} au {pd.Timestamp(date):%d/%m/%Y} évaluerait un signal sur l'échantillon vierge S1 "
            f"({S1[0]} → {S1[1]}), réservé au test unique déjà exécuté (reports/validation_S1). "
            "Choisir une date à partir du 17/11/2022 (S0).")


def _overlaps_s1(start: str | None, end: str | None) -> bool:
    a = pd.Timestamp(start) if start else pd.Timestamp.min
    b = pd.Timestamp(end) if end else pd.Timestamp.max
    return bool(a <= pd.Timestamp(S1[1]) and b >= pd.Timestamp(S1[0]))


def is_loopback(host: str) -> bool:
    """``True`` pour 127.0.0.1, localhost, ::1 (et toute adresse 127.x)."""
    h = str(host or "").strip().strip("[]").lower()
    if h == "localhost":
        return True
    try:
        return ipaddress.ip_address(h).is_loopback
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Mise en forme
# ---------------------------------------------------------------------------


def _ok(x: Any) -> bool:
    try:
        return x is not None and math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def fr_num(x: Any, decimals: int = 2, signed: bool = False) -> str:
    """Nombre au format français (espace fine des milliers, virgule, signe « − »)."""
    if not _ok(x):
        return "n.d."
    v = float(x)
    s = f"{abs(v):,.{decimals}f}".replace(",", " ").replace(".", ",")
    sign = "−" if v < 0 and s.strip("0, ") else ("+" if signed and v > 0 else "")
    return sign + s


def fr_pct(x: Any, decimals: int = 1, signed: bool = True) -> str:
    """Fraction décimale en pourcentage (0,123 → « +12,3 % »)."""
    return "n.d." if not _ok(x) else fr_num(100 * float(x), decimals, signed) + " %"


def fr_date(x: Any) -> str:
    try:
        ts = pd.Timestamp(x)
    except (TypeError, ValueError):
        return "n.d."
    return "n.d." if pd.isna(ts) else ts.strftime("%d/%m/%Y")


def to_jsonable(obj: Any) -> Any:
    """Conversion récursive en types JSON (``DataFrame`` → liste d'enregistrements)."""
    from brvm_alpha.notes.model import jsonable

    if isinstance(obj, pd.DataFrame):
        df = obj.reset_index() if not isinstance(obj.index, pd.RangeIndex) else obj
        return [to_jsonable(r) for r in df.to_dict(orient="records")]
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(v) for v in obj]
    return jsonable(obj)


def _print_json(obj: Any) -> None:
    print(json.dumps(to_jsonable(obj), ensure_ascii=False, indent=1))


def _table(rows: list[list[str]], headers: list[str]) -> str:
    widths = [max(len(str(h)), *(len(str(r[i])) for r in rows)) if rows else len(str(h)) for i, h in enumerate(headers)]
    line = "  ".join(str(h).ljust(w) for h, w in zip(headers, widths))
    out = [line, "  ".join("-" * w for w in widths)]
    out += ["  ".join(str(c).ljust(w) for c, w in zip(r, widths)) for r in rows]
    return "\n".join(out)


def _say(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


# ---------------------------------------------------------------------------
# Données du dépôt
# ---------------------------------------------------------------------------


def last_session(panel_dir: str | Path | None = None) -> pd.Timestamp | None:
    """Dernière séance disponible du panel (``sessions.parquet``, à défaut ``equities.parquet``)."""
    pdir = Path(panel_dir) if panel_dir else DEFAULT_PANEL_DIR
    try:
        if (pdir / "sessions.parquet").exists():
            s = pd.read_parquet(pdir / "sessions.parquet", columns=["date", "available"])
            s = s[s["available"].astype(bool)]
            if len(s):
                return pd.Timestamp(s["date"].max()).normalize()
        if (pdir / "equities.parquet").exists():
            d = pd.read_parquet(pdir / "equities.parquet", columns=["date"])["date"]
            if len(d):
                return pd.Timestamp(d.max()).normalize()
    except Exception:  # panel illisible : la commande le signalera
        return None
    return None


def _decision_date(args_date: Any, panel_dir: Any) -> pd.Timestamp:
    if args_date is not None:
        return pd.Timestamp(args_date).normalize()
    t = last_session(panel_dir)
    return t if t is not None else pd.Timestamp(dt.date.today())


def last_local_boc(boc_dir: str | Path) -> dt.date | None:
    """Date du BOC local le plus récent (``boc_AAAAMMJJ.txt.gz`` ou marqueur ``.missing``)."""
    best: dt.date | None = None
    p = Path(boc_dir)
    if not p.exists():
        return None
    for f in p.iterdir():
        m = re.match(r"^boc_(\d{8})\.(txt\.gz|txt|missing)$", f.name)
        if m:
            d = dt.datetime.strptime(m.group(1), "%Y%m%d").date()
            best = d if best is None or d > best else best
    return best


def _notes_store(root: Any = None) -> Any:
    from brvm_alpha.notes.store import NoteStore

    return NoteStore(root) if root else NoteStore()


def resolve_note_id(store: Any, prefix: str) -> str:
    """Identifiant complet à partir d'un préfixe unique (``KeyError`` sinon)."""
    p = str(prefix or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{4,64}", p):
        raise KeyError(f"identifiant invalide : {prefix!r} (au moins 4 caractères hexadécimaux)")
    hits = [i for i in store.ids() if str(i).lower().startswith(p)]
    if not hits:
        raise KeyError(f"aucune note d'identifiant {prefix!r}")
    if len(hits) > 1:
        raise KeyError(f"identifiant ambigu {prefix!r} : {len(hits)} notes ; donner plus de caractères")
    return hits[0]


def brvm_fetcher(max_requests: int = 200, delay_s: float = 10.0, cache_dir: Any = None) -> Callable[[str], tuple[int, bytes]]:
    """Client poli de ``notes.research`` pour ``boc_download`` (délai et blocage partagés, sans cache disque).

    L'appelable renvoie ``(statut, contenu)`` et lève ``boc_download.DownloadStopped`` au premier
    403/429, sur interdiction du robots.txt, quota atteint ou serveur indisponible.
    """
    from brvm_alpha.data import boc_download
    from brvm_alpha.notes import research as rs

    class _NoCacheSession(rs.PoliteSession):
        """Les PDF (~1 Mo) ne sont pas conservés dans le cache HTTP."""

        def cache_get(self, url: str):  # noqa: D401
            return None

        def cache_put(self, *args: Any, **kwargs: Any) -> None:
            return None

    cdir = Path(cache_dir) if cache_dir is not None else rs.DEFAULT_NOTES_DIR / "cache"
    sess = _NoCacheSession(delay_s=max(float(delay_s), boc_download.MIN_DELAY_S), max_requests=max_requests,
                           cache_dir=cdir, log_path=cdir.parent / "fetch_log.jsonl", max_retries=2,
                           user_agent=boc_download.USER_AGENT)

    def fetch(url: str) -> tuple[int, bytes]:
        try:
            res = sess.get(url)
        except (rs.AccessBlocked, rs.RobotsDisallowed, rs.QuotaExceeded, rs.ServerUnavailable,
                rs.SourceDisabled) as exc:
            raise boc_download.DownloadStopped(str(exc)) from exc
        except rs.ResearchError:  # trop de redirections : pas de bulletin à cette adresse
            return 0, b""
        return int(res.status), bytes(res.content or b"")

    fetch.session = sess  # type: ignore[attr-defined]
    return fetch


# ---------------------------------------------------------------------------
# Analyseur
# ---------------------------------------------------------------------------

_DESCRIPTION = (
    "BRVM Alpha : données des BOC, notes de l'analyste, évaluation des indices, ordre de bataille et "
    "validation, en ligne de commande.\n\n" + BANNER + "\nAide d'une commande : python -m brvm_alpha COMMANDE -h"
)


def _add_notes_root(p: argparse.ArgumentParser) -> None:
    p.add_argument("--racine", default=None, metavar="DOSSIER",
                   help="dossier du journal des notes (défaut : data/notes)")


def build_parser() -> argparse.ArgumentParser:
    """Analyseur des arguments (en français)."""
    parser = FrArgumentParser(prog="python -m brvm_alpha", description=_DESCRIPTION)
    sub = parser.add_subparsers(dest="command", required=True, title="commandes", metavar="COMMANDE")

    # -- données ---------------------------------------------------------------
    up = sub.add_parser("update", help="télécharge les BOC manquants (brvm.org, poliment) puis reconstruit le panel",
                        description="Télécharge les Bulletins Officiels de la Cote manquants depuis www.brvm.org : "
                                    "robots.txt respecté, au moins 10 s entre deux requêtes, arrêt définitif au "
                                    "premier HTTP 403 ou 429, puis reconstruit data/panel.")
    up.add_argument("--from", dest="start", type=_date_arg, default=None, metavar="AAAA-MM-JJ",
                    help="premier jour cherché (défaut : lendemain du dernier BOC local)")
    up.add_argument("--jusqu-au", dest="end", type=_date_arg, default=None, metavar="AAAA-MM-JJ",
                    help="dernier jour cherché (défaut : aujourd'hui)")
    up.add_argument("--delai", type=float, default=10.0, metavar="S",
                    help="secondes entre deux requêtes (défaut et minimum : 10)")
    up.add_argument("--max-requetes", type=_positive_int, default=200, metavar="N",
                    help="quota de requêtes de la session (défaut : 200)")
    up.add_argument("--simulation", action="store_true", help="liste les jours à chercher, sans aucune requête")
    up.add_argument("--sans-panel", action="store_true", help="ne reconstruit pas le panel")
    up.add_argument("--boc-dir", default=None, metavar="DOSSIER", help="BOC texte (défaut : data/boc_text)")
    up.add_argument("--panel-dir", default=None, metavar="DOSSIER", help="panel (défaut : data/panel)")

    pa = sub.add_parser("panel", help="reconstruit data/panel depuis les BOC locaux",
                        description="Reconstruit le panel parquet (actions, indices, marché, carnet, dividendes, "
                                    "opérations sur titres, séances) à partir des BOC texte locaux (cache incrémental).")
    pa.add_argument("--boc-dir", default=None, metavar="DOSSIER", help="BOC texte (défaut : data/boc_text)")
    pa.add_argument("--panel-dir", default=None, metavar="DOSSIER", help="sortie (défaut : data/panel)")
    pa.add_argument("--force", action="store_true", help="ignore le cache et réanalyse tous les BOC")
    pa.add_argument("--workers", type=_positive_int, default=None, metavar="N", help="processus d'analyse")

    li = sub.add_parser("live", help="cours du jour (page publique brvm.org, instantané)",
                        description="Cours du jour depuis la page publique https://www.brvm.org/fr/cours-actions/0 "
                                    "(une requête, robots.txt respecté) ; instantané sans historique : les cours "
                                    "du BOC du soir font foi.")
    li.add_argument("--format", choices=("texte", "json"), default="texte", help="format de sortie")
    li.add_argument("--symbole", action="append", default=None, metavar="SYMBOLE", help="filtre (répétable)")
    li.add_argument("--hors-ligne", action="store_true", help="relit la dernière page en cache, sans requête")

    # -- notes -------------------------------------------------------------------
    no = sub.add_parser("notes", help="notes de l'analyste : saisie, liste, fiche, archivage, export, recherche, analyse",
                        description="Journal des notes de l'analyste (append-only, data/notes/notes.jsonl). "
                                    "Codes de cibles : SYMBOLE (SNTS), IDX:BRVM-C, IDX:BRVM-30, IDX:PRESTIGE, "
                                    "IDX:PRINCIPAL, IDX:BRVM-C-TR, IDX:SECT:FIN, PAYS:CI, SECT:TEL, THEME:CACAO, MARCHE.")
    nsub = no.add_subparsers(dest="notes_cmd", required=True, title="actions", metavar="ACTION")

    na = nsub.add_parser("add", help="ajoute une note (analysée et enregistrée)",
                         description="Ajoute une note de l'analyste ; elle est analysée (type, ton, chiffres, "
                                     "matérialité, filtres de risque, lecture) puis enregistrée.")
    _add_notes_root(na)
    na.add_argument("--cible", action="append", default=None, metavar="CODE",
                    help="cible (répétable ou séparée par des virgules) : SNTS, IDX:BRVM-30, PAYS:CI, SECT:FIN, "
                         "THEME:CACAO, MARCHE ; noms acceptés (« Sonatel », « BRVM 30 »)")
    na.add_argument("--titre", default="", help="titre de la note")
    g = na.add_mutually_exclusive_group()
    g.add_argument("--texte", default=None, help="texte de la note")
    g.add_argument("--fichier", default=None, metavar="CHEMIN", help="fichier texte (UTF-8) contenant la note")
    na.add_argument("--avis", choices=("haussier", "baissier", "neutre"), default=None, help="avis de l'analyste")
    na.add_argument("--conviction", type=_conviction_arg, default=None, metavar="1-5", help="conviction de 1 à 5")
    na.add_argument("--horizon", type=_positive_int, default=None, metavar="SÉANCES",
                    help="horizon en séances (défaut : 20)")
    na.add_argument("--source", default=None, help="origine de l'information (texte libre, ex. « rapport annuel »)")
    na.add_argument("--url", default=None, help="adresse de la source (http ou https)")
    na.add_argument("--publie-le", dest="publie_le", default=None, metavar="DATE",
                    help="date (ou date et heure UTC) de publication : AAAA-MM-JJ, « AAAA-MM-JJ HH:MM », JJ/MM/AAAA")
    na.add_argument("--type", dest="event_type", default=None, metavar="TYPE",
                    help="type d'événement (DIV_NOTICE, RES_ANNUAL, PROFIT_WARNING, MACRO…) ; défaut : détecté")
    na.add_argument("--etiquette", action="append", default=None, metavar="MOT", help="étiquette (répétable)")
    na.add_argument("--format", choices=("texte", "json"), default="texte",
                    help="format de sortie (défaut : texte)")

    nl = nsub.add_parser("list", help="liste les notes (filtres : cible, date)",
                         description="Dernières versions des notes, de la plus récente à la plus ancienne.")
    _add_notes_root(nl)
    nl.add_argument("--cible", default=None, metavar="CODE", help="cible (code ou nom)")
    nl.add_argument("--depuis", type=_date_arg, default=None, metavar="AAAA-MM-JJ", help="publiées depuis")
    nl.add_argument("--jusqu-au", dest="jusqu_au", type=_date_arg, default=None, metavar="AAAA-MM-JJ",
                    help="publiées jusqu'au")
    nl.add_argument("--statut", choices=("actives", "archivees", "toutes"), default="actives",
                    help="statut (défaut : actives)")
    nl.add_argument("--limite", type=_positive_int, default=50, metavar="N", help="nombre maximal (défaut : 50)")
    nl.add_argument("--format", choices=("texte", "json"), default="texte",
                    help="format de sortie (défaut : texte)")

    ns = nsub.add_parser("show", help="fiche d'une note (analyse, lecture, versions)")
    _add_notes_root(ns)
    ns.add_argument("id", metavar="ID", help="identifiant (préfixe unique d'au moins 4 caractères)")
    ns.add_argument("--format", choices=("texte", "json"), default="texte",
                    help="format de sortie (défaut : texte)")

    nr = nsub.add_parser("archive", help="archive une note (nouvelle version, historique conservé)")
    _add_notes_root(nr)
    nr.add_argument("id", metavar="ID", help="identifiant (préfixe unique)")
    nr.add_argument("--motif", default=None, help="motif de l'archivage")

    ne = nsub.add_parser("export", help="exporte les notes en Markdown")
    _add_notes_root(ne)
    ne.add_argument("--sortie", default=None, metavar="CHEMIN",
                    help="fichier Markdown (défaut : reports/notes_AAAAMMJJ.md ; « - » : sortie standard)")
    ne.add_argument("--cible", default=None, metavar="CODE", help="cible (code ou nom)")
    ne.add_argument("--statut", choices=("actives", "archivees", "toutes"), default="actives",
                    help="notes exportées (défaut : actives)")

    nq = nsub.add_parser("research", help="recherche polie sur brvm.org (ou hors ligne) et BOC locaux",
                         description="Recherche automatique : listes publiques de www.brvm.org (annonces, OST, avis, "
                                     "dividendes), rapports des émetteurs et événements des BOC locaux ; notes "
                                     "analysées ajoutées au journal. " + RULES_POLITENESS)
    _add_notes_root(nq)
    nq.add_argument("--cibles", action="append", default=None, metavar="CODES",
                    help="périmètre (codes séparés par des virgules ; défaut : tout le marché)")
    nq.add_argument("--hors-ligne", action="store_true", help="aucune requête réseau : cache disque et BOC locaux")
    nq.add_argument("--max-requetes", type=_positive_int, default=150, metavar="N", help="quota (défaut : 150)")
    nq.add_argument("--depuis", type=_date_arg, default=None, metavar="AAAA-MM-JJ", help="remonter les listes jusqu'à")
    nq.add_argument("--sans-boc", action="store_true", help="n'analyse pas les BOC locaux")
    nq.add_argument("--simulation", action="store_true", help="n'enregistre rien (dry run)")

    nz = nsub.add_parser("analyze", help="analyse un texte sans l'enregistrer",
                         description="Analyse un texte (type d'événement, ton, chiffres, cibles, matérialité, "
                                     "filtres de risque, lecture) sans l'ajouter au journal.")
    gz = nz.add_mutually_exclusive_group(required=True)
    gz.add_argument("--texte", default=None, help="texte à analyser")
    gz.add_argument("--fichier", default=None, metavar="CHEMIN", help="fichier texte (UTF-8)")
    nz.add_argument("--titre", default="", help="titre")
    nz.add_argument("--cible", action="append", default=None, metavar="CODE", help="cible imposée (répétable)")
    nz.add_argument("--format", choices=("texte", "json"), default="texte",
                    help="format de sortie (défaut : texte)")

    # -- indices -------------------------------------------------------------------
    ix = sub.add_parser("indices", help="évaluation des indices (position, confiance, raisons) ; « indices dossier CODE »",
                        description="Évaluation des indices BRVM à une date (S0 seulement) : niveau, rendements, "
                                    "tendance, valorisation, largeur, régime, notes ; position SURPONDÉRER / NEUTRE / "
                                    "SOUS-PONDÉRER, confiance et raisons chiffrées. Aide à la décision, pas un signal "
                                    "validé. Sous-commande : « indices dossier CODE ».")
    ix.add_argument("--date", type=_date_arg, default=None, metavar="AAAA-MM-JJ",
                    help="date d'évaluation (défaut : dernière séance du panel)")
    ix.add_argument("--format", choices=("texte", "json"), default="texte",
                    help="format de sortie (défaut : texte)")
    ix.add_argument("--detail", action="store_true", help="affiche toutes les raisons")
    ix.add_argument("--sans-notes", action="store_true", help="exclut la composante « notes »")
    _add_notes_root(ix)
    ix.add_argument("--panel-dir", default=None, metavar="DOSSIER", help="panel (défaut : data/panel)")
    ixs = ix.add_subparsers(dest="indices_cmd", required=False, title="sous-commande (facultative)",
                           metavar="[dossier CODE]")
    ixd = ixs.add_parser("dossier", help="dossier détaillé d'un indice (constituants, contributions, notes)")
    ixd.add_argument("code", metavar="CODE", help="indice : IDX:BRVM-C, IDX:BRVM-30, IDX:PRESTIGE, IDX:SECT:FIN…")
    # Options répétées après « dossier » : SUPPRESS conserve la valeur donnée avant la sous-commande.
    ixd.add_argument("--date", type=_date_arg, default=argparse.SUPPRESS, metavar="AAAA-MM-JJ",
                     help="date d'évaluation (défaut : dernière séance du panel)")
    ixd.add_argument("--format", choices=("texte", "json"), default=argparse.SUPPRESS,
                     help="format de sortie (défaut : texte)")
    ixd.add_argument("--sans-notes", action="store_true", default=argparse.SUPPRESS,
                     help="exclut les notes de l'analyste")
    ixd.add_argument("--racine", default=argparse.SUPPRESS, metavar="DOSSIER",
                     help="dossier du journal des notes (défaut : data/notes)")
    ixd.add_argument("--panel-dir", default=argparse.SUPPRESS, metavar="DOSSIER", help="panel (défaut : data/panel)")

    # -- univers, explication, backtest, validation -----------------------------------
    u = sub.add_parser("universe", help="univers éligible U1-U10 à une date (contrôle de forme)")
    u.add_argument("--date", type=_date_arg, default=None, metavar="AAAA-MM-JJ",
                   help="date de décision (défaut : dernière séance du panel)")
    u.add_argument("--capital", type=_capital_arg, default=None, help="capital K en FCFA (défaut : 10 M)")
    u.add_argument("--panel-dir", default=None, help="répertoire du panel (défaut : data/panel)")

    ex = sub.add_parser("explain", help="explique la ligne d'un titre (décomposition du score, contraintes)",
                        description="Décomposition du score d'un titre à une date (S0 seulement) : univers, blocs de "
                                    "signaux (valeur, z, poids, contribution), rang, poids, plafonds, filtres de "
                                    "risque, notes de l'analyste, valorisation (information).")
    ex.add_argument("symbole", metavar="SYMBOLE", help="code BRVM (SNTS, ORAC…)")
    ex.add_argument("--date", type=_date_arg, default=None, metavar="AAAA-MM-JJ",
                    help="date de décision (défaut : dernière séance du panel)")
    ex.add_argument("--variante", default=None, help="variante (A … I, REF ; défaut : celle de l'ordre de bataille)")
    ex.add_argument("--capital", type=_capital_arg, default=None, help="capital K en FCFA (défaut : 10 M)")
    ex.add_argument("--format", choices=("texte", "json"), default="texte",
                    help="format de sortie (défaut : texte)")
    ex.add_argument("--sans-notes", action="store_true", help="ignore les notes de l'analyste")
    ex.add_argument("--panel-dir", default=None, metavar="DOSSIER", help="panel (défaut : data/panel)")

    b = sub.add_parser("backtest", help="backtest net de coûts (S1 refusé sans --validation-s1)")
    b.add_argument("--start", required=True, help="première séance simulée (AAAA-MM-JJ)")
    b.add_argument("--end", required=True, help="dernière séance simulée (AAAA-MM-JJ)")
    b.add_argument("--variant", default="A", help="variante pré-enregistrée (A … H)")
    b.add_argument("--capital", type=float, default=None, help="capital K en FCFA (défaut : 10 M)")
    b.add_argument("--costs", default="central", help="scénario de coûts : optimistic, central, stress, severe")
    b.add_argument("--window-basis", default=None, choices=("boc", "sessions"),
                   help="comptage des fenêtres (obligatoire avec --validation-s1)")
    b.add_argument("--validation-s1", action="store_true",
                   help="autorise S1 : réservé au test UNIQUE pré-enregistré (§8.1)")
    b.add_argument("--panel-dir", default=None, help="répertoire du panel (défaut : data/panel)")

    v = sub.add_parser("validate", help="validation : test unique S1 (verrouillé) ou diagnostic S0 (contaminé)")
    v.add_argument("--sample", required=True, choices=("S1", "S0"), help="échantillon : S1 (test unique) ou S0")
    v.add_argument("--rerun-reason", default=None,
                   help="S1 : motif d'une relance (bogue démontré) ; nouveaux essais, les deux résultats publiés")
    v.add_argument("--workers", type=int, default=None, help="processus parallèles (au plus 3)")
    v.add_argument("--out-dir", default=None, help="dossier de sortie (défaut : reports/validation_S1 ou "
                                                   "reports/diagnostic_S0)")
    v.add_argument("--panel-dir", default=None, help="répertoire du panel (défaut : data/panel)")
    v.add_argument("--decision-mode", default="evenementiel", choices=("evenementiel", "mensuel"),
                   help="evenementiel (défaut : fins de mois + ordres entre deux du §6, règles pays D10 dès la "
                        "séance qui suit l'annonce) ou mensuel (fins de mois seulement) ; consigné dans le verrou")

    # -- ordre de bataille, rapport, interface ------------------------------------------
    r = sub.add_parser("recommend", help="ordre de bataille complet pour un capital (Markdown, JSON ou HTML)",
                       description="Ordre de bataille « au titre et au franc près » : variante choisie d'après le test "
                                   "S1, ordres, prix limites, coûts détaillés, échéancier d'exécution, revenus, "
                                   "distribution à 12 mois (historique, pas une prévision), stress, déclencheurs.")
    r.add_argument("--capital", type=_capital_arg, required=True, metavar="K",
                   help="capital total en FCFA (titres détenus compris) : 10000000, 10M, 1,5Md")
    r.add_argument("--portefeuille", default=None, metavar="FICHIER.csv",
                   help="portefeuille actuel : CSV « symbole,titres » (une ligne par titre)")
    r.add_argument("--cash", type=_capital_arg, default=None, metavar="MONTANT",
                   help="liquidités disponibles (défaut : capital − titres détenus)")
    r.add_argument("--variante", default=None, help="variante imposée (défaut : choix d'après le test S1)")
    r.add_argument("--format", choices=("md", "json", "html"), default="md", help="format (défaut : md)")
    r.add_argument("--date", type=_date_arg, default=None, metavar="AAAA-MM-JJ",
                   help="date de décision (défaut : dernière séance du panel)")
    r.add_argument("--couts", default="central", help="scénario de coûts : optimistic, central, stress, severe")
    r.add_argument("--tirages", type=_positive_int, default=5000, metavar="N", help="tirages du bootstrap (5000)")
    r.add_argument("--graine", type=int, default=0, metavar="N", help="graine du bootstrap (0)")
    r.add_argument("--sortie", default=None, metavar="CHEMIN", help="écrit la sortie dans ce fichier")
    r.add_argument("--sans-notes", action="store_true", help="ignore les notes de l'analyste")
    r.add_argument("--sans-indices", action="store_true", help="n'évalue pas les indices (plus rapide)")
    _add_notes_root(r)
    r.add_argument("--panel-dir", default=None, metavar="DOSSIER", help="panel (défaut : data/panel)")

    rp = sub.add_parser("report", help="rapport HTML autonome (marché, S1, ordre de bataille, indices, notes…)")
    rp.add_argument("--capital", type=_capital_arg, required=True, metavar="K", help="capital total en FCFA")
    rp.add_argument("--sortie", default=None, metavar="CHEMIN",
                    help="fichier HTML (défaut : reports/rapport_AAAA-MM-JJ.html)")
    rp.add_argument("--date", type=_date_arg, default=None, metavar="AAAA-MM-JJ",
                    help="date de décision (défaut : dernière séance du panel)")
    rp.add_argument("--portefeuille", default=None, metavar="FICHIER.csv", help="CSV « symbole,titres »")
    rp.add_argument("--cash", type=_capital_arg, default=None, metavar="MONTANT",
                    help="liquidités disponibles (défaut : capital − titres détenus)")
    rp.add_argument("--variante", default=None, help="variante imposée (défaut : choix d'après le test S1)")
    rp.add_argument("--tirages", type=_positive_int, default=5000, metavar="N", help="tirages du bootstrap (5000)")
    rp.add_argument("--couts", default="central", help="scénario de coûts : optimistic, central, stress, severe")
    rp.add_argument("--graine", type=int, default=0, metavar="N", help="graine du bootstrap (0)")
    _add_notes_root(rp)
    rp.add_argument("--panel-dir", default=None, metavar="DOSSIER", help="panel (défaut : data/panel)")

    sv = sub.add_parser("serve", help="interface web locale (http://127.0.0.1:8765)",
                        description="Interface web locale en français (tableau de bord, notes, recherche, indices, "
                                    "portefeuille, explication, validation). Liée à 127.0.0.1 uniquement ; une autre "
                                    "adresse exige --hote (avertissement : l'interface n'a pas d'authentification).")
    sv.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"port (défaut : {DEFAULT_PORT} ; 0 : port libre)")
    sv.add_argument("--hote", default=None, metavar="ADRESSE",
                    help="adresse d'écoute autre que 127.0.0.1 (déconseillé : aucune authentification)")
    _add_notes_root(sv)
    sv.add_argument("--panel-dir", default=None, metavar="DOSSIER", help="panel (défaut : data/panel)")
    return parser


# ---------------------------------------------------------------------------
# Données : update, panel, live
# ---------------------------------------------------------------------------


def _build_panel(boc_dir: Path, panel_dir: Path, force: bool = False, workers: int | None = None) -> int:
    from brvm_alpha.data import store

    if not boc_dir.exists():
        _say(f"échec : dossier des BOC introuvable ({boc_dir})")
        return 1
    print(f"Reconstruction du panel {panel_dir} depuis {boc_dir}…", flush=True)
    summary = store.build_panel(boc_dir, panel_dir, workers=workers, force=force)
    print(str(summary))
    return 0


def _cmd_update(args: argparse.Namespace) -> int:
    from brvm_alpha.data import boc_download

    boc_dir = Path(args.boc_dir) if args.boc_dir else DEFAULT_BOC_DIR
    panel_dir = Path(args.panel_dir) if args.panel_dir else DEFAULT_PANEL_DIR
    today = dt.date.today()
    if args.start is not None:
        start = args.start.date()
    else:
        last = last_local_boc(boc_dir)
        start = (last + dt.timedelta(days=1)) if last else dt.date(2017, 1, 2)
    end = args.end.date() if args.end is not None else today
    if end > today:
        end = today
    delay = max(float(args.delai), boc_download.MIN_DELAY_S)
    days = boc_download.pending_days(start, end, boc_dir) if start <= end else []
    print(f"BOC manquants du {start:%d/%m/%Y} au {end:%d/%m/%Y} : {len(days)} jour(s) ouvré(s) à chercher "
          f"(dossier {boc_dir}).")
    print(f"Politesse : robots.txt respecté, {delay:.0f} s au moins entre deux requêtes, arrêt au premier HTTP "
          "403/429, quota de " f"{args.max_requetes} requêtes.")
    if days:
        worst = len(days) * len(boc_download.RECENT_SUFFIXES) * delay
        print(f"Durée maximale estimée : {worst / 60:.0f} min (5 adresses possibles par jour).")
    if args.simulation:
        for d in sorted(days):
            print(f"  {d:%Y-%m-%d}")
        print("Simulation : aucune requête envoyée.")
        return 0
    from brvm_alpha.notes import research as rs

    cache_dir = rs.DEFAULT_NOTES_DIR / "cache"
    blocked = rs.blocked_hosts(cache_dir).get("www.brvm.org")
    if blocked:
        _say(f"refusé : www.brvm.org a refusé l'accès le {blocked.get('ts')} (HTTP {blocked.get('status')}). "
             "Aucune requête n'est envoyée ; le blocage ne se lève qu'explicitement, avec l'accord du site.")
        return 2
    n, stopped = 0, None
    if days:
        fetch = brvm_fetcher(max_requests=args.max_requetes, delay_s=delay, cache_dir=cache_dir)
        try:
            n = boc_download.download_range(start, end, boc_dir, pause=delay, fetcher=fetch, today=today,
                                            progress=lambda m: print("  " + m, flush=True))
        except boc_download.DownloadStopped as exc:
            stopped = str(exc)
            _say(f"arrêt : {exc}")
        print(f"{n} BOC téléchargé(s) ; {fetch.session.n_requests} requête(s) envoyée(s).")  # type: ignore[attr-defined]
    code = 1 if stopped else 0
    if n > 0 and not args.sans_panel:
        code = max(code, _build_panel(boc_dir, panel_dir))
    elif not args.sans_panel:
        print("Aucun nouveau BOC : panel inchangé (python -m brvm_alpha panel pour le reconstruire).")
    return code


def _cmd_panel(args: argparse.Namespace) -> int:
    boc_dir = Path(args.boc_dir) if args.boc_dir else DEFAULT_BOC_DIR
    panel_dir = Path(args.panel_dir) if args.panel_dir else DEFAULT_PANEL_DIR
    return _build_panel(boc_dir, panel_dir, force=args.force, workers=args.workers)


def _cmd_live(args: argparse.Namespace) -> int:
    from brvm_alpha.data import live
    from brvm_alpha.notes import research as rs

    cache_dir = rs.DEFAULT_NOTES_DIR / "cache"
    sess = rs.PoliteSession(max_requests=3, offline=bool(args.hors_ligne), cache_dir=cache_dir,
                            log_path=cache_dir.parent / "fetch_log.jsonl")
    try:
        res = sess.get(live.LIVE_URL, max_age_s=60)
    except rs.ResearchError as exc:
        _say(f"échec : {exc}")
        return 1
    if res.status != 200:
        _say(f"échec : HTTP {res.status} sur {live.LIVE_URL}")
        return 1
    fetched = pd.Timestamp(res.fetched_at) if res.fetched_at else pd.Timestamp.now(tz="UTC")
    snap = live.parse_live_html(res.text, fetched_at=fetched.to_pydatetime())
    q = snap.quotes
    if args.symbole and len(q):
        wanted = {s.upper() for s in args.symbole}
        q = q[q["symbol"].str.upper().isin(wanted)]
    if args.format == "json":
        _print_json({"bandeau": BANNER, "source": live.LIVE_URL, "lu_le": fetched, "depuis_cache": res.from_cache,
                     "indices": snap.indices, "activite": snap.activity, "cours": q})
        return 0
    print(f"Cours du jour — {live.LIVE_URL} (lu le {fetched:%d/%m/%Y %H:%M} UTC"
          f"{', cache' if res.from_cache else ''}) : instantané, les cours du BOC du soir font foi.")
    for name, d in snap.indices.items():
        print(f"  {name:12s} {fr_num(d.get('level'), 2):>10s}  {fr_num(d.get('change_pct'), 2, True)} %")
    rows = [[r.symbol, str(r.name)[:28], fr_num(r.close, 0), fr_num(r.change_pct, 2, True) + " %", fr_num(r.volume, 0)]
            for r in q.itertuples()]
    if rows:
        print(_table(rows, ["Titre", "Nom", "Clôture", "Var.", "Volume"]))
    print(BANNER)
    return 0


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------


def _read_text_file(path: str) -> str:
    p = Path(path)
    if not p.is_file():
        raise ValueError(f"fichier introuvable : {path}")
    if p.stat().st_size > 2_000_000:
        raise ValueError("fichier trop volumineux (plus de 2 Mo)")
    return p.read_text(encoding="utf-8-sig")


def _split_targets(values: Sequence[str] | None) -> list[str]:
    out: list[str] = []
    for v in values or []:
        for t in re.split(r"[;,|\n]+", str(v)):
            if t.strip() and t.strip() not in out:
                out.append(t.strip())
    return out


def make_manual_note(*, targets: Sequence[str] | None = None, title: str = "", text: str = "",
                     stance: str | None = None, conviction: int | None = None, horizon: int | None = None,
                     source: str | None = None, url: str | None = None, published: str | None = None,
                     event_type: str | None = None, tags: Sequence[str] | None = None) -> Any:
    """Construit une ``Note`` de l'analyste à partir d'une saisie (CLI ou interface web).

    ``source`` : texte libre (« rapport annuel », « presse ») conservé en étiquette ``source:…`` ;
    un code du contrat (``manual``, ``url``…) est appliqué tel quel. ``url`` : http(s) seulement.
    Lève ``ValueError`` (message en français) pour une saisie invalide.
    """
    from brvm_alpha.notes.model import SOURCES, Note

    title = str(title or "").strip()
    text = str(text or "")
    if not title and not text.strip():
        raise ValueError("une note doit avoir un titre ou un texte")
    if len(title) > 500:
        raise ValueError("titre trop long (500 caractères au plus)")
    url = str(url or "").strip()
    if url and not re.match(r"^https?://[^\s<>\"']+$", url, re.I):
        raise ValueError("adresse invalide : http:// ou https:// attendu")
    src = "manual"
    tag_list = [str(t).strip() for t in (tags or []) if str(t).strip()]
    s = str(source or "").strip()
    if s:
        if s.lower() in SOURCES:
            src = s.lower()
        else:
            tag_list.append(f"source:{s[:120]}")
    pub: Any = None
    if published not in (None, ""):
        p = str(published).strip()
        try:
            pub = parse_date(p).strftime("%Y-%m-%d")
        except ValueError:
            try:
                ts = pd.Timestamp(p.replace("h", ":"))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"date de publication invalide : {p!r}") from exc
            pub = ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
        pub_ts = pd.Timestamp(pub)
        pub_naive = pub_ts.tz_convert("UTC").tz_localize(None) if pub_ts.tzinfo is not None else pub_ts
        if pub_naive > pd.Timestamp.now(tz="UTC").tz_localize(None) + pd.Timedelta(days=1):
            raise ValueError("date de publication dans le futur : une note n'agit qu'une fois publiée")
    if conviction is not None and not 1 <= int(conviction) <= 5:
        raise ValueError("conviction : entier de 1 à 5")
    if horizon is not None and int(horizon) <= 0:
        raise ValueError("horizon : nombre de séances > 0")
    kw: dict[str, Any] = dict(author="analyste", source=src, url=url, title=title, text=text,
                              targets=_split_targets(targets), event_type=event_type or None, stance=stance or None,
                              conviction=conviction, tags=tag_list, published_at=pub)
    if horizon is not None:
        kw["horizon_days"] = int(horizon)
    return Note(**kw)


def _analysis_lines(an: dict[str, Any] | None) -> list[str]:
    if not an:
        return ["Analyse : non disponible."]
    lines = [f"Analyse : type {an.get('event_type')}, score {fr_num(an.get('score'), 2, True)} (ton "
             f"{fr_num(an.get('tone'), 2, True)}, chiffres {fr_num(an.get('s_num'), 2, True)}), matérialité "
             f"{fr_num(an.get('materiality'), 2)}, confiance {fr_num(an.get('confidence'), 2)}."]
    if an.get("targets"):
        lines.append("Cibles retenues : " + ", ".join(an["targets"]))
    if an.get("risk_flags"):
        lines.append("Filtres de risque : " + ", ".join(an["risk_flags"]))
    if an.get("reading"):
        lines.append("Lecture : " + str(an["reading"]))
    for w in an.get("warnings") or []:
        lines.append("Avertissement : " + str(w))
    return lines


def _note_summary(n: Any) -> list[str]:
    lines = [f"Note {n.note_id[:12]} (version {n.version}, {n.status}) — {n.title or '(sans titre)'}",
             f"Publiée le {fr_date(n.published_at)} ; négociable à partir du {fr_date(n.first_tradable_session)} ; "
             f"auteur {n.author} ; source {n.source}" + (f" ({n.url})" if n.url else "")]
    if n.targets:
        lines.append("Cibles saisies : " + ", ".join(n.targets))
    if n.targets_unknown:
        lines.append("Cibles non reconnues (conservées, sans effet) : " + ", ".join(n.targets_unknown))
    if n.stance:
        lines.append(f"Avis : {n.stance}" + (f", conviction {n.conviction}/5" if n.conviction else "")
                     + f", horizon {n.horizon_days} séances")
    if n.tags:
        lines.append("Étiquettes : " + ", ".join(n.tags))
    return lines


def _status_arg(s: str) -> str | None:
    return {"actives": "active", "archivees": "archived", "toutes": None}[s]


def _cmd_notes(args: argparse.Namespace) -> int:
    cmd = args.notes_cmd
    if cmd == "analyze":
        from brvm_alpha.notes.analyze import analyze_text

        text = args.texte if args.texte is not None else _read_text_file(args.fichier)
        an = analyze_text(text, title=args.titre, manual_targets=_split_targets(args.cible)).to_dict()
        if args.format == "json":
            _print_json({"bandeau": BANNER, "analyse": an, "enregistree": False})
            return 0
        print("Analyse sans enregistrement (lecture factuelle, pas une prévision) :")
        print("\n".join(_analysis_lines(an)))
        print(BANNER)
        return 0
    store = _notes_store(args.racine)
    if cmd == "add":
        from brvm_alpha.notes.store import NoteConflictError

        text = args.texte if args.texte is not None else (_read_text_file(args.fichier) if args.fichier else "")
        note = make_manual_note(targets=args.cible, title=args.titre, text=text, stance=args.avis,
                                conviction=args.conviction, horizon=args.horizon, source=args.source, url=args.url,
                                published=args.publie_le, event_type=args.event_type, tags=args.etiquette)
        try:
            nid = store.add(note, analyze=True)
        except NoteConflictError as exc:
            _say(f"refusé : {exc}")
            return 2
        saved = store.get(nid)
        if args.format == "json":
            _print_json({"bandeau": BANNER, "note": saved.to_dict()})
            return 0
        print(f"Note enregistrée : {nid}")
        print("\n".join(_note_summary(saved) + _analysis_lines(saved.analysis)))
        print(BANNER)
        return 0
    if cmd == "list":
        df = store.list(target=args.cible, since=args.depuis, until=args.jusqu_au, status=_status_arg(args.statut))
        if len(df):
            df = df.sort_values("published_at", ascending=False).head(args.limite)
        if args.format == "json":
            cols = ["note_id", "version", "published_at", "first_tradable_session", "author", "source", "title",
                    "all_targets", "stance", "conviction", "status", "score", "materiality", "confidence", "risk_flags"]
            _print_json({"bandeau": BANNER, "notes": df[cols] if len(df) else []})
            return 0
        if store.errors:
            _say(f"{len(store.errors)} ligne(s) illisible(s) ignorée(s) dans le journal : {store.errors[0]}")
        if not len(df):
            print("Aucune note.")
            return 0
        rows = [[r.note_id[:12], fr_date(r.published_at), ", ".join(r.all_targets or [])[:28] or "—",
                 (r.title or "(sans titre)")[:48], fr_num(r.score, 2, True), r.status] for r in df.itertuples()]
        print(_table(rows, ["Id", "Publiée", "Cibles", "Titre", "Score", "Statut"]))
        print(f"{len(df)} note(s). {BANNER}")
        return 0
    if cmd == "show":
        nid = resolve_note_id(store, args.id)
        n = store.get(nid)
        versions = store.versions(nid)
        if args.format == "json":
            _print_json({"bandeau": BANNER, "note": n.to_dict(), "versions": [v.to_dict() for v in versions]})
            return 0
        print("\n".join(_note_summary(n)))
        if n.text:
            print("Texte :")
            print("  " + "\n  ".join(n.text.strip().splitlines()[:40]))
        print("\n".join(_analysis_lines(n.analysis)))
        print("Versions :")
        for v in versions:
            print(f"  v{v.version}  écrite le {fr_date(v.recorded_at)}  statut {v.status}  {v.title[:50]}")
        print(BANNER)
        return 0
    if cmd == "archive":
        nid = resolve_note_id(store, args.id)
        n = store.archive(nid, reason=args.motif)
        print(f"Note {nid[:12]} archivée (version {n.version} ; l'historique est conservé).")
        return 0
    if cmd == "export":
        if args.sortie == "-":
            import tempfile

            with tempfile.TemporaryDirectory() as tmp:
                out = store.export_markdown(Path(tmp) / "notes.md", target=args.cible, status=_status_arg(args.statut))
                print(out.read_text(encoding="utf-8"))
            return 0
        path = Path(args.sortie) if args.sortie else DEFAULT_REPORTS_DIR / f"notes_{dt.date.today():%Y%m%d}.md"
        out = store.export_markdown(path, target=args.cible, status=_status_arg(args.statut))
        print(f"Export Markdown : {out}")
        return 0
    if cmd == "research":
        from brvm_alpha.notes import research as rs

        print(RULES_POLITENESS)
        mode = "hors ligne (cache disque et BOC locaux, aucune requête)" if args.hors_ligne else \
            f"en ligne (au plus {args.max_requetes} requêtes vers www.brvm.org)"
        print(f"Recherche {mode}…", flush=True)
        targets = _split_targets(args.cibles) or None
        res = rs.run_research(store, targets=targets, since=args.depuis, max_requests=args.max_requetes,
                              offline=bool(args.hors_ligne), boc=not args.sans_boc, dry_run=bool(args.simulation))
        print(res.report.summary())
        for n in list(res)[:20]:
            print(f"  {n.note_id[:12]}  {fr_date(n.published_at)}  {', '.join(n.targets)[:24]:24s}  {n.title[:60]}")
        if len(res) > 20:
            print(f"  … et {len(res) - 20} autre(s) (python -m brvm_alpha notes list).")
        print(BANNER)
        return 1 if res.report.stopped else 0
    return 2  # pragma: no cover - argparse impose une action


# ---------------------------------------------------------------------------
# Indices
# ---------------------------------------------------------------------------


def _cmd_indices(args: argparse.Namespace) -> int:
    from brvm_alpha.notes import index_eval

    dossier = args.indices_cmd == "dossier"
    fmt = args.format
    t = _decision_date(args.date, args.panel_dir)
    if in_s1(t):
        _say(s1_refusal(t, "l'évaluation des indices"))
        return 2
    store = None if args.sans_notes else _notes_store(args.racine)
    if store is not None and not store.path.exists():
        store = None
    panels = index_eval.load_panels(args.panel_dir) if args.panel_dir else None
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        if dossier:
            d = index_eval.index_dossier(args.code, panels=panels, store=store, asof=t)
        else:
            ev = index_eval.evaluate_indices(panels=panels, store=store, asof=t)
    if dossier:
        if fmt == "json":
            _print_json({"bandeau": BANNER, **{k: v for k, v in d.items() if k != "overlays"}})
            return 0
        _print_dossier(d)
        return 0
    if fmt == "json":
        _print_json({"bandeau": BANNER, "asof": t, "indices": ev})
        return 0
    when = fr_date(ev["date"].max()) if len(ev) and "date" in ev else fr_date(t)
    print(f"Évaluation des indices au {when} — aide à la décision, pas un signal validé "
          f"(notes : {'incluses' if store is not None else 'aucune'}).")
    rows = [[code, str(r["label"])[:40], fr_num(r["level"], 2), fr_pct(r.get("ret_1m")), fr_pct(r.get("ret_12m")),
             fr_pct(r.get("ytd")), str(r["stance"]), fr_num(r["confidence"], 2), fr_num(r["composite"], 2, True)]
            for code, r in ev.iterrows()]
    print(_table(rows, ["Code", "Indice", "Niveau", "1 mois", "12 mois", "Depuis 31/12", "Position", "Confiance",
                        "Score"]))
    for code, r in ev.iterrows():
        reasons = list(r["reasons"] or [])
        shown = reasons if args.detail else reasons[:3]
        print(f"\n{r['label']} ({code}) : {r['stance']}, confiance {fr_num(r['confidence'], 2)}")
        for s in shown:
            print(f"  - {s}")
        if len(reasons) > len(shown):
            print(f"  ({len(reasons) - len(shown)} autre(s) raison(s) : --detail ; dossier : "
                  f"python -m brvm_alpha indices dossier {code})")
    print("\n" + BANNER)
    return 0


def _print_dossier(d: dict[str, Any]) -> None:
    ev = d["evaluation"]
    print(f"Dossier {d['label']} ({d['index']}) au {fr_date(ev.get('date'))} : {ev.get('stance')}, confiance "
          f"{fr_num(ev.get('confidence'), 2)}, score {fr_num(ev.get('composite'), 2, True)} ; composition : "
          f"{d.get('composition')}")
    print("Raisons :")
    for s in d.get("reasons") or []:
        print(f"  - {s}")
    cons = d.get("constituents")
    if isinstance(cons, pd.DataFrame) and len(cons):
        rows = [[sym, str(r.get("name") or "")[:26], fr_pct(r.get("weight"), 1, False), fr_num(r.get("close"), 0),
                 fr_pct(r.get("ret_12m")), fr_pct(r.get("contribution_12m"), 2), fr_num(r.get("note_score"), 2, True),
                 ",".join(r.get("flags") or []) + (" veto" if r.get("veto") else "")]
                for sym, r in cons.head(15).iterrows()]
        print(f"Constituants ({len(cons)}, 15 premiers par poids) :")
        print(_table(rows, ["Titre", "Nom", "Poids", "Cours", "12 mois", "Contrib. 12 m", "Notes", "Filtres"]))
    notes = d.get("recent_notes") or []
    print(f"Notes qui l'influencent ({len(notes)}) :" if notes else "Aucune note récente sur l'indice ou ses constituants.")
    for n in notes[:15]:
        print(f"  {str(n['note_id'])[:12]}  {fr_date(n['first_tradable_session'])}  score "
              f"{fr_num(n.get('score'), 2, True)}  {', '.join(n.get('targets') or [])[:24]}  {str(n.get('title'))[:50]}")
    cmm = d.get("change_my_mind") or []
    if cmm:
        print("Ce qui ferait changer d'avis :")
        for s in cmm:
            print(f"  - {s}")
    cal = d.get("calendar")
    if isinstance(cal, pd.DataFrame) and len(cal):
        print("Calendrier (120 prochains jours) :")
        for r in cal.head(12).to_dict(orient="records"):
            vals = [fr_date(v) if isinstance(v, pd.Timestamp) else str(v) for v in r.values() if v is not None]
            print("  " + " | ".join(vals)[:140])
    print(BANNER)


# ---------------------------------------------------------------------------
# Univers, explication, backtest, validation
# ---------------------------------------------------------------------------


def _cmd_universe(args: argparse.Namespace) -> int:
    from brvm_alpha.strategy import BrvmAlpha, build_panels

    t = _decision_date(args.date, args.panel_dir)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        panels = build_panels(args.panel_dir, end=t)
    u = BrvmAlpha(notes=None, capital=args.capital).universe(t, panels)
    # séparateur de milliers appliqué au seul montant (et non à toute la ligne, dont la virgule)
    floor = f"{u.attrs['mdv_floor']:,.0f}".replace(",", " ")
    print(f"Univers au {pd.Timestamp(t).date()} : {u.attrs['n_eligible']} titres éligibles, "
          f"mode {u.attrs['mode']} (plancher U5 {floor} FCFA)")
    for sym, row in u.iterrows():
        print(f"  {sym:6s} {'oui' if row['eligible'] else 'non'}  {row['reason']}")
    return 0


def explain_symbol(symbol: str, asof: Any, *, variant: str | None = None, capital: float | None = None,
                   notes: Any = "auto", panels: Any = None, panel_dir: Any = None) -> dict[str, Any]:
    """``BrvmAlpha.explain`` à la date ``asof`` (S1 refusé : ``ValueError``), variante par défaut = choix du §3.4."""
    from brvm_alpha.portfolio import recommend as rec
    from brvm_alpha.strategy import BrvmAlpha, build_panels

    if in_s1(asof):
        raise ValueError(s1_refusal(asof, "l'explication"))
    sym = str(symbol or "").upper().strip()
    if not re.fullmatch(r"[A-Z0-9]{2,8}", sym):
        raise ValueError(f"symbole invalide : {symbol!r}")
    choice = None
    if variant is None:
        choice = rec.choose_variant()
        variant = choice["variante"]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        if panels is None:
            panels = build_panels(panel_dir)
        model = BrvmAlpha(variant=variant, capital=capital or DEFAULT_CAPITAL, notes=notes)
        out = model.explain(pd.Timestamp(asof), panels, sym)
    out["choix_variante"] = None if choice is None else {k: choice.get(k) for k in ("variante", "motif", "statut_A")}
    return out


def _cmd_explain(args: argparse.Namespace) -> int:
    t = _decision_date(args.date, args.panel_dir)
    if in_s1(t):
        _say(s1_refusal(t, "l'explication"))
        return 2
    e = explain_symbol(args.symbole, t, variant=args.variante, capital=args.capital,
                       notes=None if args.sans_notes else "auto", panel_dir=args.panel_dir)
    if args.format == "json":
        _print_json({k: v for k, v in e.items()})
        return 0
    ch = e.get("choix_variante")
    print(f"Explication {e['symbol']} au {fr_date(e['asof'])}, variante {e['variant']}"
          + (f" ({ch.get('motif')})" if ch and ch.get("motif") else ""))
    print(e.get("text") or "")
    blocks = e.get("blocks") or {}
    if blocks:
        rows = [[lab, fr_num(b.get("raw"), 3), fr_num(b.get("z"), 2, True), fr_num(b.get("weight"), 2),
                 fr_num(b.get("contribution"), 3, True), "recherche" if b.get("research_only") else ""]
                for lab, b in blocks.items()]
        print(_table(rows, ["Bloc", "Valeur", "z", "Poids", "Contribution", ""]))
    sc = e.get("score") or {}
    print(f"Score final {fr_num(sc.get('final'), 3, True)} ; rang {sc.get('rank') or 'n.d.'}/{sc.get('n_ranked') or 'n.d.'} ; "
          f"poids cible {fr_pct(e.get('weight'), 2, False)}.")
    rf = e.get("risk_flags") or {}
    if rf.get("active"):
        print("Filtres de risque actifs : " + ", ".join(rf["active"]))
    print(e.get("banner") or BANNER)
    return 0


def _cmd_backtest(args: argparse.Namespace) -> int:
    if _overlaps_s1(args.start, args.end) and not args.validation_s1:
        print(f"refusé : la période {args.start} → {args.end} recoupe l'échantillon vierge S1 "
              f"({S1[0]} → {S1[1]}), réservé à un test unique pré-enregistré (--validation-s1).", file=sys.stderr)
        return 2
    if args.validation_s1 and args.window_basis is None:
        print("refusé : --validation-s1 exige --window-basis (boc ou sessions), à trancher par un addendum "
              "pré-enregistré.", file=sys.stderr)
        return 2
    from brvm_alpha import settings
    from brvm_alpha.backtest.engine import Backtester
    from brvm_alpha.strategy import BrvmAlpha, build_panels

    cfg = settings.apply_to_platform_config(scenario=args.costs)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        panels = build_panels(args.panel_dir, end=args.end)
    history = None if args.validation_s1 else "2022-11-17"
    model = BrvmAlpha(cfg, variant=args.variant, capital=args.capital, notes=None, history_start=history,
                      window_basis=args.window_basis, validation_s1=bool(args.validation_s1))
    bt = Backtester(panels, cfg.costs, cfg.constraints, model.capital, cfg.execution, cfg.taxes,
                    params=settings.load_strategy_config())
    res = bt.run(model.strategy_fn(), rebalance="M", start=args.start, end=args.end)
    s = res.summary(panels.get("market_tr"), benchmark_is_level=True) if "market_tr" in panels else res.summary()
    print(f"Backtest {args.variant} du {args.start} au {args.end} (coûts {args.costs}, estimation sous hypothèses)")
    for key in ("total_return", "cagr", "vol", "max_drawdown", "excess_cagr", "information_ratio", "turnover",
                "total_costs", "n_trades"):
        if key in s:
            print(f"  {key} : {s[key]}")
    print(BANNER)
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    from brvm_alpha.validation import ValidationFailed, ValidationRefused, run_validation

    try:
        res = run_validation(args.sample, out_dir=args.out_dir, rerun_reason=args.rerun_reason,
                             panel_dir=args.panel_dir, workers=args.workers, log=_say,
                             decision_mode=args.decision_mode)
    except ValidationRefused as exc:
        print(f"refusé : {exc}", file=sys.stderr)
        return 2
    except ValidationFailed as exc:
        print(f"échec : {exc}", file=sys.stderr)
        return 1
    m = res.metrics
    print(f"Validation {res.sample} : t0 = {pd.Timestamp(m['t0']).date()}, fin = {pd.Timestamp(m['fin']).date()}, "
          f"durée {res.duration_s:.0f} s (estimations sous hypothèses)")
    if res.sample == "S0":
        print("Diagnostic S0 : échantillon contaminé, aucune valeur de preuve.")
    for v, st in res.statuses.items():
        r = m["runs"].get(m["variantes"][v]["run_id"], {})
        act, ir = r.get("actif_tr_an"), r.get("ir_tr")
        act_s = f"{100 * act:+.1f} %/an" if act is not None and act == act else "n.d."
        ir_s = f"{ir:.2f}" if ir is not None and ir == ir else "n.d."
        print(f"  {v:4s} {st:12s} actif net / TR {act_s}, IR {ir_s}")
    print(f"Rapport : {res.out_dir / 'resultats.md'}")
    print(BANNER)
    return 0


# ---------------------------------------------------------------------------
# Ordre de bataille, rapport, interface
# ---------------------------------------------------------------------------

_HTML_WRAP = """<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title><style>
:root{{--bg:#fbfbfa;--fg:#1d2327;--muted:#5b6670;--line:#d9dde1;--accent:#1f5f8b}}
@media (prefers-color-scheme: dark){{:root{{--bg:#15191d;--fg:#e6e9ec;--muted:#9aa5ae;--line:#323a42;--accent:#7fb6e0}}}}
body{{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;margin:0;padding:16px}}
main{{max-width:1100px;margin:0 auto}} table{{border-collapse:collapse;font-size:13px}} th,td{{border-bottom:1px solid var(--line);
padding:4px 6px;text-align:left;vertical-align:top}} section{{overflow-x:auto}} a{{color:var(--accent)}}
.bandeau{{border-left:4px solid #b26b00;padding:8px 12px;font-weight:600}}
</style></head><body><main><p class="bandeau">{banner}</p>
{body}
</main></body></html>
"""


def html_document(title: str, fragment: str) -> str:
    """Document HTML minimal autour d'un fragment déjà échappé (bandeau inclus, aucune ressource externe)."""
    import html as _html

    return _HTML_WRAP.format(title=_html.escape(title), banner=_html.escape(BANNER), body=fragment)


def _holdings_arg(path: str | None) -> dict[str, int] | None:
    return read_holdings(path) if path else None


def _cmd_recommend(args: argparse.Namespace) -> int:
    from brvm_alpha.portfolio import recommend as rec

    t = _decision_date(args.date, args.panel_dir)
    if in_s1(t):
        _say(s1_refusal(t, "l'ordre de bataille"))
        return 2
    holdings = _holdings_arg(args.portefeuille)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        if args.sans_notes:
            store: Any = False
        elif args.racine:
            from brvm_alpha.notes.store import NoteStore

            store = NoteStore(args.racine)  # même journal que l'interface et le rapport (--racine)
        else:
            store = None
        o = rec.recommend(t, args.capital, holdings=holdings, cash=args.cash, variant=args.variante,
                          costs=args.couts, n_boot=args.tirages, seed=args.graine, notes_store=store,
                          panel_dir=args.panel_dir, index_evaluation=not args.sans_indices)
    if args.format == "json":
        out = json.dumps(o.to_dict(), ensure_ascii=False, indent=1)
    elif args.format == "html":
        out = html_document(f"Ordre de bataille au {fr_date(o.asof)}", o.to_html_fragment())
    else:
        out = o.to_markdown()
    if args.sortie:
        p = Path(args.sortie)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(out, encoding="utf-8")
        print(f"Ordre de bataille écrit : {p} ({len(out.encode('utf-8'))} octets). {BANNER}")
    else:
        print(out)
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    from brvm_alpha.report import build_report

    t = _decision_date(args.date, args.panel_dir)
    if in_s1(t):
        _say(s1_refusal(t, "le rapport"))
        return 2
    out = Path(args.sortie) if args.sortie else DEFAULT_REPORTS_DIR / f"rapport_{t:%Y-%m-%d}.html"
    kw: dict[str, Any] = {"holdings": _holdings_arg(args.portefeuille), "variant": args.variante,
                          "cash": args.cash, "n_boot": args.tirages, "costs": args.couts, "seed": args.graine}
    if args.racine:
        kw["notes_root"] = args.racine
    if args.panel_dir:
        kw["panel_dir"] = args.panel_dir
    print(f"Rapport au {fr_date(t)} pour {fr_num(args.capital, 0)} FCFA…", flush=True)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        path = build_report(t, args.capital, out, **kw)
    print(f"Rapport écrit : {path}")
    print(BANNER)
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:
    from brvm_alpha.ui import server

    host = args.hote or "127.0.0.1"
    allow_remote = False
    if args.hote and not is_loopback(args.hote):
        allow_remote = True
        _say(f"AVERTISSEMENT : écoute sur {args.hote} : l'interface n'a pas d'authentification ; toute machine qui "
             "atteint cette adresse peut lire et écrire les notes. À réserver à un réseau de confiance.")
    try:
        srv = server.make_server(host, args.port, allow_remote=allow_remote,
                                 services=server.Services(notes_root=args.racine, panel_dir=args.panel_dir))
    except (ValueError, OSError) as exc:
        _say(f"refusé : {exc}")
        return 2
    h, p = srv.server_address[:2]
    shown = f"[{h}]" if ":" in str(h) else h
    print(f"Interface BRVM Alpha : http://{shown}:{p}/  (Ctrl+C pour arrêter). {BANNER}", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt de l'interface.")
    finally:
        srv.shutdown_jobs()
        srv.server_close()
    return 0


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------

COMMANDS: dict[str, Callable[[argparse.Namespace], int]] = {
    "update": _cmd_update,
    "panel": _cmd_panel,
    "live": _cmd_live,
    "notes": _cmd_notes,
    "indices": _cmd_indices,
    "universe": _cmd_universe,
    "explain": _cmd_explain,
    "backtest": _cmd_backtest,
    "validate": _cmd_validate,
    "recommend": _cmd_recommend,
    "report": _cmd_report,
    "serve": _cmd_serve,
}


def main(argv: Sequence[str] | None = None) -> int:
    """Point d'entrée : renvoie le code de sortie (0 : succès ; 1 : échec ; 2 : refus ou saisie invalide)."""
    args = build_parser().parse_args(argv)
    handler = COMMANDS.get(args.command)
    if handler is None:  # pragma: no cover - argparse impose une commande
        return 2
    try:
        return handler(args)
    except FileNotFoundError as exc:
        _say(f"échec : fichier introuvable ({exc}). Le panel existe-t-il ? (python -m brvm_alpha panel)")
        return 1
    except (ValueError, KeyError) as exc:
        msg = exc.args[0] if isinstance(exc, KeyError) and exc.args else exc
        _say(f"erreur : {msg}")
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
