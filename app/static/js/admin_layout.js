// app/static/js/admin_layout.js
// Admin Layout — извлечена от app/templates/layouts/admin_layout.html (Правило 1).

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

const ADMIN_S_TABS = ['general','account','privacy','billing','usage'];

function openAdminSettingsModal() {
    document.getElementById('adminSettingsModal').style.display = 'block';
    showAdminSTab('general');
}
function closeAdminSettingsModal() {
    document.getElementById('adminSettingsModal').style.display = 'none';
}
document.addEventListener('keydown', e => { if(e.key==='Escape') closeAdminSettingsModal(); });

function showAdminSTab(tab) {
    ADMIN_S_TABS.forEach(t => {
        const c = document.getElementById('admin-stab-content-'+t);
        const b = document.getElementById('admin-stab-'+t);
        if (!c||!b) return;
        if (t===tab) {
            c.style.display='block';
            b.style.background='#F3F4F6';
            b.style.color='#111827';
            b.style.fontWeight='600';

        } else {
            c.style.display='none';
            b.style.background='transparent';
            b.style.color='#374151';
            b.style.fontWeight='400';

        }
    });
}

async function adminSmSaveProfile() {
    const fd = new FormData();
    fd.append('rank', document.getElementById('admin-sm-rankInput').value);
    fd.append('company', document.getElementById('admin-sm-companyInput').value);
    const msg = document.getElementById('admin-sm-profileMsg');
    const d = await (await fetch('/settings/profile',{method:'POST',body:fd})).json();
    msg.textContent = d.message;
    msg.style.color = d.success ? '#059669' : '#dc2626';
    msg.style.display = 'block';
    setTimeout(()=>msg.style.display='none', 3000);
}

async function adminSmChangePassword() {
    const cur = document.getElementById('admin-sm-curPass').value;
    const np  = document.getElementById('admin-sm-newPass').value;
    const cp  = document.getElementById('admin-sm-confPass').value;
    const msg = document.getElementById('admin-sm-passMsg');
    if (np!==cp) { msg.textContent='Passwords do not match'; msg.style.color='#dc2626'; msg.style.display='block'; return; }
    if (np.length<6) { msg.textContent='Password too short'; msg.style.color='#dc2626'; msg.style.display='block'; return; }
    const fd = new FormData();
    fd.append('current_password',cur);
    fd.append('new_password',np);
    const d = await (await fetch('/settings/password',{method:'POST',body:fd})).json();
    msg.textContent = d.message;
    msg.style.color = d.success ? '#059669' : '#dc2626';
    msg.style.display = 'block';
    if (d.success) {
        document.getElementById('admin-sm-curPass').value='';
        document.getElementById('admin-sm-newPass').value='';
        document.getElementById('admin-sm-confPass').value='';
    }
    setTimeout(()=>msg.style.display='none', 3000);
}
