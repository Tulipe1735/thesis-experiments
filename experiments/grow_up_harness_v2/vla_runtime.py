"""Process bridge to the pinned SmolVLA worker; no policy logic lives here.

The worker runs in `~/.venvs/g1-vla` because lerobot 0.4.4 pins numpy <2.3 and the
MuJoCo environment is registered at 2.5.4. It speaks JSON lines and writes each
native (1,50,28) action chunk to a .npy file inside this repository.
"""

import json
import queue
import subprocess
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PYTHON = Path.home() / ".venvs/g1-vla/bin/python"
WORKER = ROOT / "grasp_optimization/smolvla_worker.py"


def _write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                    encoding="utf-8")


class SmolVLAClient:
    """Load once, predict many times. Any non-READY first packet is a hard failure."""

    def __init__(self, folder: Path, python: Path = DEFAULT_PYTHON, timeout: float = 900.0):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=False)
        if not Path(python).exists():
            raise FileNotFoundError(f"VLA interpreter missing: {python}")
        self.log = (self.folder / "policy_worker.log").open("w", encoding="utf-8")
        self.messages: queue.Queue = queue.Queue()
        self.calls = 0
        started = time.monotonic()
        self.process = subprocess.Popen(
            [str(python), "-u", str(WORKER)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.log,
            text=True, encoding="utf-8", bufsize=1, cwd=str(ROOT),
            env={**_env(), "G1_VLA_WORK": str(Path.home() / "vla-work")},
        )

        def read_packets():
            try:
                for line in self.process.stdout:
                    if line.startswith("VLA_JSON "):
                        self.messages.put(json.loads(line[len("VLA_JSON "):]))
                    else:
                        self.log.write(line)
                        self.log.flush()
            finally:
                self.messages.put({"status": "PROCESS_EXITED"})

        self.reader = threading.Thread(target=read_packets, daemon=True)
        self.reader.start()
        self.info = self._receive(timeout)
        if self.info.get("status") != "READY":
            self.close()
            raise RuntimeError("VLA worker failed to load: " + json.dumps(self.info, ensure_ascii=False))
        self.info["load_seconds"] = round(time.monotonic() - started, 2)
        _write(self.folder / "policy_runtime.json", self.info)

    def _receive(self, timeout: float) -> dict:
        try:
            return self.messages.get(timeout=timeout)
        except queue.Empty:
            raise TimeoutError("VLA worker timed out; see policy_worker.log") from None

    def predict(self, observation: dict, instruction: str, output_file: Path,
                rng_seed: int | None = None) -> dict:
        if self.process.poll() is not None:
            raise RuntimeError("The VLA worker is not running")
        output_file = Path(output_file).resolve()
        if not output_file.is_relative_to(ROOT) or output_file.suffix != ".npy":
            raise ValueError("Action output must be a .npy inside the repository")
        started = time.monotonic()
        request = {"op": "predict", "observation": observation, "instruction": instruction,
                   "output_file": str(output_file)}
        if rng_seed is not None:
            request["rng_seed"] = rng_seed
        self.process.stdin.write(json.dumps(request, ensure_ascii=False) + "\n")
        self.process.stdin.flush()
        result = self._receive(300.0)
        result["request_wall_seconds"] = round(time.monotonic() - started, 3)
        self.calls += 1
        if result.get("status") != "PREDICTED":
            raise RuntimeError("VLA inference failed: " + json.dumps(result, ensure_ascii=False))
        return result

    def close(self) -> None:
        if self.process.poll() is None:
            try:
                self.process.stdin.write('{"op":"close"}\n')
                self.process.stdin.flush()
                self.process.wait(timeout=10)
            except (OSError, subprocess.TimeoutExpired):
                self.process.terminate()
                try:
                    self.process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()
        self.log.close()


def _env() -> dict:
    import os
    env = dict(os.environ)
    env["MUJOCO_GL"] = "egl"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env
