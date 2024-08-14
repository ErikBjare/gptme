"""
Evals for code generation tools.

Inspired by a document by Anton Osika and Axel Theorell.
"""

import csv
import inspect
import io
import logging
import subprocess
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from multiprocessing import Process, Queue
from pathlib import Path
from typing import Union

import click
from tabulate import tabulate

from .agents import Agent, GPTMe
from .evals import tests, tests_map
from .execenv import SimpleExecutionEnv
from .types import (
    CaseResult,
    ExecResult,
    ExecTest,
    ResultContext,
    Status,
)


@dataclass
class ProcessSuccess:
    files: dict[str, str | bytes]
    stdout: str
    stderr: str
    duration: float


@dataclass
class ProcessError:
    message: str
    stdout: str
    stderr: str
    duration: float


ProcessResult = Union[ProcessSuccess, ProcessError]


def act_process(agent, files, prompt, queue: "Queue[ProcessResult]"):
    # Runs on a process for each eval

    # redirect stdout and stderr to streams
    stdout, stderr = io.StringIO(), io.StringIO()
    sys.stdout, sys.stderr = stdout, stderr

    start = time.time()
    try:
        files = agent.act(files, prompt)
        duration = time.time() - start
        queue.put(ProcessSuccess(files, stdout.getvalue(), stderr.getvalue(), duration))
    except Exception as e:
        duration = time.time() - start
        queue.put(ProcessError(str(e), stdout.getvalue(), stderr.getvalue(), duration))


# Configure logging, including fully-qualified module names
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

project_dir = Path(__file__).parent.parent


def execute(test: ExecTest, agent: Agent, timeout: int) -> ExecResult:
    """
    Executes the code for a specific model with a timeout.
    """
    print(
        f"Running test {test['name']} with prompt: {test['prompt']} for model: {agent.model}"
    )

    queue: Queue[ProcessResult] = Queue()
    p = Process(target=act_process, args=(agent, test["files"], test["prompt"], queue))
    p.start()
    p.join(timeout)

    time_gen = 0.0
    time_run = 0.0
    time_eval = 0.0

    status: Status = "success"
    if p.is_alive():
        p.terminate()
        p.join()
        status = "timeout"
        time_gen = timeout

    if queue.empty():
        logger.error("Queue is empty, expected a result")
        return {
            "name": test["name"],
            "status": "error",
            "results": [],
            "timings": {"gen": time_gen, "run": time_run, "eval": time_eval},
            "stdout": "",
            "stderr": "",
        }

    result = queue.get()
    time_gen = result.duration
    stdout, stderr = result.stdout, result.stderr

    if isinstance(result, ProcessError):
        return {
            "name": test["name"],
            "status": "error",
            "results": [],
            "timings": {"gen": time_gen, "run": time_run, "eval": time_eval},
            "stdout": stdout,
            "stderr": stderr,
        }
    else:
        files = result.files

    # check and collect results
    run_start = time.time()
    env = SimpleExecutionEnv()
    env.upload(files)
    stdout_run, stderr_run, exit_code = env.run(test["run"])
    time_run = time.time() - run_start

    files = env.download()

    ctx = ResultContext(files, stdout_run, stderr_run, exit_code)
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

    time_eval = sum(r["duration"] for r in results)

    return {
        "name": test["name"],
        "status": status,
        "results": results,
        "timings": {
            "gen": time_gen,
            "run": time_run,
            "eval": time_eval,
        },
        "stdout": stdout,
        "stderr": stderr,
    }


def run_evals(
    tests, models, timeout: int, parallel: int
) -> dict[str, list[ExecResult]]:
    """
    Run evals for a list of tests.
    """
    # For coverage to work with multiprocessing
    # https://pytest-cov.readthedocs.io/en/latest/subprocess-support.html
    try:
        from pytest_cov.embed import cleanup_on_sigterm  # fmt: skip
    except ImportError:
        pass
    else:
        cleanup_on_sigterm()

    model_results = defaultdict(list)
    with ProcessPoolExecutor(parallel) as executor:
        model_futures_to_test = {
            model: {
                executor.submit(execute, test, GPTMe(model=model), timeout): test
                for test in tests
            }
            for model in models
        }
        for model, future_to_test in model_futures_to_test.items():
            for future in as_completed(future_to_test):
                test = future_to_test[future]
                try:
                    result = future.result()
                    model_results[model].append(result)
                    print(f"=== Completed test {test['name']} ===")
                except Exception as exc:
                    print(f"Test {test['name']} generated an exception: {exc}")
    return model_results


def print_model_results(model_results: dict[str, list[ExecResult]]):
    for model, results in model_results.items():
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


def print_model_results_table(model_results: dict[str, list[ExecResult]]):
    table_data = []
    headers = ["Model"] + [test["name"] for test in tests]

    for model, results in model_results.items():
        row = [model]
        for test in tests:
            try:
                result = next(r for r in results if r["name"] == test["name"])
                passed = all(case["passed"] for case in result["results"])
                checkmark = "✅" if result["status"] == "success" and passed else "❌"
                duration = sum(result["timings"].values())
                reason = "timeout" if result["status"] == "timeout" else ""
                if reason:
                    row.append(f"{checkmark} {reason}")
                else:
                    row.append(f"{checkmark} {duration:.2f}s")
            except StopIteration:
                row.append("❌ N/A")
        table_data.append(row)

    print(tabulate(table_data, headers=headers, tablefmt="grid"))


@click.command()
@click.argument("test_names", nargs=-1)
@click.option("_model", "--model", "-m", multiple=True, help="Model to use")
@click.option("--timeout", "-t", default=15, help="Timeout for code generation")
@click.option("--parallel", "-p", default=10, help="Number of parallel evals to run")
def main(test_names: list[str], _model: list[str], timeout: int, parallel: int):
    models = _model or [
        "openai/gpt-4o",
        "anthropic/claude-3-5-sonnet-20240620",
        "openrouter/meta-llama/llama-3.1-70b-instruct",
    ]

    tests_to_run = (
        [tests_map[test_name] for test_name in test_names] if test_names else tests
    )

    print("=== Running evals ===")
    model_results = run_evals(tests_to_run, models, timeout, parallel)
    print("\n=== Finished ===\n")

    print("\n\n=== Model Results ===")
    print_model_results(model_results)

    print("\n\n=== Model Comparison ===")
    print_model_results_table(model_results)

    # Write results to CSV
    write_results_to_csv(model_results)

    sys.exit(0)


def write_results_to_csv(model_results: dict[str, list[ExecResult]]):
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
        for model, results in model_results.items():
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
