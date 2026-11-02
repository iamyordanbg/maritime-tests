// app/static/js/all-mistakes-review.js
// "View answers" на All Mistakes: разбъркване на въпросите и махане/връщане на въпрос от решаването.
(function () {
  var list = document.getElementById('amQuestions');
  if (!list) return;
  var testId = list.dataset.testId;
  var counter = document.getElementById('amIncluded');

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
