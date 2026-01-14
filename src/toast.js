import { onRecognitionStart, onRecognitionStop, getRecognitionState } from './recognition.js';
// 引入热键桥接模块，使本窗口也能收到 recognition:start/stop 事件
import './hotkeys.js';

console.log('[toast] initializing, __TAURI__=', !!globalThis.__TAURI__);

const tauriEvent = globalThis.__TAURI__?.event;
console.log('[toast] tauriEvent available:', !!tauriEvent);

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
    try { startSound && startSound.currentTime !== undefined && (startSound.currentTime = 0); } catch { }
    try { startSound && startSound.play && startSound.play().catch(() => { }); } catch { }
}

function playFinalSound() {
    ensureSounds();
    try { finalSound && finalSound.currentTime !== undefined && (finalSound.currentTime = 0); } catch { }
    try { finalSound && finalSound.play && finalSound.play().catch(() => { }); } catch { }
}

// 控制 Tauri 窗口显示/隐藏
async function showWindow() {
    console.log('[toast] showWindow called');
    if (!window.__TAURI__) {
        console.error('[toast] window.__TAURI__ is undefined');
        return;
    }
    if (!window.__TAURI__.window) {
        console.error('[toast] window.__TAURI__.window is undefined');
        return;
    }
    try {
        const win = await window.__TAURI__.window.getCurrentWindow();
        console.log('[toast] got window, calling show()');
        await win.show();
        await win.setAlwaysOnTop(true);
        console.log('[toast] window shown');
    } catch (e) {
        console.error('[toast] showWindow error:', e);
    }
}

async function hideWindow() {
    console.log('[toast] hideWindow called');
    if (!window.__TAURI__?.window?.getCurrentWindow) return;
    try {
        const win = await window.__TAURI__.window.getCurrentWindow();
        await win.hide();
        console.log('[toast] window hidden');
    } catch (e) {
        console.error('[toast] hideWindow error:', e);
    }
}

// 等待 DOM 加载后再设置监听
window.addEventListener('DOMContentLoaded', () => {
    console.log('[toast] DOM loaded');

    const root = document.getElementById('toast-root');
    const indicator = document.getElementById('toast-indicator');
    const statusEl = document.getElementById('toast-status');
    const modeEl = document.getElementById('toast-mode');
    const textEl = document.getElementById('toast-text');

    console.log('[toast] elements found:', !!root, !!indicator, !!statusEl, !!modeEl, !!textEl);

    if (!root || !indicator || !statusEl || !modeEl || !textEl) {
        console.error('[toast] some elements not found!');
        return;
    }

    // 初始状态：隐藏 toast
    root.classList.remove('visible');

    if (tauriEvent?.listen) {
        console.log('[toast] setting up event listeners');

        // 监听应用关闭事件，确保 toast 窗口关闭
        tauriEvent.listen('tauri://close-requested', () => {
            console.log('[toast] app close requested, hiding toast');
            hideWindow();
        });

        // 监听 speech-event 事件，根据不同的事件类型更新 UI
        tauriEvent.listen('speech-event', ev => {
            console.log('[toast] speech-event received:', ev.payload);
            const payload = ev.payload || {};
            const eventType = payload.event;

            if (eventType === 'recording' && payload.state === 'start') {
                // 开始录音
                console.log('[toast] handling recording start');
                showToast();
                indicator.classList.remove('recording', 'processing');
                indicator.classList.add('recording');
                statusEl.textContent = '正在录音…';
                modeEl.textContent = '快捷键';
            } else if (eventType === 'recording' && payload.state === 'stop') {
                // 停止录音
                console.log('[toast] handling recording stop');
                showToast();
                indicator.classList.remove('recording', 'processing');
                indicator.classList.add('processing');
                statusEl.textContent = '正在优化表达…';
            } else if (eventType === 'final') {
                // 完成优化
                console.log('[toast] handling final');
                showToast();
                indicator.classList.remove('recording', 'processing');
                indicator.classList.add('processing');
                statusEl.textContent = '优化完成，已注入文本';
                modeEl.textContent = '完成';
                textEl.textContent = payload.processed || payload.raw || '';
                textEl.classList.remove('empty');
                playFinalSound();
                // 1.5 秒后自动隐藏
                setTimeout(() => {
                    console.log('[toast] auto-hiding after final');
                    root.classList.remove('visible');
                    hideWindow();
                }, 1500);
            } else if (eventType === 'error') {
                console.log('[toast] handling error');
                showToast();
                indicator.classList.remove('recording', 'processing');
                statusEl.textContent = `出错：${payload.message || '未知错误'}`;
                modeEl.textContent = '错误';
                setTimeout(() => {
                    root.classList.remove('visible');
                    hideWindow();
                }, 3200);
            }
        });

        console.log('[toast] event listeners set up');
    } else {
        console.error('[toast] Tauri event API not available');
    }
});

function showToast() {
    console.log('[toast] showToast called');
    if (!root) return;
    root.classList.add('visible');
    showWindow();
}
