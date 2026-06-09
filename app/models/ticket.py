from ..extensions import db
from datetime import datetime

class Ticket(db.Model):
    """Support tickets"""
    __tablename__ = 'ticket'
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subject    = db.Column(db.String(200), nullable=False)
    type       = db.Column(db.String(20), default='question')  # bug/suggestion/question
    status     = db.Column(db.String(20), default='open')      # open/in_progress/closed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    messages   = db.relationship('TicketMessage', backref='ticket', lazy=True, cascade='all, delete-orphan')

class TicketMessage(db.Model):
    """Съобщения в ticket"""
    __tablename__ = 'ticket_message'
    id         = db.Column(db.Integer, primary_key=True)
    ticket_id  = db.Column(db.Integer, db.ForeignKey('ticket.id'), nullable=False)
    sender     = db.Column(db.String(10), nullable=False)  # 'user' or 'admin'
    body       = db.Column(db.String(500), nullable=False)
    is_read    = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
