-- Run once in the SQL Editor of YOUR Supabase project.
-- Passwords stay in Supabase-managed auth.users. No browser role can read these tables.
create table if not exists public.landguard_profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email text not null unique,
  display_name text not null,
  role text not null check (role in ('SYSTEM_ADMIN','STATE_OFFICER','DISTRICT_OFFICER','IMPLEMENTING_AGENCY')),
  status text not null default 'invited' check (status in ('invited','active','disabled')),
  state text,
  district text,
  project_ids text[] not null default '{}',
  invited_by uuid references auth.users(id) on delete set null,
  invitation_delivery text not null default 'not_sent' check (invitation_delivery in ('not_sent','accepted_by_brevo','failed')),
  invited_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  check (role not in ('STATE_OFFICER','DISTRICT_OFFICER') or (state is not null and length(trim(state)) > 0)),
  check (role <> 'DISTRICT_OFFICER' or (district is not null and length(trim(district)) > 0)),
  check (role <> 'IMPLEMENTING_AGENCY' or cardinality(project_ids) > 0)
);
create table if not exists public.landguard_sessions (
  token_hash text primary key,
  user_id uuid not null references public.landguard_profiles(id) on delete cascade,
  expires_at timestamptz not null,
  created_at timestamptz not null default now()
);
create index if not exists landguard_sessions_user_idx on public.landguard_sessions(user_id);
create table if not exists public.landguard_auth_limits (
  bucket text primary key,
  hits integer not null,
  expires_at timestamptz not null
);
create table if not exists public.landguard_auth_audit (
  id bigint generated always as identity primary key,
  actor_id uuid,
  subject_id uuid,
  event text not null,
  created_at timestamptz not null default now()
);
alter table public.landguard_profiles enable row level security;
alter table public.landguard_sessions enable row level security;
alter table public.landguard_auth_limits enable row level security;
alter table public.landguard_auth_audit enable row level security;
revoke all on public.landguard_profiles, public.landguard_sessions, public.landguard_auth_limits, public.landguard_auth_audit from public, anon, authenticated;
grant all on public.landguard_profiles, public.landguard_sessions, public.landguard_auth_limits, public.landguard_auth_audit to service_role;
grant usage, select on sequence public.landguard_auth_audit_id_seq to service_role;

create or replace function public.landguard_auth_rate_limit(p_bucket text, p_limit integer)
returns boolean language plpgsql security definer set search_path = '' as $$
declare n integer;
begin
  delete from public.landguard_auth_limits where expires_at < now();
  insert into public.landguard_auth_limits(bucket,hits,expires_at)
    values(p_bucket,1,now()+interval '2 minutes')
    on conflict(bucket) do update set hits=public.landguard_auth_limits.hits+1
    returning hits into n;
  return n <= p_limit;
end; $$;
revoke all on function public.landguard_auth_rate_limit(text,integer) from public,anon,authenticated;
grant execute on function public.landguard_auth_rate_limit(text,integer) to service_role;

create or replace function public.landguard_bootstrap_admin(p_id uuid,p_email text,p_name text)
returns void language plpgsql security definer set search_path = '' as $$
begin
  perform pg_advisory_xact_lock(26017,1);
  if exists(select 1 from public.landguard_profiles where role='SYSTEM_ADMIN') then
    raise exception 'System administrator already provisioned';
  end if;
  insert into public.landguard_profiles(id,email,display_name,role,status)
    values(p_id,p_email,p_name,'SYSTEM_ADMIN','invited');
end; $$;
revoke all on function public.landguard_bootstrap_admin(uuid,text,text) from public,anon,authenticated;
grant execute on function public.landguard_bootstrap_admin(uuid,text,text) to service_role;
