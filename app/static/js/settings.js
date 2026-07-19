// app/static/js/settings.js
// Логика за страницата с настройки на профила (settings.html).
// Extracted от inline <script> блок — Правило 1 на NEXT_SESSION_PROMPT.md.

// Theme switcher (sidebar тема — cookie-базирана, различна от Reading Settings)
function setTheme(theme) {
    document.cookie = 'theme=' + theme + ';path=/;max-age=31536000';
    const btns = {
        dark: document.getElementById('themeDark'),
        light: document.getElementById('themeLight'),
        system: document.getElementById('themeSystem')
    };
    Object.entries(btns).forEach(([k, btn]) => {
        if (!btn) return;
        if (k === theme) {
            btn.style.background = '#635BFF';
            btn.style.color = '#fff';
        } else {
            btn.style.background = 'transparent';
            btn.style.color = 'rgba(232,237,242,0.6)';
        }
    });
}

// Apply saved theme on load
(function() {
    const t = document.cookie.split(';').find(c => c.trim().startsWith('theme='))?.split('=')[1]?.trim() || 'dark';
    setTheme(t);
})();

// Save profile
async function saveProfile() {
    const rank = document.getElementById('rankInput').value;
    const company = document.getElementById('companyInput').value;
    const msg = document.getElementById('profileMsg');
    const fd = new FormData();
    fd.append('rank', rank);
    fd.append('company', company);
    const r = await fetch('/settings/profile', { method: 'POST', body: fd });
    const d = await r.json();
    msg.textContent = d.message;
    msg.style.color = d.success ? '#06D6A0' : '#ef4444';
    msg.style.display = 'block';
    setTimeout(() => msg.style.display = 'none', 3000);
}

function openDeleteConfirm() {
    document.getElementById('deleteOverlay').style.display = 'flex';
}
function closeDeleteConfirm() {
    document.getElementById('deleteOverlay').style.display = 'none';
}
function toggleGoldCard(id) {
    const el = document.getElementById('goldcard-' + id);
    const chev = document.getElementById('chev-' + id);
    if (!el) return;
    const open = el.style.display === 'block';
    el.style.display = open ? 'none' : 'block';
    if (chev) chev.style.transform = open ? 'rotate(0deg)' : 'rotate(180deg)';
}
async function confirmDelete() {
    const btn = document.getElementById('deleteBtn');
    btn.disabled = true;
    btn.textContent = '...';
    const r = await fetch('/settings/delete-account', { method: 'POST' });
    const d = await r.json();
    if (d.success) {
        window.location.href = '/';
    } else {
        btn.disabled = false;
        btn.textContent = 'Изтрий';
        alert(d.message || 'Грешка');
    }
}

// Change password
async function changePassword() {
    const cur = document.getElementById('curPass').value;
    const np = document.getElementById('newPass').value;
    const cp = document.getElementById('confPass').value;
    const msg = document.getElementById('passMsg');
    if (np !== cp) { msg.textContent = 'Паролите не съвпадат'; msg.style.color = '#ef4444'; msg.style.display = 'block'; return; }
    if (np.length < 6) { msg.textContent = 'Паролата е прекалено кратка'; msg.style.color = '#ef4444'; msg.style.display = 'block'; return; }
    const fd = new FormData();
    fd.append('current_password', cur);
    fd.append('new_password', np);
    const r = await fetch('/settings/password', { method: 'POST', body: fd });
    const d = await r.json();
    msg.textContent = d.message;
    msg.style.color = d.success ? '#06D6A0' : '#ef4444';
    msg.style.display = 'block';
    if (d.success) {
        document.getElementById('curPass').value = '';
        document.getElementById('newPass').value = '';
        document.getElementById('confPass').value = '';
    }
    setTimeout(() => msg.style.display = 'none', 3000);
}
