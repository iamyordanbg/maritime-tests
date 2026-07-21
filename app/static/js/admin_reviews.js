// app/static/js/admin_reviews.js
// Event delegation за review card action бутоните (Approve/Reject/Delete)

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
        } else {
            btn.disabled = false;
        }
    } catch (err) {
        btn.disabled = false;
    }
});
