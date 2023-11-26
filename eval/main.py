"""
Evals for code generation tools.

Inspired by a document by Anton Osika and Axel Theorell.
"""
import inspect
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

Files = Dict[str, str]


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


class TestResult(TypedDict):
    name: str
    results: list[CaseResult]
    timings: dict[str, float]


class ExecTest(TypedDict):
    name: str
    files: Files
    run: str
    prompt: str
    expect: dict[str, Callable[[ResultContext], bool]]


tests: list[ExecTest] = [
    {
        "name": "hello",
        "files": {"hello.py": "print('Hello, world!')"},
        "run": "python hello.py",
        "prompt": "Change the code in hello.py to print 'Hello, human!'",
        "expect": {
            "correct output": lambda ctx: ctx.stdout == "Hello, human!\n",
            "correct file": lambda ctx: ctx.files["hello.py"].strip()
            == "print('Hello, human!')",
        },
    },
    {
        "name": "hello-patch",
        "files": {"hello.py": "print('Hello, world!')"},
        "run": "python hello.py",
        "prompt": "Patch the code in hello.py to print 'Hello, human!'",
        "expect": {
            "correct output": lambda ctx: ctx.stdout == "Hello, human!\n",
            "correct file": lambda ctx: ctx.files["hello.py"].strip()
            == "print('Hello, human!')",
        },
    },
    {
        "name": "hello-ask",
        "files": {"hello.py": "print('Hello, world!')"},
        "run": "echo 'Erik' | python hello.py",
        # TODO: work around the "don't try to execute it" part by improving gptme such that it just gives EOF to stdin in non-interactive mode
        "prompt": "modify hello.py to ask the user for their name and print 'Hello, <name>!'. don't try to execute it",
        "expect": {
            "correct output": lambda ctx: "Hello, Erik!" in ctx.stdout,
        },
    },
    {
        "name": "prime100",
        "files": {},
        "run": "python prime.py",
        "prompt": "write a script prime.py that computes and prints the 100th prime number",
        "expect": {
            "correct output": lambda ctx: "541" in ctx.stdout.split(),
        },
    },
    {
        "name": "init-git",
        "files": {},
        "run": "git status",
        "prompt": "initialize a git repository, write a main.py file, and commit it",
        "expect": {
            "clean exit": lambda ctx: ctx.exit_code == 0,
            "clean working tree": lambda ctx: "nothing to commit, working tree clean"
            in ctx.stdout,
            "main.py exists": lambda ctx: "main.py" in ctx.files,
            "we have a commit": lambda ctx: "No commits yet" not in ctx.stdout,
        },
    },
    # Fails, gets stuck on interactive stuff
    # {
    #     "name": "init-vue-ts-tailwind",
    #     "files": {},
    #     "run": "cat package.json",
    #     "prompt": "initialize a vue project with typescript and tailwind, make a page that says 'Hello, world!'. don't try to execute it or do anything interactive",
    #     "expect": {
    #         "package.json exists": lambda ctx: "package.json" in ctx.files,
    #         "vue installed": lambda ctx: '"vue":' in ctx.files["package.json"],
    #         "tailwind installed": lambda ctx: '"tailwindcss":'
    #         in ctx.files["package.json"],
    #         "typescript installed": lambda ctx: '"typescript":'
    #         in ctx.files["package.json"],
    #     },
    # },
]

tests_map = {test["name"]: test for test in tests}

class FileStore:
    def __init__(self):
        self.working_dir = Path(tempfile.mkdtemp(prefix="gptme-evals-"))
        self.working_dir.mkdir(parents=True, exist_ok=True)
        self.id = self.working_dir.name.split("-")[-1]

    def upload(self, files: Files):
        for name, content in files.items():
            path = self.working_dir / name
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w") as f:
                f.write(content)
        return self

    def download(self) -> Files:
        files = {}
        ignore = [".git"]
        for path in self.working_dir.glob("**/*"):
            if any(path.match(i) for i in ignore):
                continue
            if path.is_file():
                with open(path, "r") as f:
                    try:
                        content = f.read()
                    except UnicodeDecodeError:
                        content = "binary file"
                    files[str(path.relative_to(self.working_dir))] = content
        return files

class Agent:
    def act(files: Files | None, command: str | None, prompt: str) -> Files:
        """
        Carries out the prompt and returns artifacts in the form of `Files`.
        """
        raise NotImplementedError


class GPTMe(Agent):
    def act(self, files: Files | None, command: str | None, prompt: str):
        store = FileStore()
        os.chdir(store.working_dir) # can now modify store content

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
    '''
    A simple execution environment that runs the code in the files.

    upload() and download() are inherited from FileStore.
    '''

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
        while p.poll() is None:
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
            if time.time() - start > 30:
                print("Timeout!")
                p.kill()
                break
        print("--- Finished run ---\n")
        return stdout_full, stderr_full, p.returncode


def execute(test: ExecTest) -> TestResult:
    """
    Executes the code.
    """
    print(f"Running test {test['name']} with prompt: {test['prompt']}")
    agent = GPTMe()


    # generate code
    gen_start = time.time()
    files = agent.act(test["files"], test["run"], test["prompt"])
    gen_duration = time.time() - gen_start

    # check and collect results
    run_start = time.time()
    env = SimpleExecutionEnv()
    stdout, stderr, exit_code = env.upload(files).run(test["run"])
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
    print(f"Completed {len(results)} tests:")
    for result in results:
        checkmark = "✅" if all(case["passed"] for case in result["results"]) else "❌"
        total_duration = (
            result["timings"]["gen"]
            + result["timings"]["run"]
            + result["timings"]["eval"]
        )
        print(
            f"- {result['name']} in {total_duration} (gen: {result['timings']['gen']:.2f}s, run: {result['timings']['run']:.2f}s, eval: {result['timings']['eval']:.2f}s)"
        )
        for case in result["results"]:
            checkmark = "✅" if case["passed"] else "❌"
            print(f"  {checkmark} {case['name']}")


if __name__ == "__main__":
    main()
