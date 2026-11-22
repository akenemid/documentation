#!/bin/bash
D="$(dirname "$0")"
until grep -q DONE "$D/fetch2.log"; do sleep 15; done
cd "$D/pages/iss"
UA="Mozilla/5.0 (research bot; polite crawl)"
while read p; do n=$(basename "$p"); curl -s --max-time 40 -A "$UA" "https://www.brvm.org$p" -o "$n.html" -w "$n %{http_code} %{size_download}\n"; sleep 10; done < "$D/issuer_eq.txt"
curl -s --max-time 40 -A "$UA" "https://www.brvm.org/fr/textes-reglementaires/reglement-general-instructions-circulaires-et-autres-textes-publies-par-la" -o "../textes.html" -w "textes %{http_code} %{size_download}\n"; sleep 10
curl -s --max-time 40 -A "$UA" "https://www.brvm.org/fr/esv/consolidation" -o "../consolidation.html" -w "consolidation %{http_code}\n"; sleep 10
curl -s --max-time 40 -A "$UA" "https://www.brvm.org/fr/horaires-de-cotation" -o "../horaires.html" -w "horaires %{http_code}\n"; sleep 10
echo DONE3
