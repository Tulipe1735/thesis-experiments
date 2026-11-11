"""Trusted parent-side transport for a disposable, syscall-filtered process."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import selectors
import subprocess
import sys
import time
from typing import Any


class WorkerError(RuntimeError):
    """A skill failed; its worker is no longer usable."""


class IsolationError(WorkerError):
    """The mandatory OS isolation boundary could not be established."""


class WorkerTimeout(WorkerError):
    pass


class WorkerOutputLimit(WorkerError):
    pass


class WorkerInputLimit(WorkerError):
    pass


class WorkerProtocolError(WorkerError):
    pass


class WorkerCrashed(WorkerError):
    pass


_UNSET = object()
_MIB = 1024 * 1024


def _positive_number(name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError(f"{name} must be a positive finite number")
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a positive finite number")
    return float(value)


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON value: {value}")


class Worker:
    """One skill, one episode, one isolated process.

    Source defines ``act(observation, task, state)`` and optionally
    ``init(profile)``. ``act`` returns ``{"action": {...}, "state": ...}``.
    State is retained unless the caller explicitly supplies a replacement.
    The trusted simulator must separately authorize each returned action.
    Every error closes the worker; create a fresh Worker for another episode.
    This object is synchronous and must not be called concurrently.
    """

    def __init__(
        self,
        source: str,
        profile: dict[str, Any],
        *,
        python_executable: str | os.PathLike[str] | None = None,
        wall_timeout: float = 5.0,
        startup_timeout: float = 20.0,
        max_input_bytes: int = 8 * _MIB,
        max_output_bytes: int = _MIB,
        memory_bytes: int = 1536 * _MIB,
        cpu_seconds: int = 120,
    ) -> None:
        if not isinstance(source, str) or not isinstance(profile, dict):
            raise TypeError("source must be text and profile must be a dictionary")
        self.wall_timeout = _positive_number("wall_timeout", wall_timeout)
        startup_timeout = _positive_number("startup_timeout", startup_timeout)
        for name, value in (
            ("max_input_bytes", max_input_bytes),
            ("max_output_bytes", max_output_bytes),
            ("memory_bytes", memory_bytes),
            ("cpu_seconds", cpu_seconds),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if max_input_bytes > 64 * _MIB:
            raise ValueError("max_input_bytes cannot exceed the 64 MiB wire limit")
        self.max_input_bytes = max_input_bytes
        self.max_output_bytes = max_output_bytes
        self._sequence = 0
        self._process: subprocess.Popen[bytes] | None = None
        self._closed = False
        self.last_stderr = ""
        self.state: Any = None
        self.initial_state: Any = None
        self.security: dict[str, Any] = {}
        request = self._encode(
            {
                "id": 0,
                "kind": "start",
                "source": source,
                "profile": profile,
                "limits": {
                    "max_input_bytes": max_input_bytes,
                    "memory_bytes": memory_bytes,
                    "cpu_seconds": cpu_seconds,
                },
            }
        )
        executable = os.fspath(python_executable or sys.executable)
        environment = {
            "LANG": "C.UTF-8",
            "OPENBLAS_NUM_THREADS": "1",
            "OMP_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "BLIS_NUM_THREADS": "1",
            "VECLIB_MAXIMUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
        }
        try:
            self._process = subprocess.Popen(
                [executable, "-I", "-u", str(Path(__file__).with_name("_entry.py"))],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=environment,
                close_fds=True,
                start_new_session=True,
                bufsize=0,
            )
            for stream in (
                self._process.stdin,
                self._process.stdout,
                self._process.stderr,
            ):
                assert stream is not None
                os.set_blocking(stream.fileno(), False)
            response = self._exchange(request, 0, startup_timeout)
            if response.get("kind") != "ready":
                raise WorkerProtocolError("worker did not return the startup handshake")
            self.security = response.get("security", {})
            if not isinstance(self.security, dict) or self.security.get("seccomp") is not True:
                raise IsolationError("worker did not establish mandatory syscall isolation")
            self.initial_state = response.get("state")
            self.state = self.initial_state
        except BaseException:
            self.close()
            raise

    @property
    def pid(self) -> int | None:
        return self._process.pid if self._process is not None else None

    @property
    def is_alive(self) -> bool:
        return (
            not self._closed
            and self._process is not None
            and self._process.poll() is None
        )

    def _encode(self, message: dict[str, Any]) -> bytes:
        payload = json.dumps(message, allow_nan=False, separators=(",", ":")).encode("utf-8") + b"\n"
        if len(payload) > self.max_input_bytes:
            raise WorkerInputLimit(
                f"input is {len(payload)} bytes; limit is {self.max_input_bytes}"
            )
        return payload

    def _exchange(self, payload: bytes, request_id: int, timeout: float) -> dict[str, Any]:
        process = self._process
        if self._closed or process is None:
            raise WorkerCrashed("worker is closed")
        assert process.stdin and process.stdout and process.stderr
        deadline = time.monotonic() + timeout
        pending = memoryview(payload)
        output = bytearray()
        errors = bytearray()
        total_output = 0
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdin, selectors.EVENT_WRITE, "input")
                selector.register(process.stdout, selectors.EVENT_READ, "output")
                selector.register(process.stderr, selectors.EVENT_READ, "errors")
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise WorkerTimeout(f"worker exceeded {timeout:g}s wall-time limit")
                    events = selector.select(remaining)
                    if not events:
                        raise WorkerTimeout(f"worker exceeded {timeout:g}s wall-time limit")
                    for key, _ in events:
                        if key.data == "input":
                            try:
                                written = os.write(key.fd, pending[:65536])
                            except BlockingIOError:
                                continue
                            except BrokenPipeError as exc:
                                raise WorkerCrashed("worker closed its input") from exc
                            pending = pending[written:]
                            if not pending:
                                selector.unregister(key.fileobj)
                            continue
                        try:
                            chunk = os.read(key.fd, 65536)
                        except BlockingIOError:
                            continue
                        if not chunk:
                            selector.unregister(key.fileobj)
                            if key.data == "output" and b"\n" not in output:
                                raise WorkerCrashed(
                                    f"worker exited without a response (status {process.poll()})"
                                )
                            continue
                        total_output += len(chunk)
                        if total_output > self.max_output_bytes:
                            raise WorkerOutputLimit(
                                f"worker exceeded {self.max_output_bytes} output bytes"
                            )
                        if key.data == "errors":
                            errors.extend(chunk)
                        else:
                            output.extend(chunk)
                    if b"\n" in output:
                        line, remainder = bytes(output).split(b"\n", 1)
                        if remainder or pending:
                            raise WorkerProtocolError("unsolicited or extra worker response")
                        try:
                            response = json.loads(line, parse_constant=_reject_constant)
                        except (ValueError, UnicodeError, RecursionError) as exc:
                            raise WorkerProtocolError("worker returned invalid JSON") from exc
                        if not isinstance(response, dict) or response.get("id") != request_id:
                            raise WorkerProtocolError("worker returned an invalid response id")
                        if response.get("kind") == "isolation_error":
                            raise IsolationError(str(response.get("error", "isolation failed")))
                        if response.get("kind") == "error":
                            raise WorkerError(str(response.get("error", "skill failed")))
                        self.last_stderr = errors.decode("utf-8", errors="replace")
                        return response
        except BaseException:
            self.last_stderr = errors.decode("utf-8", errors="replace")
            self.close()
            raise

    def act(self, observation: Any, task: Any, state: Any = _UNSET) -> dict[str, Any]:
        """Return a JSON result; validate its action in the trusted simulator."""
        if not self.is_alive:
            self.close()
            raise WorkerCrashed("worker is not running")
        self._sequence += 1
        try:
            request = self._encode(
                {
                    "id": self._sequence,
                    "kind": "act",
                    "observation": observation,
                    "task": task,
                    "state": self.state if state is _UNSET else state,
                }
            )
            response = self._exchange(request, self._sequence, self.wall_timeout)
            if response.get("kind") != "result":
                raise WorkerProtocolError("worker returned an unexpected message kind")
            result = response.get("result")
            if not isinstance(result, dict) or not isinstance(result.get("action"), dict):
                raise WorkerProtocolError("skill result must contain an action object")
            if "state" not in result:
                raise WorkerProtocolError("skill result must contain JSON state")
            self.state = result["state"]
            return result
        except BaseException:
            self.close()
            raise

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        process = self._process
        if process is None:
            return
        if process.poll() is None:
            try:
                process.kill()
            except ProcessLookupError:
                pass
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream is not None:
                stream.close()

    def __enter__(self) -> Worker:
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()

    def __del__(self) -> None:
        if hasattr(self, "_closed"):
            self.close()
