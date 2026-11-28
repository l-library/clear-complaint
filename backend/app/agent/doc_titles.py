"""文档展示名映射：文件名式的来源标题折成人文标题。

数据复制自 experiment/corpus/manifest.json 的 filename 式 source → title
（两边独立维护，改动需同步版本号）。未知值原样透传，不发明标题。
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"


@lru_cache(maxsize=1)
def titles() -> dict[str, str]:
    payload = json.loads((DATA / "doc_titles.json").read_text(encoding="utf-8"))
    return dict(payload["titles"])


def display_name(raw: str) -> str:
    """平台透传的 doc_title 在冻结表里时换成人文标题，否则原样返回。"""
    return titles().get(raw, raw)
