# Device and location adaptation / 设备与位置适配

This is a source-level checklist, not a claim that any additional model is supported. Please report actual device results separately from desktop previews.

## Hardware assumptions / 硬件假设

The current implementation targets Paperwhite 2 on firmware 5.12.2.2:

- Visible portrait size: **758 × 1024**; landscape design size: **1024 × 758**.
- The framebuffer is queried read-only with `FBIOGET_VSCREENINFO`, but the rendered layout still uses those fixed design dimensions.
- `/dev/input/event1`, ARM 32-bit `input_event` records (`2iHHi`, 16 bytes), absolute multi-touch coordinates and a specific landscape transform are assumed.
- Images are drawn with the device's `eips -g ... -w gc16`; periodic full refreshes use `-f`.
- `launch.sh` assumes the existing `awesome` window manager and `pillow` service. It pauses/resumes the existing UI rather than restarting the framework. This follows the approach used by [KOReader's Kindle launcher](https://github.com/koreader/koreader/blob/master/platform/kindle/koreader.sh), but is not a compatibility guarantee for other firmware.
- The Python interpreter, environment variables and native commands must match your runtime.

For another device, start by checking panel dimensions, input-device capabilities and event ABI. Update drawing, hit regions and coordinate conversion together. Verify normal exit, interrupted exit and restoration of the previous sleep/UI state before long-running use. Do not copy the PW2 service handling into an unrelated platform without inspection.

目前的渲染和触摸仍有固定分辨率与路径，并非“读取到分辨率就能自动兼容”。适配时应同时检查字号、间距、触摸区域、坐标转换、刷新命令和退出恢复逻辑。请把“能生成预览图”和“已经在设备上运行”分开记录。

## Location and time zones / 城市与时区

The deliberately small settings screen only exposes `language` (`zh`, `en`) and `display_mode` (`second_timezone`, `lunar`, `both`). It does not currently expose location search or arbitrary time-zone selection.

To change the defaults in `extensions/adelaide-clock/clock.py`:

1. Change the latitude/longitude and API timezone in `API`.
2. Supply matching IANA zoneinfo data instead of the bundled `Adelaide` file, and load it as `TZ`. Do not replace a daylight-saving zone with a permanent fixed offset.
3. Change the `ADELAIDE` label and the main city name as needed.
4. To change the second clock, update `BEIJING` and the localized secondary title. A zone with daylight saving needs corresponding zoneinfo data instead of the Beijing fixed offset.
5. Lunar dates currently follow Beijing dates by design. If the second clock is changed, decide whether lunar conversion should remain tied to Beijing; do not change that calendar rule accidentally.
6. Clear or validate location-specific weather caches. Daily low/high values must continue to select the correct local calendar date.

城市与时区暂时需要改源码和对应时区数据。农历默认按北京时间的日期计算，尤其要检查午夜附近两地日期不同的情况。

## Assets and fonts / 图标和字体

- `tools/build_icons.py` reproduces the original weather PNG artwork. It requires Pillow and writes to the application's `icons/`.
- `tools/build_font.py ORIGINAL_FONT.otf` rebuilds the renamed Chinese subset from Noto Sans CJK SC under OFL. Obtain the original from [Noto CJK](https://github.com/notofonts/noto-cjk/blob/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf); it is not downloaded automatically.
- When adding Chinese UI text, rebuild the subset so the new glyphs are included.
- Monochrome/stipple rendering should be checked on the actual panel; screenshots do not show ghosting.

## Reporting compatibility / 适配反馈

Please include model, firmware, Python/Pillow versions, dimensions/orientation and which functions were physically tested. Screenshots, minimal patches and reproducible steps are welcome. Remove account identifiers, serial numbers, personal files and unrelated logs before posting.
