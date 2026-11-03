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
from app.models import Post, PostComment, PostLike, PostView, User
from app.models.ticket import Ticket, TicketMessage

NOTIFICATION_TYPE = 'notification'


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


def add_comment(post, user, body):
    """Store the comment and notify everybody else who commented on this post before."""
    previous = {c.user_id for c in PostComment.query.filter_by(post_id=post.id).all()}
    comment = PostComment(post_id=post.id, user_id=user.id, body=body)
    post.last_activity = datetime.utcnow()
    db.session.add(comment)
    db.session.commit()
    _notify_repliers(post, user, body, previous - {user.id})
    return comment


def _notify_repliers(post, commenter, body, recipient_ids):
    if not recipient_ids:
        return
    from app.services.email import send_post_reply_email_async
    commenter_name = commenter.nick or commenter.name
    subject = f"New reply: {post.title}"[:200]
    text = f"{commenter_name}: {body}"[:500]
    for uid in recipient_ids:
        recipient = User.query.get(uid)
        if not recipient:
            continue
        ticket = Ticket.query.filter_by(user_id=uid, type=NOTIFICATION_TYPE, subject=subject).first()
        if not ticket:
            ticket = Ticket(user_id=uid, subject=subject, type=NOTIFICATION_TYPE, status='open')
            db.session.add(ticket)
            db.session.flush()
        ticket.updated_at = datetime.utcnow()
        db.session.add(TicketMessage(ticket_id=ticket.id, sender='admin', body=text, is_read=False))
        try:
            if recipient.notif_subscription is not False and recipient.email:
                send_post_reply_email_async(recipient.email, recipient.name, commenter_name, post.title, body)
        except Exception as e:
            print(f"POST REPLY EMAIL ERROR: {e}", flush=True)
    db.session.commit()
