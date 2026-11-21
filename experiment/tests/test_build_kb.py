from pathlib import Path

from tools import build_kb

KB = Path(__file__).resolve().parent.parent / "corpus" / "kb"


def test_filename_strips_official_boilerplate() -> None:
    name = build_kb.filename_for(
        "国家卫生健康委办公厅关于印发流行性感冒诊疗方案（2025年版）的通知",
        "govcn-关于印发流行性感冒诊疗方案-2025年版-的通知",
    )

    assert name == "流行性感冒诊疗方案（2025年版）"


def test_filename_drops_attachment_number() -> None:
    assert build_kb.filename_for("附件 11 水痘诊疗方案", "17340030xxxx") == "水痘诊疗方案"


def test_unreadable_title_falls_back_to_slug() -> None:
    """兜底名也必须可读：宁可保留原文件名，也不要空名字。"""
    assert build_kb.filename_for("附件 1", "1645425789350_85133") == "1645425789350_85133"


def test_title_evidence_beats_keyword_cooccurrence() -> None:
    """流感的高危人群一节提到高血压，不该因此被标成慢病随访。"""
    tags = build_kb.tags_for("流行性感冒诊疗方案（2025年版）", {"慢病随访"})

    assert tags == ["呼吸道症状"]


def test_keyword_tags_are_only_a_fallback() -> None:
    assert build_kb.tags_for("未收录的病名", {"发热待查"}) == ["发热待查"]
    assert build_kb.tags_for("未收录的病名", set()) == ["未标注"]


def test_exported_filenames_are_readable_and_unique() -> None:
    files = sorted(path.name for path in KB.glob("*.txt"))

    assert len(files) >= 50
    assert len(files) == len(set(files))
    # 数字开头的名字在引用里会直接露给用户
    assert not [name for name in files if name[0].isdigit()]


def test_manifest_covers_every_exported_file() -> None:
    import csv

    rows = list(csv.DictReader((KB / "kb_manifest.csv").open(encoding="utf-8")))
    listed = {row["文件名"] for row in rows}
    exported = {path.name for path in KB.glob("*.txt")}

    assert listed == exported
    for row in rows:
        assert row["来源"], row["文件名"]
