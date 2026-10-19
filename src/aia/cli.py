"""Ligne de commande : python -m aia.cli <commande>."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="aia", description="Analyste IA fiable : banc d'essai")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("generate", help="Génère les données brutes fictives et les charge dans DuckDB")
    ev = sub.add_parser("eval", help="Lance le banc d'essai avec l'API Anthropic (ANTHROPIC_API_KEY requise)")
    ev.add_argument("--modes", nargs="+", default=["raw", "raw_doc", "semantic"], choices=["raw", "raw_doc", "semantic"])
    ev.add_argument("--runs", type=int, default=1, help="nombre de passages (3 recommandé pour mesurer la variabilité)")
    ev.add_argument("--model", default=None, help="identifiant du modèle (défaut : variable AIA_MODEL ou claude-sonnet-5-5)")
    ev.add_argument("--workers", type=int, default=4)
    ev.add_argument("--limit", type=int, default=None, help="ne tester que les N premières questions (essai rapide)")
    ev.add_argument("--out", default=None)
    ev.add_argument("--provider", choices=["api", "claude-code"], default="api",
                    help="api : clé API Anthropic ; claude-code : ton abonnement Claude Pro/Max via Claude Code, sans clé API")
    ev.add_argument("--resume", action="store_true", help="reprendre un passage interrompu (avec --out du même dossier)")
    rp = sub.add_parser("report", help="Génère rapport.md et rapport.html à partir d'un dossier de résultats")
    rp.add_argument("run_dir")
    ask = sub.add_parser("ask", help="Pose une question à l'analyste (condition couche sémantique)")
    ask.add_argument("question")
    ask.add_argument("--mode", default="semantic", choices=["raw", "raw_doc", "semantic"])
    sub.add_parser("naive", help="Montre ce que coûtent les pièges avec des requêtes naïves (sans IA)")
    a = ap.parse_args(argv)
    try:
        return _dispatch(a)
    except RuntimeError as e:  # ex. clé API absente : message clair, sans trace technique
        print(f"Erreur : {e}", file=sys.stderr)
        return 1


def _dispatch(a) -> int:
    if a.cmd == "generate":
        from .generate import generate
        for t, n in generate().items():
            print(f"{t:18s} {n:>8,d} lignes")
    elif a.cmd == "eval":
        from .benchmark import QUESTIONS
        from .llm import AnthropicLLM
        from .report import write_report
        from .runner import run_benchmark
        if a.provider == "claude-code":
            from .llm import ClaudeCodeLLM
            llm = ClaudeCodeLLM(a.model)
        else:
            llm = AnthropicLLM(a.model)
        out = Path(a.out or f"results/run-{time.strftime('%Y%m%d-%H%M')}")
        qs = QUESTIONS[: a.limit] if a.limit else QUESTIONS
        if a.resume:
            if not a.out:                                   # sans --out : dernier passage connu
                runs_dirs = sorted(Path("results").glob("run-*/meta.json"))
                if not runs_dirs:
                    print("Aucun passage à reprendre (dossier results/run-* introuvable).", file=sys.stderr)
                    return 1
                out = runs_dirs[-1].parent
            meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
            a.runs, a.modes = meta["runs"], meta["modes"]
            qs = QUESTIONS[: meta["n_questions"]]
            print(f"Reprise du passage {out.name} ({meta.get('api_errors', '?')} appel(s) à refaire)")
        n = len(qs) * len(a.modes) * a.runs
        print(f"Modèle {llm.name} · {len(qs)} questions × {len(a.modes)} conditions × {a.runs} passage(s) = {n} appels")
        results = run_benchmark(llm, out, a.modes, a.runs, a.workers, qs, resume=a.resume)
        errs = [r for r in results if r["verdict"] == "api_error"]
        if errs:
            print(f"\n⚠️  {len(errs)} appel(s) sur {len(results)} ont échoué. Première erreur : {errs[0]['error']}", file=sys.stderr)
        if len(errs) == len(results):
            print("Aucun appel n'a abouti : pas de rapport. Avec une clé API : elle doit commencer par sk-ant- et avoir du crédit. "
                  "Avec Claude Code : lance `claude` une fois pour te connecter.", file=sys.stderr)
            return 1
        md, hp = write_report(out)
        print(f"\nRapport : {md}\nPage web : {hp}")
        if errs:
            print("\n⚠️  Passage INCOMPLET : relance avec --resume (ou le lanceur) pour refaire les appels échoués.", file=sys.stderr)
            return 2
    elif a.cmd == "report":
        from .report import write_report
        md, hp = write_report(a.run_dir)
        print(md, hp, sep="\n")
    elif a.cmd == "ask":
        from . import db
        from .llm import AnthropicLLM, parse_json
        from .prompts import system_prompt, user_prompt
        from .semantic import compile_spec
        comp = AnthropicLLM().complete(system_prompt(a.mode), user_prompt(a.question))
        parsed = parse_json(comp.text) or {}
        print("Réponse du modèle :", json.dumps(parsed, ensure_ascii=False, indent=2))
        if parsed.get("status") == "ok":
            con = db.connect()
            sql, params = compile_spec(parsed) if a.mode == "semantic" else (parsed["sql"], [])
            print("\nSQL exécuté :\n" + sql, "\n\nRésultat :")
            for row in db.run_select(con, sql, params)[:30]:
                print("  ", row)
    elif a.cmd == "naive":
        from . import naive_baseline
        print(naive_baseline.render_markdown(naive_baseline.run()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
