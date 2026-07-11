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
