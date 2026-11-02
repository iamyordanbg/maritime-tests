// app/static/js/all-mistakes.js
// Попъп "All Mistakes е заключен": колко решени Test/Mix/Simulator са нужни и колко има клиентът.
(function () {
  var modal = document.getElementById('amLockedModal');
  if (!modal) return;

  function close() { modal.hidden = true; }

  document.querySelectorAll('.js-am-locked').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var needed = btn.dataset.needed, solved = btn.dataset.solved;
      document.getElementById('amNeeded').textContent = needed;
      document.getElementById('amNeededOf').textContent = needed;
      document.getElementById('amSolved').textContent = solved;
      modal.hidden = false;
    });
  });
  document.getElementById('amLockedClose').addEventListener('click', close);
  modal.addEventListener('click', function (e) { if (e.target === modal) close(); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') close(); });
})();
