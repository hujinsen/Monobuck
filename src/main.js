/* Global UI interactions for Monologue Web */
// 引入全局快捷键协调层（Ctrl+Win / 双击Ctrl / Ctrl+Command / 双击Option 等）
import './hotkeys.js';
import { ws_connect, ws_send_text, ws_send_binary, ws_status, ws_listen } from './websocket.js';

// ========== 调试日志捕获 ==========
const DEBUG_PANEL_MAX_LOGS = 100;
const debugLogs = [];
let debugPanelInitialized = false;

function addDebugLog(source, message, isError = false) {
  const timestamp = new Date().toLocaleTimeString('zh-CN', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
  debugLogs.push({ timestamp, source, message, isError });

  // 限制日志数量
  if (debugLogs.length > DEBUG_PANEL_MAX_LOGS) {
    debugLogs.shift();
  }

  // 如果面板可见，立即更新
  updateDebugPanel();
}

function updateDebugPanel() {
  const debugPanel = document.getElementById('debug-panel');
  const debugLog = document.getElementById('debug-log');
  if (!debugPanel || !debugLog) return;

  debugLog.innerHTML = debugLogs.map(log => {
    const timeClass = `log-time`;
    const sourceClass = `log-source`;
    const errorClass = log.isError ? 'log-error' : '';
    return `<div class="log-entry ${errorClass}">
      <span class="${timeClass}">[${log.timestamp}]</span>
      <span class="${sourceClass}">${log.source}</span>
      <span>${log.message}</span>
    </div>`;
  }).join('');
}

function initDebugPanel() {
  if (debugPanelInitialized) return;
  debugPanelInitialized = true;

  const debugPanel = document.getElementById('debug-panel');
  if (!debugPanel) return;

  const toggleBtn = document.getElementById('debug-toggle');
  const clearBtn = document.getElementById('debug-clear');

  toggleBtn?.addEventListener('click', () => {
    const logDiv = debugPanel.querySelector('.debug-log');
    if (logDiv) {
      if (logDiv.style.display === 'none') {
        logDiv.style.display = 'block';
        toggleBtn.textContent = '隐藏';
      } else {
        logDiv.style.display = 'none';
        toggleBtn.textContent = '显示';
      }
    }
  });

  clearBtn?.addEventListener('click', () => {
    debugLogs.length = 0;
    updateDebugPanel();
  });
}

// 覆盖 console 方法
const originalConsole = {
  log: console.log,
  error: console.error,
  warn: console.warn,
  info: console.info,
};

console.log = (...args) => {
  originalConsole.log(...args);
  addDebugLog('LOG', args.map(arg => typeof arg === 'object' ? JSON.stringify(arg) : String(arg)).join(' '));
};

console.error = (...args) => {
  originalConsole.error(...args);
  addDebugLog('ERROR', args.map(arg => typeof arg === 'object' ? JSON.stringify(arg) : String(arg)).join(' '), true);
};

console.warn = (...args) => {
  originalConsole.warn(...args);
  addDebugLog('WARN', args.map(arg => typeof arg === 'object' ? JSON.stringify(arg) : String(arg)).join(' '));
};

console.info = (...args) => {
  originalConsole.info(...args);
  addDebugLog('INFO', args.map(arg => typeof arg === 'object' ? JSON.stringify(arg) : String(arg)).join(' '));
};
// ========== 调试日志捕获结束 ==========

// 应用启动时，将上一次选择的麦克风偏好同步给 Rust 端，
// 这样即便本次没有打开设置面板，录音也会优先使用该设备。
if (typeof window !== 'undefined' && window.__TAURI__?.core?.invoke) {
  const savedMic = localStorage.getItem('pref.mic');
  if (savedMic && savedMic !== '系统默认') {
    window.__TAURI__.core.invoke('set_mic_preference', { name: savedMic }).catch(() => { /* ignore */ });
  }
}

// WebSocket 与识别面板生命周期整合：仅在 DOM 就绪后建立连接，允许状态显示 Connecting / Connected
let _wsClientId = null;
let _wsInitialized = false;

// 增加重试机制的 WebSocket 连接函数
async function wsConnectWithRetry(updateStatus, retries = 0, maxRetries = 30) {
  try {
    const clientId = await ws_connect();
    console.log('[ws] connected clientId=', clientId);
    updateStatus('Connected', 'connected');
    return clientId;
  } catch (err) {
    console.warn(`[ws] connection attempt ${retries + 1} failed:`, err);

    if (retries >= maxRetries) {
      updateStatus('Connection Failed', 'error');
      console.error('[ws] Max retries reached, server might be down.');
      return null;
    }

    // 等待后重试 (首几次快一点，后面慢一点，比如: 500, 1000, 1500, 2000, 2000...)
    const delay = Math.min(500 * (retries + 1), 2000);
    await new Promise(r => setTimeout(r, delay));
    return wsConnectWithRetry(updateStatus, retries + 1, maxRetries);
  }
}

function initWebSocketBridge(panelRefs) {
  if (_wsInitialized) return; // 防重复
  _wsInitialized = true;
  const { statusEl } = panelRefs || {};
  const updateStatus = (text, st) => {
    if (!statusEl) return;
    statusEl.textContent = text;
    statusEl.dataset.state = st;
  };

  // 连接前标记 Connecting
  updateStatus('Connecting...', 'connecting');

  // 使用重试机制建立连接
  wsConnectWithRetry(updateStatus).then(clientId => {
    if (!clientId) return; // 连接失败

    _wsClientId = clientId;
    // 仅监听生命周期事件；不发送任意文本到 ASR 端
    // 生命期事件监听
    ws_listen('ws-open', payload => {

      console.log('[ws-open]', payload);
      updateStatus('Connected', 'connected');
    });
    ws_listen('ws-inject', payload => {
      console.log('[ws-inject]', payload);
      // 注入完成后若当前已经 final 或 processing，覆盖为 Injected
      if (statusEl) {
        statusEl.textContent = 'Injected';
        statusEl.dataset.state = 'injected';
      }
    });
    ws_listen('ws-end', payload => {
      console.log('[ws-end]', payload);
      // 非活动或已完成后显示 Disconnected
      if (statusEl && statusEl.dataset.state !== 'active') {
        statusEl.textContent = 'Disconnected';
        statusEl.dataset.state = 'disconnected';
      }
    });
    ws_listen('ws-close', payload => {
      console.log('[ws-close]', payload);
      if (statusEl && statusEl.dataset.state !== 'active') {
        statusEl.textContent = 'Disconnected';
        statusEl.dataset.state = 'disconnected';
      }
    });
    ws_listen('ws-error', payload => {
      console.warn('[ws-error]', payload);
      // 若尚未进入识别 final 阶段，视为连接错误
      if (statusEl && !['final', 'injected', 'error'].includes(statusEl.dataset.state)) {
        statusEl.textContent = 'Error';
        statusEl.dataset.state = 'error';
      }
    });
    // 保留普通消息调试
    ws_listen('ws-message', payload => console.log('[ws-message]', payload));
  }).catch(err => {
    console.error('[ws] connect failed', err);
    updateStatus('Error', 'error');
  });
}

// /**
//  * 检查并获取麦克风访问权限
//  * @async
//  * @returns {Promise<MediaStream>} 返回获取到的媒体流
//  * @throws {Error} 当用户已拒绝麦克风权限时抛出错误
//  */
// async function ensureMic() {
//   const st = await navigator.permissions.query({ name: 'microphone' });
//   if (st.state === 'granted') return await navigator.mediaDevices.getUserMedia({ audio: true });
//   if (st.state === 'prompt') {
//     return await navigator.mediaDevices.getUserMedia({ audio: true }); // 会弹框
//   }
//   throw new Error('用户已拒绝麦克风');
// }

// console.log(ensureMic());

// 可按需使用识别钩子：示例（懒得立即渲染 UI 可删除）
import { onRecognitionStart, onRecognitionStop } from './recognition.js';
import { getStats, setAppStatus } from './api.js';

// 简单示例：控制台打印（后续可替换为真正录音逻辑）
onRecognitionStart(e => console.log('[recognition start]', e));
onRecognitionStop(e => console.log('[recognition stop]', e));

// Live recognition panel updates
function initLivePanel() {
  const panel = document.querySelector('#live-recognition');
  if (!panel) return;
  const statusEl = panel.querySelector('.live-rec-status');
  const rawEl = panel.querySelector('.live-rec-line.raw .text');
  const processedEl = panel.querySelector('.live-rec-line.processed .text');
  const durEl = panel.querySelector('.live-rec-meta .dur');

  // 初始化 WebSocket 生命周期桥接（只执行一次）
  initWebSocketBridge({ statusEl });

  onRecognitionStart(ev => {
    if (!statusEl) return;
    statusEl.textContent = 'Listening...';
    statusEl.dataset.state = 'active';
    rawEl.textContent = '';
    processedEl.textContent = '';
    durEl.textContent = '0';
  });
  onRecognitionStop(ev => {
    if (!statusEl) return;
    // 刚结束录音，进入“处理中”阶段（ASR+LLM），最终结果稍后到达
    statusEl.textContent = 'Processing...';
    statusEl.dataset.state = 'processing';
    // 若在阈值内没有拿到 final，显示提示
    if (panel._finalTimer) clearTimeout(panel._finalTimer);
    panel._finalTimer = setTimeout(() => {
      if (statusEl.dataset.state === 'processing') {
        statusEl.textContent = 'Still processing...';
        statusEl.dataset.state = 'processing-wait';
      }
    }, 4000); // 4s 未完成给出反馈
  });
  // Final transcript event
  document.addEventListener('recognition:final', e => {
    // 恢复原生窗口标题
    setAppStatus('idle');

    const { raw, processed, durationMs } = e.detail || {};
    if (rawEl) rawEl.textContent = raw || '';
    if (processedEl) processedEl.textContent = processed || raw || '';
    if (durEl) durEl.textContent = String(durationMs || 0);
    if (statusEl) {
      // 如果稍后会有注入事件，再先标记 Final；注入事件会覆盖为 Injected
      statusEl.textContent = 'Final';
      statusEl.dataset.state = 'final';
      if (panel._finalTimer) { clearTimeout(panel._finalTimer); panel._finalTimer = null; }
    }
  });
  // Error event
  document.addEventListener('recognition:error', e => {
    // 恢复原生窗口标题
    setAppStatus('idle');

    const { message } = e.detail || {};
    if (statusEl) {
      statusEl.textContent = 'Error';
      statusEl.dataset.state = 'error';
    }
    if (processedEl && message) {
      processedEl.textContent = '[ERROR] ' + message;
    }
    if (panel._finalTimer) { clearTimeout(panel._finalTimer); panel._finalTimer = null; }
  });
}

window.addEventListener('DOMContentLoaded', initLivePanel);
/* Assumptions: TAURI context present but we keep code defensive */

window.addEventListener('DOMContentLoaded', () => {
  initNav();
  enhanceButtons();
  initDebugPanel();  // 初始化调试面板
  // 不再预创建设置模态，首次点击时才初始化
  // 监听后端实时统计更新事件
  const tauriEvent = window.__TAURI__?.event;
  if (tauriEvent?.listen) {
    tauriEvent.listen('stats-updated', (event) => {
      console.log('[stats-updated]', event);
      // 收到后端推送时，刷新首页统计和“最近转录”
      refreshHomeStats();
      renderHomeRecentTranscripts();
      // 如果当前正处于“转录”页面，则刷新转录列表
      const activeNav = document.querySelector('.nav-item.active');
      if (activeNav && activeNav.dataset.target === 'transcripts') {
        // 重新从后端读取全部会话并渲染
        (async () => {
          const rawList = await fetchAllTranscripts();
          transcriptsAll = rawList.map((s, idx) => {
            let createdAt;
            try {
              const d = new Date(s.created_at || s.session_id || '');
              createdAt = isNaN(d.getTime()) ? new Date() : d;
            } catch {
              createdAt = new Date();
            }
            const text = (s.refined_text || '').trim() || (s.raw_text || '').trim();
            const words = text ? text.length : 0;
            const durationSec = Math.round((s.duration_ms || 0) / 1000);
            return {
              id: idx + 1,
              text,
              source: 'Local',
              durationSec,
              words,
              createdAt,
              sessionId: s.session_id,
              jsonFilename: s.json_filename,
            };
          });
          transcriptsLoaded = 0;
          renderTranscripts();
          updateInfiniteStatus();
        })();
      }
    });
  }
});




function qs(sel, ctx = document) { return ctx.querySelector(sel); }
function qsa(sel, ctx = document) { return Array.from(ctx.querySelectorAll(sel)); }
// 引入设置模态模块
import { initSettingsModal, openSettingsModal } from './components/settings-modal.js';
import { initStreakBadge, reportActivity } from './components/streak.js';
import { confirmDialog } from './components/ui-dialog.js';
// 已在顶部统一导入 WebSocket 函数

async function loadView(key) {
  const container = qs('#view-container');
  if (!container) return;
  // map key to file name
  const map = {
    dashboard: 'home',
    transcripts: 'transcripts',
    instructions: 'instructions',
    dictionary: 'dictionary',
    settings: 'settings',
    account: 'account',
    help: 'help'
  };
  const fileKey = map[key] || 'home';
  try {
    const res = await fetch(`./views/${fileKey}.html`);
    if (!res.ok) throw new Error('加载失败: ' + res.status);
    const html = await res.text();
    container.innerHTML = html;
    // run any post-load enhancements
    if (fileKey === 'home') {
      buildCalendar();
      // 初始化活跃徽章（重复调用安全）
      initStreakBadge();

      // 根据真实统计刷新顶部统计卡 & 今日 Banner
      refreshHomeStats();
      // 填充首页“最近转录”列表
      renderHomeRecentTranscripts();
    }
    if (fileKey === 'transcripts') {
      renderTranscripts();
      initTranscriptsInteractions();
    }
    if (fileKey === 'instructions') {
      initInstructions();
    }
    if (fileKey === 'dictionary') {
      initDictionary();
    }
    const main = qs('.content');
    if (main) {
      if (fileKey === 'transcripts') {
        main.classList.add('no-scroll');
      } else {
        main.classList.remove('no-scroll');
      }
      main.focus({ preventScroll: false });
    }
  } catch (err) {
    container.innerHTML = `<div class="panel"><h2 class="panel-title">错误</h2><p>${err.message}</p></div>`;
  }
}

function initNav() {
  qsa('.nav-item').forEach(btn => {
    btn.addEventListener('click', () => {
      const target = btn.dataset.target;
      if (target === 'settings') {
        // 设置作为模态，不改变当前主视图 active 状态
        openSettingsModal();
        return; // 不继续常规导航
      }
      qsa('.nav-item').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      loadView(target);
      history.replaceState(null, '', '#' + target);
    });
  });
  // hash routing
  const hash = location.hash.replace('#', '');
  if (hash) {
    const targetBtn = qs(`.nav-item[data-target="${hash}"]`);
    if (targetBtn) targetBtn.click();
  } else {
    loadView('dashboard');
  }
}

function buildCalendar() {
  const grid = qs('#calendar-grid');
  if (!grid) return;
  // generate 35 cells (5 weeks *7)
  const today = new Date();
  const seed = today.getDate();
  for (let i = 0; i < 35; i++) {
    const cell = document.createElement('div');
    cell.className = 'cell';
    // pseudo-random level for illustration
    const val = (Math.sin(seed + i) + 1) / 2; // 0..1
    const lvl = val > 0.75 ? 'l4' : val > 0.55 ? 'l3' : val > 0.35 ? 'l2' : val > 0.15 ? 'l1' : '';
    if (lvl) cell.classList.add(lvl);
    cell.title = `Day ${i + 1}: ${(val * 100).toFixed(0)} score`;
    cell.setAttribute('role', 'button');
    cell.tabIndex = 0;
    cell.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); cell.click(); } });
    cell.addEventListener('click', () => {
      cell.classList.toggle('pulse');
      setTimeout(() => cell.classList.remove('pulse'), 600);
    });
    grid.appendChild(cell);
  }
}

// 首页统计卡 & 今日 Banner
async function refreshHomeStats() {
  const totalEl = qs('#stat-total-words');
  const timeEl = qs('#stat-time-saved');
  const wpmEl = qs('#stat-wpm');
  const bannerEl = document.querySelector('.banner');
  try {
    const { totalWords, timeSavedSeconds, wpm, todayWords } = await getStats();
    if (totalEl && typeof totalWords === 'number') totalEl.textContent = String(totalWords);
    if (timeEl && typeof timeSavedSeconds === 'number') {
      if (timeSavedSeconds < 60) {
        timeEl.textContent = `${timeSavedSeconds}秒`;
      } else {
        const min = Math.round(timeSavedSeconds / 60);
        timeEl.textContent = `${min}分钟`;
      }
    }
    if (wpmEl && typeof wpm === 'number') wpmEl.textContent = String(wpm.toFixed(1));
    if (bannerEl && typeof todayWords === 'number') {
      const n = todayWords;
      if (n > 0) {
        bannerEl.textContent = `今天转录了${n}个字！继续加油！`;
      } else {
        bannerEl.textContent = '今天还没有新的转录，试试按两下 Ctrl 开始吧！';
      }
    }
  } catch (e) {
    console.warn('[home-stats] failed to refresh', e);
  }
}

// 首页左下角“最近转录”面板渲染
async function renderHomeRecentTranscripts() {
  const listEl = qs('#recent-transcripts');
  if (!listEl) return;
  // 先清空占位内容
  listEl.innerHTML = '<li class="transcript-item"><div class="text" style="opacity:.6">加载中...</div></li>';
  const sessions = await fetchRecentSessions(5);
  if (!sessions.length) {
    listEl.innerHTML = '<li class="transcript-item"><div class="text" style="opacity:.6">暂无转录记录</div></li>';
    return;
  }
  const items = sessions.map(s => {
    // created_at 预计为字符串，可尝试解析时间
    let timeStr = '';
    try {
      const d = new Date(s.created_at || s.session_id || '');
      if (!isNaN(d.getTime())) {
        timeStr = String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0');
      }
    } catch { }
    const text = (s.refined_text || '').trim() || (s.raw_text || '').trim() || '[空白转录]';
    return `<li class="transcript-item">
      <div class="time">${timeStr || '--:--'}</div>
      <div class="text">${escapeHtml(text)}</div>
    </li>`;
  }).join('');
  listEl.innerHTML = items;
}

function enhanceButtons() {
  qsa('button.btn').forEach(btn => {
    btn.addEventListener('pointerdown', () => btn.classList.add('down'));
    btn.addEventListener('pointerup', () => btn.classList.remove('down'));
    btn.addEventListener('mouseleave', () => btn.classList.remove('down'));
  });
}


// confirmDialog 已抽取到 ./components/ui-dialog.js

// Optional TAURI command examples (guarded)
export async function greet(name) {
  if (window.__TAURI__?.core?.invoke) {
    return await window.__TAURI__.core.invoke('greet', { name });
  }
  return `Hello ${name}`;
}

// 获取最近转录记录（后端 records/sessions 中的会话）
export async function fetchRecentSessions(limit = 10) {
  const invoke = window.__TAURI__?.core?.invoke;
  if (!invoke) return [];
  try {
    const list = await invoke('get_recent_sessions', { limit });
    return Array.isArray(list) ? list : [];
  } catch (e) {
    console.error('[recent-sessions] failed to load', e);
    return [];
  }
}

// 获取所有转录记录（转录页面使用）
export async function fetchAllTranscripts() {
  const invoke = window.__TAURI__?.core?.invoke;
  if (!invoke) return [];
  try {
    const list = await invoke('get_all_transcripts');
    return Array.isArray(list) ? list : [];
  } catch (e) {
    console.error('[all-transcripts] failed to load', e);
    return [];
  }
}

// (设置模态逻辑已拆分至 components/settings-modal.js)

// ---------------- Transcripts Page Logic ----------------
let transcriptsAll = []; // 后端加载的原始数据
let transcriptsPageSize = 20; // 每次翻页条数
let transcriptsLoaded = 0; // 当前列表加载到的条数（非搜索时）
let transcriptsRenderedCache = []; // 当前渲染的数据（未过滤前）
let transcriptsSearchActive = false;

function groupByDate(list) {
  const map = new Map();
  list.forEach(item => {
    const d = item.createdAt;
    const key = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
    if (!map.has(key)) map.set(key, []);
    map.get(key).push(item);
  });
  // sort keys desc (recent first)
  return Array.from(map.entries()).sort((a, b) => new Date(b[0]) - new Date(a[0]));
}

function renderTranscripts() {
  const root = qs('#transcripts-groups');
  const searchInput = qs('#transcripts-search');
  if (!root) return;
  const term = (searchInput?.value || '').trim().toLowerCase();
  transcriptsSearchActive = !!term;
  let sourceList;
  if (transcriptsSearchActive) {
    // 搜索模式：全量过滤
    sourceList = transcriptsAll.filter(t => (t.text || '').toLowerCase().includes(term));
  } else {
    // 非搜索：分页加载
    if (transcriptsLoaded === 0) {
      transcriptsLoaded = transcriptsPageSize;
    }
    sourceList = transcriptsAll.slice(0, transcriptsLoaded);
  }
  transcriptsRenderedCache = sourceList;
  const grouped = groupByDate(sourceList);
  root.innerHTML = grouped.map(([date, items]) => {
    const label = date === formatDate(new Date()) ? 'TODAY' : date;
    return `<div class="group"><div class="group-label">${label}</div><ul class="transcript-list">${items.map(renderTranscriptItem).join('')}</ul></div>`;
  }).join('') || `<div class="panel"><p style="opacity:.6">No transcripts.</p></div>`;
  updateInfiniteStatus();
}

function renderTranscriptItem(t) {
  const time = formatTime(t.createdAt);
  return `<li class="transcript-item" data-id="${t.id}">
    <div class="time">${time}</div>
    <div class="source-icon"><img class="source-img" src="https://edge.microsoft.com/favicon.ico" alt="${t.source}"></div>
    <div class="text">${escapeHtml(t.text)}</div>
    <div class="meta">
      <span class="duration">${t.durationSec}s • ${t.words} words</span>
      <div class="actions">
        <button class="icon-btn action-repeat" title="Repeat">&#8635;</button>
        <button class="icon-btn action-like" title="Like">&#128077;</button>
        <button class="icon-btn action-dislike" title="Dislike">&#128078;</button>
        <button class="icon-btn action-copy" title="Copy">&#128203;</button>
        <button class="icon-btn action-more" title="More">&#8942;</button>
      </div>
    </div>
  </li>`;
}

function formatDate(d) { return d.toISOString().slice(0, 10); }
function formatTime(d) { return String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0'); }
function escapeHtml(str) { return str.replace(/[&<>"']/g, s => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', '\'': '&#39;' }[s])); }

function initTranscriptsInteractions() {
  const searchInput = qs('#transcripts-search');
  if (searchInput) {
    searchInput.addEventListener('input', () => {
      // 重置搜索状态后重新渲染
      renderTranscripts();
    });
  }
  const root = qs('#transcripts-groups');
  if (!root) return;
  root.addEventListener('click', e => {
    const btn = e.target.closest('.icon-btn');
    if (!btn) return;
    const itemEl = btn.closest('.transcript-item');
    if (!itemEl) return;
    const id = Number(itemEl.dataset.id);
    if (btn.classList.contains('action-like')) {
      toggleExclusive(btn, itemEl, 'liked', '.action-like', '.action-dislike', 'disliked');
    } else if (btn.classList.contains('action-dislike')) {
      toggleExclusive(btn, itemEl, 'disliked', '.action-dislike', '.action-like', 'liked');
    } else if (btn.classList.contains('action-copy')) {
      const text = itemEl.querySelector('.text')?.textContent || '';
      navigator.clipboard?.writeText(text).catch(() => { });
      btn.classList.add('copied');
      setTimeout(() => btn.classList.remove('copied'), 1200);
    } else if (btn.classList.contains('action-repeat')) {
      // demo: flash item
      itemEl.classList.add('pulse');
      setTimeout(() => itemEl.classList.remove('pulse'), 600);
    }
  });

  // 无限滚动监听
  const scrollBox = qs('#transcripts-scroll');
  const statusEl = qs('#transcripts-status');
  // 首次进入时从后端加载全部会话
  (async () => {
    const rawList = await fetchAllTranscripts();
    transcriptsAll = rawList.map((s, idx) => {
      let createdAt;
      try {
        const d = new Date(s.created_at || s.session_id || '');
        createdAt = isNaN(d.getTime()) ? new Date() : d;
      } catch {
        createdAt = new Date();
      }
      const text = (s.refined_text || '').trim() || (s.raw_text || '').trim();
      const words = text ? text.length : 0;
      const durationSec = Math.round((s.duration_ms || 0) / 1000);
      return {
        id: idx + 1,
        text,
        source: 'Local',
        durationSec,
        words,
        createdAt,
        sessionId: s.session_id,
        jsonFilename: s.json_filename,
      };
    });
    transcriptsLoaded = 0;
    renderTranscripts();
    if (statusEl) updateInfiniteStatus();
  })();
  if (scrollBox) {
    scrollBox.addEventListener('scroll', () => {
      if (transcriptsSearchActive) return; // 搜索时不触发加载
      const threshold = 80; // px 距底部阈值
      if (scrollBox.scrollTop + scrollBox.clientHeight >= scrollBox.scrollHeight - threshold) {
        loadMoreTranscripts();
      }
    });
  }
  if (statusEl) updateInfiniteStatus();
}

function loadMoreTranscripts() {
  const total = transcriptsAll.length;
  if (transcriptsLoaded >= total) return; // 全部加载完
  transcriptsLoaded = Math.min(transcriptsLoaded + transcriptsPageSize, total);
  renderTranscripts();
}

function updateInfiniteStatus() {
  const statusEl = qs('#transcripts-status');
  if (!statusEl) return;
  if (transcriptsSearchActive) {
    statusEl.textContent = `Search results: ${transcriptsRenderedCache.length}`;
    return;
  }
  const total = transcriptsAll.length;
  if (transcriptsLoaded >= total) {
    statusEl.textContent = 'All transcripts loaded';
  } else {
    statusEl.textContent = `Loaded ${transcriptsLoaded}/${total} • Scroll for more...`;
  }
}

function toggleExclusive(btn, itemEl, addClass, selectorSelf, selectorOther, otherClass) {
  // Remove opposite state
  itemEl.querySelectorAll(selectorOther).forEach(b => b.classList.remove(otherClass));
  // Toggle current
  if (btn.classList.contains(addClass)) {
    btn.classList.remove(addClass);
  } else {
    itemEl.querySelectorAll(selectorSelf).forEach(b => b.classList.remove(addClass));
    btn.classList.add(addClass);
  }
}

// ---------------- Instructions Page Logic ----------------
function initInstructions() {
  const root = qs('#instructions-root');
  if (!root) return;
  const grid = qs('#modes-grid');
  const createBtn = qs('#create-mode-btn');
  if (createBtn) {
    createBtn.addEventListener('click', () => {
      const id = 'mode-' + Date.now();
      const card = document.createElement('div');
      card.className = 'mode-card';
      card.dataset.id = id;
      card.innerHTML = `<div class="mode-top"><div class="mode-title">新模式</div><button class="icon-btn mode-edit" title="Edit">✎ 编辑</button></div>
  <div class="mode-body hidden" data-role="edit-body"><textarea class="mode-text" placeholder="请输入模式提示词"></textarea>
  <div class="mode-actions"><button class="btn primary mode-save">保存</button><button class="btn ghost mode-cancel">取消</button><button class="btn danger mode-delete">删除</button></div></div>
  <div class="mode-footer"><button class="switch" aria-label="Toggle mode" data-role="toggle"><span></span></button></div>`;
      grid.appendChild(card);
    });
  }
  grid?.addEventListener('click', e => {
    const editBtn = e.target.closest('.mode-edit');
    if (editBtn) {
      const card = editBtn.closest('.mode-card');
      const body = card.querySelector('[data-role="edit-body"]');
      body.classList.toggle('hidden');
      return;
    }
    const saveBtn = e.target.closest('.mode-save');
    if (saveBtn) {
      const card = saveBtn.closest('.mode-card');
      const body = card.querySelector('[data-role="edit-body"]');
      body.classList.add('hidden');
      return;
    }
    const cancelBtn = e.target.closest('.mode-cancel');
    if (cancelBtn) {
      const card = cancelBtn.closest('.mode-card');
      const body = card.querySelector('[data-role="edit-body"]');
      body.classList.add('hidden');
      return;
    }
    const deleteBtn = e.target.closest('.mode-delete');
    if (deleteBtn) {
      const card = deleteBtn.closest('.mode-card');
      const title = card.querySelector('.mode-title')?.textContent?.trim() || '该';
      confirmDialog({ title: '确认删除', message: `确认删除“${title}”模式？`, confirmText: '确定', cancelText: '取消', danger: true })
        .then(ok => { if (ok) card.remove(); });
      return;
    }
    const toggleBtn = e.target.closest('.switch');
    if (toggleBtn) {
      toggleBtn.classList.toggle('active');
      return;
    }
  });
}

// ---------------- Dictionary Page Logic ----------------
let dictionaryEntries = []; // {id, original, replacement?}
function initDictionary() {
  const form = qs('#dict-form');
  const originalInput = qs('#dict-original');
  const replacementInput = qs('#dict-replacement');
  const toggleReplace = qs('#dict-toggle-replace');
  const list = qs('#dict-list');
  const empty = qs('#dict-empty');
  const alertBox = qs('#dict-alert');
  const addBtn = qs('#dict-add-btn');
  const arrowEl = qs('#dict-arrow');
  if (!form) return;

  function renderList() {
    list.innerHTML = dictionaryEntries.map(entry => `<li class="dict-item" data-id="${entry.id}">
      <span class="dict-term">${escapeHtml(entry.original)}</span>
      ${entry.replacement ? `<span class="dict-arrow">→</span><span class="dict-replacement">${escapeHtml(entry.replacement)}</span>` : ''}
      <div class="dict-actions">
        <button class="icon-btn dict-edit" title="编辑">✎</button>
        <button class="icon-btn dict-delete" title="删除">✖</button>
      </div>
    </li>`).join('');
    empty.style.display = dictionaryEntries.length ? 'none' : 'block';
  }

  function showAlert(msg) {
    alertBox.textContent = msg;
    alertBox.classList.remove('hidden');
    setTimeout(() => alertBox.classList.add('hidden'), 3000);
  }

  toggleReplace?.addEventListener('click', () => {
    toggleReplace.classList.toggle('active');
    const active = toggleReplace.classList.contains('active');
    replacementInput.classList.toggle('hidden', !active);
    arrowEl.classList.toggle('hidden', !active);
    if (!active) {
      replacementInput.value = '';
    } else {
      replacementInput.focus();
    }
    updateAddState();
  });

  form.addEventListener('submit', e => {
    e.preventDefault();
    const original = originalInput.value.trim();
    const replacement = !replacementInput.classList.contains('hidden') ? replacementInput.value.trim() : '';
    if (!original) { showAlert('请输入原始词。'); return; }
    if (dictionaryEntries.some(e => e.original.toLowerCase() === original.toLowerCase())) { showAlert('该词已存在。'); return; }
    const entry = { id: Date.now(), original, replacement: replacement || null };
    dictionaryEntries.push(entry);
    originalInput.value = '';
    replacementInput.value = '';
    renderList();
    updateAddState();
  });

  list.addEventListener('click', e => {
    const delBtn = e.target.closest('.dict-delete');
    if (delBtn) {
      const li = delBtn.closest('.dict-item');
      const id = Number(li.dataset.id);
      const entry = dictionaryEntries.find(x => x.id === id);
      confirmDialog({ title: '删除词条', message: `确认删除“${entry.original}”？`, confirmText: '删除', cancelText: '取消', danger: true, type: 'danger' })
        .then(ok => { if (ok) { dictionaryEntries = dictionaryEntries.filter(x => x.id !== id); renderList(); } });
      return;
    }
    const editBtn = e.target.closest('.dict-edit');
    if (editBtn) {
      const li = editBtn.closest('.dict-item');
      const id = Number(li.dataset.id);
      const entry = dictionaryEntries.find(x => x.id === id);
      if (!entry) return;
      // If already editing, ignore
      if (li.classList.contains('editing')) return;
      enterEditMode(li, entry);
      return;
    }
    const saveBtn = e.target.closest('.dict-save');
    if (saveBtn) {
      const li = saveBtn.closest('.dict-item');
      const id = Number(li.dataset.id);
      const entry = dictionaryEntries.find(x => x.id === id);
      if (!entry) return;
      const originalField = li.querySelector('.dict-edit-original');
      const replacementField = li.querySelector('.dict-edit-replacement');
      const newOriginal = (originalField?.value || '').trim();
      const newReplacement = replacementField ? (replacementField.value || '').trim() : '';
      if (!newOriginal) { flashInvalid(originalField); return; }
      if (dictionaryEntries.some(x => x.id !== id && x.original.toLowerCase() === newOriginal.toLowerCase())) {
        flashDuplicate(originalField); return;
      }
      entry.original = newOriginal;
      if (entry.replacement !== null) {
        entry.replacement = newReplacement || null;
      }
      renderList();
      return;
    }
    const cancelBtn = e.target.closest('.dict-cancel');
    if (cancelBtn) {
      const li = cancelBtn.closest('.dict-item');
      const id = Number(li.dataset.id);
      const entry = dictionaryEntries.find(x => x.id === id);
      if (!entry) return;
      // Simply rerender to exit edit
      renderList();
      return;
    }
  });

  renderList();

  function updateAddState() {
    const original = originalInput.value.trim();
    const needReplace = toggleReplace.classList.contains('active');
    const replacement = replacementInput.value.trim();
    const enabled = original && (!needReplace || replacement);
    if (enabled) {
      addBtn.disabled = false;
      addBtn.classList.remove('disabled');
    } else {
      addBtn.disabled = true;
      addBtn.classList.add('disabled');
    }
  }

  originalInput.addEventListener('input', updateAddState);
  replacementInput.addEventListener('input', updateAddState);
  updateAddState();

  // Inline edit helpers
  function enterEditMode(li, entry) {
    li.classList.add('editing');
    li.innerHTML = `<div class="dict-edit-fields">
      <input type="text" class="dict-input dict-edit-original" value="${escapeHtml(entry.original)}" aria-label="编辑原始词" />
      ${entry.replacement !== null ? `<span class="dict-arrow">→</span><input type="text" class="dict-input dict-edit-replacement" value="${escapeHtml(entry.replacement || '')}" aria-label="编辑替换词" placeholder="替换词(可留空)" />` : ''}
    </div>
    <div class="dict-edit-actions">
      <button class="btn primary dict-save" title="保存">保存</button>
      <button class="btn ghost dict-cancel" title="取消">取消</button>
    </div>`;
    const originalField = li.querySelector('.dict-edit-original');
    originalField.focus();
    originalField.addEventListener('keydown', e => { if (e.key === 'Enter') { li.querySelector('.dict-save')?.click(); } });
    const replField = li.querySelector('.dict-edit-replacement');
    replField?.addEventListener('keydown', e => { if (e.key === 'Enter') { li.querySelector('.dict-save')?.click(); } });
  }

  function flashInvalid(input) {
    if (!input) return;
    input.classList.add('shake');
    setTimeout(() => input.classList.remove('shake'), 600);
  }
  function flashDuplicate(input) {
    showAlert('该词已存在。');
    flashInvalid(input);
  }
}
