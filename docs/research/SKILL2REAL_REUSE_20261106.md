# Skill2Real 公开资产复用评估

日期：2026-11-06。状态：公开资产已核对，16 条外部技能文本已按 candidate-only 导入；未执行第三方代码、未跑机器人、未请求模型。
边界：只读官方项目页、其公开数据文件与论文；G1/MuJoCo 适配尚未实执行。

## 1. 结论

**没有一段 Skill2Real 运行时代码能在我们的 G1/MuJoCo 接口上直接执行。** 可直接复用的是它的**技能文本组织方式、分阶段程序契约和准入检查**，不是它的 `goto_pose` / `gripper_goto` 后端。

具体判断：

| 类别 | 内容 | 判断 |
|---|---|---|
| 可直接复用 | 126 条 skill 中的规则/适用条件/状态说明；技能卡字段 | 其中 16 条已按 T01 相关性导入为 candidate MemoryNote |
| 可直接借鉴 | `main(api, stage_inputs)` 的分阶段状态机、`status`/`execution_ok` 检查、`motion_epoch`、保留观测 | 已先写入作者提示的 staged state / re-observe 规则；动作结果字段尚未接入 |
| 可适配 | 18 个 API 操作中的感知/状态部分；Cerebellum/Brain 两级库；PVG 的 Governor 准入标准 | 需要 G1 专用适配，尚未实执行 |
| 不可直接复用 | 58 个 task program、`goto_pose`/`gripper_goto`/`compile_pose`、俯视/立体/SAM 感知、论文成功率 | 平台、许可或证据边界不符 |
| 未公开 | 训练代码、PVG 完整实现、runtime 后端、代码许可证 | 项目页未发现 GitHub/许可声明；论文仅 CC BY 4.0 |

关键事实：站点称有 **58 个 task program**，但 `task-data.js` 中 **58/58** 都标为 `kind: "adapted_task_program"`、`reexecuted: false`；它们不是在这些页面上重新执行过的成功记录。**126 条 skill 是给 Proposer 读的文本记忆**，站点自己的 `skill-memory.md` 明确说“code inside a skill document is context for program generation; it is not an additional callable API”。

因此，**导入这些 skill 不等于给库增加可执行技能**；它们只能作为外部先验，之后仍要在 G1 上经候选、执行和独立验收。

## 2. 公开资产盘点（2026-11-06）

| 资产 | 数量/内容 | 一手来源 |
|---|---|---|
| Skill catalogue | 126 条：65 Cerebellum + 61 Brain | <https://skill2real.github.io/#skills>；<https://skill2real.github.io/skill-library-data.js> |
| 分类 | grasp 22、transport 26、inspect 9、manipulate 8；Brain：referent 22、binding 16、progress 14、destination 6、sequence 3 | 同上 |
| Task gallery | 58 条：11 LIBERO-90、4 LIBERO-Pro Long、8 Robosuite、25 real、10 tabletop | <https://skill2real.github.io/task-data.js> |
| Task code | 58/58 有 `program` 路径；58/58 为 `adapted_task_program`、`reexecuted:false` | 同上 |
| API | 18 个操作：8 感知、6 状态/位姿、4 控制 | <https://skill2real.github.io/#standard-api>；站点 `documents["api-reference.txt"]` |
| 技能记忆说明 | 明确为文本记忆，不是函数包 | 站点 `documents["skill-memory.md"]` |
| 论文 | arXiv 2610.02788v2；HTML 标 License: CC BY 4.0 | <https://arxiv.org/abs/2610.02788v2>；<https://arxiv.org/html/2610.02788v1> |
| 训练/PVG 代码 | 项目页、`app.js` 与数据文件中未发现 GitHub 链接、代码仓库或许可证声明 | 同上；未发现不等于不存在，需作者确认 |

公开 task program 例子：

- `can_in_tray.py`：<https://skill2real.github.io/assets/tasks/programs/can_in_tray.py>
- `upright_soup_can.py`：<https://skill2real.github.io/assets/tasks/programs/upright_soup_can.py>
- 站点 media note：<https://skill2real.github.io/assets/media-note.txt>

`can_in_tray.py` 的实际结构是 `def main(api, stage_inputs)`，含 `observe`、`discover`、`observe_retention`、`stereo/depth`、`segment`、`measure` 等阶段；没有模块 import，动作通过 `api.goto_pose` / `api.gripper_goto` / `api.compile_pose` 发出。它依赖一个我们本地不存在的 18 操作后端。

## 3. 可直接复用的内容

### 3.1 外部技能记忆（已导入 16 条）

已从 126 条中选 16 条与 T01 杯子/托盘最相关的规则，按“规则 / 适用条件 / 本地适配 / 注意事项”改写成中文，保留来源 URL、源文件 SHA、条目 SHA 和检索日期。导入结果：

- 代码：`experiments/grow_up_harness_v2/harness/external_memory.py`
- 导入入口：`experiments/grow_up_harness_v2/calibration/import_skill2real_memory.py`
- 运行与原始证据：`experiments/grow_up_harness_v2/runs/skill2real_memory_import_20261106_002/`
- 源快照：`experiments/grow_up_harness_v2/runs/skill2real_memory_import_20261106_001/source/`
- 源文件 SHA：`f51d813378ae7c9840c45765d8a60d6c5de8b6daa4915a61e53c054f790c0ca3`（skill-library-data.js）
- 结果：**16 candidate MemoryNote、16/16 条目哈希通过、0 validated、0 executable skill、0 formal admission、0 local execution**
- 后续加载：`external_memory.load_registry_notes(registry_root, snapshot_id)` 按冻结快照返回同一批 digest，不重新生成；同目录 `loader_check.json` 记录 16/16 digest 一致、全部 candidate、未重新生成

选入条目及本地用途：

| 条目 | 规则要点 | 对我们的用法 |
|---|---|---|
| skill-001 Choose a clear side for rim contact | 杯沿被把手/杂物挤住时选无遮挡侧，接触可见杯口下方杯壁 | 抓杯前检查把手与侧向间隙，不固定 yaw |
| skill-003 Identify the actionable receptacle opening | 用面积/重叠/包含区分开口与边沿/侧壁 | 托盘检测不把外接框当承托区 |
| skill-004 Choose a supported interior placement | 斜视时先比较结构，看到侧壁不等于找到承托内部 | 放置点仍由 `tray_floor_center_m` + 杯底偏移算 |
| skill-016 Adapt rim contact to handle clearance | 选给手指和抬起留空间的杯沿侧，把手避开接近路径 | 抓杯避让把手 |
| skill-022 Balance rim engagement and release clearance | 抓取接触也要考虑释放时手指是否卡杯沿 | 释放前检查手指/杯沿几何 |
| skill-037 Carry a rim-held vessel in short segments | 长距离持杯分段，下降前在目的地上方重观察杯体 | 对应我们的 5 cm 分段与再观察 |
| skill-039 Check realized clearance during lift | 大幅抬升横向偏移时保留已完成抬升，只改失败后缀 | 有界修复，不回退已抬高度 |
| skill-045 Clear a raised receptacle during transport | 先让被持物最低点越过托盘边沿，再横移 | 用杯底最低点而非掌高检查 |
| skill-046 Clear the inner finger after release | 释放后内侧手指可能钩住杯沿；先支撑再退指 | 释放后检查手指退出 |
| skill-051 Confirm mug retention from current evidence | 接触后是否仍抓住要看当前证据，不能凭命令完成 | `close_hand` 的 `EXECUTED` 不等于抓牢 |
| skill-058 Distinguish support contact from free motion | 区分到达最终支撑与仍在自由空间 | 下降阶段检查杯底/托盘实际关系 |
| skill-063 Gate traversal on the first lift's evidence | 抓取到运输前要求首次抬升证据 | 先小抬升确认随动，再运输 |
| skill-080 Lower a vessel into a bounded receptacle | 末段倾斜先查底板/侧壁干涉，比较释放前后状态 | 对应历史近失与倾斜失败 |
| skill-090 Place the object body, not the wrist | 腕部居中不等于杯体居中 | 释放前用当前观测核对杯体 |
| skill-097 Release near the interior support | 内部承托面与边沿分开；障碍上方释放会弹开 | 释放高度以底板为基准 |
| skill-120 Separate gripper obstruction from retention | 夹爪闭合受阻不等于抓住 | 不把闭合读数当抓持证据 |

**这批导入没有改变正式库**：`library_snapshot.json` 只含 MemoryNote，正式 op 表为空，技能图节点/边为空；每条 note 都是 `candidate`，且文本开头是 `[EXTERNAL PRIOR - NOT LOCALLY VALIDATED]`。

### 3.2 技能卡字段结构

他们的 skill 条目由四部分组成：自然语言 Rule、Apply when、Decision context、API-level Code template（有的还有 state description）。我们的 `MemoryNote.text` 目前是一段文本，语义卡只有 pre/post/failure exits；可以直接补的字段是：

- `applies_when`：什么时候适用；
- `decision_context`：这条规则改变哪个决策；
- `layer`：Cerebellum（局部效果）或 Brain（组合/进度）；
- `category`：grasp / inspect / transport / progress / binding 等；
- `source`：外部先验还是本地证据。

这比把 126 条全文塞进提示词更有用：候选作者只拿到与当前效果相关的 4–6 条，且知道它们是外部未验证先验。

### 3.3 分阶段程序契约（可直接改写进我们的 Worker）

`can_in_tray.py` / `upright_soup_can.py` 的共同模式：

1. `main(api, stage_inputs)` 每次只做一个 decision stage；
2. 返回 `status: "need_observation"`、`execution_state`、`outcome_evidence`、`next_step`；
3. `checked_motion` 要求返回 `status == "ok"` 且 `execution_ok is True`，否则抛 `motion_not_confirmed`；
4. `valid_pose` 检查 xyz 三个有限数、四元数四个有限数且范数接近 1；
5. `motion_epoch` 在每次运动后递增，使旧的深度/分割证据失效；
6. 抓取后先 `observe_retention`，要求 `contact_supported` / `lift_supported` 才进入运输；
7. 释放后检查 separation 和 placed relation，再决定下一个目标。

这正好补我们最近一次候选的两个接口问题：v1 把 `task` 当包装对象、v2 返回 `action.type`。我们的 `local_artifact_cycle.py` 已补精确 `runtime_bindings` 和 `local_action()`；还可以把 `execution_ok`、`measured_pose`、`motion_epoch` 作为动作返回的标准字段，让候选必须检查“实际动没动”，而不是只看命令已发出。

### 3.4 PVG 准入检查（Appendix D.2 的直接启发）

论文 Appendix D.2 记录了一个 bowl-transfer 案例：四个 proposal 共享同一个成功程序，但只有 1 个被 Governor 接纳，另外 3 个被拒：

- **相对指代**：接纳。规则能从新图像选对左碗，且执行程序实现了该规则；
- **接触绑定**：拒绝。它属于冻结的 Cerebellum，不应写入 Brain；
- **目的几何**：拒绝。计算托盘几何/释放间隙是局部放置程序，超出 Brain 更新范围；
- **进度检查**：拒绝。包含了一个没有实现、没有测试的 object–hand co-motion 条款。

可迁移的不是“让 LLM 当裁判”，而是四条**确定性预检查**：

1. 一个候选只允许一个可独立判定的效果；
2. 候选声明的层级/范围必须与它实际修改的对象一致（局部效果不能写成组合技能）；
3. 条目里的每个 clause 都要有对应执行证据，未实现的 clause 不得随候选一起入库；
4. 整项程序成功不能证明其中每条规则都成立；只接纳被单独验证的那条。

这可以直接加到我们的 `ValidationReport` 之前，作为 `candidate` 准入的 gate；最终物理资格仍由我们的 paired / repair_lineage 和独立评价器决定，LLM Governor 只做 advisory，不作成功 oracle。

## 4. 需要适配的接口

| Skill2Real API | 我们的现状 | 适配判断 |
|---|---|---|
| `get_scene_image` | `head_rgb_path` + `depth_path` + `K` + `T_optical_to_pelvis` | 可用；语义改为头部 RGB-D |
| `get_wrist_view` | 无腕部相机 | 不可用；不要把头部图伪装成 wrist view |
| `get_topdown_image` / `get_topdown_stereo_view` | 只有头部相机；`task_observer` 是旁观相机，策略不可用 | 不可用；需要另装俯视相机才谈得上 |
| `get_foundation_stereo_depth` | 无立体对；有单目深度 | 不可直接；用 `pixel_to_pelvis`/现有深度 |
| `get_sam_mask_from_box` | 无 SAM | 不可直接；用现有 `visible_cups`/`locate_tray` 或候选自写分割 |
| `measure_visible_geometry` | `pixel_to_pelvis` + 可见几何 | 可部分适配 |
| `compile_pose` | 主实验不提供现成 IK；允许 Agent 自写 | **不要在平台侧提供**；可让候选自写 `compile_pose` |
| `goto_pose` | 左 14 关节 `set_joints`/T01 `move`，有位移/速度/预算 guard | 需适配；不能直接暴露笛卡尔 `goto_pose` |
| `gripper_goto(width)` | Dex3-1 七关节手，无“开口宽度”原语 | 需适配为手指目标/预设手形，不能保留 width 语义 |
| `goto_pose_both` | 当前单侧臂范围 | 不支持；双臂是后续 |
| `gohome` | 无同等安全 home 原语 | 不提供；避免绕过关节 guard |
| `get_end_effector_pose` | `left_palm`（current_pelvis，m，quaternion_xyzw） | 可直接映射 |
| `get_previous_proposer_state` | `state` / blackboard（扁平值） | 可映射，但需显式 flatten 与来源 ID |
| `grasp_center_to_tool0_pose` | 工程 `_place` / 候选自写 | 只可作为候选自写或工程给定分支 |

结论：**感知和位姿部分可以按我们的观测重写；控制部分不能照搬。** 尤其不能因为 Skill2Real 提供了 `compile_pose`，就把现成 IK 注入主实验——那会改变“关节级身体试探 / 自主 IK”的归因。

## 5. 不能直接复用的部分

- **58 个 task program**：依赖 18 操作后端；全部 `adapted_task_program`、`reexecuted:false`。它们可作为分阶段结构参考，不是成功轨迹，也不是我们的基线。
- **126 条 skill**：文本记忆，不是函数；没有在 G1 上执行过。导入后仍是 candidate。
- **成功率**：78.75% real-world、56.3% Pro Long、89.4% Robosuite 来自 UR5e/不同任务/不同模型，不能作为 G1 T01 的对照数字。
- **训练/PVG 实现**：站点没有公开代码仓库、训练脚本或许可证；论文 CC BY 4.0 只覆盖论文文本/图，不自动覆盖站点代码。**不把第三方代码复制进仓库**，只保留来源链接、哈希和改写后的规则。
- **`skill-memory.md` 的边界**：它自己说 code template 不是 callable API；把 126 条当“技能库已增长”会重复我们之前“文件/版本数不等于能力”的错误。

## 6. 本地已做改动（全部非物理）

| 文件 | 改动 | 证据 |
|---|---|---|
| `experiments/grow_up_harness_v2/harness/external_memory.py` | 16 条外部规则、源/条目哈希校验、候选 MemoryNote 生成、冻结快照加载器 | 新文件；`runs/skill2real_memory_import_20261106_002/loader_check.json` |
| `experiments/grow_up_harness_v2/calibration/import_skill2real_memory.py` | 排他输出、先 registration、再导入、冻结快照 | `runs/skill2real_memory_import_20261106_002/results.json` |
| `experiments/grow_up_harness_v2/calibration/local_artifact_cycle.py` | `prompt(..., memories=...)` 增加 `external_skill_memory`，明确“未验证先验、不得当成本地成功或可调用技能” | 新增测试 |
| `experiments/grow_up_harness_v2/tests/test_external_memory.py` | 源/条目哈希、candidate 状态、无代码、registry 只增 memory、无正式 op | 通过 |
| `experiments/grow_up_harness_v2/tests/test_local_joint_interface.py` | 外部记忆在作者提示中显式标记 candidate | 通过 |

导入运行结果：`runs/skill2real_memory_import_20261106_002/results.json`；库快照：同目录 `library_snapshot.json`；可读条目：同目录 `notes.md`。源下载暂存：`runs/skill2real_memory_import_20261106_001/source_provenance.json`。

没有新增物理回合、没有模型请求、没有把任何 note 晋升为 validated。

## 7. 建议的下一步

**先做非物理的调用预检，不要直接开新一批 T01。**

1. 在 `local_artifact_cycle.py` 的作者提示中只放 4–6 条与本效果直接相关的 note（例如空手清障只用 skill-001/016；托盘放置才用 003/004/045/097），不要让候选一次读 16 条。
2. 用现有 `local_action()` 加一个 dry-run Worker 测试：候选源码必须能在 `init(profile)` / `act(observation, contract, state)` 下返回合法 `op`，且 `execution_ok`/`measured_pose` 字段只作为结果检查，不由平台代填。
3. 预检通过后，再按 `docs/research/LOCAL_ARTIFACT_CYCLE_20261106.md` 的登记方式开一个新的单效果批次；仍用 1 个初态、同模型、同预算，不追加到已关闭的 `_004`。
4. 若要测试“外部记忆是否有用”，对照应是同一候选作者、同一初态、同一动作接口，只改“是否提供这组 note”；两组都保留失败，不能拿 Skill2Real 的论文成功率当对照。

## 8. 交接三问

1. **直接复用了什么？**  
   16 条 Skill2Real 技能文本作为 candidate MemoryNote，带源文件/条目哈希；以及技能卡字段、分阶段程序契约、PVG 的准入检查。没有复用他们的运行时代码。

2. **实际导入了哪一版，是否验证？**  
   导入了 `skill-library-data.js`（SHA `f51d8133…`）中的 16 条；`runs/skill2real_memory_import_20261106_002/` 记录 16/16 条目哈希通过、0 validated、0 executable、0 formal admission。它们尚未在 G1 上执行。

3. **新增覆盖或收益是什么？**  
   目前只新增了**外部先验的组织与可追溯导入**，没有新增可验证物理效果、没有正式技能、没有复用收益。下一步才能检验“带这组 note 的候选是否比不带更好”；在此之前，不能把导入数量写成能力增长。

## 9. 一手来源

- 项目页与技能目录：<https://skill2real.github.io/#skills>
- 技能数据：<https://skill2real.github.io/skill-library-data.js>（SHA `f51d813378ae7c9840c45765d8a60d6c5de8b6daa4915a61e53c054f790c0ca3`）
- 任务数据：<https://skill2real.github.io/task-data.js>（SHA `1d53326bccf9462552f570b394824e5255efbaa47f78b4a915d8694f78b42820`）
- 任务代码示例：<https://skill2real.github.io/assets/tasks/programs/can_in_tray.py>、<https://skill2real.github.io/assets/tasks/programs/upright_soup_can.py>
- 站点说明：<https://skill2real.github.io/assets/media-note.txt>、站点内 `documents["skill-memory.md"]`、`documents["api-reference.txt"]`
- 论文：<https://arxiv.org/abs/2610.02788v2>；HTML：<https://arxiv.org/html/2610.02788v1>（CC BY 4.0）
- 论文方法：§3.1 共享接口、§3.2 PVG、§3.3 两级训练；Appendix C 18 操作、D.2 四个 proposal 的准入/拒绝、E.7 技能调用与证据边界。
