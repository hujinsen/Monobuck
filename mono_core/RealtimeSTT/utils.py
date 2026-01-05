import os
import psutil


def check_parent_process(shutdown_event) -> None:
    """Set shutdown_event if parent process has died.

    This helper is shared by worker processes so they can
    exit promptly when the main process is gone.
    """
    ppid = os.getppid()
    if not psutil.pid_exists(ppid) and not shutdown_event.is_set():
        shutdown_event.set()
