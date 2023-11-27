"""
Evals for code generation tools.

Inspired by a document by Anton Osika and Axel Theorell.
"""

import base64
import inspect
import logging
import os
import subprocess
import sys
import tempfile
import time
from abc import abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, TypedDict

from gptme.cli import chat as gptme_chat
from gptme.message import Message
from gptme.prompts import get_prompt

from evals import tests, tests_map

logger = logging.getLogger(__name__)

Files = Dict[str, str | bytes]


class ExecutionEnv:
    @abstractmethod
    def run(self, command: str):
        """
        Runs a command in the execution environment.
        """
        raise NotImplementedError

    @abstractmethod
    def upload(self, files: Files):
        """
        Uploads files to the execution environment.
        """
        raise NotImplementedError

    @abstractmethod
    def download(self) -> Files:
        """
        Downloads files from the execution environment.
        """
        raise NotImplementedError


@dataclass
class ResultContext:
    """
    Context for the result of a test.
    """

    files: Files
    stdout: str
    stderr: str
    exit_code: int


class CaseResult(TypedDict):
    name: str
    passed: bool
    code: str
    duration: float


class ExecResult(TypedDict):
    name: str
    results: list[CaseResult]
    timings: dict[str, float]


class ExecTest(TypedDict):
    name: str
    files: Files
    run: str
    prompt: str
    expect: dict[str, Callable[[ResultContext], bool]]


class FileStore:
    def __init__(self):
        self.working_dir = Path(tempfile.mkdtemp(prefix="gptme-evals-"))
        self.working_dir.mkdir(parents=True, exist_ok=True)
        self.id = self.working_dir.name.split("-")[-1]

    def upload(self, files: Files):
        for name, content in files.items():
            path = self.working_dir / name
            path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, str):
                with open(path, "w") as f:
                    f.write(content)
            elif isinstance(content, bytes):
                with open(path, "wb") as f:
                    f.write(base64.b64decode(content))

    def download(self) -> Files:
        files: Files = {}
        for path in self.working_dir.glob("**/*"):
            if path.is_file():
                key = str(path.relative_to(self.working_dir))
                try:
                    with open(path, "r") as f:
                        files[key] = f.read()
                except UnicodeDecodeError:
                    # file is binary
                    with open(path, "rb") as f:
                        files[key] = base64.b64encode(f.read())
        return files


class Agent:
    @abstractmethod
    def act(self, files: Files | None, prompt: str) -> Files:
        """
        Carries out the prompt and returns artifacts in the form of `Files`.
        """
        raise NotImplementedError


class GPTMe(Agent):
    def act(self, files: Files | None, prompt: str):
        store = FileStore()
        os.chdir(store.working_dir)  # can now modify store content

        if files:
            store.upload(files)

        print("\n--- Start of generation ---")
        print(f"Working in {store.working_dir}")
        # TODO: add timeout
        try:
            gptme_chat(
                [Message("user", prompt)],
                [get_prompt()],
                f"gptme-evals-{store.id}",
                "openai",
                "gpt-4-1106-preview",
                no_confirm=True,
                interactive=False,
            )
        # don't exit on sys.exit()
        except (SystemExit, KeyboardInterrupt):
            pass
        print("--- Finished generation ---\n")

        return store.download()


class SimpleExecutionEnv(FileStore, ExecutionEnv):
    """
    A simple execution environment that runs the code in the files.

    upload() and download() are inherited from FileStore.
    """

    def run(self, command) -> tuple[str, str, int]:
        os.chdir(self.working_dir)

        start = time.time()
        print("\n--- Start of run ---")
        # while running, also print the stdout and stderr
        p = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self.working_dir,
            text=True,
            shell=True,
        )
        print("$", command)
        stdout_full, stderr_full = "", ""
        while p.poll() is None or p.stdout or p.stderr:
            assert p.stdout is not None
            assert p.stderr is not None
            stdout = p.stdout.readline()
            stderr = p.stderr.readline()
            if stdout:
                print(stdout, end="")
                stdout_full += stdout
            if stderr:
                print(stderr, end="")
                stderr_full += stderr
            if not stdout and not stderr and p.poll() is not None:
                break
            if time.time() - start > 30:
                print("Timeout!")
                p.kill()
                break
        print("--- Finished run ---\n")
        return stdout_full, stderr_full, p.returncode


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
