// app/static/js/admin_header.js
// Admin Header — извлечена от app/templates/layouts/admin_header.html (Правило 1).

document.getElementById('adminHeaderSupportBtn').addEventListener('click', function() { openSupportPopup(); });

async function refreshSupportBadge() {
    try {
        const d = await (await fetch('/admin/support/unread')).json();
        const badge = document.getElementById('supportBadge');
        if (!badge) return;
        if (d.count > 0) { badge.textContent = d.count; badge.classList.add('ah-support-badge-visible'); }
        else badge.classList.remove('ah-support-badge-visible');
    } catch(e) {}
}

// Зареждаме при страницата
refreshSupportBadge();
// Обновяваме на всеки 30 секунди
setInterval(refreshSupportBadge, 30000);

(function() {
    var el = document.getElementById('adminHeaderUtcClock');
    if (!el) return;
    var months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    function tick() {
        var now = new Date();
        var pad = function(n) { return String(n).padStart(2, '0'); };
        var dateStr = pad(now.getUTCDate()) + ' ' + months[now.getUTCMonth()] + ' ' + now.getUTCFullYear();
        var timeStr = pad(now.getUTCHours()) + ':' + pad(now.getUTCMinutes()) + ':' + pad(now.getUTCSeconds());
        el.textContent = dateStr + ' \u00b7 UTC ' + timeStr;
    }
    tick();
    setInterval(tick, 1000);
})();
