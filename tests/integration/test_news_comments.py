"""Desktop news reader: comments come 3 at a time, most-liked first; comments can be liked; deleting a post cleans up."""
import pytest
from werkzeug.security import generate_password_hash
from app.extensions import db
from app.models import Post, PostComment, PostCommentLike, User


@pytest.fixture
def world(app):
    with app.app_context():
        u = User(name="Reader", email="reader@test.bg", password=generate_password_hash("Test123"),
                 plan="free", is_active=False, email_verified=True)
        p = Post(title="P", body="Body", image_url="")
        db.session.add_all([u, p]); db.session.commit()
        cs = []
        for i in range(5):
            c = PostComment(post_id=p.id, user_id=u.id, body=f"c{i}")
            db.session.add(c); db.session.commit(); cs.append(c.id)
        reply = PostComment(post_id=p.id, user_id=u.id, body="reply", parent_id=cs[0])
        db.session.add(reply); db.session.commit()
        ids = (u.id, p.id, cs, reply.id)
    yield ids
    with app.app_context():
        PostCommentLike.query.delete()
        PostComment.query.filter_by(post_id=ids[1]).delete()
        Post.query.filter_by(id=ids[1]).delete()
        User.query.filter_by(id=ids[0]).delete()
        db.session.commit()


def _login(app):
    c = app.test_client()
    c.post('/login', data={'email': 'reader@test.bg', 'password': 'Test123'}, headers={'X-Requested-With': 'XMLHttpRequest'})
    return c


def test_comments_paged_by_likes(app, world):
    uid, pid, cs, reply_id = world
    c = _login(app)
    assert c.post(f'/feed/comment-like/{cs[3]}').get_json() == {'liked': True, 'likes': 1}
    first = c.get(f'/feed/post/{pid}/comments?limit=3&offset=0').get_json()
    # engagement = likes + replies: c0 (1 reply) and c3 (1 like) tie -> oldest first; the rest by age
    assert [x['body'] for x in first['comments']] == ['c0', 'c3', 'c1']
    assert first['total'] == 5 and first['has_more'] is True
    assert first['comments'][1]['liked'] is True and first['comments'][1]['likes'] == 1
    assert [r['body'] for r in first['comments'][0]['replies']] == ['reply']     # replies stay under their comment
    second = c.get(f'/feed/post/{pid}/comments?limit=3&offset=3').get_json()
    assert [x['body'] for x in second['comments']] == ['c2', 'c4'] and second['has_more'] is False


def test_comment_like_toggles_and_needs_login(app, world):
    uid, pid, cs, _ = world
    assert app.test_client().post(f'/feed/comment-like/{cs[0]}').status_code == 401
    c = _login(app)
    assert c.post(f'/feed/comment-like/{cs[0]}').get_json()['liked'] is True
    assert c.post(f'/feed/comment-like/{cs[0]}').get_json() == {'liked': False, 'likes': 0}


def test_comments_without_limit_keep_old_format(app, world):
    uid, pid, cs, _ = world
    data = _login(app).get(f'/feed/post/{pid}/comments').get_json()
    assert len(data['comments']) == 6 and 'total' not in data               # News Center still gets everything


def test_deleting_a_post_removes_comment_likes(app, world):
    uid, pid, cs, _ = world
    c = _login(app)
    c.post(f'/feed/comment-like/{cs[0]}')
    with app.app_context():
        admin = User(name="Adm", email="adm@test.bg", password=generate_password_hash("Test123"), plan="free",
                     is_active=False, email_verified=True, is_admin=True)
        db.session.add(admin); db.session.commit(); aid = admin.id
    a = app.test_client()
    a.post('/login', data={'email': 'adm@test.bg', 'password': 'Test123'}, headers={'X-Requested-With': 'XMLHttpRequest'})
    assert a.delete(f'/admin/feed/post/{pid}').status_code == 200
    with app.app_context():
        assert PostCommentLike.query.count() == 0
        User.query.filter_by(id=aid).delete(); db.session.commit()


def test_reply_to_any_comment_and_preview_of_top_two(app, world):
    uid, pid, cs, reply_id = world
    c = _login(app)
    r = c.post(f'/feed/comment/{pid}', json={'body': 'answer to the reply', 'parent_id': reply_id}).get_json()
    assert r['parent_id'] == reply_id and r['reply_to'] == 'Reader'
    page = c.get(f'/feed/post/{pid}/comments?limit=3').get_json()['comments']
    assert [x['body'] for x in page[0]['replies']] == ['reply', 'answer to the reply']   # a reply to a reply stays in the thread
    posts = c.get('/feed/latest?limit=50&top_comments=2').get_json()
    mine = next(p for p in posts if p['id'] == pid)
    assert [x['body'] for x in mine['top_comments']] == ['c0'] + [mine['top_comments'][1]['body']]
    assert mine['top_comments'][0]['replies'] == 2 and len(mine['top_comments']) == 2
    assert 'top_comments' not in c.get('/feed/latest?limit=50').get_json()[0]            # other callers are unchanged
