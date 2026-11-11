# 四视角原生 LeRobot 数据集接口调研与导出说明

核查日期：2026-10-24。范围：已安装原生 API、宇树官方相机说明、独立导出器；未改动既有控制器、场景、worker、测试或冻结文件。当前交付不等待采集，也不运行下载、上传、训练或机器人控制。

## 1. 结论与证据范围

本机 `lerobot==0.4.4` 的数据格式版本为 **`v3.0`**，支持 `LeRobotDataset.create → add_frame → save_episode → finalize`。应调用本机接口生成原生 Parquet/MP4 数据集，不能照抄 ToastedBread 卡片中的旧 `v2.0` 文件布局。[L1][L2]

官方 ToastedBread 数据集为 30 Hz、640×480、28 维双臂及 Dex3 关节状态/动作，四路图像对应头部左右双目、左右腕部单目。**本次核查的官方数据集卡、配套元数据和 AVP 硬件说明未发布该数据集逐相机的精确外参**，不能把项目自行设置的相机位姿称为训练数据的标定复现。[D1][D2][D3]

交付的 `export_fourview_demos.py` 只接受新采集、独立验证成功的工程示范；四路视频及 28 维绝对弧度状态/目标直接写入原生特征。训练与离线验证保留明确 episode 索引，归一化统计仅聚合训练示范。离线验证来自已知练习位置，**不是独立或 held-out 任务成功率 benchmark**。[E1]

## 2. 官方相机布置：哪些已知，哪些未知

| 原始特征键 | 可由官方资料支持的视角 | 原生图像形状 |
|---|---|---|
| `observation.images.cam_left_high` | 头部左目 | CHW `[3,480,640]` |
| `observation.images.cam_right_high` | 头部右目 | CHW `[3,480,640]` |
| `observation.images.cam_left_wrist` | 左腕单目 | CHW `[3,480,640]` |
| `observation.images.cam_right_wrist` | 右腕单目 | CHW `[3,480,640]` |

来源：官方数据集卡的 Camera Positions 与四路 `features`；键名的 left/right 与头部/腕部说明共同确定上述对应关系。[D1]

1. 卡片将 Camera View 指向 `unitreerobotics/avp_teleoperate` 第 5 节，并要求硬件安装后参考数据集首帧调整场景；卡片也明确采集跨多次会话、各条数据存在差异。卡片中约 45° 指的是面包机/托盘相对机器人摆放，**不是相机旋转外参**。[D1]
2. 该官方链接目前重定向到 `unitreerobotics/xr_teleoperate`；README 第 5 节继续指向 `Device.md`。这次还核查了官方历史提交 `7cd188c1657ad4df97cfcd44e9f35bac937f7f2b` 中的硬件文档，供可追溯引用；该提交不代表原数据集采集时版本。[D2][D3]
3. `Device.md` 给出参考头部双目规格：30 FPS / 125° FOV / 60 mm 基线，并列出后续 60 FPS 选项；腕部参考器材包括左右各一台单目相机，也另列 D405 选项。说明本身将器材参数标为参考。不能因此断定 ToastedBread 所有会话均使用其中某一个具体型号，不能把 D405 深度加入这个 RGB 特征契约。[D3]
4. 官方提供头部支架、腕环/相机支架的图示与 CAD，并要求腕环与腕关节接缝对齐；这些是安装依据。已核查文档没有为这 418 个 episode 提供四路 `T_robot_camera` / `T_wrist_camera` 的数值旋转和平移、逐会话标定结果或与这些 RGB 流对应的完整内参/畸变表。支架尺寸、FOV 与双目基线不足以恢复四相机相对机器人坐标系的完整变换。[D1][D3]

工程实现可据此建立“头部双目 + 双腕”的视角覆盖，但其仿真外参应以项目自身记录为准，并标明与官方采集的精确几何关系未知。[D1][D3]

## 3. 本机原生 API 的精确行为

使用的解释器：

```text
/mnt/c/Users/23660/Documents/Codex/2026-10-23/files-mentioned-by-the-user-hk/work/vla-env/bin/python
```

实际导入检查读得 `lerobot 0.4.4`、`torch 2.7.1+cu126`、`torchvision 0.22.1+cu126`、`av 15.1.0`；未安装 `torchcodec`。已安装 torchvision 提供 `VideoReader`，PyAV 能解析 `h264` 编码器为 `libx264`，也具备 `libsvtav1`。这里只确认导入与编码器可用性；真实采集视频的解码需由导出后的原生回读检查确认。[L1][L3；本次本机只读探测]

| 接口/约束 | 已安装实现中的行为 | 导出器处理 |
|---|---|---|
| `create(repo_id,fps,features,root,...)` | `root` 必须尚不存在；本机支持 `video_backend`、`vcodec`、`streaming_encoding` | 在 `/tmp` 新建暂存数据集，使用 `local/g1-cup-fourview-engineered-v1` |
| 数值特征 | float32；形状用 tuple `(28,)`；名称是一维关节名列表 | 两个数值特征共用原生关节顺序，无排列或语义转换 |
| 视频特征 | `dtype="video"`；CHW 声明 `(3,480,640)`；输入可为 uint8 HWC | 原始 RGB memmap `[capacity,480,640,3]`，仅读取前 T 帧 |
| `add_frame(frame)` | 要求 `task`；会修改 frame；自动写入 `frame_index` 与 `frame_index/fps` | 每帧构造新 dict，不额外传入 timestamp 或物理时钟 |
| 显式 timestamp | 本机 `validate_frame` 将默认 bookkeeping 字段排除在调用方输入外，直接传 timestamp 会被判为多余特征 | NPZ 的名义时钟先校验，原生库重建同一 `i/30`；两个时钟另存审计文件 |
| `save_episode(parallel_encoding=False)` | 原生计算图像/数值统计、保存 episode 与视频；每次把 info 的 splits 重设为全 train | 最后一次保存后再固定真正的 split 范围 |
| `finalize()` | 关闭数据和 episode 元数据的 Parquet writer，写完 footer | 始终调用；不以对象析构代替 |
| 解码 | 原生支持 CPU torchcodec 和 torchvision 的 pyav/video_reader；torchcodec 缺失时默认回退 pyav | 显式使用已安装 `pyav`，不安装新依赖 |

来源：已安装 `lerobot_dataset.py` 的 `create`、`add_frame`、`save_episode`、`finalize`、`__getitem__`；`utils.py` 的 `validate_frame` / 特征转换；`video_utils.py` 的解码分发。[L1][L2][L3]

本机 streaming encoder 在队列满时可能丢帧并给出 warning。因此导出器使用原生非 streaming 路径，在 `/tmp` 写临时 PNG，再以原生 `vcodec="h264"` 编码；4 个图像写入线程、每个编码器 2 线程、相机顺序编码。H.264 是本机原生 API 支持的存储编码，不声称与官方卡片 AV1 的压缩结果相同。输出检查还核对每个 MP4 的帧数、帧率和分辨率。[L1][L3][E1]

图像统计由原生 `compute_episode_stats` 从其采样帧/降采样图像计算，范围归一化到 `[0,1]`、形状 `[3,1,1]`；不应描述为逐像素遍历全部原始帧。状态/动作统计同样由库生成。导出器从库保存的逐 episode 统计调用原生 `aggregate_stats` 聚合训练部分，再用原生 `write_stats` 写 `meta/stats.json`，保留全体统计和离线验证统计作审计。[L4][L1][E1]

## 4. 采集接口与额外约束

沿用请求指定的 `capture_manifest.json` 接口：`fps=30`、一个 canonical `task`、28 个原生关节名及逐列 workspace 映射、四个原始 camera key，以及包含 `seed/capture_dir/split/verified_success` 的 episode 列表。每个 capture 目录必须包含 `samples.npz`、`capture.json` 和 `independent_verification.json`。[E1]

本轮采集器计划提供 6 条原生 30 Hz 抓取/抬升片段：train seeds 为 `[1000,1100,1102,1207]`，offline-validation seeds 为 `[1002,1200]`。这些全是已知练习位置。任务文本直接采用 manifest 中原始 `vla_handoff.SUBGOAL` 的值；导出器不导入既有控制器，也不替换 instruction。上述是本轮实现约定的采集接口，实际是否已采集仍以 manifest 和独立验证文件为准。[E1]

调用方需保持以下细节：[E1]

- **RGB** uint8 HWC，不是 OpenCV BGR。每路必须是独立 raw 文件，声明的 capacity 可大于 T，文件不得小于声明容量；仅前 T 帧参与导出。RGB 的颜色含义需要由采集器保证，单凭数组 dtype 无法推断。
- `samples.npz`：`state/action` 为有限浮点 `[T,28]`，列已经按 native 顺序排列；表示绝对关节位置/目标，单位弧度。导出仅转换存储 dtype 为 float32，不加当前 q，不做角度单位转换、符号翻转、重排或归一化。
- 标签时序严格为：`state[t]` 是物理步前在 t 测得的状态；`action[t]` 是当时已经选好、供**紧接着的 2 ms 控制步**使用的绝对 PD 目标，再按 30 Hz 采样。它不是下一帧实测 q，也不是 delta。库的动作窗口从 offset 0 开始，导出不移动标签一帧。[E1]
- 来源 teacher 在 **500 Hz** 运行，这些是其绝对目标的原生 30 Hz 样本。采样间的有限差分命令**不保证全部符合更严格的 VLA 命令幅度/速率上限**；本次 `validated=true` 仅认证数据 schema、值保真、时钟、存储/解码与统计，不认证 VLA runtime guard 的约束合规性。运行时保护继续适用，导出不裁剪或重写标签以掩盖差异。[E1]
- 左手原生列为 Thumb0/1/2、Middle0/1、Index0/1；**右手原生列为 Thumb0/1/2、Index0/1、Middle0/1**。不能把 workspace 的右手分组顺序直接当作 native 列序。原始顺序来自官方卡片及已保存的官方元数据。[D1][E1]
- `timestamp[T]` 是从 0 开始的名义 `i/30`。`simulation_time[T]` 是实际仿真时间，推荐 float64：落在 2 ms 网格上，相邻采样相隔 16 或 17 个物理步，相对名义时钟偏差不超过一个物理步。两个时钟严格递增。程序拒绝原始 20 Hz 时钟，不进行旧轨迹插值。
- 每个 episode 至少 2 帧；至少一条 episode 达到 50 帧，以实际验证未 padding 的 50 步动作窗口。短 episode 的尾部仍按原生规则 padding，并在检查中核对 `action_is_pad`。
- manifest 的 `verified_success` 必须为 JSON `true`；**同目录独立验证报告顶层的 `verified_success` 也必须为 JSON `true`**。缺少文件、false 或字符串 `"true"` 都拒绝。`capture.json.provenance` 必须为 `engineered_visual_tactile_teacher`，task/fps 必须与 manifest 一致；若 capture/验证报告带 seed，也须一致。
- 至少有一条 train 示范，才能得到 training-only normalization；validation 可暂时为空，但其实际索引会如实记录。同一 seed 不得跨 train/validation；capture_dir 不得重复。

本轮 raw memmap 容量为 `[600,480,640,3]`，每路由独立相机实际渲染；导出仍仅用 `sample_count=T`，不会将未写入的容量补成示范帧。本轮相机实现将腕部 near clip 为 8 mm，仅作用于渲染，原始头部相机不变；本导出器完全不改相机/场景。这套 rig 是工程近似，不具备官方原数据集精确外参复现的证据。[E1][D1][D3]

## 5. 输出内容、划分与使用

模型特征恰好为 4 路 video、`observation.state` 和 `action`；另有原生 `timestamp/frame_index/episode_index/index/task_index` bookkeeping，语言 task 写入原生任务表。杯子真值、深度、物理时间、成功标签、验证报告均不会成为模型特征。[L1][L2][E1]

原生保存 episode 时仍按 manifest 中各 split 的相对顺序，整体将 train 排在 validation 前，以便在 `meta/info.json` 表达连续范围。例如两条 train 加一条 validation 时，范围为 `train="0:2"`、`validation="2:3"`。每条新 episode 的原 manifest 下标都会保留；来源 seed/目录和训练/验证索引记录于 `meta/engineering_export.json`。[E1]

**后续训练必须显式把 `split_episode_indices["train"]` 传给 `LeRobotDataset(..., episodes=...)` 或对应训练配置的 `dataset.episodes`。本机构造器的 `episodes=None` 会读取所有 episode，不会因 info 中写有 validation 就自动排除它。** 本交付不启动训练。[L1][E1]

输出主要包括：[L1][E1]

- `data/chunk-*/file-*.parquet`、`videos/<camera_key>/chunk-*/file-*.mp4`，以及原生 `meta/info.json`、`meta/tasks.parquet`、`meta/episodes/...`。
- `meta/stats.json`：仅训练部分的库生成统计；`meta/stats_all_episodes.json`：库原始全体聚合统计；如存在 validation，另有 `meta/stats_offline_validation.json`。
- `meta/capture_manifest.json` 与 `meta/engineering_export.json`：canonical task、native/workspace 名称、split 索引、来源/数组摘要、API 版本及源码 hash、工程数据性质说明。
- `meta/capture_audit/episode_XXXXXX/`：原始 capture 与独立验证 JSON 的副本、`timing.npz` 两个时钟。原始大体积 memmap 不复制，未来 `--check-only` 不依赖 `/tmp` 原始图像文件。
- 数据集根目录 **`conversion_report.json`**：集成用顶层字段 `total_episodes`、`fps`、`camera_keys`、`validated`（JSON bool），另有逐项检查、解码样本、视频 header 检查及验证范围说明。只有全部本地检查通过才写 `validated=true`。`meta/export_validation.json` 保存相同详细报告；完成 `finalize()` 并通过暂存数据集原生回读后，才复制到指定的新输出目录。输出目录已存在即拒绝，不支持覆盖或追加。

这些归一化统计保存在新数据集目录中，**不覆盖 checkpoint 自带的统计**，也不修改任何 checkpoint 文件或权重；本轮只做 SFT 数据准备，没有权重更新、训练或 push。[E1]

通过原生 CPU `LeRobotDataset` 回读时使用：

```python
delta_timestamps = {"action": [i / 30 for i in range(50)]}
```

检查少量 item 的每路视觉为 float32 `[3,480,640]`、CPU、`[0,1]`，状态为 `[28]`，动作窗口为 `[50,28]`；同时核对实际值、episode 边界 padding 和至少一个无 padding 窗口。全量数值行按源 float32 数组 hash 校验，逐 episode 物理时钟单独核验，视频仅对少量 item 解码，并用 MP4 header 核对全部文件的帧数/尺寸/帧率。[L1][L3][E1]

运行导出：

```bash
/mnt/c/Users/23660/Documents/Codex/2026-10-23/files-mentioned-by-the-user-hk/work/vla-env/bin/python -B \
  /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/export_fourview_demos.py \
  --manifest /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/demonstrations/cup_fourview_v1/capture_manifest.json \
  --output /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/datasets/cup_fourview_v1
```

只检查已有数据集（不修改输出，可省略 manifest，不需要原始 capture/memmap）：

```bash
/mnt/c/Users/23660/Documents/Codex/2026-10-23/files-mentioned-by-the-user-hk/work/vla-env/bin/python -B \
  /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/export_fourview_demos.py \
  --output /mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/datasets/cup_fourview_v1 \
  --check-only
```

导出及检查会强制 Hugging Face offline 与禁用 telemetry，数据读取缓存放在本次 `/tmp` 临时目录；缺少本地文件时不能从 Hub 补下载。退出码 0 表示实际检查通过，2 表示输入或运行检查失败。[E1]

## 6. 本次验证记录与尚未完成的实测

- 已完成已安装版本、原生方法签名、数据格式版本、PyAV / torchvision 导入及 CPU 编码器存在性核查。[L1][L3；本机只读探测]
- 语法编译通过；有效 manifest、62 帧 30 Hz / 2 ms 双时钟样例通过；11 类纯 schema 拒绝检查通过：20 Hz 声明、native 列序、workspace 映射、缺相机、未验证成功、seed 跨 split、状态维度错误、非有限动作、20 Hz 名义时钟、20 Hz 物理间隔、非 2 ms 网格物理时钟。该有效时钟样例的最大相对偏差为 1.333333 ms，物理间隔为 16/17 步。全部在内存测试，未新增测试文件。[E1；本次执行记录]
- 28 列 native 顺序与项目保存的官方 metadata 一致；调用已安装原生 `validate_frame` 与 `get_hf_features_from_features`，导出器的四视频 + state/action schema 通过；另确认向原生 frame 显式添加 timestamp 确实会被拒绝。[D1][L2；本次执行记录]
- CLI help 正常；向已经存在的输出目录运行导出时，在导入重型原生运行库前以退出码 2 拒绝覆盖。已只读核对现有 `collect_fourview_demos.py` 的 NPZ/manifest/capture 字段及 `tests/test_fourview_dataset.py` 对根目录 conversion report 的接口要求，未修改它们。[E1；本次执行记录]
- 尚未获得本次 collector 的真实 capture；因此本次没有产出 cup 数据集，也没有宣称四路真实视频解码、独立任务表现或训练已经验证。实际导出时这些本地数据检查会自动执行；无需等待采集来完成本导出器交付。[E1]

## 7. 一手来源与本机证据定位

- **[D1]** [宇树官方 ToastedBread 数据集卡，固定 revision 02cb291](https://huggingface.co/datasets/unitreerobotics/G1_Dex3_ToastedBread_Dataset/blob/02cb29161f5adb2981a072aa35b408d82a556d07/README.md)。已核对项目保存的 [README.md](/mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/assets/vla_checkpoint_metadata/kiteml_g1_smolvla/source_dataset/README.md)；其 SHA-256 为 `fec1c167f576413cc2969c410371fecf3d09876247ff679fc83377300b2602ee`。关节/相机结构还可查同目录 [meta/info.json](/mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/assets/vla_checkpoint_metadata/kiteml_g1_smolvla/source_dataset/meta/info.json)。
- **[D2]** [卡片所附官方 AVP teleoperate 链接](https://github.com/unitreerobotics/avp_teleoperate)，当前重定向 [xr_teleoperate README](https://github.com/unitreerobotics/xr_teleoperate#5-%EF%B8%8F-hardware) 第 5 节。
- **[D3]** [官方 Device.md，固定提交 7cd188c](https://github.com/unitreerobotics/xr_teleoperate/blob/7cd188c1657ad4df97cfcd44e9f35bac937f7f2b/Device.md)，§5.2 采集器材、§5.3 安装图示；另核对 [当前官方 Device.md](https://github.com/unitreerobotics/xr_teleoperate/blob/main/Device.md)。这些是硬件参考，不是原数据集逐会话标定。
- **[L1]** [LeRobot 官方 v0.4.4 dataset 源码](https://github.com/huggingface/lerobot/blob/v0.4.4/src/lerobot/datasets/lerobot_dataset.py)。实际运行事实以本机安装文件 [lerobot_dataset.py](/mnt/c/Users/23660/Documents/Codex/2026-10-23/files-mentioned-by-the-user-hk/work/vla-env/lib/python3.12/site-packages/lerobot/datasets/lerobot_dataset.py) 为准：`CODEBASE_VERSION` 第 83 行、metadata 的 splits 第 427 行附近、构造器第 567 行、action padding 第 972 行附近、`__getitem__` 第 1082 行、`finalize` 第 1131 行、`add_frame` 第 1171 行、`save_episode` 第 1225 行、`create` 第 1642 行。SHA-256：`e0930de3c1dac7aedec3458cdabc6f5838e61c020927de2f7fe41308bd639809`。
- **[L2]** [LeRobot 官方 v0.4.4 utils 源码](https://github.com/huggingface/lerobot/blob/v0.4.4/src/lerobot/datasets/utils.py)；已安装 [utils.py](/mnt/c/Users/23660/Documents/Codex/2026-10-23/files-mentioned-by-the-user-hk/work/vla-env/lib/python3.12/site-packages/lerobot/datasets/utils.py)，`write_stats` 第 295 行、HF features 第 564 行、`validate_frame` 第 986 行、视频维度校验第 1089 行。SHA-256：`3b1a2552701faee5fd3d4149667129b94db52d608e9c07d8fff5e102c59dc569`。
- **[L3]** [LeRobot 官方 v0.4.4 video_utils 源码](https://github.com/huggingface/lerobot/blob/v0.4.4/src/lerobot/datasets/video_utils.py)，已在线核对 pyav fallback 分发；已安装 [video_utils.py](/mnt/c/Users/23660/Documents/Codex/2026-10-23/files-mentioned-by-the-user-hk/work/vla-env/lib/python3.12/site-packages/lerobot/datasets/video_utils.py)，默认解码器第 117 行、torchvision CPU 解码第 157 行、编码第 390 行、streaming 丢帧处理第 815 行附近。SHA-256：`90f93dc671edbb21c8ec6f57591f2c961ef64e08ec944abcc37157c579eaf842`。
- **[L4]** [LeRobot 官方 v0.4.4 compute_stats 源码](https://github.com/huggingface/lerobot/blob/v0.4.4/src/lerobot/datasets/compute_stats.py)；已安装 [compute_stats.py](/mnt/c/Users/23660/Documents/Codex/2026-10-23/files-mentioned-by-the-user-hk/work/vla-env/lib/python3.12/site-packages/lerobot/datasets/compute_stats.py)，图像采样第 197 行附近、`compute_episode_stats` 第 477 行、`aggregate_stats` 第 605 行。SHA-256：`941dd3c6d0f14704e95123c9a9c49270b2b5ea589f712b734adb4ee03b8736b2`。
- **[E1]** 本次实现 [export_fourview_demos.py](/mnt/c/Users/23660/Downloads/HK_IndoorBranch_R47b_20261022/grasp_optimization/export_fourview_demos.py) 及本轮约定的 collector 契约；这是本项目接口/处理行为的依据，不作为第三方采集精度或任务成功率的证据。

## 8. 主执行流程后续完成记录

导出器交付后，主流程已完成 6 条真实工程示范的采集和导出：每条195帧，共1170帧，训练4条、离线验证2条。最终数据集位于 `datasets/cup_fourview_v1`；四路视频的原生解码、完整数值标签、50步动作和 padding、训练部分统计均通过，根目录 conversion_report.json 的 validated 为 true。61项回归检查通过。此段补充前文第6节在导出器交付时尚未进行的实测；没有进行训练或权重更新。
