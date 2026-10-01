"""
app/routes/admin_reviews_mgmt.py
==================================
Admin: Reviews management - одобрение/отхвърляне на потребителски отзиви
преди да излязат на landing страницата.
"""
from flask import Blueprint, render_template, request, jsonify
from app.extensions import db
from app.models.review import Review
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
    return render_template('admin/reviews.html', reviews=reviews, status_filter=status_filter, counts=counts)


@admin_reviews_mgmt.route('/reviews/<int:review_id>/approve', methods=['POST'])
@admin_required
def approve_review(review_id):
    review = Review.query.get_or_404(review_id)
    review.status = 'approved'
    db.session.commit()
    return jsonify({'success': True})


@admin_reviews_mgmt.route('/reviews/<int:review_id>/reject', methods=['POST'])
@admin_required
def reject_review(review_id):
    review = Review.query.get_or_404(review_id)
    review.status = 'rejected'
    db.session.commit()
    return jsonify({'success': True})


@admin_reviews_mgmt.route('/reviews/<int:review_id>/delete', methods=['POST'])
@admin_required
def delete_review(review_id):
    review = Review.query.get_or_404(review_id)
    db.session.delete(review)
    db.session.commit()
    return jsonify({'success': True})
