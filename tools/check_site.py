#!/usr/bin/env python3
"""Static sanity checks for the LeafBlitz single-page site.

Runs without a browser: it parses the HTML, cross-references the inline
JavaScript against the DOM ids it touches, and fails on the regressions that
are easy to introduce by hand (placeholder phone numbers, dead links, missing
local assets, unbalanced tags, unparseable JSON-LD).

Usage:
    python3 tools/check_site.py [path/to/index.html]

Exit code 0 = clean, 1 = problems found (prints one line per problem).
"""

from __future__ import annotations

import json
import os
import re
import sys
from html.parser import HTMLParser

# Void elements never have a closing tag.
VOID = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
}

# Placeholder contact details that must never reach production.
BAD_CONTACT_PATTERNS = [
    r"\(555\)\s*546",           # original template phone
    r"555-01\d\d",               # fictional reserved range
    r"tel:5555465323",
    r"example\.com",
    r"lorem ipsum",
    r"\bTODO\b",
    r"\bFIXME\b",
    r"\bXXX\b",
]

REQUIRED_CONTACTS = [
    "334-777-3031",
    "334-578-2252",
    "Corinthianbrown@checkchasinempire.onmicrosoft.com",
]


class StructureParser(HTMLParser):
    """Collects ids, anchors, local assets and reports unbalanced tags."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: list[str] = []
        self.anchors: list[str] = []
        self.local_assets: list[str] = []
        self.stack: list[tuple[str, int]] = []
        self.errors: list[str] = []
        self.jsonld: list[str] = []
        self._in_jsonld = False
        self.title_count = 0
        self.meta_description = 0
        self.viewport = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in VOID:
            pass
        else:
            self.stack.append((tag, self.getpos()[0]))
        if "id" in a:
            self.ids.append(a["id"])
        href = a.get("href", "")
        if href.startswith("#"):
            self.anchors.append(href[1:])
        if tag == "link":
            if a.get("rel") == "canonical":
                pass
            if href and not href.startswith(("http", "data:", "#", "mailto:", "tel:", "sms:")):
                self.local_assets.append(href)
            if a.get("rel") == "icon" or a.get("rel") == "apple-touch-icon":
                pass
        if tag == "script":
            src = a.get("src", "")
            if src and not src.startswith(("http", "data:")):
                self.local_assets.append(src)
            if a.get("type") == "application/ld+json":
                self._in_jsonld = True
        if tag == "img":
            src = a.get("src", "")
            if src and not src.startswith(("http", "data:", "${")):
                self.local_assets.append(src)
        if tag == "title":
            self.title_count += 1
        if tag == "meta":
            if a.get("name") == "description":
                self.meta_description += 1
            if a.get("name") == "viewport":
                self.viewport += 1

    def handle_endtag(self, tag):
        if tag == "script":
            self._in_jsonld = False
        if tag in VOID:
            return
        if not self.stack:
            self.errors.append(f"line {self.getpos()[0]}: closing </{tag}> with no open tag")
            return
        open_tag, line = self.stack.pop()
        if open_tag != tag:
            self.errors.append(
                f"line {self.getpos()[0]}: </{tag}> closes <{open_tag}> opened on line {line}"
            )
            # Push back so the rest of the document still lines up.
            self.stack.append((open_tag, line))

    def handle_data(self, data):
        if self._in_jsonld:
            self.jsonld.append(data)

    def handle_startendtag(self, tag, attrs):
        # Self-closing form, e.g. <meta ... /> -- handled like a start tag.
        self.handle_starttag(tag, attrs)
        if tag not in VOID and self.stack and self.stack[-1][0] == tag:
            self.stack.pop()


def check(path: str) -> list[str]:
    problems: list[str] = []
    with open(path, encoding="utf-8") as fh:
        html = fh.read()

    parser = StructureParser()
    parser.feed(html)
    parser.close()

    # 1. Structure -----------------------------------------------------------
    problems += parser.errors
    for tag, line in parser.stack:
        problems.append(f"line {line}: <{tag}> never closed")

    if parser.title_count != 1:
        problems.append(f"expected exactly 1 <title>, found {parser.title_count}")
    if parser.meta_description != 1:
        problems.append(f"expected 1 meta description, found {parser.meta_description}")
    if parser.viewport != 1:
        problems.append(f"expected 1 viewport meta, found {parser.viewport}")

    dupes = {i for i in parser.ids if parser.ids.count(i) > 1}
    if dupes:
        problems.append(f"duplicate id attributes: {sorted(dupes)}")

    # 2. Anchors -------------------------------------------------------------
    for anchor in parser.anchors:
        if anchor == "":
            problems.append('dead link: bare href="#"')
        elif anchor not in parser.ids:
            problems.append(f"anchor #{anchor} has no matching id")

    # 3. Local assets exist --------------------------------------------------
    root = os.path.dirname(os.path.abspath(path))
    for asset in parser.local_assets:
        if not os.path.exists(os.path.join(root, asset.split("?")[0])):
            problems.append(f"missing local asset: {asset}")

    # 4. JSON-LD parses ------------------------------------------------------
    for blob in parser.jsonld:
        try:
            json.loads(blob)
        except json.JSONDecodeError as exc:
            problems.append(f"invalid JSON-LD: {exc}")

    # 5. Placeholder / template leftovers ------------------------------------
    for pattern in BAD_CONTACT_PATTERNS:
        for m in re.finditer(pattern, html, re.IGNORECASE):
            line = html.count("\n", 0, m.start()) + 1
            problems.append(f"line {line}: placeholder text still present: {m.group(0)!r}")

    # 6. Required real contact details (main page only) -----------------------
    if os.path.basename(path) == "index.html":
        for contact in REQUIRED_CONTACTS:
            if contact not in html:
                problems.append(f"missing required contact detail: {contact}")

    # 7. tel:/mailto: links agree with the real numbers ----------------------
    for m in re.finditer(r'href="tel:([^"]+)"', html):
        if "${" in m.group(1):        # JS template literal, resolved at runtime
            continue
        digits = re.sub(r"\D", "", m.group(1))
        if len(digits) != 11 or not digits.startswith("1") or not digits[1:].startswith("334"):
            line = html.count("\n", 0, m.start()) + 1
            problems.append(f"line {line}: suspicious tel: link {m.group(1)!r}")

    # 8. JS <-> DOM cross reference ------------------------------------------
    ids = set(parser.ids)
    for m in re.finditer(r"getElementById\(\s*'([^']+)'\s*\)", html):
        if m.group(1) not in ids:
            line = html.count("\n", 0, m.start()) + 1
            problems.append(f"line {line}: JS references unknown id #{m.group(1)}")
    for m in re.finditer(r"querySelector\(\s*'#([A-Za-z0-9_-]+)'\s*\)", html):
        if m.group(1) not in ids:
            problems.append(f"JS querySelector references unknown id #{m.group(1)}")

    defined = set(re.findall(r"function\s+([A-Za-z0-9_$]+)\s*\(", html))
    defined |= set(re.findall(r"(?:const|let|var)\s+([A-Za-z0-9_$]+)\s*=\s*(?:function|\()", html))
    for m in re.finditer(r'on(?:click|change|input|submit|keydown|keyup)="([A-Za-z0-9_$]+)\s*\(', html):
        if m.group(1) not in defined and m.group(1) not in {"document", "window"}:
            line = html.count("\n", 0, m.start()) + 1
            problems.append(f"line {line}: inline handler calls undefined function {m.group(1)}()")

    # 9. Accessibility basics -------------------------------------------------
    for m in re.finditer(r"<img\b[^>]*>", html):
        tag = m.group(0)
        if "alt=" not in tag:
            line = html.count("\n", 0, m.start()) + 1
            problems.append(f"line {line}: <img> without alt text")

    return problems


def extract_scripts(path: str) -> list[str]:
    """Return the inline <script> bodies so they can be syntax-checked by node."""
    with open(path, encoding="utf-8") as fh:
        html = fh.read()
    out = []
    for m in re.finditer(r"<script(?![^>]*\bsrc=)(?![^>]*ld\+json)[^>]*>(.*?)</script>", html, re.S):
        body = m.group(1).strip()
        if body:
            out.append(body)
    return out


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else "index.html"
    if not os.path.exists(path):
        print(f"check_site: {path} not found")
        return 1
    problems = check(path)
    # Keep the output readable: one line per distinct problem.
    seen: dict[str, int] = {}
    for p in problems:
        seen[p] = seen.get(p, 0) + 1
    if seen:
        print(f"FAIL {path}: {len(problems)} problem(s), {len(seen)} distinct")
        for p, n in list(seen.items())[:60]:
            print(f"  - {p}" + (f"  (x{n})" if n > 1 else ""))
        if len(seen) > 60:
            print(f"  ... and {len(seen) - 60} more distinct problems")
        return 1
    print(f"OK {path}: structure, links, assets, contacts, a11y and JS references are clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
