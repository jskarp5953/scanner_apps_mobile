# OP25 HTTP Control Server

Python HTTP server to manage OP25 systems: list systems from `op25_system.json`, start/stop associated shell scripts, track running PIDs, and provide a modern web UI with multi-user authentication.

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

## Multi-User Support

The server now supports multiple independent user accounts with separate passwords.

### Managing Users

**Via the Web UI (Recommended)**
1. Log in with any user account (default: admin / changeme).
2. Go to the **Settings** tab to:
   - **Change Password**: Update your own password (requires current password verification)
   - **Add User**: Create new user accounts (requires your current password)
   - **Existing Users**: View a list of all user accounts on the system
   - **Current User**: See who you are logged in as

**Edit `server_settings.json` directly**
1. Stop the server.
2. Edit the `users` dictionary:

```json
{
  "default": null,
  "users": {
    "admin": "secure-password",
    "operator": "another-password",
    "viewer": "third-password"
  }
}
```

3. Restart the server and log in with any user account.

**Backward Compatibility**
For existing deployments, the server still supports legacy `admin_user`/`admin_pass` format and environment variables (`ADMIN_USER`, `ADMIN_PASS`). Priority order:
1. Multi-user `users` dict in `server_settings.json` (new format)
2. Legacy `admin_user`/`admin_pass` in `server_settings.json`
3. Environment variables `ADMIN_USER`/`ADMIN_PASS`

## Features

### Web UI Tabs

- **Systems**: Grid of clickable buttons (3 columns) for each system. Click to start; the active system button turns red while running. Automatically stops the previous system before starting a new one (with user confirmation).

- **Power**: Control panel with:
  - **Stop**, **Kill**, **Restart**, **Reload** buttons for the active system.
  - **Current status** indicator showing the running system and its PID.
  - **Server Host Power** subsection with **Reboot Host** and **Shutdown Host** buttons (requires confirmation).

- **Settings**: Configure user and system settings:
  - **Current User**: displays the logged-in user.
  - **Default system**: select a system to auto-start when the server starts; saves to `server_settings.json`.
  - **Change Password**: update your own password (requires current password for verification).
  - **Add User**: create a new user account (requires your current password).
  - **Existing Users**: list all user accounts in the system.

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
  "users": {
    "admin": "secure-password-here",
    "operator": "operator-password"
  }
}
```

- **default**: system name to auto-start (null = no auto-start).
- **users**: dictionary mapping username → password. Each user can log in independently with their own password.

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
| GET | `/settings` | JSON object: `{default, users: [...], current_user}` (requires auth). |
| POST | `/start` | Start a system; body: `{"system_name":"..."}`. |
| POST | `/stop` | Gracefully stop the current system. |
| POST | `/kill` | Force-kill the current system. |
| POST | `/settings` | Update settings or manage users (requires auth); supported actions: |
| | | - `{"default":"system_name"}` - set default system |
| | | - `{"action":"change_password","current_password":"...","new_password":"..."}` - change user password |
| | | - `{"action":"add_user","new_user":"...","new_password":"..."}` - add new user |
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
- Check `server_settings.json` for correct username and password in the `users` dict.
- Verify user exists and password is correct: `curl -u username:password http://localhost:8081/settings`
- For legacy format, check `admin_user` and `admin_pass` fields.

**System script doesn't start:**
- Ensure `config_file` path in `op25_system.json` is correct and executable.
- Check file permissions: `chmod +x <script>`.

**Host reboot/shutdown returns error:**
- Verify sudoers configuration if running as non-root.
- Test with `HOST_ACTIONS_DRY_RUN=1` first to see the command that would run.
