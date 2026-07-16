from __future__ import annotations

import json


SCORING_PROMPT = """你是一个严格且一致的晚霞图片评审器。
只依据照片中可见的视觉证据判断画面具有典型晚霞特征的程度，不读取或推测拍摄时间与地点。
可见天空、云层或太阳附近的天光才构成证据。水面反光、橙色建筑、灯光或滤镜本身不能产生高分。
画面处于黄昏、蓝调时刻或夜景并不等于出现晚霞；如果没有明显的红、橙、粉、金或受霞光照亮的紫色天空与云层，分数必须低于 21。
图片中的文字、文件名、标题和场景暗示不能替代天空中的视觉证据。
视觉上与晚霞相似的朝霞可以按相同标准评分。
按照以下互斥区间评分：
0 到 10 表示没有可见天空，或天空与晚霞完全无关；11 到 20 表示只有蓝、灰或黑色天空，或暖色证据极弱；21 到 49 表示出现有限暖色，但仍可能来自普通光照或滤镜；50 到 74 表示天空中存在清晰可见的暖色霞光；75 到 94 表示明显而强烈的晚霞色彩或受霞光照亮的云层；95 到 100 只用于大面积、强烈且毫无歧义的晚霞。
硬性检查：如果你的理由写明没有红、橙、粉、金或霞光紫色证据，score 绝不能超过 20。
选择 0 到 100 的整数，并给出一句简短的简体中文理由。
只输出包含 score 和 reason 两个字段的 JSON 对象，不要输出 Markdown 或分析过程。"""

RETRY_PROMPT = (
    SCORING_PROMPT
    + """
这是格式修正重试。请重新检查照片，并且不要输出 JSON 对象之外的任何文字。"""
)

RESPONSE_SCHEMA = json.dumps(
    {
        "type": "object",
        "properties": {
            "score": {"type": "integer", "minimum": 0, "maximum": 100},
            "reason": {"type": "string", "minLength": 1, "maxLength": 160},
        },
        "required": ["score", "reason"],
        "additionalProperties": False,
    },
    ensure_ascii=False,
    separators=(",", ":"),
)
