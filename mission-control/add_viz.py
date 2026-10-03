#!/usr/bin/env python3
"""Add rich data visualizations to the Mission Control TV dashboard.
Modifies index.html (and tv.html which is identical) in place.
"""
import re
import sys

PATH = sys.argv[1] if len(sys.argv) > 1 else '/tmp/dashboard/index.html'
html = open(PATH, encoding='utf-8').read()

# ---------------------------------------------------------------- CSS additions
VIZ_CSS = """
  /* ===== Rich visualizations ===== */
  /* Animated ambient background orbs (transform/opacity only) */
  .bg-orb{position:fixed; border-radius:50%; filter:blur(90px); opacity:.16; pointer-events:none; z-index:0; will-change:transform;}
  .bg-orb.o1{width:560px;height:560px;left:-140px;top:-120px;background:#0ea5e9;animation:drift1 26s ease-in-out infinite alternate;}
  .bg-orb.o2{width:480px;height:480px;right:-120px;top:22%;background:#8b5cf6;animation:drift2 32s ease-in-out infinite alternate;}
  .bg-orb.o3{width:420px;height:420px;left:34%;bottom:-160px;background:#ec4899;animation:drift1 38s ease-in-out infinite alternate-reverse;}
  @keyframes drift1{from{transform:translate(0,0) scale(1);}to{transform:translate(90px,60px) scale(1.12);}}
  @keyframes drift2{from{transform:translate(0,0) scale(1.08);}to{transform:translate(-70px,80px) scale(.94);}}
  /* Donut chart */
  .donut-wrap{display:flex; align-items:center; gap:18px; margin:12px 0 6px;}
  .donut{transform:rotate(-90deg);}
  .donut .track{fill:none; stroke:rgba(255,255,255,.09); stroke-width:14;}
  .donut .val{fill:none; stroke-width:14; stroke-linecap:round; transition:stroke-dashoffset 1.2s cubic-bezier(.22,1,.36,1);}
  .donut-center{font-size:30px; font-weight:800; fill:#fff;}
  .donut-sub{font-size:15px; fill:var(--dim);}
  .donut-legend{display:flex; flex-direction:column; gap:8px; font-size:19px;}
  .donut-legend .lg{display:flex; align-items:center; gap:10px;}
  .donut-legend .sw{width:16px; height:16px; border-radius:5px; flex:none;}
  /* Sparkline */
  .spark-wrap{margin:10px 0 2px;}
  .spark-lbl{font-size:16px; color:var(--faint); letter-spacing:.12em; margin-bottom:4px;}
  .spark{width:100%; height:44px; display:block;}
  .spark .area{fill:url(#sparkGrad); opacity:.28;}
  .spark .line{fill:none; stroke:var(--acc1); stroke-width:3; stroke-linecap:round; stroke-linejoin:round;}
  .spark .enddot{fill:var(--acc1);}
  /* Pulse rings around live status dots (expanding rings via pseudo-elements) */
  .dotlive.on{position:relative;}
  .dotlive.on::before,.dotlive.on::after{content:""; position:absolute; inset:-8px; border-radius:50%;
    border:3px solid var(--ok); opacity:0; animation:ringpulse 2.4s ease-out infinite; pointer-events:none;}
  .dotlive.on::after{animation-delay:1.2s;}
  @keyframes ringpulse{0%{transform:scale(.55); opacity:.9;}70%{opacity:.25;}100%{transform:scale(1.3); opacity:0;}}
  /* Poster shelf (Emby) */
  .poster-shelf{display:flex; gap:12px; margin:12px 0 4px;}
  .poster{flex:1 1 0; aspect-ratio:2/3; border-radius:12px; position:relative; overflow:hidden;
    box-shadow:0 8px 22px rgba(0,0,0,.45); border:1px solid rgba(255,255,255,.09);}
  .poster .pt{position:absolute; left:8px; right:8px; bottom:7px; font-size:14px; font-weight:700;
    color:#fff; text-shadow:0 2px 6px rgba(0,0,0,.8); line-height:1.15;}
  .poster .py{position:absolute; top:6px; left:8px; font-size:12px; color:rgba(255,255,255,.85);
    background:rgba(0,0,0,.45); padding:2px 7px; border-radius:20px;}
  /* GitHub contribution graph */
  .contrib{display:grid; grid-template-columns:repeat(13, 1fr); gap:5px; margin:12px 0 4px;}
  .contrib .day{aspect-ratio:1; border-radius:4px; background:rgba(255,255,255,.06);}
  .contrib .day.l1{background:#0e4429;} .contrib .day.l2{background:#006d32;}
  .contrib .day.l3{background:#26a641;} .contrib .day.l4{background:#39d353;}
  .contrib-lbl{font-size:16px; color:var(--faint); letter-spacing:.1em; margin-top:10px;}
  /* Animated counters */
  .bigstat .n.counting{font-variant-numeric:tabular-nums;}
  /* Network mesh strip */
  .netmesh{display:flex; align-items:center; gap:10px; margin:12px 0 4px; flex-wrap:wrap;}
  .netnode{display:flex; align-items:center; gap:8px; font-size:17px; padding:7px 13px;
    border-radius:24px; background:rgba(255,255,255,.05); border:1px solid rgba(255,255,255,.09);}
  .netnode .nd{width:11px; height:11px; border-radius:50%; flex:none;}
  .netnode.on .nd{background:var(--ok); box-shadow:0 0 10px var(--ok); animation:blink 2.2s ease-in-out infinite;}
  .netnode.off .nd{background:var(--bad); opacity:.7;}
  @keyframes blink{0%,100%{opacity:1;}50%{opacity:.45;}}
  .netlink{width:22px; height:2px; background:linear-gradient(90deg,var(--acc1),transparent); flex:none; opacity:.6;}
"""

# Insert CSS before closing </style>
assert '</style>' in html, "no </style> found"
html = html.replace('</style>', VIZ_CSS + '\n</style>', 1)

# ------------------------------------------------- background orbs in <body>
# Insert right after <body ...> tag
m = re.search(r'<body[^>]*>', html)
assert m, "no <body> found"
orbs = ('<div class="bg-orb o1"></div><div class="bg-orb o2"></div><div class="bg-orb o3"></div>'
        '<svg width="0" height="0" style="position:absolute"><defs>'
        '<linearGradient id="sparkGrad" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0" stop-color="#6ee7ff" stop-opacity=".9"/>'
        '<stop offset="1" stop-color="#6ee7ff" stop-opacity="0"/></linearGradient>'
        '</defs></svg>')
html = html[:m.end()] + orbs + html[m.end():]

# ------------------------------------------------- JS helpers (append to 2nd script)
helpers = """
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
"""

# Append helpers to the second script block (before its closing tag)
parts = html.split('</script>')
assert len(parts) >= 3, f"expected 2 script blocks, got {len(parts)-1}"
# parts[1] is the second script content end; insert before its close
parts[1] = parts[1] + helpers
html = '</script>'.join(parts)

# ------------------------------------------------- card function modifications
# 1) teraboxCard: replace bigstat+meter with donut
old_tb = """  const body = has
    ? `<div class="bigstat"><span class="n">${Math.round(pct)}%</span><span class="u">used</span></div>`
      + meter(pct, pct>85?'bad':pct>65?'warn':'')
      + rowline('💾 Used', `<b>${fmtBytes(tb.used)}</b>`)
      + rowline('💾 Free', `<b>${fmtBytes(tb.free)}</b>`)
      + rowline('⬆️ Uploaders', `<b>${uploaders||0}</b>`)"""
new_tb = """  const donut = has ? donutSVG(pct,
      `<div class="lg"><span class="sw" style="background:#5eead4"></span><span>Used <b>${fmtBytes(tb.used)}</b></span></div>`
      + `<div class="lg"><span class="sw" style="background:rgba(255,255,255,.18)"></span><span>Free <b>${fmtBytes(tb.free)}</b></span></div>`,
      'used', ['#5eead4','#38bdf8']) : '';
  const body = has
    ? donut
      + rowline('⬆️ Uploaders', `<b>${uploaders||0}</b>`)
      + sparkSVG('terabox-'+Math.round(pct), 24)"""
assert old_tb in html, "teraboxCard body not found"
html = html.replace(old_tb, new_tb, 1)

# 2b) pcCard: network mesh — pass byId and render device mesh
# Change function signature
old_sig = "function pcCard(d){"
new_sig = "function pcCard(d, byId){"
assert old_sig in html, "pcCard signature not found"
html = html.replace(old_sig, new_sig, 1)

# Add netmesh helper to JS helpers (insert before animateCounters)
old_ac = "/* Animated counters: count .bigstat .n up on first render */"
new_ac = """function netMesh(byId){
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
/* Animated counters: count .bigstat .n up on first render */"""
assert old_ac in html, "animateCounters comment not found"
html = html.replace(old_ac, new_ac, 1)

# Add netmesh to pcCard body (after the Emby rowline)
old_pc_emby = """    + rowline('🎬 Emby', embyOk?`<span class="ok">● ${esc(d.emby.version||'')}</span>`:'<span class="bad">● down</span>')"""
new_pc_emby = """    + rowline('🎬 Emby', embyOk?`<span class="ok">● ${esc(d.emby.version||'')}</span>`:'<span class="bad">● down</span>')
    + `<div class="sesslbl">🌐 Fleet mesh</div>` + netMesh(byId)"""
assert old_pc_emby in html, "pcCard Emby rowline not found"
html = html.replace(old_pc_emby, new_pc_emby, 1)

# Update call site
old_call = "  if(pc) fleet.push(pcCard(pc));"
new_call = "  if(pc) fleet.push(pcCard(pc, byId));"
assert old_call in html, "pcCard call site not found"
html = html.replace(old_call, new_call, 1)

old_pc_body = """    + rowline('⏱️ Uptime', `<b>${fmtUptime(d.uptime_s)}</b>`)
    + meter(d.uptime_s!=null?Math.min(100,(d.uptime_s/86400)*100):0)"""
new_pc_body = """    + rowline('⏱️ Uptime', `<b>${fmtUptime(d.uptime_s)}</b>`)
    + sparkSVG('pc-uptime', 26)"""
assert old_pc_body in html, "pcCard uptime not found"
html = html.replace(old_pc_body, new_pc_body, 1)

# 3) embyCard: poster shelf from recent titles
old_emby = """  const recent=(lib.recent||[]).slice(0,4).map(t=>`<div class="sess"><b>${esc(t)}</b></div>`).join('');"""
new_emby = """  const recent=(lib.recent||[]).slice(0,4).map(t=>`<div class="sess"><b>${esc(t)}</b></div>`).join('');
  const posters=(lib.recent||[]).slice(0,4).map((t,i)=>{
    const grads=[['#0ea5e9','#6366f1'],['#f472b6','#8b5cf6'],['#34d399','#0ea5e9'],['#fbbf24','#f97316']];
    const m=/\\((\\d{4})\\)/.exec(t||''); return {t:(t||'Untitled').replace(/\\s*\\(\\d{4}\\).*$/,''), y:m?m[1]:'', g:grads[i%4]};});
  const shelf=posters.length?posterShelf(posters):'';"""
assert old_emby in html, "embyCard recent not found"
html = html.replace(old_emby, new_emby, 1)

old_emby_body = """    + (recent?`<div class="sesslbl">🆕 Recently added</div>${recent}`:'');"""
new_emby_body = """    + (shelf?`<div class="sesslbl">🆕 Recently added</div>${shelf}`:(recent?`<div class="sesslbl">🆕 Recently added</div>${recent}`:''));"""
assert old_emby_body in html, "embyCard body recent not found"
html = html.replace(old_emby_body, new_emby_body, 1)

# 4) githubCard: contribution graph + counter handled globally
old_gh = """    + `<div class="sess"><b>theartfuldodger-site</b> ↗</div>`;"""
new_gh = """    + `<div class="sess"><b>theartfuldodger-site</b> ↗</div>`
    + contribGraph('github-'+pub+'-'+priv, 13);"""
assert old_gh in html, "githubCard body not found"
html = html.replace(old_gh, new_gh, 1)

# 5) Hook animateCounters into render(): call at end of render after applyFocus.
# render() ends with "  applyFocus();\n}" — hook right after the applyFocus call inside render.
m = re.search(r"(  focus\.c=Math\.min\(focus\.c, ROWS\[focus\.r\]\.cards\.length-1\);\n  applyFocus\(\);)", html)
assert m, "render() end not found"
html = html.replace(m.group(1), m.group(1) + "\n  animateCounters();", 1)

open(PATH, 'w', encoding='utf-8').write(html)
print(f"OK: visualizations added to {PATH} ({len(html)} bytes)")
