// app/edit-profile.tsx
import { useEffect, useState } from "react";
import {
  View,
  Text,
  TextInput,
  Pressable,
  Alert,
  ActivityIndicator,
  ScrollView,
  StyleSheet,
} from "react-native";
import { useRouter } from "expo-router";
import { apiFetch } from "@/lib/api";
import type { UserRead, UserUpdate } from "@/types/api";

export default function EditProfileScreen() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [displayName, setDisplayName] = useState("");
  const [username, setUsername] = useState("");
  const [phone, setPhone] = useState("");

  useEffect(() => {
    apiFetch<UserRead>("/users/me")
      .then((me) => {
        setDisplayName(me.display_name ?? "");
        setUsername(me.username ?? "");
        setPhone(me.phone ?? "");
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  async function handleSave() {
    if (!displayName.trim()) {
      Alert.alert("확인", "이름을 입력해주세요.");
      return;
    }
    setSaving(true);
    try {
      const body: UserUpdate = {
        display_name: displayName.trim(),
        username: username.trim() || undefined,
        phone: phone.trim() || undefined,
      };
      await apiFetch("/users/me", { method: "PATCH", body });
      Alert.alert("완료", "프로필이 수정되었습니다.");
      router.back();
    } catch (e: any) {
      const detail = (e?.body as any)?.detail ?? e?.message ?? "저장 실패";
      Alert.alert("오류", typeof detail === "string" ? detail : JSON.stringify(detail));
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <View style={s.center}><ActivityIndicator size="large" /></View>;
  }

  return (
    <ScrollView style={s.container} contentContainerStyle={{ padding: 20 }}>
      <Text style={s.label}>이름 *</Text>
      <TextInput
        value={displayName}
        onChangeText={setDisplayName}
        placeholder="표시될 이름"
        style={s.input}
      />

      <Text style={s.label}>사용자명</Text>
      <TextInput
        value={username}
        onChangeText={setUsername}
        placeholder="username (영문/숫자)"
        autoCapitalize="none"
        style={s.input}
      />

      <Text style={s.label}>전화번호</Text>
      <TextInput
        value={phone}
        onChangeText={setPhone}
        placeholder="010-0000-0000"
        keyboardType="phone-pad"
        style={s.input}
      />

      <Pressable
        style={[s.saveBtn, saving && { opacity: 0.6 }]}
        onPress={handleSave}
        disabled={saving}
      >
        <Text style={s.saveBtnText}>{saving ? "저장 중..." : "저장"}</Text>
      </Pressable>
    </ScrollView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f9fafb" },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  label: { fontSize: 13, fontWeight: "600", color: "#374151", marginBottom: 6, marginTop: 16 },
  input: {
    borderWidth: 1,
    borderColor: "#d1d5db",
    borderRadius: 10,
    padding: 14,
    fontSize: 15,
    backgroundColor: "#fff",
  },
  saveBtn: {
    marginTop: 32,
    padding: 14,
    backgroundColor: "#1a1a1a",
    borderRadius: 12,
  },
  saveBtnText: { color: "#fff", textAlign: "center", fontWeight: "700", fontSize: 15 },
});
