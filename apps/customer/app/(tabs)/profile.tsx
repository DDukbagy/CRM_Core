// app/(tabs)/profile.tsx
import { View, Text, Pressable, Alert } from "react-native";
import { useRouter } from "expo-router";
import { clearAccessToken } from "@/lib/api";

export default function ProfileScreen() {
  const router = useRouter();

  async function logout() {
    await clearAccessToken();
    Alert.alert("로그아웃", "토큰을 삭제했어.");
    router.replace("/(auth)/login");
  }

  return (
    <View style={{ flex: 1, padding: 20, gap: 12 }}>
      <Text style={{ fontSize: 18, fontWeight: "700" }}>내정보</Text>

      <Pressable onPress={logout} style={{ padding: 12, borderRadius: 10, borderWidth: 1 }}>
        <Text style={{ textAlign: "center" }}>로그아웃</Text>
      </Pressable>
    </View>
  );
}