/**
 * frontend/js/upload.js — Drag-and-Drop Document Processing
 *
 * Manages the file upload lifecycle for the RAG pipeline.
 *   - UI Interactions: Handles drag-over, drop, and file input selection events.
 *   - API Integration: Submits `FormData` containing the file to the backend parsing engine.
 *   - State Updates: Refreshes the Sidebar document list upon successful upload and indexing.
 */

import { UploadAPI, ChatAPI } from './api.js';

export function initUpload({ dropZone, fileInput, filesPanel, activeDocBadge, activeDocName, showToast, onUpload, getActiveChatId, onNewChatCreated, initialData = null }) {
  let activeFileId = null;
  let currentLoadChatId = null;
  const docCache = {}; // Cache doc list per chat

  if (initialData) {
    // Populate cache with files from super-endpoint
    initialData.forEach(f => {
      if (f.chat_id) {
        if (!docCache[f.chat_id]) docCache[f.chat_id] = [];
        docCache[f.chat_id].push(f);
      }
    });
  }

  // ─── Delete modal state ───────────────────────────────────────────────────
  let pendingDeleteId   = null;
  let pendingDeleteName = null;
  let pendingChatId     = null;

  const deleteOverlay  = document.getElementById('docDeleteOverlay');
  const deleteNameEl   = document.getElementById('docDeleteName');
  const deleteConfirm  = document.getElementById('docDeleteConfirm');
  const deleteCancel   = document.getElementById('docDeleteCancel');

  if (deleteCancel)  deleteCancel.addEventListener('click',  closeDeleteModal);
  if (deleteOverlay) deleteOverlay.addEventListener('click', (e) => { if (e.target === deleteOverlay) closeDeleteModal(); });
  if (deleteConfirm) deleteConfirm.addEventListener('click', async () => {
    if (!pendingDeleteId) return;
    try {
      await UploadAPI.deleteFile(pendingDeleteId);
      showToast('Document deleted', 'info');
      if (pendingDeleteId === activeFileId) {
        activeFileId = null;
        activeDocBadge.style.display = 'none';
      }
      closeDeleteModal();
      if (pendingChatId) await loadFilesForChat(pendingChatId);
    } catch (err) {
      showToast(`Failed to delete: ${err.message}`, 'error');
      closeDeleteModal();
    }
  });

  function openDeleteModal(id, name, chatId) {
    pendingDeleteId   = id;
    pendingDeleteName = name;
    pendingChatId     = chatId;
    if (deleteNameEl) deleteNameEl.textContent = name;
    if (deleteConfirm) deleteConfirm.classList.add('btn-danger');
    if (deleteOverlay) deleteOverlay.classList.add('open');
  }

  function closeDeleteModal() {
    pendingDeleteId = null;
    if (deleteOverlay) deleteOverlay.classList.remove('open');
  }

  // ─── Drag-and-drop events ─────────────────────────────────────────────────
  dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('dragover');
  });
  dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
  dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    const file = e.dataTransfer.files[0];
    if (file) uploadFile(file);
  });

  // ─── File input change ────────────────────────────────────────────────────
  fileInput.addEventListener('change', () => {
    if (fileInput.files[0]) uploadFile(fileInput.files[0]);
    fileInput.value = '';
  });

  // ─── Upload logic ─────────────────────────────────────────────────────────
  // ─── Upload logic ─────────────────────────────────────────────────────────
  async function uploadFile(file) {
    let chatId = getActiveChatId ? getActiveChatId() : null;
    if (!chatId) {
      try {
        const chat = await ChatAPI.newChat();
        chatId = chat.id;
        if (onNewChatCreated) await onNewChatCreated(chat);
      } catch (err) {
        showToast('Failed to create chat for upload.', 'error');
        return;
      }
    }

    // ── Build placeholder card with progress bar ──────────────────────────
    const placeholder = document.createElement('div');
    placeholder.className = 'doc-card uploading';
    placeholder.innerHTML = `
      <div class="upload-progress-container">
        <div class="upload-progress-bar" id="upbar-${Date.now()}" style="width:0%"></div>
      </div>
      <div class="upload-text" id="uptext-${Date.now()}">Uploading...</div>
      <div class="doc-card-name" style="font-size:10px;margin-top:4px;">${file.name}</div>
    `;

    const grid = filesPanel.querySelector('.doc-cards-grid');
    if (grid) grid.appendChild(placeholder);
    else {
      filesPanel.innerHTML = '<div class="doc-cards-grid"></div>';
      filesPanel.querySelector('.doc-cards-grid').appendChild(placeholder);
    }

    const progressBar = placeholder.querySelector('.upload-progress-bar');
    const uploadText  = placeholder.querySelector('.upload-text');

    // Smooth easing helper — animates bar to a target % over `ms` milliseconds
    let currentPct = 0;
    let animId = null;

    function animateTo(targetPct, ms, label) {
      if (label && uploadText) uploadText.textContent = label;
      
      const start     = currentPct;
      const diff      = targetPct - start;
      const startTime = performance.now();

      // Cancel previous animation if any
      if (animId) cancelAnimationFrame(animId);

      return new Promise(resolve => {
        function step(now) {
          const elapsed  = now - startTime;
          const progress = Math.min(elapsed / ms, 1);
          
          // Ease-in-out cubic
          const eased = progress < 0.5
            ? 4 * progress * progress * progress
            : 1 - Math.pow(-2 * progress + 2, 3) / 2;

          currentPct = start + diff * eased;
          progressBar.style.width = `${currentPct}%`;

          if (progress < 1) {
            animId = requestAnimationFrame(step);
          } else {
            animId = null;
            resolve();
          }
        }
        animId = requestAnimationFrame(step);
      });
    }

    // Phase 1 — Slow ramp-up while uploading (0 → 40% over 1.5s)
    const phase1 = animateTo(40, 1500, 'Uploading...');

    try {
      const uploadPromise = UploadAPI.uploadFileWithProgress(file, chatId, (percent) => {
        // Map real upload progress (0-100) onto the 40-70% range
        const mapped = 40 + (percent / 100) * 30;
        if (mapped > currentPct) {
          // Update immediately for real progress, but stop the Phase 1 loop if it's slow
          currentPct = mapped;
          progressBar.style.width = `${currentPct}%`;
        }
      });

      // Phase 2 — Hold at ~70% while server processes/indexes (slow crawl to 70%)
      const phase2 = animateTo(70, 4000, 'Processing document...');

      const result = await uploadPromise;

      // Phase 3 — Server done: smoothly complete to 100%
      await animateTo(100, 600, 'Done!');
      
      // Keep "Done!" visible for a moment
      await new Promise(r => setTimeout(r, 800));

      // Phase 4 — Fade out the bar gracefully
      progressBar.style.transition = 'opacity 0.4s ease';
      progressBar.style.opacity    = '0';
      await new Promise(r => setTimeout(r, 400));

      activeFileId = result.id;
      localStorage.setItem('CortexChat_active_file_id', result.id);
      localStorage.setItem('CortexChat_active_file_name', result.original_name);

      activeDocName.textContent = result.original_name;
      activeDocBadge.style.display = 'flex';
      dropZone.classList.remove('visible');

      showToast(`${result.original_name} uploaded successfully`, 'success');
      onUpload(result);
      await loadFilesForChat(chatId);
    } catch (err) {
      showToast(`Upload failed: ${err.message}`, 'error');
      await loadFilesForChat(chatId);
    }
  }



  // ─── Load files for a specific chat ──────────────────────────────────────

  async function loadFilesForChat(chatId) {
    currentLoadChatId = chatId;
    
    // 1. Render from cache immediately for zero-lag feel
    if (docCache[chatId]) {
      const cached = docCache[chatId];
      if (cached.length === 0) {
        filesPanel.innerHTML = '<div class="doc-empty">No documents in this chat yet.</div>';
      } else {
        renderDocCards(cached, chatId);
      }
    } else {
      // Clear panel immediately if no cache to prevent "ghost documents" from previous chat
      filesPanel.innerHTML = '<div class="doc-empty">Loading documents...</div>';
    }

    try {
      const allFiles = await UploadAPI.listFiles();
      // Ensure we only render if this is still the active chat
      if (currentLoadChatId !== chatId) return;

      const files = chatId ? allFiles.filter(f => f.chat_id === chatId) : [];

      // 2. Only re-render if data has changed to prevent flicker
      if (JSON.stringify(docCache[chatId]) !== JSON.stringify(files)) {
        docCache[chatId] = files;
        if (!files.length) {
          filesPanel.innerHTML = '<div class="doc-empty">No documents in this chat yet.</div>';
          return;
        }
        renderDocCards(files, chatId);
      }
    } catch (_) { /* silently ignore */ }
  }

  // ─── Render document cards ────────────────────────────────────────────────
  function renderDocCards(files, chatId) {
    filesPanel.innerHTML = `<div class="doc-cards-grid">${files.map(f => `
      <div class="doc-card ${f.id == activeFileId ? 'selected' : ''}"
           data-id="${f.id}" data-name="${escHtml(f.original_name)}" data-chat="${chatId || ''}">
        <button class="doc-card-delete" data-id="${f.id}" data-name="${escHtml(f.original_name)}" title="Delete document">
          <svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
        <div class="doc-card-icon">${fileIconSVG(f.file_type)}</div>
        <div class="doc-card-name" title="${escHtml(f.original_name)}">${escHtml(f.original_name)}</div>
        <div class="doc-card-type">.${f.file_type.toUpperCase()}</div>
      </div>
    `).join('')}</div>`;

    // Sync active document name if one is selected
    if (activeFileId) {
      const activeFile = files.find(f => String(f.id) === String(activeFileId));
      if (activeFile) {
        activeDocName.textContent = activeFile.original_name;
        activeDocBadge.style.display = 'flex';
      }
    }

    // Select card
    filesPanel.querySelectorAll('.doc-card').forEach(card => {
      card.addEventListener('click', (e) => {
        if (e.target.closest('.doc-card-delete')) return;
        const id   = parseInt(card.dataset.id, 10);
        const name = card.dataset.name;

        const cards = filesPanel.querySelectorAll('.doc-card');
        const chatId = getActiveChatId();
        
        if (activeFileId == id) {
          // Deselect
          activeFileId = null;
          activeDocBadge.style.display = 'none';
          if (chatId) localStorage.removeItem(`activeFile_${chatId}`);
          cards.forEach(c => c.classList.remove('selected'));
        } else {
          activeFileId = id;
          activeDocName.textContent = name;
          activeDocBadge.style.display = 'flex';
          if (chatId) {
            localStorage.setItem(`activeFile_${chatId}`, JSON.stringify({ id, name }));
          }
          cards.forEach(c => c.classList.remove('selected'));
          card.classList.add('selected');
        }
      });
    });

    // Delete button
    filesPanel.querySelectorAll('.doc-card-delete').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        openDeleteModal(parseInt(btn.dataset.id, 10), btn.dataset.name, chatId);
      });
    });
  }

  function deselect() {
    activeFileId = null;
    activeDocBadge.style.display = 'none';
    filesPanel.querySelectorAll('.doc-card').forEach(c => c.classList.remove('selected'));
  }

  function clear() {
    deselect();
    filesPanel.innerHTML = '<div class="doc-empty">Select a chat to see its documents.</div>';
  }

  function setSelectedFileId(id, name = null) {
    activeFileId = id;
    if (id) {
      activeDocBadge.style.display = 'flex';
      if (name) activeDocName.textContent = name;
      
      // Find card and select it if it exists in DOM, and update name if found (more accurate)
      filesPanel.querySelectorAll('.doc-card').forEach(c => {
        const isTarget = String(c.dataset.id) === String(id);
        c.classList.toggle('selected', isTarget);
        if (isTarget) {
          activeDocName.textContent = c.dataset.name || 'Document';
        }
      });
    } else {
      activeDocBadge.style.display = 'none';
    }
  }

  return {
    getActiveFileId: () => activeFileId,
    deselect,
    clear,
    loadFilesForChat,
    setSelectedFileId
  };
}

// ─── Helpers ──────────────────────────────────────────────────────────────

function truncateName(name) {
  if (name.length <= 14) return name;
  const ext = name.lastIndexOf('.');
  if (ext > 0) {
    const base = name.slice(0, ext);
    const extension = name.slice(ext);
    return base.slice(0, 10) + '…' + extension;
  }
  return name.slice(0, 13) + '…';
}

function fileIconSVG(ext) {
  const isImg = ['png', 'jpg', 'jpeg', 'webp', 'gif'].includes(ext.toLowerCase());
  const color = isImg ? '#34d399' : (ext === 'pdf' ? '#f87171' : '#60a5fa');

  if (isImg) {
    return `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="${color}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>`;
  }

  return `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none"
    stroke="${color}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
    <polyline points="14 2 14 8 20 8"/>
  </svg>`;
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
