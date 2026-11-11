# 文档索引

本页是唯一的导航入口。`AGENTS.md` 管规则，这里只回答"该读哪一份"。最后更新：2026-11-11。

## 先读

| 想知道什么 | 文件 |
|---|---|
| 怎样设计、执行和报告一轮实验 | [research/RESEARCH_METHOD.md](research/RESEARCH_METHOD.md) |
| 下一轮该把回合花在哪（注意力预算、焦点卡） | [research/RESEARCH_METHOD.md](research/RESEARCH_METHOD.md) §11；`../AGENTS.md` §2 |
| 研究要证明什么、晋升规则 | [research/GROW_UP_MINIMAL_EXPERIMENT.md](research/GROW_UP_MINIMAL_EXPERIMENT.md) §1–13 |
| 已确认的决定与当前执行约束 | [research/ALIGNMENT_AND_SEQUENCE.md](research/ALIGNMENT_AND_SEQUENCE.md) §9；[adr/](adr/) |
| 日常改 leaf / 映射、冻结与统一运行入口 | [harness 入口](../experiments/grow_up_harness_v2/README.md)、[精简及验证](research/REPO_SIMPLIFICATION_20261111.md) |
| 术语 | `../GLOSSARY.md` |

## 当前结果（全部为仿真）


| 结果 | 报告 | 原始证据 |
|---|---|---|
| T03 避障接近leaf已实调；生成训练父版/姿态版均1/4，冻结同分布新实例三臂均1/4，code/skill4对一致；无新增完整T03修复 | [research/T03_SCALE_20261111.md](research/T03_SCALE_20261111.md) | `../experiments/grow_up_harness_v2/runs/t03_obstacle_pose_eval_20261111_001/`（开发在obstacle_pose_20261111_001，primitive成功不等于任务成功） |
| T03 持续训练累计解决1/6已试任务；冻结位置留出code/skill各1/4，4对调用及轨迹一致；未晋升正式Skill | [research/T03_ARTIFACT_CYCLE_20261110.md](research/T03_ARTIFACT_CYCLE_20261110.md) | `../experiments/grow_up_harness_v2/runs/t03_frozen_eval_20261111_001/`（全部前序失败保留） |
| 同一artifact的code执行/skill调用验证（T01、T02两臂均成功，四段录像） | [research/ARTIFACT_MAPPING_HOLDOUT_20261109.md](research/ARTIFACT_MAPPING_HOLDOUT_20261109.md) | `../experiments/grow_up_harness_v2/runs/artifact_mapping_repair_20261110_001/` |
| T02 三杯归集：v2 工程参照 3/3、Agent 0；v3 Agent 1 例（带人工诊断） | [research/T02_GROW_V2_20261107.md](research/T02_GROW_V2_20261107.md) | `../experiments/grow_up_harness_v2/runs/grow_t02_v2_20261107_001/summary.json`、`grow_t02_v3_20261107_001/summary.json` |
| T02 抖动阶梯 5 / 10 mm | 同上，"抖动阶梯"一节 | `../experiments/grow_up_harness_v2/runs/t02_ladder_5mm_20261107_001/results.json`、`t02_ladder_10mm_20261107_001/results.json` |
| T01 artifact v5–v9 投影执行（开发初态，未晋升） | [research/ARTIFACT_ACCUMULATION_AND_EVALUATION_20261106.md](research/ARTIFACT_ACCUMULATION_AND_EVALUATION_20261106.md) | `../experiments/grow_up_harness_v2/runs/t01_artifact_series_20261106_001/summary.json`、`t01_artifact_provenance_audit_20261106_001/audit.json` |
| T01 ROS 正式 Skill v1.1（配对加冻结新初态） | [research/GROW_UP_MINIMAL_EXPERIMENT.md](research/GROW_UP_MINIMAL_EXPERIMENT.md) §15 | `../experiments/t0_agent_v1/skill_registry/T01_ros_cup_to_tray_v1_1.json`；登记包在 `../experiments/ros_skill_cycle/validated/T01_ros_cup_to_tray_v1_1/`；审计在 `../experiments/ros_skill_cycle/audits/`；7 段视频在 `../experiments/ros_skill_cycle/exports/story_20261029_001/` |
| harness v2 前置门：F0 v2 3/4、评价器复算 16/16、可达上限 | 旧协议原文见 `PROTOCOL.md` 的归档位置；数字以右侧 JSON 为准 | `../experiments/grow_up_harness_v2/runs/f0v2_engineering_20261103_001/results.json`、`audit_recompute_20261103_001/results.json`、`reach_envelope_20261103_002/envelope.json` |
| 抓杯工程 v2 跨位置 7/8；SmolVLA 冻结 0/4 | `../grasp_optimization/README_CN.md`（已发布口径） | `../grasp_optimization/validation/` |

## 背景与参考

| 内容 | 文件 |
|---|---|
| 任务分类 L0/L1 | [research/T0_TASK_TAXONOMY.md](research/T0_TASK_TAXONOMY.md)、`.markmap.md` |
| 身体能力主树 | [research/BODY_TO_TASK_TREE.md](research/BODY_TO_TASK_TREE.md) |
| 观测边界与公平对照 | [research/OBSERVATION_AND_EXPERIMENT_PROTOCOL.md](research/OBSERVATION_AND_EXPERIMENT_PROTOCOL.md) |
| benchmark 参考 | [research/BENCHMARK_AND_MEMORY_REFERENCES.md](research/BENCHMARK_AND_MEMORY_REFERENCES.md) |
| grow loop、局部积累、Skill2Real 复用 | [research/GROW_LOOP_20261106.md](research/GROW_LOOP_20261106.md)、[LOCAL_ARTIFACT_CYCLE_20261106.md](research/LOCAL_ARTIFACT_CYCLE_20261106.md)、[SKILL2REAL_REUSE_20261106.md](research/SKILL2REAL_REUSE_20261106.md) |
| T02 curriculum 设计（未执行）与闭环修复 | [research/T02_ARTIFACT_V2_CURRICULUM.md](research/T02_ARTIFACT_V2_CURRICULUM.md)、[T02_EXPERIMENT_20261107.md](research/T02_EXPERIMENT_20261107.md) |
| 室内场景交接 | `../HK_IndoorBranch_R47b_20261022/README_CN.md` |
| 目录精简记录（含备份位置） | [CLEANUP_20261108.md](CLEANUP_20261108.md)；更早的记录 `CLEANUP_20261025.md` 已被取代 |

2026-11-08 之前写的研究文档里，有部分证据路径已随精简删除，详见 `CLEANUP_20261108.md`。

## 目录

```text
AGENTS.md  GLOSSARY.md
docs/                         INDEX、research/、adr/
outputs/                      新冻结包、运行与导出（整目录忽略）
archive/                      精简前原文备份与清单（整目录忽略）
experiments/
  grow_up_harness_v2/         唯一 harness：library/、映射、统一入口、tests/；旧 runs/ 只读
  ros_skill_cycle/            T01 ROS Action Skill：入口、审计、登记包、代表视频
  t01_revision/               T01 有界修订与 ROS 2 / ros2_control 运行环境
  t0_agent_v1/                冻结的 plant / 谓词 / 评价器 / 数据集划分 / skill_registry（依赖库，只读）
  cordis_t01/                 T01 Worker 与变化初态（依赖库，只读）
  grow_up_v2/isolation/       seccomp Worker 入口（依赖库，只读）
grasp_optimization/           底层控制、规划、视觉模块；冻结初态与验收结果
HK_IndoorBranch_R47b_20261022/  室内场景资产
```
