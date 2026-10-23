"""
tests/integration/test_review_reply_image_edit.py
=================================================
Админ: снимка към отговора на сайта (качване/смяна/махане) и редакция на отзиви.
"""
import io
import os

import pytest
from PIL import Image

from app.models.review import Review
from app.utils import image_upload

AJAX = {'X-Requested-With': 'XMLHttpRequest'}


@pytest.fixture(autouse=True)
def _env(db, tmp_path, monkeypatch):
    monkeypatch.setattr(image_upload, 'UPLOAD_FOLDER', str(tmp_path))
    Review.query.delete()
    db.session.commit()
    yield
    Review.query.delete()
    db.session.commit()


def _admin(client):
    client.post('/login', data={'email': 'admin@test.bg', 'password': 'Admin123'}, headers=AJAX)


def _review(db, user, **kw):
    base = dict(user_id=user.id, stars=4, text='Original', status='approved',
                visibility='account', display_name='Ivan Petrov', role='Cadet')
    base.update(kw)
    r = Review(**base)
    db.session.add(r)
    db.session.commit()
    return r


def _png(width=1200, height=600):
    buf = io.BytesIO()
    Image.new('RGB', (width, height), (200, 30, 30)).save(buf, 'PNG')
    buf.seek(0)
    return buf


def _files(tmp_path):
    return sorted(os.listdir(tmp_path))


def test_reply_with_image_saved_resized_and_public(client, db, admin_user, free_user, tmp_path):
    r = _review(db, free_user)
    _admin(client)
    res = client.post(f'/admin/reviews/{r.id}/reply',
                      data={'reply': 'Thanks!', 'image': (_png(), 'p.png')}, content_type='multipart/form-data')
    data = res.get_json()
    assert data['success'] and data['image'].startswith('/feed/img/') and data['image'].endswith('.webp')
    files = _files(tmp_path)
    assert len(files) == 1
    with Image.open(tmp_path / files[0]) as img:
        assert img.format == 'WEBP' and img.width == 800
    item = client.get('/api/reviews/public').get_json()[0]
    assert item['reply'] == 'Thanks!' and item['reply_image'] == data['image']


def test_image_only_reply_is_allowed(client, db, admin_user, free_user, tmp_path):
    r = _review(db, free_user)
    _admin(client)
    res = client.post(f'/admin/reviews/{r.id}/reply', data={'reply': '', 'image': (_png(), 'p.png')},
                      content_type='multipart/form-data')
    assert res.get_json()['success']
    item = client.get('/api/reviews/public').get_json()[0]
    assert item['reply'] == '' and item['reply_image']


def test_replacing_and_removing_image_deletes_old_file(client, db, admin_user, free_user, tmp_path):
    r = _review(db, free_user)
    _admin(client)
    client.post(f'/admin/reviews/{r.id}/reply', data={'reply': 'A', 'image': (_png(), 'a.png')},
                content_type='multipart/form-data')
    client.post(f'/admin/reviews/{r.id}/reply', data={'reply': 'A', 'image': (_png(300, 300), 'b.png')},
                content_type='multipart/form-data')
    assert len(_files(tmp_path)) == 1  # старата е изтрита
    # текст без нов файл не пипа снимката
    client.post(f'/admin/reviews/{r.id}/reply', json={'reply': 'A2'})
    assert len(_files(tmp_path)) == 1 and db.session.get(Review, r.id).admin_reply_image
    res = client.post(f'/admin/reviews/{r.id}/reply', data={'reply': 'A2', 'remove_image': '1'},
                      content_type='multipart/form-data')
    assert res.get_json()['image'] == '' and _files(tmp_path) == []


def test_remove_reply_clears_text_and_image(client, db, admin_user, free_user, tmp_path):
    r = _review(db, free_user)
    _admin(client)
    client.post(f'/admin/reviews/{r.id}/reply', data={'reply': 'A', 'image': (_png(), 'a.png')},
                content_type='multipart/form-data')
    client.post(f'/admin/reviews/{r.id}/reply', data={'reply': '', 'remove_image': '1'},
                content_type='multipart/form-data')
    item = client.get('/api/reviews/public').get_json()[0]
    assert item['reply'] == '' and item['reply_image'] == '' and _files(tmp_path) == []


@pytest.mark.parametrize('filename,payload', [('x.txt', b'hello'), ('x.png', b'not an image')])
def test_invalid_upload_rejected(client, db, admin_user, free_user, tmp_path, filename, payload):
    r = _review(db, free_user)
    _admin(client)
    res = client.post(f'/admin/reviews/{r.id}/reply',
                      data={'reply': 'A', 'image': (io.BytesIO(payload), filename)}, content_type='multipart/form-data')
    assert res.status_code == 400 and not res.get_json()['success']
    assert _files(tmp_path) == [] and db.session.get(Review, r.id).admin_reply is None


def test_too_large_upload_rejected(client, db, admin_user, free_user, tmp_path, monkeypatch):
    monkeypatch.setattr(image_upload, 'MAX_UPLOAD_BYTES', 100)
    r = _review(db, free_user)
    _admin(client)
    res = client.post(f'/admin/reviews/{r.id}/reply', data={'reply': 'A', 'image': (_png(), 'p.png')},
                      content_type='multipart/form-data')
    assert res.status_code == 400 and _files(tmp_path) == []


def test_unapproved_reply_with_image_leaves_no_file(client, db, admin_user, free_user, tmp_path):
    r = _review(db, free_user, status='pending')
    _admin(client)
    res = client.post(f'/admin/reviews/{r.id}/reply', data={'reply': 'A', 'image': (_png(), 'p.png')},
                      content_type='multipart/form-data')
    assert res.status_code == 400 and _files(tmp_path) == []


def test_create_review_with_reply_image(client, db, admin_user, tmp_path):
    _admin(client)
    res = client.post('/admin/reviews/create', content_type='multipart/form-data', data={
        'visibility': 'account', 'name': 'Ivan Petrov', 'stars': '5', 'text': 'Added', 'reply': 'Hi',
        'image': (_png(), 'p.png')})
    assert res.get_json()['success'] and len(_files(tmp_path)) == 1
    assert client.get('/api/reviews/public').get_json()[0]['reply_image']


def test_delete_review_removes_reply_image(client, db, admin_user, free_user, tmp_path):
    r = _review(db, free_user)
    _admin(client)
    client.post(f'/admin/reviews/{r.id}/reply', data={'reply': 'A', 'image': (_png(), 'a.png')},
                content_type='multipart/form-data')
    client.post(f'/admin/reviews/{r.id}/delete')
    assert _files(tmp_path) == []


def test_edit_named_review(client, db, admin_user, free_user):
    r = _review(db, free_user)
    _admin(client)
    res = client.post(f'/admin/reviews/{r.id}/edit',
                      json={'text': ' Edited text ', 'stars': '2', 'name': 'Petar Ivanov', 'role': ''})
    assert res.get_json() == {'success': True}
    r = db.session.get(Review, r.id)
    assert (r.text, r.stars, r.display_name, r.role) == ('Edited text', 2, 'Petar Ivanov', None)


def test_edit_anonymous_keeps_name_hidden(client, db, admin_user, free_user):
    r = _review(db, free_user, visibility='anonymous', display_name='Anonymous Sailor')
    _admin(client)
    client.post(f'/admin/reviews/{r.id}/edit', json={'text': 'New', 'stars': '5', 'name': 'Leak Name', 'role': 'X'})
    r = db.session.get(Review, r.id)
    assert r.display_name == 'Anonymous Sailor' and r.text == 'New' and r.role == 'X'


@pytest.mark.parametrize('bad', [{'text': ''}, {'stars': '9'}, {'name': ''}, {'text': 'x' * 1001}])
def test_edit_rejects_invalid(client, db, admin_user, free_user, bad):
    r = _review(db, free_user)
    _admin(client)
    payload = {'text': 'ok', 'stars': '3', 'name': 'Ivan', 'role': ''}
    payload.update(bad)
    res = client.post(f'/admin/reviews/{r.id}/edit', json=payload)
    assert res.status_code == 400 and db.session.get(Review, r.id).text == 'Original'


def test_edit_requires_admin(client, db, free_user):
    r = _review(db, free_user)
    client.post('/login', data={'email': 'free@test.bg', 'password': 'Test123'}, headers=AJAX)
    res = client.post(f'/admin/reviews/{r.id}/edit', json={'text': 'Hack', 'stars': '1', 'name': 'x'})
    assert res.status_code in (301, 302, 401, 403) and db.session.get(Review, r.id).text == 'Original'


def test_feed_post_image_still_saved_via_shared_util(client, db, admin_user, tmp_path):
    _admin(client)
    res = client.post('/admin/feed/post', content_type='multipart/form-data',
                      data={'title': 'T', 'body': 'B', 'image': (_png(), 'p.png')})
    assert res.get_json()['ok'] and len(_files(tmp_path)) == 1
    res = client.post('/admin/feed/post', content_type='multipart/form-data',
                      data={'title': 'T', 'body': 'B', 'image': (io.BytesIO(b'zzz'), 'p.png')})
    assert res.status_code == 400
