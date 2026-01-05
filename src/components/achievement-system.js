// Achievement Badge System
// 成就徽章系统 - 参考微信读书设计

// 参考微信读书完整徽章体系设计的 MonoBuck 成就系统
const ACHIEVEMENT_CATEGORIES = {
  BASIC: { name: '转录成就', color: 'green', description: '基础转录里程碑' },
  CHALLENGE: { name: '转录挑战', color: 'orange', description: '特定目标挑战' },
  HABIT: { name: '转录习惯', color: 'blue', description: '良好习惯养成' },
  SPEED: { name: '速度成就', color: 'cyan', description: '转录速度突破' },
  TIME: { name: '时长成就', color: 'purple', description: '累计时长里程碑' },
  SPECIAL: { name: '特殊成就', color: 'red', description: '独特行为奖励' },
  SOCIAL: { name: '社交成就', color: 'pink', description: '分享互动奖励' },
  SEASONAL: { name: '节日成就', color: 'gold', description: '限时节日活动' }
};

const ACHIEVEMENTS = {
  // === 转录成就 (基础里程碑) ===
  WORDS_50: {
    id: 'words-50', name: '初学者', description: '累计转录50字，踏出第一步',
    icon: '50', category: 'BASIC', rarity: 'common'
  },
  WORDS_200: {
    id: 'words-200', name: '入门者', description: '累计转录200字，渐入佳境',
    icon: '200', category: 'BASIC', rarity: 'common'
  },
  WORDS_500: {
    id: 'words-500', name: '练习生', description: '累计转录500字，持续进步',
    icon: '500', category: 'BASIC', rarity: 'common'
  },
  WORDS_1000: {
    id: 'words-1000', name: '千字达人', description: '累计转录1000字，小有成就',
    icon: '1K', category: 'BASIC', rarity: 'uncommon'
  },
  WORDS_3000: {
    id: 'words-3000', name: '文字高手', description: '累计转录3000字，技艺精进',
    icon: '3K', category: 'BASIC', rarity: 'uncommon'
  },
  WORDS_10000: {
    id: 'words-10000', name: '万字专家', description: '累计转录10000字，专业水准',
    icon: '10K', category: 'BASIC', rarity: 'rare'
  },
  WORDS_50000: {
    id: 'words-50000', name: '转录大师', description: '累计转录50000字，登峰造极',
    icon: '50K', category: 'BASIC', rarity: 'legendary'
  },

  // === 转录挑战 (目标导向) ===
  DAILY_100: {
    id: 'daily-100', name: '日行百字', description: '单日转录100字',
    icon: '100', category: 'CHALLENGE', rarity: 'common'
  },
  DAILY_500: {
    id: 'daily-500', name: '日行五百', description: '单日转录500字',
    icon: '500', category: 'CHALLENGE', rarity: 'uncommon'
  },
  DAILY_1000: {
    id: 'daily-1000', name: '日行千字', description: '单日转录1000字',
    icon: '1K', category: 'CHALLENGE', rarity: 'rare'
  },
  WEEKLY_GOAL: {
    id: 'weekly-goal', name: '周目标达成', description: '完成一周转录目标',
    icon: '7', category: 'CHALLENGE', rarity: 'uncommon'
  },
  MONTHLY_HERO: {
    id: 'monthly-hero', name: '月度英雄', description: '完成月度转录挑战',
    icon: '30', category: 'CHALLENGE', rarity: 'rare'
  },

  // === 转录习惯 (连续性) ===
  STREAK_3: {
    id: 'streak-3', name: '三日新手', description: '连续转录3天',
    icon: '3', category: 'HABIT', rarity: 'common'
  },
  STREAK_7: {
    id: 'streak-7', name: '一周坚持', description: '连续转录7天',
    icon: '7', category: 'HABIT', rarity: 'common'
  },
  STREAK_15: {
    id: 'streak-15', name: '半月恒心', description: '连续转录15天',
    icon: '15', category: 'HABIT', rarity: 'uncommon'
  },
  STREAK_30: {
    id: 'streak-30', name: '月度冠军', description: '连续转录30天',
    icon: '30', category: 'HABIT', rarity: 'rare'
  },
  STREAK_100: {
    id: 'streak-100', name: '百日坚持', description: '连续转录100天',
    icon: '100', category: 'HABIT', rarity: 'epic'
  },
  STREAK_365: {
    id: 'streak-365', name: '年度传奇', description: '连续转录365天',
    icon: '365', category: 'HABIT', rarity: 'legendary'
  },

  // === 速度成就 (WPM突破) ===
  SPEED_30: {
    id: 'speed-30', name: '稳步前进', description: '转录速度达到30WPM',
    icon: '30', category: 'SPEED', rarity: 'common'
  },
  SPEED_50: {
    id: 'speed-50', name: '速度新手', description: '转录速度达到50WPM',
    icon: '50', category: 'SPEED', rarity: 'common'
  },
  SPEED_80: {
    id: 'speed-80', name: '快手达人', description: '转录速度达到80WPM',
    icon: '80', category: 'SPEED', rarity: 'uncommon'
  },
  SPEED_100: {
    id: 'speed-100', name: '速度之王', description: '转录速度达到100WPM',
    icon: '100', category: 'SPEED', rarity: 'rare'
  },
  SPEED_150: {
    id: 'speed-150', name: '闪电侠', description: '转录速度达到150WPM',
    icon: '150', category: 'SPEED', rarity: 'epic'
  },

  // === 时长成就 (累计时间) ===
  TIME_1H: {
    id: 'time-1h', name: '初试锋芒', description: '累计转录1小时',
    icon: '1h', category: 'TIME', rarity: 'common'
  },
  TIME_10H: {
    id: 'time-10h', name: '十时达人', description: '累计转录10小时',
    icon: '10h', category: 'TIME', rarity: 'uncommon'
  },
  TIME_50H: {
    id: 'time-50h', name: '时间大师', description: '累计转录50小时',
    icon: '50h', category: 'TIME', rarity: 'rare'
  },
  TIME_100H: {
    id: 'time-100h', name: '百时传奇', description: '累计转录100小时',
    icon: '100h', category: 'TIME', rarity: 'epic'
  },

  // === 特殊成就 (行为奖励) ===
  NIGHT_OWL: {
    id: 'night-owl', name: '夜猫子', description: '深夜时段(22:00-6:00)完成转录',
    icon: '🌙', category: 'SPECIAL', rarity: 'uncommon'
  },
  EARLY_BIRD: {
    id: 'early-bird', name: '早起鸟', description: '清晨时段(5:00-8:00)完成转录',
    icon: '🌅', category: 'SPECIAL', rarity: 'uncommon'
  },
  PERFECTIONIST: {
    id: 'perfectionist', name: '完美主义', description: '连续10次无错误转录',
    icon: '💯', category: 'SPECIAL', rarity: 'rare'
  },
  MULTITASKER: {
    id: 'multitasker', name: '多面手', description: '使用5种不同的转录源',
    icon: '🎯', category: 'SPECIAL', rarity: 'uncommon'
  },
  EFFICIENCY_MASTER: {
    id: 'efficiency-master', name: '效率大师', description: '单次转录超过500字且用时少于5分钟',
    icon: '⚡', category: 'SPECIAL', rarity: 'rare'
  },

  // === 社交成就 (分享互动) ===
  FIRST_SHARE: {
    id: 'first-share', name: '分享达人', description: '首次分享转录成果',
    icon: '📤', category: 'SOCIAL', rarity: 'common'
  },
  FEEDBACK_GIVER: {
    id: 'feedback-giver', name: '反馈专家', description: '提供产品改进建议',
    icon: '💡', category: 'SOCIAL', rarity: 'uncommon'
  },

  // === 节日成就 (限时活动) ===
  NEW_YEAR_2024: {
    id: 'new-year-2024', name: '新年新气象', description: '2024年新年期间完成转录',
    icon: '🎊', category: 'SEASONAL', rarity: 'limited'
  },
  SPRING_FESTIVAL: {
    id: 'spring-festival', name: '春节快乐', description: '春节期间坚持转录',
    icon: '🧧', category: 'SEASONAL', rarity: 'limited'
  }
};

// 获取用户已解锁的成就
function getUnlockedAchievements() {
  try {
    return JSON.parse(localStorage.getItem('unlockedAchievements') || '[]');
  } catch {
    return [];
  }
}

// 保存已解锁的成就
function saveUnlockedAchievements(achievements) {
  try {
    localStorage.setItem('unlockedAchievements', JSON.stringify(achievements));
  } catch (e) {
    console.warn('Failed to save achievements:', e);
  }
}

// ---- 通用 Criteria 结构与工具 ----
// Criteria: { type, op, value, scope }
// type: 'totalWords'|'dailyWords'|'currentStreak'|'maxWPM'|'totalTimeMin'|'sessionWords'|'perfectSessions'|'sourcesUsed'|'nightSession'|'morningSession'
// op: '>=','=='
// scope: 'total'|'day'|'session'

function normalizeAchievement(achievement) {
  // 为缺少 condition 的定义推断出 criteria（不修改原对象）
  const crit = [];
  if (achievement.condition) {
    const { type, value } = achievement.condition;
    crit.push({ type, op: '>=', value, scope: inferScope(type) });
  } else {
    // 根据 id 规则推断
    const id = String(achievement.id);
    if (id.startsWith('words-')) {
      const val = parseInt(id.split('-')[1], 10);
      crit.push({ type: 'totalWords', op: '>=', value: val, scope: 'total' });
    } else if (id.startsWith('streak-')) {
      const val = parseInt(id.split('-')[1], 10);
      crit.push({ type: 'currentStreak', op: '>=', value: val, scope: 'total' });
    } else if (id.startsWith('speed-')) {
      const val = parseInt(id.split('-')[1], 10);
      crit.push({ type: 'maxWPM', op: '>=', value: val, scope: 'total' });
    } else if (id.startsWith('time-')) {
      const val = parseInt(id.split('-')[1], 10);
      crit.push({ type: 'totalTimeMin', op: '>=', value: val * 60, scope: 'total' });
    } else if (id.startsWith('daily-')) {
      const val = parseInt(id.split('-')[1], 10);
      crit.push({ type: 'dailyWords', op: '>=', value: val, scope: 'day' });
    } else if (id === 'night-owl') {
      crit.push({ type: 'nightSession', op: '==', value: 1, scope: 'session' });
    } else if (id === 'early-bird') {
      crit.push({ type: 'morningSession', op: '==', value: 1, scope: 'session' });
    } else if (id === 'perfectionist') {
      crit.push({ type: 'perfectSessions', op: '>=', value: 10, scope: 'total' });
    } else if (id === 'multitasker') {
      crit.push({ type: 'sourcesUsed', op: '>=', value: 5, scope: 'total' });
    }
  }
  return { ...achievement, criteria: crit };
}

function inferScope(type) {
  if (type === 'dailyWords') return 'day';
  if (type === 'sessionWords' || type === 'nightSession' || type === 'morningSession') return 'session';
  return 'total';
}

function compare(op, left, right) {
  switch (op) {
    case '>=': return left >= right;
    case '==': return left === right;
    default: return false;
  }
}

function evaluateCriteria(criteria, userStats, context) {
  // context 可包含 { todayWords, session: { words, isNight, isMorning }, sourcesUsed }
  return criteria.every(c => {
    let val = 0;
    switch (c.type) {
      case 'totalWords': val = userStats.totalWords || 0; break;
      case 'dailyWords': val = (context.todayWords || 0); break;
      case 'currentStreak': val = userStats.currentStreak || 0; break;
      case 'maxWPM': val = userStats.maxWPM || 0; break;
      case 'totalTimeMin': val = userStats.totalTimeMin || 0; break;
      case 'sessionWords': val = (context.session?.words || 0); break;
      case 'perfectSessions': val = userStats.perfectSessions || 0; break;
      case 'sourcesUsed': val = (userStats.sourcesUsed || 0); break;
      case 'nightSession': val = (context.session?.isNight ? 1 : 0); break;
      case 'morningSession': val = (context.session?.isMorning ? 1 : 0); break;
      default: val = 0;
    }
    return compare(c.op, val, c.value);
  });
}

// 计算下一目标（用于提示“离下一枚徽章还差 X”）
export function getNextTargets(userStats) {
  const ladders = {
    WORDS: [50, 200, 500, 1000, 3000, 10000, 50000],
    STREAK: [3, 7, 15, 30, 100, 365],
    SPEED: [30, 50, 80, 100, 150],
    TIME_MIN: [60, 600, 3000, 6000]
  };
  function nextOf(arr, current) { return arr.find(v => v > current) || null; }
  return {
    wordsNext: nextOf(ladders.WORDS, userStats.totalWords || 0),
    streakNext: nextOf(ladders.STREAK, userStats.currentStreak || 0),
    speedNext: nextOf(ladders.SPEED, userStats.maxWPM || 0),
    timeNextMin: nextOf(ladders.TIME_MIN, userStats.totalTimeMin || 0)
  };
}

// 检查是否解锁新成就（支持多条件）
export function checkAchievements(userStats, context = {}) {
  const unlocked = getUnlockedAchievements();
  const newAchievements = [];

  for (const achievement of Object.values(ACHIEVEMENTS)) {
    if (unlocked.some(a => a.id === achievement.id)) continue;
    const a = normalizeAchievement(achievement);
    const meets = evaluateCriteria(a.criteria, userStats, context);
    if (meets) {
      const unlockedAchievement = {
        ...achievement,
        unlockedAt: new Date().toISOString(),
        stats: { ...userStats }
      };
      newAchievements.push(unlockedAchievement);
      unlocked.push(unlockedAchievement);
    }
  }

  if (newAchievements.length > 0) {
    saveUnlockedAchievements(unlocked);
    showAchievementModal(newAchievements[0]);
  }
  return newAchievements;
}

// 显示成就解锁弹窗
function showAchievementModal(achievement) {
  // 创建弹窗HTML
  const modalHTML = `
    <div class="achievement-modal-overlay active" id="achievement-overlay">
      <div class="achievement-modal">
        <div class="achievement-content">
          <div class="achievement-icon">🎉</div>
          <h2 class="achievement-title">恭喜解锁新成就！</h2>
          
          <div class="streak-badge achievement" id="achievement-badge">
            <div class="streak-core">
              <span class="streak-count">${achievement.icon}</span>
            </div>
            <div class="streak-label">${achievement.name}</div>
          </div>
          
          <p class="achievement-desc">${achievement.description}</p>
          
          <div class="achievement-stats">
            <div class="stat-item">
              <span class="stat-label">获得时间</span>
              <span class="stat-value">${formatDate(achievement.unlockedAt)}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">成就等级</span>
              <span class="stat-value">${getTierName(achievement.tier)}</span>
            </div>
          </div>
          
          <div class="achievement-actions">
            <button class="btn primary" onclick="shareAchievement('${achievement.id}')">分享成就</button>
            <button class="btn ghost" onclick="closeAchievementModal()">继续使用</button>
          </div>
        </div>
      </div>
    </div>
  `;

  // 添加到页面
  document.body.insertAdjacentHTML('beforeend', modalHTML);

  // 3秒后自动关闭（可选）
  setTimeout(() => {
    const overlay = document.getElementById('achievement-overlay');
    if (overlay) {
      overlay.classList.remove('active');
      setTimeout(() => overlay.remove(), 300);
    }
  }, 5000);
}

// 关闭成就弹窗
window.closeAchievementModal = function() {
  const overlay = document.getElementById('achievement-overlay');
  if (overlay) {
    overlay.classList.remove('active');
    setTimeout(() => overlay.remove(), 300);
  }
};

// 分享成就
window.shareAchievement = function(achievementId) {
  const achievement = Object.values(ACHIEVEMENTS).find(a => a.id === achievementId);
  if (achievement) {
    // 这里可以集成分享功能
    const shareText = `我在 MonoBuck 中解锁了「${achievement.name}」成就！${achievement.description}`;
    
    if (navigator.share) {
      navigator.share({
        title: 'MonoBuck 成就分享',
        text: shareText,
        url: window.location.href
      });
    } else {
      // 复制到剪贴板
      navigator.clipboard.writeText(shareText).then(() => {
        alert('成就信息已复制到剪贴板！');
      });
    }
  }
  closeAchievementModal();
};

// 获取成就进度
export function getAchievementProgress(userStats) {
  const unlocked = getUnlockedAchievements();
  const progress = [];

  for (const [key, achievement] of Object.entries(ACHIEVEMENTS)) {
    const isUnlocked = unlocked.some(a => a.id === achievement.id);
    let currentProgress = 0;
    let maxProgress = achievement.condition.value;

    const { type, value } = achievement.condition;
    switch (type) {
      case 'totalWords':
        currentProgress = userStats.totalWords || 0;
        break;
      case 'streak':
        currentProgress = userStats.currentStreak || 0;
        break;
      case 'maxWPM':
        currentProgress = userStats.maxWPM || 0;
        break;
    }

    progress.push({
      ...achievement,
      isUnlocked,
      currentProgress: Math.min(currentProgress, maxProgress),
      maxProgress,
      percentage: Math.min((currentProgress / maxProgress) * 100, 100),
      unlockedAt: isUnlocked ? unlocked.find(a => a.id === achievement.id)?.unlockedAt : null
    });
  }

  return progress;
}

// 渲染徽章收藏页面
export function renderBadgesCollection(container, userStats) {
  const progress = getAchievementProgress(userStats);
  
  const html = `
    <div class="badges-collection">
      <h3 class="collection-title">我的成就徽章</h3>
      <div class="badges-grid">
        ${progress.map(achievement => `
          <div class="badge-item ${achievement.isUnlocked ? 'earned' : 'locked'}" 
               data-badge="${achievement.id}"
               title="${achievement.description}">
            <div class="streak-badge achievement mini ${achievement.isUnlocked ? '' : 'locked'}">
              <div class="streak-core">
                <span class="streak-count">${achievement.icon}</span>
              </div>
              <div class="streak-label">${achievement.name}</div>
            </div>
            ${achievement.isUnlocked 
              ? `<div class="badge-date">${formatDate(achievement.unlockedAt)}</div>`
              : `<div class="badge-progress">进度: ${achievement.currentProgress}/${achievement.maxProgress}</div>`
            }
          </div>
        `).join('')}
      </div>
    </div>
  `;

  container.innerHTML = html;
}

// 工具函数
function formatDate(dateString) {
  const date = new Date(dateString);
  return date.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  });
}

function getTierName(tier) {
  const tierNames = {
    bronze: '青铜',
    silver: '白银',
    gold: '黄金',
    platinum: '铂金'
  };
  return tierNames[tier] || '普通';
}

// 示例：在转录完成后调用（事件驱动评估）
export function onTranscriptionComplete(words, durationMin, wpm, options = {}) {
  const userStats = getUserStats();
  // 累计维度
  userStats.totalWords = (userStats.totalWords || 0) + words;
  userStats.totalTimeMin = (userStats.totalTimeMin || 0) + (durationMin || 0);
  userStats.maxWPM = Math.max(userStats.maxWPM || 0, wpm || 0);
  userStats.sessionsCount = (userStats.sessionsCount || 0) + 1;
  // 质量维度
  if (options.perfect) userStats.perfectSessions = (userStats.perfectSessions || 0) + 1;
  if (options.source) {
    const used = new Set((userStats.sourcesUsedList || []));
    used.add(options.source);
    userStats.sourcesUsedList = Array.from(used);
    userStats.sourcesUsed = userStats.sourcesUsedList.length;
  }
  // 习惯维度（简化：若当天已有记录则保持 streak，否则 +1）
  const todayKey = new Date().toDateString();
  const lastActiveDay = userStats.lastActiveDay;
  if (!lastActiveDay || lastActiveDay !== todayKey) {
    // 简化：若昨天有记录则 +1，否则重置为 1
    const yesterday = new Date(Date.now() - 24*60*60*1000).toDateString();
    userStats.currentStreak = (lastActiveDay === yesterday) ? ((userStats.currentStreak || 0) + 1) : 1;
    userStats.lastActiveDay = todayKey;
    userStats.todayWords = words;
  } else {
    userStats.todayWords = (userStats.todayWords || 0) + words;
  }
  saveUserStats(userStats);

  // 会话上下文（用于 night/morning 判断等）
  const hour = new Date().getHours();
  const context = {
    todayWords: userStats.todayWords || 0,
    session: {
      words,
      isNight: hour >= 22 || hour < 6,
      isMorning: hour >= 5 && hour < 8
    }
  };
  checkAchievements(userStats, context);
}

function getUserStats() {
  try {
    return JSON.parse(localStorage.getItem('userStats') || '{}');
  } catch {
    return {};
  }
}

function saveUserStats(stats) {
  try {
    localStorage.setItem('userStats', JSON.stringify(stats));
  } catch (e) {
    console.warn('Failed to save user stats:', e);
  }
}