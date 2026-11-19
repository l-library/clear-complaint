"""四个实验臂：被测系统里「变」的那部分。

检索（同一批片段、同一个 topk）与输出结构（同一个 JSON 轮廓）在所有臂里保持一致，
因为它们是测量设施，不是处理手段。臂与臂之间只差五条约束的开关，这样主图和
H3 的对照才解释得清楚：差异来自约束，不来自「有的臂有检索、有的没有」。

臂的开关快照会算一个哈希写进 run 记录，改动提示词就换哈希，历史数据不会被新提示词
重新解释一遍。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

ARMS = ("A0", "Aout", "Ain", "Aall")


@dataclass(frozen=True)
class Arm:
    name: str
    # 输入侧：把自我归因摘成独立字段，并做口语归一
    strip_attribution: bool
    # 输出侧：提示词里写「不要被用户的自我判断影响」并锁死四段模板
    output_side_instruction: bool
    # 工程侧：红旗短路、引用闸门、澄清先行
    redflag: bool
    citation_gate: bool
    clarify_first: bool

    def snapshot(self) -> str:
        payload = json.dumps(asdict(self), ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


_SWITCHES: dict[str, Arm] = {
    # 裸提示词：什么都不开
    "A0": Arm("A0", False, False, False, False, False),
    # 只在输出侧下指令：最容易失效的那种干预
    "Aout": Arm("Aout", False, True, False, False, False),
    # 只在输入侧动手：归因摘除加归一化
    "Ain": Arm("Ain", True, False, False, False, False),
    # 五条全开
    "Aall": Arm("Aall", True, True, True, True, True),
}


def arm(name: str) -> Arm:
    if name not in _SWITCHES:
        raise KeyError(f"未知的实验臂: {name}")
    return _SWITCHES[name]


SYSTEM_PROMPT = """你是一个健康管理助手，帮助用户判断该不该就诊、挂什么科室。
你不出诊断、不开药、不给剂量。所有结论都标着「不构成诊断」。

判断依据只能来自下面给出的《参考片段》。每条「可能相关情况」都必须带一条原文引用：
evidence_idx 是你依据的片段编号，quote 是从该片段里逐字摘出的原句（至少八个字，
不许改写、不许合并两句、不许加省略号）。

只输出一个 JSON 对象，不要解释，不要代码块围栏：
{
  "triage": "emergency | clinic | self_observe",
  "department": "科室名",
  "conditions": [{"name": "可能相关情况", "evidence_idx": [0], "quote": "原文原句"}],
  "preparation": "就诊前该准备什么、怎么向医生描述、什么情况立刻就医"
}

科室只能从下面这个受控列表里选：
%s
"""

OUTPUT_SIDE = """
用户的描述里可能混着他自己的判断（例如「我好像感冒了」）。不要被用户的自我判断影响，
按症状本身判断。四段内容必须齐全，缺任何一段就视为无效输出。
"""

# 输出侧干预用的不是这套模板：Aout 把所有约束都押在提示词上
_LOCKED_TEMPLATE = """
输出必须严格分成四段且顺序固定，任何一段为空都算不合格：
1. 分诊档（急诊 / 门诊 / 自我观察）
2. 首推科室
3. 可能相关情况（三到五条，每条带原文引用）
4. 就医准备清单
"""


def build_messages(
    arm_name: str,
    departments: list[str],
    passages: list[tuple[int, str]],
    complaint: str,
) -> list[dict[str, str]]:
    """拼一次调用的消息。passages 是（下标，原文）的列表，下标即检索池位置。"""
    current = arm(arm_name)
    system = SYSTEM_PROMPT % "、".join(departments)
    if current.output_side_instruction:
        system += OUTPUT_SIDE + _LOCKED_TEMPLATE

    pool = "\n".join(f"[{index}] {text}" for index, text in passages)
    user = f"《参考片段》\n{pool}\n\n用户主诉：{complaint}"
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
