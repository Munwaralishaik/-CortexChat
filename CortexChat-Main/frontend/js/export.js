/**
 * frontend/js/export.js — PDF Generation & Download Handler
 *
 * Coordinates with the backend PDF generation endpoint (`/export/pdf`).
 * Handles the binary Blob response, constructs a temporary ObjectURL, 
 * and programmatically triggers a browser file download for the user.
 */

import { ExportAPI } from './api.js';

/**
 * Export the given chat as a PDF and trigger a file download.
 *
 * @param {number|null} chatId
 * @param {Function} showToast - showToast(message, type) function
 */
export async function exportChatPDF(chatId, showToast, messages = null, filename = null) {
  if (!chatId) {
    showToast('No active chat to export', 'warning');
    return;
  }

  showToast('Generating PDF…', 'info');

  try {
    const blob = await ExportAPI.exportPDF(chatId, messages, filename);

    // Trigger download
    const url  = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href     = url;
    
    // Ensure filename has .pdf extension
    let finalName = filename || `CortexChat_${chatId}`;
    if (!finalName.toLowerCase().endsWith('.pdf')) finalName += '.pdf';
    
    link.download = finalName;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);

    showToast('PDF downloaded!', 'success');
  } catch (err) {
    showToast(`Export failed: ${err.message}`, 'error');
  }
}
