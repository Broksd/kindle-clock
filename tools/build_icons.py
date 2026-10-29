# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-only
"""Code-drawn weather icon study. No device changes or image editing."""
from pathlib import Path
import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
OUT=Path(__file__).resolve().parents[1]/'extensions/adelaide-clock/icons'
S=4

def weather_icon(kind,size=(180,160)):
 im=Image.new('L',(180*S,160*S),255);d=ImageDraw.Draw(im)
 def box(v):return tuple(round(x*S) for x in v)
 def line(points,width=2):d.line([(round(x*S),round(y*S)) for x,y in points],fill=0,width=round(width*S),joint='curve')
 def ellipse(v,fill=None,width=2):d.ellipse(box(v),fill=fill,outline=0 if fill is None else None,width=round(width*S))
 def sun(x=119,y=42,r=23):
  ellipse((x-r,y-r,x+r,y+r),width=2.5)
  for i in range(12):
   a=i*math.tau/12;line([(x+math.cos(a)*(r+9),y+math.sin(a)*(r+9)),(x+math.cos(a)*(r+18),y+math.sin(a)*(r+18))],1.8)
 def moon(x=119,y=42,r=27):
  mask=Image.new('L',im.size,0);m=ImageDraw.Draw(mask)
  m.ellipse(box((x-r,y-r,x+r,y+r)),fill=255)
  m.ellipse(box((x-r*.2,y-r*1.2,x+r*1.35,y+r*.6)),fill=0)
  edge=ImageChops.subtract(mask,mask.filter(ImageFilter.MinFilter(19)))
  im.paste(0,(0,0),edge)
 def star(x,y,r=4):
  line([(x-r,y),(x+r,y)],1.2);line([(x,y-r),(x,y+r)],1.2)
 def cloud(dx=0,dy=0,smaller=False):
  mask=Image.new('L',im.size,0);m=ImageDraw.Draw(mask)
  def move(v):return box(tuple(n+(dx if i%2==0 else dy) for i,n in enumerate(v)))
  for e in [(24,61,80,115),(56,36,124,106),(97,65,151,115)]:m.ellipse(move(e),fill=255)
  m.rectangle(move((51,84,125,115)),fill=255)
  im.paste(255,(0,0),mask)
  inner=mask.filter(ImageFilter.MinFilter(25));im.paste(0,(0,0),ImageChops.subtract(mask,inner))
  dots=Image.new('L',im.size,0);p=ImageDraw.Draw(dots)
  for row,yy in enumerate(range(80,115,6)):
   for xx in range(34+row%2*3,152,6):
    if yy<98 and xx<109:continue
    p.ellipse(box((xx+dx-.8,yy+dy-.8,xx+dx+.8,yy+dy+.8)),fill=255)
  im.paste(0,(0,0),ImageChops.multiply(dots,inner))
 def rain(count=3,heavy=False,dots=False):
  xs={1:[88],2:[70,109],3:[56,89,122],4:[48,75,102,129]}[count]
  for i,x in enumerate(xs):
   yy=119+(i%2)*4
   if dots:ellipse((x-1,yy,x+2,yy+3),fill=0)
   else:line([(x+4,yy),(x-3,yy+(19 if heavy else 12))],3 if heavy else 2)
   if dots:ellipse((x-5,yy+13,x-2,yy+16),fill=0)
 def snowflake(x,y,r=8):
  for i in range(3):
   a=i*math.pi/3;line([(x-math.cos(a)*r,y-math.sin(a)*r),(x+math.cos(a)*r,y+math.sin(a)*r)],1.6)
 def bolt():
  d.polygon([tuple(round(t*S) for t in xy) for xy in [(96,101),(82,123),(95,123),(83,147),(115,116),(101,116),(112,101)]],fill=0)
 if kind=='sun':sun(88,69,32)
 elif kind=='moon':moon(85,70,35);star(132,44);star(119,102,3)
 elif kind=='partly':sun();cloud()
 elif kind=='partly-night':moon();star(153,23,3);cloud()
 elif kind=='cloudy':cloud(0,-3)
 elif kind=='fog':
  cloud(0,-15)
  for i,y in enumerate([116,128,140]):
   line([(32+(i%2)*7,y),(89,y)],2);line([(102,y),(146-(i%2)*8,y)],2)
 else:
  if kind=='showers':sun(119,35,20)
  cloud(0,-15)
  if kind=='drizzle':rain(3,dots=True)
  elif kind=='light-rain':rain(1)
  elif kind=='rain':rain(3)
  elif kind=='heavy-rain':rain(4,True)
  elif kind=='showers':rain(2)
  elif kind=='snow':snowflake(75,129);snowflake(112,133,6)
  elif kind=='heavy-snow':
   for x,y in [(55,127),(90,137),(125,125)]:snowflake(x,y,8)
  elif kind=='freezing':
   rain(1);snowflake(119,133,7);ellipse((61,131,68,138),width=1.5)
  elif kind=='thunder':bolt();line([(57,119),(51,133)],2);line([(136,119),(130,133)],2)
  elif kind=='hail':
   bolt()
   for x,y in [(53,124),(129,124),(139,139)]:ellipse((x-3,y-3,x+3,y+3),width=1.5)
 return im.resize(size,Image.Resampling.LANCZOS)

if __name__ == '__main__':
    OUT.mkdir(parents=True,exist_ok=True)
    for kind in ['sun','moon','partly','partly-night','cloudy','fog','drizzle','light-rain','rain','heavy-rain','showers','snow','heavy-snow','freezing','thunder','hail']:
        weather_icon(kind).save(OUT/(kind+'.png'))
    image=Image.new('L',(180,160),255);draw=ImageDraw.Draw(image)
    draw.ellipse((62,46,118,102),outline=0,width=3);draw.line((90,61,90,82),fill=0,width=3);draw.ellipse((88,89,92,93),fill=0)
    image.save(OUT/'unknown.png')
