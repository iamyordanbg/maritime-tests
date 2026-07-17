// app/static/js/admin_edit_test.js
// Admin Edit Test — извлечена от app/templates/admin/edit_test.html (Правило 1+2).
// Очаква window.TEST_DATA = {id, isDemo} - сетнат от малка data-инжекция
// в темплейта, преди този файл.

const testId = window.TEST_DATA.id;

document.getElementById('et-demo-btn').addEventListener('click', confirmDemo);
document.getElementById('et-delete-btn').addEventListener('click', confirmDelete);
document.getElementById('et-save-btn').addEventListener('click', saveAll);
document.getElementById('questionsContainer').addEventListener('change', function(e) {
    if (e.target.classList.contains('q-correct-radio')) markCorrect(e.target);
});

function markCorrect(radio) {
    const box = radio.closest('[data-qidx]');
    box.querySelectorAll('.opt-wrap').forEach(wrap => {
        const r = wrap.querySelector('input[type="radio"]');
        const t = wrap.querySelector('.opt-text');
        const ok = r && r.checked;
        wrap.className = `opt-wrap flex items-center gap-2 p-1.5 rounded border ${ok ? 'border-emerald-500/50 bg-emerald-500/5' : 'border-slate-700/40 bg-[#1C2541]/40'}`;
        if (t) t.className = `opt-text flex-1 bg-transparent text-[14px] border-none focus:outline-none ${ok ? 'text-emerald-400 font-bold' : 'text-slate-300'}`;
    });
}

async function saveAll() {
    const boxes = document.querySelectorAll('[data-qidx]');
    const updated = [];
    const letters = ['a','b','c','d','e','f','g','h'];
    boxes.forEach(box => {
        const qId = parseInt(box.dataset.qid);
        const qText = box.querySelector('.q-text').value;
        const options = [];
        box.querySelectorAll('.opt-wrap').forEach((wrap, oIdx) => {
            const radio = wrap.querySelector('input[type="radio"]');
            const textInput = wrap.querySelector('.opt-text');
            options.push({ letter: letters[oIdx] || 'x', text: textInput ? textInput.value : '', isCorrect: radio ? radio.checked : false });
        });
        if (options.length > 0 && !options.some(o => o.isCorrect)) options[0].isCorrect = true;
        updated.push({ id: qId, question: qText, options });
    });
    try {
        await fetch(`/admin/tests/${testId}/update-info`, {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ title: document.getElementById('testTitle').value, level: document.getElementById('testLevel').value })
        });
        const res = await fetch(`/admin/tests/${testId}/questions`, {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ questions: updated })
        });
        const data = await res.json();
        if (data.success) {
            const t = document.createElement('div');
            t.className = 'fixed bottom-6 right-6 z-[100] px-4 py-3 rounded-xl text-[11px] font-bold shadow-2xl border bg-emerald-500/20 border-emerald-500/40 text-emerald-300';
            t.textContent = '✓ Changes saved!';
            document.body.appendChild(t);
            setTimeout(() => t.remove(), 3000);
        }
    } catch(e) { alert('Error saving!'); }
}

async function confirmDelete() {
    if (!confirm('Are you sure? This action is irreversible!')) return;
    const res = await fetch(`/admin/tests/${testId}/delete`, { method: 'POST' });
    const data = await res.json();
    if (data.success) window.location.href = '/admin/tests';
}

function confirmDemo() {
    const isDemo = window.TEST_DATA.isDemo;
    const msg = isDemo ? 'Deactivate demo for this test?' : 'Activate this test as demo?';
    if (!confirm(msg)) return;
    fetch(`/admin/demo/toggle/${testId}`, {
        method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json'}
    })
    .then(r => r.json())
    .then(data => { if (data.success) location.reload(); })
    .catch(err => alert('Error: ' + err));
}
