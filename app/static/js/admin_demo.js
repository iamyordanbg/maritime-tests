// app/static/js/admin_demo.js
// Admin Demo tests управление — извлечена от app/templates/admin/demo.html (Правило 1).

document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => filterCat(btn.dataset.cat));
});
document.querySelectorAll('.demo-toggle').forEach(btn => {
    btn.addEventListener('click', () => toggleDemo(btn.dataset.testid, btn));
});

function filterCat(cat) {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.getElementById('tab-' + cat).classList.add('active');
    document.querySelectorAll('.test-row').forEach(row => {
        let hide;
        if (cat === 'all') hide = false;
        else if (cat === 'demo') hide = row.dataset.demo !== 'true';
        else hide = row.dataset.cat !== cat;
        row.classList.toggle('demo-row-hidden', hide);
    });
}

async function toggleDemo(testId, btn) {
    btn.disabled = true;
    btn.classList.add('demo-toggle-loading');
    try {
        const res = await fetch('/admin/demo/toggle/' + testId, {
            method: 'POST', credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' }
        });
        if (!res.ok) throw new Error('Server error ' + res.status);
        const data = await res.json();
        if (data.success) {
            const isDemo = data.is_demo;
            btn.classList.toggle('is-demo', isDemo);
            btn.dataset.demo = isDemo ? 'true' : 'false';
            btn.title = (isDemo ? 'Деактивирай' : 'Unblock') + ' демо';
            btn.closest('.test-row').dataset.demo = isDemo ? 'true' : 'false';
            // Update stats counter
            const total = document.querySelectorAll('.test-row[data-demo="true"]').length;
            document.querySelector('.text-amber-400').textContent = total;
        }
    } catch (err) {
        alert('Error: ' + err.message);
    } finally {
        btn.disabled = false;
        btn.classList.remove('demo-toggle-loading');
    }
}
