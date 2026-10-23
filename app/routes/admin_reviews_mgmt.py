"""
app/routes/admin_reviews_mgmt.py
==================================
Admin: Reviews management - одобрение/отхвърляне на потребителски отзиви
преди да излязат на landing страницата.
"""
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, session
from app.extensions import db
from app.models.review import Review
from app.models.user import User
from app.services.reviews import (
    count_pending_reviews, set_admin_reply, set_review_date, create_admin_review,
    ReviewInputError, ReplyError, REPLY_MAX_LENGTH, TEXT_MAX_LENGTH, NAME_MAX_LENGTH, ROLE_MAX_LENGTH,
)
from app.utils.decorators import admin_required

admin_reviews_mgmt = Blueprint("admin_reviews_mgmt", __name__, url_prefix="/admin")


@admin_reviews_mgmt.route('/reviews')
@admin_required
def admin_reviews():
    status_filter = request.args.get('status', 'pending')
    query = Review.query
    if status_filter in ('pending', 'approved', 'rejected'):
        query = query.filter_by(status=status_filter)
    reviews = query.order_by(Review.created_at.desc()).all()
    counts = {
        'pending': Review.query.filter_by(status='pending').count(),
        'approved': Review.query.filter_by(status='approved').count(),
        'rejected': Review.query.filter_by(status='rejected').count(),
    }
    return render_template('admin/reviews.html', reply_max=REPLY_MAX_LENGTH, text_max=TEXT_MAX_LENGTH,
                           name_max=NAME_MAX_LENGTH, role_max=ROLE_MAX_LENGTH, today=datetime.utcnow().date().isoformat(), reviews=reviews, status_filter=status_filter, counts=counts)


@admin_reviews_mgmt.route('/reviews/<int:review_id>/approve', methods=['POST'])
@admin_required
def approve_review(review_id):
    review = Review.query.get_or_404(review_id)
    review.status = 'approved'
    db.session.commit()
    return jsonify({'success': True, 'pending': count_pending_reviews()})


@admin_reviews_mgmt.route('/reviews/<int:review_id>/reject', methods=['POST'])
@admin_required
def reject_review(review_id):
    review = Review.query.get_or_404(review_id)
    review.status = 'rejected'
    db.session.commit()
    return jsonify({'success': True, 'pending': count_pending_reviews()})


@admin_reviews_mgmt.route('/reviews/<int:review_id>/delete', methods=['POST'])
@admin_required
def delete_review(review_id):
    review = Review.query.get_or_404(review_id)
    db.session.delete(review)
    db.session.commit()
    return jsonify({'success': True, 'pending': count_pending_reviews()})


@admin_reviews_mgmt.route('/reviews/<int:review_id>/reply', methods=['POST'])
@admin_required
def reply_review(review_id):
    review = Review.query.get_or_404(review_id)
    payload = request.get_json(silent=True) or {}
    try:
        set_admin_reply(review, payload.get('reply'))
    except ReplyError as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    db.session.commit()
    return jsonify({'success': True, 'reply': review.admin_reply or ''})


@admin_reviews_mgmt.route('/reviews/create', methods=['POST'])
@admin_required
def create_review():
    admin = User.query.get(session['user_id'])
    try:
        create_admin_review(admin, request.get_json(silent=True) or {})
    except ReviewInputError as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    return jsonify({'success': True})


@admin_reviews_mgmt.route('/reviews/<int:review_id>/date', methods=['POST'])
@admin_required
def change_review_date(review_id):
    review = Review.query.get_or_404(review_id)
    try:
        set_review_date(review, (request.get_json(silent=True) or {}).get('date'))
    except ReviewInputError as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    db.session.commit()
    return jsonify({'success': True, 'date': review.created_at.date().isoformat()})
