"""doc_titles 冻结表：文件名式来源换人文标题，未知值原样透传。"""

from app.agent import doc_titles


def test_known_filename_maps_to_human_title() -> None:
    assert doc_titles.display_name("1645425822651_51288.pdf") == "常见动物致伤诊疗规范"


def test_unknown_title_passes_through_unchanged() -> None:
    assert doc_titles.display_name("普通感冒规范诊治的专家共识") == "普通感冒规范诊治的专家共识"
    assert doc_titles.display_name("1645425891698_70530.docx") == "1645425891698_70530.docx"
    assert doc_titles.display_name("") == ""
