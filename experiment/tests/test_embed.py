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
    for name in ("EMBED_API_KEY", "MAAS_API_KEY", "HUAWEI_MAAS_API_KEY"):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(embed.EmbedError, match="EMBED_API_KEY"):
        embed._config()


def test_rate_limit_is_retried_not_fatal(monkeypatch: pytest.MonkeyPatch) -> None:
    """服务端限流 4 次/秒；把它当致命错误会让整轮矩阵挂掉。"""
    import urllib.error

    calls = {"n": 0}

    class FakeResponse:
        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return b'{"data": [{"index": 0, "embedding": [1.0, 2.0]}]}'

    def fake_urlopen(*args: object, **kwargs: object) -> FakeResponse:
        calls["n"] += 1
        if calls["n"] == 1:
            raise urllib.error.HTTPError("u", 429, "too many", {}, None)  # type: ignore[arg-type]
        return FakeResponse()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setenv("EMBED_API_KEY", "x")
    monkeypatch.setattr(embed, "MIN_INTERVAL", 0.0)

    assert embed._request(["甲"]) == [[1.0, 2.0]]
    assert calls["n"] == 2
