// app/static/js/admin_promos.js
// Admin Plans & Promo управление — извлечена от app/templates/admin/promos.html (Правило 1).

document.getElementById('usageLimitType').addEventListener('change', function() {
    document.getElementById('usageLimitCountWrap').classList.toggle('hidden', this.value !== 'custom');
});
document.getElementById('promo-create-btn').addEventListener('click', createPromo);
document.getElementById('promo-copycode-btn').addEventListener('click', copyCode);
document.getElementById('bulkDeleteBtn').addEventListener('click', confirmBulkDelete);
document.getElementById('selectAllPromos').addEventListener('click', function() { toggleSelectAll(this); });
document.getElementById('promo-confirm-cancel-btn').addEventListener('click', closeConfirmModal);
document.getElementById('promo-details-close-btn').addEventListener('click', closePlanDetails);
document.getElementById('planDetailsOverlay').addEventListener('click', function(e) {
    if (e.target === this) closePlanDetails();
});
document.getElementById('promoTable').addEventListener('click', function(e) {
    const checkEl = e.target.closest('.promo-check');
    if (checkEl) { updateBulkBar(); return; }
    const detailsBtn = e.target.closest('.promo-showdetails-btn');
    if (detailsBtn) { showPlanDetails(JSON.parse(detailsBtn.dataset.plan)); return; }
    const copyBtn = e.target.closest('.promo-copytext-btn');
    if (copyBtn) { copyText(copyBtn.dataset.code); return; }
    const delBtn = e.target.closest('.promo-delete-btn');
    if (delBtn) { deletePromo(delBtn.dataset.promoid); return; }
    const delPayBtn = e.target.closest('.promo-deletepayment-btn');
    if (delPayBtn) { deletePayment(delPayBtn.dataset.paymentid); }
});

async function createPromo() {
    const restrictedEmail = document.getElementById('restrictedEmail').value.trim();
    const autoEmail = document.getElementById('autoEmail').checked;
    if (autoEmail && !restrictedEmail) {
        alert("Auto-email is checked, but the 'Restrict to email' field is empty - no recipient. Enter an email address or uncheck the box.");
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

async function deletePayment(id) {
    openConfirmModal('This payment/plan will be permanently deleted - the user will lose access. Continue?', async () => {
        try {
            const res = await fetch(`/admin/payments/${id}/delete`, { method: 'POST' });
            if (!res.ok) { showToast('Error: server returned ' + res.status, false); return; }
            const data = await res.json();
            if (data.success) {
                const row = document.getElementById(`payment_row_${id}`);
                if (row) row.remove();
                showToast('✓ Payment deleted');
                updateBulkBar();
            } else {
                showToast(data.message || 'Delete failed', false);
            }
        } catch (e) {
            showToast('Server connection error — check console', false);
            console.error('deletePayment failed:', e);
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
        ['Type', p.plan_type_label],
        ['Access type', p.access_type || '—'],
        ['Price', p.price != null ? p.price + ' €' : '—'],
        ['Test type (department)', p.department_restriction ? p.department_restriction.charAt(0).toUpperCase()+p.department_restriction.slice(1) : 'All (chosen at activation)'],
        ['Duration after activation', p.duration_days + ' days'],
        // БЪГ ФИКС: тези 4 полета са концепции, приложими САМО за Custom
        // Promo кодове (chakащ период за активиране, email ограничение,
        // брой теми, custom usage limit) - за стандартни планове (Basic/
        // Plus/Gold) преди тук имаше hardcode-нати fallback стойности
        // (|| 30, 'No restriction', || 1, '1 person'), които СЪЗДАВАХА
        // ВПЕЧАТЛЕНИЕ, че тези настройки реално важат за стандартния план,
        // докато той просто няма такава концепция. Никакъв hardcode
        // fallback вече не се прилага без изрично одобрение (виж
        // NEXT_SESSION_PROMPT.md) - показва се честно 'N/A (стандартен план)'.
        ['Activation period (stand-by)', (p.is_custom || p.activation_window_days != null) ? (p.activation_window_days + ' days') : 'N/A (direct activation)'],
        ['Topics allowed', p.topics_allowed],
        ['Tests quota', p.tests_quota_override],
        ['Restricted to email', p.is_custom ? (p.restricted_email || 'No restriction') : 'N/A (direct payment)'],
        ['Usage limit', p.is_custom
            ? (p.usage_limit_type === 'custom' ? ('Custom — ' + (p.usage_limit_count||1) + ' activations') : (p.usage_limit_type === 'multiple' ? 'Multiple (unlimited)' : '1 person'))
            : '1 person (own account)'],
        ['Used so far', p.used_count || 0],
        ['Activated department', p.department || '—'],
        ['Activated level', p.level || '—'],
        ['Internal note', p.internal_note || '—'],
    ];
    let html = '';
    rows.forEach(([label, value]) => {
        html += `<div class="promo-details-row">
            <span class="promo-details-label">${label}</span>
            <span class="promo-details-value">${value}</span>
        </div>`;
    });
    document.getElementById('planDetailsBody').innerHTML = html;
    document.getElementById('planDetailsOverlay').classList.add('promo-details-overlay-open');
}

function closePlanDetails() {
    document.getElementById('planDetailsOverlay').classList.remove('promo-details-overlay-open');
}
