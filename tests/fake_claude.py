#!/usr/bin/env python3
"""Faux exécutable `claude` pour les tests : imite `claude -p ... --output-format json` sans réseau."""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
sys.path.insert(0, os.path.join(HERE, ".."))

args = sys.argv[1:]
get = lambda flag: args[args.index(flag) + 1] if flag in args else None  # noqa: E731


def reply(payload: dict, code: int = 0):
    print(json.dumps(payload))
    sys.exit(code)


if args[:2] == ["auth", "status"]:
    print(json.dumps({"loggedIn": not os.environ.get("FAKE_CLAUDE_LOGGED_OUT")}, indent=2))
    sys.exit(0)
if "ANTHROPIC_API_KEY" in os.environ:                     # la clé ne doit jamais atteindre Claude Code
    reply({"type": "result", "is_error": True, "result": "ANTHROPIC_API_KEY présente : facturation API !"}, 1)
if os.environ.get("FAKE_CLAUDE_FAIL"):
    reply({"type": "result", "is_error": True, "result": "Usage limit reached"}, 1)
assert get("--tools") == "" and "--no-session-persistence" in args and get("--output-format") == "json"

from tests.test_end_to_end import oracle  # noqa: E402

mode = re.search(r"Mode de travail : (\w+)", get("--system-prompt")).group(1)
text = oracle(mode, get("-p").removeprefix("Question : "))
reply({"type": "result", "subtype": "success", "is_error": False, "result": text,
       "usage": {"input_tokens": 321, "output_tokens": 45}, "modelUsage": {"claude-sonnet-5-5": {}}})
