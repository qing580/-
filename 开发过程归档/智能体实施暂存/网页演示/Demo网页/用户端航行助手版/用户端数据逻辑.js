(function (root) {
  'use strict';

  function number(value) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : NaN;
  }

  function relatedEvents(events, mmsi, limit = 5) {
    const id = String(mmsi ?? '');
    return events
      .filter(event => event.cpa && event.vessels.length > 1 && event.vessels.some(vessel => String(vessel.mmsi) === id))
      .sort((first, second) => second.score - first.score ||
        (first.cpa?.tcpa ?? Infinity) - (second.cpa?.tcpa ?? Infinity))
      .slice(0, limit);
  }

  function otherVessel(event, ownMmsi) {
    return event.vessels.find(vessel => String(vessel.mmsi) !== String(ownMmsi)) || event.vessels[0] || null;
  }

  function attentionBand(events) {
    const score = events[0]?.score || 0;
    if (score >= 75) return { level: '需立即关注', tone: 'critical', score };
    if (score >= 55) return { level: '建议提前观察', tone: 'warning', score };
    if (score >= 35) return { level: '保持关注', tone: 'watch', score };
    return { level: '当前未见突出会遇风险', tone: 'low', score };
  }

  function pointToSegmentNm(point, start, end) {
    const lat0 = (number(start.lat) + number(end.lat)) / 2;
    const scaleX = 60 * Math.cos(lat0 * Math.PI / 180);
    const x = (number(point.lon) - number(start.lon)) * scaleX;
    const y = (number(point.lat) - number(start.lat)) * 60;
    const bx = (number(end.lon) - number(start.lon)) * scaleX;
    const by = (number(end.lat) - number(start.lat)) * 60;
    if (![x, y, bx, by].every(Number.isFinite)) return Infinity;
    const lengthSquared = bx * bx + by * by;
    if (lengthSquared === 0) return Math.hypot(x, y);
    const ratio = Math.max(0, Math.min(1, (x * bx + y * by) / lengthSquared));
    return Math.hypot(x - ratio * bx, y - ratio * by);
  }

  function routeAssessment(start, end, events, corridorNm = 3) {
    const valid = [start?.lat, start?.lon, end?.lat, end?.lon].every(value => Number.isFinite(number(value)));
    if (!valid) return { available: false, reason: '起点或终点坐标无效', events: [] };
    const matched = events.map(event => ({
      event,
      corridorDistance: pointToSegmentNm(event.location, start, end)
    })).filter(item => item.corridorDistance <= corridorNm)
      .sort((first, second) => second.event.score - first.event.score || first.corridorDistance - second.corridorDistance);
    const highest = matched[0]?.event.score || 0;
    return {
      available: true,
      events: matched,
      highest,
      level: highest >= 75 ? '高风险目标靠近走廊' : highest >= 55 ? '走廊附近需提前观察' : matched.length ? '走廊附近存在关注目标' : '当前时间片未发现突出会遇事件',
      corridorNm
    };
  }

  function answerCard(question, context) {
    const events = relatedEvents(context.events || [], context.ownMmsi, 5);
    const top = events[0];
    const time = context.time || new Date().toISOString();
    if (question === 'why') {
      return top ? {
        conclusion: `${otherVessel(top, context.ownMmsi)?.name || '首要目标'}建议重点观察。`,
        evidence: `风险等级 ${top.level}；DCPA ${top.cpa?.dcpa?.toFixed(2) ?? '不可用'} nm；TCPA ${top.cpa?.tcpa?.toFixed(1) ?? '不可用'} min；${top.encounterShape || '会遇形态待判断'}。`,
        confidence: top.confidence,
        uncertainty: '基于 AIS 匀速直线外推，目标变速、转向或数据延迟会改变结果。',
        action: '持续观察双方航向和航速，并由值班人员结合 COLREGs 与现场态势判断。',
        time
      } : emptyAnswer(time);
    }
    if (question === 'quality') {
      return {
        conclusion: context.quality?.motionCoverage >= 0.8 ? '本批次运动字段覆盖较好，但仍需关注单船数据时延。' : '运动字段覆盖有限，部分会遇计算可能不可用。',
        evidence: `位置字段有效率 ${percent(context.quality?.positionValidity)}，运动字段覆盖率 ${percent(context.quality?.motionCoverage)}。`,
        confidence: '中',
        uncertainty: 'AIS 静态字段可能缺失或填报错误，六小时样本不代表长期规律。',
        action: '查看目标 AIS 时间和船型来源，必要时等待后续报文或人工核验。',
        time
      };
    }
    return events.length ? {
      conclusion: `当前发现 ${events.length} 个与关注船有关的中等关注及以上会遇目标。`,
      evidence: `首要目标 ${otherVessel(top, context.ownMmsi)?.name || top.id}，风险等级 ${top.level}。`,
      confidence: top.confidence,
      uncertainty: '当前仅包含 AIS 与 CPA/TCPA，尚无风浪、海流和航道网络数据。',
      action: '优先查看 Top 1 目标的 DCPA、TCPA 和 AIS 新鲜度。',
      time
    } : emptyAnswer(time);
  }

  function emptyAnswer(time) {
    return {
      conclusion: '当前时间片未筛选出与关注船有关的中等关注及以上会遇事件。',
      evidence: '系统已检查当前有效 AIS 快照和 CPA/TCPA 初筛结果。',
      confidence: '中',
      uncertainty: '这不等于绝对安全；未广播 AIS 的目标和环境影响不在当前数据中。',
      action: '保持正常瞭望，并继续观察后续 AIS 更新。',
      time
    };
  }

  function percent(value) {
    return Number.isFinite(Number(value)) ? `${(Number(value) * 100).toFixed(1)}%` : '不可用';
  }

  const api = { relatedEvents, otherVessel, attentionBand, pointToSegmentNm, routeAssessment, answerCard };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.ClientData = api;
})(typeof window !== 'undefined' ? window : globalThis);
