#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Adelaide clock with local Beijing/lunar date and daily weather."""
import argparse
import datetime as dt
import fcntl
import json
import logging
import math
import os
from pathlib import Path
import select
import signal
import ssl
import struct
import subprocess
import sys
import threading
import time
import urllib.request
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw, ImageFont, ImageChops
from lunardate import LunarDate

ROOT = Path(__file__).resolve().parent
with (ROOT / 'Adelaide').open('rb') as handle:
    TZ = ZoneInfo.from_file(handle, key='Australia/Adelaide')
BEIJING = dt.timezone(dt.timedelta(hours=8), 'Asia/Shanghai')
API = ('https://api.open-meteo.com/v1/forecast?latitude=-34.9285&longitude=138.6007'
       '&current=temperature_2m,weather_code,is_day'
       '&daily=temperature_2m_min,temperature_2m_max,weather_code,sunrise,sunset'
       '&forecast_days=3&timezone=Australia%2FAdelaide')
SYSTEM_ENV = {k: v for k, v in os.environ.items() if k not in ('LD_LIBRARY_PATH', 'PYTHONHOME', 'PYTHONPATH')}
FONT_CACHE = {}
ICON_CACHE = {}
WEATHER_CACHE = Path('/tmp/adelaide-clock-weather-v2.json')
SETTINGS_PATH = ROOT / 'settings.json'
DEFAULT_SETTINGS = {'language': 'zh', 'display_mode': 'both'}
DISPLAY_MODES = ('second_timezone', 'lunar', 'both')


def load_settings(path=SETTINGS_PATH):
    try:
        raw = json.loads(Path(path).read_text())
    except (OSError, ValueError):
        raw = {}
    if not isinstance(raw, dict):
        raw = {}
    return {key: raw.get(key) if raw.get(key) in allowed else DEFAULT_SETTINGS[key]
            for key, allowed in {'language': ('zh', 'en'), 'display_mode': DISPLAY_MODES}.items()}


def save_settings(settings, path=SETTINGS_PATH):
    normalized = {key: settings.get(key, default) for key, default in DEFAULT_SETTINGS.items()}
    if normalized['language'] not in ('zh', 'en') or normalized['display_mode'] not in DISPLAY_MODES:
        raise ValueError('Invalid settings')
    path = Path(path)
    temporary = path.with_suffix('.json.tmp')
    with temporary.open('w') as stream:
        json.dump(normalized, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)
    return normalized

def command(args):
    return subprocess.check_output(args, stderr=subprocess.DEVNULL, env=SYSTEM_ENV, timeout=8).decode().strip()

def framebuffer_info():
    fd = os.open('/dev/fb0', os.O_RDONLY)
    try:
        info = struct.unpack('40I', fcntl.ioctl(fd, 0x4600, bytes(160)))
        return {'width': info[0], 'height': info[1], 'virtual_width': info[2],
                'virtual_height': info[3], 'bits_per_pixel': info[6], 'rotation': info[34]}
    finally:
        os.close(fd)

def battery():
    try:
        return int(command(['lipc-get-prop', 'com.lab126.powerd', 'battLevel']))
    except Exception:
        return None

def weather_valid(data):
    current = data['current']
    value = float(current['temperature_2m'])
    if not math.isfinite(value) or not -80 <= value <= 65:
        raise ValueError('Invalid weather temperature')
    daily = data['daily']
    count = len(daily['time'])
    if not count or any(len(daily[key]) != count for key in
                        ('temperature_2m_min', 'temperature_2m_max', 'weather_code', 'sunrise', 'sunset')):
        raise ValueError('Incomplete daily weather')
    for day, low, high in zip(daily['time'], daily['temperature_2m_min'], daily['temperature_2m_max']):
        dt.date.fromisoformat(day)
        if low is not None and high is not None:
            if not (-80 <= float(low) <= float(high) <= 65):
                raise ValueError('Invalid daily temperature range')
    return data

def fetch_weather():
    request = urllib.request.Request(API, headers={'User-Agent': 'Adelaide-Kindle-Clock/1.0'})
    context = ssl.create_default_context(cafile=str(ROOT / 'cacert.pem'))
    with urllib.request.urlopen(request, timeout=12, context=context) as response:
        raw = response.read(512000)
    data = weather_valid(json.loads(raw.decode('utf-8')))
    return {'fetched_at': time.time(), 'data': data}

class Weather:
    def __init__(self):
        self.lock = threading.Lock()
        self.snapshot = None
        self.version = 0
        self.failed = False
        self.stopping = threading.Event()
        for path in (WEATHER_CACHE, ROOT / 'weather-cache.json'):
            try:
                value = json.loads(path.read_text())
                weather_valid(value['data'])
                self.snapshot = value
                break
            except Exception:
                pass

    def run(self):
        while not self.stopping.is_set():
            try:
                snapshot = fetch_weather()
                temporary = WEATHER_CACHE.with_suffix('.json.tmp')
                temporary.write_text(json.dumps(snapshot))
                temporary.replace(WEATHER_CACHE)
                with self.lock:
                    self.snapshot = snapshot
                    self.failed = False
                    self.version += 1
            except Exception as error:
                logging.warning('Weather update: %s', error)
                with self.lock:
                    self.failed = True
                    self.version += 1
            self.stopping.wait(900)

    def get(self):
        with self.lock:
            return self.snapshot, self.failed, self.version

def icon_kind(code, is_day=True):
    if code == 0:
        return 'sun' if is_day else 'moon'
    if code in (1, 2):
        return 'partly' if is_day else 'partly-night'
    if code == 3:
        return 'cloudy'
    if code in (45, 48):
        return 'fog'
    if code in (51, 53, 55):
        return 'drizzle'
    if code in (56, 57, 66, 67):
        return 'freezing'
    if code == 61:
        return 'light-rain'
    if code == 63:
        return 'rain'
    if code == 65:
        return 'heavy-rain'
    if code in (71, 73, 77, 85):
        return 'snow'
    if code in (75, 86):
        return 'heavy-snow'
    if code in (80, 81, 82):
        return 'showers'
    if code == 95:
        return 'thunder'
    if code in (96, 99):
        return 'hail'
    return 'unknown'


def lunar_text(beijing, language='zh'):
    try:
        lunar = LunarDate.from_solar_date(beijing.year, beijing.month, beijing.day)
    except ValueError:
        return '--'
    if language == 'en':
        return ('LEAP ' if lunar.is_leap_month else '') + 'MONTH ' + str(lunar.month) + ' / DAY ' + str(lunar.day)
    months = ('正', '二', '三', '四', '五', '六', '七', '八', '九', '十', '冬', '腊')
    digits = '一二三四五六七八九十'
    day = lunar.day
    if day <= 10:
        day_text = '初' + digits[day-1]
    elif day < 20:
        day_text = '十' + digits[day-11]
    elif day == 20:
        day_text = '二十'
    elif day < 30:
        day_text = '廿' + digits[day-21]
    else:
        day_text = '三十'
    return ('闰' if lunar.is_leap_month else '') + months[lunar.month-1] + '月' + day_text


def daily_conditions(snapshot, now):
    """Select today's Adelaide forecast; never relabel yesterday's range."""
    if not snapshot:
        return None, None, 'unknown'
    daily = snapshot['data']['daily']
    today = now.astimezone(TZ).date().isoformat()
    try:
        index = daily['time'].index(today)
    except ValueError:
        return None, None, 'unknown'
    code = daily['weather_code'][index]
    current = snapshot['data']['current']
    current_time = dt.datetime.fromisoformat(current['time'])
    current_is_fresh = abs((now.astimezone(TZ).replace(tzinfo=None)-current_time).total_seconds()) <= 1800
    if current_is_fresh:
        code = current['weather_code']
        is_day = bool(current.get('is_day', 1))
    else:
        sunrise = dt.datetime.fromisoformat(daily['sunrise'][index]).replace(tzinfo=TZ)
        sunset = dt.datetime.fromisoformat(daily['sunset'][index]).replace(tzinfo=TZ)
        is_day = sunrise <= now < sunset
    return daily['temperature_2m_min'][index], daily['temperature_2m_max'][index], icon_kind(code, is_day)


def render(orientation, now, snapshot, failed=False, level=None, display_mode='both', language='zh'):
    if display_mode not in ('second_timezone', 'lunar', 'both'):
        raise ValueError('Unknown secondary panel display mode')
    english = language == 'en'
    secondary_title = 'BEIJING TIME' if english else '北京时间'
    lunar_title = 'LUNAR DATE' if english else '农历'
    landscape = orientation == 'landscape'
    width, height = (1024, 758) if landscape else (758, 1024)
    image = Image.new('L', (width, height), 255)
    draw = ImageDraw.Draw(image)
    margin = 46 if landscape else 40

    def font_for(kind, size):
        filename = {'clock': 'DSEG7Classic-Bold.ttf', 'chinese': 'ClockCJK.otf'}.get(kind, 'Vera.ttf')
        key = filename, size
        if key not in FONT_CACHE:
            FONT_CACHE[key] = ImageFont.truetype(str(ROOT / 'fonts' / filename), size)
        return FONT_CACHE[key]

    def label(text, x, y, size=22, align='left', clock=False, max_width=None, chinese=False):
        text = str(text)
        kind = 'clock' if clock else 'chinese' if chinese else 'plain'
        while True:
            font = font_for(kind, size)
            box = draw.textbbox((0, 0), text, font=font)
            w = box[2]-box[0]
            fit = draw.textbbox((0, 0), '88:88', font=font) if clock and ':' in text else box
            if max_width is None or fit[2]-fit[0] <= max_width or size <= 12:
                break
            size -= 1
        left = x-w if align == 'right' else x-w/2 if align == 'center' else x
        draw.text((round(left-box[0]), round(y-box[1])), text, font=font, fill=0)
        return left, y, left+w, y+box[3]-box[1]

    def rule(y):
        draw.line((margin, y, width-margin, y), fill=0, width=2)

    def temperature_range(low, high, center, y, size, max_width):
        values = [str(round(value)) if value is not None else '--' for value in (low, high)]
        gap, degree, dash = 15, 7, 14
        while True:
            font = font_for('clock', size)
            boxes = [draw.textbbox((0, 0), v, font=font) for v in values]
            total = sum(b[2]-b[0] for b in boxes)+2*(4+degree)+dash+2*gap
            if total <= max_width or size <= 20:
                break
            size -= 1
        layer = Image.new('L', (math.ceil(total)+20, size+20), 255)
        ink = ImageDraw.Draw(layer)
        x = 8
        for index, value in enumerate(values):
            box = ink.textbbox((0, 0), value, font=font)
            ink.text((x-box[0], -box[1]), value, font=font, fill=0)
            x += box[2]-box[0]+4
            ink.ellipse((x, 1, x+degree, 1+degree), outline=0, width=2)
            x += degree+gap
            if index == 0:
                ink.line((x, size*.47, x+dash, size*.47), fill=0, width=2)
                x += dash+gap
        bounds = ImageChops.invert(layer).getbbox()
        if bounds:
            content = layer.crop(bounds)
            image.paste(content, (round(center-content.width/2), round(y)))

    draw.rectangle((17, 17, width-18, height-18), outline=0, width=3)
    draw.rectangle((25, 25, width-26, height-26), outline=0, width=1)
    header = 62 if landscape else 70
    label('ADELAIDE', margin+4, header, 24 if landscape else 22)
    label(now.strftime('%a  %m.%d').upper(), width-margin-4, header,
          28 if landscape else 25, align='right')
    rule(124 if landscape else 140)
    label('24H', margin+4, 160 if landscape else 192, 22)
    label(now.strftime('%H:%M'), width/2, 210 if landscape else 294,
          350 if landscape else 268, align='center', clock=True,
          max_width=width-margin*2-10)
    bottom = 516 if landscape else 624
    footer = height-92
    rule(bottom)
    center_y = (bottom+footer)/2
    split = width//2
    inset = 20 if landscape else 36
    draw.line((split, bottom+inset, split, footer-inset), fill=0, width=2)
    low, high, kind = daily_conditions(snapshot, now)
    icon_size = (150, 133) if landscape else (181, 161)
    key = kind, icon_size
    if key not in ICON_CACHE:
        with Image.open(ROOT / 'icons' / (kind+'.png')) as source:
            ICON_CACHE[key] = source.convert('L').resize(icon_size, Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.LANCZOS)
    if landscape:
        image.paste(ICON_CACHE[key], (margin+10, round(center_y-66)))
        temperature_range(low, high, margin+322, center_y-21, 42, 250)
    else:
        tile = ICON_CACHE[key]
        bounds = ImageChops.invert(tile).getbbox()
        visible_center = (bounds[0]+bounds[2])/2 if bounds else tile.width/2
        image.paste(tile, (round((margin+split)/2-visible_center), round(center_y-118)))
        temperature_range(low, high, (margin+split)/2, center_y+60, 40, split-margin-30)
    stale = failed or not snapshot or time.time()-float(snapshot['fetched_at']) > 1800
    if stale:
        label(('OFFLINE' if snapshot or failed else 'UPDATING') if english else
              ('离线' if snapshot or failed else '更新中'), margin+4, bottom+9, 13, chinese=not english)
    beijing = now.astimezone(BEIJING)
    lunar = lunar_text(beijing, language)
    rx, right = split+20, width-margin-4
    if display_mode == 'second_timezone':
        center = (split+width-margin)/2
        label(secondary_title, center, center_y-(52 if landscape else 63),
              22 if landscape else 23, align='center', chinese=not english)
        label(beijing.strftime('%H:%M'), center, center_y-(11 if landscape else 5),
              70 if landscape else 66, align='center', clock=True,
              max_width=width-margin-split-42)
    elif display_mode == 'lunar':
        center = (split+width-margin)/2
        label(lunar_title, center, center_y-(40 if landscape else 51),
              22 if landscape else 23, align='center', chinese=not english)
        label(lunar, center, center_y+(3 if landscape else 7),
              (30 if landscape else 25) if english else (43 if landscape else 42), align='center', chinese=not english,
              max_width=width-margin-split-42)
    elif landscape:
        content_left, content_right = split+24, width-margin-10
        time_center = content_left+(content_right-content_left)*.245
        lunar_center = content_left+(content_right-content_left)*.77
        label(secondary_title, time_center, center_y-39, 20 if english else 22, align='center', chinese=not english, max_width=206)
        label(lunar_title, lunar_center, center_y-39, 19 if english else 22, align='center', chinese=not english, max_width=174)
        label(beijing.strftime('%H:%M'), time_center, center_y+1, 47, align='center', clock=True, max_width=206)
        if english:
            parts = lunar.split(' / ')
            label(parts[0], lunar_center, center_y, 21, align='center', max_width=174)
            label(parts[-1] if len(parts) > 1 else '', lunar_center, center_y+29, 23, align='center', max_width=174)
        else:
            label(lunar, lunar_center, center_y+9, 29, align='center', max_width=174, chinese=True)
    else:
        label(secondary_title, (rx+right)/2, center_y-84, 22 if english else 23, align='center', chinese=not english)
        label(beijing.strftime('%H:%M'), (rx+right)/2, center_y-30, 52, align='center', clock=True, max_width=right-rx)
        if english:
            label(lunar_title, (rx+right)/2, center_y+42, 16, align='center')
            label(lunar, (rx+right)/2, center_y+70, 21, align='center', max_width=right-rx)
        else:
            label('农历  '+lunar, (rx+right)/2, center_y+53, 26, align='center', max_width=right-rx, chinese=True)
    rule(footer)
    label('ROTATE' if english else '旋转', width*.15, footer+29, 20, align='center', chinese=not english)
    label(('BAT ' if english else '电量 ')+(str(level)+'%' if level is not None else '--'), width*.39, footer+29, 18, align='center', chinese=not english)
    label('SETTINGS' if english else '设置', width*.65, footer+29, 19, align='center', chinese=not english)
    label('EXIT' if english else '退出', width*.90, footer+29, 20, align='center', chinese=not english)
    return image


def settings_regions(orientation):
    width, height = (1024, 758) if orientation == 'landscape' else (758, 1024)
    margin = 48
    language_top = round(height*.20)+42
    language_height = 64 if orientation == 'landscape' else 76
    mode_top = language_top+language_height+86
    mode_height = 64 if orientation == 'landscape' else 86
    return {
        'back': (width-margin-140, margin, width-margin, margin+54),
        'lang:zh': (margin, language_top, width//2-12, language_top+language_height),
        'lang:en': (width//2+12, language_top, width-margin, language_top+language_height),
        **{'mode:'+mode: (margin, mode_top+index*(mode_height+14),
                         width-margin, mode_top+index*(mode_height+14)+mode_height)
           for index, mode in enumerate(DISPLAY_MODES)}
    }


def touch_action(x, y, orientation, screen='clock'):
    width, height = (1024, 758) if orientation == 'landscape' else (758, 1024)
    if screen == 'settings':
        for action, (left, top, right, bottom) in settings_regions(orientation).items():
            if left <= x <= right and top <= y <= bottom:
                return action
        return None
    if y >= height-92:
        if x < width*.27:
            return 'rotate'
        if width*.51 <= x < width*.79:
            return 'settings'
        if x >= width*.80:
            return 'exit'
    return None


def render_settings(orientation, settings, save_error=False):
    width, height = (1024, 758) if orientation == 'landscape' else (758, 1024)
    image = Image.new('L', (width, height), 255)
    draw = ImageDraw.Draw(image)
    english = settings['language'] == 'en'
    regions = settings_regions(orientation)
    def label(value, x, y, size=24, max_width=None, center=False):
        filename = 'ClockCJK.otf' if any(ord(c) > 127 for c in value) else 'Vera.ttf'
        while True:
            key = filename, size
            if key not in FONT_CACHE:
                FONT_CACHE[key] = ImageFont.truetype(str(ROOT/'fonts'/filename), size)
            font = FONT_CACHE[key]
            box = draw.textbbox((0, 0), value, font=font)
            w = box[2]-box[0]
            if max_width is None or w <= max_width or size <= 14:
                break
            size -= 1
        draw.text((round(x-w/2-box[0] if center else x-box[0]), round(y-box[1])), value, font=font, fill=0)
    draw.rectangle((17, 17, width-18, height-18), outline=0, width=3)
    draw.rectangle((25, 25, width-26, height-26), outline=0, width=1)
    label('SETTINGS' if english else '设置', 48, 57, 32)
    left, top, right, bottom = regions['back']
    draw.rectangle((left, top, right, bottom), outline=0, width=2)
    label('BACK' if english else '返回', (left+right)/2, top+15, 23, center=True)
    language_top = regions['lang:zh'][1]
    label('LANGUAGE' if english else '语言', 48, language_top-42, 23)
    mode_top = regions['mode:second_timezone'][1]
    label('RIGHT PANEL' if english else '右侧显示', 48, mode_top-42, 23)
    names = {'lang:zh': '中文', 'lang:en': 'English',
             'mode:second_timezone': 'SECOND TIME ZONE' if english else '第二时区',
             'mode:lunar': 'LUNAR DATE' if english else '农历',
             'mode:both': 'LUNAR + SECOND TIME ZONE' if english else '农历 + 第二时区'}
    for action, value in names.items():
        left, top, right, bottom = regions[action]
        selected = (action == 'lang:'+settings['language'] or action == 'mode:'+settings['display_mode'])
        draw.rectangle((left, top, right, bottom), outline=0, width=3 if selected else 1)
        cx, cy = left+26, (top+bottom)/2
        draw.ellipse((cx-10, cy-10, cx+10, cy+10), outline=0, width=2)
        if selected:
            draw.ellipse((cx-5, cy-5, cx+5, cy+5), fill=0)
        label(value, left+52, cy-13, 25, max_width=right-left-72)
    message = ('COULD NOT SAVE. TRY AGAIN.' if english else '无法保存，请重试') if save_error else (
        'CHANGES SAVE AUTOMATICALLY' if english else '选择后自动保存')
    label(message, width/2, height-76, 20, max_width=width-96, center=True)
    return image


class Touch:
    def __init__(self, path='/dev/input/event1'):
        self.fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
        self.ranges = {}
        for code in (0, 1, 53, 54):
            try:
                result = fcntl.ioctl(self.fd, 0x80184540+code, bytes(24))
                _, minimum, maximum, _, _, _ = struct.unpack('6i', result)
                if maximum > minimum:
                    self.ranges[code] = minimum, maximum
            except OSError:
                pass
        if not (53 in self.ranges and 54 in self.ranges or 0 in self.ranges and 1 in self.ranges):
            raise RuntimeError('Touch coordinate ranges unavailable')
        self.values = {}
        self.released = False

    def read(self, timeout, orientation, screen='clock'):
        if not select.select([self.fd], [], [], timeout)[0]:
            return None
        try:
            raw = os.read(self.fd, 16*64)
        except BlockingIOError:
            return None
        for offset in range(0, len(raw)-15, 16):
            _, _, kind, code, value = struct.unpack('2iHHi', raw[offset:offset+16])
            if kind == 3 and code in (0, 1, 53, 54):
                self.values[code] = value
            if kind == 3 and code == 57 and value == -1 or kind == 1 and code == 330 and value == 0:
                self.released = True
            if kind == 0 and code == 0 and self.released:
                self.released = False
                xcode, ycode = (53, 54) if 53 in self.values and 54 in self.values else (0, 1)
                if xcode not in self.values or ycode not in self.values:
                    continue
                xmin, xmax = self.ranges[xcode]
                ymin, ymax = self.ranges[ycode]
                x = (self.values[xcode]-xmin)*757/(xmax-xmin)
                y = (self.values[ycode]-ymin)*1023/(ymax-ymin)
                if orientation == 'landscape':
                    x, y = y, 757-x
                    width, height = 1024, 758
                else:
                    width, height = 758, 1024
                action = touch_action(x, y, orientation, screen)
                if action:
                    return action
        return None

    def close(self):
        os.close(self.fd)

def check():
    import PIL
    print('Python:', sys.version.split()[0])
    print('Pillow:', PIL.__version__)
    print('Adelaide local time:', dt.datetime.now(TZ).isoformat())
    print('Framebuffer:', framebuffer_info())
    print('Native display:', command(['eips', '-i']))
    touch = Touch()
    print('Touch ranges:', touch.ranges)
    touch.close()
    try:
        weather = fetch_weather()
        (ROOT / 'weather-cache.json').write_text(json.dumps(weather))
        print('WEATHER_CHECK_OK:', weather['data']['current'])
    except Exception as error:
        print('WEATHER_CHECK_FAILED:', repr(error))
        weather = Weather().snapshot
    settings = load_settings()
    render('landscape', dt.datetime.now(TZ), weather, level=battery(), **settings).save('/tmp/adelaide-clock-check.png')
    print('CLOCK_CHECK_OK')

def main():
    beijing_now = dt.datetime.now(BEIJING)
    settings = load_settings()
    screen, save_error = 'clock', False
    logging.info('CLOCK_V3_STARTED language=%s mode=%s Beijing=%s lunar=%s',
                 settings['language'], settings['display_mode'], beijing_now.isoformat(), lunar_text(beijing_now))
    running = [True]
    def stop(signum, frame):
        running[0] = False
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        orientation = (ROOT / 'orientation.txt').read_text().strip()
    except OSError:
        orientation = 'landscape'
    if orientation not in ('landscape', 'portrait'):
        orientation = 'landscape'
    weather = Weather()
    worker = threading.Thread(target=weather.run, daemon=True)
    worker.start()
    touch = Touch()
    previous = None
    refreshes = 0
    level = battery()
    try:
        while running[0]:
            now = dt.datetime.now(TZ)
            snapshot, failed, version = weather.get()
            state = now.strftime('%Y-%m-%d %H:%M'), orientation, version, screen, tuple(sorted(settings.items())), save_error
            if state != previous:
                if previous is None or previous[0] != state[0]:
                    level = battery()
                image = render_settings(orientation, settings, save_error) if screen == 'settings' else render(
                    orientation, now, snapshot, failed, level, **settings)
                if orientation == 'landscape':
                    image = image.rotate(270, expand=True)
                path = '/tmp/adelaide-clock-frame.png'
                image.save(path)
                args = ['eips', '-g', path, '-w', 'gc16']
                if refreshes % 15 == 0:
                    args.append('-f')
                subprocess.run(args, env=SYSTEM_ENV, check=True, timeout=15,
                               stdout=subprocess.DEVNULL)
                refreshes += 1
                previous = state
            action = touch.read(.75, orientation, screen)
            if action == 'exit':
                break
            if action == 'rotate':
                orientation = 'portrait' if orientation == 'landscape' else 'landscape'
                (ROOT / 'orientation.txt').write_text(orientation)
            elif action == 'settings':
                screen, save_error = 'settings', False
            elif action == 'back':
                screen, save_error = 'clock', False
            elif action and action.startswith(('lang:', 'mode:')):
                key = 'language' if action.startswith('lang:') else 'display_mode'
                candidate = dict(settings)
                candidate[key] = action.split(':', 1)[1]
                try:
                    settings = save_settings(candidate)
                    save_error = False
                    logging.info('SETTINGS_CHANGED language=%s mode=%s', settings['language'], settings['display_mode'])
                except OSError:
                    save_error = True
                    logging.exception('Settings could not be saved')
    finally:
        touch.close()
        weather.stopping.set()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    check() if args.check else main()
