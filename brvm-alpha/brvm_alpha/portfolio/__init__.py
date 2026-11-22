"""Gestion du risque et construction de portefeuille (BRVM, long-only).

- :mod:`brvm_alpha.portfolio.risk` : covariance rétrécie de Ledoit-Wolf robuste
  aux valeurs manquantes, matrice de corrélation la plus proche (Higham),
  Hierarchical Risk Parity, contributions au risque.
- :mod:`brvm_alpha.portfolio.construct` : optimisation moyenne-variance sous
  contraintes (secteur, pays, liquidité, coûts), HRP incliné par l'alpha,
  Kelly fractionnel, bande de non-transaction, arrondi en nombre de titres.
"""
