"""
Evals for code generation tools.

Inspired by a document by Anton Osika and Axel Theorell.
"""

import inspect
import logging
import sys
import time

from .agents import GPTMe
from .evals import tests, tests_map
from .execenv import SimpleExecutionEnv
from .types import (
    CaseResult,
    ExecResult,
    ExecTest,
    ResultContext,
)

logger = logging.getLogger(__name__)


def execute(test: ExecTest) -> ExecResult:
    """
    Executes the code.
    """
    print(f"Running test {test['name']} with prompt: {test['prompt']}")
    agent = GPTMe()

    # generate code
    gen_start = time.time()
    files = agent.act(test["files"], test["prompt"])
    gen_duration = time.time() - gen_start

    # check and collect results
    run_start = time.time()
    env = SimpleExecutionEnv()
    env.upload(files)
    stdout, stderr, exit_code = env.run(test["run"])
    run_duration = time.time() - run_start

    files = env.download()

    ctx = ResultContext(files, stdout, stderr, exit_code)
    results: list[CaseResult] = []
    print(f"\n--- Results for {test['name']} ---")
    for name, case in test["expect"].items():
        code = inspect.getsource(case).strip()
        eval_start = time.time()
        try:
            passed = case(ctx)
        except Exception as e:
            print(f"Error while checking {name}: {e}")
            passed = False
        eval_duration = time.time() - eval_start
        checkmark = "✅" if passed else "❌"
        print(f"{checkmark} {name:20s}")
        results.append(
            {"name": name, "passed": passed, "code": code, "duration": eval_duration}
        )
    print("--- End of results ---\n")

    return {
        "name": test["name"],
        "results": results,
        "timings": {
            "gen": gen_duration,
            "run": run_duration,
            "eval": sum(r["duration"] for r in results),
        },
    }


def main():
    test_name = sys.argv[1] if len(sys.argv) > 1 else None
    results = []
    if test_name:
        print(f"=== Running test {test_name} ===")
        result = execute(tests_map[test_name])
        results.append(result)
    else:
        print("=== Running all tests ===")
        for test in tests:
            result = execute(test)
            results.append(result)

    print("=== Finished ===\n")
    duration_total = sum(
        result["timings"]["gen"] + result["timings"]["run"] + result["timings"]["eval"]
        for result in results
    )
    print(f"Completed {len(results)} tests in {duration_total:.2f}s:")
    for result in results:
        checkmark = "✅" if all(case["passed"] for case in result["results"]) else "❌"
        duration_result = (
            result["timings"]["gen"]
            + result["timings"]["run"]
            + result["timings"]["eval"]
        )
        print(
            f"- {result['name']} in {duration_result:.2f}s (gen: {result['timings']['gen']:.2f}s, run: {result['timings']['run']:.2f}s, eval: {result['timings']['eval']:.2f}s)"
        )
        for case in result["results"]:
            checkmark = "✅" if case["passed"] else "❌"
            print(f"  {checkmark} {case['name']}")

    all_success = all(
        all(case["passed"] for case in result["results"]) for result in results
    )
    if all_success:
        print("\n✅ All tests passed!")
    else:
        print("\n❌ Some tests failed!")

    sys.exit(0 if all_success else 1)


if __name__ == "__main__":
    main()
