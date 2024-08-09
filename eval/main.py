"""
Evals for code generation tools.

Inspired by a document by Anton Osika and Axel Theorell.
"""

import csv
import inspect
import logging
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from .agents import Agent, GPTMe
from .evals import tests, tests_map
from .execenv import SimpleExecutionEnv
from .types import (
    CaseResult,
    ExecResult,
    ExecTest,
    ResultContext,
)

logger = logging.getLogger(__name__)

project_dir = Path(__file__).parent.parent


def execute(test: ExecTest, agent: Agent) -> ExecResult:
    """
    Executes the code for a specific model.
    """
    print(
        f"Running test {test['name']} with prompt: {test['prompt']} for model: {agent.model}"
    )

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
    models = [
        # "openai/gpt-3.5-turbo",
        # "openai/gpt-4-turbo",
        # "openai/gpt-4o",
        "openai/gpt-4o-mini",
        # "anthropic/claude-3-5-sonnet-20240620",
        "anthropic/claude-3-haiku-20240307",
    ]
    test_name = sys.argv[1] if len(sys.argv) > 1 else None

    all_results = {}
    for model in models:
        print(f"\n=== Running tests for model: {model} ===")
        llm, model = model.split("/")
        agent = GPTMe(llm=llm, model=model)

        results = []
        if test_name:
            print(f"=== Running test {test_name} ===")
            result = execute(tests_map[test_name], agent)
            results.append(result)
        else:
            print("=== Running all tests ===")
            for test in tests:
                result = execute(test, agent)
                results.append(result)

        all_results[model] = results

    print("\n=== Finished ===\n")

    for model, results in all_results.items():
        print(f"\nResults for model: {model}")
        duration_total = sum(
            result["timings"]["gen"]
            + result["timings"]["run"]
            + result["timings"]["eval"]
            for result in results
        )
        print(f"Completed {len(results)} tests in {duration_total:.2f}s:")
        for result in results:
            checkmark = (
                "✅" if all(case["passed"] for case in result["results"]) else "❌"
            )
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

    print("\n=== Model Comparison ===")
    for test in tests:
        print(f"\nTest: {test['name']}")
        for model, results in all_results.items():
            result = next(r for r in results if r["name"] == test["name"])
            passed = all(case["passed"] for case in result["results"])
            checkmark = "✅" if passed else "❌"
            duration = sum(result["timings"].values())
            print(f"{model}: {checkmark} {duration:.2f}s")

    all_success = all(
        all(all(case["passed"] for case in result["results"]) for result in results)
        for results in all_results.values()
    )
    if all_success:
        print("\n✅ All tests passed for all models!")
    else:
        print("\n❌ Some tests failed!")

    # Write results to CSV
    write_results_to_csv(all_results)

    sys.exit(0 if all_success else 1)


def write_results_to_csv(all_results):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # get current commit hash and dirty status, like: a8b2ef0-dirty
    commit_hash = subprocess.run(
        ["git", "describe", "--always", "--dirty", "--exclude", "'*'"],
        text=True,
        capture_output=True,
    ).stdout.strip()
    filename = project_dir / f"eval_results_{timestamp}.csv"

    with open(filename, "w", newline="") as csvfile:
        fieldnames = [
            "Model",
            "Test",
            "Passed",
            "Total Duration",
            "Generation Time",
            "Run Time",
            "Eval Time",
            "Commit Hash",
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        for model, results in all_results.items():
            for result in results:
                passed = all(case["passed"] for case in result["results"])
                writer.writerow(
                    {
                        "Model": model,
                        "Test": result["name"],
                        "Passed": "true" if passed else "false",
                        "Total Duration": sum(result["timings"].values()),
                        "Generation Time": result["timings"]["gen"],
                        "Run Time": result["timings"]["run"],
                        "Eval Time": result["timings"]["eval"],
                        "Commit Hash": commit_hash,
                    }
                )

    print(f"\nResults saved to {filename.resolve()}")


if __name__ == "__main__":
    main()
