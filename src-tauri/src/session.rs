use serde::{Deserialize, Serialize};
use std::fs;
use std::path::PathBuf;
use std::sync::{Arc, Mutex};

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct SessionMetadata {
    pub session_id: String,
    pub created_at: String,
    pub duration_ms: u64,
    pub raw_text: String,
    pub refined_text: String,
    pub raw_text_count: usize,
    pub refined_text_count: usize,
    pub audio_filename: String,
    pub json_filename: String,
}

pub struct SessionState {
    pub current_id: Option<String>,
    pub start_time: Option<chrono::DateTime<chrono::Local>>,
    pub raw_text: String,
    pub refined_text: String,
    pub base_dir: PathBuf,
    pub duration_ms: u64,
}

impl SessionState {
    pub fn new(base_dir: PathBuf) -> Self {
        // Ensure directories exist
        let audio_dir = base_dir.join("audio");
        let sessions_dir = base_dir.join("sessions");
        std::fs::create_dir_all(&audio_dir).expect("failed to create audio dir");
        std::fs::create_dir_all(&sessions_dir).expect("failed to create sessions dir");

        Self {
            current_id: None,
            start_time: None,
            raw_text: String::new(),
            refined_text: String::new(),
            base_dir,
            duration_ms: 0,
        }
    }
}

pub struct SessionShared {
    pub inner: Arc<Mutex<SessionState>>,
}

/// 简单的数据结构，供前端展示“最近转录记录”使用
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct RecentSessionItem {
    pub session_id: String,
    pub created_at: String,
    pub duration_ms: u64,
    pub refined_text: String,
    pub json_filename: String,
}

/// 完整转录记录结构，供“转录”页面使用
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct TranscriptItem {
    pub session_id: String,
    pub created_at: String,
    pub duration_ms: u64,
    pub raw_text: String,
    pub refined_text: String,
    pub raw_text_count: usize,
    pub refined_text_count: usize,
    pub audio_filename: String,
    pub json_filename: String,
}

/// 从指定 base_dir 读取 `sessions` 目录下的最近 N 条会话元数据。
/// 这里直接按文件名倒序（文件名中已经包含时间戳）。
pub fn read_recent_sessions(base_dir: &PathBuf, limit: usize) -> Vec<RecentSessionItem> {
    let sessions_dir = base_dir.join("sessions");
    let mut entries: Vec<_> = match fs::read_dir(&sessions_dir) {
        Ok(read_dir) => read_dir
            .filter_map(|e| e.ok())
            .filter(|e| e.path().extension().and_then(|s| s.to_str()) == Some("json"))
            .collect(),
        Err(_) => return Vec::new(),
    };

    // 文件名形如 20251208_221321_064.json，按名字倒序即可近似“最近”
    entries.sort_by_key(|e| e.file_name());
    entries.reverse();

    let mut result = Vec::new();
    for entry in entries.into_iter().take(limit) {
        let path = entry.path();
        let file_name = match path.file_name().and_then(|s| s.to_str()) {
            Some(s) => s.to_string(),
            None => continue,
        };
        let content = match fs::read_to_string(&path) {
            Ok(c) => c,
            Err(_) => continue,
        };
        let meta: Result<SessionMetadata, _> = serde_json::from_str(&content);
        if let Ok(m) = meta {
            result.push(RecentSessionItem {
                session_id: m.session_id,
                created_at: m.created_at,
                duration_ms: m.duration_ms,
                refined_text: m.refined_text,
                json_filename: file_name,
            });
        }
    }

    result
}

/// 读取所有会话记录，按文件名倒序（最新在前）返回
pub fn read_all_sessions(base_dir: &PathBuf) -> Vec<TranscriptItem> {
    let sessions_dir = base_dir.join("sessions");
    let mut entries: Vec<_> = match fs::read_dir(&sessions_dir) {
        Ok(read_dir) => read_dir
            .filter_map(|e| e.ok())
            .filter(|e| e.path().extension().and_then(|s| s.to_str()) == Some("json"))
            .collect(),
        Err(_) => return Vec::new(),
    };

    entries.sort_by_key(|e| e.file_name());
    entries.reverse();

    let mut result = Vec::new();
    for entry in entries.into_iter() {
        let path = entry.path();
        let file_name = match path.file_name().and_then(|s| s.to_str()) {
            Some(s) => s.to_string(),
            None => continue,
        };
        let content = match fs::read_to_string(&path) {
            Ok(c) => c,
            Err(_) => continue,
        };
        let meta: Result<SessionMetadata, _> = serde_json::from_str(&content);
        if let Ok(m) = meta {
            result.push(TranscriptItem {
                session_id: m.session_id,
                created_at: m.created_at,
                duration_ms: m.duration_ms,
                raw_text: m.raw_text,
                refined_text: m.refined_text,
                raw_text_count: m.raw_text_count,
                refined_text_count: m.refined_text_count,
                audio_filename: m.audio_filename,
                json_filename: file_name,
            });
        }
    }

    result
}
