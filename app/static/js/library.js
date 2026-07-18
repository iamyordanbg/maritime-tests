// Library страница - извлечена логика (виж app/templates/user/library.html за данните)
function closeAwaitingTestPopup() {
  document.getElementById('awaitingTestOverlay').classList.remove('show');
}
if (LIB.needs_first_selection) {
  document.addEventListener('DOMContentLoaded', function() {
    document.getElementById('awaitingTestOverlay').classList.add('show');
  });
}
// Ако потребителят е по средата на Gold активация (избрал е 1-ви тест,
// после е презаредил страницата преди да завърши) - показваме отново
// popup-а за 2-ри тест автоматично, вместо да го изгубим тихо.
if (GOLD_ACTIVATION && GOLD_ACTIVATION.first_test_id) {
  document.addEventListener('DOMContentLoaded', function() {
    showGoldSecondPrompt(GOLD_ACTIVATION.first_test_title);
  });
}

var RANKS = [
  {id:'r1',label:'Captain / Master',stripes:4,level:'management'},
  {id:'r2',label:'Chief Officer',stripes:3,level:'management'},
  {id:'r3',label:'Second Officer',stripes:2,level:'operational'},
  {id:'r4',label:'Third Officer',stripes:1,level:'operational'},
  {id:'r5',label:'Deck Cadet',stripes:0,level:'operational'}
];
// Deck Ratings — отделна секция под основните рангове
var DECK_RATINGS = [
  {id:'dr1',label:'Bosun · Able Seaman · Ordinary Seaman',stripes:0,level:'rating_deck'}
];
var ENGINE = [
  {id:'e1',label:'Chief Engineer',stripes:4,level:'management'},
  {id:'e2',label:'Second Engineer',stripes:3,level:'management'},
  {id:'e3',label:'Third Engineer',stripes:2,level:'operational'},
  {id:'e4',label:'Fourth Engineer',stripes:1,level:'operational'},
  {id:'e5',label:'Engine Cadet',stripes:0,level:'operational'}
];
var ENGINE_RATINGS = [
  {id:'er1',label:'Oiler · Motorman · Wiper',stripes:0,level:'rating_engine'}
];

function stripes(n){
  if(n===0) return '<div style="font-size:14px;color:rgba(232,160,32,0.6)">⬟</div>';
  var s='';
  for(var i=0;i<n;i++) s+='<div class="stripe" style="width:'+(n===4?18:n===3?16:n===2?14:12)+'px"></div>';
  return s;
}

function buildLibDD(tid, isPremiumUser) {
  var freeMode = !isPremiumUser;
  var rows = '';
  // Test
  rows += freeMode
    ? '<div class="lib-dml dim"><span class="lib-dmi">📝</span><div><p class="lib-dmt">Test</p><p class="lib-dms">All questions in order</p></div></div>'
    : '<a href="/test/'+tid+'" class="lib-dml"><span class="lib-dmi">📝</span><div><p class="lib-dmt">Test</p><p class="lib-dms">All questions in order</p></div></a>';
  // Mix
  rows += freeMode
    ? '<div class="lib-dml dim"><span class="lib-dmi">🔀</span><div><p class="lib-dmt">Mix</p><p class="lib-dms">Questions shuffled</p></div></div>'
    : '<a href="/test/'+tid+'?shuffle=true" class="lib-dml"><span class="lib-dmi">🔀</span><div><p class="lib-dmt">Mix</p><p class="lib-dms">Questions shuffled</p></div></a>';
  // Mistakes — dim-click за free, активен за premium (errors се проверяват при клик)
  rows += '<div class="lib-dml dim-click" data-tid="'+tid+'" onclick="libMistakesClick(this)"><span class="lib-dmi">❌</span><div><p class="lib-dmt">Mistakes</p><p class="lib-dms">Only questions you got wrong</p></div></div>';
  // Simulator — винаги активен
  rows += '<a href="/test/'+tid+'/simulator" class="lib-dml" style="border-bottom:none"><span class="lib-dmi">🎯</span><div><p class="lib-dmt">Simulator</p><p class="lib-dms">45 questions · 60 minutes</p></div></a>';

  return '<div class="ddm lib-ddm" style="display:none;position:absolute;right:0;top:calc(100% + 6px);z-index:9999;background:rgba(10,24,47,0.98);border:1px solid rgba(232,160,32,0.3);border-radius:12px;min-width:225px;box-shadow:0 20px 60px rgba(0,0,0,0.85)">'
    + '<div style="padding:8px 14px 6px;border-bottom:1px solid rgba(255,255,255,0.06)"><p style="font-size:9px;color:rgba(232,160,32,0.75);font-weight:700;letter-spacing:0.1em;text-transform:uppercase;margin:0">Choose Mode</p></div>'
    + rows + '</div>';
}

function renderCard(t){
  var sel = (LIB.selected_test_ids || []).indexOf(t.id) !== -1;
  var safeTitle = t.title.replace(/\\/g,'\\\\').replace(/'/g,"\\'");

  if (LIB.is_premium || GOLD_ACTIVATION) {
    // Premium (Basic/Plus/Gold): избраният тест + demo тестовете остават
    // напълно нормални/кликаеми (избор на тест от библиотеката, БЕЗ popup
    // за режим - бутонът "Load" избира И директно зарежда). Всеки ДРУГ
    // тест (не избран, не demo) вече е ВИЗУАЛНО заключен - избледняла
    // карта + лек "Premium" бадж - кликването показва информативен toast
    // (showLibPremiumToast), НЕ объркващия confirm popup "Are you sure
    // you want to select X?", който предполага директна смяна на избора.
    var pLocked = !GOLD_ACTIVATION && !sel && !t.is_demo;

    var pbadge = sel
      ? '<span style="background:#06D6A0;color:#071a2e;font-size:9px;font-weight:700;padding:2px 7px;border-radius:20px;margin-right:6px">✓ ИЗБРАН</span>'
      : t.is_demo
        ? '<span style="background:#E8A020;color:#071a2e;font-size:9px;font-weight:700;padding:2px 7px;border-radius:20px;margin-right:6px">DEMO</span>'
        : pLocked
          ? '<span style="background:rgba(99,91,255,0.15);color:#a78bfa;font-size:9px;font-weight:700;padding:2px 7px;border-radius:20px;margin-right:6px">Premium</span>'
          : '';
    var pCardStyle = sel
      ? 'background:rgba(6,214,160,0.06);border:1.5px solid rgba(6,214,160,0.4)'
      : pLocked
        ? 'background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.07);opacity:0.65'
        : 'background:rgba(232,160,32,0.06);border:1.5px solid rgba(232,160,32,0.4)';
    var pBS = 'width:110px;padding:8px 0;font-size:12px;font-weight:700;cursor:pointer;border-radius:8px;text-align:center;display:inline-flex;align-items:center;justify-content:center;gap:6px';
    // БЪГ ФИКС (продължение): предишният "sel=true -> skip API" фикс имаше
    // критичен пропуск - sel е computed ПО ТЕСТ (кой да е grant вече го
    // ползва ли), не ПО GRANT (чакащия, все още неконфигуриран grant има
    // ли нужда от избор). Потребител с 2 активни plan-а (напр. Basic вече
    // с избран тест X + нов Plus без тест) - ако избере СЪЩИЯ тест X за
    // Plus, sel=true (X вече Е избран - за Basic!), бутонът тихо
    // навигираше директно към dashboard БЕЗ да вика /library/select -
    // Plus оставаше завинаги без прикачен тест. Сега: skip-ваме API-то
    // САМО ако sel=true И НЯМА чакащ grant (LIB.awaiting_selection=false) -
    // щом има чакащ grant, ВИНАГИ минаваме през selectLibraryTest(),
    // дори за тест, вече избран другаде, за да се прикачи коректно.
    var pBtn;
    if (t.is_demo) {
      // Demo тест — не изисква избор/grant изобщо (винаги свободно
      // достъпен). Вместо "Are you sure you want to select X?" (безсмислен
      // за демо), показваме dropdown със същите функции като на landing
      // страницата (Test/Mix/Mistakes/Simulator) - огледално на free-план
      // клона по-долу.
      pBtn = '<div style="position:relative;flex-shrink:0;overflow:visible">'
        + '<button onclick="event.stopPropagation();libToggleDD(this)" style="'+pBS+';background:#E8A020;color:#071a2e;border:none">Open ▾</button>'
        + buildLibDD(t.id, false)
        + '</div>';
    } else if (pLocked) {
      pBtn = '<button onclick="window.location.href=PLANS_URL" style="'+pBS+';background:rgba(99,91,255,0.15);color:#a78bfa;border:1px solid rgba(99,91,255,0.3)">Load</button>';
    } else if (sel && !LIB.awaiting_selection) {
      pBtn = '<button onclick="window.location.href=DASHBOARD_URL" style="'+pBS+';background:#E8A020;color:#071a2e;border:none">Load</button>';
    } else {
      pBtn = '<button onclick="selectLibraryTest('+t.id+',\''+safeTitle+'\')" style="'+pBS+';background:#E8A020;color:#071a2e;border:none">Load</button>';
    }
    return '<div class="tcard" id="tc'+t.id+'" style="'+pCardStyle+'"><div>'+pbadge
      +'<div style="font-size:13px;font-weight:600;color:'+(pLocked?'#64748b':'#fff')+'">'+t.title+'</div>'
      +'<div style="font-size:11px;color:rgba(232,237,242,0.4);margin-top:3px">'+t.question_count+' questions</div>'
      +'</div>'+pBtn+'</div>';
  }

  // ----- Free-план поток (непроменено legacy поведение, демо включено) -----
  var locked = LIB.window_active && !sel && !t.is_demo;

  // Бадж
  var badge = sel
    ? '<span style="background:#06D6A0;color:#071a2e;font-size:9px;font-weight:700;padding:2px 7px;border-radius:20px;margin-right:6px">✓ ИЗБРАН</span>'
    : t.is_demo
      ? '<span style="background:#E8A020;color:#071a2e;font-size:9px;font-weight:700;padding:2px 7px;border-radius:20px;margin-right:6px">DEMO</span>'
      : locked
        ? '<span style="background:rgba(99,91,255,0.15);color:#a78bfa;font-size:9px;font-weight:700;padding:2px 7px;border-radius:20px;margin-right:6px">🔒 PREMIUM</span>'
        : '';

  // Цвят на картата
  var cardStyle = sel
    ? 'background:rgba(6,214,160,0.06);border:1.5px solid rgba(6,214,160,0.4)'
    : locked
      ? 'background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.07)'
      : 'background:rgba(232,160,32,0.06);border:1.5px solid rgba(232,160,32,0.4)';

  var BS = 'width:110px;padding:8px 0;font-size:12px;font-weight:700;cursor:pointer;border-radius:8px;text-align:center;display:inline-flex;align-items:center;justify-content:center;gap:6px';

  var btn;
  if (locked) {
    // Заключен — само Premium бутон без dropdown
    btn = '<button onclick="showLibPremiumToast(event)" style="'+BS+';background:rgba(99,91,255,0.15);color:#a78bfa;border:1px solid rgba(99,91,255,0.3)">🔒 Premium</button>';
  } else if (!LIB.window_active && !t.is_demo && !sel) {
    // Няма активен прозорец и не е demo → Load за избор на тест
    btn = '<button onclick="openModal('+t.id+',\''+safeTitle+'\')" style="'+BS+';background:#E8A020;color:#071a2e;border:none">Load</button>';
  } else {
    // Demo или избран/свободен (free) → бутон с dropdown (само за демо преглед)
    var label = sel ? '✓ Open ▾' : 'Open ▾';
    btn = '<div style="position:relative;flex-shrink:0;overflow:visible">'
      + '<button onclick="event.stopPropagation();libToggleDD(this)" style="'+BS+';background:#E8A020;color:#071a2e;border:none">'
      + label
      + '</button>'
      + buildLibDD(t.id, false)
      + '</div>';
  }

  return '<div class="tcard" id="tc'+t.id+'" style="'+cardStyle+'"><div>'+badge
    +'<div style="font-size:13px;font-weight:600;color:'+(locked?'#64748b':'#fff')+'">'+t.title+'</div>'
    +'<div style="font-size:11px;color:rgba(232,237,242,0.4);margin-top:3px">'+t.question_count+' questions</div>'
    +'</div>'+btn+'</div>';
}

function renderRanks(ranks, cat, el){
  var html='';
  ranks.forEach(function(r,i){
    var tests = TESTS.filter(function(t){ return t.category===cat && t.level_key===r.level; });
    var inner = tests.length ? tests.map(renderCard).join('') : '<div style="text-align:center;padding:20px;color:rgba(232,237,242,0.3);font-size:13px">Coming soon</div>';
    html+='<div class="rank-card" id="rc'+r.id+'" style="animation:fi 0.3s '+(i*60)+'ms ease both">'
      +'<div class="rank-header" onclick="tog(\''+r.id+'\')">'
      +'<div style="display:flex;align-items:center;gap:14px"><div class="epaulette">'+stripes(r.stripes)+'</div>'
      +'<div><div style="font-size:14px;font-weight:600;color:#fff">'+r.label+'</div>'
      +'<div style="font-size:11px;color:rgba(232,237,242,0.4);margin-top:2px">'+tests.length+' теста</div></div></div>'
      +'<div class="chevron">▾</div></div>'
      +'<div class="rank-body"><div class="rank-inner">'+inner+'</div></div></div>';
  });
  document.getElementById(el).innerHTML=html;
}

function tog(id){
  var c=document.getElementById('rc'+id);
  c.classList.toggle('open');
}

function renderDeckRatings(){
  var html = '<div style="margin-top:28px">'
    + '<div style="font-size:11px;color:rgba(255,255,255,0.3);font-weight:700;letter-spacing:0.12em;text-transform:uppercase;text-align:center;margin-bottom:14px;display:flex;align-items:center;gap:10px">'
    + '<div style="flex:1;height:1px;background:rgba(255,255,255,0.07)"></div>'
    + '<span>Deck Ratings</span>'
    + '<div style="flex:1;height:1px;background:rgba(255,255,255,0.07)"></div>'
    + '</div>';
  DECK_RATINGS.forEach(function(r, i){
    var tests = TESTS.filter(function(t){ return t.category==='deck' && t.level_key===r.level; });
    var inner = tests.length ? tests.map(renderCard).join('') : '<div style="text-align:center;padding:20px;color:rgba(232,237,242,0.3);font-size:13px">Coming soon</div>';
    html += '<div class="rank-card" id="rc'+r.id+'" style="animation:fi 0.3s '+(i*60)+'ms ease both">'
      + '<div class="rank-header" onclick="tog(\''+r.id+'\');">'
      + '<div style="display:flex;align-items:center;gap:14px">'
      + '<div class="epaulette" style="background:linear-gradient(135deg,#1a2a3a,#243040)">'
      + '<i class="fa-solid fa-anchor" style="font-size:14px;color:rgba(232,160,32,0.6)"></i>'
      + '</div>'
      + '<div><div style="font-size:14px;font-weight:600;color:#fff">'+r.label+'</div>'
      + '<div style="font-size:11px;color:rgba(232,237,242,0.4);margin-top:2px">'+tests.length+' теста</div>'
      + '</div></div>'
      + '<div class="chevron">▾</div></div>'
      + '<div class="rank-body"><div class="rank-inner">'+inner+'</div></div>'
      + '</div>';
  });
  html += '</div>';
  document.getElementById('deckRatings').innerHTML = html;
}

function renderEngineRatings(){
  var html = '<div style="margin-top:28px">'
    + '<div style="font-size:11px;color:rgba(255,255,255,0.3);font-weight:700;letter-spacing:0.12em;text-transform:uppercase;text-align:center;margin-bottom:14px;display:flex;align-items:center;gap:10px">'
    + '<div style="flex:1;height:1px;background:rgba(255,255,255,0.07)"></div>'
    + '<span>Engine Ratings</span>'
    + '<div style="flex:1;height:1px;background:rgba(255,255,255,0.07)"></div>'
    + '</div>';
  ENGINE_RATINGS.forEach(function(r, i){
    var tests = TESTS.filter(function(t){ return t.category==='engine' && t.level_key===r.level; });
    var inner = tests.length ? tests.map(renderCard).join('') : '<div style="text-align:center;padding:20px;color:rgba(232,237,242,0.3);font-size:13px">Coming soon</div>';
    html += '<div class="rank-card" id="rc'+r.id+'" style="animation:fi 0.3s '+(i*60)+'ms ease both">'
      + '<div class="rank-header" onclick="tog(\''+r.id+'\');">'
      + '<div style="display:flex;align-items:center;gap:14px">'
      + '<div class="epaulette" style="background:linear-gradient(135deg,#1a2a3a,#243040)">'
      + '<i class="fa-solid fa-gear" style="font-size:14px;color:rgba(232,160,32,0.6)"></i>'
      + '</div>'
      + '<div><div style="font-size:14px;font-weight:600;color:#fff">'+r.label+'</div>'
      + '<div style="font-size:11px;color:rgba(232,237,242,0.4);margin-top:2px">'+tests.length+' теста</div>'
      + '</div></div>'
      + '<div class="chevron">▾</div></div>'
      + '<div class="rank-body"><div class="rank-inner">'+inner+'</div></div>'
      + '</div>';
  });
  html += '</div>';
  document.getElementById('engineRatings').innerHTML = html;
}

function showDept(d){
  var sr = document.getElementById('searchResults');
  if (sr) { sr.style.display='none'; sr.innerHTML=''; }
  document.getElementById('deptSelect').style.display='none';
  document.getElementById('deckDept').style.display=d==='deck'?'block':'none';
  document.getElementById('engineDept').style.display=d==='engine'?'block':'none';
  if(d==='deck') {
    renderRanks(RANKS,'deck','deckRanks');
    renderDeckRatings();
  } else {
    renderRanks(ENGINE,'engine','engineRanks');
    renderEngineRatings();
  }
}

function hideDept(){
  document.getElementById('deptSelect').style.display='block';
  document.getElementById('deckDept').style.display='none';
  document.getElementById('engineDept').style.display='none';
}

function selectLibraryTest(id, title){
  // Показва потвърждение ПРЕДИ реалния избор (POST /library/select) -
  // потребителят трябва изрично да потвърди коя тест избира.
  document.getElementById('confirmSelectTestName').textContent = title;
  document.getElementById('confirmSelectOverlay').dataset.testId = id;
  document.getElementById('confirmSelectOverlay').dataset.testTitle = title;
  document.getElementById('confirmSelectOverlay').classList.add('show');
}

function cancelSelectConfirm(){
  document.getElementById('confirmSelectOverlay').classList.remove('show');
}

function confirmSelectTest(){
  const overlay = document.getElementById('confirmSelectOverlay');
  const id = overlay.dataset.testId;
  overlay.classList.remove('show');
  fetch('/library/select', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({test_id:id})})
    .then(function(r){ return r.json(); })
    .then(function(d){
      if (d.gold_prompt_second) {
        showGoldSecondPrompt(d.first_test_title);
      } else if (d.success) {
        window.location.href = DASHBOARD_URL;
      } else {
        alert(d.message || 'Грешка при избора на тест.');
      }
    })
    .catch(function(){ alert('Грешка при избора на тест.'); });
}

function showGoldSecondPrompt(firstTitle){
  document.getElementById('goldSecondOverlay').classList.add('show');
}
function closeGoldSecondPrompt(){
  document.getElementById('goldSecondOverlay').classList.remove('show');
}

function openModal(id, title){
  if(LIB.window_active && LIB.selected_test_id===id){
    window.location.href=DASHBOARD_URL;
    return;
  }
  // Преизбирането вече е ВИНАГИ позволено (както при Basic/Plus) - преди
  // тук имаше 'if(LIB.window_active) return;', което тихо блокираше
  // отварянето на попъпа за друг тест, докато прозорецът е активен.
  pendingId=id;
  document.getElementById('testName').textContent=title;
  document.getElementById('overlay').classList.add('show');
}

function closeModal(){
  pendingId=null;
  document.getElementById('overlay').classList.remove('show');
}

function confirmSelect(){
  if(!pendingId) return;
  var btn=document.getElementById('nextBtn');
  btn.disabled=true; btn.textContent='...';
  fetch('/library/select',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({test_id:pendingId})})
  .then(function(r){return r.json();})
  .then(function(d){
    if (d.gold_prompt_second) {
      closeModal();
      btn.disabled=false; btn.textContent='Next';
      showGoldSecondPrompt(d.first_test_title);
    } else if(d.success){ window.location.href=DASHBOARD_URL; }
    else{ btn.disabled=false; btn.textContent='Next'; alert(d.message||'Грешка'); }
  })
  .catch(function(){ btn.disabled=false; btn.textContent='Next'; alert('Грешка в мрежата'); });
}

function openUpgradePopup(){
  document.getElementById('upgradeOverlay').style.display='flex';
}
function closeUpgradePopup(){
  document.getElementById('upgradeOverlay').style.display='none';
}

document.addEventListener('click', function() {
  document.querySelectorAll('.lib-ddm').forEach(function(d){ d.style.display='none'; });
});

var _searchTimer = null;
var _searchController = null;
var _searchGen = 0;

function _positionSearchResults() {
  var input = document.getElementById('libSearch');
  var el = document.getElementById('searchResults');
  if (!input || !el) return;
  var rect = input.getBoundingClientRect();
  el.style.position = 'fixed';
  el.style.top = (rect.bottom + 4) + 'px';
  el.style.left = rect.left + 'px';
  el.style.width = rect.width + 'px';
  el.style.zIndex = '99999';
}

// Hide on scroll
document.addEventListener('scroll', function() {
  var el = document.getElementById('searchResults');
  if (el) el.style.display = 'none';
}, true);

function filterTests(q){
  var el = document.getElementById('searchResults');
  if (!q || q.length < 2) {
    clearTimeout(_searchTimer);
    if (_searchController) _searchController.abort();
    _searchGen++; // инвалидира pending fetch
    if (el) { el.style.display='none'; el.innerHTML=''; }
    _searchNavIdx = -1;
    return;
  }
  clearTimeout(_searchTimer);
  if (_searchController) _searchController.abort();
  _searchController = new AbortController();
  var signal = _searchController.signal;
  var gen = ++_searchGen;
  _searchTimer = setTimeout(function() {
    fetch('/library/search?q=' + encodeURIComponent(q), {signal: signal})
      .then(function(r){ return r.json(); })
      .then(function(found){
        if (gen !== _searchGen) return; // стара заявка
        _positionSearchResults();
        _searchNavIdx = -1;
        el.style.display = 'block';
        if (!found.length) {
          el.innerHTML = '<p style="color:rgba(232,237,242,0.4);font-size:13px;padding:8px">Няма намерени резултати</p>';
          return;
        }
        el.innerHTML = '';
        found.forEach(function(t){
          var badge = t.is_demo
            ? '<span style="background:#E8A020;color:#071a2e;font-size:9px;font-weight:700;padding:1px 6px;border-radius:10px;margin-right:6px">DEMO</span>'
            : '<span style="background:rgba(67,158,178,0.2);color:#439EB2;font-size:9px;font-weight:700;padding:1px 6px;border-radius:10px;margin-right:6px">' + (t.category||'').toUpperCase() + '</span>';
          var item = document.createElement('div');
          item.setAttribute('data-id', t.id);
          item.style.cssText = 'padding:10px 12px;cursor:pointer;border-radius:6px;display:flex;align-items:center;justify-content:space-between';
          item.innerHTML = '<div style="display:flex;align-items:center">' + badge + '<span style="color:#fff;font-size:13px">' + t.title + '</span></div>'
            + '<span style="color:rgba(232,237,242,0.3);font-size:11px">' + t.question_count + ' q</span>';
          item.onmouseover = function(){ this.style.background='rgba(232,160,32,0.08)'; };
          item.onmouseout = function(){ this.style.background='transparent'; };
          (function(tid, tcat){ item.onclick = function(){ searchSelectTest(tid, tcat); }; })(t.id, t.category||'deck');
          el.appendChild(item);
        });
      })
      .catch(function(e){ if (e.name !== 'AbortError') el.style.display='none'; });
  }, 250);
}

function searchSelectTest(id, category) {
  // Stop any pending search
  clearTimeout(_searchTimer);
  if (_searchController) _searchController.abort();
  _searchGen++;

  // Hide dropdown but keep input text
  var el = document.getElementById('searchResults');
  if (el) { el.style.display = 'none'; el.innerHTML = ''; }
  _searchNavIdx = -1;

  // Navigate
  var dept = category || 'deck';
  var test = TESTS.find(function(t){ return t.id === id; });
  if (!test) return;

  showDept(dept);

  setTimeout(function(){
    var ranks = dept === 'deck' ? RANKS : ENGINE;
    var rank = ranks.find(function(r){ return r.level === test.level_key; });
    if (rank) {
      var rankCard = document.getElementById('rc' + rank.id);
      if (rankCard && !rankCard.classList.contains('open')) tog(rank.id);
    }
    setTimeout(function(){
      var card = document.getElementById('tc' + id);
      if (card) {
        card.scrollIntoView({behavior: 'smooth', block: 'center'});
        card.style.outline = '2px solid rgba(232,160,32,0.9)';
        card.style.borderRadius = '10px';
        setTimeout(function(){ card.style.outline = ''; }, 2500);
      }
    }, 300);
  }, 400);
}


// Отваря/затваря dropdown в library
var _activeDD = null;
var _activeDDOrigin = null;

function libToggleDD(btn) {
  // Затвори всички
  if (_activeDD) {
    _activeDDOrigin.appendChild(_activeDD);
    _activeDD.style.display = 'none';
    _activeDD.style.position = 'absolute';
    _activeDD.style.top = 'calc(100% + 6px)';
    _activeDD.style.bottom = '';
    _activeDD.style.left = '';
    _activeDD = null;
    _activeDDOrigin = null;
  }
  var dd = btn.nextElementSibling;
  if (!dd || !dd.classList.contains('lib-ddm')) return;
  var isOpen = dd.style.display === 'block';
  if (isOpen) return;

  // Позиционираме спрямо btn в body
  var rect = btn.getBoundingClientRect();
  _activeDDOrigin = btn.parentElement;
  document.body.appendChild(dd);
  dd.style.position = 'fixed';
  dd.style.left = '';
  dd.style.right = (window.innerWidth - rect.right) + 'px';
  dd.style.zIndex = '99999';

  // Измерваме реалната височина невидимо, за да решим посоката на отваряне —
  // без това, dropdown-и близо до долния край на екрана (последните карти в
  // списъка) излизаха извън видимата зона ("залепваха" в дъното), вместо да
  // се отворят нагоре, където има достатъчно място.
  dd.style.visibility = 'hidden';
  dd.style.top = '0px';
  dd.style.bottom = '';
  dd.style.display = 'block';
  var ddHeight = dd.offsetHeight;
  dd.style.display = 'none';

  var spaceBelow = window.innerHeight - rect.bottom - 6;
  var spaceAbove = rect.top - 6;

  if (spaceBelow < ddHeight && spaceAbove > spaceBelow) {
    dd.style.top = '';
    dd.style.bottom = (window.innerHeight - rect.top + 6) + 'px';
  } else {
    dd.style.bottom = '';
    dd.style.top = (rect.bottom + 6) + 'px';
  }

  dd.style.display = 'block';
  dd.style.visibility = 'visible';
  _activeDD = dd;
}

// Mistakes клик — проверява дали има грешки
async function libMistakesClick(el) {
  var tid = el.getAttribute('data-tid');
  if (!tid) return;
  await loadErrorsData(parseInt(tid));
  if (ERRORS_DATA[parseInt(tid)]) {
    window.location.href = '/test/'+tid+'/mistakes';
  } else {
    el.innerHTML = '<span class="lib-dmi">❌</span><div><p class="lib-dmt" style="color:#94a3b8;font-style:italic">No mistakes yet</p><p class="lib-dms">Solve at least 2 tests</p></div>';
    setTimeout(function(){ document.querySelectorAll('.lib-ddm').forEach(function(d){d.style.display='none';}); }, 1800);
  }
}

// helpers за errors статус
var ERRORS_DATA = {};
async function loadErrorsData(testId) {
  try {
    const res = await fetch('/dashboard/test-errors-status?test_id=' + testId);
    const data = await res.json();
    ERRORS_DATA[testId] = data.has_errors;
  } catch(e) { ERRORS_DATA[testId] = false; }
}

// ── INLINE PREMIUM TOAST за library ──
let _libPremTimer = null;
function showLibPremiumToast(evt) {
  evt.stopPropagation();
  const btn = evt.currentTarget;
  let t = document.getElementById('libPremToast');
  if (!t) {
    t = document.createElement('div');
    t.id = 'libPremToast';
    t.style.cssText = 'position:fixed;z-index:9999;background:#1C2541;border:1px solid rgba(99,91,255,0.5);border-radius:10px;padding:10px 14px;box-shadow:0 4px 20px rgba(0,0,0,0.5);max-width:230px;opacity:0;transition:opacity 0.2s ease;pointer-events:none';
    t.innerHTML = '<div style="display:flex;align-items:flex-start;gap:8px"><i class="fa-solid fa-lock" style="color:#635BFF;font-size:12px;margin-top:1px;flex-shrink:0"></i><div><p style="font-size:11px;font-weight:700;color:#e8edf2;margin:0 0 2px">Premium Feature</p><p style="font-size:10px;color:rgba(232,237,242,0.55);margin:0">Активирай абонамент за достъп до този тест.</p></div></div>';
    document.body.appendChild(t);
  }
  clearTimeout(_libPremTimer);
  const r = btn.getBoundingClientRect();
  t.style.display = 'block';
  t.style.opacity = '0';
  requestAnimationFrame(() => {
    const tw = t.offsetWidth || 230;
    let left = r.left;
    if (left + tw > window.innerWidth - 16) left = window.innerWidth - tw - 16;
    t.style.left = left + 'px';
    t.style.top = (r.bottom + 6) + 'px';
    requestAnimationFrame(() => { t.style.opacity = '1'; });
  });
  _libPremTimer = setTimeout(() => {
    t.style.opacity = '0';
    setTimeout(() => { t.style.display = 'none'; }, 200);
  }, 2800);
}

// --- Search keyboard navigation ---
var _searchNavIdx = -1;

function searchKeyNav(e) {
  var el = document.getElementById('searchResults');
  var input = document.getElementById('libSearch');

  if (e.key === 'Escape') {
    if (el) el.style.display = 'none';
    _searchNavIdx = -1;
    return;
  }

  if (e.key === 'Enter') {
    e.preventDefault();
    var q = input ? input.value.trim() : '';
    // If dropdown is visible and item selected — click it
    if (el && el.style.display !== 'none') {
      var items = el.querySelectorAll('div[data-id]');
      if (_searchNavIdx >= 0 && items[_searchNavIdx]) {
        items[_searchNavIdx].click();
        return;
      }
      // No selection — click first item
      if (items.length) {
        items[0].click();
        return;
      }
    }
    // Dropdown hidden but has text — re-search and go to first result
    if (q.length >= 2) {
      fetch('/library/search?q=' + encodeURIComponent(q))
        .then(function(r){ return r.json(); })
        .then(function(found){
          if (found.length) {
            searchSelectTest(found[0].id, found[0].category);
          }
        });
    }
    return;
  }

  if (!el || el.style.display === 'none') return;
  var items = el.querySelectorAll('div[data-id]');
  if (!items.length) return;

  if (e.key === 'ArrowDown') {
    e.preventDefault();
    _searchNavIdx = Math.min(_searchNavIdx + 1, items.length - 1);
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    _searchNavIdx = Math.max(_searchNavIdx - 1, 0);
  } else {
    return;
  }

  items.forEach(function(item, i) {
    item.style.background = i === _searchNavIdx ? 'rgba(232,160,32,0.15)' : 'transparent';
    item.style.borderRadius = '6px';
  });
  if (items[_searchNavIdx]) {
    items[_searchNavIdx].scrollIntoView({block:'nearest'});
  }
}

document.addEventListener('click', function(e) {
  var el = document.getElementById('searchResults');
  var input = document.getElementById('libSearch');
  if (!el) return;
  if (!el.contains(e.target) && e.target !== input) {
    el.style.display = 'none';
    _searchNavIdx = -1;
  }
});

document.addEventListener('scroll', function() {
  var el = document.getElementById('searchResults');
  if (el) el.style.display = 'none';
  _searchNavIdx = -1;
}, true);
