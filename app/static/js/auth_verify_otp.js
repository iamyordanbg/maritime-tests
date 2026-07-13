// app/static/js/auth_verify_otp.js
// OTP verification — извлечена от app/templates/auth/verify_otp.html (Правило 1).

// OTP input navigation
function moveNext(input) {
  const digits = document.querySelectorAll('.otp-digit');
  const idx = Array.from(digits).indexOf(input);
  if (input.value && idx < digits.length - 1) digits[idx + 1].focus();
  updateOTP();
}
function movePrev(e, input) {
  if (e.key === 'Backspace' && !input.value) {
    const digits = document.querySelectorAll('.otp-digit');
    const idx = Array.from(digits).indexOf(input);
    if (idx > 0) digits[idx - 1].focus();
  }
}
function updateOTP() {
  const digits = document.querySelectorAll('.otp-digit');
  document.getElementById('otpValue').value = Array.from(digits).map(d => d.value).join('');
}

// Handle paste
document.addEventListener('paste', function(e) {
  const text = (e.clipboardData || window.clipboardData).getData('text').replace(/\D/g, '').slice(0, 6);
  const digits = document.querySelectorAll('.otp-digit');
  text.split('').forEach((c, i) => { if (digits[i]) digits[i].value = c; });
  updateOTP();
  if (digits[text.length - 1]) digits[text.length - 1].focus();
});

// 5 minute countdown
let seconds = 300;
const timerEl = document.getElementById('timer');
if (timerEl) {
  const interval = setInterval(() => {
    seconds--;
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    timerEl.textContent = m + ':' + (s < 10 ? '0' : '') + s;
    if (seconds <= 0) {
      clearInterval(interval);
      timerEl.textContent = '0:00';
      timerEl.style.color = '#ef4444';
    }
  }, 1000);
}

// Auto-focus first digit
document.querySelector('.otp-digit')?.focus();
