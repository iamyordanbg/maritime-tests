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
    user_seq = db.Column(db.Integer, nullable=True)  # #N ЗАПИСАН ВЕДНЪЖ при създаване (user.lifetime_test_count в момента на решаването) -
                                                        # ако по-стари резултати се изтрият после, номерацията НЕ се разбърква/преизчислява.

    @property
    def display_id(self):
        """Free-план ID, СЪЩАТА структура като премиум (BG префикс + код +
        дата(ддммгг) + -пореден номер), само кодът е 3 Букви+3 Цифри
        групирани вместо редувани:
            BG + КОД(ааа111) + ДАТА(ддммгг) + '-' + ПОРЕДЕН НОМЕР
        Пример: BGFTA973070726-001

        КОД - от free_code(user_id) - стабилен за целия Free "живот" на
        потребителя (аналог на "номера на grant-а" при премиум, но Free
        няма отделен grant обект за всяка избрана тема).
        ПОРЕДЕН НОМЕР - колко пъти ТОЗИ потребител е решавал ИМЕННО този
        тест (test_id), не общо за акаунта - аналог на "поредния номер в
        рамките на конкретния grant" при премиум."""
        from app.utils.codes import free_code
        code_part = free_code(self.user_id)
        date_part = self.taken_at.strftime('%d%m%y')
        # ПОСТОЯНЕН пореден номер - записан веднъж при решаването (self.user_seq),
        # не се преизчислява от оцелелите редове (би се разбъркал при триене
        # на стари резултати, напр. изтекла Free сесия). Fallback само за
        # стари редове отпреди тази промяна, на които user_seq е NULL.
        if self.user_seq:
            seq = self.user_seq
        else:
            seq = (TestResult.query
                   .filter(TestResult.user_id == self.user_id,
                           TestResult.test_id == self.test_id,
                           TestResult.taken_at <= self.taken_at)
                   .count())
        return f"BG{code_part}{date_part}-{seq:03d}"

