// Log, error, report, stopped, and summary card rendering
import { finalizeCurrent } from './stages.js';

export function addLog(message) {
  const el = document.createElement('div');
  el.className = 'log-msg';
  el.textContent = message;
  document.getElementById('stages').appendChild(el);
}

export function addError(message) {
  const el = document.createElement('div');
  el.className = 'error-msg';
  el.textContent = message;
  document.getElementById('stages').appendChild(el);
}

export function showReport(text) {
  finalizeCurrent();
  const el = document.createElement('div');
  el.className = 'report-card';
  el.innerHTML = '<h2>Report</h2><div class="report-body"></div>';
  el.querySelector('.report-body').textContent = text;
  document.getElementById('stages').appendChild(el);
}

export function showStopped(message) {
  finalizeCurrent();
  const el = document.createElement('div');
  el.className = 'stopped-card';
  el.textContent = message;
  document.getElementById('stages').appendChild(el);
}

export function showSummary(summary) {
  finalizeCurrent();
  const el = document.createElement('div');
  el.className = 'summary-card';

  let metaHtml = '';
  if (summary.completed_stages && summary.completed_stages.length > 0) {
    metaHtml += `Completed: ${summary.completed_stages.join(', ')}`;
  }
  if (summary.interrupted_stage) {
    metaHtml += ` | Interrupted during: ${summary.interrupted_stage}`;
  }
  if (summary.test_status) {
    const ts = summary.test_status;
    const status = ts.passing ? 'PASSING' : 'FAILING';
    metaHtml += ` | Tests: ${status} (${ts.total} total, ${ts.failures} failures)`;
  }

  el.innerHTML = `
    <h2>Pipeline Summary</h2>
    ${metaHtml ? '<div class="summary-meta">' + metaHtml + '</div>' : ''}
    <div class="summary-body"></div>`;
  el.querySelector('.summary-body').textContent = summary.summary || JSON.stringify(summary, null, 2);
  document.getElementById('stages').appendChild(el);
}
