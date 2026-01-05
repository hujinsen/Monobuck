// 创意勋章定义 - 更有趣味和品味的命名
export const CREATIVE_DEFINITIONS = [
  // 使用次数系列 - "修行之路"
  { id: 'usage-1', name: '🌱 初入江湖', rarity: 'common' },
  { id: 'usage-10', name: '⚔️ 小试牛刀', rarity: 'common' },
  { id: 'usage-50', name: '🗡️ 渐入佳境', rarity: 'uncommon' },
  { id: 'usage-100', name: '🏹 百步穿杨', rarity: 'uncommon' },
  { id: 'usage-500', name: '🛡️ 身经百战', rarity: 'rare' },
  { id: 'usage-1000', name: '👑 千锤百炼', rarity: 'rare' },
  { id: 'usage-5000', name: '🔮 登峰造极', rarity: 'epic' },
  { id: 'usage-10000', name: '⭐ 万古流芳', rarity: 'epic' },
  { id: 'usage-50000', name: '🌟 举世无双', rarity: 'legendary' },
  { id: 'usage-100000', name: '💫 神话再现', rarity: 'legendary' },

  // 时长系列 - "时光印记" (分钟)
  { id: 'duration-1', name: '🕐 分秒必争', rarity: 'common' },
  { id: 'duration-10', name: '🕕 十分专注', rarity: 'common' },
  { id: 'duration-30', name: '🕘 三十而立', rarity: 'uncommon' },
  { id: 'duration-60', name: '🕐 一气呵成', rarity: 'uncommon' },
  { id: 'duration-300', name: '🌅 晨昏定省', rarity: 'rare' },
  { id: 'duration-1200', name: '🌙 夜以继日', rarity: 'rare' },
  { id: 'duration-6000', name: '⚡ 百炼成钢', rarity: 'epic' },
  { id: 'duration-30000', name: '🔥 炉火纯青', rarity: 'epic' },
  { id: 'duration-60000', name: '🏔️ 登峰造极', rarity: 'legendary' },

  // 字数系列 - "文采飞扬"
  { id: 'words-100', name: '📜 初露锋芒', rarity: 'common' },
  { id: 'words-1000', name: '🖋️ 千字珠玑', rarity: 'common' },
  { id: 'words-5000', name: '📚 洋洋洒洒', rarity: 'uncommon' },
  { id: 'words-10000', name: '🎭 万言书生', rarity: 'uncommon' },
  { id: 'words-50000', name: '📖 著作等身', rarity: 'rare' },
  { id: 'words-100000', name: '🏛️ 文章巨匠', rarity: 'rare' },
  { id: 'words-500000', name: '🌊 汪洋恣肆', rarity: 'epic' },
  { id: 'words-1000000', name: '🌌 才高八斗', rarity: 'epic' },
  { id: 'words-5000000', name: '✨ 笔走龙蛇', rarity: 'legendary' },

  // 连续天数系列 - "坚持之美"
  { id: 'streak-1', name: '🌱 初心不改', rarity: 'common' },
  { id: 'streak-3', name: '🌿 三日成习', rarity: 'common' },
  { id: 'streak-7', name: '🌳 七日之约', rarity: 'uncommon' },
  { id: 'streak-15', name: '🌙 半月如一', rarity: 'uncommon' },
  { id: 'streak-30', name: '🌕 月圆月缺', rarity: 'rare' },
  { id: 'streak-60', name: '🌸 春华秋实', rarity: 'rare' },
  { id: 'streak-100', name: '☀️ 百日筑基', rarity: 'epic' },
  { id: 'streak-365', name: '🎋 四季如春', rarity: 'epic' },
  { id: 'streak-730', name: '🏔️ 山高水长', rarity: 'legendary' },
  { id: 'streak-1825', name: '🌌 五载春秋', rarity: 'legendary' },

  // 特殊时间系列 - "昼夜精灵"
  { id: 'night-owl-10', name: '🦉 夜半钟声', criteria: [{ type: 'nightUsage', op: '>=', value: 10 }], rarity: 'uncommon' },
  { id: 'night-owl-50', name: '🌙 月下独酌', criteria: [{ type: 'nightUsage', op: '>=', value: 50 }], rarity: 'rare' },
  { id: 'early-bird-10', name: '🐦 闻鸡起舞', criteria: [{ type: 'morningUsage', op: '>=', value: 10 }], rarity: 'uncommon' },

  // 特殊行为系列 - "品格之光"
  { id: 'perfectionist-5', name: '💎 精益求精', criteria: [{ type: 'consecutivePerfect', op: '>=', value: 5 }], rarity: 'uncommon' },
  { id: 'persistent-7', name: '🔥 百折不挠', criteria: [{ type: 'currentStreak', op: '>=', value: 7 }], rarity: 'rare' },
  { id: 'daily-hero-1000', name: '⚡ 一日千里', criteria: [{ type: 'dailyWords', op: '>=', value: 1000 }], rarity: 'uncommon' },

  // 新增创意勋章
  { id: 'night-owl-100', name: '🌌 暗夜君王', criteria: [{ type: 'nightUsage', op: '>=', value: 100 }], rarity: 'epic' },
  { id: 'early-bird-50', name: '🌅 晨光使者', criteria: [{ type: 'morningUsage', op: '>=', value: 50 }], rarity: 'rare' },
  { id: 'perfectionist-20', name: '🏆 完美无瑕', criteria: [{ type: 'consecutivePerfect', op: '>=', value: 20 }], rarity: 'rare' },
  { id: 'speed-demon', name: '💨 疾风骤雨', criteria: [{ type: 'dailyWords', op: '>=', value: 5000 }], rarity: 'epic' },
  { id: 'marathon-runner', name: '🏃 马拉松勇士', criteria: [{ type: 'totalDuration', op: '>=', value: 1440 }], rarity: 'epic' }, // 24小时
];

// 主题分类
export const BADGE_THEMES = {
  cultivation: {
    name: '修行之路',
    description: '从初入江湖到神话再现的成长历程',
    badges: ['usage-1', 'usage-10', 'usage-50', 'usage-100', 'usage-500', 'usage-1000', 'usage-5000', 'usage-10000', 'usage-50000', 'usage-100000']
  },
  timekeeper: {
    name: '时光印记', 
    description: '珍惜时间，专注当下的时光记录',
    badges: ['duration-1', 'duration-10', 'duration-30', 'duration-60', 'duration-300', 'duration-1200', 'duration-6000', 'duration-30000', 'duration-60000']
  },
  wordsmith: {
    name: '文采飞扬',
    description: '从初露锋芒到笔走龙蛇的文字之旅', 
    badges: ['words-100', 'words-1000', 'words-5000', 'words-10000', 'words-50000', 'words-100000', 'words-500000', 'words-1000000', 'words-5000000']
  },
  persistence: {
    name: '坚持之美',
    description: '持之以恒，岁月如歌的坚持见证',
    badges: ['streak-1', 'streak-3', 'streak-7', 'streak-15', 'streak-30', 'streak-60', 'streak-100', 'streak-365', 'streak-730', 'streak-1825']
  },
  nightowl: {
    name: '昼夜精灵',
    description: '夜半钟声与闻鸡起舞的时间精灵',
    badges: ['night-owl-10', 'night-owl-50', 'night-owl-100', 'early-bird-10', 'early-bird-50']
  },
  excellence: {
    name: '品格之光',
    description: '精益求精，百折不挠的品格体现',
    badges: ['perfectionist-5', 'perfectionist-20', 'persistent-7', 'daily-hero-1000', 'speed-demon', 'marathon-runner']
  }
};

// 勋章描述和故事
export const BADGE_STORIES = {
  'usage-1': '踏出第一步，江湖路漫漫。每个传奇都始于初心。',
  'usage-10': '十次磨砺，小试身手。刀锋初露，锐气渐显。',
  'usage-100': '百步之外，一箭穿心。精准源于无数次的练习。',
  'usage-1000': '千锤百炼，方成利器。技艺炉火纯青，名震一方。',
  'words-1000': '千字珠玑，字字生辉。文思如泉涌，妙笔生花。',
  'words-100000': '十万文章，著作等身。学富五车，才高八斗。',
  'streak-7': '七日之约，言出必行。坚持是最美的品格。',
  'streak-365': '四季轮回，初心不改。一年如一日的坚持，令人敬佩。',
  'night-owl-10': '夜半钟声，独自求索。在寂静中寻找灵感的夜行者。',
  'early-bird-10': '闻鸡起舞，勤奋如初。晨光中的身影最是动人。'
};

export default CREATIVE_DEFINITIONS;