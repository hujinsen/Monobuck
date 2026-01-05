#[cfg(target_os = "windows")]
use windows::Win32::UI::Input::KeyboardAndMouse::{
    SendInput, INPUT, INPUT_0, INPUT_KEYBOARD, KEYBDINPUT, KEYEVENTF_KEYUP, KEYEVENTF_UNICODE,
    VIRTUAL_KEY,
};

// 公开给 websocket 内部调用的函数
pub fn inject_text_unicode_internal(text: &str) -> Result<(), String> {
    #[cfg(target_os = "windows")]
    {
        let units: Vec<u16> = text.encode_utf16().collect();
        // 逐个字符发送，避免一次性发送导致乱序
        for u in units {
            let mut inputs: Vec<INPUT> = Vec::with_capacity(2);
            inputs.push(INPUT {
                r#type: INPUT_KEYBOARD,
                Anonymous: INPUT_0 {
                    ki: KEYBDINPUT {
                        wVk: VIRTUAL_KEY(0),
                        wScan: u,
                        dwFlags: KEYEVENTF_UNICODE,
                        time: 0,
                        dwExtraInfo: 0,
                    },
                },
            });
            inputs.push(INPUT {
                r#type: INPUT_KEYBOARD,
                Anonymous: INPUT_0 {
                    ki: KEYBDINPUT {
                        wVk: VIRTUAL_KEY(0),
                        wScan: u,
                        dwFlags: KEYEVENTF_UNICODE | KEYEVENTF_KEYUP,
                        time: 0,
                        dwExtraInfo: 0,
                    },
                },
            });

            let sent = unsafe { SendInput(&inputs, std::mem::size_of::<INPUT>() as i32) } as usize;
            if sent != inputs.len() {
                return Err(format!(
                    "SendInput 单字符发送失败: {sent}/{len}",
                    len = inputs.len()
                ));
            }
            // 微小延迟，确保目标程序按顺序处理
            std::thread::sleep(std::time::Duration::from_millis(10));
        }
        Ok(())
    }
    #[cfg(not(target_os = "windows"))]
    {
        Err("当前平台未实现文本注入".into())
    }
}

#[tauri::command]
pub fn inject_text_unicode(text: String) -> Result<(), String> {
    inject_text_unicode_internal(&text)
}
