"""Chargé au démarrage du serveur de processus (« forkserver ») du panel : il meurt avec le processus principal.

Sans ce lien, si seul le processus principal est tué (``KILL`` au seul PID, tueur de mémoire du noyau), le
serveur de processus et les travailleurs restent vivants, rattachés au processus 1 (le maître Odoo dans le
conteneur). Les travailleurs, eux, sont liés à ce serveur par :func:`brvm_alpha.ressources.initialiser_travailleur`.
"""

from brvm_alpha import ressources

ressources.lier_au_parent()
