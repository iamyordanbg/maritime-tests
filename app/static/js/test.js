// Test страница - извлечена логика (виж app/templates/user/test.html
// за window.TEST_DATA данните, подавани от Jinja)

// ==== Anti-copy защита (само в mainContent зоната) ====
// Блокира copy/cut/десен бутон (context menu) в тестовата зона - обичайните
// начини потребителят да копира текст. Не блокира глобално цялата страница
// (напр. header/sidebar остават нормални за copy, ако там има нужда).
document.addEventListener('DOMContentLoaded', function () {
    const area = document.getElementById('mainContent');
    if (!area) return;
    ['copy', 'cut', 'contextmenu'].forEach(function (evt) {
        area.addEventListener(evt, function (e) { e.preventDefault(); });
    });
});

// ==== Основна логика (реклами, рендериране на въпроси, отговори,
// прогресивно зареждане, изпращане на теста) ====



const totalQuestions = window.TEST_DATA.totalQuestions;

// Зарежда реални реклами (от admin панела) в слотовете на всеки 10-ти въпрос.
// data-ad-loaded маркира вече обработените слотове, за да не се дублира
// извикването при новодобавените слотове от progressive rendering-а.
function loadAdsForNewSlots() {
    document.querySelectorAll('.ad-slot:not([data-ad-loaded])').forEach(async (slot) => {
        slot.setAttribute('data-ad-loaded', '1');
        try {
            const res = await fetch('/api/random-ad');
            const data = await res.json();
            if (!data.ad) return;
            const ad = data.ad;
            const body = slot.querySelector('.ad-slot-body');
            const imgHtml = ad.image_url ? `<img src="${ad.image_url}" style="max-width:100%;max-height:120px;border-radius:8px;margin-bottom:10px">` : '';
            const linkOpen = ad.link_url ? `<a href="${ad.link_url}" target="_blank" rel="noopener" onclick="fetch('/api/ad-click/${ad.id}',{method:'POST'})" style="text-decoration:none;color:inherit">` : '<div>';
            const linkClose = ad.link_url ? '</a>' : '</div>';
            body.innerHTML = `${linkOpen}${imgHtml}<p style="font-size:15px;font-weight:700;color:#E8A020;margin-bottom:6px">${ad.title}</p>${ad.body ? `<p style="font-size:13px;color:rgba(232,237,242,0.6)">${ad.body}</p>` : ''}${linkClose}`;
        } catch(e) {}
    });
}
loadAdsForNewSlots();
const testId = window.TEST_DATA.testId;
const isDemo = window.TEST_DATA.isDemo;
const startTime = Date.now();

// Плавно появяване на страницата
document.addEventListener('DOMContentLoaded', function() {
    setTimeout(() => {
        document.getElementById('mainContent').style.opacity = '1';
    }, 50);
});

// answers[qId] = oIdx — директно по qId, без индекси
const answers = {};

// Пълните данни за ВСИЧКИ въпроси — един JSON блок (евтино за парсване,
// дори при 700+ въпроса), използва се и за optionsMap, и за progressive
// rendering-а на въпросите извън първите 12, рендерирани от сървъра.
const allQuestions = window.TEST_DATA.allQuestions;
const INITIAL_RENDERED = window.TEST_DATA.initialRendered;
const isFreePlanJs = window.TEST_DATA.isFreePlanJs;
const isShuffleJs = window.TEST_DATA.isShuffleJs;

const optionsMap = {};
allQuestions.forEach(q => { optionsMap[q.id] = q.options; });

function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

// Строи HTML-а за 1 въпрос (индекс i е 0-based, глобален в целия тест) —
// точно същата разметка като Jinja цикъла по-горе, вкл. рекламния слот
// на всеки 10-ти въпрос за free план.
function buildQuestionHtml(q, i) {
    let html = '';
    const loopIndex = i + 1;
    if (loopIndex > 1 && loopIndex % 10 === 1 && isFreePlanJs) {
        html += `
        <div class="ad-slot" id="ad-slot-${loopIndex}" style="background:linear-gradient(135deg,rgba(232,160,32,0.08),rgba(232,160,32,0.03));border:1px solid rgba(232,160,32,0.25);border-radius:14px;padding:20px 24px;text-align:center;margin:8px 0">
            <p style="font-size:10px;color:rgba(232,237,242,0.35);text-transform:uppercase;letter-spacing:0.1em;margin-bottom:8px">Реклама</p>
            <div class="ad-slot-body" style="background:rgba(255,255,255,0.04);border-radius:10px;padding:24px;min-height:80px;display:flex;align-items:center;justify-content:center">
                <div>
                    <p style="font-size:15px;font-weight:700;color:#E8A020;margin-bottom:6px">Искаш неограничен достъп?</p>
                    <p style="font-size:13px;color:rgba(232,237,242,0.6);margin-bottom:14px">Премини на платен план и реши всички тестове без ограничения</p>
                    <a href="${window.TEST_DATA.dashboardUpgradeUrl}" style="background:#E8A020;color:#071a2e;padding:8px 24px;border-radius:8px;font-size:12px;font-weight:700;text-decoration:none">Upgrade сега →</a>
                </div>
            </div>
        </div>`;
    }

    const qLabel = isShuffleJs ? ('#' + q.id) : loopIndex;
    let imgHtml = '';
    if (q.image) {
        imgHtml = `
            <div class="mt-3">
                <img src="${escapeHtml(q.image)}" alt="Снимка към въпроса" class="rounded-xl mx-auto border border-slate-700/40 transition" style="display:block;margin:0 auto;cursor:pointer" loading="lazy" onload="this.style.width=(this.naturalWidth*1.2)+'px';this.style.maxWidth='none'" onclick="toggleLightbox(this.src)">
            </div>`;
    }

    let optsHtml = '';
    q.options.forEach((opt, oIdx) => {
        const optText = (typeof opt === 'string') ? opt : opt.text;
        optsHtml += `
                <label class="opt-label flex items-center gap-3 bg-[#0B132B]/50 border border-slate-700/50 hover:border-purple-500/50 rounded-lg p-3.5 text-[15px] text-slate-300 cursor-pointer transition" id="lbl_${q.id}_${oIdx}">
                    <input type="radio" name="q_${i}" value="${oIdx}" data-qidx="${i}" data-qid="${q.id}" data-oidx="${oIdx}" onchange="onAnswer(this)" class="accent-purple-500 h-4 w-4 shrink-0">
                    <span class="text-purple-400 font-black uppercase text-[13px] shrink-0 w-6">${oIdx + 1})</span>
                    <span>${escapeHtml(optText)}</span>
                </label>`;
    });

    html += `
        <div class="bg-[#1C2541]/60 border border-slate-700/40 rounded-xl p-5 space-y-3" id="qbox_${i}">
            <p class="text-white text-[17px] font-bold leading-relaxed">
                <span class="text-purple-400 mr-1.5">${qLabel}.</span>${escapeHtml(q.question)}
            </p>${imgHtml}
            <div class="space-y-2" style="margin-top:20px">${optsHtml}
            </div>
        </div>`;
    return html;
}

// Прогресивно добавя останалите въпроси (извън първите 12) на партиди от
// по 25, всяка партида в свободното време на браузъра (requestIdleCallback),
// за да не блокира main thread-а наведнъж — точно тук беше 7-сек фризът.
function renderRemainingQuestions() {
    const container = document.getElementById('questionsContainer');
    const total = allQuestions.length;
    let idx = INITIAL_RENDERED;
    const BATCH_SIZE = 25;

    function renderBatch() {
        let html = '';
        let count = 0;
        while (idx < total && count < BATCH_SIZE) {
            html += buildQuestionHtml(allQuestions[idx], idx);
            idx++;
            count++;
        }
        if (html) container.insertAdjacentHTML('beforeend', html);
        loadAdsForNewSlots();
        if (idx < total) scheduleNextBatch();
    }

    function scheduleNextBatch() {
        if ('requestIdleCallback' in window) {
            requestIdleCallback(renderBatch, { timeout: 200 });
        } else {
            setTimeout(renderBatch, 16);
        }
    }

    if (idx < total) scheduleNextBatch();
}
document.addEventListener('DOMContentLoaded', renderRemainingQuestions);

function onAnswer(radio) {
    const qId = parseInt(radio.dataset.qid);
    const oIdx = parseInt(radio.dataset.oidx);
    answers[qId] = oIdx;
    updateProgress();
    highlightSelected(qId, oIdx);
}

function highlightSelected(qId, oIdx) {
    const opts = optionsMap[qId] || [];
    const normalClass = 'opt-label flex items-center gap-3 bg-[#0B132B]/50 border border-slate-700/50 hover:border-purple-500/50 rounded-lg p-3.5 text-[15px] text-slate-300 cursor-pointer transition';
    // Същият деликатен пастелен подход като в Simulator - редa леко
    // тонира с интензитета от слайдера (0-10), без ярка рамка около него.
    // На Light/Sepia бледият виолет почти не се вижда на светъл фон + бял
    // текст е нечетим там - топъл кехлибарен акцент + тъмен текст вместо.
    const hi = window._highlightIntensity !== undefined ? window._highlightIntensity : 5;
    const rowOpacity = (0.02 + (hi / 10) * 0.28).toFixed(3);
    const mainEl = document.getElementById('mainContent');
    const theme = mainEl ? mainEl.dataset.theme : 'dark';
    const isLightish = theme === 'light' || theme === 'sepia';
    const selectedBg = isLightish ? `rgba(180,83,9,${rowOpacity})` : `rgba(167,139,250,${rowOpacity})`;
    const selectedTextColor = isLightish ? (theme === 'sepia' ? '#4a3c28' : '#3d2c1a') : '#ffffff';
    // !important - иначе theme CSS правилото за .opt-label фон/цвят
    // (важи за ВСИЧКИ бутони на Light/Sepia) засенчва обикновен inline style
    const selectedStyle = `background:${selectedBg} !important;color:${selectedTextColor} !important`;
    // Директен достъп по ID (мигновен), не сканиране на целия документ —
    // при голям тест (768+ въпроса) querySelectorAll на всеки клик натрупваше
    // прогресивно забавяне; getElementById е постоянна скорост, без значение
    // от размера на теста.
    for (let i = 0; i < opts.length; i++) {
        const lbl = document.getElementById(`lbl_${qId}_${i}`);
        if (!lbl) continue;
        if (i === oIdx) {
            lbl.className = 'opt-label flex items-center gap-3 rounded-lg p-3.5 text-[15px] cursor-pointer transition font-bold';
            lbl.style.cssText = selectedStyle;
        } else {
            lbl.className = normalClass;
            lbl.style.cssText = '';
        }
    }
}

function updateProgress() {
    const count = Object.keys(answers).length;
    document.getElementById('answeredCount').textContent = `${count} / ${totalQuestions}`;
    const progressTextEl = document.getElementById('progressText');
    if (progressTextEl) progressTextEl.textContent = `${count} от ${totalQuestions} въпроса отговорени`;
}

async function submitTest() {
    const unanswered = totalQuestions - Object.keys(answers).length;
    if (unanswered > 0) {
        // Намери първия неотговорен въпрос и скролни до него
        const qIds = allQuestions.map(q => q.id);
        let firstUnansweredIdx = -1;
        for (let i = 0; i < qIds.length; i++) {
            if (answers[qIds[i]] === undefined) {
                firstUnansweredIdx = i;
                break;
            }
        }
        if (firstUnansweredIdx !== -1) {
            const target = document.getElementById('qbox_' + firstUnansweredIdx);
            if (target) {
                target.scrollIntoView({ behavior: 'smooth', block: 'center' });
                target.style.transition = 'box-shadow 0.3s ease';
                target.style.boxShadow = '0 0 0 2px #E8A020';
                setTimeout(() => { target.style.boxShadow = 'none'; }, 2000);
            }
        }
        return;
    }

    document.getElementById('submitBtn').disabled = true;
    document.getElementById('submitBtn').innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-1"></i> Проверява...';

    try {
        // Нормализирай ключовете
        const payload = {};
        Object.entries(answers).forEach(([k, v]) => { payload[String(k)] = v; });
        const duration = Math.round((Date.now() - startTime) / 1000);

        // Прати ID-тата на заредените въпроси
        const questionIds = allQuestions.map(q => q.id);

        const submitUrl = isDemo ? `/demo/test/${testId}/submit` : `/test/${testId}/submit`;
        const res = await fetch(submitUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                answers: payload,
                question_ids: questionIds,
                test_type: window.TEST_DATA.testType,
                duration: duration
            })
        });
        // БЪГ ФИКС: преди тук изобщо не се проверяваше res.ok/data.error -
        // при грешка (403 quota, 500 и т.н.) кодът продължаваше все едно
        // резултатът е успешен, показвайки "undefined%"/NaN, БЕЗ реален
        // запис в базата (нито история, нито брояч). Сега - същата защита
        // като в simulator.html.
        if (!res.ok) {
            let errText = '';
            try { errText = await res.text(); } catch (_) {}
            throw new Error(`HTTP ${res.status}: ${errText.slice(0, 300)}`);
        }
        const data = await res.json();
        if (data.error) {
            throw new Error(data.message || data.error);
        }

        // Оцвети всеки въпрос директно по qId
        Object.keys(optionsMap).forEach(qIdStr => {
            const qId = parseInt(qIdStr);
            const opts = optionsMap[qId];
            const selectedOIdx = (answers[qId] !== undefined) ? answers[qId] : null;

            opts.forEach((opt, oIdx) => {
                const label = document.getElementById(`lbl_${qId}_${oIdx}`);
                if (!label) return;

                const radio = label.querySelector('input[type="radio"]');
                if (radio) radio.disabled = true;

                const isSelected = (selectedOIdx === oIdx);
                const isCorrect = opt.isCorrect;

                label.className = 'opt-label flex items-center gap-3 rounded-lg p-3.5 text-[15px] border transition';

                if (isCorrect && isSelected) {
                    label.classList.add('bg-emerald-500/20', 'border-emerald-400', 'text-emerald-300', 'font-bold');
                } else if (!isCorrect && isSelected) {
                    label.classList.add('bg-rose-500/20', 'border-rose-400', 'text-rose-300');
                } else {
                    // 'Правилен, но НЕ избран от потребителя' вече е НЕУТРАЛЕН
                    // (не зелен border) - зелена рамка на опция, която
                    // потребителят изобщо не е кликнал, беше объркваща
                    // (изглеждаше сякаш Е избрана). Реалният избор на
                    // потребителя (вярно=зелено / грешно=червено) остава
                    // единственият цветен индикатор.
                    label.classList.add('bg-[#0B132B]/10', 'border-slate-700/20', 'text-slate-500');
                }
            });
        });

        const answered = Object.keys(answers).length;
        const wrong = answered - data.score;
        const skipped = totalQuestions - answered;

        const icon = document.getElementById('resultIcon');
        const title = document.getElementById('resultTitle');

        if (data.passed) {
            icon.className = 'w-16 h-16 rounded-2xl flex items-center justify-center text-3xl mx-auto bg-emerald-500/20 border border-emerald-500/30';
            icon.innerHTML = '<i class="fa-solid fa-trophy text-emerald-400"></i>';
            title.textContent = 'ПОЛОЖЕН!';
            title.className = 'text-xl font-black text-emerald-400';
        } else {
            icon.className = 'w-16 h-16 rounded-2xl flex items-center justify-center text-3xl mx-auto bg-red-500/20 border border-red-500/30';
            icon.innerHTML = '<i class="fa-solid fa-xmark text-red-400"></i>';
            title.textContent = 'НЕПОЛОЖЕН';
            title.className = 'text-xl font-black text-red-400';
        }

        document.getElementById('resultScore').innerHTML =
            `<span class="${data.passed ? 'text-emerald-400' : 'text-red-400'}">${data.percent}%</span>`;

        document.getElementById('resultStats').innerHTML = `
            <p>Отговорени: <b class="text-white">${answered}</b> от <b class="text-white">${totalQuestions}</b></p>
            <p><span class="text-emerald-400 font-bold">✓ Верни: ${data.score}</span>
               &nbsp;|&nbsp;
               <span class="text-red-400 font-bold">✗ Грешни: ${wrong}</span>
               &nbsp;|&nbsp;
               <span class="text-slate-500">Пропуснати: ${skipped}</span>
            </p>
            <p class="text-[10px] text-slate-600 mt-1">Минимум 70% за положен</p>
        `;

        document.getElementById('resultModal').classList.remove('hidden');
        // Demo - скриваме бутона към история
        const histBtn = document.getElementById('historyBtn');
        if (histBtn && isDemo) histBtn.style.display = 'none';
        document.getElementById('submitBtn').disabled = false;
        document.getElementById('submitBtn').innerHTML = '<i class="fa-solid fa-check-circle mr-1"></i> Провери';

    } catch(e) {
        document.getElementById('submitBtn').disabled = false;
        document.getElementById('submitBtn').innerHTML = '<i class="fa-solid fa-check-circle mr-1"></i> Провери';
        if (isDemo) {
            // Demo режим - показваме popup за регистрация
            const overlay = document.createElement('div');
            overlay.id = 'demoRegPopup';
            overlay.style.cssText = 'position:fixed;inset:0;z-index:99999;background:rgba(0,0,0,0.7);backdrop-filter:blur(6px);display:flex;align-items:center;justify-content:center';
            overlay.innerHTML = `
                <div style="background:#0d1f35;border:1px solid rgba(232,160,32,0.3);border-radius:20px;padding:36px 32px;max-width:420px;width:90%;text-align:center;box-shadow:0 30px 80px rgba(0,0,0,0.6)">
                    <div style="width:64px;height:64px;background:rgba(232,160,32,0.15);border-radius:16px;display:flex;align-items:center;justify-content:center;margin:0 auto 20px;font-size:28px">🔒</div>
                    <h2 style="color:#fff;font-size:20px;font-weight:700;margin:0 0 10px">Регистрирай се безплатно</h2>
                    <p style="color:rgba(255,255,255,0.55);font-size:14px;line-height:1.6;margin:0 0 24px">За да видиш верните отговори, резултата и историята си — създай безплатен акаунт. Отнема под 1 минута.</p>
                    <div style="display:flex;flex-direction:column;gap:10px">
                        <a href="/register" style="background:#e8a020;color:#071a2e;border:none;border-radius:10px;padding:13px 24px;font-size:14px;font-weight:700;text-decoration:none;display:block">
                            Регистрирай се безплатно →
                        </a>
                        <a href="/login" style="background:rgba(255,255,255,0.07);color:rgba(255,255,255,0.7);border:1px solid rgba(255,255,255,0.1);border-radius:10px;padding:11px 24px;font-size:13px;font-weight:600;text-decoration:none;display:block">
                            Вече имам акаунт
                        </a>
                        <button onclick="document.getElementById('demoRegPopup').remove()" style="background:none;border:none;color:rgba(255,255,255,0.3);font-size:12px;cursor:pointer;padding:6px">
                            Затвори
                        </button>
                    </div>
                </div>`;
            document.body.appendChild(overlay);
            overlay.addEventListener('click', function(e) {
                if (e.target === overlay) overlay.remove();
            });
        } else {
            alert('Грешка при изпращане: ' + (e && e.message ? e.message : e) + '\n\nМоля, копирай това съобщение и го изпрати за диагностика.');
        }
    }
}

// ==== Настройки за четене (слайдери, шрифтове) + lightbox за снимки ====

// ==== НАСТРОЙКИ ЗА ЧЕТЕНЕ (слайдери 0-10 за размер + отделни шрифтове
// за въпрос/отговори) ====
function togglePrefsPanel() {
    const p = document.getElementById('prefsPanel');
    p.style.display = p.style.display === 'block' ? 'none' : 'block';
}
document.addEventListener('click', function(e) {
    const panel = document.getElementById('prefsPanel');
    const btn = document.getElementById('prefsBtn');
    if (panel && panel.style.display === 'block' && !panel.contains(e.target) && e.target !== btn && !btn.contains(e.target)) {
        panel.style.display = 'none';
    }
});

const FONT_STACKS = {
    default: 'inherit',
    georgia: "Georgia, 'Times New Roman', serif",
    times: "'Times New Roman', Times, serif",
    verdana: "Verdana, Geneva, sans-serif",
    arial: "Arial, Helvetica, sans-serif",
    roboto: "'Roboto', sans-serif",
    opensans: "'Open Sans', sans-serif",
    montserrat: "'Montserrat', sans-serif",
    poppins: "'Poppins', sans-serif",
    lato: "'Lato', sans-serif",
    nunito: "'Nunito', sans-serif",
    worksans: "'Work Sans', sans-serif",
    raleway: "'Raleway', sans-serif",
    sourcesans: "'Source Sans 3', sans-serif",
    notosans: "'Noto Sans', sans-serif",
    merriweather: "'Merriweather', serif",
    playfair: "'Playfair Display', serif",
    ptserif: "'PT Serif', serif",
    oswald: "'Oswald', sans-serif",
    rubik: "'Rubik', sans-serif",
    ubuntu: "'Ubuntu', sans-serif",
};

function applyPrefs(prefs) {
    const el = document.getElementById('mainContent');
    if (!el) return;
    el.dataset.theme = prefs.theme || 'dark';

    const qSize = prefs.q_font_size !== undefined ? prefs.q_font_size : 5;
    const aSize = prefs.a_font_size !== undefined ? prefs.a_font_size : 5;
    const hi = prefs.highlight_intensity !== undefined ? prefs.highlight_intensity : 5;
    window._highlightIntensity = hi;  // четено от highlightSelected() по-долу
    const qPx = 12 + qSize * 2;   // 0 -> 12px, 10 -> 32px
    const aPx = 12 + aSize * 2;
    const qFont = FONT_STACKS[prefs.q_font_family || 'default'];
    const aFont = FONT_STACKS[prefs.a_font_family || 'default'];
    const qBold = prefs.q_bold !== undefined ? prefs.q_bold : true;
    const aBold = prefs.a_bold !== undefined ? prefs.a_bold : false;
    const qWeight = qBold ? '700' : '400';
    const aWeight = aBold ? '700' : '500';

    let styleEl = document.getElementById('dynamicPrefsStyle');
    if (!styleEl) {
        styleEl = document.createElement('style');
        styleEl.id = 'dynamicPrefsStyle';
        document.head.appendChild(styleEl);
    }
    styleEl.textContent = `
        #mainContent [id^="qbox_"] > p { font-size: ${qPx}px !important; font-family: ${qFont} !important; font-weight: ${qWeight} !important; }
        #mainContent .opt-label span:last-child { font-size: ${aPx}px !important; font-family: ${aFont} !important; font-weight: ${aWeight} !important; }
    `;

    document.getElementById('qSizeSlider').value = qSize;
    document.getElementById('aSizeSlider').value = aSize;
    document.getElementById('hiSlider').value = hi;
    document.getElementById('qSizeVal').textContent = qSize;
    document.getElementById('aSizeVal').textContent = aSize;
    document.getElementById('hiVal').textContent = hi;
    document.getElementById('qFontFamilySelect').value = prefs.q_font_family || 'default';
    document.getElementById('aFontFamilySelect').value = prefs.a_font_family || 'default';

    document.getElementById('qBoldBtn').dataset.active = qBold;
    document.getElementById('qBoldLabel').textContent = qBold ? 'On' : 'Off';
    document.getElementById('qBoldBtn').style.background = qBold ? '#4CC9F0' : 'transparent';
    document.getElementById('qBoldBtn').style.color = qBold ? '#0B132B' : '#94a3b8';

    document.getElementById('aBoldBtn').dataset.active = aBold;
    document.getElementById('aBoldLabel').textContent = aBold ? 'On' : 'Off';
    document.getElementById('aBoldBtn').style.background = aBold ? '#4CC9F0' : 'transparent';
    document.getElementById('aBoldBtn').style.color = aBold ? '#0B132B' : '#94a3b8';

    document.querySelectorAll('.pref-opt-btn').forEach(function(b) {
        const active = b.dataset.prefBtn === 'theme' && b.dataset.prefVal === (prefs.theme || 'dark');
        b.style.background = active ? '#4CC9F0' : 'transparent';
        b.style.color = active ? '#0B132B' : '#94a3b8';
        b.style.borderColor = active ? '#4CC9F0' : 'rgba(255,255,255,0.15)';
    });

    // Ако вече има избран отговор на видим въпрос, преоцвети веднага със
    // новия интензитет (без да чака нов клик)
    document.querySelectorAll('input[type="radio"]:checked').forEach(function(radio) {
        highlightSelected(parseInt(radio.dataset.qid), parseInt(radio.dataset.oidx));
    });
}

function toggleBold(key) {
    const current = window._testPrefs || {};
    const newVal = !(current[key] !== undefined ? current[key] : (key === 'q_bold'));
    setPref(key, newVal);
}

async function setPref(key, value) {
    const current = window._testPrefs || {q_font_size:5, a_font_size:5, highlight_intensity:5, theme:'dark', q_font_family:'default', a_font_family:'default', q_bold:true, a_bold:false};
    current[key] = value;
    window._testPrefs = current;
    applyPrefs(current);
    try {
        await fetch('/api/test-preferences', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({[key]: value})
        });
    } catch (e) {}
}

// 'Reset to Default' бутонът в панела - връща ВСИЧКИ настройки на
// стойностите по подразбиране (сървърът пази какви точно са те).
async function resetPrefsToDefault() {
    try {
        await fetch('/api/test-preferences', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({reset: true})
        });
        const res = await fetch('/api/test-preferences');
        const prefs = await res.json();
        window._testPrefs = prefs;
        applyPrefs(prefs);
    } catch (e) {}
}

// Слайдерите извикват setPref директно с числовата стойност, плюс
// обновяват веднага живото число до заглавието (без да чакат сървъра)
function onSliderInput(key, value, labelId) {
    document.getElementById(labelId).textContent = value;
    setPref(key, parseInt(value, 10));
}

(async function loadPrefs() {
    try {
        const res = await fetch('/api/test-preferences');
        const prefs = await res.json();
        window._testPrefs = prefs;
        applyPrefs(prefs);
    } catch (e) {}
})();

function toggleLightbox(src) {
    const modal = document.getElementById('imgModal');
    const modalImg = document.getElementById('modalImg');
    if (modal.style.display === 'inline-block') { modal.style.display = 'none'; return; }
    modalImg.src = src;
    modal.style.display = 'inline-block';
    modalImg.onload = function() {
        modalImg.style.width = Math.round(modalImg.naturalWidth * 1.78) + 'px';
        modalImg.style.height = 'auto';
    };
}
function closeImgModal() { document.getElementById('imgModal').style.display = 'none'; }
document.addEventListener('keydown', function(e) { if(e.key==='Escape') closeImgModal(); });
let isDragging=false,dragOffsetX=0,dragOffsetY=0;
function dragStart(e) {
    if(e.target.tagName==='BUTTON'||e.target.tagName==='IMG') return;
    isDragging=true;
    const r=document.getElementById('imgModal').getBoundingClientRect();
    dragOffsetX=e.clientX-r.left; dragOffsetY=e.clientY-r.top;
    document.addEventListener('mousemove',dragMove);
    document.addEventListener('mouseup',dragEnd);
}
function dragMove(e) {
    if(!isDragging) return;
    const m=document.getElementById('imgModal');
    m.style.left=(e.clientX-dragOffsetX)+'px';
    m.style.top=(e.clientY-dragOffsetY)+'px';
    m.style.right='auto';
}
function dragEnd(){isDragging=false;document.removeEventListener('mousemove',dragMove);document.removeEventListener('mouseup',dragEnd);}
