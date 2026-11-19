from tools.fetch import split_clauses

GUIDELINE = """一、病原学
麻疹病毒为副黏病毒科麻疹病毒属，只有一个血清型，人是麻疹病毒的唯一宿主。

二、临床表现
（一）潜伏期。
潜伏期 7～21 天，一般为 10～14 天。
（二）前驱期。
主要表现为发热、流涕、咳嗽、流泪、畏光和斑丘疹等。

三、诊断
（一）诊断原则。
根据流行病学史、临床表现和实验室检测结果综合判断。

链接：全国人大 | 全国政协
版权所有：中国政府网
"""


def test_split_clauses_keeps_heading_path() -> None:
    clauses = split_clauses(GUIDELINE)

    headings = [clause.heading for clause in clauses]
    assert headings[0] == "一、病原学"
    assert "二、临床表现 / （二）前驱期。" in headings
    assert headings[-1] == "三、诊断 / （一）诊断原则。"


def test_split_clauses_drops_page_footer() -> None:
    joined = " ".join(clause.text for clause in split_clauses(GUIDELINE))

    assert "版权所有" not in joined
    assert "全国人大" not in joined


def test_split_clauses_keeps_clinical_text_verbatim() -> None:
    clauses = split_clauses(GUIDELINE)
    prodrome = next(clause for clause in clauses if "前驱期" in clause.heading)

    assert prodrome.text == "主要表现为发热、流涕、咳嗽、流泪、畏光和斑丘疹等。"
