"""Pillow thumbnail composition adapted from videoeditinggod/v3/thumb/make.py."""
import argparse
from pathlib import Path
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
from config import font_path

def fit_font(draw,text,width,size):
    while size > 20:
        font = ImageFont.truetype(str(font_path(True)),size)
        if draw.textlength(text,font=font) <= width:
            return font
        size -= 2
    raise ValueError('Headline is too long. Use two short lines.')

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--title',required=True)
    p.add_argument('--subtitle',required=True)
    p.add_argument('--badge',default='')
    p.add_argument('--screenshot',type=Path)
    p.add_argument('--cutout',type=Path,help='Transparent person/product PNG')
    p.add_argument('-o','--output',type=Path,required=True)
    a = p.parse_args()
    width,height = 1280,720
    y,x = np.mgrid[:height,:width]
    bg = np.zeros((height,width,3),float)+(8,11,20)
    for cx,cy,r,color,opacity in [(150,700,380,(18,120,120),.75),(1150,60,420,(110,70,200),.7)]:
        bg += np.exp(-((x-cx)**2+(y-cy)**2)/(2*r*r))[...,None]*np.array(color)*opacity
    im = Image.fromarray(bg.clip(0,255).astype('uint8')).convert('RGBA')
    grid = Image.new('RGBA',im.size)
    d = ImageDraw.Draw(grid)
    for gx in range(0,width,48): d.line([(gx,0),(gx,height)],fill=(120,165,195,18))
    for gy in range(0,height,48): d.line([(0,gy),(width,gy)],fill=(120,165,195,18))
    im.alpha_composite(grid)
    if a.screenshot:
        image = ImageOps.fit(Image.open(a.screenshot).convert('RGB'),(510,330))
        card = Image.new('RGBA',(526,346),(94,234,212,255))
        card.paste(image,(8,8))
        card = card.rotate(-5,resample=Image.Resampling.BICUBIC,expand=True)
        im.alpha_composite(card,(38,330))
    if a.cutout:
        person = Image.open(a.cutout).convert('RGBA')
        person.thumbnail((650,720),Image.Resampling.LANCZOS)
        rim = Image.new('RGBA',person.size,(94,234,212,255))
        rim.putalpha(person.getchannel('A').filter(ImageFilter.GaussianBlur(14)))
        loc = (width-person.width,height-person.height)
        im.alpha_composite(rim,loc); im.alpha_composite(person,loc)
    d = ImageDraw.Draw(im)
    max_width = 820 if a.cutout else 1180
    for xy,text,size,color in [((44,20),a.title,126,(244,248,245)),((48,174),a.subtitle,96,(94,234,212))]:
        font = fit_font(d,text,max_width,size)
        d.text(xy,text,font=font,fill=color,stroke_width=4,stroke_fill=(6,10,18))
    if a.badge:
        font = fit_font(d,a.badge,1050,32)
        tw = d.textlength(a.badge,font=font)
        d.rounded_rectangle((48,642,tw+108,700),radius=28,fill=(10,18,30),outline=(94,234,212),width=3)
        d.text((78,650),a.badge,font=font,fill=(244,248,245))
    a.output.parent.mkdir(parents=True,exist_ok=True)
    im.convert('RGB').save(a.output)
    print(a.output)

if __name__ == '__main__':
    main()
