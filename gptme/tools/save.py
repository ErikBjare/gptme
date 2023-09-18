from ..util import ask_execute
from ..message import Message


from typing import Generator


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

    print("Saving to " + fn)
    with open(fn, "w") as f:
        f.write(code)
    yield Message("system", f"Saved to {fn}")
