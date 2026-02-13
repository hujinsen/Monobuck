[中文](README_CN.md)
# Monobuck2 Usage & Development Guide

> A cross-platform voice input assistant for Windows: press a global shortcut to start speaking, get real-time speech-to-text, then auto-refine the text with an LLM and inject it into the current cursor position.

---

https://github.com/user-attachments/assets/abfacdaf-51ce-4c54-9da5-f29755435b10

## 1. Overview

Monobuck2 is inspired by the macOS app Monologue and aims to bring a similar, polished voice input experience to Windows (and potentially other platforms).

Typical flow:

- You press a global shortcut (e.g., `Ctrl + Win` or double-press `Ctrl`) to start recording.
- The backend performs real-time ASR (speech recognition) to convert your speech into text.
- The raw ASR text is sent to an LLM for formatting and refinement so that the result is directly usable with minimal edits.
- The refined text is injected back into the current focused input field (editor, browser, IM, etc.).

Architecture at a glance:

- **Frontend UI** (in `src/`): Plain HTML/CSS/JavaScript, responsible for the dashboard, stats, achievements view, and in-app interactions.
- **Python backend** (in `mono_core/`): Provides local/remote ASR and text refinement services over WebSocket.
- **Tauri/Rust bridge** (in `src-tauri/`):
  - Listens to system-wide hotkeys.
  - Captures microphone audio and streams it to the Python WebSocket server.
  - Manages session persistence under `records/`.
  - Packages everything into a desktop app (primarily for Windows, extendable to macOS/Linux).

See the architecture diagram in `docs/Screenshot_20260209221338.png`.

---

## 2. Repository Structure

- `mono_core/` – Python backend core
  - `websocket_server.py`: WebSocket audio service entry (later bundled as `websocket_server.exe`).
  - `core/`:
    - `asr_service.py`: ASR service wrapper (currently remote Fun-ASR realtime; local strategy placeholder included).
    - `text_service.py`: Text service wrapper, calling DashScope LLMs (e.g., Qwen) for refinement.
    - `config.json` / `config.py`: Configuration loading utilities (API keys, ASR parameters, feature flags, etc.).
    - Other helpers: runtime, models, utilities.
  - `RealtimeSTT/`: Realtime speech pipeline modules (VAD, recorder, state machine, etc.).
  - `examples/`: Standalone Python demos.
  - `tests/`: Backend test cases (ASR strategy switching, stream/session persistence, etc.).
- `src/` – Frontend web assets
  - `index.html`: Main window markup.
  - `main.js`: Main frontend logic (navigation, dashboard, stats updates, Tauri event handling, etc.).
  - `hotkeys.js`: Bridges Rust-side recognition events to frontend `CustomEvent`s (`recognition:start/stop`).
  - `recognition.js`: Normalized recognition lifecycle hooks (start/stop/error, etc.).
  - `websocket.js`: Uses Tauri commands to connect to the Python WebSocket server (`ws://localhost:12000/ws/audio/{clientId}`).
  - `api.js`: Talks to Tauri/Rust to fetch stats and transcripts from local storage.
  - `assets/`: Icons, fonts, sounds, etc.
  - `views/`: HTML fragments for dashboard, transcripts, instructions, settings, etc.
- `src-tauri/` – Tauri (Rust) layer
  - `tauri.conf.json`: App configuration (windows, bundle, resources).
    - `bundle.resources` includes `resources/websocket_server.exe` built from Python.
  - `src/`: Rust code handling global shortcuts, audio capture, WebSocket proxying, session persistence, etc.
  - `resources/`: Extra resources packaged with the app (including `websocket_server.exe`).
- `docs/` – Design and workflow docs
  - `DESIGN_GUIDE.md`: Detailed UI design guide (colors, typography, components, layout).
  - `ASR_WORKFLOW.md`: ASR + refine pipeline design (producer/consumer queues, session boundaries, race-condition handling).
  - `ACHIEVEMENTS.md`: Achievements / badges system and reward mechanics.
- `packages/achievements/`: JS package draft for the achievements UI and logic.
- `records/`: Runtime-generated sessions and audio-related data (mainly orchestrated by the Rust side).

---

## 3. Environment & Dependencies

### 3.1 Requirements

- **OS**: Windows 10 or later (primary target). Other platforms are possible with Tauri.
- **Node.js**: Recommended >= 18.
- **Rust**: Stable toolchain via `rustup` (required by Tauri 2).
- **Python**: >= 3.10 (strongly recommended to manage via `uv`).

### 3.2 Python Backend Dependencies

Python dependencies are defined in `mono_core/pyproject.toml`, including:

- ASR: `funasr`, `funasr-onnx`, `webrtcvad-wheels`, `silero-vad`, `sounddevice`, `pyaudio`, etc.
- LLM: `dashscope` (for Aliyun DashScope / Qwen models).
- Web: `websockets`, `fastapi`, `uvicorn`, `python-multipart` (some used by submodules).
- Others: `numpy`, `torch`, `jieba`, `psutil`, `pyinstaller`, and more.

Use `uv` in `mono_core/` to create and sync the environment:

```bash
cd mono_core
uv init .
uv sync
```

After this, use the virtualenv Python for running and bundling the backend.

---

## 4. Getting Started (Development)

### Step 1 – Set up the Python backend

1. Create and sync the environment (as above):

   ```bash
   cd mono_core
   uv init .
   uv sync
   ```

2. Configure `mono_core/core/config.json`:

   - Set `DASHSCOPE_API_KEY` for Aliyun DashScope (both ASR and LLM, depending on your setup).
   - Optionally tune `ASR_SAMPLE_RATE`, `ASR_FORMAT`, `USE_REMOTE_LLM`, etc.
   - Check where `get_config_value` is used in code to see which keys are expected.

3. Run the WebSocket server in development mode (no bundling required):

   ```bash
   cd mono_core
   python websocket_server.py
   ```

   Default address: `ws://localhost:12000/ws/audio/{client_id}`.

### Step 2 – Set up the Node/Tauri frontend

1. Install Node dependencies at repo root:

   ```bash
   cd ..  # back to repo root
   npm install
   ```

   `package.json` mainly includes:

   - `@tauri-apps/cli`: Tauri 2 CLI.
   - `@tauri-apps/plugin-global-shortcut`: global shortcut plugin.

2. Start Tauri dev mode:

   ```bash
   npm run tauri dev
   ```

   This will:

   - Start the Tauri dev process and open the main window (`src/index.html`).
   - Let the Rust side handle global shortcuts, recording status window, and the bridge to Python WebSocket.

> For development:
> - You can run `python mono_core/websocket_server.py` separately and watch backend logs.
> - You can use Tauri devtools to debug the frontend.

---

## 5. Building for Distribution

### 5.1 Bundle the Python WebSocket server

Inside `mono_core/`, use the provided script:

```bash
cd mono_core
python build_websocket_server.py
```

This uses PyInstaller to produce a standalone `websocket_server.exe`.

The output is copied to:

- `src-tauri/resources/websocket_server.exe`

Tauri config `src-tauri/tauri.conf.json` contains:

```json
"bundle": {
  "resources": [
    "resources/websocket_server.exe"
  ]
}
```

So the executable is packaged with the final app and launched by the Rust side when needed.

### 5.2 Build the Tauri app

From the repository root:

```bash
npm run tauri build
```

- Tauri will build the desktop app according to `src-tauri/tauri.conf.json`.
- Artifacts are typically in `src-tauri/target/release/`.

> Important: ensure `src-tauri/resources/websocket_server.exe` exists before building; otherwise, ASR will not work in the packaged app.

---

## 6. Features & Interaction Model

### 6.1 Global hotkeys & recording lifecycle

- Rust side listens to platform-specific global shortcuts, for example:
  - Press-and-hold `Ctrl + Win` to record, release to stop; or
  - Double-tap `Ctrl` to start, tap again to stop.
- On recording start:
  - A small recording status window (`recording_status.html`) is shown/updated.
  - Microphone audio is streamed to the Python WebSocket server.
  - A `recognition:start` custom event is dispatched to the frontend (`hotkeys.js`).
- On recording stop:
  - A `stop_recording` command is sent via WebSocket text message on the Python side.
  - The backend finishes ASR and refinement according to the queue-based workflow.
  - The final result is returned via a Tauri event, and the Rust side injects the refined text into the current cursor position.

### 6.2 ASR + refine workflow

Within `mono_core/websocket_server.py`:

- `ConnectionManager` keeps per-client state:
  - WebSocket connection.
  - Audio buffer and queue.
  - Stop event.
- An ASR worker thread per connection:
  - Consumes from the audio queue and passes data to `ASRService.transcribe_stream`.
  - Emits incremental recognition results into a `result_queue`.
  - At the end of a session, pushes a sentinel `{"status": "session_end"}` into `result_queue`.
- An async `asr_consumer` task:
  - Reads from `result_queue`.
  - Appends only `is_final=true` texts to `session_text_list`.
  - When it receives `session_end`, it joins all collected texts into `raw_text`, calls `TextService.refine(raw_text)`, and sends a `final_result` message to the client.

This design is thoroughly documented in `docs/ASR_WORKFLOW.md`. It avoids race conditions by treating the session end as a first-class event in the data stream.

### 6.3 Frontend UI & achievements

- **Dashboard**:
  - Shows usage statistics, calendar heatmap, recent transcripts, etc.
- **Transcripts view**:
  - Lists historical sessions (backed by JSON files under `records/sessions/`).
- **Achievements system**:
  - Designed in `docs/ACHIEVEMENTS.md` and prototyped under `packages/achievements/`.
  - Multiple dimensions (usage count, duration, words, streak, special holidays, etc.).
- **UI design language**:
  - Dark, deep-green theme with glassmorphism and golden accents, described in `docs/DESIGN_GUIDE.md`.

---

## 7. Configuration & Troubleshooting

### 7.1 Key config options

Main configuration lives in `mono_core/core/config.json` (read via `get_config_value`):

- `DASHSCOPE_API_KEY`: Aliyun DashScope API key.
- `ASR_SAMPLE_RATE`: Sample rate (default 16000).
- `ASR_FORMAT`: Audio format (e.g., `pcm`).
- `USE_REMOTE_LLM`: Whether to call remote LLM (otherwise a local mock strategy is used).

Restart the Python WebSocket server after changing config values.

### 7.2 Logs & debugging

- **Python backend**:
  - `mono_core/websocket_server.py` logs to:
    - A temp file `monobuck_audio_service.log` under the OS temp directory.
    - Standard output.
- **Tauri/Rust**:
  - Logs appear in the Tauri dev console / terminal.
- **Frontend**:
  - `src/main.js` overrides `console.log/error/...` and writes to the on-screen debug panel (`#debug-panel`).

Common issues:

1. **Cannot connect to WebSocket**:
   - Check that the Python server is running and port 12000 is free.
   - Look at backend logs for import errors (Fun-ASR, DashScope, etc.).
2. **ASR works but no refinement**:
   - Verify `USE_REMOTE_LLM` and `DASHSCOPE_API_KEY`.
3. **Tauri app starts but UI is broken or unresponsive**:
   - Run `npm run tauri dev` and open devtools to inspect frontend errors.
   - Confirm that `resources/websocket_server.exe` is present and executable.

---

## 8. Developer Notes & Extension Ideas

- **ASR-only experiments**:
  - Use `ASRService.transcribe_file` or `transcribe_stream` directly from small scripts under `mono_core/examples/`.
- **Frontend-only prototyping**:
  - Serve the `src/` directory using a static server (e.g., VS Code Live Server). Some features that depend on Tauri APIs will be disabled or require mocks.
- **Local ASR / local LLM**:
  - `asr_service.py` and `text_service.py` already contain local strategy placeholders (`LocalASRStrategy`, `LocalLLMStrategy`).
  - You can plug in your own models and keep the same WebSocket & UI contracts.
