from __future__ import annotations

import pytest

from sunsetscore.config import DEFAULT_INTERVAL, load_config, resolve_interval
from sunsetscore.errors import ConfigError


def test_missing_config_uses_default(tmp_path) -> None:
    assert load_config(tmp_path).interval == DEFAULT_INTERVAL


def test_config_interval_and_command_override(tmp_path) -> None:
    (tmp_path / ".sunsetscore.toml").write_text(
        "[sampling]\ninterval = 7\n",
        encoding="utf-8",
    )

    assert resolve_interval(tmp_path, None) == 7
    assert resolve_interval(tmp_path, 3) == 3


@pytest.mark.parametrize(
    "content, expected",
    [
        ("unknown = 1\n", "未知配置项"),
        ("[sampling]\nintervel = 2\n", "intervel"),
        ("[sampling]\ninterval = 0\n", "大于等于 1"),
        ("[sampling]\ninterval = true\n", "大于等于 1"),
        ("sampling = 3\n", "必须是表"),
        ("[sampling\n", "无法读取配置文件"),
    ],
)
def test_invalid_config_fails_strictly(tmp_path, content: str, expected: str) -> None:
    (tmp_path / ".sunsetscore.toml").write_text(content, encoding="utf-8")

    with pytest.raises(ConfigError, match=expected):
        load_config(tmp_path)
