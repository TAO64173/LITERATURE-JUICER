# Deployment Guide

## Overview

- **Frontend**: Vercel (Next.js)
- **Backend**: Render or any Python host (FastAPI + Uvicorn)
- **Database**: Supabase (Postgres)
- **Auth**: Clerk

---

## 1. Supabase Setup

1. Create a project at [supabase.com](https://supabase.com)
2. Go to **SQL Editor** and run `supabase/schema.sql`
3. Copy the **Project URL** and **service_role key** (Settings → API)

## 2. Clerk Setup

1. Create an application at [clerk.com](https://clerk.com)
2. Enable **Email + Password** sign-in
3. Copy keys from the Clerk Dashboard:
   - **Publishable Key** (pk_test_...)
   - **Secret Key** (sk_test_...)
   - **JWKS URL** (from JWT Templates → show JWKS URL)

## 3. Backend (Render)

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DEEPSEEK_API_KEY` | Yes | DeepSeek API key |
| `DEEPSEEK_BASE_URL` | No | Default: `https://api.deepseek.com` |
| `DEEPSEEK_MODEL` | No | Default: `deepseek-chat` |
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes | Supabase service_role key |
| `CLERK_JWKS_URL` | Yes | Clerk JWKS endpoint |
| `CLERK_SECRET_KEY` | Yes | Clerk secret key (for email fetch) |
| `CORS_ORIGINS` | No | Comma-separated origins |

### Render Settings

- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
- **Root Directory**: project root

## 4. Frontend (Vercel)

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Yes | Clerk publishable key |
| `CLERK_SECRET_KEY` | Yes | Clerk secret key |
| `NEXT_PUBLIC_CLERK_SIGN_IN_URL` | No | `/sign-in` |
| `NEXT_PUBLIC_CLERK_SIGN_UP_URL` | No | `/sign-up` |
| `NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL` | No | `/` |
| `NEXT_PUBLIC_CLERK_AFTER_SIGN_UP_URL` | No | `/` |
| `NEXT_PUBLIC_API_URL` | Yes | Backend URL (e.g. `https://your-api.onrender.com`) |
| `NEXT_PUBLIC_SUPABASE_URL` | No | Supabase URL (if using client-side Supabase) |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | No | Supabase anon key |

### Vercel Settings

- **Framework Preset**: Next.js
- **Root Directory**: `frontend`
- **Build Command**: `npm run build` (default)
- **Output**: `.next` (default)

## 5. Database Migration

If upgrading from a version without invite/redeem tables, run this in Supabase SQL Editor:

```sql
-- Add invite columns to users table
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS invite_code VARCHAR(5) UNIQUE;
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS invited_by TEXT;
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS invite_rewarded BOOLEAN DEFAULT FALSE;

-- Create invite_records table
CREATE TABLE IF NOT EXISTS public.invite_records (...);
-- (copy from schema.sql)

-- Create redeem_codes table
CREATE TABLE IF NOT EXISTS public.redeem_codes (...);
-- (copy from schema.sql)

-- Add indexes, RLS, grants (copy from schema.sql)
```

Or simply re-run the full `schema.sql` — all statements use `IF NOT EXISTS`.

## 6. Insert Test Redeem Codes

```sql
INSERT INTO public.redeem_codes (code, quota_amount, status) VALUES
  ('TEST10A', 10, 'unused'),
  ('TEST20B', 20, 'unused');
```

## 7. Verify

1. Visit frontend URL → sign up → should see 3 free uploads
2. Visit `/pricing` → should see invite code and redeem section
3. Share invite link → new user signs up → inviter gets +2
4. Enter redeem code → quota increases
5. Admin account → shows unlimited quota
