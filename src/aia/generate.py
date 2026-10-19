"""Génère les données brutes d'« Atelier Nord », boutique en ligne FICTIVE (déco, cuisine, jardin).

Les données imitent un export de système source réel, avec ses défauts :
statuts codés, commandes de test et annulées, TVA et remises par ligne, retours,
clients en doublon, régions et catégories écrites de plusieurs façons.
Tout est déterministe (graine fixe).
"""
from __future__ import annotations

import csv
import datetime as dt
import math
import random
from pathlib import Path

import duckdb

from .reference import (CATEGORIES, CATEGORY_VAT, CATEGORY_WEIGHTS, REGION_WEIGHTS, REGIONS,
                        category_map_rows, region_map_rows)

SEED = 42
START = dt.date(2023, 1, 1)
END = dt.date(2025, 12, 31)

RAW_DDL = """
CREATE TABLE raw_customers (
    customer_id  INTEGER,
    email        VARCHAR,
    created_at   DATE,
    region       VARCHAR
);
CREATE TABLE raw_products (
    product_id      INTEGER,
    sku             VARCHAR,
    product_name    VARCHAR,
    category        VARCHAR,
    unit_cost_eur   DOUBLE,
    list_price_ttc  DOUBLE
);
CREATE TABLE raw_orders (
    order_id     INTEGER,
    customer_id  INTEGER,
    order_date   DATE,
    status       VARCHAR,
    channel      VARCHAR
);
CREATE TABLE raw_order_items (
    order_item_id   INTEGER,
    order_id        INTEGER,
    product_id      INTEGER,
    quantity        INTEGER,
    unit_price_ttc  DOUBLE,
    discount_pct    DOUBLE,
    vat_rate        DOUBLE
);
CREATE TABLE raw_refunds (
    refund_id          INTEGER,
    order_item_id      INTEGER,
    quantity_returned  INTEGER,
    refund_date        DATE
);
"""

BASES = {
    "Décoration": ["Vase", "Miroir", "Cadre", "Bougeoir", "Coussin déco", "Horloge", "Plateau", "Photophore", "Sculpture", "Panier"],
    "Cuisine": ["Poêle", "Casserole", "Couteau chef", "Planche à découper", "Bol", "Théière", "Set de verres", "Moule", "Saladier", "Cocotte"],
    "Luminaires": ["Lampe de table", "Suspension", "Applique", "Lampadaire", "Lampe de chevet", "Guirlande", "Plafonnier", "Spot rail", "Lanterne", "Veilleuse"],
    "Textile": ["Plaid", "Housse de couette", "Rideau", "Tapis", "Nappe", "Serviette de bain", "Torchon", "Taie d'oreiller", "Jeté de lit", "Set de table"],
    "Jardin": ["Pot en terre", "Arrosoir", "Jardinière", "Salon de jardin", "Bac potager", "Brasero", "Hamac", "Lanterne solaire", "Sécateur", "Parasol"],
    "Petit électroménager": ["Bouilloire", "Grille-pain", "Blender", "Cafetière", "Robot pâtissier", "Friteuse à air", "Mixeur plongeant", "Centrifugeuse", "Gaufrier", "Balance connectée"],
}
PRICE_RANGE = {"Décoration": (15, 80), "Cuisine": (10, 90), "Luminaires": (25, 150),
               "Textile": (12, 70), "Jardin": (8, 60), "Petit électroménager": (30, 200)}
RETURN_PROB = {"Décoration": 0.04, "Cuisine": 0.04, "Luminaires": 0.06, "Textile": 0.11,
               "Jardin": 0.05, "Petit électroménager": 0.08}
SEASON = {1: 1.15, 2: 0.9, 3: 0.95, 4: 0.95, 5: 1.0, 6: 1.0, 7: 1.1, 8: 0.8, 9: 1.0, 10: 1.05, 11: 1.35, 12: 1.5}


def _write_csv(path: Path, header: list[str], rows: list[tuple]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def build_tables(seed: int = SEED) -> dict[str, tuple[list[str], list[tuple]]]:
    rng = random.Random(seed)
    canon_regions = list(REGIONS)
    canon_cats = list(CATEGORIES)

    # ---- Clients -------------------------------------------------------------------
    span = (END - dt.date(2022, 6, 1)).days
    customers, canon_of = [], {}
    n_base = 6500
    for i in range(1, n_base + 1):
        created = dt.date(2022, 6, 1) + dt.timedelta(days=int(span * rng.random() ** 0.7))
        canon = None if rng.random() < 0.03 else rng.choices(canon_regions, REGION_WEIGHTS)[0]
        region = None if canon is None else rng.choice(REGIONS[canon])
        customers.append([i, f"client{i}@exemple.fr", created, region])
        canon_of[i] = canon
    # Doublons : même personne, nouvel identifiant, e-mail écrit autrement
    next_id = n_base + 1
    for i in rng.sample(range(1, n_base + 1), int(n_base * 0.04)):
        _, email, created, _ = customers[i - 1]
        canon = canon_of[i]
        dup_email = rng.choice([email.upper(), " " + email, email.capitalize()])
        dup_created = min(END, created + dt.timedelta(days=rng.randint(30, 400)))
        region = None if canon is None else rng.choice(REGIONS[canon])
        customers.append([next_id, dup_email, dup_created, region])
        canon_of[next_id] = canon
        next_id += 1
    # Comptes internes de test
    qa_ids = []
    for k in range(1, 6):
        customers.append([next_id, f"qa{k}@atelier-nord.fr", dt.date(2022, 6, 1), None])
        qa_ids.append(next_id)
        next_id += 1

    # ---- Produits ------------------------------------------------------------------
    products, prod_by_cat, pid = [], {c: [] for c in canon_cats}, 1
    for cat in canon_cats:
        lo, hi = PRICE_RANGE[cat]
        for k in range(20):
            name = f"{BASES[cat][k % 10]} {'Classique' if k < 10 else 'Premium'}"
            price = rng.uniform(lo, hi) * (1.0 if k < 10 else 1.4)
            price = round(price) - 0.10
            cost = round(price / (1 + CATEGORY_VAT[cat]) * rng.uniform(0.40, 0.62), 2)
            products.append([pid, f"AN-{pid:04d}", name, rng.choice(CATEGORIES[cat]), cost, price])
            prod_by_cat[cat].append((pid, price))
            pid += 1

    # ---- Commandes, lignes, retours -------------------------------------------------
    orders, items, refunds = [], [], []
    order_id = item_id = refund_id = 1
    by_created = sorted(customers, key=lambda c: c[2])
    eligible, ptr, buyers = [], 0, []
    last_days_start = END - dt.timedelta(days=10)
    day = START
    while day <= END:
        while ptr < len(by_created) and by_created[ptr][2] <= day:
            if by_created[ptr][0] not in qa_ids:
                eligible.append(by_created[ptr][0])
            ptr += 1
        growth = 1.3 ** (day.year - 2023)
        mean = 14 * growth * SEASON[day.month] * (1.15 if day.weekday() >= 5 else 1.0)
        n = max(0, round(rng.gauss(mean, math.sqrt(mean))))
        for _ in range(n):
            cust = rng.choice(buyers) if buyers and rng.random() < 0.40 else rng.choice(eligible)
            buyers.append(cust)
            app_share = 0.18 + 0.07 * (day.year - 2023)
            channel = rng.choices(["web", "app", "marketplace"], [1 - app_share - 0.15, app_share, 0.15])[0]
            if day >= last_days_start:
                status = rng.choices(["SHP", "PAID", "CXL"], [0.5, 0.4, 0.1])[0]
            else:
                status = rng.choices(["DLV", "CXL", "SHP"], [0.91, 0.07, 0.02])[0]
            orders.append((order_id, cust, day, status, channel))
            promo_month = day.month in (1, 7, 11)
            for _ in range(rng.choices([1, 2, 3, 4], [0.45, 0.30, 0.17, 0.08])[0]):
                cat = rng.choices(canon_cats, CATEGORY_WEIGHTS)[0]
                p_id, list_price = rng.choice(prod_by_cat[cat])
                qty = 1 if cat == "Petit électroménager" else rng.choices([1, 2, 3], [0.78, 0.17, 0.05])[0]
                if promo_month:
                    disc = rng.choices([0, 0.1, 0.2, 0.3], [0.55, 0.2, 0.15, 0.1])[0]
                else:
                    disc = rng.choices([0, 0.1, 0.15], [0.88, 0.08, 0.04])[0]
                price = round(list_price * (1 + 0.03 * (day.year - 2023)), 2)
                items.append((item_id, order_id, p_id, qty, price, disc, CATEGORY_VAT[cat]))
                if status == "DLV" and rng.random() < RETURN_PROB[cat]:
                    r_date = day + dt.timedelta(days=rng.randint(5, 45))
                    if r_date <= END:
                        refunds.append((refund_id, item_id, rng.randint(1, qty), r_date))
                        refund_id += 1
                item_id += 1
            order_id += 1
        day += dt.timedelta(days=1)

    # Commandes de test (comptes internes) : annulent le sens des chiffres si on les garde
    for _ in range(80):
        d = START + dt.timedelta(days=rng.randint(0, (END - START).days))
        orders.append((order_id, rng.choice(qa_ids), d, "TST", "web"))
        for _ in range(rng.randint(1, 2)):
            p_id, list_price = rng.choice(prod_by_cat[rng.choice(canon_cats)])
            items.append((item_id, order_id, p_id, rng.choice([1, 1, 50]), list_price, 0.0, 0.20))
            item_id += 1
        order_id += 1

    return {
        "raw_customers": (["customer_id", "email", "created_at", "region"], [tuple(c) for c in customers]),
        "raw_products": (["product_id", "sku", "product_name", "category", "unit_cost_eur", "list_price_ttc"],
                         [tuple(p) for p in products]),
        "raw_orders": (["order_id", "customer_id", "order_date", "status", "channel"], orders),
        "raw_order_items": (["order_item_id", "order_id", "product_id", "quantity", "unit_price_ttc",
                             "discount_pct", "vat_rate"], items),
        "raw_refunds": (["refund_id", "order_item_id", "quantity_returned", "refund_date"], refunds),
    }


def generate(db_path: str = "warehouse.duckdb", csv_dir: str = "data/raw",
             seeds_dir: str = "dbt_project/seeds") -> dict[str, int]:
    tables = build_tables()
    csv_path = Path(csv_dir)
    for name, (header, rows) in tables.items():
        _write_csv(csv_path / f"{name}.csv", header, rows)
    _write_csv(Path(seeds_dir) / "region_map.csv", ["raw_value", "region"], region_map_rows())
    _write_csv(Path(seeds_dir) / "category_map.csv", ["raw_value", "category"], category_map_rows())

    Path(db_path).unlink(missing_ok=True)
    con = duckdb.connect(db_path)
    con.execute(RAW_DDL)
    for name in tables:
        con.execute(f"COPY {name} FROM '{(csv_path / f'{name}.csv').as_posix()}' (HEADER, DELIMITER ',')")
    counts = {n: con.execute(f"SELECT count(*) FROM {n}").fetchone()[0] for n in tables}
    con.close()
    return counts


if __name__ == "__main__":
    for table, n in generate().items():
        print(f"{table:18s} {n:>8,d} lignes")
