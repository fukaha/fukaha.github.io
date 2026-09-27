"""Leknevî's al-Fawaid al-bahiyya, read letter by letter.

Reads tools/fevaid/fawaid-entries.json (the 525 entries of the book, from the fikhiefendi/fuqaha
sources) and writes
  _data/fevaid.json         the parts (one per letter) with their entries, for the reading pages
  _fevaid/<lang>/<slug>.md  one stub page per part and language
  data/fevaid.json          one row per entry, for the table of all entries
Every entry is the entry of one jurist page: entry n is the page whose source entry is n.
Run after tools/import_fuqaha.py.
"""
import json
import re
from pathlib import Path

from import_cevahir import GLYPHS, LETTERS, LANGS

ROOT = Path(__file__).resolve().parent.parent
BOOK = {"tr": "el-Fevâidü’l-behiyye", "en": "al-Fawāʾid al-bahiyya", "ar": "الفوائد البهية"}


def letter(section):
    words = re.sub(r"[()\[\]]", " ", section).split()
    for name, slug, tr, en in LETTERS:
        if name in words:
            return name, slug, tr, en
    raise SystemExit(f"harf bulunamadı: {section}")


def paras(text):
    # Leknevî's own remarks, "(قال الجامع)", start a paragraph of their own.
    text = re.sub(r"\s+", " ", text).strip()
    return [p.strip() for p in re.split(r"\s(?=\(قال الجامع\))", text) if p.strip()]


def main():
    entries = json.loads((ROOT / "tools/fevaid/fawaid-entries.json").read_text(encoding="utf-8"))
    pages = json.loads((ROOT / "_data/jurists.json").read_text(encoding="utf-8"))["pages"]
    by_entry = {str(v["source"]["entry"]): k for k, v in pages.items()}
    rows_fk = {r["id"]: r for r in json.loads((ROOT / "data/fukaha.json").read_text(encoding="utf-8"))}

    parts, rows = [], []
    for i, e in enumerate(entries, 1):
        name, slug, tr, en = letter(e["section"])
        if not parts or parts[-1]["slug"] != slug:
            parts.append({"slug": slug, "kind": "harf", "letter": GLYPHS[[l[1] for l in LETTERS].index(slug)],
                          "title": {"tr": f"{tr} harfi", "en": f"Letter {en}", "ar": f"حرف {name[2:]}"}, "entries": []})
        jid = by_entry.get(str(e["n"]))
        head = re.sub(r"[()]", "", e["heading"]).strip()
        item = {"id": i, "n": str(e["n"]), "name": head, "paras": paras(e["text"]),
                "page": e.get("pageStart"), "end": e.get("pageEnd") if e.get("pageEnd") != e.get("pageStart") else None,
                "jurists": [jid] if jid else None}
        parts[-1]["entries"].append({k: v for k, v in item.items() if v})
        j = rows_fk.get(jid, {})
        row = {"id": i, "n": str(e["n"]), "part": slug, "partName": parts[-1]["title"], "name": head,
               "page": e.get("pageStart"), "cite": f"{e.get('pageStart')}" + (f"-{e['pageEnd']}" if item.get("end") else ""),
               "death": j.get("death"), "deathM": j.get("deathM"), "century": j.get("century"),
               "jurists": [dict(j["name"], id=jid)] if jid and j else None}
        rows.append({k: v for k, v in row.items() if v not in (None, "", [])})
    for p in parts:
        p["count"] = len(p["entries"])

    (ROOT / "_data/fevaid.json").write_text(json.dumps({"parts": parts}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (ROOT / "data/fevaid.json").write_text(json.dumps(rows, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    for lang in LANGS:
        d = ROOT / "_fevaid" / lang
        d.mkdir(parents=True, exist_ok=True)
        for old in d.glob("*.md"):
            old.unlink()
        for p in parts:
            title = f"{p['title'][lang]} · {BOOK[lang]}"
            (d / f"{p['slug']}.md").write_text(
                f"---\ntitle: {json.dumps(title, ensure_ascii=False)}\npart: {p['slug']}\nbook: fevaid\n---\n", encoding="utf-8")
    stats = ROOT / "_data/stats.yml"
    text = stats.read_text(encoding="utf-8")
    if re.search(r"(?m)^  fevaid: \d+$", text):
        text = re.sub(r"(?m)^  fevaid: \d+$", f"  fevaid: {len(rows)}", text)
    else:
        text = re.sub(r"(?m)^(  cevahir: \d+)$", rf"\1\n  fevaid: {len(rows)}", text)
    stats.write_text(text, encoding="utf-8")
    print(f"{len(parts)} harf, {len(rows)} madde; fakih sayfasına bağlı {sum(1 for r in rows if 'jurists' in r)}")


if __name__ == "__main__":
    main()
