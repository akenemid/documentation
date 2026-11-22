#!/bin/bash
cd "$(dirname "$0")/pages/p"
UA="Mozilla/5.0 (research bot; polite crawl)"
get(){ # name path
  curl -s --max-time 40 -A "$UA" "https://www.brvm.org$2" -o "$1.html" -w "$1 %{http_code} %{size_download}\n"; sleep 10; }
for i in 1 2; do get rapports_$i "/fr/rapports-societes-cotees?page=$i"; done
for i in $(seq 1 43); do get dividendes_$i "/fr/esv/paiement-de-dividendes?page=$i"; done
for i in $(seq 1 26); do get communiques_$i "/fr/emetteurs/type-annonces/communiques?page=$i"; done
for i in $(seq 1 19); do get convocations_$i "/fr/emetteurs/type-annonces/convocations-assemblees-generales?page=$i"; done
for i in $(seq 1 29); do get avis_$i "/fr/marche/avis-et-publications/avis?page=$i"; done
echo DONE
