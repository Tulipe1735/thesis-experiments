# SmolVLA 杯子微调：训练后物理评估协议侧车审计

日期：2026-10-24。本文是基于本地主源的审计与**建议预注册方案**，不是训练完成或新试验成功的声明。“物理评估”在本文指当前原生场景中的 MuJoCo 动力学评估，不能外推为实体机器人实验。

本审计使用 research 工作流，并行只读核查时序、执行约束、数据与归一化。实际只读取已有 JSON/NPZ/源码，并用 CPU `mj_forward` 重建已有训练示范的掌位；没有调用 `mj_step`、策略推理或 GPU，没有创建试验 episode。唯一写入文件是本文。主线继续负责训练实现、另行冻结新协议和执行评估。

## 1. 可以直接交给主线的结论

1. **保留旧 0.2 s / 3 cm contact-probe 原样。** 它只回答很短动作是否产生新对向接触，不能检验 10 cm 抬杯。旧冻结明确禁止无接触进展或触发保护后自动延长；新实验必须使用独立协议版本，不能把旧失败改记成通过。[S1][S2]
2. **另注册“手势进展 → 对向接触 → 小幅离桌 → 主抬升 → 终态保持”的完整任务评估。** 建议总策略动作预算 8.0 s（240 帧，30 Hz），接触前及小抬升期间仍保留左掌 3 cm 边界，只有通过接触和小抬升门才允许进入明确标注的新 15 cm 主抬升包络。所有闭合和抬升目标均来自策略，评估器只检查、停止和终止保持。[S1][S5][S6] 这些新数值是本审计建议，不是已有冻结参数。
3. **核心比较必须是 `训练权重 + cup 统计` 对 `原权重 + 同一 cup 统计`。** 再报告 `原权重 + 原 Toast 统计`。仅比较训练前后的整套 pipeline，会把换统计带来的闭合先验误记成权重学习。[S9][S10][S11]
4. **使用新杯位、相同初始积分状态、相同相机/限速/时序，提前冻结再测。** 原有 6 条示范及其位置都是 practice；val 4..5 只作已知位置的离线验证。[S7][S8] 本报告没有生成或声称已经冻结新 episode、模型或 manifest。

## 2. 原始约束到底约束什么

| 项目 | 已核实的值/行为 | 主源 |
|---|---|---|
| 旧动作预算 | 6 帧 / 30 Hz = 名义 0.2 s；每次只执行 50 帧预测中的前 5 帧，最多两次推理 | [S1] 第 35–53、131–185 行；[S2] |
| 左/右掌离开起点 | 左 0.03 m、右 0.02 m；比较 `fk` 的当前 pelvis 坐标中掌位，距离基准始终是该次 handoff 起点 | [S2]；[S3] 第 121–129 行；[S4] 第 182–193 行 |
| 接触载荷、跟踪误差 | 左手总近似触觉载荷 60 N、右手 2 N；主动臂关节目标跟踪误差 0.45 rad | [S2]；[S1] 第 175–180 行 |
| VLA 命令速度上限 | 臂 `min(profile, 0.75)` rad/s；手指 `min(profile, 1.0)` rad/s；先裁关节范围，再逐帧限制目标变化量 | [S1] 第 91–97、118–121、159–170 行 |
| 原生 motor profile | 拇指 1/2 的 profile 速度字段均为 12 rad/s、力矩限幅 1.4 Nm；拇指 0 为 3.14 rad/s、2.45 Nm。执行器同时使用 profile 力矩边界 | [S12]；[S4] 第 40–49 行 |
| 返回后的动作 | 旧 probe 将主动关节目标设为返回时的实测角，再观察 1 s；没有接上工程闭合或 lift | [S1] 第 199–218 行 |

**1 rad/s 是当前 VLA 适配器的命令目标变化率上限，不是 MuJoCo 对实际 `qvel` 的硬约束，也不是 profile 原始电机速度。** 不应把放宽到 profile 的 12 rad/s 当作原协议不变。新协议建议继续使用 0.75/1.0 rad/s、既有 PD 参数和力矩限幅，同时记录实际 `qvel`、力矩及裁剪率。[S1][S4][S12]

原 base 保护包括倾斜超过 12°、高度过低、漂移超过 0.12 m、非有限状态和总仿真预算耗尽；这些保护不能因主抬升阶段而删除。最终任务成功另有更严的倾斜 ≤5°、漂移 ≤3 cm 要求。[S4] 第 149–160 行；[S13]

## 3. 示范的实际时序与 0.2 s 门的局限

### 3.1 读取口径

录制器从 pregrasp 后、闭合前开始，500 Hz 控制中在真实物理步前抽取 30 Hz 的实测 `state` 与已选定的绝对 PD `action` 目标；`timestamp=i/30`，实际仿真时刻在 `simulation_time`。这些动作不是下一帧实测关节值，也不是增量。[S5] 第 33–88、151–156 行；[S8] 第 73–84 行。

六条 `samples.npz` 均为 195×28 的 state/action，即 6.5 s 帧预算；最后一帧名义时间为 194/30 = 6.466667 s，不能把末帧时间误作整个 episode 预算。以下接触与 held 时间由已有 `verified_samples.json` 选择 `time >= samples.simulation_time[0]` 后首次满足相应布尔条件的样本，再减去首个实际采样时刻得到。验证轨迹约每 0.05 s 记录，因此这是**首次被采样到的时刻**，不是精确碰撞起始时刻。[S4] 第 162–170 行；[S13] 第 88–100 行。

| 原生 episode / split | seed | pregrasp 采样起点（仿真 s） | 首次对向接触（相对 s） | 首次 held（相对 s） | 原始样本；接触/held 记录 |
|---|---:|---:|---:|---:|---|
| 0 / train | 1000 | 11.770 | 0.430 | 4.830 | [NPZ][D0]；[接触][V0] / [held][H0] |
| 1 / train | 1100 | 11.756 | 0.494 | 4.844 | [NPZ][D1]；[接触][V1] / [held][H1] |
| 2 / train | 1102 | 21.764 | 0.388 | 4.838 | [NPZ][D2]；[接触][V2] / [held][H2] |
| 3 / train | 1207 | 21.770 | 0.432 | 4.832 | [NPZ][D3]；[接触][V3] / [held][H3] |
| 4 / validation | 1002 | 13.770 | 0.480 | 4.830 | [NPZ][D4]；[接触][V4] / [held][H4] |
| 5 / validation | 1200 | 11.756 | 0.444 | 4.844 | [NPZ][D5]；[接触][V5] / [held][H5] |

这里只用既有 val 记录审计时序；建议的 8 s 总预算也由 train 示范和执行上限支持，不应再根据未来测试结果改期限。

### 3.2 demo_1000 的具体动作序列

| 从 pregrasp 起的区间 | 记录中的动作 | 定位 |
|---|---|---|
| 0–0.7 s | 拇指 1/2 目标到 0.65 rad，拇指 0 目标为 0 | [A1] 第 1572–1584 行 |
| 0.7–1.0 s | middle/index 仅闭合到工程参数的 0.15 倍，本例随即满足反馈条件 | [A1] 第 1620–1676 行 |
| 1.0–1.5 s | settle 与触觉门 | [A1] 第 1678–1700 行 |
| 1.5–3.0 s | 2 cm 试抬 1 s，再保持 0.5 s | [A1] 第 1701–1785 行 |
| 3.0–5.0 s | 主抬升；目标为原 pregrasp 掌位 +12.5 cm，不是在 2 cm 上再加 12.5 cm | [A1] 第 1787–2100 行；[S6] 第 187–191 行 |
| 5.0–6.5 s | 保持 1.5 s | [A1] 第 2102–2108 行 |

旧 handoff 中拇指 1/2 实测约 0.000478/0.000072 rad，目标均为 0；工程闭合目标分别为 0.65 rad。[S14] 第 14–21、463–473 行。因而在 1 rad/s 的**目标 slew** 下，仅把命令从 0 推到 0.65 就至少需要约 0.65 s；六帧仅能推进约 0.2 rad，尚未计入 PD 跟踪、接触阻挡和策略是否持续给出闭合方向。**到达 0.65 不是发生接触的必要条件**，所以不能据此证明 0.2 s 内接触绝对不可能；它说明“0.2 s 没接触 ⇒ 没学会抓杯”的推断缺乏时间预算支持。

训练示范的拇指 1/2 action 标签相邻帧最大变化率约 **1.39166 rad/s**（使用真实 `simulation_time` 求差），超过 VLA 1 rad/s 上限。这与教师 0.7 s smoothstep 插值的峰值 `1.5×0.65/0.7≈1.39286` 一致。原生 `set_joints` 校验的是 profile 速度，录制元数据也明确没有认证 VLA 限速兼容性。[D0][D1][D2][D3]；[S4] 第 277–299 行；[S8] 第 82–84 行。**结论是需要留出执行余量，不是应提高 VLA 速度上限。**

另对四条 train 的 `model.mjb + pregrasp_state.npz + trajectory.npz` 只做 CPU 前向重建，按现有 `fk` 口径计算从 pregrasp 的掌位变化：最大左掌位移分别约 12.170、12.254、12.202、12.179 cm；最大水平变化 0.419、0.476、0.342、0.386 cm。其依据是各 [D0]–[D3] 同目录的三个物理记录文件，以及 [S4] 第 182–193 行的 FK 定义；没有重新执行教师。这支持“主抬升需要超过 3 cm 的显式新包络”，不能证明 15 cm 对所有新杯位都安全。

## 4. 推荐预注册的两条评估轨道

### 4.1 LegacyProbe：保持历史定义

保持旧 manifest、6 帧、限速、所有 guard、两次推理上限和返回实测角后 1 s 观察，单列是否出现**初态没有的杯子对向接触**。未接触、保护或不满足旧 extension gate 时，记录旧门失败并结束该 episode。不能把手指开始运动改叫旧接触门通过，也不能继续这个 episode 再补动作。[S1][S2]

建议先在既有 seed 1000 的已核验 handoff 上报告三种 pipeline 的这项开发诊断。该位置是练习位置，不能作为新杯位成功率。以下完整协议可以从同一初态**另起一条明确标识的新实验**，无需把旧门失败改成成功；它从注册之初就具有不同的手势阶段与总预算。

### 4.2 StagedLift-v1：完整任务建议

以下是可直接冻结的一组保守起始数值，主线若实施应在读取任何新测试结果前确定版本。时间 `t_action` 只累计实际执行策略帧的物理步；推理等待另记，绝不把等待期间额外的目标运动额度加入 slew 限制。**表中手势阈值只检查已有命令/实测动作，不生成或纠正闭合轨迹。**

| 阶段 | 建议期限与准入门 | 平移包络与失败处理 |
|---|---|---|
| 初始资格 | handoff 时无已有杯子对向抓持，杯底仍在桌面附近；起始状态稳定且无保护 | 先保存完整初态；不合格按第 7 节报告，不按模型结果换位置 |
| 早期手势 | `t_action=0.2 s`：拇指 1/2 至少一关节的已执行目标相对起点正向推进 ≥0.03 rad，且对应实测推进 ≥0.01 rad；或已独立确认新杯子对向接触 | 保留左掌离起点 ≤3 cm；这里明确只判“手势”，不要求旧 contact gate 通过；无进展停止 |
| 持续手势 | `t_action=0.8 s`：至少一拇指关节目标累计正向推进 ≥0.20 rad、实测 ≥0.10 rad；或已形成杯子对向接触 | 仍保留左掌 3 cm；不强迫实测到 0.65，因为接触可阻止继续转动；无进展停止 |
| 接触门 | 最迟 `t_action=2.0 s`：同一只左手 thumb 与 index/middle 至少一指各 ≥1 N，持续至少 0.10 s；独立验证还须确认是杯子、两法向余弦 <−0.5，且两指杯接触各 ≥0.1 N | 左掌 3 cm；未达标停止。1 N 是建议的稳健触觉准入值；独立几何门沿用既有对向定义，不把任意碰触当抓持 |
| 小抬升门 | 接触后继续策略动作；最迟 `t_action=4.0 s`，杯体相对初始上升 ≥5 mm、杯底离桌 ≥5 mm、杯上非手支撑 <0.1 N，并有左手对向接触，持续 ≥0.20 s | 左掌仍 ≤3 cm。最早 `t_action=3.0 s` 且小抬升门通过，才可进入主抬升；未通过不放大包络 |
| 主抬升 | 仅在上两门均通过后，继续策略到 `t_action=8.0 s`，总计最多 240 帧 | 新阶段明确允许左掌离 pregrasp **总距离 ≤0.15 m**、水平距离 ≤0.03 m、相对 z 在 [−0.01,+0.15] m；以同一 pregrasp 为基准，不能每帧重置起点 |
| 终态保持 | 动作预算结束后把主动关节目标设为该时刻实测角，观察 1.5 s，记录独立终态连续保持 | 继续所有保护；不再调用工程 close/lift，不保持尚未达到的闭合目标来补抓 |

平移比较继续采用原 `fk` 的 pelvis 相对坐标，并记录世界坐标变化，杯子升高与离桌高度始终用世界重力方向判断。[S3][S4][S13] 主抬升的 15 cm 是**相对于旧 3 cm 的显式新阶段许可**；只有接触和小抬升门通过后才生效。右掌 2 cm、右手 2 N、左手 60 N、臂跟踪误差 0.45 rad、原 base 保护、原关节范围/PD/力矩上限始终有效。3 cm、15 cm 均检查每个物理步，包括推理等待和 terminal hold。

建议所有组都只允许左 14 维策略命令，右臂/右手保留同一初始目标，躯干与腿沿用同一底层控制器；它们仍是动力学物体。该 right-hold 是公开适配器，不能称为模型学会保持右臂；如另测 all28，单列为次要消融。[S1] 第 79–88、123–124、187–188 行。

**监督信息边界：**策略输入仅四张真实 RGB、28 个实测关节角与固定任务文本，使用相同摄像头、关节名映射、绝对角输出语义，不给 cup truth、深度、教师动作、phase ID 或 tactile。[S5][S8][S15] 运行时安全触觉不能识别对象；若按表格使用独立杯几何来决定升级/停止，须公开称为“带评估监督门的 VLA”，而非完全传感器自主策略。更弱的纯传感器实施只能用 object-agnostic tactile/FK 判门，事后由独立杯接触证据否决假接触；两种监督方式不可混为同一实验条件。

8 s 的依据：train 教师完整轨迹 6.5 s、最早满足 held 约 4.83–4.84 s，外加较慢指令 slew 的余量。它是合理可尝试的上限，**不是保证一定够用或能成功**；若限速导致模型迟迟不能进入 lift，作为动作分布与执行器不匹配报告，不能看过测试后临时延时、改阈值或调用教师。

## 5. 权重效果与换归一化效果的最小对照

| 组 | 网络权重 | 状态归一化与动作反归一化 | 可以回答什么 |
|---|---|---|---|
| A：原始基线 | 原 pinned Toast checkpoint，权重哈希不变 | 原 checkpoint 的 Toast stats | 原 pipeline 在同一新杯位/预算下的表现 |
| B：normalization-only | **与 A 逐字节相同的网络权重**，没有梯度更新 | 与 C 完全相同的 cup **train 0..3** stats | 改坐标/输出先验本身带来的变化 |
| C：真实 fine-tune | 只在 train 0..3 训练并按预定 val 规则选出的 checkpoint | 与 B 完全相同的 cup-train pre/postprocessor | **C−B** 才是同一归一化条件下训练权重的增益 |
| N：negative hold | 不执行策略动作，保留起始目标 | 无关 | 检查静态支撑、初态抓持、评分错误 |
| P：工程参考（可选） | 冻结教师，不算 VLA | 无关 | 场景可行性参考；额外工程控制必须披露 |

A/B/C 的相机四路、提示词、采样 RNG、动作 mask、裁剪/限速、chunk/prefix、等待和阶段门完全相同。不能把 A 的旧 head-only /0.2 s 结果与 C 的四视图/长预算直接比较。工程参考的操作机制不同，旧 matched_direct 本身也承认额外 grasp/lift 预算，不是证明学到权重的反事实。[S1] 第 50–53 行；[S15]

归一化会产生很大的实际动作差异：原契约为 state/action `MEAN_STD`、图像 `IDENTITY`；本机实现的正向是 `(x−mean)/(std+eps)`，反向是 `z×std+mean`。[S9][S11] cup-train 的 thumb1/2 action mean 都是 **0.613601 rad**、std 都为 **0.128391 rad**，middle/index mean 约 −0.104049/−0.078037 rad；部分动作维度的 std 为 **0**，包括 thumb0 及多个右侧维度。[S10] 第 253–315 行。因此即使网络只输出归一化零，B 的反归一化也已给出接近闭合的目标；std=0 的维度直接固定成 mean，与网络输出无关。B 不是“没训练所以应当什么都不动”的弱基线。

必须同时替换输入 state 和输出 action 的统计，保存真正运行的 pre/postprocessor 文件哈希与 epsilon；保留图像 IDENTITY，不因本地存在图像均值/方差就顺手启用新图像归一化。不要只改 `meta/stats.json` 就宣称运行器实际加载了新统计：现有加载器从 checkpoint 文件加载两条 processor pipeline。[S9][S11][S16] 第 94–101 行。极小 state std 还可能放大新初态偏差；任何统一方差下限必须预先固定、B/C 一致，并公开其与原 native 统计的差异。

导出器已把 `meta/stats.json` 写成仅训练统计，另留 all-episodes 和 validation 统计；后两者不得供 B/C 使用。[S17] 第 287–300 行；[S8] 第 85–98 行。训练及 val 的 episode 索引也必须显式指定，不能只依赖 `info.splits` 字段自动筛选。

离线比较建议报告 val 4..5 中反归一化后的 rad MAE/RMSE，按 episode 汇总，排除 action padding；不同 stats 下的 normalized loss 不能直接当成同一物理误差。固定训练种子、训练步数或 checkpoint 选择规则后再开启新测试。C 与 Toast stats 交叉拼接可作诊断，但与它训练时的坐标不一致，不能取代 B，也不能仅靠这种交叉拼接宣称完成严格的训练/统计交互消融。

## 6. 初始积分状态、等待与实际延迟

### 6.1 每个新 seed 内配对

同一 seed 先由同一冻结 RGB-D/数值规划流程抵达**未闭合的已验证 pregrasp**，保存一次初态。A/B/C/N 从同一 `mjSTATE_INTEGRATION` 数组恢复，并恢复 targets、base_reference、kp、kd、torque_limits；模型物理数组、相机 rig 和控制器版本也须相同。只配对 qpos、同一 seed 或“看起来相同”不够。[S3] 第 90–104 行；[S4] 第 404–409 行。

记录积分数组原始 bytes 的 SHA-256，以及 controller 数组/模型物理参数的哈希；NPZ 容器文件哈希另存，因为容器元数据不等同于物理数组。现有 verifier 已计算初始积分数组哈希；四相机挂载会保存新的 model/initial_state，因此须在**挂载后**比较实际分支初态，保留 camera-only 物理等价检查。[S13] 第 96–105 行；[S18] 第 119–143 行。

各组第一次动作之前的积分状态也应匹配；一旦动作不同，后续状态自然会分叉，**不能为了“配对”把每个 chunk 都恢复回初态**。保存各 chunk 推理前与动作前快照，只要求同一初态、同一时序规则，不要求分叉后的状态仍相同。

### 6.2 两种计时问题分开报告

现有 live probe 用实测 `request_wall_seconds` 推进仿真；四视图消融则推进 `max(实际请求耗时,5 s)`，超过 5 s 标记 `FIXED_WAIT_BUDGET_OVERRUN`。[S1] 第 147–150 行；[S19] 第 98–112 行。5 s 是**人为匹配等待预算**，不是模型推理延迟；8 s 动作预算也不是整个物理 episode 只持续 8 s。

建议主比较先沿用明确的固定等待：`W=5.0 s/次`，所有 A/B/C/N 同一时间表，推理期间保持上一条已下发目标；超时统一记 timing failure，不因某组慢就悄悄给它更多物理时间。可以先用独立开发位置进行无评分延迟校准，在开启测试前一次性冻结别的 W；不能用测试成功率挑 W。暖机次数和输入模板各组相同，暖机不执行电机动作。

若每次消费 5 帧、8 s 共 240 帧，则最多 48 次推理，固定等待最多 **240 s**，再加 8 s 动作与 1.5 s terminal hold，handoff 后物理预算约 **249.5 s**，另计不超过物理步量级的时间量化。应注册一个略有余量的 handoff 相对硬上限，例如 **250 s**；现有 `robot.budget` 是绝对仿真时刻，不能忘记加上 handoff 起始 `data.time`，也不能沿用旧 90/180 s 总上限然后把超时误判成学不会。[S4] 第 159–160、172–179 行。

固定等待会让关节在旧目标下继续趋稳/接触，它改变动力学过程，不能称为实时部署表现。另行预注册真实延迟轨道时，每组用自己的实测 wall latency 推进物理并全程监控，所评估的是“权重/实现/速度”的整体系统。第一动作状态可能因此不同，须披露，不能继续声称严格时序配对；真实延迟失败后也不能改换固定等待结果作主结果。

每个 trial 至少分别记录 `t_action`、`t_inference_wait_sim`、`t_terminal`、`t_total_sim`、进程真实总 wall time、每次 request wall time、同步后的模型计算时间、图像采样时刻到命令施加的 observation age，以及人为补等候时间。请求 wall timer 包含进程通信；现有 fourview 模型内部另有同步 GPU 的计算计时，两者不是同一个量。[S20] 第 65–75 行；[S15] 第 49–61 行。等待期间发生的接触和 held 必须标注实际所处阶段，不能计成策略又多执行了若干帧。

N 组使用相同预注册等待/帧时槽但不下发动作，单列 gate failure；可继续作有保护的被动负对照观察，不得把这种被动观察说成通过手势门。任何组安全终止后都记录实际暴露时长；不为凑齐时间继续危险运动。

## 7. 新 seed、预抓取覆盖率与防止测试调参

建议开发 seed **1900..1903**，最终测试 seed **2000..2019**，每个测试 seed 每个 A/B/C 组运行一次，策略 RNG 固定为 0；这是 20 个配对初态、60 个主 trial。N 最多追加 20 个被动对照；P 如执行则统一覆盖预定 seed，不能只补跑 C 失败的位置。多 RNG 重复若需要，必须事前统一扩展所有组；重复同一 seed 不得当作独立的新杯位样本。

**这些 ID 是建议清单，目前尚未创建对应场景，也不代表给 `--seed 2000` 就能生成新位置。** 当前 `build_scene(seed)` 读取 `P01_native_v01_practice_<seed>.json`，没有在函数里随机生成候选。[S21] 第 22–30 行。实施者须先核查这些 ID 未在别的试验使用，再一次性冻结 ID→精确杯位、姿态、站姿与生成器版本/哈希，不修改旧 frozen manifests。

具体位置生成建议：保持原材料、质量、杯姿态、站姿与相机，只随机杯中心；对每个 ID 使用固定版本 `numpy.random.Generator(PCG64(seed))` 的前两个均匀数，分别映射到原中心可采样矩形 **x∈[0.118,0.332] m，y∈[0.168,0.302] m**。最终坐标数值及 NumPy 版本必须写入新评估记录，之后只读该表，不在运行时重新抽样。中心范围来自已审核布局，区域审核单另存为 `human_zone_review=true`；它不保证每个杯位都能稳定站立、碰撞安全或抵达 pregrasp。[S22][S23]

允许在**完全不运行待测策略**的统一准备流程中核验候选位置和 pregrasp，但不得试抓后按成功与否筛选杯位。预先规定 reach/初态资格条件和失败处理：保持原 20 个 seed 名单，报告 `k/20` 能抵达合格 pregrasp 的覆盖率；主操作能力报告 A/B/C 在同一 k 个合格初态上的配对成功率，并另报把准备失败计为失败的端到端 `成功数/20`。若 k 很小，明确覆盖不足；不能不断补抽，直至凑满 20 个好抓位置。

原 1000/1100/1102/1207 是 train，1002/1200 是已知 practice val；其余已用过的 1000–1207 系列也不因没进入这 6 条数据就自动成为新测试。[S7] 对新测试结果不得用于选 checkpoint、改变归一化/限速/门阈值/动作时长、手改杯位、提示词或重跑选最好。协议变更必须出新版本、保留所有旧失败，且换一组尚未查看结果的新测试位置。

## 8. 独立验证、指标与证据限制

保留现有 `verify_grasp.py` 的独立复算作为历史可比口径：从保存的模型、初态、轨迹和 motor forces 重建接触，不读取 controller 的成功声明；held 要求杯体升高 ≥0.10 m、杯底离桌 ≥0.09 m、有同手对向接触、非手支撑 <0.1 N、pelvis 倾斜 ≤5°、漂移 ≤0.03 m，最长连续合格样本区间 ≥1.0 s 才成功。[S13] 第 13–38、54–105 行。为当前任务额外明确只接受**左手**对向接触，避免原 verifier 的“任一侧”条件混入右手抓持。

建议主指标再要求：在 1.5 s terminal hold 的最后 1.0 s 内连续满足上述条件，且整个 trial 无安全保护/阶段门失败。原 verifier 的 `verified_success`、`longest_strict_hold_s` 仍照常保留；终态指标是另行注册的更严格派生指标，不能覆写旧结果。20 Hz 证据用最后样本时间减最早样本时间，不插值、不按“20 帧就是 1 秒”虚增持续时间；每个门都单独输出实测证据窗口。

每个 seed 报告 A/B/C 是否成功、首个失败阶段、最大杯抬升/最低点离桌、终态连续 hold、对向接触首现时刻（action clock 与总 simulation clock 都给）、左/右掌最大偏移、非手支撑、穿透峰值、base 漂移/倾斜、载荷与裁剪/限速比例。主要效应报告 **C−B 的配对成功率差**、两组成功/失败不一致的 seed 数、按 seed 的配对 bootstrap 区间或预先指定的精确配对检验；另给 B−A。样本单位是杯位，不能用 195 帧或相同杯位多次回放充当大样本。

独立性与可复核性有边界：

- 现有 verifier 复算的是保存的 qpos/qvel 与根据 actuator_force 反推的控制，不是每个采样点的完整积分状态重放；轨迹约 50 ms 一帧，可能漏掉中间瞬态。[S13] 第 29–37 行；[S4] 第 167–170 行。保护应每 2 ms 执行；需要更强审计时另存关键门/terminal 的高频完整物理记录。
- `no_external_base_force` 当前检查的是复算末态的力数组，`equality_constraints` 只是模型中约束数，单靠这两个输出不足以证明全程没有外力、动态加约束或其他绑定。[S13] 第 104–105 行。执行端应记录模型/约束哈希和逐步或逐窗口 `xfrc_applied/qfrc_applied` 证据，禁止 mocap/weld/物体绑定，核对动作来源链与真实 motor targets。
- 相同 MuJoCo 场景中的独立验证器与控制器仍共享物理模型；录像、渲染或教师 `environment_result` 不能独立证明真实机器人成功。杯质量/碰撞几何是工程近似，四相机也不等同于原 Toast 数据集的标定。[S21] 第 74–96 行；[S8] 第 99–100 行；[S19] 对应冻结说明。
- 4 条 train、2 条已知位置 val 的规模很小；新测试成功也仅支持该场景和同一物理/相机分布下从合格 pregrasp 开始的闭合与抬升，不能宣称学会完整寻找、接近、跨物体或实体部署。

主线实施前应固定：模型与实际 processor 哈希；数据 split/统计哈希；checkpoint 选择规则；新杯位表与 pregrasp 资格规则；匹配初态与模型数组；所有阶段期限/阈值；8 s/240 帧与推理次数上限；固定等待/真实延迟轨道；终态评分与统计方法。**本审计不实施这些改动，也不把建议视为已经完成的冻结或验证。**

## 9. 主源索引与只读复核信息

下列链接均指向实际读取的本地主源；链接后行号说明对应的证据区间。二进制 NPZ 无文本行号，采用键名、选择公式与哈希定位。

[S1]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/vla_live_probe.py:26
[S2]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/validation/vla_live_mask_v3/manifest.json:6
[S3]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/vla_handoff.py:90
[S4]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/pantry_robot.py:36
[S5]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/collect_fourview_demos.py:33
[S6]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/vision_grasp.py:157
[S7]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/demonstrations/cup_fourview_v1/collection_manifest.json:3
[S8]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/datasets/cup_fourview_v1/meta/engineering_export.json:73
[S9]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/assets/vla_checkpoint_metadata/kiteml_g1_smolvla/contract.json:135
[S10]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/datasets/cup_fourview_v1/meta/stats.json:253
[S11]: /mnt/c/Users/23660/Documents/Codex/2026-10-23/files-mentioned-by-the-user-hk/work/vla-env/lib/python3.12/site-packages/lerobot/processor/normalize_processor.py:325
[S12]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/assets/robot_profile.json:1063
[S13]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/verify_grasp.py:13
[S14]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/episodes/handoff_pregrasp_1000/handoff_metadata.json:14
[S15]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/fourview_policy.py:22
[S16]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/smolvla_preview.py:92
[S17]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/export_fourview_demos.py:287
[S18]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/fourview_camera.py:119
[S19]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/fourview_trial.py:98
[S20]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/smolvla_runtime.py:65
[S21]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/pantry_scene.py:22
[S22]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/scenes/pantry/p01_zones_v01/zone_config.json:58
[S23]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/scenes/pantry/p01_zones_v01/human_review.json:2
[A1]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/demonstrations/cup_fourview_v1/episodes/demo_1000/actions.json:1572
[D0]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/demonstrations/cup_fourview_v1/episodes/demo_1000/samples.npz
[D1]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/demonstrations/cup_fourview_v1/episodes/demo_1100/samples.npz
[D2]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/demonstrations/cup_fourview_v1/episodes/demo_1102/samples.npz
[D3]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/demonstrations/cup_fourview_v1/episodes/demo_1207/samples.npz
[D4]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/demonstrations/cup_fourview_v1/episodes/demo_1002/samples.npz
[D5]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/demonstrations/cup_fourview_v1/episodes/demo_1200/samples.npz
[V0]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/demonstrations/cup_fourview_v1/episodes/demo_1000/verified_samples.json:3177
[V1]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/demonstrations/cup_fourview_v1/episodes/demo_1100/verified_samples.json:3260
[V2]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/demonstrations/cup_fourview_v1/episodes/demo_1102/verified_samples.json:5797
[V3]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/demonstrations/cup_fourview_v1/episodes/demo_1207/verified_samples.json:5775
[V4]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/demonstrations/cup_fourview_v1/episodes/demo_1002/verified_samples.json:3775
[V5]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/demonstrations/cup_fourview_v1/episodes/demo_1200/verified_samples.json:3238
[H0]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/demonstrations/cup_fourview_v1/episodes/demo_1000/verified_samples.json:4673
[H1]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/demonstrations/cup_fourview_v1/episodes/demo_1100/verified_samples.json:4739
[H2]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/demonstrations/cup_fourview_v1/episodes/demo_1102/verified_samples.json:7310
[H3]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/demonstrations/cup_fourview_v1/episodes/demo_1207/verified_samples.json:7270
[H4]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/demonstrations/cup_fourview_v1/episodes/demo_1002/verified_samples.json:5253
[H5]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/demonstrations/cup_fourview_v1/episodes/demo_1200/verified_samples.json:4734

本次复核的关键 SHA-256：

| 主源 | SHA-256 |
|---|---|
| `vla_live_probe.py` | `74c5aedddd7b90f8e14e8f5ec5783669ce455ffbbc09af9e9ca9b546b50ff662` |
| `vla_handoff.py` | `79cd103db1c060dfd9f51bb8a53a5d020d581b2d3608f09b253a389a61bb05fd` |
| `verify_grasp.py` | `4dc63b46af9c88f0c34d7ff6776f095048551a57054793a24497f3de112957f2` |
| `pantry_robot.py` | `f4f1467d2e1f41052fcf6e14ab344f7ac22caa4ba04a9fa052405d6228d7e69b` |
| `fourview_trial.py` | `ee35dd681026b8f54b750be11e62d69379d1c393d27bba6c872cca13362a8a48` |
| `datasets/cup_fourview_v1/meta/stats.json` | `9c514818a448a1c5defb19eec5e361f40c440635fa1ed81399c91d86c898444c` |
| demo_1000 `samples.npz` | `f9ecf5ba72bfa6e8201308230879a2d350a285bd216f8559b70c8149f79a5bb5` |

表中 timing 可用 `first(row.time−simulation_time[0] where row.opposing_contacts/held)` 复核；slew 用 `max(abs(diff(action[:,15:17])) / diff(simulation_time)[:,None])` 复核。下标依据 [S8] 的 native/workspace 命名序列，不能按另一套手指顺序重排。本文链接和哈希对应审计读取时刻；主线后续新增训练文件不构成本审计的实验结果。
