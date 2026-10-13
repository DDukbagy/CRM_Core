// 브라우저용 Supabase 클라이언트
import { createBrowserClient } from "@supabase/ssr";
import type { SupabaseClient } from "@supabase/supabase-js";

let _client: SupabaseClient | null = null;

/**
 * 브라우저용 Supabase Client (singleton)
 * - 여러 곳에서 import해도 동일 인스턴스 사용
 */
export function supabaseBrowser(): SupabaseClient {
  if (_client) return _client;

  _client = createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  );

  return _client;
}

/**
 * 공용 인스턴스 (DashboardLayout 등에서 사용)
 */
export const supabase = supabaseBrowser();
