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
    .side { height: 100vh; background: var(--panel); border-left: 1px solid var(--line); display: grid; grid-template-rows: auto auto minmax(260px,1fr) 270px; }
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
    .leaflet-popup-content { font-family: "Microsoft YaHei", Arial, sans-serif; line-height: 1.55; }
    @media (max-width: 980px) {
      .app { grid-template-columns: 1fr; grid-template-rows: 58vh auto; }
      .map-wrap { height: 58vh; }
      .side { height: auto; min-height: 42vh; grid-template-rows: auto auto 280px 300px; border-left: 0; border-top: 1px solid var(--line); }
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
        <p class="sub">基于马六甲海峡 / 新加坡海峡 10 分钟 AIS 数据，在真实在线地图底图上展示船型分类、筛选、统计和分类依据。</p>
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
        <h2 class="section-title">分类依据</h2>
        <div id="detailBox" class="detail-box"></div>
      </section>
    </aside>
  </div>
  <script>
    const DATA = __DATA__;
    const COLORS = { "货船": "#2368d8", "油轮": "#d98210", "渔船": "#27875d", "其他": "#6e56cf", "未知": "#8a96a3" };
    const ORDER = ["货船", "油轮", "渔船", "其他", "未知"];
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
      return `<b>${v.name}</b><br>MMSI：${v.mmsi}<br>船型：${v.category}<br>置信度：${v.confidence || '未标注'}<br>依据：${v.reason || '暂无'}`;
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
        const card = document.createElement('div');
        card.className = 'vessel-card' + (selected.mmsi === v.mmsi ? ' active' : '');
        card.innerHTML = `<div class="card-top"><div class="card-title">${v.name}</div><span class="badge" style="background:${COLORS[v.category]}">${v.category}</span></div>
          <div class="meta">MMSI：${v.mmsi}<br>置信度：${v.confidence || '未标注'} | 轨迹点：${v.points.length} | 平均速度：${v.avg_sog ?? '暂无'}</div>`;
        card.onclick = () => selectVessel(v.mmsi, true);
        wrap.appendChild(card);
      });
    }

    function renderDetail() {
      const v = selected;
      document.getElementById('detailBox').innerHTML = `
        <b>船舶 MMSI：</b>${v.mmsi}<br>
        <b>船名：</b>${v.name}<br>
        <b>分类结果：</b><span style="color:${COLORS[v.category]};font-weight:700">${v.category}</span><br>
        <b>AIS 船型码：</b>${v.vessel_type || '暂无'}<br>
        <b>置信度：</b>${v.confidence || '未标注'}<br>
        <b>分类来源：</b>${v.source || '暂无'}<br>
        <b>分类依据：</b>${v.reason || '暂无'}<br>
        <b>是否需要人工复核：</b>${v.need_review || '暂无'}<br><br>
        <b>智能体说明：</b>系统先读取 AIS 船型码，如果缺少船型码，就查询人工补全表；仍然缺少时才标为未知。船舶分类结果后续会影响异常解释，例如油轮异常停留的风险权重可以高于普通货船。`;
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

    document.getElementById('categoryFilter').onchange = () => { renderList(); renderMap(true); };
    document.getElementById('reviewFilter').onchange = () => { renderList(); renderMap(true); };
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
