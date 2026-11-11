"""Project one PolicyArtifact into executable-code and semantic-skill views.

The artifact is the fact source. The code view validates the observation keys and
delegates to a caller-supplied runtime; it does not silently load a model or run
physics. The skill view describes the same checkpoint, contract, training data
and evaluation. Neither view is a validation report or a success claim.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .contracts import PolicyArtifact

ROOT = Path(__file__).resolve().parents[3]


def _sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def generate_controller_code(policy: PolicyArtifact) -> str:
    """Project a parameterized controller; the parameter file is the checkpoint."""
    params = policy.checkpoint.get("parameters", {})
    controller = {"v4": "VisionGraspV4", "v5": "VisionGraspV5",
                  "v6": "VisionGraspV6", "v7": "VisionGraspV7",
                  "v8": "VisionGraspV8", "v9": "VisionGraspV9",
                  "v10": "VisionGraspV10"}.get(params.get("policy"), "VisionGraspV3")
    lines = [
        '"""Generated from the parameterized-controller PolicyArtifact. Do not edit."""',
        "",
        f"# artifact: {policy.id} v{policy.version}",
        f"# digest: {policy.digest()}",
        f"# status: {policy.status.value}",
        f"PARAMS = {params!r}",
        "",
        "",
        "def build(port, folder, memory_path=None):",
        f"    from grasp_optimization.grasp_policy_search import {controller}",
        f"    return {controller}(port, folder, memory_path=memory_path, params=PARAMS)",
        "",
    ]
    return "\n".join(lines)


def generate_code(policy: PolicyArtifact) -> str:
    if policy.policy_type == "parameterized_visual_tactile_controller":
        return generate_controller_code(policy)
    checkpoint = policy.checkpoint
    action = policy.action
    lines = [
        '"""Generated from the PolicyArtifact YAML/JSON record. Do not edit."""',
        "",
        f"# artifact: {policy.id} v{policy.version}",
        f"# digest: {policy.digest()}",
        f"# status: {policy.status.value}",
        f"CHECKPOINT = {checkpoint!r}",
        f"OBSERVATION_KEYS = {list(policy.observation_keys)!r}",
        f"JOINT_NAMES = {tuple(action['joint_names'])!r}",
        f"ACTION_UNITS = {action['units']!r}",
        f"ACTION_HORIZON = {int(action['horizon'])}",
        f"ACTION_FPS = {float(action['fps'])}",
        "",
        "",
        "def validate_observation(observation):",
        "    missing = [key for key in OBSERVATION_KEYS if key not in observation]",
        "    if missing:",
        "        raise ValueError('missing observation keys: ' + repr(missing))",
        "    return observation",
        "",
        "",
        "def act(runtime, observation):",
        '    """Call runtime.predict(checkpoint, observation, joint_names, horizon)."""',
        "    validate_observation(observation)",
        "    result = runtime.predict(CHECKPOINT['path'], observation, JOINT_NAMES, ACTION_HORIZON)",
        "    if not isinstance(result, dict) or 'actions' not in result:",
        "        raise ValueError('runtime.predict must return a dict with actions')",
        "    return result",
        "",
    ]
    return "\n".join(lines)


def generate_skill(policy: PolicyArtifact) -> str:
    action = policy.action
    training = policy.training
    evaluation = policy.evaluation
    lines = [
        f"# {policy.id} v{policy.version}",
        "",
        f"Generated from the PolicyArtifact record (digest `{policy.digest()}`). "
        "The code projection and this card are two views of one record.",
        "",
        f"- status: `{policy.status.value}`",
        f"- validation: `{policy.validation.value if policy.validation else 'none'}`",
        f"- policy type: `{policy.policy_type}`",
        f"- checkpoint: `{policy.checkpoint['path']}`",
        f"- checkpoint sha256: `{policy.checkpoint['sha256']}`",
        "",
        "## Contract",
        "",
        "Preconditions: " + ", ".join(f"`{item.name}`" for item in policy.pre),
        "Postconditions: " + ", ".join(f"`{item.name}`" for item in policy.post),
        "Failure exits: " + ", ".join(f"`{code}`" for code in policy.failure_codes),
        "",
        "## Observation and action",
        "",
        "Observation keys: " + ", ".join(f"`{key}`" for key in policy.observation_keys),
        f"Joint order: {len(action['joint_names'])} names; units `{action['units']}`; "
        f"horizon {action['horizon']} at {action['fps']} Hz.",
        "",
        "## Training",
        "",
        f"- dataset: `{training['dataset_path']}` (sha256 `{training['dataset_sha256']}`)",
        f"- train episodes: {list(training['train_episodes'])}; "
        f"validation episodes: {list(training['validation_episodes'])}",
        f"- objective: `{training['objective']}`",
        f"- optimizer steps: {training['optimizer_steps']}; selected step: {training['selected_step']}; "
        f"seed: {training['seed']}",
        "",
        "## Evaluation",
        "",
        f"- official evaluator: `{evaluation['official_evaluator']}`",
        f"- dense/diagnostic evaluator: `{evaluation['dense_evaluator']}`",
        f"- initial states: {', '.join(f'`{item}`' for item in evaluation['initial_states'])}",
        f"- metrics: {', '.join(f'`{item}`' for item in evaluation['metrics'])}",
        "",
        "## Limits",
        "",
    ]
    lines += [f"- {item}" for item in policy.limits]
    lines += ["", "A candidate remains a candidate until a ValidationReport is bound to this "
              "exact digest. Offline loss or a checkpoint file is not task success.", ""]
    return "\n".join(lines)


def compile_policy(policy: PolicyArtifact, output: Path) -> dict:
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    code = generate_code(policy)
    skill = generate_skill(policy)
    (output / "program.py").write_text(code, encoding="utf-8")
    (output / "SKILL.md").write_text(skill, encoding="utf-8")
    (output / "policy.json").write_text(json.dumps(policy.to_dict(), indent=2) + "\n",
                                         encoding="utf-8")
    manifest = {
        "artifact": {"id": policy.id, "version": policy.version, "digest": policy.digest(),
                     "kind": policy.kind, "status": policy.status.value},
        "checkpoint": dict(policy.checkpoint),
        "training": dict(policy.training),
        "evaluation": dict(policy.evaluation),
        "generated": {name: _sha(output / name)
                      for name in ("program.py", "SKILL.md", "policy.json")},
        "generator": {"path": str(Path(__file__).relative_to(ROOT)),
                      "sha256": _sha(Path(__file__))},
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest
