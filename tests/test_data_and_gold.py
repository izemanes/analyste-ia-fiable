"""Vérifie la cohérence des données, des modèles dbt et des réponses de référence."""
import pytest

from aia import db
from aia.benchmark import QUESTIONS
from aia.gold import GOLD_PRELUDE, gold_sql
from aia.scoring import results_match
from aia.semantic import compile_spec

ANSWERABLE = [q for q in QUESTIONS if q.expected == "answer"]


def test_benchmark_shape():
    levels = {}
    for q in QUESTIONS:
        levels[q.level] = levels.get(q.level, 0) + 1
    assert levels == {"simple": 20, "moyen": 20, "difficile": 10, "abstention": 10}
    assert len({q.id for q in QUESTIONS}) == 60


def test_traps_change_the_numbers(con):
    """Si les pièges ne changeaient pas les chiffres, le banc d'essai ne mesurerait rien."""
    true_rev = con.execute(GOLD_PRELUDE + "SELECT SUM(net_ht) FROM vl WHERE order_year = 2025").fetchone()[0]
    naive = con.execute("""SELECT SUM(i.quantity * i.unit_price_ttc) FROM raw_order_items i
                           JOIN raw_orders o USING (order_id) WHERE year(o.order_date) = 2025""").fetchone()[0]
    assert naive > true_rev * 1.25
    dup = con.execute("SELECT count(*) FROM raw_customers").fetchone()[0] - con.execute(
        "SELECT count(DISTINCT lower(trim(email))) FROM raw_customers").fetchone()[0]
    assert dup > 200
    assert con.execute("SELECT count(DISTINCT region) FROM raw_customers").fetchone()[0] > 20


@pytest.mark.parametrize("q", ANSWERABLE, ids=lambda q: q.id)
def test_gold_from_raw_equals_semantic_layer_on_dbt_marts(con, q):
    """Deux chemins indépendants (SQL pur sur tables brutes / dbt + compilateur) => mêmes chiffres."""
    gold_rows = db.run_select(con, q.gold_sql)
    assert gold_rows, "une question sans résultat ne prouve rien"
    sql, params = compile_spec(q.gold_spec)
    sem_rows = db.run_select(con, sql, params)
    assert results_match(gold_rows, sem_rows, q.ratio), (gold_rows[:3], sem_rows[:3])


@pytest.mark.parametrize("q", [q for q in ANSWERABLE if q.limit], ids=lambda q: q.id)
def test_rankings_have_no_tie_at_the_cut(con, q):
    """Un classement dont la frontière est à égalité aurait une « bonne réponse » arbitraire."""
    full = db.run_select(con, gold_sql(q.metrics, q.dims, q.filters, q.order, None))
    idx = len(q.dims)  # première colonne métrique
    values = [r[idx] for r in full]
    if len(values) > q.limit:
        assert values[q.limit - 1] != values[q.limit]
