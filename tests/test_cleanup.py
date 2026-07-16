from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path
import signal

import pytest

from sunsetscore.reporting.markdown import write_markdown_report
from sunsetscore.results import IndependentScoreResult
from sunsetscore.runtime import download
from sunsetscore.runtime.specs import ArtifactSpec
from sunsetscore.termination import TerminationRequested


class InterruptedResponse:
    status = 200

    def __init__(self) -> None:
        self._first_read = True

    def __enter__(self):
        return self

    def __exit__(self, *args) -> None:
        return None

    def getcode(self) -> int:
        return self.status

    def read(self, size: int) -> bytes:
        del size
        if self._first_read:
            self._first_read = False
            return b"partial"
        raise TerminationRequested(signal.SIGTERM)


def test_interrupted_download_removes_partial_cache(tmp_path, monkeypatch) -> None:
    payload = b"partial-download"
    spec = ArtifactSpec(
        filename="artifact.bin",
        url="https://example.invalid/artifact",
        size=len(payload),
        sha256=sha256(payload).hexdigest(),
    )
    destination = tmp_path / spec.filename
    partial = tmp_path / f"{spec.filename}.part"
    monkeypatch.setattr(
        download, "urlopen", lambda *args, **kwargs: InterruptedResponse()
    )

    with pytest.raises(TerminationRequested):
        download.ensure_download(spec, destination)

    assert not partial.exists()
    assert not destination.exists()


def test_interrupted_report_write_removes_temporary_file(tmp_path, monkeypatch) -> None:
    result = IndependentScoreResult(
        root_directory=str(tmp_path),
        generated_at="2026-07-16T12:00:00+08:00",
        model_version="fake-v1",
        report_path="",
        directories=(),
    )

    def interrupted_write(path: Path, data: str, *, encoding: str) -> None:
        del data
        with path.open("w", encoding=encoding) as stream:
            stream.write("partial")
        raise TerminationRequested(signal.SIGTERM)

    monkeypatch.setattr(Path, "write_text", interrupted_write)

    with pytest.raises(TerminationRequested):
        write_markdown_report(result, tmp_path, filename_timestamp="20260716-120000")

    temporary = tmp_path / f".sunsetscore-analysis-20260716-120000.md.{os.getpid()}.tmp"
    assert not temporary.exists()
