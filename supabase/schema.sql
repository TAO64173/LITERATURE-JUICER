-- Literature Juicer — Supabase Schema
-- Run this in the Supabase SQL Editor

-- Users table: synced from Clerk on first upload
create table if not exists public.users (
  id uuid primary key default gen_random_uuid(),
  clerk_user_id text unique not null,
  email text not null,
  created_at timestamptz not null default now()
);

-- Quotas table: one row per user
create table if not exists public.quotas (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  total_quota integer not null default 3,
  used_quota integer not null default 0,
  created_at timestamptz not null default now(),
  constraint unique_user_quota unique (user_id)
);

-- Usage history: tracks each successful upload+process operation
create table if not exists public.usage_history (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  files_count integer not null default 1,
  created_at timestamptz not null default now()
);

-- Analysis history: tracks individual PDF analysis records per user
create table if not exists public.analysis_history (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  filename text not null,
  status text not null default 'processing',
  result_url text,
  created_at timestamptz not null default now()
);

-- Indexes
create index if not exists idx_users_clerk_user_id on public.users(clerk_user_id);
create index if not exists idx_quotas_user_id on public.quotas(user_id);
create index if not exists idx_usage_history_user_id on public.usage_history(user_id);
create index if not exists idx_analysis_history_user_id on public.analysis_history(user_id);

-- Row Level Security (backend uses service role key, bypasses RLS)
alter table public.users enable row level security;
alter table public.quotas enable row level security;
alter table public.usage_history enable row level security;
alter table public.analysis_history enable row level security;

-- Atomic quota deduction function
create or replace function deduct_quota(p_user_id uuid)
returns integer as $$
declare
  v_remaining integer;
begin
  select total_quota - used_quota into v_remaining
  from quotas where user_id = p_user_id for update;

  if v_remaining is null or v_remaining <= 0 then
    return -1;
  end if;

  update quotas set used_quota = used_quota + 1 where user_id = p_user_id;
  return v_remaining - 1;
end;
$$ language plpgsql;
