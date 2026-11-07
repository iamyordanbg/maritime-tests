"""
app/services/feed.py
====================
Business logic for the news feed: unique views, likes, comments and
"new reply" notifications (in-platform inbox message + email).
"""
import uuid
from datetime import datetime
from flask import session
from sqlalchemy.exc import IntegrityError
from app.extensions import db
from app.models import Post, PostComment, PostLike, PostCommentLike, PostView, User, Notification


def viewer_key():
    """Registered users are counted by id, visitors by an anonymous session id."""
    if session.get('user_id'):
        return f"u{session['user_id']}"
    if not session.get('vid'):
        session['vid'] = uuid.uuid4().hex
    return f"s{session['vid']}"


def register_view(post):
    """Count the current viewer once per post. Returns the post's view total."""
    key = viewer_key()
    if not PostView.query.filter_by(post_id=post.id, viewer_key=key).first():
        try:
            db.session.add(PostView(post_id=post.id, viewer_key=key))
            post.views = (post.views or 0) + 1
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
    return post.views or 0


def stats_for(post_ids, user_id=None):
    """{post_id: {'comments': n, 'likes': n, 'liked': bool}} in three queries."""
    if not post_ids:
        return {}
    comments = dict(db.session.query(PostComment.post_id, db.func.count(PostComment.id))
                    .filter(PostComment.post_id.in_(post_ids)).group_by(PostComment.post_id).all())
    likes = dict(db.session.query(PostLike.post_id, db.func.count(PostLike.id))
                 .filter(PostLike.post_id.in_(post_ids)).group_by(PostLike.post_id).all())
    mine = set()
    if user_id:
        mine = {r[0] for r in db.session.query(PostLike.post_id)
                .filter(PostLike.post_id.in_(post_ids), PostLike.user_id == user_id).all()}
    return {pid: {'comments': comments.get(pid, 0), 'likes': likes.get(pid, 0), 'liked': pid in mine}
            for pid in post_ids}


def toggle_like(post, user_id):
    existing = PostLike.query.filter_by(post_id=post.id, user_id=user_id).first()
    if existing:
        db.session.delete(existing)
        liked = False
    else:
        db.session.add(PostLike(post_id=post.id, user_id=user_id))
        liked = True
    try:
        db.session.commit()
    except IntegrityError:  # double tap raced with itself: the like already exists
        db.session.rollback()
        liked = True
    count = PostLike.query.filter_by(post_id=post.id).count()
    return liked, count


def toggle_comment_like(comment, user_id):
    """Like / unlike a comment. Returns (liked, total likes of the comment)."""
    existing = PostCommentLike.query.filter_by(comment_id=comment.id, user_id=user_id).first()
    if existing:
        db.session.delete(existing)
        liked = False
    else:
        db.session.add(PostCommentLike(comment_id=comment.id, user_id=user_id))
        liked = True
    try:
        db.session.commit()
    except IntegrityError:  # double tap raced with itself: the like already exists
        db.session.rollback()
        liked = True
    return liked, PostCommentLike.query.filter_by(comment_id=comment.id).count()


def _threads(comments, likes):
    """Group one post's comments: returns (top-level comments ranked by engagement, {top id: [replies, oldest first]}).
    Engagement = likes + number of replies; older first on a tie. A reply to a reply belongs to its top-level comment."""
    by_id = {c.id: c for c in comments}

    def root(c):
        while c.parent_id and c.parent_id in by_id:
            c = by_id[c.parent_id]
        return c.id

    replies = {}
    for c in comments:
        if c.parent_id:
            replies.setdefault(root(c), []).append(c)
    tops = [c for c in comments if not c.parent_id]
    tops.sort(key=lambda c: (-(likes.get(c.id, 0) + len(replies.get(c.id, []))), c.created_at, c.id))
    return tops, replies


def _like_counts(ids):
    if not ids:
        return {}
    return dict(db.session.query(PostCommentLike.comment_id, db.func.count(PostCommentLike.id))
                .filter(PostCommentLike.comment_id.in_(ids)).group_by(PostCommentLike.comment_id).all())


def reply_to_name(comment, by_id=None):
    """Display name of the author a reply answers ('' for a top-level comment)."""
    if not comment.parent_id:
        return ''
    parent = (by_id or {}).get(comment.parent_id) or PostComment.query.get(comment.parent_id)
    return display_name(parent.user) if parent else ''


def comments_page(post, user_id=None, offset=0, limit=3):
    """Top-level comments, most engaging first (likes + replies), `limit` at a time.
    Every returned comment carries `likes`, `liked` and its `replies`. Returns (page, total top-level comments)."""
    all_comments = PostComment.query.filter_by(post_id=post.id).order_by(PostComment.created_at, PostComment.id).all()
    by_id = {c.id: c for c in all_comments}
    likes = _like_counts(list(by_id))
    mine = {r[0] for r in db.session.query(PostCommentLike.comment_id)
            .filter(PostCommentLike.comment_id.in_(list(by_id)), PostCommentLike.user_id == user_id).all()} if by_id and user_id else set()
    tops, replies = _threads(all_comments, likes)
    page = tops[offset:offset + limit]
    return [(c, likes.get(c.id, 0), c.id in mine,
             [(r, likes.get(r.id, 0), r.id in mine, reply_to_name(r, by_id)) for r in replies.get(c.id, [])])
            for c in page], len(tops)


def top_comments_for(post_ids, n=2):
    """{post_id: [{'user', 'body', 'likes', 'replies'}]} - the n most engaging top-level comments of each post (preview)."""
    if not post_ids:
        return {}
    rows = PostComment.query.filter(PostComment.post_id.in_(post_ids)).order_by(PostComment.created_at, PostComment.id).all()
    likes = _like_counts([c.id for c in rows])
    by_post = {}
    for c in rows:
        by_post.setdefault(c.post_id, []).append(c)
    out = {}
    for pid, comments in by_post.items():
        tops, replies = _threads(comments, likes)
        out[pid] = [{'user': display_name(c.user), 'body': c.body, 'likes': likes.get(c.id, 0), 'replies': len(replies.get(c.id, []))}
                    for c in tops[:n]]
    return out


def display_name(user):
    """Name shown next to comments. The admin is always shown in English."""
    if user.is_admin:
        return 'Administrator'
    return user.nick or user.name


def add_comment(post, user, body, parent_id=None):
    """Store the comment (optionally a reply to another comment of the same post) and notify
    the parent's author and everybody else who commented on this post before."""
    parent = None
    if parent_id:
        parent = PostComment.query.filter_by(id=parent_id, post_id=post.id).first()
        if not parent:
            raise ValueError('invalid parent')
    previous = {c.user_id for c in PostComment.query.filter_by(post_id=post.id).all()}
    comment = PostComment(post_id=post.id, user_id=user.id, body=body, parent_id=parent.id if parent else None)
    post.last_activity = datetime.utcnow()
    db.session.add(comment)
    db.session.commit()
    _notify(post, comment, user, body, previous - {user.id}, parent.user_id if parent else None)
    return comment


def _notify(post, comment, commenter, body, recipient_ids, parent_author_id):
    """One in-platform notification (+ email) per person: 'reply' for the comment's author, 'comment' for the rest."""
    from app.services.email import send_post_reply_email_async
    if parent_author_id and parent_author_id != commenter.id:
        recipient_ids = set(recipient_ids) | {parent_author_id}
    if not recipient_ids:
        return
    actor = display_name(commenter)
    for uid in recipient_ids:
        recipient = User.query.get(uid)
        if not recipient:
            continue
        kind = 'reply' if uid == parent_author_id else 'comment'
        db.session.add(Notification(user_id=uid, post_id=post.id, comment_id=comment.id,
                                    kind=kind, actor_name=actor, body=body[:300]))
        try:
            if recipient.notif_subscription is not False and recipient.email:
                send_post_reply_email_async(recipient.email, recipient.name, actor, post.title, body, kind)
        except Exception as e:
            print(f"POST REPLY EMAIL ERROR: {e}", flush=True)
    db.session.commit()


def notifications_for(user_id, limit=30):
    rows = (Notification.query.filter_by(user_id=user_id)
            .order_by(Notification.created_at.desc()).limit(limit).all())
    unread = Notification.query.filter_by(user_id=user_id, is_read=False).count()
    return rows, unread


def mark_read(user_id, notification_id=None):
    q = Notification.query.filter_by(user_id=user_id, is_read=False)
    if notification_id:
        q = q.filter_by(id=notification_id)
    q.update({'is_read': True})
    db.session.commit()
