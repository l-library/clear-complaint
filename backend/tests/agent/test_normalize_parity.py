"""归一化替换表与 experiment 基线逐条对齐。

阶段一的覆盖测量是在 experiment/harness/normalize.py 上做的，backend 的归一化
一旦少了某条映射，红旗就会漏掉测量认为已经覆盖的表述。两个项目约定独立维护、
不互相 import，所以这里只读源码文本：ast 取出两侧的赋值字面量再比内容。
"""

import ast
from pathlib import Path

import pytest

from app.agent.normalize import COLLOQUIAL_MAP, PINYIN_MAP

EXPERIMENT_NORMALIZE = (
    Path(__file__).resolve().parents[3] / "experiment" / "harness" / "normalize.py"
)
TABLES = {
    "PINYIN_MAP": PINYIN_MAP,
    "COLLOQUIAL_MAP": COLLOQUIAL_MAP,
}


def _as_string_pairs(name: str, value: object) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, tuple):
        raise AssertionError(f"experiment 的 {name} 不是元组：{value!r}")
    pairs: list[tuple[str, str]] = []
    for item in value:
        if not (
            isinstance(item, tuple)
            and len(item) == 2
            and all(isinstance(part, str) for part in item)
        ):
            raise AssertionError(f"experiment 的 {name} 里出现非二元字符串项：{item!r}")
        left, right = item
        pairs.append((str(left), str(right)))
    return tuple(pairs)


def _experiment_table(name: str) -> tuple[tuple[str, str], ...]:
    """从 experiment 源码里取出替换表，不 import 那个项目。"""
    tree = ast.parse(EXPERIMENT_NORMALIZE.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", None) == name:
            assert node.value is not None, f"experiment 的 {name} 只有注解没有赋值"
            literal: object = ast.literal_eval(node.value)
            return _as_string_pairs(name, literal)
    raise AssertionError(f"experiment/harness/normalize.py 里找不到 {name} 的赋值")


@pytest.mark.parametrize("name", TABLES)
def test_normalize_table_matches_experiment(name: str) -> None:
    backend = TABLES[name]
    experiment = _experiment_table(name)
    missing = [pair for pair in experiment if pair not in backend]
    extra = [pair for pair in backend if pair not in experiment]

    assert backend == experiment, (
        f"{name} 在 backend 与 experiment 之间已经漂移："
        f"backend 缺 {missing}，多出 {extra}"
        f"{'，只有顺序不同' if not missing and not extra else ''}。"
        "按约定两边在同一次提交里改、位置也一致，让 diff 只显示真实变化"
    )
