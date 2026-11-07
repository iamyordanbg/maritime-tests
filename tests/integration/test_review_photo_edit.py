"""
tests/integration/test_review_reply_image_edit.py
=================================================
Админ: снимка на автора на ръчно добавен отзив (показва се на мястото на аватара) и редакция.
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


def _create(client, **kw):
    data = {'visibility': 'account', 'name': 'Ivan Petrov', 'stars': '5', 'text': 'Added'}
    data.update(kw)
    return client.post('/admin/reviews/create', data=data, content_type='multipart/form-data')


def _public(client):
    return client.get('/api/reviews/public').get_json()[0]


def test_create_review_with_photo_saved_small_and_public(client, db, admin_user, tmp_path):
    _admin(client)
    res = _create(client, photo=(_png(), 'p.png'))
    assert res.get_json()['success']
    files = _files(tmp_path)
    assert len(files) == 1
    with Image.open(tmp_path / files[0]) as img:
        assert img.format == 'WEBP' and img.width == 256
    item = _public(client)
    assert item['picture'] == '/feed/img/' + files[0]
    assert item['initials'] == '' and item['avatar'] is None and item['name'] == 'Ivan Petrov'


def test_photo_ignored_for_anonymous_review(client, db, admin_user, tmp_path):
    _admin(client)
    _create(client, visibility='anonymous', photo=(_png(), 'p.png'))
    assert _files(tmp_path) == [] and _public(client)['picture'] is None


@pytest.mark.parametrize('filename,payload', [('x.txt', b'hello'), ('x.png', b'not an image')])
def test_invalid_photo_rejected(client, db, admin_user, tmp_path, filename, payload):
    _admin(client)
    res = _create(client, photo=(io.BytesIO(payload), filename))
    assert res.status_code == 400 and Review.query.count() == 0 and _files(tmp_path) == []


def test_too_large_photo_rejected(client, db, admin_user, tmp_path, monkeypatch):
    monkeypatch.setattr(image_upload, 'MAX_UPLOAD_BYTES', 100)
    _admin(client)
    assert _create(client, photo=(_png(), 'p.png')).status_code == 400 and _files(tmp_path) == []


def test_invalid_review_with_photo_leaves_no_file(client, db, admin_user, tmp_path):
    _admin(client)
    assert _create(client, text='', photo=(_png(), 'p.png')).status_code == 400
    assert _files(tmp_path) == []


def _edit(client, review_id, **kw):
    data = {'text': 'Edited', 'stars': '4', 'name': 'Ivan Petrov', 'role': ''}
    data.update(kw)
    return client.post(f'/admin/reviews/{review_id}/edit', data=data, content_type='multipart/form-data')


def test_edit_replaces_and_removes_photo(client, db, admin_user, tmp_path):
    _admin(client)
    _create(client, photo=(_png(), 'a.png'))
    rid = Review.query.one().id
    assert _edit(client, rid, photo=(_png(300, 300), 'b.png')).get_json()['success']
    assert len(_files(tmp_path)) == 1  # старата е изтрита
    _edit(client, rid)  # без файл - снимката остава
    assert len(_files(tmp_path)) == 1 and db.session.get(Review, rid).display_picture_url
    _edit(client, rid, remove_photo='1')
    assert _files(tmp_path) == [] and db.session.get(Review, rid).display_picture_url is None


def test_customer_review_photo_cannot_be_changed_by_admin(client, db, admin_user, free_user, tmp_path):
    r = _review(db, free_user, display_picture_url='https://example.com/google.jpg')
    _admin(client)
    _edit(client, r.id, photo=(_png(), 'x.png'))
    assert db.session.get(Review, r.id).display_picture_url == 'https://example.com/google.jpg'
    assert _files(tmp_path) == []
    _edit(client, r.id, remove_photo='1')
    assert db.session.get(Review, r.id).display_picture_url == 'https://example.com/google.jpg'


def test_edit_form_shows_photo_field_only_for_admin_made_named_reviews(client, db, admin_user, free_user):
    _admin(client)
    _create(client)
    _review(db, free_user, text='Customer review')
    html = client.get('/admin/reviews?status=approved').get_data(as_text=True)
    assert html.count('Reviewer photo (shown instead of the avatar)') == 1


def test_delete_review_removes_photo(client, db, admin_user, tmp_path):
    _admin(client)
    _create(client, photo=(_png(), 'a.png'))
    client.post(f'/admin/reviews/{Review.query.one().id}/delete')
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
