# AGENTS.md

本仓库存放香港单房间 T0 具身任务研究的代码与证据。平台为 MuJoCo + G1 + 双 Dex3-1，所有结论仅限仿真。论文仓库 `~/projects/thesis` 有独立规则。

## 默认工作流

- 导航只读 [docs/INDEX.md](docs/INDEX.md)。做实验之前读 [RESEARCH_METHOD.md](docs/research/RESEARCH_METHOD.md)；T01–T04 及之后的新流程按 [GROW_UP_ROOT_DOWN_REVISE_20261113.md](docs/research/GROW_UP_ROOT_DOWN_REVISE_20261113.md) 执行，不要把所有历史报告、协议和运行快照重新装进上下文。
- 日常只改 `experiments/grow_up_harness_v2/library/` 的 leaf/组合关系与 `library/policies/`（积累算法 A、投影算法 R），或 harness 中的内核工具封装、投影与积累实现。入口说明只维护现有 [README.md](experiments/grow_up_harness_v2/README.md)。
- 工件入口为 `calibration/artifacts.py list|freeze|verify|diff`；新流程（T01–T04 起）只用 `calibration/tabletop.py`；旧 T03 线的已有运行与复算沿用 `calibration/t03.py`。不再按轮次、新阶段或版本新增实验脚本。
- 修改后显式冻结所选程序的依赖闭包，生成一个包。内容身份只在冻结/显式审计时计算；正常运行不扫描整仓、不复制整库、不登记全目录源码哈希，不要求当前源码恢复成旧运行版本。
- 工件名、组件关系与物理路径分开。移动 library 文件只更新树中的相对位置；谱系父版本仅是来源，不自动变成执行依赖。
- 新运行和导出统一进根目录 `outputs/`，整体忽略。旧 `runs/`、`validation/` 与冻结数据集只读；不为精简代码而改写成功、失败或旧初态。
- 检查规模跟随改动：先相关检查，有跨模块风险再跑整套；同一代码版本复用已有检查证据，不每次 run 重算整套审计。
- 日常复用已有工件包和检查结果。只有工件或映射改变、需要新包时才冻结一次；额外哈希复算和 `verify` 仅在用户明确要求审计时执行。

## 实验与归因

- 新实验使用新配置、新输出目录，排他创建。保留实际采样对象、位姿、朝向和参数；只存 seed 不够。已消耗 seed 写入运行配置，不补抽到成功，不按测试结果挑检查点。
- 开跑前登记基线、预算、预测、证伪条件。负对照成功整批作废。T03 的正例失败、持续训练和留出门遵循方法 §10；不能把困难任务从训练分母里筛掉。
- 新流程以能力缺口记录代替焦点卡；本条及下两条只适用于旧 T03 线。`focuses` 每项包含 `stage` 与可观测 `mechanism_trigger`，阶段与顺序以 `harness/t03_handoff.py` 的 `STAGES` 为准，默认上限 3。`handoff` 覆盖到最深焦点的所有关卡。默认路径跑通不算触发。
- 没登记的阶段本轮不改；上游阻塞既不给下游记功也不记过。开跑前用 `t03_focus.py precheck`，统一入口自动调用；结束用 `report` 分焦点报触发次数及触发后的完整成功次数。
- 某阶段连续两轮零触发、触发后失败已转移下游，或 code/skill 连续两轮同成功率时，应换/加焦点，不继续堆同一工件。
- 工程参照成功与 Agent 成功分栏。后者必须注明人工诊断、真值、录制段比例等辅助。本地显式 skill ID 调用不能写成模型自主选用；静态、接口、primitive 检查不能写成完整任务成功。
- 结论引用原始 JSON、日志或录像。每项验证写清证明什么、没证明什么。保持失败记录，变更后的结果分开报告。
- 改变研究方向的结论定稿前，按方法 §8 交给新 context 的 subagent 找反例；普通代码精简不启动这项研究审查。

## 代码与执行

- 唯一 harness 是 `experiments/grow_up_harness_v2/`，不新建 `_v3`。工件版本由内容身份区分；正式冻结包不可覆盖。
- `experiments/t0_agent_v1/`、`cordis_t01/`、`grow_up_v2/isolation/` 和 `grasp_optimization/*.py` 是历史冻结依赖，不修改；必要适配写在 harness。新流程不将这些库的所有文件绑成每轮前置门。
- 不改已安装第三方源码。新依赖须固定版本并登记到 `grasp_optimization/reports/dependencies.json`。不加未证实原因的 try/except、兜底值或重试。
- 从仓库根运行脚本，路径相对根目录，Python 用 `$G1_PYTHON`；设置 `PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1`。渲染加 `MUJOCO_GL=egl LIBGL_ALWAYS_SOFTWARE=1`。

```bash
export G1_PYTHON=$HOME/.venvs/g1-mujoco/bin/python
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 MUJOCO_GL=egl LIBGL_ALWAYS_SOFTWARE=1 \
  "$G1_PYTHON" -B -m unittest discover \
  -s experiments/grow_up_harness_v2/tests -t experiments/grow_up_harness_v2
```

## 由检查强制的规则

下列规则已由代码强制，提示词里不必再重复，也不必再手动 `find -newer`。纠正同类错误时先在此表加检查，再考虑加文字。

| 规则 | 强制方式 |
|---|---|
| 生成种子不复用；有意复现须声明 | `tabletop.prepare`：与 `configs/` 已登记种子重叠即拒绝，除非 `replicates` 列出被复现运行且 `generate` 完全相同 |
| prepare 后内核接口不改 | `tabletop.kernel` 开跑前比对 `kernel.json`，不同即 `KERNEL_CHANGED_AFTER_PREPARE`（只覆盖登记的接口与叶子哈希，不覆盖源码树） |
| 运行不写冻结库与被读运行 | `tabletop.kernel` 结束时检查 `experiments/t0_agent_v1`，`contacts` 检查原运行，有新写入即作废或报错 |
| 回合之间中断可续跑；回合开始后中断则整批作废，不重跑该回合 | `tabletop.kernel` 开头：已作废即停；有 `physical_started` 无 `physical_completed` 即记 `INTERRUPTED` 作废。形式化检查见 `.claude/skills/verify-run-lifecycle` |
| 已完成运行只读；整批作废不报成功率 | `tabletop.report` 只在批次结束后写 `report.json`，不覆盖不同内容的已有文件；有 `batch_invalid` 只打印作废原因 |
| 不按轮次新增脚本、不建第二个 harness | `tests/test_repo_rules.py` 的 calibration 白名单与 harness 名检查 |
| 历史冻结依赖不修改 | `tests/test_repo_rules.py` 与基线提交比对（忽略 WSL 权限位） |

## 文档与清理

- 日常结果在聊天中简短说明，默认不新增报告文件。用户明确要求报告时，才放到 `docs/research/<TOPIC>_<yyyymmdd>.md`，按方法 §7 组织。中文为主，新术语先入 `GLOSSARY.md`。不为同一件事再造 README/STATUS/PROGRESS/SUMMARY/NOTES。
- 删除/移动文档同步 `docs/INDEX.md`。`grasp_optimization/README_CN.md` 和 `reports/THESIS_UPDATE_20261024_FINAL.md` 为已发布口径，只追加，不改旧数字。E2/E3 为工程阶段（旧报告和代码中写作 P2/P3），勿与任务模板或投影阶梯 P0–P3 混用。
- 目录清理先备份并记录原路径；不得无授权删除研究结果、ADR、术语表或 validation。用户本次已授权 repo/流程精简，原文备份与清单见 `archive/repo_ponytail_20261111_001.*`；2026-11-13 旧线无引用脚本的备份见 `archive/repo_cleanup_20261113_001.*`；2026-11-14 术语表精简与旧文档（旧设计、旧线结果报告）的备份见 `archive/glossary_prune_20261114_001.*`、`archive/docs_prune_20261114_001.*`；这不授权后续丢弃新旧失败证据。
- 不提交凭据。`.mjb`、`.npz`、权重、检查点与导出不入源码库。

## 协作

- 用用户的语言，结论先行。范围含糊先明确目标、边界与完成判据，再填常规可逆选择；不重复询问已有授权。
- 收尾简短说明结果、实际验证和必要的阻塞/边界；有交付物再给位置。无需固定数量的边界条目、验收问题或额外总结文档。同一修正两轮仍不到位时停下来，建议重写需求。
