# 工件库与实验入口

日期：2026-11-11。状态：已实现；验证记录见 [精简报告](../../docs/research/REPO_SIMPLIFICATION_20261111.md)。边界：MuJoCo + G1 + 双 Dex3-1 仿真。

日常只编辑 leaf 或映射算法。工件库独立于运行证据；调整目录不要求恢复旧运行的源码哈希。

```text
library/tree.yaml             任务树、工件位置、程序的组件组合
library/artifacts/*.yaml      工件契约、作用域与来源
library/artifacts/*.py        可编辑 leaf 源码
harness/artifact_mapping.py   同一工件映射为 code / 可调用 skill
harness/artifact_v2.py        复用的组合编译器及历史 Store
harness/library.py            按所选程序冻结一个包
calibration/artifacts.py      list / freeze / verify / diff
calibration/t03.py            prepare / propose / train / evaluate / execute / card / report
calibration/t03_focus.py      既有焦点预检与只读阶段报告
runs/                        旧实验原始证据，只读
../../outputs/               新运行、冻结包与导出，整目录忽略
```

## 编辑与冻结

`library/tree.yaml` 中的 `programs` 列出 6 个入口：`t01`、`t02`、`t03_base`、`t03_temporal`、`t03_route`、`t03_pose`。后四个共享 open/grasp/placement/finish；按组合选用 locate 和 approach。它们保留原工件身份，均不因此晋升正式 Skill。

在 `tree.yaml` 的 `artifacts` 找 leaf 的 YAML，再编辑其 `implementation.source` 指向的 Python 文件。移动文件时只更新这两个相对位置；逻辑名字、已有冻结包不受影响。T03 根程序由 `components` 生成，不再手写一份组件 ID 分发器。T02 的组合 `ir.use` 使用库内逻辑名。T01 保留原声明式 IR。

```bash
export G1_PYTHON=$HOME/.venvs/g1-mujoco/bin/python
export PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1
export MUJOCO_GL=egl LIBGL_ALWAYS_SOFTWARE=1
# 以下命令均从仓库根运行
"$G1_PYTHON" -B experiments/grow_up_harness_v2/calibration/artifacts.py list
mkdir -p outputs/artifacts
"$G1_PYTHON" -B experiments/grow_up_harness_v2/calibration/artifacts.py freeze t03_pose --out outputs/artifacts/t03_pose.json
"$G1_PYTHON" -B experiments/grow_up_harness_v2/calibration/artifacts.py freeze t03_route --out outputs/artifacts/t03_route.json
```

冻结时才对所选程序及其实际依赖计算内容身份，包含映射结果和声明的 runtime/evaluator 版本。每个包只有一个 JSON 文件，含所需源码、契约、组件关系和两种投影；不收集整仓源码、旧 store、谱系父版本或历史运行。包按新文件排他创建，不能覆盖。

正常加载不重算仓库、ledger 或文件哈希。日常复用已有包，修改工件或映射、需要新包时才冻结一次；额外哈希复算和 `artifacts.py verify <包>` 仅在用户明确要求审计时执行。`diff <旧包> <新包>` 查看组件、评价器和映射变化。库中 `provenance.parents` 是来源记录，不是执行依赖。

## 运行与修订

复制并填写 `configs/t03_example.json`，指定新的配置、输出路径与种子。示例未执行；所列种子不是已获验证的实验设计。开跑前核对预算、已消耗种子、基线、预测、焦点及 handoff。方法只看 [RESEARCH_METHOD.md](../../docs/research/RESEARCH_METHOD.md)。

```bash
"$G1_PYTHON" -B experiments/grow_up_harness_v2/calibration/t03.py prepare <新配置.json>
"$G1_PYTHON" -B experiments/grow_up_harness_v2/calibration/t03.py train <新运行目录>
"$G1_PYTHON" -B experiments/grow_up_harness_v2/calibration/t03.py report <新运行目录>
# 同一候选完整训练成功后，才允许生成并执行预登记留出
"$G1_PYTHON" -B experiments/grow_up_harness_v2/calibration/t03.py evaluate <新运行目录>
```

`prepare` 自动调用既有焦点门。每个运行只保存所用冻结包、配置、实际采样初态和证据，不复制整个库，也不沿旧 run 链校验源码。可选 `previous` 仅用于读阶段报告。

`train` 在同一实际初态执行负对照及 parent/code/skill；所有拒绝、失败与成功保留。code/skill 共享实现、预算和初态，并逐字节比较轨迹。skill 默认是本地显式 ID 调用，不能报成模型自主选用。完整训练成功才开启留出；原失败和工程正例在 T03 训练中不构成筛掉困难任务的理由。

需要模型修 leaf 时，用 `propose <运行目录> --role <grasp|locate|approach|placement|finish> --diagnosis <诊断.json>`。仅允许已登记焦点、显式模型配置及调用预算；一次调用保留原始回复，不自动重试。输出到该运行的 `proposals/`，静态检查通过仍只是候选。将候选应用到对应 library leaf，记录来源，再显式冻结、新登记验证；已有失败与冻结包不改。

`card` 显示已冻结调用卡；`execute --task <ID> --split <train|holdout> --arm <parent|code|skill> [--call <调用.json>]` 可做单次调用。它仍受负对照、预算和留出门约束。

## 验证与边界

代码变更跑相关检查；精简交付已跑整套测试。日常每个 run 不重复整套代码审计。旧 T01/T02 的训练、ROS 与证据复算工具继续保留，用于既有研究线；新的 T03 只用统一入口。

日常结果在聊天中简短说明，默认不新增报告文件；初态、日志、结果和 verdict 仍按运行保存。用户明确要求时才撰写正式报告。

执行器、机器人保护、独立评价器与冻结依赖库未重写。包冻结的是控制工件和声明的接口版本，不是整个仿真软件环境；runtime/evaluator 改动必须更改版本，旧结果不能称为新实现的结果。原有机器人资产与冻结初态仍须在本机可用。

旧逐轮 T03 脚本、配置、重复导出及组合绑定工具已移入 `archive/repo_ponytail_20261111_001.tar.gz`，原路径见同名 `.json`。历史 `runs/`、`validation/`、研究报告与 ADR 保留；不需要为继续实验恢复整套旧路径或旧源码。旧预注册细节见 [PROTOCOL.md](PROTOCOL.md) 中的归档说明。
