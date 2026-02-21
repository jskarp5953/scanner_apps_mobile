#!/usr/bin/env python3
import json
import os
import signal
import subprocess
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

HERE = os.path.dirname(__file__)
JSON_PATH = os.path.join(HERE, 'op25_system.json')
SETTINGS_PATH = os.path.join(HERE, 'server_settings.json')

_lock = threading.Lock()
_proc = None
_proc_info = None


def read_settings():
    if not os.path.exists(SETTINGS_PATH):
        return {}
    try:
        with open(SETTINGS_PATH, 'r') as f:
            return json.load(f)
    except Exception:
        return {}


def write_settings(d):
    with open(SETTINGS_PATH, 'w') as f:
        json.dump(d, f)



def read_systems():
    with open(JSON_PATH, 'r') as f:
        return json.load(f).get('systems', [])


def stop_current():
    global _proc, _proc_info
    with _lock:
        if _proc is None:
            return False
        try:
            os.killpg(os.getpgid(_proc.pid), signal.SIGTERM)
        except Exception:
            pass
        try:
            _proc.wait(timeout=5)
        except Exception:
            try:
                os.killpg(os.getpgid(_proc.pid), signal.SIGKILL)
            except Exception:
                pass
        _proc = None
        _proc_info = None
        return True


def force_kill_current():
    """Forcefully kill the current process group with SIGKILL."""
    global _proc, _proc_info
    with _lock:
        if _proc is None:
            return False
        try:
            os.killpg(os.getpgid(_proc.pid), signal.SIGKILL)
        except Exception:
            pass
        try:
            _proc.wait(timeout=5)
        except Exception:
            pass
        _proc = None
        _proc_info = None
        return True


def start_system(config_file, system_name):
    global _proc, _proc_info
    with _lock:
        # Stop any tracked process first
        if _proc is not None:
            stop_current()

        # Some config scripts spawn detached children; attempt to find
        # any lingering processes that reference the config file and
        # terminate them before starting a new instance.
        try:
            out = subprocess.check_output(['pgrep', '-f', config_file], text=True)
            pids = [int(x) for x in out.split() if x.strip()]
            for pid in pids:
                try:
                    if _proc and pid == _proc.pid:
                        # already handled by stop_current()
                        continue
                    os.killpg(os.getpgid(pid), signal.SIGTERM)
                except Exception:
                    pass
            # brief wait for processes to exit gracefully
            import time
            time.sleep(0.5)
            # force-kill remaining matches
            try:
                out2 = subprocess.check_output(['pgrep', '-f', config_file], text=True)
                pids2 = [int(x) for x in out2.split() if x.strip()]
                for pid in pids2:
                    try:
                        os.killpg(os.getpgid(pid), signal.SIGKILL)
                    except Exception:
                        pass
            except subprocess.CalledProcessError:
                # no remaining processes
                pass
        except subprocess.CalledProcessError:
            # pgrep found nothing
            pass

        p = subprocess.Popen(['/bin/bash', config_file], stdout=subprocess.PIPE, stderr=subprocess.PIPE, preexec_fn=os.setsid)
        _proc = p
        _proc_info = {'pid': p.pid, 'system_name': system_name}
        return _proc_info


class Handler(BaseHTTPRequestHandler):
    def _set_json(self, code=200):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()

    def _set_html(self, code=200):
        self.send_response(code)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == '/':
            html = ['<html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>OP25 Control</title>']
            html.append('<style>body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial;max-width:900px;margin:24px auto;color:#222} .tabs{display:flex;gap:8px;margin-bottom:16px} .tabs button{padding:8px 14px;border:0;border-radius:6px;background:#eee;cursor:pointer} .tabs button.active{background:#3498db;color:#fff} .card{background:#fff;padding:16px;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,0.08)} .system-button{display:block;padding:10px 14px;border-radius:8px;border:1px solid #ddd;background:#f6f6f6;cursor:pointer;text-align:center;width:100%;} .system-button.active{background:#e74c3c;color:#fff;border-color:#e74c3c} .controls{display:flex;gap:8px;align-items:center;margin-top:8px} .muted{color:#666;font-size:0.9em} #status{font-weight:600} /* grid layout */ #systems-list{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;align-items:start} /* modal */ .modal-overlay{position:fixed;left:0;top:0;right:0;bottom:0;background:rgba(0,0,0,0.45);display:flex;align-items:center;justify-content:center;z-index:1000} .modal{background:#fff;padding:16px;border-radius:8px;max-width:420px;width:90%;box-shadow:0 6px 20px rgba(0,0,0,0.2)} .modal h4{margin:0 0 8px 0} .modal .muted{margin-bottom:12px} .modal .modal-controls{display:flex;gap:8px;justify-content:flex-end} .btn-danger{background:#e74c3c;color:#fff;border-color:#e74c3c} .btn-warning{background:#f39c12;color:#fff;border-color:#f39c12} /* larger power tab buttons */ #tab-content-power .controls button{padding:12px 18px;font-size:1.05rem;border-radius:10px;min-width:110px}</style>')
            html.append('</head><body>')
            html.append('<h1>OP25 Control</h1>')
            html.append('<div class="tabs"><button id="tab-btn-systems" class="active" onclick="showTab(\'systems\')">Systems</button><button id="tab-btn-settings" onclick="showTab(\'settings\')">Settings</button><button id="tab-btn-power" onclick="showTab(\'power\')">Power</button></div>')
            html.append('<div id="tab-content-systems" class="tabcontent card">')
            html.append('<div class="muted">Click a system to start it; the active system will turn <b>red</b>.</div>')
            html.append('<div style="margin-top:12px" id="systems-list">Loading systems…</div>')
            # default selector moved to Settings tab
            # controls intentionally kept minimal on Systems tab; use Power tab for status/reload controls
            html.append('</div>')

            html.append('<div id="tab-content-power" class="tabcontent" style="display:none">')
            html.append('<div class="card"><h3>OP25 Control Options</h3><div class="controls"><button onclick="stop()">Stop</button><button onclick="kill()">Kill</button><button onclick="restart()">Restart</button><button onclick="reloadSystems()">Reload</button></div><div style="margin-top:8px" class="muted">Current status: <span id="status">(no process)</span></div><p class="muted">Use <b>Kill</b> to forcefully terminate if Stop does not work.</p><hr/><h4>Server Host Power</h4><div class="controls"><button onclick="hostReboot()" style="background:#f39c12;color:#fff;border-color:#f39c12">Reboot Host</button><button onclick="hostShutdown()" style="background:#c0392b;color:#fff;border-color:#c0392b">Shutdown Host</button></div><p class="muted">Warning: Reboot/Shutdown will affect the host; ensure the server user can run these commands (see README).</p></div>' )
            html.append('</div>')

            html.append('<div id="tab-content-settings" class="tabcontent" style="display:none"><div class="card"><h3>Settings</h3><div><label>Default system: <select id="default_select"></select></label> <button onclick="saveDefault()">Save Default</button> <button onclick="startDefault()">Start Default</button></div><p class="muted">Save the default system to auto-start with the server.</p></div></div>')

            html.append('''
<!-- confirm modal -->
<div id="confirm-overlay" class="modal-overlay" style="display:none">
  <div class="modal">
    <h4 id="confirm-title"></h4>
    <div class="muted" id="confirm-msg"></div>
    <div class="modal-controls">
      <button id="confirm-cancel">Cancel</button>
      <button id="confirm-ok" style="background:#e74c3c;color:#fff;border-color:#e74c3c">Confirm</button>
    </div>
  </div>
</div>

<!-- info modal -->
<div id="info-overlay" class="modal-overlay" style="display:none">
  <div class="modal">
    <div class="muted" id="info-msg"></div>
    <div class="modal-controls">
      <button id="info-ok">OK</button>
    </div>
  </div>
</div>

<script>
function showTab(name){
  // hide all tab contents
  document.querySelectorAll('.tabcontent').forEach(el=>el.style.display='none');
  // show the requested content
  const content = document.getElementById('tab-content-'+name);
  if(content) content.style.display='block';
  // update active tab button
  document.querySelectorAll('.tabs button').forEach(b=>b.classList.remove('active'));
  const btn = document.getElementById('tab-btn-'+name);
  if(btn) btn.classList.add('active');
  // refresh relevant data when switching
  if(name === 'systems'){
    if(typeof renderSystems === 'function') renderSystems();
    if(typeof updateStatus === 'function') updateStatus();
  } else if(name === 'power'){
    if(typeof updateStatus === 'function') updateStatus();
  } else if(name === 'settings'){
    if(typeof renderSettings === 'function') renderSettings();
    if(typeof updateStatus === 'function') updateStatus();
  }
}

function showConfirm(title,msg){
  return new Promise(resolve=>{
    const ov = document.getElementById('confirm-overlay');
    const t = document.getElementById('confirm-title');
    const m = document.getElementById('confirm-msg');
    const ok = document.getElementById('confirm-ok');
    const cancel = document.getElementById('confirm-cancel');
    const cleanup = ()=>{ ov.style.display='none'; ok.onclick = null; cancel.onclick = null; };
    t.innerText = title||'Confirm';
    m.innerText = msg||'Are you sure?';
    ok.onclick = ()=>{ cleanup(); resolve(true); };
    cancel.onclick = ()=>{ cleanup(); resolve(false); };
    ov.style.display = 'flex';
  });
}

function showInfo(msg){
  return new Promise(resolve=>{
    const ov = document.getElementById('info-overlay');
    const m = document.getElementById('info-msg');
    const ok = document.getElementById('info-ok');
    const cleanup = ()=>{ ov.style.display='none'; ok.onclick = null; };
    m.innerText = msg||'';
    ok.onclick = ()=>{ cleanup(); resolve(true); };
    ov.style.display = 'flex';
  });
}

async function fetchSystems(){
  const r = await fetch('/systems');
  return await r.json();
}

async function renderSystems(){
  const list = document.getElementById('systems-list');
  const systems = await fetchSystems();
  list.innerHTML = '';
  systems.forEach(s=>{
    const btn = document.createElement('button');
    btn.className = 'system-button';
    btn.textContent = s.system_name;
    btn.setAttribute('data-name', s.system_name);
    btn.onclick = async ()=>{ await start(s.system_name); };
    list.appendChild(btn);
  });
  updateStatus();
}

async function renderSettings(){
  const sel = document.getElementById('default_select');
  const systems = await fetch('/systems').then(r=>r.json());
  if(sel){
    sel.innerHTML = '';
    const settings = await (await fetch('/settings')).json();
    systems.forEach(s=>{
      const opt = document.createElement('option');
      opt.value = s.system_name; opt.textContent = s.system_name;
      if(settings.default && settings.default === s.system_name) opt.selected = true;
      sel.appendChild(opt);
    });
  }
}

async function reloadSystems(){ await renderSystems(); }

async function saveDefault(){
  const sel = document.getElementById('default_select');
  if(!sel) return;
  const value = sel.value || null;
  const r = await fetch('/settings', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({default: value})});
  const j = await r.json();
  if(r.ok) await showInfo('Saved default: '+value);
  else await showInfo('Save failed: '+ (j.error || JSON.stringify(j)));
}

async function startDefault(){
  const sel = document.getElementById('default_select');
  if(!sel) return await showInfo('No default selected');
  await start(sel.value);
}

async function start(name){
  const buttons = document.querySelectorAll('.system-button');
  // disable all buttons while we perform the stop/start sequence
  buttons.forEach(b=>{ b.disabled=true });

  // If a different system is running, stop it first and wait for shutdown
  try{
    const st = await (await fetch('/status')).json();
    if(st.running && st.system_name && st.system_name !== name){
      await showInfo('Stopping running system: '+st.system_name);
      await fetch('/stop', {method:'POST'});
      // wait up to 5s for process to stop
      const deadline = Date.now() + 5000;
      while(Date.now() < deadline){
        const now = await (await fetch('/status')).json();
        if(!now.running) break;
        await new Promise(r=>setTimeout(r, 200));
      }
    }
  }catch(e){
    // ignore status errors and proceed to start
  }

  const resp = await fetch('/start', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({system_name:name})});
  const j = await resp.json();
  updateStatus();
  buttons.forEach(b=>b.disabled=false);
  if(!resp.ok) await showInfo('Start failed: '+ (j.error || JSON.stringify(j)));
}

async function stop(){
  const r = await fetch('/stop', {method:'POST'}); const j = await r.json(); updateStatus(); if(!r.ok) await showInfo('Stop failed')
}

async function kill(){
  const ok = await showConfirm('Kill process','Forcefully terminate the running process?');
  if(!ok) return;
  const r = await fetch('/kill', {method:'POST'}); const j = await r.json(); updateStatus(); if(!r.ok) await showInfo('Kill failed: '+ (j.error || JSON.stringify(j))); else await showInfo('Kill succeeded');
}

async function restart(){
  const st = await (await fetch('/status')).json();
  if(!st.running){ await showInfo('No running system to restart'); return }
  const ok = await showConfirm('Restart system','Restart the running system now?');
  if(!ok) return;
  const name = st.system_name; await stop(); await start(name);
}

async function hostReboot(){
  const ok = await showConfirm('Reboot host','Reboot the host now? This will reboot the machine.');
  if(!ok) return;
  const r = await fetch('/host/reboot', {method:'POST'});
  const j = await r.json();
  if(!r.ok) await showInfo('Reboot failed: '+(j.error||JSON.stringify(j))); else await showInfo('Reboot initiated');
}

async function hostShutdown(){
  const ok = await showConfirm('Shutdown host','Shutdown the host now? This will power off the machine.');
  if(!ok) return;
  const r = await fetch('/host/shutdown', {method:'POST'});
  const j = await r.json();
  if(!r.ok) await showInfo('Shutdown failed: '+(j.error||JSON.stringify(j))); else await showInfo('Shutdown initiated');
}

async function updateStatus(){
  const r = await fetch('/status');
  const j = await r.json();
    const statusEl = document.getElementById('status');
    if(j.running){ statusEl.innerText = j.system_name+' (pid '+j.pid+')' }
    else { statusEl.innerText = '(no process)' }
  document.querySelectorAll('.system-button').forEach(b=>{
    if(j.running && b.dataset.name===j.system_name){
      b.classList.add('active');
      b.disabled = true;
    } else {
      b.classList.remove('active');
      b.disabled = false;
    }
  });
}

// initial render
renderSystems();
setInterval(updateStatus,3000);
</script>
''')
            html.append('</body></html>')
            self._set_html()
            self.wfile.write('\n'.join(html).encode('utf-8'))
            return
        elif parsed.path == '/status':
            with _lock:
                if _proc is None:
                    self._set_json(200)
                    self.wfile.write(json.dumps({'running': False}).encode('utf-8'))
                else:
                    self._set_json(200)
                    self.wfile.write(json.dumps({'running': True, 'pid': _proc.pid, 'system_name': _proc_info.get('system_name')}).encode('utf-8'))
                return
        elif parsed.path == '/settings':
            s = read_settings()
            self._set_json(200)
            self.wfile.write(json.dumps({'default': s.get('default')}).encode('utf-8'))
            return
        elif parsed.path == '/systems':
            # return the raw systems list for client-side UI
            systems = read_systems()
            self._set_json(200)
            self.wfile.write(json.dumps(systems).encode('utf-8'))
            return
        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length) if length else b''
        if parsed.path == '/start':
            try:
                data = json.loads(body.decode('utf-8'))
                want_name = data.get('system_name')
                systems = read_systems()
                found = next((s for s in systems if s.get('system_name') == want_name), None)
                if not found:
                    self._set_json(400)
                    self.wfile.write(json.dumps({'error': 'system not found'}).encode('utf-8'))
                    return
                cfg = found.get('config_file')
                if not os.path.exists(cfg):
                    self._set_json(500)
                    self.wfile.write(json.dumps({'error': 'config file not found', 'path': cfg}).encode('utf-8'))
                    return
                info = start_system(cfg, want_name)
                self._set_json(200)
                self.wfile.write(json.dumps({'started': True, 'pid': info['pid'], 'system_name': info['system_name']}).encode('utf-8'))
            except Exception as e:
                self._set_json(500)
                self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))
            return
        elif parsed.path == '/stop':
            ok = stop_current()
            self._set_json(200)
            self.wfile.write(json.dumps({'stopped': ok}).encode('utf-8'))
            return
        elif parsed.path == '/kill':
            ok = force_kill_current()
            self._set_json(200)
            self.wfile.write(json.dumps({'killed': ok}).encode('utf-8'))
            return
        elif parsed.path == '/host/reboot':
            try:
                # attempt to stop current process cleanly
                stop_current()
                dry = os.environ.get('HOST_ACTIONS_DRY_RUN') == '1'
                cmd = ['reboot'] if os.geteuid() == 0 else ['sudo', 'reboot']
                if dry:
                    self._set_json(200)
                    self.wfile.write(json.dumps({'reboot': True, 'dry_run': True, 'cmd': cmd}).encode('utf-8'))
                else:
                    subprocess.Popen(cmd)
                    self._set_json(200)
                    self.wfile.write(json.dumps({'reboot': True}).encode('utf-8'))
            except Exception as e:
                self._set_json(500)
                self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))
            return
        elif parsed.path == '/host/shutdown':
            try:
                stop_current()
                dry = os.environ.get('HOST_ACTIONS_DRY_RUN') == '1'
                cmd = ['shutdown', '-h', 'now'] if os.geteuid() == 0 else ['sudo', 'shutdown', '-h', 'now']
                if dry:
                    self._set_json(200)
                    self.wfile.write(json.dumps({'shutdown': True, 'dry_run': True, 'cmd': cmd}).encode('utf-8'))
                else:
                    subprocess.Popen(cmd)
                    self._set_json(200)
                    self.wfile.write(json.dumps({'shutdown': True}).encode('utf-8'))
            except Exception as e:
                self._set_json(500)
                self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))
            return
        elif parsed.path == '/settings':
            try:
                data = json.loads(body.decode('utf-8')) if body else {}
                default = data.get('default')
                systems = read_systems()
                if default and not any(s.get('system_name') == default for s in systems):
                    self._set_json(400)
                    self.wfile.write(json.dumps({'error': 'system not found'}).encode('utf-8'))
                    return
                write_settings({'default': default})
                self._set_json(200)
                self.wfile.write(json.dumps({'saved': True, 'default': default}).encode('utf-8'))
            except Exception as e:
                self._set_json(500)
                self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))
            return
        else:
            self.send_error(404)


def run(port=8081):
    server = HTTPServer(('0.0.0.0', port), Handler)
    print(f"Starting server on port {port}")
    # auto-start default if configured
    s = read_settings()
    default = s.get('default')
    if default:
        systems = read_systems()
        found = next((x for x in systems if x.get('system_name') == default), None)
        if found and os.path.exists(found.get('config_file')):
            print(f"Auto-starting default system: {default}")
            start_system(found.get('config_file'), default)
        else:
            print(f"Default system '{default}' not found or config missing.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('Shutting down')
        stop_current()
        server.server_close()


if __name__ == '__main__':
    run()
