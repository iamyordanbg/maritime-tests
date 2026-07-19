// app/static/js/activate_confirm.js
// Activate confirm — извлечена от app/templates/activate/confirm.html (Правило 1).

function limitTwo(checkbox) {
  const boxes = document.querySelectorAll('input[name="test_ids"]:checked');
  if (boxes.length > 2) { checkbox.checked = false; }
}
