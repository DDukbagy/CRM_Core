import * as Sentry from "@sentry/react-native";
import { Stack, useRouter, useSegments } from "expo-router";

const SENTRY_DSN = process.env.EXPO_PUBLIC_SENTRY_DSN;
if (SENTRY_DSN) {
  Sentry.init({
    dsn: SENTRY_DSN,
    environment: process.env.EXPO_PUBLIC_APP_ENV ?? "development",
    tracesSampleRate: 0.1,
  });
}
import { useEffect, useState } from "react";
import { View, ActivityIndicator, Platform } from "react-native";
import * as Notifications from "expo-notifications";
import { supabase } from "@/lib/supabase";
import { apiFetch } from "@/lib/api";
import type { Session } from "@supabase/supabase-js";

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
    shouldShowBanner: true,
    shouldShowList: true,
  }),
});

async function registerPushToken() {
  if (Platform.OS === "web") return;
  try {
    const { status } = await Notifications.requestPermissionsAsync();
    if (status !== "granted") return;
    const token = (await Notifications.getExpoPushTokenAsync()).data;
    await apiFetch("/users/me/push-token", {
      method: "PUT",
      body: JSON.stringify({ token }),
    });
  } catch {
    // 시뮬레이터 또는 권한 거부 시 무시
  }
}

export default function RootLayout() {
  const router = useRouter();
  const segments = useSegments();
  const [session, setSession] = useState<Session | null | undefined>(undefined);

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => setSession(session));
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_e, s) => setSession(s));
    return () => subscription.unsubscribe();
  }, []);

  useEffect(() => {
    if (session === undefined) return;
    const inAuth = segments[0] === "(auth)";
    if (session && inAuth) {
      router.replace("/(tabs)");
      registerPushToken();
    }
    if (!session && !inAuth) router.replace("/(auth)/login" as never);
  }, [session, segments, router]);

  if (session === undefined) {
    return (
      <View style={{ flex: 1, alignItems: "center", justifyContent: "center" }}>
        <ActivityIndicator />
      </View>
    );
  }

  return (
    <Stack>
      <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
      <Stack.Screen name="(auth)/login" options={{ headerShown: false }} />
      <Stack.Screen name="customer/[id]" options={{ title: "고객 상세" }} />
      <Stack.Screen name="passes" options={{ headerShown: false }} />
    </Stack>
  );
}
