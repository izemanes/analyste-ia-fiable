"""Exécute le banc d'essai : question -> modèle -> SQL -> résultat -> verdict."""
from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from . import db
from .benchmark import QUESTIONS, Question
from .llm import parse_json
from .prompts import MODES, system_prompt, user_prompt
from .scoring import results_match
from .semantic import SemanticError, compile_spec

ABSTAIN = ("clarify", "unsupported")
_lock = threading.Lock()


def _preview(rows: list[tuple], n: int = 6) -> list[list[Any]]:
    return [[(round(c, 4) if isinstance(c, float) else (str(c) if not isinstance(c, (int, str, type(None))) else c))
             for c in r] for r in rows[:n]]


def evaluate_one(llm, mode: str, q: Question, run: int = 1) -> dict[str, Any]:
    """Pose une question au modèle dans une condition donnée et note la réponse."""
    rec: dict[str, Any] = {"id": q.id, "level": q.level, "mode": mode, "run": run, "question": q.text,
                           "expected": q.expected, "traps": q.traps, "model": getattr(llm, "name", "?")}
    con = db.connect()
    try:
        comp = llm.complete(system_prompt(mode), user_prompt(q.text))
        rec.update(latency_s=round(comp.latency_s, 2), input_tokens=comp.input_tokens,
                   output_tokens=comp.output_tokens, response=comp.text)
        parsed = parse_json(comp.text)
        status = (parsed or {}).get("status")
        rec["status"] = status
        if parsed is None or status not in ("ok", *ABSTAIN):
            rec["verdict"] = "invalid_output"
            return rec

        if status in ABSTAIN:
            rec["message"] = parsed.get("message", "")
            rec["verdict"] = "correct_abstention" if q.expected == "abstain" else "false_abstention"
            return rec
        if q.expected == "abstain":
            rec["verdict"] = "overconfident"            # a répondu un chiffre alors qu'il fallait s'abstenir
            rec["answer_given"] = parsed.get("sql") or parsed
            return rec

        try:
            if mode == "semantic":
                sql, params = compile_spec(parsed)
                rec["spec"] = parsed
            else:
                sql, params = parsed.get("sql", ""), []
            rec["sql"] = sql
            rows = db.run_select(con, sql, params)
        except (SemanticError, db.QueryRejected) as e:
            rec.update(verdict="execution_error", error=str(e)[:300])
            return rec
        except Exception as e:  # erreur SQL (colonne inconnue, syntaxe...)
            rec.update(verdict="execution_error", error=f"{type(e).__name__}: {str(e)[:300]}")
            return rec

        gold_rows = db.run_select(con, q.gold_sql)
        ok = results_match(gold_rows, rows, q.ratio)
        rec.update(verdict="correct" if ok else "wrong_result", got_preview=_preview(rows),
                   gold_preview=_preview(gold_rows), n_rows=len(rows))
        return rec
    except Exception as e:  # erreur d'API ou imprévue : on la consigne, on ne plante pas tout le run
        rec.update(verdict="api_error", error=f"{type(e).__name__}: {str(e)[:300]}")
        return rec
    finally:
        con.close()


def run_benchmark(llm, out_dir: str | Path, modes=MODES, runs: int = 1, workers: int = 4,
                  questions: list[Question] | None = None, progress=print, resume: bool = False) -> list[dict]:
    """Lance toutes les (condition, question, passage). Avec resume=True, reprend un passage interrompu :
    les réponses déjà obtenues sont conservées, celles qui avaient échoué (erreur d'API) sont refaites."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    questions = questions or QUESTIONS
    results: list[dict] = []
    if resume:
        for m in modes:
            f = out / f"{m}.jsonl"
            if f.exists():
                results += [r for r in (json.loads(x) for x in f.read_text(encoding="utf-8").splitlines() if x.strip())
                            if r["verdict"] != "api_error"]
    done_keys = {(r["mode"], r["id"], r["run"]) for r in results}
    tasks = [(m, q, r) for m in modes for r in range(1, runs + 1) for q in questions
             if (m, q.id, r) not in done_keys]
    files = {m: (out / f"{m}.jsonl").open("w", encoding="utf-8") for m in modes}
    for r in results:                       # on réécrit les réponses conservées
        files[r["mode"]].write(json.dumps(r, ensure_ascii=False) + "\n")
    done, t0 = 0, time.time()
    if resume and results:
        progress(f"  Reprise : {len(results)} réponses déjà obtenues, {len(tasks)} à faire")
    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(evaluate_one, llm, m, q, r) for m, q, r in tasks]
            for fut in as_completed(futures):
                rec = fut.result()
                with _lock:
                    files[rec["mode"]].write(json.dumps(rec, ensure_ascii=False) + "\n")
                    files[rec["mode"]].flush()
                results.append(rec)
                done += 1
                if done % 20 == 0 or done == len(tasks):
                    progress(f"  {done}/{len(tasks)} questions traitées ({time.time() - t0:.0f}s)")
    finally:
        for f in files.values():
            f.close()
    (out / "meta.json").write_text(json.dumps({
        "model": getattr(llm, "name", "?"), "modes": list(modes), "runs": runs,
        "n_questions": len(questions), "provider": getattr(llm, "provider", "api"),
        "api_errors": sum(r["verdict"] == "api_error" for r in results), "date": time.strftime("%Y-%m-%d %H:%M"),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return results
