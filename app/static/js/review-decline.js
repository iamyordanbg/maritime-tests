// Страница "No thanks" от имейла (templates/review_decline.html): записва отказа автоматично,
// без втори клик. Без JS остава ръчният бутон "Yes, no thanks" (POST към същия адрес).
(function () {
    const form = document.getElementById('rdForm');
    if (!form) return;
    fetch(window.location.href, {method: 'POST'})
        .then(res => res.ok ? res.text() : Promise.reject(res.status))
        .then(html => {
            const doc = new DOMParser().parseFromString(html, 'text/html');
            const card = doc.querySelector('.rd-card');
            if (card) document.querySelector('.rd-card').innerHTML = card.innerHTML;
        })
        .catch(() => { /* остава ръчният бутон */ });
})();
