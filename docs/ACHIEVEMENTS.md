# MonoBuck 勋章系统设计方案

> 基于多维度激励的勋章体系，通过四个核心维度 + 特色勋章，为用户提供全方位的成就感和持续使用动力。

## 1. 设计理念

### 核心思路
- 多维度覆盖：使用次数、使用时长、转录字数、使用天数四个核心维度
- 阶梯式进阶：从入门到专家级别的合理数值梯度设计
- 特色场景：夜猫子、节日等特殊时间段勋章增加趣味性
- 视觉层次：通过稀有度和色彩体系营造收集欲望

### 参考标杆
- 微信读书：精美的勋章视觉设计和合理的获取难度
- QQ音乐：多维度的成就体系和社交分享功能

## 2. 四大核心维度

### 2.1 使用次数勋章
**阶梯设计**：1, 10, 50, 100, 500, 1000, 5000, 10000, 50000, 100000

```javascript
const USAGE_COUNT_ACHIEVEMENTS = [
  { id: 'usage-1', name: '初次体验', count: 1, rarity: 'common' },
  { id: 'usage-10', name: '入门用户', count: 10, rarity: 'common' },
  { id: 'usage-50', name: '熟练用户', count: 50, rarity: 'uncommon' },
  { id: 'usage-100', name: '百次达人', count: 100, rarity: 'uncommon' },
  { id: 'usage-500', name: '资深用户', count: 500, rarity: 'rare' },
  { id: 'usage-1000', name: '千次专家', count: 1000, rarity: 'rare' },
  { id: 'usage-5000', name: '转录大师', count: 5000, rarity: 'epic' },
  { id: 'usage-10000', name: '万次传奇', count: 10000, rarity: 'epic' },
  { id: 'usage-50000', name: '超级用户', count: 50000, rarity: 'legendary' },
  { id: 'usage-100000', name: '终极大师', count: 100000, rarity: 'legendary' }
];
```

### 2.2 使用时长勋章
**阶梯设计**：1分钟, 10分钟, 30分钟, 1小时, 5小时, 20小时, 100小时, 500小时, 1000小时

```javascript
const DURATION_ACHIEVEMENTS = [
  { id: 'duration-1', name: '初试锋芒', minutes: 1, rarity: 'common' },
  { id: 'duration-10', name: '小试牛刀', minutes: 10, rarity: 'common' },
  { id: 'duration-30', name: '半小时达人', minutes: 30, rarity: 'uncommon' },
  { id: 'duration-60', name: '一小时专家', minutes: 60, rarity: 'uncommon' },
  { id: 'duration-300', name: '五小时大师', minutes: 300, rarity: 'rare' },
  { id: 'duration-1200', name: '二十小时传奇', minutes: 1200, rarity: 'rare' },
  { id: 'duration-6000', name: '百小时英雄', minutes: 6000, rarity: 'epic' },
  { id: 'duration-30000', name: '五百小时王者', minutes: 30000, rarity: 'epic' },
  { id: 'duration-60000', name: '千小时宗师', minutes: 60000, rarity: 'legendary' }
];
```

### 2.3 转录字数勋章
**阶梯设计**：100, 1000, 5000, 10000, 50000, 100000, 500000, 1000000, 5000000

```javascript
const WORDS_ACHIEVEMENTS = [
  { id: 'words-100', name: '百字新手', words: 100, rarity: 'common' },
  { id: 'words-1000', name: '千字达人', words: 1000, rarity: 'common' },
  { id: 'words-5000', name: '五千字专家', words: 5000, rarity: 'uncommon' },
  { id: 'words-10000', name: '万字大师', words: 10000, rarity: 'uncommon' },
  { id: 'words-50000', name: '五万字传奇', words: 50000, rarity: 'rare' },
  { id: 'words-100000', name: '十万字英雄', words: 100000, rarity: 'rare' },
  { id: 'words-500000', name: '五十万字王者', words: 500000, rarity: 'epic' },
  { id: 'words-1000000', name: '百万字宗师', words: 1000000, rarity: 'epic' },
  { id: 'words-5000000', name: '五百万字神话', words: 5000000, rarity: 'legendary' }
];
```

### 2.4 使用天数勋章
**阶梯设计**：1, 3, 7, 15, 30, 60, 100, 365, 730, 1825

```javascript
const STREAK_ACHIEVEMENTS = [
  { id: 'streak-1', name: '初来乍到', days: 1, rarity: 'common' },
  { id: 'streak-3', name: '三日坚持', days: 3, rarity: 'common' },
  { id: 'streak-7', name: '一周达人', days: 7, rarity: 'uncommon' },
  { id: 'streak-15', name: '半月专家', days: 15, rarity: 'uncommon' },
  { id: 'streak-30', name: '月度冠军', days: 30, rarity: 'rare' },
  { id: 'streak-60', name: '双月大师', days: 60, rarity: 'rare' },
  { id: 'streak-100', name: '百日传奇', days: 100, rarity: 'epic' },
  { id: 'streak-365', name: '年度英雄', days: 365, rarity: 'epic' },
  { id: 'streak-730', name: '两年王者', days: 730, rarity: 'legendary' },
  { id: 'streak-1825', name: '五年宗师', days: 1825, rarity: 'legendary' }
];
```

## 3. 特色勋章系统

### 3.1 特殊时间段勋章
```javascript
const SPECIAL_TIME_ACHIEVEMENTS = [
  {
    id: 'night-owl-10',
    name: '夜猫子',
    description: '深夜时段(00:00-05:00)使用10次',
    timeRange: '00:00-05:00',
    count: 10,
    rarity: 'uncommon'
  },
  {
    id: 'night-owl-50',
    name: '深夜达人',
    description: '深夜时段(00:00-05:00)使用50次',
    timeRange: '00:00-05:00',
    count: 50,
    rarity: 'rare'
  },
  {
    id: 'early-bird-10',
    name: '早起鸟',
    description: '清晨时段(05:00-08:00)使用10次',
    timeRange: '05:00-08:00',
    count: 10,
    rarity: 'uncommon'
  }
];
```

### 3.2 节日勋章
```javascript
const FESTIVAL_ACHIEVEMENTS = [
  {
    id: 'spring-festival',
    name: '春节快乐',
    description: '春节期间使用MonoBuck',
    festival: '春节',
    rarity: 'limited'
  },
  {
    id: 'mid-autumn',
    name: '中秋团圆',
    description: '中秋节期间使用MonoBuck',
    festival: '中秋节',
    rarity: 'limited'
  },
  {
    id: 'dragon-boat',
    name: '端午安康',
    description: '端午节期间使用MonoBuck',
    festival: '端午节',
    rarity: 'limited'
  },
  {
    id: 'new-year',
    name: '新年新气象',
    description: '元旦期间使用MonoBuck',
    festival: '元旦',
    rarity: 'limited'
  }
];
```

### 3.3 行为特色勋章
```javascript
const BEHAVIOR_ACHIEVEMENTS = [
  {
    id: 'perfectionist-5',
    name: '完美主义者',
    description: '连续5次无错误转录',
    criteria: { type: 'consecutivePerfect', value: 5 },
    rarity: 'uncommon'
  },
  {
    id: 'persistent-7',
    name: '坚持不懈',
    description: '连续7天都有使用记录',
    criteria: { type: 'consecutiveDays', value: 7 },
    rarity: 'rare'
  },
  {
    id: 'daily-hero-1000',
    name: '单日英雄',
    description: '单日转录字数超过1000字',
    criteria: { type: 'dailyWords', value: 1000 },
    rarity: 'uncommon'
  }
];
```

## 4. 稀有度与色彩体系

### 4.1 稀有度分级
```javascript
const RARITY_SYSTEM = {
  common: {
    name: '普通',
    color: '#4ade80',      // 浅绿 - 清新感
    description: '入门级成就',
    glowEffect: 'none'
  },
  uncommon: {
    name: '优秀',
    color: '#16a34a',      // 深绿 - 品牌主色
    description: '进阶级成就',
    glowEffect: 'subtle'
  },
  rare: {
    name: '稀有',
    color: '#0891b2',      // 蓝绿 - 进阶感
    description: '高级成就',
    glowEffect: 'moderate'
  },
  epic: {
    name: '史诗',
    color: '#9333ea',      // 紫色 - 稀有感
    description: '专家级成就',
    glowEffect: 'strong'
  },
  legendary: {
    name: '传奇',
    color: '#f59e0b',      // 金橙 - 传奇感
    description: '大师级成就',
    glowEffect: 'intense'
  },
  limited: {
    name: '限定',
    color: 'linear-gradient(45deg, #ff6b6b, #4ecdc4, #45b7d1, #96ceb4)', // 彩虹渐变
    description: '限时特殊成就',
    glowEffect: 'rainbow'
  }
};
```

### 4.2 视觉动效规范
```css
/* 稀有度对应的视觉效果 */
.achievement-common { 
  border: 2px solid #4ade80; 
}

.achievement-uncommon { 
  border: 2px solid #16a34a;
  box-shadow: 0 0 10px rgba(22, 163, 74, 0.3);
}

.achievement-rare { 
  border: 2px solid #0891b2;
  box-shadow: 0 0 15px rgba(8, 145, 178, 0.4);
}

.achievement-epic { 
  border: 2px solid #9333ea;
  box-shadow: 0 0 20px rgba(147, 51, 234, 0.5);
  animation: epicGlow 2s ease-in-out infinite alternate;
}

.achievement-legendary { 
  border: 2px solid #f59e0b;
  box-shadow: 0 0 25px rgba(245, 158, 11, 0.6);
  animation: legendaryGlow 1.5s ease-in-out infinite alternate;
}

.achievement-limited { 
  border: 2px solid transparent;
  background: linear-gradient(45deg, #ff6b6b, #4ecdc4, #45b7d1, #96ceb4);
  animation: rainbowGlow 3s linear infinite;
}
```

## 5. 核心算法实现

### 5.1 成就评估系统
```javascript
// 统一成就评估函数
function evaluateAchievement(achievement, userStats, context) {
  const { type, value } = achievement.criteria;
  
  switch (type) {
    case 'totalUsage':
      return userStats.totalUsage >= value;
    case 'totalDuration':
      return userStats.totalDuration >= value;
    case 'totalWords':
      return userStats.totalWords >= value;
    case 'consecutiveDays':
      return userStats.currentStreak >= value;
    case 'nightUsage':
      return userStats.nightUsage >= value;
    case 'dailyWords':
      return context.todayWords >= value;
    case 'consecutivePerfect':
      return userStats.consecutivePerfect >= value;
    default:
      return false;
  }
}

// 获取下一目标
function getNextTargets(userStats) {
  const ladders = {
    USAGE: [1, 10, 50, 100, 500, 1000, 5000, 10000, 50000, 100000],
    DURATION: [1, 10, 30, 60, 300, 1200, 6000, 30000, 60000],
    WORDS: [100, 1000, 5000, 10000, 50000, 100000, 500000, 1000000, 5000000],
    STREAK: [1, 3, 7, 15, 30, 60, 100, 365, 730, 1825]
  };
  
  const getNext = (ladder, current) => ladder.find(val => val > current) || null;
  
  return {
    nextUsage: getNext(ladders.USAGE, userStats.totalUsage || 0),
    nextDuration: getNext(ladders.DURATION, userStats.totalDuration || 0),
    nextWords: getNext(ladders.WORDS, userStats.totalWords || 0),
    nextStreak: getNext(ladders.STREAK, userStats.currentStreak || 0)
  };
}
```

### 5.2 事件驱动接口
```javascript
// 转录完成事件处理
function onTranscriptionComplete(words, durationMinutes, options = {}) {
  const userStats = getUserStats();
  const context = {
    todayWords: getTodayWords(),
    isNight: isNightTime(),
    isMorning: isMorningTime(),
    session: {
      words,
      duration: durationMinutes,
      perfect: options.perfect || false
    }
  };
  
  // 更新统计数据
  updateUserStats(userStats, words, durationMinutes, context);
  
  // 检查新解锁的成就
  const newAchievements = checkNewAchievements(userStats, context);
  
  // 显示成就解锁弹窗
  if (newAchievements.length > 0) {
    showAchievementUnlocked(newAchievements);
  }
  
  return newAchievements;
}
```

## 6. UI集成方案

### 6.1 首页展示
- 最近获得徽章：显示最近3枚解锁的勋章
- 下一目标提示：显示各维度的下一个目标，如"再转录234字解锁'千字达人'"

### 6.2 成就页面
- 分类展示：按四大维度 + 特色勋章分区显示
- 进度显示：已获得勋章显示解锁日期，未获得显示当前进度
- 筛选功能：按稀有度、分类、获得状态筛选

### 6.3 解锁弹窗
- 动效层次：根据稀有度控制动效强度
- 分享功能：一键生成分享卡片
- 防打扰：同一会话只显示最高稀有度的一枚勋章

## 7. 数据存储

### 7.1 用户统计数据
```javascript
const userStats = {
  totalUsage: 0,           // 总使用次数
  totalDuration: 0,        // 总使用时长(分钟)
  totalWords: 0,           // 总转录字数
  currentStreak: 0,        // 当前连续天数
  bestStreak: 0,           // 最佳连续天数
  nightUsage: 0,           // 夜间使用次数
  morningUsage: 0,         // 清晨使用次数
  consecutivePerfect: 0,   // 连续完美次数
  lastActiveDate: null,    // 最后活跃日期
  todayWords: 0,           // 今日字数
  todayUsage: 0           // 今日使用次数
};
```

### 7.2 已解锁成就
```javascript
const unlockedAchievements = [
  {
    id: 'words-1000',
    unlockedAt: '2024-01-15T10:30:00Z',
    rarity: 'common'
  }
  // ...
];
```

## 8. 开发路线

### Phase 1: 基础框架 (1周)
- 实现四大维度的基础勋章系统
- 完成成就评估和数据统计逻辑
- 首页下一目标提示功能

### Phase 2: 视觉优化 (1周)  
- 实现稀有度色彩和动效系统
- 完成成就页面的分类展示
- 解锁弹窗和分享功能

### Phase 3: 特色功能 (1周)
- 特殊时间段勋章系统
- 节日勋章和限时活动
- 行为特色勋章完善

### Phase 4: 优化完善 (1周)
- 性能优化和数据持久化
- A/B测试调整阶梯间隔
- 用户反馈收集和迭代

## 9. 预期效果

通过这套勋章系统，预期能够：
- 提升用户粘性：通过连续天数和阶梯目标鼓励持续使用
- 增强成就感：多维度成就覆盖不同类型用户的使用习惯
- 促进分享传播：精美的勋章设计和分享功能增加产品曝光
- 数据驱动优化：通过成就数据分析用户行为，指导产品迭代
