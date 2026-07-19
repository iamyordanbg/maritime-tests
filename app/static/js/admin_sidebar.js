// app/static/js/admin_sidebar.js
// Admin Sidebar (toggle + settings modal) — извлечена от app/templates/layouts/admin_sidebar.html (Правило 1+2+3).
// News Center логиката е СПОДЕЛЕНА с user_sidebar - виж news_center.js, не се дублира тук.

// ---------- Event wiring (заменя премахнатите onclick) ----------
document.getElementById('adminSidebarToggleBtn')?.addEventListener('click', toggleAdminSidebar);
document.getElementById('admin-support-link')?.addEventListener('click', function(e) {
    e.preventDefault();
    openSupportPopup();
});
document.getElementById('admin-news-btn')?.addEventListener('click', openNewsCenter);
document.getElementById('adminMenuBtn')?.addEventListener('click', toggleAdminMenu);
document.getElementById('admin-open-settings-btn')?.addEventListener('click', function() {
    openAdminSettingsModal();
    document.getElementById('adminMenuPopup').classList.remove('admin-menu-popup-open');
});
document.getElementById('adminSettingsModal')?.addEventListener('click', function(e) {
    if (e.target === this) closeAdminSettingsModal();
});
document.getElementById('admin-stab-general')?.addEventListener('click', () => showAdminSTab('general'));
document.getElementById('admin-stab-account')?.addEventListener('click', () => showAdminSTab('account'));
document.getElementById('admin-stab-privacy')?.addEventListener('click', () => showAdminSTab('privacy'));
document.getElementById('asm-close-btn')?.addEventListener('click', closeAdminSettingsModal);
document.getElementById('asm-save-profile-btn')?.addEventListener('click', adminSmSaveProfile);
document.getElementById('asm-logout-all-btn')?.addEventListener('click', adminLogoutAll);
document.getElementById('asm-change-pass-btn')?.addEventListener('click', adminSmChangePassword);
document.getElementById('sp-widget-close-btn')?.addEventListener('click', closeSupportPopup);
document.getElementById('sp-startconv-btn')?.addEventListener('click', spStartConversation);
document.getElementById('spCloseTicketBtn')?.addEventListener('click', spCloseTicket);
document.getElementById('sp-widget-send-btn')?.addEventListener('click', spSendReply);
document.getElementById('newsBackBtn')?.addEventListener('click', () => closeNewsPost());
document.getElementById('nc-close-btn')?.addEventListener('click', closeNewsCenter);
document.getElementById('nc-new-post-btn')?.addEventListener('click', openNewsAdminForm);
document.getElementById('nc-clear-img-btn')?.addEventListener('click', clearNewsImage);
document.getElementById('nc-publish-btn')?.addEventListener('click', submitNewsPost);
document.getElementById('nc-cancel-btn')?.addEventListener('click', closeNewsAdminForm);
document.getElementById('admin-notif-subscription')?.addEventListener('change', function() { adminSaveNotif(this); });
document.getElementById('spReplyInput')?.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); spSendReply(); }
});
document.getElementById('newsSearchInput')?.addEventListener('input', function() { filterNews(this.value); });
document.getElementById('naImage')?.addEventListener('change', function() { previewNewsImage(this); });

function toggleAdminSidebar() {
    const collapsed = document.cookie.split(';').find(c => c.trim().startsWith('adminSidebarCollapsed='))?.split('=')[1]?.trim() === 'true';
    const newVal = !collapsed;
    document.cookie = 'adminSidebarCollapsed=' + newVal + ';path=/;max-age=31536000';
    window.location.reload();
}
function toggleAdminMenu(e) {
    e.stopPropagation();
    document.getElementById('adminMenuPopup').classList.toggle('admin-menu-popup-open');
}
document.addEventListener('click', e => {
    const btn = document.getElementById('adminMenuBtn');
    const popup = document.getElementById('adminMenuPopup');
    if (popup && btn && !btn.contains(e.target) && !popup.contains(e.target)) {
        popup.classList.remove('admin-menu-popup-open');
    }
});

const ADMIN_S_TABS = ['general','account','privacy'];
function openAdminSettingsModal() {
    document.getElementById('adminSettingsModal').classList.add('asm-modal-open');
    showAdminSTab('general');
}
function closeAdminSettingsModal() {
    document.getElementById('adminSettingsModal').classList.remove('asm-modal-open');
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
        c.classList.toggle('asm-tab-panel-open', t === tab);
        b.classList.toggle('asm-tab-btn-active', t === tab);
    });
}
async function adminSaveNotif(cb) {
    const track = document.getElementById('admin-notif-subscription-track');
    track.classList.toggle('active', cb.checked);
    cb.nextElementSibling.nextElementSibling.classList.toggle('active', cb.checked);
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
    msg.textContent = d.message;
    msg.classList.toggle('asm-msg-success', d.success);
    msg.classList.toggle('asm-msg-error', !d.success);
    msg.classList.add('asm-msg-open');
    setTimeout(()=>msg.classList.remove('asm-msg-open'), 3000);
}
async function adminSmChangePassword() {
    const cur = document.getElementById('admin-sm-curPass').value;
    const np = document.getElementById('admin-sm-newPass').value;
    const cp = document.getElementById('admin-sm-confPass').value;
    const msg = document.getElementById('admin-sm-passMsg');
    if (np!==cp) {
        msg.textContent='Passwords do not match'; msg.classList.remove('asm-msg-success'); msg.classList.add('asm-msg-error', 'asm-msg-open');
        return;
    }
    if (np.length<6) {
        msg.textContent='Password too short'; msg.classList.remove('asm-msg-success'); msg.classList.add('asm-msg-error', 'asm-msg-open');
        return;
    }
    const fd = new FormData();
    fd.append('current_password',cur); fd.append('new_password',np);
    const d = await (await fetch('/settings/password',{method:'POST',body:fd})).json();
    msg.textContent = d.message;
    msg.classList.toggle('asm-msg-success', d.success);
    msg.classList.toggle('asm-msg-error', !d.success);
    msg.classList.add('asm-msg-open');
    if (d.success) { document.getElementById('admin-sm-curPass').value=''; document.getElementById('admin-sm-newPass').value=''; document.getElementById('admin-sm-confPass').value=''; }
    setTimeout(()=>msg.classList.remove('asm-msg-open'), 3000);
}

// SUPPORT CENTER
supportCurrentTicketId = null;
let spPendingUserId = null;
let spPendingUserEmail = null;

function openSupportPopup() {
    const sidebar = document.getElementById('adminSidebar');
    const w = sidebar ? sidebar.offsetWidth : 56;
    const popup = document.getElementById('adminSupportPopup');
    popup.style.setProperty('--sp-left', w + 'px');
    popup.classList.add('sp-popup-open');
    document.getElementById('spStartConv').classList.remove('sp-startconv-open');
    document.getElementById('spEmpty').classList.add('sp-empty-open');
    document.getElementById('spChat').classList.remove('sp-chat-open');
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
    popup.style.setProperty('--sp-left', w + 'px');
    popup.classList.add('sp-popup-open');

    const tickets = await (await fetch('/admin/support/tickets')).json();
    await spLoadTickets(tickets);
    const match = tickets.find(t => t.email === email);
    if (match) {
        spOpenTicket(match.id);
    } else {
        document.getElementById('spEmpty').classList.remove('sp-empty-open');
        document.getElementById('spChat').classList.remove('sp-chat-open');
        document.getElementById('spStartConv').classList.add('sp-startconv-open');
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
        document.getElementById('spStartConv').classList.remove('sp-startconv-open');
        await spLoadTickets();
        spOpenTicket(d.ticket_id);
    }
}
function closeSupportPopup() {
    document.getElementById('adminSupportPopup').classList.remove('sp-popup-open');
    supportCurrentTicketId = null;
}
async function spLoadTickets(preFetched) {
    const el = document.getElementById('spTicketList');
    if (!el) return;
    el.innerHTML = '<div class="sp-list-loading"><i class="fa-solid fa-spinner fa-spin"></i></div>';
    try {
        const tickets = preFetched || await (await fetch('/admin/support/tickets')).json();
        if (!tickets.length) {
            el.innerHTML = '<div class="sp-list-empty"><i class="fa-solid fa-inbox sp-list-empty-icon"></i><p class="sp-list-empty-text">No inquiries</p></div>';
            return;
        }
        const typeMap = {
            bug: {label:'🐛 Проблем', cls:'sp-card-type-bug'},
            suggestion: {label:'💡 Предложение', cls:'sp-card-type-suggestion'},
            question: {label:'❓ Въпрос', cls:'sp-card-type-question'}
        };
        const statusMap = {
            open: {label:'Отворен', cls:'sp-card-status-open'},
            in_progress: {label:'В процес', cls:'sp-card-status-progress'},
            closed: {label:'Затворен', cls:'sp-card-status-closed'}
        };
        el.innerHTML = tickets.map(t => {
            const tc = typeMap[t.type] || typeMap.question;
            const sc = statusMap[t.status] || statusMap.open;
            const statusBorderCls = t.status === 'open' ? 'sp-card-border-open' : t.status === 'in_progress' ? 'sp-card-border-progress' : 'sp-card-border-closed';
            const unreadCls = t.unread > 0 ? 'sp-card-unread' : '';
            return '<div class="sp-card ' + statusBorderCls + ' ' + unreadCls + '" data-ticketid="' + t.id + '" id="spCard_' + t.id + '">' +
                '<p class="sp-card-email">' + spEsc(t.email) + '</p>' +
                (t.name ? '<p class="sp-card-name">' + spEsc(t.name) + '</p>' : '<div class="sp-card-name-empty"></div>') +
                '<div class="sp-card-footer">' +
                '<span class="sp-card-type-badge ' + tc.cls + '">' + tc.label + '</span>' +
                '<span class="sp-card-status ' + sc.cls + '">● ' + sc.label + '</span>' +
                '</div></div>';
        }).join('');
        el.querySelectorAll('.sp-card').forEach(card => {
            card.addEventListener('click', () => spOpenTicket(card.dataset.ticketid));
        });
    } catch(e) {
        el.innerHTML = '<div class="sp-list-error">Error</div>';
    }
}
async function spOpenTicket(id) {
    supportCurrentTicketId = id;
    document.querySelectorAll('[id^="spCard_"]').forEach(el => el.classList.remove('sp-card-selected'));
    const card = document.getElementById('spCard_' + id);
    if (card) card.classList.add('sp-card-selected');
    document.getElementById('spStartConv').classList.remove('sp-startconv-open');
    document.getElementById('spEmpty').classList.remove('sp-empty-open');
    document.getElementById('spChat').classList.add('sp-chat-open');
    await spLoadMessages(id);
    // Обновяваме badge веднага
    refreshSupportBadge();
}


async function spLoadMessages(id) {
    const el = document.getElementById('spMessages');
    el.innerHTML = '<div class="sp-msgs-loading"><i class="fa-solid fa-spinner fa-spin"></i></div>';
    const data = await (await fetch('/admin/support/' + id + '/messages')).json();
    const typeLabels = {bug:'🐛 Проблем', suggestion:'💡 Предложение', question:'❓ Въпрос'};
    const statusLabels = {open:'Отворен', in_progress:'В процес', closed:'Затворен'};
    document.getElementById('spChatEmail').textContent = data.user.email;
    document.getElementById('spChatMeta').textContent = (data.user.name||'') + ' · ' + (typeLabels[data.ticket.type]||'') + ' · ' + (statusLabels[data.ticket.status]||'');
    document.getElementById('spCloseTicketBtn').classList.toggle('hidden', data.ticket.status === 'closed');
    el.innerHTML = data.messages.map(m =>
        '<div class="sp-msg-row ' + (m.sender==='admin' ? 'sp-msg-row-admin' : 'sp-msg-row-user') + '">' +
        '<div class="sp-msg-bubble ' + (m.sender==='admin' ? 'sp-msg-bubble-admin' : 'sp-msg-bubble-user') + '">' +
        '<p class="sp-msg-body">' + spEsc(m.body) + '</p>' +
        '<p class="sp-msg-meta">' + (m.sender==='admin'?'Вие':spEsc(data.user.name||'User')) + ' · ' + m.created_at + '</p>' +
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
        document.getElementById('spCloseTicketBtn').classList.add('hidden');
        await spLoadMessages(supportCurrentTicketId);
        await spLoadTickets();
        refreshSupportBadge();
    }
}
function spEsc(s) {
    return String(s||'').replace(/&/g,'&amp;').replace(/\x3c/g,'&lt;').replace(/\x3e/g,'&gt;');
}

window.addEventListener('pageshow', function() {
    document.getElementById('adminSettingsModal').classList.remove('asm-modal-open');
    document.getElementById('adminMenuPopup').classList.remove('admin-menu-popup-open');
    document.getElementById('adminSupportPopup').classList.remove('sp-popup-open');
    supportCurrentTicketId = null;
});
