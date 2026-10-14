// Pure acquisition/export logic. Platform sensor and file APIs live in the UX page.
function finite(value) { return typeof value === 'number' && isFinite(value); }

function createRecorder(options) {
  options = options || {};
  const now = options.now || Date.now;
  const limit = options.maxSamples || 2000;
  const duration = options.durationMs || 2000;
  let record = null;
  let active = false;
  let previousElapsed = null;

  function snapshot() { return record ? JSON.parse(JSON.stringify(record)) : null; }
  function stop(reason, timestamp) {
    if (record && active) {
      active = false;
      record.stopped_epoch_ms = timestamp === undefined ? now() : timestamp;
      record.stop_reason = reason || 'manual';
    }
    return snapshot();
  }

  return {
    start: function () {
      const started = now();
      if (!finite(started)) throw new Error('回调时钟不可用');
      previousElapsed = null;
      active = true;
      record = {
        schema_version: 1,
        session_id: String(started) + '_' + Math.floor(Math.random() * 16777216).toString(16),
        started_epoch_ms: started,
        stopped_epoch_ms: null,
        stop_reason: null,
        metadata: {
          device_model_reported: 'Xiaomi Smart Band 9 Pro',
          firmware_reported: options.firmware || '3.1.175',
          mi_fitness_version_reported: '3.59.1',
          requested_interval: 'game',
          requested_duration_ms: duration,
          acceleration_unit: 'unknown',
          hardware_timestamp: false,
          time_source: 'Date.now_callback_arrival',
          label_source: 'manual_instruction',
          activity_instruction: options.label || 'still',
          wrist_side: 'not_recorded',
          app_version: '0.1.0'
        },
        row_fields: ['callback_elapsed_ms', 'x', 'y', 'z', 'page_state'],
        rows: [], events: [],
        diagnostics: { invalid_samples: 0, clock_regressions: 0, zero_intervals: 0 }
      };
      return snapshot();
    },
    append: function (value, pageState) {
      if (!active) return { accepted: false, stopReason: record && record.stop_reason };
      const timestamp = now();
      const elapsed = timestamp - record.started_epoch_ms;
      if (!finite(timestamp)) {
        record.diagnostics.invalid_samples++;
        return { accepted: false };
      }
      if (elapsed >= duration) {
        stop('duration', timestamp);
        return { accepted: false, stopReason: 'duration' };
      }
      if (!value || !finite(value.x) || !finite(value.y) || !finite(value.z)) {
        record.diagnostics.invalid_samples++;
        return { accepted: false };
      }
      if (previousElapsed !== null) {
        if (elapsed < previousElapsed) record.diagnostics.clock_regressions++;
        if (elapsed === previousElapsed) record.diagnostics.zero_intervals++;
      }
      previousElapsed = elapsed;
      record.rows.push([elapsed, value.x, value.y, value.z, pageState || 'visible']);
      if (record.rows.length >= limit) {
        stop('sample_limit', timestamp);
        return { accepted: true, stopReason: 'sample_limit' };
      }
      return { accepted: true };
    },
    event: function (type, detail) {
      if (active && record.events.length < 100) {
        record.events.push({ elapsed_ms: now() - record.started_epoch_ms,
          type: type, detail: detail === undefined ? null : String(detail) });
      }
    },
    stop: stop,
    snapshot: snapshot,
    isActive: function () { return active; },
    count: function () { return record ? record.rows.length : 0; }
  };
}

function crc32(text) {
  let crc = -1;
  for (let i = 0; i < text.length; i++) {
    crc ^= text.charCodeAt(i);
    for (let bit = 0; bit < 8; bit++) crc = (crc >>> 1) ^ (0xedb88320 & -(crc & 1));
  }
  return ('00000000' + ((crc ^ -1) >>> 0).toString(16)).slice(-8);
}

function encodeChunks(record, payloadSize) {
  if (!record || !record.rows || record.rows.length === 0) throw new Error('没有样本，不能导出');
  const size = payloadSize || 320;
  if (size < 80 || size > 1000 || Math.floor(size) !== size) throw new Error('无效分片大小');
  // ASCII permits identical CRC computation in JS, QR readers and Python.
  const body = JSON.stringify(record).replace(/[\u007f-\uffff]/g, function (char) {
    return '\\u' + ('0000' + char.charCodeAt(0).toString(16)).slice(-4);
  });
  const checksum = crc32(body);
  const total = Math.ceil(body.length / size);
  const frames = [];
  for (let index = 0; index < total; index++) {
    frames.push(['IMU9P', '1', record.session_id, String(index + 1), String(total),
      checksum, body.slice(index * size, (index + 1) * size)].join('|'));
  }
  return frames;
}

module.exports = { createRecorder: createRecorder, crc32: crc32, encodeChunks: encodeChunks };
