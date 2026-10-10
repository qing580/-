(function (root) {
  'use strict';

  const WIDTH = 720;
  const HEIGHT = 300;
  const PAD = 34;
  const DEFAULT_GAP_MS = 2 * 60 * 1000;
  const DEFAULT_WINDOW_MS = 10 * 60 * 1000;

  function esc(value) {
    return String(value ?? '').replace(/[&<>'"]/g, char => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
    })[char]);
  }

  function number(value) {
    if (value === null || value === undefined || String(value).trim() === '') return NaN;
    return Number(value);
  }

  function validPoint(point) {
    const timeMs = Date.parse(point?.time);
    const lat = number(point?.lat);
    const lon = number(point?.lon);
    return Number.isFinite(timeMs) && Number.isFinite(lat) && Number.isFinite(lon) &&
      Math.abs(lat) <= 90 && Math.abs(lon) <= 180;
  }

  function normalizedPoint(point) {
    return { source: point, timeMs: Date.parse(point.time), lat: Number(point.lat), lon: Number(point.lon) };
  }

  function trackSegments(points, options = {}) {
    const cutoffMs = Number.isFinite(options.cutoffMs) ? options.cutoffMs : Infinity;
    const windowMs = Number.isFinite(options.windowMs) ? options.windowMs : DEFAULT_WINDOW_MS;
    const gapMs = Number.isFinite(options.maxGapMs) ? options.maxGapMs : DEFAULT_GAP_MS;
    const startMs = cutoffMs === Infinity ? -Infinity : cutoffMs - windowMs;
    const rows = (points || []).filter(validPoint).map(normalizedPoint)
      .filter(point => point.timeMs >= startMs && point.timeMs <= cutoffMs)
      .sort((first, second) => first.timeMs - second.timeMs);
    const segments = [];
    let segment = [];
    rows.forEach(point => {
      const previous = segment[segment.length - 1];
      if (previous && point.timeMs - previous.timeMs > gapMs) {
        if (segment.length) segments.push(segment);
        segment = [];
      }
      segment.push(point);
    });
    if (segment.length) segments.push(segment);
    return segments;
  }

  function empty(message = '暂无可绘制的真实数据') {
    return `<div class="ais-viz-empty"><b>暂无图形</b><span>${esc(message)}</span></div>`;
  }

  function extent(values) {
    const finite = values.filter(Number.isFinite);
    if (!finite.length) return null;
    let min = Math.min(...finite);
    let max = Math.max(...finite);
    if (min === max) {
      const delta = Math.abs(min) > 1 ? Math.abs(min) * .02 : .02;
      min -= delta;
      max += delta;
    }
    return [min, max];
  }

  function scale(value, domain, range) {
    return range[0] + (value - domain[0]) * (range[1] - range[0]) / (domain[1] - domain[0]);
  }

  function geoProjector(points) {
    const latExtent = extent(points.map(point => point.lat));
    const lonExtent = extent(points.map(point => point.lon));
    if (!latExtent || !lonExtent) return null;
    const latPad = Math.max((latExtent[1] - latExtent[0]) * .12, .0005);
    const lonPad = Math.max((lonExtent[1] - lonExtent[0]) * .12, .0005);
    const latDomain = [latExtent[0] - latPad, latExtent[1] + latPad];
    const lonDomain = [lonExtent[0] - lonPad, lonExtent[1] + lonPad];
    return point => ({
      x: scale(point.lon, lonDomain, [PAD, WIDTH - PAD]),
      y: scale(point.lat, latDomain, [HEIGHT - PAD, PAD])
    });
  }

  function grid() {
    return [1, 2, 3, 4].map(index => {
      const x = PAD + index * (WIDTH - PAD * 2) / 5;
      const y = PAD + index * (HEIGHT - PAD * 2) / 5;
      return `<path d="M${x} ${PAD}V${HEIGHT - PAD}M${PAD} ${y}H${WIDTH - PAD}"/>`;
    }).join('');
  }

  function trackPlot(points, options = {}) {
    const segments = trackSegments(points, options);
    const all = segments.flat();
    if (!all.length) return empty(options.emptyMessage);
    const project = geoProjector(all);
    const paths = segments.filter(segment => segment.length > 1).map(segment => {
      const d = segment.map((point, index) => {
        const pos = project(point);
        return `${index ? 'L' : 'M'}${pos.x.toFixed(1)} ${pos.y.toFixed(1)}`;
      }).join(' ');
      return `<path class="ais-viz-track" d="${d}"/>`;
    }).join('');
    const latest = project(all[all.length - 1]);
    const first = project(all[0]);
    return `<div class="ais-viz-chart"><div class="ais-viz-title"><b>${esc(options.title || '近期真实轨迹')}</b><span>实线为真实 AIS，断口表示采样间隔超过 2 分钟</span></div><svg viewBox="0 0 ${WIDTH} ${HEIGHT}" role="img" aria-label="${esc(options.title || '真实AIS轨迹')}"><g class="ais-viz-grid">${grid()}</g>${paths}<circle class="ais-viz-point muted" cx="${first.x.toFixed(1)}" cy="${first.y.toFixed(1)}" r="4"/><circle class="ais-viz-point current" cx="${latest.x.toFixed(1)}" cy="${latest.y.toFixed(1)}" r="6"/></svg></div>`;
  }

  function lineSegments(points) {
    const segments = [];
    let segment = [];
    (points || []).forEach(point => {
      const timeMs = Date.parse(point?.time);
      const value = number(point?.value);
      if (!Number.isFinite(timeMs) || !Number.isFinite(value)) {
        if (segment.length) segments.push(segment);
        segment = [];
        return;
      }
      const previous = segment[segment.length - 1];
      if (previous && timeMs - previous.timeMs > DEFAULT_GAP_MS) {
        segments.push(segment);
        segment = [];
      }
      segment.push({ timeMs, value });
    });
    if (segment.length) segments.push(segment);
    return segments;
  }

  function lineChart(seriesList, options = {}) {
    const normalized = (seriesList || []).map(series => ({ ...series, segments: lineSegments(series.points) }));
    const all = normalized.flatMap(series => series.segments.flat());
    if (!all.length) return empty(options.emptyMessage);
    const xDomain = extent(all.map(point => point.timeMs));
    const yDomain = extent(all.map(point => point.value));
    const paths = normalized.map((series, seriesIndex) => series.segments.map(segment => {
      const d = segment.map((point, index) => `${index ? 'L' : 'M'}${scale(point.timeMs, xDomain, [PAD, WIDTH - PAD]).toFixed(1)} ${scale(point.value, yDomain, [HEIGHT - PAD, PAD]).toFixed(1)}`).join(' ');
      return `<path class="ais-viz-series" style="stroke:${esc(series.color || ['#158b90', '#c55a4f', '#c89a35'][seriesIndex % 3])}" d="${d}"/>`;
    }).join('')).join('');
    const legend = normalized.map((series, index) => `<span><i style="background:${esc(series.color || ['#158b90', '#c55a4f', '#c89a35'][index % 3])}"></i>${esc(series.label)}</span>`).join('');
    return `<div class="ais-viz-chart"><div class="ais-viz-title"><b>${esc(options.title || '趋势')}</b><span>${esc(options.unit || '')}</span></div><svg viewBox="0 0 ${WIDTH} ${HEIGHT}" role="img"><g class="ais-viz-grid">${grid()}</g>${paths}<text x="${PAD}" y="${PAD - 8}">${esc(yDomain[1].toFixed(options.digits ?? 1))}</text><text x="${PAD}" y="${HEIGHT - 8}">${esc(yDomain[0].toFixed(options.digits ?? 1))}</text></svg><div class="ais-viz-legend">${legend}</div></div>`;
  }

  function routePlot({ start, end, events = [], corridorNm = 3 } = {}) {
    const routePoints = [start, end].filter(point => point && Number.isFinite(number(point.lat)) && Number.isFinite(number(point.lon)))
      .map(point => ({ lat: Number(point.lat), lon: Number(point.lon) }));
    if (routePoints.length < 2) return empty('请输入有效目的地后生成筛查走廊');
    const eventPoints = events.filter(event => Number.isFinite(number(event.lat)) && Number.isFinite(number(event.lon)))
      .map(event => ({ ...event, lat: Number(event.lat), lon: Number(event.lon) }));
    const project = geoProjector([...routePoints, ...eventPoints]);
    const first = project(routePoints[0]);
    const last = project(routePoints[1]);
    const markers = eventPoints.map(event => {
      const pos = project(event);
      return `<g><circle class="ais-viz-event ${esc(event.tone || 'watch')}" cx="${pos.x.toFixed(1)}" cy="${pos.y.toFixed(1)}" r="7"/><title>${esc(event.label || '风险事件')}</title></g>`;
    }).join('');
    return `<div class="ais-viz-chart"><div class="ais-viz-title"><b>直线筛查走廊</b><span>半宽 ${esc(corridorNm)} nm · 非推荐航线</span></div><svg viewBox="0 0 ${WIDTH} ${HEIGHT}" role="img"><g class="ais-viz-grid">${grid()}</g><path class="ais-viz-corridor" d="M${first.x.toFixed(1)} ${first.y.toFixed(1)}L${last.x.toFixed(1)} ${last.y.toFixed(1)}"/><path class="ais-viz-route" d="M${first.x.toFixed(1)} ${first.y.toFixed(1)}L${last.x.toFixed(1)} ${last.y.toFixed(1)}"/><circle class="ais-viz-point current" cx="${first.x.toFixed(1)}" cy="${first.y.toFixed(1)}" r="7"/><circle class="ais-viz-destination" cx="${last.x.toFixed(1)}" cy="${last.y.toFixed(1)}" r="7"/>${markers}<text x="${first.x + 10}" y="${first.y - 10}">关注船</text><text x="${last.x + 10}" y="${last.y - 10}">目的地</text></svg><div class="ais-viz-note">未检查陆地、水深、交通分离制、禁限区和操纵性能。</div></div>`;
  }

  function relativeMotion({ vessels = [], cpa = null, title = '相对运动与 CPA' } = {}) {
    const tracks = vessels.map((vessel, index) => ({
      label: vessel.label || `船舶 ${index + 1}`,
      color: vessel.color || ['#148a8f', '#c6544d'][index % 2],
      segments: trackSegments(vessel.points || [], vessel.options || {})
    }));
    const all = tracks.flatMap(track => track.segments.flat());
    if (!all.length) return empty();
    const projected = [];
    tracks.forEach(track => {
      const latest = track.segments.flat().slice(-1)[0];
      if (!latest) return;
      const sog = number(latest.source.sog);
      const cog = number(latest.source.cog);
      if (!(Number.isFinite(sog) && sog >= 0 && Number.isFinite(cog) && cog >= 0 && cog < 360)) return;
      const minutes = Math.max(0, Math.min(30, number(cpa?.tcpa) || 10));
      const distanceNm = sog * minutes / 60;
      const radians = cog * Math.PI / 180;
      projected.push({
        track,
        start: latest,
        end: { lat: latest.lat + Math.cos(radians) * distanceNm / 60, lon: latest.lon + Math.sin(radians) * distanceNm / (60 * Math.cos(latest.lat * Math.PI / 180)) }
      });
    });
    const project = geoProjector([...all, ...projected.map(item => item.end)]);
    const paths = tracks.map(track => track.segments.filter(segment => segment.length > 1).map(segment => `<path class="ais-viz-series" style="stroke:${esc(track.color)}" d="${segment.map((point, index) => { const pos = project(point); return `${index ? 'L' : 'M'}${pos.x.toFixed(1)} ${pos.y.toFixed(1)}`; }).join(' ')}"/>`).join('')).join('');
    const forecasts = projected.map(item => { const start = project(item.start); const end = project(item.end); return `<path class="ais-viz-forecast" style="stroke:${esc(item.track.color)}" d="M${start.x.toFixed(1)} ${start.y.toFixed(1)}L${end.x.toFixed(1)} ${end.y.toFixed(1)}"/><circle class="ais-viz-point" style="fill:${esc(item.track.color)}" cx="${start.x.toFixed(1)}" cy="${start.y.toFixed(1)}" r="6"/>`; }).join('');
    const legend = tracks.map(track => `<span><i style="background:${esc(track.color)}"></i>${esc(track.label)}</span>`).join('');
    return `<div class="ais-viz-chart"><div class="ais-viz-title"><b>${esc(title)}</b><span>${cpa?.available ? `DCPA ${esc(Number(cpa.dcpa).toFixed(2))} nm · TCPA ${esc(Number(cpa.tcpa).toFixed(1))} min` : '运动字段不足时不推算'}</span></div><svg viewBox="0 0 ${WIDTH} ${HEIGHT}" role="img"><g class="ais-viz-grid">${grid()}</g>${paths}${forecasts}</svg><div class="ais-viz-legend">${legend}<span><i class="dashed"></i>匀速直线推算</span></div></div>`;
  }

  function statusMatrix(items = []) {
    if (!items.length) return empty();
    return `<div class="ais-viz-status-grid">${items.map(item => `<div class="ais-viz-status ${esc(item.tone || 'ready')}"><span>${esc(item.label)}</span><b>${esc(item.status)}</b><small>${esc(item.detail || '')}</small></div>`).join('')}</div>`;
  }

  function barChart(items = [], options = {}) {
    const valid = items.map(item => ({ ...item, value: number(item.value) })).filter(item => Number.isFinite(item.value));
    if (!valid.length) return empty();
    const max = Math.max(...valid.map(item => item.value), 1);
    return `<div class="ais-viz-bars"><div class="ais-viz-title"><b>${esc(options.title || '分布')}</b><span>${esc(options.note || '')}</span></div>${valid.map(item => `<div class="ais-viz-bar-row"><span>${esc(item.label)}</span><i><b style="width:${Math.max(1, item.value / max * 100).toFixed(1)}%;background:${esc(item.color || '#168c91')}"></b></i><strong>${esc(item.display ?? item.value)}</strong></div>`).join('')}</div>`;
  }

  function timeline(events = [], options = {}) {
    const rows = events.slice(0, options.limit || 12);
    if (!rows.length) return empty('当前回放时刻没有可视化事件');
    return `<div class="ais-viz-timeline"><div class="ais-viz-title"><b>${esc(options.title || '事件时间轴')}</b><span>${rows.length} 条</span></div>${rows.map((event, index) => `<div class="ais-viz-timeline-row ${esc(event.tone || 'watch')}"><time>${esc(event.time || '--')}</time><i></i><div><b>${esc(event.label || '事件')}</b><span>${esc(event.detail || '')}</span></div>${index < rows.length - 1 ? '<em></em>' : ''}</div>`).join('')}</div>`;
  }

  function evidenceChain(nodes = []) {
    if (!nodes.length) return empty();
    return `<div class="ais-viz-evidence-chain">${nodes.map((node, index) => `<div class="ais-viz-evidence-node ${esc(node.tone || '')}"><span>${esc(node.label)}</span><b>${esc(node.value)}</b><small>${esc(node.detail || '')}</small></div>${index < nodes.length - 1 ? '<i>→</i>' : ''}`).join('')}</div>`;
  }

  const api = { trackSegments, trackPlot, lineChart, routePlot, relativeMotion, statusMatrix, barChart, timeline, evidenceChain, empty };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.AisVisuals = api;
})(typeof window !== 'undefined' ? window : globalThis);
