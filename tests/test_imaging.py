from __future__ import annotations

from PIL import Image
import pytest

from sunsetscore.errors import ImagePreparationError
from sunsetscore.imaging import prepared_image


def test_prepared_image_is_rgb_and_limited_to_1280_pixels(tmp_path) -> None:
    source = tmp_path / "large.jpg"
    Image.new("RGBA", (2000, 1000), (255, 100, 20, 128)).convert("RGB").save(source)

    with prepared_image(source) as prepared:
        with Image.open(prepared) as image:
            assert image.mode == "RGB"
            assert image.size == (1280, 640)

    assert not prepared.exists()


def test_prepared_image_applies_exif_orientation(tmp_path) -> None:
    source = tmp_path / "rotated.jpg"
    exif = Image.Exif()
    exif[274] = 6
    Image.new("RGB", (20, 10), "red").save(source, exif=exif)

    with prepared_image(source) as prepared:
        with Image.open(prepared) as image:
            assert image.size == (10, 20)


def test_invalid_image_raises_expected_error(tmp_path) -> None:
    source = tmp_path / "broken.png"
    source.write_bytes(b"not an image")

    with pytest.raises(ImagePreparationError, match="无法解码"):
        with prepared_image(source):
            pass
