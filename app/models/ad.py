"""
app/models/ad.py
=================
Реклами за Free план — управлявани от admin панела, показвани на всеки
5-ти въпрос в тестовете (реални и демо).
"""

from datetime import datetime
from ..extensions import db


class Ad(db.Model):
    __tablename__ = 'ad'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    image_url = db.Column(db.String(500), nullable=True)
    link_url = db.Column(db.String(500), nullable=True)
    body = db.Column(db.Text, nullable=True)          # кратък текст, ако няма изображение
    is_active = db.Column(db.Boolean, default=True)
    impressions = db.Column(db.Integer, default=0)     # брой пъти показана
    clicks = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
