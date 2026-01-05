use rdev::{Event, EventType, Key};
use std::sync::{Arc, Mutex};
use std::time::Instant;
use tauri::Emitter;

// 启动一个后台线程监听全局键盘事件（使用 rdev 支持纯修饰键模式）
// 需求：
// Windows / Linux:
//   1) Ctrl + Win 组合 -> 开始识别 (combo)
//   2) 双击 Ctrl -> 开始识别 (double-ctrl)
//   3) （识别中）单击 Ctrl -> 结束识别 (single-ctrl)
// macOS:
//   1) Ctrl + Command -> 开始识别 (combo)
//   2) 双击 Option    -> 开始识别 (double-opt)
//   3) （识别中）单击 Option -> 结束识别 (single-opt)
// 说明：rdev 监听可能在 macOS 需要“辅助功能”权限。

#[derive(Debug, Clone)]
pub struct CustomShortcut {
    pub ctrl: bool,
    pub alt: bool,
    pub shift: bool,
    pub meta: bool,
    pub main: Option<rdev::Key>,
    pub display: String,
}

#[derive(Debug)]
pub struct HotkeyState {
    active: bool,
    activation_mode: Option<String>, // 记录当前激活模式："combo" 或 "double-ctrl"
    last_ctrl_time: Option<std::time::Instant>,
    ctrl_down: bool,
    win_down: bool,
    cmd_down: bool,
    opt_down: bool,
    shift_down: bool,
    custom: Option<CustomShortcut>,
}

#[derive(Clone)]
pub struct Shared {
    pub inner: Arc<Mutex<HotkeyState>>,
}

// === 自定义快捷键命令 ===
#[tauri::command]
pub fn set_custom_shortcut(
    accelerator: &str,
    state: tauri::State<'_, Shared>,
) -> Result<(), String> {
    let parsed = parse_custom_accelerator(accelerator)?;
    let mut guard = state
        .inner
        .lock()
        .map_err(|_| "state poisoned".to_string())?;
    guard.custom = Some(parsed);
    Ok(())
}

#[tauri::command]
pub fn clear_custom_shortcut(state: tauri::State<'_, Shared>) -> Result<(), String> {
    let mut guard = state
        .inner
        .lock()
        .map_err(|_| "state poisoned".to_string())?;
    guard.custom = None;
    Ok(())
}

/**
 * 解析字符串形式的快捷键描述，将其转换为CustomShortcut结构体
 *
 * # 参数
 * - `accel`: 字符串形式的快捷键描述，使用加号(+)分隔多个键，例如 "Ctrl+Shift+A", "Alt+F4", "Space"
 *
 * # 返回值
 * - `Ok(CustomShortcut)`: 成功解析的快捷键配置
 * - `Err(String)`: 解析失败时返回错误信息
 *
 * # 支持的键类型
 * - **修饰键**:
 *   - Ctrl/Control
 *   - Alt/Option
 *   - Shift
 *   - Win/Super/Meta/Command/Cmd
 * - **特殊键**:
 *   - Esc/Escape
 *   - Space/Spacebar
 * - **功能键**:
 *   - F1 到 F12
 * - **字母键**:
 *   - A 到 Z (大小写不敏感)
 *
 * # 错误情况
 * - 空字符串输入
 * - 无法识别的键名
 * - 不包含主键（必须包含至少一个字母键、功能键或特殊键）
 *
 * # 示例
 * ```
 * // 有效的快捷键格式
 * let shortcut1 = parse_custom_accelerator("Ctrl+Shift+A").unwrap();
 * let shortcut2 = parse_custom_accelerator("Alt+F4").unwrap();
 * let shortcut3 = parse_custom_accelerator("Space").unwrap();
 *
 * // 无效的快捷键格式
 * assert!(parse_custom_accelerator("").is_err());
 * assert!(parse_custom_accelerator("Ctrl+Alt").is_err()); // 缺少主键
 * assert!(parse_custom_accelerator("Ctrl+1").is_err());   // 数字键不支持
 * ```
 */
pub fn parse_custom_accelerator(accel: &str) -> Result<CustomShortcut, String> {
    use rdev::Key;
    let mut ctrl = false;
    let mut alt = false;
    let mut shift = false;
    let mut meta = false;
    let mut main: Option<rdev::Key> = None;
    let tokens: Vec<String> = accel
        .split('+')
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .collect();
    if tokens.is_empty() {
        return Err("空的快捷键".into());
    }
    for t in &tokens {
        let low = t.to_lowercase();
        match low.as_str() {
            "ctrl" | "control" => ctrl = true,
            "alt" | "option" => alt = true,
            "shift" => shift = true,
            "win" | "super" | "meta" | "command" | "cmd" => meta = true,
            "esc" | "escape" => main = Some(Key::Escape),
            "space" | "spacebar" => main = Some(Key::Space),
            other => {
                if other.starts_with('f') && other.len() <= 3 {
                    if let Ok(num) = other[1..].parse::<u8>() {
                        main = function_key(num);
                        continue;
                    }
                }
                if other.len() == 1 {
                    let ch = other.chars().next().unwrap().to_ascii_uppercase();
                    if ('A'..='Z').contains(&ch) {
                        main = letter_key(ch);
                        continue;
                    }
                }
                return Err(format!("无法解析键: {}", t));
            }
        }
    }
    if main.is_none() {
        return Err("需包含一个主键(字母/功能键/Space/Escape)".into());
    }
    Ok(CustomShortcut {
        ctrl,
        alt,
        shift,
        meta,
        main,
        display: accel.to_string(),
    })
}

pub fn letter_key(ch: char) -> Option<rdev::Key> {
    use rdev::Key::*;
    Some(match ch {
        'A' => KeyA,
        'B' => KeyB,
        'C' => KeyC,
        'D' => KeyD,
        'E' => KeyE,
        'F' => KeyF,
        'G' => KeyG,
        'H' => KeyH,
        'I' => KeyI,
        'J' => KeyJ,
        'K' => KeyK,
        'L' => KeyL,
        'M' => KeyM,
        'N' => KeyN,
        'O' => KeyO,
        'P' => KeyP,
        'Q' => KeyQ,
        'R' => KeyR,
        'S' => KeyS,
        'T' => KeyT,
        'U' => KeyU,
        'V' => KeyV,
        'W' => KeyW,
        'X' => KeyX,
        'Y' => KeyY,
        'Z' => KeyZ,
        _ => return None,
    })
}

pub fn function_key(n: u8) -> Option<rdev::Key> {
    use rdev::Key::*;
    Some(match n {
        1 => F1,
        2 => F2,
        3 => F3,
        4 => F4,
        5 => F5,
        6 => F6,
        7 => F7,
        8 => F8,
        9 => F9,
        10 => F10,
        11 => F11,
        12 => F12,
        _ => return None,
    })
}

// 初始化快捷键监听器的函数
pub fn init_hotkey_listener<R, E>(
    app_handle: &tauri::AppHandle,
    state: Arc<Mutex<HotkeyState>>,
    sidecar_sender_opt: Option<R>,
) where
    R: Fn(serde_json::Value) -> E + Clone + Send + 'static,
    E: std::fmt::Debug,
{
    const DOUBLE_MS: u128 = 380; // 双击间隔
    let app_handle_clone = app_handle.clone();
    let state_thread = state.clone();

    std::thread::spawn(move || {
        let handle = app_handle_clone;

        // 辅助函数：发事件
        let handle_for_emit = handle.clone();
        let sender_opt = sidecar_sender_opt.clone();
        let emit = move |ty: &str, trigger: &str, mode: &str| {
            let _ = handle_for_emit.emit(
                "recognition-event",
                serde_json::json!({
                    "type": ty,
                    "trigger": trigger,
                    "mode": mode
                }),
            );
            // 将 start/stop 映射到 python sidecar
            if let Some(sender) = sender_opt.clone() {
                match ty {
                    "start" => {
                        // 调试事件：即将发送 start
                        let _ = handle_for_emit.emit(
                            "speech-event",
                            serde_json::json!({"event":"debug","stage":"emit-start-cmd"}),
                        );
                        sender(serde_json::json!({"cmd": "start"}));
                    }
                    "stop" => {
                        let _ = handle_for_emit.emit(
                            "speech-event",
                            serde_json::json!({"event":"debug","stage":"emit-stop-cmd"}),
                        );
                        sender(serde_json::json!({"cmd": "stop"}));
                    }
                    _ => {}
                }
            }
        };

        // 额外克隆一个 handle 供按键调试使用
        let debug_handle = handle.clone();

        let result = rdev::listen(move |event: Event| {
            let mut s = state_thread.lock().ok().unwrap();

            // 基础按键调试：输出键盘事件
            let dbg_key = match event.event_type {
                EventType::KeyPress(k) => Some(format!("press:{:?}", k)),
                EventType::KeyRelease(k) => Some(format!("release:{:?}", k)),
                _ => None,
            };
            if let Some(dbg) = dbg_key {
                let _ = debug_handle.emit(
                    "speech-event",
                    serde_json::json!({"event": "debug", "stage": "key", "detail": dbg}),
                );
            }

            match event.event_type {
                EventType::KeyPress(key) => {
                    // 优先处理自定义快捷键
                    if let Some(custom) = s.custom.clone() {
                        // 更新修饰键状态
                        match key {
                            rdev::Key::ControlLeft | rdev::Key::ControlRight => s.ctrl_down = true,
                            rdev::Key::MetaLeft | rdev::Key::MetaRight => {
                                s.win_down = true;
                                s.cmd_down = true;
                            }
                            rdev::Key::Alt => s.opt_down = true,
                            rdev::Key::ShiftLeft | rdev::Key::ShiftRight => s.shift_down = true,
                            _ => {}
                        }
                        if Some(key) == custom.main {
                            // 主键按下时检查修饰键
                            let modifiers_ok = (!custom.ctrl || s.ctrl_down)
                                && (!custom.alt || s.opt_down)
                                && (!custom.shift || s.shift_down)
                                && (!custom.meta || s.win_down || s.cmd_down);
                            if modifiers_ok {
                                if !s.active {
                                    emit("start", &custom.display, "custom");
                                    s.active = true;
                                } else {
                                    emit("stop", &custom.display, "custom");
                                    s.active = false;
                                }
                            }
                        }
                        return; // 自定义路径结束
                    }

                    #[cfg(any(target_os = "windows", target_os = "linux"))]
                    {
                        match key {
                            Key::ControlLeft | Key::ControlRight => {
                                // 忽略自动重复按键 (auto-repeat)，防止长按导致反复触发停止
                                if s.ctrl_down {
                                    return;
                                }
                                let now = Instant::now();
                                // 单击 Ctrl 在 active=true 时 -> 停止
                                if s.active {
                                    // 防止重复：只在按下瞬间处理
                                    emit("stop", "Control", "single-ctrl");
                                    s.active = false;
                                    s.last_ctrl_time = None;
                                    s.activation_mode = None;
                                } else {
                                    // 还未激活 -> 进行双击判定
                                    if let Some(prev) = s.last_ctrl_time {
                                        if now.duration_since(prev).as_millis() <= DOUBLE_MS {
                                            emit("start", "Control", "double-ctrl");
                                            s.active = true;
                                            s.activation_mode = Some("double-ctrl".to_string());
                                            let _ = debug_handle.emit(
                                                "speech-event",
                                                serde_json::json!({"event": "debug", "stage": "double-ctrl-detected"})
                                            );
                                            s.last_ctrl_time = None; // 重置
                                        } else {
                                            s.last_ctrl_time = Some(now);
                                        }
                                    } else {
                                        s.last_ctrl_time = Some(now);
                                    }
                                }
                                s.ctrl_down = true;
                            }
                            Key::MetaLeft | Key::MetaRight => {
                                // Windows 键 / Super 键
                                s.win_down = true;
                                if s.ctrl_down && !s.active {
                                    // ctrl 已按下且未激活 -> 组合启动
                                    emit("start", "Control+Super", "combo");
                                    s.active = true;
                                    s.activation_mode = Some("combo".to_string());
                                    let _ = debug_handle.emit(
                                        "speech-event",
                                        serde_json::json!({"event": "debug", "stage": "combo-ctrl-super"})
                                    );
                                    s.last_ctrl_time = None; // 清除单击节奏
                                }
                            }
                            Key::Alt => {
                                s.opt_down = true;
                            }
                            Key::ShiftLeft | Key::ShiftRight => {
                                s.shift_down = true;
                            }
                            _ => {}
                        }
                    }

                    #[cfg(target_os = "macos")]
                    {
                        match key {
                            Key::ControlLeft | Key::ControlRight => {
                                s.ctrl_down = true;
                                if s.cmd_down && !s.active {
                                    // Ctrl+Command 组合
                                    emit("start", "Control+Command", "combo");
                                    s.active = true;
                                    s.last_opt_time = None;
                                }
                            }
                            Key::MetaLeft | Key::MetaRight => {
                                // Command 键
                                s.cmd_down = true;
                                if s.ctrl_down && !s.active {
                                    emit("start", "Control+Command", "combo");
                                    s.active = true;
                                    s.last_opt_time = None;
                                }
                            }
                            Key::Alt => {
                                // Option 键
                                if s.opt_down {
                                    return;
                                }
                                let now = Instant::now();
                                if s.active {
                                    emit("stop", "Option", "single-opt");
                                    s.active = false;
                                    s.last_opt_time = None;
                                } else {
                                    if let Some(prev) = s.last_opt_time {
                                        if now.duration_since(prev).as_millis() <= DOUBLE_MS {
                                            emit("start", "Option", "double-opt");
                                            s.active = true;
                                            s.last_opt_time = None;
                                        } else {
                                            s.last_opt_time = Some(now);
                                        }
                                    } else {
                                        s.last_opt_time = Some(now);
                                    }
                                }
                                s.opt_down = true;
                            }
                            Key::ShiftLeft | Key::ShiftRight => {
                                s.shift_down = true;
                            }
                            _ => {}
                        }
                    }
                }

                EventType::KeyRelease(key) => {
                    #[cfg(any(target_os = "windows", target_os = "linux"))]
                    {
                        match key {
                            Key::ControlLeft | Key::ControlRight => {
                                s.ctrl_down = false;
                                // 当Ctrl键释放且当前处于活动状态时，只在combo模式下停止识别
                                // 双击Ctrl模式下不自动停止
                                if s.active && s.activation_mode.as_deref() == Some("combo") {
                                    emit("stop", "Control", "combo-release");
                                    s.active = false;
                                    s.activation_mode = None;
                                }
                            }
                            Key::MetaLeft | Key::MetaRight => {
                                s.win_down = false;
                                // 当Win键释放且当前处于活动状态时，只在combo模式下停止识别
                                // 双击Ctrl模式下不自动停止
                                if s.active && s.activation_mode.as_deref() == Some("combo") {
                                    emit("stop", "Super", "combo-release");
                                    s.active = false;
                                    s.activation_mode = None;
                                }
                            }
                            Key::Alt => {
                                s.opt_down = false;
                            }
                            Key::ShiftLeft | Key::ShiftRight => {
                                s.shift_down = false;
                            }
                            _ => {}
                        }
                    }

                    #[cfg(target_os = "macos")]
                    {
                        match key {
                            Key::ControlLeft | Key::ControlRight => {
                                s.ctrl_down = false;
                            }
                            Key::MetaLeft | Key::MetaRight => {
                                s.cmd_down = false;
                            }
                            Key::Alt => {
                                s.opt_down = false;
                            }
                            Key::ShiftLeft | Key::ShiftRight => {
                                s.shift_down = false;
                            }
                            _ => {}
                        }
                    }
                }

                _ => {}
            }
        });

        if let Err(e) = result {
            // 监听失败
            let _ = handle.emit(
                "recognition-event",
                serde_json::json!({
                    "type": "error",
                    "trigger": "listener",
                    "mode": "rdev",
                    "error": format!("{:?}", e)
                }),
            );
        }
    });
}

// 创建默认的HotkeyState
pub fn create_default_hotkey_state() -> HotkeyState {
    HotkeyState {
        active: false,
        activation_mode: None,
        last_ctrl_time: None,
        ctrl_down: false,
        win_down: false,
        cmd_down: false,
        opt_down: false,
        shift_down: false,
        custom: None,
    }
}
