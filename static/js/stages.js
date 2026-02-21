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
    <div class="stage-body"></div>`;
  document.getElementById('stages').appendChild(card);
  state.currentCard = card;
  state.currentToolList = null;
  state.toolCount = 0;
  updateStepper(stage, false);
}

export function addTool(name, input) {
  if (!state.currentCard) return;
  state.toolCount++;

  // If no tool list exists yet (tools arriving before any thinking), create one
  if (!state.currentToolList) {
    const body = state.currentCard.querySelector('.stage-body');
    const list = document.createElement('ul');
    list.className = 'tool-list';
    body.appendChild(list);
    state.currentToolList = list;
  }

  const li = document.createElement('li');
  const desc = formatToolDescription(name, input);
  li.textContent = desc;
  li.title = desc;
  state.currentToolList.appendChild(li);
  state.currentToolList.scrollTop = state.currentToolList.scrollHeight;
  let badge = state.currentCard.querySelector('.badge-tools');
  if (!badge) {
    const meta = state.currentCard.querySelector('.stage-meta');
    badge = document.createElement('span');
    badge.className = 'stage-badge badge-tools';
    meta.insertBefore(badge, meta.firstChild);
  }
  badge.textContent = state.toolCount + ' tool' + (state.toolCount > 1 ? 's' : '');
}

export function addThinking(text) {
  if (!state.currentCard) return;

  const body = state.currentCard.querySelector('.stage-body');
  body.classList.add('open');

  const el = document.createElement('div');
  el.className = 'think-block';
  el.innerHTML = `
    <div class="think-header"><span class="think-dot"></span>reasoning</div>
    <div class="think-body"></div>`;
  body.appendChild(el);

  // Each thinking block owns the tool list that follows it
  const list = document.createElement('ul');
  list.className = 'tool-list';
  body.appendChild(list);
  state.currentToolList = list;

  const textEl = el.querySelector('.think-body');
  const dot = el.querySelector('.think-dot');

  // Blinking cursor node
  const cursor = document.createElement('span');
  cursor.className = 'think-cursor';
  cursor.textContent = '▋';
  const textNode = document.createTextNode('');
  textEl.appendChild(textNode);
  textEl.appendChild(cursor);

  // Target ~2s total regardless of text length; minimum 1ms/char
  const charsPerFrame = Math.max(1, Math.ceil(text.length / (2000 / 16)));
  let typed = 0;

  function frame() {
    const end = Math.min(typed + charsPerFrame, text.length);
    textNode.textContent = text.slice(0, end);
    typed = end;
    textEl.scrollTop = textEl.scrollHeight;
    if (typed < text.length) {
      requestAnimationFrame(frame);
    } else {
      cursor.remove();
      dot.classList.add('done');
    }
  }
  requestAnimationFrame(frame);
}

export function addStageText(text) {
  if (!state.currentCard) return;
  const body = state.currentCard.querySelector('.stage-body');
  body.classList.add('open');
  const el = document.createElement('div');
  el.className = 'stage-text';
  el.textContent = text;
  body.appendChild(el);
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
