"""检索：稠密向量 + 词面 BM25，用倒数排名融合。

为什么不是纯稠密：实测这批同质临床文本的片段间相似度均值 0.579，而一条短 query
对全库的最大相似度只有 0.555——短 query 与长片段不在同一区域，排序不可靠。
词面一路能兜住「流涕」「腹泻」这类术语命中，融合后排序稳定得多。

检索池只有 clinical 片段。query 必须是**归一化之后**的结构化表述（详见
docs/stage1.md 的「已知限制」）。
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from harness.normalize import normalize
from tools import embed

CORPUS = Path(__file__).resolve().parent.parent / "corpus"
TOPK = 5
# 融合常数取 60，稠密与词面各自贡献按位次衰减，避免任何一路靠绝对分数垄断
RRF_K = 60
# 中文按 2-gram 切，无需分词依赖，也不会因为分词器版本变化而不可复现
NGRAM = 2


@dataclass(frozen=True)
class Passage:
    chunk_id: str
    title: str
    heading: str
    text: str
    score: float


class FixedPool:
    """固定检索池：用于隔离「知识库给了什么」这一层。

    阶段一的检索器与阶段二平台知识库不是同一实现，这层差异值多少，只能靠
    把池子换成无关内容或空池来量。
    """

    def __init__(self, passages: list[Passage]) -> None:
        self._passages = passages

    def search(self, query: str, k: int = TOPK) -> list[Passage]:
        return self._passages[:k]


class Index:
    """冻结向量与片段元数据。构造后不再读网络，只有 query 需要向量化。"""

    def __init__(self) -> None:
        self.meta = json.loads((CORPUS / "vectors.json").read_text(encoding="utf-8"))
        data = np.load(CORPUS / "vectors.npz")
        self._ids = [str(item) for item in data["ids"]]
        self._vectors = data["vectors"]
        self._rows = {
            row["chunk_id"]: row
            for row in (
                json.loads(line)
                for line in (CORPUS / "chunks.jsonl").read_text("utf-8").splitlines()
                if line
            )
        }
        self._bm25: _BM25 | None = None

    @property
    def model(self) -> str:
        return str(self.meta["model"])

    def passages(self) -> list[Passage]:
        """整池摊开。固定池实验要从中抽无关片段，所以需要一个整池视图。"""
        return [
            Passage(
                chunk_id=cid,
                title=self._rows[cid]["title"],
                heading=self._rows[cid]["heading"],
                text=self._rows[cid]["text"],
                score=0.0,
            )
            for cid in self._ids
        ]

    def _lexical(self, query: str) -> list[int]:
        if self._bm25 is None:
            self._bm25 = _BM25([self._rows[cid]["text"] for cid in self._ids])
        return self._bm25.rank(query)

    def search(self, query: str, k: int = TOPK) -> list[Passage]:
        folded = normalize(query)
        vector = _query_vector(folded)
        size = len(self._ids)

        dense = [index for index, _ in embed.top_k(self._vectors, vector, size)]
        fused = _rrf([dense, self._lexical(folded)], size)[: min(k, size)]

        hits = [(index, float(self._vectors[index] @ vector)) for index in fused]
        passages = []
        for index, score in hits:
            row = self._rows[self._ids[index]]
            passages.append(
                Passage(
                    chunk_id=row["chunk_id"],
                    title=row["title"],
                    heading=row["heading"],
                    text=row["text"],
                    score=score,
                )
            )
        return passages


def _ngrams(text: str) -> list[str]:
    folded = normalize(text)
    return [folded[i : i + NGRAM] for i in range(max(0, len(folded) - NGRAM + 1))]


class _BM25:
    """极简 BM25。语料只有几百条片段，Python 实现够用且完全可复现。"""

    def __init__(self, corpus: list[str], k1: float = 1.5, b: float = 0.75) -> None:
        self._docs = [_ngrams(text) for text in corpus]
        self._k1 = k1
        self._b = b
        self._lengths = [len(doc) for doc in self._docs]
        self._avg = sum(self._lengths) / max(1, len(self._lengths))
        self._df: dict[str, int] = {}
        for doc in self._docs:
            for term in set(doc):
                self._df[term] = self._df.get(term, 0) + 1

    def rank(self, query: str) -> list[int]:
        terms = _ngrams(query)
        total = len(self._docs)
        scores: list[float] = []
        for index, doc in enumerate(self._docs):
            counts: dict[str, int] = {}
            for term in doc:
                counts[term] = counts.get(term, 0) + 1
            score = 0.0
            for term in terms:
                if term not in counts:
                    continue
                df = self._df.get(term, 0)
                idf = math.log(1 + (total - df + 0.5) / (df + 0.5))
                tf = counts[term]
                norm = 1 - self._b + self._b * self._lengths[index] / max(self._avg, 1e-9)
                score += idf * tf * (self._k1 + 1) / (tf + self._k1 * norm)
            scores.append(score)
        return sorted(range(total), key=lambda i: -scores[i])


def _rrf(rankings: list[list[int]], size: int) -> list[int]:
    """倒数排名融合：只看位次不看绝对分数，两路分数量纲不同也能合。"""
    total: dict[int, float] = {}
    for ranking in rankings:
        for position, index in enumerate(ranking):
            total[index] = total.get(index, 0.0) + 1.0 / (RRF_K + position + 1)
    return sorted(range(size), key=lambda i: -total.get(i, 0.0))


def _query_vector(query: str) -> NDArray[np.float32]:
    """query 向量按文本缓存，run 记录里存的就是它，检索池因此可离线重算。"""
    cache: Path = CORPUS.parent / ".cache" / "query"
    cache.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(query.encode("utf-8")).hexdigest()
    path = cache / f"{key}.json"
    if path.exists():
        raw = json.loads(path.read_text(encoding="utf-8"))
    else:
        raw = embed._request([query])[0]
        path.write_text(json.dumps(raw), encoding="utf-8")
    vector: NDArray[np.float32] = np.asarray([raw], dtype=np.float32)
    normalized: NDArray[np.float32] = embed._normalize(vector)[0]
    return normalized
