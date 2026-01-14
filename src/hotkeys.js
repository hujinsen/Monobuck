// 全局快捷键桥接（后端 rdev 已处理 Ctrl+Win / 双击 Ctrl 等平台特定逻辑）
// 这里仅负责：监听后端广播的 recognition-event -> 转换为前端统一 CustomEvent
// 不再自行注册任何快捷键，避免与需求冲突。

const debug = (...args) => { if (window.__HOTKEY_DEBUG__) console.log('[hotkeys]', ...args) }

function dispatch(name, detail) {
    document.dispatchEvent(new CustomEvent(name, { detail }))
}

function setupBackendBridge() {
    console.log('[hotkeys] setupBackendBridge called');
    const tauriEvent = globalThis.__TAURI__?.event;
    console.log('[hotkeys] Tauri event API available:', !!tauriEvent?.listen);
    if (!tauriEvent?.listen) {
        console.warn('[hotkeys] 无法监听后端事件：TAURI event API 不存在');
        return;
    }
    tauriEvent.listen('recognition-event', ev => {
        const data = ev.payload;
        console.log('[hotkeys] recognition-event received:', data);
        if (!data || typeof data !== 'object') return;
        const { type } = data;
        debug('backend recognition-event', data);
        if (type === 'start') {
            console.log('[hotkeys] dispatching recognition:start');
            dispatch('recognition:start', data);
        }
        else if (type === 'stop') {
            console.log('[hotkeys] dispatching recognition:stop');
            dispatch('recognition:stop', data);
        }
        else if (type === 'error') console.error('[hotkeys] backend error', data);
    });
}

setupBackendBridge();

// 兼容旧 API：导出空实现，避免其它模块引用报错
export function initHotkeys() { /* no-op */ }
export function disposeHotkeys() { /* no-op */ }
export function isRecognitionActive() { return false }
export function manuallyStopRecognition() { /* no-op */ }
