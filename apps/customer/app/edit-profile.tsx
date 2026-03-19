// app/edit-profile.tsx
import { useEffect, useState, useMemo, useRef, useCallback } from "react";
import {
  View,
  Text,
  TextInput,
  Pressable,
  Alert,
  ActivityIndicator,
  ScrollView,
  StyleSheet,
  Modal,
  FlatList,
  Animated,
  Dimensions,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useRouter, useLocalSearchParams } from "expo-router";
import { apiFetch } from "@/lib/api";
import type { UserRead, UserUpdate } from "@/types/api";

const SCREEN_H = Dimensions.get("window").height;

const GENDER_OPTIONS = [
  { label: "남성", value: "MALE" },
  { label: "여성", value: "FEMALE" },
];

const currentYear = new Date().getFullYear();
const YEARS = Array.from({ length: currentYear - 1929 }, (_, i) => String(currentYear - 10 - i));
const MONTHS = Array.from({ length: 12 }, (_, i) => String(i + 1).padStart(2, "0"));

type PickerField = "year" | "month" | "day";

export default function EditProfileScreen() {
  const router = useRouter();
  const { user: userParam } = useLocalSearchParams<{ user: string }>();
  const slideAnim = useRef(new Animated.Value(0)).current;
  const [loading, setLoading] = useState(!userParam);
  const [saving, setSaving] = useState(false);

  const [displayName, setDisplayName] = useState("");
  const [username, setUsername] = useState("");
  const [phone, setPhone] = useState("");
  const [birthYear, setBirthYear] = useState("");
  const [birthMonth, setBirthMonth] = useState("");
  const [birthDay, setBirthDay] = useState("");
  const [pickerOpen, setPickerOpen] = useState<PickerField | null>(null);
  const [gender, setGender] = useState<string | null>(null);
  const [lessonPurpose, setLessonPurpose] = useState("");

  // 슬라이드 다운 후 콜백
  const dismiss = useCallback((onDone: () => void) => {
    slideAnim.stopAnimation();
    Animated.timing(slideAnim, {
      toValue: SCREEN_H,
      duration: 180,
      useNativeDriver: false,
    }).start(() => onDone());
  }, [slideAnim]);

  // 월/년도에 따라 유효한 일수 계산
  const days = useMemo(() => {
    if (!birthMonth) return Array.from({ length: 31 }, (_, i) => String(i + 1).padStart(2, "0"));
    const y = birthYear ? parseInt(birthYear) : 2000;
    const m = parseInt(birthMonth);
    const count = new Date(y, m, 0).getDate();
    return Array.from({ length: count }, (_, i) => String(i + 1).padStart(2, "0"));
  }, [birthYear, birthMonth]);

  useEffect(() => {
    if (birthDay && parseInt(birthDay) > days.length) setBirthDay("");
  }, [days]);

  useEffect(() => {
    const init = (me: UserRead) => {
      setDisplayName(me.display_name ?? "");
      setUsername(me.username ?? "");
      setPhone(me.phone ?? "");
      if (me.birth_date) {
        const [y, m, d] = me.birth_date.split("-");
        setBirthYear(y ?? "");
        setBirthMonth(m ?? "");
        setBirthDay(d ?? "");
      }
      setGender(me.gender ?? null);
      setLessonPurpose(me.lesson_purpose ?? "");
    };

    if (userParam) {
      init(JSON.parse(userParam) as UserRead);
    } else {
      apiFetch<UserRead>("/users/me")
        .then(init)
        .catch(() => {})
        .finally(() => setLoading(false));
    }
  }, []);

  async function handleSave() {
    if (!displayName.trim()) {
      Alert.alert("확인", "이름을 입력해주세요.");
      return;
    }
    const birthDate =
      birthYear && birthMonth && birthDay
        ? `${birthYear}-${birthMonth}-${birthDay}`
        : null;

    setSaving(true);
    try {
      const body: UserUpdate = {
        display_name: displayName.trim(),
        username: username.trim() || undefined,
        phone: phone.trim() || undefined,
        birth_date: birthDate,
        gender: gender,
        lesson_purpose: lessonPurpose.trim() || null,
      };
      await apiFetch("/users/me", { method: "PATCH", body });
      dismiss(() => router.back());
    } catch (e: any) {
      const detail = (e?.body as any)?.detail ?? e?.message ?? "저장 실패";
      Alert.alert("오류", typeof detail === "string" ? detail : JSON.stringify(detail));
    } finally {
      setSaving(false);
    }
  }

  const pickerItems =
    pickerOpen === "year" ? YEARS : pickerOpen === "month" ? MONTHS : days;

  const pickerTitle =
    pickerOpen === "year" ? "년도 선택" : pickerOpen === "month" ? "월 선택" : "일 선택";

  const handlePickerSelect = (val: string) => {
    if (pickerOpen === "year") setBirthYear(val);
    else if (pickerOpen === "month") setBirthMonth(val);
    else if (pickerOpen === "day") setBirthDay(val);
    setPickerOpen(null);
  };

  const formatPickerLabel = (field: PickerField, val: string) => {
    if (!val) return field === "year" ? "년도" : field === "month" ? "월" : "일";
    if (field === "year") return `${val}년`;
    if (field === "month") return `${Number(val)}월`;
    return `${Number(val)}일`;
  };

  if (loading) {
    return <View style={s.center}><ActivityIndicator size="large" /></View>;
  }

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: "#f9fafb" }} edges={["top", "bottom"]}>
      <Animated.View style={[{ flex: 1 }, { transform: [{ translateY: slideAnim }] }]}>
        {/* 헤더 */}
        <View style={s.header}>
          <Text style={s.headerTitle}>프로필 수정</Text>
        </View>

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
          <View style={s.birthRow}>
            {(["year", "month", "day"] as PickerField[]).map((field) => {
              const val = field === "year" ? birthYear : field === "month" ? birthMonth : birthDay;
              return (
                <Pressable key={field} style={s.birthBtn} onPress={() => setPickerOpen(field)}>
                  <Text style={val ? s.birthVal : s.birthPlaceholder}>
                    {formatPickerLabel(field, val)}
                  </Text>
                </Pressable>
              );
            })}
          </View>

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

          <View style={s.btnRow}>
            <Pressable
              style={s.cancelBtn}
              onPress={() => dismiss(() => router.back())}
              disabled={saving}
            >
              <Text style={s.cancelBtnText}>취소</Text>
            </Pressable>
            <Pressable
              style={[s.saveBtn, saving && { opacity: 0.6 }]}
              onPress={handleSave}
              disabled={saving}
            >
              <Text style={s.saveBtnText}>{saving ? "저장 중..." : "저장"}</Text>
            </Pressable>
          </View>
        </ScrollView>

        {/* 생년월일 피커 모달 */}
        <Modal
          visible={pickerOpen !== null}
          transparent
          animationType="slide"
          onRequestClose={() => setPickerOpen(null)}
        >
          <Pressable style={s.pickerOverlay} onPress={() => setPickerOpen(null)}>
            <Pressable style={s.pickerSheet} onPress={() => {}}>
              <View style={s.pickerHeader}>
                <Text style={s.pickerTitle}>{pickerTitle}</Text>
                <Pressable onPress={() => setPickerOpen(null)}>
                  <Text style={s.pickerClose}>닫기</Text>
                </Pressable>
              </View>
              <FlatList
                data={pickerItems}
                keyExtractor={(item) => item}
                style={{ maxHeight: 320 }}
                renderItem={({ item }) => {
                  const current =
                    pickerOpen === "year" ? birthYear : pickerOpen === "month" ? birthMonth : birthDay;
                  const selected = item === current;
                  return (
                    <Pressable
                      style={[s.pickerItem, selected && s.pickerItemSelected]}
                      onPress={() => handlePickerSelect(item)}
                    >
                      <Text style={[s.pickerItemText, selected && s.pickerItemTextSelected]}>
                        {pickerOpen === "year"
                          ? `${item}년`
                          : pickerOpen === "month"
                          ? `${Number(item)}월`
                          : `${Number(item)}일`}
                      </Text>
                    </Pressable>
                  );
                }}
              />
            </Pressable>
          </Pressable>
        </Modal>
      </Animated.View>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  header: {
    height: 52,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: "#fff",
    borderBottomWidth: 1,
    borderBottomColor: "#e5e7eb",
  },
  headerTitle: { fontSize: 16, fontWeight: "700", color: "#111" },
  container: { flex: 1, backgroundColor: "#f9fafb" },
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
  birthRow: { flexDirection: "row", gap: 8, marginTop: 4 },
  birthBtn: {
    flex: 1,
    borderWidth: 1,
    borderColor: "#d1d5db",
    borderRadius: 10,
    paddingVertical: 13,
    paddingHorizontal: 8,
    backgroundColor: "#fff",
    alignItems: "center",
  },
  birthVal: { fontSize: 15, color: "#111", fontWeight: "500" },
  birthPlaceholder: { fontSize: 15, color: "#9ca3af" },
  genderRow: { flexDirection: "row", gap: 8, marginTop: 4 },
  genderBtn: {
    flex: 1, paddingVertical: 10, borderRadius: 8,
    borderWidth: 1, borderColor: "#d1d5db",
    backgroundColor: "#fff", alignItems: "center",
  },
  genderBtnActive: { backgroundColor: "#1a1a1a", borderColor: "#1a1a1a" },
  genderBtnTxt: { fontSize: 13, color: "#374151", fontWeight: "600" },
  genderBtnTxtActive: { color: "#fff" },
  btnRow: { flexDirection: "row", gap: 10, marginTop: 32, marginBottom: 40 },
  cancelBtn: { flex: 1, padding: 14, backgroundColor: "#f3f4f6", borderRadius: 12, alignItems: "center" },
  cancelBtnText: { color: "#374151", fontWeight: "700", fontSize: 15 },
  saveBtn: { flex: 1, padding: 14, backgroundColor: "#1a1a1a", borderRadius: 12, alignItems: "center" },
  saveBtnText: { color: "#fff", textAlign: "center", fontWeight: "700", fontSize: 15 },
  pickerOverlay: { flex: 1, backgroundColor: "rgba(0,0,0,0.4)", justifyContent: "flex-end" },
  pickerSheet: { backgroundColor: "#fff", borderTopLeftRadius: 20, borderTopRightRadius: 20, paddingBottom: 32 },
  pickerHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", padding: 16, borderBottomWidth: 1, borderBottomColor: "#f3f4f6" },
  pickerTitle: { fontSize: 16, fontWeight: "700", color: "#111" },
  pickerClose: { fontSize: 14, color: "#6b7280" },
  pickerItem: { paddingVertical: 14, paddingHorizontal: 20 },
  pickerItemSelected: { backgroundColor: "#f0fdf4" },
  pickerItemText: { fontSize: 16, color: "#374151", textAlign: "center" },
  pickerItemTextSelected: { color: "#16a34a", fontWeight: "700" },
});
