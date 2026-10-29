#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-only
# Name: Adelaide Clock
# Author: Broksd
# Icon: /mnt/us/extensions/adelaide-clock/library-cover.jpg
APP=/mnt/us/extensions/adelaide-clock
setsid sh "$APP/launch.sh" >/dev/null 2>&1 </dev/null &
exit 0
