#!/usr/bin/env python3
"""Builds the base map of the jurists' map: tiles in assets/map/tiles and region labels.

    python3 tools/build_map.py NE_DIR THURAYYA_DIR

NE_DIR holds Natural Earth data (public domain, naturalearthdata.com):
  NE2_HR_LC_SR_W_DR.tif      Natural Earth II with shaded relief, water and drainages, 1:10m
  ne_10m_land/ne_10m_land.shp, ne_10m_lakes/ne_10m_lakes.shp,
  ne_10m_lakes_historic/ne_10m_lakes_historic.shp  (the Aral Sea before it shrank)
THURAYYA_DIR is a checkout of github.com/althurayya/althurayya.github.io (data CC BY 4.0);
master/places.geojson gives the regions of Georgette Cornu's atlas, which colour the map.

The map is equirectangular (one pixel is 1/60 of a degree at the largest zoom), so it is shown
with Leaflet's CRS.Simple. Writes:
  assets/map/tiles/{z}/{x}/{y}.webp   zoom 0-3, 256 px tiles
  assets/map/regions.json             region names and label positions
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
import shapefile
from PIL import Image, ImageDraw, ImageFilter
from scipy.ndimage import gaussian_filter
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "map"

# extent in degrees and pixels per degree of the largest zoom
WEST, EAST, SOUTH, NORTH = -11, 91, 6, 53
PPD = 60
ZOOMS = 4
TILE = 256

# Display regions: names, fill colour, and the Cornu regions (al-Thurayya) that seed them.
# Regions with no Cornu seed get theirs from SEEDS below. Deserts are left uncoloured.
REGIONS = {
    "endulus": ("Endülüs", "al-Andalus", "الأندلس", "#e7a9c8", ["Andalus"]),
    "sicilya": ("Sicilya", "Sicily", "صقلية", "#e7a9c8", ["Sicile"]),
    "magrib": ("Mağrib", "Maghrib", "المغرب", "#bcd9a2", ["Maghrib"]),
    "berka": ("Berka", "Barqa", "برقة", "#f0dc96", ["Barqa"]),
    "misir": ("Mısır", "Egypt", "مصر", "#c8aee0", ["Egypt"]),
    "sam": ("Şam", "Syria", "الشام", "#a9d5a3", ["Sham"]),
    "cezire": ("Cezîre", "Jazira", "الجزيرة", "#eba3ab", ["Aqur"]),
    "irak": ("Irak", "Iraq", "العراق", "#f2d98a", ["Iraq"]),
    "hicaz": ("Hicaz", "Hijaz", "الحجاز", "#b3d9a8", []),
    "yemen": ("Yemen", "Yemen", "اليمن", "#f2dc9b", ["Yemen"]),
    "cibal": ("Cibâl", "Jibal", "الجبال", "#f3c08c", ["Jibal"]),
    "huzistan": ("Huzistan", "Khuzistan", "خوزستان", "#9fd4cf", ["Khuzistan"]),
    "fars": ("Fars", "Fars", "فارس", "#c9b4e2", ["Faris"]),
    "kirman": ("Kirman", "Kirman", "كرمان", "#f4c894", ["Kirman"]),
    "azerbaycan": ("Azerbaycan", "Azerbaijan", "أذربيجان", "#eda5a1", ["Rihab"]),
    "taberistan": ("Taberistan", "Tabaristan", "طبرستان", "#b8dca2", ["Daylam"]),
    "horasan": ("Horasan", "Khurasan", "خراسان", "#f5d58c", ["Khurasan"]),
    "sistan": ("Sistan", "Sistan", "سجستان", "#a5d8d2", ["Sijistan"]),
    "sind": ("Sind", "Sind", "السند", "#c6e2a5", ["Sind"]),
    "harezm": ("Harezm", "Khwarazm", "خوارزم", "#f3c3a0", []),
    "maveraunnehir": ("Mâverâünnehir", "Transoxiana", "ما وراء النهر", "#cfb2dd", ["Transoxiana"]),
    "turkistan": ("Türkistan", "Turkestan", "تركستان", "#b7d8aa", []),
    "hind": ("Hind", "India", "الهند", "#eedba2", []),
    "rum": ("Rum", "Rum", "بلاد الروم", "#9fcfc2", []),
    "kirim": ("Kırım", "Crimea", "القرم", "#f1bb8d", []),
}

# Seeds for the regions outside Cornu's atlas (lat, lng); rough outlines of where they lay.
SEEDS = {
    "rum": [(41.0, 29.0), (40.2, 29.1), (39.9, 32.9), (37.9, 32.5), (38.7, 35.5), (39.8, 37.0), (40.3, 36.6),
            (41.0, 34.0), (41.7, 35.0), (38.5, 27.2), (39.4, 29.9), (37.2, 28.4), (36.9, 30.7), (38.4, 38.3),
            (39.7, 39.5), (41.7, 26.6), (42.7, 23.3), (42.0, 21.4), (43.9, 18.4), (43.9, 20.6), (41.3, 19.8),
            (40.6, 22.9), (39.6, 22.4), (42.5, 25.5), (44.8, 20.5), (43.2, 27.9), (38.0, 23.7), (40.9, 31.6),
            (37.0, 35.3), (38.3, 30.5), (39.7, 34.0), (40.7, 26.0), (42.1, 24.7), (44.3, 22.0)],
    "kirim": [(45.0, 34.1), (45.3, 33.4), (45.0, 35.4), (44.7, 34.4), (45.8, 34.2)],
    "turkistan": [(42.3, 69.6), (42.9, 71.4), (42.8, 74.6), (43.3, 68.2), (44.0, 67.0), (39.5, 76.0), (38.4, 77.2),
                  (41.2, 80.2), (43.8, 76.9), (42.5, 78.5), (40.5, 73.5), (45.0, 71.0)],
    "hind": [(31.5, 74.3), (28.6, 77.2), (27.2, 78.0), (26.4, 74.6), (23.0, 72.6), (25.4, 81.8), (30.2, 71.5),
             (29.0, 79.5), (24.6, 77.7), (21.2, 72.8), (23.3, 77.4), (19.1, 72.9), (26.8, 80.9), (22.7, 75.9),
             (17.4, 78.5), (21.1, 79.1), (25.3, 83.0), (28.0, 73.3), (32.7, 74.9), (15.5, 75.0)],
}

# Where a label sits when the seed centre is a poor place for it (lat, lng).
LABEL_AT = {
    "hicaz": (23.2, 39.6), "sam": (33.3, 37.2), "rum": (39.2, 32.8), "irak": (32.2, 44.9), "misir": (26.2, 30.6),
    "magrib": (31.0, 1.0), "endulus": (38.4, -4.6), "cezire": (36.4, 41.4), "maveraunnehir": (40.6, 66.0),
    "horasan": (35.4, 59.4), "hind": (26.0, 78.5), "turkistan": (42.6, 73.8), "yemen": (15.4, 45.4),
    "azerbaycan": (39.4, 46.6), "taberistan": (36.6, 52.4), "fars": (29.4, 53.2), "kirman": (29.2, 57.6),
    "cibal": (34.6, 48.8), "sistan": (31.0, 62.0), "sind": (26.6, 68.2), "harezm": (41.9, 60.2),
    "huzistan": (31.6, 49.0), "kirim": (45.4, 34.0), "berka": (31.2, 21.6), "sicilya": (37.6, 14.2),
}

# Seas and lakes, labelled in blue (lat, lng).
WATERS = [
    ("Akdeniz", "Mediterranean Sea", "البحر الأبيض المتوسط", 34.4, 18.5),
    ("Karadeniz", "Black Sea", "البحر الأسود", 43.3, 34.5),
    ("Hazar Denizi", "Caspian Sea", "بحر قزوين", 42.0, 50.8),
    ("Kızıldeniz", "Red Sea", "البحر الأحمر", 20.2, 38.6),
    ("Basra Körfezi", "Persian Gulf", "الخليج", 27.0, 51.0),
    ("Umman Denizi", "Arabian Sea", "بحر العرب", 16.5, 62.5),
    ("Hint Okyanusu", "Indian Ocean", "المحيط الهندي", 9.0, 72.0),
    ("Aral Gölü", "Aral Sea", "بحيرة آرال", 45.1, 59.6),
    ("Atlas Okyanusu", "Atlantic Ocean", "المحيط الأطلسي", 36.0, -9.2),
]

WATER = (196, 222, 238)
COAST = (120, 163, 196)
GRID = (118, 170, 214)


def px(lng, lat):
    return (lng - WEST) * PPD, (NORTH - lat) * PPD


def crop_relief(ne):
    Image.MAX_IMAGE_PIXELS = None
    im = Image.open(ne / "NE2_HR_LC_SR_W_DR.tif")
    ppd = im.size[0] / 360
    assert round(ppd) == PPD
    return im.crop((round((WEST + 180) * PPD), round((90 - NORTH) * PPD),
                    round((EAST + 180) * PPD), round((90 - SOUTH) * PPD))).convert("RGB")


def polygons(path):
    """Rasterises a polygon shapefile into a mask of the map's size."""
    w, h = (EAST - WEST) * PPD, (NORTH - SOUTH) * PPD
    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)
    for shape in shapefile.Reader(str(path)).shapes():
        x0, y0, x1, y1 = shape.bbox
        if x1 < WEST or x0 > EAST or y1 < SOUTH or y0 > NORTH:
            continue
        parts = list(shape.parts) + [len(shape.points)]
        for a, b in zip(parts, parts[1:]):
            ring = [px(x, y) for x, y in shape.points[a:b]]
            if len(ring) > 2:
                # rings drawn in turn: outer rings fill, holes (counter-clockwise) clear
                area = sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1]))
                draw.polygon(ring, fill=255 if area > 0 else 0)
    return mask


def seeds(thurayya):
    pts, ids, reach = [], [], []
    by_code = {code: rid for rid, r in REGIONS.items() for code in r[4]}
    for f in json.loads((thurayya / "master/places.geojson").read_text(encoding="utf-8"))["features"]:
        c = f["properties"]["cornuData"]
        lng, lat = f["geometry"]["coordinates"]
        code = c.get("region_code")
        rid = by_code.get(code)
        if code == "Jazirat al-Arab":
            rid = "hicaz" if lng < 41.6 and lat > 19.5 else None
        elif code == "Transoxiana" and lng < 62.6 and lat > 40.3:
            rid = "harezm"
        elif code == "Transoxiana" and lng > 69.3 and lat > 42.2:
            rid = "turkistan"
        pts.append((lat, lng))
        ids.append(rid)  # None keeps deserts and unlisted regions uncoloured
        reach.append(2.1)
    for rid, ll in SEEDS.items():
        pts += ll
        ids += [rid] * len(ll)
        reach += [3.2] * len(ll)  # our own seeds are sparser, so each colours a wider circle
    return np.array(pts), ids, np.array(reach)


def blur_rgba(rgba, radius):
    """Gaussian blur on premultiplied colour, so uncoloured ground does not darken the edges."""
    a = rgba[..., 3:4] / 255
    chans = [gaussian_filter(c, radius) for c in np.moveaxis(np.concatenate([rgba[..., :3] * a, a * 255], axis=2), 2, 0)]
    pre, alpha = np.stack(chans[:3], axis=2), chans[3][..., None]
    rgb = np.where(alpha > 0.5, pre / np.maximum(alpha, 1e-3) * 255, 0)
    return np.concatenate([rgb, alpha], axis=2).clip(0, 255)


def region_layer(size, land, pts, ids, reach):
    """Soft region colours: every land pixel takes the colour of the nearest seed, fading with distance."""
    step = 4  # computed on a coarser grid, then blurred and enlarged
    w, h = size[0] // step, size[1] // step
    ys, xs = np.mgrid[0:h, 0:w]
    lat = NORTH - (ys + 0.5) * step / PPD
    lng = WEST + (xs + 0.5) * step / PPD
    k = np.cos(np.radians(33))  # one scale for the whole map is close enough at these latitudes
    tree = cKDTree(np.c_[pts[:, 0], pts[:, 1] * k])
    dist, idx = tree.query(np.c_[lat.ravel(), lng.ravel() * k])
    colours = np.array([[0, 0, 0, 0]] + [list(int(REGIONS[r][3][i:i + 2], 16) for i in (1, 3, 5)) + [255]
                                         for r in REGIONS], dtype=np.float32)
    index = {r: i + 1 for i, r in enumerate(REGIONS)}
    seed_colour = np.array([index.get(r, 0) if r else 0 for r in ids])
    rgba = colours[seed_colour[idx]].reshape(h, w, 4)
    # full colour within about a degree of a seed, none beyond two (three for our own seeds)
    r = reach[idx].reshape(h, w)
    fade = np.clip((r - dist.reshape(h, w)) / (r / 2), 0, 1)
    rgba[..., 3] *= fade
    small_land = np.asarray(land.resize((w, h), Image.BILINEAR), dtype=np.float32) / 255
    rgba[..., 3] *= small_land
    layer = Image.fromarray(blur_rgba(rgba, 5).astype(np.uint8), "RGBA")
    return layer.resize(size, Image.BICUBIC)


def label_positions(pts, ids):
    out = {}
    for rid, r in REGIONS.items():
        if rid in LABEL_AT:
            lat, lng = LABEL_AT[rid]
        else:
            ll = pts[[i for i, x in enumerate(ids) if x == rid]]
            lat, lng = ll.mean(axis=0)
        out[rid] = {"tr": r[0], "en": r[1], "ar": r[2], "lat": round(float(lat), 2), "lng": round(float(lng), 2)}
    return out


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    ne, thurayya = Path(sys.argv[1]), Path(sys.argv[2])
    relief = crop_relief(ne)
    size = relief.size
    coast = polygons(ne / "ne_10m_land/ne_10m_land.shp")
    lakes = np.maximum(np.asarray(polygons(ne / "ne_10m_lakes/ne_10m_lakes.shp")),
                       np.asarray(polygons(ne / "ne_10m_lakes_historic/ne_10m_lakes_historic.shp")))
    land = Image.fromarray(np.minimum(np.asarray(coast), 255 - lakes))

    # pale relief on land, flat water with a darker shore line
    base = np.asarray(relief, dtype=np.float32)
    grey = base.mean(axis=2, keepdims=True)
    base = grey + (base - grey) * 0.55                      # less saturated
    base = base * 0.72 + np.array([247, 243, 232]) * 0.28   # lighter, toward paper
    m = np.asarray(land.filter(ImageFilter.GaussianBlur(0.8)), dtype=np.float32)[..., None] / 255
    out = base * m + np.array(WATER) * (1 - m)
    img = Image.fromarray(out.clip(0, 255).astype(np.uint8), "RGB")

    shore = coast.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.GaussianBlur(0.6))
    img.paste(Image.new("RGB", size, COAST), mask=shore.point(lambda v: min(255, v * 2) * 0.55))

    pts, ids, reach = seeds(thurayya)
    regions = region_layer(size, land, pts, ids, reach)
    # multiply the region colours into the relief so its shading shows through
    r = np.asarray(regions, dtype=np.float32)
    a = r[..., 3:4] / 255 * 0.8
    tinted = np.asarray(img, dtype=np.float32) * (1 - a) + np.asarray(img, dtype=np.float32) * r[..., :3] / 255 * a
    img = Image.fromarray(tinted.clip(0, 255).astype(np.uint8), "RGB")

    # graticule every 10 degrees
    draw = ImageDraw.Draw(img, "RGBA")
    for lng in range(-10, EAST + 1, 10):
        x = px(lng, 0)[0]
        draw.line([(x, 0), (x, size[1])], fill=GRID + (150,), width=2)
    for lat in range(10, NORTH + 1, 10):
        y = px(0, lat)[1]
        draw.line([(0, y), (size[0], y)], fill=GRID + (150,), width=2)

    tiles = OUT / "tiles"
    for z in range(ZOOMS):
        scale = 2 ** (ZOOMS - 1 - z)
        level = img.resize((math.ceil(size[0] / scale), math.ceil(size[1] / scale)), Image.LANCZOS) if scale > 1 else img
        for x in range(math.ceil(level.width / TILE)):
            for y in range(math.ceil(level.height / TILE)):
                tile = Image.new("RGB", (TILE, TILE), WATER)
                tile.paste(level.crop((x * TILE, y * TILE, min(level.width, (x + 1) * TILE), min(level.height, (y + 1) * TILE))))
                path = tiles / str(z) / str(x) / f"{y}.webp"
                path.parent.mkdir(parents=True, exist_ok=True)
                tile.save(path, "WEBP", quality=78, method=6)
        print("zoom", z, level.size)
    img.resize((size[0] // 4, size[1] // 4), Image.LANCZOS).save(OUT / "overview.jpg", quality=82, optimize=True)

    meta = {
        "bounds": {"west": WEST, "east": EAST, "south": SOUTH, "north": NORTH},
        "ppd": PPD, "zooms": ZOOMS, "tile": TILE,
        "regions": label_positions(pts, ids),
        "waters": [{"tr": tr, "en": en, "ar": ar, "lat": lat, "lng": lng} for tr, en, ar, lat, lng in WATERS],
    }
    (OUT / "regions.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print("wrote", OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
