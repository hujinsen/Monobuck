// Learn more about Tauri commands at https://tauri.app/develop/calling-rust/
use std::sync::{Arc, Mutex};
use tauri::path::BaseDirectory;
use tauri::{Emitter, Manager}; // emit()
// 在当前 Tauri 版本中，逻辑坐标和尺寸类型直接从 tauri 根命名空间导出
use tauri::{LogicalPosition, LogicalSize};

// 引入快捷键模块
mod hotkey;
use hotkey::{
    clear_custom_shortcut, create_default_hotkey_state, init_hotkey_listener, set_custom_shortcut,
    Shared,
};

mod websocket;
use websocket::{
    ws_connect, ws_disconnect, ws_send_binary, ws_send_text, ws_status, WebSocketState, WsShared,
};
// 注入与音频模块
mod injection;
use injection::inject_text_unicode;
mod audio_stream;
use audio_stream::{start_audio, stop_audio, AudioShared, AudioState, InputDevicesInfo};
mod session;
use session::{
    read_all_sessions, read_recent_sessions, RecentSessionItem, SessionShared, SessionState,
    TranscriptItem,
};
mod stats;
use stats::{compute_stats_full, StatsAggregate};
// Python 子进程共享状态
#[derive(Clone)]
struct PythonShared {
    inner: Arc<Mutex<Option<std::process::Child>>>,
}

// 统计缓存共享状态
#[derive(Clone)]
struct StatsShared {
    inner: Arc<Mutex<StatsAggregate>>,
}

// 在某些情况下（例如窗口异常关闭或子进程未被正常记录），
// 可能仍会残留名为 websocket_server.exe 的 sidecar 进程。
// 为了在应用关闭时更稳妥地清理它，这里在 Windows 下追加一次基于进程名的强制结束。
#[cfg(target_os = "windows")]
fn kill_websocket_sidecar_best_effort() {
    use std::process::Command;
    // 使用 taskkill /IM websocket_server.exe /F /T 结束同名进程树，失败静默忽略。
    let _ = Command::new("taskkill")
        .args(["/IM", "websocket_server.exe", "/F", "/T"])
        .spawn();
}

#[cfg(not(target_os = "windows"))]
fn kill_websocket_sidecar_best_effort() {
    // 非 Windows 平台无需额外处理
}

// 记录用户在设置面板中选择的麦克风设备名称，由音频模块在启动录音时优先使用
#[tauri::command]
fn set_mic_preference(
    name: String,
    audio: tauri::State<'_, AudioShared>,
) -> Result<(), String> {
    let mut guard = audio
        .inner
        .lock()
        .map_err(|_| "audio state poisoned".to_string())?;
    guard.preferred_input = Some(name);
    Ok(())
}

/// 获取当前系统可用的音频输入设备列表
#[tauri::command]
fn get_input_devices(audio: tauri::State<'_, AudioShared>) -> Result<InputDevicesInfo, String> {
    let shared = audio.inner.clone();
    audio_stream::list_input_devices(shared)
}

#[tauri::command]
fn greet(name: &str) -> String {
    format!("Hello, {}! You've been greeted from Rust!", name)
}

/// 供前端调用：获取最近 N 条转录会话元数据
#[tauri::command]
fn get_recent_sessions(
    limit: Option<u32>,
    state: tauri::State<'_, SessionShared>,
) -> Vec<RecentSessionItem> {
    let limit = limit.unwrap_or(10).max(1).min(100) as usize;
    let guard = state.inner.lock().expect("session state poisoned");
    read_recent_sessions(&guard.base_dir, limit)
}

/// 供“转录”页面调用：获取所有会话转录记录（按时间倒序）
#[tauri::command]
fn get_all_transcripts(state: tauri::State<'_, SessionShared>) -> Vec<TranscriptItem> {
    let guard = state.inner.lock().expect("session state poisoned");
    read_all_sessions(&guard.base_dir)
}

/// 聚合统计：总字数 / 节省时间 / WPM / 今日字数
#[tauri::command]
fn get_stats(stats: tauri::State<'_, StatsShared>) -> Result<StatsAggregate, String> {
    let guard = stats
        .inner
        .lock()
        .map_err(|_| "stats state poisoned".to_string())?;
    Ok(guard.clone())
}

/// 设置应用状态（用于更新标题栏等原生界面）
#[tauri::command]
fn set_app_status(status: String, app: tauri::AppHandle) {
    update_window_title(&app, &status);
}

fn update_window_title(app: &tauri::AppHandle, status: &str) {
    if let Some(win) = app.get_webview_window("main") {
        let title = match status {
            "recording" => "🔴 Monobuck - 正在录音...",
            "processing" => "🟡 Monobuck - 正在优化表达...",
            "idle" => "Monobuck",
            _ => "Monobuck",
        };
        let _ = win.set_title(title);
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    use tauri::Manager;
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        // 初始化全局快捷键插件（实际注册 & 双击逻辑下放到前端 JS）
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .setup(|app| {
            let app_handle = app.handle().clone();

            // 初始化热键状态
            let hotkey_state = Arc::new(Mutex::new(create_default_hotkey_state()));
            app.manage(Shared {
                inner: hotkey_state.clone(),
            });

            // 初始化 WebSocket 状态
            let ws_state = Arc::new(Mutex::new(WebSocketState::new()));
            app.manage(WsShared { inner: ws_state });

            // 初始化音频状态
            let audio_state = Arc::new(Mutex::new(AudioState::new()));
            app.manage(AudioShared { inner: audio_state });

            // 初始化 Session 状态
            // 当前目录是 src-tauri，父目录是项目根
            let project_root = std::env::current_dir()
                .unwrap()
                .parent()
                .unwrap()
                .to_path_buf();
            let records_dir = project_root.join("records");
            let session_state = Arc::new(Mutex::new(SessionState::new(records_dir)));
            app.manage(SessionShared { inner: session_state.clone() });

            // 初始化统计缓存（启动时根据已有 sessions 计算一次）
            let stats_state = Arc::new(Mutex::new(StatsAggregate::default()));
            {
                let session_state_for_stats = session_state.clone();
                let stats_state_clone = stats_state.clone();
                tauri::async_runtime::spawn(async move {
                    if let Ok(session) = session_state_for_stats.lock() {
                        let items = read_all_sessions(&session.base_dir);
                        let agg = compute_stats_full(&items);
                        if let Ok(mut s) = stats_state_clone.lock() {
                            *s = agg;
                        }
                    }
                });
            }
            app.manage(StatsShared { inner: stats_state });

            // 启动 WebSocket Server 作为 sidecar 进程
            // 开发模式优先使用本地 python + 源码，
            // 打包后使用打进资源的 websocket_server.exe
            let py_state = Arc::new(Mutex::new(None::<std::process::Child>));
            app.manage(PythonShared { inner: py_state.clone() });

            #[cfg(target_os = "windows")]
            {
                use std::process::{Command, Stdio};

                #[cfg(debug_assertions)]
                {
                    // 开发模式：直接用本地 python 运行源码，方便调试
                    let script_path = project_root.join("mono_core").join("websocket_server.py");

                    let venv_python = project_root
                        .join("mono_core")
                        .join(".venv")
                        .join("Scripts")
                        .join("python.exe");

                    let child_result = Command::new(&venv_python)
                        .arg(&script_path)
                        .current_dir(project_root.join("mono_core"))
                        .stdout(Stdio::null())
                        .stderr(Stdio::null())
                        .spawn();

                    match child_result {
                        Ok(child) => {
                            if let Ok(mut g) = py_state.lock() {
                                *g = Some(child);
                            }
                            let _ = app.emit(
                                "backend-event",
                                serde_json::json!({"evt":"python-start","path": venv_python}),
                            );
                        }
                        Err(e) => {
                            let _ = app.emit(
                                "backend-event",
                                serde_json::json!({
                                    "evt":"python-start-error",
                                    "error": format!("dev python start failed: {e}"),
                                }),
                            );
                        }
                    }
                }

                #[cfg(not(debug_assertions))]
                {
                    // release / 打包后：启动打包到资源目录中的 websocket_server.exe sidecar
                    let sidecar_path = app
                        .path()
                        .resolve("resources/websocket_server.exe", BaseDirectory::Resource)
                        .or_else(|_| app.path().resolve("websocket_server.exe", BaseDirectory::Resource))
                        .expect("无法找到 websocket_server.exe sidecar");

                    // Debug log to temp file
                    let log_path = std::env::temp_dir().join("monobuck_rust_debug.log");
                    let _ = std::fs::write(&log_path, format!("Attempting to spawn sidecar at: {:?}\n", sidecar_path));

                    let mut command = Command::new(&sidecar_path);
                    command.stdout(Stdio::null());
                    command.stderr(Stdio::null());
                    
                    // 设置工作目录为 sidecar 所在目录
                    if let Some(parent) = sidecar_path.parent() {
                        command.current_dir(parent);
                        let _ = std::fs::write(&log_path, format!("Setting CWD to: {:?}\n", parent));
                    }

                    // 关键：在 Windows 上，如果是 GUI 应用启动的子进程，
                    // 某些库（如 onnxruntime/multiprocessing）可能因为没有控制台而行为异常。
                    // 尝试显式创建无窗口标志，或者保留 CREATE_NO_WINDOW
                    use std::os::windows::process::CommandExt;
                    const CREATE_NO_WINDOW: u32 = 0x08000000;
                    command.creation_flags(CREATE_NO_WINDOW);

                    let child_result = command.spawn();

                    match child_result {
                        Ok(child) => {
                            let _ = std::fs::write(&log_path, format!("Spawn success: {:?}\n", sidecar_path));
                            if let Ok(mut g) = py_state.lock() {
                                *g = Some(child);
                            }
                            let _ = app.emit(
                                "backend-event",
                                serde_json::json!({
                                    "evt":"python-sidecar-start",
                                    "path": sidecar_path,
                                }),
                            );
                        }
                        Err(e) => {
                            let _ = std::fs::write(&log_path, format!("Spawn failed: {}\n", e));
                            let _ = app.emit(
                                "backend-event",
                                serde_json::json!({
                                    "evt":"python-sidecar-error",
                                    "error": e.to_string(),
                                }),
                            );
                        }
                    }
                }
            }

            // 应用关闭时清理：停止音频、断开 WS、终止 Python 子进程
            {
                let app_handle_for_close = app_handle.clone();
                if let Some(main_win) = app_handle.clone().get_webview_window("main") {
                    let py_state_for_close = py_state.clone();
                    main_win.on_window_event(move |event| {
                        use tauri::WindowEvent;
                        if let WindowEvent::CloseRequested { .. } = event {
                        // 停止音频
                        let audio_state = app_handle_for_close.state::<AudioShared>().inner.clone();
                        let session_state = app_handle_for_close.state::<SessionShared>().inner.clone();
                        let _ = stop_audio(audio_state, session_state);
                        // 断开 WS
                        let ws = app_handle_for_close.state::<WsShared>();
                        // 调用命令接口需要异步，这里简单设置状态并发 Close 帧
                        if let Ok(mut g) = ws.inner.lock() {
                            if g.connected {
                                if let Some(tx) = &g.sender {
                                    let _ = tx.send(tokio_tungstenite::tungstenite::protocol::Message::Close(None));
                                }
                                g.connected = false;
                                g.sender = None;
                                g.url = None;
                            }
                        }
                        // 终止 Python 子进程（State 管理）
                        if let Ok(mut g) = py_state_for_close.lock() {
                            if let Some(mut child) = g.take() {
                                let _ = child.kill();
                                let _ = child.wait();
                            }
                        }
                        // 兜底：再按进程名尝试结束可能残留的 websocket_server.exe
                        kill_websocket_sidecar_best_effort();
                        
                        // 显式退出应用，解决 toast 窗口残留导致进程不退出的问题
                        app_handle_for_close.exit(0);
                        }
                    });
                }
            }

            // 启动 Python 后端进程（Windows 优先使用 venv）
            // 简化：不做健康检查与重连，仅在应用启动时尝试一次。
            // let py_state = Arc::new(Mutex::new(None::<Child>));
            // app.manage(PythonShared { inner: py_state.clone() });
            // #[cfg(target_os = "windows")]
            // {
            //     // 尝试使用项目内虚拟环境 python
            //     // 注意：Tauri 运行时当前目录通常是 src-tauri，因此这里使用相对上级路径
            //     let python_path = "../mono_core/.venv/Scripts/python.exe";
            //     let script_path = "../mono_core/webapp/backend/websocket_server.py";
            //     let child_result = Command::new(python_path)
            //         .arg(script_path)
            //         .stdout(Stdio::null())
            //         .stderr(Stdio::null())
            //         .spawn();
            //     match child_result {
            //         Ok(child) => {
            //             if let Ok(mut g) = py_state.lock() { *g = Some(child); }
            //             let _ = app.emit("backend-event", serde_json::json!({"evt":"python-start","path":python_path}));
            //         }
            //         Err(e) => {
            //             // 回退到系统 python
            //             let child_fallback = Command::new("python")
            //                 .arg(script_path)
            //                 .stdout(Stdio::null())
            //                 .stderr(Stdio::null())
            //                 .spawn();
            //             match child_fallback {
            //                 Ok(child) => {
            //                     if let Ok(mut g) = py_state.lock() { *g = Some(child); }
            //                     let _ = app.emit("backend-event", serde_json::json!({"evt":"python-start-fallback","path":"python","error":format!("venv failed: {}", e)}));
            //                 }
            //                 Err(e2) => {
            //                     let _ = app.emit("backend-event", serde_json::json!({"evt":"python-start-error","error":format!("{e}; fallback: {e2}")}));
            //                 }
            //             }
            //         }
            //     }
            // }

            // // 应用关闭时清理：停止音频、断开 WS、终止 Python 子进程
            // {
            //     let app_handle_for_close = app_handle.clone();
            //     if let Some(main_win) = app_handle.clone().get_webview_window("main") {
            //         let py_state_for_close = app.state::<PythonShared>().inner.clone();
            //         main_win.on_window_event(move |event| {
            //             use tauri::WindowEvent;
            //             if let WindowEvent::CloseRequested { .. } = event {
            //             // 停止音频
            //             let audio_state = app_handle_for_close.state::<AudioShared>().inner.clone();
            //             let session_state = app_handle_for_close.state::<SessionShared>().inner.clone();
            //             let _ = stop_audio(audio_state, session_state);
            //             // 断开 WS
            //             let ws = app_handle_for_close.state::<WsShared>();
            //             // 调用命令接口需要异步，这里简单设置状态并发 Close 帧
            //             if let Ok(mut g) = ws.inner.lock() {
            //                 if g.connected {
            //                     if let Some(tx) = &g.sender {
            //                         let _ = tx.send(tokio_tungstenite::tungstenite::protocol::Message::Close(None));
            //                     }
            //                     g.connected = false;
            //                     g.sender = None;
            //                     g.url = None;
            //                 }
            //             }
            //             // 终止 Python 子进程（State 管理）
            //             if let Ok(mut g) = py_state_for_close.lock() {
            //                 if let Some(mut child) = g.take() {
            //                     let _ = child.kill();
            //                     let _ = child.wait();
            //                 }
            //             }
            //             }
            //         });
            //     }
            // }

            // // 检查 5678 端口是否已监听，若就绪则自动连接到 WS
            // {
            //     let app_for_connect = app_handle.clone();
            //     std::thread::spawn(move || {
            //         use std::net::TcpStream;
            //         let addr = "127.0.0.1:5678";
            //         // 最多尝试 10 次，每次间隔 500ms，大约 5 秒
            //         for _ in 0..10 {
            //             if TcpStream::connect(addr).is_ok() {
            //                 // 端口已打开，启动异步任务进行 ws 连接
            //                 tauri::async_runtime::spawn(async move {
            //                     let millis = std::time::SystemTime::now()
            //                         .duration_since(std::time::UNIX_EPOCH)
            //                         .map(|d| d.as_millis())
            //                         .unwrap_or(0);
            //                     let tid = std::thread::current().id();
            //                     let client_id = format!("{}_{:?}", millis, tid);
            //                     let url = format!("ws://127.0.0.1:5678/ws/audio/{}", client_id);
            //                     let ws_state = app_for_connect.state::<WsShared>().inner.clone();
            //                     let session_state = app_for_connect.state::<SessionShared>().inner.clone();
            //                     let stats_state = app_for_connect.state::<StatsShared>().inner.clone();
            //                     if let Err(e) = ws_connect_internal(ws_state, session_state, stats_state, app_for_connect.clone(), url.clone()).await {
            //                         let _ = app_for_connect.emit("ws-error", serde_json::json!({"evt":"auto-connect","error":e}));
            //                     }
            //                 });
            //                 return;
            //             }
            //             std::thread::sleep(std::time::Duration::from_millis(500));
            //         }
            //         // 多次尝试仍未连通，发事件提示后端未就绪
            //         let _ = app_for_connect.emit("backend-event", serde_json::json!({"evt":"python-port-timeout","addr":addr}));
            //     });
            // }

            // 由热键触发的开始/停止回调
            let app_handle_for_cb = app_handle.clone();
            let sender_wrapper = move |cmd: serde_json::Value| {
                if let Some(cmd_str) = cmd.get("cmd").and_then(|v| v.as_str()) {
                    match cmd_str {
                        "start" => {
                            // 更新主窗口标题状态
                            update_window_title(&app_handle_for_cb, "recording");

                            // 显示录音状态浮窗
                            if let Some(status_win) = app_handle_for_cb.get_webview_window("recording-status") {
                                let _ = status_win.show();
                            }

                            let audio_state = app_handle_for_cb.state::<AudioShared>().inner.clone();
                            let ws_state = app_handle_for_cb.state::<WsShared>().inner.clone();
                            let session_state = app_handle_for_cb.state::<SessionShared>().inner.clone();
                            if let Err(e) = start_audio(audio_state, ws_state, session_state) {
                                eprintln!("启动音频失败: {e}");
                                let _ = app_handle_for_cb.emit("speech-event", serde_json::json!({"event":"error","stage":"start-audio","error":e}));
                                update_window_title(&app_handle_for_cb, "idle");
                            } else {
                                let _ = app_handle_for_cb.emit("speech-event", serde_json::json!({"event":"info","stage":"audio-started"}));
                                // 录音真正开始时通知前端，驱动 recognition.js 中的 recording/start 流程
                                let _ = app_handle_for_cb.emit(
                                    "speech-event",
                                    serde_json::json!({
                                        "event": "recording",
                                        "state": "start"
                                    }),
                                );
                            }
                        }
                        "stop" => {
                            // 更新状态为"正在优化表达"
                            update_window_title(&app_handle_for_cb, "processing");

                            let audio_state = app_handle_for_cb.state::<AudioShared>().inner.clone();
                            let session_state = app_handle_for_cb.state::<SessionShared>().inner.clone();
                            if let Err(e) = stop_audio(audio_state, session_state) {
                                eprintln!("停止音频失败: {e}");
                                let _ = app_handle_for_cb.emit("speech-event", serde_json::json!({"event":"error","stage":"stop-audio","error":e}));
                            } else {
                                let _ = app_handle_for_cb.emit("speech-event", serde_json::json!({"event":"info","stage":"audio-stopped"}));
                                // 录音停止（等待后端最终结果），供前端区分"录音中"和"处理中"
                                let _ = app_handle_for_cb.emit(
                                    "speech-event",
                                    serde_json::json!({
                                        "event": "recording",
                                        "state": "stop"
                                    }),
                                );
                                // 发送 stop_recording 指令给 Python
                                use tauri::Manager;
                                let ws_state = app_handle_for_cb.state::<WsShared>();
                                let msg = serde_json::json!({
                                    "type": "control",
                                    "command": "stop_recording"
                                }).to_string();
                                let _ = websocket::ws_send_text_internal(&ws_state.inner, &msg);
                                // 隐藏录音状态浮窗
                                if let Some(status_win) = app_handle_for_cb.get_webview_window("recording-status") {
                                    let _ = status_win.hide();
                                }
                            }
                        }
                        _ => {}
                    }
                }
            };

            println!("即将初始化快捷键监听器·····");
            // 初始化快捷键监听器
            init_hotkey_listener(&app_handle, hotkey_state, Some(sender_wrapper));

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            greet,
            get_all_transcripts,
            get_recent_sessions,
            set_custom_shortcut,
            clear_custom_shortcut,
            ws_connect,
            ws_send_text,
            ws_send_binary,
            ws_disconnect,
            ws_status,
            inject_text_unicode,
            set_mic_preference,
            get_input_devices,
            set_app_status
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
