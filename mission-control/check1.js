
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
  return {id:'emby', cls:'k-emby', icon:'film', title:'Emby Library', sub:'movies & tv', url:'http://sethserver.freeddns.org:8096',
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
  return {id:'terabox', cls:'k-tb', icon:'cloud', title:'TeraBox', sub:'cloud · tb-direct', url:'https://www.terabox.com',
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
      rowline('🎧 Player', `<a class="ext" href="https://music.apple.com" target="_self">music.apple.com ↗</a>`)
    + rowline('🎤 Artist', `<a class="ext" href="https://suno.com" target="_self">The Artful Dodger ↗</a>`)
    + `<div class="stub">🎵 RouteNote activated 2026-10-03 — releases land here on delivery.</div>`;
  return {id:'applemusic', cls:'k-am', icon:'applemusic', title:'Apple Music', sub:'The Artful Dodger', url:'https://music.apple.com',
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
  return {id:'github', cls:'k-gh', icon:'github', title:'GitHub', sub:'kellner-dot', url:'https://github.com/kellner-dot',
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
  return {id:'calendar', cls:'k-cal', icon:'calendar', title:'Calendar', sub:'upcoming dates', url:'https://calendar.google.com',
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
    case 'emby': { const l=j.emby_library||{}; return `${l.movies!=null?l.movies:'—'} movies · ${l.series!=null?l.series:'—'} series`; }
    case 'terabox': { const t=j.terabox||{}; const has=t.total!=null&&t.used!=null;
      return has ? `${Math.round(t.used/t.total*100)}% used · ${ctx.pc&&ctx.pc.terabox_uploaders||0} up` : 'syncing'; }
    case 'biglybt': { const b=j.biglybt||{}; return b.running ? 'running' : 'stopped'; }
    case 'applemusic': return 'The Artful Dodger';
    case 'artist': return '3 releases · RouteNote ready';
    case 'github': { const g=j.github||{}; const t=(g.public_repos||0)+(g.private_repos||0); return `${t} repos`; }
    case 'kaviguard': { const kg=j.kaviguard||{}; return Object.keys(kg).length ? 'shield up' : 'syncing'; }
    case 'calendar': { return 'upcoming dates'; }
    case 'hearing': { const h=hearingData||{hearing_date:'2026-11-12'}; const target=new Date(h.hearing_date+'T08:15:00-04:00');
      const days=Math.max(0,Math.ceil((target-new Date())/86400000)); return `${days} days to go`; }
    case 'act-photos': return 'slideshow · press OK';
    case 'act-iptv': return 'TV Navigator player';
    case 'act-refresh': return 'reload dashboard data';
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

/* ---------- render ---------- */
function render(j){
  // header/footer freshness
  const s=Math.floor((Date.now()-new Date(j.generated_iso).getTime())/1000);
  const live = s<120;
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
    githubCard(j.github),
    kaviguardCard(j.kaviguard),
    calendarCard(),
    hearingCard(),
  ];

  ROWS=[
    {label:'My Fleet', cards:fleet},
    {label:'Media', cards:media},
    {label:'Operations', cards:ops},
    {label:'Quick Actions', cards:actionCards()},
  ];

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
  let icon='bolt', title='', sub='', dot='', pillHtml='', detail='', url='';
  if(focus.zone==='hero'){
    const s=heroSubject; if(!s) return;
    if(s.type==='device'&&s.card){ ({icon,title,sub,dot}=s.card); pillHtml=s.card.pill; detail=s.card.detail; url=s.card.url||''; }
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
    ({icon,title,sub,dot}=c); pillHtml=c.pill; detail=c.detail; url=c.url||'';
  }
  document.getElementById('ov-card').innerHTML=
    `<div class="ov-head"><div class="ov-icon">${ICONS[icon]||''}</div>
     <div><h2>${title}</h2><div class="osub">${sub||''}</div></div>
     <div class="ov-x" id="ov-x" title="Close">✕</div></div>
     ${dot}
     <div>${pillHtml}</div>${detail}
     <div class="ov-actions">`+
       (url?`<button class="ov-btn" id="ov-open">Open →</button>`:'')+
       `<button class="ov-btn ghost" id="ov-close-btn">Close</button></div>
     <div class="hint"><b>OK</b> open &nbsp;&middot;&nbsp; <b>Back</b> close</div>`;
  document.getElementById('ov-x').onclick=closeOverlay;
  document.getElementById('ov-close-btn').onclick=closeOverlay;
  const ob=document.getElementById('ov-open');
  if(ob) ob.onclick=()=>{ if(url) window.location.href=url; };
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
  else if(c.isAction==='refresh'){ load(); }
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


/* ---------- mouse / touch clicks (event delegation) ---------- */
document.getElementById('rows').addEventListener('click', e=>{
  const p=e.target.closest('.poster'); if(!p) return;
  const sec=p.closest('.row-sec'); if(!sec||!ROWS.length) return;
  const ri=+sec.dataset.sec, ci=ROWS[ri].cards.findIndex(c=>c.id===p.dataset.id);
  if(ci<0) return;
  focus={zone:'rows',r:ri,c:ci}; applyFocus();
  const c=ROWS[ri].cards[ci];
  if(c.isAction) runCardAction(c); else openOverlay();
});
document.getElementById('hero-actions').addEventListener('click', e=>{
  const b=e.target.closest('[data-ha]'); if(!b) return;
  focus={zone:'hero',r:0,c:+b.dataset.ha}; applyFocus(); runHeroAction(+b.dataset.ha);
});
document.getElementById('overlay').addEventListener('click', e=>{
  if(e.target.id==='overlay') closeOverlay();
});
document.getElementById('photoframe').addEventListener('click', e=>{
  if(e.target.id==='photoframe') closePhotoFrame();
});

/* ---------- DPAD / keyboard ---------- */
document.addEventListener('keydown', e=>{
  const k=e.key;
  if(photoFrameOpen()){
    if(k==='ArrowLeft'){ pfNav(-1); e.preventDefault(); return; }
    if(k==='ArrowRight'){ pfNav(1); e.preventDefault(); return; }
    if(k==='Escape'||k==='Backspace'||k==='GoBack'){ closePhotoFrame(); e.preventDefault(); return; }
    return;
  }
  if(overlayOpen()){
    if(k==='Enter'){ const ob=document.getElementById('ov-open'); if(ob){ ob.click(); e.preventDefault(); } return; }
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
    if(photoFrameOpen()){ closePhotoFrame(); e.preventDefault(); }
    else if(overlayOpen()){ closeOverlay(); e.preventDefault(); }
    else {
      const stack=document.getElementById('notif-stack');
      if(stack.children.length>0){ stack.firstChild.querySelector('.nx').click(); e.preventDefault(); }
    }
  }
});

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
    const [r,b,h,p,ib,np]=await Promise.all([
      fetch(STATUS_URL,{cache:'no-store'}),
      fetch('briefing.json',{cache:'no-store'}).catch(()=>null),
      fetch('hearing.json',{cache:'no-store'}).catch(()=>null),
      fetch('photos.json',{cache:'no-store'}).catch(()=>null),
      fetch('../tv-inbox/inbox.json',{cache:'no-store'}).catch(()=>null),
      fetch('nowplaying.json',{cache:'no-store'}).catch(()=>null),
    ]);
    const j=await r.json();
    try{ if(b&&b.ok) briefingData=await b.json(); }catch(e){}
    try{ if(h&&h.ok) hearingData=await h.json(); }catch(e){}
    try{ if(p&&p.ok) photosData=await p.json(); }catch(e){}
    try{ if(ib&&ib.ok) checkInbox(await ib.json()); }catch(e){}
    try{ if(np&&np.ok){ npData=await np.json(); renderNowPlaying(npData); } }catch(e){}
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
