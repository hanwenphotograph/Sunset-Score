from __future__ import annotations

from hashlib import sha256
from io import BytesIO
import zipfile

import pytest

from sunsetscore.errors import RuntimeInstallError
from sunsetscore.runtime import archive as runtime_archive
from sunsetscore.runtime import download, install
from sunsetscore.runtime.devices import RuntimeCandidate
from sunsetscore.runtime.paths import (
    HOME_ENVIRONMENT_VARIABLE,
    RuntimePaths,
    get_runtime_paths,
)
from sunsetscore.runtime.specs import ArtifactSpec, RuntimeSpec, detect_runtime_spec


class ByteResponse(BytesIO):
    def __init__(self, value: bytes, status: int) -> None:
        super().__init__(value)
        self.status = status

    def getcode(self) -> int:
        return self.status


def _artifact(payload: bytes, filename: str = "artifact.bin") -> ArtifactSpec:
    return ArtifactSpec(
        filename=filename,
        url="https://example.invalid/artifact",
        size=len(payload),
        sha256=sha256(payload).hexdigest(),
    )


def test_download_resumes_partial_file(tmp_path, monkeypatch) -> None:
    payload = b"0123456789"
    destination = tmp_path / "artifact.bin"
    partial = tmp_path / "artifact.bin.part"
    partial.write_bytes(payload[:4])
    requests = []

    def fake_urlopen(request, timeout):
        requests.append(request)
        return ByteResponse(payload[4:], 206)

    monkeypatch.setattr(download, "urlopen", fake_urlopen)

    assert download.ensure_download(_artifact(payload), destination) == destination
    assert destination.read_bytes() == payload
    assert requests[0].get_header("Range") == "bytes=4-"


def test_valid_cached_download_does_not_use_network(tmp_path, monkeypatch) -> None:
    payload = b"cached"
    destination = tmp_path / "artifact.bin"
    destination.write_bytes(payload)
    monkeypatch.setattr(
        download,
        "urlopen",
        lambda *args, **kwargs: pytest.fail("network must not be used"),
    )

    assert download.ensure_download(_artifact(payload), destination) == destination


def test_runtime_platform_matrix() -> None:
    assert detect_runtime_spec("Windows", "AMD64").key == "windows-x64"
    assert detect_runtime_spec("Darwin", "arm64").key == "macos-arm64"
    assert detect_runtime_spec("Darwin", "x86_64").key == "macos-x64"
    assert detect_runtime_spec("Linux", "x86_64").key == "linux-x64"
    with pytest.raises(RuntimeInstallError, match="不支持当前平台"):
        detect_runtime_spec("Linux", "aarch64")


def test_home_environment_variable_overrides_platform_path(
    tmp_path, monkeypatch
) -> None:
    selected = tmp_path / "portable"
    monkeypatch.setenv(HOME_ENVIRONMENT_VARIABLE, str(selected))

    assert get_runtime_paths().home == selected.resolve()


def test_zip_traversal_is_rejected(tmp_path) -> None:
    archive = tmp_path / "runtime.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("../escape.exe", b"bad")

    with pytest.raises(RuntimeInstallError, match="非法路径"):
        runtime_archive.extract_archive(archive, tmp_path / "output")


def test_zip_backslash_traversal_is_rejected(tmp_path) -> None:
    archive = tmp_path / "runtime.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("..\\escape.exe", b"bad")

    with pytest.raises(RuntimeInstallError, match="非法路径"):
        runtime_archive.extract_archive(archive, tmp_path / "output")


def test_runtime_archive_is_installed_once(tmp_path, monkeypatch) -> None:
    archive = tmp_path / "runtime.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("bin/llama-mtmd-cli.exe", b"executable")
    payload = archive.read_bytes()
    artifact = ArtifactSpec(
        filename=archive.name,
        url="https://example.invalid/runtime.zip",
        size=len(payload),
        sha256=sha256(payload).hexdigest(),
    )
    spec = RuntimeSpec("test-x64", artifact, "llama-mtmd-cli.exe")
    paths = RuntimePaths(tmp_path / "home")
    paths.create()
    calls = 0

    def fake_download(requested, destination):
        nonlocal calls
        calls += 1
        return archive

    monkeypatch.setattr(install, "ensure_download", fake_download)

    first = install._ensure_runtime(paths, spec)
    second = install._ensure_runtime(paths, spec)

    assert first == second
    assert first.read_bytes() == b"executable"
    assert calls == 1


def test_runtime_installs_additional_archives(tmp_path, monkeypatch) -> None:
    main = tmp_path / "main.zip"
    dependency = tmp_path / "dependency.zip"
    with zipfile.ZipFile(main, "w") as output:
        output.writestr("bin/llama-mtmd-cli.exe", b"executable")
    with zipfile.ZipFile(dependency, "w") as output:
        output.writestr("bin/cudart.dll", b"dependency")
    main_spec = _artifact(main.read_bytes(), main.name)
    dependency_spec = _artifact(dependency.read_bytes(), dependency.name)
    spec = RuntimeSpec(
        "test-cuda",
        main_spec,
        "llama-mtmd-cli.exe",
        "cuda",
        (dependency_spec,),
    )
    paths = RuntimePaths(tmp_path / "home")
    paths.create()
    archives = {main.name: main, dependency.name: dependency}
    monkeypatch.setattr(
        install,
        "ensure_download",
        lambda requested, destination: archives[requested.filename],
    )

    executable = install._ensure_runtime(paths, spec)

    assert executable.read_bytes() == b"executable"
    assert (executable.parent / "cudart.dll").read_bytes() == b"dependency"


def test_runtime_selection_continues_after_gpu_failure(tmp_path, monkeypatch) -> None:
    cuda = RuntimeCandidate(detect_runtime_spec("Windows", "AMD64", "cuda"), "Test GPU")
    cpu = RuntimeCandidate(detect_runtime_spec("Windows", "AMD64"), "Test CPU")
    cpu_executable = tmp_path / "cpu.exe"

    def fake_install(paths, spec):
        if spec.backend == "cuda":
            raise RuntimeInstallError("模拟 GPU 失败")
        return cpu_executable

    monkeypatch.setattr(install, "_ensure_runtime", fake_install)

    selected, executable, device = install._select_runtime(
        RuntimePaths(tmp_path), [cuda, cpu]
    )

    assert selected.spec.backend == "cpu"
    assert executable == cpu_executable
    assert device == "Test CPU"
