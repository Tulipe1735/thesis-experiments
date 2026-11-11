"""Gateway smoke test: one real OpenCode call, no experiment episode.

Records the session, model, prompt/response hashes, tokens and cost. This is a
transport check, not an Agent task and not a physical episode.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "experiments/grow_up_harness_v2") not in sys.path:
    sys.path.insert(0, str(ROOT / "experiments/grow_up_harness_v2"))

from harness.agent import MODEL, OpenCodeGateway  # noqa: E402
from experiments.t0_agent_v1.common import write_new  # noqa: E402

PROMPT = "Reply with the single word: ready"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args(argv)

    output_root = Path(args.output).resolve()
    output_root.mkdir(parents=True, exist_ok=False)
    workspace = output_root / "workspace"
    gateway = OpenCodeGateway(workspace, model=MODEL, timeout_s=args.timeout)
    try:
        response = gateway.run(PROMPT)
    except Exception as error:  # keep the failure; never fabricate a reply
        summary = {
            "date": "2026-11-04",
            "boundary": "simulation",
            "kind": "opencode_gateway_smoke",
            "status": "FAILED",
            "model": MODEL,
            "error": {"type": type(error).__name__, "message": str(error)[:600]},
            "experiment_episodes": 0,
            "passed": False,
        }
        write_new(output_root / "results.json", summary)
        print("GATEWAY_SMOKE", summary["status"], summary["error"], flush=True)
        return 1
    summary = {
        "date": "2026-11-04",
        "boundary": "simulation",
        "kind": "opencode_gateway_smoke",
        "status": "PASSED",
        "model": MODEL,
        "session_id": response.session_id,
        "message_id": response.message_id,
        "prompt": PROMPT,
        "prompt_sha256": response.prompt_sha256,
        "response_text": response.text,
        "response_sha256": response.response_sha256,
        "input_tokens": response.input_tokens,
        "output_tokens": response.output_tokens,
        "cost": response.cost,
        "wall_time_s": response.wall_time_s,
        "experiment_episodes": 0,
        "passed": bool(response.session_id.startswith("ses") and response.text and response.input_tokens > 0),
    }
    write_new(output_root / "results.json", summary)
    print("GATEWAY_SMOKE", summary["status"], response.text, response.input_tokens, flush=True)
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
