## Paediatric Pain Manual Navigation Preview

This repo contains a small toolchain that extracts headings from the PDF handbook and generates a clickable HTML navigator with live PDF rendering (via pdf.js). These instructions assume macOS 13+ with the stock `python3`.

### 1. Install dependencies

```bash
cd "/Users/luke/Developer/clients/Waikato Hospital"
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip pdfplumber
```

> Tip: keep the virtual environment active whenever you regenerate the data.

### 2. Detect headings and embed PDF metadata

```bash
source .venv/bin/activate
python3 detect_headings.py "Pain Management Handbook 2019. palliative (PDF).pdf" --json > headings.json
```

This writes `headings.json` in the following shape so downstream tools (and future chatbots) know which PDF to load:

```json
{
  "pdf": "Pain Management Handbook 2019. palliative (PDF).pdf",
  "pdf_path": "Pain Management Handbook 2019. palliative (PDF).pdf",
  "headings": [ ... ]
}
```

### 3. Build the HTML preview

```bash
source .venv/bin/activate
python3 build_headings_html.py headings.json
```

Opening `headings.html` will now show all sections on the left and render the real PDF page on the right as you click each heading.

### 4. Serve locally on macOS

Modern browsers block pdf.js from fetching `file://` URLs. Run a tiny static server so the HTML and PDF are both served over HTTP:

```bash
source .venv/bin/activate
python3 -m http.server 8000
```

Then open `http://localhost:8000/headings.html` (the PDF lives in the same folder, so pdf.js can request it directly).

### 5. Feeding the data to a chatbot

- Use `headings.json` as the source of truth for your navigation tree and associated PDF name.
- When a user asks for a section, map their intent to a heading node, then serve the relevant PDF page (or pre-rendered snippet) referenced by `pdf`/`pdf_path`.
- Because the JSON format is stable, backend services can stream the same payload to Teams tabs, bots, or other viewers without extra glue code.

### Troubleshooting

- If `detect_headings.py` errors, ensure the PDF filename is quoted (it contains spaces and parentheses).
- Regeneration is idempotent; rerun steps 2–4 whenever the PDF changes or you tweak detection heuristics.
- If pdf.js fails to load a page, confirm the PDF sits alongside `headings.html` when served over HTTP.

