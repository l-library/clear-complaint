from pathlib import Path

import numpy as np
import pytest

from tools import embed


def test_normalize_makes_unit_vectors() -> None:
    matrix = np.asarray([[3.0, 4.0], [0.0, 0.0]], dtype=np.float32)

    normalized = embed._normalize(matrix)

    assert np.isclose(np.linalg.norm(normalized[0]), 1.0)
    # 零向量不能除出 NaN，检索池里偶尔会有空片段
    assert np.isfinite(normalized[1]).all()


def test_top_k_returns_best_matches_in_order() -> None:
    matrix = embed._normalize(np.asarray([[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]], dtype=np.float32))
    query = embed._normalize(np.asarray([[1.0, 0.1]], dtype=np.float32))[0]

    result = embed.top_k(matrix, query, k=2)

    assert [index for index, _ in result] == [0, 2]
    assert result[0][1] > result[1][1]


def test_cached_reuses_vectors_and_only_calls_for_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: object
) -> None:
    calls: list[list[str]] = []

    def fake_request(texts: list[str]) -> list[list[float]]:
        calls.append(texts)
        return [[float(len(text)), 1.0] for text in texts]

    monkeypatch.setattr(embed, "CACHE", Path(str(tmp_path)))
    monkeypatch.setattr(embed, "_request", fake_request)

    first = embed._cached(["甲", "乙"])
    second = embed._cached(["甲", "丙"])

    assert first == [[1.0, 1.0], [1.0, 1.0]]
    assert second[1] == [1.0, 1.0]
    # 第二次只把没缓存过的「丙」发出去
    assert calls[1] == ["丙"]


def test_missing_credentials_is_reported_not_silently_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("EMBED_API_KEY", raising=False)
    monkeypatch.delenv("MAAS_API_KEY", raising=False)

    with pytest.raises(embed.EmbedError, match="EMBED_API_KEY"):
        embed._config()
