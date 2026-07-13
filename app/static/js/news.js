// app/static/js/news.js
// News center функционалност — извлечена от sidebar.js (Правило 1+3).
async function openNewsCenter() {
    document.getElementById('newsCenterModal').style.display = 'flex';
    document.body.style.overflow = 'hidden';
    showNewsList();
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

function renderNewsFeed(posts) {
    const el = document.getElementById('newsListItems');
    if (!posts.length) {
        el.innerHTML = '<p style="text-align:center;color:#94a3b8;font-size:12px;padding:30px 16px">No posts found</p>';
        return;
    }
    el.innerHTML = posts.map(p => `
        <div style="background:#09172C;border-radius:10px;margin:0 0 12px 0;overflow:hidden;position:relative">

            <div style="padding:12px 14px 8px">
                <p style="font-size:14px;font-weight:700;color:#e2e8f0;margin:0 0 6px;line-height:1.4">${p.title}</p>
                <div style="font-size:13px;color:#94a3b8;line-height:1.6">
                    <span id="ns-short-${p.id}" style="display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden">${p.body||''}</span>
                    <span id="ns-full-${p.id}" style="display:none;white-space:pre-wrap">${p.body||''}</span>
                    ${(p.body||'').length > 150 ? `<button onclick="toggleNsBody(${p.id})" id="ns-btn-${p.id}" style="background:none;border:none;color:#94a3b8;font-size:12px;cursor:pointer;padding:1px 0">See more</button>` : ''}
                </div>
            </div>
            ${p.image_url ? `<img src="${p.image_url}" style="width:100%;max-height:280px;object-fit:cover;display:block" onerror="this.style.display='none'">` : ''}

            <div style="display:flex;align-items:center;justify-content:space-between;padding:4px 14px;font-size:11px;color:#94a3b8;border-bottom:1px solid #1c2e50">
                <span>${p.time_ago}</span>
                <span>${p.comments||0} comments</span>
            </div>
            <div style="display:flex">
                <button onclick="toggleNsLike(${p.id},this)" style="flex:1;background:none;border:none;cursor:pointer;color:#94a3b8;font-size:12px;font-weight:600;padding:8px 4px;display:flex;align-items:center;justify-content:center;gap:5px" onmouseover="this.style.background='#1c2e50'" onmouseout="this.style.background='none'">
                    <i class="fa-regular fa-thumbs-up" style="font-size:14px"></i> Like
                </button>
                <button onclick="toggleNsComments(${p.id})" style="flex:1;background:none;border:none;cursor:pointer;color:#94a3b8;font-size:12px;font-weight:600;padding:8px 4px;display:flex;align-items:center;justify-content:center;gap:5px" onmouseover="this.style.background='#1c2e50'" onmouseout="this.style.background='none'">
                    <i class="fa-regular fa-comment" style="font-size:14px"></i> Comment
                </button>
                <button onclick="shareNsPost('${p.title}')" style="flex:1;background:none;border:none;cursor:pointer;color:#94a3b8;font-size:12px;font-weight:600;padding:8px 4px;display:flex;align-items:center;justify-content:center;gap:5px" onmouseover="this.style.background='#1c2e50'" onmouseout="this.style.background='none'">
                    <i class="fa-solid fa-share" style="font-size:14px"></i> Share
                </button>
            </div>
            <div id="ns-comments-${p.id}" style="display:none;padding:8px 14px 10px;border-top:1px solid #1c2e50">
                <div id="ns-comments-list-${p.id}" style="margin-bottom:8px">
                    <p style="font-size:11px;color:#94a3b8;text-align:center;padding:4px 0">Loading...</p>
                </div>
                <div style="display:flex;gap:6px">
                    <input type="text" id="ns-cinput-${p.id}" placeholder="Write a comment..."
                        style="flex:1;border:none;border-radius:20px;padding:7px 12px;font-size:12px;outline:none;background:#1c2e50;color:#e2e8f0"
                        onkeydown="if(event.key==='Enter')submitNsComment(${p.id})">
                    <button onclick="submitNsComment(${p.id})" style="background:#e8a020;color:#fff;border:none;border-radius:20px;padding:6px 12px;font-size:12px;cursor:pointer">→</button>
                </div>
            </div>
        </div>`).join('');
}

function toggleNsLike(id, btn) {
    const liked = btn.dataset.liked === '1';
    btn.dataset.liked = liked ? '0' : '1';
    btn.style.color = liked ? '#94a3b8' : '#e8a020';
    btn.innerHTML = liked
        ? '<i class="fa-regular fa-thumbs-up" style="font-size:14px"></i> Like'
        : '<i class="fa-solid fa-thumbs-up" style="font-size:14px"></i> Like';
}

function shareNsPost(title) {
    const url = window.location.origin + '/feed';
    if (navigator.share) { navigator.share({title, url}).catch(()=>{}); }
    else {
        navigator.clipboard.writeText(url).then(()=>{
            const t = document.createElement('div');
            t.style.cssText = 'position:fixed;bottom:20px;left:50%;transform:translateX(-50%);background:#09172C;color:#e2e8f0;padding:7px 16px;border-radius:20px;font-size:12px;z-index:99999;border:1px solid #1c2e50';
            t.textContent = '✓ Link copied';
            document.body.appendChild(t);
            setTimeout(()=>t.remove(), 2000);
        });
    }
}


function toggleNsBody(id) {
    const s=document.getElementById('ns-short-'+id);
    const f=document.getElementById('ns-full-'+id);
    const b=document.getElementById('ns-btn-'+id);
    if(s.style.display!=='none'){s.style.display='none';f.style.display='block';b.textContent='Show less';}
    else{s.style.display='-webkit-box';f.style.display='none';b.textContent='Show more';}
}

async function toggleNsComments(id) {
    const el = document.getElementById('ns-comments-'+id);
    if(el.style.display==='none') {
        el.style.display='block';
        // Load comments
        try {
            const res = await fetch('/feed/post/'+id);
            const data = await res.json();
            const list = document.getElementById('ns-comments-list-'+id);
            if(!data.comments.length) {
                list.innerHTML = '<p style="font-size:11px;color:#9ca3af;text-align:center;padding:4px 0">No comments yet</p>';
            } else {
                list.innerHTML = data.comments.map(c=>`
                    <div style="display:flex;gap:8px;margin-bottom:8px">
                        <div style="width:22px;height:22px;border-radius:50%;background:#e5e7eb;display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:700;color:#6b7280;flex-shrink:0">${c.user[0].toUpperCase()}</div>
                        <div>
                            <div style="font-size:11px;font-weight:600;color:#111827">${c.user} <span style="font-size:9px;color:#9ca3af;font-weight:400">${c.time_ago}</span></div>
                            <div style="font-size:11px;color:#374151">${c.body}</div>
                        </div>
                    </div>`).join('');
            }
        } catch(e) {}
    } else {
        el.style.display='none';
    }
}

async function submitNsComment(id) {
    const inp = document.getElementById('ns-cinput-'+id);
    const body = inp.value.trim(); if(!body) return;
    const res = await fetch('/feed/comment/'+id, {
        method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({body})
    });
    const data = await res.json(); if(data.error) return;
    inp.value='';
    const list = document.getElementById('ns-comments-list-'+id);
    const p = list.querySelector('p'); if(p) p.remove();
    const div = document.createElement('div');
    div.style.cssText='display:flex;gap:8px;margin-bottom:8px';
    div.innerHTML=`<div style="width:22px;height:22px;border-radius:50%;background:#e5e7eb;display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:700;color:#6b7280;flex-shrink:0">${data.user[0].toUpperCase()}</div>
        <div><div style="font-size:11px;font-weight:600;color:#111827">${data.user} <span style="font-size:9px;color:#9ca3af">${data.time_ago}</span></div>
        <div style="font-size:11px;color:#374151">${data.body}</div></div>`;
    list.appendChild(div);
    // Update comment count in button
    const btn = document.querySelector(`[onclick="toggleNsComments(${id})"]`);
    if(btn) btn.innerHTML = `<i class="fa-regular fa-comment"></i> ${parseInt(btn.textContent)+1} Comments`;
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
    document.getElementById('newsPostMeta').textContent = `👁 ${data.views}  ·  ${data.time_ago}`;
    document.getElementById('newsPostBody').textContent = data.body;
    const imgEl = document.getElementById('newsPostImage');
    imgEl.innerHTML = data.image_url ? `<img src="${data.image_url}" style="width:100%;max-height:200px;object-fit:cover;border-radius:10px 10px 0 0">` : '';

    const cl = document.getElementById('newsCommentsList');
    if (!data.comments.length) {
        cl.innerHTML = '<p style="font-size:11px;color:#9ca3af;text-align:center;padding:4px 0">No comments yet</p>';
    } else {
        cl.innerHTML = data.comments.map(c => `
            <div style="display:flex;gap:8px;margin-bottom:8px">
                <div style="width:22px;height:22px;border-radius:50%;background:#e5e7eb;display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:700;color:#6b7280;flex-shrink:0">${c.user[0].toUpperCase()}</div>
                <div><div style="font-size:11px;font-weight:600;color:#111827">${c.user} <span style="font-size:9px;color:#9ca3af;font-weight:400">${c.time_ago}</span></div>
                <div style="font-size:11px;color:#374151;line-height:1.5">${c.body}</div></div>
            </div>`).join('');
    }
}

function closeNewsPost() { showNewsList(); }

async function submitNewsComment() {
    if (!currentNewsPostId) return;
    const inp = document.getElementById('newsCommentInput');
    const body = inp.value.trim(); if (!body) return;
    const res = await fetch('/feed/comment/' + currentNewsPostId, {
        method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({body})
    });
    const data = await res.json(); if (data.error) return;
    inp.value = '';
    const cl = document.getElementById('newsCommentsList');
    const p = cl.querySelector('p'); if (p) p.remove();
    const div = document.createElement('div');
    div.style.cssText = 'display:flex;gap:8px;margin-bottom:8px';
    div.innerHTML = `<div style="width:22px;height:22px;border-radius:50%;background:#e5e7eb;display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:700;color:#6b7280;flex-shrink:0">${data.user[0].toUpperCase()}</div>
        <div><div style="font-size:11px;font-weight:600;color:#111827">${data.user} <span style="font-size:9px;color:#9ca3af;font-weight:400">${data.time_ago}</span></div>
        <div style="font-size:11px;color:#374151">${data.body}</div></div>`;
    cl.appendChild(div);
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
