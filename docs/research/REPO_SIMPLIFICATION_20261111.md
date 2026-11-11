# 工件库、实验入口与旧测试精简

日期：2026-11-11。状态：已执行。边界：仓库与流程整理；没有新增机器人训练或留出回合，没有新增任务成功结论。

## 1. 结论

日常开发收敛到可编辑 library、共用映射算法、显式冻结和统一 T03 入口。新运行只带所选程序的小包与自身证据，不复制整库、不扫描整仓源码哈希、不依赖旧运行的源码路径。

12 个逐轮 T03 入口由一个 `calibration/t03.py` 接替；工件操作集中到 `calibration/artifacts.py`。共 36 个旧入口、配置、重复导出和已废弃模块/测试文件已完整备份后移出活动目录。另按用户追加授权删除冗余测试方法：总计撤下 31 项旧测试，新增当前库/运行边界的 15 项测试，最终 325 项全部通过。没有通过删除失败测试来使检查通过：整理前 341 项在正确的 EGL 环境下已全部通过。

## 2. 结果与证据

| 检查 | 结果 | 原始证据 |
|---|---|---|
| T01/T02 与四种 T03 程序导入 | 6 个程序原工件 ref 与可执行代码一致；T03 组件绑定一致 | `experiments/grow_up_harness_v2/tests/test_library.py::test_imported_programs_keep_original_artifact_refs_and_code`；`outputs/repo_ponytail_20261111_001/tests.log` |
| 移动 library 及 leaf YAML/Python 文件 | 更新位置索引后整个冻结包及身份一致 | 同测试文件 `test_moving_library_and_leaf_files_preserves_release_identity` |
| 修改单个 leaf | 只改变对应组件及根程序身份，其余组件不变 | 同测试文件 `test_leaf_edit_changes_only_that_component_and_root` |
| 不再读旧 store 或扫描哈希 | 加载冻结包时禁用旧 Store 和 SHA256 仍能工作 | 同测试文件 `test_bundle_load_needs_no_library_store_or_hash_scan`；`outputs/repo_ponytail_20261111_001/verification.json` |
| 显式审计、排他创建 | 6 个包审计通过；破坏包内容会失败；已有包拒绝覆盖 | `outputs/repo_ponytail_20261111_001/verification.json`；相关单测 |
| T03 根程序隔离分发 | 四种根程序在实际 Worker 中返回原组件 ID；四种统一入口的原生执行器/源码参数另有分发测试 | `outputs/repo_ponytail_20261111_001/verification.json`；`test_program_versions_dispatch_exact_frozen_components_to_their_native_executor` |
| 焦点门与训练成功门 | 示例预检通过；无完整同候选训练成功不得生成留出；不允许改登记范围外组件 | `outputs/repo_ponytail_20261111_001/precheck.log`；相关单测 |
| 运行产物与源码区分 | outputs、archive、runs、validation、旧运行环境、凭据均被忽略；library 和机器人源码资产保留可跟踪 | `outputs/repo_ponytail_20261111_001/verification.json` 中 `ignore_checks` |
| 整套检查 | 整理前 341/341，整理后 325/325 | `outputs/repo_ponytail_20261111_001/baseline_tests.log`、`tests.log` |

新工作入口与命令只维护在 [harness README](../../experiments/grow_up_harness_v2/README.md)；[library 树](../../experiments/grow_up_harness_v2/library/tree.yaml) 是可编辑工件的位置与组合入口。

## 3. 成本

没有外部模型调用，没有新训练/留出回合，没有录像重渲染。工程验证包含整套单测、6 个工件包的编译/显式审计、4 种 T03 根程序的真实隔离 Worker 调用、CLI 与 ignore 规则检查。单测里的 mock 成功输出、静态/接口检查不计为任务成功。

新测试和独立包检查的计数在 `outputs/repo_ponytail_20261111_001/verification.json`；单测耗时只作为日志记录，没有作性能对比或加速主张。

## 4. 验收对照

本轮是工程整理，没有预注册新的科研预测。用户要求是减少只为记录/校验而增加的耦合，并允许删无用旧测试。验收项已在上表落实：只改 leaf/映射即可出新包；移动文件不改变控制身份；运行不沿旧 run 检查源码；当前行为检查继续通过。

没有把“包能加载”“Worker 返回组件”或“检查通过”写成机器人任务成功。

## 5. 证明了什么、没证明什么

**已证明的工程行为：** 当前库中的六个程序可保持原可执行代码与身份导出；库/leaf 可移动；单个 leaf 修订不牵连无关组件；冻结包可离开库独立加载；同一入口根据声明接口调用既有原生执行器；负对照、预算、阶段范围和留出门仍是入口约束。

**尚未验证：** 没有用新统一入口执行完整的 G1 训练或留出任务，因此不能声称其完整物理轨迹已与旧入口复现一致。四种执行器的分发检查使用真实根 Worker，但以测试替身代替完整物理回合。

包只冻结控制工件、映射结果和声明的 runtime/evaluator 版本，未冻结整个软件环境，不能仅凭版本标签证明运行代码逐字一致。普通调用仍做所选源码字符串的绑定检查，不再遍历磁盘上的全仓文件。

没有验证无历史数据的全新 clone 能运行整套历史测试；既有机器人资产、初态与历史复算测试仍需本机数据。旧 T01/T02/ROS 复现工具保留历史方式；新默认流程以 library 与统一 T03 入口为准。工件的文字 pre/post 没有因此获得自动语义衔接证明，也没有晋升任何正式 Skill。

## 6. 自主决定与归档

- 沿用现有 artifact.v1/v2 模型、组合编译器、Worker、原生执行器、机器人保护与独立评价器；不新增框架或第三方依赖。
- 导入 `t01`、`t02`、`t03_base`、`t03_temporal`、`t03_route`、`t03_pose`。来源父版本只作谱系记录，不拖入整个历史库。导入内容保持候选身份；已有正式 ROS Skill 的登记不改。
- library 中保存可读名称的 YAML/Python；T03 的组件 ID 根程序由树生成。冻结包保存执行闭包，路径不参与位置身份；旧 T01 初态路径保留为来源元数据，新冻结不会为生成代码读取或重新校验它们。
- T03 模型提议集中为一个有预算的 `propose`，保留原始回复与拒绝，不自动重试，不改已冻结包。静态通过仍只是候选；新源码应用到 library 后需另行冻结、登记和验证。
- 新产物进根 `outputs/`；备份进 `archive/`。旧 `runs/`、`validation/` 及全部失败/成功证据均保留，因此本轮没有释放旧证据占用的磁盘空间。
- 备份为 `archive/repo_ponytail_20261111_001.tar.gz`，共 230 个整理前文件，含被移出的完整原文；原路径、删除清单与测试删除理由在同名 `.json`。删除前逐个确认归档内容与原文件一致。旧 PROTOCOL 与重复技能导出也在包内，未改写旧数字。
- 删除 18 项旧组合绑定层测试、9 项早期 T02 minimal_stub 迁移自检，以及 4 项表格复写/自我比较/源码格式/固定链列表断言。当前组合执行、拒绝边界、初态配对、映射绑定与独立评价器行为测试保留。编译测试还移除了内部变量名断言，保留实际动作序列断言。
- 新报告排除负对照的焦点计数；对新统一入口记录的 `decision_stages`，将真实发生在 preflight 的避障选择归到 preflight。历史原始 JSON 与其旧标签没有追改。
- `AGENTS.md`、方法 §5 和入口说明去除重复流程要求；旧协议改成历史索引，数字仍指原始证据与归档原文。

## 7. 未决与验收问题

1. **移动文件是否要恢复旧 run 的源码哈希？** 不需要。移动 library/leaf 的身份一致测试及冻结包独立加载测试可回答；旧物理资产的装载仍遵循其原生接口。
2. **删了哪些测试，剩下的通过了吗？** 精确清单与理由在归档 `.json`，31 项旧测试退出活动套件，最终 `tests.log` 为 325/325；新增加的 15 项针对当前库与入口行为。
3. **本轮是否证明新的机器人任务成功，或减少了旧证据磁盘占用？** 都没有。原始工程检查 JSON 明记新任务回合与删除旧运行证据均为 0；下一次真正实验仍须新登记，并在同一保存初态验证原生入口的完整行为。
