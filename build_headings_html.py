#!/usr/bin/env python3
"""
Read headings.json (output from detect_headings.py --json)
and generate a simple 'Teams-like' HTML page:

- Left sidebar: chapters + subheading buttons
- Right pane: shows details for the selected item
"""

import json
import sys
from pathlib import Path

HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Paediatric Pain Manual – Nav Preview</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      display: flex;
      height: 100vh;
      color: #111827;
    }

    .sidebar {
      width: 320px;
      background: #f3f4f6;
      border-right: 1px solid #e5e7eb;
      padding: 12px;
      overflow-y: auto;
    }

    .sidebar-header {
      font-weight: 600;
      margin-bottom: 8px;
      font-size: 14px;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      color: #6b7280;
    }

    .chapter {
      margin-bottom: 8px;
      border-radius: 8px;
      padding: 6px 8px;
    }

    .chapter-title {
      font-size: 14px;
      font-weight: 600;
      margin-bottom: 4px;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }

    .chapter-title:hover {
      color: #1d4ed8;
    }

    .chapter-title span.chevron {
      font-size: 11px;
      color: #9ca3af;
      margin-left: 6px;
    }

    .subheading-list {
      margin-top: 4px;
      padding-left: 4px;
      border-left: 2px solid #e5e7eb;
    }

    /* Collapsed chapters hide their subheading list */
    .chapter.collapsed .subheading-list {
      display: none;
    }

    .subheading-btn {
      display: block;
      width: 100%;
      text-align: left;
      padding: 4px 6px;
      margin: 2px 0;
      border: none;
      border-radius: 6px;
      background: transparent;
      font-size: 13px;
      cursor: pointer;
      color: #374151;
    }

    .subheading-btn:hover {
      background: #e5e7eb;
    }

    .subheading-btn.selected {
      background: #dbeafe;
      color: #1d4ed8;
      font-weight: 500;
    }

    .content {
      flex: 1;
      padding: 16px 20px;
      overflow-y: auto;
      background: #ffffff;
    }

    .content h1 {
      margin-top: 0;
      font-size: 22px;
    }

    .content .meta {
      font-size: 13px;
      color: #6b7280;
      margin-bottom: 12px;
    }

    .pill {
      display: inline-flex;
      align-items: center;
      padding: 2px 8px;
      border-radius: 999px;
      background: #eff6ff;
      color: #1d4ed8;
      font-size: 12px;
      margin-right: 6px;
    }

    .placeholder-box {
      margin-top: 16px;
      padding: 16px;
      border-radius: 12px;
      border: 1px dashed #d1d5db;
      background: #f9fafb;
      font-size: 13px;
      color: #4b5563;
    }

    .search-box {
      margin-bottom: 8px;
    }

    .search-input {
      width: 100%;
      padding: 6px 8px;
      border-radius: 6px;
      border: 1px solid #d1d5db;
      font-size: 13px;
    }

    .search-input:focus {
      outline: none;
      border-color: #2563eb;
      box-shadow: 0 0 0 1px #2563eb33;
    }

    .pdf-container {
      margin-top: 16px;
      border: 1px solid #e5e7eb;
      border-radius: 12px;
      background: #0f172a;
      min-height: 420px;
      display: flex;
      align-items: center;
      justify-content: center;
      position: relative;
      overflow: hidden;
    }

    .pdf-container canvas {
      width: 100%;
      height: auto;
      display: block;
      background: #1f2937;
    }

    .pdf-status {
      position: absolute;
      top: 12px;
      left: 12px;
      padding: 4px 10px;
      border-radius: 999px;
      background: rgba(15, 23, 42, 0.8);
      color: #f8fafc;
      font-size: 12px;
    }

    .pdf-container.error {
      background: #fff;
      color: #b91c1c;
      border-color: #fecaca;
      min-height: auto;
      padding: 16px;
      display: block;
    }

    .page-controls {
      display: flex;
      align-items: center;
      justify-content: flex-end;
      gap: 8px;
      margin-top: 8px;
    }

    .page-btn {
      border: 1px solid #d1d5db;
      background: #fff;
      border-radius: 6px;
      padding: 4px 10px;
      font-size: 13px;
      cursor: pointer;
      color: #1f2937;
    }

    .page-btn:hover:not(:disabled) {
      border-color: #2563eb;
      color: #1d4ed8;
    }

    .page-btn:disabled {
      opacity: 0.4;
      cursor: not-allowed;
    }

    .page-indicator {
      font-size: 12px;
      color: #6b7280;
      font-weight: 500;
    }

    .section-text {
      margin-top: 16px;
      padding: 16px;
      border: 1px solid #e5e7eb;
      border-radius: 12px;
      background: #fefefe;
      font-size: 14px;
      line-height: 1.6;
    }

    .section-text p {
      margin: 8px 0;
    }

    .section-text ul {
      margin: 12px 0;
      padding-left: 20px;
    }

    .section-text table {
      width: 100%;
      border-collapse: collapse;
      margin: 12px 0;
      font-size: 13px;
    }

    .section-text td {
      border: 1px solid #e5e7eb;
      padding: 4px 6px;
      vertical-align: top;
    }

    .section-text .text-muted {
      color: #6b7280;
      font-style: italic;
    }
  </style>
</head>
<body>
  <div class="sidebar">
    <div class="sidebar-header">Chapters & Sections</div>
    <div class="search-box">
      <input id="searchInput" class="search-input" placeholder="Search headings..." />
    </div>
    <div id="sidebarContent"></div>
  </div>
  <div class="content">
    <h1>Paediatric Pain Manual – Navigation Preview</h1>
    <p class="meta">
      Click a subheading on the left to see details. In Teams, this is where you'd:
      <span class="pill">Scroll PDF to page X</span>
      <span class="pill">Highlight section</span>
    </p>
    <div class="placeholder-box">
      <strong>No section selected yet.</strong><br/>
      This pane is acting like your future Teams tab content area.<br/>
      When you click a heading on the left, you'll see:
      <ul>
        <li>Heading text + parent chapter</li>
        <li>The PDF page rendered via pdf.js</li>
        <li>Quick metadata chips you can reuse in Teams</li>
        <li>A short description of what the Teams app would do</li>
      </ul>
    </div>
  </div>

  <script src="vendor/pdfjs/pdf.min.js"></script>
  <script>
    const pdfjsBuild = window['pdfjs-dist/build/pdf'];
    if (pdfjsBuild && pdfjsBuild.GlobalWorkerOptions) {
      pdfjsBuild.GlobalWorkerOptions.workerSrc = 'vendor/pdfjs/pdf.worker.min.js';
      window.pdfjsLib = pdfjsBuild;
    } else {
      console.error('pdf.js failed to initialize');
    }
  </script>
  <script>
    // The tree + metadata from detect_headings.py --json
    const headingData = __JSON_DATA__;
    const headingsTree = Array.isArray(headingData) ? headingData : (headingData.headings || []);
    const pdfSource = Array.isArray(headingData)
      ? ''
      : (
          headingData.pdf_path ||
          headingData.pdf ||
          headingData.pdf_filename ||
          headingData.pdfPath ||
          ''
        );

    const sidebarContent = document.getElementById('sidebarContent');
    const content = document.querySelector('.content');
    const searchInput = document.getElementById('searchInput');
    let currentSelectedButton = null;
    let pdfDocPromise = null;

    function collectChapters(tree) {
      const chapters = [];
      function walk(nodes) {
        nodes.forEach(node => {
          if (node.level === 2) {
            chapters.push(node);
          }
          if (node.children && node.children.length) {
            walk(node.children);
          }
        });
      }
      walk(tree);
      return chapters;
    }

    function filterNodesBySearch(term, chapters) {
      if (!term) return chapters;
      term = term.toLowerCase();
      return chapters.map(ch => {
        const matchChapter = ch.text.toLowerCase().includes(term);
        const filteredChildren = (ch.children || []).filter(child =>
          child.text.toLowerCase().includes(term)
        );
        if (matchChapter || filteredChildren.length) {
          return Object.assign({}, ch, { children: filteredChildren.length ? filteredChildren : ch.children });
        }
        return null;
      }).filter(Boolean);
    }

    function renderSidebar(chapters) {
      sidebarContent.innerHTML = "";
      chapters.forEach(chapter => {
        const chapterEl = document.createElement('div');
        chapterEl.classList.add('chapter');   // base class first

        const hasChildren = chapter.children && chapter.children.length > 0;

        // Default state:
        // - With children -> collapsed (hidden, ▸)
        // - Without children -> expanded, no chevron
        if (hasChildren) {
          chapterEl.dataset.expanded = 'false';
          chapterEl.classList.add('collapsed');   // ensure hidden on first render
        } else {
          chapterEl.dataset.expanded = 'true';
        }

        const titleEl = document.createElement('div');
        titleEl.className = 'chapter-title';

        const titleText = document.createElement('span');
        titleText.textContent = chapter.text;
        titleEl.appendChild(titleText);

        let chevron = null;
        if (hasChildren) {
          chevron = document.createElement('span');
          chevron.className = 'chevron';
          chevron.textContent = '▸'; // collapsed by default
          titleEl.appendChild(chevron);
        }

        titleEl.addEventListener('click', () => {
          if (hasChildren) {
            const expanded = chapterEl.dataset.expanded === 'true';
            if (expanded) {
              chapterEl.dataset.expanded = 'false';
              chapterEl.classList.add('collapsed');
              if (chevron) chevron.textContent = '▸';
            } else {
              chapterEl.dataset.expanded = 'true';
              chapterEl.classList.remove('collapsed');
              if (chevron) chevron.textContent = '▾';
            }
          }
          // Show this chapter in the main pane
          showHeading(chapter, chapter);
        });

        chapterEl.appendChild(titleEl);

        if (hasChildren) {
          const listEl = document.createElement('div');
          listEl.className = 'subheading-list';

          chapter.children.forEach(child => {
            const btn = document.createElement('button');
            btn.className = 'subheading-btn';
            btn.textContent = child.text;
            btn.addEventListener('click', (e) => {
              e.stopPropagation();
              selectButton(btn);
              showHeading(child, chapter);
            });
            listEl.appendChild(btn);
          });

          chapterEl.appendChild(listEl);
        }

        sidebarContent.appendChild(chapterEl);
      });
    }

    function selectButton(btn) {
      if (currentSelectedButton) {
        currentSelectedButton.classList.remove('selected');
      }
      currentSelectedButton = btn;
      if (currentSelectedButton) {
        currentSelectedButton.classList.add('selected');
      }
    }

    async function ensurePdfLoaded() {
      if (!pdfSource) {
        throw new Error("No PDF path defined in headings.json");
      }
      if (!window.pdfjsLib) {
        throw new Error("pdf.js failed to load");
      }
      if (!pdfDocPromise) {
        pdfDocPromise = window.pdfjsLib.getDocument(pdfSource).promise;
      }
      return pdfDocPromise;
    }

    async function renderPdfPage(pageNumber, canvas) {
      const pdf = await ensurePdfLoaded();
      const page = await pdf.getPage(pageNumber);
      const viewport = page.getViewport({ scale: 1.2 });
      const ctx = canvas.getContext('2d');
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      await page.render({ canvasContext: ctx, viewport }).promise;
    }

    async function showHeading(node, chapter) {
      content.innerHTML = "";

      const h1 = document.createElement('h1');
      h1.textContent = node.text;

      const meta = document.createElement('p');
      meta.className = 'meta';
      meta.textContent = `Part of "${chapter.text}" • Page ${node.page} • Level L${node.level}`;

      const pills = document.createElement('div');
      const pillChapter = document.createElement('span');
      pillChapter.className = 'pill';
      pillChapter.textContent = 'Chapter: ' + chapter.text;

      const pillPage = document.createElement('span');
      pillPage.className = 'pill';
      pillPage.textContent = 'Page: ' + node.page;

      const pillLevel = document.createElement('span');
      pillLevel.className = 'pill';
      pillLevel.textContent = 'Level: L' + node.level;

      pills.appendChild(pillChapter);
      pills.appendChild(pillPage);
      pills.appendChild(pillLevel);

      content.appendChild(h1);
      content.appendChild(meta);
      content.appendChild(pills);

      const pdfWrapper = document.createElement('div');
      pdfWrapper.className = 'pdf-container';

      const pdfStatus = document.createElement('div');
      pdfStatus.className = 'pdf-status';
      pdfWrapper.appendChild(pdfStatus);

      content.appendChild(pdfWrapper);

      if (!pdfSource) {
        pdfStatus.textContent = 'Add "pdf" to headings.json to preview the file here.';
        pdfWrapper.classList.add('error');
        const textDumpFallback = document.createElement('div');
        textDumpFallback.className = 'section-text';
        textDumpFallback.innerHTML = node.content_html || '<p class="text-muted">No extracted text for this section yet.</p>';
        content.appendChild(textDumpFallback);
        return;
      }

      pdfStatus.textContent = `Loading page ${node.page}…`;

      const canvas = document.createElement('canvas');
      canvas.className = 'pdf-canvas';
      pdfWrapper.appendChild(canvas);

      const controls = document.createElement('div');
      controls.className = 'page-controls';
      const prevBtn = document.createElement('button');
      prevBtn.className = 'page-btn';
      prevBtn.textContent = '← Prev page';
      const pageIndicator = document.createElement('span');
      pageIndicator.className = 'page-indicator';
      const nextBtn = document.createElement('button');
      nextBtn.className = 'page-btn';
      nextBtn.textContent = 'Next page →';
      controls.appendChild(prevBtn);
      controls.appendChild(pageIndicator);
      controls.appendChild(nextBtn);
      content.appendChild(controls);

      const pdfDoc = await ensurePdfLoaded();
      const totalPages = pdfDoc.numPages;
      let activePage = node.page;
      let isRendering = false;

      function updateControls() {
        prevBtn.disabled = activePage <= 1;
        nextBtn.disabled = activePage >= totalPages;
        pageIndicator.textContent = `Page ${activePage} / ${totalPages}`;
      }

      async function goToPage(targetPage) {
        if (targetPage < 1 || targetPage > totalPages || isRendering) {
          return;
        }
        isRendering = true;
        pdfStatus.textContent = `Loading page ${targetPage}…`;
        try {
          await renderPdfPage(targetPage, canvas);
          activePage = targetPage;
          pdfStatus.textContent = `Showing page ${targetPage}`;
        } catch (err) {
          console.error(err);
          pdfWrapper.classList.add('error');
          pdfStatus.textContent = 'Unable to load PDF page. Check console for details.';
        } finally {
          isRendering = false;
          updateControls();
        }
      }

      prevBtn.addEventListener('click', () => goToPage(activePage - 1));
      nextBtn.addEventListener('click', () => goToPage(activePage + 1));

      await goToPage(node.page);

      const textDump = document.createElement('div');
      textDump.className = 'section-text';
      textDump.innerHTML = node.content_html || '<p class="text-muted">No extracted text for this section yet.</p>';
      content.appendChild(textDump);
    }

    const allChapters = collectChapters(headingsTree);

    // Initial render
    renderSidebar(allChapters);

    // Search filter
    searchInput.addEventListener('input', () => {
      const term = searchInput.value;
      const filtered = filterNodesBySearch(term, allChapters);
      renderSidebar(filtered);
      currentSelectedButton = null;
    });
  </script>
</body>
</html>
"""

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 build_headings_html.py headings.json")
        sys.exit(1)

    json_path = Path(sys.argv[1])
    data = json.loads(json_path.read_text(encoding="utf-8"))

    serialized = json.dumps(data).replace("</", "<\\/")
    html = HTML_TEMPLATE.replace("__JSON_DATA__", serialized)

    output_path = json_path.with_suffix(".html")
    output_path.write_text(html, encoding="utf-8")

    print(f"✅ Wrote {output_path}")
    print("   Open this file in your browser to click through the headings.")

if __name__ == "__main__":
    main()
