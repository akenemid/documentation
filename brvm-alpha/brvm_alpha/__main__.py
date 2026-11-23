"""``python -m brvm_alpha`` : garde de démarrage (:mod:`brvm_alpha.demarrage`), puis :mod:`brvm_alpha.cli`.

La garde est posée avant l'import de pandas : signal TERM (code 130), limite de mémoire trop basse (code 6),
échec au chargement du paquet (6, 8 ou 7), toujours un objet JSON avec ``--format json``, jamais le code 3.
"""

from brvm_alpha.demarrage import lancer

raise SystemExit(lancer())
