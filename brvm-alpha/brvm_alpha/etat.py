"""État de l'installation : commande ``python -m brvm_alpha etat`` et adresse ``/etat.json`` de l'interface.

Lecture seule : aucun fichier n'est écrit, **aucune requête réseau** n'est envoyée, aucune commande
système n'est lancée (le commit git est lu dans le dossier ``.git``). Le relevé ne fait jamais
échouer la commande : une donnée absente ou illisible est rendue comme « rien » (``null``, 0).

Contenu (mêmes clés en texte et en JSON) :

- ``pret`` : vrai seulement si le panel est **lisible** (calendrier et table des actions) **et**
  l'historique **complet** (``historique_complet``) ; sinon ``raison`` dit pourquoi, en une phrase
  (« historique incomplet : N jours à télécharger… », « panel illisible : … ») ;
- ``historique_complet`` : aucun jour ouvré sans fichier depuis le 02/01/2017 (hors jours récents, dont
  le BOC n'est peut-être pas encore publié ; un jour marqué sans bulletin compte comme connu), et panel
  qui couvre les bulletins (du premier au dernier) ;
- ``version`` : en mode embarqué, la version écrite dans ``VERSION`` ; sinon le commit git court du
  code, à défaut la variable ``BRVM_ALPHA_VERSION``, à défaut « inconnue » ;
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
    """Version du code : en mode embarqué, celle du fichier ``VERSION`` ; sinon le commit git court (7 caractères),
    lu sans lancer ``git`` ; sinon ``BRVM_ALPHA_VERSION`` ; sinon « inconnue »."""
    code_root = Path(root) if root is not None else paths.REPO_ROOT
    if paths.est_embarque(environ, code_root):
        shipped = paths.version_livree(code_root)
        if shipped:
            return shipped
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
    """Dernière séance, séances présentes et manquantes, retard du panel à l'instant ``now``.

    ``lisible`` : le calendrier (``sessions.parquet``) **et** la table des actions (``equities.parquet``,
    une colonne lue) s'ouvrent ; sinon ``erreur`` dit lequel et pourquoi, et le panel compte pour vide.
    Lecture sous le verrou partagé du panel (jamais un panel à moitié remplacé), sans rien écrire.
    """
    out: dict[str, Any] = {"dossier": str(panel_dir), "derniere_seance": None, "seances_presentes": 0,
                           "seances_manquantes": 0, "seances_en_retard": 0, "retard": None,
                           "premiere_seance": None, "lisible": False, "erreur": None}
    from brvm_alpha.data import store as _store

    try:
        with _store.lecture_panel(panel_dir, lock_timeout_s=5.0):
            sess_p, eq_p = panel_dir / "sessions.parquet", panel_dir / "equities.parquet"
            if not sess_p.exists() and not eq_p.exists():
                return out
            what = "sessions.parquet"
            try:
                if sess_p.exists():
                    s = pd.read_parquet(sess_p, columns=["date", "available"])
                    avail = s["available"].astype(bool)
                    out["seances_presentes"] = int(avail.sum())
                    out["seances_manquantes"] = int((~avail).sum())
                    days = pd.to_datetime(s.loc[avail, "date"], errors="coerce").dropna()
                    out["premiere_seance"] = _iso_day(days.min()) if len(days) else None
                what = "equities.parquet"
                if not eq_p.exists():
                    raise FileNotFoundError("fichier absent")
                d = pd.read_parquet(eq_p, columns=["date"])["date"]
                if not sess_p.exists():
                    out["seances_presentes"] = int(d.nunique())
                    out["premiere_seance"] = _iso_day(d.min()) if len(d) else None
            except Exception as exc:  # panel illisible : rendu comme vide, avec le motif
                out["seances_presentes"] = out["seances_manquantes"] = 0
                out["premiere_seance"] = None
                out["erreur"] = f"{what} : {type(exc).__name__}: {str(exc)[:200]}"
                return out
            last = cli.last_session(panel_dir) if out["seances_presentes"] else None
    except Exception as exc:  # verrou occupé au-delà de 5 s (bascule bloquée) : relevé sans le panel
        out["erreur"] = f"lecture impossible : {exc}"
        return out
    if last is None:
        out["seances_presentes"] = 0
        return out
    out["lisible"] = True
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
    first: dt.date | None = None
    for name in names:
        m = _BOC_RE.match(name)
        if m and m.group(2) in ("txt.gz", "txt"):
            try:
                day = dt.datetime.strptime(m.group(1), "%Y%m%d").date()
            except ValueError:
                continue
            first = day if first is None or day < first else first
    out: dict[str, Any] = {"dossier": str(boc_dir), "en_cache": n_boc, "sans_bulletin": n_missing,
                           "dernier": _iso_day(last), "premier": _iso_day(first), "jours_a_telecharger": 0,
                           "premier_jour_cherche": None, "jours_a_telecharger_depuis_2017": 0,
                           "sans_bulletin_definitif": 0, "a_reessayer": 0, "jours_manquants": None,
                           "historique_complet": False}
    try:
        start, _end, days = cli.update_window(boc_dir, today=today)
        out["jours_a_telecharger"] = len(days)
        out["premier_jour_cherche"] = _iso_day(start)
        out["jours_a_telecharger_depuis_2017"] = len(cli.update_window(boc_dir, start=cli.HISTORY_START, today=today)[2])
    except Exception:  # pragma: no cover - dossier illisible
        pass
    try:
        from brvm_alpha.data import boc_download

        st = boc_download.etat_dossier(boc_dir, boc_download.HISTORY_START, today, today)
        out["sans_bulletin_definitif"] = st.marques_definitifs
        out["a_reessayer"] = st.marques_non_definitifs
        out["jours_manquants"] = len(st.sans_fichier)
        out["historique_complet"] = bool(n_boc) and not st.sans_fichier
    except Exception:  # pragma: no cover - dossier illisible : historique réputé incomplet
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
    bulletins = bulletins_state(bdir, t.date())
    complete, reason = readiness(panel, bulletins)
    size = dir_size(ddir)
    return {
        "bandeau": cli.BANNER,
        "pret": reason is None,
        "raison": reason,
        "historique_complet": complete,
        "version": code_version(),
        "releve_le": _iso_instant(t),
        "panel": panel,
        "bulletins": bulletins,
        "site": site_state(nroot),
        "notes": notes_state(store, pdir, panel["derniere_seance"], t, notes_status),
        "rapport": report_state(rdir),
        "donnees": {"dossier": str(ddir), "taille_octets": size, "taille": human_size(size)},
    }


#: Commande à relancer tant que l'historique est incomplet.
HISTORY_HINT = ("lancer python -m brvm_alpha update --from 2017-01-02, à relancer tant que des jours restent à "
                "télécharger, puis python -m brvm_alpha panel")


def readiness(panel: dict[str, Any], bulletins: dict[str, Any]) -> tuple[bool, str | None]:
    """``(historique complet, raison de « pas prêt » ou None)`` d'après les relevés du panel et des bulletins."""
    n_missing = bulletins.get("jours_manquants")
    hist_ok = bool(bulletins.get("historique_complet"))
    covers = True
    cover_reason = None
    if panel.get("lisible"):
        last_b, first_b = bulletins.get("dernier"), bulletins.get("premier")
        last_p, first_p = panel.get("derniere_seance"), panel.get("premiere_seance")
        if last_b and last_p and last_p < last_b:
            covers = False
            cover_reason = (f"panel à reconstruire : il s'arrête au {cli.fr_date(last_p)} alors que le dernier bulletin "
                            f"est du {cli.fr_date(last_b)} (python -m brvm_alpha panel)")
        elif first_b and first_p and first_p > first_b:
            covers = False
            cover_reason = (f"panel à reconstruire : il commence au {cli.fr_date(first_p)} alors que le premier "
                            f"bulletin est du {cli.fr_date(first_b)} (python -m brvm_alpha panel)")
    complete = hist_ok and covers
    if panel.get("erreur") and not panel.get("lisible"):
        return complete, f"panel illisible : {panel['erreur']}"
    if not panel.get("lisible") or not panel.get("seances_presentes"):
        return complete, "panel absent ou vide"
    if not hist_ok:
        n = n_missing if n_missing is not None else bulletins.get("jours_a_telecharger_depuis_2017", 0)
        return complete, (f"historique incomplet : {cli.fr_num(n, 0)} jour(s) à télécharger depuis le 02/01/2017 "
                          f"(panel de {cli.fr_num(panel.get('seances_presentes', 0), 0)} séance(s))")
    if not covers:
        return complete, cover_reason
    return complete, None


def _fr_day(iso: Any, none: str = "aucune") -> str:
    return cli.fr_date(iso) if iso else none


def _fr_instant(iso: Any) -> str:
    return f"{pd.Timestamp(iso):%d/%m/%Y %H:%M} UTC" if iso else "date inconnue"


def format_text(state: dict[str, Any]) -> str:
    """Relevé en phrases simples (français), terminé par l'avertissement obligatoire."""
    p, b, s, n, r, d = (state[k] for k in ("panel", "bulletins", "site", "notes", "rapport", "donnees"))
    lines = [f"État de BRVM Alpha (version du code : {state['version']}), relevé le {_fr_instant(state['releve_le'])}."]
    reason = state.get("raison")
    if state["pret"]:
        lines.append("Prêt : oui (panel lisible, historique complet depuis le 02/01/2017).")
    elif reason and reason.startswith("historique incomplet"):
        lines.append(f"Prêt : non ({reason}). {HISTORY_HINT[0].upper() + HISTORY_HINT[1:]}.")
    elif reason and reason.startswith("panel à reconstruire"):
        lines.append(f"Prêt : non ({reason}).")
    else:
        lines.append(f"Prêt : non ({reason or 'panel absent ou vide'}). " + cli.PANEL_HINT[0].upper()
                     + cli.PANEL_HINT[1:] + ".")
    lines.append("Historique : complet depuis le 02/01/2017." if state.get("historique_complet") else
                 f"Historique : incomplet ({cli.fr_num(b.get('jours_manquants') or 0, 0)} jour(s) sans bulletin ni "
                 "marqueur depuis le 02/01/2017).")
    if p["derniere_seance"]:
        lines.append(f"Panel : dernière séance le {_fr_day(p['derniere_seance'])} ; "
                     f"{cli.fr_num(p['seances_presentes'], 0)} séance(s) présente(s), "
                     f"{cli.fr_num(p['seances_manquantes'], 0)} manquante(s). Dossier : {p['dossier']}.")
    else:
        lines.append(f"Panel : aucune séance. Dossier : {p['dossier']}.")
    lines.append(f"Retard du panel : {p['retard'].replace('`', '')}" if p["retard"] else "Retard du panel : aucun.")
    lines.append(f"Bulletins : {cli.fr_num(b['en_cache'], 0)} en cache (dernier : {_fr_day(b['dernier'], 'aucun')}), "
                 f"{cli.fr_num(b['sans_bulletin'], 0)} jour(s) marqué(s) sans bulletin. Dossier : {b['dossier']}.")
    if b.get("a_reessayer"):
        lines.append(f"Jours à réessayer : {cli.fr_num(b['a_reessayer'], 0)} (marqueur non définitif : réponse sans PDF, "
                     "redirection ou extraction ratée ; seul un 404 répété le rend définitif).")
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


__all__ = ["ENV_VERSION", "UNKNOWN_VERSION", "HISTORY_HINT", "code_version", "dir_size", "human_size", "panel_state",
           "bulletins_state", "readiness", "site_state", "notes_state", "report_state", "collect_state", "format_text"]
