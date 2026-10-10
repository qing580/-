'use strict';

const fs = require('node:fs');
const path = require('node:path');

class AisToolError extends Error {
  constructor(code, message, statusCode = 400) {
    super(message);
    this.name = 'AisToolError';
    this.code = code;
    this.statusCode = statusCode;
  }
}

function finite(value) {
  if (value === null || value === undefined || String(value).trim() === '') return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function publicPoint(point) {
  if (!point) return null;
  return {
    observedAt: point.time,
    lat: finite(point.lat),
    lon: finite(point.lon),
    sogKt: finite(point.sog),
    cogDeg: finite(point.cog),
    trueHeadingDeg: finite(point.heading),
    sourceType: 'AIS_real_observation'
  };
}

function datasetBounds(vessels) {
  let minimum = Infinity;
  let maximum = -Infinity;
  vessels.forEach(vessel => vessel.points.forEach(point => {
    const time = Date.parse(point.time);
    if (!Number.isFinite(time)) return;
    minimum = Math.min(minimum, time);
    maximum = Math.max(maximum, time);
  }));
  return { minimum, maximum };
}

function sanitizeCpa(cpa) {
  if (!cpa) return null;
  return {
    available: Boolean(cpa.available),
    label: cpa.label || '',
    dcpaNm: finite(cpa.dcpa),
    tcpaMinutes: finite(cpa.tcpa),
    relativeSpeedKt: finite(cpa.relativeSpeed),
    method: 'constant_velocity_linear_extrapolation'
  };
}

function createAisTools(config) {
  let cache = null;

  function load() {
    if (cache) return cache;
    if (!fs.existsSync(config.aisDataFile)) {
      throw new AisToolError('ais_data_missing', '正式AIS演示数据不存在', 503);
    }
    const dataset = JSON.parse(fs.readFileSync(config.aisDataFile, 'utf8'));
    if (!Array.isArray(dataset.vessels)) {
      throw new AisToolError('ais_data_invalid', 'AIS演示数据格式无效', 503);
    }
    const managementPath = path.join(config.aisModuleDir, '管理端数据逻辑.js');
    const encounterPath = path.join(config.aisModuleDir, '船舶邻近计算.js');
    const management = require(managementPath);
    const encounter = require(encounterPath);
    cache = {
      dataset,
      management,
      encounter,
      bounds: datasetBounds(dataset.vessels),
      quality: management.dataQuality(dataset.vessels),
      vesselsByMmsi: new Map(dataset.vessels.map(vessel => [String(vessel.mmsi), vessel]))
    };
    return cache;
  }

  function metadata() {
    const state = load();
    return {
      dataset: path.basename(config.aisDataFile),
      vesselCount: state.dataset.vessels.length,
      pointCount: state.quality.points,
      startTime: new Date(state.bounds.minimum).toISOString(),
      endTime: new Date(state.bounds.maximum).toISOString(),
      sourceNote: state.dataset.generated_note || '',
      calculations: ['snapshot', 'trajectory_window', 'neighbors', 'CPA/TCPA', 'event_screening', 'data_quality']
    };
  }

  function validateQuery(mmsi, timeValue) {
    const id = String(mmsi || '').trim();
    if (!/^\d{7,9}$/.test(id)) {
      throw new AisToolError('invalid_mmsi', 'MMSI必须是数据中存在的7至9位数字标识');
    }
    const time = Date.parse(String(timeValue || ''));
    if (!Number.isFinite(time)) throw new AisToolError('invalid_time', '回放时间必须是有效ISO时间');
    const state = load();
    if (!state.vesselsByMmsi.has(id)) throw new AisToolError('vessel_not_found', '当前AIS数据中没有该MMSI', 404);
    if (time < state.bounds.minimum || time > state.bounds.maximum) {
      throw new AisToolError('time_out_of_range', '回放时间超出当前AIS数据范围', 422);
    }
    return { id, time, state };
  }

  function context(mmsi, timeValue, options = {}) {
    const { id, time, state } = validateQuery(mmsi, timeValue);
    const windowMinutes = Math.max(5, Math.min(60, Number(options.windowMinutes) || 30));
    const vessel = state.vesselsByMmsi.get(id);
    const bundle = state.management.buildEvents(state.dataset.vessels, time, state.encounter);
    const ownSnapshot = bundle.snapshots.find(row => String(row.vessel.mmsi) === id) || null;
    const relatedEvents = bundle.events.filter(event =>
      event.vessels.some(item => String(item.mmsi) === id)).slice(0, 5);
    const neighborBundle = state.encounter.neighbors(state.dataset.vessels, id, time);
    const neighbors = neighborBundle.rows.filter(row => row.age <= 5 && row.distance <= 8).slice(0, 5).map(row => {
      const event = relatedEvents.find(item => item.vessels.some(candidate => String(candidate.mmsi) === String(row.vessel.mmsi)));
      return {
        mmsi: String(row.vessel.mmsi),
        name: row.vessel.name || '未获取船名',
        category: row.vessel.category || '未知',
        distanceNm: finite(row.distance),
        observationAgeMinutes: finite(row.age),
        courseComparison: row.course?.label || '不可用',
        courseDifferenceDeg: finite(row.course?.delta),
        cpa: sanitizeCpa(row.cpa),
        screeningLevel: event?.level || '未进入中等关注事件',
        evidenceConfidence: event?.confidence || '未评级'
      };
    });
    const trajectoryStart = time - windowMinutes * 60000;
    const trajectory = vessel.points.filter(point => {
      const pointTime = Date.parse(point.time);
      return Number.isFinite(pointTime) && pointTime >= trajectoryStart && pointTime <= time;
    }).map(publicPoint);
    const current = publicPoint(ownSnapshot?.point);
    const missingReasons = [];
    if (!ownSnapshot) missingReasons.push('所选回放时刻之前没有该船真实AIS位置');
    if (ownSnapshot?.ageMinutes > 5) missingReasons.push('最近AIS位置超过5分钟');
    if (current && current.sogKt === null) missingReasons.push('当前SOG缺失');
    if (current && current.cogDeg === null) missingReasons.push('当前COG缺失');

    return {
      query: { mmsi: id, replayTime: new Date(time).toISOString(), trajectoryWindowMinutes: windowMinutes },
      dataset: { name: path.basename(config.aisDataFile), region: 'malacca_southeast_singapore_strait', historicalReplay: true },
      vessel: {
        mmsi: id,
        name: vessel.name || '未获取船名',
        category: vessel.category || '未知',
        categorySource: vessel.source || '未标注',
        imo: vessel.imo || null,
        callSign: vessel.call_sign || null
      },
      currentObservation: current ? { ...current, ageMinutes: finite(ownSnapshot.ageMinutes) } : null,
      trajectory,
      neighbors,
      events: relatedEvents.map(event => ({
        id: event.id,
        kind: event.kind,
        level: event.level,
        source: event.source,
        confidence: event.confidence,
        updatedAt: event.updatedAt,
        vesselMmsis: event.vessels.map(item => String(item.mmsi)),
        distanceNm: finite(event.distance),
        cpa: sanitizeCpa(event.cpa),
        encounterShape: event.encounterShape || null,
        metric: event.metric || null,
        explanation: event.explanation
      })),
      quality: {
        positionValidity: state.quality.positionValidity,
        motionCoverage: state.quality.motionCoverage,
        classificationCoverage: state.quality.classificationCoverage
      },
      evidenceGate: {
        sufficientForCurrentMotion: Boolean(current && ownSnapshot.ageMinutes <= 5 && current.sogKt !== null && current.cogDeg !== null),
        missingReasons,
        boundary: '仅使用回放时刻及以前的真实AIS观测；CPA/TCPA为匀速直线外推，不替代人工航海判断。'
      }
    };
  }

  return { metadata, context };
}

module.exports = { AisToolError, createAisTools, datasetBounds, publicPoint, sanitizeCpa };
