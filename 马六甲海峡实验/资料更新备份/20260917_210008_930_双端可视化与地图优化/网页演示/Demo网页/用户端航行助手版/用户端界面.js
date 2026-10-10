(function () {
  'use strict';

  if (!window.ClientData || !window.ManagementData || !window.EncounterMath || typeof DATA === 'undefined') return;

  const app = document.querySelector('.app');
  const overviewPage = document.getElementById('overviewPage');
  const detailPage = document.getElementById('detailPage');
  const originalRenderAll = renderAll;
  const readMessages = new Set();
  let view = 'home';
  let ownMmsi = '';
  let selectedEvent = null;
  const clientMarkerCache = new Map();
  let clientVisibleMmsis = new Set();
  let bundle = { snapshots: [], events: [] };
  let routeResult = null;
  let question = 'nearby';

  function esc(value) {
    return String(value ?? '').replace(/[&<>'"]/g, char => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
    })[char]);
  }

  function icon(name) { return `<i data-lucide="${name}" aria-hidden="true"></i>`; }
  function num(value, digits = 1, suffix = '') {
    return Number.isFinite(Number(value)) ? `${Number(value).toFixed(digits)}${suffix}` : '不可用';
  }
  function timeText(value, seconds = false) {
    const date = new Date(value);
    if (!Number.isFinite(date.getTime())) return '暂无';
    return new Intl.DateTimeFormat('zh-CN', {
      month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
      second: seconds ? '2-digit' : undefined, hour12: false
    }).format(date);
  }

  function createShell() {
    document.body.classList.add('client-mode');
    document.body.insertAdjacentHTML('afterbegin', `
      <aside class="cu-sidebar" aria-label="用户端主导航">
        <div class="cu-brand"><div class="cu-brand-mark">${icon('navigation')}</div><div class="cu-brand-copy"><strong>海上异常监测智能体</strong><span>马六甲海峡 · 用户端</span></div></div>
        <nav class="cu-nav">
          <div class="cu-nav-label">航行风险助手</div>
          <button class="cu-nav-button active" data-cu-view="home" title="航行首页">${icon('map')}<span>航行首页</span></button>
          <button class="cu-nav-button" data-cu-view="encounters" title="附近会遇">${icon('scan-line')}<span>附近会遇</span></button>
          <button class="cu-nav-button" data-cu-view="route" title="航线预评估">${icon('route')}<span>航线预评估</span></button>
          <button class="cu-nav-button" data-cu-view="environment" title="环境风险">${icon('cloud-sun')}<span>环境风险</span></button>
          <button class="cu-nav-button" data-cu-view="assistant" title="智能问答与消息">${icon('message-square-text')}<span>智能问答与消息</span></button>
        </nav>
        <div class="cu-sidebar-foot"><strong>风险辅助提示</strong>不替代 COLREGs、驾驶台瞭望或法定避碰判断</div>
      </aside>
      <header class="cu-topbar">
        <div class="cu-page-heading"><strong id="cuPageTitle">航行首页</strong><span id="cuPageSubtitle">关注船与附近关键风险</span></div>
        <div class="cu-kpi"><b id="cuOwnSpeed">--</b><span>关注船航速</span></div>
        <div class="cu-kpi danger"><b id="cuRiskCount">0</b><span>附近关注目标</span></div>
        <div class="cu-kpi"><b id="cuFreshness">--</b><span>AIS 数据新鲜度</span></div>
        <div class="cu-system-state"><i></i><span id="cuDataState">六小时历史 AIS 已载入</span></div>
      </header>
      <div id="cuToast" class="cu-toast" role="status"></div>`);

    overviewPage.insertAdjacentHTML('beforeend', `
      <section class="cu-self-card" aria-label="关注船状态">
        <div class="cu-self-label">我的关注船</div>
        <select id="cuOwnSelect" class="cu-self-select" aria-label="选择关注船"></select>
        <div id="cuSelfSummary"></div>
      </section>
      <aside class="cu-nearby-rail" aria-label="附近重点会遇">
        <div class="cu-rail-head"><div><h2>附近重点会遇</h2><span>仅显示与关注船有关的 Top 5</span></div><span id="cuRailTime">--</span></div>
        <div class="cu-rail-note">风险分数用于排序。点击目标查看 DCPA、TCPA、数据时间和不确定性。</div>
        <div id="cuTopEvents" class="cu-event-list"></div>
        <div class="cu-rail-footer"><button id="cuAllEncounters" class="cu-button primary">${icon('arrow-right')}查看附近会遇</button></div>
      </aside>`);

    app.insertAdjacentHTML('beforeend', pagesMarkup());
    detailPage.classList.add('hidden');
    bindNavigation();
  }

  function pagesMarkup() {
    return `
      <section id="cuEncountersPage" class="cu-page" data-cu-page="encounters"><div class="cu-page-inner">
        <div class="cu-section-head"><div><h1>附近船舶与会遇风险</h1><p>围绕关注船筛选 Top 5，不把全域事件堆给用户。</p></div><button class="cu-button" data-route="home">${icon('map')}返回航行首页</button></div>
        <div class="cu-grid-2"><section class="cu-card"><div class="cu-card-head"><h2>风险排序</h2><span id="cuEncounterCount">0 个目标</span></div><div id="cuEncounterList"></div></section><aside id="cuEncounterDetail" class="cu-stack"></aside></div>
      </div></section>
      <section id="cuRoutePage" class="cu-page" data-cu-page="route"><div class="cu-page-inner">
        <div class="cu-section-head"><div><h1>航线风险预评估</h1><p>以关注船当前位置到目的地的直线走廊筛查当前风险，不生成自动航线。</p></div><button class="cu-button" data-route="home">${icon('map')}返回航行首页</button></div>
        <div class="cu-grid-2"><main class="cu-stack"><section class="cu-card"><div class="cu-card-head"><h2>评估条件</h2><span>当前位置自动读取 AIS</span></div><form id="cuRouteForm" class="cu-form">
          <div class="cu-field"><label for="cuDestLat">目的地纬度</label><input id="cuDestLat" type="number" step="0.0001" value="1.1700" required></div>
          <div class="cu-field"><label for="cuDestLon">目的地经度</label><input id="cuDestLon" type="number" step="0.0001" value="104.0500" required></div>
          <div class="cu-field"><label for="cuRouteSpeed">预计航速（节）</label><input id="cuRouteSpeed" type="number" min="1" max="35" step="0.5" value="10"></div>
          <div class="cu-field"><label for="cuCorridor">筛查走廊半宽（海里）</label><select id="cuCorridor"><option value="2">2 海里</option><option value="3" selected>3 海里</option><option value="5">5 海里</option></select></div>
          <div class="cu-actions"><button class="cu-button teal" type="submit">${icon('search')}开始预评估</button></div>
        </form></section><section class="cu-card"><div class="cu-card-head"><h2>直线走廊示意</h2><span>非电子海图航线</span></div><div id="cuRouteViz" class="cu-route-viz"></div></section></main><aside id="cuRouteResult" class="cu-card cu-route-result"></aside></div>
      </div></section>
      <section id="cuEnvironmentPage" class="cu-page" data-cu-page="environment"><div class="cu-page-inner">
        <div class="cu-section-head"><div><h1>环境风险</h1><p>只展示有可靠来源、观测时间和可信信息的数据。</p></div><button class="cu-button" data-route="home">${icon('map')}返回航行首页</button></div>
        <section class="cu-card cu-empty-state"><div class="cu-empty-copy"><div class="cu-empty-icon">${icon('cloud-off')}</div><h1>当前环境数据暂未覆盖</h1><p>系统目前只有六小时历史 AIS 数据，因此不能回答实时台风、风浪、海流、赤潮或油膜问题。</p><div class="cu-callout">环境数据未接入不等于环境安全。航行人员仍需使用正式气象、海况和航行通告。</div></div><div class="cu-source-list">
          <div class="cu-source-item"><b>台风路径与影响范围</b><span>需要预报时次、中心位置、强度和影响半径</span></div><div class="cu-source-item"><b>风、浪、海流</b><span>需要有效时间、网格分辨率和更新时间</span></div><div class="cu-source-item"><b>叶绿素异常与赤潮疑似</b><span>不能把叶绿素异常直接表述为赤潮</span></div><div class="cu-source-item"><b>油膜疑似区</b><span>需要遥感证据、置信度和误报因素</span></div>
        </div></section>
      </div></section>
      <section id="cuAssistantPage" class="cu-page" data-cu-page="assistant"><div class="cu-page-inner">
        <div class="cu-section-head"><div><h1>智能问答与消息中心</h1><p>当前使用本地证据模板生成可追溯回答，在线大模型尚未接入。</p></div><button class="cu-button" data-route="home">${icon('map')}返回航行首页</button></div>
        <div class="cu-grid-2"><main class="cu-stack"><section class="cu-card"><div class="cu-card-head"><h2>选择一个问题</h2><span>每个回答包含六项证据字段</span></div><div class="cu-question-grid"><button class="cu-question" data-question="nearby">我当前附近有什么风险？</button><button class="cu-question" data-question="why">为什么首要目标需要关注？</button><button class="cu-question" data-question="quality">这些 AIS 结果可靠吗？</button></div></section><section id="cuAnswer" class="cu-card cu-answer"></section></main><aside class="cu-card"><div class="cu-card-head"><h2>风险消息</h2><span id="cuUnreadCount">0 条未读</span></div><div id="cuMessages"></div></aside></div>
      </div></section>`;
  }

  function refreshData() {
    bundle = ManagementData.buildEvents(DATA.vessels, currentTime(), EncounterMath);
    ensureOwn();
  }

  function ensureOwn() {
    const fresh = bundle.snapshots.filter(item => item.ageMinutes <= 5);
    if (fresh.some(item => String(item.vessel.mmsi) === String(ownMmsi))) return;
    ownMmsi = String(bundle.events[0]?.vessels[0]?.mmsi || fresh[0]?.vessel.mmsi || DATA.vessels[0]?.mmsi || '');
  }

  function ownRow() {
    return bundle.snapshots.find(item => String(item.vessel.mmsi) === String(ownMmsi)) || null;
  }

  function ownEvents() { return ClientData.relatedEvents(bundle.events, ownMmsi, 5); }
  function other(event) { return ClientData.otherVessel(event, ownMmsi); }

  function fillOwnSelect() {
    const select = document.getElementById('cuOwnSelect');
    const fresh = bundle.snapshots.filter(item => item.ageMinutes <= 5)
      .sort((a, b) => (b.vessel.point_count || b.vessel.points.length) - (a.vessel.point_count || a.vessel.points.length));
    const current = fresh.find(item => String(item.vessel.mmsi) === String(ownMmsi));
    const options = current ? [current, ...fresh.filter(item => item !== current)] : fresh;
    select.innerHTML = options.slice(0, 120).map(item => `<option value="${esc(item.vessel.mmsi)}" ${String(item.vessel.mmsi) === String(ownMmsi) ? 'selected' : ''}>${esc(item.vessel.name || '未命名')} · ${esc(item.vessel.mmsi)}</option>`).join('');
    select.onchange = () => {
      ownMmsi = select.value;
      selectedEvent = null;
      routeResult = null;
      renderCurrent(true);
      toast('关注船已切换，附近风险与问答已同步更新');
    };
  }

  function refreshHeader() {
    const row = ownRow();
    const events = ownEvents();
    document.getElementById('cuOwnSpeed').textContent = row ? num(row.point.sog, 1, ' kt') : '--';
    document.getElementById('cuRiskCount').textContent = events.length;
    document.getElementById('cuFreshness').textContent = row ? `${num(row.ageMinutes, 1)} min` : '--';
    document.getElementById('cuDataState').textContent = `${isPlaying ? '历史回放中' : '历史回放已暂停'} · ${timeText(currentTime(), true)}`;
  }

  function selfSummary() {
    const row = ownRow();
    const events = ownEvents();
    const band = ClientData.attentionBand(events);
    if (!row) return '<div class="cu-callout">当前时间片没有关注船的有效位置，请切换回放时间或关注船。</div>';
    const tips = events.length ? [
      `首要目标 ${esc(other(events[0])?.name || '未命名')}，DCPA ${num(events[0].cpa?.dcpa, 2, ' nm')}。`,
      `预计最近会遇时间 ${num(events[0].cpa?.tcpa, 1, ' min')}，请持续观察航向变化。`,
      '环境数据尚未覆盖，当前结论只基于 AIS 与 CPA/TCPA。'
    ] : ['当前未筛选出中等关注及以上会遇事件。', '这不等于绝对安全，仍需保持驾驶台瞭望。', '环境数据尚未覆盖，不能形成综合环境结论。'];
    return `<div class="cu-self-summary"><div><div class="cu-self-name">${esc(row.vessel.name || '未命名')}</div><div class="cu-self-meta">${esc(row.vessel.category)} · MMSI ${esc(row.vessel.mmsi)}<br>${num(row.point.sog, 1, ' kt')} · 航向 ${num(row.point.cog, 1, '°')} · ${timeText(row.point.time, true)}</div></div><div class="cu-attention ${band.tone}"><b>${band.score || '—'}</b><span>${esc(band.level)}</span></div></div><div class="cu-tips">${tips.map(tip => `<div class="cu-tip">${icon('chevron-right')}<span>${tip}</span></div>`).join('')}</div>`;
  }

  function markerIcon(vessel, event, isOwn) {
    const color = COLORS[vessel.category] || COLORS['未知'];
    const classes = isOwn ? 'client-own-marker' : `client-target-marker ${event ? '' : 'client-muted-marker'} ${event?.tone === 'critical' ? 'critical' : ''}`;
    const html = `<div class="risk-marker ${classes}" title="${esc(vessel.name || vessel.mmsi)}"><span class="risk-halo"></span><span class="ship-wrap">${shipSvg(vessel.category, color, headingOf(vessel), isOwn)}</span></div>`;
    return L.divIcon({ className: 'ship-marker', html, iconSize: [88, 46], iconAnchor: [44, 23] });
  }

  function renderHomeMap(fit = false) {
    clearLayers();
    const own = ownRow();
    if (!own) return;
    const events = ownEvents();
    const eventByTarget = new Map(events.map(event => [String(other(event)?.mmsi), event]));
    const nearby = bundle.snapshots.filter(item => {
      if (item.ageMinutes > 5) return false;
      if (String(item.vessel.mmsi) === String(ownMmsi)) return true;
      const distance = EncounterMath.distance(own.point, item.point);
      return Number.isFinite(distance) && distance <= 12;
    });
    const bounds = [];
    const nextVisible = new Set();
    nearby.forEach(item => {
      const isOwn = String(item.vessel.mmsi) === String(ownMmsi);
      const event = eventByTarget.get(String(item.vessel.mmsi));
      const vessel = { ...item.vessel, points: [item.point] };
      const key = String(vessel.mmsi);
      const replayState = preparedVessels.has(key) ? HistoricalAisReplay.stateAt(preparedVessels.get(key), currentTime()) : null;
      const position = replayState ? [replayState.displayPosition.lat, replayState.displayPosition.lon] : [item.point.lat, item.point.lon];
      let marker = clientMarkerCache.get(key);
      if (!marker) {
        marker = L.marker(position, { icon: markerIcon(vessel, event, isOwn), riseOnHover: true });
        marker.on('click', () => {
          const currentEvent = ownEvents().find(candidate => String(other(candidate)?.mmsi) === key);
          if (currentEvent) openEncounter(currentEvent.id);
          else toast(isOwn ? '这是当前关注船' : '该目标当前没有中等关注及以上会遇事件');
        });
        clientMarkerCache.set(key, marker);
      } else {
        marker.setLatLng(position).setIcon(markerIcon(vessel, event, isOwn));
      }
      marker.addTo(map);
      marker.bindTooltip(`${esc(vessel.name || '未命名')} · ${isOwn ? '我的关注船' : esc(vessel.category)}`, { direction: 'top', offset: [0, -12] });
      if (replayState) updateMarkerReplayClass(marker, replayState);
      layers.push(marker);
      nextVisible.add(key);
      bounds.push(position);
    });
    clientVisibleMmsis = nextVisible;
    if (fit && bounds.length) map.fitBounds(bounds, { padding: [55, 55], maxZoom: 13 });
  }

  replayFrameHooks.push(timeMs => {
    if (view !== 'home') return;
    clientVisibleMmsis.forEach(key => {
      const marker = clientMarkerCache.get(key);
      const prepared = preparedVessels.get(key);
      if (!marker || !prepared || !map.hasLayer(marker)) return;
      const replayState = HistoricalAisReplay.stateAt(prepared, timeMs);
      if (!replayState) return;
      marker.setLatLng([replayState.displayPosition.lat, replayState.displayPosition.lon]);
      updateMarkerReplayClass(marker, replayState);
    });
  });

  function eventItem(event, index) {
    const target = other(event);
    return `<button class="cu-event-item ${event.tone}" data-event-id="${esc(event.id)}"><span class="cu-event-rank">${index + 1}</span><span class="cu-event-copy"><b>${esc(target?.name || target?.mmsi || '目标船')}</b><span>${esc(target?.category || '船型未知')} · ${esc(event.encounterShape || event.kind)}<br>DCPA ${num(event.cpa?.dcpa, 2, ' nm')} · TCPA ${num(event.cpa?.tcpa, 1, ' min')}</span></span><strong class="cu-event-score">${event.score}</strong></button>`;
  }

  function bindEventButtons(root) {
    root.querySelectorAll('[data-event-id]').forEach(button => button.onclick = () => openEncounter(button.dataset.eventId));
  }

  function renderHome(fit = false) {
    fillOwnSelect();
    document.getElementById('cuSelfSummary').innerHTML = selfSummary();
    const events = ownEvents();
    document.getElementById('cuRailTime').textContent = timeText(currentTime());
    const wrap = document.getElementById('cuTopEvents');
    wrap.innerHTML = events.length ? events.map(eventItem).join('') : '<div class="cu-callout">当前时间片没有与关注船有关的中等关注及以上会遇事件。</div>';
    bindEventButtons(wrap);
    renderHomeMap(fit);
    setTimeout(() => map.invalidateSize(), 0);
  }

  function renderEncounters() {
    const events = ownEvents();
    document.getElementById('cuEncounterCount').textContent = `${events.length} 个目标`;
    const list = document.getElementById('cuEncounterList');
    list.innerHTML = events.length ? events.map((event, index) => {
      const target = other(event);
      return `<article class="cu-target" data-event-id="${esc(event.id)}"><div><h3>${index + 1}. ${esc(target?.name || target?.mmsi || '目标船')}</h3><div class="cu-target-meta"><span>${esc(target?.category || '船型未知')}</span><span>MMSI ${esc(target?.mmsi || '未知')}</span><span>${esc(event.encounterShape || event.kind)}</span><span>AIS 可信提示：${esc(event.confidence)}</span></div><div class="cu-target-metrics"><div><b>${num(event.distance, 2, ' nm')}</b><span>当前距离</span></div><div><b>${num(event.cpa?.dcpa, 2, ' nm')}</b><span>DCPA</span></div><div><b>${num(event.cpa?.tcpa, 1, ' min')}</b><span>TCPA</span></div></div></div><div class="cu-score ${event.tone}">${event.score}<small>${esc(event.level)}</small></div></article>`;
    }).join('') : '<div class="cu-card-body">当前时间片暂无重点会遇目标。继续回放后可观察其他时刻。</div>';
    bindEventButtons(list);
    selectedEvent = events.find(event => event.id === selectedEvent?.id) || events[0] || null;
    renderEncounterDetail();
  }

  function renderEncounterDetail() {
    const wrap = document.getElementById('cuEncounterDetail');
    const event = selectedEvent;
    if (!event) { wrap.innerHTML = '<section class="cu-card cu-card-body">选择一个目标查看依据。</section>'; return; }
    const target = other(event);
    wrap.innerHTML = `<section class="cu-card cu-detail-hero ${event.tone}"><span class="cu-self-label">${esc(event.kind)} · ${esc(event.source)}</span><h2>${esc(target?.name || target?.mmsi || '目标船')}</h2><p>${esc(event.explanation)} 当前结果只用于提前观察。</p></section><section class="cu-card"><div class="cu-card-head"><h2>关键依据</h2><span>${esc(event.encounterShape || '形态待判断')}</span></div><div class="cu-metric-grid"><div class="cu-metric"><span>DCPA</span><b>${num(event.cpa?.dcpa, 2, ' nm')}</b></div><div class="cu-metric"><span>TCPA</span><b>${num(event.cpa?.tcpa, 1, ' min')}</b></div><div class="cu-metric"><span>风险值</span><b>${event.score}</b></div></div></section><section class="cu-card"><div class="cu-card-head"><h2>可信度与下一步</h2><span>AIS ${timeText(event.updatedAt, true)}</span></div><div class="cu-card-body"><dl class="cu-facts"><div class="cu-fact"><dt>可信提示</dt><dd>${esc(event.confidence)}</dd></div><div class="cu-fact"><dt>数据来源</dt><dd>${esc(event.source)}</dd></div><div class="cu-fact"><dt>建议动作</dt><dd>持续观察双方航向和航速，由航行人员结合 COLREGs 与现场态势判断。</dd></div></dl><div class="cu-callout">CPA/TCPA 基于匀速直线外推。目标变速、转向或 AIS 延迟会改变结果，不能替代人工避碰判断。</div></div></section>`;
  }

  function openEncounter(id) {
    selectedEvent = ownEvents().find(event => event.id === id) || bundle.events.find(event => event.id === id) || null;
    route('encounters');
  }

  function renderRoute() {
    const row = ownRow();
    if (!routeResult) document.getElementById('cuRouteResult').innerHTML = '<h2>等待输入</h2><p>填写目的地后，系统将检查当前事件是否靠近直线走廊。</p><div class="cu-callout">本功能不是航线规划器，也不输出转向、改速或避碰指令。</div>';
    renderRouteViz(routeResult);
    document.getElementById('cuRouteForm').onsubmit = event => {
      event.preventDefault();
      if (!row) { toast('当前关注船没有有效位置'); return; }
      const end = { lat: Number(document.getElementById('cuDestLat').value), lon: Number(document.getElementById('cuDestLon').value) };
      const corridor = Number(document.getElementById('cuCorridor').value);
      routeResult = ClientData.routeAssessment(row.point, end, bundle.events, corridor);
      routeResult.end = end;
      routeResult.speed = Number(document.getElementById('cuRouteSpeed').value);
      renderRouteResult();
      renderRouteViz(routeResult);
    };
  }

  function renderRouteViz(result) {
    const wrap = document.getElementById('cuRouteViz');
    const markers = (result?.events || []).slice(0, 5).map((item, index) => `<i class="cu-route-event ${item.event.tone}" style="left:${32 + index * 10}%;top:${40 + (index % 2) * 12}%" title="${esc(item.event.id)}"></i>`).join('');
    wrap.innerHTML = `<i class="cu-route-node start" title="关注船当前位置"></i><i class="cu-route-node end" title="输入目的地"></i>${markers}<div class="cu-route-caption">示意图仅表达筛查走廊及附近事件，不按真实比例绘制。</div>`;
  }

  function renderRouteResult() {
    const wrap = document.getElementById('cuRouteResult');
    if (!routeResult?.available) { wrap.innerHTML = `<h2>无法评估</h2><p>${esc(routeResult?.reason || '输入无效')}</p>`; return; }
    wrap.innerHTML = `<span class="cu-self-label">当前时间片评估</span><h2>${esc(routeResult.level)}</h2><p>走廊半宽 ${routeResult.corridorNm} 海里，发现 ${routeResult.events.length} 个靠近走廊的当前风险事件，最高风险值 ${routeResult.highest || '—'}。</p><dl class="cu-facts">${routeResult.events.slice(0, 5).map(item => `<div class="cu-fact"><dt>${esc(item.event.id)}</dt><dd>风险 ${item.event.score} · 距走廊 ${num(item.corridorDistance, 2, ' nm')}</dd></div>`).join('')}</dl><div class="cu-callout">直线走廊没有检查水深、陆地、交通分离制、禁限区、操纵性能或环境影响，只能作为进一步评估的风险提示。</div>`;
  }

  function renderAssistant() {
    const quality = ManagementData.dataQuality(DATA.vessels);
    const answer = ClientData.answerCard(question, { events: bundle.events, ownMmsi, time: new Date(currentTime()).toISOString(), quality });
    document.getElementById('cuAnswer').innerHTML = `<span class="cu-self-label">本地证据回答 · 非在线大模型</span><h2>${esc(answer.conclusion)}</h2><div class="cu-answer-grid"><dl class="cu-facts"><div class="cu-fact"><dt>数据时间</dt><dd>${esc(timeText(answer.time, true))}</dd></div><div class="cu-fact"><dt>证据</dt><dd>${esc(answer.evidence)}</dd></div><div class="cu-fact"><dt>可信提示</dt><dd>${esc(answer.confidence)}</dd></div><div class="cu-fact"><dt>不确定因素</dt><dd>${esc(answer.uncertainty)}</dd></div><div class="cu-fact"><dt>下一步动作</dt><dd>${esc(answer.action)}</dd></div></dl></div>`;
    document.querySelectorAll('[data-question]').forEach(button => button.onclick = () => { question = button.dataset.question; renderAssistant(); });
    renderMessages();
  }

  function renderMessages() {
    const events = ownEvents();
    const unread = events.filter(event => !readMessages.has(event.id)).length;
    document.getElementById('cuUnreadCount').textContent = `${unread} 条未读`;
    const wrap = document.getElementById('cuMessages');
    wrap.innerHTML = events.length ? events.map(event => `<article class="cu-message ${readMessages.has(event.id) ? 'read' : ''}" data-message-id="${esc(event.id)}"><i class="cu-message-dot"></i><div><b>${esc(other(event)?.name || event.id)} · ${esc(event.level)}</b><span>DCPA ${num(event.cpa?.dcpa, 2, ' nm')} · TCPA ${num(event.cpa?.tcpa, 1, ' min')} · ${timeText(event.updatedAt)}</span></div><strong>${event.score}</strong></article>`).join('') : '<div class="cu-card-body">当前没有风险消息。</div>';
    wrap.querySelectorAll('[data-message-id]').forEach(item => item.onclick = () => {
      readMessages.add(item.dataset.messageId);
      openEncounter(item.dataset.messageId);
    });
  }

  function renderCurrent(fit = false) {
    refreshData();
    refreshHeader();
    if (view === 'home') renderHome(fit);
    if (view === 'encounters') renderEncounters();
    if (view === 'route') renderRoute();
    if (view === 'assistant') renderAssistant();
    if (window.lucide) lucide.createIcons();
  }

  const titles = {
    home: ['航行首页', '关注船与附近关键风险'],
    encounters: ['附近会遇', 'Top 5 目标与 CPA/TCPA 依据'],
    route: ['航线预评估', '直线走廊风险筛查，不生成自动航线'],
    environment: ['环境风险', '数据覆盖状态与来源边界'],
    assistant: ['智能问答与消息', '证据化回答与非打扰式消息中心']
  };

  function route(next) {
    view = next;
    overviewPage.classList.toggle('hidden', next !== 'home');
    document.querySelectorAll('.cu-page').forEach(page => page.classList.toggle('active', page.dataset.cuPage === next));
    document.querySelectorAll('.cu-nav-button').forEach(button => button.classList.toggle('active', button.dataset.cuView === next));
    document.getElementById('cuPageTitle').textContent = titles[next][0];
    document.getElementById('cuPageSubtitle').textContent = titles[next][1];
    history.replaceState(null, '', `#${next}`);
    renderCurrent(next === 'home');
  }

  function bindNavigation() {
    document.querySelectorAll('[data-cu-view]').forEach(button => button.onclick = () => route(button.dataset.cuView));
    document.querySelectorAll('[data-route]').forEach(button => button.onclick = () => route(button.dataset.route));
    document.getElementById('cuAllEncounters').onclick = () => route('encounters');
  }

  function toast(message) {
    const node = document.getElementById('cuToast');
    node.textContent = message;
    node.classList.add('show');
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => node.classList.remove('show'), 2200);
  }

  createShell();
  if (currentStep === 0 && timeSteps.length > 1) currentStep = Math.floor(timeSteps.length * 0.58);
  renderTimeline();
  refreshData();
  ensureOwn();
  window.openVesselDetail = mmsi => {
    const event = ownEvents().find(item => item.vessels.some(vessel => String(vessel.mmsi) === String(mmsi)));
    if (event) openEncounter(event.id);
    else toast('该船当前没有与关注船相关的重点会遇事件');
  };
  window.showOverviewPage = () => route('home');
  window.renderAll = fit => {
    currentTime();
    renderTimeline(true);
    renderCurrent(Boolean(fit));
  };
  route(['home', 'encounters', 'route', 'environment', 'assistant'].includes(location.hash.slice(1)) ? location.hash.slice(1) : 'home');
})();
