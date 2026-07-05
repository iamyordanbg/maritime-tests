from ..extensions import db
from datetime import datetime
import json

class Test(db.Model):
    """Тестове (качени от admin)"""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(20), nullable=False)   # deck / engine
    level = db.Column(db.String(50), default='Operational Level')
    questions_json = db.Column(db.Text, nullable=False)   # JSON с въпросите
    question_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_demo = db.Column(db.Boolean, default=False)
    results = db.relationship('TestResult', backref='test', lazy=True)

    def get_questions(self):
        return json.loads(self.questions_json)


class DemoVisit(db.Model):
    """Посещения на демо страницата"""
    id = db.Column(db.Integer, primary_key=True)
    ip_hash = db.Column(db.String(64), nullable=False)  # SHA256 на IP - GDPR safe
    visited_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_agent = db.Column(db.String(200), default='')  # браузър


class TestImage(db.Model):
    """Снимки към въпроси — пазят се trайно в базата (не на диска на
    контейнера, който е ephemeral и се изтрива при всеки redeploy)."""
    id = db.Column(db.Integer, primary_key=True)
    test_id = db.Column(db.Integer, db.ForeignKey('test.id'), nullable=False)
    question_id = db.Column(db.Integer, nullable=False)  # q['id']
    image_data = db.Column(db.Text, nullable=True)  # base64, NULL ако е в R2
    format = db.Column(db.String(10), default='jpg')  # jpg / png
    storage = db.Column(db.String(10), default='db')  # 'db' или 'r2'
    r2_key = db.Column(db.String(255))  # пътят в R2 bucket-а, ако storage='r2'

