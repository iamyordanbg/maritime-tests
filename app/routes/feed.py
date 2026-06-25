from flask import Blueprint, render_template, request, jsonify, session
from ..extensions import db
from ..models import Post, PostComment, User
from datetime import datetime
import os, uuid, json
from pathlib import Path

feed = Blueprint('feed', __name__)

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'static', 'feed_images')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED = {'png','jpg','jpeg','gif','webp'}
BLOG_COUNTER_FILE = Path(__file__).parent.parent / 'static' / 'blog_interest.json'

def allowed(f): return '.' in f and f.rsplit('.',1)[1].lower() in ALLOWED

def time_ago(dt):
    if not dt: return ''
    now = datetime.utcnow()
    if isinstance(dt, str):
        try:
            from dateutil import parser
            dt = parser.parse(dt).replace(tzinfo=None)
        except: return ''
    try: diff = (now - dt).total_seconds()
    except: return ''
    if diff < 3600: return f'{int(diff//60)}m ago'
    if diff < 86400: return f'{int(diff//3600)}h ago'
    if diff < 604800: return f'{int(diff//86400)}d ago'
    return dt.strftime('%d.%m.%Y')

@feed.route('/feed')
def index():
    q = request.args.get('q','').strip()
    user = None
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
    posts = Post.query.order_by(Post.last_activity.desc()).all()
    if q: posts = [p for p in posts if q.lower() in p.title.lower()]
    return render_template('feed/index.html', own_posts=posts, q=q, user=user, time_ago=time_ago)

@feed.route('/feed/img/<path:filename>')
def feed_image(filename):
    from flask import send_from_directory
    return send_from_directory(UPLOAD_FOLDER, filename)

@feed.route('/feed/latest')
def latest():
    limit = min(int(request.args.get('limit', 3)), 50)
    posts = Post.query.order_by(Post.last_activity.desc()).limit(limit).all()
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
        'comments':[{'id':c.id,'user':c.user.nick or c.user.name,'body':c.body,'time_ago':time_ago(c.created_at)} for c in post.comments]
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

@feed.route('/admin/feed/posts')
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
