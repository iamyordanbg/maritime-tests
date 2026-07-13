// app/static/js/admin_ads.js
// Admin Ads управление — извлечена от app/templates/admin/ads.html (Правило 1).

async function createAd() {
    const fd = new FormData();
    fd.append('title', document.getElementById('adTitle').value);
    fd.append('image_url', document.getElementById('adImageUrl').value);
    fd.append('link_url', document.getElementById('adLinkUrl').value);
    fd.append('body', document.getElementById('adBody').value);
    const res = await fetch('/admin/ads/create', { method: 'POST', body: fd });
    const data = await res.json();
    if (data.success) location.reload();
    else alert(data.message || 'Error');
}
async function toggleAd(id) {
    await fetch(`/admin/ads/${id}/toggle`, { method: 'POST' });
    location.reload();
}
async function deleteAd(id) {
    if (!confirm('Delete this ad?')) return;
    await fetch(`/admin/ads/${id}/delete`, { method: 'POST' });
    document.getElementById(`ad_row_${id}`)?.remove();
}
