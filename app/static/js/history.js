// app/static/js/history.js
// User History страница — извлечена от app/templates/user/history.html (Правило 1).

document.querySelectorAll('.history-id-copy').forEach(el => {
    el.addEventListener('click', function() {
        const text = this.dataset.copy;
        navigator.clipboard.writeText(text).then(() => {
            const original = this.textContent;
            this.textContent = '✓ Copied';
            this.classList.add('history-id-copied');
            setTimeout(() => {
                this.textContent = original;
                this.classList.remove('history-id-copied');
            }, 1200);
        }).catch(() => {});
    });
});
