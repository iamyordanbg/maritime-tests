// app/static/js/admin_signals.js
// Admin Signals управление — извлечена от app/templates/admin/signals.html (Правило 1).

let currentSignalId = null;

// Отваряме детайл на сигнал
function openSignal(id, name, message, type, date, reply, status) {
    currentSignalId = id;
    document.getElementById('detailTitle').textContent = name + ' — ' + date;
    document.getElementById('detailMeta').innerHTML =
        '<span style="font-size:9px;font-weight:700;padding:2px 8px;border-radius:4px;background:rgba(76,201,240,0.1);color:#4CC9F0;border:1px solid rgba(76,201,240,0.2)">' + type + '</span>' +
        (status === 'resolved' ? '<span style="font-size:9px;color:#4ade80">✓ Решен</span>' : '<span style="font-size:9px;color:#f59e0b">⏳ Чака отговор</span>');
    document.getElementById('detailMessage').textContent = message;
    const replyDiv = document.getElementById('detailReply');
    if (reply) {
        document.getElementById('detailReplyText').textContent = reply;
        replyDiv.style.display = 'block';
    } else {
        replyDiv.style.display = 'none';
    }
    document.getElementById('signalDetailModal').style.display = 'block';
}

function closeDetail() {
    document.getElementById('signalDetailModal').style.display = 'none';
}

function closeDetailAndReply() {
    closeDetail();
    const el = document.getElementById('signal_' + currentSignalId);
    if (el) {
        const msg = el.querySelector('p[style*="text-overflow"]');
        const name = el.querySelector('span[style*="font-weight:700"]');
        openReply(currentSignalId, msg ? msg.textContent : '', name ? name.textContent : '');
    }
}

// Reply Modal
function openReply(id, message, userName) {
    currentSignalId = id;
    document.getElementById('replyOrigMsg').innerHTML = '<strong style="color:#fff">' + userName + ':</strong> ' + message;
    document.getElementById('replyText').value = '';
    document.getElementById('replyCount').textContent = '0/500';
    document.getElementById('replyModal').style.display = 'block';
}

function closeReply() {
    document.getElementById('replyModal').style.display = 'none';
}

document.getElementById('replyText').addEventListener('input', function() {
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
    if (!confirm('Изтриване на сигнала?')) return;
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
