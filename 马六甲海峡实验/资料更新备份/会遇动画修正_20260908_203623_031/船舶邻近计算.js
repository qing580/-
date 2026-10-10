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
  function risk(row) {
    const distanceScore = clamp((3 - row.distance) / 3, 0, 1);
    const crossingScore = row.course.delta === null ? .38 : clamp(Math.sin(row.course.delta * Math.PI / 180), 0, 1);
    const speedA = numeric(row.own?.sog);
    const speedB = numeric(row.point?.sog);
    const speedScore = clamp(((Number.isFinite(speedA) ? speedA : 0) + (Number.isFinite(speedB) ? speedB : 0)) / 36, 0, 1);
    const freshnessScore = clamp(1 - row.age / 10, 0, 1);
    const score = Math.round((distanceScore * .46 + crossingScore * .24 + speedScore * .18 + freshnessScore * .12) * 100);
    let level = '低关注', tone = 'low';
    if (score >= 72) { level = '紧急关注'; tone = 'critical'; }
    else if (score >= 48) { level = '重点关注'; tone = 'warning'; }
    else if (score >= 28) { level = '一般关注'; tone = 'watch'; }
    return { score, level, tone, parts: { distanceScore, crossingScore, speedScore, freshnessScore } };
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
      return { vessel: v, point: other, own: point, distance: distance(point, other), age: Math.max(0, (time - Date.parse(other.time)) / 60000), course: course(point, other, time) };
    }).filter(Boolean).sort((a, b) => a.distance - b.distance) };
  }
  const api = { latest, distance, course, risk, rank, neighbors };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.EncounterMath = api;
})(typeof window === 'undefined' ? this : window);
