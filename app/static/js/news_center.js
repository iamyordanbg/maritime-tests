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

// Counters row: views (unique people), comments, likes. The date is only shown on desktop (.ns-date).
function nsCountsHTML(p) {
    return `<span class="ns-count"><i class="fa-regular fa-eye"></i> ${p.views || 0}</span>
        <span class="ns-count" data-ns-comments><i class="fa-regular fa-comment"></i> ${p.comments || 0}</span>
        <span class="ns-count" data-ns-likes><i class="fa-regular fa-thumbs-up"></i> ${p.likes || 0}</span>`;
}

function nsCommentHTML(c) {
    return `<div class="nc-cm">
        <div class="nc-cm-avatar">${ncEscape((c.user || '?').charAt(0).toUpperCase())}</div>
        <div class="nc-cm-main">
            <div class="nc-cm-name">${ncEscape(c.user)} <span class="nc-cm-time">${ncEscape(c.time_ago)}</span></div>
            <div class="nc-cm-body">${ncEscape(c.body)}</div>
        </div>
    </div>`;
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

function shareNsPost(id) {
    const post = (window._newsPosts || []).find(p => p.id === id);
    const url = window.location.origin + '/feed';
    if (navigator.share) { navigator.share({title: post ? post.title : '', url}).catch(() => {}); }
    else if (navigator.clipboard) {
        navigator.clipboard.writeText(url).then(() => nsToast('✓ Link copied'));
    }
}

async function toggleNsComments(id) {
    const card = document.getElementById('ns-card-' + id);
    const open = card.classList.toggle('show-comments');
    if (!open) return;
    const list = document.getElementById('ns-comments-list-' + id);
    try {
        const data = await (await fetch('/feed/post/' + id + '/comments')).json();   // does not count as a view
        list.innerHTML = data.comments.length ? data.comments.map(nsCommentHTML).join('') : '<p class="ns-note">No comments yet</p>';
        nsUpdateCount(id, 'comments', data.comments.length);
    } catch (e) {}
}

async function submitNsComment(id) {
    const inp = document.getElementById('ns-cinput-' + id);
    const body = inp.value.trim(); if (!body) return;
    const res = await fetch('/feed/comment/' + id, {
        method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({body})
    });
    if (res.status === 401) { nsToast('Log in to comment'); return; }
    if (!res.ok) return;
    const data = await res.json();
    inp.value = '';
    const list = document.getElementById('ns-comments-list-' + id);
    const note = list.querySelector('.ns-note'); if (note) note.remove();
    list.insertAdjacentHTML('beforeend', nsCommentHTML(data));
    const post = (window._newsPosts || []).find(p => p.id === id);
    nsUpdateCount(id, 'comments', (post ? post.comments : 0) + 1);
}

async function openNewsPost(id) {
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
    document.getElementById('newsPostMeta').innerHTML = `<span class="ns-count"><i class="fa-regular fa-eye"></i> ${data.views}</span> <span class="ns-count"><i class="fa-regular fa-comment"></i> ${data.comments.length}</span> <span class="ns-count"><i class="fa-regular fa-thumbs-up"></i> ${data.likes || 0}</span><span class="ns-date"> · ${ncEscape(data.time_ago)}</span>`;
    document.getElementById('newsPostBody').textContent = data.body;
    const imgEl = document.getElementById('newsPostImage');
    imgEl.innerHTML = data.image_url ? `<img src="${data.image_url}" style="width:100%;max-height:200px;object-fit:cover;border-radius:10px 10px 0 0">` : '';

    const cl = document.getElementById('newsCommentsList');
    cl.innerHTML = data.comments.length ? data.comments.map(nsCommentHTML).join('') : '<p class="ns-note ns-note--light">No comments yet</p>';
}

function closeNewsPost() { showNewsList(); }

async function submitNewsComment() {
    if (!currentNewsPostId) return;
    const inp = document.getElementById('newsCommentInput');
    const body = inp.value.trim(); if (!body) return;
    const res = await fetch('/feed/comment/' + currentNewsPostId, {
        method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({body})
    });
    if (res.status === 401) { nsToast('Log in to comment'); return; }
    if (!res.ok) return;
    const data = await res.json();
    inp.value = '';
    const cl = document.getElementById('newsCommentsList');
    const note = cl.querySelector('.ns-note'); if (note) note.remove();
    cl.insertAdjacentHTML('beforeend', nsCommentHTML(data));
}

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

