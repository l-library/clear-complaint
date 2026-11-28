"""#26 第 5 项：backend 与 experiment 两份冻结表不许悄悄漂移。

red_flags / vocab / departments 复制自 experiment 并约定「两边独立维护，
改动需同步版本号」。靠人记得就是漂移风险：这里按内容哈希钉死，任何一侧
单方面改动都会先在 CI 上炸出来。

doc_titles 无 experiment 侧同文件（来源是 corpus/manifest.json，experiment
不改动），按 test_normalize_parity 的先例改为语义钉死：从 manifest 重新推
导一遍映射，与 backend 表逐条比对。
"""

import hashlib
import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
TABLES = ("red_flags.json", "vocab.json", "departments.json")


@pytest.mark.parametrize("name", TABLES)
def test_frozen_tables_match_experiment(name: str) -> None:
    backend = (REPO_ROOT / "backend" / "app" / "agent" / "data" / name).read_bytes()
    experiment = (REPO_ROOT / "experiment" / "corpus" / name).read_bytes()

    assert hashlib.sha256(backend).hexdigest() == hashlib.sha256(experiment).hexdigest(), (
        f"{name} 在两个项目间已经漂移：按约定先同步版本号并让两边内容一致，再动任何一侧"
    )


def test_doc_titles_match_experiment_manifest() -> None:
    """doc_titles.json 钉死到 corpus/manifest.json：文件名式 source → title。

    推导规则与建表时一致：source 不含汉字（文件名式来源）且 title 非空。
    任一侧改动（manifest 换名、backend 改映射）都会在此炸出。
    """
    manifest = json.loads((REPO_ROOT / "experiment" / "corpus" / "manifest.json").read_text())
    expected = {
        row["source"]: row["title"]
        for row in manifest
        if re.search(r"[\u4e00-\u9fff]", row["source"]) is None and row["title"]
    }
    payload = json.loads(
        (REPO_ROOT / "backend" / "app" / "agent" / "data" / "doc_titles.json").read_text()
    )

    assert payload["version"] == 1
    assert payload["titles"] == expected, (
        "doc_titles.json 与 experiment/corpus/manifest.json 已经漂移："
        "按推导规则（文件名式 source、title 非空）重新生成并同步版本号"
    )
