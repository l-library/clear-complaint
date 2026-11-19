import json
from pathlib import Path

CORPUS = Path(__file__).resolve().parent.parent / "corpus"
MIN_CHARS, MAX_CHARS = 150, 400


def _chunks() -> list[dict[str, str]]:
    lines = (CORPUS / "chunks.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line]


def test_chunk_length_is_within_bounds() -> None:
    chunks = _chunks()

    assert chunks
    lengths = [len(chunk["text"]) for chunk in chunks]
    assert min(lengths) >= MIN_CHARS
    assert max(lengths) <= MAX_CHARS


def test_chunk_ids_are_unique_and_traceable() -> None:
    chunks = _chunks()
    ids = [chunk["chunk_id"] for chunk in chunks]

    assert len(ids) == len(set(ids))
    for chunk in chunks:
        assert chunk["chunk_id"].startswith(chunk["source"] + "#")


def test_chunks_carry_a_section_heading() -> None:
    """片段必须知道自己来自哪一节，引用时才能给出处。"""
    chunks = _chunks()
    with_heading = [chunk for chunk in chunks if chunk["heading"].strip()]

    assert len(with_heading) / len(chunks) > 0.95
