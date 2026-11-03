// app/static/js/privacy.js
// Settings > Privacy tab: the e-mail notifications switch (saved on the account via /settings/notifications).
async function savePrivacyEmail(cb) {
    const msg = document.getElementById('privacyEmailMsg');
    const wanted = cb.checked;
    try {
        const res = await fetch('/settings/notifications', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ notif_subscription: wanted })
        });
        const data = await res.json();
        if (!res.ok || !data.success) throw new Error('save failed');
        if (msg) { msg.textContent = wanted ? 'Saved: e-mails are on.' : 'Saved: e-mails are off.'; msg.style.color = '#16a34a'; }
    } catch (e) {
        cb.checked = !wanted;            // show the real, unchanged state
        if (msg) { msg.textContent = 'Could not save. Please try again.'; msg.style.color = '#dc2626'; }
    }
}
