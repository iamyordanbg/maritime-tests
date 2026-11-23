"""
tests/integration/test_admin_edit_news_post.py
==============================================
Админ: редакция на новина (заглавие, текст, снимка) през GET /admin/feed/post/<id> и POST /admin/feed/post/<id>/edit.
Замененият/махнатият файл се изтрива от хранилището след успешното записване; при отказ новата снимка не остава.
"""
import importlib
import io

import pytest
from PIL import Image

from app.models import Post, PostView
from app.utils import image_upload

feed_routes = importlib.import_module('app.routes.feed')
AJAX = {'X-Requested-With': 'XMLHttpRequest'}


@pytest.fixture
def folder(tmp_path, monkeypatch):
    monkeypatch.setattr(image_upload, 'UPLOAD_FOLDER', str(tmp_path))
    monkeypatch.setattr(feed_routes, 'UPLOAD_FOLDER', str(tmp_path))
    for k in ('R2_ACCOUNT_ID', 'R2_ACCESS_KEY_ID', 'R2_SECRET_ACCESS_KEY', 'R2_BUCKET_NAME', 'R2_PUBLIC_URL'):
        monkeypatch.delenv(k, raising=False)
    return tmp_path


@pytest.fixture
def post(db, folder):
    (folder / 'old.webp').write_bytes(b'x')
    p = Post(title='Old title', body='Old body', image_url='/feed/img/old.webp')
    db.session.add(p)
    db.session.commit()
    yield p
    PostView.query.filter_by(post_id=p.id).delete()
    db.session.delete(Post.query.get(p.id)) if Post.query.get(p.id) else None
    db.session.commit()


def _admin(client):
    client.post('/login', data={'email': 'admin@test.bg', 'password': 'Admin123'}, headers=AJAX)


def _png(name='n.png'):
    buf = io.BytesIO()
    Image.new('RGB', (30, 20), 'green').save(buf, 'PNG')
    buf.seek(0)
    return (buf, name)


def _edit(client, pid, **form):
    return client.post(f'/admin/feed/post/{pid}/edit', data=form, content_type='multipart/form-data')


def test_get_returns_fields_and_does_not_count_a_view(client, db, admin_user, post):
    _admin(client)
    data = client.get(f'/admin/feed/post/{post.id}').get_json()
    assert data == {'id': post.id, 'title': 'Old title', 'body': 'Old body', 'image_url': '/feed/img/old.webp'}
    assert (Post.query.get(post.id).views or 0) == 0


def test_only_admin_can_read_or_edit(client, db, basic_user, post):
    client.post('/login', data={'email': 'basic@test.bg', 'password': 'Test123'}, headers=AJAX)
    assert client.get(f'/admin/feed/post/{post.id}').status_code == 403
    assert _edit(client, post.id, title='x', body='y').status_code == 403
    assert Post.query.get(post.id).title == 'Old title'


def test_edit_title_and_body_keeps_the_picture(client, db, admin_user, post, folder):
    _admin(client)
    res = _edit(client, post.id, title='  New title ', body='New body')
    assert res.status_code == 200 and res.get_json()['title'] == 'New title'
    p = Post.query.get(post.id)
    assert (p.title, p.body, p.image_url) == ('New title', 'New body', '/feed/img/old.webp')
    assert (folder / 'old.webp').exists()


def test_new_picture_replaces_and_deletes_the_old_file(client, db, admin_user, post, folder):
    _admin(client)
    res = _edit(client, post.id, title='T', body='B', image=_png())
    assert res.status_code == 200
    url = Post.query.get(post.id).image_url
    assert url.startswith('/feed/img/') and url != '/feed/img/old.webp'
    assert (folder / url.rsplit('/', 1)[1]).is_file()
    assert not (folder / 'old.webp').exists()


def test_remove_image_drops_the_picture_and_the_file(client, db, admin_user, post, folder):
    _admin(client)
    assert _edit(client, post.id, title='T', body='B', remove_image='1').status_code == 200
    assert Post.query.get(post.id).image_url == ''
    assert not (folder / 'old.webp').exists()


@pytest.mark.parametrize('title,body,msg', [('', 'B', 'required'), ('T', '  ', 'required'), ('x' * 201, 'B', 'too long')])
def test_validation_refuses_the_change_and_drops_a_just_stored_picture(client, db, admin_user, post, folder, title, body, msg):
    _admin(client)
    before = set(p.name for p in folder.iterdir())
    res = _edit(client, post.id, title=title, body=body, image=_png())
    assert res.status_code == 400 and msg in res.get_json()['error']
    p = Post.query.get(post.id)
    assert (p.title, p.image_url) == ('Old title', '/feed/img/old.webp')
    assert set(x.name for x in folder.iterdir()) == before          # the new file did not stay behind


def test_bad_image_is_a_400_and_nothing_changes(client, db, admin_user, post):
    _admin(client)
    res = _edit(client, post.id, title='T', body='B', image=(io.BytesIO(b'not an image'), 'x.png'))
    assert res.status_code == 400
    assert Post.query.get(post.id).title == 'Old title'


def test_edit_unknown_post_is_404(client, db, admin_user):
    _admin(client)
    assert _edit(client, 999999, title='T', body='B').status_code == 404


# ---------------------------------------------------------------------------
# Author (the avatar in front of the title on the dashboard)
# ---------------------------------------------------------------------------
def test_new_post_remembers_its_author_and_latest_exposes_the_current_avatar(client, db, admin_user, folder):
    _admin(client)
    res = client.post('/admin/feed/post', data={'title': 'By admin', 'body': 'b'}, content_type='multipart/form-data')
    pid = res.get_json()['id']
    try:
        assert Post.query.get(pid).author_id == admin_user.id
        row = next(p for p in client.get('/feed/latest?limit=50').get_json() if p['id'] == pid)
        assert row['author'] == 'Administrator' and row['author_avatar'] == ''
        admin_user.avatar_version, admin_user.avatar_data = 3, b'\xff\xd8jpg'
        db.session.commit()
        row = next(p for p in client.get('/feed/latest?limit=50').get_json() if p['id'] == pid)
        assert row['author_avatar'] == f'/feed/avatar/{admin_user.id}?v=3'          # a new photo = a new URL, nothing stored in the post
        assert client.get(row['author_avatar']).status_code == 200
    finally:
        admin_user.avatar_version, admin_user.avatar_data = 0, None
        Post.query.filter_by(id=pid).delete()
        db.session.commit()


def test_post_without_author_has_no_avatar_fields_filled(client, db, post):
    row = next(p for p in client.get('/feed/latest?limit=50').get_json() if p['id'] == post.id)
    assert row['author'] == '' and row['author_avatar'] == ''
