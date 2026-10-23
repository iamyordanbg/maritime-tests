// Landing "How it works" - само за телефон (<=560px, същия breakpoint като
// .steps -> 1 колона в landing.css). Докато потребителят скролва, картата,
// която пресича средата на екрана, получава клас .step--active (същия вид
// като десктоп hover). На по-големи екрани скриптът не прави нищо.
(function () {
  var mq = window.matchMedia('(max-width: 560px)');
  var steps = document.querySelectorAll('.how-sec .step');
  var observer = null;

  function start() {
    if (observer || !('IntersectionObserver' in window)) return;
    // rootMargin -50%/-50% свива зоната на наблюдение до хоризонталната
    // линия точно в средата на екрана.
    observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        e.target.classList.toggle('step--active', e.isIntersecting);
      });
    }, { rootMargin: '-50% 0px -50% 0px', threshold: 0 });
    steps.forEach(function (s) { observer.observe(s); });
  }

  function stop() {
    if (observer) { observer.disconnect(); observer = null; }
    steps.forEach(function (s) { s.classList.remove('step--active'); });
  }

  function sync() { if (mq.matches) start(); else stop(); }

  sync();
  if (mq.addEventListener) mq.addEventListener('change', sync);
  else if (mq.addListener) mq.addListener(sync);
})();
