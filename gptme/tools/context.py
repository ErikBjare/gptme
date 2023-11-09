import json
import shutil
from pathlib import Path

from ..message import Message
from ..tools.shell import get_shell


def gen_context_msg() -> Message:
    """Generate a message with context information from output of `pwd` and `git status`."""
    shell = get_shell()
    msgstr = ""

    cmd = "pwd"
    ret, pwd, _ = shell.run_command(cmd)
    assert ret == 0
    msgstr += f"$ {cmd}\n{pwd.rstrip()}\n\n"

    cmd = "git status -s --porcelain"
    ret, git, _ = shell.run_command(cmd)
    if ret == 0 and git:
        msgstr += f"$ {cmd}\n{git}\n\n"

    if shutil.which("ctags"):
        msgstr += f"$ ctags\n{ctags()}\n\n"

    return Message("system", msgstr.strip(), hide=True)


def _gitignore():
    """Read the gitignore, return a list of ignored patterns."""

    project_root = Path(".")
    with open(project_root / ".gitignore") as f:
        gitignore = f.read()

    ignored = []
    for line in gitignore.splitlines():
        if not line.startswith("#"):
            ignored.append(line.rstrip("/"))

    return ignored


def _get_ctags_cmd():
    ignored = _gitignore()
    ignored_str = " ".join([f"--exclude='{i}'" for i in ignored])

    return f"ctags -R --output-format=json {ignored_str} --fields=+l+n --languages=python --python-kinds=-iv -f -"


def ctags() -> str:
    """Generate ctags output for project in working dir."""
    assert shutil.which("ctags"), "ctags not found"

    shell = get_shell()
    cmd = _get_ctags_cmd()
    ret, ctags, _ = shell.run_command(cmd)
    assert ret == 0

    output = ["ctags:"]
    tags = []
    for line in ctags.splitlines():
        try:
            tags.append(json.loads(line))
        except json.JSONDecodeError:
            output += [f"  failed to parse: {line}"]
            break

    files = {tag["path"] for tag in tags}
    for file in sorted(files):
        filetags = [tag for tag in tags if tag["path"] == file]
        output += [str(file)]
        level = 0
        for tag in sorted(filetags, key=lambda x: x["line"]):
            if tag["kind"] == "class":
                output += [level * "  " + f"  class {tag['name']}:{tag['line']}"]
                level += 1
            elif tag["kind"] == "function":
                level = 0
                output += [level * "  " + f"  def {tag['name']}:{tag['line']}"]
            elif tag["kind"] == "variable":
                level = 0
                output += [level * "  " + f"  {tag['name']}:{tag['line']}"]
            elif tag["kind"] == "unknown":
                # import a as b
                pass
            else:
                output += [
                    level * "  " + f"  {tag['kind']} {tag['name']}:{tag['line']}"
                ]

    return "\n".join(output)


if __name__ == "__main__":
    output = ctags()
    print(output)
