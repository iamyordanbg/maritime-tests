// app/static/js/admin_tests.js
// Admin Tests управление — извлечена от app/templates/admin/tests.html (Правило 1+2).
// Очаква window.ALL_TESTS (data-инжекция от Jinja) за търсенето.

let selectedFile = null;
let uploadCategory = 'deck';

function openUploadModal(cat) {
    uploadCategory = cat;
    const etoOpt = document.getElementById('etoOption');
    const levelSelect = document.getElementById('uploadLevel');
    if (cat === 'engine') {
        etoOpt.style.display = '';
    } else {
        etoOpt.style.display = 'none';
        if (levelSelect.value === 'ETO') levelSelect.value = 'Operational Level';
    }
    const m = document.getElementById('uploadModal');
    m.style.display = 'flex';
}
function closeUploadModal() {
    document.getElementById('uploadModal').style.display = 'none';
    document.getElementById('fileInfo').style.display = 'none';
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
        document.getElementById('fileInfo').style.display = 'flex';
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
        document.getElementById('fileInfo').style.display = 'flex';
    }
});

async function submitUpload() {
    if (!selectedFile) { alert('Select file!'); return; }
    
    // Check title BEFORE uploading file
    const titleVal = document.getElementById('uploadTitle').value;
    const filename = selectedFile.name.replace('.xlsx','').replace('.xls','');
    const checkTitle = titleVal || filename;
    
    const checkRes = await fetch(`/admin/tests/next-title?title=${encodeURIComponent(checkTitle)}`);
    const checkData = await checkRes.json();
    
    if (checkData.duplicate) {
        // Show notification without uploading file
        const existing = document.getElementById('duplicateNote');
        if (existing) existing.remove();
        const note = document.createElement('div');
        note.id = 'duplicateNote';
        note.className = 'mt-2 bg-amber-500/10 border border-amber-500/30 rounded-lg p-2 text-[11px] text-amber-300';
        note.innerHTML = `⚠️ Test with name <b>"${checkTitle}"</b> already exists.<br>
            <div style="display:flex;gap:8px;margin-top:8px">
                <button onclick="continueUpload('${checkData.title}')" style="background:#f59e0b;color:#0B132B;font-weight:bold;padding:4px 12px;border-radius:6px;font-size:10px;cursor:pointer">Save as "${checkData.title}"</button>
                <button onclick="document.getElementById('duplicateNote').remove()" style="background:#334155;color:white;font-weight:bold;padding:4px 12px;border-radius:6px;font-size:10px;cursor:pointer">Cancel</button>
            </div>`;
        document.getElementById('uploadProgress').after(note);
        return;
    }
    
    // Continue with upload
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
                    // Get next available title from backend
                    const titleRes = await fetch(`/admin/tests/next-title?title=${encodeURIComponent(data.title)}`);
                    const titleData = await titleRes.json();
                    const nextTitle = titleData.title;
                    
                    const existing = document.getElementById('duplicateNote');
                    if (existing) existing.remove();
                    
                    const note = document.createElement('div');
                    note.id = 'duplicateNote';
                    note.className = 'mt-2 bg-amber-500/10 border border-amber-500/30 rounded-lg p-2 text-[11px] text-amber-300';
                    note.innerHTML = `⚠️ Test with name <b>"${data.title}"</b> already exists.<br>
                        <div style="display:flex;gap:8px;margin-top:8px">
                            <button onclick="uploadWithForce('${nextTitle}')" style="background:#f59e0b;color:#0B132B;font-weight:bold;padding:4px 12px;border-radius:6px;font-size:10px;cursor:pointer">Save as "${nextTitle}"</button>
                            <button onclick="document.getElementById('duplicateNote').remove()" style="background:#334155;color:white;font-weight:bold;padding:4px 12px;border-radius:6px;font-size:10px;cursor:pointer">Cancel</button>
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
    if (!title || title.length < 3) { note.style.display = 'none'; return; }
    titleCheckTimeout = setTimeout(async () => {
        try {
            const res = await fetch(`/admin/tests/next-title?title=${encodeURIComponent(title)}`);
            const data = await res.json();
            if (data.duplicate) {
                document.getElementById('titleDupText').textContent = `Already exists — will be saved as "${data.title}"`;
                note.style.display = 'block';
            } else {
                note.style.display = 'none';
            }
        } catch(e) {}
    }, 400);
}

async function uploadWithForce(newTitle) {
    // Used already parsed data from session - without new upload
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
    // Redirect to edit page
    window.location.href = `/admin/tests/${id}/edit`;
}

function performSearchInline() {
    const q = document.getElementById('searchInput').value.toLowerCase().trim();
    document.querySelectorAll('.test-row').forEach(row => {
        const titleEl = row.querySelector('p');
        const title = (row.dataset.title || (titleEl ? titleEl.textContent : '') || '').toLowerCase();
        row.style.display = (!q || title.includes(q)) ? '' : 'none';
    });
}
function performSearch() { performSearchInline(); }
document.getElementById('searchInput').addEventListener('keydown', e => {
    if (e.key === 'Enter') performSearch();
});

(function(){
    var tip=document.getElementById('globalTooltip');
    document.addEventListener('mouseover',function(e){
        var el=e.target.closest('[data-tip]');
        if(!el){tip.style.display='none';return;}
        tip.textContent=el.dataset.tip;
        tip.style.display='block';
    });
    document.addEventListener('mousemove',function(e){
        if(tip.style.display==='none')return;
        var x=e.clientX+14,y=e.clientY-44;
        if(x+320>window.innerWidth)x=e.clientX-334;
        if(y<0)y=e.clientY+14;
        tip.style.left=x+'px';tip.style.top=y+'px';
    });
    document.addEventListener('mouseout',function(e){
        if(!e.relatedTarget||!e.relatedTarget.closest('[data-tip]'))tip.style.display='none';
    });
})();

function openSearchModal() {
  document.getElementById('searchModal').style.display = 'block';
  setTimeout(() => document.getElementById('searchModalInput').focus(), 50);
}

function closeSearchModal() {
  document.getElementById('searchModal').style.display = 'none';
  document.getElementById('searchModalInput').value = '';
  document.getElementById('searchResults').innerHTML = '<div id="searchEmpty" style="text-align:center;padding:32px;color:#475569;font-size:13px"><i class="fa-solid fa-magnifying-glass" style="font-size:24px;display:block;margin-bottom:8px;opacity:0.4"></i>Enter search term</div>';
}

function runSearch(q) {
  const results = document.getElementById('searchResults');
  if (!q || q.length < 1) {
    results.innerHTML = '<div style="text-align:center;padding:32px;color:#475569;font-size:13px"><i class="fa-solid fa-magnifying-glass" style="font-size:24px;display:block;margin-bottom:8px;opacity:0.4"></i>Enter search term</div>';
    return;
  }
  
  const lower = q.toLowerCase();
  // Search in DOM directly - more reliable
  const rows = document.querySelectorAll('.test-row');
  const found = [];
  rows.forEach(row => {
    const titleEl = row.querySelector('p');
    const title = titleEl ? titleEl.textContent.trim() : '';
    const dataTitle = row.dataset.title || '';
    if (title.toLowerCase().includes(lower) || dataTitle.includes(lower)) {
      const id = row.id.replace('test_row_', '');
      const level = row.querySelector('.text-blue-400')?.textContent || '';
      const cat = row.closest('.bg-\[\#1C2541\]\/40') ? 
                  (row.closest('[id]')?.id || '') : '';
      found.push({id, title, level});
    }
  });

  if (!found.length) {
    results.innerHTML = '<div style="text-align:center;padding:32px;color:#475569;font-size:13px"><i class="fa-solid fa-circle-xmark" style="font-size:24px;display:block;margin-bottom:8px;opacity:0.4"></i>No tests found for <strong style="color:#fff">"' + q + '"</strong></div>';
    return;
  }

  results.innerHTML = '<div style="padding:6px 10px;font-size:10px;color:#64748b;text-transform:uppercase;letter-spacing:0.08em">' + found.length + ' results</div>' +
    found.map(t => `
      <div onclick="closeSearchModal();document.getElementById('test_row_${t.id}')?.scrollIntoView({behavior:'smooth',block:'center'});document.getElementById('test_row_${t.id}')?.classList.add('ring-1','ring-purple-500')"
           style="padding:10px 14px;border-radius:10px;cursor:pointer;transition:background 0.2s;display:flex;align-items:center;justify-content:space-between;gap:10px"
           onmouseover="this.style.background='rgba(99,102,241,0.1)'"
           onmouseout="this.style.background='transparent'">
        <div>
          <div style="font-size:13px;font-weight:500;color:#fff">${t.title}</div>
          <div style="font-size:11px;color:#64748b;margin-top:2px">${t.level}</div>
        </div>
        <i class="fa-solid fa-arrow-right" style="color:#64748b;font-size:11px;flex-shrink:0"></i>
      </div>`).join('');
}

// Keep old performSearch for compatibility
function performSearch() { openSearchModal(); }

// ESC to close
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeSearchModal();
});

async function toggleDemo(testId, isDemo) {
    const res = await fetch(`/admin/tests/${testId}/toggle-demo`, {method:'POST'});
    const data = await res.json();
    if(data.success) location.reload();
}
