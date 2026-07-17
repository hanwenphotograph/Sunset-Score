from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import subprocess
from tempfile import TemporaryFile
from threading import Lock
from time import monotonic, sleep
from typing import BinaryIO
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..errors import InferenceError
from ..log import logger
from ..runtime import RuntimeEnvironment
from .command import server_command
from .protocol import request_body, response_content
from .settings import (
    INFERENCE_TIMEOUT_SECONDS,
    SERVER_HOST,
    SERVER_STARTUP_TIMEOUT_SECONDS,
)


class LlamaServer:
    def __init__(self, environment: RuntimeEnvironment, *, slots: int) -> None:
        self.environment = environment
        self.slots = slots
        try:
            self._port = _available_port()
        except OSError as exc:
            raise InferenceError(f"无法为本地推理服务分配端口: {exc}") from exc
        self._process: subprocess.Popen[bytes] | None = None
        self._log: BinaryIO | None = None
        self._lifecycle_lock = Lock()

    def complete(self, image: Path, prompt: str) -> str:
        self._ensure_started()
        request = Request(
            f"http://{SERVER_HOST}:{self._port}/v1/chat/completions",
            data=request_body(image, prompt),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=INFERENCE_TIMEOUT_SECONDS) as response:
                document = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[-500:]
            raise InferenceError(f"本地推理服务返回 HTTP {exc.code}: {detail}") from exc
        except (OSError, URLError, json.JSONDecodeError) as exc:
            raise InferenceError(f"无法访问本地推理服务: {exc}") from exc
        return response_content(document)

    def close(self) -> None:
        with self._lifecycle_lock:
            process, self._process = self._process, None
            log, self._log = self._log, None
        if process is not None:
            _stop_process(process)
        if log is not None:
            log.close()

    def _ensure_started(self) -> None:
        with self._lifecycle_lock:
            if self._process is not None and self._process.poll() is None:
                return
            if self._log is not None:
                self._log.close()
                self._log = None
            self._process = None
            self._start_locked()

    def _start_locked(self) -> None:
        log = TemporaryFile(mode="w+b")
        environment = os.environ.copy()
        environment["NO_COLOR"] = "1"
        command = server_command(self.environment, self._port, self.slots)
        logger.info("正在启动常驻推理服务：%d 个槽位", self.slots)
        try:
            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                env=environment,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except OSError as exc:
            log.close()
            raise InferenceError(f"无法启动本地推理服务: {exc}") from exc
        self._process = process
        self._log = log
        try:
            _wait_until_ready(process, self._port)
        except InferenceError as exc:
            self._process = None
            self._log = None
            _stop_process(process, graceful=False)
            detail = _log_tail(log)
            log.close()
            suffix = f": {detail}" if detail else ""
            raise InferenceError(f"{exc}{suffix}") from exc


def _wait_until_ready(process: subprocess.Popen[bytes], port: int) -> None:
    deadline = monotonic() + SERVER_STARTUP_TIMEOUT_SECONDS
    request = Request(f"http://{SERVER_HOST}:{port}/health")
    while monotonic() < deadline:
        if process.poll() is not None:
            raise InferenceError(f"本地推理服务提前退出，退出码为 {process.returncode}")
        try:
            with urlopen(request, timeout=1) as response:
                if response.status == 200:
                    return
        except (HTTPError, OSError, URLError):
            pass
        sleep(0.1)
    raise InferenceError("等待本地推理服务启动超时")


def _available_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind((SERVER_HOST, 0))
        return int(listener.getsockname()[1])


def _stop_process(
    process: subprocess.Popen[bytes],
    *,
    graceful: bool = True,
) -> None:
    if process.poll() is not None:
        return
    try:
        if graceful:
            process.terminate()
        else:
            process.kill()
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            process.kill()
            process.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            pass
    except OSError:
        pass


def _log_tail(stream: BinaryIO) -> str:
    stream.flush()
    size = stream.seek(0, os.SEEK_END)
    stream.seek(max(0, size - 2000))
    lines = stream.read().decode("utf-8", errors="replace").splitlines()
    return lines[-1][:500] if lines else ""
