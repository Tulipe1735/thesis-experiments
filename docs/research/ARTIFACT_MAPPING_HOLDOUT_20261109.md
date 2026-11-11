# 同一 artifact 的 code / skill 映射验证

日期：2026-11-10。状态：已执行。边界：MuJoCo仿真；两个已知成功开发初态上的调用复现，不是新控制器学习或未见初态泛化。

## 1. 结论

存量显式mapping记录中没有code/skill配对成功；既有T01、T02成功工件仍然可用。本轮修复映射语义后，T01和T02各完成code直接执行1/1、skill按ID调用1/1，合计4/4独立验收成功。这是**工程参照工件的两种调用路径复现**，不是新增Agent控制能力。

问题在于旧skill路径让模型凭说明重写控制器，且T01导出器附加的左关节-only限制与成功实现的Cartesian/腰部接口不同。现在code直接执行工件编译结果；skill卡保留工件ID、契约、代码哈希，模型返回ID和公共参数后分派到同一冻结实现。未改原控制策略、评价器或成功工件。

映射实现：`experiments/grow_up_harness_v2/harness/artifact_mapping.py`；入口沿用`calibration/mapping_holdout.py`。存量审计索引：本轮运行的`prior_evidence_audit.json`（1011个既有证据文件，列出原始判定路径及哈希）。ROS正式Skill与T02 v3的既有成功不能替代同工件配对证据。

## 2. 结果与原始证据

运行根目录（下文R）：`experiments/grow_up_harness_v2/runs/artifact_mapping_repair_20261110_001/`。

| 任务 / 保存初态 | 工件 | code | skill调用 | 各臂仿真时长 |
|---|---|---|---|---|
| T01 / t01_110901_000 | t01_cup_to_tray v9，8d9baf1c7c85… | 1/1成功 | 1/1成功 | 69.486秒 |
| T02 / t02_92301_001 | t02_cup1_lift_clear_then_recorded@c15975503e7e | 1/1成功 | 1/1成功 | 197.050秒 |

原始独立判定（路径相对仓库根）：

- T01 code：`experiments/grow_up_harness_v2/runs/artifact_mapping_repair_20261110_001/T01/t01_110901_000/code/verdict.json`。
- T01 skill：`experiments/grow_up_harness_v2/runs/artifact_mapping_repair_20261110_001/T01/t01_110901_000/skill/execution/verdict.json`。
- T02 code：`experiments/grow_up_harness_v2/runs/artifact_mapping_repair_20261110_001/T02/t02_92301_001/code/verdict.json`。
- T02 skill：`experiments/grow_up_harness_v2/runs/artifact_mapping_repair_20261110_001/T02/t02_92301_001/skill/execution/verdict.json`。

T01杯底最终余量9.850mm、托盘支撑力1.864N；T02三杯余量分别11.814、10.259、8.059mm，三杯共同稳定7.800秒，最终手接触力均为0。两个wait负对照均失败。

两任务各自的两臂：实际初态数组一致、source_sha256一致、trajectory.npz字节一致。T01代码SHA为`d4e07dbd9d1f939ce2bd7a92086c2b3774b94817fffa697568ff17943d9178e7`；T02为`de4111cbf67eed3f00e32dc278ccd3aadafc2a9a57b41c3bcff43cb3661046ae`，分别与历史成功result.json记录一致。模型原始回复在`R/<family>/<task>/skill/proposal_01/model/reply.txt`，实际调用和绑定在同级`invocation.json`、`binding.json`；没有生成控制器source。

四段1×原速录像：`R/videos/T01_code.mp4`、`T01_skill.mp4`、`T02_code.mp4`、`T02_skill.mp4`。它们由本轮保存的qpos/qvel渲染，不再执行物理；每段同名JSON绑定模型、轨迹、判定、视频哈希及帧数。不能把两臂轨迹相同解读为skill视频冒用code：两臂分别执行并保存，随后核对轨迹字节。最终四视频核对记录为`R/video_audit.json`，总交付索引为`R/summary.json`。

## 3. 成本与代码验证

以下照搬`R/T01/summary.json`和`R/T02/summary.json`的counts；6个物理回合包括4个目标臂和2个负对照。

| counts字段 | T01 | T02 |
|---|---:|---:|
| proposer_calls | 1 | 1 |
| critic_calls | 0 | 0 |
| gate_rejections | 0 | 0 |
| physical_episodes | 3 | 3 |
| commands | 132 | 2578 |
| worker_calls | 8 | 2570 |
| simulation_s | 141.72200000003883 | 396.85000000042544 |
| llm_wall_s | 2.5679397819912992 | 1.5068599179940065 |
| prompt_tokens | 4479 | 2741 |
| completion_tokens | 73 | 49 |

开跑前278项单测通过；审查发现两项边界问题并在全部物理结束后修正，最终280项通过。日志：`R/unit_tests.log`、`R/final_unit_tests.log`。后两项检查初态副本被更改时拒绝运行、调用拒绝不计入物理失败分母。**本次物理运行没有使用这两个后来新增的保护**；实际初态副本哈希由落盘数据另行核实，未发现变化。执行时源码35个文本文件保存在`R/source_snapshot/`，清单为`execution_source_snapshot.json`；后续变化为`post_run_hardening.json`。

## 4. 预测对照

预测原文保存在`configs/artifact_mapping_repair_20261110.json`及`R/registration.json`，未在运行后修改。

- **成立**：negative——两个wait失败；code——两个历史成功投影均复现；skill——两次调用解析到原代码并成功；mapping——两视图工件ID、IR哈希、可执行哈希及原生接口保持。
- **被推翻**：无。
- **未能检验**：没有错误格式回复，真实运行未触发一次格式重试机会；边界拒绝只由单测覆盖。该重试行为不是原四条成功预测之一。
- **预测里没想到的**：独立审查发现初态副本未纳入冻结检查、调用拒绝会错误计入评价分母；均在运行后修正，保留执行快照，不改旧结果。

## 5. 证明与边界

证明了：这两个既有成功工件可以同时导出可执行code和可调用skill，并在相同已保存初态上通过同一独立评价；skill调用保留原生接口，不需要重合成控制器。

没有证明：多候选库中模型能选对工件、库比从零更好、改变杯数/hold_s后的通用参数化、新初态泛化或自主修复。此处每任务只有一个已给出完整ID的候选；原失败只作历史引用，没有同初态重跑旧重生成策略，因此不报告相对旧算法的成功率增益。T02沿用v3带人工诊断的成果（五段录制、一段新撤手），本轮没有新增leaf或正式Skill晋升。

## 6. 本轮决定与清理

用户确认“验证同一工件的技能调用与代码执行”后，使用两个预先登记的原成功初态；没有新采样、补抽、调参或重试物理。DeepSeek v4.1-flash、温度0，仅需返回ID和参数，两次均一次通过。

用户授权清理后，先备份203个文本文件，再移出14个重复入口/配置/诊断文件/报告。备份与逐文件哈希：`archive/artifact_mapping_cleanup_20261110_001.tar.gz`、同名`.json`；删除清单：`archive/artifact_mapping_cleanup_removed_20261110_001.json`。原始runs/validation删除0个，成功工件删除0个。详情见`docs/CLEANUP_20261108.md`。旧映射重生成流程不再作为主入口；保留FAST→SLOW事实反馈与网络错误停止修复。

## 7. 未决问题与证据自检

未做的后续对照只有三类：冻结多候选库测试选择；改变公共参数测试参数语义；预先冻结新初态测试泛化。本轮不以这些额外实验拖延交付。

1. 调用的是同一工件吗？看两个`skill/invocation.json`和对应`exports/<family>/manifest.json`。
2. 是否真的执行成功？看四个独立`verdict.json`，不是单测或模型自评。
3. 为什么不能说学会新控制？看`reply.txt`和历史代码SHA，模型只返回调用，控制器未变。

## 8. 新context反例审查

以下追加独立审查原文。行号指审查时源码，执行版本可在`R/source_snapshot/`追溯；两处P2修正在物理结束后，未将后改源码冒充执行版本。

结论：目前读到的 T01 证据支持“模型返回已有工件调用，运行器执行同一冻结实现，并在同一保存初态复现成功”。未发现重生成控制器或换接口。T02 本轮只审查注册与投影视图，不判断未完成结果。

按严重程度列反例与缺口：

1. **P2：接口拒绝会被计成已评价物理回合。** `selected is None` 时没有运行 skill 物理回合，但汇总仍写 `evaluated: 1`，`status` 仍可为 `complete`。这会把“调用格式未通过”混成任务失败分母；本次 T01 已实际执行，不受此缺口影响。证据：[mapping_holdout.py:167](/home/tulipe/projects/thesis-experiments/experiments/grow_up_harness_v2/calibration/mapping_holdout.py:167)、[mapping_holdout.py:174](/home/tulipe/projects/thesis-experiments/experiments/grow_up_harness_v2/calibration/mapping_holdout.py:174)。

2. **P2：运行所用初态副本没有纳入冻结检查。** 注册哈希检查的是历史 `original`，随后复制的 `samples_*/*.npz` 未加入 `dependencies`；运行前不校验副本与注册哈希。T01 的数组审计只证明“还原值等于当前副本”，没有检查其 SHA 是否等于注册值。本次只读实算两个副本 SHA 均匹配注册，因此不能据此否定本次配对，但冻结保证存在缺口。证据：[mapping_holdout.py:66](/home/tulipe/projects/thesis-experiments/experiments/grow_up_harness_v2/calibration/mapping_holdout.py:66)、[mapping_holdout.py:82](/home/tulipe/projects/thesis-experiments/experiments/grow_up_harness_v2/calibration/mapping_holdout.py:82)、[t01_episode.py:190](/home/tulipe/projects/thesis-experiments/experiments/grow_up_harness_v2/harness/t01_episode.py:190)。

3. **结论限制：只能证明给定工件的调用与复现，不能证明选择能力或修复收益。** 请求只给一个候选，并直接提供完整目标 `artifact_ref` 与参数；初态明确按历史成功选择。原失败只登记为历史引用，没有在本轮同初态执行。因此支持调用链验证，不支持“模型学会挑选”“相对旧映射提升”或未见初态迁移。证据：[request.json](/home/tulipe/projects/thesis-experiments/experiments/grow_up_harness_v2/runs/artifact_mapping_repair_20261110_001/T01/t01_110901_000/skill/proposal_01/model/request.json)、[registration.json](/home/tulipe/projects/thesis-experiments/experiments/grow_up_harness_v2/runs/artifact_mapping_repair_20261110_001/registration.json)。

4. **接口边界：参数核对不等于通用参数化执行。** `resolve` 核对参数后只返回原代码；T01 执行没有接收调用的 `object_count/hold_s`，T02 则从任务重新构造参数。当前固定的 `1/3 杯、1 秒` 可保持一致，但没有证据支持改变这些参数后的调用语义。证据：[artifact_mapping.py:25](/home/tulipe/projects/thesis-experiments/experiments/grow_up_harness_v2/harness/artifact_mapping.py:25)、[mapping_holdout.py:145](/home/tulipe/projects/thesis-experiments/experiments/grow_up_harness_v2/calibration/mapping_holdout.py:145)。

T01 的正面核查：

- 模型回复只有 `artifact_ref + params`；binding、直接执行与 skill 执行的源代码 SHA 均为 `d4e07dbd…`。证据：[reply.txt](/home/tulipe/projects/thesis-experiments/experiments/grow_up_harness_v2/runs/artifact_mapping_repair_20261110_001/T01/t01_110901_000/skill/proposal_01/model/reply.txt)、[binding.json](/home/tulipe/projects/thesis-experiments/experiments/grow_up_harness_v2/runs/artifact_mapping_repair_20261110_001/T01/t01_110901_000/skill/binding.json)。
- 两臂初态审计均匹配注册 SHA；负对照失败；两臂独立判成功，轨迹 SHA 相同。证据：[code/verdict.json](/home/tulipe/projects/thesis-experiments/experiments/grow_up_harness_v2/runs/artifact_mapping_repair_20261110_001/T01/t01_110901_000/code/verdict.json)、[skill/execution/verdict.json](/home/tulipe/projects/thesis-experiments/experiments/grow_up_harness_v2/runs/artifact_mapping_repair_20261110_001/T01/t01_110901_000/skill/execution/verdict.json)。

未修改文件、未运行测试或实验、未调用模型。未复算评价器；未审查 T02 未完成结果；未验证完整传递依赖的冻结覆盖。

本轮证据可回答的三个问题：模型生成了什么？两臂执行字节与初态是否相同？为何成功仍不足以证明选择能力或未见初态迁移？

以下为补充审查完整原文：

补充审查：**T02 也支持同工件调用配对成功；两项 P2 已在活动源码修复。**

- T02 调用仅含注册 `artifact_ref` 与 `3 杯、1 秒` 参数；两臂源代码 SHA 均为 `de4111cb…`，各执行 1284 条命令、197.05 仿真秒，独立评价均成功，三杯共同稳定约 7.8 秒。证据：[code/verdict.json](/home/tulipe/projects/thesis-experiments/experiments/grow_up_harness_v2/runs/artifact_mapping_repair_20261110_001/T02/t02_92301_001/code/verdict.json)、[skill/execution/verdict.json](/home/tulipe/projects/thesis-experiments/experiments/grow_up_harness_v2/runs/artifact_mapping_repair_20261110_001/T02/t02_92301_001/skill/execution/verdict.json)、[binding.json](/home/tulipe/projects/thesis-experiments/experiments/grow_up_harness_v2/runs/artifact_mapping_repair_20261110_001/T02/t02_92301_001/skill/binding.json)。
- 我独立读取原始数组及字节：T01、T02 的两臂初态均与注册样本一致，样本 SHA 匹配注册，两臂 `trajectory.npz` 字节相同；保存的源码快照 SHA 全部匹配清单。
- 活动源码相对执行快照的改动仅涉及：登记初态副本、每回合前核对其 SHA、调用拒绝记为 `evaluated=0/status=invocation_rejected`。未改控制器投影。两项边界测试覆盖相应行为；现有日志记录 280 项测试通过，我未重跑。证据：[post_run_hardening.json](/home/tulipe/projects/thesis-experiments/experiments/grow_up_harness_v2/runs/artifact_mapping_repair_20261110_001/post_run_hardening.json)、[测试日志](/tmp/artifact_mapping_final_unit_tests.log)。

这些是**运行后修正**，不能描述成本次实验已使用新保护；本次初态一致性由原始数据补充核实。结论仍限于两个已知成功初态上的调用与复现，不扩展到参数泛化、候选选择能力或旧映射修复收益。未修改文件、未运行物理或模型。
