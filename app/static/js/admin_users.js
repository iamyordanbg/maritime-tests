// admin/users — toggle block/unblock логика

function toggleUser(id) {
    const btn = document.getElementById('toggle_btn_' + id);
    const isBlocking = btn && btn.title === 'Блокирай';
    showToggleConfirm(id, isBlocking);
}

function showToggleConfirm(id, isBlocking) {
    const old = document.getElementById('toggleConfirmModal');
    if (old) old.remove();

    const modal = document.createElement('div');
    modal.id = 'toggleConfirmModal';
    modal.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.6);backdrop-filter:blur(3px);z-index:9999;display:flex;align-items:center;justify-content:center';
    modal.innerHTML = `
        <div style="background:#fff;border-radius:16px;width:380px;max-width:90vw;padding:28px 28px 22px;box-shadow:0 25px 80px rgba(0,0,0,0.4)">
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:18px;padding-bottom:14px;border-bottom:1px solid #f3f4f6">
                <h5 style="font-size:14px;font-weight:700;color:#111827;margin:0;text-transform:uppercase;letter-spacing:0.05em">
                    ${isBlocking ? '🚫 Block User' : '✓ Unblock User'}
                </h5>
                <button onclick="document.getElementById('toggleConfirmModal').remove()"
                    style="background:#f3f4f6;border:1px solid #e5e7eb;width:28px;height:28px;border-radius:50%;cursor:pointer;font-size:16px;color:#374151;display:flex;align-items:center;justify-content:center;line-height:1">✕</button>
            </div>
            <p style="font-size:13px;color:#6b7280;line-height:1.6;margin:0 0 22px">
                ${isBlocking ? 'Are you sure you want to block this user?' : 'Are you sure you want to unblock this user?'}
            </p>
            <div style="display:flex;gap:10px;justify-content:flex-end">
                <button onclick="document.getElementById('toggleConfirmModal').remove()"
                    style="padding:8px 20px;border-radius:8px;border:1px solid #e5e7eb;background:#f9fafb;color:#374151;font-size:13px;font-weight:600;cursor:pointer">
                    Cancel
                </button>
                <button onclick="confirmToggleUser(${id})"
                    style="padding:8px 20px;border-radius:8px;border:none;background:${isBlocking ? '#ef4444' : '#10b981'};color:#fff;font-size:13px;font-weight:700;cursor:pointer">
                    ${isBlocking ? 'Block' : 'Unblock'}
                </button>
            </div>
        </div>`;
    modal.addEventListener('click', e => { if (e.target === modal) modal.remove(); });
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
        row.style.display = match ? '' : 'none';
    });
}
const _si = document.getElementById('searchInput'); if(_si) _si.addEventListener('keydown', e => { if(e.key === 'Enter') filterUsers(); });

function deleteUser(userId, email) {
    if (!confirm('Delete потребител ' + email + '?')) return;
    fetch('/admin/users/' + userId + '/delete', {
        method: 'POST',
        credentials: 'same-origin'
    })
    .then(r => r.json())
    .then(d => { 
        if (d.success) location.reload(); 
        else alert('Грешка: ' + (d.message || 'Неизвестна грешка')); 
    })
    .catch(() => alert('Грешка при изтриване!'));
}

function _positionMenu(btn, menu) {
    const rect = btn.getBoundingClientRect();
    const menuHeight = 90; // приблизителна височина, за преценка дали да отвори нагоре
    const spaceBelow = window.innerHeight - rect.bottom;
    if (spaceBelow < menuHeight) {
        menu.style.top = 'auto';
        menu.style.bottom = (window.innerHeight - rect.top + 6) + 'px';
    } else {
        menu.style.bottom = 'auto';
        menu.style.top = (rect.bottom + 6) + 'px';
    }
    const menuWidth = menu.offsetWidth || 200;
    let left = rect.right - menuWidth;
    if (left < 6) left = 6;
    menu.style.left = left + 'px';
}
function toggleEyeMenu(event, userId) {
    event.stopPropagation();
    document.querySelectorAll('[id^="eyeMenu_"]').forEach(el => {
        if (el.id !== `eyeMenu_${userId}`) el.style.display = 'none';
    });
    const menu = document.getElementById(`eyeMenu_${userId}`);
    if (!menu) return;
    if (menu.style.display === 'none') {
        menu.style.display = 'block';
        _positionMenu(event.currentTarget, menu);
    } else {
        menu.style.display = 'none';
    }
}
document.addEventListener('click', () => {
    document.querySelectorAll('[id^="eyeMenu_"]').forEach(el => el.style.display = 'none');
});
function copyMailToClipboard(event, email) {
    event.stopPropagation();
    navigator.clipboard.writeText(email).then(() => {
        const el = event.currentTarget;
        const original = el.innerHTML;
        el.innerHTML = '<i class="fa-solid fa-check" style="width:14px;color:#34d399"></i><span style="color:#34d399">Copied!</span>';
        setTimeout(() => { el.innerHTML = original; }, 1200);
    }).catch(() => {});
}

// toggle логиката е в /static/js/admin_users.js

// Account Billing popup - показва ПЪЛНАТА billing история на потребителя
// (всички Basic/Plus/Gold покупки, активни И вече изтекли), взета от
// /admin/users/<id>/billing - същите данни каквито потребителят вижда в
// собствения си Billing/Usage таб, но без филтъра "само активните".
function openAccountBillingModal(event, userId, email) {
    event.preventDefault();
    document.querySelectorAll('[id^="eyeMenu_"]').forEach(el => el.style.display = 'none');

    const overlay = document.getElementById('accountBillingOverlay');
    const body = document.getElementById('accountBillingBody');
    document.getElementById('accountBillingEmail').textContent = email;
    body.innerHTML = '<p style="color:#94a3b8;font-size:11px;text-align:center;padding:20px 0">Loading…</p>';
    overlay.style.display = 'flex';

    fetch(`/admin/users/${userId}/billing`)
        .then(r => r.json())
        .then(data => {
            if (!data.cards || data.cards.length === 0) {
                body.innerHTML = '<p style="color:#94a3b8;font-size:11px;text-align:center;padding:20px 0">No paid subscriptions purchased yet.</p>';
                return;
            }
            let html = `<p style="color:#94a3b8;font-size:10px;margin-bottom:10px;text-transform:uppercase;letter-spacing:0.05em">Total purchases: <span style="color:#4CC9F0;font-weight:700">${data.total_purchases}</span></p>`;
            data.cards.forEach(c => {
                const statusColor = c.status === 'Active' ? '#34d399' : '#94a3b8';
                html += `
                <div style="background:#0B132B;border:1px solid rgba(100,116,139,0.25);border-radius:10px;padding:12px 14px;margin-bottom:8px">
                    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px">
                        <span style="font-size:12px;font-weight:700;color:#e2e8f0">${c.plan} Plan <span style="color:#64748b;font-weight:500;font-size:10px">${c.code}</span></span>
                        <span style="font-size:9px;font-weight:700;text-transform:uppercase;color:${statusColor}">${c.status}</span>
                    </div>
                    <p style="font-size:10px;color:#94a3b8;margin:0">From ${c.activated_at} to ${c.expires_at}</p>
                </div>`;
            });
            body.innerHTML = html;
        })
        .catch(() => {
            body.innerHTML = '<p style="color:#f87171;font-size:11px;text-align:center;padding:20px 0">Failed to load billing history.</p>';
        });
}
function closeAccountBillingModal() {
    document.getElementById('accountBillingOverlay').style.display = 'none';
}
