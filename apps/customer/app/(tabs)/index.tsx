// app/(tabs)/index.tsx
import { View, Text, Pressable, Alert } from "react-native";
import { apiFetch } from "@/lib/api";

export default function HomeScreen() {
  async function testApi() {
    try {
      // 백엔드에 health 엔드포인트가 없으면, 실제 있는 걸로 바꾸면 됨
      const data = await apiFetch<any>("/health", { requireAuth: false });
      Alert.alert("API OK", JSON.stringify(data));
    } catch (e: any) {
      Alert.alert("API ERROR", e?.message ?? "unknown");
    }
  }

  return (
    <View style={{ flex: 1, padding: 20, gap: 12 }}>
      <Text style={{ fontSize: 20, fontWeight: "700" }}>오늘 요약</Text>
      <Text>여기에 오늘 예약/수업 요약 카드가 들어갈 예정</Text>

      <Pressable onPress={testApi} style={{ padding: 12, borderRadius: 10, borderWidth: 1 }}>
        <Text style={{ textAlign: "center" }}>API 연결 테스트</Text>
      </Pressable>
    </View>
  );
}