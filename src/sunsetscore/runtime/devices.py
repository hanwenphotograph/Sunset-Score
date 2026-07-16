from __future__ import annotations

from dataclasses import dataclass
import ctypes.util
import os
from pathlib import Path
import platform
import re
import subprocess

from .specs import RuntimeSpec, detect_runtime_spec


MINIMUM_CUDA_VERSION = (12, 4)


@dataclass(frozen=True, slots=True)
class RuntimeCandidate:
    spec: RuntimeSpec
    device_hint: str


def detect_runtime_candidates(*, force_cpu: bool = False) -> list[RuntimeCandidate]:
    system = platform.system()
    machine = platform.machine()
    cpu = RuntimeCandidate(detect_runtime_spec(system, machine, "cpu"), _cpu_name())
    if force_cpu:
        return [cpu]

    system_name = system.casefold()
    candidates: list[RuntimeCandidate] = []
    nvidia = _detect_nvidia_gpu()
    if system_name == "windows" and nvidia and _supports_managed_cuda(nvidia[1]):
        candidates.append(
            RuntimeCandidate(detect_runtime_spec(system, machine, "cuda"), nvidia[0])
        )
    if system_name == "darwin":
        candidates.append(
            RuntimeCandidate(
                detect_runtime_spec(system, machine, "metal"),
                _mac_gpu_name(machine),
            )
        )
    elif _vulkan_loader_available(system_name):
        candidates.append(
            RuntimeCandidate(
                detect_runtime_spec(system, machine, "vulkan"),
                nvidia[0] if nvidia else "Vulkan-compatible GPU",
            )
        )
    candidates.append(cpu)
    return candidates


def _detect_nvidia_gpu() -> tuple[str, tuple[int, int] | None] | None:
    names = _run_command(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"])
    if names is None:
        return None
    name = next((line.strip() for line in names.splitlines() if line.strip()), "")
    if not name:
        return None
    details = _run_command(["nvidia-smi"])
    match = re.search(r"CUDA Version:\s*(\d+)\.(\d+)", details or "")
    version = (int(match.group(1)), int(match.group(2))) if match else None
    return name, version


def _supports_managed_cuda(version: tuple[int, int] | None) -> bool:
    return version is None or version >= MINIMUM_CUDA_VERSION


def _vulkan_loader_available(system: str) -> bool:
    if system == "windows":
        windows = Path(os.environ.get("WINDIR", r"C:\Windows"))
        return (windows / "System32" / "vulkan-1.dll").is_file()
    if system == "linux":
        return ctypes.util.find_library("vulkan") is not None
    return False


def _run_command(command: list[str]) -> str | None:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout if result.returncode == 0 else None


def _cpu_name() -> str:
    return platform.processor().strip() or platform.machine() or "CPU"


def _mac_gpu_name(machine: str) -> str:
    arm_names = {"arm64", "aarch64"}
    return "Apple Metal GPU" if machine.casefold() in arm_names else "Metal GPU"
