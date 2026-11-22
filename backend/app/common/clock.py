"""时间约定：全项目 Asia/Shanghai，出参统一 yyyy-MM-dd HH:mm:ss。

数据库列是 TIMESTAMPTZ（存 UTC），换算和格式化只在这里做，路由与业务层不自己算。
"""

from datetime import datetime
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo("Asia/Shanghai")


def now_shanghai() -> datetime:
    return datetime.now(SHANGHAI)


def format_shanghai(moment: datetime) -> str:
    return moment.astimezone(SHANGHAI).strftime("%Y-%m-%d %H:%M:%S")
