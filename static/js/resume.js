// Resume banner + checkForSummary
import { postSummary } from './api.js';
import { state } from './state.js';

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

export async function checkForSummary(prefetched) {
  const target = document.getElementById('target').value.trim();
  if (!target) return;

  const section = document.getElementById('resume-section');
  try {
    if (prefetched !== undefined) {
      if (!prefetched) {
        section.innerHTML = '';
        state.cachedSummary = null;
        return;
      }
      state.cachedSummary = prefetched;
    } else {
      const res = await postSummary(target);

      if (!res.ok) {
        section.innerHTML = '';
        state.cachedSummary = null;
        return;
      }

      state.cachedSummary = await res.json();
    }
    const stages = state.cachedSummary.completed_stages || [];
    const interrupted = state.cachedSummary.interrupted_stage || '?';
    const ts = state.cachedSummary.test_status || {};
    const testInfo = ts.passing ? 'passing' : `${ts.failures} failures`;
    const timestamp = state.cachedSummary.timestamp || '';

    section.innerHTML = `
      <div class="resume-banner">
        <div class="resume-header">
          <span class="resume-label">Previous run available</span>
          <div class="resume-toggle">
            <input type="checkbox" id="resume-check">
            <label for="resume-check">Resume from here</label>
          </div>
        </div>
        <div style="font-size:12px;color:#8b949e;margin-top:6px;">
          Completed: ${stages.join(', ') || 'none'} | Stopped at: ${interrupted} | Tests: ${testInfo}
          ${timestamp ? ' | ' + timestamp : ''}
        </div>
        <div style="margin-top:8px;">
          <button class="resume-preview-toggle" id="resume-preview-toggle-btn">Show summary</button>
        </div>
        <div class="resume-preview" id="resume-preview">
          <div class="resume-preview-body">${escapeHtml(state.cachedSummary.summary || 'No summary text')}</div>
        </div>
      </div>`;

    // Attach toggle via addEventListener instead of inline onclick
    const toggleBtn = document.getElementById('resume-preview-toggle-btn');
    if (toggleBtn) {
      toggleBtn.addEventListener('click', toggleResumePreview);
    }

    // Fill ticket from summary when checked; restore previous value when unchecked
    const resumeCheck = document.getElementById('resume-check');
    if (resumeCheck && state.cachedSummary.ticket) {
      let savedTicket = '';
      resumeCheck.addEventListener('change', () => {
        const ticketEl = document.getElementById('ticket');
        if (!ticketEl) return;
        if (resumeCheck.checked) {
          savedTicket = ticketEl.value;
          ticketEl.value = state.cachedSummary.ticket;
        } else {
          ticketEl.value = savedTicket;
        }
      });
    }
  } catch (err) {
    section.innerHTML = '';
    state.cachedSummary = null;
  }
}

function toggleResumePreview() {
  const preview = document.getElementById('resume-preview');
  if (!preview) return;
  preview.classList.toggle('open');
  const btn = document.getElementById('resume-preview-toggle-btn');
  if (btn) {
    btn.textContent = preview.classList.contains('open') ? 'Hide summary' : 'Show summary';
  }
}
