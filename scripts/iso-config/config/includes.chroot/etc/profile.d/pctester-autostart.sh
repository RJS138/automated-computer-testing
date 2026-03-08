#!/bin/sh
# Auto-start PC Tester on tty1 login.
# On any other terminal (SSH, tty2, etc.) this is a no-op.
if [ "$(tty)" = "/dev/tty1" ] && [ -x /usr/local/bin/pctester ]; then
    clear
    /usr/local/bin/pctester
    echo ""
    echo "PC Tester exited. Type 'reboot' to restart or press Enter for a shell."
    read -r _
    exec bash
fi
