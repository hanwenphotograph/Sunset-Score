from __future__ import annotations

import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tarfile
import zipfile

from ..errors import RuntimeInstallError


def extract_archive(archive: Path, destination: Path) -> None:
    try:
        if archive.name.endswith(".zip"):
            _extract_zip(archive, destination)
        elif archive.name.endswith(".tar.gz"):
            _extract_tar(archive, destination)
        else:
            raise RuntimeInstallError(f"不支持的运行时压缩格式: {archive.name}")
    except (tarfile.TarError, zipfile.BadZipFile) as exc:
        raise RuntimeInstallError(f"运行时压缩包已损坏: {exc}") from exc


def find_executable(root: Path, name: str) -> Path:
    matches = list(root.rglob(name))
    if len(matches) != 1:
        raise RuntimeInstallError(f"运行时压缩包中的 {name} 数量异常")
    return matches[0]


def make_executable(path: Path) -> None:
    if os.name != "nt":
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _extract_zip(archive: Path, destination: Path) -> None:
    with zipfile.ZipFile(archive) as source:
        for member in source.infolist():
            target = _archive_target(destination, member.filename)
            mode = member.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise RuntimeInstallError("运行时压缩包包含不允许的符号链接")
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with (
                source.open(member) as input_stream,
                target.open("wb") as output_stream,
            ):
                shutil.copyfileobj(input_stream, output_stream)


def _extract_tar(archive: Path, destination: Path) -> None:
    with tarfile.open(archive, "r:gz") as source:
        for member in source.getmembers():
            target = _archive_target(destination, member.name)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            if not member.isfile():
                raise RuntimeInstallError("运行时压缩包包含不允许的特殊文件")
            target.parent.mkdir(parents=True, exist_ok=True)
            input_stream = source.extractfile(member)
            if input_stream is None:
                raise RuntimeInstallError(f"无法读取压缩包成员: {member.name}")
            with input_stream, target.open("wb") as output_stream:
                shutil.copyfileobj(input_stream, output_stream)
            target.chmod(member.mode & 0o777)


def _archive_target(root: Path, name: str) -> Path:
    relative = PurePosixPath(name.replace("\\", "/"))
    if relative.is_absolute() or ".." in relative.parts:
        raise RuntimeInstallError(f"运行时压缩包包含非法路径: {name}")
    return root.joinpath(*relative.parts)
