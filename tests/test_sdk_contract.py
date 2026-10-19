"""Test de contrat : le vrai SDK Anthropic parle à un faux serveur local.

Il détecte les incompatibilités entre mon code et la version du SDK installée (ex. un paramètre retiré),
sans clé ni réseau.
"""
import http.server
import json
import re
import tempfile
import threading

from aia.llm import AnthropicLLM
from aia.runner import run_benchmark
from tests.test_end_to_end import oracle


class FakeAnthropic(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        system = body["system"] if isinstance(body["system"], str) else "".join(b["text"] for b in body["system"])
        content = body["messages"][0]["content"]
        user = content if isinstance(content, str) else content[0]["text"]
        mode = re.search(r"Mode de travail : (\w+)", system).group(1)
        text = oracle(mode, user.removeprefix("Question : "))
        payload = json.dumps({
            "id": "msg_test", "type": "message", "role": "assistant", "model": body["model"],
            "content": [{"type": "text", "text": text}], "stop_reason": "end_turn", "stop_sequence": None,
            "usage": {"input_tokens": 120, "output_tokens": 40},
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


def test_real_sdk_against_local_fake_server(con, monkeypatch):
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FakeAnthropic)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "cle-de-test")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", f"http://127.0.0.1:{server.server_port}")
    try:
        llm = AnthropicLLM()
        with tempfile.TemporaryDirectory() as d:
            res = run_benchmark(llm, d, runs=1, workers=4, progress=lambda *_: None)
    finally:
        server.shutdown()
    assert len(res) == 180
    errors = [r for r in res if r["verdict"] == "api_error"]
    assert not errors, errors[:2]
    assert all(r["verdict"] in ("correct", "correct_abstention") for r in res)
    assert res[0]["input_tokens"] == 120
