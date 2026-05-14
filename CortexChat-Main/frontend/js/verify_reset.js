/**
 * frontend/js/verify_reset.js — Entry Point: OTP Password Reset Verification
 * 
 * Manages the 6-digit code input required before assigning a new password.
 */

import { handleVerifyReset, initOTPInputs } from './auth.js';

const email = sessionStorage.getItem('CortexChat_reset_email');
const resetEmailEl = document.getElementById('resetEmail');

if (!email) {
  window.location.href = 'forgot_password.html';
} else if (resetEmailEl) {
  resetEmailEl.textContent = email;
}

initOTPInputs();

const verifyResetForm = document.getElementById('verifyResetForm');
if (verifyResetForm) {
  verifyResetForm.addEventListener('submit', handleVerifyReset);
}
