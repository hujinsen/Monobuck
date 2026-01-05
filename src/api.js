/**
 * Monobuck2 前端统一 API 抽象层
 * -------------------------------------------------
 * 目标：
 *  1. 抽象 Tauri invoke / HTTP fetch / 本地 mock 的访问差异
 *  2. 在早期（后端尚未实现）提供稳定函数签名（带 JSDoc 类型提示）
 *  3. 中央化 streak 阈值与里程碑计算逻辑，便于后端实现时比对
 *  4. 后续替换真实端点或数据层时，不需要修改业务调用方
 *
 * 说明：当前 Rust 端仅有 `greet` 命令。下面每个 API 会依次尝试：
 *  1. Tauri invoke（未来需要你在 Rust 中补齐的命令）
 *  2. HTTP fetch（如将来接入本地/嵌入式 HTTP 服务）
 *  3. 本地 mock（必要时写入 localStorage 以保持会话状态）
 *
 * 推荐后端命令签名（计划）：
 *  - get_streak() -> { currentStreak, bestStreak, todayActive, milestone{tier,name,nextTierIn}, lastActiveDate }
 *  - log_activity(words: u32, duration_sec: u32, finished_at: i64) -> { streak }
 *  - get_stats() -> { totalWords, timeSavedSeconds, wpm }
 *  - list_transcripts(offset: u32, limit: u32, search?: String) -> { items, total }
 */

const TAURI_INVOKE = () => window.__TAURI__?.core?.invoke;
const isTauri = () => typeof TAURI_INVOKE() === 'function';

// ---- 通用工具 --------------------------------------------------------------
async function tryInvoke(command, payload) {
    if (!isTauri()) throw new Error('not-tauri');
    return await TAURI_INVOKE()(command, payload || {});
}

async function tryFetchJSON(url, opts) {
    const res = await fetch(url, opts);
    if (!res.ok) throw new Error('HTTP ' + res.status);
    return res.json();
}

function todayUTC() {
    return new Date().toISOString().slice(0, 10); // YYYY-MM-DD
}

// ---- Streak Mock 逻辑（与文档保持一致） -----------------------------------
const STREAK_KEY = 'mock.streak.state';

/**
 * 从 localStorage 读取 streak 状态（仅 mock 模式使用）
 * 结构: { currentStreak, bestStreak, lastActiveDate, todayActive }
 */
function loadStreakState() {
    try { return JSON.parse(localStorage.getItem(STREAK_KEY) || 'null'); } catch { return null; }
}
function saveStreakState(s) {
    try { localStorage.setItem(STREAK_KEY, JSON.stringify(s)); } catch { /* ignore */ }
}

const STREAK_TIERS = [
    { threshold: 1, name: 'Seed' },
    { threshold: 3, name: 'Sprout' },
    { threshold: 7, name: 'Leafy' },
    { threshold: 14, name: 'Branch' },
    { threshold: 30, name: 'Grove' },
    { threshold: 60, name: 'Evergreen' }
];

function computeMilestone(streak) {
    let tier = 0, name = STREAK_TIERS[0].name, nextThreshold = null;
    for (let i = 0; i < STREAK_TIERS.length; i++) {
        if (streak >= STREAK_TIERS[i].threshold) { tier = i; name = STREAK_TIERS[i].name; }
        else { nextThreshold = STREAK_TIERS[i].threshold; break; }
    }
    return { tier, name, nextThreshold, nextTierIn: nextThreshold ? nextThreshold - streak : null };
}

function applyActivityToMock(words, durationSec) {
    // 阈值来自设计文档：词数 ≥150 或 时长 ≥120 秒 视为当日活跃
    const active = (words || 0) >= 150 || (durationSec || 0) >= 120;
    const today = todayUTC();
    let state = loadStreakState();
    if (!state) {
        state = { currentStreak: 0, bestStreak: 0, lastActiveDate: null, todayActive: false };
    }
    if (active) {
        if (state.lastActiveDate === today) {
            // Already counted today
            state.todayActive = true;
        } else {
            // Determine continuity
            const yesterday = new Date(Date.now() - 86400000).toISOString().slice(0, 10);
            if (state.lastActiveDate === yesterday) {
                state.currentStreak += 1;
            } else {
                state.currentStreak = 1; // reset (either break or first time)
            }
            state.lastActiveDate = today;
            state.todayActive = true;
            if (state.currentStreak > state.bestStreak) state.bestStreak = state.currentStreak;
        }
    }
    saveStreakState(state);
    return state;
}

function buildStreakResponse(state) {
    const safe = state || { currentStreak: 0, bestStreak: 0, lastActiveDate: null, todayActive: false };
    const milestone = computeMilestone(safe.currentStreak);
    return {
        currentStreak: safe.currentStreak,
        bestStreak: safe.bestStreak,
        todayActive: safe.todayActive && safe.lastActiveDate === todayUTC(),
        lastActiveDate: safe.lastActiveDate,
        milestone
    };
}

// ---- 对外导出函数 ---------------------------------------------------------

/**
 * 获取 streak 信息。
 * 调用顺序：invoke('get_streak') → GET /api/streak → 本地 mock。
 * @returns {Promise<{currentStreak:number,bestStreak:number,todayActive:boolean,lastActiveDate:string|null,milestone:{tier:number,name:string,nextThreshold:number|null,nextTierIn:number|null}}>} 
 */
export async function getStreak() {
    // 1. Tauri command attempt
    try { return await tryInvoke('get_streak'); } catch (_) { /* ignore fallback */ }
    // 2. HTTP attempt
    try { return await tryFetchJSON('/api/streak'); } catch (_) { /* ignore fallback */ }
    // 3. Local mock
    return buildStreakResponse(loadStreakState());
}

/**
 * 记录一次活动（词数 + 时长）。顺序：invoke('log_activity') → POST /api/activity/log → 本地 streak 更新。
 * @param {number} words 词数
 * @param {number} durationSec 时长（秒）
 * @returns {Promise<{accepted:boolean,streak?:any}>} 返回是否接受以及（若可）更新后的 streak
 */
export async function logActivity(words = 0, durationSec = 0) {
    const payload = { words, durationSec, finishedAt: Math.floor(Date.now() / 1000) };
    // 1. Tauri
    try {
        const r = await tryInvoke('log_activity', payload);
        return { accepted: true, streak: r?.streak }; // assume backend returns updated streak
    } catch (_) { /* fallback */ }
    // 2. HTTP
    try {
        await fetch('/api/activity/log', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    } catch (_) { /* swallow */ }
    // 3. Local mock streak update
    const state = applyActivityToMock(words, durationSec);
    return { accepted: true, streak: buildStreakResponse(state) };
}

/**
 * 获取聚合统计（总字数 / 节省时间 / WPM），后端未实现前使用占位值。
 * 目前：优先尝试从 Tauri 命令 get_all_transcripts 推导。
 * @returns {Promise<{totalWords:number,timeSavedSeconds:number,wpm:number,todayWords?:number}>}
 */
export async function getStats() {
    try { return await tryInvoke('get_stats'); } catch (_) { }
    try { return await tryFetchJSON('/api/stats'); } catch (_) { }
    // 尝试从 Tauri 的 get_all_transcripts 推导真实统计
    try {
        const list = await tryInvoke('get_all_transcripts');
        if (Array.isArray(list) && list.length) {
            let totalChars = 0;
            let totalDurationMs = 0;
            let maxWpm = 0;
            let todayChars = 0;
            const today = new Date();
            const todayKey = today.toISOString().slice(0, 10);
            for (const s of list) {
                const text = (s.refined_text || s.raw_text || '').trim();
                const chars = text.length;
                const durMs = s.duration_ms || 0;
                totalChars += chars;
                totalDurationMs += durMs;
                const durMin = durMs > 0 ? durMs / 1000 / 60 : 0;
                if (chars > 0 && durMin > 0) {
                    const wpm = chars / durMin;
                    if (wpm > maxWpm) maxWpm = wpm;
                }
                try {
                    const d = new Date(s.created_at || s.session_id || '');
                    const key = isNaN(d.getTime()) ? '' : d.toISOString().slice(0, 10);
                    if (key === todayKey) todayChars += chars;
                } catch (_) { }
            }
            const timeSavedSeconds = totalChars * 0.5; // 假设语音比打字快一半，每字平均 0.5 秒
            const avgWpm = totalDurationMs > 0 ? totalChars / (totalDurationMs / 1000 / 60) : maxWpm || 0;
            return {
                totalWords: totalChars,
                timeSavedSeconds: Math.round(timeSavedSeconds),
                wpm: Number(avgWpm.toFixed(1)),
                todayWords: todayChars,
            };
        }
    } catch (_) { }
    // Derive from mock streak or defaults (placeholder numbers)
    return { totalWords: 47, timeSavedSeconds: 22, wpm: 70.5 };
}

/**
 * 分页/搜索列出转录记录。
 * @param {object} opts 传入选项
 * @param {number} [opts.offset=0] 偏移量
 * @param {number} [opts.limit=20] 单页限制
 * @param {string} [opts.search] 搜索关键字（可选）
 * @returns {Promise<{items:Array, total:number, offset:number, limit:number}>}
 */
export async function listTranscripts(opts = {}) {
    const { offset = 0, limit = 20, search = '' } = opts;
    try { return await tryInvoke('list_transcripts', { offset, limit, search }); } catch (_) { }
    try { return await tryFetchJSON(`/api/transcripts?offset=${offset}&limit=${limit}&search=${encodeURIComponent(search)}`); } catch (_) { }
    // Mock sample (mirror existing sample in main.js)
    const sample = [
        { id: 1, text: '示例转录一', source: 'Edge', durationSec: 2, words: 2, createdAt: new Date().toISOString() },
        { id: 2, text: '示例转录二', source: 'Edge', durationSec: 3, words: 4, createdAt: new Date(Date.now() - 1800000).toISOString() },
        { id: 3, text: '示例转录三', source: 'Edge', durationSec: 5, words: 6, createdAt: new Date(Date.now() - 3600000).toISOString() }
    ];
    const filtered = search ? sample.filter(s => s.text.toLowerCase().includes(search.toLowerCase())) : sample;
    const items = filtered.slice(0, limit);
    return { items, total: filtered.length, offset, limit };
}

/**
 * 示例：封装已有后端 greet（保持风格统一，可选）。
 */
export async function greet(name) {
    try { return await tryInvoke('greet', { name }); } catch (_) { return `Hello ${name}`; }
}

// ---- 开发调试诊断 ---------------------------------------------------------
export function apiDiagnostics() {
    return {
        isTauri: isTauri(),
        storedStreak: loadStreakState(),
        tauriCommandsPlanned: ['get_streak', 'log_activity', 'get_stats', 'list_transcripts']
    };
}

// 可选：开发期挂到 window 方便控制台调试
if (typeof window !== 'undefined') {
    window.__API__ = { getStreak, logActivity, getStats, listTranscripts, greet, apiDiagnostics };
}
