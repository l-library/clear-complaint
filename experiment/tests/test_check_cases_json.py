import json
from pathlib import Path

from tools import check_cases


def test_broken_line_does_not_abort_the_whole_review(tmp_path: Path) -> None:
    """审稿工具最常见的输入就是手改出的语法错误，不能因此整轮崩掉。"""
    good = {
        "case_id": "X01",
        "domain": "呼吸道症状",
        "variants": {
            "V1": "流鼻涕三天了",
            "V2": "我好像感冒了，流鼻涕三天",
            "V3": "很担心，流鼻涕三天了",
            "V4": "流鼻涕",
            "V5": "liu鼻涕三天了",
        },
        "gold": {"triage": "clinic", "department": "呼吸内科", "red_flags": []},
    }
    path = tmp_path / "cases.jsonl"
    path.write_text(
        json.dumps(good, ensure_ascii=False) + "\n" + '{"case_id": "X02", "gold": "triage": {}\n',
        encoding="utf-8",
    )

    rows: list[dict[str, object]] = []
    broken = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            broken += 1

    assert len(rows) == 1
    assert broken == 1
    assert check_cases._issues(rows[0]) == []


def test_trailing_question_counts_as_self_diagnosis() -> None:
    """把病名挂在句尾问出来也是自我归因，不该被判成「没改到点子上」。"""
    row = {
        "case_id": "X03",
        "domain": "发热待查",
        "variants": {
            "V1": "发热两天，咽痛乏力",
            "V2": "发热两天，最高三十八度五，咽痛乏力，是不是流感啊",
            "V3": "有点担心，发热两天了，会不会是肺炎",
            "V4": "发热",
            "V5": "fa热两天，咽tong乏力",
        },
        "gold": {"triage": "self_observe", "department": "全科医学科", "red_flags": []},
    }

    assert check_cases._issues(row) == []
