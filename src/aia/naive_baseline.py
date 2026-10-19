"""Requêtes « naïves » écrites À LA MAIN (ce n'est PAS une IA) : elles montrent, chiffres à l'appui,
ce que coûtent les pièges des données quand on lit les tables brutes sans connaître les règles métier.
Chaque requête fait l'erreur la plus courante : tous les statuts, prix TTC sans remise, pas de retours,
doublons clients, libellés bruts de régions et de catégories.
"""
from __future__ import annotations

from . import db
from .benchmark import BY_ID
from .scoring import results_match

NAIVE = {
    "S01": "SELECT SUM(i.quantity * i.unit_price_ttc) FROM raw_order_items i JOIN raw_orders o USING (order_id) WHERE year(o.order_date) = 2025",
    "S02": "SELECT COUNT(*) FROM raw_orders WHERE year(order_date) = 2024",
    "S04": "SELECT SUM(i.quantity * i.unit_price_ttc) / COUNT(DISTINCT o.order_id) FROM raw_order_items i JOIN raw_orders o USING (order_id) WHERE year(o.order_date) = 2025",
    "S05": "SELECT c.region, SUM(i.quantity * i.unit_price_ttc) FROM raw_order_items i JOIN raw_orders o USING (order_id) JOIN raw_customers c USING (customer_id) WHERE year(o.order_date) = 2025 GROUP BY c.region",
    "S06": "SELECT p.category, SUM(i.quantity * i.unit_price_ttc) FROM raw_order_items i JOIN raw_orders o USING (order_id) JOIN raw_products p USING (product_id) WHERE year(o.order_date) = 2025 GROUP BY p.category",
    "S07": "SELECT COUNT(DISTINCT customer_id) FROM raw_orders WHERE year(order_date) = 2025",
    "S08": "SELECT SUM(i.quantity * (i.unit_price_ttc - p.unit_cost_eur)) FROM raw_order_items i JOIN raw_orders o USING (order_id) JOIN raw_products p USING (product_id) WHERE year(o.order_date) = 2024",
    "S09": "SELECT (SELECT SUM(quantity_returned) FROM raw_refunds) * 1.0 / (SELECT SUM(quantity) FROM raw_order_items)",
}
WHY = {
    "S01": "toutes les commandes (annulées et tests), prix TTC, remises et retours ignorés",
    "S02": "commandes annulées et de test comptées",
    "S04": "même CA gonflé, divisé par toutes les commandes",
    "S05": "26 libellés de région différents au lieu de 9, CA gonflé",
    "S06": "libellés de catégories dupliqués (casse, accents), CA gonflé",
    "S07": "doublons clients comptés plusieurs fois, annulées et tests inclus",
    "S08": "TTC au lieu de HT, remises et retours ignorés, tout statut",
    "S09": "retours de toutes les années rapportés à toutes les ventes",
}


def run() -> list[dict]:
    con = db.connect()
    out = []
    for qid, sql in NAIVE.items():
        q = BY_ID[qid]
        gold = db.run_select(con, q.gold_sql)
        got = db.run_select(con, sql)
        row = {"id": qid, "question": q.text, "ok": results_match(gold, got, q.ratio), "why": WHY[qid],
               "n_gold": len(gold), "n_got": len(got)}
        if len(gold) == 1 and len(got) == 1 and isinstance(gold[0][0], (int, float)):
            row["gold"], row["naive"] = float(gold[0][0]), float(got[0][0])
            row["ecart_pct"] = (row["naive"] / row["gold"] - 1) * 100
        out.append(row)
    con.close()
    return out


def _fmt(v: float) -> str:
    if abs(v) < 1:
        s = f"{v:.4f}"
    elif v == int(v):
        s = f"{int(v):,}"
    else:
        s = f"{v:,.2f}"
    return s.replace(",", " ").replace(".", ",")


def render_markdown(rows: list[dict]) -> str:
    lines = ["| Question | Vraie valeur | Requête naïve | Écart | Pourquoi |", "|---|---:|---:|---:|---|"]
    for r in rows:
        if "gold" in r:
            gv, nv = _fmt(r["gold"]), _fmt(r["naive"])
            ecart = f"{r['ecart_pct']:+.0f} %"
        else:
            gv, nv, ecart = f"{r['n_gold']} lignes", f"{r['n_got']} lignes", "—"
        lines.append(f"| {r['question']} | {gv} | {nv} | {ecart} | {r['why']} |")
    wrong = sum(not r["ok"] for r in rows)
    lines.append(f"\n**{wrong} réponses fausses sur {len(rows)}** avec des requêtes naïves écrites à la main (pas une IA).")
    return "\n".join(lines)
