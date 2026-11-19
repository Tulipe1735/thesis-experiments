---
name: verify-run-lifecycle
description: TLA+ check of the tabletop run lifecycle after prepare (negative controls, engineering rows, interruption and rerun, batch_invalid, physical budget, report.json). Use before and after changing tabletop.py kernel/negative/start_physical/report or the first line of harness/kernel.py execute, or to answer whether a run can be resumed, voided or reported.
---

# 运行生命周期的形式化检查

`calibration/tabletop.py` 的一次运行在 prepare 之后，由 `events.jsonl` 和磁盘上的回合目录记录状态。进程可以在任意两步之间中断，操作者随后重跑 `kernel` 或单独跑 `report`。测试只覆盖写到的几种顺序；这里用 TLC 走遍小规模下的所有顺序。

## 检查的规则

规则写在 `model/RunLifecycle.tla` 末尾，每条一句话：

| 规则 | 含义 | 被打破的危害 |
|---|---|---|
| `WithinBudget` | `physical_started` 不超过 `caps.physical_episodes` | 超预算运行 |
| `NoPhysicsAfterVoid` | 出现 `batch_invalid` 后不再开始物理回合 | 作废批次继续消耗预算、产生看似有效的回合 |
| `NegativeControlFirst` | 某模板的工程回合只在其负对照通过后开始 | 负对照失效的批次被当作有效测量 |
| `NoEpisodeStartedTwice` | 同一 (task, arm) 最多开始一次；中断的回合不重跑 | 补跑到成功，或预算被重复扣 |
| `RerunNeverStuck` | 重跑 `kernel` 不会因回合目录已存在而失败 | 运行被永久卡住，只能弃用整个目录 |
| `FinishedBatchIsClean` | 正常跑完的批次里，开始过的回合都已完成 | 中断的回合被悄悄跳过，分母失真 |
| `FinalReportAlwaysWritten` | 跑完的批次总能写出 `report.json` | 最终报告停留在中途内容 |
| `FinishedReportCoversAllRows` | 跑完时报告覆盖每一行 | 报告漏行 |

中断口径（用户 2026-11-15 选定）：两个回合之间中断，重跑接着跑；回合开始后（已记 `physical_started`）未完成就中断，重跑时记 `batch_invalid: INTERRUPTED`，整批作废，不重跑该回合。

## 覆盖的代码与同步点

模型每个动作对应一步代码（注释在 `.tla` 中）：

- `calibration/tabletop.py`：`kernel`、`negative`、`start_physical`、`report`；
- `harness/kernel.py`：`execute` 的第一行 `out.mkdir(parents=True, exist_ok=False)`；Agent 臂经 `agent_episode`，它先以同一个 `execute` 建回合目录，重试分支 `branches/NN` 都在这一个回合之内。回合内部的物理、工具链与分支只抽象为"跑完 / 中断 / 结果"。

同步点（2026-11-19 零 token 变体筛查，两文件含未提交改动，故用内容哈希；2026-11-18 变体轮为 `67bc2945…` / `87bd2aab…`，同日重试轮为 `f0bdf8e6…` / `cd28b18a…`，2026-11-17 为 `1bf2ae0a…` / `68ed94f5…`，2026-11-15 首版为 `84a36be3…` / `babb05c5…`）：

```
0b30f9646a6ffe8abd6e6954c96c70ddbcaa75053dd3fffa316a73eeac351ea2  experiments/grow_up_harness_v2/calibration/tabletop.py
fab3186839fc03ef41b6b13e58fda0d6e96d75e9df2a5f78fb83ee5f235afc73  experiments/grow_up_harness_v2/harness/kernel.py
```

`sha256sum` 与此不同时，先读这两处函数的改动，判断模型是否仍描述代码；确认后才更新同步点。

## 范围与假设

- 行循环按 (行, 臂) 走，臂固定为 engineering、agent 两个（`arms` 的双臂配置；单臂运行是它的子情形）；行循环前有一步大脑会话开启，可能失败。
- `check.cfg`：3 行、2 个模板（A, A, B）、双臂、预算 9，足够跑完（2 个负对照 + 6 个回合）；`budget.cfg`：同样 3 行、预算 3，预算会卡住（`WithinBudget` 只在这里真正受检）；`chart.cfg`：1 行、预算 3，只用于画图。规则检查须跑 `check.cfg` 与 `budget.cfg` 两份。
- 所有行 ready；同一时刻只有一个 `kernel` 进程；中断只发生在步骤之间。
- 不建模：prepare 本身、墙钟预算（与物理预算同路径）、`check_kernel_unchanged`、冻结目录写入检查、`checkpoints`/`trials`/`contacts`/`sweep` 命令、回合内的 checkpoint 与续跑。

## 运行

1. 在仓库外的临时目录复制 `model/` 下全部文件。
2. 用 pstack 的 `/statechart` skill 检查：规则用 `RunLifecycle.tla` + `check.cfg`，再用 `budget.cfg` 跑一次；图用 `chart.cfg` + `view.mjs`。命令与选项以该 skill 当前版本为准。首次运行它会用 mise 装 TLC 1.7.4 与 Java；下载慢时，按该 skill 支持的 `TLA2TOOLS`、`JAVA` 环境变量指向已有的 jar 与 Java 11+。
3. 读结果：按 `/statechart` 的说明读 report 里每条被打破规则的最短路径。

## 区分真 bug 与模型错误

每条被打破的规则都要在真实代码上逐步重放。`replay.py` 已覆盖现有反例；从 `experiments/grow_up_harness_v2` 运行：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B ../../.claude/skills/verify-run-lifecycle/replay.py
```

它只把 MuJoCo、plant 和单回合物理换成替身，`kernel`、`negative`、`start_physical`、`report` 与 `execute` 的建目录行都是真代码。重放不出来，先假定模型错了，对照代码改模型，不改规则。

## 改代码时

1. 改动碰到上面列出的函数，就先按新代码改模型（一步代码一个动作），再跑检查，不要按"能通过"去改。
2. 有意改变承诺（例如中断回合改为作废），先改规则并写明依据。
3. 改模型后，把代码按规则所防的方式改坏一次（如删掉行循环的 `batch_invalid` 检查），确认对应规则会被打破，再撤掉。
4. 报告：每条规则是否成立、新的反例路径与重放结果、仍未覆盖的部分。

## 历史与当前结果

2026-11-19 零 token 变体筛查（新命令 `sweep`，不写 `events.jsonl`、不走 kernel/report，同配置重跑时跳过已完成回合；`execute` 的大脑定位多读 `case['vlm_sources']` 缓存）：生命周期动作未变，模型不改；未建模命令里加上 `sweep`。

2026-11-18 变体轮（`agent_episode` 加变体分支：带变体重新开一个回合，仍在同一个 (行, 臂) 回合内；report 加变体计数）：生命周期动作未变，模型不改；`replay.py` 五条路径照旧。

2026-11-18（Agent 臂重试分支 `agent_episode`，`brain_session` 加 Magpie）：
- 生命周期动作未变：每个 (行, 臂) 仍是一次 `start_physical`、一次 `physical_completed`；分支中途中断照旧记 `INTERRUPTED` 作废整批。模型不改，未重跑 TLC。
- `replay.py` 替身加 `agent_episode`（与真实代码一样先调 `execute`），五条路径结果与 2026-11-17 相同。

2026-11-17（`arms` 双臂与 `brain_session`，A_static 配置）：
- 模型改为 (行, 臂) 循环并加 `SessionOpens` / `SessionFails`，`check.cfg` 预算 6→9；8 条规则在 `check.cfg`（853 个不同状态）与 `budget.cfg`（162）下全部成立。TLC 1.7.4，Java 为 jammy-updates openjdk-17-jre-headless 17.0.21 经 `apt-get download` + `dpkg -x` 解到 scratchpad（/etc 下的配置链接改指解包目录），不装系统。
- `replay.py` 的替身跟上代码（`verifier` 多 `hand_rule`、`execute` 多 `brain`、任务目录有 `task.json`），新增两条双臂路径：行 a 的 Agent 回合中断 → `INTERRUPTED` → `BATCH_INVALID`；行 b 两臂之间中断 → 重跑 ok，最终报告两臂各 2 行。原有三条路径结果不变。
- 改坏验证：手动 report 只等工程臂 → `FinalReportAlwaysWritten`；已完成判定只按行（不分臂）→ `FinishedReportCoversAllRows`；跳过负对照直接进行循环 → `NegativeControlFirst`。

2026-11-15：

- 首版模型在当时代码上打破 `RerunResumes`（重跑不卡住）与 `BudgetPaysOnlyForPhysics`，并在真实代码重放：工程回合中途中断后重跑因回合目录已存在抛 `FileExistsError`，且每次重跑先记一次 `physical_started`（1 个回合记了 3 次）；负对照先建目录后检查预算，`NEGATIVE_WAIT_REJECTED` 后同样卡住。
- 用户选定中断口径（见"检查的规则"）后，代码改为：`kernel` 开头遇已作废即停、遇已开始未完成的回合即记 `INTERRUPTED` 作废；负对照先 `start_physical` 再建目录；等待被拒记 `batch_invalid`。规则相应改为上表 8 条，`check.cfg` 与 `budget.cfg` 下全部成立，`replay.py` 三条路径与预期一致。
- 同日还修复了第 1 步引入的 `report` 回归（中途手动 `report` 后最终报告写不进）：`report` 只在批次结束后写文件。
- 改坏验证（每条规则都见过失败）：删中断检查 → `NoEpisodeStartedTwice`、`RerunNeverStuck`；删开头作废检查 → `NoPhysicsAfterVoid`、`FinalReportAlwaysWritten`；跳过负对照 → `NegativeControlFirst`；旧 `report` → `FinalReportAlwaysWritten`；预算判断差一（`budget.cfg`）→ `WithinBudget`；把已开始当作已完成跳过 → `FinishedBatchIsClean`；行循环少一行 → `FinishedReportCoversAllRows`。
- 未建模的风险：同一目录同时跑两个 `kernel` 进程（如后台启动未确认就再开一个）会被当成中断而作废整批。
