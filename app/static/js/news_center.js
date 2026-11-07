// app/static/js/news_center.js
// News Center — споделена между user_sidebar.html и layouts/admin_sidebar.html
// (Правило 3 anti-duplication - беше дублирана идентично на 2 места).

// Докато попъп е отворен, фонът зад него не се скролва: колелцето върху затъмнението се блокира,
// а вътрешният скрол не "прелива" във фона (виж и overscroll-behavior в CSS/inline стила).
function lockPopupScroll(overlay, scrollSelector) {
    if (!overlay || overlay.dataset.scrollLocked) return;
    overlay.dataset.scrollLocked = '1';
    ['wheel', 'touchmove'].forEach(function (type) {
        overlay.addEventListener(type, function (e) {
            if (!e.target.closest(scrollSelector)) e.preventDefault();
        }, { passive: false });
    });
}

async function openNewsCenter(scrollToId) {
    lockPopupScroll(document.getElementById('newsCenterModal'), '.nc-content');
    document.getElementById('newsCenterModal').style.display = 'flex';
    document.body.style.overflow = 'hidden';
    await showNewsList();
    // Opened from a dashboard tile: bring that post to the top of the feed
    if (typeof scrollToId === 'number') {
        const card = document.getElementById('ns-card-' + scrollToId);
        if (card) card.scrollIntoView({block: 'start'});
    }
}

function closeNewsCenter() {
    document.getElementById('newsCenterModal').style.display = 'none';
    document.body.style.overflow = '';
    if (typeof refreshDashNews === 'function') refreshDashNews();   // dashboard tiles show the fresh views / comments / likes
}

async function showNewsList() {
    document.getElementById('newsCenterTitle').textContent = 'News';
    document.getElementById('newsBackBtn').style.display = 'none';
    document.getElementById('newsListView').style.display = 'block';
    document.getElementById('newsDetailView').style.display = 'none';
    if(document.getElementById('newsAdminForm')) document.getElementById('newsAdminForm').style.display = 'none';
    if(document.getElementById('newsSearchInput')) document.getElementById('newsSearchInput').value = '';

    const res = await fetch('/feed/latest?limit=50');
    window._newsPosts = await res.json();
    renderNewsFeed(window._newsPosts);
}

function filterNews(q) {
    const posts = (window._newsPosts || []).filter(p => p.title.toLowerCase().includes(q.toLowerCase()));
    renderNewsFeed(posts);
}

function ncEscape(s) {
    return String(s == null ? '' : s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

function nsToast(text) {
    const t = document.createElement('div');
    t.className = 'ns-toast';
    t.textContent = text;
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 2200);
}

// Views are an admin-only figure: the API sends `views` only to admins, so nobody else gets an eye counter.
function newsViewsHTML(p, cls) {
    return p.views === undefined ? '' : `<span${cls ? ` class="${cls}"` : ''}><i class="fa-regular fa-eye"></i> ${p.views}</span>`;
}

// Counters row: (admin: views), comments, likes, shares. The date is only shown on desktop (.ns-date).
function nsCountsHTML(p) {
    return `${newsViewsHTML(p, 'ns-count')}
        <span class="ns-count" data-ns-comments><i class="fa-regular fa-comment"></i> ${p.comments || 0}</span>
        <span class="ns-count" data-ns-likes><i class="fa-regular fa-thumbs-up"></i> ${p.likes || 0}</span>
        <span class="ns-count" data-ns-shares><i class="fa-solid fa-share"></i> ${p.shares || 0}</span>`;
}

// ctx: 'c' = comments box under a feed card, 'd' = the opened post view
function nsCommentInput(ctx, postId) {
    return document.getElementById(ctx === 'd' ? 'newsCommentInput' : 'ns-cinput-' + postId);
}

function nsCommentHTML(c, ctx, postId, replyTo) {
    return `<div class="nc-cm${c.parent_id ? ' nc-cm--reply' : ''}" data-cid="${c.id}">
        <div class="nc-cm-avatar">${ncEscape((c.user || '?').charAt(0).toUpperCase())}</div>
        <div class="nc-cm-main">
            <div class="nc-cm-name">${ncEscape(c.user)} <span class="nc-cm-time">${ncEscape(c.time_ago)}</span></div>
            <div class="nc-cm-body">${replyTo ? `<span class="nc-cm-to">↪ ${ncEscape(replyTo)}</span> ` : ''}${ncEscape(c.body)}</div>
            <button type="button" class="nc-cm-reply" data-ctx="${ctx}" data-pid="${postId}" data-cid="${c.id}" data-name="${ncEscape(c.user)}"
                data-on-click='[["startNsReply","$data:ctx","$num:pid","$num:cid","$data:name"]]'>Reply</button>
        </div>
    </div>`;
}

// Top-level comments, each followed by all of its replies (oldest first)
function nsThreadHTML(comments, ctx, postId) {
    if (!comments.length) return '<p class="ns-note' + (ctx === 'd' ? ' ns-note--light' : '') + '">No comments yet</p>';
    const byId = {}; comments.forEach(c => byId[c.id] = c);
    const rootOf = c => { let r = c; while (r.parent_id && byId[r.parent_id]) r = byId[r.parent_id]; return r.id; };
    const roots = comments.filter(c => !c.parent_id || !byId[c.parent_id]);
    return roots.map(r => nsCommentHTML(r, ctx, postId, '') +
        comments.filter(c => c.id !== r.id && rootOf(c) === r.id)
                .map(c => nsCommentHTML(c, ctx, postId, byId[c.parent_id] ? byId[c.parent_id].user : '')).join('')).join('');
}

function startNsReply(ctx, postId, commentId, name) {
    const inp = nsCommentInput(ctx, postId);
    if (!inp) return;
    cancelNsReply(ctx, postId, true);
    inp.dataset.parent = commentId;
    inp.placeholder = 'Reply to ' + name + '...';
    const row = inp.parentElement;
    row.insertAdjacentHTML('beforebegin', `<div class="nc-replying" data-ctx="${ctx}" data-pid="${postId}">
        <span>Replying to <b>${ncEscape(name)}</b></span>
        <button type="button" aria-label="Cancel reply" data-ctx="${ctx}" data-pid="${postId}" data-on-click='[["cancelNsReply","$data:ctx","$num:pid"]]'>✕</button></div>`);
    inp.focus();
}

function cancelNsReply(ctx, postId, keepFocus) {
    const inp = nsCommentInput(ctx, postId);
    if (!inp) return;
    delete inp.dataset.parent;
    inp.placeholder = 'Write a comment...';
    const bar = inp.parentElement.previousElementSibling;
    if (bar && bar.classList.contains('nc-replying')) bar.remove();
}

async function nsLoadComments(ctx, postId) {
    const list = document.getElementById(ctx === 'd' ? 'newsCommentsList' : 'ns-comments-list-' + postId);
    const data = await (await fetch('/feed/post/' + postId + '/comments')).json();   // does not count as a view
    list.innerHTML = nsThreadHTML(data.comments, ctx, postId);
    if (ctx === 'c') nsUpdateCount(postId, 'comments', data.comments.length);
}

async function nsPostComment(ctx, postId) {
    const inp = nsCommentInput(ctx, postId);
    const body = inp.value.trim(); if (!body) return;
    const payload = {body};
    if (inp.dataset.parent) payload.parent_id = Number(inp.dataset.parent);
    const res = await fetch('/feed/comment/' + postId, {
        method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)
    });
    if (res.status === 401) { nsToast('Log in to comment'); return; }
    if (!res.ok) return;
    inp.value = '';
    cancelNsReply(ctx, postId);
    await nsLoadComments(ctx, postId);
}

function renderNewsFeed(posts) {
    const el = document.getElementById('newsListItems');
    if (!posts.length) {
        el.innerHTML = '<p class="ns-empty">No posts found</p>';
        return;
    }
    el.innerHTML = posts.map(p => `
        <div class="ns-card${p.liked ? ' is-liked' : ''}" id="ns-card-${p.id}" data-id="${p.id}">
            <div class="ns-card-open" data-id="${p.id}" data-on-click='[["openNewsPost","$num:id"]]'>
                <div class="ns-card-top">
                    <p class="ns-title">${ncEscape(p.title)}</p>
                    <div class="ns-text">
                        <span class="ns-short">${ncEscape(p.body)}</span>
                        <span class="ns-full">${ncEscape(p.body)}</span>
                    </div>
                </div>
                ${p.image_url ? `<img class="ns-img" src="${ncEscape(p.image_url)}" alt="" data-on-error='[["@style","$this","display","none"]]'>` : ''}
            </div>
            ${(p.body || '').length > 150 ? `<button type="button" class="ns-more" data-id="${p.id}" data-on-click='[["toggleNsBody","$num:id"]]'>See more</button>` : ''}
            <div class="ns-meta">
                <span class="ns-date">${ncEscape(p.time_ago)}</span>
                <span class="ns-counts">${nsCountsHTML(p)}</span>
            </div>
            <div class="ns-actions">
                <button type="button" class="ns-btn ns-like-btn" data-id="${p.id}" data-on-click='[["toggleNsLike","$num:id"]]'>
                    <i class="${p.liked ? 'fa-solid' : 'fa-regular'} fa-thumbs-up"></i> Like
                </button>
                <button type="button" class="ns-btn" data-id="${p.id}" data-on-click='[["toggleNsComments","$num:id"]]'>
                    <i class="fa-regular fa-comment"></i> Comment
                </button>
                <button type="button" class="ns-btn" data-id="${p.id}" data-on-click='[["shareNsPost","$num:id"]]'>
                    <i class="fa-solid fa-share"></i> Share
                </button>
            </div>
            <div class="ns-comments-box">
                <div class="ns-comments-list" id="ns-comments-list-${p.id}"><p class="ns-note">Loading...</p></div>
                <div class="ns-comment-row">
                    <input type="text" class="ns-comment-input" id="ns-cinput-${p.id}" data-id="${p.id}" maxlength="1000" placeholder="Write a comment..."
                        data-on-keydown='[["!ifKey","Enter","submitNsComment","$num:id"]]'>
                    <button type="button" class="ns-comment-send" data-id="${p.id}" aria-label="Send comment" data-on-click='[["submitNsComment","$num:id"]]'>→</button>
                </div>
            </div>
        </div>`).join('');
}

function toggleNsBody(id) {
    const card = document.getElementById('ns-card-' + id);
    const expanded = card.classList.toggle('is-expanded');
    card.querySelector('.ns-more').textContent = expanded ? 'Show less' : 'See more';
}

function nsUpdateCount(id, key, value) {
    const el = document.querySelector(`#ns-card-${id} [data-ns-${key}]`);
    if (el) el.lastChild.textContent = ' ' + value;
    const post = (window._newsPosts || []).find(p => p.id === id);
    if (post) post[key] = value;
}

async function toggleNsLike(id) {
    let res;
    try { res = await fetch('/feed/like/' + id, {method: 'POST'}); } catch (e) { return; }
    if (res.status === 401) { nsToast('Log in to like'); return; }
    if (!res.ok) return;
    const data = await res.json();
    const card = document.getElementById('ns-card-' + id);
    card.classList.toggle('is-liked', data.liked);
    const icon = card.querySelector('.ns-like-btn i');
    icon.classList.toggle('fa-solid', data.liked);
    icon.classList.toggle('fa-regular', !data.liked);
    nsUpdateCount(id, 'likes', data.likes);
    const post = (window._newsPosts || []).find(p => p.id === id);
    if (post) post.liked = data.liked;
}

// Shared by the News Center and the desktop reader: share the post link, then count the share once per user.
// Resolves to the new share total, or null when nothing was shared (cancelled / no clipboard).
async function newsSharePost(id, title) {
    const url = window.location.origin + '/dashboard?news=' + id;
    try {
        if (navigator.share) await navigator.share({title: title || '', url});
        else if (navigator.clipboard) { await navigator.clipboard.writeText(url); nsToast('✓ Link copied'); }
        else return null;
    } catch (e) { return null; }
    try {
        const res = await fetch('/feed/share/' + id, {method: 'POST'});
        return res.ok ? (await res.json()).shares : null;
    } catch (e) { return null; }
}

async function shareNsPost(id) {
    const post = (window._newsPosts || []).find(p => p.id === id);
    const shares = await newsSharePost(id, post ? post.title : '');
    if (shares !== null) nsUpdateCount(id, 'shares', shares);
}

async function toggleNsComments(id) {
    const card = document.getElementById('ns-card-' + id);
    if (card.classList.toggle('show-comments')) { try { await nsLoadComments('c', id); } catch (e) {} }
}

function submitNsComment(id) { return nsPostComment('c', id); }


async function openNewsPost(id, scrollToCommentId) {
    currentNewsPostId = id;
    document.getElementById('newsCenterTitle').textContent = 'Post';
    document.getElementById('newsBackBtn').style.display = 'block';
    document.getElementById('newsListView').style.display = 'none';
    document.getElementById('newsAdminForm').style.display = 'none';
    document.getElementById('newsDetailView').style.display = 'block';
    document.getElementById('newsPostTitle').textContent = '...';
    document.getElementById('newsPostBody').textContent = '';
    document.getElementById('newsCommentsList').innerHTML = '';

    const res = await fetch('/feed/post/' + id);
    const data = await res.json();
    document.getElementById('newsPostTitle').textContent = data.title;
    document.getElementById('newsPostMeta').innerHTML = `${newsViewsHTML(data, 'ns-count')} <span class="ns-count"><i class="fa-regular fa-comment"></i> ${data.comments.length}</span> <span class="ns-count"><i class="fa-regular fa-thumbs-up"></i> ${data.likes || 0}</span> <span class="ns-count"><i class="fa-solid fa-share"></i> ${data.shares || 0}</span><span class="ns-date"> · ${ncEscape(data.time_ago)}</span>`;
    document.getElementById('newsPostBody').textContent = data.body;
    const imgEl = document.getElementById('newsPostImage');
    imgEl.innerHTML = data.image_url ? `<img src="${data.image_url}" style="width:100%;max-height:200px;object-fit:cover;border-radius:10px 10px 0 0">` : '';

    cancelNsReply('d', id);
    document.getElementById('newsCommentsList').innerHTML = nsThreadHTML(data.comments, 'd', id);
    if (scrollToCommentId) {
        const el = document.querySelector(`#newsCommentsList [data-cid="${scrollToCommentId}"]`);
        if (el) { el.scrollIntoView({block: 'center'}); el.classList.add('nc-cm--flash'); }
    }
}

function closeNewsPost() { showNewsList(); }

function submitNewsComment() { if (currentNewsPostId) return nsPostComment('d', currentNewsPostId); }

function openNewsAdminForm() {
    document.getElementById('newsCenterTitle').textContent = 'New Post';
    document.getElementById('newsBackBtn').style.display = 'block';
    document.getElementById('newsListView').style.display = 'none';
    document.getElementById('newsDetailView').style.display = 'none';
    document.getElementById('newsAdminForm').style.display = 'block';
    loadNaPosts();
}

function closeNewsAdminForm() { showNewsList(); }

function previewNewsImage(input) {
    if (input.files && input.files[0]) {
        const reader = new FileReader();
        reader.onload = e => { document.getElementById('naPreviewImg').src = e.target.result; document.getElementById('naImagePreview').style.display = 'block'; };
        reader.readAsDataURL(input.files[0]);
    }
}
function clearNewsImage() { document.getElementById('naImage').value = ''; document.getElementById('naImagePreview').style.display = 'none'; }

async function submitNewsPost() {
    const title = document.getElementById('naTitle').value.trim();
    const body = document.getElementById('naBody').value.trim();
    const st = document.getElementById('naStatus');
    if (!title || !body) { st.textContent = 'Title and content required.'; st.style.display = 'block'; return; }
    st.style.display = 'none';
    const fd = new FormData(); fd.append('title', title); fd.append('body', body);
    const img = document.getElementById('naImage').files[0]; if (img) fd.append('image', img);
    const res = await fetch('/admin/feed/post', {method: 'POST', body: fd});
    const data = await res.json();
    if (data.ok) {
        document.getElementById('naTitle').value = '';
        document.getElementById('naBody').value = '';
        clearNewsImage();
        loadNaPosts();
        showNewsList();
    }
}

async function loadNaPosts() {
    const res = await fetch('/admin/feed/posts'); const posts = await res.json();
    const el = document.getElementById('naPostsList');
    el.innerHTML = posts.length
        ? '<p style="font-size:10px;font-weight:700;color:#6b7280;margin-bottom:6px;text-transform:uppercase">Published</p>' +
          posts.map(p => `<div style="display:flex;align-items:center;justify-content:space-between;padding:6px 0;border-bottom:1px solid #f9fafb;font-size:11px">
              <span style="flex:1;color:#374151">${p.title}</span>
              <button onclick="deleteNewsPost(${p.id})" style="background:#fef2f2;color:#dc2626;border:1px solid #fecaca;border-radius:5px;padding:2px 7px;font-size:10px;cursor:pointer">✕</button>
          </div>`).join('')
        : '<p style="font-size:11px;color:#9ca3af">No posts yet.</p>';
}

async function deleteNewsPost(id) {
    if (!confirm('Delete this post?')) return;
    await fetch('/admin/feed/post/' + id, {method: 'DELETE'});
    loadNaPosts();
}

let currentSignalType = 'question';

