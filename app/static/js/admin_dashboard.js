// app/static/js/admin_dashboard.js
// Admin Dashboard — извлечена от app/templates/admin/dashboard.html (Правило 1).

// ── Support stats badge ──
                (async function() {
                    try {
                        const d = await (await fetch('/admin/support/stats')).json();
                        const pc = document.getElementById('pendingCount');
                        const pi = document.querySelector('#pendingBadge .fa-hourglass-half');
                        pc.textContent = d.pending;
                        if (d.pending > 0) {
                            pc.style.color = '#f59e0b';
                            if (pi) pi.style.color = '#f59e0b';
                        }
                        document.getElementById('totalCount').textContent = d.total;
                    } catch(e) {
                        document.getElementById('pendingCount').textContent = '–';
                        document.getElementById('totalCount').textContent = '–';
                    }
                })();

// ── Global tooltip ──
(function(){
    var tip=document.getElementById('globalTooltip');
    document.addEventListener('mouseover',function(e){
        var el=e.target.closest('[data-tip]');
        if(!el){tip.style.display='none';return;}
        tip.textContent=el.dataset.tip;
        tip.style.display='block';
    });
    document.addEventListener('mousemove',function(e){
        if(tip.style.display==='none')return;
        var x=e.clientX+14,y=e.clientY-44;
        if(x+320>window.innerWidth)x=e.clientX-334;
        if(y<0)y=e.clientY+14;
        tip.style.left=x+'px';tip.style.top=y+'px';
    });
    document.addEventListener('mouseout',function(e){
        if(!e.relatedTarget||!e.relatedTarget.closest('[data-tip]'))tip.style.display='none';
    });
})();

// ── Delete result / cleanup expired ──
async function deleteResult(id) {
    if (!confirm('Delete this result?')) return;
    const res = await fetch(`/admin/results/${id}/delete`, { method: 'POST' });
    const data = await res.json();
    if (data.success) location.reload();
}

async function cleanupExpired() {
    if (!confirm('Delete ALL results belonging to sailors whose plan is no longer active? This cannot be undone.')) return;
    const res = await fetch('/admin/results/cleanup-expired', { method: 'POST' });
    const data = await res.json();
    if (data.success) {
        const t = document.createElement('div');
        t.className = 'fixed bottom-6 right-6 z-[100] px-4 py-3 rounded-xl text-[11px] font-bold shadow-2xl border bg-emerald-500/20 border-emerald-500/40 text-emerald-300';
        t.textContent = `✓ Deleted ${data.deleted} results from expired plans`;
        document.body.appendChild(t);
        setTimeout(() => { t.remove(); location.reload(); }, 2000);
    }
}

async function cleanupResults(days) {
    if (!confirm(`Delete all results older than ${days} days?`)) return;
    const res = await fetch('/admin/results/cleanup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ days })
    });
    const data = await res.json();
    if (data.success) {
        const t = document.createElement('div');
        t.className = 'fixed bottom-6 right-6 z-[100] px-4 py-3 rounded-xl text-[11px] font-bold shadow-2xl border bg-emerald-500/20 border-emerald-500/40 text-emerald-300';
        t.textContent = `✓ Deleted ${data.deleted} results`;
        document.body.appendChild(t);
        setTimeout(() => { t.remove(); location.reload(); }, 2000);
    }
}

// ── Snapshots chart (Chart.js) ──
let chartInstance = null;
let currentMetric = null;
let currentPeriod = '1Y';

function openChart(metric, title) {
    currentMetric = metric;
    document.getElementById('chartTitle').textContent = title;
    document.getElementById('chartModal').style.display = 'block';
    loadChart('1Y');
}

function closeChart() {
    document.getElementById('chartModal').style.display = 'none';
    if (chartInstance) { chartInstance.destroy(); chartInstance = null; }
}

function loadChart(period) {
    currentPeriod = period;
    // Активен бутон
    ['6M','1Y','2Y','3Y','5Y','ALL'].forEach(p => {
        const btn = document.getElementById('period-' + p);
        if (!btn) return;
        if (p === period) {
            btn.style.background = 'rgba(255,255,255,0.15)';
            btn.style.color = '#fff';
        } else {
            btn.style.background = 'transparent';
            btn.style.color = 'rgba(148,163,184,0.7)';
        }
    });

    fetch(`/admin/api/snapshots/${currentMetric}?period=${period}`)
        .then(r => r.json())
        .then(data => {
            if (chartInstance) chartInstance.destroy();
            const ctx = document.getElementById('analyticsChart').getContext('2d');
            chartInstance = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: data.labels,
                    datasets: [{
                        label: data.metric.replace('_', ' '),
                        data: data.data,
                        borderColor: '#4CC9F0',
                        backgroundColor: 'rgba(76,201,240,0.08)',
                        borderWidth: 2,
                        pointRadius: 3,
                        pointBackgroundColor: '#4CC9F0',
                        tension: 0.4,
                        fill: true,
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            backgroundColor: '#0B132B',
                            borderColor: 'rgba(255,255,255,0.1)',
                            borderWidth: 1,
                            titleColor: '#94a3b8',
                            bodyColor: '#fff',
                            bodyFont: { size: 14, weight: '600' },
                        }
                    },
                    scales: {
                        x: {
                            grid: { color: 'rgba(255,255,255,0.05)' },
                            ticks: { color: 'rgba(148,163,184,0.7)', font: { size: 11 } }
                        },
                        y: {
                            grid: { color: 'rgba(255,255,255,0.05)' },
                            ticks: { color: 'rgba(148,163,184,0.7)', font: { size: 11 } },
                            beginAtZero: true
                        }
                    }
                }
            });
        })
        .catch(() => {
            // Няма данни още
            const ctx = document.getElementById('analyticsChart').getContext('2d');
            if (chartInstance) chartInstance.destroy();
            chartInstance = new Chart(ctx, {
                type: 'line',
                data: { labels: [], datasets: [{ data: [], borderColor: '#4CC9F0' }] },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    plugins: { legend: { display: false } }
                }
            });
        });
}

async function recordSnapshot() {
    const r = await fetch('/admin/api/snapshots/record', { method: 'POST' });
    const d = await r.json();
    if (d.success) {
        loadChart(currentPeriod);
    }
}

document.addEventListener('keydown', e => { if(e.key === 'Escape') closeChart(); });
