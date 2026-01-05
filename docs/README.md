
## 项目架构分析 (2026-01-04 更新)

> 本节总结当前代码库的技术栈、组件职责、数据流与改进路线，便于后续快速迭代。架构相较 2025-10 版本已有较大演进（引入 Python ASR+LLM、Tauri 会话持久化与统计等），因此本节为“当前真实状态”的对照说明。

### 1. 技术栈与目录概览
| 层 | 技术 | 现状 |
| --- | --- | --- |
| 桌面容器 | Tauri 2 (Rust) | 通过 `lib.rs` 启动应用，注册热键、音频流、WebSocket 客户端、会话与统计等命令，并在 Windows 上以子进程方式拉起 Python WebSocket sidecar（开发态跑源码，发布态跑打包好的 `websocket_server.exe`） |
| 语音与 LLM 后端 | Python 3.10+ | `mono_core` 内：ASR 使用阿里云 DashScope fun-asr-realtime（流式），Text 使用 DashScope 通义千问（或本地占位策略）做 refine，所有配置集中在 `core/config.json` |
| 前端 | 原生 ES Modules + 单一入口 `main.js` | 无框架（轻量），视图片段按需 `fetch` 注入；通过 `api.js` 抽象 Tauri 命令 / HTTP / mock；通过 `websocket.js` 与 Rust 命令交互 |
| 样式 | 单文件 `styles.css` | 含 Design Tokens / 组件 / 视图 / 动画；已支持浅色模式与部分 motion 降级 |
| 交互组件 | 自研 dropdown / settings modal / streak / confirm dialog 等 | 封装程度中等，可测试点明确 |
| 数据持久 | JSON 文件 + 内存 + `localStorage` | 会话与统计落盘在 `records/`（Rust 负责）；streak 暂为前端 mock + `localStorage`；其余如指令/词典暂存于内存 |

主要目录（与实际代码对齐）：
```
src/
	index.html (壳 + 侧栏导航)
	main.js (集中式页面与业务逻辑)
	api.js (统一 API 抽象: Tauri invoke / HTTP / mock)
	websocket.js (Tauri WebSocket 命令的薄封装)
	components/ (下拉, 设置模态, streak, 对话框等)
	views/ (分片 HTML：home / transcripts / instructions / dictionary ...)
src-tauri/
	src/lib.rs (Tauri 入口、全局状态与命令注册、Python sidecar 管理)
	src/audio_stream.rs / websocket.rs / session.rs / stats.rs / injection.rs / hotkey.rs
mono_core/
	core/asr_service.py (ASR 策略: 远程 Fun-ASR 为主)
	core/text_service.py (LLM 文本生成与 refine)
	core/service_runtime.py (ASR + refine 编排)
	websocket_server.py (Python WebSocket + ASR/Refine 入口)
records/
	audio/ (由 Rust 侧音频模块管理的音频文件)
	sessions/ (每次会话一份 JSON，供统计和前端展示)
docs/
	ASR_WORKFLOW.md (详细的 ASR + Refine 流程说明)
```

### 2. 音频 → ASR → Refine → 注入：端到端链路

从用户视角：按下全局快捷键开始说话，停止后自动把润色后的文本“打”进当前应用。

大致链路（更细节参考 `docs/ASR_WORKFLOW.md`）：

1. 全局快捷键：
	 - `src-tauri/src/hotkey.rs` 监听系统级快捷键；
	 - Rust 侧在 `lib.rs` 中将快捷键事件包装成 `"start" / "stop"` 指令，通过回调 `sender_wrapper` 触发音频采集的开始/结束。
2. 音频采集与发送：
	 - `src-tauri/src/audio_stream.rs` 使用 `cpal` 从系统麦克风拉音频帧；
	 - 通过 `src-tauri/src/websocket.rs` 维护到 Python WebSocket Server 的连接，将 PCM 分片发往 `ws://localhost:12000/ws/audio/{client_id}`。
3. Python WebSocket + ASR：
	 - `mono_core/websocket_server.py` 建立 WebSocket 服务器，`ConnectionManager` 为每个 `client_id` 维护音频队列、缓冲与停止事件；
	 - 独立 ASR Worker 线程消费音频队列，调用 `ASRService.transcribe_stream(...)`，将流式识别结果写入 `result_queue`；
	 - 识别结束时，Worker 会：
		 - 若有最后未标记 `is_final` 的片段，强制标记为最终句并放入 `result_queue`；
		 - 追加一个 `{"status": "session_end"}` 作为会话结束哨兵。
4. 结果消费与 refine：
	 - 异步协程 Consumer 从 `result_queue` 中读取：
		 - 普通结果：原样通过 WebSocket 推回 Rust/前端（`"status": "recognition_result"`），仅当 `is_final=true` 时才记入当前会话 `session_text_list`；
		 - 收到 `session_end`：将 `session_text_list` 拼成 `raw_text`，清空列表，然后在线程池中调用 `TextService.refine(raw_text)`；
	 - 最终结果通过 `"status": "final_result"`（包含 raw_text + refined_text）推回。
5. Rust 会话记录与统计：
	 - `src-tauri/src/session.rs` 在会话结束后将本次会话的 meta + 文本写入 `records/sessions/*.json`；
	 - `src-tauri/src/stats.rs` 在启动时以及收到新会话时，基于所有 session 计算聚合统计（总字数、节省时间、WPM、今日字数等），缓存到 `StatsShared`，并通过 `get_stats` 命令暴露给前端；
	 - 同时通过 Tauri 事件 `stats-updated` 推送给前端刷新首页视图。
6. 文本注入：
	 - `src-tauri/src/injection.rs` 暴露 `inject_text_unicode` 命令，将 refined 文本以模拟键盘输入的方式注入到当前活动窗口。
7. 前端 UI：
	 - `src/main.js` 中的 `initLivePanel()` 订阅识别生命周期事件和 `recognition:final` 事件，更新“实时识别面板”上的状态、原始文本、润色文本和时长；
	 - `src/websocket.js` 负责将前端调用转换为 Tauri 命令，并监听 Rust 发出的 `ws-open/ws-message/ws-error/ws-end/ws-close/ws-inject` 等事件来更新 UI。

### 3. 前端视图加载与导航机制

与早期设计一致，前端仍采用“视图片段 + 轻量路由”的方式：

- 侧栏按钮绑定 `data-target`，通过 hash (`#dashboard` 等) 或点击触发 `loadView(key)`；
- `loadView` 将 `views/<name>.html` 片段 `fetch` 注入 `#view-container`；
- 根据视图类型触发增强：
	- home：渲染热力日历 + streak 徽章，读取 `getStats()` 和最近会话列表；
	- transcripts：渲染转录列表（现已接真实数据源），支持分页/搜索；
	- instructions/dictionary：本地编辑操作逻辑仍集中在 `main.js`；
- 通过切换 `.active` 类与 `history.replaceState` 模拟轻量路由。

已知问题保持不变：

- 没有统一的“卸载”生命周期（事件监听有潜在累积风险）；
- 大量业务逻辑仍集中在 `main.js`，后续维护成本较高，适合逐步模块化拆分。

### 4. 组件职责概览（更新版）

| 组件 | 文件 | 作用要点 | 备注 |
| ---- | ---- | -------- | ---- |
| Dropdown | `components/dropdown.js` | 原生 `<select>` → 自定义浮层；ARIA + 键盘导航 + 自动翻转 | 通过 registry 统一管理，可单元测试 |
| Settings Modal | `components/settings-modal.*` | 延迟加载 HTML 模板与多面板；枚举麦克风；增强 `<select>` | 有设备缓存点，可添加错误态重试 |
| Streak Badge | `components/streak.js` | 本地缓存 + `getStreak()`；当前后端 `get_streak` 尚未实现时回退到 `localStorage` mock | 计算逻辑与本文档保持一致 |
| Confirm Dialog | `components/ui-dialog.js` | 全局确认/危险操作对话框 | 焦点环捕获 / 可访问性良好 |
| Transcripts List | `main.js` + `api.js` | 从 Tauri 命令 `get_all_transcripts` 或 `list_transcripts`（未来）获取真实会话数据，提供分页/搜索 | 建议后续拆分为独立模块 `components/transcripts.js` |
| Dictionary Manager | `main.js` 片段 | 词条增删改 + 替换模式开关 | 当前仅内存持有，需 IndexedDB / 后端持久层 |

### 5. 当前数据与状态流

| 数据类型 | 来源 | 缓存/持久 | 消费者 | 备注 |
| -------- | ---- | --------- | ------- | ---- |
| Streak 状态 | 预期后端命令 `get_streak` 或 `/api/streak` | 前端 `localStorage.mock.streak.state` | `streak.js` / 首页 | 后端尚未实现 streak；当前全在前端 mock 中演进 |
| 活动上报 | 预期 `log_activity` / `/api/activity/log` | 无（计划写入 streak 状态） | `reportActivity()` / `api.logActivity()` | 目前主要驱动 mock streak 更新 |
| 转录会话列表 | Rust `SessionState` + `records/sessions/*.json` | JSON 文件（磁盘） | `api.getStats()` / 首页“最近转录” / “转录”页面列表 | 已有真实数据源，不再是纯假数据 |
| 统计汇总 | Rust `StatsAggregate` | 内存（`StatsShared`） + 可由 sessions 重新计算 | `api.getStats()` / 首页统计卡片 | 启动时和每次新会话后重新聚合，并通过 `stats-updated` 推送前端 |
| 词典词条 | 表单输入 | 内存 | `main.js` | 刷新即丢失，仍建议 IndexedDB 化 |
| 模式 (instructions) | DOM + 操作 | 内存 | `main.js` | 同上，适合抽离数据模型 |
| 麦克风偏好 | 用户选择 | `localStorage.pref.mic` | Settings Modal | 需与本地设备枚举对齐 |

### 6. 后端 (Tauri + Python) 状态

Rust 侧（`src-tauri/src/lib.rs`）：

- 已存在的对外命令：
	- `greet(name)`：示例命令；
	- `ws_connect/ws_send_text/ws_send_binary/ws_disconnect/ws_status`：前端 WebSocket 桥接；
	- `get_recent_sessions(limit?)`：读取最近 N 条会话；
	- `get_all_transcripts()`：读取全部会话（倒序），供统计与“转录”页面使用；
	- `get_stats()`：返回聚合统计 `StatsAggregate`；
	- `inject_text_unicode(text)`：将文本注入当前活动窗口；
	- 热键相关：`set_custom_shortcut/clear_custom_shortcut` 等。
- 持久化：
	- 会话 JSON：`records/sessions/*.json`；
	- 音频文件：`records/audio/`（具体格式由 `audio_stream.rs` 控制）。

Python 侧（`mono_core`）：

- 仅通过 WebSocket 进行交互，不直接暴露 HTTP API 或命令；
- 配置统一从 `core/config.json` 读取（不再支持环境变量覆盖，避免多重来源冲突）；
- ASR 与 Text 服务的职责边界清晰：
	- `ASRService` 负责语音转文本（支持文件、外部流、麦克风），不关心 LLM；
	- `TextService` 负责根据 prompt 对文本做生成/润色；
	- `ServiceRuntime` 将两者编排成不同模式（整文件、流式、麦克风）。

### 7. 徽章 / Streak 机制要点（仍按设计文档）

- 阈值: 1/3/7/14/30/60 天 → 六档里程碑（Seed→Evergreen）。
- 判定：词数 ≥ 150 或 时长 ≥ 120 秒（满足其一记为活跃日）。
- 返回结构（推荐后端实现时沿用）：
	- `{ currentStreak, bestStreak, todayActive, milestone{tier,name,nextTierIn}, lastActiveDate, daysBitmask? }`。
- 升级动画：仅在 fresh 拉取 & 等级提升时加 `.upgrade`。
- 当前实现状态：
	- 计算逻辑已经在 `src/api.js` 中以 mock 形式落地；
	- 后端尚无 `get_streak/log_activity` 命令，未来可以直接参考现有 mock 行为来对齐实现。

### 8. 建议的增量路线 (Phases, 更新版)

| 阶段 | 目标 | 关键产出 |
| ---- | ---- | -------- |
| P1 | 补齐 streak 与 activity 后端命令 | Rust: `get_streak`, `log_activity`；Python: 可选增加 streak 文件/SQLite；前端: `streak.js`/`api.js` 切换到真实后端，保留 mock 作为降级 |
| P2 | 转录与统计 API 稳定化 | 在 Rust 侧引出 `list_transcripts(offset,limit,search)`，前端 `api.listTranscripts()` 切换到真实实现，并将首页与“转录”页面统一使用该 API |
| P3 | 数据层与缓存 | 设计统一数据层（会话、streak、词典），会话/统计已使用 JSON，可评估是否迁移到 SQLite；前端可引入 IndexedDB 缓存大体量历史 |
| P4 | 视图与组件模块化 | 抽出 `components/transcripts.js`、`stores/*`，减少 `main.js` 体积；建立简单的视图 mount/unmount 生命周期，防止事件监听累积 |
| P5 | 设置与设备体验 | 扩展设置面板：真实麦克风枚举/记忆、失败重试、全局快捷键可视化配置与冲突提示 |
| P6 | 性能与结构 | 拆分 `styles.css`（tokens/layout/components/views），优化首屏渲染、长列表虚拟滚动、ASR/Refine 延迟监控 |
| P7 | 质量/监控 | 指标埋点（识别成功率、端到端延迟、注入失败率）、错误日志、覆盖 ASR/Refine 关键路径的单元测试与集成测试 |

### 9. 主要风险与缓解（结合当前实现）

| 风险 | 影响 | 当前状态与缓解 |
| ---- | ---- | -------------- |
| 逻辑集中在 `main.js` | 难维护/扩展 | 现状仍集中；可按 P4 渐进拆分组件与 store |
| Streak 后端缺失 | 前后端行为不一致风险 | 目前前端已实现完整 mock 逻辑，可作为后端实现的“金标准”对照 |
| WebSocket/ASR 竞态 | 可能丢失最后一句或重复 refine | 已通过队列+哨兵（`__STOP__` / `session_end`）在 Python 端解决，详见 `ASR_WORKFLOW.md` |
| 事件泄漏 | 导致性能问题或行为异常 | 视图 mount/unmount 尚未统一管理，导航较多时需关注监听数增长；后续可引入简单路由管理器 |
| CSS 单文件膨胀 | 冲突 & 首屏渲染 | 当前仍为单文件；可按 tokens/layout/components/views 分层演进 |

### 10. 里程碑验收指标建议（沿用 + 适配当前状态）

| 指标 | 目标 |
| ---- | ---- |
| Streak API 成功率 | > 99%（落地真实后端后统计） |
| 端到端延迟（说完到注入完成） | POC 阶段尽量控制在 1.5~2s 内 |
| 首屏渲染 (冷启动) | < 1.2s（使用 mock 数据时） |
| 事件重复绑定泄漏 | 0（导航 50 次内监听数量不增长） |
| ASR/Refine 核心测试 | 覆盖关键边界：0/1 句、长句、静音、API 错误等 |

---
若后续架构继续演进（例如引入 SQLite、服务拆分或多模型路由），可按需将本节拆分为独立的 `ARCHITECTURE.md` 与 `ARCHITECTURE_CHANGELOG.md`，以便持续记录设计决策与权衡过程。

