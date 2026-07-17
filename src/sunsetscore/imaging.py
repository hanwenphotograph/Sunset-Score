from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterator

from PIL import Image, ImageOps, UnidentifiedImageError

from .errors import ImagePreparationError


MAX_IMAGE_EDGE = 1024


@contextmanager
def prepared_image(source: Path) -> Iterator[Path]:
    """Normalize orientation, color mode, and size for deterministic inference."""

    try:
        with TemporaryDirectory(prefix="sunsetscore-image-") as temporary:
            destination = Path(temporary) / "input.png"
            _prepare(source, destination)
            yield destination
    except ImagePreparationError:
        raise
    except OSError as exc:
        raise ImagePreparationError(f"无法准备图片 {source}: {exc}") from exc


def _prepare(source: Path, destination: Path) -> None:
    try:
        with Image.open(source) as opened:
            oriented = ImageOps.exif_transpose(opened)
            try:
                with oriented.convert("RGB") as image:
                    image.thumbnail(
                        (MAX_IMAGE_EDGE, MAX_IMAGE_EDGE),
                        Image.Resampling.LANCZOS,
                    )
                    image.save(destination, format="PNG")
            finally:
                oriented.close()
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise ImagePreparationError(f"无法解码图片 {source}: {exc}") from exc
