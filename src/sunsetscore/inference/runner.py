from __future__ import annotations

import os
from pathlib import Path
import subprocess

from ..errors import InferenceError
from ..imaging import prepared_image
from ..results import PhotoScore
from ..runtime import RuntimeEnvironment, ensure_runtime_environment
from .parser import parse_model_response
from .prompt import RESPONSE_SCHEMA, RETRY_PROMPT, SCORING_PROMPT


INFERENCE_TIMEOUT_SECONDS = 600


class LocalVisionScorer:
    def __init__(self, environment: RuntimeEnvironment | None = None) -> None:
        self._environment = environment or ensure_runtime_environment()

    @property
    def model_version(self) -> str:
        return self._environment.version

    def score(self, image: Path) -> PhotoScore:
        with prepared_image(image) as normalized:
            first_output = self._invoke(normalized, SCORING_PROMPT)
            try:
                return parse_model_response(first_output)
            except InferenceError:
                second_output = self._invoke(normalized, RETRY_PROMPT)
                return parse_model_response(second_output)

    def _invoke(self, image: Path, prompt: str) -> str:
        command = [
            str(self._environment.executable),
            "-m",
            str(self._environment.model),
            "--mmproj",
            str(self._environment.projector),
            "--image",
            str(image),
            "-p",
            prompt,
            "--json-schema",
            RESPONSE_SCHEMA,
            "--temp",
            "0",
            "--top-k",
            "1",
            "--top-p",
            "1",
            "--seed",
            "0",
            "--ctx-size",
            "4096",
            "--image-max-tokens",
            "1280",
            "-n",
            "160",
            "--no-warmup",
            "--log-verbosity",
            "0",
            "--log-colors",
            "off",
            "--no-log-timestamps",
        ]
        environment = os.environ.copy()
        environment["NO_COLOR"] = "1"
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=environment,
                timeout=INFERENCE_TIMEOUT_SECONDS,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise InferenceError(f"无法执行本地模型: {exc}") from exc

        if result.returncode != 0:
            detail = _last_nonempty_line(result.stderr) or _last_nonempty_line(
                result.stdout
            )
            suffix = f"：{detail}" if detail else ""
            raise InferenceError(f"本地模型退出码为 {result.returncode}{suffix}")
        return result.stdout


def _last_nonempty_line(value: str) -> str:
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    return lines[-1][:300] if lines else ""
