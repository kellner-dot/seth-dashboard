/* KaviTV Scheduler — web UI.
 * Loads the public KaviTV lineup (channels.json) + curated schedules
 * (schedules.json) from the dashboard repo, lets Seth program the 24/7
 * channels, and sends the result to the RVG bridge (or downloads it).
 */
"use strict";

const REPO_BASE = "https://kellner-dot.github.io/seth-dashboard/kavitv";
const $ = (id) => document.getElementById(id);

const state = {
  channels: [],
  schedules: {},       // "YYYY-MM-DD" -> {channel: schedule}
  channelNum: 30,
  date: null,          // broadcast day YYYY-MM-DD
  working: null,       // editable schedule for channel+date
  pool: [],
  selectedMovie: null, // ref of movie picked from pool, awaiting placement
  dirty: false,
};

/* ---------- utils ---------- */
function toast(msg, ms = 2600) {
  const t = $("toast");
  t.textContent = msg;
  t.classList.remove("hidden");
  clearTimeout(t._h);
  t._h = setTimeout(() => t.classList.add("hidden"), ms);
}
function todayStr() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
function hhmmToMin(s) {
  const [h, m] = s.split(":").map(Number);
  return h * 60 + m;
}
// Seeded RNG (mulberry32) with a string seed hash.
function seededRng(seedStr) {
  let h = 2166136261;
  for (let i = 0; i < seedStr.length; i++) {
    h ^= seedStr.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  let a = h >>> 0;
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
function daypart(hh) {
  if (hh < 6) return "overnight";
  if (hh < 12) return "morning";
  if (hh < 17) return "afternoon";
  if (hh < 20) return "evening";
  if (hh < 23) return "prime";
  return "late";
}

/* ---------- data loading ---------- */
async function loadData() {
  const [ch, sch] = await Promise.all([
    fetch(`${REPO_BASE}/channels.json`).then((r) => r.json()),
    fetch(`${REPO_BASE}/schedules.json`).then((r) => (r.ok ? r.json() : { days: {} })).catch(() => ({ days: {} })),
  ]);
  state.channels = (ch.channels || []).filter((c) => c.kind === "movies");
  state.schedules = sch.days || {};
  // curated flagships first, then by number
  state.channels.sort((a, b) => (b.curated ? 1 : 0) - (a.curated ? 1 : 0) || a.number - b.number);
  if (!state.channels.some((c) => c.number === state.channelNum)) {
    state.channelNum = state.channels[0].number;
  }
}

/* ---------- channel list ---------- */
function renderChannels() {
  const el = $("channels");
  el.innerHTML = "";
  for (const c of state.channels) {
    const d = document.createElement("div");
    d.className = "ch-item" + (c.number === state.channelNum ? " active" : "");
    d.innerHTML = `<span class="num">${c.number}</span><span class="nm">${esc(c.name)}</span>` +
      (c.curated ? `<span class="cur">curated</span>` : "");
    d.onclick = () => { state.channelNum = c.number; state.dirty = false; refresh(); };
    el.appendChild(d);
  }
}
function getChannel() {
  return state.channels.find((c) => c.number === state.channelNum);
}

/* ---------- working schedule ---------- */
function getSavedSchedule() {
  const day = state.schedules[state.date] || {};
  return day[state.channelNum] || day[String(state.channelNum)] || null;
}
function ensureWorking() {
  if (!state.working) {
    const saved = getSavedSchedule();
    if (saved) {
      state.working = JSON.parse(JSON.stringify(saved));
    } else {
      state.working = {
        channel: state.channelNum, date: state.date,
        generated_at: new Date().toISOString(), generated_by: "manual",
        items: [],
      };
    }
  }
  return state.working;
}

/* ---------- timeline ---------- */
function esc(s) {
  return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
function renderTimeline() {
  const ch = getChannel();
  $("channelName").textContent = `${ch.number} — ${ch.name}`;
  const w = ensureWorking();
  $("channelMeta").textContent =
    `${w.items.length} programs · ${ch.tagline || ""}` +
    (state.dirty ? " · ● unsaved changes" : "") +
    (w.generated_by === "auto" ? " · auto-generated" : "");

  const tl = $("timeline");
  tl.innerHTML = "";
  const items = [...w.items].sort((a, b) => hhmmToMin(a.start) - hhmmToMin(b.start));
  // broadcast-day order: 06:00 first
  items.sort((a, b) => ((hhmmToMin(a.start) - 360 + 1440) % 1440) - ((hhmmToMin(b.start) - 360 + 1440) % 1440));

  let prevEnd = 360; // 06:00
  for (const it of items) {
    const s = hhmmToMin(it.start);
    const sb = (s - 360 + 1440) % 1440;
    const pb = (prevEnd - 360 + 1440) % 1440;
    if (sb > pb + 5) {
      tl.appendChild(gapEl(prevEnd, s));
    }
    tl.appendChild(progEl(it));
    prevEnd = hhmmToMin(it.end);
  }
  // tail gap to 06:00 next day
  if ((prevEnd - 360 + 1440) % 1440 < 1430) {
    tl.appendChild(gapEl(prevEnd, 360, true));
  }
  renderPool();
}
function fmtRange(sMin, eMin) {
  const f = (m) => `${String(Math.floor(m / 60) % 24).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
  return `${f(sMin)}–${f(eMin)}`;
}
function progEl(it) {
  const d = document.createElement("div");
  d.className = `prog slot-${it.slot || "manual"}`;
  d.innerHTML =
    `<div class="time">${esc(it.start)}–${esc(it.end)}</div>` +
    `<div class="info"><div class="title">${esc(it.title)}${it.pinned ? ' <span class="pin-badge">📌</span>' : ""}</div>` +
    `<div class="sub">${esc(it.year || "")} · ${esc((it.genres || []).join(" / "))} · ★${it.rating == null ? "–" : it.rating} · ${(it.runtime_estimated ? "~" : "") + it.runtime_min} min</div></div>` +
    `<span class="slot">${esc(it.slot || "")}</span>`;
  d.onclick = () => openDrawer(it);
  return d;
}
function gapEl(fromMin, toMin, wrap) {
  const d = document.createElement("div");
  d.className = "gap";
  const label = wrap ? `＋ fill to 06:00` : `＋ ${fmtRange(fromMin, toMin)} — tap to schedule`;
  d.textContent = label;
  d.onclick = () => {
    if (state.selectedMovie) {
      placeMovie(state.selectedMovie, fromMin);
    } else {
      toast("Pick a movie from the pool first, then tap a gap");
      $("poolSearch").focus();
    }
  };
  return d;
}

/* ---------- movie pool ---------- */
function getPool() {
  const ch = getChannel();
  // Curated channels keep movies without runtime data; the scheduler
  // estimates 95 min (Emby lacks RunTimeTicks for most of the library).
  return (ch.programs || []).map((m) =>
    m.runtime_min ? m : { ...m, runtime_min: 95, runtime_estimated: true }
  );
}
function rtLabel(m) {
  return (m.runtime_estimated ? "~" : "") + m.runtime_min + "m";
}
function renderPool() {
  const q = $("poolSearch").value.trim().toLowerCase();
  let pool = getPool();
  state.pool = pool;
  if (q) {
    pool = pool.filter((m) => (m.title + " " + (m.year || "")).toLowerCase().includes(q));
  }
  $("poolStats").textContent = `${pool.length} movies in pool`;
  const el = $("pool");
  el.innerHTML = "";
  for (const m of pool.slice(0, 300)) {
    const d = document.createElement("div");
    d.className = "movie" + (state.selectedMovie === m.ref ? " selected" : "");
    d.innerHTML = `<div class="t">${esc(m.title)}</div>` +
      `<div class="m">${esc(m.year || "")} · ${esc((m.genres || []).join("/"))} · ★${m.rating == null ? "–" : m.rating} · ${rtLabel(m)}</div>`;
    d.onclick = () => {
      state.selectedMovie = state.selectedMovie === m.ref ? null : m.ref;
      renderPool();
      if (state.selectedMovie) toast(`Selected "${m.title}" — tap a gap in the timeline to place it`);
    };
    el.appendChild(d);
  }
  if (pool.length > 300) {
    const more = document.createElement("div");
    more.className = "m";
    more.style.cssText = "color:var(--dim);font-size:.8rem;padding:8px;";
    more.textContent = `…and ${pool.length - 300} more (refine search)`;
    el.appendChild(more);
  }
}
function placeMovie(ref, atMin) {
  const m = getPool().find((x) => x.ref === ref);
  if (!m) return;
  const w = ensureWorking();
  const hh = Math.floor(atMin / 60) % 24, mm = atMin % 60;
  const start = `${String(hh).padStart(2, "0")}:${String(mm).padStart(2, "0")}`;
  const endMin = atMin + (m.runtime_min || 90);
  const end = `${String(Math.floor(endMin / 60) % 24).padStart(2, "0")}:${String(endMin % 60).padStart(2, "0")}`;
  // remove any program overlapping the new slot
  w.items = w.items.filter((it) => {
    const s = hhmmToMin(it.start), e = hhmmToMin(it.end);
    const ns = atMin, ne = endMin;
    return e <= ns || s >= ne;
  });
  w.items.push({
    ref: m.ref, title: m.title, year: m.year, runtime_min: m.runtime_min,
    rating: m.rating, genres: (m.genres || []).slice(0, 2),
    start, end, slot: daypart(hh), pinned: true,
  });
  w.generated_by = "manual";
  state.selectedMovie = null;
  state.dirty = true;
  renderTimeline();
  toast(`📌 "${m.title}" placed at ${start}`);
}

/* ---------- drawer (program detail) ---------- */
let drawerItem = null;
function openDrawer(it) {
  drawerItem = it;
  $("drawerTitle").textContent = `${it.title} (${it.year || "?"})`;
  $("drawerBody").innerHTML =
    `<div class="row"><span class="lbl">Time</span>${esc(it.start)} – ${esc(it.end)}</div>` +
    `<div class="row"><span class="lbl">Slot</span>${esc(it.slot || "")}${it.pinned ? " · 📌 pinned" : ""}</div>` +
    `<div class="row"><span class="lbl">Rating</span>★${it.rating == null ? "–" : it.rating} · ${it.runtime_min} min</div>` +
    `<div class="row"><span class="lbl">Genres</span>${esc((it.genres || []).join(" / "))}</div>` +
    `<div class="actions">` +
    `<button id="dPin">${it.pinned ? "Unpin" : "Pin"}</button>` +
    `<button id="dReplace">Replace…</button>` +
    `<button id="dRemove" style="border-color:var(--accent);color:var(--accent)">Remove</button>` +
    `</div>` +
    `<p class="hint" style="color:var(--dim);font-size:.8rem">Replace: pick a movie in the pool, close this, then tap the gap left behind.</p>`;
  $("drawer").classList.remove("hidden");
  $("dPin").onclick = () => { it.pinned = !it.pinned; state.dirty = true; $("drawer").classList.add("hidden"); renderTimeline(); };
  $("dRemove").onclick = () => {
    const w = ensureWorking();
    w.items = w.items.filter((x) => x !== it);
    state.dirty = true;
    $("drawer").classList.add("hidden");
    renderTimeline();
  };
  $("dReplace").onclick = () => {
    const w = ensureWorking();
    w.items = w.items.filter((x) => x !== it);
    state.dirty = true;
    $("drawer").classList.add("hidden");
    renderTimeline();
    toast("Pick a replacement from the movie pool, then tap the gap");
    $("poolSearch").focus();
  };
}

/* ---------- auto-fill (JS port of scheduler.py) ---------- */
function autoFill() {
  const ch = getChannel();
  const pool = getPool();
  if (!pool.length) { toast("No movies in this channel's pool"); return; }
  const rng = seededRng(`kavitv-sched:${ch.number}:${state.date}`);
  const pick = (arr) => arr[Math.floor(rng() * arr.length)];

  // 48h exclusion from saved schedules
  const banned = new Set();
  const days = Object.keys(state.schedules).filter((d) => d < state.date).sort().slice(-2);
  for (const d of days) {
    const s = state.schedules[d][ch.number] || state.schedules[d][String(ch.number)];
    if (s) for (const it of s.items) banned.add(it.ref);
  }
  // keep existing pins
  const w = ensureWorking();
  const pins = w.items.filter((i) => i.pinned).map((i) => ({ ref: i.ref, start: i.start }));
  const byRef = Object.fromEntries(pool.map((m) => [m.ref, m]));

  const rating = (m) => (typeof m.rating === "number" ? m.rating : 0);
  const genres = (m) => (m.genres || []).map((g) => g.toLowerCase());
  const decade = (m) => (m.year ? Math.floor(m.year / 10) * 10 : 0);
  const prefer = {
    morning: (m) => rating(m) >= 6 && genres(m).some((g) => ["comedy", "family", "animation", "music", "adventure"].includes(g)),
    afternoon: (m) => (m.runtime_min || 999) < 115,
    evening: (m) => rating(m) >= 7.0,
    prime: (m) => rating(m) >= 7.5,
    late: (m) => rating(m) >= 6.5,
    overnight: (m) => rating(m) === 0 || rating(m) < 6.5,
  };
  const keyFn = {
    prime: (m) => -rating(m),
    evening: (m) => -rating(m),
    overnight: (m) => -(m.runtime_min || 0),
  };
  function choose(cands, part, avoidSame) {
    let c = cands;
    const liked = c.filter(prefer[part]);
    if (liked.length) c = liked;
    if (avoidSame) {
      const spaced = c.filter((m) => !(genres(m)[0] === avoidSame[0] && decade(m) === avoidSame[1]));
      if (spaced.length) c = spaced;
    }
    if (keyFn[part]) {
      c = [...c].sort(keyFn[part]).slice(0, 5);
    }
    return c.length ? pick(c) : null;
  }

  const pinTimes = pins
    .map((p) => ({ min: hhmmToMin(p.start), m: byRef[p.ref] }))
    .filter((p) => p.m)
    .sort((a, b) => a.min - b.min);

  const items = [];
  const used = new Set(banned);
  let recent = [];
  const emit = (m, startMin, part, pinned) => {
    const dur = m.runtime_min || 90;
    const f = (x) => `${String(Math.floor(x / 60) % 24).padStart(2, "0")}:${String(x % 60).padStart(2, "0")}`;
    items.push({
      ref: m.ref, title: m.title, year: m.year, runtime_min: dur,
      runtime_estimated: !!m.runtime_estimated,
      rating: m.rating, genres: (m.genres || []).slice(0, 2),
      start: f(startMin), end: f(startMin + dur), slot: part, pinned,
    });
    used.add(m.ref);
    recent.push([genres(m)[0] || "", decade(m)]);
    recent = recent.slice(-2);
    return startMin + dur + 3;
  };

  let t = 360, end = 1800;
  let pinIdx = 0;
  while (t < end) {
    const hh = Math.floor(t / 60) % 24;
    const part = daypart(hh);
    const avoid = recent.length >= 2 && recent[0][0] === recent[1][0] && recent[0][1] === recent[1][1] ? recent[1] : null;
    // next pin after t?
    const nextPin = pinTimes.slice(pinIdx).find((p) => p.min > t % 1440 || (p.min + 1440) > t);
    let deadline = null, pinMovie = null;
    if (nextPin) {
      // pin clock time -> broadcast-absolute minutes
      const abs = nextPin.min < 360 ? nextPin.min + 1440 : nextPin.min;
      if (abs > t && abs < end) { deadline = abs; pinMovie = nextPin.m; }
    }
    let cands = pool.filter((m) => !used.has(m.ref) && m.runtime_min);
    if (deadline != null) {
      const room = deadline - t;
      const fit = cands.filter((m) => (m.runtime_min || 999) <= room);
      if (fit.length) {
        const m = choose(fit, part, avoid);
        if (m) { t = emit(m, t, part, false); continue; }
      }
      // bumper gap to the pin
      t = emit(pinMovie, deadline, daypart(Math.floor(deadline / 60) % 24), true);
      pinIdx = pinTimes.indexOf(nextPin) + 1;
      continue;
    }
    let m = choose(cands, part, avoid);
    if (!m) {
      const relax = pool.filter((x) => x.runtime_min && !items.some((i) => i.ref === x.ref));
      m = relax.length ? pick(relax) : null;
    }
    if (!m) break;
    t = emit(m, t, part, false);
  }

  state.working = {
    channel: ch.number, date: state.date,
    generated_at: new Date().toISOString(), generated_by: "auto",
    items,
  };
  state.dirty = true;
  renderTimeline();
  toast(`✨ Auto-filled ${items.length} programs for ${ch.name}`);
}

/* ---------- EPG preview ---------- */
function epgPreview() {
  const grid = $("epgGrid");
  const now = new Date();
  const nowMin = now.getHours() * 60 + now.getMinutes();
  let html = `<table><tr><th>Ch</th><th>Channel</th><th>Now</th><th>Next</th></tr>`;
  const scheds = state.schedules[state.date] || {};
  for (const ch of state.channels.slice(0, 12)) {
    const s = scheds[ch.number] || scheds[String(ch.number)];
    let nowT = "—", nextT = "—", nowCls = "";
    if (s && s.items.length) {
      const items = [...s.items].sort((a, b) => ((hhmmToMin(a.start) - 360 + 1440) % 1440) - ((hhmmToMin(b.start) - 360 + 1440) % 1440));
      const bmin = (nowMin - 360 + 1440) % 1440;
      for (let i = 0; i < items.length; i++) {
        const a = (hhmmToMin(items[i].start) - 360 + 1440) % 1440;
        const b = (hhmmToMin(items[i].end) - 360 + 1440) % 1440;
        const bb = b <= a ? b + 1440 : b;
        const nb = bmin < a ? bmin + 1440 : bmin;
        if (a <= nb && nb < bb) {
          nowT = `${items[i].start} ${esc(items[i].title)}`;
          const n = items[(i + 1) % items.length];
          nextT = `${n.start} ${esc(n.title)}`;
          nowCls = "now";
          break;
        }
      }
    } else if (ch.programs && ch.programs.length) {
      nowT = "(seeded shuffle — no curated schedule)";
    }
    html += `<tr><td>${ch.number}</td><td>${esc(ch.name)}</td><td class="${nowCls}">${nowT}</td><td>${nextT}</td></tr>`;
  }
  grid.innerHTML = html + "</table>";
  $("epgModal").classList.remove("hidden");
}

/* ---------- send / download ---------- */
function bridgeSettings() {
  return {
    url: (localStorage.getItem("kavitv.bridgeUrl") || "").replace(/\/$/, ""),
    token: localStorage.getItem("kavitv.bridgeToken") || "",
  };
}
async function sendSchedule() {
  const w = ensureWorking();
  if (!w.items.length) { toast("Nothing to send — schedule is empty"); return; }
  const { url, token } = bridgeSettings();
  if (!url) {
    downloadSchedule();
    toast("No bridge URL set — downloaded JSON instead (⚙️ to configure)");
    return;
  }
  try {
    const r = await fetch(`${url}/rvd/kavitv/schedule`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-RVD-Token": token },
      body: JSON.stringify({ channel: w.channel, date: w.date, items: w.items }),
    });
    const j = await r.json();
    if (!r.ok) throw new Error(j.error || r.status);
    state.dirty = false;
    renderTimeline();
    toast(`📡 Schedule sent for ch${w.channel} on ${w.date}`);
  } catch (e) {
    downloadSchedule();
    toast(`Bridge unreachable (${e.message}) — downloaded JSON instead`);
  }
}
function downloadSchedule() {
  const w = ensureWorking();
  const blob = new Blob([JSON.stringify({ [w.date]: { [w.channel]: w } }, null, 1)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `kavitv-schedule-ch${w.channel}-${w.date}.json`;
  a.click();
  URL.revokeObjectURL(a.href);
}

/* ---------- refresh / init ---------- */
function refresh() {
  state.working = null;
  state.selectedMovie = null;
  renderChannels();
  renderTimeline();
}
async function init() {
  state.date = todayStr();
  $("datePicker").value = state.date;
  try {
    await loadData();
  } catch (e) {
    toast("Failed to load KaviTV data: " + e.message);
    return;
  }
  if (!state.channels.length) { toast("No movie channels found"); return; }
  refresh();

  $("datePicker").onchange = (e) => {
    state.date = e.target.value || todayStr();
    state.dirty = false;
    refresh();
  };
  $("autoFillBtn").onclick = autoFill;
  $("sendBtn").onclick = sendSchedule;
  $("epgBtn").onclick = epgPreview;
  $("epgClose").onclick = () => $("epgModal").classList.add("hidden");
  $("epgModal").onclick = (e) => { if (e.target.id === "epgModal") $("epgModal").classList.add("hidden"); };
  $("drawerClose").onclick = () => $("drawer").classList.add("hidden");
  $("drawer").onclick = (e) => { if (e.target.id === "drawer") $("drawer").classList.add("hidden"); };
  $("poolSearch").oninput = renderPool;
  $("settingsBtn").onclick = () => {
    const p = $("settingsPanel");
    p.classList.toggle("hidden");
    const s = bridgeSettings();
    $("bridgeUrl").value = s.url;
    $("bridgeToken").value = s.token;
  };
  $("saveSettings").onclick = () => {
    localStorage.setItem("kavitv.bridgeUrl", $("bridgeUrl").value.trim());
    localStorage.setItem("kavitv.bridgeToken", $("bridgeToken").value);
    $("settingsPanel").classList.add("hidden");
    toast("Bridge settings saved (this browser only)");
  };
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { $("drawer").classList.add("hidden"); $("epgModal").classList.add("hidden"); }
  });
}
init();
