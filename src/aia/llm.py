"""Clients de modèle de langage : Anthropic (réel) et clients factices pour les tests."""
from __future__ import annotations

import inspect
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from typing import Callable

DEFAULT_MODEL = os.environ.get("AIA_MODEL", "claude-sonnet-5-5")


@dataclass
class Completion:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_s: float = 0.0


class AnthropicLLM:
    """Appelle l'API Anthropic. Nécessite la variable d'environnement ANTHROPIC_API_KEY."""

    provider = "api"

    def __init__(self, model: str | None = None, max_tokens: int = 1500):
        import anthropic  # import tardif : inutile pour les tests

        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError("ANTHROPIC_API_KEY n'est pas définie (voir README, section « Lancer l'évaluation »).")
        self._anthropic = anthropic
        self.client = anthropic.Anthropic(max_retries=6)
        self.model = model or DEFAULT_MODEL
        self.max_tokens = max_tokens
        # Les versions récentes du SDK n'acceptent plus « temperature » : on ne l'envoie que si c'est permis.
        self._send_temperature = "temperature" in inspect.signature(self.client.messages.create).parameters

    @property
    def name(self) -> str:
        return self.model

    def complete(self, system: str, user: str) -> Completion:
        kwargs = dict(model=self.model, max_tokens=self.max_tokens, system=system,
                      messages=[{"role": "user", "content": user}])
        t0 = time.time()
        try:
            resp = self.client.messages.create(**kwargs, **({"temperature": 0} if self._send_temperature else {}))
        except self._anthropic.BadRequestError as e:
            if "temperature" in str(e).lower():          # certains modèles n'acceptent pas ce paramètre
                self._send_temperature = False
                resp = self.client.messages.create(**kwargs)
            else:
                raise
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        return Completion(text, resp.usage.input_tokens, resp.usage.output_tokens, time.time() - t0)


class ClaudeCodeLLM:
    """Interroge le modèle via Claude Code (`claude -p`), avec l'abonnement Claude Pro/Max : pas de clé API.

    Pour rester proche d'un appel API direct : prompt système REMPLACÉ par celui du projet, aucun outil,
    aucune session conservée, aucun réglage ni mémoire utilisateur chargés, dossier de travail vide.
    La clé API est retirée de l'environnement, sinon Claude Code facturerait l'API au lieu de l'abonnement.
    Limites : le modèle est choisi par Claude Code (ou --model), la température n'est pas réglable et
    les quotas de l'abonnement s'appliquent.
    """

    provider = "claude-code"

    def __init__(self, model: str | None = None, claude_bin: str | None = None, timeout_s: int = 240):
        candidates = [claude_bin, shutil.which("claude"), os.path.expanduser("~/.local/bin/claude"),
                      os.path.expanduser("~/.claude/local/claude")]
        self.bin = next((c for c in candidates if c and os.path.exists(c)), None)
        if not self.bin:
            raise RuntimeError("Claude Code est introuvable. Installe-le (voir docs/PAS_A_PAS.md, « Sans clé API »).")
        self.model = model
        self.timeout_s = timeout_s
        self._seen_model: str | None = None
        self._workdir = tempfile.mkdtemp(prefix="aia-cc-")

    @property
    def name(self) -> str:
        return f"claude-code ({self._seen_model or self.model or 'modèle par défaut'})"

    def complete(self, system: str, user: str) -> Completion:
        cmd = [self.bin, "-p", user, "--system-prompt", system, "--tools", "", "--output-format", "json",
               "--no-session-persistence", "--setting-sources", "", "--disable-slash-commands", "--strict-mcp-config"]
        if self.model:
            cmd += ["--model", self.model]
        env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
        t0 = time.time()
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=self.timeout_s,
                                  cwd=self._workdir, env=env, stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Claude Code n'a pas répondu en {self.timeout_s} s") from None
        out = (proc.stdout or "").strip()
        try:
            data = json.loads(out)
        except json.JSONDecodeError:
            data = None
        if proc.returncode != 0 or (isinstance(data, dict) and data.get("is_error")):
            msg = (data or {}).get("result") if isinstance(data, dict) else None
            raise RuntimeError((msg or proc.stderr or out or "erreur inconnue")[-400:])
        if not isinstance(data, dict):
            return Completion(out, 0, 0, time.time() - t0)
        usage = data.get("usage") or {}
        used = data.get("modelUsage")
        if isinstance(used, dict) and used:
            self._seen_model = next(iter(used))
        return Completion(str(data.get("result", "")), int(usage.get("input_tokens", 0) or 0),
                          int(usage.get("output_tokens", 0) or 0), time.time() - t0)


class FakeLLM:
    """Client factice pour les tests : `responder(mode, question_text) -> str`."""

    name = "fake"

    def __init__(self, responder: Callable[[str, str], str]):
        self.responder = responder

    def complete(self, system: str, user: str) -> Completion:
        mode = re.search(r"Mode de travail : (\w+)", system).group(1)
        question = user.removeprefix("Question : ")
        return Completion(self.responder(mode, question), 100, 50, 0.01)


def parse_json(text: str) -> dict | None:
    """Extrait le premier objet JSON d'une réponse (tolère les blocs ```json)."""
    text = re.sub(r"```(?:json)?", "", text).strip()
    start = text.find("{")
    if start < 0:
        return None
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    return None
    return None
