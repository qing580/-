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
  <title>Demo7 一小时AIS动态监测模拟版</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <style>
    :root {
      --panel: #ffffff;
      --line: #d8e1ea;
      --text: #142033;
      --muted: #637083;
      --blue: #2368d8;
      --danger: #c53434;
      --amber: #d66a1f;
    }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: "Microsoft YaHei", Arial, sans-serif; color: var(--text); background: #edf3f7; }
    .app { min-height: 100vh; background: #edf3f7; }
    .page { min-height: 100vh; }
    .page.hidden { display: none; }
    .map-wrap { position: relative; height: 100vh; }
    #map { width: 100%; height: 100%; background: #dbe8f2; }
    .toolbar {
      position: absolute; top: 18px; left: 18px; z-index: 900; display: flex; flex-wrap: wrap; gap: 8px;
      background: #fff; border-radius: 8px; padding: 10px; box-shadow: 0 10px 28px rgba(42,66,92,.16);
    }
    select, button { min-height: 36px; border: 1px solid var(--line); border-radius: 7px; background: #fff; padding: 0 10px; font: inherit; }
    button { cursor: pointer; transition: transform .16s ease, box-shadow .16s ease, background .16s ease; }
    button:hover { transform: translateY(-1px); box-shadow: 0 5px 14px rgba(20,32,51,.14); }
    button.primary { background: var(--blue); border-color: var(--blue); color: #fff; }
    button.icon { min-width: 38px; padding: 0 9px; font-weight: 800; }
    button.danger { background: #fff5f5; border-color: #f0b8b8; color: var(--danger); font-weight: 800; }
    button.danger.active { background: var(--danger); border-color: var(--danger); color: #fff; box-shadow: 0 8px 20px rgba(197,52,52,.22); }
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
    .overview-title {
      position: absolute; top: 18px; right: 18px; z-index: 900; width: min(360px, calc(100vw - 36px));
      background: rgba(255,255,255,.96); border: 1px solid var(--line); border-radius: 8px; padding: 13px 14px;
      box-shadow: 0 10px 28px rgba(42,66,92,.16);
    }
    .overview-title h1 { margin: 0 0 6px; font-size: 20px; letter-spacing: 0; }
    .overview-title p { margin: 0; color: var(--muted); font-size: 12px; line-height: 1.5; }
    .overview-stats {
      position: absolute; right: 18px; bottom: 88px; z-index: 900; display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px;
      width: min(360px, calc(100vw - 36px));
    }
    .overview-stat { border: 1px solid var(--line); border-radius: 8px; background: rgba(255,255,255,.96); padding: 9px 10px; box-shadow: 0 8px 22px rgba(42,66,92,.12); }
    .overview-stat b { display: block; font-size: 20px; color: #102542; }
    .overview-stat span { color: var(--muted); font-size: 12px; }
    .alarm-toast {
      position: absolute; top: 104px; right: 18px; z-index: 930; width: min(360px, calc(100vw - 36px));
      border-radius: 8px; border: 1px solid #ebb2b2; background: rgba(255,248,248,.98); color: #3b1720;
      box-shadow: 0 14px 34px rgba(80,28,28,.22); padding: 12px; display: none;
    }
    .alarm-toast.show { display: block; animation: toastIn .22s ease-out; }
    .alarm-top { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 6px; }
    .alarm-title { font-weight: 900; color: var(--danger); }
    .alarm-close { width: 28px; min-width: 28px; min-height: 28px; padding: 0; border-radius: 999px; color: #8a2b2b; }
    .alarm-text { font-size: 12px; line-height: 1.55; color: #553036; }
    .alarm-action { margin-top: 9px; width: 100%; background: var(--danger); color: #fff; border-color: var(--danger); font-weight: 800; }
    .alarm-log-toggle {
      position: absolute; right: 18px; bottom: 208px; z-index: 920; min-width: 132px;
      background: #102542; border-color: #102542; color: #fff; font-weight: 800;
      box-shadow: 0 10px 24px rgba(16,37,66,.22);
    }
    .alarm-log-panel {
      position: absolute; right: 18px; top: 250px; bottom: 268px; z-index: 925; width: min(380px, calc(100vw - 36px));
      border: 1px solid #d6e0ea; border-radius: 8px; background: rgba(255,255,255,.98);
      box-shadow: 0 18px 42px rgba(32,52,78,.22); display: none; overflow: hidden;
    }
    .alarm-log-panel.open { display: grid; grid-template-rows: auto 1fr; }
    .alarm-log-head { display: flex; justify-content: space-between; gap: 10px; align-items: center; padding: 10px 12px; border-bottom: 1px solid #e1e8f0; }
    .alarm-log-head b { color: #102542; }
    .alarm-log-close { width: 28px; min-width: 28px; min-height: 28px; padding: 0; border-radius: 999px; }
    .alarm-log-list { overflow: auto; padding: 10px; display: grid; gap: 8px; align-content: start; }
    .alarm-record { border: 1px solid #ecd0d0; border-left: 4px solid var(--danger); border-radius: 8px; padding: 9px; background: #fffafa; }
    .alarm-record-top { display: flex; justify-content: space-between; gap: 8px; color: #26364f; font-size: 12px; margin-bottom: 5px; }
    .alarm-record-name { font-weight: 900; color: #102542; overflow-wrap: anywhere; }
    .alarm-record-score { color: var(--danger); font-weight: 900; white-space: nowrap; }
    .alarm-record-meta { color: #637083; font-size: 12px; line-height: 1.45; }
    .alarm-record button { width: 100%; margin-top: 7px; color: var(--danger); border-color: #efc4c4; background: #fff; font-weight: 800; }
    .alarm-empty { color: var(--muted); font-size: 12px; line-height: 1.6; padding: 6px 2px; }
    @keyframes toastIn {
      from { opacity: 0; transform: translateY(-6px); }
      to { opacity: 1; transform: translateY(0); }
    }
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
    .ship-marker svg { display: block; width: 30px; height: 22px; filter: drop-shadow(0 2px 3px rgba(15, 32, 52, .32)); transition: transform .16s ease, width .16s ease, height .16s ease; }
    .ship-marker.selected { z-index: 760 !important; }
    .ship-marker.selected svg { width: 52px; height: 38px; transform-origin: center; }
    .risk-marker { position: relative; width: 88px; height: 46px; display: flex; align-items: center; justify-content: center; pointer-events: auto; }
    .risk-marker .ship-wrap { position: relative; z-index: 2; }
    .risk-marker:hover .ship-wrap { transform: scale(1.14); }
    .risk-halo { position: absolute; left: 50%; top: 50%; width: 34px; height: 34px; border-radius: 50%; transform: translate(-50%, -50%); opacity: .82; }
    .risk-marker.risk-low .risk-halo { display: none; }
    .risk-marker.risk-medium .risk-halo { border: 2px solid rgba(199,139,17,.65); background: rgba(199,139,17,.10); }
    .risk-marker.risk-elevated .risk-halo { width: 40px; height: 40px; border: 2px solid rgba(214,106,31,.82); background: rgba(214,106,31,.16); box-shadow: 0 0 14px rgba(214,106,31,.45); }
    .risk-marker.risk-high .risk-halo { width: 44px; height: 44px; border: 2px solid rgba(197,52,52,.94); background: rgba(197,52,52,.18); box-shadow: 0 0 18px rgba(197,52,52,.62); animation: alarmPulse 1.15s ease-out infinite; }
    .risk-marker.selected .risk-halo { width: 64px; height: 64px; }
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
    .detail-page { background: #eef4f8; }
    .detail-shell { min-height: 100vh; display: grid; grid-template-rows: auto 1fr; }
    .detail-top {
      display: flex; justify-content: space-between; gap: 14px; align-items: center; padding: 16px 22px;
      background: #fff; border-bottom: 1px solid var(--line);
    }
    .detail-top-main { min-width: 0; }
    .detail-title { margin: 0 0 5px; font-size: 22px; letter-spacing: 0; }
    .detail-sub { margin: 0; color: var(--muted); font-size: 13px; line-height: 1.45; }
    .back-btn { min-width: 92px; background: #102542; border-color: #102542; color: #fff; }
    .detail-layout { display: grid; grid-template-columns: minmax(280px, 360px) 1fr; gap: 14px; padding: 14px; min-height: 0; }
    .detail-side, .detail-main { min-height: 0; }
    .info-panel, .detail-box { border: 1px solid var(--line); border-radius: 8px; background: #fff; padding: 14px; }
    .info-panel { display: grid; gap: 12px; align-content: start; }
    h1 { margin: 0 0 6px; font-size: 22px; letter-spacing: 0; }
    .sub { margin: 0; color: var(--muted); font-size: 13px; line-height: 1.55; }
    .tag { display: inline-block; margin-top: 8px; color: #174ea6; background: #edf4ff; border: 1px solid #b9d1ff; border-radius: 999px; padding: 4px 9px; font-size: 12px; }
    .stats { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; }
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
    .detail-main { overflow: auto; }
    .detail-box { font-size: 13px; line-height: 1.6; min-height: calc(100vh - 112px); }
    .detail-box b { color: #0b2545; }
    .selected-ship-preview { display: flex; justify-content: center; align-items: center; min-height: 84px; border: 1px solid #dbe6ef; border-radius: 8px; background: #f8fbfe; }
    .selected-ship-preview svg { width: 156px; height: 112px; filter: drop-shadow(0 5px 10px rgba(15, 32, 52, .22)); }
    .detail-facts { display: grid; gap: 8px; color: #33445f; font-size: 13px; line-height: 1.5; }
    .fact-row { display: flex; justify-content: space-between; gap: 12px; border-bottom: 1px solid #edf1f5; padding-bottom: 7px; }
    .fact-row span:first-child { color: var(--muted); }
    .fact-row span:last-child { text-align: right; font-weight: 700; color: #102542; overflow-wrap: anywhere; }
    .risk-head { display: grid; grid-template-columns: 1fr auto; gap: 10px; align-items: start; margin-bottom: 12px; }
    .risk-title { margin: 0; font-size: 15px; font-weight: 800; color: #0b2545; overflow-wrap: anywhere; }
    .risk-meta { margin-top: 4px; color: var(--muted); font-size: 12px; line-height: 1.45; }
    .score-badge { min-width: 86px; border-radius: 8px; padding: 8px 9px; color: #fff; text-align: center; box-shadow: inset 0 -1px 0 rgba(0,0,0,.12); }
    .score-badge b { display: block; color: #fff; font-size: 22px; line-height: 1; }
    .score-badge span { font-size: 12px; }
    .risk-summary { border: 1px solid #dbe6ef; background: #f7fbff; border-radius: 8px; padding: 10px; margin: 10px 0 12px; color: #203047; }
    .risk-grid { display: grid; gap: 8px; margin-top: 8px; }
    .metric { border: 1px solid var(--line); border-radius: 8px; padding: 8px 9px; background: #fff; }
    .metric.expandable { cursor: pointer; }
    .metric.expandable:hover { border-color: #b9d1ff; box-shadow: 0 4px 12px rgba(35,104,216,.08); }
    .metric-detail { display: none; margin-top: 7px; padding-top: 7px; border-top: 1px dashed #d5dee8; color: #4b5d76; font-size: 12px; line-height: 1.5; }
    .metric.open .metric-detail { display: block; }
    .metric-top { display: flex; justify-content: space-between; gap: 8px; font-size: 12px; color: #26364f; }
    .metric-name { font-weight: 700; }
    .metric-score { color: var(--muted); white-space: nowrap; }
    .bar { height: 7px; background: #e9eef4; border-radius: 99px; overflow: hidden; margin-top: 6px; }
    .bar-fill { height: 100%; border-radius: 99px; }
    .explain { margin: 12px 0 0; padding-left: 18px; color: #304158; }
    .explain li { margin: 4px 0; }
    .advice { margin-top: 10px; border-left: 4px solid var(--blue); background: #f3f7fc; padding: 9px 10px; border-radius: 6px; color: #22334f; }
    .formula { margin-top: 10px; color: var(--muted); font-size: 12px; line-height: 1.45; }
    .agent-flow { display: grid; gap: 8px; margin: 10px 0 12px; }
    .agent-step { border: 1px solid #d8e3ef; border-radius: 8px; background: #fbfdff; padding: 9px 10px; }
    .agent-step-top { display: flex; justify-content: space-between; gap: 8px; align-items: center; margin-bottom: 4px; }
    .agent-step-name { font-weight: 800; color: #102542; }
    .agent-step-tag { border-radius: 999px; padding: 2px 7px; font-size: 11px; color: #174ea6; background: #edf4ff; border: 1px solid #c5d8ff; white-space: nowrap; }
    .agent-step-text { color: #33445f; font-size: 12px; line-height: 1.5; }
    .agent-conclusion { border: 1px solid #cbdff5; background: linear-gradient(180deg, #f7fbff 0%, #eef6ff 100%); border-radius: 8px; padding: 10px; margin: 10px 0 12px; color: #203047; }
    .agent-conclusion-title { font-weight: 800; color: #0b2545; margin-bottom: 4px; }
    .leaflet-popup-content { font-family: "Microsoft YaHei", Arial, sans-serif; line-height: 1.55; }
    @media (max-width: 980px) {
      .map-wrap { height: 100vh; }
      .time-panel { grid-template-columns: 1fr; left: 10px; right: 10px; bottom: 10px; }
      .legend, .overview-title, .overview-stats, .alarm-toast, .alarm-log-toggle, .alarm-log-panel { display: none; }
      .detail-layout { grid-template-columns: 1fr; }
      .detail-top { align-items: flex-start; }
    }
  </style>
</head>
<body>
  <div class="app">
    <main id="overviewPage" class="page map-wrap">
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
        <button id="highRiskBtn" class="danger">高风险聚焦</button>
        <button id="fitBtn" class="primary">适配全图</button>
      </div>
      <div id="map"></div>
      <div class="overview-title">
        <h1>马六甲海峡AIS动态监测</h1>
        <p>总览页只展示船舶位置、船型图标和风险颜色。点击任意船舶进入单船智能体分析页。</p>
      </div>
      <div id="alarmToast" class="alarm-toast">
        <div class="alarm-top">
          <span class="alarm-title">高风险船舶预警</span>
          <button id="alarmCloseBtn" class="alarm-close" aria-label="关闭预警">×</button>
        </div>
        <div id="alarmText" class="alarm-text"></div>
        <button id="alarmActionBtn" class="alarm-action">查看智能体报告</button>
      </div>
      <button id="alarmLogBtn" class="alarm-log-toggle">预警记录 0</button>
      <div id="alarmLogPanel" class="alarm-log-panel">
        <div class="alarm-log-head">
          <b>本次播放预警记录</b>
          <button id="alarmLogCloseBtn" class="alarm-log-close" aria-label="关闭预警记录">×</button>
        </div>
        <div id="alarmLogList" class="alarm-log-list"></div>
      </div>
      <div class="legend" id="legend"></div>
      <div class="overview-stats">
        <div class="overview-stat"><b id="totalShips">0</b><span>当前船舶</span></div>
        <div class="overview-stat"><b id="knownShips">0</b><span>已分类</span></div>
        <div class="overview-stat"><b id="unknownShips">0</b><span>高风险</span></div>
      </div>
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
    <section id="detailPage" class="page detail-page hidden">
      <div class="detail-shell">
        <header class="detail-top">
          <div class="detail-top-main">
            <h1 class="detail-title">单船智能体分析报告</h1>
            <p class="detail-sub">点击“返回总览”回到地图；详情页集中展示风险等级、综合分、AHP分解和 LangGraph 节点流程。</p>
          </div>
          <button id="backBtn" class="back-btn">返回总览</button>
        </header>
        <div class="detail-layout">
          <aside class="detail-side">
            <div class="info-panel">
              <h2 class="section-title">船舶画像</h2>
              <div id="selectedShipPreview" class="selected-ship-preview"></div>
              <div id="selectedShipFacts" class="detail-facts"></div>
            </div>
          </aside>
          <main class="detail-main">
            <h2 class="section-title">LangGraph智能体分析报告</h2>
            <div id="detailBox" class="detail-box"></div>
          </main>
        </div>
      </div>
    </section>
    <div id="vesselList" hidden></div>
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
    let alarmTargetMmsi = null;
    let dismissedAlarmMmsi = null;
    let alarmLogOpen = false;
    const alarmRecords = new Map();
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
      const width = selectedIcon ? 52 : 30;
      const height = selectedIcon ? 38 : 22;
      const scale = selectedIcon ? 1.18 : 1;
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
          line.on('click', () => openVesselDetail(v.mmsi, false));
          layers.push(line);
          latlngs.forEach(p => bounds.push(p));
        }
        if (latlngs.length > 0) {
          const last = latlngs[latlngs.length - 1];
          const marker = L.marker(last, { icon: vesselIcon(v), riseOnHover: true }).addTo(map);
          marker.bindPopup(popupHtml(v));
          marker.on('click', () => openVesselDetail(v.mmsi, false));
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
      const trackShips = document.getElementById('trackShips');
      const cargoShips = document.getElementById('cargoShips');
      const tankerShips = document.getElementById('tankerShips');
      if (trackShips) trackShips.textContent = pointCount;
      if (cargoShips) cargoShips.textContent = counts['货船'] || 0;
      if (tankerShips) tankerShips.textContent = counts['油轮'] || 0;
      document.getElementById('unknownShips').textContent = highRiskCount;
      const highRiskBtn = document.getElementById('highRiskBtn');
      if (highRiskBtn) {
        const focused = document.getElementById('riskFilter').value === '高风险';
        highRiskBtn.classList.toggle('active', focused);
        highRiskBtn.textContent = focused ? '显示全部风险' : '高风险聚焦';
      }
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
      if (!wrap) return;
      wrap.innerHTML = '';
      visibleVessels().forEach(v => {
        const risk = riskProfile(v);
        const card = document.createElement('div');
        card.className = 'vessel-card' + (selected && selected.mmsi === v.mmsi ? ' active' : '');
        card.innerHTML = `<div class="card-top"><div class="card-title">${v.name}</div><span class="badge" style="background:${COLORS[v.category]}">${v.category}</span></div>
          <div class="meta">MMSI：${v.mmsi}<br>风险：<b style="color:${risk.color}">${risk.level} ${risk.total}分</b> | 轨迹点：${v.points.length} | 平均速度：${formatValue(v.avg_sog, '节')}</div>`;
        card.onclick = () => openVesselDetail(v.mmsi, true);
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

    function agentWorkflow(v, risk) {
      const avgSog = numberOr(v.avg_sog, NaN);
      const pointCount = v.points.length || numberOr(v.point_count, 0);
      const dataQuality = risk.items.find(item => item.key === 'credibility')?.score ?? 0;
      const behaviorScore = risk.items.find(item => item.key === 'behavior')?.score ?? 0;
      const encounterScore = risk.items.find(item => item.key === 'encounter')?.score ?? 0;
      const dlConfidence = numberOr(v.dl_confidence, NaN);
      const dlText = v.dl_predicted_category
        ? `深度学习原型判断为${v.dl_predicted_category}${Number.isFinite(dlConfidence) ? `，置信度 ${(dlConfidence * 100).toFixed(1)}%` : ''}；融合结论为${v.fusion_category || v.category}。`
        : '当前未接入深度学习分类结果，使用规则分类结果。';
      const dlRiskConfidence = numberOr(v.dl_risk_confidence, NaN);
      const dlRiskText = v.dl_predicted_risk_level
        ? `Risk-MLP 预测为${v.dl_predicted_risk_level}${Number.isFinite(dlRiskConfidence) ? `，置信度 ${(dlRiskConfidence * 100).toFixed(1)}%` : ''}；融合风险等级为${v.fusion_risk_level || risk.level}。`
        : '当前未接入深度学习风险预测结果，使用 AHP 风险等级。';
      const speedText = Number.isFinite(avgSog) ? `${avgSog.toFixed(1)} 节` : '缺失';
      const reviewText = String(v.need_review || '').includes('是') || String(v.need_review || '').includes('建议')
        ? '建议进入人工复核池'
        : '暂不需要人工复核';
      const alarmText = risk.key === 'high'
        ? '触发重点预警，地图端用红色脉冲图标提示，点击图标可显示分数。'
        : risk.key === 'elevated'
          ? '进入重点观察队列，建议继续跟踪后续轨迹。'
          : '保持常规监测，等待更多 AIS 数据更新。';
      return [
        {
          name: '节点1 数据感知',
          tag: 'AIS输入',
          text: `读取 ${pointCount} 个轨迹点，最近速度 ${speedText}，近邻船舶 ${risk.near} 艘。`
        },
        {
          name: '节点2 船舶分类',
          tag: v.confidence || '分类结果',
          text: `规则识别为${v.category}${v.broad_category ? `，归入${v.broad_category}` : ''}；${dlText}`
        },
        {
          name: '节点3 AHP风险评分',
          tag: `${risk.total} / 100`,
          text: `按 AHP 权重融合行为异常、会遇风险、水域环境、船型后果和数据可信度；行为分 ${behaviorScore}，会遇分 ${encounterScore}，数据可信度风险分 ${dataQuality}。`
        },
        {
          name: '节点4 深度学习风险预测',
          tag: v.dl_predicted_risk_level || risk.level,
          text: dlRiskText
        },
        {
          name: '节点5 融合预警报告',
          tag: risk.level,
          text: `${alarmText}${reviewText}。`
        }
      ];
    }

    function agentConclusion(v, risk) {
      const lead = risk.key === 'high'
        ? '该船当前处于重点预警状态'
        : risk.key === 'elevated'
          ? '该船当前处于较高关注状态'
          : risk.key === 'medium'
            ? '该船当前处于持续观察状态'
            : '该船当前处于常规监测状态';
      const dlPart = v.dl_predicted_category ? ` 船舶分类模型给出“${v.dl_predicted_category}”判断，融合分类为“${v.fusion_category || v.category}”。` : '';
      const riskPart = v.dl_predicted_risk_level ? ` 风险预测模型给出“${v.dl_predicted_risk_level}”判断，融合风险等级为“${v.fusion_risk_level || risk.level}”。` : '';
      return `${lead}。智能体判断主要受船型类别、当前位置附近船舶密度、平均航速、轨迹点数量和 AIS 静态信息完整度影响。${dlPart}${riskPart}`;
    }

    function metricDetail(item, v, risk) {
      const avgSog = numberOr(v.avg_sog, NaN);
      const pointCount = v.points.length || numberOr(v.point_count, 0);
      const details = {
        behavior: Number.isFinite(avgSog)
          ? `该维度主要看速度状态和轨迹点数量。当前平均速度 ${avgSog.toFixed(1)} 节，轨迹点 ${pointCount} 个；低速停留、高速通过或轨迹过少都会提高行为异常分。`
          : `该维度主要看速度状态和轨迹点数量。当前速度信息缺失，系统会把它作为不确定风险处理。`,
        encounter: `该维度主要看近距离船舶数量。当前约 3 公里范围内有 ${risk.near} 艘船，周边船越多，会遇和碰撞风险越高。`,
        environment: `该维度考虑马六甲海峡东南入口/新加坡海峡附近航道密集、通航空间有限，因此基础环境风险较高。`,
        consequence: `该维度考虑船型后果。油轮、货船、客船等一旦发生事故，可能造成能源运输、货物运输或人员安全影响，因此分值更高。`,
        credibility: `该维度反映 AIS 信息完整度。船名、船型码、轨迹点越少，系统越难确认身份和行为，可信度风险越高。`
      };
      return details[item.key] || '该维度由 AHP 权重体系参与综合风险分计算。';
    }

    function renderDetail() {
      const v = selected;
      if (!v || !v.points || !v.points.length) {
        document.getElementById('detailBox').innerHTML = '当前模拟时间内还没有可分析的船舶。点击播放后，LangGraph智能体会按“数据感知-船舶分类-风险推理-报告生成”的流程生成分析报告。';
        renderSelectedShipFacts(null, null);
        return;
      }
      const risk = riskProfile(v);
      renderSelectedShipFacts(v, risk);
      const agentSteps = agentWorkflow(v, risk).map(step => `
        <div class="agent-step">
          <div class="agent-step-top">
            <span class="agent-step-name">${step.name}</span>
            <span class="agent-step-tag">${step.tag}</span>
          </div>
          <div class="agent-step-text">${step.text}</div>
        </div>`).join('');
      const rows = risk.items.map(item => `
        <div class="metric expandable" onclick="this.classList.toggle('open')">
          <div class="metric-top">
            <span class="metric-name">${item.name}</span>
            <span class="metric-score">${item.score}分 × ${(item.weight * 100).toFixed(2)}% = ${item.contribution}分</span>
          </div>
          <div class="bar"><div class="bar-fill" style="width:${item.score}%;background:${risk.color}"></div></div>
          <div class="metric-detail">${metricDetail(item, v, risk)}</div>
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
          <b>深度学习分类：</b>${v.dl_predicted_category || '暂无'}${Number.isFinite(numberOr(v.dl_confidence, NaN)) ? `，置信度 ${(numberOr(v.dl_confidence) * 100).toFixed(1)}%` : ''}；融合结论：${v.fusion_category || v.category || '暂无'}<br>
          <b>深度学习风险：</b>${v.dl_predicted_risk_level || '暂无'}${Number.isFinite(numberOr(v.dl_risk_confidence, NaN)) ? `，置信度 ${(numberOr(v.dl_risk_confidence) * 100).toFixed(1)}%` : ''}；融合风险：${v.fusion_risk_level || risk.level || '暂无'}<br>
          <b>数据状态：</b>${v.confidence || '未标注'}，${v.need_review || '暂无'}。
        </div>
        <div class="agent-conclusion">
          <div class="agent-conclusion-title">智能体综合结论</div>
          ${agentConclusion(v, risk)}
        </div>
        <b>LangGraph 节点流程</b>
        <div class="agent-flow">${agentSteps}</div>
        <b>AHP 指标分解</b>
        <div class="risk-grid">${rows}</div>
        <ul class="explain">${reasons}</ul>
        <div class="advice"><b>处置建议：</b>${risk.advice}</div>
        <div class="formula">智能体框架：采用 LangGraph 思路组织为“数据感知 → 船舶分类 → 风险推理 → 报告生成”四个节点。计算方法：综合风险分 = Σ（维度得分 × AHP 权重）。当前为演示版规则评分，后续可接入专家问卷和更多历史轨迹数据修正。</div>`;
    }

    function renderSelectedShipFacts(v, risk) {
      const preview = document.getElementById('selectedShipPreview');
      const facts = document.getElementById('selectedShipFacts');
      if (!preview || !facts) return;
      if (!v || !risk) {
        preview.innerHTML = '';
        facts.innerHTML = '<div class="fact-row"><span>状态</span><span>等待选择船舶</span></div>';
        return;
      }
      const last = v.points[v.points.length - 1] || {};
      preview.innerHTML = shipSvg(v.category, risk.color, 90, true);
      facts.innerHTML = `
        <div class="fact-row"><span>船名</span><span>${v.name}</span></div>
        <div class="fact-row"><span>MMSI</span><span>${v.mmsi}</span></div>
        <div class="fact-row"><span>船型</span><span>${v.category}</span></div>
        <div class="fact-row"><span>DL分类</span><span>${v.dl_predicted_category || '暂无'}</span></div>
        <div class="fact-row"><span>融合结论</span><span>${v.fusion_category || v.category}</span></div>
        <div class="fact-row"><span>DL风险</span><span>${v.dl_predicted_risk_level || '暂无'}</span></div>
        <div class="fact-row"><span>风险置信度</span><span>${Number.isFinite(numberOr(v.dl_risk_confidence, NaN)) ? `${(numberOr(v.dl_risk_confidence) * 100).toFixed(1)}%` : '暂无'}</span></div>
        <div class="fact-row"><span>风险等级</span><span style="color:${risk.color}">${risk.level}</span></div>
        <div class="fact-row"><span>综合分</span><span>${risk.total} / 100</span></div>
        <div class="fact-row"><span>纬度</span><span>${formatValue(last.lat, '')}</span></div>
        <div class="fact-row"><span>经度</span><span>${formatValue(last.lon, '')}</span></div>
        <div class="fact-row"><span>平均速度</span><span>${formatValue(v.avg_sog, '节')}</span></div>`;
    }

    function showOverviewPage() {
      document.getElementById('overviewPage').classList.remove('hidden');
      document.getElementById('detailPage').classList.add('hidden');
      renderAlarmToast();
      setTimeout(() => map.invalidateSize(), 40);
    }

    function showDetailPage() {
      document.getElementById('overviewPage').classList.add('hidden');
      document.getElementById('detailPage').classList.remove('hidden');
      document.getElementById('alarmToast').classList.remove('show');
      window.scrollTo({ top: 0, behavior: 'auto' });
    }

    function openVesselDetail(mmsi, pan) {
      selectVessel(mmsi, pan);
      window.setTimeout(showDetailPage, 180);
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

    function renderAlarmToast() {
      const toast = document.getElementById('alarmToast');
      const text = document.getElementById('alarmText');
      const high = activeVessels()
        .map(v => ({ vessel: v, risk: riskProfile(v) }))
        .filter(item => item.risk.key === 'high')
        .sort((a, b) => b.risk.total - a.risk.total)[0];
      if (high) addAlarmRecord(high.vessel, high.risk);
      renderAlarmLog();
      if (!toast || !text || document.getElementById('overviewPage').classList.contains('hidden')) return;
      if (!high || dismissedAlarmMmsi === String(high.vessel.mmsi)) {
        alarmTargetMmsi = null;
        toast.classList.remove('show');
        return;
      }
      alarmTargetMmsi = high.vessel.mmsi;
      text.innerHTML = `发现 <b>${high.vessel.name}</b>，MMSI：${high.vessel.mmsi}，综合风险 <b style="color:${high.risk.color}">${high.risk.total}分</b>。建议立即查看智能体分析报告。`;
      toast.classList.add('show');
    }

    function addAlarmRecord(v, risk) {
      const key = String(v.mmsi);
      const existed = alarmRecords.get(key);
      if (existed && existed.score >= risk.total) return;
      alarmRecords.set(key, {
        mmsi: key,
        name: v.name,
        category: v.category,
        score: risk.total,
        level: risk.level,
        color: risk.color,
        time: formatTime(currentTime())
      });
    }

    function renderAlarmLog() {
      const btn = document.getElementById('alarmLogBtn');
      const panel = document.getElementById('alarmLogPanel');
      const list = document.getElementById('alarmLogList');
      if (!btn || !panel || !list) return;
      const records = Array.from(alarmRecords.values()).sort((a, b) => b.score - a.score);
      btn.textContent = `预警记录 ${records.length}`;
      panel.classList.toggle('open', alarmLogOpen);
      if (!records.length) {
        list.innerHTML = '<div class="alarm-empty">播放过程中出现的高风险船舶会记录在这里。即使右上角弹窗被新预警覆盖，这里也不会丢。</div>';
        return;
      }
      list.innerHTML = records.map(item => `
        <div class="alarm-record">
          <div class="alarm-record-top">
            <span class="alarm-record-name">${item.name}</span>
            <span class="alarm-record-score">${item.score}分</span>
          </div>
          <div class="alarm-record-meta">MMSI：${item.mmsi}<br>船型：${item.category} | ${item.level}<br>首次/最高预警时间：${item.time}</div>
          <button data-mmsi="${item.mmsi}">查看报告</button>
        </div>`).join('');
      list.querySelectorAll('button[data-mmsi]').forEach(btn => {
        btn.onclick = () => openVesselDetail(btn.dataset.mmsi, false);
      });
    }

    function renderAll(fit = false) {
      ensureSelectedVisible();
      renderStats();
      renderList();
      renderDetail();
      renderMap(fit);
      renderTimeline();
      renderAlarmToast();
      renderAlarmLog();
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

    function toggleHighRiskFocus() {
      const riskFilter = document.getElementById('riskFilter');
      riskFilter.value = riskFilter.value === '高风险' ? '全部' : '高风险';
      renderAll(true);
    }

    document.getElementById('categoryFilter').onchange = () => renderAll(true);
    document.getElementById('reviewFilter').onchange = () => renderAll(true);
    document.getElementById('riskFilter').onchange = () => renderAll(true);
    document.getElementById('highRiskBtn').onclick = toggleHighRiskFocus;
    document.getElementById('fitBtn').onclick = () => renderMap(true);
    document.getElementById('backBtn').onclick = showOverviewPage;
    document.getElementById('alarmCloseBtn').onclick = () => {
      dismissedAlarmMmsi = alarmTargetMmsi ? String(alarmTargetMmsi) : null;
      document.getElementById('alarmToast').classList.remove('show');
    };
    document.getElementById('alarmActionBtn').onclick = () => {
      if (alarmTargetMmsi) openVesselDetail(alarmTargetMmsi, false);
    };
    document.getElementById('alarmLogBtn').onclick = () => {
      alarmLogOpen = !alarmLogOpen;
      renderAlarmLog();
    };
    document.getElementById('alarmLogCloseBtn').onclick = () => {
      alarmLogOpen = false;
      renderAlarmLog();
    };
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
