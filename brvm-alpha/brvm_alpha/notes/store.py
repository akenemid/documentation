"""Journal des notes : ``NoteStore``, fichier JSONL **append-only** (``data/notes/notes.jsonl``).

Principes :
- **une ligne par version** de note ; une modification ou un archivage ajoute une ligne,
  aucune ligne n'est jamais réécrite ni supprimée (historique complet, auditable) ;
- écriture sous **verrou** (fichier ``.lock`` créé en exclusif, verrou périmé levé après
  ``stale_after_s``) et ``fsync`` après chaque ajout ;
- une ligne illisible (écriture interrompue) est ignorée à la lecture et signalée dans
  ``errors`` ; le fichier n'est pas réparé en place ;
- ``asof(ts)`` ne renvoie que les notes **connues** à ``ts`` : ``created_at <= ts``,
  publication (prudente) ``<= ts`` et version **en vigueur** à ``ts`` (dernière version
  écrite avant ``ts``). Une date seule ``ts`` désigne la fin de cette journée.
"""

from __future__ import annotations

import json
import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import pandas as pd

from .model import (
    Note,
    asof_utc,
    first_tradable_session,
    normalize_targets,
    to_utc,
    utc_now,
)


def fr_num(x: float, decimals: int = 2) -> str:
    """« 0,64 » (virgule décimale)."""
    return f"{x:,.{decimals}f}".replace(",", " ").replace(".", ",")


def fr_signed(x: float, decimals: int = 2) -> str:
    """« +0,64 », « −0,31 »."""
    return ("+" if x >= 0 else "−") + fr_num(abs(x), decimals)

DEFAULT_ROOT = "data/notes"
JOURNAL_NAME = "notes.jsonl"
STORE_FORMAT = 1

#: Champs qu'une mise à jour ne peut pas modifier.
PROTECTED_FIELDS = frozenset({"note_id", "version", "created_at", "recorded_at"})
#: Champs dont la modification relance l'analyse.
CONTENT_FIELDS = frozenset({"title", "text", "targets", "event_type", "stance", "conviction", "published_at", "tags", "url"})

COLUMNS = [
    "note_id", "version", "recorded_at", "created_at", "published_at", "published_precision",
    "first_tradable_session", "author", "source", "url", "title", "text", "targets", "all_targets",
    "event_type", "stance", "conviction", "horizon_days", "tags", "status", "score", "tone", "s_num",
    "materiality", "confidence", "risk_flags", "reading", "analysis", "op",
]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


class StoreLockError(RuntimeError):
    """Le verrou d'écriture n'a pas pu être obtenu."""


class NoteStore:
    """Journal JSONL des notes de l'analyste (voir le module).

    ``root`` : répertoire du journal. La valeur par défaut ``"data/notes"`` désigne le
    répertoire ``data/notes`` du dépôt ; un autre chemin relatif s'entend depuis le
    répertoire courant. Le répertoire n'est créé qu'à la première écriture.
    ``calendar`` : calendrier des séances (``store.load_sessions``) pour
    ``first_tradable_session`` ; à défaut, calendrier du panel puis jours ouvrés.
    """

    def __init__(
        self,
        root: str | Path = DEFAULT_ROOT,
        calendar: Any = None,
        filename: str = JOURNAL_NAME,
        lock_timeout_s: float = 10.0,
        stale_after_s: float = 120.0,
    ):
        root = Path(root)
        if str(root) == DEFAULT_ROOT and not root.is_absolute():
            root = _repo_root() / DEFAULT_ROOT
        self.root = root
        self.path = self.root / filename
        self.lock_path = self.root / (filename + ".lock")
        self.calendar = calendar
        self.lock_timeout_s = lock_timeout_s
        self.stale_after_s = stale_after_s
        self.errors: list[str] = []
        self._cache_key: tuple[int, int] | None = None
        self._records: list[dict[str, Any]] = []
        self._tlock = threading.RLock()

    # ------------------------------------------------------------------
    # Verrou et lecture
    # ------------------------------------------------------------------
    @contextmanager
    def _locked(self) -> Iterator[None]:
        self.root.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self.lock_timeout_s
        with self._tlock:
            while True:
                try:
                    fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                    os.write(fd, f"{os.getpid()} {time.time():.3f}".encode())
                    os.close(fd)
                    break
                except FileExistsError:
                    try:
                        age = time.time() - self.lock_path.stat().st_mtime
                        if age > self.stale_after_s:
                            self.lock_path.unlink(missing_ok=True)  # verrou périmé
                            continue
                    except FileNotFoundError:
                        continue
                    if time.monotonic() > deadline:
                        raise StoreLockError(f"verrou occupé : {self.lock_path}")
                    time.sleep(0.05)
            try:
                yield
            finally:
                self.lock_path.unlink(missing_ok=True)

    def _read(self) -> list[dict[str, Any]]:
        """Toutes les lignes valides du journal (cache invalidé par taille et date)."""
        with self._tlock:
            if not self.path.exists():
                self._records, self._cache_key = [], None
                return []
            st = self.path.stat()
            key = (st.st_mtime_ns, st.st_size)
            if key == self._cache_key:
                return self._records
            recs: list[dict[str, Any]] = []
            errors: list[str] = []
            with self.path.open("r", encoding="utf-8") as fh:
                for i, line in enumerate(fh, start=1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        d = json.loads(line)
                    except json.JSONDecodeError:
                        errors.append(f"ligne {i} illisible (ignorée)")
                        continue
                    if not isinstance(d, dict) or not d.get("note_id"):
                        errors.append(f"ligne {i} sans note_id (ignorée)")
                        continue
                    recs.append(d)
            self._records, self._cache_key, self.errors = recs, key, errors
            return recs

    def _append(self, record: dict[str, Any]) -> None:
        line = json.dumps(record, ensure_ascii=False)
        with self.path.open("ab") as fh:
            if fh.tell() > 0:
                with self.path.open("rb") as rh:
                    rh.seek(-1, os.SEEK_END)
                    if rh.read(1) != b"\n":
                        fh.write(b"\n")  # termine une ligne partielle (elle restera ignorée)
            fh.write(line.encode("utf-8") + b"\n")
            fh.flush()
            os.fsync(fh.fileno())
        self._cache_key = None

    # ------------------------------------------------------------------
    # Versions
    # ------------------------------------------------------------------
    def _versions_raw(self, note_id: str) -> list[dict[str, Any]]:
        recs = [r for r in self._read() if r.get("note_id") == note_id]
        return sorted(recs, key=lambda r: (int(r.get("version") or 1), r.get("recorded_at") or ""))

    def _latest_raw(self) -> dict[str, dict[str, Any]]:
        latest: dict[str, dict[str, Any]] = {}
        for r in self._read():
            nid = r["note_id"]
            cur = latest.get(nid)
            if cur is None or int(r.get("version") or 1) >= int(cur.get("version") or 1):
                latest[nid] = r
        return latest

    def __contains__(self, note_id: object) -> bool:
        return any(r.get("note_id") == note_id for r in self._read())

    def __len__(self) -> int:
        return len({r["note_id"] for r in self._read()})

    def __iter__(self) -> Iterator[Note]:
        for r in self._latest_raw().values():
            yield Note.from_dict(r)

    def ids(self) -> list[str]:
        """Identifiants des notes (ordre d'ajout)."""
        return list(dict.fromkeys(r["note_id"] for r in self._read()))

    # ------------------------------------------------------------------
    # Écriture
    # ------------------------------------------------------------------
    def _with_calendar(self, note: Note) -> None:
        """Recalcule la séance négociable avec le calendrier du journal, sauf valeur imposée."""
        if self.calendar is None or note.published_at is None:
            return
        auto = first_tradable_session(note.published_at, date_only=note.published_precision == "date")
        if note.first_tradable_session is None or note.first_tradable_session == auto:
            note.recompute_first_tradable(self.calendar)

    def _analyze(self, note: Note, panels: dict | None = None) -> dict[str, Any]:
        from .analyze import analyze_note  # import tardif (évite un cycle)

        return analyze_note(note, panels=panels, sessions=self.calendar).to_dict()

    def add(self, note: Note, analyze: bool = False, panels: dict | None = None, now: Any = None) -> str:
        """Ajoute une note (version 1) et renvoie son ``note_id``.

        Idempotent : si ``note_id`` est déjà dans le journal, rien n'est écrit (utiliser
        :meth:`update` pour modifier). ``analyze=True`` calcule l'analyse si elle manque.
        ``now`` (UTC) fixe l'instant d'écriture (tests, reprise d'historique).
        """
        if not isinstance(note, Note):
            raise TypeError("add() attend une Note")
        with self._locked():
            self._cache_key = None
            if note.note_id in self:
                return note.note_id
            rec_at = to_utc(now) or utc_now()
            note = note.copy()
            note.version = 1
            note.recorded_at = rec_at
            self._with_calendar(note)
            if analyze and note.analysis is None:
                note.analysis = self._analyze(note, panels)
            rec = note.to_dict()
            rec["op"] = "add"
            rec["store_format"] = STORE_FORMAT
            self._append(rec)
        return note.note_id

    def add_many(self, notes: list[Note], analyze: bool = False, now: Any = None) -> list[str]:
        """Ajoute plusieurs notes ; renvoie les identifiants (doublons ignorés)."""
        return [self.add(n, analyze=analyze, now=now) for n in notes]

    def update(
        self,
        note_id: str,
        /,
        now: Any = None,
        reanalyze: bool = True,
        panels: dict | None = None,
        **changes: Any,
    ) -> Note:
        """Écrit une **nouvelle version** de la note (l'ancienne est conservée).

        ``note_id``, ``version``, ``created_at`` et ``recorded_at`` ne sont pas modifiables.
        Changer ``published_at`` recalcule ``first_tradable_session`` (sauf valeur fournie).
        Si le contenu change et que la note avait une analyse, l'analyse est recalculée
        (``reanalyze=False`` pour l'éviter). Sans changement effectif, rien n'est écrit.
        """
        bad = PROTECTED_FIELDS & set(changes)
        if bad:
            raise ValueError(f"champs non modifiables : {', '.join(sorted(bad))}")
        if not changes:
            raise ValueError("aucune modification demandée")
        with self._locked():
            self._cache_key = None
            versions = self._versions_raw(note_id)
            if not versions:
                raise KeyError(note_id)
            base = Note.from_dict(versions[-1])
            d = base.to_dict()
            d.update(changes)
            if "published_at" in changes:
                if "first_tradable_session" not in changes:
                    d["first_tradable_session"] = None
                if "published_precision" not in changes:
                    d["published_precision"] = None
            new = Note.from_dict(d)
            new.version = base.version + 1
            new.recorded_at = to_utc(now) or utc_now()
            if "published_at" in changes and "first_tradable_session" not in changes:
                self._with_calendar(new)
            if new.to_dict() | {"version": base.version, "recorded_at": None} == base.to_dict() | {"recorded_at": None}:
                return base  # aucun changement effectif
            content_changed = any(
                getattr(new, k) != getattr(base, k) for k in CONTENT_FIELDS if k in changes
            )
            if "analysis" not in changes and reanalyze and content_changed and base.analysis is not None:
                new.analysis = self._analyze(new, panels)
            rec = new.to_dict()
            rec["op"] = "archive" if changes.get("status") == "archived" and base.status != "archived" else "update"
            rec["store_format"] = STORE_FORMAT
            self._append(rec)
        return new

    def archive(self, note_id: str, reason: str | None = None, now: Any = None) -> Note:
        """Archive la note (nouvelle version ``status="archived"``) ; l'historique est conservé."""
        changes: dict[str, Any] = {"status": "archived"}
        if reason:
            base = self.get(note_id)
            changes["tags"] = list(base.tags) + [f"archive:{reason}"]
        return self.update(note_id, now=now, reanalyze=False, **changes)

    # ------------------------------------------------------------------
    # Lecture
    # ------------------------------------------------------------------
    def get(self, note_id: str, version: int | None = None) -> Note:
        """Dernière version de la note (ou ``version`` donnée) ; ``KeyError`` si absente."""
        versions = self._versions_raw(note_id)
        if not versions:
            raise KeyError(note_id)
        if version is None:
            return Note.from_dict(versions[-1])
        for r in versions:
            if int(r.get("version") or 1) == int(version):
                return Note.from_dict(r)
        raise KeyError(f"{note_id} v{version}")

    def versions(self, note_id: str) -> list[Note]:
        """Toutes les versions d'une note, de la plus ancienne à la plus récente."""
        return [Note.from_dict(r) for r in self._versions_raw(note_id)]

    def frame(self, all_versions: bool = False) -> pd.DataFrame:
        """Tableau des notes (dernières versions, ou toutes les versions)."""
        recs = self._read() if all_versions else list(self._latest_raw().values())
        return _to_frame(recs)

    def list(
        self,
        target: Any = None,
        since: Any = None,
        until: Any = None,
        source: str | None = None,
        status: str | None = "active",
        event_type: str | None = None,
        author: str | None = None,
    ) -> pd.DataFrame:
        """Dernières versions des notes, filtrées.

        ``target`` : code ou désignation libre (« Sonatel », « BRVM 30 »…), ou liste ;
        cherché dans les cibles saisies **et** détectées. ``since`` / ``until`` portent sur
        ``published_at`` (une date seule ``until`` inclut toute la journée). ``status=None``
        renvoie aussi les notes archivées.
        """
        df = self.frame()
        return _filter(df, target, since, until, source, status, event_type, author)

    def asof(self, ts: Any, strict: bool = True, include_archived: bool = False) -> pd.DataFrame:
        """Notes connues à l'instant ``ts``, dans la version en vigueur à cet instant.

        ``strict=True`` (défaut, sans biais d'anticipation) : une note n'apparaît que si
        ``created_at <= ts`` **et** sa publication (fin de journée pour une date seule)
        ``<= ts`` ; la version retenue est la dernière écrite (``recorded_at``) avant ``ts``.
        ``strict=False`` (reconstitution d'historique rétro-collecté) : seule la
        publication compte et la dernière version connue est utilisée ; les corrections
        ultérieures sont alors employées, à réserver aux notes ``auto`` reconstituées.
        """
        t = asof_utc(ts)
        if t is None:
            raise ValueError("asof : date vide")
        by_id: dict[str, list[dict[str, Any]]] = {}
        for r in self._read():
            by_id.setdefault(r["note_id"], []).append(r)
        chosen: list[dict[str, Any]] = []
        for nid, recs in by_id.items():
            recs = sorted(recs, key=lambda r: int(r.get("version") or 1))
            if strict:
                in_force = [r for r in recs if (to_utc(r.get("recorded_at")) or to_utc(r.get("created_at"))) <= t]
                if not in_force:
                    continue
                r = in_force[-1]
            else:
                r = recs[-1]
            created = to_utc(r.get("created_at"))
            pub = _published_effective(r)
            if strict and (created is None or created > t):
                continue
            if pub is None or pub > t:
                continue
            if not include_archived and r.get("status") == "archived":
                continue
            chosen.append(r)
        return _to_frame(chosen)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------
    def export_markdown(
        self,
        path: str | Path,
        target: Any = None,
        status: str | None = "active",
        asof: Any = None,
        title: str = "Notes de l'analyste",
    ) -> Path:
        """Écrit un fichier Markdown lisible (notes triées de la plus récente à la plus ancienne)."""
        df = self.asof(asof) if asof is not None else self.list(target=target, status=status)
        if asof is not None and target is not None:
            df = _filter(df, target, None, None, None, None, None, None)
        lines = [f"# {title}", ""]
        gen = utc_now()
        lines.append(f"Export du {gen:%d/%m/%Y à %Hh%M} UTC — {len(df)} note(s)."
                     + (f" Vue au {asof_utc(asof):%d/%m/%Y %Hh%M} UTC." if asof is not None else ""))
        lines.append("")
        lines.append("> Lecture factuelle, sans garantie : chaque score est assorti d'une confiance ; "
                     "les notes ne pilotent jamais seules le portefeuille.")
        lines.append("")
        if len(df):
            df = df.sort_values("published_at", ascending=False)
        for _, row in df.iterrows():
            r = {k: (None if (not isinstance(v, (list, dict)) and pd.isna(v)) else v) for k, v in row.items()}
            tg = ", ".join(r["all_targets"]) if isinstance(r["all_targets"], list) and r["all_targets"] else "—"
            pub = r["published_at"]
            lines.append(f"## {pub:%d/%m/%Y} — {r['title'] or '(sans titre)'}")
            lines.append("")
            lines.append(f"- **Cibles** : {tg}")
            lines.append(f"- **Type** : {r['event_type'] or '—'} ; **source** : {r['source']}"
                         + (f" ({r['url']})" if r["url"] else "") + f" ; **auteur** : {r['author']}")
            fts = r["first_tradable_session"]
            if fts is not None:
                lines.append(f"- **Négociable à partir du** : {pd.Timestamp(fts):%d/%m/%Y}")
            if isinstance(r["stance"], str) and r["stance"]:
                lines.append(f"- **Avis de l'analyste** : {r['stance']}"
                             + (f", conviction {int(r['conviction'])}/5" if r["conviction"] is not None else "")
                             + f", horizon {int(r['horizon_days'])} séances")
            if r["score"] is not None:
                lines.append(f"- **Score** : {fr_signed(r['score'])} ; matérialité {fr_num(r['materiality'], 2)} ; "
                             f"confiance {fr_num(r['confidence'], 2)}")
            if isinstance(r["risk_flags"], list) and r["risk_flags"]:
                lines.append(f"- **Filtres de risque** : {', '.join(r['risk_flags'])}")
            if r["tags"]:
                lines.append(f"- **Étiquettes** : {', '.join(r['tags'])}")
            lines.append(f"- **Version** : {int(r['version'])} ; identifiant `{r['note_id'][:12]}`")
            if r["reading"]:
                lines.append("")
                lines.append(r["reading"])
            if r["text"]:
                lines.append("")
                body = str(r["text"]).strip()
                if len(body) > 1500:
                    body = body[:1500].rstrip() + " […]"
                lines.extend("> " + ln if ln.strip() else ">" for ln in body.splitlines())
            lines.append("")
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        return out


# ---------------------------------------------------------------------------
# Tableaux
# ---------------------------------------------------------------------------


def _published_effective(r: dict[str, Any]) -> pd.Timestamp | None:
    pub = to_utc(r.get("published_at"))
    if pub is None:
        return None
    if r.get("published_precision") == "date":
        return pub.normalize() + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
    return pub


def _to_frame(recs: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for r in recs:
        an = r.get("analysis") or {}
        targets = list(r.get("targets") or [])
        all_t = list(targets)
        for t in an.get("targets") or []:
            if t not in all_t:
                all_t.append(t)
        rows.append({
            "note_id": r.get("note_id"),
            "version": int(r.get("version") or 1),
            "recorded_at": r.get("recorded_at"),
            "created_at": r.get("created_at"),
            "published_at": r.get("published_at"),
            "published_precision": r.get("published_precision") or "datetime",
            "first_tradable_session": r.get("first_tradable_session"),
            "author": r.get("author"),
            "source": r.get("source"),
            "url": r.get("url") or "",
            "title": r.get("title") or "",
            "text": r.get("text") or "",
            "targets": targets,
            "all_targets": all_t,
            "event_type": r.get("event_type") or an.get("event_type"),
            "stance": r.get("stance"),
            "conviction": r.get("conviction"),
            "horizon_days": r.get("horizon_days"),
            "tags": list(r.get("tags") or []),
            "status": r.get("status") or "active",
            "score": an.get("score"),
            "tone": an.get("tone"),
            "s_num": an.get("s_num"),
            "materiality": an.get("materiality"),
            "confidence": an.get("confidence"),
            "risk_flags": list(an.get("risk_flags") or []),
            "reading": an.get("reading") or "",
            "analysis": an or None,
            "op": r.get("op") or "add",
        })
    df = pd.DataFrame(rows, columns=COLUMNS)
    for c in ("recorded_at", "created_at", "published_at"):
        df[c] = pd.to_datetime(df[c], utc=True, errors="coerce", format="ISO8601")
    df["first_tradable_session"] = pd.to_datetime(df["first_tradable_session"], errors="coerce")
    for c in ("score", "tone", "s_num", "materiality", "confidence"):
        df[c] = pd.to_numeric(df[c], errors="coerce").astype(float)
    df["conviction"] = pd.to_numeric(df["conviction"], errors="coerce")
    if len(df):
        df = df.sort_values(["published_at", "note_id"]).reset_index(drop=True)
    return df


def _filter(
    df: pd.DataFrame,
    target: Any,
    since: Any,
    until: Any,
    source: str | None,
    status: str | None,
    event_type: str | None,
    author: str | None,
) -> pd.DataFrame:
    if not len(df):
        return df
    mask = pd.Series(True, index=df.index)
    if status is not None:
        mask &= df["status"] == status
    if source is not None:
        mask &= df["source"] == source
    if author is not None:
        mask &= df["author"] == author
    if event_type is not None:
        mask &= df["event_type"].astype(str) == str(event_type).upper()
    if since is not None:
        s = to_utc(since)
        mask &= df["published_at"] >= s
    if until is not None:
        u = asof_utc(until)
        mask &= df["published_at"] <= u
    if target is not None:
        wanted = normalize_targets(target if isinstance(target, (list, tuple, set)) else [target])
        if not wanted:
            return df.iloc[0:0]
        mask &= df["all_targets"].apply(lambda ts: any(w in (ts or []) for w in wanted))
    return df[mask].reset_index(drop=True)


__all__ = ["NoteStore", "StoreLockError", "COLUMNS", "PROTECTED_FIELDS"]
