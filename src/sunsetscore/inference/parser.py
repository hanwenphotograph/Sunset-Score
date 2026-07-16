from __future__ import annotations

import json

from ..errors import InferenceError
from ..results import PhotoScore


def parse_model_response(output: str) -> PhotoScore:
    decoder = json.JSONDecoder()
    candidates: list[dict[object, object]] = []
    for index, character in enumerate(output):
        if character != "{":
            continue
        try:
            value, _ = decoder.raw_decode(output, index)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            candidates.append(value)

    for candidate in reversed(candidates):
        score = candidate.get("score")
        reason = candidate.get("reason")
        if type(score) is not int or not 0 <= score <= 100:
            continue
        if not isinstance(reason, str):
            continue
        normalized_reason = " ".join(reason.split())
        if not normalized_reason or len(normalized_reason) > 200:
            continue
        return PhotoScore(score=score, reason=normalized_reason)

    raise InferenceError("模型没有返回有效的评分 JSON")
