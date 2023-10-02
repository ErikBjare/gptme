from pathlib import Path
from typing import Generator

from ..message import Message
from ..util import ask_execute


def execute_save(fn: str, code: str, ask: bool) -> Generator[Message, None, None]:
    """Save the code to a file."""
    # strip leading newlines
    code = code.lstrip("\n")

    if ask:
        print(f"Save to {fn}?")
        confirm = ask_execute(fn)
        print()
    else:
        print("Skipping save confirmation.")

    if ask and not confirm:
        # early return
        yield Message("system", "Save cancelled.")
        return

    path = Path(fn).expanduser()

    # if the file exists, ask to overwrite
    if path.exists():
        print("File already exists.")
        overwrite = ask_execute("overwrite")
        print()
        if not overwrite:
            # early return
            yield Message("system", "Save cancelled.")
            return

    # if the folder doesn't exist, ask to create it
    if not path.parent.exists():
        print("Folder does not exist.")
        create = ask_execute("create")
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
