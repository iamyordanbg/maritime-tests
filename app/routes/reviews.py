"""
app/routes/reviews.py
======================
Потребителски отзиви - submission route + should-prompt check за
попъпа в dashboard-a.
"""
from flask import Blueprint, request, session, jsonify, render_template, url_for
from app.extensions import db
from app.models.user import User
from app.models.review import Review
from app.utils.decorators import login_required
from app.services.reviews import (
    review_prompt_variant, postpone_review_prompt, decline_review_prompt, account_display_name,
)
from app.services.review_reminders import read_decline_token
from app.services.review_persona import public_identity, public_initials
from app.services.site import SITE_SHORT_NAME

reviews = Blueprint("reviews", __name__)


@reviews.route('/api/reviews/public')
def api_public_reviews():
    approved = Review.query.filter_by(status='approved').order_by(Review.created_at.desc()).all()
    items = []
    for r in approved:
        name, avatar = public_identity(r)
        initials = public_initials(r)
        items.append({
            'name': name,
            'picture': r.display_picture_url,
            'avatar': avatar,  # spec за avatars.js, когато няма реална снимка
            'role': r.role or '',
            'stars': r.stars,
            'text': r.text,
            'date': r.created_at.date().isoformat() if r.created_at else '',
            'reply': r.admin_reply or '',
            'reply_by': SITE_SHORT_NAME,
            'initials': initials,
        })
    return jsonify(items)


@reviews.route('/api/review/should-prompt')
@login_required
def api_should_prompt_review():
    user = User.query.get(session['user_id'])
    variant = review_prompt_variant(user)
    return jsonify({'should_prompt': variant is not None,
                    'variant': variant,  # 'initial' (3 бутона) / 'reminder' (2 бутона, след имейла)
                    'display_name': account_display_name(user)})


@reviews.route('/api/review/postpone', methods=['POST'])
@login_required
def api_postpone_review():
    """"Not now": без прозорец, напомняне по имейл след седмица."""
    postpone_review_prompt(User.query.get(session['user_id']))
    return jsonify({'success': True})


@reviews.route('/api/review/decline', methods=['POST'])
@login_required
def api_decline_review():
    """"No thanks": прозорецът и напомнянията не се показват повече."""
    decline_review_prompt(User.query.get(session['user_id']))
    return jsonify({'success': True})


@reviews.route('/review/decline/<token>', methods=['GET', 'POST'])
def review_decline_page(token):
    """Линкът "No thanks" от имейла. GET само показва потвърждение (скенерите на имейл
    клиентите отварят линковете), записът става с POST."""
    user = User.query.get(read_decline_token(token) or 0)
    if user is None:
        return render_template('review_decline.html', state='invalid'), 400
    if request.method == 'POST':
        decline_review_prompt(user)
        return render_template('review_decline.html', state='done')
    return render_template('review_decline.html', state='confirm')


@reviews.route('/api/review/submit', methods=['POST'])
@login_required
def api_submit_review():
    user = User.query.get(session['user_id'])

    # Once-per-account guard, независимо какво връща should_prompt_review
    # в момента на заявката (defense in depth - клиентска логика не се
    # доверява сляпо).
    if Review.query.filter_by(user_id=user.id).first():
        return jsonify({'success': False, 'message': 'You have already left a review.'}), 400

    stars = request.form.get('stars', type=int)
    text = (request.form.get('text') or '').strip()[:1000]
    visibility = request.form.get('visibility', 'anonymous')
    role = (request.form.get('role') or '').strip()[:150]

    if not stars or stars < 1 or stars > 5:
        return jsonify({'success': False, 'message': 'Please choose a rating from 1 to 5 stars.'}), 400
    if not text:
        return jsonify({'success': False, 'message': 'Please write a short review.'}), 400
    if visibility not in ('anonymous', 'account'):
        visibility = 'anonymous'

    display_name = 'Anonymous Sailor'
    display_picture_url = None
    if visibility == 'account':
        display_name = account_display_name(user)
        if not display_name:
            return jsonify({'success': False, 'message': 'Add your name in Settings to post under your account name.'}), 400
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
