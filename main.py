#!/usr/bin/env python3
"""The Lighthouse That Guides Starships.

A single generative artwork, drawn procedurally with the Python standard
library only: a lone lighthouse on a cliff edge throws a warm beam up to a
giant ringed planet hanging over a night sea. No network, no external
assets, fully deterministic: the same bytes on every run.

Writes one image to $MAKEFUN_OUTPUT_DIR/entry.png (or /output/entry.png).
"""

import math
import os
import random
import struct
import zlib

W = H = 1024
SEED = 20261113

# ---------------------------------------------------------------- palette ---

SKY_STOPS = [
    (0.00, (6, 8, 30)),
    (0.38, (20, 17, 60)),
    (0.62, (52, 32, 96)),
    (0.74, (96, 52, 116)),
    (1.00, (16, 14, 42)),
]

NEBULA_A = (198, 74, 158)   # magenta
NEBULA_B = (56, 190, 214)   # teal
NEBULA_C = (110, 78, 220)   # violet

PLANET_BANDS = [
    (14, 74, 104),
    (30, 128, 160),
    (64, 182, 205),
    (140, 218, 226),
    (34, 132, 164),
    (18, 88, 122),
]
PLANET_NIGHT = (8, 20, 38)
RIM_WARM = (255, 176, 104)
RING_COL = (228, 208, 176)

BEAM_COL = (255, 186, 92)
BEAM_CORE = (255, 236, 182)

RIDGE_FAR = (38, 31, 72)
RIDGE_NEAR = (14, 12, 32)
SEA_TOP = (60, 46, 106)
SEA_BOT = (9, 13, 36)
LAMP_COL = (255, 220, 148)

# --------------------------------------------------------------- geometry ---

PLANET_CX, PLANET_CY, PLANET_R = 692, 282, 182
RING_IN, RING_OUT = 214, 336
RING_TILT = -0.34          # radians, ring plane tilt
RING_FLAT = 0.34           # minor/major axis ratio of projected ellipse

LAMP_X, LAMP_Y = 255, 568  # lighthouse lamp position
BEAM_TX, BEAM_TY = 566, 412  # beam target: planet lower-left limb
SEA_Y = 748

# ------------------------------------------------------------------ utils ---


def clamp255(v):
    if v < 0:
        return 0
    if v > 255:
        return 255
    return int(v)


def lerp(a, b, t):
    return a + (b - a) * t


def smooth(t):
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    return t * t * (3.0 - 2.0 * t)


def grad(stops, t):
    """Piecewise-linear gradient through (position, rgb) stops."""
    if t <= stops[0][0]:
        return stops[0][1]
    for i in range(1, len(stops)):
        if t <= stops[i][0]:
            t0, c0 = stops[i - 1]
            t1, c1 = stops[i]
            f = (t - t0) / (t1 - t0)
            return (lerp(c0[0], c1[0], f), lerp(c0[1], c1[1], f),
                    lerp(c0[2], c1[2], f))
    return stops[-1][1]


# ------------------------------------------------------------ value noise ---


def hash2(x, y):
    h = (x * 374761393 + y * 668265263) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    h = (h ^ (h >> 16)) & 0xFFFFFFFF
    return h / 4294967295.0


def vnoise(x, y):
    xi = int(math.floor(x))
    yi = int(math.floor(y))
    xf = x - xi
    yf = y - yi
    u = xf * xf * (3.0 - 2.0 * xf)
    v = yf * yf * (3.0 - 2.0 * yf)
    a = hash2(xi, yi)
    b = hash2(xi + 1, yi)
    c = hash2(xi, yi + 1)
    d = hash2(xi + 1, yi + 1)
    return lerp(lerp(a, b, u), lerp(c, d, u), v)


def fbm(x, y, octaves=3):
    s = 0.0
    amp = 0.5
    f = 1.0
    norm = 0.0
    for _ in range(octaves):
        s += amp * vnoise(x * f, y * f)
        norm += amp
        amp *= 0.5
        f *= 2.03
    return s / norm


# -------------------------------------------------------------- PNG writer ---


def write_png(path, w, h, rgb):
    stride = w * 3
    raw = bytearray()
    prev = bytes(stride)
    for y in range(h):
        row = bytes(rgb[y * stride:(y + 1) * stride])
        if y == 0:
            raw.append(0)
            raw += row
        else:
            raw.append(2)  # Up filter
            raw += bytes((a - b) & 0xFF for a, b in zip(row, prev))
        prev = row
    comp = zlib.compress(bytes(raw), 9)

    def chunk(typ, data):
        out = struct.pack(">I", len(data)) + typ + data
        out += struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)
        return out

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", comp)
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


# ------------------------------------------------------------ image buffer ---

img = bytearray(W * H * 3)


def blend_px(i, r, g, b, a):
    """Alpha-over blend at flat index i (byte offset)."""
    ia = 1.0 - a
    img[i] = clamp255(r * a + img[i] * ia)
    img[i + 1] = clamp255(g * a + img[i + 1] * ia)
    img[i + 2] = clamp255(b * a + img[i + 2] * ia)


def add_px(i, r, g, b, a):
    """Additive glow at flat index i."""
    img[i] = clamp255(img[i] + r * a)
    img[i + 1] = clamp255(img[i + 1] + g * a)
    img[i + 2] = clamp255(img[i + 2] + b * a)


# -------------------------------------------------------------- 1. sky -----


def paint_sky():
    for y in range(H):
        r, g, b = grad(SKY_STOPS, y / (H - 1))
        row = bytes((clamp255(r), clamp255(g), clamp255(b))) * W
        img[y * W * 3:(y + 1) * W * 3] = row


# ----------------------------------------------------------- 2. nebula ----


def paint_nebula():
    # Two coarse fields: a ridged density field (wisps) and a slow colour
    # field, both bilinearly upsampled. No hard colour boundaries anywhere.
    gw = gh = 256
    dens = [0.0] * (gw * gh)
    cols = [0.0] * (gw * gh)
    for gy in range(gh):
        for gx in range(gw):
            cols[gy * gw + gx] = fbm(gx / gw * 2.0 + 3.3, gy / gh * 2.0 + 9.1, 2)
    for gy in range(gh):
        for gx in range(gw):
            # Domain-warp the density sample by the colour field for curl.
            w = (cols[gy * gw + gx] - 0.5) * 1.6
            d = fbm(gx / gw * 4.5 + w + 11.7, gy / gh * 4.5 + w * 0.6 + 4.2, 4)
            dens[gy * gw + gx] = 1.0 - abs(2.0 * d - 1.0)
    for y in range(SEA_Y):
        fy = y / (H - 1) * (gh - 1)
        y0 = int(fy)
        y1 = y0 + 1 if y0 + 1 < gh else y0
        wy = fy - y0
        base = y * W * 3
        for x in range(W):
            fx = x / (W - 1) * (gw - 1)
            x0 = int(fx)
            x1 = x0 + 1 if x0 + 1 < gw else x0
            wx = fx - x0
            dv = lerp(lerp(dens[y0 * gw + x0], dens[y0 * gw + x1], wx),
                      lerp(dens[y1 * gw + x0], dens[y1 * gw + x1], wx), wy)
            cv = lerp(lerp(cols[y0 * gw + x0], cols[y0 * gw + x1], wx),
                      lerp(cols[y1 * gw + x0], cols[y1 * gw + x1], wx), wy)
            a = smooth((dv - 0.62) / 0.26) * 0.33
            if a <= 0.01:
                continue
            # Keep a clear halo around the planet so the disc pops.
            pdx = x - PLANET_CX
            pdy = y - PLANET_CY
            pd2 = pdx * pdx + pdy * pdy
            inner = (PLANET_R + 30) ** 2
            outer = (PLANET_R + 170) ** 2
            if pd2 < inner:
                continue
            if pd2 < outer:
                a *= smooth((math.sqrt(pd2) - (PLANET_R + 30)) / 140.0)
                if a <= 0.01:
                    continue
            # Colour drifts smoothly magenta -> violet -> teal with the field.
            t = smooth(cv * 1.4 - 0.2)
            if t < 0.5:
                c = (lerp(NEBULA_A[0], NEBULA_C[0], t * 2),
                     lerp(NEBULA_A[1], NEBULA_C[1], t * 2),
                     lerp(NEBULA_A[2], NEBULA_C[2], t * 2))
            else:
                c = (lerp(NEBULA_C[0], NEBULA_B[0], (t - 0.5) * 2),
                     lerp(NEBULA_C[1], NEBULA_B[1], (t - 0.5) * 2),
                     lerp(NEBULA_C[2], NEBULA_B[2], (t - 0.5) * 2))
            fade = 1.0 - smooth((y - SEA_Y + 260) / 260.0)
            blend_px(base + x * 3, c[0], c[1], c[2], a * fade)


# ------------------------------------------------------------- 3. stars ----


def paint_stars(rng):
    stars = []
    for _ in range(420):
        x = rng.randint(0, W - 1)
        y = rng.randint(0, SEA_Y - 40)
        # Thin the crowd near the planet so the disc stays clean.
        if (x - PLANET_CX) ** 2 + (y - PLANET_CY) ** 2 < (PLANET_R + 60) ** 2:
            if rng.random() < 0.75:
                continue
        bright = rng.randint(90, 255)
        stars.append((x, y, bright))
    for x, y, bright in stars:
        i = (y * W + x) * 3
        warm = rng.random() < 0.25
        r, g, b = (255, 226, 180) if warm else (220, 232, 255)
        a = bright / 255.0
        blend_px(i, r, g, b, a)
        if bright > 215:  # a few bright stars get a cross flare
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                xx, yy = x + dx, y + dy
                if 0 <= xx < W and 0 <= yy < H:
                    blend_px((yy * W + xx) * 3, r, g, b, a * 0.45)
    # One shooting star, upper left.
    sx, sy = 128, 138
    for t in range(120):
        x = sx + t
        y = sy + int(t * 0.42)
        if 0 <= x < W and 0 <= y < H:
            a = 0.85 * (1.0 - t / 120.0)
            blend_px((y * W + x) * 3, 255, 244, 210, a)
            if t < 8:
                blend_px((y * W + x) * 3, 255, 255, 255, 0.9)


# ------------------------------------------------------- 4. planet glow ----


def paint_planet_glow():
    R = PLANET_R * 1.5
    x0 = max(0, int(PLANET_CX - R))
    x1 = min(W, int(PLANET_CX + R) + 1)
    y0 = max(0, int(PLANET_CY - R))
    y1 = min(H, int(PLANET_CY + R) + 1)
    for y in range(y0, y1):
        dy = y - PLANET_CY
        base = y * W * 3
        for x in range(x0, x1):
            dx = x - PLANET_CX
            d = math.sqrt(dx * dx + dy * dy) / R
            if d >= 1.0:
                continue
            a = (1.0 - d) ** 2.4 * 0.24
            add_px(base + x * 3, 70, 190, 215, a)


# -------------------------------------------------------------- 5. beam ----


def paint_beam():
    ox, oy = LAMP_X, LAMP_Y
    dx = BEAM_TX - ox
    dy = BEAM_TY - oy
    length = math.hypot(dx, dy)
    ux, uy = dx / length, dy / length
    reach = length + 70  # tuck the far end under the planet's limb
    x0 = max(0, min(ox, BEAM_TX) - 110)
    x1 = min(W, max(ox, BEAM_TX) + 110)
    y0 = max(0, min(oy, BEAM_TY) - 110)
    y1 = min(H, max(oy, BEAM_TY) + 110)
    for y in range(y0, y1):
        base = y * W * 3
        for x in range(x0, x1):
            px, py = x - ox, y - oy
            t = px * ux + py * uy
            if t < 0.0 or t > reach:
                continue
            perp = abs(px * uy - py * ux)
            width = 6.0 + t * 0.16
            q = perp / width
            if q > 2.6:
                continue
            fall = math.exp(-q * q * 1.05) * (1.0 - 0.45 * t / reach)
            # Opaque-ish warm body so it reads amber over any sky colour,
            # plus a hot additive core.
            blend_px(base + x * 3, BEAM_COL[0], BEAM_COL[1], BEAM_COL[2],
                     fall * 0.52)
            if q < 0.5:
                add_px(base + x * 3, BEAM_CORE[0], BEAM_CORE[1],
                       BEAM_CORE[2], (0.5 - q) * 1.1 * (1.0 - t / reach))


# ---------------------------------------------------- 6. rings (behind) ----

_COS_T = math.cos(RING_TILT)
_SIN_T = math.sin(RING_TILT)


def ring_pixel(x, y, front):
    """Return (r, g, b, alpha) for a ring point, or None."""
    dx = x - PLANET_CX
    dy = y - PLANET_CY
    u = dx * _COS_T + dy * _SIN_T
    v = -dx * _SIN_T + dy * _COS_T
    if front != (v > 0):
        return None
    r = math.sqrt(u * u + (v / RING_FLAT) ** 2)
    if r < RING_IN or r > RING_OUT:
        return None
    # Band structure: bright and dim lanes across the ring width.
    band = 0.5 + 0.5 * math.sin(r * 0.32 + 1.7 * math.sin(r * 0.061))
    edge = smooth((r - RING_IN) / 26.0) * (1.0 - smooth((r - RING_OUT + 30) / 30.0))
    # Lit from the lower left: the near-left arc glows warmest.
    ang = math.atan2(v, u)
    lit = 0.45 + 0.55 * max(0.0, math.cos(ang - 2.35))
    a = (0.16 + 0.5 * band) * edge * lit
    warm = 0.5 + 0.5 * math.cos(ang - 2.35)
    rr = lerp(205, 255, warm)
    gg = lerp(215, 205, warm)
    bb = lerp(225, 165, warm)
    return rr, gg, bb, a


def paint_rings(front):
    R = RING_OUT + 4
    x0 = max(0, int(PLANET_CX - R))
    x1 = min(W, int(PLANET_CX + R) + 1)
    y0 = max(0, int(PLANET_CY - R * RING_FLAT - 30))
    y1 = min(H, int(PLANET_CY + R * RING_FLAT + 30) + 1)
    for y in range(y0, y1):
        base = y * W * 3
        for x in range(x0, x1):
            p = ring_pixel(x, y, front)
            if p is not None and p[3] > 0.01:
                blend_px(base + x * 3, p[0], p[1], p[2], p[3])


# ------------------------------------------------------------- 7. planet ---


def paint_planet():
    # Light from the lower left (the lighthouse side), slightly frontal so
    # most of the disc stays lit and the night side keeps faint band detail.
    lx, ly, lz = -0.62, 0.48, 0.62
    ll = math.sqrt(lx * lx + ly * ly + lz * lz)
    lx, ly, lz = lx / ll, ly / ll, lz / ll
    R = PLANET_R
    x0 = max(0, PLANET_CX - R)
    x1 = min(W, PLANET_CX + R + 1)
    y0 = max(0, PLANET_CY - R)
    y1 = min(H, PLANET_CY + R + 1)
    nb = len(PLANET_BANDS)
    for y in range(y0, y1):
        dy = y - PLANET_CY
        base = y * W * 3
        for x in range(x0, x1):
            dx = x - PLANET_CX
            d2 = dx * dx + dy * dy
            if d2 > R * R:
                continue
            d = math.sqrt(d2)
            nx, ny = dx / R, dy / R
            nz = math.sqrt(max(0.0, 1.0 - nx * nx - ny * ny))
            # Warped latitude bands.
            warp = (fbm(x * 0.012 + 3.1, y * 0.012 + 8.4, 2) - 0.5) * 0.55
            lat = ny + warp
            band_f = (math.sin(lat * 8.5) * 0.5 + 0.5) * (nb - 1)
            bi = int(band_f)
            bf = band_f - bi
            c0 = PLANET_BANDS[bi]
            c1 = PLANET_BANDS[bi + 1] if bi + 1 < nb else PLANET_BANDS[bi]
            r = lerp(c0[0], c1[0], bf)
            g = lerp(c0[1], c1[1], bf)
            b = lerp(c0[2], c1[2], bf)
            # A warm sunset belt low on the disc.
            belt = math.exp(-((lat - 0.34) / 0.16) ** 2)
            r = lerp(r, 226, belt * 0.45)
            g = lerp(g, 148, belt * 0.45)
            b = lerp(b, 92, belt * 0.45)
            # Day/night terminator + night side (kept faintly visible).
            diff = nx * lx + ny * ly + nz * lz
            day = smooth((diff + 0.28) / 0.62)
            r = lerp(PLANET_NIGHT[0], r, day)
            g = lerp(PLANET_NIGHT[1], g, day)
            b = lerp(PLANET_NIGHT[2], b, day)
            r += 8.0 * (1.0 - day)
            g += 14.0 * (1.0 - day)
            b += 22.0 * (1.0 - day)
            # Warm rim light on the lit limb.
            rim = smooth((d / R - 0.86) / 0.14) * max(0.0, nx * lx + ny * ly)
            r = lerp(r, RIM_WARM[0], rim * 0.85)
            g = lerp(g, RIM_WARM[1], rim * 0.85)
            b = lerp(b, RIM_WARM[2], rim * 0.85)
            i = base + x * 3
            img[i] = clamp255(r)
            img[i + 1] = clamp255(g)
            img[i + 2] = clamp255(b)
    # Storm oval: a pale swirling eye on the day side.
    sx, sy, sr = PLANET_CX - 52, PLANET_CY - 34, 44
    for y in range(sy - sr, sy + sr + 1):
        for x in range(sx - sr, sx + sr + 1):
            ex = (x - sx) / sr
            ey = (y - sy) / (sr * 0.62)
            e = ex * ex + ey * ey
            if e >= 1.0:
                continue
            swirl = 0.5 + 0.5 * math.sin(math.atan2(ey, ex) * 2.0 - e * 5.0)
            a = (1.0 - e) * (0.25 + 0.35 * swirl)
            i = (y * W + x) * 3
            blend_px(i, 214, 240, 244, a)


# ----------------------------------------------------------- 8. ridges -----


def ridge_line(points, x):
    """Cosine-interpolated height through control points."""
    if x <= points[0][0]:
        return points[0][1]
    for i in range(1, len(points)):
        if x <= points[i][0]:
            x0, y0 = points[i - 1]
            x1, y1 = points[i]
            f = (x - x0) / (x1 - x0)
            f = (1.0 - math.cos(f * math.pi)) / 2.0
            return y0 + (y1 - y0) * f
    return points[-1][1]


FAR_POINTS = [(0, 668), (150, 640), (330, 662), (520, 636),
              (700, 660), (880, 642), (1024, 664)]
NEAR_POINTS = [(0, 812), (120, 768), (255, 668), (360, 716),
               (460, 772), (540, 902), (620, 1024)]


def ridge_arrays():
    far_y = [0] * W
    near_y = [0] * W
    far_bot = [0] * W
    for x in range(W):
        far_y[x] = int(ridge_line(FAR_POINTS, x))
        near_y[x] = int(ridge_line(NEAR_POINTS, x)) if x <= 620 else H
        # Wavy shoreline so the far ridge meets the sea without a ruler line.
        far_bot[x] = SEA_Y + int(9.0 * math.sin(x * 0.021 + 1.3)
                                 + 7.0 * vnoise(x * 0.011, 3.3))
    return far_y, near_y, far_bot


_RIDGE_CACHE = None


def ridges():
    global _RIDGE_CACHE
    if _RIDGE_CACHE is None:
        _RIDGE_CACHE = ridge_arrays()
    return _RIDGE_CACHE


def paint_ridges():
    far_y, near_y, far_bot = ridges()
    # Far ridge: flat silhouette down to its wavy shoreline.
    for x in range(W):
        for y in range(far_y[x], far_bot[x]):
            i = (y * W + x) * 3
            img[i] = RIDGE_FAR[0]
            img[i + 1] = RIDGE_FAR[1]
            img[i + 2] = RIDGE_FAR[2]
    # Near ridge: silhouette with a faint vertical shading.
    for x in range(W):
        top = near_y[x]
        if top >= H:
            continue
        for y in range(top, H):
            depth = (y - top) / max(1, H - top)
            sh = 1.0 - depth * 0.35
            i = (y * W + x) * 3
            img[i] = clamp255(RIDGE_NEAR[0] * sh)
            img[i + 1] = clamp255(RIDGE_NEAR[1] * sh)
            img[i + 2] = clamp255(RIDGE_NEAR[2] * sh)
        # Rim light along the crest, teal toward the planet, warm near the lamp.
        t = x / (W - 1)
        rr = lerp(255, 90, t)
        gg = lerp(190, 205, t)
        bb = lerp(110, 225, t)
        for k, a in ((0, 0.55), (1, 0.30), (2, 0.15)):
            y = top + k
            if y < H:
                blend_px((y * W + x) * 3, rr, gg, bb, a)
    # Faint teal fill light on the cliff face, strongest toward the planet.
    for y in range(660, H):
        base = y * W * 3
        for x in range(240, 640):
            if y < near_y[x]:
                continue
            col = math.exp(-((x - 540) / 240.0) ** 2)
            depth = 1.0 - (y - near_y[x]) / 320.0
            a = col * max(0.0, depth) * 0.10
            if a > 0.005:
                add_px(base + x * 3, 70, 160, 190, a)


# ---------------------------------------------------------------- 9. sea ---


def paint_sea(rng):
    _, near_y, far_bot = ridges()
    # Base gradient rows: visible between the far shoreline and the cliff.
    for y in range(SEA_Y, H):
        t = (y - SEA_Y) / (H - SEA_Y)
        r = lerp(SEA_TOP[0], SEA_BOT[0], t)
        g = lerp(SEA_TOP[1], SEA_BOT[1], t)
        b = lerp(SEA_TOP[2], SEA_BOT[2], t)
        base = y * W * 3
        for x in range(W):
            if y < far_bot[x] or y >= near_y[x]:
                continue
            i = base + x * 3
            img[i] = clamp255(r)
            img[i + 1] = clamp255(g)
            img[i + 2] = clamp255(b)
    # Planet reflection: shimmering teal column.
    for y in range(SEA_Y, H):
        fade = 1.0 - (y - SEA_Y) / (H - SEA_Y) * 0.55
        base = y * W * 3
        for x in range(430, 950):
            if y < far_bot[x] or y >= near_y[x]:
                continue
            col = math.exp(-((x - PLANET_CX) / 150.0) ** 2)
            shim = 0.5 + 0.5 * vnoise(x * 0.09, y * 0.22)
            a = col * fade * shim * 0.55
            if a > 0.01:
                add_px(base + x * 3, 80, 205, 225, a)
    # Warm shimmer near the beam's foot.
    for y in range(SEA_Y, H):
        fade = 1.0 - (y - SEA_Y) / (H - SEA_Y) * 0.7
        base = y * W * 3
        for x in range(180, 470):
            if y < far_bot[x] or y >= near_y[x]:
                continue
            col = math.exp(-((x - 330) / 110.0) ** 2)
            shim = 0.5 + 0.5 * vnoise(x * 0.11 + 40.0, y * 0.26)
            a = col * fade * shim * 0.34
            if a > 0.01:
                add_px(base + x * 3, 255, 180, 90, a)
    # Horizontal sparkle streaks.
    for _ in range(110):
        x = rng.randint(430, 1000)
        y = rng.randint(SEA_Y + 4, H - 6)
        if y < far_bot[x] or y >= near_y[x]:
            continue
        ln = rng.randint(8, 55)
        a = rng.uniform(0.10, 0.34)
        warm = x < 560 and rng.random() < 0.5
        c = (255, 190, 110) if warm else (130, 220, 235)
        for xx in range(x, min(W, x + ln)):
            blend_px((y * W + xx) * 3, c[0], c[1], c[2], a)


# --------------------------------------------------------- 10. lighthouse --


def paint_lighthouse():
    cx = LAMP_X
    base_y = 668  # ridge crest under the tower
    # Tower: trapezoid, wider at the base.
    for y in range(584, base_y + 1):
        t = (y - 584) / (base_y - 584)
        half = lerp(13, 20, t)
        for x in range(int(cx - half), int(cx + half) + 1):
            i = (y * W + x) * 3
            img[i] = RIDGE_NEAR[0]
            img[i + 1] = RIDGE_NEAR[1]
            img[i + 2] = RIDGE_NEAR[2]
    # Gallery platform.
    for y in range(578, 585):
        for x in range(cx - 18, cx + 19):
            i = (y * W + x) * 3
            img[i] = 10
            img[i + 1] = 9
            img[i + 2] = 24
    # Lamp room: warm glass with dark frame.
    for y in range(558, 578):
        for x in range(cx - 13, cx + 14):
            i = (y * W + x) * 3
            if x in (cx - 13, cx + 13, cx):
                img[i] = 10
                img[i + 1] = 9
                img[i + 2] = 24
            else:
                img[i] = LAMP_COL[0]
                img[i + 1] = LAMP_COL[1]
                img[i + 2] = LAMP_COL[2]
    # Dome roof.
    for y in range(548, 558):
        t = (y - 548) / 10.0
        half = lerp(2, 14, t)
        for x in range(int(cx - half), int(cx + half) + 1):
            i = (y * W + x) * 3
            img[i] = 10
            img[i + 1] = 9
            img[i + 2] = 24
    # Finial.
    for y in range(543, 548):
        i = (y * W + cx) * 3
        img[i] = 10
        img[i + 1] = 9
        img[i + 2] = 24
    # Teal rim on the tower's planet-facing edge.
    for y in range(584, base_y + 1):
        t = (y - 584) / (base_y - 584)
        half = lerp(13, 20, t)
        x = int(cx + half)
        blend_px((y * W + x) * 3, 90, 205, 225, 0.5)
    # Lamp halo.
    for y in range(LAMP_Y - 80, LAMP_Y + 81):
        for x in range(LAMP_X - 80, LAMP_X + 81):
            d = math.hypot(x - LAMP_X, y - LAMP_Y) / 80.0
            if d >= 1.0:
                continue
            a = (1.0 - d) ** 2.2 * 0.6
            add_px((y * W + x) * 3, 255, 200, 120, a)


# ------------------------------------------------------- 11. mist + shade --


def paint_mist():
    for (yc, thick, alpha) in ((800, 46, 0.10), (884, 60, 0.13), (962, 70, 0.15)):
        for y in range(yc - thick, yc + thick + 1):
            if y < 0 or y >= H:
                continue
            prof = 1.0 - abs(y - yc) / thick
            a = alpha * prof * prof
            base = y * W * 3
            for x in range(W):
                blend_px(base + x * 3, 168, 148, 218, a)


def paint_vignette():
    row_f = [1.0 - 0.30 * smooth((abs(y / (H - 1) - 0.5) * 2 - 0.55) / 0.45)
             for y in range(H)]
    col_f = [1.0 - 0.30 * smooth((abs(x / (W - 1) - 0.5) * 2 - 0.55) / 0.45)
             for x in range(W)]
    for y in range(H):
        rf = row_f[y]
        base = y * W * 3
        for x in range(W):
            f = rf * col_f[x]
            if f >= 0.999:
                continue
            i = base + x * 3
            img[i] = clamp255(img[i] * f)
            img[i + 1] = clamp255(img[i + 1] * f)
            img[i + 2] = clamp255(img[i + 2] * f)


# ------------------------------------------------------------------ main ---


def main():
    rng = random.Random(SEED)
    paint_sky()
    paint_nebula()
    paint_stars(rng)
    paint_planet_glow()
    paint_beam()
    paint_rings(front=False)
    paint_planet()
    paint_rings(front=True)
    paint_ridges()
    paint_sea(rng)
    paint_lighthouse()
    paint_mist()
    paint_vignette()
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "entry.png")
    size = write_png(path, W, H, img)
    print("wrote %s (%d bytes)" % (path, size))


if __name__ == "__main__":
    main()
