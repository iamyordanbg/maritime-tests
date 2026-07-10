from ..extensions import db
from datetime import datetime

class PromoCode(db.Model):
    """Промокодове"""
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    client_name = db.Column(db.String(200), default='')
    access_type = db.Column(db.String(100), default='Регулярни тестове')
    price = db.Column(db.Float, default=0)
    is_active = db.Column(db.Boolean, default=True)
    is_used = db.Column(db.Boolean, default=False)
    used_by = db.Column(db.String(120), default='')
    used_at = db.Column(db.DateTime, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)              # валидност (Gold: 12 месеца)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    stripe_payment_intent = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # --- Gold активация ---
    plan = db.Column(db.String(20), default='gold')                  # план, който кодът активира
    department = db.Column(db.String(10), nullable=True)              # deck / engine — избира се при активация
    level = db.Column(db.String(50), nullable=True)                   # Operational / Management — избира се при активация
    selected_test_ids = db.Column(db.Text, nullable=True)             # JSON [id1, id2] — избраните 2 теста
    mistakes_grace_days = db.Column(db.Integer, default=60)           # All Mistakes grace период след изтичане
    activated_at = db.Column(db.DateTime, nullable=True)              # кога е активиран кодът от потребителя

    # --- Споделяне ---
    shared_to = db.Column(db.String(120), nullable=True)              # имейл на последния получател
    shared_at = db.Column(db.DateTime, nullable=True)                 # кога е споделен за последно
    shared_count = db.Column(db.Integer, default=0)                   # колко пъти е споделян

    # --- Разширени критерии при ръчно генериране (admin/promos) ---
    promo_name = db.Column(db.String(200), nullable=True)             # символично име на промото (не се шифрова, само за админ бележка)
    internal_note = db.Column(db.Text, nullable=True)                 # свободен коментар, вижда се само от admin
    department_restriction = db.Column(db.String(10), nullable=True)  # deck/engine - ако е None, всички типове тестове достъпни при активация
    duration_days = db.Column(db.Integer, default=30)                 # достъп в дни СЛЕД активация (замества PLANS['gold']['valid_days_per_code'])
    activation_window_days = db.Column(db.Integer, default=30)        # колко дни кодът може да стои в STAND-BY преди да изтече неизползван
    topics_allowed = db.Column(db.Integer, default=1)                 # брой различни теми/департаменти, които могат да се заредят
    tests_quota_override = db.Column(db.Integer, default=50)          # общ брой тестове за решаване в прозореца
    restricted_email = db.Column(db.String(120), nullable=True)       # ако е зададен - само този имейл може да активира кода
    usage_limit_type = db.Column(db.String(10), default='single')     # single / custom / multiple
    usage_limit_count = db.Column(db.Integer, nullable=True)          # брой позволени активации, ако usage_limit_type == 'custom'
    used_count = db.Column(db.Integer, default=0)                     # реален брой активации досега (за custom/multiple)


