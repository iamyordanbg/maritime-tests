// admin/users — toggle block/unblock логика

// ---------- Event wiring (заменя премахнатите onclick/onmouseover) ----------
document.getElementById('us-billing-close-btn')?.addEventListener('click', closeAccountBillingModal);
document.getElementById('accountBillingOverlay')?.addEventListener('click', function(e) {
    if (e.target === this) closeAccountBillingModal();
});
document.getElementById('usersBody')?.addEventListener('click', function(e) {
    const delBtn = e.target.closest('.us-delete-btn');
    if (delBtn) { deleteUser(delBtn.dataset.userid, delBtn.dataset.email); return; }
    const toggleBtn = e.target.closest('.us-toggle-btn');
    if (toggleBtn) { toggleUser(toggleBtn.dataset.userid); return; }
    const supportBtn = e.target.closest('.us-support-btn');
    if (supportBtn) { openSupportPopupForUser(supportBtn.dataset.userid, supportBtn.dataset.email); return; }
    const eyeBtn = e.target.closest('.us-eyemenu-btn');
    if (eyeBtn) { toggleEyeMenu(e, eyeBtn.dataset.userid); return; }
    const billingLink = e.target.closest('.us-billing-link');
    if (billingLink) { openAccountBillingModal(e, billingLink.dataset.userid, billingLink.dataset.email); }
});

function toggleUser(id) {
    const btn = document.getElementById('toggle_btn_' + id);
    const isBlocking = btn && btn.title === 'Block';
    showToggleConfirm(id, isBlocking);
}

function showToggleConfirm(id, isBlocking) {
    const old = document.getElementById('toggleConfirmModal');
    if (old) old.remove();

    const modal = document.createElement('div');
    modal.id = 'toggleConfirmModal';
    modal.className = 'us-toggle-confirm-overlay';
    modal.innerHTML = `
        <div class="us-toggle-confirm-box">
            <div class="us-toggle-confirm-header">
                <h5 class="us-toggle-confirm-title">
                    ${isBlocking ? '🚫 Block User' : '✓ Unblock User'}
                </h5>
                <button class="us-toggle-confirm-close-btn">✕</button>
            </div>
            <p class="us-toggle-confirm-text">
                ${isBlocking ? 'Are you sure you want to block this user?' : 'Are you sure you want to unblock this user?'}
            </p>
            <div class="us-toggle-confirm-actions">
                <button class="us-toggle-confirm-cancel-btn">
                    Cancel
                </button>
                <button class="us-toggle-confirm-ok-btn ${isBlocking ? 'us-toggle-confirm-ok-block' : 'us-toggle-confirm-ok-unblock'}">
                    ${isBlocking ? 'Block' : 'Unblock'}
                </button>
            </div>
        </div>`;
    modal.addEventListener('click', e => { if (e.target === modal) modal.remove(); });
    modal.querySelector('.us-toggle-confirm-close-btn').addEventListener('click', () => modal.remove());
    modal.querySelector('.us-toggle-confirm-cancel-btn').addEventListener('click', () => modal.remove());
    modal.querySelector('.us-toggle-confirm-ok-btn').addEventListener('click', () => confirmToggleUser(id));
    document.body.appendChild(modal);
}

async function confirmToggleUser(id) {
    document.getElementById('toggleConfirmModal')?.remove();
    const res = await fetch(`/admin/users/${id}/toggle`, { method: 'POST' });
    const data = await res.json();
    if (data.success) location.reload();
}

function filterUsers() {
    const q = document.getElementById('searchInput').value.toLowerCase();
    document.querySelectorAll('.user-row').forEach(row => {
        const match = row.dataset.name.includes(q) || row.dataset.email.includes(q);
        row.classList.toggle('us-row-hidden', !match);
    });
}
const _si = document.getElementById('searchInput'); if(_si) _si.addEventListener('keydown', e => { if(e.key === 'Enter') filterUsers(); });

function deleteUser(userId, email) {
    if (!confirm('Delete user ' + email + '?')) return;
    fetch('/admin/users/' + userId + '/delete', {
        method: 'POST',
        credentials: 'same-origin'
    })
    .then(r => r.json())
    .then(d => {
        if (d.success) location.reload();
        else alert('Error: ' + (d.message || 'Unknown error'));
    })
    .catch(() => alert('Error deleting!'));
}

function _positionMenu(btn, menu) {
    const rect = btn.getBoundingClientRect();
    const menuHeight = 90;
    const spaceBelow = window.innerHeight - rect.bottom;
    if (spaceBelow < menuHeight) {
        menu.style.setProperty('--menu-top', 'auto');
        menu.style.setProperty('--menu-bottom', (window.innerHeight - rect.top + 6) + 'px');
        menu.classList.add('us-eyemenu-up');
    } else {
        menu.style.setProperty('--menu-bottom', 'auto');
        menu.style.setProperty('--menu-top', (rect.bottom + 6) + 'px');
        menu.classList.remove('us-eyemenu-up');
    }
    const menuWidth = menu.offsetWidth || 200;
    let left = rect.right - menuWidth;
    if (left < 6) left = 6;
    menu.style.setProperty('--menu-left', left + 'px');
}
function toggleEyeMenu(event, userId) {
    event.stopPropagation();
    document.querySelectorAll('[id^="eyeMenu_"]').forEach(el => {
        if (el.id !== `eyeMenu_${userId}`) el.classList.add('hidden');
    });
    const menu = document.getElementById(`eyeMenu_${userId}`);
    if (!menu) return;
    if (menu.classList.contains('hidden')) {
        menu.classList.remove('hidden');
        _positionMenu(event.currentTarget, menu);
    } else {
        menu.classList.add('hidden');
    }
}
document.addEventListener('click', () => {
    document.querySelectorAll('[id^="eyeMenu_"]').forEach(el => el.classList.add('hidden'));
});

function copyMailToClipboard(event, email) {
    event.stopPropagation();
    navigator.clipboard.writeText(email).then(() => {
        const el = event.currentTarget;
        const original = el.innerHTML;
        el.innerHTML = '<i class="fa-solid fa-check us-copy-check-icon"></i><span class="us-copy-check-text">Copied!</span>';
        setTimeout(() => { el.innerHTML = original; }, 1200);
    }).catch(() => {});
}

// Account Billing popup - показва ПЪЛНАТА billing история на потребителя
// (всички Basic/Plus/Gold покупки, активни И вече изтекли), взета от
// /admin/users/<id>/billing - същите данни каквито потребителят вижда в
// собствения си Billing/Usage таб, но без филтъра "само активните".
function openAccountBillingModal(event, userId, email) {
    event.preventDefault();
    document.querySelectorAll('[id^="eyeMenu_"]').forEach(el => el.classList.add('hidden'));

    const overlay = document.getElementById('accountBillingOverlay');
    const body = document.getElementById('accountBillingBody');
    document.getElementById('accountBillingEmail').textContent = email;
    body.innerHTML = '<p class="us-billing-loading">Loading…</p>';
    overlay.classList.add('us-billing-overlay-open');

    fetch(`/admin/users/${userId}/billing`)
        .then(r => r.json())
        .then(data => {
            if (!data.cards || data.cards.length === 0) {
                body.innerHTML = '<p class="us-billing-loading">No paid subscriptions purchased yet.</p>';
                return;
            }
            let html = `<p class="us-billing-total">Total purchases: <span class="us-billing-total-num">${data.total_purchases}</span></p>`;
            data.cards.forEach(c => {
                const statusClass = c.status === 'Active' ? 'us-billing-status-active' : 'us-billing-status-inactive';
                html += `
                <div class="us-billing-card">
                    <div class="us-billing-card-row">
                        <span class="us-billing-card-plan">${c.plan} Plan <span class="us-billing-card-code">${c.code}</span></span>
                        <span class="us-billing-card-status ${statusClass}">${c.status}</span>
                    </div>
                    <p class="us-billing-card-dates">From ${c.activated_at} to ${c.expires_at}</p>
                </div>`;
            });
            body.innerHTML = html;
        })
        .catch(() => {
            body.innerHTML = '<p class="us-billing-error">Failed to load billing history.</p>';
        });
}
function closeAccountBillingModal() {
    document.getElementById('accountBillingOverlay').classList.remove('us-billing-overlay-open');
}
