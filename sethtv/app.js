/* SethTV — live-only TV app. No library browsing, no resume points:
   the schedule is the boss. DPAD: up/down surf, OK opens guide, BACK closes. */
(function () {
'use strict';
var RELAY = 'http://10.0.0.98:8099';
var TZ = 'America/New_York';

var video = document.getElementById('video');
var statusEl = document.getElementById('status');
var statusMsg = document.getElementById('status-msg');
var osd = document.getElementById('osd');
var guideEl = document.getElementById('guide');
var rowsEl = document.getElementById('rows');
var liveDot = document.getElementById('live-dot');
var clockEl = document.getElementById('clock');
var gclockEl = document.getElementById('gclock');

var state = {
  mode: 'boot',            // boot | watch | guide
  live: false,             // relay reachable?
  channels: [],            // [{id,number,name,tagline,now,now_kind,next,slots?}]
  cur: 0,                  // index into channels
  hls: null,
  osdTimer: null,
  selRow: 0, selCol: 0,    // guide cursor
  guideProgs: [],          // per-row program lists rendered
};

function $(id) { return document.getElementById(id); }
function fmtClock(ms) {
  return new Date(ms).toLocaleTimeString('en-US', {hour: 'numeric', minute: '2-digit', timeZone: TZ});
}
function fmtHM(ms) {
  return new Date(ms).toLocaleTimeString('en-US', {hour: 'numeric', minute: '2-digit', hour12: true, timeZone: TZ});
}
function progTitle(p) {
  if (!p) return '—';
  var t = p.title || 'SethTV';
  if (p.series) t = p.series + (p.season ? ' S' + p.season + 'E' + p.episode : '') + ': ' + t;
  return t;
}
function progMeta(p) {
  if (!p) return '';
  var bits = [];
  if (p.year) bits.push(p.year);
  if (p.genres && p.genres.length) bits.push(p.genres.slice(0, 3).join(' · '));
  if (p.rating) bits.push('★ ' + Number(p.rating).toFixed(1));
  return bits.join('   ');
}
function progress(p, nowMs) {
  if (!p || !p.stop_ms || p.stop_ms <= p.start_ms) return 0;
  return Math.min(1, Math.max(0, (nowMs - p.start_ms) / (p.stop_ms - p.start_ms)));
}

/* ---------------- data ---------------- */
function fetchJSON(url, timeoutMs) {
  return new Promise(function (resolve, reject) {
    var to = setTimeout(function () { reject(new Error('timeout')); }, timeoutMs || 5000);
    fetch(url).then(function (r) {
      clearTimeout(to);
      if (!r.ok) throw new Error('http ' + r.status);
      return r.json();
    }).then(resolve, function (e) { clearTimeout(to); reject(e); });
  });
}

function slotToProg(slot) {
  var item = slot.item || {};
  return {
    title: item.name || slot.title, series: item.series, season: item.season,
    episode: item.episode, year: item.year, genres: item.genres, overview: item.overview,
    rating: item.rating, item_id: item.id, start_ms: slot.start_ms, stop_ms: slot.stop_ms,
    kind: slot.kind,
  };
}

function nowNextFromSlots(slots, at) {
  var i = 0;
  while (i < slots.length && slots[i].start_ms <= at) i++;
  i--;
  if (i < 0) return {now: null, next: slots.length ? slotToProg(slots[0]) : null};
  var cur = slotToProg(slots[i]);
  cur.offset_ms = Math.max(0, at - slots[i].start_ms);
  var nxt = (i + 1 < slots.length) ? slotToProg(slots[i + 1]) : null;
  return {now: cur, next: nxt};
}

function boot() {
  tickClock();
  setInterval(tickClock, 15000);
  // 1) try the LAN relay (live mode: guide + tune URLs)
  fetchJSON(RELAY + '/api/guide', 4000).then(function (g) {
    state.live = true;
    state.channels = g.channels;
    enterWatch(0);
  }, function () {
    // 2) fallback: static schedule from GitHub Pages (guide only, no playback)
    statusMsg.textContent = 'Home relay unreachable — loading the published schedule (guide only).';
    fetchJSON('./schedule.json', 8000).then(function (sched) {
      var at = Date.now();
      state.live = false;
      state.channels = sched.channels.map(function (ch) {
        var nn = nowNextFromSlots(ch.slots, at);
        return {id: ch.id, number: ch.number, name: ch.name, tagline: ch.tagline,
                now: nn.now, now_kind: nn.now && nn.now.kind, next: nn.next, slots: ch.slots};
      });
      enterWatch(0);
      showOsdNote('Relay offline — guide only. Playback needs the home PC relay.');
    }, function () {
      statusMsg.textContent = 'Could not reach the relay or the published schedule. Check the network and press OK to retry.';
      state.mode = 'dead';
    });
  });
}

function refreshGuideData() {
  if (!state.live || !state.channels.length) return;
  fetchJSON(RELAY + '/api/guide', 5000).then(function (g) {
    state.channels = g.channels;
    if (state.mode === 'guide') renderGuide();
    else if (state.mode === 'watch') showOsd(state.cur, 2500);
  }, function () {});
}

/* ---------------- player ---------------- */
function playUrl(url) {
  if (state.hls) { try { state.hls.destroy(); } catch (e) {} state.hls = null; }
  if (window.Hls && window.Hls.isSupported()) {
    var hls = new window.Hls({maxBufferLength: 30, liveSyncDurationCount: 3});
    state.hls = hls;
    hls.loadSource(url);
    hls.attachMedia(video);
    hls.on(window.Hls.Events.MANIFEST_PARSED, function () { video.play().catch(function () {}); });
    hls.on(window.Hls.Events.ERROR, function (_ev, data) {
      if (data.fatal) showOsdNote('Stream error — press ▲▼ to re-tune.');
    });
  } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
    video.src = url; // native HLS (just in case)
    video.play().catch(function () {});
  } else {
    showOsdNote('This TV cannot play HLS streams.');
  }
}

function tune(num) {
  var ch = state.channels[num];
  if (!ch) return;
  state.cur = num;
  if (!state.live) {
    showOsd(num, 4000);
    showOsdNote('Relay offline — cannot play. Guide data only.');
    return;
  }
  statusMsg.textContent = 'Tuning channel ' + ch.number + '…';
  statusEl.classList.remove('hidden');
  fetchJSON(RELAY + '/api/tune?channel=' + ch.number, 8000).then(function (t) {
    statusEl.classList.add('hidden');
    if (t.error || !t.hls_url) { showOsdNote('Tune failed: ' + (t.error || 'unknown')); return; }
    state.channels[num].now = t.program;
    playUrl(t.hls_url);
    showOsd(num, 6000);
  }, function () {
    statusEl.classList.add('hidden');
    showOsdNote('Relay did not answer — press ▲▼ to retry.');
  });
}

function surf(dir) {
  var n = state.channels.length;
  if (!n) return;
  tune((state.cur + dir + n) % n);
}

/* ---------------- OSD ---------------- */
function showOsd(num, ms) {
  var ch = state.channels[num];
  if (!ch) return;
  var p = ch.now;
  $('osd-num').textContent = ch.number + ' —';
  $('osd-name').textContent = ch.name;
  $('osd-prog').textContent = progTitle(p);
  $('osd-meta').textContent = (p && p.kind !== 'program' ? 'Intermission · ' : '') + progMeta(p) +
    (p ? '   ·   ' + fmtHM(p.start_ms) + ' – ' + fmtHM(p.stop_ms) : '');
  $('osd-bar').style.width = (progress(p, Date.now()) * 100).toFixed(1) + '%';
  osd.classList.remove('hidden');
  liveDot.classList.remove('hidden');
  clockEl.classList.remove('hidden');
  if (state.osdTimer) clearTimeout(state.osdTimer);
  state.osdTimer = setTimeout(function () { osd.classList.add('hidden'); }, ms || 6000);
}
function showOsdNote(text) {
  $('osd-num').textContent = '';
  $('osd-name').textContent = 'SethTV';
  $('osd-prog').textContent = text;
  $('osd-meta').textContent = '';
  $('osd-bar').style.width = '0%';
  osd.classList.remove('hidden');
  if (state.osdTimer) clearTimeout(state.osdTimer);
  state.osdTimer = setTimeout(function () { osd.classList.add('hidden'); }, 5000);
}
function tickClock() {
  var t = fmtClock(Date.now());
  clockEl.textContent = t;
  gclockEl.textContent = t;
}

/* ---------------- guide ---------------- */
function enterWatch(num) {
  state.mode = 'watch';
  guideEl.classList.add('hidden');
  statusEl.classList.add('hidden');
  tune(num);
}

function guidePrograms(ch, at) {
  // now + next 3 from slots (live mode has no slots; synthesize from now/next)
  if (ch.slots) {
    var out = [], i = 0;
    while (i < ch.slots.length && ch.slots[i].start_ms <= at) i++;
    i = Math.max(0, i - 1);
    for (var k = i; k < Math.min(ch.slots.length, i + 4); k++) out.push(slotToProg(ch.slots[k]));
    return out;
  }
  var progs = [];
  if (ch.now) progs.push(ch.now);
  if (ch.next) progs.push(ch.next);
  return progs;
}

function renderGuide() {
  var at = Date.now();
  state.guideProgs = [];
  rowsEl.innerHTML = '';
  state.channels.forEach(function (ch, r) {
    var progs = guidePrograms(ch, at);
    state.guideProgs.push(progs);
    var row = document.createElement('div');
    row.className = 'grow' + (r === state.selRow ? ' sel' : '');
    var chd = document.createElement('div');
    chd.className = 'gch';
    chd.innerHTML = '<div class="n">' + ch.number + ' <small>' + escapeHtml(ch.name) + '</small></div>' +
      '<div class="t">' + escapeHtml(ch.tagline || '') + '</div>';
    row.appendChild(chd);
    var pd = document.createElement('div');
    pd.className = 'progs';
    progs.forEach(function (p, c) {
      var card = document.createElement('div');
      card.className = 'pcard' + (c === 0 ? ' now' : '') +
        ((r === state.selRow && c === state.selCol) ? ' cursel' : '');
      var when = c === 0 ? 'NOW' : fmtHM(p.start_ms);
      card.innerHTML = '<div class="when">' + when + '</div>' +
        '<div class="pt">' + escapeHtml(progTitle(p)) + '</div>' +
        '<div class="pm">' + escapeHtml(progMeta(p)) + '</div>' +
        (c === 0 ? '<div class="pbar"><div style="width:' +
          (progress(p, at) * 100).toFixed(1) + '%"></div></div>' : '');
      pd.appendChild(card);
    });
    row.appendChild(pd);
    rowsEl.appendChild(row);
  });
}

function escapeHtml(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
    return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c];
  });
}

function openGuide() {
  state.mode = 'guide';
  state.selRow = state.cur;
  state.selCol = 0;
  refreshGuideData();
  renderGuide();
  guideEl.classList.remove('hidden');
  osd.classList.add('hidden');
}
function closeGuide() {
  state.mode = 'watch';
  guideEl.classList.add('hidden');
  showOsd(state.cur, 3000);
}
function guideMove(dr, dc) {
  var rows = state.channels.length;
  state.selRow = (state.selRow + dr + rows) % rows;
  var cols = state.guideProgs[state.selRow] ? state.guideProgs[state.selRow].length : 1;
  state.selCol = Math.min(Math.max(0, state.selCol + dc), cols - 1);
  renderGuide();
}
function guideOk() {
  var ch = state.channels[state.selRow];
  closeGuide();
  if (ch) tune(state.selRow);
}

/* ---------------- input ---------------- */
var BACK_KEYS = {27: 1, 461: 1, 10009: 1, 8: 1};
document.addEventListener('keydown', function (e) {
  var k = e.keyCode || e.which;
  if (state.mode === 'dead' && (k === 13)) { state.mode = 'boot'; statusEl.classList.remove('hidden'); boot(); return; }
  if (state.mode === 'boot' || state.mode === 'dead') return;

  if (state.mode === 'watch') {
    if (k === 38) { surf(-1); e.preventDefault(); }          // up: previous channel
    else if (k === 40) { surf(1); e.preventDefault(); }      // down: next channel
    else if (k === 13) { openGuide(); e.preventDefault(); }  // OK: guide
    else if (k === 37 || k === 39) { showOsd(state.cur, 6000); e.preventDefault(); }
    else if (BACK_KEYS[k]) { showOsd(state.cur, 6000); e.preventDefault(); }
  } else if (state.mode === 'guide') {
    if (k === 38) { guideMove(-1, 0); e.preventDefault(); }
    else if (k === 40) { guideMove(1, 0); e.preventDefault(); }
    else if (k === 37) { guideMove(0, -1); e.preventDefault(); }
    else if (k === 39) { guideMove(0, 1); e.preventDefault(); }
    else if (k === 13) { guideOk(); e.preventDefault(); }
    else if (BACK_KEYS[k]) { closeGuide(); e.preventDefault(); }
  }
});

// refresh guide data every 5 min so now/next never goes stale
setInterval(refreshGuideData, 5 * 60 * 1000);

boot();
})();
