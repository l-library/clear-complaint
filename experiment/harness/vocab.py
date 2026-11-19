"""候选词表闸门：可能相关情况只能落在受控病名上。

模型的自由命名五花八门（「普通感冒（不构成诊断）」「新冠病毒感染（需病原学鉴别）」），
直接输出就成了自造病名。这里把自由命名折到受控词表：词表里的病名或别名出现在
模型给的名字里，就算落在词表内；折不上的删除，并且把原本的自由命名记下来，
方便看模型的命名偏好。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

CORPUS = Path(__file__).resolve().parent.parent / "corpus"


@dataclass(frozen=True)
class Term:
    name: str
    aliases: tuple[str, ...]
    domain: str
    department: str


@lru_cache(maxsize=1)
def terms() -> tuple[Term, ...]:
    payload = json.loads((CORPUS / "vocab.json").read_text(encoding="utf-8"))
    return tuple(
        Term(
            name=row["name"],
            aliases=tuple(row["aliases"]),
            domain=row["domain"],
            department=row["department"],
        )
        for row in payload["terms"]
    )


@lru_cache(maxsize=1)
def _known() -> set[str]:
    return {term.name for term in terms()} | {alias for term in terms() for alias in term.aliases}


def resolve(name: str) -> Term | None:
    """把一个自由命名折到受控词表。取最长命中，避免「感冒」抢走「流行性感冒」。"""
    best: Term | None = None
    best_len = 0
    for term in terms():
        for surface in (term.name, *term.aliases):
            if surface and surface in name and len(surface) > best_len:
                best, best_len = term, len(surface)
    return best


def known_terms() -> set[str]:
    """给输入侧归因摘除用的词面集合。"""
    return set(_known())
