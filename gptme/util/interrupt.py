"""
Sets up a KeyboardInterrupt handler to handle Ctrl-C during the chat loop.
"""

import os
import time

from . import console

_interruptible_state = False
last_interrupt_time = 0.0


def handle_keyboard_interrupt(signum, frame):  # pragma: no cover
    """
    This handler allows interruption of the assistant or tool execution when in an interruptible state,
    while still providing a safeguard against accidental exits during user input.
    """
    global last_interrupt_time
    current_time = time.time()

    # if testing with pytest
    testing = bool(os.getenv("PYTEST_CURRENT_TEST"))

    if _interruptible_state or testing:
        raise KeyboardInterrupt

    # if current_time - last_interrupt_time <= timeout:
    #     console.log("Second interrupt received, exiting...")
    #     sys.exit(0)

    last_interrupt_time = current_time
    console.print()
    # console.log(
    #     f"Interrupt received. Press Ctrl-C again within {timeout} seconds to exit."
    # )
    console.log("Interrupted. Press Ctrl-D to exit.")


def set_interruptible():
    global _interruptible_state
    _interruptible_state = True


def clear_interruptible():
    global _interruptible_state
    _interruptible_state = False


class Interruptible:
    """Context manager for handling keyboard interrupts."""

    def __enter__(self):
        set_interruptible()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        clear_interruptible()
        if exc_type is KeyboardInterrupt:
            console.log("Interrupted. Stopping current execution.")
            return True  # Suppress the exception
