import pytest

from aia.scoring import results_match
from aia.semantic import SemanticError, compile_spec


def test_scoring_tolerances():
    assert results_match([(1160301.35,)], [(1160301,)])                 # arrondi à l'euro toléré
    assert not results_match([(1160301.35,)], [(1160000,)])             # vrai écart
    assert not results_match([(3995,)], [(3996,)])                      # un comptage doit être exact
    assert results_match([(0.0494,)], [(4.94,)], ratio_ok=True)         # pourcentage accepté pour un taux
    assert not results_match([(0.0494,)], [(4.94,)], ratio_ok=False)
    assert results_match([("Textile", 0.089)], [("textile", 0.089, 42)], ratio_ok=True)  # colonne en plus, casse
    assert not results_match([("a", 1), ("b", 2)], [("a", 1)])          # nombre de lignes exact
    assert results_match([("a", 1), ("b", 2)], [("b", 2), ("a", 1)])    # ordre libre


def test_compiler_rejects_bad_requests():
    ok = {"metrics": ["orders"]}
    assert compile_spec(ok)[0].startswith("SELECT COUNT(DISTINCT order_id) AS orders")
    for bad in [
        {"metrics": []},
        {"metrics": ["benefice_net"]},
        {"metrics": ["orders"], "dimensions": ["vendeur"]},
        {"metrics": ["orders"], "filters": [{"dimension": "region", "op": "=", "value": "Normandie"}]},
        {"metrics": ["orders"], "filters": [{"dimension": "order_year", "op": "=", "value": "2025; DROP"}]},
        {"metrics": ["orders"], "filters": [{"dimension": "order_date", "op": "like", "value": "2025"}]},
        {"metrics": ["orders"], "order_by": {"field": "revenue_ht"}},
        {"metrics": ["orders"], "limit": 0},
    ]:
        with pytest.raises(SemanticError):
            compile_spec(bad)


def test_values_are_parameters_not_concatenated():
    sql, params = compile_spec({"metrics": ["orders"], "filters": [{"dimension": "channel", "op": "=", "value": "app"}]})
    assert "app" not in sql and params == ["app"]


def test_integer_given_as_text_is_accepted_but_not_injection():
    sql, params = compile_spec({"metrics": ["orders"], "filters": [{"dimension": "order_year", "op": "=", "value": "2025"}]})
    assert params == [2025]
