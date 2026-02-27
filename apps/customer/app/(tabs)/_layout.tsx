// app/(tabs)/_layout.tsx
import { Tabs } from "expo-router";

export default function TabsLayout() {
  return (
    <Tabs screenOptions={{ headerTitleAlign: "center" }}>
      <Tabs.Screen name="index" options={{ title: "홈" }} />
      <Tabs.Screen name="schedule" options={{ title: "스케줄" }} />
      <Tabs.Screen name="bookings" options={{ title: "예약" }} />
      <Tabs.Screen name="profile" options={{ title: "내정보" }} />
    </Tabs>
  );
}