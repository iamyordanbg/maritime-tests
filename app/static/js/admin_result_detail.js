// app/static/js/admin_result_detail.js
// Admin Result Detail — извлечена от app/templates/admin/result_detail.html (Правило 1+2).
// Очаква window.RESULT_DATA = {id}

document.getElementById('rd-delete-btn').addEventListener('click', deleteResult);
document.getElementById('reviewPrefsBtn').addEventListener('click', toggleReviewPrefsPanel);
document.getElementById('reviewSizeSlider').addEventListener('input', function() { setReviewFontSize(this.value); });
document.querySelectorAll('.review-theme-btn').forEach(btn => {
    btn.addEventListener('click', () => setReviewTheme(btn.dataset.reviewTheme));
});
document.getElementById('rd-img-modal-close-btn').addEventListener('click', closeImgModal);
document.getElementById('modalImg').addEventListener('click', closeImgModal);
document.getElementById('imgModal').addEventListener('mousedown', dragStart);
document.querySelectorAll('[data-lightbox-trigger]').forEach(img => {
    img.addEventListener('load', function() {
        this.style.setProperty('--imgw', Math.round(this.naturalWidth * 1.2) + 'px');
    });
    img.addEventListener('click', function() { toggleLightbox(this.src); });
});

async function deleteResult() {
    if (!confirm('Delete this result?')) return;
    const res = await fetch(`/admin/results/${window.RESULT_DATA.id}/delete`, { method: 'POST' });
    const data = await res.json();
    if (data.success) window.location.href = '/admin';
}

function toggleReviewPrefsPanel() {
    document.getElementById('reviewPrefsPanel').classList.toggle('hidden');
}
document.addEventListener('click', function(e) {
    const panel = document.getElementById('reviewPrefsPanel');
    const btn = document.getElementById('reviewPrefsBtn');
    if (panel && !panel.classList.contains('hidden') && !panel.contains(e.target) && e.target !== btn && !btn.contains(e.target)) {
        panel.classList.add('hidden');
    }
});

function setReviewFontSize(val) {
    document.getElementById('reviewSizeVal').textContent = val;
    const px = 11 + (parseInt(val) * 0.6);
    document.getElementById('resultReviewRoot').style.setProperty('--review-q-size', px + 'px');
    document.getElementById('resultReviewRoot').style.setProperty('--review-a-size', (px - 1) + 'px');
}

function setReviewTheme(theme) {
    const root = document.getElementById('resultReviewRoot');
    root.classList.remove('theme-dark', 'theme-light', 'theme-sepia');
    root.classList.add('theme-' + theme);
    document.querySelectorAll('.review-theme-btn').forEach(b => {
        b.classList.toggle('review-theme-btn-active', b.dataset.reviewTheme === theme);
    });
}
setReviewTheme('dark');

function toggleLightbox(src) {
    const modal = document.getElementById('imgModal');
    const modalImg = document.getElementById('modalImg');
    if (modal.classList.contains('rd-img-modal-open')) { modal.classList.remove('rd-img-modal-open'); return; }
    modalImg.src = src;
    modal.classList.add('rd-img-modal-open');
    modalImg.onload = function() {
        modalImg.style.setProperty('--modal-imgw', Math.round(modalImg.naturalWidth * 1.2 * 1.78) + 'px');
    };
}
function closeImgModal() { document.getElementById('imgModal').classList.remove('rd-img-modal-open'); }
document.addEventListener('keydown', function(e) { if(e.key==='Escape') closeImgModal(); });

let isDragging=false,dragOffsetX=0,dragOffsetY=0;
function dragStart(e) {
    if(e.target.tagName==='BUTTON'||e.target.tagName==='IMG') return;
    isDragging=true;
    const r=document.getElementById('imgModal').getBoundingClientRect();
    dragOffsetX=e.clientX-r.left; dragOffsetY=e.clientY-r.top;
    document.addEventListener('mousemove',dragMove);
    document.addEventListener('mouseup',dragEnd);
}
function dragMove(e) {
    if(!isDragging) return;
    const m=document.getElementById('imgModal');
    m.style.setProperty('--modal-left', (e.clientX-dragOffsetX)+'px');
    m.style.setProperty('--modal-top', (e.clientY-dragOffsetY)+'px');
    m.classList.add('rd-img-modal-dragged');
}
function dragEnd(){isDragging=false;document.removeEventListener('mousemove',dragMove);document.removeEventListener('mouseup',dragEnd);}
