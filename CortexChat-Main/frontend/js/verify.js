/**
 * frontend/js/verify.js — Entry Point: OTP Signup Verification
 * 
 * Manages the 6-digit code input and countdown timer for new accounts.
 */

import { handleVerify, handleResend, initOTPInputs, startCountdown } from './auth.js';

// Must arrive here from signup form only
const email = sessionStorage.getItem('CortexChat_pending_email');
const pendingEmailEl = document.getElementById('pendingEmail');

if (!email) {
  window.location.href = 'signup.html';
} else if (pendingEmailEl) {
  pendingEmailEl.textContent = email;
}

const verifyForm = document.getElementById('verifyForm');
if (verifyForm) {
  verifyForm.addEventListener('submit', handleVerify);
}

const resendBtn = document.getElementById('resendBtn');
if (resendBtn) {
  resendBtn.addEventListener('click', handleResend);
}

initOTPInputs();
startCountdown(60);
