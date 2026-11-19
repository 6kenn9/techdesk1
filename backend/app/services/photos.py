"""Обробка фото пристроїв: перевірка формату, поворот за EXIF, стиснення й видалення метаданих."""
from io import BytesIO
from PIL import Image, ImageOps, UnidentifiedImageError
from ..core.security import fail

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_SIDE = 1600
MAX_PER_DEVICE = 30
FORMATS = {"JPEG", "MPO", "PNG", "WEBP"}
Image.MAX_IMAGE_PIXELS = 50_000_000

def normalize(data):
    """Повертає (jpeg_bytes, width, height). Повторне кодування прибирає EXIF, зокрема геолокацію."""
    try:
        with Image.open(BytesIO(data)) as source:
            if source.format not in FORMATS:
                raise UnidentifiedImageError
            # Розмір відомий із заголовка ще до розпакування: маленький файл може описувати гігантське зображення.
            # Pillow сам відхиляє лише вдвічі більші за MAX_IMAGE_PIXELS, тож межу перевіряємо тут.
            if source.width * source.height > Image.MAX_IMAGE_PIXELS:
                fail(413, "Зображення завелике: до 50 мегапікселів.")
            image = ImageOps.exif_transpose(source).convert("RGB")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, ValueError):
        fail(422, "Завантажте зображення у форматі JPEG, PNG або WebP.")
    image.thumbnail((MAX_SIDE, MAX_SIDE))
    output = BytesIO()
    image.save(output, "JPEG", quality=85, optimize=True)
    return output.getvalue(), image.width, image.height
