"""
app/routes/reviews.py
======================
Потребителски отзиви - submission route + should-prompt check за
попъпа в dashboard-a.
"""
from flask import Blueprint, request, session, jsonify
from app.extensions import db
from app.models.user import User
from app.models.review import Review
from app.utils.decorators import login_required
from app.services.reviews import should_prompt_review

reviews = Blueprint("reviews", __name__)


@reviews.route('/api/reviews/public')
def api_public_reviews():
    approved = Review.query.filter_by(status='approved').order_by(Review.created_at.desc()).all()
    return jsonify([{
        'name': r.display_name,
        'picture': r.display_picture_url,
        'role': r.role or '',
        'stars': r.stars,
        'text': r.text,
    } for r in approved])


@reviews.route('/api/review/should-prompt')
@login_required
def api_should_prompt_review():
    user = User.query.get(session['user_id'])
    return jsonify({'should_prompt': should_prompt_review(user)})


@reviews.route('/api/review/submit', methods=['POST'])
@login_required
def api_submit_review():
    user = User.query.get(session['user_id'])

    # Once-per-account guard, независимо какво връща should_prompt_review
    # в момента на заявката (defense in depth - клиентска логика не се
    # доверява сляпо).
    if Review.query.filter_by(user_id=user.id).first():
        return jsonify({'success': False, 'message': 'Вече си оставил отзив.'}), 400

    stars = request.form.get('stars', type=int)
    text = (request.form.get('text') or '').strip()[:1000]
    visibility = request.form.get('visibility', 'anonymous')
    role = (request.form.get('role') or '').strip()[:150]

    if not stars or stars < 1 or stars > 5:
        return jsonify({'success': False, 'message': 'Избери оценка от 1 до 5 звезди.'}), 400
    if not text:
        return jsonify({'success': False, 'message': 'Напиши отзив.'}), 400
    if visibility not in ('anonymous', 'google'):
        visibility = 'anonymous'

    display_name = 'Anonymous Sailor'
    display_picture_url = None
    if visibility == 'google':
        if not user.google_id:
            return jsonify({'success': False, 'message': 'Свържи акаунта си с Google, за да оставиш отзив с профила си.'}), 400
        display_name = user.name or user.email.split('@')[0]
        display_picture_url = user.google_picture_url

    review = Review(
        user_id=user.id,
        stars=stars,
        text=text,
        visibility=visibility,
        display_name=display_name,
        display_picture_url=display_picture_url,
        role=role or None,
        status='pending',
    )
    db.session.add(review)
    db.session.commit()
    return jsonify({'success': True})
