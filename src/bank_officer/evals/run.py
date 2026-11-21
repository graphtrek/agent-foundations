"""Run the same questions through several architecture profiles and compare.

    uv run python src/bank_officer/evals/run.py --arch baseline,no_router,single_agent [--repeat 3]

Prints a table and writes ``logs/evals/<timestamp>.json``. The runner itself
is ``eval_runner.py`` (shared with the ``eval.html`` page).
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval_runner import (  # noqa: E402
    _safe_run,
    load_cases,
    save_results,
    summarize,
    valid_architectures,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--arch", help="comma separated profile ids (default: all)")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--case", help="comma separated case ids (default: all)")
    args = parser.parse_args()

    archs = args.arch.split(",") if args.arch else valid_architectures()
    cases = load_cases()
    if args.case:
        wanted = set(args.case.split(","))
        cases = [c for c in cases if c["id"] in wanted]

    results = []
    for arch in archs:
        for case in cases:
            for _ in range(args.repeat):
                result = _safe_run(arch, case)
                results.append(result)
                print(f"{arch:24} {case['id']:26} {'PASS' if result['passed'] else 'FAIL'} "
                      f"{result['ms']:>6} ms  tools={len(result['tools'])}", flush=True)

    print("\n" + f"{'architecture':24} {'pass':>9} {'median ms':>10} {'avg tools':>10}")
    for row in summarize(archs, results):
        print(f"{row['arch']:24} {row['passed']:>4}/{row['runs']:<4} "
              f"{row['median_ms']:>10.0f} {row['avg_tools']:>10.1f}")
    print(f"\nSaved: {save_results(archs, results)}")


if __name__ == "__main__":
    main()
