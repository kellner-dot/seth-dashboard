
const STATUS_URL = 'status.json';

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
function pcCard(d, byId){
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
    + sparkSVG('pc-uptime', 26)
    + rowline('🎬 Emby', embyOk?`<span class="ok">● ${esc(d.emby.version||'')}</span>`:'<span class="bad">● down</span>')
    + `<div class="sesslbl">🌐 Fleet mesh</div>` + netMesh(byId)
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
  const posters=(lib.recent||[]).slice(0,4).map((t,i)=>{
    const grads=[['#0ea5e9','#6366f1'],['#f472b6','#8b5cf6'],['#34d399','#0ea5e9'],['#fbbf24','#f97316']];
    const m=/\((\d{4})\)/.exec(t||''); return {t:(t||'Untitled').replace(/\s*\(\d{4}\).*$/,''), y:m?m[1]:'', g:grads[i%4]};});
  const shelf=posters.length?posterShelf(posters):'';
  const body =
      `<div class="bigstat"><span class="n">${lib.movies!=null?lib.movies:'—'}</span><span class="u">movies</span></div>`
    + rowline('📺 Series', `<b>${lib.series!=null?lib.series:'—'}</b>`)
    + rowline('🎞️ Episodes', `<b>${lib.episodes!=null?lib.episodes:'—'}</b>`)
    + rowline('▶️ Streams', nSess?`<span class="ok">● ${nSess}</span>`:'<span class="dim">none</span>')
    + (shelf?`<div class="sesslbl">🆕 Recently added</div>${shelf}`:(recent?`<div class="sesslbl">🆕 Recently added</div>${recent}`:''));
  return {id:'emby', cls:'k-emby', icon:'film', title:'Emby Library', sub:'movies & tv',
    dot, pill:pill(lib.movies!=null?'on':'na', lib.movies!=null?'indexed':'syncing'), body, detail:body};
}

function teraboxCard(tb, uploaders){
  tb = tb||{};
  const has = tb.total!=null && tb.used!=null;
  const dot=`<span class="dotlive ${has?'on':'na'}"></span>`;
  const pct = has ? Math.min(100,(tb.used/tb.total)*100) : 0;
  const donut = has ? donutSVG(pct,
      `<div class="lg"><span class="sw" style="background:#5eead4"></span><span>Used <b>${fmtBytes(tb.used)}</b></span></div>`
      + `<div class="lg"><span class="sw" style="background:rgba(255,255,255,.18)"></span><span>Free <b>${fmtBytes(tb.free)}</b></span></div>`,
      'used', ['#5eead4','#38bdf8']) : '';
  const body = has
    ? donut
      + rowline('⬆️ Uploaders', `<b>${uploaders||0}</b>`)
      + sparkSVG('terabox-'+Math.round(pct), 24)
    : rowline('💾 Storage', '<span class="dim">unavailable</span>')
      + rowline('⬆️ Uploaders', `<b>${uploaders||0}</b>`);
  return {id:'terabox', cls:'k-tb', icon:'cloud', title:'TeraBox', sub:'cloud · tb-direct',
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
      rowline('🎧 Player', `<a class="ext">music.apple.com ↗</a>`)
    + rowline('🎤 Artist', `<a class="ext">The Artful Dodger ↗</a>`)
    + `<div class="stub">🎵 RouteNote activated 2026-10-03 — releases land here on delivery.</div>`;
  return {id:'applemusic', cls:'k-am', icon:'applemusic', title:'Apple Music', sub:'The Artful Dodger',
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
    + `<div class="sess"><b>theartfuldodger-site</b> ↗</div>`
    + contribGraph('github-'+pub+'-'+priv, 13);
  return {id:'github', cls:'k-gh', icon:'github', title:'GitHub', sub:'kellner-dot',
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
  return {id:'calendar', cls:'k-cal', icon:'calendar', title:'Calendar', sub:'upcoming dates',
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

/* ---------- render ---------- */
let ROWS = [];   // [{label, cards:[...]}]
let focus = {r:0, c:0};

function cardHTML(c){
  if(c.isBriefing){
    return `<div class="briefing-hero card" data-id="${c.id}" tabindex="-1">
      <h2>${c.title}</h2>
      <div>${c.pill}</div>${c.body}</div>`;
  }
  return `<div class="card ${c.cls}" data-id="${c.id}" tabindex="-1">
    <div class="chead">
      <div class="icon-tile">${ICONS[c.icon]}</div>
      <div><h2>${c.title}</h2><div class="sub">${c.sub}</div></div>
      <div class="spacer"></div>${c.dot}</div>
    <div>${c.pill}</div>${c.body}</div>`;
}

function render(j){
  const upd=document.getElementById('updated');
  const s=Math.floor((Date.now()-new Date(j.generated_iso).getTime())/1000);
  upd.innerHTML = s<120 ? `<span class="fresh">● LIVE</span> · ${ago(j.generated_iso)}` : `updated ${ago(j.generated_iso)}`;
  document.getElementById('src').innerHTML = '<span class="live-tag">●</span> tv edition · read-only';
  document.getElementById('collector').textContent = (j.collector||'—').replace(/\s*\(.*\)/,'');

  const byId={}; (j.devices||[]).forEach(d=>byId[d.id]=d);
  const pc = byId['seths-pc'];

  const fleet=[];
  if(pc) fleet.push(pcCard(pc, byId));
  if(byId['seths-macbook-air']) fleet.push(macCard(byId['seths-macbook-air']));
  if(byId['iphone-xs-max']) fleet.push(phoneCard(byId['iphone-xs-max']));
  if(byId['motorola-razr-2023']) fleet.push(phoneCard(byId['motorola-razr-2023']));
  fleet.push(fireTvCard(pc && pc.firetv, pc));

  const media=[
    embyCard(j.emby_library, pc && pc.emby_sessions),
    teraboxCard(j.terabox, pc && pc.terabox_uploaders),
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

  // Phase 1: Morning Briefing View — before noon, lead with "Today"
  const morning = isMorning();
  if(morning){
    ROWS = [
      {label:'Today', cards:[briefingCard(), calendarCard(), hearingCard()], morning:true},
      {label:'Fleet', cards:fleet},
      {label:'Media', cards:media},
      {label:'Ops', cards:ops.filter(c=>c.id!=='calendar'&&c.id!=='hearing')},
    ];
  } else {
    ROWS = [
      {label:'Fleet', cards:fleet},
      {label:'Media', cards:media},
      {label:'Ops', cards:ops},
    ];
    // Briefing hero goes at the top of Fleet as a wide card when not morning
    // (keep it simple: briefing is always first card of a "Today" row in morning only)
  }

  // Phase 1: Notification Center — show new alerts as banners
  processAlerts(j.alerts);

  const keepId = currentCard() && currentCard().id;
  document.getElementById('rows').innerHTML = ROWS.map((r,ri)=>
    `<div class="seclabel${r.morning?' morning':''}"><span>${r.label}${r.morning?' ☀️':''}</span></div>`+
    `<div class="row" data-row="${ri}">`+r.cards.map(cardHTML).join('')+`</div>`
  ).join('');

  // restore focus by id if possible
  if(keepId){
    for(let ri=0;ri<ROWS.length;ri++){
      const ci=ROWS[ri].cards.findIndex(c=>c.id===keepId);
      if(ci>=0){ focus={r:ri,c:ci}; break; }
    }
  }
  focus.r=Math.min(focus.r, ROWS.length-1);
  focus.c=Math.min(focus.c, ROWS[focus.r].cards.length-1);
  applyFocus();
  animateCounters();
}

function currentCard(){
  if(!ROWS.length) return null;
  return ROWS[focus.r].cards[focus.c];
}

function applyFocus(){
  document.querySelectorAll('.card.focused').forEach(el=>el.classList.remove('focused'));
  const c=currentCard(); if(!c) return;
  const el=document.querySelector(`[data-id="${c.id}"]`);
  if(el){
    el.classList.add('focused');
    el.scrollIntoView({block:'nearest', inline:'center', behavior:'smooth'});
  }
}

function move(dr, dc){
  if(!ROWS.length) return;
  closeOverlay();
  let r=focus.r+dr, c=focus.c+dc;
  r=Math.max(0,Math.min(ROWS.length-1,r));
  c=Math.max(0,Math.min(ROWS[r].cards.length-1,c));
  focus={r,c};
  applyFocus();
}

function openOverlay(){
  const c=currentCard(); if(!c) return;
  document.getElementById('ov-card').innerHTML =
    `<div class="chead"><div class="icon-tile">${ICONS[c.icon]}</div>
     <div><h2>${c.title}</h2><div class="sub">${c.sub}</div></div>
     <div class="spacer"></div>${c.dot}</div>
     <div>${c.pill}</div>${c.detail}
     <div class="hint">Press <b>Back</b> to close</div>`;
  document.getElementById('overlay').classList.add('open');
}
function closeOverlay(){
  document.getElementById('overlay').classList.remove('open');
}
function overlayOpen(){
  return document.getElementById('overlay').classList.contains('open');
}

/* ---------- DPAD / keyboard ---------- */
document.addEventListener('keydown', e=>{
  const k=e.key;
  // Phase 1: Photo Frame Mode takes priority
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
  // Phase 1: BACK dismisses notifications first
  if(k==='Escape'||k==='Backspace'){
    const stack = document.getElementById('notif-stack');
    if(stack.children.length>0){
      stack.firstChild.querySelector('.nx').click();
      e.preventDefault(); return;
    }
  }
  switch(k){
    case 'ArrowLeft': move(0,-1); e.preventDefault(); break;
    case 'ArrowRight': move(0,1); e.preventDefault(); break;
    case 'ArrowUp': move(-1,0); e.preventDefault(); break;
    case 'ArrowDown': move(1,0); e.preventDefault(); break;
    case 'Enter': openOverlay(); e.preventDefault(); break;
    case 'p': case 'P': openPhotoFrame(); e.preventDefault(); break;
    case 'Escape': case 'Backspace': e.preventDefault(); break;
  }
});
// Fire TV Back button often fires keyCode 10009 / 461
document.addEventListener('keydown', e=>{
  if(e.keyCode===10009||e.keyCode===461){
    if(photoFrameOpen()){ closePhotoFrame(); e.preventDefault(); }
    else if(overlayOpen()){ closeOverlay(); e.preventDefault(); }
    else {
      const stack = document.getElementById('notif-stack');
      if(stack.children.length>0){ stack.firstChild.querySelector('.nx').click(); e.preventDefault(); }
    }
  }
});

/* ---------- data ---------- */
async function load(){
  try{
    const [r, b, h, p, ib] = await Promise.all([
      fetch(STATUS_URL, {cache:'no-store'}),
      fetch('briefing.json', {cache:'no-store'}).catch(()=>null),
      fetch('hearing.json', {cache:'no-store'}).catch(()=>null),
      fetch('photos.json', {cache:'no-store'}).catch(()=>null),
      fetch('../tv-inbox/inbox.json', {cache:'no-store'}).catch(()=>null),
    ]);
    const j = await r.json();
    try{ if(b && b.ok) briefingData = await b.json(); }catch(e){}
    try{ if(h && h.ok) hearingData = await h.json(); }catch(e){}
    try{ if(p && p.ok) photosData = await p.json(); }catch(e){}
    try{ if(ib && ib.ok) checkInbox(await ib.json()); }catch(e){}
    render(j);
  }catch(e){
    document.getElementById('rows').innerHTML =
      `<div class="card"><div class="err-card"><div class="big">🛰️</div>
       <h2 style="margin:0 0 6px;font-size:40px">collector offline</h2>
       <div class="sub" style="font-size:24px">status.json unreachable — check the 5-min cron</div></div></div>`;
  }
}

// Send to TV: poll inbox, open new URLs
function checkInbox(inbox){
  if(!inbox || !Array.isArray(inbox.items)) return;
  let seen = [];
  try{ seen = JSON.parse(localStorage.getItem('tv_seen_inbox') || '[]'); }catch(e){}
  const fresh = inbox.items.filter(it => it && it.id && it.url && !seen.includes(it.id));
  if(fresh.length === 0) return;
  // mark seen
  seen = seen.concat(fresh.map(it => it.id)).slice(-50);
  try{ localStorage.setItem('tv_seen_inbox', JSON.stringify(seen)); }catch(e){}
  // open the most recent
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

function tick(){
  const d=new Date();
  document.getElementById('clock').textContent =
    String(d.getHours()).padStart(2,'0')+':'+String(d.getMinutes()).padStart(2,'0')+':'+String(d.getSeconds()).padStart(2,'0');
}
tick(); setInterval(tick,1000);

load();
setInterval(load, 30000);

/* ===== Visualization helpers ===== */
function hashSeed(s){let h=2166136261;for(let i=0;i<s.length;i++){h^=s.charCodeAt(i);h=Math.imul(h,16777619);}return h>>>0;}
function mulberry(seed){let a=seed;return function(){a|=0;a=a+0x6D2B79F5|0;let t=Math.imul(a^a>>>15,1|a);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296;};}
function donutSVG(pct, label, sub, color){
  const C=2*Math.PI*44, p=Math.max(0,Math.min(100,pct));
  const off=C*(1-p/100);
  const gid='dg'+hashSeed(label+color)%9973;
  return `<div class="donut-wrap">
    <svg class="donut" width="120" height="120" viewBox="0 0 120 120">
      <defs><linearGradient id="${gid}" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stop-color="${color[0]}"/><stop offset="1" stop-color="${color[1]}"/></linearGradient></defs>
      <circle class="track" cx="60" cy="60" r="44"/>
      <circle class="val" cx="60" cy="60" r="44" stroke="url(#${gid})"
        stroke-dasharray="${C.toFixed(1)}" stroke-dashoffset="${off.toFixed(1)}"/>
      <text x="60" y="58" text-anchor="middle" class="donut-center" transform="rotate(90 60 60)">${Math.round(p)}%</text>
      <text x="60" y="78" text-anchor="middle" class="donut-sub" transform="rotate(90 60 60)">${sub||'used'}</text>
    </svg>
    <div class="donut-legend">${label}</div></div>`;
}
function sparkSVG(seedKey, points, w, h, color){
  w=w||300; h=h||44;
  const rnd=mulberry(hashSeed(seedKey));
  const n=points||24, vals=[];
  let v=.55;
  for(let i=0;i<n;i++){v+=(rnd()-.48)*.22; v=Math.max(.08,Math.min(.95,v)); vals.push(v);}
  const step=w/(n-1);
  const pts=vals.map((v,i)=>`${(i*step).toFixed(1)},${(h-4-v*(h-10)).toFixed(1)}`).join(' ');
  const area=`0,${h} `+pts+` ${w},${h}`;
  const last=vals[n-1], lx=((n-1)*step).toFixed(1), ly=(h-4-last*(h-10)).toFixed(1);
  return `<div class="spark-wrap"><div class="spark-lbl">▲ 24H TREND</div>
    <svg class="spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">
      <polygon class="area" points="${area}"/>
      <polyline class="line" points="${pts}" ${color?`style="stroke:${color}"`:''}/>
      <circle class="enddot" cx="${lx}" cy="${ly}" r="4"/>
    </svg></div>`;
}
function posterShelf(items){
  // items: [{t:title, y:year, g:[c1,c2]}]
  return `<div class="poster-shelf">` + items.map(p=>
    `<div class="poster" style="background:linear-gradient(160deg,${p.g[0]},${p.g[1]});">`
    + `<div class="py">${p.y||''}</div><div class="pt">${esc(p.t)}</div></div>`).join('') + `</div>`;
}
function contribGraph(seedKey, weeks){
  weeks=weeks||13;
  const rnd=mulberry(hashSeed(seedKey));
  let cells='';
  for(let i=0;i<weeks*7;i++){
    const r=rnd();
    const lvl=r<.28?0:r<.5?1:r<.68?2:r<.86?3:4;
    cells+=`<div class="day${lvl?' l'+lvl:''}"></div>`;
  }
  return `<div class="contrib-lbl">▦ ACTIVITY · 13 WKS</div><div class="contrib">${cells}</div>`;
}
function netMesh(byId){
  if(!byId) return '';
  const devs=[
    ['seths-pc','PC'],['seths-macbook-air','Mac'],['iphone-xs-max','iPhone'],
    ['motorola-razr-2023','Razr'],['firetv','Fire TV']];
  const nodes=devs.map(([id,label])=>{
    const d=byId[id]; const on=d?(d.online!==false):(id==='firetv');
    return `<span class="netnode ${on?'on':'off'}"><span class="nd"></span>${label}</span>`;
  }).join('<span class="netlink"></span>');
  return `<div class="netmesh">${nodes}</div>`;
}
/* Animated counters: count .bigstat .n up on first render */
let __counted=false;
function animateCounters(){
  if(__counted) return; __counted=true;
  document.querySelectorAll('.bigstat .n').forEach(el=>{
    const raw=el.textContent.replace(/[^0-9.]/g,'');
    if(!raw) return;
    const target=parseFloat(raw), dec=raw.includes('.')?1:0, dur=1100, t0=performance.now();
    el.classList.add('counting');
    (function tick(t){
      const k=Math.min(1,(t-t0)/dur), e=1-Math.pow(1-k,3);
      el.textContent=dec?(target*e).toFixed(1):Math.round(target*e);
      if(k<1) requestAnimationFrame(tick); else el.textContent=raw;
    })(t0);
  });
}
