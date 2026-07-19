// app/static/js/billing_plans_page.js
// Стандартна billing/plans.html е MODAL fragment (display:none по
// подразбиране, отваря се от бутон в user_sidebar.html чрез
// openPlansModal()). Тук (billing/plans_page.html) е зареден като
// САМОСТОЯТЕЛНА страница - вместо да дублираме съдържанието, просто я
// отваряме веднага при зареждане.
window.BILLING_PLANS_STANDALONE = true;
document.addEventListener('DOMContentLoaded', openPlansModal);
