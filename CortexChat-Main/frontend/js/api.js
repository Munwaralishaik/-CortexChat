/**
 * frontend/js/api.js — Centralized API Client & Networking Layer
 *
 * All HTTP requests to the CortexChat backend pass through this module. 
 * Responsibilities include:
 *   - Base URL configuration (auto-detects host environment).
 *   - JWT Bearer Token injection into Authorization headers.
 *   - Unified error handling (throwing clean exceptions on non-2xx responses).
 *   - Exporting grouped API classes (Auth, ChatAPI, UploadAPI, ExportAPI, UserAPI).
 */

// Empty BASE_URL makes all requests relative to the current host (since backend serves frontend)
const BASE_URL = '/api';
const TOKEN_KEY = 'CortexChat_token';

// ─── Core fetch wrapper ────────────────────────────────────────────────────

async function apiFetch(path, options = {}) {
  const token = localStorage.getItem(TOKEN_KEY);
  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  };

  // Let browser set Content-Type for FormData (includes multipart boundary)
  if (options.body instanceof FormData) delete headers['Content-Type'];

  const res = await fetch(`${BASE_URL}${path}`, { ...options, headers });
  if (res.status === 204) return null;

  if (!res.ok) {
    let message = `HTTP ${res.status}`;
    try {
      const err = await res.json();
      if (Array.isArray(err.detail)) {
        message = err.detail.map(e => e.msg).join(', ');
      } else {
        message = err.detail || JSON.stringify(err);
      }
    } catch (_) { /* ignore JSON parse errors */ }

    if (res.status === 401) {
      // Auto-logout only if not already on the login/index page
      if (!window.location.pathname.endsWith('index.html') && window.location.pathname !== '/') {
        Auth.logout(); 
      }
      throw new Error(message || 'Unauthorized');
    }

    throw new Error(message);
  }

  const contentType = res.headers.get('Content-Type') || '';
  if (contentType.includes('application/json')) return res.json();
  if (contentType.includes('application/pdf'))   return res.blob();
  return res.text();
}

// ─── Auth ─────────────────────────────────────────────────────────────────

export const Auth = {
  /** Step 1 of signup: name + email + password → OTP sent to email */
  signup: (name, email, password) =>
    apiFetch('/auth/signup', {
      method: 'POST',
      body: JSON.stringify({ name, email, password }),
    }),

  /** Step 2 of signup: verify OTP code → activate account → JWT */
  verifySignup: (email, otp_code) =>
    apiFetch('/auth/verify-signup', {
      method: 'POST',
      body: JSON.stringify({ email, otp_code }),
    }),

  /** Login: email + password → JWT (no OTP) */
  login: (email, password) =>
    apiFetch('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),

  forgotPassword: (email) =>
    apiFetch('/auth/forgot-password', {
      method: 'POST',
      body: JSON.stringify({ email }),
    }),

  verifyReset: (email, otp_code) =>
    apiFetch('/auth/verify-reset', {
      method: 'POST',
      body: JSON.stringify({ email, otp_code }),
    }),

  resetPassword: (reset_token, new_password) =>
    apiFetch('/auth/reset-password', {
      method: 'POST',
      body: JSON.stringify({ reset_token, new_password }),
    }),

  logout() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem('activeChatId');
    localStorage.removeItem('activeChatTitle');
    window.location.href = '/pages/index.html';
  },

  saveToken: (token) => localStorage.setItem(TOKEN_KEY, token),
  getToken:  ()      => localStorage.getItem(TOKEN_KEY),
  isLoggedIn:()      => !!localStorage.getItem(TOKEN_KEY),
};

// ─── Chat ─────────────────────────────────────────────────────────────────

export const ChatAPI = {
  newChat: (title = 'New Chat') =>
    apiFetch('/chat/new', { method: 'POST', body: JSON.stringify({ title }) }),

  sendMessage: (chat_id, content, file_id = null, language = 'English', summary_mode = null) =>
    apiFetch('/chat/message', {
      method: 'POST',
      body: JSON.stringify({ chat_id, content, file_id, language, summary_mode }),
    }),

  sendMessageStream: async (chat_id, content, file_id = null, language = "English", onToken) => {
    const token = localStorage.getItem(TOKEN_KEY);
    const response = await fetch(`${BASE_URL}/chat/message/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ chat_id, content, file_id, language }),
    });

    if (!response.ok) throw new Error(`Streaming failed: ${response.statusText}`);

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value, { stream: true });
      if (onToken) onToken(chunk);
    }
  },

  getHistory: () => apiFetch('/chat/history'),
  getChat:    (id) => apiFetch(`/chat/${id}`),
  updateChat: (id, updates) => apiFetch(`/chat/${id}`, { method: 'PATCH', body: JSON.stringify(updates) }),
  deleteChat: (id) => apiFetch(`/chat/${id}`, { method: 'DELETE' }),
};

// ─── Upload ───────────────────────────────────────────────────────────────

export const UploadAPI = {
  uploadFile: (file, chatId = null) => {
    const fd = new FormData();
    fd.append('file', file);
    if (chatId) fd.append('chat_id', chatId);
    return apiFetch('/upload/document', { method: 'POST', body: fd });
  },
  uploadFileWithProgress: (file, chatId = null, onProgress) => {
    return new Promise((resolve, reject) => {
      const fd = new FormData();
      fd.append('file', file);
      if (chatId) fd.append('chat_id', chatId);

      const xhr = new XMLHttpRequest();
      xhr.open('POST', `${BASE_URL}/upload/document`);
      
      const token = localStorage.getItem(TOKEN_KEY);
      if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`);

      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable && onProgress) {
          const percent = Math.round((e.loaded / e.total) * 100);
          onProgress(percent);
        }
      };

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(JSON.parse(xhr.responseText));
        } else {
          reject(new Error(xhr.responseText || `Status ${xhr.status}`));
        }
      };
      xhr.onerror = () => reject(new Error('Network error'));
      xhr.send(fd);
    });
  },
  listFiles:  () => apiFetch('/upload/files'),
  deleteFile: (id) => apiFetch(`/upload/files/${id}`, { method: 'DELETE' }),
};

// ─── Export ───────────────────────────────────────────────────────────────

export const ExportAPI = {
  exportPDF: (chat_id, messages = null, filename = null) =>
    apiFetch('/export/pdf', { 
      method: 'POST', 
      body: JSON.stringify({ chat_id, messages, filename }) 
    }),
};

// ─── User ─────────────────────────────────────────────────────────────────

export const UserAPI = {
  getProfile:        () => apiFetch('/user/profile'),
  getInit:           () => apiFetch('/user/init'),
  patchProfile:      (body) => apiFetch('/user/profile', { method: 'PATCH', body: JSON.stringify(body) }),
  updatePreferences: (prefs) =>
    apiFetch('/user/preferences', { method: 'PATCH', body: JSON.stringify(prefs) }),
  deleteUser: () => apiFetch('/user/', { method: 'DELETE' }),
};
