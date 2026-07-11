// ==== СПОДЕЛЕН МОДУЛ: Настройки за четене (font size / theme / font family /
// highlight intensity / background brightness / font weight) ====
// Ползва се от simulator.html, test.html (Test/Mix/Mistakes) и
// result_review.html (/result/<id>) - преди тази промяна всеки от трите
// имаше СОБСТВЕНО, почти дублирано копие на тази логика (виж git история
// за конкретните бъгове, поправяни поотделно във всяко копие - причината
// да се обединят в 1 файл: 1 поправка вече работи навсякъде).
//
// ВАЖНО за реда на <script> таговете: този файл трябва да се зарежда
// СЛЕД page-specific скрипта (simulator.js/test.js/result_review.js) в
// HTML-а - loadPrefs() по-долу автоматично вика applyPrefs() веднага щом
// файлът се изпълни, а applyPrefs() извиква (ако съществува)
// window.onPrefsApplied(prefs) - page-specific hook, дефиниран в
// simulator.js/test.js, за екранно-специфични довършителни действия
// (напр. renderQuestion() в симулатора, highlightSelected() в test.js).
// Ако reading-prefs.js се зареди ПРЕДИ page-specific скрипта, hook-ът
// още няма да съществува в момента на 1-вото извикване - затова редът
// на <script> таговете има значение.
//
// ВАЖНО за DOM съвместимост: applyPrefs() генерира CSS правила и за
// ДВАТА établished DOM patern-а в проекта:
//   - "Simulator pattern": #simContent (+ #fullReview) с #qBox/#answersContainer
//   - "List pattern": #mainContent с [id^="qbox_"]/.opt-label (test.html,
//     result_review.html, история feature - list от много въпроси наведнъж)
// CSS селектори, които не съвпадат с нищо на текущата страница, са
// напълно безобидни no-op правила - затова е безопасно да се генерират
// и двата пattern-а винаги, вместо да се "гадае" в кой режим сме.

function togglePrefsPanel(btnId) {
    const p = document.getElementById('prefsPanel');
    const wasOpen = p.style.display === 'block';
    if (wasOpen) { p.style.display = 'none'; return; }
    // Панелът е единствен, споделен елемент - позиционираме го спрямо
    // РЕАЛНО кликнатия бутон (различни страници/екрани може да имат
    // повече от един бутон, отварящ същия панел - напр. симулаторовия
    // #fullReview има собствен frPrefsBtn, различен от prefsBtn).
    const btn = document.getElementById(btnId || 'prefsBtn');
    if (!btn) { p.style.display = 'block'; return; }
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
    // Темата (data-theme) и яркостта (filter:brightness) се прилагат на
    // ВСЕКИ от възможните root контейнери, които реално съществуват на
    // текущата страница - #simContent/#fullReview (simulator pattern) или
    // #mainContent (list pattern). getElementById връща null безобидно,
    // ако елементът липсва на тази страница.
    const theme = prefs.theme || 'dark';
    const roots = ['simContent', 'fullReview', 'mainContent']
        .map(id => document.getElementById(id))
        .filter(Boolean);
    if (roots.length === 0) return;  // страницата изобщо няма Reading Settings контейнер

    const brLevel = prefs.bg_brightness !== undefined ? prefs.bg_brightness : 5;
    const brFilter = (0.7 + (brLevel / 10) * 0.6).toFixed(2);
    roots.forEach(el => {
        el.dataset.theme = theme;
        el.style.filter = `brightness(${brFilter})`;
    });
    const brSliderEl = document.getElementById('brSlider');
    const brValEl = document.getElementById('brVal');
    if (brSliderEl) brSliderEl.value = brLevel;
    if (brValEl) brValEl.textContent = brLevel;

    const qSize = prefs.q_font_size !== undefined ? prefs.q_font_size : 5;
    const aSize = prefs.a_font_size !== undefined ? prefs.a_font_size : 5;
    const hi = prefs.highlight_intensity !== undefined ? prefs.highlight_intensity : 5;
    // Пазим глобално - highlightSelected()/renderQuestion() (page-specific)
    // четат тази стойност при построяване на избрания отговор.
    window._highlightIntensity = hi;
    const rowOpacity = (0.02 + (hi / 10) * 0.28).toFixed(3);
    const qPx = 12 + qSize * 2;
    const aPx = 12 + aSize * 2;
    const qFont = FONT_STACKS[prefs.q_font_family || 'default'];
    const aFont = FONT_STACKS[prefs.a_font_family || 'default'];
    const qBold = prefs.q_bold !== undefined ? prefs.q_bold : true;
    const aBold = prefs.a_bold !== undefined ? prefs.a_bold : false;
    const qWeight = qBold ? '700' : '400';
    const aWeight = aBold ? '700' : '500';

    // Общ 'Font Weight' слайдер (0-10) - НЕЗАВИСИМ от Bold бутоните.
    // На стойност 5 (default, недокоснат) НЕ override-ва нищо - пази
    // старото поведение за всеки, който не го е пипал.
    const fw = prefs.font_weight !== undefined ? prefs.font_weight : 5;
    const fwOverride = fw !== 5;
    const fwValue = 300 + fw * 60;
    const fwSliderEl = document.getElementById('fwSlider');
    const fwValEl = document.getElementById('fwVal');
    if (fwSliderEl) fwSliderEl.value = fw;
    if (fwValEl) fwValEl.textContent = fw;

    let styleEl = document.getElementById('dynamicPrefsStyle');
    if (!styleEl) {
        styleEl = document.createElement('style');
        styleEl.id = 'dynamicPrefsStyle';
        document.head.appendChild(styleEl);
    }
    styleEl.textContent = `
        /* Simulator pattern */
        #simContent #qBox p, #simContent #qText { font-size: ${qPx}px !important; font-family: ${qFont} !important; font-weight: ${qWeight} !important; }
        #simContent #answersContainer button span:last-child { font-size: ${aPx}px !important; font-family: ${aFont} !important; font-weight: ${aWeight} !important; }
        #simContent #answersContainer button span:first-child { font-family: ${aFont} !important; }
        #fullReview .qbox_review p { font-size: ${qPx}px !important; font-family: ${qFont} !important; font-weight: ${qWeight} !important; }
        #fullReview .opt-label .opt-text { font-size: ${aPx}px !important; font-family: ${aFont} !important; font-weight: ${aWeight} !important; }
        #fullReview .opt-label.is-correct { background: rgba(16,185,129,${rowOpacity}) !important; }
        #fullReview .opt-label.is-wrong { background: rgba(244,63,94,${rowOpacity}) !important; }
        /* List pattern (test.html, result_review.html) */
        #mainContent [id^="qbox_"] > p { font-size: ${qPx}px !important; font-family: ${qFont} !important; font-weight: ${qWeight} !important; }
        #mainContent .opt-label span:last-child { font-size: ${aPx}px !important; font-family: ${aFont} !important; font-weight: ${aWeight} !important; }
        #mainContent .opt-label.is-correct { background: rgba(16,185,129,${rowOpacity}) !important; }
        #mainContent .opt-label.is-wrong { background: rgba(244,63,94,${rowOpacity}) !important; }
        ${fwOverride ? `
        #simContent #qBox p, #simContent #qText, #simContent #answersContainer button span:last-child,
        #fullReview .qbox_review p, #fullReview .opt-label .opt-text,
        #mainContent [id^="qbox_"] > p, #mainContent .opt-label span:last-child { font-weight: ${fwValue} !important; }
        ` : ''}
    `;

    const qSizeSlider = document.getElementById('qSizeSlider');
    const aSizeSlider = document.getElementById('aSizeSlider');
    const hiSlider = document.getElementById('hiSlider');
    if (qSizeSlider) qSizeSlider.value = qSize;
    if (aSizeSlider) aSizeSlider.value = aSize;
    if (hiSlider) hiSlider.value = hi;
    const qSizeVal = document.getElementById('qSizeVal');
    const aSizeVal = document.getElementById('aSizeVal');
    const hiVal = document.getElementById('hiVal');
    if (qSizeVal) qSizeVal.textContent = qSize;
    if (aSizeVal) aSizeVal.textContent = aSize;
    if (hiVal) hiVal.textContent = hi;
    const qFontSelect = document.getElementById('qFontFamilySelect');
    const aFontSelect = document.getElementById('aFontFamilySelect');
    if (qFontSelect) qFontSelect.value = prefs.q_font_family || 'default';
    if (aFontSelect) aFontSelect.value = prefs.a_font_family || 'default';

    const qBoldBtn = document.getElementById('qBoldBtn');
    const qBoldLabel = document.getElementById('qBoldLabel');
    if (qBoldBtn && qBoldLabel) {
        qBoldBtn.dataset.active = qBold;
        qBoldLabel.textContent = qBold ? 'On' : 'Off';
        qBoldBtn.style.background = qBold ? '#4CC9F0' : 'transparent';
        qBoldBtn.style.color = qBold ? '#0B132B' : '#94a3b8';
    }
    const aBoldBtn = document.getElementById('aBoldBtn');
    const aBoldLabel = document.getElementById('aBoldLabel');
    if (aBoldBtn && aBoldLabel) {
        aBoldBtn.dataset.active = aBold;
        aBoldLabel.textContent = aBold ? 'On' : 'Off';
        aBoldBtn.style.background = aBold ? '#4CC9F0' : 'transparent';
        aBoldBtn.style.color = aBold ? '#0B132B' : '#94a3b8';
    }

    document.querySelectorAll('.pref-opt-btn').forEach(function(b) {
        const active = b.dataset.prefBtn === 'theme' && b.dataset.prefVal === theme;
        b.style.background = active ? '#4CC9F0' : 'transparent';
        b.style.color = active ? '#0B132B' : '#94a3b8';
        b.style.borderColor = active ? '#4CC9F0' : 'rgba(255,255,255,0.15)';
    });

    // Page-specific довършителни действия (напр. симулаторът преизчертава
    // текущия въпрос, test.js преоцветява вече избрания отговор) - вижте
    // коментара в началото на файла за реда на <script> таговете.
    if (typeof window.onPrefsApplied === 'function') {
        window.onPrefsApplied(prefs);
    }
}

function toggleBold(key) {
    const current = window._testPrefs || {};
    const newVal = !(current[key] !== undefined ? current[key] : (key === 'q_bold'));
    setPref(key, newVal);
}

async function setPref(key, value) {
    const current = window._testPrefs || {q_font_size:5, a_font_size:5, highlight_intensity:5, theme:'dark', q_font_family:'default', a_font_family:'default', q_bold:true, a_bold:false, bg_brightness:5, font_weight:5};
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
