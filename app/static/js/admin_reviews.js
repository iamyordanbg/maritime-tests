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

document.addEventListener('click', async function(e) {
    const btn = e.target.closest('[data-action]');
    if (!btn) return;
    const action = btn.dataset.action;
    const id = btn.dataset.id;
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
