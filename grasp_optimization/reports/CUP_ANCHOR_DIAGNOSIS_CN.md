# 杯子微调 full-v1：仅训练位置 seed1000 的只读诊断

日期：2026-10-24。本次只检查 `cup_sft1_1000_original / statistics_only / finetuned`、工程 `demo_1000` 与已保存的离线验证预测。**没有查看 1300..1303 的试验结果或汇总结果，没有读取大权重、运行 GPU/策略推理或调用 `mj_step`。** CPU `mj_forward` 仅用于保存状态的前向几何及静态关节替换，不生成轨迹、不重跑物理。唯一写入文件是本文；不改当前协议、执行器、checkpoint 或其他冻结文件。

## 1. 结论及证据强度

**直接证据：微调组确实执行了拇指闭合，但在形成对向抓持之前，臂腕运动使掌心越过 closing 的 3 cm 边界。不能把本例简化为“手指没有闭合”，也不能据此宣称已学会抓杯。** 三组都是 `LEFT_PALM_DEPARTURE_CLOSING`，没有进入下一传感器阶段、没有形成杯子对向抓持。[O][S][F]

- **已证实：**微调组停止时 thumb1/2 的实际角约 0.15782/0.15859 rad、速度约 0.90766/0.96019 rad/s；目标已推进到 0.186 rad。手指不是静止的。[FA][FE]
- **已证实：**同一时刻掌位偏移为 `[+11.55, −20.39, +19.00] mm`，模长 30.170 mm。仅把左手七个指关节换成末态角、其余保持初态，掌位变化为零；替换臂腕七关节则产生 33.406 mm 位移。越界直接涉及臂腕/其余姿态，不是手指在其自身关节上闭合所直接平移掌心。[FI][FE][FM][FK]
- **已证实：**微调后的离线左臂七维与左手七维误差都低于 statistics-only，但左臂仍是更大的误差块。整体动作误差变好，不等于接触前的掌位保持已达到要求。[OP][SP][FP][GT]
- **尚属解释：**提前产生抬臂动作、动作阶段混合、杯位之间的姿态均值偏置、闭环状态偏移，都可能与这些现象相容；当前记录不足以确定哪一个是训练误差的根因。下面的建议仅供新版本实验，不用于本轮改参数或重选 checkpoint。

## 2. 训练背景与配对条件

小型训练记录显示：总优化 700 步，按离线验证选中 300 步，122 个参数张量改变，冻结参数未改变；另一个已存在的小型审计 JSON 报告 normalization-only 与 best 两个保存文件各 500 个张量均匹配已记录参数。[TR] 第 2–6、145–167 行；[TA] 第 2–12 行。本次读取的是这些记录，**没有重新读取大权重或独立重做逐张量审计**。微调 anchor 推理记录里的所选权重哈希也与训练 result 的 selected hash 相同。[F][TR]

本轮按实际冻结的 full-v1 解释结果：30 Hz、每次执行前 6 帧、固定等待 2 s、总动作预算 8 s；closing 掌位半径 0.03 m；臂/指命令限速 0.75/1 rad/s；传感器阶段门只使用 object-agnostic tactile 与本体状态，杯身份在事后核验。[CFG] 第 76–103 行。这里没有把上一份审计的建议数值替换进当前执行。

只读逐数组比较得到：三组 `initial_state.npz` 中的 `mujoco_integration_state、targets、base_reference、kp、kd、torque_limits` **完全相同**。三个独立核验文件的初始积分数组 SHA-256 都是：

`906790d9f8b7a6b491fdab598565d6ca0b8babb186b87b5f35819bdfb6feb2dc`。[OV][SV][FV]

第一次 2 s 等待内的已记录 `time、qpos、qvel、joint_targets、actuator_force` 也逐元素相同，第一组四张输入图像的哈希在三组之间相同。[OT][ST][FT]；[O][S][F] 的首个 chunk 输入。等待结束时，掌心仅共同漂移约 **1.504 mm**，说明随后约 30 mm 的越界不能仅由“三组起点不同”解释。

请求真实 wall latency 首次约为 0.611/0.677/0.921 s，三组物理等待均补齐到 2 s。[O] 第 440 行起；[S][F] 第 152 行起。不能把 2 s 称为模型真实延迟；在本例也不能用推理快慢解释初次动作前的状态差异。**共同存在的 2 s 观测陈旧效应并未被消融，仍可能影响所有组。**

## 3. 三组实际停止在哪里

| seed1000 组别 | 累计动作时间 | 已记录执行帧 / 推理次数 | 自 handoff 起物理时间 | 末态掌心偏移 | 传感器阶段 / terminal hold |
|---|---:|---:|---:|---:|---|
| original | 0.450 s | 14 / 3 | 6.450 s | 30.140 mm | closing / 0 s |
| statistics_only | 0.188 s | 6 / 1 | 2.188 s | 30.425 mm | closing / 0 s |
| finetuned | 0.190 s | 6 / 1 | 2.190 s | 30.170 mm | closing / 0 s |

执行状态、动作时间与阶段来自 [O][S][F]；位移由各组 initial/final 完整状态和 model 的 FK 复算。[OI][OE][OM][SI][SE][SM][FI][FE][FM] “6 帧”包含因保护而只执行了部分时长的最后一帧，不能一概乘成完整 0.2 s。original 三个 chunk 分别执行 6、6、2 帧。

statistics-only 与 finetuned **都在 0.2 s 早期手势检查之前**触发掌位保护，不能归因为 `NO_EARLY_THUMB_GESTURE`，更不能归因为已耗尽 2 s 动作接触期限。执行器先检查掌位，再检查手势和期限；三个 `sensor_phases` 为空。[EXEC] 第 197–230 行；[O][S][F]

最后执行行的最大主动臂目标跟踪误差分别约 **0.04072、0.05574、0.01886 rad**，均小于冻结 0.45 rad 阈值。[OA][SA][FA][CFG] 这说明此处的直接停止原因是末端位置越界；**关节追踪较好仍可追踪到错误的接触前姿态**。不能据此证明控制器全程没有任何跟踪误差。

## 4. 手指：有闭合，缺少的是已实现的杯子对向抓持

所有七指向量按 `[thumb0, thumb1, thumb2, middle0, middle1, index0, index1]` 排列。这里的 native 是**已反归一化的绝对关节目标**，不是网络归一化 latent，也不是增量。

| 组 | 首个 native 手目标 | 最后实际施加的手目标 | 停止时实测手角 |
|---|---|---|---|
| original | `[-.81606,.81836,.11507,−.62568,−1.33469,−.62773,−.96127]` | `[-.44133,.44133,.05881,−.44133,−.44133,−.44133,−.44133]` | `[-.41797,.41829,.03604,−.35304,−.39032,−.37940,−.40079]` |
| statistics_only | `[0,.44245,.48078,−.10481,−.06125,−.10702,−.07085]` | `[0,.184,.184,−.10272,−.06520,−.11244,−.06985]` | `[.00012,.15691,.15682,−.09671,−.06483,−.10904,−.06924]` |
| finetuned | `[0,.30034,.21374,.02393,.01243,.03157,.00319]` | `[0,.186,.186,0,0,0,−.00180]` | `[−.00009,.15782,.15859,.00306,−.00088,−.00114,−.00087]` |

首个目标取各组 `chunk_001_native_absolute.npy[0,0]`；最后 applied 取 original 的 chunk003 末行、另两组 chunk001 末行；末态实测角来自 `final_state.npz` 的完整积分状态，和最后 applied 的实测角一致。[ON][SN][FN][OA][SA][FA][OE][SE][FE]

微调组 thumb1/2 停止时的 `qvel≈0.908/0.960 rad/s`，statistics-only 为 `0.967/0.971 rad/s`，都还在正向闭合。original 的 thumb0 大幅转负，而 thumb2 仅约 0.036 rad，和工程示范的 `thumb0≈0、thumb1/2` 共同闭合不同。**三组都不能被概括为“没有手指动作”，但动作几何不同。**

微调组执行后的其余四指接近零，比 statistics-only 立即下发约 −0.1/−0.07 rad 的动作更接近示范初段的开指状态。不过还存在重要限定：**微调首 6 帧、四个非拇指原始目标中，21/24 个为正，超出这些关节非正的合法范围，随后被裁到 0。** middle0/index0 在这六帧全为正。因此“执行层呈现拇指先行”是网络与范围裁剪共同作用的证据，不能把它直接等同为网络精确学会了零目标或完整指序。[FN][FA]；[EXEC] 第 269–289 行；[LIMIT]

停止后 `execute()` 会把主动目标改成实测角，随后保存 final_state，且不再积分。[EXEC] 第 295–310 行。因此不能读取 final_state 的 `targets` 与 q 相等，就倒推模型没有给出闭合目标；实际下发命令必须看 applied 记录。这里 qvel 取 final_state，是因为另两组约 50 ms 的 trajectory 末样本停在 13.920 s，早于真正停止的 13.958/13.960 s，不能混成同一时刻。

## 5. 对照工程 demo_1000 的最早合指段

示范先用 0.7 s 只转拇指，再用 0.3 s 把中指/食指推进到设定闭合量的 0.15 倍，之后 settle；最初 1.5 s 的左臂七维目标基本保持 pregrasp 值，最大变化不足约 `1e−6 rad`。[DEMO][DA][TEACH]

| 示范相对时间 | thumb1/2 目标 | thumb1/2 实测角 | middle0/1、index0/1 目标 |
|---|---|---|---|
| 0.200 s | `.13114/.13114` | `.10004/.10025` | 全为 0 |
| 0.434 s | `.44238/.44238` | `.34062/.37664` | 全为 0 |
| 0.700 s | `.65000/.65000` | `.30699/.47580` | 约 0，刚进入合指插值 |
| 0.800 s | `.65000/.65000` | `.30343/.47488` | `[-.03218,−.02414,−.03218,−.02414]` |
| 1.000 s | `.65000/.65000` | `.27560/.47297` | `[-.12,−.09,−.12,−.09]` |

来自 `samples.npz` 的实际 `simulation_time/state/action`；0.434 s 行不是把名义 13/30 当作精确物理时刻。[DEMO] 角度在接触后偏离 0.65 目标并不自动表示没追踪：PD、力矩与接触约束允许实测角停在更小位置。

示范保存的实际接触记录中，thumb 首次达到 0.1 N 的样本在相对 **0.380 s**；相对 **0.430 s** 首次同时出现 thumb/index/middle 杯接触，载荷约 **5.810/3.693/2.096 N**，thumb/index 合力法向余弦约 **−0.76494**，满足对向条件。[DC][DV] 此时 CPU FK 的掌位变化约 **3.607 mm**；最接近前 0.2 s 的 trajectory 样本实际在 +0.180 s，掌位变化约 1.996 mm，不把它伪称为精确 +0.200 s。[DT][DM][DP][FK]

因此微调组在约 0.19 s 就被保护截断，早于教师本例首次可见对向接触的约 0.43 s。它的拇指实际转动幅度甚至已高于示范 +0.2 s 的约 0.10 rad。**当前首要可见差异是闭合期间没有像教师那样保持臂腕/掌位；“拇指尚未触杯”与“不会闭合”必须分开。** 教师没有本轮每次 2 s 的推理等待，且用 500 Hz smoothstep 标签；这个对照是已有轨迹的行为比较，不是严格匹配时序的干预实验。

## 6. 臂、腕漂移的几何分解

共同 pregrasp 左臂目标是：

`[-.863578,.517200,−.588252,.822255,−.884768,.008208,.612513]`

顺序为 shoulder_pitch/roll/yaw、elbow、wrist_roll/pitch/yaw。下表是**实际下发末目标减 pregrasp 目标**，不是原始网络目标：[OA][SA][FA][OI][SI][FI]

| 关节 | original | statistics_only | finetuned |
|---|---:|---:|---:|
| shoulder_pitch | +.33100 | −.13800 | −.05437 |
| shoulder_roll | −.07003 | +.00400 | −.01129 |
| shoulder_yaw | +.33100 | −.04967 | −.02111 |
| elbow | −.33100 | −.06586 | −.05703 |
| wrist_roll | +.33100 | −.05422 | −.05120 |
| wrist_pitch | −.14943 | +.06837 | +.05879 |
| wrist_yaw | −.33100 | +.01752 | −.01549 |

微调首个 native 左臂目标约 `[-.99558,.49724,−.66378,.76977,−.92754,−.00327,.51976]`，在同一 chunk 的前 6 帧中也有变化，例如 wrist_pitch 从约 −.00327 到 +.07607。最后 limited 目标与首个 native 不是同一个量，不能拿第一行 raw 代表全程，也不能只检查原始角度在 joint range 内就认定它能保持 pregrasp。三组首 6 帧左臂 raw 均未违反关节角范围，仍然会经允许的角度变化产生过大的掌位平移。[ON][SN][FN][LIMIT]

用各组 model 与初态 qpos，只把指定关节换成该组**停止时实测角**，其他 qpos 固定不动，CPU `mj_forward` 得到：

| 只替换的块 | original 掌位移 | statistics_only 掌位移 | finetuned 掌位移 |
|---|---:|---:|---:|
| 指七维 | 0.000 mm | 0.000 mm | 0.000 mm |
| 臂腕七维 | 27.879 mm | 35.531 mm | 33.406 mm |
| 肩/肘四维 | 46.911 mm | 43.569 mm | 37.428 mm |
| 腕三维 | 42.315 mm | 9.393 mm | 7.292 mm |
| 完整真实末态 | 30.140 mm | 30.425 mm | 30.170 mm |

数据源为各组 model、initial_state 与 final_state；FK 定义见 [FK]。这是**静态几何敏感性比较**，不是重新运行“冻结某关节”的物理试验；各行不能相加，肩/肘与腕可能相互抵消，完整末态还有其他关节/姿态的变化。不能把 37.428 mm 与 7.292 mm 化成因果贡献百分比。

它支持：微调组问题涉及臂的接触前定位，不能只叫“腕漂了”；original 的大幅腕/臂运动则有明显抵消。末态掌方向相对初态旋转约 20.630°、2.985°、5.110°。finetuned 末态 pelvis 倾斜/漂移都很小，三组独立核验的最大 pelvis 倾斜都不足 0.08°、漂移不足 1 mm，不支持把本例直接归因于机器人整体摔倒。[OV][SV][FV]

## 7. 接触记录：单指碰杯不等于对向握持

下表直接累加 `contact_trace.json` 里**明确含 task_cup 与 left_hand 对应指体**的 normal_force，而非把手碰桌面的触觉算作杯接触；只报告已有记录内峰值。[OC][SC][FC] 该记录由诊断机器人在已有约 50 ms 轨迹采样时刻保存实际接触，不是本次重新积分所得。[DIAG]

| 组 | 杯上 thumb 峰值 | 杯上 index 峰值 | 杯上 middle 峰值 | 已记录杯子左手对向接触 |
|---|---:|---:|---:|---|
| original | 0 N | 5.071 N | 7.102 N | 无 |
| statistics_only | 0 N | 0 N | 1.359 N | 无 |
| finetuned | 0 N | 0 N | 1.718 N | 无 |

三组最早 ≥0.1 N 的左手杯接触都在仿真 **13.870 s**，即第一次动作开始后约 0.100 s，涉及 `left_hand_middle_0_link`。[OC][SC][FC] 微调此时非拇指仍接近开指，却已经出现中指近端接触；这和整只手随臂腕移动接近/碰到杯壁的解释相容，**不能仅凭接触力峰值断言模型在进行成功合指**。recorded thumb 杯接触为零，同时事后左手专用验证也没有任何对向样本。[OL][SL][FL]

独立核验的最大杯体升高为约 3.021、5.623、2.992 mm，连续 strict hold 都是 0，均没有 10 cm lift 成功证据。[OV][SV][FV] 这些短暂升高可能包含杯体受碰撞/倾斜时的运动，不能解释成抓住后的抬升；要判定原因还需接触、最低点离桌与支撑状态一起看。三组暴露时间不同，不能按这些毫米峰值给模型能力排序。

限制：约 50 ms 的保存间隔不能排除样本间很短的接触；这里的“无”指**保存接触记录和独立核验中未见**，不是声称每个 2 ms 步都已被本次审计排除。尤其 statistics-only/finetuned 的最后 trajectory 样本早于停止点；本次最终几何/速度用 final_state 补足，未凭此捏造未保存的接触力时间序列。

## 8. 离线验证：左臂七维与左手七维分别看

使用已保存的三个 prediction NPZ，分别取 `indices=[780,810,860,920,975,1005,1055,1115]`。GT 为允许读取的 `/tmp/cup-native-training-cache-v1/action.npy`，形状 1170×28；每个 index 向后取 50 帧，前一 val episode 边界为 975、后一边界为 1170，本次八个窗口都未越界、均无需 padding。按训练脚本相同的“每窗口先求均值，再对八窗口等权”口径复算；分块用左臂列 `[0:7]`、左手列 `[14:21]`。[OP][SP][FP][GT][VAL]

| 已保存的离线预测 | 左臂7 MSE（rad²） | 左臂7 MAE（rad） | 左手7 MSE（rad²） | 左手7 MAE（rad） | 全28 MSE（rad²） |
|---|---:|---:|---:|---:|---:|
| 原权重 / 原统计 | .607815 | .658242 | .581565 | .692473 | .456268 |
| 原权重 / cup统计 | .030573 | .129170 | .004538 | .031506 | .008778 |
| 微调权重 / cup统计 | .018225 | .100876 | .001533 | .015156 | .004939 |

全28及左手 MSE 复算与已有 result 一致到浮点计算精度。相同 cup 统计下，微调平均降低左臂 MSE 约 40%、左手 MSE 约 66%；但微调后左臂 MSE 仍约为左手的 **11.9 倍**。不能让全28平均数或手指改善掩盖臂腕误差。[TR][OP][SP][FP]

也不是每个窗口都更好：例如 index860，左臂 MSE 为 `.007750 → .010076`；index920 为 `.012775 → .014589`。这只供既定离线诊断，不据此重选 checkpoint。八个窗口来自两个已知 practice val episode，不是八个独立杯位，更不是本轮新位置测试成功率。

离线改善与当前 anchor 失败可以同时成立：绝对角误差较小仍可通过末端运动学产生厘米级掌位误差；闭环中，策略同时控制臂和指，尚未得到对向接触就因臂运动失去继续闭合的机会。仅用离线 MSE 不能证明这一因果链，但现场保存的 q/目标/FK/接触对“臂定位尚未满足当前门”提供了直接证据。

## 9. 留给新版本的实验建议，本轮不实施

1. **先检验接触前臂保持这个假设。** 另注册“仅闭合阶段保留 pregrasp 臂目标，仍由 VLA 输出手指”的诊断消融，对 original/statistics-only/finetuned 使用同一适配器。公开说明这是新增臂保持先验；即使成功也不能冒称原 full-v1 自主成功，且不能加入脚本合指。它用于区分“手部输出本来是否有机会形成接触”和“臂漂移把机会截断”。当前三组记录不重跑、不补动作。
2. **分别约束/评价臂和手，尤其是 pregrasp 后尚未接触的时段。** 在新开发数据上增加闭合期臂目标/掌位及方向误差、native 关节范围违反率的诊断；检查是否需要更多“保持臂位并闭合”的示范或独立的任务空间损失。当前证据不够决定应该改 loss 权重还是训练步数，也不能据 anchor 失败即时换 checkpoint。
3. **检查时间阶段与预测窗口。** 教师最初 1.5 s 基本保持臂目标，而首个 50 帧 chunk 也覆盖后续即将试抬的时段。用训练/独立开发集预注册分析“前几帧是否混入未来臂动作”，并分开测固定 2 s 等待与更低观测延迟；当前不能把“预测未来 50 帧”本身直接诊断为实现 bug。
4. **把裁剪前后分开报告。** finetuned 非拇指首 6 帧 21/24 为正而被裁到 0，需要在新开发集判断这是小幅合法性误差、时序误差还是系统性偏置。不要只看 applied 的开指就认定网络已精确模仿手序，也不要把它改成脚本零目标来修饰本轮结果。
5. **保留失败和统计对照。** 本轮 full-v1 参数、checkpoint300、旧/新 seed 结果与 frozen manifests 全部照原流程保留。若采纳任何新适配器、训练目标、等待时长或阈值，另起协议版本，并使用未据其结果调参的独立新位置；本诊断不对未查看的新测试作任何效果推断。

## 10. 主源定位与复算说明

文本证据链接含行号；NPZ/NPY/MJB 无文本行号，以键、数组列和下述口径定位。所有物理 episode 链接均限定 seed1000；没有链接或读取新 seed 结果。

- runtime：`native[0, frame, 0:7/14:21]`；applied 的 `raw_target、command_target、actual_joint_q、time`；完整 q/qvel 取 `final_state.mujoco_integration_state`，用该 episode model 的 joint qpos/dof 地址映射，绝不把 actuator 列号当 qpos 列号。
- FK：`R_pelvis.T @ (site_xpos[left_palm]−xpos[pelvis])`，位移基准为恢复后的 initial_state。静态替换只改 qpos，不积分、不解释为接触动力学结果。
- 接触：从已保存 contact_trace 中筛选 task_cup 与 left_hand，逐指累加载荷；对向时统一法向方向，检查 thumb/另一指各 ≥0.1 N 且法向余弦 <−0.5。零载荷表示记录中没有相应载荷证据。

本次关键读取哈希：

| 文件 | SHA-256 |
|---|---|
| evaluate_cup_policy.py | `50fa274b0c58eb3dd005feab388ab39159793a89c02cc5d0f05cf19d06bee495` |
| training/cup_fourview_sft_v1/result.json | `13be691374d4266c279a64c06360441f4607c08482c7cfef6a3efb2a674e2cef` |
| original chunk001 native | `0342250eb6200ad2d08949a8bbda056df7ad9c2f5d8a92caba4e0f14a5b134b4` |
| statistics_only chunk001 native | `71c7a4960e89a6bafa20f028bf999c2d71ccba1644433379e08c99342af06e95` |
| finetuned chunk001 native | `7ceec36c804f5eee176e6ba845797d51879ef34d92cb8b41fdcad54571c66ff3` |
| finetuned chunk001 applied | `cd2e4fcd462e9ca5711370191e0cd977bd4f45afc6c1c94fce37e1c7fbe316c7` |
| finetuned final_state | `1f6502c08f6225fe22049269965960b918639db2d54c45d610d453c720042f0b` |

[TR]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/training/cup_fourview_sft_v1/result.json:2
[TA]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/reports/cup_checkpoint_tensor_audit.json:2
[CFG]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/validation/cup_finetune_full_v1/manifest.json:76
[EXEC]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/evaluate_cup_policy.py:188
[LIMIT]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/vla_live_probe.py:91
[FK]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/pantry_robot.py:184
[DIAG]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/diagnose_grasp.py:21
[VAL]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/train_cup_policy.py:107
[TEACH]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/vision_grasp_v2.py:81
[O]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/episodes/cup_sft1_1000_original/vla_tool_001/result.json:2
[S]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/episodes/cup_sft1_1000_statistics_only/vla_tool_001/result.json:2
[F]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/episodes/cup_sft1_1000_finetuned/vla_tool_001/result.json:2
[ON]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/episodes/cup_sft1_1000_original/vla_tool_001/chunk_001_native_absolute.npy
[SN]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/episodes/cup_sft1_1000_statistics_only/vla_tool_001/chunk_001_native_absolute.npy
[FN]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/episodes/cup_sft1_1000_finetuned/vla_tool_001/chunk_001_native_absolute.npy
[OA]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/episodes/cup_sft1_1000_original/vla_tool_001/chunk_003_applied.npz
[SA]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/episodes/cup_sft1_1000_statistics_only/vla_tool_001/chunk_001_applied.npz
[FA]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/episodes/cup_sft1_1000_finetuned/vla_tool_001/chunk_001_applied.npz
[OI]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/episodes/cup_sft1_1000_original/initial_state.npz
[SI]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/episodes/cup_sft1_1000_statistics_only/initial_state.npz
[FI]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/episodes/cup_sft1_1000_finetuned/initial_state.npz
[OE]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/episodes/cup_sft1_1000_original/final_state.npz
[SE]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/episodes/cup_sft1_1000_statistics_only/final_state.npz
[FE]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/episodes/cup_sft1_1000_finetuned/final_state.npz
[OM]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/episodes/cup_sft1_1000_original/model.mjb
[SM]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/episodes/cup_sft1_1000_statistics_only/model.mjb
[FM]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/episodes/cup_sft1_1000_finetuned/model.mjb
[OT]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/episodes/cup_sft1_1000_original/trajectory.npz
[ST]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/episodes/cup_sft1_1000_statistics_only/trajectory.npz
[FT]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/episodes/cup_sft1_1000_finetuned/trajectory.npz
[OV]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/episodes/cup_sft1_1000_original/independent_verification.json:2
[SV]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/episodes/cup_sft1_1000_statistics_only/independent_verification.json:2
[FV]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/episodes/cup_sft1_1000_finetuned/independent_verification.json:2
[OC]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/episodes/cup_sft1_1000_original/contact_trace.json:111556
[SC]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/episodes/cup_sft1_1000_statistics_only/contact_trace.json:111556
[FC]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/episodes/cup_sft1_1000_finetuned/contact_trace.json:111556
[OL]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/episodes/cup_sft1_1000_original/left_verification_samples.json:1
[SL]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/episodes/cup_sft1_1000_statistics_only/left_verification_samples.json:1
[FL]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/episodes/cup_sft1_1000_finetuned/left_verification_samples.json:1
[DEMO]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/demonstrations/cup_fourview_v1/episodes/demo_1000/samples.npz
[DA]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/demonstrations/cup_fourview_v1/episodes/demo_1000/actions.json:1572
[DC]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/demonstrations/cup_fourview_v1/episodes/demo_1000/contact_trace.json:643205
[DV]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/demonstrations/cup_fourview_v1/episodes/demo_1000/verified_samples.json:3177
[DT]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/demonstrations/cup_fourview_v1/episodes/demo_1000/trajectory.npz
[DM]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/demonstrations/cup_fourview_v1/episodes/demo_1000/model.mjb
[DP]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/demonstrations/cup_fourview_v1/episodes/demo_1000/pregrasp_state.npz
[OP]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/training/cup_fourview_sft_v1/original_statistics_validation_predictions.npz
[SP]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/training/cup_fourview_sft_v1/normalization_only_validation_predictions.npz
[FP]: /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/training/cup_fourview_sft_v1/selected_trained_validation_predictions.npz
[GT]: /tmp/cup-native-training-cache-v1/action.npy
