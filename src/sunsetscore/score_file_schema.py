from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .aggregation import summarize_scores
from .results import DirectoryScoreResult, SampleScore, SunsetRange
from .version import __version__


SCORE_FORMAT_VERSION = 3


@dataclass(frozen=True, slots=True)
class StoredDirectoryScore:
    result: DirectoryScoreResult
    sample_scores: tuple[SampleScore, ...]
    generated_at: str
    model_version: str
    inference_backend: str
    inference_device: str
    recursive: bool


def parse_score_document(document: Any, directory_label: str) -> StoredDirectoryScore:
    root = _mapping(document, "评分文件")
    _require_version(root)
    result_data = _mapping(root.get("result"), "result")
    sample_scores = _sample_scores(root.get("sample_scores"))
    result = _result(result_data, directory_label)
    _validate_result(result, sample_scores)
    recursive = root.get("recursive")
    if type(recursive) is not bool:
        raise ValueError("recursive 必须是布尔值")
    return StoredDirectoryScore(
        result=result,
        sample_scores=sample_scores,
        generated_at=_text(root.get("generated_at"), "generated_at"),
        model_version=_text(root.get("model_version"), "model_version"),
        inference_backend=_text(root.get("inference_backend"), "inference_backend"),
        inference_device=_text(root.get("inference_device"), "inference_device"),
        recursive=recursive,
    )


def _require_version(root: dict[str, Any]) -> None:
    version = root.get("format_version")
    if type(version) is not int or version != SCORE_FORMAT_VERSION:
        raise ValueError("不支持的评分文件格式版本")
    application_version = root.get("application_version")
    if application_version != __version__:
        raise ValueError(
            f"评分文件应用版本 {application_version!r} 与当前版本 {__version__!r} 不一致"
        )


def _result(data: dict[str, Any], directory_label: str) -> DirectoryScoreResult:
    _text(data.get("directory"), "directory")
    if data.get("error") is not None:
        raise ValueError("评分文件不能包含失败结果")
    return DirectoryScoreResult(
        directory=directory_label,
        image_count=_integer(data.get("image_count"), "image_count", 0),
        sampled_count=_integer(data.get("sampled_count"), "sampled_count", 1),
        successful_count=_integer(data.get("successful_count"), "successful_count", 1),
        failed_count=_integer(data.get("failed_count"), "failed_count", 0),
        interval=_integer(data.get("interval"), "interval", 1),
        inference_workers=_integer(data.get("inference_workers"), "inference_workers", 1),
        average_score=_number(data.get("average_score"), "average_score"),
        max_score=_integer(data.get("max_score"), "max_score", 0, 5),
        has_sunset=_boolean(data.get("has_sunset"), "has_sunset"),
        sunset_ranges=_sunset_ranges(data.get("sunset_ranges")),
    )


def _sample_scores(value: Any) -> tuple[SampleScore, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError("sample_scores 必须是非空数组")
    samples = tuple(_sample_score(item) for item in value)
    indexes = [sample.sample_index for sample in samples]
    if indexes != sorted(set(indexes)):
        raise ValueError("sample_scores 必须按不重复的 sample_index 排序")
    return samples


def _sample_score(value: Any) -> SampleScore:
    data = _mapping(value, "sample_score")
    return SampleScore(
        sample_index=_integer(data.get("sample_index"), "sample_index", 1),
        photo=_text(data.get("photo"), "photo"),
        score=_integer(data.get("score"), "score", 0, 5),
        reason=_text(data.get("reason"), "reason"),
    )


def _sunset_ranges(value: Any) -> tuple[SunsetRange, ...]:
    if not isinstance(value, list):
        raise ValueError("sunset_ranges 必须是数组")
    return tuple(_sunset_range(item) for item in value)


def _sunset_range(value: Any) -> SunsetRange:
    data = _mapping(value, "sunset_range")
    return SunsetRange(
        start_photo=_text(data.get("start_photo"), "start_photo"),
        end_photo=_text(data.get("end_photo"), "end_photo"),
    )


def _validate_result(
    result: DirectoryScoreResult,
    samples: tuple[SampleScore, ...],
) -> None:
    if result.sampled_count != result.successful_count + result.failed_count:
        raise ValueError("sampled_count 与成功、失败样本数不一致")
    if result.image_count < result.sampled_count:
        raise ValueError("image_count 不能小于 sampled_count")
    if result.successful_count != len(samples):
        raise ValueError("successful_count 与 sample_scores 数量不一致")
    if samples[-1].sample_index > result.sampled_count:
        raise ValueError("sample_index 不能超过 sampled_count")
    summary = summarize_scores(samples, sampled_count=result.sampled_count)
    expected = (
        summary.average_score,
        summary.max_score,
        summary.has_sunset,
        summary.sunset_ranges,
    )
    actual = (
        result.average_score,
        result.max_score,
        result.has_sunset,
        result.sunset_ranges,
    )
    if actual != expected:
        raise ValueError("目录汇总结论与 sample_scores 不一致")


def _mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} 必须是对象")
    return value


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} 必须是非空字符串")
    return value


def _boolean(value: Any, name: str) -> bool:
    if type(value) is not bool:
        raise ValueError(f"{name} 必须是布尔值")
    return value


def _integer(value: Any, name: str, minimum: int, maximum: int | None = None) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} 必须是大于等于 {minimum} 的整数")
    if maximum is not None and value > maximum:
        raise ValueError(f"{name} 必须小于等于 {maximum}")
    return value


def _number(value: Any, name: str) -> float:
    if type(value) not in (int, float) or not 0 <= value <= 5:
        raise ValueError(f"{name} 必须是 0 到 5 之间的数字")
    return float(value)
