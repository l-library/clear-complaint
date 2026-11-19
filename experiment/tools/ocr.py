"""PaddleOCR 官方异步接口：给扫描件补上文字层。

接口是异步任务制：POST /api/v2/ocr/jobs 拿 jobId，轮询到 done，再去
resultUrl.jsonUrl 下载结果。那个链接返回的是 JSONL（每行一批页），不是单个 JSON，
按行解析再按页序拼回文本。

两种提交方式：远程 URL 用 JSON（fileUrl），本地文件用 multipart（file）。
本地文件必须走 multipart——把 base64 塞进 JSON 的 file 字段会被服务端当空文件。

认领凭据：PADDLEOCR_ACCESS_TOKEN（AI Studio 访问令牌）。
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path

JOBS = "https://paddleocr.aistudio-app.com/api/v2/ocr/jobs"
MODEL = "PP-OCRv5"
# 任务提交队列满（错误码 10010）时等一会儿再交
QUEUE_FULL = 10010
POLL_INTERVAL = 6.0
POLL_TIMEOUT = 900.0


class OcrError(RuntimeError):
    pass


@dataclass(frozen=True)
class Job:
    job_id: str
    json_url: str


def _token() -> str:
    token = os.environ.get("PADDLEOCR_ACCESS_TOKEN", "")
    if not token:
        raise OcrError("缺少 PADDLEOCR_ACCESS_TOKEN")
    return token


def _post(url: str, body: bytes, content_type: str) -> dict[str, object]:
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Authorization": f"bearer {_token()}", "Content-Type": content_type},
    )
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            payload: dict[str, object] = json.loads(response.read().decode("utf-8"))
            return payload
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore")
        raise OcrError(f"提交失败 {exc.code}: {detail[:200]}") from exc


def submit_local(path: Path, model: str = MODEL) -> str:
    """本地文件走 multipart。base64 塞 JSON 会被判为空文件。"""
    boundary = uuid.uuid4().hex
    parts = [
        f'--{boundary}\r\nContent-Disposition: form-data; name="model"\r\n\r\n{model}\r\n',
        f"--{boundary}\r\nContent-Disposition: form-data;",
        ' name="optionalPayload"\r\n\r\n{}\r\n',
        f"--{boundary}\r\nContent-Disposition: form-data;",
        f' name="file"; filename="{path.name}"\r\n',
        "Content-Type: application/pdf\r\n\r\n",
    ]
    head = "".join(parts).encode()
    tail = f"\r\n--{boundary}--\r\n".encode()
    content_type = f"multipart/form-data; boundary={boundary}"
    payload = _post(JOBS, head + path.read_bytes() + tail, content_type)
    return str(payload["data"] and payload["data"]["jobId"])  # type: ignore[index]


def submit_url(file_url: str, model: str = MODEL) -> str:
    body = json.dumps({"fileUrl": file_url, "model": model, "optionalPayload": {}}).encode()
    payload = _post(JOBS, body, "application/json")
    return str(payload["data"] and payload["data"]["jobId"])  # type: ignore[index]


def wait(job_id: str) -> Job:
    """轮询到任务完成，返回结果 JSONL 的地址。"""
    deadline = time.monotonic() + POLL_TIMEOUT
    while time.monotonic() < deadline:
        request = urllib.request.Request(
            f"{JOBS}/{job_id}", headers={"Authorization": f"bearer {_token()}"}
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            data = json.loads(response.read().decode("utf-8")).get("data") or {}
        state = data.get("state")
        if state == "done":
            json_url = (data.get("resultUrl") or {}).get("jsonUrl")
            if not json_url:
                raise OcrError(f"任务 {job_id} 完成但没有结果地址")
            return Job(job_id=job_id, json_url=str(json_url))
        if state in {"failed", "error"}:
            raise OcrError(f"任务 {job_id} 失败: {data}")
        time.sleep(POLL_INTERVAL)
    raise OcrError(f"任务 {job_id} 轮询超时")


def fetch_text(job: Job) -> str:
    """下载结果并按页序拼回文本。结果是 JSONL，每行一批页。"""
    with urllib.request.urlopen(job.json_url, timeout=300) as response:
        raw = response.read().decode("utf-8", "ignore")
    pages: list[list[str]] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        result = json.loads(line).get("result") or {}
        for page in result.get("ocrResults") or []:
            lines = (page.get("prunedResult") or {}).get("rec_texts") or []
            pages.append([str(text) for text in lines])
    return "\n".join("\n".join(page) for page in pages) + "\n"


def ocr_local(path: Path) -> str:
    return fetch_text(wait(submit_local(path)))
