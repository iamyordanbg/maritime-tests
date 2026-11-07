"""Profile photo: validate the upload and turn it into a small square JPEG."""
import io
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_PIXELS = 25_000_000
SIZE = 256


def avatar_response(user):
    """The user's photo as an image response (the URL carries ?v=<version>, so the browser may cache it), or 404."""
    from flask import Response
    if not user or not user.avatar_version or not user.avatar_data:
        return ('', 404)
    return Response(user.avatar_data, mimetype='image/jpeg', headers={'Cache-Control': 'private, max-age=86400'})


class AvatarError(ValueError):
    """Message is safe to show to the user."""


def make_avatar(raw: bytes) -> bytes:
    if not raw:
        raise AvatarError('Choose a photo first.')
    if len(raw) > MAX_UPLOAD_BYTES:
        raise AvatarError('The photo is too large (max 5 MB).')
    try:
        img = Image.open(io.BytesIO(raw))
        if img.width * img.height > MAX_PIXELS:
            raise AvatarError('The photo has too many pixels.')
        img = ImageOps.exif_transpose(img)
        if img.mode in ('RGBA', 'LA', 'P'):
            img = img.convert('RGBA')
            bg = Image.new('RGB', img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[-1])
            img = bg
        else:
            img = img.convert('RGB')
    except AvatarError:
        raise
    except (UnidentifiedImageError, OSError, ValueError):
        raise AvatarError('This file is not a supported image (use JPG, PNG or WebP).')
    img = ImageOps.fit(img, (SIZE, SIZE), Image.LANCZOS)
    out = io.BytesIO()
    img.save(out, 'JPEG', quality=85, optimize=True)
    return out.getvalue()
