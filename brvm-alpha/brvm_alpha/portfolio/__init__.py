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
"""
