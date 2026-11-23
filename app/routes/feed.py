from flask import Blueprint, render_template, request, jsonify, session, url_for, current_app
from ..extensions import db
from ..models import Post, PostComment, PostLike, PostCommentLike, PostShare, PostView, Notification, User
from ..services import feed as feed_service
from datetime import datetime
import json
from pathlib import Path

feed = Blueprint('feed', __name__)

from ..utils.image_upload import UPLOAD_FOLDER, R2_PREFIX, ImageUploadError, allowed_image as allowed, save_webp, delete_uploaded
from ..utils import r2_storage

BLOG_COUNTER_FILE = Path(__file__).parent.parent / 'static' / 'blog_interest.json'

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
    """Old files are served from the volume; everything uploaded since R2 was configured is redirected to R2
    (the file name is a random uuid, so the redirect is immutable and the browser may cache it for good)."""
    import os
    from flask import send_from_directory, redirect
    if not os.path.isfile(os.path.join(UPLOAD_FOLDER, os.path.basename(filename))) and r2_storage.is_r2_configured():
        resp = redirect(r2_storage.public_url_for(R2_PREFIX + os.path.basename(filename)), code=302)
        resp.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
        return resp
    return send_from_directory(UPLOAD_FOLDER, filename)

def _is_admin():
    """Views are an admin-only figure: only admins get them in the JSON."""
    u = User.query.get(session['user_id']) if session.get('user_id') else None
    return bool(u and u.is_admin)

def _avatar_url(user):
    """A user's current profile photo URL ('' -> the UI shows the initial); ?v= changes when they upload a new one."""
    return url_for('feed.user_avatar', user_id=user.id, v=user.avatar_version) if user and user.avatar_version else ''

def _author_json(post):
    """Who published the post: display name + the author's CURRENT photo URL ('' = none -> the UI shows the initial)."""
    return {'author': feed_service.display_name(post.author) if post.author else '', 'author_avatar': _avatar_url(post.author)}

def _comment_json(c):
    avatar = _avatar_url(c.user)
    return {'id':c.id,'parent_id':c.parent_id,'user':feed_service.display_name(c.user),'avatar':avatar,'body':c.body,'time_ago':time_ago(c.created_at)}

@feed.route('/feed/avatar/<int:user_id>')
def user_avatar(user_id):
    """A commenter's profile photo (only ever linked from comments that already show their name)."""
    from ..services.avatar import avatar_response
    return avatar_response(User.query.get(user_id))

@feed.route('/feed/latest')
def latest():
    limit = min(int(request.args.get('limit', 3)), 50)
    posts = Post.query.order_by(Post.last_activity.desc()).limit(limit).all()
    stats = feed_service.stats_for([p.id for p in posts], session.get('user_id'))
    previews = feed_service.top_comments_for([p.id for p in posts], n=request.args.get('top_comments', type=int) or 0) \
        if request.args.get('top_comments', type=int) else {}
    admin = _is_admin()
    return jsonify([dict({
        'id': p.id,
        'title': p.title,
        'time_ago': time_ago(p.created_at),
        'image_url': p.image_url or '',
        'comments': stats[p.id]['comments'],
        'likes': stats[p.id]['likes'],
        'shares': stats[p.id]['shares'],
        'liked': stats[p.id]['liked'],
        'body': p.body or ''
    }, **_author_json(p), **({'views': p.views or 0} if admin else {}),
       **({'top_comments': previews.get(p.id, [])} if request.args.get('top_comments', type=int) else {})) for p in posts])

@feed.route('/feed/post/<int:post_id>')
def view_post(post_id):
    post = Post.query.get_or_404(post_id)
    views = feed_service.register_view(post)
    st = feed_service.stats_for([post.id], session.get('user_id'))[post.id]
    return jsonify(dict({
        'id':post.id,'title':post.title,'body':post.body,
        'image_url':post.image_url,
        'time_ago':time_ago(post.created_at),
        'likes':st['likes'],'liked':st['liked'],'shares':st['shares'],
        'comments':[_comment_json(c) for c in post.comments]
    }, **_author_json(post), **({'views':views} if _is_admin() else {})))

@feed.route('/feed/post/<int:post_id>/comments')
def post_comments(post_id):
    """Comments only: does not count as a view. Without `limit` all comments (News Center);
    with `limit`/`offset` the most-liked top-level comments page by page, with their replies (desktop reader)."""
    post = Post.query.get_or_404(post_id)
    if 'limit' not in request.args:
        return jsonify({'comments':[_comment_json(c) for c in post.comments]})
    limit = max(1, min(request.args.get('limit', 3, type=int), 50))
    offset = max(0, request.args.get('offset', 0, type=int))
    page, total = feed_service.comments_page(post, session.get('user_id'), offset, limit)
    def one(c, likes, liked, reply_to=''):
        return dict(_comment_json(c), likes=likes, liked=liked, reply_to=reply_to)
    return jsonify({'comments':[dict(one(c, l, m), replies=[one(*r) for r in reps]) for c, l, m, reps in page],
                    'total':total, 'has_more':offset + len(page) < total})

@feed.route('/feed/comment-like/<int:comment_id>', methods=['POST'])
def like_comment(comment_id):
    if not session.get('user_id') or not User.query.get(session['user_id']):
        return jsonify({'error':'login_required'}),401
    comment = PostComment.query.get_or_404(comment_id)
    liked, count = feed_service.toggle_comment_like(comment, session['user_id'])
    return jsonify({'liked':liked,'likes':count})

@feed.route('/feed/like/<int:post_id>', methods=['POST'])
def like_post(post_id):
    if not session.get('user_id') or not User.query.get(session['user_id']):
        return jsonify({'error':'login_required'}),401
    post = Post.query.get_or_404(post_id)
    liked, count = feed_service.toggle_like(post, session['user_id'])
    return jsonify({'liked':liked,'likes':count})

@feed.route('/feed/share/<int:post_id>', methods=['POST'])
def share_post(post_id):
    if not session.get('user_id') or not User.query.get(session['user_id']):
        return jsonify({'error':'login_required'}),401
    post = Post.query.get_or_404(post_id)
    return jsonify({'shares':feed_service.record_share(post, session['user_id'])})

@feed.route('/feed/comment/<int:post_id>', methods=['POST'])
def add_comment(post_id):
    user = User.query.get(session['user_id']) if session.get('user_id') else None
    if not user: return jsonify({'error':'login_required'}),401
    post = Post.query.get_or_404(post_id)
    data = request.get_json(silent=True) or {}
    body = (data.get('body') or '').strip()
    if not body or len(body)>1000: return jsonify({'error':'invalid'}),400
    try:
        c = feed_service.add_comment(post, user, body, data.get('parent_id'))
    except ValueError:
        return jsonify({'error':'invalid'}),400
    return jsonify(dict(_comment_json(c), reply_to=feed_service.reply_to_name(c)))

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
        try:
            image_url = save_webp(file)
        except ImageUploadError as e:
            return jsonify({'error': str(e)}), 400
    post = Post(title=title, body=body, image_url=image_url, author_id=u.id)
    db.session.add(post); db.session.commit()
    return jsonify({'ok':True,'id':post.id})

def _admin_or_none():
    """The logged-in admin, or None."""
    if 'user_id' not in session: return None
    u = User.query.get(session['user_id'])
    return u if u and u.is_admin else None

@feed.route('/admin/feed/post/<int:post_id>', methods=['GET'])
def admin_get_post(post_id):
    """Raw fields for the edit form (does not count as a view)."""
    if not _admin_or_none(): return jsonify({'error':'unauthorized'}),403
    post = Post.query.get_or_404(post_id)
    return jsonify({'id':post.id,'title':post.title,'body':post.body,'image_url':post.image_url or ''})

@feed.route('/admin/feed/post/<int:post_id>/edit', methods=['POST'])
def admin_edit_post(post_id):
    if not _admin_or_none(): return jsonify({'error':'unauthorized'}),403
    post = Post.query.get_or_404(post_id)
    new_image_url = ''
    file = request.files.get('image')
    if file and file.filename:
        try:
            new_image_url = save_webp(file)
        except ImageUploadError as e:
            return jsonify({'error': str(e)}), 400
    try:
        orphan = feed_service.update_post(post, request.form.get('title'), request.form.get('body'),
                                          new_image_url=new_image_url, remove_image=request.form.get('remove_image') == '1')
    except feed_service.PostValidationError as e:
        delete_uploaded(new_image_url)          # the new picture was already stored - drop it, the change is refused
        return jsonify({'error': str(e)}), 400
    except Exception:
        delete_uploaded(new_image_url)
        current_app.logger.exception('Editing news post %s failed', post_id)
        return jsonify({'error': 'The post could not be saved.'}), 500
    delete_uploaded(orphan)                     # the replaced / removed picture is no longer used
    return jsonify({'ok':True,'id':post.id,'title':post.title,'body':post.body,'image_url':post.image_url or ''})

@feed.route('/admin/feed/post/<int:post_id>', methods=['DELETE'])
def admin_delete_post(post_id):
    if not _admin_or_none(): return jsonify({'error':'unauthorized'}),403
    post = Post.query.get_or_404(post_id)
    try:
        image_url = feed_service.delete_post(post)
    except Exception:
        current_app.logger.exception('Deleting news post %s failed', post_id)
        return jsonify({'error': 'The post could not be deleted.'}), 500
    delete_uploaded(image_url)   # the picture (R2 object or volume file) goes with the post
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
