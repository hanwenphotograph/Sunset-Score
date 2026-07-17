from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import stat
import tempfile
from uuid import uuid4

from ..discovery import discover_images
from ..errors import AutopackError
from ..log import logger
from ..results import IndependentScoreResult, ScoreResult, SunsetRange
from .settings import OUTPUT_DIRECTORY_NAME


@dataclass(frozen=True, slots=True)
class AutopackResult:
    output_directory: Path
    photo_count: int
    source_directory_count: int


@dataclass(frozen=True, slots=True)
class _PackGroup:
    source_directory: Path
    recursive: bool
    output_prefix: Path
    ranges: tuple[SunsetRange, ...]


def pack_score_result(
    input_directory: Path,
    result: ScoreResult,
    *,
    recursive: bool,
) -> AutopackResult:
    root = input_directory.expanduser().resolve()
    groups = []
    if result.has_sunset:
        _require_ranges(result.sunset_ranges, str(root))
        groups.append(_PackGroup(root, recursive, Path(), result.sunset_ranges))
    elif result.sunset_ranges:
        raise AutopackError("未检测到晚霞的结果不能包含晚霞区间")
    return _pack(root, groups)


def pack_independent_result(
    input_directory: Path,
    result: IndependentScoreResult,
) -> AutopackResult:
    root = input_directory.expanduser().resolve()
    groups = []
    for item in result.directories:
        if not item.succeeded:
            continue
        if not item.has_sunset:
            if item.sunset_ranges:
                raise AutopackError(
                    f"未检测到晚霞的目录不能包含晚霞区间: {item.directory}"
                )
            continue
        _require_ranges(item.sunset_ranges, item.directory)
        relative = _safe_directory(item.directory)
        source = (root / relative).resolve()
        _require_descendant(source, root, item.directory)
        groups.append(_PackGroup(source, False, relative, item.sunset_ranges))
    return _pack(root, groups)


def _pack(root: Path, groups: list[_PackGroup]) -> AutopackResult:
    output = root / OUTPUT_DIRECTORY_NAME
    _validate_existing_output(output)
    stage = Path(
        tempfile.mkdtemp(
            prefix=f".{root.name}-{OUTPUT_DIRECTORY_NAME}-",
            dir=root.parent,
        )
    )
    photo_count = 0
    source_count = 0
    try:
        for group in groups:
            selected = _select_photos(group)
            if selected:
                source_count += 1
            for source, relative in selected:
                destination = stage / group.output_prefix / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
                photo_count += 1
        _install_output(stage, output)
    except AutopackError:
        raise
    except OSError as exc:
        raise AutopackError(f"无法写入晚霞打包目录 {output}: {exc}") from exc
    finally:
        _cleanup_tree(stage)
    logger.info(
        "晚霞照片已写入 %s：%d 个来源目录，共 %d 张",
        output,
        source_count,
        photo_count,
    )
    return AutopackResult(output, photo_count, source_count)


def _select_photos(group: _PackGroup) -> list[tuple[Path, Path]]:
    images = discover_images(group.source_directory, recursive=group.recursive)
    relative_images = [image.relative_to(group.source_directory) for image in images]
    indexes = {relative.as_posix(): index for index, relative in enumerate(relative_images)}
    selected: set[int] = set()
    for item in group.ranges:
        start = indexes.get(item.start_photo)
        end = indexes.get(item.end_photo)
        if start is None or end is None:
            raise AutopackError(
                "晚霞区间照片已不存在，请使用 --force 重新评分: "
                f"{item.start_photo} 至 {item.end_photo}"
            )
        if start > end:
            raise AutopackError(
                f"晚霞区间起点位于终点之后: {item.start_photo} 至 {item.end_photo}"
            )
        selected.update(range(start, end + 1))
    return [(images[index], relative_images[index]) for index in sorted(selected)]


def _install_output(stage: Path, output: Path) -> None:
    backup: Path | None = None
    if os.path.lexists(output):
        backup = output.with_name(f".{output.name}-backup-{uuid4().hex}")
        os.replace(output, backup)
    try:
        os.replace(stage, output)
    except OSError as exc:
        if backup is not None:
            try:
                os.replace(backup, output)
            except OSError as rollback_exc:
                raise AutopackError(
                    f"无法安装新打包目录，且旧目录恢复失败: {rollback_exc}"
                ) from exc
        raise
    if backup is not None:
        _cleanup_tree(backup)


def _validate_existing_output(output: Path) -> None:
    if not os.path.lexists(output):
        return
    if _is_link_or_reparse(output):
        raise AutopackError(f"晚霞打包路径不能是链接或重解析点: {output}")
    if not output.is_dir():
        raise AutopackError(f"晚霞打包路径不是目录: {output}")


def _safe_directory(value: str) -> Path:
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise AutopackError(f"无效的来源目录: {value}")
    return relative


def _require_descendant(path: Path, root: Path, label: str) -> None:
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise AutopackError(f"来源目录超出输入范围: {label}") from exc
    output = root / OUTPUT_DIRECTORY_NAME
    if path == root or path == output or output in path.parents:
        raise AutopackError(f"无效的来源目录: {label}")


def _require_ranges(ranges: tuple[SunsetRange, ...], label: str) -> None:
    if not ranges:
        raise AutopackError(f"检测到晚霞但缺少晚霞区间: {label}")


def _is_link_or_reparse(path: Path) -> bool:
    if path.is_symlink():
        return True
    try:
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
    except OSError:
        return True
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def _cleanup_tree(path: Path) -> None:
    if not os.path.lexists(path):
        return
    try:
        shutil.rmtree(path)
    except OSError as exc:
        logger.warning("无法清理自动打包临时目录 %s: %s", path, exc)
