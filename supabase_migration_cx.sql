-- ============================================
-- CX Improvements Migration (ready to paste)
-- Run in Supabase SQL Editor
-- Safe to re-run (uses IF NOT EXISTS / OR REPLACE)
-- ============================================

-- 1. Allow onboarding sessions without a shop yet
ALTER TABLE chat_sessions
  ALTER COLUMN shop_id DROP NOT NULL;

-- 2. Cache first message while user picks a shop
ALTER TABLE chat_sessions
  ADD COLUMN IF NOT EXISTS pending_query text;

ALTER TABLE chat_sessions
  ADD COLUMN IF NOT EXISTS pending_voice_file_id text;

-- 3. Short-term conversational memory (last 3–4 turns)
CREATE TABLE IF NOT EXISTS chat_history (
  id bigserial PRIMARY KEY,
  chat_id bigint NOT NULL,
  role text NOT NULL CHECK (role IN ('user', 'assistant')),
  message text NOT NULL,
  created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chat_history_chat_id_created_at
  ON chat_history (chat_id, created_at DESC);

-- 4. Upsert pending query (text or __VOICE__ marker + file id)
CREATE OR REPLACE FUNCTION upsert_pending_query(
  p_chat_id bigint,
  p_query text,
  p_voice_file_id text DEFAULT NULL
)
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
  INSERT INTO chat_sessions (chat_id, pending_query, pending_voice_file_id)
  VALUES (p_chat_id, p_query, p_voice_file_id)
  ON CONFLICT (chat_id) DO UPDATE
    SET pending_query = EXCLUDED.pending_query,
        pending_voice_file_id = EXCLUDED.pending_voice_file_id;
END;
$$;

-- 5. Fetch recent history for query rewriting (uses existing "message" column)
CREATE OR REPLACE FUNCTION get_recent_chat_history(
  p_chat_id bigint,
  p_limit int DEFAULT 4
)
RETURNS TABLE (role text, content text)
LANGUAGE sql
STABLE
AS $$
  SELECT h.role, h.message AS content
  FROM chat_history h
  WHERE h.chat_id = p_chat_id
  ORDER BY h.created_at DESC
  LIMIT p_limit;
$$;

-- 6. Grant RPC access to service role / API (if not already granted)
GRANT EXECUTE ON FUNCTION upsert_pending_query(bigint, text, text) TO service_role;
GRANT EXECUTE ON FUNCTION get_recent_chat_history(bigint, int) TO service_role;

-- Optional: verify
-- SELECT * FROM chat_sessions LIMIT 5;
-- SELECT * FROM get_recent_chat_history(123456789, 4);
