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


// Settings > Privacy > Devices: ends every session of the account (this browser too), then goes to the landing page.
async function signOutAllDevices() {
    const msg = document.getElementById('signOutAllMsg');
    if (!window.confirm('Sign out of all devices, including this one?')) return;
    try {
        const res = await fetch('/settings/sign-out-all', { method: 'POST' });
        const data = await res.json();
        if (!res.ok || !data.success) throw new Error('failed');
        window.location.replace('/?login=1');
    } catch (e) {
        if (msg) { msg.textContent = 'Could not sign out. Please try again.'; msg.style.color = '#dc2626'; }
    }
}

// Settings > Privacy > Sign-in history: loaded when the user opens it (rendering is in login-history.js).
async function toggleLoginHistory() {
    const box = document.getElementById('loginHistoryBox');
    const btn = document.getElementById('loginHistoryBtn');
    if (!box || !btn) return;
    if (!box.hidden) { box.hidden = true; btn.textContent = 'Show'; return; }
    box.hidden = false;
    btn.textContent = 'Hide';
    box.innerHTML = '<p class="lh-empty">Loading…</p>';
    try {
        const res = await fetch('/settings/login-history');
        const data = await res.json();
        if (!res.ok) throw new Error('failed');
        box.innerHTML = renderLoginHistory(data.entries, { admin: false })
            + '<p class="lh-note">Shown in your local time. Kept for ' + data.retention_days + ' days. Duration is the time until your last activity. '
            + 'If you do not recognise an IP address, use Sign out of all devices and change your password.</p>';
    } catch (e) {
        box.innerHTML = '<p class="lh-empty">Could not load the history. Please try again.</p>';
    }
}
