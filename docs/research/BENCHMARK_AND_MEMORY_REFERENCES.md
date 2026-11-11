# Benchmark 与 memory / skill 参考依据

检索核对日期：2026-10-24。状态：研究参考，不是已选定的实验协议。优先依据论文、作者项目和官方文档；未在本工作区安装或运行下述 benchmark，未完整审计其代码。

Q1–Q12 更新：自主写的 IK 合法，知识驱动 Skill Synthesis 与经验驱动 Skill Improvement 分开；正式 Skill 采用同初态配对或完整修复谱系验证，跨 seed 用于可选扩展；同杯分轴冻结迁移。OCL 和跨尺度各为后续方向。活动分类用于应用层；参考方法的现成接口不能当本项目公平对照。最新归因与实施方案见[整体方案](GROW_UP_MINIMAL_EXPERIMENT.md)。

## 1. 不同来源解决不同问题

| 来源 | 已核对的组织方式 / 评测维度 | 对本项目的用途 | 不可直接等同的内容 |
|---|---|---|---|
| [RoboCasa365](https://robocasa.ai/) | 65 atomic + 300 composite；复合任务按活动组织 | L0 / L1 结构、操作任务组合、持续学习流程 | 厨房覆盖不等于办公室覆盖；其机器人接口不等于 G1 |
| [BEHAVIOR](https://behavior.stanford.edu/behavior_components/behavior_tasks.html) | BEHAVIOR-1K 的 1,000 活动；BDDL 对象、初态和目标条件 | 补齐非厨房任务，定义资产需求和谓词 | 物体 taxonomy 不是任务目的树；定义存在不等于当前可执行 |
| [LIBERO](https://github.com/Lifelong-Robot-Learning/LIBERO) | Spatial / Object / Goal / LIBERO-100；后者含 90 预训练与 10 下游任务 | 空间、对象、目标的受控迁移评测 | suites 不是生活目的 L0；新 seed 不等于新任务 |
| [LIBERO-Plus](https://sylvestf.github.io/LIBERO-plus/) | 布局、视角、机器人初态、语言、光照、背景纹理、传感噪声七轴；10,030 实例 | 鲁棒性和采样矩阵 | 10,030 实例不是 10,030 类语义任务 |
| [EmbodiedBench](https://embodiedbench.github.io/) | EB-ALFRED、EB-Habitat 偏高层；EB-Navigation、EB-Manipulation 偏低层 | 区分 LLM 调高层工具与直接低层动作 | 四环境不能混为同一种动作难度 |
| [ALFWorld](https://alfworld.github.io/) | 六任务族及 seen / unseen 划分 | 可选的低成本高层经验复用辅助实验 | 文本任务成功不证明视觉、触觉或连续物理控制 |

建议：**分类参照 RC + BEHAVIOR；本地评测设计参照 LIBERO / LIBERO-Plus；接口分层参照 EmbodiedBench。** 如果要做可与发表结果直接比较的公开 benchmark 实验，必须在其原环境和匹配协议中运行，单独报告；不能把借鉴分类后的本地 G1 分数冠以原 benchmark 名称。

BEHAVIOR 2026 Challenge 的 100-task 子集与 BEHAVIOR-1K 原始 1,000 活动区分：[Challenge](https://behavior.stanford.edu/challenge/index.html)。

## 2. RoboCasa：原生分类证据与版本边界

来源：[复合任务页](https://robocasa.ai/docs/build/html/tasks/composite_tasks.html)、[网页分类映射](https://robocasa.ai/docs/build/html/static/composite_tasks_dropdown.js)、[任务元数据](https://robocasa.ai/docs/build/html/static/task_attributes.json?v=2)、[RoboCasa365 论文 §3.3](https://arxiv.org/html/2603.04356v1)。

以下是官方网页映射显式列出的 6 个 category 和 51 个 activity 标签。把 category / activity 对应到 L0 / L1 是便于本项目阅读的说法；**51 个标签不是当前 60 个实际活动的完整且一致的规范表。**

| Category | 显式 Activity 标签 |
|---|---|
| Food Preparation（食材准备） | Washing Produce；Defrosting Food；Preparing Sandwiches；Mixing Ingredients；Seasoning Food；Making Salads；Preparing Marinades；Measuring Ingredients；Chopping Vegetables；Slicing Meat |
| Cooking（烹调） | Boiling Water；Sauteing Vegetables；Frying Foods；Steaming Vegetables；Microwaving Foods；Toasting Bread；Slow Cooking；Baking；Broiling Fish；Simmering Sauces |
| Beverage Preparation（饮品准备） | Brewing Coffee；Making Tea；Making Smoothies；Making Juice；Preparing Hot Chocolate；Mixing Drinks；Adding Ice to Beverages |
| Organizing and Storage（整理与储存） | Arranging Cabinets；Stocking Supplies；Organizing Dishes and Containers；Sorting Ingredients；Organizing Utensils；Loading Refrigerator；Storing Leftovers；Managing Freezer Space |
| Serving（餐饮服务） | Setting the Table；Plating Food；Portioning Meals；Filling Serving Dishes；Serving Beverages；Arranging Buffet；Packing Lunches；Arranging Condiments；Garnishing Dishes |
| Cleaning and Sanitizing（清洁与卫生） | Washing Dishes；Loading Dishwasher；Sanitizing Surfaces；Cleaning Appliances；Organizing Recycling；Cleaning Sink；Sanitizing Cutting Boards |

注意：当前任务元数据有一些不同拼写与新增活动，网页对未匹配名称作启发式归类。例如 `Microwaving Food` 与 `Microwaving Foods`、`Sanitizing Surface` 与 `Sanitizing Surfaces` 并不完全匹配。**本项目不复制这些兜底归类，也不把整理后的归并假称为论文原表。**

### 实际元数据中的 60 个复合活动标签

以下保留原名，不强行为每个补上未经核实的官方父类：

```text
Adding Ice to Beverages; Arranging Buffet; Arranging Cabinets;
Arranging Condiments; Baking; Boiling; Brewing; Broiling Fish;
Chopping Food; Chopping Vegetables; Cleaning Appliances; Cleaning Sink;
Clearing Table; Defrosting Food; Filling Serving Dishes; Frying;
Garnishing Dishes; Loading Dishwasher; Loading Fridge; Making Juice;
Making Salads; Making Smoothies; Making Tea; Making Toast;
Managing Freezer Space; Measuring Ingredients; Meat Preparation;
Microwaving Food; Mixing Ingredients; Mixing and Blending;
Organizing Dishes and Containers; Organizing Recycling;
Organizing Utensils; Packing Lunches; Plating Food; Portioning Meals;
Preparing Hot Chocolate; Preparing Marinade; Preparing Sandwiches;
Reheating Food; Restocking Supplies; Sanitizing Cutting Board;
Sanitizing Surface; Sauteing Vegetables; Seasoning Food;
Serving Beverages; Serving Food; Setting the Table; Simmering Sauces;
Slicing Meat; Slow Cooking; Snack Preparation; Sorting Ingredients;
Steaming Food; Steaming Vegetables; Storing Leftovers;
Tidying Cabinets and Drawers; Toasting Bread; Washing Dishes;
Washing Fruits and Vegetables
```

### 基础技能是另一条轴

当前[官网正文](https://robocasa.ai/)列出 10 项：Pick and Place；Opening and Closing Doors；Opening and Closing Drawers；Twisting Knobs；Turning Levers；Pressing Buttons；Insertion；Navigation；Sliding Racks；Closing/Opening Lids。

2026-03 论文 v1 写八项，当前原子任务网页 UI 的拆分方式也与官网正文不同。此处明确使用当前官网正文版本，不混成一个不存在的统一官方分类。

### 两个值得直接借鉴的机制

- [持续学习评测](https://robocasa.ai/docs/build/html/benchmarking/lifelong_learning.html)：125 tasks，依次为 65 atomic、20 个 2–3 阶段任务、20 个 4–5 阶段任务、20 个 6+ 阶段任务。每阶段重测之前任务，测新任务习得与旧能力保留。我们可借鉴评测逻辑，不必照搬全部规模。
- [子任务分段标注](https://robocasa.ai/docs/build/html/use_cases/subtask_annotations.html)：包含 `subtask_idx`、`subtask_name`、`subtask_stage`、`subtask_lang`，来自特权仿真状态。可参考分段和技能表达，但不能称为仅从视觉自动发现技能；官方标准 leaderboard 禁止把这些额外标签加入指定训练数据。

## 3. 其他来源的使用细节

**BEHAVIOR：**先读[概念](https://behavior.stanford.edu/getting_started/important_concepts.html)和[活动清单](https://behavior.stanford.edu/knowledgebase/tasks/)。最值得借用的是“活动 -> 角色对象 -> 初态条件 -> 目标逻辑 -> 可行场景”，不应把对象 synset 层级直接移植成任务树。未核实到一个可原样照搬的统一家庭任务 L0 / L1 树。

**LIBERO：**Spatial、Object、Goal 各 10 个任务；LIBERO-100 含 90 预训练与 10 下游 lifelong 任务。它适合提醒我们分别测试“只换摆放”“换对象”“换目标关系”“换组合”，不要用一批混杂变化的成功率代替归因。

**EmbodiedBench：**六个能力子集为 Base、Common Sense、Complex Instruction、Spatial Awareness、Visual Perception、Long Horizon。能力子集应成为诊断标签，不是生活任务主类；原始 benchmark 与后续 Challenge 版本也应区分。

**ALFWorld：**官方六类为 Pick & Place、Examine in Light、Clean & Place、Heat & Place、Cool & Place、Pick Two & Place。参考[官方任务说明](https://github.com/alfworld/alfworld/blob/master/alfworld/agents/README.md)。不要与 ALFRED 的七种模板混写；文本接口实验最多支持高层规划 / 经验复用主张。

**Habitat 3.0：**[官方页](https://aihabitat.org/habitat3/)主要讨论 Social Navigation 和 Social Rearrangement。当前没有人机协作要求，不推荐仅为“覆盖更多 benchmark”而加入；Habitat 平台家族也不是一个统一任务分类表。

## 4. Memory / skill 提取：四篇工作的职责分工

### DROC：最直接的机器人知识提取参考

[论文](https://arxiv.org/abs/2311.10678)；[全文 v2](https://arxiv.org/html/2311.10678v2)；[官方项目](https://sites.google.com/stanford.edu/droc)。

标题：Distilling and Retrieving Generalizable Knowledge for Robot Manipulation via Language Corrections。从任务、计划 / 代码、人工语言纠正和机器人响应中蒸馏知识：计划层的约束与偏好，技能层的抓取相对姿态、距离等参数、对象信息与修正代码；另更新对象当前状态。检索结合任务语义与视觉相似性。

真实 Franka 桌面实验包含技能层任务和计划层迁移，衡量完成所需人工纠正，并比较无历史、不蒸馏等条件。**可借鉴知识层级与迁移验证；不能把依赖人工纠正的方法说成完全自主失败归因，也不是 VLA 梯度训练。**

### ExpeL：从成功 / 失败经验抽取规则

[论文](https://arxiv.org/abs/2308.10144)；[全文 v3](https://arxiv.org/html/2308.10144v3)；[官方代码](https://github.com/LeapLabTHU/ExpeL)。

保存两类内容：具体成功轨迹作为示例，以及通过同任务成功 / 失败对比、多任务成功归纳得到的自然语言 insights。使用 ADD / EDIT / UPVOTE / DOWNVOTE 管理经验；不更新模型参数。实验包括 HotpotQA、ALFWorld、WebShop，并有 retrieve-only、insights-only 等消融。

**可借鉴“原始经验检索 vs 抽象规则”的对照。** 原方法检索相关成功轨迹、提供 insight 列表，不能误说它对所有 insight 都做按需检索。ALFWorld 文本结果不支持连续动作学习的主张。

### Voyager：可执行技能的生成、验证与组合

[论文](https://arxiv.org/abs/2305.16291)；[全文 v2](https://arxiv.org/html/2305.16291v2)；[官方项目](https://voyager.minedojo.org/)。

Minecraft 中的 skill 是可执行代码程序，用描述 embedding 检索，可组合旧程序。自动课程提出任务，执行后利用反馈、错误和自验证改进，确认完成后入库。验证包括探索、技术树、新世界任务及组件消融。

**可借鉴候选 -> 执行 -> 验证 -> 入库 -> 检索 -> 组合。** 机器人迁移时应增加前置条件、成功 / 失败出口、物理约束和独立验证。包装已有 `grasp()` 工具不等于学出了抓取控制器；Minecraft 接口不是 G1 连续控制。

### Dream-RSI：历史实验驱动的探索策略改进

[论文](https://arxiv.org/abs/2609.14858)；[全文 v2](https://arxiv.org/html/2609.14858v2)；[官方代码](https://github.com/zhengkid/Dream-RSI)；[项目](https://dream-rsi.com/)。v1 为 2026-09-13，已核对 v2 为 2026-10-06。

准确标题为 Dream-RSI: Recursive Self-Improvement through Evolving Worlds，**不是 Dreamer**。保留历史 discovery trees，把已记录的探索过程变成 replay worlds，优化决定分支选择、并行和停止的可编程 exploration policy；底层 discovery agent、评估器与接口固定。

Replay 只能揭示历史树已存结果，不能预测未探索机器人动作的反事实结果；改进策略仍需回到在线实验。论文 9 个任务覆盖 GPU kernel、数学优化、Lasso 算法工程、agent harness 四域，**没有机器人具身实验**。

适合本项目后续研究“下一轮练什么、在哪种失败上花预算”，不适合作为第一步的机器人 skill 提取器。论文有历史高层 insights 限制探索的具体实验，提示我们做经验有用性消融，不意味着普遍否定 memory。

## 5. 本项目可采用的经验生命周期：仍是提案

```text
真实回合记录
  -> 按阶段与失败位置整理证据
  -> 提取带适用条件、证据来源的候选经验
  -> 在独立开发实例上检验是否可复用
  -> 经验知识入库，或形成可执行 skill 候选
  -> 通过前置条件 / 结束条件 / 失败出口检验后晋升 skill
  -> 冻结版本，在未见实例上比较有无检索、参数或技能复用
```

候选 memory 应至少区分：对象 / 环境事实、身体约束与动作参数、失败与恢复经验、任务流程经验。一个成功回合不足以证明一般规则；记录适用范围、反例和证据比写得漂亮更重要。

参考工作中的 skill 需区分：现成工程工具的组合、模型生成的可执行程序、通过示范或 RL 学出的控制策略。本项目已选择第二种作为当前 skill 形态，并要求遵守关节级动作边界；不能通过程序内部调用现成 IK 或工程抓取绕过该边界。其他形式可以作明确标注的独立对照，不混称同一种自主习得能力。

主实验已选择冻结评测，不在测试回合间积累经验；Online Continual Learning 后续另设。最新对照是知识生成 / 经验改进的冻结程序版本，以及运行时显式 memory 无 / 有；保持初态、接口和预算可比，记录物理练习成本与候选选择。原始轨迹检索可作后续扩展对照，不增加首版必做组数。

可按 DROC -> ExpeL -> Voyager 的顺序明确知识和技能边界；Dream-RSI 等有足够可比的历史实验后再讨论。**这是一种建议依赖顺序，不代表用户已同意改变原研究计划。**

## 6. 任务分类与场景关联参考（2026-10-25）

日期：2026-10-25。状态：**分类提案的参考依据，未执行新增任务。** 边界：仿真任务设计；不代表实体验证或本地资产已经支持这些交互。

| 一手来源 | 来源实际怎样组织任务 | 本项目可以借鉴什么 |
|---|---|---|
| [RoboCasa365 论文 §3.3、图 3](https://arxiv.org/html/2603.04356v1#S3.SS3)；[官方复合任务页](https://robocasa.ai/docs/build/html/tasks/composite_tasks.html) | 区分原子任务与复合任务；复合任务按共享功能和语义组织为 6 个活动族、60 个活动。任务蓝图包含目标描述、对象、设施及所需技能序列。 | 用生活或工作目的组织应用任务，再以场景对象和设施落实具体实例。原子技能与应用活动分别呈现，避免在论文任务树中混入身体练习、学习流程和评测轴。 |
| [BEHAVIOR 任务定义](https://behavior.stanford.edu/behavior_components/behavior_tasks.html#task-structure)；[官方知识库说明](https://behavior.stanford.edu/behavior_components/behavior_knowledgebase.html#website-features) | 任务由对象、初态条件和目标条件定义；知识库为任务列兼容场景，为场景列房间及对象库存。 | 建立任务与场景的对应关系：同一收纳目的可用办公室文件盒或茶水间杯柜实现；是否适配取决于所需对象、功能区和交互状态。不能只按房间名字推断全部任务可执行。 |
| [ALFRED 官方生成常量 `GOALS` / `GOALS_VALID`](https://github.com/askforalfred/alfred/blob/master/gen/constants.py#L35-L49) | 代码列 7 种目标模板及其有效房间类型：普通取放覆盖四类房间；清洗后放置限厨房和浴室；加热、冷却后放置限厨房；灯下观察限客厅和卧室。 | 保留跨场景基础任务，同时让需要特定设施的任务只出现在适配场景中。通用模板与场景关联活动可以并存，不必让每个房间机械地重复完整任务清单。 |
| [LIBERO 官方仓库](https://github.com/Lifelong-Robot-Learning/LIBERO#benchmarking-knowledge-transfer-for-lifelong-robot-learning) | Spatial、Object、Goal 三个 suite 控制不同分布变化；LIBERO-100 组合多类知识变化。 | 将对象、位置和目标关系变化作为独立设计轴。更换本地资产可以形成新的任务实例，但仅换外观或名称不自动构成新的任务子类或操作能力。 |

**下面是本项目的综合设计判断，不是上述 benchmark 的统一官方分类。** 论文主树继续按任务目的组织；场景名称和代表资产放在相应子类的实例层。基础取放用于检验可复用的操作能力，讨论室的按席位材料布置、办公室的文件分类收纳、茶水间的器具准备等用于体现不同场景的用途。论文图中仅展示任务分类与任务实例，依据、状态和评测说明放在图外。

本地场景范围的证据为 `HK_IndoorBranch_R47b_20261022/legacy_physics_DH01r10/registered_scene_manifest.json` 的 `scope`：茶水间、走廊、四人讨论室、四座独立办公室；这些证据不自动证明设备物理可交互。IN20 仍是独立未合并候选，边界见 `HK_IndoorBranch_R47b_20261022/README_CN.md`。分类和场景实例的具体落点见 [T0 任务分类](T0_TASK_TAXONOMY.md)。

对香港场景的改进应落到实际资产、空间和使用关系，例如按讨论室席位布置用品、在办公文件柜内分类归档、在茶水间服务位补给器具。若要进一步主张狭小空间、拥挤摆放或本地使用习惯带来独特挑战，仍需另有本地测量、来源或实验；当前不据香港场景名称宣称这些属性，也不宣称已优于参考 benchmark。

## 7. T01–T07 的资产来源核实（2026-10-26）

日期：2026-10-26。状态：**来源检索、轻量元数据核对和一个原生 MJCF 瓶子下载已执行；新增外部资产的任务执行未验证。** 边界：MuJoCo + G1 + 双 Dex3-1 仿真，不涉及实体。

### 7.1 图片所示 SimReady：可找到具体对象，但需逐资产验收

用户图片的两个入口是 [NVIDIA SimReady Assets](https://huggingface.co/datasets/nvidia/simready-assets) 和 [SimReady Central 搜索](https://huggingface.co/spaces/nvidia/simready-central)。[官方说明](https://docs.omniverse.nvidia.com/simready/latest/simready-central.html)将其定义为带仿真元数据、目标配置与验证证据的 OpenUSD 资产；来源许可与具体版本随包保存。

固定 [SimReady Central 索引版本 `aca433cdd810b903ab0cfc34c8ac366f1d28acfb`](https://github.com/NVIDIA-Omniverse/simready-central/blob/aca433cdd810b903ab0cfc34c8ac366f1d28acfb/submissions/nvidia/simready-assets) 有 2,536 条 package URL；本次按杯、果实、瓶、盘与货架名称筛得 96 条候选。该数量属于这份索引，不与 Hugging Face 当前首页资产数混用，也不代表已接入数量。实际条目、筛选表达式和固定 URL 保存在 `experiments/t0_agent_v1/asset_source_metadata_20261026_001/simready_index_matches.json`。

以下七个代表对象均固定在 Hugging Face revision `653d91e182011f357cf1644013cc94ddf194d349`；逐个真实读取了目录、BOM、包定义和 MuJoCo 物理声明，未下载几何与完整纹理包。

| 资产标识 / 固定包入口 | 可对应任务 | 目录文件总量（十进制 MB） | 包内声明的质量（kg） |
|---|---|---:|---:|
| [`kitchenware_cup_a01`](https://huggingface.co/datasets/nvidia/simready-assets/blob/653d91e182011f357cf1644013cc94ddf194d349/kitchenware_cup_a01/com.nvidia.simready.packaging.json) | T01/T02/T04/T06/T07 的杯变体 | 11.57 | 0.14070028 |
| [`kitchenware_mug_a01`](https://huggingface.co/datasets/nvidia/simready-assets/blob/653d91e182011f357cf1644013cc94ddf194d349/kitchenware_mug_a01/com.nvidia.simready.packaging.json) | 带把杯候选 | 7.74 | 1.3335773 |
| [`kitchenware_tray_a01`](https://huggingface.co/datasets/nvidia/simready-assets/blob/653d91e182011f357cf1644013cc94ddf194d349/kitchenware_tray_a01/com.nvidia.simready.packaging.json) | T01/T02/T04 托盘；T07 可选辅助器具 | 11.39 | 0.82590896 |
| [`food_produce_apple_b01`](https://huggingface.co/datasets/nvidia/simready-assets/blob/653d91e182011f357cf1644013cc94ddf194d349/food_produce_apple_b01/com.nvidia.simready.packaging.json) | T03/T04 的刚体苹果候选 | 6.15 | 0.15984476 |
| [`food_produce_orange_a01`](https://huggingface.co/datasets/nvidia/simready-assets/blob/653d91e182011f357cf1644013cc94ddf194d349/food_produce_orange_a01/com.nvidia.simready.packaging.json) | T03/T04 的刚体橙子候选 | 6.93 | 0.28074574 |
| [`food_beverage_bottledWater_b01`](https://huggingface.co/datasets/nvidia/simready-assets/blob/653d91e182011f357cf1644013cc94ddf194d349/food_beverage_bottledWater_b01/com.nvidia.simready.packaging.json) | T05 的水瓶候选 | 7.31 | 瓶身 0.25039706；盖 0.004944255 |
| [`storage_shelf_basic_a01`](https://huggingface.co/datasets/nvidia/simready-assets/blob/653d91e182011f357cf1644013cc94ddf194d349/storage_shelf_basic_a01/com.nvidia.simready.packaging.json) | T05 的货架候选 | 158.02 | 3010.833 |

目录总量含缩略图与部分重复纹理，不是最小转换下载量；质量为来源声明，未实测校准。七个包均声明 `CC-BY-4.0`；复用时需保留来源署名、许可链接及转换修改说明，见 [CC BY 4.0 官方说明](https://creativecommons.org/licenses/by/4.0/)。这不扩大为整个搜索平台统一采用同一许可。

七者均包含 `simready_usd/payloads/MuJoCo/enabled.usda`、`instances_mujoco.usda`，不能称其没有 MuJoCo 配置；但目录中没有原生 `.xml`，本地尚未执行 USD 组合、转换、MuJoCo 编译或 G1 接触验收。代表杯还含语义标签 `plastic cup/Q3089098`、抓取参考点、惯性及摩擦声明；这些标注不是 Dex3 可抓性的实验证据。

本次物理审计发现，七者的 MuJoCo 声明均采用 `convexHull`；托盘凹槽、杯把与货架开口是否被碰撞凸包填实必须另查。带把杯的 1.33 kg、货架的约 3 吨质量也应先核对尺寸、单位和惯性，不能直接当作已校准物理参数。杯子的旧嵌入特性检查含失败项，而 2026-10-09 的 Package 报告只说明包规范两项通过；两者不互相替代，更不等于任务成功。

证据：`experiments/t0_agent_v1/asset_source_metadata_20261026_001/simready_selected_summary.json`（大小/许可/包哈希）、`simready_physics_audit.json`（质量/碰撞声明）；各资产同名子目录保存原目录 JSON、BOM 与物理 USDA，杯子目录另存原 LICENSE、Package 报告和语义声明。21 项 BOM 与物理声明的来源 SHA-256 一致性核对通过，记录为 `metadata_verification.json`，不替代物理或任务验收。首批接入判断是优先检查杯、苹果、橙子；承托容器仍使用已经能表达底板与边沿的本地几何，直到外部容器内腔单独通过验收。

### 7.2 原生 MJCF 的小型接入候选

已从 [robosuite 固定版本 `5ce6643f3092639d08f7b0f90ed1c6a84f50552c`](https://github.com/ARISE-Initiative/robosuite/tree/5ce6643f3092639d08f7b0f90ed1c6a84f50552c) 下载 `objects/bottle.xml`、`objects/meshes/bottle.stl`、`textures/glass.png` 和原仓库 LICENSE，共 **98,196 bytes**，位置为 `experiments/t0_agent_v1/assets/robosuite_bottle_v1/`。源文件未改写；本地 Git blob 哈希与远端目录公布值一致，逐文件 SHA-256、URL、大小与 MIT 许可记录于 `manifest.json`。

这是一个玻璃瓶形状的刚体代理，不是已经标注内容物的真实水瓶。原 XML 有独立视觉/碰撞 geom、密度与摩擦、底部/顶部/水平半径 site；没有自由关节，也没有 G1 碰撞位掩码或目标谓词。接入须由本地适配器增补命名前缀、自由关节、质量与接触参数、角色标签，再做编译和独立稳定性验收；任务取送与移动仍需另外验证。

[RoboCasa 对象目录](https://robocasa.ai/docs/build/html/assets/objects.html)及[固定版对象配置](https://github.com/robocasa/robocasa/blob/2ce1aecdd76e29b52d32fdb160436c5a3e230b07/robocasa/models/objects/kitchen_objects.py)还有 `cup/mug/apple/orange/tray/plate/bottled_water/water_bottle` 类别，可作为第二批原生 MJCF 候选；其[导入指南](https://github.com/robocasa/robocasa/blob/2ce1aecdd76e29b52d32fdb160436c5a3e230b07/robocasa/scripts/asset_scripts/README.md)解释了 `model.xml + visual + collision` 结构。对象大包不随代码仓库直接附齐，本次没有下载这些包，未核实单个对象文件体量；代码仓库 MIT 不能替代各第三方对象的来源许可核对。

T06/T07 可参考 RoboCasa 的[柜体模板](https://github.com/robocasa/robocasa/tree/2ce1aecdd76e29b52d32fdb160436c5a3e230b07/robocasa/models/assets/fixtures/cabinets)：`cabinet_single.xml` 为 1,632 bytes，`cabinet_hinge.xml` 为 2,397 bytes，`cabinet_panels/slab.xml` 为 586 bytes。但前两者的门 body 只有关节/参考点，门板、把手需经 `cabinets.py` 组装；独立取一个模板不能形成可接触开柜任务。未把缺少移动和柜门工具的模板计为 G1 已可执行。源 revision、模板 blob 哈希及边界保存在 `experiments/t0_agent_v1/asset_source_metadata_20261026_001/native_sources.json`。

资产检索、任务生成与实际机器人执行分开登记。任务的正式定义、随机化和有效性结果见 [T0 任务分类](T0_TASK_TAXONOMY.md) 的新增生成器章节；这里不据候选资产数量推算任务种类或机器人成功率。

## 8. Harness VLA、Embodied Turing Machines 与 code / skill 对照依据（2026-11-06）

日期：2026-11-06。状态：**文献调研 / 未复现**。边界：**仿真设计**；下文的论文结果均属作者报告，本工作区未安装这些实现、未运行实验。本节只追加来源与方法比较，不修改既有结论或实验协议。

### 8.1 用户简称的确切来源与候选边界

本次先检索本文件及工作区 Markdown 中的 `Harness VLA`、`Embodied Turing`、`Turing Machine`，未找到已登记条目；原有 §4 的 DROC / ExpeL / Voyager / Dream-RSI 仍是不同职责的参考。按名称匹配并经论文和作者页相互印证，最可能对应以下两篇；这确认了存在精确匹配论文，不代替用户对其所指版本的确认。

| 用户简称 | 精确匹配来源 | 已核对的一手入口 |
|---|---|---|
| “harness vla” | Yixian Zhang、Huanming Zhang 等，**Harness VLA: Steering Frozen VLAs into Reliable Manipulation Primitives via Memory-Guided Agents**，arXiv:2607.08448；v1 2026-07-09，当前所读 v5 2026-09-24 | [书目信息和版本](https://arxiv.org/abs/2607.08448v5)、[全文 v5](https://arxiv.org/html/2607.08448v5)、[作者项目页](https://harnessvla.github.io/)、[作者指定实现 RPent](https://github.com/RLinf/RPent) |
| “embodied turing machine” | Kairui Hu、Siyuan Hu、Fangzhou Hong、Zhaoxi Chen、Ziwei Liu，**Embodied Turing Machines: Stateful Code for Robot Recursive Self-Improvement**，arXiv:2610.12369v1，2026-10-08 | [书目信息](https://arxiv.org/abs/2610.12369v1)、[全文 v1](https://arxiv.org/html/2610.12369v1)、[作者项目页](https://etmcode-bit.github.io/)；全文简称 COAP（Code-Only-as-Policy） |

若“harness vla”只是口头描述而非论文名，还存在 **RoboHarness: A Simple Harness Outperforms VLA and World Action Models**（Bince Qu、Wei Chen、Bo Zhang，[arXiv:2610.14018v2](https://arxiv.org/abs/2610.14018v2)，摘要明确是给 coding agent 提供视觉几何控制面板、评测 BEHAVIOR Challenge 2025）的候选。它与精确题名 Harness VLA 是两篇论文，本节不把 RoboHarness 的任务、结果或实现归给 Harness VLA。ETM 的单复数简称有精确标题匹配，当前没有必须另猜一篇的证据。

### 8.2 Harness VLA：固定动作库，学习调用方式和经验

**执行接口。** planner 接收任务文本、RGB-D、末端及夹爪状态，经文件式 REPL 发出 JSON primitive 调用；worker 执行动作，保存下一步图像、状态和诊断，再交还 planner。论文明确 planner 不直接输出 torque、joint target 或 action chunk，也不读取 oracle object pose。[§2.1–2.3](https://arxiv.org/html/2607.08448v5#S2)、[附录 A](https://arxiv.org/html/2607.08448v5#A1)。

共享动作词表为 `move_to`、`move_pose`、`rotate_wrist`、`rotate_pitch`、`set_gripper`、`release` 与 `vla_act`，各环境可用项见论文表 9；RoboCasa 增加 `navigate_to`、`move_base`，RoboTwin 用 `arm` 绑定单臂或双臂。解析控制器内部可以调用 operational-space servo、Jacobian controller 或 IK planner。`vla_act(prompt, max_chunks, stop)` 将冻结 VLA 包成可提前返回、可重新布置后再试的接触动作；VLA 读实时相机与机器人状态、产生 action chunks。**这包含现成几何求解和冻结接触策略，不是从单关节动作自行学出控制器。** 来源：[§2.3](https://arxiv.org/html/2607.08448v5#S2.SS3)、[附录 B 表 9 与实现说明](https://arxiv.org/html/2607.08448v5#A2)。

**固定和变化分别在哪里。** VLA 权重与 primitive 词表在评测前固定。参考 seed 上允许 reset 和探索，改变 staging、提示词、停止条件与组合；成功 trace 形成 task-specific JSONL，配套 JSON 保存策略和失败诊断，Global Memory 保存跨任务 success rules / failure models。后续探索可以替换 trace，失败保留为负证据；变化的是经验与调用方案，论文明确不扩充 primitive 库。部署从当前图像重新绑定几何，不能复用参考坐标。来源：[§2.2](https://arxiv.org/html/2607.08448v5#S2.SS2)、[附录 A “Iterative memory construction”](https://arxiv.org/html/2607.08448v5#A1)、[附录 E.3–E.4](https://arxiv.org/html/2607.08448v5#A5.SS3)。

**“检索”不等于已经核实了向量检索器。** 论文 task memory 是与当前任务对应的 audit / trace，global memory 是上下文指导；官方实现文档提供文件工具，按任务范围读取允许的 memory，按需读取且须在当前观测下重定位。本次未发现足以把这一机制概括为 embedding nearest-neighbor skill retrieval 的证据。官方文档明确 evaluation 只读 memory、不更新，exploration 才 reset、重试和写入。来源：[论文附录 E](https://arxiv.org/html/2607.08448v5#A5)、[官方 Memory and Exploration 的开头、Evaluate with Local Memory](https://rpent.readthedocs.io/en/latest/rst_source/guides/memory.html)、[官方 RoboCasa / Task Memory](https://rpent.readthedocs.io/en/latest/rst_source/simulators/robocasa.html#task-memory)。

### 8.3 Harness VLA 的环境、预算及公开实现边界

| 项目 | 原文或官方实现实际规定 | 来源位置 |
|---|---|---|
| LIBERO / LIBERO-Pro | 桌面操作；冻结 RLinf `pi05_libero130_fullshot` π0.5-SFT；标准四 suite 共 40 个任务；Pro 为四 suite × instruction-redirection / position-swap 共八格，每格 10 tasks × 10 evaluation seeds。seed 0 仅探索，报告用 s1–s10 | [论文 §3.1、附录 C.1–C.2、D.1](https://arxiv.org/html/2607.08448v5#A3)；[官方 LIBERO / Observation and Action、VLA Configuration](https://rpent.readthedocs.io/en/latest/rst_source/simulators/libero.html) |
| RoboCasa365 | 当前官方集成为 PandaOmron 移动操作机器人、RLDX-1；planner 使用 RGB-D / world coordinates 与 base / end-effector / gripper 状态，RLDX 使用三相机历史、状态和任务文本；原文 v5 是 18 Atomic + 16 Composite-Seen + 16 Composite-Unseen，每任务 5 个评测 seed，共 250 rollouts | [论文附录 C.3、D.2](https://arxiv.org/html/2607.08448v5#A3.SS3)；[官方 RoboCasa / Overview、Observation and Action](https://rpent.readthedocs.io/en/latest/rst_source/simulators/robocasa.html) |
| RoboTwin C2R | 双臂操作、冻结经过 RoboTwin post-training 的 LingBot-VLA；一个 expert-verified clean 实例获得 trace，50 tasks × 5 expert-verified randomized seeds，共 250 rollouts；随机环境不另做 bootstrapping。当前官方实现用 SAPIEN，支持 16 值末端动作或 14 值 joint / gripper 动作 | [论文附录 C.4、D.3](https://arxiv.org/html/2607.08448v5#A3.SS4)；[官方 RoboTwin / Observation and Action、Installation](https://rpent.readthedocs.io/en/latest/rst_source/simulators/robotwin.html) |
| 论文中的预算 | §2.2 只定性写探索 wall-clock 较宽、部署 budget 缩短并禁止 reset；不能由此推算本项目的回合、秒数或训练成本已经匹配 | [§2.2](https://arxiv.org/html/2607.08448v5#S2.SS2)、[附录 E.6 / Budget, Reset, and Termination](https://arxiv.org/html/2607.08448v5#A5.SS6) |
| 当前官方复现命令的预算 | LIBERO Long 示例：100 planner turns / 5000 s timeout / 10000 episode steps；RoboTwin 示例：100 / 4800 s / 10000；RoboCasa Target50：100 turns、Atomic 1800 s、Composite 3600 s；exploration 示例是 3 sessions × 最多 5 attempts。这些是所读官方文档配置，不自动当成论文每项实验的原始预算 | [LIBERO / Experiment Reproduction](https://rpent.readthedocs.io/en/latest/rst_source/simulators/libero.html#experiment-reproduction)、[RoboTwin / Experiment Reproduction](https://rpent.readthedocs.io/en/latest/rst_source/simulators/robotwin.html#experiment-reproduction)、[RoboCasa / Experiment Reproduction](https://rpent.readthedocs.io/en/latest/rst_source/simulators/robocasa.html#experiment-reproduction-target50)、[Memory / Explore](https://rpent.readthedocs.io/en/latest/rst_source/guides/memory.html#explore-and-build-local-memory) |

**代码可获得，但须冻结对应版本。** 论文和项目均指向 Apache-2.0 的 [RLinf/RPent](https://github.com/RLinf/RPent)。本次读取主分支 commit 为 [`c41c0e6c3dc44e3347070ac1361bc2c288901873`](https://github.com/RLinf/RPent/tree/c41c0e6c3dc44e3347070ac1361bc2c288901873)（GitHub commit 时间 2026-11-05）。实际核读 [`LiberoToolkit._register_libero_tools` / exploration-only `reset`](https://github.com/RLinf/RPent/blob/c41c0e6c3dc44e3347070ac1361bc2c288901873/robots/libero/toolkit.py) 和 [`Pi05VLAClient.encode_obs` / `predict`](https://github.com/RLinf/RPent/blob/c41c0e6c3dc44e3347070ac1361bc2c288901873/rpent/robots/components/pi05_vla_client.py)：后者编码相机、state 和任务文本，经 RPC 返回 `[chunk, action_dim]`，支持的 embodiment registry 不含 G1。当前工具名是 `pi0_pick` / `pi0_doubled` 等，不能要求当前源码逐字存在论文抽象名 `vla_act`。权重与 assets 另行下载；本次只核对入口和部分源码，未下载权重或检查全套运行能力。

**三个会影响公平比较的版本问题：**（1）[当前 RoboCasa Target50 文档](https://rpent.readthedocs.io/en/latest/rst_source/simulators/robocasa.html#experiment-reproduction-target50)是 Atomic 10 seeds、Composite 5 seeds，共 340 runs，与论文 v5 的 250 不同；（2）[官方 memory provenance](https://rpent.readthedocs.io/en/latest/rst_source/guides/memory.html#release-provenance-and-compatibility)说明 merged Astra memory 尚未重评，历史 741/800 用分开的冻结快照，不能把 merged release 直接标为同一结果；（3）论文 [Flash Mode 附录 G / Max-card selection](https://arxiv.org/html/2607.08448v5#A7)明确同 seeds 选最佳卡片并报告，属于 retrospective best-card，不能当独立 held-out 成绩。直接复现需要匹配论文 / reproduction branch、模型、memory SHA、环境与预算；在 G1 上替换 embodiment / 动作接口则只能叫 **adapted Harness VLA baseline（按本项目接口改编的对照）**。

### 8.4 Embodied Turing Machines / COAP：离线改库，在线只运行有状态代码

**执行接口与库。** COAP 在测试时不调用 VLM 或 VLA；固定 task program 从 RGB 与 proprioception 维护 environment、robot、task state，计算下一 trajectory segment。状态跨当前 episode 持续，包括遮挡物体最后测量与任务阶段；这不是测试回合之间继续学习。任务程序调用共享的对象模块，再调用 grasp / pick / place / push / pour、感知和 motion；其内部含 IK、碰撞过滤、抓取检查、搬运、释放、验证。**因此 COAP 是“运行时 code-only”，同时本来就有可复用的操作模块库；不能把它解释成“无库、无经验”的 pure code。** 来源：[§3.1](https://arxiv.org/html/2610.12369v1#S3.SS1)、[§3.3](https://arxiv.org/html/2610.12369v1#S3.SS3)。

**感知输入及先验。** 只接收头部与左右腕部三路 RGB、关节角、末端位姿、夹爪命令回显和语言，无测试 depth / segmentation / model service。NumPy / OpenCV 代码用机器人 mesh 投影去除机器人像素、桌面区域、已知对象几何拟合来测位置和 yaw；camera models、robot meshes、object shapes、table height 是 benchmark 的公开常量。开发时允许用 simulator ground truth 比较测量，测试时不读 oracle。它不是不使用任何几何先验的 RGB agent。来源：[§3.1–3.2](https://arxiv.org/html/2610.12369v1#S3.SS2)、[§3.4](https://arxiv.org/html/2610.12369v1#S3.SS4)、[§4.1](https://arxiv.org/html/2610.12369v1#S4.SS1)、[§5.4](https://arxiv.org/html/2610.12369v1#S5.SS4)。

**怎样改进。** Claude Opus 5.5 coding agents 在离线 worktrees 提出 diff，先做 numeric scene stage 检查与 IK / collision 检查，再在 validation layouts 比较成功数；开发、validation selection 与 test 区分，测试时代码冻结。附录 B 记录 selection margin 为 4 episodes、重复运行噪声 1–3 episodes；作者亦明确分支增益在用于选择的 layouts 上测量，会有乐观偏差。这个过程比“存一段 memory”更接近完整共享策略代码的离线修订。来源：[§3.4](https://arxiv.org/html/2610.12369v1#S3.SS4)、[附录 B](https://arxiv.org/html/2610.12369v1#A2)。

| 比较项 | 已核实事实与限制 | 一手出处 |
|---|---|---|
| 环境 / robot / task | COAP 全部结果限仿真；RoboDojo 42 双臂任务：Memory 6、Precision 8、Open 8、Generalization 12、Long-Horizon 8。RoboDojo 原始平台是 Isaac Sim + ARX X5 双臂，双臂基座间距 0.6 m，不是 MuJoCo + G1 + Dex3 | [COAP §4 表 2、§5.4](https://arxiv.org/html/2610.12369v1#S4)；[RoboDojo §3.1、§4.1](https://arxiv.org/html/2607.04434v1#S3.SS1) |
| 评测规模 / 评价器 | COAP §4.1 写每任务 three seeds × 50 layouts，使用官方 evaluation client、judge、summary；70.24% 是作者报告的官方流程输出，不是本地复算。作者项目页标 self-evaluated | [COAP §4.1–4.2](https://arxiv.org/html/2610.12369v1#S4.SS1)；[作者项目页 / One benchmark](https://etmcode-bit.github.io/#results) |
| 执行预算 | 所读 COAP 文本未给可直接套给所有任务的统一 episode 秒数或统一离线总开发预算；RoboDojo 原文附录 D.2 用每任务示范长度第 90 百分位 × 1.2，短自动合成任务 × 1.5 定 horizon。不能拿运行时 0.3 ms median call 当成含开发和重感知的总耗时 | [RoboDojo 附录 D.2](https://arxiv.org/html/2607.04434v1#A4.SS2)；[COAP §5.4 与附录 A.1 / Decision time](https://arxiv.org/html/2610.12369v1#A1.SS1) |
| 官方实现 | 截至本次核对，论文与作者页未提供可确认的 COAP policy / shared library 源码下载链接；作者页 `Code` 导航指向站内展示，不能当实现仓库。项目账号[公开仓库列表](https://api.github.com/users/etmcode-bit/repos?per_page=100)当时仅返回[网站仓库](https://github.com/etmcode-bit/etmcode-bit.github.io)。这只说明本次未核实到入口，不断言作者从未发布在别处 | [作者项目页](https://etmcode-bit.github.io/)、[论文](https://arxiv.org/html/2610.12369v1) |

RoboDojo 本身的 [benchmark](https://github.com/RoboDojo-Benchmark/RoboDojo) 与 [XPolicyLab](https://github.com/XPolicyLab/XPolicyLab) 是其论文列出的官方代码，**benchmark 代码公开不等于 COAP 策略已公开**（[RoboDojo 论文首页及 §4.3](https://arxiv.org/html/2607.04434v1#S4.SS3)）。当前可把 COAP 作为明确的方法基线来源；若自行按论文实现，需标 **paper-based reimplementation**，若再改为本地 G1 / 关节接口则标 **adapted COAP baseline**；当前证据不支持写“直接运行官方 COAP 已复现”。

### 8.5 三组比较能回答什么，哪些名称不能直接等同

以下是**基于文献的设计判断，待另行登记，尚未执行或定稿**。两篇论文足以支撑选择有出处的强基线，但没有提供用户所要三组在本地相同观测、动作、训练和测试预算下的因果比较。特别是本项目 §5 已把 skill 选为模型生成的可执行程序，code 与 skill 在表示上有重叠，必须用“允许哪些操作”定义组别。

| 用户要检验的组 | 可审计的候选定义 | 文献支撑与能回答的问题 |
|---|---|---|
| code + skill | 同一个运行时 planner 可生成新程序，也可调用冻结、已验证、版本固定的 skill；新代码和 skill 均走相同低层接口 | Harness VLA 支持把固定 primitives 与运行时 planner / memory 组合的强参照，但其固定工程 primitives + 冻结 VLA 不等于本项目自主生成 skill；因此需标 adapted，而非照搬命名。对比另两组可以测本地混合策略的相对收益 |
| pure code | 同一个 planner 从本轮允许的身体 / 环境资料与观测生成代码，不读取本项目习得的 skill / memory 库；共同 runtime、底层驱动和合法数学工具须一致 | 这是去掉“习得库访问”的本地消融。COAP 则是另一个更强的参照：离线演化共享代码、在线冻结；直接把 COAP 归到这个“无习得库”的消融会误归因（[COAP §3.3–3.4](https://arxiv.org/html/2610.12369v1#S3.SS3)） |
| pure skills | 同一个 planner 只能选择并绑定同一冻结 skill 库；不许生成新控制逻辑、修改 skill 或用任意代码补救。若允许序列 / 条件组合，须明确许可语法、重试与失败出口 | 能检验收益是否来自运行时新代码、以及库覆盖不足时的处理；不能直接把 end-to-end VLA 称为这组，因为单个冻结 VLA 与显式有限 skill 库的动作空间不同 |

对 Harness VLA 更忠实的补充比较是：**同冻结 VLA 直接执行 vs 同 VLA + 解析 primitives + agent / memory**（[§3.1](https://arxiv.org/html/2607.08448v5#S3.SS1)）；对 COAP 更忠实的是：**开发后冻结的有状态共享程序 vs 在线 agent**（[§3](https://arxiv.org/html/2610.12369v1#S3)）。这些可以是外部方法参照；用户三组应作为同一 harness 的能力限制对照，不能只选三篇论文的公开分数拼成三组结果。若要进一步宣称 code 与 skill 存在统计交互 / 协同，单凭三组优劣仍不足以完整识别，需要另行明确因素设计和零因素条件；本节不增加实验组。

**直接相关的补充来源是 Skill2Real，而不是“pure skills”已现成存在的证据。** [Skill2Real: Agentic Skill Learning for Zero-Shot Sim-to-Real Robot Manipulation，arXiv:2610.02788v1 §3.1–3.4](https://arxiv.org/html/2610.02788v1#S3)明确 Proposer 每个 decision stage 条件于冻结 Cerebellum / Brain memory **生成可执行程序**；训练用 PVG 验证入库，部署只保留 Proposer + 公共 API + 冻结 memory。因此它本身更接近 code + learned skill 的相关工作，不是禁止新代码的 pure-skills。论文 [§4.4、§5.2 表 1](https://arxiv.org/html/2610.02788v1#S4.SS4)有 no learned skills / Cerebellum-only / Brain-only / full 的控制，能借鉴“固定 Proposer 和 API，只改变知识库”的归因；[作者页](https://skill2real.github.io/#skills)公开 skill 示例与 task program，但本次未完整审计训练实现，不能据示例宣称可直接复现。

2026-11-06 的公开资产补充核对见 [SKILL2REAL_REUSE_20261106.md](SKILL2REAL_REUSE_20261106.md)：58 个 task program 均标为 `adapted_task_program`、`reexecuted:false`，126 条 skill 是文本记忆而非可调用函数；站点未公开训练/PVG 代码或许可证。可迁移的是技能文本结构、分阶段契约和准入检查，不是其运行时代码或成功率。

### 8.6 对本项目贡献的支持范围与未决项

**可支持的研究问题：** 在同一 MuJoCo + G1 + 双 Dex3-1、相同允许观测与低层动作边界下，经过实际练习与验证的冻结 skill 库，能否比无习得库的新代码和仅用冻结 skills 的执行获得更好的任务完成、恢复行为或成本；并把固定工具的调用经验与实际新增 / 改进可执行能力分开。Harness VLA 已研究“固定库 + 经验”，COAP 已研究“共享代码库 + 离线改进”，Skill2Real 已研究“验证后的程序技能 + 层级组合”，因此仅声称“代码和 skill 结合”“写 memory”“库会增长”不足以由这批文献推导出新颖性。本地三组若实际配对执行、控制成本并保留失败，才会成为本项目的证据；本节不预言哪组会赢。支撑来源分别为 [Harness VLA §2](https://arxiv.org/html/2607.08448v5#S2)、[COAP §3](https://arxiv.org/html/2610.12369v1#S3)、[Skill2Real §3](https://arxiv.org/html/2610.02788v1#S3)。

尚未解决的三项：① 用户所指是否就是上述精确匹配的版本，以及 pure skills 是否允许条件 / 循环 / 重试；② 官方 COAP 完整实现入口和总离线开发预算；③ 本地公平适配的共同感知先验、合法 solver / VLA 权限与开发成本。Harness VLA 和 COAP 均使用现成 IK / 几何 / 操作模块；若本项目主实验坚持自主关节级合成，它们要么作为单列的强工程 / 外部方法对照，要么统一适配到底层接口并明确方法改动，不能偷偷让某组多获得 IK、oracle 或预训练接触能力。

本轮自主决定仅限文献检索：以精确标题匹配为主、RoboHarness 保留为名称歧义候选；正文方法固定读 Harness VLA v5 / COAP v1；实现固定核读 RPent 上述 commit；Skill2Real 仅作已核实的相关工作补充。不选择实验阈值、容差、初态、seed、跳过项或重试，不修改 PROTOCOL、实现及既有 runs。

交接核对题（答案均在本节一手来源中）：（1）Harness VLA 在增长什么，哪些库与权重保持固定？（2）为什么 COAP 不能直接当“没有可复用库的 pure code”？（3）为什么在 G1 跑改编版、或用 Flash Mode 的同 seed 最优卡，不能写成原方法已独立复现？
