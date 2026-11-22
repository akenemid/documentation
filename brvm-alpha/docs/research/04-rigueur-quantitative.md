# 04 — Rigueur quantitative et statistique : ne pas se tromper

> **Projet** : BRVM Alpha · **Module** : recherche / validation, inférence, risque, construction
> **Rédigé le** : 2026-11-22 · **Statut** : v1.1 (passé au vérificateur sceptique le 2026-11-22 ; voir la dernière section)
> **Portée** : surapprentissage des backtests (PBO par CSCV), Sharpe probabiliste et dégonflé, tests multiples, validation walk-forward et purgée, bootstrap stationnaire, covariance rétrécie, HRP, Black-Litterman, Kelly fractionnel, CVaR, corrections du trading peu fréquent (Dimson, Scholes-Williams, Getmansky-Lo-Makarov, Lo 2002), régimes, combinaison bayésienne et James-Stein, coefficient d'information et loi fondamentale. Pour chaque méthode : formule exacte, référence, et **paramètres chiffrés pour un marché d'environ 48 actions peu liquides comme la BRVM**.
> **Documents liés** : `01-structure-marche.md` (règles, ±7,5 %), `02-litterature-brvm.md` (efficience), `03-facteurs-marches-frontieres.md` (facteurs, DSR interne = 0,65), `../ARCHITECTURE.md` (contrats `quant/stats.py`, `portfolio/risk.py`, `portfolio/construct.py`, `backtest/walkforward.py`).

---

## 0. Avertissement et méthode

1. **Aucune méthode de ce document ne garantit un gain.** Elles font l'inverse : elles mesurent **à quel point on peut se tromper**. Même une stratégie dont le vrai Sharpe annuel vaut 1,0 (ce qui est exceptionnel) perd de l'argent une année sur six en moyenne : P(année négative) = Φ(−SR) = 15,9 %. Avec un Sharpe de 0,5, c'est 30,9 % (dérivation sous normalité, section 4.6). Promettre « 100 % de gains » serait mathématiquement faux. Notre engagement est la **rigueur** : chaque signal devra franchir les filtres de la section 17 avant d'engager un franc.
2. **Limites d'accès pendant cette revue.** La lecture directe des textes intégraux (WebFetch et curl) a échoué pour `escholarship.org`, `www.davidhbailey.com` et `people.duke.edu` : ces hôtes ne sont pas autorisés dans le réseau de la session. Les autres hôtes académiques n'ont pas été réessayés, conformément à la consigne de l'outil. De plus, le **budget de recherche web de la session a été épuisé** après les 20 premières recherches de cette revue. Les thèmes régimes (HMM, filtres de tendance), James-Stein/Jorion, MinBTL et détails de Black-Litterman n'ont donc **pas pu être vérifiés en ligne**. Pour les relancer, il suffit d'envoyer un message de suite (le budget est par tour), ou d'autoriser les hôtes ci-dessus dans les réglages réseau de la session.
3. **Étiquettes de vérification** (colonne « Vérif. » et section Sources) :
   - **[S]** : référence ou fait confirmé **dans cette session** par le moteur de recherche (métadonnées, résumé ou extraits) ;
   - **[B]** : référence bibliographique classique, **non vérifiée dans cette session** (budget épuisé). La formule présentée est standard, mais la page ou le DOI doit être contrôlé avant citation externe ;
   - **[D]** : dérivation mathématique faite ici, vérifiable par le lecteur ;
   - **[C]** : **calcul interne** reproductible sur les BOC parsés (section 2).
4. **Niveaux de confiance** (mêmes conventions que les revues 02 et 03) : **high** = source primaire lue, dérivation ou calcul interne reproductible ; **medium** = résumé d'éditeur ou de RePEc cohérent, ou formule standard très répandue ; **low** = source secondaire unique, extrait fragmentaire, ou paramètre fixé par jugement.
5. **Aucun chiffre n'a été inventé.** Quand un paramètre « recommandé » vient de notre jugement et non d'un article, c'est écrit (« choix interne »).

---

## 1. Résumé exécutif

| # | Conclusion | Confiance |
|---|---|---|
| 1 | **Le danger n° 1 à la BRVM n'est pas l'absence d'alpha mais l'illusion d'alpha.** Sur 5 ans de données, tester 50 variantes sans aucun talent donne en moyenne un **meilleur Sharpe annualisé de 1,02** par le seul hasard (10 variantes : 0,70 ; 1 000 : 1,46). Formule de Bailey & López de Prado (2014), section 4.3. | high [D] |
| 2 | **Démonstration sur nos BOC** : une grille de 36 stratégies momentum (2023-2026, rendements actifs contre le panier équipondéré) donne un meilleur ratio d'information de **0,98**. C'est exactement l'espérance du maximum sous l'hypothèse nulle (**0,98**), d'où un **DSR de 0,50**. La **PBO** (CSCV, S = 16, 12 870 combinaisons) vaut **0,37**, et la pente de dégradation hors échantillon est **−0,81**. Ce « bon » résultat n'est donc **pas** une preuve. | high [C] |
| 3 | **Les prix périmés gonflent le Sharpe et dégonflent le risque.** Le panier équipondéré a une autocorrélation journalière de **ρ₁ = 0,23** (Ljung-Box p < 10⁻⁴). L'annualisation naïve × √252 **surestime le Sharpe de 72 %** (facteur de Lo 2002 : 0,58 × √252). Elle **sous-estime la volatilité de 44 %** : 9,1 % par an d'après les séances, contre 16,3 % d'après les rendements mensuels. Pour le Composite, la surestimation du Sharpe est de 30 %. | high [C] |
| 4 | **Effet Epps** : la corrélation moyenne entre titres passe de **0,046** (journalière) à **0,087** (hebdomadaire) puis à **0,179** (mensuelle). Une matrice de covariance estimée sur données journalières **sous-estime fortement le risque du portefeuille**. Il faut estimer en **hebdomadaire** (ou agréger), puis rétrécir avec Ledoit-Wolf. L'intensité optimale vers la corrélation constante est déjà **δ* = 0,79** en hebdomadaire. | high [C] |
| 5 | **Bêtas** : le bêta MCO journalier médian vaut **0,50**. Le bêta de Dimson (1 avance, 5 retards) vaut **0,88**, celui de Scholes-Williams **0,78** et le bêta MCO hebdomadaire **0,71**. Le MCO journalier est biaisé vers zéro de 35 à 45 %. Le coefficient du marché retardé d'une séance est significatif (t > 2) pour **22 %** des titres. | high [C] |
| 6 | **Lissage de Getmansky-Lo-Makarov (MA(2) normalisé)** : pour le panier journalier, θ = (0,755 ; 0,148 ; 0,097) et l'indice de lissage ξ = Σθ² = **0,60**. Environ 25 % du rendement « vrai » d'une séance n'apparaît qu'aux deux séances suivantes. | high [C] |
| 7 | **Le passé ne dit rien des rendements moyens par titre.** Le facteur de James-Stein calculé sur 43 titres et 59 mois vaut **c = 0** : il faut rétrécir à 100 % vers la moyenne commune. La corrélation de rang des rendements moyens entre la 1ʳᵉ et la 2ᵉ moitié de l'échantillon est de **−0,12**. Les rendements espérés doivent venir de **signaux × IC** (Grinold), jamais des moyennes historiques. | high [C] |
| 8 | **Puissance statistique** : avec environ 45 titres, l'erreur-type d'un IC mensuel vaut environ 1/√45 = **0,15**. Pour établir un IC moyen de 0,05 à t = 2, il faut **36 mois** ; à t = 3 (seuil de Harvey-Liu-Zhu), **80 mois**. Le MinTRL d'un Sharpe annuel de 1,0 (contre 0, à 95 %) est de **2,7 à 3,5 ans**. Contre un Sharpe de référence de 0,5, il passe à **10,9 ans**. | high [D/C] |
| 9 | **Tests multiples** : un nouveau facteur doit franchir **t > 3,0** (Harvey, Liu & Zhu 2016). Avec la correction de Bonferroni, un Sharpe de 1,0 mesuré sur 5 ans perd **49 %** après 10 essais et **100 %** après 50. Un Sharpe de 1,5 perd 39 % après 50 essais (méthode de Harvey & Liu 2015). | high [D] / medium [S] (méthode) |
| 10 | **Validation** : walk-forward expansif avec **purge** (horizon du label) et **embargo** d'au moins **21 séances**. Les autocorrélations du panier restent significatives jusqu'à environ 10 séances en journalier et 3 à 4 semaines en hebdomadaire. CPCV (N = 10 groupes, k = 2) : **45 découpages, 9 chemins**. | high [C] / medium [S] |
| 11 | **Bootstrap stationnaire** : la longueur de bloc optimale de Politis-White (avec la correction de 2009) vaut **8,6 séances** pour le panier journalier et **12,4** pour ses carrés. Recommandation : **b = 20 séances** pour les IC de Sharpe. L'IC à 95 % du Sharpe du panier passe de [2,22 ; 4,10] (i.i.d.) à [1,46 ; 4,97] (b = 20) : il est **presque deux fois plus large**. | high [C] / medium [S] |
| 12 | **Construction** : HRP (pas d'inversion de Σ) et Black-Litterman (précision des vues tirée de l'IC) sont adaptés à N ≈ 45 et T court. Le Kelly doit être **fractionnel (¼, plafond ½)** et appliqué à un alpha **rétréci**. Le ½-Kelly garde 75 % de la croissance pour 25 % de la variance. Il fait passer la probabilité de perdre un jour la moitié du capital de 50 % à **12,5 %**. Surestimer μ d'un facteur 2 ramène la croissance à **zéro**. | high [D] / medium [S] |
| 13 | **CVaR** : les limites de ±7,5 % tronquent les pertes journalières. La CVaR 95 % journalière × √21 donne 5,6 % pour le panier, contre **7,3 %** mesuré en mensuel (−23 %). Il faut optimiser la CVaR sur des **scénarios hebdomadaires ou mensuels rééchantillonnés par blocs**, jamais sur des scénarios journaliers. | high [C] |
| 14 | **Régimes** : un modèle markovien à 2 états sur le Composite hebdomadaire est préféré à 1 état (BIC 894,0 contre 900,1). Les durées moyennes sont d'environ **18 semaines**. Mais l'état « volatil » a eu le rendement moyen le **plus élevé** (marché haussier 2022-2026 : +144 %), et le Composite n'a croisé sa moyenne mobile 200 jours que **3 fois**. Il n'y a **pas assez d'événements** pour valider un filtre de régime comme source d'alpha. Il faut l'utiliser seulement comme **dosage du risque**. **[Vérificateur]** 2017-2020 est désormais disponible : le Composite y perd 49 %, avec un drawdown de −57,9 % et 13 croisements de la moyenne mobile 200 séances. Il faut tout ré-estimer sur 2017-2026 (§14.3). | high [C] / low (portée) |

**Message central** : sur la BRVM, la rigueur consiste à (i) **annualiser et estimer le risque avec les corrections de prix périmés**, (ii) **compter chaque essai** et dégonfler en conséquence, (iii) **rétrécir tout ce qui est estimé** (covariance, IC, alpha, Kelly), et (iv) **refuser de promouvoir** un signal qui ne franchit pas l'ensemble des filtres de la section 17. Le fait que nos premiers résultats échouent à ces filtres (DSR 0,50 ; PBO 0,37) prouve qu'ils sont utiles.

---

## 2. Faits BRVM qui conditionnent toutes les méthodes (calcul interne [C])

**Données** : BOC texte parsés par `brvm_alpha.data.store.build_panel` (1 273 séances, du 25/06/2021 au 20/11/2026, 50 symboles, avertissements de parsing hors informatifs : 0,06 %). **Échantillon d'analyse : du 03/01/2022 au 20/11/2026 (1 202 séances)**. 2021 est exclue parce que le téléchargement a laissé de longs trous (jusqu'à 50 jours entre deux BOC), ce qui produirait de faux rendements « d'une séance ». Rendements = rendement total quotidien (`tr_ret`, dividendes nets réinvestis), séances suspendues exclues. Marché = BRVM Composite (indice de prix). Panier équipondéré (« EW ») = moyenne des rendements des titres disponibles.

Source des faits de marché : BOC du 20/11/2026, https://www.brvm.org/sites/default/files/boc_20261120_2.pdf : **48 sociétés cotées**, 12 au compartiment Prestige et 36 au compartiment Principal ; 46 titres transigés ce jour-là ; Composite à 492,89 (confiance high).

> **[Mise à jour du vérificateur, 2026-11-22]** Le téléchargement a progressé depuis la rédaction. `data/boc_text` contient maintenant **2 334 BOC du 02/01/2017 au 20/11/2026**, et le panel reconstruit compte 50 symboles et 106 892 lignes. **2017-2020 n'a aucun trou de plus de 5 jours** (238 à 250 BOC par an). **2021 reste troué** : 156 BOC seulement et 9 trous de plus de 5 jours, le plus long de 50 jours (du 06/05 au 25/06/2021). La date de début propre du 03/01/2022 reste donc valable pour l'échantillon contigu principal. En revanche, **2017-2020 est désormais disponible comme second échantillon** (voir §14.3 et §17.2).
> **Nombre réel de séances par an** : les numéros des BOC donnent N° 247 au 29/12/2023, N° 249 au 31/12/2024, N° 249 au 31/12/2025 et N° 222 au 20/11/2026. La BRVM a donc environ **248 séances par an**, et non 252. Annualiser avec 252 surestime la volatilité et le Sharpe annualisés d'environ 0,8 % (√(252/248)) : c'est négligeable, mais à documenter. Quelques séances manquent aussi au téléchargement (par exemple 243 fichiers pour 249 séances en 2024) : un rendement « d'une séance » couvre alors parfois deux séances. Sources : BOC locaux `boc_20231229`, `boc_20241231`, `boc_20251231` et `boc_20261120` (confiance high).

### 2.1 Liquidité et univers

| Mesure (par titre, puis distribution entre titres) | 2022-2026 | 2 dernières années |
|---|---|---|
| Part des séances sans échange : médiane / p90 | 0,3 % / 10,0 % | 0,0 % / 1,4 % |
| Part des séances à **variation nulle** : médiane / p90 | **25,0 %** / 39,6 % | **19,0 %** / 24,9 % |
| Valeur médiane échangée par séance : p10 / médiane / p90 | 0,34 / 4,8 / 17,2 M FCFA | 2,0 / 9,6 / 31,2 M FCFA |
| Lignes titre×séance à la limite ±7,5 % (\|var\| ≥ 7,3 %) | 3,1 % | 3,9 % |

**Univers éligible** (filtre actuel de `config.UniverseFilter` : échangé au moins 50 % des 120 dernières séances **et** valeur médiane d'au moins 2 M FCFA) :

| Année | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|
| Titres éligibles (médiane mensuelle) | 17 | 16,5 | 22 | 31 | **45** |

Lecture : depuis la cotation en continu, presque tous les titres s'échangent chaque jour. **L'illiquidité prend surtout la forme de montants minuscules et de cours inchangés** (une séance sur quatre ou cinq), pas de séances sans transaction. La **largeur** (nombre de paris indépendants) a beaucoup augmenté en 2025-2026. Un backtest sur 2022-2024 travaille donc sur seulement 16 à 22 titres.

### 2.2 Autocorrélation, lissage, horizon

| Série | ρ₁ … ρ₅ journaliers | Ljung-Box Q(10), p | ρ₁ hebdo (n = 255) | ρ₁ mensuel (n = 59) | VR(5) | VR(20) | Lo : η(252)/√252 |
|---|---|---|---|---|---|---|---|
| Composite (indice de prix) | −0,004 ; 0,052 ; 0,028 ; 0,044 ; 0,069 | 28,8 ; p = 0,001 | 0,189 | 0,172 | 1,09 | 1,52 | **0,771** |
| Panier EW (rendement total) | **0,231** ; 0,157 ; 0,090 ; 0,057 ; 0,074 | 155,7 ; p < 10⁻⁴ | **0,325** | 0,248 | 1,64 | **2,70** | **0,582** |
| Titres individuels (ρ₁ médian) | **−0,056** (IQR −0,134 à 0,014 ; 72 % négatifs) | — | — | — | — | — | — |

Erreurs-types sous H₀ : 1/√1202 = 0,029 (journalier), 0,063 (hebdomadaire), 0,13 (mensuel). L'autocorrélation journalière du panier dépasse 2 erreurs-types (0,058) aux retards 1-3, 5-7 et 10 (0,116) ; les retards 4 et 8 sont à la limite.

**Lecture** : chaque titre pris seul montre un léger **rebond** (ρ₁ < 0, effet d'aller-retour sur la fourchette). Le **portefeuille**, lui, montre une forte **autocorrélation positive**, issue des **corrélations croisées décalées** : les titres peu actifs « rattrapent » le marché avec retard (Lo & MacKinlay 1990 ; https://dspace.mit.edu/bitstream/1721.1/47826/1/econometricanaly00loan.pdf ; [S], medium). Les deux phénomènes appellent des corrections différentes.

| Volatilité annualisée | quotidien × √252 | hebdo × √52 | mensuel × √12 | Rapport mensuel/quotidien |
|---|---|---|---|---|
| Composite | 9,6 % | 10,0 % | 13,0 % | 1,35 |
| Panier EW | 9,1 % | 11,4 % | **16,3 %** | **1,78** |
| Titre médian (43 titres) | 39,1 % | — | — | **0,93** |

**Conséquence pratique** : la volatilité d'un **titre** est correctement estimée en journalier, à 7 % près. Celle d'un **portefeuille** est sous-estimée de 44 % en journalier. Tout ce qui agrège (risque du portefeuille, Sharpe, tracking error, CVaR) doit être mesuré à l'horizon de détention (hebdomadaire ou mensuel) ou corrigé.

### 2.3 Autres constats utilisés plus bas

| Thème | Résultat | Section |
|---|---|---|
| Moments journaliers | Composite : asymétrie −0,13, kurtosis 5,62 ; panier : asymétrie −0,46, kurtosis 5,78 | 4 |
| Marché sur la période | Composite 202,28 (31/12/2021) → 492,89 (20/11/2026), soit **+144 %** ; drawdown maximal −13,9 % (creux le 02/12/2022) | 14 |
| Volatilité résiduelle mensuelle médiane d'un titre | 9,2 % | 16 |
| Dispersion transversale mensuelle médiane | 10,2 % | 16 |

---

## 3. Surapprentissage des backtests : PBO par CSCV

### 3.1 Référence

Bailey, D. H., Borwein, J. M., López de Prado, M. & Zhu, Q. J. (2017). « The Probability of Backtest Overfitting ». *Journal of Computational Finance* 20(4), 39-69, DOI 10.21314/JCF.2016.322. SSRN : https://papers.ssrn.com/abstract=2326253 ; notice : https://ideas.repec.org/a/rsk/journ0/2471206.html [S]. Cadre **non paramétrique et indépendant du modèle** ; les auteurs jugent la validation par simple échantillon de réserve peu fiable pour les backtests d'investissement (résumé). Confiance : **medium-high**.

### 3.2 Algorithme exact (CSCV)

On part de la matrice **M** (T × N) des rendements par période de N configurations testées (toutes, y compris les mauvaises).

1. Découper M en **S** blocs chronologiques contigus de T/S lignes (S **pair**).
2. Former toutes les combinaisons **J** de S/2 blocs : il y en a C(S, S/2). Pour S = 16, C(16, 8) = **12 870** (la version de travail imprime « 12 780 », une coquille signalée par une source secondaire ; [S]). L'échantillon d'apprentissage est J, l'échantillon de test est son complément J̄.
3. Pour chaque J, calculer la performance R_n (sur J) et R̄_n (sur J̄) de chaque configuration n (le Sharpe par défaut).
4. Retenir n* = argmax_n R_n, c'est-à-dire ce qu'aurait choisi le chercheur.
5. Calculer le rang relatif hors échantillon ω̄ = rang(R̄_{n*}) / (N + 1) ∈ ]0, 1[ et son logit **λ = ln(ω̄ / (1 − ω̄))**.
6. **PBO = P(λ ≤ 0) = ∫_{−∞}^{0} f(λ) dλ** : c'est la fréquence à laquelle le meilleur en échantillon finit **sous la médiane** hors échantillon.
7. Diagnostics : régression **R̄_{n*} = a + b·R_{n*}** (pente b < 0, signe de surapprentissage) et **P(R̄_{n*} < 0)**, la probabilité de perte hors échantillon.

Sources des étapes : métadonnées et résumé de l'article [S] ; logit et définition de PBO confirmés par deux articles qui appliquent la méthode (https://arxiv.org/pdf/2608.27734, https://arxiv.org/pdf/1910.05555) [S] ; implémentation de référence `pbo_cscv` dans `quant/stats.py` (cohérente avec notre réimplémentation indépendante, section 3.4). Confiance : **medium-high**.

**Repères d'interprétation** : PBO ≈ 0 pour une configuration réellement supérieure ; PBO ≈ 0,5 si les configurations sont du bruit i.i.d. ; PBO → 1 quand la sélection exploite un bruit qui se retourne. L'article ne fixe **pas de seuil universel**. Une source secondaire suggère de rejeter au-delà de 5 % (https://www.mql5.com/en/articles/24095 ; low). Notre seuil est un **choix interne** (section 17).

### 3.3 Paramètres pour la BRVM

| Paramètre | Valeur | Justification |
|---|---|---|
| S (blocs) | **16** en journalier si T ≥ 640 séances (≥ 40 séances par bloc) ; **10** en hebdomadaire (C(10,5) = 252) ; **8** si moins de 3 ans | Chaque bloc doit contenir plusieurs fois la durée de mémoire mesurée (≈ 10 séances, section 2.2) |
| Fréquence de M | **journalière** pour le classement, mais le critère doit être le **Sharpe corrigé de Lo**, ou bien M hebdomadaire | Le Sharpe naïf favorise les configurations dont les prix sont les plus périmés |
| N | **toutes** les variantes journalisées (registre d'essais) | Retirer les mauvaises variantes biaise la PBO vers le bas |
| Critère | Sharpe des rendements **actifs nets de coûts** contre l'indice de référence | Cohérent avec l'objectif « battre les indices » |

### 3.4 Démonstration sur nos BOC [C]

Grille de **36 stratégies momentum acheteur seul** : rétrospective L ∈ {21, 63, 126, 252} séances, saut ∈ {0, 5, 21}, top-k ∈ {5, 10, 15}, rééquilibrage toutes les 21 séances, exécution en t+1, rendements **bruts** actifs contre le panier EW. Période : du 17/03/2023 au 20/11/2026 (T = 901 séances).

| Mesure | Valeur |
|---|---|
| Meilleure configuration | L = 63, saut = 21, top-10 |
| Son IR annualisé naïf | **0,98** (médiane de la grille : 0,18 ; 58 % des IR > 0) |
| Son IR corrigé de Lo (q = 5 / q = 10) | 0,75 / 0,87 |
| **PBO** (S = 16, 12 870 combinaisons, blocs de 56 séances) | **0,369** |
| P(perte hors échantillon du meilleur IS) | 0,371 |
| Pente de dégradation b (R²) | **−0,81** (0,17) |
| Implémentation du projet `pbo_cscv` | identique : PBO 0,369, b −0,810, P(perte) 0,371 |

Lecture : il y a un peu de signal (PBO < 0,5, en ligne avec le momentum 3-6 mois de la revue 03), mais **plus la configuration brille en échantillon, moins elle brille hors échantillon** (b ≈ −0,8). Ce n'est **pas** un signal promouvable.

---

## 4. Sharpe probabiliste (PSR), dégonflé (DSR), MinTRL

### 4.1 Références

- Bailey & López de Prado (2012). « The Sharpe Ratio Efficient Frontier ». *Journal of Risk* 15(2), 3-44. SSRN 1821643 (PDF repéré : https://www.davidhbailey.com/dhbpapers/sharpe-frontier.pdf, non lisible depuis la session) [S].
- Bailey & López de Prado (2014). « The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting and Non-Normality ». *Journal of Portfolio Management* 40(5), 94-107, DOI 10.3905/jpm.2014.40.5.094. https://papers.ssrn.com/abstract=2460551 [S].
- Présentation de López de Prado (Nomura, 2015) donnant E[max SR] avec γ ≈ 0,5772 : https://www.nomura.com/events/9th-annual-global-quantitative-investment-strategies-conference/resources/upload/10_00_Marcos_Lopez_de_Prado_20150510.pdf [S].
- Lo (2002), variance i.i.d. du Sharpe (section 13.4) [S].

### 4.2 Formules (Sharpe par période, non annualisé)

Soient SR̂ le Sharpe estimé sur T observations, γ₃ l'asymétrie et γ₄ la kurtosis **non excédentaire**, c'est-à-dire le moment centré réduit d'ordre 4 (= 3 pour une loi normale ; `scipy.stats.kurtosis(fisher=False)`, comme dans `quant/stats.py`). La même forme, avec √(T − 1) et (γ₄ − 1)/4, est implémentée dans `skfolio.measures.probabilistic_sharpe_ratio` (skfolio 1.14.4, qui cite Bailey & López de Prado 2012) ; vérification du 2026-11-22.

```
σ²(SR̂) ≈ (1 − γ₃·SR̂ + ((γ₄ − 1)/4)·SR̂²) / (T − 1)

PSR(SR*) = Φ( (SR̂ − SR*)·√(T − 1) / √(1 − γ₃·SR̂ + ((γ₄ − 1)/4)·SR̂²) )

MinTRL(SR*, α) = 1 + (1 − γ₃·SR̂ + ((γ₄ − 1)/4)·SR̂²) · ( z_{1−α} / (SR̂ − SR*) )²     [en observations]
```

Pour des rendements i.i.d. normaux (γ₃ = 0, γ₄ = 3), on retrouve σ²(SR̂) ≈ (1 + SR̂²/2)/T (Lo 2002). Confiance : **medium-high**. La forme de l'erreur-type est confirmée par des sources secondaires concordantes [S] : https://portfoliooptimizer.io/blog/the-probabilistic-sharpe-ratio-bias-adjustment-confidence-intervals-hypothesis-testing-and-minimum-track-record-length/ ; elle est identique dans `quant/stats.py`.

### 4.3 Espérance du maximum et DSR

Sous H₀ (aucun talent), avec N essais indépendants dont les Sharpe ont une variance V[SR_n] :

```
SR₀ = E[max_n SR̂_n] ≈ √V[SR_n] · ( (1 − γ)·Φ⁻¹(1 − 1/N) + γ·Φ⁻¹(1 − 1/(N·e)) ),   γ = 0,5772156649 (Euler-Mascheroni)

DSR = PSR(SR₀)
```

Le DSR est la probabilité que le vrai Sharpe dépasse celui qu'on obtiendrait par le hasard du meilleur des N essais. Seuil d'usage : **DSR ≥ 0,95**. Confiance : **medium-high** [S].

**Table des multiplicateurs** (E[max] en unités de √V) [D] :

| N essais | 2 | 5 | 10 | 20 | 50 | 100 | 1 000 |
|---|---|---|---|---|---|---|---|
| E[max]/√V | 0,52 | 1,19 | 1,58 | 1,90 | 2,28 | 2,53 | 3,26 |

**En Sharpe annualisé**, sous H₀, l'écart-type du Sharpe estimé sur Y années est d'environ 1/√Y. Le **meilleur Sharpe attendu par pur hasard** vaut alors [D] :

| N \ années | 3 ans | 5 ans | 10 ans |
|---|---|---|---|
| 10 essais | 0,91 | **0,70** | 0,50 |
| 50 essais | 1,31 | **1,02** | 0,72 |
| 100 essais | 1,46 | 1,13 | 0,80 |
| 1 000 essais | 1,88 | 1,46 | 1,03 |

C'est l'idée de la « longueur minimale de backtest » (MinBTL) de Bailey, Borwein, López de Prado & Zhu (2014), « Pseudo-Mathematics and Financial Charlatanism », *Notices of the AMS* 61(5) [B ; forme exacte de leur borne **non vérifiée** dans cette session, la table ci-dessus est notre dérivation directe]. Avec l'autocorrélation de la BRVM, le nombre d'années **effectives** est plus petit, et la table est donc **optimiste**.

### 4.4 Nombre effectif d'essais

Le DSR suppose des essais indépendants. Les variantes d'une même idée sont corrélées, d'où l'idée d'un **N effectif**. Deux approximations, mesurées sur notre grille de 36 configurations (corrélation moyenne des rendements actifs : 0,448) [C] :

| Méthode | N effectif |
|---|---|
| N̂ = ρ̄ + (1 − ρ̄)·M (approximation souvent attribuée à Bailey & López de Prado ; **non vérifiée dans le texte**, low) | 20,3 |
| Ratio de participation des valeurs propres (Σλ)²/Σλ² | 3,9 |
| Regroupement (clustering) des configurations (López de Prado ; recommandé, non testé ici) | à calculer |

**Règle prudente (choix interne)** : utiliser le **N brut du registre** pour la décision, et les N effectifs seulement comme analyse de sensibilité. Un N plus grand donne un DSR plus sévère.

### 4.5 Démonstration [C]

Meilleure configuration de la grille (section 3.4) : SR̂ = 0,0620 par séance, γ₃ = −0,21, γ₄ = 4,68, T = 901, N = 36, V[SR] = 0,00083.

| Mesure | Valeur |
|---|---|
| SR₀ = E[max] | 0,0619 par séance (**0,98** annualisé) |
| PSR(0) | 0,967 (paraît significatif seul…) |
| **DSR** | **0,501** (…mais pas du tout une fois la sélection prise en compte) |
| `quant/stats.py:deflated_sharpe` | 0,5015 (identique) |

### 4.6 MinTRL : combien d'années pour croire un Sharpe ? [D]

À 95 % unilatéral, contre SR* = 0 sauf indication contraire :

| Sharpe annuel observé | i.i.d. normal | γ₃ = −0,5 ; γ₄ = 6 (journalier) | même chose, mesuré en mensuel | contre SR* = 0,5 |
|---|---|---|---|---|
| 0,50 | 10,8 ans | 11,0 ans | 12,0 ans | — |
| 0,75 | 4,8 ans | 4,9 ans | 5,7 ans | 43,3 ans |
| 1,00 | 2,7 ans | 2,8 ans | 3,5 ans | 10,9 ans |
| 1,50 | 1,2 an | 1,3 an | 1,8 an | 2,7 ans |

À appliquer **au Sharpe corrigé de Lo**, sinon le MinTRL est sous-estimé.

> **[Précision du vérificateur]** La colonne « contre SR* = 0,5 » suppose des rendements **i.i.d. normaux** (recalcul : 43,3 / 10,8 / 2,7 ans). Avec γ₃ = −0,5 et γ₄ = 6, il faut **44,4 / 11,2 / 2,9 ans** en journalier et **50,6 / 13,6 / 4,0 ans** en mensuel, pour des Sharpe observés de 0,75 / 1,00 / 1,50. Les autres colonnes sont confirmées par recalcul.

Probabilité de perte sur un horizon, si le vrai Sharpe est SR et les rendements normaux : P(perte sur h années) = Φ(−SR·√h) [D].

| Vrai SR annuel | 0,25 | 0,50 | 0,75 | 1,00 | 1,50 |
|---|---|---|---|---|---|
| P(année négative) | 40,1 % | 30,9 % | 22,7 % | 15,9 % | 6,7 % |
| P(5 ans négatifs en cumul) | 28,8 % | 13,2 % | 4,7 % | 1,3 % | < 0,1 % |

### 4.7 Paramètres BRVM

- Calculer PSR, DSR et MinTRL sur des rendements **actifs nets**, à fréquence **hebdomadaire** (moins de prix périmés), ou bien en journalier avec un Sharpe corrigé de Lo.
- SR* = **0** pour « existe-t-il un alpha ? », et SR* = **0,3** annualisé pour « vaut-il les risques et l'effort ? » (choix interne).
- Seuils : PSR(0) ≥ 0,95 **et** DSR ≥ 0,95 avec le N du registre.

---

## 5. Tests multiples : haircut de Harvey-Liu-Zhu

### 5.1 Références

- Harvey, C. R., Liu, Y. & Zhu, H. (2016). « …and the Cross-Section of Expected Returns ». *Review of Financial Studies* 29(1), 5-68. https://ideas.repec.org/a/oup/rfinst/v29y2016i1p5-68..html ; NBER w20592 : https://www.nber.org/papers/w20592 [S]. Conclusion : un nouveau facteur doit franchir **t > 3,0** ; « la plupart des résultats annoncés en économie financière sont probablement faux ». Confiance : **high** (résumé).
- Harvey, C. R. & Liu, Y. (2015). « Backtesting ». *Journal of Portfolio Management*, automne 2015. Copies : https://people.duke.edu/~charvey/Research/Published_Papers/P120_Backtesting.PDF ; https://www.cmegroup.com/content/dam/cmegroup/education/files/backtesting.pdf [S]. Le Sharpe est traité comme une statistique t, puis ajusté par **Bonferroni**, **Holm** (contrôle du FWER) ou **BHY** (contrôle du FDR, la plus clémente). Le haircut est **non linéaire** : les Sharpe élevés sont moins pénalisés, ce qui invalide la règle empirique du « −50 % ». Au moins 315 facteurs ont été testés dans la littérature. Confiance : **medium** (formules exactes non relues dans le texte).
- Code R de référence de la méthode : https://gist.github.com/jaymon0703/50a170e4e37da951ea1192888418c82a [S, low].

### 5.2 Formules (forme standard)

Sharpe annualisé SR sur T années : t = SR·√T, p = 2·(1 − Φ(t)). Pour M tests triés p₍₁₎ ≤ … ≤ p₍M₎ :

```
Bonferroni : p_adj = min(1, M·p)
Holm       : p_adj(i) = max_{j ≤ i} min(1, (M − j + 1)·p₍j₎)
BHY        : p_adj(i) = min_{j ≥ i} min(1, M·c(M)·p₍j₎ / j),   c(M) = Σ_{k=1..M} 1/k
Haircut    : t_adj = Φ⁻¹(1 − p_adj/2) ;  HSR = t_adj / √T ;  haircut = 1 − HSR/SR
```

Holm et BHY ont besoin de **toutes** les p-valeurs des essais : il faut donc journaliser chaque essai. Confiance : **high** pour les procédures statistiques classiques (Holm 1979 ; Benjamini & Yekutieli 2001, *Annals of Statistics* 29(4) [B]), **medium** pour leur mise en œuvre exacte par Harvey-Liu.

### 5.3 Ordres de grandeur pour la BRVM (Bonferroni, 5 ans de données) [D]

| SR observé | t | p | N = 10 | N = 50 | N = 200 |
|---|---|---|---|---|---|
| 0,75 | 1,68 | 0,094 | HSR 0,04 (−95 %) | 0 (−100 %) | 0 (−100 %) |
| 1,00 | 2,24 | 0,025 | HSR 0,51 (**−49 %**) | 0 (**−100 %**) | 0 |
| 1,50 | 3,35 | 0,0008 | HSR 1,19 (−21 %) | HSR 0,92 (−39 %) | HSR 0,63 (−58 %) |

### 5.4 Alternatives quand on compare N stratégies à un indice

Reality Check de White (2000, *Econometrica* 68(5)), test SPA de Hansen (2005, *JBES* 23(4)) et procédure pas-à-pas de Romano & Wolf (2005, *Econometrica* 73(4)) [B]. Toutes reposent sur un **bootstrap stationnaire** (section 7). Elles sont plus puissantes que Bonferroni quand les essais sont corrélés. À implémenter en v2 (choix interne).

### 5.5 Paramètres BRVM

- **t_NW ≥ 3,0** pour tout **nouveau** facteur ou signal (HLZ). t_NW ≥ 2,0 suffit pour un facteur déjà documenté hors BRVM (revue 03) **et** prédéclaré.
- Haircut **BHY** avec M = nombre d'essais du registre ; on promeut si HSR > 0,3 (choix interne).

---

## 6. Validation : walk-forward, k-fold purgé, embargo, CPCV

### 6.1 Références

López de Prado, M. (2018). *Advances in Financial Machine Learning*. Wiley. Chapitre 7 (purge et embargo), chapitre 12 (validation croisée combinatoire purgée, CPCV). Rattachement des chapitres confirmé par https://pypi.org/project/purgedcv/ ; définition : https://en.wikipedia.org/wiki/Purged_cross-validation [S]. Confiance : **medium**.

### 6.2 Définitions exactes

- **Label** de l'observation i : rendement sur [t_i, t_i + h] (h = horizon de détention, par exemple 21 séances).
- **Purge** : retirer de l'apprentissage toute observation dont l'intervalle de label **chevauche** l'intervalle de test.
- **Embargo** : retirer aussi les observations d'apprentissage qui **suivent** immédiatement le test, pendant e séances (l'embargo ne s'applique qu'après le test). Il neutralise la mémoire sérielle.
- **CPCV** : découper en N groupes ; chaque découpage prend k groupes en test, soit C(N, k) découpages, et on reconstitue **φ[N, k] = (k/N)·C(N, k) = C(N − 1, k − 1)** chemins de backtest complets. Exemples confirmés : N = 6, k = 2 donne 15 découpages et 5 chemins [S] ; 10 groupes et 8 en test donnent 36 chemins sur 45 combinaisons [S, https://arxiv.org/pdf/2407.17645].
- **Walk-forward** : apprentissage sur le passé uniquement, test sur la période suivante, avancement d'un pas. C'est le seul schéma qui reproduit la décision réelle. Il n'évalue qu'**un seul chemin**, d'où l'intérêt de la CPCV pour obtenir une **distribution** de Sharpe hors échantillon.

La règle souvent citée d'un embargo d'environ 1 % de T n'a **pas pu être vérifiée** dans le livre (low). Nous fixons l'embargo à partir des **données BRVM** (ci-dessous).

### 6.3 Paramètres BRVM (choix internes fondés sur la section 2)

| Paramètre | Valeur | Justification |
|---|---|---|
| Schéma principal | **walk-forward expansif** (`walk_forward_windows(..., expanding=True)`) | Peu de données : ne rien jeter du passé |
| Apprentissage minimal | **504 séances (2 ans)** | IC : erreur-type d'environ 0,15/√24 = 0,03 après 24 mois |
| Fenêtre de test et pas | **63 séances (1 trimestre)** | Cohérent avec un rééquilibrage trimestriel (revue 03) |
| Purge | **h** = horizon du label (21 séances pour un signal mensuel, 63 pour un signal trimestriel) | Définition |
| **Embargo** | **21 séances** (minimum 10) | ρ_k du panier significatif jusqu'à environ 10 séances (journalier) et 3 à 4 semaines (hebdomadaire), section 2.2 |
| CPCV | **N = 10 groupes, k = 2** → 45 découpages, **9 chemins** ; environ 120 séances par groupe sur 5 ans | Distribution de Sharpe hors échantillon |
| Hors échantillon final | Réserver les **6 derniers mois** jusqu'à la décision de mise en production ; ne les consulter **qu'une fois** | Évite l'usure de l'échantillon de test |
| Pré-enregistrement | Paramètres figés **avant** la première exécution sur la réserve (voir revue 03, §8) | Les DSR et PBO perdent leur sens sinon |

**Spécificité BRVM** : utiliser 2013-2021 comme **second échantillon de validation** une fois les BOC anciens téléchargés et propres (règle de promotion déjà posée en revue 03). Les données d'avant 2013 (fixing, univers plus petit) ne doivent servir qu'à des **tests de robustesse qualitatifs**. **[Mise à jour du vérificateur]** 2017-2020 est **déjà disponible et sans trou** (§2) ; 2013-2016 n'est pas encore téléchargé, et 2021 reste exclu (trous).

> **[Correction du vérificateur : correspondance avec le code]** `backtest/walkforward.py:walk_forward_windows(dates, train_years, test_months, embargo_days, expanding=True, min_train_days)` travaille en **ancrages calendaires** (années et mois), pas en nombre de séances. Il n'a **qu'un seul** écart, `embargo_days`, qui compte des séances retirées à la **fin** de l'apprentissage, juste **avant** le test. Ce paramètre joue donc le rôle de la **purge**. L'embargo « après le test » de López de Prado n'existe pas en walk-forward pur ; il ne s'applique qu'en k-fold purgé et en CPCV. Correspondance à coder :
> - `train_years = 2` (environ 496 séances à 248 séances par an) et `min_train_days = 480` ;
> - `test_months = 3` (environ 62 séances) ;
> - `embargo_days = h + 21` (purge du label, plus une marge pour la mémoire sérielle d'environ 10 séances), soit 42 pour un label mensuel et 84 pour un label trimestriel. C'est une règle prudente, choix du vérificateur.
>
> En CPCV, purge (h) et embargo (21) restent deux paramètres séparés (Source : lecture du code, 2026-11-22 ; confiance high pour le code, medium pour la règle h + 21.)

---

## 7. Bootstrap stationnaire (Politis-Romano) et IC sur la performance

### 7.1 Références

- Politis, D. N. & Romano, J. P. (1994). « The Stationary Bootstrap ». *JASA* 89, 1303-1313 : blocs de longueur **géométrique** de moyenne b, série rééchantillonnée stationnaire. https://gnosis.library.ucy.ac.cy/handle/7/57533 [S].
- Politis, D. N. & White, H. (2004). « Automatic Block-Length Selection for the Dependent Bootstrap ». *Econometric Reviews* 23(1), 53-70. https://ideas.repec.org/a/taf/emetrv/v23y2004i1p53-70.html [S].
- Patton, A., Politis, D. N. & White, H. (2009). Correction, *Econometric Reviews* 28(4), 372-375 : la constante devient **D_SB = 2·ĝ(0)²**, et ce sont les résultats corrigés qu'il faut utiliser. https://public.econ.duke.edu/~ap172/Patton_Politis_White_2009.pdf [S]. Code R : https://public.econ.duke.edu/~ap172/ppw.R.txt [S].
- Ledoit, O. & Wolf, M. (2008). « Robust performance hypothesis testing with the Sharpe ratio ». *Journal of Empirical Finance* 15(5), 850-859 : bootstrap **studentisé** par blocs circulaires pour tester la **différence** de deux Sharpe, valide avec des queues épaisses et de la dépendance. https://econpapers.repec.org/RePEc:eee:empfin:v:15:y:2008:i:5:p:850-859 ; PDF : https://uzh.ch/cmsssl/econ/dam/jcr:ffffffff-935a-b0d6-0000-00007214c2bc/jef_2008pdf.pdf [S].

### 7.2 Algorithme

```
I₁ ~ U{1..n} ;  pour t ≥ 1 : I_{t+1} = U{1..n} avec probabilité p = 1/b, sinon (I_t mod n) + 1
X*_t = X_{I_t}  ;  statistique θ* = f(X*) ;  répéter B fois ; IC = percentiles (ou studentisé)
```

Longueur optimale de Politis-White (version corrigée, noyau « flat-top » λ(s) = 1 si |s| ≤ ½, 2(1 − |s|) si ½ < |s| ≤ 1, 0 sinon) :

```
Ĝ = Σ_{|k| ≤ M} λ(k/M)·|k|·R̂(k) ;   ĝ(0) = Σ_{|k| ≤ M} λ(k/M)·R̂(k) ;   D_SB = 2·ĝ(0)²
b_opt = (2·Ĝ² / D_SB)^{1/3} · n^{1/3}
```

M = 2·m̂, où m̂ est le plus petit retard au-delà duquel K_n = max(5, ⌈√log₁₀ n⌉) autocorrélations consécutives restent sous 2·√(log₁₀ n / n). Confiance : **medium-high**. **[Vérifié le 2026-11-22]** Les constantes figurent à l'identique dans `arch.bootstrap.optimal_block_length` (arch 9.0.0, PyPI, qui cite Politis & White 2004, *Econometric Reviews* 23:1, 53-70, DOI 10.1081/ETC-120028836, et Patton, Politis & White 2009, *Econometric Reviews* 28:4, 372-375, DOI 10.1080/07474930802459016) :
- D_SB = 2·ĝ(0)² et D_CB = (4/3)·ĝ(0)² ;
- noyau flat-top ;
- bande de ±2√(log₁₀ n / n) ;
- m_max = ⌈√n⌉ + K_n et b_max = ⌈min(3√n, n/3)⌉.

Seule différence : arch prend K_n = max(5, log₁₀ n). Pour n < 10⁵, les deux règles donnent K_n = 5. Une réimplémentation indépendante retrouve exactement les valeurs du §7.3.

### 7.3 Mesures sur nos BOC [C]

| Série | b_opt (Politis-White corrigé) |
|---|---|
| Composite journalier | 0,4 (pratiquement i.i.d. ; plancher pratique : 1) |
| Composite journalier, carrés (volatilité) | 8,5 |
| Panier EW journalier | **8,6** |
| Panier EW journalier, carrés | **12,4** |
| Composite hebdomadaire | 2,7 semaines |
| Panier EW hebdomadaire | 7,7 semaines |

Effet de b sur l'IC à 95 % du Sharpe annualisé (naïf) du panier EW, 2022-2026, B = 1 000 :

| b | 1 (i.i.d.) | 5 | 10 | 20 | 40 |
|---|---|---|---|---|---|
| IC 95 % | [2,22 ; 4,10] | [1,85 ; 4,52] | [1,81 ; 4,71] | [1,46 ; 4,97] | [1,40 ; 5,05] |
| Écart-type bootstrap | 0,49 | 0,69 | 0,78 | 0,90 | 0,94 |

Le niveau élevé de ce Sharpe reflète un marché très haussier (+144 %) et un taux sans risque pris à 0. Le chiffre qui compte ici est **l'élargissement de l'IC**. Pour la meilleure stratégie de la grille (IR actif 0,98) : IC 95 % = [−0,28 ; 2,28] avec b = 10, et P(IR ≤ 0) = 5,8 %.

### 7.4 Paramètres BRVM

- `stationary_bootstrap(..., mean_block=20, n_boot=5000, seed=…)` pour des rendements journaliers ; **mean_block = 8** (semaines) en hebdomadaire.
- Règle : b = max(b_opt(r), b_opt(r²)) arrondi vers le haut, avec un **plancher de 10 séances** (choix interne : la statistique de Sharpe dépend de la moyenne et de la variance).
- Comparer deux stratégies (ou stratégie contre indice) par le test studentisé de Ledoit-Wolf (2008) sur la **différence** de Sharpe, et non par deux IC séparés.

---

## 8. Covariance rétrécie (Ledoit-Wolf)

### 8.1 Références

- Ledoit & Wolf (2003). « Improved estimation of the covariance matrix of stock returns with an application to portfolio selection ». *Journal of Empirical Finance* 10(5) : cible à **un facteur** (marché). PDF : https://uzh.ch/cmsssl/econ/dam/jcr:ffffffff-935a-b0d6-ffff-ffff9961f70f/jef.pdf [S].
- Ledoit & Wolf (2004). « Honey, I Shrunk the Sample Covariance Matrix ». *Journal of Portfolio Management* 30(4), 110-119, DOI 10.3905/jpm.2004.110 : cible à **corrélation constante** ; intensité optimale **κ̂/T** bornée à [0, 1]. https://econ-papers.upf.edu/papers/691.pdf ; notes : https://reasonabledeviations.com/notes/papers/ledoit_wolf_covariance [S].
- Ledoit & Wolf (2004). « A well-conditioned estimator for large-dimensional covariance matrices ». *Journal of Multivariate Analysis* 88(2), février 2004, p. 365-411 : cible **identité** ; c'est l'estimateur de `sklearn.covariance.LedoitWolf` (https://scikit-learn.org/stable/modules/generated/sklearn.covariance.LedoitWolf.html). Volume, numéro, mois et pages sont confirmés le 2026-11-22 par la docstring de scikit-learn 1.9.1 (source secondaire, confiance medium-high).
- Effet Epps : Epps (1979), *JASA* 74 [B]. Bruit des matrices de corrélation et loi de Marchenko-Pastur : Laloux, Cizeau, Bouchaud & Potters (1999), *Physical Review Letters* 83 [B].

### 8.2 Formules (cible à corrélation constante)

```
Σ̂ = δ*·F + (1 − δ*)·S          F_ii = s_ii ;  F_ij = r̄·√(s_ii·s_jj) ;  r̄ = corrélation moyenne
δ* = max(0, min(1, κ̂/T)) ;  κ̂ = (π̂ − ρ̂)/γ̂
π̂ = Σ_ij (1/T)·Σ_t [(y_it − ȳ_i)(y_jt − ȳ_j) − s_ij]²
ρ̂ = Σ_i π̂_ii + Σ_{i≠j} (r̄/2)·( √(s_jj/s_ii)·θ̂_ii,ij + √(s_ii/s_jj)·θ̂_jj,ij )
θ̂_ii,ij = (1/T)·Σ_t [(y_it − ȳ_i)² − s_ii]·[(y_it − ȳ_i)(y_jt − ȳ_j) − s_ij]
γ̂ = ‖F − S‖²_F
```

Structure confirmée [S]. Expression complète transcrite du code `covCor.m` des auteurs, comme dans `portfolio/risk.py`. Confiance : **medium-high**. **[Vérifié le 2026-11-22]** C'est la même structure (π̂, ρ̂ avec θ̂, γ̂ = ‖F − S‖²) que `CovarianceShrinkage._ledoit_wolf_constant_correlation` de PyPortfolioOpt 1.6.0. Une réimplémentation indépendante redonne δ* = 0,68 / 0,79 / 0,87 (tableau ci-dessous).

Bord du bruit (Marchenko-Pastur, corrélations) : λ₊ = (1 + √(N/T))². Les valeurs propres sous λ₊ sont indiscernables du bruit.

### 8.3 Mesures sur nos BOC [C] (44 titres présents au moins 95 % des séances)

| Fenêtre | T | N/T | Corr. moyenne | λ₊ | Valeurs propres > λ₊ | 1ʳᵉ valeur propre (part) | Ratio de participation | Conditionnement de S | **δ* (corr. constante)** | δ* (identité, sklearn) |
|---|---|---|---|---|---|---|---|---|---|---|
| Journalier, 2 ans | 456 | 0,10 | 0,046 | 1,72 | 2 | 3,29 (7,5 %) | 35,5 | 16 | **0,68** | 0,21 |
| Hebdomadaire, 2 ans | 97 | 0,45 | 0,087 | 2,80 | 2 | 5,31 (12,1 %) | 23,1 | 135 | **0,79** | 0,36 |
| Mensuel, environ 4 ans | 49 | 0,90 | 0,179 | 3,79 | 1 | 9,64 (21,9 %) | 12,6 | 32 585 | **0,86** | 0,48 |

Lecture :
1. La corrélation **quadruple** entre le journalier et le mensuel (effet Epps des prix périmés). Le risque d'un portefeuille calculé sur données journalières est donc trop bas.
2. Seules **1 à 2** valeurs propres dépassent le bruit : la structure se réduit à un facteur marché, plus peut-être un facteur pays ou secteur. Tout le reste est du bruit d'estimation, ce qui justifie un **rétrécissement fort** (δ* ≈ 0,7-0,9).
3. En mensuel, S est presque singulière (conditionnement de 3·10⁴). Un optimiseur de Markowitz sur S y produirait des poids absurdes.

### 8.4 Paramètres BRVM

| Paramètre | Valeur |
|---|---|
| Fréquence | **hebdomadaire** (vendredi, rendements composés), ou journalier agrégé avec `horizon=5` dans `ledoit_wolf_cov` |
| Fenêtre | **104 semaines** (2 ans), minimum 52 |
| Cible | **corrélation constante** (par défaut) ; variante « un facteur » (marché, bêta de Dimson) en challenger |
| δ* | estimé (attendu 0,7-0,9) ; **plancher de 0,5** (choix interne, prudence pour T/N ≈ 2) |
| Données manquantes | covariances par paires (implémenté) puis projection sur la matrice semi-définie positive la plus proche (`nearest_psd_cov`) |
| Volatilité pour le dosage | soit hebdomadaire × √52, soit journalière × facteur de Lo du **portefeuille**. **Jamais** journalière × √252 pour un portefeuille |
| Variante future | rétrécissement **non linéaire** (Ledoit & Wolf 2020, *Annals of Statistics* [B]) quand N/T > 0,5 |

---

## 9. Hierarchical Risk Parity (HRP)

### 9.1 Référence

López de Prado, M. (2016). « Building Diversified Portfolios that Outperform Out of Sample ». *Journal of Portfolio Management* 42(4), 59-69, DOI 10.3905/jpm.2016.42.4.059. https://papers.ssrn.com/abstract=2708678 [S]. L'article vise l'instabilité, la concentration et la sous-performance des optimiseurs quadratiques. Selon des simulations de Monte-Carlo (mémoire de CBS, https://research-api.cbs.dk/ws/portalfiles/portal/76452070/1332322_Master_Thesis_Hierarchical_Risk_Parity.pdf), HRP a une variance hors échantillon plus faible que le portefeuille de variance minimale [S, low-medium].

### 9.2 Algorithme

1. Distance : **d_ij = √(½·(1 − ρ_ij))**.
2. (Code original) distance des distances d̃_ij = ‖d_·i − d_·j‖₂, puis classification hiérarchique à **lien simple**.
3. **Quasi-diagonalisation** : réordonner les titres selon les feuilles du dendrogramme.
4. **Bissection récursive** : couper chaque grappe en deux moitiés L₀ et L₁. Avec V_k = w̃_kᵀ·Σ_k·w̃_k (w̃_k = poids inverses de la variance dans L_k), α = 1 − V₀/(V₀ + V₁), puis w[L₀] ×= α et w[L₁] ×= 1 − α.

Pas d'inversion de Σ, d'où la robustesse aux matrices mal conditionnées (section 8.3). Les détails de l'algorithme n'ont pas été relus dans le texte pendant la session ; ils sont conformes à `portfolio/risk.py:hrp_weights`. Confiance : **medium**. **[Vérificateur, 2026-11-22]** La distance d = √(½(1 − ρ)) et le lien `single` par défaut sont confirmés par une implémentation tierce : `HRPOpt.optimize(linkage_method="single")` dans PyPortfolioOpt 1.6.0, qui reprend le code de López de Prado avec sa permission. Cette implémentation classe directement sur d, **sans** distance des distances. L'affirmation selon laquelle d̃ « reproduit l'article » reste **[NON VÉRIFIÉ]** dans le texte primaire. Attention : dans le projet, `hrp_weights(distance_of_distances=False)` est la valeur par défaut, donc il faut passer `True` explicitement si l'on garde ce choix. skfolio 1.14.4 utilise `ward` par défaut : le choix du lien n'est pas neutre et doit être compté dans le registre.

### 9.3 Paramètres BRVM

| Paramètre | Valeur |
|---|---|
| Entrée | covariance **hebdomadaire 104 semaines, rétrécie** (section 8) |
| Lien | `single` (article) ; `ward` en challenger, **compté dans le registre d'essais** |
| `distance_of_distances` | `True` pour reproduire l'article |
| Rôle | (a) **pondération à l'intérieur** de la sélection (les ~15 titres retenus par le score) ; (b) portefeuille de référence « risque » à battre |
| Contraintes | appliquer ensuite `max_weight` (15 %), les plafonds pays et secteur et les plafonds de liquidité (`construct.liquidity_caps`). HRP seul ne connaît pas la liquidité |
| N effectif attendu | ratio de participation hebdomadaire d'environ 23 sur 44 : HRP diversifie entre un petit nombre de grappes réelles (à identifier sur le dendrogramme ; non mesuré dans cette revue) |

---

## 10. Black-Litterman

### 10.1 Références

- Black, F. & Litterman, R. (1992). « Global Portfolio Optimization ». *Financial Analysts Journal* 48(5), 28-43. https://rpc.cfainstitute.org/research/financial-analysts-journal/1992/faj-v48-n5-28 [S]. Les rendements d'équilibre servent de point de départ neutre, que l'on incline selon des vues pondérées par leur confiance (résumé).
- He, G. & Litterman, R. (1999). « The Intuition Behind Black-Litterman Model Portfolios ». Goldman Sachs [S pour l'existence ; contenu non lu].
- Idzorek, T. « A Step-by-Step Guide to the Black-Litterman Model — Incorporating user-specified confidence levels » (document de travail, environ 2003-2005 ; PDF repéré : https://www.cis.upenn.edu/~mkearns/finread/idzorek.pdf) [S pour l'existence ; formule de confiance non lue].

### 10.2 Formules (forme standard)

```
Π = δ·Σ·w_mkt                                                (rendements implicites d'équilibre)
μ_BL = [ (τΣ)⁻¹ + Pᵀ Ω⁻¹ P ]⁻¹ · [ (τΣ)⁻¹ Π + Pᵀ Ω⁻¹ Q ]
     = Π + τΣPᵀ (P τΣ Pᵀ + Ω)⁻¹ (Q − PΠ)                     (forme équivalente)
Σ_post = Σ + [ (τΣ)⁻¹ + Pᵀ Ω⁻¹ P ]⁻¹                         (covariance prédictive)
Ω (He-Litterman) = diag(P · τΣ · Pᵀ)
```

δ est l'aversion au risque implicite (δ = prime de marché / variance du marché), P la matrice des vues, Q leurs valeurs et Ω leur incertitude. Confiance : **medium** (formules standard [B], non relues dans le texte pendant la session).

### 10.3 Usage pour BRVM Alpha (choix internes)

- **Vues = alpha de Grinold** (section 16) : P = I (une vue par titre), Q_i = Π_i + IC·ω_i·z_i, avec Ω_ii = **(ω_i·σ_IC)²**, où σ_IC est l'incertitude sur l'IC (section 15). Le modèle devient alors une **combinaison bayésienne** équilibre + signaux, où la confiance vient de la **mesure** de l'IC et non d'une opinion.
- **w_mkt** : capitalisations **flottantes** de l'univers éligible. Le flottant est publié par la BRVM (avis n° 303 du 12/10/2026, cité en revue 01). Sinon, utiliser les capitalisations brutes avec un plafond de 15 % par titre, pour éviter que les plus grosses capitalisations ne dominent Π.
- **τ** : **0,05** (choix interne dans la plage usuelle 0,025-0,05) **[NON VÉRIFIÉ dans une source primaire]**. Seule confirmation secondaire : 0,05 est la valeur par défaut de `BlackLittermanModel` dans PyPortfolioOpt 1.6.0. Le même code définit l'Ω par défaut comme diag(τ·PΣPᵀ) et l'attribue à He & Litterman (1999). Avec un Ω de He-Litterman, μ_BL ne dépend **pas du tout** de τ quand P = I.
- **[Correction du vérificateur]** L'Ω retenu ici, Ω_ii = (ω_i·σ_IC)², **n'est pas proportionnel à τ** : la phrase précédente ne s'y applique donc pas. Ordre de grandeur en mensuel :
  - Ω_ii ≈ (0,092 × 0,02)² ≈ 3·10⁻⁶ ;
  - τ·σ_i² ≈ 0,05 × 0,113² ≈ 6·10⁻⁴.

  Le poids donné à chaque vue, τσ²/(τσ² + Ω), vaut donc environ **0,99** quel que soit τ dans [0,025 ; 0,05]. On obtient μ_BL ≈ Q = Π + α. Black-Litterman n'apporte alors **presque aucun rétrécissement supplémentaire** : tout le rétrécissement de l'alpha vient de IC_post (§15.4). Il faut le savoir avant de compter sur BL comme second garde-fou. Il faut aussi exprimer Σ et Ω sur **le même horizon** (mensuel). Calcul du vérificateur, confiance medium.
- **δ** : calibré pour que la prime implicite du Composite égale une hypothèse de prime **À CALIBRER** (aucune valeur sourcée pour la BRVM dans cette revue ; le BOC publie un indicateur « prime de risque du marché » de 0,58 dont la définition n'est pas documentée ici).
- Optimisation finale sous contraintes (long-only, plafonds, liquidité) avec Σ rétrécie. BL sert à produire **μ**, pas à lever les contraintes.

---

## 11. Critère de Kelly fractionnel

### 11.1 Références

- Kelly, J. L. (1956). « A New Interpretation of Information Rate ». *Bell System Technical Journal* 35(4) [B].
- Thorp, E. O. (2006). « The Kelly Criterion in Blackjack, Sports Betting, and the Stock Market », chapitre du *Handbook of Asset and Liability Management*. PDF : https://www.gwern.net/doc/statistics/decision/2006-thorp.pdf [S pour l'existence et la structure : approximation continue, « the case for fractional Kelly »].
- MacLean, L. C., Thorp, E. O. & Ziemba, W. T. (2010). « Long-term capital growth: the good and bad properties of the Kelly and fractional Kelly capital growth criteria ». *Quantitative Finance* 10(7), 681-687. https://www.stat.berkeley.edu/~aldous/157/Papers/Good_Bad_Kelly.pdf [S]. Le Kelly maximise le taux de croissance limite. Il est **risqué à court terme**, car son aversion au risque d'Arrow-Pratt est faible. Le Kelly fractionnel, mélange de Kelly et de cash, lisse la trajectoire de richesse et **modère l'impact des erreurs d'estimation**. Même un investisseur Kelly peut perdre l'essentiel de sa richesse dans de mauvais scénarios. Confiance : **medium-high**.

### 11.2 Formules et dérivations [D]

Pour une exposition f à un actif d'excès de rendement μ, de volatilité σ et de Sharpe S = μ/σ (temps continu, mouvement brownien géométrique) :

```
g(f) = f·μ − ½·f²·σ²   ⇒   f* = μ/σ²     (vectoriel : f* = Σ⁻¹(μ − r))
Kelly fractionnel f = c·f* :  g(c) = (c − c²/2)·S² ;  vol(ln W) = c·S
```

| c (fraction de Kelly) | Croissance relative g(c)/g(1) = 2c − c² | Variance relative c² | P(la richesse touche un jour x·W₀) = x^{(2/c) − 1} | P(perdre la moitié un jour) |
|---|---|---|---|---|
| 1 (plein Kelly) | 100 % | 100 % | x | **50 %** |
| ½ | **75 %** | **25 %** | x³ | **12,5 %** |
| ¼ | 43,8 % | 6,3 % | x⁷ | 0,8 % |
| 2 (μ surestimé ×2) | **0 %** | 400 % | — | — |

Dérivation de la colonne 4 : ln W a une dérive m = (c − c²/2)·S² et une variance s² = c²·S² ; la probabilité de toucher le niveau −a est exp(−2ma/s²) = exp(−a·(2/c − 1)). Confiance : **high** (calcul), mais le modèle suppose des paramètres **connus** et des rendements continus et normaux.

### 11.3 Le vrai problème à la BRVM : l'erreur sur μ [C]

Panier EW 2022-2026 (mensuel) : μ = 29,4 %/an, σ = 16,3 %/an, sur 4,9 ans. L'erreur-type de μ vaut σ/√années = **7,4 %/an**, d'où un IC 95 % de **[15,0 % ; 43,8 %]**. Un Kelly « historique » (r = 0, simplification) serait de 11 fois le capital, ce qui est absurde : c'est un artefact d'un marché haussier exceptionnel. Pour l'alpha **actif**, l'incertitude relative est encore plus grande : IR estimé 0,98 contre un IC [−0,28 ; 2,28] (section 7.3). Le Kelly plein sur un μ estimé revient presque toujours à **sur-parier**, et le ½-Kelly appliqué à un μ surestimé d'un facteur 2 devient de facto un plein Kelly.

### 11.4 Paramètres BRVM

| Paramètre | Valeur | Justification |
|---|---|---|
| `fractional_kelly_scale(..., fraction=0.25)` | **¼** par défaut, **plafond ½** | Erreur d'estimation dominante (§11.3) ; choix interne cohérent avec le code existant |
| μ en entrée | **alpha rétréci** (Grinold × IC rétréci, section 15) ou μ_BL, **jamais** une moyenne historique | §15.3 : c = 0 |
| σ, Σ | Hebdomadaire rétrécie, ou journalière × facteur de Lo | §2.2, §8 |
| `max_gross` | **1,0** (pas de levier : achat seul, pas de crédit-titres à la BRVM) | Contrainte de marché |
| Rôle | Fixe la **part investie** (actions contre cash/obligations) et plafonne la taille des lignes. Ne fixe **pas** les poids relatifs, qui relèvent du score, de HRP et de BL | Choix interne |

---

## 12. Optimisation CVaR

### 12.1 Références

- Rockafellar, R. T. & Uryasev, S. (2000). « Optimization of conditional value-at-risk ». *Journal of Risk* 2, 21-42 **[NON VÉRIFIÉ : numéro et pages]**. Le vérificateur se souvient de la citation usuelle « vol. 2, n° 3, p. 21-41 », mais n'a pas pu la contrôler en session ; la notice RePEc ci-dessous doit trancher. L'existence et le titre sont confirmés par skfolio 1.14.4, qui cite « Optimization of conditional value-at-risk », Rockafellar & Uryasev (2000). Contenu : VaR et CVaR calculées **simultanément** ; avec des scénarios, le problème devient un **programme linéaire**. https://ideas.repec.org/a/rsk/journ4/2161159.html ; version de travail : https://sites.math.washington.edu/~rtr/papers/rtr179-CVaR1.pdf [S]. Synthèse : https://arxiv.org/pdf/1511.00140 [S].
- Rockafellar & Uryasev (2002). « Conditional value-at-risk for general loss distributions ». *Journal of Banking & Finance* 26(7) [B].

### 12.2 Formules

```
CVaR_α(w) = min_ζ  F_α(w, ζ),   F_α(w, ζ) = ζ + 1/((1 − α)·S) · Σ_s max(0, L_s(w) − ζ)
L_s(w) = −r_sᵀ w   (perte du scénario s) ;  le ζ optimal est la VaR_α

Programme linéaire :  min_{w, ζ, u}  ζ + 1/((1 − α)S)·Σ u_s
                      s.c.  u_s ≥ −r_sᵀ w − ζ ,  u_s ≥ 0 ,  contraintes sur w
```

Certaines sources écrivent 1/α au lieu de 1/(1 − α), selon la convention de niveau de queue [S]. Confiance : **high** pour l'identité variationnelle.

### 12.3 Mesures sur nos BOC [C]

| Série | VaR / CVaR 95 % journalière | VaR / CVaR 95 % hebdo | VaR / CVaR 95 % mensuelle | Pire séance / semaine / mois |
|---|---|---|---|---|
| Composite | 0,92 % / 1,32 % | 1,81 % / 2,71 % | 4,59 % / 6,21 % | −3,66 % / −4,77 % / −7,82 % |
| Panier EW | 0,84 % / 1,21 % | 1,96 % / 2,99 % | 6,26 % / **7,25 %** | −3,69 % / −5,64 % / −8,25 % |
| Titre médian | — | CVaR 95 % hebdo : **10,2 %** | — | — |

Pour le panier, la CVaR journalière × √5 donne 2,71 % contre 2,99 % mesuré (−9 %), et × √21 donne 5,56 % contre 7,25 % mesuré (**−23 %**). Les pertes **s'étalent sur plusieurs séances** (limites de ±7,5 % et prix périmés). La règle de la racine carrée sous-estime le risque de queue.

### 12.4 Paramètres BRVM

| Paramètre | Valeur |
|---|---|
| Horizon des scénarios | **5 séances** (rendements hebdomadaires glissants) ; 21 séances pour le reporting |
| Génération | **5 000 scénarios** par bootstrap stationnaire de blocs de semaines (b = 8 semaines) sur 2 à 5 ans, plus des scénarios de stress explicites : Composite −15 % en 2 mois (repère : la pire baisse sur 8 semaines vaut −14,3 % en 2017-2020 et −8,9 % en 2022-2026). **[Correction du vérificateur]** Le repère « drawdown maximal de −13,9 % » ne vaut que pour 2022-2026. Les BOC 2017-2020 montrent un **drawdown du Composite de −57,9 %**, du 01/03/2017 au 26/10/2020 (285,18 le 02/01/2017, 145,37 le 31/12/2020, soit −49 % sur quatre ans). Il faut ajouter un **scénario de marché baissier prolongé** (−50 % sur environ 3,5 ans) au jeu de stress, pour la CVaR et pour le dimensionnement de Kelly. Source : BOC locaux et recalcul du vérificateur, confiance high |
| α | **0,95**. Avec 255 semaines d'historique brut, la queue à 95 % ne contient qu'environ 13 observations, d'où la nécessité du bootstrap. Utiliser α = 0,90 pour une estimation stable si les scénarios ne sont pas rééchantillonnés |
| Usage | **contrainte** (CVaR du portefeuille ≤ 1,25 × CVaR du Composite, choix interne) plutôt qu'objectif unique ; l'objectif reste l'alpha rétréci |
| Contrôle | Comparer chaque mois la CVaR ex ante et les pertes réalisées (test de couverture) |

---

## 13. Trading peu fréquent et prix périmés

### 13.1 Bêta de Dimson (1979)

Dimson, E. (1979). « Risk measurement when shares are subject to infrequent trading ». *Journal of Financial Economics* 7(2), 197-226, DOI 10.1016/0304-405x(79)90013-8 : méthode des **coefficients agrégés** [S]. Confiance : **medium-high**.

```
r_i,t = α + Σ_{k = −K_lead..K_lag} β_k · r_m,t−k + ε_t      β_Dimson = Σ_k β_k
```

### 13.2 Bêta de Scholes-Williams (1977)

Scholes, M. & Williams, J. (1977). « Estimating betas from nonsynchronous data ». *Journal of Financial Economics* 5(3), 309-327. https://econpapers.repec.org/RePEc:eee:jfinec:v:5:y:1977:i:3:p:309-327 [S pour la référence]. Les bêtas MCO sur rendements journaliers sont biaisés et non convergents en présence de non-synchronisme [S]. Formule standard [B, medium] :

```
β_SW = (β₋₁ + β₀ + β₊₁) / (1 + 2·ρ_m)
```

β₋₁, β₀ et β₊₁ sont les pentes des régressions **simples** de r_i sur r_m retardé, contemporain et avancé ; ρ_m est l'autocorrélation d'ordre 1 du marché.

### 13.3 Lissage de Getmansky, Lo & Makarov (2004)

Getmansky, M., Lo, A. W. & Makarov, I. (2004). « An econometric model of serial correlation and illiquidity in hedge fund returns ». *Journal of Financial Economics* 74, 529-609. NBER w9571 : https://www.nber.org/papers/w9571 ; page de l'auteur : https://web.mit.edu/Alo/www/Papers/serialhf.html [S]. Les rendements publiés sont plus lisses que les rendements économiques vrais, ce qui sous-estime la volatilité et gonfle le Sharpe ; l'article propose des estimateurs du profil de lissage et un Sharpe ajusté [S]. Spécification [medium ; la forme exacte MA(2) n'a été vue que dans une source secondaire, https://stat.ethz.ch/pipermail/r-sig-finance/2007q3/001691.html] :

```
R°_t = θ₀·R_t + θ₁·R_{t−1} + θ₂·R_{t−2},   θ_j ≥ 0 (en théorie),  Σθ_j = 1
Var(R°) = ξ·σ²  avec  ξ = Σθ_j²  ≤ 1
Estimation : MA(2) par maximum de vraisemblance, ψ̂ ; puis θ̂_j = ψ̂_j / (1 + ψ̂₁ + ψ̂₂)
SR vrai (par période) = √ξ · SR observé  ;  annualisation ensuite par √q (rendements vrais i.i.d.)   [D]
```

### 13.4 Ajustement de Lo (2002) du Sharpe annualisé

Lo, A. W. (2002). « The Statistics of Sharpe Ratios ». *Financial Analysts Journal* 58(4), 36-52. https://ideas.repec.org/a/taf/ufajxx/v58y2002i4p36-52.html [S]. Multiplier un Sharpe mensuel par √12 n'est valide que sous des conditions particulières ; le Sharpe annuel d'un hedge fund peut être **surestimé de 65 %** à cause de l'autocorrélation [S]. Formule (confirmée à l'identique dans `quant/stats.py` ; le moteur de recherche l'a restituée de mémoire sans pouvoir la vérifier, d'où medium) :

```
SR(q) = η(q)·SR ,   η(q) = q / √( q + 2·Σ_{k=1}^{q−1} (q − k)·ρ_k )
```

> **[Précision du vérificateur : notation]** Chez Lo (2002), **q est l'horizon d'agrégation**. Pour passer du journalier à l'annuel, q = T = 252 (ou 248 séances réelles). Dans `quant/stats.py:lo_adjusted_sharpe(returns, q, periods_per_year)`, η est calculé à T = `periods_per_year`, et **`q` désigne le retard maximal** des autocorrélations ρ_k estimées, supposées nulles au-delà (troncature). Le paramètre `lo_q` de ce document (10 en journalier, 4 en hebdomadaire, 2 en mensuel) est donc une **troncature**, pas l'horizon de Lo. La mise en garde « jamais q = 252 » veut dire : ne jamais additionner 251 autocorrélations empiriques bruitées. Formule et valeurs inchangées : 0,771 et 0,582 sont reproduits à l'identique (troncature 10, T = 252).

### 13.5 Mesures sur nos BOC [C]

**Bêtas** (2023-2026, 46 titres, marché = Composite journalier, ρ_m = −0,03) :

| Estimateur | Bêta médian |
|---|---|
| MCO journalier | **0,50** |
| Dimson (1 avance, retards 0-1) | 0,74 |
| Dimson (1 avance, retards 0-2) | 0,77 |
| **Dimson (1 avance, retards 0-5)** | **0,88** |
| Scholes-Williams | 0,78 |
| MCO hebdomadaire | 0,71 |

Rapport médian Dimson (−1..+2) / MCO : **1,68**. Rapport hebdomadaire / MCO : 1,42. Le coefficient au retard 1 a t > 2 pour 22 % des titres, au retard 2 pour 4 %, à l'avance 1 (|t| > 2) pour 11 %.

**Lissage GLM** (θ₀ ; θ₁ ; θ₂ ; ξ) :

| Série | θ₀ | θ₁ | θ₂ | ξ | √ξ |
|---|---|---|---|---|---|
| Composite journalier | 0,959 | −0,005 | 0,047 | 0,92 | 0,96 |
| Composite hebdomadaire | 0,751 | 0,120 | 0,129 | 0,59 | 0,77 |
| Panier EW journalier | 0,755 | 0,148 | 0,097 | 0,60 | 0,78 |
| Panier EW hebdomadaire | 0,719 | 0,224 | 0,058 | 0,57 | 0,75 |

**Lo 2002** (Sharpe naïf → corrigé, r = 0, illustration) : Composite journalier 1,99 → 1,54 (η/√252 = 0,771, q = 10 retards) ; panier EW 3,18 → 1,85 (0,582). Attention au choix du retard maximal : sur la meilleure stratégie de la grille, le Sharpe corrigé vaut 0,75 (q = 5) ou 0,87 (q = 10). Il vaut 1,84 si l'on prend **tous** les retards jusqu'à 252, car on additionne alors 250 autocorrélations bruitées : **il ne faut jamais tronquer à q = 252**.

### 13.6 Paramètres BRVM

| Usage | Paramètre |
|---|---|
| Bêta (risque, neutralisation, momentum résiduel) | `dimson_beta(..., lags=5)` en journalier sur 2 ans, avec 1 avance et 5 retards. Note : l'implémentation actuelle `dimson_betas` est **symétrique** (−K..K). Il faut ajouter un paramètre `leads=1` séparé (à coder). Variante robuste : MCO hebdomadaire sur 104 semaines avec 1 avance et 1 retard |
| Rétrécissement du bêta | vers la moyenne transversale (≈ 0,8-0,9 en Dimson) avec un poids bayésien (section 15.4) |
| Sharpe annualisé | toujours publier **naïf et Lo** ; Lo avec q = 10 (journalier), q = 4 (hebdomadaire), q = 2 (mensuel) |
| Vérification croisée | Sharpe GLM (√ξ) : si \|SR_Lo − SR_GLM\| / SR_Lo > 25 %, signaler une instabilité (choix interne) |
| Tests d'efficience et IC | rendements **de transaction à transaction**, ou exclusion des séances à variation nulle et volume quasi nul (revue 02) |

---

## 14. Modèles de régimes et filtres de tendance

### 14.1 Références [B — non vérifiées en session, budget de recherche épuisé]

- Hamilton, J. D. (1989). « A New Approach to the Economic Analysis of Nonstationary Time Series and the Business Cycle ». *Econometrica* 57(2), 357-384 (modèle markovien à changement de régime, filtre d'Hamilton).
- Ang, A. & Bekaert, G. (2002). « International Asset Allocation with Regime Shifts ». *Review of Financial Studies* 15(4).
- Moskowitz, T., Ooi, Y. H. & Pedersen, L. H. (2012). « Time Series Momentum ». *Journal of Financial Economics* 104(2).
- Faber, M. (2007). « A Quantitative Approach to Tactical Asset Allocation ». *Journal of Wealth Management* (moyenne mobile de 10 mois), SSRN 962461.
- Implémentation utilisée : `statsmodels.tsa.regime_switching.MarkovRegression` (statsmodels 0.15.0, installé).

### 14.2 Modèle

```
r_t | s_t = j  ~  N(μ_j, σ_j²) ,   P(s_t = j | s_{t−1} = i) = p_ij
Durée moyenne d'un régime : 1/(1 − p_jj)
Filtre (Hamilton) : ξ_{t|t} ∝ f(r_t | s_t)·(Pᵀ ξ_{t−1|t−1})  ;  lissage de Kim pour ξ_{t|T}
```

(Formules standard, confiance medium.) **Pour la décision en temps réel, n'utiliser que les probabilités filtrées ξ_{t|t}**. Les probabilités lissées utilisent le futur, ce qui serait un biais d'anticipation.

### 14.3 Mesures sur nos BOC [C] (Composite hebdomadaire, 255 semaines, 2022-2026)

| | Régime A (calme) | Régime B (agité) |
|---|---|---|
| μ hebdo | 0,21 % | **0,52 %** |
| σ hebdo | 0,87 % (≈ 6,3 %/an) | 1,75 % (≈ 12,6 %/an) |
| P(rester) | 0,945 | 0,947 |
| Durée moyenne | 18,3 semaines | 18,9 semaines |
| Part du temps | 50 % | 50 % |

BIC : 894,0 (2 régimes) contre 900,1 (1 régime). Deux régimes de **volatilité** existent bien.

Filtres de tendance : le Composite était au-dessus de sa moyenne mobile de 200 séances **86 %** du temps, avec **3 croisements** (3 aussi avec une bande de ±2 %). Au-dessus de sa moyenne mobile de 10 mois : 82 % des 51 mois, 3 croisements. Drawdown maximal : −13,9 %.

**Lecture** : (i) sur cette période, l'état agité a eu le rendement moyen le **plus élevé**. La règle des marchés développés (forte volatilité = marché baissier) **ne s'applique pas** telle quelle. (ii) **Trois** signaux en cinq ans ne permettent **aucune** inférence sur la valeur d'un filtre de tendance. Un backtest de filtre de tendance sur cette période est du **pur surapprentissage**.

> **[Recalcul et mise à jour du vérificateur, 2026-11-22]** Sur 254 semaines (contre 255), le modèle à 2 régimes donne :
> - BIC = 891,5 (2 régimes) contre 897,5 (1 régime). L'écart de BIC, environ 6, est le même que dans la revue ;
> - μ = 0,21 % / 0,52 % par semaine, σ = 0,87 % / 1,75 % ;
> - P(rester) = 0,946 / 0,950 ;
> - 86 % du temps au-dessus de la moyenne mobile 200 séances, avec 3 croisements.
>
> Résultats **confirmés**. Mais la conclusion (i) ne vaut que pour un marché haussier. Sur **2017-2020**, désormais disponible sans trou, le Composite a passé seulement **6 % du temps au-dessus de sa moyenne mobile 200 séances**, avec **13 croisements**, et a subi un drawdown de **−57,9 %**. Les paramètres de régime doivent être ré-estimés sur 2017-2026 (2021 étant exclu ou traité à part) avant tout usage, même pour le dosage du risque. Source : BOC locaux, confiance high (calcul).

### 14.4 Paramètres BRVM

| Paramètre | Valeur |
|---|---|
| Modèle | 2 régimes, moyenne et variance changeantes, sur les rendements **hebdomadaires** du Composite (puis du Composite Total Return quand l'historique sera suffisant) |
| Estimation | fenêtre expansive, ré-estimée **mensuellement**, `search_reps=20` ; probabilités **filtrées** uniquement |
| Usage autorisé | **dosage du risque** : cible de volatilité ex ante, réduction de 25 % de l'exposition si P(agité) > 0,8 **et** drawdown du Composite > 8 % (choix interne). Ce dosage reste un essai compté dans le registre |
| Usage interdit (pour l'instant) | signal d'alpha ou de *market timing*, tant qu'il n'y a pas **au moins 10 changements de régime indépendants** hors échantillon (règle interne). Il faudra les BOC 1998-2021 ; 2017-2020 est déjà disponible, avec 13 croisements de la moyenne mobile 200 séances (vérificateur) |
| Filtre de tendance | moyenne mobile de 200 séances avec bande de ±2 %, en **challenger** d'overlay seulement, évalué sur 1998-2021 |

---

## 15. Combinaison bayésienne des signaux et rétrécissement (James-Stein)

### 15.1 Références

- James, W. & Stein, C. (1961). « Estimation with quadratic loss ». *Proceedings of the 4th Berkeley Symposium* 1, 361-379 [B].
- Jorion, P. (1986). « Bayes-Stein Estimation for Portfolio Analysis ». *Journal of Financial and Quantitative Analysis* 21(3) [B] : rétrécissement des moyennes vers le rendement du portefeuille de variance minimale.
- Vasicek, O. (1973). « A note on using cross-sectional information in Bayesian estimation of security betas ». *Journal of Finance* 28(5) [B].
- DeMiguel, Garlappi & Uppal (2009), *RFS* 22(5), 1915-1953 : l'estimation d'une allocation optimale exige environ 3 000 mois pour 25 actifs, d'où la force de 1/N. https://ideas.repec.org/a/oup/rfinst/v22y2009i5p1915-1953.html (repris de la revue 03, medium).

### 15.2 Formules

James-Stein (avec rétrécissement « partie positive ») vers la moyenne commune μ̄, pour N ≥ 4 moyennes estimées de variance d'échantillonnage σ̄²/T :

```
μ̂_i^JS = μ̄ + c·(μ̂_i − μ̄) ,   c = max(0, 1 − (N − 3)·(σ̄²/T) / Σ_i (μ̂_i − μ̄)²)
```

Forme normale-normale (base de toute la section) [D] : pour une mesure x d'erreur-type s et un a priori N(m, τ²),

```
E[θ | x] = (x/s² + m/τ²) / (1/s² + 1/τ²) = m + k·(x − m),   k = τ²/(τ² + s²)
```

### 15.3 Mesure sur nos BOC [C] : rendements moyens par titre

43 titres, 59 mois (2022-2026). L'écart-type transversal des rendements moyens annualisés vaut 14,6 %, et l'erreur-type moyenne de chaque moyenne **19,7 %**. D'où **c = 0** : rétrécissement de 100 %. La corrélation des rendements moyens entre la 1ʳᵉ et la 2ᵉ moitié de l'échantillon vaut −0,09 (Pearson) et −0,12 (Spearman). **La dispersion des performances passées par titre est entièrement compatible avec du bruit.**

Conséquence : **interdiction** d'utiliser les rendements historiques moyens comme rendements espérés (dans Markowitz, Kelly ou BL). Seuls des **signaux** dont l'IC a été mesuré hors échantillon peuvent écarter les rendements espérés de l'équilibre.

### 15.4 Application aux IC et aux poids des signaux (choix internes, chiffrés)

- **IC rétréci** de chaque signal : IC_post = k·IC_mesuré + (1 − k)·IC_prior, avec k = n/(n + n₀). Ici n = nombre de mois mesurés hors échantillon et **n₀ = 36 mois** : c'est le nombre de mois nécessaires pour qu'un IC de 0,05 atteigne t = 2 avec 45 titres (section 16.3).
- **IC_prior** : 0,02 pour un facteur documenté en marchés frontières (revue 03), **0** pour un signal nouveau. Aucune étude ne donne d'IC propre à la BRVM (revue 03, conclusion 12).
- **Poids de combinaison** : w ∝ Σ_IC⁻¹·IC_post (combinaison maximisant l'IR composite), puis rétrécissement vers des **poids égaux** avec une intensité de **0,5** (DeMiguel et al. 2009 ; revue 03). Paramètre `shrunk_ic_weights(ic_history, prior, shrinkage=0.5)`.
- **Bêtas** : β_post = k·β_Dimson + (1 − k)·β̄, avec k = τ²/(τ² + se²), où τ² est la variance transversale des bêtas et se l'erreur-type individuelle (Vasicek).

---

## 16. Coefficient d'information et loi fondamentale (Grinold-Kahn)

### 16.1 Références

- Grinold, R. C. (1989). « The Fundamental Law of Active Management ». *Journal of Portfolio Management* 15(3) [S pour l'attribution et la forme IR = IC·√BR, via des sources secondaires : https://www.cfainstitute.org/-/media/documents/support/programs/cfa/technical-append-to-analysis-of-active-portfolio-mgmt.pdf].
- Clarke, R., de Silva, H. & Thorley, S. (2002). « Portfolio Constraints and the Fundamental Law of Active Management ». *Financial Analysts Journal* 58(5), 48-66. https://ideas.repec.org/a/taf/ufajxx/v58y2002i5p48-66.html [S] : **IR = TC·IC·√BR**. Le coefficient de transfert TC vaut 1 sans contrainte et reste < 1 avec des contraintes (pas de vente à découvert, plafonds). Confiance : **high** (résumé).
- Grinold, R. C. (1994). « Alpha is Volatility Times IC Times Score ». *Journal of Portfolio Management* 20(4) [B] ; Grinold & Kahn (2000), *Active Portfolio Management*, 2ᵉ éd., McGraw-Hill [B].

### 16.2 Formules

```
IC_t = corr_Spearman( score_{i,t} , r_{i,t→t+h} )      (transversal, par date)
Erreur-type sous H₀ : se(IC_t) ≈ 1/√(N − 1) ≈ 1/√N
IR ≈ TC · IC · √BR       BR = nombre de paris indépendants par an
α_i = IC · ω_i · z_i     (ω_i = volatilité résiduelle sur l'horizon, z_i = score standardisé)
TC = corr(Δw_i·σ_i , α_i/σ_i)
```

### 16.3 Chiffrage BRVM [C/D]

**Nombre de mois pour établir un IC moyen** (mois supposés indépendants, se = 1/√N) :

| IC moyen | N = 30 : t = 2 / t = 3 | N = 45 : t = 2 / t = 3 |
|---|---|---|
| 0,03 | 149 / 334 mois | 99 / 223 mois |
| 0,05 | 54 / 120 mois | **36 / 80 mois** |
| 0,08 | 21 / 47 mois | 14 / 32 mois |

**Coefficient de transfert simulé** (45 titres, z ~ N(0,1), volatilités résiduelles égales, référence équipondérée) : top-10 équipondéré : **0,71** ; top-15 : **0,77** ; top-22 : 0,80 ; top-10 sur 30 titres : 0,77 ; poids proportionnels au score tronqués à 0 (faible tracking error) : 0,98. Avec une référence pondérée par la capitalisation et des plafonds de liquidité, le TC réel sera **plus bas**, à mesurer dans le backtest.

**Largeur effective** : le ratio de participation des corrélations hebdomadaires est d'environ 23 « titres indépendants » sur 44 (section 8.3).

| Rééquilibrage | BR ≈ 23 × fréquence | IR attendu avec IC = 0,05 et TC = 0,75 |
|---|---|---|
| Trimestriel | 92 | **0,36** |
| Mensuel | 276 | 0,62 (surestimé : les signaux lents comme la value ne se renouvellent pas chaque mois, donc les paris ne sont pas indépendants) |

**Alpha de Grinold** : avec IC = 0,05, ω = 9,2 %/mois (volatilité résiduelle médiane) et z = +1, on obtient α ≈ **0,46 %/mois brut** (≈ 5,5 %/an) pour un titre à +1 écart-type. Avant coûts (≈ 1,7 à 2,8 % par aller-retour hors spread et impact, selon la revue 01) et avant toute incertitude sur l'IC.

**Ordre de grandeur réaliste** : IR net de 0,2 à 0,5. Cela rejoint l'estimation *a priori* de +2 à +4 %/an au-dessus de l'indice de la revue 03. Un IR > 1 annoncé sur la BRVM doit être traité comme un **signal d'erreur** (biais d'anticipation, prix périmés, coûts oubliés ou surapprentissage) tant qu'il n'a pas franchi la section 17.

### 16.4 Paramètres BRVM

| Paramètre | Valeur |
|---|---|
| `information_coefficient(method="spearman")` | horizon h = 21 séances (mensuel) et 63 (trimestriel) ; exécution décalée en t+1 |
| Univers de calcul | titres éligibles à la date (filtre de liquidité) ; **minimum 15 titres** par date, sinon IC non calculé |
| Statistique rapportée | IC moyen, écart-type, **t de Newey-West** (`newey_west_tstat`, retards = h/5 + 1 pour des IC chevauchants, choix interne), proportion de mois positifs, IC par sous-période |
| `grinold_alpha(..., ic=IC_post)` | IC **rétréci** (section 15.4), plafonné à 0,08 (choix interne) |
| Promotion | ≥ 36 mois hors échantillon et t_NW ≥ 2 (facteur documenté) ou ≥ 3 (nouveau) |

---

## 17. Implications pour la plate-forme

### 17.1 Filtre de promotion d'un signal ou d'une stratégie (à coder dans `backtest/walkforward.py` et `quant/stats.py`)

Toutes les conditions sont évaluées **hors échantillon (walk-forward), nettes de coûts, contre le BRVM Composite Total Return** (et contre le panier équipondéré) :

| # | Test | Seuil | Fonction |
|---|---|---|---|
| G1 | Registre d'essais complet (chaque variante journalisée avec ses rendements) | obligatoire | à créer : `TrialRegistry` |
| G2 | PSR(SR* = 0) sur rendements actifs hebdomadaires | ≥ 0,95 | `probabilistic_sharpe` |
| G3 | DSR avec N = nombre d'essais du registre | ≥ 0,95 | `deflated_sharpe` |
| G4 | PBO par CSCV sur toutes les variantes de la famille | ≤ **0,25** (choix interne) et pente de dégradation > −0,5 | `pbo_cscv` |
| G5 | Haircut BHY (M = registre) | HSR > 0,3 | `haircut_sharpe(method="bhy")` |
| G6 | IC du bootstrap stationnaire (b = 20 séances) du ratio d'information | borne basse à 95 % > 0 | `stationary_bootstrap` |
| G7 | IC moyen : t_NW ≥ 3 (nouveau) ou ≥ 2 (documenté et prédéclaré), sur ≥ 36 mois | oui | `ic_summary`, `newey_west_tstat` |
| G8 | Stabilité : même signe de l'alpha sur chaque moitié de l'échantillon et sur 2013-2021 quand l'historique sera disponible | oui | — |
| G9 | Sharpe corrigé de Lo ≥ 0,6 × Sharpe naïf ; sinon, enquêter sur les prix périmés | oui | `lo_adjusted_sharpe(q=10)` |

État actuel : la meilleure stratégie momentum (section 3.4) **échoue** à G3 (0,50) et à G4 (0,37). Le composite value + momentum de la revue 03 échoue à G3 (0,65).

### 17.2 Paramètres prêts à coder

```yaml
# brvm_alpha — rigueur quantitative v1 (revue 04, 2026-11-22)
data:
  clean_start: "2022-01-03"            # 2021 : trous de BOC (jusqu'à 50 jours)
  holdout_months: 6                    # réserve finale, consultée une fois
  validation_history: ["2017-01-02", "2020-12-31"]   # [CORRIGÉ vérif. 2026-11-22] 2017-2020 disponible sans trou ; 2021 exclu (trous) ; 2013-2016 à ajouter une fois téléchargé
  sessions_per_year_observed: 248      # [AJOUT vérif.] BOC N° 247 (2023), 249 (2024), 249 (2025)

returns_and_sharpe:
  periods_per_year: 252                # convention ; réel ≈ 248 → surestimation ≈ 0,8 % des vol/Sharpe annualisés (à documenter dans les rapports)
  report: [naive, lo, glm]             # toujours les trois
  lo_q: {daily: 10, weekly: 4, monthly: 2}   # = retard MAXIMAL des ρ_k (troncature, paramètre `q` du code), η calculé à T = periods_per_year ; jamais troncature à 251
  eval_frequency: "W-FRI"              # métriques de performance en hebdomadaire
  sr_star_alpha: 0.0
  sr_star_worth_it_annual: 0.3

overfitting:
  trial_registry: true                 # chaque variante journalisée (rendements + paramètres)
  n_trials_for_dsr: "registry_count"   # N brut ; N effectif en sensibilité seulement
  dsr_min: 0.95
  psr_min: 0.95
  pbo: {n_splits_daily: 16, n_splits_weekly: 10, metric: "sharpe_lo", max_pbo: 0.25, min_degradation_slope: -0.5}
  haircut: {method: "bhy", min_hsr_annual: 0.3}
  new_factor_min_t: 3.0
  documented_factor_min_t: 2.0

validation:
  scheme: "walk_forward_expanding"
  train_min_sessions: 504
  test_sessions: 63
  step_sessions: 63
  purge_sessions: "label_horizon"      # 21 (mensuel) / 63 (trimestriel)
  embargo_sessions: 21                 # mesuré : mémoire ≈ 10 séances / 3-4 semaines
  cpcv: {n_groups: 10, k_test: 2}      # 45 découpages, 9 chemins (formule k/N·C(N,k) confirmée : skfolio 1.14.4)
  # [AJOUT vérif. 2026-11-22] correspondance avec l'API réelle (calendaire, un seul écart avant le test) :
  walk_forward_windows_args: {train_years: 2, test_months: 3, embargo_days: "label_horizon + 21", expanding: true, min_train_days: 480}

bootstrap:
  method: "stationary"
  mean_block_daily: 20
  mean_block_weekly: 8
  block_floor_daily: 10
  n_boot: 5000                         # à passer explicitement : défaut du code stationary_bootstrap = 2000
  sharpe_difference_test: "ledoit_wolf_2008_studentized"

covariance:
  frequency: "W-FRI"
  lookback_weeks: 104
  min_weeks: 52
  estimator: "ledoit_wolf"
  target: "constant_correlation"       # challenger : single_index (bêta de Dimson)
  shrinkage_floor: 0.5
  expected_shrinkage: [0.7, 0.9]       # mesuré : 0,68 (j), 0,79 (h), 0,86 (m)
  never: "daily_vol_times_sqrt252_for_portfolios"

beta:
  method: "dimson"
  leads: 1
  lags: 5                              # à ajouter : dimson_betas asymétrique
  window_sessions: 504
  shrink_to_cross_section: true        # Vasicek, k = tau² / (tau² + se²)

hrp:
  cov: "covariance (ci-dessus)"
  linkage_method: "single"             # challenger "ward" -> registre
  distance_of_distances: true          # à passer explicitement (défaut du code : False) ; fidélité à l'article [NON VÉRIFIÉ]
  role: "pondération intra-sélection + portefeuille de référence risque"

black_litterman:
  tau: 0.05                            # [NON VÉRIFIÉ en source primaire] ; peu influent ICI car Ω ≪ τΣ → μ_BL ≈ Q (voir §10.3, note du vérificateur)
  views: "grinold_alpha"               # P = I, Q = Pi + IC_post * omega * z
  omega: "(omega_i * sigma_IC)^2"
  market_weights: "float_cap_eligible_capped_15pct"
  delta: "A CALIBRER"                  # prime de marché BRVM non sourcée

kelly:
  fraction: 0.25
  fraction_max: 0.5
  max_gross: 1.0                       # pas de levier
  mu_input: "alpha_shrunk_or_mu_BL"    # jamais une moyenne historique (James-Stein c = 0)

cvar:
  alpha: 0.95
  horizon_sessions: 5
  scenarios: 5000                      # bootstrap stationnaire de semaines, b = 8
  stress: [{composite_drop: -0.15, weeks: 8},          # pire 8 semaines observée : −14,3 % (2017-2020)
           {composite_drop: -0.50, weeks: 190}]        # [AJOUT vérif.] marché baissier 01/03/2017 → 26/10/2020 : drawdown −57,9 %
  constraint: "cvar_port <= 1.25 * cvar_composite"

regime:
  model: "markov_switching_2states_mean_var"
  data: "composite_weekly"
  refit: "monthly_expanding"
  use: "risk_scaling_only"
  risk_cut: {p_turbulent: 0.8, composite_drawdown: -0.08, exposure_cut: 0.25}
  min_independent_switches_for_alpha: 10
  trend_overlay_challenger: {sma_sessions: 200, band: 0.02}

signals:
  ic_method: "spearman"
  ic_horizons_sessions: [21, 63]
  ic_min_names: 15
  ic_prior: {documented: 0.02, new: 0.0}
  ic_prior_strength_months: 36         # k = n / (n + 36)
  ic_cap: 0.08
  combo_shrinkage_to_equal: 0.5
  expected_ir_net_prior: [0.2, 0.5]    # au-delà de 1 : suspicion d'erreur
```

### 17.3 Travaux de code identifiés

1. `quant/stats.py:dimson_betas` : ajouter `leads` et `lags` séparés (aujourd'hui symétrique −K..K).
2. `quant/stats.py` : ajouter `glm_smoothing(returns) -> dict(theta, xi, sr_adj)` (MA(2) normalisé, statsmodels) et `politis_white_block(x)` (version corrigée de 2009).
3. `backtest/walkforward.py` : ajouter `purged_kfold` / `cpcv(n_groups, k_test, purge, embargo)` et un `TrialRegistry` persistant (`reports/trials.parquet`) qui alimente automatiquement N (DSR), M (haircut) et la matrice de la PBO.
4. `quant/regime.py` : modèle markovien à 2 états, probabilités **filtrées** seulement, fonction `risk_scale(asof)`. **[Vérificateur]** Le module existe déjà : il contient `GaussianHMM` (méthodes `fit` et `filter`) et `hmm_filtered_probabilities`. Il reste à ajouter `risk_scale` et la ré-estimation sur 2017-2026.
5. `pbo_cscv` : passer un critère `metric` appelable « Sharpe corrigé de Lo » (q = 10) au lieu du Sharpe naïf.
6. Rapport (`report/html.py`) : afficher systématiquement Sharpe naïf, Lo et GLM, DSR avec N, PBO, MinTRL restant, et un bandeau **« non promu »** tant que G1-G9 ne sont pas tous verts.

---

## 18. Questions ouvertes

1. **Textes intégraux** : relire dans les PDF originaux (hôtes à autoriser : `www.davidhbailey.com`, `escholarship.org`, `people.duke.edu`, `papers.ssrn.com`) la borne MinBTL exacte, l'approximation du N effectif, les formules exactes de Harvey-Liu (y compris leur traitement de la corrélation entre tests), la règle de choix de bloc de Ledoit-Wolf (2008) et la règle d'embargo de López de Prado.
2. **Thèmes non vérifiés faute de budget de recherche** : HMM appliqués aux marchés africains ou frontières, filtres de tendance sur marchés frontières, James-Stein et Jorion sur marchés émergents, valeurs de τ dans Black-Litterman, valeurs empiriques du TC en long-only (Clarke et al. 2002). À relancer dans un nouveau tour.
3. **Historique** : toutes les mesures portent sur 2022-2026, une période très haussière (+144 %) et post-cotation continue. Il faut les ré-estimer sur 1998-2021 dès que les BOC anciens seront téléchargés (en cours), en particulier les régimes, l'embargo, la longueur de bloc et les bêtas. **[Vérificateur]** 2017-2020 est déjà disponible : c'est un marché baissier (−49 %, drawdown −57,9 %), donc c'est le contre-échantillon le plus utile. À traiter en priorité.
4. **Prime de risque BRVM** pour calibrer δ (Black-Litterman) et la cible de Kelly : source introuvable dans cette revue. Définition à trouver pour l'indicateur « prime de risque du marché » du BOC (0,58 le 20/11/2026).
5. **Coefficient de transfert réel** avec la référence pondérée par la capitalisation, les plafonds de liquidité et les lots : à mesurer dans le moteur de backtest.

---

## 19. Sources

Légende : [S] vérifié par recherche dans cette session (métadonnées, résumé ou extraits ; texte intégral non lu) ; [B] référence classique non vérifiée en session ; [C] calcul interne ; [D] dérivation.

**Données BRVM**
- BOC du 20/11/2026 : https://www.brvm.org/sites/default/files/boc_20261120_2.pdf [lu localement : `data/boc_text/boc_20261120.txt.gz`]
- Panel interne : `brvm_alpha.data.store.build_panel` sur `data/boc_text/` (1 273 BOC, du 25/06/2021 au 20/11/2026) [C]

**Surapprentissage, Sharpe, tests multiples**
- Bailey, Borwein, López de Prado & Zhu (2017), PBO : https://papers.ssrn.com/abstract=2326253 ; https://ideas.repec.org/a/rsk/journ0/2471206.html ; https://www.risk.net/journal-of-computational-finance/2471206/the-probability-of-backtest-overfitting [S]
- Applications de la CSCV (logit, PBO) : https://arxiv.org/pdf/2608.27734 [NON VÉRIFIÉ par le vérificateur : identifiant d'août 2026, non consultable en session] ; https://arxiv.org/pdf/1910.05555 ; https://www.mql5.com/en/articles/24095 ; https://github.com/mrbcuda/pbo [S]
- Bailey & López de Prado (2014), DSR : https://papers.ssrn.com/abstract=2460551 [S]
- López de Prado (2015), présentation Nomura (E[max SR]) : https://www.nomura.com/events/9th-annual-global-quantitative-investment-strategies-conference/resources/upload/10_00_Marcos_Lopez_de_Prado_20150510.pdf [S]
- Bailey & López de Prado (2012), PSR et MinTRL, *Journal of Risk* 15(2) : https://www.researchgate.net/publication/308231636_The_Sharpe_ratio_efficient_frontier [S] ; explications : https://portfoliooptimizer.io/blog/the-probabilistic-sharpe-ratio-bias-adjustment-confidence-intervals-hypothesis-testing-and-minimum-track-record-length/ [S]
- Bailey, Borwein, López de Prado & Zhu (2014), « Pseudo-Mathematics and Financial Charlatanism », *Notices of the AMS* 61(5) [B]
- Harvey, Liu & Zhu (2016) : https://ideas.repec.org/a/oup/rfinst/v29y2016i1p5-68..html ; https://www.nber.org/papers/w20592 ; https://papers.ssrn.com/abstract=2513152 [S]
- Harvey & Liu (2015), « Backtesting » : https://people.duke.edu/~charvey/Research/Published_Papers/P120_Backtesting.PDF ; https://www.cmegroup.com/content/dam/cmegroup/education/files/backtesting.pdf ; https://www.man.com/insights/backtesting [S]
- Holm (1979), *Scandinavian Journal of Statistics* 6(2) ; Benjamini & Yekutieli (2001), *Annals of Statistics* 29(4) ; White (2000), *Econometrica* 68(5) ; Hansen (2005), *JBES* 23(4) ; Romano & Wolf (2005), *Econometrica* 73(4) [B]

**Validation et bootstrap**
- López de Prado (2018), *Advances in Financial Machine Learning*, ch. 7 et 12 : https://pypi.org/project/purgedcv/ ; https://en.wikipedia.org/wiki/Purged_cross-validation ; https://arxiv.org/pdf/2407.17645 [S]
- Politis & Romano (1994) : https://gnosis.library.ucy.ac.cy/handle/7/57533 [S]
- Politis & White (2004) : https://ideas.repec.org/a/taf/emetrv/v23y2004i1p53-70.html [S]
- Patton, Politis & White (2009) : https://public.econ.duke.edu/~ap172/Patton_Politis_White_2009.pdf ; code : https://public.econ.duke.edu/~ap172/ppw.R.txt [S]
- Ledoit & Wolf (2008) : https://econpapers.repec.org/RePEc:eee:empfin:v:15:y:2008:i:5:p:850-859 ; https://uzh.ch/cmsssl/econ/dam/jcr:ffffffff-935a-b0d6-0000-00007214c2bc/jef_2008pdf.pdf [S]

**Covariance, HRP, Black-Litterman, Kelly, CVaR**
- Ledoit & Wolf (2004), « Honey, I Shrunk… » : https://econ-papers.upf.edu/papers/691.pdf ; https://bse.eu/research/working-papers/honey-i-shrunk-sample-covariance-matrix ; https://reasonabledeviations.com/notes/papers/ledoit_wolf_covariance [S]
- Ledoit & Wolf (2003), *JEF* : https://uzh.ch/cmsssl/econ/dam/jcr:ffffffff-935a-b0d6-ffff-ffff9961f70f/jef.pdf [S]
- Comparaison de 9 estimateurs : https://arxiv.org/pdf/1004.4272 [S, non exploité]
- scikit-learn LedoitWolf : https://scikit-learn.org/stable/modules/generated/sklearn.covariance.LedoitWolf.html [B]
- López de Prado (2016), HRP : https://papers.ssrn.com/abstract=2708678 ; https://en.wikipedia.org/wiki/Hierarchical_Risk_Parity ; https://research-api.cbs.dk/ws/portalfiles/portal/76452070/1332322_Master_Thesis_Hierarchical_Risk_Parity.pdf [S]
- Black & Litterman (1992) : https://rpc.cfainstitute.org/research/financial-analysts-journal/1992/faj-v48-n5-28 ; https://en.wikipedia.org/wiki/Black%E2%80%93Litterman_model [S]
- Idzorek : https://www.cis.upenn.edu/~mkearns/finread/idzorek.pdf [S pour l'existence]
- Thorp (2006) : https://www.gwern.net/doc/statistics/decision/2006-thorp.pdf [S]
- MacLean, Thorp & Ziemba (2010) : https://www.stat.berkeley.edu/~aldous/157/Papers/Good_Bad_Kelly.pdf ; https://ideas.repec.org/h/wsi/wschap/9789814293501_0039.html [S]
- Kelly (1956), *Bell System Technical Journal* 35(4) [B]
- Rockafellar & Uryasev (2000) : https://ideas.repec.org/a/rsk/journ4/2161159.html ; https://sites.math.washington.edu/~rtr/papers/rtr179-CVaR1.pdf ; synthèse : https://arxiv.org/pdf/1511.00140 [S]

**Trading peu fréquent**
- Dimson (1979) : https://doi.org/10.1016/0304-405x(79)90013-8 ; https://scilit.com/publications/0c07f33393d102e8c9f4c707acd0323b [S]
- Scholes & Williams (1977) : https://econpapers.repec.org/RePEc:eee:jfinec:v:5:y:1977:i:3:p:309-327 [S]
- Lo & MacKinlay (1990), trading non synchrone : https://dspace.mit.edu/bitstream/1721.1/47826/1/econometricanaly00loan.pdf [S]
- Getmansky, Lo & Makarov (2004) : https://www.nber.org/papers/w9571 ; https://web.mit.edu/Alo/www/Papers/serialhf.html ; https://stat.ethz.ch/pipermail/r-sig-finance/2007q3/001691.html [S]
- Lo (2002) : https://ideas.repec.org/a/taf/ufajxx/v58y2002i4p36-52.html ; https://rpc.cfainstitute.org/research/financial-analysts-journal/2002/the-statistics-of-sharpe-ratios [S]

**Régimes, rétrécissement, gestion active**
- Hamilton (1989), *Econometrica* 57(2) ; Ang & Bekaert (2002), *RFS* 15(4) ; Moskowitz, Ooi & Pedersen (2012), *JFE* 104(2) ; Faber (2007), SSRN 962461 [B]
- James & Stein (1961) ; Jorion (1986), *JFQA* 21(3) ; Vasicek (1973), *JF* 28(5) [B]
- DeMiguel, Garlappi & Uppal (2009) : https://ideas.repec.org/a/oup/rfinst/v22y2009i5p1915-1953.html (revue 03)
- Grinold (1989), loi fondamentale (secondaire) : https://www.cfainstitute.org/-/media/documents/support/programs/cfa/technical-append-to-analysis-of-active-portfolio-mgmt.pdf [S]
- Clarke, de Silva & Thorley (2002) : https://ideas.repec.org/a/taf/ufajxx/v58y2002i5p48-66.html [S] ; (2005) : https://ideas.repec.org/a/taf/ufajxx/v61y2005i5p70-83.html [S]
- Grinold (1994), *JPM* 20(4) ; Grinold & Kahn (2000), *Active Portfolio Management* [B]

**Documents internes liés**
- `docs/research/01-structure-marche.md` (±7,5 %, coûts) ; `02-litterature-brvm.md` (efficience, trading peu fréquent) ; `03-facteurs-marches-frontieres.md` (facteurs, DSR interne 0,65, règles de promotion)

---

## Vérification adversariale (2026-11-22)

**Rôle** : vérificateur sceptique du domaine « quant-rigor ». **Objectif** : réfuter en priorité les paramètres qui seront codés.

**Moyens et limites.** Le budget de recherche web du tour était **épuisé** dès la première requête du vérificateur. Le réseau de la session n'autorise que `www.brvm.org`, `sikafinance.com`, `richbourse.com` et les registres de paquets ; `ideas.repec.org` échoue (DNS), comme les hôtes académiques déjà signalés au §0. Les vérifications reposent donc sur quatre moyens :
1. les **BOC locaux** (source primaire : `data/boc_text`, panel reconstruit de zéro dans un répertoire temporaire, 2 334 BOC) ;
2. un **recalcul indépendant** avec des scripts écrits par le vérificateur, sans réutiliser les fonctions statistiques du projet ;
3. la **lecture du code** du projet ;
4. les **implémentations de référence** téléchargées depuis PyPI et lues sans être exécutées (arch 9.0.0, PyPortfolioOpt 1.6.0, skfolio 1.14.4), plus scikit-learn 1.9.1 (installé).

**Aucune référence bibliographique n'a pu être relue dans sa source primaire.** Les éléments bibliographiques non couverts par une implémentation de référence sont donc marqués « invérifiable en session ».

### Tableau des verdicts

| # | Élément vérifié | Verdict | Valeur correcte / constat | Preuve |
|---|---|---|---|---|
| 1 | Faits BOC du 20/11/2026 : 48 sociétés (12 Prestige + 36 Principal), 46 titres transigés, Composite 492,89, « prime de risque du marché » 0,58 | **confirmé** | identique | BOC local `boc_20261120.txt.gz` (https://www.brvm.org/sites/default/files/boc_20261120_2.pdf) |
| 2 | Composite 202,28 (31/12/2021) → 492,89 : +144 % ; drawdown maximal −13,9 %, creux le 02/12/2022 | **confirmé** | +143,7 % ; −13,9 % le 02/12/2022 | `boc_20211231` (https://www.brvm.org/sites/default/files/boc_20211231_2.pdf) + recalcul |
| 3 | `data.clean_start = 2022-01-03` (trous de BOC en 2021, jusqu'à 50 jours) | **confirmé** | 2021 : 156 BOC, 9 trous de plus de 5 jours, le plus long de 50 jours (06/05 → 25/06/2021) | inventaire de `data/boc_text` |
| 4 | `validation_history = 2013-2021` (« quand disponible ») | **corrigé** | **2017-01-02 → 2020-12-31 déjà disponible sans trou** (238 à 250 BOC par an) ; 2021 exclu ; 2013-2016 pas encore téléchargé | inventaire de `data/boc_text` |
| 5 | `periods_per_year = 252` | **corrigé** (convention gardée, mais documentée) | environ **248 séances par an** (BOC N° 247 au 29/12/2023, N° 249 au 31/12/2024, N° 249 au 31/12/2025) ; surestimation d'environ 0,8 % des vol et Sharpe annualisés | en-têtes des BOC locaux |
| 6 | Autocorrélations et facteur de Lo : ρ₁ EW = 0,231, Q(10) = 155,7, VR(20) = 2,70, η/√252 = 0,582 (EW) et 0,771 (Composite) | **confirmé** | 0,231 ; 155,8 ; 2,70 ; 0,582 ; 0,771 (troncature 10) | recalcul indépendant sur 1 202 séances |
| 7 | `lo_q` (10 / 4 / 2) | **corrigé** (notation) | c'est une **troncature** des ρ_k (paramètre `q` du code), pas le « q » de Lo, qui est l'horizon d'agrégation ; valeurs inchangées | `quant/stats.py:lo_adjusted_sharpe` |
| 8 | `eval_frequency = W-FRI` : volatilité d'un portefeuille sous-estimée de 44 % en journalier | **confirmé** | EW 9,1 % (j) / 11,4 % (h) / 16,5 % (m), rapport 1,80 ; Composite 9,6 / 10,0 / 13,1 % | recalcul |
| 9 | Covariance : effet Epps (0,046 / 0,087 / 0,179), δ* Ledoit-Wolf vers la corrélation constante (0,68 / 0,79 / 0,86), bord de Marchenko-Pastur | **confirmé** | 0,046 / 0,090 / 0,169 ; δ* 0,68 / 0,79 / 0,87 ; 2 / 2 / 1 valeurs propres au-dessus du bord ; sklearn (identité) 0,21 / 0,33 / 0,49 | réimplémentation indépendante ; structure identique à PyPortfolioOpt 1.6.0 |
| 10 | Bêtas médians : MCO 0,50, Dimson (−1..+5) 0,88, Scholes-Williams 0,78, MCO hebdomadaire 0,71 ; 22 % des titres avec t(retard 1) > 2 | **confirmé** (écart mineur sur l'hebdomadaire) | 0,51 / 0,89 / 0,78 / **0,67** ; 23 % ; 47 titres | recalcul |
| 11 | `bootstrap.mean_block` : b_opt de Politis-White corrigé (0,4 / 8,5 / 8,6 / 12,4 / 2,7 / 7,7) et constantes de la règle (D_SB = 2ĝ(0)², noyau flat-top, bande ±2√(log₁₀n/n)) | **confirmé** | valeurs identiques ; constantes identiques à arch 9.0.0 (seule différence : K_n = max(5, log₁₀ n), sans effet) | arch 9.0.0 sur PyPI (https://pypi.org/project/arch/), réimplémentation |
| 12 | Références de Politis & White (2004), *Econometric Reviews* 23(1), 53-70, et de la correction de Patton, Politis & White (2009), 28(4), 372-375 | **confirmé** | DOI 10.1081/ETC-120028836 et 10.1080/07474930802459016 | docstring d'arch 9.0.0 |
| 13 | Formule E[max SR] (γ = 0,5772) et table des multiplicateurs ; Sharpe maximal « par hasard » (0,70 / 1,02 / 1,46 sur 5 ans) | **confirmé** | identique au centième | recalcul ; formule identique dans `skfolio.measures.expected_max_sharpe_ratio` (cite Bailey & López de Prado 2014) |
| 14 | Démonstration DSR : SR₀ = 0,0619, PSR(0) = 0,967, DSR = 0,501 | **confirmé** (à partir des entrées publiées) | 0,0619 ; 0,9675 ; 0,5015 | recalcul ; grille momentum **non** relancée |
| 15 | Formules PSR et MinTRL ((γ₄ − 1)/4, √(T − 1)) ; table MinTRL | **confirmé** (avec précision) | la colonne « contre SR* = 0,5 » est i.i.d. normale ; avec queues épaisses : 11,2 ans (journalier) et 13,6 ans (mensuel) pour SR = 1 | skfolio 1.14.4 (cite B&LdP 2012) + recalcul |
| 16 | Haircut de Bonferroni sur 5 ans (SR 1,0 : −49 % pour N = 10, −100 % pour N = 50 ; SR 1,5 : −39 % pour N = 50) | **confirmé** | identique | recalcul |
| 17 | Kelly : ½-Kelly = 75 % de la croissance pour 25 % de la variance ; P(perdre la moitié) = 50 % / 12,5 % / 0,8 % ; croissance nulle à 2× | **confirmé** | identique | dérivation refaite |
| 18 | P(année négative) = Φ(−SR) (15,9 % pour SR = 1) ; table de puissance des IC (36 / 80 mois) ; IR ≈ 0,36 | **confirmé** | identique | recalcul |
| 19 | CPCV N = 10, k = 2 → 45 découpages et 9 chemins ; φ = (k/N)·C(N, k) | **confirmé** | identique | `skfolio.model_selection.CombinatorialPurgedCV._n_test_paths` |
| 20 | `validation.purge/embargo` et fenêtres en séances (504 / 63 / 21) | **corrigé** (correspondance avec le code) | `walk_forward_windows` est calendaire et n'a qu'un écart avant le test (`embargo_days`), qui joue le rôle de la purge → `train_years = 2`, `test_months = 3`, `embargo_days = h + 21` | lecture de `backtest/walkforward.py` |
| 21 | Stress CVaR « Composite −15 % en 8 semaines, repère : drawdown maximal −13,9 % » | **corrigé** | le repère ne vaut que pour 2022-2026 ; en 2017-2020, drawdown de **−57,9 %** (01/03/2017 → 26/10/2020) et pire baisse sur 8 semaines de −14,3 % → ajout d'un stress de marché baissier prolongé | BOC locaux 2017-2020 + recalcul |
| 22 | Régimes : BIC 894,0 (2 régimes) contre 900,1 (1 régime) ; durées d'environ 18 semaines ; 3 croisements de la moyenne mobile 200 séances ; « l'état agité a le meilleur rendement » | **confirmé** (2022-2026), **portée corrigée** | ΔBIC ≈ 6 (891,5 contre 897,5 sur 254 semaines) ; p = 0,946 / 0,950 ; mais 2017-2020 : 13 croisements, 6 % du temps au-dessus de la moyenne mobile 200 séances | recalcul (statsmodels 0.15.0) |
| 23 | James-Stein c = 0 (43 titres, 59 mois) ; corrélation entre moitiés −0,12 (Spearman) | **confirmé** | c = 0 (dispersion 14,6 % contre erreur-type 18,6 %) ; corrélations −0,12 (Pearson) et −0,16 (Spearman) | recalcul |
| 24 | Lissage GLM MA(2) : θ et ξ | **confirmé** | EW journalier (0,747 ; 0,151 ; 0,102), ξ = 0,59 ; Composite hebdomadaire identique | recalcul (ARIMA(0,0,2) de statsmodels) |
| 25 | Limite de ±7,5 % (3,1 % des lignes à \|var\| ≥ 7,3 %) | **confirmé** (empiriquement) | 3,25 % des lignes échangées ; une seule ligne échangée sur 51 808 au-delà de 7,55 % (SLBC −10,27 % le 18/08/2022, exception non expliquée ici) | BOC locaux 2022-2026 |
| 26 | Black-Litterman : « avec Ω ∝ τ, τ influe peu » ; τ = 0,05 ; Ω de He-Litterman = diag(PτΣPᵀ) | **corrigé** (raisonnement) / τ **invérifiable** | l'Ω retenu (ω·σ_IC)² n'est pas ∝ τ ; τ influe peu seulement parce que Ω ≪ τΣ, d'où μ_BL ≈ Q. τ = 0,05 et Ω de He-Litterman confirmés seulement par une source secondaire (défauts de PyPortfolioOpt 1.6.0) | calcul + PyPortfolioOpt |
| 27 | HRP : d = √(½(1 − ρ)), lien `single`, « d̃ reproduit l'article » | **confirmé** (d, `single`) / **invérifiable** (d̃) | PyPortfolioOpt (code de López de Prado, avec sa permission) n'utilise pas d̃ ; dans le projet, `distance_of_distances=False` par défaut | PyPortfolioOpt 1.6.0, `portfolio/risk.py` |
| 28 | Ledoit & Wolf (2004), *JMVA* 88(2), cible identité = sklearn | **confirmé** (complété) | février 2004, p. 365-411 | docstring de scikit-learn 1.9.1 |
| 29 | Rockafellar & Uryasev (2000), *Journal of Risk* 2(1), 21-42 | **invérifiable** | numéro et pages douteux ; la citation usuelle dont se souvient le vérificateur est 2(3), 21-41, **non contrôlée** → marqué [NON VÉRIFIÉ] au §12.1 | aucune source accessible en session |
| 30 | arXiv 2608.27734 (application de la CSCV) | **invérifiable** | identifiant d'août 2026 non consultable ; marqué [NON VÉRIFIÉ] | — |
| 31 | Références de Bailey-López de Prado (DSR, *JPM* 40(5) ; PBO, *JCF* 20(4) ; PSR, *J. Risk* 15(2)), de Harvey-Liu-Zhu (*RFS* 29(1), t > 3,0) et de Lo (2002, 65 %) | **invérifiable en session** (titres et années de DSR 2014 et PSR 2012 corroborés par skfolio) | les étiquettes [S] du chercheur sont maintenues, mais rien n'a été recontrôlé (budget épuisé, RePEc bloqué) | — |
| 32 | Code : `dimson_betas` symétrique ; `fractional_kelly_scale(fraction=0.25, max_gross=1.0)` ; `UniverseFilter` (50 % de 120 séances, 2 M FCFA) ; `quant/regime.py` « à créer » | **confirmé** sauf le dernier point (**corrigé**) | `quant/regime.py` existe déjà (`GaussianHMM`, `hmm_filtered_probabilities`) ; `stationary_bootstrap` a `n_boot = 2000` par défaut, donc passer 5 000 explicitement | lecture du code |

### Bilan

- **Aucun chiffre interne [C] n'a été réfuté.** Les recalculs indépendants reproduisent les valeurs au centième près, ou avec des écarts de l'ordre de l'arrondi ou d'une semaine de bord (seule exception notable : le bêta MCO hebdomadaire, 0,67 contre 0,71). Aucune étude citée ne s'est révélée inventée. En revanche, la plupart des références n'ont **pas pu** être recontrôlées en source primaire dans ce tour.
- **Corrections qui comptent pour le code** :
  1. second échantillon 2017-2020 disponible : c'est un marché baissier, avec un drawdown de −57,9 % ;
  2. stress de marché baissier prolongé à ajouter ;
  3. correspondance entre `walk_forward_windows` et les paramètres en séances (`embargo_days = h + 21`) ;
  4. `lo_q` est une troncature ;
  5. environ 248 séances par an ;
  6. Black-Litterman n'apporte presque aucun rétrécissement avec l'Ω choisi ;
  7. `distance_of_distances` et `n_boot` à passer explicitement.
- **À relancer** quand les hôtes académiques seront autorisés ou qu'un nouveau budget de recherche sera disponible : notice RePEc de Rockafellar-Uryasev (numéro et pages), texte de HRP (d̃), τ de He-Litterman, existence d'arXiv 2608.27734, résumés de HLZ et de Lo (2002).

**Sources du vérificateur** : BOC locaux (`data/boc_text`, en particulier https://www.brvm.org/sites/default/files/boc_20261120_2.pdf et https://www.brvm.org/sites/default/files/boc_20211231_2.pdf) ; https://pypi.org/project/arch/ (9.0.0, `arch/bootstrap/base.py`) ; https://pypi.org/project/PyPortfolioOpt/ (1.6.0 : `pypfopt/black_litterman.py`, `pypfopt/hierarchical_portfolio.py`, `pypfopt/risk_models.py`) ; https://pypi.org/project/skfolio/ (1.14.4 : `skfolio/measures/_measures.py`, `skfolio/model_selection/_combinatorial.py`) ; https://scikit-learn.org/stable/modules/generated/sklearn.covariance.LedoitWolf.html (docstring de la 1.9.1). Les scripts de recalcul ont été exécutés dans le répertoire temporaire de la session : ils ne sont pas versionnés.
