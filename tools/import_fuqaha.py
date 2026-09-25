#!/usr/bin/env python3
"""Builds the table data in data/*.json from a checkout of the Fuqaha archive.

    python3 tools/import_fuqaha.py ../fuqaha

Reads src/content/scholars/*.md (biographies from al-Laknawi's al-Fawa'id al-bahiyya),
src/content/works/*.yaml (theses) and src/data/*.  The source checkout is only read.

Writes:
  data/fukaha.json          jurists
  data/klasik-eserler.json  works named in the biographies
  data/tezler.json          MA and PhD theses
  _data/stats.yml           counts and the short lists shown on the home page
"""
import json
import math
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data"

MADHHABS = {"hanefi", "maliki", "safii", "hanbeli", "zahiri", "diger"}


# --- Hijri → Gregorian (tabular Islamic calendar; Julian before 1582-10-15) -------------

def hijri_to_jd(year, month=1, day=1):
    return (day + math.ceil(29.5 * (month - 1)) + (year - 1) * 354
            + (3 + 11 * year) // 30 + 1948439.5 - 1)


def jd_year(jd):
    z = math.floor(jd + 0.5)
    a = z
    if z >= 2299161:
        alpha = math.floor((z - 1867216.25) / 36524.25)
        a = z + 1 + alpha - alpha // 4
    b = a + 1524
    c = math.floor((b - 122.1) / 365.25)
    d = math.floor(365.25 * c)
    e = math.floor((b - d) / 30.6001)
    month = e - 1 if e < 14 else e - 13
    return c - 4716 if month > 2 else c - 4715


def miladi(year):
    """Gregorian years covered by a Hijri year: '1139-40'."""
    a = jd_year(hijri_to_jd(year))
    b = jd_year(hijri_to_jd(year + 1) - 1)
    if a == b:
        return str(a)
    return f"{a}-{str(b)[-2:]}" if a // 100 == b // 100 else f"{a}-{b}"


# --- reading ----------------------------------------------------------------------------

def clean(text):
    # a few YÖK records carry C1 control characters that YAML refuses
    return re.sub(r"[\x80-\x9f]", "", text)


def front_matter(path):
    return yaml.safe_load(clean(path.read_text(encoding="utf-8")).split("---")[1])


def load_yaml(path):
    return yaml.safe_load(clean(path.read_text(encoding="utf-8")))


YOK_DETAIL = "https://tez.yok.gov.tr/UlusalTezMerkezi/tezDetay.jsp?id="
YOK_PDF = "https://tez.yok.gov.tr/UlusalTezMerkezi/TezGoster?key="


def short(url, prefix):
    if not url:
        return None
    return url[len(prefix):] if url.startswith(prefix) else url


def cite(source):
    """Reference to the page of al-Fawa'id al-bahiyya, in the three languages."""
    page = source.get("page")
    if not page:
        return None
    return {
        "tr": f"el-Fevâidü'l-behiyye, s. {page}",
        "en": f"al-Fawāʾid al-bahiyya, p. {page}",
        "ar": f"الفوائد البهية، ص {page}",
    }


def compact(d):
    """Drops empty values so the JSON stays small."""
    return {k: v for k, v in d.items() if v not in (None, "", [], {})}


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    src = Path(sys.argv[1]).resolve()
    places = load_yaml(src / "src/data/places.yaml")
    work_scholars = json.loads((src / "src/data/work-scholars.json").read_text(encoding="utf-8"))

    theses_about = {}
    for work, ids in work_scholars.items():
        for sid in ids:
            theses_about.setdefault(sid, []).append(work)

    # jurists and the works named in their biographies
    jurists, classics = [], []
    for path in sorted((src / "src/content/scholars").glob("*.md")):
        d = front_matter(path)
        sid = path.stem
        death = d.get("death") or {}
        birth = d.get("birth") or {}
        dh = death.get("hijri")
        madhhab = d.get("madhhab") if d.get("madhhab") in MADHHABS else "diger"
        death_place = places.get(death.get("place"), {}).get("name") if death.get("place") else None
        source = (d.get("sources") or [{}])[0]
        name = {"tr": d["name"]["tr"], "en": d["name"]["en"], "ar": d["name"]["ar"]}
        jurists.append(compact({
            "id": sid,
            "name": name,
            "madhhab": madhhab,
            "birth": birth.get("hijri"),
            "birthM": miladi(birth["hijri"]) if birth.get("hijri") else None,
            "death": dh,
            "deathM": miladi(dh) if dh else None,
            "approx": bool(death.get("approx")) or None,
            "place": death_place,
            "works": len(d.get("works") or []),
            "theses": len(theses_about.get(sid, [])),
            "summary": compact(d.get("summary") or {}),
            "source": cite(source),
            "order": d.get("order"),
            "featured": bool(d.get("featured")) or None,
        }))
        for w in d.get("works") or []:
            classics.append(compact({
                "title": w.get("ar"),
                "titleTr": w.get("tr"),
                "titleEn": w.get("en"),
                "author": name,
                "authorId": sid,
                "death": dh,
                "deathM": miladi(dh) if dh else None,
                "madhhab": madhhab,
                "source": cite(source),
            }))

    names = {j["id"]: j["name"] for j in jurists}

    # theses
    theses = []
    for path in sorted((src / "src/content/works").glob("*.y*ml")):
        d = load_yaml(path)
        if not d["type"].startswith("tez-"):
            continue
        tt = d.get("titleTranslation") or {}
        theses.append(compact({
            "title": d["title"],
            "titleTr": d.get("titleTranslated") or tt.get("tr") or tt.get("en"),
            "author": "; ".join(d.get("authors") or []),
            "advisor": "; ".join(d.get("advisors") or []),
            "type": "doktora" if d["type"] == "tez-doktora" else "yl",
            "university": d.get("university"),
            "department": d.get("department"),
            "city": d.get("city"),
            "year": d.get("year"),
            "lang": d.get("language"),
            "pages": d.get("pageCount"),
            "topics": ", ".join(d.get("topics") or []),
            "yokNo": d.get("yokId") or d.get("yokNo"),
            # only the query values are kept; the page adds the YÖK addresses back
            "yok": short(d.get("url"), YOK_DETAIL),
            "pdf": short(d.get("fullText"), YOK_PDF),
            "jurists": [names[s] for s in work_scholars.get(path.stem, []) if s in names],
        }))
    theses.sort(key=lambda t: (-(t.get("year") or 0), t["author"]))

    OUT.mkdir(exist_ok=True)
    for name, rows in (("fukaha", jurists), ("klasik-eserler", classics), ("tezler", theses)):
        path = OUT / f"{name}.json"
        path.write_text(json.dumps(rows, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"{path.relative_to(ROOT)}: {len(rows)} kayıt, {path.stat().st_size // 1024} KB")

    # home page: counts, newest theses, jurists most written about
    latest = sorted(theses, key=lambda t: (t.get("year") or 0, t.get("yokNo") or 0), reverse=True)[:12]
    studied = sorted(jurists, key=lambda j: (-j.get("theses", 0), j.get("death") or 9999))[:4]
    stats = {
        "counts": {
            "klasik": len(classics),
            "kitaplar": len(json.loads((OUT / "kitaplar.json").read_text(encoding="utf-8"))),
            "tezler": len(theses),
            "makaleler": len(json.loads((OUT / "makaleler.json").read_text(encoding="utf-8"))),
            "fukaha": len(jurists),
        },
        "latest_theses": [
            {k: t.get(k) for k in ("title", "titleTr", "author", "type", "university", "year", "lang", "yok")}
            for t in latest
        ],
        "jurists": [
            {k: j.get(k) for k in ("id", "name", "madhhab", "death", "deathM", "summary", "theses", "works")}
            for j in studied
        ],
    }
    path = ROOT / "_data/stats.yml"
    header = "# Written by tools/import_fuqaha.py.\n"
    path.write_text(header + yaml.safe_dump(stats, allow_unicode=True, sort_keys=False, width=1000), encoding="utf-8")
    print(f"{path.relative_to(ROOT)} yazıldı")


if __name__ == "__main__":
    main()
