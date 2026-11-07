"""Everything we keep about one user, as a plain dict (Settings > Privacy > Download my data)."""
from datetime import datetime
from app.models.result import TestResult
from app.models.payment import Payment
from app.models.post import PostComment


def _iso(dt):
    return dt.isoformat() + 'Z' if dt else None


def build_user_export(user):
    results = TestResult.query.filter_by(user_id=user.id).order_by(TestResult.taken_at.asc()).all()
    payments = Payment.query.filter_by(user_id=user.id).order_by(Payment.paid_at.asc()).all()
    comments = PostComment.query.filter_by(user_id=user.id).order_by(PostComment.created_at.asc()).all()
    return {
        'exported_at': _iso(datetime.utcnow()),
        'profile': {
            'email': user.email, 'name': user.name, 'first_name': user.firstname, 'family_name': user.lastname,
            'address_as': user.nick, 'created_at': _iso(user.created_at),
            'email_notifications': user.notif_subscription is not False,
        },
        'test_results': [{
            'result_number': r.user_seq, 'test_id': r.test_id, 'type': r.test_type, 'score': r.score, 'total': r.total,
            'percent': r.percent, 'passed': r.passed, 'duration_seconds': r.duration, 'taken_at': _iso(r.taken_at),
        } for r in results],
        'payments': [{
            'plan': p.plan, 'amount_eur': p.amount, 'paid_at': _iso(p.paid_at), 'revoked_at': _iso(p.revoked_at),
        } for p in payments],
        'comments': [{
            'post_id': c.post_id, 'reply_to_comment_id': c.parent_id, 'text': c.body, 'created_at': _iso(c.created_at),
        } for c in comments],
    }
