(function (root) {
  'use strict';

  const KNOT_TO_MPS = 0.514444;
  const EARTH_RADIUS_M = 6371008.8;
  const DEFAULTS = {
    maxInterpolationGapMs: 2 * 60 * 1000,
    trackWindowMs: 10 * 60 * 1000,
    baseHistorySecondsPerRealSecond: 60
  };

  function number(value) {
    if (value === null || value === undefined || String(value).trim() === '') return NaN;
    return Number(value);
  }

  function validCoordinate(lat, lon) {
    return Number.isFinite(lat) && Number.isFinite(lon) && Math.abs(lat) <= 90 && Math.abs(lon) <= 180;
  }

  function normalizeCourse(value) {
    const parsed = number(value);
    return parsed >= 0 && parsed < 360 ? parsed : NaN;
  }

  function normalizePoint(point) {
    const timeMs = Date.parse(point?.time);
    const lat = number(point?.lat);
    const lon = number(point?.lon);
    if (!Number.isFinite(timeMs) || !validCoordinate(lat, lon)) return null;
    return {
      source: point,
      timeMs,
      lat,
      lon,
      sog: number(point.sog),
      cog: normalizeCourse(point.cog),
      heading: normalizeCourse(point.heading)
    };
  }

  function prepareVessel(vessel) {
    const points = (vessel?.points || []).map(normalizePoint).filter(Boolean)
      .sort((first, second) => first.timeMs - second.timeMs);
    const unique = [];
    points.forEach(point => {
      const previous = unique[unique.length - 1];
      if (previous && previous.timeMs === point.timeMs && previous.lat === point.lat && previous.lon === point.lon) return;
      unique.push(point);
    });
    return { source: vessel, points: unique, times: unique.map(point => point.timeMs) };
  }

  function prepareVessels(vessels) {
    const prepared = (vessels || []).map(prepareVessel).filter(vessel => vessel.points.length);
    const times = prepared.flatMap(vessel => vessel.times).sort((a, b) => a - b);
    return {
      vessels: prepared,
      startTimeMs: times[0] ?? Date.now(),
      endTimeMs: times[times.length - 1] ?? Date.now(),
      observationTimes: [...new Set(times)]
    };
  }

  function upperBound(values, target) {
    let low = 0;
    let high = values.length;
    while (low < high) {
      const middle = Math.floor((low + high) / 2);
      if (values[middle] <= target) low = middle + 1;
      else high = middle;
    }
    return low;
  }

  function bracketAt(vessel, timeMs) {
    const nextIndex = upperBound(vessel.times, timeMs);
    const previousIndex = nextIndex - 1;
    return {
      previousIndex,
      nextIndex,
      previous: previousIndex >= 0 ? vessel.points[previousIndex] : null,
      next: nextIndex < vessel.points.length ? vessel.points[nextIndex] : null
    };
  }

  function destination(point, elapsedMs) {
    if (!(elapsedMs > 0)) {
      return { lat: point.lat, lon: point.lon, usedMotion: false };
    }
    if (!(Number.isFinite(point.sog) && point.sog >= 0 && point.sog < 102.3 && Number.isFinite(point.cog))) {
      return { lat: point.lat, lon: point.lon, usedMotion: false };
    }
    const distance = point.sog * KNOT_TO_MPS * Math.max(0, elapsedMs) / 1000;
    const bearing = point.cog * Math.PI / 180;
    const angular = distance / EARTH_RADIUS_M;
    const lat1 = point.lat * Math.PI / 180;
    const lon1 = point.lon * Math.PI / 180;
    const lat2 = Math.asin(Math.sin(lat1) * Math.cos(angular) + Math.cos(lat1) * Math.sin(angular) * Math.cos(bearing));
    const lon2 = lon1 + Math.atan2(
      Math.sin(bearing) * Math.sin(angular) * Math.cos(lat1),
      Math.cos(angular) - Math.sin(lat1) * Math.sin(lat2)
    );
    return {
      lat: lat2 * 180 / Math.PI,
      lon: ((lon2 * 180 / Math.PI + 540) % 360) - 180,
      usedMotion: true
    };
  }

  function smoothstep(value) {
    const ratio = Math.max(0, Math.min(1, value));
    return ratio * ratio * (3 - 2 * ratio);
  }

  function interpolate(previous, next, timeMs, options = {}) {
    const config = { ...DEFAULTS, ...options };
    const elapsedMs = Math.max(0, timeMs - previous.timeMs);
    if (elapsedMs === 0) {
      return {
        lat: previous.lat,
        lon: previous.lon,
        status: 'observed',
        estimated: false,
        stale: false,
        gapMs: next ? next.timeMs - previous.timeMs : null,
        ratio: next ? 0 : null
      };
    }
    if (!next) {
      return {
        lat: previous.lat,
        lon: previous.lon,
        status: 'ended',
        estimated: false,
        stale: true,
        gapMs: null,
        ratio: null
      };
    }

    const gapMs = next.timeMs - previous.timeMs;
    if (!(gapMs > 0)) {
      return { lat: previous.lat, lon: previous.lon, status: 'observed', estimated: false, stale: false, gapMs, ratio: 0 };
    }
    if (gapMs > config.maxInterpolationGapMs) {
      return {
        lat: previous.lat,
        lon: previous.lon,
        status: 'signal-gap',
        estimated: false,
        stale: true,
        gapMs,
        ratio: Math.min(1, elapsedMs / gapMs)
      };
    }

    const ratio = Math.max(0, Math.min(1, elapsedMs / gapMs));
    const linear = {
      lat: previous.lat + (next.lat - previous.lat) * ratio,
      lon: previous.lon + (next.lon - previous.lon) * ratio
    };
    const projected = destination(previous, elapsedMs);
    const correction = projected.usedMotion ? smoothstep(ratio) : 1;
    return {
      lat: projected.lat * (1 - correction) + linear.lat * correction,
      lon: projected.lon * (1 - correction) + linear.lon * correction,
      status: ratio === 0 ? 'observed' : 'interpolated',
      estimated: ratio > 0,
      stale: false,
      gapMs,
      ratio
    };
  }

  function recentTrackSegments(vessel, timeMs, options = {}) {
    const config = { ...DEFAULTS, ...options };
    const windowStart = timeMs - config.trackWindowMs;
    const startIndex = upperBound(vessel.times, windowStart - 1);
    const endIndex = upperBound(vessel.times, timeMs);
    const points = vessel.points.slice(startIndex, endIndex);
    const segments = [];
    let segment = [];

    points.forEach(point => {
      const previous = segment[segment.length - 1];
      if (previous && point.timeMs - previous.timeMs > config.maxInterpolationGapMs) {
        if (segment.length > 1) segments.push(segment.map(item => [item.lat, item.lon]));
        segment = [];
      }
      segment.push(point);
    });
    if (segment.length > 1) segments.push(segment.map(item => [item.lat, item.lon]));
    return segments;
  }

  function stateAt(vessel, timeMs, options = {}) {
    const bracket = bracketAt(vessel, timeMs);
    if (!bracket.previous) return null;
    const display = interpolate(bracket.previous, bracket.next, timeMs, options);
    const course = Number.isFinite(bracket.previous.heading) ? bracket.previous.heading : bracket.previous.cog;
    return {
      vessel: vessel.source,
      observation: bracket.previous.source,
      previousIndex: bracket.previousIndex,
      nextObservation: bracket.next?.source || null,
      displayPosition: { lat: display.lat, lon: display.lon },
      displayCourse: Number.isFinite(course) ? course : 0,
      ageMs: Math.max(0, timeMs - bracket.previous.timeMs),
      ...display
    };
  }

  function createClock(startTimeMs, endTimeMs, options = {}) {
    const config = { ...DEFAULTS, ...options };
    let timeMs = Math.max(startTimeMs, Math.min(endTimeMs, options.initialTimeMs ?? startTimeMs));
    let speed = [0.5, 1, 2, 4].includes(options.speed) ? options.speed : 1;
    let playing = false;

    function seek(value) {
      timeMs = Math.max(startTimeMs, Math.min(endTimeMs, Number(value) || startTimeMs));
      return timeMs;
    }

    return {
      get timeMs() { return timeMs; },
      get speed() { return speed; },
      get playing() { return playing; },
      play() { playing = true; },
      pause() { playing = false; },
      seek,
      jump(deltaMs) { return seek(timeMs + deltaMs); },
      setSpeed(value) {
        const parsed = Number(value);
        if (![0.5, 1, 2, 4].includes(parsed)) throw new Error(`Unsupported playback speed: ${value}`);
        speed = parsed;
      },
      advance(realDeltaMs) {
        if (!playing) return timeMs;
        const safeDelta = Math.max(0, Math.min(250, Number(realDeltaMs) || 0));
        const historyDelta = safeDelta * config.baseHistorySecondsPerRealSecond * speed;
        seek(timeMs + historyDelta);
        if (timeMs >= endTimeMs) playing = false;
        return timeMs;
      },
      progress() {
        return endTimeMs > startTimeMs ? (timeMs - startTimeMs) / (endTimeMs - startTimeMs) : 0;
      }
    };
  }

  const api = {
    DEFAULTS,
    normalizePoint,
    prepareVessel,
    prepareVessels,
    upperBound,
    bracketAt,
    destination,
    interpolate,
    stateAt,
    recentTrackSegments,
    createClock
  };

  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.HistoricalAisReplay = api;
})(typeof window !== 'undefined' ? window : globalThis);
