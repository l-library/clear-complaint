"""合成手表数据生成器（docs/api-agentarts.md 16.8.3）。

只造数据，绝不读任何真实患者数据：种子取（用户 ID，日期），同一天同一个人
重复生成结果逐字节相同，重算日报时才不会因为数据抖动而改写结论。

缺失指标一律写 null，不用 0 顶替——0 步是真实可能值，与「没采到」在契约里
语义不同（16.8.3：暂时没有的数据传 null 或省略，不能用 0 充当缺失）。
"""

import hashlib
import random
from datetime import date

DATA_SOURCE = "mock"
DEVICE_ID_PREFIX = "MOCK-WATCH"

# 16.8.3 的 25 项指标键，顺序照文档表格；集合本身在 test_mock_watch 里对齐文档
METRIC_KEYS = (
    "hr",
    "rhr",
    "hrv",
    "spo2",
    "blood_pressure",
    "ecg",
    "respiratory_rate",
    "skin_temperature",
    "sleep_duration",
    "deep_sleep",
    "light_sleep",
    "rem_sleep",
    "awakenings",
    "steps",
    "distance",
    "calories_burned",
    "exercise_duration",
    "activity_type",
    "activity_intensity",
    "vo2_max",
    "hrr",
    "stress_level",
    "fall_detection",
    "recovery_score",
    "menstrual_cycle",
)

# 每天至少可用的五项，与 16.8.6 已跑通的简版用例同构
_CORE_KEYS = ("steps", "exercise_duration", "sleep_duration", "rhr", "activity_type")
# 额外可用项的候选池：有的日子多几项，有的日子只有核心五项
_OPTIONAL_KEYS = (
    "distance",
    "calories_burned",
    "hrv",
    "spo2",
    "stress_level",
    "deep_sleep",
    "light_sleep",
    "rem_sleep",
    "awakenings",
    "respiratory_rate",
    "skin_temperature",
    "recovery_score",
)

_ACTIVITY_TYPES = ("walking", "running", "cycling", "strength", "none")


def _seed(user_id: int, report_date: date) -> int:
    digest = hashlib.sha256(f"daily-watch:{user_id}:{report_date.isoformat()}".encode())
    return int.from_bytes(digest.digest()[:8], "big")


def _plain(value: int | float, unit: str) -> dict[str, object]:
    return {"value": value, "unit": unit, "quality": "usable"}


def _metric(rng: random.Random, key: str) -> dict[str, object]:
    """按 16.8.3 的字段口径造一项可用指标；取值范围只保证合理，不表达健康判断。"""
    match key:
        case "steps":
            return _plain(rng.randrange(1200, 9000, 50), "count")
        case "exercise_duration":
            return _plain(rng.randrange(5, 60, 5), "min")
        case "sleep_duration":
            return _plain(rng.randrange(300, 520, 5), "min")
        case "rhr":
            return _plain(rng.randrange(52, 79), "bpm")
        case "activity_type":
            return {
                "value": _ACTIVITY_TYPES[rng.randrange(len(_ACTIVITY_TYPES))],
                "quality": "usable",
            }
        case "distance":
            return _plain(round(rng.uniform(1.0, 8.0), 1), "km")
        case "calories_burned":
            return _plain(rng.randrange(1500, 2600, 10), "kcal")
        case "hrv":
            return {**_plain(rng.randrange(20, 71), "ms"), "method": "RMSSD"}
        case "spo2":
            return _plain(rng.randrange(95, 100), "%")
        case "stress_level":
            return {**_plain(rng.randrange(10, 80), "score"), "scale_min": 0, "scale_max": 100}
        case "deep_sleep":
            return _plain(rng.randrange(45, 120, 5), "min")
        case "light_sleep":
            return _plain(rng.randrange(120, 280, 5), "min")
        case "rem_sleep":
            return _plain(rng.randrange(40, 120, 5), "min")
        case "awakenings":
            # 合成数据不产生 0 值观测，免得「真实 0」与「缺失」在测试与前端里混淆
            return _plain(rng.randrange(1, 5), "count")
        case "respiratory_rate":
            return _plain(rng.randrange(12, 21), "breaths/min")
        case "skin_temperature":
            return _plain(round(rng.uniform(31.0, 35.0), 1), "C")
        case "recovery_score":
            return {**_plain(rng.randrange(30, 90), "score"), "scale_min": 0, "scale_max": 100}
    raise ValueError(f"未定义的合成指标: {key}")


def build_watch_data(user_id: int, report_date: date) -> dict[str, object]:
    """返回 16.8.3 的 watch_data 对象：25 项键齐全，当天采到的有值、其余为 null。"""
    rng = random.Random(_seed(user_id, report_date))
    available = set(_CORE_KEYS)
    extras = rng.sample(_OPTIONAL_KEYS, rng.randrange(0, 4))
    available.update(extras)
    metrics: dict[str, object] = {
        key: _metric(rng, key) if key in available else None for key in METRIC_KEYS
    }
    return {
        "date": report_date.isoformat(),
        "wear_minutes": rng.randrange(720, 1441, 5),
        "device": {
            "id": f"{DEVICE_ID_PREFIX}-{user_id:03d}",
            "brand": "Synthetic",
            "model": "Demo",
        },
        "metrics": metrics,
    }
