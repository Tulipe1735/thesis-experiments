# T02 实验闭环修复与对照资格

日期：2026-11-07。状态：历史复算与入口修复已执行；物理对照执行中。边界：MuJoCo 仿真。

用户指定转向 T02；T01 仅保留课程顶层组合验收，本轮未执行 T01 或修改其配方。T02 是三杯归集，槽位放置是其局部效果，两者分别验收，不把局部成功当作整项成功。

## 证据与本轮优化对象

历史完整 T02 的工程成功见 `experiments/t0_agent_v1/tray_20261025_repair_003/episodes/2401_T02_scripted/independent_verification.json`；原失败 2400 是两杯后视觉无可用杯，2402 是接近跟踪失败。Astra 调度成功见 `experiments/t0_agent_v1/tray_astra_20261025_001/episodes/2501_T02_astra/independent_verification.json`。这些不能归因于 agent 自主低层合成。

较新的 T02 槽位入口存在更早的实验闭环错误：`pilot.execute` 对失败 guarded waypoint 返回列表，旧入口忽略其中状态并继续释放；`--slot` 仅用于报告，执行仍绑定 slot_0；CLI 原先按单杯托盘成功而不是槽位成功返回 0。初态与局部稳定性也未完整约束槽位成功。

逐帧历史复算脚本 `experiments/grow_up_harness_v2/calibration/t02_slot_audit.py`，原始输出 `experiments/grow_up_harness_v2/runs/t02_slot_audit_20261107_001/results.json`：9 条局部回合，稳定入指定槽位 0/9；两条托盘局部成功仍未到指定槽位。符合事前“托盘成功不等于入槽”的预测；登记输入哈希均未变。原回合没有完整命令返回日志，因此“哪个失败回复后继续释放”尚不能仅据旧日志逐命令复原，不将源码缺陷直接当成某条轨迹全部偏差的唯一原因。

## 已修复的入口

`calibration/t02_execution.py` 绑定 IR 中实际槽位引用并重新生成执行代码，不改 artifact.v1 YAML、编译器或冻结生成文件。`calibration/t02_slot_check.py` 将绑定源码写进新输出，记录其哈希；motion 返回非成功立即中止所有后续 phase，wait 则按其实际 guard 接口判定。异常和拒绝传入独立验收，CLI 只按 slot_success 返回。

稳定入槽要求：托盘物理谓词、杯倾斜不超过 5°、指定槽位距离不超过 15 mm、末段保持至少 1 s，采样间隔超过 0.051 s 中断保持；局部资格还要求初态合法、无外力、无 equality constraint、无执行错误、无保护。完整三杯仍由原 tray_verify.py 独立判定，不修改官方判据。新增 `--saved-initial` 可复用历史保存初态；结果 seed 改为读取实际 instance，不再把生成任务误写为默认 2400。

cup_body 目前只是独立评价器对象身份，不能用它伪称视觉策略已绑定该身份；非默认 --cup 会拒绝。托盘 yaw 的槽位变换及多杯视觉身份绑定尚未实现。这些限制不通过隐式真值注入解决。

## 物理对照登记

入口 `calibration/t02_replay_controls.py`，仅运行 T02 已消耗开发初态 2401，原 instance 完整写入登记。两回合固定顺序：同初态等待负例、原工程动作重放正例。预算每回合 180 s 仿真，0 模型请求、0 重试；无 fallback；正例不合格不进入 Agent 练习。使用本地 integer-ticks-v1 记录器；模型、保存初态、历史请求与评价器均哈希登记。

`runs/t02_replay_controls_20261107_001/` 是首版 motor replay：错误地用 physics_events 的 advanced_seconds 替代请求 duration；0.133333… s 请求会推进约 0.134 s，不能等价重放 smoothstep。此尝试保留，不据其偏差否定历史工程成功。修正版本在 `runs/t02_replay_controls_20261107_002/`，用三个 cup_attempt/actions.json 的 186 个请求与 motor events 按结束时刻一一对齐，恢复原请求 duration。事前预测为负例失败、正例三杯成功，且末态与历史原始数组完全相同；相反结果会停止资格流程并保留失败。

本轮自主决定：先修实验闭环而非同时调接近、抓持、搬运参数；只用已消耗开发初态，不新增泛化主张；完整成功仍需三杯，单杯槽位是局部；正负对照前不启动模型练习；修正后结果与旧入口分列。新 context 反例审查发现并推动修复 CLI、初态门禁和重放 duration 三项问题，代码回归位于 `tests/test_t02_execution.py`。
