from __future__ import annotations

import subprocess

import pytest

from sunsetscore.errors import RuntimeInstallError
from sunsetscore.runtime import devices, probe
from sunsetscore.runtime.devices import RuntimeCandidate
from sunsetscore.runtime.specs import detect_runtime_spec


def test_windows_nvidia_candidates_prefer_cuda_then_vulkan(monkeypatch) -> None:
    monkeypatch.setattr(devices.platform, "system", lambda: "Windows")
    monkeypatch.setattr(devices.platform, "machine", lambda: "AMD64")
    monkeypatch.setattr(devices, "_cpu_name", lambda: "Test CPU")
    monkeypatch.setattr(
        devices,
        "_detect_nvidia_gpu",
        lambda: ("NVIDIA Test GPU", (13, 1)),
    )
    monkeypatch.setattr(devices, "_vulkan_loader_available", lambda system: True)

    candidates = devices.detect_runtime_candidates()

    assert [item.spec.backend for item in candidates] == ["cuda", "vulkan", "cpu"]
    assert candidates[0].device_hint == "NVIDIA Test GPU"


def test_cpu_override_skips_gpu_detection(monkeypatch) -> None:
    monkeypatch.setattr(devices.platform, "system", lambda: "Windows")
    monkeypatch.setattr(devices.platform, "machine", lambda: "AMD64")
    monkeypatch.setattr(devices, "_cpu_name", lambda: "Test CPU")
    monkeypatch.setattr(
        devices,
        "_detect_nvidia_gpu",
        lambda: pytest.fail("GPU detection must be skipped"),
    )

    candidates = devices.detect_runtime_candidates(force_cpu=True)

    assert [item.spec.backend for item in candidates] == ["cpu"]


def test_old_cuda_driver_uses_vulkan_candidate(monkeypatch) -> None:
    monkeypatch.setattr(devices.platform, "system", lambda: "Windows")
    monkeypatch.setattr(devices.platform, "machine", lambda: "AMD64")
    monkeypatch.setattr(devices, "_cpu_name", lambda: "Test CPU")
    monkeypatch.setattr(
        devices,
        "_detect_nvidia_gpu",
        lambda: ("NVIDIA Test GPU", (12, 3)),
    )
    monkeypatch.setattr(devices, "_vulkan_loader_available", lambda system: True)

    candidates = devices.detect_runtime_candidates()

    assert [item.spec.backend for item in candidates] == ["vulkan", "cpu"]


def test_gpu_probe_returns_runtime_device_line(tmp_path, monkeypatch) -> None:
    candidate = RuntimeCandidate(
        detect_runtime_spec("Windows", "AMD64", "cuda"),
        "NVIDIA Test GPU",
    )
    monkeypatch.setattr(
        probe.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0],
            0,
            stdout="Available devices:\n  CUDA0: NVIDIA Test GPU\n",
            stderr="",
        ),
    )

    assert probe.probe_gpu_runtime(tmp_path / "llama.exe", candidate) == (
        "CUDA0: NVIDIA Test GPU"
    )


def test_gpu_probe_rejects_missing_backend_device(tmp_path, monkeypatch) -> None:
    candidate = RuntimeCandidate(
        detect_runtime_spec("Windows", "AMD64", "cuda"),
        "NVIDIA Test GPU",
    )
    monkeypatch.setattr(
        probe.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0], 0, stdout="Available devices:\n", stderr=""
        ),
    )

    with pytest.raises(RuntimeInstallError, match="未列出匹配"):
        probe.probe_gpu_runtime(tmp_path / "llama.exe", candidate)
