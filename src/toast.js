import { onRecognitionStart, onRecognitionStop, getRecognitionState } from './recognition.js';
// 引入热键桥接模块，使本窗口也能收到 recognition:start/stop 事件
import './hotkeys.js';

const root = document.getElementById('toast-root');
const indicator = document.getElementById('toast-indicator');
const statusEl = document.getElementById('toast-status');
const modeEl = document.getElementById('toast-mode');
const textEl = document.getElementById('toast-text');

let hideTimer = null;
let lastFinalTs = null;

// 提示音：开始录音 & 最终完成
let startSound = null;
let finalSound = null;

function ensureSounds() {
  if (typeof Audio === 'undefined') return;
  try {
    if (!startSound) {
      startSound = new Audio('./assets/sound/start_rec.wav');
    }
    if (!finalSound) {
      finalSound = new Audio('./assets/sound/final_rec.wav');
    }
  } catch {
    // 在某些环境下（如严格 CSP）可能构造失败，忽略即可
  }
}

function playStartSound() {
  ensureSounds();
  try { startSound && startSound.currentTime !== undefined && (startSound.currentTime = 0); } catch {}
  try { startSound && startSound.play && startSound.play().catch(() => {}); } catch {}
}

function playFinalSound() {
  ensureSounds();
  try { finalSound && finalSound.currentTime !== undefined && (finalSound.currentTime = 0); } catch {}
  try { finalSound && finalSound.play && finalSound.play().catch(() => {}); } catch {}
}

function showToast() {
  if (!root) return;
  root.classList.add('visible');
}

function hideToast() {
  if (!root) return;
  root.classList.remove('visible');
}

function setIndicator(state) {
  if (!indicator) return;
  indicator.classList.remove('recording', 'processing');
  if (state === 'recording') indicator.classList.add('recording');
  if (state === 'processing') indicator.classList.add('processing');
}

function setStatus(text) {
  if (!statusEl) return;
  statusEl.textContent = text;
}

function setMode(text) {
  if (!modeEl) return;
  modeEl.textContent = text || '';
}

function setTextPreview(text) {
  if (!textEl) return;
  if (text && text.trim()) {
    textEl.textContent = text.trim();
    textEl.classList.remove('empty');
  } else {
    textEl.textContent = '暂无文本';
    textEl.classList.add('empty');
  }
}

function scheduleAutoHide(delayMs = 2600) {
  if (hideTimer) clearTimeout(hideTimer);
  hideTimer = setTimeout(() => {
    hideTimer = null;
    hideToast();
  }, delayMs);
}

// 初始化时根据当前状态做一次同步（例如应用重启时仍处于 active）
(function initialSync() {
  const state = getRecognitionState?.();
  if (!state) return;
  if (state.active) {
    showToast();
    setIndicator('recording');
    setStatus('正在聆听…');
    setMode(state.mode === 'backend' ? '快捷键 · 后台' : '手动');
  }
})();

// 订阅识别开始/结束
onRecognitionStart(state => {
  if (hideTimer) {
    clearTimeout(hideTimer);
    hideTimer = null;
  }
  showToast();
  setIndicator('recording');
  setStatus('正在聆听…');
  setMode(state.mode === 'backend' ? '快捷键 · 后台' : '手动');
  playStartSound();
});

onRecognitionStop(state => {
  // stop 之后可能还在等待最终结果，这里显示为“处理中”
  setIndicator('processing');
  setStatus('处理中…');
  setMode(state.mode === 'backend' ? '快捷键 · 后台' : '手动');
  // 不立即隐藏，等待 final 事件来收尾
});

// 监听 recognition.js 派发的最终结果事件
if (typeof document !== 'undefined') {
  document.addEventListener('recognition:final', e => {
    const detail = e.detail || {};
    lastFinalTs = detail.ts || Date.now();
    showToast();
    setIndicator('processing');
    setStatus('已完成，正在注入文本…');
    setMode('完成');
    setTextPreview(detail.processed || detail.raw || '');
    playFinalSound();
    scheduleAutoHide(2800);
  });

  document.addEventListener('recognition:error', e => {
    const detail = e.detail || {};
    showToast();
    setIndicator(null);
    setStatus(`出错：${detail.message || '未知错误'}`);
    setMode('错误');
    scheduleAutoHide(3200);
  });
}

// 调试辅助：在独立窗口中快速查看当前状态
if (typeof window !== 'undefined') {
  window.__monobuckToastDebug = {
    showToast,
    hideToast,
    setStatus,
    setTextPreview,
  };
}
