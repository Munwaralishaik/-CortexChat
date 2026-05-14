/**
 * frontend/js/index.js — Entry Point: Login
 * 
 * Bootstraps the login page. Redirects authenticated users to the dashboard.
 */

import { Auth } from './api.js';
import { handleLogin, togglePasswordVisibility } from './auth.js';

// Redirect if already logged in
if (Auth.isLoggedIn()) {
  window.location.href = 'dashboard.html';
}

const loginForm = document.getElementById('loginForm');
if (loginForm) {
  loginForm.addEventListener('submit', handleLogin);
}

togglePasswordVisibility('loginPassword', 'loginPwToggle');
