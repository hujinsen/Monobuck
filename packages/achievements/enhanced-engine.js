// @monobuck/achievements - Enhanced Engine with Extended Features
// ESM, no external deps

import { CREATIVE_DEFINITIONS, BADGE_STORIES, BADGE_THEMES } from './creative-definitions.js';

/**
 * Rarity palette aligned to project design (no gray)
 */
export const RARITY = {
  common:    { name: '普通', color: '#4ade80' },
  uncommon:  { name: '优秀', color: '#16a34a' },
  rare:      { name: '稀有', color: '#0891b2' },
  epic:      { name: '史诗', color: '#9333ea' },
  legendary: { name: '传奇', color: '#f59e0b' },
  limited:   { name: '限定', color: 'linear-gradient(45deg,#ff6b6b,#4ecdc4,#45b7d1,#96ceb4)' }
};

/** Default ladders */
export const LADDERS = {
  USAGE:    [1, 10, 50, 100, 500, 1000, 5000, 10000, 50000, 100000],
  DURATION: [1, 10, 30, 60, 300, 1200, 6000, 30000, 60000],
  WORDS:    [100, 1000, 5000, 10000, 50000, 100000, 500000, 1000000, 5000000],
  STREAK:   [1, 3, 7, 15, 30, 60, 100, 365, 730, 1825]
};

/** Default user stats */
export function defaultUserStats() {
  return {
    totalUsage: 0,
    totalDuration: 0, // minutes
    totalWords: 0,
    currentStreak: 0,
    bestStreak: 0,
    nightUsage: 0,
    morningUsage: 0,
    consecutivePerfect: 0,
    lastActiveDate: null,
    todayWords: 0,
    todayUsage: 0
  };
}

/** Utility: date helpers */
function formatDateKey(d = new Date()) { return d.toISOString().slice(0, 10); }
function isNightTime(date = new Date()) {
  const h = date.getHours();
  return h >= 0 && h < 5;
}
function isMorningTime(date = new Date()) {
  const h = date.getHours();
  return h >= 5 && h < 8;
}

/** Get next target value from ladder */
export function getNextFromLadder(ladder, current) {
  return ladder.find(v => v > current) ?? null;
}

/** High-level next targets */
export function getNextTargets(userStats, ladders = LADDERS) {
  return {
    nextUsage:    getNextFromLadder(ladders.USAGE,    userStats.totalUsage || 0),
    nextDuration: getNextFromLadder(ladders.DURATION, userStats.totalDuration || 0),
    nextWords:    getNextFromLadder(ladders.WORDS,    userStats.totalWords || 0),
    nextStreak:   getNextFromLadder(ladders.STREAK,   userStats.currentStreak || 0)
  };
}

/** Minimal store adapter interface */
export class MemoryStore {
  constructor(initial = {}) {
    this.state = { userStats: defaultUserStats(), unlocked: [], ...initial };
  }
  async getUserStats() { return this.state.userStats; }
  async setUserStats(next) { this.state.userStats = { ...next }; }
  async getUnlocked() { return [...this.state.unlocked]; }
  async addUnlocked(items) { this.state.unlocked.push(...items); }
}

/** Achievement definition helpers */
function normalizeAchievement(def) {
  // Allow shorthand by id like 'words-1000', 'streak-30', 'duration-600' (minutes), 'usage-100'
  if (!def.criteria && typeof def.id === 'string') {
    const [key, raw] = def.id.split('-');
    const val = Number(raw);
    let crit = null;
    if (key === 'words') crit = { type: 'totalWords', op: '>=', value: val };
    if (key === 'streak') crit = { type: 'currentStreak', op: '>=', value: val };
    if (key === 'duration') crit = { type: 'totalDuration', op: '>=', value: val };
    if (key === 'usage') crit = { type: 'totalUsage', op: '>=', value: val };
    if (crit) return { ...def, criteria: [crit] };
  }
  return { ...def, criteria: def.criteria || [] };
}

function evaluateDefinition(def, userStats, context) {
  return (def.criteria || []).every(c => compareMetric(getMetricValue(c.type, userStats, context), c.op, c.value));
}

function getMetricValue(type, stats, ctx) {
  switch (type) {
    case 'totalUsage': return stats.totalUsage || 0;
    case 'totalDuration': return stats.totalDuration || 0;
    case 'totalWords': return stats.totalWords || 0;
    case 'currentStreak': return stats.currentStreak || 0;
    case 'nightUsage': return stats.nightUsage || 0;
    case 'morningUsage': return stats.morningUsage || 0;
    case 'dailyWords': return ctx.todayWords || 0;
    case 'consecutivePerfect': return stats.consecutivePerfect || 0;
    default: return 0;
  }
}

function compareMetric(actual, op, value) {
  if (op === '>=') return actual >= value;
  if (op === '==') return actual === value;
  if (op === '>') return actual > value;
  if (op === '<=') return actual <= value;
  if (op === '<') return actual < value;
  return false;
}

function dayDiffKeys(keyA, keyB) {
  const a = new Date(keyA + 'T00:00:00Z');
  const b = new Date(keyB + 'T00:00:00Z');
  return Math.round((b - a) / 86400000);
}

/** Base Achievement Engine */
export class AchievementEngine {
  /**
   * @param {Object} options
   * @param {Array} options.definitions - list of achievement definitions
   * @param {Object} options.ladders - custom ladders
   * @param {Object} options.rarity - rarity palette
   * @param {Object} options.store - async store with get/set API
   */
  constructor({ definitions = [], ladders = LADDERS, rarity = RARITY, store = new MemoryStore() } = {}) {
    this.definitions = definitions.map(normalizeAchievement);
    this.ladders = ladders;
    this.rarity = rarity;
    this.store = store;
  }

  /** Record a session and evaluate achievements */
  async onTranscriptionComplete(words, durationMinutes, options = {}) {
    const now = new Date();
    const todayKey = formatDateKey(now);
    const stats = await this.store.getUserStats();

    // usage count per session
    stats.totalUsage += 1;

    // duration and words
    const minutes = Math.max(0, Number(durationMinutes) || 0);
    const w = Math.max(0, Number(words) || 0);
    stats.totalDuration += minutes;
    stats.totalWords += w;

    // day rollover and streak
    const lastKey = stats.lastActiveDate;
    if (!lastKey) {
      stats.currentStreak = 1;
    } else {
      const dayDiff = dayDiffKeys(lastKey, todayKey);
      if (dayDiff === 1) stats.currentStreak += 1;
      else if (dayDiff >= 2) stats.currentStreak = 1; // reset
    }
    stats.bestStreak = Math.max(stats.bestStreak, stats.currentStreak);
    stats.lastActiveDate = todayKey;

    // today counters
    if (lastKey !== todayKey) {
      stats.todayWords = 0;
      stats.todayUsage = 0;
    }
    stats.todayWords += w;
    stats.todayUsage += 1;

    // special time buckets
    if (isNightTime(now)) stats.nightUsage += 1;
    if (isMorningTime(now)) stats.morningUsage += 1;

    // consecutive perfect
    if (options.perfect) stats.consecutivePerfect = (stats.consecutivePerfect || 0) + 1;
    else stats.consecutivePerfect = 0;

    // persist
    await this.store.setUserStats(stats);

    // evaluate
    const context = { todayWords: stats.todayWords, session: { words: w, duration: minutes, isNight: isNightTime(now), isMorning: isMorningTime(now) } };
    const newOnes = await this.evaluateAndUnlock(stats, context);

    return { stats, unlocked: newOnes, nextTargets: getNextTargets(stats, this.ladders) };
  }

  async evaluateAndUnlock(userStats, context) {
    const unlocked = await this.store.getUnlocked();
    const unlockedIds = new Set(unlocked.map(a => a.id));
    const newly = [];

    for (const def of this.definitions) {
      if (unlockedIds.has(def.id)) continue;
      if (evaluateDefinition(def, userStats, context)) {
        newly.push({ id: def.id, rarity: def.rarity, unlockedAt: new Date().toISOString() });
      }
    }

    if (newly.length) await this.store.addUnlocked(newly);
    return newly;
  }
}

/**
 * Enhanced Achievement Engine with extended features
 */
export class EnhancedAchievementEngine extends AchievementEngine {
    constructor(options = {}) {
        super({
            definitions: options.definitions || CREATIVE_DEFINITIONS,
            ladders: options.ladders || LADDERS,
            rarity: options.rarity || RARITY,
            store: options.store || new EnhancedLocalStorageStore()
        });
        
        this.stories = options.stories || BADGE_STORIES;
        this.themes = options.themes || BADGE_THEMES;
        this.enableAnalytics = options.enableAnalytics !== false;
        
        // 分析数据
        this.analytics = {
            sessionCount: 0,
            totalUnlocks: 0,
            lastSession: null,
            unlockHistory: []
        };
        
        this.loadAnalytics();
    }
    
    /** 加载分析数据 */
    async loadAnalytics() {
        if (this.enableAnalytics && this.store.getAnalytics) {
            this.analytics = await this.store.getAnalytics();
        }
    }
    
    /** 保存分析数据 */
    async saveAnalytics() {
        if (this.enableAnalytics && this.store.setAnalytics) {
            await this.store.setAnalytics(this.analytics);
        }
    }
    
    /** 增强版会话记录 */
    async onTranscriptionComplete(words, durationMinutes, options = {}) {
        const result = await super.onTranscriptionComplete(words, durationMinutes, options);
        
        // 更新分析数据
        if (this.enableAnalytics) {
            this.analytics.sessionCount++;
            this.analytics.lastSession = new Date().toISOString();
            
            if (result.unlocked.length > 0) {
                this.analytics.totalUnlocks += result.unlocked.length;
                this.analytics.unlockHistory.push({
                    timestamp: new Date().toISOString(),
                    badges: result.unlocked.map(b => b.id),
                    sessionData: { words, duration: durationMinutes, ...options }
                });
                
                // 保持历史记录在合理范围内
                if (this.analytics.unlockHistory.length > 100) {
                    this.analytics.unlockHistory = this.analytics.unlockHistory.slice(-100);
                }
            }
            
            await this.saveAnalytics();
        }
        
        // 添加扩展信息
        result.analytics = this.analytics;
        result.stories = this.getStoriesForBadges(result.unlocked);
        result.themes = this.getThemeProgress();
        
        return result;
    }
    
    /** 获取勋章故事 */
    getStoriesForBadges(badges) {
        return badges.reduce((stories, badge) => {
            if (this.stories[badge.id]) {
                stories[badge.id] = this.stories[badge.id];
            }
            return stories;
        }, {});
    }
    
    /** 获取主题进度 */
    async getThemeProgress() {
        const unlocked = await this.store.getUnlocked();
        const unlockedIds = new Set(unlocked.map(b => b.id));
        
        return Object.entries(this.themes).reduce((progress, [themeId, theme]) => {
            const totalBadges = theme.badges.length;
            const unlockedBadges = theme.badges.filter(id => unlockedIds.has(id)).length;
            
            progress[themeId] = {
                ...theme,
                progress: unlockedBadges,
                total: totalBadges,
                percentage: Math.round((unlockedBadges / totalBadges) * 100)
            };
            
            return progress;
        }, {});
    }
    
    /** 获取稀有度分布 */
    async getRarityDistribution() {
        const unlocked = await this.store.getUnlocked();
        const rarityCount = {};
        const rarityTotal = {};
        
        // 统计总数
        this.definitions.forEach(def => {
            rarityTotal[def.rarity] = (rarityTotal[def.rarity] || 0) + 1;
        });
        
        // 统计已解锁
        unlocked.forEach(badge => {
            const def = this.definitions.find(d => d.id === badge.id);
            if (def) {
                rarityCount[def.rarity] = (rarityCount[def.rarity] || 0) + 1;
            }
        });
        
        return Object.keys(this.rarity).reduce((dist, rarity) => {
            dist[rarity] = {
                unlocked: rarityCount[rarity] || 0,
                total: rarityTotal[rarity] || 0,
                percentage: rarityTotal[rarity] ? 
                    Math.round(((rarityCount[rarity] || 0) / rarityTotal[rarity]) * 100) : 0
            };
            return dist;
        }, {});
    }
    
    /** 获取详细统计 */
    async getDetailedStats() {
        const stats = await this.store.getUserStats();
        const unlocked = await this.store.getUnlocked();
        const rarityDist = await this.getRarityDistribution();
        const themeProgress = await this.getThemeProgress();
        
        return {
            basic: stats,
            achievements: {
                total: this.definitions.length,
                unlocked: unlocked.length,
                percentage: Math.round((unlocked.length / this.definitions.length) * 100)
            },
            rarity: rarityDist,
            themes: themeProgress,
            analytics: this.analytics,
            nextTargets: getNextTargets(stats, this.ladders)
        };
    }
    
    /** 生成分享数据 */
    async generateShareData(badgeId) {
        const def = this.definitions.find(d => d.id === badgeId);
        if (!def) return null;
        
        const unlocked = await this.store.getUnlocked();
        const badge = unlocked.find(b => b.id === badgeId);
        if (!badge) return null;
        
        return {
            badge: {
                id: def.id,
                name: def.name,
                rarity: def.rarity,
                rarityName: this.rarity[def.rarity]?.name,
                story: this.stories[def.id],
                unlockedAt: badge.unlockedAt
            },
            user: {
                totalBadges: unlocked.length,
                totalDefinitions: this.definitions.length,
                completionRate: Math.round((unlocked.length / this.definitions.length) * 100)
            },
            shareText: this.generateShareText(def, badge),
            shareUrl: this.generateShareUrl(def, badge)
        };
    }
    
    /** 生成分享文本 */
    generateShareText(def, badge) {
        const story = this.stories[def.id];
        const rarityName = this.rarity[def.rarity]?.name;
        
        let text = `🏆 我刚刚解锁了勋章：${def.name}`;
        if (rarityName) {
            text += ` (${rarityName})`;
        }
        if (story) {
            text += `\n\n${story}`;
        }
        text += '\n\n#勋章系统 #成就解锁';
        
        return text;
    }
    
    /** 生成分享URL */
    generateShareUrl(def, badge) {
        const text = encodeURIComponent(this.generateShareText(def, badge));
        return `https://twitter.com/intent/tweet?text=${text}`;
    }
    
    /** 导出数据 */
    async exportData(format = 'json') {
        const stats = await this.getDetailedStats();
        const unlocked = await this.store.getUnlocked();
        
        const exportData = {
            version: '2.0.0',
            exportTime: new Date().toISOString(),
            userStats: stats.basic,
            unlockedBadges: unlocked,
            analytics: this.analytics,
            achievements: stats.achievements,
            rarity: stats.rarity,
            themes: stats.themes
        };
        
        if (format === 'json') {
            return {
                data: exportData,
                filename: `achievements-${new Date().toISOString().split('T')[0]}.json`,
                mimeType: 'application/json',
                content: JSON.stringify(exportData, null, 2)
            };
        }
        
        // 可以扩展其他格式
        return exportData;
    }
    
    /** 导入数据 */
    async importData(importData) {
        try {
            // 验证数据格式
            if (!importData.userStats || !importData.unlockedBadges) {
                throw new Error('Invalid data format');
            }
            
            // 导入用户统计
            await this.store.setUserStats(importData.userStats);
            
            // 导入解锁勋章
            if (this.store.setUnlocked) {
                await this.store.setUnlocked(importData.unlockedBadges);
            } else {
                // 兼容旧版本存储
                await this.store.addUnlocked(importData.unlockedBadges);
            }
            
            // 导入分析数据
            if (importData.analytics && this.enableAnalytics) {
                this.analytics = importData.analytics;
                await this.saveAnalytics();
            }
            
            return {
                success: true,
                imported: {
                    stats: true,
                    badges: importData.unlockedBadges.length,
                    analytics: !!importData.analytics
                }
            };
        } catch (error) {
            return {
                success: false,
                error: error.message
            };
        }
    }
}

/**
 * Enhanced LocalStorage Store with additional features
 */
export class EnhancedLocalStorageStore extends MemoryStore {
    constructor(keyPrefix = 'achievement-enhanced') {
        super();
        this.keyPrefix = keyPrefix;
        this.loadFromStorage();
    }
    
    /** 从localStorage加载数据 */
    loadFromStorage() {
        try {
            const stats = this.read('stats', defaultUserStats());
            const unlocked = this.read('unlocked', []);
            
            this.state = {
                userStats: stats,
                unlocked: unlocked
            };
        } catch (error) {
            console.warn('Failed to load from localStorage:', error);
        }
    }
    
    /** 读取数据 */
    read(key, fallback) {
        try {
            const data = localStorage.getItem(`${this.keyPrefix}:${key}`);
            return data ? JSON.parse(data) : fallback;
        } catch {
            return fallback;
        }
    }
    
    /** 写入数据 */
    write(key, data) {
        try {
            localStorage.setItem(`${this.keyPrefix}:${key}`, JSON.stringify(data));
        } catch (error) {
            console.warn('Failed to write to localStorage:', error);
        }
    }
    
    /** 获取用户统计 */
    async getUserStats() {
        return this.state.userStats;
    }
    
    /** 设置用户统计 */
    async setUserStats(stats) {
        this.state.userStats = { ...stats };
        this.write('stats', this.state.userStats);
    }
    
    /** 获取已解锁勋章 */
    async getUnlocked() {
        return [...this.state.unlocked];
    }
    
    /** 添加解锁勋章 */
    async addUnlocked(badges) {
        this.state.unlocked.push(...badges);
        this.write('unlocked', this.state.unlocked);
    }
    
    /** 设置解锁勋章（覆盖） */
    async setUnlocked(badges) {
        this.state.unlocked = [...badges];
        this.write('unlocked', this.state.unlocked);
    }
    
    /** 获取分析数据 */
    async getAnalytics() {
        return this.read('analytics', {
            sessionCount: 0,
            totalUnlocks: 0,
            lastSession: null,
            unlockHistory: []
        });
    }
    
    /** 设置分析数据 */
    async setAnalytics(analytics) {
        this.write('analytics', analytics);
    }
    
    /** 清除所有数据 */
    async clearAll() {
        const keys = ['stats', 'unlocked', 'analytics'];
        keys.forEach(key => {
            localStorage.removeItem(`${this.keyPrefix}:${key}`);
        });
        
        this.state = {
            userStats: defaultUserStats(),
            unlocked: []
        };
    }
    
    /** 获取存储大小 */
    getStorageSize() {
        let total = 0;
        const keys = ['stats', 'unlocked', 'analytics'];
        
        keys.forEach(key => {
            const data = localStorage.getItem(`${this.keyPrefix}:${key}`);
            if (data) {
                total += data.length;
            }
        });
        
        return {
            bytes: total,
            kb: Math.round(total / 1024 * 100) / 100,
            mb: Math.round(total / 1024 / 1024 * 100) / 100
        };
    }
}

/**
 * Achievement Utilities - Helper functions for UI integration
 */
export class AchievementUtils {
    constructor(engine) {
        this.engine = engine;
    }
    
    /** 获取勋章条件描述 */
    getBadgeConditions(def) {
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
    
    /** 计算勋章进度 */
    async calculateBadgeProgress(def) {
        const stats = await this.engine.store.getUserStats();
        
        if (!def.criteria || def.criteria.length === 0) {
            // 根据ID推断进度
            const [type, value] = def.id.split('-');
            const target = parseInt(value);
            let current = 0;
            
            switch (type) {
                case 'usage':
                    current = stats.totalUsage || 0;
                    break;
                case 'duration':
                    current = stats.totalDuration || 0;
                    break;
                case 'words':
                    current = stats.totalWords || 0;
                    break;
                case 'streak':
                    current = stats.currentStreak || 0;
                    break;
            }
            
            return {
                current,
                target,
                percentage: Math.min(100, (current / target) * 100)
            };
        }
        
        // 处理复杂条件
        const criterion = def.criteria[0]; // 简化处理，只取第一个条件
        let current = 0;
        
        switch (criterion.type) {
            case 'totalUsage':
                current = stats.totalUsage || 0;
                break;
            case 'totalDuration':
                current = stats.totalDuration || 0;
                break;
            case 'totalWords':
                current = stats.totalWords || 0;
                break;
            case 'currentStreak':
                current = stats.currentStreak || 0;
                break;
            case 'nightUsage':
                current = stats.nightUsage || 0;
                break;
            case 'morningUsage':
                current = stats.morningUsage || 0;
                break;
            case 'consecutivePerfect':
                current = stats.consecutivePerfect || 0;
                break;
            case 'dailyWords':
                current = stats.todayWords || 0;
                break;
        }
        
        return {
            current,
            target: criterion.value,
            percentage: Math.min(100, (current / criterion.value) * 100)
        };
    }
    
    /** 生成勋章卡片图片 */
    generateBadgeCard(def, options = {}) {
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        
        const width = options.width || 400;
        const height = options.height || 300;
        canvas.width = width;
        canvas.height = height;
        
        // 绘制背景
        const gradient = ctx.createLinearGradient(0, 0, width, height);
        gradient.addColorStop(0, '#4f46e5');
        gradient.addColorStop(1, '#7c3aed');
        ctx.fillStyle = gradient;
        ctx.fillRect(0, 0, width, height);
        
        // 绘制勋章名称
        ctx.fillStyle = 'white';
        ctx.font = `bold ${Math.floor(width / 16)}px Arial`;
        ctx.textAlign = 'center';
        ctx.fillText(def.name, width / 2, height / 2 - 20);
        
        // 绘制稀有度
        const rarityName = this.engine.rarity[def.rarity]?.name || def.rarity;
        ctx.font = `${Math.floor(width / 24)}px Arial`;
        ctx.fillText(rarityName, width / 2, height / 2 + 20);
        
        // 绘制故事（如果有）
        const story = this.engine.stories[def.id];
        if (story) {
            ctx.font = `${Math.floor(width / 32)}px Arial`;
            ctx.fillText(story, width / 2, height / 2 + 60);
        }
        
        return canvas;
    }
    
    /** 格式化时间 */
    formatDuration(minutes) {
        if (minutes < 60) {
            return `${minutes} 分钟`;
        } else if (minutes < 1440) {
            const hours = Math.floor(minutes / 60);
            const mins = minutes % 60;
            return mins > 0 ? `${hours} 小时 ${mins} 分钟` : `${hours} 小时`;
        } else {
            const days = Math.floor(minutes / 1440);
            const hours = Math.floor((minutes % 1440) / 60);
            return hours > 0 ? `${days} 天 ${hours} 小时` : `${days} 天`;
        }
    }
    
    /** 格式化数字 */
    formatNumber(num) {
        if (num >= 1000000) {
            return `${(num / 1000000).toFixed(1)}M`;
        } else if (num >= 1000) {
            return `${(num / 1000).toFixed(1)}K`;
        }
        return num.toString();
    }
}

// 导出所有内容
export {
    CREATIVE_DEFINITIONS,
    BADGE_STORIES,
    BADGE_THEMES
};

// 默认导出增强引擎
export default EnhancedAchievementEngine;