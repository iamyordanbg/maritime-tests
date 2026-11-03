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
from app.models import Post, PostComment, PostLike, PostView, User, Notification


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
