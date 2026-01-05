use crate::session::TranscriptItem;
use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize, Deserialize, Clone, Default)]
pub struct StatsAggregate {
    pub total_words: u64,
    pub time_saved_seconds: u64,
    pub wpm: f64,
    pub today_words: u64,
    #[serde(skip)]
    pub total_duration_ms: u64,
}

/// 从完整会话列表计算一次全量统计（应用启动或全量刷新时使用）
pub fn compute_stats_full(items: &[TranscriptItem]) -> StatsAggregate {
    if items.is_empty() {
        return StatsAggregate::default();
    }
    let mut agg = StatsAggregate::default();
    let today_key = chrono::Local::now().date_naive().to_string();
    for s in items {
        apply_session_increment(&mut agg, s, &today_key);
    }
    agg
}

/// 基于单条 Session 做增量更新（识别结束时调用）
pub fn apply_session_increment(agg: &mut StatsAggregate, item: &TranscriptItem, today_key: &str) {
    let text = if !item.refined_text.is_empty() {
        &item.refined_text
    } else {
        &item.raw_text
    };
    let chars = text.chars().count() as u64;
    let dur_ms = item.duration_ms;

    agg.total_words += chars;
    agg.time_saved_seconds += (chars as f64 * 0.5).round() as u64;
    agg.total_duration_ms += dur_ms;

    if agg.total_duration_ms > 0 {
        let avg_wpm = agg.total_words as f64
            / (agg.total_duration_ms as f64 / 1000.0 / 60.0);
        agg.wpm = (avg_wpm * 10.0).round() / 10.0;
    }

    if let Ok(dt) = chrono::DateTime::parse_from_rfc3339(&item.created_at) {
        let d = dt.with_timezone(&chrono::Local).date_naive().to_string();
        if d == today_key {
            agg.today_words += chars;
        }
    }
}
