// app/static/js/billing_plans.js
// Billing Plans tooltip — извлечена от app/templates/billing/plans.html (Правило 1).

(function(){
  var tip = document.getElementById('plansTooltip');
  document.querySelectorAll('.plansTipLabel[data-tooltip]').forEach(function(label){
    label.addEventListener('mouseenter', function(){
      tip.textContent = label.getAttribute('data-tooltip');
      tip.style.display = 'block';
      var r = label.getBoundingClientRect();
      var tw = tip.offsetWidth;
      var th = tip.offsetHeight;
      var left = Math.max(8, r.left);
      var top = Math.max(8, r.top - th - 8);
      tip.style.left = left + 'px';
      tip.style.top = top + 'px';
    });
    label.addEventListener('mouseleave', function(){
      tip.style.display = 'none';
    });
  });
})();
function openPlansModal() {
  document.getElementById('plansModal').style.display = 'flex';
  document.body.style.overflow = 'hidden';
}
function closePlansModal() {
  document.getElementById('plansModal').style.display = 'none';
  document.body.style.overflow = '';
  var tip = document.getElementById('plansTooltip');
  if (tip) tip.style.display = 'none';
}
function checkoutFromModal(plan) {
  if (window.BILLING_PLANS_DATA.isLoggedIn) {
  const form = document.createElement('form');
  form.method = 'POST';
  form.action = '/billing/checkout/' + plan;
  form.target = '_blank';
  document.body.appendChild(form);
  form.submit();
  } else {
  sessionStorage.setItem('pendingPlan', plan);
  closePlansModal();
  if (typeof openRegisterModal === 'function') {
    var existing = document.getElementById('registerPlanField');
    if (!existing) {
      var inp = document.createElement('input');
      inp.type = 'hidden'; inp.name = 'pending_plan'; inp.id = 'registerPlanField';
      var f = document.getElementById('registerForm');
      if (f) f.appendChild(inp);
    }
    if (document.getElementById('registerPlanField')) document.getElementById('registerPlanField').value = plan;
    openRegisterModal();
  } else {
    window.location.href = '/billing/checkout/' + plan;
  }
  }
}
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') closePlansModal();
});
