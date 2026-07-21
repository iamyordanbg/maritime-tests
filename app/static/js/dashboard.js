// app/static/js/dashboard.js
// Логика за user dashboard (dashboard.html).
// Extracted от inline <script> блокове — Правило 1 на NEXT_SESSION_PROMPT.md.
// Jinja data-инжекция (window.DASHBOARD_DATA) се сетва в темплейта преди
// зареждането на този файл.

// ── History widget ──
let historyOffset = 0;
const historyTypeColors = {
    'Mix': 'background:rgba(168,85,247,0.15);color:#c084fc',
    'Mistakes': 'background:rgba(239,68,68,0.15);color:#f87171',
    'Simulator': 'background:rgba(16,185,129,0.15);color:#34d399',
    'Test': 'background:rgba(59,130,246,0.15);color:#60a5fa'
};
async function loadMoreHistory() {
    const btn = document.getElementById('historyLoadMoreBtn');
    const spinner = document.getElementById('historyLoadingSpinner');
    if (btn) { btn.disabled = true; btn.textContent = 'Loading...'; }
    try {
        const res = await fetch(`/api/history?offset=${historyOffset}&limit=5`);
        const data = await res.json();
        if (spinner) spinner.remove();
        const list = document.getElementById('historyList');
        data.items.forEach(r => {
            const div = document.createElement('a');
            div.href = `/result/${r.result_id}`;
            div.style.textDecoration = 'none';
            div.style.cursor = 'pointer';
            div.className = 'flex items-center justify-between p-3 hover:bg-[#1C2541]/20 transition';
            const typeStyle = historyTypeColors[r.test_type] || historyTypeColors['Test'];
            div.innerHTML = `
                <div style="min-width:0;flex:1">
                <div style="display:flex;align-items:center;gap:6px">
                    <span onclick="copyResultRef(event, '#${r.display_seq}')" title="Click to copy" style="font-size:13px;font-weight:700;color:#94a3b8;cursor:copy">#${r.display_seq}</span>
                    <p class="text-white truncate" style="font-size:13px;font-weight:700">${r.title}</p>
                </div>
                    <div style="display:flex;align-items:center;gap:6px;margin-top:2px">
                        <span onclick="copyResultRef(event, '${r.taken_at}')" title="Click to copy" class="text-[9px] text-slate-500" style="cursor:copy">${r.taken_at}</span>
                        <span onclick="copyResultRef(event, '${r.display_id}')" title="Click to copy" class="text-[9px] text-slate-500" style="font-family:inherit;cursor:copy">${r.display_id}</span>
                        <span style="font-size:8px;font-weight:700;padding:1px 5px;border-radius:4px;text-transform:uppercase;letter-spacing:0.04em;shrink:0;${typeStyle}">${r.test_type}</span>
                    </div>
                </div>
                <div class="flex items-center gap-3 shrink-0">
                    <div class="text-right">
                        <span class="font-black text-sm ${r.passed ? 'text-emerald-400' : 'text-rose-400'}">${r.percent}%</span>
                        <p class="text-[9px] text-slate-500">${r.score}/${r.total}</p>
                    </div>
                    ${r.passed
                        ? '<span class="bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-1.5 py-0.5 rounded text-[9px] font-bold uppercase">Passed</span>'
                        : '<span class="bg-rose-500/10 text-rose-400 border border-rose-500/20 px-1.5 py-0.5 rounded text-[9px] font-bold uppercase">Failed</span>'}
                </div>`;
            list.appendChild(div);
        });
        historyOffset += data.items.length;
        if (!data.has_more) {
            if (btn) btn.style.display = 'none';
        } else {
            if (btn) { btn.disabled = false; btn.textContent = 'Load more'; btn.style.display = 'inline-block'; }
        }
    } catch (e) {
        if (btn) { btn.disabled = false; btn.textContent = 'Load more'; }
        const spinner = document.getElementById('historyLoadingSpinner');
        if (spinner) spinner.textContent = 'Could not load history.';
    }
}
loadMoreHistory();

// ── Quota / Sim limit modal ──
function showSimLimitModal() {
    document.getElementById('quotaModalTitle').textContent = 'Daily Simulator Limit Reached';
    document.getElementById('quotaModalText').textContent =
        "You've already used your Simulator attempt for today. Come back tomorrow, or activate a paid plan for unlimited access!";
    document.getElementById('quotaExceededModal').classList.remove('hidden');
}

(function() {
    const params = new URLSearchParams(window.location.search);
    let show = false;
    if (params.get('quota_exceeded') === '1') {
        show = true;
    } else if (params.get('sim_limit_reached') === '1') {
        document.getElementById('quotaModalTitle').textContent = 'Daily Simulator Limit Reached';
        document.getElementById('quotaModalText').textContent =
            "You've already used your Simulator attempt for today. Come back tomorrow, or activate a paid plan for unlimited access!";
        show = true;
    }
    if (show) {
        document.getElementById('quotaExceededModal').classList.remove('hidden');
        window.history.replaceState({}, '', window.location.pathname);
    }
})();

// ── Greeting ──
(function() {
    const name = (window.DASHBOARD_DATA && window.DASHBOARD_DATA.userName) || 'Sailor';
    const msgs = [
        "Добре дошъл, "+name+"! ⚓ Компасът е настроен — готов за следващия тест?",
        "Здравей, "+name+"! ☕ Кафето чака — но първо един тест.",
        "Добре дошъл, "+name+"! 🌊 Морето е спокойно — идеален ден за учене.",
        "Хей, "+name+"! 📜 Послание от капитана: учи всеки ден.",
        "⚓ Всеки въпрос е стъпка към диплома.",
        "🚢 Знанието е котва — закотви се здраво.",
        "🌊 Морето не прощава незнание.",
        "🧭 Добрият моряк учи докато е на сушата.",
    ];
    const el = document.getElementById('headerGreetingText');
    const bar = document.getElementById('headerGreeting');
    if (!el || !bar) return;
    el.textContent = msgs[Math.floor(Math.random() * msgs.length)];
    setTimeout(() => { bar.style.opacity = '1'; }, 300);
    setTimeout(() => { bar.style.opacity = '0'; }, 6300);
})();

// ── Signal / Inbox ──
async function openInbox() {
    if (typeof openSupportCenter === 'function') openSupportCenter();
}
async function submitSignal(e) {
    e.preventDefault();
    const form = document.getElementById('signalForm');
    const fd = new FormData(form);
    await fetch('/signal', { method: 'POST', body: fd });
    document.getElementById('signalModal').classList.add('hidden');
    form.reset();
}
window.addEventListener('pageshow', function(event) {
    document.getElementById('signalModal')?.classList.add('hidden');
    if (event.persisted && typeof updateSupportBadge === 'function') updateSupportBadge();
});

// ── Library counter pulse ──
(function() {
    if (sessionStorage.getItem('libJustSelected') === '1') {
        sessionStorage.removeItem('libJustSelected');
        var c = document.getElementById('libHeaderCounter');
        if (c) {
            c.style.background = 'rgba(6,214,160,0.18)';
            c.style.borderColor = 'rgba(6,214,160,0.5)';
            c.style.color = '#06D6A0';
            setTimeout(function() {
                c.style.background = 'rgba(255,255,255,0.05)';
                c.style.borderColor = 'rgba(255,255,255,0.12)';
                c.style.color = 'rgba(232,237,242,0.75)';
            }, 1700);
        }
    }
})();

// ── Library refreshed toast (window.DASHBOARD_DATA.libraryRefreshed от Jinja) ──
(function() {
    if (!window.DASHBOARD_DATA || !window.DASHBOARD_DATA.libraryRefreshed) return;
    var t = document.createElement('div');
    t.style.cssText = 'position:fixed;top:70px;right:20px;z-index:9000;background:#1C362A;border:1px solid rgba(81,159,149,0.4);border-radius:10px;padding:12px 16px;display:flex;align-items:center;gap:10px;box-shadow:0 4px 20px rgba(0,0,0,0.4);cursor:pointer;opacity:0;transition:opacity 0.4s ease;max-width:280px';
    t.innerHTML = '<i class="fa-solid fa-rotate" style="color:#519F95;font-size:14px;flex-shrink:0"></i><div><p style="font-size:12px;font-weight:600;color:#519F95;margin:0 0 2px">Нов 7-дневен цикъл!</p><p style="font-size:11px;color:rgba(81,159,149,0.7);margin:0">Избери нов тест от Library ↑</p></div>';
    document.body.appendChild(t);
    requestAnimationFrame(() => requestAnimationFrame(() => { t.style.opacity = '1'; }));
    var timer = setTimeout(fade, 5000);
    t.onclick = fade;
    function fade() { clearTimeout(timer); t.style.opacity = '0'; setTimeout(() => t.remove(), 400); }
})();

// ── Tooltips ──
function showCounterTooltip() { var b = document.getElementById('counterTooltipBox'); if (b) b.style.display = 'block'; }
function hideCounterTooltip() { var b = document.getElementById('counterTooltipBox'); if (b) b.style.display = 'none'; }
function showPlanTooltip() { const t = document.getElementById('planTooltip'); if (t) t.style.display = 'block'; }
function hidePlanTooltip() { const t = document.getElementById('planTooltip'); if (t) t.style.display = 'none'; }

// ── Copy result ref ──
let _inlineTimer = null;
function copyResultRef(event, text) {
    event.preventDefault();
    event.stopPropagation();
    navigator.clipboard.writeText(text).then(() => {
        const el = event.target;
        const original = el.textContent;
        const originalColor = el.style.color;
        el.textContent = '✓ Copied';
        el.style.color = '#34d399';
        setTimeout(() => { el.textContent = original; el.style.color = originalColor; }, 1200);
    }).catch(() => {});
}

// ── Inline premium toast ──
function showInlineToast(btn) {
    const t = document.getElementById('inlineToast');
    if (!t) return;
    clearTimeout(_inlineTimer);
    const r = btn.getBoundingClientRect();
    t.style.display = 'block';
    t.style.opacity = '0';
    requestAnimationFrame(() => {
        const tw = t.offsetWidth;
        let left = r.left;
        if (left + tw > window.innerWidth - 24) left = window.innerWidth - tw - 24;
        t.style.left = left + 'px';
        t.style.top = (r.bottom + 6) + 'px';
        requestAnimationFrame(() => { t.style.opacity = '1'; });
    });
    _inlineTimer = setTimeout(() => {
        t.style.opacity = '0';
        setTimeout(() => { t.style.display = 'none'; }, 200);
    }, 2800);
}
document.addEventListener('click', function(e) {
    const t = document.getElementById('inlineToast');
    if (t && t.style.display !== 'none' && !e.target.closest('button')) {
        clearTimeout(_inlineTimer);
        t.style.opacity = '0';
        setTimeout(() => { t.style.display = 'none'; }, 200);
    }
});

// ── News widget ──
function hideNewsWidget() {
    const w = document.getElementById('newsWidget');
    const h = document.getElementById('newsWidgetHidden');
    w.classList.remove('dash-news-visible'); w.classList.add('dash-news-hidden');
    h.classList.remove('dash-news-hidden'); h.classList.add('dash-news-visible');
    document.cookie = 'hideNews=1;path=/;max-age=2592000';
}
function showNewsWidget() {
    const w = document.getElementById('newsWidget');
    const h = document.getElementById('newsWidgetHidden');
    w.classList.remove('dash-news-hidden'); w.classList.add('dash-news-visible');
    h.classList.remove('dash-news-visible'); h.classList.add('dash-news-hidden');
    document.cookie = 'hideNews=0;path=/;max-age=2592000';
}

// ── News feed ──
(async function loadDashNews() {
    let allPosts = [], shown = 0;
    const STEP = 3;
    async function fetchPosts() {
        try {
            const res = await fetch('/feed/latest?limit=50');
            allPosts = await res.json(); shown = 0; renderPosts();
        } catch (e) {
            document.getElementById('dashNewsFeed').innerHTML = '<p style="color:#475569;font-size:10px;text-align:center;padding:20px 0">—</p>';
        }
    }
    function postHTML(p) {
        return `<div onclick="openDashNewsPost(${p.id})" style="cursor:pointer;padding:7px 8px;border-radius:7px;border:1px solid rgba(255,255,255,0.06);margin-bottom:4px;transition:background .15s" onmouseover="this.style.background='rgba(255,255,255,0.06)'" onmouseout="this.style.background='transparent'">
            <p style="font-size:11px;font-weight:600;color:#e2e8f0;line-height:1.35;margin:0 0 3px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden">${p.title}</p>
            <div style="display:flex;align-items:center;gap:6px">
                <span style="font-size:9px;color:#475569">${p.time_ago}</span>
                <span style="font-size:9px;color:#475569"><i class="fa-regular fa-eye" style="font-size:8px"></i> ${p.views || 0}</span>
                <span style="font-size:9px;color:#475569"><i class="fa-regular fa-comment" style="font-size:8px"></i> ${p.comments || 0}</span>
            </div>
        </div>`;
    }
    function renderPosts() {
        const el = document.getElementById('dashNewsFeed');
        if (!allPosts.length) { el.innerHTML = '<p style="color:#475569;font-size:10px;text-align:center;padding:20px 0">No news yet</p>'; return; }
        const slice = allPosts.slice(0, shown + STEP); shown = slice.length;
        el.innerHTML = slice.map(postHTML).join('');
        if (shown < allPosts.length) el.innerHTML += `<button onclick="loadMoreNews()" style="width:100%;margin-top:4px;padding:5px;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);border-radius:7px;color:rgba(255,255,255,0.5);font-size:9px;cursor:pointer" onmouseover="this.style.background='rgba(255,255,255,0.1)'" onmouseout="this.style.background='rgba(255,255,255,0.05)'">Load more</button>`;
    }
    window.loadMoreNews = function() {
        const el = document.getElementById('dashNewsFeed');
        const slice = allPosts.slice(0, shown + STEP); shown = slice.length;
        el.innerHTML = slice.map(postHTML).join('');
        if (shown < allPosts.length) el.innerHTML += `<button onclick="loadMoreNews()" style="width:100%;margin-top:4px;padding:5px;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);border-radius:7px;color:rgba(255,255,255,0.5);font-size:9px;cursor:pointer">Load more</button>`;
    };
    fetchPosts();
})();

async function openDashNewsPost(id) {
    let overlay = document.getElementById('dashNewsOverlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'dashNewsOverlay';
        overlay.style.cssText = 'display:none;position:fixed;inset:0;z-index:9999;background:rgba(7,26,46,0.7);backdrop-filter:blur(3px);align-items:center;justify-content:center';
        overlay.innerHTML = `<div style="background:#fff;border-radius:20px;width:500px;max-width:95vw;max-height:88vh;display:flex;flex-direction:column;box-shadow:0 25px 80px rgba(0,0,0,0.5)">
            <div style="display:flex;align-items:flex-start;justify-content:space-between;padding:20px 24px 14px;border-bottom:1px solid #f3f4f6;gap:12px">
                <h2 id="dashNewsTitle" style="font-size:16px;font-weight:700;color:#111827;line-height:1.4;flex:1"></h2>
                <button onclick="document.getElementById('dashNewsOverlay').style.display='none';document.body.style.overflow=''"
                    style="background:#f3f4f6;border:1px solid #e5e7eb;width:32px;height:32px;border-radius:50%;cursor:pointer;font-size:18px;color:#374151;display:flex;align-items:center;justify-content:center;flex-shrink:0">✕</button>
            </div>
            <div id="dashNewsBody" style="overflow-y:auto;padding:20px 24px;flex:1;font-size:13px;color:#374151;line-height:1.7"></div>
            <div style="padding:12px 24px;border-top:1px solid #f3f4f6;display:flex;justify-content:space-between;align-items:center">
                <span id="dashNewsMeta" style="font-size:11px;color:#9ca3af"></span>
                <a href="/feed" style="font-size:12px;font-weight:600;color:#0B132B;text-decoration:none">All news →</a>
            </div>
        </div>`;
        overlay.addEventListener('click', e => { if (e.target === overlay) { overlay.style.display = 'none'; document.body.style.overflow = ''; } });
        document.body.appendChild(overlay);
    }
    overlay.style.display = 'flex';
    document.body.style.overflow = 'hidden';
    document.getElementById('dashNewsTitle').textContent = '...';
    document.getElementById('dashNewsBody').innerHTML = '<div style="text-align:center;padding:30px;color:#9ca3af"><i class="fa-solid fa-circle-notch fa-spin"></i></div>';
    const res = await fetch('/feed/post/' + id);
    const data = await res.json();
    document.getElementById('dashNewsTitle').textContent = data.title;
    document.getElementById('dashNewsBody').innerHTML = `${data.image_url ? `<img src="${data.image_url}" style="width:100%;border-radius:8px;margin-bottom:14px;max-height:200px;object-fit:cover">` : ''}<p style="white-space:pre-wrap">${data.body}</p>`;
    document.getElementById('dashNewsMeta').textContent = `👁 ${data.views}  ·  ${data.time_ago}`;
}

// ── Quota Modal ──
// Quota exceeded popup — идва от server-side redirect (?quota_exceeded=1),
// когато потребител се опита да зареди тест/mix/mistakes/simulator, но
// притежаващият grant вече е изчерпал лимита си от тестове.
(function() {
    const params = new URLSearchParams(window.location.search);
    if (params.get('quota_exceeded') === '1') {
        document.getElementById('quotaExceededModal')?.classList.remove('hidden');
        params.delete('quota_exceeded');
        const newUrl = window.location.pathname + (params.toString() ? '?' + params.toString() : '');
        window.history.replaceState({}, '', newUrl);
    }
})();

// ── Review Prompt ──
// Показва се, ако потребителят е близо до изтичане на активен план
// (2 дни или <5 оставащи теста) и никога не е оставял отзив - виж
// app/services/reviews.py::should_prompt_review() за пълната логика.
let _reviewStars = 0;

function _reviewSetStars(n) {
    _reviewStars = n;
    document.querySelectorAll('.review-star-btn').forEach(btn => {
        const starVal = parseInt(btn.dataset.star, 10);
        btn.classList.toggle('active', starVal <= n);
    });
}

function _reviewDismiss() {
    document.getElementById('reviewPromptModal')?.classList.add('hidden');
}

async function _reviewSubmit() {
    const errEl = document.getElementById('reviewErrorMsg');
    errEl.classList.add('hidden');

    const text = document.getElementById('reviewText').value.trim();
    const role = document.getElementById('reviewRole').value.trim();
    const visibility = document.querySelector('input[name="reviewVisibility"]:checked')?.value || 'anonymous';

    if (_reviewStars < 1) {
        errEl.textContent = 'Please select a star rating.';
        errEl.classList.remove('hidden');
        return;
    }
    if (!text) {
        errEl.textContent = 'Please write a short review.';
        errEl.classList.remove('hidden');
        return;
    }

    const fd = new FormData();
    fd.append('stars', _reviewStars);
    fd.append('text', text);
    fd.append('role', role);
    fd.append('visibility', visibility);

    try {
        const res = await fetch('/api/review/submit', {method: 'POST', body: fd});
        const data = await res.json();
        if (data.success) {
            document.getElementById('reviewStep1').classList.add('hidden');
            document.getElementById('reviewStep2').classList.remove('hidden');
        } else {
            errEl.textContent = data.message || 'Something went wrong. Please try again.';
            errEl.classList.remove('hidden');
        }
    } catch (e) {
        errEl.textContent = 'Something went wrong. Please try again.';
        errEl.classList.remove('hidden');
    }
}

// Event delegation - единствен listener на modal-a, реагира по data-action/
// data-star атрибути вместо inline onclick= в HTML-а.
document.addEventListener('click', function(e) {
    const modal = document.getElementById('reviewPromptModal');
    if (!modal || !modal.contains(e.target)) return;

    const starBtn = e.target.closest('.review-star-btn');
    if (starBtn) {
        _reviewSetStars(parseInt(starBtn.dataset.star, 10));
        return;
    }

    const actionBtn = e.target.closest('[data-action]');
    if (!actionBtn) return;
    if (actionBtn.dataset.action === 'review-dismiss') _reviewDismiss();
    if (actionBtn.dataset.action === 'review-submit') _reviewSubmit();
});

(async function() {
    try {
        const res = await fetch('/api/review/should-prompt');
        const data = await res.json();
        if (data.should_prompt) {
            document.getElementById('reviewPromptModal')?.classList.remove('hidden');
        }
    } catch (e) { /* тихо - не блокираме dashboard-a при неуспешна проверка */ }
})();
