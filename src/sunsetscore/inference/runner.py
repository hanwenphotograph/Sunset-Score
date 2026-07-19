from __future__ import annotations

import atexit
from pathlib import Path
from threading import Event, Lock
from types import TracebackType

from ..errors import InferenceError
from ..imaging import prepared_image
from ..log import logger
from ..results import PhotoScore
from ..runtime import RuntimeEnvironment, ensure_runtime_environment
from .parser import parse_model_response
from .prompt import RETRY_PROMPT, SCORING_PROMPT
from .server import LlamaServer


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
        self._workers = 1
        self._server: LlamaServer | None = None
        self._server_lock = Lock()
        self._closed = Event()
        self._fallback_attempted = False
        self._fallback_lock = Lock()
        atexit.register(self.close)

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

    @property
    def accelerator_fallback_active(self) -> bool:
        return self._fallback_attempted and self._environment.backend == "cpu"

    def configure_workers(self, workers: int) -> None:
        if self._closed.is_set():
            raise RuntimeError("scorer is closed")
        if workers < 1:
            raise ValueError("workers must be at least 1")
        with self._server_lock:
            if self._workers == workers:
                return
            server, self._server = self._server, None
            self._workers = workers
        if server is not None:
            server.close()

    def score(self, image: Path) -> PhotoScore:
        with prepared_image(image) as normalized:
            first_output = self._invoke(normalized, SCORING_PROMPT)
            try:
                return parse_model_response(first_output)
            except InferenceError:
                second_output = self._invoke(normalized, RETRY_PROMPT)
                return parse_model_response(second_output)

    def restore_acceleration(self) -> bool:
        if not self.accelerator_fallback_active or self._closed.is_set():
            return False
        replacement = ensure_runtime_environment(force_cpu=False)
        if replacement.backend == "cpu":
            return False
        with self._fallback_lock:
            if not self.accelerator_fallback_active or self._closed.is_set():
                return False
            with self._server_lock:
                server, self._server = self._server, None
                self._environment = replacement
                self._fallback_attempted = False
            if server is not None:
                server.close()
        logger.info(
            "已重新启用推理后端：%s，设备：%s",
            replacement.backend.upper(),
            replacement.device,
        )
        return True

    def close(self) -> None:
        self._closed.set()
        with self._server_lock:
            server, self._server = self._server, None
        if server is not None:
            server.close()

    def __enter__(self) -> LocalVisionScorer:
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exception_type, exception, traceback
        self.close()

    def _invoke(self, image: Path, prompt: str) -> str:
        if self._closed.is_set():
            raise InferenceError("本地评分器已经关闭")
        active_environment = self._environment
        try:
            return self._server_for().complete(image, prompt)
        except InferenceError as exc:
            if self._closed.is_set():
                raise
            if self._fallback_to_cpu(active_environment, str(exc)):
                return self._invoke(image, prompt)
            raise

    def _server_for(self) -> LlamaServer:
        with self._server_lock:
            if self._closed.is_set():
                raise InferenceError("本地评分器已经关闭")
            environment = self._environment
            if self._server is not None:
                return self._server
            slots = self._workers if environment.backend != "cpu" else 1
            self._server = LlamaServer(environment, slots=slots)
            return self._server

    def _fallback_to_cpu(
        self,
        failed_environment: RuntimeEnvironment,
        reason: str,
    ) -> bool:
        if failed_environment.backend == "cpu" or self._closed.is_set():
            return False
        with self._fallback_lock:
            if self._closed.is_set():
                return False
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
            replacement = ensure_runtime_environment(force_cpu=True)
            with self._server_lock:
                server, self._server = self._server, None
                self._environment = replacement
            if server is not None:
                server.close()
            logger.info(
                "已切换推理后端：%s，设备：%s",
                replacement.backend.upper(),
                replacement.device,
            )
            return True
