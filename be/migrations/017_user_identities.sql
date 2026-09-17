-- Migration 017 (USER_DB): extra Auth0 identities for one account.
-- users.email and users.auth0_id are both UNIQUE, so a second login method for
-- the same person (e.g. Google after email/password) had nowhere to go: every
-- router looked the user up by auth0_id and found nothing. be/services/identity.py
-- reads this table and hands routers the account's own users.auth0_id.
-- Rows are added by an admin, never automatically (account pre-hijacking guard).

CREATE TABLE IF NOT EXISTS user_identities (
    auth0_sub  TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    linked_at  TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_identities_user_id ON user_identities (user_id);
