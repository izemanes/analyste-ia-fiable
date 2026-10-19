"""Prompts des trois conditions testées.

  raw      : tables brutes + 3 lignes d'exemple, AUCUNE règle métier (cas « on branche l'IA sur la base »)
  raw_doc  : idem + glossaire complet des règles métier (cas « on documente bien »)
  semantic : l'IA ne voit que le catalogue d'indicateurs et choisit quoi demander ; le SQL est généré
             par le compilateur (cas « couche sémantique »)

Les trois conditions reçoivent la même consigne d'abstention : ne pas deviner si la question est
ambiguë ou hors périmètre.
"""
from __future__ import annotations

from .db import connect
from .generate import RAW_DDL
from .reference import DATA_END, DATA_START, REF_DATE
from .semantic import render_catalog_for_prompt

MODES = ("raw", "raw_doc", "semantic")

HEADER = """Mode de travail : {mode}
Tu es l'analyste de données d'Atelier Nord, une boutique en ligne française (décoration, cuisine, luminaires, textile, jardin, petit électroménager).
Les données couvrent de {start} à {end}. Nous sommes le {ref} : « cette année » = 2025, « l'an dernier » = 2024, « le dernier trimestre disponible » = 2025-Q4.
Réponds en français. Réponds UNIQUEMENT par un objet JSON, sans texte autour."""

ABSTENTION = """RÈGLE DE FIABILITÉ : ne devine jamais. Si la question est trop ambiguë pour être traitée de façon fiable (critère ou période non précisés, plusieurs sens possibles) réponds {{"status": "clarify", "message": "<la précision à demander>"}}. Si l'information demandée n'existe pas dans les données réponds {{"status": "unsupported", "message": "<ce qui manque>"}}."""

GLOSSARY = """RÈGLES MÉTIER (à appliquer systématiquement) :
- Commandes valides : statut DLV (livrée), SHP (expédiée) ou PAID (payée). Les statuts CXL (annulée) et TST (test interne) sont à exclure de TOUS les chiffres.
- Chiffre d'affaires (CA) = montant HT après remise, net des retours. Prix HT unitaire d'une ligne = unit_price_ttc * (1 - discount_pct) / (1 + vat_rate). Les retours (raw_refunds, via order_item_id) sont déduits à hauteur de quantity_returned * prix HT unitaire de la ligne, et rattachés à la date de la commande d'origine (pas à la date du remboursement).
- Marge brute = CA net HT - coût d'achat des unités conservées, soit (quantity - quantités retournées) * unit_cost_eur. Les produits retournés sont remis en stock. Ce n'est pas un bénéfice net. Taux de marge brute = marge brute / CA net HT.
- Panier moyen = CA net HT / nombre de commandes valides.
- Taux de retour = unités retournées / unités vendues (quantity), sur les commandes valides.
- Un client = une adresse e-mail normalisée (minuscules, sans espaces autour). Des doublons existent : même e-mail, customer_id différents. Clients actifs = nombre d'e-mails normalisés distincts ayant au moins une commande valide sur la période.
- Région du client : saisie libre, écrite de plusieurs façons (casse, accents, sigles comme IDF, ARA, PACA, HDF, N-Aquitaine). À ramener aux 8 régions officielles : Île-de-France, Auvergne-Rhône-Alpes, Provence-Alpes-Côte d'Azur, Occitanie, Nouvelle-Aquitaine, Bretagne, Hauts-de-France, Grand Est. Région vide ou non reconnue : « Inconnue ».
- Catégorie de produit : casse, accents et espaces variables. À ramener aux 6 catégories officielles : Décoration, Cuisine, Luminaires, Textile, Jardin, Petit électroménager.
- Périodes : année, trimestre et mois calendaires, d'après order_date."""

RAW_FORMAT = """FORMAT DE RÉPONSE :
{{"status": "ok", "sql": "<une seule requête SELECT en SQL DuckDB>"}}
ou {{"status": "clarify", "message": "..."}} ou {{"status": "unsupported", "message": "..."}}
La requête doit être en lecture seule (SELECT ou WITH ... SELECT) et renvoyer directement la réponse à la question."""

SEMANTIC_FORMAT = """FORMAT DE RÉPONSE :
{{"status": "ok",
  "metrics": ["<indicateur>", ...],
  "dimensions": ["<axe>", ...],
  "filters": [{{"dimension": "<axe>", "op": "=", "value": ...}}, ...],
  "order_by": {{"field": "<indicateur ou axe demandé>", "direction": "desc"}},
  "limit": <entier>}}
ou {{"status": "clarify", "message": "..."}} ou {{"status": "unsupported", "message": "..."}}
Opérateurs de filtre : =, !=, >, >=, <, <=, in, not in (valeur = liste), between (valeur = [début, fin]).
« dimensions » : les axes de regroupement (vide si un seul chiffre global est demandé). « order_by » et « limit » servent aux classements (« les 3 meilleures », « la région avec le plus »). Omets les clés inutiles.
N'utilise QUE les indicateurs et axes du catalogue ; n'invente rien."""


def _sample_rows(n: int = 3) -> str:
    con = connect()
    out = []
    for table in ("raw_customers", "raw_products", "raw_orders", "raw_order_items", "raw_refunds"):
        cur = con.execute(f"SELECT * FROM {table} ORDER BY 1 LIMIT {n}")
        cols = [d[0] for d in cur.description]
        rows = "\n".join("  " + " | ".join(str(v) for v in r) for r in cur.fetchall())
        out.append(f"-- {table} : {' | '.join(cols)}\n{rows}")
    con.close()
    return "\n".join(out)


_cache: dict[str, str] = {}


def system_prompt(mode: str) -> str:
    if mode in _cache:
        return _cache[mode]
    head = HEADER.format(mode=mode, start=DATA_START, end=DATA_END, ref=REF_DATE)
    if mode == "raw":
        body = f"SCHÉMA DE LA BASE (DuckDB) :\n{RAW_DDL.strip()}\n\nEXEMPLES DE LIGNES :\n{_sample_rows()}\n\n{ABSTENTION}\n\n{RAW_FORMAT}"
    elif mode == "raw_doc":
        body = (f"SCHÉMA DE LA BASE (DuckDB) :\n{RAW_DDL.strip()}\n\nEXEMPLES DE LIGNES :\n{_sample_rows()}\n\n"
                f"{GLOSSARY}\n\n{ABSTENTION}\n\n{RAW_FORMAT}")
    elif mode == "semantic":
        body = f"{render_catalog_for_prompt()}\n\n{ABSTENTION}\n\n{SEMANTIC_FORMAT}"
    else:
        raise ValueError(f"mode inconnu : {mode}")
    _cache[mode] = f"{head}\n\n{body}"
    return _cache[mode]


def user_prompt(question: str) -> str:
    return f"Question : {question}"
