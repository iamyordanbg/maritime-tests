// app/static/js/auth_reset.js
// Password reset — извлечена от app/templates/auth/reset.html (Правило 1).

let resetTimerInterval = null;

function showStep(n) {
  [1,2,3].forEach(i => document.getElementById('step'+i).style.display = i===n ? 'block' : 'none');
}

async function sendResetOTP() {
  const email = document.getElementById('resetEmail').value;
  const err = document.getElementById('step1Error');
  if (!email) { err.textContent='Въведи имейл'; err.style.display='block'; return; }
  
  const fd = new FormData();
  fd.append('email', email);
  const r = await fetch('/reset-password', {method:'POST', body:fd});
  const d = await r.json();
  if (d.success) {
    document.getElementById('step2Email').textContent = email;
    showStep(2);
    startResetTimer();
    setTimeout(() => document.querySelector('.rotp').focus(), 100);
  } else {
    err.textContent = d.message || 'Грешка';
    err.style.display = 'block';
  }
}

function startResetTimer() {
  if (resetTimerInterval) clearInterval(resetTimerInterval);
  let sec = 300;
  const el = document.getElementById('resetTimer');
  resetTimerInterval = setInterval(() => {
    sec--;
    const m = Math.floor(sec/60), s = sec%60;
    el.textContent = m + ':' + (s<10?'0':'') + s;
    if (sec <= 0) {
      clearInterval(resetTimerInterval);
      el.textContent = '0:00'; el.style.color = '#ef4444';
      document.getElementById('resendResetBtn').style.display = 'block';
    }
  }, 1000);
}

function rotpNext(input) {
  const digits = document.querySelectorAll('.rotp');
  const idx = Array.from(digits).indexOf(input);
  if (input.value && idx < digits.length-1) digits[idx+1].focus();
}
function rotpPrev(e, input) {
  if (e.key==='Backspace' && !input.value) {
    const digits = document.querySelectorAll('.rotp');
    const idx = Array.from(digits).indexOf(input);
    if (idx>0) digits[idx-1].focus();
  }
}

async function verifyResetOTP() {
  const otp = Array.from(document.querySelectorAll('.rotp')).map(d=>d.value).join('');
  const err = document.getElementById('step2Error');
  if (otp.length < 6) { err.textContent='Въведи всичките 6 цифри'; err.style.display='block'; return; }
  
  const fd = new FormData();
  fd.append('otp', otp);
  const r = await fetch('/reset-password', {method:'POST', body:fd});
  const d = await r.json();
  if (d.success) {
    showStep(3);
    setTimeout(() => document.getElementById('newPass').focus(), 100);
  } else {
    err.textContent = d.message || 'Грешен код';
    err.style.display = 'block';
  }
}

async function resendResetOTP() {
  const email = document.getElementById('step2Email').textContent;
  const fd = new FormData();
  fd.append('email', email);
  const r = await fetch('/reset-password', {method:'POST', body:fd});
  const d = await r.json();
  if (d.success) {
    document.getElementById('resendResetBtn').style.display = 'none';
    document.querySelectorAll('.rotp').forEach(d=>d.value='');
    startResetTimer();
    document.querySelector('.rotp').focus();
  }
}

function rToggle(id, iconId) {
  const i = document.getElementById(id);
  const ic = document.getElementById(iconId);
  i.type = i.type==='password'?'text':'password';
  ic.className = i.type==='password'?'fa-solid fa-eye':'fa-solid fa-eye-slash';
}

function rCheckStrength(val) {
  const bars = [document.getElementById('rbar1'),document.getElementById('rbar2'),document.getElementById('rbar3')];
  const label = document.getElementById('rStrengthLabel');
  let score = 0;
  if (val.length>=6) score++;
  if (val.length>=10) score++;
  if (/[0-9]/.test(val) && /[a-zA-Z]/.test(val)) score++;
  const colors = ['#EF4444','#F59E0B','#22C55E'];
  const labels = ['','Слаба','Средна','Силна'];
  bars.forEach((b,i) => b.style.background = i<score ? colors[score-1] : '#e5e7eb');
  label.textContent = val.length>0 ? labels[score] : '';
  label.style.color = ['','#EF4444','#F59E0B','#22C55E'][score];
}

function rCheckMatch() {
  const p1 = document.getElementById('newPass').value;
  const p2 = document.getElementById('confirmPass').value;
  const msg = document.getElementById('rMatchMsg');
  if (!p2) { msg.style.display='none'; return; }
  msg.textContent = p1===p2 ? '✓ Паролите съвпадат' : '✗ Паролите не съвпадат';
  msg.style.color = p1===p2 ? '#22C55E' : '#EF4444';
  msg.style.display = 'block';
}

async function submitNewPassword() {
  const password = document.getElementById('newPass').value;
  const confirm = document.getElementById('confirmPass').value;
  const err = document.getElementById('step3Error');
  
  if (password !== confirm) { err.textContent='Паролите не съвпадат'; err.style.display='block'; return; }
  if (password.length < 6) { err.textContent='Паролата е прекалено кратка'; err.style.display='block'; return; }
  
  const fd = new FormData();
  fd.append('password', password);
  fd.append('confirm_password', confirm);
  const r = await fetch('/reset-password', {method:'POST', body:fd});
  const d = await r.json();
  if (d.success) {
    window.location.replace(d.redirect || '/?login=1');
  } else {
    err.textContent = d.message || 'Грешка';
    err.style.display = 'block';
  }
}

// Handle paste on OTP
document.addEventListener('paste', function(e) {
  if (document.getElementById('step2').style.display === 'none') return;
  const text = (e.clipboardData||window.clipboardData).getData('text').replace(/\D/g,'').slice(0,6);
  const digits = document.querySelectorAll('.rotp');
  text.split('').forEach((c,i) => { if (digits[i]) digits[i].value = c; });
  if (digits[text.length-1]) digits[text.length-1].focus();
});
