// app/(tabs)/profile.tsx
import { useEffect, useState, useCallback } from "react";
import { View, Text, Pressable, Alert, ActivityIndicator, StyleSheet, Platform } from "react-native";
import { useRouter, useFocusEffect } from "expo-router";
import { apiFetch } from "@/lib/api";
import { supabase } from "@/lib/supabase";
import type { UserRead } from "@/types/api";

const roleLabel: Record<string, string> = {
  CUSTOMER: "고객",
  INSTRUCTOR: "강사",
  CONTENT_MANAGER: "콘텐츠 매니저",
  ADMIN: "관리자",
};

export default function ProfileScreen() {
  const router = useRouter();
  const [user, setUser] = useState<UserRead | null>(null);
  const [loading, setLoading] = useState(true);

  // 프로필 수정 후 돌아왔을 때 자동 갱신
  useFocusEffect(
    useCallback(() => {
      setLoading(true);
      apiFetch<UserRead>("/users/me")
        .then(setUser)
        .catch((e) => console.error("프로필 로딩 실패:", e))
        .finally(() => setLoading(false));
    }, [])
  );

  async function handleLogout() {
    if (Platform.OS === "web") {
      if (!window.confirm("로그아웃 하시겠습니까?")) return;
      await supabase.auth.signOut();
    } else {
      Alert.alert("로그아웃", "로그아웃 하시겠습니까?", [
        { text: "취소", style: "cancel" },
        { text: "로그아웃", style: "destructive", onPress: () => supabase.auth.signOut() },
      ]);
    }
  }

  if (loading) {
    return <View style={s.center}><ActivityIndicator size="large" /></View>;
  }

  return (
    <View style={s.container}>
      {/* 프로필 헤더 */}
      <View style={s.header}>
        <View style={s.avatar}>
          <Text style={s.avatarText}>{user?.display_name?.[0] ?? "?"}</Text>
        </View>
        <Text style={s.name}>{user?.display_name}</Text>
        <Text style={s.role}>{roleLabel[user?.role ?? ""] ?? user?.role}</Text>
      </View>

      {/* 정보 카드 */}
      <View style={s.infoCard}>
        <InfoRow label="이메일" value={user?.email ?? "-"} />
        <InfoRow label="사용자명" value={user?.username ?? "-"} />
        <InfoRow label="전화번호" value={user?.phone ?? "미등록"} />
        <InfoRow label="가입일" value={user?.created_at ? user.created_at.slice(0, 10) : "-"} />
        {user?.manager_id ? (
          <InfoRow label="담당 강사 ID" value={user.manager_id.slice(0, 8) + "..."} />
        ) : (
          <InfoRow label="담당 강사" value="미배정" />
        )}
      </View>

      {/* 프로필 수정 */}
      <Pressable style={s.editBtn} onPress={() => router.push("/edit-profile" as any)}>
        <Text style={s.editBtnText}>프로필 수정</Text>
      </Pressable>

      {/* 로그아웃 */}
      <Pressable style={s.logoutBtn} onPress={handleLogout}>
        <Text style={s.logoutText}>로그아웃</Text>
      </Pressable>
    </View>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <View style={s.row}>
      <Text style={s.rowLabel}>{label}</Text>
      <Text style={s.rowValue}>{value}</Text>
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f9fafb" },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  header: { alignItems: "center", padding: 32, backgroundColor: "#fff", borderBottomWidth: 1, borderBottomColor: "#f3f4f6" },
  avatar: { width: 72, height: 72, borderRadius: 36, backgroundColor: "#1a1a1a", alignItems: "center", justifyContent: "center", marginBottom: 12 },
  avatarText: { color: "#fff", fontSize: 28, fontWeight: "700" },
  name: { fontSize: 20, fontWeight: "700", color: "#111" },
  role: { fontSize: 13, color: "#6b7280", marginTop: 4 },
  infoCard: { margin: 16, backgroundColor: "#fff", borderRadius: 12, overflow: "hidden", elevation: 2 },
  row: { flexDirection: "row", justifyContent: "space-between", paddingHorizontal: 16, paddingVertical: 14, borderBottomWidth: 1, borderBottomColor: "#f3f4f6" },
  rowLabel: { fontSize: 14, color: "#6b7280" },
  rowValue: { fontSize: 14, color: "#111", fontWeight: "500", maxWidth: "60%", textAlign: "right" },
  editBtn: { marginHorizontal: 16, marginTop: 8, padding: 14, backgroundColor: "#f3f4f6", borderRadius: 12 },
  editBtnText: { textAlign: "center", color: "#374151", fontWeight: "600", fontSize: 15 },
  logoutBtn: { marginHorizontal: 16, marginTop: 8, padding: 14, backgroundColor: "#fee2e2", borderRadius: 12 },
  logoutText: { textAlign: "center", color: "#ef4444", fontWeight: "700", fontSize: 15 },
});
