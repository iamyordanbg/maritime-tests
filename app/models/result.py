from ..extensions import db
from datetime import datetime

class TestResult(db.Model):
    """Резултати от тестове"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    test_id = db.Column(db.Integer, db.ForeignKey('test.id'), nullable=False, index=True)
    score = db.Column(db.Integer, default=0)
    total = db.Column(db.Integer, default=0)
    percent = db.Column(db.Float, default=0)
    passed = db.Column(db.Boolean, default=False)
    answers_json = db.Column(db.Text, default='{}')       # Запазени отговори
    test_type = db.Column(db.String(20), default='test')
    duration = db.Column(db.Integer, default=0)  # секунди
    question_ids_json = db.Column(db.Text, default='[]')  # ID-та на въпросите
    taken_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    @property
    def display_id(self):
        """Форматиран ID: ДДММГГГГ-ЧЧММ-НОМЕР (номерът започва от 1000)"""
        date_part = self.taken_at.strftime('%d%m%Y')
        time_part = self.taken_at.strftime('%H%M')
        seq_part = self.id + 999  # id=1 → 1000, id=2 → 1001, ...
        return f"{date_part}-{time_part}-{seq_part}"

