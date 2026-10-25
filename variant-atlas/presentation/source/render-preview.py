"""Render every page of the native PowerPoint PDF and produce a contact sheet."""
from pathlib import Path
import json,math
import pymupdf
from PIL import Image, ImageDraw, ImageFont
root=Path(__file__).resolve().parents[1]
doc=pymupdf.open(root/'Bramha-Atlas-Pitch.pdf')
assert len(doc)==len(json.loads((root/'source/scene.json').read_text()))
thumbs=root/'thumbnails';thumbs.mkdir(exist_ok=True)
font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',18)
sheet=Image.new('RGB',(1600,math.ceil(len(doc)/4)*263),'#e4e7df');draw=ImageDraw.Draw(sheet)
texts=[]
for i,p in enumerate(doc):
 pix=p.get_pixmap(matrix=pymupdf.Matrix(1.6,1.6),alpha=False)
 pix.save(thumbs/f'slide-{i+1:02}.png')
 im=Image.open(thumbs/f'slide-{i+1:02}.png');im.thumbnail((384,216))
 xx=8+(i%4)*400;yy=8+(i//4)*263
 sheet.paste(im,(xx,yy));draw.text((xx+5,yy+224),f'{i+1:02d}  '+json.loads((root/'source/scene.json').read_text())[i]['title'][:33],font=font,fill='#193b3b')
 texts.append(dict(slide=i+1,text=p.get_text()))
sheet.save(root/'slide-contact-sheet.png')
(root/'source/rendered-text.json').write_text(json.dumps(texts,indent=2))
print(f'Rendered {len(doc)} native PowerPoint PDF pages at 1536 × 864.')
