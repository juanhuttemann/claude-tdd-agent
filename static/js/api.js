// All fetch() calls to /api/* endpoints

export async function fetchConfig() {
  const res = await fetch('/api/config');
  return res.json();
}

export async function fetchStatus() {
  const res = await fetch('/api/status');
  return res.json();
}

export async function postRun(ticket, target, resume) {
  return fetch('/api/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ticket, target, resume }),
  });
}

export async function postStop() {
  return fetch('/api/stop', { method: 'POST' });
}

export async function postSummary(target) {
  return fetch('/api/summary', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ target }),
  });
}

export async function postListDirs(path) {
  return fetch('/api/list_dirs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path }),
  });
}

export async function postOptimize(ticket, target) {
  return fetch('/api/optimize', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ticket, target }),
  });
}

export async function postOptimizeSubmit(ticket, target, context, answers) {
  return fetch('/api/optimize/submit', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ticket, target, context, answers }),
  });
}
