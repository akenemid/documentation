"""Rapport final de BRVM Alpha : un fichier HTML autonome, en français.

Point d'entrée : :func:`build_report` ``(asof, capital, out_path, *, panels=None,
panel_dir="data/panel", notes_root="data/notes", validation_dir="reports/validation_S1",
diagnostic_dir="reports/diagnostic_S0", holdings=None, variant=None) -> Path``.

Le rapport réunit le marché au dernier BOC, le résultat du test unique S1 (lu dans
``metrics.json``, jamais recalculé), l'ordre de bataille (``portfolio.recommend``), les revenus,
la distribution à 12 mois, l'évaluation des indices, les notes de l'analyste, les risques,
l'univers et les limites de la méthode. Chaque section est isolée : une erreur affiche un
encadré lisible au lieu de faire échouer le rapport. Performance passée ≠ garantie. Aucun gain
n'est garanti.
"""

from brvm_alpha.report.html import (
    BANNER,
    SECTIONS,
    SOURCES,
    RapportHTML,
    SectionResult,
    build_report,
    render_report,
)

__all__ = [
    "BANNER",
    "SECTIONS",
    "SOURCES",
    "RapportHTML",
    "SectionResult",
    "build_report",
    "render_report",
]
