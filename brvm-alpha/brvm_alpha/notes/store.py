"""Journal des notes : ``NoteStore``, fichier JSONL **append-only** (``data/notes/notes.jsonl``).

Principes :
- **une ligne par version** de note ; une modification ou un archivage ajoute une ligne,
  aucune ligne n'est jamais réécrite ni supprimée (historique complet, auditable) ;
- écriture sous **verrou** (``fcntl.flock`` sur ``notes.jsonl.lock``, libéré par le système à la mort
  du processus ; :class:`StoreLockError`, une :class:`~brvm_alpha.erreurs.VerrouOccupe`, au-delà de
  ``lock_timeout_s``, à défaut ``BRVM_ALPHA_ATTENTE_VERROU``, 10 s par défaut) et ``fsync`` après chaque ajout ;
- :meth:`NoteStore.add_unique` : recherche du doublon et ajout **sous le même verrou** (deux saisies
  simultanées de la même note n'en écrivent qu'une) ;
- une ligne illisible est ignorée à la lecture et signalée dans ``errors`` : écriture
  interrompue (y compris au milieu d'un caractère accentué), octets non UTF-8 (ligne
  éditée en Windows-1252), JSON invalide, ou enregistrement mal typé (version non
  entière, date illisible, cibles d'un type inattendu) ; le fichier n'est pas réparé ;
- ``asof(ts)`` ne renvoie que les notes **connues** à ``ts`` : ``created_at <= ts``,
  publication (prudente) ``<= ts`` et version **en vigueur** à ``ts`` (dernière version
  écrite avant ``ts``). Une date seule ``ts`` désigne la fin de cette journée ;
- l'analyse d'une note (``add(analyze=True)``, ``update``) est faite **hors verrou** :
  un texte long ne bloque pas les autres écrivains ;
- un instant d'écriture ``now`` antérieur à l'heure réelle (reprise d'historique) est
  accepté mais **marqué** : étiquette ``reconstitue`` et champ ``backdated``. Une telle
  version n'est jamais retenue par ``asof(strict=True)`` (aucun biais d'anticipation
  par antidatage). En mode horloge simulée (tests, ``model.SIMULATED_CLOCK_ENV``), ``now``
  est accepté tel quel.
"""

from __future__ import annotations

import json
import os
import re
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import pandas as pd

from brvm_alpha import fichiers as _fichiers
from brvm_alpha import paths as _paths
from brvm_alpha.erreurs import CleInconnue, JournalIllisible, SaisieInvalide, VerrouOccupe

from .model import (
    AUTHORS,
    RECONSTRUCTED_TAG,
    SOURCES,
    STATUSES,
    Note,
    _as_list,
    asof_utc,
    first_tradable_session,
    fold,
    is_backdated,
    normalize_targets,
    to_day,
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
    "materiality", "confidence", "risk_flags", "reading", "analysis", "op", "targets_unknown", "backdated",
]

#: Champs comparés pour détecter deux notes de l'analyste différentes sous un même identifiant
#: (le type d'événement et l'horizon sont des saisies de l'analyste : les ignorer en silence
#: perdrait sa correction ; les étiquettes n'en font pas partie).
MANUAL_CONTENT_FIELDS = ("title", "text", "targets", "targets_unknown", "event_type", "stance", "conviction",
                         "horizon_days", "published_at", "url")


#: Fenêtre (jours depuis la saisie) dans laquelle une note de l'analyste de même contenu est un doublon.
DUPLICATE_WINDOW_DAYS = 30.0


def _norm_text(value: Any) -> str:
    return re.sub(r"\s+", " ", fold(str(value or ""))).strip()


class NoteConflictError(SaisieInvalide):
    """Un identifiant existe déjà dans le journal avec un contenu différent (utiliser ``update``)."""


def _validate_record(d: dict[str, Any]) -> str | None:
    """Contrôle (et normalise en place) un enregistrement du journal ; motif du rejet ou ``None``.

    Une ligne JSON valide mais mal typée (éditée à la main) ne doit pas rendre tout le
    journal illisible : elle est rejetée, et signalée dans ``NoteStore.errors``.
    """
    try:
        v = d.get("version")
        v = 1 if v in (None, "") else int(v)
        if isinstance(d.get("version"), float) and d["version"] != int(d["version"]):
            return "version non entière"
        if v < 1:
            return "version < 1"
        d["version"] = v
    except (TypeError, ValueError):
        return f"version illisible ({d.get('version')!r})"
    for k in ("created_at", "published_at", "recorded_at"):
        val = d.get(k)
        if val in (None, ""):
            continue
        try:
            to_utc(val)
        except (TypeError, ValueError):
            return f"{k} illisible ({val!r})"
    if d.get("first_tradable_session") not in (None, ""):
        try:
            to_day(d["first_tradable_session"])
        except (TypeError, ValueError):
            return f"first_tradable_session illisible ({d['first_tradable_session']!r})"
    for k in ("targets", "tags", "targets_unknown"):
        val = d.get(k)
        if val is None:
            continue
        if isinstance(val, str):
            d[k] = _as_list(val)
        elif isinstance(val, list):
            d[k] = [str(x) for x in val if x is not None and str(x).strip()]
        else:
            return f"{k} d'un type inattendu ({type(val).__name__})"
    if d.get("author") not in (None, "") and str(d["author"]).strip().lower() not in AUTHORS:
        return f"author inconnu ({d['author']!r})"
    if d.get("source") not in (None, "") and str(d["source"]).strip().lower() not in SOURCES:
        return f"source inconnue ({d['source']!r})"
    if d.get("status") not in (None, "") and str(d["status"]).strip().lower() not in STATUSES:
        return f"status inconnu ({d['status']!r})"
    if d.get("analysis") is not None and not isinstance(d["analysis"], dict):
        return "analysis n'est pas un objet"
    # Enregistrement réduit à son identifiant (ligne éditée à la main ou tronquée) : jamais une note active
    # « (titre vide) » sans date (revue produit du 22/11/2026).
    if not str(d.get("title") or "").strip() and not str(d.get("text") or "").strip():
        return "ni titre ni texte"
    if d.get("published_at") in (None, "") and d.get("created_at") in (None, ""):
        return "date de publication absente (published_at, created_at)"
    if d.get("recorded_at") in (None, "") and d.get("created_at") in (None, ""):
        return "date d'enregistrement absente (recorded_at, created_at)"
    return None


def _is_backdated_record(r: dict[str, Any]) -> bool:
    """Version écrite avec un instant antidaté (reprise d'historique) ?"""
    return bool(r.get("backdated")) or RECONSTRUCTED_TAG in (r.get("tags") or [])


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


class StoreLockError(RuntimeError, VerrouOccupe):
    """Le verrou d'écriture n'a pas pu être obtenu (code de sortie 4)."""


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
        lock_timeout_s: float | None = None,
        stale_after_s: float = 120.0,
    ):
        root = Path(root)
        if str(root) == DEFAULT_ROOT and not root.is_absolute():
            # ``<dépôt>/data/notes``, ou ``<BRVM_ALPHA_DONNEES>/notes`` si la variable est posée.
            root = _paths.NOTES_DIR
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
        """Verrou d'écriture : fil d'exécution (``RLock``) puis processus (``fcntl.flock``), réentrant."""
        _paths.verifier_ecriture(self.path)
        self.root.mkdir(parents=True, exist_ok=True)
        # Attente : ``lock_timeout_s`` s'il est donné, sinon BRVM_ALPHA_ATTENTE_VERROU (10 s par défaut), comme
        # tous les verrous du moteur.
        attente = _fichiers.delai_verrou(self.lock_timeout_s)
        if not self._tlock.acquire(timeout=attente):
            raise StoreLockError(f"verrou occupé : {self.lock_path} (autre écriture en cours dans ce processus)")
        try:
            try:
                ctx = _fichiers.verrou(self.lock_path, attente=attente, quoi="journal des notes")
                ctx.__enter__()
            except VerrouOccupe as exc:
                raise StoreLockError(str(exc)) from None
            try:
                yield
            finally:
                ctx.__exit__(None, None, None)
        finally:
            self._tlock.release()

    def _read(self) -> list[dict[str, Any]]:
        """Toutes les lignes valides du journal (cache invalidé par taille et date)."""
        with self._tlock:
            try:
                st = self.path.stat()
            except FileNotFoundError:  # journal absent : aucune note (ce n'est pas une erreur)
                self._records, self._cache_key = [], None
                return []
            except OSError as exc:
                raise self._illisible(exc) from exc
            key = (st.st_mtime_ns, st.st_size)
            if key == self._cache_key:
                return self._records
            recs: list[dict[str, Any]] = []
            errors: list[str] = []
            try:
                fh = self.path.open("rb")
            except FileNotFoundError:  # retiré entre-temps
                self._records, self._cache_key = [], None
                return []
            except OSError as exc:  # dossier à la place du fichier, droits…
                raise self._illisible(exc) from exc
            # Lecture binaire, décodage ligne par ligne : une coupure au milieu d'un
            # caractère multi-octet ou une ligne en Windows-1252 n'invalide qu'elle-même.
            with fh:
                for i, raw in enumerate(fh, start=1):
                    try:
                        line = raw.decode("utf-8").strip()
                    except UnicodeDecodeError:
                        errors.append(f"ligne {i} : octets non UTF-8 (écriture interrompue ou autre encodage), ignorée")
                        continue
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
                    why = _validate_record(d)
                    if why:
                        errors.append(f"ligne {i} invalide : {why} (ignorée)")
                        continue
                    recs.append(d)
            self._records, self._cache_key, self.errors = recs, key, errors
            return recs

    def _illisible(self, exc: OSError) -> JournalIllisible:
        return JournalIllisible(
            f"journal des notes illisible : {self.path} ({type(exc).__name__} : {exc.strerror or exc}). Sans lui, "
            "les vetos et les achats bloqués par une note seraient ignorés : la commande s'arrête. Rétablir le fichier "
            "(ou le retirer s'il n'y a aucune note).")

    def lisible(self) -> tuple[bool, str | None]:
        """``(True, None)`` si le journal se lit (ou n'existe pas), sinon ``(False, motif)`` ; ne lève jamais."""
        try:
            self._read()
        except JournalIllisible as exc:
            return False, str(exc)
        return True, None

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
        """Séance négociable avec le calendrier du journal, jamais avant la règle de coupure.

        Valeur vide ou valeur automatique (calendrier par défaut) : recalculée avec le
        calendrier du journal. Valeur imposée : conservée si elle n'est pas antérieure à la
        séance calculée, sinon remplacée par celle-ci (``max``).
        """
        if self.calendar is None or note.published_at is None:
            return
        date_only = note.published_precision == "date"
        computed = first_tradable_session(note.published_at, sessions=self.calendar, date_only=date_only)
        auto = first_tradable_session(note.published_at, date_only=date_only)
        cur = note.first_tradable_session
        if cur is None or cur == auto or (computed is not None and cur < computed):
            note.first_tradable_session = computed

    def _analyze(self, note: Note, panels: dict | None = None) -> dict[str, Any]:
        from .analyze import analyze_note  # import tardif (évite un cycle)

        return analyze_note(note, panels=panels, sessions=self.calendar).to_dict()

    def _stamp(self, note: Note, rec: dict[str, Any], now: Any) -> None:
        """Instant d'écriture : ``recorded_at`` (``now`` ou heure réelle), ``written_at`` (heure réelle).

        Un ``now`` antérieur à l'heure réelle (hors mode horloge simulée) marque la version
        comme reconstituée : étiquette ``reconstitue`` et ``backdated: true``.
        """
        real = utc_now()
        rec_at = to_utc(now) or real
        note.recorded_at = rec_at
        rec["recorded_at"] = rec_at.isoformat()
        rec["written_at"] = real.isoformat()
        if is_backdated(rec_at, real):
            rec["backdated"] = True
            if RECONSTRUCTED_TAG not in note.tags:
                note.tags.append(RECONSTRUCTED_TAG)
            rec["tags"] = list(note.tags)

    def _check_conflict(self, note: Note) -> None:
        """Une note de l'analyste ne doit pas être ignorée en silence sous un identifiant existant."""
        if note.author != "analyste":
            return
        versions = self._versions_raw(note.note_id)
        if not versions:
            return
        new = note.to_dict()
        diff: list[str] = []
        for r in versions:  # identique à l'une des versions : simple doublon
            cur = Note.from_dict(r).to_dict()
            diff = [k for k in MANUAL_CONTENT_FIELDS if cur.get(k) != new.get(k)]
            if not diff:
                return
        if diff:
            raise NoteConflictError(
                f"l'identifiant {note.note_id[:12]} existe déjà avec un contenu différent ({', '.join(diff)}) : "
                "utiliser update() pour écrire une nouvelle version, ou créer une note distincte."
            )

    def find_duplicate(self, note: Note, max_age_days: float = DUPLICATE_WINDOW_DAYS, now: Any = None) -> str | None:
        """Identifiant d'une note de l'analyste **active** et récente de même contenu, ou ``None``.

        Même contenu : mêmes cibles (reconnues et non reconnues), titre et texte normalisés (casse,
        accents, espaces), avis, conviction et adresse. La date de publication n'est pas comparée :
        sans date saisie, elle vaut l'instant de la saisie et l'identifiant change à chaque envoi, si
        bien que la même note saisie deux fois comptait double (inclinaison et composante « notes »
        des indices : recette du 22/11/2026). ``max_age_days`` : âge maximal (jours) de la note
        existante, compté depuis sa saisie. Le journal n'est pas modifié ; c'est à l'appelant (ligne
        de commande, interface) de refuser ou de faire confirmer le doublon.
        """
        if note.author != "analyste":
            return None
        ref = to_utc(now) or utc_now()

        def key(d: dict[str, Any]) -> tuple:
            conv = d.get("conviction")
            return (tuple(sorted(str(t) for t in (d.get("targets") or []))),
                    tuple(sorted(str(t) for t in (d.get("targets_unknown") or []))),
                    _norm_text(d.get("title")), _norm_text(d.get("text")), d.get("stance") or None,
                    None if conv is None or conv != conv else int(conv), str(d.get("url") or "").strip())

        want = key(note.to_dict())
        best: tuple[str, str] | None = None
        for nid, r in self._latest_raw().items():
            if r.get("author") != "analyste" or (r.get("status") or "active") != "active":
                continue
            if key(Note.from_dict(r).to_dict()) != want:
                continue
            created = to_utc(r.get("created_at")) or to_utc(r.get("recorded_at"))
            if created is not None and abs((ref - created).total_seconds()) > max_age_days * 86400.0:
                continue
            stamp = str(r.get("created_at") or "")
            if best is None or stamp > best[1]:
                best = (nid, stamp)
        return best[0] if best else None

    def add(self, note: Note, analyze: bool = False, panels: dict | None = None, now: Any = None) -> str:
        """Ajoute une note (version 1) et renvoie son ``note_id``.

        Idempotent : si ``note_id`` est déjà dans le journal avec le même contenu, rien n'est
        écrit (utiliser :meth:`update` pour modifier). Pour une note de l'analyste dont
        l'identifiant existe avec un **contenu différent**, :class:`NoteConflictError` est
        levée (aucune saisie n'est perdue en silence). ``analyze=True`` calcule l'analyse
        si elle manque, **hors verrou**. ``now`` (UTC) fixe l'instant d'écriture (tests,
        reprise d'historique) ; antérieur à l'heure réelle, il marque la note
        « reconstituée » (exclue des vues strictes).
        """
        if not isinstance(note, Note):
            raise TypeError("add() attend une Note")
        self._cache_key = None
        if note.note_id in self:  # lecture sans verrou : évite une analyse inutile
            self._check_conflict(note)
            return note.note_id
        note = note.copy()
        note.version = 1
        self._with_calendar(note)
        if analyze and note.analysis is None:
            note.analysis = self._analyze(note, panels)  # hors verrou (texte long, autres écrivains)
        with self._locked():
            self._cache_key = None
            if note.note_id in self:  # ajoutée entre-temps par un autre écrivain
                self._check_conflict(note)
                return note.note_id
            rec = note.to_dict()
            self._stamp(note, rec, now)
            rec["op"] = "add"
            rec["store_format"] = STORE_FORMAT
            self._append(rec)
        return note.note_id

    def add_unique(self, note: Note, analyze: bool = False, panels: dict | None = None, now: Any = None,
                   max_age_days: float = DUPLICATE_WINDOW_DAYS, force: bool = False) -> tuple[Note, bool, str | None]:
        """Ajout **atomique** d'une note de l'analyste : doublon cherché et note écrite sous le même verrou.

        Renvoie ``(note, cree, doublon_id)`` :

        - même identifiant déjà au journal : ``(note existante, False, son identifiant)`` (contenu
          différent : :class:`NoteConflictError`, comme :meth:`add`) ;
        - doublon de contenu (:meth:`find_duplicate` : même cible, titre, texte, avis, conviction et
          adresse, note active saisie depuis moins de ``max_age_days`` jours) et ``force`` faux :
          ``(note existante, False, identifiant du doublon)`` ; rien n'est écrit ;
        - sinon la note est écrite : ``(note écrite, True, None)``.

        La date de publication fournie (``published_at``, saisie « publiée le ») est gardée telle
        quelle. L'analyse (``analyze=True``) est faite hors verrou ; ``now`` comme pour :meth:`add`.
        """
        if not isinstance(note, Note):
            raise TypeError("add_unique() attend une Note")
        note = note.copy()
        note.version = 1
        self._with_calendar(note)
        if analyze and note.analysis is None and note.note_id not in self:
            note.analysis = self._analyze(note, panels)  # hors verrou (texte long, autres écrivains)
        with self._locked():
            self._cache_key = None
            if note.note_id in self:
                self._check_conflict(note)
                return self.get(note.note_id), False, note.note_id
            dup = None if force else self.find_duplicate(note, max_age_days=max_age_days, now=now)
            if dup:
                return self.get(dup), False, dup
            rec = note.to_dict()
            self._stamp(note, rec, now)
            rec["op"] = "add"
            rec["store_format"] = STORE_FORMAT
            self._append(rec)
            self._cache_key = None
        return self.get(note.note_id), True, None

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
        Changer ``published_at`` recalcule ``first_tradable_session`` (sauf valeur fournie,
        qui ne peut pas précéder la séance calculée). Si le contenu change et que la note
        avait une analyse, l'analyse est recalculée **hors verrou** (``reanalyze=False``
        pour l'éviter) ; si une autre version est écrite entre-temps, la mise à jour est
        reprise sur cette nouvelle base. Sans changement effectif, rien n'est écrit.
        """
        bad = PROTECTED_FIELDS & set(changes)
        if bad:
            raise SaisieInvalide(f"champs non modifiables : {', '.join(sorted(bad))}")
        if not changes:
            raise SaisieInvalide("aucune modification demandée")
        for _attempt in range(5):
            self._cache_key = None
            versions = self._versions_raw(note_id)
            if not versions:
                raise CleInconnue(note_id)
            base = Note.from_dict(versions[-1])
            d = base.to_dict()
            if "tags" not in changes:
                # L'étiquette « reconstitue » qualifie une écriture, pas la note : elle n'est
                # pas héritée par une version écrite à l'heure réelle.
                d["tags"] = [t for t in d.get("tags") or [] if t != RECONSTRUCTED_TAG]
            d.update(changes)
            if "published_at" in changes:
                if "first_tradable_session" not in changes:
                    d["first_tradable_session"] = None
                if "published_precision" not in changes:
                    d["published_precision"] = None
            new = Note.from_dict(d)
            new.version = base.version + 1
            self._with_calendar(new)
            base_cmp = base.to_dict() | {"recorded_at": None}
            base_cmp["tags"] = [t for t in base_cmp.get("tags") or [] if t != RECONSTRUCTED_TAG]
            if new.to_dict() | {"version": base.version, "recorded_at": None} == base_cmp:
                return base  # aucun changement effectif
            content_changed = any(
                getattr(new, k) != getattr(base, k) for k in CONTENT_FIELDS if k in changes
            )
            if "analysis" not in changes and reanalyze and content_changed and base.analysis is not None:
                new.analysis = self._analyze(new, panels)  # hors verrou
            with self._locked():
                self._cache_key = None
                latest = self._versions_raw(note_id)
                if int(latest[-1].get("version") or 1) != base.version:
                    continue  # une autre version a été écrite entre-temps : on recommence
                rec = new.to_dict()
                self._stamp(new, rec, now)
                rec["op"] = "archive" if changes.get("status") == "archived" and base.status != "archived" else "update"
                rec["store_format"] = STORE_FORMAT
                self._append(rec)
            return new
        raise StoreLockError(f"mise à jour de {note_id} abandonnée : journal modifié en continu par d'autres écrivains")

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
            raise CleInconnue(note_id)
        if version is None:
            return Note.from_dict(versions[-1])
        for r in versions:
            if int(r.get("version") or 1) == int(version):
                return Note.from_dict(r)
        raise CleInconnue(f"{note_id} v{version}")

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
        ``<= ts`` ; la version retenue est la dernière écrite (``recorded_at``) avant ``ts``,
        hors versions **reconstituées** (écrites avec un ``now`` antidaté). Cette vue dit ce
        qui était *connu* à ``ts`` ; la séance où une note peut *agir* (coupure de 09h00
        appliquée à l'instant de connaissance) est calculée par ``signals.notes_asof``.
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
                in_force = [r for r in recs if not _is_backdated_record(r)
                            and (to_utc(r.get("recorded_at")) or to_utc(r.get("created_at"))) <= t]
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
        _fichiers.ecrire_atomique(out, "\n".join(lines).rstrip() + "\n")
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
        if not isinstance(an, dict):
            an = {}
        targets = [str(t) for t in _as_list(r.get("targets"))]
        all_t = list(targets)
        for t in _as_list(an.get("targets")):
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
            "tags": [str(t) for t in _as_list(r.get("tags"))],
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
            "targets_unknown": [str(t) for t in _as_list(r.get("targets_unknown"))],
            "backdated": bool(r.get("backdated")),
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


__all__ = ["NoteStore", "StoreLockError", "NoteConflictError", "COLUMNS", "PROTECTED_FIELDS"]
