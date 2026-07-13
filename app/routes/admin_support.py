# app/routes/admin_support.py
# Admin support center routes — извлечени от admin.py (Правило 5).
from flask import Blueprint, request, jsonify, render_template
from app.extensions import db
from app.models.user import User
from app.models.ticket import Ticket, TicketMessage
from app.utils.decorators import admin_required, login_required
from datetime import datetime

admin_support = Blueprint('admin_support', __name__, url_prefix='/admin')


@admin_support.route('/support/start/<int:user_id>', methods=['POST'])
@admin_required
def admin_support_start(user_id):
    """
    Admin-ът стартира НОВ разговор с потребител, който още няма никакъв
    ticket - преди тази промяна нямаше начин admin да ИНИЦИИРА съобщение,
    само да отговаря на вече съществуващи, отворени от потребителя tickets.
    """
    from app.models.ticket import TicketMessage
    user = User.query.get_or_404(user_id)
    body = (request.get_json(silent=True) or {}).get('body', '').strip()
    if not body:
        return jsonify({'success': False, 'message': 'Empty message'}), 400

    ticket = Ticket(user_id=user.id, subject='Admin message', type='question', status='in_progress')
    db.session.add(ticket)
    db.session.flush()
    msg = TicketMessage(ticket_id=ticket.id, sender='admin', body=body, is_read=False)
    db.session.add(msg)
    db.session.commit()
    return jsonify({'success': True, 'ticket_id': ticket.id})

@admin_support.route('/support')
@admin_required
def admin_support_page():
    """
    ВАЖНО: темплейтът очаква {% set t = item.ticket %}{% set u = item.user %}
    и item.unread за всеки ред - преди тази поправка тук се подаваха голи
    Ticket обекти директно (tickets_query.all()), които нямат .ticket/.user
    атрибути -> Jinja UndefinedError -> 500 грешка на ВСЯКА заявка към тази
    страница, щом има поне 1 реален ticket в базата. Точно затова 'Message
    in Support Chat' изглеждаше 'несвързано' - страницата зад него беше
    напълно счупена.
    """
    from types import SimpleNamespace
    from app.models.ticket import TicketMessage

    filter_user_id = request.args.get('user_id', type=int)
    tickets_query = Ticket.query.order_by(Ticket.created_at.desc())
    if filter_user_id:
        tickets_query = tickets_query.filter_by(user_id=filter_user_id)
    raw_tickets = tickets_query.all()

    tickets = []
    for t in raw_tickets:
        unread = TicketMessage.query.filter_by(ticket_id=t.id, sender='user', is_read=False).count()
        u = User.query.get(t.user_id)
        tickets.append(SimpleNamespace(ticket=t, user=u, unread=unread))

    admin_user = User.query.filter_by(is_admin=True).first()
    filter_user = User.query.get(filter_user_id) if filter_user_id else None
    return render_template('admin/support.html', tickets=tickets, admin_user=admin_user, filter_user=filter_user)

@admin_support.route('/support/tickets')
@admin_required
def admin_support_tickets():
    from app.models.ticket import TicketMessage
    tickets = Ticket.query.order_by(Ticket.updated_at.desc()).all()
    result = []
    for t in tickets:
        unread = TicketMessage.query.filter_by(ticket_id=t.id, sender='user', is_read=False).count()
        user = User.query.get(t.user_id)
        result.append({
            'id': t.id, 'email': user.email if user else '', 'name': user.name if user else '',
            'type': t.type, 'status': t.status, 'unread': unread,
            'created_at': t.created_at.strftime('%d.%m %H:%M')
        })
    return jsonify(result)

@admin_support.route('/support/<int:ticket_id>/messages')
@admin_required
def admin_ticket_messages(ticket_id):
    from app.models.ticket import TicketMessage
    ticket = Ticket.query.get_or_404(ticket_id)
    user = User.query.get(ticket.user_id)
    messages = TicketMessage.query.filter_by(ticket_id=ticket_id).order_by(TicketMessage.created_at).all()
    TicketMessage.query.filter_by(ticket_id=ticket_id, sender='user', is_read=False).update({'is_read': True})
    db.session.commit()
    return jsonify({
        'ticket': {'id': ticket.id, 'type': ticket.type, 'status': ticket.status},
        'user': {'email': user.email if user else '', 'name': user.name if user else ''},
        'messages': [{'id': m.id, 'body': m.body, 'sender': m.sender,
                      'created_at': m.created_at.strftime('%d.%m %H:%M')} for m in messages]
    })

@admin_support.route('/support/<int:ticket_id>/reply', methods=['POST'])
@admin_required
def admin_ticket_reply(ticket_id):
    from app.models.ticket import TicketMessage
    ticket = Ticket.query.get_or_404(ticket_id)
    body = request.form.get('body', '').strip()
    if not body:
        return jsonify({'success': False})
    msg = TicketMessage(ticket_id=ticket_id, sender='admin', body=body, is_read=False)
    ticket.status = 'in_progress'
    ticket.updated_at = datetime.utcnow()
    db.session.add(msg)
    db.session.commit()
    return jsonify({'success': True})

@admin_support.route('/support/<int:ticket_id>/close', methods=['POST'])
@admin_required
def admin_ticket_close(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    ticket.status = 'closed'
    ticket.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'success': True})

@admin_support.route('/support/unread')
@admin_required
def admin_support_unread():
    from app.models.ticket import TicketMessage
    count = TicketMessage.query.filter_by(sender='user', is_read=False).count()
    return jsonify({'count': count})

@admin_support.route('/support/stats')
@admin_required
def admin_support_stats():
    pending = Ticket.query.filter(Ticket.status != 'closed').count()
    total = Ticket.query.count()
    return jsonify({'pending': pending, 'total': total})

