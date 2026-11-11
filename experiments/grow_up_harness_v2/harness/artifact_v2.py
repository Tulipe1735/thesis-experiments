"""artifact.v2: one YAML per artifact, two projections, two layers, one task tree.

A leaf artifact carries a contract and a pointer (sha256) to authored source.
A composite artifact carries an IR: ordered steps that call other artifacts
with bound parameters. From the YAML alone the store recomputes

- the code projection: a leaf's source byte for byte, or for a composite a
  single Worker program that runs its (flattened) leaves in order; and
- the skill projection: a Markdown card built from contract, IR and ledger.

Neither projection is a source of truth; ``verify`` recompiles and compares.
The YAML is immutable and content addressed (``name@digest12``). Evidence and
status live in an append-only ledger, so adding evidence never changes an
artifact's identity. ``artifact.v1`` (``artifact.py``) is untouched.
"""

from __future__ import annotations

import ast
import hashlib
import json
import math
from pathlib import Path
from typing import Literal, Union

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA = "artifact.v2"
NAME = r"^[a-z][a-z0-9_]{1,63}$"


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Param(Strict):
    type: Literal["vec3", "quat_xyzw", "float", "str"]
    description: str


class Contract(Strict):
    pre: tuple[str, ...]
    post: tuple[str, ...]
    params: dict[str, Param]
    failure_codes: tuple[str, ...]


class Scope(Strict):
    task_family: str
    initial_sha256: tuple[str, ...]
    plant_sha256: str


class Provenance(Strict):
    author: str
    parents: tuple[str, ...] = ()
    created_on: str
    note: str = ""


class Implementation(Strict):
    language: Literal["python"] = "python"
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class FromTask(Strict):
    task: str


class Literal_(Strict):
    literal: Union[float, str, tuple[float, ...]]


class Step(Strict):
    use: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}@[0-9a-f]{12}$")
    params: dict[str, Union[FromTask, Literal_]]


class _Artifact(Strict):
    schema_: Literal["artifact.v2"] = Field(alias="schema")
    name: str = Field(pattern=NAME)
    task_node: str
    summary: str
    contract: Contract
    scope: Scope
    provenance: Provenance


class Leaf(_Artifact):
    kind: Literal["leaf"]
    implementation: Implementation


class Composite(_Artifact):
    kind: Literal["composite"]
    ir: tuple[Step, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _task_refs(self):
        for i, step in enumerate(self.ir):
            for key, value in step.params.items():
                if isinstance(value, FromTask) and value.task not in self.contract.params:
                    raise ValueError(f"step {i} param {key} reads undeclared task param {value.task}")
        return self


Artifact = Union[Leaf, Composite]


def parse(data: dict) -> Artifact:
    kind = data.get("kind")
    if kind == "leaf":
        return Leaf.model_validate(data)
    if kind == "composite":
        return Composite.model_validate(data)
    raise ValueError(f"unknown artifact kind {kind!r}")


def canonical(artifact: Artifact) -> str:
    return json.dumps(artifact.model_dump(mode="json", by_alias=True), sort_keys=True,
                      separators=(",", ":"), ensure_ascii=False)


def ref(artifact: Artifact) -> str:
    return artifact.name + "@" + hashlib.sha256(canonical(artifact).encode()).hexdigest()[:12]


def sha_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


# --- composite code projection ----------------------------------------------------

def _top_level_names(tree: ast.Module) -> set[str]:
    names = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                for sub in ast.walk(target):
                    if isinstance(sub, ast.Name):
                        names.add(sub.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update(alias.asname or alias.name.split('.')[0] for alias in node.names)
    return names


def _bound_in(node) -> set[str]:
    """Names local to a function, lambda or comprehension (minus global/nonlocal)."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
        local = set()
        if not isinstance(node, ast.ClassDef):
            a = node.args
            local = {x.arg for x in a.posonlyargs + a.args + a.kwonlyargs}
            local |= {x.arg for x in (a.vararg, a.kwarg) if x is not None}
        body = node.body if isinstance(node.body, list) else [node.body]
    else:  # comprehension node
        return {n.id for g in node.generators for n in ast.walk(g.target) if isinstance(n, ast.Name)}
    declared = set()
    stack = list(body)
    while stack:
        sub = stack.pop()
        if isinstance(sub, (ast.Global, ast.Nonlocal)):
            declared |= set(sub.names)
        elif isinstance(sub, ast.Name) and isinstance(sub.ctx, (ast.Store, ast.Del)):
            local.add(sub.id)
        elif isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            local.add(sub.name)
            continue          # nested scopes are handled when visited
        elif isinstance(sub, (ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            continue
        elif isinstance(sub, ast.ExceptHandler) and sub.name:
            local.add(sub.name)
        elif isinstance(sub, (ast.Import, ast.ImportFrom)):
            local.update(alias.asname or alias.name.split('.')[0] for alias in sub.names)
        stack.extend(ast.iter_child_nodes(sub))
    return local - declared


class _Prefix(ast.NodeTransformer):
    """Rename one leaf's module-level names so several leaves share one module.

    Scope aware: a parameter or local that shadows a module name keeps its name,
    and keyword names in calls are never touched.
    """

    def __init__(self, names: set[str], prefix: str):
        self.names, self.prefix = names, prefix
        self.shadow: list[set[str]] = []
        self.globals: list[set[str]] = []
        self.kinds: list[str] = []

    def _new(self, name: str) -> str:
        if name in self.names:
            for i in reversed(range(len(self.shadow))):
                if self.kinds[i] == 'class' and i != len(self.shadow) - 1:
                    continue
                if name in self.globals[i]:
                    return self.prefix + name
                if name in self.shadow[i]:
                    return name
            return self.prefix + name
        return name

    def _push(self, node, kind='function'):
        declared = set()
        stack = list(node.body) if isinstance(node.body, list) else [node.body]
        while stack:
            sub = stack.pop()
            if isinstance(sub, ast.Global):
                declared.update(sub.names)
            elif not isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                stack.extend(ast.iter_child_nodes(sub))
        self.shadow.append(_bound_in(node))
        self.globals.append(declared)
        self.kinds.append(kind)

    def _pop(self):
        self.shadow.pop()
        self.globals.pop()
        self.kinds.pop()

    def visit_Name(self, node):
        node.id = self._new(node.id)
        return node

    def _scoped(self, node):
        self.shadow.append(_bound_in(node))
        self.globals.append(set())
        self.kinds.append('function')
        self.generic_visit(node)
        self._pop()
        return node

    def visit_FunctionDef(self, node):
        node.name = self._new(node.name)
        node.decorator_list = [self.visit(d) for d in node.decorator_list]
        node.args.defaults = [self.visit(d) for d in node.args.defaults]
        node.args.kw_defaults = [self.visit(d) if d is not None else None for d in node.args.kw_defaults]
        self._push(node)
        node.body = [self.visit(n) for n in node.body]
        self._pop()
        return node

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node):
        node.name = self._new(node.name)
        node.bases = [self.visit(n) for n in node.bases]
        node.keywords = [self.visit(n) for n in node.keywords]
        node.decorator_list = [self.visit(n) for n in node.decorator_list]
        self._push(node, 'class')
        node.body = [self.visit(n) for n in node.body]
        self._pop()
        return node

    def visit_Import(self, node):
        for alias in node.names:
            name = alias.asname or alias.name.split('.')[0]
            mapped = self._new(name)
            if mapped != name:
                alias.asname = mapped
        return node

    visit_ImportFrom = visit_Import

    def visit_Lambda(self, node):
        node.args.defaults = [self.visit(n) for n in node.args.defaults]
        node.args.kw_defaults = [self.visit(n) if n is not None else None for n in node.args.kw_defaults]
        self._push(node)
        node.body = self.visit(node.body)
        self._pop()
        return node

    def _comprehension(self, node):
        # Python evaluates the outermost iterable in the enclosing scope.
        node.generators[0].iter = self.visit(node.generators[0].iter)
        self.shadow.append(_bound_in(node))
        self.globals.append(set())
        self.kinds.append('function')
        for i, generator in enumerate(node.generators):
            if i:
                generator.iter = self.visit(generator.iter)
            generator.target = self.visit(generator.target)
            generator.ifs = [self.visit(n) for n in generator.ifs]
        if isinstance(node, ast.DictComp):
            node.key, node.value = self.visit(node.key), self.visit(node.value)
        else:
            node.elt = self.visit(node.elt)
        self._pop()
        return node

    visit_ListComp = visit_SetComp = visit_DictComp = visit_GeneratorExp = _comprehension

    def visit_Global(self, node):
        node.names = [self._new(n) for n in node.names]
        return node


def _namespaced(source: str, prefix: str, imports_to_prefix: set[str] | None = None) -> tuple[list[ast.stmt], list[ast.stmt], bool]:
    """Imports (unchanged) and the renamed body; whether the leaf defines init."""
    tree = ast.parse(source)
    imports = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    body = [n for n in tree.body if not isinstance(n, (ast.Import, ast.ImportFrom))]
    has_init = any(isinstance(n, ast.FunctionDef) and n.name == "init" for n in body)
    names = _top_level_names(tree)
    if imports_to_prefix is not None:
        imported = {a.asname or a.name.split('.')[0] for n in imports for a in n.names}
        names -= imported - imports_to_prefix
    renamer = _Prefix(names, prefix)
    return [renamer.visit(n) for n in imports], [renamer.visit(n) for n in body], has_init


DISPATCH = '''
def _bind(params, task):
    return {k: (task[v["task"]] if "task" in v else v["literal"]) for k, v in params.items()}


def init(profile):
    global _PROFILE
    _PROFILE = profile
    return {"step": 0, "started": False, "sub": None}


def act(observation, task, state):
    while state["step"] < len(_PLAN):
        step = _PLAN[state["step"]]
        leaf = _LEAVES[step["leaf"]]
        if not state["started"]:
            state["sub"] = leaf["init"](_PROFILE) if leaf["init"] is not None else None
            state["started"] = True
        result = leaf["act"](observation, _bind(step["params"], task), state["sub"])
        action = result["action"]
        state["sub"] = result.get("state")
        if action.get("op") == "done":
            state["step"] += 1
            state["started"] = False
            continue
        if action.get("op") == "fail":
            return {"action": {"op": "fail", "reason": "step %d %s: %s" % (state["step"], step["ref"], action.get("reason"))},
                    "state": state}
        return {"action": action, "state": state}
    return {"action": {"op": "done"}, "state": state}
'''


def _explicit_states(source: str) -> bool:
    """Whether every explicit act return already supplies the Worker's state key."""
    act = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == 'act')
    returns, stack = [], list(act.body)
    while stack:
        node = stack.pop()
        if isinstance(node, ast.Return):
            returns.append(node.value)
        elif not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            stack.extend(ast.iter_child_nodes(node))
    return bool(returns) and all(isinstance(value, ast.Dict) and any(
        isinstance(key, ast.Constant) and key.value == 'state' for key in value.keys) for value in returns)


class Store:
    """artifacts/ (YAML), sources/ (by sha256), ledger.jsonl, projections/, snapshots/."""

    def __init__(self, root: Path, tree: dict, *, read_only: bool = False):
        self.root, self.tree, self.read_only = root, tree, read_only
        self.ledger_path = root / "ledger.jsonl"
        if not read_only:
            for sub in ("artifacts", "sources", "projections", "snapshots"):
                (root / sub).mkdir(parents=True, exist_ok=True)
            self.ledger_path.touch()
        self.nodes = {n["id"]: n for n in tree["nodes"]}

    def _writable(self):
        if self.read_only:
            raise PermissionError('artifact store is read-only')

    # -- storage ---------------------------------------------------------------
    def load(self, artifact_ref: str) -> Artifact:
        path = self.root / "artifacts" / f"{artifact_ref}.yaml"
        artifact = parse(yaml.safe_load(path.read_text()))
        if ref(artifact) != artifact_ref:
            raise ValueError(f"{path} does not hash to its name")
        return artifact

    def refs(self) -> list[str]:
        return sorted(p.stem for p in (self.root / "artifacts").glob("*.yaml"))

    def source(self, digest: str) -> str:
        text = (self.root / "sources" / f"{digest}.py").read_text()
        if sha_text(text) != digest:
            raise ValueError(f"source {digest} is corrupt")
        return text

    def put_source(self, text: str) -> str:
        self._writable()
        digest = sha_text(text)
        path = self.root / "sources" / f"{digest}.py"
        if not path.exists():
            path.write_text(text)
        return digest

    def add(self, data: dict) -> str:
        """Validate, check references and task node, write once, project."""
        self._writable()
        artifact = self.check(data)
        artifact_ref = ref(artifact)
        path = self.root / "artifacts" / f"{artifact_ref}.yaml"
        if not path.exists():
            path.write_text(yaml.safe_dump(artifact.model_dump(mode="json", by_alias=True),
                                           sort_keys=False, allow_unicode=True))
            self._append({"event": "added", "ref": artifact_ref, "status": "candidate"})
        self.project(artifact_ref)
        return artifact_ref

    def _append(self, event: dict) -> None:
        self._writable()
        with self.ledger_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")

    def record(self, artifact_ref: str, task: str, success: bool, episode: str, verdict_sha256: str) -> None:
        self.load(artifact_ref)
        self._append({"event": "evidence", "ref": artifact_ref, "task": task, "success": success,
                      "episode": episode, "verdict_sha256": verdict_sha256})
        self.project(artifact_ref)

    def ledger(self, artifact_ref: str | None = None) -> list[dict]:
        rows = [json.loads(line) for line in self.ledger_path.read_text().splitlines() if line]
        return [r for r in rows if artifact_ref is None or r["ref"] == artifact_ref]

    def stats(self, artifact_ref: str) -> dict:
        evidence = [r for r in self.ledger(artifact_ref) if r["event"] == "evidence"]
        status = [r["status"] for r in self.ledger(artifact_ref) if "status" in r][-1]
        return {"uses": len(evidence), "successes": sum(r["success"] for r in evidence), "status": status,
                "evidence": evidence}

    # -- projections -----------------------------------------------------------
    def _flatten(self, artifact: Artifact, binding: dict, seen: tuple) -> list[tuple[str, dict]]:
        """Leaf calls in order, with parameters bound to the outermost task."""
        missing = set(artifact.contract.params) - set(binding)
        if missing:
            raise ValueError(f"{artifact.name} lacks parameters {sorted(missing)}")
        if isinstance(artifact, Leaf):
            return [(ref(artifact), {k: binding[k] for k in artifact.contract.params})]
        if ref(artifact) in seen:
            raise ValueError(f"composite cycle through {ref(artifact)}")
        calls = []
        for step in artifact.ir:
            child = self.load(step.use)
            extra = set(step.params) - set(child.contract.params)
            if extra:
                raise ValueError(f"{step.use} has no parameters {sorted(extra)}")
            for key, value in step.params.items():
                expected = child.contract.params[key].type
                if isinstance(value, FromTask):
                    if artifact.contract.params[value.task].type != expected:
                        raise ValueError(f"{step.use} param {key} has incompatible task type")
                else:
                    literal = value.literal
                    valid = (isinstance(literal, str) if expected == 'str' else
                             isinstance(literal, (int, float)) and math.isfinite(literal) if expected == 'float' else
                             isinstance(literal, tuple) and len(literal) == (3 if expected == 'vec3' else 4)
                             and all(math.isfinite(x) for x in literal))
                    if not valid:
                        raise ValueError(f"{step.use} param {key} has incompatible literal for {expected}")
            bound = {k: (binding[v.task] if isinstance(v, FromTask) else v) for k, v in step.params.items()}
            calls += self._flatten(child, bound, seen + (ref(artifact),))
        return calls

    def check(self, data: dict) -> Artifact:
        """Every check ``add`` makes, without writing anything."""
        artifact = parse(data)
        if artifact.task_node not in self.nodes:
            raise ValueError(f"task_node {artifact.task_node!r} is not in task tree {self.tree['version']}")
        if isinstance(artifact, Leaf):
            self.source(artifact.implementation.source_sha256)
        else:
            self._flatten(artifact, {name: FromTask(task=name) for name in artifact.contract.params}, ())
        for parent in artifact.provenance.parents:
            self.load(parent)
        return artifact

    def preview_code(self, data: dict) -> str:
        """Code projection of an artifact that is not (yet) in the store."""
        return self._code(self.check(data))

    def code(self, artifact_ref: str) -> str:
        return self._code(self.load(artifact_ref))

    def _code(self, artifact: Artifact) -> str:
        if isinstance(artifact, Leaf):
            return self.source(artifact.implementation.source_sha256)
        calls = self._flatten(artifact, {name: FromTask(task=name) for name in artifact.contract.params}, ())
        leaves = list(dict.fromkeys(r for r, _ in calls))
        imports, body, table = [], [], []
        explicit_states = True
        import_bindings = {}
        for leaf_ref in leaves:
            leaf = self.load(leaf_ref)
            for node in ast.parse(self.source(leaf.implementation.source_sha256)).body:
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    for alias in node.names:
                        name = alias.asname or alias.name.split('.')[0]
                        origin = (node.module if isinstance(node, ast.ImportFrom) else None, alias.name)
                        import_bindings.setdefault(name, set()).add(origin)
        conflicts = {name for name, origins in import_bindings.items() if len(origins) > 1}
        for i, leaf_ref in enumerate(leaves):
            leaf = self.load(leaf_ref)
            source = self.source(leaf.implementation.source_sha256)
            explicit_states = explicit_states and _explicit_states(source)
            leaf_imports, leaf_body, has_init = _namespaced(source, f"_L{i}_", conflicts)
            imports += [n for n in leaf_imports if ast.unparse(n) not in {ast.unparse(m) for m in imports}]
            body += leaf_body
            table.append(f'{{"ref": {leaf_ref!r}, "act": _L{i}_act, "init": {f"_L{i}_init" if has_init else "None"}}}')
        plan = [{"leaf": leaves.index(r), "ref": r,
                 "params": {k: v.model_dump(mode="json") for k, v in params.items()}} for r, params in calls]
        header = f'"""Code projection of {ref(artifact)} (artifact.v2). Generated; do not edit."""\n'
        module = ast.Module(body=imports + body, type_ignores=[])
        # Worker retains state when an act reply omits it. Keep historical text
        # for leaves whose returns statically provide state on every path.
        dispatch = DISPATCH if explicit_states else DISPATCH.replace(
            'state["sub"] = result.get("state")', 'state["sub"] = result.get("state", state["sub"])')
        return (header + ast.unparse(module) + "\n\n_PROFILE = None\n_LEAVES = [" + ", ".join(table) + "]\n"
                + "_PLAN = " + json.dumps(plan) + "\n" + dispatch)

    def skill(self, artifact_ref: str) -> str:
        artifact = self.load(artifact_ref)
        stats = self.stats(artifact_ref)
        node = self.nodes[artifact.task_node]
        c = artifact.contract
        lines = [f"# {artifact.name}（{artifact.kind}，{stats['status']}）", "",
                 f"- artifact：`{artifact_ref}`（{SCHEMA}）",
                 f"- 任务树节点：{node['id']} {node['title']}",
                 f"- 用途：{artifact.summary}",
                 f"- 前置（pre）：{', '.join(c.pre) or '无'}",
                 f"- 效果（post）：{', '.join(c.post) or '无'}",
                 f"- 失败码：{', '.join(c.failure_codes) or '无'}",
                 f"- 作用域：{artifact.scope.task_family}；初态 {len(artifact.scope.initial_sha256)} 个",
                 f"- 证据：{stats['successes']}/{stats['uses']} 次独立判定成功（候选状态不等于已验证）",
                 f"- 来源：{artifact.provenance.author}；parents {list(artifact.provenance.parents) or '无'}",
                 "", "| 参数 | 类型 | 说明 |", "|---|---|---|"]
        lines += [f"| {k} | {p.type} | {p.description} |" for k, p in c.params.items()]
        if isinstance(artifact, Composite):
            lines += ["", "## 组成（按顺序）", ""]
            for i, step in enumerate(artifact.ir):
                bound = ", ".join(f"{k}←{'task.' + v.task if isinstance(v, FromTask) else v.literal}"
                                  for k, v in step.params.items())
                lines.append(f"{i + 1}. `{step.use}`（{bound}）")
        return "\n".join(lines) + "\n"

    def project(self, artifact_ref: str) -> dict:
        self._writable()
        folder = self.root / "projections" / artifact_ref
        folder.mkdir(exist_ok=True)
        code, skill = self.code(artifact_ref), self.skill(artifact_ref)
        (folder / "code.py").write_text(code)
        (folder / "skill.md").write_text(skill)
        manifest = {"artifact": artifact_ref, "schema": SCHEMA,
                    "yaml_sha256": hashlib.sha256((self.root / "artifacts" / f"{artifact_ref}.yaml").read_bytes()).hexdigest(),
                    "ledger_rows": len(self.ledger(artifact_ref)),
                    "code_sha256": sha_text(code), "skill_sha256": sha_text(skill)}
        (folder / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
        return manifest

    def verify(self) -> dict:
        """Recompute every projection and compare with the stored files."""
        result = {}
        for artifact_ref in self.refs():
            folder = self.root / "projections" / artifact_ref
            result[artifact_ref] = (
                (folder / "code.py").read_text() == self.code(artifact_ref)
                and (folder / "skill.md").read_text() == self.skill(artifact_ref))
        return result

    # -- graph -------------------------------------------------------------------
    def task_tree(self) -> dict:
        """Tree nodes, artifacts attached to nodes, composition edges, pre/post edges."""
        artifacts = {r: self.load(r) for r in self.refs()}
        realizes = [{"artifact": r, "node": a.task_node} for r, a in artifacts.items()]
        composes = [{"from": r, "to": step.use, "order": i}
                    for r, a in artifacts.items() if isinstance(a, Composite) for i, step in enumerate(a.ir)]
        follows = [{"from": x, "to": y, "via": sorted(set(a.contract.post) & set(b.contract.pre))}
                   for x, a in artifacts.items() for y, b in artifacts.items()
                   if x != y and set(a.contract.post) & set(b.contract.pre)]
        return {"tree_version": self.tree["version"], "nodes": self.tree["nodes"], "realizes": realizes,
                "composes": composes, "follows": follows}

    def mermaid(self) -> str:
        graph = self.task_tree()
        used = {r["node"] for r in graph["realizes"]}
        keep = set()
        for node_id in used:                      # show realized nodes and their ancestors only
            while node_id:
                keep.add(node_id)
                node_id = self.nodes[node_id].get("parent")
        safe = lambda s: "n_" + "".join(ch if ch.isalnum() else "_" for ch in s)  # noqa: E731
        lines = ["flowchart TD"]
        for node in self.tree["nodes"]:
            if node["id"] in keep:
                lines.append(f'    {safe(node["id"])}["{node["id"]} {node["title"]}"]')
                if node.get("parent") in keep:
                    lines.append(f'    {safe(node["parent"])} --> {safe(node["id"])}')
        for row in graph["realizes"]:
            status = self.stats(row["artifact"])
            lines.append(f'    {safe(row["artifact"])}(["{row["artifact"]}<br/>{status["successes"]}/{status["uses"]} {status["status"]}"])')
            lines.append(f'    {safe(row["node"])} -.- {safe(row["artifact"])}')
        for row in graph["composes"]:
            lines.append(f'    {safe(row["from"])} -->|{row["order"] + 1}| {safe(row["to"])}')
        return "\n".join(lines) + "\n"

    def snapshot(self, label: str) -> dict:
        self._writable()
        snapshot = {"label": label, "artifacts": self.refs(), "ledger_rows": len(self.ledger()),
                    "ledger_sha256": hashlib.sha256(self.ledger_path.read_bytes()).hexdigest()}
        with (self.root / "snapshots" / f"{label}.json").open("x") as handle:
            json.dump(snapshot, handle, indent=1)
        (self.root / "task_tree.json").write_text(json.dumps(self.task_tree(), ensure_ascii=False, indent=1) + "\n")
        (self.root / "task_tree.mmd").write_text(self.mermaid())
        return snapshot
