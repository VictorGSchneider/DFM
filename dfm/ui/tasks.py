"""Run slow work (network, git, big copies) off the UI thread."""

import threading

import gi
gi.require_version("GLib", "2.0")
from gi.repository import GLib


def run_async(work, on_done) -> None:
    """Call `work()` in a worker thread, then `on_done(result, error)` on the UI thread.

    `error` is the exception `work` raised (and `result` is None), or None.
    """
    def runner() -> None:
        try:
            result, error = work(), None
        except Exception as exc:  # reported to the caller, never lost in the thread
            result, error = None, exc
        GLib.idle_add(_finish, on_done, result, error)

    threading.Thread(target=runner, daemon=True).start()


def _finish(on_done, result, error) -> bool:
    on_done(result, error)
    return GLib.SOURCE_REMOVE
