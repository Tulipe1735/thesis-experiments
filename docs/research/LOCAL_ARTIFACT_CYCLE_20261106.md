# 局部 artifact 积累与复用首轮实验

日期：2026-11-06。状态：已执行，投影修复及失败审计完成，积累与复用循环未打通、正式准入 0。
边界：MuJoCo 仿真，1 个已消费的工程保存初态；后续接口修复没有追加模型请求或物理练习。

本轮按 `docs/research/ALIGNMENT_AND_SEQUENCE.md` §7–9 执行。两个 terra 候选都在接口阶段、
发出关节命令前失败，不能据此判断控制质量、可达性或积累收益。工程正负控制的保存帧证据
在反例审查及修复后复算中保留；工程见证不计作自主新增能力。

## 1. 结果与原始证据

最终原始汇总：`experiments/grow_up_harness_v2/runs/local_artifact_cycle_audit_20261106_002/results.json`。
原始候选结果在 `experiments/grow_up_harness_v2/runs/local_artifact_cycle_20261106_004/`。

| 指标 | 本轮结果 |
|---|---|
| 独立初态 | 1 个；六个物理回合不是六个独立样本 |
| 工程正控制 / 等待负控制 | 各重复 2 次；正例两次通过、负例两次失败 |
| 候选 | 1 个局部效果、2 个版本；局部通过 0/2 |
| 自主新增正式能力 / 正式准入 | 0 / 0 |
| 实际后续复用 / 接续尝试 | 0 / 0，接续成功未测 |
| 完整 T01 | 局部回合官方复判均未成功；不是完整 Agent 流程的成功率试验 |
| 新任务覆盖 / 相对不复用的成本收益 | 未测 / 未测 |

原预测的控制部分得到保存帧证据支持；候选通过未观察到，复用/接续预测未进入检验。
工程正例两次重复的最终掌位误差均约 0.278 mm、姿态误差 0.01535 rad、终端保持 1.65 s。
证据为最终汇总引用的逐回合 `verdict.json`，只证明保存帧条件，不外推到所有 0.002 s 物理步。

## 2. 投影修复与版本

生成器 `experiments/grow_up_harness_v2/harness/artifact.py` 已补全 WalkTo/MoveTo/LineTo 的
orientation、分步上限、P/grasp/params/手形/放置点绑定，并使下降实际使用 IR 的 height_m。
必需参数缺失在加载时拒绝；局部投影还核验 registration 哈希确实被 Op 绑定。

- 修复前后回归：`experiments/grow_up_harness_v2/runs/artifact_projection_20261106_001/`。
- 当前事实源：`experiments/grow_up_harness_v2/artifacts/t01_cup_to_tray.yaml`，v5、candidate。
- code/skill/IR/manifest：`experiments/grow_up_harness_v2/artifacts/generated/t01_cup_to_tray/v5/`。
- 当前生成检查及 197 项通过日志（8.589 s）：
  `experiments/grow_up_harness_v2/runs/artifact_projection_20261106_003/`。

v3/v4 及当时的检查保留，不把版本数计为能力数。技能卡明确标状态和来源；历史物理数字
保留原程序的含义，不授予新投影版本新的物理资格。

## 3. 启动前冻结的局部效果与预算

初始登记：`experiments/grow_up_harness_v2/runs/local_artifact_cycle_20261106_003/registration.json`；
候选实际执行登记：`experiments/grow_up_harness_v2/runs/local_artifact_cycle_20261106_004/registration.json`。
对象、位姿、机器人初态、模型、已列依赖哈希、阈值理由、固定顺序、预测与推翻条件均在登记中。

选择已知 `control_2500` 普通保存初态的最早空手清障段，公开目标为当前骨盆系
`[-0.07, 0.34, 0.09] m`，保持初始掌姿，不由私有杯位生成目标。位置误差 ≤8 mm、
姿态误差 ≤0.15 rad、连续保持 ≥1 s；全部保存帧手开口比例 ≥0.95、手接触力 <0.1 N、
杯子相对原初态位移 ≤5 mm、无保护。8 mm 是局部掌位容差，官方入盘 1 mm 余量不变。

控制与候选共用 `experiments/grow_up_harness_v2/harness/tp01.py` 的左 14 关节适配接口，
只开放 set_joints/wait，没有腰部或现成 IK；允许 Agent 用公开机器人几何自主编写求解器。
候选仅见本体反馈、公共目标和机器人几何，经现有 seccomp Worker 执行。

每回合仿真 ≤30 s、底层命令 ≤200，Worker 单次 ≤2 s、CPU ≤30 s、回合墙钟 ≤120 s。
模型固定 `gpt-6.1-terra`，每请求 ≤120 s；来源链最多 4 请求，初稿加一次反馈修订，最多
锁定 1 个候选。时钟采用决策能力测试：模型/Worker 计算时不推进物理，墙钟另计。
一个初态只构成机制单元；固定控制与配对顺序不用于随机化方法优劣推断。

初态哈希写入 scope.stage；局部任务谓词 `ExplicitPoseHeld` 由
`experiments/grow_up_harness_v2/harness/local_reach.py` 独立重放判定，不改十个 TP01 步谓词。

## 4. 控制、准入设计与实际退出

负例只等待；正例把已存工程成功轨迹前六条关节目标重新拆成共同接口允许的小步。
这是给定底座。负例成功则批次无效，正例失败则不进作者路径，不通过放宽判据继续。
工程轨迹及私有验收数据对候选作者隔离。

若候选局部通过，原设计仍须锁定后执行真实同模型无/有 Skill 配对：无 Skill Agent
保留同接口代码能力，有 Skill 臂记录实际冻结调用；各存独立 verdict 与两条原速同机位视频，
按既有 paired 条款判准入，等待负例不能代替 Agent 基线。本轮没有走到此分支。

输出沿革的证据均保留在 `experiments/grow_up_harness_v2/runs/`：

- `local_artifact_cycle_20261106_001/interruption.json`：外层 shell 1 s 超时导致注册前中断。
- `local_artifact_cycle_20261106_002/phase_candidates_error.json`：terra 初稿返回后，提交因
  未定义谓词 known_saved_initial 被契约拒绝，候选未执行；两个控制回合及一次请求照计成本。
- `local_artifact_cycle_20261106_003/`：修 scope/任务谓词，登记继承原样初稿、重过控制；
  之后投影器相对路径处理异常，仍未执行候选。不重新请求初稿，不重置修订预算。
- `local_artifact_cycle_20261106_004/`：只修纯路径解析后，登记引用 `_003` 的控制证据，
  核对当时已列物理/评价依赖未变，不再重复物理控制；继承不计作新增控制回合。

`_004` 的 v1 读取 task.body_geometry/task.contract 包装，而执行器传入裸 contract；
v2 返回 action.type，执行器要求 action.op。两版各仅运行准备静置 0.75 s，底层命令均为 0。
达到初稿加一次修订上限后停止，admission.json 记正式准入 0；未请求正式配对两臂模型决策、
未渲染 paired 视频、未正式复用，也未跑 A→B。这是接口失败，不是物理控制失败。

## 5. 反例审查与变更后离线复算

新 context 审查发现原局部评价器漏掉掌部几何、没有恢复逐帧控制输入，以及失败 Worker
调用漏计。原判定保留，修复后覆盖腕末端及全部手部后代，按实际仿射位置伺服关系反解
ctrl，并逐帧核对重建 actuator_force；采样缺口只中断其所在保持窗口。

中间失败均保留在 `experiments/grow_up_harness_v2/runs/local_artifact_cycle_audit_20261106_001/`：
recomputed_evaluator_v2/failure.json 记录单位增益假设被显式模型检查拒绝；
recomputed_evaluator_v3/results.json 记录对全轨迹施加采样间隔检查，因早期
2.000→2.052 s 间隔误拒正例。新增回归证明早期 travel 缺口不否定后来完整保持，
保持内部缺口不能桥接；未放宽位置、姿态、接触或保持阈值。

同目录 contact_geometry.json 显示六条轨迹全部保存帧均无左手几何接触对，掌部已包含。
最终复算代码为 `experiments/grow_up_harness_v2/calibration/local_artifact_audit.py`；
结果在 `experiments/grow_up_harness_v2/runs/local_artifact_cycle_audit_20261106_002/`，六例与原判一致。
该结论限保存帧，不证明每个物理步均无接触。

## 6. 事实源、快照、依赖与接续

候选 code/Op/Skill 的内容寻址事实源在
`experiments/grow_up_harness_v2/runs/local_artifact_cycle_20261106_004/registry/`；
同目录 projection_v1/、projection_v2/ 保留原样 code、语义卡、IR 与 manifest。
最终锁定 `skill_local_clearance` v2，digest
`030982c777f547611f434a20e50c99435402cb4ce4f57c6122ea658ebb07319c`，源码 SHA
`6a4c84502b448e1bb573efc2865afde010b9eca947c1325fab9948ecfff6c2f5`，仍为 candidate。

最终审计目录的 library_snapshot.json 保存前后快照、正式 op 数 0 与完整性检查；
skill_graph.json 仅有声明的步骤/源码依赖，真实后续调用及效果接续边为空。
历史实际执行源码按登记哈希捕获于第一审计目录 frozen_sources/，索引 source_capture.json。
delivery_checks.json 核对 T01 最新投影、候选两版投影、源码绑定、登记绑定和库完整性。

只有准入后才计划从正式冻结快照读取同 ID/version/digest/source 的 A，直接接给定工程 B：
目标 `[-0.04,0.34,0.30] m`、yaw=0，阈值同 A、共用剩余 30 s。应以连续轨迹、B 实际动作、
A/B 边界状态和独立 verdict 见证，不凭静态边或边界两次读哈希推断；本轮未执行。
晋升会改变资格对象 digest，须由 ValidationReport 连接候选与正式对象，再以正式冻结
digest 作后续调用身份；实现源码 SHA 保持不变。本轮没有正式对象可调用。

## 7. 成本与尚未验证的部分

全部练习和控制共 6 个物理回合、91.7 s 仿真、436 条底层命令，命令全部来自控制，
候选为 0。terra 共 2 次请求，输入 42,098 token、输出 4,488 token；reasoning 256 为
传输单列项，不与输出重复相加。模型墙钟 92.06 s，回合执行/验收墙钟合计 152.09 s。
Worker act 实际尝试 2 次、成功返回 1 次；旧 worker_calls: 1 保留，由最终审计更正。
最终独立离线复算 5.92 s，197 项单测 8.589 s；早期检查、失败和计时均保留。
币种费用未由传输返回，外层强制超时也没有完整内部计时，不能补造。

后续代码已补精确 runtime 参数与字面动作格式、畸形动作诊断、Worker 尝试日志及
registration 绑定校验；仅过非物理回归，没有再练习。原登记漏列 profile/context/参考
初态等读取项，下一次入口已补齐，不能事后声称本批全部执行输入已冻结。
外部 Skill2Real 技能文本已单独导入为 candidate MemoryNote（见
`SKILL2REAL_REUSE_20261106.md`）；下一次候选只应选 4–6 条与当前效果直接相关的 note，
不能把 16 条全塞进提示词，也不能把导入数量当成本地能力。

交接三问：新增自主可验证效果为 0，只有已消费初态上的工程清障见证；没有后续实际
复用版本或真实接续；新增覆盖与成本收益未测。当前只定位到作者与执行器接口失败，
不支持“积累闭环是主瓶颈”的方向性结论。下一次先以精确公开 runtime 形状作非物理
调用预检，再新登记预算和源版本；正式 paired、复用及真实接续分支仍未验证。
