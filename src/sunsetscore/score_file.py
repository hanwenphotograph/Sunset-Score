from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
from typing import Any

from .errors import ScoreFileError
from .log import logger
from .results import DirectoryScoreResult


SCORE_FILENAME = ".sunsetscore-score.json"
SCORE_FORMAT_VERSION = 1


@dataclass(frozen=True, slots=True)
class StoredDirectoryScore:
    result: DirectoryScoreResult
    generated_at: str
    model_version: str
    inference_backend: str
    inference_device: str
    recursive: bool


def read_score_file(
    directory: Path,
    *,
    directory_label: str,
    recursive: bool,
) -> StoredDirectoryScore | None:
    path = directory / SCORE_FILENAME
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        stored = _parse_document(document, directory_label)
    except FileNotFoundError:
        return None
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        logger.warning("忽略无效评分文件 %s：%s", path, exc)
        return None

    if stored.recursive != recursive:
        logger.info("评分文件扫描范围不匹配，将重新评分：%s", path)
        return None
    logger.info("已读取评分文件，跳过评分：%s", path)
    return stored


def write_score_file(
    directory: Path,
    result: DirectoryScoreResult,
    *,
    model_version: str,
    inference_backend: str,
    inference_device: str,
    recursive: bool,
) -> Path:
    path = directory / SCORE_FILENAME
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    document = {
        "format_version": SCORE_FORMAT_VERSION,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "model_version": model_version,
        "inference_backend": inference_backend,
        "inference_device": inference_device,
        "recursive": recursive,
        "result": result.to_dict(),
    }
    try:
        content = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
        temporary.write_text(content, encoding="utf-8")
        os.replace(temporary, path)
    except (OSError, TypeError, ValueError) as exc:
        raise ScoreFileError(f"无法生成评分文件 {path}: {exc}") from exc
    finally:
        _remove_temporary_file(temporary)
    logger.info("评分文件：%s", path)
    return path


def _parse_document(document: Any, directory_label: str) -> StoredDirectoryScore:
    root = _mapping(document, "评分文件")
    version = root.get("format_version")
    if type(version) is not int or version != SCORE_FORMAT_VERSION:
        raise ValueError("不支持的格式版本")
    result_data = _mapping(root.get("result"), "result")
    _text(result_data.get("directory"), "directory")
    if result_data.get("error") is not None:
        raise ValueError("评分文件不能包含失败结果")
    result = DirectoryScoreResult(
        directory=directory_label,
        image_count=_integer(result_data.get("image_count"), "image_count", 0),
        sampled_count=_integer(result_data.get("sampled_count"), "sampled_count", 0),
        successful_count=_integer(
            result_data.get("successful_count"), "successful_count", 1
        ),
        failed_count=_integer(result_data.get("failed_count"), "failed_count", 0),
        interval=_integer(result_data.get("interval"), "interval", 1),
        inference_workers=_integer(
            result_data.get("inference_workers"), "inference_workers", 1
        ),
        average_score=_number(
            result_data.get("average_score"), "average_score", 0, 100
        ),
        max_score=_integer(result_data.get("max_score"), "max_score", 0, 100),
    )
    if result.sampled_count != result.successful_count + result.failed_count:
        raise ValueError("sampled_count 与成功、失败样本数不一致")
    if result.image_count < result.sampled_count:
        raise ValueError("image_count 不能小于 sampled_count")
    recursive = root.get("recursive")
    if type(recursive) is not bool:
        raise ValueError("recursive 必须是布尔值")
    return StoredDirectoryScore(
        result=result,
        generated_at=_text(root.get("generated_at"), "generated_at"),
        model_version=_text(root.get("model_version"), "model_version"),
        inference_backend=_text(root.get("inference_backend"), "inference_backend"),
        inference_device=_text(root.get("inference_device"), "inference_device"),
        recursive=recursive,
    )


def _mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} 必须是对象")
    return value


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} 必须是非空字符串")
    return value


def _integer(value: Any, name: str, minimum: int, maximum: int | None = None) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} 必须是大于等于 {minimum} 的整数")
    if maximum is not None and value > maximum:
        raise ValueError(f"{name} 必须小于等于 {maximum}")
    return value


def _number(
    value: Any,
    name: str,
    minimum: float,
    maximum: float,
) -> float:
    if type(value) not in (int, float) or not minimum <= value <= maximum:
        raise ValueError(f"{name} 必须是 {minimum:g} 到 {maximum:g} 之间的数字")
    return float(value)


def _remove_temporary_file(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("无法清理评分临时文件 %s：%s", path, exc)
