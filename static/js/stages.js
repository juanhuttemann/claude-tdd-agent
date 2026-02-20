// Stage card rendering + stepper logic
import { state } from './state.js';

function classifyStage(name) {
  const n = name.toUpperCase();
  if (n.includes('PLAN')) return 'PLAN';
  if (n.includes('SECURITY')) return 'SECURITY';  // before REVIEW: "SECURITY REVIEW" → SECURITY
  if (n.includes('REVIEW')) return 'REVIEW';       // before RED/GREEN: "CODE REVIEW RED/GREEN" → REVIEW
  if (n.includes(' QA')) return 'QA';              // "STAGE 6 - QA" / "QA FIX"
  if (n.includes('RED')) return 'RED';
  if (n.includes('GREEN')) return 'GREEN';
  if (n.includes('REPORT')) return 'REPORT';
  return null;
}

export function updateStepper(stageName, markDone) {
  const key = classifyStage(stageName);
  if (!key) return;
  const steps = document.querySelectorAll('.step');
  let found = false;
  steps.forEach(s => {
    if (s.dataset.step === key) {
      s.className = markDone ? 'step done' : 'step active';
      found = true;
    } else if (!found) {
      s.className = 'step done';
    }
  });
}

export function finalizeCurrent() {
  if (!state.currentCard) return;
  const meta = state.currentCard.querySelector('.stage-meta');
  if (meta.querySelector('.spinner')) {
    meta.innerHTML = '<span class="stage-badge badge-done">done</span>';
  }
}

function formatToolDescription(name, input) {
  if (!input) return name;

  switch (name) {
    case 'Read':
      return `Read: ${input.file_path || '?'}`;
    case 'Write':
      return `Write: ${input.file_path || '?'}`;
    case 'Edit':
      return `Edit: ${input.file_path || '?'}`;
    case 'Bash':
      return `Bash: ${input.command || '?'}`;
    case 'Glob':
      return `Glob: ${input.pattern || '?'}`;
    case 'Grep':
      return `Grep: ${input.pattern || '?'} ${input.path ? '(' + input.path + ')' : ''}`;
    default: {
      const keys = Object.keys(input);
      if (keys.length > 0) {
        const key = keys.find(k => k.includes('path') || k.includes('file') || k.includes('pattern') || k.includes('command')) || keys[0];
        return `${name}: ${input[key]}`;
      }
      return name;
    }
  }
}

export function createStageCard(stage, description) {
  finalizeCurrent();

  const card = document.createElement('div');
  card.className = 'stage-card';
  card.innerHTML = `
    <div class="stage-header">
      <span class="stage-name">${description}</span>
      <span class="stage-meta">
        <span class="stage-badge badge-running"><span class="spinner"></span></span>
      </span>
    </div>
    <div class="stage-body">
      <ul class="tool-list"></ul>
    </div>`;
  document.getElementById('stages').appendChild(card);
  state.currentCard = card;
  state.toolCount = 0;
  updateStepper(stage, false);
}

export function addTool(name, input) {
  if (!state.currentCard) return;
  state.toolCount++;
  const list = state.currentCard.querySelector('.tool-list');
  const li = document.createElement('li');
  const desc = formatToolDescription(name, input);
  li.textContent = desc;
  li.title = desc;
  list.appendChild(li);
  list.scrollTop = list.scrollHeight;
  let badge = state.currentCard.querySelector('.badge-tools');
  if (!badge) {
    const meta = state.currentCard.querySelector('.stage-meta');
    badge = document.createElement('span');
    badge.className = 'stage-badge badge-tools';
    meta.insertBefore(badge, meta.firstChild);
  }
  badge.textContent = state.toolCount + ' tool' + (state.toolCount > 1 ? 's' : '');
}

export function setResult(turns, cost, duration) {
  if (!state.currentCard) return;
  const meta = state.currentCard.querySelector('.stage-meta');
  const secs = (duration / 1000).toFixed(1);
  meta.innerHTML = `
    <span class="stage-badge badge-tools">${state.toolCount} tools</span>
    <span>${turns} turns</span>
    <span>${cost}</span>
    <span>${secs}s</span>`;
  updateStepper(state.currentCard.querySelector('.stage-name').textContent, true);
}

// Event delegation for stage header toggle
document.getElementById('stages').addEventListener('click', e => {
  const header = e.target.closest('.stage-header');
  if (!header) return;
  const body = header.nextElementSibling;
  if (body) body.classList.toggle('open');
});
