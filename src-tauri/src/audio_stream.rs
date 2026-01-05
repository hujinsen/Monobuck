use crate::session::{SessionMetadata, SessionState};
use crate::websocket::WebSocketState;
use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};
use std::fs::File;
use std::io::BufWriter;
use std::sync::{Arc, Mutex};

pub struct AudioState {
    pub active: bool,
    pub stream: Option<cpal::Stream>,
    pub writer: Option<hound::WavWriter<BufWriter<File>>>,
    pub sample_count: u64,
    pub preferred_input: Option<String>,
}

unsafe impl Send for AudioState {}
unsafe impl Sync for AudioState {}

impl AudioState {
    pub fn new() -> Self {
        Self {
            active: false,
            stream: None,
            writer: None,
            sample_count: 0,
            preferred_input: None,
        }
    }
}

pub struct AudioShared {
    pub inner: Arc<Mutex<AudioState>>,
}

#[derive(serde::Serialize, Clone)]
pub struct InputDevicesInfo {
    /// 所有可用输入设备名称（去重）
    pub devices: Vec<String>,
    /// 系统默认输入设备名称（若存在）
    pub default: Option<String>,
    /// 用户在设置中选择的首选设备名称（若存在）
    pub preferred: Option<String>,
}

/// 列举当前系统可用的输入设备列表，供前端设置面板使用。
///
/// 说明：
/// - 仅使用 Rust / cpal 枚举真实设备，不依赖浏览器的 mediaDevices；
/// - 若 `preferred_input` 存在，前端可优先选中该设备；
/// - 若没有任何设备，将返回空 devices 列表，交由前端展示提示文案。
pub fn list_input_devices(
    audio_shared: Arc<Mutex<AudioState>>,
) -> Result<InputDevicesInfo, String> {
    let host = cpal::default_host();

    let default_name = host
        .default_input_device()
        .ok_or_else(|| "找不到默认输入设备".to_string())
        .and_then(|d| {
            d.name()
                .map_err(|e| format!("获取默认输入设备名称失败: {e}"))
        })
        .ok();

    let mut names: Vec<String> = Vec::new();
    if let Ok(devices) = host.input_devices() {
        for dev in devices {
            if let Ok(name) = dev.name() {
                if !name.is_empty() {
                    // 不再按名称去重，避免系统中存在名称相同但实际不同的麦克风设备
                    names.push(name);
                }
            }
        }
    }

    let preferred = {
        let guard = audio_shared
            .lock()
            .map_err(|_| "audio state poisoned".to_string())?;
        guard.preferred_input.clone()
    };

    Ok(InputDevicesInfo {
        devices: names,
        default: default_name,
        preferred,
    })
}

pub fn start_audio(
    audio_shared: Arc<Mutex<AudioState>>,
    ws_shared: Arc<Mutex<WebSocketState>>,
    session_shared: Arc<Mutex<SessionState>>,
) -> Result<(), String> {
    {
        let g = audio_shared.lock().map_err(|_| "audio state poisoned")?;
        if g.active {
            return Ok(());
        }
    }

    // Initialize Session
    let now = chrono::Local::now();
    let session_id = now.format("%Y%m%d_%H%M%S_%3f").to_string();
    let audio_filename = format!("{}.wav", session_id);

    {
        let mut session = session_shared
            .lock()
            .map_err(|_| "session state poisoned")?;
        session.current_id = Some(session_id.clone());
        session.start_time = Some(now);
        session.raw_text.clear();
        session.refined_text.clear();

        // Create WavWriter
        let audio_path = session.base_dir.join("audio").join(&audio_filename);
        let spec = hound::WavSpec {
            channels: 1,
            sample_rate: 16000,
            bits_per_sample: 16,
            sample_format: hound::SampleFormat::Int,
        };
        let writer = hound::WavWriter::create(audio_path, spec)
            .map_err(|e| format!("创建音频文件失败: {}", e))?;

        let mut g = audio_shared.lock().map_err(|_| "audio state poisoned")?;
        g.writer = Some(writer);
        g.sample_count = 0;
    }

    let host = cpal::default_host();

    // 读取首选设备名称（若有），优先尝试匹配该设备
    let preferred_name = {
        let g = audio_shared.lock().map_err(|_| "audio state poisoned")?;
        g.preferred_input.clone()
    };

    let device = if let Some(target) = preferred_name {
        match host.input_devices() {
            Ok(devices) => {
                let mut chosen: Option<cpal::Device> = None;
                for dev in devices {
                    let name = dev.name().unwrap_or_default();
                    if name == target {
                        chosen = Some(dev);
                        break;
                    }
                }
                chosen
                    .or_else(|| host.default_input_device())
                    .ok_or("找不到输入设备")?
            }
            Err(_) => host.default_input_device().ok_or("找不到输入设备")?,
        }
    } else {
        host.default_input_device().ok_or("找不到默认输入设备")?
    };

    println!("使用音频输入设备: {}", device.name().unwrap_or_default());

    let config = device
        .default_input_config()
        .map_err(|e| format!("获取输入配置失败: {e}"))?;
    let sample_rate_in = config.sample_rate().0 as f32;
    let channels_in = config.channels() as usize;

    let state_arc = audio_shared.clone();
    let ws_arc = ws_shared.clone();
    let mut downsample_acc: f32 = 0.0;
    let ratio = sample_rate_in / 16000.0;
    let frame_target = 320;
    let mut frame_buffer: Vec<i16> = Vec::with_capacity(frame_target);

    let err_fn = |e| eprintln!("音频输入错误: {e}");

    let stream = match config.sample_format() {
        cpal::SampleFormat::F32 => device.build_input_stream(
            &config.into(),
            move |data: &[f32], _: &cpal::InputCallbackInfo| {
                callback_common(
                    data,
                    channels_in,
                    ratio,
                    &mut downsample_acc,
                    &mut frame_buffer,
                    frame_target,
                    state_arc.clone(),
                    ws_arc.clone(),
                );
            },
            err_fn,
            None,
        ),
        cpal::SampleFormat::I16 => device.build_input_stream(
            &config.into(),
            move |data: &[i16], _: &cpal::InputCallbackInfo| {
                let mut float_buf: Vec<f32> = Vec::with_capacity(data.len());
                for s in data {
                    float_buf.push(*s as f32 / 32768.0);
                }
                callback_common(
                    &float_buf,
                    channels_in,
                    ratio,
                    &mut downsample_acc,
                    &mut frame_buffer,
                    frame_target,
                    state_arc.clone(),
                    ws_arc.clone(),
                );
            },
            err_fn,
            None,
        ),
        _ => return Err("未支持的采样格式".into()),
    }
    .map_err(|e| format!("构建音频流失败: {e}"))?;

    stream.play().map_err(|e| format!("启动音频流失败: {e}"))?;
    {
        let mut g = audio_shared.lock().map_err(|_| "audio state poisoned")?;
        g.active = true;
        g.stream = Some(stream);
    }
    Ok(())
}

fn callback_common(
    data: &[f32],
    channels: usize,
    ratio: f32,
    downsample_acc: &mut f32,
    frame_buffer: &mut Vec<i16>,
    frame_target: usize,
    state_arc: Arc<Mutex<AudioState>>,
    ws_arc: Arc<Mutex<WebSocketState>>,
) {
    if let Ok(s) = state_arc.lock() {
        if !s.active {
            return;
        }
    }
    let mut idx = 0;
    while idx < data.len() {
        let sample = data[idx];
        if ratio > 1.0 {
            *downsample_acc += 1.0;
            if *downsample_acc < ratio {
                idx += channels;
                continue;
            }
            *downsample_acc -= ratio;
        }
        let mut v = (sample * 32767.0).round() as i16;
        // 钳制范围，防止溢出
        if v > 32767 {
            v = 32767;
        } else if v < -32768 {
            v = -32768;
        }
        frame_buffer.push(v);
        if frame_buffer.len() >= frame_target {
            // 直接调用 ws_send_raw_internal，它内部会加锁，避免在此处加锁导致死锁
            let bytes: &[u8] = unsafe {
                std::slice::from_raw_parts(
                    frame_buffer.as_ptr() as *const u8,
                    frame_buffer.len() * 2,
                )
            };
            let _ = crate::websocket::ws_send_raw_internal(&ws_arc, bytes);

            // Write to WAV file
            if let Ok(mut g) = state_arc.lock() {
                if let Some(writer) = &mut g.writer {
                    for s in frame_buffer.iter() {
                        writer.write_sample(*s).ok();
                    }
                    g.sample_count += frame_buffer.len() as u64;
                }
            }

            frame_buffer.clear();
        }
        idx += channels;
    }
}

pub fn stop_audio(
    audio_shared: Arc<Mutex<AudioState>>,
    session_shared: Arc<Mutex<SessionState>>,
) -> Result<(), String> {
    let mut g = audio_shared.lock().map_err(|_| "audio state poisoned")?;
    if !g.active {
        return Ok(());
    }
    g.active = false;
    g.stream = None;

    // Finalize WAV
    if let Some(_writer) = g.writer.take() {
        let duration_ms = (g.sample_count as f64 / 16.0) as u64; // 16000 Hz -> 16 samples per ms

        // Update duration in session but DO NOT finalize JSON yet.
        // Wait for 'final_result' from Python via WebSocket.
        if let Ok(mut session) = session_shared.lock() {
            session.duration_ms = duration_ms;
        }
    }
    Ok(())
}

pub fn finalize_session(session_shared: Arc<Mutex<SessionState>>) -> Result<(), String> {
    if let Ok(mut session) = session_shared.lock() {
        if let Some(sid) = &session.current_id {
            println!(
                "Finalizing Session: ID={}, RawTextLen={}, RefinedTextLen={}",
                sid,
                session.raw_text.len(),
                session.refined_text.len()
            );

            let json_filename = format!("{}.json", sid);
            let audio_filename = format!("{}.wav", sid);

            let meta = SessionMetadata {
                session_id: sid.clone(),
                created_at: session
                    .start_time
                    .map(|t| t.to_rfc3339())
                    .unwrap_or_default(),
                duration_ms: session.duration_ms,
                raw_text: session.raw_text.clone(),
                refined_text: session.refined_text.clone(),
                raw_text_count: session.raw_text.chars().count(),
                refined_text_count: session.refined_text.chars().count(),
                audio_filename,
                json_filename: json_filename.clone(),
            };

            let json_path = session.base_dir.join("sessions").join(&json_filename);
            if let Ok(file) = File::create(json_path) {
                let _ = serde_json::to_writer_pretty(file, &meta);
            }
        }
        // Reset session

        session.duration_ms = 0;
    }
    Ok(())
}
