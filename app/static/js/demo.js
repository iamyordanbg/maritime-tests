// app/static/js/demo.js
// Demo page — извлечена от app/templates/demo.html (Правило 1+2).
// Очаква window.DEMO_DATA = {tests}

var demoTests = window.DEMO_DATA.tests;
const RANKS = [
  {id:'master',bg:'Captain / Master Mariner',en:'Captain',level:'Management Level',stripes:4,tests:[{t:'Bridge Management',s:'Management · 60 questions',demo:true},{t:'Advanced Stability',s:'Management · 45 questions'},{t:'Maritime Law & Conventions',s:'Management · 50 questions'}]},
  {id:'chief',bg:'Chief Officer',en:'Chief Officer',level:'Management Level',stripes:3,tests:[{t:'Cargo Operations',s:'Management · 55 questions',demo:true},{t:'Ship Stability',s:'Management · 50 questions'}]},
  {id:'second',bg:'Second Officer',en:'Second Officer',level:'Operational Level',stripes:2,tests:[{t:'Navigation — COLREG',s:'Operational · 60 questions',demo:true},{t:'Chart Work & ECDIS',s:'Operational · 45 questions'}]},
  {id:'third',bg:'Third Officer',en:'Third Officer',level:'Operational Level',stripes:1,tests:[{t:'Basic Navigation',s:'Operational · 50 questions',demo:true},{t:'Firefighting & LSA',s:'Operational · 40 questions'}]},
  {id:'cadet',bg:'Deck Cadet',en:'Deck Cadet',level:'Academy Level',stripes:0,tests:[{t:'Introduction to Navigation',s:'Academy · 40 questions',demo:true},{t:'Seamanship Basics',s:'Academy · 35 questions'}]},
];

const ENGINE_RANKS = [
  {id:'chiefeng',bg:'Chief Engineer',en:'Chief Engineer',level:'Management Level',stripes:4,tests:[{t:'Engine Room Management',s:'Management · 60 questions',demo:true},{t:'Marine Diesel Engines',s:'Management · 45 questions'},{t:'Maritime Law & Conventions',s:'Management · 50 questions'}]},
  {id:'secondeng',bg:'Second Engineer',en:'Second Engineer',level:'Management Level',stripes:3,tests:[{t:'Auxiliary Machinery',s:'Management · 55 questions',demo:true},{t:'Engine Operations',s:'Management · 50 questions'}]},
  {id:'electrical',bg:'ETO',en:'Electrical Officer',level:'',stripes:3,tests:[{t:'Marine Electrical Systems',s:'Management · 55 questions',demo:true},{t:'Automation & Control Systems',s:'Management · 45 questions'}]},
  {id:'thirdeng',bg:'Third Engineer',en:'Third Engineer',level:'Operational Level',stripes:2,tests:[{t:'Marine Electrotechnology',s:'Operational · 60 questions',demo:true},{t:'Pumps & Piping Systems',s:'Operational · 45 questions'}]},
  {id:'fourtheng',bg:'Fourth Engineer',en:'Fourth Engineer',level:'Operational Level',stripes:1,tests:[{t:'Basic Engineering',s:'Operational · 50 questions',demo:true},{t:'Firefighting & LSA',s:'Operational · 40 questions'}]},
  {id:'enginecadet',bg:'Engine Cadet',en:'Engine Cadet',level:'Academy Level',stripes:0,tests:[{t:'Introduction to Marine Engineering',s:'Academy · 40 questions',demo:true},{t:'Engineering Basics',s:'Academy · 35 questions'}]},
];

const openRanks = {};
const rankLevelMap = {master:'management',chief:'management',second:'operational',third:'operational',cadet:'operational',chiefeng:'management',secondeng:'management',electrical:'eto',thirdeng:'operational',fourtheng:'operational',enginecadet:'operational'};

function stripes(n){
  if(n===0) return '<div style="font-size:14px;color:rgba(232,160,32,0.6)">⬟</div>';
  return Array.from({length:n}).map(()=>'<div class="stripe" style="width:'+(n===4?18:n===3?16:n===2?14:12)+'px"></div>').join('');
}

function getRealTests(rankId, category) {
  category = category || 'deck';
  const levelKey = rankLevelMap[rankId] || 'operational';
  return demoTests.filter(t => t.category === category && t.level_key === levelKey).sort((a,b) => (b.is_demo?1:0)-(a.is_demo?1:0));
}

function renderTestCard(t) {
  if (t.is_demo) {
    return `<div style="background:rgba(232,160,32,0.08);border:1.5px solid rgba(232,160,32,0.45);border-radius:12px;padding:14px 16px;display:flex;justify-content:space-between;align-items:center">
      <div>
        <span style="background:#e8a020;color:#071a2e;font-size:9px;font-weight:700;padding:2px 8px;border-radius:20px;letter-spacing:0.05em">★ DEMO</span>
        <div style="font-size:14px;font-weight:600;color:#fff;margin-top:4px">${t.title}</div>
        <div style="font-size:11px;color:rgba(232,237,242,0.5);margin-top:3px">${t.question_count} questions · Free access</div>
      </div>
      <div style="position:relative;flex-shrink:0;overflow:visible">
        <button onclick="event.stopPropagation();toggleDD(this)" style="background:#e8a020;color:#071a2e;border:none;border-radius:8px;padding:7px 14px;font-size:11px;font-weight:600;cursor:pointer;white-space:nowrap;width:96px;box-sizing:border-box;display:inline-flex;align-items:center;justify-content:center;gap:4px">
          Load <span style="font-size:9px;display:inline-block;transition:transform 0.2s">▾</span>
        </button>
        <div class="ddm" style="display:none;position:absolute;right:0;top:calc(100% + 6px);z-index:9999;background:rgba(10,24,47,0.98);border:1px solid rgba(232,160,32,0.3);border-radius:12px;min-width:225px;box-shadow:0 20px 60px rgba(0,0,0,0.85)">
          <div style="padding:8px 14px 6px;border-bottom:1px solid rgba(255,255,255,0.06)"><p style="font-size:9px;color:rgba(232,160,32,0.75);font-weight:700;letter-spacing:0.1em;text-transform:uppercase;margin:0">Choose Mode</p></div>
          <div class="dml" style="opacity:0.35;cursor:not-allowed;pointer-events:none"><span class="dmi">📝</span><div><p class="dmt">Test</p><p class="dms">Subscription required</p></div></div>
          <div class="dml" style="opacity:0.35;cursor:not-allowed;pointer-events:none"><span class="dmi">🔀</span><div><p class="dmt">Mix</p><p class="dms">Subscription required</p></div></div>
          <div class="dml" style="opacity:0.35;cursor:not-allowed;pointer-events:none"><span class="dmi">❌</span><div><p class="dmt">Mistakes</p><p class="dms">Subscription required</p></div></div>
          <a href="/demo/test/${t.id}?mode=simulator" class="dml" style="border-bottom:none"><span class="dmi">🎯</span><div><p class="dmt">Simulator</p><p class="dms">45 questions · 60 minutes</p></div></a>
        </div>
      </div>
    </div>`;
  } else {
    return `<div style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.07);border-radius:12px;padding:14px 16px;display:flex;justify-content:space-between;align-items:center">
      <div style="opacity:0.5">
        <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px"><i class="fa-solid fa-lock" style="font-size:9px;color:#64748b"></i><span style="font-size:9px;color:#64748b;letter-spacing:0.05em;text-transform:uppercase">Subscription required</span></div>
        <div style="font-size:13px;font-weight:500;color:#94a3b8">${t.title}</div>
        <div style="font-size:11px;color:rgba(255,255,255,0.25);margin-top:3px">${t.question_count} questions</div>
      </div>
      <button onclick="window.location='/register'" style="background:transparent;color:#64748b;border:1px solid rgba(255,255,255,0.1);border-radius:8px;padding:7px 14px;font-size:11px;font-weight:600;cursor:pointer;white-space:nowrap;flex-shrink:0;transition:all 0.2s;width:96px;box-sizing:border-box" onmouseover="this.style.borderColor='#e8a020';this.style.color='#e8a020'" onmouseout="this.style.borderColor='rgba(255,255,255,0.1)';this.style.color='#64748b'">Load</button>
    </div>`;
  }
}

function renderDeckRanks(){
  document.getElementById('deckRanks').innerHTML = RANKS.map((r,i)=>{
    const realTests = getRealTests(r.id, 'deck');
    const hasReal = realTests.length > 0;
    return `<div class="rank-card ${openRanks[r.id]?'open':''}" id="card-${r.id}" style="animation:fadeIn 0.35s ${i*60}ms ease both">
      <div class="rank-header" onclick="toggleRank('${r.id}')">
        <div style="display:flex;align-items:center;gap:14px">
          <div class="epaulette">${stripes(r.stripes)}</div>
          <div>
            <div class="rank-title" style="font-size:14px;font-weight:600;color:#fff;transition:color 0.2s">${r.bg}</div>
            <div style="font-size:11px;color:rgba(232,237,242,0.4);margin-top:2px">${r.en}${r.level?' · '+r.level:''}${realTests.filter(t=>t.is_demo).length>0?' · <span style=\'color:#e8a020\'>'+realTests.filter(t=>t.is_demo).length+' demo</span>':''}</div>
          </div>
        </div>
        <div class="chevron">▾</div>
      </div>
      <div class="rank-body">
        <div class="rank-inner">
          ${hasReal?`<div style="margin-bottom:14px"><div style="font-size:11px;color:#e8a020;font-weight:600;margin-bottom:8px;display:flex;align-items:center;gap:6px"><span style="width:5px;height:5px;border-radius:50%;background:#e8a020;display:inline-block"></span>Available demo tests</div><div style="display:flex;flex-direction:column;gap:8px">${realTests.map(t=>renderTestCard(t)).join('')}</div></div>`:'<div style="text-align:center;padding:24px;color:rgba(232,237,242,0.3);font-size:13px"><i class="fa-solid fa-lock" style="font-size:24px;margin-bottom:8px;display:block;opacity:0.3"></i>Demo test coming soon</div>'}
        </div>
      </div>
    </div>`;
  }).join('');
}

function renderEngineRanks(){
  document.getElementById('engineRanks').innerHTML = ENGINE_RANKS.map((r,i)=>{
    const realTests = getRealTests(r.id, 'engine');
    const hasReal = realTests.length > 0;
    return `<div class="rank-card ${openRanks[r.id]?'open':''}" id="card-${r.id}" style="animation:fadeIn 0.35s ${i*60}ms ease both">
      <div class="rank-header" onclick="toggleRank('${r.id}')">
        <div style="display:flex;align-items:center;gap:14px">
          <div class="epaulette">${stripes(r.stripes)}</div>
          <div>
            <div class="rank-title" style="font-size:14px;font-weight:600;color:#fff;transition:color 0.2s">${r.bg}</div>
            <div style="font-size:11px;color:rgba(232,237,242,0.4);margin-top:2px">${r.en}${r.level?' · '+r.level:''}${realTests.filter(t=>t.is_demo).length>0?' · <span style=\'color:#e8a020\'>'+realTests.filter(t=>t.is_demo).length+' demo</span>':''}</div>
          </div>
        </div>
        <div class="chevron">▾</div>
      </div>
      <div class="rank-body">
        <div class="rank-inner">
          ${hasReal?`<div style="margin-bottom:14px"><div style="font-size:11px;color:#e8a020;font-weight:600;margin-bottom:8px;display:flex;align-items:center;gap:6px"><span style="width:5px;height:5px;border-radius:50%;background:#e8a020;display:inline-block"></span>Available demo tests</div><div style="display:flex;flex-direction:column;gap:8px">${realTests.map(t=>renderTestCard(t)).join('')}</div></div>`:'<div style="text-align:center;padding:24px;color:rgba(232,237,242,0.3);font-size:13px"><i class="fa-solid fa-lock" style="font-size:24px;margin-bottom:8px;display:block;opacity:0.3"></i>Demo test coming soon</div>'}
        </div>
      </div>
    </div>`;
  }).join('');
}

function toggleRank(id){
  openRanks[id] = !openRanks[id];
  renderDeckRanks();
  renderEngineRanks();
}

function renderRatings(cat) {
  const tests = demoTests.filter(t => t.category === cat && t.level_key === 'support');
  const innerId  = cat === 'deck' ? 'deckRatingsInner'  : 'engineRatingsInner';
  const subId    = cat === 'deck' ? 'deckRatingsSub'    : 'engineRatingsSub';
  const subTxt   = cat === 'deck' ? 'Bosun · Able Seaman · Ordinary Seaman'
                                  : 'Motorman · Oiler · Wiper';
  const demoCount = tests.filter(t => t.is_demo).length;
  const subEl = document.getElementById(subId);
  if (subEl) subEl.innerHTML = subTxt + (demoCount > 0
    ? ' · <span style="color:#e8a020">' + demoCount + ' demo</span>' : '');
  const el = document.getElementById(innerId);
  if (!el) return;
  if (!tests.length) {
    el.innerHTML = '<div style="text-align:center;padding:24px;color:rgba(232,237,242,0.3);font-size:13px"><i class="fa-solid fa-lock" style="font-size:24px;margin-bottom:8px;display:block;opacity:0.3"></i>Ratings tests coming soon</div>';
    return;
  }
  el.innerHTML = '<div style="display:flex;flex-direction:column;gap:8px">' +
    tests.map(t => renderTestCard(t)).join('') + '</div>';
}

function toggleRatings(){
  const card = document.getElementById('ratingsCard');
  card.classList.toggle('open');
  if (card.classList.contains('open')) renderRatings('deck');
}

function toggleEngineRatings(){
  const card = document.getElementById('engineRatingsCard');
  card.classList.toggle('open');
  if (card.classList.contains('open')) renderRatings('engine');
}

function showDept(dept){
  document.getElementById('deptSelect').style.display = 'none';
  if(dept==='deck'){
    document.getElementById('deckDept').style.display = 'block';
    renderDeckRanks();
  } else {
    document.getElementById('engineDept').style.display = 'block';
    renderEngineRanks();
  }
}

function hideDept(){
  document.getElementById('deckDept').style.display = 'none';
  document.getElementById('engineDept').style.display = 'none';
  document.getElementById('deptSelect').style.display = 'block';
}

function filterTests(q){
  var el = document.getElementById('searchResults');
  if(!q || q.length < 2){ el.style.display='none'; return; }
  var found = demoTests.filter(t => t.title.toLowerCase().includes(q.toLowerCase()));
  el.style.display = 'block';
  el.innerHTML = found.length ? '<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px">'+found.map(t=>'<div class="test-card" onclick="window.location=\'/demo/test/'+t.id+'\'" style="flex-direction:column;align-items:flex-start;gap:8px"><div style="font-size:13px;font-weight:500;color:#fff">'+t.title+'</div><div style="font-size:11px;color:rgba(232,237,242,0.4)">'+t.question_count+' questions</div></div>').join('')+'</div>' : '<p style="color:rgba(232,237,242,0.4);font-size:14px">No tests found</p>';
}

function toggleDD(btn) {
  var dd = btn.nextElementSibling;
  var arrow = btn.querySelector('span');
  var isOpen = dd.style.display === 'block';
  document.querySelectorAll('.ddm').forEach(function(d){ d.style.display='none'; });
  document.querySelectorAll('.ddm-arrow').forEach(function(a){ a.style.transform=''; });
  if (!isOpen) {
    dd.style.display = 'block';
    if (arrow) arrow.style.transform = 'rotate(180deg)';
    var el = btn.parentElement;
    for (var i=0; i<8; i++) {
      if (!el || el.tagName === 'BODY') break;
      el.style.overflow = 'visible';
      if (el.classList.contains('rank-card')) { el.style.zIndex='100'; el.style.position='relative'; }
      el = el.parentElement;
    }
  }
}

document.addEventListener('click', function() {
  document.querySelectorAll('.ddm').forEach(function(d){ d.style.display='none'; });
});
