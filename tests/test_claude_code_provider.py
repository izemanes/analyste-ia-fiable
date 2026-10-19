"""Fournisseur « Claude Code » (abonnement, sans clé API) et reprise d'un passage interrompu."""
import json
import tempfile
from pathlib import Path

from aia.benchmark import QUESTIONS
from aia.llm import ClaudeCodeLLM, FakeLLM
from aia.runner import run_benchmark
from tests.test_end_to_end import oracle

FAKE = str(Path(__file__).with_name("fake_claude.py"))
FEW = QUESTIONS[:2] + [q for q in QUESTIONS if q.id == "A03"]


def test_claude_code_provider_end_to_end(con, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ne-doit-pas-fuiter")
    llm = ClaudeCodeLLM(claude_bin=FAKE)
    with tempfile.TemporaryDirectory() as d:
        res = run_benchmark(llm, d, workers=2, questions=FEW, progress=lambda *_: None)
        meta = json.loads((Path(d) / "meta.json").read_text(encoding="utf-8"))
    assert len(res) == 9
    assert all(r["verdict"] in ("correct", "correct_abstention") for r in res), [r.get("error") for r in res][:2]
    assert res[0]["input_tokens"] == 321
    assert meta["provider"] == "claude-code" and "claude-sonnet-5-5" in meta["model"]


def test_claude_code_errors_are_reported(con, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_FAIL", "1")
    with tempfile.TemporaryDirectory() as d:
        res = run_benchmark(ClaudeCodeLLM(claude_bin=FAKE), d, workers=1, questions=FEW[:1], progress=lambda *_: None)
    assert {r["verdict"] for r in res} == {"api_error"}
    assert "Usage limit" in res[0]["error"]


def test_resume_redoes_only_failed_calls(con):
    class Broken:
        name = "broken"

        def complete(self, system, user):
            raise RuntimeError("limite atteinte")

    calls = []

    def counting(mode, text):
        calls.append((mode, text))
        return oracle(mode, text)

    with tempfile.TemporaryDirectory() as d:
        first = run_benchmark(Broken(), d, questions=FEW, progress=lambda *_: None)
        assert {r["verdict"] for r in first} == {"api_error"}
        second = run_benchmark(FakeLLM(counting), d, questions=FEW, progress=lambda *_: None, resume=True)
        assert len(calls) == 9 and len(second) == 9
        assert all(r["verdict"] in ("correct", "correct_abstention") for r in second)
        calls.clear()
        third = run_benchmark(FakeLLM(counting), d, questions=FEW, progress=lambda *_: None, resume=True)
        assert calls == [] and len(third) == 9                      # rien à refaire
        lines = sum(len((Path(d) / f"{m}.jsonl").read_text(encoding="utf-8").splitlines()) for m in ("raw", "raw_doc", "semantic"))
        assert lines == 9                                           # pas de doublons dans les fichiers


def test_incomplete_run_is_flagged_and_resumable_from_cli(con, monkeypatch, tmp_path):
    """Limite d'usage atteinte en cours de route : rapport marqué « incomplet », code retour 2, reprise par le CLI."""
    import os
    import subprocess
    import sys
    env = {**os.environ, "PATH": f"{Path(FAKE).parent}:{os.environ['PATH']}"}
    env.pop("ANTHROPIC_API_KEY", None)
    link = tmp_path / "bin"
    link.mkdir()
    (link / "claude").symlink_to(FAKE)
    env["PATH"] = f"{link}:{env['PATH']}"
    root = Path(FAKE).parents[1]
    base = [sys.executable, "-m", "aia.cli", "eval", "--provider", "claude-code", "--limit", "3", "--out", str(tmp_path / "results" / "run-test")]
    p1 = subprocess.run(base, cwd=root, env={**env, "FAKE_CLAUDE_FAIL": "1"}, capture_output=True, text=True)
    assert p1.returncode == 1                                       # rien n'a abouti : pas de rapport
    meta = json.loads((tmp_path / "results" / "run-test" / "meta.json").read_text(encoding="utf-8"))
    assert meta["api_errors"] == 9
    p2 = subprocess.run(base + ["--resume"], cwd=root, env=env, capture_output=True, text=True)
    assert p2.returncode == 0, p2.stderr
    meta = json.loads((tmp_path / "results" / "run-test" / "meta.json").read_text(encoding="utf-8"))
    assert meta["api_errors"] == 0
    assert "Passage incomplet" not in (tmp_path / "results" / "run-test" / "rapport.md").read_text(encoding="utf-8")


def test_report_warns_when_calls_failed(con):
    from aia.report import to_markdown
    rec = {"id": "S01", "level": "simple", "mode": "raw", "run": 1, "question": "?", "expected": "answer",
           "traps": ["statuts_commandes"], "verdict": "api_error", "error": "limite"}
    meta = {"model": "x", "n_questions": 1, "runs": 1, "date": "2026-10-18"}
    assert "Passage incomplet" in to_markdown(meta, [rec])
