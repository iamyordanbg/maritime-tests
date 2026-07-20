// app/static/js/sidebar.js
// Support center, news center и sidebar логика (обединен за минимални HTTP заявки).

// ── Support Center ──
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

// News Center → news_center.js (споделен модул, зареден отделно)

// ── Sidebar ──
// Sidebar / Settings modal логика - извлечена от app/templates/layouts/user_sidebar.html
let sActiveTab = 'general';
const S_TABS = ['general','account','privacy','billing','usage'];

function openDeleteConfirm(){
    document.getElementById('smDeleteOverlay').style.display='flex';
}
function closeDeleteConfirm(){
    document.getElementById('smDeleteOverlay').style.display='none';
}
async function confirmDelete(){
    const btn=document.getElementById('smDeleteBtn');
    btn.disabled=true; btn.textContent='...';
    const r=await fetch('/settings/delete-account',{method:'POST'});
    const d=await r.json();
    if(d.success){ window.location.href='/'; }
    else{ btn.disabled=false; btn.textContent='Изтрий'; alert(d.message||'Грешка'); }
}

function openSettingsModal() {
    document.getElementById('settingsModal').style.display = 'block';
    showSTab('general');
    _billingLoaded = false;
    _usageLoaded = false;

    // Current password - динамично (блокира autofill)
    const container = document.getElementById('sm-curPass-container');
    if (container) {
        container.innerHTML = '';
        const inp = document.createElement('input');
        inp.type = 'text'; // НЕ password - браузърът не предлага autofill
        inp.id = 'sm-curPass';
        inp.placeholder = '••••••••';
        inp.autocomplete = 'off';
        inp.setAttribute('data-visible', 'false');
        inp.style.webkitTextSecurity = 'disc'; // CSS маскиране
        inp.style.width = '100%';
        inp.style.border = '1.5px solid #e5e7eb';
        inp.style.borderRadius = '7px';
        inp.style.padding = '6px 36px 6px 10px';
        inp.style.fontSize = '13px';
        inp.style.color = '#111827';
        inp.style.outline = 'none';
        inp.style.boxSizing = 'border-box';
        inp.style.background = '#fafafa';
        inp.style.transition = 'all 0.2s';
        inp.addEventListener('focus', function() {
            this.style.borderColor = '#6366f1';
            this.style.background = '#fff';
        });
        inp.addEventListener('blur', function() {
            this.style.borderColor = '#e5e7eb';
            this.style.background = '#fafafa';
            checkCurPass(this);
        });
        container.appendChild(inp);
    }

    // Изчистваме new и confirm
    ['sm-newPass','sm-confPass'].forEach(id => {
        const el = document.getElementById(id);
        if (el) { el.value = ''; el.style.webkitTextSecurity = 'disc'; el.setAttribute('data-visible','false'); }
    });

    // Скриваме съобщенията
    ['sm-curMsg','sm-matchMsg'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.style.visibility = 'hidden';
    });

    checkPassStrength('');
}


let currentTicketType = 'question';
let currentTicketId = null;

// Support center → support_center.js
// News center → news.js

function setSignalType(type) {
    currentSignalType = type;
    const styles = {
        bug: {bg:'#fef2f2',color:'#dc2626',border:'#fca5a5'},
        suggestion: {bg:'#eff6ff',color:'#2563eb',border:'#93c5fd'},
        question: {bg:'#f9fafb',color:'#374151',border:'#e5e7eb'}
    };
    ['bug','suggestion','question'].forEach(t => {
        const btn = document.getElementById('stype-' + t);
        if (!btn) return;
        const s = styles[t];
        btn.style.background = s.bg;
        btn.style.color = s.color;
        btn.style.borderColor = s.border;
        btn.style.boxShadow = (t === type) ? '0 0 0 2px ' + s.border : 'none';
        btn.style.transform = (t === type) ? 'scale(1.05)' : 'scale(1)';
    });
}

async function sendContact() {
    const msg = document.getElementById('contactMessage');
    const msgEl = document.getElementById('contactMsg');
    if (!msg || !msg.value.trim()) {
        msgEl.textContent = 'Моля напишете съобщение.';
        msgEl.style.color = '#dc2626';
        msgEl.style.display = 'block';
        return;
    }
    // Защита - само текст, без HTML/скриптове
    const safeMsg = msg.value.replace(/\x3c[^\x3e]*\x3e/g, '').trim();
    const fd = new FormData();
    fd.append('message', safeMsg);
    fd.append('type', currentSignalType);
    try {
        const d = await (await fetch('/signal', {method:'POST', body:fd})).json();
        if (d.success) {
            msgEl.textContent = '✓ Съобщението е изпратено!';
            msgEl.style.color = '#059669';
            msg.value = '';
            document.getElementById('contactCount').textContent = '0/500';
        } else {
            msgEl.textContent = 'Грешка. Опитайте отново.';
            msgEl.style.color = '#dc2626';
        }
    } catch(e) {
        msgEl.textContent = 'Грешка. Опитайте отново.';
        msgEl.style.color = '#dc2626';
    }
    msgEl.style.display = 'block';
    setTimeout(() => msgEl.style.display = 'none', 4000);
}

function closeSettingsModal() {
    document.getElementById('settingsModal').style.display = 'none';
    if (_usageRefreshTimer) { clearInterval(_usageRefreshTimer); _usageRefreshTimer = null; }
}

document.addEventListener('keydown', e => { if(e.key==='Escape') closeSettingsModal(); });

function showSTab(tab) {
    const af = document.getElementById('accountFooter');
    if (af) af.style.display = tab==='account' ? 'flex' : 'none';
    S_TABS.forEach(t => {
        const c = document.getElementById('stab-content-'+t);
        const b = document.getElementById('stab-'+t);
        if (!c||!b) return;
        if (t===tab) {
            c.classList.remove('hidden');
            b.classList.add('active');
        } else {
            c.classList.add('hidden');
            b.classList.remove('active');
        }
    });
    if (tab === 'billing') loadBillingCodes();
    if (tab === 'usage') loadUsageCards();
}

let _usageLoaded = false;
let _usageRefreshTimer = null;

async function loadUsageCards() {
    const el = document.getElementById('sm-usage-cards');
    if (!el) return;
    if (_usageLoaded) return;
    _usageLoaded = true;
    await _fetchAndRenderUsage();
    _startUsageUtcClock();

    // Опресняваме на всеки 6 часа, докато модалът е отворен — достатъчно
    // гранулярно да се вижда движение дори при 1-дневен тестов план.
    if (_usageRefreshTimer) clearInterval(_usageRefreshTimer);
    _usageRefreshTimer = setInterval(_fetchAndRenderUsage, 60 * 60 * 1000);
}

let _usageClockTimer = null;
function _startUsageUtcClock() {
    const el = document.getElementById('smUsageUtcClock');
    if (!el) return;
    if (_usageClockTimer) clearInterval(_usageClockTimer);
    const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    const tick = () => {
        const now = new Date();
        const pad = n => String(n).padStart(2, '0');
        const dateStr = `${pad(now.getUTCDate())} ${months[now.getUTCMonth()]} ${now.getUTCFullYear()}`;
        el.textContent = `${dateStr} · UTC ${pad(now.getUTCHours())}:${pad(now.getUTCMinutes())}:${pad(now.getUTCSeconds())}`;
    };
    tick();
    _usageClockTimer = setInterval(tick, 1000);
}

async function _fetchAndRenderUsage() {
    const el = document.getElementById('sm-usage-cards');
    if (!el) return;
    el.innerHTML = '<p style="font-size:12px;color:#9ca3af">Loading…</p>';
    try {
        const r = await fetch('/api/my-usage');
        const data = await r.json();
        const cards = data.cards || [];

        if (cards.length === 0) {
            el.innerHTML = `<div style="text-align:center;padding:24px 0">
                <p style="font-size:13px;color:#6b7280;margin-bottom:12px">You are on the <strong>Free</strong> plan.</p>
                <a href="#" onclick="closePlansModal();openPlansModal();return false;"
                   style="background:#111827;color:#fff;border-radius:8px;padding:8px 20px;font-size:13px;font-weight:600;text-decoration:none">
                    Upgrade
                </a>
            </div>`;
            return;
        }

        let html = '';
        cards.forEach((c, i) => {
            const pctColor = c.pct_remaining > 50 ? '#10b981' : (c.pct_remaining > 20 ? '#f59e0b' : '#ef4444');
            const testLine = c.test_names.length
                ? `<div style="font-size:12px;color:#374151;margin-top:2px"><i class="fa-solid fa-file-lines" style="font-size:9px;color:#9ca3af;margin-right:4px"></i>${c.test_names.join(', ')}</div>`
                : '';
            html += `<div style="${i > 0 ? 'margin-top:20px;padding-top:20px;border-top:1px solid #f3f4f6' : ''}">`;
            html += `<div style="margin-bottom:8px">
                        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:2px">
                            <span style="font-size:13px;font-weight:600;color:#111827">${c.plan} Plan
                                <span style="font-size:11px;font-weight:600;color:#9ca3af;margin-left:6px">${c.subscription_code || ''}</span>
                            </span>
                            <span style="font-size:12px;color:#6b7280">${c.pct_remaining}% remaining</span>
                        </div>
                        ${testLine}
                     </div>`;
            html += `<div style="height:8px;background:#f3f4f6;border-radius:99px;overflow:hidden;margin-bottom:12px">
                        <div style="height:100%;width:${c.pct_remaining}%;background:${pctColor};border-radius:99px"></div>
                     </div>`;
            html += `<div style="display:flex;flex-direction:column;gap:8px">
                        <div style="display:flex;justify-content:space-between;align-items:center">
                            <span style="font-size:13px;color:#6b7280">Plan activated</span>
                            <span style="font-size:13px;font-weight:500;color:#111827">${c.activated_at}</span>
                        </div>
                        <div style="display:flex;justify-content:space-between;align-items:center">
                            <span style="font-size:13px;color:#6b7280">Plan expires</span>
                            <span style="font-size:13px;font-weight:500;color:#111827">${c.expires_at}</span>
                        </div>
                        <div style="display:flex;justify-content:space-between;align-items:center">
                            <span style="font-size:13px;color:#6b7280">Days remaining</span>
                            <span style="font-size:13px;font-weight:700;color:${pctColor}">${c.days_remaining} days</span>
                        </div>
                        <div style="display:flex;justify-content:space-between;align-items:center">
                            <span style="font-size:13px;color:#6b7280">Tests remaining</span>
                            <span style="font-size:13px;font-weight:700;color:${pctColor}">${c.tests_remaining}/${c.quota}</span>
                        </div>
                     </div>`;
            html += `</div>`;
        });
        el.innerHTML = html;
    } catch (e) {
        el.innerHTML = '<p style="font-size:12px;color:#ef4444">Could not load usage data.</p>';
    }
}

let _billingLoaded = false;
async function loadBillingCodes() {
    const el = document.getElementById('sm-billing-codes');
    if (!el) return;
    if (_billingLoaded) return;
    _billingLoaded = true;

    el.innerHTML = '<p style="font-size:12px;color:#9ca3af">Loading purchases…</p>';
    try {
        const r = await fetch('/api/my-billing');
        const data = await r.json();
        const payments = data.payments || [];
        const activatedCodes = data.activated_codes || [];

        if (payments.length === 0 && activatedCodes.length === 0) {
            el.innerHTML = '';
            return;
        }

        let html = '';

        if (activatedCodes.length > 0) {
            html += '<div style="margin-bottom:18px">' +
                    '<p style="font-size:12px;font-weight:600;color:#6b7280;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:12px">Activated codes (paid by someone else)</p>';
            activatedCodes.forEach(a => {
                const isCustom = a.plan === 'Custom';
                html += `<div style="border:1px solid #e5e7eb;border-radius:10px;margin-bottom:8px;padding:12px 14px;background:#fafafa">`;
                html += `<div style="font-size:13px;font-weight:700;color:#111827;text-transform:capitalize">${isCustom ? '📋 ' : '🥇 '}${a.plan}</div>`;
                if (!isCustom) {
                    html += `<div style="font-size:11px;color:#9ca3af;margin-top:2px"><i class="fa-solid fa-envelope" style="font-size:9px;margin-right:4px"></i>Sent from: ${a.paid_by_email}</div>`;
                } else {
                    html += `<div style="font-size:11px;color:#9ca3af;margin-top:2px"><i class="fa-solid fa-user-shield" style="font-size:9px;margin-right:4px"></i>Issued by: ${a.paid_by_email}</div>`;
                    if (a.quota) html += `<div style="font-size:11px;color:#374151;margin-top:2px"><i class="fa-solid fa-list-check" style="font-size:9px;color:#9ca3af;margin-right:4px"></i>Quota: ${a.quota} tests</div>`;
                    if (a.days_remaining !== null && a.days_remaining !== undefined) html += `<div style="font-size:11px;color:#374151;margin-top:2px"><i class="fa-solid fa-calendar-days" style="font-size:9px;color:#9ca3af;margin-right:4px"></i>Days remaining: ${a.days_remaining}</div>`;
                    if (a.code) html += `<div style="font-size:11px;color:#9ca3af;margin-top:2px;font-family:monospace">${a.code}</div>`;
                }
                if (a.active_from && a.active_until) {
                    html += `<div style="font-size:10px;color:#6b7280;margin-top:3px"><i class="fa-solid fa-clock" style="font-size:9px;margin-right:4px"></i>Active: ${a.active_from} → ${a.active_until}</div>`;
                }
                html += `</div>`;
            });
            html += '</div>';
        }

        if (payments.length === 0) {
            el.innerHTML = html;
            return;
        }

        html += '<div style="border-top:1px solid #f3f4f6;margin:18px 0;padding-top:18px">' +
                    '<p style="font-size:12px;font-weight:600;color:#6b7280;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:12px">Purchase history</p>';

        payments.forEach(p => {
            const goldBadge = p.plan === 'gold'
                ? `<span style="font-size:10px;color:#9ca3af;font-weight:400"> · ${p.codes.length} codes</span>` : '';
            html += `<div style="border:1px solid #e5e7eb;border-radius:10px;margin-bottom:8px;overflow:hidden">`;
            html += `<div style="display:flex;align-items:center;justify-content:space-between;padding:12px 14px;background:#fafafa;${p.plan === 'gold' ? 'cursor:pointer' : ''}"` +
                    (p.plan === 'gold' ? ` onclick="toggleSmGold(${p.id})"` : '') + `>`;
            html += `<div><span style="font-size:13px;font-weight:700;color:#111827;text-transform:capitalize">${p.plan === 'gold' ? '🥇 ' : ''}${p.plan}</span>${goldBadge}` +
                    `<div style="font-size:11px;color:#9ca3af;margin-top:2px">${p.amount} € · ${p.paid_at}${p.promo_email_sent ? ' · ✓ codes emailed' : ''}</div>` +
                    (p.loaded_test ? `<div style="font-size:11px;color:#374151;margin-top:3px"><i class="fa-solid fa-file-lines" style="font-size:9px;color:#9ca3af;margin-right:4px"></i>${p.loaded_test}</div>` : '') +
                    (p.active_from && p.active_until ? `<div style="font-size:10px;color:#6b7280;margin-top:3px"><i class="fa-solid fa-clock" style="font-size:9px;margin-right:4px"></i>Active: ${p.active_from} → ${p.active_until}</div>` : '') +
                    (p.subscription_code ? `<div style="font-size:11px;color:#9ca3af;margin-top:2px;font-family:monospace">${p.subscription_code}</div>` : '') +
                    `</div>`;
            if (p.plan === 'gold') html += `<i class="fa-solid fa-chevron-down" id="sm-chev-${p.id}" style="color:#9ca3af;font-size:11px"></i>`;
            html += `</div>`;

            if (p.plan === 'gold') {
                html += `<div id="sm-goldbox-${p.id}" style="display:none;padding:10px 14px">`;
                p.codes.forEach((c, i) => {
                    let badge, label;
                    if (c.is_used) { badge = 'background:#e5e7eb;color:#6b7280'; label = 'USED'; }
                    else if (c.shared_to) { badge = 'background:#f0fdf4;color:#16a34a'; label = '✓ SENT'; }
                    else { badge = 'background:#fffbeb;color:#d97706'; label = 'AVAILABLE'; }
                    const sub = c.is_used ? `Activated by ${c.used_by}` : (c.shared_to ? `Sent to ${c.shared_to}` : 'Not shared yet');
                    const activePeriod = (c.is_used && c.active_from && c.active_until)
                        ? `<div style="font-size:9px;color:#6b7280;margin-top:2px"><i class="fa-solid fa-clock" style="font-size:8px;margin-right:3px"></i>${c.active_from} → ${c.active_until}</div>`
                        : (!c.is_used && c.activate_by)
                        ? `<div style="font-size:9px;color:#d97706;margin-top:2px"><i class="fa-solid fa-hourglass-half" style="font-size:8px;margin-right:3px"></i>Activate by ${c.activate_by}</div>`
                        : '';
                    html += `<div style="display:flex;align-items:center;justify-content:space-between;padding:8px 0;${i < p.codes.length-1 ? 'border-bottom:1px solid #f3f4f6' : ''}">`;
                    html += `<div><span style="font-family:monospace;font-size:12px;color:#92400e;letter-spacing:1px">${c.code}</span>` +
                            `<div style="font-size:10px;color:#9ca3af">${sub}</div>${activePeriod}</div>`;
                    html += `<div style="display:flex;align-items:center;gap:8px">`;
                    html += `<span style="font-size:9px;font-weight:700;padding:3px 8px;border-radius:999px;${badge}">${label}</span>`;
                    if (!c.is_used) html += `<a href="/promo/share?code=${c.code}" style="font-size:11px;font-weight:600;color:#635BFF;text-decoration:none">${c.shared_to ? 'Resend' : 'Share'} →</a>`;
                    html += `</div></div>`;
                });
                html += `</div>`;
            }
            html += `</div>`;
        });

        html += '</div>';
        el.innerHTML = html;
    } catch (e) {
        el.innerHTML = '<p style="font-size:12px;color:#ef4444">Could not load purchase history.</p>';
    }
}

function toggleSmGold(id) {
    const box = document.getElementById('sm-goldbox-' + id);
    const chev = document.getElementById('sm-chev-' + id);
    if (!box) return;
    const open = box.style.display === 'block';
    box.style.display = open ? 'none' : 'block';
    if (chev) chev.style.transform = open ? 'rotate(0deg)' : 'rotate(180deg)';
}

async function smSaveProfile() {
    const nick = document.getElementById('sm-nickInput').value;
    const firstname = document.getElementById('sm-firstnameInput') ? document.getElementById('sm-firstnameInput').value : '';
    const lastname = document.getElementById('sm-lastnameInput') ? document.getElementById('sm-lastnameInput').value : '';
    const fd = new FormData();
    fd.append('nick', nick);
    fd.append('firstname', firstname);
    fd.append('lastname', lastname);
    const msg = document.getElementById('sm-profileMsg');
    const d = await (await fetch('/settings/profile',{method:'POST',body:fd})).json();
    msg.textContent = d.message;
    msg.style.color = d.success ? '#059669' : '#dc2626';
    msg.style.display = 'block';
    setTimeout(()=>msg.style.display='none', 3000);
    // Обновяваме UI
    const sidebarNick = document.getElementById('sidebar-nick');
    if (sidebarNick) sidebarNick.textContent = nick || 'Sailor';
    const sidebarName = document.getElementById('sidebar-fullname');
    if (sidebarName) sidebarName.innerHTML = (firstname||'') + (firstname&&lastname?'<br>':'') + (lastname||'') || USER_FULL_NAME;
}

async function checkCurPass(input) {
    const val = input.value;
    const msg = document.getElementById('sm-curMsg');
    if (!val || !msg) return;
    const fd = new FormData();
    fd.append('current_password', val);
    try {
        const d = await (await fetch('/settings/check-password', {method:'POST', body:fd})).json();
        msg.textContent = d.valid ? '✓ Correct' : '✗ Incorrect password';
        msg.style.color = d.valid ? '#22c55e' : '#ef4444';
        msg.style.visibility = 'visible';
    } catch(e) {}
}

function togglePass(inputId, iconId) {
    const input = document.getElementById(inputId);
    const icon = document.getElementById(iconId);
    if (!input || !icon) return;
    const visible = input.getAttribute('data-visible') === 'true';
    input.style.webkitTextSecurity = visible ? 'disc' : 'none';
    input.setAttribute('data-visible', visible ? 'false' : 'true');
    icon.className = visible ? 'fa-regular fa-eye' : 'fa-regular fa-eye-slash';
    icon.style.fontSize = '13px';
}

function checkPassStrength(val) {
    const bars = ['bar1','bar2','bar3'].map(id => document.getElementById(id));
    if (!bars[0]) return;
    let score = 0;
    if (val.length > 0 && typeof zxcvbn !== 'undefined') {
        const z = zxcvbn(val).score;
        score = z < 2 ? 1 : z < 4 ? 2 : 3;
    }
    const colors = ['#EF4444','#F59E0B','#22C55E'];
    bars.forEach((b,i) => { if(b) b.style.background = val.length === 0 ? '#e5e7eb' : i < score ? colors[score-1] : '#e5e7eb'; });
    checkPassMatch();
}

function checkPassMatch() {
    const np = document.getElementById('sm-newPass');
    const cp = document.getElementById('sm-confPass');
    const msg = document.getElementById('sm-matchMsg');
    if (!np || !cp || !msg) return;
    if (cp.value.length === 0) { msg.style.visibility = 'hidden'; return; }
    if (np.value === cp.value) {
        msg.innerHTML = '<i class="fa-solid fa-circle-check" style="color:#22c55e"></i> <span style="color:#22c55e">Passwords match</span>';
    } else {
        msg.innerHTML = '<i class="fa-solid fa-circle-xmark" style="color:#ef4444"></i> <span style="color:#ef4444">Passwords do not match</span>';
    }
    msg.style.visibility = 'visible';
}

function openForgotFromSettings() {
    closeSettingsModal();
    const modal = document.getElementById('forgotModal');
    if (modal) { modal.style.display = 'flex'; }
    else { window.location.href = '/forgot-password'; }
}

async function smChangePassword() {
    const cur = document.getElementById('sm-curPass').value;
    const np  = document.getElementById('sm-newPass').value;
    const cp  = document.getElementById('sm-confPass').value;
    const msg = document.getElementById('sm-passMsg');
    if (np !== cp) { msg.textContent='Passwords do not match'; msg.style.color='#dc2626'; msg.style.display='block'; return; }
    if (np.length < 6) { msg.textContent='Password too short'; msg.style.color='#dc2626'; msg.style.display='block'; return; }
    const fd = new FormData();
    fd.append('current_password', cur);
    fd.append('new_password', np);
    const d = await (await fetch('/settings/password',{method:'POST',body:fd})).json();
    msg.textContent = d.message;
    msg.style.color = d.success ? '#059669' : '#dc2626';
    msg.style.display = 'block';
    if (d.success) {
        ['sm-curPass','sm-newPass','sm-confPass'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.value = '';
        });
    }
    setTimeout(()=>msg.style.display='none', 3000);
}

function saveTipsToggle(cb) {
    localStorage.setItem('mt_show_messages', cb.checked ? 'true' : 'false');
    document.getElementById('tips-track').style.background = cb.checked ? '#111827' : '#e5e7eb';
    document.getElementById('tips-thumb').style.transform = cb.checked ? 'translateX(18px)' : 'translateX(0)';
}

function smSetTheme(theme) {
    localStorage.setItem('mt_theme', theme);
    ['system','light','dark'].forEach(k => {
        const b = document.getElementById('sm-theme' + k.charAt(0).toUpperCase() + k.slice(1));
        if (!b) return;
        b.classList.toggle('active', k === theme);
    });
}

// Init
(function() {
    const v = localStorage.getItem('mt_show_messages') !== 'false';
    const cb = document.getElementById('tips-toggle');
    if (cb) {
        cb.checked = v;
        document.getElementById('tips-track').style.background = v ? '#111827' : '#e5e7eb';
        document.getElementById('tips-thumb').style.transform = v ? 'translateX(18px)' : 'translateX(0)';
    }
    smSetTheme(localStorage.getItem('mt_theme') || 'system');
})();

// bfcache fix - при връщане назад/напред браузърът може да покаже СТАРА
// "снимка" на цялата страница (вкл. sidebar-а с навигацията), взета от
// паметта, БЕЗ нова заявка към сървъра - затова нови промени (напр. нов
// nav линк) не се виждат, докато клиентът не натисне ръчно refresh.
// event.persisted === true означава точно такова възстановяване от bfcache
// -> насилваме пълен reload, за да е сигурно, че страницата е винаги
// актуална спрямо последния deploy, без клиентът да трябва да го прави сам.
window.addEventListener('pageshow', function(event) {
    closeSettingsModal();
    if (event.persisted) {
        window.location.reload();
    }
});

// trigger railway PR environment
