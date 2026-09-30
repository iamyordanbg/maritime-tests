// Landing "News & Announcements" - извлечена от app/templates/landing.html (Правило 1).
// Десктоп/таблет: по 3 новини на страница (стрелки + Load more, както преди).
// Телефон (<=560px): всички новини в хоризонтална лента със snap - вижда се
// една новина и малко от следващата; стрелките скролират с по една карта.
(function () {
  var news = [
    {tag:'Exams',title:'2026 Exam Session Schedule',text:'The MA published the schedule for the 2026 certification exam sessions.',date:'May 15, 2026'},
    {tag:'Regulations',title:'STCW 2026 Changes',text:'The IMO introduced updated training and certification standards for seafarers.',date:'May 8, 2026'},
    {tag:'Platform',title:'New Engine Department Questions',text:'We added 200 new Management Level questions.',date:'May 1, 2026'},
    {tag:'Exams',title:'June 2026 Approved Candidates',text:'The list of candidates approved for the June 15 session has been published.',date:'Apr 28, 2026'},
    {tag:'Regulations',title:'New GMDSS Requirements',text:'New requirements for radio operators take effect July 1.',date:'Apr 20, 2026'},
    {tag:'Platform',title:'New Deck Simulator',text:'The simulator now covers all levels with real exam timing.',date:'Apr 10, 2026'}
  ];
  var PER_PAGE = 3;
  var grid = document.getElementById('newsGrid');
  var prevBtn = document.getElementById('prevBtn');
  var nextBtn = document.getElementById('nextBtn');
  var loadBtn = document.querySelector('.btn-load');
  if (!grid || !prevBtn || !nextBtn || !loadBtn) return;

  var mq = window.matchMedia('(max-width: 560px)');
  var page = 0;

  function cardHtml(n) {
    return '<div class="news-card"><span class="news-tag">' + n.tag + '</span><h3>' + n.title +
      '</h3><p>' + n.text + '</p><div class="news-foot"><span class="news-date">' + n.date +
      '</span><a href="#" class="news-read">Read more →</a></div></div>';
  }

  function render() {
    var items = mq.matches ? news : news.slice(page * PER_PAGE, page * PER_PAGE + PER_PAGE);
    grid.innerHTML = items.map(cardHtml).join('');
    if (mq.matches) grid.scrollLeft = 0;
  }

  // Ширина на една карта + разстоянието между тях (за скрол със стрелките).
  function cardStep() {
    var c = grid.querySelector('.news-card');
    if (!c) return grid.clientWidth;
    var gap = parseFloat(getComputedStyle(grid).columnGap) || 0;
    return c.getBoundingClientRect().width + gap;
  }

  prevBtn.onclick = function () {
    if (mq.matches) { grid.scrollBy({ left: -cardStep(), behavior: 'smooth' }); return; }
    if (page > 0) { page--; render(); }
  };
  nextBtn.onclick = function () {
    if (mq.matches) { grid.scrollBy({ left: cardStep(), behavior: 'smooth' }); return; }
    if ((page + 1) * PER_PAGE < news.length) { page++; render(); }
  };
  loadBtn.onclick = function () {
    page = (page + 1) * PER_PAGE < news.length ? page + 1 : 0;
    render();
  };

  if (mq.addEventListener) mq.addEventListener('change', render);
  else if (mq.addListener) mq.addListener(render);
  render();
})();
