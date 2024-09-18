"""
Evals for code generation tools.

Inspired by a document by Anton Osika and Axel Theorell.
"""

import csv
import logging
import multiprocessing
import multiprocessing.resource_tracker
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import click
import multiprocessing_logging
from tabulate import tabulate

from ..message import len_tokens
from .run import run_evals
from .suites import suites, tests_default, tests_map
from .types import ExecResult, ExecTest

# Suppress the specific warning about leaked semaphore objects
# NOTE: this doesn't actually work due to multiprocessing quirks
# warnings.filterwarnings(
#     "ignore",
#     category=UserWarning,
#     message=r"resource_tracker:.*",
# )

# Configure logging, including fully-qualified module names
logging.basicConfig(
    level=logging.INFO,
    # helpful in debugging: %(processName)s
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

project_dir = Path(__file__).parent.parent.parent

def print_model_results(model_results: dict[str, list[ExecResult]]):
    total_tests = 0
    total_duration = 0.0
    total_tokens = 0

    for model, results in model_results.items():
        print(f"\nResults for model: {model}")
        duration_total = sum(
            result.timings["gen"] + result.timings["run"] + result.timings["eval"]
            for result in results
        )
        model_total_tokens = sum(
            len_tokens(result.gen_stdout) + len_tokens(result.run_stdout)
            for result in results
        )
        print(
            f"Completed {len(results)} tests in {duration_total:.2f}s/{model_total_tokens}tok:"
        )
        for result in results:
            cases = result.results
            checkmark = "✅" if cases and all(case.passed for case in cases) else "❌"
            duration_result = (
                result.timings["gen"] + result.timings["run"] + result.timings["eval"]
            )
            gen_tokens = len_tokens(result.gen_stdout)
            run_tokens = len_tokens(result.run_stdout)
            result_total_tokens = gen_tokens + run_tokens
            print(
                f"{checkmark} {result.name}: {duration_result:.2f}s/{result_total_tokens}tok "
                f"(gen: {result.timings['gen']:.2f}s/{gen_tokens}tok, "
                f"run: {result.timings['run']:.2f}s/{run_tokens}tok, "
                f"eval: {result.timings['eval']:.2f}s)"
            )
            for case in cases:
                checkmark = "✅" if case.passed else "❌"
                print(f"   {checkmark} {case.name}")

        total_tests += len(results)
        total_duration += duration_total
        total_tokens += model_total_tokens

    print("\nTotal across all models:")
    print(f"Completed {total_tests} tests in {total_duration:.2f}s/{total_tokens}tok")


def print_model_results_table(model_results: dict[str, list[ExecResult]]):
    test_names = {
        result.name for results in model_results.values() for result in results
    }
    headers = ["Model"] + list(test_names)
    table_data = []

    for model, results in model_results.items():
        row = [model]
        for test_name in test_names:
            try:
                result = next(r for r in results if r.name == test_name)
                passed = all(case.passed for case in result.results)
                checkmark = "✅" if result.status == "success" and passed else "❌"
                duration = sum(result.timings.values())
                gen_tokens = len_tokens(result.gen_stdout)
                run_tokens = len_tokens(result.run_stdout)
                reason = "timeout" if result.status == "timeout" else ""
                if reason:
                    row.append(f"{checkmark} {reason}")
                else:
                    row.append(
                        f"{checkmark} {duration:.2f}s/{gen_tokens+run_tokens}tok"
                    )
            except StopIteration:
                row.append("❌ N/A")
        table_data.append(row)

    print(tabulate(table_data, headers=headers))


@click.command()
@click.argument("eval_names_or_result_files", nargs=-1)
@click.option(
    "_model",
    "--model",
    "-m",
    multiple=True,
    help="Model to use, can be passed multiple times.",
)
@click.option("--timeout", "-t", default=30, help="Timeout for code generation")
@click.option("--parallel", "-p", default=10, help="Number of parallel evals to run")
def main(
    eval_names_or_result_files: list[str],
    _model: list[str],
    timeout: int,
    parallel: int,
):
    """
    Run evals for gptme.

    Pass test names to run, or result files to print.
    """
    # init
    multiprocessing_logging.install_mp_handler()

    models = _model or [
        "openai/gpt-4o",
        "anthropic/claude-3-5-sonnet-20240620",
        "openrouter/meta-llama/llama-3.1-405b-instruct",
    ]

    results_files = [f for f in eval_names_or_result_files if f.endswith(".csv")]
    if results_files:
        for results_file in results_files:
            p = Path(results_file)
            if p.exists():
                results = read_results_from_csv(str(p))
                print(f"\n{results_file}")
                print(f"{'=' * len(results_file)}")
                print_model_results(results)
                print("\n=== Model Comparison ===")
                print_model_results_table(results)
            else:
                print(f"Error: File {results_file} not found")
                sys.exit(1)
        sys.exit(0)

    tests_to_run: list[ExecTest] = []
    for test_name in eval_names_or_result_files:
        if test_name in tests_map:
            tests_to_run.append(tests_map[test_name])
        elif test_name in suites:
            tests_to_run.extend(suites[test_name])
        else:
            raise ValueError(f"Test {test_name} not found")

    if not tests_to_run:
        tests_to_run = tests_default

    print("=== Running evals ===")
    model_results = run_evals(tests_to_run, models, timeout, parallel)
    print("\n=== Finished ===\n")

    print("\n=== Model Results ===")
    print_model_results(model_results)

    print("\n=== Model Comparison ===")
    print_model_results_table(model_results)

    # Write results to CSV
    write_results_to_csv(model_results)

    sys.exit(0)


def read_log_file(file_path: Path) -> str:
    if file_path.exists():
        with open(file_path) as f:
            return f.read()
    return ""


def read_results_from_csv(filename: str) -> dict[str, list[ExecResult]]:
    model_results = defaultdict(list)
    results_dir = Path(filename).parent
    with open(filename, newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            model = row["Model"]
            test_dir = results_dir / model / row["Test"]

            result = ExecResult(
                name=row["Test"],
                status="success" if row["Passed"] == "true" else "error",
                results=[],  # We don't have detailed results in the CSV
                timings={
                    "gen": float(row["Generation Time"]),
                    "run": float(row["Run Time"]),
                    "eval": float(row["Eval Time"]),
                },
                gen_stdout=read_log_file(test_dir / "gen_stdout.txt"),
                gen_stderr=read_log_file(test_dir / "gen_stderr.txt"),
                run_stdout=read_log_file(test_dir / "run_stdout.txt"),
                run_stderr=read_log_file(test_dir / "run_stderr.txt"),
            )
            model_results[model].append(result)
    return dict(model_results)


def write_results_to_csv(model_results: dict[str, list[ExecResult]]):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # get current commit hash and dirty status, like: a8b2ef0-dirty
    # TODO: don't assume we are in the gptme repo, use other version identifiers if available
    commit_hash = subprocess.run(
        ["git", "describe", "--always", "--dirty", "--exclude", "'*'"],
        text=True,
        capture_output=True,
    ).stdout.strip()
    results_dir = project_dir / "eval_results" / timestamp
    results_dir.mkdir(parents=True, exist_ok=True)

    csv_filename = results_dir / "eval_results.csv"

    with open(csv_filename, "w", newline="") as csvfile:
        fieldnames = [
            "Model",
            "Test",
            "Passed",
            "Total Duration",
            "Generation Time",
            "Run Time",
            "Eval Time",
            "Commit Hash",
            "Gen Stdout File",
            "Gen Stderr File",
            "Run Stdout File",
            "Run Stderr File",
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        for model, results in model_results.items():
            for result in results:
                # Needs to pass all checks, and needs to have results (not empty, as in case of timeout)
                passed = (
                    all(case.passed for case in result.results)
                    if result.results
                    else False
                )

                # Create directory for this test
                test_dir = results_dir / model / result.name
                test_dir.mkdir(parents=True, exist_ok=True)

                # Save each stream to a separate file
                gen_stdout_file = test_dir / "gen_stdout.txt"
                gen_stderr_file = test_dir / "gen_stderr.txt"
                run_stdout_file = test_dir / "run_stdout.txt"
                run_stderr_file = test_dir / "run_stderr.txt"

                with open(gen_stdout_file, "w") as f:
                    f.write(result.gen_stdout)
                with open(gen_stderr_file, "w") as f:
                    f.write(result.gen_stderr)
                with open(run_stdout_file, "w") as f:
                    f.write(result.run_stdout)
                with open(run_stderr_file, "w") as f:
                    f.write(result.run_stderr)

                writer.writerow(
                    {
                        "Model": model,
                        "Test": result.name,
                        "Passed": "true" if passed else "false",
                        "Total Duration": sum(result.timings.values()),
                        "Generation Time": result.timings["gen"],
                        "Run Time": result.timings["run"],
                        "Eval Time": result.timings["eval"],
                        "Commit Hash": commit_hash,
                        "Gen Stdout File": gen_stdout_file.relative_to(results_dir),
                        "Gen Stderr File": gen_stderr_file.relative_to(results_dir),
                        "Run Stdout File": run_stdout_file.relative_to(results_dir),
                        "Run Stderr File": run_stderr_file.relative_to(results_dir),
                    }
                )

    print(f"\nResults saved to {csv_filename.resolve()}")
    print(f"Output files saved in {results_dir.resolve()}")

    csv_filename = results_dir / "eval_results.csv"

    with open(csv_filename, "w", newline="") as csvfile:
        fieldnames = [
            "Model",
            "Test",
            "Passed",
            "Total Duration",
            "Generation Time",
            "Run Time",
            "Eval Time",
            "Commit Hash",
            "Gen Stdout File",
            "Gen Stderr File",
            "Run Stdout File",
            "Run Stderr File",
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        for model, results in model_results.items():
            for result in results:
                # Needs to pass all checks, and needs to have results (not empty, as in case of error/timeout)
                passed = (
                    all(case.passed for case in result.results)
                    if result.results
                    else False
                )

                # Create directory for this test
                test_dir = results_dir / model / result.name
                test_dir.mkdir(parents=True, exist_ok=True)

                # Save each stream to a separate file
                streams = ["gen_stdout", "gen_stderr", "run_stdout", "run_stderr"]
                for stream in streams:
                    stream_file = test_dir / f"{stream}.txt"
                    with open(stream_file, "w") as f:
                        f.write(getattr(result, stream))

                writer.writerow(
                    {
                        "Model": model,
                        "Test": result.name,
                        "Passed": "true" if passed else "false",
                        "Total Duration": sum(result.timings.values()),
                        "Generation Time": result.timings["gen"],
                        "Run Time": result.timings["run"],
                        "Eval Time": result.timings["eval"],
                        "Commit Hash": commit_hash,
                    }
                )

    print(f"\nResults saved to {csv_filename.resolve()}")
    print(f"Output files saved in {results_dir.resolve()}")
