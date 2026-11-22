"""Gestion du risque et construction de portefeuille (BRVM, long-only).

- :mod:`brvm_alpha.portfolio.risk` : covariance rétrécie de Ledoit-Wolf robuste
  aux valeurs manquantes, matrice de corrélation la plus proche (Higham),
  Hierarchical Risk Parity, contributions au risque.
- :mod:`brvm_alpha.portfolio.construct` : optimisation moyenne-variance sous
  contraintes (secteur, pays, liquidité, coûts), HRP incliné par l'alpha,
  Kelly fractionnel, bande de non-transaction, arrondi en nombre de titres ;
  construction v1 de la spécification (``target_portfolio`` : bande 30/50,
  12 à 20 lignes, plafonds ligne / secteur / pays / AES / liquidité,
  équipondération projetée, variantes G ``hrp_tilt`` et H ``mv_alpha``).
- :mod:`brvm_alpha.portfolio.recommend` : « ordre de bataille » (``recommend``) —
  variante choisie d'après le test S1, nombre exact de titres, prix limites, coûts
  au franc près, échéancier d'exécution (participation, règlement J+2), dividendes
  attendus après IRVM, distribution historique à 12 mois, stress, déclencheurs de
  revue et explications. Chargé à la demande : ``from brvm_alpha.portfolio import recommend``
  donne le sous-module, **appelable** comme sa fonction (``recommend(asof, capital, ...)``) ;
  alias ``ordre_de_bataille`` ; ``OrdreDeBataille`` et ``choose_variant`` exportés.
"""

from __future__ import annotations

import importlib
from typing import Any

#: Exports chargés à la demande : l'import du paquet (par ``strategy.alpha`` via ``construct``)
#: ne charge pas l'ordre de bataille. ``recommend`` est le sous-module (appelable) : Python le
#: résout lui-même ; un attribut homonyme serait écrasé au premier ``import ….recommend``.
_LAZY = {"OrdreDeBataille": ".recommend", "choose_variant": ".recommend", "ordre_de_bataille": ".recommend"}


def __getattr__(name: str) -> Any:
    mod = _LAZY.get(name)
    if mod is None:
        raise AttributeError(f"module 'brvm_alpha.portfolio' has no attribute {name!r}")
    return getattr(importlib.import_module(mod, __name__), name)


__all__ = ["OrdreDeBataille", "choose_variant", "ordre_de_bataille", "recommend"]
