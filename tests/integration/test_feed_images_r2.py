"""
tests/integration/test_feed_images_r2.py
========================================
Снимките на новини и на автори на отзиви отиват в Cloudflare R2, когато той е настроен (иначе не оцеляват при нова
PR среда / нов деплой, защото дискът на контейнера е ephemeral). В базата остава същият адрес /feed/img/<файл>.
R2 клиентът е подменен - тестът не пипа истинския bucket.
"""
import importlib
import io

import pytest
from PIL import Image
from werkzeug.datastructures import FileStorage

from app.utils import image_upload, r2_storage

feed_routes = importlib.import_module('app.routes.feed')   # в пакета 'feed' е Blueprint-ът, не модулът

R2_ENV = {
    'R2_ACCOUNT_ID': 'acc', 'R2_ACCESS_KEY_ID': 'key', 'R2_SECRET_ACCESS_KEY': 'secret',
    'R2_BUCKET_NAME': 'bucket', 'R2_PUBLIC_URL': 'https://cdn.example.test/',
}


def _png_upload(name='photo.png'):
    buf = io.BytesIO()
    Image.new('RGB', (40, 30), 'red').save(buf, 'PNG')
    buf.seek(0)
    return FileStorage(stream=buf, filename=name)


@pytest.fixture
def folder(tmp_path, monkeypatch):
    monkeypatch.setattr(image_upload, 'UPLOAD_FOLDER', str(tmp_path))
    monkeypatch.setattr(feed_routes, 'UPLOAD_FOLDER', str(tmp_path))
    return tmp_path


@pytest.fixture
def r2(monkeypatch):
    for k, v in R2_ENV.items():
        monkeypatch.setenv(k, v)
    calls = {'put': [], 'delete': []}
    monkeypatch.setattr(r2_storage, 'upload_bytes', lambda key, body, ct: calls['put'].append((key, body, ct)))
    monkeypatch.setattr(r2_storage, 'delete_key', lambda key: calls['delete'].append(key))
    return calls


@pytest.fixture
def no_r2(monkeypatch):
    for k in R2_ENV:
        monkeypatch.delenv(k, raising=False)


def test_upload_goes_to_r2_not_to_disk(folder, r2):
    url = image_upload.save_webp(_png_upload())
    assert url.startswith('/feed/img/') and url.endswith('.webp')
    (key, body, content_type), = r2['put']
    assert key == 'feed/' + url.rsplit('/', 1)[1] and content_type == 'image/webp'
    assert Image.open(io.BytesIO(body)).format == 'WEBP'
    assert list(folder.iterdir()) == []                      # нищо не е останало на ephemeral диска


def test_failed_r2_upload_is_an_error_and_never_falls_back_to_disk(folder, r2, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError('network down')
    monkeypatch.setattr(r2_storage, 'upload_bytes', boom)
    with pytest.raises(image_upload.ImageUploadError):
        image_upload.save_webp(_png_upload())
    assert list(folder.iterdir()) == []


def test_without_r2_the_image_is_saved_on_disk_as_before(folder, no_r2):
    url = image_upload.save_webp(_png_upload())
    assert (folder / url.rsplit('/', 1)[1]).is_file()


def test_delete_removes_the_r2_object_and_only_for_our_urls(folder, r2):
    image_upload.delete_uploaded('/feed/img/abc123.webp')
    image_upload.delete_uploaded('/feed/img/../../etc/passwd')
    image_upload.delete_uploaded('https://elsewhere.test/x.webp')
    image_upload.delete_uploaded('')
    assert r2['delete'] == ['feed/abc123.webp', 'feed/passwd']   # basename: без излизане от feed/


def test_route_redirects_missing_local_file_to_r2_with_immutable_cache(client, folder, r2):
    res = client.get('/feed/img/abc123.webp')
    assert res.status_code == 302
    assert res.headers['Location'] == 'https://cdn.example.test/feed/abc123.webp'   # домейнът идва от R2_PUBLIC_URL
    assert 'immutable' in res.headers['Cache-Control']


def test_route_still_serves_old_files_from_disk(client, folder, r2):
    Image.new('RGB', (8, 8), 'blue').save(folder / 'old.webp', 'WEBP')
    res = client.get('/feed/img/old.webp')
    assert res.status_code == 200 and res.mimetype == 'image/webp'


def test_route_404_when_missing_and_no_r2(client, folder, no_r2):
    assert client.get('/feed/img/none.webp').status_code == 404


def test_admin_news_post_end_to_end_with_r2(client, db, admin_user, folder, r2):
    from app.models import Post
    client.post('/login', data={'email': 'admin@test.bg', 'password': 'Admin123'}, headers={'X-Requested-With': 'XMLHttpRequest'})
    res = client.post('/admin/feed/post', data={'title': 'T', 'body': 'B', 'image': (_png_upload().stream, 'p.png')},
                      content_type='multipart/form-data')
    assert res.status_code == 200, res.data
    post = Post.query.get(res.get_json()['id'])
    assert post.image_url.startswith('/feed/img/')                              # в базата - същият адрес като преди
    name = post.image_url.rsplit('/', 1)[1]
    assert r2['put'][0][0] == 'feed/' + name
    assert client.get(post.image_url).headers['Location'] == f'https://cdn.example.test/feed/{name}'
    assert client.delete(f'/admin/feed/post/{post.id}').status_code == 200      # изтриване на новината
    assert r2['delete'] == ['feed/' + name]                                     # махa и обекта в R2
