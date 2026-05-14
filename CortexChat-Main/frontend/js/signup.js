/**
 * frontend/js/signup.js — Entry Point: Account Registration
 * 
 * Bootstraps the signup page. Redirects authenticated users to the dashboard.
 */

import { Auth } from './api.js';
import { handleSignup, togglePasswordVisibility } from './auth.js';

// Redirect if already logged in
if (Auth.isLoggedIn()) {
  window.location.href = 'dashboard.html';
}

const signupForm = document.getElementById('signupForm');
if (signupForm) {
  signupForm.addEventListener('submit', handleSignup);
}

togglePasswordVisibility('signupPassword', 'signupPwToggle');
togglePasswordVisibility('signupConfirm', 'signupConfirmToggle');
