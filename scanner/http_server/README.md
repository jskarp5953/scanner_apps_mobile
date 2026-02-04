# OP25 HTTP Control Server

Simple Python HTTP server to list systems from `op25_system.json`, start the associated shell script, and track the running PID so it can be stopped when another system is selected.

Usage:

1. From the `scanner/http_server` directory run:

```bash
python3 server.py
```

2. Open a browser to `http://<host>:8081` to see the simple UI.

Notes:
- The server reads `op25_system.json` in the same directory. Ensure the `config_file` paths point to executable shell scripts on the host.
- Scripts are launched via `/bin/bash <script>` and run in their own process group; the server attempts to gracefully terminate the previous process group when starting a new system.
