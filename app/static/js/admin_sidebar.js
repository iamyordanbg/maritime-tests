// app/static/js/admin_sidebar.js
// Admin Sidebar (toggle + settings modal) — извлечена от app/templates/layouts/admin_sidebar.html (Правило 1+3).
// News Center логиката е СПОДЕЛЕНА с user_sidebar - виж news_center.js, не се дублира тук.

function toggleAdminSidebar() {
    const collapsed = document.cookie.split(';').find(c => c.trim().startsWith('adminSidebarCollapsed='))?.split('=')[1]?.trim() === 'true';
    const newVal = !collapsed;
    document.cookie = 'adminSidebarCollapsed=' + newVal + ';path=/;max-age=31536000';
    window.location.reload();
}
function toggleAdminMenu(e) {
    e.stopPropagation();
    const popup = document.getElementById('adminMenuPopup');
    popup.style.display = popup.style.display === 'none' ? 'block' : 'none';
}
document.addEventListener('click', e => {
    const btn = document.getElementById('adminMenuBtn');
    const popup = document.getElementById('adminMenuPopup');
    if (popup && btn && !btn.contains(e.target) && !popup.contains(e.target)) {
        popup.style.display = 'none';
    }
});

const ADMIN_S_TABS = ['general','account','privacy'];
function openAdminSettingsModal() {
    document.getElementById('adminSettingsModal').style.display = 'block';
    showAdminSTab('general');
}
function closeAdminSettingsModal() {
    document.getElementById('adminSettingsModal').style.display = 'none';
}
document.addEventListener('keydown', e => {
    if(e.key==='Escape') {
        closeAdminSettingsModal();
        closeSupportPopup();
    }
});
function showAdminSTab(tab) {
    ADMIN_S_TABS.forEach(t => {
        const c = document.getElementById('admin-stab-content-'+t);
        const b = document.getElementById('admin-stab-'+t);
        if (!c||!b) return;
        if (t===tab) { c.style.display='block'; b.style.background='#F3F4F6'; b.style.color='#111827'; b.style.fontWeight='500'; }
        else { c.style.display='none'; b.style.background='transparent'; b.style.color='#374151'; b.style.fontWeight='400'; }
    });
}
async function adminSaveNotif(cb) {
    const track = document.getElementById('admin-notif-subscription-track');
    track.style.background = cb.checked ? '#111827' : '#e5e7eb';
    cb.nextElementSibling.nextElementSibling.style.transform = cb.checked ? 'translateX(18px)' : 'translateX(0)';
    await fetch('/settings/notifications', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({notif_subscription:cb.checked})});
}
async function adminLogoutAll() {
    const d = await (await fetch('/logout-all', {method:'POST'})).json();
    if (d.success) window.location.href = '/';
}
async function adminSmSaveProfile() {
    const fd = new FormData();
    fd.append('rank', document.getElementById('admin-sm-rankInput').value);
    fd.append('company', document.getElementById('admin-sm-companyInput').value);
    const msg = document.getElementById('admin-sm-profileMsg');
    const d = await (await fetch('/settings/profile',{method:'POST',body:fd})).json();
    msg.textContent = d.message; msg.style.color = d.success ? '#059669' : '#dc2626'; msg.style.display = 'block';
    setTimeout(()=>msg.style.display='none', 3000);
}
async function adminSmChangePassword() {
    const cur = document.getElementById('admin-sm-curPass').value;
    const np = document.getElementById('admin-sm-newPass').value;
    const cp = document.getElementById('admin-sm-confPass').value;
    const msg = document.getElementById('admin-sm-passMsg');
    if (np!==cp) { msg.textContent='Passwords do not match'; msg.style.color='#dc2626'; msg.style.display='block'; return; }
    if (np.length<6) { msg.textContent='Password too short'; msg.style.color='#dc2626'; msg.style.display='block'; return; }
    const fd = new FormData();
    fd.append('current_password',cur); fd.append('new_password',np);
    const d = await (await fetch('/settings/password',{method:'POST',body:fd})).json();
    msg.textContent = d.message; msg.style.color = d.success ? '#059669' : '#dc2626'; msg.style.display = 'block';
    if (d.success) { document.getElementById('admin-sm-curPass').value=''; document.getElementById('admin-sm-newPass').value=''; document.getElementById('admin-sm-confPass').value=''; }
    setTimeout(()=>msg.style.display='none', 3000);
}

// SUPPORT CENTER
supportCurrentTicketId = null;
let spPendingUserId = null;
let spPendingUserEmail = null;

function openSupportPopup() {
    const sidebar = document.getElementById('adminSidebar');
    const w = sidebar ? sidebar.offsetWidth : 56;
    const popup = document.getElementById('adminSupportPopup');
    popup.style.left = w + 'px';
    popup.style.display = 'flex';
    document.getElementById('spStartConv').style.display = 'none';
    document.getElementById('spEmpty').style.display = 'flex';
    document.getElementById('spChat').style.display = 'none';
    spLoadTickets();
}

// Извиква се от 'Message in Support Chat' (envelope иконата в admin/users) -
// отваря ТОЧНО този съществуващ widget (не отделна страница), и directno
// селектира/отваря разговора на дадения потребител. Ако той няма никакъв
// ticket, показва spStartConv полето вместо празното 'Изберете запитване'.
async function openSupportPopupForUser(userId, email) {
    spPendingUserId = userId;
    spPendingUserEmail = email;
    const sidebar = document.getElementById('adminSidebar');
    const w = sidebar ? sidebar.offsetWidth : 56;
    const popup = document.getElementById('adminSupportPopup');
    popup.style.left = w + 'px';
    popup.style.display = 'flex';

    const tickets = await (await fetch('/admin/support/tickets')).json();
    await spLoadTickets(tickets);
    const match = tickets.find(t => t.email === email);
    if (match) {
        spOpenTicket(match.id);
    } else {
        document.getElementById('spEmpty').style.display = 'none';
        document.getElementById('spChat').style.display = 'none';
        document.getElementById('spStartConv').style.display = 'flex';
        document.getElementById('spStartConvEmail').textContent = email;
    }
}

async function spStartConversation() {
    const body = document.getElementById('spStartConvBody').value.trim();
    if (!body || !spPendingUserId) return;
    const res = await fetch(`/admin/support/start/${spPendingUserId}`, {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({body})
    });
    const d = await res.json();
    if (d.success) {
        document.getElementById('spStartConv').style.display = 'none';
        await spLoadTickets();
        spOpenTicket(d.ticket_id);
    }
}
function closeSupportPopup() {
    document.getElementById('adminSupportPopup').style.display = 'none';
    supportCurrentTicketId = null;
}
async function spLoadTickets(preFetched) {
    const el = document.getElementById('spTicketList');
    if (!el) return;
    el.innerHTML = '<div style="text-align:center;padding:32px;color:#9ca3af"><i class="fa-solid fa-spinner fa-spin"></i></div>';
    try {
        const tickets = preFetched || await (await fetch('/admin/support/tickets')).json();
        if (!tickets.length) {
            el.innerHTML = '<div style="text-align:center;padding:40px 12px;color:#9ca3af"><i class="fa-solid fa-inbox" style="font-size:24px;margin-bottom:8px;display:block"></i><p style="font-size:12px;margin:0;font-family:\'Inter\',sans-serif">No inquiries</p></div>';
            return;
        }
        const typeMap = {
            bug: {label:'🐛 Проблем', bg:'#fef2f2', color:'#dc2626', border:'#fecaca'},
            suggestion: {label:'💡 Предложение', bg:'#eff6ff', color:'#2563eb', border:'#bfdbfe'},
            question: {label:'❓ Въпрос', bg:'#eef2ff', color:'#6366f1', border:'#c7d2fe'}
        };
        const statusMap = {
            open: {label:'Отворен', color:'#f59e0b'},
            in_progress: {label:'В процес', color:'#3b82f6'},
            closed: {label:'Затворен', color:'#9ca3af'}
        };
        el.innerHTML = tickets.map(t => {
            const tc = typeMap[t.type] || typeMap.question;
            const sc = statusMap[t.status] || statusMap.open;
            const bl = t.status==='open'?'#f59e0b':t.status==='in_progress'?'#3b82f6':'#e5e7eb';
            const bg = t.unread>0 ? '#eef2ff' : '#fff';
            return '<div onclick="spOpenTicket('+t.id+')" id="spCard_'+t.id+'"'+
                ' style="padding:12px 14px;cursor:pointer;border-bottom:1px solid #f3f4f6;border-left:3px solid '+bl+';background:'+bg+';transition:background 0.15s"'+
                ' data-hover="1"'+
                ' data-bg2="'+bg+'"' +
                '<p style="font-size:12px;font-weight:'+(t.unread>0?'700':'500')+';color:'+(t.unread>0?'#6366f1':'#111827')+';margin:0 0 2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-family:\'Inter\',sans-serif">'+spEsc(t.email)+'</p>'+
                (t.name?'<p style="font-size:11px;color:#6b7280;margin:0 0 6px;font-family:\'Inter\',sans-serif">'+spEsc(t.name)+'</p>':'<div style="margin-bottom:6px"></div>')+
                '<div style="display:flex;align-items:center;justify-content:space-between;gap:4px">'+
                '<span style="font-size:9px;font-weight:700;padding:2px 7px;border-radius:20px;background:'+tc.bg+';color:'+tc.color+';border:1px solid '+tc.border+';font-family:\'Inter\',sans-serif">'+tc.label+'</span>'+
                '<span style="font-size:9px;font-weight:600;color:'+sc.color+';font-family:\'Inter\',sans-serif">● '+sc.label+'</span>'+
                '</div></div>';
        }).join('');
    } catch(e) {
        el.innerHTML = '<div style="padding:16px;color:#9ca3af;font-size:12px">Error</div>';
    }
}
async function spOpenTicket(id) {
    supportCurrentTicketId = id;
    document.querySelectorAll('[id^="spCard_"]').forEach(el => el.style.background = '#fff');
    const card = document.getElementById('spCard_' + id);
    if (card) card.style.background = '#eef2ff';
    document.getElementById('spStartConv').style.display = 'none';
    document.getElementById('spEmpty').style.display = 'none';
    const chat = document.getElementById('spChat');
    chat.style.display = 'flex';
    chat.style.flexDirection = 'column';
    await spLoadMessages(id);
    // Обновяваме badge веднага
    refreshSupportBadge();
}


async function spLoadMessages(id) {
    const el = document.getElementById('spMessages');
    el.innerHTML = '<div style="text-align:center;padding:20px;color:#9ca3af"><i class="fa-solid fa-spinner fa-spin"></i></div>';
    const data = await (await fetch('/admin/support/' + id + '/messages')).json();
    const typeLabels = {bug:'🐛 Проблем', suggestion:'💡 Предложение', question:'❓ Въпрос'};
    const statusLabels = {open:'Отворен', in_progress:'В процес', closed:'Затворен'};
    document.getElementById('spChatEmail').textContent = data.user.email;
    document.getElementById('spChatMeta').textContent = (data.user.name||'') + ' · ' + (typeLabels[data.ticket.type]||'') + ' · ' + (statusLabels[data.ticket.status]||'');
    document.getElementById('spCloseTicketBtn').style.display = data.ticket.status==='closed' ? 'none' : 'block';
    el.innerHTML = data.messages.map(m =>
        '<div style="display:flex;'+(m.sender==='admin'?'justify-content:flex-end':'justify-content:flex-start')+'">'+
        '<div style="max-width:70%;padding:10px 14px;line-height:1.5;font-family:\'Inter\',sans-serif;'+
        'border-radius:'+(m.sender==='admin'?'14px 14px 4px 14px':'14px 14px 14px 4px')+';'+
        'background:'+(m.sender==='admin'?'#111827':'#f3f4f6')+';'+
        'color:'+(m.sender==='admin'?'#fff':'#111827')+'">'+
        '<p style="font-size:13px;margin:0 0 3px">'+spEsc(m.body)+'</p>'+
        '<p style="font-size:10px;margin:0;opacity:0.5;text-align:right">'+(m.sender==='admin'?'Вие':spEsc(data.user.name||'User'))+' · '+m.created_at+'</p>'+
        '</div></div>'
    ).join('');
    el.scrollTop = el.scrollHeight;
}
async function spSendReply() {
    const body = document.getElementById('spReplyInput').value.trim();
    if (!body || !supportCurrentTicketId) return;
    const fd = new FormData();
    fd.append('body', body);
    const d = await (await fetch('/admin/support/'+supportCurrentTicketId+'/reply',{method:'POST',body:fd})).json();
    if (d.success) {
        document.getElementById('spReplyInput').value = '';
        await spLoadMessages(supportCurrentTicketId);
        await spLoadTickets();
        refreshSupportBadge();
    }
}
async function spCloseTicket() {
    if (!supportCurrentTicketId) return;
    const d = await (await fetch('/admin/support/'+supportCurrentTicketId+'/close',{method:'POST'})).json();
    if (d.success) {
        document.getElementById('spCloseTicketBtn').style.display = 'none';
        await spLoadMessages(supportCurrentTicketId);
        await spLoadTickets();
        refreshSupportBadge();
    }
}
function spEsc(s) {
    return String(s||'').replace(/&/g,'&amp;').replace(/\x3c/g,'&lt;').replace(/\x3e/g,'&gt;');
}

window.addEventListener('pageshow', function() {
    document.getElementById('adminSettingsModal').style.display = 'none';
    document.getElementById('adminMenuPopup').style.display = 'none';
    document.getElementById('adminSupportPopup').style.display = 'none';
    supportCurrentTicketId = null;
});
