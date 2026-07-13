// app/static/js/admin_promos.js
// Admin Plans & Promo управление — извлечена от app/templates/admin/promos.html (Правило 1).

async function createPromo() {
    const restrictedEmail = document.getElementById('restrictedEmail').value.trim();
    const autoEmail = document.getElementById('autoEmail').checked;
    if (autoEmail && !restrictedEmail) {
        alert("Auto-email е маркиран, но полето 'Restrict to email' е празно - няма получател. Въведи имейл адрес или махни отметката.");
        return;
    }
    const fd = new FormData();
    fd.append('promo_name', document.getElementById('promoName').value);
    fd.append('client_name', document.getElementById('clientName').value);
    fd.append('access_type', document.getElementById('accessType').value);
    fd.append('price', document.getElementById('promoPrice').value || 0);
    fd.append('department_restriction', document.getElementById('departmentRestriction').value);
    fd.append('duration_days', document.getElementById('durationDays').value || 30);
    fd.append('activation_window_days', document.getElementById('activationWindowDays').value || 30);
    fd.append('topics_allowed', document.getElementById('topicsAllowed').value || 1);
    fd.append('tests_quota_override', document.getElementById('testsQuotaOverride').value || 50);
    fd.append('restricted_email', document.getElementById('restrictedEmail').value);
    fd.append('usage_limit_type', document.getElementById('usageLimitType').value);
    fd.append('usage_limit_count', document.getElementById('usageLimitCount').value || 1);
    fd.append('internal_note', document.getElementById('internalNote').value);
    fd.append('auto_email', document.getElementById('autoEmail').checked ? '1' : '0');
    const res = await fetch('/admin/promos/create', { method: 'POST', body: fd });
    const data = await res.json();
    if (data.success) {
        document.getElementById('newCodeText').textContent = data.code;
        document.getElementById('newCodeDisplay').classList.remove('hidden');
        if (data.email_sent) showToast('✓ Code emailed automatically', true);
        setTimeout(() => location.reload(), 3000);
    }
}
function copyCode() { copyText(document.getElementById('newCodeText').textContent); }
function copyText(text) {
    navigator.clipboard.writeText(text).then(() => {
        const t = document.createElement('div');
        t.className = 'fixed bottom-6 right-6 z-[100] px-4 py-3 rounded-xl text-[11px] font-bold shadow-2xl border bg-emerald-500/20 border-emerald-500/40 text-emerald-300';
        t.textContent = '✓ Code copied!';
        document.body.appendChild(t);
        setTimeout(() => t.remove(), 3000);
    });
}

function showToast(text, ok=true) {
    const t = document.createElement('div');
    t.className = 'fixed bottom-6 right-6 z-[210] px-4 py-3 rounded-xl text-[11px] font-bold shadow-2xl border ' +
        (ok ? 'bg-emerald-500/20 border-emerald-500/40 text-emerald-300' : 'bg-rose-500/20 border-rose-500/40 text-rose-300');
    t.textContent = text;
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 4000);
}

function openConfirmModal(text, onConfirm) {
    document.getElementById('confirmModalText').textContent = text;
    document.getElementById('confirmModal').classList.remove('hidden');
    const btn = document.getElementById('confirmModalBtn');
    const newBtn = btn.cloneNode(true); // clears old listeners
    btn.parentNode.replaceChild(newBtn, btn);
    newBtn.addEventListener('click', () => { closeConfirmModal(); onConfirm(); });
}
function closeConfirmModal() {
    document.getElementById('confirmModal').classList.add('hidden');
}

async function deletePromo(id) {
    openConfirmModal('This promo code will be permanently deleted. Continue?', async () => {
        try {
            const res = await fetch(`/admin/promos/${id}/delete`, { method: 'POST' });
            if (!res.ok) { showToast('Error: server returned ' + res.status, false); return; }
            const data = await res.json();
            if (data.success) {
                const row = document.getElementById(`promo_row_${id}`);
                if (row) row.remove();
                showToast('✓ Promo code deleted');
                updateBulkBar();
            } else {
                showToast(data.message || 'Delete failed', false);
            }
        } catch (e) {
            showToast('Server connection error — check console', false);
            console.error('deletePromo failed:', e);
        }
    });
}

function toggleSelectAll(checkbox) {
    document.querySelectorAll('.promo-check').forEach(cb => cb.checked = checkbox.checked);
    updateBulkBar();
}

function updateBulkBar() {
    const checked = document.querySelectorAll('.promo-check:checked');
    const btn = document.getElementById('bulkDeleteBtn');
    document.getElementById('selectedCount').textContent = checked.length;
    btn.disabled = checked.length === 0;

    const all = document.querySelectorAll('.promo-check');
    const selectAll = document.getElementById('selectAllPromos');
    if (selectAll) selectAll.checked = all.length > 0 && checked.length === all.length;
}

function confirmBulkDelete() {
    const checked = Array.from(document.querySelectorAll('.promo-check:checked')).map(cb => cb.value);
    if (checked.length === 0) return;

    openConfirmModal(`${checked.length} promo code(s) will be permanently deleted. Continue?`, async () => {
        try {
            const res = await fetch('/admin/promos/bulk-delete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ids: checked })
            });
            if (!res.ok) { showToast('Error: server returned ' + res.status, false); return; }
            const data = await res.json();
            if (data.success) {
                checked.forEach(id => {
                    const row = document.getElementById(`promo_row_${id}`);
                    if (row) row.remove();
                });
                showToast(`✓ Deleted ${data.deleted} promo code(s)`);
                updateBulkBar();
            } else {
                showToast(data.message || 'Delete failed', false);
            }
        } catch (e) {
            showToast('Server connection error — check console', false);
            console.error('bulkDelete failed:', e);
        }
    });
}

function showPlanDetails(p) {
    const rows = [
        ['Code', p.code || '—'],
        ['Promo name', p.promo_name || '—'],
        ['Holder', p.client_name || '—'],
        ['Type', p.is_custom ? 'Custom (Promo)' : 'Standard Gold'],
        ['Access type', p.access_type || '—'],
        ['Price', p.price != null ? p.price + ' €' : '—'],
        ['Test type (department)', p.department_restriction ? p.department_restriction.charAt(0).toUpperCase()+p.department_restriction.slice(1) : 'All (chosen at activation)'],
        ['Duration after activation', (p.duration_days || 30) + ' days'],
        ['Activation period (stand-by)', (p.activation_window_days || 30) + ' days'],
        ['Topics allowed', p.topics_allowed || 1],
        ['Tests quota', p.tests_quota_override || 50],
        ['Restricted to email', p.restricted_email || 'No restriction'],
        ['Usage limit', p.usage_limit_type === 'custom' ? ('Custom — ' + (p.usage_limit_count||1) + ' activations') : (p.usage_limit_type === 'multiple' ? 'Multiple (unlimited)' : '1 person'),],
        ['Used so far', p.used_count || 0],
        ['Activated department', p.department || '—'],
        ['Activated level', p.level || '—'],
        ['Internal note', p.internal_note || '—'],
    ];
    let html = '';
    rows.forEach(([label, value]) => {
        html += `<div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.06)">
            <span style="color:#94a3b8;font-size:11px">${label}</span>
            <span style="color:#fff;font-size:11px;font-weight:600;text-align:right;max-width:60%">${value}</span>
        </div>`;
    });
    document.getElementById('planDetailsBody').innerHTML = html;
    document.getElementById('planDetailsOverlay').style.display = 'flex';
}

function closePlanDetails() {
    document.getElementById('planDetailsOverlay').style.display = 'none';
}
