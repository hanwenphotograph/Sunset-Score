from __future__ import annotations

from dataclasses import dataclass
import platform

from ..errors import RuntimeInstallError


LLAMA_RELEASE = "b10040"
MODEL_VERSION = "Qwen3-VL-2B-Instruct-Q4_K_M"
MODEL_BASE_URL = "https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct-GGUF/resolve/main"


@dataclass(frozen=True, slots=True)
class ArtifactSpec:
    filename: str
    url: str
    size: int
    sha256: str


@dataclass(frozen=True, slots=True)
class RuntimeSpec:
    key: str
    archive: ArtifactSpec
    executable_name: str
    backend: str = "cpu"
    additional_archives: tuple[ArtifactSpec, ...] = ()


MODEL_ARTIFACT = ArtifactSpec(
    filename="Qwen3VL-2B-Instruct-Q4_K_M.gguf",
    url=f"{MODEL_BASE_URL}/Qwen3VL-2B-Instruct-Q4_K_M.gguf?download=true",
    size=1_107_409_952,
    sha256="089d75c52f4b7ffc56ba998ffc50aae89fcafc755f9e7208aacca281dca6c2ae",
)

PROJECTOR_ARTIFACT = ArtifactSpec(
    filename="mmproj-Qwen3VL-2B-Instruct-Q8_0.gguf",
    url=f"{MODEL_BASE_URL}/mmproj-Qwen3VL-2B-Instruct-Q8_0.gguf?download=true",
    size=445_053_216,
    sha256="f9a68fabba69c3b81e153367b2c7521030b0fa8bb0de400c9599c8e6725f9c82",
)


def detect_runtime_spec(
    system: str | None = None,
    machine: str | None = None,
    backend: str = "cpu",
) -> RuntimeSpec:
    system_name = (system or platform.system()).casefold()
    machine_name = _normalize_machine(machine or platform.machine())
    key = (system_name, machine_name, backend.casefold())
    try:
        return _RUNTIME_SPECS[key]
    except KeyError as exc:
        raise RuntimeInstallError(
            f"不支持当前平台或推理后端: {system_name}/{machine_name}/{backend}"
        ) from exc


def _normalize_machine(machine: str) -> str:
    value = machine.casefold()
    if value in {"amd64", "x86_64", "x64"}:
        return "x64"
    if value in {"arm64", "aarch64"}:
        return "arm64"
    return value


def _runtime_artifact(filename: str, size: int, sha256: str) -> ArtifactSpec:
    return ArtifactSpec(
        filename=filename,
        url=(
            "https://github.com/ggml-org/llama.cpp/releases/download/"
            f"{LLAMA_RELEASE}/{filename}"
        ),
        size=size,
        sha256=sha256,
    )


_WINDOWS_CPU = _runtime_artifact(
    "llama-b10040-bin-win-cpu-x64.zip",
    18_419_140,
    "ebe8cd170c80d71466bb2d381af41560f4b187952855aafc661ecd89365e4da5",
)
_WINDOWS_CUDA = _runtime_artifact(
    "llama-b10040-bin-win-cuda-12.4-x64.zip",
    249_299_749,
    "156132c824952260d416e9c12dd1614392d0915595e6fdec7ed8719e64161550",
)
_WINDOWS_CUDART = _runtime_artifact(
    "cudart-llama-bin-win-cuda-12.4-x64.zip",
    391_443_627,
    "8c79a9b226de4b3cacfd1f83d24f962d0773be79f1e7b75c6af4ded7e32ae1d6",
)
_WINDOWS_VULKAN = _runtime_artifact(
    "llama-b10040-bin-win-vulkan-x64.zip",
    33_203_497,
    "a26d80a1d399cdd8ee6c95c48d39badae15f89ebbf543bf8dc99d839b8a3fdd4",
)
_MACOS_ARM64 = _runtime_artifact(
    "llama-b10040-bin-macos-arm64.tar.gz",
    10_895_581,
    "15b844e2a3a8eb4dac92e087499afeec2cd5861c5b649a2b9121e3ce3eac93f6",
)
_MACOS_X64 = _runtime_artifact(
    "llama-b10040-bin-macos-x64.tar.gz",
    11_176_367,
    "f8f289b1d08e60cecbb4e696c3009221cc2789983c7d1a24df8c70469677e3f3",
)
_LINUX_CPU = _runtime_artifact(
    "llama-b10040-bin-ubuntu-x64.tar.gz",
    16_018_145,
    "115ef223994890f1a2fcb294ba664e6dc44d2da27b80a363efb068efadaad9e5",
)
_LINUX_VULKAN = _runtime_artifact(
    "llama-b10040-bin-ubuntu-vulkan-x64.tar.gz",
    31_440_288,
    "9294d33c7ac4cacd4e760dd8ceaff8e9e2e884ff0044cf9346c7922bd14f1abe",
)


_RUNTIME_SPECS = {
    ("windows", "x64", "cpu"): RuntimeSpec(
        "windows-x64", _WINDOWS_CPU, "llama-mtmd-cli.exe"
    ),
    ("windows", "x64", "cuda"): RuntimeSpec(
        "windows-x64-cuda-12.4",
        _WINDOWS_CUDA,
        "llama-mtmd-cli.exe",
        "cuda",
        (_WINDOWS_CUDART,),
    ),
    ("windows", "x64", "vulkan"): RuntimeSpec(
        "windows-x64-vulkan",
        _WINDOWS_VULKAN,
        "llama-mtmd-cli.exe",
        "vulkan",
    ),
    ("darwin", "arm64", "cpu"): RuntimeSpec(
        "macos-arm64", _MACOS_ARM64, "llama-mtmd-cli"
    ),
    ("darwin", "arm64", "metal"): RuntimeSpec(
        "macos-arm64-metal", _MACOS_ARM64, "llama-mtmd-cli", "metal"
    ),
    ("darwin", "x64", "cpu"): RuntimeSpec("macos-x64", _MACOS_X64, "llama-mtmd-cli"),
    ("darwin", "x64", "metal"): RuntimeSpec(
        "macos-x64-metal", _MACOS_X64, "llama-mtmd-cli", "metal"
    ),
    ("linux", "x64", "cpu"): RuntimeSpec("linux-x64", _LINUX_CPU, "llama-mtmd-cli"),
    ("linux", "x64", "vulkan"): RuntimeSpec(
        "linux-x64-vulkan", _LINUX_VULKAN, "llama-mtmd-cli", "vulkan"
    ),
}
