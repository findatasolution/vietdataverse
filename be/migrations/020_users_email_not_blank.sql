-- 020: users.email can never be blank again.
--
-- Defect this closes (live 2026-06-30 → 2026-09-25):
--   An Auth0 *access* token carries an `email` claim only when the Action that
--   adds `{NAMESPACE}/email` is installed. Without it the claim is absent, and
--   /auth/me read that as "" and inserted it. users.email is UNIQUE, so the
--   first such insert succeeded and every later one collided with it — a
--   permanent 500 from /me for every new Auth0 identity, which read on the
--   frontend as "Vui lòng đăng nhập" for users who were already signed in.
--
-- Step 1 — repair the stranded row(s).
-- The row is REPAIRED, NOT DELETED: its auth0_id is a real Google identity and
-- resolve_identity() finds that person by auth0_id, so they keep their account.
-- `.invalid` is reserved by RFC 2606 and can never resolve, so the placeholder
-- can neither be mistaken for a real inbox nor receive mail. /auth/me replaces
-- it with the person's real address the next time they sign in.
UPDATE users
SET email = 'unknown-' || user_id || '@users.vietdataverse.invalid'
WHERE btrim(email) = '';

-- Step 2 — make the defect unrepresentable.
-- The application now refuses to insert a blank email; this is the backstop for
-- any path that forgets. Loud failure beats silent corruption: the previous
-- behaviour was a row that inserted fine and then blocked everyone after it.
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_email_not_blank;
ALTER TABLE users ADD CONSTRAINT users_email_not_blank CHECK (btrim(email) <> '');
