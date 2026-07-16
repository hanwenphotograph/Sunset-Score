from __future__ import annotations

from pathlib import Path

import pytest

from sunsetscore.discovery import discover_images, sample_images
from sunsetscore.errors import InputError


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"image")


def test_non_recursive_scan_filters_formats_and_sorts_naturally(tmp_path) -> None:
    for name in ("photo10.JPG", "photo2.png", "photo1.jpeg", "notes.txt"):
        _touch(tmp_path / name)
    _touch(tmp_path / "nested" / "photo0.jpg")

    images = discover_images(tmp_path, recursive=False)

    assert [path.name for path in images] == [
        "photo1.jpeg",
        "photo2.png",
        "photo10.JPG",
    ]


def test_recursive_scan_is_one_global_relative_path_sequence(tmp_path) -> None:
    _touch(tmp_path / "b" / "photo1.jpg")
    _touch(tmp_path / "a2" / "photo1.jpg")
    _touch(tmp_path / "a10" / "photo1.jpg")

    images = discover_images(tmp_path, recursive=True)

    assert [path.relative_to(tmp_path).as_posix() for path in images] == [
        "a2/photo1.jpg",
        "a10/photo1.jpg",
        "b/photo1.jpg",
    ]


def test_sampling_starts_with_first_image() -> None:
    images = [Path(f"{number}.jpg") for number in range(1, 25)]

    assert sample_images(images, 10) == [images[0], images[10], images[20]]
    assert sample_images(images[:3], 10) == [images[0]]


def test_symlinked_image_is_skipped(tmp_path) -> None:
    source = tmp_path / "source.jpg"
    link = tmp_path / "link.jpg"
    _touch(source)
    try:
        link.symlink_to(source)
    except OSError:
        pytest.skip("symlink creation is unavailable")

    images = discover_images(tmp_path, recursive=True)

    assert images == [source]


def test_missing_input_fails(tmp_path) -> None:
    with pytest.raises(InputError, match="不存在"):
        discover_images(tmp_path / "missing", recursive=False)
