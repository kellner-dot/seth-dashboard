/* ============================================================
   Mission Control — Layout Engine (shared module)
   ------------------------------------------------------------
   Used by:
     - mission-control/tv.html and mission-control/index.html
       (TV dashboard renderer)
     - mission-control/editor/index.html (drag-drop layout editor)

   This file owns the layout.json SCHEMA: widget catalog, default
   layout, validation, and row resolution. Widget RENDERING stays in
   the dashboard pages — this module never touches the DOM.

   Sync flow: editor --(GitHub Contents API)--> layout.json on main
              --> TV polls layout.json every 30s (cache-busted) -->
              revision change --> re-render + "Layout updated" toast.

   WebSocket live-sync is a documented future upgrade (see README);
   the GitHub-inbox polling pattern is the current transport.
   ============================================================ */
(function(global){
'use strict';

var SCHEMA_VERSION = 2;

/* ------------------------------------------------------------
   CARD_CATALOG — every placeable widget.
   id: stable slot id used in layout.json (NOT the card's DOM id;
       the TV resolves it through LAYOUT_BUILDERS).
   title/sub/emoji: shown in the editor palette + preview.
   cat: palette grouping.
   ------------------------------------------------------------ */
var CARD_CATALOG = [
  {id:'fleet-pc',         title:'Gaming PC',        sub:'SETHS-PC vitals',   emoji:'🖥️', cat:'My Fleet'},
  {id:'fleet-mac',        title:'MacBook Air',      sub:'mac vitals',        emoji:'💻', cat:'My Fleet'},
  {id:'fleet-iphone',     title:'iPhone',           sub:'xs max · tailnet',  emoji:'📱', cat:'My Fleet'},
  {id:'fleet-razr',       title:'Motorola Razr',    sub:'lifeline line',     emoji:'📱', cat:'My Fleet'},
  {id:'fleet-firetv',     title:'Fire TV Stick 4K', sub:'vega os · firetv',  emoji:'📺', cat:'My Fleet'},

  {id:'media-emby',       title:'Emby Library',     sub:'movies & tv',       emoji:'🎬', cat:'Media'},
  {id:'media-terabox',    title:'TeraBox',          sub:'cloud · tb-direct', emoji:'☁️', cat:'Media'},
  {id:'media-biglybt',    title:'BiglyBT',          sub:'torrents · vpn',    emoji:'🧲', cat:'Media'},
  {id:'media-applemusic', title:'Apple Music',      sub:'my music library',  emoji:'🎵', cat:'Media'},
  {id:'media-artist',     title:'The Artful Dodger',sub:'artist project',    emoji:'🎛️', cat:'Media'},

  {id:'ops-briefing',     title:'Kavi Briefing',    sub:'morning digest',    emoji:'☀️', cat:'Operations'},
  {id:'ops-muse',         title:'Muse',             sub:'chat with kavi',    emoji:'🤖', cat:'Operations'},
  {id:'ops-github',       title:'GitHub',           sub:'kellner-dot',       emoji:'🐙', cat:'Operations'},
  {id:'ops-kaviguard',    title:'KaviGuard',        sub:'pc protection',     emoji:'🛡️', cat:'Operations'},
  {id:'ops-calendar',     title:'Calendar',         sub:'upcoming dates',    emoji:'📅', cat:'Operations'},
  {id:'ops-hearing',      title:'Hearing Countdown',sub:'disability hearing',emoji:'⚖️', cat:'Operations'},

  {id:'watch-pick',       title:'🎲 Surprise Me',   sub:'what should i watch', emoji:'🎲', cat:'Watch'},
  {id:'stats-wall',       title:'2026 in Review',   sub:'stats wall',        emoji:'📊', cat:'Stats'},

  {id:'actions-surprise', title:'🎲 Surprise Me',   sub:'random pick action',emoji:'🎲', cat:'Quick Actions'},
  {id:'actions-photos',   title:'Photo Frame',      sub:'his photography',   emoji:'🖼️', cat:'Quick Actions'},
  {id:'actions-viz',      title:'Visualize',        sub:'music visualizer',  emoji:'🎧', cat:'Quick Actions'},
  {id:'actions-iptv',     title:'IPTV Player',      sub:'tv navigator',      emoji:'📡', cat:'Quick Actions'},
  {id:'actions-refresh',  title:'Refresh',          sub:'reload data',       emoji:'🔄', cat:'Quick Actions'},
  {id:'actions-search',   title:'Search',           sub:'emby · iptv · music',emoji:'🔍', cat:'Quick Actions'},
  {id:'actions-askkavi',  title:'Ask Kavi',         sub:'answers on your tv',emoji:'💬', cat:'Quick Actions'}
];

/* ------------------------------------------------------------
   GROUP_CATALOG — dynamic whole-row groups. A group expands into
   one dashboard row built from live data (movie posters, gauges,
   uptime bars...). The TV resolves them through LAYOUT_GROUPS.
   ------------------------------------------------------------ */
var GROUP_CATALOG = [
  {id:'spotlight-new',      title:'🎬 New on Emby',       emoji:'🎬', cat:'Spotlight'},
  {id:'spotlight-continue', title:'▶️ Continue Watching',  emoji:'▶️', cat:'Spotlight'},
  {id:'vitals',             title:'⚡ System Vitals',      emoji:'⚡', cat:'Tech'},
  {id:'uptime',             title:'📊 Uptime',             emoji:'📊', cat:'Tech'},
  {id:'gh-pulse',           title:'🐙 GitHub Pulse',       emoji:'🐙', cat:'Tech'},
  {id:'mesh',               title:'🕸️ Tailnet Mesh',       emoji:'🕸️', cat:'Tech'},
  {id:'logtail',            title:'📟 Log Tail',           emoji:'📟', cat:'Tech'}
];

function cardById(id){
  for(var i=0;i<CARD_CATALOG.length;i++) if(CARD_CATALOG[i].id===id) return CARD_CATALOG[i];
  return null;
}
function groupById(id){
  for(var i=0;i<GROUP_CATALOG.length;i++) if(GROUP_CATALOG[i].id===id) return GROUP_CATALOG[i];
  return null;
}

/* ------------------------------------------------------------
   defaultLayout() — the built-in layout. Mirrors the dashboard's
   original fixed row order EXACTLY, so enabling the engine changes
   nothing until Seth saves an edit. Returned fresh on each call
   (callers may mutate freely).
   ------------------------------------------------------------ */
function defaultLayout(){
  return {
    version: SCHEMA_VERSION,
    revision: 1,
    updated: '2026-10-03T00:00:00-04:00',
    note: 'Built-in default layout — matches the original fixed row order.',
    rows: [
      {id:'fleet', label:'My Fleet', visible:true,
       cards:['fleet-pc','fleet-mac','fleet-iphone','fleet-razr','fleet-firetv']},
      {id:'media', label:'Media', visible:true,
       cards:['media-emby','media-terabox','media-biglybt','media-applemusic','media-artist']},
      {id:'spotlight-new',      visible:true, group:'spotlight-new'},
      {id:'spotlight-continue', visible:true, group:'spotlight-continue'},
      {id:'vitals',   visible:true, group:'vitals'},
      {id:'uptime',   visible:true, group:'uptime'},
      {id:'gh-pulse', visible:true, group:'gh-pulse'},
      {id:'mesh',     visible:true, group:'mesh'},
      {id:'logtail',  visible:true, group:'logtail'},
      {id:'watch', label:'🎲 What Should I Watch?', visible:true, cards:['watch-pick']},
      {id:'stats', label:'📊 Stats Wall', visible:true, cards:['stats-wall']},
      {id:'ops', label:'Operations', visible:true,
       cards:['ops-muse','ops-github','ops-kaviguard','ops-calendar','ops-hearing']},
      {id:'actions', label:'Quick Actions', visible:true,
       cards:['actions-surprise','actions-photos','actions-viz','actions-iptv',
              'actions-refresh','actions-search','actions-askkavi']}
    ]
  };
}

/* ------------------------------------------------------------
   validateLayout(doc) -> {ok, errors[], warnings[]}
   Structural problems => ok:false (TV falls back to default).
   Unknown card/group ids => warnings only (skipped at render).
   ------------------------------------------------------------ */
function validateLayout(doc){
  var errors=[], warnings=[];
  if(!doc || typeof doc!=='object'){
    return {ok:false, errors:['layout is not an object'], warnings:warnings};
  }
  if(doc.version!==SCHEMA_VERSION){
    errors.push('unsupported version '+JSON.stringify(doc.version)+' (expected '+SCHEMA_VERSION+')');
  }
  if(typeof doc.revision!=='number'){
    errors.push('revision must be a number');
  }
  if(!Array.isArray(doc.rows)){
    errors.push('rows must be an array');
    return {ok:errors.length===0, errors:errors, warnings:warnings};
  }
  var seenRows={};
  doc.rows.forEach(function(rs, ri){
    var where='rows['+ri+']';
    if(!rs || typeof rs!=='object'){ errors.push(where+': not an object'); return; }
    if(typeof rs.id!=='string' || !rs.id){ errors.push(where+': missing id'); return; }
    if(seenRows[rs.id]){ errors.push(where+': duplicate row id "'+rs.id+'"'); return; }
    seenRows[rs.id]=true;
    var hasCards = Array.isArray(rs.cards);
    var hasGroup = typeof rs.group==='string' && rs.group;
    if(!hasCards && !hasGroup){ errors.push(where+' ("'+rs.id+'"): needs cards[] or group'); return; }
    if(hasCards && hasGroup){ errors.push(where+' ("'+rs.id+'"): cards and group are mutually exclusive'); return; }
    if(hasGroup && !groupById(rs.group)){
      warnings.push(where+' ("'+rs.id+'"): unknown group "'+rs.group+'" — row will be skipped');
    }
    if(hasCards){
      rs.cards.forEach(function(cs, ci){
        var cid = (typeof cs==='string') ? cs : (cs && cs.id);
        if(typeof cid!=='string' || !cid){ errors.push(where+'.cards['+ci+']: missing card id'); return; }
        if(!cardById(cid)) warnings.push(where+'.cards['+ci+']: unknown card "'+cid+'" — card will be skipped');
      });
    }
  });
  return {ok:errors.length===0, errors:errors, warnings:warnings};
}

/* ------------------------------------------------------------
   buildRows(doc, j, ctx, builders, groups)
     doc      — layout.json object (or null/invalid → default)
     j, ctx   — dashboard data + device context (passed to builders)
     builders — {cardId: (j,ctx)=>card|null}
     groups   — {groupId: (j,ctx)=>{label,cards}|null}
   Returns [{label, cards:[...], layoutId}] ready for the row
   renderer. Never throws, never returns [] from a valid catalog
   (falls back to defaultLayout on any problem — no blank screen).
   ------------------------------------------------------------ */
function buildRows(doc, j, ctx, builders, groups){
  var d = doc;
  var v = validateLayout(d);
  if(!v.ok){
    try{ console.warn('[mc-layout] invalid layout ('+v.errors.join('; ')+') — using default'); }catch(e){}
    d = defaultLayout();
  } else if(v.warnings.length){
    try{ console.warn('[mc-layout] warnings: '+v.warnings.join('; ')); }catch(e){}
  }
  builders = builders||{};
  groups = groups||{};
  var rows=[];
  var seenRowIds={};
  (d.rows||[]).forEach(function(rs){
    if(!rs || rs.visible===false) return;
    if(seenRowIds[rs.id]) return;
    seenRowIds[rs.id]=true;
    // --- dynamic group row ---
    if(rs.group){
      var g = groups[rs.group];
      if(typeof g!=='function') return;
      var grow=null;
      try{ grow=g(j,ctx); }catch(e){ try{console.warn('[mc-layout] group "'+rs.group+'" failed: '+e.message);}catch(_){} }
      if(grow && grow.cards && grow.cards.length){
        rows.push({label: rs.label || grow.label || '', cards: grow.cards, layoutId: rs.id});
      }
      return;
    }
    // --- explicit card row ---
    var cards=[];
    (rs.cards||[]).forEach(function(cs){
      var cid = (typeof cs==='string') ? cs : (cs && cs.id);
      var cvis = (typeof cs==='string') ? true : !(cs && cs.visible===false);
      if(!cid || !cvis) return;
      var b = builders[cid];
      if(typeof b!=='function'){
        try{ console.warn('[mc-layout] unknown card id "'+cid+'" — skipped'); }catch(e){}
        return;
      }
      var card=null;
      try{ card=b(j,ctx); }catch(e){
        try{ console.warn('[mc-layout] builder "'+cid+'" threw: '+e.message); }catch(_){}
      }
      if(card) cards.push(card);
    });
    if(cards.length) rows.push({label: rs.label||'', cards: cards, layoutId: rs.id});
  });
  // Absolute last resort: if EVERYTHING resolved empty (e.g. all data
  // missing AND default also empty), still return one explanatory row
  // rather than a blank screen.
  if(!rows.length){
    rows.push({label:'', layoutId:'__empty', cards:[{
      id:'__empty', cls:'k-act', icon:'bolt', title:'No cards to show',
      sub:'data feeds offline', dot:'', pill:'',
      body:'<div class="dim">The collector feeds are unreachable. Check status.json.</div>',
      detail:''
    }]});
  }
  return rows;
}

global.MCLayout = {
  SCHEMA_VERSION: SCHEMA_VERSION,
  CARD_CATALOG: CARD_CATALOG,
  GROUP_CATALOG: GROUP_CATALOG,
  cardById: cardById,
  groupById: groupById,
  defaultLayout: defaultLayout,
  validateLayout: validateLayout,
  buildRows: buildRows
};

})(typeof window!=='undefined' ? window : this);
