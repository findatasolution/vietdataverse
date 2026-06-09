-- Migration 006: Align seller_profiles with zero-admin flow
-- Drop legacy LinkedIn requirement + allow 'auto_approved' apply_status

-- Bug 1: linkedin_url was NOT NULL (from 004), but zero-admin flow doesn't collect it at register
ALTER TABLE seller_profiles ALTER COLUMN linkedin_url DROP NOT NULL;

-- Bug 2: apply_status CHECK didn't include 'auto_approved' (from 005 omission)
ALTER TABLE seller_profiles DROP CONSTRAINT IF EXISTS seller_profiles_apply_status_check;
ALTER TABLE seller_profiles ADD CONSTRAINT seller_profiles_apply_status_check
    CHECK (apply_status IN ('pending','approved','rejected','auto_approved'));
