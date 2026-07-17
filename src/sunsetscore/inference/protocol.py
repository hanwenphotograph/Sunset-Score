from __future__ import annotations

import base64
import json
from pathlib import Path

from ..errors import InferenceError
from .prompt import RESPONSE_SCHEMA
from .settings import MAX_GENERATED_TOKENS


def request_body(image: Path, prompt: str) -> bytes:
    try:
        encoded = base64.b64encode(image.read_bytes()).decode("ascii")
    except OSError as exc:
        raise InferenceError(f"无法读取标准化图片 {image}: {exc}") from exc
    payload = {
        "model": "local",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{encoded}"},
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        "temperature": 0,
        "top_k": 1,
        "top_p": 1,
        "seed": 0,
        "max_tokens": MAX_GENERATED_TOKENS,
        "stream": False,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "sunset_score",
                "strict": True,
                "schema": json.loads(RESPONSE_SCHEMA),
            },
        },
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )


def response_content(document: object) -> str:
    try:
        content = document["choices"][0]["message"]["content"]  # type: ignore[index]
    except (KeyError, IndexError, TypeError) as exc:
        raise InferenceError("本地推理服务返回了无效响应") from exc
    if not isinstance(content, str):
        raise InferenceError("本地推理服务没有返回文本内容")
    return content
