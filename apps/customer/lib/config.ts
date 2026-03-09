// lib/config.ts
export const config = {
  apiBaseUrl: process.env.EXPO_PUBLIC_API_BASE_URL ?? "http://localhost:8000",
  supabaseUrl: process.env.EXPO_PUBLIC_SUPABASE_URL ?? "",
  supabaseAnonKey: process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY ?? "",
};
