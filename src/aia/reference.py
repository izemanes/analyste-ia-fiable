"""Référentiel métier partagé : valeurs canoniques et variantes « sales » des données sources.

Ces listes servent à (1) générer les données brutes, (2) produire les seeds dbt de
normalisation et (3) écrire les requêtes de référence du banc d'essai.
"""
from __future__ import annotations

# Fenêtre de données et date de référence donnée à l'assistant
DATA_START = "2023-01-01"
DATA_END = "2025-12-31"
REF_DATE = "2025-12-31"

# Régions : valeur canonique -> variantes que l'on trouve dans le système source
REGIONS: dict[str, list[str]] = {
    "Île-de-France": ["Île-de-France", "ile de france", "IDF", "Ile-de-France"],
    "Auvergne-Rhône-Alpes": ["Auvergne-Rhône-Alpes", "auvergne rhone alpes", "ARA", "Auvergne-Rhone-Alpes"],
    "Provence-Alpes-Côte d'Azur": ["Provence-Alpes-Côte d'Azur", "PACA", "provence alpes cote d'azur"],
    "Occitanie": ["Occitanie", "occitanie", "OCCITANIE"],
    "Nouvelle-Aquitaine": ["Nouvelle-Aquitaine", "nouvelle aquitaine", "N-Aquitaine"],
    "Bretagne": ["Bretagne", "bretagne"],
    "Hauts-de-France": ["Hauts-de-France", "hauts de france", "HDF"],
    "Grand Est": ["Grand Est", "grand est", "GRAND EST"],
}
REGION_WEIGHTS = [0.28, 0.14, 0.11, 0.11, 0.10, 0.08, 0.10, 0.08]
UNKNOWN_REGION = "Inconnue"

# Catégories de produits
CATEGORIES: dict[str, list[str]] = {
    "Décoration": ["Décoration", "decoration", "DECORATION", "Decoration "],
    "Cuisine": ["Cuisine", "cuisine", "CUISINE", "Cuisine "],
    "Luminaires": ["Luminaires", "luminaires", "LUMINAIRES"],
    "Textile": ["Textile", "textile", "TEXTILE "],
    "Jardin": ["Jardin", "jardin", "JARDIN"],
    "Petit électroménager": ["Petit électroménager", "petit electromenager", "Petit Electromenager"],
}
CATEGORY_WEIGHTS = [0.22, 0.20, 0.12, 0.18, 0.14, 0.14]
CATEGORY_VAT = {"Décoration": 0.20, "Cuisine": 0.20, "Luminaires": 0.20, "Textile": 0.20,
                "Jardin": 0.10, "Petit électroménager": 0.20}

CHANNELS = ["web", "app", "marketplace"]
# Statuts source : DLV livrée, SHP expédiée, PAID payée (à expédier), CXL annulée, TST commande de test
VALID_STATUSES = ("DLV", "SHP", "PAID")


def _norm(s: str) -> str:
    return s.strip().lower()


def region_map_rows() -> list[tuple[str, str]]:
    rows = {}
    for canon, variants in REGIONS.items():
        for v in variants + [canon]:
            rows[_norm(v)] = canon
    return sorted(rows.items())


def category_map_rows() -> list[tuple[str, str]]:
    rows = {}
    for canon, variants in CATEGORIES.items():
        for v in variants + [canon]:
            rows[_norm(v)] = canon
    return sorted(rows.items())


def _q(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def region_case_sql(col: str) -> str:
    """CASE SQL écrit à la main (chemin indépendant du seed dbt) pour les requêtes de référence."""
    whens = "\n".join(f"      WHEN {_q(k)} THEN {_q(v)}" for k, v in region_map_rows())
    return f"CASE lower(trim({col}))\n{whens}\n      ELSE {_q(UNKNOWN_REGION)} END"


def category_case_sql(col: str) -> str:
    whens = "\n".join(f"      WHEN {_q(k)} THEN {_q(v)}" for k, v in category_map_rows())
    return f"CASE lower(trim({col}))\n{whens}\n      ELSE 'Autre' END"
