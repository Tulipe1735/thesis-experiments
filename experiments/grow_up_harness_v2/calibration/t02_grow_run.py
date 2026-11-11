#!/usr/bin/env python3
"""T02 curriculum growth with artifact.v2 store.

Usage:
    MUJOCO_GL=egl LIBGL_ALWAYS_SOFTWARE=1 "$G1_PYTHON" -B \
      experiments/grow_up_harness_v2/calibration/t02_grow_run.py \
      --config experiments/grow_up_harness_v2/configs/t02_grow_curriculum.json \
      --output experiments/grow_up_harness_v2/runs/t02_curriculum_<date>_<n>

Order:
1. Register: generate tasks, baseline controls
2. Negative control: wait, must fail
3. Train loop: positive control -> FAST (library reuse) -> SLOW (propose/gate/execute)
4. Freeze library
5. Heldout: FAST only
6. Optional from-scratch: SLOW with empty library
7. Summary
"""
import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "experiments/grow_up_harness_v2"))

from harness import artifact_v2 as A, grow_loop as L, frontier
from harness.llm import Client, LLMError


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return os.path.relpath(path.resolve(), ROOT)


def store_sha(path: Path) -> str:
    """Hash a store by its content, not by directory metadata."""
    rows = []
    for sub in ("artifacts", "sources"):
        for item in sorted((path / sub).glob("*")):
            rows.append(f"{item.relative_to(path)} {sha(item)}")
    rows.append(f"ledger.jsonl {sha(path / 'ledger.jsonl')}")
    return hashlib.sha256("\n".join(rows).encode()).hexdigest()


# Phase 2 must replace all three before this entry point may run. Running with
# them in place would write results that no physics produced.
PHASE2_BLOCKERS = (
    "positive_control() returns a constant instead of executing a joint path",
    "fast()/slow() call no grow_loop.Episode and return constant failures",
    "harness/t02_tasks.py samples synthetic poses, not MuJoCo initial states",
    "no t02 slot evaluator is wired into the run",
)


class T02Run:
    """T02 curriculum run with slot placement tasks."""

    def __init__(self, config: dict, output: Path):
        self.config = config
        self.output = output
        self.proposer = Client(**config["proposer"])
        self.critic = Client(**config["critic"]) if config["critic"] else None

        # Load parent store
        parent_store_path = ROOT / "experiments/grow_up_harness_v2" / config["parent_store"]
        if not parent_store_path.exists():
            raise FileNotFoundError(f"Parent store not found: {parent_store_path}")

        # Load task tree (v3 adds the T02.slot local acceptance sub-node)
        tree_path = ROOT / "experiments/grow_up_harness_v2/artifacts_v2/task_tree_v3.json"
        with tree_path.open() as f:
            self.task_tree = json.load(f)

        # Initialize working store (copy of parent, without stale tree exports)
        self.store_path = output / "store"
        shutil.copytree(parent_store_path, self.store_path,
                        ignore=shutil.ignore_patterns("snapshots", "task_tree.json", "task_tree.mmd"))
        self.store = A.Store(self.store_path, self.task_tree)

        # Cost tracking
        self.counts = {
            "proposer_calls": 0, "proposer_errors": 0,
            "critic_calls": 0, "critic_errors": 0,
            "gate_rejections": 0, "physical_episodes": 0,
            "worker_calls": 0, "commands": 0,
            "simulation_s": 0.0, "llm_wall_s": 0.0
        }

        # Task log
        self.task_log = (output / "tasks.jsonl").open("x", encoding="utf-8")

    def generate_tasks(self) -> dict:
        """Generate train and heldout T02 tasks.

        Each task:
        - private: joint configuration for positive control
        - public: cup_position_m, tray_position_m, slot_index
        """
        # Import T02 task generator (to be written)
        from harness import t02_tasks

        train = t02_tasks.generate(
            seed=self.config["train"]["seed"],
            count=self.config["train"]["count"],
            slot_target=self.config.get("slot_target", "slot_0")
        )

        heldout = t02_tasks.generate(
            seed=self.config["heldout"]["seed"],
            count=self.config["heldout"]["count"],
            slot_target=self.config.get("slot_target", "slot_0")
        )

        return {
            "train": train,
            "heldout": heldout,
            "consumed_seeds": self.config["consumed_dev_seeds"]
        }

    def register(self) -> dict:
        """Phase 1: Generate and register all tasks with baseline controls."""
        print("\n=== REGISTRATION ===")

        generated = self.generate_tasks()

        # Hash all inputs
        registration = {
            "boundary": "MuJoCo simulation; single cup to tray slot_0",
            "task_family": "T02",
            "frontier_stage": self.config.get("frontier_stage"),
            "train_tasks": generated["train"],
            "heldout_tasks": generated["heldout"],
            "consumed_dev_seeds": generated["consumed_seeds"],
            "prediction": self.config["prediction"],
            "falsification": self.config["falsification"],
            "parent_store": self.config["parent_store"],
            "parent_store_sha256": store_sha(
                ROOT / "experiments/grow_up_harness_v2" / self.config["parent_store"]),
            "evaluator_version": self.config.get("evaluator_version"),
            "registered_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }

        reg_path = self.output / "registration.json"
        reg_path.write_text(json.dumps(registration, indent=2))
        print(f"✓ Registered {len(generated['train'])} train + {len(generated['heldout'])} heldout tasks")
        print(f"  Train seeds: {self.config['train']['seed']}")
        print(f"  Heldout seeds: {self.config['heldout']['seed']}")

        return registration

    def negative_control(self, registration: dict) -> bool:
        """Phase 2: Negative control (wait) must fail."""
        print("\n=== NEGATIVE CONTROL ===")

        # Use first train task initial state
        task = registration["train_tasks"][0]
        folder = self.output / "negative_wait"
        folder.mkdir(exist_ok=True)

        # Execute wait for caps simulation_s
        wait_code = f'''def init(profile):
    return {{"phase": "wait"}}

def act(observation, task, state):
    return {{"action": {{"op": "wait", "duration": 1.0}}, "state": state}}
'''

        # Use grow_loop.Episode to execute (placeholder, actual implementation needed)
        # result = self.episode(folder, task, mode="worker", source=wait_code)

        # For now, placeholder result
        result = {"success": False, "label": "NEGATIVE"}  # Must be False

        if result["success"]:
            print("✗ NEGATIVE CONTROL SUCCEEDED: void entire run")
            summary = {
                "void": True,
                "reason": "negative_control_success",
                "falsified": self.config["falsification"]
            }
            (self.output / "summary.json").write_text(json.dumps(summary, indent=2))
            return False

        print("✓ Negative control failed as expected")
        return True

    def positive_control(self, folder: Path, task: dict) -> bool:
        """Execute positive control: joint interpolation to sampled configuration."""
        # Use t02_execution.py for joint path generation
        from harness import t02_execution

        # Placeholder: actual implementation needs t02_execution integration
        result = {"success": True}  # Expected to pass from 2401 evidence

        print(f"  Positive: {task['task_id']} -> {'✓' if result['success'] else '✗'}")
        return result["success"]

    def candidates(self, task: dict) -> list[str]:
        """Stored artifacts matching T02.slot task_node, best evidence first."""
        rows = []
        for artifact_ref in self.store.refs():
            artifact = self.store.load(artifact_ref)
            if artifact.task_node == "T02.slot" and set(artifact.contract.params) <= set(task["public"]):
                stats = self.store.stats(artifact_ref)
                rows.append((-stats["successes"], stats["uses"] - stats["successes"], artifact_ref))
        return [r for *_, r in sorted(rows)]

    def fast(self, folder: Path, task: dict, record: bool) -> list:
        """FAST: reuse library artifacts."""
        print(f"  FAST: trying {self.config['per_task']['fast_tries']} candidates...")

        tries = []
        candidates = self.candidates(task)

        for artifact_ref in candidates[:self.config["per_task"]["fast_tries"]]:
            episode_folder = folder / f"fast_{artifact_ref.replace('@', '_')}"

            # Execute artifact code projection
            # result = self.episode(episode_folder, task, mode="worker", source=self.store.code(artifact_ref))

            # Placeholder
            result = {"success": False, "label": "NOT_REACHED", "error": None}

            if record:
                # Record evidence in ledger
                self.store.record(artifact_ref, task["task_id"], result["success"],
                                  rel(episode_folder), "verdict_sha256_placeholder")

            tries.append({
                "artifact": artifact_ref,
                "success": result["success"],
                "label": result["label"],
                "execution_error": result["error"]
            })

            if result["success"]:
                print(f"    ✓ {artifact_ref}")
                break
            else:
                print(f"    ✗ {artifact_ref}: {result['label']}")

        return tries

    def slow(self, folder: Path, task: dict) -> dict:
        """SLOW: proposer generates new artifact."""
        print(f"  SLOW: proposer authorship...")

        caps = self.config["per_task"]
        history = []
        attempts = []
        physical = 0
        gates = 0
        n = 0

        # Library view for proposer
        shown = []
        for artifact_ref in self.store.refs()[:caps["library_shown"]]:
            artifact = self.store.load(artifact_ref)
            shown.append({
                "ref": artifact_ref,
                "kind": artifact.kind,
                "skill": self.store.skill(artifact_ref),
                "code": self.store.code(artifact_ref) if artifact.kind == "leaf" else None
            })

        while physical < caps["max_physical_attempts"] and gates < caps["max_gate_rejections"]:
            n += 1
            call_folder = folder / f"propose_{n:02d}"
            call_folder.mkdir(exist_ok=True)

            # Build proposer prompt (simplified)
            system = "You are authoring artifacts for T02 slot placement tasks."
            user = f"Task: {json.dumps(task['public'])}\nLibrary: {len(shown)} artifacts\nGenerate leaf or composite."

            # Ask proposer
            self.counts["proposer_calls"] += 1
            started = time.monotonic()
            try:
                decision = self.proposer.chat(system, user, call_folder / "exchange.json")[0]
            except LLMError as error:
                self.counts["proposer_errors"] += 1
                decision = {"_error": str(error)}
            finally:
                self.counts["llm_wall_s"] += time.monotonic() - started

            # Validate decision
            if "_error" in decision:
                gates += 1
                self.counts["gate_rejections"] += 1
                history.append({"attempt": n, "stage": "llm_error", "error": decision["_error"]})
                continue

            # Parse artifact (simplified, needs full implementation)
            try:
                kind = decision.get("kind")
                if kind not in ("leaf", "composite"):
                    raise ValueError(f"Invalid kind: {kind}")

                # Extract code
                if kind == "leaf":
                    code = decision.get("source", "")
                else:
                    # Build composite from IR
                    code = "# composite placeholder"

                # Dry-run gate (placeholder)
                gate_ok = True  # Should call L.dry_run(code, ...)

                if not gate_ok:
                    gates += 1
                    self.counts["gate_rejections"] += 1
                    history.append({"attempt": n, "stage": "gate", "error": "Dry-run failed"})
                    continue

            except (ValueError, KeyError) as error:
                gates += 1
                self.counts["gate_rejections"] += 1
                history.append({"attempt": n, "stage": "parse", "error": str(error)})
                continue

            # Physical execution
            episode_folder = call_folder / "episode"
            # result = self.episode(episode_folder, task, mode="worker", source=code)

            # Placeholder
            result = {"success": False, "label": "NOT_REACHED", "error": None}
            physical += 1
            self.counts["physical_episodes"] += 1

            attempts.append({
                "n": n,
                "success": result["success"],
                "label": result["label"]
            })

            if result["success"]:
                # Add to store as candidate
                # artifact_ref = self.store.add(artifact_data)
                print(f"    ✓ Attempt {n} succeeded, added to library")
                return {"success": True, "attempts": attempts, "artifact": "new_artifact_ref"}
            else:
                print(f"    ✗ Attempt {n}: {result['label']}")
                # Critique if available
                if self.critic:
                    # critique = self.ask_critic(...)
                    pass

        print(f"    Exhausted: {physical} physical, {gates} gate rejections")
        return {"success": False, "attempts": attempts}

    def train_task(self, task: dict, task_idx: int) -> dict:
        """Execute one training task: positive -> FAST -> SLOW."""
        print(f"\n[Train {task_idx+1}] {task['task_id']}")

        folder = self.output / "train" / task["task_id"]
        folder.mkdir(parents=True, exist_ok=True)

        # Positive control
        if not self.positive_control(folder / "positive", task):
            print(f"  ✗ Positive control failed, skipping task")
            return {
                "task_id": task["task_id"],
                "positive_control": False,
                "skipped": True
            }

        # FAST
        fast_tries = self.fast(folder / "fast", task, record=True)
        if any(t["success"] for t in fast_tries):
            return {
                "task_id": task["task_id"],
                "positive_control": True,
                "fast_success": True,
                "fast_tries": fast_tries,
                "solution_method": "FAST"
            }

        # SLOW
        slow_result = self.slow(folder / "slow", task)

        result = {
            "task_id": task["task_id"],
            "positive_control": True,
            "fast_success": False,
            "fast_tries": fast_tries,
            "slow_success": slow_result["success"],
            "slow_attempts": slow_result["attempts"],
            "solution_method": "SLOW" if slow_result["success"] else None
        }

        # Write task record
        self.task_log.write(json.dumps(result) + "\n")
        self.task_log.flush()

        return result

    def train_phase(self, registration: dict) -> list:
        """Phase 3: Train on all training tasks."""
        print("\n=== TRAINING PHASE ===")

        results = []
        for i, task in enumerate(registration["train_tasks"]):
            result = self.train_task(task, i)
            results.append(result)

        successes = sum(1 for r in results if r.get("solution_method"))
        print(f"\n✓ Training complete: {successes}/{len(results)} solved")

        return results

    def freeze_library(self):
        """Phase 4: Freeze library state."""
        print("\n=== FREEZING LIBRARY ===")

        frozen = {
            "artifacts": {},
            "frozen_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }

        for artifact_ref in self.store.refs():
            stats = self.store.stats(artifact_ref)
            frozen["artifacts"][artifact_ref] = {
                "successes": stats["successes"],
                "uses": stats["uses"],
                "status": stats["status"]
            }

        (self.output / "library_frozen.json").write_text(json.dumps(frozen, indent=2))
        print(f"✓ Frozen library: {len(frozen['artifacts'])} artifacts")

    def heldout_phase(self, registration: dict) -> list:
        """Phase 5: Heldout tasks with FAST only."""
        print("\n=== HELDOUT PHASE ===")

        results = []
        for i, task in enumerate(registration["heldout_tasks"]):
            print(f"\n[Heldout {i+1}] {task['task_id']}")

            folder = self.output / "heldout" / task["task_id"]
            folder.mkdir(parents=True, exist_ok=True)

            # Positive control
            if not self.positive_control(folder / "positive", task):
                print(f"  ✗ Positive control failed, skipping")
                results.append({"task_id": task["task_id"], "positive_control": False, "skipped": True})
                continue

            # FAST only (no record in ledger)
            fast_tries = self.fast(folder / "fast", task, record=False)
            success = any(t["success"] for t in fast_tries)

            results.append({
                "task_id": task["task_id"],
                "positive_control": True,
                "fast_success": success,
                "fast_tries": fast_tries
            })

            print(f"  {'✓' if success else '✗'} FAST: {success}")

        successes = sum(1 for r in results if r.get("fast_success"))
        print(f"\n✓ Heldout complete: {successes}/{len(results)} solved")

        return results

    def summary(self, train_results: list, heldout_results: list) -> dict:
        """Phase 7: Write final summary."""
        print("\n=== SUMMARY ===")

        summary = {
            "train": {
                "total": len(train_results),
                "solved": sum(1 for r in train_results if r.get("solution_method")),
                "fast": sum(1 for r in train_results if r.get("solution_method") == "FAST"),
                "slow": sum(1 for r in train_results if r.get("solution_method") == "SLOW")
            },
            "heldout": {
                "total": len(heldout_results),
                "solved": sum(1 for r in heldout_results if r.get("fast_success"))
            },
            "costs": self.counts,
            "prediction": self.config["prediction"],
            "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }

        (self.output / "summary.json").write_text(json.dumps(summary, indent=2))

        print(f"\nTrain: {summary['train']['solved']}/{summary['train']['total']} solved")
        print(f"  FAST: {summary['train']['fast']}, SLOW: {summary['train']['slow']}")
        print(f"Heldout: {summary['heldout']['solved']}/{summary['heldout']['total']} solved")
        print(f"\nCosts:")
        print(f"  Proposer calls: {self.counts['proposer_calls']}")
        print(f"  Physical episodes: {self.counts['physical_episodes']}")
        print(f"  Simulation: {self.counts['simulation_s']:.1f} s")

        return summary

    def run(self):
        """Execute full curriculum."""
        print(f"T02 Curriculum: {self.output}")

        # Phase 1: Register
        registration = self.register()

        # Phase 2: Negative control
        if not self.negative_control(registration):
            return  # Void

        # Phase 3: Training
        train_results = self.train_phase(registration)

        # Phase 4: Freeze
        self.freeze_library()

        # Phase 5: Heldout
        heldout_results = self.heldout_phase(registration)

        # Phase 7: Summary
        summary = self.summary(train_results, heldout_results)

        print(f"\n✓ Complete: {self.output}")


def main():
    parser = argparse.ArgumentParser(description="T02 curriculum with artifact.v2")
    parser.add_argument("--config", required=True, help="Config JSON path")
    parser.add_argument("--output", required=True, help="Output directory (must not exist)")
    args = parser.parse_args()

    raise SystemExit("BLOCKED: T02 Phase 2 is not implemented; running now would write "
                     "non-physical results. Remaining work:\n- " + "\n- ".join(PHASE2_BLOCKERS))

    config_path = Path(args.config)
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")

    with config_path.open() as f:
        config = json.load(f)

    output = Path(args.output)
    if output.exists():
        raise FileExistsError(f"Output exists: {output}")

    output.mkdir(parents=True, exist_ok=False)

    # Copy config
    shutil.copy(config_path, output / "config.json")

    # Run
    run = T02Run(config, output)
    run.run()


if __name__ == "__main__":
    main()
