/**
 * frontend/js/sidebar.js — Sidebar Navigation & History Management
 *
 * Controls the left-hand navigation pane of the dashboard. Features:
 *   - Chat History: Fetching, rendering, renaming, and deleting past sessions.
 *   - Document Management: Managing context files tied to specific chats.
 *   - User Profile Actions: Handling the dropdown menu for settings and secure logout.
 *   - Responsive Design: Toggling the mobile sidebar overlay.
 */

import { ChatAPI } from './api.js';

const ICONS = {
  dots: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/></svg>`,
  archive: `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="21 8 21 21 3 21 3 8"/><rect x="1" y="3" width="22" height="5"/><line x1="10" y1="12" x2="14" y2="12"/></svg>`,
  hide: `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>`,
  delete: `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>`,
  rename: `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 1 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>`

};

export function initSidebar({ listEl, searchInput, getActiveChatId, showToast, onChatSelect, onChatDelete, initialData = null }) {
  let allChats = initialData || [];
  let openMenuId = null;
  let pendingAction = null; // { id, title, type }
  let searchQuery = '';

  if (initialData) {
    // Render immediately if we have data from super-endpoint
    render(allChats);
  } else {
    // Fallback: fetch manually if no init data provided
    refresh();
  }

  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      searchQuery = e.target.value.toLowerCase().trim();
      render(allChats);
    });
  }

  // Modal elements
  const actionOverlay = document.getElementById('chatActionOverlay');
  const actionTitle   = document.getElementById('chatActionTitle');
  const actionName    = document.getElementById('chatActionName');
  const actionSub     = document.getElementById('chatActionSub');
  const actionIcon    = document.getElementById('chatActionIconCircle');
  const actionConfirm = document.getElementById('chatActionConfirm');
  const actionCancel  = document.getElementById('chatActionCancel');

  // Filtered modal elements
  const filteredOverlay = document.getElementById('filteredChatsOverlay');
  const filteredTitle   = document.getElementById('filteredChatsTitle');
  const filteredList    = document.getElementById('filteredChatsList');
  const closeFiltered   = document.getElementById('closeFilteredBtn');

  if (closeFiltered) closeFiltered.addEventListener('click', () => filteredOverlay.classList.remove('open'));
  if (filteredOverlay) filteredOverlay.addEventListener('click', (e) => { if(e.target === filteredOverlay) filteredOverlay.classList.remove('open'); });

  // Close menu on outside click
  document.addEventListener('click', () => {
    if (openMenuId) closeMenu();
  });


  async function refresh() {
    try {
      allChats = await ChatAPI.getHistory();
      render(allChats);
    } catch (err) {
      listEl.innerHTML = `<div style="color:var(--text-muted);font-size:13px;padding:8px 12px;">Failed to load chats.</div>`;
    }
  }

  function render(chats) {
    if (!Array.isArray(chats)) return;
    // Main list only shows active (not archived/hidden) chats
    let filteredChats = chats.filter(c => !c.is_archived && !c.is_hidden);

    if (searchQuery) {
      filteredChats = filteredChats.filter(c => 
        c.title.toLowerCase().includes(searchQuery)
      );
    }

    if (!filteredChats.length) {
      listEl.innerHTML = `<div style="color:var(--text-muted);font-size:13px;padding:8px 12px;">${searchQuery ? 'No matches found' : 'No active chats. Start a new one!'}</div>`;
    } else {
      listEl.innerHTML = filteredChats.map(c => renderChatItem(c)).join('');
      attachListeners(listEl);
    }
  }

  function renderChatItem(c) {
    return `
      <div class="chat-item ${c.id === getActiveChatId() ? 'active' : ''}"
           id="chat-item-${c.id}" data-id="${c.id}" data-title="${escHtml(c.title)}">
        <span class="chat-item-title" title="${escHtml(c.title)}">${escHtml(c.title)}</span>
        
        <div class="chat-item-actions">
          <button class="chat-item-dots" data-id="${c.id}" title="Options">${ICONS.dots}</button>
        </div>
      </div>
    `;
  }


  function attachListeners(container) {
    // Select chat
    container.querySelectorAll('.chat-item').forEach(el => {
      el.addEventListener('click', (e) => {
        if (e.target.closest('.chat-item-actions')) return;
        const id    = parseInt(el.dataset.id, 10);
        if (id === getActiveChatId()) return; // Don't reload the same chat
        const title = el.dataset.title;
        
        // dashboard.js can return false to prevent switching (e.g. during selection mode)
        const allowed = onChatSelect(id, title);
        if (allowed !== false) {
          setActive(id);
          if (filteredOverlay) filteredOverlay.classList.remove('open');
        }
      });
    });

    // Handle dots click
    container.querySelectorAll('.chat-item-dots').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const id = parseInt(btn.dataset.id, 10);
        const rect = btn.getBoundingClientRect();
        
        const menu = document.getElementById('floatingChatMenu');
        if (!menu) return;

        menu.style.display = 'flex';
        menu.style.top  = `${rect.top}px`;
        menu.style.left = `${rect.right + 12}px`;
        
        openMenuId = id;
        const chat = allChats.find(c => c.id === id);
        if (chat) {
          menu.dataset.id = id;
          menu.dataset.title = chat.title;
        }
      });
    });

  }

  // Handle floating menu item clicks once
  const floatMenu = document.getElementById('floatingChatMenu');
  if (floatMenu) {
    floatMenu.querySelectorAll('.menu-item').forEach(item => {
      item.addEventListener('click', (e) => {
        e.stopPropagation();
        const id    = parseInt(floatMenu.dataset.id, 10);
        const title = floatMenu.dataset.title;
        if (!id) return;

        if (item.id === 'floatingRenameBtn') {
          closeMenu();
          const overlay = document.getElementById('renameChatOverlay');
          const input = document.getElementById('renameChatInput');
          const saveBtn = document.getElementById('renameChatSave');
          const cancelBtn = document.getElementById('renameChatCancel');
          
          if (overlay && input) {
            input.value = title;
            overlay.classList.add('open');
            setTimeout(() => {
              input.focus();
              input.select();
            }, 10);
            
            const closeRename = () => overlay.classList.remove('open');
            
            // Clean up old listeners to avoid multiple fires
            saveBtn.onclick = async () => {
              const newTitle = input.value.trim();
              if (newTitle && newTitle !== title) {
                try {
                  await ChatAPI.updateChat(id, { title: newTitle });
                  showToast('Chat renamed', 'info');
                  await refresh();
                } catch (err) {
                  showToast(`Failed to rename: ${err.message}`, 'error');
                }
              }
              closeRename();
            };
            
            cancelBtn.onclick = closeRename;
            overlay.onclick = (e) => { if(e.target === overlay) closeRename(); };
          }
          return;
        }

        const type = item.id === 'floatingArchiveBtn' ? 'archive' : (item.id === 'floatingHideBtn' ? 'hide' : 'delete');
        openActionModal(id, title, type);
        closeMenu();
      });
    });
  }

  function closeMenu() {
    const menu = document.getElementById('floatingChatMenu');
    if (menu) menu.style.display = 'none';
    openMenuId = null;
  }


  function openActionModal(id, title, type) {
    pendingAction = { id, title, type };
    actionName.textContent = title;
    // Customize modal based on action
    if (type === 'delete') {
      actionTitle.textContent = 'Delete Chat?';
      actionSub.textContent   = 'This conversation and all its documents will be permanently removed.';
      actionIcon.innerHTML    = ICONS.delete;
      actionIcon.style.color  = 'var(--error)';
      actionConfirm.className = 'btn btn-danger';
      actionConfirm.textContent = 'Delete Chat';
    } else if (type === 'archive') {
      actionTitle.textContent = 'Archive Chat?';
      actionSub.textContent   = 'Move this conversation to your archive. You can still access it later.';
      actionIcon.innerHTML    = ICONS.archive;
      actionIcon.style.color  = 'var(--text-primary)';
      actionConfirm.className = 'btn btn-outline-white';
      actionConfirm.textContent = 'Archive Chat';
    } else {
      actionTitle.textContent = 'Hide Chat?';
      actionSub.textContent   = 'Remove this conversation from your list. It won\'t be deleted.';
      actionIcon.innerHTML    = ICONS.hide;
      actionIcon.style.color  = 'var(--text-secondary)';
      actionConfirm.className = 'btn btn-outline-white';
      actionConfirm.textContent = 'Hide Chat';
    }

    actionOverlay.classList.add('open');
  }

  function closeActionModal() {
    actionOverlay.classList.remove('open');
    pendingAction = null;
  }

  if (actionCancel) actionCancel.addEventListener('click', closeActionModal);
  if (actionOverlay) actionOverlay.addEventListener('click', (e) => {
    if (e.target === actionOverlay) closeActionModal();
  });

  if (actionConfirm) {
    actionConfirm.onclick = async () => {
      if (!pendingAction) return;
      const { id, type } = pendingAction;

      // Close modal immediately for better UX
      closeActionModal();

      try {
        if (type === 'delete') {
          // Optimistic UI: Remove from local array and re-render immediately
          allChats = allChats.filter(c => c.id !== id);
          render(allChats);
          onChatDelete(id);
          showToast('Chat deleted', 'info');

          // Bypass backend call if it's a temporary optimistic chat
          if (typeof id === 'string' && id.startsWith('temp_')) {
            return;
          }

          await ChatAPI.deleteChat(id);
          return; 
        } else if (type === 'archive') {
          // Optimistic UI
          const chat = allChats.find(c => c.id === id);
          if (chat) chat.is_archived = true;
          render(allChats);
          
          showToast('Chat archived', 'success');
          await ChatAPI.updateChat(id, { is_archived: true });
        } else if (type === 'hide') {
          // Optimistic UI
          const chat = allChats.find(c => c.id === id);
          if (chat) chat.is_hidden = true;
          render(allChats);
          
          showToast('Chat hidden', 'success');
          await ChatAPI.updateChat(id, { is_hidden: true });
        }
        // Do a background refresh to ensure sync
        refresh();
      } catch (err) {
        showToast(`Failed to ${type} chat.`, 'error');
        // Revert if failed
        refresh();
      }
    };
  }

  function showFiltered(type) {
    const isArchived = type === 'archived';
    filteredTitle.textContent = isArchived ? 'Archived Chats' : 'Hidden Chats';
    const filtered = allChats.filter(c => isArchived ? c.is_archived : c.is_hidden);

    if (!filtered.length) {
      filteredList.innerHTML = `<div style="color:var(--text-muted);font-size:13px;text-align:center;padding:20px;">No ${type} chats found.</div>`;
    } else {
      // Use the same item rendering but maybe add an "Un-archive" button?
      // For now, let's just render them so they can be selected.
      filteredList.innerHTML = filtered.map(c => `
        <div class="chat-item" data-id="${c.id}" data-title="${escHtml(c.title)}" style="border: 1px solid var(--border); background: var(--bg-elevated);">
          <span class="chat-item-title">${escHtml(c.title)}</span>
          <button class="btn btn-ghost restore-btn" data-id="${c.id}" title="Restore" style="padding: 4px;">
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><polyline points="3 3 3 8 8 8"/></svg>
          </button>
        </div>
      `).join('');

      // Add selection listeners
      attachListeners(filteredList);
      
      // Add restore listeners
      filteredList.querySelectorAll('.restore-btn').forEach(btn => {
        btn.onclick = async (e) => {
          e.stopPropagation();
          const id = parseInt(btn.dataset.id, 10);
          
          // Optimistic UI: Close immediately and update local state
          filteredOverlay.classList.remove('open');
          const chat = allChats.find(c => c.id === id);
          if (chat) {
            chat.is_archived = false;
            chat.is_hidden = false;
          }
          render(allChats);
          showToast('Chat restored.', 'success');

          try {
            await ChatAPI.updateChat(id, { is_archived: false, is_hidden: false });
            refresh();
          } catch (err) {
            showToast('Failed to restore chat.', 'error');
            refresh();
          }
        };
      });
    }
    filteredOverlay.classList.add('open');
  }

  function setActive(chatId) {
    document.querySelectorAll('.chat-item').forEach(el => {
      el.classList.toggle('active', String(el.dataset.id) === String(chatId));
    });
  }

  function addChatOptimistically(chat) {
    // Add to the top of the list
    allChats.unshift(chat);
    render(allChats);
  }

  function updateChatTitleOptimistically(chatId, newTitle) {
    const chat = allChats.find(c => c.id === chatId);
    if (chat) {
      chat.title = newTitle;
      render(allChats);
    }
  }

  function finalizeTempChat(tempId, realChat) {
    const idx = allChats.findIndex(c => String(c.id) === String(tempId));
    if (idx !== -1) {
      allChats[idx] = realChat;
      render(allChats);
    }
  }

  return { refresh, setActive, showFiltered, addChatOptimistically, updateChatTitleOptimistically, finalizeTempChat };
}


export function toggleMobileSidebar(sidebarEl) {
  sidebarEl.classList.toggle('open');
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
