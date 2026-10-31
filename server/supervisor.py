"""Keep the API and each background worker in its own process.

A crash in the Bluetooth scan, the climate sampler, or the news scheduler
restarts only that process. The others keep running.
"""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

logger = logging.getLogger("server.supervisor")

_ROOT = Path(__file__).resolve().parent.parent


def child_commands(python: str) -> list[tuple[str, list[str]]]:
    """Process name and argv. The API is told not to embed the same workers."""
    return [
        ("api", [python, "-m", "server"]),
        ("climate", [python, "-m", "server.workers", "climate"]),
        ("scale", [python, "-m", "server.workers", "scale"]),
        ("news", [python, "-m", "server.workers", "news"]),
    ]


def main() -> None:
    from server.auth import require_api_key

    require_api_key()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    python = sys.executable
    specs = child_commands(python)
    env = dict(os.environ)
    env["PA_EMBED_WORKERS"] = "0"
    stop = False
    children: dict[str, subprocess.Popen[bytes]] = {}

    def _shutdown(signum, _frame) -> None:  # noqa: ANN001
        nonlocal stop
        logger.info("Supervisor received signal %s", signum)
        stop = True

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    logger.info("Starting %s isolated processes", len(specs))
    try:
        while not stop:
            for name, cmd in specs:
                proc = children.get(name)
                if proc is not None and proc.poll() is None:
                    continue
                if proc is not None:
                    logger.warning(
                        "Process %s exited (%s); restarting", name, proc.returncode
                    )
                children[name] = subprocess.Popen(
                    cmd,
                    cwd=str(_ROOT),
                    env=env,
                )
                logger.info("Started %s pid=%s", name, children[name].pid)
            time.sleep(2)
    finally:
        for name, proc in children.items():
            if proc.poll() is None:
                logger.info("Stopping %s", name)
                proc.terminate()
        for proc in children.values():
            try:
                proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    main()
