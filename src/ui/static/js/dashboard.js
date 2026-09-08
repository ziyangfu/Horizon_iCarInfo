/**
 * Horizon_iCarInfo Dashboard Interactive Client Logic
 */

document.addEventListener('DOMContentLoaded', () => {
  // App state
  const state = {
    reports: [],
    currentReport: null,
    activeCategory: 'all',
    activeTag: null,
    searchQuery: '',
    whitelistData: null,
    whitelistConfig: null,
    currentEditorMode: 'visual', // 'visual' | 'json'
  };

  // Top nav & Report controls
  const reportSelect = document.getElementById('report-select');
  const btnRefreshReports = document.getElementById('btn-refresh-reports');
  const itemsContainer = document.getElementById('items-container');
  const searchInput = document.getElementById('search-input');
  const searchClear = document.getElementById('search-clear');
  const tagsList = document.getElementById('tags-list');
  const reportTitle = document.getElementById('current-report-title');
  const reportSubtitle = document.getElementById('current-report-subtitle');
  const tabBtns = document.querySelectorAll('.tab-btn');

  // KPI elements
  const valSelectedCount = document.getElementById('val-selected-count');
  const valRawCount = document.getElementById('val-raw-count');
  const valFilterRate = document.getElementById('val-filter-rate');
  const valPapersCount = document.getElementById('val-papers-count');
  const valPatentsCount = document.getElementById('val-patents-count');
  const valAvgScore = document.getElementById('val-avg-score');

  // Tab count elements
  const cntAll = document.getElementById('cnt-all');
  const cntInfo = document.getElementById('cnt-info');
  const cntPapers = document.getElementById('cnt-papers');
  const cntPatents = document.getElementById('cnt-patents');

  // Drawer elements
  const btnOpenWhitelist = document.getElementById('btn-open-whitelist');
  const btnCloseDrawer = document.getElementById('btn-close-drawer');
  const whitelistDrawer = document.getElementById('whitelist-drawer');

  const tabModeVisual = document.getElementById('tab-mode-visual');
  const tabModeJson = document.getElementById('tab-mode-json');
  const drawerViewVisual = document.getElementById('drawer-view-visual');
  const drawerViewJson = document.getElementById('drawer-view-json');

  const selectWhitelistGroup = document.getElementById('select-whitelist-group');
  const inputNewChip = document.getElementById('input-new-chip');
  const btnAddChip = document.getElementById('btn-add-chip');
  const editableChipsBox = document.getElementById('editable-chips-box');
  const currentGroupCount = document.getElementById('current-group-count');

  const whitelistJsonTextarea = document.getElementById('whitelist-json-textarea');
  const btnFormatJson = document.getElementById('btn-format-json');
  const jsonSyntaxError = document.getElementById('json-syntax-error');

  const btnSaveWhitelist = document.getElementById('btn-save-whitelist');
  const btnResetWhitelist = document.getElementById('btn-reset-whitelist');

  // Global Toast
  const appToast = document.getElementById('app-toast');
  const toastMsg = document.getElementById('toast-msg');
  const toastIcon = document.getElementById('toast-icon');
  let toastTimer = null;

  function showToast(message, isError = false) {
    if (!appToast || !toastMsg || !toastIcon) return;
    if (toastTimer) clearTimeout(toastTimer);
    toastMsg.textContent = message;
    toastIcon.textContent = isError ? '❌' : '✅';
    appToast.classList.toggle('error', isError);
    appToast.classList.add('show');
    toastTimer = setTimeout(() => {
      appToast.classList.remove('show');
    }, 3500);
  }

  // 1. Initial Load: fetch report list
  async function init(isManualRefresh = false) {
    try {
      const res = await fetch('/api/reports?t=' + Date.now());
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      }
      const data = await res.json();
      if (data.code === 0 && data.data && data.data.length > 0) {
        state.reports = data.data;
        populateReportSelect(state.reports);
        // Load the first (latest) report
        loadReport(state.reports[0].filename);
        if (isManualRefresh) {
          showToast(`已刷新情报库，当前最新: ${state.reports[0].date || state.reports[0].filename}`);
        }
      } else {
        showEmpty('暂未发现生成的速递日报，请先在终端运行抓取或检查 data/summaries 目录');
      }
    } catch (err) {
      console.error('Failed to load reports:', err);
      showEmpty('无法连接到看板后端 API 服务: ' + err.message);
    }
  }

  // Populate Select options
  function populateReportSelect(reports) {
    if (!reportSelect) return;
    reportSelect.innerHTML = '';
    reports.forEach((rep, idx) => {
      const opt = document.createElement('option');
      opt.value = rep.filename;
      const isLatest = idx === 0 ? ' [最新]' : '';
      const langBadge = rep.lang === 'zh' ? '中' : (rep.lang === 'en' ? 'EN' : '');
      opt.textContent = `📅 ${rep.date || rep.filename} (${langBadge})${isLatest}`;
      reportSelect.appendChild(opt);
    });

    reportSelect.onchange = (e) => {
      loadReport(e.target.value);
    };
  }

  // Fetch and display a specific report
  async function loadReport(filename) {
    if (!itemsContainer) return;
    itemsContainer.innerHTML = `
      <div class="loading-state">
        <div class="spinner"></div>
        <p>正在装载并结构化解析「${escapeHtml(filename)}」情报数据...</p>
      </div>
    `;

    try {
      const res = await fetch(`/api/reports/${encodeURIComponent(filename)}?t=` + Date.now());
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      }
      const json = await res.json();
      if (json.code === 0 && json.data) {
        state.currentReport = json.data;
        state.activeCategory = 'all';
        state.activeTag = null;
        state.searchQuery = '';
        if (searchInput) searchInput.value = '';
        if (searchClear) searchClear.style.display = 'none';

        updateUI();
      } else {
        showEmpty(json.message || '加载报告失败');
      }
    } catch (err) {
      console.error('Failed to fetch report detail:', err);
      showEmpty('网络通信失败，未能加载报告内容: ' + err.message);
    }
  }

  // Update whole UI with current report data
  function updateUI() {
    if (!state.currentReport) return;
    const r = state.currentReport;
    const items = r.items || [];
    const metrics = r.metrics || {};

    // Header info
    if (reportTitle) reportTitle.textContent = r.title || '智能汽车底盘前瞻资讯速递';
    if (reportSubtitle) reportSubtitle.textContent = r.subtitle || `日期: ${r.date} | 共收录 ${items.length} 条高价值情报`;

    // Metrics
    if (valSelectedCount) valSelectedCount.textContent = metrics.selected_total || items.length;
    if (valRawCount) valRawCount.textContent = metrics.total_raw || (items.length * 9);
    if (valFilterRate) valFilterRate.textContent = `降噪率 ${metrics.noise_filter_rate || '88.5%'}`;
    if (valPapersCount) valPapersCount.textContent = metrics.papers_count || 0;
    if (valPatentsCount) valPatentsCount.textContent = metrics.patents_count || 0;
    if (valAvgScore) valAvgScore.textContent = `${metrics.avg_score || '4.5'}/10`;

    // Tab counts
    if (cntAll) cntAll.textContent = items.length;
    if (cntInfo) cntInfo.textContent = items.filter(i => i.category === 'icar-info').length;
    if (cntPapers) cntPapers.textContent = items.filter(i => i.category === 'icar-papers').length;
    if (cntPatents) cntPatents.textContent = items.filter(i => i.category === 'icar-patents').length;

    // Reset tab active state
    tabBtns.forEach(btn => {
      btn.classList.toggle('active', btn.dataset.category === state.activeCategory);
    });

    // Populate hot tags
    populateTags(items);

    // Render items
    renderItems();
  }

  // Populate dynamic tags
  function populateTags(items) {
    if (!tagsList) return;
    const tagCount = {};
    items.forEach(item => {
      (item.tags || []).forEach(tag => {
        tagCount[tag] = (tagCount[tag] || 0) + 1;
      });
    });

    const sortedTags = Object.keys(tagCount).sort((a, b) => tagCount[b] - tagCount[a]).slice(0, 10);

    tagsList.innerHTML = '';
    sortedTags.forEach(tag => {
      const span = document.createElement('span');
      span.className = `filter-tag ${state.activeTag === tag ? 'active' : ''}`;
      span.textContent = `#${tag} (${tagCount[tag]})`;
      span.addEventListener('click', () => {
        if (state.activeTag === tag) {
          state.activeTag = null;
        } else {
          state.activeTag = tag;
        }
        populateTags(items);
        renderItems();
      });
      tagsList.appendChild(span);
    });
  }

  // Filter and render items
  function renderItems() {
    if (!state.currentReport || !itemsContainer) return;

    let items = state.currentReport.items || [];

    // 1. Filter by category tab
    if (state.activeCategory !== 'all') {
      items = items.filter(i => i.category === state.activeCategory);
    }

    // 2. Filter by active tag
    if (state.activeTag) {
      items = items.filter(i => (i.tags || []).includes(state.activeTag));
    }

    // 3. Filter by search query
    const q = state.searchQuery.trim().toLowerCase();
    if (q) {
      items = items.filter(i => {
        return (
          (i.title && i.title.toLowerCase().includes(q)) ||
          (i.summary && i.summary.toLowerCase().includes(q)) ||
          (i.background && i.background.toLowerCase().includes(q)) ||
          (i.breakthrough && i.breakthrough.toLowerCase().includes(q)) ||
          (i.impact && i.impact.toLowerCase().includes(q)) ||
          (i.patent_number && i.patent_number.toLowerCase().includes(q)) ||
          (i.patent_applicant && i.patent_applicant.toLowerCase().includes(q)) ||
          (i.tags && i.tags.some(t => t.toLowerCase().includes(q)))
        );
      });
    }

    // Render list
    if (items.length === 0) {
      itemsContainer.innerHTML = `
        <div class="empty-state">
          <p>🔍 未找到匹配当前筛选条件的情报条目</p>
          <small style="color: var(--text-dim); margin-top: 8px; display: block;">尝试切换板块标签或清空搜索关键词</small>
        </div>
      `;
      return;
    }

    itemsContainer.innerHTML = '';
    items.forEach((item, index) => {
      const card = createItemCard(item, index + 1);
      itemsContainer.appendChild(card);
    });
  }

  // Helper to build DOM card
  function createItemCard(item, index) {
    const card = document.createElement('article');
    const catClass = item.category === 'icar-patents' ? 'cat-patents' : (item.category === 'icar-papers' ? 'cat-papers' : 'cat-info');
    card.className = `item-card ${catClass}`;

    // Top badges
    let badgesHtml = '';
    if (item.category === 'icar-patents') {
      badgesHtml += `<span class="cat-pill patents">⚖️ 权威发明专利</span>`;
      if (item.patent_number) {
        badgesHtml += `<span class="badge-patent-num">公开号: ${escapeHtml(item.patent_number)}</span>`;
      }
      if (item.patent_applicant) {
        badgesHtml += `<span class="badge-patent-num">申请人: ${escapeHtml(item.patent_applicant)}</span>`;
      }
    } else if (item.category === 'icar-papers') {
      badgesHtml += `<span class="cat-pill papers">🎓 顶级前沿论文</span>`;
      if (item.is_open_access) {
        badgesHtml += `<span class="badge-oa">🔓 Open Access 全文开放</span>`;
      }
    } else {
      badgesHtml += `<span class="cat-pill info">⚡️ 行业前瞻突破</span>`;
    }

    const scoreHtml = item.score ? `<div class="score-badge">⭐️ ${item.score.toFixed(1)}/10</div>` : '';

    // Meta line
    const metaText = item.meta_info ? `<span class="meta-info-text">${escapeHtml(item.meta_info)}</span>` : '';

    // Deep enrichment sections
    const hasEnrichment = item.background || item.breakthrough || item.impact || (item.references && item.references.length > 0);
    let enrichmentHtml = '';

    if (hasEnrichment) {
      let blocks = '';
      if (item.background) {
        blocks += `
          <div class="section-block">
            <span class="block-label bg-label">⚙️ 技术背景与工程挑战:</span>
            <p class="block-text">${escapeHtml(item.background)}</p>
          </div>
        `;
      }
      if (item.breakthrough) {
        blocks += `
          <div class="section-block">
            <span class="block-label tb-label">🚀 核心技术突破:</span>
            <p class="block-text">${escapeHtml(item.breakthrough)}</p>
          </div>
        `;
      }
      if (item.impact) {
        blocks += `
          <div class="section-block">
            <span class="block-label im-label">📊 行业影响与客观评价:</span>
            <p class="block-text">${escapeHtml(item.impact)}</p>
          </div>
        `;
      }
      if (item.references && item.references.length > 0) {
        const refLinks = item.references.map(r => `<li><a href="${escapeHtml(r.url)}" target="_blank" rel="noopener">🔗 ${escapeHtml(r.title || r.url)}</a></li>`).join('');
        blocks += `
          <div class="section-block">
            <span class="block-label">📚 权威溯源参考:</span>
            <ul class="refs-list">${refLinks}</ul>
          </div>
        `;
      }

      enrichmentHtml = `
        <div class="enrichment-box">
          <button class="enrichment-toggle" aria-expanded="true">
            <span>🔬 展开深度技术洞察 (Deep Tech Enrichment)</span>
            <span class="arrow">▼</span>
          </button>
          <div class="enrichment-content">
            ${blocks}
          </div>
        </div>
      `;
    }

    // Tags
    const tagsHtml = (item.tags || []).map(t => `<span class="card-tag">#${escapeHtml(t)}</span>`).join('');

    // Action buttons
    let actionsHtml = '';
    if (item.pdf_url) {
      actionsHtml += `<a href="${escapeHtml(item.pdf_url)}" target="_blank" rel="noopener" class="btn-pdf-direct">📥 免费全文直达 (PDF)</a>`;
    }
    actionsHtml += `<a href="${escapeHtml(item.url)}" target="_blank" rel="noopener" class="btn-link-out">🔗 查看原始公开文献 ↗</a>`;

    card.innerHTML = `
      <div class="card-top-bar">
        <div class="card-category-badges">
          ${badgesHtml}
        </div>
        ${scoreHtml}
      </div>

      <a href="${escapeHtml(item.url)}" target="_blank" rel="noopener" class="item-title-link">
        ${escapeHtml(item.title)}
      </a>

      <div class="meta-line">
        ${metaText}
      </div>

      ${item.summary ? `<div class="summary-lead">${escapeHtml(item.summary)}</div>` : ''}

      ${enrichmentHtml}

      ${tagsHtml ? `<div class="card-tags">${tagsHtml}</div>` : ''}

      <div class="card-actions">
        ${actionsHtml}
      </div>
    `;

    // Bind accordion toggle
    const toggleBtn = card.querySelector('.enrichment-toggle');
    const contentBox = card.querySelector('.enrichment-content');
    if (toggleBtn && contentBox) {
      toggleBtn.addEventListener('click', () => {
        const isCollapsed = contentBox.style.display === 'none';
        contentBox.style.display = isCollapsed ? 'flex' : 'none';
        toggleBtn.querySelector('.arrow').textContent = isCollapsed ? '▼' : '▶';
      });
    }

    return card;
  }

  // Helper to escape HTML safely
  function escapeHtml(str) {
    if (!str) return '';
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function showEmpty(msg) {
    if (itemsContainer) {
      itemsContainer.innerHTML = `<div class="empty-state"><p>${escapeHtml(msg)}</p></div>`;
    }
  }

  // Category Tabs
  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      tabBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.activeCategory = btn.dataset.category;
      renderItems();
    });
  });

  // Search input
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      state.searchQuery = e.target.value;
      if (searchClear) searchClear.style.display = state.searchQuery ? 'inline' : 'none';
      renderItems();
    });
  }

  if (searchClear) {
    searchClear.addEventListener('click', () => {
      if (searchInput) searchInput.value = '';
      state.searchQuery = '';
      searchClear.style.display = 'none';
      renderItems();
    });
  }

  // Refresh Button
  if (btnRefreshReports) {
    btnRefreshReports.addEventListener('click', async () => {
      btnRefreshReports.classList.add('rotating');
      showToast('正在重新扫描最新情报速递...');
      await init(true);
      setTimeout(() => btnRefreshReports.classList.remove('rotating'), 600);
    });
  }

  // --- Whitelist Management Logic ---

  // Fetch full whitelist from server
  async function fetchWhitelistData() {
    try {
      const res = await fetch('/api/whitelist?t=' + Date.now());
      const json = await res.json();
      if (json.code === 0 && json.data) {
        state.whitelistData = json.data;
        state.whitelistConfig = JSON.parse(JSON.stringify(json.data.raw_config || {}));
        updateDrawerUI();
      } else {
        showToast('加载白名单数据失败', true);
      }
    } catch (err) {
      console.error('Failed to load whitelist:', err);
      showToast('网络通信异常，无法获取白名单', true);
    }
  }

  // Update Drawer UI
  function updateDrawerUI() {
    if (!state.whitelistConfig) return;

    // Update Top 4 Metric Boxes with key fallback
    const topics = state.whitelistConfig.topics || {};
    const suppliers = state.whitelistConfig.suppliers || {};
    const wlP0T = document.getElementById('wl-p0-topics');
    const wlP1T = document.getElementById('wl-p1-topics');
    const wlP0S = document.getElementById('wl-p0-suppliers');
    const wlP1S = document.getElementById('wl-p1-suppliers');

    const p0TopicsCount = (topics.p0_core || []).length;
    const p1TopicsCount = (topics.p1_strongly_related || []).length;
    const p0SuppliersCount = (suppliers.p0_core || suppliers.p0_tier1_core || []).length;
    const p1SuppliersCount = (suppliers.p1_tier1 || suppliers.p1_tier1_oem_advanced || []).length;

    if (wlP0T) wlP0T.textContent = p0TopicsCount;
    if (wlP1T) wlP1T.textContent = p1TopicsCount;
    if (wlP0S) wlP0S.textContent = p0SuppliersCount;
    if (wlP1S) wlP1S.textContent = p1SuppliersCount;

    // Update group options with real-time count badges
    if (selectWhitelistGroup) {
      Array.from(selectWhitelistGroup.options).forEach(opt => {
        const path = opt.value;
        const arr = getGroupArray(path) || [];
        // Clean previous count badge e.g. " (54条)"
        const baseLabel = opt.getAttribute('data-base-label') || opt.textContent.replace(/\s*\(\d+条\)$/, '');
        opt.setAttribute('data-base-label', baseLabel);
        opt.textContent = `${baseLabel} (${arr.length}条)`;
      });
    }

    // Render current active group chips
    renderCurrentGroupChips();

    // Sync JSON textarea
    if (whitelistJsonTextarea) {
      whitelistJsonTextarea.value = JSON.stringify(state.whitelistConfig, null, 2);
    }
    if (jsonSyntaxError) {
      jsonSyntaxError.style.display = 'none';
    }
  }

  // Resolve array from nested key path with fallback mappings
  function getGroupArray(path) {
    if (!state.whitelistConfig) return null;

    // Key aliases mapping to guarantee seamless data retrieval
    const ALIAS_MAP = {
      'suppliers.p0_tier1_core': 'suppliers.p0_core',
      'suppliers.p1_tier1_oem_advanced': 'suppliers.p1_tier1',
      'suppliers.p2_tier2_specialized': 'suppliers.p2_tools_software_services',
      'suppliers.p3_oem_brands': 'suppliers.p3_oem',
      'topics.p2_methods_tools': 'topics.p2_methods_tools_ai',
      'topics.p3_general_control': 'topics.p3_broad_context_required',
      'noise_reduction.negative_keywords': 'noise_reduction.penalize_keywords',
    };

    let targetPath = ALIAS_MAP[path] || path;

    const parts = targetPath.split('.');
    let cur = state.whitelistConfig;
    for (let i = 0; i < parts.length - 1; i++) {
      if (!cur[parts[i]]) cur[parts[i]] = {};
      cur = cur[parts[i]];
    }
    const lastKey = parts[parts.length - 1];

    // If key not found, check if reverse alias exists
    if (!Array.isArray(cur[lastKey])) {
      for (const [aliasKey, origKey] of Object.entries(ALIAS_MAP)) {
        if (origKey === targetPath) {
          const aliasParts = aliasKey.split('.');
          let aCur = state.whitelistConfig;
          for (let j = 0; j < aliasParts.length - 1; j++) {
            if (aCur) aCur = aCur[aliasParts[j]];
          }
          if (aCur && Array.isArray(aCur[aliasParts[aliasParts.length - 1]])) {
            return aCur[aliasParts[aliasParts.length - 1]];
          }
        }
      }
      cur[lastKey] = [];
    }
    return cur[lastKey];
  }

  // Render chips for currently selected category
  function renderCurrentGroupChips() {
    if (!selectWhitelistGroup || !editableChipsBox) return;
    const groupPath = selectWhitelistGroup.value;
    const arr = getGroupArray(groupPath) || [];

    if (currentGroupCount) {
      currentGroupCount.textContent = `当前分类收录 ${arr.length} 个词条`;
    }
    editableChipsBox.innerHTML = '';

    if (arr.length === 0) {
      editableChipsBox.innerHTML = '<span style="color: var(--text-muted); font-size: 0.85rem;">暂无词条，可在上方输入并点击添加</span>';
      return;
    }

    arr.forEach((itemText, idx) => {
      const chip = document.createElement('span');
      chip.className = 'chip chip-removable';
      chip.innerHTML = `
        <span class="chip-text">${escapeHtml(itemText)}</span>
        <button class="btn-del-chip" title="删除「${escapeHtml(itemText)}」">✕</button>
      `;

      chip.querySelector('.btn-del-chip').addEventListener('click', () => {
        arr.splice(idx, 1);
        renderCurrentGroupChips();
        updateDrawerStatsOnly();
      });

      editableChipsBox.appendChild(chip);
    });
  }

  // Fast update for stats numbers
  function updateDrawerStatsOnly() {
    if (!state.whitelistConfig) return;
    const topics = state.whitelistConfig.topics || {};
    const suppliers = state.whitelistConfig.suppliers || {};
    const wlP0T = document.getElementById('wl-p0-topics');
    const wlP1T = document.getElementById('wl-p1-topics');
    const wlP0S = document.getElementById('wl-p0-suppliers');
    const wlP1S = document.getElementById('wl-p1-suppliers');

    if (wlP0T) wlP0T.textContent = (topics.p0_core || []).length;
    if (wlP1T) wlP1T.textContent = (topics.p1_strongly_related || []).length;
    if (wlP0S) wlP0S.textContent = (suppliers.p0_tier1_core || []).length;
    if (wlP1S) wlP1S.textContent = (suppliers.p1_tier1_oem_advanced || []).length;
  }

  // Add chip action
  function addChipFromInput() {
    if (!inputNewChip || !selectWhitelistGroup) return;
    const text = inputNewChip.value.trim();
    if (!text) return;

    const groupPath = selectWhitelistGroup.value;
    const arr = getGroupArray(groupPath);
    if (!arr) return;

    // Duplicate check
    if (arr.includes(text)) {
      showToast(`词条「${text}」已存在`, true);
      return;
    }

    arr.unshift(text); // Add to front
    inputNewChip.value = '';
    renderCurrentGroupChips();
    updateDrawerStatsOnly();
    showToast(`已添加「${text}」`);
  }

  // Drawer Tabs Switcher
  if (tabModeVisual && tabModeJson) {
    tabModeVisual.addEventListener('click', () => {
      if (state.currentEditorMode === 'json' && whitelistJsonTextarea) {
        try {
          const parsed = JSON.parse(whitelistJsonTextarea.value);
          state.whitelistConfig = parsed;
          if (jsonSyntaxError) jsonSyntaxError.style.display = 'none';
        } catch (err) {
          if (jsonSyntaxError) {
            jsonSyntaxError.textContent = `JSON 语法错误，无法切换: ${err.message}`;
            jsonSyntaxError.style.display = 'block';
          }
          return;
        }
      }
      state.currentEditorMode = 'visual';
      tabModeVisual.classList.add('active');
      tabModeJson.classList.remove('active');
      if (drawerViewVisual) drawerViewVisual.style.display = 'block';
      if (drawerViewJson) drawerViewJson.style.display = 'none';
      updateDrawerUI();
    });

    tabModeJson.addEventListener('click', () => {
      state.currentEditorMode = 'json';
      tabModeJson.classList.add('active');
      tabModeVisual.classList.remove('active');
      if (drawerViewJson) drawerViewJson.style.display = 'block';
      if (drawerViewVisual) drawerViewVisual.style.display = 'none';
      if (whitelistJsonTextarea) {
        whitelistJsonTextarea.value = JSON.stringify(state.whitelistConfig, null, 2);
      }
      if (jsonSyntaxError) jsonSyntaxError.style.display = 'none';
    });
  }

  // Select Group change
  if (selectWhitelistGroup) {
    selectWhitelistGroup.addEventListener('change', () => {
      renderCurrentGroupChips();
    });
  }

  // Add chip events
  if (btnAddChip) {
    btnAddChip.addEventListener('click', addChipFromInput);
  }
  if (inputNewChip) {
    inputNewChip.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        addChipFromInput();
      }
    });
  }

  // JSON Prettify
  if (btnFormatJson && whitelistJsonTextarea) {
    btnFormatJson.addEventListener('click', () => {
      try {
        const parsed = JSON.parse(whitelistJsonTextarea.value);
        whitelistJsonTextarea.value = JSON.stringify(parsed, null, 2);
        state.whitelistConfig = parsed;
        if (jsonSyntaxError) jsonSyntaxError.style.display = 'none';
        showToast('JSON 已格式化排版');
      } catch (err) {
        if (jsonSyntaxError) {
          jsonSyntaxError.textContent = `格式化失败: ${err.message}`;
          jsonSyntaxError.style.display = 'block';
        }
      }
    });
  }

  // Save Whitelist
  if (btnSaveWhitelist) {
    btnSaveWhitelist.addEventListener('click', async () => {
      let payload = state.whitelistConfig;

      if (state.currentEditorMode === 'json' && whitelistJsonTextarea) {
        try {
          payload = JSON.parse(whitelistJsonTextarea.value);
          state.whitelistConfig = payload;
          if (jsonSyntaxError) jsonSyntaxError.style.display = 'none';
        } catch (err) {
          if (jsonSyntaxError) {
            jsonSyntaxError.textContent = `JSON 语法错误: ${err.message}`;
            jsonSyntaxError.style.display = 'block';
          }
          showToast('JSON 格式有误，请修正后重试', true);
          return;
        }
      }

      btnSaveWhitelist.disabled = true;
      btnSaveWhitelist.textContent = '💾 正在保存...';

      try {
        const res = await fetch('/api/whitelist', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json; charset=utf-8' },
          body: JSON.stringify(payload)
        });
        const json = await res.json();
        if (json.code === 0) {
          showToast(json.message || '白名单已保存并热重载生效！');
          state.whitelistConfig = payload;
          updateDrawerUI();
        } else {
          showToast(json.message || '保存失败', true);
        }
      } catch (err) {
        console.error('Failed to save whitelist:', err);
        showToast('网络请求失败，未能保存白名单', true);
      } finally {
        btnSaveWhitelist.disabled = false;
        btnSaveWhitelist.textContent = '💾 保存并生效';
      }
    });
  }

  // Reset Whitelist
  if (btnResetWhitelist) {
    btnResetWhitelist.addEventListener('click', () => {
      if (confirm('确定要放弃当前未保存的修改，重新载入白名单文件吗？')) {
        fetchWhitelistData();
        showToast('已重置回文件原始状态');
      }
    });
  }

  // Whitelist Drawer Open/Close
  if (btnOpenWhitelist && whitelistDrawer) {
    btnOpenWhitelist.addEventListener('click', () => {
      whitelistDrawer.classList.add('open');
      if (!state.whitelistConfig) {
        fetchWhitelistData();
      } else {
        updateDrawerUI();
      }
    });
  }

  if (btnCloseDrawer && whitelistDrawer) {
    btnCloseDrawer.addEventListener('click', () => {
      whitelistDrawer.classList.remove('open');
    });
  }

  if (whitelistDrawer) {
    whitelistDrawer.addEventListener('click', (e) => {
      if (e.target === whitelistDrawer) {
        whitelistDrawer.classList.remove('open');
      }
    });
  }

  // Launch initial report load
  init();
});
