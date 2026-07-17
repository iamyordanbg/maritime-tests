// app/static/js/admin_support.js
// Admin Support Center — извлечена от app/templates/admin/support.html (Правило 1+2).
// Очаква window.SUPPORT_DATA = {filterUserId, filterUserEmail, hasFilterUser, firstTicketId}

let currentTicketId = null;

// ---------- Event wiring (заменя премахнатите onclick/onmouseover/onfocus) ----------
document.getElementById('sp-open-btn')?.addEventListener('click', openSupportPopup);
document.getElementById('sp-close-btn')?.addEventListener('click', closeSupportPopup);
document.getElementById('closeTicketBtn')?.addEventListener('click', closeCurrentTicket);
document.getElementById('sp-send-btn')?.addEventListener('click', sendReply);
document.getElementById('replyInput')?.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendReply(); }
});
document.getElementById('sp-list-panel')?.addEventListener('click', function(e) {
    const card = e.target.closest('.sp-tcard');
    if (card) openTicket(card.dataset.ticketid);
});

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
        <div class="sp-startconv-box">
            <i class="fa-solid fa-comment-dots sp-startconv-icon"></i>
            <p class="sp-startconv-label">No conversation yet with</p>
            <p class="sp-startconv-email">${window.SUPPORT_DATA.filterUserEmail}</p>
            <textarea id="startConvBody" rows="3" placeholder="Write the first message…" class="sp-startconv-textarea"></textarea>
            <button id="sp-startconv-btn" class="sp-startconv-btn">
                Start conversation
            </button>
        </div>`;
    document.getElementById('sp-startconv-btn').addEventListener('click', startConversation);
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
    document.getElementById('supportPopup').classList.add('sp-popup-open');
}

function closeSupportPopup() {
    document.getElementById('supportPopup').classList.remove('sp-popup-open');
    window.history.back();
}

async function openTicket(id) {
    id = parseInt(id, 10);
    currentTicketId = id;

    // Highlight - селектираната карта получава клас, CSS :hover:not(.selected)
    // се грижи за hover ефекта на останалите автоматично, без нужда от JS.
    document.querySelectorAll('.sp-tcard').forEach(el => {
        el.classList.remove('sp-tcard-selected');
    });
    const active = document.getElementById('tcard_' + id);
    if (active) active.classList.add('sp-tcard-selected');

    document.getElementById('chatEmpty').classList.add('hidden');
    document.getElementById('chatPane').classList.add('sp-chat-pane-open');

    await loadMessages(id);
}

async function loadMessages(id) {
    const el = document.getElementById('chatMessages');
    el.innerHTML = '<div class="sp-loading"><i class="fa-solid fa-spinner fa-spin"></i></div>';

    const data = await (await fetch('/admin/support/' + id + '/messages')).json();

    const typeLabels = {bug:'🐛 Проблем', suggestion:'💡 Предложение', question:'❓ Въпрос'};
    const statusLabels = {open:'Отворен', in_progress:'В процес', closed:'Затворен'};

    document.getElementById('chatEmail').textContent = data.user.email;
    document.getElementById('chatMeta').textContent =
        (data.user.name || '') + ' · ' + (typeLabels[data.ticket.type] || '') + ' · ' + (statusLabels[data.ticket.status] || '');

    const closeBtn = document.getElementById('closeTicketBtn');
    closeBtn.classList.toggle('hidden', data.ticket.status === 'closed');

    el.innerHTML = data.messages.map(m => `
        <div class="sp-msg-row ${m.sender==='admin' ? 'sp-msg-row-admin' : 'sp-msg-row-user'}">
            <div class="sp-msg-bubble ${m.sender==='admin' ? 'sp-msg-bubble-admin' : 'sp-msg-bubble-user'}">
                <p class="sp-msg-body">${escHtml(m.body)}</p>
                <p class="sp-msg-meta">
                    ${m.sender==='admin' ? 'Вие' : escHtml(data.user.name || 'User')} · ${m.created_at}
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
        document.getElementById('closeTicketBtn').classList.add('hidden');
        await loadMessages(currentTicketId);
    }
}

function escHtml(s) {
    return String(s).replace(/&/g,'&amp;').replace(/\x3c/g,'&lt;').replace(/\x3e/g,'&gt;');
}
