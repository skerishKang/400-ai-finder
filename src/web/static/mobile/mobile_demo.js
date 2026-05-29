// ===== State =====
let conversations = [];
let currentConvId = null;
let messageCount = 0;
let sidebarOpen = window.innerWidth > 768;

// ===== DOM refs =====
const messagesEl = document.getElementById('messages');
const messagesInner = messagesEl.querySelector('.messages-inner');
const inputEl = document.getElementById('input');
const sendBtn = document.getElementById('sendBtn');
const welcomeEl = document.getElementById('welcome');
const convListEl = document.getElementById('convList');
const sidebarEl = document.getElementById('sidebar');
const overlayEl = document.getElementById('sidebarOverlay');
const themeToggle = document.getElementById('themeToggle');

// ===== Auto-resize textarea =====
inputEl.addEventListener('input', () => {
  inputEl.style.height = 'auto';
  inputEl.style.height = Math.min(inputEl.scrollHeight, 200) + 'px';
});

inputEl.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
    e.preventDefault();
    send();
  }
});

// ===== Theme =====
function setTheme(theme){
  document.documentElement.setAttribute('data-theme', theme);
  themeToggle.textContent = theme === 'dark' ? '☀️' : '🌙';
  localStorage.setItem('theme', theme);
}

function toggleTheme(){
  const current = document.documentElement.getAttribute('data-theme');
  setTheme(current === 'dark' ? 'light' : 'dark');
}

// Init theme: saved > system > light
const savedTheme = localStorage.getItem('theme');
if (savedTheme) {
  setTheme(savedTheme);
} else {
  setTheme('light');
}

// ===== Sidebar =====
function toggleSidebar(){
  if (window.innerWidth <= 768) {
    // Mobile: overlay mode
    sidebarEl.classList.toggle('open');
    overlayEl.classList.toggle('show');
  } else {
    // Desktop: collapse/expand
    sidebarEl.classList.toggle('closed');
    sidebarOpen = !sidebarEl.classList.contains('closed');
  }
}

function closeSidebar(){
  if (window.innerWidth <= 768) {
    sidebarEl.classList.remove('open');
    overlayEl.classList.remove('show');
  }
}

overlayEl.addEventListener('click', closeSidebar);

// Responsive sidebar
window.addEventListener('resize', () => {
  if (window.innerWidth <= 768) {
    // Mobile: sidebar hidden by default
    sidebarEl.classList.remove('closed');
  } else {
    // Desktop: respect sidebarOpen state
    if (!sidebarOpen) {
      sidebarEl.classList.add('closed');
    } else {
      sidebarEl.classList.remove('closed');
    }
  }
});

// ===== Conversation management =====
function generateId(){
  return 'conv_' + Date.now() + '_' + Math.random().toString(36).slice(2,6);
}

function newChat(){
  const id = generateId();
  conversations.unshift({ id, name: '새 대화', messages: [] });
  currentConvId = id;
  renderConversations();
  clearMessages();
  showWelcome();
  closeSidebar();
  inputEl.focus();
}

function deleteConv(id, e){
  e.stopPropagation();
  conversations = conversations.filter(c => c.id !== id);
  if (currentConvId === id) {
    if (conversations.length > 0) {
      switchConv(conversations[0].id);
    } else {
      currentConvId = null;
      clearMessages();
      showWelcome();
    }
  }
  renderConversations();
}

function switchConv(id){
  const conv = conversations.find(c => c.id === id);
  if (!conv) return;
  currentConvId = id;
  renderConversations();
  renderMessages(conv.messages);
  closeSidebar();
}

function getCurrentConv(){
  if (!currentConvId) {
    newChat();
  }
  return conversations.find(c => c.id === currentConvId);
}

function renderConversations(){
  if (!convListEl) return;
  convListEl.innerHTML = conversations.map(c => `
    <div class="conv-item ${c.id === currentConvId ? 'active' : ''}"
         onclick="switchConv('${c.id}')">
      <span class="conv-icon">💬</span>
      <span class="conv-name">${esc(c.name)}</span>
      <button class="conv-del" onclick="deleteConv('${c.id}', event)" title="삭제">✕</button>
    </div>
  `).join('') || '<div style="padding:16px 14px;font-size:13px;color:var(--text-tertiary);text-align:center">아직 대화가 없습니다</div>';
}

// ===== Messages =====
function showWelcome(){
  if (welcomeEl) welcomeEl.style.display = 'flex';
}

function hideWelcome(){
  if (welcomeEl) welcomeEl.style.display = 'none';
}

function clearMessages(){
  const existing = messagesInner.querySelectorAll('.msg-row, .typing-row, .welcome');
  existing.forEach(el => el.remove());
}

function renderMessages(msgs){
  clearMessages();
  if (msgs.length === 0) {
    showWelcome();
    return;
  }
  hideWelcome();
  msgs.forEach(m => {
    addMessageToDOM(m.role, m.html, m.sources, false);
  });
  scrollToBottom();
}

function addMessageToDOM(role, html, sources, animate = true){
  hideWelcome();
  const row = document.createElement('div');
  row.className = 'msg-row ' + role;
  if (animate) row.style.animation = 'msgIn .3s ease';

  const inner = document.createElement('div');
  inner.className = 'msg-inner';

  const avatar = document.createElement('div');
  avatar.className = 'msg-avatar';
  avatar.textContent = role === 'user' ? 'U' : 'AI';

  const content = document.createElement('div');
  content.className = 'msg-content';
  content.innerHTML = html;

  inner.appendChild(avatar);
  inner.appendChild(content);

  if (role === 'assistant' && sources && sources.length > 0) {
    const wrap = document.createElement('div');
    wrap.className = 'sources-wrap';
    sources.forEach(s => {
      const a = document.createElement('a');
      a.className = 'source-link';
      a.href = s.url || '#';
      a.target = '_blank';
      a.rel = 'noopener';
      a.innerHTML =
        '<span class="src-icon">🔗</span>' +
        '<div class="src-info">' +
          '<div class="src-title">' + esc(s.title || '바로가기') + '</div>' +
          '<div class="src-url">' + esc(s.url || '') + '</div>' +
        '</div>' +
        '<span class="src-arrow">→</span>';
      wrap.appendChild(a);
    });
    content.appendChild(wrap);
  }

  row.appendChild(inner);
  messagesInner.appendChild(row);
  scrollToBottom();
  return row;
}

function showTyping(){
  hideWelcome();
  const existing = messagesInner.querySelector('.typing-row');
  if (existing) return existing;

  const row = document.createElement('div');
  row.className = 'typing-row';
  row.innerHTML = `
    <div class="msg-inner">
      <div class="msg-avatar" style="background:var(--text-secondary);color:#fff">AI</div>
      <div class="typing-dots">
        <span class="dot"></span>
        <span class="dot"></span>
        <span class="dot"></span>
      </div>
    </div>
  `;
  messagesInner.appendChild(row);
  scrollToBottom();
  return row;
}

function hideTyping(){
  const el = messagesInner.querySelector('.typing-row');
  if (el) el.remove();
}

function scrollToBottom(){
  requestAnimationFrame(() => {
    messagesEl.scrollTop = messagesEl.scrollHeight;
  });
}

// ===== API =====
async function send(){
  const text = inputEl.value.trim();
  if (!text) return;

  inputEl.value = '';
  inputEl.style.height = 'auto';
  sendBtn.disabled = true;

  const conv = getCurrentConv();
  if (!conv) return;

  if (conv.messages.length === 0) {
    conv.name = text.length > 24 ? text.slice(0, 24) + '…' : text;
    renderConversations();
  }

  const userHtml = esc(text).replace(/\n/g, '<br>');
  conv.messages.push({ role: 'user', html: userHtml, sources: [] });
  addMessageToDOM('user', userHtml, []);

  showTyping();

  try {
    const res = await fetch(API_ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: text, site_name: SITE_NAME })
    });

    hideTyping();

    if (!res.ok) throw new Error('서버 오류 (' + res.status + ')');

    const data = await res.json();
    const answerHtml = renderMarkdown(esc(data.answer || ''));
    const sources = data.sources || [];

    conv.messages.push({ role: 'assistant', html: answerHtml, sources });
    addMessageToDOM('assistant', answerHtml, sources);

    messageCount++;
  } catch (err) {
    hideTyping();
    const errHtml = '<p style="color:#ef4444">⚠️ ' + esc(err.message) + '</p>' +
      '<p style="font-size:13px;color:var(--text-tertiary);margin-top:8px">잠시 후 다시 시도해 주세요.</p>';
    conv.messages.push({ role: 'assistant', html: errHtml, sources: [] });
    addMessageToDOM('assistant', errHtml, []);

    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = '오류가 발생했습니다: ' + err.message;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
  } finally {
    sendBtn.disabled = false;
    inputEl.focus();
  }
}

function quickAsk(q){
  inputEl.value = q;
  send();
}

// ===== Utilities =====
function esc(s){
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

function renderMarkdown(md){
  let html = md
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    .replace(/((?:<li>.*<\/li>\n?)+)/g, '<ul>$1</ul>')
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br>');

  if (!html.startsWith('<')) {
    html = '<p>' + html + '</p>';
  }

  return html;
}

// ===== Init =====
newChat();
inputEl.focus();
