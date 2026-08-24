"""
MCS_LAUNCHER.py — Single-file launcher for the MCS CVOR RMS system.

Usage:
    python MCS_LAUNCHER.py            # normal launch
    python MCS_LAUNCHER.py --reset    # delete and rewrite all generated files
    python MCS_LAUNCHER.py --browser-only  # skip Tkinter, open HTML in browser
    python MCS_LAUNCHER.py --no-backend    # skip Flask backend (offline/demo)
"""

from __future__ import annotations

# ── EMBEDDED FILE CONTENTS ────────────────────────────────────────────────────

HTML_CONTENT = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>MCS CVOR RMS</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#0a0e17;--panel:#111827;--border:#1e2d45;--accent:#00aaff;--accent2:#00ff99;--text:#c8d6e5;--muted:#4a5e72}
body{background:var(--bg);color:var(--text);font-family:'Segoe UI',Arial,sans-serif;height:100vh;display:flex;flex-direction:column;overflow:hidden}
header{background:var(--panel);border-bottom:1px solid var(--border);padding:8px 16px;display:flex;align-items:center;justify-content:space-between;flex-shrink:0}
.logo{font-size:1.1rem;font-weight:700;color:var(--accent);letter-spacing:2px}
.clock{font-size:.85rem;color:var(--accent2);font-family:monospace}
nav{display:flex;gap:4px}
nav button{background:transparent;border:1px solid var(--border);color:var(--text);padding:5px 14px;border-radius:4px;cursor:pointer;font-size:.8rem;transition:all .2s}
nav button.active,nav button:hover{background:var(--accent);color:#000;border-color:var(--accent)}
main{flex:1;display:flex;overflow:hidden}
#sidebar{width:260px;background:var(--panel);border-right:1px solid var(--border);display:flex;flex-direction:column;overflow:hidden}
#content{flex:1;overflow-y:auto;padding:16px}
.tab{display:none}.tab.active{display:block}
/* Dashboard */
.kpi-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:12px;margin-bottom:20px}
.kpi{background:var(--panel);border:1px solid var(--border);border-radius:8px;padding:14px;text-align:center}
.kpi .val{font-size:1.8rem;font-weight:700;color:var(--accent)}
.kpi .lbl{font-size:.75rem;color:var(--muted);margin-top:4px}
.table-wrap{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:.82rem}
th,td{padding:8px 10px;border-bottom:1px solid var(--border);text-align:left}
th{color:var(--muted);font-weight:600;background:var(--panel)}
tr:hover td{background:#151e2e}
.badge{display:inline-block;padding:2px 8px;border-radius:12px;font-size:.7rem;font-weight:700;text-transform:uppercase}
.ONLINE{background:#003d1a;color:#00ff99;border:1px solid #00ff99}
.OFFLINE{background:#3d0000;color:#ff3b30;border:1px solid #ff3b30}
.FAULT{background:#3d2d00;color:#ffcc00;border:1px solid #ffcc00}
.MAINTENANCE{background:#222;color:#888;border:1px solid #888}
.UNKNOWN{background:#0d1a2e;color:#3a5070;border:1px solid #3a5070}
/* Map */
#map-container{display:flex;height:calc(100vh - 100px)}
#map{flex:1}
#map-legend{width:220px;background:var(--panel);border-left:1px solid var(--border);padding:12px;overflow-y:auto;font-size:.8rem}
#map-legend h4{color:var(--accent);margin-bottom:10px}
.legend-item{display:flex;align-items:center;gap:8px;margin-bottom:6px;cursor:pointer}
.legend-dot{width:12px;height:12px;border-radius:50%;flex-shrink:0}
/* Sidebar filters */
#sidebar h3{padding:12px;color:var(--accent);font-size:.85rem;border-bottom:1px solid var(--border);flex-shrink:0}
#filter-list{overflow-y:auto;flex:1;padding:8px}
.filter-item{padding:6px 8px;border-radius:4px;cursor:pointer;display:flex;align-items:center;gap:8px;font-size:.8rem}
.filter-item:hover{background:var(--border)}
.filter-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
/* API bar */
#api-bar{background:var(--panel);border-top:1px solid var(--border);padding:6px 12px;display:flex;align-items:center;gap:8px;font-size:.75rem;flex-shrink:0}
#api-url{background:#0d1520;border:1px solid var(--border);color:var(--text);padding:3px 8px;border-radius:4px;width:260px;font-size:.75rem}
/* Buttons */
.btn{background:var(--accent);color:#000;border:none;padding:6px 14px;border-radius:4px;cursor:pointer;font-size:.8rem;font-weight:600}
.btn:hover{opacity:.85}
.btn-sm{padding:3px 8px;font-size:.75rem}
.btn-danger{background:#ff3b30;color:#fff}
.btn-outline{background:transparent;border:1px solid var(--accent);color:var(--accent)}
/* Modal */
.modal-overlay{position:fixed;inset:0;background:rgba(0,0,0,.7);display:none;align-items:center;justify-content:center;z-index:9999}
.modal-overlay.open{display:flex}
.modal{background:var(--panel);border:1px solid var(--border);border-radius:10px;width:700px;max-width:95vw;max-height:90vh;display:flex;flex-direction:column;overflow:hidden}
.modal-header{padding:14px 18px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center}
.modal-header h3{color:var(--accent);font-size:1rem}
.modal-body{flex:1;overflow-y:auto;padding:18px}
.modal-tabs{display:flex;gap:4px;margin-bottom:16px;border-bottom:1px solid var(--border);padding-bottom:8px}
.mtab{background:transparent;border:1px solid var(--border);color:var(--text);padding:4px 12px;border-radius:4px;cursor:pointer;font-size:.8rem}
.mtab.active{background:var(--accent);color:#000;border-color:var(--accent)}
.modal-tab-content{display:none}.modal-tab-content.active{display:block}
/* Forms */
.form-row{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:10px}
.form-group{display:flex;flex-direction:column;gap:4px}
label{font-size:.75rem;color:var(--muted)}
input,select,textarea{background:#0d1520;border:1px solid var(--border);color:var(--text);padding:6px 10px;border-radius:4px;font-size:.8rem}
input:focus,select:focus,textarea:focus{outline:none;border-color:var(--accent)}
/* Shelter SVG */
.shelter-wrap{background:#050b14;border:1px solid var(--border);border-radius:6px;padding:16px;display:flex;justify-content:center}
/* Notification */
#notif{position:fixed;top:60px;right:20px;background:var(--panel);border:1px solid var(--accent2);color:var(--accent2);padding:10px 18px;border-radius:6px;font-size:.82rem;z-index:10000;display:none;animation:fadeIn .3s}
@keyframes fadeIn{from{opacity:0;transform:translateY(-8px)}to{opacity:1;transform:translateY(0)}}
/* File import area */
.drop-zone{border:2px dashed var(--border);border-radius:8px;padding:30px;text-align:center;cursor:pointer;transition:border-color .2s}
.drop-zone:hover,.drop-zone.drag{border-color:var(--accent)}
pre.preview{background:#050b14;border:1px solid var(--border);border-radius:4px;padding:12px;font-size:.75rem;max-height:200px;overflow-y:auto;white-space:pre-wrap}
</style>
</head>
<body>
<header>
  <span class="logo">&#9670; MCS CVOR RMS</span>
  <nav>
    <button class="active" onclick="showTab('dashboard')">Dashboard</button>
    <button onclick="showTab('bases')">Bases</button>
    <button onclick="showTab('cvor')">CVOR Systems</button>
    <button onclick="showTab('map')">Map</button>
    <button onclick="showTab('import')">Import</button>
  </nav>
  <span class="clock" id="clock">UTC 00:00:00</span>
</header>
<main>
  <div id="sidebar">
    <h3>&#9654; FILTERS</h3>
    <div id="filter-list"></div>
  </div>
  <div id="content">

    <!-- DASHBOARD -->
    <div class="tab active" id="tab-dashboard">
      <div class="kpi-grid" id="kpi-grid"></div>
      <h3 style="color:var(--accent);margin-bottom:10px;font-size:.9rem">ALL CVOR SYSTEMS</h3>
      <div class="table-wrap">
        <table id="dash-table">
          <thead><tr><th>Base</th><th>CVOR</th><th>Freq (MHz)</th><th>Power</th><th>Status</th><th>Last Seen</th><th></th></tr></thead>
          <tbody></tbody>
        </table>
      </div>
    </div>

    <!-- BASES -->
    <div class="tab" id="tab-bases">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
        <h3 style="color:var(--accent);font-size:.9rem">SAAF BASES</h3>
        <div style="display:flex;gap:8px">
          <button class="btn btn-sm btn-outline" onclick="exportAll()">Export All</button>
          <button class="btn btn-sm" onclick="openBaseModal()">+ Add Base</button>
        </div>
      </div>
      <div class="table-wrap">
        <table id="bases-table">
          <thead><tr><th>ID</th><th>Name</th><th>Location</th><th>Lat</th><th>Lon</th><th>CVOR Units</th><th></th></tr></thead>
          <tbody></tbody>
        </table>
      </div>
    </div>

    <!-- CVOR -->
    <div class="tab" id="tab-cvor">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
        <h3 style="color:var(--accent);font-size:.9rem">CVOR SYSTEMS</h3>
        <button class="btn btn-sm" onclick="openCvorModal()">+ Add CVOR</button>
      </div>
      <div class="table-wrap">
        <table id="cvor-table">
          <thead><tr><th>Base</th><th>Name</th><th>IP</th><th>Freq</th><th>Power</th><th>Mode</th><th>Status</th><th></th></tr></thead>
          <tbody></tbody>
        </table>
      </div>
    </div>

    <!-- MAP -->
    <div class="tab" id="tab-map">
      <div id="map-container">
        <div id="map"></div>
        <div id="map-legend">
          <h4>STATUS</h4>
          <div class="legend-item" onclick="toggleFilter('ONLINE')">
            <div class="legend-dot" style="background:#00ff99"></div><span>Online</span>
          </div>
          <div class="legend-item" onclick="toggleFilter('OFFLINE')">
            <div class="legend-dot" style="background:#ff3b30"></div><span>Offline</span>
          </div>
          <div class="legend-item" onclick="toggleFilter('FAULT')">
            <div class="legend-dot" style="background:#ffcc00"></div><span>Fault</span>
          </div>
          <div class="legend-item" onclick="toggleFilter('MAINTENANCE')">
            <div class="legend-dot" style="background:#888"></div><span>Maintenance</span>
          </div>
          <div class="legend-item" onclick="toggleFilter('UNKNOWN')">
            <div class="legend-dot" style="background:#3a5070"></div><span>Unknown</span>
          </div>
          <hr style="border-color:var(--border);margin:12px 0"/>
          <h4>BASES</h4>
          <div id="base-legend"></div>
        </div>
      </div>
    </div>

    <!-- IMPORT -->
    <div class="tab" id="tab-import">
      <h3 style="color:var(--accent);margin-bottom:14px;font-size:.9rem">FILE IMPORT</h3>
      <div class="drop-zone" id="drop-zone" onclick="document.getElementById('file-input').click()">
        <p style="color:var(--muted)">Drop .ini / config.sys / .lda files here or click to browse</p>
        <input type="file" id="file-input" multiple accept=".ini,.sys,.lda" style="display:none" onchange="handleFiles(this.files)"/>
      </div>
      <div id="import-results" style="margin-top:14px"></div>
    </div>

  </div>
</main>
<div id="api-bar">
  <span style="color:var(--muted)">API:</span>
  <input id="api-url" value="http://localhost:8080" onchange="setApiUrl(this.value)"/>
  <button class="btn btn-sm" onclick="detectNetwork()">Detect</button>
  <button class="btn btn-sm btn-outline" onclick="loadAll()">&#8635; Refresh</button>
  <span id="api-status" style="color:var(--muted);margin-left:8px">—</span>
</div>

<!-- MODAL -->
<div class="modal-overlay" id="modal" onclick="if(event.target===this)closeModal()">
  <div class="modal">
    <div class="modal-header">
      <h3 id="modal-title">Details</h3>
      <button class="btn btn-sm btn-danger" onclick="closeModal()">✕</button>
    </div>
    <div class="modal-body" id="modal-body"></div>
  </div>
</div>

<!-- ADD BASE MODAL -->
<div class="modal-overlay" id="base-modal" onclick="if(event.target===this)closeBaseModal()">
  <div class="modal">
    <div class="modal-header">
      <h3 id="base-modal-title">Add Base</h3>
      <button class="btn btn-sm btn-danger" onclick="closeBaseModal()">✕</button>
    </div>
    <div class="modal-body">
      <div class="form-row">
        <div class="form-group"><label>Name</label><input id="b-name" placeholder="AFB Waterkloof"/></div>
        <div class="form-group"><label>Location</label><input id="b-location" placeholder="Pretoria"/></div>
      </div>
      <div class="form-row">
        <div class="form-group"><label>Latitude</label><input id="b-lat" type="number" step="any" placeholder="-25.83"/></div>
        <div class="form-group"><label>Longitude</label><input id="b-lon" type="number" step="any" placeholder="28.22"/></div>
      </div>
      <div style="text-align:right;margin-top:12px">
        <button class="btn" onclick="saveBase()">Save</button>
      </div>
    </div>
  </div>
</div>

<!-- ADD CVOR MODAL -->
<div class="modal-overlay" id="cvor-modal" onclick="if(event.target===this)closeCvorModal()">
  <div class="modal">
    <div class="modal-header">
      <h3 id="cvor-modal-title">Add CVOR</h3>
      <button class="btn btn-sm btn-danger" onclick="closeCvorModal()">✕</button>
    </div>
    <div class="modal-body">
      <div class="form-row">
        <div class="form-group"><label>Base</label><select id="c-base"></select></div>
        <div class="form-group"><label>Name</label><input id="c-name" placeholder="CVOR-1"/></div>
      </div>
      <div class="form-row">
        <div class="form-group"><label>IP Address</label><input id="c-ip" placeholder="192.168.1.100"/></div>
        <div class="form-group"><label>Port</label><input id="c-port" type="number" value="2101"/></div>
      </div>
      <div class="form-row">
        <div class="form-group"><label>Frequency (MHz)</label><input id="c-freq" type="number" step="0.05" placeholder="112.30"/></div>
        <div class="form-group"><label>Power (W)</label><input id="c-power" type="number" step="1" placeholder="50"/></div>
      </div>
      <div class="form-row">
        <div class="form-group"><label>Mode</label>
          <select id="c-mode"><option>NORMAL</option><option>STANDBY</option><option>TEST</option></select>
        </div>
        <div class="form-group"><label>Status</label>
          <select id="c-status"><option>UNKNOWN</option><option>ONLINE</option><option>OFFLINE</option><option>FAULT</option><option>MAINTENANCE</option></select>
        </div>
      </div>
      <div style="text-align:right;margin-top:12px">
        <button class="btn" onclick="saveCvor()">Save</button>
      </div>
    </div>
  </div>
</div>

<div id="notif"></div>

<script>
// ── Configuration ─────────────────────────────────────────────────────────────
let API_URL = localStorage.getItem('mcs_api_url') || 'http://localhost:8080';
document.getElementById('api-url').value = API_URL;

function setApiUrl(v){API_URL=v.trim();localStorage.setItem('mcs_api_url',API_URL);}

// ── Demo bases (used when backend unavailable) ────────────────────────────────
const DEMO_BASES = [
  {id:1,name:'AFB Waterkloof',location:'Pretoria',lat:-25.830,lon:28.222},
  {id:2,name:'Hoedspruit AFB',location:'Hoedspruit',lat:-24.368,lon:31.049},
  {id:3,name:'Langebaanweg AFB',location:'Langebaanweg',lat:-32.970,lon:18.160},
  {id:4,name:'Overberg Test Range',location:'Bredasdorp',lat:-34.554,lon:20.314},
  {id:5,name:'Louis Trichardt AFB',location:'Louis Trichardt',lat:-23.055,lon:29.924},
  {id:6,name:'Ysterplaat AFB',location:'Cape Town',lat:-33.882,lon:18.497},
  {id:7,name:'Makhado AFB',location:'Makhado',lat:-23.155,lon:29.698},
  {id:8,name:'Port Elizabeth AFB',location:'Port Elizabeth',lat:-33.985,lon:25.617},
  {id:9,name:'Durban AFB',location:'Durban',lat:-29.970,lon:30.950},
  {id:10,name:'Bloemfontein AFB',location:'Bloemfontein',lat:-29.094,lon:26.302},
];

// ── State ─────────────────────────────────────────────────────────────────────
let allBases=[], allCvor=[], map=null, markers=[], activeFilters=new Set(['ONLINE','OFFLINE','FAULT','MAINTENANCE','UNKNOWN']);
let editingBaseId=null, editingCvorId=null;

// ── Clock ─────────────────────────────────────────────────────────────────────
function tick(){const n=new Date;document.getElementById('clock').textContent='UTC '+n.toUTCString().slice(17,25);}
setInterval(tick,1000);tick();

// ── Tab switching ─────────────────────────────────────────────────────────────
function showTab(name,btn){
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  document.querySelectorAll('nav button').forEach(b=>b.classList.remove('active'));
  document.getElementById('tab-'+name).classList.add('active');
  const target=btn||(typeof event!=='undefined'&&event&&event.target&&event.target.matches('nav button')?event.target:null);
  if(target)target.classList.add('active');
  if(name==='map'){setTimeout(()=>{if(map)map.invalidateSize();else initMap();},100);}
}

// ── Notification ──────────────────────────────────────────────────────────────
function notify(msg,dur=3000){
  const n=document.getElementById('notif');
  n.textContent=msg;n.style.display='block';
  clearTimeout(n._t);n._t=setTimeout(()=>n.style.display='none',dur);
}

// ── API helper ────────────────────────────────────────────────────────────────
async function api(path,opt={}){
  const st=document.getElementById('api-status');
  try{
    const r=await fetch(API_URL+path,{headers:{'Content-Type':'application/json'},...opt});
    if(!r.ok)throw new Error(r.status);
    st.textContent='●  Connected';st.style.color='var(--accent2)';
    return r.json();
  }catch(e){
    st.textContent='●  Offline';st.style.color='var(--muted)';
    throw e;
  }
}

// ── Load all data ─────────────────────────────────────────────────────────────
async function loadAll(){
  try{
    [allBases,allCvor]=await Promise.all([api('/api/bases'),api('/api/cvor')]);
  }catch{
    allBases=DEMO_BASES;allCvor=[];
  }
  renderDashboard();renderBases();renderCvor();renderSidebarFilters();
  if(map)renderMapMarkers();
}

// ── Dashboard ─────────────────────────────────────────────────────────────────
function renderDashboard(){
  const counts={ONLINE:0,OFFLINE:0,FAULT:0,MAINTENANCE:0,UNKNOWN:0};
  allCvor.forEach(c=>counts[c.status]=(counts[c.status]||0)+1);
  document.getElementById('kpi-grid').innerHTML=
    `<div class="kpi"><div class="val" style="color:var(--accent2)">${counts.ONLINE}</div><div class="lbl">ONLINE</div></div>`+
    `<div class="kpi"><div class="val" style="color:#ff3b30">${counts.OFFLINE}</div><div class="lbl">OFFLINE</div></div>`+
    `<div class="kpi"><div class="val" style="color:#ffcc00">${counts.FAULT}</div><div class="lbl">FAULT</div></div>`+
    `<div class="kpi"><div class="val">${allBases.length}</div><div class="lbl">BASES</div></div>`+
    `<div class="kpi"><div class="val">${allCvor.length}</div><div class="lbl">CVOR UNITS</div></div>`;
  const tbody=document.querySelector('#dash-table tbody');
  tbody.innerHTML=allCvor.map(c=>{
    const base=allBases.find(b=>b.id===c.base_id)||{name:'—'};
    return `<tr><td>${base.name}</td><td>${c.name}</td><td>${c.frequency||'—'}</td><td>${c.power_w||'—'} W</td><td><span class="badge ${c.status}">${c.status}</span></td><td>${c.last_seen||'—'}</td><td><button class="btn btn-sm" onclick="openCvorDetail(${c.id})">Details</button></td></tr>`;
  }).join('');
}

// ── Bases ─────────────────────────────────────────────────────────────────────
function renderBases(){
  const tbody=document.querySelector('#bases-table tbody');
  tbody.innerHTML=allBases.map(b=>{
    const cnt=allCvor.filter(c=>c.base_id===b.id).length;
    return `<tr><td>${b.id}</td><td>${b.name}</td><td>${b.location||'—'}</td><td>${b.lat}</td><td>${b.lon}</td><td>${cnt}</td><td>
      <button class="btn btn-sm btn-outline" onclick="exportBase(${b.id})">Export</button>
      <button class="btn btn-sm" onclick="editBase(${b.id})">Edit</button>
      <button class="btn btn-sm btn-danger" onclick="deleteBase(${b.id})">Del</button>
    </td></tr>`;
  }).join('');
}

function openBaseModal(id=null){
  editingBaseId=id;
  document.getElementById('base-modal-title').textContent=id?'Edit Base':'Add Base';
  if(id){const b=allBases.find(x=>x.id===id);if(b){document.getElementById('b-name').value=b.name;document.getElementById('b-location').value=b.location||'';document.getElementById('b-lat').value=b.lat;document.getElementById('b-lon').value=b.lon;}}
  else{['b-name','b-location','b-lat','b-lon'].forEach(x=>document.getElementById(x).value='');}
  document.getElementById('base-modal').classList.add('open');
}
function closeBaseModal(){document.getElementById('base-modal').classList.remove('open');editingBaseId=null;}
function editBase(id){openBaseModal(id);}

async function saveBase(){
  const payload={name:document.getElementById('b-name').value,location:document.getElementById('b-location').value,lat:parseFloat(document.getElementById('b-lat').value),lon:parseFloat(document.getElementById('b-lon').value)};
  try{
    if(editingBaseId)await api('/api/bases/'+editingBaseId,{method:'PUT',body:JSON.stringify(payload)});
    else await api('/api/bases',{method:'POST',body:JSON.stringify(payload)});
    notify('Base saved');closeBaseModal();loadAll();
  }catch{notify('Save failed (offline mode)');}
}

async function deleteBase(id){
  if(!confirm('Delete base?'))return;
  try{await api('/api/bases/'+id,{method:'DELETE'});notify('Deleted');loadAll();}
  catch{notify('Delete failed (offline mode)');}
}

// ── CVOR ──────────────────────────────────────────────────────────────────────
function renderCvor(){
  const tbody=document.querySelector('#cvor-table tbody');
  tbody.innerHTML=allCvor.map(c=>{
    const base=allBases.find(b=>b.id===c.base_id)||{name:'—'};
    return `<tr><td>${base.name}</td><td>${c.name}</td><td>${c.ip_address||'—'}</td><td>${c.frequency||'—'} MHz</td><td>${c.power_w||'—'} W</td><td>${c.mode||'—'}</td><td><span class="badge ${c.status}">${c.status}</span></td><td>
      <button class="btn btn-sm" onclick="openCvorDetail(${c.id})">Details</button>
      <button class="btn btn-sm btn-danger" onclick="deleteCvor(${c.id})">Del</button>
    </td></tr>`;
  }).join('');
}

function openCvorModal(id=null){
  editingCvorId=id;
  document.getElementById('cvor-modal-title').textContent=id?'Edit CVOR':'Add CVOR';
  const sel=document.getElementById('c-base');
  sel.innerHTML=allBases.map(b=>`<option value="${b.id}">${b.name}</option>`).join('');
  if(id){const c=allCvor.find(x=>x.id===id);if(c){sel.value=c.base_id;document.getElementById('c-name').value=c.name;document.getElementById('c-ip').value=c.ip_address||'';document.getElementById('c-port').value=c.port||2101;document.getElementById('c-freq').value=c.frequency||'';document.getElementById('c-power').value=c.power_w||'';document.getElementById('c-mode').value=c.mode||'NORMAL';document.getElementById('c-status').value=c.status||'UNKNOWN';}}
  document.getElementById('cvor-modal').classList.add('open');
}
function closeCvorModal(){document.getElementById('cvor-modal').classList.remove('open');editingCvorId=null;}

async function saveCvor(){
  const payload={base_id:parseInt(document.getElementById('c-base').value),name:document.getElementById('c-name').value,ip_address:document.getElementById('c-ip').value,port:parseInt(document.getElementById('c-port').value),frequency:parseFloat(document.getElementById('c-freq').value),power_w:parseInt(document.getElementById('c-power').value),mode:document.getElementById('c-mode').value,status:document.getElementById('c-status').value};
  try{
    if(editingCvorId)await api('/api/cvor/'+editingCvorId,{method:'PUT',body:JSON.stringify(payload)});
    else await api('/api/cvor',{method:'POST',body:JSON.stringify(payload)});
    notify('CVOR saved');closeCvorModal();loadAll();
  }catch{notify('Save failed (offline mode)');}
}

async function deleteCvor(id){
  if(!confirm('Delete CVOR?'))return;
  try{await api('/api/cvor/'+id,{method:'DELETE'});notify('Deleted');loadAll();}
  catch{notify('Delete failed (offline mode)');}
}

async function openCvorDetail(id){
  const c=allCvor.find(x=>x.id===id);
  if(!c)return;
  const base=allBases.find(b=>b.id===c.base_id)||{name:'—'};
  let alarms=[];
  try{alarms=(await api('/api/cvor/'+id+'/alarms')).alarms||[];}catch{}
  document.getElementById('modal-title').textContent=c.name+' — '+base.name;
  document.getElementById('modal-body').innerHTML=`
    <div class="modal-tabs">
      <button class="mtab active" onclick="switchMtab(0,this)">Status</button>
      <button class="mtab" onclick="switchMtab(1,this)">Settings</button>
      <button class="mtab" onclick="switchMtab(2,this)">Shelter</button>
      <button class="mtab" onclick="switchMtab(3,this)">Remote Control</button>
    </div>
    <div class="modal-tab-content active" id="mtab-0">
      <table style="width:100%">
        <tr><td style="color:var(--muted)">Status</td><td><span class="badge ${c.status}">${c.status}</span></td></tr>
        <tr><td style="color:var(--muted)">IP</td><td>${c.ip_address||'—'}:${c.port||'—'}</td></tr>
        <tr><td style="color:var(--muted)">Frequency</td><td>${c.frequency||'—'} MHz</td></tr>
        <tr><td style="color:var(--muted)">Power</td><td>${c.power_w||'—'} W</td></tr>
        <tr><td style="color:var(--muted)">Mode</td><td>${c.mode||'—'}</td></tr>
        <tr><td style="color:var(--muted)">Last Seen</td><td>${c.last_seen||'—'}</td></tr>
      </table>
      <h4 style="margin-top:14px;margin-bottom:8px;color:var(--accent);font-size:.8rem">ALARMS</h4>
      ${alarms.length?`<table><thead><tr><th>Time</th><th>Code</th><th>Message</th><th>Severity</th></tr></thead><tbody>${alarms.map(a=>`<tr><td>${a.timestamp||''}</td><td>${a.alarm_code||''}</td><td>${a.message||''}</td><td>${a.severity||''}</td></tr>`).join('')}</tbody></table>`:'<p style="color:var(--muted);font-size:.8rem">No alarms</p>'}
      <div style="margin-top:12px">
        <button class="btn btn-sm" onclick="pingCvor(${c.id})">&#9679; Ping</button>
      </div>
    </div>
    <div class="modal-tab-content" id="mtab-1">
      <div class="form-row">
        <div class="form-group"><label>Frequency</label><input id="m-freq" value="${c.frequency||''}"/></div>
        <div class="form-group"><label>Power (W)</label><input id="m-power" value="${c.power_w||''}"/></div>
      </div>
      <div class="form-row">
        <div class="form-group"><label>Mode</label>
          <select id="m-mode"><option ${c.mode==='NORMAL'?'selected':''}>NORMAL</option><option ${c.mode==='STANDBY'?'selected':''}>STANDBY</option><option ${c.mode==='TEST'?'selected':''}>TEST</option></select>
        </div>
        <div class="form-group"><label>Ident</label><input id="m-ident" value="${c.ident||''}"/></div>
      </div>
      <button class="btn btn-sm" onclick="applySettings(${c.id})">Apply Settings</button>
    </div>
    <div class="modal-tab-content" id="mtab-2">
      <div class="shelter-wrap">
        <svg width="400" height="280" viewBox="0 0 400 280">
          <rect width="400" height="280" fill="#050b14"/>
          <rect x="30" y="40" width="340" height="200" rx="8" fill="none" stroke="#1e2d45" stroke-width="2"/>
          <rect x="30" y="40" width="340" height="30" fill="#111827"/>
          <text x="200" y="61" fill="#00aaff" font-size="12" text-anchor="middle">SHELTER LAYOUT</text>
          <!-- Rack 1 -->
          <rect x="60" y="90" width="60" height="130" rx="4" fill="#0d1520" stroke="#1e2d45"/>
          <text x="90" y="108" fill="#4a5e72" font-size="9" text-anchor="middle">RACK 1</text>
          <rect x="68" y="115" width="44" height="20" rx="2" fill="#003d1a" stroke="#00ff99"/>
          <text x="90" y="129" fill="#00ff99" font-size="7" text-anchor="middle">TX-A</text>
          <rect x="68" y="140" width="44" height="20" rx="2" fill="#003d1a" stroke="#00ff99"/>
          <text x="90" y="154" fill="#00ff99" font-size="7" text-anchor="middle">TX-B</text>
          <rect x="68" y="165" width="44" height="20" rx="2" fill="#0d1520" stroke="#1e2d45"/>
          <text x="90" y="179" fill="#4a5e72" font-size="7" text-anchor="middle">STANDBY</text>
          <!-- Rack 2 -->
          <rect x="140" y="90" width="60" height="130" rx="4" fill="#0d1520" stroke="#1e2d45"/>
          <text x="170" y="108" fill="#4a5e72" font-size="9" text-anchor="middle">RACK 2</text>
          <rect x="148" y="115" width="44" height="20" rx="2" fill="#111827" stroke="#00aaff"/>
          <text x="170" y="129" fill="#00aaff" font-size="7" text-anchor="middle">MONITOR</text>
          <rect x="148" y="140" width="44" height="20" rx="2" fill="#111827" stroke="#00aaff"/>
          <text x="170" y="154" fill="#00aaff" font-size="7" text-anchor="middle">CONTROL</text>
          <!-- UPS -->
          <rect x="260" y="140" width="80" height="50" rx="4" fill="#1a1000" stroke="#ffcc00"/>
          <text x="300" y="162" fill="#ffcc00" font-size="9" text-anchor="middle">UPS</text>
          <text x="300" y="178" fill="#ffcc00" font-size="7" text-anchor="middle">BACKUP</text>
          <!-- AC -->
          <rect x="260" y="90" width="80" height="40" rx="4" fill="#001a1a" stroke="#00aaff"/>
          <text x="300" y="115" fill="#00aaff" font-size="9" text-anchor="middle">A/C UNIT</text>
          <!-- Door -->
          <rect x="175" y="220" width="50" height="18" rx="2" fill="#111827" stroke="#1e2d45"/>
          <text x="200" y="232" fill="#4a5e72" font-size="8" text-anchor="middle">DOOR</text>
        </svg>
      </div>
    </div>
    <div class="modal-tab-content" id="mtab-3">
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:14px">
        <button class="btn" onclick="sendCmd(${c.id},'REBOOT')">&#9851; Reboot</button>
        <button class="btn btn-outline" onclick="sendCmd(${c.id},'APPLY_CONFIG')">Apply Config</button>
        <button class="btn btn-outline" onclick="sendCmd(${c.id},'SET_MODE',{mode:'NORMAL'})">Set NORMAL</button>
        <button class="btn btn-outline" onclick="sendCmd(${c.id},'SET_MODE',{mode:'STANDBY'})">Set STANDBY</button>
      </div>
      <div id="cmd-result" style="font-family:monospace;font-size:.75rem;color:var(--accent2);background:#050b14;padding:10px;border-radius:4px;min-height:60px"></div>
    </div>
  `;
  document.getElementById('modal').classList.add('open');
}

function switchMtab(idx,btn){
  document.querySelectorAll('.mtab').forEach(b=>b.classList.remove('active'));
  document.querySelectorAll('.modal-tab-content').forEach(t=>t.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('mtab-'+idx).classList.add('active');
}

async function pingCvor(id){
  try{const r=await api('/api/cvor/'+id+'/ping',{method:'POST'});notify('Ping: '+r.status);}
  catch{notify('Ping failed');}
}

async function applySettings(id){
  const payload={command:'APPLY_CONFIG',params:{frequency:document.getElementById('m-freq').value,power:document.getElementById('m-power').value,mode:document.getElementById('m-mode').value,ident:document.getElementById('m-ident').value}};
  try{const r=await api('/api/cvor/'+id+'/command',{method:'POST',body:JSON.stringify(payload)});notify('Applied: '+r.result);}
  catch{notify('Apply failed (offline mode)');}
}

async function sendCmd(id,command,params={}){
  const el=document.getElementById('cmd-result');
  el.textContent='Sending…';
  try{const r=await api('/api/cvor/'+id+'/command',{method:'POST',body:JSON.stringify({command,params})});el.textContent=JSON.stringify(r,null,2);}
  catch{el.textContent='Error: offline or connection refused';}
}

// ── Map ───────────────────────────────────────────────────────────────────────
const STATUS_COLOR={ONLINE:'#00ff99',OFFLINE:'#ff3b30',FAULT:'#ffcc00',MAINTENANCE:'#888',UNKNOWN:'#3a5070'};

function makePin(color){
  return `<svg xmlns="http://www.w3.org/2000/svg" width="28" height="36" viewBox="0 0 28 36">
    <circle cx="14" cy="14" r="10" fill="${color}" opacity=".2">
      <animate attributeName="r" values="10;14;10" dur="2s" repeatCount="indefinite"/>
      <animate attributeName="opacity" values=".2;0;.2" dur="2s" repeatCount="indefinite"/>
    </circle>
    <path d="M14 2C8.48 2 4 6.48 4 12c0 7.5 10 22 10 22S24 19.5 24 12c0-5.52-4.48-10-10-10z" fill="${color}" stroke="#000" stroke-width="1"/>
    <circle cx="14" cy="12" r="4" fill="#fff" opacity=".9"/>
  </svg>`;
}

function buildPopup(base){
  const cvors=allCvor.filter(c=>c.base_id===base.id);
  return `<div style="font-family:Segoe UI,Arial,sans-serif;min-width:180px;background:#111827;color:#c8d6e5;padding:8px;border-radius:6px">
    <b style="color:#00aaff">${base.name}</b><br/>
    <small style="color:#4a5e72">${base.location||''}</small><br/>
    <small>Lat: ${base.lat} Lon: ${base.lon}</small>
    ${cvors.length?`<hr style="border-color:#1e2d45;margin:6px 0"/>${cvors.map(c=>`<div><span style="color:${STATUS_COLOR[c.status]||'#888'};font-size:.75rem">&#9679;</span> ${c.name} — ${c.frequency||'?'} MHz</div>`).join('')}`:''}
  </div>`;
}

function initMap(){
  map=L.map('map',{center:[-29,25],zoom:5,zoomControl:true});
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'© OSM'}).addTo(map);
  renderMapMarkers();
}

function renderMapMarkers(){
  markers.forEach(m=>m.remove());markers=[];
  const baseLegend=document.getElementById('base-legend');
  baseLegend.innerHTML='';
  allBases.forEach(base=>{
    const cvors=allCvor.filter(c=>c.base_id===base.id);
    let status='UNKNOWN';
    if(cvors.some(c=>c.status==='ONLINE'))status='ONLINE';
    else if(cvors.some(c=>c.status==='FAULT'))status='FAULT';
    else if(cvors.some(c=>c.status==='OFFLINE'))status='OFFLINE';
    else if(cvors.some(c=>c.status==='MAINTENANCE'))status='MAINTENANCE';
    if(!activeFilters.has(status))return;
    const color=STATUS_COLOR[status]||'#3a5070';
    const icon=L.divIcon({html:makePin(color),iconSize:[28,36],iconAnchor:[14,36],className:''});
    const m=L.marker([base.lat,base.lon],{icon}).addTo(map);
    m.bindPopup(buildPopup(base),{className:'',maxWidth:300});
    markers.push(m);
    baseLegend.innerHTML+=`<div class="legend-item"><div class="legend-dot" style="background:${color}"></div><span>${base.name}</span></div>`;
  });
}

function toggleFilter(status){
  if(activeFilters.has(status))activeFilters.delete(status);
  else activeFilters.add(status);
  if(map)renderMapMarkers();
}

// ── Sidebar filters ───────────────────────────────────────────────────────────
function renderSidebarFilters(){
  const el=document.getElementById('filter-list');
  el.innerHTML=allBases.map(b=>`<div class="filter-item" onclick="flyToBase(${b.id})"><div class="filter-dot" style="background:var(--accent)"></div><span>${b.name}</span></div>`).join('');
}

function flyToBase(id){
  const b=allBases.find(x=>x.id===id);if(!b)return;
  const mapBtn=document.querySelectorAll('nav button')[3];
  showTab('map',mapBtn);
  setTimeout(()=>{if(map)map.flyTo([b.lat,b.lon],10,{duration:1.5});},200);
}

// ── Network detect ────────────────────────────────────────────────────────────
async function detectNetwork(){
  try{const r=await api('/api/network/detect');notify('IP: '+r.ip_address);}
  catch{notify('Network detect failed (offline)');}
}

// ── Export ────────────────────────────────────────────────────────────────────
async function exportAll(){
  try{
    const r=await api('/api/export/all');
    const blob=new Blob([JSON.stringify(r,null,2)],{type:'application/json'});
    const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='mcs_export_all.json';a.click();
  }catch{
    const blob=new Blob([JSON.stringify({bases:allBases,cvor:allCvor},null,2)],{type:'application/json'});
    const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='mcs_export_all.json';a.click();
  }
}

async function exportBase(id){
  try{
    const r=await api('/api/export/base/'+id);
    const blob=new Blob([JSON.stringify(r,null,2)],{type:'application/json'});
    const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='mcs_base_'+id+'.json';a.click();
  }catch{
    const b=allBases.find(x=>x.id===id);
    const cvors=allCvor.filter(c=>c.base_id===id);
    const blob=new Blob([JSON.stringify({base:b,cvor:cvors},null,2)],{type:'application/json'});
    const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='mcs_base_'+id+'.json';a.click();
  }
}

// ── File import ───────────────────────────────────────────────────────────────
const dz=document.getElementById('drop-zone');
dz.addEventListener('dragover',e=>{e.preventDefault();dz.classList.add('drag');});
dz.addEventListener('dragleave',()=>dz.classList.remove('drag'));
dz.addEventListener('drop',e=>{e.preventDefault();dz.classList.remove('drag');handleFiles(e.dataTransfer.files);});

async function handleFiles(files){
  const results=document.getElementById('import-results');
  results.innerHTML='';
  for(const f of files){
    const text=await f.text();
    const preview=document.createElement('div');
    preview.innerHTML=`<h4 style="color:var(--accent);font-size:.8rem;margin-bottom:6px">${f.name}</h4><pre class="preview">${escHtml(text.slice(0,2000))}</pre>`;
    results.appendChild(preview);
    try{
      const fd=new FormData();fd.append('file',f);
      await fetch(API_URL+'/api/cvor/import_preview',{method:'POST',body:fd});
    }catch{}
  }
}

function escHtml(s){return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}

// ── Init ──────────────────────────────────────────────────────────────────────
loadAll();
</script>
</body>
</html>
"""

MODELS_PY = r"""
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Base(db.Model):
    __tablename__ = 'bases'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    location = db.Column(db.String(120))
    lat = db.Column(db.Float, nullable=False)
    lon = db.Column(db.Float, nullable=False)
    cvor_systems = db.relationship('CVORSystem', backref='base', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return dict(id=self.id, name=self.name, location=self.location, lat=self.lat, lon=self.lon)


class CVORSystem(db.Model):
    __tablename__ = 'cvor_systems'
    id = db.Column(db.Integer, primary_key=True)
    base_id = db.Column(db.Integer, db.ForeignKey('bases.id'), nullable=False)
    name = db.Column(db.String(80), nullable=False)
    ip_address = db.Column(db.String(45))
    port = db.Column(db.Integer, default=2101)
    frequency = db.Column(db.Float)
    power_w = db.Column(db.Integer)
    mode = db.Column(db.String(20), default='NORMAL')
    status = db.Column(db.String(20), default='UNKNOWN')
    ident = db.Column(db.String(10))
    last_seen = db.Column(db.String(30))
    settings = db.relationship('CVORSettings', backref='cvor', uselist=False, cascade='all, delete-orphan')
    shelter = db.relationship('ShelterLayout', backref='cvor', uselist=False, cascade='all, delete-orphan')
    alarms = db.relationship('AlarmLog', backref='cvor', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return dict(
            id=self.id, base_id=self.base_id, name=self.name,
            ip_address=self.ip_address, port=self.port,
            frequency=self.frequency, power_w=self.power_w,
            mode=self.mode, status=self.status, ident=self.ident,
            last_seen=self.last_seen,
        )


class CVORSettings(db.Model):
    __tablename__ = 'cvor_settings'
    id = db.Column(db.Integer, primary_key=True)
    cvor_id = db.Column(db.Integer, db.ForeignKey('cvor_systems.id'), nullable=False)
    carrier_power = db.Column(db.Float)
    vor_bearing = db.Column(db.Float)
    morse_ident = db.Column(db.String(10))
    audio_level = db.Column(db.Float)
    rf_mode = db.Column(db.String(20))
    extra_json = db.Column(db.Text)

    def to_dict(self):
        return dict(
            id=self.id, cvor_id=self.cvor_id,
            carrier_power=self.carrier_power, vor_bearing=self.vor_bearing,
            morse_ident=self.morse_ident, audio_level=self.audio_level,
            rf_mode=self.rf_mode, extra_json=self.extra_json,
        )


class ShelterLayout(db.Model):
    __tablename__ = 'shelter_layouts'
    id = db.Column(db.Integer, primary_key=True)
    cvor_id = db.Column(db.Integer, db.ForeignKey('cvor_systems.id'), nullable=False)
    layout_json = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return dict(id=self.id, cvor_id=self.cvor_id, layout_json=self.layout_json, updated_at=str(self.updated_at))


class AlarmLog(db.Model):
    __tablename__ = 'alarm_logs'
    id = db.Column(db.Integer, primary_key=True)
    cvor_id = db.Column(db.Integer, db.ForeignKey('cvor_systems.id'), nullable=False)
    timestamp = db.Column(db.String(30), default=lambda: datetime.utcnow().isoformat())
    alarm_code = db.Column(db.String(20))
    message = db.Column(db.String(200))
    severity = db.Column(db.String(20))
    acknowledged = db.Column(db.Boolean, default=False)

    def to_dict(self):
        return dict(
            id=self.id, cvor_id=self.cvor_id, timestamp=self.timestamp,
            alarm_code=self.alarm_code, message=self.message,
            severity=self.severity, acknowledged=self.acknowledged,
        )
"""

DATABASE_PY = r"""
from models import db, Base, CVORSystem


SAAF_BASES = [
    dict(name='AFB Waterkloof',      location='Pretoria',      lat=-25.830, lon=28.222),
    dict(name='Hoedspruit AFB',      location='Hoedspruit',    lat=-24.368, lon=31.049),
    dict(name='Langebaanweg AFB',    location='Langebaanweg',  lat=-32.970, lon=18.160),
    dict(name='Overberg Test Range', location='Bredasdorp',    lat=-34.554, lon=20.314),
    dict(name='Louis Trichardt AFB', location='Louis Trichardt',lat=-23.055, lon=29.924),
    dict(name='Ysterplaat AFB',      location='Cape Town',     lat=-33.882, lon=18.497),
    dict(name='Makhado AFB',         location='Makhado',       lat=-23.155, lon=29.698),
    dict(name='Port Elizabeth AFB',  location='Port Elizabeth',lat=-33.985, lon=25.617),
    dict(name='Durban AFB',          location='Durban',        lat=-29.970, lon=30.950),
    dict(name='Bloemfontein AFB',    location='Bloemfontein',  lat=-29.094, lon=26.302),
]


def seed_database():
    if Base.query.count() > 0:
        return
    for i, bd in enumerate(SAAF_BASES, start=1):
        base = Base(**bd)
        db.session.add(base)
        db.session.flush()
        cvor = CVORSystem(
            base_id=base.id,
            name=f'CVOR-{i:02d}',
            ip_address=f'192.168.{i}.100',
            port=2101,
            frequency=round(108.0 + i * 0.35, 2),
            power_w=50,
            mode='NORMAL',
            status='UNKNOWN',
            ident=f'V{i:02d}',
        )
        db.session.add(cvor)
    db.session.commit()
"""

NETWORK_DETECT_PY = r"""
import socket


def detect_network_info():
    result = {
        'ip_address': '127.0.0.1',
        'subnet_mask': '255.255.255.0',
        'gateway': None,
        'interfaces': [],
    }
    try:
        import netifaces
        gateways = netifaces.gateways()
        default_gw = gateways.get('default', {})
        if netifaces.AF_INET in default_gw:
            gw_ip, iface = default_gw[netifaces.AF_INET][:2]
            result['gateway'] = gw_ip
            addrs = netifaces.ifaddresses(iface).get(netifaces.AF_INET, [])
            if addrs:
                result['ip_address'] = addrs[0].get('addr', '127.0.0.1')
                result['subnet_mask'] = addrs[0].get('netmask', '255.255.255.0')
        result['interfaces'] = []
        for iface in netifaces.interfaces():
            addrs = netifaces.ifaddresses(iface).get(netifaces.AF_INET, [])
            for a in addrs:
                result['interfaces'].append({'interface': iface, 'ip': a.get('addr'), 'netmask': a.get('netmask')})
    except Exception:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            result['ip_address'] = s.getsockname()[0]
            s.close()
        except Exception:
            pass
    return result
"""

TCP_CLIENT_PY = r"""
import socket
import struct
import json

STX = 0x02
ETX = 0x03


def _frame(payload: 'dict | bytes') -> bytes:
    data = json.dumps(payload).encode() if isinstance(payload, dict) else payload
    length = struct.pack('>H', len(data))
    return bytes([STX]) + length + data + bytes([ETX])


def _unframe(raw: bytes) -> dict | None:
    if len(raw) < 4 or raw[0] != STX or raw[-1] != ETX:
        return None
    length = struct.unpack('>H', raw[1:3])[0]
    data = raw[3:3 + length]
    try:
        return json.loads(data)
    except Exception:
        return {'raw': data.decode(errors='replace')}


class ThalesTCPClient:
    def __init__(self, host: str, port: int, timeout: float = 5.0):
        self.host = host
        self.port = port
        self.timeout = timeout

    def send_command(self, command: str, params: dict | None = None) -> dict:
        payload = {'command': command, 'params': params or {}}
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        try:
            sock.connect((self.host, self.port))
            sock.sendall(_frame(payload))
            raw = b''
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                raw += chunk
                if raw[-1] == ETX:
                    break
            return _unframe(raw) or {'error': 'bad_frame'}
        except socket.timeout:
            return {'error': 'timeout'}
        except ConnectionRefusedError:
            return {'error': 'connection_refused'}
        except Exception as exc:
            return {'error': str(exc)}
        finally:
            sock.close()

    def ping(self) -> bool:
        r = self.send_command('PING')
        return r.get('result') == 'PONG' or r.get('status') == 'OK'
"""

FILE_IMPORT_PY = r"""
import configparser
import io
import re


def parse_ini(text: str) -> dict:
    cp = configparser.ConfigParser()
    cp.read_string(text)
    return {s: dict(cp.items(s)) for s in cp.sections()}


def parse_config_sys(text: str) -> dict:
    result = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#') or line.startswith(';'):
            continue
        if '=' in line:
            k, _, v = line.partition('=')
            result[k.strip()] = v.strip()
        elif line.upper().startswith('DEVICE') or line.upper().startswith('FILES'):
            result.setdefault('_directives', []).append(line)
    return result


def parse_lda(text: str) -> dict:
    records = []
    current = {}
    for line in text.splitlines():
        line = line.strip()
        if not line:
            if current:
                records.append(current)
                current = {}
            continue
        m = re.match(r'^(\w[\w\s]*?)\s*[:=]\s*(.*)$', line)
        if m:
            current[m.group(1).strip()] = m.group(2).strip()
        else:
            current.setdefault('_raw', []).append(line)
    if current:
        records.append(current)
    return {'records': records, 'count': len(records)}


def parse_file(filename: str, content: str) -> dict:
    fname = filename.lower()
    if fname.endswith('.ini'):
        return {'type': 'ini', 'data': parse_ini(content)}
    elif fname == 'config.sys' or fname.endswith('.sys'):
        return {'type': 'config.sys', 'data': parse_config_sys(content)}
    elif fname.endswith('.lda'):
        return {'type': 'lda', 'data': parse_lda(content)}
    else:
        return {'type': 'unknown', 'data': {'raw': content[:500]}}
"""

APP_PY = r"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, request, jsonify
from flask_cors import CORS

from models import db, Base, CVORSystem, CVORSettings, ShelterLayout, AlarmLog
from database import seed_database
from network_detect import detect_network_info
from tcp_client import ThalesTCPClient
from file_import import parse_file

DB_DIR = os.path.join(os.path.dirname(__file__), '..', 'database')
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, 'cvor_mcs.db')

app = Flask(__name__)
CORS(app)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.abspath(DB_PATH)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

with app.app_context():
    db.create_all()
    seed_database()


# ── Bases ──────────────────────────────────────────────────────────────────────

@app.route('/api/bases', methods=['GET'])
def get_bases():
    return jsonify([b.to_dict() for b in Base.query.all()])


@app.route('/api/bases', methods=['POST'])
def create_base():
    d = request.get_json(force=True)
    base = Base(name=d['name'], location=d.get('location', ''), lat=float(d['lat']), lon=float(d['lon']))
    db.session.add(base)
    db.session.commit()
    return jsonify(base.to_dict()), 201


@app.route('/api/bases/<int:bid>', methods=['PUT'])
def update_base(bid):
    base = Base.query.get_or_404(bid)
    d = request.get_json(force=True)
    base.name = d.get('name', base.name)
    base.location = d.get('location', base.location)
    base.lat = float(d.get('lat', base.lat))
    base.lon = float(d.get('lon', base.lon))
    db.session.commit()
    return jsonify(base.to_dict())


@app.route('/api/bases/<int:bid>', methods=['DELETE'])
def delete_base(bid):
    base = Base.query.get_or_404(bid)
    db.session.delete(base)
    db.session.commit()
    return jsonify({'deleted': bid})


@app.route('/api/bases/<int:bid>/split', methods=['POST'])
def split_base(bid):
    base = Base.query.get_or_404(bid)
    d = request.get_json(force=True)
    new_base = Base(name=d.get('name', base.name + ' (Split)'), location=base.location, lat=base.lat, lon=base.lon)
    db.session.add(new_base)
    db.session.commit()
    return jsonify(new_base.to_dict()), 201


# ── CVOR ───────────────────────────────────────────────────────────────────────

@app.route('/api/cvor', methods=['GET'])
def get_cvor():
    return jsonify([c.to_dict() for c in CVORSystem.query.all()])


@app.route('/api/cvor', methods=['POST'])
def create_cvor():
    d = request.get_json(force=True)
    c = CVORSystem(
        base_id=int(d['base_id']), name=d['name'],
        ip_address=d.get('ip_address'), port=int(d.get('port', 2101)),
        frequency=float(d.get('frequency', 0) or 0),
        power_w=int(d.get('power_w', 50) or 50),
        mode=d.get('mode', 'NORMAL'), status=d.get('status', 'UNKNOWN'),
        ident=d.get('ident', ''),
    )
    db.session.add(c)
    db.session.commit()
    return jsonify(c.to_dict()), 201


@app.route('/api/cvor/<int:cid>', methods=['PUT'])
def update_cvor(cid):
    c = CVORSystem.query.get_or_404(cid)
    d = request.get_json(force=True)
    for field in ('name', 'ip_address', 'mode', 'status', 'ident'):
        if field in d:
            setattr(c, field, d[field])
    if 'port' in d:
        c.port = int(d['port'])
    if 'frequency' in d:
        c.frequency = float(d['frequency'] or 0)
    if 'power_w' in d:
        c.power_w = int(d['power_w'] or 0)
    if 'base_id' in d:
        c.base_id = int(d['base_id'])
    db.session.commit()
    return jsonify(c.to_dict())


@app.route('/api/cvor/<int:cid>', methods=['DELETE'])
def delete_cvor(cid):
    c = CVORSystem.query.get_or_404(cid)
    db.session.delete(c)
    db.session.commit()
    return jsonify({'deleted': cid})


@app.route('/api/cvor/<int:cid>/ping', methods=['POST'])
def ping_cvor(cid):
    c = CVORSystem.query.get_or_404(cid)
    if not c.ip_address:
        return jsonify({'status': 'no_ip'})
    client = ThalesTCPClient(c.ip_address, c.port or 2101)
    ok = client.ping()
    status = 'ONLINE' if ok else 'OFFLINE'
    c.status = status
    from datetime import datetime
    c.last_seen = datetime.utcnow().isoformat() if ok else c.last_seen
    db.session.commit()
    return jsonify({'status': status, 'reachable': ok})


@app.route('/api/cvor/<int:cid>/status', methods=['GET'])
def cvor_status(cid):
    c = CVORSystem.query.get_or_404(cid)
    return jsonify({'id': cid, 'status': c.status, 'last_seen': c.last_seen})


@app.route('/api/cvor/<int:cid>/alarms', methods=['GET'])
def cvor_alarms(cid):
    CVORSystem.query.get_or_404(cid)
    alarms = AlarmLog.query.filter_by(cvor_id=cid).order_by(AlarmLog.id.desc()).limit(50).all()
    return jsonify({'alarms': [a.to_dict() for a in alarms]})


@app.route('/api/cvor/<int:cid>/command', methods=['POST'])
def cvor_command(cid):
    c = CVORSystem.query.get_or_404(cid)
    d = request.get_json(force=True)
    command = d.get('command', '')
    params = d.get('params', {})
    allowed = {'SET_FREQ', 'SET_POWER', 'SET_MODE', 'SET_IDENT', 'REBOOT', 'APPLY_CONFIG'}
    if command not in allowed:
        return jsonify({'error': 'unknown_command'}), 400
    if c.ip_address:
        client = ThalesTCPClient(c.ip_address, c.port or 2101, timeout=5)
        result = client.send_command(command, params)
    else:
        result = {'result': 'simulated', 'command': command}
    if command == 'SET_FREQ' and 'frequency' in params:
        c.frequency = float(params['frequency'])
        db.session.commit()
    elif command == 'SET_POWER' and 'power' in params:
        c.power_w = int(params['power'])
        db.session.commit()
    elif command == 'SET_MODE' and 'mode' in params:
        c.mode = params['mode']
        db.session.commit()
    elif command == 'SET_IDENT' and 'ident' in params:
        c.ident = params['ident']
        db.session.commit()
    elif command == 'APPLY_CONFIG':
        for k in ('frequency', 'power', 'mode', 'ident'):
            if k in params and params[k]:
                if k == 'frequency':
                    c.frequency = float(params[k])
                elif k == 'power':
                    c.power_w = int(params[k])
                else:
                    setattr(c, k if k != 'power' else 'power_w', params[k])
        db.session.commit()
    return jsonify(result)


@app.route('/api/cvor/<int:cid>/db_settings', methods=['GET', 'POST', 'PUT'])
def cvor_db_settings(cid):
    CVORSystem.query.get_or_404(cid)
    if request.method == 'GET':
        s = CVORSettings.query.filter_by(cvor_id=cid).first()
        return jsonify(s.to_dict() if s else {})
    d = request.get_json(force=True)
    s = CVORSettings.query.filter_by(cvor_id=cid).first()
    if not s:
        s = CVORSettings(cvor_id=cid)
        db.session.add(s)
    for f in ('carrier_power', 'vor_bearing', 'audio_level'):
        if f in d:
            setattr(s, f, float(d[f]) if d[f] not in (None, '') else None)
    for f in ('morse_ident', 'rf_mode', 'extra_json'):
        if f in d:
            setattr(s, f, d[f])
    db.session.commit()
    return jsonify(s.to_dict())


@app.route('/api/cvor/<int:cid>/shelter', methods=['GET', 'POST', 'PUT'])
def cvor_shelter(cid):
    CVORSystem.query.get_or_404(cid)
    if request.method == 'GET':
        sh = ShelterLayout.query.filter_by(cvor_id=cid).first()
        return jsonify(sh.to_dict() if sh else {})
    d = request.get_json(force=True)
    sh = ShelterLayout.query.filter_by(cvor_id=cid).first()
    if not sh:
        sh = ShelterLayout(cvor_id=cid)
        db.session.add(sh)
    sh.layout_json = d.get('layout_json', sh.layout_json)
    from datetime import datetime
    sh.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify(sh.to_dict())


@app.route('/api/cvor/<int:cid>/import', methods=['POST'])
def cvor_import(cid):
    CVORSystem.query.get_or_404(cid)
    f = request.files.get('file')
    if not f:
        return jsonify({'error': 'no_file'}), 400
    content = f.read().decode(errors='replace')
    result = parse_file(f.filename, content)
    return jsonify(result)


@app.route('/api/cvor/import_preview', methods=['POST'])
def cvor_import_preview():
    f = request.files.get('file')
    if not f:
        return jsonify({'error': 'no_file'}), 400
    content = f.read().decode(errors='replace')
    result = parse_file(f.filename, content)
    return jsonify(result)


# ── Export ─────────────────────────────────────────────────────────────────────

@app.route('/api/export/all', methods=['GET'])
def export_all():
    return jsonify({
        'bases': [b.to_dict() for b in Base.query.all()],
        'cvor': [c.to_dict() for c in CVORSystem.query.all()],
    })


@app.route('/api/export/base/<int:bid>', methods=['GET'])
def export_base(bid):
    base = Base.query.get_or_404(bid)
    return jsonify({
        'base': base.to_dict(),
        'cvor': [c.to_dict() for c in CVORSystem.query.filter_by(base_id=bid).all()],
    })


# ── Network ────────────────────────────────────────────────────────────────────

@app.route('/api/network/detect', methods=['GET'])
def network_detect():
    return jsonify(detect_network_info())


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8080, debug=False, use_reloader=False)
"""

# ── BOOTSTRAP ─────────────────────────────────────────────────────────────────

import sys
import os
import threading
import subprocess
import time
import argparse
import importlib
import pathlib
import webbrowser

BASE_DIR = pathlib.Path(__file__).parent.resolve()

# ── Dark Thales ATM theme constants ──────────────────────────────────────────
_DBG   = '#0a0e17'    # background
_DPNL  = '#111827'    # panel
_DACC  = '#00aaff'    # accent blue
_DACC2 = '#00ff99'    # accent green
_DTXT  = '#c8d6e5'    # text
_DDIM  = '#4a5e72'    # muted / dimmed
_DFS   = ('Courier New', 9)   # font small
_DFM   = ('Courier New', 9, 'bold')  # font medium bold

# ── tkinterweb Python 3.13 compatibility patch ───────────────────────────────
def _patch_tkinterweb():
    """Silently ignore configure() errors in tkinterweb subwidgets.
    Fixes crash in extensions.py _handle_node_style on Python 3.13.
    Known bug in tkinterweb < 3.24 with Python 3.10+."""
    try:
        import tkinterweb.subwidgets as _sw
        _patched = 0
        for _cls_name in ('Entry', 'Combobox', 'Label', 'Button', 'Text',
                          'Scrollbar', 'Spinbox', 'Scale', 'Checkbutton',
                          'Radiobutton', 'Listbox'):
            _cls = getattr(_sw, _cls_name, None)
            if _cls and hasattr(_cls, 'configure'):
                _orig = _cls.configure
                def _safe(self, _o=_orig, **kw):
                    try:
                        _o(self, **kw)
                    except Exception:
                        pass
                _cls.configure = _safe
                _patched += 1
        if _patched:
            print(f"[MCS] tkinterweb patched {_patched} widget classes for Python 3.13 compatibility.")
    except Exception as e:
        print(f"[MCS] tkinterweb patch skipped: {e}")


# ── tkinterweb version check ──────────────────────────────────────────────────
_TKINTERWEB_MIN = (3, 24)   # minimum recommended version

def check_tkinterweb_version() -> dict:
    """Check tkinterweb version. Returns dict with keys:
    installed, version (tuple), version_str, ok, needs_upgrade, error."""
    result = {"installed": False, "version": None, "version_str": None,
              "ok": False, "needs_upgrade": False, "error": None}
    try:
        import importlib.util as _ilu
        if not _ilu.find_spec("tkinterweb"):
            result["error"] = "not_installed"; return result
        import tkinterweb as _tw
        result["installed"] = True
        ver_str = getattr(_tw, "__version__", None) or getattr(_tw, "VERSION", None) or ""
        result["version_str"] = ver_str
        import re as _re
        m = _re.match(r"(\d+)[.\-](\d+)(?:[.\-](\d+))?", str(ver_str))
        if m:
            parts = tuple(int(x) for x in m.groups() if x is not None)
            result["version"] = parts
            result["ok"] = parts[:2] >= _TKINTERWEB_MIN
            result["needs_upgrade"] = not result["ok"]
        else:
            result["ok"] = True   # can't parse — assume OK
            result["error"] = f"unparseable_version:{ver_str}"
    except Exception as e:
        result["error"] = str(e)
    return result


def upgrade_tkinterweb(progress_cb=None) -> bool:
    """Run pip install --upgrade tkinterweb. Returns True on success."""
    if progress_cb:
        progress_cb("Running: pip install --upgrade tkinterweb…")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--upgrade", "tkinterweb"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        if progress_cb:
            progress_cb("✔ tkinterweb upgraded successfully.")
        return True
    except subprocess.CalledProcessError as e:
        if progress_cb:
            progress_cb(f"✗ Upgrade failed: {e}")
        return False


REQUIRED_PACKAGES = [
    'flask', 'flask-cors', 'flask-sqlalchemy',
    'netifaces', 'pillow', 'pystray', 'tkinterweb',
    'requests', 'psutil',
]


def install_deps(update_cb=None):
    """Auto-install missing pip packages (skips already-importable ones)."""
    import importlib.util
    # Map pip package name -> importable module name
    PKG_TO_MODULE = {
        'flask': 'flask', 'flask-cors': 'flask_cors', 'flask-sqlalchemy': 'flask_sqlalchemy',
        'netifaces': 'netifaces', 'pillow': 'PIL', 'pystray': 'pystray',
        'tkinterweb': 'tkinterweb', 'requests': 'requests', 'psutil': 'psutil',
    }
    failed = []
    for pkg in REQUIRED_PACKAGES:
        module_name = PKG_TO_MODULE.get(pkg, pkg.replace('-', '_'))
        if importlib.util.find_spec(module_name) is not None:
            continue  # already installed
        if update_cb:
            update_cb(f'Installing {pkg}…')
        try:
            subprocess.check_call(
                [sys.executable, '-m', 'pip', 'install', '--quiet', pkg],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError:
            failed.append(pkg)
    if failed:
        print(f'[WARNING] Could not install: {", ".join(failed)}')


def write_files(reset=False, update_cb=None):
    """Write all backend source files to disk."""
    backend_dir = BASE_DIR / 'backend'
    backend_dir.mkdir(exist_ok=True)
    (BASE_DIR / 'database').mkdir(exist_ok=True)

    # Create empty __init__.py so backend is importable
    init_file = backend_dir / '__init__.py'
    if not init_file.exists():
        init_file.write_text('')

    files = {
        BASE_DIR / 'MCS_CVOR_RMS.html': HTML_CONTENT,
        backend_dir / 'models.py': MODELS_PY,
        backend_dir / 'database.py': DATABASE_PY,
        backend_dir / 'network_detect.py': NETWORK_DETECT_PY,
        backend_dir / 'tcp_client.py': TCP_CLIENT_PY,
        backend_dir / 'file_import.py': FILE_IMPORT_PY,
        backend_dir / 'app.py': APP_PY,
    }

    for path, content in files.items():
        if update_cb:
            update_cb(f'Writing {path.name}…')
        if reset or not path.exists():
            path.write_text(content.lstrip(), encoding='utf-8')


def start_backend(update_cb=None):
    """Import and start the Flask app in a daemon thread."""
    if update_cb:
        update_cb('Starting backend…')

    backend_dir = str(BASE_DIR / 'backend')
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)

    def _run():
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location('app', BASE_DIR / 'backend' / 'app.py')
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            mod.app.run(host='127.0.0.1', port=8080, debug=False, use_reloader=False)
        except Exception as exc:
            print(f'[Backend error] {exc}')

    t = threading.Thread(target=_run, name='flask-backend', daemon=True)
    t.start()
    # Give Flask a moment to bind
    time.sleep(1.5)
    return t


# ── TKINTER UI ────────────────────────────────────────────────────────────────

def make_tray_image():
    """Create a simple tray icon using Pillow."""
    try:
        from PIL import Image, ImageDraw
        img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse([4, 4, 60, 60], fill=(0, 170, 255, 255))
        draw.text((18, 18), 'M', fill=(0, 0, 0, 255))
        return img
    except Exception:
        return None


def detect_engine():
    """Detect available browser/web engine."""
    try:
        import tkinterweb
        return 'tkinterweb'
    except ImportError:
        return 'fallback'


# ── tkinterweb upgrade warning dialog ────────────────────────────────────────
class TkinterwebWarningDialog:
    """
    Shown during splash if tkinterweb < 3.24 is detected.
    Offers: Upgrade Now | Continue Anyway | Open in Browser
    Returns: 'upgrade' | 'continue' | 'browser' | None
    """
    def __init__(self, version_str: str):
        import tkinter as tk
        self._result = None
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.overrideredirect(True)
        self.root.configure(bg=_DBG)
        W, H = 540, 360
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")
        self._ver = version_str
        self._build()

    def _build(self):
        import tkinter as tk
        # Orange warning border
        border = tk.Frame(self.root, bg="#fd7e14", padx=2, pady=2)
        border.pack(fill="both", expand=True)
        inner = tk.Frame(border, bg=_DBG)
        inner.pack(fill="both", expand=True)

        # Header
        hdr = tk.Frame(inner, bg=_DPNL); hdr.pack(fill="x")
        tk.Label(hdr, text="✈", font=("Courier New", 18),
                 bg=_DPNL, fg=_DACC).pack(side="left", padx=(12,6), pady=8)
        tbox = tk.Frame(hdr, bg=_DPNL); tbox.pack(side="left")
        tk.Label(tbox, text="MCS CVOR RMS  —  tkinterweb Warning",
                 font=("Courier New", 10, "bold"), bg=_DPNL, fg="#fd7e14").pack(anchor="w")
        tk.Label(tbox, text="Rendering engine compatibility check",
                 font=_DFS, bg=_DPNL, fg=_DDIM).pack(anchor="w")
        tk.Frame(inner, bg="#fd7e14", height=1).pack(fill="x")

        # Body
        body = tk.Frame(inner, bg=_DBG)
        body.pack(fill="both", expand=True, padx=18, pady=12)
        tk.Label(body, text="⚠", font=("Courier New", 30),
                 bg=_DBG, fg="#fd7e14").pack()
        tk.Label(body, text=f"tkinterweb  {self._ver}  is installed.",
                 font=("Courier New", 10, "bold"), bg=_DBG, fg="#fd7e14").pack(pady=(4,0))
        tk.Label(body,
                 text=f"Version 3.24+ is recommended for Python "
                      f"{sys.version_info.major}.{sys.version_info.minor}.",
                 font=_DFS, bg=_DBG, fg=_DTXT).pack()
        tk.Label(body,
                 text="Older versions may crash when rendering the UI.\n"
                      "A compatibility patch has been applied automatically,\n"
                      "but upgrading is strongly recommended.",
                 font=_DFS, bg=_DBG, fg=_DDIM, justify="center").pack(pady=(8,0))

        self._prog_var = tk.StringVar(value="")
        tk.Label(body, textvariable=self._prog_var,
                 font=_DFS, bg=_DBG, fg=_DACC2).pack(pady=4)

        # Buttons
        btn_row = tk.Frame(inner, bg=_DBG); btn_row.pack(pady=(0,14))
        self._upg_btn = tk.Button(
            btn_row, text="⬆  Upgrade to Latest", font=_DFM,
            bg=_DBG, fg=_DACC2, bd=1, relief="solid", cursor="hand2",
            padx=10, pady=6, activebackground=_DACC2, activeforeground="#000",
            command=self._do_upgrade)
        self._upg_btn.pack(side="left", padx=5)
        tk.Button(btn_row, text="▶  Continue Anyway", font=_DFM,
                  bg=_DBG, fg="#fd7e14", bd=1, relief="solid", cursor="hand2",
                  padx=10, pady=6, activebackground="#fd7e14", activeforeground="#000",
                  command=self._continue).pack(side="left", padx=5)
        tk.Button(btn_row, text="🌐  Open in Browser", font=_DFM,
                  bg=_DBG, fg=_DDIM, bd=1, relief="solid", cursor="hand2",
                  padx=10, pady=6, command=self._browser).pack(side="left", padx=5)

    def _do_upgrade(self):
        import threading
        self._upg_btn.config(state="disabled", text="Upgrading…")
        self._prog_var.set("Running pip upgrade…")
        def _run():
            ok = upgrade_tkinterweb(progress_cb=lambda m: self._prog_var.set(m))
            if ok:
                self._prog_var.set("✔ Done!  Restarting…")
                self.root.after(1200, self._finish_upgrade)
            else:
                self._prog_var.set("✗ Failed — continuing with patch.")
                self.root.after(1500, self._continue)
        threading.Thread(target=_run, daemon=True).start()

    def _finish_upgrade(self):
        self._result = "upgrade"; self.root.destroy()

    def _continue(self):
        self._result = "continue"; self.root.destroy()

    def _browser(self):
        self._result = "browser"; self.root.destroy()

    def show(self) -> str:
        self.root.deiconify(); self.root.mainloop(); return self._result


class SplashScreen:
    def __init__(self, root):
        import tkinter as tk
        self.top = tk.Toplevel(root)
        self.top.overrideredirect(True)
        w, h = 400, 220
        sw = self.top.winfo_screenwidth()
        sh = self.top.winfo_screenheight()
        self.top.geometry(f'{w}x{h}+{(sw-w)//2}+{(sh-h)//2}')
        self.top.configure(bg='#0a0e17')
        tk.Label(self.top, text='MCS CVOR RMS', font=('Segoe UI', 18, 'bold'),
                 fg='#00aaff', bg='#0a0e17').pack(pady=(30, 5))
        tk.Label(self.top, text='Thales ATM Management Console',
                 font=('Segoe UI', 9), fg='#4a5e72', bg='#0a0e17').pack()
        self.sv = tk.StringVar(value='Initialising…')
        tk.Label(self.top, textvariable=self.sv,
                 font=('Segoe UI', 9), fg='#00ff99', bg='#0a0e17').pack(pady=(20, 5))
        import tkinter.ttk as ttk
        self.prog = ttk.Progressbar(self.top, length=300, mode='indeterminate')
        self.prog.pack(pady=5)
        self.prog.start(15)
        self.top.update()

    def update(self, msg: str, val: int = None):
        self.sv.set(msg)
        if val is not None:
            try:
                self.prog["value"] = val
            except Exception:
                pass
        self.top.update()

    def close(self):
        self.prog.stop()
        self.top.destroy()


class NotificationBanner:
    def __init__(self, parent):
        import tkinter as tk
        self.frame = tk.Frame(parent, bg='#00aaff', height=0)
        self.label = tk.Label(self.frame, text='', bg='#00aaff', fg='#000',
                              font=('Segoe UI', 9))
        self.label.pack(side='left', padx=10)
        self._after = None

    def show(self, msg, duration=3000):
        self.label.config(text=msg)
        self.frame.config(height=28)
        self.frame.pack(fill='x', side='top')
        if self._after:
            self.frame.after_cancel(self._after)
        self._after = self.frame.after(duration, self.hide)

    def hide(self):
        self.frame.pack_forget()


class CustomTitleBar:
    def __init__(self, parent, title='MCS CVOR RMS', on_close=None, on_minimize=None):
        import tkinter as tk
        self.frame = tk.Frame(parent, bg='#111827', height=36)
        self.frame.pack(fill='x', side='top')
        self.frame.pack_propagate(False)

        tk.Label(self.frame, text='⬡  ' + title, bg='#111827', fg='#00aaff',
                 font=('Segoe UI', 10, 'bold')).pack(side='left', padx=10)

        btn_frame = tk.Frame(self.frame, bg='#111827')
        btn_frame.pack(side='right', padx=4)

        for txt, cmd, hover in [
            ('─', on_minimize or (lambda: None), '#1e2d45'),
            ('✕', on_close or (lambda: None), '#ff3b30'),
        ]:
            b = tk.Label(btn_frame, text=txt, bg='#111827', fg='#c8d6e5',
                         font=('Segoe UI', 11), width=3, cursor='hand2')
            b.pack(side='left')
            b.bind('<Button-1>', lambda e, c=cmd: c())
            b.bind('<Enter>', lambda e, w=b, h=hover: w.config(bg=h))
            b.bind('<Leave>', lambda e, w=b: w.config(bg='#111827'))

        # Drag support
        self._drag_x = self._drag_y = 0
        self.frame.bind('<Button-1>', self._start_drag)
        self.frame.bind('<B1-Motion>', self._on_drag)

    def _start_drag(self, e):
        self._drag_x = e.x_root
        self._drag_y = e.y_root

    def _on_drag(self, e):
        dx = e.x_root - self._drag_x
        dy = e.y_root - self._drag_y
        root = self.frame.winfo_toplevel()
        x = root.winfo_x() + dx
        y = root.winfo_y() + dy
        root.geometry(f'+{x}+{y}')
        self._drag_x = e.x_root
        self._drag_y = e.y_root


class StatusBar:
    def __init__(self, parent):
        import tkinter as tk
        self.frame = tk.Frame(parent, bg='#111827', height=22)
        self.frame.pack(fill='x', side='bottom')
        self.frame.pack_propagate(False)
        self.label = tk.Label(self.frame, text='Ready', bg='#111827', fg='#4a5e72',
                              font=('Segoe UI', 8), anchor='w')
        self.label.pack(side='left', padx=8)
        self.clock_label = tk.Label(self.frame, text='', bg='#111827', fg='#00ff99',
                                    font=('Courier', 8))
        self.clock_label.pack(side='right', padx=8)
        self._tick()

    def set(self, msg):
        self.label.config(text=msg)

    def _tick(self):
        import datetime
        t = datetime.datetime.utcnow().strftime('UTC %H:%M:%S')
        self.clock_label.config(text=t)
        self.frame.after(1000, self._tick)


class BrowserFrame:
    """Embeds the HTML app or shows fallback."""
    def __init__(self, parent, html_path: pathlib.Path, engine: str):
        import tkinter as tk
        self.frame = tk.Frame(parent, bg='#0a0e17')
        self.frame.pack(fill='both', expand=True)
        self.url = html_path.as_uri()
        self._w = None

        if engine == 'tkinterweb':
            self._tkinterweb()
        else:
            self._fallback(html_path)

    def _tkinterweb(self):
        try:
            from tkinterweb import HtmlFrame
            f = HtmlFrame(self.frame, horizontal_scrollbar="auto",
                          messages_enabled=False)
            f.pack(fill="both", expand=True)
            try:
                f.load_url(self.url)
            except Exception as load_err:
                print(f"[tkinterweb] load warning (non-fatal): {load_err}")
            self._w = f
            return   # explicit return — prevents fallthrough to _fallback
        except Exception as e:
            print(f"[tkinterweb] init failed: {e}")
            self._fallback()

    def _fallback(self, html_path: pathlib.Path = None):
        import tkinter as tk
        _hp = html_path or pathlib.Path(self.url.replace('file://', ''))
        tk.Label(self.frame, text='MCS CVOR RMS', font=('Segoe UI', 20, 'bold'),
                 fg='#00aaff', bg='#0a0e17').pack(pady=(60, 10))
        tk.Label(self.frame, text='tkinterweb is not available.\nOpen the app in your browser.',
                 fg='#4a5e72', bg='#0a0e17', font=('Segoe UI', 10)).pack(pady=5)
        tk.Button(
            self.frame, text='Open in Browser', font=('Segoe UI', 10, 'bold'),
            bg='#00aaff', fg='#000', relief='flat', padx=20, pady=8,
            command=lambda: webbrowser.open(self.url),
        ).pack(pady=10)
        tk.Button(
            self.frame, text='Open Backend (http://localhost:8080)',
            font=('Segoe UI', 9), bg='#111827', fg='#00ff99', relief='flat',
            command=lambda: webbrowser.open('http://localhost:8080'),
        ).pack(pady=2)


class TrayManager:
    def __init__(self, root, on_show, on_quit):
        self.root = root
        self.icon = None
        try:
            import pystray
            img = make_tray_image()
            if img is None:
                return

            menu = pystray.Menu(
                pystray.MenuItem('Show MCS', lambda: root.after(0, on_show)),
                pystray.MenuItem('Quit', lambda: root.after(0, on_quit)),
            )
            self.icon = pystray.Icon('MCS CVOR RMS', img, 'MCS CVOR RMS', menu)
            threading.Thread(target=self.icon.run, daemon=True).start()
        except Exception as exc:
            print(f'[Tray] {exc}')

    def stop(self):
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass


class MCSApp:
    def __init__(self, html_path: pathlib.Path, no_backend=False):
        import tkinter as tk
        self.html_path = html_path
        self.no_backend = no_backend

        self.root = tk.Tk()
        self.root.title('MCS CVOR RMS')
        self.root.overrideredirect(True)  # borderless
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        w, h = min(1400, sw - 40), min(860, sh - 60)
        self.root.geometry(f'{w}x{h}+{(sw-w)//2}+{(sh-h)//2}')
        self.root.configure(bg='#0a0e17')
        self.root.resizable(True, True)

        # Title bar
        CustomTitleBar(
            self.root,
            on_close=self._on_close,
            on_minimize=self._on_minimize,
        )

        # Notification banner
        self.banner = NotificationBanner(self.root)

        # Status bar
        self.status_bar = StatusBar(self.root)

        # Browser frame
        engine = detect_engine()
        BrowserFrame(self.root, html_path, engine)

        # Tray
        self.tray = TrayManager(self.root, self._on_show, self._on_close)

        self.root.protocol('WM_DELETE_WINDOW', self._on_close)

    def _on_close(self):
        self.tray.stop()
        self.root.destroy()

    def _on_minimize(self):
        self.banner.show('MCS minimised to tray')
        self.root.after(600, self.root.withdraw)

    def _on_show(self):
        self.root.deiconify()
        self.root.lift()

    def run(self):
        self.root.mainloop()


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='MCS CVOR RMS Launcher')
    parser.add_argument('--reset', action='store_true', help='Delete and rewrite all generated files')
    parser.add_argument('--browser-only', action='store_true', dest='browser_only', help='Open HTML in default browser, skip Tkinter')
    parser.add_argument('--no-backend', action='store_true', dest='no_backend', help='Skip starting Flask backend')
    args = parser.parse_args()

    # Need a minimal Tk root for splash
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()

    splash = SplashScreen(root)

    # tkinterweb version check — warn if < 3.24
    splash.update("Checking tkinterweb version…", 5)
    _tw_info = check_tkinterweb_version()
    if _tw_info["installed"] and _tw_info["needs_upgrade"]:
        ver = _tw_info["version_str"] or "unknown"
        print(f"[MCS] tkinterweb {ver} < 3.24 detected — showing upgrade dialog.")
        splash.close()
        root.withdraw()
        warn_result = TkinterwebWarningDialog(ver).show()
        if warn_result == "upgrade":
            print("[MCS] Restarting after tkinterweb upgrade…")
            os.execv(sys.executable, [sys.executable] + sys.argv)
            return
        elif warn_result == "browser":
            write_files(reset=args.reset)
            if not args.no_backend:
                start_backend()
            html_path = BASE_DIR / 'MCS_CVOR_RMS.html'
            webbrowser.open(html_path.as_uri())
            return
        # "continue" or window closed — recreate splash and proceed
        root.deiconify()
        splash = SplashScreen(root)
        splash.update("Continuing with compatibility patch…", 10)
    elif _tw_info["ok"] and _tw_info["installed"]:
        splash.update(f"tkinterweb {_tw_info['version_str']} ✔", 5)
    elif not _tw_info["installed"]:
        splash.update("tkinterweb not found — will install…", 5)
    # Apply compatibility patch regardless of version
    _patch_tkinterweb()

    # 1. Install deps
    splash.update('Installing dependencies…', 10)
    install_deps(update_cb=splash.update)

    # 2. Write files
    splash.update('Writing files…')
    write_files(reset=args.reset, update_cb=splash.update)

    # 3. Start backend
    if not args.no_backend:
        splash.update('Starting backend…')
        start_backend(update_cb=splash.update)

    html_path = BASE_DIR / 'MCS_CVOR_RMS.html'

    # 4. Launch UI
    splash.update('Launching UI…')
    splash.close()
    root.destroy()

    if args.browser_only:
        webbrowser.open(html_path.as_uri())
        return

    app = MCSApp(html_path=html_path, no_backend=args.no_backend)
    app.run()


if __name__ == '__main__':
    main()
