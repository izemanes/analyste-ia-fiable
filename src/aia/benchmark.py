"""Banc d'essai : 60 questions métier en français, avec réponse de référence.

Niveaux : simple (20), moyen (20), difficile (10), abstention (10).
Les questions d'« abstention » n'ont PAS de bonne réponse chiffrée : un bon analyste doit demander
une précision ou dire que la donnée n'existe pas, plutôt que d'inventer un chiffre.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .gold import gold_sql


@dataclass
class Question:
    id: str
    level: str                      # simple | moyen | difficile | abstention
    text: str
    expected: str = "answer"        # answer | abstain
    abstain_reason: str = ""        # ambigu | hors_perimetre
    metrics: list[str] = field(default_factory=list)
    dims: list[str] = field(default_factory=list)
    filters: list[tuple] = field(default_factory=list)
    order: tuple | None = None
    limit: int | None = None
    ratio: bool = False             # accepte un taux exprimé en % (x100)

    @property
    def gold_sql(self) -> str | None:
        if self.expected != "answer":
            return None
        return gold_sql(self.metrics, self.dims, self.filters, self.order, self.limit)

    @property
    def gold_spec(self) -> dict | None:
        if self.expected != "answer":
            return None
        spec = {"status": "ok", "metrics": self.metrics, "dimensions": self.dims,
                "filters": [{"dimension": d, "op": o, "value": v} for d, o, v in self.filters]}
        if self.order:
            spec["order_by"] = {"field": self.order[0], "direction": self.order[1]}
        if self.limit:
            spec["limit"] = self.limit
        return spec

    @property
    def traps(self) -> list[str]:
        """Pièges de données que la question met en jeu (déduits de ses indicateurs et axes)."""
        t = set()
        if self.expected != "answer":
            return ["abstention"]
        if {"revenue_ht", "aov_ht", "gross_margin", "gross_margin_rate"} & set(self.metrics):
            t.add("tva_remises")
        if {"revenue_ht", "aov_ht", "gross_margin", "gross_margin_rate", "return_rate", "returned_units"} & set(self.metrics):
            t.add("retours")
        if "active_customers" in self.metrics:
            t.add("doublons_clients")
        if "region" in self.dims or any(f[0] == "region" for f in self.filters):
            t.add("regions_sales")
        if "category" in self.dims or any(f[0] == "category" for f in self.filters):
            t.add("categories_sales")
        t.add("statuts_commandes")
        return sorted(t)


Y = lambda y: ("order_year", "=", y)  # noqa: E731
_A, _M, _D, _X = "simple", "moyen", "difficile", "abstention"


def _q(id, level, text, metrics, dims=(), filters=(), order=None, limit=None, ratio=False):
    return Question(id, level, text, "answer", "", list(metrics), list(dims), list(filters), order, limit, ratio)


def _abst(id, text, reason):
    return Question(id, _X, text, "abstain", reason)


QUESTIONS: list[Question] = [
    # ------------------------------------------------------------------ simples
    _q("S01", _A, "Quel est le chiffre d'affaires de 2025 ?", ["revenue_ht"], filters=[Y(2025)]),
    _q("S02", _A, "Combien de commandes ont été passées en 2024 ?", ["orders"], filters=[Y(2024)]),
    _q("S03", _A, "Quel est le chiffre d'affaires par année ?", ["revenue_ht"], ["order_year"]),
    _q("S04", _A, "Quel est le panier moyen en 2025 ?", ["aov_ht"], filters=[Y(2025)]),
    _q("S05", _A, "Quel est le chiffre d'affaires par région en 2025 ?", ["revenue_ht"], ["region"], [Y(2025)]),
    _q("S06", _A, "Quel est le chiffre d'affaires par catégorie de produits en 2025 ?", ["revenue_ht"], ["category"], [Y(2025)]),
    _q("S07", _A, "Combien de clients actifs avons-nous eu en 2025 ?", ["active_customers"], filters=[Y(2025)]),
    _q("S08", _A, "Quelle est la marge brute totale en 2024 ?", ["gross_margin"], filters=[Y(2024)]),
    _q("S09", _A, "Quel est le taux de retour global en 2025 ?", ["return_rate"], filters=[Y(2025)], ratio=True),
    _q("S10", _A, "Combien d'unités ont été vendues par canal en 2025 ?", ["units_sold"], ["channel"], [Y(2025)]),
    _q("S11", _A, "Quel est le chiffre d'affaires du canal app en 2025 ?", ["revenue_ht"], filters=[Y(2025), ("channel", "=", "app")]),
    _q("S12", _A, "Quel est le chiffre d'affaires par trimestre en 2024 ?", ["revenue_ht"], ["order_quarter"], [Y(2024)]),
    _q("S13", _A, "Combien de commandes par canal en 2023 ?", ["orders"], ["channel"], [Y(2023)]),
    _q("S14", _A, "Quel est le chiffre d'affaires de la catégorie Luminaires en 2024 ?", ["revenue_ht"], filters=[Y(2024), ("category", "=", "Luminaires")]),
    _q("S15", _A, "Quel est le chiffre d'affaires réalisé en Bretagne en 2025 ?", ["revenue_ht"], filters=[Y(2025), ("region", "=", "Bretagne")]),
    _q("S16", _A, "Combien de clients actifs par année ?", ["active_customers"], ["order_year"]),
    _q("S17", _A, "Quel est le panier moyen par canal en 2025 ?", ["aov_ht"], ["channel"], [Y(2025)]),
    _q("S18", _A, "Quelle est la marge brute par catégorie en 2025 ?", ["gross_margin"], ["category"], [Y(2025)]),
    _q("S19", _A, "Quel est le taux de marge brute global en 2025 ?", ["gross_margin_rate"], filters=[Y(2025)], ratio=True),
    _q("S20", _A, "Quel est le chiffre d'affaires mensuel de 2024 ?", ["revenue_ht"], ["order_month"], [Y(2024)]),
    # ------------------------------------------------------------------ moyens
    _q("M01", _M, "Quelles sont les 3 régions qui font le plus de chiffre d'affaires en 2025 ?", ["revenue_ht"], ["region"], [Y(2025)], ("revenue_ht", "desc"), 3),
    _q("M02", _M, "Quels sont les 5 produits qui génèrent le plus de chiffre d'affaires en 2025 ?", ["revenue_ht"], ["product_name"], [Y(2025)], ("revenue_ht", "desc"), 5),
    _q("M03", _M, "Quel est le chiffre d'affaires par région et par canal en 2025 ?", ["revenue_ht"], ["region", "channel"], [Y(2025)]),
    _q("M04", _M, "Quel est le chiffre d'affaires de la catégorie Textile par trimestre en 2024 ?", ["revenue_ht"], ["order_quarter"], [Y(2024), ("category", "=", "Textile")]),
    _q("M05", _M, "Quelle catégorie a le taux de retour le plus élevé en 2025 ?", ["return_rate"], ["category"], [Y(2025)], ("return_rate", "desc"), 1, True),
    _q("M06", _M, "Quelle région a le panier moyen le plus élevé en 2025 ?", ["aov_ht"], ["region"], [Y(2025)], ("aov_ht", "desc"), 1),
    _q("M07", _M, "Combien de clients actifs par région en 2025 ?", ["active_customers"], ["region"], [Y(2025)]),
    _q("M08", _M, "Quelle est la marge brute par canal et par année ?", ["gross_margin"], ["channel", "order_year"]),
    _q("M09", _M, "Combien de commandes par mois en 2025 sur la marketplace ?", ["orders"], ["order_month"], [Y(2025), ("channel", "=", "marketplace")]),
    _q("M10", _M, "Quelles sont les 3 catégories avec la plus forte marge brute en 2024 ?", ["gross_margin"], ["category"], [Y(2024)], ("gross_margin", "desc"), 3),
    _q("M11", _M, "Quel est le taux de marge brute par catégorie en 2025 ?", ["gross_margin_rate"], ["category"], [Y(2025)], ratio=True),
    _q("M12", _M, "Quel est le chiffre d'affaires de décembre 2024 ?", ["revenue_ht"], filters=[("order_month", "=", "2024-12")]),
    _q("M13", _M, "Quel est le chiffre d'affaires du quatrième trimestre 2025 en Île-de-France ?", ["revenue_ht"], filters=[("order_quarter", "=", "2025-Q4"), ("region", "=", "Île-de-France")]),
    _q("M14", _M, "Combien de commandes ont été passées via l'app en Auvergne-Rhône-Alpes en 2024 ?", ["orders"], filters=[Y(2024), ("channel", "=", "app"), ("region", "=", "Auvergne-Rhône-Alpes")]),
    _q("M15", _M, "Quel est le taux de retour par canal en 2025 ?", ["return_rate"], ["channel"], [Y(2025)], ratio=True),
    _q("M16", _M, "Quelle catégorie a le plus d'unités retournées en 2025 ?", ["returned_units"], ["category"], [Y(2025)], ("returned_units", "desc"), 1),
    _q("M17", _M, "Quel est le chiffre d'affaires mensuel de la catégorie Jardin en 2025 ?", ["revenue_ht"], ["order_month"], [Y(2025), ("category", "=", "Jardin")]),
    _q("M18", _M, "Quel est le chiffre d'affaires de 2025 hors marketplace ?", ["revenue_ht"], filters=[Y(2025), ("channel", "!=", "marketplace")]),
    _q("M19", _M, "Combien de clients actifs ont commandé via l'app en 2025 ?", ["active_customers"], filters=[Y(2025), ("channel", "=", "app")]),
    _q("M20", _M, "Combien de commandes par mois au premier trimestre 2025 ?", ["orders"], ["order_month"], [("order_quarter", "=", "2025-Q1")]),
    # ------------------------------------------------------------------ difficiles
    _q("D01", _D, "Quelle région a la meilleure marge brute en 2025, et combien ?", ["gross_margin"], ["region"], [Y(2025)], ("gross_margin", "desc"), 1),
    _q("D02", _D, "Quelles sont les 3 catégories avec le plus fort taux de retour en 2024 ?", ["return_rate"], ["category"], [Y(2024)], ("return_rate", "desc"), 3, True),
    _q("D03", _D, "Donne-moi le chiffre d'affaires par catégorie et par année.", ["revenue_ht"], ["category", "order_year"]),
    _q("D04", _D, "Quels sont les 5 produits de la catégorie Cuisine avec la meilleure marge brute en 2025 ?", ["gross_margin"], ["product_name"], [Y(2025), ("category", "=", "Cuisine")], ("gross_margin", "desc"), 5),
    _q("D05", _D, "Quel est le taux de marge brute par canal et par trimestre en 2025 ?", ["gross_margin_rate"], ["channel", "order_quarter"], [Y(2025)], ratio=True),
    _q("D06", _D, "Quel est le chiffre d'affaires par région sur le dernier trimestre disponible ?", ["revenue_ht"], ["region"], [("order_quarter", "=", "2025-Q4")]),
    _q("D07", _D, "Quel est le panier moyen mensuel en Île-de-France en 2025 ?", ["aov_ht"], ["order_month"], [Y(2025), ("region", "=", "Île-de-France")]),
    _q("D08", _D, "Combien de clients actifs par trimestre en 2025 ?", ["active_customers"], ["order_quarter"], [Y(2025)]),
    _q("D09", _D, "Quelles sont les 3 régions avec le plus de clients actifs en 2024 ?", ["active_customers"], ["region"], [Y(2024)], ("active_customers", "desc"), 3),
    _q("D10", _D, "Quelle est la marge brute des Luminaires vendus sur la marketplace en 2024 ?", ["gross_margin"], filters=[Y(2024), ("category", "=", "Luminaires"), ("channel", "=", "marketplace")]),
    # ------------------------------------------------------------------ abstention
    _abst("A01", "Quels sont nos meilleurs clients ?", "ambigu"),
    _abst("A02", "Combien avons-nous gagné l'an dernier ?", "ambigu"),
    _abst("A03", "Quelle est la satisfaction client moyenne ?", "hors_perimetre"),
    _abst("A04", "Combien de visiteurs avons-nous eu sur le site en 2025 ?", "hors_perimetre"),
    _abst("A05", "Quel est notre bénéfice net en 2025 ?", "hors_perimetre"),
    _abst("A06", "Prévois le chiffre d'affaires mensuel de 2026.", "hors_perimetre"),
    _abst("A07", "Quel est le stock restant pour chaque produit ?", "hors_perimetre"),
    _abst("A08", "Est-ce que les ventes ont bien marché ?", "ambigu"),
    _abst("A09", "Quel est le chiffre d'affaires par vendeur ?", "hors_perimetre"),
    _abst("A10", "Donne-moi les chiffres du mois dernier.", "ambigu"),
]

BY_ID = {q.id: q for q in QUESTIONS}
assert len(QUESTIONS) == 60 and len(BY_ID) == 60
