// app/static/js/dashboard.js
// Логика за user dashboard (dashboard.html).
// Extracted от inline <script> блокове — Правило 1 на CLAUDE.md.
// Jinja data-инжекция (window.DASHBOARD_DATA) се сетва в темплейта преди
// зареждането на този файл.

// ── History widget ──
let historyOffset = 0;
const HISTORY_KINDS = ['Mix', 'Mistakes', 'Simulator', 'Test'];   // colours live in dashboard.css (.dash-hist-kind--*)
let historyLoading = false, historyDone = false;
async function loadMoreHistory() {
    if (historyLoading || historyDone) return;
    historyLoading = true;
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
            div.className = 'flex items-center justify-between p-3 hover:bg-[#1C2541]/20 transition dash-hist-row';
            const kind = HISTORY_KINDS.includes(r.test_type) ? r.test_type : 'Test';
            div.innerHTML = `
                <div class="dash-hist-main">
                <div class="dash-hist-line1">
                    <span data-on-click='[["copyResultRef","$event","$data:copy"]]' data-copy="#${r.display_seq}" title="Click to copy" class="dash-hist-seq">#${r.display_seq}</span>
                    <p class="text-white truncate dash-hist-title">${r.title}</p>
                </div>
                    <div class="dash-hist-line2">
                        <span data-on-click='[["copyResultRef","$event","$data:copy"]]' data-copy="${r.taken_at}" title="Click to copy" class="text-[9px] text-slate-500 dash-hist-date">${r.taken_at}</span>
                        <span data-on-click='[["copyResultRef","$event","$data:copy"]]' data-copy="${r.display_id}" title="Click to copy" class="text-[9px] text-slate-500 dash-hist-did">${r.display_id}</span>
                        <span class="dash-hist-kind dash-hist-kind--${kind.toLowerCase()}">${r.test_type}</span>
                    </div>
                </div>
                <div class="flex items-center gap-3 shrink-0">
                    <div class="text-right">
                        <span class="font-black text-sm dash-hist-pct ${r.passed ? 'text-emerald-400' : 'text-rose-400'}">${r.percent}%</span>
                        <p class="text-[9px] text-slate-500 dash-hist-score">${r.score}/${r.total}</p>
                    </div>
                    ${r.passed
                        ? '<span class="bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-1.5 py-0.5 rounded text-[9px] font-bold uppercase dash-hist-status">Passed</span>'
                        : '<span class="bg-rose-500/10 text-rose-400 border border-rose-500/20 px-1.5 py-0.5 rounded text-[9px] font-bold uppercase dash-hist-status">Failed</span>'}
                </div>`;
            list.appendChild(div);
        });
        historyOffset += data.items.length;
        if (!data.has_more) {
            historyDone = true;
            if (btn) btn.style.display = 'none';
        } else {
            if (btn) { btn.disabled = false; btn.textContent = 'Load more'; btn.style.display = 'inline-block'; }
        }
    } catch (e) {
        if (btn) { btn.disabled = false; btn.textContent = 'Load more'; }
        const spinner = document.getElementById('historyLoadingSpinner');
        if (spinner) spinner.textContent = 'Could not load history.';
    } finally {
        historyLoading = false;
        watchHistoryEnd();
    }
}

// Phone: no "Load more" button - the next cards load when the end of the list scrolls into view.
const historyPhone = window.matchMedia('(max-width: 767px)');
let historyObserver = null;
function watchHistoryEnd() {
    const sentinel = document.querySelector('.dash-history-footer');
    if (!sentinel || historyDone || !historyPhone.matches || !('IntersectionObserver' in window)) return;
    if (!historyObserver) {
        historyObserver = new IntersectionObserver(entries => {
            if (entries.some(e => e.isIntersecting)) loadMoreHistory();
        }, { rootMargin: '300px 0px' });
    }
    historyObserver.unobserve(sentinel);   // re-observe so the callback fires again while the end is still on screen
    historyObserver.observe(sentinel);
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
        "Welcome, "+name+"! ⚓ The compass is set — ready for your next test?",
        "Hello, "+name+"! ☕ The coffee can wait — one test first.",
        "Welcome, "+name+"! 🌊 The sea is calm — a perfect day to study.",
        "Hey, "+name+"! 📜 A message from the captain: study every day.",
        "⚓ Every question is a step toward your certificate.",
        "🚢 Knowledge is an anchor — hold fast.",
        "🌊 The sea does not forgive ignorance.",
        "🧭 A good sailor studies while on land.",
    ];
    const el = document.getElementById('headerGreetingText');
    const bar = document.getElementById('headerGreeting');
    if (!el || !bar) return;
    el.textContent = msgs[Math.floor(Math.random() * msgs.length)];
    // header.has-greeting drives the phone layout (lighthouse + message while shown, centred brand otherwise)
    const header = bar.closest('header');
    setTimeout(() => { bar.style.opacity = '1'; if (header) header.classList.add('has-greeting'); }, 300);
    setTimeout(() => { bar.style.opacity = '0'; if (header) header.classList.remove('has-greeting'); }, 6300);
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
    t.innerHTML = '<i class="fa-solid fa-rotate" style="color:#519F95;font-size:14px;flex-shrink:0"></i><div><p style="font-size:12px;font-weight:600;color:#519F95;margin:0 0 2px">New 7-day cycle!</p><p style="font-size:11px;color:rgba(81,159,149,0.7);margin:0">Choose a new test from the Library ↑</p></div>';
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
// ── News feed ──
(async function loadDashNews() {
    let allPosts = [];
    async function fetchPosts() {
        try {
            const res = await fetch('/feed/latest?limit=50');
            allPosts = await res.json(); renderPosts();
        } catch (e) {
            document.getElementById('dashNewsFeed').innerHTML = '<p style="color:#475569;font-size:10px;text-align:center;padding:20px 0">—</p>';
        }
    }
    function postHTML(p) {
        return `<div data-on-click='[["openDashNews","$num:id"]]' data-id="${p.id}" class="dash-news-item${p.image_url ? ' has-image' : ''}">
            ${p.image_url ? `<img class="dash-news-item-img" src="${p.image_url}" alt="" loading="lazy">` : '<div class="dash-news-item-img dash-news-item-img--none"></div>'}
            <p class="dash-news-item-title">${p.title}</p>
            <p class="dash-news-item-text">${escapeHtml(p.body || '')}</p>
            <div class="dash-news-item-meta">
                <span class="dash-news-item-date">${p.time_ago}</span>
                <span><i class="fa-regular fa-eye"></i> ${p.views || 0}</span>
                <span><i class="fa-regular fa-comment"></i> ${p.comments || 0}</span>
                <span class="dash-news-item-likes"><i class="fa-regular fa-thumbs-up"></i> ${p.likes || 0}</span>
            </div>
        </div>`;
    }
    function renderPosts() {
        const el = document.getElementById('dashNewsFeed');
        if (!allPosts.length) { el.innerHTML = '<p style="color:#475569;font-size:10px;text-align:center;padding:20px 0">No news yet</p>'; return; }
        // Всички заредени новини - картата се скролва с мишката (#dashNewsFeed има overflow-y:auto).
        el.innerHTML = allPosts.map(postHTML).join('');
    }
    fetchPosts();
})();

function closeDashNews() {
    const overlay = document.getElementById('dashNewsOverlay');
    if (overlay) overlay.style.display = 'none';
    document.body.style.overflow = '';
}

// Phones: a tile opens the full-screen News Center (feed); there the post itself opens on a second tap.
// Desktop keeps the small reader popup.
function openDashNews(id) {
    if (window.matchMedia('(max-width: 767px)').matches) openNewsCenter(id);
    else openDashNewsPost(id);
}

async function openDashNewsPost(id) {
    let overlay = document.getElementById('dashNewsOverlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'dashNewsOverlay';
        overlay.className = 'dash-news-overlay';
        overlay.innerHTML = `<div class="dash-news-modal">
            <div class="dash-news-modal-head">
                <button type="button" class="dash-news-modal-home" aria-label="Back to home" data-on-click='[["closeDashNews"]]'><i class="fa-solid fa-house"></i> Home</button>
                <h2 id="dashNewsTitle"></h2>
                <button type="button" class="dash-news-modal-close" aria-label="Close" data-on-click='[["closeDashNews"]]'>✕</button>
            </div>
            <div id="dashNewsBody"></div>
            <div class="dash-news-modal-foot">
                <span id="dashNewsMeta"></span>
                <a href="/feed">All news →</a>
            </div>
        </div>`;
        overlay.addEventListener('click', e => { if (e.target === overlay) closeDashNews(); });
        document.body.appendChild(overlay);
        lockPopupScroll(overlay, '#dashNewsBody');
    }
    overlay.style.display = 'flex';
    document.body.style.overflow = 'hidden';
    document.getElementById('dashNewsTitle').textContent = '...';
    document.getElementById('dashNewsBody').innerHTML = '<div class="dash-news-modal-loading"><i class="fa-solid fa-circle-notch fa-spin"></i></div>';
    const res = await fetch('/feed/post/' + id);
    const data = await res.json();
    document.getElementById('dashNewsTitle').textContent = data.title;
    document.getElementById('dashNewsBody').innerHTML = `${data.image_url ? `<img class="dash-news-modal-img" src="${data.image_url}" alt="">` : ''}<p class="dash-news-modal-text">${escapeHtml(data.body || '')}</p>`;
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
// Показва се, ако потребителят е близо до изтичане на активен план и никога не е
// оставял отзив (виж app/services/reviews.py::review_prompt_variant()). Три избора:
// Not now (напомняне по имейл след седмица), No thanks (повече не се показва), Submit review.
// След имейла прозорецът е с два избора (без Not now).
let _reviewStars = 0;

function _reviewSetStars(n) {
    _reviewStars = n;
    document.querySelectorAll('.review-star-btn').forEach(btn => {
        const starVal = parseInt(btn.dataset.star, 10);
        btn.classList.toggle('active', starVal <= n);
    });
}

function _reviewClose() {
    document.getElementById('reviewPromptModal')?.classList.add('hidden');
}

// Not now / No thanks: записва избора на сървъра и затваря прозореца.
async function _reviewChoose(endpoint) {
    try {
        await fetch(endpoint, {method: 'POST'});
    } catch (e) { /* избор не е записан - прозорецът ще се покаже пак при следващо зареждане */ }
    _reviewClose();
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
    const action = actionBtn.dataset.action;
    if (action === 'review-close') _reviewClose();
    if (action === 'review-postpone') _reviewChoose('/api/review/postpone');
    if (action === 'review-decline') _reviewChoose('/api/review/decline');
    if (actionBtn.dataset.action === 'review-submit') _reviewSubmit();
});

// "My account" опцията показва имената от акаунта; без имена е недостъпна.
function _reviewSetAccountOption(name) {
    const radio = document.getElementById('reviewVisibilityAccount');
    const label = document.getElementById('reviewAccountLabel');
    if (!radio || !label) return;
    if (name) {
        label.textContent = 'My account: ' + name;
    } else {
        radio.disabled = true;
        label.textContent = 'My account (add your name in Settings first)';
    }
}

(async function() {
    try {
        const res = await fetch('/api/review/should-prompt');
        const data = await res.json();
        if (data.should_prompt) {
            _reviewSetAccountOption(data.display_name);
            document.getElementById('reviewPostponeBtn')?.classList.toggle('hidden', data.variant === 'reminder');
            document.getElementById('reviewPromptModal')?.classList.remove('hidden');
        }
    } catch (e) { /* тихо - не блокираме dashboard-a при неуспешна проверка */ }
})();


// Locked-card tooltip toggle (data-on-click in dashboard.html).
function toggleLockTooltip(card) {
    var tip = card.querySelector('.dash-lock-tooltip');
    if (tip) tip.style.display = tip.style.display === 'block' ? 'none' : 'block';
}
