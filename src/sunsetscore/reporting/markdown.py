from __future__ import annotations

import os
from pathlib import Path

from ..errors import ReportError
from ..log import logger
from ..results import DirectoryScoreResult, IndependentScoreResult, SunsetRange


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
        raise ReportError(f"无法生成分析报告 {path}: {exc}") from exc
    finally:
        _remove_temporary_report(temporary)
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
        f"- 推理服务槽位：`{result.inference_workers}`",
        f"- GPU 显存限制：`{_memory_limit(result.gpu_memory_limit_gib)}`",
        f"- 成功目录：`{result.successful_directory_count}`",
        f"- 失败目录：`{result.failed_directory_count}`",
        "",
        "## 目录汇总",
        "",
        (
            "| 子目录 | 图片数 | 采样数 | 成功样本 | 失败样本 | "
            "采样间隔 | 推理槽位 | 平均分 | 最高分 | 晚霞 | 晚霞区间 | 状态 |"
        ),
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|:---:|---|---|",
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
    has_sunset = _sunset_label(item.has_sunset)
    sunset_ranges = _format_ranges(item.sunset_ranges)
    interval = str(item.interval) if item.interval is not None else "-"
    status = "成功" if item.succeeded else f"失败：{item.error}"
    values = (
        item.directory,
        str(item.image_count),
        str(item.sampled_count),
        str(item.successful_count),
        str(item.failed_count),
        interval,
        str(item.inference_workers),
        average,
        maximum,
        has_sunset,
        sunset_ranges,
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


def _memory_limit(value: float | None) -> str:
    return f"{value:g} GiB" if value is not None else "自动"


def _sunset_label(value: bool | None) -> str:
    if value is None:
        return "-"
    return "是" if value else "否"


def _format_ranges(ranges: tuple[SunsetRange, ...]) -> str:
    if not ranges:
        return "-"
    return "<br>".join(
        item.start_photo
        if item.start_photo == item.end_photo
        else f"{item.start_photo} 至 {item.end_photo}"
        for item in ranges
    )


def _remove_temporary_report(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("无法清理报告临时文件 %s：%s", path, exc)
