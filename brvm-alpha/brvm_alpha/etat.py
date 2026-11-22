"""État de l'installation : commande ``python -m brvm_alpha etat`` et adresse ``/etat.json`` de l'interface.

Lecture seule : aucun fichier n'est écrit, **aucune requête réseau** n'est envoyée, aucune commande
système n'est lancée (le commit git est lu dans le dossier ``.git``). Le relevé ne fait jamais
échouer la commande : une donnée absente ou illisible est rendue comme « rien » (``null``, 0).

Contenu (mêmes clés en texte et en JSON) :

- ``pret`` : vrai si le panel existe et n'est pas vide ;
- ``version`` : commit git court du code, à défaut la variable ``BRVM_ALPHA_VERSION``, à défaut
  « inconnue » ;
- ``panel`` : dernière séance, séances présentes et manquantes, retard éventuel
  (``portfolio.recommend.panel_staleness`` et ``stale_panel_message``, comme sur les pages) ;
- ``bulletins`` : bulletins en cache, jours marqués sans bulletin, jours restant à télécharger d'après
  le calcul de ``update --simulation`` (:func:`brvm_alpha.cli.update_window`), et le même calcul
  depuis le début de l'historique (``update --from 2017-01-02``, pour la première collecte) ;
- ``site`` : blocage éventuel de www.brvm.org (refus HTTP 403 ou 429 enregistré) ;
- ``notes`` : notes au journal et notes en vigueur ;
- ``rapport`` : dernier rapport écrit (nom, date) ;
- ``donnees`` : dossier de données et sa taille.

Performance passée ≠ garantie. Aucun gain n'est garanti.
"""

from __future__ import annotations

import datetime as dt
import os
import re
from pathlib import Path
from typing import Any

import pandas as pd

from brvm_alpha import cli, paths

#: Variable d'environnement de repli pour la version quand le code est livré sans dossier ``.git``.
ENV_VERSION = "BRVM_ALPHA_VERSION"
UNKNOWN_VERSION = "inconnue"
_SHA_RE = re.compile(r"^[0-9a-f]{40,64}$")
_VERSION_RE = re.compile(r"^[A-Za-z0-9._-]{1,40}$")
_REPORT_NAME_RE = re.compile(r"^rapport_\d{4}-\d{2}-\d{2}\.html$")
_BOC_RE = re.compile(r"^boc_(\d{8})\.(txt\.gz|txt|missing|bad)$")


# ---------------------------------------------------------------------------
# Version du code
# ---------------------------------------------------------------------------


def _git_dir(start: Path) -> Path | None:
    """Dossier ``.git`` du dépôt qui contient ``start`` (un fichier ``.git`` « gitdir: … » est suivi)."""
    for folder in (start, *start.parents):
        marker = folder / ".git"
        if marker.is_dir():
            return marker
        if marker.is_file():
            try:
                first = marker.read_text(encoding="utf-8", errors="replace").splitlines()[0]
            except (OSError, IndexError):
                return None
            if first.startswith("gitdir:"):
                target = Path(first.split(":", 1)[1].strip())
                target = target if target.is_absolute() else folder / target
                return target if target.is_dir() else None
            return None
    return None


def _read_ref(git_dir: Path, ref: str) -> str | None:
    """Commit d'une référence (fichier ``refs/…`` ou ligne de ``packed-refs``), dans le dossier git ou son dossier commun."""
    if not re.fullmatch(r"refs/[A-Za-z0-9._/\-]+", ref) or ".." in ref:
        return None
    homes = [git_dir]
    try:
        common = (git_dir / "commondir").read_text(encoding="utf-8").strip()
        homes.append((git_dir / common).resolve())
    except OSError:
        pass
    for home in homes:
        try:
            sha = (home / ref).read_text(encoding="utf-8").strip()
            if _SHA_RE.match(sha):
                return sha
        except OSError:
            pass
        try:
            for line in (home / "packed-refs").read_text(encoding="utf-8", errors="replace").splitlines():
                parts = line.split()
                if len(parts) == 2 and parts[1] == ref and _SHA_RE.match(parts[0]):
                    return parts[0]
        except OSError:
            pass
    return None


def code_version(root: str | Path | None = None, environ: Any = None) -> str:
    """Commit git court (7 caractères) du code, sans lancer ``git`` ; sinon ``BRVM_ALPHA_VERSION`` ; sinon « inconnue »."""
    try:
        git_dir = _git_dir(Path(root) if root is not None else paths.REPO_ROOT)
        if git_dir is not None:
            head = (git_dir / "HEAD").read_text(encoding="utf-8").strip()
            sha = _read_ref(git_dir, head.split(":", 1)[1].strip()) if head.startswith("ref:") else head
            if sha and _SHA_RE.match(sha):
                return sha[:7]
    except (OSError, IndexError):
        pass
    given = str((os.environ if environ is None else environ).get(ENV_VERSION, "") or "").strip()
    return given if _VERSION_RE.match(given) else UNKNOWN_VERSION


# ---------------------------------------------------------------------------
# Mesures élémentaires (aucune ne lève d'exception)
# ---------------------------------------------------------------------------


def dir_size(path: str | Path) -> int:
    """Taille en octets des fichiers d'un dossier (liens symboliques non suivis) ; 0 s'il n'existe pas."""
    total = 0
    stack = [str(path)]
    while stack:
        folder = stack.pop()
        try:
            with os.scandir(folder) as it:
                for entry in it:
                    try:
                        if entry.is_symlink():
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                        elif entry.is_file(follow_symlinks=False):
                            total += entry.stat(follow_symlinks=False).st_size
                    except OSError:
                        continue
        except OSError:
            continue
    return total


def human_size(n_bytes: int) -> str:
    """Taille lisible : « 0 octet », « 512 Ko », « 212 Mo », « 1,4 Go »."""
    n = max(int(n_bytes), 0)
    if n < 1024:
        return f"{n} octet" + ("s" if n > 1 else "")
    for unit, size in (("Go", 1024 ** 3), ("Mo", 1024 ** 2), ("Ko", 1024)):
        if n >= size:
            return f"{cli.fr_num(n / size, 1 if unit == 'Go' else 0)} {unit}"
    return f"{n} octets"  # pragma: no cover - inatteignable


def _iso_day(x: Any) -> str | None:
    return None if x is None else pd.Timestamp(x).strftime("%Y-%m-%d")


def _iso_instant(x: Any) -> str | None:
    if x is None:
        return None
    t = pd.Timestamp(x)
    t = t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def panel_state(panel_dir: Path, now: pd.Timestamp) -> dict[str, Any]:
    """Dernière séance, séances présentes et manquantes, retard du panel à l'instant ``now``."""
    out: dict[str, Any] = {"dossier": str(panel_dir), "derniere_seance": None, "seances_presentes": 0,
                           "seances_manquantes": 0, "seances_en_retard": 0, "retard": None}
    try:
        if (panel_dir / "sessions.parquet").exists():
            s = pd.read_parquet(panel_dir / "sessions.parquet", columns=["date", "available"])
            avail = s["available"].astype(bool)
            out["seances_presentes"] = int(avail.sum())
            out["seances_manquantes"] = int((~avail).sum())
        elif (panel_dir / "equities.parquet").exists():
            d = pd.read_parquet(panel_dir / "equities.parquet", columns=["date"])["date"]
            out["seances_presentes"] = int(d.nunique())
    except Exception:  # panel illisible : rendu comme vide
        out["seances_presentes"] = out["seances_manquantes"] = 0
    last = cli.last_session(panel_dir) if out["seances_presentes"] else None
    if last is None:
        out["seances_presentes"] = 0
        return out
    out["derniere_seance"] = _iso_day(last)
    try:
        from brvm_alpha.portfolio import recommend as rec

        stale, _closed, _day = rec.panel_staleness(last, now)
        out["seances_en_retard"] = len(stale)
        out["retard"] = rec.stale_panel_message(last, now, orders=False)
    except Exception:  # le contrôle du retard ne fait jamais échouer le relevé
        pass
    return out


def bulletins_state(boc_dir: Path, today: dt.date) -> dict[str, Any]:
    """Bulletins en cache et jours restant à télécharger (calcul de ``update``, sans aucune requête)."""
    n_boc = n_missing = 0
    last: dt.date | None = None
    try:
        names = os.listdir(boc_dir)
    except OSError:
        names = []
    for name in names:
        m = _BOC_RE.match(name)
        if not m:
            continue
        if m.group(2) in ("txt.gz", "txt"):
            n_boc += 1
            try:
                day = dt.datetime.strptime(m.group(1), "%Y%m%d").date()
            except ValueError:
                continue
            last = day if last is None or day > last else last
        elif m.group(2) == "missing":
            n_missing += 1
    out: dict[str, Any] = {"dossier": str(boc_dir), "en_cache": n_boc, "sans_bulletin": n_missing,
                           "dernier": _iso_day(last), "jours_a_telecharger": 0, "premier_jour_cherche": None,
                           "jours_a_telecharger_depuis_2017": 0}
    try:
        start, _end, days = cli.update_window(boc_dir, today=today)
        out["jours_a_telecharger"] = len(days)
        out["premier_jour_cherche"] = _iso_day(start)
        out["jours_a_telecharger_depuis_2017"] = len(cli.update_window(boc_dir, start=cli.HISTORY_START, today=today)[2])
    except Exception:  # pragma: no cover - dossier illisible
        pass
    return out


def site_state(notes_root: Path) -> dict[str, Any]:
    """Blocage éventuel de www.brvm.org, lu dans l'état de politesse du cache (aucune requête)."""
    out: dict[str, Any] = {"bloque": False, "depuis": None, "code_http": None}
    try:
        from brvm_alpha.notes import research as rs

        blocked = rs.blocked_hosts(notes_root / "cache").get("www.brvm.org")
    except Exception:
        blocked = None
    if blocked:
        out.update(bloque=True, depuis=str(blocked.get("ts") or "") or None, code_http=blocked.get("status"))
    return out


def notes_state(store: Any, panel_dir: Path, last: Any, now: pd.Timestamp, status: Any = None) -> dict[str, Any]:
    """Notes au journal et notes en vigueur à la séance d'application (mode direct, comme les pages)."""
    out: dict[str, Any] = {"dossier": str(getattr(store, "root", "")), "journal_present": False, "au_journal": 0,
                           "en_vigueur": 0}
    try:
        if store is None or not Path(store.path).exists():
            return out
        out["journal_present"] = True
        out["au_journal"] = len(store)
        if status is None and last is not None and out["au_journal"]:
            cal = pd.read_parquet(panel_dir / "sessions.parquet") if (panel_dir / "sessions.parquet").exists() else None
            eq = str(panel_dir) if (panel_dir / "equities.parquet").exists() else None
            known = cli.notes_instant(None, None, panel_dir, last=last, now=now)
            status = cli.notes_status(store, pd.Timestamp(last), known, calendar=cal, equities=eq)
        if status and not status.get("erreur"):
            out["en_vigueur"] = int(status.get("n_in_force") or 0)
    except Exception:  # journal illisible : compte nul, jamais d'échec
        pass
    return out


def report_state(reports_dir: Path) -> dict[str, Any]:
    """Dernier rapport écrit ``rapport_AAAA-MM-JJ.html`` (le plus récemment modifié) : nom et date."""
    out: dict[str, Any] = {"dossier": str(reports_dir), "nom": None, "date": None}
    best: tuple[float, str] | None = None
    try:
        for entry in os.scandir(reports_dir):
            if _REPORT_NAME_RE.match(entry.name) and entry.is_file():
                key = (entry.stat().st_mtime, entry.name)
                best = key if best is None or key > best else best
    except OSError:
        return out
    if best is not None:
        out["nom"] = best[1]
        out["date"] = _iso_instant(pd.Timestamp(best[0], unit="s", tz="UTC"))
    return out


# ---------------------------------------------------------------------------
# Relevé complet et mise en forme
# ---------------------------------------------------------------------------


def collect_state(*, panel_dir: str | Path | None = None, boc_dir: str | Path | None = None,
                  notes_root: str | Path | None = None, reports_dir: str | Path | None = None,
                  data_dir: str | Path | None = None, now: Any = None, store: Any = None,
                  notes_status: Any = None) -> dict[str, Any]:
    """État complet de l'installation (dictionnaire sérialisable en JSON) ; ne lève jamais.

    Les dossiers absents prennent les valeurs par défaut (:mod:`brvm_alpha.paths`). ``store`` :
    journal des notes déjà ouvert (sinon ouvert depuis ``notes_root``) ; ``notes_status`` : état daté
    des notes déjà calculé (l'interface le garde en cache). ``now`` : instant du relevé (UTC).
    """
    t = cli.now_utc() if now is None else pd.Timestamp(now)
    t = t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")
    pdir = Path(panel_dir) if panel_dir else cli.DEFAULT_PANEL_DIR
    bdir = Path(boc_dir) if boc_dir else cli.DEFAULT_BOC_DIR
    rdir = Path(reports_dir) if reports_dir else cli.DEFAULT_REPORTS_DIR
    ddir = Path(data_dir) if data_dir else paths.DATA_DIR
    if store is None:
        try:
            store = cli._notes_store(notes_root)
        except Exception:
            store = None
    nroot = Path(getattr(store, "root", notes_root or paths.NOTES_DIR))
    panel = panel_state(pdir, t)
    size = dir_size(ddir)
    return {
        "bandeau": cli.BANNER,
        "pret": bool(panel["seances_presentes"] > 0 and panel["derniere_seance"]),
        "version": code_version(),
        "releve_le": _iso_instant(t),
        "panel": panel,
        "bulletins": bulletins_state(bdir, t.date()),
        "site": site_state(nroot),
        "notes": notes_state(store, pdir, panel["derniere_seance"], t, notes_status),
        "rapport": report_state(rdir),
        "donnees": {"dossier": str(ddir), "taille_octets": size, "taille": human_size(size)},
    }


def _fr_day(iso: Any) -> str:
    return cli.fr_date(iso) if iso else "aucune"


def _fr_instant(iso: Any) -> str:
    return f"{pd.Timestamp(iso):%d/%m/%Y %H:%M} UTC" if iso else "date inconnue"


def format_text(state: dict[str, Any]) -> str:
    """Relevé en phrases simples (français), terminé par l'avertissement obligatoire."""
    p, b, s, n, r, d = (state[k] for k in ("panel", "bulletins", "site", "notes", "rapport", "donnees"))
    lines = [f"État de BRVM Alpha (version du code : {state['version']}), relevé le {_fr_instant(state['releve_le'])}."]
    lines.append("Prêt : oui (le panel existe et n'est pas vide)." if state["pret"] else
                 "Prêt : non (le panel est absent ou vide). " + cli.PANEL_HINT[0].upper() + cli.PANEL_HINT[1:] + ".")
    lines.append(f"Panel : dernière séance le {_fr_day(p['derniere_seance'])} ; {cli.fr_num(p['seances_presentes'], 0)} "
                 f"séance(s) présente(s), {cli.fr_num(p['seances_manquantes'], 0)} manquante(s). Dossier : {p['dossier']}.")
    lines.append(f"Retard du panel : {p['retard'].replace('`', '')}" if p["retard"] else "Retard du panel : aucun.")
    lines.append(f"Bulletins : {cli.fr_num(b['en_cache'], 0)} en cache (dernier : {_fr_day(b['dernier'])}), "
                 f"{cli.fr_num(b['sans_bulletin'], 0)} jour(s) marqué(s) sans bulletin. Dossier : {b['dossier']}.")
    lines.append(f"Jours restant à télécharger : {cli.fr_num(b['jours_a_telecharger'], 0)} (calcul de « update », à "
                 f"partir du {_fr_day(b['premier_jour_cherche'])}) ; {cli.fr_num(b['jours_a_telecharger_depuis_2017'], 0)} "
                 "depuis le 02/01/2017 (calcul de « update --from 2017-01-02 »). Aucune requête n'a été envoyée.")
    lines.append(f"Site www.brvm.org : bloqué depuis le {s['depuis'] or 'date inconnue'} (HTTP {s['code_http']}) : aucune "
                 "requête ne lui est envoyée tant que le blocage n'est pas levé." if s["bloque"] else
                 "Site www.brvm.org : aucun refus enregistré.")
    lines.append(f"Notes : {cli.fr_num(n['au_journal'], 0)} au journal, {cli.fr_num(n['en_vigueur'], 0)} en vigueur. "
                 f"Dossier : {n['dossier']}." if n.get("journal_present") else
                 f"Notes : aucun journal pour l'instant. Dossier : {n['dossier']}.")
    lines.append(f"Dernier rapport écrit : {r['nom']}, le {_fr_instant(r['date'])}. Dossier : {r['dossier']}." if r["nom"]
                 else f"Dernier rapport écrit : aucun. Dossier : {r['dossier']}.")
    lines.append(f"Données : {d['taille']}. Dossier : {d['dossier']}.")
    lines.append(state.get("bandeau") or cli.BANNER)
    return "\n".join(lines)


__all__ = ["ENV_VERSION", "UNKNOWN_VERSION", "code_version", "dir_size", "human_size", "panel_state", "bulletins_state",
           "site_state", "notes_state", "report_state", "collect_state", "format_text"]
