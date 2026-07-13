// app/static/js/admin_demo.js
// Admin Demo tests управление — извлечена от app/templates/admin/demo.html (Правило 1).

function filterCat(cat) {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.getElementById('tab-' + cat).classList.add('active');
    document.querySelectorAll('.test-row').forEach(row => {
        if (cat === 'all') { row.style.display = ''; return; }
        if (cat === 'demo') { row.style.display = row.dataset.demo === 'true' ? '' : 'none'; return; }
        row.style.display = row.dataset.cat === cat ? '' : 'none';
    });
}

async function toggleDemo(testId, btn) {
    btn.disabled = true;
    btn.style.opacity = '0.5';
    try {
        const res = await fetch('/admin/demo/toggle/' + testId, {
            method: 'POST', credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' }
        });
        if (!res.ok) throw new Error('Server error ' + res.status);
        const data = await res.json();
        if (data.success) {
            const isDemo = data.is_demo;
            btn.style.background = isDemo ? '#f59e0b' : '#475569';
            btn.querySelector('span').style.left = isDemo ? '19px' : '3px';
            btn.dataset.demo = isDemo ? 'true' : 'false';
            btn.title = (isDemo ? 'Деактивирай' : 'Unblock') + ' демо';
            btn.closest('.test-row').dataset.demo = isDemo ? 'true' : 'false';
            // Update stats counter
            const total = document.querySelectorAll('.test-row[data-demo="true"]').length;
            document.querySelector('.text-amber-400').textContent = total;
        }
    } catch (err) {
        alert('Грешка: ' + err.message);
    } finally {
        btn.disabled = false;
        btn.style.opacity = '1';
    }
}
