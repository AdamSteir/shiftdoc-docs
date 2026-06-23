#!/usr/bin/env python3
"""
build.py — reads _cache/, renders Jinja2 templates, writes site/.

Usage:
    python build.py
"""

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

CACHE_DIR = Path(__file__).parent / "_cache"
SITE_DIR = Path(__file__).parent / "site"
TEMPLATES_DIR = Path(__file__).parent / "templates"

SECTION_LABELS = {
    "account_settings": "Account Settings",
    "analyze": "Analyze",
    "claude_workflows": "Frameworks & Add-ons",
    "": "General",
}


def load_cache():
    pages = {}
    for po_file in sorted(CACHE_DIR.rglob("shiftdoc-po-*.json")):
        stem = po_file.stem.replace("shiftdoc-po-", "")
        qam_file = po_file.parent / f"shiftdoc-qam-{stem}.json"
        rel_dir = po_file.parent.relative_to(CACHE_DIR)
        section = str(rel_dir) if str(rel_dir) != "." else ""
        key = f"{section}/{stem}" if section else stem
        pages[key] = {
            "stem": stem,
            "section": section,
            "section_label": SECTION_LABELS.get(section, section.replace("_", " ").title()),
            "po": json.loads(po_file.read_text(encoding="utf-8")),
            "qam": json.loads(qam_file.read_text(encoding="utf-8")) if qam_file.exists() else None,
        }
    return pages


def build():
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True)
    SITE_DIR.mkdir(exist_ok=True)

    pages = load_cache()

    # Render individual feature pages
    feature_tmpl = env.get_template("feature.html.j2")
    for key, data in pages.items():
        out_dir = SITE_DIR / key
        out_dir.mkdir(parents=True, exist_ok=True)
        html = feature_tmpl.render(**data)
        (out_dir / "index.html").write_text(html, encoding="utf-8")
        print(f"  built site/{key}/index.html")

    # Group pages by section for section index pages
    sections = {}
    for key, data in pages.items():
        section = data["section"]
        sections.setdefault(section, []).append({**data, "key": key})

    section_tmpl = env.get_template("section.html.j2")
    for section, section_pages in sections.items():
        label = SECTION_LABELS.get(section, section.replace("_", " ").title())
        out_dir = SITE_DIR / section if section else SITE_DIR
        out_dir.mkdir(parents=True, exist_ok=True)
        html = section_tmpl.render(section=section, section_label=label, pages=section_pages)
        (out_dir / "index.html").write_text(html, encoding="utf-8")
        print(f"  built site/{section}/index.html" if section else "  built site/index.html (general)")

    # Render main index
    index_tmpl = env.get_template("index.html.j2")
    ordered_sections = {k: sections[k] for k in ["claude_workflows", "analyze", "account_settings", ""] if k in sections}
    html = index_tmpl.render(sections=ordered_sections, section_labels=SECTION_LABELS)
    (SITE_DIR / "index.html").write_text(html, encoding="utf-8")
    print("  built site/index.html")

    print(f"\nDone. {len(pages)} pages built.")


if __name__ == "__main__":
    build()
