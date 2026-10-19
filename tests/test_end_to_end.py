"""Tests du moteur d'évaluation avec des « modèles » factices : aucun appel réseau."""
import json
import tempfile

from aia.benchmark import BY_ID, QUESTIONS
from aia.llm import FakeLLM, parse_json
from aia.runner import evaluate_one, run_benchmark


def oracle(mode, text):
    q = next(x for x in QUESTIONS if x.text == text)
    if q.expected == "abstain":
        return json.dumps({"status": "clarify" if q.abstain_reason == "ambigu" else "unsupported", "message": "x"})
    if mode == "semantic":
        return json.dumps(q.gold_spec)
    return "```json\n" + json.dumps({"status": "ok", "sql": q.gold_sql}) + "\n```"


def test_oracle_scores_100_percent(con):
    with tempfile.TemporaryDirectory() as d:
        res = run_benchmark(FakeLLM(oracle), d, runs=1, workers=2, progress=lambda *_: None)
    assert len(res) == 3 * 60
    bad = [r for r in res if r["verdict"] not in ("correct", "correct_abstention")]
    assert not bad, bad[:3]


def test_failure_modes_are_classified(con):
    q = BY_ID["S01"]
    cases = {
        "pas du json": "invalid_output",
        json.dumps({"status": "ok", "sql": "SELECT 1"}): "wrong_result",
        json.dumps({"status": "ok", "sql": "SELECT nope FROM raw_orders"}): "execution_error",
        json.dumps({"status": "ok", "sql": "DROP TABLE raw_orders"}): "execution_error",
        json.dumps({"status": "clarify", "message": "?"}): "false_abstention",
    }
    for text, verdict in cases.items():
        rec = evaluate_one(FakeLLM(lambda m, t, _x=text: _x), "raw", q)
        assert rec["verdict"] == verdict, (text, rec)
    # Répondre un chiffre à une question sans réponse fiable = erreur « silencieuse »
    rec = evaluate_one(FakeLLM(lambda m, t: json.dumps({"status": "ok", "sql": "SELECT 1"})), "raw", BY_ID["A02"])
    assert rec["verdict"] == "overconfident"


def test_semantic_layer_rejects_unknown_metric(con):
    bad = json.dumps({"status": "ok", "metrics": ["benefice_net"]})
    rec = evaluate_one(FakeLLM(lambda m, t: bad), "semantic", BY_ID["S01"])
    assert rec["verdict"] == "execution_error"


def test_parse_json_tolerates_fences_and_text():
    assert parse_json('Voici : ```json\n{"a": "x}y", "b": 1}\n``` fin') == {"a": "x}y", "b": 1}
    assert parse_json("rien") is None


def test_api_failures_are_recorded_not_hidden(con):
    """Une clé invalide doit donner des « api_error », jamais de faux succès."""
    class Broken:
        name = "broken"

        def complete(self, system, user):
            raise RuntimeError("401 invalid x-api-key")

    rec = evaluate_one(Broken(), "semantic", BY_ID["S01"])
    assert rec["verdict"] == "api_error" and "401" in rec["error"]
