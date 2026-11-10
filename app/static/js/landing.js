/*
 * landing.js — behaviour of the public landing page (landing.html).
 * Server-side values come from window.LANDING_DATA (set in landing.html).
 * Loaded with `defer`, so the DOM is fully parsed when this runs.
 */

// ---------------------------------------------------------------- URL params
// ?register=1 / ?login=1 open the matching auth modal (used by /login and /register redirects)
(function () {
  var params = new URLSearchParams(window.location.search);
  if (params.get('register') === '1') {
    window.addEventListener('load', function () { setTimeout(openRegisterModal, 100); });
  }
  if (params.get('login') === '1') {
    window.addEventListener('load', function () { setTimeout(openLoginModal, 100); });
  }
  // Another device took this device's slot (?replaced=phone|computer): tell the user why they are at the login again
  var replaced = params.get('replaced');
  if (replaced === 'phone' || replaced === 'computer') {
    window.addEventListener('load', function () {
      setTimeout(function () {
        var box = document.getElementById('loginError');
        if (box) {
          box.textContent = 'You were signed out because this account was signed in on another ' +
            (replaced === 'phone' ? 'phone.' : 'computer or tablet.');
          box.style.display = 'block';
        }
      }, 200);
    });
  }
  // A 3rd device was signed out for violating the Terms of Use (?violation=1); the text comes from the server
  if (params.get('violation') === '1' && window.LANDING_DATA && window.LANDING_DATA.violationMessage) {
    window.addEventListener('load', function () {
      setTimeout(function () {
        var box = document.getElementById('loginError');
        if (box) {
          box.textContent = window.LANDING_DATA.violationMessage;
          box.style.display = 'block';
        }
      }, 200);
    });
  }
})();

// ------------------------------------------------------- pageshow (back button)
window.addEventListener('pageshow', function() {
    ['loginModal','registerModal','forgotModal','otpModal','termsModal','privacyModal'].forEach(function(id) {
        var el = document.getElementById(id);
        if (el) el.style.display = 'none';
    });
});

// ------------------------------------------------------------------ checkout
function submitCheckoutForm(plan) {
  var form = document.createElement('form');
  form.method = 'POST';
  form.action = '/billing/checkout/' + plan;
  form.target = '_blank';
  document.body.appendChild(form);
  form.submit();
}

function checkoutRedirect(e, plan) {
  e.preventDefault();
  if (window.LANDING_DATA.isLoggedIn) {
    // Logged in: post straight to checkout
    submitCheckoutForm(plan);
    return false;
  }
  // Not logged in: remember the plan and open the register modal
  sessionStorage.setItem('pendingPlan', plan);
  // Add a hidden field to the register form
  var existing = document.getElementById('registerPlanField');
  if (!existing) {
    var inp = document.createElement('input');
    inp.type = 'hidden';
    inp.name = 'pending_plan';
    inp.id = 'registerPlanField';
    var form = document.getElementById('registerForm');
    if (form) form.appendChild(inp);
  }
  document.getElementById('registerPlanField').value = plan;
  openRegisterModal();
  return false;
}

// After a successful login: continue with the plan chosen before logging in
window.addEventListener('load', function () {
  var plan = sessionStorage.getItem('pendingPlan');
  if (window.LANDING_DATA.isLoggedIn && plan) {
    sessionStorage.removeItem('pendingPlan');
    submitCheckoutForm(plan);
  }
});

// ---------- mobile menu ----------
function toggleMobileMenu(){
  var menu = document.getElementById('mobileMenu');
  var btn = document.getElementById('hamburgerBtn');
  var isOpen = menu.classList.toggle('open');
  btn.classList.toggle('open', isOpen);
  document.body.style.overflow = isOpen ? 'hidden' : '';
}
function closeMobileMenu(){
  document.getElementById('mobileMenu').classList.remove('open');
  document.getElementById('hamburgerBtn').classList.remove('open');
  document.body.style.overflow = '';
}

// ---------- pricing table / slider ----------
(function(){
  var tip = document.getElementById('cmpTooltip');
  document.querySelectorAll('.cmp-c-label[data-tooltip]').forEach(function(label){
    label.addEventListener('mouseenter', function(){
      tip.textContent = label.getAttribute('data-tooltip');
      tip.style.display = 'block';
      var r = label.getBoundingClientRect();
      var tw = tip.offsetWidth;
      var th = tip.offsetHeight;
      var left = Math.max(8, r.left - tw - 8);
      var top = Math.min(window.innerHeight - th - 8, Math.max(8, r.top + r.height / 2 - th / 2));
      tip.style.left = left + 'px';
      tip.style.top = top + 'px';
    });
    label.addEventListener('mouseleave', function(){
      tip.style.display = 'none';
    });
  });
})();
(function(){
  var sec = document.getElementById('plans');
  var inner = sec.querySelector('.cmp-in');
  var MAX_SCALE = 0.85; // cards are 15% shorter
  function fitHeight(){
    if (window.innerWidth <= 900) {
      sec.style.setProperty('--cmp-scale', MAX_SCALE.toFixed(5));
      return;
    }
    var target = window.innerHeight - 104 - 2;
    var lo = 0, hi = MAX_SCALE;
    for (var i = 0; i < 12; i++) {
      var mid = (lo + hi) / 2;
      sec.style.setProperty('--cmp-scale', mid.toFixed(5));
      var h = inner.getBoundingClientRect().height;
      if (h > target) { hi = mid; } else { lo = mid; }
    }
    sec.style.setProperty('--cmp-scale', lo.toFixed(5));
  }
  fitHeight();
  window.addEventListener('resize', fitHeight);
  window.addEventListener('load', fitHeight);
  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(fitHeight);
  }
})();
(function(){
  var labelCells = document.querySelectorAll('.cmp-c-label[data-row]');
  labelCells.forEach(function(cell){
    var key = cell.getAttribute('data-row');
    var group = document.querySelectorAll('.cmp-grid [data-row="' + key + '"]');
    cell.addEventListener('mouseenter', function(){
      group.forEach(function(c){ c.classList.add('row-hover'); });
    });
    cell.addEventListener('mouseleave', function(){
      group.forEach(function(c){ c.classList.remove('row-hover'); });
    });
  });

  var COL_CLASSES = ['cmp-c-free','cmp-c-basic','cmp-c-plus','cmp-c-gold'];
  COL_CLASSES.forEach(function(colClass){
    var cells = document.querySelectorAll('.' + colClass);
    cells.forEach(function(cell){
      cell.addEventListener('mouseenter', function(){
        cells.forEach(function(c){ c.classList.add('col-hover'); });
      });
      cell.addEventListener('mouseleave', function(){
        cells.forEach(function(c){ c.classList.remove('col-hover'); });
      });
    });
  });
})();

(function(){
  // Plus ribbon - a position:fixed element whose coordinates are updated
  // directly from JS (getBoundingClientRect) from the real position of the
  // Plus header cell on screen. Completely sidesteps the CSS overflow:hidden
  // + transform browser rendering conflict (see git history for
  // details) - JS tracks where the cell REALLY is right now (including
  // during the hover transform animation) and moves the wrapper exactly there.
  var plusHead = document.querySelector('.cmp-c-plus.cmp-head');
  var ribbonWrap = document.getElementById('cmpPlusRibbonWrap');
  if (!plusHead || !ribbonWrap) return;

  function positionRibbon(){
    var r = plusHead.getBoundingClientRect();
    ribbonWrap.style.top = r.top + 'px';
    ribbonWrap.style.left = (r.right - 100) + 'px';
  }

  function showRibbon(){
    positionRibbon();
    ribbonWrap.style.display = 'block';
  }
  function updateRibbon(){
    if (ribbonWrap.style.display === 'block') positionRibbon();
  }
  function hideRibbon(){
    ribbonWrap.style.display = 'none';
  }

  showRibbon();
  window.addEventListener('resize', updateRibbon);
  window.addEventListener('scroll', updateRibbon, {passive:true});

  var plusCells = document.querySelectorAll('.cmp-c-plus');
  plusCells.forEach(function(cell){
    cell.addEventListener('mouseenter', function(){
      requestAnimationFrame(function(){
        var raf2 = function(){ positionRibbon(); requestAnimationFrame(raf2); };
        ribbonWrap._raf = requestAnimationFrame(raf2);
      });
    });
    cell.addEventListener('mouseleave', function(){
      if (ribbonWrap._raf) cancelAnimationFrame(ribbonWrap._raf);
      positionRibbon();
    });
  });
})();

(function(){
  var scroller = document.getElementById('cmpMScroller');
  var tabs = document.querySelectorAll('.cmp-mtab');
  if (!scroller || !tabs.length) return;

  function setActivePlan(id){
    tabs.forEach(function(tab){
      tab.classList.toggle('active', tab.getAttribute('data-target') === id);
    });
  }

  tabs.forEach(function(tab){
    tab.addEventListener('click', function(){
      var target = document.getElementById(tab.getAttribute('data-target'));
      if (target) target.scrollIntoView({behavior:'smooth', inline:'center', block:'nearest'});
    });
  });

  // Plus is the active plan by default — position the slider and tab
  // BEFORE starting the IntersectionObserver, to avoid a race condition.
  var plusSlide = document.getElementById('cmpCardPlus');
  if (plusSlide && scroller) {
    scroller.scrollLeft = plusSlide.offsetLeft;
  }
  setActivePlan('cmpCardPlus');

  var slides = document.querySelectorAll('.cmp-mslide');
  var io = new IntersectionObserver(function(entries){
    entries.forEach(function(entry){
      if (entry.isIntersecting && entry.intersectionRatio > 0.5) {
        setActivePlan(entry.target.id);
      }
    });
  }, {root: scroller, threshold: [0.5, 0.6, 0.7]});

  requestAnimationFrame(function(){
    slides.forEach(function(s){ io.observe(s); });
  });
})();

// ---------- legal modal ----------
const legalTitles = {
  terms:   'Terms of Service',
  privacy: 'Privacy & Data',
  cookies: 'Cookie Policy',
  about:   'About us',
  contact: 'Contact',
  blog:    'Blog'
};

async function blogClick() {
  // Count the click
  fetch('/blog/interest', {method:'POST'}).catch(()=>{});
  // Open the under construction modal
  document.getElementById('legalModalTitle').textContent = 'Blog';
  document.getElementById('legalModalBody').innerHTML = `
    <div style="text-align:center;padding:40px 20px">
      <div style="font-size:48px;margin-bottom:16px">🚧</div>
      <p style="font-size:18px;font-weight:700;color:#111827;margin-bottom:10px">Under Construction</p>
      <p style="font-size:14px;color:#6b7280;line-height:1.7;max-width:320px;margin:0 auto">
        The blog is under construction. Soon you'll find stories, tips, and insights from people with maritime experience here.
      </p>
      <div style="margin-top:24px;padding:12px 20px;background:#f9fafb;border-radius:10px;display:inline-block">
        <p style="font-size:12px;color:#9ca3af;margin:0">Follow the <a href="/feed" style="color:#e8a020;font-weight:600">News</a> for updates</p>
      </div>
    </div>`;
  document.getElementById('legalModal').style.display = 'block';
  document.body.style.overflow = 'hidden';
}

async function openLegalModal(type) {
  const title = legalTitles[type] || '';
  document.getElementById('legalModalTitle').textContent = title;
  document.getElementById('legalModalBody').innerHTML = '<p style="color:#9ca3af;text-align:center;padding:32px 0">Loading...</p>';
  document.getElementById('legalModal').style.display = 'block';
  document.body.style.overflow = 'hidden';
  try {
    const res = await fetch('/' + type);
    const html = await res.text();
    document.getElementById('legalModalBody').innerHTML = html;
    document.getElementById('legalModalBody').scrollTop = 0;
  } catch(e) {
    document.getElementById('legalModalBody').innerHTML = '<p style="color:#dc2626;text-align:center;padding:32px 0">Error loading content.</p>';
  }
}

function closeLegalModal() {
  document.getElementById('legalModal').style.display = 'none';
  document.body.style.overflow = '';
}

document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') closeLegalModal();
});

// ---------- FAQ ----------
// FAQ
function toggleFaq(el){
  const item=el.parentElement;
  const was=item.classList.contains('open');
  document.querySelectorAll('.faq-item').forEach(i=>i.classList.remove('open'));
  if(!was)item.classList.add('open');
}
