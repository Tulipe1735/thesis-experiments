# Artifact 积累与评测改造

日期：2026-11-06。状态：评测诊断、抓杯控制器搜索、T01 工件投影实际执行与候选工件登记已完成；正式积累复用循环未完成。
边界：MuJoCo 仿真；当前任务为 P01 抓杯抬起稳持，尚未接续完整 T01 放盘；未训练新权重。

## 1. 结论先行

上一阶段的主要问题不是“agent 写代码不够努力”，而是三件事混在一起：

1. **artifact 只覆盖程序**：`Artifact` 能存 YAML→IR→code/skill，但不能存一个学到的 policy checkpoint，所以 VLA 只能散落在 `training/`，不能作为库条目被复用或组合。
2. **评测只有一个 1 mm 二值门**：它适合正式任务验收，但不适合训练/筛选。0.747 mm 和 0.876 mm 的回合在物理上只差不到 1 mm，却在二值标签里和“桌子外面”同为 0；这会让 IL/RL 失去梯度和近失样本。
3. **policy 优化被工程脚本替代**：上次 VLA 微调后 0/4，失败机理是合指阶段臂位漂移触发保护；继续改工程脚本或让 agent 重写整套流程，不会让 policy 学会“臂保持 + 手指闭合”。

上述 IL 方向已由用户纠正：当前优化目标是已有视觉／触觉抓杯控制器，执行情况见 §5。§2 的 1 mm 余量属于 T01 放盘诊断；当前 P01 使用 `grasp_optimization/verify_grasp.py` 的抬升、离桌、对向抓持与稳持判据，两项任务分别验收。

## 2. 评测：两层，不混用

### 2.1 官方层（不变）

`experiments/t0_agent_v1/tray_verify.py` 的 1 mm 杯底余量、底板承托、手/其他接触、倾角、速度、骨盆稳定和连续 1 s 保持全部保留。任何密集分、Qwen 或视频都不能改写 `independent_verification.json`。

### 2.2 密集层（新增，已执行）

实现：`experiments/grow_up_harness_v2/harness/dense_eval.py`；复算入口：`calibration/eval_dense_t01.py`；结果：`runs/t01_dense_eval_20261106_002/dense_eval.json`。

对 7 个已有官方标签的回合复算：

| 回合 | 官方 | relaxed-margin | near-miss | dense | 最终 margin |
|---|---|---:|---:|---:|---:|
| success_control | true | true | false | 0.999 | +6.160 mm |
| program_success | true | true | false | 0.999 | +6.457 mm |
| margin_0p747mm | false | true | true | 0.939 | +0.747 mm |
| margin_0p876mm | false | true | true | 0.940 | +0.876 mm |
| rim_lean | false | false | false | 0.450 | +0.316 mm，其他接触 1.17 N |
| negative_wait | false | false | false | 0.269 | −132.95 mm |
| code006_position | false | false | false | 0.269 | −98.95 mm |

这组结果说明：**“太严苛”损失的主要是训练信号，不是正式成功定义。** 两个 sub-mm 回合被保留为 `near_miss`，可进入课程/回放/奖励；边缘倾斜和桌外仍是低分。官方成功数仍为 2/7，没有放宽。

密集分只用于：
- IL/RL 的 reward shaping 或样本加权；
- 失败聚类和课程排序；
- 人工复核优先级。

不用于：正式晋升、论文成功率、替代独立评价器。

### 2.3 Qwen 的定位

已有审计（`runs/t01_evaluator_audit_20261106_001/vlm_judge.json`）显示 Qwen 3.5 4B 在 720 px 近景/俯视图上会误杀已知正例：它看杯口/把手，而不是杯底；还会把 0° 杯子说成倾斜。

本轮又做了一次**只看俯视、只问事实、不问 overall** 的校准：5 张 720 px 俯视图，`qwen3.5:4b`、temperature 0、结构化 JSON。结果（`runs/t01_qwen_topdown_20261106_001/triage_corrected.json`）：

- 5 次请求中 **2 次空/无效响应**（success_control、margin_0p747mm），不能把无响应算成“预测失败正确”；
- 3 个有效响应里，`cup_base_on_tray_floor` 2/3、`cup_base_inside_tray_rim` **1/3**、`cup_upright` 3/3、`hand_touching_cup` 1/3、`other_objects_touching_cup` 2/3；
- 已知正例 `program_success` 被说成“杯底不可见、手正在接触”；`rim_lean` 被说成“杯底在内框内、直立”（实际有其他物体接触/倾斜）。

原始 `triage.json` 的汇总把“空响应”误算成与负例一致；`triage_corrected.json` 保留原文件并只对有效响应计分。结论不变：**4B VLM 在 720 px 上不能可靠判 1 mm，俯视机位本身也救不了；它只能做粗筛/解释。** 这也说明“更精准”不能靠换 prompt，必须把 1 mm 交给几何/物理评价器。

可做的改造，不是让它判 1 mm：
- 相机：固定俯视 + 45° 近景 + 腕部视图；俯视以托盘为中心，加 1 cm 网格/托盘内框（仅诊断图，不进入策略）。
- 输出：只问可观察事实（杯底是否可见、在托盘底板上、是否越过内框、是否直立、手是否接触），允许 `unknown`；**不问 overall success**。
- 聚合：Qwen 只做粗筛/失败解释；物理量仍由 `tray_verify` 计算。校准报告混淆矩阵，不把单次 verdict 当标签。
- 如果要做 learned evaluator：用带物理标签的俯视分割/几何模型，而不是 4B VLM 的直接 yes/no。

这比继续调 prompt 更符合“更精准”：把 1 mm 交给几何，把语义/异常交给 VLM。

## 3. Artifact：policy 和 program 同库

### 3.1 已有实现

`experiments/grow_up_harness_v2/harness/contracts.py` 新增 `PolicyArtifact`，并接入同一 `Registry`；`harness/policy_artifact.py` 从同一记录生成 code 与 skill 两个投影。

`PolicyArtifact` 字段：

| 字段 | 作用 |
|---|---|
| `checkpoint.path/sha256` | 权重身份；不复制 1.2 GB 文件 |
| `policy_type` | `smolvla_flow_matching` / `mlp` / 未来 RL policy |
| `observation_keys` | 策略合法输入，防止训练/部署错位 |
| `action.joint_names/units/horizon/fps` | 动作语义、顺序、频率 |
| `training` | 数据路径/哈希、训练/验证 episodes、objective、步数、选中步、seed |
| `evaluation` | 官方评价器、密集评价器、初态、指标 |
| `pre/post/failure_codes` | 与程序技能相同的契约 |
| `status/validation` | candidate 不能声明验证等级；validated 必须绑定报告 |
| `limits/evidence` | 适用范围、失败与原始路径 |

### 3.2 已登记的第一个 policy

`runs/policy_artifact_cup_20261106_002/`：

- artifact：`policy_cup_fourview_sft` v1，digest `3be436d268e42c978888f490f8ff9c5838784c1e64a1ba1763bf2a0cdecad427`；
- checkpoint：`grasp_optimization/training/cup_fourview_sft_v1/best/model.safetensors`，SHA `bf8c08dc…`；
- 训练数据：`cup_fourview_v1`，episodes 0–3 训练、4–5 离线验证；700 步、选中 300；
- 物理结果：训练位置 1000 和新位置 1300–1303 三组均 0/4；
- 投影：同目录 `projection/program.py`、`SKILL.md`、`policy.json`、`manifest.json`；
- 状态：candidate，validation null；正式 op 表为空。

这个 artifact 的意义不是“VLA 会了”，而是：**checkpoint、训练数据、动作语义、契约、评价器和失败范围第一次被同一个 digest 绑定。** 以后可以按 ID/version/digest 复用或组合，而不是在 `training/` 里找一坨权重。

### 3.3 三类 artifact 的分工

| 类型 | 内容 | 对应 Skill2Real |
|---|---|---|
| `PolicyArtifact` | 学到的局部策略（IL/RL），带 checkpoint 与动作契约 | Cerebellum 的局部技能 |
| `Skill` / `Op` | 可执行程序/局部效果，带 pre/post/failure | Cerebellum 的可执行版本 |
| `Procedure` / 组合程序 | 引用冻结 artifact 的顺序/条件组合 | Brain 的任务组合 |

组合层只能引用**冻结的 ID/version/digest**，不能复制相似代码或重新训练一个近似 policy 冒充复用。

## 4. 积累循环：先局部，后组合

```text
任务缺口
  -> 选择局部效果（有独立物理判据）
  -> 采集/复用示范（工程教师或已有成功轨迹）
  -> 训练局部 policy（IL/RL）或写局部程序
  -> 同一初态/留出初态执行
  -> 官方 verdict + 密集分 + 失败分类
  -> ValidationReport（paired / repair_lineage / expanded）
  -> 写入 Registry（candidate -> validated）
  -> 组合层按冻结版本调用
  -> 新任务覆盖/复用/成本统计
```

关键约束：

- **一个候选只做一个局部效果**；不把“抓取+运输+放置”打包成一个候选。
- **训练与验证分离**：训练 demonstrations 只在练习集；新位置/新初态在运行前冻结。
- **官方与密集分开**：密集分可用于课程，但不能把 near-miss 写成成功。
- **复用按 digest**：后续任务记录 artifact ID/version/digest、对象绑定和实际调用；没有调用就不算复用。
- **组合要真实接续**：前段实际终态直接接后段，不插入隐藏复位；条件化测试单独标。
- **库规模按覆盖/连接/复用衡量**：不数文件、版本、seed 或日志。

这与 Skill2Real 的 PVG 两级结构相容：Cerebellum 学局部，Brain 在局部冻结后学组合；但我们的验证不是 LLM Governor 投票，而是**独立物理评价器 + 密集诊断 + 预登记对照**。他们的 126 条文本记忆可作外部先验（已导入 16 条），但不能替代本地执行。

## 5. 第一个 policy 优化：v2 抓杯控制器

### 5.1 为什么不是 VLA

目标是现有 `grasp_optimization/vision_grasp_v2.py`：头部 RGB-D + 本体 + 模拟触觉、在 seeds 1200–1207 上 7/8 的抓杯控制器。VLA checkpoint 只保留为负对照，不再训练。上一轮把“policy 优化”误写成 VLA 微调，方向错误，已撤回。

### 5.2 硬失败定位

seed 1206 的冻结 v2 失败不是视觉或触觉，而是 `ArmPlannerV2.select` 所有候选都在 `approach_open` 第 3 步出现 `max_joint_delta_rad > 0.5`，被连续性门槛拒绝；最终 `NO_REACHABLE_VISUAL_TARGET_PATH_V2`，0 cm 抬升。路径离散化是首个可检验参数。

### 5.3 方法：新版本参数搜索，不改冻结 v2

新增 `grasp_optimization/grasp_policy_search.py`：

- `ArmPlannerV3(ArmPlannerV2)`：只把路径步长 `step_m`、后撤距离 `behind_m`、高位 `high_z` 显式参数化；其余候选顺序、IK、连续性门槛、评测器不变。
- `VisionGraspV3(VisionGraspV2)`：沿用视觉/触觉流程，可切换 `adaptive / thumb_lead / simultaneous` 闭手。
- 评价：`verify_grasp.py` 的独立 `verified_success`，与控制器返回无关。
- 冻结 v2、`arm_planner.py`、验收器均未编辑；新实验目录排他创建。

实现边界：这些路径参数控制 **preflight**；继承的 `VisionGrasp.linear/approach` 仍使用 0.025 m 离散步长、0.13 m 后退与 0.30 m 高位。因此旧搜索结果不能解释为这些参数同步改变了实际执行路径。

### 5.4 已观察结果（开发，非新位置）

路径搜索 `runs/grasp_policy_search_20261106_002/`：12 组全部失败，但失败层变了。

- `step_m=0.025/0.020`：仍然无可达路径，和 v2 基线一致。
- `step_m=0.015/0.0125`：路径可达，接近、拇指/手指触觉门、2 cm 试提都通过；随后 12.5 cm 主抬升丢抓，杯子倾斜约 90°，最大抬升 6.57 cm。
- `behind_m=0.10`：`behind_high` IK 拒绝；`behind_m=0.16`：无可达路径；`high_z=0.34`：无可达路径；`high_z=0.26`：同样丢抓。

闭合搜索 `runs/grasp_policy_closure_20261106_001/`：固定 `step_m=0.015`，两条闭手都通过 seed 1206。

| 闭手 | 独立成功 | 最大抬升 | 连续保持 | 终态杯倾角 |
|---|---:|---:|---:|---:|
| `thumb_lead` | true | 11.75 cm | 1.60 s | 1.49° |
| `simultaneous` | true | 12.02 cm | 1.65 s | 3.56° |

这证明：**seed 1206 的失败可以沿“路径离散化 → 闭手保持”两层拆开修复**；`adaptive` 在 15% 闭合处停止会丢抓，`thumb_lead/simultaneous` 继续闭合能保留。

### 5.5 开发集上的 C0→C3 曲线

在 1200–1207（已消费开发集）上逐版本冻结评估：

| 版本 | 策略 | 成功 | 结论 |
|---|---|---:|---|
| C0 | v2 adaptive | 7/8 | 基线；1206 无路径/丢抓 |
| C1 | path step 0.015 + adaptive | 7/8 | 路径修好但 1206 仍丢抓，无净增益 |
| C2 | path + full close (thumb_lead) | 6/8 | 1206 修好但 1200/1201 回归，**拒绝** |
| C3 | path + selector + recovery（v6） | **8/8** | 只在 index<4 N 时 reopen/retreat/reapproach/full-close |

完整逐 seed 结果与 SVG：`runs/policy_artifact_grasp_recovery_20261106_001/curve.json`、`curve.svg`。C2 的负结果和 C3 的 8/8 是同一评测口径下的不同版本，不是补抽。

### 5.6 1400–1403：首次冻结测试与后续开发

在运行前登记、按同一批准区域均匀采样 4 个新位置（1400–1403），不做 IK/成功预筛：

| 策略 | 成功 | 失败 |
|---|---:|---|
| C0 v2 adaptive | 2/4 | 1400 触觉不足；1403 无路径 |
| C3 selector+recovery | 2/4 | 同样 1400/1403 |
| C4 portfolio：baseline + reset fallback | **3/4**（1 个条件化 reset） | 1403 无路径 |

C3 在这四个首次测试实例上未显示成功数增益；开发集 8/8 尚无迁移收益支持。此后 1400–1403 已用于诊断和修订，C4 的 3/4 属于开发结果，不能和首次冻结测试合并为未见迁移提升。C4 的具体证据：

- 1400 的 C4 单独技能：`preferred_yaw=0.2`、`offset=[0.03,-0.07,-0.052]`、从开始全闭，独立验收通过（11.59 cm、1.60 s、倾角 4.34°）；
- 当时仅有 C4 从原初态执行通过的证据；V9/V10 在抓取中途重规划失败。旧 portfolio 的 1400 成功依赖显式复位，不能据此证明连续恢复，也不能推断 C4 必须复位才可能成功。
- 1403 的有限扫描没有找到路径（160 组 yaw×offset）；只支持“该规划器在所试参数与状态下未找到解”。原 `OUT_OF_CURRENT_KINEMATIC_ENVELOPE` 结论过强，纠正为可达性未知。它保留在原测试分母中；尚不能断言必须增加导航或调腰。

证据：`runs/grasp_policy_transfer_20261106_002/results.json`、`runs/grasp_policy_c4_20261106_007/results.json`、`runs/grasp_policy_c5_20261106_001/scan.json`。

### 5.7 优化结果如何成为 skill/code

- C3：`policy_grasp_v2_recovery` v1 candidate（digest `6eb46bcf…`），code 投影 `build() -> VisionGraspV6`。
- C4：`policy_grasp_c4_offset_yaw` v1 candidate（digest `93c5c73c…`），code 投影 `build() -> VisionGraspV3`，参数固定 yaw .2 / offset [.03,-.07,-.052] / 全闭；portfolio 记录 attempt1 与 conditional reset attempt2，`same_initial_state=true`。

两者都没有 validation；C4 的 1400 成功是条件化 reset，不是正式 paired/repair_lineage，也没有后续复用。

### 5.8 证明了什么、没证明什么

证明：控制器开发结果从 7/8 到 8/8，比较发现了 C2 的回归；C4 在已用于开发的 1400 增加了一个从原初态执行的成功配方。
没证明：正式准入、按工件身份实际复用、未见迁移收益、完整 T01 放置或跨任务组合。当前是控制器开发曲线与候选登记，尚不能称为已完成积累循环；连续恢复的新增实验另记。

### 5.9 连续重抓的退回路线修正（2026-11-06）

状态：已执行，原预测被物理结果推翻；边界：P01 仿真开发实例，未增加抓杯成功。
原始证据根路径为 `experiments/grow_up_harness_v2/runs/`：

- `grasp_regrasp_route_20261106_001/registration.json`：四个已消费实例的实际杯位、朝向，原失败、负对照、固定 C4 正例与 V11 处理臂；最多 6 回合，每回合 90 s、1 个候选修订、0 重试、0 模型请求。源码在同目录 `source_snapshot/`，运行前后检查磁盘哈希。
- 同目录 `kinematic_replay.json`：从旧 V10/1400 终态仅提取机器人关节与已有 RGB-D 估计。直接回清空位规划失败；沿原朝向逆向经过高位与清空位后，yaw=0.2 路径通过。回归检查直接调用 V10/V11 的实际退回方法和机器人专用 IK，未推进物理。
- `grasp_regrasp_route_20261106_002/registration.json`：首批中断后，仅完成未启动的 1206；没有重跑已中断的 1201，也没有修改控制器源码。
- `grasp_regrasp_route_audit_20261106_001/results.json`：跨两目录汇总；`oom_evidence.log` 保存内存终止证据，`harness_tests.log` 保存 210 项通过记录。

| 条件 | 独立结果 | 解释 |
|---|---|---|
| 1400 wait-only 90 s | 失败，符合预期 | 负对照通过 |
| 1400 原 C4 thumb-leading 配方 | 成功，最大抬升 11.59 cm，最长严格保持 1.602 s | 正例复现；与历史初态积分状态哈希相同 |
| 1400 V11 连续重抓 | 失败，最大抬升 0.197 cm，保持 0 s | 回清空位与重新接近已实执行；全闭后 thumb=0 N，触觉门拒绝 |
| 1200 V11 | 成功，11.98 cm、1.65 s | 未触发 C4 退回分支 |
| 1201 V11 | 无判定，进程遭 OOM/SIGKILL | 已保存前两条动作；缺完整轨迹与独立结果，不计成物理失败或成功 |
| 1206 V11 | 成功，12.01 cm、1.65 s | 保留原 C3 恢复分支；未触发 C4 退回分支 |

预期“修正退回路线即可使 1400 连续抓稳”不成立。修正只移除了已复现的 IK 阻塞，不能将重新接近成功称为抓杯成功。全部已完成新回合的初态积分状态哈希与各自历史实例一致，均无回合内复位；原 1201 中断不补抽。

本轮自主决定：保持原触觉阈值、yaw/offset、物理评价器；只修改退回路线，不扩展新位置；1 次修订用尽后停止，不修改失败预测。完成 5/6 回合（含两个对照），另 1 个中断。完整回合共 189.798 s 仿真、224 次物理工具调用；含中断前已保存记录至少 194.048 s、226 次调用，总墙钟与中断后未保存动作成本未知。不能报告四位置完整成功率。

代码入口：`grasp_optimization/grasp_policy_search.py::VisionGraspV11`；复现入口：`experiments/grow_up_harness_v2/calibration/grasp_regrasp_route.py`。批次在中断后改为每回合独立进程并保存非零退出状态，以释放回合间原生资源；改造后的完整物理批次未重跑。210 项测试在该运行器改造前通过，改造后针对实际退回路线的回归测试再通过 1 项。

未决原因：已成功 C4 使用 thumb-leading，V10/V11 的重抓分支使用同时全闭；重抓仍用接触前的杯位估计。二者均可能影响抓稳，本轮没有单独干预，不能指定其中一项为已证实原因。V11 保留为失败候选实现，正式准入、按 artifact ID 调度、未见覆盖收益均为 0 或未测。

### 5.10 T01 工件：可执行投影、命令修复与放置精度边界（2026-11-06）

状态：已执行 13 个物理回合（含对照）；工件仍为 candidate，无正式验证。
边界：MuJoCo 仿真，单杯 `DH_2F_mug_06`、固定托盘；全部实例均已消费。

**问题**：T01 工件此前只有历史结果，没有“当前 code 投影被实际执行、结果绑定同一 digest”的证据。

**溯源审计**（`runs/t01_artifact_provenance_audit_20261106_001/audit.json`，只读文件哈希）：
当前 v5 投影为 `ba31ca46…`；而 v5 YAML 记录的配对/迁移/验收证据来自 `_superseded/t01_cup_to_tray_v1/program.py`（`9f4b3004…`），run 017 引用的 `skills/t01_cup_to_tray_v1/program.py` 已不存在。历史物理结果对 v1 程序仍有效，但**不能视为 v5 投影已被执行**。

**方法**：每批先登记实例哈希、工件 digest、源码哈希、预算、预测与推翻条件；编译出目标版本并核对 v(n-1)→v(n) 程序差异；每回合独立进程执行（避免上一轮 OOM 复发）；入口为 `t01_fast.py`（已保存初态）或 `t01_artifact_case.py`（生成实例）；判定只用 `tray_verify.py` 的复算结果。运行目录：
`runs/t01_artifact_v6_20261106_002/`、`t01_artifact_v7_20261106_001/`、`t01_artifact_v8_20261106_001/`、`t01_artifact_v9_20261106_001/`；汇总 `runs/t01_artifact_series_20261106_001/summary.json`。

| 版本 | 相对上一版的唯一改动 | control_2500 | position_310102 | position_310103 |
|---|---|---|---|---|
| v5 | —（首次执行当前投影） | ✅ 7.198 s | 未跑 | 未跑 |
| v6 | 前倾后三段 absolute move 改 `move_linear` | ✅ 4.118 s | ❌ lift 段 5 cm 拒绝；已抓起并抬 12.2 cm | ✅ 7.068 s |
| v7 | 抬升/托盘上方/下降也改 `move_linear` | ✅ 7.386 s | ✅ 7.306 s，余量 +7.47 mm | ❌ −24.10 mm，12.01°，6 次修正 |
| v8 | 仅下降段恢复分步 | ✅ 7.386 s | ✅ 7.406 s，余量 +6.12 mm | ❌ −24.10 mm（轨迹与 v7 逐位相同） |
| v9 | 抬升/运输 `move_linear` 时长 2 s → 8 s | ✅ 7.386 s | ❌ −1.79 mm，8.58°，修正 0 | ❌ −0.02 mm，8.39°，修正 0 |

历史 repl3（v1 程序）在 310102 为 plan 段 5 cm 拒绝、310103 成功；它只作对照，不与 v6–v9 合并计数。

**机理结论**：

1. v6 修掉了“腰部前倾后仍按旧游标分段”的拒绝；实测拒绝时实际手掌距目标 6.77 cm。修好后 310102 能抓起并抬 12.2 cm，失败转移到 lift 段。
2. v7 修掉运输段同类累计滞后；310102 首次完整通过。但 310103 在放置段退化。
3. v8 的 310103 轨迹与 v7 **逐位相同**（trajectory `2f81ec1c…`），证明下降段改动对该例无影响；退化来自 v7 的抬升/运输。
4. v9 延长时长没有带来净收益：两例都落在边界附近（−1.79 mm、−0.02 mm），杯底 8.4° 压在边沿，视觉修正为 0 次。**主导约束已不是命令族，而是释放时的毫米级放置精度与缺少释放前姿态检查。**

**判定**：v6、v7、v8 各 2/3，v9 1/3，**没有版本同时覆盖三例，也没有版本支配 v6/v7**。这证明工件可执行、digest 可绑定、评价器能拦住压边失败；不证明工件已具备稳健的 T01 能力。

**成本**：13 个回合（含 5 次对照/重复）、832.5 s 仿真、1252.2 s 墙钟、0 模型请求；另有一次 v6 批次 OOM 中断（1201，无判定），以及两次启动器参数错误（未产生物理回合），均保留。

**结构性问题**：把新证据写入 YAML 会改变 artifact digest，导致“被测试的程序”和“最终记录”不是同一 digest。要在不改变已测版本的前提下晋升，需要独立的 ValidationReport 绑定 digest，而不是回写 YAML。

## 6. 不做什么
- 不因为密集分高就把官方 1 mm 改成成功；官方与密集分两栏报告。
- 不再用 Qwen 4B 直接判 1 mm；它只做粗筛/解释。
- 不再训练 VLA；VLA checkpoint 只保留为负对照，当前目标是 v2 抓杯 policy。
- 不把 1200–1207 的开发验证写成新位置泛化；这些 seeds 已被冻结 v2 消费。
- 不把 126 条 Skill2Real 文本当可执行技能；它们只是 candidate memory。
- 不新建第二套 registry；`PolicyArtifact` 已接入现有 Registry。
- 不把 4 条示范的离线 MSE 写成任务成功。

## 7. 本轮实际产物

| 产物 | 路径 | 状态 |
|---|---|---|
| 密集物理分与失败分类 | `harness/dense_eval.py`、`runs/t01_dense_eval_20261106_002/dense_eval.json` | 已执行；7 例复算，官方不变 |
| 俯视 Qwen 校准 | `runs/t01_qwen_topdown_20261106_001/triage.json`、`triage_corrected.json` | 已执行；5 请求，2 空响应；仅诊断 |
| `PolicyArtifact` 类型与同库 Registry | `harness/contracts.py`、`harness/policy_artifact.py`、`harness/registry.py` | 已实现并测试 |
| v2 路径参数搜索 | `runs/grasp_policy_search_20261106_002/` | 已执行；12 组 0 成功，但把失败从路径推进到保持 |
| v2 闭手搜索 | `runs/grasp_policy_closure_20261106_001/` | 已执行；1206 通过，但全局闭手在 1200–1207 为 6/8，拒绝 |
| v2 1200–1207 无回归检查 | `runs/grasp_policy_validation_20261106_001/` | 已执行；thumb_lead 6/8、simultaneous 6/8，均低于 v2 7/8 |
| C0→C3 开发曲线 | `runs/policy_artifact_grasp_recovery_20261106_001/curve.json`、`curve.svg` | 7/8 → 7/8 → 6/8 → 8/8 |
| C3 policy artifact | `runs/policy_artifact_grasp_recovery_20261106_001/results.json`、`projection/` | candidate；开发 8/8，未晋升 |
| 新位置 1400–1403 迁移 | `runs/grasp_policy_transfer_20261106_002/results.json` | C0 2/4、C3 2/4；本组未见增益 |
| C4 offset/yaw skill + portfolio | `runs/policy_artifact_grasp_c4_20261106_001/results.json`、`portfolio.json` | 已消费实例上 3/4；1400 依赖 reset |
| C5 1403 可达扫描 | `runs/grasp_policy_c5_20261106_001/scan.json` | 160 组未找到路径；可达性未知 |
| v7/v8 补充技能 | `runs/grasp_policy_recovery2_20261106_001/results.json` | 1400 grip recovery 失败、1403 yaw fallback 失败 |
| 现有 SmolVLA 的 policy artifact | `runs/policy_artifact_cup_20261106_002/results.json`、`projection/` | 负对照；candidate，物理 0/4，无 validation |
| T01 工件投影执行 v5–v9 | `runs/t01_artifact_series_20261106_001/summary.json` | 13 回合、0 模型请求；最好 2/3，无版本支配 |
| T01 工件溯源审计 | `runs/t01_artifact_provenance_audit_20261106_001/audit.json` | v5 证据属于 v1 程序，不绑定 v5 投影 |
| 回归测试 | `experiments/grow_up_harness_v2/tests/` | 213 项通过（8.603 s） |

未执行/未通过：没有新 VLA 训练；C3/C4 均未晋升；首次四位置测试没有观察到 C3 成功数增益。

旧成本汇总 `runs/grasp_policy_accumulation_20261106_002/summary.json` 记录所列批次共 **94 个物理回合、1803.4 s 仿真、3676 条 actions 记录、0 次模型请求**。actions 含触觉等诊断记录，3676 不能称为底层命令数；该汇总未覆盖全部早期 smoke/retain 尝试，也不含离线扫描的计算成本，不能称为全成本。原 JSON 只读保留。这些开发回合不是独立任务样本，不能按 51/94 报任务成功率。

## 8. 下一步顺序

1. **T01 放置闭环（最高优先）**：§5.10 显示主导失败已是释放时的毫米级放置与边沿倾斜，而不是命令族。下一步在 `release` 前用公开观测检查杯底相对托盘承托区的位置/倾角，不满足就重定位或抬起重试，而不是继续调运输时长。
2. **冻结并做正式验证**：在 v6/v7 中选定一个开发版本（两者各 2/3，均不支配），按 ADR-0004 做同初态 paired（wait-only vs 工件）或 repair_lineage；ValidationReport 绑定已冻 digest，不回写 YAML。
3. **C4 的连续接入**：§5.9 已消除旧返回清空位的 IK 阻塞，但 1400 仍未抓稳。下一项分别检查闭手顺序是否忠实复用 C4，以及接触后杯位估计是否仍有效。
4. **1403**：可达性未知；定位规划失败阶段，保留在原分母中，不能由有限 IK 失败排除任务。
5. **新冻结集**：1400–1403 已用于诊断；后续采样须先查历史使用记录并登记，不能预称未见。
6. 仍不训练 VLA；VLA 只作负对照。

## 9. 交接三问

1. **新增了什么可验证能力？**  
   T01 工件的 v5–v9 投影都按同一入口实际执行过，结果绑定 artifact digest 与 program 哈希；v6 修掉前倾后的 5 cm 拒绝，v7 修掉运输段累计滞后并在 310102 上取得完整 T01 成功（7.31 s，余量 +7.47 mm）。但 v7 同时让 310103 退化，v9 又把两例推到边沿，**没有版本同时覆盖三例**。P01 侧 C4 仍是同初态 reset 的条件化成功。正式验证未完成。

2. **后续复用了哪一版？**  
   没有正式复用。v5–v9 是同一工件的版本序列，同一 digest 在多个实例上执行；尚无“后续任务按 ID/version/digest 调用”或跨技能接续。C3/C4 policy artifact 亦未晋升。

3. **新增覆盖/成本收益？**  
   T01 的净覆盖为 0：v6 覆盖 control+310103，v7/v8 覆盖 control+310102，v9 仅 control；最好 2/3，互有交换。13 个回合、832.5 s 仿真、1252.2 s 墙钟、0 模型请求。未见集、正式配对与实体收益均未测。


## artifact.v2 两层接线（2026-11-07）

日期：2026-11-07。状态：已执行迁移与接线，验证结果见下列原始路径。边界：MuJoCo 仿真。

采用用户确认的两层工件，新开 `artifact.v2`，保留 `artifact.v1`。叶子保存源码哈希，组合保存顺序 IR；不是只靠 YAML 文件就能还原，重算还需要其引用的源码、子工件和账本。实现为 `experiments/grow_up_harness_v2/harness/artifact_v2.py`。契约谓词是声明，目前编译器检查引用和参数名称，不执行前后置谓词证明，也不证明参数的物理含义相容。

迁移来源是 `experiments/grow_up_harness_v2/runs/grow_reach_20261106_001/library/code_f7e83f8334a4.json`。迁移结果是 `experiments/grow_up_harness_v2/runs/artifact_v2_migration_20261107_001/result.json`：叶子 `reach_pose_hold@12ddba99e5ca`，源码逐字节一致，18 条既有独立判定全部导入。导入不算新增执行或晋升。

FAST 执行 code 投影，SLOW 提示词展示 skill 卡片与叶子源码，模型可提议源码叶子或组合 IR；只有独立成功后入库，仍为 candidate。入口 `experiments/grow_up_harness_v2/calibration/grow.py`；v2 重放配置为 `experiments/grow_up_harness_v2/configs/grow_reach_v2_replay.json`。旧 `grow_reach_v1.json` 保留历史配置，不适用于新入口的 `parent_store` 字段要求。

本轮自主决定：reach 挂 B2.1；姿态放契约内；三个参数为 position_m、quaternion_xyzw、hold_s；组合冒烟挂 DEV.waypoints，先到固定中间位姿保持 0.3 s 再到目标。冒烟 seed 84001，两个目标完整采样在 registration.json；循环重放复用 81101/82101 的首任务，不称未见测试。预算沿用 simulation 30 s、commands 200、wall 300 s。循环重放禁用 SLOW 物理尝试，不调用模型；这不验证在线创作质量。

失败目录 `experiments/grow_up_harness_v2/runs/artifact_v2_composite_smoke_20261107_001/` 与 `_002/` 保留：均未完成汇总，不能报告成功；本轮 `_002` 在首叶子执行后因相对路径与绝对根目录混用而退出。修正脚本输出路径 resolve 后，变更后结果另存 `_003/`，并补登记正负对照，不与前两次混合。

验证入口：`calibration/artifact_v2_composite_smoke.py`；循环重放结果：`experiments/grow_up_harness_v2/runs/artifact_v2_loop_replay_20261107_001/summary.json`。任务树分类、artifact 挂载和组合边分别保存；Mermaid 为 store/task_tree.mmd。同一叶子重复调用用带序号的组合边表示，不是每次执行事件的轨迹树。前后谓词交集只作图关系，不是可达性证据。

最终对照预测：`experiments/grow_up_harness_v2/runs/artifact_v2_composite_smoke_20261107_003/results.json` 中叶子 2/2、人工组合 2/2，均无 unsafe frame，组合在两个目标上都更慢（叶子约 4.55/4.75 s，组合均约 8.35 s），符合预先预测。正负对照的原始 verdict.json 位于同目录 control_negative/ 与各任务 control_positive/。这是工程组合成功，证明该叶子的两步绑定、编译与 Worker 执行通路可用，不证明 agent 自主写组合、T01 长程成功或前后置契约正确。

循环重放 train 1/1、heldout_store 1/1，proposer/critic 调用均为 0；两个任务源码哈希与原判定一致，冻结账本一致，两投影可重算。逐任务原始路径及检查见 `experiments/grow_up_harness_v2/runs/artifact_v2_completion_audit_20261107_001/results.json`；预测对照见同目录 prediction_comparison.json。该结论只覆盖已消耗任务的 Agent 叶子重放，不扩展未见泛化。EGL 环境下 230 项测试通过；首次遗漏 EGL 的测试错误保留在本次会话工具输出，不归因于任务能力。

交接自检（答案均在上述原始证据）：① 为什么 18 条导入不算 18 条新增执行？② 两次 FAST 重放是否改变了源码和独立判定？③ 人工组合 2/2 具体证明什么，尚未证明什么？
