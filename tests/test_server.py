from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from sunsetscore.errors import InferenceError
from sunsetscore.inference.protocol import request_body, response_content
from sunsetscore.inference.command import server_command
from sunsetscore.runtime import RuntimeEnvironment


def _environment(tmp_path: Path, backend: str) -> RuntimeEnvironment:
    return RuntimeEnvironment(
        executable=tmp_path / "llama-mtmd-cli.exe",
        server_executable=tmp_path / "llama-server.exe",
        model=tmp_path / "model.gguf",
        projector=tmp_path / "mmproj.gguf",
        version="fake-model",
        backend=backend,
        free_gpu_memory_mib=15_000 if backend != "cpu" else None,
    )


def test_gpu_server_command_uses_two_slots_and_safe_memory_margin(tmp_path) -> None:
    command = server_command(_environment(tmp_path, "cuda"), 32123, 2)

    assert command[0].endswith("llama-server.exe")
    assert command[command.index("--parallel") + 1] == "2"
    assert command[command.index("--ctx-size") + 1] == "8192"
    assert command[command.index("--image-max-tokens") + 1] == "1024"
    assert command[command.index("--fit-target") + 1] == "6144"
    assert "--no-mmproj-offload" not in command


def test_cpu_server_command_disables_all_gpu_offload(tmp_path) -> None:
    command = server_command(_environment(tmp_path, "cpu"), 32123, 1)

    assert command[command.index("--device") + 1] == "none"
    assert command[command.index("--gpu-layers") + 1] == "0"
    assert "--no-mmproj-offload" in command


def test_unknown_gpu_memory_moves_projector_to_cpu(tmp_path) -> None:
    environment = _environment(tmp_path, "vulkan")
    environment = RuntimeEnvironment(
        executable=environment.executable,
        server_executable=environment.server_executable,
        model=environment.model,
        projector=environment.projector,
        version=environment.version,
        backend=environment.backend,
    )

    command = server_command(environment, 32123, 1)

    assert "--no-mmproj-offload" in command


def test_request_body_contains_image_prompt_and_json_schema(tmp_path) -> None:
    image = tmp_path / "input.png"
    image.write_bytes(b"png-data")

    payload = json.loads(request_body(image, "score this"))

    content = payload["messages"][0]["content"]
    encoded = content[0]["image_url"]["url"].split(",", 1)[1]
    assert base64.b64decode(encoded) == b"png-data"
    assert content[1] == {"type": "text", "text": "score this"}
    assert payload["response_format"]["json_schema"]["schema"]["required"] == [
        "score",
        "reason",
    ]


def test_response_content_validates_server_document() -> None:
    document = {"choices": [{"message": {"content": "result"}}]}

    assert response_content(document) == "result"
    with pytest.raises(InferenceError, match="无效响应"):
        response_content({})
