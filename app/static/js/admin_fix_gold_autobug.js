// app/static/js/admin_fix_gold_autobug.js
// Извлечена от app/templates/admin/fix_gold_autobug.html (Правило 1).

const fgaForm = document.getElementById('fgaForm');
if (fgaForm) {
    fgaForm.addEventListener('submit', function(e) {
        const count = fgaForm.dataset.confirmCount;
        if (!confirm('Сигурен ли си? Ще промениш плана на ' + count + ' акаунта.')) {
            e.preventDefault();
        }
    });
}
