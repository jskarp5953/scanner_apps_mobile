# OP25 HTTP Control Server

Python HTTP server to manage OP25 systems: list systems from `op25_system.json`, start/stop associated shell scripts, track running PIDs, and provide a modern web UI with authentication.

## Quick Start

### Prerequisites
- Python 3.7+
- Systems defined in `op25_system.json` with valid shell script paths

### First Run

1. From the `scanner/http_server` directory, start the server:

```bash
python3 server.py
```

2. On first startup, the server creates `server_settings.json` if it doesn't exist, with placeholder admin credentials:
   - **Username**: `admin`
   - **Password**: `changeme`

3. Open a browser to `http://<host>:8081` and log in with the above credentials.

### Set Your Own Credentials

You have two options:

**Option A: Via the Web UI**
1. Log in with default credentials (admin / changeme).
2. Go to the **Settings** tab.
3. Update the admin username and password (not yet exposed in the UI; use Option B instead).

**Option B: Edit `server_settings.json` directly**
1. Stop the server.
2. Edit `server_settings.json` in the same directory:

```json
{
  "default": null,
  "admin_user": "your-username",
  "admin_pass": "your-password"
}
```

3. Restart the server and log in with your new credentials.

**Option C: Use environment variables (backward compatible)**
Set `ADMIN_USER` and `ADMIN_PASS` environment variables before starting:

```bash
export ADMIN_USER=myuser
export ADMIN_PASS=mypass
python3 server.py
```

Priority: `server_settings.json` credentials take precedence over environment variables.

## Features

### Web UI Tabs

- **Systems**: Grid of clickable buttons (3 columns) for each system. Click to start; the active system button turns red while running. Automatically stops the previous system before starting a new one (with user confirmation).

- **Power**: Control panel with:
  - **Stop**, **Kill**, **Restart**, **Reload** buttons for the active system.
  - **Current status** indicator showing the running system and its PID.
  - **Server Host Power** subsection with **Reboot Host** and **Shutdown Host** buttons (requires confirmation).

- **Settings**: Configure:
  - **Default system**: select a system to auto-start when the server starts; saves to `server_settings.json`.
  - **Start Default**: manually start the configured default system.

### Process Management

- Scripts are launched via `/bin/bash <script>` and run in their own process group (`preexec_fn=os.setsid`).
- When switching systems, the server:
  1. Gracefully terminates the previous process group with SIGTERM.
  2. Waits up to 5 seconds for shutdown.
  3. Force-kills with SIGKILL if needed.
  4. Hunts for lingering processes via `pgrep` and cleans them up before starting the new system.

### Modal Dialogs

- Confirm/Info overlays for dangerous operations (Kill, Restart, Reboot, Shutdown).
- Non-intrusive confirmation flow with Cancel/OK buttons.

### Auto-Start Default System

- If a default system is set in `server_settings.json`, the server automatically starts it on launch.
- Prints status to console for debugging.

## Configuration

### `server_settings.json`

Persisted settings file created on first run:

```json
{
  "default": "aurora_fire",
  "admin_user": "admin",
  "admin_pass": "changeme"
}
```

- **default**: system name to auto-start (null = no auto-start).
- **admin_user** / **admin_pass**: HTTP Basic Authentication credentials.

### `op25_system.json`

List of systems to manage. Example:

```json
{
  "systems": [
    { "system_name": "Aurora Fire", "config_file": "/path/to/aurora_fire.sh" },
    { "system_name": "Douglas", "config_file": "/path/to/douglas.sh" }
  ]
}
```

Ensure `config_file` paths are:
- Absolute or relative to the http_server directory.
- Executable shell scripts.

## Host Power Controls

By default, the server attempts to run `reboot` or `shutdown -h now`. Configuration depends on the server's user:

### If running as root:
No additional setup needed.

### If running as a non-root user (e.g., `pi`):
Configure passwordless sudo for reboot/shutdown. Edit sudoers with `visudo`:

```bash
# Allow user 'pi' to run reboot/shutdown without password
pi ALL=(ALL) NOPASSWD: /sbin/reboot, /sbin/shutdown
```

### Safe Testing:
Set the environment variable `HOST_ACTIONS_DRY_RUN=1` before starting the server. Power endpoints will return JSON responses but not execute host actions:

```bash
HOST_ACTIONS_DRY_RUN=1 python3 server.py
```

## API Endpoints

All endpoints (except `/systems` and `/status`) require HTTP Basic Authentication.

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/` | Serves the web UI (requires auth). |
| GET | `/systems` | JSON list of available systems. |
| GET | `/status` | JSON object: `{running, pid, system_name}`. |
| GET | `/settings` | JSON object: `{default, admin_user}` (requires auth). |
| POST | `/start` | Start a system; body: `{"system_name":"..."}`. |
| POST | `/stop` | Gracefully stop the current system. |
| POST | `/kill` | Force-kill the current system. |
| POST | `/settings` | Update settings; body: `{"default":"...", "admin_user":"...", "admin_pass":"..."}`. |
| POST | `/host/reboot` | Reboot the host (requires auth and confirmation in UI). |
| POST | `/host/shutdown` | Shutdown the host (requires auth and confirmation in UI). |

## Logging & Debugging

- Server prints startup messages to console (including default system auto-start status).
- HTTP requests are logged by Python's BaseHTTPServer.
- For process-related debugging, check for lingering processes with `pgrep -f <config_file>`.

## Troubleshooting

**Port already in use:**
```bash
lsof -iTCP:8081 -sTCP:LISTEN
kill -9 <PID>
```

**Auth fails:**
- Check `server_settings.json` for correct `admin_user` and `admin_pass`.
- Verify `curl` basic auth: `curl -u username:password http://localhost:8081/`

**System script doesn't start:**
- Ensure `config_file` path in `op25_system.json` is correct and executable.
- Check file permissions: `chmod +x <script>`.

**Host reboot/shutdown returns error:**
- Verify sudoers configuration if running as non-root.
- Test with `HOST_ACTIONS_DRY_RUN=1` first to see the command that would run.
