// Result Review страница - Настройки за четене (font size / theme / font
// family), същата логика като в test.js/simulator.js, адаптирана тук за
// read-only изглед (без radio избор/highlightSelected - отговорите вече
// имат фиксирани зелен/червен цветове за верен/грешен).

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
    const qPx = 12 + qSize * 2;
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
        #mainContent .opt-label.is-correct { background: rgba(16,185,129,${rowOpacity}) !important; }
        #mainContent .opt-label.is-wrong { background: rgba(244,63,94,${rowOpacity}) !important; }
    `;

    document.getElementById('qSizeSlider').value = qSize;
    document.getElementById('aSizeSlider').value = aSize;
    document.getElementById('qSizeVal').textContent = qSize;
    document.getElementById('aSizeVal').textContent = aSize;
    const hi = prefs.highlight_intensity !== undefined ? prefs.highlight_intensity : 5;
    document.getElementById('hiSlider').value = hi;
    document.getElementById('hiVal').textContent = hi;
    // Интензитетът на зеления/червения фон на верен/грешен отговор -
    // същата формула като highlightSelected() в test.js (0.02 - 0.30),
    // за консистентност с решаването на теста.
    const rowOpacity = (0.02 + (hi / 10) * 0.28).toFixed(3);
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

window.addEventListener('DOMContentLoaded', () => {
    requestAnimationFrame(() => {
        document.getElementById('mainContent').style.opacity = '1';
    });
});
