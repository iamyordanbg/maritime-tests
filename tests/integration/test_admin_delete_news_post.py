"""
tests/integration/test_admin_delete_news_post.py
================================================
Админ: изтриване на новина с коментари и известия. На Postgres (внешните ключове се прилагат) известията сочат
към коментарите (notification.comment_id), затова те трябва да се изтрият ПРЕДИ коментарите - иначе заявката
пада с 500 и новината си остава (а интерфейсът мълчеше). Тестът включва прилагането на FK и в SQLite.
"""
import pytest
from sqlalchemy import text

from app.models import Notification, Post, PostComment, PostLike, PostView, User

AJAX = {'X-Requested-With': 'XMLHttpRequest'}


@pytest.fixture
def fk_on(db, admin_user, basic_user):
    """FK ON за теста; зависи от user фикстурите, за да се почисти ПРЕДИ тях."""
    db.session.commit()
    db.session.execute(text('PRAGMA foreign_keys=ON'))
    yield
    db.session.rollback()
    for model in (Notification, PostLike, PostView):
        model.query.delete()
    PostComment.query.update({'parent_id': None})
    PostComment.query.delete()
    Post.query.delete()
    db.session.commit()
    db.session.execute(text('PRAGMA foreign_keys=OFF'))


def _login_admin(client):
    client.post('/login', data={'email': 'admin@test.bg', 'password': 'Admin123'}, headers=AJAX)


def _post_with_thread(db, author):
    post = Post(title='T', body='B', image_url='')
    db.session.add(post)
    db.session.commit()
    c1 = PostComment(post_id=post.id, user_id=author.id, body='first')
    db.session.add(c1)
    db.session.commit()
    c2 = PostComment(post_id=post.id, user_id=author.id, parent_id=c1.id, body='reply')
    db.session.add(c2)
    db.session.commit()
    db.session.add_all([
        Notification(user_id=author.id, post_id=post.id, comment_id=c2.id, kind='reply', actor_name='A', body='x'),
        PostLike(post_id=post.id, user_id=author.id),
        PostView(post_id=post.id, viewer_key='k'),
    ])
    db.session.commit()
    return post.id


def test_delete_post_with_comments_replies_and_notifications(client, db, admin_user, basic_user, fk_on):
    pid = _post_with_thread(db, basic_user)
    _login_admin(client)
    res = client.delete(f'/admin/feed/post/{pid}')
    assert res.status_code == 200, res.data
    assert Post.query.get(pid) is None
    assert PostComment.query.filter_by(post_id=pid).count() == 0
    assert Notification.query.filter_by(post_id=pid).count() == 0


def test_failed_delete_answers_json_500_and_keeps_the_post(client, db, admin_user, basic_user, fk_on, monkeypatch):
    pid = _post_with_thread(db, basic_user)
    _login_admin(client)

    def boom(*a, **k):
        raise RuntimeError('db down')
    monkeypatch.setattr(db.session, 'delete', boom)
    res = client.delete(f'/admin/feed/post/{pid}')
    assert res.status_code == 500 and res.get_json()['error']
    monkeypatch.undo()
    assert Post.query.get(pid) is not None                       # връщане назад: нищо не е изтрито наполовина
    assert PostComment.query.filter_by(post_id=pid).count() == 2
