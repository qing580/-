(function () {
  'use strict';

  if (!window.ManagementData || !window.EncounterMath || typeof DATA === 'undefined') return;

  const originalEncounterOpen = openVesselDetail;
  const originalRenderAll = renderAll;
  const overviewPage = document.getElementById('overviewPage');
  const detailPage = document.getElementById('detailPage');
  const app = document.querySelector('.app');
  const statusOverrides = new Map();
  const operationLog = [];
  let currentView = 'overview';
  let currentEvent = null;
  const managementMarkerCache = new Map();
  let managementVisibleMmsis = new Set();
  let eventBundle = { snapshots: [], events: [] };
  let refreshQueued = false;

  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>'"]/g, char => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
    })[char]);
  }

  function formatTime(value, seconds = false) {
    const date = new Date(value);
    if (!Number.isFinite(date.getTime())) return '暂无';
    return new Intl.DateTimeFormat('zh-CN', {
      month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
      second: seconds ? '2-digit' : undefined, hour12: false
    }).format(date);
  }

  function formatNumber(value, digits = 1, suffix = '') {
    const numeric = Number(value);
    return Number.isFinite(numeric) ? `${numeric.toFixed(digits)}${suffix}` : '不可用';
  }

  function icon(name) {
    return `<i data-lucide="${name}" aria-hidden="true"></i>`;
  }

  function createShell() {
    document.body.classList.add('management-mode');
    document.body.insertAdjacentHTML('afterbegin', `
      <aside class="mg-sidebar" aria-label="管理端主导航">
        <div class="mg-brand"><div class="mg-brand-mark">${icon('radar')}</div><div class="mg-brand-copy"><strong>海上异常监测智能体</strong><span>马六甲海峡实验 · 管理端</span></div></div>
        <nav class="mg-nav">
          <div class="mg-nav-label">监测与处置</div>
          <button class="mg-nav-button active" data-mg-view="overview">${icon('map')}<span>综合态势</span></button>
          <button class="mg-nav-button" data-mg-view="events">${icon('list-filter')}<span>异常事件中心</span></button>
          <button class="mg-nav-button" data-mg-view="event-detail">${icon('scan-search')}<span>事件研判</span></button>
          <button class="mg-nav-button" data-mg-view="vessels">${icon('ship')}<span>船舶档案</span></button>
          <div class="mg-nav-label">数据与能力</div>
          <button class="mg-nav-button" data-mg-view="environment">${icon('cloud-sun')}<span>环境监测</span></button>
          <button class="mg-nav-button" data-mg-view="models">${icon('database-zap')}<span>数据与模型</span></button>
        </nav>
        <div class="mg-sidebar-foot"><strong>辅助研判系统</strong>不替代 COLREGs 与人工航海判断</div>
      </aside>
      <header class="mg-topbar">
        <div class="mg-page-heading"><strong id="mgPageTitle">综合态势</strong><span id="mgPageSubtitle">马六甲海峡六小时增强 AIS 历史回放</span></div>
        <div class="mg-kpi"><b id="mgShipCount">0</b><span>当前活跃船舶</span></div>
        <div class="mg-kpi danger"><b id="mgHighCount">0</b><span>高风险会遇</span></div>
        <div class="mg-kpi"><b id="mgPendingCount">0</b><span>待确认/核查</span></div>
        <div class="mg-kpi"><b id="mgQuality">0%</b><span>位置字段有效率</span></div>
        <div class="mg-system-state"><i></i><span id="mgDataState">历史数据已载入</span></div>
      </header>
      <div id="mgToast" class="mg-toast" role="status"></div>`);

    overviewPage.insertAdjacentHTML('beforeend', `
      <aside id="mgEventRail" class="mg-event-rail" aria-label="优先处置事件">
        <div class="mg-rail-head"><div><h2>优先处置</h2><span>碰撞风险与行为初筛</span></div><span id="mgRailTime">--</span></div>
        <div class="mg-rail-note">仅展示 Top 5。点击事件查看计算依据、数据时间和不确定因素。</div>
        <div id="mgTopEvents" class="mg-event-list"></div>
        <div class="mg-rail-footer"><button id="mgAllEvents" class="mg-button primary">${icon('arrow-right')}查看全部事件</button></div>
      </aside>`);

    app.insertAdjacentHTML('beforeend', pagesMarkup());
    document.getElementById('reviewFilter').hidden = true;
    document.getElementById('riskFilter').hidden = true;
    document.getElementById('highRiskBtn').hidden = true;
    detailPage.classList.add('hidden');
  }

  function pagesMarkup() {
    return `
      <section id="mgEventsPage" class="mg-page" data-page="events">
        <div class="mg-page-inner">
          <div class="mg-section-head"><div><h1>异常事件中心</h1><p>从地图告警进入可核查、可流转的事件列表。当前状态操作仅保存在本次演示会话。</p></div><div class="mg-actions"><button class="mg-button" data-route="overview">${icon('map')}返回态势</button></div></div>
          <div class="mg-card mg-filterbar"><input id="mgEventSearch" placeholder="搜索事件编号、船名或 MMSI"><select id="mgRiskFilter"><option value="全部">全部风险</option><option value="高风险">高风险</option><option value="中高风险">中高风险</option><option value="中等关注">中等关注</option></select><select id="mgStatusFilter"><option value="全部">全部状态</option><option value="待确认">待确认</option><option value="待核查">待核查</option><option value="已派单">已派单</option><option value="处理中">处理中</option><option value="已确认">已确认</option><option value="已关闭">已关闭</option><option value="误报或证据不足">误报或证据不足</option></select><button id="mgResetStatus" class="mg-button">${icon('rotate-ccw')}重置演示状态</button></div>
          <div class="mg-card"><div class="mg-card-head"><h2>当前时间片事件</h2><span id="mgEventCount">0 条</span></div><div class="mg-table-wrap"><table class="mg-table"><thead><tr><th>事件编号</th><th>事件类型</th><th>涉及对象</th><th>核心证据</th><th>风险</th><th>可信提示</th><th>状态</th><th>更新时间</th></tr></thead><tbody id="mgEventRows"></tbody></table><div id="mgEventEmpty" class="mg-empty" hidden>当前筛选条件下没有事件。</div></div></div>
        </div>
      </section>
      <section id="mgEventDetailPage" class="mg-page" data-page="event-detail"><div id="mgEventDetail" class="mg-page-inner"></div></section>
      <section id="mgVesselsPage" class="mg-page" data-page="vessels"><div id="mgVesselDetail" class="mg-page-inner"></div></section>
      <section id="mgEnvironmentPage" class="mg-page" data-page="environment">
        <div class="mg-page-inner"><div class="mg-section-head"><div><h1>环境监测</h1><p>环境模块保持真实数据边界，未接入的数据不使用模拟值替代。</p></div></div>
          <div class="mg-card mg-empty-state"><div class="mg-empty-copy"><div class="mg-empty-icon">${icon('cloud-sun')}</div><h1>马六甲海峡环境数据暂未接入</h1><p>当前页面不显示虚构的台风、风浪、海流、赤潮或油膜结果。接入后，每个图层必须同时显示数据来源、观测时间、空间分辨率和置信度。</p><div class="mg-callout">“叶绿素异常区”不能直接表述为“赤潮区”；遥感油膜暗斑也需要结合风速、云影和人工核查。</div></div><div class="mg-source-list"><div class="mg-source-item"><b>台风路径与预报</b><span>需要预报时次、中心位置、强度和影响半径</span></div><div class="mg-source-item"><b>风、浪、海流</b><span>需要有效时间、网格范围和数据更新时间</span></div><div class="mg-source-item"><b>海温与叶绿素</b><span>需要卫星产品、云量、观测时间和异常基线</span></div><div class="mg-source-item"><b>油膜疑似区</b><span>需要 SAR/光学证据、识别置信度和误报因素</span></div><div class="mg-source-item"><b>航道与敏感设施</b><span>需要交通分离制、锚地、港口和设施矢量数据</span></div><div class="mg-source-item"><b>下一步接入原则</b><span>先完成来源与许可审计，再设计多源时空对齐</span></div></div></div>
        </div>
      </section>
      <section id="mgModelsPage" class="mg-page" data-page="models"><div id="mgModelContent" class="mg-page-inner"></div></section>`;
  }

  function currentEvents() {
    return eventBundle.events.map(event => ({ ...event, status: statusOverrides.get(event.id) || event.status }));
  }

  function vesselEncounterRisk(mmsi) {
    return currentEvents().filter(event => event.cpa &&
      event.vessels.some(vessel => String(vessel.mmsi) === String(mmsi)))
      .sort((a, b) => b.score - a.score)[0] || null;
  }

  function managementVesselIcon(vessel) {
    const event = vesselEncounterRisk(vessel.mmsi);
    const riskClass = event?.tone === 'critical' ? 'risk-high' : 'risk-low';
    const selectedIcon = selected && String(selected.mmsi) === String(vessel.mmsi);
    const color = COLORS[vessel.category] || COLORS['未知'];
    const html = `<div class="risk-marker ${riskClass} ${selectedIcon ? 'selected' : ''}" title="${event ? `${escapeHtml(event.level)} ${event.score}分` : escapeHtml(vessel.category)}"><span class="risk-halo"></span><span class="ship-wrap">${shipSvg(vessel.category, color, headingOf(vessel), selectedIcon)}</span></div>`;
    return L.divIcon({ className: `ship-marker ${selectedIcon ? 'selected' : ''}`, html, iconSize: [88, 46], iconAnchor: [44, 28] });
  }

  function renderManagementMap(fit = false) {
    clearLayers();
    const category = document.getElementById('categoryFilter').value;
    const bounds = [];
    const nextVisible = new Set();
    eventBundle.snapshots.filter(item => item.ageMinutes <= 5 && (category === '全部' || item.vessel.category === category)).forEach(item => {
      const vessel = { ...item.vessel, points: [item.point] };
      const key = String(vessel.mmsi);
      const replayState = preparedVessels.has(key) ? HistoricalAisReplay.stateAt(preparedVessels.get(key), currentTime()) : null;
      const position = replayState ? [replayState.displayPosition.lat, replayState.displayPosition.lon] : [item.point.lat, item.point.lon];
      let marker = managementMarkerCache.get(key);
      if (!marker) {
        marker = L.marker(position, { icon: managementVesselIcon(vessel), riseOnHover: true });
        marker.on('click', () => openVesselDetail(key, false));
        managementMarkerCache.set(key, marker);
      } else {
        marker.setLatLng(position).setIcon(managementVesselIcon(vessel));
      }
      marker.addTo(map);
      marker.bindTooltip(`${escapeHtml(vessel.name || '未命名')} · ${escapeHtml(vessel.category)}`, { direction: 'top', offset: [0, -12] });
      if (replayState) updateMarkerReplayClass(marker, replayState);
      layers.push(marker);
      nextVisible.add(key);
      bounds.push(position);
    });
    managementVisibleMmsis = nextVisible;
    if (fit && bounds.length) map.fitBounds(bounds, { padding: [38, 38] });
  }

  replayFrameHooks.push(timeMs => {
    if (currentView !== 'overview') return;
    managementVisibleMmsis.forEach(key => {
      const marker = managementMarkerCache.get(key);
      const prepared = preparedVessels.get(key);
      if (!marker || !prepared || !map.hasLayer(marker)) return;
      const replayState = HistoricalAisReplay.stateAt(prepared, timeMs);
      if (!replayState) return;
      marker.setLatLng([replayState.displayPosition.lat, replayState.displayPosition.lon]);
      updateMarkerReplayClass(marker, replayState);
    });
  });

  function refreshData() {
    eventBundle = ManagementData.buildEvents(DATA.vessels, currentTime(), EncounterMath);
    if (currentEvent) currentEvent = currentEvents().find(event => event.id === currentEvent.id) || currentEvent;
  }

  function refreshKpis() {
    const quality = ManagementData.dataQuality(DATA.vessels);
    const events = currentEvents();
    const freshShips = eventBundle.snapshots.filter(item => item.ageMinutes <= 5).length;
    const high = events.filter(event => event.level === '高风险').length;
    const pending = events.filter(event => ['待确认', '待核查', '已派单', '处理中'].includes(event.status)).length;
    document.getElementById('mgShipCount').textContent = freshShips;
    document.getElementById('mgHighCount').textContent = high;
    document.getElementById('mgPendingCount').textContent = pending;
    document.getElementById('mgQuality').textContent = `${(quality.positionValidity * 100).toFixed(1)}%`;
    document.getElementById('mgDataState').textContent = `${isPlaying ? '历史回放中' : '历史回放已暂停'} · ${formatTime(currentTime(), true)}`;
    document.getElementById('liveStatus').textContent = `${isPlaying ? '回放中' : '已暂停'}：${freshShips} 艘活跃 / ${high} 个高风险会遇`;
  }

  function evidenceText(event) {
    if (event.cpa) return `DCPA ${formatNumber(event.cpa.dcpa, 2, ' nm')} · TCPA ${formatNumber(event.cpa.tcpa, 1, ' min')}`;
    return event.metric || '查看初筛依据';
  }

  function vesselNames(event) {
    return event.vessels.map(vessel => vessel.name || vessel.mmsi).join(' / ');
  }

  function renderRail() {
    const events = currentEvents().slice(0, 5);
    document.getElementById('mgRailTime').textContent = formatTime(currentTime());
    const wrap = document.getElementById('mgTopEvents');
    wrap.innerHTML = events.length ? events.map((event, index) => `
      <button class="mg-event-item ${event.tone}" data-event-id="${escapeHtml(event.id)}">
        <span class="mg-event-rank">${index + 1}</span><span class="mg-event-copy"><b>${escapeHtml(event.kind)}</b><span>${escapeHtml(vesselNames(event))}<br>${escapeHtml(evidenceText(event))}</span></span><strong class="mg-event-score">${event.score}</strong>
      </button>`).join('') : '<div class="mg-empty">当前时刻未筛选出中等关注及以上事件。继续播放可观察其他时间片。</div>';
    wrap.querySelectorAll('[data-event-id]').forEach(button => button.addEventListener('click', () => openEvent(button.dataset.eventId)));
  }

  function filteredEvents() {
    const search = document.getElementById('mgEventSearch').value.trim().toLowerCase();
    const risk = document.getElementById('mgRiskFilter').value;
    const status = document.getElementById('mgStatusFilter').value;
    return currentEvents().filter(event => {
      const haystack = `${event.id} ${event.kind} ${vesselNames(event)} ${event.vessels.map(v => v.mmsi).join(' ')}`.toLowerCase();
      return (!search || haystack.includes(search)) && (risk === '全部' || event.level === risk) && (status === '全部' || event.status === status);
    });
  }

  function renderEventTable() {
    const allRows = filteredEvents();
    const rows = allRows.slice(0, 20);
    const tbody = document.getElementById('mgEventRows');
    document.getElementById('mgEventCount').textContent = allRows.length > rows.length ? `优先显示 ${rows.length} / ${allRows.length} 条` : `${rows.length} 条`;
    document.getElementById('mgEventEmpty').hidden = allRows.length > 0;
    tbody.innerHTML = rows.map(event => `
      <tr data-event-id="${escapeHtml(event.id)}"><td><b>${escapeHtml(event.id)}</b></td><td>${escapeHtml(event.kind)}</td><td>${escapeHtml(vesselNames(event))}</td><td>${escapeHtml(evidenceText(event))}</td><td><span class="mg-risk-pill ${event.tone}">${escapeHtml(event.level)} · ${event.score}</span></td><td>${escapeHtml(event.confidence)}</td><td><span class="mg-status-pill">${escapeHtml(event.status)}</span></td><td>${escapeHtml(formatTime(event.updatedAt))}</td></tr>`).join('');
    tbody.querySelectorAll('[data-event-id]').forEach(row => row.addEventListener('click', () => openEvent(row.dataset.eventId)));
  }

  function renderEventDetail() {
    const events = currentEvents();
    const event = currentEvent || events[0];
    const wrap = document.getElementById('mgEventDetail');
    if (!event) {
      wrap.innerHTML = `<div class="mg-section-head"><div><h1>事件研判</h1><p>当前时间片暂无可研判事件。</p></div><button class="mg-button" data-route="overview">${icon('map')}返回态势</button></div><div class="mg-card mg-empty">继续播放历史 AIS 数据后再查看事件证据。</div>`;
      bindRoutes(wrap);
      return;
    }
    currentEvent = event;
    const cpa = event.cpa;
    const parts = event.risk?.parts;
    const vessels = event.vessels;
    const nextStatus = { '待确认': '待核查', '待核查': '已派单', '已派单': '处理中', '处理中': '已确认', '已确认': '已关闭' }[event.status];
    wrap.innerHTML = `
      <div class="mg-section-head"><div><h1>事件研判与证据链</h1><p>${escapeHtml(event.id)} · 数据时间 ${escapeHtml(formatTime(event.updatedAt, true))}</p></div><div class="mg-actions"><button class="mg-button" data-route="events">${icon('list-filter')}事件中心</button><button class="mg-button" data-route="overview">${icon('map')}综合态势</button></div></div>
      <div class="mg-detail-grid"><main class="mg-evidence-stack">
        <section class="mg-card mg-hero"><div><div class="mg-hero-kicker">${escapeHtml(event.kind)} · ${escapeHtml(event.source)}</div><h1>${escapeHtml(vesselNames(event))}</h1><p>${escapeHtml(event.explanation)} 当前结论为辅助研判结果，需要结合航道、作业状态和人工观察进一步确认。</p></div><div class="mg-score">${event.score}<small>${escapeHtml(event.level)} / 100</small></div></section>
        <section class="mg-card"><div class="mg-card-head"><h2>核心运动学证据</h2><span>${escapeHtml(event.encounterShape || '行为变化初筛')}</span></div><div class="mg-metric-grid"><div class="mg-metric-box"><span>最近会遇距离 DCPA</span><b>${cpa ? formatNumber(cpa.dcpa, 2, ' nm') : '不适用'}</b></div><div class="mg-metric-box"><span>最近会遇时间 TCPA</span><b>${cpa ? formatNumber(cpa.tcpa, 1, ' min') : '不适用'}</b></div><div class="mg-metric-box"><span>当前距离 / 行为幅度</span><b>${cpa ? formatNumber(event.distance, 2, ' nm') : escapeHtml(event.metric || '不可用')}</b></div></div></section>
        <section class="mg-card"><div class="mg-card-head"><h2>算法依据与不确定性</h2><span>版本 CPA-TCPA v1.0 / 行为规则 v0.1</span></div><div class="mg-evidence-body"><dl>
          <div class="mg-evidence-row"><dt>数据来源</dt><dd>${escapeHtml(event.source)}</dd></div><div class="mg-evidence-row"><dt>船舶对象</dt><dd>${vessels.map(v => `${escapeHtml(v.name || '未命名')}（${escapeHtml(v.mmsi)}，${escapeHtml(v.category)}）`).join('<br>')}</dd></div><div class="mg-evidence-row"><dt>位置</dt><dd>${formatNumber(event.location.lat, 5)}°, ${formatNumber(event.location.lon, 5)}°</dd></div><div class="mg-evidence-row"><dt>可信提示</dt><dd>${escapeHtml(event.confidence)}。${cpa?.label ? escapeHtml(cpa.label) : '阈值用于演示初筛，尚未经过标注测试集验证。'}</dd></div>
        </dl>${parts ? `<div class="mg-bar-row"><div class="mg-bar-label"><span>DCPA贡献 · 权重38%</span><b>${Math.round(parts.cpaScore * 100)}</b></div><div class="mg-bar"><i style="width:${Math.round(parts.cpaScore * 100)}%"></i></div></div><div class="mg-bar-row"><div class="mg-bar-label"><span>TCPA贡献 · 权重28%</span><b>${Math.round(parts.tcpaScore * 100)}</b></div><div class="mg-bar"><i style="width:${Math.round(parts.tcpaScore * 100)}%"></i></div></div><div class="mg-bar-row"><div class="mg-bar-label"><span>当前距离贡献 · 权重18%</span><b>${Math.round(parts.distanceScore * 100)}</b></div><div class="mg-bar"><i style="width:${Math.round(parts.distanceScore * 100)}%"></i></div></div>` : ''}<div class="mg-callout">CPA/TCPA 基于匀速直线外推，只用于风险筛查，不能替代 COLREGs、驾驶台观察和法定避碰决策。</div></div></section>
      </main><aside class="mg-evidence-stack">
        <section class="mg-card"><div class="mg-card-head"><h2>处置状态</h2><span>前端演示状态</span></div><div class="mg-evidence-body"><p><span class="mg-status-pill">${escapeHtml(event.status)}</span></p><div class="mg-actions" style="justify-content:flex-start">${nextStatus ? `<button id="mgAdvanceStatus" class="mg-button primary">${icon('arrow-right')}流转为${nextStatus}</button>` : ''}<button id="mgInsufficient" class="mg-button">${icon('circle-help')}证据不足</button><button id="mgCloseEvent" class="mg-button">${icon('check')}关闭事件</button></div><div class="mg-callout">状态变更仅用于演示事件闭环，尚未接入真实用户、权限和后端工单。</div></div></section>
        <section class="mg-card"><div class="mg-card-head"><h2>建议核查动作</h2><span>智能体解释层</span></div><div class="mg-evidence-body"><ol><li>检查两船后续 AIS 航向和航速是否持续。</li><li>核对附近航道、锚地和作业状态。</li><li>确认 AIS 数据时延与船型字段可靠性。</li><li>必要时调取更多时段数据或开展人工核查。</li></ol></div></section>
        ${event.kind === '高风险会遇' ? `<button id="mgPlayEncounter" class="mg-button danger">${icon('play')}播放会遇情景演示</button>` : ''}
      </aside></div>`;
    bindRoutes(wrap);
    if (nextStatus) document.getElementById('mgAdvanceStatus').onclick = () => setEventStatus(event, nextStatus);
    document.getElementById('mgInsufficient').onclick = () => setEventStatus(event, '误报或证据不足');
    document.getElementById('mgCloseEvent').onclick = () => setEventStatus(event, '已关闭');
    const play = document.getElementById('mgPlayEncounter');
    if (play) play.onclick = () => {
      selected = activeVessels().find(v => String(v.mmsi) === String(event.vessels[0].mmsi)) || selected;
      originalEncounterOpen(event.vessels[0].mmsi, false);
    };
  }

  function renderVesselDetail() {
    const current = selected && eventBundle.snapshots.find(item => String(item.vessel.mmsi) === String(selected.mmsi));
    const vessel = current?.vessel || selected || DATA.vessels[0];
    const point = current?.point || vessel.points[vessel.points.length - 1];
    const points = vessel.points.filter(item => Number.isFinite(Date.parse(item.time)));
    const speeds = points.map(item => Number(item.sog)).filter(value => Number.isFinite(value) && value < 102.3);
    const related = currentEvents().filter(event => event.vessels.some(item => String(item.mmsi) === String(vessel.mmsi))).slice(0, 5);
    const wrap = document.getElementById('mgVesselDetail');
    wrap.innerHTML = `
      <div class="mg-section-head"><div><h1>船舶档案与行为画像</h1><p>身份、分类来源、当前状态和本批次行为证据分开展示。</p></div><div class="mg-actions"><button class="mg-button" data-route="overview">${icon('map')}返回态势</button>${related[0] ? `<button id="mgRelatedEvent" class="mg-button primary">${icon('scan-search')}查看关联事件</button>` : ''}</div></div>
      <section class="mg-card mg-vessel-summary"><div class="mg-ship-preview">${shipSvg(vessel.category, COLORS[vessel.category] || COLORS['未知'], 90, true)}</div><div><div class="mg-card-head" style="padding-left:0"><div><h2>${escapeHtml(vessel.name || '未获取船名')}</h2><span>MMSI ${escapeHtml(vessel.mmsi)} · ${escapeHtml(vessel.category)}</span></div><span class="mg-quality-pill ${vessel.category === '未知' ? 'bad' : ''}">${escapeHtml(vessel.source || '分类来源未标注')}</span></div><div class="mg-fact-grid"><div class="mg-fact"><span>IMO</span><b>${escapeHtml(vessel.imo || '缺失')}</b></div><div class="mg-fact"><span>呼号</span><b>${escapeHtml(vessel.call_sign || '缺失')}</b></div><div class="mg-fact"><span>尺寸</span><b>${formatNumber(vessel.ship_length, 0, ' m')} × ${formatNumber(vessel.ship_width, 0, ' m')}</b></div><div class="mg-fact"><span>当前航速</span><b>${formatNumber(point?.sog, 1, ' kt')}</b></div><div class="mg-fact"><span>当前航向</span><b>${formatNumber(point?.cog, 1, '°')}</b></div><div class="mg-fact"><span>位置时间</span><b>${escapeHtml(formatTime(point?.time, true))}</b></div></div></div></section>
      <div class="mg-columns"><section class="mg-card"><div class="mg-card-head"><h2>分类证据</h2><span>事实与推断分离</span></div><div class="mg-evidence-body"><dl><div class="mg-evidence-row"><dt>AIS 静态船型</dt><dd>${escapeHtml(vessel.category)}（代码 ${escapeHtml(vessel.vessel_type || '缺失')}）</dd></div><div class="mg-evidence-row"><dt>映射依据</dt><dd>${escapeHtml(vessel.reason || '未记录')}</dd></div><div class="mg-evidence-row"><dt>模型推断船型</dt><dd>${vessel.dl_predicted_category ? `${escapeHtml(vessel.dl_predicted_category)}，置信度 ${formatNumber(Number(vessel.dl_confidence) * 100, 1, '%')}` : '待训练/待验证'}</dd></div><div class="mg-evidence-row"><dt>人工核验</dt><dd>${escapeHtml(vessel.need_review || '未完成')}</dd></div></dl><div class="mg-callout">当前同步只使用 AIS vessel_type 映射，不能把它当作深度学习模型准确率结果。</div></div></section>
      <section class="mg-card"><div class="mg-card-head"><h2>六小时批次画像</h2><span>不形成违法或信用结论</span></div><div class="mg-evidence-body"><dl><div class="mg-evidence-row"><dt>有效轨迹点</dt><dd>${points.length}</dd></div><div class="mg-evidence-row"><dt>活动时间范围</dt><dd>${formatTime(points[0]?.time)} 至 ${formatTime(points[points.length - 1]?.time)}</dd></div><div class="mg-evidence-row"><dt>平均 / 最大航速</dt><dd>${formatNumber(speeds.length ? speeds.reduce((sum, value) => sum + value, 0) / speeds.length : NaN, 1, ' kt')} / ${formatNumber(speeds.length ? Math.max(...speeds) : NaN, 1, ' kt')}</dd></div><div class="mg-evidence-row"><dt>当前关联事件</dt><dd>${related.length} 条</dd></div></dl></div></section></div>`;
    bindRoutes(wrap);
    const relatedButton = document.getElementById('mgRelatedEvent');
    if (relatedButton) relatedButton.onclick = () => openEvent(related[0].id);
  }

  function renderModels() {
    const quality = ManagementData.dataQuality(DATA.vessels);
    const wrap = document.getElementById('mgModelContent');
    wrap.innerHTML = `
      <div class="mg-section-head"><div><h1>数据质量与模型管理</h1><p>说明系统为什么得出结果、哪些数据尚缺失，以及当前模型能否被信任。</p></div><button class="mg-button" data-route="overview">${icon('map')}返回态势</button></div>
      <div class="mg-quality-grid"><div class="mg-card mg-quality-card"><span>AIS 船舶数</span><b>${quality.vessels}</b><small>六小时增强 AIS 批次中的有效 MMSI</small></div><div class="mg-card mg-quality-card"><span>有效位置记录</span><b>${quality.valid.toLocaleString()}</b><small>位置与时间字段通过基础合法性检查</small></div><div class="mg-card mg-quality-card"><span>船型已映射</span><b>${(quality.classificationCoverage * 100).toFixed(1)}%</b><small>来源为 AIS 静态船型码，不代表模型准确率</small></div><div class="mg-card mg-quality-card"><span>运动字段覆盖</span><b>${(quality.motionCoverage * 100).toFixed(1)}%</b><small>位置、SOG、COG 同时满足计算格式要求</small></div><div class="mg-card mg-quality-card"><span>环境数据</span><b>未接入</b><small>当前不生成环境风险结论</small></div><div class="mg-card mg-quality-card"><span>人工真值集</span><b>未完成</b><small>分类准确率暂不能正式报告</small></div></div>
      <div class="mg-columns"><section class="mg-card"><div class="mg-card-head"><h2>算法与模型版本</h2><span>当前演示</span></div><div class="mg-evidence-body"><dl><div class="mg-evidence-row"><dt>CPA/TCPA</dt><dd>v1.0 · 匀速直线外推 · 已有单元测试</dd></div><div class="mg-evidence-row"><dt>会遇风险值</dt><dd>DCPA 38% + TCPA 28% + 距离 18% + 航向 10% + 新鲜度 6%</dd></div><div class="mg-evidence-row"><dt>行为事件</dt><dd>v0.1 · 阈值初筛 · 尚未用标注集验证</dd></div><div class="mg-evidence-row"><dt>船型深度学习</dt><dd>待训练/待验证，本页面不展示虚假预测</dd></div><div class="mg-evidence-row"><dt>智能体解释层</dt><dd>前端规则化报告原型，尚未接入在线大模型服务</dd></div></dl></div></section><section class="mg-card"><div class="mg-card-head"><h2>已知局限</h2><span>答辩时应主动说明</span></div><div class="mg-evidence-body"><ul><li>六小时数据不足以代表长期季节性和全部船舶行为。</li><li>AIS 静态船型码可能缺失或填报错误。</li><li>低速目标的 COG 容易抖动，CPA/TCPA 可能不可用。</li><li>风险权重是演示评分体系，仍需专家判断和标注事件验证。</li><li>没有环境数据时，不能判断强风浪是否解释异常行为。</li></ul></div></section></div>`;
    bindRoutes(wrap);
  }

  function setEventStatus(event, status) {
    statusOverrides.set(event.id, status);
    operationLog.push({ eventId: event.id, status, time: new Date().toISOString() });
    currentEvent = { ...event, status };
    toast(`事件 ${event.id} 已流转为“${status}”`);
    refreshManagement();
    renderEventDetail();
  }

  function resetStatuses() {
    statusOverrides.clear();
    operationLog.length = 0;
    toast('演示状态已重置');
    refreshManagement();
  }

  function toast(message) {
    const node = document.getElementById('mgToast');
    node.textContent = message;
    node.classList.add('show');
    window.setTimeout(() => node.classList.remove('show'), 2200);
  }

  function openEvent(id) {
    currentEvent = currentEvents().find(event => event.id === id) || currentEvent;
    route('event-detail');
  }

  function pageMeta(view) {
    return {
      overview: ['综合态势', '马六甲海峡六小时增强 AIS 历史回放'],
      events: ['异常事件中心', '事件发现、核查与处置状态闭环'],
      'event-detail': ['事件研判', '运动学证据、数据质量与不确定性'],
      vessels: ['船舶档案', '身份、船型来源与行为画像'],
      environment: ['环境监测', '多源环境数据接入状态'],
      models: ['数据与模型', '数据质量、算法版本与适用边界']
    }[view] || ['管理端', '海上异常监测智能体'];
  }

  function route(view) {
    currentView = view;
    const isOverview = view === 'overview';
    overviewPage.classList.toggle('hidden', !isOverview);
    detailPage.classList.add('hidden');
    document.querySelectorAll('.mg-page').forEach(page => page.classList.toggle('active', page.dataset.page === view));
    document.querySelectorAll('.mg-nav-button').forEach(button => button.classList.toggle('active', button.dataset.mgView === view));
    const [title, subtitle] = pageMeta(view);
    document.getElementById('mgPageTitle').textContent = title;
    document.getElementById('mgPageSubtitle').textContent = subtitle;
    if (view === 'events') renderEventTable();
    if (view === 'event-detail') renderEventDetail();
    if (view === 'vessels') renderVesselDetail();
    if (view === 'models') renderModels();
    if (isOverview) window.setTimeout(() => map.invalidateSize(), 50);
    try { history.replaceState(null, '', `#${view}`); } catch (_) { /* Local-file history may be restricted. */ }
    if (window.lucide) window.lucide.createIcons();
  }

  function bindRoutes(root = document) {
    root.querySelectorAll('[data-route]').forEach(button => button.onclick = () => route(button.dataset.route));
    if (window.lucide) window.lucide.createIcons();
  }

  function refreshManagement() {
    refreshData();
    refreshKpis();
    renderRail();
    if (currentView === 'overview') renderManagementMap(false);
    if (currentView === 'events') renderEventTable();
    if (currentView === 'event-detail') renderEventDetail();
    if (currentView === 'vessels') renderVesselDetail();
    if (currentView === 'models') renderModels();
    if (window.lucide) window.lucide.createIcons();
  }

  function queueManagementRefresh() {
    if (refreshQueued) return;
    refreshQueued = true;
    window.requestAnimationFrame(() => {
      refreshQueued = false;
      refreshManagement();
    });
  }

  createShell();
  vesselIcon = managementVesselIcon;
  renderMap = renderManagementMap;
  renderAll = function (...args) {
    currentTime();
    renderTimeline(true);
    queueManagementRefresh();
  };
  openVesselDetail = function (mmsi) {
    const snapshot = activeVessels().find(vessel => String(vessel.mmsi) === String(mmsi));
    selected = snapshot || DATA.vessels.find(vessel => String(vessel.mmsi) === String(mmsi)) || selected;
    route('vessels');
  };
  showOverviewPage = function () { route('overview'); };
  document.getElementById('backBtn').onclick = () => route('overview');
  const encounterBack = document.getElementById('encBack');
  const encounterExit = document.getElementById('encExit');
  if (encounterBack) encounterBack.onclick = () => route('overview');
  if (encounterExit) encounterExit.addEventListener('click', () => route('event-detail'));
  document.querySelectorAll('.mg-nav-button').forEach(button => button.onclick = () => route(button.dataset.mgView));
  document.getElementById('mgAllEvents').onclick = () => route('events');
  document.getElementById('mgEventSearch').oninput = renderEventTable;
  document.getElementById('mgRiskFilter').onchange = renderEventTable;
  document.getElementById('mgStatusFilter').onchange = renderEventTable;
  document.getElementById('mgResetStatus').onclick = resetStatuses;
  bindRoutes();

  if (currentStep === 0 && timeSteps.length > 4) {
    currentStep = Math.floor((timeSteps.length - 1) * 0.58);
    refreshData();
    originalRenderAll(true);
  }
  refreshManagement();
  const requested = location.hash.replace('#', '');
  route(['overview', 'events', 'event-detail', 'vessels', 'environment', 'models'].includes(requested) ? requested : 'overview');
})();
