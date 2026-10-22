"""Render the project's own geometric app mark into Windows ICO."""
from pathlib import Path
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1]
size=512
image=Image.new('RGBA',(size,size),(0,0,0,0));draw=ImageDraw.Draw(image)
draw.rounded_rectangle((16,16,496,496),radius=120,fill='#19171a',outline='#806c43',width=12)
draw.ellipse((144,144,368,368),outline='#e1c27c',width=20)
orbit=Image.new('RGBA',(size,size),(0,0,0,0));od=ImageDraw.Draw(orbit);od.ellipse((68,184,444,328),outline='#e1c27c',width=16);orbit=orbit.rotate(40,resample=Image.Resampling.BICUBIC);image=Image.alpha_composite(image,orbit);draw=ImageDraw.Draw(image)
draw.ellipse((232,232,280,280),fill='#fff3cc');draw.polygon([(384,84),(416,116),(384,148),(352,116)],fill='#efce8e')
image.save(ROOT/'assets/app.ico',sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
print('Created app.ico')
