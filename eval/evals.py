from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from main import ExecTest

tests: list["ExecTest"] = [
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
    #     "prompt": "initialize a vue project with typescript and tailwind, make a page that says 'Hello, world!'. avoid interactive tools to initialize the project",
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
