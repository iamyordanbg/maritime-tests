# app/routes/support.py
# Signals и Support Center routes — извлечени от app/routes/dashboard.py.
# Правило 4 (NEXT_SESSION_PROMPT.md): Routing → app/routes/ (само HTTP handling).
# Правило 5: намалява dashboard.py от 2202 реда.

from flask import Blueprint, request, session, jsonify
from app.extensions import db
from app.models.user import User
from app.models.signal import Signal
from app.models.ticket import Ticket, TicketMessage
from app.utils.decorators import login_required
from datetime import datetime

support = Blueprint('support', __name__)


# ── Signals ──

@support.route('/signal', methods=['POST'])
@login_required
def submit_signal():
    from app.services.email import send_signal_notification
    msg = request.form.get('message', '').strip()[:500]
    sig_type = request.form.get('type', 'bug')
    user = User.query.get(session['user_id'])
    if msg:
        signal = Signal(
            user_id=user.id,
            user_name=user.name,
            user_email=user.email,
            type=sig_type,
            message=msg
        )
        db.session.add(signal)
        db.session.commit()
        send_signal_notification(user.name, user.email, sig_type, msg)
    return jsonify({'success': True})


@support.route('/signals/unread')
@login_required
def unread_signals():
    user_id = session['user_id']
    count = Signal.query.filter_by(user_id=user_id, is_read=False).filter(Signal.reply != None).count()
    return jsonify({'count': count})


@support.route('/signals/read/<int:signal_id>', methods=['POST'])
@login_required
def mark_signal_read(signal_id):
    signal = Signal.query.filter_by(id=signal_id, user_id=session['user_id']).first()
    if signal:
        signal.is_read = True
        db.session.commit()
    return jsonify({'success': True})


@support.route('/signals/my')
@login_required
def my_signals():
    signals = Signal.query.filter_by(user_id=session['user_id']).order_by(Signal.created_at.desc()).all()
    return jsonify([{
        'id': s.id,
        'type': s.type,
        'message': s.message,
        'reply': s.reply,
        'replied_at': s.replied_at.strftime('%d.%m.%Y %H:%M') if s.replied_at else None,
        'is_read': s.is_read,
        'created_at': s.created_at.strftime('%d.%m.%Y %H:%M')
    } for s in signals])


# ── Support Center (Tickets) ──

@support.route('/support/tickets')
@login_required
def get_tickets():
    user_id = session['user_id']
    tickets = Ticket.query.filter_by(user_id=user_id).order_by(Ticket.updated_at.desc()).all()
    result = []
    for t in tickets:
        unread = TicketMessage.query.filter_by(
            ticket_id=t.id, sender='admin', is_read=False).count()
        last_msg = TicketMessage.query.filter_by(
            ticket_id=t.id).order_by(TicketMessage.created_at.desc()).first()
        result.append({
            'id': t.id,
            'subject': t.subject,
            'type': t.type,
            'status': t.status,
            'unread': unread,
            'last_message': last_msg.body[:80] + '...' if last_msg and len(last_msg.body) > 80 else (last_msg.body if last_msg else ''),
            'updated_at': t.updated_at.strftime('%d.%m.%Y %H:%M')
        })
    return jsonify(result)


@support.route('/support/tickets/<int:ticket_id>/messages')
@login_required
def get_ticket_messages(ticket_id):
    ticket = Ticket.query.filter_by(id=ticket_id, user_id=session['user_id']).first_or_404()
    TicketMessage.query.filter_by(
        ticket_id=ticket_id, sender='admin', is_read=False).update({'is_read': True})
    db.session.commit()
    msgs = TicketMessage.query.filter_by(ticket_id=ticket_id).order_by(TicketMessage.created_at).all()
    return jsonify({
        'ticket': {
            'id': ticket.id,
            'subject': ticket.subject,
            'type': ticket.type,
            'status': ticket.status
        },
        'messages': [{
            'id': m.id,
            'sender': m.sender,
            'body': m.body,
            'created_at': m.created_at.strftime('%d.%m.%Y %H:%M')
        } for m in msgs]
    })


@support.route('/support/tickets', methods=['POST'])
@login_required
def create_ticket():
    from app.services.email import send_new_ticket_notification
    user_id = session['user_id']
    user = User.query.get(user_id)
    subject = request.form.get('subject', '').strip()[:200]
    body = request.form.get('body', '').replace('<', '&lt;').strip()[:500]
    ticket_type = request.form.get('type', 'question')
    if not subject or not body:
        return jsonify({'success': False, 'message': 'Попълнете всички полета'})
    ticket = Ticket(user_id=user_id, subject=subject, type=ticket_type)
    db.session.add(ticket)
    db.session.flush()
    msg = TicketMessage(ticket_id=ticket.id, sender='user', body=body)
    db.session.add(msg)
    db.session.commit()
    send_new_ticket_notification(user.name, user.email, subject, body, ticket.id)
    return jsonify({'success': True, 'ticket_id': ticket.id})


@support.route('/support/tickets/<int:ticket_id>/reply', methods=['POST'])
@login_required
def reply_ticket(ticket_id):
    from app.services.email import send_user_reply_notification
    ticket = Ticket.query.filter_by(id=ticket_id, user_id=session['user_id']).first_or_404()
    user = User.query.get(session['user_id'])
    body = request.form.get('body', '').replace('<', '&lt;').strip()[:500]
    if not body:
        return jsonify({'success': False, 'message': 'Празно съобщение'})
    ticket.status = 'open'
    ticket.updated_at = datetime.utcnow()
    msg = TicketMessage(ticket_id=ticket_id, sender='user', body=body)
    db.session.add(msg)
    db.session.commit()
    send_user_reply_notification(user.name, user.email, ticket.subject, body, ticket_id)
    return jsonify({'success': True})


@support.route('/support/unread')
@login_required
def support_unread():
    user_id = session['user_id']
    count = (TicketMessage.query
             .join(Ticket, TicketMessage.ticket_id == Ticket.id)
             .filter(Ticket.user_id == user_id,
                     TicketMessage.sender == 'admin',
                     TicketMessage.is_read == False)
             .count())
    return jsonify({'count': count})
