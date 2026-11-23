#!/bin/sh
# Export du moteur BRVM Alpha pour l'embarquer dans un module Odoo (mode embarqué, appels en ligne de commande).
#
# Usage :  sh deploiement/exporter-moteur.sh DOSSIER
#
# Copie SEULEMENT ce que le moteur lit à l'exécution :
#   brvm_alpha/                                 le code (sans __pycache__ ni fichier caché)
#   configs/                                    paramètres figés de la stratégie
#   reports/validation_S1/, reports/diagnostic_S0*/, reports/trials.parquet   résultats livrés de la validation
#   deploiement/requirements-moteur-py311.txt   jeu minimal des paquets (Python 3.11)
# Rien d'autre : ni tests, ni documentation (docs/research et ses scripts d'étude compris), ni données, ni
# scripts de déploiement. Puis écrit DOSSIER/VERSION : commit court (suivi de « +modifie » si le code diffère
# du commit), date UTC, empreinte sha256 de chaque fichier. Ce fichier, à la racine du code exporté, active
# le mode embarqué (brvm_alpha.paths.est_embarque) : dossiers de données obligatoires, aucune écriture dans
# le code, pdftotext obligatoire, version lue dans VERSION.
#
# Vérifier un export :  grep -E '^[0-9a-f]{64}  ' DOSSIER/VERSION | (cd DOSSIER && sha256sum -c --quiet)
#
# DOSSIER : absent ou vide, hors du dossier du code. Avec git, la liste vient de git (fichiers suivis, plus
# les nouveaux fichiers non ignorés) ; sans git, de l'arbre (sans __pycache__, *.pyc ni fichier caché).
#
# Codes de sortie (jamais 3) : 0 export écrit ; 1 échec ; 2 mauvaise utilisation.
# Performance passée ≠ garantie. Aucun gain n'est garanti.
set -eu

echec() {
    printf 'échec : %s\n' "$*" >&2
    exit 1
}
usage() {
    printf '%s\n' "$*" >&2
    exit 2
}

[ $# -eq 1 ] || usage "usage : sh deploiement/exporter-moteur.sh DOSSIER"
ICI=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
CODE=$(CDPATH='' cd -- "$ICI/.." && pwd)
DEST=$1
case "$DEST" in
    /*) ;;
    *) DEST=$(pwd)/$DEST ;;
esac
case "$DEST/" in
    "$CODE/"*) usage "refusé : DOSSIER ($DEST) est dans le dossier du code ($CODE) ; choisir un dossier à part." ;;
esac
if [ -e "$DEST" ] && [ -n "$(ls -A "$DEST" 2>/dev/null)" ]; then
    usage "refusé : DOSSIER ($DEST) existe et n'est pas vide."
fi
if command -v sha256sum >/dev/null 2>&1; then
    EMPREINTE="sha256sum"
elif command -v shasum >/dev/null 2>&1; then
    EMPREINTE="shasum -a 256"
else
    echec "ni sha256sum ni shasum : impossible de calculer les empreintes."
fi

LISTE=$(mktemp)
trap 'rm -f "$LISTE" "$LISTE.tri"' EXIT
COMMIT=inconnu
COMMIT_LONG=inconnu
MODIF=non
set -- brvm_alpha configs reports/validation_S1 'reports/diagnostic_S0*' reports/trials.parquet \
    deploiement/requirements-moteur-py311.txt
if command -v git >/dev/null 2>&1 && git -C "$CODE" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    git -C "$CODE" -c core.quotepath=off ls-files --cached --others --exclude-standard -- "$@" >"$LISTE"
    COMMIT=$(git -C "$CODE" rev-parse --short=7 HEAD)
    COMMIT_LONG=$(git -C "$CODE" rev-parse HEAD)
    if [ -n "$(git -C "$CODE" status --porcelain --untracked-files=normal -- "$@")" ]; then MODIF=oui; fi
else
    (cd "$CODE" && find brvm_alpha configs reports/validation_S1 reports/diagnostic_S0* reports/trials.parquet \
        deploiement/requirements-moteur-py311.txt -type f) >"$LISTE"
fi
# Jamais de cache Python ni de fichier caché ; chaque fichier une seule fois.
grep -v -e '/__pycache__/' -e '\.pyc$' -e '/\.' -e '^\.' "$LISTE" | sort -u >"$LISTE.tri" || true
[ -s "$LISTE.tri" ] || echec "aucun fichier à exporter depuis $CODE."
grep -qx 'brvm_alpha/__init__.py' "$LISTE.tri" || echec "brvm_alpha/__init__.py absent de la liste."
grep -qx 'deploiement/requirements-moteur-py311.txt' "$LISTE.tri" || \
    echec "deploiement/requirements-moteur-py311.txt absent."

mkdir -p "$DEST"
n=0
while IFS= read -r f; do
    if [ ! -f "$CODE/$f" ]; then  # fichier suivi mais supprimé de l'arbre : le code diffère du commit
        MODIF=oui
        continue
    fi
    mkdir -p "$DEST/$(dirname -- "$f")"
    cp -p -- "$CODE/$f" "$DEST/$f"
    n=$((n + 1))
done <"$LISTE.tri"

VERSION_LIGNE=$COMMIT
SUFFIXE=""
if [ "$MODIF" = oui ]; then
    VERSION_LIGNE="$COMMIT+modifie"
    SUFFIXE=" (code modifié depuis ce commit)"
fi
{
    printf '%s\n' "$VERSION_LIGNE"
    printf '%s\n' "# BRVM Alpha : moteur exporté pour le mode embarqué (deploiement/exporter-moteur.sh)."
    printf '%s\n' "# Ce fichier, à la racine du code, active le mode embarqué (brvm_alpha.paths.est_embarque)."
    printf '# commit : %s%s\n' "$COMMIT_LONG" "$SUFFIXE"
    printf '# date (UTC) : %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    printf '# fichiers : %s\n' "$n"
    printf '%s\n' "# Empreintes sha256. Vérification : grep -E '^[0-9a-f]{64}  ' VERSION | sha256sum -c --quiet"
    while IFS= read -r f; do
        if [ -f "$DEST/$f" ]; then (cd "$DEST" && $EMPREINTE -- "$f"); fi
    done <"$LISTE.tri"
} >"$DEST/VERSION"

printf 'Export écrit : %s (%s fichiers, version %s).\n' "$DEST" "$n" "$VERSION_LIGNE"
if [ "$MODIF" = oui ]; then
    printf '%s\n' "Attention : le code exporté diffère du commit $COMMIT (fichiers modifiés ou nouveaux)." >&2
fi
