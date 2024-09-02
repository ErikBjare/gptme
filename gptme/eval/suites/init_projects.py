from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gptme.eval.main import ExecTest


def check_clean_exit(ctx):
    return ctx.exit_code == 0


def check_clean_working_tree(ctx):
    return "nothing to commit, working tree clean" in ctx.stdout


def check_commit_exists(ctx):
    return "No commits yet" not in ctx.stdout


def check_package_json(ctx):
    return "package.json" in ctx.files


def check_output_compiled_successfully(ctx):
    return "Compiled successfully" in ctx.stdout


def check_output_erik(ctx):
    return "Erik" in ctx.stdout


def check_cargo_toml(ctx):
    return "Cargo.toml" in ctx.files


def check_exists_main(ctx):
    return "main.py" in ctx.files


tests: list["ExecTest"] = [
    {
        "name": "init-git",
        "files": {},
        "run": "git status",
        "prompt": "initialize a git repository, write a main.py file, and commit it",
        "expect": {
            "clean exit": check_clean_exit,
            "clean working tree": check_clean_working_tree,
            "main.py exists": check_exists_main,
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
]
