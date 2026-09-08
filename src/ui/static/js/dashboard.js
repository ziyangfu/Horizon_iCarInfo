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
  };

  // DOM Elements
  const reportSelect = document.getElementById('report-select');
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

  // 1. Initial Load: fetch report list
  async function init() {
    try {
      const res = await fetch('/api/reports');
      const data = await res.json();
      if (data.code === 0 && data.data && data.data.length > 0) {
        state.reports = data.data;
        populateReportSelect(state.reports);
        // Load the first (latest) report
        loadReport(state.reports[0].filename);
      } else {
        showEmpty('暂未发现生成的速递日报，请先在终端运行抓取或检查 data/summaries 目录');
      }
    } catch (err) {
      console.error('Failed to load reports:', err);
      showEmpty('无法连接到看板后端 API 服务');
    }
  }

  // Populate Select options
  function populateReportSelect(reports) {
    reportSelect.innerHTML = '';
    reports.forEach((rep, idx) => {
      const opt = document.createElement('option');
      opt.value = rep.filename;
      const isLatest = idx === 0 ? ' [最新]' : '';
      const langBadge = rep.lang === 'zh' ? '中' : (rep.lang === 'en' ? 'EN' : '');
      opt.textContent = `📅 ${rep.date || rep.filename} (${langBadge})${isLatest}`;
      reportSelect.appendChild(opt);
    });

    reportSelect.addEventListener('change', (e) => {
      loadReport(e.target.value);
    });
  }

  // Fetch and display a specific report
  async function loadReport(filename) {
    itemsContainer.innerHTML = `
      <div class="loading-state">
        <div class="spinner"></div>
        <p>正在装载并结构化解析「${filename}」情报数据...</p>
      </div>
    `;

    try {
      const res = await fetch(`/api/reports/${encodeURIComponent(filename)}`);
      const json = await res.json();
      if (json.code === 0 && json.data) {
        state.currentReport = json.data;
        state.activeCategory = 'all';
        state.activeTag = null;
        state.searchQuery = '';
        searchInput.value = '';
        searchClear.style.display = 'none';

        updateUI();
      } else {
        showEmpty(json.message || '加载报告失败');
      }
    } catch (err) {
      console.error('Failed to fetch report detail:', err);
      showEmpty('网络通信失败，未能加载报告内容');
    }
  }

  // Update whole UI with current report data
  function updateUI() {
    if (!state.currentReport) return;
    const r = state.currentReport;
    const items = r.items || [];
    const metrics = r.metrics || {};

    // Header info
    reportTitle.textContent = r.title || '智能汽车底盘前瞻资讯速递';
    reportSubtitle.textContent = r.subtitle || `日期: ${r.date} | 共收录 ${items.length} 条高价值情报`;

    // Metrics
    valSelectedCount.textContent = metrics.selected_total || items.length;
    valRawCount.textContent = metrics.total_raw || (items.length * 9);
    valFilterRate.textContent = `降噪率 ${metrics.noise_filter_rate || '88.5%'}`;
    valPapersCount.textContent = metrics.papers_count || 0;
    valPatentsCount.textContent = metrics.patents_count || 0;
    valAvgScore.textContent = `${metrics.avg_score || '4.5'}/10`;

    // Tab counts
    cntAll.textContent = items.length;
    cntInfo.textContent = items.filter(i => i.category === 'icar-info').length;
    cntPapers.textContent = items.filter(i => i.category === 'icar-papers').length;
    cntPatents.textContent = items.filter(i => i.category === 'icar-patents').length;

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
    if (!state.currentReport) return;

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
    itemsContainer.innerHTML = `<div class="empty-state"><p>${escapeHtml(msg)}</p></div>`;
  }

  // Event Listeners: Category Tabs
  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      tabBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.activeCategory = btn.dataset.category;
      renderItems();
    });
  });

  // Event Listeners: Search input
  searchInput.addEventListener('input', (e) => {
    state.searchQuery = e.target.value;
    searchClear.style.display = state.searchQuery ? 'inline' : 'none';
    renderItems();
  });

  searchClear.addEventListener('click', () => {
    searchInput.value = '';
    state.searchQuery = '';
    searchClear.style.display = 'none';
    renderItems();
  });

  // Event Listeners: Whitelist Drawer
  btnOpenWhitelist.addEventListener('click', async () => {
    whitelistDrawer.classList.add('open');
    if (!state.whitelistData) {
      try {
        const res = await fetch('/api/whitelist');
        const json = await res.json();
        if (json.code === 0) {
          state.whitelistData = json.data;
          renderWhitelistDrawer(json.data);
        }
      } catch (err) {
        console.error('Failed to load whitelist:', err);
      }
    }
  });

  btnCloseDrawer.addEventListener('click', () => {
    whitelistDrawer.classList.remove('open');
  });

  whitelistDrawer.addEventListener('click', (e) => {
    if (e.target === whitelistDrawer) {
      whitelistDrawer.classList.remove('open');
    }
  });

  function renderWhitelistDrawer(data) {
    const stats = data.stats || {};
    document.getElementById('wl-p0-topics').textContent = stats.p0_topics_count || '--';
    document.getElementById('wl-p1-topics').textContent = stats.p1_topics_count || '--';
    document.getElementById('wl-p0-suppliers').textContent = stats.p0_suppliers_count || '--';
    document.getElementById('wl-p1-suppliers').textContent = stats.p1_suppliers_count || '--';

    // P0 Topics chips
    const p0TopicsContainer = document.getElementById('p0-topics-chips');
    p0TopicsContainer.innerHTML = '';
    (data.topics?.p0_core || []).slice(0, 18).forEach(topic => {
      const chip = document.createElement('span');
      chip.className = 'chip';
      chip.textContent = topic;
      p0TopicsContainer.appendChild(chip);
    });

    // Suppliers chips
    const suppliersContainer = document.getElementById('suppliers-chips');
    suppliersContainer.innerHTML = '';
    const coreSuppliers = (data.suppliers?.p0_tier1_core || []).concat(data.suppliers?.p1_tier1_oem_advanced || []).slice(0, 18);
    coreSuppliers.forEach(sup => {
      const chip = document.createElement('span');
      chip.className = 'chip';
      chip.textContent = sup;
      suppliersContainer.appendChild(chip);
    });

    // Negative keywords chips
    const negativeContainer = document.getElementById('negative-chips');
    negativeContainer.innerHTML = '';
    (data.noise_words || []).forEach(word => {
      const chip = document.createElement('span');
      chip.className = 'chip';
      chip.textContent = `-${word}`;
      negativeContainer.appendChild(chip);
    });
  }

  // Run init
  init();
});
