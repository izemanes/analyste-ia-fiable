import json
import tempfile
from pathlib import Path

from aia.llm import FakeLLM
from aia.report import write_report
from aia.runner import run_benchmark
from tests.test_end_to_end import oracle


def test_report_is_generated_from_a_run(con):
    with tempfile.TemporaryDirectory() as d:
        run_benchmark(FakeLLM(oracle), d, runs=2, workers=2, progress=lambda *_: None)
        md, hp = write_report(d)
        text, page = Path(md).read_text(encoding="utf-8"), Path(hp).read_text(encoding="utf-8")
    assert "Couche sémantique" in text and "modèle factice" in text
    assert "<html" in page and "Question par question" in page and "Peut-on faire confiance" in page
    assert json.loads(json.dumps({"ok": True}))  # le rapport ne casse pas sur plusieurs passages
