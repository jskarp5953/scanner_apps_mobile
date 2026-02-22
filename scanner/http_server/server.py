#!/usr/bin/env python3
import json
import os
import signal
import subprocess
import threading
import base64
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
        # Initialize with default structure on first run
        defaults = {'default': None, 'users': {'admin': 'changeme'}}
        try:
            with open(SETTINGS_PATH, 'w') as f:
                json.dump(defaults, f, indent=2)
            print(f"Created default {SETTINGS_PATH} with admin:changeme")
        except Exception as e:
            print(f"Warning: could not create settings file: {e}")
        return defaults
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
    current_user = None  # Track authenticated user
    
    def _set_json(self, code=200):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()

    def _set_html(self, code=200):
        self.send_response(code)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()

    def _unauthorized(self):
      self.send_response(401)
      self.send_header('WWW-Authenticate', 'Basic realm="OP25"')
      self.end_headers()

    def _check_auth(self):
      """Return True if request is authorized.

      Supports both new multi-user format (users dict) and legacy format
      (admin_user/admin_pass), falling back to environment vars.
      """
      s = read_settings() or {}
      auth = self.headers.get('Authorization')
      if not auth or not auth.startswith('Basic '):
        self._unauthorized()
        return False
      try:
        token = auth.split(' ', 1)[1]
        decoded = base64.b64decode(token).decode('utf-8')
        u, p = decoded.split(':', 1)
      except Exception:
        self._unauthorized()
        return False
      
      # Check against new multi-user format first
      users = s.get('users', {})
      if users and u in users and users[u] == p:
        self.current_user = u
        return True
      
      # Fall back to legacy format
      admin_user = s.get('admin_user') or os.environ.get('ADMIN_USER')
      admin_pass = s.get('admin_pass') or os.environ.get('ADMIN_PASS')
      if admin_user and admin_pass and u == admin_user and p == admin_pass:
        self.current_user = admin_user
        return True
      
      self._unauthorized()
      return False

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == '/':
          if not self._check_auth():
            return
          html = ['<html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>OP25 Control</title>']
          html.append('<style>body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial;max-width:900px;margin:24px auto;color:#222} .tabs{display:flex;gap:8px;margin-bottom:16px} .tabs button{padding:8px 14px;border:0;border-radius:6px;background:#eee;cursor:pointer} .tabs button.active{background:#3498db;color:#fff} .card{background:#fff;padding:16px;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,0.08)} .system-button{display:block;padding:10px 14px;border-radius:8px;border:1px solid #ddd;background:#f6f6f6;cursor:pointer;text-align:center;width:100%;transition:transform .08s ease,box-shadow .12s ease,opacity .12s ease} .system-button:active{transform:translateY(1px)} .system-button.active{background:#e74c3c;color:#fff;border-color:#e74c3c} .controls{display:flex;gap:8px;align-items:center;margin-top:8px} .muted{color:#666;font-size:0.9em} #status{font-weight:600} /* grid layout */ #systems-list{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;align-items:start} /* modal */ .modal-overlay{position:fixed;left:0;top:0;right:0;bottom:0;background:rgba(0,0,0,0.45);display:flex;align-items:center;justify-content:center;z-index:1000} .modal{background:#fff;padding:16px;border-radius:8px;max-width:420px;width:90%;box-shadow:0 6px 20px rgba(0,0,0,0.2)} .modal h4{margin:0 0 8px 0} .modal .muted{margin-bottom:12px} .modal .modal-controls{display:flex;gap:8px;justify-content:flex-end} .btn-danger{background:#e74c3c;color:#fff;border-color:#e74c3c} .btn-warning{background:#f39c12;color:#fff;border-color:#f39c12} /* larger power tab buttons */ #tab-content-power .controls button{padding:12px 18px;font-size:1.05rem;border-radius:10px;min-width:110px} /* disabled active system visuals */ .system-button:disabled{opacity:0.75;cursor:not-allowed;filter:grayscale(6%);} .system-button.active:disabled{box-shadow:0 0 0 4px rgba(231,76,60,0.08);outline:2px solid rgba(231,76,60,0.06);opacity:1}</style>')
          html.append('</head><body>')
          html.append('<h1>OP25 Control</h1>')
          html.append('<div class="tabs"><button id="tab-btn-systems" class="active" onclick="showTab(\'systems\')">Systems</button><button id="tab-btn-settings" onclick="showTab(\'settings\')">Settings</button><button id="tab-btn-power" onclick="showTab(\'power\')">Power</button></div>')
          html.append('<div id="tab-content-systems" class="tabcontent card"><div class="muted">Click a system to start it; the active system will turn <b>red</b>.</div><div style="margin-top:12px" id="systems-list">Loading systems…</div></div>')
          html.append('<div id="tab-content-power" class="tabcontent" style="display:none"><div class="card"><h3>OP25 Control Options</h3><div class="controls"><button onclick="stop()">Stop</button><button onclick="kill()">Kill</button><button onclick="restart()">Restart</button><button onclick="reloadSystems()">Reload</button></div><div style="margin-top:8px" class="muted">Current status: <span id="status">(no process)</span></div><p class="muted">Use <b>Kill</b> to forcefully terminate if Stop does not work.</p><hr/><h4>Server Host Power</h4><div class="controls"><button onclick="hostReboot()" style="background:#f39c12;color:#fff;border-color:#f39c12">Reboot Host</button><button onclick="hostShutdown()" style="background:#c0392b;color:#fff;border-color:#c0392b">Shutdown Host</button></div><p class="muted">Warning: Reboot/Shutdown will affect the host; ensure the server user can run these commands (see README).</p></div></div>')
          html.append('<div id="tab-content-settings" class="tabcontent" style="display:none"><div class="card"><h3>Settings</h3><hr/><h4>Current User</h4><div style="margin-bottom:16px"><p class="muted">Logged in as: <strong id="current_user_display">-</strong></p></div><hr/><h4>Default System</h4><div style="margin-bottom:16px"><label>Select system: <select id="default_select"></select></label> <button onclick="saveDefault()">Save Default</button> <button onclick="startDefault()">Start Default</button></div><p class="muted">Save the default system to auto-start with the server.</p><hr/><h4>Change Password</h4><div style="margin-bottom:16px"><input type="password" id="current_password" placeholder="Current password" style="padding:8px;border:1px solid #ccc;border-radius:4px;width:100%;max-width:300px;box-sizing:border-box;margin-bottom:8px"/><input type="password" id="new_password" placeholder="New password" style="padding:8px;border:1px solid #ccc;border-radius:4px;width:100%;max-width:300px;box-sizing:border-box;margin-bottom:8px"/><button onclick="changePassword()" style="margin-top:8px">Change Password</button></div><hr/><h4>Add User</h4><div style="margin-bottom:16px"><input type="text" id="new_user" placeholder="New username" style="padding:8px;border:1px solid #ccc;border-radius:4px;width:100%;max-width:300px;box-sizing:border-box;margin-bottom:8px"/><input type="password" id="new_user_pass" placeholder="Password" style="padding:8px;border:1px solid #ccc;border-radius:4px;width:100%;max-width:300px;box-sizing:border-box;margin-bottom:8px"/><button onclick="addUser()" style="margin-top:8px">Add User</button></div><h4>Existing Users</h4><div id="users_list" class="muted" style="margin-top:8px">Loading...</div></div></div>')
          html.append('<div id="confirm-overlay" class="modal-overlay" style="display:none"><div class="modal"><h4 id="confirm-title"></h4><div class="muted" id="confirm-msg"></div><div class="modal-controls"><button id="confirm-cancel">Cancel</button><button id="confirm-ok" style="background:#e74c3c;color:#fff;border-color:#e74c3c">Confirm</button></div></div></div>')
          html.append('<div id="info-overlay" class="modal-overlay" style="display:none"><div class="modal"><div class="muted" id="info-msg"></div><div class="modal-controls"><button id="info-ok">OK</button></div></div></div>')
          html.append('<script>function showTab(n){document.querySelectorAll(\'.tabcontent\').forEach(el=>el.style.display=\'none\');const c=document.getElementById(\'tab-content-\'+n);if(c)c.style.display=\'block\';document.querySelectorAll(\'.tabs button\').forEach(b=>b.classList.remove(\'active\'));const b=document.getElementById(\'tab-btn-\'+n);if(b)b.classList.add(\'active\');if(n===\'systems\'){if(typeof renderSystems===\'function\')renderSystems();if(typeof updateStatus===\'function\')updateStatus();}else if(n===\'power\'){if(typeof updateStatus===\'function\')updateStatus();}else if(n===\'settings\'){if(typeof renderSettings===\'function\')renderSettings();if(typeof updateStatus===\'function\')updateStatus();}}function showConfirm(t,m){return new Promise(r=>{const o=document.getElementById(\'confirm-overlay\');const tl=document.getElementById(\'confirm-title\');const msg=document.getElementById(\'confirm-msg\');const ok=document.getElementById(\'confirm-ok\');const c=document.getElementById(\'confirm-cancel\');const cl=()=>{o.style.display=\'none\';ok.onclick=null;c.onclick=null;};tl.innerText=t||\'Confirm\';msg.innerText=m||\'Are you sure?\';ok.onclick=()=>{cl();r(true);};c.onclick=()=>{cl();r(false);};o.style.display=\'flex\';})}function showInfo(m){return new Promise(r=>{const o=document.getElementById(\'info-overlay\');const ms=document.getElementById(\'info-msg\');const ok=document.getElementById(\'info-ok\');const cl=()=>{o.style.display=\'none\';ok.onclick=null;};ms.innerText=m||\'\';ok.onclick=()=>{cl();r(true);};o.style.display=\'flex\';})}async function fetchSystems(){const r=await fetch(\'/systems\');return await r.json();}async function renderSystems(){const l=document.getElementById(\'systems-list\');const s=await fetchSystems();l.innerHTML=\'\';s.forEach(sy=>{const btn=document.createElement(\'button\');btn.className=\'system-button\';btn.textContent=sy.system_name;btn.setAttribute(\'data-name\',sy.system_name);btn.onclick=async()=>{await start(sy.system_name);};l.appendChild(btn);});updateStatus();}async function renderSettings(){const sel=document.getElementById(\'default_select\');const sys=await fetch(\'/systems\').then(r=>r.json());const st=await(await fetch(\'/settings\')).json();document.getElementById(\'current_user_display\').innerText=st.current_user||\'-\';if(sel){sel.innerHTML=\'\';sys.forEach(s=>{const o=document.createElement(\'option\');o.value=s.system_name;o.textContent=s.system_name;if(st.default&&st.default===s.system_name)o.selected=true;sel.appendChild(o);});}const ulist=document.getElementById(\'users_list\');ulist.innerHTML=\'\';(st.users||[]).forEach(u=>{const div=document.createElement(\'div\');div.style=\'display:flex;justify-content:space-between;align-items:center;padding:6px 0;border-bottom:1px solid #eee\';const span=document.createElement(\'span\');span.textContent=u;if(u===st.current_user)span.textContent+=\' (you)\';div.appendChild(span);if(u!==st.current_user){const btn=document.createElement(\'button\');btn.textContent=\'Remove\';btn.onclick=()=>removeUser(u);btn.style=\'padding:4px 10px;font-size:0.85rem;background:#c0392b;color:#fff;border-color:#c0392b;border-radius:4px;cursor:pointer\';div.appendChild(btn);}ulist.appendChild(div);});}async function reloadSystems(){await renderSystems();}async function saveDefault(){const sel=document.getElementById(\'default_select\');if(!sel)return;const v=sel.value||null;const r=await fetch(\'/settings\',{method:\'POST\',headers:{\'Content-Type\':\'application/json\'},body:JSON.stringify({default:v})});const j=await r.json();if(r.ok)await showInfo(\'Saved default: \'+v);else await showInfo(\'Save failed: \'+(j.error||JSON.stringify(j)));}async function startDefault(){const sel=document.getElementById(\'default_select\');if(!sel)return await showInfo(\'No default selected\');await start(sel.value);}async function changePassword(){const cur=document.getElementById(\'current_password\').value;const nw=document.getElementById(\'new_password\').value;if(!cur||!nw){await showInfo(\'Please fill in both password fields\');return;}const r=await fetch(\'/settings\',{method:\'POST\',headers:{\'Content-Type\':\'application/json\'},body:JSON.stringify({action:\'change_password\',current_password:cur,new_password:nw})});if(!r.ok){const j=await r.json();await showInfo(\'Failed: \'+(j.error||JSON.stringify(j)));return;}await showInfo(\'Password changed successfully\');document.getElementById(\'current_password\').value=\'\';document.getElementById(\'new_password\').value=\'\';}async function addUser(){const u=document.getElementById(\'new_user\').value;const p=document.getElementById(\'new_user_pass\').value;if(!u||!p){await showInfo(\'Please fill in both username and password fields\');return;}const r=await fetch(\'/settings\',{method:\'POST\',headers:{\'Content-Type\':\'application/json\'},body:JSON.stringify({action:\'add_user\',new_user:u,new_password:p})});if(!r.ok){const j=await r.json();await showInfo(\'Failed: \'+(j.error||JSON.stringify(j)));return;}await showInfo(\'User added successfully\');document.getElementById(\'new_user\').value=\'\';document.getElementById(\'new_user_pass\').value=\'\';renderSettings();}async function removeUser(u){const pwd=prompt(\'Enter your password to confirm user removal:\');if(!pwd)return;const r=await fetch(\'/settings\',{method:\'POST\',headers:{\'Content-Type\':\'application/json\'},body:JSON.stringify({action:\'remove_user\',remove_user:u,current_password:pwd})});if(!r.ok){const j=await r.json();await showInfo(\'Failed: \'+(j.error||JSON.stringify(j)));return;}await showInfo(\'User removed successfully\');renderSettings();}async function start(n){const btn=document.querySelectorAll(\'.system-button\');btn.forEach(b=>{b.disabled=true});try{const st=await(await fetch(\'/status\')).json();if(st.running&&st.system_name&&st.system_name!==n){await showInfo(\'Stopping running system: \'+st.system_name);await fetch(\'/stop\',{method:\'POST\'});const d=Date.now()+5000;while(Date.now()<d){const now=await(await fetch(\'/status\')).json();if(!now.running)break;await new Promise(r=>setTimeout(r,200));}}}catch(e){}const resp=await fetch(\'/start\',{method:\'POST\',headers:{\'Content-Type\':\'application/json\'},body:JSON.stringify({system_name:n})});const j=await resp.json();updateStatus();btn.forEach(b=>b.disabled=false);if(!resp.ok)await showInfo(\'Start failed: \'+(j.error||JSON.stringify(j)));}async function stop(){const r=await fetch(\'/stop\',{method:\'POST\'});const j=await r.json();updateStatus();if(!r.ok)await showInfo(\'Stop failed\');}async function kill(){const ok=await showConfirm(\'Kill process\',\'Forcefully terminate the running process?\');if(!ok)return;const r=await fetch(\'/kill\',{method:\'POST\'});const j=await r.json();updateStatus();if(!r.ok)await showInfo(\'Kill failed: \'+(j.error||JSON.stringify(j)));else await showInfo(\'Kill succeeded\');}async function restart(){const st=await(await fetch(\'/status\')).json();if(!st.running){await showInfo(\'No running system to restart\');return}const ok=await showConfirm(\'Restart system\',\'Restart the running system now?\');if(!ok)return;const n=st.system_name;await stop();await start(n);}async function hostReboot(){const ok=await showConfirm(\'Reboot host\',\'Reboot the host now? This will reboot the machine.\');if(!ok)return;const r=await fetch(\'/host/reboot\',{method:\'POST\'});const j=await r.json();if(!r.ok)await showInfo(\'Reboot failed: \'+(j.error||JSON.stringify(j)));else await showInfo(\'Reboot initiated\');}async function hostShutdown(){const ok=await showConfirm(\'Shutdown host\',\'Shutdown the host now? This will power off the machine.\');if(!ok)return;const r=await fetch(\'/host/shutdown\',{method:\'POST\'});const j=await r.json();if(!r.ok)await showInfo(\'Shutdown failed: \'+(j.error||JSON.stringify(j)));else await showInfo(\'Shutdown initiated\');}async function updateStatus(){const r=await fetch(\'/status\');const j=await r.json();const s=document.getElementById(\'status\');if(j.running){s.innerText=j.system_name+\' (pid \'+j.pid+\')\';}else{s.innerText=\'(no process)\'}document.querySelectorAll(\'.system-button\').forEach(b=>{if(j.running&&b.dataset.name===j.system_name){b.classList.add(\'active\');b.disabled=true;}else{b.classList.remove(\'active\');b.disabled=false;}});}renderSystems();setInterval(updateStatus,3000);</script>')
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
          # restrict settings view to authenticated users
          if not self._check_auth():
            return
          s = read_settings()
          resp = {
            'default': s.get('default'),
            'users': list(s.get('users', {}).keys()),
            'current_user': self.current_user
          }
          self._set_json(200)
          self.wfile.write(json.dumps(resp).encode('utf-8'))
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
        # Require auth for state-changing operations
        if parsed.path.startswith('/start') or parsed.path.startswith('/stop') or parsed.path.startswith('/kill') or parsed.path.startswith('/host/') or parsed.path.startswith('/settings'):
          if not self._check_auth():
            return

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
                action = data.get('action')
                default = data.get('default')
                admin_user = data.get('admin_user')
                admin_pass = data.get('admin_pass')
                
                # Handle multi-user actions
                if action == 'change_password':
                    current_pwd = data.get('current_password')
                    new_pwd = data.get('new_password')
                    if not current_pwd or not new_pwd:
                        self._set_json(400)
                        self.wfile.write(json.dumps({'error': 'missing password fields'}).encode('utf-8'))
                        return
                    s = read_settings()
                    users = s.get('users', {})
                    if self.current_user not in users or users[self.current_user] != current_pwd:
                        self._set_json(403)
                        self.wfile.write(json.dumps({'error': 'current password incorrect'}).encode('utf-8'))
                        return
                    users[self.current_user] = new_pwd
                    s['users'] = users
                    write_settings(s)
                    self._set_json(200)
                    self.wfile.write(json.dumps({'ok': True}).encode('utf-8'))
                    return
                
                if action == 'add_user':
                    new_user = data.get('new_user')
                    new_password = data.get('new_password')
                    if not new_user or not new_password:
                        self._set_json(400)
                        self.wfile.write(json.dumps({'error': 'missing user/password fields'}).encode('utf-8'))
                        return
                    s = read_settings()
                    users = s.get('users', {})
                    if new_user in users:
                        self._set_json(400)
                        self.wfile.write(json.dumps({'error': 'user already exists'}).encode('utf-8'))
                        return
                    users[new_user] = new_password
                    s['users'] = users
                    write_settings(s)
                    self._set_json(200)
                    self.wfile.write(json.dumps({'ok': True}).encode('utf-8'))
                    return
                
                if action == 'remove_user':
                    remove_user = data.get('remove_user')
                    current_pwd = data.get('current_password')
                    if not remove_user or not current_pwd:
                        self._set_json(400)
                        self.wfile.write(json.dumps({'error': 'missing remove_user or password fields'}).encode('utf-8'))
                        return
                    # Cannot remove yourself
                    if remove_user == self.current_user:
                        self._set_json(403)
                        self.wfile.write(json.dumps({'error': 'cannot remove your own user account'}).encode('utf-8'))
                        return
                    s = read_settings()
                    users = s.get('users', {})
                    # Verify current password
                    if self.current_user not in users or users[self.current_user] != current_pwd:
                        self._set_json(403)
                        self.wfile.write(json.dumps({'error': 'current password incorrect'}).encode('utf-8'))
                        return
                    # Remove the user
                    if remove_user not in users:
                        self._set_json(400)
                        self.wfile.write(json.dumps({'error': 'user does not exist'}).encode('utf-8'))
                        return
                    del users[remove_user]
                    s['users'] = users
                    write_settings(s)
                    self._set_json(200)
                    self.wfile.write(json.dumps({'ok': True}).encode('utf-8'))
                    return
                
                systems = read_systems()
                if default and not any(s.get('system_name') == default for s in systems):
                    self._set_json(400)
                    self.wfile.write(json.dumps({'error': 'system not found'}).encode('utf-8'))
                    return
                # merge with existing settings so we don't wipe other keys
                s = read_settings() or {}
                if default is not None:
                    s['default'] = default
                if admin_user is not None:
                    s['admin_user'] = admin_user
                if admin_pass is not None:
                    s['admin_pass'] = admin_pass
                write_settings(s)
                # Do not echo admin_pass back in the response
                resp = {'saved': True, 'default': s.get('default'), 'admin_user': s.get('admin_user')}
                self._set_json(200)
                self.wfile.write(json.dumps(resp).encode('utf-8'))
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
