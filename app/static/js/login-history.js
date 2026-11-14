// app/static/js/login-history.js
// Shared by Settings > Privacy (the user's own sign-in history) and the admin "IP entry" window.
// renderLoginHistory(entries) returns the table HTML; all values coming from the server are escaped.
function lhEscape(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, function (c) {
        return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
}

function lhFormatTime(iso) {
    var d = new Date(iso);
    if (isNaN(d.getTime())) return '—';
    return d.toLocaleString([], { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function lhCell(label, html) {
    return '<td data-label="' + label + '">' + html + '</td>';
}

function renderLoginHistory(entries) {
    if (!entries || !entries.length) return '<p class="lh-empty">No sign-ins recorded yet.</p>';
    var rows = entries.map(function (e) {
        var mark = e.current ? ' <span class="lh-current-badge">This device</span>' : '';
        return '<tr>'
            + lhCell('Time', lhEscape(lhFormatTime(e.at)) + mark)
            + lhCell('IP address', lhEscape(e.ip) || '—')
            + lhCell('Device', lhEscape(e.device) || '<span class="lh-muted">—</span>')
            + lhCell('Duration', lhEscape(e.duration))
            + '</tr>';
    }).join('');
    return '<table class="lh-table"><thead><tr><th>Time</th><th>IP address</th><th>Device</th><th>Duration</th></tr></thead><tbody>'
        + rows + '</tbody></table>';
}
