from flask import Blueprint, render_template, request, jsonify, session
from ..extensions import db
from ..models import Post, PostComment, User, UserFeedPrefs
from datetime import datetime
import os, uuid, json
from pathlib import Path
from werkzeug.utils import secure_filename
from .rss_feeds import FEEDS, CATEGORY_ORDER
from .rss_cache import get_cached

feed = Blueprint('feed', __name__)

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'static', 'feed_images')
ALLOWED = {'png','jpg','jpeg','gif','webp'}
BLOG_COUNTER_FILE = Path(__file__).parent.parent / 'static' / 'blog_interest.json'

def allowed(f): return '.' in f and f.rsplit('.',1)[1].lower() in ALLOWED

def time_ago(dt):
    if not dt: return ''
    now = datetime.utcnow()
    if isinstance(dt, str):
        try: from dateutil import parser; dt = parser.parse(dt).replace(tzinfo=None)
        except: return ''
    try: diff = (now - dt).total_seconds()
    except: return ''
    if diff < 60: return 'Току-що'
    if diff < 3600: return f'Преди {int(diff//60)} мин'
    if diff < 86400: return f'Преди {int(diff//3600)} ч'
    if diff < 604800: return f'Преди {int(diff//86400)} дни'
    return dt.strftime('%d.%m.%Y')

def get_user_categories(user_id):
    prefs = UserFeedPrefs.query.filter_by(user_id=user_id).first()
    if prefs and prefs.categories:
        return prefs.categories.split(',')
    return ['maritime', 'world']

@feed.route('/feed')
def index():
    q = request.args.get('q','').strip()
    user = None
    user_cats = ['maritime', 'world']
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user: user_cats = get_user_categories(user.id)

    # Твоите публикации
    posts_q = Post.query
    if q: posts_q = posts_q.filter(Post.title.ilike(f'%{q}%'))
    own_posts = posts_q.order_by(Post.last_activity.desc()).all()

    return render_template('feed/index.html',
        own_posts=own_posts, q=q, user=user,
        time_ago=time_ago, feeds=FEEDS,
        user_cats=user_cats, category_order=CATEGORY_ORDER)

@feed.route('/feed/rss')
def rss_fetch():
    cats = [c for c in request.args.get('cats','maritime,world').split(',') if c in FEEDS]
    q = request.args.get('q','').strip().lower()
    if not cats: cats = ['maritime','world']

    items = get_cached(cats)

    if q:
        items = [i for i in items if q in i['title'].lower()]

    # Обновяваме time_ago динамично
    for i in items:
        if i.get('published'):
            i['time_ago'] = time_ago(i['published'])

    return jsonify(items[:50])

@feed.route('/feed/latest')
def latest():
    posts = Post.query.order_by(Post.last_activity.desc()).limit(3).all()
    return jsonify([{'id':p.id,'title':p.title,'time_ago':time_ago(p.created_at)} for p in posts])

@feed.route('/feed/post/<int:post_id>')
def view_post(post_id):
    post = Post.query.get_or_404(post_id)
    post.views += 1
    db.session.commit()
    return jsonify({
        'id':post.id,'title':post.title,'body':post.body,
        'image_url':post.image_url,'views':post.views,
        'time_ago':time_ago(post.created_at),
        'comments':[{
            'id':c.id,'user':c.user.nick or c.user.name,
            'body':c.body,'time_ago':time_ago(c.created_at)
        } for c in post.comments]
    })

@feed.route('/feed/comment/<int:post_id>', methods=['POST'])
def add_comment(post_id):
    if 'user_id' not in session: return jsonify({'error':'login_required'}),401
    post = Post.query.get_or_404(post_id)
    body = request.json.get('body','').strip()
    if not body or len(body)>1000: return jsonify({'error':'invalid'}),400
    c = PostComment(post_id=post_id, user_id=session['user_id'], body=body)
    post.last_activity = datetime.utcnow()
    db.session.add(c); db.session.commit()
    return jsonify({'id':c.id,'user':c.user.nick or c.user.name,'body':c.body,'time_ago':time_ago(c.created_at)})

@feed.route('/feed/prefs', methods=['GET','POST'])
def feed_prefs():
    if 'user_id' not in session: return jsonify({'error':'unauthorized'}),401
    if request.method=='GET':
        prefs = UserFeedPrefs.query.filter_by(user_id=session['user_id']).first()
        return jsonify({
            'categories': prefs.categories.split(',') if prefs else ['maritime','world'],
            'language': prefs.language if prefs else 'both'
        })
    data = request.json
    prefs = UserFeedPrefs.query.filter_by(user_id=session['user_id']).first()
    if not prefs:
        prefs = UserFeedPrefs(user_id=session['user_id'])
        db.session.add(prefs)
    cats = [c for c in data.get('categories',[]) if c in FEEDS]
    prefs.categories = ','.join(cats) if cats else 'maritime,world'
    prefs.language = data.get('language','both')
    db.session.commit()
    return jsonify({'ok':True})

# ── ADMIN ──
@feed.route('/admin/feed/posts', methods=['GET'])
def admin_posts():
    if 'user_id' not in session: return jsonify({'error':'unauthorized'}),403
    u = User.query.get(session['user_id'])
    if not u or not u.is_admin: return jsonify({'error':'unauthorized'}),403
    posts = Post.query.order_by(Post.created_at.desc()).all()
    return jsonify([{'id':p.id,'title':p.title,'views':p.views,'comments':len(p.comments),'created_at':p.created_at.strftime('%d.%m.%Y')} for p in posts])

@feed.route('/admin/feed/post', methods=['POST'])
def admin_create_post():
    if 'user_id' not in session: return jsonify({'error':'unauthorized'}),403
    u = User.query.get(session['user_id'])
    if not u or not u.is_admin: return jsonify({'error':'unauthorized'}),403
    title = request.form.get('title','').strip()
    body  = request.form.get('body','').strip()
    if not title or not body: return jsonify({'error':'missing fields'}),400
    image_url = ''
    file = request.files.get('image')
    if file and allowed(file.filename):
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        ext = file.filename.rsplit('.',1)[1].lower()
        fname = f"{uuid.uuid4().hex}.{ext}"
        file.save(os.path.join(UPLOAD_FOLDER, fname))
        image_url = f'/static/feed_images/{fname}'
    post = Post(title=title, body=body, image_url=image_url)
    db.session.add(post); db.session.commit()
    return jsonify({'ok':True,'id':post.id})

@feed.route('/admin/feed/post/<int:post_id>', methods=['DELETE'])
def admin_delete_post(post_id):
    if 'user_id' not in session: return jsonify({'error':'unauthorized'}),403
    u = User.query.get(session['user_id'])
    if not u or not u.is_admin: return jsonify({'error':'unauthorized'}),403
    post = Post.query.get_or_404(post_id)
    PostComment.query.filter_by(post_id=post_id).delete()
    db.session.delete(post); db.session.commit()
    return jsonify({'ok':True})

@feed.route('/blog/interest', methods=['POST'])
def blog_interest():
    try:
        data = json.loads(BLOG_COUNTER_FILE.read_text()) if BLOG_COUNTER_FILE.exists() else {'clicks':0}
        data['clicks'] = data.get('clicks',0)+1
        BLOG_COUNTER_FILE.write_text(json.dumps(data))
    except: pass
    return jsonify({'ok':True})

@feed.route('/admin/blog/interest')
def blog_interest_count():
    if 'user_id' not in session: return jsonify({'error':'unauthorized'}),403
    u = User.query.get(session['user_id'])
    if not u or not u.is_admin: return jsonify({'error':'unauthorized'}),403
    try:
        data = json.loads(BLOG_COUNTER_FILE.read_text()) if BLOG_COUNTER_FILE.exists() else {'clicks':0}
        return jsonify(data)
    except: return jsonify({'clicks':0})
