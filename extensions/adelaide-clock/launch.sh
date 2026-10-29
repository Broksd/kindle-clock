#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-only
APP=/mnt/us/extensions/adelaide-clock
PY=/mnt/us/python3/bin/python3.9
PIDFILE=/tmp/adelaide-clock-launch.pid
FB_SAVE=/tmp/adelaide-clock-fb.dump
if [ -f "$PIDFILE" ]; then
    oldpid=$(cat "$PIDFILE")
    case "$oldpid" in ''|*[!0-9]*) ;; *) kill -0 "$oldpid" 2>/dev/null && exit 0 ;; esac
fi
echo "$$" > "$PIDFILE"
exec >> "$APP/launcher.log" 2>&1
snapshot() {
    echo "STATE $1 $(date '+%Y-%m-%dT%H:%M:%S%z')"
    printf 'boot_id='; cat /proc/sys/kernel/random/boot_id
    printf 'uptime='; cat /proc/uptime
    initctl status framework
    initctl status lab126_gui
}
old_screensaver=$(lipc-get-prop com.lab126.powerd preventScreenSaver 2>/dev/null)
case "$old_screensaver" in 0|1) ;; *) old_screensaver=0 ;; esac
child=''
paused_pids=''
pillow_disabled=0
fb_saved=0
cleanup() {
    result=$?
    trap - EXIT INT TERM HUP
    if [ -n "$child" ]; then
        kill "$child" 2>/dev/null
        wait "$child" 2>/dev/null
    fi
    # Match KOReader's default Kindle exit path: resume the existing desktop.
    for pid in $paused_pids; do
        [ "$(cat "/proc/$pid/comm" 2>/dev/null)" = awesome ] && kill -CONT "$pid"
    done
    [ "$fb_saved" = 1 ] && cat "$FB_SAVE" > /dev/fb0
    rm -f "$FB_SAVE"
    if [ "$pillow_disabled" = 1 ]; then
        lipc-set-prop com.lab126.pillow disableEnablePillow enable
        lipc-set-prop com.lab126.appmgrd start app://com.lab126.booklet.home
    fi
    lipc-set-prop com.lab126.powerd preventScreenSaver "$old_screensaver"
    echo "CLOCK_EXIT_STATUS=$result"
    snapshot exit
    rm -f "$PIDFILE"
}
trap cleanup EXIT
trap 'exit 0' INT TERM HUP
snapshot start
[ -x "$PY" ] || exit 1
# PW2 on 5.12.2.2: preserve framework and lab126_gui, pause only the WM.
wm_pids=$(pidof awesome)
[ -n "$wm_pids" ] || { echo 'No window manager found; leaving desktop alone'; exit 1; }
cat /dev/fb0 > "$FB_SAVE" || exit 1
fb_saved=1
lipc-set-prop com.lab126.powerd preventScreenSaver 1 || exit 1
# Mark before disabling, so even an interrupted call will be recovered.
pillow_disabled=1
lipc-set-prop com.lab126.pillow disableEnablePillow disable || exit 1
for pid in $wm_pids; do
    [ "$(cat "/proc/$pid/comm" 2>/dev/null)" = awesome ] || exit 1
    paused_pids="$paused_pids $pid"
    kill -STOP "$pid" || exit 1
done
PYTHONHOME=/mnt/us/python3 LD_LIBRARY_PATH=/mnt/us/python3/lib "$PY" -u "$APP/clock.py" >> "$APP/clock.log" 2>&1 &
child=$!
wait "$child"
result=$?
child=''
exit "$result"
