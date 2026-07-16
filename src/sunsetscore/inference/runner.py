from __future__ import annotations

import os
from pathlib import Path
import subprocess
from threading import Lock

from ..errors import InferenceError
from ..imaging import prepared_image
from ..log import logger
from ..results import PhotoScore
from ..runtime import RuntimeEnvironment, ensure_runtime_environment
from .parser import parse_model_response
from .prompt import RESPONSE_SCHEMA, RETRY_PROMPT, SCORING_PROMPT


INFERENCE_TIMEOUT_SECONDS = 600


class LocalVisionScorer:
    def __init__(
        self,
        environment: RuntimeEnvironment | None = None,
        *,
        cpu_infer: bool = False,
    ) -> None:
        self._environment = environment or ensure_runtime_environment(
            force_cpu=cpu_infer
        )
        self._fallback_attempted = False
        self._fallback_lock = Lock()

    @property
    def model_version(self) -> str:
        return self._environment.version

    @property
    def inference_backend(self) -> str:
        return self._environment.backend

    @property
    def inference_device(self) -> str:
        return self._environment.device

    @property
    def parallel_scoring_supported(self) -> bool:
        return self._environment.backend != "cpu"

    @property
    def free_gpu_memory_mib(self) -> int | None:
        return self._environment.free_gpu_memory_mib

    def score(self, image: Path) -> PhotoScore:
        with prepared_image(image) as normalized:
            first_output = self._invoke(normalized, SCORING_PROMPT)
            try:
                return parse_model_response(first_output)
            except InferenceError:
                second_output = self._invoke(normalized, RETRY_PROMPT)
                return parse_model_response(second_output)

    def _invoke(self, image: Path, prompt: str) -> str:
        active_environment = self._environment
        command = self._build_command(active_environment, image, prompt)
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
            if self._fallback_to_cpu(active_environment, str(exc)):
                return self._invoke(image, prompt)
            raise InferenceError(f"无法执行本地模型: {exc}") from exc

        if result.returncode != 0:
            detail = _last_nonempty_line(result.stderr) or _last_nonempty_line(
                result.stdout
            )
            if self._fallback_to_cpu(
                active_environment,
                detail or f"退出码 {result.returncode}",
            ):
                return self._invoke(image, prompt)
            suffix = f"：{detail}" if detail else ""
            raise InferenceError(f"本地模型退出码为 {result.returncode}{suffix}")
        return result.stdout

    def _build_command(
        self,
        environment: RuntimeEnvironment,
        image: Path,
        prompt: str,
    ) -> list[str]:
        command = [
            str(environment.executable),
            "-m",
            str(environment.model),
            "--mmproj",
            str(environment.projector),
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
        if environment.backend == "cpu":
            command.extend(["--device", "none", "--gpu-layers", "0"])
        else:
            command.extend(["--gpu-layers", "auto", "--fit", "on"])
        return command

    def _fallback_to_cpu(
        self,
        failed_environment: RuntimeEnvironment,
        reason: str,
    ) -> bool:
        if failed_environment.backend == "cpu":
            return False
        with self._fallback_lock:
            if self._environment.backend == "cpu":
                return True
            if self._fallback_attempted:
                return False
            self._fallback_attempted = True
            logger.warning(
                "%s 推理失败，将自动回退 CPU：%s",
                failed_environment.backend.upper(),
                reason,
            )
            self._environment = ensure_runtime_environment(force_cpu=True)
            logger.info(
                "已切换推理后端：%s，设备：%s",
                self._environment.backend.upper(),
                self._environment.device,
            )
            return True


def _last_nonempty_line(value: str) -> str:
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    return lines[-1][:300] if lines else ""
