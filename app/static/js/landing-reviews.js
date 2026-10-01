// Landing "What our customers say" - извлечена от app/templates/landing.html (Правило 1).
// Десктоп/таблет: по 3 отзива на страница (стрелки + точки, както преди).
// Телефон (<=560px): всички отзиви в хоризонтална лента със snap - една карта и съвсем
// малка част от следващата (същото разпределение като новините); точките следват скрола.
(function () {
  var grid = document.getElementById('reviewGrid');
  var prevBtn = document.getElementById('btnPrev');
  var nextBtn = document.getElementById('btnNext');
  var dots = document.getElementById('revDots');
  if (!grid || !prevBtn || !nextBtn || !dots) return;

  var PER_PAGE = 3;
  var mq = window.matchMedia('(max-width: 560px)');
  var reviews = [];
  var page = 0;

  function esc(s) {
    var d = document.createElement('div');
    d.textContent = s == null ? '' : String(s);
    return d.innerHTML;
  }

  function stars(n) { return '★'.repeat(n) + '☆'.repeat(5 - n); }

  function cardHtml(r) {
    // Реална снимка -> <img>; иначе морски аватар от avatars.js (spec идва от сървъра);
    // буквата е само резервен вариант, ако avatars.js не е зареден.
    var avatar;
    if (r.picture) avatar = '<img class="rev-pic" src="' + esc(r.picture) + '" alt="">';
    else if (r.avatar && window.MaritimeAvatars) avatar = window.MaritimeAvatars.svg(r.avatar, 'rev-pic');
    else avatar = '<div class="rev-pic rev-pic--ph">' + esc((r.name || '?')[0]) + '</div>';
    return '<div class="rev-card">' +
      '<div class="rev-stars">' + stars(r.stars) + '</div>' +
      '<p class="rev-text">&ldquo;' + esc(r.text) + '&rdquo;</p>' +
      '<div class="rev-foot">' + avatar +
      '<div><div class="rev-name">' + esc(r.name) + '</div>' +
      '<div class="rev-role">' + esc(r.role) + '</div></div></div></div>';
  }

  function cardStep() {
    var c = grid.querySelector('.rev-card');
    if (!c) return grid.clientWidth;
    var gap = parseFloat(getComputedStyle(grid).columnGap) || 0;
    return c.getBoundingClientRect().width + gap;
  }

  function dotCount() { return mq.matches ? reviews.length : Math.ceil(reviews.length / PER_PAGE); }

  function activeDot() {
    if (!mq.matches) return page;
    var step = cardStep();
    return step ? Math.min(reviews.length - 1, Math.round(grid.scrollLeft / step)) : 0;
  }

  function paintDots() {
    var active = activeDot();
    var n = dotCount();
    dots.innerHTML = '';
    for (var i = 0; i < n; i++) {
      var d = document.createElement('div');
      d.className = 'rev-dot' + (i === active ? ' rev-dot--on' : '');
      (function (idx) { d.onclick = function () { goTo(idx); }; })(i);
      dots.appendChild(d);
    }
  }

  function goTo(i) {
    if (mq.matches) { grid.scrollTo({ left: i * cardStep(), behavior: 'smooth' }); return; }
    page = i;
    render();
  }

  function render() {
    if (!reviews.length) { grid.innerHTML = ''; dots.innerHTML = ''; return; }
    grid.innerHTML = reviews.map(cardHtml).join('');
    if (mq.matches) {
      grid.style.transform = '';
      grid.scrollLeft = 0;
    } else {
      var gap = parseFloat(getComputedStyle(grid).columnGap) || 0;
      grid.style.transform = 'translateX(-' + (page * (grid.clientWidth + gap)) + 'px)';
    }
    prevBtn.style.display = !mq.matches && page > 0 ? 'block' : 'none';
    nextBtn.style.display = !mq.matches && (page + 1) * PER_PAGE < reviews.length ? 'block' : 'none';
    paintDots();
  }

  prevBtn.onclick = function () { if (page > 0) { page--; render(); } };
  nextBtn.onclick = function () { if ((page + 1) * PER_PAGE < reviews.length) { page++; render(); } };

  var ticking = false;
  grid.addEventListener('scroll', function () {
    if (!mq.matches || ticking) return;
    ticking = true;
    requestAnimationFrame(function () {
      ticking = false;
      var active = activeDot();
      var list = dots.children;
      for (var i = 0; i < list.length; i++) list[i].classList.toggle('rev-dot--on', i === active);
    });
  }, { passive: true });

  if (mq.addEventListener) mq.addEventListener('change', function () { page = 0; render(); });
  window.addEventListener('resize', function () { if (!mq.matches) render(); });

  fetch('/api/reviews/public')
    .then(function (r) { return r.json(); })
    .then(function (data) { reviews = data || []; })
    .catch(function () { reviews = []; })
    .then(render);
})();
