// app/static/js/admin_tests.js
// Admin Tests управление — извлечена от app/templates/admin/tests.html (Правило 1+2).
// Очаква window.ALL_TESTS (data-инжекция от Jinja) за търсенето.

let selectedFile = null;
let uploadCategory = 'deck';

// ---------- Event wiring (заменя премахнатите onclick/oninput/onchange) ----------
document.querySelectorAll('.tt-upload-btn').forEach(btn => {
    btn.addEventListener('click', () => openUploadModal(btn.dataset.cat));
});
document.getElementById('tt-upload-close-x').addEventListener('click', closeUploadModal);
document.getElementById('tt-upload-cancel-btn').addEventListener('click', closeUploadModal);
document.getElementById('submitBtn').addEventListener('click', submitUpload);
document.getElementById('uploadTitle').addEventListener('input', function() { checkTitleDuplicate(this.value); });
document.getElementById('dropZone').addEventListener('click', () => document.getElementById('fileInput').click());
document.getElementById('tt-search-btn').addEventListener('click', performSearchInline);
document.getElementById('tt-search-modal-close-btn').addEventListener('click', closeSearchModal);
document.getElementById('searchModalInput').addEventListener('input', function() { runSearch(this.value); });
document.getElementById('searchModal').addEventListener('click', function(e) {
    if (e.target === this) closeSearchModal();
});
document.addEventListener('click', function(e) {
    const editBtn = e.target.closest('.tt-edit-btn');
    if (editBtn) openEditModal(editBtn.dataset.testid, editBtn.dataset.title);
});

function openUploadModal(cat) {
    uploadCategory = cat;
    const etoOpt = document.getElementById('etoOption');
    const levelSelect = document.getElementById('uploadLevel');
    if (cat === 'engine') {
        etoOpt.classList.remove('hidden');
    } else {
        etoOpt.classList.add('hidden');
        if (levelSelect.value === 'ETO') levelSelect.value = 'Operational Level';
    }
    document.getElementById('uploadModal').classList.add('tt-modal-open');
}
function closeUploadModal() {
    document.getElementById('uploadModal').classList.remove('tt-modal-open');
    document.getElementById('fileInfo').classList.add('hidden');
    document.getElementById('uploadProgress').classList.add('hidden');
    document.getElementById('fileInput').value = '';
    document.getElementById('uploadTitle').value = '';
    document.getElementById('submitBtn').disabled = false;
    document.getElementById('submitBtn').innerHTML = '<i class="fa-solid fa-upload mr-1"></i> Import';
    selectedFile = null;
}

document.getElementById('fileInput').addEventListener('change', (e) => {
    if (e.target.files[0]) {
        selectedFile = e.target.files[0];
        document.getElementById('fileName').textContent = selectedFile.name;
        document.getElementById('fileInfo').classList.remove('hidden');
    }
});

const dz = document.getElementById('dropZone');
dz.addEventListener('dragover', e => { e.preventDefault(); dz.classList.add('border-[#34d399]/60'); });
dz.addEventListener('dragleave', () => dz.classList.remove('border-[#34d399]/60'));
dz.addEventListener('drop', e => {
    e.preventDefault(); dz.classList.remove('border-[#34d399]/60');
    if (e.dataTransfer.files[0]) {
        selectedFile = e.dataTransfer.files[0];
        document.getElementById('fileName').textContent = selectedFile.name;
        document.getElementById('fileInfo').classList.remove('hidden');
    }
});

// Делегиран listener за динамично инжектираните "duplicate note" бутони
// (Save as.../Cancel) - заменя предишните onclick="..." в generated HTML.
document.addEventListener('click', function(e) {
    const saveBtn = e.target.closest('.tt-dupnote-save');
    if (saveBtn) {
        if (saveBtn.dataset.mode === 'force') uploadWithForce(saveBtn.dataset.title);
        else continueUpload(saveBtn.dataset.title);
        return;
    }
    if (e.target.closest('.tt-dupnote-cancel')) {
        document.getElementById('duplicateNote')?.remove();
    }
});

async function submitUpload() {
    if (!selectedFile) { alert('Select file!'); return; }

    const titleVal = document.getElementById('uploadTitle').value;
    const filename = selectedFile.name.replace('.xlsx','').replace('.xls','');
    const checkTitle = titleVal || filename;

    const checkRes = await fetch(`/admin/tests/next-title?title=${encodeURIComponent(checkTitle)}`);
    const checkData = await checkRes.json();

    if (checkData.duplicate) {
        const existing = document.getElementById('duplicateNote');
        if (existing) existing.remove();
        const note = document.createElement('div');
        note.id = 'duplicateNote';
        note.className = 'mt-2 bg-amber-500/10 border border-amber-500/30 rounded-lg p-2 text-[11px] text-amber-300';
        note.innerHTML = `⚠️ Test with name <b>"${checkTitle}"</b> already exists.<br>
            <div class="tt-dupnote-actions">
                <button class="tt-dupnote-save" data-mode="continue" data-title="${checkData.title}">Save as "${checkData.title}"</button>
                <button class="tt-dupnote-cancel">Cancel</button>
            </div>`;
        document.getElementById('uploadProgress').after(note);
        return;
    }

    await continueUpload(checkTitle);
}

async function continueUpload(finalTitle) {
    const existing = document.getElementById('duplicateNote');
    if (existing) existing.remove();

    document.getElementById('uploadProgress').classList.remove('hidden');
    document.getElementById('submitBtn').disabled = true;
    document.getElementById('submitBtn').innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-1"></i> Processing...';

    const fd = new FormData();
    fd.append('file', selectedFile);
    fd.append('title', finalTitle);
    fd.append('category', uploadCategory);
    fd.append('level', document.getElementById('uploadLevel').value);

    try {
        const res = await fetch('/admin/tests/upload', { method: 'POST', body: fd });
        const data = await res.json();

        if (data.duplicate) {
            const titleRes = await fetch(`/admin/tests/next-title?title=${encodeURIComponent(data.title)}`);
            const titleData = await titleRes.json();
            const nextTitle = titleData.title;

            const existing = document.getElementById('duplicateNote');
            if (existing) existing.remove();

            const note = document.createElement('div');
            note.id = 'duplicateNote';
            note.className = 'mt-2 bg-amber-500/10 border border-amber-500/30 rounded-lg p-2 text-[11px] text-amber-300';
            note.innerHTML = `⚠️ Test with name <b>"${data.title}"</b> already exists.<br>
                <div class="tt-dupnote-actions">
                    <button class="tt-dupnote-save" data-mode="force" data-title="${nextTitle}">Save as "${nextTitle}"</button>
                    <button class="tt-dupnote-cancel">Cancel</button>
                </div>`;
            document.getElementById('uploadProgress').after(note);
            document.getElementById('submitBtn').disabled = false;
            document.getElementById('submitBtn').innerHTML = '<i class="fa-solid fa-upload mr-1"></i> Import';
            return;
        }

        if (data.success) {
            closeUploadModal();
            location.reload();
        } else {
            alert('Error: ' + data.error);
            closeUploadModal();
        }
    } catch(e) {
        alert('Error uploading file');
        closeUploadModal();
    }
}

let titleCheckTimeout = null;
async function checkTitleDuplicate(title) {
    clearTimeout(titleCheckTimeout);
    const note = document.getElementById('titleDupNote');
    if (!title || title.length < 3) { note.classList.add('hidden'); return; }
    titleCheckTimeout = setTimeout(async () => {
        try {
            const res = await fetch(`/admin/tests/next-title?title=${encodeURIComponent(title)}`);
            const data = await res.json();
            if (data.duplicate) {
                document.getElementById('titleDupText').textContent = `Already exists — will be saved as "${data.title}"`;
                note.classList.remove('hidden');
            } else {
                note.classList.add('hidden');
            }
        } catch(e) {}
    }, 400);
}

async function uploadWithForce(newTitle) {
    try {
        const res = await fetch('/admin/tests/force-upload', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title: newTitle })
        });
        const data = await res.json();
        if (data.success) { closeUploadModal(); location.reload(); }
        else alert('Error: ' + (data.error || 'Unknown error'));
    } catch(e) { alert('Error uploading'); }
}

async function deleteTest(id) {
    if (!confirm('Delete this test?')) return;
    const res = await fetch(`/admin/tests/${id}/delete`, { method: 'POST' });
    const data = await res.json();
    if (data.success) document.getElementById(`test_row_${id}`).remove();
}

function openEditModal(id, title) {
    window.location.href = `/admin/tests/${id}/edit`;
}

function performSearchInline() {
    const q = document.getElementById('searchInput').value.toLowerCase().trim();
    document.querySelectorAll('.test-row').forEach(row => {
        const titleEl = row.querySelector('p');
        const title = (row.dataset.title || (titleEl ? titleEl.textContent : '') || '').toLowerCase();
        row.classList.toggle('tt-row-hidden', !(!q || title.includes(q)));
    });
}
document.getElementById('searchInput').addEventListener('keydown', e => {
    if (e.key === 'Enter') performSearchInline();
});

(function(){
    var tip=document.getElementById('globalTooltip');
    document.addEventListener('mouseover',function(e){
        var el=e.target.closest('[data-tip]');
        if(!el){tip.classList.remove('tt-tooltip-visible');return;}
        tip.textContent=el.dataset.tip;
        tip.classList.add('tt-tooltip-visible');
    });
    document.addEventListener('mousemove',function(e){
        if(!tip.classList.contains('tt-tooltip-visible'))return;
        var x=e.clientX+14,y=e.clientY-44;
        if(x+320>window.innerWidth)x=e.clientX-334;
        if(y<0)y=e.clientY+14;
        tip.style.left=x+'px';tip.style.top=y+'px';
    });
    document.addEventListener('mouseout',function(e){
        if(!e.relatedTarget||!e.relatedTarget.closest('[data-tip]'))tip.classList.remove('tt-tooltip-visible');
    });
})();

function openSearchModal() {
  document.getElementById('searchModal').classList.add('tt-modal-open');
  setTimeout(() => document.getElementById('searchModalInput').focus(), 50);
}

function closeSearchModal() {
  document.getElementById('searchModal').classList.remove('tt-modal-open');
  document.getElementById('searchModalInput').value = '';
  document.getElementById('searchResults').innerHTML = '<div id="searchEmpty" class="tt-search-empty"><i class="fa-solid fa-magnifying-glass tt-search-empty-icon"></i>Enter search term</div>';
}

// Делегиран listener за динамично генерираните search резултати -
// заменя onclick/onmouseover/onmouseout в generated HTML string-а по-долу.
document.getElementById('searchResults').addEventListener('click', function(e) {
    const item = e.target.closest('.tt-search-result-item');
    if (!item) return;
    closeSearchModal();
    const row = document.getElementById('test_row_' + item.dataset.testid);
    row?.scrollIntoView({behavior:'smooth', block:'center'});
    row?.classList.add('ring-1','ring-purple-500');
});

function runSearch(q) {
  const results = document.getElementById('searchResults');
  if (!q || q.length < 1) {
    results.innerHTML = '<div class="tt-search-empty"><i class="fa-solid fa-magnifying-glass tt-search-empty-icon"></i>Enter search term</div>';
    return;
  }

  const lower = q.toLowerCase();
  const rows = document.querySelectorAll('.test-row');
  const found = [];
  rows.forEach(row => {
    const titleEl = row.querySelector('p');
    const title = titleEl ? titleEl.textContent.trim() : '';
    const dataTitle = row.dataset.title || '';
    if (title.toLowerCase().includes(lower) || dataTitle.includes(lower)) {
      const id = row.id.replace('test_row_', '');
      const level = row.querySelector('.text-blue-400')?.textContent || '';
      found.push({id, title, level});
    }
  });

  if (!found.length) {
    results.innerHTML = '<div class="tt-search-empty"><i class="fa-solid fa-circle-xmark tt-search-empty-icon"></i>No tests found for <strong class="tt-search-noresult-strong">"' + q + '"</strong></div>';
    return;
  }

  results.innerHTML = '<div class="tt-search-count">' + found.length + ' results</div>' +
    found.map(t => `
      <div class="tt-search-result-item" data-testid="${t.id}">
        <div>
          <div class="tt-search-result-title">${t.title}</div>
          <div class="tt-search-result-level">${t.level}</div>
        </div>
        <i class="fa-solid fa-arrow-right tt-search-result-arrow"></i>
      </div>`).join('');
}

// ESC to close
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeSearchModal();
});

async function toggleDemo(testId, isDemo) {
    const res = await fetch(`/admin/tests/${testId}/toggle-demo`, {method:'POST'});
    const data = await res.json();
    if(data.success) location.reload();
}
