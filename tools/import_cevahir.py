#!/usr/bin/env python3
"""Splits Ibn Abi al-Wafa's al-Jawahir al-mudiyya into its biographies.

    python3 tools/import_cevahir.py

Reads the OpenITI text in tools/cevahir/*.completed (mARkdown: “### $” starts a biography,
“### |” a book or letter, “### ||” a chapter, PageV01P032 ends page 32 of volume 1) and
tools/cevahir/fakihler.tsv (entry id <tab> jurist id <tab> note, checked by hand).

Writes:
  _data/cevahir.json        the parts and their entries, for the reading pages
  _data/cevahir_fakih.json  the entry about each jurist, keyed by jurist id, for the jurist pages
  data/cevahir.json         one short row per entry, for the searchable index
  _cevahir/<lang>/<part>.md one stub per part and language; the layout reads _data/cevahir.json
  _data/stats.yml           only the entry count is changed
"""
import json
import re
from pathlib import Path

from import_fuqaha import century, miladi

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "tools/cevahir"
LANGS = ("tr", "en", "ar")
BOOK = {"tr": "el-Cevâhirü’l-mudıyye", "en": "al-Jawāhir al-muḍiyya", "ar": "الجواهر المضية"}

# The letters of the main part, in the book's order: source heading word → slug, Turkish, English.
LETTERS = [
    ("الألف", "elif", "Elif", "Alif"), ("الباء", "be", "Be", "Bāʾ"), ("التاء", "te", "Te", "Tāʾ"),
    ("الثاء", "se", "Se", "Thāʾ"), ("الجيم", "cim", "Cîm", "Jīm"), ("الحاء", "ha", "Hâ", "Ḥāʾ"),
    ("الخاء", "hi", "Hı", "Khāʾ"), ("الدال", "dal", "Dâl", "Dāl"), ("الذال", "zel", "Zel", "Dhāl"),
    ("الراء", "ra", "Râ", "Rāʾ"), ("الزاي", "ze", "Ze", "Zāy"), ("السين", "sin", "Sîn", "Sīn"),
    ("الشين", "shin", "Şın", "Shīn"), ("الصاد", "sad", "Sâd", "Ṣād"), ("الضاد", "dad", "Dâd", "Ḍād"),
    ("الطاء", "ta", "Tı", "Ṭāʾ"), ("الظاء", "za", "Zı", "Ẓāʾ"), ("العين", "ayn", "Ayn", "ʿAyn"),
    ("الغين", "gayn", "Gayn", "Ghayn"), ("الفاء", "fe", "Fe", "Fāʾ"), ("القاف", "kaf", "Kaf", "Qāf"),
    ("الكاف", "kef", "Kef", "Kāf"), ("اللام", "lam", "Lâm", "Lām"), ("الميم", "mim", "Mîm", "Mīm"),
    ("النون", "nun", "Nûn", "Nūn"), ("الهاء", "he", "He", "Hāʾ"), ("الواو", "vav", "Vav", "Wāw"),
    ("الياء", "ye", "Ye", "Yāʾ"),
]

GLYPHS = "ابتثجحخدذرزسشصضطظعغفقكلمنهوي"

# The books after the letters. The source heading is the key; the kunya book has an empty heading.
BOOKS = {
    "kuna": ("kunyeler", "Künyeler", "Kunyas", "كتاب الكنى"),
    "كتاب الذيل على الكنى": ("kunyeler-zeyl", "Künyeler zeyli", "Kunyas, supplement", "كتاب الذيل على الكنى"),
    "كتاب النساء": ("kadinlar", "Kadınlar", "Women", "كتاب النساء"),
    "كتاب الأنساب": ("nisbeler", "Nisbeler", "Nisbas", "كتاب الأنساب"),
    "كتاب الألقاب": ("lakaplar", "Lakaplar", "Honorifics", "كتاب الألقاب"),
    "كتاب من عرف بابن فلان": ("ibn", "İbn … diye tanınanlar", "Known as Ibn …", "كتاب من عرف بابن فلان"),
}

UNITS = {"واحد": 1, "واحدة": 1, "إحدى": 1, "احدى": 1, "أحد": 1, "احد": 1, "اثنتين": 2, "اثنين": 2,
         "اثنتي": 2, "اثني": 2, "ثنتين": 2, "ثلاث": 3, "ثلاثة": 3, "ثلث": 3, "أربع": 4, "اربع": 4, "أربعة": 4,
         "خمس": 5, "خمسة": 5, "ست": 6, "ستة": 6, "سبع": 7, "سبعة": 7, "ثمان": 8, "ثماني": 8, "ثمانية": 8,
         "تسع": 9, "تسعة": 9}
TENS = {"عشرين": 20, "ثلاثين": 30, "ثلثين": 30, "أربعين": 40, "اربعين": 40, "خمسين": 50, "ستين": 60,
        "سبعين": 70, "ثمانين": 80, "تسعين": 90}
HUNDRED = {"مائة", "مئة", "ماية", "مائه"}
DIED = re.compile(r"(?:^|\s)[وف]?(?:مات|ماتت|توفي|توفى|توفيت|وفاته|وفاتها|قتل|استشهد|درج)(?=\s|$)")


def year_words(words):
    """[“ست”, “وأربعين”, “وأربع”, “مائة”] → 446; None when the words are not a year."""
    total, unit, seen = 0, None, False
    for i, w in enumerate(words):
        joined = w.startswith("و") and w[1:] not in ("احد",)
        core = w[1:] if joined and (w[1:] in UNITS or w[1:] in TENS or w[1:] in HUNDRED
                                    or w[1:].startswith(("مائت", "عشر")) or re.match(r".+(مائة|مئة|ماية)$", w[1:])) else w
        if core.isdigit():
            return int(core) if not seen else None
        if core in UNITS:
            if unit is not None:
                total += unit
            unit = UNITS[core]
        elif core in ("عشر", "عشرة"):
            total += (unit or 0) + 10
            unit = None
        elif core in TENS:
            total += (unit or 0) + TENS[core]
            unit = None
        elif core in HUNDRED:
            total += unit * 100 if unit and not joined else (unit or 0) + 100
            unit = None
        elif core.startswith("مائت"):
            total += (unit or 0) + 200
            unit = None
        elif m := re.match(r"^(\w+?)(مائة|مئة|ماية)$", core):
            if m.group(1) not in UNITS:
                break
            total += (unit or 0) + UNITS[m.group(1)] * 100
            unit = None
        else:
            break
        seen = True
    if unit is not None:
        total += unit
    return total if seen else None


def death_year(text):
    """The year after the first “died … in the year …” of the entry."""
    for m in DIED.finditer(text):
        rest = text[m.end():].split()[:22]
        for i, w in enumerate(rest):
            if w in ("سنة", "سنه", "عام"):
                y = year_words(rest[i + 1:i + 8])
                if y and 90 <= y <= 780:
                    return y
                break
    return None


STOP = re.compile(r"^(قال|كان|تفقه|سمع|روى|ذكره|ذكر|مات|توفي|توفى|ولد|يأتي|ياتي|تقدم|له|من|أحد|احد|حدث|سكن|قدم|"
                  r"ولي|تولى|درس|أخذ|اخذ|صاحب|والد|وهو|هو|شيخ|نسبة|بفتح|بضم|بكسر|لقب|فقيه|الفقيه|الإمام|الامام|"
                  r"الشيخ|القاضي|العلامة|الحافظ)$")


def head(text):
    """The name at the start of an entry: the words before the first verb or description."""
    words = text.split()
    out = []
    for w in words[:16]:
        if w == "تكرر":  # the editor's mark for a repeated entry
            break
        if out and len(out) >= 2 and STOP.match(w):
            break
        out.append(w)
    while len(out) > 2 and out[-1] in ("بن", "ابن", "أبو", "أبي", "ابو", "ابي", "و"):
        out.pop()
    return " ".join(out).rstrip("،,.")


def clean(line):
    line = re.sub(r"\bms\d+\b", "", line)
    line = re.sub(r"(\s*%)+\s*", " ٭ ", line)  # verse halves
    line = line.replace("@QB@", "﴿").replace("@QE@", "﴾")
    line = re.sub(r"﴿\s+", "﴿", line)
    line = re.sub(r"\s+﴾", "﴾", line)
    return re.sub(r"\s+", " ", line).strip()


def parse(path):
    """Yields (kind, value) events in book order: part, chapter, entry, text, para, page."""
    body = path.read_text(encoding="utf-8").split("#META#Header#End#", 1)[1]
    for raw in body.splitlines():
        line = raw.rstrip()
        if not line:
            continue
        m = re.match(r"^### (\|+|\$\$|\$DIC_NIS\$|\$)\s*(.*)$", line)
        if m:
            mark, rest = m.groups()
            if mark == "|PARATEXT|" or rest.startswith("|PARATEXT|"):
                yield "stop", None
                return
            if mark == "|":
                yield "part", clean(rest)
            elif mark.startswith("|"):
                yield "chapter", (len(mark), clean(rest))
            else:
                n, _, rest = rest.partition(" ")
                yield "entry", {"$": "tercume", "$$": "tercume", "$DIC_NIS$": "nisbe"}[mark]
                yield from text_events(rest)
            continue
        if line.startswith("~~"):
            yield from text_events(line[2:])
        elif line.startswith("#"):
            yield "para", None
            yield from text_events(line.lstrip("#* "))


def text_events(s):
    pos = 0
    for m in re.finditer(r"PageV(\d+)P(\d+)", s):
        yield "text", s[pos:m.start()]
        yield "page", (int(m.group(1)), int(m.group(2)))
        pos = m.end()
    yield "text", s[pos:]


def build(path):
    parts, part, chapter, entry = [], None, None, None
    pending = []     # entries still waiting for the page they start on
    in_main = False  # between “حرف الألف” and the kunya book
    in_manaqib = False
    count = 0

    def new_part(slug, tr, en, ar, kind):
        p = {"slug": slug, "title": {"tr": tr, "en": en, "ar": ar}, "kind": kind, "entries": []}
        parts.append(p)
        return p

    def start(kind, name=None):
        nonlocal entry, count
        count += 1
        entry = {"id": count, "kind": kind, "chapter": chapter, "paras": [""]}
        if name:
            entry["name"] = name
        part["entries"].append(entry)
        pending.append(entry)

    for ev, val in parse(path):
        if ev == "stop":
            break
        if ev == "part":
            chapter, entry = None, None
            if val.startswith("حرف"):
                in_main = True
                word = val.split()[-2] if val.endswith(("المهملة", "المعجمة", "الموحدة", "المثلثة", "الفاء", "القاف",
                                                        "الكاف", "اللام", "الميم", "النون", "الهاء", "الواو")) else None
                hit = next((x for x in LETTERS if x[0] in val), None)
                if "المعتنقة" in val:
                    part = None
                    continue
                if not hit:
                    raise SystemExit(f"bilinmeyen harf başlığı: {val}")
                ar, slug, tr, en = hit
                part = new_part(slug, f"{tr} harfi", f"Letter {en}", val.split(" فارغ")[0], "harf")
                part["letter"] = GLYPHS[LETTERS.index(hit)]
            elif val == "" and in_main:
                slug, tr, en, ar = BOOKS["kuna"]
                part = new_part(slug, tr, en, ar, "kitap")
            elif val in BOOKS:
                slug, tr, en, ar = BOOKS[val]
                part = new_part(slug, tr, en, ar, "kitap")
            elif val.startswith("المقدمة"):
                part = None
            elif val.startswith("الكتاب الجامع"):
                part = None
                in_main = False
            else:
                part = None
            in_manaqib = False
            continue
        if ev == "chapter":
            level, title = val
            if level == 2 and title.startswith("الباب الثالث"):
                # Abu Hanifa's virtues, abridged from the author's al-Bustan: one entry of its own.
                part = new_part("ebu-hanife", "İmam Ebû Hanîfe", "Imam Abu Hanifa", "الإمام أبو حنيفة", "kitap")
                chapter = None
                start("menakib", "أبو حنيفة النعمان بن ثابت")
                entry["intro"] = title
                in_manaqib = True
                continue
            if in_manaqib and level == 2:
                in_manaqib, part, entry = False, None, None
                continue
            if in_manaqib:
                entry["paras"].append("")
                entry.setdefault("sections", []).append(len(entry["paras"]) - 1)
                entry["paras"][-1] = "§" + title
                entry["paras"].append("")
                continue
            if part is None:
                continue
            if level == 2:
                chapter = title
            elif level == 3:
                chapter = (chapter.split(" · ")[0] + " · " + title) if chapter else title
            entry = None
            continue
        if part is None:
            continue
        if ev == "entry":
            if part["slug"] in ("nisbeler", "lakaplar") or val == "nisbe":
                start("nisbe" if part["slug"] != "lakaplar" else "lakap")
            else:
                start({"kunyeler": "kunye", "kunyeler-zeyl": "kunye", "kadinlar": "kadin",
                       "ibn": "ibn"}.get(part["slug"], "tercume"))
        elif ev == "para" and entry:
            if entry["paras"][-1].strip():
                entry["paras"].append("")
        elif ev == "text" and entry:
            entry["paras"][-1] += " " + val
        elif ev == "page":
            for e in pending:
                e["vol"], e["page"] = val
            pending.clear()
            if entry:
                entry["end"] = val[1]

    for p in parts:
        for e in p["entries"]:
            paras = [clean(x) for x in e["paras"]]
            e["paras"] = [x for x in paras if x and x != "§"]
            text = " ".join(x for x in e["paras"] if not x.startswith("§"))
            if e["kind"] == "nisbe":
                e.setdefault("name", e["paras"][0].split()[0])
            elif e["kind"] == "lakap":
                e.setdefault("name", head(" ".join(e["paras"][0].split()[:5])))
            else:
                e.setdefault("name", head(e["paras"][0]))
            e["death"] = death_year(text)
            e["refonly"] = len(text.split()) <= 12 and ("تقدم" in text or "يأتي" in text or len(text.split()) <= 6)
            if e.get("end") == e.get("page"):
                e.pop("end", None)
    return [p for p in parts if p["entries"]]


def main():
    src = next(SRC.glob("*.completed"))
    parts = build(src)

    entries = {e["id"]: e for p in parts for e in p["entries"]}
    links = {}  # entry id → jurist ids
    jurists = {j["id"]: j for j in json.loads((ROOT / "data/fukaha.json").read_text(encoding="utf-8"))}
    for line in (SRC / "fakihler.tsv").read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        eid, jid, *note = line.split("\t")
        eid, jid = int(eid), jid.strip()
        if jid not in jurists:
            raise SystemExit(f"fakihler.tsv: bilinmeyen fakih {jid}")
        # The note starts with the entry's first words: a check that the numbering has not moved.
        head_words = note[0].split(" · ")[0].split()[:3] if note else []
        if head_words and entries[eid]["paras"][0].split()[:len(head_words)] != head_words:
            raise SystemExit(f"fakihler.tsv: {eid} numaralı madde değişmiş görünüyor ({note[0]})")
        links.setdefault(eid, []).append(jid)

    rows, by_jurist, pages = [], {}, []
    for p in parts:
        out = []
        for e in p["entries"]:
            item = {"id": e["id"], "name": e["name"], "paras": e["paras"]}
            for k in ("chapter", "vol", "page", "end", "death", "intro"):
                if e.get(k):
                    item[k] = e[k]
            if e["kind"] not in ("tercume", "menakib"):
                item["kind"] = e["kind"]
            if e["refonly"]:
                item["ref"] = True
            jids = links.get(e["id"], [])
            if jids:
                item["jurists"] = jids
            for jid in jids:
                by_jurist[jid] = {k: v for k, v in {"id": e["id"], "part": p["slug"], "name": e["name"], "vol": e.get("vol"),
                                                     "page": e.get("page"), "end": e.get("end"),
                                                     "paras": e["paras"]}.items() if v}
            out.append(item)

            row = {"id": e["id"], "part": p["slug"], "partName": p["title"], "name": e["name"],
                   "kind": e["kind"], "vol": e.get("vol"), "page": e.get("page"),
                   "cite": f"{e.get('vol')}/{e.get('page')}" if e.get("page") else None}
            # A linked jurist's own year of death is checked; the one read from the entry is a guess.
            death = next((jurists[j]["death"] for j in jids if jurists[j].get("death")), e["death"])
            if death:
                row.update(death=death, deathM=miladi(death), century=century(death))
            if jids:
                row.update(jurists=[dict(jurists[j]["name"], id=j) for j in jids])
            if e["refonly"]:
                row["ref"] = True
            rows.append({k: v for k, v in row.items() if v not in (None, "", [])})
        pages.append({k: v for k, v in p.items() if k != "entries"} | {"count": len(out), "entries": out})

    (ROOT / "_data/cevahir.json").write_text(json.dumps({"parts": pages}, ensure_ascii=False, separators=(",", ":")),
                                            encoding="utf-8")
    (ROOT / "_data/cevahir_fakih.json").write_text(json.dumps(by_jurist, ensure_ascii=False, indent=1, sort_keys=True),
                                                  encoding="utf-8")
    (ROOT / "data/cevahir.json").write_text(json.dumps(rows, ensure_ascii=False, separators=(",", ":")),
                                           encoding="utf-8")

    stubs = ROOT / "_cevahir"
    for lang in LANGS:
        d = stubs / lang
        d.mkdir(parents=True, exist_ok=True)
        for old in d.glob("*.md"):
            old.unlink()
        for p in parts:
            title = f"{p['title'][lang]} · {BOOK[lang]}"
            (d / f"{p['slug']}.md").write_text(
                f"---\ntitle: {json.dumps(title, ensure_ascii=False)}\npart: {p['slug']}\n---\n", encoding="utf-8")

    stats = ROOT / "_data/stats.yml"
    text = stats.read_text(encoding="utf-8")
    n = len(rows)
    if re.search(r"(?m)^  cevahir: \d+$", text):
        text = re.sub(r"(?m)^  cevahir: \d+$", f"  cevahir: {n}", text)
    else:
        text = re.sub(r"(?m)^(  makaleler: \d+)$", rf"\1\n  cevahir: {n}", text)
    stats.write_text(text, encoding="utf-8")

    kinds = {}
    for r in rows:
        kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
    print(f"{len(parts)} kısım, {n} madde {kinds}; vefat yılı bulunan {sum(1 for r in rows if 'death' in r)}; "
          f"fakihe bağlı {len(by_jurist)}")


if __name__ == "__main__":
    main()
