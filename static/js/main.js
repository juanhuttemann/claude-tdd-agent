// Entry point: init, startRun, stopPipeline, window.* bridges
import { state } from './state.js';
import { fetchConfig, fetchStatus, postRun, postStop } from './api.js';
import { connectSSE, startTimer } from './sse.js';
import { addError } from './notifications.js';
import { checkForSummary } from './resume.js';
import { openDirBrowser, closeDirBrowser, filterDirectories, setQuickPath } from './dirBrowser.js';

async function stopPipeline() {
  const btn = document.getElementById('stop-btn');
  btn.disabled = true;
  btn.textContent = 'Stopping...';

  try {
    await postStop();
  } catch (err) {
    btn.disabled = false;
    btn.textContent = 'Stop';
  }
}

async function startRun() {
  const ticket = document.getElementById('ticket').value.trim();
  const target = document.getElementById('target').value.trim();
  if (!ticket) return;

  const resumeCheck = document.getElementById('resume-check');
  const resume = resumeCheck ? resumeCheck.checked : false;

  document.getElementById('stages').innerHTML = '';
  document.querySelectorAll('.step').forEach(s => s.className = 'step');
  state.currentCard = null;

  const res = await postRun(ticket, target, resume);

  if (!res.ok) {
    const err = await res.json();
    addError(err.error || 'Failed to start');
    return;
  }

  startTimer(Date.now());
  await new Promise(r => setTimeout(r, 200));
  connectSSE();
}

// Init on page load
async function init() {
  const config = await fetchConfig();
  const targetInput = document.getElementById('target');
  targetInput.value = config.default_target;
  targetInput.placeholder = 'Enter target path';
  targetInput.disabled = false;

  const quickSelectEl = document.getElementById('quick-select');
  if (config.common_dirs && config.common_dirs.length > 0) {
    config.common_dirs.forEach(dir => {
      const btn = document.createElement('button');
      btn.className = 'secondary';
      btn.textContent = dir.name;
      btn.onclick = () => setQuickPath(dir.path);
      quickSelectEl.appendChild(btn);
    });
  }

  await checkForSummary();

  targetInput.addEventListener('change', () => checkForSummary());

  const s = await fetchStatus();
  if (s.status === 'running' || s.status === 'done') {
    if (s.started_at) startTimer(s.started_at);
    connectSSE();
  }
}

init();

// Bridge functions to window for inline onclick attributes in HTML
window.startRun = startRun;
window.stopPipeline = stopPipeline;
window.openDirBrowser = openDirBrowser;
window.closeDirBrowser = closeDirBrowser;
window.filterDirectories = filterDirectories;
