"""Rasterize the application's simple geometric compass icon for Windows."""
from pathlib import Path
from PIL import Image, ImageDraw

root = Path(__file__).resolve().parents[1]
scale = 4
image = Image.new('RGBA', (256*scale, 256*scale))
draw = ImageDraw.Draw(image)
def box(values): return tuple(v*scale for v in values)
draw.rounded_rectangle(box((8,8,248,248)), radius=58*scale, fill='#5453d7')
draw.ellipse(box((49,49,207,207)), outline='white', width=12*scale)
points = [(159,92),(141,141),(92,159),(110,110),(159,92)]
draw.line([(x*scale,y*scale) for x,y in points], fill='white', width=12*scale, joint='curve')
draw.ellipse(box((123,123,133,133)), fill='white')
image.resize((256,256), Image.Resampling.LANCZOS).save(root/'assets/app.ico', sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
