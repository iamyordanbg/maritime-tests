from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from ..extensions import db
from ..models import Post, PostComment, User
from datetime import datetime, timedelta
import os, uuid
from werkzeug.utils import secure_filename

feed = Blueprint('feed', __name__)

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'static', 'feed_images')
ALLOWED = {'png','jpg','jpeg','gif','webp'}

def allowed(filename):
    return '.' in filename and filename.rsplit('.',1)[1].lower() in ALLOWED

def time_ago(dt):
    now = datetime.utcnow()
    diff = now - dt
    s = diff.total_seconds()
    if s < 60: return 'Току-що'
    if s < 3600: return f'Преди {int(s//60)} мин'
    if s < 86400: return f'Преди {int(s//3600)} ч'
    if s < 604800: return f'Преди {int(s//86400)} дни'
    return dt.strftime('%d.%m.%Y')

@feed.route('/feed')
def index():
    q = request.args.get('q','').strip()
    posts = Post.query
    if q:
        posts = posts.filter(Post.title.ilike(f'%{q}%'))
    posts = posts.order_by(Post.last_activity.desc()).all()
    user = None
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
    return render_template('feed/index.html', posts=posts, q=q, user=user, time_ago=time_ago)

@feed.route('/feed/post/<int:post_id>')
def view_post(post_id):
    post = Post.query.get_or_404(post_id)
    post.views += 1
    db.session.commit()
    user = None
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
    return jsonify({
        'id': post.id,
        'title': post.title,
        'body': post.body,
        'image_url': post.image_url,
        'views': post.views,
        'time_ago': time_ago(post.created_at),
        'comments': [{
            'id': c.id,
            'user': c.user.nick or c.user.name,
            'body': c.body,
            'time_ago': time_ago(c.created_at)
        } for c in post.comments]
    })

@feed.route('/feed/comment/<int:post_id>', methods=['POST'])
def add_comment(post_id):
    if 'user_id' not in session:
        return jsonify({'error': 'login_required'}), 401
    post = Post.query.get_or_404(post_id)
    body = request.json.get('body','').strip()
    if not body or len(body) > 1000:
        return jsonify({'error': 'invalid'}), 400
    c = PostComment(post_id=post_id, user_id=session['user_id'], body=body)
    post.last_activity = datetime.utcnow()
    db.session.add(c)
    db.session.commit()
    return jsonify({
        'id': c.id,
        'user': c.user.nick or c.user.name,
        'body': c.body,
        'time_ago': time_ago(c.created_at)
    })

# ── ADMIN ──────────────────────────────────────────────────────────────
@feed.route('/admin/feed/posts', methods=['GET'])
def admin_posts():
    if 'user_id' not in session: return jsonify({'error':'unauthorized'}), 403
    u = User.query.get(session['user_id'])
    if not u or not u.is_admin: return jsonify({'error':'unauthorized'}), 403
    posts = Post.query.order_by(Post.created_at.desc()).all()
    return jsonify([{
        'id': p.id, 'title': p.title,
        'views': p.views,
        'comments': len(p.comments),
        'created_at': p.created_at.strftime('%d.%m.%Y')
    } for p in posts])

@feed.route('/admin/feed/post', methods=['POST'])
def admin_create_post():
    if 'user_id' not in session: return jsonify({'error':'unauthorized'}), 403
    u = User.query.get(session['user_id'])
    if not u or not u.is_admin: return jsonify({'error':'unauthorized'}), 403

    title = request.form.get('title','').strip()
    body  = request.form.get('body','').strip()
    if not title or not body:
        return jsonify({'error':'missing fields'}), 400

    image_url = ''
    file = request.files.get('image')
    if file and allowed(file.filename):
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        ext = file.filename.rsplit('.',1)[1].lower()
        fname = f"{uuid.uuid4().hex}.{ext}"
        file.save(os.path.join(UPLOAD_FOLDER, fname))
        image_url = f'/static/feed_images/{fname}'

    post = Post(title=title, body=body, image_url=image_url)
    db.session.add(post)
    db.session.commit()
    return jsonify({'ok': True, 'id': post.id})

@feed.route('/admin/feed/post/<int:post_id>', methods=['DELETE'])
def admin_delete_post(post_id):
    if 'user_id' not in session: return jsonify({'error':'unauthorized'}), 403
    u = User.query.get(session['user_id'])
    if not u or not u.is_admin: return jsonify({'error':'unauthorized'}), 403
    post = Post.query.get_or_404(post_id)
    PostComment.query.filter_by(post_id=post_id).delete()
    db.session.delete(post)
    db.session.commit()
    return jsonify({'ok': True})

# ── BLOG INTEREST COUNTER ──────────────────────────────────────────────
from pathlib import Path
import json

BLOG_COUNTER_FILE = Path(__file__).parent.parent / 'static' / 'blog_interest.json'

@feed.route('/blog/interest', methods=['POST'])
def blog_interest():
    try:
        data = json.loads(BLOG_COUNTER_FILE.read_text()) if BLOG_COUNTER_FILE.exists() else {'clicks': 0}
        data['clicks'] = data.get('clicks', 0) + 1
        BLOG_COUNTER_FILE.write_text(json.dumps(data))
    except Exception:
        pass
    return jsonify({'ok': True})

@feed.route('/admin/blog/interest', methods=['GET'])
def blog_interest_count():
    if 'user_id' not in session: return jsonify({'error':'unauthorized'}), 403
    u = User.query.get(session['user_id'])
    if not u or not u.is_admin: return jsonify({'error':'unauthorized'}), 403
    try:
        data = json.loads(BLOG_COUNTER_FILE.read_text()) if BLOG_COUNTER_FILE.exists() else {'clicks': 0}
        return jsonify(data)
    except Exception:
        return jsonify({'clicks': 0})
