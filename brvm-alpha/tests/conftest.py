"""Configuration commune des tests.

Les tests du module ``notes`` simulent des instants d'écriture passés (``NoteStore.add(now=...)``,
``run_research(now=...)``) pour reconstituer des chronologies. Hors tests, un tel instant
antidaté marque la note « reconstituée » (exclue des vues strictes, voir
``brvm_alpha.notes.store``). Le mode horloge simulée est donc activé pour toute la suite ;
les tests de régression du marquage le désactivent localement (``monkeypatch.delenv``).

Le nom de la variable est lu dans ``brvm_alpha.notes.model`` s'il s'importe ; sinon (module des
notes absent ou en cours d'écriture par un autre workflow) il est écrit en dur, pour que les tests
du moteur, du portefeuille et de la stratégie restent collectables (``test_without_notes_module``).
"""

from __future__ import annotations

import os

#: Valeur de repli, identique à ``brvm_alpha.notes.model.SIMULATED_CLOCK_ENV``.
_FALLBACK_SIMULATED_CLOCK_ENV = "BRVM_ALPHA_SIMULATED_CLOCK"

try:
    from brvm_alpha.notes.model import SIMULATED_CLOCK_ENV
except Exception:  # noqa: BLE001 - tout échec d'import du module des notes (ImportError, SyntaxError…)
    SIMULATED_CLOCK_ENV = _FALLBACK_SIMULATED_CLOCK_ENV

os.environ.setdefault(SIMULATED_CLOCK_ENV, "1")
