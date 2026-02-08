// Directory browser modal + fuzzy search
import { postListDirs } from './api.js';
import { state } from './state.js';
import { checkForSummary } from './resume.js';

export async function openDirBrowser() {
  document.getElementById('dir-modal').classList.add('open');
  document.getElementById('dir-search').value = '';
  await loadDirectories(document.getElementById('target').value || '/');
  document.getElementById('dir-search').focus();
}

export function closeDirBrowser() {
  document.getElementById('dir-modal').classList.remove('open');
}

// Fuzzy match function - returns score and match indices
function fuzzyMatch(text, query) {
  if (!query) return { score: 1, indices: [] };

  text = text.toLowerCase();
  query = query.toLowerCase();

  let textIdx = 0;
  let queryIdx = 0;
  let score = 0;
  let indices = [];

  while (textIdx < text.length && queryIdx < query.length) {
    if (text[textIdx] === query[queryIdx]) {
      indices.push(textIdx);
      score += textIdx === queryIdx ? 2 : 1;
      queryIdx++;
    }
    textIdx++;
  }

  if (queryIdx < query.length) {
    return null;
  }

  return { score: score / query.length, indices };
}

export function filterDirectories() {
  const query = document.getElementById('dir-search').value.trim();
  const dirList = document.getElementById('dir-list');
  const items = dirList.querySelectorAll('.dir-item');

  items.forEach(item => {
    const name = item.dataset.name;
    if (!query) {
      item.classList.remove('hidden');
      const nameSpan = item.querySelector('.dir-name');
      if (nameSpan) {
        nameSpan.textContent = name;
        nameSpan.classList.remove('match');
      }
      return;
    }

    const result = fuzzyMatch(name, query);
    if (result) {
      item.classList.remove('hidden');
      const nameSpan = item.querySelector('.dir-name');
      if (nameSpan && result.indices.length > 0) {
        let highlighted = '';
        let lastIdx = 0;
        result.indices.forEach(idx => {
          highlighted += name.substring(lastIdx, idx);
          highlighted += '<span class="match">' + name[idx] + '</span>';
          lastIdx = idx + 1;
        });
        highlighted += name.substring(lastIdx);
        nameSpan.innerHTML = highlighted;
      }
    } else {
      item.classList.add('hidden');
    }
  });
}

async function loadDirectories(path) {
  const dirList = document.getElementById('dir-list');
  const currentPathEl = document.getElementById('current-path');

  dirList.innerHTML = '<li class="dir-item">Loading...</li>';
  currentPathEl.textContent = path;
  document.getElementById('dir-search').value = '';

  try {
    const res = await postListDirs(path);

    if (!res.ok) {
      dirList.innerHTML = '<li class="dir-item" style="color: #f85149;">Error loading directories</li>';
      return;
    }

    const data = await res.json();
    state.currentBrowsePath = data.path;
    currentPathEl.textContent = data.path;
    state.currentDirEntries = data.entries;

    dirList.innerHTML = '';
    state.currentDirEntries.forEach(entry => {
      const li = document.createElement('li');
      li.className = 'dir-item' + (entry.name === '..' ? ' parent' : '');
      li.dataset.name = entry.name;
      li.innerHTML = '<span class="dir-name">' + entry.name + '</span>';
      li.onclick = () => {
        if (entry.name === '..') {
          loadDirectories(entry.path);
        } else {
          document.getElementById('target').value = entry.path;
          closeDirBrowser();
        }
      };
      dirList.appendChild(li);
    });
  } catch (err) {
    dirList.innerHTML = '<li class="dir-item" style="color: #f85149;">Error: ' + err.message + '</li>';
  }
}

export function setQuickPath(path) {
  document.getElementById('target').value = path;
  checkForSummary();
}
