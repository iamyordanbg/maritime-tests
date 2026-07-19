// app/static/js/layouts_support.js
// User Support Center popup — извлечена от app/templates/layouts/support.html (Правило 1).

let currentAdminTicketId = null;

async function openAdminTicket(id, subject) {
    currentAdminTicketId = id;
    document.getElementById('noTicketSelected').style.display = 'none';
    const detail = document.getElementById('ticketDetailContent');
    detail.style.display = 'flex';
    document.getElementById('adminTicketTitle').textContent = subject;
    document.getElementById('adminReplyBody').value = '';
    await loadAdminMessages();
}

async function loadAdminMessages() {
    const el = document.getElementById('adminTicketMessages');
    el.innerHTML = '<div style="text-align:center;padding:20px;color:#64748b"><i class="fa-solid fa-spinner fa-spin"></i></div>';
    const data = await (await fetch('/admin/support/' + currentAdminTicketId + '/messages')).json();
    document.getElementById('adminTicketMeta').textContent =
        data.user.name + ' · ' + data.user.email + ' · ' +
        (data.ticket.status === 'open' ? 'Отворен' : data.ticket.status === 'in_progress' ? 'В процес' : 'Затворен');
    const closeBtn = document.getElementById('closeTicketBtn');
    closeBtn.style.display = data.ticket.status === 'closed' ? 'none' : 'block';
    el.innerHTML = data.messages.map(m => `
        <div style="display:flex;${m.sender === 'admin' ? 'justify-content:flex-end' : 'justify-content:flex-start'}">
            <div style="max-width:75%;padding:10px 14px;border-radius:${m.sender === 'admin' ? '16px 16px 4px 16px' : '16px 16px 16px 4px'};
                background:${m.sender === 'admin' ? '#4CC9F0' : 'rgba(255,255,255,0.07)'};
                color:${m.sender === 'admin' ? '#0B132B' : '#e2e8f0'}">
                <p style="font-size:13px;margin:0 0 4px;line-height:1.5">${m.body}</p>
                <p style="font-size:10px;margin:0;opacity:0.6;text-align:right">${m.sender === 'admin' ? 'Вие' : 'Потребител'} · ${m.created_at}</p>
            </div>
        </div>
    `).join('');
    el.scrollTop = el.scrollHeight;
}

async function sendAdminReply() {
    const body = document.getElementById('adminReplyBody').value.trim();
    if (!body) return;
    const fd = new FormData();
    fd.append('body', body);
    const d = await (await fetch('/admin/support/' + currentAdminTicketId + '/reply', {method:'POST', body:fd})).json();
    if (d.success) {
        document.getElementById('adminReplyBody').value = '';
        await loadAdminMessages();
        // Обновяваме ticket item
        const item = document.getElementById('adminTicketItem_' + currentAdminTicketId);
        if (item) item.style.background = 'transparent';
    }
}

async function closeAdminTicket() {
    const d = await (await fetch('/admin/support/' + currentAdminTicketId + '/close', {method:'POST'})).json();
    if (d.success) location.reload();
}

// bfcache fix
window.addEventListener('pageshow', function() {
    document.getElementById('noTicketSelected').style.display = 'flex';
    const detail = document.getElementById('ticketDetailContent');
    if (detail) detail.style.display = 'none';
});
