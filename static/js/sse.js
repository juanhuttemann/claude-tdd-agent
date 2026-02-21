// SSE connection + event wiring
import { state } from './state.js';
import { createStageCard, addTool, addThinking, addStageText, setResult, finalizeCurrent } from './stages.js';
import { addVerifyResult, addLog, addError, showReport, showStopped, showSummary } from './notifications.js';
import { checkForSummary } from './resume.js';

function formatElapsed(ms) {
  const totalSecs = Math.floor(ms / 1000);
  const mins = Math.floor(totalSecs / 60);
  const secs = totalSecs % 60;
  return mins > 0 ? `${mins}m ${String(secs).padStart(2, '0')}s` : `${secs}s`;
}

function updateTimerDisplay() {
  if (!state.pipelineStartedAt) return;
  const el = document.getElementById('elapsed-timer');
  if (el) el.textContent = formatElapsed(Date.now() - state.pipelineStartedAt);
}

export function startTimer(startedAt) {
  stopTimer();
  state.pipelineStartedAt = startedAt;
  updateTimerDisplay();
  state.timerInterval = setInterval(updateTimerDisplay, 1000);
}

function stopTimer() {
  if (state.timerInterval) {
    clearInterval(state.timerInterval);
    state.timerInterval = null;
  }
  updateTimerDisplay(); // show final value
}

export function connectSSE() {
  const btn = document.getElementById('run');
  btn.disabled = true;
  document.getElementById('form-card').classList.add('hidden');
  document.getElementById('stepper-row').style.display = 'flex';
  document.getElementById('stop-btn').style.display = 'block';
  document.getElementById('stop-btn').disabled = false;
  document.getElementById('stop-btn').textContent = 'Stop';
  document.getElementById('indicator').className = 'dot running';

  state.evtSource = new EventSource('/api/events');

  state.evtSource.addEventListener('banner', e => {
    const d = JSON.parse(e.data);
    createStageCard(d.stage, d.description);
  });

  state.evtSource.addEventListener('thinking', e => {
    const d = JSON.parse(e.data);
    addThinking(d.text);
  });

  state.evtSource.addEventListener('tool', e => {
    const d = JSON.parse(e.data);
    addTool(d.tool, d.input);
  });

  state.evtSource.addEventListener('stage_text', e => {
    const d = JSON.parse(e.data);
    addStageText(d.text);
  });

  state.evtSource.addEventListener('result', e => {
    const d = JSON.parse(e.data);
    setResult(d.turns, d.cost, d.duration);
  });

  state.evtSource.addEventListener('test_verify', e => {
    const d = JSON.parse(e.data);
    addVerifyResult(d);
  });

  state.evtSource.addEventListener('log', e => {
    const d = JSON.parse(e.data);
    addLog(d.message);
  });

  state.evtSource.addEventListener('report', e => {
    const d = JSON.parse(e.data);
    showReport(d.text);
  });

  state.evtSource.addEventListener('stopped', e => {
    const d = JSON.parse(e.data);
    showStopped(d.message || 'Pipeline stopped by user');
    document.getElementById('stop-btn').style.display = 'none';
  });

  state.evtSource.addEventListener('summary', e => {
    const d = JSON.parse(e.data);
    showSummary(d.summary || d);
  });

  state.evtSource.addEventListener('error', e => {
    try { addError(JSON.parse(e.data).message); } catch (_) {}
  });

  state.evtSource.addEventListener('done', () => {
    finalizeCurrent();
    stopTimer();
    document.getElementById('indicator').className = 'dot done';
    document.getElementById('form-card').classList.remove('hidden');
    document.getElementById('stop-btn').style.display = 'none';
    btn.disabled = false;
    state.evtSource.close();
    state.evtSource = null;
    checkForSummary();
  });
}
