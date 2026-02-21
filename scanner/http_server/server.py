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

    def _unauthorized(self):
      self.send_response(401)
      self.send_header('WWW-Authenticate', 'Basic realm="OP25"')
      self.end_headers()

    def _check_auth(self):
      """Return True if request is authorized.

      Credentials are read from server_settings.json (admin_user/admin_pass)
      falling back to environment vars ADMIN_USER/ADMIN_PASS. If no
      credentials are configured, deny access to force operators to set
      an admin user and password.
      """
      s = read_settings() or {}
      user = s.get('admin_user') or os.environ.get('ADMIN_USER')
      pwd = s.get('admin_pass') or os.environ.get('ADMIN_PASS')
      if not user or not pwd:
        self._unauthorized()
        return False
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
      if u == user and p == pwd:
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
          self._set_json(200)
          self.wfile.write(json.dumps({'default': s.get('default'), 'admin_user': s.get('admin_user')}).encode('utf-8'))
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
                default = data.get('default')
                admin_user = data.get('admin_user')
                admin_pass = data.get('admin_pass')
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
