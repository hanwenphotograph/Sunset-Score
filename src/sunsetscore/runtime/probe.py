from __future__ import annotations

from pathlib import Path
import subprocess

from ..errors import RuntimeInstallError
from .devices import RuntimeCandidate


def probe_gpu_runtime(executable: Path, candidate: RuntimeCandidate) -> str:
    try:
        result = subprocess.run(
            [str(executable), "--list-devices"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeInstallError(f"无法启动 GPU 运行时自检: {exc}") from exc
    output = "\n".join((result.stdout, result.stderr)).strip()
    if result.returncode != 0:
        detail = _last_nonempty_line(output)
        raise RuntimeInstallError(f"GPU 运行时自检失败: {detail or result.returncode}")
    token = candidate.spec.backend.casefold()
    device_line = next(
        (
            line.strip(" -\t")
            for line in output.splitlines()
            if token in line.casefold()
        ),
        "",
    )
    if not device_line:
        raise RuntimeInstallError("GPU 运行时未列出匹配的计算设备")
    return device_line


def _last_nonempty_line(value: str) -> str:
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    return lines[-1][:300] if lines else ""
