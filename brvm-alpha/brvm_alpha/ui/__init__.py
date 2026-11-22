"""Interface web locale de BRVM Alpha (``python -m brvm_alpha serve``).

- :mod:`.server` : serveur ``http.server`` (``ThreadingHTTPServer``) lié à 127.0.0.1, sécurité
  (jeton anti-CSRF sur chaque POST, en-tête ``Host`` vérifié, taille de corps bornée, en-têtes de
  sécurité), services de calcul (notes, indices, ordre de bataille, rapport, recherche) et fil de
  travail unique pour les opérations longues ;
- :mod:`.pages` : pages HTML en français (styles et script en ligne, aucune ressource externe,
  thème clair/sombre, utilisable sur téléphone), texte systématiquement échappé.

Performance passée ≠ garantie. Aucun gain n'est garanti.
"""

from brvm_alpha.ui.server import Job, JobBusy, JobManager, Services, UIServer, make_server, serve

__all__ = ["Job", "JobBusy", "JobManager", "Services", "UIServer", "make_server", "serve"]
