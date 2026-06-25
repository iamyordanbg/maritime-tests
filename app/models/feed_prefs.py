from ..extensions import db

class UserFeedPrefs(db.Model):
    __tablename__ = 'user_feed_prefs'
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)
    categories = db.Column(db.String(500), default='maritime,world')  # comma separated
    language   = db.Column(db.String(10), default='both')  # 'bg', 'en', 'both'

    user = db.relationship('User', backref=db.backref('feed_prefs', uselist=False))
