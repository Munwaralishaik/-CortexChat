/**
 * frontend/js/auth.js — Authentication Workflow Controllers
 *
 * Encapsulates the UI logic and API coordination for all identity flows:
 *   - Login (index.html): Email/Password validation -> JWT storage.
 *   - Registration (signup.html): Account creation -> OTP email dispatch.
 *   - Verification (verify.html & verify_reset.html): 6-digit OTP handling.
 *   - Password Reset: Forgot password -> OTP verification -> New password assignment.
 *
 * Interacts directly with `api.js` and updates `sessionStorage` state.
 */

import { Auth } from './api.js';

// ─── Page Transitions ──────────────────────────────────────────────────────

// Check if we arrived here via a slide transition
const direction = sessionStorage.getItem('nav_direction');
if (direction) {
  const card = document.querySelector('.auth-card');
  if (card) {
    // Cancel the default fade-up so it doesn't compete with slide-in
    card.style.animation = 'none';
    void card.offsetWidth; // force reflow
    card.classList.add(direction === 'left' ? 'slide-in-right' : 'slide-in-left');
  }
  sessionStorage.removeItem('nav_direction');
}

// Handle bfcache (back button) restoring loading states
window.addEventListener('pageshow', (e) => {
  if (e.persisted) {
    document.querySelectorAll('form').forEach(f => f.reset());
    document.querySelectorAll('.btn').forEach(btn => setLoading(btn, false));
    const card = document.querySelector('.auth-card');
    if (card) {
      card.classList.remove('slide-out-left', 'slide-out-right', 'slide-in-left', 'slide-in-right');
    }
  }
});

// Helper to reliably trigger a slide out
function triggerSlideOut(dir, href) {
  sessionStorage.setItem('nav_direction', dir);
  const card = document.querySelector('.auth-card');
  if (card) {
    card.classList.remove('slide-in-left', 'slide-in-right', 'slide-out-left', 'slide-out-right');
    // Force reflow to ensure the new class triggers an animation
    void card.offsetWidth;
    card.classList.add(`slide-out-${dir}`);
    setTimeout(() => { window.location.href = href; }, 140);
  } else {
    window.location.href = href;
  }
}

// Handle clicks on navigation links
document.addEventListener('click', (e) => {
  if (e.target.matches('a.nav-link')) {
    e.preventDefault();
    const href = e.target.getAttribute('href');
    const dir = e.target.getAttribute('data-direction'); // "left" or "right"
    if (dir) {
      triggerSlideOut(dir, href);
    } else {
      window.location.href = href;
    }
  }
});

// ─── Login ─────────────────────────────────────────────────────────────────

export async function handleLogin(event) {
  event.preventDefault();
  clearError();

  const email    = document.getElementById('loginEmail').value.trim();
  const password = document.getElementById('loginPassword').value;
  const btn      = document.getElementById('loginBtn');

  if (!email || !password) return showError('Please enter your email and password.');

  setLoading(btn, true);
  try {
    const res = await Auth.login(email, password);
    Auth.saveToken(res.access_token);
    window.location.href = 'dashboard.html';
  } catch (err) {
    showError(err.message);
    setLoading(btn, false);
  }
}

// ─── Signup ────────────────────────────────────────────────────────────────

export async function handleSignup(event) {
  event.preventDefault();
  clearError();

  const name     = document.getElementById('signupName').value.trim();
  const email    = document.getElementById('signupEmail').value.trim();
  const password = document.getElementById('signupPassword').value;
  const confirm  = document.getElementById('signupConfirm').value;
  const btn      = document.getElementById('signupBtn');

  if (!name || !email || !password) return showError('All fields are required.');
  if (password.length < 8)          return showError('Password must be at least 8 characters.');
  if (password !== confirm)         return showError('Passwords do not match.');

  setLoading(btn, true);
  try {
    await Auth.signup(name, email, password);
    sessionStorage.setItem('CortexChat_pending_email', email);
    
    // Smooth transition
    triggerSlideOut('left', 'verify.html');
  } catch (err) {
    showError(err.message);
    setLoading(btn, false);
  }
}

// ─── OTP Verify (signup step 2) ────────────────────────────────────────────

export async function handleVerify(event) {
  event.preventDefault();
  clearError();

  const email = sessionStorage.getItem('CortexChat_pending_email');
  if (!email) { window.location.href = 'signup.html'; return; }

  // Collect 6 OTP digits
  const digits = [...document.querySelectorAll('.otp-digit')]
    .map(el => el.value)
    .join('');

  if (digits.length < 6) return showError('Enter the full 6-digit code.');

  const btn = document.getElementById('verifyBtn');
  setLoading(btn, true);

  try {
    const res = await Auth.verifySignup(email, digits);
    Auth.saveToken(res.access_token);
    sessionStorage.removeItem('CortexChat_pending_email');
    window.location.href = 'dashboard.html';
  } catch (err) {
    showError(err.message);
    setLoading(btn, false);
  }
}

export async function handleResend() {
  clearError();
  const email    = sessionStorage.getItem('CortexChat_pending_email');
  const password = sessionStorage.getItem('CortexChat_pending_pw') || '';
  if (!email) return;

  try {
    // Re-trigger signup which resends the OTP
    await Auth.signup('', email, password || 'resend');
    showSuccess('A new code has been sent to your email.');
    startCountdown();
  } catch (err) {
    showError(err.message);
  }
}

// ─── Forgot Password Flow ────────────────────────────────────────────────────

export async function handleForgotPassword(event) {
  event.preventDefault();
  clearError();
  const el = document.getElementById('formSuccess');
  if (el) el.style.display = 'none';

  const email = document.getElementById('forgotEmail').value.trim();
  const btn = document.getElementById('forgotBtn');
  if (!email) return showError('Please enter your email.');

  setLoading(btn, true);
  try {
    const res = await Auth.forgotPassword(email);
    sessionStorage.setItem('CortexChat_reset_email', email);
    
    // Smooth transition
    triggerSlideOut('left', 'verify_reset.html');
  } catch (err) {
    showError(err.message);
    setLoading(btn, false);
  }
}

export async function handleVerifyReset(event) {
  event.preventDefault();
  clearError();

  const email = sessionStorage.getItem('CortexChat_reset_email');
  if (!email) { window.location.href = 'forgot_password.html'; return; }

  const digits = [...document.querySelectorAll('.otp-digit')].map(el => el.value).join('');
  if (digits.length < 6) return showError('Enter the full 6-digit code.');

  const btn = document.getElementById('verifyResetBtn');
  setLoading(btn, true);
  try {
    const res = await Auth.verifyReset(email, digits);
    sessionStorage.setItem('CortexChat_reset_token', res.reset_token);
    
    // Smooth transition
    triggerSlideOut('left', 'reset_password.html');
  } catch (err) {
    showError(err.message);
    setLoading(btn, false);
  }
}

export async function handleResetPassword(event) {
  event.preventDefault();
  clearError();

  const resetToken = sessionStorage.getItem('CortexChat_reset_token');
  if (!resetToken) { window.location.href = 'forgot_password.html'; return; }

  const newPassword = document.getElementById('newPassword').value;
  const confirm = document.getElementById('confirmNewPassword').value;
  const btn = document.getElementById('resetPasswordBtn');

  if (!newPassword) return showError('Please enter a new password.');
  if (newPassword.length < 8) return showError('Password must be at least 8 characters.');
  if (newPassword !== confirm) return showError('Passwords do not match.');

  setLoading(btn, true);
  try {
    const res = await Auth.resetPassword(resetToken, newPassword);
    sessionStorage.removeItem('CortexChat_reset_email');
    sessionStorage.removeItem('CortexChat_reset_token');
    
    showToast('Password reset successfully. Redirecting...');
    setTimeout(() => {
      triggerSlideOut('right', 'index.html');
    }, 1500);
  } catch (err) {
    showError(err.message);
    setLoading(btn, false);
  }
}

// ─── OTP input keyboard UX ─────────────────────────────────────────────────

export function initOTPInputs() {
  const inputs = [...document.querySelectorAll('.otp-digit')];
  inputs.forEach((input, i) => {
    input.addEventListener('input', () => {
      input.classList.toggle('filled', !!input.value);
      if (input.value && i < inputs.length - 1) inputs[i + 1].focus();
    });
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Backspace' && !input.value && i > 0) inputs[i - 1].focus();
    });
    input.addEventListener('paste', (e) => {
      const paste = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6);
      paste.split('').forEach((ch, idx) => {
        if (inputs[idx]) { inputs[idx].value = ch; inputs[idx].classList.add('filled'); }
      });
      if (paste.length === 6) inputs[5].focus();
      e.preventDefault();
    });
  });
}

// ─── Countdown timer for resend ─────────────────────────────────────────────

export function startCountdown(seconds = 60) {
  const btn   = document.getElementById('resendBtn');
  const label = document.getElementById('countdownLabel');
  if (!btn || !label) return;

  btn.disabled  = true;
  let remaining = seconds;

  const tick = () => {
    label.textContent = `Resend in ${remaining}s`;
    if (remaining <= 0) { btn.disabled = false; label.textContent = ''; return; }
    remaining--;
    setTimeout(tick, 1000);
  };
  tick();
}

// ─── Helpers ───────────────────────────────────────────────────────────────

function showToast(msg) {
  let container = document.querySelector('.toast-container');
  if (!container) {
    container = document.createElement('div');
    container.className = 'toast-container';
    document.body.appendChild(container);
  }
  const toast = document.createElement('div');
  toast.className = 'toast';
  toast.style.background = 'var(--bg-elevated)';
  toast.style.color = 'var(--text-primary)';
  toast.style.border = '1px solid var(--border)';
  toast.textContent = msg;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.3s';
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}

function showError(msg) {
  const el = document.getElementById('formError');
  if (!el) return;
  el.textContent = msg;
  el.style.color = 'var(--text-primary)';
  el.style.background = 'var(--bg-elevated)';
  el.style.border = '1px solid var(--border)';
  el.style.padding = '8px 12px';
  el.style.borderRadius = 'var(--radius-sm)';
  el.style.display = 'block';
  el.style.textAlign = 'center';
}

function showSuccess(msg) {
  showToast(msg);
}

function clearError() {
  const el = document.getElementById('formError');
  if (el) el.style.display = 'none';
}

function setLoading(btn, loading) {
  if (!btn) return;
  if (loading) {
    const width = btn.offsetWidth;
    btn.dataset.original = btn.innerHTML;
    btn.style.width = width + 'px';
    btn.style.minWidth = width + 'px';
    btn.innerHTML = '<div class="spinner"></div>';
    btn.disabled  = true;
  } else {
    btn.innerHTML = btn.dataset.original || btn.innerHTML;
    btn.style.width = '';
    btn.style.minWidth = '';
    btn.disabled  = false;
  }
}

// ─── Password visibility toggle ─────────────────────────────────────────────

export function togglePasswordVisibility(inputId, toggleId) {
  const input  = document.getElementById(inputId);
  const toggle = document.getElementById(toggleId);
  if (!input || !toggle) return;

  const eyeSVG = `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="eye-icon"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"></path><circle cx="12" cy="12" r="3"></circle></svg>`;
  const eyeOffSVG = `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="eye-icon"><path d="M9.88 9.88a3 3 0 1 0 4.24 4.24"></path><path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68"></path><path d="M6.61 6.61A13.526 13.526 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61"></path><line x1="2" x2="22" y1="2" y2="22"></line></svg>`;

  toggle.addEventListener('click', () => {
    const isHidden = input.type === 'password';
    input.type     = isHidden ? 'text' : 'password';
    toggle.innerHTML = isHidden ? eyeOffSVG : eyeSVG;
  });
}
