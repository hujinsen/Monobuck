/* Settings modal module (lazy loaded on first open). */
// confirmDialog 可按需从 '../components/ui-dialog.js' 导入，这里暂不直接使用以避免循环
// 自定义增强下拉框组件（仅设置面板内特定字段）
import { enhanceSettingsSelects } from './settings-select.js';

function qs(sel, ctx = document) { return ctx.querySelector(sel); }
function qsa(sel, ctx = document) { return Array.from(ctx.querySelectorAll(sel)); }

let injected = false;
let injectingPromise = null;
export function initSettingsModal() {
    if (injected) return Promise.resolve();
    if (injectingPromise) return injectingPromise;
    // 先确保 spinner 显示
    ensureSettingsSpinner();
    injectingPromise = fetch('./components/settings-modal.html')
        .then(r => r.text())
        .then(html => {
            const tpl = document.createElement('template');
            tpl.innerHTML = html.trim();
            document.body.appendChild(tpl.content);
            const scrollRoot = qs('#settings-scroll-root');
            if (scrollRoot) {
                scrollRoot.innerHTML = [
                    renderSettingsPanelGeneral(),
                    renderSettingsPanelSystem(),
                    basicPanel('customization', 'Customization', 'Theme / accent color / layout settings (TBD).'),
                    basicPanel('account', 'Account', 'Account information & profile (TBD).'),
                    basicPanel('plan', 'Plan & Billing', 'Subscription management (TBD).'),
                    basicPanel('privacy', 'Data & Privacy', 'Data retention and export controls (TBD).'),
                    basicPanel('referral', 'Referral', 'Invite friends to gain quota (TBD).'),
                    basicPanel('help', 'Help center', 'FAQ & support contact (TBD).'),
                    signOutPanel()
                ].join('\n');
            }
            wireSettingsModal();
            // 注入后增强下拉框视觉与交互（仅指定的几个）
            enhanceSettingsSelects();
            injected = true;
        })
        .catch(err => { console.error('Settings modal load failed:', err); showSettingsLoadError(err); });
    return injectingPromise;
}

export async function openSettingsModal() {
    if (!injected) {
        await initSettingsModal();
    }
    const overlay = qs('#settings-overlay');
    if (!overlay) return;
    overlay.classList.remove('hidden');
    requestAnimationFrame(() => overlay.classList.add('active'));
    qsa('.settings-nav-item').forEach(b => b.classList.toggle('active', b.dataset.panel === 'general'));
    qsa('.settings-panel').forEach(p => p.classList.toggle('hidden', p.dataset.panel !== 'general'));
}

function closeSettingsModal() {
    const overlay = qs('#settings-overlay');
    if (!overlay) return;
    overlay.classList.remove('active');
    setTimeout(() => overlay.classList.add('hidden'), 180);
}

function basicPanel(id, title, desc) {
    return `<section class="settings-panel hidden" data-panel="${id}"><h2 class="panel-heading">${title}</h2><p class="panel-desc">${desc}</p></section>`;
}
function signOutPanel() {
    return `<section class="settings-panel hidden" data-panel="signout"><h2 class="panel-heading">Sign out</h2><p class="panel-desc">确认要登出当前会话？</p><div class="panel-row"><button class="btn danger" id="settings-signout-btn">Sign out</button></div></section>`;
}

function renderSettingsPanelGeneral() {
    return `<section class="settings-panel" data-panel="general">
        <h2 class="panel-heading">通用</h2>
        <div class="panel-block">
            <div class="block-title">快捷键</div>
            <div class="shortcut-previews"><div class="shortcut-preview">
                <div id="shortcut-active-indicator" class="shortcut-indicator off" title="当前识别状态">●</div>
            </div><div class="shortcut-preview"></div></div>
            <ul class="shortcut-list" id="dynamic-shortcut-list">
                ${renderDynamicShortcuts()}
                                <li class="shortcut-row custom-shortcut-row" id="custom-shortcut-row">
                                    <div class="info">
                                        <div class="label">自定义快捷键</div>
                                        <div class="sub" id="custom-shortcut-sub">未设置：可定义一个组合（例如 Ctrl+Shift+K）。设置后默认组合启动和免提启动将失效。</div>
                                    </div>
                                    <div class="actions">
                                        <div class="keys" id="custom-shortcut-display"><span class="keycap muted">未设置</span></div>
                                        <button class="text-btn" id="record-custom-shortcut-btn">记录</button>
                                        <button class="text-btn danger" id="clear-custom-shortcut-btn" style="display:none;">清除</button>
                                    </div>
                                </li>
            </ul>
            <div class="shortcut-hint" style="margin-top:8px;font-size:12px;opacity:.7;">
                如需修改此组合，请稍后在“系统”面板开放自定义；当前实现遵循：Windows/Linux = Ctrl + Win；macOS = Ctrl + Command；双击/单击规则已内置。
            </div>
        </div>
        <div class="panel-block">
      <div class="block-title">模型</div>
      <div class="form-grid">
        ${selectField('转录模型', 'setting-transcription-source', ['在线模型', '本地模型'])}
        <div class="field-group hidden" id="selected-model-row">
          <label class="field-label">选择模型</label>
          <div class="field-inline"><select class="setting-select" id="setting-model"><option>中等模型 (默认)</option><option>小模型（快速）</option><option>大模型（准确度高）</option></select><button class="btn ghost small" id="download-model-btn">下载模型</button></div>
        </div>
        ${selectField('输出语言', 'setting-language', ['Auto Detect', 'Chinese', 'English', 'Japanese'])}
      </div>
    </div>
    <div class="panel-block">
      <div class="block-title">更新</div>
      <div class="panel-row gap">
        <div class="update-box"><div class="label">检查更新</div><div class="sub" id="current-version">Version 0.1.0</div></div>
        <button class="btn primary small" id="check-updates-btn">检查更新</button>
        <div class="update-box"><div class="label">遇到问题？</div><div class="sub">请分享日志或反馈问题</div></div>
        <button class="btn ghost small" id="share-logs-btn">Share logs</button>
      </div>
    </div>
  </section>`;
}

function shortcutItem(label, sub, k1, k2, k3, isCancelable) {
    const keys = [k1, k2, k3].filter(Boolean).map(k => `<span class="keycap">${k}</span>`).join('');
    return `<li class="shortcut-row ${isCancelable ? 'cancel-row' : ''}"><div class="info"><div class="label">${label}</div><div class="sub">${sub}</div></div><div class="actions"><div class="keys">${keys}</div>${isCancelable ? '<button class="text-btn reset-btn" data-action="reset-cancel">取消</button>' : ''}</div></li>`;
}

// ---- 新增：根据平台渲染实际使用的快捷键规则 ----
function detectPlatform() {
    const p = navigator.platform.toLowerCase();
    if (p.includes('mac')) return 'mac';
    if (p.includes('win')) return 'win';
    return 'linux';
}

function renderDynamicShortcuts() {
    const plat = detectPlatform();
    if (plat === 'mac') {
        // mac: Ctrl + Command 组合启动；双击 Option 启动；（激活中）单击 Option 结束
        return [
            shortcutItem('组合启动', '按下 Control + Command 立即开始识别。', '⌃', '⌘'),
            shortcutItem('免提启动', '快速双击 ⌥ (Option) 开始识别。', '⌥', '⌥'),
            // shortcutItem('结束识别', '识别进行中，单击一次 ⌥ 即可结束。', '⌥'),
            // shortcutItem('取消录音', '正在识别时按 Esc 取消（开发中）。', 'ESC', null, null, true)
        ].join('');
    }
    // Windows / Linux: Ctrl + Win 组合启动；双击 Ctrl 启动；（激活中）单击 Ctrl 结束
    return [
        shortcutItem('组合启动', '按下 Ctrl + Win 立即开始识别，松开结束。', 'Ctrl', 'Win'),
        shortcutItem('免提启动', '快速双击 Ctrl 开始识别，再次单击Ctrl结束。', 'Ctrl', 'Ctrl'),
        // shortcutItem('结束识别', '识别进行中，单击一次 Ctrl 即可结束。', 'Ctrl'),
        // shortcutItem('取消录音', '正在识别时按 Esc 取消（开发中）。', 'ESC', null, null, true)
    ].join('');
}

// 识别状态指示灯更新（来自 recognition.js 的事件）
function initRecognitionIndicator() {
    const el = document.getElementById('shortcut-active-indicator');
    if (!el) return;
    function setActive(active) {
        el.classList.toggle('on', active);
        el.classList.toggle('off', !active);
        el.style.color = active ? 'var(--accent, #4ade80)' : 'var(--gray-500, #777)';
        el.title = active ? '识别中（由全局快捷键触发）' : '未识别';
    }
    document.addEventListener('recognition:start', () => setActive(true));
    document.addEventListener('recognition:stop', () => setActive(false));
    // 初始状态
    setActive(false);
}

function selectField(label, id, options) {
    return `<div class="field-group"><label for="${id}" class="field-label">${label}</label><select id="${id}" class="setting-select">${options.map(o => `<option>${o}</option>`).join('')}</select></div>`;
}

function renderSettingsPanelSystem() {
    return `<section class="settings-panel hidden" data-panel="system">
    <h2 class="panel-heading">系统</h2>
    <div class="panel-block">
        <div class="block-title">音频</div>
        <div class="audio-mic-group">
            <div class="panel-subtitle">输入设备</div>
            <div class="form-grid">${selectField('麦克风', 'setting-mic', ['系统默认'])}</div>
            <div class="mic-status" id="mic-status" aria-live="polite">正在检测麦克风设备…</div>
        </div>
        <div class="audio-switches-sep"></div>
        ${toggleRow('音效', '开始或停止语音识别时播放提示音。', 'sound-effects')}
        ${toggleRow('静音系统音频', '开始录音时自动将系统媒体音量静音。', 'mute-media')}
    </div>
    <div class="panel-block">
        <div class="block-title">系统行为</div>
        ${toggleRow('开机自动启动', '开机后自动启动应用。', 'open-login')}
        ${toggleRow('录音时防止睡眠', '录音过程中防止系统进入睡眠，避免中断。', 'prevent-sleep', true)}
        ${toggleRow('在任务栏/停靠栏中显示图标', '始终在任务栏或停靠栏中显示应用图标，便于快速打开。', 'dock-icon', true)}
        ${toggleRow('显示侧边悬停录音面板', '闲置时将录音面板停靠在屏幕边缘，随时唤出。', 'monophone', true)}
        ${toggleRow('兼容非标准键盘', '为非标准键盘启用额外兼容逻辑。', 'nonstd-kb')}
    </div>
</section>`;
}

function toggleRow(label, sub, id, active) {
    return `<div class="toggle-row" data-id="${id}"><div class="info"><div class="label">${label}</div><div class="sub">${sub}</div></div><button class="switch ${active ? 'active' : ''}" role="switch" aria-checked="${active ? 'true' : 'false'}" data-role="toggle"><span></span></button></div>`;
}

function wireSettingsModal() {
    const overlay = qs('#settings-overlay');
    const closeBtn = qs('#settings-close');
    const nav = qs('#settings-nav');
    function onKey(e) { if (e.key === 'Escape') { closeSettingsModal(); } }
    closeBtn.addEventListener('click', closeSettingsModal);
    overlay.addEventListener('mousedown', e => { if (e.target === overlay) closeSettingsModal(); });
    document.addEventListener('keydown', onKey);
    nav.addEventListener('click', e => {
        const btn = e.target.closest('.settings-nav-item');
        if (!btn) return;
        const panel = btn.dataset.panel;
        qsa('.settings-nav-item').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        qsa('.settings-panel').forEach(p => p.classList.toggle('hidden', p.dataset.panel !== panel));
    });
    overlay.addEventListener('click', e => {
        const resetBtn = e.target.closest('[data-action="reset-cancel"]');
        if (resetBtn) { /* TODO: implement reset */ }
        const switchBtn = e.target.closest('.switch');
        if (switchBtn && switchBtn.dataset.role === 'toggle') {
            switchBtn.classList.toggle('active');
            switchBtn.setAttribute('aria-checked', switchBtn.classList.contains('active') ? 'true' : 'false');
        }
    });
    const srcSelect = qs('#setting-transcription-source');
    const modelRow = qs('#selected-model-row');
    srcSelect?.addEventListener('change', () => {
        if (srcSelect.value.toLowerCase() === 'local') modelRow.classList.remove('hidden'); else modelRow.classList.add('hidden');
    });

    // ---- Microphone dynamic enumeration & preference persistence ----
    const micSelect = qs('#setting-mic');
    if (micSelect) {
        // Restore saved value
        const saved = localStorage.getItem('pref.mic');
        if (saved) {
            // value may be added after enumeration
            micSelect.value = saved;
        }
        micSelect.addEventListener('change', () => {
            localStorage.setItem('pref.mic', micSelect.value);
            const st = qs('#mic-status');
            if (st) {
                st.textContent = `当前输入设备：${micSelect.value}`;
            }
            // 尝试同步到后端（若运行在 Tauri 环境中）
            if (window.__TAURI__?.core?.invoke) {
                window.__TAURI__.core.invoke('set_mic_preference', { name: micSelect.value }).catch(() => { });
            }
        });
        enumerateMicrophones(micSelect, saved).catch(err => {
            const st = qs('#mic-status');
            if (st) st.textContent = `设备枚举失败：${err.message}`;
        });
    }

    // 初始化备用快捷键逻辑
    initCustomShortcutUI();
}

// 在面板渲染后尝试初始化指示灯（若存在）
document.addEventListener('DOMContentLoaded', () => {
    // settings 模态首次打开时才会真正插入，但如果已存在则绑定
    setTimeout(() => { try { initRecognitionIndicator(); } catch { } }, 0);
});

async function enumerateMicrophones(selectEl, savedValue) {
    const status = qs('#mic-status');

    // 优先通过 Tauri 命令从 Rust 端获取真实设备列表
    if (window.__TAURI__?.core?.invoke) {
        try {
            if (status) status.textContent = '正在从后端获取设备列表…';
            const info = await window.__TAURI__.core.invoke('get_input_devices');
            const devices = Array.isArray(info?.devices) ? info.devices : [];
            const preferred = info?.preferred || savedValue || '';
            const def = info?.default || '系统默认';

            const currentVal = preferred || selectEl.value || def;

            // 先清空旧的动态选项（保留第一个“系统默认”）
            Array.from(selectEl.querySelectorAll('option')).forEach((o, idx) => { if (idx > 0) o.remove(); });
            devices.forEach(name => {
                const opt = document.createElement('option');
                opt.value = name;
                opt.textContent = name;
                selectEl.appendChild(opt);
            });

            // 恢复或设置当前值
            if ([...selectEl.options].some(o => o.value === currentVal)) {
                selectEl.value = currentVal;
            } else {
                selectEl.value = '系统默认';
            }

            // 触发 change 以同步 UI 与偏好
            selectEl.dispatchEvent(new Event('change'));

            if (status) {
                if (devices.length) {
                    status.textContent = `当前输入设备：${selectEl.value}`;
                } else {
                    status.textContent = '未找到可用麦克风';
                }
            }
            return;
        } catch (err) {
            if (status) status.textContent = `从后端获取设备失败：${err?.message || err}`;
            // 若后端失败则退回到浏览器枚举
        }
    }

    // 回退方案：使用浏览器 mediaDevices 枚举（在普通浏览器调试时仍可工作）
    if (!navigator.mediaDevices?.enumerateDevices) {
        if (status) status.textContent = '当前环境不支持媒体设备 API';
        return;
    }
    if (status) status.textContent = '正在检测麦克风设备…';
    let devices;
    try {
        await navigator.mediaDevices.getUserMedia({ audio: true }).catch(() => { /* ignore if user denies; we still try enumerate */ });
        devices = await navigator.mediaDevices.enumerateDevices();
    } catch (err) {
        if (status) status.textContent = '无法访问音频设备';
        throw err;
    }
    const mics = devices.filter(d => d.kind === 'audioinput');
    const currentVal = selectEl.value;
    Array.from(selectEl.querySelectorAll('option')).forEach((o, idx) => { if (idx > 0) o.remove(); });
    mics.forEach(d => {
        const opt = document.createElement('option');
        const label = d.label || `麦克风 ${selectEl.children.length}`;
        opt.value = label;
        opt.textContent = label;
        selectEl.appendChild(opt);
    });
    if ([...selectEl.options].some(o => o.value === currentVal)) {
        selectEl.value = currentVal;
    }
    selectEl.dispatchEvent(new Event('change'));
    if (status) {
        if (mics.length) {
            const chosen = selectEl.value;
            status.textContent = `当前输入设备：${chosen}`;
        } else {
            status.textContent = '未找到可用麦克风';
        }
    }
}

function showSettingsLoadError(err) {
    const root = qs('#settings-scroll-root');
    if (!root) return;
    root.innerHTML = `<div class="panel" style="text-align:center;gap:16px;">
        <h2 class="panel-title" style="margin-top:0;">加载失败</h2>
        <p style="opacity:.7;font-size:13px;">${(err?.message || '网络错误')}。<br>请检查网络连接后重试。</p>
        <button class="btn primary" id="settings-retry-btn">重试加载</button>
    </div>`;
    qs('#settings-retry-btn')?.addEventListener('click', () => {
        // 重新触发加载
        injected = false; injectingPromise = null;
        ensureSettingsSpinner();
        openSettingsModal();
    });
}

function ensureSettingsSpinner() {
    const root = qs('#settings-scroll-root');
    if (!root) return;
    // 如果已存在内容或 spinner 不重复插入
    if (root.querySelector('#settings-loading')) return;
    fetch('./components/spinner.html')
        .then(r => r.text())
        .then(html => { root.innerHTML = html; })
        .catch(() => { root.innerHTML = '<div style="padding:40px 0;text-align:center;font-size:13px;opacity:.7;">Loading…</div>'; });
}

// 导出关闭函数供特殊场景使用（暂未在 main 中显式使用）
export { closeSettingsModal };

// ================= 自定义备用快捷键逻辑 =================
function initCustomShortcutUI() {
    const recordBtn = qs('#record-custom-shortcut-btn');
    const clearBtn = qs('#clear-custom-shortcut-btn');
    const display = qs('#custom-shortcut-display');
    const sub = qs('#custom-shortcut-sub');
    if (!recordBtn || !clearBtn || !display) return;

    const LS_KEY = 'pref.customShortcut';
    let recording = false;
    let recordIndicatorTimeout = null;

    const saved = localStorage.getItem(LS_KEY);
    if (saved) {
        applyCustomShortcutUI(saved);
        // 尝试告知后端（若刷新后状态丢失）
        invokeRust('set_custom_shortcut', { accelerator: saved }).catch(() => { });
    }

    recordBtn.addEventListener('click', () => {
        if (recording) return;
        recording = true;
        display.innerHTML = '<span class="keycap recording">按下组合…</span>';
        recordBtn.disabled = true;
        recordBtn.textContent = '等待…';
        sub && (sub.textContent = '请同时按下修饰键 + 主键（Esc 取消）');
    });

    clearBtn.addEventListener('click', () => {
        invokeRust('clear_custom_shortcut', {}).then(() => {
            localStorage.removeItem(LS_KEY);
            display.innerHTML = '<span class="keycap muted">未设置</span>';
            recordBtn.style.display = '';
            recordBtn.disabled = false;
            recordBtn.textContent = '记录';
            clearBtn.style.display = 'none';
            sub && (sub.textContent = '未设置：可定义一个组合（例如 Ctrl+Shift+K）。设置后默认 Ctrl+Win / 双击规则将被覆盖。');
        }).catch(err => {
            flashError('清除失败: ' + (err?.message || err));
        });
    });

    window.addEventListener('keydown', onCapture, true);
    window.addEventListener('keyup', onKeyUp, true);

    function onKeyUp(e) {
        if (!recording) return;
        // 防止 modifier 抬起导致再次触发
        e.stopPropagation();
        e.preventDefault();
    }

    function onCapture(e) {
        if (!recording) return;
        // 阻止传播，避免影响其它逻辑
        e.stopPropagation();
        e.preventDefault();
        if (e.key === 'Escape') {
            cancelRecording();
            return;
        }
        const isModifier = ['Shift', 'Control', 'Alt', 'Meta'].includes(e.key);
        // 等待主键（非纯修饰）
        if (isModifier) {
            showPressedPreview(e);
            return;
        }
        // 构造 accelerator
        const accel = buildAccelerator(e);
        if (!accel) {
            flashError('无法识别该按键');
            cancelRecording();
            return;
        }
        invokeRust('set_custom_shortcut', { accelerator: accel }).then(() => {
            localStorage.setItem(LS_KEY, accel);
            applyCustomShortcutUI(accel);
        }).catch(err => {
            flashError('设置失败: ' + (err?.message || err));
            cancelRecording();
        });
    }

    function applyCustomShortcutUI(accel) {
        display.innerHTML = accel.split('+').map(k => `<span class="keycap">${escapeHtml(k)}</span>`).join('');
        recordBtn.style.display = 'none';
        clearBtn.style.display = '';
        clearBtn.disabled = false;
        recording = false;
        recordBtn.disabled = false;
        recordBtn.textContent = '记录';
        sub && (sub.textContent = '已设置自定义快捷键：默认组合与双击方案已禁用。');
    }

    function cancelRecording() {
        recording = false;
        recordBtn.disabled = false;
        recordBtn.textContent = '记录';
        const has = !!localStorage.getItem(LS_KEY);
        if (!has) display.innerHTML = '<span class="keycap muted">未设置</span>';
        else applyCustomShortcutUI(localStorage.getItem(LS_KEY));
        sub && (sub.textContent = has ? '已设置自定义快捷键：默认组合与双击方案已禁用。' : '未设置：可定义一个组合（例如 Ctrl+Shift+K）。设置后默认 Ctrl+Win / 双击规则将被覆盖。');
    }

    function buildAccelerator(e) {
        const parts = [];
        if (e.ctrlKey) parts.push('Ctrl');
        if (e.altKey) parts.push(isMac() ? 'Option' : 'Alt');
        if (e.shiftKey) parts.push('Shift');
        if (e.metaKey) parts.push(isMac() ? 'Command' : 'Win');
        const main = normalizeMainKey(e);
        if (!main) return null;
        parts.push(main);
        return parts.join('+');
    }

    function showPressedPreview(e) {
        // 动态显示已按下修饰键
        const parts = [];
        if (e.ctrlKey || e.key === 'Control') parts.push('Ctrl');
        if (e.altKey || e.key === 'Alt') parts.push(isMac() ? 'Option' : 'Alt');
        if (e.shiftKey || e.key === 'Shift') parts.push('Shift');
        if (e.metaKey || e.key === 'Meta') parts.push(isMac() ? 'Command' : 'Win');
        if (!parts.length) return;
        display.innerHTML = parts.map(k => `<span class="keycap">${k}</span>`).join('');
    }

    function normalizeMainKey(e) {
        const k = e.key;
        if (k.length === 1) {
            const upper = k.toUpperCase();
            if (/^[A-Z0-9]$/.test(upper)) return upper; // 字母或数字
        }
        if (/^F\d{1,2}$/.test(k)) return k.toUpperCase();
        if (k === ' ') return 'Space';
        if (k === 'Escape') return 'Escape';
        if (k === 'Tab') return 'Tab'; // 可选支持
        return null;
    }

    function isMac() { return navigator.platform.toLowerCase().includes('mac'); }

    function invokeRust(cmd, args) {
        if (window.__TAURI__?.core?.invoke) {
            return window.__TAURI__.core.invoke(cmd, args);
        }
        return Promise.reject(new Error('Tauri API 不可用'));
    }

    function flashError(msg) {
        if (!display) return;
        const prev = display.innerHTML;
        display.innerHTML = `<span class="keycap error" style="background:#fee;color:#c00;">${escapeHtml(msg)}</span>`;
        clearTimeout(recordIndicatorTimeout);
        recordIndicatorTimeout = setTimeout(() => { display.innerHTML = prev; }, 1800);
    }

    function escapeHtml(str) { return str.replace(/[&<>"]+/g, s => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[s])); }
}
