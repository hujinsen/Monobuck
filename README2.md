# Monobuck2 使用与开发指南

> Windows / 跨平台语音输入助手：按下快捷键开始说话，自动语音转文字，并通过大模型润色后直接注入到光标位置。

---

## 1. 项目简介

Monobuck2 是一个受 macOS 应用 Monologue 启发的跨平台语音输入工具：

- 按下快捷键（如 Ctrl + Win 或双击 Ctrl），即可开始录音；
- 后端实时进行语音识别（ASR），将语音转为文本；
- 文本再交给大模型进行“规范化/润色”，输出直接可用的高质量文本；
- 最终结果自动回填到当前光标位置（任何编辑器/输入框中）。

项目采用前后端分离 + Tauri 框架：

- **前端 UI**：HTML/CSS/JavaScript（在 `src/` 中），负责界面、统计面板和勋章系统等；
- **Python 后端**：在 `mono_core/` 中，通过 WebSocket 提供本地/远程 ASR 与文本润色服务；
- **Tauri/Rust 中间层**：在 `src-tauri/` 中，负责：
  - 全局快捷键监听（Ctrl+Win / 双击 Ctrl 等）；
  - 调用系统麦克风并推音频流给 Python WebSocket 服务；
  - 维护本地 session 记录（`records/`）和统计数据；
  - 打包为桌面应用（Windows 为主，亦可扩展 macOS/Linux）。

架构示意图见：`docs/Screenshot_20260209221338.png`。

---

## 2. 仓库结构概览

- `mono_core/`：Python 后端核心
  - `websocket_server.py`：WebSocket 音频服务入口（打包为 `websocket_server.exe`）。
  - `core/`：后端具体逻辑
    - `asr_service.py`：ASR 服务封装（远程 Fun-ASR 实时识别为主，预留本地模型策略）。
    - `text_service.py`：文本服务封装，调用通义千问等模型进行润色（Refine）。
    - `config.json` / `config.py`：后端配置读取与管理（API Key、ASR 参数等）。
    - 其他：模型管理、Runtime、工具函数等。
  - `RealtimeSTT/`：实时语音流处理相关模块（VAD、录音、状态机等）。
  - `examples/`：Python 侧独立示例脚本。
  - `tests/`：ASR 策略切换、会话持久化等后端测试。
- `src/`：前端 Web 资源
  - `index.html`：主窗口页面结构。
  - `main.js`：前端主逻辑（导航、统计展示、与 Tauri 事件交互等）。
  - `hotkeys.js`：将 Rust 后端发出的 `recognition-event` 转换为前端 `CustomEvent`（start/stop）。
  - `recognition.js`：封装前端识别生命周期事件（开始/结束/错误等）。
  - `websocket.js`：通过 Tauri 命令连接 Python WebSocket（`ws://localhost:12000/ws/audio/{clientId}`）。
  - `api.js`：通过 Tauri 命令或本地文件访问统计、会话记录等。
  - `assets/`：图标、字体、提示音等静态资源。
  - `views/`：Dashboard / 转录列表 / 使用说明 / 设置等 HTML 片段。
- `src-tauri/`：Tauri（Rust）层
  - `tauri.conf.json`：Tauri 配置（窗口、bundler、资源列表等）。
    - `bundle.resources` 中包含 `resources/websocket_server.exe`，与 Python 打包结果对应。
  - `src/`：Rust 端代码（全局快捷键、音频采集、WebSocket 代理、session 记录等）。
  - `resources/`：打包时一并带入的资源（包括 `websocket_server.exe`）。
- `docs/`：设计与实现文档
  - `DESIGN_GUIDE.md`：前端 UI/交互/配色设计指南（Starbucks 风格深绿 + 玻璃拟物）。
  - `ASR_WORKFLOW.md`：ASR + Refine 的详细流程说明（生产者-消费者模型、队列设计）。
  - `ACHIEVEMENTS.md`：勋章系统与激励机制设计方案。
- `packages/achievements/`：前端勋章系统的独立 JS 包（设计草稿/组件封装）。
- `records/`：运行时生成的 session / 音频等记录（主要由 Rust 端维护）。

---

## 3. 运行与开发环境

### 3.1 系统要求

- 操作系统：Windows 10 及以上（主要开发与测试平台），理论上可扩展至 macOS / Linux。
- Node.js：建议 >= 18。
- Rust：Tauri 2 需要稳定版 Rust 工具链（`rustup` 安装即可）。
- Python：>= 3.10（推荐使用 `uv` 管理虚拟环境）。

### 3.2 Python 后端依赖

Python 侧依赖在 `mono_core/pyproject.toml` 中声明，主要包括：

- ASR 相关：`funasr`、`funasr-onnx`、`webrtcvad-wheels`、`silero-vad`、`sounddevice`、`pyaudio` 等；
- LLM 相关：`dashscope`（用于通义系列模型调用）；
- Web 层：`websockets`、`fastapi`、`uvicorn`（部分模块使用）；
- 其他：`numpy`、`torch`、`jieba`、`psutil`、`pyinstaller` 等。

建议通过 `uv` 在 `mono_core/` 目录下管理环境：

```bash
cd mono_core
uv init .
uv sync
```

完成后即可使用虚拟环境内的 Python 运行/打包后端服务。

---

## 4. 快速开始（开发模式）

### 步骤 1：准备 Python 后端

1. 进入后端目录并创建环境（如上所示）：

   ```bash
   cd mono_core
   uv init .
   uv sync
   ```

2. 配置 `mono_core/core/config.json`：

   - 配置阿里云 DashScope 的 `DASHSCOPE_API_KEY`（用于远程 ASR 与 LLM，视实际使用而定）；
   - 根据需要配置 `ASR_SAMPLE_RATE`、`ASR_FORMAT`、`USE_REMOTE_LLM` 等；
   - 可以参考代码中的 `get_config_value` 调用查看需要的键。

3. 直接运行 Python WebSocket 服务（开发时可以不打包）：

   ```bash
   cd mono_core
   python websocket_server.py
   ```

   默认监听：`ws://localhost:12000/ws/audio/{client_id}`，端口为 `12000`。

### 步骤 2：准备 Node/Tauri 前端

1. 在仓库根目录安装依赖：

   ```bash
   cd ..  # 回到仓库根目录 MonoBuck2
   npm install
   ```

   `package.json` 中只包含 Tauri CLI 及其插件依赖：

   - `@tauri-apps/cli`：Tauri 2 命令行工具；
   - `@tauri-apps/plugin-global-shortcut`：全局快捷键插件。

2. 开发模式启动 Tauri：

   ```bash
   npm run tauri dev
   ```

   这会：

   - 启动 Tauri dev 进程，打开主窗口（`src/index.html`）；
   - 由 Rust 端负责：捕获快捷键、创建录音窗口、与 Python WebSocket 建立连接等。

> 开发时你可以：
> - 单独运行 Python（`python mono_core/websocket_server.py`），观察日志；
> - 使用浏览器 DevTools 调试前端 UI（Tauri dev 模式下可启用）。

---

## 5. 打包发布

### 5.1 打包 Python WebSocket 服务

进入 `mono_core/`，使用已有脚本打包：

```bash
cd mono_core
python build_websocket_server.py
```

脚本会调用 PyInstaller，生成独立的 `websocket_server.exe`。

生成物会被复制到：

- `src-tauri/resources/websocket_server.exe`

Tauri 配置 `src-tauri/tauri.conf.json` 中的：

```json
"bundle": {
  "resources": [
    "resources/websocket_server.exe"
  ]
}
```

会在最终安装包中携带该可执行文件，运行时由 Rust 端拉起。

### 5.2 打包 Tauri 应用

在仓库根目录执行：

```bash
npm run tauri build
```

- Tauri 会使用 `src-tauri/tauri.conf.json` 中的配置打包应用；
- 产物默认位于：`src-tauri/target/release/`（不同平台文件名略有差异）。

> 注意：打包前应确保 `src-tauri/resources/websocket_server.exe` 存在，否则应用内无法进行语音识别。

---

## 6. 功能与交互概览

### 6.1 快捷键与录音流程

- Rust 端监听系统层快捷键（例如：
  - Ctrl + Win 按住说话，松开结束；
  - 双击 Ctrl 开始，再按一次停止；
  - 具体组合以实际实现为准）。
- 监听到开始事件后：
  - 展示/更新录音状态小窗（由 `recording_status.html` 渲染）；
  - 通过 Tauri 命令推送音频流到 Python WebSocket 服务；
  - 向前端广播 `recognition:start`。
- 停止录音：
  - 推送停止指令到 Python（在 WebSocket 文本消息中发送 `stop_recording` 命令）；
  - Python 侧按 `docs/ASR_WORKFLOW.md` 中描述的队列机制，完成 ASR 和 Refine；
  - 最终通过 Tauri 事件把 `final_result` 返回给前端，并注入当前光标位置。

### 6.2 ASR + Refine 细节

在 `mono_core/websocket_server.py` 中：

- `ConnectionManager` 维护每个客户端连接的：
  - WebSocket 实例；
  - 音频缓冲与队列；
  - 停止事件等。
- 每个连接对应一个 ASR worker 线程：
  - 从 `audio_queue` 读取音频帧，调用 `ASRService.transcribe_stream`；
  - 将中间/最终识别结果放入 `result_queue`；
  - 在会话结束时插入 `{"status": "session_end"}` 消息。
- 异步 `asr_consumer` 协程：
  - 持续从 `result_queue` 读取识别结果；
  - 将 `is_final=True` 的文本拼接到 `session_text_list`；
  - 收到 `session_end` 时再一次性调用 `TextService.refine(raw_text)`，返回 `final_result`。

更多细节可以参考：`docs/ASR_WORKFLOW.md`。

### 6.3 前端 UI 与勋章系统

- Dashboard：展示使用统计、热力日历、最近转录等。
- 转录列表：按 session 展示历史记录（从 `records/sessions/*.json` 读取）。
- 勋章系统：
  - 设计文档在 `docs/ACHIEVEMENTS.md`；
  - 具体 JS 草案在 `packages/achievements/`。
- UI 设计语言：深绿色 + 玻璃拟物 + 金色点缀（详见 `docs/DESIGN_GUIDE.md`）。

---

## 7. 配置与常见问题

### 7.1 配置项

主要配置位于 Python 端 `mono_core/core/config.json`，典型项包括：

- `DASHSCOPE_API_KEY`：阿里云 DashScope API Key；
- `ASR_SAMPLE_RATE`：采样率，默认 16000；
- `ASR_FORMAT`：音频格式（如 `pcm`）；
- `USE_REMOTE_LLM`：是否启用远程大模型（否则走本地 mock）。

修改配置后，重启 Python WebSocket 服务即可生效。

### 7.2 日志与排错

- Python 端：
  - `mono_core/websocket_server.py` 启动时会把日志输出到：
    - 临时目录下的 `monobuck_audio_service.log`；
    - 控制台标准输出。
- Tauri/Rust 端：
  - 运行时日志可在 Tauri 控制台中查看；
- 前端：
  - `src/main.js` 中接管了 `console.log/error`，面板 `#debug-panel` 中可查看最近日志。

常见问题排查思路：

1. 无法连接 WebSocket：
   - 确认 Python 服务是否已启动，端口 12000 是否被占用；
   - 查看后端日志中是否有导入 Fun-ASR / DashScope 失败等异常。
2. 有识别但没有润色：
   - 检查 `USE_REMOTE_LLM` 配置；
   - 检查 `DASHSCOPE_API_KEY` 是否有效。
3. Tauri 启动后无响应：
   - 使用 `npm run tauri dev` 并打开 DevTools 查看前端报错；
   - 检查 `resources/websocket_server.exe` 是否存在并可执行。

---

## 8. 面向开发者的建议

- 若只想调试 ASR：
  - 可以在 `mono_core/examples/` 中添加独立脚本，直接调用 `ASRService.transcribe_file` 或 `transcribe_stream`。
- 若只想调试前端 UI：
  - 可使用 VS Code 的 Live Server / 任意静态服务器直接打开 `src/` 目录，但部分依赖 Tauri API 的功能会不可用。
- 若要扩展本地 ASR / 本地 LLM：
  - 在 `asr_service.py` 与 `text_service.py` 中已有 `Local*Strategy` 占位，可以在不依赖远程服务的前提下实现完整链路。

如需我进一步补充英文版 README 或拆分为「用户使用手册」+「开发文档」两份文件，也可以继续说明。