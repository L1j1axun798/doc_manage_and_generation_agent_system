from io import BytesIO

import pytest
from PIL import Image

from apps.document_generation.exceptions import DocumentGenerationError
from apps.document_generation.image_assets import normalize_document_image


def _jpeg(width: int, height: int) -> bytes:
    image = Image.new("RGB", (width, height), "white")
    exif = Image.Exif()
    exif[0x010E] = "historical project metadata"
    output = BytesIO()
    image.save(output, format="JPEG", exif=exif)
    return output.getvalue()


def test_document_image_is_normalized_to_png_without_exif() -> None:
    content, media_type, width, height = normalize_document_image(_jpeg(1600, 900))

    assert media_type == "image/png"
    assert (width, height) == (1600, 900)
    with Image.open(BytesIO(content)) as normalized:
        assert normalized.format == "PNG"
        assert not normalized.getexif()


def test_document_image_rejects_resolution_below_a4_quality_threshold() -> None:
    with pytest.raises(DocumentGenerationError) as exc_info:
        normalize_document_image(_jpeg(800, 600))

    assert exc_info.value.default_code == "IMAGE_RESOLUTION_INSUFFICIENT"

