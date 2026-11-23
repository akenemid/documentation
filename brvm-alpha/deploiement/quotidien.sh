#!/bin/sh
# Tâche quotidienne de BRVM Alpha, pensée pour la nuit : nouveaux bulletins, panel, suivi sur papier, notes,
# rapport.
#
# Usage :  sh quotidien.sh
# Exemple de planification (cron, heure UTC, après la parution du BOC du soir) :
#   30 22 * * 1-5  BRVM_PYTHON=... BRVM_ALPHA_DONNEES=... sh .../deploiement/quotidien.sh
#
# Priorité basse (nice, et ionice s'il existe) : la tâche laisse la machine aux utilisateurs.
# Durée habituelle : quelques minutes (une à cinq requêtes pour le bulletin, 10 s au moins entre
# deux ; la collecte des notes envoie jusqu'à 150 requêtes, soit 25 minutes au plus).
# « update » cherche tout jour manquant depuis le 02/01/2017 (du plus récent au plus ancien, dans la
# limite du quota) : les trous laissés par une collecte interrompue sont comblés nuit après nuit.
# Aucun rapport n'est écrit tant que l'historique est incomplet (« etat » : pret = false).
# Arrêt : Ctrl+C ou signal TERM au script ; la commande en cours reçoit TERM et s'arrête proprement.
#
# Variables : voir commun.sh. En plus :
#   BRVM_CAPITAL  capital du rapport, en FCFA (défaut : 10000000)
#
# Codes de sortie (jamais 3) : 0 tout s'est bien passé ; 1 une étape a échoué ou l'historique est
# incomplet ; 2 mauvaise utilisation ; 4 une autre tâche tourne déjà (par exemple la première
# collecte) ; 5 refus du site ; 8 configuration ; 130 ou 143 arrêt demandé.
# Performance passée ≠ garantie. Aucun gain n'est garanti.
set -eu
. "$(dirname -- "$0")/commun.sh"

CAPITAL=${BRVM_CAPITAL:-10000000}
brvm_entier BRVM_CAPITAL "$CAPITAL"

brvm_init quotidien
brvm_priorite_basse
brvm_verrou

echecs=0
reseau=oui
refus=non
journal "tâche quotidienne : début."

# 1. Bulletins manquants (le jour même et les trous de l'historique, quota de 200 requêtes).
lancer update --sans-panel
etat_releve
brvm_conclure_update
case "$BRVM_CONCLUSION" in
    refus) reseau=non; refus=oui
           journal "www.brvm.org a refusé l'accès : aucune autre requête cette nuit. Ne pas insister." ;;
    usage) exit 2 ;;
    verrou) exit 4 ;;
    configuration) exit 8 ;;
    reseau|echec) echecs=1 ;;
esac

# 2. Panel : calcul local (seuls les bulletins nouveaux sont relus).
lancer panel
if [ "$BRVM_CODE_RETOUR" -ne 0 ]; then echecs=1; fi

# 2 bis. Suivi sur papier : ligne de la semaine des portefeuilles suivis (calcul local, aucune requête).
lancer suivi maj
if [ "$BRVM_CODE_RETOUR" -ne 0 ]; then
    journal "suivi maj en échec : la tâche continue vers le rapport."; echecs=1
fi

# 3. Notes : collecte polie des publications, puis lecture de 20 documents au plus.
if [ "$reseau" = oui ]; then
    lancer notes research --pdf 20
    if [ "$BRVM_CODE_RETOUR" -ne 0 ]; then echecs=1; fi
fi

# 4. Rapport du jour, seulement si l'installation est prête (panel lisible ET historique complet).
etat_releve
if [ "$(etat_champ pret)" = true ]; then
    lancer report --capital "$CAPITAL"
    if [ "$BRVM_CODE_RETOUR" -ne 0 ]; then echecs=1; fi
else
    journal "pas de rapport : installation pas prête ($(etat_champ raison)) ; la collecte continue les nuits suivantes."
    echecs=1
fi

if [ "$refus" = oui ]; then
    journal "tâche quotidienne : fin, le site a refusé l'accès (voir plus haut)."
    exit 5
fi
if [ "$echecs" -ne 0 ]; then
    journal "tâche quotidienne : fin, avec au moins une étape en échec ou un historique incomplet (voir plus haut)."
    exit 1
fi
journal "tâche quotidienne : fin, tout s'est bien passé."
