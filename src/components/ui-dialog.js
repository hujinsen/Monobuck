/* Global confirm dialog extracted from main.js */
function qs(sel, ctx = document) { return ctx.querySelector(sel); }

export function confirmDialog(opts = {}) {
    const {
        title = '确认',
        message = '确定执行此操作？',
        confirmText = '确定',
        cancelText = '取消',
        danger = false,
        type = 'default'
    } = opts;
    const overlay = qs('#global-modal');
    const titleEl = qs('#global-modal-title');
    const textEl = qs('#global-modal-text');
    const confirmBtn = qs('#global-modal-confirm');
    const cancelBtn = qs('#global-modal-cancel');
    const iconEl = qs('#global-modal-icon');
    if (!overlay || !titleEl || !textEl || !confirmBtn || !cancelBtn) {
        return Promise.resolve(false);
    }
    const iconMap = { info: 'ℹ', success: '✔', warning: '⚠', danger: '✖', default: '❓' };
    const useType = iconMap[type] ? type : 'default';
    if (iconEl) iconEl.textContent = iconMap[useType];
    const modalEl = overlay.querySelector('.modal');
    if (modalEl) modalEl.setAttribute('data-type', useType);
    titleEl.textContent = title;
    textEl.textContent = message;
    confirmBtn.textContent = confirmText;
    cancelBtn.textContent = cancelText;
    confirmBtn.classList.toggle('danger', !!danger);

    let resolveFn; const p = new Promise(r => resolveFn = r);
    const previousActive = document.activeElement;
    let focusables = [];
    function cleanup() {
        confirmBtn.removeEventListener('click', onConfirm);
        cancelBtn.removeEventListener('click', onCancel);
        document.removeEventListener('keydown', onKey);
        overlay.removeEventListener('click', onOutside);
        overlay.classList.remove('active');
        setTimeout(() => overlay.classList.add('hidden'), 180);
        previousActive && previousActive.focus?.();
    }
    function onConfirm() { resolveFn(true); cleanup(); }
    function onCancel() { resolveFn(false); cleanup(); }
    function onKey(e) {
        if (e.key === 'Escape') { onCancel(); return; }
        if (e.key === 'Tab') {
            if (!focusables.length) return;
            const first = focusables[0];
            const last = focusables[focusables.length - 1];
            const active = document.activeElement;
            if (e.shiftKey) { if (active === first) { e.preventDefault(); last.focus(); } }
            else { if (active === last) { e.preventDefault(); first.focus(); } }
        }
    }
    function onOutside(e) { if (e.target === overlay) onCancel(); }
    overlay.classList.remove('hidden');
    requestAnimationFrame(() => overlay.classList.add('active'));
    confirmBtn.focus();
    const selector = 'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
    const scope = overlay.querySelector('.modal');
    focusables = Array.from(scope.querySelectorAll(selector)).filter(el => el.offsetParent !== null);
    confirmBtn.addEventListener('click', onConfirm, { once: true });
    cancelBtn.addEventListener('click', onCancel, { once: true });
    document.addEventListener('keydown', onKey);
    overlay.addEventListener('click', onOutside);
    return p;
}
