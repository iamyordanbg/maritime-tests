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
