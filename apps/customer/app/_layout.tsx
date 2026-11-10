// 앱 루트: 로그인 상태에 따라 화면 이동, Sentry, 푸시 알림 등록
import * as Sentry from "@sentry/react-native";
import { Stack, useRouter, useSegments } from "expo-router";
import { useEffect, useState } from "react";
import { View, ActivityIndicator } from "react-native";
import { supabase } from "@/lib/supabase";
import { configureForegroundNotifications, registerPushToken, subscribeNotificationTaps } from "@/lib/push";
import type { Session } from "@supabase/supabase-js";

const SENTRY_DSN = process.env.EXPO_PUBLIC_SENTRY_DSN;
if (SENTRY_DSN) {
  Sentry.init({
    dsn: SENTRY_DSN,
    environment: process.env.EXPO_PUBLIC_APP_ENV ?? "development",
    tracesSampleRate: 0.1,
  });
}

configureForegroundNotifications();

export default function RootLayout() {
  const router = useRouter();
  const segments = useSegments();
  const [session, setSession] = useState<Session | null | undefined>(undefined);

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
    });

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session);
    });

    return () => subscription.unsubscribe();
  }, []);

  useEffect(() => {
    if (session === undefined) return;

    const inAuthGroup = segments[0] === "(auth)";
    if (session && inAuthGroup) {
      router.replace("/(tabs)");
    }
    if (!session && !inAuthGroup) {
      router.replace("/(auth)/login" as any);
    }
  }, [session, segments, router]);

  // 로그인된 사용자마다 한 번 푸시 토큰 등록 (앱을 로그인 상태로 다시 열 때도 포함)
  const userId = session?.user.id;
  useEffect(() => {
    if (userId) registerPushToken();
  }, [userId]);

  // 알림을 누르면 해당 예약 상세로 이동 (로그인 상태에서만)
  useEffect(() => {
    if (!userId) return;
    return subscribeNotificationTaps((route) => router.push(route as any));
  }, [userId, router]);

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
      <Stack.Screen name="booking/[id]" options={{ title: "예약 상세" }} />
      <Stack.Screen name="edit-profile" options={{ headerShown: false, animation: "none" }} />
    </Stack>
  );
}
