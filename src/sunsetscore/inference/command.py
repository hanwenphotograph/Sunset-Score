from __future__ import annotations

from pathlib import Path

from ..runtime import RuntimeEnvironment
from .settings import (
    CONTEXT_TOKENS_PER_SLOT,
    GPU_FIT_TARGET_MIB,
    IMAGE_MAX_TOKENS,
    INFERENCE_TIMEOUT_SECONDS,
    SERVER_HOST,
)


def server_command(
    environment: RuntimeEnvironment,
    port: int,
    slots: int,
) -> list[str]:
    executable = environment.server_executable or _sibling_server(environment.executable)
    command = [
        str(executable),
        "-m",
        str(environment.model),
        "--mmproj",
        str(environment.projector),
        "--host",
        SERVER_HOST,
        "--port",
        str(port),
        "--parallel",
        str(slots),
        "--ctx-size",
        str(CONTEXT_TOKENS_PER_SLOT * slots),
        "--image-max-tokens",
        str(IMAGE_MAX_TOKENS),
        "--mtmd-batch-max-tokens",
        str(IMAGE_MAX_TOKENS),
        "--timeout",
        str(INFERENCE_TIMEOUT_SECONDS),
        "--cont-batching",
        "--jinja",
        "--no-warmup",
        "--no-webui",
        "--log-verbosity",
        "0",
        "--log-colors",
        "off",
        "--no-log-timestamps",
    ]
    if environment.backend == "cpu":
        command.extend(
            ["--device", "none", "--gpu-layers", "0", "--no-mmproj-offload"]
        )
        return command

    command.extend(
        [
            "--gpu-layers",
            "auto",
            "--fit",
            "on",
            "--fit-target",
            str(GPU_FIT_TARGET_MIB),
        ]
    )
    if not _has_safe_projector_memory(environment):
        command.append("--no-mmproj-offload")
    return command


def _has_safe_projector_memory(environment: RuntimeEnvironment) -> bool:
    free_memory = environment.free_gpu_memory_mib
    return free_memory is not None and free_memory >= GPU_FIT_TARGET_MIB


def _sibling_server(executable: Path) -> Path:
    name = "llama-server.exe" if executable.suffix.casefold() == ".exe" else "llama-server"
    return executable.with_name(name)
