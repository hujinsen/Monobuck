// recognition.js
// 统一的“语音识别生命周期”事件钩子层
// 目标：
//  1. 订阅由 hotkeys.js / 后端广播的识别开始/结束事件
//  2. 提供手动触发 (模拟/测试) API，不影响真实状态判定链
//  3. 提供去重：若重复触发 start 不再广播；stop 同理
//  4. 允许多个监听者独立取消订阅
//
// 事件来源链路：
//   系统全局快捷键 -> (Rust emit recognition-event) -> hotkeys.js -> DOM CustomEvent
//   本模块再次封装为回调式 API，便于业务使用
//
// 外部 API：
//   onRecognitionStart(cb) => unsubscribe()
//   onRecognitionStop(cb)  => unsubscribe()
//   triggerRecognitionStart(meta?)  (手动模拟)
//   triggerRecognitionStop(meta?)   (手动模拟)
//   getRecognitionState() -> { active:boolean, lastStartAt:number|null, lastStopAt:number|null, trigger?:string, mode?:string }
//
// 注意：模拟触发会带上 meta.mock=true，区分真实来源。

let state = {
    active: false,
    lastStartAt: null,
    lastStopAt: null,
    trigger: undefined,
    mode: undefined,
    lastTextRaw: '',
    lastTextProcessed: '',
    lastDurationMs: 0,
};

const startListeners = new Set();
const stopListeners = new Set();

function safeCall(set, payload) {
    for (const cb of [...set]) {
        try { cb(payload); } catch (e) { console.warn('[recognition] listener error', e); }
    }
}

function internalStart(detail) {
    if (state.active) return; // 去重
    state.active = true;
    state.lastStartAt = Date.now();
    state.trigger = detail?.trigger;
    state.mode = detail?.mode;
    safeCall(startListeners, { ...state, mock: detail?.mock === true });
}

function internalStop(detail) {
    if (!state.active) return; // 去重
    state.active = false;
    state.lastStopAt = Date.now();
    safeCall(stopListeners, { ...state, mock: detail?.mock === true });
}

// 监听 hotkeys.js 转发的浏览器事件
function attachDomBridge() {
    document.addEventListener('recognition:start', e => {
        console.log('[recognition.js] DOM recognition:start event received', e.detail);
        internalStart(e.detail);
    });
    document.addEventListener('recognition:stop', e => {
        console.log('[recognition.js] DOM recognition:stop event received', e.detail);
        internalStop(e.detail);
    });
    // 监听后端的语音 sidecar 转发 (speech-event)
    const tauriEvent = globalThis.__TAURI__?.event;
    console.log('[recognition.js] Tauri event API available:', !!tauriEvent?.listen);
    if (tauriEvent?.listen) {
        tauriEvent.listen('speech-event', ev => {
            const payload = ev.payload;
            if (!payload || typeof payload !== 'object') return;
            const eventType = payload.event;
            console.log('[speech-event]', eventType, payload); // 调试日志
            if (eventType === 'recording' && payload.state === 'start') {
                if (!state.active) internalStart({ trigger: 'backend', mode: 'backend' });
            } else if (eventType === 'recording' && payload.state === 'stop') {
                // 仅停止录音，还未 final，保持 processing 状态由 UI 管理
            } else if (eventType === 'final') {
                state.lastTextRaw = payload.raw || '';
                state.lastTextProcessed = payload.processed || payload.raw || '';
                state.lastDurationMs = payload.duration_ms || 0;
                if (state.active) internalStop({ trigger: 'backend-final', mode: 'backend' });
                document.dispatchEvent(new CustomEvent('recognition:final', {
                    detail: {
                        raw: state.lastTextRaw,
                        processed: state.lastTextProcessed,
                        durationMs: state.lastDurationMs,
                        ts: payload.ts,
                    }
                }));
            } else if (eventType === 'error') {
                // 后端错误事件传递到前端
                document.dispatchEvent(new CustomEvent('recognition:error', { detail: { message: payload.message || 'unknown error', raw: state.lastTextRaw, ts: payload.ts } }));
                // 如果仍处于 active，强制停止
                if (state.active) internalStop({ trigger: 'backend-error', mode: 'backend' });
            }
        });
    } else {
        console.error('[recognition.js] Tauri event API not available');
    }
}
attachDomBridge();

// 对外回调注册
export function onRecognitionStart(cb) {
    if (typeof cb !== 'function') return () => { };
    startListeners.add(cb);
    // 若当前已是 active，立即回放一次，方便组件挂载后同步
    if (state.active) queueMicrotask(() => { try { cb({ ...state, replay: true }); } catch { } });
    return () => startListeners.delete(cb);
}
export function onRecognitionStop(cb) {
    if (typeof cb !== 'function') return () => { };
    stopListeners.add(cb);
    if (!state.active && state.lastStopAt) queueMicrotask(() => { try { cb({ ...state, replay: true }); } catch { } });
    return () => stopListeners.delete(cb);
}

// 手动模拟（不会触发全局快捷键，仅本层 & 订阅者）
export function triggerRecognitionStart(meta = {}) { internalStart({ ...meta, mock: true, mode: meta.mode || 'manual' }); }
export function triggerRecognitionStop(meta = {}) { internalStop({ ...meta, mock: true, mode: meta.mode || 'manual' }); }

export function getRecognitionState() { return { ...state }; }

// 调试辅助（可选）
if (typeof window !== 'undefined') {
    window.__RECOG__ = { getRecognitionState, triggerRecognitionStart, triggerRecognitionStop };
}
