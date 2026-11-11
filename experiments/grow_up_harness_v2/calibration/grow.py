"""Config-driven accumulation run on generated reach tasks.

    MUJOCO_GL=egl LIBGL_ALWAYS_SOFTWARE=1 "$G1_PYTHON" -B \
      experiments/grow_up_harness_v2/calibration/grow.py \
      --config experiments/grow_up_harness_v2/configs/grow_reach_v1.json \
      --output experiments/grow_up_harness_v2/runs/grow_<date>_<n>

Order: register -> negative control -> per train task (positive control, FAST
artifact reuse, SLOW propose/gate/execute/critique) -> frozen held-out tasks
(store FAST only, and an optional from-scratch proposer arm). Every model
reply, gate result, episode and store snapshot stays in the output folder.

The library is an artifact.v2 store: FAST executes an artifact's code
projection, SLOW shows the proposer skill projections (and leaf code) and
accepts either a new leaf or a composite over stored artifacts. An artifact
enters the store only after an independent success.
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

from harness import artifact_v2 as A, grow_loop as L, task_generator, frontier  # noqa: E402
from harness.llm import Client, LLMError, LLMReplyError  # noqa: E402

TREE = ROOT / "experiments/grow_up_harness_v2/artifacts_v2/task_tree_v1.json"
REQUIRED = {"parent_store", "train", "heldout", "proposer", "critic", "caps", "per_task", "prediction", "falsification"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return os.path.relpath(path.resolve(), ROOT)


class Run:
    def __init__(self, config: dict, output: Path):
        self.config, self.output = config, output
        self.proposer = Client(**config["proposer"])
        self.critic = Client(**config["critic"]) if config["critic"] else None
        self.counts = {"proposer_calls": 0, "proposer_errors": 0, "critic_calls": 0, "critic_errors": 0,
                       "gate_rejections": 0, "physical_episodes": 0, "worker_calls": 0, "commands": 0,
                       "simulation_s": 0., "llm_wall_s": 0.}
        self.rows = (output / "tasks.jsonl").open("x", encoding="utf-8")

    def boundary(self) -> str:
        return "MuJoCo simulation; generated empty-hand reach-and-hold tasks on one saved T01 initial"

    def positive_description(self) -> str:
        return "privileged joint interpolation to the sampled configuration, per task"

    def tree_path(self) -> Path:
        return TREE

    def source(self) -> Path:
        return task_generator.SOURCE

    def generate_tasks(self, settings: dict) -> dict:
        return task_generator.generate(**settings)

    def proposer_system(self) -> str:
        return L.PROPOSER_SYSTEM

    def critic_system(self) -> str:
        return L.CRITIC_SYSTEM

    def before_store_add(self, store: A.Store, data: dict) -> None:
        """Called after an independent success, before the solving artifact enters the store."""

    def episode(self, folder: Path, task: dict, **kwargs) -> dict:
        result = L.Episode(folder, self.plan, self.config["caps"]).run(task["public"], **kwargs)
        self.counts["physical_episodes"] += 1
        self.counts["worker_calls"] += result["worker_calls"]
        self.counts["commands"] += result["commands"]
        self.counts["simulation_s"] += result["simulation_seconds"]
        print(json.dumps({"episode": rel(folder), "success": result["success"],
                          "label": result["facts"]["rule_label"]}), flush=True)
        return result

    def ask(self, client: Client, system: str, user: str, record: Path, kind: str):
        self.counts[f"{kind}_calls"] += 1
        started = time.monotonic()
        try:
            return client.chat(system, user, record)[0]
        except LLMError as error:
            self.counts[f"{kind}_errors"] += 1
            if not isinstance(error, LLMReplyError):
                raise
            return {"_error": str(error)}
        finally:
            self.counts["llm_wall_s"] += time.monotonic() - started

    def candidates(self, store: A.Store, task: dict) -> list[str]:
        """Stored artifacts of this task family whose parameters the task provides; best evidence first."""
        family = self.family["task_family"]
        rows = []
        for artifact_ref in store.refs():
            artifact = store.load(artifact_ref)
            if artifact.scope.task_family == family and set(artifact.contract.params) <= set(task["public"]):
                stats = store.stats(artifact_ref)
                rows.append((-stats["successes"], stats["uses"] - stats["successes"], artifact_ref))
        return [r for *_, r in sorted(rows)]

    def task_input(self, task: dict) -> dict:
        return {k: task["public"][k] for k in self.family["contract"]["params"]}

    def fast(self, folder: Path, task: dict, store: A.Store, record: bool) -> list:
        tries = []
        candidates = self.candidates(store, task)
        limit = len(candidates) if self.config.get("frontier_stage") else self.config["per_task"]["fast_tries"]
        for artifact_ref in candidates[:limit]:
            episode = folder / f"fast_{artifact_ref.replace('@', '_')}"
            result = self.episode(episode, task, mode="worker", source=store.code(artifact_ref),
                                  task_input=self.task_input(task))
            if record:
                store.record(artifact_ref, task["task_id"], result["success"], rel(episode),
                             sha(episode / "verdict.json"))
            tries.append({"artifact": artifact_ref, "success": result["success"],
                          "stage": "fast", "facts": result["facts"],
                          "label": result["facts"]["rule_label"],
                          "execution_error": result["error"],
                          "evidence_status": json.loads((episode / "verdict.json").read_text()).get("evidence_status")})
            if result["success"]:
                break
        return tries

    def library_view(self, store: A.Store | None, task: dict) -> list:
        if store is None:
            return []
        view = []
        refs = store.refs() if self.config.get("frontier_stage") else self.candidates(store, task)
        for artifact_ref in refs[:self.config["per_task"]["library_shown"]]:
            entry = {"ref": artifact_ref, "kind": store.load(artifact_ref).kind, "skill": store.skill(artifact_ref)}
            if entry["kind"] == "leaf":
                entry["code"] = store.code(artifact_ref)
            view.append(entry)
        return view

    def artifact_data(self, decision: dict, task: dict, store: A.Store | None) -> tuple[dict, str]:
        """The proposer reply as artifact.v2 data and its code projection; raises ValueError."""
        kind = decision.get("kind")
        if kind not in ("leaf", "composite") or (kind == "composite" and store is None):
            raise ValueError("reply kind must be 'leaf'" + ("" if store is None else " or 'composite'"))
        parents = decision.get("parents") or []
        if not isinstance(parents, list) or (parents and store is None):
            raise ValueError("parents must be a list of library refs")
        data = {"schema": A.SCHEMA, "kind": kind, "name": decision.get("name"),
                "task_node": self.family["task_node"], "summary": decision.get("summary") or "",
                "contract": self.family["contract"],
                "scope": {"task_family": self.family["task_family"],
                          "initial_sha256": [self.generated["source_initial"]["sha256"]],
                          "plant_sha256": self.generated["plant"]["sha256"]},
                "provenance": {"author": self.proposer.model, "parents": parents,
                               "created_on": task["task_id"], "note": str(decision.get("note") or "")[:2000]}}
        try:
            if kind == "leaf":
                source = decision.get("source")
                if not isinstance(source, str):
                    raise ValueError("leaf reply lacks a string field 'source'")
                data["implementation"] = {"language": "python", "source_sha256": A.sha_text(source)}
                A.parse(data)
                for parent in parents:
                    store.load(parent)
                return data, source
            data["ir"] = decision.get("ir")
            return data, store.preview_code(data)
        except (FileNotFoundError, KeyError, TypeError) as error:
            raise ValueError(f"{type(error).__name__}: {error}") from None

    def slow(self, folder: Path, task: dict, store: A.Store | None, *, previous_attempts=()) -> dict:
        caps = self.config["per_task"]
        shown = self.library_view(store, task)
        history, attempts = list(previous_attempts), []
        physical = gates = 0
        n = 0
        while physical < caps["max_physical_attempts"] and gates < caps["max_gate_rejections"]:
            n += 1
            call = folder / f"propose_{n:02d}"
            composition_first = bool(self.config.get("frontier_stage") and shown and n == 1)
            system = self.proposer_system() + ("\nThis attempt must compose existing artifacts: kind must be composite; do not author a new leaf yet." if composition_first else "")
            packet = json.loads(L.proposer_prompt(task["public"], self.plan, self.observation, shown, history,
                                                  self.family, store.task_tree() if store else None))
            decision = self.ask(self.proposer, system, json.dumps(packet, ensure_ascii=False), call, "proposer")
            try:
                if "_error" in decision:
                    raise ValueError(decision["_error"])
                if composition_first and decision.get("kind") != "composite":
                    raise ValueError("first frontier proposal must be a composite")
                data, code = self.artifact_data(decision, task, store)
            except ValueError as error:
                gates += 1
                self.counts["gate_rejections"] += 1
                history.append({"attempt": n, "stage": "reply", "error": str(error)[:1000]})
                attempts.append({"n": n, "stage": "reply", "error": str(error)[:300]})
                continue
            gate = L.dry_run(code, self.plan["body_geometry"], self.task_input(task), self.observation,
                             caps["gate_steps"])
            L.write_new(call / "gate.json", gate)
            if not gate["passed"]:
                gates += 1
                self.counts["gate_rejections"] += 1
                history.append({"attempt": n, "stage": "interface_gate", "error": gate["error"]})
                attempts.append({"n": n, "stage": "gate", "kind": data["kind"], "error": gate["error"]})
                continue
            physical += 1
            episode = folder / f"attempt_{n:02d}"
            result = self.episode(episode, task, mode="worker", source=code, task_input=self.task_input(task))
            attempt = {"n": n, "stage": "physical", "kind": data["kind"], "success": result["success"],
                       "label": result["facts"]["rule_label"], "source_sha256": result["source_sha256"]}
            if result["success"]:
                attempts.append(attempt)
                artifact_ref = None
                if store is not None:
                    if data["kind"] == "leaf":
                        store.put_source(code)
                    self.before_store_add(store, data)
                    artifact_ref = store.add(data)
                    if A.sha_text(store.code(artifact_ref)) != result["source_sha256"]:
                        raise RuntimeError("stored code projection differs from the executed code")
                    store.record(artifact_ref, task["task_id"], True, rel(episode), sha(episode / "verdict.json"))
                return {"solved": True, "attempts": attempts, "artifact": artifact_ref}
            visible = {k: v for k, v in result["facts"].items() if k not in ("rule_label", "max_contact_N")}
            feedback = {"attempt": n, "stage": "physical", "kind": data["kind"], "facts": visible}
            if self.critic:
                diagnosis = self.ask(self.critic, self.critic_system(),
                                     L.critic_prompt(task["public"], visible, L.last_actions(episode), code),
                                     folder / f"critic_{n:02d}", "critic")
                attempt["critic_class"] = diagnosis.get("failure_class")
                attempt["critic_agrees_with_rule"] = diagnosis.get("failure_class") == result["facts"]["rule_label"]
                feedback["critic"] = {k: diagnosis.get(k) for k in ("failure_class", "explanation", "advice")}
            history.append(feedback)
            attempts.append(attempt)
        return {"solved": False, "attempts": attempts, "artifact": None}

    def task(self, phase: str, task: dict, store: A.Store | None, *, learn: bool, scratch: bool) -> dict:
        folder = self.output / phase / task["task_id"]
        folder.mkdir(parents=True)
        before = dict(self.counts)
        row = {"phase": phase, "task_id": task["task_id"],
               "task_extent_m": task["private"].get("task_extent_m")}
        if "palm_travel_m" in task["private"]:
            row["palm_travel_m"] = task["private"]["palm_travel_m"]
        if self.config["controls"]["positive"] == "all":
            positive = self.episode(folder / "control_positive", task, mode="engineering",
                                    sampled_q=task["private"]["sampled_arm_q"])
            row["positive_control"] = positive["success"]
            if not positive["success"]:
                row["skipped"] = "positive control failed; task not used for agent arms"
                self.rows.write(json.dumps(row) + "\n")
                self.rows.flush()
                return row
        row["store_size_before"] = len(store.refs()) if store else 0
        row["fast"] = self.fast(folder, task, store, learn) if store and not scratch else []
        row["solved_by"] = "fast" if any(t["success"] for t in row["fast"]) else None
        gate = frontier.author_gate(row.get("positive_control", False), row["fast"],
                                    len(self.candidates(store, task)) if store else 0, attempted_all=True)
        if self.config.get("frontier_stage"):
            row["author_gate"] = gate
        may_author = not self.config.get("frontier_stage") or gate["open"]
        if row["solved_by"] is None and (learn or scratch) and may_author:
            slow = self.slow(folder / ("scratch" if scratch else "slow"), task, store if learn else None,
                             previous_attempts=row["fast"])
            row["slow"] = slow
            if slow["solved"]:
                row["solved_by"] = "scratch" if scratch else "slow"
        row["success"] = row["solved_by"] is not None
        row["cost"] = {k: self.counts[k] - before[k] for k in self.counts}
        if learn:
            store.snapshot("after_" + task["task_id"])
        self.rows.write(json.dumps(row) + "\n")
        self.rows.flush()
        return row

    def execute(self) -> dict:
        config, output = self.config, self.output
        if config.get("frontier_stage"):
            if config["controls"]["positive"] != "all" or config.get("evaluator_version") != L.local_reach_v3.VERSION:
                raise ValueError("frontier requires positive controls on every task and evaluator v3")
            train = frontier.generate(config["frontier_stage"], **config["train"])
            heldout = frontier.generate(config["frontier_stage"], **config["heldout"])
        else:
            train = self.generate_tasks(config["train"])
            heldout = self.generate_tasks(config["heldout"])
        overlap = {t["task_id"] for t in train["tasks"]} & {t["task_id"] for t in heldout["tasks"]}
        if overlap or config["train"]["seed"] == config["heldout"]["seed"]:
            raise ValueError("held-out seed must differ from train seed")
        self.generated, self.family = train, train["family"]
        instance = json.loads((self.source() / "instance.json").read_text())
        self.plan = {"instance": instance, "plant": train["plant"], "caps": config["caps"],
                     "evaluator_version": config.get("evaluator_version", "explicit-pose-replay-v2")}
        dependencies = [Path(L.__file__), Path(A.__file__), self.tree_path(), Path(task_generator.__file__), Path(L.local_reach.__file__), Path(L.local_reach_v3.__file__), Path(frontier.__file__),
                        Path(L.tp01.__file__), Path(__file__), Path(L.__file__).with_name("llm.py"),
                        Path(L.__file__).with_name("agent.py"),
                        ROOT / "experiments/grow_up_v2/isolation/worker.py",
                        ROOT / "experiments/grow_up_v2/isolation/_entry.py",
                        ROOT / "experiments/cordis_t01/worker.py", ROOT / "experiments/t0_agent_v1/runtime.py",
                        ROOT / "grasp_optimization/pantry_robot.py", ROOT / train["plant"]["path"],
                        self.source() / "initial_state.npz"]
        registration = {
            "date": time.strftime("%Y-%m-%d"), "status": "registered_before_physics",
            "boundary": self.boundary(),
            "config": config, "proposer": self.proposer.describe(),
            "critic": self.critic.describe() if self.critic else None,
            "parent_store": self._parent_record(),
            "frontier_curriculum": frontier.STAGES if config.get("frontier_stage") else None,
            "verdict": self.plan["evaluator_version"],
            "baselines": {"negative": "wait-only on first train task; success voids the run",
                          "positive": self.positive_description(),
                          "fallback": "none", "original_failure": "no prior agent run on these generated tasks",
                          "treatment": "proposer with growing library (train), frozen library FAST (held-out)",
                          "comparison": "from-scratch proposer on held-out tasks" if config["heldout_scratch"] else None},
            "train_tasks": train, "heldout_tasks": heldout,
            "prediction": config["prediction"], "falsification": config["falsification"],
            "dependencies": {rel(p): sha(p) for p in dependencies},
        }
        L.write_new(output / "registration.json", registration)
        negative = self.episode(output / "control_negative", train["tasks"][0], mode="wait")
        if negative["success"]:
            L.write_new(output / "summary.json", {"status": "void", "reason": "negative control succeeded"})
            return {"status": "void"}
        self.observation = json.loads((output / "control_negative/public_initial.json").read_text())
        self.plan["body_geometry"] = self._geometry()
        L.write_new(output / "body_geometry.json", self.plan["body_geometry"])
        store = self._store()
        rows = [self.task("train", t, store, learn=True, scratch=False) for t in train["tasks"]]
        frozen = store.snapshot("frozen")
        L.write_new(output / "store_frozen.json", frozen)
        held = [self.task("heldout_store", t, store, learn=False, scratch=False) for t in heldout["tasks"]]
        scratch = [self.task("heldout_scratch", t, None, learn=False, scratch=True)
                   for t in heldout["tasks"]] if config["heldout_scratch"] else []
        if store.snapshot("end")["ledger_sha256"] != frozen["ledger_sha256"]:
            raise RuntimeError("held-out phase changed the frozen store")
        self.rows.close()
        summary = summarize(rows, held, scratch, self.counts, store)
        L.write_new(output / "summary.json", summary)
        return summary

    def _parent_record(self) -> dict | None:
        parent = self.config["parent_store"]
        if parent is None:
            return None
        ledger = ROOT / parent / "ledger.jsonl"
        return {"path": parent, "ledger_sha256": sha(ledger), "artifacts": sorted(
            p.stem for p in (ROOT / parent / "artifacts").glob("*.yaml"))}

    def _store(self) -> A.Store:
        """A fresh store in the run; a parent store is copied in, never written."""
        root = self.output / "store"
        parent = self.config["parent_store"]
        if parent is not None:
            shutil.copytree(ROOT / parent, root, ignore=shutil.ignore_patterns("snapshots", "task_tree.*"))
        store = A.Store(root, json.loads(self.tree_path().read_text()))
        if parent is not None and sha(root / "ledger.jsonl") != self._parent_record()["ledger_sha256"]:
            raise RuntimeError("parent store ledger changed while copying")
        bad = [r for r, ok in store.verify().items() if not ok]
        if bad:
            raise RuntimeError(f"projections do not recompute: {bad}")
        store.snapshot("initial")
        return store

    def _geometry(self) -> dict:
        folder = self.output / "geometry_probe"
        folder.mkdir()
        L.write_new(folder / "instance.json", self.plan["instance"])
        robot = L.SavedInitialRobot(folder, self.plan["instance"], budget=1.,
                                    scene_path=ROOT / self.plan["plant"]["path"],
                                    initial_state=self.source() / "initial_state.npz")
        geometry = L.body_geometry(robot)
        robot.finish()
        return geometry


def summarize(train: list, held: list, scratch: list, counts: dict, store: A.Store) -> dict:
    def block(rows):
        used = [r for r in rows if "skipped" not in r]
        return {"tasks": len(rows), "skipped": len(rows) - len(used),
                "success": sum(r["success"] for r in used),
                "solved_by": {k: sum(r.get("solved_by") == k for r in used) for k in ("fast", "slow", "scratch")},
                "proposer_calls": sum(r["cost"]["proposer_calls"] for r in used),
                "physical_episodes_agent": sum(r["cost"]["physical_episodes"] for r in used)
                - sum(1 for r in used if "positive_control" in r),
                "per_task": [{"task": r["task_id"], "success": r["success"], "solved_by": r.get("solved_by"),
                              "proposer_calls": r["cost"]["proposer_calls"],
                              "store_size_before": r.get("store_size_before")} for r in used]}
    critic = [a for r in train + scratch for a in (r.get("slow") or {}).get("attempts", [])
              if "critic_class" in a]
    tree = store.task_tree()
    return {"status": "complete", "train": block(train), "heldout_store": block(held),
            "heldout_scratch": block(scratch) if scratch else None,
            "store": {"artifacts": store.refs(),
                      "kinds": {k: sum(store.load(r).kind == k for r in store.refs()) for k in ("leaf", "composite")},
                      "composes_edges": len(tree["composes"]), "follows_edges": len(tree["follows"]),
                      "task_nodes": sorted({r["node"] for r in tree["realizes"]})},
            "counts": counts,
            "critic_agreement": {"n": len(critic), "agree": sum(a["critic_agrees_with_rule"] for a in critic)},
            "note": "success = the independent evaluator named in registration.json verdict; store artifacts are candidates, none promoted"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    missing = REQUIRED - set(config)
    if missing:
        raise SystemExit(f"config lacks {sorted(missing)}")
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "config.json").write_bytes(args.config.read_bytes())
    print(json.dumps(Run(config, args.output).execute(), indent=1))


if __name__ == "__main__":
    main()
