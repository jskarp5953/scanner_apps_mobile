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


def start_system(config_file, system_name):
    global _proc, _proc_info
    with _lock:
        if _proc is not None:
            stop_current()
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
            systems = read_systems()
            html = ['<html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>OP25 Systems</title></head><body>']
            html.append('<h2>Available Systems</h2>')
            # list
            html.append('<ul>')
            for s in systems:
                name = s.get('system_name')
                cfg = s.get('config_file')
                html.append(f"<li><b>{name}</b> - <small>{cfg}</small> <button onclick=\"start('{name}')\">Start</button></li>")
            html.append('</ul>')

            # default selector
            html.append('<h3>Default system (auto-start)</h3>')
            html.append('<select id="default_select"></select> <button onclick="saveDefault()">Save Default</button> <button onclick="startDefault()">Start Default</button>')

            html.append('<p><button onclick="stop()">Stop</button> <span id="status">(no process)</span></p>')
            html.append('''
<script>
function makeOption(name, selected){
  const opt = document.createElement('option');
  opt.value = name; opt.textContent = name;
  if(selected) opt.selected = true;
  return opt;
}
async function loadSettings(){
  const r = await fetch('/settings');
  const j = await r.json();
  const sel = document.getElementById('default_select');
  sel.innerHTML = '';
  // populate
  const systemsResp = await fetch('/systems');
  const systems = await systemsResp.json();
  systems.forEach(s=> sel.appendChild(makeOption(s.system_name, s.system_name === j.default)));
}
async function saveDefault(){
  const sel = document.getElementById('default_select');
  const value = sel.value || null;
  await fetch('/settings',{method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({default: value})});
  alert('Saved default: '+value);
}
async function startDefault(){
  const sel = document.getElementById('default_select');
  if(!sel.value){ alert('No default selected'); return }
  await fetch('/start', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({system_name: sel.value})});
  updateStatus();
}
async function start(name){
  const resp = await fetch('/start', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({system_name:name})});
  const j = await resp.json();
  updateStatus();
  alert(JSON.stringify(j));
}
async function stop(){ await fetch('/stop',{method:'POST'}); updateStatus(); }
async function updateStatus(){ const r=await fetch('/status'); const j=await r.json(); document.getElementById('status').innerText = j.running ? (j.system_name+' (pid '+j.pid+')') : '(no process)'; }
setInterval(updateStatus,3000);
updateStatus();
loadSettings();
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
