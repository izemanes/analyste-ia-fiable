# Résultats : fiabilité de l'analyste IA

Modèle : `claude-code (claude-opus-5-5)` · 60 questions · 1 passage(s) · 2026-10-18 20:49

## Synthèse

| Condition | Score global | Réponses justes (50 questions) | Abstentions justes (10) | Chiffres faux silencieux | Erreurs visibles |
|---|---:|---:|---:|---:|---:|
| Tables brutes | **18 %** | 2 % | 100 % | 72 % | 0 % |
| Tables brutes + glossaire | **95 %** | 94 % | 100 % | 5 % | 0 % |
| Couche sémantique | **100 %** | 100 % | 100 % | 0 % | 0 % |

*Chiffre faux silencieux : l'IA livre un chiffre faux (ou invente une réponse) sans que rien ne signale le problème. C'est l'erreur la plus dangereuse en entreprise.*

## Réponses justes par niveau de difficulté

| Condition | Simples | Moyennes | Difficiles |
|---|---:|---:|---:|
| Tables brutes | 5 % | 0 % | 0 % |
| Tables brutes + glossaire | 95 % | 95 % | 90 % |
| Couche sémantique | 100 % | 100 % | 100 % |

## Réponses justes selon le piège de données en jeu

| Piège | Tables brutes | Tables brutes + glossaire | Couche sémantique |
|---|---:|---:|---:|
| Catégories mal saisies | 0 % | 92 % | 100 % |
| Clients en doublon | 0 % | 83 % | 100 % |
| Régions mal saisies | 0 % | 100 % | 100 % |
| Retours et remboursements | 3 % | 95 % | 100 % |
| Statuts (annulées, tests) | 2 % | 94 % | 100 % |
| TVA et remises | 3 % | 94 % | 100 % |

## Détail des verdicts

| Verdict | Tables brutes | Tables brutes + glossaire | Couche sémantique |
|---|---:|---:|---:|
| Réponse juste | 1 | 47 | 50 |
| Abstention à raison | 10 | 10 | 10 |
| Chiffre faux (silencieux) | 43 | 3 | 0 |
| Abstention à tort | 6 | 0 | 0 |

## Coût et rapidité

| Condition | Latence moyenne | Tokens en entrée | Tokens en sortie |
|---|---:|---:|---:|
| Tables brutes | 9.3 s | 120 | 43 757 |
| Tables brutes + glossaire | 7.6 s | 120 | 37 855 |
| Couche sémantique | 3.7 s | 120 | 6 176 |
