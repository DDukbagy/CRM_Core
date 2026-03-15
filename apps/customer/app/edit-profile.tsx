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
  Switch,
} from "react-native";
import { useRouter } from "expo-router";
import { apiFetch } from "@/lib/api";
import type { UserRead, UserUpdate } from "@/types/api";

const GENDER_OPTIONS = [
  { label: "남성", value: "MALE" },
  { label: "여성", value: "FEMALE" },
];

export default function EditProfileScreen() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const [displayName, setDisplayName] = useState("");
  const [username, setUsername] = useState("");
  const [phone, setPhone] = useState("");
  const [birthDate, setBirthDate] = useState("");       // YYYY-MM-DD
  const [gender, setGender] = useState<string | null>(null);
  const [lessonPurpose, setLessonPurpose] = useState("");
  const [feedbackConsent, setFeedbackConsent] = useState(false);

  useEffect(() => {
    apiFetch<UserRead>("/users/me")
      .then((me) => {
        setDisplayName(me.display_name ?? "");
        setUsername(me.username ?? "");
        setPhone(me.phone ?? "");
        setBirthDate(me.birth_date ?? "");
        setGender(me.gender ?? null);
        setLessonPurpose(me.lesson_purpose ?? "");
        setFeedbackConsent(me.feedback_consent ?? false);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  async function handleSave() {
    if (!displayName.trim()) {
      Alert.alert("확인", "이름을 입력해주세요.");
      return;
    }
    // 생년월일 형식 검증 (입력한 경우)
    if (birthDate && !/^\d{4}-\d{2}-\d{2}$/.test(birthDate)) {
      Alert.alert("확인", "생년월일은 YYYY-MM-DD 형식으로 입력해주세요.");
      return;
    }
    setSaving(true);
    try {
      const body: UserUpdate = {
        display_name: displayName.trim(),
        username: username.trim() || undefined,
        phone: phone.trim() || undefined,
        birth_date: birthDate.trim() || null,
        gender: gender,
        lesson_purpose: lessonPurpose.trim() || null,
        feedback_consent: feedbackConsent,
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
      <Text style={s.sectionTitle}>기본 정보</Text>

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

      <Text style={[s.sectionTitle, { marginTop: 24 }]}>레슨 정보</Text>

      <Text style={s.label}>생년월일</Text>
      <TextInput
        value={birthDate}
        onChangeText={setBirthDate}
        placeholder="YYYY-MM-DD"
        keyboardType="numbers-and-punctuation"
        style={s.input}
        maxLength={10}
      />

      <Text style={s.label}>성별</Text>
      <View style={s.genderRow}>
        {GENDER_OPTIONS.map((opt) => (
          <Pressable
            key={String(opt.value)}
            style={[s.genderBtn, gender === opt.value && s.genderBtnActive]}
            onPress={() => setGender(opt.value)}
          >
            <Text style={[s.genderBtnTxt, gender === opt.value && s.genderBtnTxtActive]}>
              {opt.label}
            </Text>
          </Pressable>
        ))}
      </View>

      <Text style={s.label}>레슨 목적</Text>
      <TextInput
        value={lessonPurpose}
        onChangeText={setLessonPurpose}
        placeholder="예: 스코어 줄이기, 스윙 교정, 취미"
        multiline
        numberOfLines={2}
        style={[s.input, { height: 72, textAlignVertical: "top" }]}
      />

      <Text style={[s.sectionTitle, { marginTop: 24 }]}>공개 설정</Text>
      <View style={s.consentRow}>
        <View style={{ flex: 1 }}>
          <Text style={s.label}>피드백 게시물 공개 동의</Text>
          <Text style={s.consentDesc}>강사가 작성한 나의 피드백을 다른 사람에게 공개합니다</Text>
        </View>
        <Switch
          value={feedbackConsent}
          onValueChange={setFeedbackConsent}
          trackColor={{ false: "#e5e7eb", true: "#1a1a1a" }}
          thumbColor="#fff"
        />
      </View>

      <View style={s.btnRow}>
        <Pressable style={s.cancelBtn} onPress={() => router.back()} disabled={saving}>
          <Text style={s.cancelBtnText}>취소</Text>
        </Pressable>
        <Pressable style={[s.saveBtn, saving && { opacity: 0.6 }]} onPress={handleSave} disabled={saving}>
          <Text style={s.saveBtnText}>{saving ? "저장 중..." : "저장"}</Text>
        </Pressable>
      </View>
    </ScrollView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f9fafb" },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  sectionTitle: { fontSize: 12, fontWeight: "700", color: "#9ca3af", letterSpacing: 0.5, marginTop: 24, marginBottom: 4, textTransform: "uppercase" },
  label: { fontSize: 13, fontWeight: "600", color: "#374151", marginBottom: 6, marginTop: 16 },
  input: {
    borderWidth: 1,
    borderColor: "#d1d5db",
    borderRadius: 10,
    padding: 14,
    fontSize: 15,
    backgroundColor: "#fff",
  },
  genderRow: { flexDirection: "row", gap: 8, marginTop: 4 },
  consentRow: { flexDirection: "row", alignItems: "center", marginTop: 8, backgroundColor: "#fff", borderRadius: 10, padding: 14, borderWidth: 1, borderColor: "#d1d5db" },
  consentDesc: { fontSize: 12, color: "#9ca3af", marginTop: 2, lineHeight: 17 },
  genderBtn: {
    flex: 1, paddingVertical: 10, borderRadius: 8,
    borderWidth: 1, borderColor: "#d1d5db",
    backgroundColor: "#fff", alignItems: "center",
  },
  genderBtnActive: { backgroundColor: "#1a1a1a", borderColor: "#1a1a1a" },
  genderBtnTxt: { fontSize: 13, color: "#374151", fontWeight: "600" },
  genderBtnTxtActive: { color: "#fff" },
  btnRow: {
    flexDirection: "row",
    gap: 10,
    marginTop: 32,
    marginBottom: 40,
  },
  cancelBtn: {
    flex: 1,
    padding: 14,
    backgroundColor: "#f3f4f6",
    borderRadius: 12,
    alignItems: "center",
  },
  cancelBtnText: { color: "#374151", fontWeight: "700", fontSize: 15 },
  saveBtn: {
    flex: 1,
    padding: 14,
    backgroundColor: "#1a1a1a",
    borderRadius: 12,
    alignItems: "center",
  },
  saveBtnText: { color: "#fff", textAlign: "center", fontWeight: "700", fontSize: 15 },
});
