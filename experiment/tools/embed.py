"""把片段向量化并冻结成仓库工件。

冻结的意义：检索结果必须能离线重算。向量只算一次，存 corpus/vectors.npz；之后
检索只对 query 调一次接口，把 query 向量与模型名写进 run 记录，任何人拿到仓库就能
复现同一份检索池，不依赖当天的服务状态。

端点走 OpenAI 兼容的 /embeddings，所以换成 MaaS 之外的兼容服务只需要改三个变量：
EMBED_BASE_URL、EMBED_API_KEY、EMBED_MODEL。

用法：
    uv run python -m tools.embed            # 建向量
    uv run python -m tools.embed --check    # 只校验已有工件
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent.parent
CORPUS = HERE / "corpus"
CACHE = HERE / ".cache" / "embed"

# 实测：MaaS 的向量化端点在 /v1 下，/openai/v1 只有对话接口，会返回 404 APIG.0101
DEFAULT_BASE_URL = "https://api.modelarts-maas.com/v1"
DEFAULT_MODEL = "bge-m3"
BATCH_SIZE = 16
# 服务端限流 4 次/秒（ModelArts.81101），多线程跑矩阵时靠这个闸门排队，
# 而不是靠撞 429 再退避
MIN_INTERVAL = 0.30
_THROTTLE = threading.Lock()
_LAST_CALL = 0.0


class EmbedError(RuntimeError):
    pass


def _config() -> tuple[str, str, str]:
    base = os.environ.get("EMBED_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    key = (
        os.environ.get("EMBED_API_KEY")
        or os.environ.get("MAAS_API_KEY")
        or os.environ.get("HUAWEI_MAAS_API_KEY", "")
    )
    model = os.environ.get("EMBED_MODEL", DEFAULT_MODEL)
    if not key:
        raise EmbedError("缺少 EMBED_API_KEY / MAAS_API_KEY / HUAWEI_MAAS_API_KEY")
    return base, key, model


def _wait_turn() -> None:
    global _LAST_CALL
    with _THROTTLE:
        gap = time.monotonic() - _LAST_CALL
        if gap < MIN_INTERVAL:
            time.sleep(MIN_INTERVAL - gap)
        _LAST_CALL = time.monotonic()


def _request(texts: list[str]) -> list[list[float]]:
    base, key, model = _config()
    body = json.dumps({"model": model, "input": texts}).encode()
    request = urllib.request.Request(
        f"{base}/embeddings",
        data=body,
        method="POST",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    last: Exception | None = None
    for attempt in range(6):
        _wait_turn()
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                payload = json.loads(response.read().decode("utf-8"))
            rows = sorted(payload["data"], key=lambda row: row["index"])
            return [list(row["embedding"]) for row in rows]
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "ignore")[:160]
            # 429 是限流，重试就好；其他 4xx 是我们自己的问题，重试无意义
            if exc.code == 429 or exc.code >= 500:
                last = exc
                time.sleep(1.5 * (attempt + 1))
                continue
            raise EmbedError(f"向量化失败 {exc.code}: {detail}") from exc
        except Exception as exc:  # noqa: BLE001 - 网络抖动重试
            last = exc
            time.sleep(2 * (attempt + 1))
    raise EmbedError(f"向量化失败（重试 6 次仍不通）: {last}")


def _cached(texts: list[str]) -> list[list[float]]:
    """按文本哈希缓存，重复运行不重复消耗配额。"""
    CACHE.mkdir(parents=True, exist_ok=True)
    keys = [hashlib.sha256(text.encode("utf-8")).hexdigest() for text in texts]
    missing = [
        text for text, key in zip(texts, keys, strict=True) if not (CACHE / f"{key}.json").exists()
    ]
    for start in range(0, len(missing), BATCH_SIZE):
        batch = missing[start : start + BATCH_SIZE]
        for text, vector in zip(batch, _request(batch), strict=True):
            key = hashlib.sha256(text.encode("utf-8")).hexdigest()
            (CACHE / f"{key}.json").write_text(json.dumps(vector), encoding="utf-8")
    return [json.loads((CACHE / f"{key}.json").read_text(encoding="utf-8")) for key in keys]


def top_k(matrix: np.ndarray, query: np.ndarray, k: int) -> list[tuple[int, float]]:
    """余弦相似度取前 k。向量已归一化，点积即余弦。"""
    scores = matrix @ query
    order = np.argsort(-scores)[:k]
    return [(int(index), float(scores[index])) for index in order]


def _pool() -> list[dict[str, str]]:
    """检索池放 clinical 与 triage 片段。
    治疗段落里的剂量与方剂不进池（检索到就会诱发用药建议）；triage 是受控表
    corpus/triage_pool.json 里逐条策展的分诊判据：住院标准、就医与居家指征、
    重症高危人群判据，它们住在治疗/预防/流行病学章节里，却是分诊的直接依据。
    """
    rows = [
        json.loads(line)
        for line in (CORPUS / "chunks.jsonl").read_text("utf-8").splitlines()
        if line
    ]
    return [row for row in rows if row["role"] in ("clinical", "triage")]


def _normalize(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return (matrix / np.where(norms == 0, 1.0, norms)).astype(np.float32)


def build() -> int:
    rows = _pool()
    if not rows:
        raise EmbedError("检索池为空")
    texts = [f"{row['title']}｜{row['heading']}｜{row['text']}" for row in rows]
    vectors = _normalize(np.asarray(_cached(texts), dtype=np.float32))
    ids = np.asarray([row["chunk_id"] for row in rows])

    np.savez_compressed(CORPUS / "vectors.npz", ids=ids, vectors=vectors)
    _, _, model = _config()
    (CORPUS / "vectors.json").write_text(
        json.dumps(
            {
                "model": model,
                "dim": int(vectors.shape[1]),
                "count": int(vectors.shape[0]),
                "normalized": True,
                "chunks_sha256": hashlib.sha256((CORPUS / "chunks.jsonl").read_bytes()).hexdigest(),
                "pool": "clinical + triage",
                "text_template": "title｜heading｜text",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"[info] {vectors.shape[0]} 条向量，维度 {vectors.shape[1]}，模型 {model}")
    return 0


def check() -> int:
    """工件自检：条数一致、维度一致、数值有限、chunks 未变。"""
    meta = json.loads((CORPUS / "vectors.json").read_text(encoding="utf-8"))
    data = np.load(CORPUS / "vectors.npz")
    vectors = data["vectors"]
    rows = _pool()

    problems: list[str] = []
    if vectors.shape[0] != len(rows):
        problems.append(f"向量 {vectors.shape[0]} 条，检索池 {len(rows)} 条")
    if vectors.shape[1] != meta["dim"]:
        problems.append(f"维度 {vectors.shape[1]} 与元数据 {meta['dim']} 不符")
    if not np.isfinite(vectors).all():
        problems.append("存在非有限数值")
    current = hashlib.sha256((CORPUS / "chunks.jsonl").read_bytes()).hexdigest()
    if current != meta["chunks_sha256"]:
        problems.append("chunks.jsonl 已变动，向量过期，需要重建")
    for item in problems:
        print(f"[fail] {item}")
    if problems:
        return 1
    print(f"[ok] {vectors.shape[0]} 条向量，维度 {vectors.shape[1]}，模型 {meta['model']}")
    return 0


def main(argv: list[str]) -> int:
    return check() if "--check" in argv else build()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
