# T02 Artifact V2 Curriculum 设计

日期：2026-11-07。状态：Phase 1 已执行（迁移与编译/派发验证通过），Phase 2 未执行。边界：MuJoCo 仿真，单杯入槽局部验收；本轮无物理回合。

本文是单杯入槽设计，Phase 2 未执行。实际跑通的三杯积累循环见 [T02_GROW_V2_20261107.md](T02_GROW_V2_20261107.md)。

## 目标

将 T02 (单杯入指定槽位) 接入 artifact.v2 + frontier 闭环，验证：
1. artifact.v1 → v2 迁移路径可行
2. composite 投影编译正确
3. FAST (库重放) + SLOW (模型提议) 训练流程完整
4. 冻结库在留出任务上复现

## 前置条件

- ✓ 2401 **整项三杯 T02** 的 motor replay 资格已确认：`runs/t02_replay_controls_20261107_002/results.json`，negative 失败、positive 成功；它不是单杯入槽的局部正例
- ✓ T02 执行入口已修复：`calibration/t02_execution.py` 绑定实际槽位，motion 返回非成功立即中止
- ✓ 槽位验收判据：托盘物理谓词 + 杯倾斜 ≤5° + 指定槽位距离 ≤15 mm + 末段保持 ≥1 s
- ✓ frontier.py 已注册 `t02_slot_placement` stage，task_node = "T02.slot"

## 执行记录（2026-11-07，Phase 1）

产物目录：`experiments/grow_up_harness_v2/runs/t02_v2_migration_20261107_001/`

- `migration.json`：Phase 1 迁移元数据，`composite_ref = t02_grasp_stub@439b464f5886`；新 leaf `grasp_close@5ae5bfa017ef`、`hand_open@22732f29f263`、`timed_wait@ccafd2a34ea0`。
- `verification.json`：`passed: true`。5 个 artifact 的 ref 与两套投影全部重算一致，composite 代码可编译，合成派发 30 次调用（20 次 set_joints、9 次 wait、1 次 done，5.7 仿真秒）并以 done 终止。这是派发检查，不是物理回合。
- 单元测试：`tests.test_t02_artifact_v2` 9/9 通过；全仓 `unittest discover` 252/252 通过。

本轮修掉的框架问题（均属“为跑通而改”，结果与用户原稿分列）：

1. 迁移脚本的 `REPO_ROOT` 多套了一层 `experiments/grow_up_harness_v2`，且手工用 YAML 字节算 ref；现改为 `Store.add`，由 canonical JSON 计算内容地址并校验任务树与引用。
2. `hand_open` 的 `task_node: B3.0` 不在任务树中；改为 `B3.2 分指合拢`。
3. `Task tree v2` 没有 `T02.slot`。新增 `artifacts_v2/task_tree_v3.json`，把 `T02.slot` 作为 `T02` 的局部验收子节点；不把整项 T02 记为已实现。
4. 原 leaf 每次 act 都返回同一条 `set_joints`（永不 done），且 2.0 s 超过 0.02–0.2 s 门禁。改为每次 ≤0.04 rad、0.2 s 的有界步进与显式 done。
5. `t02_grow_run.py` 的 `positive_control`/`fast`/`slow` 仍是常量占位，直接运行会写出无物理来源的结果；入口现改为 fail-closed，列出 Phase 2 阻塞项后退出。

关键边界：`t02_replay_controls_20261107_002` 的正例是**整项三杯 T02** 的 motor replay，不是单杯入指定槽位的局部正例。历史局部复算 `runs/t02_slot_audit_20261107_001/results.json` 为稳定入槽 0/9。因此本轮只声明“迁移与编译路径可行”，不声明 `t02_slot_placement` 的正例已建立；frontier 的 `ready` 状态需要 Phase 2 用真实槽位正例重新确认。

另一个占位绑定：composite 把 `cup_quaternion_xyzw` 直接传给 `reach_pose_hold` 当掌姿目标。杯子的朝向不等于抓取掌姿；Phase 2 必须换成独立的抓取朝向参数或由抓取规划产生。

## Phase 1: 迁移与验证（无模型调用）

### 1.1 Artifact 迁移

脚本：`calibration/t02_v2_migration_full.py`

**输入：**
- `artifacts/t02_slot_place.yaml` (v1)：工程配方，0/4 槽位成功
- `runs/artifact_v2_migration_20261107_001/store`：父 store，含 `reach_pose_hold@12ddba99e5ca`

**输出：**
- `runs/t02_v2_migration_20261107_001/store/`：新 store
- 新 leaf artifacts：
  - `grasp_close@<hash>`：从 v1 `close_angles` 提取
  - `hand_open@<hash>`：开手至 0.0
  - `timed_wait@<hash>`：定时等待
- composite artifact：`t02_grasp_stub@<hash>`
  - IR: reach_pose_hold → grasp_close → timed_wait
  - 最小可行组合，验证编译路径
  - 完整 T02 编舞（lift/carry/place/release）留给 Phase 2

**验证：**
```bash
cd experiments/grow_up_harness_v2
PYTHONDONTWRITEBYTECODE=1 "$G1_PYTHON" -B -m unittest tests.test_t02_artifact_v2 -v
```

检查点：
- [x] 所有 leaf 加载无错
- [x] composite 引用解析正确
- [x] code 投影编译为合法 Python
- [x] skill 投影生成 markdown

### 1.2 Baseline 登记

脚本：`calibration/t02_baseline_registration.py`（待编写）

**负对照：** wait 5 s，初态 2401
**正对照：** 2401 的 motor replay（已有证据，复用 `t02_replay_controls_20261107_002`）

**门禁：**
- 负对照被判成功 → 整批作废，写 `summary.json: {void: true}`
- 正对照失败 → 不进入训练段

## Phase 2: 训练段（FAST → SLOW）

脚本：`calibration/t02_grow_run.py`（骨架已写，物理入口 fail-closed，Phase 2 未实现）

配置：`configs/t02_grow_curriculum.json`

### 2.1 任务采样

- 训练：seed 4101–4104（4 个任务）
- 留出：seed 4201–4202（2 个任务）
- 消耗种子：2400, 2401, 2402, 4001–4004（不再使用）

每个任务采样：
- 私有：关节构型（正例对照用）
- 公开：杯位姿、托盘位姿、槽位索引（目前固定 slot_0）
- 写入 `registration.json`，哈希锁定

### 2.2 训练循环

对每个训练任务：

**1. 正例对照**
- 按私有构型做关节插值（`t02_execution.py` 路径）
- 失败 → 跳过该任务，不补抽新任务

**2. FAST（库重放）**
- 从 parent_store 查找 `task_node: T02.slot` 的 candidates
- 按成功次数排序，取前 `fast_tries=2` 条
- 原样执行（不调用模型），成功 → 进入下一任务

**3. SLOW（模型提议）**
- 仅在 FAST 全部失败时运行
- 提议模型输入：
  - 公开目标：杯位姿、托盘位姿、槽位索引
  - 身体几何：`body_geometry` from profile
  - 初始观测：`initial_state.npz` 的首帧
  - 库中前 `library_shown=3` 条 artifact 的 skill 卡片
  - 前几次失败反馈（若有）
- 干跑门禁：
  - 白名单检查：只允许调用 store 中 artifacts
  - 连续 `gate_steps=12` 次 act 调用，规则检查动作
  - 不通过 → 错误原文退回模型，不占物理回合
  - 通过 → 进入物理回合
- 物理回合：
  - 独立评价器判定：托盘 + 槽位双重条件
  - 失败 → 诊断模型（若有）生成反馈，记录 failure_category
  - 成功 → 代码入库，状态 `candidate`，记录 parents 和证据
- 上限：`max_physical_attempts=3`，`max_gate_rejections=4`

### 2.3 成本记录

每个任务分项记录：
- 提议模型调用：次数、token、耗时
- 诊断模型调用：次数、token、耗时（若启用）
- 接口拦截次数
- 物理回合次数
- Worker 调用次数
- 底层命令数
- 仿真秒数
- 墙钟时间

## Phase 3: 冻结与留出

### 3.1 冻结库

写 `library_frozen.json`：
- 训练段结束时库的完整快照
- 所有 candidate 的 ref、parents、证据、成功次数

### 3.2 留出段

seed 4201–4202，正例对照 + FAST only：
- 不调用提议模型
- 不往库里添加新代码
- 只从冻结库重放

### 3.3 从零对照组（可选）

若 `heldout_scratch: true`：
- 同一批留出任务（seed 4201–4202）
- 空库
- 直接走 SLOW 提议
- 用于对比库的复用价值

## Phase 4: 汇总

输出 `summary.json` + `tasks.jsonl`：

**汇总统计：**
- 训练成功数 / 4
- 留出成功数 / 2
- 从零成功数 / 2（若运行）
- 解出方式分布：fast / slow / scratch
- 总成本：模型调用、物理回合、仿真秒、墙钟

**逐任务记录（`tasks.jsonl`）：**
```json
{
  "task_id": "T02_4101",
  "seed": 4101,
  "positive_control": true,
  "fast_attempts": 2,
  "fast_success": false,
  "slow_attempts": 3,
  "slow_success": true,
  "solution_ref": "adaptive_slot_place@<hash>",
  "costs": {
    "proposer_calls": 3,
    "gate_rejections": 1,
    "physical_rounds": 3,
    "worker_calls": 87,
    "commands": 156,
    "simulation_s": 98.3,
    "wall_s": 142.7
  },
  "failure_categories": ["ORIENTATION", "NOT_HELD"]
}
```

## 预测与推翻条件

**预测（`configs/t02_grow_curriculum.json`）：**
> Negative fails. Positives pass (2401 known working from t02_replay_controls_20261107_002). Library exhausted before first SLOW. Composition-first authorship creates slot_offset variants from reach+close+place leaves.

**推翻条件（`falsification`）：**
- Negative 成功 → 整批作废
- 任何正例失败 → 跳过该任务
- 在库耗尽前成功 → SLOW 未执行（预测错误，记录但不作废）
- 在执行错误或证据不足后开放 authorship → 门禁失败

## 未做的事

1. **托盘 yaw 变换**：槽位偏移量假设托盘长轴 = 骨盆 x 轴，yaw ≠ 0 时槽位坐标变换尚未实现
2. **多杯视觉身份绑定**：当前 `--cup` 非默认会拒绝，视觉策略未绑定指定 cup_body
3. **诊断模型反馈**：`critic: null`，SLOW 失败后无诊断指导
4. **完整三杯 T02**：本轮只验证单杯入槽，三杯归集是后续组合任务
5. **slot 参数化**：当前固定 slot_0，未提升 `slot_index` 为 task param

## 没把握的点

1. **Leaf 粒度**：当前 Phase 1 只提取 reach+close+wait，完整 T02 编舞需要 lift / carry / place / release 等更多 leaves。是按 v1 每个 op 拆一个 leaf，还是合并为语义单元（如 `place_sequence`）？
2. **Proposer 输入格式**：提议模型看到的是 skill markdown 卡片还是 YAML IR？如何表达"组合现有 artifacts"？
3. **正例对照来源**：2401 的 motor replay 可复用为整项 T02 正例，但不能当槽位局部正例；4101–4104 的槽位正例需要新生成 joint paths，这些是在训练脚本里实时计算还是预先采样存储？

## 下一步

**Phase 1 已完成：**
1. ✓ 运行 `t02_v2_migration_full.py`，生成 store
2. ✓ 运行 `t02_v2_verify.py` 与 `test_t02_artifact_v2.py`，投影与派发检查通过
3. ✓ `t02_grow_run.py` 现有 7-phase 骨架，但执行入口 fail-closed

**Phase 2 进入条件（全部满足才可跑物理）：**
1. `t02_tasks.py` 改为从真实 MuJoCo 初态采样，保存实际对象 qpos 与初态哈希
2. `positive_control` 接入真实 joint path 执行与独立评价器；4101–4104 逐任务有正例
3. `fast`/`slow` 接入 `grow_loop.Episode`/T02 episode，记录独立 verdict 与证据哈希
4. 槽位评价器接入（托盘谓词 + 15 mm + 5° + ≥1 s，沿用 `t02_execution.stable_slot`）
5. 先用一个真实初态建立 `T02.slot` 局部正例；否则 frontier `ready` 不成立
6. 完整编舞 lift / carry / place / release 的 leaf 与 composite IR 扩展

## 交付文件

- `calibration/t02_v2_migration_full.py`：迁移脚本 ✓（已执行）
- `calibration/t02_v2_verify.py`：store/投影/派发验证，写 `verification.json` ✓（已执行）
- `calibration/t02_grow_run.py`：7-phase 骨架，物理入口 fail-closed（Phase 2 未实现）
- `calibration/t02_baseline_registration.py`：baseline 登记（未编写）
- `configs/t02_grow_curriculum.json`：配置 ✓
- `artifacts_v2/task_tree_v3.json`：v2 + `T02.slot` 局部子节点 ✓
- `harness/frontier.py`：已添加 t02_slot_placement stage（`ready` 待局部正例复核）
- `tests/test_t02_artifact_v2.py`：单测 ✓（9/9）
- `docs/research/T02_ARTIFACT_V2_CURRICULUM.md`：本文档 ✓
