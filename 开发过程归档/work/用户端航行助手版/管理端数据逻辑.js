(function (root) {
  'use strict';

  function number(value) {
    if (value === null || value === undefined || String(value).trim() === '') return NaN;
    return Number(value);
  }

  function validPoint(point) {
    return point && Number.isFinite(Date.parse(point.time)) &&
      Number.isFinite(number(point.lat)) && Math.abs(number(point.lat)) <= 90 &&
      Number.isFinite(number(point.lon)) && Math.abs(number(point.lon)) <= 180;
  }

  function snapshots(vessels, time, encounterMath) {
    return vessels.map(vessel => {
      const points = vessel.points.filter(point => validPoint(point) && Date.parse(point.time) <= time)
        .sort((a, b) => Date.parse(a.time) - Date.parse(b.time));
      const point = points[points.length - 1] || null;
      return {
        vessel,
        point,
        previous: points[points.length - 2] || null,
        ageMinutes: point ? Math.max(0, (time - Date.parse(point.time)) / 60000) : Infinity,
        pointCount: points.length
      };
    }).filter(item => item.point);
  }

  function circularDifference(a, b) {
    const first = number(a);
    const second = number(b);
    if (!(first >= 0 && first < 360 && second >= 0 && second < 360)) return null;
    const raw = Math.abs(first - second);
    return Math.min(raw, 360 - raw);
  }

  function encounterShape(first, second) {
    const delta = circularDifference(first.cog, second.cog);
    if (delta === null) return '航向资料不足';
    if (delta >= 150) return '对遇形态';
    if (delta <= 20) return '同向或追越形态';
    return '交叉形态';
  }

  function riskBand(score) {
    if (score >= 75) return { level: '高风险', tone: 'critical' };
    if (score >= 55) return { level: '中高风险', tone: 'warning' };
    if (score >= 35) return { level: '中等关注', tone: 'watch' };
    return { level: '低关注', tone: 'low' };
  }

  function eventId(prefix, ids) {
    const identifiers = ids.map(value => String(value || 'unknown')).join('-');
    return `${prefix}-${identifiers}`;
  }

  function confidenceFor(first, second, cpa) {
    if (!cpa.available) return '低';
    const age = Math.max(first.ageMinutes, second.ageMinutes);
    if (age <= 1) return '高';
    if (age <= 3) return '中';
    return '较低';
  }

  function buildEncounterEvents(snapshotRows, time, encounterMath) {
    const fresh = snapshotRows.filter(item => item.ageMinutes <= 5);
    const events = [];
    for (let i = 0; i < fresh.length; i += 1) {
      for (let j = i + 1; j < fresh.length; j += 1) {
        const first = fresh[i];
        const second = fresh[j];
        const distance = encounterMath.distance(first.point, second.point);
        if (!Number.isFinite(distance) || distance > 8) continue;
        const course = encounterMath.course(first.point, second.point, time);
        const cpa = encounterMath.cpa(first.point, second.point, time);
        const assessed = encounterMath.risk({
          own: first.point,
          point: second.point,
          distance,
          age: Math.max(first.ageMinutes, second.ageMinutes),
          course,
          cpa
        });
        if (assessed.score < 35 || !cpa.available || cpa.tcpa < 0) continue;
        const band = riskBand(assessed.score);
        events.push({
          id: eventId('ENC', [first.vessel.mmsi, second.vessel.mmsi]),
          kind: assessed.score >= 75 ? '高风险会遇' : '会遇风险初筛',
          source: 'AIS + CPA/TCPA',
          level: band.level,
          tone: band.tone,
          score: assessed.score,
          confidence: confidenceFor(first, second, cpa),
          status: assessed.score >= 75 ? '待核查' : '待确认',
          firstSeen: new Date(time).toISOString(),
          updatedAt: new Date(time).toISOString(),
          location: {
            lat: (number(first.point.lat) + number(second.point.lat)) / 2,
            lon: (number(first.point.lon) + number(second.point.lon)) / 2
          },
          vessels: [first.vessel, second.vessel],
          points: [first.point, second.point],
          distance,
          cpa,
          risk: assessed,
          encounterShape: encounterShape(first.point, second.point),
          explanation: '基于两船最新 AIS 位置、航速和航向进行匀速直线外推。'
        });
      }
    }
    return events;
  }

  function buildBehaviorEvents(snapshotRows, time) {
    const events = [];
    snapshotRows.forEach(item => {
      const { vessel, point, previous, ageMinutes } = item;
      if (ageMinutes > 5 || !previous) return;
      const elapsed = (Date.parse(point.time) - Date.parse(previous.time)) / 60000;
      if (!(elapsed > 0 && elapsed <= 10)) return;
      const currentSpeed = number(point.sog);
      const previousSpeed = number(previous.sog);
      const turn = circularDifference(point.cog, previous.cog);
      if (turn !== null && turn >= 60 && Math.max(currentSpeed, previousSpeed) >= 2) {
        const score = Math.min(82, Math.round(48 + turn / 5));
        const band = riskBand(score);
        events.push({
          id: eventId('TURN', [vessel.mmsi]), kind: '异常转向初筛', source: 'AIS 行为规则',
          level: band.level, tone: band.tone, score, confidence: elapsed <= 3 ? '中' : '较低', status: '待确认',
          firstSeen: point.time, updatedAt: new Date(time).toISOString(), location: { lat: point.lat, lon: point.lon },
          vessels: [vessel], points: [point], metric: `${turn.toFixed(1)}° / ${elapsed.toFixed(1)}分钟`,
          explanation: '短时间航向变化超过演示筛选阈值，需要结合航道、避碰和作业状态人工核查。'
        });
      }
      if (Number.isFinite(currentSpeed) && Number.isFinite(previousSpeed) && previousSpeed >= 8 && previousSpeed - currentSpeed >= 6) {
        const drop = previousSpeed - currentSpeed;
        const score = Math.min(80, Math.round(50 + drop * 3));
        const band = riskBand(score);
        events.push({
          id: eventId('SLOW', [vessel.mmsi]), kind: '异常减速初筛', source: 'AIS 行为规则',
          level: band.level, tone: band.tone, score, confidence: elapsed <= 3 ? '中' : '较低', status: '待确认',
          firstSeen: point.time, updatedAt: new Date(time).toISOString(), location: { lat: point.lat, lon: point.lon },
          vessels: [vessel], points: [point], metric: `${previousSpeed.toFixed(1)} -> ${currentSpeed.toFixed(1)}节`,
          explanation: '短时间航速下降超过演示筛选阈值，需要结合拥堵、锚泊和环境因素人工核查。'
        });
      }
    });
    return events;
  }

  function buildEvents(vessels, time, encounterMath) {
    const rows = snapshots(vessels, time, encounterMath);
    const events = [...buildEncounterEvents(rows, time, encounterMath), ...buildBehaviorEvents(rows, time)];
    events.sort((a, b) => b.score - a.score ||
      (a.cpa?.tcpa ?? Infinity) - (b.cpa?.tcpa ?? Infinity) || a.id.localeCompare(b.id));
    return { snapshots: rows, events };
  }

  function recentTrack(vessel, cutoff, minutes = 30) {
    const end = number(cutoff);
    const duration = Math.max(0, number(minutes)) * 60 * 1000;
    if (!vessel || !Array.isArray(vessel.points) || !Number.isFinite(end) || !Number.isFinite(duration)) return [];
    const start = end - duration;
    return vessel.points.filter(point => {
      const stamp = Date.parse(point.time);
      return validPoint(point) && stamp >= start && stamp <= end;
    }).sort((first, second) => Date.parse(first.time) - Date.parse(second.time));
  }

  function dataQuality(vessels) {
    let points = 0;
    let valid = 0;
    let motionReady = 0;
    vessels.forEach(vessel => vessel.points.forEach(point => {
      points += 1;
      if (validPoint(point)) valid += 1;
      const sog = number(point.sog);
      const cog = number(point.cog);
      if (validPoint(point) && Number.isFinite(sog) && sog >= 0 && sog < 102.3 && cog >= 0 && cog < 360) motionReady += 1;
    }));
    const classified = vessels.filter(vessel => vessel.category && vessel.category !== '未知').length;
    return {
      vessels: vessels.length,
      points,
      valid,
      motionReady,
      classified,
      positionValidity: points ? valid / points : 0,
      motionCoverage: points ? motionReady / points : 0,
      classificationCoverage: vessels.length ? classified / vessels.length : 0
    };
  }

  const api = { snapshots, buildEvents, buildEncounterEvents, buildBehaviorEvents, recentTrack, dataQuality, riskBand, circularDifference };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.ManagementData = api;
})(typeof window === 'undefined' ? this : window);
