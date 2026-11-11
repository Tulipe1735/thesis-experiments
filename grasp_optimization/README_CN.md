# P01 抓杯实验：结果总览

整理日期：2026-10-24。当前可用版本为 **视觉与触觉直接控制 v2**：在同一批 8 个新杯位上，冻结 v1 通过 1 个，冻结 v2 通过 7 个。成功轨迹完成“夹住 → 小幅试提 → 抬高至少 10 cm → 保持至少 1 秒”。

**最新：四相机 SmolVLA 已完成真实微调及 15 条配对执行。** 使用 4 条训练示范、2 条离线验证示范，训练 700 步，按验证选中第 300 步；相对“仅换杯子归一化统计”的对照，抽样离线动作误差下降 43.73%。4 个新杯位中，原权重、仅换统计、微调三组均为 **0/4**；14 条回合因合指阶段掌位越界停止，另 1 条触觉门短暂通过后因接触丢失停止，独立验收均未确认稳定抓杯。**67 项检查通过**。见 [微调与执行报告](CUP_FINETUNE_CN.md)、[统计对照与微调录像](deliverables/P01_cup_finetune_comparison.mp4)、[实际权重与训练记录](training/cup_fourview_sft_v1/README_CN.md)。

此前四相机接入与 6 条工程示范采集见 [历史报告](FOURVIEW_DEMOS_CN.md)、[原权重短动作录像](deliverables/P01_fourview_VLA_original_weights.mp4)、[工程示范录像](deliverables/P01_fourview_engineered_demo.mp4)。采集阶段文档里的“尚未微调”为当时状态；数据和旧冻结记录保持原样。

此前 v3 试验已确认右手保持可让 VLA 完成 0.2 秒动作，详见 [VLA 新推理历史报告](VLA_LIVE_V3_CN.md)。

[观看 v1/v2 对照录像](deliverables/P01_v2_paired_new_position.mp4) · [阅读 v2 详细报告](V2_GRASP_CN.md) · [查看逐位置结果](reports/v2_progress.json)

## 当前结果

| 项目 | 已保存的结果 | 解释 |
|---|---|---|
| 新位置配对验证 | v1：1/8；v2：7/8 | 相同的 seeds 1200–1207，各位置内初态相同；代码在运行前冻结 |
| v2 成功动作 | 最大抬升 11.83–12.03 cm，独立连续达标约 1.65 秒 | 独立重算对向抓持、离台与身体稳定条件 |
| 复现 | 共 24 次运行；每个位置的 v2 重复两次，轨迹逐数组一致 | 14/16 次通过不等于 16 个独立样本 |
| 开发位置复核 | 10/10 通过 | 已参与开发，单列记录，不计为未见位置验证 |
| 回归检查 | v2 阶段 42 项、VLA v3 阶段 50 项；当前累计 67 项通过 | 已保存各阶段记录，原冻结代码保持一致 |
| 四相机 VLA 微调 | 动作误差下降 43.73%；三组新杯位拿杯均 0/4 | 参数已实际更新，但臂腕在合指时偏移，未进入抬升；与只换统计分开比较 |
| 剩余失败 | seed 1206：无法找到满足连续性限制的路径 | 在接近和合指前停止，保留完整失败记录 |

改进集中在两处：扩大候选掌向和躯干姿态的搜索范围，每次姿态调整后重新拍照定位；拇指先到位，另外两指分段闭合，接触充分后停止继续挤压。原先继续合指会把杯子推出夹口。躯干允许动作范围有所扩大，因此这是完整控制方案的配对比较，不能把收益全部归因于合指方式。

控制器读取头部 RGB-D、自身状态和模拟触觉，不读取杯子真实位置；旁观相机用于录像。没有增大摩擦或电机力矩，也没有把杯子绑定到手。验收器另外读取模拟真值核对结果。

这批证据覆盖同一房间、同一杯型和固定照明，样本数较小，不代表任意场景成功率。1200–1207 已用于验证，后续调参后需要另选新位置。

## Astra、VLA 与 memory 的状态

Astra 在前一阶段已完成两条调用工程动作工具的开发回合，详见 [视觉与 Astra 历史报告](VISION_ASTRA_CN.md)。本轮 v2 执行没有调用 Astra。

VLA 的历史试验包括：v2 阶段只重放保存动作，保持相同等待与 0.106 秒动作，右掌偏移从 21.43 mm 降至 0.24 mm；随后 v3 进行真实新推理，原样执行在 0.106 秒触发保护，保持右侧目标后完成 0.200 秒动作并重新推理一次，右掌偏移 0.90 mm。两条分支仍无拇指对向抓持，见 [v3 报告](VLA_LIVE_V3_CN.md)。这些历史试验没有更新权重；最新的杯子微调已实际更新 122 个参数张量。

随后增加四相机配对试验：真实输入为头部左目、右目及左右腕部四路 RGB。新左目单图与四视图在相同初态、首次动作前状态和固定等待下比较，两者共享同一首张左目图；增加视图改变了预测，但当前 0.2 秒预算内仍未形成拇指对向抓持。相机为工程近似布置，原训练外参未知；详见 [本轮报告](FOURVIEW_DEMOS_CN.md)。

[四相机抓杯数据集](datasets/cup_fourview_v1/README_CN.md) 包含 4 条训练示范和 2 条离线验证示范，全部来自已知 practice 位置。它们由工程 v2 生成，不能计为 VLA 成功。本次已用训练部分完成任务微调，另在新杯位 1300–1303 做三组配对；相同初态、首次四图及等待阶段保存状态均通过核验。本轮没有调用 Astra，VLA 仍只读四路 RGB、实测关节角和任务文本，触觉在执行器中作检查。

第一条成功轨迹及原 memory 仍保留。v2 新增 [工程经验记录](v2/engineering_memory.json)，明确标为本地证据汇总；它未用于本批冻结验证，也没有证明读取它能带来独立收益。memory 文件不会自动更新 VLA 权重。

## 录像、轨迹和证据入口

| 要查看的内容 | 文件 |
|---|---|
| 同初态 v1/v2 对照，约 20 秒 | [对照录像](deliverables/P01_v2_paired_new_position.mp4)，上方 v1、下方 v2；v1 结束后标注末帧保持 |
| 另一个新位置的完整 v2 执行 | [seed 1200 双视角录像](deliverables/P01_v2_new_position_1200.mp4) |
| 当前代表成功回合 | [seed 1201 轨迹](episodes/paired_v2_1201_v2_repeat_1/trajectory.npz)、[独立验收](episodes/paired_v2_1201_v2_repeat_1/independent_verification.json) |
| 当前失败回合 | [seed 1206 规划记录](episodes/paired_v2_1206_v2_repeat_1/kinematic_preflight.json)、[独立验收](episodes/paired_v2_1206_v2_repeat_1/independent_verification.json) |
| 首次成功与经验 | [第一条成功轨迹](episodes/direct_008/trajectory.npz)、[参考回合 memory](episodes/final_reference_1000/episode_memory.json) |
| 全部新位置结果 | [逐位置汇总](reports/v2_progress.json)、[24 次原始结果](validation/frozen_v2/results.json) |
| 固定实验条件与检查 | [执行前冻结清单](validation/frozen_v2/manifest.json)、[42 项检查记录](reports/v2_final_tests.txt) |
| VLA 右手约束对照 | [重放结果](validation/vla_right_mask_v2/summary.json) |

## 各阶段记录

| 阶段 | 结论 | 报告 |
|---|---|---|
| 直接控制工程示范 | 查清右手接触柜体、左手缺少拇指对向接触；使用杯位真值得到首条成功 | [第一阶段历史报告](DIRECT_GRASP_CN.md) |
| 头部视觉与 Astra 工具调用 | 改为图像定位；两条开发回合成功；模型生成 memory | [视觉与 Astra 报告](VISION_ASTRA_CN.md) |
| v1 冻结验证与 VLA 接管 | 旧批次 8 个位置通过 3 个；VLA 短动作未抓持 | [v1 与 VLA 报告](FROZEN_VLA_CN.md) |
| 当前 v2 配对验证 | 新批次同 8 个位置，v1 1/8、v2 7/8；右手约束重放仍未抓持 | [v2 报告](V2_GRASP_CN.md) |
| VLA 新推理与右手保持 v3 | 3 次新推理；受限分支完成 0.2 秒但未形成对向抓持；工程参照成功 | [VLA v3 报告](VLA_LIVE_V3_CN.md) |
| 四相机配对与原生演示数据 | 8 次新调用（含 2 次无电机热身）；四视图短动作未抓持；6 条工程演示导出为原生 30 Hz 数据 | [四相机与演示报告](FOURVIEW_DEMOS_CN.md) |
| 四相机 SmolVLA 实际微调 | 700 个优化器步，选中第 300 步；15 条回合、30 次调用（含 3 次热身）；新杯位三组均 0/4 | [微调与执行报告](CUP_FINETUNE_CN.md) |

旧批次的 3/8 与新批次的 7/8 使用不同位置，不能直接当成同条件对比；当前可比的是新批次内的 **1/8 与 7/8**。各阶段的成功、失败和冻结代码均保留。

## 策略是什么，各自看哪段录像

这里的“策略”分两层：Astra 决定看什么、何时调用哪个动作工具；视觉工程控制器或 VLA 决定机械臂具体怎么动。固定种子、初始姿态和相机属于实验条件，不是动作策略。

| 策略 | 它具体做什么 | 对应录像 |
|---|---|---|
| 直接控制基线 | 控制器读取模拟器里的杯子位置，按固定路径接近、合指、试提并抬升。适合作为最早的工程抓取参照，不属于视觉自主抓取。 | [直接控制成功回合](deliverables/P01_success_verified.mp4) |
| 头部 RGB-D + Astra | Astra 看头部图像选目标、根据返回结果决定下一步调用；接近和抓持由已经写好的工程动作工具执行。因此它是“模型调度 + 工程动作”，不是 Astra 或 VLA 自己输出全部关节轨迹。 | [seed 1000 成功](deliverables/P01_Astra_RGBD_success.mp4)；[seed 1002 不可达恢复后成功](deliverables/P01_Astra_RGBD_reach_recovery.mp4) |
| 头部 RGB-D 直接控制 v1 | 控制器从头部深度图估计杯位，再做运动学规划；合指方式较固定。新一批对照中的 seed 1201 因拇指接触不足而失败。 | [seed 1201 v1 单独录像](deliverables/P01_v1_new_position_1201.mp4) |
| 头部 RGB-D + 触觉反馈 v2 | 扩大掌向和躯干姿态的候选，调整后重新观测；拇指先到位，其他手指逐步闭合，触觉达到条件后停止。 | [seed 1201 v1/v2 同初态对照](deliverables/P01_v2_paired_new_position.mp4)；[seed 1200 v2 完整动作](deliverables/P01_v2_new_position_1200.mp4)；[seed 1201 v2 单独录像](deliverables/P01_v2_new_position_1201.mp4) |
| 原生 VLA 短动作 | 模型从头部图像和 28 个关节角直接输出关节目标。本次只执行了 0.106 秒就因右掌偏移触发保护，没有抓住杯子。 | [VLA 双视角短动作](deliverables/P01_VLA_pregrasp_short.mp4)；[VLA 与工程动作并排对照](deliverables/P01_pregrasp_comparison.mp4)。对照下方工程动作有更多完成抓持的时间，所以不能看作等动作时长的胜负比较。 |
| VLA 右手约束回放 | 把已保存动作重放，只让左侧目标动作通过、保持右臂目标不变。右掌偏移变小，但没有抓持；这是动作适配消融，没有新推理，也没有单独录像。 | [数值与独立验收记录](validation/vla_right_mask_v2/summary.json) |
| VLA 新推理 + 右手保持 v3 | 从同一抓取前状态重新推理；前 5 帧后再观测和推理，完成 0.2 秒。右侧目标保持不变，仍缺少拇指对向接触。没有工程动作接回 VLA 分支。 | [新 VLA 与工程参照对照](deliverables/P01_VLA_live_v3_comparison.mp4)；[受限 VLA 单独录像](deliverables/P01_VLA_live_v3_right_hold.mp4) |
| 原权重 VLA 四相机 | 输入头部双目和双腕四路 RGB，28 维实测状态；原权重、原限速，右侧目标保持。仍未形成对向抓持。 | [四视图 VLA](deliverables/P01_fourview_VLA_original_weights.mp4)；[仅新左目输入参照](deliverables/P01_fourview_left_only_control.mp4) |
| 工程 v2 四路演示采集 | 工程控制器用原头部 RGB-D 和触觉完成抓持，四路 RGB 与动作按 30 Hz 原生同步记录，用于后续学习。 | [工程示范四路录像](deliverables/P01_fourview_engineered_demo.mp4)；[原生数据集说明](datasets/cup_fourview_v1/README_CN.md) |
| 四相机任务微调 VLA | 实际更新动作 expert 和状态投影；从工程准备好的 pregrasp 开始，VLA 输出合指与抬升目标。右侧目标保持，触觉与掌位只作检查；本轮未完成抓持。 | [微调四路录像](deliverables/P01_cup_finetuned_anchor.mp4)；[首个新杯位](deliverables/P01_cup_finetuned_new1300.mp4) |
| 相同杯子统计、原权重对照 | 不训练任何权重，只替换归一化统计，排除缩放变化的作用。 | [与微调同初态对照](deliverables/P01_cup_finetune_comparison.mp4)；[完整四路](deliverables/P01_cup_statistics_only_anchor.mp4) |

成功轨迹和 memory 记录的是经验，不是新动作策略。Astra 的 memory 由执行回合写入；v2 engineering memory 是本地证据整理。两者都不会自动训练或更新 VLA 权重。

## 使用入口与下一项

Windows 可双击 [Watch_v2_comparison.cmd](Watch_v2_comparison.cmd) 查看录像；[Run_vision_v2.cmd](Run_vision_v2.cmd) 运行本地 v2，新建回合目录。

本轮可双击 [Watch_fourview_VLA.cmd](Watch_fourview_VLA.cmd) 看原权重四视图接管，或 [Watch_fourview_demo.cmd](Watch_fourview_demo.cmd) 看供后续训练的工程示范。

最新微调对照可双击 [Watch_cup_finetune.cmd](Watch_cup_finetune.cmd)，或 [Watch_cup_finetuned.cmd](Watch_cup_finetuned.cmd) 看微调模型的完整四路录像。

在本目录的 WSL 终端运行：

```bash
# 本地 v2；不请求 Astra 或 VLA
bash run.sh vision-v2 --seed 1000

# 核对冻结条件，或回放已保存轨迹
bash run.sh v2-check
bash run.sh replay episodes/paired_v2_1201_v2_repeat_1

# 四相机冻结条件、结果与最终数据集回读；不进行模型推理或训练
bash run.sh fourview-check
bash run.sh fourview-results
bash run.sh fourview-data-check

# 微调冻结核对与已保存结果汇总；不启动训练、推理或物理步进
bash run.sh cup-sft-check
bash run.sh cup-sft-results
```

原默认 `bash run.sh run` 仍运行历史真值直接控制；当前视觉版本使用 `vision-v2`。依赖沿用已有 MuJoCo 环境；如路径迁移，设置 `G1_PYTHON`，版本见 [依赖记录](reports/dependencies.json)。

原定的四相机任务微调和新杯位评估已完成，当前瓶颈为合指阶段的臂位保持。下一项在独立新版本中比较“合指阶段保持 pregrasp 臂目标、手指仍由 VLA 控制”的消融，先检验手部输出是否有形成抓持的机会，再决定补数据和训练方式。新适配器必须使用新的测试位置，不能回填本轮结果。seed 1206 的连续路径问题仍作为视觉分支已知失败保留；Astra 自动派发待低层动作稳定后再接入。

## 新增结果：Astra 工程取放闭环（2026-10-25）

日期：2026-10-25。状态：已执行。边界：MuJoCo 仿真、单茶水间、同杯、1 人 1 杯的局部开发试验；旧结果不变。

依据已有成功抓杯工程经验，新增执行了任务树叶节点“茶水间：按茶歇人数摆放空杯”的 1 人实例。四个登记回合全部保留：2100 工程调度完成；2101 首次 Astra 请求因联网权限失败而未执行动作；2102 Astra 逐步调度完成；2103 Astra 读取上一回合 memory 并选择复用其工程组合候选，完整取放再次通过独立验收。

- [Astra 逐步取放双机位原速录像](../experiments/t0_agent_v1/pilot_20261025_001/media/2102_astra.mp4)：抓起、移动、放下、松手、撤手；最终误差约 4.09 mm，连续稳定约 5.276 s。
- [工程工具验证录像](../experiments/t0_agent_v1/pilot_20261025_001/media/2100_scripted.mp4)：0 次模型调用，单独标注工程条件。
- [完整结果与候选/经验索引](../experiments/t0_agent_v1/pilot_20261025_001/results.json)：14 次请求尝试、13 次收到响应，VLA 调用 0；包括联网失败。
- [四项目标、框架及执行协议](../docs/research/GROW_UP_MINIMAL_EXPERIMENT.md#14-四项目标与工程工具闭环首版2026-10-25)、[33 个叶节点与场景扩充登记](../docs/research/T0_TASK_TAXONOMY.md#10-树叶基础任务与场景登记2026-10-25-新增)。

两次提炼产出的是同一套工程工具组合的两份记录，去重后 1 个候选；已完成一次跨回合复用，正式 Skill 仍为 0。Memory 已被检索，不构成收益对照；高层决策由 10 次变为 1 次时，两回合底层动作命令仍各为 55 次。这里只证明单个新增任务闭环与组合复用，不代表多个基础任务已稳定掌握，不属于裸 Astra、自主关节技能合成或实体验证。

## 新增结果：两人两杯工程摆放（2026-10-25）

日期：2026-10-25。状态：双杯工程回合通过；双杯 Astra 未启动。边界：单茶水间 MuJoCo 开发仿真，旧单杯结果不变。

同一叶任务扩为两名参与者、两个同时存在且可相互碰撞的空杯。2200 工程回合依次抓起、移动、放下两杯，独立验收通过：最终误差分别 4.108 / 3.332 mm，双杯同时终态稳定 5.242 s，末态手接触均为 0。共 59.792 s 仿真、111 次底层动作命令；本轮 Astra / VLA 请求均为 0，正式 Skill 仍为 0。

- [双杯原速录像](../experiments/t0_agent_v1/two_cup_20261025_001/media/2200_scripted.mp4)
- [双杯独立验收](../experiments/t0_agent_v1/two_cup_20261025_001/episodes/2200_scripted/independent_verification.json)
- [结果及 Astra 待执行状态](../experiments/t0_agent_v1/two_cup_20261025_001/results.json)
- [协议与复现入口](../docs/research/GROW_UP_MINIMAL_EXPERIMENT.md#143-两人两杯开发试验)

自动审批认为此前网关授权仅限已完成的两个单杯回合，拒绝启动双杯数据发送；待明确扩展授权后方可执行登记的 Astra 槽。当前结论是双杯场景、视觉选择、工程动作与联合验收跑通，不是双杯 Astra 已完成任务。

## 新增结果：T01 单杯入托盘与 T02 三杯归集（2026-10-25）

日期：2026-10-25。状态：T01 两个同初态修复复查通过；T02 三次开发试验均未整项通过。边界：MuJoCo 工程仿真，Astra/VLA 调用 0，正式 Skill 0。

按用户新指令，当前任务改为 T01/T02，前述两杯茶歇摆放停止后续执行，历史结果原样保留。新增的是可自由移动、具有底板和边沿的托盘；用头部 RGB-D 和可见角标定位，独立验收杯底完整包含、实际底板支撑、释放和终态共同稳定。初态按位置和朝向小幅扰动；杯型、托盘类型仍固定。

- **T01：已跑通。** 两次早期撤手失败均保留；修复后重放相同 2300/2301 初态，两次通过，终态稳定 5.922 / 6.772 s，手接触均为 0。共 4 次尝试、2 次通过，不作留出成功率声明。[通过录像](../experiments/t0_agent_v1/tray_20261025_001/media/T01_repaired_2300.mp4) · [首次失败录像](../experiments/t0_agent_v1/tray_20261025_001/media/T01_initial_failure_2300.mp4)。
- **T02：尚未跑通。** 2400 前两杯完成后，第三杯路径不可达；2401、2402 分别在高位绕行、降手时碰到已归集的杯子并触发保护。3 次尝试均失败。[首轮两杯后停止](../experiments/t0_agent_v1/tray_20261025_001/media/T02_initial_failure_2400.mp4) · [最后一次碰撞保护](../experiments/t0_agent_v1/tray_20261025_001/media/T02_latest_failure_2402.mp4)。
- [七回合完整结果与证据](../experiments/t0_agent_v1/tray_20261025_001/results.json) · [任务定义、协议与复现](../docs/research/GROW_UP_MINIMAL_EXPERIMENT.md#144-t01-单杯入托盘与-t02-三杯归集)。

26 项行为/回归检查通过，原 v1/v2 冻结代码与候选保持；这不改变 T02 的失败结论。当前明确缺口是围绕已归集杯子的手部扫掠空间规划，关节 IK 可达不等于无碰撞。记录完整保留，首批 2300 的验收序列化异常在外置审计目录重算，未修改原回合文件。

## 新增结果：T01 / T02 的 Astra 工具调度完成（2026-10-25）

日期：2026-10-25。状态：两项任务均有实际 Astra 调度成功记录，独立物理验收通过。边界：固定白杯与视觉标记托盘的 MuJoCo 开发仿真，旧结果不改写。

T02 补上已归集杯子的视觉障碍记录、手臂/手指及持杯路径检查，并用深度连续性拆分图像中相连的前后杯轮廓。三个修复开发回合保留两次失败与一次通过；随后 Astra / 2501 完成全部三杯，终点共同稳定 6.930 s，最小杯底余量 6.133 mm，底层命令 186 次。

T01 的首次 Astra / 2500 在运输末点触发 IK 保护并失败；降低单杯中央位置的运输高度 2 cm、补完整运输路径预检后，同一初态的本地配对与 Astra 配对均通过。成功回合终点稳定 7.214 s，杯底余量 6.160 mm，底层命令 62 次；没有换位置补抽或放宽保护/验收阈值。

- [T02 三杯 Astra 原速双视角录像](../experiments/t0_agent_v1/tray_astra_20261025_001/media/T02_Astra_2501.mp4)
- [T01 修复后 Astra 原速双视角录像](../experiments/t0_agent_v1/tray_astra_20261025_002/media/T01_Astra_repaired_2500.mp4)
- [全部 8 个新增回合及失败记录](../experiments/t0_agent_v1/tray_astra_20261025_002/results.json) · [证据完整性核对](../experiments/t0_agent_v1/tray_astra_20261025_002/integrity_checks.json)
- [实施、边界与候选说明](../docs/research/GROW_UP_MINIMAL_EXPERIMENT.md#1442-视觉障碍修复与-astra-托盘试验)

本轮 3 个 Astra 回合共 12 次模型请求（10 次决策、2 次经验提炼），其中首次 T01 失败；另有 5 个本地开发/配对回合，3 次通过、2 次失败。31 项检查通过，冻结控制、原感知模块与独立验收器未改。产出 2 份 memory 候选和 2 份工程工具组合候选，正式 Skill 仍为 0；候选尚未单独复执行，未验证记忆增益。本结果属于 Astra 调度工程工具，不是裸模型控制、自主低层技能合成、扩大资产多样性或实体验证。

## 新增判定：T01 修复谱系正式 Skill（2026-10-25）

日期：2026-10-25。状态：协议判定与正式登记完成，没有新增或改写物理回合。边界：固定白杯、四个可见标记的矩形托盘、pantry 场景、seed 2500 的 MuJoCo 仿真。

用户确认将 T01 的完整修复过程与最终成功程序共同作为正式 Skill。当前协议新增 `repair_lineage` 验证等级：原失败、合法诊断、有界修复、同一实际初态脚本复验、Astra 复验、独立验收和冻结哈希共同构成一条证据链。T01 先修过撤手段：2300/2301 分别在水平撤手和抬手末段被 IK 拒绝，改为沿骨盆 -x 撤 8 cm、再抬 8 cm，并加入逐段预检后，同初态重放均通过。随后 Astra / 2500 暴露第二个问题：14 cm 运输点的 IK 位置误差 7.092 mm，超出原 6 mm 门槛；单杯中央槽改为 12 cm 后误差为 1.288 mm，并增加运输到下降的连续路径预检，门槛和任务谓词均未放宽。最终程序为 `inspect → collect_next → finish`，与成功 Astra 回合的实际决策序列一致。

- [正式 Skill 登记](../experiments/t0_agent_v1/skill_registry/T01_tray_place_repair_v1.json)
- [失败诊断](../experiments/t0_agent_v1/tray_astra_20261025_001/transfer_actual_state_diagnosis.json)
- [修复后 Astra 原速录像](../experiments/t0_agent_v1/tray_astra_20261025_002/media/T01_Astra_repaired_2500.mp4)
- [当前晋升协议与证据解释](../docs/research/GROW_UP_MINIMAL_EXPERIMENT.md#145-候选-skill-配对与修复谱系协议修订)

当前正式 Skill 数量为 **1**，验证等级为 `repair_lineage`。这不扩大为其他 seed、杯型、无标记托盘、T02 或实体能力。T01 成功回合检索旧 Memory 的数量为 0，因此 Memory 仍只有候选，不能把成功归因于记忆复用。上节“正式 Skill 仍为 0”是执行结束时的历史状态，原文与原始 JSON 均保留。

## 新增结果：T03 刚体橙子入果盘（2026-10-26）

日期：2026-10-26。状态：已执行，同初态脚本与当前 Codex 高层调度复验均通过。边界：MuJoCo 仿真、直径 80 mm 刚体球形橙子、四标记矩形果盘、seed 2600；没有新增 Astra 网关请求。

原样 T01 Skill + Memory 在视觉检查阶段失败；适配水果/果盘感知后继续修复释放时的滚动。最终在落盘后先等待姿态稳定，再卸力、受限法向分指和张手。全部 11 回合中 9 次失败完整保留；末两次为同初态脚本与 Codex 复验，不是两个新实例。两者末尾连续达标 7.964 s、完整投影余量 12.147 mm、底板支撑 1.863 N，手及其他物接触为 0。37 项检查通过，模型、初态和独立验收门槛在修复中保持不变。

- [Codex 复验原速双视角录像](../experiments/t0_agent_v1/fruit_20261026_002/media/T03_Codex_verified_2600.mp4) · [脚本复验录像](../experiments/t0_agent_v1/fruit_20261026_002/media/T03_scripted_verified_2600.mp4)
- [首次完整取放失败录像](../experiments/t0_agent_v1/fruit_20261026_001/media/T03_release_failure_2600.mp4) · [全部回合与失败](../experiments/t0_agent_v1/fruit_20261026_002/results.json)
- [T03 正式 Skill](../experiments/t0_agent_v1/skill_registry/T03_fruit_place_repair_v1.json) · [更新后的候选 Memory](../experiments/t0_agent_v1/fruit_20261026_002/memory.json)
- [完整修复、预算与结论边界](../docs/research/GROW_UP_MINIMAL_EXPERIMENT.md#146-t03复用-t01-后的水果取放修复谱系) · [一致性核对](../experiments/t0_agent_v1/fruit_20261026_002/integrity_checks.json)

新增 T03 的 `repair_lineage` 正式登记后，当前 T01、T03 各有一个范围受限的正式 Skill，T02 未晋升。Memory 仍是候选，没有单因素收益对照。仅验证一个实际初态，且“稳定”是冻结速度门槛下的有限窗口，不承诺无限期完全静止；其他水果、无标记果盘、跨 seed、Astra 对该版本的调度和实体执行均未验证。原 T01 Skill、Memory 和本页旧数字保持原样。
