"""
app/routes/notifications.py
===========================
In-platform notifications (HTTP only; logic in services/feed.py).
"""
from flask import Blueprint, jsonify, session
from app.utils.decorators import login_required
from app.services import feed as feed_service
from app.routes.feed import time_ago

notifications = Blueprint('notifications', __name__)


@notifications.route('/notifications')
@login_required
def list_notifications():
    rows, unread = feed_service.notifications_for(session['user_id'])
    return jsonify({'unread': unread, 'items': [{
        'id': n.id, 'post_id': n.post_id, 'post_title': n.post.title if n.post else '',
        'comment_id': n.comment_id, 'kind': n.kind, 'actor': n.actor_name, 'body': n.body,
        'is_read': n.is_read, 'time_ago': time_ago(n.created_at),
    } for n in rows]})


@notifications.route('/notifications/unread')
@login_required
def unread_count():
    return jsonify({'count': feed_service.notifications_for(session['user_id'], limit=1)[1]})


@notifications.route('/notifications/read', methods=['POST'])
@login_required
def read_all():
    feed_service.mark_read(session['user_id'])
    return jsonify({'ok': True})


@notifications.route('/notifications/<int:notification_id>/read', methods=['POST'])
@login_required
def read_one(notification_id):
    feed_service.mark_read(session['user_id'], notification_id)
    return jsonify({'ok': True})
