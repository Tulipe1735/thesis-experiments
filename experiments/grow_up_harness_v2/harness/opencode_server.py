"""One private OpenCode server bound to the Agent workspace.

The shared background service can answer the first request of a new project
with a config cached for another project, which made the canary probe leak. A
private server started in the workspace has the workspace as its project from
process start, so the deny-all config applies to the first model call.

The server is stopped when the context exits. Its stdout/stderr are kept as
evidence.
"""

from __future__ import annotations

import os
import secrets
import socket
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_port(port: int, process: subprocess.Popen, timeout_s: float) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"opencode serve exited with {process.returncode}")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.2)
    raise RuntimeError("opencode serve did not listen before the timeout")


@contextmanager
def serve(workspace: Path | str, log_dir: Path | str, *, timeout_s: float = 60.0):
    workspace = Path(workspace).resolve()
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=False)
    port = free_port()
    password = secrets.token_hex(16)
    env = {
        **os.environ,
        "PWD": str(workspace),
        "OPENCODE_PASSWORD": password,
    }
    stdout = (log_dir / "server.out").open("wb")
    stderr = (log_dir / "server.err").open("wb")
    process = subprocess.Popen(
        ["opencode", "serve", "--hostname", "127.0.0.1", "--port", str(port)],
        cwd=str(workspace),
        env=env,
        stdout=stdout,
        stderr=stderr,
    )
    try:
        _wait_for_port(port, process, timeout_s)
        yield {
            "url": f"http://127.0.0.1:{port}",
            "password": password,
            "pid": process.pid,
        }
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        stdout.close()
        stderr.close()
