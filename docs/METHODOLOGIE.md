# Méthodologie et limites

## Question de recherche
Quand on branche une IA sur des données d'entreprise pour répondre à des questions en français, **quelle part des réponses est juste, et quelle part est fausse sans que personne ne s'en aperçoive ?** Trois conditions sont comparées pour isoler ce qui améliore la fiabilité : l'accès aux seules tables brutes, l'ajout d'un glossaire métier, l'usage d'une couche sémantique.

## Protocole
1. **Données** : jeu fictif déterministe (graine fixe), généré par `src/aia/generate.py`, avec des défauts réalistes et connus.
2. **Règles métier** : décrites dans `docs/GLOSSAIRE.md` (CA net HT, commandes valides, clients dédoublonnés, etc.).
3. **Questions** : 60 questions écrites en français naturel, réparties en simples (20), moyennes (20), difficiles (10) et abstention (10).
4. **Réponses de référence** : calculées en SQL pur sur les tables brutes (`gold.py`). Un test vérifie leur concordance avec les modèles dbt et la couche sémantique ; un autre vérifie qu'aucun classement ne tombe sur une égalité à la frontière du « top N ».
5. **Passage** : chaque question est posée à l'IA dans les trois conditions, température 0 (ou valeur par défaut si le modèle ne l'accepte pas). Plusieurs passages (`--runs 3`) mesurent la variabilité.
6. **Notation automatique** (`scoring.py`) : ordre des lignes et colonnes libre, colonnes supplémentaires tolérées, nombre de lignes exact, comptages exacts, montants à l'euro près, taux acceptés en pourcentage.
7. **Verdicts** : juste, abstention à raison, chiffre faux silencieux, erreur visible, abstention à tort.

## Pourquoi un test d'abstention
Dans une entreprise, un « je ne sais pas » coûte peu et un chiffre inventé coûte cher. Les 10 questions d'abstention (ambiguës ou hors périmètre) mesurent si l'IA devine. Toutes les conditions reçoivent la même consigne d'abstention, pour que la comparaison reste équitable.

## Limites connues
- **Données synthétiques.** Elles contiennent des pièges que j'ai choisis ; une vraie base en aurait d'autres. Le but est de comparer des conditions, pas de prédire un score en production.
- **Un seul auteur pour le banc d'essai.** Il peut contenir des biais de formulation. Les questions et les réponses de référence sont publiques et critiquables.
- **60 questions, c'est peu.** Les écarts de quelques points entre deux conditions ne sont pas significatifs ; seuls les écarts nets le sont. D'où les passages multiples.
- **Fournisseur d'accès.** Avec `--provider claude-code` (abonnement), le prompt système est remplacé par celui du projet et les outils sont désactivés, mais le modèle est choisi par Claude Code et la température n'est pas réglable : les résultats ne sont pas strictement comparables à ceux d'un appel API direct. Le rapport consigne le modèle observé.
- **Sensibilité aux prompts.** Un autre prompt peut changer les scores, surtout en conditions 1 et 2. Les prompts utilisés sont dans `src/aia/prompts.py`.
- **Dépendance au modèle et à la date.** Les résultats valent pour un modèle donné à une date donnée ; le rapport les consigne.
- **Abstention en partie subjective.** Certaines questions sont ambiguës par construction ; une autre équipe pourrait en trancher quelques-unes différemment.
- **Couche sémantique simplifiée.** Elle couvre un seul tableau de faits et des indicateurs agrégés. Elle ne gère pas les comparaisons de périodes ni les indicateurs sur plusieurs tables de faits.
- **La notation indulgente sur la forme** (colonnes en plus) pourrait accepter de rares réponses justes par hasard.

## Ce que ce projet ne prétend pas
Il ne prouve pas qu'une couche sémantique est toujours meilleure. Il fournit un moyen de **mesurer** si c'est le cas, dans quelles situations, et si une bonne documentation suffit.
