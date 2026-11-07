// app/static/js/notifications.js
// In-platform notifications: "X replied to your comment" on a news post. Separate from the Support Center.

function nfEscape(s) {
    return String(s == null ? '' : s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

// Dots: [data-notif-dot] = notifications only; [data-unread-any] = notifications or support messages (avatar, Account)
async function updateNotifBadge() {
    try {
        const d = await (await fetch('/notifications/unread')).json();
        window._notifUnread = d.count;
        document.querySelectorAll('[data-notif-dot]').forEach(el => el.classList.toggle('has-unread', d.count > 0));
        refreshAnyUnreadDots();
    } catch (e) {}
}

function refreshAnyUnreadDots() {
    const any = (window._notifUnread || 0) > 0 || (window._supportUnread || 0) > 0;
    document.querySelectorAll('[data-unread-any]').forEach(el => el.classList.toggle('has-unread', any));
}

async function openNotifications() {
    document.getElementById('notifModal').style.display = 'flex';
    document.body.style.overflow = 'hidden';
    await loadNotifications();
}

function closeNotifications() {
    document.getElementById('notifModal').style.display = 'none';
    document.body.style.overflow = '';
}

async function loadNotifications() {
    const el = document.getElementById('notifList');
    const data = await (await fetch('/notifications')).json();
    if (!data.items.length) { el.innerHTML = '<p class="nf-empty">No notifications yet</p>'; return; }
    el.innerHTML = data.items.map(n => `
        <button type="button" class="nf-item${n.is_read ? '' : ' is-unread'}" data-id="${n.id}" data-post="${n.post_id}" data-comment="${n.comment_id || 0}"
            data-on-click='[["openNotification","$num:id","$num:post","$num:comment"]]'>
            <span class="nf-item-head"><b>${nfEscape(n.actor)}</b> ${n.kind === 'reply' ? 'replied to your comment' : 'commented in a post you commented on'}</span>
            <span class="nf-item-body">${nfEscape(n.body)}</span>
            <span class="nf-item-post">${nfEscape(n.post_title)} · ${nfEscape(n.time_ago)}</span>
        </button>`).join('');
}

async function openNotification(id, postId, commentId) {
    fetch('/notifications/' + id + '/read', {method: 'POST'}).then(updateNotifBadge);
    closeNotifications();
    await openNewsCenter();
    openNewsPost(postId, commentId || undefined);
}

async function markAllNotificationsRead() {
    await fetch('/notifications/read', {method: 'POST'});
    await loadNotifications();
    updateNotifBadge();
}

updateNotifBadge();
setInterval(updateNotifBadge, 60000);
