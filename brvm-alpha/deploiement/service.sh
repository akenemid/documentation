#!/bin/sh
# Service de BRVM Alpha : lance l'interface web du moteur, liée à 127.0.0.1 seulement.
# À placer sous un superviseur (supervisor, systemd, Docker) qui le relance s'il s'arrête.
#
# Usage :  sh service.sh
#
# L'interface n'a pas d'authentification : elle n'écoute que sur 127.0.0.1. C'est le relais
# authentifié (le contrôleur Odoo) qui la rend visible aux utilisateurs autorisés.
#
# Variables : voir commun.sh. En plus :
#   BRVM_PORT                   port d'écoute sur 127.0.0.1 (défaut : 8765)
#   BRVM_ALPHA_PREFIXE          préfixe d'adresse du relais, par exemple /rz_brvm_alpha/ui (défaut : aucun)
#   BRVM_ALPHA_ORIGINES_RELAIS  origines du relais acceptées pour les formulaires, séparées par des
#                               virgules, par exemple https://erp.exemple.com (défaut : aucune)
#   BRVM_CADRE_MEME_ORIGINE     « oui » : les pages peuvent s'afficher dans un cadre (iframe) de la
#                               même origine que le relais (défaut : non, aucun cadre)
#
# Performance passée ≠ garantie. Aucun gain n'est garanti.
set -eu
. "$(dirname -- "$0")/commun.sh"

brvm_init service

PORT=${BRVM_PORT:-8765}
if [ -n "${BRVM_ALPHA_PREFIXE:-}" ]; then export BRVM_ALPHA_PREFIXE; fi
if [ -n "${BRVM_ALPHA_ORIGINES_RELAIS:-}" ]; then export BRVM_ALPHA_ORIGINES_RELAIS; fi

set -- serve --port "$PORT"
case "${BRVM_CADRE_MEME_ORIGINE:-non}" in
    oui|1|true) set -- "$@" --cadre-meme-origine ;;
esac

journal "service : interface sur 127.0.0.1:$PORT ; préfixe : ${BRVM_ALPHA_PREFIXE:-aucun} ; origines du relais : ${BRVM_ALPHA_ORIGINES_RELAIS:-aucune} ; cadre de même origine : ${BRVM_CADRE_MEME_ORIGINE:-non}."
# « exec » : le superviseur parle directement au moteur (arrêt propre, pas de processus en trop).
exec "$BRVM_PYTHON" -m brvm_alpha "$@"
