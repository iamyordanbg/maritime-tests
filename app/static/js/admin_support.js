// app/static/js/admin_support.js
// Admin Support Center — извлечена от app/templates/admin/support.html (Правило 1+2).
// Очаква window.SUPPORT_DATA = {filterUserId, filterUserEmail, hasFilterUser, firstTicketId}

let currentTicketId = null;

// Пускаме auto-open по ДВА начина - веднага при парсване на скрипта (не
// чака никакво browser събитие изобщо, най-надеждно) И на pageshow (за
// bfcache връщане назад/напред). openSupportPopup/openTicket са function
// декларации по-долу в СЪЩИЯ файл - hoisted, достъпни са тук независимо
// от реда на кода.
function runSupportAutoOpen() {
    openSupportPopup();
    // Ако сме дошли от 'Message in Support Chat' за конкретен потребител:
    // ако вече има негов ticket - отваряме го директно; ако няма НИКАКЪВ -
    // показваме поле за стартиране на нов разговор.
    if (window.SUPPORT_DATA.hasFilterUser) {
        if (window.SUPPORT_DATA.firstTicketId) {
            openTicket(window.SUPPORT_DATA.firstTicketId);
        } else {
            showStartConversationBox();
        }
    }
}
runSupportAutoOpen();
window.addEventListener('pageshow', runSupportAutoOpen);


function showStartConversationBox() {
    const main = document.getElementById('ticketMainArea');
    if (!main) return;
    main.innerHTML = `
        <div style="max-width:420px;margin:60px auto;text-align:center">
            <i class="fa-solid fa-comment-dots" style="font-size:32px;color:#0891b2;margin-bottom:14px;display:block"></i>
            <p style="color:#111827;font-size:13px;margin-bottom:4px">No conversation yet with</p>
            <p style="color:#0891b2;font-size:13px;font-weight:700;margin-bottom:18px">${window.SUPPORT_DATA.filterUserEmail}</p>
            <textarea id="startConvBody" rows="3" placeholder="Write the first message…"
                style="width:100%;background:#f9fafb;border:1px solid #d1d5db;border-radius:8px;padding:10px;color:#111827;font-size:12px;resize:none;margin-bottom:10px"></textarea>
            <button onclick="startConversation()" style="background:#4CC9F0;color:#0B132B;border:none;border-radius:8px;padding:9px 20px;font-size:12px;font-weight:700;cursor:pointer">
                Start conversation
            </button>
        </div>`;
}

async function startConversation() {
    const body = document.getElementById('startConvBody').value.trim();
    if (!body) return;
    const res = await fetch(`/admin/support/start/${window.SUPPORT_DATA.filterUserId}`, {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({body})
    });
    const d = await res.json();
    if (d.success) {
        window.location.reload();
    }
}

function openSupportPopup() {
    document.getElementById('supportPopup').style.display = 'flex';
}

function closeSupportPopup() {
    document.getElementById('supportPopup').style.display = 'none';
    window.history.back();
}

async function openTicket(id) {
    currentTicketId = id;

    // Highlight
    document.querySelectorAll('[id^="tcard_"]').forEach(el => {
        el.style.background = 'transparent';
        el.style.borderLeftColor = el.style.borderLeftColor;
    });
    const active = document.getElementById('tcard_' + id);
    if (active) active.style.background = 'rgba(76,201,240,0.08)';

    document.getElementById('chatEmpty').style.display = 'none';
    const pane = document.getElementById('chatPane');
    pane.style.display = 'flex';
    pane.style.flexDirection = 'column';
    pane.style.flex = '1';

    await loadMessages(id);
}

async function loadMessages(id) {
    const el = document.getElementById('chatMessages');
    el.innerHTML = '<div style="text-align:center;padding:20px;color:#64748b"><i class="fa-solid fa-spinner fa-spin"></i></div>';

    const data = await (await fetch('/admin/support/' + id + '/messages')).json();

    const typeLabels = {bug:'🐛 Проблем', suggestion:'💡 Предложение', question:'❓ Въпрос'};
    const statusLabels = {open:'Отворен', in_progress:'В процес', closed:'Затворен'};

    document.getElementById('chatEmail').textContent = data.user.email;
    document.getElementById('chatMeta').textContent =
        (data.user.name || '') + ' · ' + (typeLabels[data.ticket.type] || '') + ' · ' + (statusLabels[data.ticket.status] || '');

    const closeBtn = document.getElementById('closeTicketBtn');
    closeBtn.style.display = data.ticket.status === 'closed' ? 'none' : 'block';

    el.innerHTML = data.messages.map(m => `
        <div style="display:flex;${m.sender==='admin'?'justify-content:flex-end':'justify-content:flex-start'}">
            <div style="max-width:70%;padding:10px 14px;line-height:1.5;
                border-radius:${m.sender==='admin'?'16px 16px 4px 16px':'16px 16px 16px 4px'};
                background:${m.sender==='admin'?'#4CC9F0':'#f3f4f6'};
                color:${m.sender==='admin'?'#0B132B':'#111827'}">
                <p style="font-size:13px;margin:0 0 4px">${escHtml(m.body)}</p>
                <p style="font-size:10px;margin:0;opacity:0.6;text-align:right">
                    ${m.sender==='admin'?'Вие':escHtml(data.user.name||'User')} · ${m.created_at}
                </p>
            </div>
        </div>
    `).join('');
    el.scrollTop = el.scrollHeight;
}

async function sendReply() {
    const body = document.getElementById('replyInput').value.trim();
    if (!body || !currentTicketId) return;
    const fd = new FormData();
    fd.append('body', body);
    const d = await (await fetch('/admin/support/' + currentTicketId + '/reply', {method:'POST', body:fd})).json();
    if (d.success) {
        document.getElementById('replyInput').value = '';
        await loadMessages(currentTicketId);
    }
}

async function closeCurrentTicket() {
    if (!currentTicketId) return;

    const d = await (await fetch('/admin/support/' + currentTicketId + '/close', {method:'POST'})).json();
    if (d.success) {
        document.getElementById('closeTicketBtn').style.display = 'none';
        await loadMessages(currentTicketId);
    }
}

function escHtml(s) {
    return String(s).replace(/&/g,'&amp;').replace(/\x3c/g,'&lt;').replace(/\x3e/g,'&gt;');
}
