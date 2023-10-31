from pathlib import Path
from typing import Generator

from ..message import Message
from ..util import ask_execute


def execute_save(
    fn: str, code: str, ask: bool, append: bool = False
) -> Generator[Message, None, None]:
    """Save the code to a file."""
    action = "save" if not append else "append"
    # strip leading newlines
    code = code.lstrip("\n")

    if ask:
        confirm = ask_execute(f"{action.capitalize()} to {fn}?")
        print()
    else:
        confirm = True
        print(f"Skipping {action} confirmation.")

    if ask and not confirm:
        # early return
        yield Message("system", f"{action.capitalize()} cancelled.")
        return

    path = Path(fn).expanduser()

    if append:
        if not path.exists():
            yield Message("system", f"File {fn} doesn't exist, can't append to it.")
            return

        with open(path, "a") as f:
            f.write("\n" + code)
        yield Message("system", f"Appended to {fn}")
        return

    # if the file exists, ask to overwrite
    if path.exists():
        overwrite = ask_execute("File exists, overwrite?")
        print()
        if not overwrite:
            # early return
            yield Message("system", "Save cancelled.")
            return

    # if the folder doesn't exist, ask to create it
    if not path.parent.exists():
        create = ask_execute("Folder doesn't exist, create it?")
        print()
        if create:
            path.parent.mkdir(parents=True)
        else:
            # early return
            yield Message("system", "Save cancelled.")
            return

    print("Saving to " + fn)
    with open(path, "w") as f:
        f.write(code)
    yield Message("system", f"Saved to {fn}")
