Small, focused instructions for AI coding agents working with the Raspberry Pi helper apps in this folder.

Context & purpose
- This folder (`apps` for RPi) contains small utilities (e.g., `radioreference_import.py`, `scanning_menu.sh`) used to support `op25` deployments on Raspberry Pi devices.

What to know before editing
- These scripts are lightweight and target Raspbian/Ubuntu on RPis; prefer POSIX shell compatibility and minimal external dependencies.
- `radioreference_import.py` is a network-using script that depends on a premium Radioreference account for data — do not attempt automated scraping without credentials.
- UI automation (kiosk browser launch) is done via `scanning_menu.sh` and expects `chromium` on RPi with a touch screen.

Conventions and quick examples
- Keep CLI flags consistent with existing scripts (see `scanning_menu.sh`).
- Prefer small, testable changes; validate by running the script on RPi or in a Debian chroot.

If unclear, ask the human for:
- Target RPi OS/version and whether changes must remain compatible with offline setups.

Next steps: If you want, I can merge and harmonize this guidance into the top-level repo `copilot-instructions.md`.
