-- Run this once if 001_identity.sql was already applied with the legacy ADMIN role.
-- It converts the technical administrator into SYSTEM_ADMIN and removes project-access semantics.
begin;

alter table public.landguard_profiles drop constraint if exists landguard_profiles_role_check;
update public.landguard_profiles set role='SYSTEM_ADMIN' where role='ADMIN';
alter table public.landguard_profiles
  add constraint landguard_profiles_role_check
  check (role in ('SYSTEM_ADMIN','STATE_OFFICER','DISTRICT_OFFICER','IMPLEMENTING_AGENCY'));

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

commit;
