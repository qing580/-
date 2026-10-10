"""Build an offline Demo6 page focused on vessel classification."""

from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AIS_CSV = ROOT / "data_raw" / "ais_malacca_10min.csv"
CLASS_CSV = ROOT / "results" / "tables" / "malacca_vessel_classification_10min.csv"
DEMO_DIR = ROOT / "frontend" / "demo"
OUT_HTML = DEMO_DIR / "demo_map_v6_vessel_classification.html"

CATEGORY_COLORS = {
    "货船": "#2368d8",
    "油轮": "#d98210",
    "渔船": "#27875d",
    "其他": "#6e56cf",
    "未知": "#8a96a3",
}
CATEGORY_ORDER = ["货船", "油轮", "渔船", "其他", "未知"]


def safe_float(value: str | None, default: float | None = None) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return default
        number = float(value)
        if math.isnan(number) or math.isinf(number):
            return default
        return number
    except ValueError:
        return default


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def build_data() -> dict:
    classifications = read_csv(CLASS_CSV)
    by_mmsi = {str(row["mmsi"]): row for row in classifications}
    positions: dict[str, list[dict]] = defaultdict(list)

    for row in read_csv(AIS_CSV):
        if row.get("message_type") != "PositionReport":
            continue
        lat = safe_float(row.get("lat"))
        lon = safe_float(row.get("lon"))
        if lat is None or lon is None:
            continue
        mmsi = str(row.get("mmsi", "")).strip()
        positions[mmsi].append(
            {
                "time": row.get("received_at", ""),
                "lat": lat,
                "lon": lon,
                "sog": safe_float(row.get("sog"), 0),
                "cog": safe_float(row.get("cog"), 0),
                "heading": safe_float(row.get("heading"), 0),
            }
        )

    vessels = []
    for row in classifications:
        mmsi = str(row["mmsi"]).strip()
        pts = positions.get(mmsi, [])
        category = row.get("vessel_category", "未知") or "未知"
        vessels.append(
            {
                "mmsi": mmsi,
                "name": (row.get("vessel_name") or "未获取船名").strip() or "未获取船名",
                "category": category,
                "confidence": row.get("confidence", ""),
                "source": row.get("classification_source", ""),
                "reason": row.get("classification_reason", ""),
                "need_review": row.get("need_manual_review", ""),
                "point_count": int(safe_float(row.get("point_count"), 0) or 0),
                "avg_sog": safe_float(row.get("avg_sog"), None),
                "vessel_type": row.get("raw_vessel_type", ""),
                "points": pts,
            }
        )

    counts = {cat: 0 for cat in CATEGORY_ORDER}
    for vessel in vessels:
        counts[vessel["category"]] = counts.get(vessel["category"], 0) + 1

    return {
        "vessels": vessels,
        "stats": {
            "total": len(vessels),
            "known": sum(1 for v in vessels if v["category"] != "未知"),
            "position_rows": sum(len(v["points"]) for v in vessels),
            "with_track": sum(1 for v in vessels if v["points"]),
            "counts": counts,
        },
    }


HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Demo6 船舶分类增强版</title>
  <style>
    :root {
      --panel: #ffffff;
      --line: #d8e1ea;
      --text: #142033;
      --muted: #637083;
      --sea: #e8f4fb;
      --blue: #2368d8;
    }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: "Microsoft YaHei", Arial, sans-serif; color: var(--text); background: #edf3f7; }
    .app { min-height: 100vh; display: grid; grid-template-columns: 1fr 440px; }
    .map-wrap { position: relative; height: 100vh; background: var(--sea); overflow: hidden; }
    svg { width: 100%; height: 100%; display: block; background: linear-gradient(#eaf7fe, #dceef8); }
    .toolbar {
      position: absolute; top: 18px; left: 18px; z-index: 10; display: flex; flex-wrap: wrap; gap: 8px;
      background: #fff; border-radius: 8px; padding: 10px; box-shadow: 0 10px 28px rgba(42,66,92,.16);
    }
    select, button { min-height: 36px; border: 1px solid var(--line); border-radius: 7px; background: #fff; padding: 0 10px; font: inherit; }
    button { cursor: pointer; }
    button.primary { background: var(--blue); border-color: var(--blue); color: #fff; }
    .legend {
      position: absolute; left: 18px; bottom: 18px; z-index: 10; background: #fff; border: 1px solid var(--line);
      border-radius: 8px; padding: 10px 12px; font-size: 12px; line-height: 1.8; color: var(--muted);
      box-shadow: 0 8px 22px rgba(42,66,92,.12);
    }
    .dot { display: inline-block; width: 11px; height: 11px; border-radius: 50%; margin-right: 5px; vertical-align: -1px; }
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
    .tip {
      position: absolute; z-index: 12; display: none; max-width: 280px; background: #fff; border: 1px solid var(--line);
      border-radius: 8px; padding: 9px 10px; font-size: 12px; line-height: 1.5; box-shadow: 0 10px 24px rgba(42,66,92,.18);
      pointer-events: none;
    }
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
        <button id="fitBtn" class="primary">重置视图</button>
      </div>
      <svg id="map" viewBox="0 0 1200 800" role="img" aria-label="马六甲船舶分类离线示意地图"></svg>
      <div id="tip" class="tip"></div>
      <div class="legend" id="legend"></div>
    </main>
    <aside class="side">
      <section class="header">
        <h1>Demo6 船舶分类增强版</h1>
        <p class="sub">基于马六甲海峡 / 新加坡海峡 10 分钟 AIS 数据，展示船舶分类、筛选、统计和分类依据。</p>
        <span class="tag">离线可用：不依赖外部地图</span>
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
    const svg = document.getElementById('map');
    const tip = document.getElementById('tip');
    const NS = 'http://www.w3.org/2000/svg';
    const PAD = 58, W = 1200, H = 800;
    let selected = DATA.vessels.find(v => v.points.length) || DATA.vessels[0];

    function e(tag, attrs = {}, text = '') {
      const n = document.createElementNS(NS, tag);
      Object.entries(attrs).forEach(([k, v]) => n.setAttribute(k, v));
      if (text) n.textContent = text;
      return n;
    }

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

    function bounds() {
      const pts = DATA.vessels.flatMap(v => v.points);
      const lons = pts.map(p => p.lon), lats = pts.map(p => p.lat);
      const minLon = Math.min(...lons), maxLon = Math.max(...lons);
      const minLat = Math.min(...lats), maxLat = Math.max(...lats);
      return { minLon: minLon - .03, maxLon: maxLon + .03, minLat: minLat - .02, maxLat: maxLat + .02 };
    }
    const B = bounds();
    function project(lon, lat) {
      const x = PAD + (lon - B.minLon) / (B.maxLon - B.minLon) * (W - PAD * 2);
      const y = H - PAD - (lat - B.minLat) / (B.maxLat - B.minLat) * (H - PAD * 2);
      return [x, y];
    }

    function drawBase() {
      svg.appendChild(e('rect', { x: 0, y: 0, width: W, height: H, fill: '#e8f4fb' }));
      svg.appendChild(e('path', { d: 'M58 720 L58 150 C165 160 210 220 245 320 C285 435 250 585 315 742 L58 742 Z', fill: '#e6eadf', stroke: '#bac7b4', 'stroke-width': 2 }));
      svg.appendChild(e('text', { x: 92, y: 178, fill: '#6b755f', 'font-size': 18, 'font-weight': 700 }, '新加坡及周边陆地区域示意'));
      svg.appendChild(e('text', { x: 785, y: 72, fill: '#31627d', 'font-size': 18, 'font-weight': 700 }, '马六甲 / 新加坡海峡 AIS 船舶分类'));
      for (let i = 0; i <= 6; i++) {
        const lon = B.minLon + (B.maxLon - B.minLon) * i / 6;
        const [x] = project(lon, B.minLat);
        svg.appendChild(e('line', { x1: x, y1: PAD, x2: x, y2: H - PAD, stroke: '#b8c9d7', 'stroke-width': 1, opacity: .55 }));
        svg.appendChild(e('text', { x, y: H - 22, 'text-anchor': 'middle', fill: '#5c6a79', 'font-size': 13 }, lon.toFixed(2) + '°E'));
      }
      for (let i = 0; i <= 5; i++) {
        const lat = B.minLat + (B.maxLat - B.minLat) * i / 5;
        const [, y] = project(B.minLon, lat);
        svg.appendChild(e('line', { x1: PAD, y1: y, x2: W - PAD, y2: y, stroke: '#b8c9d7', 'stroke-width': 1, opacity: .55 }));
        svg.appendChild(e('text', { x: 18, y: y + 4, fill: '#5c6a79', 'font-size': 13 }, lat.toFixed(2) + '°N'));
      }
    }

    function showTip(evt, html) {
      tip.innerHTML = html;
      tip.style.display = 'block';
      tip.style.left = Math.min(evt.clientX + 14, window.innerWidth - 310) + 'px';
      tip.style.top = Math.max(evt.clientY - 10, 12) + 'px';
    }
    function hideTip() { tip.style.display = 'none'; }

    function drawVessels() {
      visibleVessels().forEach(v => {
        const color = COLORS[v.category] || COLORS['未知'];
        if (v.points.length > 1) {
          const d = v.points.map((p, i) => {
            const [x, y] = project(p.lon, p.lat);
            return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)} ${y.toFixed(1)}`;
          }).join(' ');
          svg.appendChild(e('path', { d, fill: 'none', stroke: color, 'stroke-width': selected.mmsi === v.mmsi ? 3.4 : 2, opacity: selected.mmsi === v.mmsi ? .95 : .5 }));
        }
        const last = v.points[v.points.length - 1];
        if (!last) return;
        const [x, y] = project(last.lon, last.lat);
        const marker = e('circle', { cx: x, cy: y, r: selected.mmsi === v.mmsi ? 8 : 5.5, fill: color, stroke: '#fff', 'stroke-width': 2, style: 'cursor:pointer' });
        marker.addEventListener('click', () => selectVessel(v.mmsi));
        marker.addEventListener('mousemove', evt => showTip(evt, `<b>${v.category}</b><br>${v.name}<br>MMSI ${v.mmsi}<br>${v.reason}`));
        marker.addEventListener('mouseleave', hideTip);
        svg.appendChild(marker);
      });
    }

    function renderMap() {
      svg.innerHTML = '';
      drawBase();
      drawVessels();
    }

    function renderStats() {
      document.getElementById('totalShips').textContent = DATA.stats.total;
      document.getElementById('knownShips').textContent = DATA.stats.known;
      document.getElementById('trackShips').textContent = DATA.stats.with_track;
      document.getElementById('cargoShips').textContent = DATA.stats.counts['货船'] || 0;
      document.getElementById('tankerShips').textContent = DATA.stats.counts['油轮'] || 0;
      document.getElementById('unknownShips').textContent = DATA.stats.counts['未知'] || 0;
      document.getElementById('legend').innerHTML = ORDER.map(c => `<div><span class="dot" style="background:${COLORS[c]}"></span>${c}：${DATA.stats.counts[c] || 0} 艘</div>`).join('');
    }

    function renderList() {
      const wrap = document.getElementById('vesselList');
      wrap.innerHTML = '';
      visibleVessels().forEach(v => {
        const card = document.createElement('div');
        card.className = 'vessel-card' + (selected.mmsi === v.mmsi ? ' active' : '');
        card.innerHTML = `<div class="card-top"><div class="card-title">${v.name}</div><span class="badge" style="background:${COLORS[v.category]}">${v.category}</span></div>
          <div class="meta">MMSI：${v.mmsi}<br>置信度：${v.confidence || '未标注'} | 轨迹点：${v.points.length} | 平均速度：${v.avg_sog ?? '暂无'}</div>`;
        card.onclick = () => selectVessel(v.mmsi);
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

    function selectVessel(mmsi) {
      selected = DATA.vessels.find(v => v.mmsi === mmsi) || selected;
      renderList();
      renderDetail();
      renderMap();
    }

    document.getElementById('categoryFilter').onchange = () => { renderList(); renderMap(); };
    document.getElementById('reviewFilter').onchange = () => { renderList(); renderMap(); };
    document.getElementById('fitBtn').onclick = () => renderMap();
    renderStats();
    renderList();
    renderDetail();
    renderMap();
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
