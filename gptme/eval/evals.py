from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from main import ExecTest


def correct_output_hello(ctx):
    return ctx.stdout == "Hello, human!\n"


def correct_file_hello(ctx):
    return ctx.files["hello.py"].strip() == "print('Hello, human!')"


def check_prime_output(ctx):
    return "541" in ctx.stdout.split()


def check_clean_exit(ctx):
    return ctx.exit_code == 0


def check_clean_working_tree(ctx):
    return "nothing to commit, working tree clean" in ctx.stdout


def check_main_py_exists(ctx):
    return "main.py" in ctx.files


def check_commit_exists(ctx):
    return "No commits yet" not in ctx.stdout


def check_output_hello_ask(ctx):
    return "Hello, Erik!" in ctx.stdout


def check_package_json(ctx):
    return "package.json" in ctx.files


def check_output_compiled_successfully(ctx):
    return "Compiled successfully" in ctx.stdout


def check_output_erik(ctx):
    return "Erik" in ctx.stdout


def check_cargo_toml(ctx):
    return "Cargo.toml" in ctx.files


tests: list["ExecTest"] = [
    {
        "name": "hello",
        "files": {"hello.py": "print('Hello, world!')"},
        "run": "python hello.py",
        "prompt": "Change the code in hello.py to print 'Hello, human!'",
        "expect": {
            "correct output": correct_output_hello,
            "correct file": correct_file_hello,
        },
    },
    {
        "name": "hello-patch",
        "files": {"hello.py": "print('Hello, world!')"},
        "run": "python hello.py",
        "prompt": "Patch the code in hello.py to print 'Hello, human!'",
        "expect": {
            "correct output": correct_output_hello,
            "correct file": correct_file_hello,
        },
    },
    {
        "name": "hello-ask",
        "files": {"hello.py": "print('Hello, world!')"},
        "run": "echo 'Erik' | python hello.py",
        # TODO: work around the "don't try to execute it" part by improving gptme such that it just gives EOF to stdin in non-interactive mode
        "prompt": "modify hello.py to ask the user for their name and print 'Hello, <name>!'. don't try to execute it",
        "expect": {
            "correct output": check_output_hello_ask,
        },
    },
    {
        "name": "prime100",
        "files": {},
        "run": "python prime.py",
        "prompt": "write a script prime.py that computes and prints the 100th prime number",
        "expect": {
            "correct output": check_prime_output,
        },
    },
    {
        "name": "init-git",
        "files": {},
        "run": "git status",
        "prompt": "initialize a git repository, write a main.py file, and commit it",
        "expect": {
            "clean exit": check_clean_exit,
            "clean working tree": check_clean_working_tree,
            "main.py exists": check_main_py_exists,
            "we have a commit": check_commit_exists,
        },
    },
    {
        "name": "init-react",
        "files": {},
        "run": "npm run build",
        "prompt": "create a react project in the current directory, try to build it, but dont start the server and dont use git",
        "expect": {
            "package.json exists": check_package_json,
            "builds successfully": check_output_compiled_successfully,
        },
    },
    {
        "name": "init-rust",
        "files": {},
        "run": "cargo build",
        "prompt": "create a Rust project in the current directory",
        "expect": {
            "Cargo.toml exists": check_cargo_toml,
        },
    },
    {
        "name": "whois-superuserlabs-ceo",
        "files": {},
        "run": "cat answer.txt",
        "prompt": "who is the CEO of Superuser Labs? write the answer to answer.txt",
        "expect": {
            "correct output": check_output_erik,
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
