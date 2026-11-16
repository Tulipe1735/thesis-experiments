# 工件库与实验入口

日期：2026-11-11。状态：已实现；验证记录见 精简报告（已归档，见 `archive/docs_prune_20261114_001.json`）。边界：MuJoCo + G1 + 双 Dex3-1 仿真。

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
calibration/tabletop.py       T01–T04 新流程入口：prepare / kernel / report（阶段 0）/ contacts / checkpoints / trials / vlm
harness/kernel.py             内核 K_v1：既有桌面阶段分组为 locate / grasp / place 工具，记录工具边界，每阶段写检查点并可续跑
harness/reach_trial.py        评价器可达性试跑与缺口归因（方法 §2.1.1 第 1 步）
harness/vlm_locate.py         K3 VLM 定位原语（2D 部分）：本机 ollama，温度 0，按模型摘要与图像哈希缓存
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

代码变更跑相关检查；精简交付已跑整套测试。日常每个 run 不重复整套代码审计。2026-11-13 起，旧 T01/T02/VLA/F0/B1–B2 线中不再被 harness、测试或文档入口引用的 56 支复算脚本已移入 `archive/repo_cleanup_20261113_001.tar.gz`（原路径与哈希见同名 `.json`，亦可从 git 历史恢复）；仍被引用的保留。旧 T03 线只用 `t03.py`，新流程只用 `tabletop.py`。

日常结果在聊天中简短说明，默认不新增报告文件；初态、日志、结果和 verdict 仍按运行保存。用户明确要求时才撰写正式报告。

执行器、机器人保护、独立评价器与冻结依赖库未重写。包冻结的是控制工件和声明的接口版本，不是整个仿真软件环境；runtime/evaluator 改动必须更改版本，旧结果不能称为新实现的结果。原有机器人资产与冻结初态仍须在本机可用。

旧逐轮 T03 脚本、配置、重复导出及组合绑定工具已移入 `archive/repo_ponytail_20261111_001.tar.gz`，原路径见同名 `.json`。历史 `runs/`、`validation/`、研究报告与 ADR 保留；不需要为继续实验恢复整套旧路径或旧源码。旧预注册细节见 [PROTOCOL.md](PROTOCOL.md) 中的归档说明。

## T01–T04 新流程：阶段 0（内核可靠度）

定义与流程见 [GROW_UP_ROOT_DOWN_REVISE_20261113.md](../../docs/research/GROW_UP_ROOT_DOWN_REVISE_20261113.md)。阶段 0 只跑工程栏：固定工具链，无 Agent，不用测试集。

```bash
# 以下命令均从仓库根运行，环境变量同上
"$G1_PYTHON" -B experiments/grow_up_harness_v2/calibration/artifacts.py freeze t03_base --out outputs/artifacts/K_v1_t03_base_20261113.json
"$G1_PYTHON" -B experiments/grow_up_harness_v2/calibration/tabletop.py prepare experiments/grow_up_harness_v2/configs/tabletop_kernel_20261113_001.json
"$G1_PYTHON" -B experiments/grow_up_harness_v2/calibration/tabletop.py kernel outputs/tabletop_kernel_20261113_001
"$G1_PYTHON" -B experiments/grow_up_harness_v2/calibration/tabletop.py report outputs/tabletop_kernel_20261113_001
```

配置二选一：`instances` 列冻结数据集实例；`generate` 用冻结采样器和 T03 近侧网格就地生成 near 桶训练实例（种子与数量写入配置，拒绝样本保留、不补抽）。`report` 按"模板/可达桶"分组；far 桶失败归移动工具，不计入 near 桶可靠度。

`contacts <运行目录> <新输出目录>` 只读重放：把到达 grasp 的回合保存的积分状态恢复到同一场景的新 plant，用 plant 自身的监测规则列出保护停止时的违规接触（按"机器人部位->对方"归类），并给出 grasp/place 边界时目标物的逐体支撑力；不执行动作，不消耗物理预算。

`kernel` 可中断后重跑，已完成的回合不重复。每个模板先跑一次 2 秒等待负对照，被判成功则整批作废。每回合保存 `tools.json`（各工具的自报结果、边界检查、失败是否可重来）、`boundary_states.npz`（工具边界的积分状态，供后续分叉）和独立 `verdict.json`。边界检查阈值写在运行目录的 `kernel.json`，只用于测量工具，不是任务判定。

每个阶段边界（以及配置加手张开之后）在回合目录 `checkpoints/` 写一个检查点，清单见 `checkpoints.json`。检查点含 MuJoCo 积分状态、plant/port/控制器的属性和工具链自身记录，是 harness 自写的 pickle，只从本仓库输出目录加载。`K.execute(..., resume=<检查点>)` 按原流程重建配置（不推进物理）、写回检查点，从下一阶段继续；轨迹保留源回合前缀，评价器照常判整段历史。续跑结果带 `resumed_from`，与完整回合分栏报告。`checkpoints <配置>` 是 E1 验收：每个任务新跑一次源回合，再从它的每个检查点续跑，逐项比对积分/边界状态字节和各记录（见 `configs/tabletop_checkpoint_check_20261114_001.json`）。

可达性试跑（`harness/reach_trial.py`）：节点失败后，从该节点的入口检查点用 K_v1 同一阶段代码跑到所在工具结束，按工具边界检查判"可达"；不用真值，大脑不可见，不计入任何栏的成功。失败节点的执行者就是 K_v1 时，试跑只是重放，归因记为 `untestable`；其余节点按登记校准（在非参照执行者实际通过过的入口上，假"不可达"率不超过登记值、试跑数不少于登记下限）启用，未启用记 `uncalibrated`，启用后分 `node` / `upstream` / `kernel_gap`。原始与归因后 p_j 并排报告，分母不变。`trials <配置>` 是 E2 检查：先确认带检查点的重跑（`configs/tabletop_kernel_near_20261115_001.json`）与阶段 0 逐回合一致，再从重跑每个检查点做一次试跑，比对试跑与源回合的工具边界记录。

`vlm <配置>` 是 E3 的离线可行性测试（方法 §5.4 K3）：从带检查点运行的 `00_configured` 检查点取回 locate 实际读到的 320×180 头部帧（另渲染登记的大尺寸作对照，属传感器改动，只报告），用分割渲染得到目标掩码，比较 VLM 与按 `nominal_rgba` 的颜色变体基线的 2D 命中、弃权、高置信错误和耗时。判定只用内核相机尺寸；证伪即 K3 不进 K_v2。模型标识、权重摘要和 ollama 版本写入运行目录 `model.json`。
