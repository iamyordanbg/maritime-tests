// app/static/js/login-history.js
// Shared by Settings > Privacy (the user's own sign-in history) and the admin "IP entry" window.
// renderLoginHistory(entries, {admin}) returns the table HTML; all values coming from the server are escaped.
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

function lhDistanceCell(e) {
    if (e.km === null || e.km === undefined) return lhCell('Distance', '<span class="lh-muted">—</span>');
    var text = lhEscape(e.km) + ' km · ' + lhEscape(e.gap_min) + ' min';
    var badge = e.alert ? ' <span class="lh-alert-badge">⚠ Alert</span>' : '';
    return lhCell('Distance', text + badge);
}

function renderLoginHistory(entries, opts) {
    var admin = !!(opts && opts.admin);
    if (!entries || !entries.length) return '<p class="lh-empty">No sign-ins recorded yet.</p>';
    var head = '<th>Time</th><th>IP address</th><th>Location</th><th>Device</th><th>Duration</th>' + (admin ? '<th>Distance from previous</th>' : '');
    var rows = entries.map(function (e) {
        var mark = e.current ? ' <span class="lh-current-badge">This device</span>' : '';
        var cells = lhCell('Time', lhEscape(lhFormatTime(e.at)) + mark)
            + lhCell('IP address', lhEscape(e.ip) || '—')
            + lhCell('Location', lhEscape(e.place) || '<span class="lh-muted">—</span>')
            + lhCell('Device', lhEscape(e.device) || '<span class="lh-muted">—</span>')
            + lhCell('Duration', lhEscape(e.duration));
        if (admin) cells += lhDistanceCell(e);
        return '<tr' + (e.alert ? ' class="lh-row-alert"' : '') + '>' + cells + '</tr>';
    }).join('');
    return '<table class="lh-table"><thead><tr>' + head + '</tr></thead><tbody>' + rows + '</tbody></table>';
}
