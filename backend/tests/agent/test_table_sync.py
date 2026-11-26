"""#26 第 5 项：backend 与 experiment 两份冻结表不许悄悄漂移。

red_flags / vocab / departments 复制自 experiment 并约定「两边独立维护，
改动需同步版本号」。靠人记得就是漂移风险：这里按内容哈希钉死，任何一侧
单方面改动都会先在 CI 上炸出来。
"""

import hashlib
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
