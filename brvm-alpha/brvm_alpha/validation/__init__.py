"""Exécuteur de la validation (spécification §8, additif v1.1 : D2, D6, D7, D12).

- :func:`run_validation` : test **unique** S1 (verrouillé) ou diagnostic S0 (contaminé) ;
- :func:`run_plan` / :class:`RunSpec` : plan des 30 runs (9 variantes + REF aux coûts centraux
  et de stress à 10 M FCFA ; A et I aux coûts optimistes et sévères ; A, I et REF à 100 M et
  1 Md FCFA) ;
- :mod:`~brvm_alpha.validation.lock` : verrou (arbre git identique à HEAD, refus de relance
  sans motif, ``lock.json``) ;
- :mod:`~brvm_alpha.validation.benchmarks` : étalons (Composite TR, panier EW des éligibles
  de A, Composite prix, BRVM 10/30/Prestige, fonds actions non disponibles) ;
- :mod:`~brvm_alpha.validation.report_md` : rapport ``resultats.md`` en français.

Performance passée ≠ garantie. Aucun gain n'est garanti.
"""

from brvm_alpha.validation.lock import ValidationRefused, check_rerun, git_tree_state
from brvm_alpha.validation.runner import (
    BANNER,
    CAPACITY_CAPITALS,
    CAPITAL_REFERENCE,
    MAX_WORKERS,
    S0_MENTION,
    SAMPLES,
    RunSpec,
    ValidationFailed,
    ValidationResult,
    brvm_alpha_model,
    run_plan,
    run_validation,
)

__all__ = [
    "BANNER",
    "CAPACITY_CAPITALS",
    "CAPITAL_REFERENCE",
    "MAX_WORKERS",
    "S0_MENTION",
    "SAMPLES",
    "RunSpec",
    "ValidationFailed",
    "ValidationRefused",
    "ValidationResult",
    "brvm_alpha_model",
    "check_rerun",
    "git_tree_state",
    "run_plan",
    "run_validation",
]
