# Rendement net et pertes — le suivi sur papier (S2)

> **Performance passée ≠ garantie. Aucun gain n'est garanti.**
>
> Ce module ne promet aucun gain et ne rend aucune perte impossible.
> Statut de la plate-forme : toutes les variantes (A à I) et la référence REF sont **REJETÉES** sur leur test (S1).
> La plate-forme fonctionne en « indice discipliné », **à titre d'étude**.
> Le suivi sans argent réel (S2) commence le **mardi 01/12/2026**.
> Rien dans ce document n'autorise un achat avec de l'argent réel.

Ce document décrit le protocole du suivi sur papier : ce qui sera suivi, comment on en jugera, ce que vous devez décider
et signer avant le 01/12/2026. Il reprend le §8 et le §13 du cahier des charges du module « Rendement net et pertes ».
Les numéros entre crochets (§…) renvoient à ce cahier.

L'empreinte SHA-256 de ce fichier est écrite dans chaque ligne de la déclaration signée (`empreinte_cahier`). Modifier
ce fichier après la signature change son empreinte : la date du commit fait foi.

Statut des chiffres : **Fait** (recalculable), **Estimation** (méthode citée, incertain), **Hypothèse** (supposé, non
vérifié). Les seuils marqués « Hypothèse de travail » sont des propositions : vous les validez ou les corrigez.

---

## 1. En deux mots

1. On ne peut ni garantir un gain ni empêcher une perte.
2. Le suivi sur papier ne prouvera aucune règle par ses gains avant plusieurs années.
3. Il vérifie la « plomberie » : frais payés, ordres servis, argent qui dort, données manquantes.
4. Toute règle nouvelle doit être **écrite, datée et signée avant** d'être suivie. Sinon, elle ne pourra pas être jugée
   honnêtement.
5. La plate-forme ne passe aucun ordre, ne vend jamais seule et ne recommande pas d'argent réel avec les règles
   actuelles.

---

## 2. Ce que le suivi peut montrer, et ce qu'il ne peut pas [§8.1]

- **Le suivi ne peut pas prouver la référence par ses gains avant plusieurs années.** Dans son test, l'écart de suivi de
  la référence face au marché était de 4,31 % par an [Fait publié, `reports/validation_S1/metrics.json`]. Neuf fois sur
  dix, le hasard seul déplace donc son retard cumulé de moins de 5 points à 6 mois, 7 points à 12 mois et 12 points à
  36 mois [Estimation, hypothèse normale].
- **Le suivi vérifie la plomberie** : frais, exécution, argent qui dort, données.
- **Aucun essai ne sera prouvé par ses gains en un an.** Le plus petit avantage visible après un an est de 1,6 à
  3,3 points par an pour un seul essai [Estimation].
- **On ne classe jamais des essais par leur rendement.** Avec trois essais sans avantage réel, la chance qu'au moins un
  dépasse la référence par hasard est d'au plus 87,5 % ; avec cinq, d'au plus 96,9 % [Estimation, bornes hautes].

---

## 3. Les portefeuilles suivis [§8.6]

| Nom | Règle | Taille et tarif | Rôle | Compte dans m |
|---|---|---|---|---|
| `REF-S2` | article 1 : la règle telle qu'elle a été testée | 10 000 000 FCFA, tarif supposé | témoin | non |
| `N` | article 5 : la référence avec les notes de l'analyste | 10 000 000 FCFA, tarif supposé | essai à prétention de rendement | oui |
| `E-C`, `E-D` | articles 6 et 7 : la référence plus un seul écart (option 1 seulement) | 10 000 000 FCFA, tarif supposé | essais jugés sur le suivi | E-D oui ; E-C dès son premier écart au témoin |
| `PLAN` | l'ordre par défaut, avec la mémoire de la remise à niveau de janvier et les écarts déclarés « oui » | 10 000 000 FCFA, tarif supposé | vérification comptable | non |
| `MOI` | la même règle que `PLAN`, à votre taille et avec votre grille ; papier ou réel | votre montant en actions, votre grille | analyse de sensibilité, pas un essai | non |

`m` est le nombre d'essais à prétention de rendement : il durcit le seuil de chaque décision (§5 ci-dessous).

---

## 4. Les articles de la déclaration

La commande `suivi declarer --modele` écrit ces articles dans un fichier, avec la proposition par défaut de chacun. Vous
remplissez la réponse de chaque article, puis vous signez (§9).

### Article 1 — `REF-S2`, la référence telle qu'elle a été testée [§8.2]

Phrase : *Le panier de référence suit la règle testée : les 20 plus grosses sociétés éligibles, remises à niveau fin
janvier, sans les notes.*

| Élément | Valeur figée |
|---|---|
| Sélection et poids | variante REF (D8) : 20 plus grosses capitalisations éligibles, poids proportionnels à la capitalisation, plafonds de D8, 98 % investi |
| Calendrier | remise à niveau à la première décision de janvier ; positions gardées entre deux ; sorties forcées de la règle (filtres de risque, inéligibilité) |
| Dividendes | crédités nets à la date de paiement ; gardés en liquidités jusqu'à la remise à niveau |
| Arrondi, bande | vers le bas, ligne par ligne ; bande de 2 points par ligne |
| Exécution | cours moyen du jour suivant si le titre est échangé ; 10 % du volume du jour au plus ; report 10 séances |
| Notes de l'analyste | aucune (elles n'ont joué aucun rôle dans le test) |
| Coûts, capital | scénario « central » ; 10 000 000 FCFA |
| Départ | première décision à la dernière séance au plus tard le 30/11/2026 ; première exécution à la première séance à partir du 01/12/2026 |
| Code | le moteur du test, sans modification ; fabrique `brvm_alpha.suivi.temoin.temoin_model` |

Ce témoin n'a pas besoin de signature : sa définition est celle du test. Un test automatique prouve que sa fabrique
redonne, au franc, les mêmes valeurs et les mêmes ordres que la fabrique du test.

**Budget de retard, écrit d'avance** [Estimation] : 3,3 à 4,2 points de moins que le marché la première année (frais
d'entrée compris), puis 1,7 à 2,6 points de moins par an. Aucune conclusion sur la référence avant 36 mois. L'alerte de
la spécification (retard relatif de 10 %) reste le seul seuil.

**Ce que le suivi vérifie sur la référence** : P1 identité comptable de chaque semaine (écart de 0 FCFA) ; P2 frais payés
contre frais prévus ; P3 part investie moyenne ; P4 part des titres servis ; P5 ordres déclenchés par un trou de
bulletins ; P6 coût de la remise à niveau de janvier ; P7 écart au marché en valeur de part ; P8 exécution sur papier en
mode « test » contre le moteur (les écarts sont publiés).

### Articles 2 à 4 — écarts d'exécution : des décisions humaines datées [§8.3]

> Ces écarts ne sont pas jugés sur leurs gains. Leur effet sur le rendement est celui d'être plus ou moins investi : il a
> le signe du marché. La décision se prend maintenant, par vous. Le suivi vérifie seulement que la règle fait ce qu'elle
> dit et ne coûte pas plus que prévu.

Chaque écart accepté s'applique dans `PLAN`, jamais dans `REF-S2`. Chaque clause de retrait peut échouer.

| Article | Écart | Ce qu'on compte | Clause de retrait, écrite d'avance | Durée | Proposition |
|---|---|---|---|---|---|
| E-L | Ordres à cours limité, exécution sur papier avec test de limite (plus stricte que l'exécution du test) | part des titres servis à 1, 3 et 10 séances ; prix payé contre cours moyen du jour et contre dernier cours | aucune : c'est une mesure | 12 mois | **oui** |
| E-B | Compléter un ordre servi en partie ; placer un apport d'argent frais hors de la bande | part investie après les ordres ; ordres en plus ; frais en plus | retiré si un complément coûte, en frais facturés par franc, plus de deux fois l'ordre d'origine | 12 mois | **oui** |
| E-A | Arrondi « plus forts restes » avec une marge de deux trimestres de frais | francs placés en plus ; marge du pire cas à chaque ordre | retiré si, une seule fois, la provision au prix limite dépasse les liquidités, ou si la grille réelle rend la marge négative | 12 mois | **au choix** |

Une entrée en plusieurs fois, si vous l'appliquez, s'ajoute comme article E-T de même nature.

### Article 5 — `N`, la référence avec les notes [§8.4]

Phrase : *Le panier de référence avec les notes de l'analyste : le seul essai sur papier qui cherche à faire mieux que le
panier sans les notes.*

| Élément | Contenu |
|---|---|
| Règle | REF-S2, plus les notes de l'analyste (veto, filtres de risque, inclinaisons), en règle stricte à la date de décision |
| Mesure | `d_t` = rendement hebdomadaire net de N − celui de REF-S2 |
| Statistique | t de Newey-West de la moyenne de `d_t` (4 retards) ; intervalle par bootstrap stationnaire (blocs de 8 semaines, 5 000 tirages, graine 0) |
| Durée | aucune lecture de rendement avant 52 semaines ; aucune affirmation avant 156 semaines |
| Notes retirées de l'ordre | à un point d'étape d'au moins 52 semaines, si t ≤ −2,0 ou si le retard cumulé de N sur REF-S2 atteint 3 points **[Hypothèse de travail : à valider]** |
| Notes confirmées | seulement à 156 semaines ou plus, si t ≥ 3,0 **et** p unilatérale ≤ 0,05 ÷ m **et** DSR ≥ 0,95 |
| Sinon | « indéterminé » : rien ne change ; l'écran écrit « les notes n'ont pas fait leurs preuves » |
| Prédiction écrite d'avance | « indéterminé » est le résultat le plus probable, même si les notes sont utiles |

### Articles 6 et 7 — `E-C` et `E-D` : essais, ou dérogation signée [§8.4]

La spécification de la stratégie (§8.5, dernier paragraphe) classe deux questions comme « décisions humaines attendues
(non tranchées ici, **nouvel essai à juger sur S2 seulement**) » : (i) le plancher D1 et l'âge des ordres après un trou de
bulletins ; (ii) le repli D8 (dividendes gardés en liquidités jusqu'à la remise à niveau annuelle).

| Article | Essai | Règle | Critère écrit d'avance |
|---|---|---|---|
| 6 | E-C, continuité des données | REF-S2 + option `--continuite` : pas de vente pour une inéligibilité calculée sur une fenêtre de 126 séances où des bulletins manquent | **retenue** dans PLAN si aucun titre réellement suspendu ou radié n'a été gardé à tort plus de 20 séances ; **retirée** sinon ; compte dans m dès son premier écart au témoin |
| 7 | E-D, réinvestissement mensuel | REF-S2 + option `--reinvestir` : à la dernière séance du mois, une seule ligne, aucune vente | **retirée** au 31/01/2028 si les frais par franc réinvesti dépassent 1,5 fois ceux de l'ordre d'entrée, ou s'il y a plus de 6 ordres par an ; **confirmée** seulement à 156 semaines ou plus, avec les conditions de N |

Réponses possibles pour chacun :

- **option 1 (proposée)** : essai déclaré, inscrit au registre (`S2-EC`, `S2-ED`), avec son portefeuille « REF-S2 plus
  l'écart seul » exécuté sur papier en mode « test » ;
- **option 2 : oui** ou **option 2 : non** : dérogation signée au §8.5 de la spécification (son texte est cité dans la
  ligne). L'écart devient une décision d'exécution, appliquée (oui) ou non dans PLAN ; il n'est pas inscrit au registre
  et ne compte ni dans N ni dans m ;
- **non déclaré** : aucune ligne. Sans signature de l'une ou l'autre option avant le 01/12/2026, E-C et E-D restent
  **éteints** dans PLAN.

Déclarer E-D, c'est choisir d'être plus exposé au marché de mai à janvier.

### Le plan `PLAN` [§8.6]

Phrase : *Le plan suivi sur papier : l'ordre par défaut, avec la mémoire de la remise à niveau de janvier et les écarts
que vous acceptez.*

C'est l'ordre par défaut (avec les notes, sauf si vous choisissez « sans les notes ») + la mémoire annuelle (`--suivi`)
+ les écarts déclarés « oui ». Ce n'est pas « ce que fait la commande par défaut », qui n'a pas de mémoire. PLAN n'est
jamais comparé au témoin sur le rendement, seulement sur des faits comptés.

---

## 5. Correction pour comparaisons multiples [§8.5]

1. m = nombre d'essais à prétention de rendement inscrits pour S2. Option 1 : m = 2 au départ (N et E-D), puis 3 dès que
   E-C s'écarte du témoin. Option 2 : m = 1 (N seul).
2. Seuil unilatéral de 0,05 ÷ m (Bonferroni), **en plus** de t ≥ 3,0.
3. Tout essai ajouté plus tard augmente m pour toutes les décisions à venir. Aucun seuil n'est relâché après coup.
4. Le DSR est calculé avec tous les essais du registre (98 aujourd'hui, plus les trois à cinq lignes S2).
5. Un portefeuille identique au témoin (E-C sans bulletin manquant) entre dans N pour le DSR, mais pas dans m tant qu'il
   reste identique.
6. Aucun classement par rendement n'est affiché avant un point d'étape.

---

## 6. Points d'étape [§8.8]

| Date | Ce qu'on lit | Ce qu'on peut décider |
|---|---|---|
| 01/12/2026 | début du suivi sur papier | — |
| chaque semaine | bulletin : trois feux | une revue, jamais une vente automatique |
| 29/01/2027 | remise à niveau de la référence | coût mesuré (P6) |
| 01/06/2027 | comptabilité seulement : P1 à P7, clauses de retrait | retrait d'un écart ; première date possible pour **examiner** une décision humaine sur l'argent réel |
| 01/12/2027 | première lecture de `d_t` (52 semaines) | retrait éventuel des notes |
| 31/01/2028 | E-D après une saison de dividendes et une remise à niveau | retrait de E-D, ou « en cours » (jamais « confirmé » avant 156 semaines) |
| 01/12/2029 | 156 semaines | première affirmation possible |

Entre deux points d'étape : aucune décision sur une règle, aucun changement sans nouvel article.

---

## 7. Vers l'argent réel : ce que le module affiche, et ce qu'il ne décide pas [§8.9]

Le texte actuel de la spécification exige, pour le statut PROMU, des filtres verts sur S1 **et** sur S2. Tout est rejeté
sur S1 : **avec ce texte, rien ne peut être promu, et la plate-forme ne recommandera pas d'argent réel.** Changer ce
texte serait votre décision, jamais avant 6 mois de suivi sur papier (01/06/2027).

Conditions **nécessaires, non suffisantes**, proposées pour qu'une telle décision puisse seulement être examinée
[Hypothèse de travail] : 26 semaines de journal sans rupture de chaîne ; grille du courtier au statut « grille écrite » ;
contrôles P1 à P5 et P8 conformes ; retard de la référence dans son budget ; montant que vous acceptez de risquer, réserve
et durée choisis ; un changement écrit de la règle de promotion, daté, avec sa raison ; une décision écrite et signée de
votre part.

---

## 8. Décisions humaines en attente [§13]

À trancher **avant le 01/12/2026** :

| N° | Décision | Proposition par défaut | Où elle s'écrit |
|---|---|---|---|
| 1 | Les notes dans l'ordre pendant le suivi : garder l'ordre « avec notes », ou revenir à la règle testée « sans notes » ? | **garder « avec les notes »** (défaut actuel) | article PLAN |
| 2 | Écarts d'exécution : oui ou non pour E-L, E-B, E-A | **E-L oui ; E-B oui ; E-A au choix** | articles E-L, E-B, E-A |
| 3 | E-C et E-D : essais (option 1) ou dérogation signée (option 2) ; déclarer E-D ou non | **option 1 pour les deux** (conforme au §8.5 de la spécification) | articles E-C, E-D |
| 3 bis | Seuils de l'article 5 : retrait des notes à t ≤ −2,0 ou à 3 points de retard cumulé | **valider** (ou corriger dans le fichier avant de signer) | article N |
| 3 ter | Trois exceptions aux tests existants (pages de l'interface, couverture des routes, tâche de nuit) | **accord** ; sinon les routes nouvelles et l'étape de nuit sont retirées et `suivi maj` se lance à la main | décision écrite, hors déclaration |
| 3 quater | Signature : initiales ou pseudonyme (jamais le nom complet : le fichier est suivi par git) | **initiales** dans `<données>/profil/signature.json` | profil, hors dépôt |
| 4 | Grille du courtier : envoyer les 8 questions ; garder le courtier actuel ou un courtier sans frais par ligne | **envoyer les 8 questions** (`plan questions`) | grille, hors déclaration |
| 5 | Statut de l'investisseur : personne physique résidente ? de quel pays ? | **personne physique résidente** (supposé par tout le module) | grille |
| 6 | Ce que j'accepte de risquer, taux de la réserve, durée | **« pas encore »** : la table de choix s'affiche | plan, hors déclaration |

À trancher plus tard : chemin vers l'argent réel pour une règle née après S1 ; seuils des feux (tous sans base
statistique) ; correction de la date de paiement projetée (accord écrit demandé) ; impôt sur les plus-values, taxe sur
le courtage et sur les frais annuels (à faire confirmer) ; taux et sûreté du placement d'attente (hors du champ de la
plate-forme) ; comparaison avec l'alternative simple (ne pas investir, ou un fonds actions de la place).

---

## 9. Signer la déclaration, avant le 01/12/2026

La signature se fait **dans le dépôt de développement** (là où `reports/` et `docs/` sont suivis par git), jamais sur le
serveur d'installation. Sur une installation, la commande refuse avec le code 2 : « La déclaration se signe dans le dépôt
de développement, puis se livre par un commit. »

### 9.1 La commande, telle qu'elle sera

La commande `suivi declarer` est ajoutée à la ligne de commande dans la phase suivante. Elle s'emploiera ainsi :

```
# 1. Écrire le projet de déclaration (articles 1 à 7 et PLAN, propositions par défaut) :
python -m brvm_alpha suivi declarer --modele > projet_declaration.json

# 2. Ouvrir projet_declaration.json et remplir le champ "reponse" de chaque article
#    (valeurs permises dans "choix" ; seuils « Hypothèse de travail » à valider ou corriger).

# 3. Choisir vos initiales (1 à 12 lettres, chiffres ou tirets), par exemple dans
#    <données>/profil/signature.json : {"signe_par": "AB"}

# 4. Signer et inscrire au registre des essais (dépôt de développement seulement) :
python -m brvm_alpha suivi declarer --fichier projet_declaration.json --signer AB \
    --registre --confirmer "J'INSCRIS AU REGISTRE"

# 5. Vérifier la chaîne :
python -m brvm_alpha suivi verifier

# 6. Commit AVANT le 01/12/2026 (sa date fait foi) :
git add brvm-alpha/reports/suivi_S2/declaration.jsonl brvm-alpha/reports/trials.parquet \
        brvm-alpha/configs/rendement_net.yaml brvm-alpha/docs/RENDEMENT_NET.md
git commit -m "[ADD] brvm-alpha: déclaration signée du suivi sur papier"
```

L'étape 4 écrit `reports/suivi_S2/declaration.jsonl` (une ligne par article) et ajoute trois à cinq lignes au registre
`reports/trials.parquet` : `S2-REF`, `S2-N`, `S2-PLAN`, et `S2-EC`, `S2-ED` si vous avez choisi l'option 1. Les 98
lignes existantes du registre ne changent pas (leur empreinte est vérifiée avant de remplacer le fichier).

### 9.2 Si la ligne de commande n'est pas encore prête

Les mêmes fonctions existent déjà dans le paquet. Depuis le dossier `brvm-alpha` du dépôt de développement :

```python
import json
from pathlib import Path
from brvm_alpha import paths
from brvm_alpha.suivi import declaration as D

# 1. Projet : à remplir à la main (champ "reponse"), puis relu.
Path("projet_declaration.json").write_text(json.dumps(D.modele(), ensure_ascii=False, indent=1), encoding="utf-8")
articles = json.loads(Path("projet_declaration.json").read_text(encoding="utf-8"))

# 2. Signature et inscription (chemins explicites, aucun défaut) :
dossier = paths.REPO_ROOT / "reports" / "suivi_S2"
D.signer(articles, "AB", dossier)
D.inscrire_au_registre(dossier, paths.REPO_ROOT / "reports" / "trials.parquet", confirmer=D.CONFIRMATION_REGISTRE)
print(D.verifier(dossier))
```

### 9.3 Les règles de la déclaration

- Une ligne ne se modifie jamais. Chaque ligne porte l'empreinte SHA-256 de la ligne précédente (`precedente`) et de son
  propre contenu (`empreinte`) : toute réécriture rompt la chaîne, `suivi verifier` le signale et le feu « Données »
  passe au rouge. Une chaîne rompue bloque tout ajout avant une décision humaine écrite.
- Une règle se remplace par une nouvelle ligne de type `remplace`, qui ne vaut que pour l'avenir.
- Une ligne signée après le 01/12/2026 est acceptée, mais ne vaut qu'à partir de la séance suivante ; la page Validation
  écrit « déclarée après le début du suivi ».
- Chaque ligne porte : l'empreinte des paramètres de la stratégie (`configs/strategy_v1.yaml`), celle des réglages du
  module (`configs/rendement_net.yaml`), celle de ce document, et le commit du code.
- Aucune donnée personnelle : la signature est faite d'initiales ou d'un pseudonyme, ou de l'empreinte d'un texte que
  vous seul connaissez (`{"signe_par_empreinte": "<SHA-256>"}`). Jamais un nom complet ni une adresse.
- Sans déclaration au 01/12/2026, seul le témoin `REF-S2` est suivi, et l'écran l'écrit.

---

## 10. Où vivent les fichiers

| Fichier | Où | Suivi par git |
|---|---|---|
| Déclaration signée | `reports/suivi_S2/declaration.jsonl` (dépôt de développement) | oui |
| Registre des essais | `reports/trials.parquet` (ajout de lignes seulement, sur votre commande) | oui |
| Signature choisie | `<données>/profil/signature.json` | **non** |
| Journal d'un portefeuille | `<données>/suivi/<nom>/` : `semaines.csv`, `empreintes.jsonl`, `operations.csv`, `positions.csv`, `anomalies.jsonl`, `controles.json` ; `carnet.jsonl` pour PLAN, MOI, E-C, E-D | **non** |

`<données>` est le dossier de données de l'installation (variable `BRVM_ALPHA_DONNEES`). Le suivi n'écrit jamais sous
`reports/` de lui-même : seule la déclaration, signée par vous, y entre.

---

## 11. Le journal de la semaine et le bulletin [§F10, §F12]

Chaque semaine (vendredi v ; t = dernière séance disponible au plus tard ce vendredi) :

- **valeur** = titres au cours + liquidités ; **argent engagé** = apports − retraits ; **écart** = valeur − argent
  engagé ;
- **pont, une seule base** : le cours de référence avant l'ordre. L'écart se décompose exactement, au franc près, en :
  effet des cours + dividendes reçus − frais d'achat et de vente (frais facturés et coût dans le prix) − frais annuels
  prélevés + intérêts ;
- **frais partis pour de bon** (frais de transaction et frais annuels) et **baisses de cours non vendues** (elles peuvent
  se retourner ou s'aggraver) ;
- **valeur de part** (rendement pondéré par le temps) : l'écart au marché ne dépend pas des dates de vos apports ;
- **dividendes à recevoir** (détachés, pas encore payés) : montrés à part, hors du pont ;
- une division d'actions ne crée aucune fausse perte ; un titre absent du bulletin est valorisé au dernier cours − 10 %.

Deux lancements la même semaine donnent une seule ligne. Une semaine déjà écrite n'est jamais réécrite : si son recalcul
diffère, une entrée « le passé a changé » est ajoutée et le feu « Données » passe au rouge.

Le bulletin porte trois feux : **Perte**, **Fuites**, **Données**. Vert : rien à faire. Orange : une revue. Rouge : une
décision écrite. **Un feu ouvre une revue, jamais une vente. Aucune de ces décisions n'a été testée.** Les seuils ont été
choisis après lecture de la période 2022-2026, sans base statistique ; leur utilité est inconnue.

---

## 12. Ce que le module ne fait pas

- Il ne promet aucun gain et ne présente aucune perte comme impossible.
- Il ne passe aucun ordre réel, ne vend jamais seul et ne transmet rien à un courtier.
- Il n'active aucune variante rejetée et ne change pas l'ordre de bataille par défaut.
- Il ne simule aucune règle sur l'échantillon S1 (jusqu'au 16/11/2022) ; il lit seulement les résultats publiés.
- Il ne lance ni `validate` ni `backtest`, et ne modifie ni `validation/runner.py`, ni le moteur, ni
  `configs/strategy_v1.yaml`.
- Il ne signe rien à votre place : la déclaration et l'inscription au registre ne se font que sur votre commande
  explicite, dans le dépôt de développement.
- Il ne classe aucun essai par son rendement avant un point d'étape.
- Il n'envoie aucune requête réseau ; vos données (grille, portefeuille, avis d'opéré, signature) restent dans le dossier
  de données local.
- Il ne connaît aucun taux de placement et ne conseille aucun placement.

> **Performance passée ≠ garantie. Aucun gain n'est garanti.**
