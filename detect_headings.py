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

                headings.append(
                    {
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


def build_tree(headings):
    """
    Build a simple parent/children tree from a flat list of headings.

    Rule:
    - A heading is a child of the previous heading with a lower level.
    """
    tree = []
    stack = []

    for h in headings:
        node = dict(h)
        node["children"] = []

        # Pop until we find a parent with a lower level
        while stack and stack[-1]["level"] >= node["level"]:
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
