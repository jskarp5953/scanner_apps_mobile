# OP25 HTTP Control Server

Simple Python HTTP server to list systems from `op25_system.json`, start the associated shell script, and track the running PID so it can be stopped when another system is selected.

Usage:

1. From the `scanner/http_server` directory run:

```bash
python3 server.py
```

2. Open a browser to `http://<host>:8081` to see the modern UI.

Notes:
- The server reads `op25_system.json` in the same directory. Ensure the `config_file` paths point to executable shell scripts on the host.
- Scripts are launched via `/bin/bash <script>` and run in their own process group; the server attempts to gracefully terminate the previous process group when starting a new system.
- The web UI has two tabs:
  - **Systems**: clickable buttons for each system. Clicking a system starts its script; the active system button will turn red while running.
  - **Power**: control panel with **Stop**, **Kill**, **Restart**, **Reload** (reload systems list), and host-level **Reboot**/**Shutdown** buttons; **Current status** indicator is shown here. Be careful: Reboot/Shutdown affect the whole host.
- Use the **Settings** tab to set an auto-started default system; the selection is saved to `server_settings.json` in the same directory.

Host reboot/shutdown notes:
- By default the server will attempt to run `reboot`/`shutdown -h now`. If the server is not running as root, it will prefix commands with `sudo` and will therefore require passwordless sudo configuration to work unattended. Example sudoers entry (edit with `visudo`):

```
# allow user 'pi' to run reboot/shutdown without password
pi ALL=(ALL) NOPASSWD: /sbin/reboot, /sbin/shutdown
```

- For safe testing without actually rebooting, set the environment variable `HOST_ACTIONS_DRY_RUN=1` before starting the server; the endpoints return a JSON response but do not execute host actions.
