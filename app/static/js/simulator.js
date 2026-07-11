// Simulator страница - извлечена логика (виж app/templates/user/simulator.html за window.SIMULATOR_DATA)

document.addEventListener('DOMContentLoaded', function () {
    const area = document.getElementById('simContent');
    if (!area) return;
    ['copy', 'cut', 'contextmenu'].forEach(function (evt) {
        area.addEventListener(evt, function (e) { e.preventDefault(); });
    });
});

// ==== НАСТРОЙКИ ЗА ЧЕТЕНЕ (слайдери 0-10 + отделни шрифтове) - вижте
// същата логика в user/test.html ====
function togglePrefsPanel(btnId) {
    const p = document.getElementById('prefsPanel');
    const wasOpen = p.style.display === 'block';
    if (wasOpen) { p.style.display = 'none'; return; }
    // Панелът е единствен, споделен елемент - позиционираме го спрямо
    // РЕАЛНО кликнатия бутон (prefsBtn при решаване, frPrefsBtn в review
    // екрана на симулатора - двата бутона живеят в различни DOM разклонения,
    // затова position:absolute спрямо родителя не работи еднакво и за двата).
    const btn = document.getElementById(btnId || 'prefsBtn');
    const r = btn.getBoundingClientRect();
    p.style.position = 'fixed';
    p.style.top = (r.bottom + 8) + 'px';
    p.style.right = (window.innerWidth - r.right) + 'px';
    p.style.left = 'auto';
    p.style.display = 'block';
}
document.addEventListener('click', function(e) {
    const panel = document.getElementById('prefsPanel');
    if (!panel || panel.style.display !== 'block') return;
    const btn1 = document.getElementById('prefsBtn');
    const btn2 = document.getElementById('frPrefsBtn');
    const onBtn = (btn1 && (e.target === btn1 || btn1.contains(e.target)))
               || (btn2 && (e.target === btn2 || btn2.contains(e.target)));
    if (!panel.contains(e.target) && !onBtn) {
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
    const el = document.getElementById('simContent');
    if (!el) return;
    el.dataset.theme = prefs.theme || 'dark';
    // Синхронизираме темата и с fullReview (отделен DOM branch, виж
    // коментара в togglePrefsPanel() по-горе).
    const frEl = document.getElementById('fullReview');
    if (frEl) frEl.dataset.theme = prefs.theme || 'dark';

    // Яркост на фона - CSS filter:brightness() върху ЦЯЛАТА страница
    // (не само #qBox), работи с всяка от 4-те теми едновременно. 0-10
    // слайдер -> 0.7-1.3 filter стойност (5 = 1.0 = без промяна). Не
    // ползваме по-широк диапазон - твърде тъмно/светло прави текста
    // нечетим, каквото и да е дадено brightness() не пипа контраста.
    const brLevel = prefs.bg_brightness !== undefined ? prefs.bg_brightness : 5;
    const brFilter = (0.7 + (brLevel / 10) * 0.6).toFixed(2);
    el.style.filter = `brightness(${brFilter})`;
    if (frEl) frEl.style.filter = `brightness(${brFilter})`;
    const brSliderEl = document.getElementById('brSlider');
    const brValEl = document.getElementById('brVal');
    if (brSliderEl) brSliderEl.value = brLevel;
    if (brValEl) brValEl.textContent = brLevel;

    const qSize = prefs.q_font_size !== undefined ? prefs.q_font_size : 5;
    const aSize = prefs.a_font_size !== undefined ? prefs.a_font_size : 5;
    const hi = prefs.highlight_intensity !== undefined ? prefs.highlight_intensity : 5;
    // Пазим глобално - renderQuestion() чете тази стойност при всяко
    // построяване на отговорите, за да изчисли яркостта на избрания ред.
    window._highlightIntensity = hi;
    const qPx = 12 + qSize * 2;
    const aPx = 12 + aSize * 2;
    const qFont = FONT_STACKS[prefs.q_font_family || 'default'];
    const aFont = FONT_STACKS[prefs.a_font_family || 'default'];
    const qBold = prefs.q_bold !== undefined ? prefs.q_bold : true;
    const aBold = prefs.a_bold !== undefined ? prefs.a_bold : false;
    const qWeight = qBold ? '700' : '400';
    const aWeight = aBold ? '700' : '500';

    // Общ 'Font Weight' слайдер (0-10) - НЕЗАВИСИМ от Bold бутоните на
    // въпрос/отговор по-долу. На стойност 5 (default, недокоснат) НЕ
    // override-ва нищо - пази старото поведение за всеки, който не го е
    // пипал. Само при реално местене на слайдера, override-ва двете
    // (въпрос+отговор) с ЕДНА обща дебелина (300-900), последно правило
    // в CSS каскадата печели над qWeight/aWeight по-горе.
    const fw = prefs.font_weight !== undefined ? prefs.font_weight : 5;
    const fwOverride = fw !== 5;
    const fwValue = 300 + fw * 60;
    document.getElementById('fwSlider').value = fw;
    document.getElementById('fwVal').textContent = fw;

    let styleEl = document.getElementById('dynamicPrefsStyle');
    if (!styleEl) {
        styleEl = document.createElement('style');
        styleEl.id = 'dynamicPrefsStyle';
        document.head.appendChild(styleEl);
    }
    styleEl.textContent = `
        #simContent #qBox p, #simContent #qText { font-size: ${qPx}px !important; font-family: ${qFont} !important; font-weight: ${qWeight} !important; }
        #simContent #answersContainer button span:last-child { font-size: ${aPx}px !important; font-family: ${aFont} !important; font-weight: ${aWeight} !important; }
        #simContent #answersContainer button span:first-child { font-family: ${aFont} !important; }
        #fullReview .qbox_review p { font-size: ${qPx}px !important; font-family: ${qFont} !important; font-weight: ${qWeight} !important; }
        #fullReview .opt-label span:last-child { font-size: ${aPx}px !important; font-family: ${aFont} !important; font-weight: ${aWeight} !important; }
        #fullReview .opt-label.is-correct { background: rgba(16,185,129,${(0.02 + (hi / 10) * 0.28).toFixed(3)}) !important; }
        #fullReview .opt-label.is-wrong { background: rgba(244,63,94,${(0.02 + (hi / 10) * 0.28).toFixed(3)}) !important; }
        ${fwOverride ? `
        #simContent #qBox p, #simContent #qText, #simContent #answersContainer button span:last-child,
        #fullReview .qbox_review p, #fullReview .opt-label span:last-child { font-weight: ${fwValue} !important; }
        ` : ''}
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

    // Ако вече има изобразени отговори, преизчертай ги веднага с новата
    // интензивност (без да чакаш следваща смяна на въпрос)
    if (typeof currentIdx !== 'undefined' && questions[currentIdx]) renderQuestion(currentIdx);
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
// стойностите по подразбиране (сървърът пази какви точно са те - виж
// /api/test-preferences, reset:true клона).
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

// ==== ДИНАМИЧНА ШИРИНА НА КАРТАТА (спрямо РЕАЛНАТА ширина на монитора,
// не фиксирани пиксели) - потребителят поиска кодът да ЧЕТЕ ширината на
// екрана и от там да смята нужната ширина, вместо hardcode-нато число.
// Съотношението 42% е избрано на база 807px/1920px (Full HD) - запазено
// като процент, така изгледа остава пропорционален на ВСЯКА резолюция.
// min/max границите пазят картата четима на много малки/много големи
// монитори (напр. телефон или 4K).
function applyResponsiveCardWidth() {
    const wrap = document.getElementById('questionCardWrap');
    if (!wrap) return;
    const screenWidth = window.innerWidth;
    // +10% по искане - при по-дълги отговори (3-4 реда всеки) картата
    // понякога се отрязваше на долу към бутоните (Back/Continue/End Exam) -
    // по-широка карта = по-къси редове = по-малко вертикално препъляне.
    let target = screenWidth * 0.462;
    target = Math.max(462, Math.min(1100, target));  // не по-тясно от 462px, не по-широко от 1100px
    wrap.style.maxWidth = target + 'px';
}
applyResponsiveCardWidth();
window.addEventListener('resize', applyResponsiveCardWidth);

const testId = window.SIMULATOR_DATA.testId;
const isDemo = window.SIMULATOR_DATA.isDemo;
const totalQuestions = window.SIMULATOR_DATA.totalQuestions;
const questions = window.SIMULATOR_DATA.questions;
const answers = {};  // { qId: oIdx }
let currentIdx = 0;
let timerInterval = null;
let secondsLeft = 60 * 60; // 60 минути
let examFinished = false;
let _lastScore = 0, _lastTotal = 0, _lastPercent = 0;

// Fade in
document.addEventListener('DOMContentLoaded', function() {
    setTimeout(() => {
        document.getElementById('simContent').style.opacity = '1';
    }, 50);
    renderQuestion(0);
    startTimer();
    buildDots();
});

// ============================================================
// ТАЙМЕР
// ============================================================
function startTimer() {
    timerInterval = setInterval(() => {
        secondsLeft--;
        updateTimerDisplay();
        if (secondsLeft <= 0) {
            clearInterval(timerInterval);
            finishExam();
        }
    }, 1000);
}

function updateTimerDisplay() {
    const m = Math.floor(secondsLeft / 60);
    const s = secondsLeft % 60;
    const display = `${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
    const el = document.getElementById('timerDisplay');
    el.textContent = display;
    // Червен таймер при < 5 минути
    if (secondsLeft <= 300) {
        el.className = 'text-[14px] font-black text-red-400 font-mono animate-pulse';
    }
}

// ============================================================
// РЕНДЕРИРАНЕ НА ВЪПРОС
// ============================================================
function preloadImage(idx) {
    if (idx >= 0 && idx < questions.length && questions[idx].image) {
        const img = new Image();
        img.src = questions[idx].image;
    }
}

const isFreePlanJs = window.SIMULATOR_DATA.isFreePlanJs;
const dismissedAdSlots = new Set();

// Фиксиран списък от индексите на рекламните слотове (независимо дали са
// били "dismiss-нати" или не) - рекламата НЕ Е въпрос и не трябва да се
// брои като "неотговорен" при проверка дали изпитът е завършен.
const adSlotIndices = new Set();
for (let i = 0; i < totalQuestions; i++) {
    const loopIndex = i + 1;
    if (isFreePlanJs && loopIndex > 1 && loopIndex % 10 === 1) adSlotIndices.add(i);
}

function shouldShowAdSlot(idx) {
    const loopIndex = idx + 1;
    return isFreePlanJs && loopIndex > 1 && loopIndex % 10 === 1 && !dismissedAdSlots.has(idx);
}

async function loadAdInterstitialContent() {
    try {
        const res = await fetch('/api/random-ad');
        const data = await res.json();
        if (!data.ad) return;
        const ad = data.ad;
        const body = document.getElementById('adInterstitialBody');
        const imgHtml = ad.image_url ? `<img src="${ad.image_url}" style="max-width:100%;max-height:120px;border-radius:8px;margin-bottom:10px">` : '';
        const linkOpen = ad.link_url ? `<a href="${ad.link_url}" target="_blank" rel="noopener" onclick="fetch('/api/ad-click/${ad.id}',{method:'POST'})" style="text-decoration:none;color:inherit">` : '<div>';
        const linkClose = ad.link_url ? '</a>' : '</div>';
        body.innerHTML = `${linkOpen}${imgHtml}<p style="font-size:16px;font-weight:700;color:#E8A020;margin-bottom:6px">${ad.title}</p>${ad.body ? `<p style="font-size:13px;color:rgba(232,237,242,0.6)">${ad.body}</p>` : ''}${linkClose}`;
    } catch (e) {}
}

function dismissAdInterstitial() {
    dismissedAdSlots.add(currentIdx);
    document.getElementById('adInterstitial').style.display = 'none';
    document.getElementById('qBox').style.display = '';
    document.getElementById('navRow').style.display = '';
    document.getElementById('finishWrap').style.display = 'block';
}

function renderQuestion(idx) {
    currentIdx = idx;

    // Ресетваме скрола на 0 при всяка нова карта (въпрос ИЛИ реклама) - иначе
    // ако предишният въпрос е бил дълъг и потребителят е скролнал надолу,
    // следващата карта (включително рекламата) се появява на различно
    // разстояние от хедъра всеки път, вместо на едно и също фиксирано място.
    const mainEl = document.getElementById('simMain');
    if (mainEl) mainEl.scrollTop = 0;

    if (shouldShowAdSlot(idx)) {
        document.getElementById('adInterstitial').style.display = 'flex';
        document.getElementById('qBox').style.display = 'none';
        loadAdInterstitialContent();
        document.getElementById('questionCounter').textContent = `${idx + 1} / ${totalQuestions}`;
        return;
    }
    document.getElementById('adInterstitial').style.display = 'none';
    document.getElementById('qBox').style.display = '';

    const q = questions[idx];

    document.getElementById('qNumber').textContent = `${idx + 1}.`;
    document.getElementById('qId').textContent = `#${q.id}`;
    document.getElementById('qText').textContent = q.question;
    document.getElementById('questionCounter').textContent = `${idx + 1} / ${totalQuestions}`;

    // Progress бар
    const pct = ((idx) / totalQuestions) * 100;
    document.getElementById('progressBar').style.width = pct + '%';

    // Снимка (ако има)
    const imgWrap = document.getElementById('qImageWrap');
    if (q.image) {
        document.getElementById('qImage').src = q.image;
        imgWrap.classList.remove('hidden');
    } else {
        imgWrap.classList.add('hidden');
    }
    // Preload next and previous question images
    preloadImage(idx + 1);
    preloadImage(idx - 1);

    // Отговори
    const container = document.getElementById('answersContainer');
    container.innerHTML = '';
    const selectedOIdx = answers[q.id];

    q.options.forEach((opt, oIdx) => {
        const isSelected = selectedOIdx === oIdx;
        const btn = document.createElement('button');
        // На тъмен фон (#0B132B) дори "деликатен" полупрозрачен пастел
        // изглежда неестествено ярко/странно (силен контраст near-black
        // vs light lavender overlay). Затова: редa е ОЩЕ по-блед
        // (0.16 -> 0.08 opacity), а буквата е ПЛЪТЕН приглушен цвят
        // (не прозрачност) - чете се ясно като бадж, без да е неонов.
        // Интензитетът на реда (0-10, слайдер 'Answer Highlight Intensity')
        // мапва към opacity диапазон 0.02-0.30 - потребителят може сам да
        // регулира яркостта, вместо фиксирана стойност.
        const hi = window._highlightIntensity !== undefined ? window._highlightIntensity : 5;
        const rowOpacity = (0.02 + (hi / 10) * 0.28).toFixed(3);
        // На Light/Sepia бледият виолет почти не се вижда на светъл фон,
        // а бял текст върху него е нечетим - за тези 2 теми ползваме
        // топъл кехлибарен акцент (съвпада с топлата им палитра) и
        // ТЪМЕН текст вместо бял.
        const theme = (document.getElementById('simContent') || {}).dataset ? document.getElementById('simContent').dataset.theme : 'dark';
        const isLightish = theme === 'light' || theme === 'sepia' || theme === 'ink';
        const selectedBg = isLightish ? `rgba(180,83,9,${rowOpacity})` : `rgba(167,139,250,${rowOpacity})`;
        const selectedTextColor = isLightish ? (theme === 'sepia' || theme === 'ink' ? '#4a3c28' : '#3d2c1a') : '#ffffff';
        const selectedLetterColor = isLightish ? '#b45309' : '#8b5cf6';
        btn.className = `w-full flex items-center gap-4 rounded-xl p-4 text-[15px] font-medium transition text-left
            ${isSelected ? 'font-bold' : 'bg-[#1C2541]/40 text-slate-300 hover:bg-[#1C2541]/70'}`;
        if (isSelected) {
            btn.style.setProperty('background', selectedBg, 'important');
            btn.style.setProperty('color', selectedTextColor, 'important');
        }
        btn.onclick = () => selectAnswer(q.id, oIdx);
        btn.innerHTML = `
            <span class="flex items-center justify-center text-[17px] font-black shrink-0"
                style="width:28px;${isSelected ? `color:${selectedLetterColor}` : ''}">
                ${opt.letter.toUpperCase()}
            </span>
            <span>${opt.text}</span>
        `;
        container.appendChild(btn);
    });

    // Бутони
    document.getElementById('btnBack').style.visibility = idx === 0 ? 'hidden' : 'visible';

    // Continue/Back остават ВИНАГИ видими - дори на последния въпрос,
    // клиентът може да иска да се върне назад и да прегледа отговорите си.
    // END EXAM се показва ДОПЪЛНИТЕЛНО на последния въпрос, не вместо
    // Continue бутона (nextQuestion() вече е безобиден no-op на последния
    // въпрос - currentIdx < totalQuestions-1 проверката просто не прави нищо).
    document.getElementById('btnNext').style.display = 'flex';
    
    // END EXAM бутонът е ВИНАГИ видим (на постоянното си място), но стилът
    // му се сменя динамично: блед (като заключения Mistakes бутон в
    // картата), докато НЕ всички въпроси са отговорени; зелен/активен,
    // само щом ВСИЧКИ (без рекламните слотове) са отговорени - НЕ просто
    // защото потребителят е стигнал до последния въпрос (предишно
    // поведение, поправено - бутонът светваше подвеждащо на #45, дори с
    // неотговорени по-рано въпроси).
    const finishBtn = document.getElementById('finishExamBtn');
    const answerableTotal = totalQuestions - adSlotIndices.size;
    const allAnswered = Object.keys(answers).length >= answerableTotal;
    if (allAnswered) {
        finishBtn.className = 'bg-emerald-500 hover:bg-emerald-400 text-[#0B132B] font-black py-3 px-10 rounded-xl text-[13px] uppercase tracking-wider transition shadow-md cursor-pointer';
        finishBtn.style.cssText = '';
    } else {
        finishBtn.className = 'font-black py-3 px-10 rounded-xl text-[13px] uppercase tracking-wider transition cursor-not-allowed';
        finishBtn.style.cssText = 'background:rgba(16,185,129,0.05);color:rgba(52,211,153,0.3);border:1px solid rgba(16,185,129,0.1)';
    }

    updateDots();
}

// ============================================================
// ИЗБОР НА OFГОВОР
// ============================================================
function selectAnswer(qId, oIdx) {
    answers[qId] = oIdx;
    renderQuestion(currentIdx);
    updateDots();
}

// ============================================================
// НАВИГАЦИЯ
// ============================================================
function nextQuestion() {
    if (currentIdx < totalQuestions - 1) renderQuestion(currentIdx + 1);
}
function prevQuestion() {
    if (currentIdx > 0) renderQuestion(currentIdx - 1);
}

// ============================================================
// ТОЧКИ ИНДИКАТОРИ
// ============================================================
function buildDots() {
    const container = document.getElementById('dotIndicators');
    container.innerHTML = '';
    questions.forEach((q, idx) => {
        if (adSlotIndices.has(idx)) return;
        const dot = document.createElement('button');
        dot.id = `dot_${idx}`;
        dot.className = 'w-2 h-2 rounded-full bg-slate-700 transition';
        dot.onclick = () => renderQuestion(idx);
        container.appendChild(dot);
    });
}

function updateDots() {
    questions.forEach((q, idx) => {
        const dot = document.getElementById(`dot_${idx}`);
        if (!dot) return;
        if (idx === currentIdx) {
            dot.className = 'w-2.5 h-2.5 rounded-full dot-current transition';
        } else if (answers[q.id] !== undefined) {
            dot.className = 'w-2 h-2 rounded-full bg-emerald-400 transition';
        } else {
            dot.className = 'w-2 h-2 rounded-full bg-slate-700 transition';
        }
    });
}

// ============================================================
// ЗАВЪРШВАНЕ
// ============================================================
async function finishExam() {
    if (examFinished) return;

    const answerableTotal = totalQuestions - adSlotIndices.size;
    const unanswered = answerableTotal - Object.keys(answers).length;
    if (unanswered > 0) {
        // Намери първия неотговорен въпрос и навигирай директно до него -
        // симулаторът показва по 1 въпрос наведнъж (не скролваща страница
        // като обикновения тест), затова тук "отиване до въпроса" означава
        // renderQuestion(idx), не scrollIntoView. Прескачаме рекламните
        // слотове - те не са въпроси и не се броят.
        let firstUnansweredIdx = -1;
        for (let i = 0; i < questions.length; i++) {
            if (adSlotIndices.has(i)) continue;
            if (answers[questions[i].id] === undefined) {
                firstUnansweredIdx = i;
                break;
            }
        }
        if (firstUnansweredIdx !== -1) {
            renderQuestion(firstUnansweredIdx);
            const box = document.getElementById('qBox');
            if (box) {
                box.style.transition = 'box-shadow 0.3s ease';
                box.style.boxShadow = '0 0 0 1px rgba(232,160,32,0.25)';
                setTimeout(() => { box.style.boxShadow = 'none'; }, 2000);
            }
        }
        return;
    }

    examFinished = true;
    clearInterval(timerInterval);

    try {
        // Конвертирай answers към string ключове
        const answersPayload = {};
        Object.entries(answers).forEach(([k, v]) => { answersPayload[String(k)] = v; });

        // ID-тата на РЕАЛНИТЕ въпроси (без рекламните слотове - те не са
        // въпроси и не бива да участват в total/score изчислението никъде,
        // нито на клиента, нито на сървъра).
        const questionIds = questions.filter((q, i) => !adSlotIndices.has(i)).map(q => q.id);

        const duration = (60 * 60) - secondsLeft;

        const submitUrl = isDemo ? `/demo/test/${testId}/submit` : `/test/${testId}/submit`;
        const res = await fetch(submitUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                answers: answersPayload, 
                test_type: 'simulator',
                question_ids: questionIds,
                duration: duration
            })
        });
        if (!res.ok) {
            let errText = '';
            try { errText = await res.text(); } catch (_) {}
            throw new Error(`HTTP ${res.status}: ${errText.slice(0, 300)}`);
        }
        const data = await res.json();

        if (data.error) {
            examFinished = false;
            alert(data.message || 'Възникна грешка при предаването на теста. Опитайте пак.');
            return;
        }

        const answered = Object.keys(answers).length;
        const wrong = answered - data.score;
        const skipped = answerableTotal - answered;
        const timeUsed = (60 * 60 - secondsLeft);
        const mUsed = Math.floor(timeUsed / 60);
        const sUsed = timeUsed % 60;

        // Изпитът се смята за положен само при >=90% верни (или <=10% грешни) -
        // взимаме РЕШЕНИЕТО директно от сървъра (data.passed), който вече
        // изчислява това коректно в submit_test(). ПОПРАВКА НА БЪГ: преди
        // тук имаше отделна клиентска формула ("wrong < 6"), която грешно
        // показваше "ПОЛОЖЕН!" дори при 50% грешни отговори (напр. 3 грешни
        // от 10 = 70% -> показваше PASSED вместо FAILED).
        const examPassed = data.passed;

        const icon = document.getElementById('resultIcon');
        const title = document.getElementById('resultTitle');
        if (examPassed) {
            icon.className = 'w-16 h-16 rounded-2xl flex items-center justify-center text-3xl mx-auto bg-emerald-500/20 border border-emerald-500/30';
            icon.innerHTML = '<i class="fa-solid fa-trophy text-emerald-400"></i>';
            title.textContent = 'ПОЛОЖЕН!';
            title.className = 'text-xl font-black text-emerald-400';
        } else {
            icon.className = 'w-16 h-16 rounded-2xl flex items-center justify-center text-3xl mx-auto bg-red-500/20 border border-red-500/30';
            icon.innerHTML = '<i class="fa-solid fa-anchor text-red-400"></i>';
            title.textContent = 'FAILED';
            title.className = 'text-xl font-black text-red-400';
        }

        document.getElementById('resultScore').innerHTML =
            `<span class="${examPassed ? 'text-emerald-400' : 'text-red-400'}">${data.percent}%</span>`;

        document.getElementById('resultStats').innerHTML = `
            <p>Answered: <b class="text-white">${answered}</b> от <b class="text-white">${answerableTotal}</b></p>
            <p>
                <span class="text-emerald-400 font-bold">✓ Correct: ${data.score}</span> &nbsp;|&nbsp;
                <span class="text-red-400 font-bold">✗ Грешни: ${wrong}</span> &nbsp;|&nbsp;
                <span class="text-slate-500">Пропуснати: ${skipped}</span>
            </p>
            <p class="text-slate-500">Времe: ${String(mUsed).padStart(2,'0')}:${String(sUsed).padStart(2,'0')} минути</p>
            <p class="text-[10px] text-slate-600 mt-1">Minimum 90% to pass</p>
        `;

        if (isDemo) {
            _lastScore = data.score; _lastTotal = totalQuestions; _lastPercent = data.percent;
            showSubscribePopup(data.score, totalQuestions, data.percent);
            return;
        }
        document.getElementById('resultModal').classList.remove('hidden');
    } catch(e) {
        examFinished = false;
        if (isDemo) {
            showSubscribePopup();
        } else {
            alert('Грешка при предаване на теста: ' + (e && e.message ? e.message : e) + '\n\nМоля, копирай това съобщение и го изпрати за диагностика.');
        }
    }
}

function showSubscribePopup(score, total, percent) {
    score = score || 0; total = total || totalQuestions; percent = percent || 0;
    const circumference = 2 * Math.PI * 26; // r=26
    const offset = circumference - (percent / 100) * circumference;

    const overlay = document.createElement('div');
    overlay.id = 'subscribePopup';
    overlay.style.cssText = 'position:fixed;inset:0;z-index:99999;background:rgba(0,0,0,0.6);backdrop-filter:blur(6px);display:flex;align-items:center;justify-content:center';
    overlay.innerHTML = `
        <div style="background:#fff;border-radius:20px;padding:32px;max-width:380px;width:90%;box-shadow:0 30px 80px rgba(0,0,0,0.4);position:relative">
            <button onclick="document.getElementById('subscribePopup').remove()" style="position:absolute;top:14px;right:14px;background:none;border:none;color:#94a3b8;font-size:20px;cursor:pointer;line-height:1;padding:4px">✕</button>
            <div style="display:flex;align-items:center;justify-content:space-between;gap:16px">
                <div>
                    <p style="color:#0B132B;font-size:15px;font-weight:800;margin:0 0 4px;letter-spacing:0.02em">YOUR RESULT:</p>
                    <p style="color:#0B132B;font-size:15px;font-weight:800;margin:0">${score} OF ${total} CORRECT</p>
                </div>
                <div style="position:relative;width:64px;height:64px;flex-shrink:0">
                    <svg width="64" height="64" viewBox="0 0 64 64" style="transform:rotate(-90deg)">
                        <circle cx="32" cy="32" r="26" fill="none" stroke="#e2e8f0" stroke-width="6"/>
                        <circle cx="32" cy="32" r="26" fill="none" stroke="#6c5ce7" stroke-width="6"
                            stroke-dasharray="${circumference}" stroke-dashoffset="${offset}" stroke-linecap="round"/>
                    </svg>
                    <div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:800;color:#0B132B">${percent}%</div>
                </div>
            </div>
            <p style="color:#64748b;font-size:13px;line-height:1.6;margin:16px 0 20px">За да отключите всички функции и тестове които дава възможност платформата, изберете своят абонамент.</p>
            <a href="/register" style="background:#6c5ce7;color:#fff;border:none;border-radius:10px;padding:13px 24px;font-size:14px;font-weight:700;text-decoration:none;display:block;text-align:center;letter-spacing:0.05em">
                ИЗБЕРИ АБОНАМЕНТ
            </a>
            <div style="text-align:center;margin-top:12px">
                <button onclick="document.getElementById('subscribePopup').remove()" style="background:none;border:none;color:#94a3b8;font-size:12px;cursor:pointer;text-decoration:underline">Затвори</button>
            </div>
        </div>`;
    document.body.appendChild(overlay);
    overlay.addEventListener('click', function(e) {
        if (e.target === overlay) overlay.remove();
    });
}

function reviewAnswers() {
    document.getElementById('resultModal').classList.add('hidden');
    // Скрий симулатор view, покажи пълен преглед
    document.getElementById('simContent').style.display = 'none';
    document.getElementById('fullReview').style.display = 'block';

    const container = document.getElementById('fullReviewContainer');
    container.innerHTML = '';

    questions.forEach((q, idx) => {
        const selectedOIdx = answers[q.id];
        const isAnswered = selectedOIdx !== undefined;
        const isCorrect = isAnswered && q.options[selectedOIdx].isCorrect;

        const box = document.createElement('div');
        box.className = `qbox_review bg-[#0B132B] border rounded-xl p-4 space-y-2 ${!isAnswered ? 'border-slate-700/20' : isCorrect ? 'border-slate-700/30' : 'border-red-500/20'}`;

        const imgHtml = q.image ? `
            <div class="mt-2 mb-2">
                <img src="${q.image}" style="max-height:160px;width:auto;border-radius:8px;cursor:pointer;display:block"
                     onclick="toggleLightbox(this.src)">
            </div>` : '';

        let html = `
            <div class="flex items-start justify-between gap-2">
                <p class="text-[13px] font-bold text-white leading-relaxed flex-1">
                    <span class="text-purple-400 mr-1">${idx + 1}.</span>
                    <span class="text-slate-600 text-[10px] mr-1">#${q.id}</span>
                    ${q.question}
                </p>
                ${!isAnswered
                    ? '<span class="bg-slate-700/50 text-slate-400 border border-slate-600/30 px-1.5 py-0.5 rounded text-[8px] font-bold uppercase shrink-0">Skipped</span>'
                    : ''
                }
            </div>
            <div class="space-y-1">
        `;

        q.options.forEach((opt, oIdx) => {
            const isSel = isAnswered && selectedOIdx === oIdx;
            const isCorr = opt.isCorrect;
            let cls = 'opt-label flex items-center gap-2 px-3 py-2 rounded-lg text-[12px] border ';
            let borderStyle = '';
            if (isCorr && isSel) { cls += 'is-correct text-emerald-300 font-bold'; borderStyle = 'border-color:rgba(16,185,129,0.12)'; }
            else if (isCorr) { cls += 'is-correct text-emerald-500 font-bold'; borderStyle = 'border-color:rgba(16,185,129,0.12)'; }
            else if (isSel) { cls += 'is-wrong text-red-400'; borderStyle = 'border-color:rgba(244,63,94,0.12)'; }
            else cls += 'is-neutral text-slate-500';

            html += `<div class="${cls}" style="${borderStyle}">
                <span class="font-black text-[10px] w-5 shrink-0">${opt.letter.toUpperCase()})</span>
                <span>${opt.text}</span>
                ${isCorr ? '<i class="fa-solid fa-check text-[9px] ml-auto text-emerald-400"></i>' : ''}
                ${isSel && !isCorr ? '<i class="fa-solid fa-xmark text-[9px] ml-auto text-red-400"></i>' : ''}
            </div>`;
        });

        html += '</div>';
        box.innerHTML = imgHtml + html;
        container.appendChild(box);
    });
}

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

// Клавиши A/(←) = Back, D/(→) = Continue - само докато решаваш теста
// (не докато пишеш в поле за текст, ако някога има такова на страницата).
document.addEventListener('keydown', function(e) {
    const tag = (e.target && e.target.tagName) || '';
    if (tag === 'INPUT' || tag === 'TEXTAREA') return;
    if (examFinished) return;
    // e.code = физическата позиция на клавиша (KeyA/KeyD/ArrowLeft/ArrowRight),
    // независимо от активната клавиатурна подредба (латиница/кирилица).
    // e.key връща различен символ на кирилица ('а' кирилица != 'a' латиница),
    // затова НЕ го ползваме тук - иначе бутоните не работят при БГ подредба.
    if (e.code === 'KeyA' || e.code === 'ArrowLeft') {
        e.preventDefault();
        prevQuestion();
    } else if (e.code === 'KeyD' || e.code === 'ArrowRight') {
        e.preventDefault();
        nextQuestion();
    }
});
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
