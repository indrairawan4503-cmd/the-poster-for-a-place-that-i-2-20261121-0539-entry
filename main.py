#!/usr/bin/env python3
"""Aerthwaite - a travel poster for a place that isn't there.

Pure Python 3.13 stdlib. Draws the poster procedurally (dusk sky gradient,
floating lantern islands chained by rope bridges, one tall lighthouse-island)
into a 1024x1024 PNG at /output/entry.png. Deterministic: fixed-seed
pseudo-randomness only, no network, no external assets, no clock.
"""
import os
import struct
import zlib

W, H = 1024, 1024
OUT = "/output/entry.png"

buf = bytearray(W * H * 3)


# ---------------------------------------------------------------- pixels
def set_px(x, y, color, alpha=1.0):
    if 0 <= x < W and 0 <= y < H:
        i = (y * W + x) * 3
        if alpha >= 1.0:
            buf[i], buf[i + 1], buf[i + 2] = color
        else:
            buf[i] = int(buf[i] + (color[0] - buf[i]) * alpha)
            buf[i + 1] = int(buf[i + 1] + (color[1] - buf[i + 1]) * alpha)
            buf[i + 2] = int(buf[i + 2] + (color[2] - buf[i + 2]) * alpha)


def lerp(a, b, t):
    return a + (b - a) * t


def mix(c1, c2, t):
    return (int(round(lerp(c1[0], c2[0], t))),
            int(round(lerp(c1[1], c2[1], t))),
            int(round(lerp(c1[2], c2[2], t))))


def fill_rect(x0, y0, x1, y1, color, alpha=1.0):
    for y in range(max(0, y0), min(H, y1 + 1)):
        for x in range(max(0, x0), min(W, x1 + 1)):
            set_px(x, y, color, alpha)


def fill_circle(cx, cy, r, color, alpha=1.0):
    for y in range(cy - r, cy + r + 1):
        for x in range(cx - r, cx + r + 1):
            if (x - cx) * (x - cx) + (y - cy) * (y - cy) <= r * r:
                set_px(x, y, color, alpha)


def fill_ellipse(cx, cy, rx, ry, color, alpha=1.0):
    for y in range(cy - ry, cy + ry + 1):
        for x in range(cx - rx, cx + rx + 1):
            if ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.0:
                set_px(x, y, color, alpha)


def fill_poly(pts, color, alpha=1.0):
    ys = [p[1] for p in pts]
    ymin, ymax = max(0, min(ys)), min(H - 1, max(ys))
    n = len(pts)
    for y in range(ymin, ymax + 1):
        xs = []
        for i in range(n):
            x1, y1 = pts[i]
            x2, y2 = pts[(i + 1) % n]
            if y1 == y2:
                continue
            if min(y1, y2) <= y < max(y1, y2):
                xs.append(x1 + (y - y1) * (x2 - x1) / (y2 - y1))
        xs.sort()
        for i in range(0, len(xs) - 1, 2):
            for x in range(max(0, int(xs[i])), min(W - 1, int(xs[i + 1])) + 1):
                set_px(x, y, color, alpha)


def draw_line(x0, y0, x1, y1, color, width=1, alpha=1.0):
    steps = max(abs(x1 - x0), abs(y1 - y0), 1)
    r = max(1, width // 2)
    for i in range(steps + 1):
        t = i / steps
        x = int(round(lerp(x0, x1, t)))
        y = int(round(lerp(y0, y1, t)))
        fill_circle(x, y, r, color, alpha)


def quad_bezier(p0, p1, p2, t):
    x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0]
    y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]
    return (x, y)


# ------------------------------------------------------- deterministic rng
_seed = 20261121


def rnd():
    global _seed
    _seed = (_seed * 1103515245 + 12345) & 0x7FFFFFFF
    return _seed / 0x7FFFFFFF


# ------------------------------------------------------------------ font
# 5x7 bitmap glyphs, written out by hand for this poster.
FONT = {
    'A': ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    'B': ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    'C': ("01110", "10001", "10000", "10000", "10000", "10001", "01110"),
    'D': ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    'E': ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    'F': ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    'G': ("01110", "10001", "10000", "10111", "10001", "10001", "01111"),
    'H': ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    'I': ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    'J': ("00111", "00010", "00010", "00010", "00010", "10010", "01100"),
    'K': ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    'L': ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    'M': ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    'N': ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    'O': ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    'P': ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    'Q': ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    'R': ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    'S': ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    'T': ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    'U': ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    'V': ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    'W': ("10001", "10001", "10001", "10101", "10101", "11011", "10001"),
    'X': ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    'Y': ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    'Z': ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    ' ': ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
    '-': ("00000", "00000", "00000", "01110", "00000", "00000", "00000"),
    '.': ("00000", "00000", "00000", "00000", "00000", "01100", "01100"),
    "'": ("00100", "00100", "01000", "00000", "00000", "00000", "00000"),
}


def text_width(s, scale):
    return len(s) * 6 * scale - scale


def draw_text(s, x, y, scale, color):
    cx = x
    for ch in s:
        glyph = FONT.get(ch, FONT[' '])
        for row in range(7):
            bits = glyph[row]
            for col in range(5):
                if bits[col] == '1':
                    fill_rect(cx + col * scale, y + row * scale,
                              cx + col * scale + scale - 1,
                              y + row * scale + scale - 1, color)
        cx += 6 * scale


# --------------------------------------------------------------- scenery
SKY_STOPS = [
    (0, (6, 30, 38)),
    (260, (12, 52, 62)),
    (520, (18, 80, 90)),
    (640, (38, 100, 104)),
    (700, (150, 110, 70)),
    (760, (70, 100, 96)),
    (880, (24, 58, 64)),
    (1024, (8, 32, 40)),
]


def sky_color(y):
    for i in range(len(SKY_STOPS) - 1):
        y0, c0 = SKY_STOPS[i]
        y1, c1 = SKY_STOPS[i + 1]
        if y0 <= y <= y1:
            return mix(c0, c1, (y - y0) / (y1 - y0))
    return SKY_STOPS[-1][1]


def draw_sky():
    for y in range(H):
        c = sky_color(y)
        i = y * W * 3
        buf[i:(y + 1) * W * 3] = bytes(c) * W


def draw_stars():
    for _ in range(140):
        x = int(rnd() * W)
        y = int(rnd() * 430)
        b = rnd()
        col = (255, 250, 230) if b > 0.85 else (210, 230, 230)
        if b > 0.92:
            fill_circle(x, y, 2, col, 0.9)
        else:
            set_px(x, y, col, 0.55 + 0.4 * b)


def draw_moon():
    fill_circle(905, 100, 44, (246, 232, 196))
    fill_circle(890, 88, 9, (224, 206, 168))
    fill_circle(918, 116, 6, (224, 206, 168))
    fill_circle(906, 74, 5, (224, 206, 168))
    for r, a in ((66, 0.10), (54, 0.14)):
        fill_circle(905, 100, r, (250, 235, 190), a)


def draw_birds():
    for (x, y, s) in ((300, 250, 9), (352, 228, 7), (700, 300, 8), (742, 278, 6)):
        draw_line(x - s, y, x, y + 4, (16, 44, 52), 2)
        draw_line(x, y + 4, x + s, y, (16, 44, 52), 2)


def draw_cloud_sea():
    # layered soft cloud banks along the bottom third
    for (cx, cy, rx, ry, col, a) in (
            (180, 900, 260, 46, (96, 128, 128), 0.55),
            (520, 930, 320, 52, (110, 140, 138), 0.55),
            (860, 905, 280, 48, (96, 128, 128), 0.55),
            (330, 965, 300, 50, (70, 102, 104), 0.7),
            (700, 975, 330, 52, (70, 102, 104), 0.7),
            (120, 995, 240, 44, (52, 84, 88), 0.8),
            (900, 1000, 260, 44, (52, 84, 88), 0.8),
            (512, 1010, 420, 40, (40, 70, 74), 0.85),
    ):
        fill_ellipse(cx, cy, rx, ry, col, a)
    # warm tint where the dusk light catches the clouds
    fill_ellipse(512, 880, 420, 26, (214, 150, 84), 0.18)


def island(cx, top, w, depth, grass=(38, 96, 66), grass_hi=(52, 122, 82),
           rock=(72, 60, 50), rock_dark=(52, 44, 38)):
    half = w // 2
    pts = [(cx - half, top), (cx + half, top),
           (cx + half - 18, top + depth // 3),
           (cx + half // 2, top + 2 * depth // 3),
           (cx + 10, top + depth - 14), (cx - 8, top + depth),
           (cx - half // 2 - 6, top + 2 * depth // 3),
           (cx - half + 14, top + depth // 3)]
    fill_poly(pts, rock)
    shade = [(cx - half + 14, top + depth // 3),
             (cx + half - 18, top + depth // 3),
             (cx + half // 2, top + 2 * depth // 3),
             (cx + 10, top + depth - 14), (cx - 8, top + depth),
             (cx - half // 2 - 6, top + 2 * depth // 3)]
    fill_poly(shade, rock_dark, 0.45)
    fill_ellipse(cx, top, half, 13, grass)
    fill_ellipse(cx, top - 2, half, 9, grass_hi)


def lantern(x, y, s=1.0):
    for r, a in ((26, 0.10), (19, 0.16), (13, 0.28)):
        fill_circle(x, y, int(r * s), (255, 180, 70), a)
    w = int(11 * s)
    h = int(15 * s)
    fill_rect(x - w, y - h // 2, x + w, y + h // 2, (255, 176, 66))
    fill_rect(x - w, y - h // 2, x + w, y - h // 2 + 2, (214, 120, 40))
    fill_rect(x - w, y + h // 2 - 2, x + w, y + h // 2, (214, 120, 40))
    fill_rect(x - 1, y - h // 2 - 3, x + 1, y - h // 2, (120, 70, 30))
    draw_line(x, y + h // 2, x, y + h // 2 + 6, (255, 200, 90), 1)
    fill_rect(x - w + 2, y - h // 2 + 3, x - w + 4, y + h // 2 - 3,
              (255, 220, 140))


def hanging_lantern(x, top_y, drop, s=1.0):
    draw_line(x, top_y, x, top_y + drop, (90, 70, 50), 1)
    lantern(x, top_y + drop + 8, s)


def bridge(p0, p2, sag):
    mid = ((p0[0] + p2[0]) // 2, (p0[1] + p2[1]) // 2 + sag)
    prev = None
    for i in range(41):
        pt = quad_bezier(p0, mid, p2, i / 40)
        if prev is not None:
            draw_line(int(prev[0]), int(prev[1]), int(pt[0]), int(pt[1]),
                      (122, 96, 66), 2)
        prev = pt
    for i in range(1, 20):
        pt = quad_bezier(p0, mid, p2, i / 20)
        x, y = int(pt[0]), int(pt[1])
        fill_rect(x - 4, y, x + 4, y + 3, (146, 110, 72))
    return mid


def lighthouse(cx, base_y):
    top_y = base_y - 150
    bot_w, top_w = 36, 26
    pts = [(cx - bot_w, base_y), (cx + bot_w, base_y),
           (cx + top_w, top_y), (cx - top_w, top_y)]
    fill_poly(pts, (236, 220, 184))
    # teal bands across the tapering tower
    for by in (base_y - 60, base_y - 110):
        hw = int(bot_w + (top_w - bot_w) * (base_y - by) / 150)
        fill_rect(cx - hw, by, cx + hw, by + 13, (24, 84, 92))
    # lamp room
    fill_rect(cx - 24, top_y - 26, cx + 24, top_y, (32, 34, 44))
    fill_rect(cx - 28, top_y - 30, cx + 28, top_y - 26, (20, 22, 30))
    fill_poly([(cx - 22, top_y - 30), (cx + 22, top_y - 30), (cx, top_y - 48)],
              (150, 60, 44))
    # glowing lamp
    for r, a in ((34, 0.12), (24, 0.22), (16, 0.4)):
        fill_circle(cx, top_y - 13, r, (255, 196, 90), a)
    fill_circle(cx, top_y - 13, 11, (255, 214, 120))
    # light beam sweeping right across the dusk sky
    beam = [(cx + 20, top_y - 16), (W, top_y - 64),
            (W, top_y + 12), (cx + 20, top_y - 4)]
    fill_poly(beam, (255, 214, 140), 0.18)
    beam2 = [(cx - 20, top_y - 14), (0, top_y - 44),
             (0, top_y + 6), (cx - 20, top_y - 6)]
    fill_poly(beam2, (255, 214, 140), 0.09)


def cottage(x, y):
    # small house with a lit window on the left island
    fill_rect(x, y, x + 85, y + 52, (120, 80, 60))
    fill_poly([(x - 10, y), (x + 95, y), (x + 42, y - 28)], (70, 45, 35))
    fill_rect(x + 62, y - 34, x + 74, y - 8, (90, 60, 44))
    fill_rect(x + 14, y + 16, x + 36, y + 36, (255, 200, 100))
    for r, a in ((30, 0.10), (20, 0.16)):
        fill_circle(x + 25, y + 26, r, (255, 190, 90), a)
    fill_rect(x + 52, y + 20, x + 68, y + 52, (52, 36, 28))


def pine(x, y, s):
    # y = base of the tree on the grass
    fill_rect(x - 3, y - 12 * s, x + 3, y, (70, 48, 34))
    for i, (w, h) in enumerate(((26, 26), (20, 22), (13, 18))):
        ty = y - 12 * s - i * 16 * s
        fill_poly([(x - w * s, ty), (x + w * s, ty), (x, ty - h * s)],
                  (24, 70, 50))


# ------------------------------------------------------------------ png
def write_png(path):
    raw = b"".join(b"\x00" + bytes(buf[y * W * 3:(y + 1) * W * 3])
                   for y in range(H))

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 9))
    png += chunk(b"IEND", b"")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(png)


# ------------------------------------------------------------------ main
def main():
    draw_sky()
    draw_stars()
    draw_moon()
    draw_birds()

    # hazy distant islets on the horizon
    island(250, 660, 90, 60, grass=(30, 74, 74), grass_hi=(40, 92, 90),
           rock=(52, 72, 72), rock_dark=(40, 58, 58))
    island(800, 700, 110, 66, grass=(30, 74, 74), grass_hi=(40, 92, 90),
           rock=(52, 72, 72), rock_dark=(40, 58, 58))

    draw_cloud_sea()

    # small floating islets, high in the dusk
    island(160, 350, 110, 80)
    island(870, 340, 100, 75)
    island(430, 830, 140, 90)

    # main islands
    island(190, 560, 240, 140)
    island(850, 520, 250, 170)
    island(515, 440, 380, 280)

    # the landmark: lighthouse-island
    lighthouse(515, 440)

    # cottage on the left island, pines on the right island
    cottage(140, 508)
    pine(790, 522, 1)
    pine(855, 516, 1)
    pine(915, 522, 1)
    fill_ellipse(760, 524, 26, 9, (52, 122, 82))
    fill_ellipse(930, 524, 24, 8, (52, 122, 82))

    # rope bridges between the islands
    b1 = bridge((300, 566), (335, 448), 55)
    b2 = bridge((695, 448), (735, 528), 50)

    # lanterns hanging from bridges and island edges
    for t in (0.35, 0.65):
        pt = quad_bezier((300, 566), b1, (335, 448), t)
        hanging_lantern(int(pt[0]), int(pt[1]), 14, 0.9)
    for t in (0.4, 0.7):
        pt = quad_bezier((695, 448), b2, (735, 528), t)
        hanging_lantern(int(pt[0]), int(pt[1]), 14, 0.9)
    hanging_lantern(96, 566, 16)
    hanging_lantern(272, 564, 14, 0.9)
    hanging_lantern(760, 526, 16)
    hanging_lantern(928, 524, 14, 0.9)
    hanging_lantern(380, 446, 18)
    hanging_lantern(650, 446, 16, 0.9)
    hanging_lantern(160, 356, 14, 0.85)
    hanging_lantern(870, 346, 14, 0.85)
    hanging_lantern(430, 836, 16)
    # lanterns flanking the lighthouse base
    lantern(462, 428, 0.9)
    lantern(568, 428, 0.9)

    # ---------------------------------------------------------- typography
    title = "AERTHWAITE"
    scale = 11
    tx = (W - text_width(title, scale)) // 2
    draw_text(title, tx + 5, 71, scale, (6, 28, 34))
    draw_text(title, tx, 66, scale, (255, 233, 176))

    tagline = "WHERE THE LANTERNS NEVER SLEEP"
    tscale = 3
    gx = (W - text_width(tagline, tscale)) // 2
    draw_text(tagline, gx + 2, 178, tscale, (6, 28, 34))
    draw_text(tagline, gx, 176, tscale, (255, 210, 122))

    # small rule + diamond under the tagline
    draw_line(380, 216, 500, 216, (212, 164, 90), 2)
    draw_line(524, 216, 644, 216, (212, 164, 90), 2)
    fill_poly([(512, 208), (520, 216), (512, 224), (504, 216)], (255, 210, 122))

    # thin vintage-poster frame
    fill_rect(20, 20, W - 21, 22, (212, 164, 90), 0.85)
    fill_rect(20, H - 23, W - 21, H - 21, (212, 164, 90), 0.85)
    fill_rect(20, 20, 22, H - 21, (212, 164, 90), 0.85)
    fill_rect(W - 23, 20, W - 21, H - 21, (212, 164, 90), 0.85)

    write_png(OUT)


if __name__ == "__main__":
    main()
