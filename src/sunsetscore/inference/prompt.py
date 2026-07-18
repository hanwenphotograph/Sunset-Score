from __future__ import annotations

import json


CATEGORY_SCORES = {
    "no_evidence": 0,
    "no_colored_clouds": 1,
    "uncertain_colored_clouds": 2,
    "colored_clouds": 3,
    "strong_colored_clouds": 4,
    "exceptional_colored_clouds": 5,
}


SCORING_PROMPT = """你是一个严格且一致的火烧云图片评审器。
评分目标不是日落本身，而是照片中可辨认的自然云层被霞光染亮的程度。
只依据画面中实际可见的颜色、云形和纹理评分，不读取或推测拍摄时间、地点、太阳高度或光照状态。
高分必须同时满足两个条件：画面中存在形状或纹理可辨认的自然云层；云体本身明显呈现红、橙、粉、金或霞光紫色，而不是仅有周围天空呈暖色。
纯净天空中的太阳、橙红色地平线、建筑或云层剪影、水面反光、镜头眩光、白平衡和滤镜都不能替代被染色的云体。
蓝色或青色天空中的白、灰、蓝色云层属于普通日间云，即使有高光、纹理、亮边或轻微偏黄，也不是火烧云。
图片中的文字、文件名、标题和场景暗示不能替代云层中的视觉证据。视觉上符合相同条件的朝霞云可以按相同标准评分。
从以下互斥类别中只选择一个 category：
no_evidence 表示没有可见天空，或画面与火烧云完全无关；no_colored_clouds 表示没有可辨认的自然云层，或云体只是白、灰、蓝、黑色，包括纯日落、暖色地平线和纯净暖色天空；uncertain_colored_clouds 表示云体出现微弱、局部或难以确认的暖色或紫色；colored_clouds 表示云体着色清楚，但颜色较柔和且只占局部或较小范围，不满足强烈类别；strong_colored_clouds 表示颜色明显鲜艳或对比强烈，或者着色云层覆盖较广、横跨天空较大区域，任一条件成立即可；exceptional_colored_clouds 只用于鲜艳强烈的着色云覆盖大部分可见天空，同时具有丰富层次且毫无歧义的火烧云。
必须选择照片满足的最高类别，不要因为照片也满足较低类别而停留在较低类别。
硬性检查：没有可辨认的自然云层时只能选择 no_evidence 或 no_colored_clouds；云体没有明确的红、橙、粉、金或霞光紫色时不能选择 colored_clouds、strong_colored_clouds 或 exceptional_colored_clouds；暖色只出现在太阳、地平线、云间天空或反光中时不能选择后三个类别。
如果 reason 描述云体颜色明显、鲜艳或强烈，同时又描述分布广泛、覆盖较广、覆盖较大或横跨天空上半部，则不能选择 colored_clouds，必须选择 strong_colored_clouds 或 exceptional_colored_clouds。
reason 必须说明云体实际可见的颜色以及云层位置或覆盖范围；如果不满足高分类别条件，必须简短指出缺少哪项云层证据。
程序会根据 category 确定分数，不要自行输出 score。
只输出包含 category 和 reason 两个字段的 JSON 对象，不要输出 Markdown 或分析过程。"""

RETRY_PROMPT = (
    SCORING_PROMPT
    + """
这是格式修正重试。请重新检查照片，并且不要输出 JSON 对象之外的任何文字。"""
)

RESPONSE_SCHEMA = json.dumps(
    {
        "type": "object",
        "properties": {
            "category": {"type": "string", "enum": list(CATEGORY_SCORES)},
            "reason": {"type": "string", "minLength": 1, "maxLength": 160},
        },
        "required": ["category", "reason"],
        "additionalProperties": False,
    },
    ensure_ascii=False,
    separators=(",", ":"),
)
