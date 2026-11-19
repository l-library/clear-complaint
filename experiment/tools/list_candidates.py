"""只做发现：把候选文件列成下载清单，不打开正文页。

正文页要过卫健委的瑞数防护，连续自动化请求会被升级拦截，所以清单这一步只碰
站点搜索接口（拓尔思 kaipuyun），把「标题 + URL」落成一个人可点的清单。下载由人
在浏览器里完成，PDF 放进 corpus/raw/，之后的分片与统计全部离线，不依赖反爬。

用法：uv run python -m tools.list_candidates
"""

from __future__ import annotations

import json
from pathlib import Path

from tools import nhc

CORPUS = Path(__file__).resolve().parent.parent / "corpus"


def main() -> int:
    hits = nhc.candidates()
    if not hits:
        print("[error] 没拿到候选，先确认 tools.nhc.search 还能通")
        return 1
    hits = sorted(hits, key=lambda hit: hit.title)
    CORPUS.mkdir(parents=True, exist_ok=True)
    (CORPUS / "nhc_candidates.json").write_text(
        json.dumps([{"title": h.title, "url": h.url} for h in hits], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    lines = [
        "# 语料下载清单",
        "",
        "来源：国家卫生健康委官网（政务公开主动公开内容）。这些文件属国家机关发布的",
        "行政性质文件，《著作权法》第五条不适用于它们，因此可以入库分发，"
        "这是「材料里的数字能被评委复现」的前提。",
        "",
        "正文页有瑞数动态防护，脚本连续抓取会被升级拦截，所以由人在浏览器里点开下载，"
        "PDF 放到 `corpus/raw/`，文件名保持清单里的建议名。分片与统计全部离线跑，不碰网络。",
        "",
        "| # | 标题（搜索页给的可能被截断，以打开后的页面标题为准） | 链接 |",
        "| --- | --- | --- |",
    ]
    for index, hit in enumerate(hits, 1):
        lines.append(f"| {index} | {hit.title} | <{hit.url}> |")
    (CORPUS / "download_list.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[info] 候选 {len(hits)} 条，清单写入 corpus/download_list.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
