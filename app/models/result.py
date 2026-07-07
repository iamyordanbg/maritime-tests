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
        """Форматиран ID на Free-план резултат: ДДММГГГГ-ЧЧММ-КОД
        КОД е 3 Букви + 3 Цифри (напр. ABC123), генериран чрез
        app.utils.codes.free_code() от TestResult.id (глобално уникален
        сам по себе си, затова тук не е нужен per-user brojach - самият
        код вече гарантира 0% колизия). Преди тази промяна последният
        сегмент беше просто self.id + 999 (виждаше се като суров пореден
        номер от базата - фиксирано в отделен commit); сега вместо число
        е нечитаем/нескроллируем код, по същия дизайн принцип като
        премиум BG кодовете, само 3 Букви + 3 Цифри групирани, не
        редувани."""
        from app.utils.codes import free_code
        date_part = self.taken_at.strftime('%d%m%Y')
        time_part = self.taken_at.strftime('%H%M')
        code_part = free_code(self.id)
        return f"{date_part}-{time_part}-{code_part}"

