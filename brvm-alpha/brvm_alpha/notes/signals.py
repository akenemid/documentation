"""Signaux datés tirés des notes : scores par cible, surcouches manuelles bornées, filtres R1-R10.

Contrat : ``docs/ARCHITECTURE.md``, section « Module Notes de l'analyste » (``notes/signals.py``).

Principes
---------
- **Point-in-time strict** (``strict=True``, défaut) : une décision prise à la séance J
  (signaux calculés avant 09h00 UTC, document 07 §2.3 point 2) n'utilise que ce que le
  système **connaissait** avant la coupure de J. La séance où une note agit est donc
  ``first_tradable_session(max(publication prudente, created_at, recorded_at))`` —
  coupure 09h00 UTC appliquée à l'**instant de connaissance**, et non à la seule
  publication : une note publiée à 08h00 mais saisie à 20h00 n'agit qu'à J+1. De même, la
  version en vigueur à J est la dernière dont l'écriture précède la coupure de J, et un
  archivage écrit pendant la séance ne prend effet qu'à la séance suivante. Les versions
  reconstituées (écrites avec un ``now`` antidaté, étiquette ``reconstitue``) sont
  ignorées. ``Δ`` est compté depuis cette séance effective (colonne
  ``first_tradable_session`` des sorties ; la valeur fondée sur la seule publication
  reste dans ``first_tradable_session_published``).
- ``strict=False`` (reconstitution d'historique rétro-collecté) : seule la publication
  compte (``first_tradable_session`` stockée), dernière version connue.
- **Score de nouvelles** (document 07 §3.4-6, signal S5 §6.5, spécification §S5) :
  ``S(t) = Σ_k s_k · w_k · d_k(t)``, où ``s_k`` est le score de la note (``analyze``, dans
  [−1, 1]), ``w_k`` le poids de propagation (1 pour la cible elle-même) et
  ``d_k(t) = exp(−Δ_k/τ)`` la décroissance, ``Δ_k`` étant le nombre de séances écoulées
  depuis la séance effective, avec **τ = 10 séances par défaut** (document 07 :
  ``decay_tau_sessions: 10``). Le paramètre ``half_life`` (demi-vie, ``2^(−Δ/h)``) reste
  disponible : sa valeur par défaut :data:`DEFAULT_HALF_LIFE` vaut ``10·ln 2 ≈ 6,93``
  séances, ce qui reproduit exactement ``exp(−Δ/10)`` ; ``tau`` est prioritaire s'il est donné.
- **Propagation** (paramètres explicites, :data:`DEFAULT_PROPAGATION`) : une note sur un
  pays ou un secteur se répercute sur les titres concernés avec un poids 0,5, une note sur
  le marché avec 0,25, une note sur un indice sur ses constituants avec 0,25, une note sur
  un thème sur les sociétés exposées (``entities.theme_exposure``, documents 05 §10.1 et
  06b §7.5) avec ``0,25 × signe`` : le score d'une note de thème est lu comme le sens
  d'évolution du facteur, le signe donne l'effet d'une hausse du facteur sur la société
  (0 = ambigu, pas de propagation).
  Pour une même note, un titre reçoit le **plus grand** des poids applicables (pas de double
  compte). La composition (secteur, compartiment, indice) est celle de la séance
  ``first_tradable_session`` de la note.
- **Cibles d'une note** : les cibles saisies (``targets``) font foi ; à défaut, les cibles
  détectées par l'analyse ; si un symbole est détecté, les cibles plus larges détectées
  (pays, secteur, thème, marché, indice) ne sont que du contexte et ne propagent pas.
- **Surcouches manuelles** (:func:`manual_overlays`) : ``veto`` (note manuelle étiquetée
  « veto », ou filtre R3 / R9 actif), ``tilt`` (``signe(stance) × conviction/5 × 0,5``
  écart-type, borné à ±0,5, valable ``horizon_days`` séances), ``flags`` (R1-R10 actifs,
  durées du document 07 §6.6).

Deux instants, deux modes (:class:`NotesMoment`)
-------------------------------------------------
Une évaluation manipule deux instants distincts : la **date des cours** (dernier BOC, paramètre
``asof``) et l'**instant de connaissance des notes**.

- **Mode historique** (défaut de toutes les fonctions : ``known_at=None``) : dates passées,
  backtests, diagnostics, validation. Règle stricte ci-dessus, évaluée à la date des cours ;
  aucune anticipation. Rien ne change pour un appel programmatique existant.
- **Mode direct** (``known_at=<instant UTC>``, passé explicitement par le seul chemin « direct »
  de la ligne de commande, de l'interface et du rapport) : l'outil tourne le soir ou le week-end
  pour la séance suivante et doit tenir compte de tout ce qui est connu **au moment où il
  tourne**. La **séance d'application** est la première séance après la date des cours, ou la
  suivante si sa coupure de 09h00 UTC est déjà passée : ``max(séance qui suit le dernier BOC,
  première séance négociable de known_at)`` (:func:`application_session`). Sont en vigueur les
  notes dont une version est écrite au plus tard à ``known_at``, non archivées, publiées au plus
  tard à ``known_at`` (une note datée de demain n'agit pas) et dont la première séance négociable
  est au plus tard la séance d'application. L'âge ``Δ`` (décroissance, durée des filtres, horizon
  d'un avis) est compté jusqu'à la séance d'application, depuis :

  * la première séance négociable de la **publication** pour une note collectée automatiquement
    (l'information est publique et datée par sa source ; la date de collecte n'est qu'un artefact
    de l'outil : une alerte sur résultats de juin collectée en novembre a bien cinq mois) ;
  * ``first_tradable_session(max(publication prudente, saisie))`` pour une note de l'analyste
    (son avis vaut à partir du moment où il l'exprime, comme en mode strict).

  La règle de coupure de 09h00 UTC est inchangée ; une version reconstituée (``now`` antidaté)
  ne compte que si ``known_at`` n'est pas antérieur à l'heure réelle.

Les notes ne pilotent jamais seules le portefeuille : le poids du score S5 reste nul tant
que l'IC walk-forward n'a pas dépassé 0,05 sur au moins 3 années (document 07 §6.5) ;
:func:`notes_panel` fournit le panel date × symbole pour cette mesure. Aucune sortie n'est
une garantie : ce sont des lectures factuelles, chiffrées, avec leur confiance.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd

from brvm_alpha.reference import country_of

from .model import (
    DEFAULT_HORIZON_DAYS,
    FIXED_HOLIDAYS,
    HISTORICAL_SYMBOLS,
    KNOWN_SYMBOLS,
    NEWS_CUTOFF_UTC,
    RECONSTRUCTED_TAG,
    RISK_FLAGS,
    Note,
    SessionCalendar,
    asof_utc,
    default_calendar,
    default_panel_dir,
    fold,
    is_backdated,
    normalize_targets,
    stance_sign,
    target_kind,
    target_label,
    to_day,
)
from .store import COLUMNS as STORE_COLUMNS
from .store import NoteStore, _to_frame

# ---------------------------------------------------------------------------
# Paramètres
# ---------------------------------------------------------------------------

#: Constante de temps du score de nouvelles, en séances : ``exp(−Δ/τ)`` avec τ = 10
#: (document 07 §3.4 règle 6, §6.5 S5, ``decay_tau_sessions: 10`` ; spécification §S5).
DEFAULT_TAU = 10.0
#: Demi-vie équivalente à τ = 10 séances : ``10·ln 2 ≈ 6,93`` (``2^(−Δ/h) = exp(−Δ/τ)``).
DEFAULT_HALF_LIFE = DEFAULT_TAU * math.log(2.0)
#: Poids de propagation d'une note vers les titres concernés (choix de conception, non
#: validés : à mesurer par l'IC walk-forward avant tout usage pondéré).
DEFAULT_PROPAGATION: dict[str, float] = {
    "country": 0.5,
    "sector": 0.5,
    "market": 0.25,
    "index": 0.25,
    "theme": 0.25,
}
#: En dessous de ce facteur de décroissance, une note est considérée comme éteinte
#: (≈ 69 séances pour τ = 10).
MIN_DECAY = 1e-3
#: Borne de la surcouche manuelle (en écarts-types du score multifacteur).
TILT_MAX_SD = 0.5
#: Conviction supposée quand l'analyste donne un avis sans conviction.
DEFAULT_CONVICTION = 3

#: Types d'événements qui valent « comptes suivants » (fin de R3, fin anticipée de R9).
ACCOUNTS_EVENTS = frozenset({"RES_ANNUAL", "RES_S1"})
#: Types d'événements qui valent « rapport publié » (fin de R7).
REPORT_EVENTS = frozenset({"RES_ANNUAL", "RES_S1", "ACT_Q1", "ACT_Q3"})

#: Filtres de risque (document 07 §6.6) : durée en séances et actions.
#: ``sessions`` : durée fixe ; ``until`` : événement qui y met fin ; ``fallback`` : durée
#: retenue quand l'événement de fin n'est pas observable (choix de conception, signalé).
RISK_RULES: dict[str, dict[str, Any]] = {
    "R1": {"until": "resumption", "buffer": 5, "block_buys": True, "liquidity_haircut": 0.10,
           "action": "aucun achat ; alerte sur les positions ; décote de liquidité de 10 %",
           "duration": "jusqu'à la reprise de cotation + 5 séances"},
    "R2": {"sessions": 60, "block_buys": True, "governance_penalty": -1.0,
           "action": "aucun nouvel achat ; −1 en gouvernance", "duration": "60 séances"},
    "R3": {"until": "next_accounts", "block_buys": True, "exclude": True, "veto": True,
           "action": "exclusion des achats ; révision manuelle", "duration": "jusqu'aux comptes suivants"},
    "R4": {"sessions": 120, "max_weight_mult": 0.5,
           "action": "poids maximal × 0,5", "duration": "120 séances"},
    "R5": {"until": "ex_date", "fallback": 60, "block_buys": True,
           "action": "aucun achat avant le détachement des droits",
           "duration": "jusqu'au détachement des droits (60 séances à défaut de date)"},
    "R6": {"until": "offer_result", "fallback": 120, "freeze_auto": True,
           "action": "gel des signaux automatiques ; analyse manuelle de la prime",
           "duration": "jusqu'au résultat de l'offre (120 séances à défaut)"},
    "R7": {"until": "next_report", "alert": True, "quality_penalty_red": -0.5,
           "action": "alerte « retard » ; −0,5 en qualité au niveau rouge", "duration": "jusqu'à la publication"},
    "R8": {"sessions": 5, "check_adjustment": True,
           "action": "contrôle du facteur d'ajustement avant tout signal", "duration": "5 séances"},
    "R9": {"sessions": 60, "until": "next_accounts", "block_buys": True, "veto": True, "quality_penalty": -1.0,
           "disable": ("S1", "S4"),
           "action": "aucun achat ; S1 et S4 désactivés ; −1 en qualité",
           "duration": "60 séances (fin anticipée aux comptes suivants)"},
    "R10": {"sessions": 120, "alert": True, "quality_penalty": -0.5, "lookback_days": 120,
            "action": "alerte « alerte sur résultats manquante » ; −0,5 en qualité", "duration": "120 séances"},
}

#: Exposition des thèmes, table de repli utilisée seulement si ``entities.theme_exposure``
#: est indisponible (source de vérité : ``entities.THEME_EXPOSURES``, documents 05 §10.1 et
#: 06b §7.5). Entrées : (cible, signe de l'effet d'une **hausse du facteur**) ; signe 0 =
#: effet ambigu (pas de propagation du score).
THEME_EXPOSURE: dict[str, tuple[tuple[str, int], ...]] = {
    "CAOUTCHOUC": (("SPHC", 1), ("SOGC", 1)),
    "HUILE_PALME": (("PALC", 0), ("SOGC", 1)),
    "SUCRE": (("SCRC", 0),),
    "CACAO": (("FTSC", 1), ("SDSC", 1), ("NTLC", 0)),
    "CAJOU": (("FTSC", 1), ("SDSC", 1)),
    "PETROLE": (("SMBC", 1), ("TTLC", 0), ("TTLS", 0), ("SHEC", 0)),
    "ENERGIE": (("SNTS", -1), ("ORAC", -1), ("ONTBF", -1), ("SCRC", -1)),
    "GAZ": (("CIEC", 0),),
    "OR": (("BOAM", 1), ("BOABF", 1), ("CBIBF", 1), ("ONTBF", 1)),
    "COTON": (("UNXC", 0),),
    "MOBILE_MONEY": (("SNTS", -1), ("ORAC", -1), ("ONTBF", -1)),
    "SECURITE": (("ONTBF", -1), ("ORAC", -1), ("SNTS", -1)),
    "LOGISTIQUE": (("SPHC", -1), ("CABC", -1)),
    "TAUX_BCEAO": (("SECT:FIN", -1),),
}


def theme_exposures(code: str) -> list[tuple[str, int]]:
    """Cibles exposées à un thème et signe de l'effet d'une hausse du facteur.

    Convention de propagation : le score d'une note de thème (et l'avis « haussier » d'une
    note manuelle sur un thème) est lu comme le **sens d'évolution du facteur** (hausse du
    cours du cacao, des taux directeurs, du coût de l'énergie…). La contribution propagée à
    un titre vaut ``score × signe × poids`` ; un signe nul (effet ambigu : marges encadrées,
    effets de stock) ne propage rien. Les thèmes sans exposition documentée (inflation,
    élections…) ne se propagent pas : cibler alors le pays ou le marché.
    """
    key = str(code or "").upper()
    key = key[6:] if key.startswith("THEME:") else key
    try:
        from . import entities

        fn = getattr(entities, "theme_exposure", None)
        if callable(fn):
            out = []
            for e in fn(key) or []:
                t = e.get("target") if isinstance(e, Mapping) else None
                if t:
                    out.append((str(t), int(e.get("sign", 0) or 0)))
            return out
    except Exception:  # pragma: no cover - module en cours de modification
        pass
    return list(THEME_EXPOSURE.get(key, ()))


_RELATION = {"country": "pays", "sector": "secteur", "market": "marché", "index": "indice", "theme": "thème"}


# ---------------------------------------------------------------------------
# Mise en forme (copie locale : ce module ne dépend pas de l'import d'analyze)
# ---------------------------------------------------------------------------


def _fr_num(x: float, decimals: int = 2) -> str:
    return f"{x:,.{decimals}f}".replace(",", " ").replace(".", ",")


def _fr_signed(x: float, decimals: int = 2) -> str:
    return ("+" if x >= 0 else "−") + _fr_num(abs(x), decimals)


def _fr_date(ts: Any) -> str:
    return pd.Timestamp(ts).strftime("%d/%m/%Y")


# ---------------------------------------------------------------------------
# Calendrier : compteur de séances vectorisé
# ---------------------------------------------------------------------------


def _as_calendar(calendar: Any) -> SessionCalendar:
    if isinstance(calendar, SessionCalendar):
        return calendar
    if calendar is None:
        return default_calendar()
    if isinstance(calendar, pd.DataFrame) and "date" not in calendar.columns and calendar.index.name == "date":
        calendar = calendar.reset_index()
    return SessionCalendar(calendar)


class SessionClock:
    """Compteur de séances : ``count(j)`` = nombre de séances ``<= j``.

    Construit sur le calendrier :class:`~brvm_alpha.notes.model.SessionCalendar` (séances
    connues, prolongées par les jours ouvrés hors fériés fixes dans les lacunes et hors du
    panel). ``between(a, b)`` = nombre de séances dans ``]a, b]``, identique à
    ``SessionCalendar.sessions_between`` mais vectorisé.
    """

    def __init__(self, calendar: Any = None):
        self.calendar = _as_calendar(calendar)
        self._lo: np.datetime64 | None = None
        self._cum: np.ndarray = np.array([], dtype=np.int64)
        self._sess: np.ndarray = np.array([], dtype=bool)
        self._offset = 0  # les comptes restent absolus quand la plage est étendue vers le passé

    def _is_session_vec(self, days: np.ndarray) -> np.ndarray:
        cal = self.calendar
        dts = cal.dates
        ts = pd.DatetimeIndex(days)
        open_wd = (ts.dayofweek < 5) & ~pd.Index(list(zip(ts.month, ts.day))).isin(list(FIXED_HOLIDAYS))
        if len(dts) == 0:
            return np.asarray(open_wd)
        unknown = (days < dts[0]) | (days > dts[-1])
        for lo, hi in cal.gaps:
            unknown |= (days > lo) & (days < hi)
        known = np.isin(days, dts)
        return np.where(unknown, np.asarray(open_wd), known)

    def _hi(self) -> np.datetime64:
        return self._lo + np.timedelta64(len(self._cum) - 1, "D")

    def _ensure(self, lo: np.datetime64, hi: np.datetime64) -> None:
        if self._lo is not None and lo >= self._lo and hi <= self._hi():
            return
        old_lo = self._lo
        old_first = int(self._cum[0]) + self._offset if old_lo is not None else 0
        cur_lo = old_lo if old_lo is not None else lo
        cur_hi = self._hi() if old_lo is not None else hi
        new_lo = min(lo - np.timedelta64(30, "D"), cur_lo)
        new_hi = max(hi + np.timedelta64(400, "D"), cur_hi)
        days = np.arange(new_lo, new_hi + np.timedelta64(1, "D"), dtype="datetime64[D]")
        sess = self._is_session_vec(days)
        cum = np.cumsum(sess.astype(np.int64))
        if old_lo is not None:
            self._offset = old_first - int(cum[int((old_lo - new_lo).astype(np.int64))])
        self._lo, self._sess, self._cum = new_lo, sess, cum

    @staticmethod
    def _days(values: Any) -> np.ndarray:
        idx = pd.DatetimeIndex(pd.to_datetime(pd.Index(np.atleast_1d(values))))
        if idx.tz is not None:
            idx = idx.tz_convert("UTC").tz_localize(None)
        return idx.normalize().values.astype("datetime64[D]")

    def count(self, days: Any) -> np.ndarray:
        """Nombre de séances ``<= j`` pour chaque jour (tableau d'entiers)."""
        d = self._days(days)
        if not len(d):
            return np.array([], dtype=np.int64)
        self._ensure(d.min(), d.max())
        return self._cum[(d - self._lo).astype(np.int64)] + self._offset

    def between(self, a: Any, b: Any) -> int:
        """Nombre de séances dans ``]a, b]`` (0 si ``b <= a``)."""
        ca, cb = self.count([a, b])
        return int(max(cb - ca, 0))

    def first_tradable(self, instants: Any, cutoff: Any = NEWS_CUTOFF_UTC) -> np.ndarray:
        """Première séance négociable de chaque instant (vectorisé ; ``NaT`` si vide).

        Même règle que :func:`brvm_alpha.notes.model.first_tradable_session` pour un
        instant précis : avant ``cutoff`` (09h00 UTC) un jour de séance, la séance du jour ;
        sinon la séance suivante. Renvoie un tableau ``datetime64[ns]`` (minuit, sans fuseau).
        """
        idx = pd.DatetimeIndex(pd.to_datetime(pd.Index(np.atleast_1d(instants)), utc=True))
        out = np.full(len(idx), np.datetime64("NaT", "ns"), dtype="datetime64[ns]")
        valid = ~idx.isna()
        if not valid.any():
            return out
        tv = idx[valid].tz_convert("UTC").tz_localize(None)
        days = tv.normalize().values.astype("datetime64[D]")
        tod = (tv - tv.normalize()).values
        before = tod < np.timedelta64(cutoff.hour * 3600 + cutoff.minute * 60, "s")
        self._ensure(days.min(), days.max() + np.timedelta64(40, "D"))
        i = (days - self._lo).astype(np.int64)
        target = np.where(before & self._sess[i], self._cum[i], self._cum[i] + 1)
        while int(self._cum[-1]) < int(target.max()):  # pragma: no cover - garde-fou
            self._ensure(days.min(), self._hi() + np.timedelta64(400, "D"))
            i = (days - self._lo).astype(np.int64)
            target = np.where(before & self._sess[i], self._cum[i], self._cum[i] + 1)
        pos = np.searchsorted(self._cum, target, side="left")
        out[np.asarray(valid)] = (self._lo + pos.astype("timedelta64[D]")).astype("datetime64[ns]")
        return out

    def nth_session(self, day: Any, n: int) -> pd.Timestamp:
        """``n``-ième séance après ``day`` (``n >= 1``) ; ``n = 0`` : ``day`` s'il est une séance, sinon la suivante."""
        d = self._days([day])[0]
        self._ensure(d, d + np.timedelta64(int(2 * n + 30), "D"))
        i = int((d - self._lo).astype(np.int64))
        base = int(self._cum[i])
        target = base + n if n >= 1 else base + (0 if self._sess[i] else 1)
        while int(self._cum[-1]) < target:
            self._ensure(d, self._hi() + np.timedelta64(400, "D"))
            i = int((d - self._lo).astype(np.int64))
            target = int(self._cum[i]) + (n if n >= 1 else (0 if self._sess[i] else 1))
        pos = int(np.searchsorted(self._cum, target, side="left"))
        return pd.Timestamp(self._lo + np.timedelta64(pos, "D"))


_CLOCKS: dict[int, tuple[Any, SessionClock]] = {}


def _clock(calendar: Any) -> SessionClock:
    """Compteur mis en cache par objet calendrier (le défaut est partagé)."""
    if isinstance(calendar, SessionClock):
        return calendar
    key = id(calendar)
    hit = _CLOCKS.get(key)
    if hit is not None and hit[0] is calendar:
        return hit[1]
    clk = SessionClock(calendar)
    if len(_CLOCKS) > 16:
        _CLOCKS.clear()
    _CLOCKS[key] = (calendar, clk)
    return clk


# ---------------------------------------------------------------------------
# Deux instants : date des cours et instant de connaissance des notes
# ---------------------------------------------------------------------------

MODE_DIRECT = "direct"
MODE_HISTORICAL = "historique"


@dataclass(frozen=True)
class NotesMoment:
    """Les deux instants d'une évaluation des notes (voir l'en-tête du module).

    ``prices_date`` : date des cours (dernier BOC, minuit sans fuseau) ; ``known_at`` : instant
    de connaissance des notes (UTC), ``None`` en mode historique ; ``session`` : séance à
    laquelle les notes sont appliquées (mode direct : séance qui suit le dernier BOC, ou la
    suivante si la coupure de 09h00 UTC est passée ; mode historique : la date des cours) ;
    ``mode`` : ``"direct"`` ou ``"historique"``.
    """

    prices_date: pd.Timestamp
    session: pd.Timestamp
    known_at: pd.Timestamp | None = None
    mode: str = MODE_HISTORICAL

    @property
    def direct(self) -> bool:
        return self.mode == MODE_DIRECT

    def describe(self) -> str:
        """« Notes connues au JJ/MM/AAAA HH:MM UTC, appliquées à la séance du JJ/MM/AAAA »."""
        if self.direct and self.known_at is not None:
            return (f"Notes connues au {self.known_at:%d/%m/%Y %H:%M} UTC, appliquées à la séance du "
                    f"{_fr_date(self.session)}")
        return (f"Notes en mode historique (règle stricte, sans anticipation : connues avant la coupure de 09h00 UTC "
                f"de la séance du {_fr_date(self.session)})")

    def to_dict(self) -> dict[str, Any]:
        return {"mode": self.mode, "date_des_cours": self.prices_date, "connues_au": self.known_at,
                "seance_application": self.session}


def knowledge_instant(value: Any) -> pd.Timestamp | None:
    """Instant de connaissance (UTC) d'une saisie : une date seule désigne la fin de cette journée.

    Un ``pd.Timestamp`` avec fuseau est pris tel quel (minuit compris) ; un :class:`NotesMoment`
    rend son instant.
    """
    if value is None:
        return None
    if isinstance(value, NotesMoment):
        return value.known_at
    if isinstance(value, pd.Timestamp) and value.tzinfo is not None:
        return value.tz_convert("UTC")
    return asof_utc(value)


def application_session(prices_date: Any, known_at: Any, calendar: Any = None) -> pd.Timestamp:
    """Séance d'application des notes en mode direct.

    ``max(première séance après la date des cours, première séance négociable de known_at)`` :
    la séance qui suit le dernier BOC, ou la suivante si sa coupure de 09h00 UTC est déjà passée
    (règle de :func:`brvm_alpha.notes.model.first_tradable_session`, inchangée). Hors du
    calendrier connu, les jours ouvrés hors fériés fixes font foi (hypothèse).
    """
    day = to_day(prices_date)
    k = knowledge_instant(known_at)
    if day is None or k is None:
        raise ValueError("application_session : date des cours et instant de connaissance requis")
    clock = _clock(calendar)
    nxt = clock.nth_session(day, 1)
    ft = pd.Timestamp(clock.first_tradable([k])[0])
    return max(pd.Timestamp(nxt), ft)


def notes_moment(asof: Any, known_at: Any = None, calendar: Any = None) -> NotesMoment:
    """Instants d'une évaluation : mode direct si ``known_at`` est donné, historique sinon."""
    if isinstance(known_at, NotesMoment):
        return known_at
    t = asof_utc(asof)
    if t is None:
        raise ValueError("asof : date vide")
    day = t.tz_localize(None).normalize()
    k = knowledge_instant(known_at)
    if k is None:
        return NotesMoment(prices_date=day, session=day, known_at=None, mode=MODE_HISTORICAL)
    return NotesMoment(prices_date=day, session=application_session(day, k, calendar), known_at=k, mode=MODE_DIRECT)


def decay_factor(elapsed: Any, half_life: float | None = DEFAULT_HALF_LIFE, tau: float | None = None) -> np.ndarray:
    """Facteur de décroissance : ``exp(−Δ/τ)`` si ``tau`` est donné, sinon ``2^(−Δ/h)``.

    Par défaut (``half_life = 10·ln 2``), c'est la formule du document 07 : ``exp(−Δ/10)``.
    ``half_life=None`` sans ``tau`` : τ = :data:`DEFAULT_TAU`.
    """
    e = np.asarray(elapsed, dtype=float)
    if tau is None and (half_life is None or half_life == DEFAULT_HALF_LIFE):
        tau = DEFAULT_TAU  # valeur par défaut : formule exacte du document 07
    if tau is not None:
        if tau <= 0:
            raise ValueError("tau doit être > 0")
        return np.exp(-e / float(tau))
    if half_life <= 0:
        raise ValueError("half_life doit être > 0")
    return np.power(0.5, e / float(half_life))


def _decay_horizon(half_life: float | None, tau: float | None, min_decay: float) -> int:
    """Nombre de séances au-delà duquel le facteur de décroissance passe sous ``min_decay``."""
    if tau is None and (half_life is None or half_life == DEFAULT_HALF_LIFE):
        tau = DEFAULT_TAU
    if tau is not None:
        return int(math.ceil(tau * math.log(1.0 / min_decay))) + 1
    return int(math.ceil(half_life * math.log2(1.0 / min_decay))) + 1


# ---------------------------------------------------------------------------
# Univers : composition des cibles larges, point-in-time
# ---------------------------------------------------------------------------

_EQ_COLUMNS = ["date", "symbol", "name", "sector", "compartment", "value", "volume", "status", "close"]


@lru_cache(maxsize=2)
def _default_equities_cached(path: str, mtime_ns: int) -> pd.DataFrame:
    df = pd.read_parquet(path)
    cols = [c for c in _EQ_COLUMNS if c in df.columns]
    df = df[cols].copy()
    df["date"] = pd.to_datetime(df["date"])
    return df


def default_equities() -> pd.DataFrame | None:
    """Colonnes utiles de ``data/panel/equities.parquet`` (lecture mise en cache), ou ``None``."""
    path = default_panel_dir() / "equities.parquet"
    if not path.exists():
        return None
    return _default_equities_cached(str(path), path.stat().st_mtime_ns)


def _equities_long(equities: Any) -> pd.DataFrame | None:
    if equities is None:
        return None
    if isinstance(equities, (str, Path)):
        p = Path(equities)
        p = p / "equities.parquet" if p.is_dir() else p
        return _default_equities_cached(str(p), p.stat().st_mtime_ns)
    if isinstance(equities, Mapping):
        equities = equities.get("equities")
        if equities is None:
            return None
    df = equities
    if "symbol" not in df.columns or "date" not in df.columns:
        df = df.reset_index()
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    return df


class Universe:
    """Composition des cibles larges à une date (``equities`` au format long de ``load_equities``).

    Sans panel : univers des symboles connus (``reference``), secteurs de la classification
    2025 (``reference.SECTOR_2025``) et compartiment Prestige 2026 (avis 001-2026).
    """

    PRESTIGE_2026 = frozenset("ECOC NTLC ONTBF ORAC PALC SGBC SIBC SMBC SNTS SPHC TTLC TTLS".split())

    def __init__(self, equities: Any = "default"):
        if isinstance(equities, str) and equities == "default":
            eq = default_equities()
        else:
            eq = _equities_long(equities)
        self.equities = eq
        self._dates = np.array([], dtype="datetime64[ns]")
        self._groups: dict[np.datetime64, np.ndarray] = {}
        if eq is not None and len(eq):
            eq = eq.sort_values(["date", "symbol"]).reset_index(drop=True)
            self.equities = eq
            d = eq["date"].values
            self._dates, starts = np.unique(d, return_index=True)
            ends = np.r_[starts[1:], len(eq)]
            self._bounds = dict(zip(self._dates, zip(starts, ends)))
        self._cache: dict[tuple[str, Any], tuple[list[str], str]] = {}

    def snapshot(self, day: Any) -> pd.DataFrame | None:
        """Lignes de la dernière séance ``<= day`` (``None`` sans panel ou avant le panel)."""
        if self.equities is None or not len(self._dates):
            return None
        d = np.datetime64(pd.Timestamp(to_day(day)), "ns")
        i = int(np.searchsorted(self._dates, d, side="right")) - 1
        if i < 0:
            return None
        a, b = self._bounds[self._dates[i]]
        return self.equities.iloc[a:b]

    def listed(self, day: Any) -> list[str]:
        snap = self.snapshot(day)
        if snap is None:
            return sorted(KNOWN_SYMBOLS - set(HISTORICAL_SYMBOLS))
        return sorted(snap["symbol"].unique())

    def members(self, code: str, day: Any) -> tuple[list[str], str]:
        """Symboles couverts par ``code`` à la date (et la méthode utilisée)."""
        key = (code, pd.Timestamp(to_day(day)))
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        out = self._members(code, key[1])
        self._cache[key] = out
        return out

    def _members(self, code: str, day: pd.Timestamp) -> tuple[list[str], str]:
        from brvm_alpha import reference as ref

        kind = target_kind(code)
        if kind == "symbol":
            return [code], "titre"
        listed = self.listed(day)
        if kind == "market":
            return listed, "toutes les actions cotées"
        if kind == "country":
            c = code[5:]
            return [s for s in listed if country_of(s) == c], f"titres du pays {c} (reference.country_of)"
        if kind == "sector":
            sec = code[5:]
            snap = self.snapshot(day)
            if snap is not None and "sector" in snap.columns and (snap["sector"] == sec).any():
                return sorted(snap.loc[snap["sector"] == sec, "symbol"].unique()), "secteur du BOC à la date"
            return [s for s in listed if ref.SECTOR_2025.get(s) == sec], "secteur BRVM 2025 (reference)"
        if kind == "theme":
            out: list[str] = []
            for item, sign in theme_exposures(code):
                if sign == 0:
                    continue
                syms = self.members(item, day)[0] if target_kind(item) != "symbol" else [item]
                out.extend(s for s in syms if s in listed and s not in out)
            return sorted(out), "exposition du thème (entities.theme_exposure, signe non nul)"
        if kind == "index":
            from . import index_eval  # import tardif (index_eval importe ce module)

            members, method = index_eval.index_constituents(code, day, equities=self.equities, universe=self)
            return list(members), method
        return [], "inconnu"


# ---------------------------------------------------------------------------
# Lecture des notes
# ---------------------------------------------------------------------------


def _ensure_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for c in STORE_COLUMNS:
        if c not in df.columns:
            df[c] = None
    for c in ("recorded_at", "created_at", "published_at"):
        df[c] = pd.to_datetime(df[c], utc=True, errors="coerce", format="mixed")
    df["first_tradable_session"] = pd.to_datetime(df["first_tradable_session"], errors="coerce")
    if getattr(df["first_tradable_session"].dt, "tz", None) is not None:
        df["first_tradable_session"] = df["first_tradable_session"].dt.tz_convert("UTC").dt.tz_localize(None)
    df["first_tradable_session"] = df["first_tradable_session"].dt.normalize()
    df["version"] = pd.to_numeric(df["version"], errors="coerce").fillna(1).astype(int)
    df["status"] = df["status"].fillna("active")
    df["published_precision"] = df["published_precision"].fillna("datetime")
    for c in ("tags", "targets", "targets_unknown"):
        df[c] = df[c].apply(lambda v: list(v) if isinstance(v, (list, tuple, np.ndarray)) else
                            ([] if v is None or (isinstance(v, float) and math.isnan(v)) else [v]))
    return df


def _published_effective(df: pd.DataFrame) -> pd.Series:
    pub = df["published_at"]
    end = pub.dt.normalize() + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
    return pub.where(df["published_precision"] != "date", end)


def all_versions(store_or_frame: Any) -> pd.DataFrame:
    """Toutes les versions des notes (``NoteStore``, ``DataFrame`` du journal ou liste de ``Note``)."""
    if isinstance(store_or_frame, NoteStore):
        return _ensure_columns(store_or_frame.frame(all_versions=True))
    if isinstance(store_or_frame, pd.DataFrame):
        return _ensure_columns(store_or_frame)
    if store_or_frame is None:
        return _ensure_columns(_to_frame([]))
    items = list(store_or_frame)
    recs = []
    for n in items:
        if isinstance(n, Note):
            recs.append(n.to_dict())
        elif isinstance(n, Mapping):
            recs.append(Note.from_dict(dict(n)).to_dict())
        else:
            raise TypeError("attendu : NoteStore, DataFrame ou liste de Note")
    return _ensure_columns(_to_frame(recs))


def notes_asof(store_or_frame: Any, asof: Any, strict: bool = True, calendar: Any = None, *,
               known_at: Any = None) -> pd.DataFrame:
    """Notes connues et négociables à ``asof`` (une ligne par note, version en vigueur).

    ``known_at`` (mot-clé, défaut ``None`` = **mode historique**, comportement inchangé) : instant
    de connaissance des notes du **mode direct**. ``asof`` est alors la date des cours (dernier
    BOC) ; les notes sont celles connues à ``known_at`` dont la première séance négociable est au
    plus tard la séance d'application (:func:`application_session`). Voir l'en-tête du module
    (âge compté depuis la publication pour une note automatique, depuis la saisie pour une note
    de l'analyste). ``strict`` est sans effet en mode direct.

    ``strict=True`` (défaut) : règle de connaissance du module (voir l'en-tête) —
    version en vigueur = dernière version non reconstituée écrite avant la coupure de la
    séance (et avant ``asof`` si c'est un instant), note active, publication prudente
    ``<= asof``, et séance effective ``first_tradable_session(max(publication prudente,
    created_at, recorded_at de la 1re version connue))`` ``<= asof``. La colonne
    ``first_tradable_session`` contient cette séance effective ; ``known_at`` l'instant de
    connaissance ; ``first_tradable_session_published`` la séance fondée sur la seule
    publication.

    ``strict=False`` : ``NoteStore.asof(strict=False)`` (dernière version, publication
    ``<= asof``), puis ``first_tradable_session <= asof``.

    ``calendar`` : calendrier des séances (défaut : celui du ``NoteStore``, sinon le
    calendrier du panel).
    """
    t = asof_utc(asof)
    if t is None:
        raise ValueError("asof : date vide")
    day = t.tz_localize(None).normalize()
    if known_at is not None:
        if calendar is None and isinstance(store_or_frame, NoteStore):
            calendar = store_or_frame.calendar
        clock = _clock(calendar)
        m = notes_moment(day, known_at, clock)
        return _select_direct(all_versions(store_or_frame), m.known_at, m.session, clock)
    if strict:
        if calendar is None and isinstance(store_or_frame, NoteStore):
            calendar = store_or_frame.calendar
        df = all_versions(store_or_frame)
        return _select_strict(df, t, day, _clock(calendar))
    if isinstance(store_or_frame, NoteStore):
        df = _ensure_columns(store_or_frame.asof(asof, strict=False))
    else:
        df = _select_in_force(all_versions(store_or_frame), t, strict=False)
    if not len(df):
        return df
    fts = df["first_tradable_session"]
    out = df[fts.notna() & (fts <= day)].reset_index(drop=True)
    return out.assign(first_tradable_session_published=out["first_tradable_session"],
                      known_at=_published_effective(out))


def _is_reconstructed(tags: Any) -> bool:
    return isinstance(tags, (list, tuple)) and RECONSTRUCTED_TAG in tags


def _knowledge(df: pd.DataFrame, clock: SessionClock) -> pd.DataFrame:
    """Colonnes de connaissance par version : ``_known`` (max(created_at, recorded_at)),
    ``_fts_known`` (séance à partir de laquelle la version est connue avant la coupure),
    ``_eligible`` (version utilisable en mode strict) et ``_first_known`` (par note)."""
    rec = df["recorded_at"].fillna(df["created_at"])
    created = df["created_at"].fillna(rec)
    known = pd.concat([created, rec], axis=1).max(axis=1)
    known = pd.to_datetime(known, utc=True)
    recon = df["tags"].apply(_is_reconstructed) if "tags" in df.columns else pd.Series(False, index=df.index)
    if "backdated" in df.columns:
        recon = recon | df["backdated"].apply(lambda v: v is True or (isinstance(v, (int, np.integer)) and v == 1))
    eligible = known.notna() & df["created_at"].notna() & ~recon
    fts_known = pd.Series(clock.first_tradable(known.values), index=df.index)
    first_known = known.where(eligible).groupby(df["note_id"]).transform("min")
    return df.assign(_rec=rec, _known=known, _fts_known=fts_known, _eligible=eligible, _first_known=first_known)


def _effective_session(df: pd.DataFrame, clock: SessionClock) -> tuple[pd.Series, pd.Series]:
    """Séance effective (mode strict) et instant de connaissance de chaque ligne.

    ``max(first_tradable_session stockée, first_tradable_session(max(publication prudente,
    première connaissance de la note)))``.
    """
    pub = _published_effective(df)
    anchor = pd.concat([pub, df["_first_known"]], axis=1).max(axis=1)
    anchor = pd.to_datetime(anchor, utc=True)
    fts_k = pd.Series(clock.first_tradable(anchor.values), index=df.index)
    stored = df["first_tradable_session"]
    eff = pd.concat([stored, fts_k], axis=1).max(axis=1)
    return pd.to_datetime(eff), anchor


def _select_strict(df: pd.DataFrame, t: pd.Timestamp, day: pd.Timestamp, clock: SessionClock) -> pd.DataFrame:
    if not len(df):
        return df.assign(first_tradable_session_published=df["first_tradable_session"], known_at=df["created_at"])
    df = _knowledge(df, clock)
    ok = df["_eligible"] & (df["_rec"] <= t) & (df["_fts_known"] <= day)
    cand = df[ok]
    if not len(cand):
        return _drop_tmp(cand).assign(first_tradable_session_published=cand["first_tradable_session"],
                                      known_at=cand["created_at"])
    cand = cand.sort_values(["note_id", "version"])
    out = cand.groupby("note_id", sort=False).tail(1)
    eff, anchor = _effective_session(out, clock)
    pub = _published_effective(out)
    keep = pub.notna() & (pub <= t) & (out["status"] != "archived") & eff.notna() & (eff <= day)
    out = out.assign(first_tradable_session_published=out["first_tradable_session"], known_at=anchor,
                     first_tradable_session=eff)
    out = _drop_tmp(out[keep])
    if len(out):
        out = out.sort_values(["published_at", "note_id"])
    return out.reset_index(drop=True)


def _select_direct(df: pd.DataFrame, k: pd.Timestamp, session: pd.Timestamp, clock: SessionClock) -> pd.DataFrame:
    """Notes en vigueur en mode direct : connues à ``k``, négociables au plus tard à ``session``.

    Version retenue : la dernière écrite au plus tard à ``k`` (une version reconstituée ne compte
    que si ``k`` n'est pas antérieur à l'heure réelle : on ne peut pas prouver qu'elle était
    connue avant). Séance effective (colonne ``first_tradable_session``) : celle de la
    publication pour une note automatique ; ``max(publication, saisie)`` pour une note de
    l'analyste. ``first_tradable_session_published`` garde la séance de la publication,
    ``known_at`` la première connaissance de la note.
    """
    if not len(df):
        return df.assign(first_tradable_session_published=df["first_tradable_session"], known_at=df["created_at"])
    rec = df["recorded_at"].fillna(df["created_at"])
    created = df["created_at"].fillna(rec)
    known = pd.to_datetime(pd.concat([created, rec], axis=1).max(axis=1), utc=True)
    usable = known.notna() & (known <= k)
    if is_backdated(k):  # instant passé : une version antidatée n'est pas une preuve de connaissance
        recon = df["tags"].apply(_is_reconstructed)
        if "backdated" in df.columns:
            recon = recon | df["backdated"].apply(lambda v: v is True or (isinstance(v, (int, np.integer)) and v == 1))
        usable &= ~recon
    cand = df[usable].assign(_known=known[usable])
    if not len(cand):
        return cand.drop(columns=["_known"]).assign(first_tradable_session_published=cand["first_tradable_session"],
                                                     known_at=cand["created_at"])
    cand = cand.assign(_first_known=cand.groupby("note_id")["_known"].transform("min"))
    out = cand.sort_values(["note_id", "version"]).groupby("note_id", sort=False).tail(1)
    pub = _published_effective(out)
    stored = out["first_tradable_session"]
    by_pub = pd.Series(clock.first_tradable(pub.values), index=out.index)
    stored = stored.where(stored.notna(), by_pub)
    anchor = pd.to_datetime(pd.concat([pub, out["_first_known"]], axis=1).max(axis=1), utc=True)
    by_entry = pd.Series(clock.first_tradable(anchor.values), index=out.index)
    manual = out["author"] == "analyste"
    eff = stored.where(~manual, pd.concat([stored, by_entry], axis=1).max(axis=1))
    eff = pd.to_datetime(eff)
    keep = (out["published_at"].notna() & (out["published_at"] <= k) & (out["status"] != "archived")
            & eff.notna() & (eff <= session))
    out = out.assign(first_tradable_session_published=stored, known_at=out["_first_known"],
                     first_tradable_session=eff)
    out = out[keep].drop(columns=["_known", "_first_known"])
    if len(out):
        out = out.sort_values(["published_at", "note_id"])
    return out.reset_index(drop=True)


def _drop_tmp(df: pd.DataFrame) -> pd.DataFrame:
    return df.drop(columns=[c for c in ("_rec", "_known", "_fts_known", "_eligible", "_first_known") if c in df.columns])


def _select_in_force(df: pd.DataFrame, t: pd.Timestamp, strict: bool) -> pd.DataFrame:
    if not len(df):
        return df
    rec = df["recorded_at"].fillna(df["created_at"])
    keep = []
    for _, g in df.assign(_rec=rec).groupby("note_id", sort=False):
        g = g.sort_values("version")
        if strict:
            g = g[(g["_rec"] <= t) & ~g["tags"].apply(_is_reconstructed)]
            if not len(g):
                continue
        keep.append(g.index[-1])
    out = df.loc[keep]
    pub = _published_effective(out)
    mask = pub.notna() & (pub <= t) & (out["status"] != "archived")
    if strict:
        mask &= out["created_at"].notna() & (out["created_at"] <= t)
    return out[mask].reset_index(drop=True)


_ANALYSIS_CACHE: dict[tuple[str, int, str], dict[str, Any]] = {}


def _row_note(row: Mapping[str, Any]) -> Note:
    d = {k: row.get(k) for k in ("note_id", "created_at", "published_at", "first_tradable_session", "author",
                                 "source", "url", "title", "text", "targets", "event_type", "stance", "conviction",
                                 "horizon_days", "tags", "status", "version", "published_precision", "recorded_at",
                                 "targets_unknown")}
    for k, v in list(d.items()):
        if not isinstance(v, (list, tuple, dict)) and v is not None and pd.isna(v):
            d[k] = None
    if d.get("horizon_days") is None:
        d["horizon_days"] = DEFAULT_HORIZON_DAYS
    d["targets"] = list(d.get("targets") or [])
    d["tags"] = list(d.get("tags") or [])
    d["targets_unknown"] = list(d.get("targets_unknown") or [])
    return Note.from_dict(d)


def note_analysis(row: Mapping[str, Any], calendar: Any = None) -> dict[str, Any]:
    """Analyse d'une ligne du journal (celle du journal si elle existe, sinon calculée et mise en cache)."""
    an = row.get("analysis")
    if isinstance(an, dict) and an:
        return an
    key = (str(row.get("note_id")), int(row.get("version") or 1), str(row.get("title") or "")[:80])
    hit = _ANALYSIS_CACHE.get(key)
    if hit is not None:
        return hit
    from .analyze import analyze_note  # import tardif

    res = analyze_note(_row_note(row), sessions=None if calendar is None else _as_calendar(calendar)).to_dict()
    if len(_ANALYSIS_CACHE) > 20000:
        _ANALYSIS_CACHE.clear()
    _ANALYSIS_CACHE[key] = res
    return res


def _finite(x: Any) -> float | None:
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def note_score_value(row: Mapping[str, Any], calendar: Any = None) -> tuple[float, dict[str, Any]]:
    """Score ``s_k`` d'une note (dans [−1, 1]) et son analyse."""
    an = note_analysis(row, calendar)
    s = _finite(an.get("score"))
    return (0.0 if s is None else max(-1.0, min(1.0, s))), an


def effective_targets(row: Mapping[str, Any], analysis: Mapping[str, Any] | None = None) -> list[tuple[str, str]]:
    """Cibles retenues pour une note : ``[(code, origine)]``, origine ``"saisie"`` ou ``"détectée"``.

    Les cibles saisies font foi. À défaut, cibles détectées ; si un symbole est détecté,
    les cibles plus larges détectées ne sont que du contexte (elles ne propagent pas).
    Une note de l'analyste dont les cibles saisies sont **toutes inconnues**
    (``targets_unknown``, faute de frappe ou titre hors liste) n'a aucune cible : son avis
    n'est jamais reporté sur des sociétés détectées dans le texte qu'elle ne visait pas.
    """
    manual = normalize_targets(list(row.get("targets") or []))
    if manual:
        return [(t, "saisie") for t in manual]
    unknown = row.get("targets_unknown")
    if isinstance(unknown, (list, tuple, np.ndarray)) and len(unknown) and row.get("author") == "analyste":
        return []
    an = analysis if analysis is not None else (row.get("analysis") or {})
    detected = normalize_targets(list((an or {}).get("targets") or row.get("all_targets") or []))
    if any(target_kind(t) == "symbol" for t in detected):
        detected = [t for t in detected if target_kind(t) == "symbol"]
    return [(t, "détectée") for t in detected]


def _target_weights(
    targets: list[tuple[str, str]],
    day: pd.Timestamp,
    universe: Universe,
    propagation: Mapping[str, float],
) -> dict[str, tuple[float, str, str]]:
    """Poids par cible atteinte : ``{cible: (poids, cible source, relation)}``.

    Poids 1 pour les cibles de la note ; sinon poids de propagation de la nature de la cible
    source (signé pour un thème : ``poids × signe``). Pour un même titre, le poids de plus
    grande valeur absolue l'emporte (pas de double compte).
    """
    out: dict[str, tuple[float, str, str]] = {}
    for code, _origin in targets:
        out[code] = (1.0, code, "directe")

    def offer(sym: str, w: float, src: str, rel: str) -> None:
        cur = out.get(sym)
        if cur is None or abs(w) > abs(cur[0]):
            out[sym] = (w, src, rel)

    for code, _origin in targets:
        kind = target_kind(code)
        if kind == "symbol":
            continue
        w = float(propagation.get(kind, 0.0))
        if w == 0:
            continue
        if kind == "theme":
            listed = set(universe.listed(day))
            for item, sign in theme_exposures(code):
                if sign == 0:
                    continue
                syms = [item] if target_kind(item) == "symbol" else universe.members(item, day)[0]
                for s in syms:
                    if s in listed:
                        offer(s, w * sign, code, _RELATION["theme"])
            continue
        syms, _method = universe.members(code, day)
        for s in syms:
            offer(s, w, code, _RELATION.get(kind, kind))
    return out


# ---------------------------------------------------------------------------
# Scores datés
# ---------------------------------------------------------------------------

CONTRIBUTION_COLUMNS = [
    "target", "kind", "note_id", "version", "source_target", "relation", "weight", "first_tradable_session",
    "sessions_elapsed", "decay", "note_score", "contribution", "author", "source", "event_type", "title",
    "materiality", "confidence", "risk_flags", "stance", "conviction",
]


def note_contributions(
    store_or_frame: Any,
    asof: Any,
    half_life: float = DEFAULT_HALF_LIFE,
    calendar: Any = None,
    propagation: Mapping[str, float] | None = None,
    equities: Any = "default",
    strict: bool = True,
    tau: float | None = None,
    min_decay: float = MIN_DECAY,
    universe: Universe | None = None,
    known_at: Any = None,
) -> pd.DataFrame:
    """Contributions élémentaires ``s_k · w_k · d_k(asof)`` : une ligne par (cible atteinte, note).

    Voir :func:`note_scores` pour les paramètres. ``relation`` vaut ``directe`` pour la cible
    de la note elle-même, sinon ``pays``, ``secteur``, ``marché``, ``indice`` ou ``thème``.
    ``known_at`` : instant de connaissance du mode direct (:func:`notes_asof`) ; la décroissance
    est alors comptée jusqu'à la séance d'application.
    """
    prop = dict(DEFAULT_PROPAGATION if propagation is None else propagation)
    t = asof_utc(asof)
    if t is None:
        raise ValueError("asof : date vide")
    day = t.tz_localize(None).normalize()
    clock = _clock(calendar)
    if known_at is not None:
        known_at = notes_moment(day, known_at, clock)
        day = known_at.session
    df = notes_asof(store_or_frame, asof, strict=strict, calendar=calendar, known_at=known_at)
    if not len(df):
        return pd.DataFrame(columns=CONTRIBUTION_COLUMNS)
    uni = universe if universe is not None else Universe(equities)
    elapsed = clock.count(day)[0] - clock.count(df["first_tradable_session"].values)
    dec = decay_factor(np.maximum(elapsed, 0), half_life, tau)
    rows: list[dict[str, Any]] = []
    for (_, r), e, d in zip(df.iterrows(), elapsed, dec):
        if d < min_decay:
            continue
        row = r.to_dict()
        s, an = note_score_value(row, calendar)
        tg = effective_targets(row, an)
        if not tg:
            continue
        fts = pd.Timestamp(row["first_tradable_session"])
        for target, (w, src, rel) in _target_weights(tg, fts, uni, prop).items():
            rows.append({
                "target": target, "kind": target_kind(target), "note_id": row["note_id"], "version": int(row["version"]),
                "source_target": src, "relation": rel, "weight": w, "first_tradable_session": fts,
                "sessions_elapsed": int(max(e, 0)), "decay": float(d), "note_score": s,
                "contribution": s * w * float(d), "author": row.get("author"), "source": row.get("source"),
                "event_type": row.get("event_type") or an.get("event_type"), "title": row.get("title") or "",
                "materiality": _finite(an.get("materiality")), "confidence": _finite(an.get("confidence")),
                "risk_flags": list(an.get("risk_flags") or []), "stance": row.get("stance"),
                "conviction": _finite(row.get("conviction")),
            })
    out = pd.DataFrame(rows, columns=CONTRIBUTION_COLUMNS)
    return out


SCORE_COLUMNS = [
    "kind", "label", "score", "score_direct", "score_propagated", "score_manual", "score_auto", "n_notes",
    "n_direct", "n_propagated", "n_manual", "n_auto", "mean_confidence", "last_session", "last_note_id",
    "last_title", "last_event_type",
]


def note_scores(
    store_or_frame: Any,
    asof: Any,
    half_life: float = DEFAULT_HALF_LIFE,
    calendar: Any = None,
    propagation: Mapping[str, float] | None = None,
    equities: Any = "default",
    strict: bool = True,
    tau: float | None = None,
    min_decay: float = MIN_DECAY,
    propagate: bool = True,
    known_at: Any = None,
) -> pd.DataFrame:
    """Score de nouvelles par cible à la date ``asof`` : ``Σ s_k · w_k · exp(−Δ_k/τ)`` (τ = 10).

    - ``store_or_frame`` : ``NoteStore``, ``DataFrame`` du journal (``store.frame``,
      ``store.asof``…) ou liste de ``Note`` ;
    - ``asof`` : date (fin de journée) ou instant UTC ; seules les notes connues avant la
      coupure de la séance et négociables comptent (:func:`notes_asof`) ;
    - ``half_life`` : demi-vie en séances, ``2^(−Δ/h)`` ; défaut ``10·ln 2`` (= τ 10) ;
      ``tau`` : constante de temps du document 07, ``exp(−Δ/τ)``, prioritaire si donnée
      (défaut effectif : τ = 10) ; ``calendar`` : calendrier des séances
      (``load_sessions``, liste de dates, ``SessionCalendar``) ; défaut : panel du dépôt ;
    - ``propagation`` : poids par nature de cible (:data:`DEFAULT_PROPAGATION`) ;
      ``propagate=False`` : cibles directes seulement ;
    - ``equities`` : panel long (``load_equities``) pour la composition des secteurs,
      compartiments et indices ; ``"default"`` : panel du dépôt ; ``None`` : référence ;
    - ``strict`` : voir ``NoteStore.asof`` ;
    - ``known_at`` : ``None`` (défaut, mode historique) ou instant de connaissance du mode
      direct (voir l'en-tête du module et :func:`notes_asof`).

    Une ligne par cible (index ``target``) : ``score`` (total), ``score_direct`` (notes sur
    la cible elle-même), ``score_propagated``, ``score_manual`` / ``score_auto`` (auteur),
    ``n_notes``…, ``last_session`` (séance négociable de la note la plus récente),
    ``last_note_id``, ``last_title``, ``last_event_type``. Trié par ``|score|`` décroissant.
    """
    con = note_contributions(store_or_frame, asof, half_life=half_life, calendar=calendar, propagation=propagation,
                             equities=equities, strict=strict, tau=tau, min_decay=min_decay, known_at=known_at)
    if not propagate and len(con):
        con = con[con["relation"] == "directe"]
    return aggregate_contributions(con)


def aggregate_contributions(con: pd.DataFrame) -> pd.DataFrame:
    """Agrège des contributions (:func:`note_contributions`) en une ligne par cible."""
    if con is None or not len(con):
        out = pd.DataFrame(columns=SCORE_COLUMNS)
        out.index.name = "target"
        return out
    rows = []
    for target, g in con.groupby("target", sort=False):
        direct = g["relation"] == "directe"
        manual = g["author"] == "analyste"
        last = g.sort_values(["first_tradable_session", "note_id"]).iloc[-1]
        conf = pd.to_numeric(g["confidence"], errors="coerce")
        rows.append({
            "target": target, "kind": target_kind(target), "label": target_label(target),
            "score": float(g["contribution"].sum()),
            "score_direct": float(g.loc[direct, "contribution"].sum()),
            "score_propagated": float(g.loc[~direct, "contribution"].sum()),
            "score_manual": float(g.loc[manual, "contribution"].sum()),
            "score_auto": float(g.loc[~manual, "contribution"].sum()),
            "n_notes": int(g["note_id"].nunique()), "n_direct": int(g.loc[direct, "note_id"].nunique()),
            "n_propagated": int(g.loc[~direct, "note_id"].nunique()),
            "n_manual": int(g.loc[manual, "note_id"].nunique()), "n_auto": int(g.loc[~manual, "note_id"].nunique()),
            "mean_confidence": float(conf.mean()) if conf.notna().any() else np.nan,
            "last_session": last["first_tradable_session"], "last_note_id": last["note_id"],
            "last_title": last["title"], "last_event_type": last["event_type"],
        })
    out = pd.DataFrame(rows).set_index("target")
    out = out.reindex(out["score"].abs().sort_values(ascending=False, kind="stable").index)
    return out[SCORE_COLUMNS]


def notes_panel(
    store: Any,
    calendar: Any,
    symbols: Iterable[str] | None,
    half_life: float = DEFAULT_HALF_LIFE,
    propagation: Mapping[str, float] | None = None,
    equities: Any = "default",
    strict: bool = True,
    tau: float | None = None,
    min_decay: float = MIN_DECAY,
    targets: Iterable[str] | None = None,
) -> pd.DataFrame:
    """Panel date × symbole du score de nouvelles, point-in-time (IC walk-forward, S5).

    ``calendar`` : dates des lignes (``load_sessions`` : séances avec date ; liste de dates ;
    ``SessionCalendar``) et calendrier de comptage des séances. Chaque valeur est égale à
    ``note_scores(store, t, ...)["score"]`` pour le symbole à la date ``t`` (mêmes règles,
    voir :func:`notes_asof`) : en mode strict, version en vigueur à la séance ``t`` (écrite
    avant sa coupure), note connue avant la coupure, séance effective ``<= t`` (aucune
    information postérieure). ``symbols=None`` : tous les symboles atteints ; ``targets`` : codes non
    symboles à ajouter en colonnes (``IDX:BRVM-30``, ``PAYS:CI``…). 0 en l'absence de note.
    """
    prop = dict(DEFAULT_PROPAGATION if propagation is None else propagation)
    cal = _as_calendar(calendar)
    if isinstance(calendar, SessionCalendar):
        dates = pd.DatetimeIndex(pd.to_datetime(cal.dates))
    elif isinstance(calendar, pd.DataFrame):
        col = calendar["date"] if "date" in calendar.columns else calendar.index.to_series()
        dates = pd.DatetimeIndex(pd.to_datetime(col.dropna()).dt.normalize().unique()).sort_values()
    else:
        dates = pd.DatetimeIndex(pd.to_datetime(pd.Index(list(calendar))).dropna().normalize().unique()).sort_values()
    clock = _clock(cal)
    cols = list(dict.fromkeys(list(symbols or []) + list(targets or [])))
    df = all_versions(store)
    out = pd.DataFrame(0.0, index=dates, columns=cols)
    out.index.name = "date"
    if not len(df) or not len(dates):
        return out
    uni = Universe(equities)
    c_dates = clock.count(dates.values)
    day_ns = dates.values.astype("datetime64[D]")
    acc: dict[str, np.ndarray] = {c: np.zeros(len(dates)) for c in cols}
    max_len = _decay_horizon(half_life, tau, min_decay)
    if strict:
        df = _knowledge(df, clock)
        df = df[df["_eligible"]]
        if len(df):
            eff, _anchor = _effective_session(df, clock)
            df = df.assign(_eff=eff)
    else:
        df = df.assign(_eff=df["first_tradable_session"])

    def _d(ts: Any) -> np.datetime64 | None:
        if ts is None or pd.isna(ts):
            return None
        return np.datetime64(pd.Timestamp(ts).normalize(), "D")

    for _nid, g in df.groupby("note_id", sort=False):
        g = g.sort_values("version")
        rows = list(g.iterrows())
        if strict:
            # Version i en vigueur à la séance D : fts_known_i <= D < min(fts_known_j, j > i).
            starts = [_d(r["_fts_known"]) for _, r in rows]
            ends: list[np.datetime64 | None] = []
            for i in range(len(rows)):
                later = [x for x in starts[i + 1:] if x is not None]
                ends.append(min(later) if later else None)
        else:
            rows = rows[-1:]
            starts, ends = [None], [None]
        for i, (_, r) in enumerate(rows):
            if r["status"] == "archived":
                continue
            eff = _d(r["_eff"])
            if eff is None:
                continue
            start = eff if starts[i] is None else max(eff, starts[i])
            end = ends[i]
            if end is not None and end <= start:
                continue
            lo = int(np.searchsorted(day_ns, start, side="left"))
            hi = len(dates) if end is None else int(np.searchsorted(day_ns, end, side="left"))
            if hi <= lo:
                continue
            row = r.to_dict()
            row["first_tradable_session"] = pd.Timestamp(eff)
            s, an = note_score_value(row, cal)
            if s == 0.0:
                continue
            tg = effective_targets(row, an)
            if not tg:
                continue
            weights = _target_weights(tg, pd.Timestamp(eff), uni, prop)
            wanted = {c: w for c, (w, _src, _rel) in weights.items()
                      if (c in acc) or (symbols is None and target_kind(c) == "symbol")}
            if not wanted:
                continue
            c_eff = clock.count([pd.Timestamp(eff)])[0]
            el = c_dates[lo:hi] - c_eff
            keep = el <= max_len
            if not keep.any():
                continue
            dec = decay_factor(np.maximum(el, 0), half_life, tau)
            dec = np.where(keep & (dec >= min_decay), dec, 0.0)
            for c, w in wanted.items():
                if c not in acc:
                    acc[c] = np.zeros(len(dates))
                acc[c][lo:hi] += s * w * dec
    out = pd.DataFrame(acc, index=dates)
    out.index.name = "date"
    if symbols is None:
        out = out[sorted(out.columns)]
    return out


# ---------------------------------------------------------------------------
# Surcouches manuelles et filtres de risque
# ---------------------------------------------------------------------------


def _is_veto(row: Mapping[str, Any]) -> bool:
    tags = [fold(str(t)) for t in (row.get("tags") or [])]
    return row.get("author") == "analyste" and any(t == "veto" or t.startswith("veto:") for t in tags)


def _fold_title(row: Mapping[str, Any]) -> str:
    return fold(str(row.get("title") or ""))


def _r7_level(fts: pd.Timestamp, day: pd.Timestamp) -> tuple[str, pd.Timestamp]:
    """Niveau R7 (orange / rouge) d'après les dates limites BRVM (document 07 §5.2, §6.6).

    Note publiée de mai à octobre : comptes annuels et T1 (date limite 30/04, rouge le 30/06) ;
    de novembre à avril : S1 et T3 (31/10, rouge le 31/12). Choix de conception signalé.
    """
    y = fts.year
    if 5 <= fts.month <= 10:
        red = pd.Timestamp(year=y, month=6, day=30)
    elif fts.month >= 11:
        red = pd.Timestamp(year=y, month=12, day=31)
    else:
        red = pd.Timestamp(year=y - 1, month=12, day=31)
    return ("rouge" if day >= red else "orange"), red


def _panel_resumption(uni: Universe, symbol: str, since: pd.Timestamp, day: pd.Timestamp) -> pd.Timestamp | None:
    """Première séance non suspendue après une série de mentions SP observée depuis ``since``."""
    eq = uni.equities
    if eq is None or "status" not in eq.columns:
        return None
    g = eq[(eq["symbol"] == symbol) & (eq["date"] >= since) & (eq["date"] <= day)].sort_values("date")
    if not len(g):
        return None
    st = g["status"].astype(str).to_numpy()
    sp = np.flatnonzero(st == "suspended")
    if not len(sp):
        return None
    after = np.flatnonzero(st[sp[0]:] != "suspended")
    if not len(after):
        return None
    return pd.Timestamp(g["date"].iloc[sp[0] + after[0]])


def manual_overlays(
    store: Any,
    asof: Any,
    calendar: Any = None,
    equities: Any = "default",
    propagation: Mapping[str, float] | None = None,
    strict: bool = True,
    tilt_max: float = TILT_MAX_SD,
    use_panel_status: bool = True,
    known_at: Any = None,
) -> dict[str, Any]:
    """Surcouches de l'analyste et filtres de risque actifs à la date ``asof``.

    ``known_at`` : ``None`` (défaut, mode historique : règle stricte à la date ``asof``) ou
    instant de connaissance du **mode direct** ; les durées sont alors comptées jusqu'à la
    séance d'application (clés ``session``, ``known_at`` et ``mode`` du résultat).

    Renvoie un dictionnaire :

    - ``veto`` : ``{symbole: [motifs]}`` — note manuelle étiquetée « veto » (valable
      ``horizon_days`` séances après sa séance négociable, sauf archivage ; une cible large
      s'étend à ses titres) ou filtre R3 / R9 actif ;
    - ``tilt`` : ``pd.Series`` symbole -> ajustement en écarts-types, somme des
      ``signe(stance) × conviction/5 × 0,5`` des notes manuelles en vigueur (pondérée par la
      propagation pour une cible large), bornée à ``±tilt_max`` ; ``tilt_targets`` : idem
      par cible saisie ;
    - ``flags`` : ``{symbole: [ {code, label, since, until, remaining_sessions, note_id,
      title, action, ...} ]}`` — R1-R10 actifs (durées du document 07 §6.6) ;
    - ``block_buys`` (R1, R2, R3, R5, R9 et veto), ``max_weight_mult`` (R4 : 0,5),
      ``freeze_auto`` (R6), ``quality_penalty`` (R7 rouge −0,5, R9 −1, R10 −0,5),
      ``governance_penalty`` (R2 −1), ``disabled_signals`` (R9 : S1, S4) ;
    - ``table`` : une ligne par surcouche active (avec la note qui la porte : ``published_at``,
      ``source``, ``url``) ; ``tilt_notes`` : notes de l'analyste qui portent une inclinaison ;
      ``reasons`` : phrases en français ; ``n_notes`` : notes connues et négociables.
    """
    prop = dict(DEFAULT_PROPAGATION if propagation is None else propagation)
    t = asof_utc(asof)
    if t is None:
        raise ValueError("asof : date vide")
    prices_day = t.tz_localize(None).normalize()
    clock = _clock(calendar)
    moment = notes_moment(prices_day, known_at, clock)
    day = moment.session
    df = notes_asof(store, asof, strict=strict, calendar=calendar, known_at=None if known_at is None else moment)
    uni = Universe(equities)
    rows: list[dict[str, Any]] = []
    tilt_t: dict[str, float] = {}
    tilt_s: dict[str, float] = {}
    tilt_src: dict[str, list[str]] = {}
    tilt_ids: set[str] = set()

    if len(df):
        df = df.sort_values(["first_tradable_session", "published_at", "note_id"]).reset_index(drop=True)
        analyses = [note_analysis(r.to_dict(), calendar) for _, r in df.iterrows()]
        df = df.assign(_an=analyses)
        df["_et"] = [r.get("event_type") or a.get("event_type") for r, a in zip(df.to_dict("records"), analyses)]
        sym_targets = []
        for _, r in df.iterrows():
            tg = effective_targets(r.to_dict(), r["_an"])
            sym_targets.append([c for c, _ in tg if target_kind(c) == "symbol"])
        df["_syms"] = sym_targets
        df["_ft"] = [_fold_title(r) for r in df.to_dict("records")]
    c_day = clock.count(day)[0]

    def later_events(sym: str, after: pd.Timestamp, types: frozenset[str], title_rx: str | None = None) -> pd.Timestamp | None:
        if not len(df):
            return None
        m = (df["first_tradable_session"] > after) & df["_et"].isin(types) & df["_syms"].apply(lambda xs: sym in xs)
        if title_rx is not None:
            m &= df["_ft"].str.contains(title_rx, regex=True)
        sub = df[m]
        return None if not len(sub) else pd.Timestamp(sub["first_tradable_session"].min())

    for _, r in (df.iterrows() if len(df) else []):
        row = r.to_dict()
        an = row["_an"]
        fts = pd.Timestamp(row["first_tradable_session"])
        elapsed = int(c_day - clock.count([fts])[0])
        nid = row["note_id"]
        title = row.get("title") or ""
        base = {"note_id": nid, "title": title, "since": fts, "first_tradable_session": fts,
                "author": row.get("author"), "event_type": row.get("_et"), "published_at": row.get("published_at"),
                "source": row.get("source"), "url": row.get("url") or ""}

        # 1) Veto manuel.
        horizon = int(_finite(row.get("horizon_days")) or DEFAULT_HORIZON_DAYS)
        tg = effective_targets(row, an)
        if _is_veto(row) and elapsed < horizon:
            until = clock.nth_session(fts, horizon - 1) if horizon > 1 else fts
            for code, _o in tg:
                syms, _m = uni.members(code, fts)
                for s in syms:
                    rows.append({**base, "symbol": s, "kind": "veto", "code": "VETO", "until": until,
                                 "remaining_sessions": horizon - 1 - elapsed, "source_target": code,
                                 "action": "exclusion manuelle (veto de l'analyste)"})

        # 2) Surcouche manuelle bornée (tilt).
        sgn = stance_sign(row.get("stance"))
        if row.get("author") == "analyste" and sgn != 0 and elapsed < horizon:
            conv = _finite(row.get("conviction")) or DEFAULT_CONVICTION
            val = sgn * conv / 5.0 * tilt_max
            if tg:
                tilt_ids.add(nid)
            for code, _o in tg:
                tilt_t[code] = tilt_t.get(code, 0.0) + val
            for s, (w, src, _rel) in _target_weights(tg, fts, uni, prop).items():
                if target_kind(s) != "symbol":
                    continue
                tilt_s[s] = tilt_s.get(s, 0.0) + val * w
                tilt_src.setdefault(s, []).append(nid)

        # 3) Filtres de risque (titres seulement).
        flags = list(an.get("risk_flags") or [])
        ex = an.get("extracted") or {}
        r10_unconfirmed = False
        if "R10" not in flags and ex.get("r10_candidate") and row["_syms"]:
            pub = pd.Timestamp(row["published_at"])
            sym0 = row["_syms"][0]
            prior = df[(df["_et"] == "PROFIT_WARNING") & df["_syms"].apply(lambda xs: sym0 in xs)
                       & (df["published_at"] < pub) & (df["published_at"] >= pub - pd.Timedelta(days=120))]
            if not len(prior):
                flags.append("R10")
                r10_unconfirmed = True
        for code in flags:
            rule = RISK_RULES.get(code)
            if rule is None:
                continue
            for s in row["_syms"]:
                until: pd.Timestamp | None = None
                remaining: int | None = None
                active = True
                extra: dict[str, Any] = {}
                if code == "R1":
                    res = later_events(s, fts, frozenset({"RESUMPTION"}))
                    if use_panel_status:
                        pr = _panel_resumption(uni, s, fts, day)
                        if pr is not None and (res is None or pr < res):
                            res = pr
                    if res is not None:
                        until = clock.nth_session(res, int(rule["buffer"]))
                        extra["resumption"] = res
                        active = day <= until
                elif code in ("R3", "R7"):
                    types = ACCOUNTS_EVENTS if code == "R3" else REPORT_EVENTS
                    nxt = later_events(s, fts, types)
                    if nxt is not None and nxt <= day:
                        active = False
                    if code == "R7":
                        level, red = _r7_level(fts, day)
                        extra.update({"level": level, "red_from": red})
                elif code == "R5":
                    exd = to_day(ex.get("ex_date")) if ex.get("ex_date") is not None else None
                    if exd is not None and exd > fts:
                        until = exd - pd.Timedelta(days=1)
                        active = day < exd
                        extra["rights_ex_date"] = exd
                    else:
                        n = int(rule["fallback"])
                        active = elapsed < n
                        until = clock.nth_session(fts, n - 1)
                        remaining = n - 1 - elapsed
                        extra["fallback"] = True
                elif code == "R6":
                    res = later_events(s, fts, frozenset({"TAKEOVER", "OPV_IPO"}), r"resultat|cloture|bilan")
                    if res is not None and res <= day:
                        active = False
                    else:
                        n = int(rule["fallback"])
                        active = elapsed < n
                        until = clock.nth_session(fts, n - 1)
                        remaining = n - 1 - elapsed
                        extra["fallback"] = True
                else:
                    n = int(rule["sessions"])
                    active = elapsed < n
                    until = clock.nth_session(fts, n - 1) if n > 1 else fts
                    remaining = n - 1 - elapsed
                    if code == "R9":
                        nxt = later_events(s, fts, ACCOUNTS_EVENTS)
                        if nxt is not None and nxt <= day:
                            active = False
                            extra["ended_by_accounts"] = nxt
                    if code == "R10" and r10_unconfirmed:
                        extra["confirmed"] = False
                if not active:
                    continue
                if remaining is None and until is not None:
                    remaining = max(int(clock.between(day, until)), 0)
                rows.append({**base, "symbol": s, "kind": "flag", "code": code, "until": until,
                             "remaining_sessions": remaining, "source_target": s, "action": rule["action"],
                             "label": RISK_FLAGS.get(code, code), **extra})

    table = pd.DataFrame(rows)
    if len(table):
        table = table.sort_values(["symbol", "code", "since"]).reset_index(drop=True)
    veto: dict[str, list[str]] = {}
    flags_out: dict[str, list[dict[str, Any]]] = {}
    block: set[str] = set()
    mwm: dict[str, float] = {}
    freeze: set[str] = set()
    qpen: dict[str, float] = {}
    gpen: dict[str, float] = {}
    disabled: dict[str, set[str]] = {}
    reasons: list[str] = []
    for rec in table.to_dict("records") if len(table) else []:
        s = rec["symbol"]
        code = rec["code"]
        short = rec["note_id"][:10]
        until_txt = f"jusqu'au {_fr_date(rec['until'])}" if rec.get("until") is not None and not pd.isna(rec.get("until")) else \
            RISK_RULES.get(code, {}).get("duration", "durée ouverte")
        if code == "VETO":
            veto.setdefault(s, []).append(f"veto manuel (note {short} du {_fr_date(rec['since'])}, {until_txt})")
            block.add(s)
            reasons.append(f"{s} : veto manuel de l'analyste depuis le {_fr_date(rec['since'])}, {until_txt} "
                           f"(note {short} « {rec['title'][:60]} »).")
            continue
        rule = RISK_RULES[code]
        info = {k: rec.get(k) for k in ("code", "label", "since", "until", "remaining_sessions", "note_id", "title",
                                        "action", "level", "resumption", "confirmed", "fallback", "rights_ex_date",
                                        "published_at", "source", "url", "author")
                if k in rec and not (isinstance(rec.get(k), float) and math.isnan(rec.get(k)))}
        flags_out.setdefault(s, []).append(info)
        if rule.get("veto"):
            veto.setdefault(s, []).append(f"{code} actif depuis le {_fr_date(rec['since'])} (note {short})")
        if rule.get("block_buys"):
            block.add(s)
        if rule.get("max_weight_mult"):
            mwm[s] = min(mwm.get(s, 1.0), float(rule["max_weight_mult"]))
        if rule.get("freeze_auto"):
            freeze.add(s)
        pen = rule.get("quality_penalty")
        if code == "R7" and rec.get("level") == "rouge":
            pen = rule.get("quality_penalty_red")
        if pen:
            qpen[s] = min(qpen.get(s, 0.0), float(pen))
        if rule.get("governance_penalty"):
            gpen[s] = min(gpen.get(s, 0.0), float(rule["governance_penalty"]))
        for sig in rule.get("disable", ()):
            disabled.setdefault(s, set()).add(sig)
        rem = rec.get("remaining_sessions")
        rem_txt = f", encore {int(rem)} séance(s)" if rem is not None and not pd.isna(rem) and rem >= 0 else ""
        extra = ""
        if code == "R10" and rec.get("confirmed") is False:
            extra = " (aucune alerte sur résultats dans le journal des 120 jours précédents : à vérifier)"
        if code == "R7" and rec.get("level"):
            extra = f" (niveau {rec['level']})"
        reasons.append(f"{s} : {code} depuis le {_fr_date(rec['since'])}, {until_txt}{rem_txt} — {rule['action']}{extra}.")

    tilt = pd.Series({s: float(np.clip(v, -tilt_max, tilt_max)) for s, v in tilt_s.items()}, dtype=float, name="tilt")
    tilt_targets = pd.Series({c: float(np.clip(v, -tilt_max, tilt_max)) for c, v in tilt_t.items()}, dtype=float,
                             name="tilt")
    for s, v in tilt.items():
        if v != 0:
            reasons.append(f"{s} : surcouche manuelle {_fr_signed(v)} écart-type (borne ±{_fr_num(tilt_max, 1)} ; "
                           f"{len(tilt_src.get(s, []))} note(s) de l'analyste).")
    return {
        "asof": prices_day,
        "session": day,
        "known_at": moment.known_at,
        "mode": moment.mode,
        "n_notes": int(len(df)),
        "tilt_notes": sorted(tilt_ids),
        "veto": veto,
        "tilt": tilt.sort_index(),
        "tilt_targets": tilt_targets.sort_index(),
        "flags": flags_out,
        "block_buys": sorted(block),
        "max_weight_mult": mwm,
        "freeze_auto": sorted(freeze),
        "quality_penalty": qpen,
        "governance_penalty": gpen,
        "disabled_signals": {k: sorted(v) for k, v in disabled.items()},
        "table": table,
        "reasons": reasons,
    }


# ---------------------------------------------------------------------------
# État des notes à une évaluation : ligne de synthèse, notes en vigueur, filtres actifs
# ---------------------------------------------------------------------------

IN_FORCE_COLUMNS = [
    "note_id", "version", "published_at", "first_tradable_session", "known_at", "author", "manual", "source", "url",
    "title", "targets", "event_type", "score", "confidence", "materiality", "stance", "conviction", "horizon_days",
    "sessions_elapsed", "decay", "weight", "filters", "tilt", "tags",
]

#: Comment lever un blocage issu d'une note (texte affiché avec chaque filtre).
LIFT_HINT = ("archiver la note (python -m brvm_alpha notes archive {id}, ou bouton « Archiver » de sa fiche dans "
             "l'interface) : l'archivage écrit une nouvelle version, l'historique est conservé")


def blocks_buys(code: Any) -> bool:
    """Le filtre ``code`` (``R1``…``R10`` ou ``VETO``) interdit-il les achats (document 07 §6.6) ?"""
    c = str(code or "").upper()
    return c == "VETO" or bool(RISK_RULES.get(c, {}).get("block_buys"))


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def _text_or_none(value: Any) -> str | None:
    """Texte non vide, sinon ``None`` (pandas 3 : une valeur manquante d'une colonne de textes vaut NaN)."""
    return value if isinstance(value, str) and value else None


def notes_in_force(
    store: Any,
    asof: Any,
    *,
    known_at: Any = None,
    calendar: Any = None,
    equities: Any = "default",
    propagation: Mapping[str, float] | None = None,
    half_life: float = DEFAULT_HALF_LIFE,
    tau: float | None = None,
    min_decay: float = MIN_DECAY,
    strict: bool = True,
    overlays: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """État des notes pour une évaluation : synthèse, notes en vigueur et filtres actifs.

    ``asof`` : date des cours ; ``known_at`` : ``None`` (mode historique, règle stricte) ou
    instant de connaissance du mode direct. Une note est **en vigueur** si elle est connue et
    négociable (:func:`notes_asof`) et agit encore : décroissance ``exp(−Δ/τ) >= min_decay``
    (moins de 70 séances environ pour τ = 10), filtre de risque ou veto actif, ou avis de
    l'analyste dans son horizon.

    Renvoie un dictionnaire : ``moment`` (:class:`NotesMoment`), ``mode``, ``prices_date``,
    ``session``, ``known_at`` ; ``n_known`` (notes connues et négociables), ``n_in_force``,
    ``n_manual``, ``n_auto``, ``n_scored`` (en vigueur avec un score non nul), ``n_filters``
    (couples titre × filtre R actifs), ``n_block_buys`` (titres dont l'achat est bloqué par une
    note), ``n_veto``, ``n_tilt`` ; ``line`` : « Notes connues au JJ/MM/AAAA HH:MM UTC,
    appliquées à la séance du JJ/MM/AAAA : N en vigueur (dont M manuelles), F filtre(s) de
    risque actif(s) » ; ``scores_message`` (texte clair quand aucune note ne porte de score) ;
    ``table`` (une ligne par note en vigueur, colonnes :data:`IN_FORCE_COLUMNS`, triée de la
    plus récente à la plus ancienne) ; ``filters`` (une entrée par titre × filtre : règle, note
    — date, titre, source, lien —, fin du blocage, comment le lever) ; ``overlays``
    (:func:`manual_overlays`). Lecture factuelle, sans garantie.
    """
    t = asof_utc(asof)
    if t is None:
        raise ValueError("asof : date vide")
    prices_day = t.tz_localize(None).normalize()
    clock = _clock(calendar)
    moment = notes_moment(prices_day, known_at, clock)
    day = moment.session
    direct = moment if known_at is not None else None
    df = notes_asof(store, asof, strict=strict, calendar=calendar, known_at=direct)
    ov = overlays if overlays is not None else manual_overlays(
        store, asof, calendar=calendar, equities=equities, propagation=propagation, strict=strict, known_at=direct)
    tab = ov.get("table")
    recs = tab.to_dict("records") if isinstance(tab, pd.DataFrame) and len(tab) else []
    by_note: dict[str, list[str]] = {}
    filters: list[dict[str, Any]] = []
    for rec in recs:
        code = str(rec.get("code"))
        nid = str(rec.get("note_id"))
        label = f"{code} ({rec.get('symbol')})"
        if label not in by_note.setdefault(nid, []):
            by_note[nid].append(label)
        until = rec.get("until")
        until = None if until is None or pd.isna(until) else pd.Timestamp(until)
        rem = rec.get("remaining_sessions")
        rem = None if rem is None or pd.isna(rem) else int(rem)
        rule = RISK_RULES.get(code, {})
        filters.append({
            "symbole": rec.get("symbol"), "code": code,
            "libelle": "veto manuel de l'analyste" if code == "VETO" else RISK_FLAGS.get(code, code),
            "action": rec.get("action") or rule.get("action", ""), "bloque_achats": blocks_buys(code),
            "depuis": pd.Timestamp(rec["since"]), "jusqu_au": until, "seances_restantes": rem,
            "duree": (f"jusqu'au {_fr_date(until)}" if until is not None else rule.get("duration", "durée ouverte")),
            "note_id": nid, "note_titre": _text_or_none(rec.get("title")) or "", "note_date": rec.get("published_at"),
            "note_source": _text_or_none(rec.get("source")) or "", "note_url": _text_or_none(rec.get("url")) or "",
            "note_auteur": _text_or_none(rec.get("author")) or "", "lever": LIFT_HINT.format(id=nid[:12]),
        })
    tilt_ids = set(ov.get("tilt_notes") or [])
    rows: list[dict[str, Any]] = []
    if len(df):
        elapsed = clock.count(day)[0] - clock.count(df["first_tradable_session"].values)
        dec = decay_factor(np.maximum(elapsed, 0), half_life, tau)
        for (_, r), e, d in zip(df.iterrows(), elapsed, dec):
            row = r.to_dict()
            nid = str(row["note_id"])
            flt = by_note.get(nid, [])
            if d < min_decay and not flt and nid not in tilt_ids:
                continue
            sc, an = note_score_value(row, calendar)
            rows.append({
                "note_id": nid, "version": int(row["version"]), "published_at": row.get("published_at"),
                "first_tradable_session": pd.Timestamp(row["first_tradable_session"]),
                "known_at": row.get("known_at"), "author": _text_or_none(row.get("author")),
                "manual": row.get("author") == "analyste", "source": _text_or_none(row.get("source")) or "",
                "url": _text_or_none(row.get("url")) or "", "title": _text_or_none(row.get("title")) or "",
                "targets": [c for c, _o in effective_targets(row, an)],
                "event_type": _text_or_none(row.get("event_type")) or _text_or_none(an.get("event_type")),
                "score": sc,
                "confidence": _finite(an.get("confidence")), "materiality": _finite(an.get("materiality")),
                "stance": _text_or_none(row.get("stance")), "conviction": _finite(row.get("conviction")),
                "horizon_days": _finite(row.get("horizon_days")), "sessions_elapsed": int(max(e, 0)),
                "decay": float(d), "weight": float(sc * d) if d >= min_decay else 0.0, "filters": list(flt),
                "tilt": nid in tilt_ids, "tags": list(row.get("tags") or []),
            })
    table = pd.DataFrame(rows, columns=IN_FORCE_COLUMNS)
    if len(table):
        table = table.sort_values(["first_tradable_session", "published_at", "note_id"],
                                  ascending=[False, False, True]).reset_index(drop=True)
    n_in = int(len(table))
    n_manual = int(table["manual"].sum()) if n_in else 0
    n_scored = int((table["weight"].abs() > 1e-12).sum()) if n_in else 0
    pairs = {(f["symbole"], f["code"]) for f in filters if f["code"] != "VETO"}
    n_veto = len({f["symbole"] for f in filters if f["code"] == "VETO"})
    tilt = ov.get("tilt")
    n_tilt = int((pd.Series(tilt, dtype=float) != 0).sum()) if tilt is not None and len(tilt) else 0
    blocked = sorted({str(f["symbole"]) for f in filters if f["bloque_achats"]})
    line = (f"{moment.describe()} : {n_in} en vigueur (dont {_plural(n_manual, 'manuelle')}), "
            f"{len(pairs)} filtre(s) de risque actif(s)")
    extra = []
    if n_veto:
        extra.append(f"{n_veto} veto(s) manuel(s)")
    if n_tilt:
        extra.append(f"{n_tilt} inclinaison(s)")
    if blocked:
        extra.append("achats bloqués : " + ", ".join(blocked))
    if extra:
        line += " ; " + ", ".join(extra)
    line += "."
    if not n_in:
        msg = ("Aucune note en vigueur : aucune note connue n'agit à cette séance" + (
            "" if moment.direct else " (mode historique : une note saisie ou collectée après cette date n'agit pas)")
            + ".")
    elif not n_scored:
        msg = (f"Aucune des {n_in} note(s) en vigueur ne porte de score directionnel : leurs titres n'ont ni chiffre "
               "ni ton exploitable (score nul). Elles agissent seulement par leurs filtres de risque et par les avis "
               "de l'analyste ; lire le contenu des documents (python -m brvm_alpha notes lire) peut leur donner un "
               "score.")
    else:
        msg = f"{n_scored} note(s) en vigueur sur {n_in} portent un score directionnel non nul."
    return {
        "moment": moment, "mode": moment.mode, "prices_date": moment.prices_date, "session": moment.session,
        "known_at": moment.known_at, "n_known": int(len(df)), "n_in_force": n_in, "n_manual": n_manual,
        "n_auto": n_in - n_manual, "n_scored": n_scored, "n_filters": len(pairs), "n_veto": n_veto,
        "n_tilt": n_tilt, "n_block_buys": len(blocked), "block_buys": blocked, "line": line,
        "scores_message": msg, "table": table, "filters": filters, "overlays": ov,
    }


def top_notes(table: pd.DataFrame, n: int = 10) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Les ``n`` notes les plus positives et les ``n`` plus négatives (score × décroissance non nul)."""
    if table is None or not len(table):
        empty = pd.DataFrame(columns=IN_FORCE_COLUMNS)
        return empty, empty
    w = pd.to_numeric(table["weight"], errors="coerce").fillna(0.0)
    pos = table[w > 1e-12].assign(_w=w[w > 1e-12]).sort_values("_w", ascending=False, kind="stable").head(n)
    neg = table[w < -1e-12].assign(_w=w[w < -1e-12]).sort_values("_w", ascending=True, kind="stable").head(n)
    return pos.drop(columns=["_w"]).reset_index(drop=True), neg.drop(columns=["_w"]).reset_index(drop=True)


__all__ = [
    "DEFAULT_HALF_LIFE", "DEFAULT_TAU", "DEFAULT_PROPAGATION", "RISK_RULES", "THEME_EXPOSURE", "TILT_MAX_SD", "SessionClock",
    "theme_exposures",
    "Universe", "decay_factor", "note_contributions", "note_scores", "aggregate_contributions", "notes_panel",
    "manual_overlays", "notes_asof", "effective_targets", "all_versions",
    "NotesMoment", "MODE_DIRECT", "MODE_HISTORICAL", "application_session", "notes_moment", "knowledge_instant",
    "notes_in_force", "top_notes", "blocks_buys", "IN_FORCE_COLUMNS",
]
