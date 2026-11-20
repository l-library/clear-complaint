import numpy as np
import pytest

from harness import retrieval


def test_bm25_ranks_the_document_that_actually_contains_the_term() -> None:
    index = retrieval._BM25(
        [
            "手足口病主要表现为手、足、口腔等部位的斑丘疹、疱疹。",
            "细菌性痢疾以腹泻、里急后重、脓血便为主要表现。",
            "水痘表现为发热与瘙痒性水疱疹。",
        ]
    )

    assert index.rank("腹泻里急后重")[0] == 1


def test_rrf_fuses_by_position_not_by_absolute_score() -> None:
    """两路分数量纲不同（余弦在 0 到 1，BM25 无上界），只能看位次。"""
    dense = [0, 1, 2]
    lexical = [2, 0, 1]

    fused = retrieval._rrf([dense, lexical], 3)

    # 0 与 2 各有一路第一、一路第二，1 两路都垫底
    assert fused[:2] == [0, 2] or fused[:2] == [2, 0]
    assert fused[-1] == 1


def test_ngrams_work_without_a_tokenizer() -> None:
    """中文按 2-gram 切，不引分词依赖，也不会因分词器版本变化不可复现。"""
    assert retrieval._ngrams("脓血便") == ["脓血", "血便"]


def test_ngrams_are_taken_after_colloquial_folding() -> None:
    """词面一路也走归一化，否则患者说「流鼻涕」永远匹配不上文件里的「流涕」。"""
    assert retrieval._ngrams("流鼻涕") == ["流涕"]


def test_search_returns_at_most_k_and_only_clinical_chunks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    index = retrieval.Index()
    # 稠密一路打平，排序由词面一路决定，测试因此不依赖网络
    monkeypatch.setattr(
        retrieval,
        "_query_vector",
        lambda _: np.zeros(index._vectors.shape[1], dtype=np.float32),
    )

    passages = index.search("腹泻", k=3)

    assert len(passages) == 3
    for passage in passages:
        assert index._rows[passage.chunk_id]["role"] == "clinical"


def test_partial_tail_line_does_not_break_resume(tmp_path: object) -> None:
    """进程被强杀时最后一行可能是半截，续跑要跳过它而不是整轮崩掉。"""
    import json
    from pathlib import Path

    from tools import run_matrix

    path = Path(str(tmp_path)) / "run.jsonl"
    path.write_text(
        json.dumps({"unit_id": "c1-V1-A0-m-r1"}) + "\n" + '{"unit_id": "c1-V2-A0-m',
        encoding="utf-8",
    )

    assert run_matrix._done(path) == {"c1-V1-A0-m-r1"}
