#!/usr/bin/env python3
"""Downloads the site's images from Wikimedia Commons and records their credits.

Only files whose licence is public domain, CC0, CC BY or CC BY-SA are accepted;
the licence and the author are read from Commons at download time, not typed by hand.

    python3 tools/fetch_images.py          # downloads what is missing
    python3 tools/fetch_images.py --force  # downloads everything again
    python3 tools/fetch_images.py --local DIR  # uses DIR/<id>.jpg when it exists
    python3 tools/fetch_images.py --local DIR --offline CREDITS.json
        # no network: only the images found in DIR, with credits read from CREDITS.json
        # ({id: {title, page, artist, license, licenseUrl}}, as recorded at an earlier download)

Writes assets/img/<id>.jpg (1600 px wide), assets/img/<id>-sm.jpg (720 px wide)
and _data/images.yml.
"""
import io
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
IMG = ROOT / "assets" / "img"
DATA = ROOT / "_data" / "images.yml"
API = "https://commons.wikimedia.org/w/api.php"
UA = "fukaha.github.io image fetcher (https://fukaha.github.io)"
ALLOWED = re.compile(r"^(Public domain|PD.*|CC0.*|CC BY(-SA)? [0-9.]+.*)$", re.I)

IMAGES = {
    "muwatta": {
        "file": "Muwatta (Malik ibn Anas) 1326 Salé Morocco Marinid manuscript.png",
        "tr": "İmam Mâlik, el-Muvatta’. Selâ (Fas), 1326 tarihli Merînî nüshası",
        "en": "Mālik ibn Anas, al-Muwaṭṭaʾ. Marinid copy, Salé, dated 1326",
        "ar": "الموطأ للإمام مالك، نسخة مرينية مؤرخة سنة ١٣٢٦م، سلا",
    },
    "mabsut": {
        "file": "A 622 AH Handwritten Manuscript Excerpt of Al-Mabsut.jpg",
        "tr": "Serahsî, el-Mebsût. 622/1225 tarihli nüsha",
        "en": "Al-Sarakhsī, al-Mabsūṭ. Copy dated 622/1225",
        "ar": "المبسوط للسرخسي، نسخة مؤرخة ٦٢٢هـ",
    },
    "kharaj": {
        "file": "961 AH manuscripts of Kitab al-Kharaj.jpg",
        "tr": "Ebû Yûsuf, Kitâbü’l-Harâc. 961/1554 tarihli nüsha",
        "en": "Abū Yūsuf, Kitāb al-Kharāj. Copy dated 961/1554",
        "ar": "كتاب الخراج لأبي يوسف، نسخة مؤرخة ٩٦١هـ",
    },
    "multaqa": {
        "file": "Multaqa al abhur.jpg",
        "tr": "İbrâhim el-Halebî, Mülteka’l-ebhur. 11./17. yüzyıl nüshası",
        "en": "Ibrāhīm al-Ḥalabī, Multaqā al-abḥur. 11th/17th-century copy",
        "ar": "ملتقى الأبحر لإبراهيم الحلبي، نسخة من القرن الحادي عشر",
    },
    "kadizade": {
        "file": "Kadizade Besir Aga 397.jpg",
        "tr": "Kadızâde Mehmed Efendi’nin (ö. 1045/1635) bir eserinin nüshası, Süleymaniye Ktp., Beşir Ağa 397",
        "en": "Copy of a work by Kadızade Mehmed Efendi (d. 1045/1635), Süleymaniye Library, Beşir Ağa 397",
        "ar": "نسخة من مؤلَّف لقاضي زاده محمد أفندي (ت ١٠٤٥هـ)، مكتبة السليمانية، بشير آغا ٣٩٧",
    },
    "binding": {
        "file": "Turkey, Istanbul, Ottoman period, 15th century - Bookbinding for a Koran - 1944.495 - Cleveland Museum of Art.tif",
        "tr": "Mushaf cildi, İstanbul, Osmanlı dönemi, 15. yüzyıl. Cleveland Museum of Art",
        "en": "Binding for a Qurʾān, Istanbul, Ottoman period, 15th century. Cleveland Museum of Art",
        "ar": "جلد مصحف، إسطنبول، العهد العثماني، القرن الخامس عشر الميلادي",
    },
    "library": {
        "file": "Maqamat hariri.jpg",
        "tr": "Kütüphanede bir ilim meclisi. Vâsıtî’nin Harîrî’nin Makāmât’ı için yaptığı tasvir, Bağdat, 634/1237",
        "en": "A gathering of scholars in a library. Al-Wāsiṭī’s illustration to al-Ḥarīrī’s Maqāmāt, Baghdad, 634/1237",
        "ar": "مجلس علم في مكتبة، من تصاوير الواسطي لمقامات الحريري، بغداد، ٦٣٤هـ",
    },
    "hunat": {
        "file": "Girih in stone at Kayseri Hunat Hatun.jpg",
        "tr": "Hunat Hatun Medresesi taç kapısında taş geçme (girih) süslemesi, Kayseri, Selçuklu dönemi",
        "en": "Stone girih ornament on the portal of the Hunat Hatun Madrasa, Kayseri, Seljuq period",
        "ar": "زخرفة هندسية حجرية على بوابة مدرسة خوند خاتون، قيصري، العهد السلجوقي",
    },
    "shahizinda": {
        "file": "Samarkand Shah-i Zinda Tuman Aqa complex cropped2.jpg",
        "tr": "On köşeli yıldıza dayanan geçme süsleme, Tuman Ağa külliyesi, Şâh-ı Zinde, Semerkant",
        "en": "Girih strapwork on a ten-point star, Tuman Aqa complex, Shah-i Zinda, Samarkand",
        "ar": "زخرفة هندسية على نجمة عشرية، مجمع تومان آقا، شاه زنده، سمرقند",
    },
    "ulughbeg": {
        "file": "Ulugh Beg Madrasa, Samarkand.jpg",
        "tr": "Uluğ Bey Medresesi, Semerkant, 823/1420",
        "en": "The Ulugh Beg Madrasa, Samarkand, 823/1420",
        "ar": "مدرسة ألغ بيك، سمرقند، ٨٢٣هـ",
    },
    "registan": {
        "file": "Registan 01.jpg",
        "tr": "Registan Meydanı ve medreseleri, Semerkant",
        "en": "The Registan and its madrasas, Samarkand",
        "ar": "ساحة ريكستان ومدارسها، سمرقند",
    },
    "mustansiriya": {
        "file": "المدرسة المستنصرية في بغداد (3) cropped edited.jpg",
        "tr": "Müstansıriye Medresesi, Bağdat, 631/1234",
        "en": "The Mustanṣiriyya Madrasa, Baghdad, 631/1234",
        "ar": "المدرسة المستنصرية، بغداد، ٦٣١هـ",
    },
    "bouinania": {
        "file": "Main courtyard of Bou Inania Madrasa, Fez, Marocco.jpg",
        "tr": "Bû İnâniyye Medresesi’nin avlusu, Fas, 756/1355",
        "en": "Courtyard of the Bū ʿInāniyya Madrasa, Fez, 756/1355",
        "ar": "صحن المدرسة البوعنانية، فاس، ٧٥٦هـ",
    },
    "bayezid": {
        "file": "Yıldırım Bayezid medresesi bursa - panoramio.jpg",
        "tr": "Yıldırım Bayezid Medresesi, Bursa",
        "en": "The Yıldırım Bayezid Madrasa, Bursa",
        "ar": "مدرسة يلدرم بايزيد، بورصة",
    },
    "istakhri": {
        "file": "Bahr-e Fars.jpg",
        "tr": "Fars Denizi. İstahrî’nin Mesâlikü’l-memâlik’inin bir nüshasından",
        "en": "The Persian Sea, from a copy of al-Iṣṭakhrī’s Masālik al-mamālik",
        "ar": "بحر فارس، من نسخة من مسالك الممالك للإصطخري",
    },
}


def get(url, params=None):
    if params:
        url += "?" + urllib.parse.urlencode(params)
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except Exception as e:  # rate limits and timeouts
            if attempt == 4:
                raise
            time.sleep(15 * (attempt + 1))
            print("  retry:", e)


def text(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html or "")).strip()


def infos(titles):
    """Licence, author and download URL of every file, in a single API request."""
    raw = get(API, {
        "action": "query", "format": "json", "titles": "|".join("File:" + t for t in titles),
        "prop": "imageinfo", "iiprop": "url|extmetadata", "iiurlwidth": 1920,
        "iiextmetadatafilter": "LicenseShortName|LicenseUrl|Artist|Credit",
    })
    data = json.loads(raw)["query"]
    names = {n["to"]: n["from"] for n in data.get("normalized", [])}
    result = {}
    for page in data["pages"].values():
        if "imageinfo" not in page:
            sys.exit(f"not found on Commons: {page['title']}")
        ii = page["imageinfo"][0]
        meta = ii["extmetadata"]
        title = names.get(page["title"], page["title"])[len("File:"):]
        result[title] = {
            "thumb": ii.get("thumburl") or ii["url"],
            "page": ii["descriptionurl"],
            "license": text(meta.get("LicenseShortName", {}).get("value")),
            "licenseUrl": text(meta.get("LicenseUrl", {}).get("value")) or None,
            "artist": text(meta.get("Artist", {}).get("value")) or text(meta.get("Credit", {}).get("value")),
        }
    return result


def save(im, path, width):
    if im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    im.save(path, "JPEG", quality=80, optimize=True, progressive=True)


def yaml_str(s):
    return json.dumps(s, ensure_ascii=False) if s is not None else "null"


def main():
    force = "--force" in sys.argv
    # --local DIR: take <id>.jpg from DIR instead of downloading it (credits still come from Commons)
    local = Path(sys.argv[sys.argv.index("--local") + 1]) if "--local" in sys.argv else None
    IMG.mkdir(parents=True, exist_ok=True)
    out = ["# Written by tools/fetch_images.py. Captions are edited in that script.", ""]
    offline = Path(sys.argv[sys.argv.index("--offline") + 1]) if "--offline" in sys.argv else None
    if offline:
        recorded = json.loads(offline.read_text(encoding="utf-8"))
        metas = {IMAGES[k]["file"]: recorded[k] for k in IMAGES
                 if k in recorded and ((IMG / f"{k}.jpg").exists() or (local and (local / f"{k}.jpg").exists()))}
    else:
        metas = infos([item["file"] for item in IMAGES.values()])
    for key, item in IMAGES.items():
        if item["file"] not in metas:
            print(key, "skipped (not available offline)")
            continue
        print(key)
        meta = metas[item["file"]]
        if not ALLOWED.match(meta["license"]):
            sys.exit(f"{key}: licence not allowed: {meta['license']}")
        big, small = IMG / f"{key}.jpg", IMG / f"{key}-sm.jpg"
        if force or not big.exists():
            if local and (local / f"{key}.jpg").exists():
                im = Image.open(local / f"{key}.jpg").convert("RGB")
            else:
                im = Image.open(io.BytesIO(get(meta["thumb"]))).convert("RGB")
                time.sleep(5)
            save(im, big, 1600)
            save(im, small, 720)
        with Image.open(big) as im:
            w, h = im.size
        out += [
            f"{key}:",
            f"  src: /assets/img/{key}.jpg",
            f"  small: /assets/img/{key}-sm.jpg",
            f"  width: {w}",
            f"  height: {h}",
            f"  tr: {yaml_str(item['tr'])}",
            f"  en: {yaml_str(item['en'])}",
            f"  ar: {yaml_str(item['ar'])}",
            f"  title: {yaml_str(item['file'])}",
            f"  page: {yaml_str(meta['page'])}",
            f"  artist: {yaml_str(meta['artist'][:200])}",
            f"  license: {yaml_str(meta['license'])}",
            f"  licenseUrl: {yaml_str(meta['licenseUrl'])}",
        ]
    DATA.write_text("\n".join(out) + "\n", encoding="utf-8")
    print("wrote", DATA.relative_to(ROOT))


if __name__ == "__main__":
    main()
