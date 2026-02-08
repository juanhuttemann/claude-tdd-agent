// SSE connection + event wiring
import { state } from './state.js';
import { createStageCard, addTool, setResult, finalizeCurrent } from './stages.js';
import { addLog, addError, showReport, showStopped, showSummary } from './notifications.js';
import { checkForSummary } from './resume.js';

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

  state.evtSource.addEventListener('init', () => {});

  state.evtSource.addEventListener('banner', e => {
    const d = JSON.parse(e.data);
    createStageCard(d.stage, d.description);
  });

  state.evtSource.addEventListener('tool', e => {
    const d = JSON.parse(e.data);
    addTool(d.tool, d.input);
  });

  state.evtSource.addEventListener('result', e => {
    const d = JSON.parse(e.data);
    setResult(d.turns, d.cost, d.duration);
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
    document.getElementById('indicator').className = 'dot done';
    document.getElementById('form-card').classList.remove('hidden');
    document.getElementById('stop-btn').style.display = 'none';
    btn.disabled = false;
    state.evtSource.close();
    state.evtSource = null;
    checkForSummary();
  });
}
