// Base layout логика - извлечена от app/templates/layouts/base.html
// (keep-alive ping, глобални UI помощни функции и т.н.)

// Реален "keep-alive" ping — само докато потребителят действително е активен
// (мърда мишка/клавиатура/клик). При INACTIVITY_TIMEOUT_MINUTES (подадена стойност)
// минути без реално действие спираме всички фонови заявки и връщаме към login,
// вместо да продължаваме да питаме сървъра безкрайно.
(function() {
    const TIMEOUT_MS = INACTIVITY_TIMEOUT_MINUTES * 60 * 1000;
    let lastActivity = Date.now();
    let pingTimer = null;

    ['mousemove', 'keydown', 'click', 'scroll', 'touchstart'].forEach(evt =>
        document.addEventListener(evt, () => { lastActivity = Date.now(); }, { passive: true })
    );

    pingTimer = setInterval(() => {
        const idleMs = Date.now() - lastActivity;
        if (idleMs > TIMEOUT_MS) {
            clearInterval(pingTimer);
            window.location.href = LOGIN_URL;
            return;
        }
        fetch('/ping').catch(() => {});
    }, 4 * 60 * 1000);
})();


function openLoginModal() {
  document.getElementById('loginModal').style.display = 'block';
  document.getElementById('loginError').style.display = 'none';
  if (window.turnstile) turnstile.reset();
  // Clear fields but keep autocomplete for dropdown on click
  document.getElementById('loginEmail').value = '';
  document.getElementById('loginPassword').value = '';
  setTimeout(() => document.getElementById('loginEmail').focus(), 100);
}
function closeLoginModal() {
  document.getElementById('loginModal').style.display = 'none';
}
function toggleModalPass() {
  const i = document.getElementById('loginPassword');
  const ic = document.getElementById('modalEyeIcon');
  i.type = i.type === 'password' ? 'text' : 'password';
  ic.className = i.type === 'password' ? 'fa-solid fa-eye' : 'fa-solid fa-eye-slash';
}
document.addEventListener('keydown', e => { if(e.key==='Escape') closeLoginModal(); });
async function submitLogin(e) {
  e.preventDefault();
  const email = document.getElementById('loginEmail').value;
  const pass = document.getElementById('loginPassword').value;
  const btn = document.getElementById('loginSubmit');
  const err = document.getElementById('loginError');
  const token = document.querySelector('#loginModal input[name="cf-turnstile-response"]');
  btn.textContent = 'Влизане...'; btn.disabled = true; err.style.display = 'none';
  const fd = new FormData();
  fd.append('email', email);
  fd.append('password', pass);
  if (token) fd.append('cf-turnstile-response', token.value);
  const pendingPlan = sessionStorage.getItem('pendingPlan');
  if (pendingPlan) fd.append('pending_plan', pendingPlan);
  const res = await fetch('/login', {method:'POST', body:fd, redirect:'manual', headers:{'X-Requested-With':'XMLHttpRequest'}});
  
  // Handle JSON response from AJAX login
  const ct = res.headers.get('Content-Type') || '';
  if (ct.includes('application/json')) {
    const data = await res.json();
    if (data.success) {
      // Show loading overlay immediately to hide landing page flash
      document.body.style.opacity = '0';
      document.body.style.transition = 'opacity 0.1s';
      window.location.replace(data.redirect || '/dashboard');
      return;
    }
  }
  
  if (res.type === 'opaqueredirect' || res.status === 302 || res.redirected) {
    // Check if redirected to verify-otp
    closeRegisterModal();
    // Get email from form
    const regEmail = document.getElementById('regEmail').value;
    openOtpModal(regEmail);
    return;
  }
  const text = await res.text();
  if (text.includes('Грешен') || text.includes('невалид') || res.status >= 400) {
    err.textContent = 'Грешен имейл или парола.';
    err.style.display = 'block';
    if (window.turnstile) turnstile.reset();
  } else {
    window.location.href = '/';
  }
  btn.textContent = 'Влез'; btn.disabled = false;
}


function openRegisterModal() {
  document.getElementById('registerModal').style.display = 'block';

  document.getElementById('regEmail').value = '';
  document.getElementById('regPassword').value = '';
  document.getElementById('registerError').style.display = 'none';
  document.getElementById('registerSuccess').style.display = 'none';
  checkRegStrength('');
  if (window.turnstile) turnstile.reset();
}
function closeRegisterModal() {
  document.getElementById('registerModal').style.display = 'none';
}
function toggleRegPass() {
  const i = document.getElementById('regPassword');
  const ic = document.getElementById('regEyeIcon');
  i.type = i.type === 'password' ? 'text' : 'password';
  ic.className = i.type === 'password' ? 'fa-solid fa-eye' : 'fa-solid fa-eye-slash';
}
function checkRegStrength(val) {
  const bars = [document.getElementById('rbar1'), document.getElementById('rbar2'), document.getElementById('rbar3')];
  const label = document.getElementById('regStrengthLabel');
  if (!bars[0]) return;
  const score = passwordScore(val);
  const colors = ['#EF4444','#F59E0B','#22C55E'];
  const labels = ['','Слаба','Средна','Силна'];
  const lcolors = ['','#EF4444','#F59E0B','#22C55E'];
  bars.forEach((b,i) => b.style.background = val.length === 0 ? '#e5e7eb' : i < score ? colors[score-1] : '#e5e7eb');
  if (label) { label.textContent = val.length > 0 ? labels[score] : ''; label.style.color = lcolors[score] || ''; }
}

// Ясен стандарт за сложност на парола (NIST/OWASP базиран):
// Минимум 8 символа, и поне 3 от 4-те категории: главна буква, малка буква, цифра, специален знак.
// Връща 0 (празно), 1 (слаба), 2 (средна) или 3 (силна).
function passwordScore(val) {
  if (!val) return 0;
  if (val.length < 8) return 1; // под минимума — винаги слаба

  const hasUpper = /[A-Z]/.test(val);
  const hasLower = /[a-z]/.test(val);
  const hasDigit = /[0-9]/.test(val);
  const hasSpecial = /[^a-zA-Z0-9]/.test(val);
  const categories = [hasUpper, hasLower, hasDigit, hasSpecial].filter(Boolean).length;

  if (categories <= 1) return 1;                          // слаба
  if (categories === 2) return 2;                          // средна
  if (categories === 3) return val.length >= 12 ? 3 : 2;    // 3 категории: силна само ако е и достатъчно дълга
  return 3;                                                 // всичките 4 категории — силна
}
function onTurnstileSuccess(token) {
  // Token received - enable submit button
  const btn = document.getElementById('regSubmit');
  if (btn) btn.disabled = false;
}

// Execute Turnstile automatically when modal opens
function executeTurnstile() {
  if (window.turnstile) {
    turnstile.reset();
  }
}

document.addEventListener('keydown', e => { if(e.key==='Escape') closeRegisterModal(); });
async function submitRegister(e) {
  e.preventDefault();
  const name = '';
  const email = document.getElementById('regEmail').value;
  const pass = document.getElementById('regPassword').value;
  const err = document.getElementById('registerError');
  const suc = document.getElementById('registerSuccess');
  const btn = document.getElementById('regSubmit');
  const token = document.querySelector('#registerModal input[name="cf-turnstile-response"]');
  if (pass.length < 6) { err.textContent='Паролата трябва да е поне 6 символа.'; err.style.display='block'; return; }
  if (!/[0-9]/.test(pass) || !/[a-zA-Z]/.test(pass)) { err.textContent='Паролата трябва да съдържа букви И цифри.'; err.style.display='block'; return; }
  btn.textContent='Моля изчакай...'; btn.disabled=true; err.style.display='none';
  const fd = new FormData();
  fd.append('name', name);
  fd.append('email', email);
  fd.append('password', pass);
  if (token) fd.append('cf-turnstile-response', token.value);
  const pendingPlan = sessionStorage.getItem('pendingPlan');
  if (pendingPlan) fd.append('pending_plan', pendingPlan);
  const res = await fetch('/register', {method:'POST', body:fd, redirect:'manual'});
  
  // 302 redirect = success
  if (res.type === 'opaqueredirect' || res.status === 302 || res.redirected) {
    // Check if redirected to verify-otp
    closeRegisterModal();
    // Get email from form
    const regEmail = document.getElementById('regEmail').value;
    openOtpModal(regEmail);
    return;
  }
  
  // 200 = error, read the flash message
  const text = await res.text();
  const parser = new DOMParser();
  const doc = parser.parseFromString(text, 'text/html');
  
  // Try to find flash message in response
  const flashEl = doc.querySelector('[class*="bg-red"], [class*="rose"], [class*="error"]');
  let errMsg = flashEl ? flashEl.textContent.trim() : '';
  
  if (!errMsg) {
    if (text.includes('вече е регистриран')) errMsg = 'Имейлът вече е регистриран.';
    else if (text.includes('Невалиден')) errMsg = 'Невалиден имейл адрес.';
    else if (text.includes('Твърде много')) errMsg = 'Твърде много опити. Опитай след 1 час.';
    else if (text.includes('верификацията')) errMsg = 'Антибот верификацията е неуспешна.';
    else errMsg = 'Грешка при регистрацията. Опитай отново.';
  }
  
  err.textContent = errMsg;
  err.style.display = 'block';
  if (window.turnstile) turnstile.reset();
  btn.textContent='Създай акаунт'; btn.disabled=false;
}


let otpTimerInterval = null;

function openOtpModal(email) {
  document.getElementById('otpModal').style.display = 'block';
  document.getElementById('otpEmailDisplay').textContent = email;
  document.getElementById('otpError').style.display = 'none';
  // Clear inputs
  document.querySelectorAll('.otp-digit').forEach(d => d.value = '');
  // Start timer
  startOtpTimer();
  setTimeout(() => document.querySelector('.otp-digit').focus(), 100);
}

function startOtpTimer() {
  if (otpTimerInterval) clearInterval(otpTimerInterval);
  let seconds = 300;
  const timerEl = document.getElementById('otpTimer');
  otpTimerInterval = setInterval(() => {
    seconds--;
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    timerEl.textContent = m + ':' + (s < 10 ? '0' : '') + s;
    if (seconds <= 0) {
      clearInterval(otpTimerInterval);
      timerEl.textContent = '0:00';
      timerEl.style.color = '#ef4444';
    }
  }, 1000);
}

function otpMoveNext(input) {
  const digits = document.querySelectorAll('.otp-digit');
  const idx = Array.from(digits).indexOf(input);
  if (input.value && idx < digits.length - 1) {
    digits[idx + 1].focus();
  }
  const code = Array.from(digits).map(d => d.value).join('');
  document.getElementById('otpHidden').value = code;
  if (code.length === 6 && Array.from(digits).every(d => d.value)) {
    setTimeout(() => document.getElementById('otpForm').dispatchEvent(new Event('submit', {cancelable: true})), 120);
  }
}

function otpMovePrev(e, input) {
  if (e.key === 'Backspace' && !input.value) {
    const digits = document.querySelectorAll('.otp-digit');
    const idx = Array.from(digits).indexOf(input);
    if (idx > 0) digits[idx - 1].focus();
  }
}

document.addEventListener('paste', function(e) {
  if (!document.getElementById('otpModal').style.display || document.getElementById('otpModal').style.display === 'none') return;
  const text = (e.clipboardData || window.clipboardData).getData('text').replace(/\D/g, '').slice(0, 6);
  const digits = document.querySelectorAll('.otp-digit');
  text.split('').forEach((c, i) => { if (digits[i]) digits[i].value = c; });
  document.getElementById('otpHidden').value = Array.from(digits).map(d => d.value).join('');
  if (digits[text.length - 1]) digits[text.length - 1].focus();
  if (text.length === 6) {
    setTimeout(() => document.getElementById('otpForm').dispatchEvent(new Event('submit', {cancelable: true})), 120);
  }
});

let _otpSubmitting = false;
async function submitOTP(e) {
  e.preventDefault();
  if (_otpSubmitting) return;
  _otpSubmitting = true;
  const otp = document.getElementById('otpHidden').value;
  const err = document.getElementById('otpError');
  const btn = document.getElementById('otpSubmit');
  
  _otpSubmitting = false;
  if (otp.length < 6) {
    err.textContent = 'Въведи всичките 6 цифри.';
    err.style.display = 'block';
    return;
  }
  
  btn.textContent = 'Проверяване...';
  btn.disabled = true;
  err.style.display = 'none';
  
  const fd = new FormData();
  fd.append('otp', otp);
  
  const res = await fetch('/verify-otp', {
    method: 'POST', body: fd,
    headers: {'Accept': 'application/json'}
  });

  if (res.ok) {
    const data = await res.json().catch(() => null);
    if (data && data.success) {
      clearInterval(otpTimerInterval);
      document.body.style.opacity = '0';
      window.location.replace(data.redirect || '/dashboard');
      return;
    }
  }

  if (res.status === 302 || res.redirected) {
    clearInterval(otpTimerInterval);
    document.body.style.opacity = '0';
    window.location.replace('/dashboard');
    return;
  }
  
  const text = await res.text();
  if (text.includes('Грешен')) {
    err.textContent = 'Грешен код. Опитай отново.';
  } else if (text.includes('изтекъл')) {
    err.textContent = 'Кодът е изтекъл. Регистрирай се отново.';
  } else {
    err.textContent = 'Грешка. Опитай отново.';
  }
  err.style.display = 'block';
  btn.textContent = 'Потвърди';
  btn.disabled = false;
}


let forgotTimerInt = null;

function openForgotModal() {
  closeLoginModal();
  document.getElementById('forgotModal').style.display = 'block';
  fShowStep(1);
  document.getElementById('forgotEmail').value = '';
  document.getElementById('fStep1Error').style.display = 'none';
  setTimeout(() => document.getElementById('forgotEmail').focus(), 100);
}

function closeForgotModal() {
  document.getElementById('forgotModal').style.display = 'none';
  if (forgotTimerInt) clearInterval(forgotTimerInt);
}

function fShowStep(n) {
  [1,2,3].forEach(i => document.getElementById('fStep'+i).style.display = i===n?'block':'none');
}

async function forgotSendOTP() {
  const email = document.getElementById('forgotEmail').value;
  const err = document.getElementById('fStep1Error');
  if (!email) { err.textContent='Въведи имейл'; err.style.display='block'; return; }
  const fd = new FormData(); fd.append('email', email);
  const r = await fetch('/reset-password', {method:'POST', body:fd});
  const d = await r.json();
  if (d.success) {
    document.getElementById('fStep2Email').textContent = email;
    document.querySelectorAll('.fotp').forEach(i => i.value='');
    document.getElementById('fStep2Error').style.display='none';
    document.getElementById('forgotResendBtn').style.display='none';
    fShowStep(2);
    startForgotTimer();
    setTimeout(() => document.querySelector('.fotp').focus(), 100);
  } else {
    err.textContent = d.message||'Грешка'; err.style.display='block';
  }
}

function startForgotTimer() {
  if (forgotTimerInt) clearInterval(forgotTimerInt);
  let sec = 300;
  const el = document.getElementById('forgotTimer');
  el.style.color = '#635BFF';
  forgotTimerInt = setInterval(() => {
    sec--;
    const m = Math.floor(sec/60), s = sec%60;
    el.textContent = m+':'+(s<10?'0':'')+s;
    if (sec <= 0) {
      clearInterval(forgotTimerInt);
      el.textContent='0:00'; el.style.color='#ef4444';
      document.getElementById('forgotResendBtn').style.display='inline';
    }
  }, 1000);
}

function fotpNext(input) {
  const d = document.querySelectorAll('.fotp');
  const i = Array.from(d).indexOf(input);
  if (input.value && i < d.length-1) d[i+1].focus();
}
function fotpPrev(e, input) {
  if (e.key==='Backspace' && !input.value) {
    const d = document.querySelectorAll('.fotp');
    const i = Array.from(d).indexOf(input);
    if (i>0) d[i-1].focus();
  }
}

document.addEventListener('paste', function(e) {
  const modal = document.getElementById('forgotModal');
  const step2 = document.getElementById('fStep2');
  if (!modal || modal.style.display === 'none' || !step2 || step2.style.display === 'none') return;
  const text = (e.clipboardData || window.clipboardData).getData('text').replace(/\D/g, '').slice(0, 6);
  const digits = document.querySelectorAll('.fotp');
  text.split('').forEach((c, i) => { if (digits[i]) digits[i].value = c; });
  if (digits[text.length - 1]) digits[text.length - 1].focus();
  if (text.length === 6) {
    setTimeout(() => document.getElementById('otpForm').dispatchEvent(new Event('submit', {cancelable: true})), 120);
  }
});

async function forgotResend() {
  const email = document.getElementById('fStep2Email').textContent;
  const btn = document.getElementById('forgotResendBtn');
  btn.textContent='Изпращане...'; btn.disabled=true;
  const fd = new FormData(); fd.append('email', email);
  const r = await fetch('/reset-password', {method:'POST', body:fd});
  const d = await r.json();
  if (d.success) {
    document.querySelectorAll('.fotp').forEach(i=>i.value='');
    btn.style.display='none'; btn.disabled=false;
    btn.textContent='Изпрати кода отново';
    startForgotTimer();
    document.querySelector('.fotp').focus();
  } else {
    btn.textContent='Грешка. Опитай отново.'; btn.disabled=false;
  }
}

async function forgotVerifyOTP() {
  const otp = Array.from(document.querySelectorAll('.fotp')).map(d=>d.value).join('');
  const err = document.getElementById('fStep2Error');
  if (otp.length<6) { err.textContent='Въведи всичките 6 цифри'; err.style.display='block'; return; }
  const fd = new FormData(); fd.append('otp', otp);
  const r = await fetch('/reset-password', {method:'POST', body:fd});
  const d = await r.json();
  if (d.success) {
    if (forgotTimerInt) clearInterval(forgotTimerInt);
    document.getElementById('fNewPass').value='';
    document.getElementById('fConfPass').value='';
    document.getElementById('fStep3Error').style.display='none';
    fShowStep(3);
    setTimeout(() => document.getElementById('fNewPass').focus(), 100);
  } else {
    err.textContent=d.message||'Грешен код'; err.style.display='block';
  }
}

function fToggle(id, iconId) {
  const i=document.getElementById(id), ic=document.getElementById(iconId);
  i.type=i.type==='password'?'text':'password';
  ic.className=i.type==='password'?'fa-solid fa-eye':'fa-solid fa-eye-slash';
}

function fCheckStr(val) {
  const bars=[document.getElementById('fb1'),document.getElementById('fb2'),document.getElementById('fb3')];
  const label=document.getElementById('fStrLabel');
  const score = passwordScore(val);
  const colors=['#EF4444','#F59E0B','#22C55E'];
  bars.forEach((b,i)=>b.style.background=val.length===0?'#e5e7eb':i<score?colors[score-1]:'#e5e7eb');
  label.textContent=val.length>0?['','Слаба','Средна','Силна'][score]:'';
  label.style.color=['','#EF4444','#F59E0B','#22C55E'][score];
}

function fCheckMatch() {
  const p1=document.getElementById('fNewPass').value, p2=document.getElementById('fConfPass').value;
  const msg=document.getElementById('fMatchMsg');
  if(!p2){msg.style.display='none';return;}
  msg.textContent=p1===p2?'✓ Паролите съвпадат':'✗ Паролите не съвпадат';
  msg.style.color=p1===p2?'#22C55E':'#EF4444';
  msg.style.display='block';
}

async function forgotSubmitPass() {
  const p=document.getElementById('fNewPass').value, c=document.getElementById('fConfPass').value;
  const err=document.getElementById('fStep3Error');
  if(p!==c){err.textContent='Паролите не съвпадат';err.style.display='block';return;}
  if(p.length<6){err.textContent='Паролата е прекалено кратка';err.style.display='block';return;}
  const fd=new FormData(); fd.append('password',p); fd.append('confirm_password',c);
  const r=await fetch('/reset-password',{method:'POST',body:fd});
  const d=await r.json();
  if(d.success){
    closeForgotModal();
    window.location.replace(d.redirect||'/?login=1');
  } else {
    err.textContent=d.message||'Грешка'; err.style.display='block';
  }
}
// OTP resend
function resendOTP() {
  const btn = document.getElementById('resendOtpBtn');
  btn.textContent = 'Изпращане...';
  btn.disabled = true;
  fetch('/resend-otp', {method: 'POST'})
    .then(r => r.json())
    .then(d => {
      if (d.success) {
        btn.textContent = 'Кодът е изпратен!';
        // Restart timer
        startOtpTimer();
        setTimeout(() => {
          btn.textContent = 'Изпрати кода отново';
          btn.disabled = false;
          btn.style.display = 'none';
        }, 3000);
      } else {
        btn.textContent = 'Грешка. Опитай отново.';
        btn.disabled = false;
      }
    });
}

// Show resend button when timer expires
const origStartTimer = window.startOtpTimer;


function googleRegisterWithTerms(e) {
    e.preventDefault();
    window.location.href = '/auth/google';
}

function openTerms(e) { if(e) e.preventDefault(); const m=document.getElementById('termsModal'); m.style.display='flex'; m.style.alignItems='center'; m.style.justifyContent='center'; }
function openPrivacy(e) { if(e) e.preventDefault(); const m=document.getElementById('privacyModal'); m.style.display='flex'; m.style.alignItems='center'; m.style.justifyContent='center'; }
document.addEventListener('keydown', function(e) {
    if(e.key==='Escape') {
        document.getElementById('termsModal').style.display='none';
        document.getElementById('privacyModal').style.display='none';
    }
});


window.addEventListener('pageshow', function() {
    ['loginModal','registerModal','forgotModal','termsModal','privacyModal'].forEach(function(id) {
        var el = document.getElementById(id);
        if (el) el.style.display = 'none';
    });
});


let supportCurrentTicketId = null;

function openSupportPopup() {
    const sidebar = document.getElementById('adminSidebar');
    const w = sidebar ? sidebar.offsetWidth : 56;
    const popup = document.getElementById('adminSupportPopup');
    popup.style.left = w + 'px';
    popup.style.display = 'flex';
    spLoadTickets();
}

function closeSupportPopup() {
    document.getElementById('adminSupportPopup').style.display = 'none';
    supportCurrentTicketId = null;
}

async function spLoadTickets() {
    const el = document.getElementById('spTicketList');
    if (!el) return;
    el.innerHTML = '<div style="text-align:center;padding:32px;color:#9ca3af"><i class="fa-solid fa-spinner fa-spin"></i></div>';
    try {
        const tickets = await (await fetch('/admin/support/tickets')).json();
        if (!tickets.length) {
            el.innerHTML = '<div style="text-align:center;padding:40px 12px;color:#9ca3af"><i class="fa-solid fa-inbox" style="font-size:24px;margin-bottom:8px;display:block"></i><p style="font-size:12px;margin:0">Няма запитвания</p></div>';
            return;
        }
        const typeMap = {
            bug: {label:'🐛 Проблем', bg:'#fef2f2', color:'#dc2626', border:'#fecaca'},
            suggestion: {label:'💡 Предложение', bg:'#eff6ff', color:'#2563eb', border:'#bfdbfe'},
            question: {label:'❓ Въпрос', bg:'#eef2ff', color:'#6366f1', border:'#c7d2fe'}
        };
        const statusMap = {
            open: {label:'Отворен', color:'#f59e0b'},
            in_progress: {label:'В процес', color:'#3b82f6'},
            closed: {label:'Затворен', color:'#9ca3af'}
        };
        el.innerHTML = tickets.map(t => {
            const tc = typeMap[t.type] || typeMap.question;
            const sc = statusMap[t.status] || statusMap.open;
            const bl = t.status==='open'?'#f59e0b':t.status==='in_progress'?'#3b82f6':'#e5e7eb';
            const bg = t.unread>0 ? '#eff6ff' : '#fff';
            return '<div onclick="spOpenTicket('+t.id+')" id="spCard_'+t.id+'"'+
                ' style="padding:12px 14px;cursor:pointer;border-bottom:1px solid #f3f4f6;'+
                'border-left:3px solid '+bl+';background:'+bg+';transition:background 0.15s"'+
                ' class="sp-ticket-card" data-bg="'+bg+'" data-id="'+t.id+'">'+
                
                '<p style="font-size:12px;font-weight:'+(t.unread>0?'700':'500')+';color:'+(t.unread>0?'#6366f1':'#111827')+';margin:0 0 2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">'+spEsc(t.email)+'</p>'+
                (t.name?'<p style="font-size:11px;color:#6b7280;margin:0 0 6px">'+spEsc(t.name)+'</p>':'<div style="margin-bottom:6px"></div>')+
                '<div style="display:flex;align-items:center;justify-content:space-between;gap:4px">'+
                '<span style="font-size:9px;font-weight:700;padding:2px 7px;border-radius:20px;background:'+tc.bg+';color:'+tc.color+';border:1px solid '+tc.border+'">'+tc.label+'</span>'+
                '<span style="font-size:9px;font-weight:600;color:'+sc.color+'">● '+sc.label+'</span>'+
                '</div></div>';
        }).join('');
        // Задаваме width на лявата лента
        const leftW = el.offsetWidth || 240;
        document.documentElement.style.setProperty('--sp-left-w', leftW + 'px');
    } catch(e) {
        el.innerHTML = '<div style="padding:16px;color:#9ca3af;font-size:12px">Грешка</div>';
    }
}

async function spOpenTicket(id) {
    supportCurrentTicketId = id;
    document.querySelectorAll('[id^="spCard_"]').forEach(el => {
        el.style.background = '#fff';
    });
    const card = document.getElementById('spCard_' + id);
    if (card) card.style.background = '#eef2ff';
    document.getElementById('spEmpty').style.display = 'none';
    const chat = document.getElementById('spChat');
    chat.style.display = 'flex';
    chat.style.flexDirection = 'column';
    await spLoadMessages(id);
}

async function spLoadMessages(id) {
    const el = document.getElementById('spMessages');
    el.innerHTML = '<div style="text-align:center;padding:20px;color:#9ca3af"><i class="fa-solid fa-spinner fa-spin"></i></div>';
    const data = await (await fetch('/admin/support/' + id + '/messages')).json();
    const typeLabels = {bug:'🐛 Проблем', suggestion:'💡 Предложение', question:'❓ Въпрос'};
    const statusLabels = {open:'Отворен', in_progress:'В процес', closed:'Затворен'};
    document.getElementById('spChatEmail').textContent = data.user.email;
    document.getElementById('spChatMeta').textContent =
        (data.user.name||'') + ' · ' + (typeLabels[data.ticket.type]||'') + ' · ' + (statusLabels[data.ticket.status]||'');
    document.getElementById('spCloseTicketBtn').style.display = data.ticket.status==='closed'?'none':'block';
    el.innerHTML = data.messages.map(m =>
        '<div style="display:flex;'+(m.sender==='admin'?'justify-content:flex-end':'justify-content:flex-start')+'">'+
        '<div style="max-width:72%;padding:9px 13px;line-height:1.5;'+
        'border-radius:'+(m.sender==='admin'?'14px 14px 4px 14px':'14px 14px 14px 4px')+';'+
        'background:'+(m.sender==='admin'?'#111827':'#f3f4f6')+';'+
        'color:'+(m.sender==='admin'?'#fff':'#111827')+'">'+
        '<p style="font-size:13px;margin:0 0 3px">'+spEsc(m.body)+'</p>'+
        '<p style="font-size:10px;margin:0;opacity:0.5;text-align:right">'+
        (m.sender==='admin'?'Вие':spEsc(data.user.name||'Потребител'))+' · '+m.created_at+
        '</p></div></div>'
    ).join('');
    el.scrollTop = el.scrollHeight;
}

async function spSendReply() {
    const body = document.getElementById('spReplyInput').value.trim();
    if (!body || !supportCurrentTicketId) return;
    const fd = new FormData();
    fd.append('body', body);
    const d = await (await fetch('/admin/support/'+supportCurrentTicketId+'/reply',{method:'POST',body:fd})).json();
    if (d.success) {
        document.getElementById('spReplyInput').value = '';
        await spLoadMessages(supportCurrentTicketId);
        await spLoadTickets();
    }
}

async function spCloseTicket() {
    if (!supportCurrentTicketId) return;
    const d = await (await fetch('/admin/support/'+supportCurrentTicketId+'/close',{method:'POST'})).json();
    if (d.success) {
        document.getElementById('spCloseTicketBtn').style.display = 'none';
        await spLoadMessages(supportCurrentTicketId);
        await spLoadTickets();
    }
}

function spEsc(s) {
    return String(s||'').replace(/&/g,'&amp;').replace(/\x3c/g,'&lt;').replace(/\x3e/g,'&gt;');
}

window.addEventListener('pageshow', function() {
    const p = document.getElementById('adminSupportPopup');
    if (p) p.style.display = 'none';
    supportCurrentTicketId = null;
});


