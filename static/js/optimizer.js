// Plan optimizer: Q&A flow for refining vague tickets
import { postOptimize, postOptimizeSubmit } from './api.js';

let _context = '';
let _questions = [];

function esc(s) {
  const el = document.createElement('span');
  el.textContent = s;
  return el.innerHTML;
}

export async function startOptimize() {
  const ticket = document.getElementById('ticket').value.trim();
  const target = document.getElementById('target').value.trim();
  if (!ticket) return;

  const btn = document.getElementById('optimize-btn');
  const panel = document.getElementById('optimize-panel');

  btn.disabled = true;
  btn.textContent = 'Analyzing...';
  panel.innerHTML = '<div class="opt-loading"><span class="spinner"></span> Scanning codebase...</div>';
  panel.style.display = 'block';

  try {
    const res = await postOptimize(ticket, target);
    const data = await res.json();
    if (!res.ok) {
      panel.innerHTML = `<div class="opt-error">${esc(data.error || 'Failed')}</div>`;
      return;
    }
    _context = data.context || '';
    _questions = data.questions || [];
    renderQuestions(data);
  } catch (err) {
    panel.innerHTML = `<div class="opt-error">${esc(err.message)}</div>`;
  } finally {
    btn.disabled = false;
    btn.textContent = 'Optimize';
  }
}

function renderQuestions(data) {
  const panel = document.getElementById('optimize-panel');
  const qid = id => esc(String(id));

  let h = '';
  if (data.context) h += `<div class="opt-context">${esc(data.context)}</div>`;

  for (const q of data.questions) {
    h += `<div class="opt-q"><div class="opt-q-text">${esc(q.question)}</div><div class="opt-opts">`;
    for (const opt of q.options) {
      h += `<label class="opt-opt"><input type="radio" name="q${qid(q.id)}" value="${esc(opt)}"><span>${esc(opt)}</span></label>`;
    }
    h += `<label class="opt-opt opt-custom"><input type="radio" name="q${qid(q.id)}" value="__custom__"><input type="text" class="opt-custom-input" placeholder="Other..." disabled></label>`;
    h += '</div></div>';
  }

  h += '<div class="opt-actions"><button id="rewrite-btn" onclick="submitOptimize()">Rewrite Ticket</button></div>';
  panel.innerHTML = h;

  // Wire "Other" radios
  panel.querySelectorAll('.opt-custom input[type="radio"]').forEach(radio => {
    const txt = radio.parentElement.querySelector('.opt-custom-input');
    panel.querySelectorAll(`input[name="${radio.name}"]`).forEach(r => {
      r.addEventListener('change', () => {
        txt.disabled = !radio.checked;
        if (radio.checked) txt.focus();
      });
    });
  });
}

export async function submitOptimize() {
  const ticket = document.getElementById('ticket').value.trim();
  const target = document.getElementById('target').value.trim();
  const panel = document.getElementById('optimize-panel');
  const btn = document.getElementById('rewrite-btn');

  const answers = [];
  for (const q of _questions) {
    const sel = panel.querySelector(`input[name="q${q.id}"]:checked`);
    if (!sel) continue;
    let answer = sel.value;
    if (answer === '__custom__') {
      const ci = sel.parentElement.querySelector('.opt-custom-input');
      answer = ci ? ci.value.trim() : '';
    }
    if (answer) answers.push({ question: q.question, answer });
  }

  if (!answers.length) {
    panel.querySelectorAll('.opt-error').forEach(e => e.remove());
    panel.insertAdjacentHTML('beforeend', '<div class="opt-error">Answer at least one question.</div>');
    return;
  }

  btn.disabled = true;
  btn.textContent = 'Rewriting...';

  try {
    const res = await postOptimizeSubmit(ticket, target, _context, answers);
    const data = await res.json();
    if (!res.ok) {
      panel.innerHTML = `<div class="opt-error">${esc(data.error || 'Failed')}</div>`;
      return;
    }
    document.getElementById('ticket').value = data.optimized_ticket;
    panel.innerHTML = '<div class="opt-ok">Ticket rewritten. Review above, then click Run.</div>';
    setTimeout(() => { panel.style.display = 'none'; }, 3000);
  } catch (err) {
    panel.innerHTML = `<div class="opt-error">${esc(err.message)}</div>`;
  }
}
