#!/usr/bin/env python3
"""
Simple heading/subheading detector for PDFs.

Heuristics:
- Uses pdfplumber to read words, their font sizes and positions.
- Finds the most common font size = "body" text.
- Any larger fonts that occur often enough are treated as heading sizes.
- Uses font size + simple regex patterns to distinguish:
    - Document titles (largest font, e.g. cover page)
    - Top-level sections: "1. INTRODUCTION"
    - Subsections:      "3.1 Paracetamol", etc.

You can later reuse the `extract_headings` / `build_tree` functions
inside your Teams app backend.
"""

import argparse
import json
import re
import statistics
from collections import Counter
from html import escape
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

import pdfplumber


def analyze_font_sizes(pdf_path, sample_pages=None):
    """
    Scan the PDF and infer:
    - body_size: most common font size
    - heading_sizes: list of font sizes significantly larger than body
    """
    size_counts = Counter()

    with pdfplumber.open(pdf_path) as pdf:
        n_pages = len(pdf.pages)
        if sample_pages is None:
            pages_range = range(n_pages)
        else:
            pages_range = range(min(sample_pages, n_pages))

        for i in pages_range:
            page = pdf.pages[i]
            words = page.extract_words(extra_attrs=["fontname", "size"])
            for w in words:
                try:
                    sz = float(w.get("size"))
                except (TypeError, ValueError):
                    continue
                size_counts[round(sz, 1)] += 1

    if not size_counts:
        raise RuntimeError("No font sizes found in the PDF.")

    # Most frequent font size = body text
    body_size, _ = max(size_counts.items(), key=lambda kv: kv[1])

    # Heading sizes: larger than body and used more than a few times
    heading_sizes = sorted(
        [
            size
            for size, count in size_counts.items()
            if size > body_size + 0.5 and count >= 3
        ],
        reverse=True,  # largest font first
    )

    return body_size, heading_sizes, size_counts


def classify_line_level(text,
                        median_size,
                        body_size,
                        heading_sizes,
                        size_tol=0.6):
    """
    Decide if a line is a heading and what level it should be.

    Returns:
        1, 2, 3, ... for heading levels
        None if this line is not a heading
    """
    # Map font size to "tier" (1 = largest heading size)
    tier = None
    for idx, h_size in enumerate(heading_sizes, start=1):
        if abs(median_size - h_size) <= size_tol:
            tier = idx
            break

    if tier is None:
        return None

    text_stripped = text.strip()

    # Regexes tuned for this style of manual:
    # e.g. "1. INTRODUCTION" (all caps after the number)
    upper_section = re.compile(r"^\d+\.\s+[A-Z0-9 ,()/\-]+$")
    # e.g. "3.1 Paracetamol"
    subsection = re.compile(r"^\d+\.\d+")

    if tier == 1:
        # Biggest font (e.g. title lines)
        return 1

    if upper_section.match(text_stripped):
        # "1. INTRODUCTION", "2. PRINCIPLES OF ..."
        return 2
    elif subsection.match(text_stripped):
        # "3.1 Paracetamol", "3.2 Diclofenac (Voltaren)", etc.
        return 3
    else:
        # Fallback: still treat as some kind of heading
        return 2 + (tier - 2)


def extract_headings(pdf_path,
                     size_tol=0.6,
                     max_pages=None):
    """
    Extract heading lines from the PDF.

    Returns:
        body_size, heading_sizes, headings_list, size_counts
    """
    body_size, heading_sizes, size_counts = analyze_font_sizes(
        pdf_path, sample_pages=max_pages
    )

    headings = []

    with pdfplumber.open(pdf_path) as pdf:
        n_pages = len(pdf.pages)
        if max_pages is None:
            page_range = range(n_pages)
        else:
            page_range = range(min(max_pages, n_pages))

        for p_idx in page_range:
            page = pdf.pages[p_idx]
            words = page.extract_words(extra_attrs=["fontname", "size"])

            # Group words into lines by vertical position ('top')
            lines = {}
            for w in words:
                top = float(w["top"])
                key = round(top, 1)
                lines.setdefault(key, []).append(w)

            # Iterate lines from top to bottom
            for top, line_words in sorted(lines.items(), key=lambda kv: kv[0]):
                # Sort words left to right
                line_words_sorted = sorted(line_words, key=lambda w: w["x0"])
                text = " ".join(w["text"] for w in line_words_sorted).strip()
                if not text:
                    continue

                sizes = [float(w["size"]) for w in line_words_sorted]
                median_size = statistics.median(sizes)

                level = classify_line_level(
                    text, median_size, body_size, heading_sizes, size_tol=size_tol
                )
                if level is None:
                    continue

                # Heuristic: skip extremely long lines (probably body)
                if len(text) > 160:
                    continue

                heading_id = len(headings)
                headings.append(
                    {
                        "id": heading_id,
                        "page": p_idx + 1,  # human-friendly page number
                        "top": top,
                        "level": level,
                        "font_size": median_size,
                        "text": text,
                    }
                )

    # Ensure reading order: by page, then vertical position
    headings.sort(key=lambda h: (h["page"], h["top"]))
    return body_size, heading_sizes, headings, size_counts


BULLET_CHARS = ("•", "-", "–", "—", "▪", "‣", "·")
GAP_THRESHOLD = 14  # pdf coordinate units (~points)


def assemble_line(words):
    """Build a text string for a line + classify its type."""
    if not words:
        return "", "blank"

    segments = [words[0]["text"]]
    large_gaps = 0

    for prev, curr in zip(words, words[1:]):
        gap = float(curr["x0"]) - float(prev["x1"])
        if gap > GAP_THRESHOLD:
            segments.append("    ")  # emulate column spacing
            large_gaps += 1
        else:
            segments.append(" ")
        segments.append(curr["text"])

    raw = "".join(segments)
    stripped = raw.strip()
    if not stripped:
        return "", "blank"

    if stripped[:1] in BULLET_CHARS:
        return stripped, "bullet"

    if large_gaps >= 2:
        return raw, "table"

    return stripped, "paragraph"


def extract_lines_from_page(page, min_top=None, max_top=None):
    """Return ordered line dicts (text + type) within optional bounds."""
    words = page.extract_words(extra_attrs=["fontname", "size"])
    if not words:
        return []

    grouped = {}
    for w in words:
        top = float(w["top"])
        if min_top is not None and top < min_top - 0.2:
            continue
        if max_top is not None and top >= max_top - 0.2:
            continue
        key = round(top, 1)
        grouped.setdefault(key, []).append(w)

    lines = []
    for key in sorted(grouped.keys()):
        line_words = sorted(grouped[key], key=lambda item: item["x0"])
        text, line_type = assemble_line(line_words)
        if text:
            lines.append({"text": text, "type": line_type})
    return lines


def format_lines_as_html(lines):
    """Convert classified lines into lightweight semantic HTML."""
    html_parts = []
    list_buffer: List[str] = []
    table_buffer: List[str] = []

    bullet_strip_chars = "".join(BULLET_CHARS + (" ",))

    def flush_list():
        if list_buffer:
            items = "".join(f"<li>{escape(item)}</li>" for item in list_buffer)
            html_parts.append(f"<ul>{items}</ul>")
            list_buffer.clear()

    def flush_table():
        if table_buffer:
            rows = []
            for row in table_buffer:
                cells = [
                    escape(cell.strip())
                    for cell in re.split(r"\s{2,}", row.strip())
                    if cell.strip()
                ]
                if cells:
                    rows.append("<tr>" + "".join(f"<td>{cell}</td>" for cell in cells) + "</tr>")
            if rows:
                html_parts.append(f"<table>{''.join(rows)}</table>")
            table_buffer.clear()

    for line in lines:
        text = line["text"]
        line_type = line["type"]

        if line_type == "bullet":
            flush_table()
            stripped = text.lstrip(bullet_strip_chars).strip()
            list_buffer.append(stripped or text.strip())
            continue

        if line_type == "table":
            flush_list()
            table_buffer.append(text)
            continue

        if not text.strip():
            flush_list()
            flush_table()
            continue

        flush_list()
        flush_table()
        html_parts.append(f"<p>{escape(text.strip())}</p>")

    flush_list()
    flush_table()

    if not html_parts:
        return '<p class="text-muted">No text detected for this section.</p>'

    return "".join(html_parts)


def attach_section_html(pdf_path, headings):
    """Populate each heading with an HTML snippet for its body."""
    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)

        for idx, heading in enumerate(headings):
            start_page = heading["page"]
            start_top = heading["top"]

            end_page = total_pages
            end_top: Optional[float] = None
            heading_level = heading.get("level")

            for next_heading in headings[idx + 1 :]:
                next_level = next_heading.get("level")
                if heading_level is None or next_level is None:
                    continue
                if next_level <= heading_level:
                    end_page = next_heading["page"]
                    end_top = next_heading["top"]
                    break

            section_lines = []
            for page_num in range(start_page, end_page + 1):
                page = pdf.pages[page_num - 1]
                min_top = None
                max_top = None
                if page_num == start_page:
                    min_top = start_top + 0.5  # skip the heading line itself
                if end_top is not None and page_num == end_page:
                    max_top = end_top
                page_lines = extract_lines_from_page(page, min_top=min_top, max_top=max_top)
                section_lines.extend(page_lines)

            heading["content_html"] = format_lines_as_html(section_lines)


def build_tree(headings):
    """
    Build a simple parent/children tree from a flat list of headings.

    Rule:
    - A heading is a child of the previous heading with a lower level.
    """
    tree = []
    stack = []

    def level_value(item):
        level = item.get("level")
        if isinstance(level, (int, float)):
            return level
        return float("inf")

    for h in headings:
        node = dict(h)
        node["children"] = []

        current_level = level_value(node)

        # Pop until we find a parent with a lower level
        while stack and level_value(stack[-1]) >= current_level:
            stack.pop()

        if stack:
            stack[-1]["children"].append(node)
        else:
            tree.append(node)

        stack.append(node)

    return tree


def print_tree(nodes, indent=0):
    """Pretty-print the heading tree to stdout."""
    for n in nodes:
        prefix = "  " * indent
        print("- (L%d, p%d) %s" % (n["level"], n["page"], n["text"]))
        if n.get("children"):
            print_tree(n["children"], indent + 1)


def main():
    parser = argparse.ArgumentParser(
        description="Detect headings/subheadings in a PDF by font-size heuristics."
    )
    parser.add_argument("pdf", help="Path to the input PDF file")
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Only scan the first N pages (useful for testing)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output the heading tree as JSON instead of pretty text",
    )

    args = parser.parse_args()

    body_size, heading_sizes, headings, size_counts = extract_headings(
        args.pdf, max_pages=args.max_pages
    )

    attach_section_html(args.pdf, headings)

    tree = build_tree(headings)

    if args.json:
        payload = {
            "pdf": Path(args.pdf).name,
            "pdf_path": args.pdf,
            "headings": tree,
        }
        print(json.dumps(payload, indent=2))
    else:
        print("Body font size (most common):", body_size)
        print("Detected heading font sizes (largest first):", heading_sizes)
        print()
        print_tree(tree)


if __name__ == "__main__":
    main()
