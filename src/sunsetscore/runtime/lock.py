from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
from time import monotonic, sleep, time
from typing import Iterator

from ..errors import RuntimeInstallError
from ..log import logger


LOCK_TIMEOUT_SECONDS = 3600
STALE_LOCK_SECONDS = 6 * 3600


@contextmanager
def installation_lock(path: Path) -> Iterator[None]:
    started = monotonic()
    last_notice = -10.0
    acquired = False
    while not acquired:
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            _remove_stale_lock(path)
            elapsed = monotonic() - started
            if elapsed >= LOCK_TIMEOUT_SECONDS:
                raise RuntimeInstallError("等待其他 SunsetScore 安装进程超时")
            if elapsed - last_notice >= 10:
                logger.info("正在等待其他进程完成模型安装")
                last_notice = elapsed
            sleep(0.25)
            continue
        except OSError as exc:
            raise RuntimeInstallError(f"无法创建安装锁 {path}: {exc}") from exc

        with os.fdopen(descriptor, "w", encoding="ascii") as stream:
            stream.write(f"pid={os.getpid()}\ntime={int(time())}\n")
        acquired = True

    try:
        yield
    finally:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logger.warning("无法移除安装锁：%s", path)


def _remove_stale_lock(path: Path) -> None:
    try:
        age = time() - path.stat().st_mtime
        if age > STALE_LOCK_SECONDS:
            logger.warning("发现过期安装锁，正在清理：%s", path)
            path.unlink()
    except FileNotFoundError:
        pass
    except OSError:
        pass
