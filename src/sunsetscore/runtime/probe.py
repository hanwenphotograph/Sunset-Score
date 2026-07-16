from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import subprocess

from ..errors import RuntimeInstallError
from .devices import RuntimeCandidate


_MEMORY_PATTERN = re.compile(r"\((\d+) MiB,\s*(\d+) MiB free\)")


@dataclass(frozen=True, slots=True)
class GpuDeviceInfo:
    label: str
    total_memory_mib: int | None = None
    free_memory_mib: int | None = None


def probe_gpu_runtime(
    executable: Path,
    candidate: RuntimeCandidate,
) -> GpuDeviceInfo:
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
    memory = _MEMORY_PATTERN.search(device_line)
    if memory is None:
        return GpuDeviceInfo(device_line)
    return GpuDeviceInfo(
        device_line,
        total_memory_mib=int(memory.group(1)),
        free_memory_mib=int(memory.group(2)),
    )


def _last_nonempty_line(value: str) -> str:
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    return lines[-1][:300] if lines else ""
