"""
app/utils/image_upload.py
=========================
Общо качване на снимки за feed постовете и за снимките на авторите на отзиви. Снимките се смаляват
и се записват като WebP.

Къде се пазят:
  * когато Cloudflare R2 е настроен (виж app/utils/r2_storage.py) - в R2 под ключ feed/<файл>.webp.
    Така не се губят при нов деплой / нова PR среда (дискът на контейнера е ephemeral);
  * иначе (локална разработка без R2) - на диска: Railway volume или static/feed_images.
В базата винаги се пази един и същ адрес /feed/img/<файл> - route-ът в app/routes/feed.py го сервира от диска
(старите файлове) или пренасочва към R2. Така адресът на R2 (r2.dev днес, свой домейн утре) се взима само от
конфигурацията R2_PUBLIC_URL и нищо в базата не трябва да се променя при смяната му.
"""
import io
import logging
import os
import uuid

from . import r2_storage

log = logging.getLogger(__name__)

R2_PREFIX = 'feed/'

IMAGE_URL_PREFIX = '/feed/img/'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
DEFAULT_MAX_WIDTH = 800
AVATAR_MAX_WIDTH = 256  # снимка на автор на отзив - показва се в малък кръг


class ImageUploadError(ValueError):
    """Файлът не е валидна снимка (формат, размер или повреден)."""


def _find_upload_folder():
    vol = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH', '')
    if vol and os.path.isdir(vol):
        path = os.path.join(vol, 'feed_images')
    else:
        path = os.path.join(os.path.dirname(__file__), '..', 'static', 'feed_images')
    os.makedirs(path, exist_ok=True)
    return path


UPLOAD_FOLDER = _find_upload_folder()
print(f"[FEED] UPLOAD_FOLDER = {UPLOAD_FOLDER}", flush=True)


def allowed_image(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_webp(file_storage, max_width=DEFAULT_MAX_WIDTH):
    """Записва качена снимка като WebP (смалена до max_width). Връща публичния URL.
    ImageUploadError при грешен формат, прекалено голям или повреден файл."""
    if not file_storage or not allowed_image(file_storage.filename or ''):
        raise ImageUploadError('Choose a PNG, JPG, GIF or WebP image.')
    stream = file_storage.stream
    stream.seek(0, os.SEEK_END)
    size = stream.tell()
    stream.seek(0)
    if size > MAX_UPLOAD_BYTES:
        raise ImageUploadError(f'Image is too large (max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB).')
    from PIL import Image
    try:
        img = Image.open(stream).convert('RGB')
    except Exception:
        raise ImageUploadError('The file is not a valid image.')
    if img.width > max_width:
        img = img.resize((max_width, int(img.height * max_width / img.width)), Image.LANCZOS)
    name = f"{uuid.uuid4().hex}.webp"
    if r2_storage.is_r2_configured():
        buf = io.BytesIO()
        img.save(buf, 'WEBP', quality=82, optimize=True)
        try:
            r2_storage.upload_bytes(R2_PREFIX + name, buf.getvalue(), 'image/webp')
        except Exception:
            # R2 е настроен, но качването пропадна: не пишем тихо на ephemeral диска (снимката ще изчезне).
            log.exception('R2 upload of a feed image failed')
            raise ImageUploadError('The image could not be saved. Please try again.')
    else:
        img.save(os.path.join(UPLOAD_FOLDER, name), 'WEBP', quality=82, optimize=True)
    return IMAGE_URL_PREFIX + name


def delete_uploaded(url):
    """Изтрива качена по-рано снимка по URL (безопасно: само файлове в UPLOAD_FOLDER и ключове feed/ в R2)."""
    if not url or not url.startswith(IMAGE_URL_PREFIX):
        return
    name = os.path.basename(url)
    path = os.path.join(UPLOAD_FOLDER, name)
    if os.path.isfile(path):
        os.remove(path)
    if r2_storage.is_r2_configured():
        try:
            r2_storage.delete_key(R2_PREFIX + name)
        except Exception:
            log.exception('R2 delete of a feed image failed')
