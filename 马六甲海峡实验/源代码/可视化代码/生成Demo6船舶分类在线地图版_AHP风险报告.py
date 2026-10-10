# -*- coding: utf-8 -*-
"""Build an online-map Demo6 page focused on vessel classification."""

from __future__ import annotations

import json
from pathlib import Path

from build_demo_v6_vessel_classification import build_data


ROOT = Path(__file__).resolve().parents[2]
DEMO_DIR = ROOT / "frontend" / "demo"
OUT_HTML = DEMO_DIR / "demo_map_v6_vessel_classification_online.html"


HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Demo6 船舶分类在线地图版</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <style>
    :root {
      --panel: #ffffff;
      --line: #d8e1ea;
      --text: #142033;
      --muted: #637083;
      --blue: #2368d8;
    }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: "Microsoft YaHei", Arial, sans-serif; color: var(--text); background: #edf3f7; }
    .app { min-height: 100vh; display: grid; grid-template-columns: 1fr 440px; }
    .map-wrap { position: relative; height: 100vh; }
    #map { width: 100%; height: 100%; background: #dbe8f2; }
    .toolbar {
      position: absolute; top: 18px; left: 18px; z-index: 900; display: flex; flex-wrap: wrap; gap: 8px;
      background: #fff; border-radius: 8px; padding: 10px; box-shadow: 0 10px 28px rgba(42,66,92,.16);
    }
    select, button { min-height: 36px; border: 1px solid var(--line); border-radius: 7px; background: #fff; padding: 0 10px; font: inherit; }
    button { cursor: pointer; }
    button.primary { background: var(--blue); border-color: var(--blue); color: #fff; }
    .legend {
      position: absolute; left: 18px; bottom: 18px; z-index: 900; background: #fff; border: 1px solid var(--line);
      border-radius: 8px; padding: 8px 10px; font-size: 12px; line-height: 1.6; color: var(--muted);
      box-shadow: 0 8px 22px rgba(42,66,92,.12);
    }
    .legend-row { display: flex; align-items: center; gap: 6px; white-space: nowrap; }
    .legend-icon { width: 34px; height: 20px; display: inline-flex; align-items: center; justify-content: center; }
    .ship-marker { width: 30px !important; height: 22px !important; margin-left: -15px !important; margin-top: -11px !important; }
    .ship-marker svg { display: block; width: 30px; height: 22px; filter: drop-shadow(0 2px 3px rgba(15, 32, 52, .32)); }
    .ship-marker.selected { z-index: 720 !important; }
    .ship-marker.selected svg { width: 38px; height: 27px; transform-origin: center; }
    .ship-icon-outline { stroke: #fff; stroke-width: 2.4; stroke-linejoin: round; stroke-linecap: round; }
    .ship-icon-line { fill: none; stroke: #142033; stroke-width: 1.6; stroke-linecap: round; stroke-linejoin: round; opacity: .82; }
    .ship-icon-light { fill: rgba(255,255,255,.88); stroke: rgba(20,32,51,.42); stroke-width: .9; }
    .ship-icon-window { fill: #eaf5ff; stroke: rgba(20,32,51,.35); stroke-width: .8; }
    .cargo-box-yellow { fill: #ffd84d; stroke: rgba(20,32,51,.35); stroke-width: .8; }
    .cargo-box-red { fill: #f36b4f; stroke: rgba(20,32,51,.35); stroke-width: .8; }
    .cargo-box-blue { fill: #42a5e8; stroke: rgba(20,32,51,.35); stroke-width: .8; }
    .cargo-box-green { fill: #55b86a; stroke: rgba(20,32,51,.35); stroke-width: .8; }
    .tanker-tank { fill: #d8dce2; stroke: rgba(20,32,51,.56); stroke-width: 1; }
    .fishing-net { fill: none; stroke: #142033; stroke-width: 1.15; stroke-linecap: round; opacity: .86; }
    .side { height: 100vh; background: var(--panel); border-left: 1px solid var(--line); display: grid; grid-template-rows: auto auto minmax(220px, .9fr) minmax(380px, 1.15fr); }
    .header, .stats, .list, .detail { padding: 16px 18px; }
    .header { border-bottom: 1px solid var(--line); }
    h1 { margin: 0 0 6px; font-size: 22px; letter-spacing: 0; }
    .sub { margin: 0; color: var(--muted); font-size: 13px; line-height: 1.55; }
    .tag { display: inline-block; margin-top: 8px; color: #174ea6; background: #edf4ff; border: 1px solid #b9d1ff; border-radius: 999px; padding: 4px 9px; font-size: 12px; }
    .stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; border-bottom: 1px solid var(--line); }
    .stat { border: 1px solid var(--line); border-radius: 8px; background: #fbfdff; padding: 10px; min-height: 58px; }
    .stat b { display: block; font-size: 21px; margin-bottom: 2px; }
    .stat span { color: var(--muted); font-size: 12px; }
    .list { overflow: auto; border-bottom: 1px solid var(--line); }
    .section-title { margin: 0 0 10px; font-size: 16px; }
    .vessel-card { border: 1px solid var(--line); border-radius: 8px; padding: 10px; margin-bottom: 9px; background: #fff; cursor: pointer; }
    .vessel-card.active { border-color: var(--blue); box-shadow: 0 0 0 2px rgba(35,104,216,.12); }
    .card-top { display: flex; justify-content: space-between; gap: 8px; align-items: center; }
    .card-title { font-weight: 700; font-size: 14px; overflow-wrap: anywhere; }
    .badge { color: #fff; border-radius: 999px; padding: 3px 8px; font-size: 12px; white-space: nowrap; }
    .meta { color: var(--muted); margin-top: 6px; font-size: 12px; line-height: 1.55; }
    .detail { background: #f8fbfe; overflow: auto; }
    .detail-box { border: 1px solid var(--line); border-radius: 8px; background: #fff; padding: 12px; font-size: 13px; line-height: 1.6; }
    .detail-box b { color: #0b2545; }
    .risk-head { display: grid; grid-template-columns: 1fr auto; gap: 10px; align-items: start; margin-bottom: 12px; }
    .risk-title { margin: 0; font-size: 15px; font-weight: 800; color: #0b2545; overflow-wrap: anywhere; }
    .risk-meta { margin-top: 4px; color: var(--muted); font-size: 12px; line-height: 1.45; }
    .score-badge { min-width: 86px; border-radius: 8px; padding: 8px 9px; color: #fff; text-align: center; box-shadow: inset 0 -1px 0 rgba(0,0,0,.12); }
    .score-badge b { display: block; color: #fff; font-size: 22px; line-height: 1; }
    .score-badge span { font-size: 12px; }
    .risk-summary { border: 1px solid #dbe6ef; background: #f7fbff; border-radius: 8px; padding: 10px; margin: 10px 0 12px; color: #203047; }
    .risk-grid { display: grid; gap: 8px; margin-top: 8px; }
    .metric { border: 1px solid var(--line); border-radius: 8px; padding: 8px 9px; background: #fff; }
    .metric-top { display: flex; justify-content: space-between; gap: 8px; font-size: 12px; color: #26364f; }
    .metric-name { font-weight: 700; }
    .metric-score { color: var(--muted); white-space: nowrap; }
    .bar { height: 7px; background: #e9eef4; border-radius: 99px; overflow: hidden; margin-top: 6px; }
    .bar-fill { height: 100%; border-radius: 99px; }
    .explain { margin: 12px 0 0; padding-left: 18px; color: #304158; }
    .explain li { margin: 4px 0; }
    .advice { margin-top: 10px; border-left: 4px solid var(--blue); background: #f3f7fc; padding: 9px 10px; border-radius: 6px; color: #22334f; }
    .formula { margin-top: 10px; color: var(--muted); font-size: 12px; line-height: 1.45; }
    .leaflet-popup-content { font-family: "Microsoft YaHei", Arial, sans-serif; line-height: 1.55; }
    @media (max-width: 980px) {
      .app { grid-template-columns: 1fr; grid-template-rows: 58vh auto; }
      .map-wrap { height: 58vh; }
      .side { height: auto; min-height: 42vh; grid-template-rows: auto auto 280px 420px; border-left: 0; border-top: 1px solid var(--line); }
    }
  </style>
</head>
<body>
  <div class="app">
    <main class="map-wrap">
      <div class="toolbar">
        <select id="categoryFilter" aria-label="船型筛选">
          <option value="全部">全部船型</option>
          <option value="货船">货船</option>
          <option value="油轮">油轮</option>
          <option value="渔船">渔船</option>
          <option value="其他">其他</option>
          <option value="未知">未知</option>
        </select>
        <select id="reviewFilter" aria-label="复核筛选">
          <option value="全部">全部复核状态</option>
          <option value="需要">需要复核</option>
          <option value="不需要">不需要复核</option>
        </select>
        <button id="fitBtn" class="primary">适配全图</button>
      </div>
      <div id="map"></div>
      <div class="legend" id="legend"></div>
    </main>
    <aside class="side">
      <section class="header">
        <h1>Demo6 船舶分类在线地图版</h1>
        <p class="sub">基于马六甲海峡 / 新加坡海峡 10 分钟 AIS 数据，在真实在线地图底图上展示船型分类、AHP 风险评分和单船分析报告。</p>
        <span class="tag">在线地图：需要网络加载底图</span>
      </section>
      <section class="stats">
        <div class="stat"><b id="totalShips">0</b><span>总船舶</span></div>
        <div class="stat"><b id="knownShips">0</b><span>已分类</span></div>
        <div class="stat"><b id="trackShips">0</b><span>有轨迹</span></div>
        <div class="stat"><b id="cargoShips">0</b><span>货船</span></div>
        <div class="stat"><b id="tankerShips">0</b><span>油轮</span></div>
        <div class="stat"><b id="unknownShips">0</b><span>未知</span></div>
      </section>
      <section class="list">
        <h2 class="section-title">船舶分类列表</h2>
        <div id="vesselList"></div>
      </section>
      <section class="detail">
        <h2 class="section-title">单船风险分析报告</h2>
        <div id="detailBox" class="detail-box"></div>
      </section>
    </aside>
  </div>
  <script>
    const DATA = __DATA__;
    const COLORS = { "货船": "#2368d8", "油轮": "#d98210", "渔船": "#27875d", "其他": "#6e56cf", "未知": "#8a96a3" };
    const ORDER = ["货船", "油轮", "渔船", "其他", "未知"];
    const AHP_WEIGHTS = [
      { key: 'behavior', name: '船舶行为异常', weight: 0.3197 },
      { key: 'encounter', name: '碰撞与会遇风险', weight: 0.3197 },
      { key: 'environment', name: '水域通航环境', weight: 0.1836 },
      { key: 'consequence', name: '船舶类型后果', weight: 0.1091 },
      { key: 'credibility', name: 'AIS 数据可信度', weight: 0.0680 }
    ];
    const RISK_COLORS = { low: '#23845a', medium: '#c78b11', elevated: '#d66a1f', high: '#c53434' };
    const map = L.map('map', { zoomControl: true }).setView([1.25, 103.84], 11);
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 18,
      attribution: '&copy; OpenStreetMap contributors'
    }).addTo(map);
    let selected = DATA.vessels.find(v => v.points.length) || DATA.vessels[0];
    let layers = [];

    function visibleVessels() {
      const category = document.getElementById('categoryFilter').value;
      const review = document.getElementById('reviewFilter').value;
      return DATA.vessels.filter(v => {
        const categoryOk = category === '全部' || v.category === category;
        const need = String(v.need_review || '').includes('是') || String(v.need_review || '').includes('建议');
        const reviewOk = review === '全部' || (review === '需要' ? need : !need);
        return categoryOk && reviewOk;
      });
    }

    function popupHtml(v) {
      const risk = riskProfile(v);
      return `<b>${v.name}</b><br>MMSI：${v.mmsi}<br>船型：${v.category}<br>风险等级：${risk.level}<br>综合分：${risk.total} / 100`;
    }

    function headingOf(v) {
      const last = v.points[v.points.length - 1] || {};
      const raw = Number(last.heading);
      const cog = Number(last.cog);
      if (Number.isFinite(raw) && raw >= 0 && raw < 360) return raw;
      if (Number.isFinite(cog) && cog >= 0 && cog < 360) return cog;
      return 0;
    }

    function shipSvg(category, color, rotation = 90, selectedIcon = false) {
      const width = selectedIcon ? 38 : 30;
      const height = selectedIcon ? 27 : 22;
      const scale = selectedIcon ? 1.06 : 1;
      const turn = rotation - 90;
      const hull = `class="ship-icon-outline" fill="${color}"`;
      let inner = '';
      if (category === '货船') {
        inner = `
          <path ${hull} d="M5 24 H34 L44 17 H50 L46 30 H13 Q7 30 5 24 Z"/>
          <rect class="cargo-box-yellow" x="10" y="14" width="6.4" height="5.6" rx=".8"/>
          <rect class="cargo-box-red" x="17" y="14" width="6.4" height="5.6" rx=".8"/>
          <rect class="cargo-box-blue" x="24" y="14" width="6.4" height="5.6" rx=".8"/>
          <rect class="cargo-box-green" x="13.5" y="8" width="6.4" height="5.6" rx=".8"/>
          <rect class="cargo-box-yellow" x="20.5" y="8" width="6.4" height="5.6" rx=".8"/>
          <path class="ship-icon-line" d="M9 27 H43 M36 17 l5 -4"/>`;
      } else if (category === '油轮') {
        inner = `
          <path ${hull} d="M4 24 H35 L45 17 H51 L47 30 H12 Q6 30 4 24 Z"/>
          <rect class="ship-icon-light" x="37" y="8" width="8" height="10" rx="1.4"/>
          <rect class="ship-icon-window" x="40" y="10" width="3" height="2"/>
          <ellipse class="tanker-tank" cx="14" cy="17.3" rx="5.2" ry="5.1"/>
          <ellipse class="tanker-tank" cx="25" cy="17.3" rx="5.2" ry="5.1"/>
          <ellipse class="tanker-tank" cx="36" cy="17.3" rx="5.2" ry="5.1"/>
          <path class="ship-icon-line" d="M9 27 Q26 30 44 27 M10 12 H38"/>`;
      } else if (category === '渔船') {
        inner = `
          <path ${hull} d="M8 25 H33 L44 19 H50 L46 30 H15 Q10 30 8 25 Z"/>
          <rect class="ship-icon-light" x="31" y="10" width="10" height="9" rx="1.8"/>
          <rect class="ship-icon-window" x="34" y="12" width="4.4" height="2.8"/>
          <path class="ship-icon-line" d="M21 23 V6 M21 6 L8 18 M21 6 L31 20"/>
          <path class="fishing-net" d="M9 18 q-4 5 .8 9 q3.3-4 .2-9 M7.5 22 H12.8 M8.8 25 H12"/>
          <path class="ship-icon-line" d="M13 27 H43"/>`;
      } else if (category === '其他') {
        inner = `
          <path ${hull} d="M7 24 H34 L45 18 H51 L47 30 H15 Q9 30 7 24 Z"/>
          <rect class="ship-icon-light" x="31" y="9.5" width="11" height="10" rx="2"/>
          <rect class="ship-icon-window" x="34" y="12" width="4.6" height="3"/>
          <circle class="ship-icon-light" cx="16" cy="26" r="1.8"/>
          <circle class="ship-icon-light" cx="23" cy="26" r="1.8"/>`;
      } else {
        inner = `
          <path ${hull} d="M7 24 H34 L45 18 H51 L47 30 H15 Q9 30 7 24 Z"/>
          <rect class="ship-icon-light" x="31" y="10" width="10.5" height="9.5" rx="2"/>
          <path class="ship-icon-line" d="M21 13 q.5-5 5-5 q4.6 0 4.6 3.7 q0 2.5-3.2 4.2 q-2.2 1.1-2.2 3.5"/>
          <circle class="ship-icon-line" cx="25.4" cy="24.8" r="1.2"/>`;
      }
      return `<svg viewBox="0 0 56 40" width="${width}" height="${height}" aria-label="${category}图标">
        <g transform="rotate(${turn} 28 20) scale(${scale}) translate(${selectedIcon ? -1.3 : 0} ${selectedIcon ? -1 : 0})">${inner}</g>
      </svg>`;
    }

    function vesselIcon(v) {
      const selectedIcon = selected.mmsi === v.mmsi;
      const color = COLORS[v.category] || COLORS['未知'];
      return L.divIcon({
        className: `ship-marker ${selectedIcon ? 'selected' : ''}`,
        html: shipSvg(v.category, color, headingOf(v), selectedIcon),
        iconSize: [selectedIcon ? 38 : 30, selectedIcon ? 27 : 22],
        iconAnchor: [selectedIcon ? 19 : 15, selectedIcon ? 13.5 : 11],
        popupAnchor: [0, selectedIcon ? -15 : -12]
      });
    }

    function clearLayers() {
      layers.forEach(layer => map.removeLayer(layer));
      layers = [];
    }

    function renderMap(fit = false) {
      clearLayers();
      const bounds = [];
      visibleVessels().forEach(v => {
        const color = COLORS[v.category] || COLORS['未知'];
        const latlngs = v.points.map(p => [p.lat, p.lon]);
        if (latlngs.length > 1) {
          const line = L.polyline(latlngs, {
            color,
            weight: selected.mmsi === v.mmsi ? 4 : 2.4,
            opacity: selected.mmsi === v.mmsi ? .95 : .55
          }).addTo(map);
          line.on('click', () => selectVessel(v.mmsi, false));
          layers.push(line);
          latlngs.forEach(p => bounds.push(p));
        }
        if (latlngs.length > 0) {
          const last = latlngs[latlngs.length - 1];
          const marker = L.marker(last, { icon: vesselIcon(v), riseOnHover: true }).addTo(map);
          marker.bindPopup(popupHtml(v));
          marker.on('click', () => selectVessel(v.mmsi, false));
          layers.push(marker);
          bounds.push(last);
        }
      });
      if (fit && bounds.length) {
        map.fitBounds(bounds, { padding: [34, 34] });
      }
    }

    function renderStats() {
      document.getElementById('totalShips').textContent = DATA.stats.total;
      document.getElementById('knownShips').textContent = DATA.stats.known;
      document.getElementById('trackShips').textContent = DATA.stats.with_track;
      document.getElementById('cargoShips').textContent = DATA.stats.counts['货船'] || 0;
      document.getElementById('tankerShips').textContent = DATA.stats.counts['油轮'] || 0;
      document.getElementById('unknownShips').textContent = DATA.stats.counts['未知'] || 0;
      document.getElementById('legend').innerHTML = ORDER.map(c => `<div class="legend-row"><span class="legend-icon">${shipSvg(c, COLORS[c], 90, false)}</span>${c}：${DATA.stats.counts[c] || 0} 艘</div>`).join('');
    }

    function renderList() {
      const wrap = document.getElementById('vesselList');
      wrap.innerHTML = '';
      visibleVessels().forEach(v => {
        const risk = riskProfile(v);
        const card = document.createElement('div');
        card.className = 'vessel-card' + (selected.mmsi === v.mmsi ? ' active' : '');
        card.innerHTML = `<div class="card-top"><div class="card-title">${v.name}</div><span class="badge" style="background:${COLORS[v.category]}">${v.category}</span></div>
          <div class="meta">MMSI：${v.mmsi}<br>风险：<b style="color:${risk.color}">${risk.level} ${risk.total}分</b> | 轨迹点：${v.points.length} | 平均速度：${formatValue(v.avg_sog, '节')}</div>`;
        card.onclick = () => selectVessel(v.mmsi, true);
        wrap.appendChild(card);
      });
    }

    function clamp(value, min = 0, max = 100) {
      return Math.max(min, Math.min(max, value));
    }

    function numberOr(value, fallback = 0) {
      const n = Number(value);
      return Number.isFinite(n) ? n : fallback;
    }

    function formatValue(value, unit = '') {
      const n = Number(value);
      if (!Number.isFinite(n)) return '暂无';
      return `${n.toFixed(1)}${unit}`;
    }

    function haversineKm(a, b) {
      const rad = Math.PI / 180;
      const dLat = (b.lat - a.lat) * rad;
      const dLon = (b.lon - a.lon) * rad;
      const lat1 = a.lat * rad;
      const lat2 = b.lat * rad;
      const s = Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;
      return 6371 * 2 * Math.atan2(Math.sqrt(s), Math.sqrt(1 - s));
    }

    function nearbyCount(v, km = 3) {
      const last = v.points[v.points.length - 1];
      if (!last) return 0;
      return DATA.vessels.filter(other => {
        if (other.mmsi === v.mmsi || !other.points.length) return false;
        const oLast = other.points[other.points.length - 1];
        return haversineKm(last, oLast) <= km;
      }).length;
    }

    function riskLevel(score) {
      if (score >= 80) return { level: '高风险', key: 'high', advice: '建议重点关注，后续可生成预警记录并持续跟踪该船轨迹。' };
      if (score >= 60) return { level: '较高风险', key: 'elevated', advice: '建议人工复核，重点查看船型、速度状态和后续轨迹变化。' };
      if (score >= 40) return { level: '中风险', key: 'medium', advice: '建议继续跟踪，等待更多 AIS 轨迹点后再更新判断。' };
      return { level: '低风险', key: 'low', advice: '当前仅需正常观察，暂未出现明显风险信号。' };
    }

    function riskProfile(v) {
      const avgSog = numberOr(v.avg_sog, NaN);
      const pointCount = v.points.length || numberOr(v.point_count, 0);
      const last = v.points[v.points.length - 1] || {};
      const near = nearbyCount(v);
      let behavior = 28;
      if (!Number.isFinite(avgSog)) behavior += 18;
      else if (avgSog < 0.5) behavior += 34;
      else if (avgSog < 2) behavior += 22;
      else if (avgSog > 18) behavior += 24;
      else if (avgSog > 12) behavior += 14;
      if (pointCount <= 1) behavior += 18;
      else if (pointCount <= 3) behavior += 10;

      const encounter = clamp(30 + near * 13 + (Number.isFinite(avgSog) && avgSog > 10 ? 8 : 0));
      const environment = clamp(58 + (last.lon >= 103.75 && last.lon <= 103.95 ? 10 : 0) + (near >= 3 ? 8 : 0));
      const consequenceMap = { '油轮': 82, '货船': 68, '渔船': 48, '其他': 42, '未知': 55 };
      const consequence = consequenceMap[v.category] ?? 50;
      let credibility = 24;
      if (!v.name || v.name === '未获取船名') credibility += 18;
      if (!v.vessel_type || String(v.vessel_type).trim() === '') credibility += 18;
      if (pointCount <= 1) credibility += 30;
      else if (pointCount <= 3) credibility += 18;
      if (String(v.need_review || '').includes('建议') || String(v.need_review || '').includes('是')) credibility += 12;

      const raw = {
        behavior: clamp(behavior),
        encounter: clamp(encounter),
        environment: clamp(environment),
        consequence: clamp(consequence),
        credibility: clamp(credibility)
      };
      const items = AHP_WEIGHTS.map(item => ({
        ...item,
        score: Number(raw[item.key].toFixed(1)),
        contribution: Number((raw[item.key] * item.weight).toFixed(2))
      }));
      const total = Number(items.reduce((sum, item) => sum + item.contribution, 0).toFixed(1));
      const level = riskLevel(total);
      return { total, items, near, ...level, color: RISK_COLORS[level.key] };
    }

    function riskReasons(v, risk) {
      const avgSog = numberOr(v.avg_sog, NaN);
      const reasons = [];
      reasons.push(`系统将该船识别为${v.category}，船型会影响事故后果维度的分数。`);
      if (!Number.isFinite(avgSog)) reasons.push('当前平均速度缺失，系统会把它作为信息不足处理。');
      else if (avgSog < 0.5) reasons.push(`平均速度约 ${avgSog.toFixed(1)} 节，接近静止，可能是停泊、等待或低速通过。`);
      else reasons.push(`平均速度约 ${avgSog.toFixed(1)} 节，系统据此判断运动状态是否异常。`);
      if (risk.near > 0) reasons.push(`该船周边约 3 公里内有 ${risk.near} 艘船，会遇风险相应提高。`);
      else reasons.push('该船周边近距离船舶较少，会遇风险暂时不高。');
      if ((v.points.length || 0) <= 1) reasons.push('轨迹点数量偏少，AIS 数据可信度较弱，建议后续继续采集。');
      return reasons;
    }

    function renderDetail() {
      const v = selected;
      const risk = riskProfile(v);
      const rows = risk.items.map(item => `
        <div class="metric">
          <div class="metric-top">
            <span class="metric-name">${item.name}</span>
            <span class="metric-score">${item.score}分 × ${(item.weight * 100).toFixed(2)}% = ${item.contribution}分</span>
          </div>
          <div class="bar"><div class="bar-fill" style="width:${item.score}%;background:${risk.color}"></div></div>
        </div>`).join('');
      const reasons = riskReasons(v, risk).map(text => `<li>${text}</li>`).join('');
      document.getElementById('detailBox').innerHTML = `
        <div class="risk-head">
          <div>
            <p class="risk-title">${v.name}</p>
            <div class="risk-meta">MMSI：${v.mmsi}<br>船型：<span style="color:${COLORS[v.category]};font-weight:700">${v.category}</span> | AIS码：${v.vessel_type || '暂无'}<br>轨迹点：${v.points.length} | 平均速度：${formatValue(v.avg_sog, '节')}</div>
          </div>
          <div class="score-badge" style="background:${risk.color}">
            <b>${risk.total}</b><span>${risk.level}</span>
          </div>
        </div>
        <div class="risk-summary">
          <b>分类依据：</b>${v.reason || '暂无'}<br>
          <b>数据状态：</b>${v.confidence || '未标注'}，${v.need_review || '暂无'}。
        </div>
        <b>AHP 指标分解</b>
        <div class="risk-grid">${rows}</div>
        <ul class="explain">${reasons}</ul>
        <div class="advice"><b>处置建议：</b>${risk.advice}</div>
        <div class="formula">计算方法：综合风险分 = Σ（维度得分 × AHP 权重）。当前为演示版规则评分，后续可接入专家问卷和更多历史轨迹数据修正。</div>`;
    }

    function selectVessel(mmsi, pan) {
      selected = DATA.vessels.find(v => v.mmsi === mmsi) || selected;
      renderList();
      renderDetail();
      renderMap(false);
      const last = selected.points[selected.points.length - 1];
      if (pan && last) {
        map.setView([last.lat, last.lon], Math.max(map.getZoom(), 13));
      }
    }

    function ensureSelectedVisible() {
      const visible = visibleVessels();
      if (!visible.length) return;
      if (!visible.some(v => v.mmsi === selected.mmsi)) selected = visible[0];
    }

    document.getElementById('categoryFilter').onchange = () => { ensureSelectedVisible(); renderList(); renderDetail(); renderMap(true); };
    document.getElementById('reviewFilter').onchange = () => { ensureSelectedVisible(); renderList(); renderDetail(); renderMap(true); };
    document.getElementById('fitBtn').onclick = () => renderMap(true);
    renderStats();
    renderList();
    renderDetail();
    renderMap(true);
  </script>
</body>
</html>
"""


def main() -> None:
    data = build_data()
    DEMO_DIR.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(HTML.replace("__DATA__", json.dumps(data, ensure_ascii=False)), encoding="utf-8")
    print(f"Wrote {OUT_HTML}")
    print(data["stats"])


if __name__ == "__main__":
    main()
