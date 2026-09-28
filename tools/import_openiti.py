#!/usr/bin/env python3
"""Ties the classical works and the jurists to the books and authors of the OpenITI corpus.

The KITAB project publishes OpenITI, a corpus of premodern Arabic texts (CC BY-NC-SA 4.0). Its
metadata, tools/openiti/OpenITI_metadata_*.tsv (from Zenodo), gives each text's author, year of
death, title and edition. A work of ours matches a text when the years of death agree (±1) and the
titles share their distinctive words; a jurist matches an author when the years agree and the
names share distinctive words. Matches the scorer is unsure of go to tools/openiti/eslesme.tsv,
where a line "work|jurist <tab> our id <tab> OpenITI URI <tab> + or -" confirms or rejects one.

Writes
  _data/openiti.json   our work and jurist ids → OpenITI texts, for the pages
  data/openiti.json    the same, with the metadata of every matched text, for other applications
Run after tools/import_fuqaha.py and tools/import_cevahir.py.
"""
import csv
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "tools/openiti"
RAW = "https://raw.githubusercontent.com/OpenITI/{repo}/master/data/{author}/{book}/{version}"

STOP = set("""في على من عن إلى الى و أو ما بن ابن بنت أبو أبي أبى أم عبد كتاب رسالة شرح حاشية مختصر الشيخ الإمام الامام
الفقيه القاضي محمد أحمد علي حسن حسين عمر عثمان إبراهيم يوسف الدين المتوفى المتوفي هـ ت""".split())
WEAK_TITLE = {"شرح", "حاشية", "مختصر", "كتاب", "رسالة", "المختصر", "الشرح", "الحاشية"}


def norm(s):
    s = re.sub("[ً-ْـٰ]", "", s or "")
    s = re.sub("[أإآٱ]", "ا", s).replace("ى", "ي").replace("ة", "ه").replace("ؤ", "و").replace("ئ", "ي")
    s = re.sub(r"[^ء-ي\s]", " ", s)
    return s.split()


def words(s, stop=STOP):
    out = set()
    for w in norm(s):
        w = w[2:] if w.startswith("ال") and len(w) > 3 else w
        if len(w) > 1 and w not in stop and w not in {norm(x)[0] if norm(x) else x for x in ()}:
            out.add(w)
    return out - {x[2:] if x.startswith("ال") else x for x in (" ".join(norm(" ".join(STOP)))).split()}


def lead(title):
    """The first two distinctive words of a title, in order."""
    out = []
    for w in norm(title):
        w = w[2:] if w.startswith("ال") and len(w) > 3 else w
        if len(w) > 1 and w not in STOP and w not in WEAK_TITLE:
            out.append(w)
        if len(out) == 2:
            break
    return out


def raw_url(uri, date, path=""):
    """The address of the text in its OpenITI repository (one repository per 25 years of death dates)."""
    author, book = uri.split(".")[0], ".".join(uri.split(".")[:2])
    y = int(date)
    repo = f"{((y - 1) // 25 + 1) * 25:04d}AH"
    ext = path.rsplit(".", 1)[-1] if path.rsplit(".", 1)[-1] in ("completed", "mARkdown", "inProgress") else ""
    return RAW.format(repo=repo, author=author, book=book, version=uri) + (f".{ext}" if ext else "")


def load_texts():
    path = next(SRC.glob("OpenITI_metadata_*.tsv"))
    texts = []
    for r in csv.DictReader(path.open(encoding="utf-8"), delimiter="\t"):
        if r["language"] != "ara":
            continue
        try:
            date = int(float(r["date"]))
        except ValueError:
            continue
        uri = r["version_uri"]
        texts.append({
            "uri": uri, "book": r["book"], "date": date, "author_ar": r["author_ar"].split("::")[0].strip(),
            "author_lat": r["author_lat"], "title_ar": r["title_ar"].split("::")[0].strip(), "title_lat": r["title_lat"],
            "edition": r["ed_info"].split("::")[-1].strip() if r["ed_info"] else "", "words": int(float(r["tok_length"] or 0)),
            "hanafi": bool(re.search(r"hanaf|حنفي|الحنفي", r["tags"], re.I)), "ocr": r["uncorrected_OCR"] == "True",
            "raw": raw_url(uri, date, r["local_path"]),
        })
    return texts


def overlap(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def reviewed():
    out = {}
    path = SRC / "eslesme.tsv"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.startswith("#"):
                continue
            kind, oid, uri, verdict, *_ = line.split("\t") + ["", ""]
            out[(kind, oid, uri)] = verdict.strip()
    return out


def main():
    texts = load_texts()
    by_year = defaultdict(list)
    for t in texts:
        by_year[t["date"]].append(t)
    near = lambda y: [t for d in (y - 1, y, y + 1) for t in by_year.get(d, [])]
    verdicts = reviewed()
    review = []

    works = json.loads((ROOT / "data/klasik-eserler.json").read_text(encoding="utf-8"))
    jurists = [j for j in json.loads((ROOT / "data/fukaha.json").read_text(encoding="utf-8")) if not str(j["id"]).startswith("cv-")]

    def decide(kind, oid, t, score, auto, low, label):
        v = verdicts.get((kind, oid, t["uri"]))
        if v == "+":
            return True
        if v == "-":
            return False
        if score >= auto:
            return True
        if score >= low:
            review.append(f"{kind}\t{oid}\t{t['uri']}\t?\t{score:.2f} · {label} · {t['title_ar']} · {t['author_ar']}")
        return False

    work_map, jurist_map, used = {}, defaultdict(list), {}
    death_of = {j["id"]: j.get("death") for j in jurists}
    for i, w in enumerate(works):
        death = w.get("death") or death_of.get(w.get("authorId"))
        if not death:
            continue
        oid = str(i)
        tw = words(w["title"]) - WEAK_TITLE
        head = lead(w["title"])
        aw = words(w["author"]["ar"]) if isinstance(w.get("author"), dict) else set()
        best = []
        for t in near(int(death)):
            s = overlap(tw, words(t["title_ar"]) - WEAK_TITLE)
            # the same weak head ("شرح", "حاشية") must also agree
            if s and (("شرح" in w["title"]) != ("شرح" in t["title_ar"])):
                s *= 0.7
            # the first two distinctive words of the title are the title ("بدائع الصنائع ...")
            if len(head) == 2 and head == lead(t["title_ar"]):
                s = max(s, 0.8)
            # the author must share a distinctive word of his name too
            if s and aw and not aw & (words(t["author_ar"]) | words(t["title_ar"])):
                s *= 0.5
            if decide("work", oid, t, s, 0.75, 0.4, w["title"]):
                best.append((s, t))
        if best:
            best.sort(key=lambda x: (-x[0], x[1]["ocr"], -x[1]["words"]))
            t = best[0][1]
            work_map[oid] = t["uri"]
            used[t["uri"]] = t
            if w.get("authorId"):
                jurist_map[w["authorId"]].append(t["uri"])

    for j in jurists:
        if not j.get("death"):
            continue
        nw = words(j["name"]["ar"])
        for t in near(int(j["death"])):
            s = overlap(nw, words(t["author_ar"]))
            # two distinctive words of the name, or one when the years agree exactly and the name is short
            if len(nw & words(t["author_ar"])) < 2 and not (len(nw) == 1 and t["date"] == j["death"]):
                s = min(s, 0.5)
            if t["uri"] in jurist_map[j["id"]]:
                continue
            if decide("jurist", j["id"], t, s, 0.99, 0.55, j["name"]["tr"]):
                jurist_map[j["id"]].append(t["uri"])
                used[t["uri"]] = t

    jurist_map = {k: sorted(set(v)) for k, v in jurist_map.items() if v}
    # the works table carries the text of each matched work, for its "Text" column
    for i, w in enumerate(works):
        w.pop("oi", None)
        if str(i) in work_map:
            w["oi"] = work_map[str(i)]
    (ROOT / "data/klasik-eserler.json").write_text(json.dumps(works, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    site = {"works": work_map, "jurists": jurist_map,
            "texts": {u: {k: t[k] for k in ("title_ar", "title_lat", "author_ar", "date", "words", "edition", "raw", "ocr")}
                      for u, t in used.items()}}
    (ROOT / "_data/openiti.json").write_text(json.dumps(site, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (ROOT / "data/openiti.json").write_text(json.dumps(
        {"source": "OpenITI (KITAB project), CC BY-NC-SA 4.0, https://doi.org/10.5281/zenodo.3082463",
         "works": {works[int(k)]["title"]: v for k, v in work_map.items()}, **{k: v for k, v in site.items() if k != "works"}},
        ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    old = [l for l in ((SRC / "eslesme.tsv").read_text(encoding="utf-8").splitlines() if (SRC / "eslesme.tsv").exists() else [])
           if l.strip() and not l.startswith("#") and l.split("\t")[3].strip() in "+-" and l.split("\t")[3].strip()]
    (SRC / "eslesme.tsv").write_text(
        "# Tür\tbizim kimlik\tOpenITI URI\t+ (doğru) / - (yanlış) / ? (bakılmadı)\tpuan · bizim ad · OpenITI adı · müellif\n"
        + "\n".join(old + review) + "\n", encoding="utf-8")
    print(f"{len(texts)} Arapça metin; eşleşen eser {len(work_map)}/{len(works)}, fakih {len(jurist_map)}; "
          f"kontrol bekleyen {len(review)}; bağlanan metin {len(used)} ({sum(t['words'] for t in used.values()) // 10**6} M kelime)")


if __name__ == "__main__":
    main()
