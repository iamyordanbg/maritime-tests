// Library страница - извлечена логика (виж app/templates/user/library.html за данните)
function closeAwaitingTestPopup() {
  document.getElementById('awaitingTestOverlay').classList.remove('show');
}
// Popup-ът "Избери тест сега" беше премахнат по изрично желание - потребителят
// иска директен достъп до библиотеката, без прекъсващи съобщения, дори когато
// LIB.needs_first_selection е true.
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
  if(n===0) return '<div class="lib-rank-zero-icon">⬟</div>';
  var s='';
  for(var i=0;i<n;i++) s+='<div class="stripe" style="width:'+(n===4?18:n===3?16:n===2?14:12)+'px"></div>';
  return s;
}

function buildLibDD(tid, isPremiumUser, isDemoTest) {
  // Demo тест = "Simulator only" (виж landing.html cmp-таблицата и
  // demo.js renderTestCard) - Test/Mix/Mistakes ВИНАГИ заключени за demo,
  // независимо дали потребителят е premium - демото е upsell преглед, не
  // пълноценен режим. freeMode тук форсира заключения вид за Test/Mix/
  // Mistakes и за demo тестове, огледално на landing демо картата.
  var freeMode = !isPremiumUser || isDemoTest;
  var rows = '';
  // Test
  rows += freeMode
    ? '<div class="lib-dml dim"><span class="lib-dmi">📝</span><div><p class="lib-dmt">Test</p><p class="lib-dms">'+(isDemoTest?'Subscription required':'All questions in order')+'</p></div></div>'
    : '<a href="/test/'+tid+'" class="lib-dml"><span class="lib-dmi">📝</span><div><p class="lib-dmt">Test</p><p class="lib-dms">All questions in order</p></div></a>';
  // Mix
  rows += freeMode
    ? '<div class="lib-dml dim"><span class="lib-dmi">🔀</span><div><p class="lib-dmt">Mix</p><p class="lib-dms">'+(isDemoTest?'Subscription required':'Questions shuffled')+'</p></div></div>'
    : '<a href="/test/'+tid+'?shuffle=true" class="lib-dml"><span class="lib-dmi">🔀</span><div><p class="lib-dmt">Mix</p><p class="lib-dms">Questions shuffled</p></div></a>';
  // Mistakes — заключено за demo (огледално на landing), dim-click за free,
  // активен за premium non-demo (errors се проверяват при клик)
  rows += freeMode
    ? '<div class="lib-dml dim"><span class="lib-dmi">❌</span><div><p class="lib-dmt">Mistakes</p><p class="lib-dms">'+(isDemoTest?'Subscription required':'Only questions you got wrong')+'</p></div></div>'
    : '<div class="lib-dml dim-click" data-tid="'+tid+'" onclick="libMistakesClick(this)"><span class="lib-dmi">❌</span><div><p class="lib-dmt">Mistakes</p><p class="lib-dms">Only questions you got wrong</p></div></div>';
  // Simulator — винаги активен, ОСВЕН за Free план потребител, който вече
  // е изчерпал дневния си лимит (1 симулатор/ден) за истински (не demo)
  // тест - вместо навигация към страница, която веднага го връща назад,
  // показваме малък inline toast директно тук ("Daily limit reached").
  // За DEMO тест води към /demo/test/.../mode=simulator (същия "upsell"
  // flow като landing страницата - показва прост резултат + бутон
  // "Choose Subscription", НЕ пълен детайлен report), не към обикновения
  // /test/.../simulator (логнат, с пълен report) - демо трябва да подтиква
  // към абонамент, дори за вече логнат потребител, достигнал го от Library.
  var simUrl = isDemoTest ? ('/demo/test/'+tid+'?mode=simulator') : ('/test/'+tid+'/simulator');
  var simLimitReached = !isDemoTest && !isPremiumUser && LIB.simulator_available_today === false;
  rows += simLimitReached
    ? '<div class="lib-dml lib-ddm-simulator" onclick="showLibInlineToast(event,\'Daily Limit Reached\',\'Your Free plan allows 1 simulator test per day. Please try again tomorrow.\')"><span class="lib-dmi">🎯</span><div><p class="lib-dmt">Simulator</p><p class="lib-dms">45 questions · 60 minutes</p></div></div>'
    : '<a href="'+simUrl+'" class="lib-dml lib-ddm-simulator"><span class="lib-dmi">🎯</span><div><p class="lib-dmt">Simulator</p><p class="lib-dms">45 questions · 60 minutes</p></div></a>';

  return '<div class="ddm lib-ddm">'
    + '<div class="lib-ddm-header"><p class="lib-ddm-header-title">Choose Mode</p></div>'
    + rows + '</div>';
}

function renderCard(t){
  var sel = (LIB.selected_test_ids || []).indexOf(t.id) !== -1;
  var safeTitle = t.title.replace(/\\/g,'\\\\').replace(/'/g,"\\'");

  if (GOLD_ACTIVATION) {
    // Активиране на НОВ Gold/Custom код в момента (избор на 1-ви/2-ри тест
    // за самата активация) - отделен, еднократен flow, не browsing на вече
    // активна библиотека, затова остава непроменен: "Are you sure..."
    // confirm през selectLibraryTest(), с изключение на demo тестовете,
    // които директно отварят dropdown-а.
    var pbadge = sel
      ? '<span class="lib-badge lib-badge--selected">✓ ИЗБРАН</span>'
      : t.is_demo
        ? '<span class="lib-badge lib-badge--demo">DEMO</span>'
        : '';
    var pCardClass = sel ? 'lib-card--selected' : 'lib-card--premium';
    var pBtn;
    if (t.is_demo) {
      pBtn = '<div class="lib-dd-wrap">'
        + '<button onclick="event.stopPropagation();libToggleDD(this)" class="lib-btn lib-btn--load">Open ▾</button>'
        + buildLibDD(t.id, false, t.is_demo)
        + '</div>';
    } else if (sel && !LIB.awaiting_selection) {
      pBtn = '<button onclick="window.location.href=DASHBOARD_URL" class="lib-btn lib-btn--load">Load</button>';
    } else {
      pBtn = '<button onclick="selectLibraryTest('+t.id+',\''+safeTitle+'\')" class="lib-btn lib-btn--load">Load</button>';
    }
    return '<div class="tcard '+pCardClass+'" id="tc'+t.id+'"><div>'+pbadge
      +'<div class="lib-title">'+t.title+'</div>'
      +'<div class="lib-question-count">'+t.question_count+' questions</div>'
      +'</div>'+pBtn+'</div>';
  }

  if (LIB.is_premium) {
    // Тест, който НЕ е избран/активен за конкретния платен потребител и
    // не е demo -> визуално ЗАКЛЮЧЕН (бледа карта, бадж "Premium", Load
    // бутон води към цените на плановете - upsell за допълнителен тест).
    // Demo тестовете се държат точно както в самата demo секция - директен
    // dropdown достъп (Test/Mix/Mistakes/Simulator), без нужда от избор.
    // Избраният/активен тест -> бадж "Заредено", Load отвежда директно
    // към dashboard-а на потребителя.
    var pLocked = !sel && !t.is_demo;

    var pbadge = sel
      ? '<span class="lib-badge lib-badge--selected">Заредено</span>'
      : t.is_demo
        ? '<span class="lib-badge lib-badge--demo">DEMO</span>'
        : pLocked
          ? '<span class="lib-badge lib-badge--premium">Premium</span>'
          : '';
    var pCardClass = sel
      ? 'lib-card--selected'
      : pLocked
        ? 'lib-card--locked'
        : 'lib-card--premium';
    var pBtn;
    if (t.is_demo) {
      pBtn = '<div class="lib-dd-wrap">'
        + '<button onclick="event.stopPropagation();libToggleDD(this)" class="lib-btn lib-btn--load">Open ▾</button>'
        + buildLibDD(t.id, true, t.is_demo)
        + '</div>';
    } else if (pLocked) {
      pBtn = '<button onclick="window.location.href=PLANS_URL" class="lib-btn lib-btn--locked">Load</button>';
    } else if (sel && !LIB.awaiting_selection) {
      pBtn = '<button onclick="window.location.href=DASHBOARD_URL" class="lib-btn lib-btn--load">Load</button>';
    } else {
      pBtn = '<button onclick="selectLibraryTest('+t.id+',\''+safeTitle+'\')" class="lib-btn lib-btn--load">Load</button>';
    }
    return '<div class="tcard '+pCardClass+'" id="tc'+t.id+'"><div>'
      +'<div class="lib-badge-row">'+pbadge+'</div>'
      +'<div class="lib-title'+(pLocked?' lib-title--locked':'')+'">'+t.title+'</div>'
      +'<div class="lib-question-count">'+t.question_count+' questions</div>'
      +'</div>'+pBtn+'</div>';
  }

  // ----- Free-план поток (непроменено legacy поведение, демо включено) -----
  var locked = LIB.window_active && !sel && !t.is_demo;

  // Бадж
  var badge = sel
    ? '<span class="lib-badge lib-badge--selected">✓ ИЗБРАН</span>'
    : t.is_demo
      ? '<span class="lib-badge lib-badge--demo">DEMO</span>'
      : locked
        ? '<span class="lib-badge lib-badge--locked-premium">🔒 PREMIUM</span>'
        : '';

  // Цвят на картата
  var cardClass = sel
    ? 'lib-card--selected'
    : locked
      ? 'lib-card--locked-free'
      : 'lib-card--premium';

  var btn;
  if (locked) {
    // Заключен — само Premium бутон без dropdown
    btn = '<button onclick="window.location.href=PLANS_URL" class="lib-btn lib-btn--locked">Open</button>';
  } else if (!LIB.window_active && !t.is_demo && !sel) {
    // Няма активен прозорец и не е demo → Load за избор на тест
    btn = '<button onclick="openModal('+t.id+',\''+safeTitle+'\')" class="lib-btn lib-btn--load">Load</button>';
  } else {
    // Demo или избран/свободен (free) → бутон с dropdown (само за демо преглед)
    var label = 'Open';
    // Заредения (sel) тест, чийто дневен лимит на симулатора вече е
    // изчерпан - кликването на "Open" вече НЕ отваря dropdown-а изобщо,
    // а директно показва известие за дневния лимит + препратка към избор
    // на план, вместо потребителят да трябва да влиза в Choose Mode и чак
    // после да научи от Simulator опцията.
    var simLimitReachedForCard = sel && !t.is_demo && LIB.simulator_available_today === false;
    if (simLimitReachedForCard) {
      btn = '<button onclick="showLibInlineToast(event,\'Daily Limit Reached\',\'Your Free plan allows 1 simulator test per day. If you want full access, please choose a suitable plan for your needs.\')" class="lib-btn lib-btn--load">'
        + label + '</button>';
    } else {
      btn = '<div class="lib-dd-wrap">'
        + '<button onclick="event.stopPropagation();libToggleDD(this)" class="lib-btn lib-btn--load">'
        + label
        + '</button>'
        + buildLibDD(t.id, false, t.is_demo)
        + '</div>';
    }
  }

  return '<div class="tcard '+cardClass+'" id="tc'+t.id+'"><div>'+badge
    +'<div class="lib-title'+(locked?' lib-title--locked':'')+'">'+t.title+'</div>'
    +'<div class="lib-question-count">'+t.question_count+' questions</div>'
    +'</div>'+btn+'</div>';
}

function renderRanks(ranks, cat, el){
  var html='';
  ranks.forEach(function(r,i){
    var tests = TESTS.filter(function(t){ return t.category===cat && t.level_key===r.level; });
    var inner = tests.length ? tests.map(renderCard).join('') : '<div class="lib-empty-slot">Coming soon</div>';
    // animation-delay е динамично изчислена стойност по индекс (стъпаловиден
    // fade-in ефект) - не може да е статичен CSS клас, затова остава inline.
    html+='<div class="rank-card" id="rc'+r.id+'" style="animation:fi 0.3s '+(i*60)+'ms ease both">'
      +'<div class="rank-header" onclick="tog(\''+r.id+'\')">'
      +'<div class="lib-rank-header-row"><div class="epaulette">'+stripes(r.stripes)+'</div>'
      +'<div><div class="lib-rank-title">'+r.label+'</div>'
      +'<div class="lib-rank-subtitle">'+tests.length+' теста</div></div></div>'
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
  var html = '<div class="lib-ratings-section">'
    + '<div class="lib-ratings-divider-row">'
    + '<div class="lib-ratings-divider-line"></div>'
    + '<span>Deck Ratings</span>'
    + '<div class="lib-ratings-divider-line"></div>'
    + '</div>';
  DECK_RATINGS.forEach(function(r, i){
    var tests = TESTS.filter(function(t){ return t.category==='deck' && t.level_key===r.level; });
    var inner = tests.length ? tests.map(renderCard).join('') : '<div class="lib-empty-slot">Coming soon</div>';
    html += '<div class="rank-card" id="rc'+r.id+'" style="animation:fi 0.3s '+(i*60)+'ms ease both">'
      + '<div class="rank-header" onclick="tog(\''+r.id+'\');">'
      + '<div class="lib-rank-header-row">'
      + '<div class="epaulette lib-rating-epaulette">'
      + '<i class="fa-solid fa-anchor lib-rating-icon"></i>'
      + '</div>'
      + '<div><div class="lib-rank-title">'+r.label+'</div>'
      + '<div class="lib-rank-subtitle">'+tests.length+' теста</div>'
      + '</div></div>'
      + '<div class="chevron">▾</div></div>'
      + '<div class="rank-body"><div class="rank-inner">'+inner+'</div></div>'
      + '</div>';
  });
  html += '</div>';
  document.getElementById('deckRatings').innerHTML = html;
}

function renderEngineRatings(){
  var html = '<div class="lib-ratings-section">'
    + '<div class="lib-ratings-divider-row">'
    + '<div class="lib-ratings-divider-line"></div>'
    + '<span>Engine Ratings</span>'
    + '<div class="lib-ratings-divider-line"></div>'
    + '</div>';
  ENGINE_RATINGS.forEach(function(r, i){
    var tests = TESTS.filter(function(t){ return t.category==='engine' && t.level_key===r.level; });
    var inner = tests.length ? tests.map(renderCard).join('') : '<div class="lib-empty-slot">Coming soon</div>';
    html += '<div class="rank-card" id="rc'+r.id+'" style="animation:fi 0.3s '+(i*60)+'ms ease both">'
      + '<div class="rank-header" onclick="tog(\''+r.id+'\');">'
      + '<div class="lib-rank-header-row">'
      + '<div class="epaulette lib-rating-epaulette">'
      + '<i class="fa-solid fa-gear lib-rating-icon"></i>'
      + '</div>'
      + '<div><div class="lib-rank-title">'+r.label+'</div>'
      + '<div class="lib-rank-subtitle">'+tests.length+' теста</div>'
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
  hideLibInlineToast();
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
          el.innerHTML = '<p class="lib-search-empty">Няма намерени резултати</p>';
          return;
        }
        el.innerHTML = '';
        found.forEach(function(t){
          var badge = t.is_demo
            ? '<span class="lib-search-badge lib-search-badge--demo">DEMO</span>'
            : '<span class="lib-search-badge lib-search-badge--category">' + (t.category||'').toUpperCase() + '</span>';
          var item = document.createElement('div');
          item.setAttribute('data-id', t.id);
          item.className = 'lib-search-item';
          item.innerHTML = '<div class="lib-search-item-row">' + badge + '<span class="lib-search-item-title">' + t.title + '</span></div>'
            + '<span class="lib-search-item-count">' + t.question_count + ' q</span>';
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

function closeActiveLibDD() {
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
}

function libToggleDD(btn) {
  closeActiveLibDD();
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
    el.innerHTML = '<span class="lib-dmi">❌</span><div><p class="lib-dmt lib-dmt--muted">No mistakes yet</p><p class="lib-dms">Solve at least 2 tests</p></div>';
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

// ── Обобщен (generic) inline toast за библиотеката - параметризиран по
// title/text, за да се преизползва навсякъде, вместо copy-paste версия
// за всеки отделен случай (Anti-Duplication DRY правилото). ──
function hideLibInlineToast() {
  var t = document.getElementById('libInlineToast');
  if (!t || t.style.display === 'none') return;
  clearTimeout(_libToastTimer);
  t.style.opacity = '0';
  setTimeout(() => { t.style.display = 'none'; }, 200);
}

let _libToastTimer = null;
function showLibInlineToast(evt, title, text) {
  evt.stopPropagation();
  evt.preventDefault();
  const btn = evt.currentTarget;
  const r = btn.getBoundingClientRect();
  closeActiveLibDD();
  let t = document.getElementById('libInlineToast');
  if (!t) {
    t = document.createElement('div');
    t.id = 'libInlineToast';
    t.className = 'lib-toast';
    document.body.appendChild(t);
  }
  t.innerHTML = '<div class="lib-toast-row"><i class="fa-solid fa-circle-info lib-toast-icon"></i><div><p class="lib-toast-title"></p><p class="lib-toast-text"></p></div></div>';
  t.querySelector('.lib-toast-title').textContent = title;
  t.querySelector('.lib-toast-text').textContent = text;
  clearTimeout(_libToastTimer);
  // position/opacity/display тук са runtime изчислени стойности (зависят от
  // позицията на кликнатия елемент) - не могат да са статичен CSS клас,
  // затова остават директни JS style property set-вания.
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
  // Известието стои МИНИМУМ 10 секунди (или до клик другаде - виж
  // разширения глобален document click listener по-горе), не 2.8с както
  // преди - потребителят поиска достатъчно време да го прочете спокойно.
  _libToastTimer = setTimeout(hideLibInlineToast, 10000);
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
    item.classList.toggle('lib-search-item--active', i === _searchNavIdx);
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
