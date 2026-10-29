# Kindle Clock

[中文](README.md) · [Porting notes](docs/PORTING.md) · [Third-party notices](NOTICE.md)

A small project that turns an old Kindle into a desk clock: large digital time, weather icons, daily minimum/maximum temperatures, and an optional second clock or Chinese lunar date.

It began as a personal tool for a **Kindle Paperwhite 2 (2013 / 6th generation), firmware 5.12.2.2**. The source and design are shared as a starting point. You are welcome to adapt it to your own device, location and preferences, report compatibility results, or contribute a PR.

**This is an early hobby project, not a universal, fully tested Kindle installer.**

## AI-assisted jailbreaking, reverse analysis and development

This old-device project was developed with **AI assistance (Codex)**. The work included checking publicly documented jailbreak compatibility, reading open-source launchers, inspecting package formats and runtime dependencies, and debugging display, touch, weather connectivity and desktop restoration, alongside the UI and application code.

“AI-assisted hacking / reverse analysis” here means using AI to understand existing community techniques, tool behavior and file formats, followed by device-specific adaptation and verification. The device was jailbroken using the existing [WinterBreak](https://github.com/KindleModding/WinterBreak) project. Package-format analysis referenced [KindleTool](https://github.com/NiLuJe/KindleTool), and UI restoration was informed by KOReader. This repository does not claim a newly discovered jailbreak vulnerability or provide a universal cracking tool.

We hope it serves as a practical starting point for AI-assisted exploration of old hardware. Contributions and adaptations are welcome; please distinguish inspected code and desktop tests from behavior actually verified on a device.

## What has been tested?

| Area | Status |
| --- | --- |
| Fullscreen display, time, online weather check and normal exit on PW2 | Verified on the preceding device version |
| New bilingual settings, three right-panel modes, saved preferences and touch flow | Desktop simulation tests passed; not yet tested on the Kindle |
| Other Kindle models, screen sizes and firmware versions | Unverified; contributions welcome |

The latest settings version was deliberately not installed back onto the original device for another test round. Rendered previews are not proof of device compatibility.

![English landscape preview](docs/images/landscape-en.png)

## Features

- Compact, large seven-segment time; portrait and landscape layouts.
- Monochrome weather icons with stippled clouds and unshaded moon outlines.
- Daily minimum–maximum temperatures in Celsius, without hourly forecasts.
- **English / 中文** interface; preferences save automatically.
- One right-panel selector: **SECOND TIME ZONE**, **LUNAR DATE**, or **LUNAR + SECOND TIME ZONE**. A single item is centered; combined items sit side by side in landscape and stack in portrait.
- Automatic sleep is prevented while running and the previous setting is restored on exit.
- A static library cover launches **Adelaide Clock**.

![Settings preview](docs/images/settings-en.png)

## Time, location and weather

Time comes from the Kindle system clock, without online time requests. Defaults are **Australia/Adelaide** for the main clock, including daylight saving, and **UTC+08:00 / Beijing** for the second clock. Chinese lunar dates are calculated locally from the Beijing date; the bundled library supports 1900–2099. English lunar labels use forms such as `MONTH 9 / DAY 20`; `LEAP` marks a leap month.

[Open-Meteo](https://open-meteo.com/) weather updates approximately every 15 minutes. Daily temperatures follow the Adelaide calendar date. Offline data is marked accordingly; an expired forecast is never silently relabeled as today's range.

The settings screen only controls language and panel contents. **Location and time zones still use the original Adelaide/Beijing example.** Changing them requires editing the coordinates, zone data and labels described in [PORTING.md](docs/PORTING.md).

## Requirements and manual installation

This project assumes an already jailbroken Kindle with shell-script library integration and a compatible **Python 3.9+ / Pillow** runtime. The original device used NiLuJe Python3 0.15.N for PW2+, providing Python 3.9.8 and Pillow 9.0.0.dev0. The default Python path is `/mnt/us/python3/bin/python3.9`.

Native `eips`, LIPC tools, `initctl`, `setsid` and related system utilities must be available. Runtime packages, jailbreak tools, firmware and user backups are not distributed here. See [NiLuJe's original runtime thread](https://www.mobileread.com/forums/showthread.php?t=225030) for upstream material.

For a device whose prerequisites and paths have been checked:

1. Copy `extensions/adelaide-clock/` into the matching Kindle directory.
2. Copy `documents/Adelaide-Clock.sh` into the Kindle's `documents/`.
3. Check the Python path in `launch.sh`.
4. Safely eject USB storage, then open **Adelaide Clock** in the library. Enable Wi-Fi for weather.

Use **ROTATE**, **SETTINGS**, and **EXIT** along the bottom. In settings, choose a language and a right-panel mode; changes save automatically. **BACK** returns to the clock. Personal `settings.json` is created at runtime and is excluded from the repository.

Do not assume other models use the same framebuffer, touch coordinates or desktop services. The current implementation still contains PW2-specific values. Read the porting notes first.

## Development

Desktop tests require Python 3.9+ on a platform with `fcntl`, such as Linux/macOS:

```sh
python3 -m pip install -r requirements-dev.txt
python3 -m unittest discover -s tests -v
```

Tests do not access a real Kindle. Device touch, refresh behavior, power use and desktop restoration still need physical testing.

## Contributions

Fork and adjust the project for your hardware. Useful reports include model, firmware, runtime versions and reproduction steps. Please remove personal information from screenshots or logs; do not upload books, account data or full device backups.

Original application code and original icon artwork are licensed under GPL-3.0. Bundled third-party components retain their own terms; see [LICENSE](LICENSE) and [NOTICE.md](NOTICE.md).
