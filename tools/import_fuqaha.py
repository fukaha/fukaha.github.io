#!/usr/bin/env python3
"""Builds the table data in data/*.json from a checkout of the Fuqaha archive.

    python3 tools/import_fuqaha.py ../fuqaha

Reads src/content/scholars/*.md (biographies from al-Laknawi's al-Fawa'id al-bahiyya),
src/content/works/*.yaml (theses) and src/data/*.  The source checkout is only read.

Writes:
  data/fukaha.json          jurists
  data/klasik-eserler.json  works named in the biographies
  data/tezler.json          MA and PhD theses
  _data/jurists.json        everything a jurist's own page shows, keyed by id
  _fakihler/<lang>/*.md     one stub per jurist and language; the layout reads _data/jurists.json
  _data/stats.yml           counts, charts and the short lists shown on the home page
  _data/places.json         the places on the map (coordinates from al-Thurayya where it has them)
  data/harita.json          places and jurists for the map page
  data/silsile.json         the teacher-student network, laid out along the years of death

Turkish readings of the Arabic work titles and of the teachers' and students' names come from
tools/translit/*.tsv (Arabic <tab> Turkish), kept by hand. tools/translit/eslesme.tsv ties names
written differently from a jurist's own entry (“صاحب الهداية”, “أبو يوسف”) to that jurist.
"""
import collections
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


def body(path):
    """The source text under the front matter, as paragraphs."""
    text = clean(path.read_text(encoding="utf-8")).split("---", 2)[2]
    return [p.replace("**", "").strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def century(h):
    return (h - 1) // 100 + 1 if h else None


LANGS = ("tr", "en", "ar")


def load_tsv(name):
    """Arabic → Turkish readings kept by hand in tools/translit/<name>.tsv."""
    rows = (line.split("\t") for line in (ROOT / "tools/translit" / f"{name}.tsv").read_text(encoding="utf-8").splitlines()
            if line and not line.startswith("#"))
    return {ar: tr for ar, tr in rows}


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


class NoAliases(yaml.SafeDumper):
    """Writes repeated objects out in full; Jekyll's YAML reader refuses anchors."""
    def ignore_aliases(self, data):
        return True


def compact(d):
    """Drops empty values so the JSON stays small."""
    return {k: v for k, v in d.items() if v not in (None, "", [], {})}


RELATION = re.compile(r"^(?:أبوه|ابنه|ابنته|ولده|والده|جده لأمه|جده|عمه|خاله|أخوه|حفيده|ابن ابنه|ابن أخيه|ابن أخته|أخو)\s+")
RELATION_TR = re.compile(r"^(?:babası|oğlu|kızı|anne tarafından dedesi|dedesi|amcası|dayısı|kardeşi|torunu|yeğeni|kız kardeşinin oğlu)\s+")


def network(pages, jurists):
    """The teacher-student network: every tie either side records, among jurists and the people
    they name who have no entry of their own. Written to data/silsile.json with a layout whose
    x is the year of death, and to each page as its two steps up and down ("ego")."""
    names = {j["id"]: j["name"] for j in jurists}
    death = {j["id"]: j.get("death") for j in jurists}
    outside = {}

    def key(x):
        if x.get("id"):
            return x["id"]
        ar = RELATION.sub("", x["ar"])  # "his father Hammad" and "Hammad" are one person
        if ar not in outside:
            outside[ar] = {"ar": ar, "tr": RELATION_TR.sub("", x.get("tr") or ar)}
        return "~" + ar

    edges = set()
    for sid, page in pages.items():
        for x in page.get("teachers", []):
            edges.add((key(x), sid))
        for x in page.get("students", []):
            edges.add((sid, key(x)))
    edges = sorted(e for e in edges if e[0] != e[1])
    up, down = collections.defaultdict(list), collections.defaultdict(list)
    for a, b in edges:
        down[a].append(b)
        up[b].append(a)

    def label(k):
        if k.startswith("~"):
            o = outside[k[1:]]
            return {"ar": o["ar"], "tr": o["tr"], "en": o["tr"]}
        return names[k]

    # each page: teachers and their teachers, students and their students
    for sid, page in pages.items():
        def node(k, more):
            n = compact({"id": None if k.startswith("~") else k, "n": label(k), "d": death.get(k)})
            if more:
                n["m"] = [compact({"id": None if m.startswith("~") else m, "n": label(m)}) for m in more[:6]]
            return n
        t = sorted(up.get(sid, []), key=lambda k: death.get(k) or 0)
        st = sorted(down.get(sid, []), key=lambda k: death.get(k) or 9999)
        if t or st:
            page["ego"] = {"t": [node(k, sorted(up.get(k, []), key=lambda m: death.get(m) or 0)) for k in t],
                           "s": [node(k, sorted(down.get(k, []), key=lambda m: death.get(m) or 9999)) for k in st]}

    # layout: x from the year of death; people without one sit a generation after their
    # teachers or before their students; y from a simple force layout
    keys = sorted({k for e in edges for k in e})
    x = {k: death.get(k) for k in keys}
    for _ in range(12):
        for k in keys:
            if x[k] is None or k.startswith("~"):
                guesses = [x[t] + 35 for t in up.get(k, []) if x.get(t) is not None and not t.startswith("~")] + \
                          [x[s] - 35 for s in down.get(k, []) if x.get(s) is not None and not s.startswith("~")]
                if not guesses:
                    guesses = [x[t] + 35 for t in up.get(k, []) if x.get(t) is not None] + \
                              [x[s] - 35 for s in down.get(k, []) if x.get(s) is not None]
                if guesses:
                    x[k] = sum(guesses) / len(guesses)
    keys = [k for k in keys if x[k] is not None]
    # columns of 25 years; within a column each person has a row of his own, and the rows are
    # ordered so that people sit near those they are tied to (a few barycentre sweeps)
    SLICE, GAP = 25, 24
    col = {k: int(x[k] // SLICE) for k in keys}
    cols = collections.defaultdict(list)
    for k in sorted(keys, key=lambda k: (-(len(up.get(k, [])) + len(down.get(k, []))), k)):
        cols[col[k]].append(k)
    nbr = {k: [n for n in up.get(k, []) + down.get(k, []) if n in col and col[n] != col[k]] for k in keys}

    def rows():
        return {k: i - (len(ks) - 1) / 2 for ks in cols.values() for i, k in enumerate(ks)}
    for sweep in range(10):
        pos = rows()
        order = sorted(cols) if sweep % 2 == 0 else sorted(cols, reverse=True)
        for c in order:
            ks = cols[c]
            bary = {k: (sum(pos[n] for n in nbr[k]) / len(nbr[k]) if nbr[k] else pos[k]) for k in ks}
            ks.sort(key=lambda k: bary[k])
            pos.update({k: i - (len(ks) - 1) / 2 for i, k in enumerate(ks)})
    pos = rows()
    x = {k: (col[k] + 0.5) * SLICE for k in keys}
    y = {k: pos[k] * GAP for k in keys}
    nodes = []
    index = {}
    for k in sorted(keys, key=lambda k: (x[k], y[k])):
        index[k] = len(nodes)
        n = {"x": x[k], "y": y[k], "n": label(k)}
        if not k.startswith("~"):
            n["id"] = k
            if death.get(k):
                n["d"] = death[k]
        nodes.append(n)
    links = [[index[a], index[b]] for a, b in edges if a in index and b in index]
    (OUT / "silsile.json").write_text(json.dumps({"nodes": nodes, "links": links}, ensure_ascii=False, separators=(",", ":")),
                                      encoding="utf-8")
    print(f"data/silsile.json: {len(nodes)} kişi, {len(links)} bağ, {sum(1 for n in nodes if n.get('id'))} fakih")


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    src = Path(sys.argv[1]).resolve()
    places = load_yaml(src / "src/data/places.yaml")
    work_scholars = json.loads((src / "src/data/work-scholars.json").read_text(encoding="utf-8"))

    names_ar, names_tr = {}, {}
    for path in sorted((src / "src/content/scholars").glob("*.md")):
        fm = front_matter(path)
        names_ar.setdefault(fm["name"]["ar"], path.stem)
        names_tr[path.stem] = fm["name"]["tr"]
    people_tr, works_tr, same = load_tsv("kisiler"), load_tsv("eserler"), load_tsv("eslesme")

    def place(pid):
        return places.get(pid, {}).get("name") if pid else None

    def geo(d):
        """Every place tied to a jurist, with its role: [[place id, role], ...]."""
        pairs = [[(d.get("birth") or {}).get("place"), "dogum"], [(d.get("death") or {}).get("place"), "vefat"]]
        pairs += [[x.get("place"), x.get("role")] for x in d.get("places") or []]
        out = []
        for pid, role in pairs:
            if pid in places and [pid, role] not in out:
                out.append([pid, role])
        return out

    theses_about = {}
    for work, ids in work_scholars.items():
        for sid in ids:
            theses_about.setdefault(sid, []).append(work)

    # jurists and the works named in their biographies
    jurists, classics, pages = [], [], {}
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
            "century": century(dh),
            "summary": compact(d.get("summary") or {}),
            "source": cite(source),
            "order": d.get("order"),
            "featured": bool(d.get("featured")) or None,
        }))
        def person(n):
            pid = names_ar.get(n) or same.get(n)
            pid = pid if pid != sid else None
            # a name written as in the jurist's own entry takes his name; "his father X" keeps its reading
            tr = names_tr[pid] if pid and n in names_ar else people_tr.get(n)
            return compact({"ar": n, "tr": tr, "id": pid})
        works = [compact({"ar": w.get("ar"), "tr": w.get("tr") or works_tr.get(w.get("ar")), "en": w.get("en")})
                 for w in d.get("works") or []]
        pages[sid] = compact({
            "name": name,
            "madhhab": madhhab,
            "birth": compact({"h": birth.get("hijri"), "m": miladi(birth["hijri"]) if birth.get("hijri") else None,
                              "place": place(birth.get("place"))}),
            "death": compact({"h": dh, "m": miladi(dh) if dh else None, "place": death_place,
                              "month": death.get("month"), "day": death.get("day"),
                              "alt": death.get("alt"), "approx": bool(death.get("approx")) or None}),
            "century": century(dh),
            "places": [compact({"place": place(x.get("place")), "role": x.get("role")}) for x in d.get("places") or [] if place(x.get("place"))],
            "geo": geo(d),
            "teachers": [person(n) for n in d.get("teachers") or []],
            "students": [person(n) for n in d.get("students") or []],
            "works": works,
            "summary": compact(d.get("summary") or {}),
            "source": compact({k: source.get(k) for k in ("book", "bookTr", "author", "authorTr", "edition", "page", "entry")}),
            "text": body(path),
            "order": d.get("order"),
        })
        for w in works:
            classics.append(compact({
                "title": w.get("ar"),
                "titleTr": w.get("tr"),
                "titleEn": w.get("en"),
                "author": name,
                "authorId": sid,
                "death": dh,
                "deathM": miladi(dh) if dh else None,
                "madhhab": madhhab,
                "century": century(dh),
                "source": cite(source),
            }))

    names = {j["id"]: j["name"] for j in jurists}

    # theses
    theses, by_stem = [], {}
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
            "jurists": [dict(names[s], id=s) for s in work_scholars.get(path.stem, []) if s in names],
        }))
        by_stem[path.stem] = theses[-1]
    theses.sort(key=lambda t: (-(t.get("year") or 0), t["author"]))

    for sid, page in pages.items():
        about = [by_stem[w] for w in theses_about.get(sid, []) if w in by_stem]
        about.sort(key=lambda t: (-(t.get("year") or 0), t["author"]))
        page["theses"] = [{k: t.get(k) for k in ("title", "author", "type", "university", "year", "lang", "yok")} for t in about]

    # neighbours in time: jurists with a known death year, in order
    dated = sorted((j for j in jurists if j.get("death")), key=lambda j: (j["death"], j.get("order") or 0))
    for i, j in enumerate(dated):
        page = pages[j["id"]]
        if i: page["prev"] = dated[i - 1]["id"]
        if i < len(dated) - 1: page["next"] = dated[i + 1]["id"]
        near = sorted(dated[max(0, i - 6):i] + dated[i + 1:i + 7], key=lambda o: abs(o["death"] - j["death"]))[:6]
        page["peers"] = sorted((o["id"] for o in near), key=lambda x: pages[x]["death"]["h"])
    # a jurist's places, each once with all its roles, for the small map on his page
    for page in pages.values():
        spots = {}
        for pid, role in page.get("geo", []):
            spots.setdefault(pid, []).append(role)
        if spots:
            page["spots"] = [{"id": pid, "roles": roles} for pid, roles in spots.items()]

    OUT.mkdir(exist_ok=True)
    network(pages, jurists)
    brief = {j["id"]: {k: j.get(k) for k in ("name", "death", "deathM", "madhhab")} for j in jurists}
    (ROOT / "_data/jurists.json").write_text(
        json.dumps({"pages": pages, "brief": brief}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    # the map: places in use and the jurists tied to them
    used = sorted({pid for page in pages.values() for pid, _ in page.get("geo", [])})
    geo_places = {pid: compact({
        "name": places[pid]["name"], "region": places[pid].get("regionId"),
        "lat": places[pid]["lat"], "lng": places[pid]["lng"],
        "uri": places[pid].get("uri") if places[pid].get("coordSource") == "thurayya" else None,
        "approx": places[pid].get("coordSource") != "thurayya" or None,
    }) for pid in used}
    (ROOT / "_data/places.json").write_text(json.dumps(geo_places, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    geo_jurists = [compact({"id": j["id"], "name": j["name"], "madhhab": j["madhhab"], "death": j.get("death"),
                            "deathM": j.get("deathM"), "century": j.get("century"), "geo": pages[j["id"]]["geo"]})
                   for j in jurists if pages[j["id"]].get("geo")]
    (OUT / "harita.json").write_text(json.dumps({"places": geo_places, "jurists": geo_jurists},
                                                ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    stubs = ROOT / "_fakihler"
    for lang in LANGS:
        folder = stubs / lang
        folder.mkdir(parents=True, exist_ok=True)
        for old in folder.glob("*.md"):
            old.unlink()
        for j in jurists:
            title = j["name"].get(lang) or j["name"]["tr"]
            summary = (j.get("summary") or {}).get(lang) or (j.get("summary") or {}).get("tr") or ""
            (folder / f"{j['id']}.md").write_text(
                "---\n" + yaml.safe_dump({"title": title, "summary": summary}, allow_unicode=True, width=1000) + "---\n",
                encoding="utf-8")

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
            "cevahir": len(json.loads((OUT / "cevahir.json").read_text(encoding="utf-8"))),
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
        # "jurist of the day": the 60 dated, summarised jurists with the most works and theses
        "daily": [
            {k: j.get(k) for k in ("id", "name", "madhhab", "death", "deathM", "place", "summary", "theses", "works")}
            for j in sorted(sorted((j for j in jurists if j.get("death") and j.get("summary") and (j["works"] or j["theses"])),
                                   key=lambda j: -(j["works"] + 3 * j["theses"]))[:60],
                            key=lambda j: j.get("order") or 0)
        ],
        "centuries": [{"c": c, "n": n} for c, n in sorted(collections.Counter(j["century"] for j in jurists if j.get("century")).items())],
        "undated": sum(1 for j in jurists if not j.get("century")),
        "places": [{"place": p, "n": n} for p, n in collections.Counter(
            json.dumps(j["place"], ensure_ascii=False, sort_keys=True) for j in jurists if j.get("place")).most_common(10)],
        "years": [{"y": y, "n": n} for y, n in sorted(collections.Counter(t["year"] for t in theses if t.get("year") and t["year"] >= 1990).items())],
        "years_before": sum(1 for t in theses if t.get("year") and t["year"] < 1990),
        "first_year": min(t["year"] for t in theses if t.get("year")),
        "universities": [{"name": u, "n": n} for u, n in collections.Counter(
            t["university"].split(",")[0] for t in theses if t.get("university")).most_common(8)],
        "topics": [{"name": x, "n": n} for x, n in collections.Counter(
            x.strip() for t in theses for x in (t.get("topics") or "").split(",") if x.strip()).most_common(10)],
        "thesis_langs": dict(collections.Counter(t.get("lang") for t in theses).most_common(3)),
        "doktora": sum(1 for t in theses if t["type"] == "doktora"),
    }
    for p in stats["places"]:
        p["place"] = json.loads(p["place"])
    path = ROOT / "_data/stats.yml"
    header = "# Written by tools/import_fuqaha.py.\n"
    path.write_text(header + yaml.dump(stats, Dumper=NoAliases, allow_unicode=True, sort_keys=False, width=1000), encoding="utf-8")
    print(f"{path.relative_to(ROOT)} yazıldı")


if __name__ == "__main__":
    main()
