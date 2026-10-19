"""Réponses de référence (« gold ») calculées DIRECTEMENT sur les tables brutes.

Ce chemin est volontairement indépendant des modèles dbt : le CTE `vl` ci-dessous réécrit les
règles métier en SQL pur sur raw_*. Un test vérifie que les deux chemins donnent les mêmes chiffres.
"""
from __future__ import annotations

from .reference import category_case_sql, region_case_sql

GOLD_PRELUDE = f"""
WITH cust AS (
    SELECT customer_id,
           min(customer_id) OVER (PARTITION BY lower(trim(email))) AS customer_key,
           {region_case_sql('region')} AS region
    FROM raw_customers
),
ref AS (
    SELECT order_item_id, sum(quantity_returned) AS qty_ret
    FROM raw_refunds GROUP BY order_item_id
),
vl AS (
    SELECT
        i.order_item_id,
        o.order_id,
        o.order_date,
        strftime(o.order_date, '%Y-%m')                                   AS order_month,
        CAST(year(o.order_date) AS INTEGER)                               AS order_year,
        CAST(year(o.order_date) AS VARCHAR) || '-Q' || CAST(quarter(o.order_date) AS VARCHAR) AS order_quarter,
        c.customer_key,
        c.region,
        o.channel,
        p.product_name,
        {category_case_sql('p.category')}                                 AS category,
        i.quantity,
        coalesce(r.qty_ret, 0)                                            AS refunded_qty,
        (i.quantity - coalesce(r.qty_ret, 0))
            * i.unit_price_ttc * (1 - i.discount_pct) / (1 + i.vat_rate)  AS net_ht,
        (i.quantity - coalesce(r.qty_ret, 0)) * p.unit_cost_eur           AS cogs_net
    FROM raw_order_items i
    JOIN raw_orders o   ON o.order_id = i.order_id
    JOIN cust c         ON c.customer_id = o.customer_id
    JOIN raw_products p ON p.product_id = i.product_id
    LEFT JOIN ref r     ON r.order_item_id = i.order_item_id
    WHERE o.status IN ('DLV', 'SHP', 'PAID')
)
"""

# Expressions de référence, écrites à part du catalogue sémantique
GOLD_METRICS = {
    "revenue_ht": "SUM(net_ht)",
    "orders": "COUNT(DISTINCT order_id)",
    "units_sold": "SUM(quantity)",
    "aov_ht": "SUM(net_ht) / COUNT(DISTINCT order_id)",
    "gross_margin": "SUM(net_ht) - SUM(cogs_net)",
    "gross_margin_rate": "(SUM(net_ht) - SUM(cogs_net)) / SUM(net_ht)",
    "active_customers": "COUNT(DISTINCT customer_key)",
    "returned_units": "SUM(refunded_qty)",
    "return_rate": "CAST(SUM(refunded_qty) AS DOUBLE) / SUM(quantity)",
}


def _lit(v) -> str:
    if isinstance(v, (int, float)):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"


def gold_sql(metrics, dims=(), filters=(), order=None, limit=None) -> str:
    cols = [*dims, *[f"{GOLD_METRICS[m]} AS {m}" for m in metrics]]
    sql = GOLD_PRELUDE + f"SELECT {', '.join(cols)} FROM vl"
    conds = []
    for dim, op, val in filters:
        if op in ("in", "not in"):
            conds.append(f"{dim} {op.upper()} ({', '.join(_lit(x) for x in val)})")
        else:
            conds.append(f"{dim} {op} {_lit(val)}")
    if conds:
        sql += " WHERE " + " AND ".join(conds)
    if dims:
        sql += " GROUP BY " + ", ".join(dims)
    if order:
        sql += f" ORDER BY {order[0]} {order[1].upper()}"
    if limit:
        sql += f" LIMIT {limit}"
    return sql
