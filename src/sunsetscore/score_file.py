from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path

from .errors import ScoreFileError
from .log import logger
from .results import DirectoryScoreResult, SampleScore
from .score_file_schema import (
    SCORE_FORMAT_VERSION,
    StoredDirectoryScore,
    parse_score_document,
)
from .version import __version__


SCORE_FILENAME = ".sunsetscore-score.json"


def read_score_file(
    directory: Path,
    *,
    directory_label: str,
    recursive: bool,
) -> StoredDirectoryScore | None:
    path = directory / SCORE_FILENAME
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        stored = parse_score_document(document, directory_label)
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
    sample_scores: tuple[SampleScore, ...],
) -> Path:
    path = directory / SCORE_FILENAME
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    document = {
        "format_version": SCORE_FORMAT_VERSION,
        "application_version": __version__,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "model_version": model_version,
        "inference_backend": inference_backend,
        "inference_device": inference_device,
        "recursive": recursive,
        "result": result.to_dict(),
        "sample_scores": [sample.to_dict() for sample in sample_scores],
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


def _remove_temporary_file(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("无法清理评分临时文件 %s：%s", path, exc)
