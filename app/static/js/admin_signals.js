// app/static/js/admin_signals.js
// Admin Signals управление — извлечена от app/templates/admin/signals.html (Правило 1+2).

let currentSignalId = null;

// ---------- Event wiring (заменя премахнатите onclick/onmouseover) ----------
document.querySelectorAll('.sg-card').forEach(card => {
    card.addEventListener('click', () => {
        openSignal(card.dataset.signalid, card.dataset.username, card.dataset.message,
            card.dataset.type, card.dataset.created, card.dataset.reply, card.dataset.status);
    });
});
document.querySelectorAll('.sg-actions').forEach(actions => {
    actions.addEventListener('click', e => e.stopPropagation());
});
document.querySelectorAll('.sg-reply-btn').forEach(btn => {
    btn.addEventListener('click', () => openReply(btn.dataset.signalid, btn.dataset.message, btn.dataset.username));
});
document.querySelectorAll('.sg-resolve-btn').forEach(btn => {
    btn.addEventListener('click', () => resolveSignal(btn.dataset.signalid));
});
document.querySelectorAll('.sg-delete-btn').forEach(btn => {
    btn.addEventListener('click', () => deleteSignal(btn.dataset.signalid));
});
document.getElementById('sg-detail-close-btn')?.addEventListener('click', closeDetail);
document.getElementById('sg-detail-close-btn2')?.addEventListener('click', closeDetail);
document.getElementById('detailReplyBtn')?.addEventListener('click', closeDetailAndReply);
document.getElementById('sg-reply-close-btn')?.addEventListener('click', closeReply);
document.getElementById('sg-reply-cancel-btn')?.addEventListener('click', closeReply);
document.getElementById('sg-reply-send-btn')?.addEventListener('click', sendReply);

// Отваряме детайл на сигнал
function openSignal(id, name, message, type, date, reply, status) {
    currentSignalId = id;
    document.getElementById('detailTitle').textContent = name + ' — ' + date;
    document.getElementById('detailMeta').innerHTML =
        '<span class="sg-detail-type-badge">' + type + '</span>' +
        (status === 'resolved' ? '<span class="sg-detail-resolved">✓ Решен</span>' : '<span class="sg-detail-pending">⏳ Чака отговор</span>');
    document.getElementById('detailMessage').textContent = message;
    const replyDiv = document.getElementById('detailReply');
    if (reply) {
        document.getElementById('detailReplyText').textContent = reply;
        replyDiv.classList.remove('hidden');
    } else {
        replyDiv.classList.add('hidden');
    }
    document.getElementById('signalDetailModal').classList.add('sg-modal-open');
}

function closeDetail() {
    document.getElementById('signalDetailModal').classList.remove('sg-modal-open');
}

function closeDetailAndReply() {
    closeDetail();
    const el = document.getElementById('signal_' + currentSignalId);
    if (el) {
        openReply(currentSignalId, el.dataset.message, el.dataset.username);
    }
}

// Reply Modal
function openReply(id, message, userName) {
    currentSignalId = id;
    document.getElementById('replyOrigMsg').innerHTML = '<strong class="sg-reply-orig-name">' + userName + ':</strong> ' + message;
    document.getElementById('replyText').value = '';
    document.getElementById('replyCount').textContent = '0/500';
    document.getElementById('replyModal').classList.add('sg-modal-open');
}

function closeReply() {
    document.getElementById('replyModal').classList.remove('sg-modal-open');
}

document.getElementById('replyText')?.addEventListener('input', function() {
    document.getElementById('replyCount').textContent = this.value.length + '/500';
});

async function sendReply() {
    const reply = document.getElementById('replyText').value.trim();
    if (!reply) return;
    const fd = new FormData();
    fd.append('reply', reply);
    const res = await fetch('/admin/signals/' + currentSignalId + '/reply', {method:'POST', body:fd});
    const d = await res.json();
    if (d.success) {
        closeReply();
        location.reload();
    }
}

async function resolveSignal(id) {
    const res = await fetch('/admin/signals/' + id + '/resolve', {method:'POST'});
    const d = await res.json();
    if (d.success) location.reload();
}

async function deleteSignal(id) {
    if (!confirm('Delete this signal?')) return;
    const res = await fetch('/admin/signals/' + id + '/delete', {method:'POST'});
    const d = await res.json();
    if (d.success) {
        const el = document.getElementById('signal_' + id);
        if (el) el.remove();
    }
}

// Escape затваря модалите
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        closeDetail();
        closeReply();
    }
});

// bfcache fix
window.addEventListener('pageshow', function() {
    closeDetail();
    closeReply();
});
