import json
from pathlib import Path

from ..message import Message
from ..tools.shell import get_shell


def _gen_context_msg() -> Message:
    shell = get_shell()
    msgstr = ""

    cmd = "pwd"
    ret, pwd, _ = shell.run_command(cmd)
    assert ret == 0
    msgstr += f"$ {cmd}\n{pwd.strip()}\n"

    cmd = "git status -s --porcelain"
    ret, git, _ = shell.run_command(cmd)
    if ret == 0 and git:
        msgstr += f"$ {cmd}\n{git}\n"

    return Message("system", msgstr.strip(), hide=True)


def _gitignore():
    """Read the gitignore, return a list of ignored patterns."""

    project_root = Path(".")
    with open(project_root / ".gitignore", "r") as f:
        gitignore = f.read()

    ignored = []
    for line in gitignore.splitlines():
        if not line.startswith("#"):
            ignored.append(line.rstrip("/"))

    return ignored


def _ctags():
    """Generate ctags for current project."""

    ignored = _gitignore()
    ignored_str = " ".join([f"--exclude='{i}'" for i in ignored])

    shell = get_shell()
    cmd = f"ctags -R --output-format=json {ignored_str} --fields=+l+n --languages=python --python-kinds=-iv -f -"
    print(cmd)
    ret, ctags, _ = shell.run_command(cmd)
    assert ret == 0

    print("ctags:")
    tags = []
    for line in ctags.splitlines():
        try:
            tags.append(json.loads(line))
        except json.JSONDecodeError:
            print("  failed to parse: ", line)
            break

    files = {tag["path"] for tag in tags}
    for file in sorted(files):
        filetags = [tag for tag in tags if tag["path"] == file]
        print(f"{file}")
        level = 0
        for tag in sorted(filetags, key=lambda x: x["line"]):
            if tag["kind"] == "class":
                print(level * "  " + f"  class {tag['name']}:{tag['line']}")
                level += 1
            elif tag["kind"] == "function":
                level = 0
                print(level * "  " + f"  def {tag['name']}:{tag['line']}")
            elif tag["kind"] == "variable":
                level = 0
                print(level * "  " + f"  {tag['name']}:{tag['line']}")
            elif tag["kind"] == "unknown":
                # import a as b
                pass
            else:
                print(level * "  " + f"  {tag['kind']} {tag['name']}:{tag['line']}")

    return ctags


if __name__ == "__main__":
    assert _ctags()
