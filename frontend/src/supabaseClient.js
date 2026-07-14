import { createClient } from "@supabase/supabase-js";

// The Supabase client wants the bare project URL (https://xxx.supabase.co),
// but it's easy to instead copy the REST endpoint shown elsewhere in the
// dashboard (which has /rest/v1/ appended) — strip down to the origin so
// either form works.
const rawUrl = import.meta.env.VITE_SUPABASE_URL;
const url = rawUrl ? new URL(rawUrl).origin : rawUrl;
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;
const isConfigured = Boolean(url) && Boolean(anonKey) && url !== "..." && anonKey !== "...";

if (!isConfigured) {
  console.warn(
    "VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY are not set — sign in and history will not work. " +
      "Copy frontend/.env.example to frontend/.env and fill them in."
  );
}

// Falls back to a syntactically valid placeholder so createClient doesn't
// throw and take the whole app down before Supabase is configured — auth
// calls will simply fail with a clear network/auth error instead, which the
// UI already handles.
export const supabase = createClient(
  isConfigured ? url : "https://placeholder.supabase.co",
  isConfigured ? anonKey : "placeholder-anon-key"
);
