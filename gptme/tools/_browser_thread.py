import importlib
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from queue import Empty, Queue
from threading import Event, Lock, Thread
from typing import Any, Literal, TypeVar

from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

T = TypeVar("T")

TIMEOUT = 30  # seconds


@dataclass
class Command:
    func: Callable
    args: tuple
    kwargs: dict


Action = Literal["stop"]


class BrowserThread:
    def __init__(self):
        self.queue: Queue[tuple[Command | Action, object]] = Queue()
        self.results: dict[object, tuple[Any, Exception | None]] = {}
        self.lock = Lock()
        self.ready = Event()
        self._init_error: Exception | None = None
        self.thread = Thread(target=self._run, daemon=True)
        self.thread.start()
        # Wait for browser to be ready
        if not self.ready.wait(timeout=TIMEOUT):
            raise TimeoutError("Browser failed to start")
        if self._init_error:
            raise self._init_error

        logger.debug("Browser thread started")

    def _run(self):
        try:
            playwright = sync_playwright().start()
            try:
                browser = playwright.chromium.launch()
                logger.info("Browser launched")
            except Exception as e:
                if "Executable doesn't exist" in str(e):
                    pw_version = importlib.metadata.version("playwright")
                    self._init_error = RuntimeError(
                        f"Browser executable not found. Run: pipx run playwright=={pw_version} install chromium-headless-shell"
                    )
                else:
                    self._init_error = e
                self.ready.set()  # Signal init complete (with error)
                return

            self.ready.set()  # Signal successful init

            while True:
                try:
                    cmd, cmd_id = self.queue.get(timeout=1.0)
                    if cmd == "stop":
                        break

                    try:
                        result = cmd.func(browser, *cmd.args, **cmd.kwargs)
                        with self.lock:
                            self.results[cmd_id] = (result, None)
                    except Exception as e:
                        logger.exception("Error in browser thread")
                        with self.lock:
                            self.results[cmd_id] = (None, e)
                except Empty:
                    # Timeout on queue.get, continue waiting
                    continue
        except Exception:
            logger.exception("Fatal error in browser thread")
            self.ready.set()  # Prevent hanging in __init__
            raise
        finally:
            try:
                browser.close()
                playwright.stop()
            except Exception:
                logger.exception("Error stopping browser")
            logger.info("Browser stopped")

    def execute(self, func: Callable[..., T], *args, **kwargs) -> T:
        if not self.thread.is_alive():
            raise RuntimeError("Browser thread died")

        cmd_id = object()  # unique id
        self.queue.put((Command(func, args, kwargs), cmd_id))

        deadline = time.monotonic() + TIMEOUT
        while time.monotonic() < deadline:
            with self.lock:
                if cmd_id in self.results:
                    result, error = self.results.pop(cmd_id)
                    if error:
                        raise error
                    logger.info("Browser operation completed")
                    return result
            time.sleep(0.1)  # Prevent busy-waiting

        raise TimeoutError(f"Browser operation timed out after {TIMEOUT}s")

    def stop(self):
        """Stop the browser thread"""
        try:
            self.queue.put(("stop", object()))
            self.thread.join(timeout=TIMEOUT)
        except Exception:
            logger.exception("Error stopping browser thread")
