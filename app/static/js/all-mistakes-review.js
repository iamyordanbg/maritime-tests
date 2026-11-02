// app/static/js/all-mistakes-review.js
// "View answers" на All Mistakes: разбъркване на въпросите и махане/връщане на въпрос от решаването.
(function () {
  var list = document.getElementById('amQuestions');
  if (!list) return;
  var testId = list.dataset.testId;
  var counter = document.getElementById('amIncluded');

  // Разбъркване (Fisher-Yates) - само пренарежда картите на екрана.
  var shuffleBtn = document.getElementById('amShuffle');
  if (shuffleBtn) {
    shuffleBtn.addEventListener('click', function () {
      var cards = Array.prototype.slice.call(list.querySelectorAll('[data-qid]'));
      for (var i = cards.length - 1; i > 0; i--) {
        var j = Math.floor(Math.random() * (i + 1));
        var t = cards[i]; cards[i] = cards[j]; cards[j] = t;
      }
      cards.forEach(function (c) { list.appendChild(c); });
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
  }

  // Махане/връщане на въпрос от решаването (записва се на сървъра; във View answers остава).
  list.addEventListener('click', function (e) {
    var btn = e.target.closest('.js-am-exclude');
    if (!btn) return;
    var card = btn.closest('[data-qid]');
    var excluded = btn.getAttribute('aria-pressed') !== 'true';
    btn.disabled = true;
    fetch('/all-mistakes/' + testId + '/exclude', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
      body: JSON.stringify({ question_id: card.dataset.qid, excluded: excluded })
    }).then(function (r) { return r.json(); }).then(function (d) {
      if (!d.success) return;
      btn.setAttribute('aria-pressed', excluded ? 'true' : 'false');
      card.classList.toggle('am-q--off', excluded);
      if (counter) counter.textContent = d.included;
    }).catch(function () {}).then(function () { btn.disabled = false; });
  });
})();
