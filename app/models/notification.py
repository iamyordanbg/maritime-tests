from ..extensions import db
from datetime import datetime

class Notification(db.Model):
    """In-platform notification: somebody replied in a post the user commented on."""
    __tablename__ = 'notification'
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    post_id    = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    comment_id = db.Column(db.Integer, db.ForeignKey('post_comment.id'), nullable=True)
    kind       = db.Column(db.String(10), nullable=False)    # 'reply' (to your comment) | 'comment' (in your post thread)
    actor_name = db.Column(db.String(100), nullable=False)
    body       = db.Column(db.String(300), nullable=False)
    is_read    = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    post = db.relationship('Post', lazy=True)
