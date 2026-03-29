#!/bin/sh
# Auto-start Touchstone on tty1 via X11.
# On any other terminal (SSH, tty2, etc.) this is a no-op.
if [ "$(tty)" = "/dev/tty1" ] && [ -z "${DISPLAY:-}" ]; then
    clear
    xinit /usr/local/bin/touchstone-session -- :0 vt1
    echo ""
    echo "Touchstone exited. Type 'reboot' to restart or press Enter for a shell."
    read -r _
    exec bash
fi
