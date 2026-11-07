"""
app/models/all_mistakes_exclusion.py
====================================
Въпрос, който клиентът е махнал от решаването в All Mistakes (остава видим в 'View answers').
Само за All Mistakes - обикновеният Mistakes не ползва това.
"""
from datetime import datetime
from ..extensions import db


class AllMistakesExclusion(db.Model):
    __tablename__ = 'all_mistakes_exclusion'
    __table_args__ = (db.UniqueConstraint('user_id', 'test_id', 'question_id', name='uq_am_exclusion'),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    test_id = db.Column(db.Integer, nullable=False, index=True)
    question_id = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
