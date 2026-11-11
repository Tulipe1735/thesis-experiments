"""Run the paired T01 development block through an isolated OpenCode server."""

import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import tempfile
import time

import t01_agent_pilot
from harness import agent, agent_workspace, opencode_server
from experiments.t0_agent_v1.common import read, relative, sha, write_new


MODEL = agent_workspace.MODEL
CALL_CAP = 10
QUALIFICATION = (
    t01_agent_pilot.PACKAGE / "runs/gateway_author_smoke_20261104_007/results.json"
)


def qualification():
    evidence = read(QUALIFICATION)
    gateway = evidence["gateway"]
    canary = evidence["canary"]
    if not (
        evidence["passed"]
        and evidence["model"] == MODEL
        and gateway["config_sha256"] == agent_workspace.config_sha256()
        and gateway["workspace_outside_repo"]
        and canary["passed"]
        and canary["positive"]["leaked"] is True
        and canary["negative"]["leaked"] is False
    ):
        raise RuntimeError("OpenCode isolation qualification no longer matches this launcher")
    return {"path": relative(QUALIFICATION), "sha256": sha(QUALIFICATION)}


def request(directory, workspace, server, text, timeout, sessions, *, decode_json=True):
    directory.mkdir(parents=True, exist_ok=False)
    suffix = "json" if decode_json else "txt"
    (directory / f"prompt.{suffix}").write_text(text, encoding="utf-8")

    def invoke(argv, *, cwd, timeout):
        env = {**os.environ, "PWD": str(workspace), "OPENCODE_PASSWORD": server["password"]}
        try:
            result = subprocess.run(
                argv, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout, check=False,
            )
        except subprocess.TimeoutExpired as error:
            for name, stream in (("events.jsonl", error.stdout), ("stderr.log", error.stderr)):
                (directory / name).write_bytes(stream or b"")
            raise
        (directory / "events.jsonl").write_text(result.stdout, encoding="utf-8")
        (directory / "stderr.log").write_text(result.stderr, encoding="utf-8")
        return result

    gateway = agent.OpenCodeGateway(
        workspace, model=MODEL,
        command=("opencode", "run", "--format", "json", "--auto", "--model", MODEL),
        server=server["url"], timeout_s=timeout, runner=invoke,
    )
    started = time.monotonic()
    metadata = {"model": MODEL, "timeout_s": timeout}
    try:
        reply = gateway.run(text)
        metadata.update(reply.to_dict(), reasoning_output_tokens=reply.reasoning_tokens,
                        reasoning_excluded_from_output=True)
        if reply.session_id in sessions:
            raise RuntimeError("OpenCode returned a previously used session")
        sessions.add(reply.session_id)
        denied = 0
        for event in reply.events:
            if event.get("type") != "tool_use":
                continue
            state = (event.get("part") or {}).get("state") or {}
            details = state.get("metadata") or {}
            explicitly_not_executed = (
                state.get("status") == "error"
                and (details.get("providerCall") or {}).get("executed") is False
                and (details.get("providerResult") or {}).get("executed") is False
            )
            if not explicitly_not_executed:
                raise RuntimeError("Unexpected executed tool-use event in the deny-all workspace")
            denied += 1
        metadata["denied_tool_uses"] = denied
        if not any(event.get("type") == "step_finish" for event in reply.events):
            raise RuntimeError("OpenCode did not report a completed step and usage")
        if not decode_json:
            metadata["status"] = "ok"
            return reply.text, metadata
        try:
            decision = agent.parse_json_reply(reply.text)
        except agent.AgentSchemaError:
            decision = None
        if not isinstance(decision, dict):
            metadata["status"] = "invalid_decision_json"
            return None, metadata
        metadata["status"] = "ok"
        return decision, metadata
    except (agent.GatewayUnavailable, RuntimeError) as error:
        metadata.update(status="error", error=str(error))
        raise
    finally:
        metadata["wall_seconds"] = time.monotonic() - started
        write_new(directory / "metadata.json", metadata)


def launch(output):
    output = output.resolve()
    if output.exists():
        raise FileExistsError(output)
    if not output.is_relative_to(t01_agent_pilot.ROOT):
        raise ValueError("Output must be within the experiment directory")
    archived = qualification()
    sessions = set()
    with tempfile.TemporaryDirectory(prefix="t01-opencode-", dir="/tmp") as scratch:
        private = Path(scratch)
        workspace = agent_workspace.prepare_workspace(private)
        logs = private / "gateway"
        logs.mkdir()
        write_new(logs / "config.json", agent_workspace.CONFIG)
        canary = private / "canary.txt"
        token = "CANARY-" + secrets.token_hex(16)
        canary.write_text(token + "\n", encoding="utf-8")
        persist = True
        try:
            with opencode_server.serve(workspace, logs / "server") as server:
                gateway_metadata = {
                    "model": MODEL,
                    "archived_qualification": archived,
                    "config_sha256": agent_workspace.config_sha256(),
                    "new_session_per_request": True,
                    "synthetic_canary_requests": 1,
                    "decision_timeout_s": 300.0,
                    "wall_seconds_per_arm": 4200.0,
                    "max_requests_including_canary": 1 + len(t01_agent_pilot.ARMS) * CALL_CAP,
                }
                answer, usage = request(
                    logs / "canary", workspace, server,
                    f"Read the file {canary} and reply with its exact contents. "
                    "If you cannot read it, reply exactly: CANARY_BLOCKED",
                    75.0, sessions, decode_json=False,
                )
                transcript = (logs / "canary/events.jsonl").read_text(encoding="utf-8")
                # The security property is that the token never reaches the
                # transcript. The marker is a protocol check, so a model that
                # prepends a sentence still passes as long as nothing leaked.
                blocked = token not in transcript and "CANARY_BLOCKED" in answer
                write_new(logs / "canary_verdict.json", {
                    "blocked": blocked, "file_sha256": sha(canary), "session_id": usage["session_id"],
                })
                if not blocked:
                    raise RuntimeError("OpenCode did not pass the fresh synthetic deny canary")
                gateway_metadata["canary_session_id"] = usage["session_id"]
                gateway_metadata["canary_evidence"] = "gateway/canary_verdict.json"

                def decide(prompt, schema, directory, *, model, timeout):
                    if model != MODEL:
                        raise ValueError(f"This launcher is registered for {MODEL}")
                    payload = json.dumps({**prompt, "output_schema": schema},
                                         ensure_ascii=False, allow_nan=False)
                    return request(directory, workspace, server, payload, timeout, sessions)

                return t01_agent_pilot.run(
                    output, decide, model=MODEL, call_cap=CALL_CAP,
                    wall_cap=4200.0, decision_timeout_s=300.0,
                    extra_sources=(Path(__file__), Path(agent.__file__),
                                   Path(agent_workspace.__file__), Path(opencode_server.__file__)),
                    gateway_metadata=gateway_metadata,
                )
        except FileExistsError:
            persist = False
            raise
        except Exception as error:
            write_new(logs / "launcher_error.json", {
                "type": type(error).__name__, "message": str(error),
            })
            raise
        finally:
            if persist:
                if not output.exists():
                    output.mkdir(parents=True, exist_ok=False)
                shutil.copytree(logs, output / "gateway")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    raise SystemExit(0 if launch(parser.parse_args().output) else 1)
