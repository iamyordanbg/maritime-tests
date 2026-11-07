// app/static/js/dash_news_reader.js
// Desktop news reader popup (dashboard). A tile opens the post: text, the whole picture, views / like / comments,
// the 3 most-liked comments (+ "View more") and a comment box; below it the other posts, scrollable, each opening in place.
// Phones open the News Center instead (news_center.js).
const dnr = { postId: null, offset: 0, pageSize: 3, total: 0 };

function dnrEsc(s) { return typeof ncEscape === 'function' ? ncEscape(s) : String(s == null ? '' : s); }

function closeDashNews() {
    const overlay = document.getElementById('dashNewsOverlay');
    if (overlay) overlay.style.display = 'none';
    document.body.style.overflow = '';
    if (typeof refreshDashNews === 'function') refreshDashNews();   // tiles show the fresh views / comments / likes
}

// Phones: a tile opens the full-screen News Center (feed); there the post itself opens on a second tap.
function openDashNews(id) {
    if (window.matchMedia('(max-width: 767px)').matches) openNewsCenter(id);
    else openDashNewsPost(id);
}

function dnrOverlay() {
    let overlay = document.getElementById('dashNewsOverlay');
    if (overlay) return overlay;
    overlay = document.createElement('div');
    overlay.id = 'dashNewsOverlay';
    overlay.className = 'dash-news-overlay';
    overlay.innerHTML = `<div class="dash-news-modal">
        <div class="dash-news-modal-head">
            <button type="button" class="dash-news-modal-home" aria-label="Back to home" data-on-click='[["closeDashNews"]]'><i class="fa-solid fa-house"></i> Home</button>
            <h2 id="dashNewsTitle"></h2>
            <button type="button" class="dash-news-modal-close" aria-label="Close" data-on-click='[["closeDashNews"]]'>✕</button>
        </div>
        <div id="dashNewsBody"></div>
        <div class="dash-news-modal-foot">
            <span id="dashNewsMeta"></span>
            <a href="/feed">All news →</a>
        </div>
    </div>`;
    overlay.addEventListener('click', e => { if (e.target === overlay) closeDashNews(); });
    document.body.appendChild(overlay);
    lockPopupScroll(overlay, '#dashNewsBody');
    return overlay;
}

function dnrCommentHTML(c, isReply) {
    const replies = (c.replies || []).map(r => dnrCommentHTML(r, true)).join('');
    return `<div class="dnr-comment${isReply ? ' is-reply' : ''}" data-cid="${c.id}">
        <div class="dnr-comment-head"><b>${dnrEsc(c.user)}</b><span>${dnrEsc(c.time_ago)}</span></div>
        <p>${dnrEsc(c.body)}</p>
        <button type="button" class="dnr-clike${c.liked ? ' is-liked' : ''}" data-id="${c.id}" data-on-click='[["dashNewsCommentLike","$num:id"]]'>
            <i class="${c.liked ? 'fa-solid' : 'fa-regular'} fa-thumbs-up"></i> <span>${c.likes || 0}</span>
        </button>
        ${replies}
    </div>`;
}

function dnrMoreCardHTML(p) {
    return `<div class="dnr-card" data-id="${p.id}" data-on-click='[["openDashNewsPost","$num:id"]]'>
        <p class="dnr-card-title">${dnrEsc(p.title)}</p>
        <p class="dnr-card-text">${dnrEsc(p.body)}</p>
        ${p.image_url ? `<img class="dnr-card-img" src="${dnrEsc(p.image_url)}" alt="" loading="lazy">` : ''}
        <div class="dnr-card-meta"><span><i class="fa-regular fa-eye"></i> ${p.views || 0}</span><span><i class="fa-regular fa-thumbs-up"></i> ${p.likes || 0}</span><span><i class="fa-regular fa-comment"></i> ${p.comments || 0}</span><span class="dnr-card-date">${dnrEsc(p.time_ago)}</span></div>
    </div>`;
}

function dnrSetViewMore(hasMore) {
    const btn = document.getElementById('dnrViewMore');
    if (btn) btn.style.display = hasMore ? 'block' : 'none';
}

async function dnrLoadComments(id) {
    const res = await fetch(`/feed/post/${id}/comments?limit=${dnr.pageSize}&offset=${dnr.offset}`, { cache: 'no-store' });
    const data = await res.json();
    if (dnr.postId !== id) return;                                   // another post was opened meanwhile
    const list = document.getElementById('dnrCommentList');
    // a comment posted by the reader is already on top: do not list it a second time when its page arrives
    const fresh = data.comments.filter(c => !list.querySelector(`.dnr-comment[data-cid="${c.id}"]`));
    list.insertAdjacentHTML('beforeend', fresh.map(c => dnrCommentHTML(c, false)).join(''));
    dnr.offset += data.comments.length;
    dnr.total = data.total;
    dnrSetViewMore(data.has_more);
    const empty = document.getElementById('dnrNoComments');
    if (empty) empty.style.display = dnr.total ? 'none' : 'block';
}

function dashNewsMoreComments(id) { return dnrLoadComments(id); }

async function openDashNewsPost(id) {
    const overlay = dnrOverlay();
    overlay.style.display = 'flex';
    document.body.style.overflow = 'hidden';
    dnr.postId = id; dnr.offset = 0; dnr.total = 0;
    const body = document.getElementById('dashNewsBody');
    document.getElementById('dashNewsTitle').textContent = '...';
    body.innerHTML = '<div class="dash-news-modal-loading">Loading...</div>';
    body.scrollTop = 0;
    let data, others = [];
    try {
        const [res, resAll] = await Promise.all([fetch('/feed/post/' + id), fetch('/feed/latest?limit=50', { cache: 'no-store' })]);
        data = await res.json();
        others = (await resAll.json()).filter(p => p.id !== id);
    } catch (e) { body.innerHTML = '<div class="dash-news-modal-loading">Could not load the post.</div>'; return; }
    if (dnr.postId !== id) return;
    document.getElementById('dashNewsTitle').textContent = data.title;
    document.getElementById('dashNewsMeta').textContent = `👁 ${data.views}  ·  ${data.time_ago}`;
    const commentCount = (data.comments || []).length;
    body.innerHTML = `<article class="dnr-post">
        <p class="dash-news-modal-text">${dnrEsc(data.body)}</p>
        ${data.image_url ? `<img class="dash-news-modal-img" src="${dnrEsc(data.image_url)}" alt="">` : ''}
        <div class="dash-news-stats">
            <span><i class="fa-regular fa-eye"></i> ${data.views || 0}</span>
            <button type="button" id="dnrLikeBtn" class="dnr-like${data.liked ? ' is-liked' : ''}" data-id="${id}" data-on-click='[["dashNewsLike","$num:id"]]'>
                <i class="${data.liked ? 'fa-solid' : 'fa-regular'} fa-thumbs-up"></i> <span id="dnrLikeCount">${data.likes || 0}</span>
            </button>
            <span><i class="fa-regular fa-comment"></i> <span id="dnrCommentCount">${commentCount}</span></span>
        </div>
        <div class="dnr-comments">
            <h3>Comments</h3>
            <div class="dnr-comment-row">
                <input type="text" id="dnrCommentInput" class="dnr-comment-input" data-id="${id}" maxlength="1000" placeholder="Write a comment..."
                    data-on-keydown='[["!ifKey","Enter","dashNewsSubmitComment","$num:id"]]'>
                <button type="button" class="dnr-comment-send" data-id="${id}" aria-label="Send comment" data-on-click='[["dashNewsSubmitComment","$num:id"]]'>→</button>
            </div>
            <p id="dnrNoComments" class="dnr-empty" style="display:none">No comments yet. Be the first.</p>
            <div id="dnrCommentList"></div>
            <button type="button" id="dnrViewMore" class="dnr-view-more" style="display:none" data-id="${id}" data-on-click='[["dashNewsMoreComments","$num:id"]]'>View more comments</button>
        </div>
    </article>
    ${others.length ? `<section class="dnr-more"><h3>More news</h3>${others.map(dnrMoreCardHTML).join('')}</section>` : ''}`;
    try { await dnrLoadComments(id); } catch (e) { /* comments stay empty; the post itself is shown */ }
}

async function dashNewsLike(id) {
    let res;
    try { res = await fetch('/feed/like/' + id, { method: 'POST' }); } catch (e) { return; }
    if (!res.ok) return;
    const d = await res.json();
    const btn = document.getElementById('dnrLikeBtn');
    if (!btn || dnr.postId !== id) return;
    btn.classList.toggle('is-liked', d.liked);
    const icon = btn.querySelector('i');
    icon.classList.toggle('fa-solid', d.liked); icon.classList.toggle('fa-regular', !d.liked);
    document.getElementById('dnrLikeCount').textContent = d.likes;
}

async function dashNewsCommentLike(cid) {
    let res;
    try { res = await fetch('/feed/comment-like/' + cid, { method: 'POST' }); } catch (e) { return; }
    if (!res.ok) return;
    const d = await res.json();
    const btn = document.querySelector(`.dnr-clike[data-id="${cid}"]`);
    if (!btn) return;
    btn.classList.toggle('is-liked', d.liked);
    const icon = btn.querySelector('i');
    icon.classList.toggle('fa-solid', d.liked); icon.classList.toggle('fa-regular', !d.liked);
    btn.querySelector('span').textContent = d.likes;
}

async function dashNewsSubmitComment(id) {
    const input = document.getElementById('dnrCommentInput');
    const text = (input.value || '').trim();
    if (!text) return;
    input.disabled = true;
    try {
        const res = await fetch('/feed/comment/' + id, {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ body: text }),
        });
        if (!res.ok) return;
        const c = await res.json();
        if (dnr.postId !== id) return;
        input.value = '';
        // the new comment has no likes yet, so it would sort last: show it on top right away
        document.getElementById('dnrCommentList').insertAdjacentHTML('afterbegin', dnrCommentHTML(Object.assign({ likes: 0, liked: false, replies: [] }, c), false));
        const counter = document.getElementById('dnrCommentCount');
        counter.textContent = (parseInt(counter.textContent, 10) || 0) + 1;
        const empty = document.getElementById('dnrNoComments');
        if (empty) empty.style.display = 'none';
    } finally { input.disabled = false; input.focus(); }
}
