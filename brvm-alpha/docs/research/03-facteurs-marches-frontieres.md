# 03 — Évidence des facteurs sur marchés émergents, frontières et africains

> **Projet** : BRVM Alpha · **Module** : recherche / facteurs de sélection d'actions
> **Rédigé le** : 2026-11-22 · **Statut** : v1.1, vérifiée (à réviser quand les textes intégraux seront accessibles)
> **Après vérification adversariale (2026-11-22, section 12)** : les faits tirés des BOC (rendement moyen, PER, secteurs, limite de ±7,5 %, ajustement du cours précédent au détachement) et les résultats internes de la section 7 sont **confirmés** par une reproduction indépendante. Quatre points codés sont **corrigés** :
> - le coût aller central passe de 1 % à **1,25 %**, car la revue 02 a corrigé l'aller-retour de base à 2,5 % ;
> - l'indice **BRVM Composite Total Return** n'existe que depuis sa base du 02/01/2025 et n'est publié au BOC que depuis le 02/01/2026. Il faut donc un indice reconstruit pour les backtests et pour le filtre de crash ;
> - les BOC locaux commencent le **02/01/2017**, et non en 2013. Les sous-périodes changent en conséquence ;
> - la surperformance attendue est revue en baisse.
> Les chiffres d'articles que la session n'a pu relire dans aucune source primaire sont marqués **[NON VÉRIFIÉ]**.
> **Portée** : value, rendement du dividende, momentum, faible volatilité, qualité/profitabilité, taille, illiquidité, retournement de court terme. Primes moyennes, t-stats, définitions précises, robustesse après coûts, crash du momentum, interactions value × momentum, méthodes de combinaison. Conclusion : une recommandation chiffrée de facteurs et de pondérations à tester sur la BRVM.
> **Documents liés** : `02-litterature-brvm.md` (littérature propre à la BRVM, règles de marché, coûts).

---

## 0. Avertissement

1. **Aucun facteur ne garantit un gain.** Les primes factorielles sont des **moyennes de long terme** : elles alternent avec des années de sous-performance, parfois longues, et elles diminuent souvent après publication (McLean & Pontiff 2016 : −58 % aux États-Unis). Une plate-forme sérieuse les traite comme des **hypothèses à valider hors échantillon et après coûts**, jamais comme une promesse de rendement. Promettre « 100 % de gains garantis » serait faux.
2. **Limite d'accès.** Pendant cette revue, la session n'a pas pu lire les textes intégraux. La récupération directe (WebFetch ou curl) a été refusée par le réseau de la session pour `repub.eur.nl`, `pages.stern.nyu.edu`, `papers.ssrn.com`, `core.ac.uk`, `nber.org`, `ideas.repec.org`, `quantpedia.com`, `robeco.com` et d'autres hôtes académiques. Les chiffres viennent donc des **résumés et extraits renvoyés par le moteur de recherche**. Quand une source secondaire est la seule origine d'un chiffre, c'est indiqué. Quand un chiffre est introuvable, il est noté **« non trouvé »**. Aucun chiffre n'a été inventé. Pour lire les tableaux originaux, il faudrait autoriser ces hôtes dans les réglages réseau de la session.
3. **Niveaux de confiance** (mêmes conventions que la revue 02) :
   - **high** : fait lu dans une source primaire, ou calcul interne reproductible sur les BOC ;
   - **medium** : résumé d'éditeur, de RePEc ou d'auteur relayé par le moteur de recherche, cohérent entre plusieurs sources ;
   - **low** : source secondaire unique, extrait fragmentaire, version de travail ou sources contradictoires.
4. **Section 7** : c'est une **vérification exploratoire interne** sur 48 mois de BOC (novembre 2022 à novembre 2026). Elle n'a pas valeur de preuve : l'échantillon est court, il couvre un seul régime (marché très haussier) et beaucoup de variantes ont été testées.

---

## 1. Résumé exécutif

| # | Conclusion | Confiance |
|---|---|---|
| 1 | **Value et momentum sont les deux facteurs les mieux établis sur les marchés émergents ET frontières.** Ils sont documentés par Rouwenhorst (1999, 20 pays), van der Hart et al. (2003, 32 pays), Cakici et al. (2013, 18 pays), Hanauer & Lauterbach (2019, 28 pays), de Groot et al. (2012, 24 marchés frontières) et Zaremba & Maydybura (2019, 22 marchés frontières, plus de 4 500 titres). | medium-high |
| 2 | **Ordres de grandeur bruts (top − bottom, marchés frontières)** : B/P 1,40 %/mois, E/P 1,53 %/mois, D/P 0,59 %/mois, momentum 6 mois 1,69 %/mois (de Groot et al., version de travail) **[NON VÉRIFIÉ]**. **Nets d'un coût de 2,5 % par transaction** : environ 6,6-7,7 %/an pour la value et 4,6-7,2 %/an pour le momentum (version publiée, d'après des résumés) **[NON VÉRIFIÉ]**. L'étude elle-même existe bien (24 marchés frontières, 1997-2008, effets value, momentum et taille locale). Ce sont ses chiffres qui n'ont pu être relus dans aucune source primaire. | low-medium (secondaire) |
| 3 | **La taille n'est pas un facteur fiable.** Il n'y a pas de prime de taille dans les régions développées sur 20 ans (Fama-French 2012), pas de prime cohérente dans les marchés frontières (Zaremba & Maydybura 2019) et pas d'effet taille sur le JSE (Muller & Ward 2013). L'Égypte, la Namibie et la Zambie font exception. La prime réapparaît seulement si l'on contrôle la qualité (« junk ») (Asness et al. 2018). | medium |
| 4 | **Faible volatilité** : la relation risque-rendement est plate ou négative dans les émergents (Blitz, Pang & van Vliet 2013 ; Hanauer & Lauterbach 2019). Sur **9 marchés frontières africains, 2004-2023**, la prime de faible volatilité est significative **sauf en marché haussier** (Steyn, Gilbert & Viviers 2024 **[NON VÉRIFIÉ]**). C'est un facteur **défensif**. | medium (Steyn et al. : low) |
| 5 | **Qualité/profitabilité** : la profitabilité brute et le CF/P sont robustes dans les émergents (Hanauer & Lauterbach 2019). Dans les marchés frontières, il n'y a **pas d'évidence cohérente** pour la profitabilité ni pour l'investissement (Zaremba & Maydybura 2019), mais FF5 et FF6 expliquent le mieux l'Afrique frontière (Hearn et al. 2025 **[NON VÉRIFIÉ]**). | medium |
| 6 | **Illiquidité** : la prime d'illiquidité est positive et significative en moyenne sur 45 pays (Amihud et al. 2015). Des effets de liquidité existent sur **tous les marchés subsahariens étudiés** (Hearn 2012). Mais c'est une prime **difficile à récolter** : les coûts y sont les plus élevés. | medium |
| 7 | **Retournement à 1 mois** : il est faible ou **inversé** (continuation) dans les marchés frontières et peu développés, d'après des travaux de Zaremba cités dans un chapitre d'ouvrage. Sa rotation est énorme et son coût (1,94 %/mois aux États-Unis selon Medhat & Schmeling 2022 **[NON VÉRIFIÉ]**) absorbe la prime brute. **À exclure du moteur alpha.** | low-medium |
| 8 | **Value et momentum sont corrélés négativement** : −0,49 en moyenne par classe d'actifs (−0,60 dans une autre version de l'article), selon Asness, Moskowitz & Pedersen (2013). Ces valeurs exactes sont **[NON VÉRIFIÉ]** ; le signe négatif, lui, est établi. Le mélange 50/50 bat chaque facteur pris seul sur tous les marchés étudiés. Sur nos BOC 2023-2026, la corrélation entre les rendements des spreads E/P et momentum est de **−0,57 à −0,58**. | medium-high (AMP) / high (calcul interne) |
| 9 | **Coûts** : l'écart effectif moyen est de 2,6 % (pondéré également) et de 1,9 % (pondéré par la capitalisation) sur 19 marchés frontières, contre 0,72 % aux États-Unis **[NON VÉRIFIÉ]**. Un rééquilibrage **mensuel** détruit les gains de diversification, un rééquilibrage **trimestriel ou plus long** les préserve (Marshall et al. 2015). Les anomalies dont la rotation est **inférieure à 50 % par mois** survivent aux coûts si on les construit intelligemment, avec une bande achat/conservation (Novy-Marx & Velikov 2016). | medium |
| 10 | **Crash du momentum** : il survient en « état de panique », quand le marché rebondit après une chute et que la volatilité est élevée. Le levier du momentum dosé selon sa propre volatilité fait passer le Sharpe de **0,53 à 0,97** (Barroso & Santa-Clara 2015, avec une volatilité cible de 12 %/an). La version dynamique de Daniel & Moskowitz (2016) double environ le Sharpe. En portefeuille **acheteur seul** (le cas BRVM), le risque de crash est réduit, car il vient surtout de la jambe vendeuse (les perdants qui rebondissent). | medium |
| 11 | **Combinaison** : il faut des poids **simples et égaux**, l'estimation d'une allocation optimale exigeant environ 3 000 mois pour 25 actifs (DeMiguel et al. 2009). Il vaut mieux combiner les signaux avant de construire le portefeuille, car les transactions se compensent (DeMiguel et al. 2020). La différence entre approche « intégrée » et « mélangée » n'est **pas statistiquement robuste** (Leippold & Rüegg 2018). | medium |
| 12 | **Aucune étude publiée sur les primes factorielles transversales propres à la BRVM n'a été trouvée** (recherches en français et en anglais, 2026-11-22). Notre vérification interne (section 7) montre : un momentum **3-6 mois** positif ; un momentum 12-1 nul ; une **continuation à 1 mois** (pas de retournement) ; des facteurs value, faible volatilité et illiquidité **instables selon la sous-période** ; et un composite **value + momentum 6-1** à **+1,09 %/mois brut** contre le panier équipondéré (t = 2,20), qui **ne survit pas** au Sharpe dégonflé (DSR = 0,65 < 0,95). | high (calcul) / low (portée) |

**Recommandation (détails en section 8)** : tester sur la BRVM un **composite acheteur seul** pondéré à **35 % value** (E/P 15 % + D/P 20 %), **35 % momentum 6-1**, **20 % faible volatilité** et **10 % qualité** (proxy dividendes en attendant les comptes annuels).

- Sélection : le tiers supérieur, environ 15 titres, en équipondéré.
- Exécution : signal **mensuel**, avec une **bande** (on entre dans le top 30 %, on sort sous le top 50 %).
- Risque : le poids du momentum baisse quand sa volatilité explose.
- Référence : le **BRVM Composite Total Return**. Il n'est officiel que depuis sa base du 02/01/2025 ; avant cette date, il faut un **indice reconstruit** (voir 8.3).
- Deux challengers pré-enregistrés : value 50 / momentum 6-1 50, et une variante avec un momentum 12-1.

La surperformance nette attendue *a priori* est **modeste** : environ **0 à +4 %/an, avec un centre vers +2 %**, au-dessus de l'indice, et une forte incertitude. Cette fourchette a été corrigée le 2026-11-22 (la v1 donnait +2 à +4 %), après le relèvement du coût aller à 1,25 %. Sur 2023-2026, le composite principal ne fait que **+0,11 %/mois net** à 1,25 % aller contre le panier équipondéré (non significatif).

---

## 2. Définitions précises des facteurs (fenêtres, sauts de mois, données BRVM)

### 2.1 Définitions standards dans la littérature

| Facteur | Définition standard | Fenêtre / saut | Rééquilibrage | Référence | Confiance |
|---|---|---|---|---|---|
| Momentum (Jegadeesh-Titman) | Rendement cumulé sur J mois ; on achète les gagnants et on vend les perdants ; détention K mois | J, K ∈ {3, 6, 9, 12} ; **saut d'une semaine** entre la formation et la détention | portefeuilles qui se chevauchent | Jegadeesh & Titman 1993, *JF* 48(1), 65-91 ; https://ideas.repec.org/a/bla/jfinan/v48y1993i1p65-91.html | medium |
| Momentum « 12-1 » (Carhart, Fama-French, AMP) | Rendement de t−12 à t−1, **en sautant le dernier mois** | 11 mois de formation, **saut d'un mois** | mensuel | AMP 2013 (même famille de mesures) ; Fama-French 2012 | medium |
| Momentum 6 mois (marchés frontières) | Rendement des 6 derniers mois, portefeuille top − bottom | 6 mois (saut non vérifié) | mensuel | de Groot et al. 2012 (version de travail) ; https://www.cxoadvisory.com/value-premium/extending-value-and-momentum-to-frontier-market-stocks/ | low-medium |
| Momentum intermédiaire « 12-7 » | Rendement de t−12 à t−7 | saut de 6 mois | mensuel | Novy-Marx (2012), contesté : **pas d'« écho » hors des États-Unis** (37 pays, Goyal & Wahal 2015) ; https://ideas.repec.org/a/cup/jfinqa/v50y2015i06p1237-1267_00.html | medium |
| Momentum résiduel (idiosyncratique) | Momentum calculé sur les résidus d'une régression factorielle | 12-1 sur les résidus | mensuel | Blitz, Huij & Martens 2011, *JEF* : Sharpe environ **2 fois** celui du momentum total ; Blitz, Hanauer & Vidojevic 2020, *IREF* 69 : robuste dans les développés et les émergents ; https://econpapers.repec.org/RePEc:eee:reveco:v:69:y:2020:i:c:p:932-957 | medium |
| Retournement de court terme | Rendement du dernier mois (on achète les perdants) | 1 mois | mensuel ou plus fréquent | de Groot, Huij & Zhou 2012, *JBF* 36(2) ; Medhat & Schmeling 2022, *RFS* 35(3) | medium |
| Value | B/P (fonds propres / capitalisation), E/P, D/P, CF/P | données comptables décalées pour éviter le biais d'anticipation | mensuel à annuel | de Groot et al. 2012 ; van der Hart et al. 2003 ; Hou, Karolyi & Kho 2011 (CF/P) ; Hanauer & Lauterbach 2019 (CF/P) | medium |
| Rendement du dividende | D/P : dernier dividende annuel / cours | glissant | mensuel | de Groot et al. 2012 (D/P) ; Muller & Ward 2013 (JSE) | medium |
| Faible volatilité | Écart-type des rendements passés ; on achète le quintile ou décile le moins volatil | **3 ans** (Blitz & van Vliet 2007) ; volatilité historique (Steyn et al. 2024) | mensuel | Blitz & van Vliet 2007, *JPM* ; https://papers.ssrn.com/abstract=980865 | medium |
| Bêta faible (BAB) | Long bêta faible à levier, short bêta élevé | estimation du bêta : volatilités sur 1 an de rendements quotidiens, corrélation sur 5 ans de rendements à 3 jours chevauchants, bêta rétréci vers 1 avec un poids de 0,6 (selon le texte publié, connu du vérificateur ; non relu en ligne le 2026-11-22) | mensuel | Frazzini & Pedersen 2014, *JFE* 111(1) | medium |
| Profitabilité / qualité | Marge brute / actifs (GP/A) ; QMJ = profitabilité + croissance + sécurité + distribution | comptes annuels | annuel | Novy-Marx 2013, *JFE* ; Asness, Frazzini & Pedersen 2019, *RAS* 24(1) | medium |
| Taille | Capitalisation boursière (petites − grandes) | — | annuel | Fama-French 2012 ; Asness et al. 2018 | medium |
| Illiquidité | Amihud : moyenne de \|r\| / montant échangé ; rotation ; part des rendements nuls | 1 à 12 mois | mensuel | Amihud et al. 2015, *JFE* 117(2) ; Hearn 2012 ; Marshall et al. 2015 | medium |

### 2.2 Données disponibles dans les BOC de la BRVM

Le parseur `brvm_alpha/data/boc_parser.py` extrait, pour chaque titre et chaque séance, les champs suivants : cours de clôture, cours de référence, variation, volume, valeur échangée, dernier dividende net et sa date, rendement net et PER, plus le marqueur de détachement « (D) ».

| Facteur | Calculable avec les BOC seuls ? | Variable BOC | Remarque |
|---|---|---|---|
| Momentum (toutes fenêtres) | **Oui** | rendements quotidiens reconstruits | Ajuster les détachements (voir 7.1) |
| E/P | **Oui** | `per` → E/P = 1/PER si PER > 0 | Au 20/11/2026, sur 48 titres, 4 ont un PER manquant ou ≤ 0 et 6 un PER > 50 : Unilever CI 631, Bernabé CI 519, Bank of Africa NG 225, Africa Global Logistics 186, Erium CI (ex-Air Liquide CI) 78, SAFCA CI 51. Il faut des rangs, pas des niveaux. |
| D/P | **Oui** | `net_yield_pct` (dividende net / cours) | Le « taux de rendement moyen du marché » publié (7,12 %) est la **moyenne simple** des 43 titres qui ont un rendement (vérifié, high). La médiane n'est que de **4,67 %** : la moyenne est tirée par quelques valeurs extrêmes. |
| Faible volatilité, bêta | **Oui** | rendements quotidiens | Bêta : corriger le trading non synchrone (bêta de Dimson ; `quant/stats.py:dimson_beta` existe) |
| Illiquidité (Amihud, rotation) | **Oui pour Amihud**, rotation **non** | `value`, `volume` | La rotation exige le nombre d'actions en circulation |
| Taille | **Non** | — | Capitalisation par titre absente des BOC ; nombre d'actions à collecter (brvm.org, rapports annuels) |
| B/P, profitabilité, qualité | **Non** | — | Comptes annuels et semestriels à collecter (publications des émetteurs sur brvm.org) |
| Révisions de bénéfices (van der Hart et al.) | **Non** | — | Couverture par les analystes quasi nulle |

---

## 3. Évidence empirique par région

### 3.1 Marchés émergents

| Étude | Échantillon | Résultats chiffrés disponibles | Lien | Confiance |
|---|---|---|---|---|
| Rouwenhorst (1999), *JF* 54(4), 1439-1464 | 20 pays émergents, plus de 1 700 titres, environ 1982-1997 | Momentum, petite taille et value présents ; **pas de prime pour le bêta élevé**. Momentum gagnants − perdants **≈ 0,39 %/mois (t = 2,35)** **[NON VÉRIFIÉ]** en moyenne équipondérée sur les 20 marchés ; gagnants > perdants dans **17 pays sur 20**, et l'écart dépasse deux écarts-types dans 6. Un autre chiffre (0,58 %/mois, t = 3,78) correspond à une autre pondération non identifiée. Les facteurs sont corrélés à la rotation | https://ideas.repec.org/a/bla/jfinan/v54y1999i4p1439-1464.html ; http://depot.som.yale.edu/icf/papers/fileuploads/2501/original/98-95.pdf | medium (chiffres issus d'extraits) |
| van der Hart, Slagter & van Dijk (2003), *JEF* 10, 105-132 | 32 pays, 1985-1999 | **Value, momentum et révisions de bénéfices** gagnants ; **taille, liquidité et retour à la moyenne non**. E/P : haut − bas = **1,02 %/mois (t = 5,46)** ; portefeuille E/P contre indice équipondéré : **0,53 %/mois (t = 4,45)** **[NON VÉRIFIÉ]**. Le multicritère améliore la performance. Les stratégies restent applicables par un grand investisseur malgré les coûts | https://papers.tinbergen.nl/01009.pdf ; https://www.sciencedirect.com/science/article/abs/pii/S0927539802000221 | medium |
| Cakici, Fabozzi & Tan (2013), *EMR* 16, 46-65 | 18 pays, 1990-2011 | Value présente **dans tous les émergents** ; momentum dans tous **sauf l'Europe de l'Est** ; les facteurs locaux font mieux que les globaux (segmentation) | https://econpapers.repec.org/RePEc:eee:ememar:v:16:y:2013:i:c:p:46-65 | medium |
| Hanauer & Lauterbach (2019), *EMR* 38, 265-286 | 28 pays, juillet 1995 à juin 2016, sans financières ni micro-capitalisations | Anomalies robustes en pondération égale et en pondération par la capitalisation : **CF/P, profitabilité brute, émission nette d'actions, momentum**. **Pas de relation positive risque-rendement**. Les définitions FF5 sont moins robustes que des définitions alternatives | https://ideas.repec.org/a/eee/ememar/v38y2019icp265-286.html ; https://alphaarchitect.com/the-cross-section-of-emerging-market-stock-returns/ | medium |
| Blitz, Pang & van Vliet (2013), *EMR* 16, 31-45 | Émergents, environ 1989-2010 | Relation risque-rendement **plate ou négative** ; effet **croissant dans le temps** ; faiblement lié à l'effet des marchés développés. Version de travail : long/short faible − forte volatilité ≈ **+8,8 %/an** contre l'indice, **brut**, surtout grâce à la jambe vendeuse | https://ideas.repec.org/a/eee/ememar/v16y2013icp31-45.html ; https://www.cxoadvisory.com/volatility-effects/reward-for-risk-in-emerging-equity-markets/ | medium (8,8 % : low) |
| Hou, Karolyi & Kho (2011), *RFS* 24(8), 2527-2574 | Plus de 27 000 titres, 49 pays | Un modèle **momentum + CF/P** explique mieux les rendements mondiaux que le CAPM et que taille + B/M | https://ideas.repec.org/a/oup/rfinst/v24y2011i8p2527-2574.html | medium |
| Chui, Titman & Wei (2010), *JF* 65(1), 361-392 | 41 pays, 1980-2003 | Profits du momentum liés à **l'individualisme** (Hofstede), à la dispersion des analystes, aux coûts de transaction ; **négativement liés à la taille** | https://ideas.repec.org/a/bla/jfinan/v65y2010i1p361-392.html | medium |
| Griffin, Ji & Martin (2003), *JF* 58(6), 2515-2547 | International | Momentum positif en bonne comme en mauvaise conjoncture : **pas une prime de risque macroéconomique** ; retournement à 1-5 ans. Détail régional émergent **non trouvé** | https://ideas.repec.org/a/bla/jfinan/v58y2003i6p2515-2547.html | medium |
| Fama & French (2012), *JFE* 105(3), 457-472 | Amérique du Nord, Europe, Japon, Asie-Pacifique (développés) | Momentum **partout sauf au Japon**, et plus fort chez les petites valeurs. Value dans les 4 régions, primes qui **diminuent avec la taille, sauf au Japon** (précision du vérificateur, d'après le résumé publié). **Pas de prime de taille** sur 20 ans et plus | https://econpapers.repec.org/RePEc:eee:jfinec:v:105:y:2012:i:3:p:457-472 ; https://rpc.cfainstitute.org/research/cfa-digest/2012/11/size-value-and-momentum-in-international-stock-returns-digest-summary | medium |
| Asness, Moskowitz & Pedersen (2013), *JF* 68(3), 929-985 | 8 marchés ou classes d'actifs | Value et momentum présents partout ; **corrélation value-momentum moyenne −0,49** (−0,60 selon une autre version ; Japon −0,64). 50/50 sur toutes classes : **Sharpe ≈ 1,42-1,45** **[NON VÉRIFIÉ]**. 50/50 actions : Sharpe ≈ 1,1 aux États-Unis, 1,2 au Japon, 1,6 au Royaume-Uni et en Europe (version 2008) | https://www.aqr.com/Insights/Research/Journal-Article/Value-and-Momentum-Everywhere ; https://rpc.cfainstitute.org/research/cfa-digest/2013/11/value-and-momentum-everywhere-digest-summary ; https://conference.nber.org/confer/2008/si2008/AP/pedersen.pdf | medium |
| Jacobs & Müller (2020), *JFE* 135, 213-230 | 241 anomalies, 39 marchés | **Seuls les États-Unis** montrent un déclin fiable après publication ; les anomalies reflètent plutôt une **mauvaise valorisation** et des barrières à l'arbitrage que du *data mining* | https://www.fin.wiwi.uni-due.de/forschung/publikationen/anomalies-across-the-globe-once-public-no-longer-existent-14591/ | medium |
| Jensen, Kelly & Pedersen (2023), *JF* 78(5), 2465-2518 | 153 facteurs, 93 pays | La plupart des facteurs se répliquent (taux de **82,4 %** contre 35 % selon Hou-Xue-Zhang) ; ils forment 13 thèmes et tiennent hors échantillon | https://econpapers.repec.org/RePEc:nbr:nberwo:28432 ; https://alphaarchitect.com/factors-are-global-respectable-and-repeatable/ | medium |

### 3.2 Marchés frontières

| Étude | Échantillon | Résultats | Lien | Confiance |
|---|---|---|---|---|
| de Groot, Pang & Swinkels (2012), *JEF* 19(5), 796-818 | **24 marchés frontières** parmi les plus liquides, plus de 1 400 titres, 1997-2008, sans biais du survivant | Effets **value et momentum** économiquement et statistiquement significatifs, plus un **effet taille local**. Version de travail (top − bottom quintile, brut) : **B/P 1,40 %, E/P 1,53 %, D/P 0,59 %, momentum 6 mois 1,69 %/mois** **[NON VÉRIFIÉ]**, dont environ deux tiers viennent de la jambe acheteuse. **Coût : 2,5 % par transaction aller** × rotation **[NON VÉRIFIÉ]**. Net : value **≈ 6,6-7,7 %/an**, momentum **≈ 4,6-7,2 %/an** **[NON VÉRIFIÉ]** ; le momentum est **moins robuste aux coûts** que la value. Les facteurs globaux ne l'expliquent pas. **La neutralité pays réduit le momentum** (une partie vient du momentum pays) | https://econpapers.repec.org/RePEc:eee:empfin:v:19:y:2012:i:5:p:796-818 ; https://ideas.repec.org/p/ems/eureri/37284.html ; https://www.cxoadvisory.com/value-premium/extending-value-and-momentum-to-frontier-market-stocks/ | medium (chiffres mensuels : low-medium) |
| Zaremba & Maydybura (2019), *EMR* 38, 219-238 | Plus de 4 500 titres, 22 pays frontières, 1997-2018 | **Value et momentum forts et fiables** ; **pas d'évidence cohérente** pour la taille, l'investissement et la profitabilité. Intégration faible ; les **facteurs locaux** battent les globaux ; FF6 est le meilleur modèle | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3332958 ; https://www.sciencedirect.com/science/article/abs/pii/S156601411830116X | medium |
| Zaremba, Maydybura, Czapkiewicz & Arnaut (2021), *EMFT* 57(13), 3604-3633 | Plus de 160 anomalies, plus de 3 600 sociétés, 23 pays frontières, 1996-2017 | **Le modèle à 4 facteurs de Carhart (avec momentum) bat FF5 et le modèle q** ; ajouter profitabilité et investissement n'apporte rien | https://ideas.repec.org/a/mes/emfitr/v57y2021i13p3604-3633.html ; https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3378785 | medium |
| Zaremba (2020), *EMFT* 56(12), 2852-2873 | 140 anomalies, 23 pays frontières | **Forte persistance** des rendements d'anomalies, portée par les rendements passés de court et de long terme : on peut sélectionner les anomalies selon leur performance passée (momentum de facteurs) | https://ideas.repec.org/a/mes/emfitr/v56y2020i12p2852-2873.html | medium |
| Czapkiewicz, Zaremba & Szczygielski (2019), *Economic Research-Ekonomska Istraživanja* | 140 anomalies, 1997-2016 | Les anomalies **apparaissent et disparaissent** (modèle à changement de régime markovien) | https://www.tandfonline.com/doi/full/10.1080/1331677X.2019.1653782 | medium |
| Blackburn & Cakici (document de travail) | Frontières, 2005-2016 | Facteurs locaux > globaux, donc segmentation | https://alphaarchitect.com/factor-investing-in-frontier-stock-markets/ | low |
| Marshall, Nguyen & Visaltanachoti (2015), *J. Financial Markets* 24, 1-24 | 19 marchés frontières | Écart effectif ≈ **2,6 % (pondération égale) / 1,9 % (pondération par la capitalisation)** contre 0,72 % aux États-Unis (version de travail) **[NON VÉRIFIÉ]**. Le rééquilibrage **mensuel** annule les gains de diversification ; le rééquilibrage à **3 mois ou plus** les préserve. Coûts plus élevés quand l'aversion au risque monte | https://ideas.repec.org/a/eee/finmar/v24y2015icp1-24.html ; https://www.cxoadvisory.com/equity-premium/frontier-market-costs-and-benefits | medium |
| Chapitre d'ouvrage citant Zaremba & Szyszka (2016), Zaremba & Czapkiewicz (2017), Zaremba (2017) | Marchés peu développés et frontières | Le **retournement de court terme se transforme en continuation de court terme** | https://link.springer.com/chapter/10.1007/978-3-319-91530-2_3 | low (source secondaire) |
| Thèse UCT (2026), « Essays on momentum in frontier equity markets » | 11 marchés frontières, 2007-2023 | Les stratégies de momentum **plus courtes** battent les plus longues. Après coûts, les profits du momentum **disparaissent dans la plupart des marchés, sauf pour les stratégies courtes** | https://open.uct.ac.za/items/2e9c4d25-aae8-4bd9-93f8-5b6285c9edef | low **[NON VÉRIFIÉ]** (extrait unique, liste des marchés non vérifiée) |

### 3.3 Afrique (hors BRVM, puis BRVM)

| Marché | Étude | Période | Résultats | Lien | Confiance |
|---|---|---|---|---|---|
| Afrique frontière (9 marchés) | Steyn, Gilbert & Viviers (2024), *Investment Analysts Journal* 53(3), 189-206 | mars 2004 à juillet 2023 | Quintiles équipondérés triés sur la volatilité historique : **prime de faible volatilité significative, sauf en marché haussier**. Liste des pays et ampleur de la prime **non trouvées** | https://www.tandfonline.com/doi/abs/10.1080/10293523.2024.2361986 | low-medium **[NON VÉRIFIÉ]** (aucune source primaire relue) |
| Afrique subsaharienne | Hearn (2012), *Applied Financial Economics* 22(9), 681-707 | n.d. | Filtre de Kalman variable dans le temps : **effets de liquidité dans tous les marchés subsahariens étudiés** ; effets de taille marqués en Namibie et en Zambie | https://econpapers.repec.org/RePEc:taf:apfiec:v:22:y:2012:i:9:p:681-707 | medium |
| Afrique frontière | Hearn, Tauringana, Ntim, Malagila & Mishra (2025), *IRFA* 97, 103752 | 23 ans | FF5 et FF6 ont le meilleur pouvoir explicatif ; la croissance des actifs compte. Présence de la BRVM **non confirmée** | https://ideas.repec.org/a/eee/finana/v97y2025ics1057521924006847.html | low-medium **[NON VÉRIFIÉ]** |
| Afrique du Sud (JSE) | Muller & Ward (2013), *Investment Analysts Journal* | 1985-2011 | Effets significatifs et persistants : **momentum** (le plus fort), rendement des bénéfices, **rendement du dividende**, P/B, CF/P, liquidité, ROC, ROE, couverture des intérêts. **Pas d'effet taille**, sauf pour les toutes petites sociétés | https://repository.up.ac.za/handle/2263/21852 | medium |
| JSE | Étude 2023 sur les titres liquides | 2000-2021 | Pas d'effet taille, mais une prime des moyennes capitalisations | https://informahealthcare.com/doi/abs/10.1080/23322039.2023.2231662 | low |
| JSE | Thèse UWC | n.d. | Primes de taille et de momentum **procycliques**, prime value **contracyclique** | https://etd.uwc.ac.za/handle/11394/7316 | low |
| Nigeria | Assogbavi & Dodge (2002), *Journal of African Development* 5(1) | n.d. | Momentum à horizon moyen : environ **2 %/mois** ; le volume aide à prévoir | https://ideas.repec.org/a/afe/journl/v5y2002i1p16-35.html | low-medium |
| Nigeria | Musa et al. (2022) | 52 sociétés, 2016-2020 | Le momentum à **3 mois** fait mieux qu'à 6 ou 9 mois | https://ideas.repec.org/a/ris/amjoms/0070.html | low |
| Kenya (NSE) | Plusieurs études | 2001-2022 | Résultats **mitigés** : facteurs marché, taille, value et investissement significatifs (2009-2014), momentum faible. HML explicatif (2006-2015). Factor investing **non rentable** sur les grandes capitalisations (thèse 2010-2019 : momentum positif mais mitigé, value négative) | https://su-plus.strathmore.edu/handle/11071/12947 ; https://dx.doi.org/10.19044/esj.2018.v14n22p276 ; https://ideas.repec.org/h/spr/prbchp/978-3-031-84885-8_42.html | low |
| Égypte (EGX) | Thèses et articles | 1998-2018 | **L'effet taille est le plus constant** ; value et momentum mitigés selon les études | https://etheses.whiterose.ac.uk/id/eprint/28539/ ; https://journals.muni.cz/fai/article/download/14178/11846 | low |
| Maroc (Bourse de Casablanca) | Tazi, Aguenaou & Abrache (2022) ; autres | 2001-2020 | Taille et value **partielles**, momentum **non significatif** sur 2013-2017 ; une autre étude (2001-2020) trouve au contraire le **momentum le plus robuste**. Résultats contradictoires | https://ideas.repec.org/a/eco/journ1/2022-01-09.html ; https://ideas.repec.org/a/gam/jijfss/v11y2023i1p20-d1037353.html | low |
| **BRVM** | Revue 02 et cette revue | — | **Aucune étude publiée sur les primes value, momentum, faible volatilité ou qualité propres à la BRVM.** Le CAPM et FF3 expliquent mal le marché (R² ajusté moyen de 20,4 %, 28 titres, 2001-2008). Le rendement du dividende est l'axe de rémunération dominant (taux moyen 7,12 % au 20/11/2026) | voir `02-litterature-brvm.md`, section 5 ; https://www.tandfonline.com/doi/abs/10.1080/09603107.2012.718062 | medium (absence constatée) |

**Lecture critique de l'Afrique.** Les études sur les marchés africains autres que le JSE utilisent souvent des échantillons de 20 à 60 titres, des périodes courtes et des tests du modèle de Fama-French (R², alphas) plutôt que des primes de portefeuilles avec t-stats et coûts. Elles divergent souvent. **Le seul résultat robuste à travers l'Afrique est le momentum de court ou moyen terme** (JSE, Nigeria, thèse UCT), mais il est **fragile après coûts**. La value est forte au JSE et dans les échantillons frontières multi-pays. La faible volatilité est un facteur défensif qui disparaît en marché haussier.

---

## 4. Robustesse après coûts dans les marchés illiquides

### 4.1 Ce que dit la littérature

| Résultat | Source | Confiance |
|---|---|---|
| Les profits du momentum aux États-Unis sont **largement illusoires** après coûts : les titres qui ont le plus de momentum sont aussi les plus chers à négocier | Lesmond, Schill & Zhou 2004, *JFE* 71, 349-380 ; https://ideas.repec.org:443/a/eee/jfinec/v71y2004i2p349-380.html | medium |
| La pondération égale est la meilleure avant coûts et la pire après ; une **pondération par la liquidité** réduit les coûts | Korajczyk & Sadka 2004, *JF* (cité dans le résumé de la recherche ci-dessus) | low-medium |
| Les anomalies dont la rotation est **inférieure à 50 % par mois (aller)** gardent des spreads nets significatifs si on les conçoit pour limiter les coûts. La meilleure technique est une **bande achat/conservation** : critère d'entrée plus strict que le critère de maintien. Taille, value et profitabilité ont la plus grande capacité | Novy-Marx & Velikov 2016, *RFS* 29(1), 104-147 ; https://www.nber.org/papers/w20721 | medium |
| Frontières : value et momentum survivent à **2,5 % par transaction aller** ; le momentum est moins robuste que la value | de Groot et al. 2012 | low-medium **[NON VÉRIFIÉ]** |
| Frontières : écart effectif de 2,6 % (pondération égale) contre 0,72 % aux États-Unis ; rééquilibrer **au moins tous les 3 mois** | Marshall et al. 2015 | medium |
| Retournement à 1 mois : coût mensuel moyen de **1,94 %** **[NON VÉRIFIÉ]**, supérieur au rendement brut (États-Unis) | Medhat & Schmeling 2022 (résumé) ; https://alphaarchitect.com/short-term-momentum/ | low-medium |
| Retournement : 30 à 50 points de base par semaine, nets, **seulement sur les grandes capitalisations** et avec une construction qui limite la rotation (États-Unis) | de Groot, Huij & Zhou 2012, *JBF* 36(2) ; https://ideas.repec.org/a/eee/jbfina/v36y2012i2p371-382.html | medium |
| Combiner plusieurs caractéristiques **réduit les coûts**, car les transactions se compensent : 15 caractéristiques significatives avec coûts, contre 6 sans | DeMiguel, Martín-Utrera, Nogales & Uppal 2020, *RFS* 33(5), 2180-2222 ; https://ideas.repec.org/a/oup/rfinst/v33y2020i5p2180-2222..html | medium |
| La jambe acheteuse représente presque tous les profits de la taille, **environ 60 % de ceux de la value et environ 50 % de ceux du momentum** **[NON VÉRIFIÉ pour les parts exactes]** | Israel & Moskowitz 2013, *JFE* 108, 275-301 ; https://ideas.repec.org/a/eee/jfinec/v108y2013i2p275-301.html | medium |

### 4.2 Application à la BRVM (arithmétique des coûts)

Hypothèses de coûts reprises de la revue 02 **après sa correction** : **1,25 % par transaction aller** en scénario central (aller-retour de base de 2,5 % ; 2 × (0,30 + 0,80 × 1,18) = 2,49 %), et 1,5 % aller en scénario de stress (aller-retour de 3 %). *Correction du 2026-11-22 : la v1 de cette revue utilisait 1 % aller (aller-retour de 2 %), une valeur que la revue 02 a réfutée comme erreur de calcul.* Pour un portefeuille dont la rotation aller mensuelle est T, le coût mensuel vaut environ **2 × T × c**, où c est le coût d'une transaction aller.

| Stratégie (rotation mesurée en section 7) | Rotation aller T (par mois, tiers supérieur) | Coût mensuel à c = 1,25 % | Coût annuel | À c = 1,5 % (stress) |
|---|---|---|---|---|
| Value (E/P ou D/P) | 0,12 | 0,30 % | ≈ 3,6 % | ≈ 4,3 % |
| Faible volatilité | 0,12 | 0,29 % | ≈ 3,5 % | ≈ 4,1 % |
| Momentum 12-1 | 0,17 | 0,43 % | ≈ 5,1 % | ≈ 6,2 % |
| Momentum 6-1 | 0,28 | 0,69 % | ≈ 8,3 % | ≈ 9,9 % |
| Composite value + momentum 6-1 | 0,28 | 0,70 % | ≈ 8,4 % | ≈ 10,0 % |
| Retournement à 1 mois | 0,66 | 1,64 % | ≈ 19,7 % | ≈ 23,6 % |

*Colonnes recalculées le 2026-11-22. À l'ancienne hypothèse de c = 1 %, les coûts annuels étaient de 2,9 / 2,8 / 4,1 / 6,6 / 6,7 / 15,8 %.*

**Conséquences.**

1. **Le retournement à 1 mois est mort-né** sur la BRVM : environ 20 % par an de coûts (16 % à l'ancienne hypothèse de 1 %).
2. Avec un rééquilibrage **mensuel sans bande**, le momentum consomme environ 8 % par an (8,3-8,4 % à 1,25 % aller). La **bande** est indispensable (Novy-Marx & Velikov 2016) : on entre dans le top 30 %, on sort sous le top 50 %. Sur nos BOC (section 7.3), la bande **mensuelle** divise la rotation par environ 2 (de 0,28 à 0,15 pour value + momentum 6-1). Elle conserve l'essentiel de la prime brute (0,94 %/mois contre 1,09 %). La bande **trimestrielle** réduit encore la rotation (0,09), mais **détruit le signal momentum**, qui décroît vite (0,25 %/mois). Le rééquilibrage trimestriel de Marshall et al. (2015) vaut pour la diversification d'indices, pas pour un signal de momentum court.
3. Le seuil de rentabilité d'un facteur sur la BRVM est donc d'environ **3,5 à 8,5 % par an de prime brute en portefeuille acheteur seul**. C'est l'ordre de grandeur des primes nettes publiées pour les marchés frontières. **La marge est mince.**

---

## 5. Crash du momentum

### 5.1 Faits établis

| Fait | Source | Confiance |
|---|---|---|
| Le momentum subit des séries rares et persistantes de pertes, en partie **prévisibles**. Elles surviennent en « état de panique », **après des baisses de marché et quand la volatilité est élevée**, au moment du **rebond**. Le portefeuille se comporte alors comme une option d'achat vendue | Daniel & Moskowitz 2016, *JFE* 122(2), 221-247 ; https://www.nber.org/papers/w20439 | medium |
| Exemple : de mars à mai 2009, le décile des perdants a gagné **+163 %**, celui des gagnants **+8 %** (États-Unis) | version 2011 de Daniel & Moskowitz, relayée par la recherche ; chiffres cohérents avec le texte publié en 2016, selon le vérificateur | medium |
| Une stratégie dynamique (prévision de la moyenne et de la variance du momentum) **double environ l'alpha et le Sharpe** du momentum statique | Daniel & Moskowitz 2016 | medium |
| Le risque du momentum est variable et prévisible. Dosé selon sa variance réalisée sur les **6 derniers mois de rendements quotidiens**, le momentum voit son **Sharpe passer de 0,53 à 0,97** et les crashs disparaissent presque. La volatilité cible de l'article est de **12 % par an** (selon le texte publié, connu du vérificateur ; non relu en ligne le 2026-11-22) | Barroso & Santa-Clara 2015, *JFE* 116(1), 111-120 ; https://econpapers.repec.org/RePEc:eee:jfinec:v:116:y:2015:i:1:p:111-120 | medium |
| Le momentum résiduel a un Sharpe environ double du momentum total, surtout parce qu'il est moins volatil ; il est robuste dans les émergents | Blitz, Huij & Martens 2011 ; Blitz, Hanauer & Vidojevic 2020 | medium |
| À l'international, les profits du momentum sont **plus forts en marché haussier et en période peu volatile** | Goyal, Jegadeesh & Subrahmanyam (2025), *Review of Finance* 29(1), 241-273 ; https://ideas.repec.org/a/oup/revfin/v29y2025i1p241-273..html | low-medium **[NON VÉRIFIÉ]** |
| Aucune étude sur les crashs du momentum **spécifiquement en Afrique ou sur la BRVM** n'a été trouvée | recherche du 2026-11-22 | medium (absence constatée) |

### 5.2 Pourquoi le risque de crash est différent sur la BRVM

- **Pas de vente à découvert** : le crash classique vient surtout de la jambe vendeuse, quand les perdants très bêta rebondissent violemment. En portefeuille acheteur seul, on subit une **sous-performance relative** au rebond, pas une perte à effet de levier.
- **Limites de ±7,5 % par séance** (vérifié sur les BOC : aucune des 42 836 séances-titres échangées entre novembre 2022 et novembre 2026 ne dépasse ±7,5 %) : un rebond général s'étale sur plusieurs séances, et les perdants touchent le plafond haut. Un ordre d'achat au plafond peut rester non exécuté. Le crash relatif est **plus lent** mais peut durer.
- **Marché multi-pays (8 pays de l'UEMOA)** : un choc propre à un pays (politique, souverain) peut créer des perdants « pays » qui rebondissent ensemble. De Groot et al. trouvent qu'une partie du momentum frontière est du **momentum pays**. Il faut suivre l'exposition pays du panier momentum.

### 5.3 Règles proposées (hypothèses à tester)

1. **Pondération du momentum dosée selon sa volatilité** (à la Barroso & Santa-Clara) : poids du momentum dans le composite × min(1, σ_cible / σ̂_6m), où σ̂_6m est la volatilité réalisée, sur 126 séances, du spread momentum acheteur moins univers. σ_cible = médiane historique de σ̂_6m. Plancher à 0,5 × le poids nominal.
2. **Filtre « rebond après baisse »** (à la Daniel & Moskowitz) : si le Composite Total Return est en baisse sur 24 mois **et** si sa volatilité sur 3 mois dépasse le 80ᵉ centile, **diviser par deux le poids du momentum** pendant 3 mois. La fenêtre de **24 mois est bien celle de l'indicateur de marché baissier de Daniel & Moskowitz (2016)** : rendement cumulé du marché négatif sur les 24 derniers mois (confirmé par le vérificateur). En revanche, D&M mesurent la variance du marché sur **126 séances** ; la fenêtre de 63 séances et le seuil du 80ᵉ centile sont des **choix du projet**. **Série de marché** : l'indice Composite Total Return officiel n'existe que depuis le 02/01/2025. Avant cette date, il faut utiliser l'indice TR reconstruit (voir 8.3), jamais l'indice prix seul.
3. **Variante momentum résiduel** : momentum sur les résidus d'une régression sur le marché (bêta de Dimson) et sur le pays, à tester comme alternative au momentum brut.

---

## 6. Interactions value × momentum et combinaison des facteurs

### 6.1 Interactions

| Résultat | Source | Confiance |
|---|---|---|
| Les mesures value et momentum sont corrélées **négativement entre titres**, mais chacune prédit positivement les rendements. La value est **plus forte chez les perdants** et le momentum **plus fort chez les titres chers** | Asness 1997, *FAJ* 53(2), 29-36 ; https://www.aqr.com/library/journal-articles/the-interaction-of-value-and-momentum-strategies | medium |
| Corrélation des rendements value et momentum ≈ −0,49 à −0,60 **[NON VÉRIFIÉ pour les valeurs]** ; elle s'explique par des **expositions de signes opposés au risque de liquidité** | AMP 2013 | medium |
| La profitabilité est corrélée négativement à la value : l'ajouter **réduit la volatilité** et améliore la value, surtout chez les grandes valeurs liquides | Novy-Marx 2013 ; https://alphaarchitect.com/the-profitability-factor-international-evidence/ | medium |
| **BRVM, 2023-2026 (calcul interne)** : corrélation des spreads tertiles E/P et momentum 12-1 = **−0,58** ; E/P et momentum 6-1 = **−0,57** ; D/P et momentum 12-1 = **−0,41**. Faible volatilité et illiquidité : **−0,86** (sur la BRVM, les titres illiquides sont aussi les plus volatils) | section 7 | high (calcul) / low (stabilité) |

### 6.2 Méthodes de combinaison

| Méthode | Résultat | Source | Confiance |
|---|---|---|---|
| Poids égaux (1/N) plutôt qu'optimisés | Aucun des 14 modèles d'optimisation ne bat 1/N de façon fiable ; il faudrait environ **3 000 mois** d'historique pour 25 actifs | DeMiguel, Garlappi & Uppal 2009, *RFS* 22(5) ; https://ideas.repec.org/a/oup/rfinst/v22y2009i5p1915-1953.html | medium |
| Intégré (combinaison des signaux) contre mélangé (combinaison des portefeuilles) | L'intégré évite les titres aux expositions contradictoires (AQR, Fitzgibbons et al. 2017). Le mélangé a un meilleur ratio d'information à tracking error faible ou modérée, l'intégré à tracking error élevée, avec un point de bascule vers une exposition moyenne d'environ 0,9 (Ghayur et al. 2018). **Pas de différence statistiquement robuste** (Leippold & Rüegg 2018) | https://www.aqr.com/insights/research/white-papers/long-only-style-investing ; https://rpc.cfainstitute.org/research/financial-analysts-journal/2018/faj-v74-n3-5 ; https://econpapers.repec.org/RePEc:bla:eufman:v:24:y:2018:i:5:p:829-855 | medium |
| Compensation des transactions | Combiner les signaux réduit la rotation totale | DeMiguel et al. 2020 | medium |
| Momentum de facteurs (pondérer davantage les facteurs qui ont bien marché) | Robuste aux États-Unis et à l'international (Gupta & Kelly 2019 ; Ehsani & Linnainmaa 2022). Dans les marchés frontières, il existe une persistance des anomalies (Zaremba 2020) | https://www.nber.org/papers/w25551 ; https://alphaarchitect.com/2019/06/is-factor-momentum-really-everywhere | medium |
| Modèle de référence pour les marchés frontières | Le **4 facteurs de Carhart** (marché, taille, value, momentum) bat FF5 et le modèle q (Zaremba et al. 2021) ; FF6 selon Zaremba & Maydybura 2019 | voir 3.2 | medium |

**Choix pour la BRVM.** L'univers compte **45 à 48 titres**, la gestion est acheteuse seule et l'historique propre est court. Les signaux doivent donc être combinés en **rangs normalisés équipondérés** (score intégré) : c'est robuste aux valeurs extrêmes comme le PER de 631 et cela permet aux transactions de se compenser. Puis on prend le **tiers supérieur**. Les poids ne doivent **pas** être optimisés sur l'échantillon. Le momentum de facteurs n'est **pas activé** tant qu'on dispose de moins de 10 ans de séries de facteurs propres à la BRVM.

---

## 7. Vérification exploratoire interne sur les BOC (pas une étude publiée)

### 7.1 Méthode

- **Données** : 986 BOC du **17/11/2022 au 20/11/2026**, lus par `boc_parser.parse_boc_file`. 49 symboles au total ; 45 titres en moyenne dans l'univers à chaque fin de mois.
- **Rendements totaux quotidiens** : vérification faite, le BOC du lendemain d'une séance marquée « (D) » affiche un **cours précédent ajusté du dividende** : écart médian de −6,26 % avec la clôture de la veille, pour un rendement médian du dividende de 6,6 % sur 128 événements. Reproduction du 2026-11-22 : 131 événements, écart médian de −6,26 %, et un dividende implicite égal en médiane au dividende publié à 0,5 % près.
  - Les jours de détachement, le rendement total vaut (clôture + dividende implicite) / clôture de la veille − 1, où dividende implicite = clôture de la veille − cours précédent ajusté.
  - Si l'écart entre cours précédent et clôture de la veille dépasse 30 % (fractionnement), on prend clôture / cours précédent − 1.
  - Sinon, on prend clôture / clôture de la veille − 1.
  - Les titres suspendus sont exclus.
- **Univers** : titres non suspendus en fin de mois, avec au moins 40 séances de rendement sur les 63 dernières.
- **Signaux** :
  - momentum : `mom12_1`, `mom6_1`, `mom3_1`, `mom9_1`, `mom6_0`, `mom12_7` ;
  - retournement : `str1` = −rendement du dernier mois ;
  - value et rendement : `ep` = 1/PER si PER > 0 ; `dy` = rendement net BOC ;
  - faible volatilité : `lowvol` = −écart-type sur 126 séances (au moins 100 observations) ;
  - illiquidité : `illiq` = log de la moyenne de |r| / montant échangé sur 63 séances.
- **Portefeuilles** : **tertiles équipondérés** (environ 15 titres par jambe), formés à la clôture de fin de mois t. **Délai d'exécution d'une séance** : on détient de la clôture de t+1 à la clôture de la fin du mois suivant + 1. Statistiques mesurées :
  - « L/S » = tiers supérieur − tiers inférieur ;
  - « LO−EW » = tiers supérieur − panier équipondéré de l'univers ;
  - t-stats de Newey-West à 3 retards (`quant/stats.py:newey_west_tstat`).
- **Contexte** : le panier équipondéré a rapporté **+2,87 % par mois** en moyenne sur la période, un marché très haussier. La reproduction indépendante donne **+3,13 %** ; l'écart dépend de la chaîne de calcul du rendement total. Au 20/11/2026, le Composite a gagné +42,56 % sur 2026 et le Composite Total Return +49,19 % (BOC).

### 7.2 Résultats par facteur (bruts, avant coûts sauf la dernière colonne)

| Facteur | Mois | L/S %/mois | t (NW) | % de mois > 0 | LO−EW %/mois | t (NW) | Rotation aller (top) | LO−EW net à 1,25 % aller (corrigé) |
|---|---|---|---|---|---|---|---|---|
| mom12_1 | 36 | +0,38 | 0,35 | 50 % | −0,39 | −0,54 | 0,17 | −0,83 |
| **mom6_1** | 42 | **+2,11** | **2,34** | 60 % | +0,86 | 1,43 | 0,28 | +0,17 |
| str1 (retournement) | 46 | **−0,74** | −1,31 | 48 % | −0,59 | −1,97 | 0,66 | −2,24 |
| ep | 46 | +0,33 | 0,37 | 52 % | +0,27 | 0,52 | 0,12 | −0,02 |
| dy | 46 | +0,28 | 0,44 | 57 % | −0,32 | −0,89 | 0,12 | −0,62 |
| lowvol | 43 | −0,27 | −0,19 | 56 % | +0,12 | 0,20 | 0,12 | −0,18 |
| illiq | 46 | +0,41 | 0,29 | 37 % | +0,34 | 0,38 | 0,08 | +0,14 |

**Fenêtres de momentum (L/S, %/mois, t NW)** :

| Fenêtre | Résultat |
|---|---|
| 3-1 | +1,84 (t = 2,63) |
| **6-0** (sans saut) | **+2,45 (t = 2,66)** |
| 6-1 | +2,10 (t = 2,34) |
| 9-1 | +1,23 (t = 1,39) |
| 12-1 | +0,38 (t = 0,35) |
| 12-7 | **−1,94** (t = −1,49) |

Le momentum ne vit que sur l'horizon court-moyen, et la partie 12-7 est *négative* : il n'y a **pas d'« écho »**, comme le trouvent Goyal & Wahal (2015) hors des États-Unis.

**Sous-périodes (L/S, %/mois, t NW)** :

| Facteur | jusqu'au 31/12/2024 | depuis le 01/01/2025 |
|---|---|---|
| mom6_1 | +1,24 (t = 1,56) | +2,89 (t = 1,95) |
| str1 | +0,22 (t = 0,32) | −1,79 (t = −2,66) |
| ep | +0,20 (t = 0,24) | +0,48 (t = 0,29) |
| dy | −0,31 (t = −0,34) | +0,93 (t = 1,04) |
| **lowvol** | **+2,04 (t = 3,47)** | **−2,48** (t = −1,06) |
| **illiq** | **−1,64 (t = −3,01)** | **+2,65** (t = 1,04) |

La faible volatilité gagne en 2023-2024 et perd en 2025-2026, la phase la plus haussière. C'est exactement le schéma de Steyn et al. (2024) : pas de prime en marché haussier.

### 7.3 Combinaisons (score intégré par rangs normalisés, tiers supérieur)

| Composite (poids) | Mois | L/S %/mois (t) | LO−EW %/mois (t) | Tracking error / an | Rotation aller | LO−EW net à 1,25 % aller (corrigé) |
|---|---|---|---|---|---|---|
| Value (E/P 50 %, D/P 50 %) | 46 | +0,59 (0,65) | +0,21 (0,54) | 9,8 % | 0,14 | −0,13 |
| Momentum 6-1 seul | 42 | +2,10 (2,34) | +0,86 (1,43) | 12,3 % | 0,28 | +0,17 |
| **Value 50 % + momentum 6-1 50 %** | 42 | +1,99 (2,44) | **+1,09 (2,20)** | 9,9 % | 0,28 | **+0,39** |
| Value + mom 6-1 + faible volatilité (1/3 chacun) | 42 | +1,17 (1,56) | +0,53 (1,07) | 11,6 % | 0,18 | +0,07 |
| Idem + continuation 1 mois (20 %) | 42 | +2,06 (3,15) | +0,91 (2,44) | 9,4 % | 0,24 | +0,31 |
| Value 50 % + mom 12-1 50 % | 36 | −0,05 (−0,07) | −0,35 (−0,92) | 9,0 % | 0,21 | −0,88 |
| Composite « 12-1 » (E/P 15, D/P 20, mom 6-1 20, mom 12-1 15, faible vol 20) | 36 | +0,86 (1,13) | +0,11 (0,20) | 10,6 % | 0,18 | −0,34 |
| Composite principal sans qualité (E/P 15, D/P 20, mom 6-1 35, faible vol 20) | 42 | n.d. | +0,54 (1,49) | n.d. | 0,22 | +0,00 |

« n.d. » : non calculé.

**Effet de la bande de rotation** (LO−EW brut en %/mois, avec son t ; rotation aller mensuelle ; net à 1,25 % et 1,5 % aller, recalculé le 2026-11-22) :

| Composite | Mensuel sans bande | **Mensuel avec bande (30/50)** | Trimestriel avec bande (30/50) |
|---|---|---|---|
| Value 50 + mom 6-1 50 | 1,09 (2,20) ; rot. 0,28 ; net **+0,39** / +0,25 | 0,94 (1,77) ; rot. 0,15 ; net **+0,57** / **+0,49** | 0,25 (0,77) ; rot. 0,09 ; net +0,04 / −0,01 |
| Principal sans qualité (mom 6-1 35 %) | 0,54 (1,49) ; rot. 0,22 ; net +0,00 / −0,11 | 0,35 (0,66) ; rot. 0,09 ; net **+0,11** / +0,07 | 0,11 (0,20) ; rot. 0,05 ; net −0,02 / −0,04 |
| Composite « 12-1 » | 0,11 (0,20) ; rot. 0,18 ; net −0,34 / −0,42 | −0,01 (−0,03) ; rot. 0,06 ; net −0,16 / −0,19 | −0,15 (−0,23) ; rot. 0,05 ; net −0,28 / −0,29 |

Le signal momentum s'éteint en quelques mois. **La bande mensuelle est le meilleur compromis** entre coûts et dégradation du signal sur cet échantillon.

**Contrôle du biais de sélection.** 13 configurations acheteuses ont été comparées formellement (et au moins 6 fenêtres de momentum en plus). Pour le meilleur composite (value + momentum 6-1) :

| Mesure | Valeur |
|---|---|
| Sharpe annualisé de LO−EW | 1,31 |
| PSR(0) | 0,997 |
| **Sharpe dégonflé** (DSR, N = 13 ; `quant/stats.py:deflated_sharpe`) | **0,654** |

Le DSR reste **sous le seuil de 0,95** : le résultat **n'est pas significatif** une fois corrigé du nombre d'essais. Le nombre réel d'essais est plus élevé que 13, ce qui rend la correction encore plus sévère.

### 7.4 Interprétation

1. **Cohérent avec la littérature** :
   - le momentum court-moyen est positif (de Groot : 6 mois ; Nigeria : 3 mois ; thèse UCT : les stratégies courtes survivent) ;
   - le retournement à 1 mois laisse place à une **continuation** (Zaremba et al. sur les frontières) ;
   - value et momentum sont corrélés négativement (AMP) ;
   - la faible volatilité disparaît en marché haussier (Steyn et al.).
2. **Non concluant** : la value (E/P, D/P) seule est nulle sur cette période. Dans un marché où presque tout a monté de plus de 40 % par an, ce n'est **pas** une preuve d'absence de prime de long terme.
3. **Prudence** :
   - 36 à 48 mois de données et environ 15 titres par jambe : l'écart-type d'une moyenne mensuelle est d'environ 0,8 à 0,9 point ;
   - un seul régime de marché ;
   - les variantes testées sont nombreuses ;
   - les dividendes sont reconstruits à partir des ajustements du cours de référence ;
   - la taille n'a pas pu être testée.
4. **Étape suivante** : réestimer tout cela sur **2017-2026** en gardant **les paramètres figés dans ce document** (pré-enregistrement), puis séparer 2017-2019, 2020-2022 et 2023+. Le téléchargement est terminé : 2 334 BOC du 02/01/2017 au 20/11/2026. Les BOC antérieurs à 2017 renvoient une erreur 404 au format d'URL du projet (test du 2026-11-22). *Correction : la v1 visait 2013-2026.*

---

## 8. Recommandation chiffrée : facteurs et pondérations à tester sur la BRVM

### 8.1 Principe

Les poids viennent d'abord de la **littérature** sur les marchés frontières et émergents, puis sont **ajustés modérément** selon la faisabilité sur la BRVM : données disponibles, coûts et 45 titres. Ils **ne sont pas** optimisés sur la vérification interne de la section 7.

Deux choix sont toutefois **cohérents avec la vérification locale, et donc en partie influencés par elle** : l'horizon de momentum 6-1 et la bande mensuelle. C'est pourquoi la variante 12-1 (C) et la variante trimestrielle restent suivies. Tous ces paramètres sont **figés** avant le test sur **2017-01-02 → 2022-11-16**, qui servira de validation hors de l'échantillon de sélection 2022-2026. *Correction : la v1 indiquait 2013-2022, mais il n'y a pas de BOC locaux avant 2017.*

### 8.2 Composite « BRVM Alpha v1 » (acheteur seul)

| Bloc | Poids | Signaux (rangs normalisés dans l'univers) | Justification | Statut des données |
|---|---|---|---|---|
| **Value** | **35 %** | E/P (1/PER, PER > 0 ; PER ≤ 0 ou manquant mis au rang le plus bas) : **15 %** ; D/P (rendement net BOC, dividende versé dans les 18 derniers mois) : **20 %** | Facteur le plus robuste aux coûts dans les marchés frontières (de Groot ; Zaremba & Maydybura). Le D/P est la composante la plus naturelle à la BRVM (rendement moyen d'environ 7 %) et il est observable chaque jour | Disponible (BOC) |
| **Momentum** | **35 %** | **6-1** (formation 6 mois, saut d'un mois ; délai d'exécution d'une séance). Le 12-1 n'est qu'un challenger | Dans les marchés frontières, la littérature favorise l'horizon court-moyen (de Groot et al. : 6 mois ; thèse UCT : stratégies courtes ; Nigeria : 3 mois), et il n'y a pas d'écho hors des États-Unis (Goyal & Wahal). Localement, le 12-1 est nul et le 12-7 négatif. Pondération dosée selon sa volatilité (section 5.3) | Disponible (BOC) |
| **Faible volatilité** | **20 %** | −σ sur 250 séances (au moins 200 observations ; 126 en attendant) | Prime de faible volatilité dans l'Afrique frontière hors marché haussier ; amortit les baisses ; corrélée négativement au momentum (−0,26 à −0,52 en interne) | Disponible (BOC) |
| **Qualité** | **10 %** | Provisoire : régularité du dividende (nombre d'années avec dividende sur 5) et PER compris entre 3 et 40. Cible : ROE, marge, endettement (comptes annuels) | QMJ : composantes « distribution » et « profitabilité ». Évite les pièges de rendement (D/P élevé parce que le cours s'effondre) | Partiel ; comptes annuels à collecter |
| Taille | **0 %** | — | Pas de prime fiable (Fama-French 2012 ; Zaremba & Maydybura 2019 ; JSE) ; données absentes | À collecter pour le contrôle du risque |
| Retournement à 1 mois | **0 %** | — | Continuation dans les marchés frontières ; rotation de 66 % ; coût d'environ 16 %/an | Variante de recherche seulement (continuation) |
| Illiquidité | **0 % en alpha** | sert de **contrainte** : filtre de liquidité, plafond par rapport au volume moyen | Prime réelle mais instable localement (−3,0 puis +1,0 de t-stat), et la moins récoltable | Disponible (BOC) |

### 8.3 Construction du portefeuille

| Paramètre | Valeur | Source ou justification |
|---|---|---|
| Univers | Titres non suspendus, au moins 40 séances échangées sur 63 ; montant médian quotidien ≥ 2 M FCFA (seuil dur) | Revue 02. Au 30/10/2026, le montant médian quotidien sur 63 séances vaut : p10 = 4,4 M, p25 = 9,1 M, médiane = 19,3 M, p75 = 40,4 M et p90 = 78,5 M FCFA |
| Sélection | **Tiers supérieur** du score (environ 15 titres), minimum 12 titres | 45 titres : les tertiles sont la granularité maximale raisonnable (revue 02 : au moins 8 par jambe) |
| Pondération | Égale, plafonnée à 10 % par ligne ; position ≤ 10 % du montant quotidien moyen | DeMiguel et al. 2009 ; contrainte de capacité |
| Rééquilibrage | Signal et transactions **mensuels**, avec une **bande** : on entre si le rang est dans le top 30 %, on sort s'il tombe sous le top 50 %. Variante trimestrielle à suivre | Novy-Marx & Velikov 2016. Section 7.3 : la bande mensuelle divise la rotation par 2 environ ; la version trimestrielle détruit le signal momentum |
| Exposition pays | Alerte si le poids d'un pays dans le portefeuille dépasse **1,5 fois** son poids dans l'univers ; variante neutre par pays à tester | de Groot et al. (momentum pays) |
| Exposition secteur | Alerte si un secteur dépasse 1,5 fois son poids dans l'univers. Univers au 20/11/2026 : FIN 17, CB 9, CD 7, IND 6, ENE 4, TEL 3, SPU 2 | Diversification ; 7 secteurs seulement |
| Indice de référence | **BRVM Composite Total Return**, officiel à partir du 02/01/2025 (base 100) et publié au BOC depuis le 02/01/2026 (avis BRVM n° 308-2025 du 24/12/2025). **Avant 2025 : indice TR reconstruit** à partir de l'indice prix BRVM Composite chaîné avec les dividendes détachés. Il sera pondéré par la capitalisation quand le nombre d'actions sera collecté ; en attendant, on prend le panier équipondéré TR de l'univers. **Jamais l'indice prix seul** : l'écart est de 7,9 points en 2025 (+33,1 % TR contre +25,3 % prix) et de 6,6 points en 2026 au 20/11 (+49,19 % contre +42,56 %) | Revue 02 ; BOC du 24/12/2025 et du 20/11/2026 ; https://www.brvm.org/fr/indices |

### 8.4 Challengers pré-enregistrés (à tester en parallèle, N du DSR = 3 au minimum)

| Code | Poids | Rôle | Résultat interne 2023-2026 (bande mensuelle, sans qualité) |
|---|---|---|---|
| **A — principal** | E/P 15, D/P 20, mom 6-1 35, faible volatilité 20, qualité 10 | Ancré sur la littérature : value + momentum dominent dans les frontières ; faible volatilité défensive ; qualité contre les pièges de rendement | +0,35 %/mois brut (t = 0,66) ; **+0,11 %/mois net** à 1,25 % aller (+0,16 % à 1 %) |
| B — value × momentum | E/P 25, D/P 25, mom 6-1 50 | Combinaison d'AMP 2013 ; meilleur résultat interne, **choisi après coup** (DSR = 0,65) | +0,94 %/mois brut (t = 1,77) ; +0,57 %/mois net à 1,25 % aller |
| C — horizon long | E/P 15, D/P 20, mom 6-1 20, mom 12-1 15, faible volatilité 20, qualité 10 | Définition « standard » 12-1 (AMP, Carhart) | −0,01 %/mois brut ; −0,16 %/mois net à 1,25 % aller |

Le principal reste **A**, et non B : B est le gagnant d'une sélection faite sur le même échantillon. A est plus diversifié, et donc plus robuste à un changement de régime. La faible volatilité devrait aider en marché baissier (Steyn et al. 2024). B ne remplacera A que si, sur 2017-2022 (données hors de l'échantillon de sélection), B reste meilleur **et** franchit DSR ≥ 0,95. *Correction : la v1 disait « A passera devant B » et visait 2013-2022.*

### 8.5 Attentes honnêtes (a priori, avant test)

| Élément | Estimation | Raisonnement |
|---|---|---|
| Prime brute long/short des facteurs frontières (littérature) | Value environ 1 %/mois ; momentum environ 0,8-1,7 %/mois | de Groot et al. |
| Part captée en acheteur seul | Environ 50-60 % | Israel & Moskowitz 2013 |
| Décote pour déclin après publication et biais de sélection | Environ −30 à −50 % | McLean & Pontiff 2016 (−26 % hors échantillon, −58 % après publication aux États-Unis), à tempérer par Jacobs & Müller 2020 (pas de déclin fiable hors des États-Unis) |
| Coûts (bande mensuelle, rotation aller de 0,09 à 0,15 par mois) | Environ −2,7 à −4,5 %/an | Section 4.2 : 2 × rotation × 1,25 % × 12 (corrigé ; −2,2 à −3,6 % à l'ancienne hypothèse de 1 %) |
| **Surperformance nette attendue contre le Composite TR** | **Environ 0 à +4 %/an, centre vers +2 %/an** (corrigé ; la v1 donnait +2 à +4 %), tracking error ≈ 8-12 %, ratio d'information ≈ 0 à 0,4 (centre vers 0,2) | Recalcul avec les lignes ci-dessus : prime acheteuse d'environ 0,5-0,8 %/mois (6-10 %/an), moins 30 à 50 % de décote (3-7 %/an), moins 2,7 à 4,5 %/an de coûts. Au mieux quelques points par an, avec des années négatives. **Ce n'est pas une garantie.** |

---

## 9. Implications pour la plate-forme : paramètres prêts à coder

```yaml
# brvm_alpha/config/factor_priors.yaml (proposition, issue de la revue 03)
data:
  source: "BOC (brvm.org) via brvm_alpha.data.boc_parser"
  total_return:
    ex_div_marker: "(D)"                 # le lendemain, prev_close = cours de référence ajusté du dividende
    div_implied: "close_lag - prev_close"  # si D(t-1) et prev_close < close_lag
    split_gap_threshold: 0.30            # |prev_close/close_lag - 1| > 30 % -> utiliser close/prev_close
  missing_for_factors: ["shares_outstanding", "book_equity", "roe", "gross_profit", "assets"]  # à collecter

universe:
  exclude_status: ["suspended"]
  min_obs_63d: 40
  hard_min_median_value_63d_fcfa: 2_000_000
  soft_min_median_value_63d_fcfa: 10_000_000   # revue 02 ; ne laisse que ~12 mois avec >=18 titres en 2023-2026 -> soft
  min_names: 24                          # sinon pas de portefeuille ce mois-là

signals:                                 # tous convertis en rangs normalisés (z de rang) dans l'univers du mois
  ep:      {def: "1/PER if PER>0 else rank_min", winsor_pct: [1, 99]}
  dy:      {def: "net_yield_pct", require_dividend_within_months: 18, cap_pct: 15}
  mom6_1:  {formation_months: 6, skip_months: 1, implementation_lag_days: 1}
  mom12_1: {formation_months: 12, skip_months: 1, implementation_lag_days: 1}
  lowvol:  {window_days: 250, min_obs: 200, fallback_window_days: 126, sign: -1}
  quality_proxy:
    dividend_years_paid_of_5: true
    per_sane_range: [3, 40]
  research_only:                         # NE PAS utiliser dans le composite v1
    mom6_0: {formation_months: 6, skip_months: 0}
    mom3_1: {formation_months: 3, skip_months: 1}
    mom12_7: {formation_months: 12, skip_months: 7}       # pas d'écho attendu (Goyal-Wahal ; interne -1,94 %/mois)
    residual_mom: {formation_months: 12, skip_months: 1, regress_on: ["market_dimson", "country"]}
    str1_continuation: {months: 1, sign: +1}             # frontières : continuation, pas retournement
    illiq_amihud: {window_days: 63, log: true}

composite_v1:                            # poids FIGÉS avant le test 2013-2026 (pré-enregistrement)
  weights: {ep: 0.15, dy: 0.20, mom6_1: 0.35, lowvol: 0.20, quality_proxy: 0.10}   # A - principal
  challengers:
    B_value_momentum: {ep: 0.25, dy: 0.25, mom6_1: 0.50}
    C_long_horizon:   {ep: 0.15, dy: 0.20, mom6_1: 0.20, mom12_1: 0.15, lowvol: 0.20, quality_proxy: 0.10}
  promotion_rule: "B remplace A seulement si B > A sur 2017-01-02..2022-11-16 ET DSR(B) >= 0.95"   # CORRIGÉ (était 2013-2022)
  combine: "weighted sum of rank z-scores (signal blending)"
  missing_signal: "z = 0 (neutre)"
  momentum_vol_scaling:                  # Barroso & Santa-Clara 2015 (adapté)
    window_days: 126
    target: "median of trailing sigma"
    reference_target_vol_ann_bsc: 0.12   # valeur de l'article (VÉRIFIÉ) ; non utilisée telle quelle en acheteur seul
    floor_multiplier: 0.5
  momentum_crash_filter:                 # inspiré de Daniel & Moskowitz 2016 ; fenêtre de 24 m VÉRIFIÉE (indicateur de marché baissier de D&M)
    market: "benchmarks.primary (indice TR reconstruit avant 2025-01-02)"   # CORRIGÉ : le TR officiel n'existe pas avant 2025
    bear_lookback_months: 24
    vol_lookback_days: 63                # choix du projet (D&M : variance sur 126 séances)
    vol_percentile_trigger: 80
    momentum_weight_multiplier: 0.5
    duration_months: 3

portfolio:
  long_only: true
  select: "top_tercile"                  # ~15 titres
  min_holdings: 12
  weighting: "equal"
  max_weight: 0.10
  max_pct_adv: 10
  signal_frequency: "monthly"
  trade_frequency: "monthly"             # bande mensuelle (interne : rotation /2, signal conservé)
  trade_frequency_variant: "quarterly"   # à suivre ; détruit le momentum 6-1 sur 2023-2026
  band: {enter_top_pct: 30, exit_below_top_pct: 50}
  country_overweight_alert_ratio: 1.5
  sector_overweight_alert_ratio: 1.5

costs:                                   # cohérent avec la revue 02
  one_way_central_pct: 1.25             # CORRIGÉ 2026-11-22 (était 1.0) : revue 02, aller-retour de base de 2,5 %
  one_way_stress_pct: 1.5               # aller-retour de 3,0 % (revue 02)
  one_way_severe_pct: 2.07              # aller-retour de 4,14 % avec un courtage de 1,5 % (revue 02)
  model: "cost_per_month = 2 * one_way_turnover * one_way_cost"

benchmarks:
  primary: "BRVM COMPOSITE TOTAL RETURN"   # officiel : base 100 au 2025-01-02, publié au BOC depuis le 2026-01-02 (avis BRVM 308-2025)
  primary_official_from: "2025-01-02"
  primary_before_official: "reconstructed_composite_tr"   # indice prix BRVM COMPOSITE + dividendes détachés ; à défaut, equal_weight_universe_tr
  never_use_price_index_as_tr: true      # écart 2025 : +33,1 % TR contre +25,3 % prix
  secondary: ["equal_weight_universe", "BRVM 30", "BRVM PRESTIGE"]   # BRVM 30 et PRESTIGE : depuis le 2023-01-02 seulement ; BRVM 10 : jusqu'au 2022-12-30

validation:
  portfolios: "tertiles, EW, 1-day lag"
  tstat: "Newey-West, lags=3 (mensuel)"
  min_oos_t_stat_single_factor: 3.0      # Harvey, Liu & Zhu 2016
  deflated_sharpe_min: 0.95              # Bailey & López de Prado ; DSR interne actuel = 0,65
  count_all_trials: true                 # journaliser CHAQUE variante testée (N du DSR)
  subperiods: ["2017-01-02..2019-12-31", "2020-01-01..2022-12-31", "2023-01-01.."]   # CORRIGÉ (était 2013-09-16..) : BOC locaux depuis le 2017-01-02
  holdout_for_promotion: "2017-01-02..2022-11-16"
  regime_split: "benchmarks.primary (reconstruit avant 2025) 12m > 0 vs <= 0"   # faible volatilité attendue surtout hors marché haussier
  require_positive_net_of_stress_costs: true
  min_history_months_for_factor_momentum: 120

exploratory_benchmarks_2022_11_2026_11:  # section 7 (bruts, tertiles, 1 j de délai) - NE PAS optimiser dessus
  ew_universe_mean_pct_m: 2.87           # reproduction indépendante : 3.13 (dépend de la chaîne TR)
  ls_pct_m: {mom12_1: 0.38, mom6_1: 2.10, str1: -0.74, ep: 0.33, dy: 0.28, lowvol: -0.27, illiq: 0.41}
  ls_t_nw: {mom12_1: 0.35, mom6_1: 2.34, str1: -1.31, ep: 0.37, dy: 0.44, lowvol: -0.19, illiq: 0.29}
  top_turnover_one_way_m: {ep: 0.12, dy: 0.12, lowvol: 0.12, mom12_1: 0.17, mom6_1: 0.28, str1: 0.66, illiq: 0.08}
  corr_ls: {ep_mom12_1: -0.58, ep_mom6_1: -0.57, dy_mom12_1: -0.41, lowvol_illiq: -0.86}
  best_combo_value_mom6: {lo_minus_ew_pct_m: 1.09, t_nw: 2.20, te_ann_pct: 9.9, dsr_n13: 0.654}
  band_monthly_net_at_1_25pct_pct_m: {A_without_quality: 0.11, B_value_momentum: 0.57, C_long_horizon: -0.16}   # CORRIGÉ (coût de 1,25 %)
  band_monthly_turnover_one_way_m: {A_without_quality: 0.09, B_value_momentum: 0.15, C_long_horizon: 0.06}

literature_priors:                       # pour bornes et vraisemblance des résultats locaux
  frontier_ls_gross_pct_m: {bp: 1.40, ep: 1.53, dp: 0.59, mom6: 1.69}        # de Groot et al., version de travail [NON VÉRIFIÉ]
  frontier_net_pct_yr: {value: [6.6, 7.7], momentum: [4.6, 7.2]}             # à 2,5 % par transaction aller [NON VÉRIFIÉ]
  em_ep_ls_pct_m: {value: 1.02, t: 5.46}                                     # van der Hart et al. 2003 [NON VÉRIFIÉ]
  em_momentum_ls_pct_m: {value: 0.39, t: 2.35}                               # Rouwenhorst 1999 (EW, 20 pays) [NON VÉRIFIÉ]
  value_momentum_corr: [-0.60, -0.49]                                        # AMP 2013 [NON VÉRIFIÉ : valeurs exactes ; signe établi]
  long_side_share: {size: 1.0, value: 0.6, momentum: 0.5}                    # Israel & Moskowitz 2013 [NON VÉRIFIÉ]
  post_publication_decay_us: 0.58                                            # McLean & Pontiff 2016 (VÉRIFIÉ ; 0,26 hors échantillon)
  frontier_effective_spread_pct: {ew: 2.6, vw: 1.9, us: 0.72}               # Marshall et al. 2015 [NON VÉRIFIÉ]
  turnover_threshold_one_way_m: 0.50                                         # Novy-Marx & Velikov 2016 (VÉRIFIÉ)
  momentum_vol_scaled_sharpe: {static: 0.53, scaled: 0.97}                   # Barroso & Santa-Clara 2015 (VÉRIFIÉ ; cible de 12 %/an)
```

**Règles d'implémentation :**

1. **Pas d'anticipation.** Le PER et le rendement BOC du jour t ne servent qu'à des transactions à partir de t+1. Les données comptables (phase 2) ne sont utilisables qu'après leur **date de publication** effective, avec au moins 3 mois de décalage pour les comptes annuels si la date n'est pas connue.
2. **Pré-enregistrement.** Les poids de `composite_v1` sont **figés**. Chaque variante testée est journalisée, et son nombre alimente le N du Sharpe dégonflé. Un changement de poids crée une version v2, évaluée seulement sur des données postérieures.
3. **Rapport utilisateur.** Le rapport affiche :
   - la performance nette contre le Composite TR ;
   - la contribution de chaque bloc (value, momentum, faible volatilité, qualité) ;
   - la rotation réalisée ;
   - les coûts estimés ;
   - le DSR ;
   - en permanence : **« les primes factorielles sont des moyennes de long terme ; aucun gain n'est garanti »**.
4. **Garde-fous.** Si le score composite repose sur moins de 3 blocs valides pour un titre, on le neutralise (z = 0). Si l'univers compte moins de 24 titres, on reste au panier équipondéré.

---

## 10. Questions ouvertes

1. **Textes intégraux à lire** dès que l'accès réseau le permet :
   - de Groot et al. 2012 : tableaux publiés, définition exacte du momentum et du saut, filtre de liquidité, liste des 24 marchés et présence de la BRVM ou de la Côte d'Ivoire ;
   - Steyn et al. 2024 : liste des 9 marchés et ampleur de la prime ;
   - Hearn et al. 2025 : pays inclus ;
   - Zaremba & Maydybura 2019 : primes chiffrées ;
   - AMP 2013 : tableau 1 publié ;
   - Barroso & Santa-Clara 2015 : niveau de volatilité cible (réglé le 2026-11-22 : 12 %/an) ;
   - Daniel & Moskowitz 2016 : définition exacte de l'indicateur de marché baissier (réglé le 2026-11-22 : rendement cumulé du marché sur 24 mois < 0 ; variance du marché sur 126 séances) ;
   - Frazzini & Pedersen 2014 : estimation du bêta (réglé le 2026-11-22, voir 2.1).
2. **Données à collecter** : nombre d'actions en circulation (taille, rotation), fonds propres, résultat net, marge brute, endettement des 48 émetteurs, avec dates de publication.
3. **Réestimation** de la section 7 sur 2017-2026 avec les paramètres figés, et analyse par régime (haussier, baissier). Le téléchargement est terminé : 2 334 BOC depuis le 02/01/2017. Pour 2013-2016, il faut trouver une autre source.
7. **Indice de référence reconstruit** avant le 02/01/2025 : valider la méthode en la comparant à l'indice TR officiel sur 2025-2026 (écart de suivi cible < 1 %/an).
4. **Neutralité pays** : la Côte d'Ivoire domine. Faut-il un momentum neutre par pays ? Il faut mesurer la part « pays » du momentum BRVM, comme de Groot et al.
5. **Continuation à 1 mois** : est-elle un artefact des limites de ±7,5 % (découverte du prix étalée sur plusieurs séances) ? Il faut la tester avec un délai de 2 à 5 séances et en excluant les titres au plafond (lien avec la section 7 de la revue 02).
6. **Pièges de rendement** : quelle part des D/P élevés précède une baisse ou une suppression du dividende ? Il faut mesurer la persistance des dividendes dans l'historique BOC.

---

## 11. Sources

**Marchés émergents et international**

- Rouwenhorst (1999), *Journal of Finance* 54(4) : https://ideas.repec.org/a/bla/jfinan/v54y1999i4p1439-1464.html ; version de travail : http://depot.som.yale.edu/icf/papers/fileuploads/2501/original/98-95.pdf
- van der Hart, Slagter & van Dijk (2003), *Journal of Empirical Finance* 10 : https://papers.tinbergen.nl/01009.pdf ; https://www.sciencedirect.com/science/article/abs/pii/S0927539802000221
- Cakici, Fabozzi & Tan (2013), *Emerging Markets Review* 16 : https://econpapers.repec.org/RePEc:eee:ememar:v:16:y:2013:i:c:p:46-65
- Hanauer & Lauterbach (2019), *Emerging Markets Review* 38 : https://ideas.repec.org/a/eee/ememar/v38y2019icp265-286.html ; https://alphaarchitect.com/the-cross-section-of-emerging-market-stock-returns/
- Blitz, Pang & van Vliet (2013), *Emerging Markets Review* 16 : https://ideas.repec.org/a/eee/ememar/v16y2013icp31-45.html ; https://www.robeco.com/docm/docu-whitepaper-the-volatility-effect-in-em.pdf ; https://www.cxoadvisory.com/volatility-effects/reward-for-risk-in-emerging-equity-markets/
- Blitz & van Vliet (2007), *Journal of Portfolio Management* : https://papers.ssrn.com/abstract=980865
- Hou, Karolyi & Kho (2011), *Review of Financial Studies* 24(8) : https://ideas.repec.org/a/oup/rfinst/v24y2011i8p2527-2574.html
- Chui, Titman & Wei (2010), *Journal of Finance* 65(1) : https://ideas.repec.org/a/bla/jfinan/v65y2010i1p361-392.html
- Griffin, Ji & Martin (2003), *Journal of Finance* 58(6) : https://ideas.repec.org/a/bla/jfinan/v58y2003i6p2515-2547.html
- Fama & French (2012), *Journal of Financial Economics* 105(3) : https://econpapers.repec.org/RePEc:eee:jfinec:v:105:y:2012:i:3:p:457-472 ; https://rpc.cfainstitute.org/research/cfa-digest/2012/11/size-value-and-momentum-in-international-stock-returns-digest-summary
- Asness, Moskowitz & Pedersen (2013), *Journal of Finance* 68(3) : https://www.aqr.com/Insights/Research/Journal-Article/Value-and-Momentum-Everywhere ; https://rpc.cfainstitute.org/research/cfa-digest/2013/11/value-and-momentum-everywhere-digest-summary ; https://conference.nber.org/confer/2008/si2008/AP/pedersen.pdf ; https://www.cxoadvisory.com/value-premium/combining-value-and-momentum-across-asset-classes/
- Asness (1997), *Financial Analysts Journal* 53(2) : https://www.aqr.com/library/journal-articles/the-interaction-of-value-and-momentum-strategies ; https://ideas.repec.org/a/taf/ufajxx/v53y1997i2p29-36.html
- Jegadeesh & Titman (1993), *Journal of Finance* 48(1) : https://ideas.repec.org/a/bla/jfinan/v48y1993i1p65-91.html
- Goyal & Wahal (2015), *JFQA* 50(6) : https://ideas.repec.org/a/cup/jfinqa/v50y2015i06p1237-1267_00.html ; https://alphaarchitect.com/when-academics-disagree-on-momentum-investing/
- Goyal, Jegadeesh & Subrahmanyam (2025), *Review of Finance* 29(1) : https://ideas.repec.org/a/oup/revfin/v29y2025i1p241-273..html
- Blitz, Huij & Martens (2011), *Journal of Empirical Finance* ; Blitz, Hanauer & Vidojevic (2020), *IREF* 69 : https://econpapers.repec.org/RePEc:eee:reveco:v:69:y:2020:i:c:p:932-957 ; https://alphaarchitect.com/swedroe-spotlight-enhancing-momentum-strategies-via-idiosyncratic-momentum/
- Daniel & Moskowitz (2016), *Journal of Financial Economics* 122(2) : https://www.nber.org/papers/w20439 ; https://econpapers.repec.org/RePEc:eee:jfinec:v:122:y:2016:i:2:p:221-247 ; https://www.chicagobooth.edu/review/understanding-momentum-crashes
- Barroso & Santa-Clara (2015), *Journal of Financial Economics* 116(1) : https://econpapers.repec.org/RePEc:eee:jfinec:v:116:y:2015:i:1:p:111-120 ; https://www.etf.com/node/94292.md
- Frazzini & Pedersen (2014), *Journal of Financial Economics* 111(1) : https://econpapers.repec.org/RePEc:eee:jfinec:v:111:y:2014:i:1:p:1-25
- Novy-Marx (2013), *Journal of Financial Economics* : https://nber.org/papers/w15940 ; https://alphaarchitect.com/the-profitability-factor-international-evidence/
- Asness, Frazzini & Pedersen (2019), *Review of Accounting Studies* 24(1) : https://link.springer.com/10.1007/s11142-018-9470-2 ; https://papers.ssrn.com/abstract=2312432
- Asness, Frazzini, Israel, Moskowitz & Pedersen (2018), *Journal of Financial Economics* 129(3) : https://econpapers.repec.org/RePEc:eee:jfinec:v:129:y:2018:i:3:p:479-509
- Amihud, Hameed, Kang & Zhang (2015), *Journal of Financial Economics* 117(2) : https://ideas.repec.org:443/a/eee/jfinec/v117y2015i2p350-368.html ; https://researchonline.jcu.edu.au/42806/
- Israel & Moskowitz (2013), *Journal of Financial Economics* 108 : https://ideas.repec.org/a/eee/jfinec/v108y2013i2p275-301.html
- Lesmond, Schill & Zhou (2004), *Journal of Financial Economics* 71 : https://ideas.repec.org:443/a/eee/jfinec/v71y2004i2p349-380.html
- Novy-Marx & Velikov (2016), *Review of Financial Studies* 29(1) : https://www.nber.org/papers/w20721 ; https://ideas.repec.org/a/oup/rfinst/v29y2016i1p104-147..html
- de Groot, Huij & Zhou (2012), *Journal of Banking & Finance* 36(2) : https://ideas.repec.org/a/eee/jbfina/v36y2012i2p371-382.html
- Medhat & Schmeling (2022), *Review of Financial Studies* 35(3) : https://econpapers.repec.org/RePEc:oup:rfinst:v:35:y:2022:i:3:p:1480-1526. ; https://alphaarchitect.com/short-term-momentum/
- Stosik & Zaremba (2026), *Economics Letters* (retournement ajusté par l'industrie, 64 pays, 0,53 %/mois) : https://www.sciencedirect.com/science/article/pii/S0165176526003095 ; https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6630998 (confiance low-medium, non utilisé dans les paramètres)
- McLean & Pontiff (2016), *Journal of Finance* : https://rpc.cfainstitute.org/research/cfa-digest/2016/06/does-academic-research-destroy-stock-return-predictability-digest-summary
- Jacobs & Müller (2020), *Journal of Financial Economics* 135 : https://www.fin.wiwi.uni-due.de/forschung/publikationen/anomalies-across-the-globe-once-public-no-longer-existent-14591/
- Jensen, Kelly & Pedersen (2023), *Journal of Finance* 78(5) : https://econpapers.repec.org/RePEc:nbr:nberwo:28432 ; https://alphaarchitect.com/factors-are-global-respectable-and-repeatable/
- Harvey, Liu & Zhu (2016), *Review of Financial Studies* 29(1) : https://ideas.repec.org/a/oup/rfinst/v29y2016i1p5-68..html ; https://nber.org/papers/w20592

**Combinaison des facteurs**

- DeMiguel, Garlappi & Uppal (2009), *Review of Financial Studies* 22(5) : https://ideas.repec.org/a/oup/rfinst/v22y2009i5p1915-1953.html
- DeMiguel, Martín-Utrera, Nogales & Uppal (2020), *Review of Financial Studies* 33(5) : https://ideas.repec.org/a/oup/rfinst/v33y2020i5p2180-2222..html
- Ghayur, Heaney & Platt (2018), *Financial Analysts Journal* 74(3) : https://rpc.cfainstitute.org/research/financial-analysts-journal/2018/faj-v74-n3-5 ; https://alphaarchitect.com/constructing-long-only-multifactor-strategies-portfolio-blending-vs-signal-blending/
- Fitzgibbons, Friedman, Pomorski & Serban (2017), *Journal of Investing* : https://www.aqr.com/insights/research/white-papers/long-only-style-investing
- Leippold & Rüegg (2018), *European Financial Management* 24(5) : https://econpapers.repec.org/RePEc:bla:eufman:v:24:y:2018:i:5:p:829-855 ; https://www.robeco.com/en-uk/insights/2017/10/mixed-versus-integrated-multi-factor-portfolios
- Ehsani & Linnainmaa (2022), *Journal of Finance* 77(3) : https://www.nber.org/papers/w25551 ; Gupta & Kelly (2019), *JPM* : https://alphaarchitect.com/2019/06/is-factor-momentum-really-everywhere

**Marchés frontières**

- de Groot, Pang & Swinkels (2012), *Journal of Empirical Finance* 19(5) : https://econpapers.repec.org/RePEc:eee:empfin:v:19:y:2012:i:5:p:796-818 ; https://ideas.repec.org/p/ems/eureri/37284.html ; https://repub.eur.nl/pub/37284/ERS-2012-012-F&A.pdf (non accessible depuis la session) ; https://www.cxoadvisory.com/value-premium/extending-value-and-momentum-to-frontier-market-stocks/ ; https://www.bayes.citystgeorges.ac.uk/__data/assets/pdf_file/0006/86658/Swinkels.pdf (non accessible depuis la session)
- Zaremba & Maydybura (2019), *Emerging Markets Review* 38 : https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3332958 ; https://www.sciencedirect.com/science/article/abs/pii/S156601411830116X
- Zaremba, Maydybura, Czapkiewicz & Arnaut (2021), *EMFT* 57(13) : https://ideas.repec.org/a/mes/emfitr/v57y2021i13p3604-3633.html ; https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3378785 ; https://quantpedia.com/equity-factor-strategies-in-frontier-markets/
- Zaremba (2020), *EMFT* 56(12) : https://ideas.repec.org/a/mes/emfitr/v56y2020i12p2852-2873.html
- Czapkiewicz, Zaremba & Szczygielski (2019) : https://www.tandfonline.com/doi/full/10.1080/1331677X.2019.1653782
- Marshall, Nguyen & Visaltanachoti (2015), *Journal of Financial Markets* 24 : https://ideas.repec.org/a/eee/finmar/v24y2015icp1-24.html ; https://www.cxoadvisory.com/equity-premium/frontier-market-costs-and-benefits
- Chapitre « Trees Do Not Grow to the Sky: Reversals in a Stock Market » (Springer) : https://link.springer.com/chapter/10.1007/978-3-319-91530-2_3
- Thèse UCT « Essays on momentum in frontier equity markets » : https://open.uct.ac.za/items/2e9c4d25-aae8-4bd9-93f8-5b6285c9edef
- Blackburn & Cakici (résumé) : https://alphaarchitect.com/factor-investing-in-frontier-stock-markets/

**Afrique**

- Steyn, Gilbert & Viviers (2024), *Investment Analysts Journal* 53(3) : https://www.tandfonline.com/doi/abs/10.1080/10293523.2024.2361986 ; https://www.nisc.co.za/products/abstracts/37767/the-low-volatility-effect-in-african-frontier-equity-markets
- Hearn (2012), *Applied Financial Economics* 22(9) : https://econpapers.repec.org/RePEc:taf:apfiec:v:22:y:2012:i:9:p:681-707 ; https://eprints.soton.ac.uk/423327/
- Hearn, Tauringana, Ntim, Malagila & Mishra (2025), *IRFA* 97 : https://ideas.repec.org/a/eee/finana/v97y2025ics1057521924006847.html ; https://eprints.soton.ac.uk/496110/
- Muller & Ward (2013), JSE : https://repository.up.ac.za/handle/2263/21852
- JSE, titres liquides 2000-2021 : https://informahealthcare.com/doi/abs/10.1080/23322039.2023.2231662 ; cyclicité (UWC) : https://etd.uwc.ac.za/handle/11394/7316
- Nigeria : https://ideas.repec.org/a/afe/journl/v5y2002i1p16-35.html ; https://ideas.repec.org/a/ris/amjoms/0070.html ; https://businessday.ng/analysis/article/exploring-momentum-investing/ (praticien, low)
- Kenya : https://su-plus.strathmore.edu/handle/11071/12947 ; https://dx.doi.org/10.19044/esj.2018.v14n22p276 ; https://ideas.repec.org/h/spr/prbchp/978-3-031-84885-8_42.html
- Égypte : https://etheses.whiterose.ac.uk/id/eprint/28539/1/Elsayed_202039159_CorrectedThesisClean.pdf ; https://journals.muni.cz/fai/article/download/14178/11846
- Maroc : https://ideas.repec.org/a/eco/journ1/2022-01-09.html ; https://ideas.repec.org/a/gam/jijfss/v11y2023i1p20-d1037353.html ; https://econjournals.com/index.php/ijefi/article/view/12685
- BRVM, CAPM et Fama-French (2013) : https://www.tandfonline.com/doi/abs/10.1080/09603107.2012.718062
- BRVM, avis n° 308-2025 « Affichage de l'indice BRVM Composite Total Return » (BOC du 24/12/2025, copie texte `data/boc_text/boc_20251224.txt.gz`) ; page des indices https://www.brvm.org/fr/indices (consultée le 2026-11-22)
- Revue 02 du projet, coûts corrigés : `02-litterature-brvm.md`, section 13 (aller-retour de base de 2,5 %)
- BRVM, données primaires : BOC n°222 du 20/11/2026, https://www.brvm.org/sites/default/files/boc_20261120_2.pdf (copie texte : `data/boc_text/boc_20261120.txt.gz`) ; 986 BOC du 17/11/2022 au 20/11/2026 dans `data/boc_text/`

---

## 12. Vérification adversariale (2026-11-22)

### 12.1 Méthode et limites

- **Rôle** : vérificateur sceptique. Le but était de réfuter en priorité les **paramètres qui seront codés** : coûts, indice de référence, fenêtres, dates et données, puis les chiffres d'études qui fixent les poids.
- **Accès réseau** :
  - le quota de recherche web de la session était épuisé dès le début de la vérification ;
  - `econpapers.repec.org`, `ideas.repec.org` et `www.cxoadvisory.com` sont bloqués (échec de résolution DNS) ;
  - `www.brvm.org` est accessible (pages publiques, GET simple).
- **Sources utilisées**, dans cet ordre :
  1. les BOC locaux (source primaire), avec une **reproduction indépendante** des calculs de la section 7. Elle utilise la chaîne `data/panel/adjusted_prices.parquet` (dividendes et divisions détectés par `store.adjusted_table`), distincte de la méthode du chercheur fondée sur le cours précédent ajusté ;
  2. brvm.org ;
  3. la revue 02 du projet, après sa propre vérification ;
  4. la connaissance bibliographique du vérificateur pour les articles très connus. Ces confirmations sont marquées « texte publié connu, non relu en ligne » : elles valent *medium*, pas *high*.
- **Ce qui n'a pas été fait** : aucun test sur 2017-01-02 → 2022-11-16. Cette période est l'échantillon de validation pré-enregistré, et y toucher maintenant la contaminerait.
- **Fichiers de vérification** (hors projet) : scripts dans le répertoire scratchpad de la session, `verif/mom_check.py`, `verif/fac_check.py`, `verif/exdiv_check.py`, `verif/idx_check.py` et `verif/tr_vs_price.py`.

### 12.2 Verdicts

| # | Élément vérifié | Valeur v1 | Verdict | Valeur retenue / commentaire | Preuve | Confiance |
|---|---|---|---|---|---|---|
| 1 | Coût aller central (`costs.one_way_central_pct`) | 1,0 % (« cohérent avec la revue 02 ») | **corrigé** | **1,25 %**. La revue 02 a corrigé l'aller-retour de base de 2,0 à 2,5 %, soit 2 × (0,30 + 0,80 × 1,18). Le stress à 1,5 % est inchangé, et un cas sévère à 2,07 % est ajouté (4,14 % aller-retour). Les tableaux 4.2, 7.2, 7.3, 8.4 et 8.5 sont recalculés | `02-litterature-brvm.md` (section 13, ligne `round_trip_baseline_pct`) ; https://www.brvm.org/fr/node/312 | high (cohérence interne) |
| 2 | Indice de référence « BRVM Composite Total Return » pour les backtests, le filtre de crash et le partage par régime | utilisé sur toute l'histoire | **corrigé** | L'indice a sa base 100 au **02/01/2025** et n'est publié au BOC que depuis le **02/01/2026** (avis BRVM n° 308-2025 du 24/12/2025). Aucun BOC de 2017-2025 ne le contient (0 fichier avant le 24/12/2025). Avant 2025, il faut un **indice TR reconstruit**. L'indice prix sous-estime le TR de 7,9 points en 2025 (+25,3 % contre +33,1 %) et de 6,6 points en 2026 au 20/11 (+42,56 % contre +49,19 %) | BOC du 24/12/2025, du 02/01/2026 et du 20/11/2026 ; https://www.brvm.org/fr/indices ; https://www.brvm.org/sites/default/files/boc_20261120_2.pdf | high |
| 3 | Indices secondaires BRVM 30 et BRVM PRESTIGE | utilisés sans réserve | **corrigé** (précision) | Ils n'existent que depuis le 02/01/2023. Le BRVM 10 s'arrête le 30/12/2022 | panel des indices des BOC 2017-2026 | high |
| 4 | Période de réestimation et sous-périodes (`validation.subperiods`, échantillon de validation) | 2013-2026 ; « 2013-09-16..2019-12-31 » | **corrigé** | Le téléchargement est terminé avec 2 334 BOC du **02/01/2017** au 20/11/2026 (configuration `--start 2017-01-01`). Les BOC du 04/01/2016 et du 02/01/2014 renvoient une erreur 404 au format d'URL du projet. Sous-périodes retenues : 2017-01-02..2019-12-31 / 2020-2022 / 2023+ ; échantillon de validation : 2017-01-02..2022-11-16 | `data/download.log` ; GET https://www.brvm.org/sites/default/files/boc_20160104.pdf → 404 | high |
| 5 | Taux de rendement moyen du marché = moyenne simple de 43 titres ; médiane | 7,12 % ; 4,67 % | **confirmé** | 43 rendements, moyenne 7,12 %, médiane 4,67 % (BOC du 20/11/2026) | https://www.brvm.org/sites/default/files/boc_20261120_2.pdf | high |
| 6 | PER manquant ou ≤ 0 et PER > 50 au 20/11/2026 | 4 et 6 (UNLC 631, BNBC 519, BOAN 225, SDSC 186, SIVC 78, SAFC 51) | **confirmé** | Identique. Les PER manquants sont SCRC, SICC, UNXC et STAC | même BOC | high |
| 7 | Secteurs de l'univers au 20/11/2026 | FIN 17, CB 9, CD 7, IND 6, ENE 4, TEL 3, SPU 2 | **confirmé** | Identique (48 sociétés) | même BOC (indices sectoriels et lignes titres) | high |
| 8 | Limite de variation de ±7,5 % par séance | ±7,5 % | **confirmé** | Aucune des 42 836 séances-titres échangées du 17/11/2022 au 20/11/2026 ne dépasse ±7,5 % | BOC locaux ; revue 01 (Instruction I-A) | high |
| 9 | Cours précédent du BOC ajusté du dividende le lendemain d'un « (D) » | écart médian −6,26 % ; 128 événements | **confirmé** | 131 événements, écart médian −6,26 %. Le dividende implicite est égal en médiane au dividende publié (ratio 0,995) | BOC locaux 2022-2026 | high |
| 10 | 986 BOC du 17/11/2022 au 20/11/2026 | 986 | **confirmé** | 986 dates distinctes | `data/boc_text/` | high |
| 11 | Spreads internes du momentum (tertiles, délai d'une séance) | 6-1 : +2,10 (t 2,34) ; 12-1 : +0,38 (t 0,35) ; 3-1 : +1,84 ; 6-0 : +2,45 ; continuation à 1 mois : +0,74 | **confirmé** (qualitativement) | Reproduction : 6-1 : **+2,47 (t 2,72)** ; 12-1 : +0,28 (t 0,26) ; 3-1 : +1,95 (t 2,30) ; 6-0 : +2,65 (t 2,83) ; continuation à 1 mois : +0,64 (t 1,02). Le signe, la hiérarchie des fenêtres et la nullité du 12-1 sont reproduits ; les niveaux bougent d'environ ±0,4 point selon la chaîne TR | BOC locaux, `verif/mom_check.py` | high (calcul) / low (portée) |
| 12 | E/P, D/P et faible volatilité non significatifs ; inversion de la faible volatilité selon la sous-période | ep +0,33 ; dy +0,28 ; lowvol −0,27 ; lowvol +2,04 (t 3,47) jusqu'en 2024, −2,48 ensuite | **confirmé** | Reproduction : ep +0,23 (t 0,26) ; dy +0,11 (t 0,18) ; lowvol −0,34 (t −0,25) ; lowvol **+2,00 (t 2,96)** jusqu'en 2024 puis **−2,68** (t −1,27) | `verif/fac_check.py` | high (calcul) / low (portée) |
| 13 | Rendement moyen du panier équipondéré | +2,87 %/mois | **invérifiable** (écart de méthode) | +3,13 %/mois sur 45 mois dans la reproduction. Ce n'est pas un paramètre codé ; le chiffre est laissé avec la note | `verif/mom_check.py` | medium |
| 14 | Barroso & Santa-Clara 2015 : Sharpe de 0,53 → 0,97 ; variance sur 126 séances | — | **confirmé** | Confirmé, et la volatilité cible manquante est ajoutée (**12 %/an**, `reference_target_vol_ann_bsc`) | texte publié connu, non relu en ligne ; https://econpapers.repec.org/RePEc:eee:jfinec:v:116:y:2015:i:1:p:111-120 | medium |
| 15 | Daniel & Moskowitz 2016 : fenêtre de 24 mois du filtre baissier | « non vérifiée » | **confirmé** | L'indicateur de marché baissier vaut 1 si le rendement cumulé du marché sur 24 mois est négatif. La variance du marché est mesurée sur 126 séances : la fenêtre de 63 séances et le 80ᵉ centile sont des choix du projet. Les chiffres de mars-mai 2009 (+163 % pour les perdants, +8 % pour les gagnants) sont cohérents | texte publié connu, non relu en ligne ; https://www.nber.org/papers/w20439 | medium |
| 16 | de Groot, Pang & Swinkels 2012 (*JEF* 19(5), 796-818) : existence, 24 marchés frontières, 1997-2008, value, momentum et taille locale | — | **confirmé** (existence et contenu général) | Étude réelle et bien référencée | https://econpapers.repec.org/RePEc:eee:empfin:v:19:y:2012:i:5:p:796-818 (non joignable ce jour) | medium |
| 17 | de Groot et al. : spreads mensuels B/P 1,40, E/P 1,53, D/P 0,59, momentum 1,69 ; coût de 2,5 % par transaction ; nets de 6,6-7,7 % et 4,6-7,2 % par an | — | **invérifiable** | Source secondaire unique (CXO, inaccessible) ; marqué [NON VÉRIFIÉ]. Ces valeurs ne servent que de bornes (`literature_priors`), pas de poids | https://www.cxoadvisory.com/value-premium/extending-value-and-momentum-to-frontier-market-stocks/ (bloqué) | low |
| 18 | Zaremba & Maydybura 2019 (*EMR* 38) : plus de 4 500 titres, 22 pays, 1997-2018 | — | **confirmé** (existence) / détails invérifiables | Article réel ; les effectifs n'ont pas été relus | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3332958 (non relu) | medium |
| 19 | Steyn, Gilbert & Viviers 2024 (*IAJ* 53(3)) : prime de faible volatilité sur 9 marchés africains, sauf en marché haussier | — | **invérifiable** | Aucune trace primaire relue dans cette session ; marqué [NON VÉRIFIÉ]. Le poids de 20 % de la faible volatilité ne doit **pas** reposer sur cette seule étude : Blitz, Pang & van Vliet (2013) sur les émergents et la reproduction interne (gain en 2023-2024, perte en 2025-2026) vont dans le même sens | https://www.tandfonline.com/doi/abs/10.1080/10293523.2024.2361986 (non relu) | low |
| 20 | Hearn et al. 2025 (*IRFA* 97, 103752) ; thèse UCT 2026 ; Stosik & Zaremba 2026 ; Goyal, Jegadeesh & Subrahmanyam 2025 | — | **invérifiable** | Marqués [NON VÉRIFIÉ] ; aucun ne fixe de paramètre codé | URL de la section 11 (non relues) | low |
| 21 | AMP 2013 : corrélation value-momentum de −0,49 / −0,60 ; Sharpe 50/50 de 1,42-1,45 | — | **invérifiable** (valeurs) / **confirmé** (signe négatif) | Marqué [NON VÉRIFIÉ] pour les valeurs. La corrélation interne BOC de −0,57/−0,58 reste valide | https://www.aqr.com/Insights/Research/Journal-Article/Value-and-Momentum-Everywhere (non relu) | medium (signe) / low (valeurs) |
| 22 | Marshall, Nguyen & Visaltanachoti 2015 : écart effectif de 2,6 % / 1,9 % contre 0,72 % | — | **invérifiable** | Article réel (*J. Financial Markets* 24) ; les chiffres sont marqués [NON VÉRIFIÉ] | https://ideas.repec.org/a/eee/finmar/v24y2015icp1-24.html (bloqué) | low-medium |
| 23 | Novy-Marx & Velikov 2016 : les anomalies dont la rotation est inférieure à 50 %/mois survivent ; la bande achat/conservation est la plus efficace | — | **confirmé** | Conforme au résumé publié | texte publié connu ; https://www.nber.org/papers/w20721 | medium |
| 24 | McLean & Pontiff 2016 : −26 % hors échantillon, −58 % après publication | — | **confirmé** | Conforme (*JF* 71(1), 97 prédicteurs) | texte publié connu ; https://rpc.cfainstitute.org/research/cfa-digest/2016/06/does-academic-research-destroy-stock-return-predictability-digest-summary | medium |
| 25 | Harvey, Liu & Zhu 2016 : seuil t > 3,0 | 3,0 | **confirmé** | Conforme | texte publié connu ; https://ideas.repec.org/a/oup/rfinst/v29y2016i1p5-68..html | medium-high |
| 26 | Jacobs & Müller 2020 (241 anomalies, 39 marchés, déclin seulement aux États-Unis) ; Jensen, Kelly & Pedersen 2023 (153 facteurs, 93 pays, 13 thèmes) | — | **confirmé** | Conforme. Le taux de 82,4 % chez JKP est plausible mais n'a pas été relu | textes publiés connus ; URL de la section 11 | medium |
| 27 | DeMiguel, Garlappi & Uppal 2009 (environ 3 000 mois pour 25 actifs, 14 modèles) ; DeMiguel et al. 2020 (6 → 15 caractéristiques) | — | **confirmé** | Conforme | textes publiés connus ; URL de la section 11 | medium |
| 28 | Medhat & Schmeling 2022 : coût de 1,94 %/mois ; Israel & Moskowitz 2013 : parts acheteuses de 60 % (value) et 50 % (momentum) | — | **invérifiable** | Les articles existent ; les chiffres sont marqués [NON VÉRIFIÉ]. `long_side_share` n'est qu'un a priori | URL de la section 11 (non relues) | low-medium |
| 29 | Fama & French 2012 : primes value « qui diminuent avec la taille » | dans les 4 régions | **corrigé** (précision) | Elles diminuent avec la taille **sauf au Japon** | texte publié connu ; https://econpapers.repec.org/RePEc:eee:jfinec:v:105:y:2012:i:3:p:457-472 | medium |
| 30 | Frazzini & Pedersen 2014 : estimation du bêta (question ouverte) | « non vérifié » | **complété** | σ sur 1 an de rendements quotidiens, corrélation sur 5 ans de rendements à 3 jours, rétrécissement vers 1 avec un poids de 0,6 | texte publié connu ; https://econpapers.repec.org/RePEc:eee:jfinec:v:111:y:2014:i:1:p:1-25 | medium |
| 31 | Règle de promotion en 8.4 (« A passera devant B ») | formulation inversée | **corrigé** | « B ne remplacera A que si… », cohérent avec `promotion_rule` | relecture | high |
| 32 | Surperformance nette attendue | +2 à +4 %/an ; ratio d'information de 0,2-0,4 | **corrigé** | **0 à +4 %/an, centre vers +2 %** ; ratio d'information de 0 à 0,4 (centre vers 0,2), après coûts de 1,25 % aller. Cela reste une hypothèse a priori, **sans aucune garantie** | recalcul (section 8.5) | low |

### 12.3 Bilan

- **Confirmés** (16) : n° 5 à 12, 14 à 16, 23 à 27.
- **Corrigés ou complétés** (8) : n° 1 à 4 et 29 à 32. Les trois corrections les plus coûteuses portent sur les paramètres codés :
  - le coût aller (n° 1) ;
  - l'indice de référence et le filtre de crash (n° 2) ;
  - la fenêtre de données (n° 4).
- **Invérifiables ce jour** (8, marqués [NON VÉRIFIÉ]) : n° 13, 17 à 22 et 28. Le n° 18 est confirmé pour l'existence de l'étude, pas pour ses détails.
- **Réfutés et supprimés** : aucun. Aucune étude citée n'a pu être identifiée comme inventée. Les études invérifiables le sont faute d'accès, pas faute d'existence probable.
- **Ce que cela change pour le moteur** :
  1. avec un coût de 1,25 %, le composite principal A ne rapporte plus que **+0,11 %/mois net** sur 2023-2026, soit pratiquement zéro ;
  2. le challenger B (value × momentum) reste positif (+0,57 %/mois net) mais il a été **choisi après coup** (DSR de 0,65) ;
  3. la décision entre A et B doit attendre la validation pré-enregistrée sur 2017-2022, avec l'indice TR reconstruit.
- **Conclusion pour l'utilisateur** : rien dans cette revue ne permet de promettre un gain, et encore moins « 100 % de gains garantis ».
