from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from platformdirs import user_data_path


HOME_ENVIRONMENT_VARIABLE = "SUNSETSCORE_HOME"


@dataclass(frozen=True, slots=True)
class RuntimePaths:
    home: Path

    @property
    def downloads(self) -> Path:
        return self.home / "downloads"

    @property
    def models(self) -> Path:
        return self.home / "models"

    @property
    def runtimes(self) -> Path:
        return self.home / "runtime"

    @property
    def install_lock(self) -> Path:
        return self.home / ".install.lock"

    def create(self) -> None:
        for path in (self.home, self.downloads, self.models, self.runtimes):
            path.mkdir(parents=True, exist_ok=True)


def get_runtime_paths() -> RuntimePaths:
    override = os.environ.get(HOME_ENVIRONMENT_VARIABLE)
    if override:
        home = Path(override).expanduser().resolve()
    else:
        home = user_data_path("SunsetScore", appauthor=False, ensure_exists=False)
    return RuntimePaths(home=home)
