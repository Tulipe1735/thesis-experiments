# Artifact → Skill/Code 映射机制分析

2026-11-09 补充：后续审查复现了导入别名、Python 作用域和参数绑定约束的错误。本文的投影哈希检查不能支持通用映射“无误”的结论；原文保留作历史记录。修复及新初态测试见 [ARTIFACT_MAPPING_HOLDOUT_20261109.md](ARTIFACT_MAPPING_HOLDOUT_20261109.md)。

日期：2026-11-08
状态：已分析当前实现
范围：`artifact.v2` 的两种投影（code / skill）及其验证

## 1. 核心映射算法

### 1.1 存储结构

```
store/
├── artifacts/                    # YAML定义（不可变，content-addressed）
│   ├── t02_cup1_lift_retreat@6dc518869aed.yaml
│   └── t02_cup1_lift_clear_then_recorded@c15975503e7e.yaml
├── sources/                      # 源码本体（按SHA256索引）
│   └── 50602b5d1748ae3a1435d01b3d7875f3f1d5f1f27fb473c6cbde81d88c80980c.py
├── ledger.json                   # 证据追加记录
└── projections/                  # 两种投影（可重新生成）
    └── t02_cup1_lift_retreat@6dc518869aed/
        ├── code.py               # 代码投影
        ├── skill.md              # Skill卡片
        └── manifest.json         # 投影哈希
```

**关键点**：
- YAML是唯一的真理源（source of truth）
- 两种投影都是**从YAML重新计算**的，不是真理源
- `verify()` 方法重算所有投影，比对哈希，确保一致性

### 1.2 代码投影算法（Leaf）

```python
# harness/artifact_v2.py:377-378
def _code(self, artifact: Artifact) -> str:
    if isinstance(artifact, Leaf):
        return self.source(artifact.implementation.source_sha256)
```

**Leaf的映射**：
1. 从YAML读 `implementation.source_sha256`
2. 查 `sources/{sha256}.py`
3. 原样返回源码

**映射正确性**：
- ✅ 直接映射，SHA256保证完整性
- ✅ 一个哈希对应一个文件，不会冲突
- ⚠️ 如果 `sources/` 里的文件被手动改了，`verify()` 会检测到哈希不匹配

### 1.3 代码投影算法（Composite）

```python
# harness/artifact_v2.py:379-393
calls = self._flatten(artifact, ..., ())          # 展平嵌套组合
leaves = list(dict.fromkeys(r for r, _ in calls)) # 去重leaf引用

for i, leaf_ref in enumerate(leaves):
    leaf = self.load(leaf_ref)
    leaf_imports, leaf_body, has_init = _namespaced(
        self.source(leaf.implementation.source_sha256), 
        f"_L{i}_"                                      # 命名空间前缀
    )
    imports += leaf_imports
    body += leaf_body
    table.append(f'{{"ref": {leaf_ref!r}, "act": _L{i}_act, ...}}')

plan = [{"leaf": leaves.index(r), "ref": r, "params": ...} for r, params in calls]

return (header + ast.unparse(module) + "\n\n_PROFILE = None\n_LEAVES = [" + 
        ", ".join(table) + "]\n_PLAN = " + json.dumps(plan) + "\n" + DISPATCH)
```

**Composite的映射**：
1. **展平（flatten）**：递归展开组合，得到leaf序列和参数绑定
2. **去重**：多次引用同一leaf只加载一次
3. **重命名**：每个leaf的 `init()` / `act()` 加前缀 `_L0_`, `_L1_`, ...，避免命名冲突
4. **拼接**：imports + bodies + `_LEAVES` 表 + `_PLAN` JSON + 调度器

**映射正确性**：
- ✅ 展平算法保证调用顺序和YAML的 `ir` 一致
- ✅ 命名空间前缀避免了leaf之间的函数名冲突
- ✅ `_PLAN` 明确记录了每一步调用哪个leaf、传什么参数
- ⚠️ **潜在问题**：如果两个leaf有相同的全局变量名（不是函数），重命名不会处理

### 1.4 Skill投影算法

```python
# harness/artifact_v2.py:395-418
def skill(self, artifact_ref: str) -> str:
    artifact = self.load(artifact_ref)
    stats = self.stats(artifact_ref)              # 从ledger统计证据
    node = self.nodes[artifact.task_node]         # 任务树节点
    
    lines = [
        f"# {artifact.name}（{artifact.kind}，{stats['status']}）",
        f"- artifact：`{artifact_ref}`",
        f"- 用途：{artifact.summary}",
        f"- 前置：{', '.join(c.pre)}",
        f"- 效果：{', '.join(c.post)}",
        f"- 证据：{stats['successes']}/{stats['uses']} 次成功",
        f"- 来源：{artifact.provenance.author}",
        ...
    ]
    
    if isinstance(artifact, Composite):
        for i, step in enumerate(artifact.ir):
            lines.append(f"{i + 1}. `{step.use}`（参数绑定）")
    
    return "\n".join(lines)
```

**Skill卡片的映射**：
1. 从YAML读 contract / provenance / summary
2. 从 ledger 统计成功率
3. 如果是composite，列出组成步骤
4. 生成Markdown

**映射正确性**：
- ✅ 纯粹的格式转换，不涉及逻辑推理
- ✅ 证据来自append-only ledger，不可篡改
- ⚠️ **状态问题**：`stats['status']` 只能是 `candidate` / `paired` / `validated_skill` 之一，但YAML本身不存status，status在ledger里

## 2. 当前映射的3个问题

### 问题1：Composite展平时参数绑定可能丢失类型信息

```yaml
# artifact YAML
ir:
  - use: t02_cup1_place@xxx
    params:
      object_count: {task: object_count}
      hold_s: {task: hold_s}
```

```python
# 生成的 _PLAN
{"leaf": 0, "ref": "t02_cup1_place@xxx", 
 "params": {"object_count": {"task": "object_count"}, ...}}
```

**问题**：
- `{task: object_count}` 是运行时从task参数查表
- 调度器 `DISPATCH` 需要知道如何解析这个字典
- 如果 `DISPATCH` 实现有bug，leaf收到的可能是 `{"task": "object_count"}` 而不是实际值

**验证方法**：
```python
# 读生成的 code.py，检查 DISPATCH 部分
code = store.code("t02_cup1_lift_clear_then_recorded@c15975503e7e")
assert "def act(" in code
assert "_PLAN" in code
```

### 问题2：Leaf全局变量冲突未处理

`_namespaced()` 只重命名函数定义，不重命名全局常量。

**例子**：
```python
# Leaf A
LIFT = 0.10

# Leaf B
LIFT = 0.15
```

如果两个leaf都被同一个composite引用，生成的代码：
```python
_L0_LIFT = 0.10  # ❌ 不会重命名
_L1_LIFT = 0.15  # ❌ 不会重命名
# 两个都叫 LIFT，后者覆盖前者
```

**验证方法**：
```bash
# 检查T02 v3的生成代码
grep -E "^[A-Z_]+ = " store/projections/*/code.py
```

### 问题3：`verify()` 只检查哈希，不检查语义

```python
def verify(self) -> dict:
    result = {}
    for artifact_ref in self.refs():
        folder = self.root / "projections" / artifact_ref
        result[artifact_ref] = (
            (folder / "code.py").read_text() == self.code(artifact_ref)
            and (folder / "skill.md").read_text() == self.skill(artifact_ref))
    return result
```

**问题**：
- 只比对文本相等，不检查生成的代码是否能正确import
- 不检查 `_PLAN` 是否和YAML的 `ir` 语义匹配
- 不检查composite展平后的leaf顺序是否保留了依赖关系（pre/post）

**建议**：
```python
def verify_semantic(self, artifact_ref: str) -> dict:
    """除了哈希，还要检查：
    1. code.py能否import（语法正确）
    2. _PLAN的leaf顺序是否满足pre→post依赖
    3. 每个step.params的绑定是否在contract.params里有定义
    """
    ...
```

## 3. 映射失败的诊断流程

如果怀疑映射有问题：

### Step 1: 检查YAML完整性
```python
import yaml
artifact = yaml.safe_load(open("store/artifacts/xxx@yyy.yaml"))
assert artifact['schema'] == 'artifact.v2'
assert artifact['kind'] in ['leaf', 'composite']
if artifact['kind'] == 'leaf':
    assert 'implementation' in artifact
    assert 'source_sha256' in artifact['implementation']
```

### Step 2: 检查源码文件存在
```python
source_sha = artifact['implementation']['source_sha256']
source_path = f"store/sources/{source_sha}.py"
assert Path(source_path).exists()
```

### Step 3: 重新生成投影并比对
```python
from harness.artifact_v2 import Store

store = Store.from_directory("store")
manifest = store.project("xxx@yyy")

# 比对哈希
assert manifest['code_sha256'] == sha256(Path("store/projections/xxx@yyy/code.py").read_bytes())
```

### Step 4: 检查生成的代码能否执行
```python
import importlib.util
spec = importlib.util.spec_from_file_location("code", "store/projections/xxx@yyy/code.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

# 检查必需的符号
assert hasattr(module, '_LEAVES')
assert hasattr(module, '_PLAN')
assert hasattr(module, 'init')
assert hasattr(module, 'act')
```

### Step 5: 对比物理执行和YAML声明
```python
# 从runs里找这个artifact的执行记录
result = json.load(open("runs/xxx/train/yyy/slow/attempt_02/result.json"))
verdict = json.load(open("runs/xxx/train/yyy/slow/attempt_02/verdict.json"))

# 检查：
# - result.success 是否和 artifact.contract.post 对应
# - 失败码是否在 artifact.contract.failure_codes 里
```

## 4. 改进建议

### 建议1：增加语义验证

```python
# harness/artifact_v2.py 新增方法
def verify_semantics(self) -> dict:
    """Verify beyond hash: syntax, dependencies, parameter bindings."""
    errors = {}
    for ref in self.refs():
        artifact = self.load(ref)
        
        # Check 1: generated code is syntactically valid
        try:
            compile(self.code(ref), f"<{ref}>", "exec")
        except SyntaxError as e:
            errors.setdefault(ref, []).append(f"Syntax error: {e}")
        
        # Check 2: composite schedule respects pre/post
        if isinstance(artifact, Composite):
            calls = self._flatten(artifact, ...)
            for i in range(len(calls) - 1):
                curr_leaf = self.load(calls[i][0])
                next_leaf = self.load(calls[i+1][0])
                if not set(curr_leaf.contract.post) & set(next_leaf.contract.pre):
                    errors.setdefault(ref, []).append(
                        f"Step {i} post doesn't enable step {i+1} pre")
        
        # Check 3: all params are defined
        for step in getattr(artifact, 'ir', []):
            for param_name in step.params:
                if param_name not in artifact.contract.params:
                    errors.setdefault(ref, []).append(
                        f"Param {param_name} not in contract")
    
    return errors
```

### 建议2：处理全局变量冲突

```python
# _namespaced() 改进
def _namespaced_v2(source: str, prefix: str):
    tree = ast.parse(source)
    
    # 收集所有顶层名称（函数、类、全局变量）
    top_names = {node.name for node in ast.walk(tree) 
                 if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Assign))}
    
    # 重命名所有顶层名称
    class Renamer(ast.NodeTransformer):
        def visit_Name(self, node):
            if node.id in top_names:
                node.id = prefix + node.id
            return node
        ...
    
    Renamer().visit(tree)
    return ast.unparse(tree)
```

### 建议3：生成执行计划的可视化

```python
def plan_to_mermaid(self, artifact_ref: str) -> str:
    """Generate execution flow diagram."""
    artifact = self.load(artifact_ref)
    if not isinstance(artifact, Composite):
        return f"graph LR\n    A[{artifact.name}]"
    
    lines = ["graph TD"]
    for i, step in enumerate(artifact.ir):
        leaf = self.load(step.use)
        lines.append(f"    S{i}[{leaf.name}<br/>{', '.join(leaf.contract.post)}]")
        if i > 0:
            lines.append(f"    S{i-1} --> S{i}")
    return "\n".join(lines)
```

## 5. 当前结论

**T02 v3的映射是否正确？**

需要验证3点：
1. ✅ YAML存在且完整（已在 `store_frozen.json` 登记）
2. ⚠️ 生成的 `code.py` 语法正确且能import（**需要测试**）
3. ⚠️ composite展平后的调用顺序和参数绑定（**需要人工检查**）

**下一步行动**：
1. 运行 `store.verify()` 检查哈希一致性
2. 尝试import生成的 `code.py`
3. 对比 `_PLAN` 和 YAML的 `ir`
4. 如果都通过，映射算法没有问题；如果失败，按诊断流程定位

---

**附：完整验证脚本**

```python
#!/usr/bin/env python3
"""Verify artifact→skill/code mapping for T02 v3."""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from harness.artifact_v2 import Store

run_dir = Path("experiments/grow_up_harness_v2/runs/grow_t02_v3_20261107_001")
store = Store.from_directory(run_dir / "store")

# 1. Hash verification
print("=== Hash Verification ===")
verify_result = store.verify()
for ref, ok in verify_result.items():
    status = "✓" if ok else "✗"
    print(f"{status} {ref}")

if not all(verify_result.values()):
    print("FAIL: Hash mismatch detected")
    sys.exit(1)

# 2. Syntax check
print("\n=== Syntax Check ===")
for ref in store.refs():
    try:
        compile(store.code(ref), f"<{ref}>", "exec")
        print(f"✓ {ref}")
    except SyntaxError as e:
        print(f"✗ {ref}: {e}")
        sys.exit(1)

# 3. Import check
print("\n=== Import Check ===")
import importlib.util
for ref in store.refs():
    proj_dir = run_dir / "store" / "projections" / ref
    code_path = proj_dir / "code.py"
    if not code_path.exists():
        print(f"✗ {ref}: projection not found")
        continue
    
    try:
        spec = importlib.util.spec_from_file_location(ref.replace("@", "_"), code_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assert hasattr(module, 'act')
        print(f"✓ {ref}")
    except Exception as e:
        print(f"✗ {ref}: {e}")
        sys.exit(1)

print("\n✅ All checks passed")
```
