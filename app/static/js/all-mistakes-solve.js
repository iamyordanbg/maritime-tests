// app/static/js/all-mistakes-solve.js
// Shuffle при решаване на All Mistakes: бутонът презарежда теста с нов ред
// и се скрива щом потребителят отговори на първия въпрос (за да не губи отговори).
(function () {
  var btn = document.getElementById('amShuffle');
  var counter = document.getElementById('answeredCount');
  if (!btn || !counter) return;
  function sync() {
    var started = parseInt(counter.textContent, 10) > 0;
    btn.style.display = started ? 'none' : '';
  }
  new MutationObserver(sync).observe(counter, { childList: true, characterData: true, subtree: true });
  sync();
})();
