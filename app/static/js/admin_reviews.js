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

// "+ Add review": ръчно добавяне на отзив (веднага одобрен); "Date": промяна на датата на отзив.
(function () {
    const form = document.getElementById('revAddForm');
    const openBtn = document.getElementById('revAddBtn');
    if (!form || !openBtn) return;
    const msg = document.getElementById('revAddMsg');

    function toggleForm(show) {
        form.hidden = !show;
        if (show) form.querySelector('[name="text"]').focus();
    }
    function syncNameField() {
        const named = form.elements.visibility.value === 'account';
        form.elements.name.disabled = !named;
        form.elements.name.required = named;
    }
    openBtn.addEventListener('click', function () { toggleForm(form.hidden); });
    document.getElementById('revAddCancel').addEventListener('click', function () { toggleForm(false); });
    form.elements.visibility.addEventListener('change', syncNameField);
    syncNameField();

    form.addEventListener('submit', async function (e) {
        e.preventDefault();
        const payload = Object.fromEntries(new FormData(form).entries());
        msg.textContent = '';
        try {
            const res = await fetch('/admin/reviews/create', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            if (data.success) { window.location.href = '/admin/reviews?status=approved'; return; }
            msg.textContent = data.message || 'Error';
        } catch (err) {
            msg.textContent = 'Network error';
        }
    });
})();

document.addEventListener('change', async function (e) {
    const input = e.target.closest('.rev-date-input');
    if (!input) return;
    const msg = input.parentElement.querySelector('.rev-date-msg');
    try {
        const res = await fetch(`/admin/reviews/${input.dataset.id}/date`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({date: input.value})
        });
        const data = await res.json();
        msg.textContent = data.success ? 'Saved' : (data.message || 'Error');
        msg.classList.toggle('rev-date-msg--ok', !!data.success);
    } catch (err) {
        msg.textContent = 'Network error';
        msg.classList.remove('rev-date-msg--ok');
    }
});

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
