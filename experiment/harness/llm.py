"""MaaS 的 OpenAI 兼容对话客户端。

四个实测事实写在这里，省得下次再踩：

1. 对话接口在 `/openai/v1`，向量化在 `/v1`，同一个 key。
2. `deepseek-v4.1-flash`（不带日期）返回 403 无权限，可用的是 `deepseek-v4.1-flash-1017`。
3. `glm-5.3` 在本账号下会把 4096 的预算全部花在 reasoning 上，`content` 返回空串、
   耗时约 58 秒，因此不适合进矩阵；`glm-5.2` 在同样预算下能正常出 JSON。
4. GLM 与盘古都是推理模型，`reasoning_tokens` 会占掉大半预算。记录里单独存它，
   解析失败按 parse_error 计，不重跑——输出不稳定本身就是结论的一部分。
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

# 同济校园网关（OneAPI 部署）。实测单次 4 秒左右，比 MaaS 快一个量级。
# 注意：网关标称与背后部署可能不一致（DeepSeek-V4.1-Flash 自称 ChatGPT），
# 材料里按网关标称写。
DEFAULT_BASE_URL = "https://agi.tongji.edu.cn/v1"
# 异构配对的判据是「不同厂商 + 能在可接受预算内出合法 JSON」。
# 华为 MaaS 上的旧配对是 deepseek-v4.1-flash-1017 与 glm-5.2，因账号资源
# 冻结（403 ModelArts.81006）与费用问题切换到同济网关。GLM 的 Flash 版
# 不是推理吞预算型，4096 内工作正常。
BENCH = ("DeepSeek-V4.1-Flash", "GLM-5.3-Flash")

TEMPERATURE = 0.7
TOP_P = 1.0
# 4096 不够：deepseek 在同一提示词下 reasoning 会顶到 4022，JSON 被截断成 parse_error。
# 全量跑到 394 格时 15 个 parse_error 全是这个原因，所以抬到 8192。
MAX_TOKENS = 8192


class LLMError(RuntimeError):
    def __init__(self, message: str, status: int = 0) -> None:
        self.status = status
        super().__init__(message)


@dataclass(frozen=True)
class Completion:
    content: str
    reasoning_tokens: int
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int


def _config() -> tuple[str, str]:
    base = os.environ.get("LLM_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    key = (
        os.environ.get("LLM_API_KEY")
        or os.environ.get("TJU_API_KEY")
        or os.environ.get("MAAS_API_KEY")
        or os.environ.get("HUAWEI_MAAS_API_KEY", "")
    )
    if not key:
        raise LLMError("缺少 LLM_API_KEY / TJU_API_KEY / HUAWEI_MAAS_API_KEY")
    return base, key


def chat(
    model: str,
    messages: list[dict[str, str]],
    *,
    max_tokens: int = MAX_TOKENS,
    temperature: float = TEMPERATURE,
    top_p: float = TOP_P,
    retries: int = 6,
) -> Completion:
    """一次调用。4xx 直接抛出（参数或权限问题重试无意义），5xx 与超时重试。"""
    base, key = _config()
    body = json.dumps(
        {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
        }
    ).encode()
    started = time.monotonic()
    last: Exception | None = None
    for attempt in range(retries + 1):
        request = urllib.request.Request(
            f"{base}/chat/completions",
            data=body,
            method="POST",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=240) as response:
                payload = json.loads(response.read().decode("utf-8"))
            usage = payload.get("usage") or {}
            details = usage.get("completion_tokens_details") or {}
            message = payload["choices"][0]["message"] or {}
            return Completion(
                content=str(message.get("content") or ""),
                reasoning_tokens=int(details.get("reasoning_tokens") or 0),
                prompt_tokens=int(usage.get("prompt_tokens") or 0),
                completion_tokens=int(usage.get("completion_tokens") or 0),
                latency_ms=int((time.monotonic() - started) * 1000),
            )
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "ignore")[:200]
            # 429 是网关的吞吐限流（短探针不撞、连续全量才撞），指数退避重试
            if exc.code == 429 or exc.code >= 500:
                last = exc
                time.sleep(min(60, 10 * (2**attempt)))
                continue
            if exc.code < 500:
                raise LLMError(f"{model} 调用失败 {exc.code}: {detail}", exc.code) from exc
            last = exc
            time.sleep(2 * (attempt + 1))
        except Exception as exc:  # noqa: BLE001 - 网络层错误重试
            last = exc
            time.sleep(2 * (attempt + 1))
    raise LLMError(f"{model} 调用失败: {last}")
