from __future__ import annotations

import os
from pathlib import Path
import re
import stat
from typing import Iterator

from .errors import InputError
from .log import logger


SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png"}
_NUMBER_PATTERN = re.compile(r"(\d+)")


def discover_images(input_directory: Path, *, recursive: bool) -> list[Path]:
    root = input_directory.expanduser()
    if _is_link_or_reparse(root):
        raise InputError(f"输入目录不能是符号链接或重解析点: {root}")
    if not root.exists():
        raise InputError(f"输入目录不存在: {root}")
    if not root.is_dir():
        raise InputError(f"输入路径不是目录: {root}")

    root = root.resolve()
    images = list(_walk(root, recursive=recursive, is_root=True))
    images.sort(key=lambda path: natural_path_key(path.relative_to(root)))
    return images


def sample_images(images: list[Path], interval: int) -> list[Path]:
    if interval < 1:
        raise ValueError("interval must be at least 1")
    return images[::interval]


def natural_path_key(path: Path) -> tuple[object, ...]:
    parts = tuple(_natural_text_key(part) for part in path.parts)
    return parts + (((2, path.as_posix()),),)


def _natural_text_key(value: str) -> tuple[tuple[int, object], ...]:
    chunks: list[tuple[int, object]] = []
    for chunk in _NUMBER_PATTERN.split(value.casefold()):
        if chunk.isdigit():
            chunks.append((1, int(chunk)))
        else:
            chunks.append((0, chunk))
    return tuple(chunks)


def _walk(directory: Path, *, recursive: bool, is_root: bool) -> Iterator[Path]:
    try:
        with os.scandir(directory) as entries:
            current = list(entries)
    except OSError as exc:
        if is_root:
            raise InputError(f"无法扫描输入目录 {directory}: {exc}") from exc
        logger.warning("跳过无法扫描的子目录 %s: %s", directory, exc)
        return

    for entry in current:
        try:
            if _entry_is_link_or_reparse(entry):
                continue
            if entry.is_file(follow_symlinks=False):
                path = Path(entry.path)
                if path.suffix.casefold() in SUPPORTED_SUFFIXES:
                    yield path
            elif recursive and entry.is_dir(follow_symlinks=False):
                yield from _walk(Path(entry.path), recursive=True, is_root=False)
        except OSError as exc:
            logger.warning("跳过无法访问的路径 %s: %s", entry.path, exc)


def _entry_is_link_or_reparse(entry: os.DirEntry[str]) -> bool:
    if entry.is_symlink():
        return True
    try:
        attributes = getattr(entry.stat(follow_symlinks=False), "st_file_attributes", 0)
    except OSError:
        return True
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def _is_link_or_reparse(path: Path) -> bool:
    if path.is_symlink():
        return True
    try:
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
    except OSError:
        return False
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))
