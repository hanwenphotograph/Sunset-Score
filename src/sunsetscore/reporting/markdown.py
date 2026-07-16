from __future__ import annotations

import os
from pathlib import Path

from ..errors import ReportError
from ..results import DirectoryScoreResult, IndependentScoreResult


def write_markdown_report(
    result: IndependentScoreResult,
    output_directory: Path,
    *,
    filename_timestamp: str,
) -> Path:
    path = _available_path(output_directory, filename_timestamp)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(build_markdown_report(result), encoding="utf-8")
        os.replace(temporary, path)
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise ReportError(f"无法生成分析报告 {path}: {exc}") from exc
    return path


def build_markdown_report(result: IndependentScoreResult) -> str:
    lines = [
        "# SunsetScore 独立目录分析报告",
        "",
        f"- 输入目录：`{_escape_code(result.root_directory)}`",
        f"- 生成时间：`{result.generated_at}`",
        f"- 评分模型：`{_escape_code(result.model_version)}`",
        f"- 推理后端：`{_escape_code(result.inference_backend.upper())}`",
        f"- 推理设备：`{_escape_code(result.inference_device)}`",
        f"- 成功目录：`{result.successful_directory_count}`",
        f"- 失败目录：`{result.failed_directory_count}`",
        "",
        "## 目录汇总",
        "",
        (
            "| 子目录 | 图片数 | 采样数 | 成功样本 | 失败样本 | "
            "采样间隔 | 平均分 | 最高分 | 状态 |"
        ),
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    lines.extend(_table_row(item) for item in result.directories)

    failures = [item for item in result.directories if not item.succeeded]
    if failures:
        lines.extend(["", "## 失败详情", ""])
        lines.extend(
            f"- `{_escape_code(item.directory)}`：{item.error}" for item in failures
        )

    lines.extend(
        [
            "",
            "## 说明",
            "",
            "每个后代目录只分析其直接包含的受支持图片，输入根目录中的图片不参与独立分析。",
            "",
        ]
    )
    return "\n".join(lines)


def _table_row(item: DirectoryScoreResult) -> str:
    average = f"{item.average_score:.2f}" if item.average_score is not None else "-"
    maximum = str(item.max_score) if item.max_score is not None else "-"
    interval = str(item.interval) if item.interval is not None else "-"
    status = "成功" if item.succeeded else f"失败：{item.error}"
    values = (
        item.directory,
        str(item.image_count),
        str(item.sampled_count),
        str(item.successful_count),
        str(item.failed_count),
        interval,
        average,
        maximum,
        status,
    )
    return "| " + " | ".join(_escape_cell(value) for value in values) + " |"


def _available_path(directory: Path, timestamp: str) -> Path:
    base = directory / f"sunsetscore-analysis-{timestamp}.md"
    if not base.exists():
        return base
    number = 2
    while True:
        candidate = directory / f"sunsetscore-analysis-{timestamp}-{number}.md"
        if not candidate.exists():
            return candidate
        number += 1


def _escape_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def _escape_code(value: str) -> str:
    return value.replace("`", "\\`")
