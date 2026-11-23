#!/bin/sh
# Préparation (machine reliée à Internet, en préproduction) des fichiers du moteur embarqué : l'archive du
# CPython 3.11 autonome et les 16 roues du jeu minimal. Rien n'est installé.
#
# Usage :  sh deploiement/preparer-python-et-roues.sh DOSSIER
#
# Écrit dans DOSSIER (hors du dépôt : ces fichiers vont dans le dépôt PRIVÉ de l'ERP, jamais ici) :
#   DOSSIER/<archive CPython>            référence : deploiement/python-autonome.txt (taille, sha256)
#   DOSSIER/roues/*.whl                  référence : deploiement/roues-py311-x86_64.tsv (nom, taille, sha256)
#   DOSSIER/python-autonome.txt, DOSSIER/roues-py311-x86_64.tsv, DOSSIER/requirements-moteur-py311.txt
#                                        copies des références, pour la traçabilité
# Chaque fichier est vérifié (taille et sha256) ; au moindre écart, le script s'arrête en échec et retire le
# fichier fautif. Les roues sont téléchargées par « pip download » pour CPython 3.11, x86_64, manylinux,
# binaires seulement, avec les empreintes attendues (--require-hashes) et sans dépendance implicite.
#
# Variables :
#   BRVM_PIP_PYTHON  interpréteur qui lance « pip download » (défaut : python3) ; n'importe quelle version
#   BRVM_DEPUIS      dossier local qui contient déjà l'archive et les roues (téléchargement antérieur) : les
#                    fichiers sont copiés de là au lieu d'être téléchargés, puis vérifiés de la même façon
#
# Codes de sortie (jamais 3) : 0 tout est présent et vérifié ; 1 échec (téléchargement, empreinte) ;
# 2 mauvaise utilisation (DOSSIER manquant, relatif ou situé dans le dépôt).
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

[ $# -eq 1 ] || usage "usage : sh deploiement/preparer-python-et-roues.sh DOSSIER"
ICI=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
CODE=$(CDPATH='' cd -- "$ICI/.." && pwd)
DEST=$1
case "$DEST" in
    /*) ;;
    *) usage "refusé : DOSSIER doit être un chemin absolu (reçu : « $DEST »)." ;;
esac
DEPOT=$CODE
if command -v git >/dev/null 2>&1 && git -C "$CODE" rev-parse --show-toplevel >/dev/null 2>&1; then
    DEPOT=$(git -C "$CODE" rev-parse --show-toplevel)
fi
for interdit in "$CODE" "$DEPOT"; do
    case "$DEST/" in
        "$interdit/"*) usage "refusé : DOSSIER ($DEST) est dans le dépôt ($interdit) : l'archive et les roues vont dans le dépôt privé de l'ERP, jamais ici." ;;
    esac
done
REF_PY=$ICI/python-autonome.txt
REF_ROUES=$ICI/roues-py311-x86_64.tsv
REQ=$ICI/requirements-moteur-py311.txt
for f in "$REF_PY" "$REF_ROUES" "$REQ"; do [ -f "$f" ] || echec "référence absente : $f"; done
if command -v sha256sum >/dev/null 2>&1; then
    empreinte() { sha256sum "$1" | cut -d ' ' -f 1; }
elif command -v shasum >/dev/null 2>&1; then
    empreinte() { shasum -a 256 "$1" | cut -d ' ' -f 1; }
else
    echec "ni sha256sum ni shasum : impossible de vérifier les empreintes."
fi
taille() { wc -c <"$1" | tr -d ' '; }
champ() { sed -n "s/^$1=//p" "$REF_PY" | head -n 1; }
ARCHIVE=$(champ archive)
URL=$(champ url)
OCTETS=$(champ octets)
SHA=$(champ sha256)
[ -n "$ARCHIVE" ] && [ -n "$URL" ] && [ -n "$OCTETS" ] && [ -n "$SHA" ] || echec "python-autonome.txt incomplet."

# Vérifie taille et empreinte ; retire le fichier en cas d'écart.
verifier() {
    if [ ! -f "$1" ]; then echec "fichier absent : $1"; fi
    if [ "$(taille "$1")" != "$2" ] || [ "$(empreinte "$1")" != "$3" ]; then
        rm -f -- "$1"
        echec "empreinte ou taille inattendue pour $1 (attendu : $2 octets, sha256 $3) : fichier retiré."
    fi
}

mkdir -p "$DEST/roues"
TMPREQ=$(mktemp)
trap 'rm -f "$TMPREQ"' EXIT

# 1. Archive du CPython autonome.
if [ -f "$DEST/$ARCHIVE" ]; then
    printf 'Archive déjà présente : %s (vérification).\n' "$ARCHIVE"
elif [ -n "${BRVM_DEPUIS:-}" ] && [ -f "$BRVM_DEPUIS/$ARCHIVE" ]; then
    cp -p -- "$BRVM_DEPUIS/$ARCHIVE" "$DEST/$ARCHIVE"
else
    command -v curl >/dev/null 2>&1 || echec "curl est introuvable : télécharger $URL à la main dans $DEST."
    printf 'Téléchargement de %s…\n' "$URL"
    curl -fL --retry 3 --proto '=https' --tlsv1.2 -o "$DEST/$ARCHIVE.part" "$URL" || {
        rm -f -- "$DEST/$ARCHIVE.part"
        echec "téléchargement de l'archive impossible ($URL)."
    }
    mv -- "$DEST/$ARCHIVE.part" "$DEST/$ARCHIVE"
fi
verifier "$DEST/$ARCHIVE" "$OCTETS" "$SHA"
printf 'Archive vérifiée : %s (%s octets, sha256 %s).\n' "$ARCHIVE" "$OCTETS" "$SHA"

# 2. Roues : exigences avec empreintes, tirées de la liste de référence (nom==version --hash=sha256:…).
grep -v '^#' "$REF_ROUES" | while IFS="$(printf '\t')" read -r roue octets sha; do
    [ -n "$roue" ] || continue
    nom=$(printf '%s' "$roue" | cut -d - -f 1)
    version=$(printf '%s' "$roue" | cut -d - -f 2)
    printf '%s==%s --hash=sha256:%s\n' "$nom" "$version" "$sha"
done >"$TMPREQ"
[ "$(wc -l <"$TMPREQ" | tr -d ' ')" -eq 16 ] || echec "la liste des roues ne compte pas 16 lignes."
if [ -n "${BRVM_DEPUIS:-}" ]; then
    grep -v '^#' "$REF_ROUES" | while IFS="$(printf '\t')" read -r roue octets sha; do
        [ -n "$roue" ] || continue
        if [ ! -f "$DEST/roues/$roue" ]; then
            for source in "$BRVM_DEPUIS/roues/$roue" "$BRVM_DEPUIS/$roue"; do
                if [ -f "$source" ]; then cp -p -- "$source" "$DEST/roues/$roue"; break; fi
            done
        fi
    done
else
    PIPPY=${BRVM_PIP_PYTHON:-python3}
    command -v "$PIPPY" >/dev/null 2>&1 || echec "interpréteur introuvable pour pip : $PIPPY (BRVM_PIP_PYTHON)."
    printf 'Téléchargement des roues (pip download, CPython 3.11, x86_64, manylinux)…\n'
    "$PIPPY" -m pip download --dest "$DEST/roues" --no-deps --require-hashes --only-binary=:all: \
        --platform manylinux_2_28_x86_64 --platform manylinux_2_27_x86_64 --platform manylinux_2_17_x86_64 \
        --platform manylinux2014_x86_64 --python-version 3.11.15 --implementation cp --abi cp311 --abi abi3 \
        --abi none --disable-pip-version-check --no-cache-dir -r "$TMPREQ" || echec "pip download a échoué."
fi

# 3. Vérification : exactement les 16 roues de la liste, chacune à sa taille et à son empreinte.
attendues=$(grep -v '^#' "$REF_ROUES" | cut -f 1 | sort)
presentes=$(cd "$DEST/roues" && ls -1 | sort)
if [ "$attendues" != "$presentes" ]; then
    printf 'Roues attendues :\n%s\nRoues présentes :\n%s\n' "$attendues" "$presentes" >&2
    echec "le dossier $DEST/roues ne contient pas exactement les roues de la liste de référence."
fi
grep -v '^#' "$REF_ROUES" | while IFS="$(printf '\t')" read -r roue octets sha; do
    [ -n "$roue" ] || continue
    verifier "$DEST/roues/$roue" "$octets" "$sha"
done
cp -p -- "$REF_PY" "$REF_ROUES" "$REQ" "$DEST/"
total=$(grep -v '^#' "$REF_ROUES" | cut -f 2 | awk '{s += $1} END {print s}')
printf 'Roues vérifiées : 16 fichiers, %s octets, dans %s/roues.\n' "$total" "$DEST"
printf 'Prêt pour une installation hors ligne : sh deploiement/installer-python-et-roues.sh PREFIXE %s CODE\n' "$DEST"
