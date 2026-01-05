# @monobuck/achievements

MonoBuck 勋章系统 - 功能完整的成就系统，支持浏览器和 Node.js 环境。

## 🌟 特性

- ✅ **零依赖** - 纯 JavaScript 实现，无外部依赖
- 🎮 **游戏化** - 完整的勋章系统，包含稀有度、主题分类
- 🎨 **创意命名** - 富有文化内涵的勋章名称和故事
- 📊 **数据分析** - 详细的统计和进度追踪
- 🔄 **可扩展** - 支持自定义勋章定义和存储适配器
- 📱 **UI 组件** - 开箱即用的 UI 组件库
- 💾 **数据管理** - 导入导出、分享功能
- 🎯 **智能提示** - 下一目标提示和进度计算

## 📦 安装

```bash
# 如果发布到 npm
npm install @monobuck/achievements

# 或者直接使用相对路径
import EnhancedAchievementEngine from './packages/achievements/enhanced-engine.js';
```

## 🚀 快速开始

### 基础使用

```javascript
import { 
    EnhancedAchievementEngine, 
    EnhancedLocalStorageStore,
    CREATIVE_DEFINITIONS 
} from '@monobuck/achievements';

// 创建引擎实例
const engine = new EnhancedAchievementEngine({
    definitions: CREATIVE_DEFINITIONS,
    store: new EnhancedLocalStorageStore()
});

// 记录一次使用
const result = await engine.onTranscriptionComplete(500, 10, { perfect: true });

console.log('统计数据:', result.stats);
console.log('新解锁勋章:', result.unlocked);
console.log('下一目标:', result.nextTargets);
console.log('勋章故事:', result.stories);
```

### UI 组件使用

```javascript
import { AchievementGrid, AchievementStatsPanel } from '@monobuck/achievements/ui-components';

// 创建勋章网格
const grid = new AchievementGrid('#badge-container', {
    showFilters: true,
    showSearch: true,
    onShare: (badgeId) => {
        console.log('分享勋章:', badgeId);
    }
});

// 设置勋章数据
grid.setDefinitions(CREATIVE_DEFINITIONS);
grid.setUnlockedBadges(unlockedBadges);

// 创建统计面板
const statsPanel = new AchievementStatsPanel('#stats-container');
const detailedStats = await engine.getDetailedStats();
statsPanel.setStats(detailedStats);
```

## 📚 API 文档

### EnhancedAchievementEngine

增强版勋章引擎，继承自基础引擎并添加了扩展功能。

#### 构造函数

```javascript
const engine = new EnhancedAchievementEngine({
    definitions: CREATIVE_DEFINITIONS,  // 勋章定义数组
    store: new EnhancedLocalStorageStore(),  // 存储适配器
    stories: BADGE_STORIES,  // 勋章故事
    themes: BADGE_THEMES,    // 主题分类
    enableAnalytics: true    // 是否启用分析
});
```

#### 主要方法

##### `onTranscriptionComplete(words, duration, options)`

记录一次使用会话并评估勋章解锁。

```javascript
const result = await engine.onTranscriptionComplete(500, 10, {
    perfect: true,  // 是否完美记录
    // 其他自定义选项
});

// 返回值
{
    stats: { /* 用户统计数据 */ },
    unlocked: [ /* 新解锁的勋章 */ ],
    nextTargets: { /* 下一目标 */ },
    analytics: { /* 分析数据 */ },
    stories: { /* 勋章故事 */ },
    themes: { /* 主题进度 */ }
}
```

##### `getDetailedStats()`

获取详细的统计信息。

```javascript
const stats = await engine.getDetailedStats();

// 返回值
{
    basic: { /* 基础统计 */ },
    achievements: { /* 勋章统计 */ },
    rarity: { /* 稀有度分布 */ },
    themes: { /* 主题进度 */ },
    analytics: { /* 分析数据 */ },
    nextTargets: { /* 下一目标 */ }
}
```

##### `generateShareData(badgeId)`

生成勋章分享数据。

```javascript
const shareData = await engine.generateShareData('usage-100');

// 返回值
{
    badge: { /* 勋章信息 */ },
    user: { /* 用户信息 */ },
    shareText: "分享文本",
    shareUrl: "分享链接"
}
```

##### `exportData(format)`

导出用户数据。

```javascript
const exportResult = await engine.exportData('json');

// 返回值
{
    data: { /* 完整数据 */ },
    filename: "achievements-2023-12-01.json",
    mimeType: "application/json",
    content: "JSON字符串"
}
```

##### `importData(data)`

导入用户数据。

```javascript
const result = await engine.importData(importedData);

// 返回值
{
    success: true,
    imported: {
        stats: true,
        badges: 15,
        analytics: true
    }
}
```

### EnhancedLocalStorageStore

增强版本地存储适配器。

```javascript
const store = new EnhancedLocalStorageStore('my-app-achievements');

// 基础方法
await store.getUserStats();
await store.setUserStats(stats);
await store.getUnlocked();
await store.addUnlocked(badges);

// 增强方法
await store.getAnalytics();
await store.setAnalytics(analytics);
await store.clearAll();
const size = store.getStorageSize();
```

### UI 组件

#### AchievementBadge

单个勋章组件。

```javascript
const badge = new AchievementBadge(definition, {
    showTooltip: true,
    showShare: true,
    showProgress: true,
    stories: BADGE_STORIES
});

badge.setUnlocked(true, '2023-12-01T10:00:00Z');
badge.setProgress({ current: 50, target: 100, percentage: 50 });

const element = badge.render();
document.body.appendChild(element);
```

#### AchievementGrid

勋章网格组件。

```javascript
const grid = new AchievementGrid('#container', {
    columns: 'auto-fill',
    minWidth: '280px',
    showFilters: true,
    showSearch: true,
    onShare: (badgeId) => { /* 分享回调 */ },
    onClick: (badgeId) => { /* 点击回调 */ }
});

grid.setDefinitions(definitions);
grid.setUnlockedBadges(unlockedBadges);
grid.addUnlockedBadge(newBadge);
```

#### AchievementStatsPanel

统计面板组件。

```javascript
const panel = new AchievementStatsPanel('#stats', {
    showRarityDistribution: true,
    showThemeProgress: true,
    showMiniWall: true
});

panel.setStats(detailedStats);
```

## 🎨 勋章系统

### 稀有度等级

- **普通** (common) - 绿色，基础成就
- **优秀** (uncommon) - 深绿，进阶成就  
- **稀有** (rare) - 蓝色，挑战成就
- **史诗** (epic) - 紫色，困难成就
- **传奇** (legendary) - 橙色，极限成就
- **限定** (limited) - 渐变，特殊成就

### 主题分类

- **修行之路** - 使用次数相关勋章
- **时光印记** - 时长相关勋章
- **文采飞扬** - 字数相关勋章
- **坚持之美** - 连续性相关勋章
- **昼夜精灵** - 特殊时间勋章
- **品格之光** - 行为品质勋章

### 预设勋章

系统包含 47 个预设勋章，涵盖：

- 使用次数：从"🌱 初入江湖"到"💫 神话再现"
- 累计时长：从"🕐 分秒必争"到"🏔️ 登峰造极"
- 累计字数：从"📜 初露锋芒"到"✨ 笔走龙蛇"
- 连续天数：从"🌱 初心不改"到"🌌 五载春秋"
- 特殊行为：夜猫子、早起鸟、完美主义者等

## 🔧 自定义

### 自定义勋章定义

```javascript
const customDefinitions = [
    {
        id: 'custom-badge-1',
        name: '🎯 自定义勋章',
        rarity: 'epic',
        criteria: [
            { type: 'totalUsage', op: '>=', value: 50 },
            { type: 'currentStreak', op: '>=', value: 7 }
        ]
    }
];

const engine = new EnhancedAchievementEngine({
    definitions: customDefinitions
});
```

### 自定义存储适配器

```javascript
class CustomStore {
    async getUserStats() {
        // 实现获取用户统计
    }
    
    async setUserStats(stats) {
        // 实现保存用户统计
    }
    
    async getUnlocked() {
        // 实现获取已解锁勋章
    }
    
    async addUnlocked(badges) {
        // 实现添加解锁勋章
    }
}

const engine = new EnhancedAchievementEngine({
    store: new CustomStore()
});
```

### 自定义 UI 样式

```css
/* 覆盖默认样式 */
.achievement-badge {
    border-radius: 16px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.1);
}

.achievement-badge.unlocked {
    background: linear-gradient(135deg, #667eea, #764ba2);
    color: white;
}
```

## 📱 完整示例

查看 `achievement-dashboard-enhanced.html` 获取完整的集成示例。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License