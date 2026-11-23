# Ordre de bataille BRVM Alpha au 20/11/2026

> **Performance passée ≠ garantie. Aucun gain n'est garanti. Statut : REJETÉ.**

**Recommandation à titre d'étude ; suivi réel (paper trading) requis avant tout engagement d'argent réel.**

> ⚠ ACHAT BLOQUÉ par une note : ETIT (R2, annulation ou report d'AG : −1 en gouvernance, aucun achat (60 séances)) — note 4a46238f820f du 23/10/2026 « ETI TG : Communiqué - Annulation de l'Assemblée Générale Ordinaire », jusqu'au 19/01/2027. Effet : aucun achat (poids cible 6,16 % sans les notes, 0 % avec) ; ce poids est redistribué aux autres lignes par les règles de construction (voir le tableau d'effet). Pour lever le blocage : archiver la note (python -m brvm_alpha notes archive 4a46238f820f, ou bouton « Archiver » de sa fiche dans l'interface) : l'archivage écrit une nouvelle version, l'historique est conservé.

> ⚠ Biais rétrospectif : poids actuels et sélection d'aujourd'hui (plus grosses capitalisations au 20/11/2026) appliqués à toute l'histoire 2017-2026 ; les titres alors en difficulté ou radiés n'y figurent pas, ce qui flatte la distribution. Lignes sans historique complet : ORAC (18,1 %, depuis le 06/01/2023), ECOC (5,0 %, depuis le 15/12/2017), BICB (2,7 %, depuis le 02/05/2025), NSBC (2,2 %, depuis le 27/10/2017), soit 28,1 % du portefeuille ; 790 valeur(s) antérieure(s) à la cotation : poids renormalisés sur les lignes cotées (et non comptées à 0 %). 0 valeur(s) manquante(s) après cotation (suspensions) comptée(s) à 0 %.

> ⚠ Résultat du test unique S1 (metrics.json, fait de simulation) : la variante appliquée REF fait −5,6 % par an contre le Composite TR (statut REJETÉ). La P(battre le TR) de la distribution à 12 mois est une fréquence historique aux poids actuels, pas une probabilité de surperformance future.

> ⚠ FUITE : Les frais annuels du courtier (124 126 FCFA) prennent 28 % des dividendes nets attendus (435 988 FCFA) [supposé].

### L'essentiel

- Prochaine séance : aucun achat. Aucune méthode n'est validée : avec les règles actuelles, la plate-forme ne recommandera pas d'argent réel. Changer ces règles serait votre décision, jamais avant le 01/06/2027 (6 mois de suivi sur papier à partir du 01/12/2026).
- Frais de la 1re année si vous achetiez tout : 284 714 FCFA, dont 89,8 % supposés ou estimés (255 762 FCFA). Ces frais n'existent que si vous achetez. Montants calculés sur un tarif supposé tant que la grille de votre courtier n'est pas saisie.
- Si vous ne faites qu'une chose cette semaine : envoyez les 8 questions à votre courtier.
- 500 000 FCFA acceptés : 1 400 000 FCFA en actions, 8 600 000 FCFA en réserve ; une année comme 2018 −410 532 FCFA à −474 919 FCFA ; pire moment de 2018 −501 430 FCFA (dépasse) ; si 2017-2020 revenait −659 065 FCFA (dépasse) ; année ordinaire (prudente) −10 489 FCFA [estimé]
- 1 000 000 FCFA acceptés : 3 000 000 FCFA en actions, 7 000 000 FCFA en réserve ; une année comme 2018 −824 753 FCFA à −974 805 FCFA ; pire moment de 2018 −1 036 590 FCFA (dépasse) ; si 2017-2020 revenait −1 403 953 FCFA (dépasse) ; année ordinaire (prudente) +118 001 FCFA [estimé]
- 2 000 000 FCFA acceptés : 6 300 000 FCFA en actions, 3 700 000 FCFA en réserve ; une année comme 2018 −1 653 624 FCFA à −1 974 832 FCFA ; pire moment de 2018 −2 107 091 FCFA (dépasse) ; si 2017-2020 revenait −2 893 483 FCFA (dépasse) ; année ordinaire (prudente) +374 746 FCFA [estimé]
- Tout en actions : 10 000 000 FCFA en actions, 0 FCFA en réserve ; une année comme 2018 −2 598 431 FCFA à −3 114 258 FCFA ; pire moment de 2018 −3 326 652 FCFA ; si 2017-2020 revenait −4 589 518 FCFA ; année ordinaire (prudente) +664 187 FCFA [estimé]
- Fréquences d'un seul passé (2017-2026 : quatre années de baisse, puis six de hausse). Ce ne sont pas des probabilités. Descriptif, pas un test.
- Réserve 10 000 000 FCFA : un point d'intérêt vaut 100 000 FCFA par an [taux inconnu : compté à 0 %]. Les intérêts de la réserve ne sont jamais déduits de la perte estimée.
- Trois feux : perte — ; fuites — ; données — (le suivi n'a pas commencé).

Décision à la clôture du BOC du 20/11/2026 ; exécution à partir du 24/11/2026. Capital 10 000 000 FCFA ; valeur du portefeuille avant ordres 10 000 000 FCFA, dont liquidités 10 000 000 FCFA.

Notes connues au 23/11/2026 14:30 UTC, appliquées à la séance du 24/11/2026 : 114 en vigueur (dont 0 manuelles), 8 filtre(s) de risque actif(s) ; achats bloqués : ETIT, SEMC, SICC.

## 1. Variante et statut de validation

- Variante retenue : **REF** — indice discipliné (D8) : 20 plus grosses capitalisations éligibles, annuel
- Motif : A est REJETÉ sur S1 : mode « indice discipliné » (§8.3, D8), aucune promesse d'alpha
- Statut de A sur S1 : REJETÉ ; registre : 20 essai(s) S1 au statut « exécuté »
- Variante en comparaison : aucune

## 2. Ordres (au titre et au franc près)

**Étude : ne transmettez pas ces ordres à votre courtier.**

| Titre | Sens | Quantité | Détenus | Cible | Poids cible | Poids réalisé | Cours réf. | Bornes | Limite | Brut | Coûts | Net | Séances |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| SNTS | ACHAT | 629 | 0 | 629 | 25,44 % | 25,41 % | 4 040 | 3 740 – 4 340 | 4 080 | 2 541 160 FCFA | 36 531 FCFA | 2 577 691 FCFA | 1 |
| ORAC | ACHAT | 94 | 0 | 94 | 18,27 % | 18,09 % | 19 250 | 17 810 – 20 690 | 19 440 | 1 809 500 FCFA | 34 906 FCFA | 1 844 406 FCFA | 1 |
| SGBC | ACHAT | 19 | 0 | 19 | 7,60 % | 7,37 % | 38 795 | 35 890 – 41 700 | 39 180 | 737 105 FCFA | 10 553 FCFA | 747 658 FCFA | 1 |
| CBIBF | ACHAT | 20 | 0 | 20 | 5,54 % | 5,50 % | 27 505 | 25 445 – 29 565 | 27 780 | 550 100 FCFA | 10 068 FCFA | 560 168 FCFA | 1 |
| SIBC | ACHAT | 62 | 0 | 62 | 5,16 % | 5,08 % | 8 200 | 7 585 – 8 815 | 8 280 | 508 400 FCFA | 8 355 FCFA | 516 755 FCFA | 1 |
| ECOC | ACHAT | 34 | 0 | 34 | 5,13 % | 5,03 % | 14 795 | 13 690 – 15 900 | 14 940 | 503 030 FCFA | 8 650 FCFA | 511 680 FCFA | 1 |
| SLBC | ACHAT | 10 | 0 | 10 | 4,20 % | 4,05 % | 40 500 | 37 465 – 43 535 | 40 905 | 405 000 FCFA | 8 058 FCFA | 413 058 FCFA | 1 |
| BICC | ACHAT | 10 | 0 | 10 | 3,25 % | 3,10 % | 31 000 | 28 675 – 33 325 | 31 310 | 310 000 FCFA | 5 930 FCFA | 315 930 FCFA | 1 |
| BOAC | ACHAT | 25 | 0 | 25 | 2,77 % | 2,75 % | 10 995 | 10 175 – 11 815 | 11 100 | 274 875 FCFA | 4 163 FCFA | 279 038 FCFA | 1 |
| BICB | ACHAT | 36 | 0 | 36 | 2,73 % | 2,70 % | 7 500 | 6 940 – 8 060 | 7 575 | 270 000 FCFA | 4 230 FCFA | 274 230 FCFA | 1 |
| STBC | ACHAT | 11 | 0 | 11 | 2,41 % | 2,35 % | 21 325 | 19 730 – 22 920 | 21 535 | 234 575 FCFA | 3 711 FCFA | 238 286 FCFA | 1 |
| NSBC | ACHAT | 15 | 0 | 15 | 2,34 % | 2,25 % | 15 000 | 13 875 – 16 125 | 15 150 | 225 000 FCFA | 3 379 FCFA | 228 379 FCFA | 1 |
| BOAB | ACHAT | 25 | 0 | 25 | 2,32 % | 2,27 % | 9 095 | 8 415 – 9 775 | 9 185 | 227 375 FCFA | 3 707 FCFA | 231 082 FCFA | 1 |
| BOABF | ACHAT | 27 | 0 | 27 | 2,13 % | 2,08 % | 7 700 | 7 125 – 8 275 | 7 775 | 207 900 FCFA | 3 470 FCFA | 211 370 FCFA | 1 |
| NTLC | ACHAT | 13 | 0 | 13 | 1,78 % | 1,66 % | 12 800 | 11 840 – 13 760 | 12 925 | 166 400 FCFA | 2 888 FCFA | 169 288 FCFA | 1 |
| BOAS | ACHAT | 22 | 0 | 22 | 1,75 % | 1,69 % | 7 700 | 7 125 – 8 275 | 7 775 | 169 400 FCFA | 2 478 FCFA | 171 878 FCFA | 1 |
| CIEC | ACHAT | 35 | 0 | 35 | 1,55 % | 1,54 % | 4 400 | 4 070 – 4 730 | 4 440 | 154 000 FCFA | 2 625 FCFA | 156 625 FCFA | 1 |
| SPHC | ACHAT | 16 | 0 | 16 | 1,23 % | 1,22 % | 7 645 | 7 075 – 8 215 | 7 720 | 122 320 FCFA | 2 206 FCFA | 124 526 FCFA | 1 |
| ONTBF | ACHAT | 42 | 0 | 42 | 1,20 % | 1,18 % | 2 805 | 2 595 – 3 015 | 2 830 | 117 810 FCFA | 2 408 FCFA | 120 218 FCFA | 1 |
| TTLC | ACHAT | 39 | 0 | 39 | 1,19 % | 1,17 % | 2 990 | 2 770 – 3 210 | 3 015 | 116 610 FCFA | 2 272 FCFA | 118 882 FCFA | 1 |

### Achats bloqués par les notes de l'analyste et effet sur les poids

| Titre | Règle | Note | Blocage | Effet sur l'ordre | Pour lever le blocage |
|---|---|---|---|---|---|
| ETIT | R2 — annulation ou report d'AG : −1 en gouvernance, aucun achat (60 séances) | note 4a46238f820f du 23/10/2026 : « ETI TG : Communiqué - Annulation de l'Assemblée Générale Ordinaire » (source brvm_list, https://www.brvm.org/sites/default/files/20261023_-_communique_-_annulation_ago_-_eti_tg.pdf) | depuis le 26/10/2026, jusqu'au 19/01/2027 (encore 38 séance(s)) | aucun achat (poids cible 6,16 % sans les notes, 0 % avec) ; ce poids est redistribué aux autres lignes par les règles de construction (voir le tableau d'effet) | archiver la note (python -m brvm_alpha notes archive 4a46238f820f, ou bouton « Archiver » de sa fiche dans l'interface) : l'archivage écrit une nouvelle version, l'historique est conservé |
| SEMC | R1 — suspension : aucun achat, alerte sur les positions (jusqu'à la reprise + 5 séances) | note e648d82ebd87 du 16/09/2026 : « SEMC : cotation suspendue (mention SP depuis le BOC du 16/09/2026) » (source boc, https://www.brvm.org/sites/default/files/boc_20260916_2.pdf) | depuis le 17/09/2026, jusqu'à la reprise de cotation + 5 séances | titre hors de la sélection : aucun effet sur cet ordre | archiver la note (python -m brvm_alpha notes archive e648d82ebd87, ou bouton « Archiver » de sa fiche dans l'interface) : l'archivage écrit une nouvelle version, l'historique est conservé |
| SICC | R1 — suspension : aucun achat, alerte sur les positions (jusqu'à la reprise + 5 séances) | note 6771f0ac46eb du 16/09/2026 : « SICC : cotation suspendue (mention SP depuis le BOC du 16/09/2026) » (source boc, https://www.brvm.org/sites/default/files/boc_20260916_2.pdf) | depuis le 17/09/2026, jusqu'à la reprise de cotation + 5 séances | titre hors de la sélection : aucun effet sur cet ordre | archiver la note (python -m brvm_alpha notes archive 6771f0ac46eb, ou bouton « Archiver » de sa fiche dans l'interface) : l'archivage écrit une nouvelle version, l'historique est conservé |

Effet des notes sur les poids cibles (même décision recalculée sans aucune note, pour information) : 21 ligne(s) modifiée(s) ; total investi cible 98,00 % sans les notes, 98,00 % avec : le poids retiré est redistribué aux autres lignes par les règles de construction existantes. Les notes ne changent aucune règle : elles retirent un titre des achats ou inclinent un score, dans les bornes de la spécification (indice discipliné : l'inclinaison n'entre pas dans la sélection par capitalisation).

| Titre | Poids cible sans les notes | Poids cible avec les notes | Écart | Motif |
|---|---|---|---|---|
| ETIT | 6,16 % | 0,00 % | −6,16 % | filtre R2 |
| ONTBF | 1,14 % | 1,20 % | +0,06 % | redistribution (construction) |
| SPHC | 1,17 % | 1,23 % | +0,06 % | redistribution (construction) |
| CIEC | 1,47 % | 1,55 % | +0,08 % | redistribution (construction) |
| BOAS | 1,66 % | 1,75 % | +0,09 % | redistribution (construction) |
| NTLC | 1,69 % | 1,78 % | +0,09 % | redistribution (construction) |
| BOABF | 2,02 % | 2,13 % | +0,11 % | redistribution (construction) |
| BOAB | 2,20 % | 2,32 % | +0,12 % | redistribution (construction) |
| NSBC | 2,22 % | 2,34 % | +0,12 % | redistribution (construction) |
| STBC | 2,29 % | 2,41 % | +0,12 % | redistribution (construction) |
| BICB | 2,59 % | 2,73 % | +0,14 % | redistribution (construction) |
| BOAC | 2,63 % | 2,77 % | +0,14 % | redistribution (construction) |
| BICC | 3,09 % | 3,25 % | +0,17 % | redistribution (construction) |
| SLBC | 3,98 % | 4,20 % | +0,22 % | redistribution (construction) |
| ECOC | 4,87 % | 5,13 % | +0,26 % | redistribution (construction) |
| SIBC | 4,90 % | 5,16 % | +0,27 % | redistribution (construction) |
| CBIBF | 5,26 % | 5,54 % | +0,28 % | redistribution (construction) |
| SGBC | 7,21 % | 7,60 % | +0,39 % | redistribution (construction) |
| ORAC | 17,33 % | 18,27 % | +0,94 % | redistribution (construction) |
| TTLC | 0,00 % | 1,19 % | +1,19 % | redistribution (construction) |
| SNTS | 24,14 % | 25,44 % | +1,31 % | redistribution (construction) |

### Coûts détaillés par ordre (estimation au cours de référence)

| Titre | Sens | Courtage | TVA | BRVM | DC/BR | Demi-spread | Impact | Total | Demi-spread % | Particip. max | Pire cas (provision) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| SNTS | achat | 20 329 FCFA | 3 659 FCFA | 5 082 FCFA | 2 541 FCFA | 2 700 FCFA | 2 220 FCFA | 36 531 FCFA | 0,106 % | 0,3 % | 2 598 246 FCFA |
| ORAC | achat | 14 476 FCFA | 2 606 FCFA | 3 619 FCFA | 1 810 FCFA | 7 312 FCFA | 5 083 FCFA | 34 906 FCFA | 0,404 % | 3,1 % | 1 850 092 FCFA |
| SGBC | achat | 5 897 FCFA | 1 061 FCFA | 1 474 FCFA | 737 FCFA | 575 FCFA | 809 FCFA | 10 553 FCFA | 0,078 % | 0,5 % | 753 680 FCFA |
| CBIBF | achat | 4 401 FCFA | 792 FCFA | 1 100 FCFA | 550 FCFA | 2 009 FCFA | 1 216 FCFA | 10 068 FCFA | 0,365 % | 1,9 % | 562 512 FCFA |
| SIBC | achat | 4 067 FCFA | 732 FCFA | 1 017 FCFA | 508 FCFA | 1 370 FCFA | 661 FCFA | 8 355 FCFA | 0,270 % | 0,7 % | 519 746 FCFA |
| ECOC | achat | 4 024 FCFA | 724 FCFA | 1 006 FCFA | 503 FCFA | 1 423 FCFA | 970 FCFA | 8 650 FCFA | 0,283 % | 1,5 % | 514 280 FCFA |
| SLBC | achat | 3 240 FCFA | 583 FCFA | 810 FCFA | 405 FCFA | 1 919 FCFA | 1 101 FCFA | 8 058 FCFA | 0,474 % | 2,9 % | 414 138 FCFA |
| BICC | achat | 2 480 FCFA | 446 FCFA | 620 FCFA | 310 FCFA | 1 242 FCFA | 832 FCFA | 5 930 FCFA | 0,401 % | 2,8 % | 316 995 FCFA |
| BOAC | achat | 2 199 FCFA | 396 FCFA | 550 FCFA | 275 FCFA | 490 FCFA | 253 FCFA | 4 163 FCFA | 0,178 % | 0,3 % | 280 953 FCFA |
| BICB | achat | 2 160 FCFA | 389 FCFA | 540 FCFA | 270 FCFA | 549 FCFA | 322 FCFA | 4 230 FCFA | 0,203 % | 0,6 % | 276 093 FCFA |
| STBC | achat | 1 877 FCFA | 338 FCFA | 469 FCFA | 235 FCFA | 507 FCFA | 285 FCFA | 3 711 FCFA | 0,216 % | 0,6 % | 239 832 FCFA |
| NSBC | achat | 1 800 FCFA | 324 FCFA | 450 FCFA | 225 FCFA | 355 FCFA | 225 FCFA | 3 379 FCFA | 0,158 % | 0,4 % | 230 077 FCFA |
| BOAB | achat | 1 819 FCFA | 327 FCFA | 455 FCFA | 227 FCFA | 551 FCFA | 328 FCFA | 3 707 FCFA | 0,242 % | 0,8 % | 232 482 FCFA |
| BOABF | achat | 1 663 FCFA | 299 FCFA | 416 FCFA | 208 FCFA | 571 FCFA | 313 FCFA | 3 470 FCFA | 0,275 % | 0,9 % | 212 536 FCFA |
| NTLC | achat | 1 331 FCFA | 240 FCFA | 333 FCFA | 166 FCFA | 532 FCFA | 286 FCFA | 2 888 FCFA | 0,319 % | 1,2 % | 170 115 FCFA |
| BOAS | achat | 1 355 FCFA | 244 FCFA | 339 FCFA | 169 FCFA | 231 FCFA | 140 FCFA | 2 478 FCFA | 0,136 % | 0,3 % | 173 177 FCFA |
| CIEC | achat | 1 232 FCFA | 222 FCFA | 308 FCFA | 154 FCFA | 544 FCFA | 165 FCFA | 2 625 FCFA | 0,353 % | 0,5 % | 157 333 FCFA |
| SPHC | achat | 979 FCFA | 176 FCFA | 245 FCFA | 122 FCFA | 546 FCFA | 138 FCFA | 2 206 FCFA | 0,447 % | 0,5 % | 125 057 FCFA |
| ONTBF | achat | 942 FCFA | 170 FCFA | 236 FCFA | 118 FCFA | 756 FCFA | 186 FCFA | 2 408 FCFA | 0,642 % | 1,0 % | 120 339 FCFA |
| TTLC | achat | 933 FCFA | 168 FCFA | 233 FCFA | 117 FCFA | 624 FCFA | 197 FCFA | 2 272 FCFA | 0,535 % | 1,1 % | 119 048 FCFA |

- Achats : brut 9 650 560 FCFA, coûts 160 588 FCFA (explicites 120 052 FCFA, implicites estimés 40 536 FCFA), net 9 811 148 FCFA ; provision pire cas 9 866 731 FCFA
- Ventes : brut 0 FCFA, coûts 0 FCFA (explicites 0 FCFA, implicites estimés 0 FCFA), net 0 FCFA
- Coûts totaux du plan : 160 588 FCFA (1,61 % de la valeur du portefeuille)
- Frais fixes annuels estimés : garde 24 126 FCFA (0,25 % de l'encours) + tenue de compte 100 000 FCFA (20 lignes × 5 000 FCFA)
- Investi après ordres (au cours de référence) : 9 650 560 FCFA (96,51 %) pour une cible atteignable de 98,00 % (cible de la spécification : 98,00 %) ; reliquat de l'arrondi vers le bas 149 440 FCFA (reste en liquidités, §6) ; liquidités restantes estimées 188 852 FCFA (pire cas 133 269 FCFA)
- Scénario de coûts : central (courtage 0,80 % × (1 + TVA 18 %), BRVM 0,20 %, DC/BR 0,10 %, impact κ = 0,016)

### Messages du modèle (signalés)

- fenêtres comptées en séances (additif v1.1, D1) : 1 BOC manquants dans les 126 dernières séances ; seuils minimaux au prorata des BOC disponibles (planchers 40 / 20), bornes de rendement à 5 séances au plus
- modulateur du momentum : séries de performance des modulateurs (spread du momentum, TR de marché) restreintes à S0 (≥ 17/11/2022) : échantillon vierge S1 protégé ; validation_s1=True est réservé au test pré-enregistré
- notes de l'analyste prises en compte : 0 veto(s), 0 inclinaison(s), 8 titre(s) avec filtre R (mode direct : notes connues au 23/11/2026 14:30 UTC, appliquées à la séance du 24/11/2026)
- indice discipliné (additif v1.1, D8) : 20 plus grosses capitalisations éligibles, poids proportionnels à la capitalisation sous plafonds, 98,00 % investis (aucune promesse d'alpha)

## 3. Exécution : échéancier par séance

- 1 séance(s) du 24/11/2026 au 24/11/2026 ; participation ≤ 10 % de la MDV63 en valeur par séance
- Ventes d'abord ; règlement J+2 (depuis le 04/12/2025) : le produit d'une vente ne finance un achat qu'à partir de sa date de règlement ; liquidités initiales utilisées d'abord
- Prix limites : achat = min(borne haute ; dernier cours × 1,01) au pas inférieur ; vente = max(borne basse ; dernier cours × 0,99) au pas supérieur. Aucun achat si le titre cote à la borne haute, aucune vente à la borne basse : ordre reporté (au plus 10 séances, puis réévaluation)
- Jour ex et jour de division : la BRVM annule les ordres en attente ; les ressaisir le jour même
- Calendrier futur : jours ouvrés hors fériés à date fixe observés 2017-2026 (01/01, 01/05, 07/08, 15/08, 01/11, 15/11, 25/12) ; fêtes mobiles inconnues (hypothèse)
- Provision à avoir avant l'ordre : 9 866 731 FCFA. Part investie maximale à ce tarif : 97,81 % (la cible de 98 % n'est pas atteignable). Marge : +133 269 FCFA ; avec un courtage plus cher de 0,2 point : +110 269 FCFA [supposé] ; provision calculée sur un tarif supposé.

| Séance | Date | Titre | Sens | Titres | Limite | Montant réf. | Pire cas | Règlement | Financement |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 24/11/2026 | BICB | achat | 36 | 7 575 | 270 000 FCFA | 276 093 FCFA | 26/11/2026 | liquidités initiales |
| 1 | 24/11/2026 | BICC | achat | 10 | 31 310 | 310 000 FCFA | 316 995 FCFA | 26/11/2026 | liquidités initiales |
| 1 | 24/11/2026 | BOAB | achat | 25 | 9 185 | 227 375 FCFA | 232 482 FCFA | 26/11/2026 | liquidités initiales |
| 1 | 24/11/2026 | BOABF | achat | 27 | 7 775 | 207 900 FCFA | 212 536 FCFA | 26/11/2026 | liquidités initiales |
| 1 | 24/11/2026 | BOAC | achat | 25 | 11 100 | 274 875 FCFA | 280 953 FCFA | 26/11/2026 | liquidités initiales |
| 1 | 24/11/2026 | BOAS | achat | 22 | 7 775 | 169 400 FCFA | 173 177 FCFA | 26/11/2026 | liquidités initiales |
| 1 | 24/11/2026 | CBIBF | achat | 20 | 27 780 | 550 100 FCFA | 562 512 FCFA | 26/11/2026 | liquidités initiales |
| 1 | 24/11/2026 | CIEC | achat | 35 | 4 440 | 154 000 FCFA | 157 333 FCFA | 26/11/2026 | liquidités initiales |
| 1 | 24/11/2026 | ECOC | achat | 34 | 14 940 | 503 030 FCFA | 514 280 FCFA | 26/11/2026 | liquidités initiales |
| 1 | 24/11/2026 | NSBC | achat | 15 | 15 150 | 225 000 FCFA | 230 077 FCFA | 26/11/2026 | liquidités initiales |
| 1 | 24/11/2026 | NTLC | achat | 13 | 12 925 | 166 400 FCFA | 170 115 FCFA | 26/11/2026 | liquidités initiales |
| 1 | 24/11/2026 | ONTBF | achat | 42 | 2 830 | 117 810 FCFA | 120 339 FCFA | 26/11/2026 | liquidités initiales |
| 1 | 24/11/2026 | ORAC | achat | 94 | 19 440 | 1 809 500 FCFA | 1 850 092 FCFA | 26/11/2026 | liquidités initiales |
| 1 | 24/11/2026 | SGBC | achat | 19 | 39 180 | 737 105 FCFA | 753 680 FCFA | 26/11/2026 | liquidités initiales |
| 1 | 24/11/2026 | SIBC | achat | 62 | 8 280 | 508 400 FCFA | 519 746 FCFA | 26/11/2026 | liquidités initiales |
| 1 | 24/11/2026 | SLBC | achat | 10 | 40 905 | 405 000 FCFA | 414 138 FCFA | 26/11/2026 | liquidités initiales |
| 1 | 24/11/2026 | SNTS | achat | 629 | 4 080 | 2 541 160 FCFA | 2 598 246 FCFA | 26/11/2026 | liquidités initiales |
| 1 | 24/11/2026 | SPHC | achat | 16 | 7 720 | 122 320 FCFA | 125 057 FCFA | 26/11/2026 | liquidités initiales |
| 1 | 24/11/2026 | STBC | achat | 11 | 21 535 | 234 575 FCFA | 239 832 FCFA | 26/11/2026 | liquidités initiales |
| 1 | 24/11/2026 | TTLC | achat | 39 | 3 015 | 116 610 FCFA | 119 048 FCFA | 26/11/2026 | liquidités initiales |

## 4. Revenus attendus : dividendes sur 12 mois (estimation)

| Titre | Titres | Date ex prévue | Paiement prévu | Dernier net/titre | IRVM | Brut | IRVM (FCFA) | Net | Statut |
|---|---|---|---|---|---|---|---|---|---|
| BOABF | 27 | 29/04/2027 | 03/05/2027 | 397,00 | 12,5 % | 12 250 FCFA | 1 531 FCFA | 10 719 FCFA | prévu (estimation : dernier dividende reconduit) ; IRVM 12,5 % [NON VÉRIFIÉ] |
| BOAC | 25 | 10/05/2027 | 12/05/2027 | 594,53 | 12,0 % | 16 890 FCFA | 2 027 FCFA | 14 863 FCFA | prévu (estimation : dernier dividende reconduit) ; BOC du 20/11/2026 : dernier dividende 597,53 FCFA ; montant retenu 594,53 FCFA, lu sur la ligne (d) du détachement du 05/05/2026 (règle du §3.1 de la spécification) |
| SNTS | 629 | 17/05/2027 | 19/05/2027 | 174,00 | 10,0 % | 121 607 FCFA | 12 161 FCFA | 109 446 FCFA | prévu (estimation : dernier dividende reconduit) |
| BOAB | 25 | 24/05/2027 | 26/05/2027 | 585,00 | 10,0 % | 16 250 FCFA | 1 625 FCFA | 14 625 FCFA | prévu (estimation : dernier dividende reconduit) ; IRVM selon l'émetteur (inférences) |
| ECOC | 34 | 24/05/2027 | 26/05/2027 | 781,44 | 12,0 % | 30 192 FCFA | 3 623 FCFA | 26 569 FCFA | prévu (estimation : dernier dividende reconduit) |
| BOAS | 22 | 31/05/2027 | 02/06/2027 | 450,00 | 10,0 % | 11 000 FCFA | 1 100 FCFA | 9 900 FCFA | prévu (estimation : dernier dividende reconduit) |
| ORAC | 94 | 07/06/2027 | 09/06/2027 | 704,00 | 12,0 % | 75 200 FCFA | 9 024 FCFA | 66 176 FCFA | prévu (estimation : dernier dividende reconduit) |
| ONTBF | 42 | 14/06/2027 | 16/06/2027 | 145,32 | 12,5 % | 6 975 FCFA | 872 FCFA | 6 103 FCFA | prévu (estimation : dernier dividende reconduit) ; IRVM 12,5 % [NON VÉRIFIÉ] |
| CBIBF | 20 | 05/07/2027 | 07/07/2027 | 900,00 | 12,5 % | 20 571 FCFA | 2 571 FCFA | 18 000 FCFA | prévu (estimation : dernier dividende reconduit) ; IRVM 12,5 % [NON VÉRIFIÉ] |
| NSBC | 15 | 05/07/2027 | 07/07/2027 | 675,98 | 12,0 % | 11 522 FCFA | 1 382 FCFA | 10 140 FCFA | prévu (estimation : dernier dividende reconduit) |
| BICC | 10 | 14/07/2027 | 16/07/2027 | 1 157,20 | 12,0 % | 13 150 FCFA | 1 578 FCFA | 11 572 FCFA | prévu (estimation : dernier dividende reconduit) |
| SGBC | 19 | 20/07/2027 | 22/07/2027 | 2 298,75 | 12,0 % | 49 632 FCFA | 5 956 FCFA | 43 676 FCFA | prévu (estimation : dernier dividende reconduit) |
| STBC | 11 | 22/07/2027 | 26/07/2027 | 1 707,20 | 12,0 % | 21 340 FCFA | 2 561 FCFA | 18 779 FCFA | prévu (estimation : dernier dividende reconduit) |
| CIEC | 35 | 23/07/2027 | 27/07/2027 | 205,92 | 12,0 % | 8 190 FCFA | 983 FCFA | 7 207 FCFA | prévu (estimation : dernier dividende reconduit) |
| SIBC | 62 | 29/07/2027 | 02/08/2027 | 374,00 | 12,0 % | 26 350 FCFA | 3 162 FCFA | 23 188 FCFA | prévu (estimation : dernier dividende reconduit) |
| SLBC | 10 | 29/07/2027 | 02/08/2027 | 1 871,76 | 12,0 % | 21 270 FCFA | 2 552 FCFA | 18 718 FCFA | prévu (estimation : dernier dividende reconduit) |
| BICB | 36 | 30/07/2027 | 02/08/2027 | 254,60 | 5,0 % | 9 648 FCFA | 482 FCFA | 9 166 FCFA | prévu (estimation : dernier dividende reconduit) ; IRVM selon l'émetteur (inférences) |
| SPHC | 16 | 09/08/2027 | 11/08/2027 | 430,32 | 12,0 % | 7 824 FCFA | 939 FCFA | 6 885 FCFA | prévu (estimation : dernier dividende reconduit) |
| NTLC | 13 | 13/08/2027 | 17/08/2027 | 369,60 | 12,0 % | 5 460 FCFA | 655 FCFA | 4 805 FCFA | prévu (estimation : dernier dividende reconduit) |
| TTLC | 39 | 21/09/2027 | 23/09/2027 | 139,77 | 12,0 % | 6 194 FCFA | 743 FCFA | 5 451 FCFA | prévu (estimation : dernier dividende reconduit) |

Revenu net attendu 435 988 FCFA (brut 491 515 FCFA, IRVM 55 527 FCFA) ; rendement net du portefeuille 4,36 % de la valeur (4,52 % de l'investi). Dernier dividende reconduit : hypothèse, pas une promesse ; un dividende n'est acquis que si les titres sont détenus la veille du détachement.

## 5. Rendement net et pertes

> **Performance passée ≠ garantie. Aucun gain n'est garanti.**

**Étude seulement : aucune méthode de la plate-forme n'a réussi son test. Sur 2017-2022, la règle de référence, sans les notes, a fait 5,6 points de moins par an que le marché ; les notes n'ont jamais été testées.**

**Prochaine séance : aucun achat. Aucune méthode n'est validée : avec les règles actuelles, la plate-forme ne recommandera pas d'argent réel. Changer ces règles serait votre décision, jamais avant le 01/06/2027 (6 mois de suivi sur papier à partir du 01/12/2026).**

Tarif employé : Tarif supposé (central) (statut : supposé).

### Du brut au net

| Poste | Montant | Fréquence | Statut | Action possible | % du capital | % des dividendes bruts |
|---|---|---|---|---|---|---|
| Dividendes bruts attendus | 491 515 FCFA | par an | estimé | — | 4,92 % | 100,0 % |
| Impôt sur les dividendes | 55 527 FCFA | par an | supposé | aucune (retenu à la source) | 0,56 % | 11,3 % |
| Courtage | 77 204 FCFA | une fois | supposé | négociable | 0,77 % | 15,7 % |
| Taxe sur le courtage | 13 896 FCFA | une fois | supposé | à vérifier (une taxe ne se négocie pas) | 0,14 % | 2,8 % |
| Commission de la BRVM | 19 302 FCFA | une fois | compté | aucune | 0,19 % | 3,9 % |
| Commission du dépositaire (DC/BR) | 9 650 FCFA | une fois | compté | aucune | 0,10 % | 2,0 % |
| Écart entre acheteurs et vendeurs | 24 806 FCFA | une fois | estimé | exécution | 0,25 % | 5,0 % |
| Effet de l'ordre sur le prix | 15 730 FCFA | une fois | estimé | exécution | 0,16 % | 3,2 % |
| Droits de garde | 24 126 FCFA | par an | supposé | négociable | 0,24 % | 4,9 % |
| Tenue de compte par ligne | 100 000 FCFA | par an | supposé | selon le courtier | 1,00 % | 20,3 % |
| Forfait de compte | 0 FCFA | par an | supposé | selon le courtier | 0,00 % | 0,0 % |
| Taxe sur les frais annuels | 0 FCFA | par an | supposé | à vérifier | 0,00 % | 0,0 % |
| Encaissement des dividendes | 0 FCFA | par an | supposé | selon le courtier | 0,00 % | 0,0 % |

- Frais et impôt de la 1re année : 340 241 FCFA (3,40 % du capital) ; années suivantes, sans transaction : 179 653 FCFA
- Dividendes moins frais : 1re année +151 274 FCFA ; années suivantes, sans transaction +311 862 FCFA [estimé]
- Part supposée ou estimée (statut le plus faible) : 91,5 % de la facture (311 289 FCFA) ; 89,8 % des seuls frais (255 762 FCFA)
- Ce qui la lèverait : la grille écrite 215 226 FCFA ; l'avis d'opéré (exécution) 40 536 FCFA ; le taux d'impôt non vérifié 7 081 FCFA ; le paiement des dividendes estimés 48 446 FCFA
- Par action possible : aucune 84 479 FCFA ; négociable 101 330 FCFA ; selon le courtier 100 000 FCFA ; à vérifier 13 896 FCFA ; exécution 40 536 FCFA
- Contrôle : dividendes bruts − (frais et impôt) = dividendes moins frais, écart 0 FCFA
- Si les dividendes baissent de 7,5 % : 1re année +118 575 FCFA ; ensuite +279 163 FCFA
- Si les dividendes baissent de 20,0 % : 1re année +64 076 FCFA ; ensuite +224 664 FCFA
- Remise à niveau de janvier et sorties forcées (hors totaux) : Estimation ; à mesurer pendant le suivi sur papier : 34 745 FCFA à 123 000 FCFA par an
- Aller-retour : 321 176 FCFA (3,33 % de l'investi)
- Variations de cours : non comptées. Les cours peuvent monter ou baisser bien plus que ces montants.
- Impôt sur les plus-values : non compté (0 supposé, non vérifié).
- Ces frais n'existent que si vous achetez. Montants calculés sur un tarif supposé tant que la grille de votre courtier n'est pas saisie.

### Frais évités par rapport au tarif supposé

Frais évités par rapport au tarif supposé ; 0 si votre courtier ne facture pas ce poste.

| Geste | Une fois | Par an | 1re année | Condition | Contrepartie |
|---|---|---|---|---|---|
| Courtier sans tenue de compte par ligne | 0 FCFA | 100 000 FCFA | — | si votre courtier facture 5 000 FCFA par ligne | changer de courtier ; courtage peut-être plus élevé ; transfert de 5 000 à 34 375 FCFA par ligne si des titres sont déjà détenus |
| Droits de garde à 0,10 % au lieu de 0,25 % | 0 FCFA | 14 475 FCFA | — | si le taux est obtenu par écrit | aucune connue |
| Courtage à 0,50 % au lieu de 0,80 % | 34 158 FCFA | sur chaque ordre futur | — | si le taux est obtenu par écrit | aucune connue ; le taux réel de départ est inconnu |
| Ensemble, avec la grille connue sans frais par ligne (courtage 1,00 %, forfait 4 000) | surcoût de 22 776 FCFA | 96 000 FCFA | 73 224 FCFA | grille homologuée lue ; non confirmée pour vous | courtage plus élevé à l'entrée (+22 776 FCFA) |
| Borne non attestée (0,50 % et aucun frais par ligne) | 34 158 FCFA | 96 000 FCFA | 130 158 FCFA | aucune grille lue ne cumule ces avantages | — |

### Inconnues à lever

- Taxe sur le courtage : de 0 à 13 896 FCFA (6 175 de moins si elle est de 10 %)
- Minimum par ordre : +13 841 FCFA s'il est de 2 500 FCFA
- Taxe sur les frais annuels : +22 343 FCFA par an si elle est de 18 %
- Impôt sur les plus-values : non compté

### Ce que j'accepte de risquer

Chocs par franc investi [estimé] : marché de 2018 × sensibilité du panier 23,97 % ; choc subi par la règle de référence dans son test publié 29,32 % (mesuré, lecture d'un résultat publié, pas un test) ; retenu 29,32 % ; pire moment de 2018 31,52 % ; baisse de 2017-2020 44,61 %.

| Je risque | En actions | En réserve | Année comme 2018 | Pire moment de 2018 | Si 2017-2020 revenait | Dividendes moins frais (1re année ; ensuite) | Année ordinaire (prudente) | Année ordinaire (flatteuse) |
|---|---|---|---|---|---|---|---|---|
| 500 000 FCFA | 1 400 000 FCFA | 8 600 000 FCFA | −410 532 FCFA à −474 919 FCFA | −501 430 FCFA (dépasse) | −659 065 FCFA (dépasse) | −67 825 FCFA ; −49 110 FCFA | −10 489 FCFA | +46 172 FCFA |
| 1 000 000 FCFA | 3 000 000 FCFA | 7 000 000 FCFA | −824 753 FCFA à −974 805 FCFA | −1 036 590 FCFA (dépasse) | −1 403 953 FCFA (dépasse) | −25 707 FCFA ; +18 977 FCFA | +118 001 FCFA | +263 350 FCFA |
| 2 000 000 FCFA | 6 300 000 FCFA | 3 700 000 FCFA | −1 653 624 FCFA à −1 974 832 FCFA | −2 107 091 FCFA (dépasse) | −2 893 483 FCFA (dépasse) | +59 016 FCFA ; +156 855 FCFA | +374 746 FCFA | +690 914 FCFA |
| tout | 10 000 000 FCFA | 0 FCFA | −2 598 431 FCFA à −3 114 258 FCFA | −3 326 652 FCFA | −4 589 518 FCFA | +151 274 FCFA ; +311 862 FCFA | +664 187 FCFA | +1 179 300 FCFA |

La lecture « passé rejoué » rejoue les gagnants d'aujourd'hui : elle flatte. Le seul test réel de la règle de référence a donné 5,6 points de moins par an que le marché.

- Fréquences d'un seul passé (2017-2026 : quatre années de baisse, puis six de hausse). Ce ne sont pas des probabilités. Descriptif, pas un test. Ce que vous acceptez de risquer n'est pas une limite. Une baisse plus forte a existé : le marché a perdu 46,7 % de mars 2017 à octobre 2020. Les intérêts de la réserve ne sont jamais déduits de la perte estimée.

- Un titre en moins (choc de 30 %) : SONATEL SN 762 348 FCFA (7,6 % du capital) [estimé]
- Un titre en moins (choc de 30 %) : ORANGE COTE D'IVOIRE 542 850 FCFA (5,4 % du capital) [estimé]
- Un titre en moins (choc de 30 %) : SOCIETE GENERALE COTE D'IVOIRE 221 132 FCFA (2,2 % du capital) [estimé]
- Un titre en moins (choc de 30 %) : CORIS BANK INTERNATIONAL 165 030 FCFA (1,7 % du capital) [estimé]
- Un titre en moins (choc de 30 %) : SOCIETE IVOIRIENNE DE BANQUE 152 520 FCFA (1,5 % du capital) [estimé]
- Un titre en moins (choc de 30 %) : ECOBANK COTE D'IVOIRE 150 909 FCFA (1,5 % du capital) [estimé]
- Poids des deux premières lignes : 43,5 % ; lignes effectives 7,9

### Où dort le reste

- Réserve 10 000 000 FCFA ; taux inconnu : compté à 0 % ; un point d'intérêt vaut 100 000 FCFA par an ; intérêts attendus 0 FCFA [supposé], montrés à part
- Les intérêts de la réserve ne sont jamais déduits de la perte estimée.

### Argent qui dort et provision

- 200 000 + 149 440 − 160 588 = 188 852 FCFA [estimé]
- Liquidités après les ordres : 188 852 FCFA (1,9 %), sous la réserve de 2 % de la règle : aucun argent ne dort au-delà. [estimé]
- Réserve de fonctionnement (information) : de quoi payer les frais fixes de 2 trimestres (62 063 FCFA) ou 3 trimestres (93 095 FCFA). [supposé]
- Provision à avoir avant l'ordre : 9 866 731 FCFA. Part investie maximale à ce tarif : 97,81 % (la cible de 98 % n'est pas atteignable). Marge : +133 269 FCFA ; avec un courtage plus cher de 0,2 point : +110 269 FCFA [supposé] ; provision calculée sur un tarif supposé.
- Avec l'arrondi « plus forts restes » : +65 485 FCFA placés (97,16 % au lieu de 96,51 %), marge du pire cas 66 323 FCFA. Option --arrondi restes, écart à la règle testée. Gain ou perte selon le marché. [compté]
- Projection à cours constants (compte des francs, ne prévoit rien) : dividendes 435 988 FCFA en 20 paiements ; liquidités moyennes 388 760 FCFA de février à janvier ; pointe 550 704 FCFA ; à la remise à niveau 488 131 FCFA [estimé].

### Argent placé en plus : gain ou perte selon le marché

Placer plus, c'est gagner plus si le marché monte et perdre plus s'il baisse.

| Changement | Francs placés en plus | Dividendes attendus [estimé] | Année ordinaire du passé (prudente à flatteuse) | Une année sur dix (flatteuse ; prudente ; périodes réelles) | Nature |
|---|---|---|---|---|---|
| Arrondi « plus forts restes » (F13c) | 65 485 FCFA | +2 958 FCFA par an | +4 349 FCFA à +7 723 FCFA | −6 452 FCFA ; −8 550 FCFA ; −12 738 FCFA | option, écart déclaré |
| Réinvestissement mensuel (F13d, règle corrigée) | 127 497 FCFA en moyenne | +5 760 FCFA par an | +8 468 FCFA à +15 036 FCFA | −12 562 FCFA ; −16 647 FCFA ; −24 800 FCFA | option, essai E-D |

Fréquences d'un seul passé (2017-2026 : quatre années de baisse, puis six de hausse). Ce ne sont pas des probabilités. Descriptif, pas un test.

Les lignes du tableau B se recoupent : elles ne s'additionnent pas. La lecture « passé rejoué » rejoue les gagnants d'aujourd'hui : elle flatte. Le seul test réel de la règle de référence a donné 5,6 points de moins par an que le marché.

### Passer l'ordre

- Vos ordres sont à cours limité. Certaines lignes peuvent ne pas être servies le jour même, ou seulement en partie.
- Horaires (heure d'Abidjan) : saisie avant l'ouverture de 9 h 00 à 9 h 45 ; cotation en continu jusqu'à 14 h 00 ; fixing de clôture à 14 h 30 ; négociation au dernier cours jusqu'à 15 h 00.
- Demandez une validité de plusieurs séances (10 au plus). La plate-forme réévalue ensuite.
- Le jour d'un détachement de dividende ou d'une division, la BRVM annule les ordres en attente : il faut les ressaisir.
- Le produit d'une vente n'est disponible que deux jours de bourse plus tard.
- Après quelques séances, relancez la commande avec ce que vous détenez vraiment.
- Au dernier carnet, 5 lignes ont un prix demandé au-dessus de votre limite et 5 n'offrent pas assez de titres au meilleur prix.

### Points à vérifier

- FUITE : Les frais annuels du courtier (124 126 FCFA) prennent 28 % des dividendes nets attendus (435 988 FCFA) [supposé].
- Tarif non vérifié : 90 % des frais de la 1re année sont supposés ou estimés (255 762 sur 284 714 FCFA). Envoyez les 8 questions à votre courtier.
- FUITE : 1 ligne(s) coûtent plus qu'elles ne versent en dividendes, en FCFA par an [supposé] : NTLC (5 416 de frais pour 4 805 de dividende).

### Détail ligne par ligne : frais annuels contre dividende attendu

| Titre | Frais annuels | Dividende net attendu | Rapport | Niveau | Statut |
|---|---|---|---|---|---|
| NTLC | 5 416 FCFA | 4 805 FCFA | 113 % | rouge | frais supposé ; dividende estimé |
| TTLC | 5 292 FCFA | 5 451 FCFA | 97 % | orange | frais supposé ; dividende estimé |
| ONTBF | 5 295 FCFA | 6 103 FCFA | 87 % | orange | frais supposé ; dividende estimé |
| SPHC | 5 306 FCFA | 6 885 FCFA | 77 % | orange | frais supposé ; dividende estimé |
| CIEC | 5 385 FCFA | 7 207 FCFA | 75 % | orange | frais supposé ; dividende estimé |
| BICB | 5 675 FCFA | 9 166 FCFA | 62 % | orange | frais supposé ; dividende estimé |
| NSBC | 5 563 FCFA | 10 140 FCFA | 55 % | orange | frais supposé ; dividende estimé |
| BOAS | 5 424 FCFA | 9 900 FCFA | 55 % | orange | frais supposé ; dividende estimé |
| BOABF | 5 520 FCFA | 10 719 FCFA | 51 % | orange | frais supposé ; dividende estimé |
| BICC | 5 775 FCFA | 11 572 FCFA | 50 % | — | frais supposé ; dividende estimé |
| BOAC | 5 687 FCFA | 14 863 FCFA | 38 % | — | frais supposé ; dividende estimé |
| BOAB | 5 568 FCFA | 14 625 FCFA | 38 % | — | frais supposé ; dividende estimé |
| CBIBF | 6 375 FCFA | 18 000 FCFA | 35 % | — | frais supposé ; dividende estimé |
| SLBC | 6 013 FCFA | 18 718 FCFA | 32 % | — | frais supposé ; dividende estimé |
| STBC | 5 586 FCFA | 18 779 FCFA | 30 % | — | frais supposé ; dividende estimé |
| SIBC | 6 271 FCFA | 23 188 FCFA | 27 % | — | frais supposé ; dividende estimé |
| ECOC | 6 258 FCFA | 26 569 FCFA | 24 % | — | frais supposé ; dividende estimé |
| SGBC | 6 843 FCFA | 43 676 FCFA | 16 % | — | frais supposé ; dividende estimé |
| ORAC | 9 524 FCFA | 66 176 FCFA | 14 % | — | frais supposé ; dividende estimé |
| SNTS | 11 353 FCFA | 109 446 FCFA | 10 % | — | frais supposé ; dividende estimé |

### Projection des liquidités par mois (cours constants, estimation)

| Mois | Liquidités en fin de mois | Dividendes du mois |
|---|---|---|
| 2026-11 | 188 852 FCFA | 0 FCFA |
| 2026-12 | 176 269 FCFA | 0 FCFA |
| 2027-01 | 176 269 FCFA | 0 FCFA |
| 2027-02 | 176 269 FCFA | 0 FCFA |
| 2027-03 | 145 663 FCFA | 0 FCFA |
| 2027-04 | 145 663 FCFA | 0 FCFA |
| 2027-05 | 321 885 FCFA | 176 222 FCFA |
| 2027-06 | 373 117 FCFA | 82 179 FCFA |
| 2027-07 | 482 491 FCFA | 109 374 FCFA |
| 2027-08 | 545 253 FCFA | 62 762 FCFA |
| 2027-09 | 519 418 FCFA | 5 451 FCFA |
| 2027-10 | 519 418 FCFA | 0 FCFA |
| 2027-11 | 519 418 FCFA | 0 FCFA |
| 2027-12 | 488 131 FCFA | 0 FCFA |
| 2028-01 | 488 131 FCFA | 0 FCFA |

> **Performance passée ≠ garantie. Aucun gain n'est garanti.**

Valorisation du marché « cher » (prime du BOC 0,58 < 1 %) : les stress sont affichés en premier (§4.5) ; l'exposition ne change pas.

## 6. Scénarios de stress (§9.3)

Source : brvm_alpha.portfolio.stress.stress_tests.

| Code | Scénario | Perte | En % de la valeur | Hypothèse | Base |
|---|---|---|---|---|---|
| ST1 | marché baissier long : chemin du TR du 01/03/2017 au 26/10/2020 (−46,7 %) — TR | −4 304 804 FCFA | −43,0 % | β 104 semaines (hebdomadaire) 0,96, borné à 0,96, jusqu'au 20/11/2026, depuis le 29/11/2024 (aucune donnée de S1) | [C-SPEC] §1.1 (fait mesuré) |
| ST1 | marché baissier long : Composite prix depuis fin 2015 (−59,8 % en 58 mois) — prix | −5 512 361 FCFA | −55,1 % | β 104 semaines (hebdomadaire) 0,96, borné à 0,96, jusqu'au 20/11/2026, depuis le 29/11/2024 (aucune donnée de S1) ; dividendes non comptés | [R08] §4.3 |
| ST2 | pire année (2018 : TR reconstruit −25,1 %) — TR | −2 313 717 FCFA | −23,1 % | β 104 semaines (hebdomadaire) 0,96, borné à 0,96, jusqu'au 20/11/2026, depuis le 29/11/2024 (aucune donnée de S1) | [C-SPEC] ; [R08] |
| ST2 | pire année (2018 : baisse intra-annuelle maximale du Composite −33,0 %) — intra-annuel | −3 041 938 FCFA | −30,4 % | β 104 semaines (hebdomadaire) 0,96, borné à 0,96, jusqu'au 20/11/2026, depuis le 29/11/2024 (aucune donnée de S1) | [R08] |
| ST3 | correction rapide (−15 % en 8 semaines ; pire 8 semaines observé −14,3 %) | −1 382 699 FCFA | −13,8 % | β 104 semaines (hebdomadaire) 0,96, borné à 0,96, jusqu'au 20/11/2026, depuis le 29/11/2024 (aucune donnée de S1) | [R04] §12.4 |
| ST4 | choc pays sévère AES (sanctions, gel BCEAO) : −21 % sur BF, ML, NE — sévère 21 % | −310 927 FCFA | −3,1 % | exposition λ AES 14,81 % du capital (siège ; filiales pour SNTS : ML 0,238) | §4.3 ; §11 macro.jump_loss ; [R05] §12 |
| ST4 | choc pays sévère AES : −26 % en 9 séances, dont 3 au plancher sans vendeur servi (rejeu Niger 2023) — stress 26 % (Niger 2023) | −384 958 FCFA | −3,8 % | exposition λ AES 14,81 % du capital (siège ; filiales pour SNTS : ML 0,238) ; aucune vente possible avant la 4ᵉ séance | [R05] §9 |
| ST4 | variante Mali 2022 : plancher dès t+1, −16,9 % en 3 séances sur ML — Mali 2022 | −102 211 FCFA | −1,0 % | exposition λ ML 6,05 % du capital | [R05] §9 |
| ST4 | coup d'État sans sanctions UEMOA : −8 % sur BF, ML, NE — modéré 8 % | −118 448 FCFA | −1,2 % | exposition λ AES 14,81 % du capital (siège ; filiales pour SNTS : ML 0,238) | §4.3 ; [R05] §12 |
| ST5 | stress souverain Sénégal : −9 % relatif en 60 séances (audit 2024) sur les titres sénégalais — relatif −9 % | −243 950 FCFA | −2,4 % | titres SN détenus : SNTS, BOAS (27,11 %) ; marché supposé stable | [R05] §9 |
| ST5 | stress souverain Sénégal : −26 % sur BOAS et SNTS — stress −26 % | −704 746 FCFA | −7,0 % | BOAS + SNTS : 27,11 % du capital (hypothèse de stress) | [R05] §9, §12 |
| ST6 | liquidité : participation divisée par 2 (5 %) et demi-spread × 2 pendant 20 séances (liquidation complète) | −204 195 FCFA | −2,0 % | coût de sortie 2,12 % de la valeur investie (normal, 10 % de participation : 2,01 %) ; non liquidable en 20 séances : 0 FCFA ; ligne la plus lente : ORAC (0,6 séances à 5 %) | hypothèse de conception ; §7.2 |
| ST7 | coûts : scénario sévère du §7.2 sur 12 mois (courtage 1,5 %, demi-spread × 2, κ = 0,05, garde 0,5 %, 10 000 FCFA par ligne) | −1 214 311 FCFA | −12,1 % | rotation 15 %/mois aller (objectif du §6, hypothèse) ; coûts centraux sur 12 mois : 667 475 FCFA ; surcoût du scénario sévère : 546 836 FCFA | §7.2 |
| ST8 | suspension de la plus grosse ligne (SNTS, 25,41 %) pendant 60 séances, valorisée −10 % — −10 % | −254 116 FCFA | −2,5 % | valorisation de risque (§7.1.7) | [R07] §4.7 |
| ST8 | suspension de la plus grosse ligne (SNTS) : valorisée −30 % (stress) — −30 % | −762 348 FCFA | −7,6 % | hypothèse de stress | [R07] §4.7 |
| ST9 | erreur de données : division non ajustée sur SNTS (faux −89,3 %) | 0 FCFA | 0,0 % | contrôle BLOQUANT vérifié (BrvmAlpha.risk_flags : data_guard (\|rendement\| > 50 %)) : signaux de SNTS bloqués ; perte apparente évitée 2 269 256 FCFA | [R08] §1 |
| ST10 | rupture de parité ou sortie de l'UEMOA : règle « sévère » sur les titres AES et les filiales de SNTS — sévère 21 % | −503 573 FCFA | −5,0 % | exposition 23,98 % du capital (AES ; SNTS : ML, GN, SL, GW) ; perte de change NON chiffrée (aucune source) | [R05] §7 |
| ST10 | rupture de parité ou sortie de l'UEMOA : règle « sévère » sur les titres AES et les filiales de SNTS — stress 26 % | −623 471 FCFA | −6,2 % | exposition 23,98 % du capital (AES ; SNTS : ML, GN, SL, GW) ; perte de change NON chiffrée (aucune source) | [R05] §7 |

## 7. Distribution historique à 12 mois (pas une prévision)

Bootstrap stationnaire (5 000 tirages, blocs moyens de 8 semaines, graine 0) des rendements hebdomadaires TR des lignes aux poids réalisés et du Composite TR, tirés ensemble ; fenêtre toute l'histoire 2017-2026 (le registre indique que le test unique S1 a été exécuté) (492 semaines, du 06/01/2017 au 20/11/2026). Nets des coûts du plan et des frais fixes de l'horizon (2,85 %). C'est une distribution historique, pas une prévision.

> ⚠ Biais rétrospectif : poids actuels et sélection d'aujourd'hui (plus grosses capitalisations au 20/11/2026) appliqués à toute l'histoire 2017-2026 ; les titres alors en difficulté ou radiés n'y figurent pas, ce qui flatte la distribution. Lignes sans historique complet : ORAC (18,1 %, depuis le 06/01/2023), ECOC (5,0 %, depuis le 15/12/2017), BICB (2,7 %, depuis le 02/05/2025), NSBC (2,2 %, depuis le 27/10/2017), soit 28,1 % du portefeuille ; 790 valeur(s) antérieure(s) à la cotation : poids renormalisés sur les lignes cotées (et non comptées à 0 %). 0 valeur(s) manquante(s) après cotation (suspensions) comptée(s) à 0 %.

> ⚠ Résultat du test unique S1 (metrics.json, fait de simulation) : la variante appliquée REF fait −5,6 % par an contre le Composite TR (statut REJETÉ). La P(battre le TR) de la distribution à 12 mois est une fréquence historique aux poids actuels, pas une probabilité de surperformance future.

| Mesure | Portefeuille (net) | Composite TR |
|---|---|---|
| Médiane | +11,8 % (11 179 300 FCFA) | +10,1 % |
| P10 | −9,9 % (9 014 738 FCFA) | −10,9 % |
| P90 | +37,6 % (13 763 475 FCFA) | +35,4 % |
| P(perte) | 25,6 % | — |
| Fréquence passée au-dessus du marché, aux poids d'aujourd'hui (flatteuse : le test S1 a donné −5,6 points par an) | 62,4 % (fréquence historique aux poids actuels) | test S1 : REF −5,6 %/an contre le TR (REJETÉ) |
| Rendement des dividendes (net) | 4,36 % | inclus dans le TR |
| Rendement annualisé du TR sur la fenêtre (fait) | — (poids actuels : biais rétrospectif) | +10,2 % |
| Volatilité annualisée (hebdo) | 11,7 % | 11,6 % |
| β hebdomadaire contre le TR (06/01/2017 → 20/11/2026) | 0,94 | 1 |

### Lectures du risque : plusieurs lectures d'un seul passé

| Lecture | Périodes en perte (graine 0 ; médiane des graines) | Année ordinaire | Une année sur dix | Une année sur vingt | Pire tirage |
|---|---|---|---|---|---|
| Passé rejoué, blocs de 8 semaines | 25,6 % ; 25,5 % | +11,8 % ; +11,8 % | −9,9 % ; −9,9 % | −15,0 % ; −15,4 % | −39,1 % |
| Marché chargé des mêmes frais, blocs de 8 semaines | 34,1 % ; 34,6 % | +6,6 % ; +6,4 % | −13,1 % ; −13,1 % | −17,5 % ; −17,9 % | — |
| Passé rejoué, blocs de 26 semaines | 30,0 % ; 30,6 % | +13,0 % ; +12,6 % | −14,8 % ; −14,8 % | −22,1 % ; −21,8 % | −42,2 % |
| Marché chargé des mêmes frais, blocs de 26 semaines | 37,6 % ; 38,2 % | +7,4 % ; +6,9 % | −17,1 % ; −17,3 % | −22,9 % ; −22,9 % | — |
| Passé rejoué, blocs de 52 semaines | 31,8 % ; 32,8 % | +16,0 % ; +13,7 % | −16,4 % ; −16,6 % | −24,6 % ; −24,9 % | −44,1 % |
| Marché chargé des mêmes frais, blocs de 52 semaines | 38,1 % ; 39,6 % | +9,1 % ; +7,3 % | −19,0 % ; −19,3 % | −24,4 % ; −24,5 % | — |
| Périodes réellement observées | 37 sur 107 (34,6 %) | — | −19,45 % | — | −26,7 % (départ 2018-03) |

Fréquences d'un seul passé (2017-2026 : quatre années de baisse, puis six de hausse). Ce ne sont pas des probabilités. Descriptif, pas un test. Selon la façon de compter et le tirage, environ 25 % à 40 % des périodes de 12 mois ont fini en perte, et une année sur dix a fini sous −10 % à −19 %.

La lecture « passé rejoué » rejoue les gagnants d'aujourd'hui : elle flatte. Le seul test réel de la règle de référence a donné 5,6 points de moins par an que le marché.

Libellé : « Fréquence passée au-dessus du marché, aux poids d'aujourd'hui (flatteuse : le test S1 a donné −5,6 points par an) ».

## 8. Déclencheurs de revue

- Prochaine revue mensuelle (dernière séance du mois) : 30/11/2026
- Rebalancement annuel de l'indice discipliné (première décision de janvier) : 29/01/2027 ; entre deux, seules les sorties forcées s'appliquent
- Début du suivi réel S2 (§8.1) : 01/12/2026
- Filtres R actifs sur les lignes : NSBC (R10); BOAB (R11×1); BOABF (R11×1); TTLC (R12)
- Légende des filtres : R10 : résultat net en baisse de 25 % ou plus sans alerte préalable (surveillance, qualité −0,5) ; R11 : drapeau des financières (§5.6 : payout brut > 1, coût du risque, créances douteuses, solvabilité… ; un drapeau : poids maximal × 0,5 ; deux ou plus : exclusion) ; R12 : drapeau des non financières (§5.6 : payout > 100 % deux ans de suite, bénéfice non récurrent ou rendement > 15 % ; poids maximal × 0,5) ; « ×N » : nombre de drapeaux levés
- Drawdown relatif contre le TR : aucun historique de suivi réel (mesuré depuis le premier jour investi, D5) ; seuils à surveiller : −10 % alerte, −15 % exposition active ÷ 2, −20 % arrêt et indice discipliné
- À revoir avant achat NSBC : −29,4 % contre le TR sur 63 séances (seuil de revue −25 %, §9.1) ; l'achat reste proposé, la revue est à faire par l'utilisateur avant de transmettre l'ordre
- À revoir avant achat CIEC : −32,3 % contre le TR sur 63 séances (seuil de revue −25 %, §9.1) ; l'achat reste proposé, la revue est à faire par l'utilisateur avant de transmettre l'ordre
- Notes de l'analyste : 0 veto(s), 0 inclinaison(s), 8 titre(s) avec filtre R issu des notes
- Notes connues au 23/11/2026 14:30 UTC, appliquées à la séance du 24/11/2026 : 114 en vigueur (dont 0 manuelles), 8 filtre(s) de risque actif(s) ; achats bloqués : ETIT, SEMC, SICC.
- Scores des notes : 41 note(s) en vigueur sur 114 portent un score directionnel non nul.
- Filtre R2 sur ETIT (annulation ou report d'AG : −1 en gouvernance, aucun achat (60 séances)) depuis le 26/10/2026, jusqu'au 19/01/2027 — note 4a46238f820f du 23/10/2026 « ETI TG : Communiqué - Annulation de l'Assemblée Générale Ordinaire » ; achats bloqués ; titre hors du plan
- Filtre R10 sur FTSC (ΔRN ≤ −25 % sans alerte sur résultats préalable (depuis le 01/10/2025)) depuis le 04/11/2026, jusqu'au 22/04/2027 — note 267c82b0e226 du 03/11/2026 « FILTISAC CI : Rapport d'activités - 1er semestre 2026 » ; titre hors du plan
- Filtre R10 sur FTSC (ΔRN ≤ −25 % sans alerte sur résultats préalable (depuis le 01/10/2025)) depuis le 04/11/2026, jusqu'au 22/04/2027 — note db5a70ec3bd2 du 03/11/2026 « FILTISAC CI : Rapport d'activités - 3e trimestre 2026 - (Annule et remplace le précédent) » ; titre hors du plan
- Filtre R10 sur NSBC (ΔRN ≤ −25 % sans alerte sur résultats préalable (depuis le 01/10/2025)) depuis le 03/11/2026, jusqu'au 21/04/2027 — note a7b94e0c53cd du 02/11/2026 « NSIA BANQUE CI : Rapport d'activités - 3e trimestre 2026 »
- Filtre R10 sur PALC (ΔRN ≤ −25 % sans alerte sur résultats préalable (depuis le 01/10/2025)) depuis le 09/10/2026, jusqu'au 29/03/2027 — note 9b1cd08a8448 du 08/10/2026 « PALM CI : Rapport d'activités - 1er semestre 2026 » ; titre hors du plan
- Filtre R1 sur SEMC (suspension : aucun achat, alerte sur les positions (jusqu'à la reprise + 5 séances)) depuis le 17/09/2026, jusqu'à la reprise de cotation + 5 séances — note e648d82ebd87 du 16/09/2026 « SEMC : cotation suspendue (mention SP depuis le BOC du 16/09/2026) » ; achats bloqués ; titre hors du plan
- Filtre R1 sur SICC (suspension : aucun achat, alerte sur les positions (jusqu'à la reprise + 5 séances)) depuis le 17/09/2026, jusqu'à la reprise de cotation + 5 séances — note 6771f0ac46eb du 16/09/2026 « SICC : cotation suspendue (mention SP depuis le BOC du 16/09/2026) » ; achats bloqués ; titre hors du plan
- Filtre R10 sur SOGC (ΔRN ≤ −25 % sans alerte sur résultats préalable (depuis le 01/10/2025)) depuis le 03/11/2026, jusqu'au 21/04/2027 — note 67f51ea73342 du 02/11/2026 « SOGB CI : Rapport d'activités - 3e trimestre 2026 » ; titre hors du plan
- Filtre R10 sur STAC (ΔRN ≤ −25 % sans alerte sur résultats préalable (depuis le 01/10/2025)) depuis le 03/11/2026, jusqu'au 21/04/2027 — note 3f8539dbea39 du 02/11/2026 « SETAO CI : Rapport d'activités - 1er semestre 2026 » ; titre hors du plan
- Règles pays actives : aucune ; aucun événement pays daté à venir dans reference.COUNTRY_EVENTS (horizon 12 mois)

### Événements à venir (12 mois)

| Date | Type | Cible | Description | Nature |
|---|---|---|---|---|
| 01/12/2026 | suivi réel | plate-forme | début du suivi réel S2 (paper trading, §8.1) | fait (protocole) |
| 04/01/2027 | révision du BRVM 30 | IDX:BRVM-30 | révision trimestrielle de la composition (information seulement, §5.5) | fait (calendrier ; date de séance estimée) |
| 01/02/2027 | publication attendue | CIEC | activité du T3 (dernière connue : 01/02/2024, + 3 an(s)) | estimation (historique des notes) |
| 17/02/2027 | publication attendue | SNTS | comptes annuels (dernière connue : 17/02/2026, + 1 an(s)) | estimation (historique des notes) |
| 18/03/2027 | AGO estimée | BOABF | date ex − 42 jours (médiane §5.4) | estimation |
| 18/03/2027 | publication attendue | BOAS | comptes annuels (dernière connue : 18/03/2026, + 1 an(s)) | estimation (historique des notes) |
| 19/03/2027 | publication attendue | SPHC | comptes annuels (dernière connue : 19/03/2026, + 1 an(s)) | estimation (historique des notes) |
| 24/03/2027 | publication attendue | BOABF | comptes annuels (dernière connue : 24/03/2026, + 1 an(s)) | estimation (historique des notes) |
| 29/03/2027 | AGO estimée | BOAC | date ex − 42 jours (médiane §5.4) | estimation |
| 01/04/2027 | révision du BRVM 30 | IDX:BRVM-30 | révision trimestrielle de la composition (information seulement, §5.5) | fait (calendrier ; date de séance estimée) |
| 05/04/2027 | AGO estimée | SNTS | date ex − 42 jours (médiane §5.4) | estimation |
| 12/04/2027 | AGO estimée | BOAB | date ex − 42 jours (médiane §5.4) | estimation |
| 12/04/2027 | AGO estimée | ECOC | date ex − 42 jours (médiane §5.4) | estimation |
| 15/04/2027 | publication attendue | ECOC | comptes annuels (dernière connue : 15/04/2026, + 1 an(s)) | estimation (historique des notes) |
| 16/04/2027 | publication attendue | BOAB | comptes annuels (dernière connue : 16/04/2026, + 1 an(s)) | estimation (historique des notes) |
| 17/04/2027 | publication attendue | SGBC | comptes annuels (dernière connue : 17/04/2026, + 1 an(s)) | estimation (historique des notes) |
| 19/04/2027 | AGO estimée | BOAS | date ex − 42 jours (médiane §5.4) | estimation |
| 20/04/2027 | publication attendue | BICC | comptes annuels (dernière connue : 20/04/2026, + 1 an(s)) | estimation (historique des notes) |
| 20/04/2027 | publication attendue | SNTS | activité du T1 (dernière connue : 20/04/2026, + 1 an(s)) | estimation (historique des notes) |
| 22/04/2027 | publication attendue | SIBC | comptes annuels (dernière connue : 22/04/2026, + 1 an(s)) | estimation (historique des notes) |
| 23/04/2027 | publication attendue | BOAS | activité du T1 (dernière connue : 23/04/2026, + 1 an(s)) | estimation (historique des notes) |
| 23/04/2027 | publication attendue | TTLC | activité du T1 (dernière connue : 23/04/2026, + 1 an(s)) | estimation (historique des notes) |
| 26/04/2027 | AGO estimée | ORAC | date ex − 42 jours (médiane §5.4) | estimation |
| 29/04/2027 | détachement prévu | BOABF | 397,00 FCFA net/titre, soit 10 719 FCFA payés vers le 03/05/2027 ; une vente programmée est reportée au jour ex si le rendement net ≥ 4 % (§5.2.6) | estimation (mois habituel) |
| 30/04/2027 | publication attendue | ECOC | activité du T1 (dernière connue : 30/04/2026, + 1 an(s)) | estimation (historique des notes) |
| 30/04/2027 | publication attendue | SPHC | activité du T1 (dernière connue : 30/04/2026, + 1 an(s)) | estimation (historique des notes) |
| 30/04/2027 | échéance de publication | toutes les lignes | comptes annuels de l'exercice précédent et activité du T1 (échéance R7) ; alerte orange le lendemain, rouge à +61 jours | fait (règle R7) |
| 02/05/2027 | publication attendue | CIEC | activité du T1 (dernière connue : 02/05/2024, + 3 an(s)) | estimation (historique des notes) |
| 03/05/2027 | AGO estimée | ONTBF | date ex − 42 jours (médiane §5.4) | estimation |
| 04/05/2027 | publication attendue | BICC | activité du T1 (dernière connue : 04/05/2026, + 1 an(s)) | estimation (historique des notes) |
| 04/05/2027 | publication attendue | BOABF | activité du T1 (dernière connue : 04/05/2026, + 1 an(s)) | estimation (historique des notes) |
| 04/05/2027 | publication attendue | CBIBF | activité du T1 (dernière connue : 04/05/2026, + 1 an(s)) | estimation (historique des notes) |
| 04/05/2027 | publication attendue | NSBC | activité du T1 (dernière connue : 04/05/2026, + 1 an(s)) | estimation (historique des notes) |
| 04/05/2027 | publication attendue | NTLC | comptes annuels (dernière connue : 04/05/2026, + 1 an(s)) | estimation (historique des notes) |
| 04/05/2027 | publication attendue | NTLC | activité du T1 (dernière connue : 04/05/2026, + 1 an(s)) | estimation (historique des notes) |
| 04/05/2027 | publication attendue | ONTBF | activité du T1 (dernière connue : 04/05/2026, + 1 an(s)) | estimation (historique des notes) |
| 04/05/2027 | publication attendue | ORAC | activité du T1 (dernière connue : 04/05/2026, + 1 an(s)) | estimation (historique des notes) |
| 04/05/2027 | publication attendue | SGBC | activité du T1 (dernière connue : 04/05/2026, + 1 an(s)) | estimation (historique des notes) |
| 04/05/2027 | publication attendue | SLBC | activité du T1 (dernière connue : 04/05/2026, + 1 an(s)) | estimation (historique des notes) |
| 04/05/2027 | publication attendue | STBC | activité du T1 (dernière connue : 04/05/2026, + 1 an(s)) | estimation (historique des notes) |
| 05/05/2027 | publication attendue | BOAB | activité du T1 (dernière connue : 05/05/2026, + 1 an(s)) | estimation (historique des notes) |
| 07/05/2027 | publication attendue | SIBC | activité du T1 (dernière connue : 07/05/2026, + 1 an(s)) | estimation (historique des notes) |
| 10/05/2027 | détachement prévu | BOAC | 594,53 FCFA net/titre, soit 14 863 FCFA payés vers le 12/05/2027 ; une vente programmée est reportée au jour ex si le rendement net ≥ 4 % (§5.2.6) | estimation (mois habituel) |
| 15/05/2027 | publication attendue | NSBC | comptes annuels (dernière connue : 15/05/2026, + 1 an(s)) | estimation (historique des notes) |
| 17/05/2027 | détachement prévu | SNTS | 174,00 FCFA net/titre, soit 109 446 FCFA payés vers le 19/05/2027 ; une vente programmée est reportée au jour ex si le rendement net ≥ 4 % (§5.2.6) | estimation (mois habituel) |
| 20/05/2027 | publication attendue | SLBC | comptes annuels (dernière connue : 20/05/2026, + 1 an(s)) | estimation (historique des notes) |
| 21/05/2027 | publication attendue | CIEC | comptes annuels (dernière connue : 21/05/2026, + 1 an(s)) | estimation (historique des notes) |
| 24/05/2027 | AGO estimée | CBIBF | date ex − 42 jours (médiane §5.4) | estimation |
| 24/05/2027 | AGO estimée | NSBC | date ex − 42 jours (médiane §5.4) | estimation |
| 24/05/2027 | détachement prévu | BOAB | 585,00 FCFA net/titre, soit 14 625 FCFA payés vers le 26/05/2027 ; une vente programmée est reportée au jour ex si le rendement net ≥ 4 % (§5.2.6) | estimation (mois habituel) |
| 24/05/2027 | détachement prévu | ECOC | 781,44 FCFA net/titre, soit 26 569 FCFA payés vers le 26/05/2027 ; une vente programmée est reportée au jour ex si le rendement net ≥ 4 % (§5.2.6) | estimation (mois habituel) |
| 31/05/2027 | détachement prévu | BOAS | 450,00 FCFA net/titre, soit 9 900 FCFA payés vers le 02/06/2027 ; une vente programmée est reportée au jour ex si le rendement net ≥ 4 % (§5.2.6) | estimation (mois habituel) |
| 02/06/2027 | AGO estimée | BICC | date ex − 42 jours (médiane §5.4) | estimation |
| 02/06/2027 | publication attendue | BOAC | activité du T1 (dernière connue : 02/06/2026, + 1 an(s)) | estimation (historique des notes) |
| 02/06/2027 | publication attendue | TTLC | comptes annuels (dernière connue : 02/06/2026, + 1 an(s)) | estimation (historique des notes) |
| 07/06/2027 | détachement prévu | ORAC | 704,00 FCFA net/titre, soit 66 176 FCFA payés vers le 09/06/2027 ; une vente programmée est reportée au jour ex si le rendement net ≥ 4 % (§5.2.6) | estimation (mois habituel) |
| 08/06/2027 | AGO estimée | SGBC | date ex − 42 jours (médiane §5.4) | estimation |
| 09/06/2027 | publication attendue | ORAC | comptes annuels (dernière connue : 09/06/2026, + 1 an(s)) | estimation (historique des notes) |
| 10/06/2027 | AGO estimée | STBC | date ex − 42 jours (médiane §5.4) | estimation |
| 11/06/2027 | AGO estimée | CIEC | date ex − 42 jours (médiane §5.4) | estimation |
| 12/06/2027 | publication attendue | ONTBF | comptes annuels (dernière connue : 12/06/2026, + 1 an(s)) | estimation (historique des notes) |
| 14/06/2027 | détachement prévu | ONTBF | 145,32 FCFA net/titre, soit 6 103 FCFA payés vers le 16/06/2027 ; une vente programmée est reportée au jour ex si le rendement net ≥ 4 % (§5.2.6) | estimation (mois habituel) |
| 15/06/2027 | publication attendue | BOAC | comptes annuels (dernière connue : 15/06/2026, + 1 an(s)) | estimation (historique des notes) |
| 17/06/2027 | AGO estimée | SIBC | date ex − 42 jours (médiane §5.4) | estimation |
| 17/06/2027 | AGO estimée | SLBC | date ex − 42 jours (médiane §5.4) | estimation |
| 18/06/2027 | AGO estimée | BICB | date ex − 42 jours (médiane §5.4) | estimation |
| 22/06/2027 | publication attendue | BICB | comptes annuels (dernière connue : 22/06/2026, + 1 an(s)) | estimation (historique des notes) |
| 26/06/2027 | publication attendue | STBC | convocation d'AG (dernière connue : 26/06/2026, + 1 an(s)) | estimation (historique des notes) |
| 28/06/2027 | AGO estimée | SPHC | date ex − 42 jours (médiane §5.4) | estimation |
| 01/07/2027 | révision du BRVM 30 | IDX:BRVM-30 | révision trimestrielle de la composition (information seulement, §5.5) | fait (calendrier ; date de séance estimée) |
| 02/07/2027 | AGO estimée | NTLC | date ex − 42 jours (médiane §5.4) | estimation |
| 05/07/2027 | détachement prévu | CBIBF | 900,00 FCFA net/titre, soit 18 000 FCFA payés vers le 07/07/2027 ; une vente programmée est reportée au jour ex si le rendement net ≥ 4 % (§5.2.6) | estimation (mois habituel) |
| 05/07/2027 | détachement prévu | NSBC | 675,98 FCFA net/titre, soit 10 140 FCFA payés vers le 07/07/2027 ; une vente programmée est reportée au jour ex si le rendement net ≥ 4 % (§5.2.6) | estimation (mois habituel) |
| 08/07/2027 | publication attendue | CBIBF | comptes annuels (dernière connue : 08/07/2026, + 1 an(s)) | estimation (historique des notes) |
| 14/07/2027 | détachement prévu | BICC | 1 157,20 FCFA net/titre, soit 11 572 FCFA payés vers le 16/07/2027 ; une vente programmée est reportée au jour ex si le rendement net ≥ 4 % (§5.2.6) | estimation (mois habituel) |
| 16/07/2027 | publication attendue | STBC | comptes annuels (dernière connue : 16/07/2026, + 1 an(s)) | estimation (historique des notes) |
| 20/07/2027 | détachement prévu | SGBC | 2 298,75 FCFA net/titre, soit 43 676 FCFA payés vers le 22/07/2027 ; une vente programmée est reportée au jour ex si le rendement net ≥ 4 % (§5.2.6) | estimation (mois habituel) |
| 22/07/2027 | détachement prévu | STBC | 1 707,20 FCFA net/titre, soit 18 779 FCFA payés vers le 26/07/2027 ; une vente programmée est reportée au jour ex si le rendement net ≥ 4 % (§5.2.6) | estimation (mois habituel) |
| 23/07/2027 | détachement prévu | CIEC | 205,92 FCFA net/titre, soit 7 207 FCFA payés vers le 27/07/2027 ; une vente programmée est reportée au jour ex si le rendement net ≥ 4 % (§5.2.6) | estimation (mois habituel) |
| 23/07/2027 | publication attendue | BICB | activité du T1 (dernière connue : 23/07/2026, + 1 an(s)) | estimation (historique des notes) |
| 24/07/2027 | publication attendue | BOAB | comptes semestriels (dernière connue : 24/07/2026, + 1 an(s)) | estimation (historique des notes) |
| 27/07/2027 | publication attendue | SNTS | comptes semestriels (dernière connue : 27/07/2026, + 1 an(s)) | estimation (historique des notes) |
| 29/07/2027 | détachement prévu | SIBC | 374,00 FCFA net/titre, soit 23 188 FCFA payés vers le 02/08/2027 ; une vente programmée est reportée au jour ex si le rendement net ≥ 4 % (§5.2.6) | estimation (mois habituel) |
| 29/07/2027 | détachement prévu | SLBC | 1 871,76 FCFA net/titre, soit 18 718 FCFA payés vers le 02/08/2027 ; une vente programmée est reportée au jour ex si le rendement net ≥ 4 % (§5.2.6) | estimation (mois habituel) |
| 30/07/2027 | détachement prévu | BICB | 254,60 FCFA net/titre, soit 9 166 FCFA payés vers le 02/08/2027 ; une vente programmée est reportée au jour ex si le rendement net ≥ 4 % (§5.2.6) | estimation (mois habituel) |
| 06/08/2027 | publication attendue | BOABF | comptes semestriels (dernière connue : 06/08/2026, + 1 an(s)) | estimation (historique des notes) |
| 09/08/2027 | détachement prévu | SPHC | 430,32 FCFA net/titre, soit 6 885 FCFA payés vers le 11/08/2027 ; une vente programmée est reportée au jour ex si le rendement net ≥ 4 % (§5.2.6) | estimation (mois habituel) |
| 10/08/2027 | AGO estimée | TTLC | date ex − 42 jours (médiane §5.4) | estimation |
| 13/08/2027 | détachement prévu | NTLC | 369,60 FCFA net/titre, soit 4 805 FCFA payés vers le 17/08/2027 ; une vente programmée est reportée au jour ex si le rendement net ≥ 4 % (§5.2.6) | estimation (mois habituel) |
| 01/09/2027 | publication attendue | CBIBF | comptes semestriels (dernière connue : 01/09/2026, + 1 an(s)) | estimation (historique des notes) |
| 01/09/2027 | publication attendue | SGBC | comptes semestriels (dernière connue : 01/09/2026, + 1 an(s)) | estimation (historique des notes) |
| 10/09/2027 | publication attendue | ECOC | comptes semestriels (dernière connue : 10/09/2026, + 1 an(s)) | estimation (historique des notes) |
| 18/09/2027 | publication attendue | SNTS | convocation d'AG (dernière connue : 18/09/2026, + 1 an(s)) | estimation (historique des notes) |
| 21/09/2027 | détachement prévu | TTLC | 139,77 FCFA net/titre, soit 5 451 FCFA payés vers le 23/09/2027 ; une vente programmée est reportée au jour ex si le rendement net ≥ 4 % (§5.2.6) | estimation (mois habituel) |
| 22/09/2027 | publication attendue | BICB | comptes semestriels (dernière connue : 22/09/2026, + 1 an(s)) | estimation (historique des notes) |
| 22/09/2027 | publication attendue | BOAS | comptes semestriels (dernière connue : 22/09/2026, + 1 an(s)) | estimation (historique des notes) |
| 29/09/2027 | publication attendue | SIBC | comptes semestriels (dernière connue : 29/09/2026, + 1 an(s)) | estimation (historique des notes) |
| 01/10/2027 | révision du BRVM 30 | IDX:BRVM-30 | révision trimestrielle de la composition (information seulement, §5.5) | fait (calendrier ; date de séance estimée) |
| 02/10/2027 | publication attendue | BOAC | comptes semestriels (dernière connue : 02/10/2026, + 1 an(s)) | estimation (historique des notes) |
| 02/10/2027 | publication attendue | ONTBF | comptes semestriels (dernière connue : 02/10/2026, + 1 an(s)) | estimation (historique des notes) |
| 06/10/2027 | publication attendue | SPHC | comptes semestriels (dernière connue : 06/10/2025, + 2 an(s)) | estimation (historique des notes) |
| 09/10/2027 | publication attendue | ORAC | comptes semestriels (dernière connue : 09/10/2026, + 1 an(s)) | estimation (historique des notes) |
| 14/10/2027 | publication attendue | BICC | comptes semestriels (dernière connue : 14/10/2026, + 1 an(s)) | estimation (historique des notes) |
| 14/10/2027 | publication attendue | SPHC | activité du T3 (dernière connue : 14/10/2026, + 1 an(s)) | estimation (historique des notes) |
| 22/10/2027 | publication attendue | BOAS | activité du T3 (dernière connue : 22/10/2026, + 1 an(s)) | estimation (historique des notes) |
| 23/10/2027 | publication attendue | NTLC | comptes semestriels (dernière connue : 23/10/2026, + 1 an(s)) | estimation (historique des notes) |
| 23/10/2027 | publication attendue | NTLC | activité du T3 (dernière connue : 23/10/2026, + 1 an(s)) | estimation (historique des notes) |
| 26/10/2027 | publication attendue | NSBC | comptes semestriels (dernière connue : 26/10/2026, + 1 an(s)) | estimation (historique des notes) |
| 26/10/2027 | publication attendue | ONTBF | activité du T3 (dernière connue : 26/10/2026, + 1 an(s)) | estimation (historique des notes) |
| 27/10/2027 | publication attendue | BOABF | activité du T3 (dernière connue : 27/10/2026, + 1 an(s)) | estimation (historique des notes) |
| 28/10/2027 | publication attendue | ECOC | activité du T3 (dernière connue : 28/10/2026, + 1 an(s)) | estimation (historique des notes) |
| 28/10/2027 | publication attendue | TTLC | comptes semestriels (dernière connue : 28/10/2026, + 1 an(s)) | estimation (historique des notes) |
| 28/10/2027 | publication attendue | TTLC | activité du T3 (dernière connue : 28/10/2026, + 1 an(s)) | estimation (historique des notes) |
| 29/10/2027 | publication attendue | ORAC | activité du T3 (dernière connue : 29/10/2026, + 1 an(s)) | estimation (historique des notes) |
| 30/10/2027 | publication attendue | CBIBF | activité du T3 (dernière connue : 30/10/2026, + 1 an(s)) | estimation (historique des notes) |
| 30/10/2027 | publication attendue | CIEC | comptes semestriels (dernière connue : 30/10/2026, + 1 an(s)) | estimation (historique des notes) |
| 30/10/2027 | publication attendue | SNTS | activité du T3 (dernière connue : 30/10/2026, + 1 an(s)) | estimation (historique des notes) |
| 31/10/2027 | échéance de publication | toutes les lignes | comptes semestriels et activité du T3 (échéance R7) ; alerte orange le lendemain, rouge à +61 jours | fait (règle R7) |
| 02/11/2027 | publication attendue | BICC | activité du T3 (dernière connue : 02/11/2026, + 1 an(s)) | estimation (historique des notes) |
| 02/11/2027 | publication attendue | NSBC | activité du T3 (dernière connue : 02/11/2026, + 1 an(s)) | estimation (historique des notes) |
| 02/11/2027 | publication attendue | SGBC | activité du T3 (dernière connue : 02/11/2026, + 1 an(s)) | estimation (historique des notes) |
| 02/11/2027 | publication attendue | SLBC | comptes semestriels (dernière connue : 02/11/2026, + 1 an(s)) | estimation (historique des notes) |
| 02/11/2027 | publication attendue | STBC | comptes semestriels (dernière connue : 02/11/2026, + 1 an(s)) | estimation (historique des notes) |
| 02/11/2027 | publication attendue | STBC | activité du T3 (dernière connue : 02/11/2026, + 1 an(s)) | estimation (historique des notes) |
| 03/11/2027 | publication attendue | BOAB | activité du T3 (dernière connue : 03/11/2026, + 1 an(s)) | estimation (historique des notes) |
| 03/11/2027 | publication attendue | BOAC | activité du T3 (dernière connue : 03/11/2026, + 1 an(s)) | estimation (historique des notes) |
| 03/11/2027 | publication attendue | SIBC | activité du T3 (dernière connue : 03/11/2026, + 1 an(s)) | estimation (historique des notes) |
| 10/11/2027 | publication attendue | BICB | activité du T3 (dernière connue : 10/11/2026, + 1 an(s)) | estimation (historique des notes) |

### Évaluation des indices (notes.index_eval, information)

| Indice | Position | Confiance | Score | Lecture |
|---|---|---|---|---|
| BRVM Composite | SOUS-PONDÉRER | 0,63 | −0,52 | Score composite −0,52 (tendance −0,42 × 0,35 ; valorisation −0,97 × 0,29 ; largeur −1,56 × 0,18 ; régime +1,00 × 0,18 ; plus notes +0,05 × 0,15) → SOUS-PONDÉRER (seuils ±0,5) ; confiance 0,63 (accord des composantes avec la position 0,79, marge au seuil 0,02, couverture 1,00, qualité des données 1,00). |
| BRVM Composite Total Return | SOUS-PONDÉRER | 0,57 | −0,53 | Score composite −0,53 (tendance −0,43 × 0,35 ; valorisation −0,97 × 0,29 ; largeur −1,56 × 0,18 ; régime +1,00 × 0,18 ; plus notes +0,05 × 0,15) → SOUS-PONDÉRER (seuils ±0,5) ; confiance 0,57 (accord des composantes avec la position 0,79, marge au seuil 0,03, couverture 1,00, qualité des données 0,90). |
| BRVM 30 | SOUS-PONDÉRER | 0,84 | −0,84 | Score composite −0,84 (tendance −0,20 × 0,35 ; valorisation −2,42 × 0,29 ; largeur −1,37 × 0,18 ; régime +1,00 × 0,18 ; plus notes +0,05 × 0,15) → SOUS-PONDÉRER (seuils ±0,5) ; confiance 0,84 (accord des composantes avec la position 0,85, marge au seuil 0,34, couverture 1,00, qualité des données 1,00). |
| BRVM Prestige | SOUS-PONDÉRER | 0,75 | −0,71 | Score composite −0,71 (tendance −0,37 × 0,35 ; valorisation −1,88 × 0,29 ; largeur −1,22 × 0,18 ; régime +1,00 × 0,18 ; plus notes +0,09 × 0,15) → SOUS-PONDÉRER (seuils ±0,5) ; confiance 0,75 (accord des composantes avec la position 0,82, marge au seuil 0,21, couverture 1,00, qualité des données 1,00). |
| BRVM Principal | SOUS-PONDÉRER | 0,95 | −1,21 | Score composite −1,21 (tendance −1,37 × 0,35 ; valorisation −2,07 × 0,29 ; largeur −1,67 × 0,18 ; régime +1,00 × 0,18 ; plus notes +0,01 × 0,15) → SOUS-PONDÉRER (seuils ±0,5) ; confiance 0,95 (accord des composantes avec la position 0,89, marge au seuil 0,71, couverture 1,00, qualité des données 1,00). |
| sectoriel Services financiers | SOUS-PONDÉRER | 0,80 | −0,92 | Score composite −0,92 (tendance −0,36 × 0,35 ; valorisation −2,28 × 0,29 ; largeur −1,66 × 0,18 ; régime +1,00 × 0,18 ; plus notes +0,00 × 0,15) → SOUS-PONDÉRER (seuils ±0,5) ; confiance 0,80 (accord des composantes avec la position 0,86, marge au seuil 0,42, couverture 1,00, qualité des données 0,90). |
| sectoriel Télécommunications | NEUTRE | 0,77 | −0,24 | Score composite −0,24 (tendance +1,07 × 0,35 ; valorisation −2,39 × 0,29 ; largeur −0,63 × 0,18 ; régime +1,00 × 0,18 ; plus notes +0,15 × 0,15) → NEUTRE (seuils ±0,5) ; confiance 0,77 (accord des composantes avec la position 0,83, marge au seuil 0,26, couverture 1,00, qualité des données 0,97). |
| sectoriel Consommation de base | SOUS-PONDÉRER | 0,84 | −0,78 | Score composite −0,78 (tendance −1,62 × 0,35 ; valorisation −0,24 × 0,29 ; largeur −0,72 × 0,18 ; régime +0,00 × 0,18 ; plus notes −0,06 × 0,15) → SOUS-PONDÉRER (seuils ±0,5) ; confiance 0,84 (accord des composantes avec la position 1,00, marge au seuil 0,28, couverture 1,00, qualité des données 0,97). |
| sectoriel Consommation discrétionnaire | SOUS-PONDÉRER | 0,95 | −1,53 | Score composite −1,53 (tendance −2,31 × 0,35 ; valorisation −0,50 × 0,29 ; largeur −1,30 × 0,18 ; régime −2,00 × 0,18 ; plus notes +0,13 × 0,15) → SOUS-PONDÉRER (seuils ±0,5) ; confiance 0,95 (accord des composantes avec la position 0,99, marge au seuil 1,03, couverture 1,00, qualité des données 0,97). |
| sectoriel Énergie | SOUS-PONDÉRER | 0,75 | −0,74 | Score composite −0,74 (tendance −0,69 × 0,35 ; valorisation −2,25 × 0,29 ; largeur −0,13 × 0,18 ; régime +1,00 × 0,18 ; plus notes +0,10 × 0,15) → SOUS-PONDÉRER (seuils ±0,5) ; confiance 0,75 (accord des composantes avec la position 0,83, marge au seuil 0,24, couverture 1,00, qualité des données 0,97). |
| sectoriel Industriels | SOUS-PONDÉRER | 0,90 | −1,50 | Score composite −1,50 (tendance −0,31 × 0,35 ; valorisation −2,91 × 0,29 ; largeur −0,93 × 0,18 ; régime −2,00 × 0,18 ; plus notes −0,11 × 0,15) → SOUS-PONDÉRER (seuils ±0,5) ; confiance 0,90 (accord des composantes avec la position 1,00, marge au seuil 1,00, couverture 1,00, qualité des données 0,90). |
| sectoriel Services publics | SOUS-PONDÉRER | 0,71 | −1,41 | Score composite −1,41 (tendance −0,30 × 0,35 ; valorisation −2,82 × 0,29 ; largeur −0,85 × 0,18 ; régime −2,00 × 0,18 ; plus notes +0,17 × 0,15) → SOUS-PONDÉRER (seuils ±0,5) ; confiance 0,71 (accord des composantes avec la position 0,98, marge au seuil 0,91, couverture 1,00, qualité des données 0,72). |

## 9. Explications (titres retenus et 5 premiers écartés)

| Titre | Statut | Rang | Poids | Explication |
|---|---|---|---|---|
| SNTS | retenu | 1 | 25,44 % | plafond de ligne max(10 % × 0,85 ; min(30 % ; 1,25 × b_i = 26,12 %)) = 26,12 % ; indice discipliné : capitalisation n° 1 parmi les éligibles |
| ORAC | retenu | 2 | 18,27 % | plafond de ligne max(10 % × 1 ; min(30 % ; 1,25 × b_i = 18,75 %)) = 18,75 % ; indice discipliné : capitalisation n° 2 parmi les éligibles |
| SGBC | retenu | 3 | 7,60 % | plafond de ligne max(10 % × 1 ; min(30 % ; 1,25 × b_i = 7,80 %)) = 10,00 % ; indice discipliné : capitalisation n° 3 parmi les éligibles |
| CBIBF | retenu | 5 | 5,54 % | plafond de ligne max(10 % × 0,75 ; min(30 % ; 1,25 × b_i = 5,69 %)) = 7,50 % ; indice discipliné : capitalisation n° 4 parmi les éligibles |
| SIBC | retenu | 6 | 5,16 % | plafond de ligne max(10 % × 1 ; min(30 % ; 1,25 × b_i = 5,30 %)) = 10,00 % ; indice discipliné : capitalisation n° 5 parmi les éligibles |
| ECOC | retenu | 7 | 5,13 % | plafond de ligne max(10 % × 1 ; min(30 % ; 1,25 × b_i = 5,27 %)) = 10,00 % ; indice discipliné : capitalisation n° 6 parmi les éligibles |
| SLBC | retenu | 8 | 4,20 % | plafond de ligne max(10 % × 1 ; min(30 % ; 1,25 × b_i = 4,31 %)) = 10,00 % ; indice discipliné : capitalisation n° 7 parmi les éligibles |
| BICC | retenu | 9 | 3,25 % | plafond de ligne max(10 % × 1 ; min(30 % ; 1,25 × b_i = 3,34 %)) = 10,00 % ; indice discipliné : capitalisation n° 8 parmi les éligibles |
| BOAC | retenu | 10 | 2,77 % | plafond de ligne max(10 % × 1 ; min(30 % ; 1,25 × b_i = 2,84 %)) = 10,00 % ; indice discipliné : capitalisation n° 9 parmi les éligibles |
| BICB | retenu | 11 | 2,73 % | plafond de ligne max(10 % × 1 ; min(30 % ; 1,25 × b_i = 2,80 %)) = 10,00 % ; indice discipliné : capitalisation n° 10 parmi les éligibles |
| STBC | retenu | 12 | 2,41 % | plafond de ligne max(10 % × 1 ; min(30 % ; 1,25 × b_i = 2,48 %)) = 10,00 % ; indice discipliné : capitalisation n° 11 parmi les éligibles |
| NSBC | retenu | 13 | 2,34 % | plafond de ligne max(10 % × 1 ; min(30 % ; 1,25 × b_i = 2,40 %)) = 10,00 % ; indice discipliné : capitalisation n° 12 parmi les éligibles ; filtres : R10 |
| BOAB | retenu | 14 | 2,32 % | plafond de ligne max(10 % × 1 ; min(30 % ; 1,25 × b_i = 2,39 %)) = 10,00 % × 0,5 (R11×1) = 5,00 % ; indice discipliné : capitalisation n° 13 parmi les éligibles ; filtres : R11×1 |
| BOABF | retenu | 15 | 2,13 % | plafond de ligne max(10 % × 0,75 ; min(30 % ; 1,25 × b_i = 2,19 %)) = 7,50 % × 0,5 (R11×1) = 3,75 % ; indice discipliné : capitalisation n° 14 parmi les éligibles ; filtres : R11×1 |
| NTLC | retenu | 16 | 1,78 % | plafond de ligne max(10 % × 1 ; min(30 % ; 1,25 × b_i = 1,83 %)) = 10,00 % ; indice discipliné : capitalisation n° 15 parmi les éligibles |
| BOAS | retenu | 17 | 1,75 % | plafond de ligne max(10 % × 0,85 ; min(30 % ; 1,25 × b_i = 1,79 %)) = 8,50 % ; indice discipliné : capitalisation n° 16 parmi les éligibles |
| CIEC | retenu | 18 | 1,55 % | plafond de ligne max(10 % × 1 ; min(30 % ; 1,25 × b_i = 1,59 %)) = 10,00 % ; indice discipliné : capitalisation n° 17 parmi les éligibles |
| SPHC | retenu | 19 | 1,23 % | plafond de ligne max(10 % × 1 ; min(30 % ; 1,25 × b_i = 1,26 %)) = 10,00 % ; indice discipliné : capitalisation n° 18 parmi les éligibles |
| ONTBF | retenu | 20 | 1,20 % | plafond de ligne max(10 % × 0,75 ; min(30 % ; 1,25 × b_i = 1,23 %)) = 7,50 % ; indice discipliné : capitalisation n° 19 parmi les éligibles |
| TTLC | retenu | 21 | 1,19 % | plafond de ligne max(10 % × 1 ; min(30 % ; 1,25 × b_i = 1,22 %)) = 10,00 % × 0,5 (R12) = 5,00 % ; indice discipliné : capitalisation n° 20 parmi les éligibles ; filtres : R12 |
| ETIT | écarté | 4 | 0,00 % | capitalisation n° 4 parmi les éligibles : achat bloqué par un filtre de risque, titre non détenu écarté de la sélection (D8) ; filtres : R2 |
| ORGT | écarté | 22 | 0,00 % | capitalisation n° 22 parmi les éligibles : hors des 20 plus grosses (D8) ; filtres : R11×1 |
| SOGC | écarté | 23 | 0,00 % | capitalisation n° 23 parmi les éligibles : hors des 20 plus grosses (D8) ; filtres : R10 |
| SDSC | écarté | 24 | 0,00 % | capitalisation n° 24 parmi les éligibles : hors des 20 plus grosses (D8) |
| SMBC | écarté | 25 | 0,00 % | capitalisation n° 25 parmi les éligibles : hors des 20 plus grosses (D8) |

## 10. Faits, estimations, hypothèses

### Faits (publiés ou réglementaires)

- Cours de clôture et cours de référence du BOC du 20/11/2026 (source : BOC, data/panel).
- Bornes de ±7,5 % autour de la référence ajustée ; pas de cotation 1 FCFA sous 100 FCFA, 5 FCFA au-delà ; quotité 1 titre (instruction I-A, §7.1, §11).
- Règlement-livraison J+2 depuis le 04/12/2025 (instruction 03-2025) ; la BRVM annule les ordres en attente le jour ex.
- Dividendes : derniers montants nets publiés au BOC (ligne (d) ou correction publiée) ; IRVM CI 12 %, SN 10 % (2026), NE 7 %, ML 7 % (§7.3).
- Commissions BRVM 0,20 % et DC/BR 0,10 % par côté (barèmes primaires).
- Statut du test S1 : REJETÉ (registre : 20 essai(s) S1 au statut « exécuté »).
- Variante appliquée : REF (A est REJETÉ sur S1 : mode « indice discipliné » (§8.3, D8), aucune promesse d'alpha).
- Prime de risque du BOC 0,58 : marché « cher » (information, jamais un signal, §4.5).

### Estimations (calculées, incertaines)

- Demi-spread par titre : ½ × spread médian de clôture sur 120 séances (carnet du BOC), plancher d'un demi-pas ; défaut 0,35 % si non mesuré.
- Impact de marché κ·√π par tranche, π = montant de la tranche / MDV63 (valeur médiane échangée sur 63 séances, séances sans échange comptées à 0).
- Montants bruts et nets au cours de référence (le prix d'exécution réel peut différer jusqu'au prix limite) ; provision « pire cas » au prix limite.
- Dates de détachement et de paiement projetées sur le mois habituel ; AGO = date ex − 42 jours (médiane).
- Distribution à 12 mois par bootstrap stationnaire (toute l'histoire 2017-2026 (le registre indique que le test unique S1 a été exécuté)) : distribution historique, pas une prévision.
- Stress du §9.3 : pertes calculées sous hypothèse de linéarité (β) ou de choc direct par pays.

### Hypothèses (supposées, non vérifiées)

- Scénario de coûts « central » : courtage 0,80 % × (1 + taxe 18 %) — taxe [NON VÉRIFIÉ] (TVA ou TAF) ; redevance AMF-UMOA nulle (introuvable).
- Impact κ = 0,016 (« 50 pb à 10 % de participation », aucune étude d'impact BRVM).
- Droits de garde 0,25 % par an et tenue de compte 5 000 FCFA par ligne et par an (SGI de type BICI ; 0 chez FGI).
- Dernier dividende reconduit à l'identique (aucune prévision de résultat) ; IRVM BF 12,5 %, BJ par émetteur, TG inconnu : [NON VÉRIFIÉ] ; aucun impôt sur les plus-values (personne physique résidente, NV).
- Calendrier futur des séances : jours ouvrés hors fériés à date fixe (fêtes mobiles inconnues).
- Personne physique résidente ; aucun ordre au-delà de la cible ; la décision du jour est reconduite jusqu'à la revue mensuelle.

> **Performance passée ≠ garantie. Aucun gain n'est garanti.**
