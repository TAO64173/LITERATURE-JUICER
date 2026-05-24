# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI Literature Juicer — a web app that converts uploaded academic PDFs into structured Excel matrix tables. Users sign up via Clerk (email+password), get 3 free uploads managed by Supabase, upload PDFs, and the system extracts key research dimensions via DeepSeek LLM, then outputs a formatted Excel file.

## Commands

```bash
# Backend (FastAPI)
python -m backend.main
# → http://127.0.0.1:8000

# Frontend (Next.js)
cd frontend && npm run dev
# → http://localhost:3000

# Run all tests
pytest

# Run a single test file
pytest tests/test_upload_api.py

# Build frontend for production
cd frontend && npm run build
```

## Environment Variables

**Backend** (`.env`):
- `DEEPSEEK_API_KEY` — DeepSeek API key for LLM extraction
- `DEEPSEEK_BASE_URL` — (optional) defaults to `https://api.deepseek.com`
- `DEEPSEEK_MODEL` — (optional) defaults to `deepseek-chat`
- `SUPABASE_URL` — Supabase project URL
- `SUPABASE_SERVICE_ROLE_KEY` — Supabase service role key (server-side only)
- `CLERK_JWKS_URL` — Clerk JWKS endpoint for JWT verification
- `CORS_ORIGINS` — comma-separated allowed origins

**Frontend** (`frontend/.env.local`):
- `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` — Clerk publishable key
- `CLERK_SECRET_KEY` — Clerk secret key
- `NEXT_PUBLIC_API_URL` — FastAPI backend URL (default: `http://localhost:8000`)

## Architecture

```
Next.js (Render)  →  FastAPI (Render)  →  Supabase (Postgres)
       ↓                    ↓
    Clerk Auth         Clerk JWT verification
    前端 UI             Supabase 额度管理

frontend/                  — Next.js frontend
  app/
    page.tsx               — Main page: hero, upload, features, footer
    layout.tsx             — ClerkProvider + ToastContainer
    sign-in/               — Clerk <SignIn /> page
    sign-up/               — Clerk <SignUp /> page
    api/proxy/[...path]/   — Proxies requests to FastAPI with Clerk JWT
    api/quota/             — GET /api/quota → FastAPI /quota
  components/
    Navbar.tsx             — Fixed nav with logo, links, QuotaDisplay, UserButton
    QuotaDisplay.tsx       — Shows remaining uploads (X / 3)
    UploadZone.tsx         — Drag-and-drop PDF upload
    FileGrid.tsx           — PDF thumbnail cards with status
    ProgressBar.tsx        — Processing progress bar
    Toast.tsx              — Toast notification system
  lib/api.ts               — API client: fetchQuota, uploadFiles (SSE stream reader)
  middleware.ts            — Clerk route protection

backend/                   — FastAPI API server
  main.py                  — App entry, CORS, mounts routers
  auth.py                  — Clerk JWT verification (RS256 via JWKS)
  supabase_client.py       — Supabase: ensure_user_and_quota, get_remaining_quota, deduct_quota
  api/
    upload_api.py          — POST /upload (SSE), GET /quota, GET /download/{filename}
    code_api.py            — POST /validate-code (legacy card code, kept but hidden)
  core/
    pdf_parser.py          — PyMuPDF text extraction
    llm_engine.py          — DeepSeek API with retry
    excel_writer.py        — openpyxl Excel generation
  uploads/                 — Uploaded PDFs (runtime, gitignored)
  outputs/                 — Generated Excel files (runtime, gitignored)

supabase/
  schema.sql               — users + quotas tables, deduct_quota() function

tests/
  conftest.py              — Auth + Supabase mock fixtures (autouse)
  test_upload_api.py       — Upload endpoint tests (11 tests)
  test_quota.py            — Quota endpoint tests
```

### Request Flow

1. User signs up/in via Clerk → redirected to `/` (protected by middleware)
2. Frontend calls `GET /api/quota` → proxy → FastAPI `/quota` → Supabase → shows "剩余额度：X / 3"
3. User uploads PDFs (drag/click) → frontend maintains `FileItem[]` state
4. User clicks "开始分析" → `POST /api/proxy/upload` (FormData) → proxy attaches Clerk JWT → FastAPI
5. Backend: `verify_clerk_token` → `ensure_user_and_quota` → check quota → `_validate_pdf` → `extract_text` → `extract_paper_info` → `write_excel` → `deduct_quota`
6. SSE events streamed back: progress → file_done → warning/error → done (with download_url)
7. Frontend parses SSE stream, updates progress bar + file status, shows download button

### Key Design Decisions

- **Next.js + Clerk + Supabase** — commercial-ready auth and quota management.
- **API proxy** — Next.js `/api/proxy/[...path]` forwards requests to FastAPI with Clerk JWT, avoiding CORS and URL exposure.
- **SSE streaming** — real-time progress events piped through the proxy via `ReadableStream`.
- **Card code system** — preserved in backend (`code_api.py`) but hidden from frontend.
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
- `tests/conftest.py` auto-mocks Clerk auth (`verify_clerk_token`) and Supabase functions for all tests.
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