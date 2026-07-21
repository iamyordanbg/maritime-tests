from ..extensions import db
from datetime import datetime

class Review(db.Model):
    """Отзиви от потребители за платформата - показвани в landing страницата
    ('What our customers say') само след admin одобрение.

    visibility='google' -> display_name/display_picture_url се попълват от
    Google OAuth данните на потребителя (реално, проверимо име/снимка).
    visibility='anonymous' -> display_name е генеричен placeholder
    ('Anonymous Sailor'), display_picture_url е null - потребителят е избрал
    да не разкрива самоличността си.

    role е свободен текст, попълван от самия потребител (напр.
    'Watch Officer, Varna'), НЕ идва от OAuth - не е проверимо поле,
    само декоративно за landing показването.
    """
    id                  = db.Column(db.Integer, primary_key=True)
    user_id             = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    stars               = db.Column(db.Integer, nullable=False)  # 1-5
    text                = db.Column(db.String(1000), nullable=False)
    visibility          = db.Column(db.String(20), default='anonymous')  # anonymous / google
    display_name        = db.Column(db.String(150), nullable=True)
    display_picture_url = db.Column(db.String(500), nullable=True)
    role                = db.Column(db.String(150), nullable=True)
    status              = db.Column(db.String(20), default='pending')  # pending / approved / rejected
    created_at          = db.Column(db.DateTime, default=datetime.utcnow)
