# Copyright and third-party notices

Original application changes and original code-drawn weather artwork: copyright 2026 Broksd, licensed under GPL-3.0. See `LICENSE`. Original-source files supplied by other projects retain their notices and licenses.

| Component | Source | License / included notice |
| --- | --- | --- |
| Chinese lunar conversion (`lunardate.py`) | [python-lunardate](https://github.com/lidaobing/python-lunardate) | Upstream copyright header retained; upstream license in `extensions/adelaide-clock/LUNARDATE-LICENSE.txt` |
| DSEG7 Classic Bold | [keshikan/DSEG](https://github.com/keshikan/DSEG) | SIL OFL, `fonts/DSEG-LICENSE.txt` |
| Bitstream Vera | [Bitstream Vera](https://www.gnome.org/fonts/) | `fonts/bitstream-vera-license.txt` |
| Clock CJK | Character subset of [Noto Sans CJK SC](https://github.com/notofonts/noto-cjk), renamed on modification | SIL OFL 1.1, `fonts/Noto-OFL.txt` |
| Public CA certificate bundle | certifi / Mozilla root store | MPL-2.0, `LICENSES/certifi-LICENSE`; no personal certificates or keys |
| Adelaide time-zone data | IANA Time Zone Database | Public-domain TZ data |

Font notice paths above are relative to `extensions/adelaide-clock/`.

Weather data is provided by [Open-Meteo](https://open-meteo.com/) under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). No live weather cache is distributed in this repository.

The design began with inspiration from [GuoBug/kindle-weather-station](https://github.com/GuoBug/kindle-weather-station) (MIT). Current weather artwork is newly code-drawn; the old upstream icon module is not included in this public package. Kindle UI restoration was informed by [KOReader's Kindle launcher](https://github.com/koreader/koreader/blob/master/platform/kindle/koreader.sh). No KOReader runtime is bundled.

Python/Pillow runtime distributions are obtained separately from their original providers. No firmware, jailbreak payloads, Kindle backups, personal books or account data are included.
