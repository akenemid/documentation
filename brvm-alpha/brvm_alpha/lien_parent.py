"""Chargé au démarrage du serveur de processus (« forkserver ») du panel : il meurt avec le processus principal.

Sans ce lien, si seul le processus principal est tué (``KILL`` au seul PID, tueur de mémoire du noyau), le
serveur de processus et les travailleurs restent vivants, rattachés au processus 1 (le maître Odoo dans le
conteneur). Les travailleurs, eux, sont liés à ce serveur par :func:`brvm_alpha.ressources.initialiser_travailleur`.

:data:`SERVEUR` garde le PID du serveur : ses travailleurs, nés de lui par ``fork``, en héritent. Un travailleur
dont le serveur est déjà mort quand il pose son lien (moteur tué juste au démarrage du pool) s'arrête aussitôt,
au lieu de rester orphelin.
"""

import os

from brvm_alpha import ressources

#: PID du serveur de processus (lu par ses travailleurs, qui en héritent par ``fork``).
SERVEUR = os.getpid()

ressources.lier_au_parent()
