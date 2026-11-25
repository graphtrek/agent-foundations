"""Text evaluation of an eval run, written by the Luna model.

After a run, every failed result is handed to the model together with the case
definition and the agent description files (``architectures/<id>/NN_<agent>.md``)
of the architecture that failed. The model says what went wrong and which agent
file should change - and exactly what to change in it. The report is saved next
to the run's JSON (``logs/evals/<stamp>.md``) and shown in a popup on eval.html.
"""

from __future__ import annotations

import dataclasses
import os
from pathlib import Path
from typing import Any

from agents.profile_loader import profile_dir
from app_context import BASE_CONFIG, OPENROUTER_API_KEY
from model_util import get_openrouter_model

REPORT_MODEL = os.environ.get("EVAL_REPORT_MODEL", "openai/gpt-6-luna")
REPORT_MAX_TOKENS = 3000
MAX_FAILURES_PER_ARCH = 12  # keeps the prompt bounded on a very bad run
REPLY_LIMIT = 1200

SYSTEM_PROMPT_HU = """\
Te egy LLM-ügynökrendszerek tesztelésére szakosodott minőségbiztosítási mérnök vagy.
Egy bankfiókos tisztviselői chat asszisztens automatikus tesztjeinek eredményét kapod: az esetek
leírását, a determinisztikus ellenőrzések eredményét, a hívott tool-okat, az asszisztens válaszát,
valamint az érintett architektúra agent leíró (Markdown) fájljainak teljes szövegét.

Írj magyar nyelvű, tömör szöveges kiértékelést Markdownban, pontosan ezzel a szerkezettel:

## Összegzés
2-4 mondat: hány futás volt hibás, és mi a közös ok (ha van).

## Hibák és javaslatok
Minden hibás eset (architektúra / eset azonosító) külön alcím (###) alatt:
- **Mi ment rosszul:** melyik ellenőrzés bukott, és a tool-hívásokból / válaszból mi látszik az okról.
- **Javítandó agent leíró:** a fájl relatív útvonala (pl. `03_router/01_branch_coordinator.md`) és miért
  pont az (nem a modell hibája, hanem melyik utasítás hiányzik, kétértelmű vagy ellentmondó).
- **Pontos módosítás:** konkrét szöveg, amit be kell szúrni vagy le kell cserélni (idézd a jelenlegi
  mondatot, ha cserélni kell, és add meg az újat kódblokkban).

## Nem prompttal javítható
Ha egy hiba nem a leírás hibája (hiányzó tool, adat, a teszt elvárása téves, modell-szórás),
írd ide indoklással; különben hagyd ki ezt a szakaszt.

Szabályok: csak a kapott fájlokra hivatkozz, ne találj ki fájlt vagy tool-t. Ha ugyanaz a hiba több
esetben jelentkezik, egy javaslatot adj és hivatkozz rá. A bank adatait ne módosítsd, a rendszer
csak lekérdező. Ne ismételd meg a teljes válaszokat."""


SYSTEM_PROMPT_EN = """\
You are a quality-assurance engineer specialised in testing LLM agent systems.
You receive the results of the automatic tests of a bank branch officer chat assistant: the
description of each case, the result of the deterministic checks, the tools that were called, the
assistant's reply, and the full text of the agent description (Markdown) files of the architecture
concerned.

Write a concise text evaluation in English, in Markdown, with exactly this structure:

## Summary
2-4 sentences: how many runs failed and what the common cause is (if any).

## Failures and suggestions
For every failed case (architecture / case id) a separate sub-heading (###) with:
- **What went wrong:** which check failed, and what the tool calls / reply show about the cause.
- **Agent file to fix:** the relative path of the file (e.g. `03_router/01_branch_coordinator.md`) and
  why that one (not the model's fault, but which instruction is missing, ambiguous or contradictory).
- **Exact change:** the concrete text to insert or replace (quote the current sentence if it is to be
  replaced, and give the new one in a code block).

## Not fixable with a prompt
If a failure is not the description's fault (missing tool, data, a wrong test expectation, model
variance), write it here with a justification; otherwise omit this section.

Rules: refer only to the files you were given, do not invent files or tools. If the same failure
appears in several cases, give one suggestion and refer to it. Do not modify the bank's data; the
system is query-only. Do not repeat the full replies."""

# Text the report is assembled from, per language (the model answer follows the system prompt).
TEXTS = {
    "hu": {
        "system": SYSTEM_PROMPT_HU, "file": "Fájl", "arch": "Architektúra", "failed_run": "Hibás futás",
        "case": "Az eset", "checks": "Ellenőrzések", "tools": "Hívott tool-ok", "outputs": "Tool-kimenetek (előnézet)",
        "endpoint": "Router végpont", "reply": "Az asszisztens válasza",
        "more": "(+{n} további hibás futás nincs felsorolva)", "totals": "Összesen {total} futás, ebből {failed} hibás.",
        "ok": "## Összegzés\n\nMinden futás sikeres volt, nincs javítandó agent leíró.",
        "empty": "A modell üres kiértékelést adott.", "failed": "## Összegzés\n\nA kiértékelés nem készült el ({model}): {exc}",
    },
    "en": {
        "system": SYSTEM_PROMPT_EN, "file": "File", "arch": "Architecture", "failed_run": "Failed run",
        "case": "The case", "checks": "Checks", "tools": "Tools called", "outputs": "Tool outputs (preview)",
        "endpoint": "Router endpoint", "reply": "The assistant's reply",
        "more": "(+{n} more failed runs not listed)", "totals": "{total} runs in total, {failed} failed.",
        "ok": "## Summary\n\nAll runs passed; no agent description needs fixing.",
        "empty": "The model returned an empty evaluation.", "failed": "## Summary\n\nThe evaluation could not be written ({model}): {exc}",
    },
}


def _agent_files(arch: str, label: str = "Fájl") -> str:
    folder = profile_dir(arch)
    parts = []
    for path in sorted(folder.glob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        parts.append(f"#### {label}: `{folder.name}/{path.name}`\n```markdown\n"
                     f"{path.read_text(encoding='utf-8').strip()}\n```")
    return "\n\n".join(parts)


def _case_text(case: dict[str, Any]) -> str:
    keys = ("customer", "question", "expected_endpoint", "expected_any_tools",
            "must_contain_numbers", "must_contain_text", "expect_access_denied")
    return "\n".join(f"- {k}: {case[k]}" for k in keys if case.get(k) not in (None, [], False))


def build_prompt(
    results: list[dict[str, Any]], cases: list[dict[str, Any]], language: str = "hu"
) -> str | None:
    """The user message for the model, or ``None`` when no run failed."""
    tx = TEXTS.get(language, TEXTS["hu"])
    by_id = {c["id"]: c for c in cases}
    failed: dict[str, list[dict[str, Any]]] = {}
    for r in results:
        if not r["passed"]:
            failed.setdefault(r["arch"], []).append(r)
    if not failed:
        return None
    sections = []
    for arch, rows in failed.items():
        sections.append(f"# {tx['arch']}: {arch}\n\n{_agent_files(arch, tx['file'])}\n")
        for r in rows[:MAX_FAILURES_PER_ARCH]:
            case = by_id.get(r["case"], {"id": r["case"]})
            checks = "\n".join(f"  {'✓' if ok else '✗'} {name}" for name, ok in r["checks"].items())
            sections.append(
                f"## {tx['failed_run']}: {arch} / {r['case']}\n"
                f"{tx['case']}:\n{_case_text(case)}\n"
                f"{tx['checks']}:\n{checks}\n"
                f"{tx['tools']}: {', '.join(r['tools']) or '–'}\n"
                f"{tx['outputs']}:\n{chr(10).join(r.get('tool_outputs') or ['–'])}\n"
                f"{tx['endpoint']}: {r['endpoint'] or '–'}\n"
                f"{tx['reply']}:\n{r['reply'][:REPLY_LIMIT]}\n"
            )
        if len(rows) > MAX_FAILURES_PER_ARCH:
            sections.append(tx["more"].format(n=len(rows) - MAX_FAILURES_PER_ARCH) + "\n")
    total = len(results)
    n_failed = sum(not r["passed"] for rs in failed.values() for r in rs)
    return tx["totals"].format(total=total, failed=n_failed) + "\n\n" + "\n".join(sections)


def generate_report(
    results: list[dict[str, Any]], cases: list[dict[str, Any]], language: str = "hu"
) -> str:
    """The evaluation text. Never raises: a model failure becomes a note in the report."""
    tx = TEXTS.get(language, TEXTS["hu"])
    prompt = build_prompt(results, cases, language)
    if prompt is None:
        return tx["ok"]
    try:
        config = dataclasses.replace(
            BASE_CONFIG, name=REPORT_MODEL, temperature=0.2, max_tokens=REPORT_MAX_TOKENS
        )
        model = get_openrouter_model(config, OPENROUTER_API_KEY)
        answer = model.invoke([("system", tx["system"]), ("human", prompt)])
        text = answer.content
        if isinstance(text, list):
            text = "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in text)
        return text.strip() or tx["empty"]
    except Exception as exc:  # the eval itself is already saved; the report is a bonus
        return tx["failed"].format(model=REPORT_MODEL, exc=exc)


def report_path(results_file: str | Path) -> Path:
    return Path(results_file).with_suffix(".md")


def save_report(results_file: str | Path, text: str) -> Path:
    out = report_path(results_file)
    out.write_text(text + "\n", encoding="utf-8")
    return out
