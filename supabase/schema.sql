-- Literature Juicer — Supabase Schema
-- Run this in the Supabase SQL Editor

-- Users table: synced from Clerk on first upload
create table if not exists public.users (
  id uuid primary key default gen_random_uuid(),
  clerk_user_id text unique not null,
  email text not null,
  role text not null default 'user',
  invite_code varchar(5) unique,
  invited_by text,
  invite_rewarded boolean default false,
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

-- Invite records: tracks successful invite referrals
create table if not exists public.invite_records (
  id uuid primary key default gen_random_uuid(),
  inviter_user_id uuid not null references public.users(id) on delete cascade,
  invited_user_id uuid not null references public.users(id) on delete cascade,
  invite_code varchar(5) not null,
  reward_quota integer not null default 2,
  created_at timestamptz not null default now()
);

-- Redeem codes: prepaid quota codes (卡密)
create table if not exists public.redeem_codes (
  id uuid primary key default gen_random_uuid(),
  code varchar(12) unique not null,
  quota_amount integer not null,
  status text not null default 'unused',
  used_by uuid references public.users(id),
  used_at timestamptz,
  created_at timestamptz not null default now(),
  expires_at timestamptz
);

-- Orders table: tracks payment orders (Mapay EPay)
create table if not exists public.orders (
  id text primary key,
  user_id uuid not null references public.users(id) on delete cascade,
  amount numeric(10,2) not null,
  credits integer not null,
  status text not null default 'pending',
  provider text not null default 'mapay',
  provider_order_id text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Indexes
create index if not exists idx_users_clerk_user_id on public.users(clerk_user_id);
create index if not exists idx_quotas_user_id on public.quotas(user_id);
create index if not exists idx_usage_history_user_id on public.usage_history(user_id);
create index if not exists idx_analysis_history_user_id on public.analysis_history(user_id);
create index if not exists idx_invite_records_inviter on public.invite_records(inviter_user_id);
create index if not exists idx_invite_records_invited on public.invite_records(invited_user_id);
create index if not exists idx_redeem_codes_code on public.redeem_codes(code);
create index if not exists idx_orders_user_id on public.orders(user_id, status);
create index if not exists idx_orders_provider_order_id on public.orders(provider_order_id);

-- Row Level Security (backend uses service role key, bypasses RLS)
alter table public.users enable row level security;
alter table public.quotas enable row level security;
alter table public.usage_history enable row level security;
alter table public.analysis_history enable row level security;
alter table public.invite_records enable row level security;
alter table public.redeem_codes enable row level security;
alter table public.orders enable row level security;

-- Schema-level permissions (REQUIRED for PostgREST access)
grant usage on schema public to service_role;
grant usage on schema public to anon;

-- Grant permissions to service_role (backend uses this role)
grant select, insert, update, delete on public.users to service_role;
grant select, insert, update, delete on public.quotas to service_role;
grant select, insert, update, delete on public.usage_history to service_role;
grant select, insert, update, delete on public.analysis_history to service_role;
grant select, insert, update, delete on public.invite_records to service_role;
grant select, insert, update, delete on public.redeem_codes to service_role;
grant select, insert, update, delete on public.orders to service_role;

-- Grant to anon for any public reads if needed
grant select on public.users to anon;
grant select on public.quotas to anon;

-- Default privileges for future objects
alter default privileges in schema public grant all on tables to service_role;
alter default privileges in schema public grant all on functions to service_role;
alter default privileges in schema public grant all on sequences to service_role;

-- Atomic quota deduction function (single unit)
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

-- Atomic batch quota deduction (deduct N units at once)
create or replace function deduct_quota_batch(p_user_id uuid, p_count integer)
returns integer as $$
declare
  v_remaining integer;
begin
  select total_quota - used_quota into v_remaining
  from quotas where user_id = p_user_id for update;

  if v_remaining is null or v_remaining < p_count then
    return -1;
  end if;

  update quotas set used_quota = used_quota + p_count where user_id = p_user_id;
  return v_remaining - p_count;
end;
$$ language plpgsql;

-- Grant execute on RPC functions to service_role
grant execute on function deduct_quota(uuid) to service_role;
grant execute on function deduct_quota_batch(uuid, integer) to service_role;

-- Atomic quota addition (for invite rewards and redeem codes)
create or replace function add_quota(p_user_id uuid, p_amount integer)
returns integer as $$
declare
  v_new_total integer;
begin
  update quotas set total_quota = total_quota + p_amount
  where user_id = p_user_id
  returning total_quota - used_quota into v_new_total;

  if v_new_total is null then
    return -1;
  end if;

  return v_new_total;
end;
$$ language plpgsql;

grant execute on function add_quota(uuid, integer) to service_role;
