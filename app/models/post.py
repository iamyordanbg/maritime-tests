from ..extensions import db
from datetime import datetime

class Post(db.Model):
    __tablename__ = 'post'
    id           = db.Column(db.Integer, primary_key=True)
    title        = db.Column(db.String(200), nullable=False)
    body         = db.Column(db.Text, nullable=False)
    image_url    = db.Column(db.String(500), default='')
    views        = db.Column(db.Integer, default=0)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    last_activity= db.Column(db.DateTime, default=datetime.utcnow)  # за сортиране по активност

    comments = db.relationship('PostComment', backref='post', lazy=True,
                               order_by='PostComment.created_at')

class PostComment(db.Model):
    __tablename__ = 'post_comment'
    id         = db.Column(db.Integer, primary_key=True)
    post_id    = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    body       = db.Column(db.String(1000), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='post_comments', lazy=True)
