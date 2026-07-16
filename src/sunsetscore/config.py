from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 only
    import tomli as tomllib

from .errors import ConfigError


CONFIG_FILENAME = ".sunsetscore.toml"
DEFAULT_INTERVAL = 10


@dataclass(frozen=True, slots=True)
class AppConfig:
    interval: int = DEFAULT_INTERVAL


def load_config(input_directory: Path) -> AppConfig:
    path = input_directory / CONFIG_FILENAME
    if not path.exists():
        return AppConfig()
    if not path.is_file():
        raise ConfigError(f"配置路径不是普通文件: {path}")

    try:
        with path.open("rb") as stream:
            document = tomllib.load(stream)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"无法读取配置文件 {path}: {exc}") from exc

    _reject_unknown(document, {"sampling"}, "配置根节点")
    sampling = document.get("sampling", {})
    if not isinstance(sampling, dict):
        raise ConfigError("配置项 sampling 必须是表")
    _reject_unknown(sampling, {"interval"}, "sampling")

    interval = sampling.get("interval", DEFAULT_INTERVAL)
    if type(interval) is not int or interval < 1:
        raise ConfigError("sampling.interval 必须是大于等于 1 的整数")
    return AppConfig(interval=interval)


def resolve_interval(input_directory: Path, override: int | None) -> int:
    config = load_config(input_directory)
    if override is None:
        return config.interval
    if type(override) is not int or override < 1:
        raise ConfigError("interval 必须是大于等于 1 的整数")
    return override


def _reject_unknown(document: dict[str, Any], allowed: set[str], location: str) -> None:
    unknown = sorted(set(document) - allowed)
    if unknown:
        names = ", ".join(unknown)
        raise ConfigError(f"{location}包含未知配置项: {names}")
