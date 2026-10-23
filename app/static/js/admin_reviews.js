// app/static/js/admin_reviews.js
// Event delegation за review card action бутоните (Approve/Reject/Delete)

// Жълтият индикатор на "Reviews" в менюто следва броя pending отзиви: изчезва при 0.
function updateReviewsIndicator(pending) {
    const link = document.getElementById('adminReviewsLink');
    const pill = document.getElementById('adminReviewsPill');
    if (!link || typeof pending !== 'number') return;
    link.classList.toggle('admin-sl--attention', pending > 0);
    if (pill) pill.textContent = pending > 0 ? pending : '';
}

// Отговор на сайта (MARADTEST) под одобрен отзив: Save / Remove.
async function saveReviewReply(btn, clear) {
    const card = btn.closest('.rev-card');
    const input = card && card.querySelector('.rev-reply-input');
    const msg = card && card.querySelector('.rev-reply-msg');
    if (!input) return;
    if (clear) input.value = '';
    btn.disabled = true;
    try {
        const res = await fetch(`/admin/reviews/${btn.dataset.id}/reply`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({reply: input.value})
        });
        const data = await res.json();
        if (msg) {
            msg.textContent = data.success ? (data.reply ? 'Saved' : 'Removed') : (data.message || 'Error');
            msg.classList.toggle('rev-reply-msg--err', !data.success);
        }
    } catch (err) {
        if (msg) { msg.textContent = 'Network error'; msg.classList.add('rev-reply-msg--err'); }
    }
    btn.disabled = false;
}

document.addEventListener('click', async function(e) {
    const btn = e.target.closest('[data-action]');
    if (!btn) return;
    const action = btn.dataset.action;
    const id = btn.dataset.id;
    if (action === 'reply' || action === 'reply-clear') { saveReviewReply(btn, action === 'reply-clear'); return; }
    if (!id || !['approve', 'reject', 'delete'].includes(action)) return;

    if (action === 'delete' && !confirm('Delete this review permanently?')) return;

    btn.disabled = true;
    try {
        const res = await fetch(`/admin/reviews/${id}/${action}`, {method: 'POST'});
        const data = await res.json();
        if (data.success) {
            const card = btn.closest('.rev-card');
            if (card) card.remove();
            updateReviewsIndicator(data.pending);
        } else {
            btn.disabled = false;
        }
    } catch (err) {
        btn.disabled = false;
    }
});
