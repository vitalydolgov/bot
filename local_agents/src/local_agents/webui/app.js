const log = document.getElementById('log');
const meta = document.getElementById('meta');
const input = document.getElementById('input');
const form = document.getElementById('composer');
const newSession = document.getElementById('new-session');
const stop = document.getElementById('stop');
let after = 0;
let assistantBubble = null;
let assistantRaw = '';

if (window.DOMPurify) {
  DOMPurify.addHook('afterSanitizeAttributes', (node) => {
    if (node.tagName === 'A') {
      node.setAttribute('target', '_blank');
      node.setAttribute('rel', 'noopener noreferrer');
    }
  });
}

function renderMarkdown(src) {
  if (window.marked && window.DOMPurify) {
    return DOMPurify.sanitize(marked.parse(src), { FORBID_ATTR: ['style'] });
  }
  const div = document.createElement('div');
  div.textContent = src;
  return div.innerHTML;
}

function setBusy(busy) {
  stop.hidden = !busy;
}

function nearBottom() {
  return log.scrollHeight - log.scrollTop - log.clientHeight < 50;
}

function add(cls, text) {
  const stick = nearBottom();
  const div = document.createElement('div');
  div.className = cls;
  div.textContent = text;
  log.appendChild(div);
  if (stick) log.scrollTop = log.scrollHeight;
  return div;
}

function handleEvent(ev) {
  const p = ev.payload;
  switch (ev.kind) {
    case 'reply': {
      const stick = nearBottom();
      if (!assistantBubble) {
        assistantBubble = add('msg assistant markdown-body', '');
        assistantRaw = '';
      }
      assistantRaw += p;
      assistantBubble.innerHTML = renderMarkdown(assistantRaw);
      if (stick) log.scrollTop = log.scrollHeight;
      break;
    }
    case 'reply_done':
      assistantBubble = null;
      assistantRaw = '';
      break;
    case 'tool_call': {
      const d = JSON.parse(p);
      add('event', '-> ' + d.name);
      break;
    }
    case 'tool_result': {
      const d = JSON.parse(p);
      if (d.error) add('event error', '<- ' + d.name + ' failed: ' + d.error);
      break;
    }
    case 'notice':
      add('event', '! ' + p);
      break;
    case 'approval_denied':
      add('event', '! approval denied for ' + p);
      break;
    case 'turn_failed':
      add('event error', 'The turn failed: ' + p);
      setBusy(false);
      break;
    case 'turn_cancelled':
      add('event', p ? 'Interrupted: ' + p : 'Interrupted.');
      setBusy(false);
      break;
    case 'error':
      add('event error', 'Error: ' + p);
      setBusy(false);
      break;
    case 'session_ready':
      meta.textContent = meta.dataset.base + ' · ready';
      break;
    case 'turn_done':
      setBusy(false);
      input.focus();
      break;
  }
}

async function poll() {
  try {
    const res = await fetch('/api/events?after=' + after);
    const data = await res.json();
    if (data.busy) setBusy(true);
    for (const ev of data.events) {
      after = ev.id;
      handleEvent(ev);
    }
  } catch (e) {
    meta.textContent = 'connection lost';
  }
  setTimeout(poll, 500);
}

async function refreshSession() {
  const res = await fetch('/api/session');
  const data = await res.json();
  meta.dataset.base = data.agent + ' · session ' + (data.sdk_id || data.session_id);
  meta.textContent = meta.dataset.base;
}

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  add('msg user', text);
  input.value = '';
  setBusy(true);
  await fetch('/api/message', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({text}),
  });
});

stop.addEventListener('click', async () => {
  await fetch('/api/cancel', {method: 'POST'});
});

newSession.addEventListener('click', async () => {
  await fetch('/api/new', {method: 'POST'});
  log.innerHTML = '';
  after = 0;
  assistantBubble = null;
  assistantRaw = '';
  setBusy(false);
  await refreshSession();
});

refreshSession().then(poll);
