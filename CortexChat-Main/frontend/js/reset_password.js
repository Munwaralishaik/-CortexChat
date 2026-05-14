/**
 * frontend/js/reset_password.js — Entry Point: Password Reset
 * 
 * Secures the reset flow, requiring a valid token in sessionStorage.
 */

import { handleResetPassword, togglePasswordVisibility } from './auth.js';

if (!sessionStorage.getItem('CortexChat_reset_token')) {
  window.location.href = 'forgot_password.html';
}

const resetPasswordForm = document.getElementById('resetPasswordForm');
if (resetPasswordForm) {
  resetPasswordForm.addEventListener('submit', handleResetPassword);
}

togglePasswordVisibility('newPassword', 'newPwToggle');
togglePasswordVisibility('confirmNewPassword', 'confirmNewPwToggle');
