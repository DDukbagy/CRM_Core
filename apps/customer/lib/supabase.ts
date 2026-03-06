// lib/supabase.ts
import { createClient } from "@supabase/supabase-js";
import { Platform } from "react-native";
import { config } from "./config";

const getStorage = () => {
  if (Platform.OS === "web") return undefined; // 웹은 localStorage 자동 사용
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  return require("@react-native-async-storage/async-storage").default;
};

export const supabase = createClient(config.supabaseUrl, config.supabaseAnonKey, {
  auth: {
    storage: getStorage(),
    autoRefreshToken: true,
    persistSession: true,
    detectSessionInUrl: false,
  },
});
