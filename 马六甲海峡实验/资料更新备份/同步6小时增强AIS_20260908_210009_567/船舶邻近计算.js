(function (root) {
  'use strict';
  const numeric = v => v === null || v === undefined || String(v).trim() === '' ? NaN : Number(v);
  function valid(p) {
    return p && Number.isFinite(Date.parse(p.time)) && Math.abs(numeric(p.lat)) <= 90 && Math.abs(numeric(p.lon)) <= 180;
  }
  function latest(v, time) {
    return v.points.filter(p => valid(p) && Date.parse(p.time) <= time)
      .reduce((a, b) => !a || Date.parse(b.time) > Date.parse(a.time) ? b : a, null);
  }
  function distance(a, b) {
    const rad = x => x * Math.PI / 180;
    const dlat = rad(Number(b.lat) - Number(a.lat));
    const dlon = rad(Number(b.lon) - Number(a.lon));
    const h = Math.sin(dlat / 2) ** 2 + Math.cos(rad(Number(a.lat))) * Math.cos(rad(Number(b.lat))) * Math.sin(dlon / 2) ** 2;
    return 6371.0088 * 2 * Math.asin(Math.sqrt(Math.min(1, Math.max(0, h)))) / 1.852;
  }
  function course(a, b, time) {
    // Five minutes and one knot are display-quality guards, not collision thresholds.
    if ([a, b].some(p => time - Date.parse(p.time) > 300000)) return { label: '旧位置，暂不比较', delta: null };
    if ([a, b].some(p => !Number.isFinite(numeric(p.sog)) || numeric(p.sog) < 1 || numeric(p.sog) >= 102.3)) return { label: '低速或航速缺失', delta: null };
    if ([a, b].some(p => !(numeric(p.cog) >= 0 && numeric(p.cog) < 360))) return { label: '航向缺失', delta: null };
    const diff = Math.abs(numeric(a.cog) - numeric(b.cog));
    const delta = Math.min(diff, 360 - diff);
    return { label: '仅航向夹角，非会遇结论', delta };
  }
  function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
  }
  function motionVector(p) {
    const sog = numeric(p.sog);
    const cog = numeric(p.cog);
    if (!Number.isFinite(sog) || sog < 0.2 || sog >= 102.3 || !(cog >= 0 && cog < 360)) return null;
    const rad = cog * Math.PI / 180;
    return { x: sog * Math.sin(rad), y: sog * Math.cos(rad), sog, cog };
  }
  function relativeXY(a, b) {
    const meanLat = (numeric(a.lat) + numeric(b.lat)) / 2 * Math.PI / 180;
    const dx = (((numeric(b.lon) - numeric(a.lon) + 540) % 360) - 180) * 60 * Math.cos(meanLat);
    const dy = (numeric(b.lat) - numeric(a.lat)) * 60;
    return { x: dx, y: dy };
  }
  function cpa(a, b, time) {
    if ([a, b].some(p => time - Date.parse(p.time) > 300000)) return { available: false, label: 'AIS位置超过5分钟，暂不计算CPA/TCPA', dcpa: null, tcpa: null };
    const va = motionVector(a), vb = motionVector(b);
    if (!va || !vb) return { available: false, label: '航速或航向不足，暂不计算CPA/TCPA', dcpa: null, tcpa: null };
    const r = relativeXY(a, b);
    const v = { x: vb.x - va.x, y: vb.y - va.y };
    const vv = v.x * v.x + v.y * v.y;
    if (vv < 0.0001) return { available: false, label: '相对速度过小，CPA/TCPA不稳定', dcpa: null, tcpa: null };
    const tcpaHours = -(r.x * v.x + r.y * v.y) / vv;
    const tcpaMinutes = tcpaHours * 60;
    const useHours = Math.max(0, tcpaHours);
    const closest = { x: r.x + v.x * useHours, y: r.y + v.y * useHours };
    const dcpa = Math.hypot(closest.x, closest.y);
    const label = tcpaMinutes < 0 ? '最近会遇点已在过去，显示当前最小距离' : '已计算未来最近会遇点';
    return { available: true, label, dcpa, tcpa: tcpaMinutes, relativeSpeed: Math.sqrt(vv) };
  }
  function risk(row) {
    const cpaResult = row.cpa || cpa(row.own, row.point, Date.parse(row.own.time));
    const cpaScore = cpaResult.available && cpaResult.tcpa >= 0 ? clamp((1.5 - cpaResult.dcpa) / 1.5, 0, 1) : 0;
    const tcpaScore = cpaResult.available && cpaResult.tcpa >= 0 ? clamp((30 - cpaResult.tcpa) / 30, 0, 1) : 0;
    const distanceScore = clamp((3 - row.distance) / 3, 0, 1);
    const crossingScore = row.course.delta === null ? .38 : clamp(Math.sin(row.course.delta * Math.PI / 180), 0, 1);
    const freshnessScore = clamp(1 - row.age / 10, 0, 1);
    const score = Math.round((cpaScore * .38 + tcpaScore * .28 + distanceScore * .18 + crossingScore * .10 + freshnessScore * .06) * 100);
    let level = '低关注', tone = 'low';
    if (score >= 75) { level = '高碰撞风险'; tone = 'critical'; }
    else if (score >= 55) { level = '中高碰撞风险'; tone = 'warning'; }
    else if (score >= 35) { level = '中等关注'; tone = 'watch'; }
    return { score, level, tone, cpa: cpaResult, parts: { cpaScore, tcpaScore, distanceScore, crossingScore, freshnessScore } };
  }
  function rank(rows, limit) {
    return rows.map(row => {
      const assessed = { ...row, risk: risk(row) };
      return assessed;
    }).sort((a, b) => b.risk.score - a.risk.score || a.distance - b.distance).slice(0, limit ?? 5);
  }
  function neighbors(vessels, ownId, time) {
    const own = vessels.find(v => String(v.mmsi) === String(ownId));
    const point = own && latest(own, time);
    if (!point) return { point: null, rows: [] };
    return { point, rows: vessels.filter(v => String(v.mmsi) !== String(ownId)).map(v => {
      const other = latest(v, time);
      if (!other) return null;
      const row = { vessel: v, point: other, own: point, distance: distance(point, other), age: Math.max(0, (time - Date.parse(other.time)) / 60000), course: course(point, other, time) };
      row.cpa = cpa(point, other, time);
      return row;
    }).filter(Boolean).sort((a, b) => a.distance - b.distance) };
  }
  const api = { latest, distance, course, cpa, risk, rank, neighbors };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.EncounterMath = api;
})(typeof window === 'undefined' ? this : window);
