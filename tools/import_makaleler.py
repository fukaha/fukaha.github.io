#!/usr/bin/env python3
"""Builds the articles table from DergiPark search exports.

    python3 tools/import_makaleler.py

Reads every tools/makaleler/*.csv (DergiPark “article search export”, one row per article) and
tools/makaleler/fakihler.tsv (DergiPark record number <tab> jurist ids, kept by hand).

Writes:
  data/makaleler.json       the articles
  _data/makale_fakih.json   the articles about each jurist, keyed by jurist id, for the jurist pages
  _data/stats.yml           only the article count is changed
"""
import csv
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "tools/makaleler"

TYPES = {"Araştırma Makalesi": "arastirma", "Kitap İncelemesi": "inceleme", "Çeviri": "ceviri"}
SMALL = {"b.", "ve", "ile", "ya", "veya", "ki", "de", "da", "bir", "ın", "in", "un", "ün", "nin", "nın"}


def tr_lower(s):
    return s.replace("I", "ı").replace("İ", "i").lower()


def tr_upper_first(w):
    return {"i": "İ", "ı": "I"}.get(w[:1], w[:1].upper()) + w[1:]


def title_case(t):
    """Titles typed in capitals are set in title case; everything else is kept as written."""
    letters = [c for c in t if c.isalpha()]
    if not letters or sum(c.isupper() for c in letters) / len(letters) < 0.8:
        return t
    out = []
    for i, word in enumerate(tr_lower(t).split(" ")):
        # el-, fi’l-, ve’n- … stay lower case; the part after the article is capitalised
        parts = re.split(r"(-)", word)
        fixed = []
        for p in parts:
            core = re.sub(r"^[“\"‘'(]+", "", p)
            lead = p[: len(p) - len(core)]
            if core and (i == 0 or core not in SMALL) and not re.match(r"^(el|fi’l|fi'l|ve’n|ve'n|alâ’l|'alâ'l)$", core):
                core = tr_upper_first(core)
            fixed.append(lead + core)
        out.append("".join(fixed))
    return " ".join(out)


def people(cell):
    """“Ad Soyad (Kurum); Ad Soyad” → “Ad Soyad; Ad Soyad”."""
    names = [re.sub(r"\s*\(.*?\)\s*$", "", p).strip() for p in cell.split(";")]
    return "; ".join(n for n in names if n)


def guess_lang(title):
    return "ar" if re.search(r"[؀-ۿ]", title) else "tr"


def main():
    jurists = {j["id"]: j["name"] for j in json.loads((ROOT / "data/fukaha.json").read_text(encoding="utf-8"))}
    links = {}
    for line in (SRC / "fakihler.tsv").read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        no, ids = line.split("\t")
        links[no.strip()] = [i for i in ids.strip().split(",") if i]
        for i in links[no.strip()]:
            if i not in jurists:
                raise SystemExit(f"fakihler.tsv: bilinmeyen fakih {i}")

    rows, seen = [], set()
    for path in sorted(SRC.glob("*.csv")):
        for r in csv.DictReader(path.open(encoding="utf-8-sig")):
            no = r["Kayıt No"].strip()
            if no in seen:
                continue
            seen.add(no)
            title = title_case(re.sub(r"\s+", " ", r["Başlık"]).strip())
            row = {
                "id": no,
                "title": title,
                "author": people(r["Yazar"]),
                "translator": people(r["Çevirmen"]),
                "journal": r["Dergi Adı"].strip(),
                "volume": r["Cilt"].strip(),
                "issue": r["Sayı"].strip(),
                "pages": r["Sayfalar"].strip(),
                "year": int(r["Yıl"]) if r["Yıl"].strip().isdigit() else None,
                "lang": r["Birincil Dil"].strip() or guess_lang(title),
                "type": TYPES.get(r["Yayın Türü"].strip(), ""),
                "doi": r["DOI"].strip(),
                "keywords": ", ".join(k.strip() for k in re.split(r"[,;]", r["Anahtar Kelimeler"]) if k.strip()),
                "abstract": re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", r["Öz"]))).strip(),
                "jurists": [dict(jurists[i], id=i) for i in links.get(no, [])],
            }
            rows.append({k: v for k, v in row.items() if v not in ("", None, [])})
    rows.sort(key=lambda a: (-(a.get("year") or 0), a["title"]))

    out = ROOT / "data/makaleler.json"
    out.write_text(json.dumps(rows, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{out.relative_to(ROOT)}: {len(rows)} makale, {sum(1 for a in rows if a.get('jurists'))} tanesi fakihe bağlı")

    by_jurist = {}
    for a in rows:
        for j in a.get("jurists", []):
            by_jurist.setdefault(j["id"], []).append(
                {k: a[k] for k in ("title", "author", "journal", "volume", "issue", "year", "doi", "type") if k in a})
    (ROOT / "_data/makale_fakih.json").write_text(
        json.dumps(by_jurist, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")

    stats = ROOT / "_data/stats.yml"
    text = stats.read_text(encoding="utf-8")
    stats.write_text(re.sub(r"(?m)^  makaleler: \d+$", f"  makaleler: {len(rows)}", text), encoding="utf-8")


if __name__ == "__main__":
    main()
