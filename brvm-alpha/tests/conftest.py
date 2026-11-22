"""Configuration commune des tests.

Les tests du module ``notes`` simulent des instants d'écriture passés (``NoteStore.add(now=...)``,
``run_research(now=...)``) pour reconstituer des chronologies. Hors tests, un tel instant
antidaté marque la note « reconstituée » (exclue des vues strictes, voir
``brvm_alpha.notes.store``). Le mode horloge simulée est donc activé pour toute la suite ;
les tests de régression du marquage le désactivent localement (``monkeypatch.delenv``).
"""

from __future__ import annotations

import os

from brvm_alpha.notes.model import SIMULATED_CLOCK_ENV

os.environ.setdefault(SIMULATED_CLOCK_ENV, "1")
