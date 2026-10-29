# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-only
from pathlib import Path
import sys, importlib.util
import argparse
parser=argparse.ArgumentParser()
parser.add_argument('source',type=Path,help='Original NotoSansCJKsc-Regular.otf')
args=parser.parse_args()
BASE=Path(__file__).resolve().parents[1]/'extensions/adelaide-clock'
from fontTools import subset
from fontTools.ttLib import TTFont
font=TTFont(args.source)
opts=subset.Options();opts.name_IDs=[0,1,2,3,4,5,6,13,14,16,17];opts.name_legacy=True
sub=subset.Subsetter(options=opts)
sub.populate(text=' '+(BASE/'clock.py').read_text())
sub.subset(font)
for n in font['name'].names:
 if n.nameID in (1,3,4,6,16):
  n.string=('ClockCJK-Regular' if n.nameID in (3,6) else 'Clock CJK').encode(n.getEncoding(),errors='replace')
font.save(BASE/'fonts/ClockCJK.otf')
