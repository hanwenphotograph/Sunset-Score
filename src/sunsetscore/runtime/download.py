from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..errors import RuntimeInstallError
from ..log import logger
from .specs import ArtifactSpec


CHUNK_SIZE = 4 * 1024 * 1024


class IntegrityError(Exception):
    pass


def ensure_download(spec: ArtifactSpec, destination: Path) -> Path:
    partial = destination.with_name(f"{destination.name}.part")
    try:
        return _ensure_download(spec, destination)
    except RuntimeInstallError:
        raise
    except OSError as exc:
        raise RuntimeInstallError(f"无法访问下载文件 {destination}: {exc}") from exc
    except BaseException:
        _remove_interrupted_download(partial)
        raise


def _ensure_download(spec: ArtifactSpec, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if _is_valid(destination, spec, announce=True):
            return destination
        logger.warning("已缓存文件校验失败，准备重新下载：%s", destination.name)
        destination.unlink()

    partial = destination.with_name(f"{destination.name}.part")
    if partial.exists() and partial.stat().st_size > spec.size:
        partial.unlink()

    last_error: Exception | None = None
    for attempt in range(1, 3):
        try:
            _download(spec, partial)
            if not _is_valid(partial, spec, announce=True):
                partial.unlink(missing_ok=True)
                raise IntegrityError("文件大小或 SHA-256 不匹配")
            os.replace(partial, destination)
            logger.info("下载完成：%s", destination.name)
            return destination
        except (HTTPError, URLError, OSError, IntegrityError) as exc:
            last_error = exc
            if attempt == 1:
                logger.warning("下载失败，将重试一次：%s", exc)

    raise RuntimeInstallError(f"无法下载 {spec.filename}: {last_error}") from last_error


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def _is_valid(path: Path, spec: ArtifactSpec, *, announce: bool) -> bool:
    try:
        if path.stat().st_size != spec.size:
            return False
        if announce and spec.size >= 100 * 1024 * 1024:
            logger.info("正在校验：%s", path.name)
        return file_sha256(path) == spec.sha256
    except OSError:
        return False


def _download(spec: ArtifactSpec, partial: Path) -> None:
    offset = partial.stat().st_size if partial.exists() else 0
    if offset == spec.size:
        return

    headers = {"User-Agent": "SunsetScore/0.5.0"}
    if offset:
        headers["Range"] = f"bytes={offset}-"
        logger.info(
            "继续下载 %s，已完成 %.1f%%", spec.filename, offset * 100 / spec.size
        )
    else:
        logger.info("开始下载 %s（%.1f MB）", spec.filename, spec.size / 1024 / 1024)

    request = Request(spec.url, headers=headers)
    with urlopen(request, timeout=60) as response:
        resumed = offset > 0 and getattr(response, "status", response.getcode()) == 206
        if offset and not resumed:
            offset = 0
        mode = "ab" if resumed else "wb"
        _copy_response(response, partial, mode, offset, spec)


def _copy_response(
    response, partial: Path, mode: str, offset: int, spec: ArtifactSpec
) -> None:
    downloaded = offset
    next_notice = ((downloaded * 100 // spec.size) // 10 + 1) * 10
    with partial.open(mode) as stream:
        while chunk := response.read(CHUNK_SIZE):
            stream.write(chunk)
            downloaded += len(chunk)
            percent = downloaded * 100 // spec.size
            if percent >= next_notice:
                logger.info("下载进度 %s：%d%%", spec.filename, min(percent, 100))
                next_notice += 10
    if downloaded != spec.size:
        raise IntegrityError(f"下载大小错误，预期 {spec.size}，实际 {downloaded}")


def _remove_interrupted_download(partial: Path) -> None:
    try:
        existed = partial.exists()
        partial.unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("无法清理未完成下载缓存 %s：%s", partial.name, exc)
    else:
        if existed:
            logger.info("已清理未完成下载缓存：%s", partial.name)
