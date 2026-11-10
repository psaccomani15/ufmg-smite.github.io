#!/usr/bin/env python3
"""Convert bib/publications.bib into data/publications.json for the website.

Run it after editing bib/publications.bib (the deploy workflow also runs it before building):
  python3 scripts/bib2json.py

Each JSON entry holds what the publications shortcode displays (title, authors, venue, year,
links) plus the BibTeX of the entry without the website-only fields.
Only the Python standard library is needed.
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
BIB = ROOT / "bib" / "publications.bib"
OUT = ROOT / "data" / "publications.json"

SITE_FIELDS = ["venue", "pdf", "slides", "artifact", "preprint", "award"]  # not exported in the BibTeX
MONTHS = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
ACCENTS = {'"': "\u0308", "'": "\u0301", "`": "\u0300", "^": "\u0302", "~": "\u0303", "c": "\u0327"}


def parse(text):
    """Minimal BibTeX parser: @type{key, field = {..} | ".." | number, ...}. Text outside entries is ignored."""
    entries, i = [], 0
    while True:
        m = re.compile(r"@(\w+)\s*\{\s*([^,\s]+)\s*,").search(text, i)
        if not m:
            return entries
        kind, key, i = m.group(1).lower(), m.group(2), m.end()
        fields = {}
        while True:
            fm = re.compile(r"\s*(\w+)\s*=\s*").match(text, i)
            if not fm:
                end = re.compile(r"\s*,?\s*\}").match(text, i)
                if not end:
                    raise SystemExit(f"bib parse error in entry {key} near: {text[i:i + 60]!r}")
                i = end.end()
                break
            name, i = fm.group(1).lower(), fm.end()
            if text[i] == "{":
                depth, j = 0, i
                while True:
                    depth += {"{": 1, "}": -1}.get(text[j], 0)
                    j += 1
                    if depth == 0:
                        break
                value, i = text[i + 1:j - 1], j
            elif text[i] == '"':
                j = text.index('"', i + 1)
                value, i = text[i + 1:j], j + 1
            else:
                vm = re.compile(r"[^,}\s]+").match(text, i)
                value, i = vm.group(0), vm.end()
            fields[name] = value
            cm = re.compile(r"\s*,").match(text, i)
            if cm:
                i = cm.end()
        entries.append((kind, key, fields))


def plain(s):
    """BibTeX/LaTeX value -> display text."""
    s = re.sub(r"\\([\"'`^~c])\{?\s*(\w)\}?", lambda m: m.group(2) + ACCENTS[m.group(1)], s)
    s = s.replace("\\&", "&").replace("\\_", "_").replace("\\%", "%").replace("\\$", "$")
    s = s.replace("{", "").replace("}", "").replace("--", "–")
    return re.sub(r"\s+", " ", s).strip()


def bibtex(kind, key, fields):
    body = ",\n".join(f"  {k} = {{{v}}}" for k, v in fields.items() if k not in SITE_FIELDS)
    return f"@{kind}{{{key},\n{body}\n}}"


def main():
    entries = parse(BIB.read_text(encoding="utf-8"))
    out, seen = [], set()
    for kind, key, f in entries:
        if key in seen:
            sys.exit(f"duplicate BibTeX key: {key}")
        seen.add(key)
        people = "author" if "author" in f else "editor"  # proceedings list editors
        missing = [k for k in ("title", people, "year") if k not in f]
        if missing:
            sys.exit(f"entry {key} lacks {', '.join(missing)}")
        year = int(re.search(r"\d{4}", f["year"]).group(0))
        venue = f.get("venue") or f.get("booktitle") or f.get("journal") or f.get("howpublished", "")
        doi = f.get("doi", "")
        out.append({
            "key": key,
            "type": kind,
            "title": plain(f["title"]),
            "authors": [plain(a) for a in re.split(r"\s+and\s+", f[people].strip())],
            "editors": people == "editor",
            "venue": plain(venue),
            "year": year,
            "month": MONTHS.get(f.get("month", "").strip().lower()[:3], 0),
            "doi": doi,
            "url": f.get("url", ""),
            **{k: f[k].strip() for k in ("pdf", "slides", "artifact", "preprint") if f.get(k)},
            **({"award": plain(f["award"])} if f.get("award") else {}),
            "bibtex": bibtex(kind, key, f),
        })
    out.sort(key=lambda e: (-e["year"], -e["month"], e["title"].lower()))
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(out)} publications -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
