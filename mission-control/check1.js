
/* ---------- helpers ---------- */
function esc(s){ return String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
function pill(on, txt){
  return `<span class="pill ${on===true?'on':on===false?'off':'na'}">${txt||(on?'online':'offline')}</span>`;
}
function rowline(k,v){ return `<div class="rowline"><span class="k">${k}</span><span class="v">${v}</span></div>`; }
function fmtUptime(s){
  if(s==null) return '—';
  const d=Math.floor(s/86400), h=Math.floor(s%86400/3600), m=Math.floor(s%3600/60);
  return d>0?`${d}d ${h}h`:(h>0?`${h}h ${m}m`:`${m}m`);
}
function ago(iso){
  const s=Math.floor((Date.now()-new Date(iso).getTime())/1000);
  return s<60?`${s}s ago`:s<3600?`${Math.floor(s/60)}m ago`:`${Math.floor(s/3600)}h ago`;
}
function fmtBytes(b){
  if(b==null||isNaN(b)) return '—';
  const u=['B','KB','MB','GB','TB']; let i=0;
  while(b>=1024&&i<u.length-1){b/=1024;i++;}
  return `${b>=100?Math.round(b):b.toFixed(1)} ${u[i]}`;
}
function meter(pct, cls){
  const p=Math.max(0,Math.min(100,pct));
  return `<div class="meter ${cls||''}"><i style="width:${p}%"></i></div>`;
}
function sigBars(ping){
  const bars = ping==null?0:(ping<80?4:ping<200?3:ping<500?2:1);
  let s='';
  for(let i=0;i<4;i++) s+=`<i style="height:${10+i*6}px;width:9px;border-radius:3px;display:inline-block;background:${i<bars?'var(--ok)':'rgba(255,255,255,.12)'}"></i>`;
  return `<span style="display:inline-flex;gap:6px;align-items:flex-end">${s}</span>`;
}


/* ---------- card builders (each returns {id,title,cls,icon,head,body,detail}) ---------- */
function pcCard(d){
  const dot=`<span class="dotlive ${d.online?'on':'off'}"></span>`;
  const embyOk = d.emby && d.emby.running;
  const up = d.terabox_uploaders||0;
  let dots=''; for(let i=0;i<4;i++) dots+=`<i class="${i<up?'lit':''}"></i>`;
  const sess=(d.emby_sessions||[]).map(s=>
    `<div class="sess"><b>${esc(s.device||'?')}</b> <span class="dim">· ${esc(s.client||'')}</span>`+
    (s.playing?`<br><span class="play">▶ ${esc(s.playing)}</span>`:`<br><span class="dim">(idle)</span>`)+`</div>`).join('');
  const body =
      rowline('🛰️ RVG agent', `<span class="${d.online?'ok':'bad'}">${esc(d.rvg_version||'—')}</span>`)
    + rowline('⏱️ Uptime', `<b>${fmtUptime(d.uptime_s)}</b>`)
    + meter(d.uptime_s!=null?Math.min(100,(d.uptime_s/86400)*100):0)
    + rowline('🎬 Emby', embyOk?`<span class="ok">● ${esc(d.emby.version||'')}</span>`:'<span class="bad">● down</span>')
    + rowline('☁️ Uploaders', `<span class="upl-dots">${dots}</span> <b>${up}</b>`)
    + (sess?`<div class="sesslbl">▶ Now playing</div>${sess}`:'');
  return {id:'pc', cls:'k-server', icon:'server', title:esc(d.name), sub:`${esc(d.hostname||d.id)} · ${esc(d.ip||'')}`,
    dot, pill:pill(d.online), body, detail:body};
}

function macCard(d){
  const dot=`<span class="dotlive ${d.online?'on':d.online===false?'off':'na'}"></span>`;
  const bb = d.bluebubbles && d.bluebubbles.up;
  const rvg = d.rvg_agent && d.rvg_agent.up;
  const body =
      rowline('💬 BlueBubbles', bb?'<span class="ok">● port 1234</span>':'<span class="bad">● down</span>')
    + rowline('🛰️ RVG Mac', rvg?'<span class="ok">● reachable</span>':'<span class="bad">● down</span>')
    + `<div class="stub">⚠️ Mac notifications: pending RVG Mac token</div>`;
  return {id:'mac', cls:'k-server', icon:'laptop', title:esc(d.name), sub:`${esc(d.id)} · ${esc(d.ip||'')}`,
    dot, pill:pill(d.online), body, detail:body};
}

function phoneCard(d){
  const dot=`<span class="dotlive ${d.online?'on':'off'}"></span>`;
  let body='';
  if(d.id==='iphone-xs-max'){
    body = rowline('📶 Tailnet ping', d.ping_ms!=null?`${sigBars(d.ping_ms)} <b>${d.ping_ms} ms</b>`:'<span class="dim">—</span>')
      + rowline('🔔 Push alerts', '<span class="ok">via ntfy ●</span>');
  } else {
    const up = d.rvg_agent && d.rvg_agent.up;
    body = rowline('🛰️ RVG Android', up?'<span class="ok">● agent up</span>':'<span class="bad">● down</span>')
      + rowline('🔔 Push alerts', '<span class="ok">via ntfy ●</span>');
  }
  return {id:d.id, cls:'k-phone', icon:'phone', title:esc(d.name), sub:`${esc(d.id)} · ${esc(d.ip||'')}`,
    dot, pill:pill(d.online), body, detail:body};
}

function fireTvCard(ft, pc){
  ft = ft||{};
  const active = !!ft.seen_in_emby;
  const adbOk = typeof ft.adb==='string' && !/unreachable|closed|n\/a/i.test(ft.adb);
  const dot=`<span class="dotlive ${active?'on':adbOk?'na':'off'}"></span>`;
  let body = rowline('📺 Emby', active?'<span class="ok">● streaming</span>':'<span class="dim">standby</span>');
  (ft.sessions||[]).forEach(s=>{
    body += `<div class="sess"><b>${esc(s.device||'Fire TV')}</b>`+(s.playing?`<br><span class="play">▶ ${esc(s.playing)}</span>`:'')+`</div>`;
  });
  body += `<div class="adbline"><b>ADB</b> · ${esc(ft.adb||'n/a')}</div>`;
  return {id:'firetv', cls:'k-tv', icon:'tv', title:'Fire TV Stick 4K', sub:'vega os · firetv',
    dot, pill:pill(active?'on':'na', active?'streaming':'standby'), body, detail:body};
}

function embyCard(lib, sessions){
  lib = lib||{};
  const dot=`<span class="dotlive ${lib.movies!=null?'on':'na'}"></span>`;
  const nSess=(sessions||[]).length;
  const recent=(lib.recent||[]).slice(0,4).map(t=>`<div class="sess"><b>${esc(t)}</b></div>`).join('');
  const body =
      `<div class="bigstat"><span class="n">${lib.movies!=null?lib.movies:'—'}</span><span class="u">movies</span></div>`
    + rowline('📺 Series', `<b>${lib.series!=null?lib.series:'—'}</b>`)
    + rowline('🎞️ Episodes', `<b>${lib.episodes!=null?lib.episodes:'—'}</b>`)
    + rowline('▶️ Streams', nSess?`<span class="ok">● ${nSess}</span>`:'<span class="dim">none</span>')
    + (recent?`<div class="sesslbl">🆕 Recently added</div>${recent}`:'');
  return {id:'emby', url:'http://sethserver.freeddns.org:8096', cls:'k-emby', icon:'film', title:'Emby Library', sub:'movies & tv',
    dot, pill:pill(lib.movies!=null?'on':'na', lib.movies!=null?'indexed':'syncing'), body, detail:body};
}

function teraboxCard(tb, uploaders){
  tb = tb||{};
  const has = tb.total!=null && tb.used!=null;
  const dot=`<span class="dotlive ${has?'on':'na'}"></span>`;
  const pct = has ? Math.min(100,(tb.used/tb.total)*100) : 0;
  const body = has
    ? `<div class="bigstat"><span class="n">${Math.round(pct)}%</span><span class="u">used</span></div>`
      + meter(pct, pct>85?'bad':pct>65?'warn':'')
      + rowline('💾 Used', `<b>${fmtBytes(tb.used)}</b>`)
      + rowline('💾 Free', `<b>${fmtBytes(tb.free)}</b>`)
      + rowline('⬆️ Uploaders', `<b>${uploaders||0}</b>`)
    : rowline('💾 Storage', '<span class="dim">unavailable</span>')
      + rowline('⬆️ Uploaders', `<b>${uploaders||0}</b>`);
  return {id:'terabox', url:'https://www.terabox.com', cls:'k-tb', icon:'cloud', title:'TeraBox', sub:'cloud · tb-direct',
    dot, pill:pill(has?'on':'na', has?Math.round(pct)+'% used':'syncing'), body, detail:body};
}

function biglybtCard(bb){
  bb = bb||{};
  const dot=`<span class="dotlive ${bb.running?'on':'off'}"></span>`;
  const body =
      rowline('🧲 Client', bb.running?'<span class="ok">● running</span>':'<span class="bad">● stopped</span>')
    + rowline('⏱️ Scheduler', bb.scheduler?esc(bb.scheduler):'<span class="dim">—</span>');
  return {id:'biglybt', cls:'k-bt', icon:'magnet', title:'BiglyBT', sub:'torrents · vpn-bound',
    dot, pill:pill(bb.running?'on':'off'), body, detail:body};
}

function appleMusicCard(){
  const body =
      rowline('🎧 Account', `<a class="ext" href="https://music.apple.com" target="_blank">sethryankellner@icloud.com ↗</a>`)
    + rowline('🎵 Library', `<span>My playlists &amp; library</span>`)
    + `<div class="stub">🎵 RouteNote activated 2026-10-03 — releases land here on delivery.</div>`;
  return {id:'applemusic', cls:'k-am', icon:'applemusic', title:'Apple Music', sub:'my music library',
    url:'https://music.apple.com',
    dot:`<span class="dotlive na"></span>`, pill:pill('na','web player'), body, detail:body};
}

function artistCard(){
  const body =
      `<div class="sess"><b>Tuff Old Bird</b> <span class="dim">· single</span><br><span class="dim">SoundOn appeal pending</span></div>`
    + `<div class="sess"><b>East Coast Lhack Wead</b> <span class="dim">· album</span><br><span class="dim">appeal filed</span></div>`
    + `<div class="sess"><b>Grandpa Tapes</b> <span class="dim">· single</span><br><span style="color:var(--ok)">RouteNote ready ●</span></div>`
    + rowline('RouteNote', '<span class="ok">free ●</span>')
    + rowline('SoundOn', '<span class="dim">appeals pending</span>');
  return {id:'artist', cls:'k-artist', icon:'vinyl', title:'The Artful Dodger', sub:'artist project',
    dot:`<span class="dotlive na"></span>`, pill:pill('na','3 releases'), body, detail:body};
}

function museCard(){
  const body =
      rowline('\u{1F9E0} Assistant', '<span class="ok">\u25CF Kavi</span>')
    + rowline('\u{1F4AC} Chat', '<a class="ext" href="https://claude.ai" target="_blank">claude.ai \u2197</a>')
    + rowline('\u2728; Ask', '<span class="dim">anything, anytime</span>');
  return {id:'muse', url:'https://claude.ai', cls:'k-muse', icon:'muse', title:'Muse', sub:'chat with kavi',
    dot:`<span class="dotlive on"></span>`, pill:pill('on','ai assistant'), body, detail:body};
}

function githubCard(g){
  g = g||{};
  const pub=g.public_repos||0, priv=g.private_repos||0, total=pub+priv;
  const dot=`<span class="dotlive ${total>0?'on':'na'}"></span>`;
  const body =
      rowline('📦 Public', `<b>${pub}</b>`) + (total?meter(pub/total*100):'')
    + rowline('🔒 Private', `<b>${priv}</b>`) + (total?meter(priv/total*100,'warn'):'')
    + `<div class="sesslbl">🌍 Live Pages</div>`
    + `<div class="sess"><b>seth-dashboard</b> ↗</div>`
    + `<div class="sess"><b>theartfuldodger-site</b> ↗</div>`;
  return {id:'github', url:'https://github.com/kellner-dot', cls:'k-gh', icon:'github', title:'GitHub', sub:'kellner-dot',
    dot, pill:pill(total>0, total>0?total+' repos':'syncing'), body, detail:body};
}

function kaviguardCard(kg){
  kg = kg||{};
  const empty = Object.keys(kg).length===0;
  const dot=`<span class="dotlive ${empty?'na':'on'}"></span>`;
  const body = empty
    ? rowline('🛡️ Engine', '<span class="dim">no data — check PC</span>')
    : rowline('🛡️ Engine', '<span class="ok">● active</span>');
  return {id:'kaviguard', cls:'k-kg', icon:'shield', title:'KaviGuard', sub:'pc protection',
    dot, pill:pill(empty?'na':'on', empty?'syncing':'shield up'), body, detail:body};
}

function calendarCard(){
  const items = [
    {d:'2026-10-03', t:'🏠 House warming', s:'10:00 AM'},
    {d:'2026-10-17', t:'🎃 Albany Nightmare Market', s:''},
    {d:'2026-10-22', t:'⚖️ Warner prep call', s:'1:00–2:00 PM EDT'},
    {d:'2026-11-12', t:'⚖️ Disability hearing', s:'8:15 AM ET · video'},
    {d:'2026-11-20', t:'🎶 Upstate at Billsville', s:''},
  ];
  const now=new Date();
  const tstr=now.getFullYear()+'-'+String(now.getMonth()+1).padStart(2,'0')+'-'+String(now.getDate()).padStart(2,'0');
  const body=items.map(it=>{
    const dt=new Date(it.d+'T12:00:00');
    const label=dt.toLocaleDateString('en-US',{month:'short',day:'numeric'});
    return `<div class="sess"><b>${label}</b> · ${it.t}${it.d===tstr?'<span class="cal-today">TODAY</span>':''}${it.s?`<br><span class="dim">${it.s}</span>`:''}</div>`;
  }).join('');
  return {id:'calendar', url:'https://calendar.google.com', cls:'k-cal', icon:'calendar', title:'Calendar', sub:'upcoming dates',
    dot:`<span class="dotlive on"></span>`, pill:pill('on','5 events'), body, detail:body};
}

function actionsRow(){
  return {id:'actions', isActions:true, title:'Quick Actions'};
}


/* ---------- Phase 1: Notification Center ---------- */
let seenAlertIds = new Set();
try{ (JSON.parse(localStorage.getItem('mc_seen_alerts')||'[]')).forEach(id=>seenAlertIds.add(id)); }catch(e){}
function alertId(a){ return (a.title||'')+'|'+(a.at||''); }

function showNotif(a){
  const stack = document.getElementById('notif-stack');
  const el = document.createElement('div');
  el.className = 'notif ' + (a.severity==='critical'?'critical':a.severity==='warn'?'warn':'');
  el.innerHTML = `<div class="ni">${a.icon||'🔔'}</div>
    <div><div class="nt">${esc(a.title||'Notification')}</div>
    <div class="nm">${esc(a.message||'')}</div></div>
    <div class="nx">BACK ✕</div>`;
  const dismiss = ()=>{
    el.classList.add('out');
    setTimeout(()=>el.remove(), 350);
    seenAlertIds.add(alertId(a));
    try{ localStorage.setItem('mc_seen_alerts', JSON.stringify([...seenAlertIds].slice(-50))); }catch(e){}
  };
  el.querySelector('.nx').onclick = dismiss;
  el.onclick = (e)=>{ if(e.target.closest('.nx')) return; dismiss(); };
  stack.appendChild(el);
  // auto-dismiss after 12s (critical stays until dismissed)
  if(a.severity!=='critical') setTimeout(()=>{ if(el.parentNode) dismiss(); }, 12000);
  // cap stack at 3
  while(stack.children.length>3) stack.firstChild.remove();
}

function processAlerts(alerts){
  (alerts||[]).forEach(a=>{
    if(!seenAlertIds.has(alertId(a))) showNotif(a);
  });
}

/* ---------- Phase 1: Kavi Briefing Card ---------- */
let briefingData = null;
async function loadBriefing(){
  try{
    const r = await fetch('briefing.json', {cache:'no-store'});
    if(r.ok) briefingData = await r.json();
  }catch(e){ /* use fallback template */ }
}
function briefingCard(){
  const b = briefingData || {
    headline:'Good day, Seth ☀️',
    greeting:"Here's your fleet at a glance.",
    bullets:['📅 Check the Calendar card for upcoming events','⚖️ Disability hearing Nov 12 — see countdown card'],
    one_thing:''
  };
  const bullets = (b.bullets||[]).map(x=>`<li>${esc(x)}</li>`).join('');
  const oneThing = b.one_thing ? `<div class="onething"><b>☝️ One thing:</b> ${esc(b.one_thing)}</div>` : '';
  const body = `<div class="bgreet">${esc(b.greeting||'')}</div><ul>${bullets}</ul>${oneThing}`;
  return {id:'briefing', cls:'', icon:'bolt', title:b.headline||'Kavi Briefing',
    sub:'morning digest', dot:`<span class="dotlive on"></span>`,
    pill:pill('on','briefing'), body,
    detail:body, isBriefing:true};
}

/* ---------- Phase 1: Hearing Countdown ---------- */
let hearingData = null;
async function loadHearing(){
  try{
    const r = await fetch('hearing.json', {cache:'no-store'});
    if(r.ok) hearingData = await r.json();
  }catch(e){}
}
function hearingCard(){
  const h = hearingData || {hearing_date:'2026-11-12', hearing_time:'8:15 AM ET', checklist:[]};
  const target = new Date(h.hearing_date+'T08:15:00-04:00');
  const now = new Date();
  const days = Math.max(0, Math.ceil((target-now)/86400000));
  const list = h.checklist||[];
  const done = list.filter(c=>c.done).length;
  const pct = list.length? Math.round(done/list.length*100):0;
  const items = list.map(c=>
    `<div class="check-item ${c.done?'done':'todo'}"><div class="cb">${c.done?'✓':''}</div><div>${esc(c.task)}</div></div>`
  ).join('');
  const body =
    `<div class="hearing-days"><span class="n">${days}</span><span class="u">days to go</span></div>`+
    rowline('📅 Date', `<b>${esc(h.hearing_date)}</b>`)+
    rowline('🕗 Time', esc(h.hearing_time||''))+
    rowline('👨‍⚖️ Judge', esc(h.judge||''))+
    `<div class="check-bar"><i style="width:${pct}%"></i></div>`+
    rowline('✅ Checklist', `<b>${done} of ${list.length}</b>`)+
    (items?`<div style="margin-top:8px;max-height:300px;overflow:hidden">${items}</div>`:'')+
    `<div class="stub" style="margin-top:12px">📋 Counts only — case details stay private.</div>`;
  return {id:'hearing', cls:'k-cal', icon:'calendar', title:'Hearing Countdown', sub:'disability case',
    dot:`<span class="dotlive ${days<=7?'na':'on'}"></span>`,
    pill:pill(days<=7?'na':'on', days+' days'), body, detail:body};
}

/* ---------- Phase 1: Photo Frame Mode ---------- */
let photosData = null, pfIdx = 0, pfTimer = null;
async function loadPhotos(){
  try{
    const r = await fetch('photos.json', {cache:'no-store'});
    if(r.ok) photosData = await r.json();
  }catch(e){}
}
function openPhotoFrame(){
  const photos = (photosData&&photosData.photos)||[];
  if(!photos.length) return;
  pfIdx = 0;
  document.getElementById('photoframe').classList.add('open');
  showPhoto();
  clearInterval(pfTimer);
  pfTimer = setInterval(()=>{ pfIdx=(pfIdx+1)%photos.length; showPhoto(); }, 8000);
}
function showPhoto(){
  const photos = (photosData&&photosData.photos)||[];
  if(!photos.length) return;
  const p = photos[pfIdx];
  const img = document.getElementById('pf-img');
  img.style.opacity = 0;
  setTimeout(()=>{
    img.src = p.url;
    img.onload = ()=>{ img.style.opacity = 1; };
    // fallback if image fails
    setTimeout(()=>{ img.style.opacity = 1; }, 1500);
  }, 300);
  document.getElementById('pf-title').textContent = p.title||'';
  document.getElementById('pf-loc').textContent = p.location||'';
  document.getElementById('pf-count').textContent = `${pfIdx+1} / ${photos.length}`;
}
function closePhotoFrame(){
  document.getElementById('photoframe').classList.remove('open');
  clearInterval(pfTimer);
}
function photoFrameOpen(){
  return document.getElementById('photoframe').classList.contains('open');
}
function pfNav(dir){
  const photos = (photosData&&photosData.photos)||[];
  if(!photos.length) return;
  pfIdx = (pfIdx+dir+photos.length)%photos.length;
  showPhoto();
  clearInterval(pfTimer);
  pfTimer = setInterval(()=>{ pfIdx=(pfIdx+1)%photos.length; showPhoto(); }, 8000);
}

/* ---------- Phase 1: Morning Briefing View ---------- */
function isMorning(){
  const h = new Date().getHours();
  return h < 12;
}



/* ============================================================
   NETFLIX-STYLE REDESIGN CORE
   Hero banner + 16:9 poster rows + translateX scrolling
   ============================================================ */
const STATUS_URL = 'status.json';
let ROWS = [];          // [{label, cards:[...]}]
let focus = {zone:'rows', r:0, c:0};
let heroActions = [];   // [{id,label,ghost}]
let heroSubject = null; // {type, card?, item?}
let npData = null;
let spotlightData = null;
let rowX = [];

/* ---------- poster stat lines ---------- */
function posterStat(c, j, ctx){
  switch(c.id){
    case 'pc': { const d=ctx.pc; return d ? `RVG ${d.rvg_version||'—'} · up ${fmtUptime(d.uptime_s)}` : ''; }
    case 'mac': { const d=ctx.mac; const bb=d&&d.bluebubbles&&d.bluebubbles.up; const rvg=d&&d.rvg_agent&&d.rvg_agent.up;
      return `BlueBubbles ${bb?'up':'down'} · RVG ${rvg?'up':'down'}`; }
    case 'iphone-xs-max': { const d=ctx.iphone; if(!d||!d.online) return 'offline';
      return d.ping_ms!=null ? `${d.ping_ms} ms ping · ntfy` : 'online · ntfy'; }
    case 'motorola-razr-2023': { const d=ctx.razr; const up=d&&d.rvg_agent&&d.rvg_agent.up;
      return `RVG Android ${up?'up':'down'} · ntfy`; }
    case 'firetv': { const ft=(ctx.pc&&ctx.pc.firetv)||{}; return ft.seen_in_emby ? 'streaming now' : 'standby'; }
    case 'emby': { const l=j.emby_library||{}; const sp=spotlightData||{};
      const uw=sp.unwatched!=null?` · ${sp.unwatched} unwatched`:'';
      return `${l.movies!=null?l.movies:'—'} movies · ${l.series!=null?l.series:'—'} series${uw}`; }
    case 'terabox': { const t=j.terabox||{}; const has=t.total!=null&&t.used!=null;
      return has ? `${Math.round(t.used/t.total*100)}% used · ${ctx.pc&&ctx.pc.terabox_uploaders||0} up` : 'syncing'; }
    case 'biglybt': { const b=j.biglybt||{}; return b.running ? 'running' : 'stopped'; }
    case 'applemusic': return 'my music library';
    case 'artist': return '3 releases · RouteNote ready';
    case 'github': { const g=j.github||{}; const t=(g.public_repos||0)+(g.private_repos||0); return `${t} repos`; }
    case 'kaviguard': { const kg=j.kaviguard||{}; return Object.keys(kg).length ? 'shield up' : 'syncing'; }
    case 'calendar': { return 'upcoming dates'; }
    case 'hearing': { const h=hearingData||{hearing_date:'2026-11-12'}; const target=new Date(h.hearing_date+'T08:15:00-04:00');
      const days=Math.max(0,Math.ceil((target-new Date())/86400000)); return `${days} days to go`; }
    case 'act-photos': return 'slideshow · press OK';
    case 'act-iptv': return 'TV Navigator player';
    case 'act-refresh': return 'reload dashboard data';
    case 'act-search': return 'Emby \u00b7 IPTV \u00b7 Music';
    case 'act-askkavi': return 'answers on your TV';
  }
  return c.sub||'';
}

function dotClass(c){
  // derive from card dot html
  const m = /dotlive (on|off|na)/.exec(c.dot||'');
  return m ? m[1] : 'na';
}

function posterHTML(c, j, ctx){
  const stat = posterStat(c, j, ctx);
  const dc = dotClass(c);
  const icon = ICONS[c.icon] || '';
  return `<div class="poster ${c.cls||''}" data-id="${c.id}" tabindex="-1">
    <div class="art">${icon}</div>
    <div class="pinfo">
      <div class="pt">${esc(c.title)} <span class="pdot ${dc}"></span></div>
      <div class="ps">${stat}</div>
    </div>
  </div>`;
}

/* ---------- action posters ---------- */
function actionCards(){
  return [
    {id:'act-photos', cls:'k-act', icon:'film', title:'Photo Frame', sub:'his photography',
     dot:'<span class="dotlive na"></span>', pill:pill('na','slideshow'), isAction:'photos', body:'', detail:''},
    {id:'act-iptv', cls:'k-tv', icon:'tv', title:'IPTV Player', sub:'TV Navigator',
     dot:'<span class="dotlive on"></span>', pill:pill('on','player'), isAction:'iptv', body:'', detail:''},
    {id:'act-refresh', cls:'k-act', icon:'bolt', title:'Refresh', sub:'reload data',
     dot:'<span class="dotlive na"></span>', pill:pill('na','manual'), isAction:'refresh', body:'', detail:''},
    {id:'act-search', cls:'k-tv', icon:'search', title:'Search', sub:'Emby \u00b7 IPTV \u00b7 Music',
     dot:'<span class="dotlive on"></span>', pill:pill('na','search'), isAction:'search', body:'', detail:''},
    {id:'act-askkavi', cls:'k-kg', icon:'chat', title:'Ask Kavi', sub:'answers on your TV',
     dot:'<span class="dotlive on"></span>', pill:pill('na','ask'), isAction:'askkavi', body:'', detail:''},
  ];
}

/* ---------- hero ---------- */
function heroStat(n, u){ return `<div class="hstat"><div class="n">${n}</div><span class="u">${u}</span></div>`; }

function renderHero(j, ctx){
  const kickerEl=document.getElementById('hero-kicker');
  const titleEl=document.getElementById('hero-title');
  const subEl=document.getElementById('hero-sub');
  const statsEl=document.getElementById('hero-stats');
  const bulletsEl=document.getElementById('hero-bullets');
  const actionsEl=document.getElementById('hero-actions');
  const artEl=document.getElementById('hero-art');

  let kicker='', title='', sub='', stats='', bullets='', art='server', subject=null;

  const np = npData;
  if(np && Array.isArray(np.items) && np.items.length){
    const item = np.items[0];
    subject = {type:'nowplaying', item};
    kicker='▶ Now Playing';
    title=item.title||'Now Playing';
    const parts=[]; if(item.series)parts.push(item.series); if(item.user)parts.push(item.user); if(item.device)parts.push(item.device);
    sub=esc(parts.join(' · '));
    stats = item.progress_pct!=null ? heroStat(Math.round(item.progress_pct)+'%', 'watched') : '';
    art='film';
  } else if(isMorning()){
    const b = briefingData || {headline:'Good morning, Seth ☀️', greeting:"Here's your day at a glance.", bullets:[], one_thing:''};
    subject = {type:'briefing'};
    kicker='☀️ Morning Briefing';
    title=b.headline||'Good morning, Seth';
    sub=esc(b.greeting||'');
    const bl=(b.bullets||[]).slice(0,3).map(x=>`<li>${esc(x)}</li>`).join('');
    const ot=b.one_thing?`<li><b>☝️ One thing:</b> ${esc(b.one_thing)}</li>`:'';
    bullets=bl+ot;
    art='bolt';
  } else {
    const d=ctx.pc;
    const card=d?pcCard(d):null;
    subject={type:'device', card};
    kicker='★ Featured Device';
    title=d?d.name:'Gaming PC';
    sub=d?(d.online?'<span class="ok">● Online</span>':'<span class="bad">● Offline</span>')+' · RVG '+esc(d.rvg_version||'—'):'';
    if(d){
      stats = heroStat(fmtUptime(d.uptime_s),'uptime')
        + heroStat((d.emby&&d.emby.running)?esc(d.emby.version||'up'):'down','emby')
        + heroStat(String(d.terabox_uploaders||0),'uploaders');
    }
    art='server';
  }

  heroSubject=subject;
  kickerEl.textContent=kicker;
  titleEl.textContent=title;
  subEl.innerHTML=sub;
  statsEl.innerHTML=stats;
  if(bullets){ bulletsEl.innerHTML=bullets; bulletsEl.style.display='block'; }
  else { bulletsEl.innerHTML=''; bulletsEl.style.display='none'; }
  artEl.innerHTML=ICONS[art]||'';

  heroActions=[
    {id:'hero-details', label:'▶ Details', ghost:false},
    {id:'hero-photos', label:'🖼️ Photos', ghost:true},
  ];
  actionsEl.innerHTML=heroActions.map((a,i)=>
    `<button class="hbtn${a.ghost?' ghost':''}" data-ha="${i}" tabindex="-1">${a.label}</button>`).join('');
}


/* ---------- Emby Spotlight: New on Emby + Continue Watching ---------- */
function moviePoster(m, kind){
  const yr = m.year ? ` (${m.year})` : '';
  const genres = (m.genres||[]).join(' · ');
  const prog = (kind==='resume' && m.progress_pct)
    ? `<div class="mprog"><div class="mprogfill" style="width:${m.progress_pct}%"></div></div>` : '';
  const sub = kind==='resume' ? `${m.progress_pct}% watched` : genres;
  return {id:'movie-'+kind+'-'+m.name.replace(/[^a-z0-9]+/gi,'-').toLowerCase().slice(0,24),
    cls:'k-emby', icon:'film', title:m.name+yr, sub:sub,
    dot:'<span class="dotlive on"></span>', pill:pill('on', kind==='resume'?'resume':'new'),
    body:`<div class="sess"><b>${esc(m.name)}${yr}</b><br><span class="dim">${esc(genres)}${m.runtime_min?' · '+m.runtime_min+' min':''}</span></div>${prog}`,
    detail:`<div class="sess"><b>${esc(m.name)}${yr}</b></div><div class="sesslbl">${esc(genres)}</div>`+(m.runtime_min?`<div class="sess"><span class="dim">${m.runtime_min} min runtime</span></div>`:'')};
}
function spotlightRows(){
  const rows=[];
  const s=spotlightData;
  if(!s) return rows;
  if(s.new_arrivals && s.new_arrivals.length){
    rows.push({label:'\uD83C\uDFAC New on Emby', cards:s.new_arrivals.map(m=>moviePoster(m,'new'))});
  }
  if(s.continue_watching && s.continue_watching.length){
    rows.push({label:'\u25B6\uFE0F Continue Watching', cards:s.continue_watching.map(m=>moviePoster(m,'resume'))});
  }
  return rows;
}
function surpriseCard(){
  const s=spotlightData;
  if(!s || !s.surprise_pick) return null;
  const p=s.surprise_pick;
  const yr=p.year?` (${p.year})`:'';
  return {id:'act-surprise', cls:'k-act', icon:'bolt', title:'\uD83C\uDFB2 Surprise Me', sub:'random pick',
    dot:'<span class="dotlive on"></span>', pill:pill('on','random'),
    isAction:'surprise',
    body:`<div class="sess"><b>\uD83C\uDFB2 ${esc(p.name)}${yr}</b><br><span class="dim">${esc((p.genres||[]).join(' · '))}</span></div>`,
    detail:`<div class="sess"><b>${esc(p.name)}${yr}</b></div><div class="sesslbl">${esc((p.genres||[]).join(' · '))}</div><div class="sess"><span class="dim">${esc(p.overview||'')}</span></div>`};
}

/* ---------- render ---------- */
function render(j){
  // header/footer freshness
  const s=Math.floor((Date.now()-new Date(j.generated_iso).getTime())/1000);
  const live = s<420; // 7-min threshold (5-min collector cadence)
  document.getElementById('updated').innerHTML = live ? `<span class="fresh" style="color:var(--ok)">● LIVE</span> · ${ago(j.generated_iso)}` : `updated ${ago(j.generated_iso)}`;
  document.getElementById('live-txt').textContent = live ? 'LIVE' : 'STALE';
  document.getElementById('live-dot').style.color = live ? 'var(--ok)' : 'var(--warn)';
  document.getElementById('src').innerHTML = '<span class="live-tag">●</span> tv edition · read-only';
  document.getElementById('collector').textContent = (j.collector||'—').replace(/\s*\(.*\)/,'');

  const byId={}; (j.devices||[]).forEach(d=>byId[d.id]=d);
  const ctx={ pc:byId['seths-pc'], mac:byId['seths-macbook-air'], iphone:byId['iphone-xs-max'], razr:byId['motorola-razr-2023'] };

  const fleet=[];
  if(ctx.pc) fleet.push(pcCard(ctx.pc));
  if(ctx.mac) fleet.push(macCard(ctx.mac));
  if(ctx.iphone) fleet.push(phoneCard(ctx.iphone));
  if(ctx.razr) fleet.push(phoneCard(ctx.razr));
  fleet.push(fireTvCard(ctx.pc && ctx.pc.firetv, ctx.pc));

  const media=[
    embyCard(j.emby_library, ctx.pc && ctx.pc.emby_sessions),
    teraboxCard(j.terabox, ctx.pc && ctx.pc.terabox_uploaders),
    biglybtCard(j.biglybt),
    appleMusicCard(),
    artistCard(),
  ];

  const ops=[
    museCard(),
    githubCard(j.github),
    kaviguardCard(j.kaviguard),
    calendarCard(),
    hearingCard(),
  ];

  const acts=actionCards();
  const sc=surpriseCard(); if(sc) acts.unshift(sc);
  ROWS=[
    {label:'My Fleet', cards:fleet},
    {label:'Media', cards:media},
  ].concat(spotlightRows()).concat([
    {label:'Operations', cards:ops},
    {label:'Quick Actions', cards:acts},
  ]);

  renderHero(j, ctx);
  processAlerts(j.alerts);

  const keep = currentCard();
  const keepId = keep && keep.id;
  document.getElementById('rows').innerHTML = ROWS.map((r,ri)=>
    `<section class="row-sec" data-sec="${ri}">
       <div class="row-label"><span>${r.label}</span><span class="cnt">${r.cards.length}</span></div>
       <div class="row-viewport"><div class="row-track" data-row="${ri}">`+
         r.cards.map(c=>posterHTML(c,j,ctx)).join('')+
       `</div></div>
     </section>`).join('');

  // restore focus
  if(keepId){
    outer: for(let ri=0;ri<ROWS.length;ri++){
      const ci=ROWS[ri].cards.findIndex(c=>c.id===keepId);
      if(ci>=0){ focus={zone:'rows',r:ri,c:ci}; break outer; }
    }
  }
  if(focus.zone==='rows'){
    focus.r=Math.min(focus.r, ROWS.length-1);
    focus.c=Math.min(focus.c, ROWS[focus.r].cards.length-1);
  }
  rowX = ROWS.map(()=>0);
  applyFocus(true);
}

function currentCard(){
  if(focus.zone!=='rows'||!ROWS.length) return null;
  return ROWS[focus.r].cards[focus.c];
}

/* ---------- focus + translateX row scrolling ---------- */
function applyFocus(instant){
  document.querySelectorAll('.poster.focused').forEach(el=>el.classList.remove('focused'));
  document.querySelectorAll('.hbtn.focused').forEach(el=>el.classList.remove('focused'));
  if(focus.zone==='hero'){
    const btn=document.querySelector(`[data-ha="${focus.c}"]`);
    if(btn){ btn.classList.add('focused'); btn.scrollIntoView({block:'nearest', behavior:instant?'auto':'smooth'}); }
    return;
  }
  const c=currentCard(); if(!c) return;
  const el=document.querySelector(`.poster[data-id="${c.id}"]`);
  if(!el) return;
  el.classList.add('focused');
  // translateX scroll: center focused poster in viewport
  const track=document.querySelector(`.row-track[data-row="${focus.r}"]`);
  const viewport=track.parentElement;
  const pw=el.offsetWidth+26; // poster + gap
  const vpW=viewport.clientWidth;
  let x = 64 + focus.c*pw + pw/2 - vpW/2;
  const maxX=Math.max(0, track.scrollWidth - vpW);
  x=Math.max(0, Math.min(maxX, x));
  rowX[focus.r]=x;
  if(instant) track.style.transition='none';
  track.style.transform=`translateX(${-x}px)`;
  if(instant){ void track.offsetWidth; track.style.transition=''; }
  // vertical: keep row visible
  const sec=el.closest('.row-sec');
  if(sec) sec.scrollIntoView({block:'nearest', behavior:instant?'auto':'smooth'});
}

function move(dr, dc){
  if(!ROWS.length) return;
  closeOverlay();
  if(focus.zone==='hero'){
    if(dc!==0){
      focus.c=Math.max(0,Math.min(heroActions.length-1,focus.c+dc));
    } else if(dr>0){
      focus={zone:'rows',r:0,c:Math.min(focus.c,ROWS[0].cards.length-1)};
    }
    applyFocus(); return;
  }
  let r=focus.r+dr, c=focus.c+dc;
  if(dr<0 && r<0){ focus={zone:'hero',r:0,c:0}; applyFocus(); return; }
  r=Math.max(0,Math.min(ROWS.length-1,r));
  c=Math.max(0,Math.min(ROWS[r].cards.length-1,c));
  focus={zone:'rows',r,c};
  applyFocus();
}

/* ---------- overlay ---------- */
function openOverlay(){
  let icon='bolt', title='', sub='', dot='', pillHtml='', detail='', cardUrl='';
  if(focus.zone==='hero'){
    const s=heroSubject; if(!s) return;
    if(s.type==='device'&&s.card){ ({icon,title,sub,dot}=s.card); pillHtml=s.card.pill; detail=s.card.detail; cardUrl=s.card.url||''; }
    else if(s.type==='briefing'){
      const b=briefingData||{headline:'Kavi Briefing',greeting:'',bullets:[],one_thing:''};
      icon='bolt'; title=b.headline||'Kavi Briefing'; sub='morning digest'; dot='<span class="dotlive on"></span>';
      pillHtml=pill('on','briefing');
      detail=`<div style="font-size:30px;color:var(--dim);margin-bottom:14px">${esc(b.greeting||'')}</div>`+
        `<ul style="list-style:none;margin:10px 0;padding:0">`+(b.bullets||[]).map(x=>`<li style="font-size:30px;padding:12px 0;border-top:2px solid rgba(255,255,255,.07)">${esc(x)}</li>`).join('')+`</ul>`+
        (b.one_thing?`<div style="margin-top:16px;padding:18px 20px;border-radius:16px;font-size:30px;background:rgba(251,191,36,.08);border:2px solid rgba(251,191,36,.35)"><b style="color:var(--warn)">☝️ One thing:</b> ${esc(b.one_thing)}</div>`:'');
    }
    else if(s.type==='nowplaying'&&s.item){
      const it=s.item; icon='film'; title=it.title||'Now Playing'; sub=[it.series,it.user,it.device].filter(Boolean).join(' · ');
      dot='<span class="dotlive on"></span>'; pillHtml=pill('on','playing');
      detail=rowline('🎬 Title',`<b>${esc(it.title||'—')}</b>`)+rowline('📺 Progress', it.progress_pct!=null?Math.round(it.progress_pct)+'%':'—');
    }
  } else {
    const c=currentCard(); if(!c||c.isAction) return;
    ({icon,title,sub,dot}=c); pillHtml=c.pill; detail=c.detail; cardUrl=c.url||'';
  }
  document.getElementById('ov-card').innerHTML=
    `<div class="ov-head"><div class="ov-icon">${ICONS[icon]||''}</div>
     <div><h2>${title}</h2><div class="osub">${sub||''}</div></div>
     <div style="flex:1"></div>${dot}</div>
     <div>${pillHtml}</div>${detail}
     ${cardUrl?`<button id="ov-open" class="ov-btn" onclick="window.location.href='${cardUrl}'">Open →</button>`:''}
     <div class="hint">Press <b>Back</b> to close</div>`;
  const ovOpen=document.getElementById('ov-open');
  if(ovOpen){ ovOpen.onclick=()=>{ window.location.href=cardUrl; }; }
  document.getElementById('overlay').classList.add('open');
}
function closeOverlay(){ document.getElementById('overlay').classList.remove('open'); }
function overlayOpen(){ return document.getElementById('overlay').classList.contains('open'); }

/* ---------- hero + card actions ---------- */
function runHeroAction(i){
  const a=heroActions[i]; if(!a) return;
  if(a.id==='hero-details') openOverlay();
  else if(a.id==='hero-photos') openPhotoFrame();
}
function runCardAction(c){
  if(!c||!c.isAction) return;
  if(c.isAction==='photos') openPhotoFrame();
  else if(c.isAction==='iptv'){ window.location.href='../iptv/'; }
    else if(c.isAction==='surprise'){ openOverlay(c); }
  else if(c.isAction==='refresh'){ load(); }
  else if(c.isAction==='search'){ openSearchOverlay(); }
  else if(c.isAction==='askkavi'){ openAskOverlay(); }
}

/* ---------- auto-update check ---------- */
async function checkForUpdate(){
  try{
    const m=/[?&](?:b|appBuild)=(\d+)/.exec(location.search);
    if(!m) return;
    const r=await fetch('version.json',{cache:'no-store'});
    if(!r.ok) return;
    const v=await r.json();
    const latest=v.missioncontrol&&v.missioncontrol.build;
    if(latest&&latest>parseInt(m[1],10)){
      const stack=document.getElementById('notif-stack');
      const el=document.createElement('div');
      el.className='notif update';
      el.innerHTML=`<div class="ni">🔄</div><div><div class="nt">Update available — Build ${latest}</div>`+
        `<div class="nm">Relaunch Mission Control from the Fire TV home screen to get the latest.</div></div>`+
        `<div class="nx">BACK ✕</div>`;
      const dismiss=()=>{ el.classList.add('out'); setTimeout(()=>el.remove(),350); };
      el.querySelector('.nx').onclick=dismiss;
      stack.appendChild(el);
    }
  }catch(e){}
}

/* ---------- DPAD / keyboard ---------- */
document.addEventListener('keydown', e=>{
  const k=e.key;
  if(searchOpen()){ handleSearchKey(e); return; }
  if(askOpen()){ handleAskKey(e); return; }
  if(photoFrameOpen()){
    if(k==='ArrowLeft'){ pfNav(-1); e.preventDefault(); return; }
    if(k==='ArrowRight'){ pfNav(1); e.preventDefault(); return; }
    if(k==='Escape'||k==='Backspace'||k==='GoBack'){ closePhotoFrame(); e.preventDefault(); return; }
    return;
  }
  if(overlayOpen()){
    if(k==='Escape'||k==='Backspace'||k==='GoBack'){ closeOverlay(); e.preventDefault(); }
    return;
  }
  if(k==='Escape'||k==='Backspace'){
    const stack=document.getElementById('notif-stack');
    if(stack.children.length>0){ stack.firstChild.querySelector('.nx').click(); e.preventDefault(); return; }
  }
  switch(k){
    case 'ArrowLeft': move(0,-1); e.preventDefault(); break;
    case 'ArrowRight': move(0,1); e.preventDefault(); break;
    case 'ArrowUp': move(-1,0); e.preventDefault(); break;
    case 'ArrowDown': move(1,0); e.preventDefault(); break;
    case 'Enter':
      if(focus.zone==='hero') runHeroAction(focus.c);
      else { const c=currentCard(); if(c&&c.isAction) runCardAction(c); else openOverlay(); }
      e.preventDefault(); break;
    case 'p': case 'P': openPhotoFrame(); e.preventDefault(); break;
    case 'Escape': case 'Backspace': e.preventDefault(); break;
  }
});
document.addEventListener('keydown', e=>{
  if(e.keyCode===10009||e.keyCode===461){
    if(searchOpen()){ closeSearchOverlay(); e.preventDefault(); }
    else if(askOpen()){ closeAskOverlay(); e.preventDefault(); }
    else if(photoFrameOpen()){ closePhotoFrame(); e.preventDefault(); }
    else if(overlayOpen()){ closeOverlay(); e.preventDefault(); }
    else {
      const stack=document.getElementById('notif-stack');
      if(stack.children.length>0){ stack.firstChild.querySelector('.nx').click(); e.preventDefault(); }
    }
  }
});


/* ============================================================
   Phase 3 — Global Search (1.5) + Ask Kavi on TV (5.2)
   Search: DPAD on-screen keyboard, client-side indexes
   (emby-index.json, iptv-index.json), Apple Music web link.
   Ask Kavi: TV keyboard for composing; the phone remote
   (tv-tools/remote.html) POSTs to the bridge /rvd/ask endpoint,
   which files the question in mission-control/kavi-questions/.
   Answers land in kavi-questions/answers/latest.json and pop up
   here as notification cards.
   ============================================================ */
const EMBY_WEB_ITEM = 'http://sethserver.freeddns.org:8096/web/index.html#!/item?id=';
let embySearchIdx = [];
let iptvSearchIdx = [];

/* ---------- shared DPAD on-screen keyboard ---------- */
function kbRowDefs(){
  const rows = [
    ['1','2','3','4','5','6','7','8','9','0'],
    ['Q','W','E','R','T','Y','U','I','O','P'],
    ['A','S','D','F','G','H','J','K','L'],
    ['Z','X','C','V','B','N','M'],
  ].map(r=>r.map(ch=>({label:ch, kind:'char', val:ch})));
  rows.push([
    {label:'space', kind:'space', wide:true},
    {label:'&#9003;', kind:'back'},
    {label:'CLR', kind:'clear'},
    {label:'&#10003; done', kind:'done', wide:true},
  ]);
  return rows;
}
function makeKb(el, activeFn){
  const kb = {
    el: el, cells: kbRowDefs(), r: 0, c: 0,
    active: activeFn || (()=>true),
    cell(){ return kb.cells[kb.r][kb.c]; },
    draw(){
      const on = kb.active();
      el.innerHTML = kb.cells.map((row,ri)=>
        '<div class="krow">'+row.map((cell,ci)=>
          '<div class="key'+(cell.wide?' wide':'')+((on&&ri===kb.r&&ci===kb.c)?' focused':'')+'">'+cell.label+'</div>'
        ).join('')+'</div>').join('');
    },
    move(dr,dc){
      const r = kb.r+dr;
      if(r<0 || r>=kb.cells.length) return false;
      kb.r = r;
      kb.c = Math.max(0, Math.min(kb.c+dc, kb.cells[kb.r].length-1));
      kb.draw();
      return true;
    },
  };
  kb.draw();
  return kb;
}

/* ---------- Global Search ---------- */
let sOpen=false, sQuery='', sKb=null, sZone='keys', sResults=[], sResIdx=0, sInfoBtn=0;

function searchOpen(){ return sOpen; }

function openSearchOverlay(){
  sOpen=true; sQuery=''; sZone='keys'; sResults=[]; sResIdx=0; sInfoBtn=0;
  document.getElementById('sov-results').innerHTML='';
  sKb = makeKb(document.getElementById('sov-keys'), ()=>sZone==='keys');
  sKb.r=0; sKb.c=0; sKb.draw();
  renderSearch();
  document.getElementById('search-overlay').classList.add('open');
}
function closeSearchOverlay(){
  sOpen=false;
  document.getElementById('search-overlay').classList.remove('open');
}

function renderSearch(){
  const f = document.getElementById('sov-field');
  f.innerHTML = sQuery ? esc(sQuery)+'<span class="caret">&#9612;</span>'
                       : '<span class="ph">Type to search&#8230;</span><span class="caret">&#9612;</span>';
  const R = document.getElementById('sov-results');
  const q = sQuery.trim().toLowerCase();
  sResults = [];
  if(!q){
    R.innerHTML = '<div class="sov-empty">&#128269; Search your Emby library, IPTV channels, and Apple Music.</div>';
    sZone='keys'; if(sKb) sKb.draw();
    return;
  }
  const em = embySearchIdx.filter(i=>(i.title||'').toLowerCase().indexOf(q)>=0).slice(0,8);
  const ip = iptvSearchIdx.filter(i=>(i.name||'').toLowerCase().indexOf(q)>=0).slice(0,8);
  em.forEach(i=>sResults.push({kind:'emby', t:i.title||'(untitled)',
    s:(((i.year||'')+' '+(i.type==='Series'?'TV show':'movie')).trim()||'Emby'), data:i}));
  ip.forEach(i=>sResults.push({kind:'iptv', t:i.name||'(unnamed)',
    s:'IPTV'+(i.group?' \u00b7 '+i.group:''), data:i}));
  sResults.push({kind:'music', t:'\uD83D\uDD0D Apple Music: "'+sQuery.trim()+'"', s:'open music.apple.com search', data:null});
  const head = {emby:'\uD83C\uDFAC Emby', iptv:'\uD83D\uDCE1 IPTV', music:'\uD83C\uDFB5 Music'};
  let h='', last='';
  sResults.forEach((r,idx)=>{
    if(r.kind!==last){ last=r.kind; h+='<div class="sres-group">'+head[r.kind]+'</div>'; }
    h+='<div class="sres"><div class="st">'+esc(r.t)+'</div><div class="ss">'+esc(r.s)+'</div></div>';
  });
  R.innerHTML = h;
  sResIdx = Math.min(sResIdx, Math.max(0, sResults.length-1));
  drawSRes();
}

function drawSRes(){
  const els = document.querySelectorAll('#sov-results .sres');
  els.forEach((el,idx)=>el.classList.toggle('focused', sZone==='results'&&idx===sResIdx));
  if(sKb) sKb.draw();
}

function sPressKey(cell){
  if(cell.kind==='char') sQuery += cell.val;
  else if(cell.kind==='space') sQuery += ' ';
  else if(cell.kind==='back') sQuery = sQuery.slice(0,-1);
  else if(cell.kind==='clear') sQuery = '';
  else if(cell.kind==='done'){
    if(sResults.length){ sZone='results'; sResIdx=0; drawSRes(); }
    return;
  }
  sResIdx=0;
  renderSearch();
}

function showChannelInfo(ch){
  sInfoBtn = 0; sZone = 'info';
  const R = document.getElementById('sov-results');
  R.innerHTML =
    '<div class="sov-info">'+
    '<div class="si-name">\uD83D\uDCE1 '+esc(ch.name)+'</div>'+
    '<div class="si-sub">'+esc(ch.group||'IPTV channel')+'</div>'+
    '<p>The Fire Stick can\u2019t receive direct launch commands, so open the <b>IPTV Player</b> and search for this channel name there.</p>'+
    '<div class="sbtn">&#9654; Open IPTV Player</div>'+
    '<div class="sbtn ghost">\u2190 Back to results</div>'+
    '</div>';
  drawSInfo();
}
function drawSInfo(){
  const btns = document.querySelectorAll('#sov-results .sbtn');
  btns.forEach((el,idx)=>el.classList.toggle('focused', idx===sInfoBtn));
}
function activateSRes(r){
  if(r.kind==='emby' && r.data && r.data.item_id){
    window.location.href = EMBY_WEB_ITEM + r.data.item_id;
  } else if(r.kind==='iptv'){
    showChannelInfo(r.data);
  } else if(r.kind==='music'){
    window.location.href = 'https://music.apple.com/search?term='+encodeURIComponent(sQuery.trim());
  }
}

function handleSearchKey(e){
  const k = e.key;
  if(k==='Escape'||k==='GoBack'){ closeSearchOverlay(); e.preventDefault(); return; }
  if(sZone==='info'){
    if(k==='ArrowUp'||k==='ArrowDown'){ sInfoBtn = sInfoBtn?0:1; drawSInfo(); }
    else if(k==='Enter'){
      if(sInfoBtn===0){ window.location.href='../iptv/'; }
      else { sZone='results'; renderSearch(); }
    }
    else if(k==='Backspace'){ sZone='results'; renderSearch(); }
    e.preventDefault(); return;
  }
  if(sZone==='keys'){
    if(k==='ArrowLeft'){ sKb.move(0,-1); }
    else if(k==='ArrowRight'){ sKb.move(0,1); }
    else if(k==='ArrowUp'){ sKb.move(-1,0); }
    else if(k==='ArrowDown'){
      if(!sKb.move(1,0) && sResults.length){ sZone='results'; sResIdx=0; drawSRes(); }
    }
    else if(k==='Enter'){ sPressKey(sKb.cell()); }
    else if(k==='Backspace'){
      if(sQuery){ sQuery=sQuery.slice(0,-1); renderSearch(); }
      else closeSearchOverlay();
    }
    else if(k.length===1){ sQuery+=k; renderSearch(); }
  } else {
    if(k==='ArrowUp'){
      if(sResIdx>0){ sResIdx--; drawSRes(); }
      else { sZone='keys'; sKb.r=sKb.cells.length-1; drawSRes(); }
    }
    else if(k==='ArrowDown'){ if(sResIdx<sResults.length-1){ sResIdx++; drawSRes(); } }
    else if(k==='Enter'){ const r=sResults[sResIdx]; if(r) activateSRes(r); }
    else if(k==='Backspace'){ sZone='keys'; if(sQuery){ sQuery=sQuery.slice(0,-1); renderSearch(); } }
    else if(k.length===1){ sQuery+=k; sZone='keys'; renderSearch(); }
  }
  e.preventDefault();
}

/* ---------- Ask Kavi on TV ---------- */
let aOpen=false, aQuery='', aKb=null, aZone='keys', aBtnIdx=0, aDone=false, aAnswer=null;

function askOpen(){ return aOpen; }

async function fetchLatestAnswer(){
  try{
    const r = await fetch('kavi-questions/answers/latest.json',{cache:'no-store'});
    if(r.ok) return await r.json();
  }catch(e){}
  return null;
}

function openAskOverlay(){
  aOpen=true; aQuery=''; aZone='keys'; aDone=false; aBtnIdx=0;
  document.getElementById('ask-body').innerHTML='';
  aKb = makeKb(document.getElementById('ask-keys'), ()=>aZone==='keys');
  aKb.r=0; aKb.c=0; aKb.draw();
  renderAsk();
  document.getElementById('ask-overlay').classList.add('open');
  fetchLatestAnswer().then(a=>{ if(aOpen && a){ aAnswer=a; renderAsk(); } });
}
function closeAskOverlay(){
  aOpen=false;
  document.getElementById('ask-overlay').classList.remove('open');
}

function renderAsk(){
  const f = document.getElementById('ask-field');
  f.innerHTML = aQuery ? esc(aQuery)+'<span class="caret">&#9612;</span>'
                       : '<span class="ph">Type your question&#8230;</span><span class="caret">&#9612;</span>';
  const B = document.getElementById('ask-body');
  if(aDone){
    B.innerHTML =
      '<div class="ask-q"><span class="lbl">\uD83D\uDCAC your question</span>\u201C'+esc(aQuery)+'\u201D</div>'+
      '<p style="font-size:29px;line-height:1.55;color:var(--txt)">'+
      '\uD83D\uDCF1 <b>To send it:</b> open the <b>Fire Stick Remote</b> on your phone \u2192 '+
      '<b>\uD83D\uDCAC Ask Kavi</b> \u2192 type and <b>Send Question</b>.<br>'+
      'Kavi\u2019s answer will pop up here as a notification.</p>'+
      '<div class="sbtn ghost'+(aBtnIdx===0?' focused':'')+'">\u270F\uFE0F Edit question</div>'+
      '<div class="sbtn'+(aBtnIdx===1?' focused':'')+'">\u2715 Close</div>';
  } else {
    let h = '';
    if(aAnswer && aAnswer.answer){
      h = '<div class="ask-ans"><b>\uD83D\uDCAC Kavi\u2019s latest answer</b><br>'+
          esc(String(aAnswer.answer)).slice(0,400)+'</div>';
    }
    B.innerHTML = h;
  }
  if(aKb) aKb.draw();
}

function aPressKey(cell){
  if(cell.kind==='char') aQuery += cell.val;
  else if(cell.kind==='space') aQuery += ' ';
  else if(cell.kind==='back') aQuery = aQuery.slice(0,-1);
  else if(cell.kind==='clear') aQuery = '';
  else if(cell.kind==='done'){
    if(aQuery.trim()){ aDone=true; aZone='done'; aBtnIdx=0; }
    renderAsk(); return;
  }
  renderAsk();
}

function handleAskKey(e){
  const k = e.key;
  if(k==='Escape'||k==='GoBack'){ closeAskOverlay(); e.preventDefault(); return; }
  if(aZone==='done'){
    if(k==='ArrowUp'||k==='ArrowDown'){ aBtnIdx = aBtnIdx?0:1; renderAsk(); }
    else if(k==='Enter'){
      if(aBtnIdx===0){ aDone=false; aZone='keys'; renderAsk(); }
      else closeAskOverlay();
    }
    else if(k==='Backspace'){ aDone=false; aZone='keys'; renderAsk(); }
    e.preventDefault(); return;
  }
  if(k==='ArrowLeft'){ aKb.move(0,-1); }
  else if(k==='ArrowRight'){ aKb.move(0,1); }
  else if(k==='ArrowUp'){ aKb.move(-1,0); }
  else if(k==='ArrowDown'){ aKb.move(1,0); }
  else if(k==='Enter'){ aPressKey(aKb.cell()); }
  else if(k==='Backspace'){
    if(aQuery){ aQuery=aQuery.slice(0,-1); renderAsk(); }
    else closeAskOverlay();
  }
  else if(k.length===1){ aQuery+=k; renderAsk(); }
  e.preventDefault();
}

/* ---------- Kavi answer polling (30s) ---------- */
async function checkKaviAnswers(){
  try{
    const r = await fetch('kavi-questions/answers/latest.json',{cache:'no-store'});
    if(!r.ok) return;
    const a = await r.json();
    if(!a || !a.id) return;
    let seen = null;
    try{ seen = localStorage.getItem('tv_seen_answer'); }catch(e){}
    if(seen === a.id) return;
    try{ localStorage.setItem('tv_seen_answer', a.id); }catch(e){}
    const stack = document.getElementById('notif-stack');
    if(!stack) return;
    const el = document.createElement('div');
    el.className = 'notif';
    el.innerHTML = '<div class="ni">\uD83D\uDCAC</div><div><div class="nt">Kavi answered</div>'+
      '<div class="nm">'+esc(String(a.answer||'')).slice(0,220)+'</div></div>'+
      '<div class="nx">BACK \u2715</div>';
    el.querySelector('.nx').onclick = ()=>{ el.classList.add('out'); setTimeout(()=>el.remove(),350); };
    stack.appendChild(el);
    if(aOpen){ aAnswer = a; renderAsk(); }
  }catch(e){}
}

/* ---------- data ---------- */
// Send to TV: poll inbox, open new URLs
function renderNowPlaying(np){
  const el = document.getElementById('nowplaying');
  if(!np || !Array.isArray(np.items) || np.items.length === 0){
    el.style.display = 'none';
    return;
  }
  const item = np.items[0];
  document.getElementById('np-icon').textContent = item.icon || '🎬';
  document.getElementById('np-title').textContent = item.title || 'Unknown';
  const sub = [];
  if(item.series) sub.push(item.series);
  if(item.user) sub.push(item.user);
  if(item.device) sub.push(item.device);
  document.getElementById('np-sub').textContent = sub.join(' · ');
  document.getElementById('np-progress').textContent =
    item.progress_pct ? Math.round(item.progress_pct) + '%' : '';
  el.style.display = 'flex';
}

function checkInbox(inbox){
  if(!inbox || !Array.isArray(inbox.items)) return;
  let seen = [];
  try{ seen = JSON.parse(localStorage.getItem('tv_seen_inbox') || '[]'); }catch(e){}
  const fresh = inbox.items.filter(it => it && it.id && it.url && !seen.includes(it.id));
  if(fresh.length === 0) return;
  seen = seen.concat(fresh.map(it => it.id)).slice(-50);
  try{ localStorage.setItem('tv_seen_inbox', JSON.stringify(seen)); }catch(e){}
  const item = fresh[fresh.length - 1];
  showInboxBanner(item.url);
  setTimeout(()=>{ window.location.href = item.url; }, 3000);
}
function showInboxBanner(url){
  let el = document.getElementById('inbox-banner');
  if(!el){
    el = document.createElement('div');
    el.id = 'inbox-banner';
    el.style.cssText = 'position:fixed;top:20px;left:50%;transform:translateX(-50%);background:#6c3ce0;color:#fff;padding:20px 32px;border-radius:12px;font-size:28px;z-index:9999;box-shadow:0 4px 20px rgba(0,0,0,0.5);';
    document.body.appendChild(el);
  }
  el.textContent = '📲 Opening: ' + (url.length > 60 ? url.slice(0,60) + '...' : url);
  el.style.display = 'block';
}

async function load(){
  try{
    const [r,b,h,p,ib,np,sp,ei,ii]=await Promise.all([
      fetch(STATUS_URL+'?t='+Date.now(),{cache:'no-store'}), // cache-bust GitHub Pages CDN
      fetch('briefing.json',{cache:'no-store'}).catch(()=>null),
      fetch('hearing.json',{cache:'no-store'}).catch(()=>null),
      fetch('photos.json',{cache:'no-store'}).catch(()=>null),
      fetch('../tv-inbox/inbox.json',{cache:'no-store'}).catch(()=>null),
      fetch('nowplaying.json',{cache:'no-store'}).catch(()=>null),
      fetch('emby-spotlight.json',{cache:'no-store'}).catch(()=>null),
      fetch('emby-index.json',{cache:'no-store'}).catch(()=>null),
      fetch('iptv-index.json',{cache:'no-store'}).catch(()=>null),
    ]);
    const j=await r.json();
    try{ if(b&&b.ok) briefingData=await b.json(); }catch(e){}
    try{ if(h&&h.ok) hearingData=await h.json(); }catch(e){}
    try{ if(p&&p.ok) photosData=await p.json(); }catch(e){}
    try{ if(ib&&ib.ok) checkInbox(await ib.json()); }catch(e){}
    try{ if(np&&np.ok){ npData=await np.json(); renderNowPlaying(npData); } }catch(e){}
    try{ if(sp&&sp.ok) spotlightData=await sp.json(); }catch(e){}
    try{ if(ei&&ei.ok){ const x=await ei.json(); if(x&&Array.isArray(x.items)) embySearchIdx=x.items; } }catch(e){}
    try{ if(ii&&ii.ok){ const x=await ii.json(); if(x&&Array.isArray(x.items)) iptvSearchIdx=x.items; } }catch(e){}
    checkKaviAnswers();
    render(j);
    checkForUpdate();
  }catch(e){
    document.getElementById('rows').innerHTML=
      `<div class="err-hero"><div class="big">🛰️</div>
       <h2 style="margin:0 0 6px;font-size:54px">collector offline</h2>
       <div style="font-size:28px;color:var(--dim)">status.json unreachable — check the 5-min cron</div></div>`;
  }
}

function tick(){
  const d=new Date();
  document.getElementById('clock').textContent=
    String(d.getHours()).padStart(2,'0')+':'+String(d.getMinutes()).padStart(2,'0')+':'+String(d.getSeconds()).padStart(2,'0');
}
tick(); setInterval(tick,1000);

load();
setInterval(load, 30000);
setInterval(checkKaviAnswers, 30000);
