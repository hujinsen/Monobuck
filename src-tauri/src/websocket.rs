use crate::audio_stream::finalize_session;
use crate::injection::inject_text_unicode_internal;
use crate::session::{SessionShared, SessionState, TranscriptItem};
use crate::stats::{apply_session_increment, StatsAggregate};
use crate::StatsShared;
use futures::{SinkExt, StreamExt};
use serde_json;
use std::sync::{Arc, Mutex};
use tauri::{AppHandle, Emitter, Manager};
use tauri::State;
use tokio::sync::mpsc;
use tokio::time::sleep;
use tokio_tungstenite::{connect_async, tungstenite::protocol::Message, tungstenite::Bytes};

#[derive(Debug)]
pub struct WebSocketState {
    pub url: Option<String>,
    pub sender: Option<mpsc::UnboundedSender<Message>>, // 写入消息的通道
    pub connected: bool,
}

impl WebSocketState {
    pub fn new() -> Self {
        Self {
            url: None,
            sender: None,
            connected: false,
        }
    }
}

pub struct WsShared {
    pub inner: Arc<Mutex<WebSocketState>>,
}

// 内部使用的原始二进制发送（无需 Base64，供音频采集调用）
pub fn ws_send_raw_internal(
    shared_arc: &Arc<Mutex<WebSocketState>>,
    bytes: &[u8],
) -> Result<(), String> {
    let guard = shared_arc.lock().map_err(|_| "state poisoned")?;
    if !guard.connected {
        return Err("未连接".into());
    }
    if let Some(tx) = &guard.sender {
        tx.send(Message::Binary(Bytes::from(bytes.to_vec())))
            .map_err(|e| format!("发送失败: {e}"))?;
    }
    Ok(())
}

pub fn ws_send_text_internal(
    shared_arc: &Arc<Mutex<WebSocketState>>,
    text: &str,
) -> Result<(), String> {
    let guard = shared_arc.lock().map_err(|_| "state poisoned")?;
    if !guard.connected {
        return Err("未连接".into());
    }
    if let Some(tx) = &guard.sender {
        tx.send(Message::Text(text.to_string().into()))
            .map_err(|e| format!("发送失败: {e}"))?;
    }
    Ok(())
}

#[tauri::command]
pub fn ws_send_text(state: State<'_, WsShared>, text: String) -> Result<(), String> {
    ws_send_text_internal(&state.inner, &text)
}

#[tauri::command]
pub fn ws_send_binary(state: State<'_, WsShared>, data: Vec<u8>) -> Result<(), String> {
    ws_send_raw_internal(&state.inner, &data)
}

#[tauri::command]
pub fn ws_disconnect(state: State<'_, WsShared>) -> Result<(), String> {
    let mut guard = state.inner.lock().map_err(|_| "state poisoned")?;
    if !guard.connected {
        return Ok(());
    }
    if let Some(tx) = &guard.sender {
        let _ = tx.send(Message::Close(None));
    }
    guard.connected = false;
    guard.sender = None;
    guard.url = None;
    Ok(())
}

#[tauri::command]
pub fn ws_status(state: State<'_, WsShared>) -> Result<bool, String> {
    let guard = state.inner.lock().map_err(|_| "state poisoned")?;
    Ok(guard.connected)
}

#[tauri::command]
pub async fn ws_connect(
    ws_state: State<'_, WsShared>,
    session_state: State<'_, SessionShared>,
    stats_state: State<'_, StatsShared>,
    app_handle: tauri::AppHandle,
    url: String,
) -> Result<(), String> {
    ws_connect_internal(
        ws_state.inner.clone(),
        session_state.inner.clone(),
        stats_state.inner.clone(),
        app_handle,
        url,
    )
    .await
}

pub async fn ws_connect_internal(
    shared_arc: Arc<Mutex<WebSocketState>>,
    session_shared: Arc<Mutex<SessionState>>,
    stats_shared: Arc<Mutex<StatsAggregate>>,
    app_handle: AppHandle,
    url: String,
) -> Result<(), String> {
    {
        let guard = shared_arc.lock().map_err(|_| "state poisoned")?;
        if guard.connected {
            return Err("已有活动连接，请先断开".into());
        }
    }
    let url_clone = url.clone();

    println!("正在连接到: {}", url);

    // Python 端在启动本地 ASR 引擎（加载 SenseVoice 模型等）时可能需要较长时间，
    // 这里通过较长的重试窗口，避免模型尚未加载完就宣告连接失败。
    let max_attempts = 120usize; // 最长约 60 秒（120 x 500ms）
    let mut last_err: Option<String> = None;
    let ws_stream = {
        use std::time::Duration;
        use tokio::time::sleep;

        let mut result = None;
        for attempt in 0..max_attempts {
            match connect_async(&url_clone).await {
                Ok((stream, _resp)) => {
                    result = Some(stream);
                    break;
                }
                Err(e) => {
                    let msg = format!("连接失败(第 {}/{} 次): {}", attempt + 1, max_attempts, e);
                    println!("{}", msg);
                    last_err = Some(msg);
                    if attempt + 1 < max_attempts {
                        sleep(Duration::from_millis(500)).await;
                    }
                }
            }
        }
        result.ok_or_else(|| {
            last_err.unwrap_or_else(|| "多次尝试后仍无法连接 WebSocket 服务器".to_string())
        })?
    };

    println!("WebSocket 连接成功");

    let (mut write, mut read) = ws_stream.split();
    let (tx, mut rx) = mpsc::unbounded_channel::<Message>();

    {
        let mut guard = shared_arc.lock().map_err(|_| "state poisoned")?;
        guard.connected = true;
        guard.sender = Some(tx);
        guard.url = Some(url_clone.clone());
    }

    // 写入任务
    tokio::spawn(async move {
        while let Some(msg) = rx.recv().await {
            if let Err(e) = write.send(msg).await {
                eprintln!("发送失败: {}", e);
                break;
            }
        }
    });

    // 读取任务
    let shared_arc_for_read = shared_arc.clone();
    let session_shared_for_read = session_shared.clone();
    let stats_shared_for_read = stats_shared.clone();
    let app_handle_for_read = app_handle.clone();
    tokio::spawn(async move {
        while let Some(item) = read.next().await {
            match item {
                Ok(Message::Text(t)) => {
                    let maybe_json = serde_json::from_str::<serde_json::Value>(&t).ok();
                    if let Some(v) = maybe_json.as_ref() {
                        if v.get("status").and_then(|x| x.as_str()) == Some("recognition_result") {
                            if let Some(txt) = v.get("text").and_then(|x| x.as_str()) {
                                println!("收到识别结果: {}", txt);

                                // Update session text
                                if let Ok(mut session) = session_shared_for_read.lock() {
                                    if session.current_id.is_some() {
                                        // Append text instead of replacing, or handle as needed.
                                        // Assuming 'txt' is a segment. If it's full text, replace is fine.
                                        // Based on Python code, it seems to be segments.
                                        // But for now, let's just log and set it.
                                        println!(
                                            "更新 Session 文本: ID={:?}, Text={}",
                                            session.current_id, txt
                                        );
                                        session.raw_text = txt.to_string();
                                        session.refined_text = txt.to_string();
                                    } else {
                                        eprintln!("收到识别结果但 Session ID 为空: {}", txt);
                                    }
                                } else {
                                    eprintln!("无法获取 Session 锁以更新文本");
                                }
                            }
                        } else if v.get("status").and_then(|x| x.as_str()) == Some("final_result") {
                            let raw = v.get("raw_text").and_then(|x| x.as_str()).unwrap_or("");
                            let refined = v
                                .get("refined_text")
                                .and_then(|x| x.as_str())
                                .unwrap_or(raw);
                            println!("收到最终结果: Raw={}, Refined={}", raw, refined);

                            // Update session text
                            match session_shared_for_read.lock() {
                                Ok(mut session) => match &session.current_id {
                                    Some(id) => {
                                        println!("[final_result] current_id present: {}", id);
                                        session.raw_text = raw.to_string();
                                        session.refined_text = refined.to_string();
                                    }
                                    None => {
                                        println!("[final_result] WARNING: current_id is None, skip updating session text");
                                    }
                                },
                                Err(e) => {
                                    eprintln!("[final_result] ERROR: failed to lock session_shared_for_read: {}", e);
                                }
                            }
                            // Finalize session (write JSON)
                            if let Err(e) = finalize_session(session_shared_for_read.clone()) {
                                eprintln!("Finalize session failed: {}", e);
                            }

                            println!("输出结果：{}", refined);
                            if let Err(e) = inject_text_unicode_internal(&refined) {
                                eprintln!("注入失败: {}", e);
                            }

                            // 使用增量方式更新聚合统计
                            match session_shared_for_read.lock() {
                                Ok(session) => {
                                    match &session.current_id {
                                        Some(sid) => {
                                            println!("[stats] will update for session_id={}", sid);
                                            let json_filename = format!("{}.json", sid);
                                            let audio_filename = format!("{}.wav", sid);
                                            let created_at = session
                                                .start_time
                                                .map(|t| t.to_rfc3339())
                                                .unwrap_or_default();
                                            let item = TranscriptItem {
                                                session_id: sid.clone(),
                                                // 这里克隆一份，保留 created_at 供后续 speech-event 使用
                                                created_at: created_at.clone(),
                                                duration_ms: session.duration_ms,
                                                raw_text: session.raw_text.clone(),
                                                refined_text: session.refined_text.clone(),
                                                raw_text_count: session.raw_text.chars().count(),
                                                refined_text_count: session
                                                    .refined_text
                                                    .chars()
                                                    .count(),
                                                audio_filename,
                                                json_filename,
                                            };
                                            let today_key =
                                                chrono::Local::now().date_naive().to_string();

                                            println!("[stats] entering update block");
                                            match stats_shared_for_read.lock() {
                                                Ok(mut agg) => {
                                                    println!(
                                                        "[stats] before apply: total_words={}, time_saved_seconds={}, wpm={}, today_words={}",
                                                        agg.total_words, agg.time_saved_seconds, agg.wpm, agg.today_words
                                                    );
                                                    apply_session_increment(
                                                        &mut agg, &item, &today_key,
                                                    );
                                                    // 将最新统计推送给前端
                                                    let _ = app_handle_for_read.emit(
                                                        "stats-updated",
                                                        serde_json::json!({
                                                            "totalWords": agg.total_words,
                                                            "timeSavedSeconds": agg.time_saved_seconds,
                                                            "wpm": agg.wpm,
                                                            "todayWords": agg.today_words,
                                                        }),
                                                    );
                                                    // 将最终识别结果广播给前端，驱动 recognition.js 中的 final 流程
                                                    let _ = app_handle_for_read.emit(
                                                        "speech-event",
                                                        serde_json::json!({
                                                            "event": "final",
                                                            "raw": raw,
                                                            "processed": refined,
                                                            "duration_ms": session.duration_ms,
                                                            "ts": created_at,
                                                        }),
                                                    );

                                                    // 更新 toast 状态为"优化完成"
                                                    let _ = app_handle_for_read.emit_to("toast", "toast-state-update", serde_json::json!({
                                                        "status": "优化完成，已注入文本",
                                                        "indicator": "processing",
                                                        "text": refined,
                                                        "mode": "完成"
                                                    }));

                                                    // 1.5 秒后自动隐藏 toast 窗口
                                                    let toast_win = app_handle_for_read.get_webview_window("toast");
                                                    if let Some(toast_win) = toast_win {
                                                        let toast_win_clone = toast_win.clone();
                                                        tauri::async_runtime::spawn(async move {
                                                            sleep(std::time::Duration::from_millis(1500)).await;
                                                            let _ = toast_win_clone.hide();
                                                        });
                                                    }
                                                    println!(
                                                        "[stats] after apply: total_words={}, time_saved_seconds={}, wpm={}, today_words={}",
                                                        agg.total_words, agg.time_saved_seconds, agg.wpm, agg.today_words
                                                    );
                                                }
                                                Err(e) => {
                                                    eprintln!("[stats] ERROR: stats_shared_for_read.lock() failed: {}", e);
                                                }
                                            }
                                        }
                                        None => {
                                            println!("[stats] WARNING: current_id is None in final_result, skip stats update");
                                        }
                                    }
                                }
                                Err(e) => {
                                    eprintln!("[stats] ERROR: failed to lock session_shared_for_read in stats block: {}", e);
                                }
                            }
                        }
                    }
                }
                Ok(Message::Close(_)) => {
                    println!("连接关闭");
                    break;
                }
                Err(e) => {
                    eprintln!("读取失败: {}", e);
                    break;
                }
                _ => {}
            }
        }
        if let Ok(mut g) = shared_arc_for_read.lock() {
            g.connected = false;
            g.sender = None;
            g.url = None;
        }
    });

    Ok(())
}
