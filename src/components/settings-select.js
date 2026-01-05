import { dropdownify } from './dropdown.js';

const TARGET_IDS = ['setting-mic', 'setting-transcription-source', 'setting-model', 'setting-language'];

export function enhanceSettingsSelects(root = document) {
    TARGET_IDS.forEach(id => {
        const el = root.querySelector('#' + id);
        if (!el) return;
        dropdownify(el, {
            onChange: (value, text, sel) => {
                // 针对 transcription source 动态显示模型行仍由已有监听处理，这里无需重复
            }
        });
    });
}

if (document.getElementById('settings-overlay')) {
    requestAnimationFrame(() => enhanceSettingsSelects());
}

