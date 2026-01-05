


function getInvoke() {
    const fn = window.__TAURI__?.core?.invoke || window.__TAURI__?.invoke;
    if (!fn) throw new Error('Tauri invoke 不可用: 未检测到 window.__TAURI__.core.invoke');
    return fn;
}

function ws_connect(optionalClientId) {
    const invoke = getInvoke();
    const clientId = optionalClientId || `${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
    const wsUrl = `ws://localhost:12000/ws/audio/${clientId}`;
    return invoke("ws_connect", { url: wsUrl }).then(() => clientId);
}

function ws_send_text(text) {
    return getInvoke()("ws_send_text", { text });
}


function ws_send_binary(uint8Array) {
    const b64 = btoa(String.fromCharCode(...uint8Array));
    return getInvoke()("ws_send_binary", { dataB64: b64 });
}

function ws_status() {
    return getInvoke()("ws_status");
}

function ws_disconnect() {
    return getInvoke()("ws_disconnect");
}

function ws_listen(event, callback) {
    return window.__TAURI__.event.listen(event, e => callback(e.payload));
}

export {
    ws_connect,
    ws_send_text,
    ws_send_binary,
    ws_status,
    ws_disconnect,
    ws_listen,
}

// // 连接
// await window.__TAURI__.invoke("ws_connect", { url: "ws://localhost:5678/ws/audio/test123" });

// // 发送文本
// await window.__TAURI__.invoke("ws_send_text", { text: "hello" });

// // 发送二进制（示例：Uint8Array）
// const bin = new Uint8Array([1, 2, 3, 4]);
// const b64 = btoa(String.fromCharCode(...bin));
// await window.__TAURI__.invoke("ws_send_binary", { dataB64: b64 });

// // 状态
// const status = await window.__TAURI__.invoke("ws_status");
// console.log(status);

// // 断开
// await window.__TAURI__.invoke("ws_disconnect");

// // 监听事件
// window.__TAURI__.event.listen("ws-message", e => console.log("WS MSG", e.payload));