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

from architecture import profile_dir

REPORT_MODEL = os.environ.get("EVAL_REPORT_MODEL", "openai/gpt-6-luna")
REPORT_MAX_TOKENS = 3000
MAX_FAILURES_PER_ARCH = 12  # keeps the prompt bounded on a very bad run
REPLY_LIMIT = 1200

SYSTEM_PROMPT = """\
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


def _agent_files(arch: str) -> str:
    folder = profile_dir(arch)
    parts = []
    for path in sorted(folder.glob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        parts.append(f"#### Fájl: `{folder.name}/{path.name}`\n```markdown\n"
                     f"{path.read_text(encoding='utf-8').strip()}\n```")
    return "\n\n".join(parts)


def _case_text(case: dict[str, Any]) -> str:
    keys = ("customer", "question", "expected_endpoint", "expected_any_tools",
            "must_contain_numbers", "must_contain_text", "expect_access_denied")
    return "\n".join(f"- {k}: {case[k]}" for k in keys if case.get(k) not in (None, [], False))


def build_prompt(results: list[dict[str, Any]], cases: list[dict[str, Any]]) -> str | None:
    """The user message for the model, or ``None`` when no run failed."""
    by_id = {c["id"]: c for c in cases}
    failed: dict[str, list[dict[str, Any]]] = {}
    for r in results:
        if not r["passed"]:
            failed.setdefault(r["arch"], []).append(r)
    if not failed:
        return None
    sections = []
    for arch, rows in failed.items():
        sections.append(f"# Architektúra: {arch}\n\n{_agent_files(arch)}\n")
        for r in rows[:MAX_FAILURES_PER_ARCH]:
            case = by_id.get(r["case"], {"id": r["case"]})
            checks = "\n".join(f"  {'✓' if ok else '✗'} {name}" for name, ok in r["checks"].items())
            sections.append(
                f"## Hibás futás: {arch} / {r['case']}\n"
                f"Az eset:\n{_case_text(case)}\n"
                f"Ellenőrzések:\n{checks}\n"
                f"Hívott tool-ok: {', '.join(r['tools']) or '–'}\n"
                f"Tool-kimenetek (előnézet):\n{chr(10).join(r.get('tool_outputs') or ['–'])}\n"
                f"Router végpont: {r['endpoint'] or '–'}\n"
                f"Az asszisztens válasza:\n{r['reply'][:REPLY_LIMIT]}\n"
            )
        if len(rows) > MAX_FAILURES_PER_ARCH:
            sections.append(f"(+{len(rows) - MAX_FAILURES_PER_ARCH} további hibás futás nincs felsorolva)\n")
    total = len(results)
    n_failed = sum(not r["passed"] for rs in failed.values() for r in rs)
    return f"Összesen {total} futás, ebből {n_failed} hibás.\n\n" + "\n".join(sections)


def generate_report(results: list[dict[str, Any]], cases: list[dict[str, Any]]) -> str:
    """The evaluation text. Never raises: a model failure becomes a note in the report."""
    prompt = build_prompt(results, cases)
    if prompt is None:
        return "## Összegzés\n\nMinden futás sikeres volt, nincs javítandó agent leíró."
    try:
        # Imported here: terminal loads the config (and may prompt for the API key).
        from model_util import get_openrouter_model
        from terminal import BASE_CONFIG, openrouter_api_key

        config = dataclasses.replace(
            BASE_CONFIG, name=REPORT_MODEL, temperature=0.2, max_tokens=REPORT_MAX_TOKENS
        )
        model = get_openrouter_model(config, openrouter_api_key)
        answer = model.invoke([("system", SYSTEM_PROMPT), ("human", prompt)])
        text = answer.content
        if isinstance(text, list):
            text = "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in text)
        return text.strip() or "A modell üres kiértékelést adott."
    except Exception as exc:  # the eval itself is already saved; the report is a bonus
        return f"## Összegzés\n\nA kiértékelés nem készült el ({REPORT_MODEL}): {exc}"


def report_path(results_file: str | Path) -> Path:
    return Path(results_file).with_suffix(".md")


def save_report(results_file: str | Path, text: str) -> Path:
    out = report_path(results_file)
    out.write_text(text + "\n", encoding="utf-8")
    return out
