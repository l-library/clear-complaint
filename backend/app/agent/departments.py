"""受控科室表：首推科室只能从这里选（17 个，阶段一冻结，版本 1）。

数据复制自 experiment/corpus/departments.json，两边独立维护，改动需同步版本号。
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"


@lru_cache(maxsize=1)
def names() -> tuple[str, ...]:
    """受控科室名单。草稿里的科室不在这里，整个草稿按结构不合规处理。"""
    payload = json.loads((DATA / "departments.json").read_text(encoding="utf-8"))
    rows = payload["departments"]
    return tuple(row["name"] for row in rows)


def contains(name: str) -> bool:
    return name in names()
