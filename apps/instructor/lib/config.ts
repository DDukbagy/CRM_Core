export const config = {
  // 끝의 "/" 는 떼어 낸다 (붙어 있으면 "//users/me" 처럼 요청되어 404)
  apiBaseUrl: (process.env.EXPO_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(/\/+$/, ""),
  supabaseUrl: process.env.EXPO_PUBLIC_SUPABASE_URL ?? "",
  supabaseAnonKey: process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY ?? "",
};
