"""Import selected Skill2Real skill text as candidate memory, never as code.

The public Skill2Real catalogue describes skills as natural-language guidance,
an API-level code template, and a compact state description. The site's own
``skill-memory.md`` says the code inside a skill document is context for
program generation, not a callable package. This module follows that boundary:
it stores paraphrased, attributed text as :class:`MemoryNote` candidates and
does not vendor or execute the third-party code templates.

Every note is scoped to the local T01 assets it is intended to guide and keeps
the source URL, source-file hash and per-entry hash. A note is not evidence of
a local physical effect and cannot satisfy a postcondition by itself.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from .contracts import MemoryNote, Scope, Status

SOURCE_URL = "https://skill2real.github.io/skill-library-data.js"
SOURCE_SHA256 = "f51d813378ae7c9840c45765d8a60d6c5de8b6daa4915a61e53c054f790c0ca3"
RETRIEVED = "2026-11-06"


@dataclass(frozen=True)
class ExternalSkill:
    source_id: str
    title: str
    layer: str
    category: str
    source_digest: str
    rule: str
    applies: str
    local_use: str
    caveat: str


SELECTED: tuple[ExternalSkill, ...] = (
    ExternalSkill(
        "skill-001", "Choose a clear side for rim contact", "Cerebellum", "grasp",
        "a215328148ec13ce56491685473c8561fee8054d9d7f39e5929be1ebe356e73a",
        "杯子等开口容器被把手或邻近物体挤住时，选一条没有遮挡的杯沿侧，接触位于可见杯口下方的杯壁；闭合方向与接近方向都由该侧可见间隙决定。",
        "带把手或邻近有杂物的杯、碗等开口容器，用于桌面放置或容器内放置。",
        "T01 抓杯前先检查把手朝向与左右侧间隙；接触点与闭合方向由当前头部 RGB-D 中可见的杯壁决定，不照搬固定 yaw。",
        "该条假设能看到杯沿与杯壁；若遮挡导致侧向间隙不可判，应保留为未解析，不能凭杯子中心猜一个侧面。",
    ),
    ExternalSkill(
        "skill-003", "Identify the actionable receptacle opening", "Cerebellum", "inspect",
        "b9438bf211d4411becae7d7bd180521da0b0c34bf9c0e60033824ef08bad7bfa",
        "用可见面积、与父物体的重叠和包含关系，把容器的可用开口与边沿或侧壁区分开；关系含糊时把开口标为未解析。",
        "定位语义父物体之后的篮子、箱子、抽屉和托盘。",
        "复用我们已有的 `tray_tools.locate_tray` 可见几何结果时，必须同时检查托盘底板与边沿；只得到一个外接框不算找到可承托内部。",
        "我们的托盘有低边沿和可见标记，不能把语义分割结果直接当成可放置区域；底板承托仍由独立评价器判。",
    ),
    ExternalSkill(
        "skill-004", "Choose a supported interior placement", "Cerebellum", "transport",
        "77b3dd31d36a85fbad8abb10425844fcf7a7f880c876765c22f5fbc156db9782",
        "斜视容器时，先比较其可见结构与开口，再选内部承托目标；看到一面侧壁不等于识别出可承托的内部。",
        "从斜上方观察的篮子、箱子和抽屉内放置。",
        "T01 的放置点仍由 `tray_floor_center_m` 加杯子在掌中的偏移计算；该条提醒我们在遮挡时不要把侧壁或外接框当成底板中心。",
        "我们当前放置判据是杯底完整投影进入底板并留 1 mm 余量，不能仅凭视觉上“在托盘里”改判。",
    ),
    ExternalSkill(
        "skill-016", "Adapt rim contact to handle clearance", "Cerebellum", "grasp",
        "4ea57b69aaca96d629c0f5c610afa83c3478595d6710727bcf893ca082ec8ac1",
        "带把手容器要选一个给手指和后续抬起都留出空间的杯沿侧；接触侧壁，同时让把手留在接近路径之外。",
        "杯子、小壶等带把手容器，桌面放置和容器内放置都适用。",
        "T01 的杯子有把手；接近前检查把手是否落在手掌与杯壁之间，必要时调整抓取 yaw 或接近方向，而不是继续沿默认 yaw 直推。",
        "Dex3-1 的七关节手形与二指夹爪不同；该条只约束空间避让，不提供可直接执行的手指闭合序列。",
    ),
    ExternalSkill(
        "skill-022", "Balance rim engagement and release clearance", "Cerebellum", "grasp",
        "a49b64f3937f1ead1abe1156743dd02e0275898993e6fc28afbac912ebd5bbbb",
        "选杯沿接触时要同时考虑抓起和释放：能抓住杯子的接触，仍可能在杯子落到支撑面时把内侧手指卡在杯沿。",
        "杯子、带垂直环的把手工具和炊具。",
        "T01 释放前检查手指与杯沿/托盘的相对位置；先建立支撑再张开，避免张开动作把杯子带偏或钩住托盘边沿。",
        "我们目前没有内侧手指卡住的直接传感证据；该条作为释放前的几何检查项，不能替代独立承托判据。",
    ),
    ExternalSkill(
        "skill-037", "Carry a rim-held vessel in short segments", "Cerebellum", "transport",
        "37f0fe6ef283ba3679f7c8a44274d727a98c354ab3c93113dadb5424a4ad0c14",
        "杯沿或把手持杯做长距离搬运时，把平移拆成短段；下降前在目的地上方重新观察被携带的杯体。",
        "杯沿、把手或边缘持物的长距离取放。",
        "T01 已有 5 cm 单次移动上限和分段 `_walk`；该条补上“每段后在目的地上方重观察杯体”，而不是只重观察手掌。",
        "我们的 5 cm 上限来自漂浮基座漂移经验，不能因为这条规则放宽；分段数与每段时长仍受预登记预算限制。",
    ),
    ExternalSkill(
        "skill-039", "Check realized clearance during lift", "Cerebellum", "transport",
        "543aef57c5c2f3b784b5a50fa3a074225159613a037b1f4a2df1962cf829e997",
        "大幅抬升造成横向偏移时，保留已经完成的抬升，只把失败的后缀换成更短的单调向上小步。",
        "大幅抬升出现横向偏移时。",
        "T01 的 `raise_clear` 失败或出现侧向漂移时，不回退已抬升的高度，只缩短剩余竖直段并重观察；这正对应我们现有的有界修复思路。",
        "该条描述的是修复策略，不是成功判据；最终仍由独立评价器判抬起、保持和放置。",
    ),
    ExternalSkill(
        "skill-045", "Clear a raised receptacle during transport", "Cerebellum", "transport",
        "bd952a7f8c7ebf531f89e941bff485e02e68afdd017ec664b9bcae48a5feef78",
        "对带凸起边沿的容器，先让被持物体的最低点越过边沿，再横向移动；开始竖直下降前先观察高处的目的对准。",
        "放入篮子/箱子以及越过凸起托盘的放置。",
        "T01 运输到托盘上方时，先检查杯底最低点高于托盘边沿，再横移到承托区上方；不要以手掌高度代替杯底高度。",
        "我们已有 `place_above_m` 与杯底偏移计算；该条要求把“杯底最低点”显式作为检查量，而不是只看掌位。",
    ),
    ExternalSkill(
        "skill-046", "Clear the inner finger after release", "Cerebellum", "transport",
        "78ee0a12b99230a666d63dc60aaa650bd765655047f9356a8aa9dc4c93992727",
        "杯沿持杯释放后，内侧手指可能仍钩住杯沿；先确认杯子已获得支撑，再让仍接触的手指朝可见外侧退出，最后才抬手离开。",
        "杯沿持杯放到桌面或容器内。",
        "T01 释放后先保持掌位、确认托盘承托，再张开并向外侧退指；若手指仍接触杯沿，不把张开命令当成释放完成。",
        "Dex3-1 没有“内侧/外侧手指”这一二指夹爪语义；需要按实际七关节手形重新定义退出方向，不能照抄手指动作。",
    ),
    ExternalSkill(
        "skill-051", "Confirm mug retention from current evidence", "Brain", "progress",
        "0ceae2a1e265234667e6b87906d22d6b6bd1a59bf4eda5f72828a4e23f972a96",
        "杯子接触发生后，是否仍被抓住要由当前证据判断；不能因为手部命令返回完成就推进后续任务。",
        "已有杯子接触、但持续抓持尚未确认时。",
        "T01 的 `close_hand` 返回 `EXECUTED` 只说明命令执行；必须再看杯子是否随手上移、是否离开原支撑，才允许进入运输。",
        "这与本项目“EXECUTED 不等于技能成功”的规则一致；独立评价器仍是最终判据，本体感觉只用于回合内决策。",
    ),
    ExternalSkill(
        "skill-058", "Distinguish support contact from free motion", "Cerebellum", "transport",
        "01e469dfff097238539687885859999aff1b0ed4d4f4a7bc6973b852fd8dbf4b",
        "把“已经接触最终支撑”与“仍在自由空间运动”区分开；观察到物体到达支撑后，再决定如何释放。",
        "物体放到架子/桌面，或浅容器内就位。",
        "T01 下降阶段用杯底与托盘底板的实际距离/接触判断是否到达支撑，而不是只按预设高度或手掌位置开手。",
        "我们当前主判据是杯底投影与承托力；该条可作为释放前的回合内检查，不能替换官方 1 mm 余量。",
    ),
    ExternalSkill(
        "skill-063", "Gate traversal on the first lift's evidence", "Brain", "progress",
        "05aefc943a02db3fa984cf23a492cd8357e21eadcd69c774bcf60ff68f756cbd",
        "从抓取转入长距离运输前，要求有支持的抓取证据；首次抬升未确认时，把剩余任务保持为未完成。",
        "抓取到运输的边界。",
        "T01 在 `close_hand` 后先做一次小幅抬升/保持，确认杯子随动，再进入 `lift` 和运输；未确认就停止或修复，不继续完整流程。",
        "首次抬升通过也不证明整项成功；放置、释放和稳定仍分开判。",
    ),
    ExternalSkill(
        "skill-080", "Lower a vessel into a bounded receptacle", "Cerebellum", "transport",
        "68b32218953d2a626897cf3fe9a1c8644ed1e204ed67625ccb6cb9d8d889b39b",
        "杯子在进入有界容器末段发生倾斜时，先检查与底板、侧壁的干涉，再继续下降；比较释放前与静置后的物体状态。",
        "杯子/碗放入托盘，或不规则物体放入箱子。",
        "T01 的 `descend_to_lower` 若出现倾斜或边沿接触，先停下检查杯底与托盘边沿/底板的几何关系，不盲目继续下降；释放后比较静置倾角与位置。",
        "这直接对应历史 6.4 mm 近失与 6–12° 倾斜失败，但那些失败不能仅凭这条规则归因；需要新的实执行证据。",
    ),
    ExternalSkill(
        "skill-090", "Place the object body, not the wrist", "Cerebellum", "transport",
        "aeb06ed7bbb7579ded3c0e32160b0bb7d9e0f2655bc389ef011c038c6b67f701",
        "杯沿或把手持杯时，释放前观察被携带的杯体是否在支撑上方；腕部居中不等于杯体居中。",
        "杯沿、把手、边缘等非对称抓取，以及容器内放置。",
        "T01 已用 `cup_in_palm_m` 把掌位换算成杯底位置；该条要求释放前用当前观测再核对一次杯体，而不是只信初始偏移。",
        "我们的 `cup_in_palm_m` 来自 `grasp_probe`，若抓取滑动该偏移会变；当前没有在线重估时必须把不确定性写出来。",
    ),
    ExternalSkill(
        "skill-097", "Release near the interior support", "Cerebellum", "transport",
        "bb70b6afeb371e04a668c2a6b30e3995f10b5fb9068b6a445e634a2b6afe9c76",
        "刚性物体进入托盘/箱子时，把内部承托面与边沿分开；在障碍上方释放可能把物体弹到目标外侧。",
        "罐/瓶放入托盘，刚性物体放入箱子。",
        "T01 的释放高度以托盘底板为基准，而不是以边沿或托盘外接框为基准；开手前检查杯底已在承托区上方。",
        "官方评价器要求杯底完整投影进入承托区并留 1 mm 余量；该条只帮助回合内选释放点，不能放宽评价。",
    ),
    ExternalSkill(
        "skill-120", "Separate gripper obstruction from retention", "Brain", "progress",
        "e41ad58cd63160b46eba1b0286dbc0bb54747363f6205df2e6ecc56f2d8d5f4e",
        "夹爪闭合受阻可能只是碰到物体，不等于已经抓住；在任务物体被支持为已获得之前，保持抓持状态未定。",
        "夹爪在物体边缘闭合后，开口读数不能证明抓持。",
        "T01 不能把 `close_hand` 的关节到位或接触力非零直接当成抓牢；要结合杯子随动、抬升和保持结果。",
        "Dex3-1 的接触分布比二指夹爪复杂；该条只给出“不要用闭合读数代替抓持证据”的原则。",
    ),
)


def _canonical_entry(entry: dict) -> str:
    return json.dumps(entry, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def source_entries(path: Path | str) -> dict[str, dict]:
    text = Path(path).read_text(encoding="utf-8")
    if not text.startswith("const skillLibraryData = "):
        raise ValueError("unexpected Skill2Real skill-library-data.js format")
    data = json.loads(text.removeprefix("const skillLibraryData = ").rstrip().rstrip(";"))
    return {entry["id"]: entry for entry in data["entries"]}


def verify_source(path: Path | str, expected_sha256: str = SOURCE_SHA256) -> str:
    raw = Path(path).read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if actual != expected_sha256:
        raise ValueError(f"Skill2Real source changed: {actual}")
    return actual


def entry_digest(entry: dict) -> str:
    return hashlib.sha256(_canonical_entry(entry).encode("utf-8")).hexdigest()


def load_registry_notes(registry_root: Path | str, snapshot_id: str | None = None
                        ) -> tuple[str, tuple[MemoryNote, ...]]:
    """Load the frozen imported notes by registry snapshot; never regenerate them."""
    from .registry import Registry

    registry = Registry(registry_root)
    snapshot = registry.head() if snapshot_id is None else registry.load(snapshot_id).snapshot
    if snapshot is None:
        raise KeyError("no frozen Skill2Real memory snapshot")
    view = registry.load(snapshot.id)
    items = tuple(sorted(
        (artifact for artifact in view.artifacts.values() if isinstance(artifact, MemoryNote)),
        key=lambda note: note.id,
    ))
    if not items:
        raise KeyError(f"snapshot {snapshot.id} has no memory notes")
    return snapshot.id, items


def notes(scope: Scope, source_path: Path | str | None = None) -> tuple[MemoryNote, ...]:
    """Build candidate memory notes, verifying each selected entry if a source is given."""
    by_id = source_entries(source_path) if source_path is not None else {}
    result = []
    for item in SELECTED:
        if by_id:
            entry = by_id.get(item.source_id)
            if entry is None:
                raise ValueError(f"missing Skill2Real entry: {item.source_id}")
            actual = entry_digest(entry)
            if actual != item.source_digest:
                raise ValueError(f"Skill2Real entry changed: {item.source_id}: {actual}")
        text = (
            "[EXTERNAL PRIOR - NOT LOCALLY VALIDATED]\n"
            f"Source: Skill2Real skill catalogue, {item.source_id} ({item.title}); "
            f"{item.layer}/{item.category}.\n"
            f"Rule (paraphrased): {item.rule}\n"
            f"Applies when: {item.applies}\n"
            f"Local adaptation: {item.local_use}\n"
            f"Caveat: {item.caveat}\n"
            "This is textual guidance for program generation, not executable code and not a "
            "validated G1 skill. It cannot satisfy a postcondition or count as a local success."
        )
        result.append(MemoryNote(
            id="mem_skill2real_" + item.source_id.removeprefix("skill-"),
            text=text,
            scope=scope,
            status=Status.CANDIDATE,
            evidence=(SOURCE_URL, f"source_sha256:{SOURCE_SHA256}",
                      f"entry_sha256:{item.source_digest}", f"retrieved:{RETRIEVED}"),
        ))
    return tuple(result)
