# Rebuild the transparent animated avatar from bot.gif.
# Removes ONLY the white that's connected to the frame border (flood fill from
# the edges) so interior whites — the eyes — are preserved. Earlier versions
# chroma-keyed every white pixel, which punched a hole in the right eye.
from PIL import Image, ImageDraw, ImageFilter
import numpy as np

SRC = "/Users/hayden/Downloads/bot.gif"
OUT = "bot.webp"
SENTINEL = (255, 0, 255)
THRESH = 42
SIZE = 300

src = Image.open(SRC)
n = getattr(src, "n_frames", 1)
frames = []
durations = []

for i in range(n):
    src.seek(i)
    rgb = src.convert("RGB").copy()
    w, h = rgb.size
    seeds = [
        (0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1),
        (w // 2, 0), (w // 2, h - 1), (0, h // 2), (w - 1, h // 2),
    ]
    for s in seeds:
        ImageDraw.floodfill(rgb, s, SENTINEL, thresh=THRESH)
    arr = np.array(rgb)
    bg = (arr[:, :, 0] == 255) & (arr[:, :, 1] == 0) & (arr[:, :, 2] == 255)

    alpha = np.where(bg, 0, 255).astype("uint8")
    alpha_img = Image.fromarray(alpha)
    # pull the opaque edge in by 1px to drop the white anti-aliased fringe
    alpha_img = alpha_img.filter(ImageFilter.MinFilter(3))

    rgba = src.convert("RGB").convert("RGBA")
    rgba.putalpha(alpha_img)
    rgba = rgba.resize((SIZE, SIZE), Image.LANCZOS)
    frames.append(rgba)
    durations.append(src.info.get("duration", 60))

frames[0].save(
    OUT,
    save_all=True,
    append_images=frames[1:],
    duration=durations,
    loop=0,
    format="WEBP",
    method=6,
    quality=86,
    minimize_size=True,
)
print(f"frames={len(frames)} size={SIZE} -> {OUT}")
