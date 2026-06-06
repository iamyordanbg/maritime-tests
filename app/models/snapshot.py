from app.extensions import db
from datetime import datetime

class MonthlySnapshot(db.Model):
    __tablename__ = 'monthly_snapshot'
    id           = db.Column(db.Integer, primary_key=True)
    year         = db.Column(db.Integer, nullable=False)
    month        = db.Column(db.Integer, nullable=False)  # 1-12
    total_users  = db.Column(db.Integer, default=0)
    active_users = db.Column(db.Integer, default=0)
    passive_users= db.Column(db.Integer, default=0)
    demo_users   = db.Column(db.Integer, default=0)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('year', 'month', name='uq_year_month'),)

    def to_dict(self):
        return {
            'year': self.year,
            'month': self.month,
            'label': f"{self.year}-{str(self.month).zfill(2)}",
            'total_users': self.total_users,
            'active_users': self.active_users,
            'passive_users': self.passive_users,
            'demo_users': self.demo_users,
        }

