// app/static/js/news_admin.js
// Admin News Center: edit and delete a news post. Reuses the "New Post" form of layouts/admin_sidebar.html in an edit
// mode (class .is-editing; data-post-id / data-had-image on #newsAdminForm are the state - nothing is kept in globals).
// Loaded after news_center.js, which owns the shared list / form helpers (showNewsList, clearNewsImage, nsToast ...).

function newsFormStatus(text) {
    const st = document.getElementById('naStatus');
    st.textContent = text; st.style.display = text ? 'block' : 'none';
}

// Open the edit form for a post (from the Edit button of a card or of the "Published" list).
async function openNewsEdit(id) {
    const form = document.getElementById('newsAdminForm');
    let data;
    try {
        const res = await fetch('/admin/feed/post/' + id);
        if (!res.ok) throw new Error('load');
        data = await res.json();
    } catch (e) { nsToast('The post could not be loaded'); return; }
    document.getElementById('newsCenterTitle').textContent = 'Edit Post';
    document.getElementById('newsBackBtn').style.display = 'block';
    document.getElementById('newsListView').style.display = 'none';
    document.getElementById('newsDetailView').style.display = 'none';
    form.style.display = 'block';
    form.classList.add('is-editing');
    form.dataset.postId = String(data.id);
    form.dataset.hadImage = data.image_url ? '1' : '';
    document.getElementById('nc-form-heading').textContent = 'Edit Post';
    document.getElementById('naTitle').value = data.title;
    document.getElementById('naBody').value = data.body;
    document.getElementById('naImage').value = '';
    const preview = document.getElementById('naImagePreview');
    if (data.image_url) { document.getElementById('naPreviewImg').src = data.image_url; preview.style.display = 'block'; }
    else preview.style.display = 'none';
    newsFormStatus('');
}

// Save: title + content, and the picture - a newly chosen file replaces it; removing the preview (x) drops it.
async function saveNewsEdit() {
    const form = document.getElementById('newsAdminForm');
    const id = form.dataset.postId;
    if (!id) return;
    const title = document.getElementById('naTitle').value.trim();
    const body = document.getElementById('naBody').value.trim();
    if (!title || !body) { newsFormStatus('Title and content required.'); return; }
    const file = document.getElementById('naImage').files[0];
    const previewHidden = document.getElementById('naImagePreview').style.display === 'none';
    const fd = new FormData(); fd.append('title', title); fd.append('body', body);
    if (file) fd.append('image', file);
    else if (form.dataset.hadImage && previewHidden) fd.append('remove_image', '1');
    const btn = document.getElementById('nc-save-btn'); btn.disabled = true;
    try {
        const res = await fetch('/admin/feed/post/' + id + '/edit', {method: 'POST', body: fd});
        const data = await res.json().catch(() => ({}));
        if (!res.ok) { newsFormStatus(data.error || 'The post could not be saved.'); return; }
        nsToast('Post saved');
        await showNewsList();
    } catch (e) { newsFormStatus('The post could not be saved.'); }
    finally { btn.disabled = false; }
}

// Delete the whole post (with its comments, likes and picture).
async function deleteEditedPost() {
    const id = document.getElementById('newsAdminForm').dataset.postId;
    if (!id || !confirm('Delete this post with all its comments? This cannot be undone.')) return;
    const btn = document.getElementById('nc-delete-btn'); btn.disabled = true;
    try {
        const res = await fetch('/admin/feed/post/' + id, {method: 'DELETE'});
        const data = await res.json().catch(() => ({}));
        if (!res.ok) { newsFormStatus(data.error || 'The post could not be deleted.'); return; }
        nsToast('Post deleted');
        await showNewsList();
    } catch (e) { newsFormStatus('The post could not be deleted.'); }
    finally { btn.disabled = false; }
}
