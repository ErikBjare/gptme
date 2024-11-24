"""
Evals for code generation tools.

Inspired by a document by Anton Osika and Axel Theorell.
"""

import csv
import logging
import subprocess
import sys
from collections import defaultdict
from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path

import click
import multiprocessing_logging
from tabulate import tabulate

from ..message import len_tokens
from .run import run_evals
from .suites import suites, tests_default, tests_map
from .types import CaseResult, EvalResult, EvalSpec

# Configure logging, including fully-qualified module names
logging.basicConfig(
    level=logging.INFO,
    # helpful in debugging: %(processName)s
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

project_dir = Path(__file__).parent.parent.parent


def sort_tests(test_names):
    # sorts a list of test names by the order they appear in the default tests
    return sorted(
        test_names,
        key=lambda x: (list(tests_map).index(x) if x in tests_map else 0),
    )


def print_model_results(model_results: dict[str, list[EvalResult]]):
    total_tests = 0
    total_tokens = 0

    for model, results in model_results.items():
        print(f"\nResults for model: {model}")
        model_total_tokens = sum(
            len_tokens(result.gen_stdout) + len_tokens(result.run_stdout)
            for result in results
        )
        print(f"Completed {len(results)} tests in {model_total_tokens}tok:")
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
                f"{checkmark} {result.name}: {duration_result:.0f}s/{result_total_tokens}tok "
                f"(gen: {result.timings['gen']:.0f}s/{gen_tokens}tok, "
                f"run: {result.timings['run']:.0f}s/{run_tokens}tok, "
                f"eval: {result.timings['eval']:.0f}s)"
            )
            for case in cases:
                checkmark = "✅" if case.passed else "❌"
                print(f"   {checkmark} {case.name}")

        total_tests += len(results)
        total_tokens += model_total_tokens
    print("\nTotal across all models:")
    print(f"Completed {total_tests} tests in {total_tokens}tok")


def print_model_results_table(model_results: dict[str, list[EvalResult]]):
    test_names = sort_tests(
        {result.name for results in model_results.values() for result in results}
    )
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
                        f"{checkmark} {duration:.0f}s/{gen_tokens+run_tokens}tok"
                    )
            except StopIteration:
                row.append("❌ N/A")
        table_data.append(row)

    print(tabulate(table_data, headers=headers))


def aggregate_and_display_results(result_files: list[str]):
    all_results: dict[str, dict[str, dict]] = {}
    for file in result_files:
        for model, model_results in read_results_from_csv(file).items():
            if model not in all_results:
                all_results[model] = {}
            for result in model_results:
                if result.name not in all_results[model]:
                    all_results[model][result.name] = {
                        "total": 0,
                        "passed": 0,
                        "tokens": 0,
                    }
                all_results[model][result.name]["total"] += 1
                all_results[model][result.name]["tokens"] += len_tokens(
                    result.gen_stdout
                ) + len_tokens(result.run_stdout)
                if result.status == "success" and all(
                    case.passed for case in result.results
                ):
                    all_results[model][result.name]["passed"] += 1

    # Prepare table data
    headers = ["Model"] + sort_tests(
        {
            test
            for model_results in all_results.values()
            for test in model_results.keys()
        }
    )
    table_data = []

    def get_status_emoji(passed, total):
        percentage = (passed / total) * 100
        if 80 <= percentage:
            return "✅"
        elif 20 <= percentage < 80:
            return "🔶"
        else:
            return "❌"

    for model, results in sorted(all_results.items()):
        row = [model.replace("openrouter/", "")]
        for test in headers[1:]:
            if test in results:
                passed = results[test]["passed"]
                total = results[test]["total"]
                tokens = results[test]["tokens"]
                status_emoji = get_status_emoji(passed, total)
                incl_tokens = True
                row.append(
                    f"{status_emoji} {passed}/{total}"
                    + (f" {round(tokens / total)}tk" if incl_tokens else "")
                )
            else:
                row.append("❓ N/A")
        table_data.append(row)

    # Print the table
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
    Pass eval or suite names to run, or result files to print.

    Output from evals will be captured, unless a single eval is run, and saved to the results directory.
    """
    # init
    multiprocessing_logging.install_mp_handler()

    models = _model or [
        "openai/gpt-4o",
        "openai/gpt-4o-mini",
        "anthropic/claude-3-5-sonnet-20241022",
        "anthropic/claude-3-5-haiku-20241022",
        "openrouter/meta-llama/llama-3.1-405b-instruct",
        "gemini/gemini-1.5-flash-latest",
    ]

    results_files = []
    for f in eval_names_or_result_files:
        p = Path(f)
        if p.suffix == ".csv":
            results_files.append(f)
        if (p / "eval_results.csv").exists():
            results_files.append(str(p / "eval_results.csv"))
    eval_names = [f for f in eval_names_or_result_files if f not in results_files]
    if len(results_files) >= 2:
        aggregate_and_display_results(results_files)
        sys.exit(0)
    elif results_files:
        model_results = read_results_from_csv(results_files[0])
        print_model_results(model_results)
        print_model_results_table(model_results)
        sys.exit(0)

    evals_to_run: list[EvalSpec] = []
    for eval_name in eval_names:
        if test := tests_map.get(eval_name):
            evals_to_run.append(test)
        elif suite := suites.get(eval_name) or suites.get(eval_name.replace("-", "_")):
            evals_to_run.extend(suite)
        else:
            raise ValueError(f"Test or results '{eval_name}' not found")

    if not evals_to_run:
        evals_to_run = tests_default

    print("=== Running evals ===")
    model_results = run_evals(evals_to_run, models, timeout, parallel)
    print("=== Finished ===")

    print("\n=== Model Results ===")
    print_model_results(model_results)

    print("\n=== Model Comparison ===")
    print_model_results_table(model_results)

    # Write results to CSV
    write_results(model_results)

    sys.exit(0)


def _read_case_results(cases_file: Path) -> Generator[CaseResult, None, None]:
    if cases_file.exists():
        with open(cases_file, newline="") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                yield CaseResult(
                    name=row["Case"],
                    passed=row["Passed"] == "true",
                    duration=float(row["Duration"]),
                )


def _write_case_results(cases_file: Path, results: list[CaseResult]):
    with open(cases_file, "w", newline="") as csvfile:
        fieldnames = ["Model", "Test", "Case", "Passed", "Duration"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            row = {
                "Case": result.name,
                "Passed": "true" if result.passed else "false",
                "Duration": round(result.duration, 2),
            }
            writer.writerow(row)


def read_log_file(file_path: Path) -> str:
    if file_path.exists():
        with open(file_path) as f:
            return f.read()
    return ""


def read_results_from_csv(filename: str) -> dict[str, list[EvalResult]]:
    model_results = defaultdict(list)
    results_dir = Path(filename).parent
    with open(filename, newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            model = row["Model"]
            test_dir = results_dir / model / row["Test"]

            result = EvalResult(
                name=row["Test"],
                status="success" if row["Passed"] == "true" else "error",
                results=list(_read_case_results(test_dir / "cases.csv")),
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


def write_results(model_results: dict[str, list[EvalResult]]):
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%SZ")
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
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, lineterminator="\n")

        writer.writeheader()
        for model, results in model_results.items():
            for result in results:
                passed = (
                    all(case.passed for case in result.results)
                    if result.results
                    else False
                )

                test_dir = results_dir / model / result.name
                test_dir.mkdir(parents=True, exist_ok=True)

                streams = ["gen_stdout", "gen_stderr", "run_stdout", "run_stderr"]
                for stream in streams:
                    stream_file = test_dir / f"{stream}.txt"
                    with open(stream_file, "w", newline="\n") as f:
                        f.write(getattr(result, stream))

                row = {
                    "Model": model,
                    "Test": result.name,
                    "Passed": "true" if passed else "false",
                    "Total Duration": round(sum(result.timings.values()), 2),
                    "Generation Time": round(result.timings["gen"], 2),
                    "Run Time": round(result.timings["run"], 2),
                    "Eval Time": round(result.timings["eval"], 2),
                    "Commit Hash": commit_hash,
                }
                writer.writerow(row)
                _write_case_results(test_dir / "cases.csv", result.results)

    print(f"\nResults saved to {csv_filename.resolve()}")
    print(f"Output files saved in {results_dir.resolve()}")
