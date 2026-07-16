from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
import tempfile

from ..errors import RuntimeInstallError
from ..log import logger
from .archive import extract_archive, find_executable, make_executable
from .download import ensure_download
from .lock import installation_lock
from .paths import RuntimePaths, get_runtime_paths
from .specs import (
    LLAMA_RELEASE,
    MODEL_ARTIFACT,
    MODEL_VERSION,
    PROJECTOR_ARTIFACT,
    RuntimeSpec,
    detect_runtime_spec,
)


@dataclass(frozen=True, slots=True)
class RuntimeEnvironment:
    executable: Path
    model: Path
    projector: Path
    version: str


def ensure_runtime_environment() -> RuntimeEnvironment:
    paths = get_runtime_paths()
    spec = detect_runtime_spec()
    try:
        paths.create()
    except OSError as exc:
        raise RuntimeInstallError(f"无法创建程序数据目录 {paths.home}: {exc}") from exc

    logger.info("程序数据目录：%s", paths.home)
    with installation_lock(paths.install_lock):
        executable = _ensure_runtime(paths, spec)
        model = ensure_download(MODEL_ARTIFACT, paths.models / MODEL_ARTIFACT.filename)
        projector = ensure_download(
            PROJECTOR_ARTIFACT,
            paths.models / PROJECTOR_ARTIFACT.filename,
        )

    return RuntimeEnvironment(
        executable=executable,
        model=model,
        projector=projector,
        version=f"{MODEL_VERSION} / llama.cpp {LLAMA_RELEASE}",
    )


def _ensure_runtime(paths: RuntimePaths, spec: RuntimeSpec) -> Path:
    target = paths.runtimes / f"{LLAMA_RELEASE}-{spec.key}"
    installed = _installed_executable(target, spec)
    if installed is not None:
        return installed

    archive = ensure_download(spec.archive, paths.downloads / spec.archive.filename)
    temporary = Path(tempfile.mkdtemp(prefix="runtime-install-", dir=paths.runtimes))
    try:
        logger.info("正在安装本地推理运行时：%s", spec.key)
        extract_archive(archive, temporary)
        executable = find_executable(temporary, spec.executable_name)
        make_executable(executable)
        relative = executable.relative_to(temporary).as_posix()
        _write_marker(temporary, spec, relative)
        _remove_managed_target(target, paths.runtimes)
        os.replace(temporary, target)
    except (OSError, ValueError) as exc:
        raise RuntimeInstallError(f"无法安装本地推理运行时: {exc}") from exc
    finally:
        if temporary.exists():
            shutil.rmtree(temporary, ignore_errors=True)

    installed = _installed_executable(target, spec)
    if installed is None:
        raise RuntimeInstallError("推理运行时安装完成后仍无法找到可执行文件")
    return installed


def _installed_executable(target: Path, spec: RuntimeSpec) -> Path | None:
    marker = target / ".installed.json"
    try:
        document = json.loads(marker.read_text(encoding="utf-8"))
        if document.get("release") != LLAMA_RELEASE:
            return None
        if document.get("archive_sha256") != spec.archive.sha256:
            return None
        relative = Path(document["executable"])
        if relative.is_absolute() or ".." in relative.parts:
            return None
        executable = target / relative
        if executable.name == spec.executable_name and executable.is_file():
            return executable
    except (OSError, KeyError, TypeError, json.JSONDecodeError):
        return None
    return None


def _write_marker(root: Path, spec: RuntimeSpec, executable: str) -> None:
    document = {
        "release": LLAMA_RELEASE,
        "platform": spec.key,
        "archive_sha256": spec.archive.sha256,
        "executable": executable,
    }
    (root / ".installed.json").write_text(
        json.dumps(document, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _remove_managed_target(target: Path, parent: Path) -> None:
    if not target.exists() and not target.is_symlink():
        return
    if target.parent.resolve() != parent.resolve():
        raise RuntimeInstallError(f"拒绝清理非托管目录: {target}")
    if target.is_symlink() or target.is_file():
        target.unlink()
    else:
        shutil.rmtree(target)
