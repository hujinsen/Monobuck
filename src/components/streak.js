// Streak Badge module
// Responsibilities: fetch streak data, render badge, report activity events
// Safe to call init multiple times.

const TIERS = [
    { threshold: 1, name: 'Seed' },
    { threshold: 3, name: 'Sprout' },
    { threshold: 7, name: 'Leafy' },
    { threshold: 14, name: 'Branch' },
    { threshold: 30, name: 'Grove' },
    { threshold: 60, name: 'Evergreen' }
];

function qs(sel, ctx = document) { return ctx.querySelector(sel); }

function computeMilestone(streak) {
    let tier = 0; let name = TIERS[0].name; let nextThreshold = null;
    for (let i = 0; i < TIERS.length; i++) {
        if (streak >= TIERS[i].threshold) { tier = i; name = TIERS[i].name; }
        else { nextThreshold = TIERS[i].threshold; break; }
    }
    return { tier, name, nextThreshold, nextTierIn: nextThreshold ? nextThreshold - streak : null };
}

function loadCache() { try { return JSON.parse(localStorage.getItem('streakSnapshot') || 'null'); } catch { return null; } }
function saveCache(data) { try { localStorage.setItem('streakSnapshot', JSON.stringify(data)); } catch { } }

export async function initStreakBadge() {
    const el = qs('#streak-badge');
    if (!el) return; // no badge placeholder yet
    const cached = loadCache();
    if (cached) renderBadge(cached);
    // fetch fresh (backend may not be ready; fallback to mock)
    try {
        const res = await fetch('/api/streak');
        if (!res.ok) throw new Error('HTTP ' + res.status);
        const data = await res.json();
        saveCache(data);
        renderBadge(data, true);
    } catch (err) {
        // fallback mock (do not overwrite existing cache if any)
        if (!cached) {
            const mock = { currentStreak: 1, bestStreak: 1, todayActive: true, milestone: computeMilestone(1) };
            renderBadge(mock);
        }
    }
}

export function reportActivity(words, durationSec) {
    // minimal throttle: skip if both zero
    if (!words && !durationSec) return;
    // send event (backend optional)
    fetch('/api/activity/log', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ words, durationSec, timestamp: Math.floor(Date.now() / 1000) })
    }).catch(() => { });
}

function renderBadge(data, fresh) {
    const el = qs('#streak-badge'); if (!el) return;
    const streak = data.currentStreak || 0;
    const todayActive = !!data.todayActive;
    const milestone = data.milestone || computeMilestone(streak);
    el.className = `streak-badge tier-${milestone.tier}` + (todayActive ? '' : ' inactive') + (fresh && milestone.tier > 0 ? ' upgrade' : '');
    qs('.streak-count', el).textContent = String(streak);
    qs('.streak-label', el).textContent = milestone.name;
    qs('.streak-next', el).textContent = milestone.nextTierIn ? `再 ${milestone.nextTierIn} 天升级` : '最高级';
}

// Optional helper for manual refresh
export async function refreshStreak() { await initStreakBadge(); }
