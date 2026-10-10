# -*- coding: utf-8 -*-
"""Build an online-map Demo7 page that replays historical AIS data."""

from __future__ import annotations

import json
from pathlib import Path

from build_demo_v6_vessel_classification import build_data


ROOT = Path(__file__).resolve().parents[2]
DEMO_DIR = ROOT / "frontend" / "demo"
OUT_HTML = DEMO_DIR / "demo_map_v7_historical_replay.html"


HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Demo7 历史AIS动态监测模拟版</title>
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
    button.icon { min-width: 38px; padding: 0 9px; font-weight: 800; }
    .time-panel {
      position: absolute; left: 18px; right: 18px; bottom: 18px; z-index: 890; display: grid; grid-template-columns: auto 1fr auto;
      gap: 12px; align-items: center; background: rgba(255,255,255,.96); border: 1px solid var(--line); border-radius: 8px;
      padding: 10px 12px; box-shadow: 0 10px 28px rgba(42,66,92,.16);
    }
    .time-controls { display: flex; gap: 7px; align-items: center; }
    .time-center { display: grid; gap: 5px; min-width: 0; }
    .time-meta { display: flex; flex-wrap: wrap; gap: 10px; color: var(--muted); font-size: 12px; }
    #timeSlider { width: 100%; accent-color: var(--blue); }
    .live-chip { border-radius: 999px; padding: 5px 9px; background: #eff6ff; color: #174ea6; border: 1px solid #bfd5ff; font-size: 12px; white-space: nowrap; }
    .legend {
      position: absolute; left: 18px; bottom: 88px; z-index: 900; background: #fff; border: 1px solid var(--line);
      border-radius: 8px; padding: 9px 10px; font-size: 12px; line-height: 1.55; color: var(--muted);
      box-shadow: 0 8px 22px rgba(42,66,92,.12);
    }
    .legend-title { font-weight: 800; color: #1b2b42; margin: 2px 0 5px; }
    .legend-block + .legend-block { margin-top: 8px; padding-top: 8px; border-top: 1px solid #e4ebf2; }
    .legend-row { display: flex; align-items: center; gap: 6px; white-space: nowrap; }
    .legend-icon { width: 34px; height: 20px; display: inline-flex; align-items: center; justify-content: center; }
    .risk-swatch { width: 14px; height: 14px; border-radius: 50%; box-shadow: inset 0 0 0 2px rgba(255,255,255,.86), 0 0 0 1px rgba(20,32,51,.18); }
    .ship-marker { width: 88px !important; height: 46px !important; margin-left: -44px !important; margin-top: -23px !important; }
    .ship-marker svg { display: block; width: 30px; height: 22px; filter: drop-shadow(0 2px 3px rgba(15, 32, 52, .32)); }
    .ship-marker.selected { z-index: 720 !important; }
    .ship-marker.selected svg { width: 38px; height: 27px; transform-origin: center; }
    .risk-marker { position: relative; width: 88px; height: 46px; display: flex; align-items: center; justify-content: center; pointer-events: auto; }
    .risk-marker .ship-wrap { position: relative; z-index: 2; }
    .risk-halo { position: absolute; left: 50%; top: 50%; width: 34px; height: 34px; border-radius: 50%; transform: translate(-50%, -50%); opacity: .82; }
    .risk-marker.risk-low .risk-halo { display: none; }
    .risk-marker.risk-medium .risk-halo { border: 2px solid rgba(199,139,17,.65); background: rgba(199,139,17,.10); }
    .risk-marker.risk-elevated .risk-halo { width: 40px; height: 40px; border: 2px solid rgba(214,106,31,.82); background: rgba(214,106,31,.16); box-shadow: 0 0 14px rgba(214,106,31,.45); }
    .risk-marker.risk-high .risk-halo { width: 44px; height: 44px; border: 2px solid rgba(197,52,52,.94); background: rgba(197,52,52,.18); box-shadow: 0 0 18px rgba(197,52,52,.62); animation: alarmPulse 1.15s ease-out infinite; }
    .risk-marker.selected .risk-halo { width: 48px; height: 48px; }
    .risk-label { display: none; position: absolute; left: 50%; top: 0; transform: translateX(-50%); z-index: 3; border-radius: 999px; padding: 2px 7px; color: #fff; font-size: 11px; font-weight: 800; line-height: 1.4; white-space: nowrap; box-shadow: 0 5px 14px rgba(20,32,51,.26); }
    .risk-marker.risk-high.show-score .risk-label { display: block; background: #c53434; }
    @keyframes alarmPulse {
      0% { transform: translate(-50%, -50%) scale(.72); opacity: .92; }
      72% { transform: translate(-50%, -50%) scale(1.32); opacity: .14; }
      100% { transform: translate(-50%, -50%) scale(1.45); opacity: 0; }
    }
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
      .time-panel { grid-template-columns: 1fr; left: 10px; right: 10px; bottom: 10px; }
      .legend { display: none; }
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
          <option value="客船">客船</option>
          <option value="拖船/港口服务船">拖船/港口服务船</option>
          <option value="游艇/娱乐船">游艇/娱乐船</option>
          <option value="高速船">高速船</option>
          <option value="作业船">作业船</option>
          <option value="其他">其他</option>
          <option value="未知">未知</option>
        </select>
        <select id="reviewFilter" aria-label="复核筛选">
          <option value="全部">全部复核状态</option>
          <option value="需要">需要复核</option>
          <option value="不需要">不需要复核</option>
        </select>
        <select id="riskFilter" aria-label="风险筛选">
          <option value="全部">全部风险</option>
          <option value="高风险">只看高风险</option>
          <option value="较高风险">较高及以上</option>
        </select>
        <button id="fitBtn" class="primary">适配全图</button>
      </div>
      <div id="map"></div>
      <div class="legend" id="legend"></div>
      <div class="time-panel">
        <div class="time-controls">
          <button id="playBtn" class="primary">播放</button>
          <button id="prevBtn" class="icon" aria-label="上一步">&lt;</button>
          <button id="nextBtn" class="icon" aria-label="下一步">&gt;</button>
        </div>
        <div class="time-center">
          <input id="timeSlider" type="range" min="0" max="0" value="0" aria-label="回放时间轴" />
          <div class="time-meta">
            <span id="currentTimeText">当前模拟时间：暂无</span>
            <span>节奏：每 3 秒推进 30 秒 AIS 时间</span>
          </div>
        </div>
        <span class="live-chip" id="liveStatus">历史回放待开始</span>
      </div>
    </main>
    <aside class="side">
      <section class="header">
        <h1>Demo7 历史AIS动态监测模拟版</h1>
        <p class="sub">把马六甲海峡历史 AIS 数据按时间顺序播放，模拟船舶动态出现、位置刷新、风险变化和右侧智能体分析报告。</p>
        <span class="tag">在线地图：需要网络加载底图</span>
      </section>
      <section class="stats">
        <div class="stat"><b id="totalShips">0</b><span>当前船舶</span></div>
        <div class="stat"><b id="knownShips">0</b><span>已分类</span></div>
        <div class="stat"><b id="trackShips">0</b><span>轨迹点</span></div>
        <div class="stat"><b id="cargoShips">0</b><span>货船</span></div>
        <div class="stat"><b id="tankerShips">0</b><span>油轮</span></div>
        <div class="stat"><b id="unknownShips">0</b><span>高风险</span></div>
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
    const COLORS = {
      "货船": "#2368d8",
      "油轮": "#d98210",
      "渔船": "#27875d",
      "客船": "#8b5cf6",
      "拖船/港口服务船": "#0f766e",
      "游艇/娱乐船": "#db2777",
      "高速船": "#ea580c",
      "作业船": "#0891b2",
      "其他": "#6e56cf",
      "未知": "#8a96a3"
    };
    const ORDER = ["货船", "油轮", "渔船", "客船", "拖船/港口服务船", "游艇/娱乐船", "高速船", "作业船", "其他", "未知"];
    const AHP_WEIGHTS = [
      { key: 'behavior', name: '船舶行为异常', weight: 0.3197 },
      { key: 'encounter', name: '碰撞与会遇风险', weight: 0.3197 },
      { key: 'environment', name: '水域通航环境', weight: 0.1836 },
      { key: 'consequence', name: '船舶类型后果', weight: 0.1091 },
      { key: 'credibility', name: 'AIS 数据可信度', weight: 0.0680 }
    ];
    const RISK_COLORS = { low: '#23845a', medium: '#c78b11', elevated: '#d66a1f', high: '#c53434' };
    const PLAY_INTERVAL_MS = 3000;
    const AIS_STEP_MS = 30000;
    const map = L.map('map', { zoomControl: true }).setView([1.25, 103.84], 11);
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 18,
      attribution: '&copy; OpenStreetMap contributors'
    }).addTo(map);
    const allPointTimes = DATA.vessels.flatMap(v => v.points.map(p => Date.parse(p.time))).filter(Number.isFinite).sort((a, b) => a - b);
    const replayStart = allPointTimes[0] || Date.now();
    const replayEnd = allPointTimes[allPointTimes.length - 1] || replayStart;
    const timeSteps = [];
    for (let t = replayStart; t <= replayEnd + AIS_STEP_MS; t += AIS_STEP_MS) timeSteps.push(t);
    let currentStep = 0;
    let isPlaying = false;
    let replayTimer = null;
    let selected = DATA.vessels.find(v => v.points.length) || DATA.vessels[0];
    const shownScoreMmsis = new Set();
    let layers = [];

    function currentTime() {
      return timeSteps[Math.min(currentStep, timeSteps.length - 1)] || replayStart;
    }

    function vesselSnapshot(v, cutoff) {
      const pts = v.points.filter(p => {
        const t = Date.parse(p.time);
        return Number.isFinite(t) && t <= cutoff;
      });
      const sogs = pts.map(p => Number(p.sog)).filter(Number.isFinite);
      const avgSog = sogs.length ? Number((sogs.reduce((sum, n) => sum + n, 0) / sogs.length).toFixed(2)) : null;
      return { ...v, points: pts, point_count: pts.length, avg_sog: avgSog };
    }

    function activeVessels() {
      return DATA.vessels.map(v => vesselSnapshot(v, currentTime())).filter(v => v.points.length > 0);
    }

    function visibleVessels() {
      const category = document.getElementById('categoryFilter').value;
      const review = document.getElementById('reviewFilter').value;
      const riskFilter = document.getElementById('riskFilter').value;
      return activeVessels().filter(v => {
        const categoryOk = category === '全部' || v.category === category;
        const need = String(v.need_review || '').includes('是') || String(v.need_review || '').includes('建议');
        const reviewOk = review === '全部' || (review === '需要' ? need : !need);
        const risk = riskProfile(v);
        const riskOk = riskFilter === '全部' || (riskFilter === '高风险' ? risk.level === '高风险' : ['较高风险', '高风险'].includes(risk.level));
        return categoryOk && reviewOk && riskOk;
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
      } else if (category === '客船') {
        inner = `
          <path ${hull} d="M4 24 H36 L48 17 H52 L48 30 H12 Q6 30 4 24 Z"/>
          <rect class="ship-icon-light" x="12" y="9" width="27" height="10" rx="2"/>
          <rect class="ship-icon-window" x="15" y="11.5" width="3" height="2.4"/>
          <rect class="ship-icon-window" x="21" y="11.5" width="3" height="2.4"/>
          <rect class="ship-icon-window" x="27" y="11.5" width="3" height="2.4"/>
          <rect class="ship-icon-window" x="33" y="11.5" width="3" height="2.4"/>
          <path class="ship-icon-line" d="M10 27 H45 M40 17 l4 -5"/>`;
      } else if (category === '拖船/港口服务船') {
        inner = `
          <path ${hull} d="M8 25 H29 L39 20 H49 L46 30 H14 Q10 30 8 25 Z"/>
          <rect class="ship-icon-light" x="28" y="10" width="12" height="10" rx="2"/>
          <rect class="ship-icon-window" x="31" y="12.5" width="5" height="2.8"/>
          <path class="ship-icon-line" d="M11 23 H22 M14 19 H24 M42 25 l7 -4"/>
          <circle class="ship-icon-light" cx="15" cy="26" r="2"/>`;
      } else if (category === '游艇/娱乐船') {
        inner = `
          <path ${hull} d="M7 25 H36 L48 19 H52 L47 29 H14 Q9 29 7 25 Z"/>
          <path class="ship-icon-light" d="M26 8 L36 22 H19 Z"/>
          <path class="ship-icon-line" d="M26 7 V24 M12 27 H44"/>
          <rect class="ship-icon-window" x="33" y="22" width="5" height="2.4"/>`;
      } else if (category === '高速船') {
        inner = `
          <path ${hull} d="M3 25 H35 L51 17 H53 L47 30 H12 Q6 30 3 25 Z"/>
          <path class="ship-icon-light" d="M16 14 H39 L45 18 H20 Z"/>
          <rect class="ship-icon-window" x="23" y="15.5" width="4" height="2"/>
          <rect class="ship-icon-window" x="30" y="15.5" width="4" height="2"/>
          <path class="ship-icon-line" d="M9 31 C18 34 32 34 45 31 M8 20 H18"/>`;
      } else if (category === '作业船') {
        inner = `
          <path ${hull} d="M6 25 H33 L44 18 H51 L46 30 H14 Q9 30 6 25 Z"/>
          <rect class="ship-icon-light" x="31" y="10" width="11" height="9" rx="1.8"/>
          <path class="ship-icon-line" d="M18 24 V8 M18 8 L8 18 M18 8 L29 19 M9 27 H43"/>
          <circle class="ship-icon-window" cx="36" cy="14" r="1.8"/>`;
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
      const selectedIcon = selected && selected.mmsi === v.mmsi;
      const risk = riskProfile(v);
      const color = risk.color;
      const showScore = shownScoreMmsis.has(String(v.mmsi));
      const html = `
        <div class="risk-marker risk-${risk.key} ${selectedIcon ? 'selected' : ''} ${showScore ? 'show-score' : ''}" title="${risk.level} ${risk.total}分">
          <span class="risk-halo"></span>
          <span class="risk-label">${risk.total}分</span>
          <span class="ship-wrap">${shipSvg(v.category, color, headingOf(v), selectedIcon)}</span>
        </div>`;
      return L.divIcon({
        className: `ship-marker ${selectedIcon ? 'selected' : ''}`,
        html,
        iconSize: [88, 46],
        iconAnchor: [44, 28],
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
            weight: selected && selected.mmsi === v.mmsi ? 4 : 2.4,
            opacity: selected && selected.mmsi === v.mmsi ? .95 : .55
          }).addTo(map);
          line.on('click', () => selectVessel(v.mmsi, false));
          layers.push(line);
          latlngs.forEach(p => bounds.push(p));
        }
        if (latlngs.length > 0) {
          const last = latlngs[latlngs.length - 1];
          const marker = L.marker(last, { icon: vesselIcon(v), riseOnHover: true }).addTo(map);
          marker.bindPopup(popupHtml(v));
          marker.on('click', () => toggleVesselScore(v.mmsi, false));
          layers.push(marker);
          bounds.push(last);
        }
      });
      if (fit && bounds.length) {
        map.fitBounds(bounds, { padding: [34, 34] });
      }
    }

    function renderStats() {
      const current = activeVessels();
      const counts = Object.fromEntries(ORDER.map(c => [c, 0]));
      current.forEach(v => counts[v.category] = (counts[v.category] || 0) + 1);
      const highRiskCount = current.filter(v => riskProfile(v).key === 'high').length;
      const pointCount = current.reduce((sum, v) => sum + v.points.length, 0);
      document.getElementById('totalShips').textContent = current.length;
      document.getElementById('knownShips').textContent = current.filter(v => v.category !== '未知').length;
      document.getElementById('trackShips').textContent = pointCount;
      document.getElementById('cargoShips').textContent = counts['货船'] || 0;
      document.getElementById('tankerShips').textContent = counts['油轮'] || 0;
      document.getElementById('unknownShips').textContent = highRiskCount;
      const typeLegend = ORDER.map(c => `<div class="legend-row"><span class="legend-icon">${shipSvg(c, '#64748b', 90, false)}</span>${c}：${counts[c] || 0} 艘</div>`).join('');
      const riskLegend = [
        ['低风险', RISK_COLORS.low, '0-39分'],
        ['中风险', RISK_COLORS.medium, '40-59分'],
        ['较高风险', RISK_COLORS.elevated, '60-79分'],
        ['高风险', RISK_COLORS.high, '80-100分 闪烁']
      ].map(([name, color, desc]) => `<div class="legend-row"><span class="risk-swatch" style="background:${color}"></span>${name}：${desc}</div>`).join('');
      document.getElementById('legend').innerHTML = `
        <div class="legend-block"><div class="legend-title">船型看外形</div>${typeLegend}</div>
        <div class="legend-block"><div class="legend-title">风险看颜色</div>${riskLegend}</div>`;
    }

    function renderList() {
      const wrap = document.getElementById('vesselList');
      wrap.innerHTML = '';
      visibleVessels().forEach(v => {
        const risk = riskProfile(v);
        const card = document.createElement('div');
        card.className = 'vessel-card' + (selected && selected.mmsi === v.mmsi ? ' active' : '');
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
      return activeVessels().filter(other => {
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
      const consequenceMap = {
        '油轮': 82,
        '货船': 68,
        '客船': 74,
        '拖船/港口服务船': 58,
        '作业船': 62,
        '高速船': 64,
        '渔船': 48,
        '游艇/娱乐船': 38,
        '其他': 42,
        '未知': 55
      };
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
      reasons.push(`系统将该船识别为${v.category}${v.broad_category ? `，归入${v.broad_category}` : ''}，船型会影响事故后果维度的分数。`);
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
      if (!v || !v.points || !v.points.length) {
        document.getElementById('detailBox').innerHTML = '当前模拟时间内还没有可分析的船舶。点击播放后，系统会按时间逐步显示船舶并生成风险报告。';
        return;
      }
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
            <div class="risk-meta">MMSI：${v.mmsi}<br>细分类：<span style="color:${COLORS[v.category]};font-weight:700">${v.category}</span> | 大类：${v.broad_category || '暂无'}<br>AIS码：${v.vessel_type || '暂无'} | 轨迹点：${v.points.length} | 平均速度：${formatValue(v.avg_sog, '节')}</div>
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
      selected = activeVessels().find(v => v.mmsi === mmsi) || selected;
      renderList();
      renderDetail();
      renderMap(false);
      const last = selected.points[selected.points.length - 1];
      if (pan && last) {
        map.setView([last.lat, last.lon], Math.max(map.getZoom(), 13));
      }
    }

    function toggleVesselScore(mmsi, pan) {
      const key = String(mmsi);
      selected = activeVessels().find(v => v.mmsi === mmsi) || selected;
      const risk = riskProfile(selected);
      if (risk.key === 'high') {
        if (shownScoreMmsis.has(key)) shownScoreMmsis.delete(key);
        else shownScoreMmsis.add(key);
      }
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
      if (!visible.length) {
        selected = null;
        return;
      }
      if (!selected || !visible.some(v => v.mmsi === selected.mmsi)) {
        selected = visible.slice().sort((a, b) => riskProfile(b).total - riskProfile(a).total)[0];
      } else {
        selected = visible.find(v => v.mmsi === selected.mmsi) || selected;
      }
    }

    function formatTime(ms) {
      return new Date(ms).toLocaleString('zh-CN', { hour12: false, timeZone: 'UTC' }) + ' UTC';
    }

    function renderTimeline() {
      const slider = document.getElementById('timeSlider');
      slider.max = Math.max(0, timeSteps.length - 1);
      slider.value = currentStep;
      document.getElementById('currentTimeText').textContent = `当前模拟时间：${formatTime(currentTime())}`;
      const current = activeVessels();
      const high = current.filter(v => riskProfile(v).key === 'high').length;
      document.getElementById('liveStatus').textContent = isPlaying ? `监测中：${current.length} 艘 / 高风险 ${high} 艘` : `已暂停：${current.length} 艘 / 高风险 ${high} 艘`;
      document.getElementById('playBtn').textContent = isPlaying ? '暂停' : '播放';
    }

    function renderAll(fit = false) {
      ensureSelectedVisible();
      renderStats();
      renderList();
      renderDetail();
      renderMap(fit);
      renderTimeline();
    }

    function nextFrame() {
      if (currentStep < timeSteps.length - 1) {
        currentStep += 1;
        renderAll(false);
      } else {
        pauseReplay();
      }
    }

    function prevFrame() {
      currentStep = Math.max(0, currentStep - 1);
      renderAll(false);
    }

    function playReplay() {
      if (isPlaying) return;
      isPlaying = true;
      renderTimeline();
      replayTimer = window.setInterval(nextFrame, PLAY_INTERVAL_MS);
    }

    function pauseReplay() {
      isPlaying = false;
      if (replayTimer) window.clearInterval(replayTimer);
      replayTimer = null;
      renderTimeline();
    }

    function toggleReplay() {
      if (isPlaying) pauseReplay();
      else playReplay();
    }

    document.getElementById('categoryFilter').onchange = () => renderAll(true);
    document.getElementById('reviewFilter').onchange = () => renderAll(true);
    document.getElementById('riskFilter').onchange = () => renderAll(true);
    document.getElementById('fitBtn').onclick = () => renderMap(true);
    document.getElementById('playBtn').onclick = toggleReplay;
    document.getElementById('prevBtn').onclick = () => { pauseReplay(); prevFrame(); };
    document.getElementById('nextBtn').onclick = () => { pauseReplay(); nextFrame(); };
    document.getElementById('timeSlider').oninput = evt => {
      pauseReplay();
      currentStep = Number(evt.target.value) || 0;
      renderAll(false);
    };
    renderAll(true);
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
