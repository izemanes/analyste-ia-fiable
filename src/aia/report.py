"""Transforme les résultats d'un passage (fichiers .jsonl) en rapport Markdown et en page HTML autonome."""
from __future__ import annotations

import html
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean

MODE_LABELS = {"raw": "Tables brutes", "raw_doc": "Tables brutes + glossaire", "semantic": "Couche sémantique"}
MODE_ORDER = ["raw", "raw_doc", "semantic"]
LEVELS = ["simple", "moyen", "difficile"]
SILENT = {"wrong_result", "overconfident"}              # un chiffre faux (ou inventé) livré avec aplomb
VISIBLE = {"execution_error", "invalid_output", "api_error"}   # l'utilisateur voit que ça a échoué


def pct(x: float, digits: int = 0) -> str:
    return f"{x * 100:.{digits}f}".replace(".", ",") + " %"


def load(run_dir: str | Path) -> tuple[dict, list[dict]]:
    d = Path(run_dir)
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    recs = []
    for m in MODE_ORDER:
        f = d / f"{m}.jsonl"
        if f.exists():
            recs += [json.loads(line) for line in f.read_text(encoding="utf-8").splitlines() if line.strip()]
    return meta, recs


def _per_run(recs: list[dict], pred) -> tuple[float, float, float]:
    """Moyenne, min et max d'une proportion calculée run par run."""
    by_run = defaultdict(list)
    for r in recs:
        by_run[r["run"]].append(r)
    vals = [pred(rs) for rs in by_run.values() if rs]
    return (mean(vals), min(vals), max(vals)) if vals else (0.0, 0.0, 0.0)


def summarize(recs: list[dict]) -> dict:
    out: dict = {}
    for mode in MODE_ORDER:
        rs = [r for r in recs if r["mode"] == mode]
        if not rs:
            continue
        ans = [r for r in rs if r["expected"] == "answer"]
        abst = [r for r in rs if r["expected"] == "abstain"]
        acc = lambda x: sum(r["verdict"] == "correct" for r in x) / len(x) if x else 0  # noqa: E731
        s = {
            "n": len(rs),
            "answerable": _per_run(ans, acc),
            "abstention": _per_run(abst, lambda x: sum(r["verdict"] == "correct_abstention" for r in x) / len(x)),
            "global": _per_run(rs, lambda x: sum(r["verdict"] in ("correct", "correct_abstention") for r in x) / len(x)),
            "silent": _per_run(rs, lambda x: sum(r["verdict"] in SILENT for r in x) / len(x)),
            "visible": _per_run(rs, lambda x: sum(r["verdict"] in VISIBLE for r in x) / len(x)),
            "false_abstention": _per_run(rs, lambda x: sum(r["verdict"] == "false_abstention" for r in x) / len(x)),
            "latency": mean(r.get("latency_s", 0) for r in rs),
            "tokens_in": sum(r.get("input_tokens", 0) for r in rs),
            "tokens_out": sum(r.get("output_tokens", 0) for r in rs),
            "by_level": {lv: acc([r for r in ans if r["level"] == lv]) for lv in LEVELS},
            "verdicts": defaultdict(int),
        }
        for r in rs:
            s["verdicts"][r["verdict"]] += 1
        traps = defaultdict(list)
        for r in ans:
            for t in r["traps"]:
                traps[t].append(r["verdict"] == "correct")
        s["by_trap"] = {t: (sum(v) / len(v), len(v)) for t, v in sorted(traps.items())}
        out[mode] = s
    return out


TRAP_LABELS = {
    "statuts_commandes": "Statuts (annulées, tests)", "tva_remises": "TVA et remises",
    "retours": "Retours et remboursements", "doublons_clients": "Clients en doublon",
    "regions_sales": "Régions mal saisies", "categories_sales": "Catégories mal saisies",
}
VERDICT_LABELS = {
    "correct": "Réponse juste", "correct_abstention": "Abstention à raison",
    "wrong_result": "Chiffre faux (silencieux)", "overconfident": "A répondu au lieu de s'abstenir (silencieux)",
    "execution_error": "Erreur d'exécution", "invalid_output": "Sortie illisible", "api_error": "Erreur d'API",
    "false_abstention": "Abstention à tort",
}


def _fmt_range(t: tuple[float, float, float], multi: bool) -> str:
    return pct(t[0]) + (f" ({pct(t[1])} à {pct(t[2])})" if multi and abs(t[1] - t[2]) > 1e-9 else "")


def to_markdown(meta: dict, recs: list[dict]) -> str:
    S, multi = summarize(recs), meta.get("runs", 1) > 1
    L = [f"# Résultats : fiabilité de l'analyste IA", "",
         f"Modèle : `{meta['model']}` · {meta['n_questions']} questions · {meta['runs']} passage(s) · {meta['date']}", ""]
    if meta["model"] == "fake":
        L += ["> ⚠️ Résultats de démonstration produits par un modèle factice : ils servent à vérifier le moteur, pas à mesurer une IA.", ""]
    n_api = sum(r["verdict"] == "api_error" for r in recs)
    if n_api:
        L += [f"> ⚠️ **Passage incomplet** : {n_api} appel(s) ont échoué (limite d'usage, connexion…). Ces chiffres ne sont pas définitifs : "
              "relance avec `--resume` pour refaire uniquement les appels échoués.", ""]
    L += ["## Synthèse", "", "| Condition | Score global | Réponses justes (50 questions) | Abstentions justes (10) | Chiffres faux silencieux | Erreurs visibles |",
          "|---|---:|---:|---:|---:|---:|"]
    for m, s in S.items():
        L.append(f"| {MODE_LABELS[m]} | **{_fmt_range(s['global'], multi)}** | {_fmt_range(s['answerable'], multi)} | "
                 f"{_fmt_range(s['abstention'], multi)} | {_fmt_range(s['silent'], multi)} | {_fmt_range(s['visible'], multi)} |")
    L += ["", "*Chiffre faux silencieux : l'IA livre un chiffre faux (ou invente une réponse) sans que rien ne signale le problème. C'est l'erreur la plus dangereuse en entreprise.*",
          "", "## Réponses justes par niveau de difficulté", "", "| Condition | Simples | Moyennes | Difficiles |", "|---|---:|---:|---:|"]
    for m, s in S.items():
        L.append(f"| {MODE_LABELS[m]} | " + " | ".join(pct(s["by_level"][lv]) for lv in LEVELS) + " |")
    L += ["", "## Réponses justes selon le piège de données en jeu", "",
          "| Piège | " + " | ".join(MODE_LABELS[m] for m in S) + " |", "|---|" + "---:|" * len(S)]
    traps = sorted({t for s in S.values() for t in s["by_trap"]})
    for t in traps:
        L.append(f"| {TRAP_LABELS.get(t, t)} | " + " | ".join(
            pct(S[m]["by_trap"][t][0]) if t in S[m]["by_trap"] else "—" for m in S) + " |")
    L += ["", "## Détail des verdicts", "", "| Verdict | " + " | ".join(MODE_LABELS[m] for m in S) + " |", "|---|" + "---:|" * len(S)]
    for v, lab in VERDICT_LABELS.items():
        if any(S[m]["verdicts"].get(v) for m in S):
            L.append(f"| {lab} | " + " | ".join(str(S[m]["verdicts"].get(v, 0)) for m in S) + " |")
    L += ["", "## Coût et rapidité", "", "| Condition | Latence moyenne | Tokens en entrée | Tokens en sortie |", "|---|---:|---:|---:|"]
    for m, s in S.items():
        L.append(f"| {MODE_LABELS[m]} | {s['latency']:.1f} s | {s['tokens_in']:,} | {s['tokens_out']:,} |".replace(",", " "))
    return "\n".join(L) + "\n"


# ----------------------------------------------------------------------------- HTML
CSS = """
:root{--bg:#FAFAFD;--surface:#fff;--soft:#F1EEFF;--ink:#1C1B29;--muted:#656478;--line:#E6E4F0;--violet:#6B4EFF;--violet-ink:#4B2FD6;--ok:#1B8A5A;--bad:#C23B3B;--warn:#B7791F;
 box-sizing:border-box;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#14131C;--surface:#1C1B27;--soft:#262240;--ink:#F1F0FA;--muted:#A5A4B8;--line:#2D2B3D;--violet:#8F78FF;--violet-ink:#B3A3FF;--ok:#4CC38A;--bad:#F07A7A;--warn:#E3B35C;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#14131C;--surface:#1C1B27;--soft:#262240;--ink:#F1F0FA;--muted:#A5A4B8;--line:#2D2B3D;--violet:#8F78FF;--violet-ink:#B3A3FF;--ok:#4CC38A;--bad:#F07A7A;--warn:#E3B35C;color-scheme:dark}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:980px;margin:0 auto;padding:40px 24px 80px}h1{font-size:2rem;letter-spacing:-.02em;margin:0 0 6px}h2{font-size:1.25rem;margin:44px 0 14px}
.meta{color:var(--muted);margin:0 0 24px}.banner{background:var(--soft);border:1px solid var(--violet);padding:12px 16px;border-radius:12px;margin-bottom:24px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:16px}.card{background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:20px}
.card h3{margin:0 0 4px;font-size:1rem}.big{font-size:2.4rem;font-weight:800;letter-spacing:-.03em;color:var(--violet-ink)}.sub{color:var(--muted);font-size:.9rem}
.bar{height:10px;border-radius:99px;background:var(--soft);overflow:hidden;margin:10px 0 4px}.bar i{display:block;height:100%;background:var(--violet)}
table{width:100%;border-collapse:collapse;background:var(--surface);border:1px solid var(--line);border-radius:12px;overflow:hidden;font-size:.94rem}
th,td{padding:10px 14px;text-align:left;border-bottom:1px solid var(--line)}th{background:var(--soft);font-weight:600}td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
tr:last-child td{border-bottom:0}.scroll{overflow-x:auto}.ok{color:var(--ok);font-weight:700}.bad{color:var(--bad);font-weight:700}.warn{color:var(--warn);font-weight:700}
details{background:var(--surface);border:1px solid var(--line);border-radius:12px;margin:8px 0;padding:10px 16px}summary{cursor:pointer;font-weight:500}
pre{white-space:pre-wrap;word-break:break-word;background:var(--soft);padding:10px 12px;border-radius:8px;font-size:.82rem;margin:6px 0}
.legend{color:var(--muted);font-size:.88rem;margin-top:10px}
"""


def _mark(v: str) -> str:
    if v in ("correct", "correct_abstention"):
        return '<span class="ok">✓</span>'
    if v in SILENT:
        return '<span class="bad">✗ silencieux</span>'
    if v == "false_abstention":
        return '<span class="warn">abstention</span>'
    return '<span class="warn">erreur</span>'


def to_html(meta: dict, recs: list[dict]) -> str:
    S, multi = summarize(recs), meta.get("runs", 1) > 1
    e = html.escape
    parts = [f'<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">'
             f'<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
             f"<title>Analyste IA fiable : résultats</title><style>{CSS}</style></head><body><div class=\"wrap\">",
             "<h1>Peut-on faire confiance à un analyste IA ?</h1>",
             f'<p class="meta">Modèle <b>{e(meta["model"])}</b> · {meta["n_questions"]} questions métier · {meta["runs"]} passage(s) · {e(meta["date"])}</p>']
    if meta["model"] == "fake":
        parts.append('<div class="banner">⚠️ Démonstration avec un modèle factice : ces résultats vérifient le moteur, ils ne mesurent aucune IA.</div>')
    n_api = sum(r["verdict"] == "api_error" for r in recs)
    if n_api:
        parts.append(f'<div class="banner">⚠️ Passage incomplet : {n_api} appel(s) ont échoué (limite d\'usage, connexion…). '
                     "Ces chiffres ne sont pas définitifs : relance avec <code>--resume</code>.</div>")
    parts.append('<div class="cards">')
    for m, s in S.items():
        g = s["global"][0]
        parts.append(f'<div class="card"><h3>{e(MODE_LABELS[m])}</h3><div class="big">{pct(g)}</div>'
                     f'<div class="bar"><i style="width:{g * 100:.0f}%"></i></div>'
                     f'<div class="sub">Chiffres faux silencieux : <b>{pct(s["silent"][0])}</b> · erreurs visibles : {pct(s["visible"][0])}</div></div>')
    parts.append("</div>")
    parts.append('<p class="legend">Score global = réponses justes + abstentions justes, sur 60 questions. Un chiffre faux silencieux est livré avec aplomb, sans alerte : c\'est le risque principal en entreprise.</p>')

    parts.append("<h2>Par niveau de difficulté</h2><div class=\"scroll\"><table><tr><th>Condition</th><th class=\"n\">Simples</th><th class=\"n\">Moyennes</th><th class=\"n\">Difficiles</th><th class=\"n\">Abstentions</th></tr>")
    for m, s in S.items():
        parts.append(f"<tr><td>{e(MODE_LABELS[m])}</td>" + "".join(f'<td class="n">{pct(s["by_level"][lv])}</td>' for lv in LEVELS)
                     + f'<td class="n">{_fmt_range(s["abstention"], multi)}</td></tr>')
    parts.append("</table></div>")

    traps = sorted({t for s in S.values() for t in s["by_trap"]})
    parts.append("<h2>Selon le piège de données</h2><div class=\"scroll\"><table><tr><th>Piège</th>"
                 + "".join(f'<th class="n">{e(MODE_LABELS[m])}</th>' for m in S) + "</tr>")
    for t in traps:
        parts.append(f"<tr><td>{e(TRAP_LABELS.get(t, t))}</td>" + "".join(
            f'<td class="n">{pct(S[m]["by_trap"][t][0]) if t in S[m]["by_trap"] else "—"}</td>' for m in S) + "</tr>")
    parts.append("</table></div>")

    parts.append("<h2>Détail des verdicts</h2><div class=\"scroll\"><table><tr><th>Verdict</th>" + "".join(f'<th class="n">{e(MODE_LABELS[m])}</th>' for m in S) + "</tr>")
    for v, lab in VERDICT_LABELS.items():
        if any(S[m]["verdicts"].get(v) for m in S):
            parts.append(f"<tr><td>{e(lab)}</td>" + "".join(f'<td class="n">{S[m]["verdicts"].get(v, 0)}</td>' for m in S) + "</tr>")
    parts.append("</table></div>")

    # Détail question par question (premier passage)
    parts.append("<h2>Question par question</h2>")
    first = defaultdict(dict)
    for r in recs:
        if r["run"] == 1:
            first[r["id"]][r["mode"]] = r
    for qid in sorted(first):
        rows = first[qid]
        any_r = next(iter(rows.values()))
        marks = " ".join(f'{e(MODE_LABELS[m])} {_mark(rows[m]["verdict"])}' for m in MODE_ORDER if m in rows)
        body = []
        for m in MODE_ORDER:
            r = rows.get(m)
            if not r:
                continue
            detail = r.get("sql") or json.dumps(r.get("spec") or r.get("message") or r.get("answer_given") or "", ensure_ascii=False)
            extra = ""
            if r["verdict"] == "wrong_result":
                extra = f'<div class="sub">Obtenu : {e(json.dumps(r.get("got_preview"), ensure_ascii=False))}<br>Attendu : {e(json.dumps(r.get("gold_preview"), ensure_ascii=False))}</div>'
            elif r.get("error"):
                extra = f'<div class="sub">Erreur : {e(r["error"])}</div>'
            body.append(f"<b>{e(MODE_LABELS[m])}</b> : {e(VERDICT_LABELS.get(r['verdict'], r['verdict']))}<pre>{e(str(detail))}</pre>{extra}")
        parts.append(f"<details><summary><b>{qid}</b> · {e(any_r['question'])} &nbsp; {marks}</summary>{''.join(body)}</details>")
    parts.append("</div></body></html>")
    return "".join(parts)


def write_report(run_dir: str | Path) -> tuple[Path, Path]:
    meta, recs = load(run_dir)
    d = Path(run_dir)
    md, hp = d / "rapport.md", d / "rapport.html"
    md.write_text(to_markdown(meta, recs), encoding="utf-8")
    hp.write_text(to_html(meta, recs), encoding="utf-8")
    return md, hp
