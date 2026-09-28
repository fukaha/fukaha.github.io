#!/usr/bin/env python3
"""The search index of the core Hanafi books of OpenITI (tools/openiti/cekirdek.tsv).

The texts themselves stay in the OpenITI repositories. This script reads local copies of them
(downloaded from the addresses in _data/openiti.json / the metadata; pass their folder as the first
argument), cuts each into passages of about 300 words at paragraph ends, and writes to data/ara/:

  books.json       the books: title, author, year of death, raw address and byte size of the file
  passages.bin     12 bytes a passage: book (u16), volume (u16), page (u16), byte length (u16),
                   byte offset in the raw file (u32), little-endian. The site fetches a passage's
                   text with an HTTP range request on the raw file, so no text is stored here.
  t/<key>.bin      the word index, split by the first two letters of the stem. Each file holds
                   terms and, for each, the passages it is in: varint count, then varint gaps.
  manifest.json    counts, the list of index files and the stemming rules

Usage: python3 tools/build_search.py <folder with the raw texts, named by version URI>
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from import_openiti import load_texts  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/ara"
PASSAGE_WORDS = 300
PREFIXES = ["وال", "فال", "بال", "كال", "لل", "ال", "و", "ف", "ب", "ل", "ك"]

HARAKAT = re.compile("[ً-ْـٰ]")
NOT_ARABIC = re.compile(r"[^ء-ي]+")
PAGE = re.compile(rb"PageV(\d+)P(\d+)")


def norm(s):
    s = HARAKAT.sub("", s)
    s = re.sub("[أإآٱ]", "ا", s).replace("ى", "ي").replace("ة", "ه").replace("ؤ", "و").replace("ئ", "ي")
    return s


def stem(w):
    for p in PREFIXES:
        if w.startswith(p) and len(w) - len(p) >= (3 if len(p) == 1 else 2):
            return w[len(p):]
    return w


def tokens(text):
    return [stem(w) for w in NOT_ARABIC.split(norm(text)) if len(w) > 1]


def clean(line):
    s = re.sub(r"<[^>]+>|PageV\d+P\d+|\bms\d+\b|@[A-Z]{2,4}@|[#~|$%]", " ", line)
    return s


def passages(data):
    """Yields (start, end, vol, page, text) for the passages of a raw mARkdown file (bytes)."""
    head = data.find(b"#META#Header#End#")
    pos = 0 if head < 0 else data.index(b"\n", head) + 1
    vol = page = 0
    start, words, buf, pvol, ppage = None, 0, [], 0, 0
    for line in data[pos:].split(b"\n"):
        lstart, pos = pos, pos + len(line) + 1
        m = None
        for m in PAGE.finditer(line):
            pass
        is_new = line.startswith(b"# ") or line.startswith(b"### ") or line == b"#"
        if is_new and start is not None and words >= PASSAGE_WORDS:
            yield start, lstart, pvol, ppage, " ".join(buf)
            start, words, buf = None, 0, []
        if start is None:
            start, pvol, ppage = lstart, vol, page
            first = PAGE.search(line)
            if first and first.start() < 8:  # a page marker at the head of the line: the passage starts on that page
                pvol, ppage = int(first.group(1)), int(first.group(2))
        text = clean(line.decode("utf-8", "replace"))
        n = len(text.split())
        words += n
        buf.append(text)
        if m:
            vol, page = int(m.group(1)), int(m.group(2))
        # a passage never grows past twice the aim, even inside one long paragraph
        if words >= 2 * PASSAGE_WORDS:
            yield start, pos, pvol, ppage, " ".join(buf)
            start, words, buf = None, 0, []
    if start is not None and words:
        yield start, len(data), pvol, ppage, " ".join(buf)


def varint(n, out):
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return


def main():
    src = Path(sys.argv[1])
    meta = {t["uri"]: t for t in load_texts()}
    core = [l.split("\t")[0] for l in (ROOT / "tools/openiti/cekirdek.tsv").read_text(encoding="utf-8").splitlines()
            if l and not l.startswith("#")]
    books, table, postings = [], bytearray(), defaultdict(list)
    pid = 0
    for b, uri in enumerate(core):
        data = (src / uri).read_bytes()
        t = meta[uri]
        n0 = pid
        for start, end, vol, page, text in passages(data):
            ln = end - start
            while ln > 65535:  # longer than a range the table can hold: cut it
                table += b.to_bytes(2, "little") + vol.to_bytes(2, "little") + page.to_bytes(2, "little") + \
                    (65535).to_bytes(2, "little") + start.to_bytes(4, "little")
                start += 65535
                ln -= 65535
                pid += 1
            for term in set(tokens(text)):
                postings[term].append(pid)
            table += b.to_bytes(2, "little") + min(vol, 65535).to_bytes(2, "little") + min(page, 65535).to_bytes(2, "little") + \
                ln.to_bytes(2, "little") + start.to_bytes(4, "little")
            pid += 1
        books.append({"uri": uri, "title": t["title_ar"] or t["title_lat"], "author": t["author_ar"], "date": t["date"],
                      "words": t["words"], "raw": t["raw"], "size": len(data), "first": n0, "count": pid - n0})
        print(f"{uri}: {pid - n0} pasaj", file=sys.stderr)

    total = pid
    common = {w for w, ps in postings.items() if len(ps) > total / 2}
    shards = defaultdict(bytearray)
    counts = defaultdict(int)
    for term in sorted(postings):
        if term in common:
            continue
        ps = postings[term]
        key = term[:2]
        out = shards[key]
        enc = term.encode("utf-8")
        varint(len(enc), out)
        out += enc
        varint(len(ps), out)
        last = -1
        for p in ps:
            varint(p - last - 1, out)
            last = p
        counts[key] += 1

    if OUT.exists():
        for f in OUT.rglob("*"):
            if f.is_file():
                f.unlink()
    (OUT / "t").mkdir(parents=True, exist_ok=True)
    names = {}
    for i, (key, data) in enumerate(sorted(shards.items())):
        name = f"{i:04x}"
        names[key] = name
        (OUT / "t" / f"{name}.bin").write_bytes(bytes(data))
    (OUT / "passages.bin").write_bytes(bytes(table))
    (OUT / "books.json").write_text(json.dumps(books, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (OUT / "manifest.json").write_text(json.dumps({
        "source": "OpenITI (KITAB project), CC BY-NC-SA 4.0, https://doi.org/10.5281/zenodo.3082463",
        "passages": total, "books": len(books), "passageWords": PASSAGE_WORDS, "prefixes": PREFIXES,
        "stopwords": sorted(common), "shards": names}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    size = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file())
    print(f"{len(books)} kitap, {total} pasaj, {len(postings) - len(common)} terim, {len(shards)} dizin dosyası, "
          f"{size / 1e6:.1f} MB; dizine alınmayan sık kelimeler: {len(common)}")


if __name__ == "__main__":
    main()
