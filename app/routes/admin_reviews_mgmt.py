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
    count_pending_reviews, set_admin_reply, set_review_date, create_admin_review, update_review,
    ReviewInputError, ReplyError, REPLY_MAX_LENGTH, TEXT_MAX_LENGTH, NAME_MAX_LENGTH, ROLE_MAX_LENGTH,
)
from app.utils.decorators import admin_required
from app.utils.image_upload import ImageUploadError, save_webp, delete_uploaded

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
    image = review.admin_reply_image
    db.session.delete(review)
    db.session.commit()
    delete_uploaded(image)
    return jsonify({'success': True, 'pending': count_pending_reviews()})


def _form_data():
    """Данни от формата - JSON (стари клиенти/тестове) или multipart (със снимка)."""
    return request.get_json(silent=True) or request.form


def _uploaded_reply_image():
    """Качената снимка към отговора -> URL (None, ако няма файл). ImageUploadError при грешка."""
    file = request.files.get('image')
    return save_webp(file) if file and file.filename else None


@admin_reviews_mgmt.route('/reviews/<int:review_id>/reply', methods=['POST'])
@admin_required
def reply_review(review_id):
    review = Review.query.get_or_404(review_id)
    data = _form_data()
    old_image = review.admin_reply_image
    new_image = None
    try:
        new_image = _uploaded_reply_image()
        if new_image is None and str(data.get('remove_image', '')).lower() in ('1', 'true'):
            new_image = ''
        set_admin_reply(review, data.get('reply'), new_image)
    except (ReviewInputError, ImageUploadError) as e:
        if new_image:
            delete_uploaded(new_image)
        return jsonify({'success': False, 'message': str(e)}), 400
    db.session.commit()
    if old_image and old_image != review.admin_reply_image:
        delete_uploaded(old_image)
    return jsonify({'success': True, 'reply': review.admin_reply or '', 'image': review.admin_reply_image or ''})


@admin_reviews_mgmt.route('/reviews/create', methods=['POST'])
@admin_required
def create_review():
    admin = User.query.get(session['user_id'])
    image = None
    try:
        image = _uploaded_reply_image()
        create_admin_review(admin, _form_data(), image)
    except (ReviewInputError, ImageUploadError) as e:
        if image:
            delete_uploaded(image)
        return jsonify({'success': False, 'message': str(e)}), 400
    return jsonify({'success': True})


@admin_reviews_mgmt.route('/reviews/<int:review_id>/edit', methods=['POST'])
@admin_required
def edit_review(review_id):
    review = Review.query.get_or_404(review_id)
    try:
        update_review(review, _form_data())
    except ReviewInputError as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    db.session.commit()
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
