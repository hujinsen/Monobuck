// @monobuck/achievements - UI Components
// Reusable UI components for achievement system integration

import { EnhancedAchievementEngine, AchievementUtils, RARITY } from './enhanced-engine.js';

/**
 * Achievement Badge Component
 * Renders a single achievement badge with tooltip and share functionality
 */
export class AchievementBadge {
    constructor(definition, options = {}) {
        this.definition = definition;
        this.options = {
            showTooltip: true,
            showShare: true,
            showProgress: true,
            className: 'achievement-badge',
            ...options
        };
        this.isUnlocked = false;
        this.progress = null;
        this.element = null;
        this.tooltip = null;
    }
    
    /** 设置解锁状态 */
    setUnlocked(unlocked, unlockedAt = null) {
        this.isUnlocked = unlocked;
        this.unlockedAt = unlockedAt;
        this.updateElement();
    }
    
    /** 设置进度 */
    setProgress(progress) {
        this.progress = progress;
        this.updateElement();
    }
    
    /** 渲染元素 */
    render() {
        const def = this.definition;
        const isUnlocked = this.isUnlocked;
        
        this.element = document.createElement('div');
        this.element.className = `${this.options.className} ${isUnlocked ? 'unlocked' : 'locked'}`;
        this.element.dataset.badgeId = def.id;
        
        // 获取emoji图标
        const emoji = def.name.match(/[\u{1F300}-\u{1F9FF}]/u)?.[0] || '🏆';
        
        this.element.innerHTML = `
            <div class="badge-header">
                <div class="badge-icon">${isUnlocked ? emoji : '🔒'}</div>
                <div class="badge-info">
                    <div class="badge-name">${def.name}</div>
                    <div class="badge-rarity rarity-${def.rarity}">
                        ${RARITY[def.rarity]?.name || def.rarity}
                    </div>
                </div>
                ${isUnlocked && this.options.showShare ? 
                    `<button class="share-btn" title="分享勋章">📤</button>` : ''}
            </div>
            
            ${!isUnlocked && this.progress && this.options.showProgress ? `
                <div class="badge-progress">
                    <div class="progress-text">
                        ${this.progress.current} / ${this.progress.target} 
                        (${this.progress.percentage.toFixed(1)}%)
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: ${this.progress.percentage}%"></div>
                    </div>
                </div>
            ` : ''}
            
            ${isUnlocked && this.unlockedAt ? `
                <div class="unlock-time">
                    🎉 ${new Date(this.unlockedAt).toLocaleString()}
                </div>
            ` : ''}
        `;
        
        // 添加事件监听器
        this.attachEventListeners();
        
        return this.element;
    }
    
    /** 更新元素 */
    updateElement() {
        if (this.element) {
            const newElement = this.render();
            this.element.replaceWith(newElement);
        }
    }
    
    /** 添加事件监听器 */
    attachEventListeners() {
        if (!this.element) return;
        
        // Tooltip
        if (this.options.showTooltip) {
            this.element.addEventListener('mouseenter', (e) => this.showTooltip(e));
            this.element.addEventListener('mouseleave', () => this.hideTooltip());
        }
        
        // Share button
        const shareBtn = this.element.querySelector('.share-btn');
        if (shareBtn) {
            shareBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.onShare?.(this.definition.id);
            });
        }
        
        // Click event
        this.element.addEventListener('click', () => {
            this.onClick?.(this.definition.id);
        });
    }
    
    /** 显示Tooltip */
    showTooltip(event) {
        if (!this.options.showTooltip) return;
        
        // 创建tooltip
        this.tooltip = document.createElement('div');
        this.tooltip.className = 'achievement-tooltip';
        
        const conditions = this.getConditions();
        const story = this.options.stories?.[this.definition.id];
        
        this.tooltip.innerHTML = `
            <div class="tooltip-title">${this.definition.name}</div>
            <div class="tooltip-conditions">
                ${conditions.map(c => `<div class="tooltip-condition">• ${c}</div>`).join('')}
            </div>
            ${story ? `<div class="tooltip-story">${story}</div>` : ''}
            ${this.progress && !this.isUnlocked ? `
                <div class="tooltip-progress">
                    <div class="progress-text">
                        进度: ${this.progress.current} / ${this.progress.target} 
                        (${this.progress.percentage.toFixed(1)}%)
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: ${this.progress.percentage}%"></div>
                    </div>
                </div>
            ` : ''}
        `;
        
        // 定位tooltip
        const rect = this.element.getBoundingClientRect();
        this.tooltip.style.position = 'absolute';
        this.tooltip.style.left = `${rect.left + window.scrollX}px`;
        this.tooltip.style.top = `${rect.bottom + window.scrollY + 10}px`;
        this.tooltip.style.zIndex = '1000';
        
        document.body.appendChild(this.tooltip);
        
        // 显示动画
        requestAnimationFrame(() => {
            this.tooltip.classList.add('show');
        });
    }
    
    /** 隐藏Tooltip */
    hideTooltip() {
        if (this.tooltip) {
            this.tooltip.classList.remove('show');
            setTimeout(() => {
                if (this.tooltip && this.tooltip.parentNode) {
                    this.tooltip.parentNode.removeChild(this.tooltip);
                }
                this.tooltip = null;
            }, 300);
        }
    }
    
    /** 获取条件描述 */
    getConditions() {
        const def = this.definition;
        const conditions = [];
        
        if (def.criteria && def.criteria.length > 0) {
            def.criteria.forEach(criterion => {
                let conditionText = '';
                switch (criterion.type) {
                    case 'totalUsage':
                        conditionText = `使用次数达到 ${criterion.value} 次`;
                        break;
                    case 'totalDuration':
                        conditionText = `累计时长达到 ${criterion.value} 分钟`;
                        break;
                    case 'totalWords':
                        conditionText = `累计字数达到 ${criterion.value} 字`;
                        break;
                    case 'currentStreak':
                        conditionText = `连续使用 ${criterion.value} 天`;
                        break;
                    case 'nightUsage':
                        conditionText = `夜间使用 ${criterion.value} 次`;
                        break;
                    case 'morningUsage':
                        conditionText = `早晨使用 ${criterion.value} 次`;
                        break;
                    case 'consecutivePerfect':
                        conditionText = `连续完美记录 ${criterion.value} 次`;
                        break;
                    case 'dailyWords':
                        conditionText = `单日字数达到 ${criterion.value} 字`;
                        break;
                    default:
                        conditionText = `${criterion.type} ${criterion.op} ${criterion.value}`;
                }
                conditions.push(conditionText);
            });
        } else {
            // 根据ID推断条件
            const [type, value] = def.id.split('-');
            const val = parseInt(value);
            switch (type) {
                case 'usage':
                    conditions.push(`使用次数达到 ${val} 次`);
                    break;
                case 'duration':
                    conditions.push(`累计时长达到 ${val} 分钟`);
                    break;
                case 'words':
                    conditions.push(`累计字数达到 ${val} 字`);
                    break;
                case 'streak':
                    conditions.push(`连续使用 ${val} 天`);
                    break;
                default:
                    conditions.push('特殊条件');
            }
        }
        
        return conditions;
    }
}

/**
 * Achievement Grid Component
 * Renders a grid of achievement badges with filtering and search
 */
export class AchievementGrid {
    constructor(container, options = {}) {
        this.container = typeof container === 'string' ? 
            document.querySelector(container) : container;
        this.options = {
            columns: 'auto-fill',
            minWidth: '280px',
            gap: '15px',
            showFilters: true,
            showSearch: true,
            ...options
        };
        
        this.definitions = [];
        this.unlockedBadges = [];
        this.badges = new Map();
        this.currentFilter = 'all';
        this.searchQuery = '';
        
        this.init();
    }
    
    /** 初始化 */
    init() {
        this.container.className = 'achievement-grid-container';
        
        if (this.options.showFilters || this.options.showSearch) {
            this.renderControls();
        }
        
        this.gridElement = document.createElement('div');
        this.gridElement.className = 'achievement-grid';
        this.gridElement.style.display = 'grid';
        this.gridElement.style.gridTemplateColumns = `repeat(${this.options.columns}, minmax(${this.options.minWidth}, 1fr))`;
        this.gridElement.style.gap = this.options.gap;
        
        this.container.appendChild(this.gridElement);
    }
    
    /** 渲染控制器 */
    renderControls() {
        const controls = document.createElement('div');
        controls.className = 'achievement-controls';
        
        if (this.options.showFilters) {
            const filters = document.createElement('div');
            filters.className = 'achievement-filters';
            filters.innerHTML = `
                <button class="filter-btn active" data-filter="all">全部</button>
                <button class="filter-btn" data-filter="unlocked">已解锁</button>
                <button class="filter-btn" data-filter="locked">未解锁</button>
                <button class="filter-btn" data-filter="recent">最近获得</button>
            `;
            
            filters.addEventListener('click', (e) => {
                if (e.target.classList.contains('filter-btn')) {
                    this.setFilter(e.target.dataset.filter);
                    
                    // 更新按钮状态
                    filters.querySelectorAll('.filter-btn').forEach(btn => {
                        btn.classList.remove('active');
                    });
                    e.target.classList.add('active');
                }
            });
            
            controls.appendChild(filters);
        }
        
        if (this.options.showSearch) {
            const search = document.createElement('div');
            search.className = 'achievement-search';
            search.innerHTML = `
                <input type="text" placeholder="搜索勋章..." class="search-input">
            `;
            
            const input = search.querySelector('.search-input');
            input.addEventListener('input', (e) => {
                this.setSearch(e.target.value);
            });
            
            controls.appendChild(search);
        }
        
        this.container.appendChild(controls);
    }
    
    /** 设置勋章定义 */
    setDefinitions(definitions) {
        this.definitions = definitions;
        this.createBadges();
        this.render();
    }
    
    /** 设置已解锁勋章 */
    setUnlockedBadges(unlockedBadges) {
        this.unlockedBadges = unlockedBadges;
        this.updateBadgeStates();
    }
    
    /** 创建勋章组件 */
    createBadges() {
        this.badges.clear();
        
        this.definitions.forEach(def => {
            const badge = new AchievementBadge(def, {
                ...this.options.badgeOptions,
                stories: this.options.stories
            });
            
            // 设置事件回调
            badge.onShare = this.options.onShare;
            badge.onClick = this.options.onClick;
            
            this.badges.set(def.id, badge);
        });
    }
    
    /** 更新勋章状态 */
    updateBadgeStates() {
        const unlockedIds = new Set(this.unlockedBadges.map(b => b.id));
        
        this.badges.forEach((badge, id) => {
            const unlockedBadge = this.unlockedBadges.find(b => b.id === id);
            badge.setUnlocked(unlockedIds.has(id), unlockedBadge?.unlockedAt);
        });
    }
    
    /** 设置勋章进度 */
    async setBadgeProgress(badgeId, progress) {
        const badge = this.badges.get(badgeId);
        if (badge) {
            badge.setProgress(progress);
        }
    }
    
    /** 设置过滤器 */
    setFilter(filter) {
        this.currentFilter = filter;
        this.render();
    }
    
    /** 设置搜索 */
    setSearch(query) {
        this.searchQuery = query.toLowerCase();
        this.render();
    }
    
    /** 渲染网格 */
    render() {
        const filteredBadges = this.getFilteredBadges();
        
        this.gridElement.innerHTML = '';
        
        filteredBadges.forEach(badge => {
            const element = badge.render();
            this.gridElement.appendChild(element);
        });
    }
    
    /** 获取过滤后的勋章 */
    getFilteredBadges() {
        let badges = Array.from(this.badges.values());
        
        // 应用过滤器
        if (this.currentFilter === 'unlocked') {
            badges = badges.filter(badge => badge.isUnlocked);
        } else if (this.currentFilter === 'locked') {
            badges = badges.filter(badge => !badge.isUnlocked);
        } else if (this.currentFilter === 'recent') {
            const recentIds = this.unlockedBadges.slice(-10).map(b => b.id);
            badges = badges.filter(badge => recentIds.includes(badge.definition.id));
        }
        
        // 应用搜索
        if (this.searchQuery) {
            badges = badges.filter(badge => 
                badge.definition.name.toLowerCase().includes(this.searchQuery) ||
                badge.definition.id.toLowerCase().includes(this.searchQuery)
            );
        }
        
        return badges;
    }
    
    /** 添加新解锁的勋章 */
    addUnlockedBadge(badgeData) {
        this.unlockedBadges.push(badgeData);
        
        const badge = this.badges.get(badgeData.id);
        if (badge) {
            badge.setUnlocked(true, badgeData.unlockedAt);
            
            // 添加解锁动画
            if (badge.element) {
                badge.element.style.animation = 'unlockPulse 0.6s ease-out';
                setTimeout(() => {
                    badge.element.style.animation = '';
                }, 600);
            }
        }
    }
}

/**
 * Achievement Stats Panel Component
 * Displays achievement statistics and progress
 */
export class AchievementStatsPanel {
    constructor(container, options = {}) {
        this.container = typeof container === 'string' ? 
            document.querySelector(container) : container;
        this.options = {
            showRarityDistribution: true,
            showThemeProgress: true,
            showMiniWall: true,
            ...options
        };
        
        this.stats = null;
        this.init();
    }
    
    /** 初始化 */
    init() {
        this.container.className = 'achievement-stats-panel';
        this.render();
    }
    
    /** 设置统计数据 */
    setStats(stats) {
        this.stats = stats;
        this.render();
    }
    
    /** 渲染面板 */
    render() {
        if (!this.stats) {
            this.container.innerHTML = '<div class="loading">加载中...</div>';
            return;
        }
        
        let html = '';
        
        // 基础统计
        html += this.renderBasicStats();
        
        // 迷你勋章墙
        if (this.options.showMiniWall) {
            html += this.renderMiniWall();
        }
        
        // 稀有度分布
        if (this.options.showRarityDistribution) {
            html += this.renderRarityDistribution();
        }
        
        // 主题进度
        if (this.options.showThemeProgress) {
            html += this.renderThemeProgress();
        }
        
        this.container.innerHTML = html;
        this.attachEventListeners();
    }
    
    /** 渲染基础统计 */
    renderBasicStats() {
        const { achievements, basic } = this.stats;
        
        return `
            <div class="stats-section">
                <h4>📊 基础统计</h4>
                <div class="stats-grid">
                    <div class="stat-item">
                        <div class="stat-value">${achievements.unlocked}</div>
                        <div class="stat-label">已解锁</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">${achievements.percentage}%</div>
                        <div class="stat-label">完成度</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">${basic.currentStreak || 0}</div>
                        <div class="stat-label">连续天数</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">${basic.totalUsage || 0}</div>
                        <div class="stat-label">使用次数</div>
                    </div>
                </div>
            </div>
        `;
    }
    
    /** 渲染迷你勋章墙 */
    renderMiniWall() {
        // 这里需要传入勋章定义和解锁状态
        return `
            <div class="stats-section">
                <h4>🏆 勋章墙</h4>
                <div class="mini-wall" id="miniWall">
                    <!-- 迷你勋章将通过JavaScript动态生成 -->
                </div>
            </div>
        `;
    }
    
    /** 渲染稀有度分布 */
    renderRarityDistribution() {
        const { rarity } = this.stats;
        
        return `
            <div class="stats-section">
                <h4>💎 稀有度分布</h4>
                <div class="rarity-grid">
                    ${Object.entries(rarity).map(([rarityKey, data]) => `
                        <div class="rarity-item rarity-${rarityKey}">
                            <div class="rarity-count">${data.unlocked}/${data.total}</div>
                            <div class="rarity-name">${RARITY[rarityKey]?.name || rarityKey}</div>
                            <div class="rarity-progress">
                                <div class="progress-bar">
                                    <div class="progress-fill" style="width: ${data.percentage}%"></div>
                                </div>
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }
    
    /** 渲染主题进度 */
    renderThemeProgress() {
        const { themes } = this.stats;
        
        return `
            <div class="stats-section">
                <h4>🎭 主题进度</h4>
                <div class="theme-list">
                    ${Object.entries(themes).map(([themeId, theme]) => `
                        <div class="theme-item">
                            <div class="theme-header">
                                <span class="theme-name">${theme.name}</span>
                                <span class="theme-progress">${theme.progress}/${theme.total}</span>
                            </div>
                            <div class="progress-bar">
                                <div class="progress-fill" style="width: ${theme.percentage}%"></div>
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }
    
    /** 添加事件监听器 */
    attachEventListeners() {
        // 可以添加点击事件等
    }
}

/**
 * Default CSS Styles
 * Basic styles for achievement components
 */
export const DEFAULT_STYLES = `
/* Achievement Badge Styles */
.achievement-badge {
    background: white;
    border: 2px solid #e5e7eb;
    border-radius: 12px;
    padding: 20px;
    transition: all 0.3s ease;
    cursor: pointer;
    position: relative;
}

.achievement-badge.unlocked {
    border-color: #10b981;
    box-shadow: 0 4px 20px rgba(16, 185, 129, 0.2);
}

.achievement-badge.locked {
    opacity: 0.6;
    background: #f9fafb;
}

.badge-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 12px;
}

.badge-icon {
    font-size: 2rem;
    margin-right: 10px;
}

.badge-info {
    flex: 1;
}

.badge-name {
    font-weight: 700;
    color: #1e293b;
    font-size: 16px;
    margin-bottom: 4px;
}

.badge-rarity {
    padding: 4px 8px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
}

.rarity-common { background: #dcfce7; color: #166534; }
.rarity-uncommon { background: #d1fae5; color: #065f46; }
.rarity-rare { background: #cffafe; color: #164e63; }
.rarity-epic { background: #e9d5ff; color: #581c87; }
.rarity-legendary { background: #fef3c7; color: #92400e; }

.share-btn {
    background: #3b82f6;
    color: white;
    border: none;
    width: 30px;
    height: 30px;
    border-radius: 50%;
    cursor: pointer;
    opacity: 0;
    transition: opacity 0.3s;
}

.achievement-badge:hover .share-btn {
    opacity: 1;
}

.badge-progress {
    margin-top: 12px;
}

.progress-bar {
    background: #e5e7eb;
    height: 4px;
    border-radius: 2px;
    overflow: hidden;
    margin-top: 4px;
}

.progress-fill {
    background: linear-gradient(90deg, #4f46e5, #7c3aed);
    height: 100%;
    transition: width 0.3s ease;
}

.unlock-time {
    font-size: 11px;
    color: #10b981;
    margin-top: 8px;
}

/* Tooltip Styles */
.achievement-tooltip {
    position: absolute;
    background: #1e293b;
    color: white;
    padding: 16px;
    border-radius: 12px;
    box-shadow: 0 10px 30px rgba(0,0,0,0.3);
    max-width: 320px;
    opacity: 0;
    transform: translateY(10px);
    transition: all 0.3s ease;
    z-index: 1000;
}

.achievement-tooltip.show {
    opacity: 1;
    transform: translateY(0);
}

.tooltip-title {
    font-weight: 700;
    color: #fbbf24;
    margin-bottom: 8px;
}

.tooltip-condition {
    margin-bottom: 6px;
    color: #e2e8f0;
}

.tooltip-story {
    margin-top: 8px;
    color: #94a3b8;
    font-style: italic;
}

/* Grid Styles */
.achievement-grid-container {
    width: 100%;
}

.achievement-controls {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
    gap: 20px;
}

.achievement-filters {
    display: flex;
    gap: 8px;
}

.filter-btn {
    padding: 8px 16px;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    background: white;
    cursor: pointer;
    transition: all 0.2s;
}

.filter-btn.active,
.filter-btn:hover {
    background: #4f46e5;
    color: white;
    border-color: #4f46e5;
}

.search-input {
    padding: 8px 12px;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    min-width: 200px;
}

/* Stats Panel Styles */
.achievement-stats-panel {
    background: white;
    border-radius: 12px;
    padding: 20px;
}

.stats-section {
    margin-bottom: 25px;
}

.stats-section h4 {
    margin-bottom: 12px;
    color: #374151;
    font-size: 14px;
    font-weight: 600;
}

.stats-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
}

.stat-item {
    text-align: center;
    padding: 12px;
    background: #f8fafc;
    border-radius: 8px;
}

.stat-value {
    font-size: 1.5rem;
    font-weight: bold;
    color: #4f46e5;
}

.stat-label {
    font-size: 12px;
    color: #6b7280;
    margin-top: 4px;
}

.rarity-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 8px;
}

.rarity-item {
    padding: 8px;
    background: #f8fafc;
    border-radius: 6px;
    text-align: center;
}

.theme-item {
    margin-bottom: 12px;
}

.theme-header {
    display: flex;
    justify-content: space-between;
    margin-bottom: 4px;
    font-size: 13px;
}

/* Animations */
@keyframes unlockPulse {
    0% { transform: scale(1); }
    50% { transform: scale(1.05); }
    100% { transform: scale(1); }
}
`;

// 自动注入样式
if (typeof document !== 'undefined') {
    const styleSheet = document.createElement('style');
    styleSheet.textContent = DEFAULT_STYLES;
    document.head.appendChild(styleSheet);
}