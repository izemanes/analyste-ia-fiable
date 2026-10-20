# Glossaire métier d'Atelier Nord

Règles de calcul appliquées partout dans le projet (dbt, couche sémantique, réponses de référence). La condition « tables brutes + glossaire » donne ce texte à l'IA.

- Commandes valides : statut DLV (livrée), SHP (expédiée) ou PAID (payée). Les statuts CXL (annulée) et TST (test interne) sont à exclure de TOUS les chiffres.
- Chiffre d'affaires (CA) = montant HT après remise, net des retours. Prix HT unitaire d'une ligne = unit_price_ttc * (1 - discount_pct) / (1 + vat_rate). Les retours (raw_refunds, via order_item_id) sont déduits à hauteur de quantity_returned * prix HT unitaire de la ligne, et rattachés à la date de la commande d'origine (pas à la date du remboursement).
- Marge brute = CA net HT - coût d'achat des unités conservées, soit (quantity - quantités retournées) * unit_cost_eur. Les produits retournés sont remis en stock. Ce n'est pas un bénéfice net. Taux de marge brute = marge brute / CA net HT.
- Panier moyen = CA net HT / nombre de commandes valides.
- Taux de retour = unités retournées / unités vendues (quantity), sur les commandes valides.
- Un client = une adresse e-mail normalisée (minuscules, sans espaces autour). Des doublons existent : même e-mail, customer_id différents. Clients actifs = nombre d'e-mails normalisés distincts ayant au moins une commande valide sur la période.
- Région du client : saisie libre, écrite de plusieurs façons (casse, accents, sigles comme IDF, ARA, PACA, HDF, N-Aquitaine). À ramener aux 8 régions officielles : Île-de-France, Auvergne-Rhône-Alpes, Provence-Alpes-Côte d'Azur, Occitanie, Nouvelle-Aquitaine, Bretagne, Hauts-de-France, Grand Est. Région vide ou non reconnue : « Inconnue ».
- Catégorie de produit : casse, accents et espaces variables. À ramener aux 6 catégories officielles : Décoration, Cuisine, Luminaires, Textile, Jardin, Petit électroménager.
- Périodes : année, trimestre et mois calendaires, d'après order_date.

## Dictionnaire des tables brutes

| Table | Contenu |
|---|---|
| raw_customers | Clients (avec doublons et régions mal écrites) |
| raw_products | Produits, coût d'achat, prix de liste TTC, catégories mal écrites |
| raw_orders | Commandes : date, statut (DLV, SHP, PAID, CXL, TST), canal (web, app, marketplace) |
| raw_order_items | Lignes de commande : quantité, prix TTC, remise, taux de TVA |
| raw_refunds | Retours : ligne concernée, quantité, date de remboursement |
