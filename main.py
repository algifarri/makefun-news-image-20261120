#!/usr/bin/env python3
"""Draw one newspaper-style poster that sums up the world news of
Friday 20 November 2026, and write it to /output/entry.png.

Pure standard library: a small RGB framebuffer, a hand-drawn 5x7 bitmap
font, flat-shaded editorial scenes for each story, and a manual PNG
encoder (zlib + struct). No network, no randomness: two runs of this
program write byte-identical files.

The day's stories, as reported on 20 November 2026:
  * HERO - Grand Theft Auto VI smashes launch records: Sensor Tower
    estimates 19.05 million copies and about $1.84 billion by launch
    day (Reuters / GameSpot, Nov 19), streams peak at 7.91 million
    concurrent viewers and 125 million hours watched in 24 hours,
    and internet exchange traffic hits a record 33.03 Tbps (DE-CIX).
  * Donald Trump says he is in no rush on Iran: no decision on new
    strikes until after January 1, "we will see what happens",
    told to Reuters, Axios and Fox News on his flight home from
    China (Reuters, Nov 19-20).
  * Cyclone Akvan makes landfall on India's east coast at noon on
    Friday 20 November, winds 90-100 kmph gusting to 110, with
    more than 100,000 people evacuated in Odisha (IMD / Jagran Josh).
  * A Houthi missile damages Riyadh's PIF Tower, the 80-storey
    headquarters of Saudi Arabia's sovereign wealth fund: windows
    blown out across seven to eight floors, no injuries, the second
    strike on the financial district in eleven days (Reuters / AFP).
  * Anthropic surges in its market debut, the AI maker's blockbuster
    first day of trading after pricing its IPO (Reuters, Nov 19).
  * Ticker: the UK to send Ukraine 1,000+ long-range strike drones;
    Fiji declares a national state of disaster over drought;
    South Korea's top court sends ex-PM Han Duck-soo's case back.
"""

import math
import os
import struct
import zlib

W = 1024
H = 1024

# ------------------------------------------------------------------ colours
PAPER = (247, 242, 228)
INK = (24, 24, 28)
FAINT = (120, 112, 96)
RULE = (24, 24, 28)
SKY = (168, 205, 232)
SKY_DEEP = (110, 160, 205)
SEA = (38, 96, 150)
SEA_DEEP = (26, 70, 116)
SAND = (232, 205, 150)
LAND = (106, 142, 74)
FIRE = (238, 110, 32)
FIRE_CORE = (250, 196, 60)
SMOKE = (105, 105, 110)
SMOKE_LT = (165, 165, 170)
RED = (178, 34, 44)
BLUE = (40, 70, 160)
GOLD = (214, 164, 40)
WHITE = (250, 250, 248)
TICKER_BG = (24, 24, 28)
TICKER_FG = (247, 242, 228)
SPACE = (10, 12, 34)
SPACE_LT = (32, 40, 80)
NEON_PINK = (255, 80, 160)
NEON_ORANGE = (255, 140, 40)
NEON_PURPLE = (120, 60, 180)
VICE_TEAL = (40, 190, 180)
STORM = (52, 72, 96)
STORM_LT = (120, 140, 168)
GREEN = (34, 160, 90)

FB = bytearray(W * H * 3)
CLIP = None  # (x0, y0, x1, y1) while a scene is painting, else None


def put(x, y, c):
    if CLIP is not None and not (CLIP[0] <= x < CLIP[2] and CLIP[1] <= y < CLIP[3]):
        return
    if 0 <= x < W and 0 <= y < H:
        i = (y * W + x) * 3
        FB[i] = c[0]
        FB[i + 1] = c[1]
        FB[i + 2] = c[2]


def fill_rect(x, y, w, h, c):
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            put(xx, yy, c)


def disc(cx, cy, r, c):
    r2 = r * r
    for yy in range(cy - r, cy + r + 1):
        for xx in range(cx - r, cx + r + 1):
            if (xx - cx) * (xx - cx) + (yy - cy) * (yy - cy) <= r2:
                put(xx, yy, c)


def half_disc_up(cx, cy, r, c):
    """Filled dome: the top half of a disc sitting on the line y=cy."""
    r2 = r * r
    for yy in range(cy - r, cy + 1):
        for xx in range(cx - r, cx + r + 1):
            if (xx - cx) * (xx - cx) + (yy - cy) * (yy - cy) <= r2:
                put(xx, yy, c)


def stroke(x0, y0, x1, y1, wdt, c):
    """Thick line: walk the segment and stamp a small disc at each step."""
    steps = max(abs(x1 - x0), abs(y1 - y0), 1)
    rad = max(wdt // 2, 0)
    for i in range(steps + 1):
        x = x0 + (x1 - x0) * i // steps
        y = y0 + (y1 - y0) * i // steps
        if rad == 0:
            put(x, y, c)
        else:
            disc(x, y, rad, c)


def poly(points, c):
    """Scanline fill of a simple polygon."""
    ys = [p[1] for p in points]
    n = len(points)
    for y in range(min(ys), max(ys) + 1):
        hits = []
        for i in range(n):
            xa, ya = points[i]
            xb, yb = points[(i + 1) % n]
            if ya == yb:
                continue
            if (ya <= y < yb) or (yb <= y < ya):
                hits.append(xa + (y - ya) * (xb - xa) // (yb - ya))
        hits.sort()
        for i in range(0, len(hits) - 1, 2):
            for x in range(hits[i], hits[i + 1] + 1):
                put(x, y, c)


def frame(x, y, w, h, c, t=3):
    fill_rect(x, y, w, t, c)
    fill_rect(x, y + h - t, w, t, c)
    fill_rect(x, y, t, h, c)
    fill_rect(x + w - t, y, t, h, c)


# ------------------------------------------------------------------ font
# 5x7 bitmap glyphs, seven rows of five pixels, '#' lit. Uppercase only:
# the poster speaks in headlines.
FONT = {
    "A": (".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "B": ("####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."),
    "C": (".####", "#....", "#....", "#....", "#....", "#....", ".####"),
    "D": ("####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."),
    "E": ("#####", "#....", "#....", "####.", "#....", "#....", "#####"),
    "F": ("#####", "#....", "#....", "####.", "#....", "#....", "#...."),
    "G": (".####", "#....", "#....", "#.###", "#...#", "#...#", ".###."),
    "H": ("#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "I": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "#####"),
    "J": ("..###", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."),
    "K": ("#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"),
    "L": ("#....", "#....", "#....", "#....", "#....", "#....", "#####"),
    "M": ("#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"),
    "N": ("#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#", "#...#"),
    "O": (".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "P": ("####.", "#...#", "#...#", "####.", "#....", "#....", "#...."),
    "Q": (".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"),
    "R": ("####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"),
    "S": (".####", "#....", "#....", ".###.", "....#", "....#", "####."),
    "T": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."),
    "U": ("#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "V": ("#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."),
    "W": ("#...#", "#...#", "#...#", "#.#.#", "#.#.#", "##.##", "#...#"),
    "X": ("#...#", ".#.#.", "..#..", "..#..", "..#..", ".#.#.", "#...#"),
    "Y": ("#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."),
    "Z": ("#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"),
    "0": (".###.", "#..##", "#.#.#", "##..#", "#...#", "#...#", ".###."),
    "1": ("..#..", ".##..", "..#..", "..#..", "..#..", "..#..", "#####"),
    "2": (".###.", "#...#", "....#", "..##.", ".#...", "#....", "#####"),
    "3": ("####.", "....#", "....#", ".###.", "....#", "....#", "####."),
    "4": ("...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."),
    "5": ("#####", "#....", "####.", "....#", "....#", "#...#", ".###."),
    "6": (".###.", "#....", "#....", "####.", "#...#", "#...#", ".###."),
    "7": ("#####", "....#", "...#.", "..#..", "..#..", "..#..", "..#.."),
    "8": (".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."),
    "9": (".###.", "#...#", "#...#", ".####", "....#", "....#", ".###."),
    " ": (".....", ".....", ".....", ".....", ".....", ".....", "....."),
    ".": (".....", ".....", ".....", ".....", ".....", ".##..", ".##.."),
    ",": (".....", ".....", ".....", ".....", ".##..", ".##..", ".#..."),
    ";": (".....", ".##..", ".##..", ".....", ".##..", ".##..", ".#..."),
    ":": (".....", ".##..", ".##..", ".....", ".##..", ".##..", "....."),
    "-": (".....", ".....", ".....", "#####", ".....", ".....", "....."),
    "'": (".##..", ".##..", ".#...", ".....", ".....", ".....", "....."),
    "!": ("..#..", "..#..", "..#..", "..#..", "..#..", ".....", "..#.."),
    "?": (".###.", "#...#", "....#", "..##.", "..#..", ".....", "..#.."),
    "/": ("....#", "....#", "...#.", "..#..", ".#...", "#....", "#...."),
    "(": ("..##.", ".#...", "#....", "#....", "#....", ".#...", "..##."),
    ")": (".##..", "...#.", "....#", "....#", "....#", "...#.", ".##.."),
    "+": (".....", "..#..", "..#..", "#####", "..#..", "..#..", "....."),
    "&": (".##..", "#..#.", "#.#..", ".#...", "#.#.#", "#..#.", ".##.#"),
    "$": ("..#..", ".####", "#.#.#", ".###.", "..#.#", "####.", "..#.."),
    "%": ("##..#", "##.#.", "...#.", "..#..", ".#...", "#.##.", "#..##"),
    "€": (".####", "#....", "####.", "#....", "####.", "#....", ".####"),
}


def text_w(s, scale):
    return len(s) * 6 * scale - scale


def draw_text(s, x, y, scale, c, bold=False):
    """Draw string s with its top-left corner at (x, y)."""
    cx = x
    for ch in s.upper():
        glyph = FONT.get(ch, FONT[" "])
        for row in range(7):
            bits = glyph[row]
            for col in range(5):
                if bits[col] == "#":
                    fill_rect(cx + col * scale, y + row * scale,
                              scale, scale, c)
                    if bold:
                        fill_rect(cx + col * scale + scale // 2,
                                  y + row * scale, scale, scale, c)
        cx += 6 * scale
    return cx


def text_c(s, cx, y, scale, c, bold=False):
    """Draw string s centred on cx."""
    return draw_text(s, cx - text_w(s, scale) // 2, y, scale, c, bold)


def text_l(s, x, y, scale, c, bold=False):
    return draw_text(s, x, y, scale, c, bold)


# ------------------------------------------------------------------ scenes
def scene_gta(x, y, w, h):
    """Vice City at sunset: a neon sun over a waterfront skyline."""
    # sunset sky in flat bands
    fill_rect(x, y, w, h // 4, NEON_PURPLE)
    fill_rect(x, y + h // 4, w, h // 4, NEON_PINK)
    fill_rect(x, y + h // 2, w, h // 4, NEON_ORANGE)
    fill_rect(x, y + (3 * h) // 4, w, h - (3 * h) // 4, (40, 20, 60))
    # the big setting sun, high enough to clear the skyline
    disc(x + int(w * 0.62), y + 30, 32, FIRE_CORE)
    disc(x + int(w * 0.62), y + 30, 21, (255, 220, 120))
    # skyline silhouettes, two rows of towers
    for i, bh in enumerate((64, 78, 92, 70, 98, 80, 62, 86)):
        bx = x + 12 + i * (w - 24) // 8
        bw = (w - 24) // 8 - 8
        fill_rect(bx, y + (3 * h) // 4 - bh, bw, bh, (30, 16, 48))
        for wy in range(5):
            for wx in range(3):
                if (i * 2 + wy + wx) % 3 == 0:
                    fill_rect(bx + 5 + wx * 9, y + (3 * h) // 4 - bh + 10 + wy * 13,
                              4, 6, GOLD)
    # water strip with a bright reflection under the sun
    sea_y = y + (3 * h) // 4
    fill_rect(x, sea_y, w, y + h - sea_y, SEA_DEEP)
    for i in range(7):
        stroke(x + w // 2 - 60 + i * 6, sea_y + 8 + i * 4,
               x + w // 2 + 60 - i * 6, sea_y + 8 + i * 4, 3, FIRE_CORE)
    # palm trees framing the scene
    for px, flip in ((x + 26, 1), (x + w - 26, -1)):
        stroke(px, sea_y - 4, px + 4 * flip, sea_y - 44, 4, (30, 60, 30))
        for k in range(5):
            ang = math.pi * (0.15 + k * 0.18)
            ex = px + int(30 * math.cos(ang) * flip)
            ey = sea_y - 44 - int(14 * math.sin(ang))
            stroke(px + 4 * flip, sea_y - 44, ex, ey, 3, (34, 110, 60))
    # a low sports car speeding along the waterfront road
    cy = sea_y - 12
    poly([(x + w // 2 - 52, cy), (x + w // 2 - 34, cy - 12),
          (x + w // 2 + 18, cy - 12), (x + w // 2 + 52, cy)], NEON_PINK)
    fill_rect(x + w // 2 - 52, cy, 104, 8, (20, 10, 30))
    disc(x + w // 2 - 34, cy + 8, 7, INK)
    disc(x + w // 2 + 34, cy + 8, 7, INK)
    disc(x + w // 2 + 48, cy - 2, 3, GOLD)  # headlight


def scene_iran(x, y, w, h):
    """Air Force One in flight beside a calendar page marked 2027."""
    fill_rect(x, y, w, h, (168, 200, 230))
    # a long white contrail curving behind the plane
    for i in range(9):
        cx = x + 16 + i * 14
        cy = y + 58 - i * 2
        disc(cx, cy, 5 + i, WHITE)
    # clouds drifting past
    for cx, cy, r in ((x + 66, y + 12, 11), (x + 84, y + 18, 8),
                      (x + w - 64, y + 10, 10), (x + w - 46, y + 17, 7)):
        disc(cx, cy, r, WHITE)
    # the plane, nose right, with two engines under the wing
    px, py = x + 52, y + 40
    fill_rect(px, py, 148, 13, WHITE)
    poly([(px + 148, py), (px + 180, py + 6), (px + 148, py + 13)], WHITE)
    poly([(px + 16, py), (px + 32, py - 15), (px + 44, py)], BLUE)
    poly([(px + 82, py + 13), (px + 100, py + 28), (px + 116, py + 13)],
         (204, 216, 232))
    fill_rect(px, py + 9, 148, 4, BLUE)
    for wx in range(7):
        fill_rect(px + 16 + wx * 19, py + 3, 9, 5, SKY_DEEP)
    fill_rect(px + 56, py + 16, 14, 7, (120, 130, 140))
    fill_rect(px + 128, py + 16, 14, 7, (120, 130, 140))
    # calendar page at bottom right, torn off at the new year
    cal_x, cal_y = x + w - 150, y + h - 60
    fill_rect(cal_x, cal_y, 130, 52, WHITE)
    frame(cal_x, cal_y, 130, 52, INK, 2)
    fill_rect(cal_x, cal_y, 130, 15, RED)
    draw_text("2027", cal_x + 46, cal_y + 21, 2, INK, bold=True)
    draw_text("JAN 1", cal_x + 42, cal_y + 37, 2, RED, bold=True)
    # a pocket watch at bottom left, hands pointing to next year
    cx, cy = x + 50, y + h - 28
    disc(cx, cy, 19, WHITE)
    disc(cx, cy, 19, WHITE)
    stroke(cx, cy, cx, cy - 14, 3, INK)
    stroke(cx, cy, cx + 10, cy - 7, 3, INK)
    disc(cx, cy, 3, RED)
    stroke(cx + 14, cy + 14, cx + 22, cy + 20, 2, GOLD)


def scene_cyclone(x, y, w, h):
    """A cyclone swirl seen from above, over a storm-tossed coast."""
    fill_rect(x, y, w, h, STORM)
    # the spiral: arcs winding inwards, storm-grey and white
    cx, cy = x + w // 2 + 40, y + h // 2 - 4
    for r, c in ((38, STORM_LT), (30, WHITE), (23, STORM),
                 (16, STORM_LT), (10, WHITE)):
        for a in range(0, 360, 8):
            ang = math.radians(a)
            px = cx + int(r * math.cos(ang))
            py = cy + int(r * math.sin(ang) * 0.8)
            disc(px, py, 3, c)
    disc(cx, cy, 5, (240, 220, 180))  # the calm eye
    # slanting rain across the whole panel
    for i in range(16):
        rx = x + 10 + (i * 29) % (w - 18)
        ry = y + 4 + (i * 19) % (h - 28)
        stroke(rx, ry, rx - 9, ry + 13, 2, (205, 218, 232))
    # waves along the bottom
    sea_y = y + h - 15
    fill_rect(x, sea_y, w, y + h - sea_y, SEA_DEEP)
    for i in range(6):
        stroke(x + 10 + i * 72, sea_y + 5, x + 50 + i * 72, sea_y + 5, 3,
               WHITE)
        stroke(x + 30 + i * 72, sea_y + 10, x + 62 + i * 72, sea_y + 10, 2,
               (180, 205, 230))
    # a small coastal house with a roof, braced against the storm
    hx, hy = x + 24, sea_y - 24
    fill_rect(hx, hy, 32, 24, (212, 192, 162))
    poly([(hx - 4, hy), (hx + 16, hy - 13), (hx + 36, hy)], RED)
    fill_rect(hx + 12, hy + 10, 8, 14, (90, 70, 50))


def scene_tower(x, y, w, h):
    """The PIF Tower in Riyadh, smoke curling from damaged floors."""
    fill_rect(x, y, w, h, (236, 192, 146))  # dusk sky
    disc(x + w - 44, y + 20, 13, FIRE_CORE)  # low sun
    # neighbouring low blocks
    fill_rect(x + 12, y + h - 32, 54, 32, (118, 108, 98))
    fill_rect(x + w - 66, y + h - 24, 54, 24, (118, 108, 98))
    # the tower itself, tapering towards the top
    tx = x + w // 2 - 32
    poly([(tx, y + h), (tx + 9, y + 4), (tx + 55, y + 4), (tx + 64, y + h)],
         (94, 140, 188))
    # window grid, lit in the dusk
    for row in range(10):
        wy = y + 10 + row * 7
        for col in range(5):
            wx = tx + 13 + col * 10
            fill_rect(wx, wy, 6, 4, (208, 224, 238))
    # damaged floors: shattered windows and smoke above them
    for row in (3, 4, 5):
        wy = y + 10 + row * 7
        for col in range(5):
            fill_rect(tx + 13 + col * 10, wy, 6, 4, (38, 28, 24))
    disc(tx + 22, y + 6, 10, SMOKE_LT)
    disc(tx + 38, y + 1, 8, SMOKE)
    disc(tx + 50, y + 8, 7, SMOKE_LT)
    # ground line
    fill_rect(x, y + h - 4, w, 4, INK)


def scene_market(x, y, w, h):
    """A stock chart climbing steeply on debut day."""
    fill_rect(x, y, w, h, (16, 32, 26))
    # faint grid
    for gy in range(3):
        fill_rect(x + 8, y + 14 + gy * 22, w - 16, 1, (40, 70, 56))
    # candlesticks rising left to right
    for i, (bh, top) in enumerate(((12, 50), (18, 42), (14, 38), (24, 28),
                                   (20, 22), (28, 12))):
        bx = x + 24 + i * 60
        fill_rect(bx, y + top, 24, bh, GREEN if i % 2 == 0 else (92, 202, 132))
        stroke(bx + 12, y + top - 7, bx + 12, y + top + bh + 7, 2,
               GREEN if i % 2 == 0 else (92, 202, 132))
    # the climbing line with an arrowhead
    pts = [(x + 22, y + 60), (x + 84, y + 52), (x + 146, y + 54),
           (x + 208, y + 38), (x + 270, y + 42), (x + 332, y + 24),
           (x + 394, y + 28), (x + w - 26, y + 8)]
    for a, b in zip(pts, pts[1:]):
        stroke(a[0], a[1], b[0], b[1], 4, (120, 230, 160))
    ax, ay = pts[-1]
    poly([(ax, ay), (ax - 16, ay - 2), (ax - 8, ay + 10)], (120, 230, 160))
    # opening bell at bottom left
    bx, by = x + 30, y + h - 22
    half_disc_up(bx, by, 12, GOLD)
    fill_rect(bx - 14, by, 28, 3, GOLD)


# ------------------------------------------------------------------ layout
def panel(x, y, w, h, scene, head_lines, detail_lines, accent):
    """One story panel: a scene, a bold headline, and a detail line."""
    global CLIP
    fill_rect(x, y, w, h, PAPER)
    frame(x, y, w, h, INK, 3)
    fill_rect(x, y, w, 10, accent)
    fill_rect(x, y + 10, w, 2, INK)
    CLIP = (x + 3, y + 3, x + w - 3, y + h - 3)
    scene(x + 10, y + 18, w - 20, 80)
    CLIP = None
    ty = y + 106
    for ln in head_lines:
        text_c(ln, x + w // 2, ty, 3, INK, bold=True)
        ty += 25
    ty += 2
    for ln in detail_lines:
        text_c(ln, x + w // 2, ty, 2, (70, 64, 54))
        ty += 17


def compose():
    """Lay out the whole front page: masthead, hero, four panels, ticker."""
    global CLIP
    fill_rect(0, 0, W, H, PAPER)

    # ---- masthead: name, weekday, date, double rule
    masthead = [
        ("WORLD NEWS SUMMARY", 3, FAINT, False),
        ("FRIDAY", 7, INK, True),
        ("20 NOVEMBER 2026", 9, RED, True),
    ]
    my = 18
    for text, scale, colour, bold in masthead:
        text_c(text, W // 2, my, scale, colour, bold=bold)
        my += 28 if scale == 3 else (58 if scale == 7 else 62)
    fill_rect(28, 176, W - 56, 5, RULE)
    fill_rect(28, 186, W - 56, 2, RULE)

    # ---- hero: GTA VI smashes launch records
    hx, hy, hw, hh = 28, 196, W - 56, 284
    frame(hx, hy, hw, hh, INK, 3)
    CLIP = (hx + 3, hy + 3, hx + hw - 3, hy + hh - 3)
    scene_gta(hx + 8, hy + 8, hw - 16, 150)
    CLIP = None
    fill_rect(hx + 60, hy + 162, hw - 120, 3, GOLD)
    hero_lines = [
        ("GTA VI: $1.84BN IN A DAY", 4, INK, True),
        ("19M COPIES SOLD, ESTIMATES SAY;", 3, (70, 64, 54), False),
        ("7.9M WATCH AT ONCE AS THE INTERNET BREAKS", 3, (70, 64, 54),
         False),
    ]
    hyy = hy + 172
    for text, scale, colour, bold in hero_lines:
        text_c(text, W // 2, hyy, scale, colour, bold=bold)
        hyy += 38 if scale == 4 else 28

    # ---- four panels, two by two, from a data table
    pw = (W - 56 - 14) // 2
    ph = 210
    py1 = 492
    py2 = py1 + ph + 10
    panels = [
        (28, py1, scene_iran,
         ["TRUMP: NO IRAN CALL", "UNTIL NEXT YEAR"],
         ["WE WILL SEE WHAT HAPPENS", "AFTER JANUARY 1"], BLUE),
        (28 + pw + 14, py1, scene_cyclone,
         ["CYCLONE AKVAN HITS", "ODISHA COAST"],
         ["LANDFALL AT NOON FRIDAY", "100,000+ EVACUATED"], STORM_LT),
        (28, py2, scene_tower,
         ["MISSILE HITS RIYADH", "SKYSCRAPER"],
         ["PIF TOWER DAMAGED,", "NO INJURIES REPORTED"], GOLD),
        (28 + pw + 14, py2, scene_market,
         ["ANTHROPIC SOARS", "ON MARKET DEBUT"],
         ["AI MAKER'S BLOCKBUSTER", "FIRST DAY OF TRADING"], GREEN),
    ]
    for px, py, scene, heads, details, accent in panels:
        panel(px, py, pw, ph, scene, heads, details, accent)

    # ---- ticker: the rest of the day in three lines
    ty = py2 + ph + 12
    fill_rect(28, ty, W - 56, H - ty - 12, TICKER_BG)
    ticker = [
        ("UK TO SEND 1,000+ LONG-RANGE DRONES TO UKRAINE", 3, TICKER_FG,
         True),
        ("FIJI DECLARES DROUGHT DISASTER", 3, TICKER_FG, False),
        ("S. KOREA COURT SENDS EX-PM HAN CASE BACK", 2, (196, 188, 168),
         False),
    ]
    tyy = [ty + 7, ty + 34, ty + 60]
    for (text, scale, colour, bold), yy in zip(ticker, tyy):
        text_c(text, W // 2, yy, scale, colour, bold=bold)


def png_bytes():
    raw = bytearray()
    row = W * 3
    for y in range(H):
        raw.append(0)
        raw += FB[y * row:(y + 1) * row]

    def chunk(tag, data):
        out = struct.pack(">I", len(data)) + tag + data
        out += struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        return out

    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + chunk(b"IEND", b""))


def main():
    compose()
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "entry.png")
    with open(path, "wb") as fh:
        fh.write(png_bytes())
    print("wrote", path)


if __name__ == "__main__":
    main()
