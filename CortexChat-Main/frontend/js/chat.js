/**
 * frontend/js/chat.js — Chat Interface & Markdown Rendering
 *
 * Dedicated utilities for dynamically building the chat UI:
 *   - Markdown Parsing: Converts AI markdown responses into styled HTML (via marked.js).
 *   - Syntax Highlighting: Applies highlight.js to code blocks.
 *   - Typing Indicators: Renders loading states during AI inference.
 *   - Textarea Auto-resize: Smoothly adjusts the chat input height based on content.
 */

/**
 * Create and append a chat message bubble to the container.
 *
 * @param {HTMLElement} container - The #chatInner element.
 * @param {'user'|'assistant'} role
 * @param {string} content
 * @returns {HTMLElement} The created message element.
 */
export function appendMessage(container, role, content, msgId = null) {
  const wrap   = document.createElement('div');
  wrap.className = `message ${role}`;
  if (msgId) wrap.dataset.messageId = msgId;


  const bubble = document.createElement('div');
  bubble.className = 'msg-bubble';
  
  if (content === '[SYNTHESIZING]') {
    bubble.innerHTML = `
      <div class="synthesizing-loader">
        <div class="loader-ring"></div>
        <div class="loader-text">Analyzing Document...</div>
      </div>
    `;
  } else if (role === 'assistant') {
    // Render markdown for assistant
    bubble.innerHTML = marked.parse(content);
    addCopyButtons(bubble);
  } else {
    bubble.textContent = content;
  }

  wrap.appendChild(bubble);
  container.appendChild(wrap);

  return wrap;
}

function addCopyButtons(element) {
  const codeBlocks = element.querySelectorAll('pre');
  codeBlocks.forEach(block => {
    // Ensure relative positioning for the button
    block.style.position = 'relative';
    
    const button = document.createElement('button');
    button.className = 'copy-code-btn';
    button.innerHTML = `
      <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
      <span>Copy</span>
    `;
    
    button.addEventListener('click', async () => {
      const code = block.querySelector('code').innerText;
      try {
        await navigator.clipboard.writeText(code);
        const span = button.querySelector('span');
        span.textContent = 'Copied!';
        button.classList.add('copied');
        setTimeout(() => {
          span.textContent = 'Copy';
          button.classList.remove('copied');
        }, 2000);
      } catch (err) {
        console.error('Failed to copy:', err);
      }
    });
    
    block.appendChild(button);
  });
}

/**
 * Show the three-dot typing indicator while waiting for the AI.
 *
 * @param {HTMLElement} container
 * @returns {HTMLElement} The typing element (call .remove() when done).
 */
export function showTypingIndicator(container, mode = 'dots') {
  const wrap = document.createElement('div');
  wrap.className = `message assistant typing-indicator ${mode}`;

  const bubble = document.createElement('div');
  bubble.className = 'msg-bubble';

  if (mode === 'document') {
    bubble.innerHTML = `
      <div class="synthesizing-loader">
        <div class="loader-ring"></div>
        <div class="loader-text">Analyzing Document...</div>
      </div>
    `;
  } else {
    for (let i = 0; i < 3; i++) {
      const dot = document.createElement('div');
      dot.className = 'typing-dot';
      bubble.appendChild(dot);
    }
  }

  wrap.appendChild(bubble);
  container.appendChild(wrap);

  return wrap;
}

/**
 * Auto-resize a textarea to fit its content (up to its max-height).
 *
 * @param {HTMLTextAreaElement} textarea
 */
export function autoResize(textarea) {
  textarea.style.height = 'auto';
  textarea.style.height = `${textarea.scrollHeight}px`;
}
