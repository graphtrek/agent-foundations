"""Eval runner shared by the CLI (``evals/run.py``) and the web page (``eval.html``).

Runs the cases of ``evals/cases.yaml`` through architecture profiles. Each run
uses a fresh ``BranchSession`` with the case's customer selected by a real
(unscored) first turn. Scoring is deterministic - expected tool called, endpoint
matched, figures present in the reply, entitlement refusal - with no LLM judge.
Behaviour is probabilistic, so one run proves little: use ``repeat``.
"""

from __future__ import annotations

import json
import re
import statistics
import threading
import time
import uuid
from pathlib import Path
from typing import Any

import yaml

import bank_data
from architecture import list_profiles
from branch_session import BranchSession
from terminal import LOGS_DIR, REGISTRY
from tools import BranchContext

CASES_FILE = Path(__file__).resolve().parent / "evals" / "cases.yaml"
EVALS_DIR = LOGS_DIR / "evals"
DENIED_MARKER = "jogosultsági szint"
MAX_REPEAT = 5


def load_cases() -> list[dict[str, Any]]:
    return yaml.safe_load(CASES_FILE.read_text(encoding="utf-8"))["cases"]


def _digits(text: str) -> str:
    return re.sub(r"\D", "", text)


def run_case(arch: str, case: dict[str, Any]) -> dict[str, Any]:
    pipeline = REGISTRY.get(arch)
    session = BranchSession(
        pipeline.router,
        pipeline.coordinator,
        BranchContext(officer_id="eval", branch_id="branch-buda"),
        thread_id_prefix=f"eval-{arch}-{case['id']}-{time.time_ns()}",
        architecture=arch,
    )
    if case.get("customer"):
        # The model only knows what is in the conversation, so the customer is
        # selected by a real first turn, as an officer would do.
        customer = bank_data.find_customer(case["customer"])
        session.run_turn(f"Válaszd ki az ügyfelet: {customer.full_name}.")
        if session.current_customer_id != case["customer"]:
            raise RuntimeError(f"setup turn did not select {case['customer']}")
    tools: list[str] = []
    endpoint: str | None = None
    reply, total_ms = "", 0
    for event, data in session.stream_turn(case["question"]):
        if event == "tool_call":
            tools.append(data["name"])
        elif event == "route" and data.get("endpoint"):
            endpoint = data["endpoint"].get("endpoint_id")
        elif event == "reply":
            reply, total_ms = data["text"], data.get("total_ms", 0)

    checks: dict[str, bool] = {}
    if case.get("expect_access_denied"):
        checks["access_denied"] = DENIED_MARKER in reply
    else:
        if case.get("expected_any_tools"):
            checks["tool"] = any(t in tools for t in case["expected_any_tools"])
        if case.get("expected_endpoint") and pipeline.router is not None:
            checks["endpoint"] = endpoint == case["expected_endpoint"]
        reply_digits = _digits(reply)
        for number in case.get("must_contain_numbers", []):
            checks[f"number {number}"] = _digits(str(number)) in reply_digits
        for fragment in case.get("must_contain_text", []):
            checks[f"text {fragment}"] = fragment.lower() in reply.lower()
    return {
        "arch": arch,
        "case": case["id"],
        "passed": all(checks.values()),
        "checks": checks,
        "tools": tools,
        "endpoint": endpoint,
        "ms": total_ms,
        "reply": reply,
    }


def _safe_run(arch: str, case: dict[str, Any]) -> dict[str, Any]:
    try:
        return run_case(arch, case)
    except Exception as exc:  # a broken run counts as a failure
        return {
            "arch": arch, "case": case["id"], "passed": False,
            "checks": {"error": False}, "tools": [], "endpoint": None,
            "ms": 0, "reply": f"ERROR: {exc}",
        }


def summarize(archs: list[str], results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary = []
    for arch in archs:
        rows = [r for r in results if r["arch"] == arch]
        summary.append({
            "arch": arch,
            "passed": sum(r["passed"] for r in rows),
            "runs": len(rows),
            "median_ms": statistics.median(r["ms"] for r in rows) if rows else 0,
            "avg_tools": statistics.mean(len(r["tools"]) for r in rows) if rows else 0,
        })
    return summary


def valid_architectures() -> list[str]:
    return [p["id"] for p in list_profiles() if "error" not in p]


def save_results(archs: list[str], results: list[dict[str, Any]]) -> Path:
    EVALS_DIR.mkdir(parents=True, exist_ok=True)
    out = EVALS_DIR / f"{time.strftime('%Y%m%d-%H%M%S')}.json"
    out.write_text(
        json.dumps({"summary": summarize(archs, results), "results": results},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return out


class EvalRun:
    """One background eval over architectures x cases x repeats."""

    def __init__(self, archs: list[str], cases: list[dict[str, Any]], repeat: int) -> None:
        self.id = uuid.uuid4().hex[:10]
        self.archs, self.cases, self.repeat = archs, cases, repeat
        self.total = len(archs) * len(cases) * repeat
        self.results: list[dict[str, Any]] = []
        self.current: str | None = None
        self.done = False
        self.saved: str | None = None
        self.cancelled = threading.Event()
        self._lock = threading.Lock()

    def start(self) -> None:
        threading.Thread(target=self._work, daemon=True).start()

    def _work(self) -> None:
        try:
            for arch in self.archs:
                for case in self.cases:
                    for _ in range(self.repeat):
                        if self.cancelled.is_set():
                            return
                        self.current = f"{arch} / {case['id']}"
                        result = _safe_run(arch, case)
                        with self._lock:
                            self.results.append(result)
        finally:
            self.current = None
            if self.results:
                self.saved = str(save_results(self.archs, self.results))
            self.done = True

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            results = list(self.results)
        return {
            "id": self.id,
            "archs": self.archs,
            "cases": [c["id"] for c in self.cases],
            "repeat": self.repeat,
            "total": self.total,
            "finished": len(results),
            "current": self.current,
            "done": self.done,
            "cancelled": self.cancelled.is_set(),
            "saved": self.saved,
            "results": results,
            "summary": summarize(self.archs, results),
        }
