// app/static/js/support_center.js
// Support center (tickets + signals) — извлечена от sidebar.js (Правило 1+3).
function openSupportCenter() {
    document.getElementById('supportModal').style.display = 'block';
    showTicketList();
    loadTickets();
}

function closeSupportModal() {
    document.getElementById('supportModal').style.display = 'none';
}

function showTicketList() {
    document.getElementById('ticketListView').style.display = 'block';
    document.getElementById('newTicketView').style.display = 'none';
    document.getElementById('ticketDetailView').style.display = 'none';
    document.getElementById('supportTitle').textContent = 'Support Center';
    document.getElementById('supportBackBtn').style.display = 'none';
    document.getElementById('newTicketBtn').style.display = 'block';
    document.getElementById('supportFooter').style.display = 'flex';
}

function showNewTicket() {
    document.getElementById('ticketListView').style.display = 'none';
    document.getElementById('newTicketView').style.display = 'block';
    document.getElementById('ticketDetailView').style.display = 'none';
    document.getElementById('supportTitle').textContent = 'New ticket';
    document.getElementById('supportBackBtn').style.display = 'block';
    document.getElementById('supportFooter').style.display = 'none';
    document.getElementById('ticketSubject').value = '';
    document.getElementById('ticketBody').value = '';
    document.getElementById('ticketBodyCount').textContent = '0/500';
    document.getElementById('newTicketStatus').style.display = 'none';
    setTicketType('question');
}

function setTicketType(type) {
    currentTicketType = type;
    const cfg = {
        bug:        { border:'#fca5a5', bg:'#fef2f2', color:'#dc2626' },
        suggestion: { border:'#93c5fd', bg:'#eff6ff', color:'#2563eb' },
        question:   { border:'#a5b4fc', bg:'#eef2ff', color:'#6366f1' }
    };
    ['bug','suggestion','question'].forEach(t => {
        const btn = document.getElementById('ttype-' + t);
        if (!btn) return;
        if (t === type) {
            const s = cfg[t];
            btn.style.background  = s.bg;
            btn.style.color       = s.color;
            btn.style.borderColor = s.border;
            btn.style.boxShadow   = 'none';
        } else {
            btn.style.background  = '#f9fafb';
            btn.style.color       = '#9ca3af';
            btn.style.borderColor = '#d1d5db';
            btn.style.boxShadow   = 'none';
        }
    });
}

function escapeHtml(s) {
    return String(s).replace(/&/g,'&amp;').replace(/\x3c/g,'&lt;').replace(/\x3e/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

async function loadTickets() {
    const el = document.getElementById('ticketListContent');
    el.innerHTML = '<div style="text-align:center;padding:40px 0;color:#9ca3af"><i class="fa-solid fa-spinner fa-spin" style="font-size:24px;margin-bottom:12px;display:block"></i>Loading...</div>';
    const tickets = await (await fetch('/support/tickets')).json();
    if (!tickets.length) {
        el.innerHTML = '<div style="text-align:center;padding:48px 0"><i class="fa-solid fa-inbox" style="font-size:36px;color:#d1d5db;display:block;margin-bottom:12px"></i><p style="color:#9ca3af;font-size:13px;margin:0">No tickets yet</p><p style="color:#c4c9d0;font-size:11px;margin:6px 0 0">Натиснете "+ New ticket" за да се свържете с нас</p></div>';
        return;
    }
    const typeIcons = { bug:'🐞', suggestion:'💡', question:'❓' };
    const statusColors = {open:'#f59e0b',in_progress:'#3b82f6',closed:'#9ca3af'};
    const statusLabels = {open:'Отворен',in_progress:'В процес',closed:'Затворен'};
    el.innerHTML = tickets.map(t => `
        <div onclick="openTicket(${t.id}, '${t.subject.replace(/'/g,"\'")}')"
            style="display:flex;align-items:center;gap:12px;padding:12px;border-radius:10px;border:1px solid ${t.unread > 0 ? '#bfdbfe' : '#f3f4f6'};background:${t.unread > 0 ? '#eff6ff' : '#fff'};cursor:pointer;margin-bottom:8px;transition:all 0.2s"
            onmouseover="this.style.borderColor='#d1d5db'" onmouseout="this.style.borderColor='${t.unread > 0 ? '#bfdbfe' : '#f3f4f6'}'">
            <div style="width:36px;height:36px;border-radius:8px;background:#f9fafb;border:1px solid #e5e7eb;display:flex;align-items:center;justify-content:center;font-size:18px;flex-shrink:0">
                ${typeIcons[t.type] || typeIcons['question']}
            </div>
            <div style="flex:1;min-width:0">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:2px">
                    <span style="font-size:13px;font-weight:${t.unread > 0 ? '700' : '500'};color:#111827;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:240px">${escapeHtml(t.subject)}</span>
                    <span style="font-size:10px;color:${statusColors[t.status]};flex-shrink:0;margin-left:8px">${statusLabels[t.status]}</span>
                </div>
                <div style="display:flex;justify-content:space-between;align-items:center">
                    <span style="font-size:11px;color:#9ca3af;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:240px">${escapeHtml(t.last_message || '')}</span>
                    <div style="display:flex;align-items:center;gap:6px;flex-shrink:0;margin-left:8px">
                        ${t.unread > 0 ? '<span style="background:#3b82f6;color:#fff;font-size:9px;font-weight:700;border-radius:10px;padding:1px 6px">' + t.unread + ' ново</span>' : ''}
                        <span style="font-size:10px;color:#d1d5db">${t.updated_at}</span>
                    </div>
                </div>
            </div>
            <i class="fa-solid fa-chevron-right" style="color:#d1d5db;font-size:11px;flex-shrink:0"></i>
        </div>
    `).join('');
}

async function openTicket(id, subject) {
    currentTicketId = id;
    document.getElementById('ticketListView').style.display = 'none';
    document.getElementById('newTicketView').style.display = 'none';
    const detailView = document.getElementById('ticketDetailView');
    detailView.style.display = 'flex';
    document.getElementById('supportTitle').textContent = subject;
    document.getElementById('supportBackBtn').style.display = 'block';
    document.getElementById('newTicketBtn').style.display = 'none';
    document.getElementById('ticketReplyBody').value = '';
    await loadTicketMessages();
    updateSupportBadge();
}

async function loadTicketMessages() {
    const el = document.getElementById('ticketMessages');
    el.innerHTML = '<div style="text-align:center;padding:20px;color:#9ca3af"><i class="fa-solid fa-spinner fa-spin"></i></div>';
    const data = await (await fetch('/support/tickets/' + currentTicketId + '/messages')).json();
    el.innerHTML = data.messages.map(m => `
        <div style="display:flex;${m.sender === 'user' ? 'justify-content:flex-end' : 'justify-content:flex-start'}">
            <div style="max-width:75%;padding:10px 14px;border-radius:${m.sender === 'user' ? '16px 16px 4px 16px' : '16px 16px 16px 4px'};
                background:${m.sender === 'user' ? '#0B132B' : '#f3f4f6'};
                color:${m.sender === 'user' ? '#fff' : '#111827'}">
                <p style="font-size:13px;margin:0 0 4px;line-height:1.5">${escapeHtml(m.body)}</p>
                <p style="font-size:10px;margin:0;opacity:0.6;text-align:right">${m.created_at}</p>
            </div>
        </div>
    `).join('');
    el.scrollTop = el.scrollHeight;
}

async function submitNewTicket() {
    const subject = document.getElementById('ticketSubject').value.trim();
    const body = document.getElementById('ticketBody').value.trim();
    const status = document.getElementById('newTicketStatus');
    if (!subject || !body) {
        status.textContent = 'Моля попълнете всички полета.';
        status.style.color = '#dc2626';
        status.style.display = 'block';
        return;
    }
    const fd = new FormData();
    fd.append('subject', subject);
    fd.append('body', body);
    fd.append('type', currentTicketType);
    const d = await (await fetch('/support/tickets', {method:'POST', body:fd})).json();
    if (d.success) {
        showTicketList();
        loadTickets();
    } else {
        status.textContent = d.message || 'Грешка.';
        status.style.color = '#dc2626';
        status.style.display = 'block';
    }
}

async function sendTicketReply() {
    const body = document.getElementById('ticketReplyBody').value.trim();
    if (!body) return;
    const fd = new FormData();
    fd.append('body', body);
    const d = await (await fetch('/support/tickets/' + currentTicketId + '/reply', {method:'POST', body:fd})).json();
    if (d.success) {
        document.getElementById('ticketReplyBody').value = '';
        await loadTicketMessages();
    }
}

async function updateSupportBadge() {
    try {
        const d = await (await fetch('/support/unread')).json();
        const badge = document.getElementById('inboxBadge');
        const icon  = document.getElementById('inboxIcon');
        const btn   = document.getElementById('inboxBtn');
        if (!badge) return;
        if (d.count > 0) {
            badge.textContent = d.count; badge.style.display = 'flex';
            if (icon) icon.style.color = '#F59E0B';
            if (btn) btn.style.borderColor = 'rgba(245,158,11,0.4)';
        } else {
            badge.style.display = 'none';
            if (icon) icon.style.color = 'rgba(148,163,184,1)';
            if (btn) btn.style.borderColor = '';
        }
    } catch(e) {}
}

// Проверяваме на всеки 60 секунди
updateSupportBadge();
setInterval(updateSupportBadge, 60000);


// ══ NEWS CENTER ══
let currentNewsPostId = null;
