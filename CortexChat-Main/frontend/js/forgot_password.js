/**
 * frontend/js/forgot_password.js — Entry Point: Forgot Password
 * 
 * Attaches event listeners to the password recovery form.
 */

import { handleForgotPassword } from './auth.js';

const forgotForm = document.getElementById('forgotForm');
if (forgotForm) {
  forgotForm.addEventListener('submit', handleForgotPassword);
}
