"""Create engineering-only illustrated placeholder frames without network/API keys.

These are NOT approved as finished EAS history illustrations. Real episodes use
individually art-directed scene illustrations from the editorial workflow.
"""
from __future__ import annotations
import math
import random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parents[1] / "examples" / "assets" / "eas"
W, H = 900, 1600
INK, RED, GOLD = (52, 44, 37), (150, 69, 45), (207, 155, 88)


def title_font(size: int):
    for name in ("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        if Path(name).exists():
            return ImageFont.truetype(name, size)
    return ImageFont.load_default()


def frame(index: int):
    random.seed(index)
    im = Image.new("RGB", (W, H))
    pix = im.load()
    for y in range(H):
        for x in range(W):
            grain = random.randint(-5, 5)
            fade = 1 - 0.14 * abs(y - H / 2) / (H / 2)
            pix[x, y] = tuple(max(0, min(255, int(a * fade + grain))) for a in (239, 209, 157))
    d = ImageDraw.Draw(im)
    for k in range(22):
        y = 80 + k * 68
        d.line((44, y, W-44, y), fill=(225, 190, 142), width=2)
    d.rectangle((25, 35, W - 25, H - 35), outline=RED, width=9)
    d.rectangle((45, 55, W - 45, H - 55), outline=(137, 94, 63), width=2)
    d.text((85, 112), "EAS  /  1888", fill=INK, font=title_font(63))
    d.line((85, 196, W - 85, 196), fill=RED, width=6)
    return im, d


def camera(d: ImageDraw.ImageDraw, ox: int = 0, oy: int = 0):
    d.polygon([(180+ox, 620+oy), (510+ox, 525+oy), (735+ox, 618+oy), (425+ox, 737+oy)], fill=(111, 76, 51))
    d.polygon([(180+ox, 620+oy), (425+ox, 737+oy), (425+ox, 1200+oy), (180+ox, 1050+oy)], fill=(82, 58, 43))
    d.polygon([(425+ox, 737+oy), (735+ox, 618+oy), (735+ox, 1070+oy), (425+ox, 1200+oy)], fill=(59, 50, 44))
    d.ellipse((472+ox, 805+oy, 694+ox, 1027+oy), fill=(162, 127, 81), outline=GOLD, width=10)
    d.ellipse((512+ox, 844+oy, 658+ox, 988+oy), fill=(34, 41, 44), outline=(213, 175, 115), width=9)
    d.ellipse((550+ox, 880+oy, 612+ox, 950+oy), fill=(64, 97, 113))
    d.ellipse((571+ox, 888+oy, 593+ox, 912+oy), fill=(190, 212, 205))
    for x, y in ((456,750),(707,658),(458,1164),(705,1060)):
        d.ellipse((x+ox-6,y+oy-6,x+ox+6,y+oy+6),fill=GOLD)


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    im, d = frame(1)
    camera(d)
    im.save(ROOT / "kodak_01.jpg", quality=85)

    im, d = frame(2)
    for row in range(5):
        for col in range(4):
            x, y = 92+col*185, 405+row*192
            d.rectangle((x,y,x+155,y+169),fill=(67,53,43),outline=GOLD,width=5)
            d.rectangle((x+19,y+17,x+137,y+147),fill=(183,139,84))
            d.ellipse((x+38,y+38,x+119,y+122),outline=(95,68,51),width=8)
    im.save(ROOT / "kodak_02.jpg", quality=85)

    im, d = frame(3)
    d.polygon([(130,615),(610,505),(777,710),(294,820)], fill=(175,122,68),outline=INK)
    d.polygon([(130,615),(294,820),(294,1200),(130,1020)], fill=(135,86,49),outline=INK)
    d.polygon([(294,820),(777,710),(777,1100),(294,1200)], fill=(191,143,86),outline=INK)
    d.line([(130,615),(294,820),(777,710)],fill=(225,195,144),width=18)
    d.rectangle((385,827,673,985),fill=(246,220,171),outline=RED,width=6)
    d.text((422,864), "U.S.", fill=INK, font=title_font(66))
    im.save(ROOT / "kodak_03.jpg", quality=85)

    im, d = frame(4)
    for i,(x,y) in enumerate(((120,400),(405,500),(155,860))):
        d.rectangle((x-10,y-10,x+310,y+390),fill=(90,65,48))
        d.rectangle((x,y,x+290,y+365),fill=(247,231,196))
        d.ellipse((x+65,y+55,x+210,y+210),fill=(128,108,87))
        d.ellipse((x+80,y+56,x+196,y+172),fill=(213,185,143))
        d.polygon([(x+70,y+280),(x+151,y+188),(x+240,y+285)],fill=(126,104,86))
    im.save(ROOT / "kodak_04.jpg", quality=85)
    print("Generated four independent engineering placeholders. Editorial approval required.")


if __name__ == "__main__":
    main()
