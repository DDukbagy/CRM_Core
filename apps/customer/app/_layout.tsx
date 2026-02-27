// app/_layout.tsx
import { Stack, useRouter, useSegments } from "expo-router";
import { useEffect, useState } from "react";
import { getAccessToken } from "@/lib/api";
import { View, ActivityIndicator } from "react-native";

export default function RootLayout() {
  const router = useRouter();
  const segments = useSegments();
  const [booting, setBooting] = useState(true);

  useEffect(() => {
    let mounted = true;

    (async () => {
      const token = await getAccessToken();
      const inAuthGroup = segments[0] === "(auth)";

      // 부팅 직후 라우팅 결정
      if (token && inAuthGroup) router.replace("/(tabs)");
      if (!token && !inAuthGroup) router.replace("/(auth)/login");

      if (mounted) setBooting(false);
    })();

    return () => {
      mounted = false;
    };
  }, [segments, router]);

  if (booting) {
    return (
      <View style={{ flex: 1, alignItems: "center", justifyContent: "center" }}>
        <ActivityIndicator />
      </View>
    );
  }

  return (
    <Stack>
      <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
      <Stack.Screen name="(auth)" options={{ headerShown: false }} />
      <Stack.Screen name="modal" options={{ presentation: "modal", title: "Modal" }} />
    </Stack>
  );
}