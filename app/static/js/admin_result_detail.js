// app/static/js/admin_result_detail.js
// Admin Result Detail — извлечена от app/templates/admin/result_detail.html (Правило 1+2).
// Очаква window.RESULT_DATA = {id}

async function deleteResult() {
    if (!confirm('Delete this result?')) return;
    const res = await fetch(`/admin/results/${window.RESULT_DATA.id}/delete`, { method: 'POST' });
    const data = await res.json();
    if (data.success) window.location.href = '/admin';
}

function toggleReviewPrefsPanel() {
    const p = document.getElementById('reviewPrefsPanel');
    p.style.display = p.style.display === 'none' ? 'block' : 'none';
}
document.addEventListener('click', function(e) {
    const panel = document.getElementById('reviewPrefsPanel');
    const btn = document.getElementById('reviewPrefsBtn');
    if (panel && panel.style.display === 'block' && !panel.contains(e.target) && e.target !== btn && !btn.contains(e.target)) {
        panel.style.display = 'none';
    }
});
function setReviewFontSize(val) {
    document.getElementById('reviewSizeVal').textContent = val;
    const px = 11 + (parseInt(val) * 0.6);
    document.querySelectorAll('.review-question-text').forEach(el => el.style.fontSize = px + 'px');
    document.querySelectorAll('.review-answer-text').forEach(el => el.style.fontSize = (px - 1) + 'px');
}
function setReviewTheme(theme) {
    const root = document.getElementById('resultReviewRoot');
    document.querySelectorAll('.review-theme-btn').forEach(b => {
        const active = b.getAttribute('data-review-theme') === theme;
        b.style.background = active ? '#4CC9F0' : 'transparent';
        b.style.color = active ? '#071a2e' : '#94a3b8';
        b.style.borderColor = active ? '#4CC9F0' : 'rgba(255,255,255,0.15)';
    });
    document.querySelectorAll('.review-question-card').forEach(card => {
        if (theme === 'light') {
            card.style.background = '#faf9f7'; card.style.borderColor = '#e5e7eb';
        } else if (theme === 'sepia') {
            card.style.background = '#f4ecd8'; card.style.borderColor = '#d8c9a3';
        } else {
            card.style.background = '#0B132B'; card.style.borderColor = '';
        }
    });
    document.querySelectorAll('.review-question-text').forEach(el => {
        el.style.color = theme === 'dark' ? '#fff' : (theme === 'sepia' ? '#3b2f1e' : '#1f2937');
    });
}
setReviewTheme('dark');

function toggleLightbox(src) {
    const modal = document.getElementById('imgModal');
    const modalImg = document.getElementById('modalImg');
    if (modal.style.display === 'inline-block') { modal.style.display = 'none'; return; }
    modalImg.src = src;
    modal.style.display = 'inline-block';
    modalImg.onload = function() {
        modalImg.style.width = Math.round(modalImg.naturalWidth * 1.2 * 1.78) + 'px';
        modalImg.style.height = 'auto';
    };
}
function closeImgModal() { document.getElementById('imgModal').style.display = 'none'; }
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
    m.style.left=(e.clientX-dragOffsetX)+'px';
    m.style.top=(e.clientY-dragOffsetY)+'px';
    m.style.right='auto';
}
function dragEnd(){isDragging=false;document.removeEventListener('mousemove',dragMove);document.removeEventListener('mouseup',dragEnd);}
