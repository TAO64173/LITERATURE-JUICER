# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI Literature Juicer — a web app that converts uploaded academic PDFs into structured Excel matrix tables. Users enter a card code (卡密) to validate quota, upload PDFs, and the system extracts key research dimensions via DeepSeek LLM, then outputs a formatted Excel file.

## Commands

```bash
# Run the server (hot reload)
python -m backend.main
# → http://127.0.0.1:8000

# Run all tests
pytest

# Run a single test file
pytest tests/test_upload_api.py

# Run a single test
pytest tests/test_upload_api.py::TestUploadPDFs::test_single_file_upload
```

## Environment Variables

Required in `.env`:
- `DEEPSEEK_API_KEY` — DeepSeek API key for LLM extraction
- `DEEPSEEK_BASE_URL` — (optional) defaults to `https://api.deepseek.com`
- `DEEPSEEK_MODEL` — (optional) defaults to `deepseek-chat`

## Architecture

```
backend/
  main.py              — FastAPI app entry, mounts routers + static files
  db_manager.py        — SQLite card code (卡密) CRUD: validate, deduct, query quota
  api/
    code_api.py        — POST /validate-code (card code validation)
    upload_api.py      — POST /upload (full pipeline), GET /download/{filename}
  core/
    pdf_parser.py      — PyMuPDF text extraction (front 3 + back 3 pages, skips references)
    llm_engine.py      — DeepSeek API call with retry; extracts question/method/metrics/innovation/limitation
    excel_writer.py    — openpyxl Excel generation with styled headers

frontend/
  templates/index.html — Single-page UI (Tailwind CDN, no React)
  static/js/app.js     — Vanilla JS: card code validation, file grid, upload, progress, download
  static/css/main.css  — Custom styles (navbar, upload zone, PDF grid thumbnails, cards)
```

### Request Flow

1. User enters card code → `POST /validate-code` → `db_manager.validate_code()`
2. User uploads PDFs (drag/click, multi-file, append) → front-end maintains `selectedFiles[]` array
3. User clicks "开始分析" → `POST /upload` with FormData
4. Backend per file: `_validate_pdf()` → save to `uploads/` → `pdf_parser.extract_text()` → `llm_engine.extract_paper_info()` → collect results
5. Backend writes all results to `outputs/literature_matrix.xlsx` via `excel_writer.write_excel()`
6. Returns `{success, files, results, download_url}` → front-end shows download button

### Key Design Decisions

- **No React** — vanilla JS + Tailwind CDN. Keep it simple.
- **No auth** — quota is card-code based (`codes_table` in SQLite).
- **Single Excel output** — all papers go into one file, overwritten on each upload.
- **LLM extraction** — DeepSeek API with 3x exponential backoff retry, 60s timeout, text truncated to 8000 chars.
- **PDF validation** — max 10MB, max 30 pages, must be valid PDF (PyMuPDF check).

## Development Rules

- **Simplicity first** — minimum code that solves the problem. No speculative abstractions.
- **Surgical changes** — touch only what the task requires. Don't refactor adjacent code.
- **Match existing style** — even if you'd do it differently.
- **Test before claiming done** — run `pytest`, verify the specific flow works.

## Testing

- Tests use `fastapi.testclient.TestClient` against the real app.
- Upload tests mock `extract_paper_info` to avoid real LLM calls.
- `monkeypatch.setattr("backend.api.upload_api.UPLOAD_DIR", tmp_path)` isolates file I/O.
- PDF test fixtures are generated with `fitz.open()` (minimal valid PDFs).
## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.