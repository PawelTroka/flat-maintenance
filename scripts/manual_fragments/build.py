"""Build task guides and unmodified visual crops from archived manufacturer PDFs.

Run from any directory. Requires pypdfium2 and Pillow. Never writes source PDFs.
Crop coordinates: one-based page, PDF points from the top-left of the page.
"""

import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

import pypdfium2 as pdfium

ROOT = Path(__file__).resolve().parents[2]
SPECS = Path(__file__).resolve().parent
MANUALS = ROOT / "docs/manuals"
OUT = ROOT / "docs/instrukcje"
DEVICES = {
    "sharp": ("sharp", "sharp"), "vestfrost": ("vestfrost", "vestfrost"),
    "waterpik": ("waterpik", "waterpik"), "roborock": ("roborock", "roborock"),
    "bps": ("suszarka", "candy"), "bp 49": ("pralka", "candy"),
    "bp49": ("pralka", "candy"), "withings": ("sprzet", "withings"),
    "siemens": ("pomieszczenia", None),
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def plain(text):
    return text.replace("**", "").strip()


def task_rows():
    rows = {}
    for line in (ROOT / "README.md").read_text(encoding="utf-8").splitlines():
        if re.match(r"^\| [a-z]+\d+[a-z]? \|", line):
            code, title, when, how = [s.strip() for s in line.strip("|").split("|")]
            rows[code] = {"title": plain(title), "when": plain(when), "how": how}
    return rows


def default_steps(how):
    # Source links are replaced by the task's own clipped illustrations below.
    text = re.sub(r"\[[^\]]+\]\[[^\]]+\]", "", how)
    text = re.sub(r"\[[^\]]+\]\([^)]*\)", "", text)
    text = re.sub(r"\s+", " ", text).strip(" ·")
    if not text or text == "—":
        raise ValueError("This task needs explicit steps in its JSON spec")
    return [text]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", nargs="+", help="Build only these task IDs during review")
    args = parser.parse_args()
    specs = []
    for path in sorted(SPECS.glob("*.json")):
        specs.extend(json.loads(path.read_text(encoding="utf-8-sig")))
    ids = [s["id"] for s in specs]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate guide IDs")
    for spec in specs:
        for field in ("steps", "safety", "notes"):
            value = spec.get(field, [])
            if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
                raise ValueError(f"{spec['id']}.{field} must be an array of strings")
    rows = task_rows()
    archive = json.loads((MANUALS / "manifest.json").read_text(encoding="utf-8"))
    titles = {Path(a["path"]).name: re.sub(r" — (?:pełna .+|full instruction manual)$", "", a["title"])
              .replace("diagrams accompanying the manual", "rysunki") for a in archive["artifacts"]}
    # Preserve checklist order in the index; helper pages follow the task list.
    order = {key: i for i, key in enumerate(rows)}
    specs.sort(key=lambda s: order.get(s["id"], len(order)))
    if args.only:
        unknown = set(args.only) - set(ids)
        if unknown:
            raise ValueError(f"Unknown IDs: {unknown}")
        specs = [s for s in specs if s["id"] in args.only]
    (OUT / "fragmenty").mkdir(parents=True, exist_ok=True)
    documents = {}
    hashes = {}
    images = {}
    records = []
    groups = defaultdict(list)
    try:
        for spec in specs:
            code = spec["id"]
            row = rows.get(code, {})
            title = spec.get("title") or row["title"]
            when = row.get("when") or spec.get("when", "W razie potrzeby")
            steps = spec.get("steps") or default_steps(row["how"])
            label = f"{code} — {title}" if code in rows else title
            lines = [f"# {label}", "", f"**{spec['device']} · {when}**", ""]
            section, photo = next((value for key, value in DEVICES.items() if key in spec["device"].lower()), (None, None))
            if photo:
                lines.extend([f"[Zdjęcie urządzenia](../zdjecia.md#{photo})", ""])
            for warning in spec.get("safety", []):
                lines.extend([f"> {warning}", ""])
            for number, step in enumerate(steps, 1):
                lines.append(f"{number}. {step}")
            lines.append("")
            if when.startswith(("Codziennie", "Po każdym")):
                lines.extend(["Wykonaj też przy każdej wizycie, minimum raz w tygodniu.", ""])
            for note in spec.get("notes", []):
                lines.extend([note, ""])
            sources = {}
            clips = []
            if spec.get("clips"):
                lines.extend(["## Fragment instrukcji producenta", "", "Dotknij rysunku, aby go powiększyć.", ""])
            for clip in spec.get("clips", []):
                filename = clip["source"]
                source = MANUALS / filename
                if source.parent != MANUALS or not source.is_file():
                    raise ValueError(f"Invalid source: {filename}")
                if filename not in documents:
                    documents[filename] = pdfium.PdfDocument(source)
                    hashes[filename] = digest(source)
                doc = documents[filename]
                page_no = clip["page"]
                if not 1 <= page_no <= len(doc):
                    raise ValueError(f"Page outside source: {clip}")
                x0, y0, x1, y1 = clip["box"]
                page = doc[page_no - 1]
                try:
                    width, height = page.get_size()
                    if not (0 <= x0 < x1 <= width + 0.1 and 0 <= y0 < y1 <= height + 0.1):
                        raise ValueError(f"Crop outside page {width}x{height}: {clip}")
                    key = (filename, page_no, tuple(clip["box"]))
                    if key not in images:
                        suffix = hashlib.sha256(json.dumps(key).encode()).hexdigest()[:10]
                        name = f"{source.stem}-p{page_no}-{suffix}.png"
                        # Render vector text at a useful resolution even for small panels.
                        scale = min(6, max(2, 1100 / (x1 - x0)))
                        bitmap = page.render(scale=scale, crop=(x0, height-y1, width-x1, y0))
                        try:
                            img = bitmap.to_pil()
                            img.save(OUT / "fragmenty" / name, optimize=True)
                            images[key] = {"image": f"fragmenty/{name}", "pixels": list(img.size)}
                        finally:
                            bitmap.close()
                finally:
                    page.close()
                image = images[key]
                caption = clip["caption"]
                lines.extend([f"**{caption}**", "", f"[![{caption}]({image['image']})]({image['image']})", ""])
                sources.setdefault(filename, []).append(page_no)
                clips.append({**clip, **image, "source_sha256": hashes[filename],
                              "image_sha256": digest(OUT / image["image"])})
            lines.extend(["## Źródło i pełna instrukcja", ""])
            for filename, pages in sources.items():
                page_list = ", ".join(map(str, sorted(set(pages))))
                page_label = "strona PDF" if len(set(pages)) == 1 else "strony PDF"
                lines.append(f"- [Pełna instrukcja — {titles.get(filename, spec['device'])}](../manuals/{filename}): {page_label} {page_list}.")
            for source in spec.get("sources", []):
                lines.append(f"- [{source['title']}](../manuals/{source['path']}).")
            if not sources and not spec.get("sources"):
                raise ValueError(f"No source for {code}")
            back = f"../../README.md#{section}" if section else "../../README.md"
            lines.extend(["", f"[Wróć do listy sprzątania]({back}) · [Wszystkie krótkie instrukcje](README.md)", ""])
            (OUT / f"{code}.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
            groups[spec["device"]].append((code, label))
            records.append({"id": code, "path": f"docs/instrukcje/{code}.md", "device": spec["device"],
                            "clips": clips, "sources": spec.get("sources", [])})
        if not args.only:
            index = ["# Krótkie instrukcje do zadań", "",
                     "**Kliknij „Instrukcja” przy zadaniu na liście sprzątania.** Otworzysz tylko potrzebne kroki i rysunki, bez szukania stron w PDF-ie.", "",
                     "Poniżej spis według urządzeń. Każda karta zawiera krótkie kroki po polsku oraz wycinki instrukcji producenta lub wskazany poradnik. Pełne pliki pozostają w [archiwum instrukcji](../manuals/README.md).", ""]
            for device, items in groups.items():
                index.extend([f"## {device}", ""])
                index.extend(f"- [{label}]({code}.md)" for code, label in items)
                index.append("")
            index.extend(["[Wróć do listy sprzątania](../../README.md)", ""])
            (OUT / "README.md").write_text("\n".join(index), encoding="utf-8", newline="\n")
            manifest = {"coordinate_system": "PDF points, top-left; pages one-based",
                        "source_archive": "docs/manuals/manifest.json", "guides": records}
            (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(f"Built {len(records)} guides with {len(images)} unique source crops.")
    finally:
        for document in documents.values():
            document.close()


if __name__ == "__main__":
    main()
