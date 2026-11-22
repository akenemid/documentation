"""Notes de l'analyste : recherche automatique, saisie manuelle, analyse et agrégation.

Contrat : ``docs/ARCHITECTURE.md``, section « Module Notes de l'analyste ».

- :mod:`.model` : ``Note``, ``NoteAnalysis``, codes de cibles, ``first_tradable_session`` ;
- :mod:`.store` : ``NoteStore``, journal JSONL append-only (``data/notes/notes.jsonl``) ;
- :mod:`.entities` : liaison texte -> symboles, indices, pays, secteurs, thèmes ;
- :mod:`.lexicon` : lexique BRVM-FR v0 et règles de types d'événements (document 07) ;
- :mod:`.analyze` : ``analyze_note`` / ``analyze_text`` -> ``NoteAnalysis`` ;
- :mod:`.research`, :mod:`.signals`, :mod:`.index_eval` : collecte, scores datés,
  évaluation des indices (modules chargés à la demande).

Les notes ne pilotent jamais seules le portefeuille : leur poids est borné et doit être
validé hors échantillon (IC walk-forward, document 07 §6.5 S5). Aucune analyse n'est une
garantie de rendement.
"""

from __future__ import annotations

import importlib
from typing import Any

from .model import (
    EVENT_TYPES,
    RISK_FLAGS,
    Note,
    NoteAnalysis,
    SessionCalendar,
    first_tradable_session,
    normalize_target,
    normalize_targets,
    target_kind,
    target_label,
)

# Attributs chargés à la demande (évite qu'un module en cours d'écriture, ou la lecture
# du panel, ne bloque l'import du modèle).
_LAZY = {
    "NoteStore": ".store",
    "analyze_note": ".analyze",
    "analyze_text": ".analyze",
    "link_entities": ".entities",
    "run_research": ".research",
    "fetch_url_note": ".research",
    "note_scores": ".signals",
    "manual_overlays": ".signals",
    "notes_panel": ".signals",
    "evaluate_indices": ".index_eval",
    "index_dossier": ".index_eval",
}


def __getattr__(name: str) -> Any:
    mod = _LAZY.get(name)
    if mod is None:
        raise AttributeError(f"module 'brvm_alpha.notes' has no attribute {name!r}")
    return getattr(importlib.import_module(mod, __name__), name)


__all__ = [
    "EVENT_TYPES", "RISK_FLAGS", "Note", "NoteAnalysis", "SessionCalendar",
    "first_tradable_session", "normalize_target", "normalize_targets", "target_kind",
    "target_label", *_LAZY,
]
