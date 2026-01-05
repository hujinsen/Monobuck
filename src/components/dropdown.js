/**
 * Generic accessible floating dropdown (listbox) module.
 * Usage:
 *   import { dropdownify } from './components/dropdown.js';
 *   dropdownify(selectElement, { maxHeight: 260, onChange: (value, text, selectEl) => {} });
 *
 * Features:
 *  - Replaces visible UI of native <select> with custom trigger + list (keeps hidden original for forms)
 *  - Keyboard: ArrowUp/Down, Home/End, Enter/Space select, Esc close, Tab exit
 *  - ARIA: trigger(button)[aria-haspopup=listbox][aria-expanded], list[role=listbox], option[role=option]
 *  - Auto flip when not enough space below
 *  - Outside click + resize reposition
 *  - Programmatic API: open(select), close(select), destroy(select)
 */

function qs(sel, ctx = document) { return ctx.querySelector(sel); }

const registry = new Map(); // selectEl => state

export function dropdownify(selectEl, opts = {}) {
    if (!selectEl || registry.has(selectEl)) return registry.get(selectEl);
    const options = { maxHeight: 260, onChange: null, ...opts };
    const originalOptions = Array.from(selectEl.querySelectorAll('option'));
    // Hide original select
    selectEl.classList.add('sb-native-hidden');
    selectEl.tabIndex = -1;
    selectEl.setAttribute('aria-hidden', 'true');
    const wrapper = document.createElement('div');
    wrapper.className = 'sb-dropdown';
    const trigger = document.createElement('button');
    trigger.type = 'button';
    trigger.className = 'sb-trigger';
    trigger.setAttribute('aria-haspopup', 'listbox');
    trigger.setAttribute('aria-expanded', 'false');
    trigger.textContent = selectEl.value || (originalOptions[0]?.textContent || 'Select');
    const list = document.createElement('ul');
    list.className = 'sb-list';
    list.setAttribute('role', 'listbox');
    list.tabIndex = -1;
    originalOptions.forEach(o => {
        const li = document.createElement('li');
        li.className = 'sb-option';
        li.setAttribute('role', 'option');
        li.dataset.value = o.value || o.textContent;
        li.textContent = o.textContent;
        if (o.selected) li.classList.add('active');
        li.setAttribute('aria-selected', o.selected ? 'true' : 'false');
        li.addEventListener('mousedown', e => e.preventDefault());
        li.addEventListener('click', () => selectOption(selectEl, trigger, list, li, options));
        list.appendChild(li);
    });
    wrapper.appendChild(trigger);
    wrapper.appendChild(list);
    selectEl.parentElement.insertBefore(wrapper, selectEl);
    const state = { selectEl, wrapper, trigger, list, options };
    registry.set(selectEl, state);
    // events
    trigger.addEventListener('click', () => toggle(state));
    trigger.addEventListener('keydown', e => {
        if (['ArrowDown', 'ArrowUp', ' '].includes(e.key)) { e.preventDefault(); open(state); moveFocus(state.list, e.key === 'ArrowUp' ? 'end' : 'start'); }
    });
    list.addEventListener('keydown', e => handleListKey(e, state));
    return state;
}

// Basic health check for tests (returns number of registered dropdowns)
export function dropdownRegistrySize() { return registry.size; }

function toggle(state) { isOpen(state) ? close(state) : open(state); }
function isOpen(state) { return state.wrapper.classList.contains('open'); }
function open(state) {
    // close others
    registry.forEach(s => { if (s !== state) close(s); });
    state.wrapper.classList.add('open');
    state.trigger.setAttribute('aria-expanded', 'true');
    position(state);
    state.list.focus();
}
function close(state) {
    state.wrapper.classList.remove('open', 'flip');
    state.trigger.setAttribute('aria-expanded', 'false');
}
function position(state) {
    const rect = state.wrapper.getBoundingClientRect();
    state.wrapper.classList.remove('flip');
    const spaceBelow = window.innerHeight - rect.bottom;
    const spaceAbove = rect.top;
    const estHeight = Math.min(state.list.scrollHeight, state.options.maxHeight);
    if (spaceBelow < estHeight && spaceAbove > spaceBelow) state.wrapper.classList.add('flip');
}
function selectOption(selectEl, trigger, list, li, options) {
    Array.from(list.children).forEach(c => { c.classList.remove('active'); c.setAttribute('aria-selected', 'false'); });
    li.classList.add('active');
    li.setAttribute('aria-selected', 'true');
    const value = li.dataset.value;
    selectEl.value = value;
    trigger.textContent = li.textContent;
    selectEl.dispatchEvent(new Event('change'));
    if (typeof options.onChange === 'function') options.onChange(value, li.textContent, selectEl);
    close(registry.get(selectEl));
    trigger.focus();
}
function moveFocus(list, mode) {
    const items = Array.from(list.querySelectorAll('.sb-option'));
    if (!items.length) return;
    let target;
    if (mode === 'start') target = items[0];
    else if (mode === 'end') target = items[items.length - 1];
    else if (typeof mode === 'number') target = items[mode];
    if (target) target.focus();
}
function handleListKey(e, state) {
    const items = Array.from(state.list.querySelectorAll('.sb-option'));
    let idx = items.indexOf(document.activeElement);
    switch (e.key) {
        case 'ArrowDown': e.preventDefault(); idx = Math.min(items.length - 1, idx + 1); items[idx].focus(); break;
        case 'ArrowUp': e.preventDefault(); idx = Math.max(0, idx - 1); items[idx].focus(); break;
        case 'Home': e.preventDefault(); items[0].focus(); break;
        case 'End': e.preventDefault(); items[items.length - 1].focus(); break;
        case 'Enter':
        case ' ': e.preventDefault(); if (document.activeElement.classList.contains('sb-option')) selectOption(state.selectEl, state.trigger, state.list, document.activeElement, state.options); break;
        case 'Escape': e.preventDefault(); close(state); state.trigger.focus(); break;
        case 'Tab': close(state); break;
    }
}

export function openDropdown(selectEl) { const st = registry.get(selectEl); if (st) open(st); }
export function closeDropdown(selectEl) { const st = registry.get(selectEl); if (st) close(st); }
export function destroyDropdown(selectEl) {
    const st = registry.get(selectEl); if (!st) return;
    close(st);
    st.wrapper.remove();
    selectEl.classList.remove('sb-native-hidden');
    selectEl.tabIndex = 0;
    selectEl.removeAttribute('aria-hidden');
    registry.delete(selectEl);
}

document.addEventListener('mousedown', e => {
    registry.forEach(st => { if (!st.wrapper.contains(e.target)) close(st); });
});
window.addEventListener('resize', () => registry.forEach(st => { if (isOpen(st)) position(st); }));

// Utility to bulk initialize by selector
export function dropdownifyAll(selector, opts) { Array.from(document.querySelectorAll(selector)).forEach(el => dropdownify(el, opts)); }
