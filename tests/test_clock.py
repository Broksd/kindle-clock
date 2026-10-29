# SPDX-License-Identifier: GPL-3.0-only
import datetime as dt
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import threading
import unittest
from unittest import mock

from PIL import Image, ImageDraw

APP = Path(__file__).resolve().parents[1] / 'extensions/adelaide-clock'
sys.path.insert(0, str(APP))
import clock


def sample_weather(now):
    date = now.date().isoformat()
    return {'fetched_at': now.timestamp(), 'data': {
        'current': {'time': date+'T15:30', 'temperature_2m': 22, 'weather_code': 2, 'is_day': 1},
        'daily': {'time': [date], 'temperature_2m_min': [12], 'temperature_2m_max': [24],
                  'weather_code': [2], 'sunrise': [date+'T06:00'], 'sunset': [date+'T19:30']}}}


class ClockTests(unittest.TestCase):
    def setUp(self):
        self.now = dt.datetime(2026, 10, 29, 15, 38, tzinfo=clock.TZ)
        self.weather = sample_weather(self.now)

    def test_settings_roundtrip_and_invalid_recovery(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'settings.json'
            self.assertEqual(clock.load_settings(path), clock.DEFAULT_SETTINGS)
            for language in ('zh', 'en'):
                for mode in clock.DISPLAY_MODES:
                    expected = {'language': language, 'display_mode': mode}
                    clock.save_settings(expected, path)
                    self.assertEqual(clock.load_settings(path), expected)
            for invalid in ('null', '[]', '{', '{"language":"xx","display_mode":"bad"}'):
                path.write_text(invalid)
                self.assertEqual(clock.load_settings(path), clock.DEFAULT_SETTINGS)
            with self.assertRaises(ValueError):
                clock.save_settings({'language': 'xx', 'display_mode': 'both'}, path)
            with self.assertRaises(OSError):
                clock.save_settings(clock.DEFAULT_SETTINGS, Path(folder)/'missing/settings.json')

    def test_beijing_dst_and_lunar_dates(self):
        expected = [((2026, 2, 17), '正月初一'), ((2026, 10, 29), '九月二十'),
                    ((2025, 7, 25), '闰六月初一')]
        for date, text in expected:
            self.assertEqual(clock.lunar_text(dt.datetime(*date, tzinfo=clock.BEIJING)), text)
        self.assertEqual(clock.lunar_text(self.now.astimezone(clock.BEIJING), 'en'), 'MONTH 9 / DAY 20')
        self.assertEqual(clock.lunar_text(dt.datetime(2025, 7, 25, tzinfo=clock.BEIJING), 'en'),
                         'LEAP MONTH 6 / DAY 1')
        for date, expected_time in [((2026, 1, 15), '09:30'), ((2026, 7, 15), '10:30')]:
            value = dt.datetime(*date, 12, tzinfo=clock.TZ).astimezone(clock.BEIJING)
            self.assertEqual(value.strftime('%H:%M'), expected_time)
        midnight = dt.datetime(2026, 10, 30, 0, 15, tzinfo=clock.TZ).astimezone(clock.BEIJING)
        self.assertEqual(midnight.date(), dt.date(2026, 10, 29))

    def test_forecast_expiry_and_icon_assets(self):
        clock.weather_valid(self.weather['data'])
        self.assertEqual(clock.daily_conditions(self.weather, self.now), (12, 24, 'partly'))
        self.assertEqual(clock.daily_conditions(self.weather, self.now+dt.timedelta(days=1)),
                         (None, None, 'unknown'))
        codes = [0, 1, 2, 3, 45, 48, 51, 53, 55, 56, 57, 61, 63, 65, 66, 67,
                 71, 73, 75, 77, 80, 81, 82, 85, 86, 95, 96, 99, -1]
        for code in codes:
            for daytime in (False, True):
                self.assertTrue((APP/'icons'/(clock.icon_kind(code, daytime)+'.png')).is_file())

    def test_all_layouts_and_english_labels(self):
        original = ImageDraw.ImageDraw.text
        seen = []
        def capture(draw, xy, text, *args, **kwargs):
            seen.append(str(text))
            return original(draw, xy, text, *args, **kwargs)
        with mock.patch.object(clock.time, 'time', return_value=self.now.timestamp()), \
             mock.patch.object(ImageDraw.ImageDraw, 'text', capture):
            for orientation, size in [('landscape', (1024, 758)), ('portrait', (758, 1024))]:
                for language in ('zh', 'en'):
                    for mode in clock.DISPLAY_MODES:
                        seen.clear()
                        image = clock.render(orientation, self.now, self.weather, False, 100, mode, language)
                        self.assertEqual(image.size, size)
                        if language == 'en':
                            self.assertFalse(any('\u4e00' <= c <= '\u9fff' for s in seen for c in s))
                        clock.render(orientation, self.now, None, True, None, mode, language)
                    settings = {'language': language, 'display_mode': 'both'}
                    self.assertEqual(clock.render_settings(orientation, settings).size, size)
                    clock.render_settings(orientation, settings, True)

    def test_touch_parser_and_settings_hit_regions(self):
        def tap(orientation, screen, x, y):
            px, py = (757-y, x) if orientation == 'landscape' else (x, y)
            read, write = os.pipe()
            touch = clock.Touch.__new__(clock.Touch)
            touch.fd, touch.ranges = read, {53: (0, 757), 54: (0, 1023)}
            touch.values, touch.released = {}, False
            def event(kind, code, value):
                return struct.pack('2iHHi', 0, 0, kind, code, round(value))
            try:
                os.write(write, event(3, 53, px)+event(3, 54, py)+event(3, 57, -1)+event(0, 0, 0))
                return touch.read(.01, orientation, screen)
            finally:
                os.close(write)
                touch.close()
        for orientation, width, height in [('landscape', 1024, 758), ('portrait', 758, 1024)]:
            for action, box in clock.settings_regions(orientation).items():
                self.assertEqual(tap(orientation, 'settings', (box[0]+box[2])/2, (box[1]+box[3])/2), action)
            for action, fraction in [('rotate', .15), ('settings', .65), ('exit', .90)]:
                self.assertEqual(tap(orientation, 'clock', width*fraction, height-60), action)
            self.assertIsNone(tap(orientation, 'clock', width*.39, height-60))

    def test_main_settings_save_back_rotate_exit(self):
        weather_data = self.weather
        sequence = iter([('clock', 'settings'), ('settings', 'lang:en'), ('settings', 'mode:lunar'),
                         ('settings', 'back'), ('clock', 'rotate'), ('clock', 'exit')])
        test = self
        class FakeTouch:
            def read(self, timeout, orientation, screen):
                expected, action = next(sequence)
                test.assertEqual(screen, expected)
                return action
            def close(self):
                pass
        class FakeWeather:
            def __init__(self):
                self.stopping = threading.Event()
            def run(self):
                pass
            def get(self):
                return weather_data, False, 0
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in ('fonts', 'icons'):
                (root/name).symlink_to(APP/name, target_is_directory=True)
            path = root/'settings.json'
            clock.save_settings(clock.DEFAULT_SETTINGS, path)
            original_save = clock.save_settings
            frames = []
            with mock.patch.object(clock, 'ROOT', root), \
                 mock.patch.object(clock, 'load_settings', side_effect=lambda: json.loads(path.read_text())), \
                 mock.patch.object(clock, 'save_settings', side_effect=lambda value: original_save(value, path)), \
                 mock.patch.object(clock, 'Touch', FakeTouch), \
                 mock.patch.object(clock, 'Weather', FakeWeather), \
                 mock.patch.object(clock, 'battery', return_value=100), \
                 mock.patch.object(clock.signal, 'signal'), \
                 mock.patch.object(clock.subprocess, 'run'), \
                 mock.patch.object(Image.Image, 'save', lambda image, *a, **k: frames.append(image.copy())):
                clock.main()
            self.assertEqual(json.loads(path.read_text()), {'language': 'en', 'display_mode': 'lunar'})
            self.assertEqual((root/'orientation.txt').read_text(), 'portrait')
            self.assertEqual(len(frames), 6)


if __name__ == '__main__':
    unittest.main()
