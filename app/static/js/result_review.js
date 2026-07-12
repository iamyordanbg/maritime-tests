// Result Review страница (/result/<id>) - извлечена логика (виж
// app/templates/user/result_review.html).
// Reading Settings панелът (theme/font/highlight/brightness/weight) вече
// живее в споделения app/static/js/reading-prefs.js (зареден СЛЕД този
// файл в result_review.html). Тази страница е read-only (без radio избор) -
// не се нуждае от свой onPrefsApplied hook.

window.addEventListener('DOMContentLoaded', () => {
    requestAnimationFrame(() => {
        document.getElementById('mainContent').style.opacity = '1';
    });
});

// Скролва до СЛЕДВАЩАТА грешка (цикличо - след последната се връща на
// 1-вата). Търси [id^="qbox_"] елементи, съдържащи поне един .is-wrong
// ред (грешно избран отговор) - идентична логика на goToFirstMistake()
// в simulator.js, адаптирана за list pattern-а на тази страница.
function goToFirstMistake() {
    const container = document.getElementById('mainContent');
    if (!container) return;
    const mistakeBoxes = Array.from(container.querySelectorAll('[id^="qbox_"]')).filter(
        box => box.querySelector('.is-wrong')
    );
    if (mistakeBoxes.length === 0) return;  // няма грешки - нищо не прави

    const cur = window._reviewMistakeCursor;
    window._reviewMistakeCursor = ((cur === undefined ? -1 : cur) + 1) % mistakeBoxes.length;
    const target = mistakeBoxes[window._reviewMistakeCursor];
    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    target.style.transition = 'box-shadow 0.3s ease';
    target.style.boxShadow = '0 0 0 1px rgba(244,63,94,0.3)';
    setTimeout(() => { target.style.boxShadow = 'none'; }, 1500);
}
