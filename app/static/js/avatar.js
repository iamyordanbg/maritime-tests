// app/static/js/avatar.js
// Settings > General > Avatar: choose, upload and remove the profile photo; updates every avatar on the page.
const AVATAR_MAX_BYTES = 5 * 1024 * 1024;

function avatarMsg(text, ok) {
    const el = document.getElementById('avatarMsg');
    if (!el) return;
    el.textContent = text;
    el.style.color = ok ? '#16a34a' : '#dc2626';
}

// version > 0: show the photo; 0: back to the initials (kept in data-initials)
function applyAvatar(version) {
    document.querySelectorAll('[data-avatar-slot]').forEach(slot => {
        slot.textContent = '';
        if (version > 0) {
            const img = document.createElement('img');
            img.className = 'avatar-img';
            img.alt = '';
            img.src = '/settings/avatar?v=' + version;
            slot.appendChild(img);
        } else {
            const span = document.createElement('span');
            span.className = slot.dataset.initialsClass || '';
            span.textContent = slot.dataset.initials || '';
            slot.appendChild(span);
        }
    });
    const rm = document.getElementById('avatarRemoveBtn');
    if (rm) rm.hidden = !(version > 0);
}

function pickAvatar() {
    const input = document.getElementById('avatarFile');
    if (input) input.click();
}

async function uploadAvatar(input) {
    const file = input.files && input.files[0];
    input.value = '';
    if (!file) return;
    if (file.size > AVATAR_MAX_BYTES) { avatarMsg('The photo is too large (max 5 MB).', false); return; }
    const fd = new FormData();
    fd.append('avatar', file);
    avatarMsg('Uploading...', true);
    try {
        const res = await fetch('/settings/avatar', { method: 'POST', body: fd });
        const data = await res.json();
        if (!res.ok || !data.success) { avatarMsg(data.message || 'Could not save the photo.', false); return; }
        applyAvatar(data.version);
        avatarMsg('Photo saved.', true);
    } catch (e) {
        avatarMsg('Could not save the photo. Please try again.', false);
    }
}

async function removeAvatar() {
    try {
        const res = await fetch('/settings/avatar/remove', { method: 'POST' });
        const data = await res.json();
        if (!res.ok || !data.success) throw new Error('remove failed');
        applyAvatar(0);
        avatarMsg('Photo removed.', true);
    } catch (e) {
        avatarMsg('Could not remove the photo. Please try again.', false);
    }
}
